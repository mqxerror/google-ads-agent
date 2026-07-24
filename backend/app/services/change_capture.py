"""Change-capture brain — classify a write, summarise it, and describe its inverse.

This module is the single, *dependency-light* source of truth for turning a
mutation (an MCP tool call or an app-router write) into a `change_log` row with a
`revert_spec`. It is imported by BOTH the FastAPI app process (operations router,
revert executor) AND the separate Google-Ads MCP server process (the
`CampaignScopeMiddleware` logging hook), so it must stay import-cheap: stdlib +
`google_ads.tool_registry.canonical_tool_name` only. No FastAPI, no aiosqlite.

What lives here (all PURE except `record_change_sync`, the stdlib-sqlite writer
the MCP process uses):

  * ``classify(tool_name)``          — is this MCP tool a write? which class?
  * ``plan_before_read(tool, args)`` — for update-class tools, the GAQL the caller
                                       should run BEFORE the mutate to capture the
                                       old value (the caller owns the SDK IO).
  * ``build_change_row(...)``        — assemble the full row dict (revertible flag,
                                       revert_spec, human summary) from the parts.
  * ``extract_resource_names(sc)``   — dig created resource names out of a proto-
                                       serialised tool result (for ADD reverts).
  * ``record_change_sync(row)``      — INSERT one row via stdlib sqlite3.

The revert executor (`app/services/change_revert.py`) consumes ``revert_spec``.
The revertible classes (as shipped) are: status flips, budget restores, bid
restores, keyword/negative ADD → remove, final-URL restores, asset link/status
restore, and RSA pin restores. Everything else is logged ``revertible=0`` with a
plain-English ``revert_reason``.
"""

from __future__ import annotations

import json
import re
import sqlite3
from typing import Any

from google_ads.tool_registry import canonical_tool_name

# ── Tool → change classification ──────────────────────────────────────────────
# Keys are CANONICAL tool-name fragments (see tool_registry.canonical_tool_name):
# a live tool matches an entry when the entry is a substring of its canonical
# name, so this survives the single/double-underscore + namespace drift the
# registry was built to absorb. Order matters — first match wins — so more
# specific fragments come before broader ones.
#
# Each entry: (fragment, spec) where spec describes the class.
#   action:  add | update | status | remove | create
#   resource: campaign | ad_group | keyword | negative_keyword | ad | budget |
#             bid_modifier | asset | rsa_pins
#   revert:  the revert_spec "kind" if in-principle revertible, else None
#   needs_before: True  -> revertibility requires a captured before-value
#   reason:  when revert is None, the plain reason it can't be undone

