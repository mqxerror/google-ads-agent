"""1-click revert executor for the Changelog.

Given a `change_log` row id, apply the INVERSE of that change through the shared
`ads_mutations` service layer (never a raw duplicate), read back to verify, then
record the revert itself as a new change_log row so the timeline stays honest —
the original row is stamped `reverted_by`, the new row carries `reverts`.

Supported revert classes (the `revert_spec.kind` values `change_capture` mints):
  restore_status  · restore_budget · restore_bid · remove_criteria ·
  remove_ad · restore_final_urls · restore_asset_status

Guarantees:
  * Idempotent — reverting an already-reverted change (or batch) → RevertConflict
    (HTTP 409). A revert row can't itself be reverted.
  * Batch-aware — a change written as part of a batch (shared `batch_id`, e.g. 24
    negatives added at once) reverts ALL its members in one op, one revert row.
  * Read-back verified — the observed post-revert value is compared to the target.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from app.services import ads_mutations, change_log

logger = logging.getLogger(__name__)


class RevertError(Exception):
    """Base — a revert couldn't be performed."""


class RevertNotFound(RevertError):
    pass


class RevertNotSupported(RevertError):
    """The change isn't revertible (destructive, or before-state uncaptured)."""


class RevertConflict(RevertError):
    """The change (or its batch) was already reverted → idempotent 409."""


def _client():
    """The live Google Ads client. Lazily ensures the SDK is initialised (reusing
    the operations router's init) so a revert works even on a cold process. Patched
    wholesale in tests."""
    from google_ads.sdk_client import get_sdk_client
    try:
        return get_sdk_client().client
    except Exception:
        from app.routers.operations import _ensure_sdk
        _ensure_sdk()
        return get_sdk_client().client


# ── Inverse application (dispatch by revert_spec kind) ────────────────────────

def _apply(client, spec: dict[str, Any]) -> dict[str, Any]:
    """Execute one inverse op + read-back verify. Returns
    {resource_name(s), observed, verified}. Raises RevertNotSupported for an
    unknown/incomplete spec."""
    kind = spec.get("kind")
    cid = spec.get("customer_id")

    if kind == "restore_status":
        target, want = spec.get("target"), spec.get("restore")
        if target == "campaign":
            rn = ads_mutations.set_campaign_status(client, cid, spec["campaign_id"], want)
            obs = ads_mutations.get_campaign_status(client, cid, spec["campaign_id"])
        elif target == "ad_group":
            rn = ads_mutations.set_ad_group_status(client, cid, spec["ad_group_id"], want)
            obs = ads_mutations.get_ad_group_status(client, cid, spec["ad_group_id"])
        elif target == "keyword":
            rn = ads_mutations.set_keyword_status(
                client, cid, spec["ad_group_id"], spec["criterion_id"], want)
            obs = ads_mutations.get_keyword_status(
                client, cid, spec["ad_group_id"], spec["criterion_id"])
        elif target == "ad":
            rn = ads_mutations.set_ad_group_ad_status(
                client, cid, spec["ad_group_id"], spec["ad_id"], want)
            obs = ads_mutations.get_ad_status(client, cid, spec["ad_group_id"], spec["ad_id"])
        else:
            raise RevertNotSupported(f"unknown status target {target!r}")
        return {"resource_name": rn, "observed": obs, "verified": obs == want}

    if kind == "restore_budget":
        want = int(spec.get("restore_micros") or 0)
        rn = ads_mutations.set_campaign_budget_micros(
            client, cid, want,
            budget_resource_name=spec.get("budget_resource_name"),
            campaign_id=spec.get("campaign_id"))
        info = ads_mutations.get_campaign_budget(client, cid, spec["campaign_id"]) \
            if spec.get("campaign_id") else None
        obs = info[1] if info else None
        return {"resource_name": rn, "observed": obs,
                "verified": obs is None or int(obs) == want}

    if kind == "restore_bid":
        want = int(spec.get("restore_micros") or 0)
        rn = spec["criterion_resource_name"]
        ads_mutations.set_criterion_bid(client, cid, rn, want)
        obs = ads_mutations.get_criterion_bid(client, cid, rn)
        return {"resource_name": rn, "observed": obs,
                "verified": obs is None or int(obs) == want}

    if kind == "remove_criteria":
        names = spec.get("resource_names") or []
        ctype = spec.get("criterion_type", "ad_group")
        if ctype == "campaign":
            removed = ads_mutations.remove_campaign_criteria(client, cid, names)
        elif ctype == "customer":
            removed = ads_mutations.remove_customer_negative_criteria(client, cid, names)
        else:  # ad_group / shared → ad_group criteria path
            removed = ads_mutations.remove_ad_group_criteria(client, cid, names)
        return {"resource_name": removed, "observed": removed,
                "verified": len(removed) == len(names)}

    if kind == "remove_ad":
        rn = ads_mutations.remove_ad_group_ad(client, cid, spec["ad_group_ad_resource_name"])
        return {"resource_name": rn, "observed": rn, "verified": True}

    if kind == "restore_final_urls":
        urls = spec.get("restore_urls") or []
        rn = ads_mutations.set_ad_final_urls(client, cid, spec["ad_resource_name"], urls)
        obs = ads_mutations.get_ad_final_urls(client, cid, spec["ad_resource_name"])
        return {"resource_name": rn, "observed": list(obs),
                "verified": list(obs) == list(urls)}

    if kind == "restore_asset_status":
        want = spec.get("restore")
        rn = ads_mutations.set_campaign_asset_status(
            client, cid, spec["campaign_asset_resource_name"], want)
        obs = ads_mutations.get_campaign_asset_status(
            client, cid, spec["campaign_asset_resource_name"])
        return {"resource_name": rn, "observed": obs, "verified": obs == want}

    raise RevertNotSupported(f"unsupported revert kind {kind!r}")


