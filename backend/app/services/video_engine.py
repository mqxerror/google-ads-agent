"""Video Engine — segment-timeline dispatcher v1 (Epic 11 P2).

One request shape for hybrid videos: an ordered list of SEGMENTS
(intro / body / outro), each tagged with an engine:

    engine="storyboard"  → hyperframes scenes, verbatim (free, local)
    engine="higgsfield"  → one generated clip (P1 machinery, cached)
    engine="soul"        → one Soul-presenter clip (NEW this phase)

Dispatcher v1 COMPILES the timeline into a single flat storyboard and
delegates rendering to premium_reel.generate_storyboard_reel — on
purpose. The P1 splice path already owns per-scene TTS (the VO bed),
mezzanine normalization, the xfade stitch, and the music duck rules;
rendering segments separately and re-stitching would duplicate that
ffmpeg logic and reopen the audio-continuity risk the plan flags
(per-clip native audio fighting the VO bed — normalize_clip strips
clip audio with -an, and the bed is rebuilt from `_speak_text`). The
segment timeline stays the REQUEST contract (P3's drag-to-reorder
editor builds on it); execution reuses the one proven pipeline.

§1a RESOLUTION (2026-07-04): no talking/lipsync model could be
verified. The read-only `higgsfield model list --video` requires an
authenticated session and the CLI session was expired at build time
("Session expired / hf auth login"); the local CLI 0.1.40 help has no
speak/lipsync surface; the curated model catalog (live-verified
2026-06-11) lists no talking-head model either. Per the plan's stated
fallback the soul engine renders a NON-LIPSYNC PRESENTER:

    1. still  — SOUL_STILL_MODEL (text2image_soul_v2) + --soul-id
    2. motion — SOUL_MOTION_MODEL (veo3, the catalog's only explicit
                image-to-video model) animates the still
    3. voice  — the segment's script goes through the existing
                per-scene TTS bed; clip-native audio is stripped by
                normalize_clip (-an)

The presenter moves and the VO plays over the clip; lips do NOT sync.
UI copy must not promise lip-sync. When a verified talking-head model
lands in the CLI, swap the SOUL_MOTION_* constants below.

Cost guardrails: MAX_SOUL_SEGMENTS (1) per render on top of P1's
MAX_HIGGSFIELD_SCENES (8); soul clips cache by prompt-hash in
ad_assets exactly like higgsfield scenes (re-renders free); and
estimate_timeline_credits() sums live per-clip estimates for the
pre-render confirmation the routers surface.

DECOUPLING: studio service layer — no google_ads imports.
"""

from __future__ import annotations

import hashlib
import logging
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, AsyncIterator, Awaitable, Callable, Optional

from app.services.higgsfield_client import HiggsfieldClient, HiggsfieldError

logger = logging.getLogger(__name__)

# Hard cap on Soul presenter clips per render — sister guard to
# higgsfield_scene.MAX_HIGGSFIELD_SCENES (8). A soul clip is TWO paid
# generations (still + motion), so one per video is the v1 budget.
MAX_SOUL_SEGMENTS = 1

# §1a fallback models (see module docstring). Both ids come from the
# curated catalog in model_catalog.py — NOT invented. veo3 is the
# catalog's only entry marked requires_input_image (the verified
# image-to-video model); it takes no --duration, so the clip renders at
# the model's native length and normalize_clip freeze-pads to the VO.
SOUL_STILL_MODEL = "text2image_soul_v2"
SOUL_MOTION_MODEL = "veo3"
# CLI 0.1.40 `generate create --help`: media flags are --image /
# --start-image / … and "accept a UUID or a local file path — paths
# are auto-uploaded". If the live smoke test shows veo3 wanting its
# contract name instead (`input_image` per the May-2026 reference),
# flip this one constant.
SOUL_MOTION_IMAGE_PARAM = "image"

DEFAULT_SOUL_LOOK_PROMPT = (
    "Professional presenter facing the camera, chest-up framing, warm "
    "confident expression, softly lit modern office background, shallow "
    "depth of field, photorealistic"
)
# Fixed motion pass — gentle presenter movement, no cuts. Kept constant
# so the prompt-hash cache stays stable across re-renders.
SOUL_MOTION_PROMPT = (
    "The presenter speaks naturally to the camera with subtle head "
    "movement and small hand gestures, steady framing, no camera cuts"
)