_WRITE_RULES: list[tuple[str, dict[str, Any]]] = [
    # ── ADD-class (revert = remove what we created) ──────────────────────────
    ("campaign_criterion_add_negative_keyword", {
        "action": "add", "resource": "negative_keyword",
        "revert": "remove_criteria", "criterion_type": "campaign"}),
    ("customer_negative_criterion_add_negative_keywords", {
        "action": "add", "resource": "negative_keyword",
        "revert": "remove_criteria", "criterion_type": "customer"}),
    ("shared_criterion_add_keywords_to_shared_set", {
        "action": "add", "resource": "negative_keyword",
        "revert": "remove_criteria", "criterion_type": "shared"}),
    ("ad_group_criterion_add_keywords", {
        "action": "add", "resource": "keyword",
        "revert": "remove_criteria", "criterion_type": "ad_group"}),
    ("ad_group_ad_create_ad_group_ad", {
        "action": "add", "resource": "ad", "revert": "remove_ad"}),
    ("ad_create_responsive_search_ad", {
        "action": "add", "resource": "ad", "revert": "remove_ad"}),
    # ── STATUS-class (revert = restore the prior status; needs before) ───────
    ("ad_group_criterion_update_ad_group_criterion_status", {
        "action": "status", "resource": "keyword", "field": "status",
        "revert": "restore_status", "target": "keyword", "needs_before": True}),
    ("ad_group_ad_update_ad_group_ad_status", {
        "action": "status", "resource": "ad", "field": "status",
        "revert": "restore_status", "target": "ad", "needs_before": True}),
    ("ad_update_ad_status", {
        "action": "status", "resource": "ad", "field": "status",
        "revert": "restore_status", "target": "ad", "needs_before": True}),
    ("campaign_asset_update_campaign_asset_status", {
        "action": "status", "resource": "asset", "field": "status",
        "revert": "restore_asset_status", "needs_before": True}),
    # ── UPDATE-class (restore the prior value; needs before) ─────────────────
    ("ad_group_criterion_update_criterion_bid", {
        "action": "update", "resource": "keyword", "field": "cpc_bid_micros",
        "revert": "restore_bid", "needs_before": True}),
    ("budget_update_campaign_budget", {
        "action": "update", "resource": "budget", "field": "amount_micros",
        "revert": "restore_budget", "needs_before": True}),
    ("campaign_bid_modifier_update_bid_modifier", {
        "action": "update", "resource": "bid_modifier", "field": "bid_modifier",
        "revert": "restore_bid_modifier", "needs_before": True}),
    ("ad_group_bid_modifier_update_ad_group_bid_modifier", {
        "action": "update", "resource": "bid_modifier", "field": "bid_modifier",
        "revert": "restore_bid_modifier", "needs_before": True}),
    ("ad_update_rsa_pins", {
        "action": "update", "resource": "rsa_pins", "field": "pins",
        "revert": "restore_pins", "needs_before": True}),
    ("campaign_update_campaign", {
        "action": "update", "resource": "campaign", "field": "status",
        "revert": "restore_status", "target": "campaign", "needs_before": True}),
    ("ad_group_update_ad_group", {
        "action": "update", "resource": "ad_group", "field": "status",
        "revert": "restore_status", "target": "ad_group", "needs_before": True}),
    # ── Genuinely irreversible from the log (no safe inverse) ────────────────
    ("ad_group_criterion_remove_ad_group_criterion", {
        "action": "remove", "resource": "keyword", "revert": None,
        "reason": "Removing a keyword is destructive — re-creating it would "
                  "lose its history and stats. Re-add it manually if needed."}),
    ("ad_group_ad_remove_ad_group_ad", {
        "action": "remove", "resource": "ad", "revert": None,
        "reason": "Removing an ad is destructive and cannot be safely recreated "
                  "with its original ID/history."}),
    ("asset_remove_asset", {
        "action": "remove", "resource": "asset", "revert": None,
        "reason": "Removing an asset is destructive; recreate it manually."}),
    ("budget_create_campaign_budget", {
        "action": "create", "resource": "budget", "revert": None,
        "reason": "Deleting a freshly-created budget can strand its campaign; "
                  "remove it manually if it was a mistake."}),
    ("asset_update_asset", {
        "action": "update", "resource": "asset", "field": "asset",
        "revert": None,
        "reason": "Asset field edits aren't auto-reversible in v1; the prior "
                  "asset content isn't captured. Re-edit manually."}),
]


def classify(tool_name: str) -> dict[str, Any] | None:
    """Return the write-classification for an MCP tool, or None if it isn't a
    tracked write (reads, list/search/get, or anything unmatched)."""
    canon = canonical_tool_name(tool_name)
    if not canon:
        return None
    for fragment, spec in _WRITE_RULES:
        if fragment in canon:
            return dict(spec)  # copy so callers can't mutate the rule table
    return None


# ── Value / summary formatting ────────────────────────────────────────────────

def _digits(v: Any) -> str:
    return re.sub(r"\D", "", str(v or ""))


def money(micros: Any) -> str:
    try:
        return f"${int(micros) / 1_000_000:,.2f}"
    except (TypeError, ValueError):
        return "?"


def summarize(spec: dict[str, Any], before: Any, after: Any,
              *, batch_count: int = 1, args: dict | None = None) -> str:
    """Human one-liner: 'Budget $150.00 → $200.00', 'Added 24 negatives', …"""
    resource = spec.get("resource", "resource")
    field = spec.get("field")
    action = spec.get("action")
    args = args or {}

    if action == "add":
        noun = {
            "negative_keyword": "negative keyword",
            "keyword": "keyword",
            "ad": "ad",
        }.get(resource, resource)
        if batch_count and batch_count > 1:
            return f"Added {batch_count} {noun}s"
        text = args.get("keyword_text") or args.get("text")
        if not text:
            kws = args.get("keywords")
            if isinstance(kws, list) and kws:
                first = kws[0]
                text = first.get("text") if isinstance(first, dict) else str(first)
        return f"Added {noun}" + (f" '{text}'" if text else "")
    if action == "remove":
        return f"Removed {resource.replace('_', ' ')}"
    if action == "create":
        return f"Created {resource}"
    if field == "status":
        if after in (None, ""):
            return f"{resource.replace('_', ' ').title()} settings updated"
        return f"Status {before or '?'} → {after}"
    if field in ("amount_micros", "cpc_bid_micros"):
        label = "Budget" if field == "amount_micros" else "Max CPC"
        return f"{label} {money(before)} → {money(after)}"
    if field == "bid_modifier":
        return f"Bid modifier {before or '?'} → {after or '?'}"
    if field == "pins":
        return "RSA pin layout changed"
    if field == "asset":
        return f"Edited {resource}"
    if field == "final_urls":
        return f"Landing page {before or '?'} → {after or '?'}"
    return f"{resource} {field or 'changed'}"