def _parse_spec(row: dict[str, Any]) -> dict[str, Any] | None:
    raw = row.get("revert_spec")
    if not raw:
        return None
    try:
        return json.loads(raw)
    except (TypeError, ValueError):
        return None


async def revert_change(change_id: int) -> dict[str, Any]:
    """Revert one change (or its whole batch). Returns
    {status, revert_id, reverted_ids, verified, summary}. Raises RevertNotFound /
    RevertNotSupported / RevertConflict for the router to map to 404 / 400 / 409."""
    row = await change_log.get(change_id)
    if not row:
        raise RevertNotFound(f"change #{change_id} not found")
    if row.get("actor_type") == "revert" or row.get("reverts"):
        raise RevertNotSupported("A revert can't itself be reverted — make the "
                                 "change again if you want it back.")
    if row.get("reverted_by"):
        raise RevertConflict(f"change #{change_id} was already reverted "
                             f"(by #{row['reverted_by']}).")

    batch_id = row.get("batch_id")
    members = await change_log.batch_members(batch_id) if batch_id else [row]

    # Idempotence for batches — any member already reverted blocks the group.
    if any(m.get("reverted_by") for m in members):
        raise RevertConflict("This change was already reverted.")

    revertible = [m for m in members if m.get("revertible")]
    if not revertible:
        reason = row.get("revert_reason") or "This change can't be reverted."
        raise RevertNotSupported(reason)

    client = _client()

    # Batch of same-kind criterion ADDs → collapse to ONE inverse op.
    specs = [(_parse_spec(m), m) for m in revertible]
    specs = [(s, m) for s, m in specs if s]
    if not specs:
        raise RevertNotSupported("No executable revert spec found on this change.")

    results: list[dict[str, Any]] = []
    if len(specs) > 1 and all(s.get("kind") == "remove_criteria" for s, _ in specs):
        merged = dict(specs[0][0])
        all_names: list[str] = []
        for s, _ in specs:
            all_names.extend(s.get("resource_names") or [])
        merged["resource_names"] = all_names
        results.append(_apply(client, merged))
    else:
        for s, _ in specs:
            results.append(_apply(client, s))

    verified = all(r.get("verified") for r in results)

    # Record the revert as a new change row + stamp the originals.
    reverted_ids = [m["id"] for s, m in specs]
    if batch_id and len(reverted_ids) > 1:
        summary = f"Reverted: {row.get('summary') or f'{len(reverted_ids)} changes'}"
    else:
        summary = f"Reverted: {row.get('summary') or f'change #{change_id}'}"

    from app.database import get_db
    db = await get_db()
    try:
        revert_row = {
            "actor_type": "revert",
            "actor_detail": f"Revert of #{change_id}"
            + (f" (+{len(reverted_ids) - 1} in batch)" if len(reverted_ids) > 1 else ""),
            "account_id": row.get("account_id"),
            "campaign_id": row.get("campaign_id"),
            "resource": row.get("resource"),
            "resource_name": row.get("resource_name"),
            "action": "revert",
            "field": row.get("field"),
            "before_value": row.get("after_value"),
            "after_value": row.get("before_value"),
            "summary": summary,
            "revertible": 0,
            "revert_reason": "Reverting a revert isn't supported — re-apply the "
                             "change instead.",
            "reverts": change_id,
        }
        revert_id = await change_log.record(revert_row, db=db)
        for _s, m in specs:
            await change_log.mark_reverted(m["id"], revert_id, db=db)
        await db.commit()
    finally:
        await db.close()

    return {
        "status": "ok",
        "revert_id": revert_id,
        "reverted_ids": reverted_ids,
        "verified": verified,
        "summary": summary,
    }