@dataclass
class VideoEngineRequest:
    """Segment timeline in, one MP4 out. `segments` is an ordered list
    of dicts discriminated on `engine` (see module docstring)."""

    account_id: Optional[str]
    segments: list[dict] = field(default_factory=list)
    voice_id: Optional[str] = None
    music_path: Optional[Path] = None   # resolved to disk by the router
    quality: str = "draft"
    aspect: str = "16:9"                # mezzanine target is 1920x1080
    campaign_id: Optional[str] = None
    sync_audio_to_scenes: bool = True
    # These three drive "finished video" mode: when set (and `segments`
    # is empty) the dispatcher auto-plans N higgsfield clips sized to
    # target_seconds instead of using hand-authored segments.
    target_seconds: Optional[int] = None
    model_id: Optional[str] = None
    prompt: Optional[str] = None
    # Finished-video voiceover: one script spanning the whole timeline
    # (sized to the target by premium_reel's voiceover_script path). When
    # set in planner mode we turn OFF per-scene sync so this single track
    # plays over the stitched clips instead of silent per-scene TTS.
    voiceover_script: Optional[str] = None


# ── Timeline compile ──────────────────────────────────────────────


def segments_to_scenes(segments: list[dict]) -> tuple[list[dict], list[str]]:
    """Compile ordered segments into the flat scene list the storyboard
    renderer accepts. Returns (scenes, warnings). Unknown engines are
    skipped with a warning rather than failing the whole render."""
    scenes: list[dict] = []
    warnings: list[str] = []
    for i, seg in enumerate(segments):
        if not isinstance(seg, dict):
            warnings.append(f"Segment {i+1} ignored — not an object.")
            continue
        engine = (seg.get("engine") or "").strip().lower()
        if engine == "storyboard":
            seg_scenes = seg.get("scenes")
            if isinstance(seg_scenes, list) and seg_scenes:
                scenes.extend(s for s in seg_scenes if isinstance(s, dict))
            else:
                warnings.append(f"Segment {i+1} (storyboard) ignored — no scenes.")
        elif engine == "higgsfield":
            prompt = (seg.get("prompt") or "").strip()
            if not prompt:
                warnings.append(f"Segment {i+1} (AI clip) ignored — no prompt.")
                continue
            scene: dict[str, Any] = {"type": "higgsfield", "prompt": prompt}
            if seg.get("model"):
                scene["model"] = str(seg["model"]).strip()
            if seg.get("duration") is not None:
                scene["duration"] = seg["duration"]
            scene["_speak_text"] = (seg.get("speak") or "").strip()
            scenes.append(scene)
        elif engine == "soul":
            script = (seg.get("script") or seg.get("speak") or "").strip()
            if not script:
                warnings.append(f"Segment {i+1} (Soul presenter) ignored — no script.")
                continue
            scene = {"type": "soul", "script": script, "_speak_text": script}
            if seg.get("soul_id"):
                scene["soul_id"] = str(seg["soul_id"]).strip()
            if seg.get("soul_character_id"):
                scene["soul_character_id"] = str(seg["soul_character_id"]).strip()
            if seg.get("look_prompt"):
                scene["look_prompt"] = str(seg["look_prompt"]).strip()
            scenes.append(scene)
        else:
            warnings.append(f"Segment {i+1} ignored — unknown engine {engine!r}.")
    return scenes, warnings


def enforce_caps(scenes: list[dict]) -> tuple[list[dict], list[str]]:
    """Credit-burn guard on the FLAT scene list (covers inline soul /
    higgsfield scenes inside storyboard segments too). First-N win so
    an intro soul survives a hand-edited duplicate. premium_reel
    re-checks both caps at render time — defense in depth."""
    from app.services.higgsfield_scene import MAX_HIGGSFIELD_SCENES

    out: list[dict] = []
    warnings: list[str] = []
    n_soul = 0
    n_hf = 0
    for s in scenes:
        t = (s.get("type") or "").strip().lower()
        if t == "soul":
            if n_soul >= MAX_SOUL_SEGMENTS:
                warnings.append(
                    f"Dropped an extra Soul presenter scene — max {MAX_SOUL_SEGMENTS} per render (credit guard)."
                )
                continue
            n_soul += 1
        elif t == "higgsfield":
            if n_hf >= MAX_HIGGSFIELD_SCENES:
                warnings.append(
                    f"Dropped an extra AI clip scene — max {MAX_HIGGSFIELD_SCENES} per render (credit guard)."
                )
                continue
            n_hf += 1
        out.append(s)
    return out, warnings


async def _fetch_soul_row(soul_character_id: str) -> Optional[dict[str, Any]]:
    """soul_characters row by OUR id (not higgsfield's soul_id)."""
    from app.database import get_db

    db = await get_db()
    try:
        cur = await db.execute(
            "SELECT id, name, soul_id, status FROM soul_characters WHERE id = ?",
            (soul_character_id,),
        )
        row = await cur.fetchone()
        return dict(row) if row else None
    finally:
        await db.close()