# ── Before-read planning (caller runs the GAQL; this stays pure) ───────────────

def _cid(args: dict) -> str:
    return _digits(args.get("customer_id"))


def plan_before_read(tool_name: str, args: dict) -> dict[str, Any] | None:
    """For an update/status-class MCP write, return {gaql, customer_id, parse}
    so the caller can capture the old value with ONE GAQL before mutating. Only
    the cheap, well-understood cases are supported; everything else returns None
    (the write is then logged revertible=0 with a reason)."""
    spec = classify(tool_name)
    if not spec or not spec.get("needs_before"):
        return None
    canon = canonical_tool_name(tool_name)
    cid = _cid(args)
    if not cid:
        return None

    if "update_ad_group_criterion_status" in canon or "update_criterion_bid" in canon:
        rn = args.get("criterion_resource_name")
        if not rn:
            ag = args.get("ad_group_id")
            crit = args.get("criterion_id")
            if ag and crit:
                rn = f"customers/{cid}/adGroupCriteria/{ag}~{crit}"
        if not rn:
            return None
        col = ("ad_group_criterion.cpc_bid_micros"
               if "update_criterion_bid" in canon
               else "ad_group_criterion.status")
        return {"customer_id": cid, "parse": spec.get("field"),
                "gaql": f"SELECT {col} FROM ad_group_criterion "
                        f"WHERE ad_group_criterion.resource_name = '{rn}'"}

    if "ad_group_ad_update_ad_group_ad_status" in canon:
        ag = _digits(args.get("ad_group_id"))
        ad = _digits(args.get("ad_id"))
        if not (ag and ad):
            return None
        rn = f"customers/{cid}/adGroupAds/{ag}~{ad}"
        return {"customer_id": cid, "parse": "status",
                "gaql": f"SELECT ad_group_ad.status FROM ad_group_ad "
                        f"WHERE ad_group_ad.resource_name = '{rn}'"}

    if "campaign_update_campaign" in canon:
        camp = _digits(args.get("campaign_id"))
        if not camp:
            return None
        return {"customer_id": cid, "parse": "status",
                "gaql": f"SELECT campaign.status FROM campaign "
                        f"WHERE campaign.id = {camp}"}

    if "update_campaign_budget" in canon:
        rn = args.get("campaign_budget_resource_name") or args.get("resource_name")
        if rn:
            where = f"campaign_budget.resource_name = '{rn}'"
        else:
            camp = _digits(args.get("campaign_id"))
            if not camp:
                return None
            # Resolve the budget through the campaign in the executor's read;
            # here we read the budget's current amount via the campaign join.
            return {"customer_id": cid, "parse": "amount_micros", "via_campaign": camp,
                    "gaql": f"SELECT campaign_budget.amount_micros, "
                            f"campaign.campaign_budget FROM campaign "
                            f"WHERE campaign.id = {camp}"}
        return {"customer_id": cid, "parse": "amount_micros",
                "gaql": f"SELECT campaign_budget.amount_micros FROM campaign_budget "
                        f"WHERE {where}"}

    if "ad_group_update_ad_group" in canon:
        ag = _digits(args.get("ad_group_id"))
        if not ag:
            return None
        return {"customer_id": cid, "parse": "status",
                "gaql": f"SELECT ad_group.status FROM ad_group "
                        f"WHERE ad_group.id = {ag}"}

    # ad status / asset status / pins / bid_modifier before-reads are handled by
    # the app-side operations router (which has direct before-state); at the MCP
    # layer they degrade to non-revertible with a reason.
    return None


# ── Resource-name extraction from a proto-serialised tool result ──────────────

