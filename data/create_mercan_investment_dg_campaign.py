"""Create 'Mercan Investment — ME — Demand Gen — Corporate' PAUSED on Mercan
Main (7178239091) via the create_demand_gen_campaign orchestrator.

A B2C corporate-brand Demand Gen campaign (Greece + Panama residency-by-
investment) wearing Mercan corporate creative — deliberately brand-level so it
does not collide with the product-specific selling campaigns.

Creative set (6 images) was generated up-front via the app's Higgsfield Studio
pipeline (data/ad_assets/<uuid>.png, registered ad_assets rows). The logo is an
existing square Google image asset in the account. Geo TARGET = JO/OM/AE/SA
countries; geo EXCLUDE = the Dubai emirate (Province 9041083) + Dubai city
(1000013). Language = English. Channels = tool default (Gmail OFF, Display/
Discover/YouTube ON). Bidding = MaximizeConversions (no tCPA).

Starts PAUSED (orchestrator default) — Wassim reviews before enabling. Run once;
re-running is guarded against a duplicate by exact campaign name.
"""
import asyncio
import json
import sys

sys.path.insert(0, "/Users/mqxerrormac16/Documents/LangarAI/google-ads-agent/backend")

from google_ads.sdk_client import GoogleAdsSdkClient, get_sdk_client, set_sdk_client
from app.config import settings


def ensure_sdk():
    try:
        get_sdk_client()
    except Exception:
        cl = GoogleAdsSdkClient()
        cl._client = None
        from google.ads.googleads.client import GoogleAdsClient
        cl._client = GoogleAdsClient.load_from_dict({
            "developer_token": settings.GOOGLE_ADS_DEVELOPER_TOKEN,
            "client_id": settings.GOOGLE_ADS_CLIENT_ID,
            "client_secret": settings.GOOGLE_ADS_CLIENT_SECRET,
            "refresh_token": settings.GOOGLE_ADS_REFRESH_TOKEN,
            "login_customer_id": settings.GOOGLE_ADS_LOGIN_CUSTOMER_ID,
            "use_proto_plus": True,
        })
        set_sdk_client(cl)


CID = "7178239091"
NAME = "Mercan Investment — ME — Demand Gen — Corporate"

# ── Copy (hard rules: no ~ | + symbols, no prices, no urgency/discount, NO
#    citizenship/passport promises, no third-party brands). ────────────────
# Demand Gen allows max 5 headlines; the brief supplied 6, all ≤30 chars.
# Dropped "Invest in Your Global Future" (the softest/most generic) to keep the
# 5 most concrete, credible claims: brand, category, both named programs, and
# the founding-year trust signal.
HEADLINES = [
    "Mercan Investment",
    "Global Residency Programs",
    "Greece Golden Visa Program",
    "Panama Investor Residency",
    "Trusted Since 1989",
]
DESCRIPTIONS = [
    "Explore government regulated residency by investment programs with a global firm.",
    "Greece and Panama residency programs for international investors. Speak to our team.",
    "A global investment migration firm with three decades of experience.",
]
BUSINESS_NAME = "Mercan Investment"
FINAL_URL = "https://www.mercan.com/"

# ── Creative refs ─────────────────────────────────────────────────────────
LOGO_ASSET_ID = "101657318467"  # 'Logo Mercan Group_1:1.png', 2481x2481, exact 1:1
LANDSCAPE_UUIDS = [
    "5284b32f-7deb-4456-92c5-458deebcddc4",  # athens golden hour
    "addcd16c-08f5-4d69-9012-1b472980e3a7",  # panama city dusk
    "bfa3ae8d-3fc3-4c1e-af7c-52c019efca22",  # navy/gold abstract
]
SQUARE_UUIDS = [
    "eced5c54-a9b1-4865-906f-df2c5cd34f8c",  # athens
    "f8a94d4f-4873-4fe7-a481-07c3d919bd02",  # panama
    "fcb72a9d-9992-4298-8833-17ed2590db99",  # navy/gold abstract
]

# ── Targeting (all verified against the live account via GeoTargetConstant
#    suggest — NOT guessed). ────────────────────────────────────────────────
LOCATION_IDS = ["2400", "2512", "2784", "2682"]  # Jordan, Oman, UAE, Saudi Arabia
EXCLUDED_LOCATION_IDS = ["9041083", "1000013"]    # Dubai emirate (Province) + Dubai city
LANGUAGE_IDS = ["1000"]                            # English
BUDGET_MICROS = 30_000_000                         # $30/day placeholder


def _validate_copy():
    for h in HEADLINES:
        assert len(h) <= 30, (h, len(h))
    for d in DESCRIPTIONS:
        assert len(d) <= 90, (d, len(d))
    assert len(BUSINESS_NAME) <= 25, (BUSINESS_NAME, len(BUSINESS_NAME))
    assert 1 <= len(HEADLINES) <= 5
    assert 1 <= len(DESCRIPTIONS) <= 5
    banned = ("~", "|", "+")
    for txt in HEADLINES + DESCRIPTIONS + [BUSINESS_NAME]:
        for b in banned:
            assert b not in txt, f"banned symbol {b!r} in {txt!r}"


def _already_exists() -> bool:
    ga = get_sdk_client().client.get_service("GoogleAdsService")
    q = (
        "SELECT campaign.id, campaign.name, campaign.status "
        "FROM campaign WHERE campaign.name = "
        f"'{NAME}' AND campaign.status != 'REMOVED'"
    )
    rows = list(ga.search(customer_id=CID, query=q))
    for r in rows:
        print(f"GUARD: campaign already exists id={r.campaign.id} "
              f"status={r.campaign.status.name} — not creating a duplicate.")
    return bool(rows)


async def main():
    ensure_sdk()
    _validate_copy()

    if _already_exists():
        return

    from google_ads.services.campaign.demand_gen_orchestrator import (
        ApiCtx,
        DemandGenOrchestrator,
    )

    bundle = {
        "name": NAME,
        "budget_micros": BUDGET_MICROS,
        "final_urls": [FINAL_URL],
        "business_name": BUSINESS_NAME,
        "headlines": HEADLINES,
        "descriptions": DESCRIPTIONS,
        "logos": [LOGO_ASSET_ID],
        "marketing_images": {
            "landscape": LANDSCAPE_UUIDS,
            "square": SQUARE_UUIDS,
            "portrait": [],
            "tall_portrait": [],
        },
        "location_ids": LOCATION_IDS,
        "excluded_location_ids": EXCLUDED_LOCATION_IDS,
        "language_ids": LANGUAGE_IDS,
        # channels: omit → tool defaults (Gmail OFF, Display/Discover/YouTube ON)
        # bidding: MaximizeConversions, no target_cpa_micros
    }

    orch = DemandGenOrchestrator()
    result = await orch.create_demand_gen_campaign(
        ctx=ApiCtx(), customer_id=CID, bundle=bundle,
    )
    print("RESULT_JSON_START")
    print(json.dumps(result, indent=2, default=str))
    print("RESULT_JSON_END")
    print(f"\nDONE (PAUSED). campaign_id = {result.get('campaign_id')}")


if __name__ == "__main__":
    asyncio.run(main())
