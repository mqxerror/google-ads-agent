"""Smart ASPECT Set wave scheduler (AD-3, Epic 17).

One approved art direction → the full slot set, rendered in waves under the
EXISTING ``studio._GENERATION_SEMAPHORE(6)`` through the EXISTING single-image
runner (``studio._run_image_job``). The batch layer ORCHESTRATES; it never forks
a second render path and never opens a second job store — the child tiles ARE
``ad_assets`` rows (V28 columns), and only the parent aggregate
(``creative_batches``) is new. So SlotThumb, the library, the SSE stream and the
exact-aspect crop all keep working unchanged.

Design invariants (architecture §8 fences, restated as code contracts):

* **One ceiling.** Every tile runs through ``studio._run_image_job``, which
  acquires the module-level ``_GENERATION_SEMAPHORE`` — batches and ad-hoc
  Studio generations share ONE 6-job cap (NFR-Q1).
* **Progress is monotonic.** Progress = terminal children / total; terminal
  states (completed | nsfw | failed) never revert in the automatic flow, so the
  fraction only ever rises. A manual retry is an explicit user re-open, outside
  that guarantee.
* **Finished tiles are never re-rendered.** The supervisor and the restart sweep
  both skip terminal children — a completed tile costs zero further credits (R2).
* **Config, not literals.** The tile cap and retry cap come from
  ``ENGINE.batch_tile_cap`` / ``ENGINE.batch_retry_max`` — no baked numbers
  (guard-scanned, NFR-D1).
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from typing import Any, Optional

from app.database import get_db
from app.services import model_catalog
from app.services.creative_specs import ENGINE

logger = logging.getLogger(__name__)

MODES = ("with_logo", "without_logo", "asset_anchored")

# Each slot's Higgsfield generation aspect: the model-supported aspect closest to
# the slot's Google geometry. `fit_image_for_slot` center-crops the remainder at
# assign time (cb76a04's rule: request 16:9, crop to 1.91:1 / 4:1 later). Keys
# mirror creative_images.IMAGE_SLOT_SPECS exactly.
SLOT_GEN_ASPECT: dict[str, str] = {
    "logos": "1:1",
    "landscape": "16:9",
    "square": "1:1",
    "portrait": "4:5",
    "tall_portrait": "9:16",
    "landscape_logo": "16:9",
}

# In-flight supervisor tasks, kept off the GC until they finish (mirrors
# studio._BACKGROUND_TASKS). Job STATE lives in DB rows, never here — this set
# holds only the asyncio.Task handles (fence F6 unaffected).
_SUPERVISORS: set[asyncio.Task] = set()


class BatchRenderError(Exception):
    """Bad batch request (unknown slot/mode, over the tile cap, …)."""


# ── credit preflight ───────────────────────────────────────────────────────

def estimate_credits(model: str, n_tiles: int) -> int:
    """Estimated Higgsfield credits for a batch = ``tiles × est_credits(model)``.

    ``est_credits`` is hand-maintained data on the catalog entry (Honesty Ledger
    #2 — the CLI exposes only prose ``cost_text``); it is added per entry in
    story 17.6. Absent (or 0), the estimate is 0 and the UI labels it "est.". The
    batch row records ACTUAL per-tile cost for recalibration."""
    entry = model_catalog.get_model(model) or {}
    per = entry.get("est_credits")
    try:
        per_i = int(per) if per is not None else 0
    except (TypeError, ValueError):
        per_i = 0
    return per_i * max(0, n_tiles)


# ── batch creation ─────────────────────────────────────────────────────────

async def create_batch(
    *,
    account_id: str,
    art_direction: str,
    model: str,
    slots: list[dict[str, Any]],
    mode: str = "without_logo",
    campaign_id: Optional[str] = None,
    logo_asset_id: Optional[str] = None,
    reference_asset_ids: Optional[list[str]] = None,
) -> dict[str, Any]:
    """Create ONE ``creative_batches`` row + N child ``ad_assets`` rows (pending).

    ``slots`` = ``[{"slot": <key>, "variants": <int>}]``. Rejects an unknown slot
    or mode, and any request over ``ENGINE.batch_tile_cap``. Returns
    ``{batch_id, tiles: [{asset_id, slot, variant_index}], est_credits}``. Does
    NOT start rendering — the caller starts the supervisor."""
    if mode not in MODES:
        raise BatchRenderError(f"unknown mode {mode!r}; expected one of {MODES}")
    if not (art_direction or "").strip():
        raise BatchRenderError("art_direction is required")

    tiles: list[tuple[str, int]] = []
    for entry in slots or []:
        slot = str(entry.get("slot") or "")
        variants = int(entry.get("variants") or 0)
        if slot not in SLOT_GEN_ASPECT:
            raise BatchRenderError(
                f"unknown slot {slot!r}; expected one of {sorted(SLOT_GEN_ASPECT)}"
            )
        if variants < 1:
            continue
        for v in range(variants):
            tiles.append((slot, v))

    n = len(tiles)
    if n == 0:
        raise BatchRenderError("no tiles requested (every slot had variants < 1)")
    if n > ENGINE.batch_tile_cap:
        raise BatchRenderError(
            f"batch of {n} tiles exceeds the cap of {ENGINE.batch_tile_cap} — "
            f"reduce slots or variants"
        )

    est = estimate_credits(model, n)
    batch_id = str(uuid.uuid4())
    tile_out: list[dict[str, Any]] = []

    db = await get_db()
    try:
        await db.execute(
            """INSERT INTO creative_batches
               (id, account_id, campaign_id, art_direction, model, mode,
                logo_asset_id, reference_asset_ids_json, slots_json, status,
                est_credits, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'running', ?, datetime('now'))""",
            (
                batch_id, account_id, campaign_id, art_direction, model, mode,
                logo_asset_id,
                json.dumps(reference_asset_ids) if reference_asset_ids else None,
                json.dumps(slots), est,
            ),
        )
        for slot, variant_index in tiles:
            asset_id = str(uuid.uuid4())
            await db.execute(
                """INSERT INTO ad_assets
                   (id, account_id, campaign_id, type, filename, url, source,
                    status, higgsfield_model, prompt, aspect_ratio,
                    batch_id, slot, variant_index, retry_count, created_at)
                   VALUES (?, ?, ?, 'image', '', '', 'higgsfield',
                           'pending', ?, ?, ?, ?, ?, ?, 0, datetime('now'))""",
                (
                    asset_id, account_id, campaign_id, model, art_direction,
                    SLOT_GEN_ASPECT[slot], batch_id, slot, variant_index,
                ),
            )
            tile_out.append(
                {"asset_id": asset_id, "slot": slot, "variant_index": variant_index}
            )
        await db.commit()
    finally:
        await db.close()

    logger.info("batch %s created: %d tiles, mode=%s, est_credits=%d",
                batch_id, n, mode, est)
    return {"batch_id": batch_id, "tiles": tile_out, "est_credits": est}


# ── supervisor ─────────────────────────────────────────────────────────────

def _track(task: asyncio.Task) -> None:
    _SUPERVISORS.add(task)
    task.add_done_callback(_SUPERVISORS.discard)


def start_supervisor(batch_id: str, *, only_asset_ids: Optional[list[str]] = None) -> asyncio.Task:
    """Fire the per-batch supervisor as a background task and return the handle."""
    task = asyncio.create_task(_supervise(batch_id, only_asset_ids=only_asset_ids))
    _track(task)
    return task


async def _supervise(batch_id: str, *, only_asset_ids: Optional[list[str]] = None) -> None:
    """Walk the batch's pending children through the single-image runner, then
    finalize. Launches all runnable tiles concurrently; the shared semaphore
    inside ``studio._run_image_job`` throttles actual generation to ≤6 (waves)."""
    batch = await _read_batch(batch_id)
    if batch is None:
        return
    children = await _read_children(batch_id)
    runnable = [
        c for c in children
        if c.get("status") == "pending"
        and (only_asset_ids is None or c["id"] in only_asset_ids)
    ]
    if runnable:
        tasks = [asyncio.create_task(_render_tile(batch, c)) for c in runnable]
        await asyncio.gather(*tasks, return_exceptions=True)
    await _finalize_if_done(batch_id)


async def _render_tile(
    batch: dict[str, Any], child: dict[str, Any], *, reattach_job_id: Optional[str] = None,
) -> None:
    """Render one tile via the EXISTING single-image runner, then post-process
    (safe-zone flags in 17.5, logo composite in 17.2). Never raises — the runner
    lands every failure in the row's status."""
    from app.routers import studio  # lazy — batch_render builds ON studio's runner

    mode = batch.get("mode") or "without_logo"
    reference: Optional[list[str]] = None
    if mode == "asset_anchored":
        try:
            reference = json.loads(batch.get("reference_asset_ids_json") or "null")
        except (TypeError, ValueError):
            reference = None

    kwargs: dict[str, Any] = dict(
        asset_id=child["id"],
        model=batch["model"],
        prompt=batch["art_direction"],
        aspect_ratio=child.get("aspect_ratio") or SLOT_GEN_ASPECT.get(child.get("slot") or "", "1:1"),
        soul_id=None,
        reference_asset_ids=reference,
    )
    # reattach_job_id is a 17.4 addition to the runner; pass only when set so the
    # runner signature stays compatible across the increment.
    if reattach_job_id:
        kwargs["reattach_job_id"] = reattach_job_id

    await studio._run_image_job(**kwargs)

    row = await studio._read_asset_row(child["id"])
    if row and row.get("status") == "completed":
        await _post_complete(batch, row)


async def _post_complete(batch: dict[str, Any], row: dict[str, Any]) -> None:
    """Per-tile completion hook. 17.5 adds the safe-zone flag write; 17.2 adds
    the with_logo compositor. Kept as one seam so both plug in without touching
    the scheduler."""
    return None


# ── retry ──────────────────────────────────────────────────────────────────

async def retry_tile(batch_id: str, asset_id: str) -> dict[str, Any]:
    """Re-enqueue ONE failed tile, up to ``ENGINE.batch_retry_max`` attempts,
    with a short backoff. A finished (completed) tile is never re-rendered (R2).
    Re-opens the batch to ``running`` and re-finalizes when the tile settles."""
    child = await _read_child(asset_id)
    if child is None or child.get("batch_id") != batch_id:
        raise BatchRenderError("tile not found in this batch")
    status = child.get("status")
    if status in ("completed",):
        raise BatchRenderError("tile already completed — nothing to retry")
    retry_count = int(child.get("retry_count") or 0)
    if retry_count >= ENGINE.batch_retry_max:
        raise BatchRenderError(
            f"tile exhausted its {ENGINE.batch_retry_max} retries"
        )

    db = await get_db()
    try:
        await db.execute(
            "UPDATE ad_assets SET status='pending', retry_count=?, "
            "error_code=NULL, error_message=NULL WHERE id=?",
            (retry_count + 1, asset_id),
        )
        await db.execute(
            "UPDATE creative_batches SET status='running' WHERE id=?", (batch_id,)
        )
        await db.commit()
    finally:
        await db.close()

    # Backoff before re-running (transient upstream blips clear fast).
    await asyncio.sleep(min(2.0 * retry_count, 4.0))
    start_supervisor(batch_id, only_asset_ids=[asset_id])
    return {"asset_id": asset_id, "status": "pending", "retry_count": retry_count + 1}


# ── read / progress ────────────────────────────────────────────────────────

def _is_terminal(child: dict[str, Any]) -> bool:
    return (child.get("status") or "") in ("completed", "nsfw", "failed")


def _progress(children: list[dict[str, Any]]) -> dict[str, int]:
    done = sum(1 for c in children if (c.get("status") or "") == "completed")
    failed = sum(1 for c in children if (c.get("status") or "") in ("failed", "nsfw"))
    return {"done": done, "failed": failed, "total": len(children)}


async def get_batch(batch_id: str) -> Optional[dict[str, Any]]:
    """The batch view: ``{batch_id, status, mode, progress{done,failed,total},
    est_credits, tiles[]}`` — the shape the GET endpoint and SSE stream serve."""
    batch = await _read_batch(batch_id)
    if batch is None:
        return None
    children = await _read_children(batch_id)
    tiles = []
    for c in children:
        safe_zone = None
        raw = c.get("safe_zone_json")
        if raw:
            try:
                safe_zone = json.loads(raw)
            except (TypeError, ValueError):
                safe_zone = None
        tiles.append({
            "asset_id": c["id"],
            "slot": c.get("slot"),
            "variant_index": c.get("variant_index"),
            "status": c.get("status") or "pending",
            "retry_count": int(c.get("retry_count") or 0),
            "url": c.get("url") or None,
            "parent_asset_id": c.get("parent_asset_id"),
            "error_message": c.get("error_message"),
            "safe_zone": safe_zone,
        })
    return {
        "batch_id": batch_id,
        "status": batch.get("status"),
        "mode": batch.get("mode"),
        "est_credits": batch.get("est_credits"),
        "progress": _progress(children),
        "tiles": tiles,
    }


async def _finalize_if_done(batch_id: str) -> Optional[str]:
    """If every child is terminal, set the batch to ``done`` /
    ``done_with_failures`` (never leave it ``running``). Returns the final status
    or None when children remain in flight."""
    children = await _read_children(batch_id)
    if not children or not all(_is_terminal(c) for c in children):
        return None
    prog = _progress(children)
    final = "done" if prog["failed"] == 0 else "done_with_failures"
    db = await get_db()
    try:
        await db.execute(
            "UPDATE creative_batches SET status=? WHERE id=?", (final, batch_id)
        )
        await db.commit()
    finally:
        await db.close()
    logger.info("batch %s finalized: %s (%s)", batch_id, final, prog)
    return final


# ── DB helpers ─────────────────────────────────────────────────────────────

async def _read_batch(batch_id: str) -> Optional[dict[str, Any]]:
    db = await get_db()
    try:
        cur = await db.execute("SELECT * FROM creative_batches WHERE id=?", (batch_id,))
        row = await cur.fetchone()
        return dict(row) if row else None
    finally:
        await db.close()


async def _read_children(batch_id: str) -> list[dict[str, Any]]:
    db = await get_db()
    try:
        cur = await db.execute(
            "SELECT * FROM ad_assets WHERE batch_id=? ORDER BY variant_index, slot",
            (batch_id,),
        )
        return [dict(r) for r in await cur.fetchall()]
    finally:
        await db.close()


async def _read_child(asset_id: str) -> Optional[dict[str, Any]]:
    db = await get_db()
    try:
        cur = await db.execute("SELECT * FROM ad_assets WHERE id=?", (asset_id,))
        row = await cur.fetchone()
        return dict(row) if row else None
    finally:
        await db.close()