def extract_resource_names(structured_content: Any) -> list[str]:
    """Recursively pull every ``resource_name`` out of a serialised MutateXResponse
    (``preserving_proto_field_name=True`` → snake_case). Order-preserving, deduped.
    Returns [] on anything unparseable — never raises."""
    out: list[str] = []
    seen: set[str] = set()

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            for k, v in node.items():
                if k in ("resource_name", "resourceName") and isinstance(v, str) and v:
                    if v not in seen:
                        seen.add(v)
                        out.append(v)
                else:
                    walk(v)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    try:
        walk(structured_content)
    except Exception:
        return []
    return out


# ── Row assembly ──────────────────────────────────────────────────────────────

def build_change_row(
    *,
    tool_name: str,
    args: dict,
    spec: dict[str, Any],
    actor_type: str,
    actor_detail: str | None,
    before: Any = None,
    after: Any = None,
    resource_names: list[str] | None = None,
    batch_id: str | None = None,
    batch_count: int = 1,
) -> dict[str, Any]:
    """Assemble a fully-formed change_log row dict from classified parts. Decides
    the revertible flag + revert_spec + reason + summary. Pure."""
    resource_names = resource_names or []
    cid = _cid(args)
    campaign_id = _digits(args.get("campaign_id")) or None
    revert = spec.get("revert")
    action = spec.get("action")
    field = spec.get("field")

    revertible = False
    revert_reason: str | None = spec.get("reason")
    revert_spec: dict[str, Any] | None = None

    if revert == "remove_criteria":
        if resource_names:
            revertible = True
            revert_spec = {"kind": "remove_criteria",
                           "customer_id": cid,
                           "criterion_type": spec.get("criterion_type", "ad_group"),
                           "resource_names": resource_names,
                           "shared_set": args.get("shared_set_resource_name")}
        else:
            revert_reason = ("The created criterion's ID wasn't captured, so it "
                             "can't be auto-removed. Remove it manually.")
    elif revert == "remove_ad":
        rn = resource_names[0] if resource_names else None
        if rn:
            revertible = True
            revert_spec = {"kind": "remove_ad", "customer_id": cid,
                           "ad_group_ad_resource_name": rn}
        else:
            revert_reason = "The new ad's ID wasn't captured; remove it manually."
    elif revert == "restore_status" and spec.get("needs_before"):
        if before not in (None, "") and after not in (None, ""):
            revertible = True
            revert_spec = {"kind": "restore_status", "customer_id": cid,
                           "target": spec.get("target"),
                           "campaign_id": campaign_id,
                           "ad_group_id": args.get("ad_group_id"),
                           "criterion_id": args.get("criterion_id"),
                           "ad_id": args.get("ad_id"),
                           "resource_name": (resource_names[0] if resource_names else None),
                           "restore": str(before)}
        elif after in (None, ""):
            revert_reason = ("This edit didn't change status (name/date change) — "
                             "not auto-reversible in v1.")
        else:
            revert_reason = "The prior status wasn't captured before the change."
    elif revert == "restore_bid" and spec.get("needs_before"):
        rn = args.get("criterion_resource_name") or (resource_names[0] if resource_names else None)
        if before not in (None, "") and rn:
            revertible = True
            revert_spec = {"kind": "restore_bid", "customer_id": cid,
                           "criterion_resource_name": rn,
                           "restore_micros": int(_digits(before) or 0)}
        else:
            revert_reason = "The prior bid wasn't captured before the change."
    elif revert == "restore_budget" and spec.get("needs_before"):
        if before not in (None, ""):
            revertible = True
            revert_spec = {"kind": "restore_budget", "customer_id": cid,
                           "campaign_id": campaign_id,
                           "budget_resource_name": args.get("campaign_budget_resource_name")
                           or args.get("resource_name"),
                           "restore_micros": int(_digits(before) or 0)}
        else:
            revert_reason = "The prior budget wasn't captured before the change."
    elif revert == "restore_final_urls":
        if before:
            revertible = True
            revert_spec = {"kind": "restore_final_urls", "customer_id": cid,
                           "ad_resource_name": args.get("ad_resource_name")
                           or (resource_names[0] if resource_names else None),
                           "restore_urls": before if isinstance(before, list) else [before]}
        else:
            revert_reason = "The prior landing page URLs weren't captured."
    elif revert == "restore_asset_status" and spec.get("needs_before"):
        rn = args.get("campaign_asset_resource_name") or args.get("resource_name") \
            or (resource_names[0] if resource_names else None)
        if before not in (None, "") and rn:
            revertible = True
            revert_spec = {"kind": "restore_asset_status", "customer_id": cid,
                           "campaign_asset_resource_name": rn, "restore": str(before)}
        else:
            revert_reason = "The prior asset link state wasn't captured."
    elif revert == "restore_pins" and spec.get("needs_before"):
        if before:
            revertible = True
            revert_spec = {"kind": "restore_pins", "customer_id": cid,
                           "ad_resource_name": args.get("ad_resource_name")
                           or (resource_names[0] if resource_names else None),
                           "restore_pins": before}
        else:
            revert_reason = "The prior RSA pin layout wasn't captured."
    elif revert == "restore_bid_modifier" and spec.get("needs_before"):
        rn = args.get("resource_name") or (resource_names[0] if resource_names else None)
        if before not in (None, "") and rn:
            revertible = True
            revert_spec = {"kind": "restore_bid_modifier", "customer_id": cid,
                           "resource_name": rn, "restore": before,
                           "modifier_kind": spec.get("resource")}
        else:
            revert_reason = "The prior bid modifier wasn't captured."

    summary = summarize(spec, before, after, batch_count=batch_count, args=args)

    return {
        "actor_type": actor_type,
        "actor_detail": actor_detail,
        "account_id": cid or None,
        "campaign_id": campaign_id,
        "resource": spec.get("resource", "unknown"),
        "resource_name": (resource_names[0] if resource_names else
                          revert_spec.get("resource_name") if revert_spec else None),
        "action": action or "update",
        "field": field,
        "before_value": None if before is None else json.dumps(before)
        if not isinstance(before, str) else before,
        "after_value": None if after is None else json.dumps(after)
        if not isinstance(after, str) else after,
        "summary": summary,
        "tool_name": tool_name,
        "batch_id": batch_id,
        "batch_count": batch_count,
        "revertible": 1 if revertible else 0,
        "revert_reason": None if revertible else revert_reason,
        "revert_spec": json.dumps(revert_spec) if revert_spec else None,
    }


