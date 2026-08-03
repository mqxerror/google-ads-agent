"""Shared image-creative helpers for the campaign orchestrators.

Both the Performance Max and Demand Gen orchestrators face the exact same
problem: a bundle names image creatives either as Google Ads asset refs
(resource name / bare numeric id — MCP/agent bundles, or a wizard bundle
poisoned by a prior attempt) OR as local upload UUIDs from
``/api/assets/upload`` / a Studio (Higgsfield) generation. Before anything is
created in Google, every ref must be classified, local bytes located, cropped
to the slot's EXACT Google aspect (±1%), transcoded (Studio ``.webp`` → PNG),
and size-capped — and pre-uploaded Google assets must be aspect-verified via
GAQL so an off-aspect one fails as a clean pre-flight error instead of
``ASPECT_RATIO_NOT_ALLOWED`` rolling back the whole campaign mid-recipe (hit
live 2026-06-11 on PMax).

This module is the single home for that logic so the two orchestrators cannot
drift. ``pmax_orchestrator`` re-exports the helpers (keeping its historical
module-level names so its regression tests can still monkeypatch
``pmax_orchestrator._locate_local_image``), and ``demand_gen_orchestrator``
imports them directly.

The slot specs (aspect + minimum pixel size) are keyed by the abstract slot
names both orchestrators use — ``logos`` / ``landscape`` / ``square`` /
``portrait`` (+ ``tall_portrait`` for Demand Gen). PMax simply never references
the ``tall_portrait`` entry, so its behavior is byte-for-byte unchanged.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Awaitable, Callable, Dict, List, Optional

# Google Ads only accepts these image formats for image assets. The local
# upload endpoint (/api/assets/upload) is deliberately broader (webp, mp4,
# audio...) because Studio uses it for non-Google purposes too — so the
# format gets re-checked at bridge time, not at upload time.
GOOGLE_IMAGE_MIME_BY_EXT = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".gif": "image/gif",
}

# Google rejects image assets above 5120KB — checked pre-flight so an
# oversized file gets transcoded (or cleanly refused) instead of blowing
# up the create mid-recipe.
MAX_GOOGLE_IMAGE_BYTES = 5 * 1024 * 1024

# Google enforces the slot's EXACT aspect ratio (±1% tolerance) and a
# hard minimum pixel size per image field type. A near-miss — a 16:9 image in
# the 1.91:1 MARKETING_IMAGE slot — fails the whole atomic create with
# ASPECT_RATIO_NOT_ALLOWED (hit live 2026-06). Local images are therefore
# center-cropped to the exact aspect pre-flight; images that sit below the
# minimum get a clean 422 instead. `aspect` is w/h.
#
# PMax uses logos/landscape/square/portrait. Demand Gen uses the same four
# plus the optional 9:16 `tall_portrait` slot — the minimums below match both
# PMax's PMax-image minimums AND Demand Gen's DemandGenMultiAssetAdInfo
# minimums (they are identical for the shared four).
#
# `landscape_logo` (4:1) is the RDA landscape-logo geometry, pre-added in P3
# (Epic 17.5) — when the Image Engine already touches slot plumbing — so P5's
# RDA builder genuinely cannot need a `creative_images.py` edit (FR6.1/FR6.2:
# after this story the module is FROZEN, and the P5 exit gate diffs it for zero
# changes). The `creative_specs.py` registry composes its geometry BY IMPORT
# from this dict (fence F2), so adding the key here flows to `GET /specs`
# automatically.
IMAGE_SLOT_SPECS = {
    "logos":          {"aspect": 1.0,    "min_w": 128, "min_h": 128,  "label": "1:1"},
    "landscape":      {"aspect": 1.91,   "min_w": 600, "min_h": 314,  "label": "1.91:1"},
    "square":         {"aspect": 1.0,    "min_w": 300, "min_h": 300,  "label": "1:1"},
    "portrait":       {"aspect": 0.8,    "min_w": 480, "min_h": 600,  "label": "4:5"},
    "tall_portrait":  {"aspect": 0.5625, "min_w": 600, "min_h": 1067, "label": "9:16"},
    "landscape_logo": {"aspect": 4.0,    "min_w": 512, "min_h": 128,  "label": "4:1"},
}
ASPECT_TOLERANCE = 0.01  # Google allows ±1% off the exact ratio


# ── Safe-zone heuristic v1 (FR2.5, D1) ─────────────────────────────────────
#
# "Subject will be cut" flags, computed FREE and LOCALLY — pure Pillow + stdlib,
# ZERO network and ZERO vision-model calls (the spy AC). The detector is one
# function behind a stable signature so the deferred vision model can drop in
# without touching a single caller (Risk R5). The flag is ADVISORY: the
# SlotThumb crop preview stays the human-verifiable truth beside it, and submit
# is NEVER blocked.

# Google overlays UI (CTA, headline) on the outer band of a served image; the
# central 80% is the reliable "safe zone" (research #9). A subject that spills
# outside it risks being covered or cropped — highest signal on the 9:16 slot.
SAFE_ZONE_FRACTION = 0.80


def subject_bbox(img) -> tuple[float, float, float, float]:
    """Estimate the subject's bounding box as normalized ``(x0, y0, x1, y1)`` in
    ``[0, 1]`` — a cheap, deterministic edge-energy heuristic (D1's accepted
    ceiling), NOT a saliency/vision model.

    Pipeline (architecture AD-3): grayscale → ``ImageFilter.FIND_EDGES`` → mean
    energy per 8×8-pixel block → threshold at ``mean + 1σ`` → bounding box of the
    LARGEST 4-connected region of above-threshold blocks → pad 4%. When no block
    clears the threshold (a near-featureless frame) the whole frame is returned
    (advisory over-flag, never a silent miss)."""
    from PIL import Image, ImageFilter  # local import — keeps module import light

    g = img.convert("L")
    w, h = g.size
    if not w or not h:
        return (0.0, 0.0, 1.0, 1.0)

    edges = g.filter(ImageFilter.FIND_EDGES)
    block = 8
    cols = max(1, w // block)
    rows = max(1, h // block)
    # BOX-resample the edge map to one cell per 8×8 block = mean block energy.
    small = edges.resize((cols, rows), Image.BOX)
    energy = list(small.tobytes())  # mode 'L' → one byte per cell, row-major
    n = len(energy)
    mean = sum(energy) / n
    var = sum((e - mean) ** 2 for e in energy) / n
    sd = var ** 0.5
    threshold = mean + sd

    hot = [e > threshold for e in energy]
    if not any(hot):
        return (0.0, 0.0, 1.0, 1.0)

    # Largest 4-connected region of hot cells (iterative flood fill).
    seen = [False] * n
    best: list[int] = []
    for start in range(n):
        if not hot[start] or seen[start]:
            continue
        stack = [start]
        seen[start] = True
        region: list[int] = []
        while stack:
            idx = stack.pop()
            region.append(idx)
            r, c = divmod(idx, cols)
            for nr, nc in ((r - 1, c), (r + 1, c), (r, c - 1), (r, c + 1)):
                if 0 <= nr < rows and 0 <= nc < cols:
                    nidx = nr * cols + nc
                    if hot[nidx] and not seen[nidx]:
                        seen[nidx] = True
                        stack.append(nidx)
        if len(region) > len(best):
            best = region

    r_vals = [idx // cols for idx in best]
    c_vals = [idx % cols for idx in best]
    # Block indices → normalized coords (block c spans [c/cols, (c+1)/cols]).
    x0 = min(c_vals) / cols
    x1 = (max(c_vals) + 1) / cols
    y0 = min(r_vals) / rows
    y1 = (max(r_vals) + 1) / rows
    pad = 0.04
    return (
        max(0.0, x0 - pad), max(0.0, y0 - pad),
        min(1.0, x1 + pad), min(1.0, y1 + pad),
    )


def crop_survival(img, target_aspect: float, *, bbox=None) -> dict:
    """Does the subject survive the center-crop to ``target_aspect`` (w/h)?

    Computes the exact-aspect center-crop window, shrinks it to its central 80%
    (the Google safe zone), and measures the fraction of the subject bbox AREA
    that lands inside. Returns ``{"flagged", "survival", "bbox", "aspect"}`` —
    ``flagged`` is True (advisory "subject will be cut") when <80% survives. Pure
    arithmetic; no image is re-encoded."""
    if bbox is None:
        bbox = subject_bbox(img)
    x0, y0, x1, y1 = bbox
    w, h = img.size
    src_aspect = (w / h) if h else target_aspect

    # Center-crop window in normalized source coords at target_aspect.
    if src_aspect > target_aspect:                 # too wide → trim left/right
        keep = target_aspect / src_aspect
        cx0, cx1 = (1 - keep) / 2, (1 + keep) / 2
        cy0, cy1 = 0.0, 1.0
    else:                                          # too tall → trim top/bottom
        keep = src_aspect / target_aspect
        cy0, cy1 = (1 - keep) / 2, (1 + keep) / 2
        cx0, cx1 = 0.0, 1.0

    def _central(a0: float, a1: float) -> tuple[float, float]:
        c = (a0 + a1) / 2
        half = (a1 - a0) * SAFE_ZONE_FRACTION / 2
        return c - half, c + half

    sx0, sx1 = _central(cx0, cx1)
    sy0, sy1 = _central(cy0, cy1)

    inter = max(0.0, min(x1, sx1) - max(x0, sx0)) * max(0.0, min(y1, sy1) - max(y0, sy0))
    bbox_area = max(1e-9, (x1 - x0) * (y1 - y0))
    survival = inter / bbox_area
    return {
        "flagged": survival < SAFE_ZONE_FRACTION,
        "survival": round(survival, 4),
        "bbox": [round(v, 4) for v in bbox],
        "aspect": target_aspect,
    }


def safe_zone_for_slot(path: "Path", slot: str) -> dict:
    """Open a rendered tile once and compute its safe-zone verdict for ``slot``.

    The batch renderer calls this at tile completion (FR2.5). Returns a
    JSON-able dict ``{"slot", "bbox", "slots": {slot: {flagged, survival}}}`` so
    the UI can render a per-slot amber chip. Never raises — a decode failure
    yields an empty (unflagged) verdict so a batch tile is never lost to an
    advisory check."""
    from PIL import Image

    spec = IMAGE_SLOT_SPECS.get(slot)
    if spec is None:
        return {"slot": slot, "bbox": None, "slots": {}}
    try:
        with Image.open(path) as opened:
            opened.load()
            bbox = subject_bbox(opened)
            verdict = crop_survival(opened, spec["aspect"], bbox=bbox)
    except Exception:
        return {"slot": slot, "bbox": None, "slots": {}}
    return {
        "slot": slot,
        "bbox": verdict["bbox"],
        "slots": {slot: {"flagged": verdict["flagged"], "survival": verdict["survival"]}},
    }


def is_google_asset_ref(ref: str) -> bool:
    """True when `ref` already identifies a Google Ads asset — either a
    full resource name (`customers/123/assets/456`) or a bare numeric
    asset id. Anything else is treated as a local asset id (UUID) from
    /api/assets/upload or a Studio generation, whose bytes still need to
    be pushed to Google as an image asset."""
    ref = (ref or "").strip()
    if not ref:
        return False
    return ref.isdigit() or (ref.startswith("customers/") and "/assets/" in ref)


def asset_resource_name(customer_id: str, ref: str) -> str:
    """Normalize an asset ref to a full resource name.

    Assets created in-process already carry full resource names; bundle
    entries that passed through as bare numeric ids (MCP/agent-created
    bundles) get expanded so link/ad rows always reference
    `customers/<cid>/assets/<id>`.
    """
    return ref if ref.startswith("customers/") else f"customers/{customer_id}/assets/{ref}"


def encode_for_google(img) -> Optional[tuple[bytes, str]]:
    """Encode a Pillow image to a (bytes, mime) pair under Google's 5MB
    cap, or None when even a JPEG re-encode busts it (caller downscales
    and retries). PNG first (lossless, keeps alpha — Studio .webp and
    logo transparency); JPEG q90 fallback for the Higgsfield Soul/4K
    outputs whose PNGs routinely exceed 5MB."""
    from io import BytesIO

    buf = BytesIO()
    img.save(buf, format="PNG")
    data = buf.getvalue()
    if len(data) <= MAX_GOOGLE_IMAGE_BYTES:
        return data, "image/png"
    buf = BytesIO()
    img.convert("RGB").save(buf, format="JPEG", quality=90)
    data = buf.getvalue()
    if len(data) <= MAX_GOOGLE_IMAGE_BYTES:
        return data, "image/jpeg"
    return None


def fit_image_for_slot(
    path: Path, slot: str, mime: Optional[str] = None
) -> Optional[tuple[bytes, str]]:
    """Make a local image Google-acceptable for `slot`, or reject it.

    Google enforces the slot's EXACT aspect (±1%) and a minimum pixel
    size — see IMAGE_SLOT_SPECS. The pipeline:

      1. Center-crop to the slot's exact aspect when off by more than
         the ±1% tolerance (crop, never letterbox/stretch).
      2. Reject anything below the slot minimum after cropping — we
         never upscale; Google would just serve a blurry ad.
      3. Re-encode (PNG first, JPEG fallback), downscaling at the same
         aspect until under the 5MB cap — but never below the minimum.

    Returns None when the on-disk file is already fully compliant
    (Google-OK format per `mime`, exact aspect, ≥ minimum, ≤ 5MB) so
    the caller can pass the original bytes through untouched — this
    keeps e.g. animated GIFs intact. Otherwise returns (bytes, mime).

    Raises ValueError with a user-actionable message phrased to read
    naturally after "<slot>[i] ('<ref>') ..."; the caller folds it into
    the pre-flight validation error (HTTP 422), so a bad image fails
    BEFORE anything is created in Google.
    """
    from PIL import Image  # local import — keeps module import light

    spec = IMAGE_SLOT_SPECS[slot]
    target = spec["aspect"]

    with Image.open(path) as opened:
        opened.load()
        img = opened
        w, h = img.size
        if not w or not h:
            raise ValueError("has zero width/height — re-export and re-upload")

        # 1 — center-crop to the exact aspect when off by more than 1%.
        aspect_ok = abs((w / h) - target) <= target * ASPECT_TOLERANCE
        if not aspect_ok:
            if (w / h) > target:  # too wide — trim left/right
                new_w, new_h = max(1, round(h * target)), h
            else:  # too tall — trim top/bottom
                new_w, new_h = w, max(1, round(w / target))
            left = (w - new_w) // 2
            top = (h - new_h) // 2
            img = img.crop((left, top, left + new_w, top + new_h))
            w, h = img.size

        # 2 — minimum size (post-crop; cropping only ever shrinks).
        if w < spec["min_w"] or h < spec["min_h"]:
            crop_note = (
                "" if aspect_ok
                else f" after center-cropping to {spec['label']}"
            )
            raise ValueError(
                f"is {w}x{h}{crop_note} — below Google's "
                f"{spec['min_w']}x{spec['min_h']} minimum for this slot "
                f"({spec['label']}); use a larger source image"
            )

        # Fully compliant on disk → pass original bytes through.
        if (
            aspect_ok
            and mime is not None
            and path.stat().st_size <= MAX_GOOGLE_IMAGE_BYTES
        ):
            return None

        # 3 — encode under the 5MB cap, downscaling (same aspect) as
        # needed but never below the slot minimum.
        while True:
            encoded = encode_for_google(img)
            if encoded is not None:
                return encoded
            scaled_w = int(w * 0.8)
            scaled_h = max(1, round(scaled_w / target))
            if scaled_w < spec["min_w"] or scaled_h < spec["min_h"]:
                raise ValueError(
                    f"can't be compressed under Google's 5120KB cap without "
                    f"dropping below the {spec['min_w']}x{spec['min_h']} "
                    f"minimum — re-export a lighter PNG/JPEG and re-upload"
                )
            img = img.resize((scaled_w, scaled_h), Image.LANCZOS)
            w, h = img.size


async def locate_local_image(ref: str) -> tuple[Path, Optional[str]]:
    """Map a local asset id (UUID from /api/assets/upload or a Studio
    generation) to its on-disk file + Google-compatible MIME type.

    Looks up the `ad_assets` DB row first (DB row = source of truth),
    then falls back to globbing ASSETS_DIR (the upload endpoint stores
    blobs as `{uuid}{ext}`). Returns mime=None when the file exists but
    isn't a format Google accepts (caller transcodes to PNG). Raises
    LookupError with a user-actionable reason — phrased to read
    naturally after "<slot>[i] ('<ref>') ..." — when the bytes can't be
    found locally.
    """
    # App-side imports live inside the function so the MCP server can
    # import this module standalone (same pattern as _post_create_sync).
    try:
        from app.database import get_db
        from app.routers.assets import ASSETS_DIR
    except ImportError as e:
        raise LookupError(
            f"is not a Google Ads asset resource name, and local-upload "
            f"resolution is unavailable in this process ({e}) — pass a "
            f"customers/<cid>/assets/<id> resource name instead"
        )

    # Defensive: refs feed a path lookup below; reject anything that
    # isn't a simple token.
    if "/" in ref or "\\" in ref or ".." in ref:
        raise LookupError(
            "is not a recognized asset reference (expected a Google Ads "
            "asset resource name or a local upload id)"
        )

    path: Optional[Path] = None
    db = await get_db()
    try:
        cur = await db.execute("SELECT url, type FROM ad_assets WHERE id = ?", (ref,))
        row = await cur.fetchone()
    finally:
        await db.close()

    if row:
        if row["type"] != "image":
            raise LookupError(
                f"is a {row['type']} asset — only images can fill "
                f"logo/marketing-image slots"
            )
        url = row["url"] or ""
        if url.startswith("/api/assets/file/") or url.startswith("/api/video/assets/"):
            path = ASSETS_DIR / url.rsplit("/", 1)[-1]

    if path is None or not path.is_file():
        # Glob fallback — covers rows whose url points elsewhere (e.g. a
        # Higgsfield CDN url after a failed local download) IF the blob
        # actually landed on disk, plus the missing-DB-row edge.
        matches = sorted(ASSETS_DIR.glob(f"{ref}.*"))
        path = matches[0] if matches else None

    if path is None or not path.is_file():
        raise LookupError(
            "has no file on this server (upload may have failed or the "
            "asset only exists on an expiring CDN) — re-upload the image"
        )

    # mime=None → not directly Google-compatible; caller transcodes.
    return path, GOOGLE_IMAGE_MIME_BY_EXT.get(path.suffix.lower())


async def resolve_image_plan(
    *,
    customer_id: str,
    slots: Dict[str, List[str]],
    fetch_dims: Callable[[str, List[str]], Dict[str, tuple[int, int]]],
    error_factory: Callable[[List[str]], Exception],
    locate: Callable[[str], Awaitable[tuple[Path, Optional[str]]]] = locate_local_image,
) -> Dict[str, List[Dict[str, Any]]]:
    """Classify every image ref in `slots` BEFORE touching Google.

    The wizard's upload endpoint (/api/assets/upload) stores files locally
    and returns a local UUID — those are NOT Google Ads resource names.
    Entries that already look like Google asset refs (resource names / bare
    numeric ids) are NOT trusted blindly: their stored dimensions are fetched
    via `fetch_dims` and the slot's exact aspect is verified pre-flight. An
    off-aspect or unverifiable pre-uploaded asset fails as a clean error
    naming slot + asset — never as ASPECT_RATIO_NOT_ALLOWED rolling back the
    whole campaign mid-recipe (hit live 2026-06).

    Args:
        customer_id: The Google Ads customer id (already formatted).
        slots: {slot_name: [image_ref, ...]} — slot_name must be a key in
            IMAGE_SLOT_SPECS.
        fetch_dims: (customer_id, [resource_name,...]) -> {resource_name:
            (w, h)} for existing IMAGE assets. Injected so unit tests can stub
            it without a live SDK client; a raising callable is caught and
            surfaces as an "unverifiable" rejection.
        error_factory: builds the exception raised when any ref is
            unresolvable (e.g. PMaxValidationError / DemandGenValidationError)
            — called with the accumulated list of error strings.
        locate: async local-image resolver (defaults to locate_local_image;
            overridable for tests / callers that keep a patchable module alias).

    Returns:
        {slot: [{"kind": "google"|"local", ...}]} for every slot in `slots`.

    Raises:
        error_factory(errors) listing every unresolvable ref so the user
        fixes them all in one pass — and nothing has been created in Google.
    """
    plan: Dict[str, List[Dict[str, Any]]] = {}
    errs: List[str] = []
    google_entries: List[tuple[str, int, str, str]] = []  # (slot, i, ref, rn)
    for slot, refs in slots.items():
        entries: List[Dict[str, Any]] = []
        for i, raw_ref in enumerate(refs or []):
            ref = (raw_ref or "").strip()
            if not ref:
                errs.append(f"{slot}[{i}] is empty")
                continue
            if is_google_asset_ref(ref):
                rn = asset_resource_name(customer_id, ref)
                google_entries.append((slot, i, ref, rn))
                entries.append({"kind": "google", "ref": ref})
                continue
            try:
                path, mime = await locate(ref)
            except LookupError as e:
                errs.append(f"{slot}[{i}] ('{ref[:40]}') {e}")
                continue
            entry: Dict[str, Any] = {
                "kind": "local", "ref": ref, "path": path, "mime": mime,
            }
            # Every local image goes through the slot fitter: it center-crops
            # to the slot's EXACT Google aspect (±1%), transcodes non-Google
            # formats (Studio .webp), enforces the 5MB cap, and rejects
            # below-minimum images — all pre-flight, so a bad image fails as a
            # clean 422 here instead of ASPECT_RATIO_NOT_ALLOWED rolling back
            # the whole campaign mid-recipe (hit live 2026-06).
            try:
                fitted = fit_image_for_slot(path, slot, mime)
            except ValueError as exc:
                errs.append(f"{slot}[{i}] ('{ref[:40]}') {exc}")
                continue
            except Exception as exc:
                errs.append(
                    f"{slot}[{i}] ('{ref[:40]}') is a {path.suffix} file "
                    f"that couldn't be processed for Google Ads ({exc}) — "
                    f"re-export as PNG/JPEG under 5MB and re-upload"
                )
                continue
            if fitted is not None:
                entry["data"], entry["mime"] = fitted
            # fitted is None → file is already fully compliant (format + exact
            # aspect + size); original bytes pass through untouched.
            entries.append(entry)
        plan[slot] = entries

    # Pre-uploaded Google assets: verify the stored aspect via `fetch_dims`.
    # A pre-existing asset can't be cropped — its bytes already live in
    # Google — so an off-aspect one is rejected here with the slot + asset
    # named, and "can't verify" counts as a rejection (never link an asset
    # whose aspect is unknown; that's exactly the resubmit path that produced
    # ASPECT_RATIO_NOT_ALLOWED at the atomic mutate, hit live 2026-06-11).
    if google_entries:
        dims: Optional[Dict[str, tuple[int, int]]]
        try:
            dims = fetch_dims(
                customer_id, sorted({rn for _, _, _, rn in google_entries})
            )
        except Exception as exc:
            dims = None
            errs.append(
                f"could not verify {len(google_entries)} pre-uploaded Google "
                f"asset(s) (asset metadata query failed: {exc}) — pass local "
                f"upload ids instead so the image can be re-fitted, or retry"
            )
        if dims is not None:
            for slot, i, ref, rn in google_entries:
                spec = IMAGE_SLOT_SPECS[slot]
                wh = dims.get(rn)
                if wh is None:
                    errs.append(
                        f"{slot}[{i}] ('{ref[:60]}') is a pre-uploaded Google "
                        f"asset whose image dimensions could not be verified "
                        f"(not found in this account, or not an image asset) — "
                        f"pass a local upload id instead so the image can be "
                        f"re-fitted to {spec['label']}"
                    )
                    continue
                w, h = wh
                target = spec["aspect"]
                if abs((w / h) - target) > target * ASPECT_TOLERANCE:
                    errs.append(
                        f"{slot}[{i}] ('{ref[:60]}') is a pre-uploaded Google "
                        f"asset at {w}x{h} — not the {spec['label']} aspect this "
                        f"slot requires, and an existing Google asset can't be "
                        f"cropped in place. Re-upload the original image (the "
                        f"upload path auto-crops to {spec['label']})"
                    )
    if errs:
        raise error_factory(errs)
    return plan
