"""LIVE expansion of 'Panama QIP — US — Search — v2' (24036236041 / 7178239091).

Approved by Wassim 2026-07-15 ("build it"). Scope = EXACTLY the approved decision
set (research/panama-us-keyword-angles.md §2-3 + data/panama-us-angles-kwp.json).

Maps the 5-group >=5K/mo plan onto the live v2 campaign:
  - AG "Investor Program (High Intent)"  (existing, KEEP $6.50)  == plan AG1 QIP Program
        + re-add `panama golden visa` (PHRASE) with BRIDGE framing in this group.
  - AG "Residency Core (Converters)"     (existing, RAISE $3.00 -> $4.50) == plan AG2 Residency Core
        + expand angle-pure residency-core phrase keywords.
  - AG "Friendly Nations Visa"           (NEW $1.50)  == plan AG3 (honest route-comparison RSA)
  - AG "Property Investors"              (NEW $2.50)  == plan AG4 (Santa Maria bridge)
  - AG "RBI Category"                    (NEW $5.50)  == plan AG5

Campaign negatives: ADD retirement + EB-5 + Florida walls; REMOVE `best place to buy`
(unblocks AG4 `best place to buy real estate in panama` 70/mo); KEEP `passport`.

RERUNNABLE-SAFE: checks existing ad-group names + existing keyword texts + existing
negatives before mutating; skips duplicates. RSA creation per-group try/except so one
policy block never aborts the build. NO settings touched except the specified
negatives + the Residency Core bid update.

Run:  cd backend && .venv/bin/python ../data/expand_panama_us_v2.py
"""
import os, sys
sys.path.insert(0, "/Users/mqxerrormac16/Documents/LangarAI/google-ads-agent/backend")
from google_ads.sdk_client import GoogleAdsSdkClient, get_sdk_client, set_sdk_client
from google.api_core import protobuf_helpers
from app.config import settings


def ensure():
    try:
        get_sdk_client()
    except Exception:
        cl = GoogleAdsSdkClient(); cl._client = None
        from google.ads.googleads.client import GoogleAdsClient
        cl._client = GoogleAdsClient.load_from_dict({
            "developer_token": settings.GOOGLE_ADS_DEVELOPER_TOKEN,
            "client_id": settings.GOOGLE_ADS_CLIENT_ID,
            "client_secret": settings.GOOGLE_ADS_CLIENT_SECRET,
            "refresh_token": settings.GOOGLE_ADS_REFRESH_TOKEN,
            "login_customer_id": settings.GOOGLE_ADS_LOGIN_CUSTOMER_ID,
            "use_proto_plus": True})
        set_sdk_client(cl)


ensure()
client = get_sdk_client().client
CID = "7178239091"
CAMP_ID = "24036236041"
CAMP_RN = f"customers/{CID}/campaigns/{CAMP_ID}"
E = client.enums
FINAL_URL = "https://www.mercan.com/lp/panama-qualified-investor-program"
ga = client.get_service("GoogleAdsService")
ags = client.get_service("AdGroupService")
agcs = client.get_service("AdGroupCriterionService")
aas = client.get_service("AdGroupAdService")
ccs = client.get_service("CampaignCriterionService")


def phrase_or_exact(mt):
    return E.KeywordMatchTypeEnum.EXACT if mt == "E" else E.KeywordMatchTypeEnum.PHRASE


# ── RSA asserts (HARD RULE — validate BEFORE any mutation) ──────────
def assert_rsa(headlines, descriptions, label):
    PROHIBITED = set("~|+*^=<>{}[]@#$%")  # symbol policy class; $ used in copy though -> allow $ explicitly
    PROHIBITED.discard("$")               # "$300K" is allowed factual copy
    for h in headlines:
        assert len(h) <= 30, f"[{label}] headline >30: {h!r} ({len(h)})"
        bad = PROHIBITED & set(h)
        assert not bad, f"[{label}] headline has prohibited symbol {bad}: {h!r}"
    for d in descriptions:
        assert len(d) <= 90, f"[{label}] desc >90: {d!r} ({len(d)})"
        bad = PROHIBITED & set(d)
        assert not bad, f"[{label}] desc has prohibited symbol {bad}: {d!r}"