# ── Columns + stdlib-sqlite writer (used by the MCP server process) ───────────

_COLUMNS = (
    "ts", "actor_type", "actor_detail", "account_id", "campaign_id", "resource",
    "resource_name", "action", "field", "before_value", "after_value", "summary",
    "tool_name", "batch_id", "batch_count", "revertible", "revert_reason",
    "revert_spec", "reverts", "reverted_by", "reverted_at",
)

_CREATE_SQL = """
CREATE TABLE IF NOT EXISTS change_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL DEFAULT (datetime('now')),
    actor_type TEXT NOT NULL DEFAULT 'api',
    actor_detail TEXT,
    account_id TEXT,
    campaign_id TEXT,
    resource TEXT NOT NULL DEFAULT 'unknown',
    resource_name TEXT,
    action TEXT NOT NULL DEFAULT 'update',
    field TEXT,
    before_value TEXT,
    after_value TEXT,
    summary TEXT,
    tool_name TEXT,
    batch_id TEXT,
    batch_count INTEGER DEFAULT 1,
    revertible INTEGER NOT NULL DEFAULT 0,
    revert_reason TEXT,
    revert_spec TEXT,
    reverts INTEGER,
    reverted_by INTEGER,
    reverted_at TEXT
)
"""


def _db_path() -> str:
    from app.config import settings  # lazy — keeps this module import-cheap
    return str(settings.database_path)


def record_change_sync(row: dict[str, Any], *, db_path: str | None = None) -> int | None:
    """INSERT one change_log row via stdlib sqlite3 (the MCP server process has no
    aiosqlite event loop of the app's). Best-effort: creates the table if missing,
    returns the new row id, and NEVER raises (returns None on failure)."""
    try:
        path = db_path or _db_path()
        conn = sqlite3.connect(path, timeout=5.0)
        try:
            conn.execute(_CREATE_SQL)
            cols = [c for c in _COLUMNS if c in row and c != "ts"]
            placeholders = ", ".join("?" for _ in cols)
            cur = conn.execute(
                f"INSERT INTO change_log ({', '.join(cols)}) VALUES ({placeholders})",
                tuple(row.get(c) for c in cols),
            )
            conn.commit()
            return cur.lastrowid
        finally:
            conn.close()
    except Exception:
        return None
