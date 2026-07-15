"""Fail-CLOSED dry-run engine for the Google Ads SDK.

CONTRACT
========
While the `force_validate_only()` context manager is active, EVERY Google Ads
mutate request that leaves this process is GUARANTEED to carry
`validate_only=True`. The Google Ads API, when it sees `validate_only=True`,
runs the request through full server-side validation but performs **no
mutation** — nothing is created, updated, or removed in the account.

The design is FAIL-CLOSED. The default posture is "do not send." A mutate call
is allowed to reach the API only when we have POSITIVELY set validate_only on
it. If — for any reason — we cannot force validate_only onto a mutate call
(unexpected signature, no request object we can flag, no injectable kwarg), we
RAISE `DryRunBlocked` *before* the real method is invoked. We never let an
unflagged mutate through on a best-effort basis.

HOW IT WORKS
============
We monkeypatch `google.ads.googleads.client.GoogleAdsClient.get_service`. Every
service client the SDK hands out (CampaignService, AssetService, ...) is passed
through `_wrap_service`, which replaces each *mutate* method with a guard:

  * A method is treated as a MUTATE if its name contains the substring
    "mutate" (covers `mutate_campaigns`, `GoogleAdsService.mutate`, batch
    variants, etc.). Non-mutate methods (`search`, `search_stream`,
    `suggest_*`, `generate_*`, keyword-plan forecasts, ...) are returned
    completely untouched — they pass through with zero interference.

  * On a mutate call, the guard forces validate_only using two strategies,
    matching the two request-shapes seen across this codebase:

      (a) REQUEST-OBJECT form — `mutate_x(request=<proto>)` or
          `mutate_x(<proto>)` positionally. We locate the proto (the `request`
          kwarg, else the first positional arg) and, if it exposes a
          `validate_only` attribute, set `request.validate_only = True`. This
          works for both proto-plus and raw-protobuf request messages.

      (b) KWARGS form — `mutate_x(customer_id=..., operations=[...])` with NO
          request object (e.g. ExperimentArmService). The SDK builds the
          request proto internally and honors a `validate_only=` kwarg, so we
          inject `kwargs["validate_only"] = True`.

  * FAIL-CLOSED gate: if the method is a mutate but NEITHER strategy could
    positively set validate_only (no flaggable request proto AND we did not
    inject the kwarg), we RAISE `DryRunBlocked` and the real method is never
    called.

  * A module-level counter records how many mutates were forced and how many
    were blocked-unforced, so a caller can assert (blocked == 0) and
    (forced > 0) as a post-run safety proof.

Idempotent: services are cached by id and their methods are marked
`__dry_run_wrapped__` so a second `get_service("CampaignService")` does not
double-wrap.

This module is self-contained and importable; it monkeypatches only while the
context manager is active and restores the original `get_service` on exit.
"""

from __future__ import annotations

import functools
import inspect
import threading
from contextlib import contextmanager
from typing import Any, Dict, Iterator

from google.ads.googleads.client import GoogleAdsClient


class DryRunBlocked(Exception):
    """Raised when a mutate could NOT be forced to validate_only.

    Fail-closed sentinel: the real mutate is never executed when this fires.
    """