# ════════════════════════════════════════════════════════════════════
#  DESIRED STATE
# ════════════════════════════════════════════════════════════════════
# Keywords to ADD to EXISTING ad groups (by ad-group name). Only new ones
# get inserted; duplicates (already-live) are skipped.
ADD_TO_EXISTING = {
    "Investor Program (High Intent)": {
        # Decision #1: re-add panama golden visa (PHRASE) as QIP bridge.
        "kws": [("panama golden visa", "P")],
    },
    "Residency Core (Converters)": {
        # Plan AG2 residency-core expansion (PHRASE). Existing 2 kws stay.
        "kws": [
            ("panama residency", "P"),
            ("panama residency requirements", "P"),
            ("panama permanent residency", "P"),
            ("panama residency visa", "P"),
            ("how to get residency in panama", "P"),
            ("panama residency program", "P"),
        ],
    },
}

# Ad-group bid updates (existing groups).
BID_UPDATES = {
    "Residency Core (Converters)": 4_500_000,  # $3.00 -> $4.50 (decision #2)
}

# NEW ad groups (created only if name not already present).
# Start CPCs = plan §3 KWP-derived starting bids.
NEW_AD_GROUPS = {
    "Friendly Nations Visa": {
        "cpc_micros": 1_500_000,  # $1.50
        "kws": [
            ("panama friendly nations visa", "P"),
            ("friendly nations visa", "P"),
            ("panama friendly nations visa requirements", "P"),
            ("friendly nations visa panama requirements", "P"),
        ],
        # HARD: FNV != QIP. Honest route-comparison bridge; never claim FNV = QIP.
        "headlines": [
            "Compare Panama Residency",
            "Find the Right Panama Route",
            "Panama Residency Routes",
            "Fastest Route in About 30 Days",
            "Qualified Investor Program",
            "$300K Govt-Approved Route",
            "Which Panama Visa Fits You",
            "Family Included",
            "No Minimum Stay Required",
            "Free Route-Comparison Guide",
            "Book a Free Consultation",
            "US Dollar Economy",
        ],
        "descriptions": [
            "Compare Panama residency routes and find the one that fits your goals.",
            "The Qualified Investor Program grants residency in about 30 days. See if it fits.",
            "Not sure which route? Get our free Panama route-comparison guide by email.",
            "Guided by Mercan's investment migration team. Free, confidential consultation.",
        ],
    },
    "Property Investors": {
        "cpc_micros": 2_500_000,  # $2.50
        "kws": [
            ("buy condo in panama", "P"),
            ("panama real estate for expats", "P"),
            ("buy property in panama", "P"),
            ("buy real estate in panama", "P"),
            ("invest in panama real estate", "P"),
            ("panama real estate investment", "P"),
            ("buy apartment in panama", "P"),
            ("best place to buy real estate in panama", "P"),
            ("santa maria panama real estate", "P"),
            ("panama beachfront property for sale", "P"),
            ("panama investment property", "P"),
        ],
        # Santa Maria = our OWN project (allowed). Bridge property -> residency.
        "headlines": [
            "Own Real Estate in Panama",
            "Property With Residency",
            "Santa Maria Residences",
            "Invest and Gain Residency",
            "$300K Govt-Approved Investment",
            "Residency in About 30 Days",
            "Family Included",
            "No Minimum Stay Required",
            "Panama Property Investment",
            "US Dollar Economy",
            "Free Investor Guide",
            "Book a Free Consultation",
        ],
        "descriptions": [
            "Own property in Panama and gain residency through a $300,000 investment.",
            "Santa Maria Residences: a government-approved route to Panama residency.",
            "Residency in about 30 days. Family included. No minimum stay required.",
            "Get the free Panama Investor Guide by email, or book a free consultation.",
        ],
    },
    "RBI Category": {
        "cpc_micros": 5_500_000,  # $5.50
        "kws": [
            ("residency by investment programs", "P"),
            ("residence by investment", "P"),
            ("permanent residency by investment", "P"),
            ("residency by investment countries", "P"),
            ("cheapest residency by investment", "P"),
        ],
        "headlines": [
            "Residency by Investment",
            "Panama Residency Route",
            "$300K Govt-Approved Route",
            "Residency in About 30 Days",
            "No Minimum Stay Required",
            "Qualified Investor Program",
            "Family Included",
            "US Dollar Economy",
            "A Stable Plan B",
            "Free Investor Guide",
            "Book a Free Consultation",
            "Guided End to End",
        ],
        "descriptions": [
            "Panama residency by investment: a $300,000 government-approved route.",
            "Gain residency in about 30 days. Family included. No minimum stay.",
            "Compare residency-by-investment routes. Get the free guide by email.",
            "Guided by Mercan's investment migration team. Free, confidential consultation.",
        ],
    },
}