async def attach_soul_ids(
    scenes: list[dict],
    *,
    fetch: Optional[Callable[[str], Awaitable[Optional[dict[str, Any]]]]] = None,
) -> tuple[list[dict], list[str]]:
    """Resolve soul scenes to a READY higgsfield soul_id. Scenes already
    carrying `soul_id` pass through; scenes with only our row id
    (`soul_character_id`) are looked up; anything unresolvable is
    dropped with a warning — the plan's "no ready character" graceful
    degrade. `fetch` is injectable for tests."""
    fetch = fetch or _fetch_soul_row
    out: list[dict] = []
    warnings: list[str] = []
    for s in scenes:
        if (s.get("type") or "").strip().lower() != "soul":
            out.append(s)
            continue
        if (s.get("soul_id") or "").strip():
            out.append(s)
            continue
        row_id = (s.get("soul_character_id") or "").strip()
        row = await fetch(row_id) if row_id else None
        if row and row.get("status") == "ready" and (row.get("soul_id") or "").strip():
            resolved = dict(s)
            resolved["soul_id"] = str(row["soul_id"]).strip()
            out.append(resolved)
        else:
            state = (row or {}).get("status") or "not found"
            warnings.append(
                f"Dropped the Soul presenter scene — character is {state}, not ready."
            )
    return out, warnings


# ── Soul presenter clip (§1a fallback — NON-LIPSYNC) ──────────────


def soul_prompt_hash(*, soul_id: str, look_prompt: str, aspect: str) -> str:
    """Deterministic cache key for one presenter clip. Includes both
    stage models so swapping SOUL_MOTION_MODEL later invalidates
    naturally instead of serving stale-look clips."""
    key = (
        f"soul|{SOUL_STILL_MODEL}|{SOUL_MOTION_MODEL}|{look_prompt.strip()}"
        f"|{soul_id}|{aspect}"
    )
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


async def _download_file(url: str, suffix: str) -> Path:
    """Download a CDN URL into ASSETS_DIR (CDN URLs expire in 24-48h,
    so we always localize — same rule as higgsfield_scene)."""
    import httpx

    from app.routers.assets import ASSETS_DIR

    dest = ASSETS_DIR / f"{uuid.uuid4()}{suffix}"
    async with httpx.AsyncClient(timeout=120.0, follow_redirects=True) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        dest.write_bytes(resp.content)
    return dest


async def _record_soul_asset(
    *,
    path: Path,
    look_prompt: str,
    soul_id: str,
    aspect: str,
    prompt_hash: str,
    hf_job_id: Optional[str],
    cdn_url: str,
    account_id: Optional[str],
    campaign_id: Optional[str],
) -> None:
    """ad_assets row for the presenter clip — library visibility AND
    the prompt-hash that makes the next render of this timeline free.
    Recording failures never fail the render (clip file is fine)."""
    from app.database import get_db

    db = await get_db()
    try:
        await db.execute(
            """INSERT INTO ad_assets
               (id, account_id, campaign_id, type, filename, url, source,
                status, higgsfield_model, prompt, aspect_ratio, soul_id,
                higgsfield_cdn_url, higgsfield_job_id, prompt_hash,
                size_bytes, created_at)
               VALUES (?, ?, ?, 'video', ?, ?, 'higgsfield', 'completed',
                       ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))""",
            (
                path.stem, account_id, campaign_id, path.name,
                f"/api/assets/file/{path.name}",
                f"{SOUL_STILL_MODEL}+{SOUL_MOTION_MODEL}",
                look_prompt, aspect, soul_id, cdn_url, hf_job_id,
                prompt_hash, path.stat().st_size,
            ),
        )
        await db.commit()
    except Exception:
        logger.exception("failed to record soul presenter clip in ad_assets")
    finally:
        await db.close()


def _first_job_id(result: dict[str, Any]) -> Optional[str]:
    raw = result.get("raw") or []
    if isinstance(raw, list) and raw and isinstance(raw[0], dict):
        return str(raw[0].get("id") or "") or None
    return None


