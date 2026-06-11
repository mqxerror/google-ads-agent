"""Higgsfield CLI subprocess client.

Ported from meta-ads-agent's slice-B implementation. The crucial pivot
that motivated the original code was that the PyPI `higgsfield-client`
SDK rejects every Higgsfield model id ("Model not found") because the
30+ models live behind the CLI surface, not the API-key surface — so
we shell out to the official `@higgsfield/cli` npm binary instead.

Setup (operator, once per machine)
----------------------------------
    npm install -g @higgsfield/cli
    higgsfield login          # browser cookie paste; OAuth → ~/.higgsfield/

Per call
--------
    higgsfield --json generate create <model> --prompt "..." --wait
               --wait-timeout <Xs> [--aspect_ratio …] [--resolution …]
               [--seed N] [--soul-id UUID]

The CLI emits a JSON array of job dicts on stdout; each completed job
carries the rendered media at `result_url`. We pick the first
completed URL.

Auth is machine-wide — this google-ads-agent build deliberately does
NOT carry the per-account vault / cookie-paste UI that meta-ads-agent
ships. The operator runs `higgsfield login` once on the box and the
backend inherits that state through `$HOME`. If `$HOME` isn't set
correctly (systemd / launchd contexts), the CLI will raise an `auth`
error on first call — the structured `_classify_cli_error` paths
surface a clear `higgsfield login` nudge.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import shutil
from typing import Any

logger = logging.getLogger(__name__)


class HiggsfieldError(Exception):
    """Structured failure surfacing the upstream CLI / runtime mode.

    `code` ∈ {auth, cli, run, shape, nsfw}. Router maps:
      - auth → 401 (the operator must `higgsfield login`)
      - cli  → 400 (our argv was wrong — usage error, unknown model)
      - nsfw → 422 (content filter flagged the prompt; rephrase)
      - run, shape → 502 (upstream Higgsfield problem or unparseable output)
    """

    def __init__(self, *, message: str, code: str | None = None) -> None:
        self.code = code
        self.message = message
        super().__init__(f"higgsfield error ({code or '?'}): {message}")


# Hard ceiling for one image-gen call. Higgsfield's image models run
# 30–120s in practice; 180s is comfortable headroom while still failing
# fast if the CLI hangs on a Chrome-bridge fallback or stuck job. Video
# callers (slice S4) construct with `timeout_s=600` to allow for the
# 5-10 min veo3_1 / kling3_0 runs.
_DEFAULT_TIMEOUT_S = 180.0


class HiggsfieldClient:
    """CLI-backed client wrapping the official ``@higgsfield/cli``
    (npm) binary. Auth is machine-wide.

    The constructor accepts an explicit `timeout_s` so callers building
    against the long-running video models can extend the CLI's
    `--wait-timeout` plus the asyncio subprocess timeout in lockstep.
    """

    def __init__(self, *, timeout_s: float = _DEFAULT_TIMEOUT_S) -> None:
        self._timeout_s = timeout_s

    def __repr__(self) -> str:  # pragma: no cover
        return f"HiggsfieldClient(timeout_s={self._timeout_s})"

    async def submit_image(self, *, model: str, prompt: str, **params: Any) -> dict[str, Any]:
        """Submit + wait for one image. Returns
        ``{"image_url": <url>, "raw": <CLI JSON envelope>}``.

        Accepted `params`: ``aspect_ratio`` (→ ``--aspect_ratio``),
        ``resolution`` (→ ``--resolution``), ``quality`` (→ ``--quality``),
        ``seed`` (→ ``--seed``), ``soul_id`` (→ ``--soul-id``). Unknown
        keys are ignored.
        """
        argv = _build_cli_argv(
            model=model, prompt=prompt, timeout_s=self._timeout_s, **params,
        )
        try:
            stdout, stderr, code = await asyncio.wait_for(
                _run_cli(argv), timeout=self._timeout_s,
            )
        except asyncio.TimeoutError as e:
            raise HiggsfieldError(
                message=(
                    f"CLI timed out after {self._timeout_s:.0f}s — the model "
                    "may be queued or the CLI is stuck. Try a different model "
                    "or re-run when Higgsfield is less loaded."
                ),
                code="run",
            ) from e
        if code != 0:
            err = (stderr or stdout or "").strip()
            # Higgsfield's polling endpoint (https://fnf.higgsfield.ai/
            # agents/jobs/<uuid>) is intermittently unreachable; when
            # the job submitted fine but the wait poll dies, the CLI's
            # stderr carries the URL we can extract a job id from.
            # Retry just the wait once before giving up.
            recovered_id = _extract_job_id_from_unreachable(err)
            if recovered_id:
                try:
                    stdout, stderr, code = await asyncio.wait_for(
                        _run_cli(_build_wait_argv(recovered_id)),
                        timeout=self._timeout_s,
                    )
                except asyncio.TimeoutError:
                    code = 1  # fall through to the original error path
            elif _is_upstream_5xx(err):
                # The SUBMIT endpoint itself returned 502/503/504 — the
                # job was never created. Brief backoff + retry whole
                # submit once. 2s is the right shape: most of their
                # blips clear in <1s; longer doesn't help an outage.
                logger.info("higgsfield submit hit upstream 5xx; retrying once after 2s")
                await asyncio.sleep(2.0)
                try:
                    stdout, stderr, code = await asyncio.wait_for(
                        _run_cli(argv), timeout=self._timeout_s,
                    )
                except asyncio.TimeoutError:
                    code = 1
            if code != 0:
                err = (stderr or stdout or "").strip()
                msg = _summarize_cli_error(err) or "cli failed"
                if recovered_id:
                    msg = (
                        f"upstream Higgsfield API was unreachable mid-poll. "
                        f"The job WAS submitted (id={recovered_id}); recover "
                        f"the image with `higgsfield generate get {recovered_id}`. "
                        f"Original error: {msg}"
                    )
                elif _is_upstream_5xx(err):
                    msg = (
                        "Higgsfield's API is unhealthy right now (returned "
                        f"5xx twice). This is upstream, not our app — wait "
                        f"a few minutes and retry. Original error: {msg}"
                    )
                raise HiggsfieldError(
                    message=msg,
                    code=_classify_cli_error(err),
                )
        # Edge case: CLI exited 0 but printed nothing on stdout. Rich's
        # Console writes status lines to stderr in non-tty mode; surface
        # that verbatim instead of the cryptic "shape: empty stdout".
        if not stdout.strip() and stderr.strip():
            raise HiggsfieldError(
                message=_summarize_cli_error(stderr.strip()),
                code=_classify_cli_error(stderr),
            )
        jobs = _parse_envelope(stdout)
        url = _first_raw_url(jobs)
        if not url:
            statuses = [str(j.get("status") or "?") for j in jobs if isinstance(j, dict)]
            raise HiggsfieldError(
                message=f"no result_url in CLI output; jobs={len(jobs)} statuses={statuses}",
                code="shape",
            )
        return {"image_url": url, "raw": jobs}

    async def submit_video(self, *, model: str, prompt: str, **params: Any) -> dict[str, Any]:
        """Submit + wait for one video. Same return shape as
        ``submit_image`` (the URL key is still ``image_url`` — kept
        consistent so call-sites that don't care about media type can
        share code). Slice S4 wires the video model picker."""
        return await self.submit_image(model=model, prompt=prompt, **params)

    async def estimate_cost(
        self, *, model: str, prompt: str, **params: Any,
    ) -> dict[str, Any]:
        """Run `higgsfield --json generate cost <model> --prompt "..."`.
        Returns the parsed `{credits, credits_exact}` envelope — the
        UI displays this next to the Generate button so the operator
        sees credit spend BEFORE clicking, not after.

        Same param surface as submit_image so the cost reflects what
        the actual submit will cost (aspect, duration, soul, etc.
        affect price upstream).
        """
        bin_path = shutil.which("higgsfield")
        if bin_path is None:
            raise HiggsfieldError(
                message="higgsfield CLI not on PATH",
                code="cli",
            )
        argv = [bin_path, "--json", "generate", "cost", model, "--prompt", prompt]
        if (a := params.get("aspect_ratio")):
            argv.extend(["--aspect_ratio", str(a)])
        if (d := params.get("duration")) is not None:
            argv.extend(["--duration", str(d)])
        if (sid := params.get("soul_id")):
            argv.extend(["--soul-id", str(sid)])
        try:
            stdout, stderr, code = await asyncio.wait_for(
                _run_cli(argv), timeout=30.0,
            )
        except asyncio.TimeoutError as e:
            raise HiggsfieldError(
                message="cost lookup timed out after 30s", code="run",
            ) from e
        if code != 0:
            err = (stderr or stdout or "").strip()
            raise HiggsfieldError(
                message=_summarize_cli_error(err) or "cost lookup failed",
                code=_classify_cli_error(err),
            )
        try:
            return json.loads(stdout.strip())
        except json.JSONDecodeError as e:
            raise HiggsfieldError(
                message=f"cost CLI returned non-JSON: {stdout[:120]!r}", code="shape",
            ) from e

    async def upload_media(self, *, file_path: str) -> dict[str, Any]:
        """Upload one local image / video to higgsfield, returning the
        envelope (contains the `id` we then pass to soul-id create or
        generate create --image). Used by the Soul-training flow to
        turn local reference photos into upload IDs."""
        bin_path = shutil.which("higgsfield")
        if bin_path is None:
            raise HiggsfieldError(message="higgsfield CLI not on PATH", code="cli")
        argv = [bin_path, "--json", "upload", "create", file_path]
        try:
            stdout, stderr, code = await asyncio.wait_for(
                _run_cli(argv), timeout=120.0,
            )
        except asyncio.TimeoutError as e:
            raise HiggsfieldError(
                message="upload timed out after 120s", code="run",
            ) from e
        if code != 0:
            err = (stderr or stdout or "").strip()
            raise HiggsfieldError(
                message=_summarize_cli_error(err) or "upload failed",
                code=_classify_cli_error(err),
            )
        try:
            return json.loads(stdout.strip())
        except json.JSONDecodeError as e:
            raise HiggsfieldError(
                message=f"upload CLI returned non-JSON: {stdout[:120]!r}", code="shape",
            ) from e

    async def soul_create(
        self, *, name: str, upload_ids: list[str], model: str = "soul-2",
    ) -> dict[str, Any]:
        """Train a new Soul reference. Requires 5-20 upload IDs from
        ``upload_media``. `model` ∈ {'soul-2', 'soul-cinematic'} —
        Soul 2.0 is the general-purpose model; cinematic is tuned for
        film-quality output. Returns the envelope (contains soul_id).
        Training runs async upstream — call `soul_wait` to poll.
        """
        bin_path = shutil.which("higgsfield")
        if bin_path is None:
            raise HiggsfieldError(message="higgsfield CLI not on PATH", code="cli")
        if not (5 <= len(upload_ids) <= 20):
            raise HiggsfieldError(
                message=f"Soul training needs 5-20 reference images; got {len(upload_ids)}",
                code="cli",
            )
        if model not in ("soul-2", "soul-cinematic"):
            raise HiggsfieldError(
                message=f"Unknown Soul model {model!r}; expected 'soul-2' or 'soul-cinematic'",
                code="cli",
            )
        # The CLI uses `--soul-2` / `--soul-cinematic` as model
        # selectors (boolean flag), not `--model <name>`.
        model_flag = f"--{model}"
        argv = [bin_path, "--json", "soul-id", "create", "--name", name, model_flag]
        for uid in upload_ids:
            argv.extend(["--image", uid])
        try:
            stdout, stderr, code = await asyncio.wait_for(
                _run_cli(argv), timeout=60.0,
            )
        except asyncio.TimeoutError as e:
            raise HiggsfieldError(
                message="soul-id create timed out after 60s (the CLI submit, not training)", code="run",
            ) from e
        if code != 0:
            err = (stderr or stdout or "").strip()
            raise HiggsfieldError(
                message=_summarize_cli_error(err) or "soul-id create failed",
                code=_classify_cli_error(err),
            )
        try:
            return json.loads(stdout.strip())
        except json.JSONDecodeError as e:
            raise HiggsfieldError(
                message=f"soul-id create returned non-JSON: {stdout[:120]!r}", code="shape",
            ) from e

    async def soul_wait(self, *, soul_id: str, timeout_s: float = 600.0) -> dict[str, Any]:
        """Block until Soul training finishes. Higgsfield trains
        Soul-2 in 5-15min typically; cinematic can be longer. Returns
        the final envelope with status."""
        bin_path = shutil.which("higgsfield")
        if bin_path is None:
            raise HiggsfieldError(message="higgsfield CLI not on PATH", code="cli")
        argv = [bin_path, "--json", "soul-id", "wait", soul_id]
        try:
            stdout, stderr, code = await asyncio.wait_for(
                _run_cli(argv), timeout=timeout_s,
            )
        except asyncio.TimeoutError as e:
            raise HiggsfieldError(
                message=f"soul-id wait timed out after {timeout_s:.0f}s — training may still complete; check `higgsfield soul-id get {soul_id}`",
                code="run",
            ) from e
        if code != 0:
            err = (stderr or stdout or "").strip()
            raise HiggsfieldError(
                message=_summarize_cli_error(err) or "soul-id wait failed",
                code=_classify_cli_error(err),
            )
        try:
            return json.loads(stdout.strip())
        except json.JSONDecodeError as e:
            raise HiggsfieldError(
                message=f"soul-id wait returned non-JSON: {stdout[:120]!r}", code="shape",
            ) from e

    async def marketing_hooks_list(self) -> list[dict[str, Any]]:
        """List Higgsfield Marketing Studio hooks — pre-engineered ad
        concepts (Product Hit, Spicy, etc.) with prompts + preview
        thumbnails + sample videos. Each operator gets the same preset
        catalogue from upstream (account-level customization is
        possible but out of scope for V1)."""
        bin_path = shutil.which("higgsfield")
        if bin_path is None:
            raise HiggsfieldError(message="higgsfield CLI not on PATH", code="cli")
        argv = [bin_path, "--json", "marketing-studio", "hooks", "list"]
        stdout, stderr, code = await asyncio.wait_for(
            _run_cli(argv), timeout=30.0,
        )
        if code != 0:
            err = (stderr or stdout or "").strip()
            raise HiggsfieldError(
                message=_summarize_cli_error(err) or "marketing-studio hooks list failed",
                code=_classify_cli_error(err),
            )
        try:
            parsed = json.loads(stdout.strip()) if stdout.strip() else {}
        except json.JSONDecodeError as e:
            raise HiggsfieldError(
                message=f"hooks list returned non-JSON: {stdout[:120]!r}", code="shape",
            ) from e
        # Envelope is {cursor, has_more, items: [...]}; extract items.
        if isinstance(parsed, dict) and "items" in parsed:
            return parsed["items"] if isinstance(parsed["items"], list) else []
        # Some CLI versions might return a flat list directly.
        if isinstance(parsed, list):
            return parsed
        return []

    async def soul_list(self, *, size: int = 100) -> list[dict[str, Any]]:
        """List trained Soul references (machine-wide; Soul training
        is account-level on the higgsfield side, machine-mapped via
        the CLI's machine-wide auth)."""
        bin_path = shutil.which("higgsfield")
        if bin_path is None:
            raise HiggsfieldError(message="higgsfield CLI not on PATH", code="cli")
        argv = [bin_path, "--json", "soul-id", "list", "--size", str(size)]
        stdout, stderr, code = await asyncio.wait_for(
            _run_cli(argv), timeout=30.0,
        )
        if code != 0:
            err = (stderr or stdout or "").strip()
            raise HiggsfieldError(
                message=_summarize_cli_error(err) or "soul-id list failed",
                code=_classify_cli_error(err),
            )
        try:
            parsed = json.loads(stdout.strip()) if stdout.strip() else []
        except json.JSONDecodeError as e:
            raise HiggsfieldError(
                message=f"soul-id list returned non-JSON: {stdout[:120]!r}", code="shape",
            ) from e
        if isinstance(parsed, list):
            return parsed
        return [parsed] if isinstance(parsed, dict) else []

    async def model_list(self, *, kind: str = "video") -> list[dict[str, Any]]:
        """List models via `higgsfield --json model list --image|--video`.

        Returns the raw item list: `[{display_name, job_set_type,
        type}, ...]` (verified against CLI June 2026). Used by the
        server-side model catalog to mark curated entries available —
        NOT as the catalog itself (the list carries no param
        contracts, costs, or tiers)."""
        if kind not in ("image", "video"):
            raise HiggsfieldError(
                message=f"model_list kind must be 'image' or 'video', got {kind!r}",
                code="cli",
            )
        bin_path = shutil.which("higgsfield")
        if bin_path is None:
            raise HiggsfieldError(message="higgsfield CLI not on PATH", code="cli")
        argv = [bin_path, "--json", "model", "list", f"--{kind}"]
        try:
            stdout, stderr, code = await asyncio.wait_for(
                _run_cli(argv), timeout=30.0,
            )
        except asyncio.TimeoutError as e:
            raise HiggsfieldError(
                message="model list timed out after 30s", code="run",
            ) from e
        if code != 0:
            err = (stderr or stdout or "").strip()
            raise HiggsfieldError(
                message=_summarize_cli_error(err) or "model list failed",
                code=_classify_cli_error(err),
            )
        try:
            parsed = json.loads(stdout.strip()) if stdout.strip() else []
        except json.JSONDecodeError as e:
            raise HiggsfieldError(
                message=f"model list returned non-JSON: {stdout[:120]!r}", code="shape",
            ) from e
        if isinstance(parsed, dict) and "items" in parsed:
            parsed = parsed["items"]
        return parsed if isinstance(parsed, list) else []

    async def get_balance(self) -> dict[str, Any]:
        """Read the operator's current Higgsfield credit balance via
        `higgsfield account status --json`. The CLI subcommand is
        `status` (not `balance` — that was my early misread of the
        help text and explained the persistent "—" in the header
        pill). Returns `{email, credits, subscription_plan_type}`."""
        bin_path = shutil.which("higgsfield")
        if bin_path is None:
            raise HiggsfieldError(
                message="higgsfield CLI not on PATH", code="cli",
            )
        argv = [bin_path, "--json", "account", "status"]
        try:
            stdout, stderr, code = await asyncio.wait_for(
                _run_cli(argv), timeout=15.0,
            )
        except asyncio.TimeoutError as e:
            raise HiggsfieldError(
                message="balance lookup timed out after 15s", code="run",
            ) from e
        if code != 0:
            err = (stderr or stdout or "").strip()
            raise HiggsfieldError(
                message=_summarize_cli_error(err) or "balance lookup failed",
                code=_classify_cli_error(err),
            )
        try:
            return json.loads(stdout.strip())
        except json.JSONDecodeError as e:
            raise HiggsfieldError(
                message=f"balance CLI returned non-JSON: {stdout[:120]!r}", code="shape",
            ) from e


# ── CLI plumbing (module-level so tests can monkeypatch _run_cli) ─────


def _build_cli_argv(
    *, model: str, prompt: str, timeout_s: float = _DEFAULT_TIMEOUT_S, **params: Any,
) -> list[str]:
    """Assemble argv for the official `@higgsfield/cli` (npm package).

    Shape: ``higgsfield --json generate create <model> --prompt "..."
    --wait --wait-timeout <Xs>``. `--json` is a GLOBAL flag (before the
    subcommand). `--wait` blocks until the job completes so we don't
    poll history ourselves. `--wait-timeout` defaults to 30s in the
    CLI; we pass our own ceiling matched to the subprocess timeout
    (minus 5s of slack so the CLI fails first with a structured
    timeout, not Python's KILL).
    """
    bin_path = shutil.which("higgsfield")
    if bin_path is None:
        raise HiggsfieldError(
            message=(
                "higgsfield CLI not on PATH. Install via "
                "`npm install -g @higgsfield/cli` (the official npm package, "
                "not the PyPI one), then run `higgsfield login` once."
            ),
            code="cli",
        )
    argv: list[str] = [
        bin_path, "--json", "generate", "create", model,
        "--prompt", prompt,
        "--wait",
        "--wait-timeout", f"{int(timeout_s - 5)}s",
    ]
    # Higgsfield CLI accepts arbitrary `--<param-name> <value>` for any
    # model param (per `higgsfield generate create --help`). Pass
    # everything through so we don't silently drop model-specific
    # params like `duration` / `mode` / `model` (Veo's fast vs preview
    # sub-variant) / `quality` / `sound`. Earlier hardcoded allow-list
    # caused the "20s video came out 5s" bug — `duration` wasn't in it
    # so Kling fell back to its default 5s.
    #
    # `soul_id` → `--soul-id` is the only key we rename (`_` to `-`)
    # because that's how Higgsfield's CLI flag is spelled. Everything
    # else passes through with its key unchanged.
    for key, value in params.items():
        if value is None or value == "":
            continue
        if key == "soul_id":
            argv.extend(["--soul-id", str(value)])
        else:
            argv.extend([f"--{key}", str(value)])
    return argv


async def _run_cli(
    argv: list[str], *, env_overlay: dict[str, str] | None = None,
) -> tuple[str, str, int]:
    """Spawn the CLI and drain stdout/stderr. Module-level so tests
    can monkeypatch this to fake CLI output without exec'ing anything.
    Inherits the parent process environment so `$HOME` (which the CLI
    uses to find `~/.higgsfield/`) flows through naturally."""
    env = dict(os.environ)
    if env_overlay:
        env.update(env_overlay)
    proc = await asyncio.create_subprocess_exec(
        *argv,
        stdin=asyncio.subprocess.DEVNULL,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=env,
    )
    out_b, err_b = await proc.communicate()
    return (
        out_b.decode("utf-8", errors="replace"),
        err_b.decode("utf-8", errors="replace"),
        int(proc.returncode or 0),
    )


# Recovery: when the polling endpoint drops mid-stream the CLI prints
# `Cannot reach https://fnf.higgsfield.ai/agents/jobs/<uuid>` and exits
# non-zero — but the job ITSELF was successfully submitted. We extract
# the UUID and retry just the wait.
_UNREACHABLE_RE = re.compile(
    r"Cannot reach https?://[^/\s]+/agents/jobs/([0-9a-f-]{36})",
    re.IGNORECASE,
)

_UPSTREAM_5XX_RE = re.compile(
    r"HTTP\s*(502|503|504)|error code:\s*(502|503|504)\b",
    re.IGNORECASE,
)


def _is_upstream_5xx(stderr: str) -> bool:
    """True when CLI stderr indicates a transient Higgsfield 5xx — used
    to gate the one-shot whole-submit retry. Distinct from the polling-
    endpoint 'Cannot reach' path which only retries the wait."""
    return bool(_UPSTREAM_5XX_RE.search(stderr or ""))


def _extract_job_id_from_unreachable(stderr: str) -> str | None:
    """Pull the job UUID from a `Cannot reach …/agents/jobs/<uuid>`
    error. Returns None when the stderr doesn't match."""
    m = _UNREACHABLE_RE.search(stderr or "")
    return m.group(1) if m else None


def _build_wait_argv(job_id: str) -> list[str]:
    """Argv for the resume-poll path: `higgsfield --json generate wait
    <job_id>`."""
    bin_path = shutil.which("higgsfield")
    if bin_path is None:  # pragma: no cover — already raised in submit_image's first call
        raise HiggsfieldError(message="higgsfield CLI not on PATH", code="cli")
    return [bin_path, "--json", "generate", "wait", job_id]


def _parse_envelope(stdout: str) -> list[dict[str, Any]]:
    """Parse the CLI's JSON output. Shape (verified against
    `@higgsfield/cli` 0.1.40+): plain array of job objects, no wrapping
    envelope. Defensive against stray prefix lines via `raw_decode`."""
    s = stdout.strip()
    if not s:
        raise HiggsfieldError(message="CLI emitted empty stdout", code="shape")
    try:
        parsed = json.loads(s)
    except json.JSONDecodeError:
        decoder = json.JSONDecoder()
        parsed = None
        for opener in ("[", "{"):
            idx = s.find(opener)
            while idx >= 0:
                try:
                    obj, _end = decoder.raw_decode(s, idx)
                    parsed = obj
                    break
                except json.JSONDecodeError:
                    idx = s.find(opener, idx + 1)
            if parsed is not None:
                break
        if parsed is None:
            raise HiggsfieldError(
                message=f"CLI stdout not JSON ({s[:120]!r})", code="shape",
            )
    if isinstance(parsed, list):
        return parsed
    if isinstance(parsed, dict):
        return [parsed]
    raise HiggsfieldError(
        message=f"CLI JSON is not array or object: {type(parsed).__name__}", code="shape",
    )


def _first_raw_url(jobs: list[dict[str, Any]]) -> str | None:
    """Pull the first completed job's result URL. Raises HiggsfieldError
    for terminal-failure states (nsfw / failed / cancelled) so callers
    don't treat them as "pending — try again"."""
    if not jobs:
        return None
    # Single error object wrapped to a list by _parse_envelope.
    if len(jobs) == 1 and "error" in jobs[0] and "id" not in jobs[0]:
        err = jobs[0]
        raise HiggsfieldError(
            message=str(err.get("message") or err.get("error") or "cli reported failure"),
            code=str(err.get("code") or "run"),
        )
    # First pass: any successful job → its URL.
    for job in jobs:
        if not isinstance(job, dict):
            continue
        st = str(job.get("status") or "").lower()
        if st in ("completed", "complete", "success", "done"):
            url = _extract_job_url(job)
            if url:
                return url
    # Second pass: detect terminal-failure statuses.
    terminal = [
        str(j.get("status") or "").lower()
        for j in jobs if isinstance(j, dict)
    ]
    if any(s == "nsfw" for s in terminal):
        raise HiggsfieldError(
            code="nsfw",
            message=(
                "Higgsfield's content filter flagged this generation as NSFW. "
                "Rephrase your prompt — common false positives: anything "
                "mentioning children, anatomy, or specific people. Try removing "
                "those references or describing the scene more abstractly."
            ),
        )
    if any(s == "failed" or s == "error" for s in terminal):
        raise HiggsfieldError(
            code="run",
            message=(
                "Higgsfield job failed upstream. Common causes: model-specific "
                "param missing (e.g. soul_v2 requires --soul-id), or Higgsfield "
                "infra error. Check `higgsfield generate get <job_id>` for detail."
            ),
        )
    if any(s == "cancelled" or s == "canceled" for s in terminal):
        raise HiggsfieldError(
            code="run",
            message="Higgsfield job was cancelled (timeout, quota, or operator action).",
        )
    # Third pass: any URL at all (some intermediate shapes don't carry
    # an explicit `status` field).
    for job in jobs:
        if isinstance(job, dict):
            url = _extract_job_url(job)
            if url:
                return url
    return None


def _extract_job_url(job: dict[str, Any]) -> str | None:
    """Pull the result URL. Official CLI puts it at `result_url`;
    older shape used `results.raw_url`. Accept both."""
    for k in ("result_url", "url", "image_url"):
        v = job.get(k)
        if isinstance(v, str) and v:
            return v
    results = job.get("results")
    if isinstance(results, dict):
        url = results.get("raw_url") or results.get("url")
        if isinstance(url, str) and url:
            return url
    if isinstance(results, list):
        for r in results:
            if isinstance(r, dict):
                url = r.get("raw_url") or r.get("url")
                if isinstance(url, str) and url:
                    return url
    return None


def _summarize_cli_error(stderr: str) -> str:
    """Pick the operator-useful slice of a CLI failure. Python tracebacks
    put the exception on the LAST line; a naïve `[:400]` keeps the
    click call-stack head and loses the cause."""
    s = stderr.strip()
    if not s:
        return ""
    if "Traceback (most recent call last)" in s:
        lines = [ln for ln in s.splitlines() if ln.strip()]
        head = "Traceback (most recent call last):"
        tail = lines[-6:]
        return head + "\n  …\n" + "\n".join(tail)
    return s if len(s) <= 600 else s[:600] + "…"


def _classify_cli_error(stderr: str) -> str:
    """Map CLI stderr into the structured `code` the router converts to
    HTTP. Auth failures → `auth`; CLI usage errors → `cli`; anything
    else → `run`."""
    low = stderr.lower()
    if any(t in low for t in (
        "not logged in", "login required", "401", "403", "expired",
        "datadome", "unauthorized", "no session",
        # `~/.higgsfield/` missing → httpx tries to encode empty/garbage
        # cookies and explodes in set_cookie_header. Root cause is "no
        # auth state"; classify as auth so operator gets the right
        # next step (`higgsfield login`).
        "unicodeencodeerror", "ascii codec can't encode",
        "set_cookie_header",
    )):
        return "auth"
    if any(t in low for t in (
        "usage:", "no such option", "invalid value for", "got unexpected",
    )):
        return "cli"
    return "run"


# ── Startup-time PATH check (called from app/main.py lifespan) ────────


def log_cli_presence_at_startup() -> None:
    """Emit a single log line indicating whether the higgsfield CLI is
    discoverable on PATH. Called from app/main.py's lifespan so a missing
    npm-global-bin in the FastAPI process PATH fails at boot rather than
    on first /api/studio/generate-image request — the original Plan
    agent flagged this is the most common deployment gotcha."""
    bin_path = shutil.which("higgsfield")
    if bin_path:
        logger.info("higgsfield CLI ready at %s", bin_path)
    else:
        logger.warning(
            "higgsfield CLI NOT on PATH. Studio's higgsfield models will "
            "fail with code=cli at first call. Install: "
            "`npm install -g @higgsfield/cli` then `higgsfield login`."
        )