# Campaign negatives to ADD (plan §3). BROAD match. Skip if already present.
NEG_ADD = [
    # Retirement wall (v2 only has "retiring to panama")
    "pensionado", "retirement", "retire", "retiree",
    # EB-5 wall (for RBI / investment-visa terms)
    "eb5", "eb-5", "green card", "us visa", "usa visa", "visa for usa",
    # Florida wall (protect property terms)
    "panama city beach", "panama city fl", "florida", "fl", "pcb",
    "rent", "rental", "rentals", "foreclosure", "cheap",
]
# Campaign negatives to REMOVE: `best place to buy` (unblocks AG4 buyer term).
# KEEP `passport` (decision + hard rule).
NEG_REMOVE = ["best place to buy"]


# ════════════════════════════════════════════════════════════════════
#  LOAD CURRENT LIVE STATE (for idempotency)
# ════════════════════════════════════════════════════════════════════
def load_ad_groups():
    """name -> {id, rn, cpc}"""
    out = {}
    q = f"""SELECT ad_group.id, ad_group.name, ad_group.cpc_bid_micros
            FROM ad_group WHERE campaign.id = {CAMP_ID}"""
    for r in ga.search(customer_id=CID, query=q):
        out[r.ad_group.name] = {
            "id": r.ad_group.id,
            "rn": f"customers/{CID}/adGroups/{r.ad_group.id}",
            "cpc": r.ad_group.cpc_bid_micros,
        }
    return out


def load_keywords_by_group():
    """ad_group_name -> set of keyword texts (positive kws only)"""
    out = {}
    q = f"""SELECT ad_group.name, ad_group_criterion.keyword.text
            FROM ad_group_criterion
            WHERE campaign.id = {CAMP_ID} AND ad_group_criterion.type = KEYWORD
            AND ad_group_criterion.negative = FALSE"""
    for r in ga.search(customer_id=CID, query=q):
        out.setdefault(r.ad_group.name, set()).add(r.ad_group_criterion.keyword.text.lower())
    return out


def load_negatives():
    """text.lower() -> resource_name (campaign-level negative keywords)"""
    out = {}
    q = f"""SELECT campaign_criterion.resource_name, campaign_criterion.keyword.text
            FROM campaign_criterion
            WHERE campaign.id = {CAMP_ID} AND campaign_criterion.negative = TRUE
            AND campaign_criterion.type = KEYWORD"""
    for r in ga.search(customer_id=CID, query=q):
        out[r.campaign_criterion.keyword.text.lower()] = r.campaign_criterion.resource_name
    return out


ad_groups = load_ad_groups()
kws_by_group = load_keywords_by_group()
neg_map = load_negatives()
print("LIVE BEFORE:")
print("  ad groups:", list(ad_groups.keys()))
print("  negatives:", len(neg_map))


# ════════════════════════════════════════════════════════════════════
#  1. CAMPAIGN NEGATIVES — add walls, remove `best place to buy`
# ════════════════════════════════════════════════════════════════════
neg_ops = []
added_negs = []
for t in NEG_ADD:
    if t.lower() in neg_map:
        continue
    op = client.get_type("CampaignCriterionOperation")
    op.create.campaign = CAMP_RN
    op.create.negative = True
    op.create.keyword.text = t
    op.create.keyword.match_type = E.KeywordMatchTypeEnum.BROAD
    neg_ops.append(op)
    added_negs.append(t)
removed_negs = []
for t in NEG_REMOVE:
    rn = neg_map.get(t.lower())
    if rn:
        op = client.get_type("CampaignCriterionOperation")
        op.remove = rn
        neg_ops.append(op)
        removed_negs.append(t)
if neg_ops:
    ccs.mutate_campaign_criteria(customer_id=CID, operations=neg_ops)
print(f"\n[negatives] added {len(added_negs)}: {added_negs}")
print(f"[negatives] removed {len(removed_negs)}: {removed_negs}")


