"""Create the Panama QIP — Oman+Jordan — Search — EN campaign, PAUSED.
Live-money creation; run once. Prints every resource name created."""
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

# ── 1. Budget ($30/day) — reuse the one already created ─────────
budget_rn = "customers/7178239091/campaignBudgets/15704325061"
print("budget (reused):", budget_rn)

# ── 2. Campaign (PAUSED, Search, Max Conversions, Search-only) ───
cs = client.get_service("CampaignService")
cop = client.get_type("CampaignOperation")
c = cop.create
c.name = "Panama QIP — Oman + Jordan — Search — EN"
c.status = E.CampaignStatusEnum.PAUSED
c.advertising_channel_type = E.AdvertisingChannelTypeEnum.SEARCH
c.campaign_budget = budget_rn
c.experiment_type = E.CampaignExperimentTypeEnum.BASE
c.contains_eu_political_advertising = 3               # DOES_NOT_CONTAIN (required in v23)
mc = client.get_type("MaximizeConversions")           # pure Max Conversions, no tCPA
c.maximize_conversions = mc
c.network_settings.target_google_search = True
c.network_settings.target_search_network = False      # Search Partners OFF
c.network_settings.target_content_network = False     # Display OFF
c.network_settings.target_partner_search_network = False
campaign_rn = cs.mutate_campaigns(customer_id=CID, operations=[cop]).results[0].resource_name
campaign_id = campaign_rn.split("/")[-1]
print("campaign:", campaign_rn, "| id:", campaign_id)

# ── 3. Geo (Oman 2512, Jordan 2400) + Language (English 1000) ────
ccs = client.get_service("CampaignCriterionService")
crit_ops = []
for geo_id in ("2512", "2400"):
    op = client.get_type("CampaignCriterionOperation")
    op.create.campaign = campaign_rn
    op.create.location.geo_target_constant = f"geoTargetConstants/{geo_id}"
    crit_ops.append(op)
lop = client.get_type("CampaignCriterionOperation")
lop.create.campaign = campaign_rn
lop.create.language.language_constant = "languageConstants/1000"
crit_ops.append(lop)
ccs.mutate_campaign_criteria(customer_id=CID, operations=crit_ops)
print("geo+language: Oman + Jordan + English set")

# ── 4. Ad groups + keywords ─────────────────────────────────────
AD_GROUPS = {
  "Golden Visa & Investor Visa": [
    ("golden visa","P"),("golden visa program","P"),("investment visa","P"),
    ("investor visa","P"),("golden visa by investment","P"),
    ("property investment visa","P"),("golden visa consultants","P"),
    ("panama golden visa","E")],
  "Residency by Investment": [
    ("panama residency by investment","E"),("permanent residency by investment","P"),
    ("residence by investment","P"),("residency by investment programs","P"),
    ("second residency","P"),("real estate residency","P"),
    ("residency through investment","P"),("panama residency","E")],
  "Citizenship & Second Passport": [
    ("citizenship by investment","P"),("second passport","P"),("second citizenship","P"),
    ("passport by investment","P"),("get a second passport","P"),
    ("panama citizenship by investment","E"),("panama citizenship","E"),
    ("panama passport by investment","E"),("panama friendly nations visa","E")],
}
HEADLINES = ["Panama Golden Visa","Residency in ~30 Days","Save $200K Before Oct 2026",
  "Official Govt Partner","$300K Investment","Path to Citizenship","Family Included",
  "142-Country Passport","Free Consultation","Your Family's Plan B",
  "Territorial Tax Benefits","Fastest Residency Program"]
DESCS = ["Panama permanent residency in ~30 days via a $300K investment. Family included.",
  "Official Government of Panama partner. Book a free, confidential consultation.",
  "Price rises to $500K in Oct 2026 - invest at $300K now. Citizenship path in 5 yrs.",
  "Passport with visa-free access to 142 countries. Territorial tax, dollar economy."]
# length safety
for h in HEADLINES: assert len(h) <= 30, h
for d in DESCS: assert len(d) <= 90, d

ags = client.get_service("AdGroupService")
agcs = client.get_service("AdGroupCriterionService")
aas = client.get_service("AdGroupAdService")
for ag_name, kws in AD_GROUPS.items():
    agop = client.get_type("AdGroupOperation")
    ag = agop.create
    ag.name = ag_name
    ag.campaign = campaign_rn
    ag.status = E.AdGroupStatusEnum.ENABLED
    ag.type_ = E.AdGroupTypeEnum.SEARCH_STANDARD
    ag_rn = ags.mutate_ad_groups(customer_id=CID, operations=[agop]).results[0].resource_name
    # keywords
    kops = []
    for text, mt in kws:
        kop = client.get_type("AdGroupCriterionOperation")
        k = kop.create
        k.ad_group = ag_rn
        k.status = E.AdGroupCriterionStatusEnum.ENABLED
        k.keyword.text = text
        k.keyword.match_type = E.KeywordMatchTypeEnum.EXACT if mt == "E" else E.KeywordMatchTypeEnum.PHRASE
        kops.append(kop)
    agcs.mutate_ad_group_criteria(customer_id=CID, operations=kops)
    # RSA
    adop = client.get_type("AdGroupAdOperation")
    ada = adop.create
    ada.ad_group = ag_rn
    ada.status = E.AdGroupAdStatusEnum.ENABLED
    ada.ad.final_urls.append(FINAL_URL)
    for h in HEADLINES:
        ai = client.get_type("AdTextAsset"); ai.text = h
        ada.ad.responsive_search_ad.headlines.append(ai)
    for d in DESCS:
        ai = client.get_type("AdTextAsset"); ai.text = d
        ada.ad.responsive_search_ad.descriptions.append(ai)
    aas.mutate_ad_group_ads(customer_id=CID, operations=[adop])
    print(f"ad group [{ag_name}]: {len(kws)} keywords + 1 RSA")

print("\nDONE (PAUSED). campaign_id =", campaign_id)
open("/tmp/panama_omjo_campaign_id.txt","w").write(campaign_id)
