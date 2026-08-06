"""Shared campaign conversion-goal setup — the proven 3-step sequence, one module.

This is the SINGLE module that owns conversion-goal-category logic for the
wizard / orchestrator create path (task #49). All three creative orchestrators
(Demand Gen, PMax, RDA) call :func:`setup_campaign_conversion_goal` right after
campaign creation to pin ONE chosen conversion action as the campaign's biddable
goal — replacing the account-default goals that otherwise mix PURCHASE / app
DOWNLOAD / CONTACT / SUBMIT_LEAD_FORM all as biddable at once.

The proven sequence (live-verified on account 7178239091, 2026-08-05):

  1. **CustomConversionGoalService** — REUSE-or-create a custom goal wrapping
     exactly the chosen conversion action. Never a duplicate goal per campaign:
     if a goal already contains exactly that one action we reuse it (the
     "Canada Descent Lead" goal 6458573428 is the precedent).
  2. **ConversionGoalCampaignConfigService** — set the campaign's config to
     ``goal_config_level=CAMPAIGN`` + ``custom_conversion_goal=<goal>``.
  3. **CampaignConversionGoalService** — set ``biddable=false`` on ALL of the
     campaign's category rows in ONE mutate batch. This is the step that was
     MISSED on 2026-08-05 and left Google warning "multiple conversion goals":
     a campaign-level custom goal does NOT auto-disable the inherited category
     goals — they must be cleared in the same operation.

Every conversion-goal-category resource-name literal lives here and nowhere else
(the orchestrators just call this function), so there is one place to reason
about the ``{campaign_id}~{CATEGORY}~{ORIGIN}`` format.

Testing discipline: the pure builders (:func:`build_zero_biddable_ops`,
:func:`pick_reusable_goal`, :func:`config_resource_name`,
:func:`conversion_action_rn`) are asserted against fixtures — NO live mutations
in the suite.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Tuple

from google.ads.googleads.v23.enums.types.goal_config_level import (
    GoalConfigLevelEnum,
)
from google.ads.googleads.v23.resources.types.campaign_conversion_goal import (
    CampaignConversionGoal,
)
from google.ads.googleads.v23.services.types.campaign_conversion_goal_service import (
    CampaignConversionGoalOperation,
)
from google.protobuf import field_mask_pb2

from google_ads.sdk_client import get_sdk_client
from google_ads.services.campaign.campaign_conversion_goal_service import (
    CampaignConversionGoalService,
)
from google_ads.services.conversions.conversion_goal_campaign_config_service import (
    ConversionGoalCampaignConfigService,
)
from google_ads.services.conversions.custom_conversion_goal_service import (
    CustomConversionGoalService,
)
from google_ads.utils import format_customer_id, get_logger

logger = get_logger(__name__)

# The value the wizard sends for the EXPLICIT "Account default goals" opt-out.
# The wizard forces a conscious choice; this sentinel means "leave the inherited
# account-default goals in place" — the orchestrator then skips all three steps.
ACCOUNT_DEFAULT = "ACCOUNT_DEFAULT"


class ConversionGoalSetupError(Exception):
    """A step in the 3-step conversion-goal sequence failed.

    The orchestrator catches this like any other step failure and runs its
    normal campaign + budget rollback (the campaign is removed, which cascades
    the config association; a created custom goal is account-scoped and left
    in place — it is reusable and does not spend, so the next attempt reuses it).
    """


# ── pure resource-name helpers (unit-tested; no network) ─────────────────────


def conversion_action_rn(customer_id: str, action_id: str) -> str:
    """``customers/{cid}/conversionActions/{action_id}`` — the membership key a
    custom conversion goal wraps."""
    return f"customers/{format_customer_id(customer_id)}/conversionActions/{action_id}"


def config_resource_name(customer_id: str, campaign_id: str) -> str:
    """``customers/{cid}/conversionGoalCampaignConfigs/{campaign_id}`` — one
    config per campaign, keyed by campaign id (SDK path helper confirmed)."""
    return (
        f"customers/{format_customer_id(customer_id)}"
        f"/conversionGoalCampaignConfigs/{campaign_id}"
    )


def campaign_conversion_goal_rn(
    customer_id: str, campaign_id: str, category: str, origin: str
) -> str:
    """``customers/{cid}/campaignConversionGoals/{campaign_id}~{CATEGORY}~{ORIGIN}``.

    ``category`` / ``origin`` are the enum NAMES (e.g. ``PURCHASE`` / ``WEBSITE``)
    exactly as GAQL returns them — matching the SDK
    ``campaign_conversion_goal_path(cid, campaign_id, category, source)`` helper.
    """
    return (
        f"customers/{format_customer_id(customer_id)}"
        f"/campaignConversionGoals/{campaign_id}~{category}~{origin}"
    )


def pick_reusable_goal(
    existing_goals: Sequence[Dict[str, Any]], action_rn: str
) -> Optional[str]:
    """Return the resource name of a custom goal that wraps EXACTLY ``action_rn``.

    The reuse-not-duplicate rule: a goal qualifies when its ``conversion_actions``
    is exactly ``[action_rn]`` (membership check) and it is not REMOVED — so we
    never create a second custom goal per campaign for the same action.
    ``existing_goals`` items are dicts
    ``{resource_name, name, conversion_actions: [...], status}``.
    """
    for goal in existing_goals:
        actions = list(goal.get("conversion_actions") or [])
        if (
            len(actions) == 1
            and actions[0] == action_rn
            and goal.get("status") != "REMOVED"
        ):
            return goal.get("resource_name")
    return None


def build_zero_biddable_ops(
    customer_id: str,
    campaign_id: str,
    category_origin_rows: Sequence[Tuple[str, str]],
) -> List[CampaignConversionGoalOperation]:
    """Build ONE update op per ``(category, origin)`` row, each setting
    ``biddable=false`` with ``updateMask=['biddable']``.

    This is the step missed on 2026-08-05. A campaign-level custom goal does NOT
    disable the inherited category goals, so every category row must be zeroed in
    the SAME batch or Google warns "multiple conversion goals". Pure builder —
    asserted against fixtures in the suite (resource-name format, mask, batch
    composition).
    """
    ops: List[CampaignConversionGoalOperation] = []
    for category, origin in category_origin_rows:
        goal = CampaignConversionGoal()
        goal.resource_name = campaign_conversion_goal_rn(
            customer_id, campaign_id, category, origin
        )
        goal.biddable = False
        op = CampaignConversionGoalOperation()
        op.update = goal
        op.update_mask.CopyFrom(field_mask_pb2.FieldMask(paths=["biddable"]))
        ops.append(op)
    return ops


# ── live GAQL reads (isolated so tests can stub them) ────────────────────────


def _search(customer_id: str, query: str) -> list:
    svc = get_sdk_client().client.get_service("GoogleAdsService")
    return list(svc.search(customer_id=format_customer_id(customer_id), query=query))


def _fetch_action_name(customer_id: str, action_id: str) -> Optional[str]:
    rows = _search(
        customer_id,
        "SELECT conversion_action.name FROM conversion_action "
        f"WHERE conversion_action.id = {int(action_id)}",
    )
    for row in rows:
        return row.conversion_action.name
    return None


def _fetch_existing_custom_goals(customer_id: str) -> List[Dict[str, Any]]:
    query = (
        "SELECT custom_conversion_goal.resource_name, custom_conversion_goal.name, "
        "custom_conversion_goal.conversion_actions, custom_conversion_goal.status "
        "FROM custom_conversion_goal"
    )
    out: List[Dict[str, Any]] = []
    for row in _search(customer_id, query):
        g = row.custom_conversion_goal
        out.append(
            {
                "resource_name": g.resource_name,
                "name": g.name,
                "conversion_actions": list(g.conversion_actions),
                "status": g.status.name,
            }
        )
    return out


def _fetch_campaign_category_rows(
    customer_id: str, campaign_id: str
) -> List[Tuple[str, str]]:
    query = (
        "SELECT campaign_conversion_goal.category, campaign_conversion_goal.origin "
        "FROM campaign_conversion_goal WHERE campaign_conversion_goal.campaign = "
        f"'customers/{format_customer_id(customer_id)}/campaigns/{campaign_id}'"
    )
    rows: List[Tuple[str, str]] = []
    for row in _search(customer_id, query):
        g = row.campaign_conversion_goal
        rows.append((g.category.name, g.origin.name))
    return rows


# ── the 3-step sequence ──────────────────────────────────────────────────────


async def setup_campaign_conversion_goal(
    ctx: Any,
    customer_id: str,
    campaign_id: str,
    conversion_action_id: str,
    validate_only: bool = False,
) -> Dict[str, Any]:
    """Pin ``conversion_action_id`` as ``campaign_id``'s only biddable goal.

    Runs the proven 3-step sequence (reuse-or-create custom goal → CAMPAIGN-level
    config → zero every category row). Raises :class:`ConversionGoalSetupError`
    on any failure so the orchestrator's existing rollback removes the campaign +
    budget. Returns a summary dict::

        {
            "custom_conversion_goal": str,     # the goal resource name
            "reused_custom_goal": bool,        # True = reused, False = created
            "category_rows_cleared": int,      # rows set biddable=false
        }
    """
    customer_id = format_customer_id(customer_id)
    action_rn = conversion_action_rn(customer_id, conversion_action_id)
    try:
        # ── Step 1 — reuse-or-create the custom goal ─────────────────────
        existing = _fetch_existing_custom_goals(customer_id)
        goal_rn = pick_reusable_goal(existing, action_rn)
        reused = goal_rn is not None
        if not reused:
            name = (
                _fetch_action_name(customer_id, conversion_action_id)
                or f"Wizard goal — action {conversion_action_id}"
            )
            svc = CustomConversionGoalService()
            op = svc.create_custom_conversion_goal_operation(
                name=name, conversion_actions=[action_rn]
            )
            resp = svc.mutate_custom_conversion_goals(
                customer_id=customer_id, operations=[op], validate_only=validate_only
            )
            goal_rn = resp.results[0].resource_name if resp.results else action_rn
        await ctx.log(
            level="info",
            message=(
                f"[conv-goal] {'reused' if reused else 'created'} custom goal "
                f"{goal_rn} for conversion action {conversion_action_id}"
            ),
        )

        # ── Step 2 — point the campaign config at the custom goal (CAMPAIGN) ─
        cfg = ConversionGoalCampaignConfigService()
        cfg_op = cfg.update_conversion_goal_campaign_config_operation(
            resource_name=config_resource_name(customer_id, campaign_id),
            goal_config_level=GoalConfigLevelEnum.GoalConfigLevel.CAMPAIGN,
            custom_conversion_goal=goal_rn,
        )
        cfg.mutate_conversion_goal_campaign_configs(
            customer_id=customer_id, operations=[cfg_op], validate_only=validate_only
        )

        # ── Step 3 — zero ALL category rows in ONE batch (the missed step) ──
        rows = _fetch_campaign_category_rows(customer_id, campaign_id)
        zero_ops = build_zero_biddable_ops(customer_id, campaign_id, rows)
        if zero_ops:
            batch = CampaignConversionGoalService()
            batch.mutate_campaign_conversion_goals(
                customer_id=customer_id,
                operations=zero_ops,
                validate_only=validate_only,
            )
        await ctx.log(
            level="info",
            message=(
                f"[conv-goal] campaign {campaign_id} → custom goal only; "
                f"cleared {len(zero_ops)} category row(s)"
            ),
        )

        return {
            "custom_conversion_goal": goal_rn,
            "reused_custom_goal": reused,
            "category_rows_cleared": len(zero_ops),
        }
    except Exception as e:  # noqa: BLE001 — re-raised as a step error for rollback
        raise ConversionGoalSetupError(
            f"conversion-goal setup failed for action {conversion_action_id}: {e}"
        ) from e


def bundle_conversion_goal_action(bundle: Dict[str, Any]) -> Optional[str]:
    """Read the bundle's ``conversion_goal_action_id`` and return the numeric
    action id to pin, or ``None`` when the operator kept the account-default
    goals (the ``ACCOUNT_DEFAULT`` sentinel) or made no selection.

    The ONE place that interprets the bundle field, so every orchestrator agrees
    on the skip semantics.
    """
    raw = bundle.get("conversion_goal_action_id")
    if raw is None:
        return None
    value = str(raw).strip()
    if not value or value == ACCOUNT_DEFAULT:
        return None
    return value


async def apply_bundle_conversion_goal(
    ctx: Any,
    customer_id: str,
    campaign_id: str,
    bundle: Dict[str, Any],
    warnings: List[str],
) -> None:
    """Orchestrator entry point: run the 3-step sequence when the bundle carries
    a chosen conversion action, appending a human-readable note to ``warnings``.

    A no-op when the operator kept the account default / made no choice. Raises
    :class:`ConversionGoalSetupError` on failure so the caller's rollback fires.
    The caller sets ``failed_step = "conversion goal setup"`` before invoking so
    the error is labelled for the rollback report.
    """
    action_id = bundle_conversion_goal_action(bundle)
    if action_id is None:
        return
    result = await setup_campaign_conversion_goal(
        ctx=ctx,
        customer_id=customer_id,
        campaign_id=campaign_id,
        conversion_action_id=action_id,
    )
    warnings.append(
        "conversion goal set to custom goal "
        f"{result['custom_conversion_goal']} "
        f"({'reused existing' if result['reused_custom_goal'] else 'created'}); "
        f"{result['category_rows_cleared']} inherited category row(s) cleared"
    )