# ════════════════════════════════════════════════════════════════════
#  2. BID UPDATES on existing ad groups
# ════════════════════════════════════════════════════════════════════
for name, new_bid in BID_UPDATES.items():
    if name not in ad_groups:
        print(f"[bid] WARN ad group not found: {name}")
        continue
    if ad_groups[name]["cpc"] == new_bid:
        print(f"[bid] {name} already ${new_bid/1e6:.2f} — skip")
        continue
    agop = client.get_type("AdGroupOperation")
    ag = agop.update
    ag.resource_name = ad_groups[name]["rn"]
    ag.cpc_bid_micros = new_bid
    agop.update_mask.CopyFrom(protobuf_helpers.field_mask(None, ag._pb))
    ags.mutate_ad_groups(customer_id=CID, operations=[agop])
    print(f"[bid] {name}: ${ad_groups[name]['cpc']/1e6:.2f} -> ${new_bid/1e6:.2f}")


# ════════════════════════════════════════════════════════════════════
#  3. ADD keywords to EXISTING ad groups (skip duplicates)
# ════════════════════════════════════════════════════════════════════
for name, spec in ADD_TO_EXISTING.items():
    if name not in ad_groups:
        print(f"[kw-existing] WARN ad group not found: {name}")
        continue
    ag_rn = ad_groups[name]["rn"]
    have = kws_by_group.get(name, set())
    kops = []
    added = []
    for text, mt in spec["kws"]:
        if text.lower() in have:
            continue
        kop = client.get_type("AdGroupCriterionOperation")
        k = kop.create
        k.ad_group = ag_rn
        k.status = E.AdGroupCriterionStatusEnum.ENABLED
        k.keyword.text = text
        k.keyword.match_type = phrase_or_exact(mt)
        kops.append(kop)
        added.append(f"{text} [{mt}]")
    if kops:
        agcs.mutate_ad_group_criteria(customer_id=CID, operations=kops)
    print(f"[kw-existing] {name}: added {len(added)} -> {added}")


# ════════════════════════════════════════════════════════════════════
#  4. CREATE new ad groups (+ keywords + one RSA each, per-group try/except)
# ════════════════════════════════════════════════════════════════════
for name, spec in NEW_AD_GROUPS.items():
    if name in ad_groups:
        print(f"[new-ag] {name} already exists — skip create.")
        # Still ensure RSA if the group somehow has none? Keep minimal: skip.
        continue
    # assert RSA copy BEFORE any mutation for this group
    assert_rsa(spec["headlines"], spec["descriptions"], name)

    agop = client.get_type("AdGroupOperation")
    ag = agop.create
    ag.name = name
    ag.campaign = CAMP_RN
    ag.status = E.AdGroupStatusEnum.ENABLED
    ag.type_ = E.AdGroupTypeEnum.SEARCH_STANDARD
    ag.cpc_bid_micros = spec["cpc_micros"]
    ag_rn = ags.mutate_ad_groups(customer_id=CID, operations=[agop]).results[0].resource_name

    kops = []
    for text, mt in spec["kws"]:
        kop = client.get_type("AdGroupCriterionOperation")
        k = kop.create
        k.ad_group = ag_rn
        k.status = E.AdGroupCriterionStatusEnum.ENABLED
        k.keyword.text = text
        k.keyword.match_type = phrase_or_exact(mt)
        kops.append(kop)
    agcs.mutate_ad_group_criteria(customer_id=CID, operations=kops)

    rsa_status = "ok"
    try:
        adop = client.get_type("AdGroupAdOperation")
        ada = adop.create
        ada.ad_group = ag_rn
        ada.status = E.AdGroupAdStatusEnum.ENABLED
        ada.ad.final_urls.append(FINAL_URL)
        for h in spec["headlines"]:
            t = client.get_type("AdTextAsset"); t.text = h
            ada.ad.responsive_search_ad.headlines.append(t)
        for d in spec["descriptions"]:
            t = client.get_type("AdTextAsset"); t.text = d
            ada.ad.responsive_search_ad.descriptions.append(t)
        aas.mutate_ad_group_ads(customer_id=CID, operations=[adop])
    except Exception as e:
        rsa_status = f"BLOCKED -> {str(e)[:200]}"
    print(f"[new-ag] {name}: {len(spec['kws'])} kw @ ${spec['cpc_micros']/1e6:.2f} + RSA {rsa_status}")

print("\nDONE. Run inspect to verify.")