async def resolve_soul_clip(
    scene: dict[str, Any],
    *,
    aspect: str = "16:9",
    account_id: Optional[str] = None,
    campaign_id: Optional[str] = None,
) -> tuple[Path, bool]:
    """Local mp4 for a soul scene. Returns (path, was_cached).

    NON-LIPSYNC presenter (§1a fallback, see module docstring):
    Soul still (SOUL_STILL_MODEL + soul_id) → image-to-video motion
    pass (SOUL_MOTION_MODEL) → caller muxes the script's TTS over the
    clip via the storyboard VO bed. Cache hit = zero credits.
    """
    soul_id = (scene.get("soul_id") or "").strip()
    if not soul_id:
        raise ValueError("soul scene has no soul_id")
    look_prompt = (scene.get("look_prompt") or "").strip() or DEFAULT_SOUL_LOOK_PROMPT

    p_hash = soul_prompt_hash(soul_id=soul_id, look_prompt=look_prompt, aspect=aspect)
    from app.services.higgsfield_scene import _find_cached_clip

    cached = await _find_cached_clip(p_hash)
    if cached is not None:
        logger.info("soul presenter cache HIT (%s) — no credits burned", p_hash[:12])
        return cached, True

    # ── Stage 1: Soul still (face-consistent) ─────────────────────
    client = HiggsfieldClient(timeout_s=600.0)
    still = await client.submit_image(
        model=SOUL_STILL_MODEL, prompt=look_prompt,
        aspect_ratio=aspect, soul_id=soul_id,
    )
    still_url = still.get("image_url")
    if not still_url:
        raise RuntimeError("soul still pass returned no image URL")
    still_path = await _download_file(still_url, ".png")

    # ── Stage 2: motion pass (image-to-video; CLI auto-uploads the
    # local path — see SOUL_MOTION_IMAGE_PARAM note above) ─────────
    result = await client.submit_video(
        model=SOUL_MOTION_MODEL, prompt=SOUL_MOTION_PROMPT,
        **{"aspect_ratio": aspect, SOUL_MOTION_IMAGE_PARAM: str(still_path)},
    )
    cdn_url = result.get("image_url")  # client uses one key for both media types
    if not cdn_url:
        raise RuntimeError("soul motion pass returned no clip URL")
    path = await _download_file(cdn_url, ".mp4")

    await _record_soul_asset(
        path=path, look_prompt=look_prompt, soul_id=soul_id, aspect=aspect,
        prompt_hash=p_hash, hf_job_id=_first_job_id(result), cdn_url=cdn_url,
        account_id=account_id, campaign_id=campaign_id,
    )
    logger.info(
        "soul presenter generated (soul=%s hash=%s) — non-lipsync fallback",
        soul_id[:8], p_hash[:12],
    )
    return path, False


# ── Pre-render credit estimate (cost guardrail) ───────────────────


async def estimate_timeline_credits(
    scenes: list[dict], *, aspect: str = "16:9",
) -> dict[str, Any]:
    """Summed live credit estimate for every scene that would touch
    Higgsfield — surfaced BEFORE the operator clicks render. Cached
    clips count as 0 (prompt-hash reuse). Per-item failures are
    null-tolerant (mirrors /api/studio/cost-estimate's soft-error
    shape): `total_credits` sums what the CLI could price and
    `unknown_count` says how many lookups it couldn't."""
    from app.services.higgsfield_scene import (
        DEFAULT_SCENE_MODEL,
        _find_cached_clip,
        scene_prompt_hash,
    )
    from app.services.model_catalog import clamp_duration

    items: list[dict[str, Any]] = []
    total = 0
    unknown = 0
    cached_hits = 0
    client = HiggsfieldClient(timeout_s=30.0)

    async def _try_estimate(kind: str, model: str, prompt: str, **params: Any) -> None:
        nonlocal total, unknown
        try:
            env = await client.estimate_cost(model=model, prompt=prompt, **params)
            credits = int(env.get("credits", 0))
            total += credits
            items.append({"kind": kind, "model": model, "credits": credits, "cached": False})
        except HiggsfieldError as e:
            unknown += 1
            items.append({
                "kind": kind, "model": model, "credits": None, "cached": False,
                "note": e.message[:200],
            })
        except Exception as e:  # estimates must never break the render flow
            unknown += 1
            items.append({
                "kind": kind, "model": model, "credits": None, "cached": False,
                "note": str(e)[:200],
            })

    for s in scenes:
        if not isinstance(s, dict):
            continue
        t = (s.get("type") or "").strip().lower()
        if t == "higgsfield":
            prompt = (s.get("prompt") or "").strip()
            if not prompt:
                continue
            model = (s.get("model") or DEFAULT_SCENE_MODEL).strip()
            try:
                requested = int(s.get("duration")) if s.get("duration") is not None else None
            except (TypeError, ValueError):
                requested = None
            duration = clamp_duration(model, requested)
            p_hash = scene_prompt_hash(model=model, prompt=prompt, duration=duration, aspect=aspect)
            if await _find_cached_clip(p_hash) is not None:
                cached_hits += 1
                items.append({"kind": "AI clip", "model": model, "credits": 0, "cached": True})
                continue
            params: dict[str, Any] = {"aspect_ratio": aspect}
            if duration is not None:
                params["duration"] = duration
            await _try_estimate("AI clip", model, prompt, **params)
        elif t == "soul":
            soul_id = (s.get("soul_id") or "").strip()
            look_prompt = (s.get("look_prompt") or "").strip() or DEFAULT_SOUL_LOOK_PROMPT
            if soul_id:
                p_hash = soul_prompt_hash(soul_id=soul_id, look_prompt=look_prompt, aspect=aspect)
                if await _find_cached_clip(p_hash) is not None:
                    cached_hits += 1
                    items.append({
                        "kind": "Soul presenter", "model": f"{SOUL_STILL_MODEL}+{SOUL_MOTION_MODEL}",
                        "credits": 0, "cached": True,
                    })
                    continue
            # Two paid stages. The motion estimate may come back null
            # when the CLI insists on a real input image — honest
            # unknown rather than an invented number.
            await _try_estimate(
                "Soul presenter (still)", SOUL_STILL_MODEL, look_prompt,
                aspect_ratio=aspect, **({"soul_id": soul_id} if soul_id else {}),
            )
            await _try_estimate(
                "Soul presenter (motion)", SOUL_MOTION_MODEL, SOUL_MOTION_PROMPT,
                aspect_ratio=aspect,
            )
    return {
        "total_credits": total,
        "unknown_count": unknown,
        "cached_hits": cached_hits,
        "items": items,
    }