class _Counters:
    """Thread-safe tally of what the guard did, for the safety post-check."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.forced = 0            # mutates we positively flagged validate_only
        self.blocked_unforced = 0  # mutates we refused to send (DryRunBlocked)
        self.passthrough = 0       # non-mutate methods returned untouched
        self.forced_methods: Dict[str, int] = {}

    def record_forced(self, method_name: str) -> None:
        with self._lock:
            self.forced += 1
            self.forced_methods[method_name] = (
                self.forced_methods.get(method_name, 0) + 1
            )

    def record_blocked(self) -> None:
        with self._lock:
            self.blocked_unforced += 1

    def reset(self) -> None:
        with self._lock:
            self.forced = 0
            self.blocked_unforced = 0
            self.passthrough = 0
            self.forced_methods = {}


# Module-level counters — a driver can read these after the run.
COUNTERS = _Counters()


def _is_mutate_method(name: str) -> bool:
    """A method writes iff its name contains 'mutate'.

    The Google Ads SDK's entire write surface is the ``mutate_*`` family
    (plus ``GoogleAdsService.mutate`` — the all-in-one batch mutate). Anything
    without "mutate" in the name is a read/lookup/suggest/generate call.
    """
    return "mutate" in name.lower()


def _force_on_request_obj(req: Any) -> bool:
    """Try strategy (a): set validate_only on a request proto. Returns success."""
    if req is None:
        return False
    # proto-plus messages and raw protobuf messages both expose validate_only
    # as a settable attribute when the request type has that field. hasattr is
    # the reliable cross-form probe.
    if hasattr(req, "validate_only"):
        try:
            req.validate_only = True
            # Confirm it actually took (defensive — some read-only wrappers
            # silently ignore sets). If it didn't stick, treat as failure so we
            # fail closed rather than send an unflagged mutate.
            if bool(getattr(req, "validate_only")) is True:
                return True
        except Exception:
            return False
    return False


def _make_guard(method: Any, method_name: str) -> Any:
    """Wrap a single mutate method with the fail-closed validate_only guard."""

    @functools.wraps(method)
    def guard(*args: Any, **kwargs: Any) -> Any:
        forced = False

        # Strategy (a): explicit request object.
        #   - keyword form: mutate_x(request=<proto>)
        #   - positional form: mutate_x(<proto>) — first positional arg
        if "request" in kwargs:
            if _force_on_request_obj(kwargs["request"]):
                forced = True
        elif args:
            # First positional is the request proto in the request-object form.
            # (Bound methods are already bound, so args[0] is the request, not
            # `self`.)
            if _force_on_request_obj(args[0]):
                forced = True

        # Strategy (b): kwargs form with no flaggable request object. The SDK
        # builds the request internally and honors validate_only= kwarg.
        if not forced:
            has_request_obj = ("request" in kwargs) or bool(args)
            looks_like_kwargs_form = ("customer_id" in kwargs) or (
                "operations" in kwargs
            )
            if not has_request_obj and looks_like_kwargs_form:
                kwargs["validate_only"] = True
                forced = True
            elif has_request_obj and not forced:
                # There WAS a request object but it had no validate_only field
                # we could set (or the set didn't stick). Last-resort: if the
                # SDK signature also accepts a validate_only kwarg alongside a
                # request, injecting it is harmless and honored. Only do this if
                # the request object genuinely lacked the field — otherwise we
                # already returned forced=True above.
                try:
                    sig = inspect.signature(method)
                    if "validate_only" in sig.parameters:
                        kwargs["validate_only"] = True
                        forced = True
                except (TypeError, ValueError):
                    pass

        # FAIL-CLOSED: refuse to send an unflagged mutate.
        if not forced:
            COUNTERS.record_blocked()
            raise DryRunBlocked(
                f"Refusing to call mutate method '{method_name}': could not "
                f"positively force validate_only=True (no flaggable request "
                f"proto and no injectable validate_only kwarg). "
                f"Fail-closed — the real mutate was NOT executed. "
                f"args={_summarize_args(args)} kwargs={sorted(kwargs)}"
            )

        COUNTERS.record_forced(method_name)
        return method(*args, **kwargs)

    guard.__dry_run_wrapped__ = True  # type: ignore[attr-defined]
    return guard


def _summarize_args(args: tuple) -> str:
    """Compact, safe repr of positional args for error messages."""
    out = []
    for a in args:
        t = type(a).__name__
        out.append(t)
    return "[" + ", ".join(out) + "]"


def _wrap_service(service: Any) -> Any:
    """Replace every mutate method on a service client with the guard.

    Idempotent: already-wrapped methods (marked ``__dry_run_wrapped__``) are
    left alone, so wrapping the same service twice is a no-op.
    """
    for attr_name in dir(service):
        if attr_name.startswith("_"):
            continue
        if not _is_mutate_method(attr_name):
            continue
        try:
            member = getattr(service, attr_name)
        except Exception:
            continue
        if not callable(member):
            continue
        if getattr(member, "__dry_run_wrapped__", False):
            continue  # already guarded
        guarded = _make_guard(member, attr_name)
        try:
            setattr(service, attr_name, guarded)
        except Exception:
            # If we cannot even replace the method, we must not leave a live
            # unguarded mutate reachable. Replace with a hard-blocking stub.
            def _blocked(*_a: Any, _n: str = attr_name, **_k: Any) -> Any:
                COUNTERS.record_blocked()
                raise DryRunBlocked(
                    f"Mutate method '{_n}' could not be wrapped; blocked "
                    f"fail-closed."
                )

            try:
                setattr(service, attr_name, _blocked)
            except Exception:
                pass
    return service


@contextmanager
def force_validate_only(reset_counters: bool = True) -> Iterator[_Counters]:
    """Context manager: force every Google Ads mutate to validate_only=True.

    While active, ``GoogleAdsClient.get_service`` returns service clients whose
    mutate methods are guarded. Yields the module ``COUNTERS`` so the caller can
    inspect ``forced`` / ``blocked_unforced`` after the block.

    On any mutate that cannot be forced, ``DryRunBlocked`` is raised inside the
    guarded call (fail-closed).
    """
    if reset_counters:
        COUNTERS.reset()

    original_get_service = GoogleAdsClient.get_service
    # Cache wrapped services by identity of (client, service_object) so
    # repeated get_service calls don't re-wrap.
    _seen_service_ids: set[int] = set()

    @functools.wraps(original_get_service)
    def patched_get_service(self: Any, name: str, *a: Any, **k: Any) -> Any:
        service = original_get_service(self, name, *a, **k)
        sid = id(service)
        if sid not in _seen_service_ids:
            _wrap_service(service)
            _seen_service_ids.add(sid)
        return service

    GoogleAdsClient.get_service = patched_get_service  # type: ignore[assignment]
    try:
        yield COUNTERS
    finally:
        GoogleAdsClient.get_service = original_get_service  # type: ignore[assignment]


# Alias per the brief.
patch_validate_only = force_validate_only


if __name__ == "__main__":
    # Minimal self-test: prove the classifier and the fail-closed gate without
    # touching the network.
    assert _is_mutate_method("mutate_campaigns")
    assert _is_mutate_method("mutate")
    assert not _is_mutate_method("search")
    assert not _is_mutate_method("suggest_geo_target_constants")

    class _FakeReq:
        def __init__(self) -> None:
            self.validate_only = False

    class _FakeService:
        def mutate_things(self, request=None, **kw):  # noqa: ANN001
            return request

        def mutate_kwargs_form(self, customer_id=None, operations=None,
                               validate_only=False):  # noqa: ANN001
            return {"customer_id": customer_id, "validate_only": validate_only}

        def mutate_unforceable(self, blob):  # noqa: ANN001
            # No request proto with validate_only, no customer_id/operations,
            # no validate_only param -> must be blocked.
            return blob

        def search(self, query=None):  # noqa: ANN001
            return "read-ok"

    svc = _FakeService()
    _wrap_service(svc)
    COUNTERS.reset()

    # (a) request-object form
    r = _FakeReq()
    svc.mutate_things(request=r)
    assert r.validate_only is True, "request-object form not forced"

    # (b) kwargs form
    res = svc.mutate_kwargs_form(customer_id="123", operations=[1])
    assert res["validate_only"] is True, "kwargs form not forced"

    # read passthrough
    assert svc.search(query="x") == "read-ok"

    # fail-closed block
    blocked = False
    try:
        svc.mutate_unforceable("payload")
    except DryRunBlocked:
        blocked = True
    assert blocked, "unforceable mutate was NOT blocked (fail-open bug!)"

    print(
        f"[self-test PASS] forced={COUNTERS.forced} "
        f"blocked_unforced={COUNTERS.blocked_unforced} "
        f"methods={COUNTERS.forced_methods}"
    )
    assert COUNTERS.forced == 2 and COUNTERS.blocked_unforced == 1
    print("[self-test PASS] fail-closed contract holds.")
