"""Create 'Panama QIP — US — Search — v2' PAUSED on Mercan Main (7178239091).
Clean rebuild: copies ONLY v1's working keywords + sane pre-drift bids; fresh
LP2-grounded RSAs; lifestyle + cross-campaign negatives from day one.
v1 (23871240619) is untouched here — cutover (enable v2 + pause v1) is a
separate, explicitly-approved step. Run once."""
import os, sys
sys.path.insert(0, "/Users/mqxerrormac16/Documents/LangarAI/google-ads-agent/backend")
from google_ads.sdk_client import GoogleAdsSdkClient, get_sdk_client, set_sdk_client
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
E = client.enums
FINAL_URL = "https://www.mercan.com/lp/panama-qualified-investor-program"
suffix = os.urandom(3).hex()

# ── 1. Budget ($150/day, own budget — never share with v1) ─────────
bs = client.get_service("CampaignBudgetService")
bop = client.get_type("CampaignBudgetOperation")
b = bop.create
b.name = f"Panama QIP US v2 — {suffix}"
b.amount_micros = 150_000_000
b.delivery_method = E.BudgetDeliveryMethodEnum.STANDARD
b.explicitly_shared = False
budget_rn = bs.mutate_campaign_budgets(customer_id=CID, operations=[bop]).results[0].resource_name
print("budget:", budget_rn)

# ── 2. Campaign (PAUSED, Search-only, Manual CPC) ──────────────────
cs = client.get_service("CampaignService")
cop = client.get_type("CampaignOperation")
c = cop.create
c.name = "Panama QIP — US — Search — v2"
c.status = E.CampaignStatusEnum.PAUSED
c.advertising_channel_type = E.AdvertisingChannelTypeEnum.SEARCH
c.campaign_budget = budget_rn
c.experiment_type = E.CampaignExperimentTypeEnum.BASE
c.contains_eu_political_advertising = 3            # required in v23
c.manual_cpc.enhanced_cpc_enabled = False          # pure Manual CPC, like v1
c.network_settings.target_google_search = True
c.network_settings.target_search_network = False
c.network_settings.target_content_network = False
c.network_settings.target_partner_search_network = False
campaign_rn = cs.mutate_campaigns(customer_id=CID, operations=[cop]).results[0].resource_name
campaign_id = campaign_rn.split("/")[-1]
print("campaign:", campaign_rn, "| id:", campaign_id)

# ── 3. Geo US (2840) + English (1000) + campaign negatives ─────────
ccs = client.get_service("CampaignCriterionService")
ops = []
gop = client.get_type("CampaignCriterionOperation")
gop.create.campaign = campaign_rn
gop.create.location.geo_target_constant = "geoTargetConstants/2840"
ops.append(gop)
lop = client.get_type("CampaignCriterionOperation")
lop.create.campaign = campaign_rn
lop.create.language.language_constant = "languageConstants/1000"
ops.append(lop)
NEGATIVES = [
    # lifestyle / non-investor (agreed Jul 8, never executed on v1)
    "move to panama", "moving to panama", "live in panama", "living in panama",
    "retiring to panama", "nomad visa", "reforestation",
    # cross-campaign wall (Greece/EU runs its own campaigns)
    "greece", "greek", "europe", "european", "eu", "schengen", "portugal",
    # off-offer
    "passport", "best place to buy",
]
for t in NEGATIVES:
    op = client.get_type("CampaignCriterionOperation")
    op.create.campaign = campaign_rn
    op.create.negative = True
    op.create.keyword.text = t
    op.create.keyword.match_type = E.KeywordMatchTypeEnum.BROAD
    ops.append(op)
ccs.mutate_campaign_criteria(customer_id=CID, operations=ops)
print(f"geo US + English + {len(NEGATIVES)} negatives set")

# ── 4. Ad groups + keywords with pre-drift bids ────────────────────
# Observed 30d avg CPCs: residency core ~$2.45; investor/program terms ~$5.86.
# Bids = modest headroom over observed, NOT the drifted $4.38 blend.
AD_GROUPS = {
  "Residency Core (Converters)": {
    "cpc_micros": 3_000_000,   # $3.00
    "kws": [("residency visa panama","P"),("panama residency for americans","P")],
  },
  "Investor Program (High Intent)": {
    "cpc_micros": 6_500_000,   # $6.50
    "kws": [("panama qualified investor program","E"),
            ("panama residency by investment","P"),
            ("panama permanent residency by investment","P"),
            ("panama investment visa","P")],
  },
}
# LP2-grounded copy (page: "Secure Panama Residency Through a $300,000
# Investment, in About 30 Days" + Plan B hook + email Investor Guide offer).
# Symbol-clean (no ~ | + etc.), no citizenship/passport promises, no tax claims.
HEADLINES = ["Panama Residency Program","Secure Panama Residency",
  "Residency in About 30 Days","$300K Investment Program",
  "Panama Residency for Americans","Your Family's Plan B",
  "No Minimum Stay Required","Family Included","Free Investor Guide",
  "Book a Free Consultation","Govt-Approved Investment","Qualified Investor Program"]
DESCS = [
  "Panama residency through a $300,000 government-approved investment, in about 30 days.",
  "Not ready to talk yet? Get the free Panama Investor Guide by email. No obligation.",
  "Your family's Plan B: residency in a stable, US dollar economy. No minimum stay.",
  "Guided end to end by Mercan's investment migration team. Free, confidential consultation.",
]
for h in HEADLINES: assert len(h) <= 30, (h, len(h))
for d in DESCS: assert len(d) <= 90, (d, len(d))

ags = client.get_service("AdGroupService")
agcs = client.get_service("AdGroupCriterionService")
aas = client.get_service("AdGroupAdService")
for ag_name, spec in AD_GROUPS.items():
    agop = client.get_type("AdGroupOperation")
    ag = agop.create
    ag.name = ag_name
    ag.campaign = campaign_rn
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
        k.keyword.match_type = E.KeywordMatchTypeEnum.EXACT if mt == "E" else E.KeywordMatchTypeEnum.PHRASE
        kops.append(kop)
    agcs.mutate_ad_group_criteria(customer_id=CID, operations=kops)
    adop = client.get_type("AdGroupAdOperation")
    ada = adop.create
    ada.ad_group = ag_rn
    ada.status = E.AdGroupAdStatusEnum.ENABLED
    ada.ad.final_urls.append(FINAL_URL)
    for h in HEADLINES:
        t = client.get_type("AdTextAsset"); t.text = h
        ada.ad.responsive_search_ad.headlines.append(t)
    for d in DESCS:
        t = client.get_type("AdTextAsset"); t.text = d
        ada.ad.responsive_search_ad.descriptions.append(t)
    try:
        aas.mutate_ad_group_ads(customer_id=CID, operations=[adop])
        print(f"ad group [{ag_name}]: {len(spec['kws'])} kw @ ${spec['cpc_micros']/1e6:.2f} + 1 RSA")
    except Exception as e:
        print(f"ad group [{ag_name}]: kw ok, RSA FAILED -> {str(e)[:120]}")

print("\nDONE (PAUSED). v2 campaign_id =", campaign_id)
open("/tmp/panama_us_v2_campaign_id.txt", "w").write(campaign_id)