# ── Dispatcher ────────────────────────────────────────────────────


async def generate_engine_video(req: VideoEngineRequest) -> AsyncIterator[dict]:
    """Compile the segment timeline → flat storyboard → render through
    the existing premium_reel pipeline. Same SSE event shape as
    generate_storyboard_reel (status / error / done pass through)."""
    # Finished-video mode: no hand-authored segments, but the trio is
    # set — auto-plan N higgsfield clips sized to target_seconds. When
    # segments ARE provided this branch is skipped and behavior is
    # byte-for-byte as before. plan_scenes returns [] for unknown /
    # non-video models, so `segments` stays [] and the existing "no
    # renderable scenes" error path fires — the correct graceful failure.
    segments = req.segments
    planner_mode = bool(req.target_seconds and req.model_id and req.prompt and not segments)
    if planner_mode:
        from app.services.model_catalog import plan_scenes
        planned = plan_scenes(int(req.target_seconds), req.model_id)
        segments = []
        for p in planned:
            seg = {"engine": "higgsfield", "prompt": req.prompt, "model": req.model_id, "speak": ""}
            if p.get("duration") is not None:
                seg["duration"] = p["duration"]
            segments.append(seg)

    # Finished-video voiceover: a single script spanning the whole
    # timeline. In planner mode the clips carry no per-scene lines
    # (speak=""), so per-scene sync would render silent — switch to the
    # whole-script VO bed (premium_reel's voiceover_script path sizes one
    # track to the full stitched duration).
    whole_script_vo = (req.voiceover_script or "").strip() if planner_mode else ""
    sync_audio = req.sync_audio_to_scenes and not whole_script_vo

    scenes, warnings = segments_to_scenes(segments)
    scenes, cap_warnings = enforce_caps(scenes)
    scenes, soul_warnings = await attach_soul_ids(scenes)
    for w in (*warnings, *cap_warnings, *soul_warnings):
        yield {"type": "status", "stage": "timeline", "message": w}
    if not scenes:
        yield {
            "type": "error", "stage": "timeline",
            "message": "no renderable scenes after compiling the segment timeline",
        }
        return

    n_soul = sum(1 for s in scenes if (s.get("type") or "").lower() == "soul")
    n_hf = sum(1 for s in scenes if (s.get("type") or "").lower() == "higgsfield")
    yield {
        "type": "status", "stage": "timeline",
        "message": (
            f"Timeline compiled — {len(scenes)} scenes"
            f" ({n_soul} Soul presenter, {n_hf} AI clip{'s' if n_hf != 1 else ''})."
        ),
    }

    from app.services.premium_reel import StoryboardReelRequest, generate_storyboard_reel

    reel_req = StoryboardReelRequest(
        scenes=scenes,
        voiceover_script=whole_script_vo,
        voice_id=req.voice_id,
        music_path=req.music_path,
        quality=req.quality,
        parallel_workers=2,
        sync_audio_to_scenes=sync_audio,
        account_id=req.account_id,
        campaign_id=req.campaign_id,
        aspect=req.aspect,
    )
    async for event in generate_storyboard_reel(reel_req):
        yield event
