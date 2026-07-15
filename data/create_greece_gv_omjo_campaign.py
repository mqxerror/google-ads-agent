"""Create the Greece Golden Visa — Oman+Jordan — Search — EN campaign, PAUSED.
Live-money creation; run once. Maximize Clicks ($4 cap). English only.
Keywords are Greece/EU-specific ONLY — no generic 'mixed' terms Panama uses
(prevents self-competition in the same account). Prints every resource name."""
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
FINAL_URL = "https://www.mercan.com/lp/greece-golden-visa"
suffix = os.urandom(3).hex()

# ── 1. Budget ($30/day) ─────────────────────────────────────────
bs = client.get_service("CampaignBudgetService")
bop = client.get_type("CampaignBudgetOperation")
b = bop.create
b.name = f"Greece GV OM+JO EN — {suffix}"
b.amount_micros = 30_000_000
b.delivery_method = E.BudgetDeliveryMethodEnum.STANDARD
b.explicitly_shared = False
budget_rn = bs.mutate_campaign_budgets(customer_id=CID, operations=[bop]).results[0].resource_name
print("budget:", budget_rn)

# ── 2. Campaign (PAUSED, Search, Maximize Clicks $4 cap, Search-only) ─
cs = client.get_service("CampaignService")
cop = client.get_type("CampaignOperation")
c = cop.create
c.name = "Greece Golden Visa — Oman + Jordan — Search — EN"
c.status = E.CampaignStatusEnum.PAUSED
c.advertising_channel_type = E.AdvertisingChannelTypeEnum.SEARCH
c.campaign_budget = budget_rn
c.experiment_type = E.CampaignExperimentTypeEnum.BASE
c.contains_eu_political_advertising = 3               # DOES_NOT_CONTAIN (required v23)
c.target_spend.cpc_bid_ceiling_micros = 4_000_000     # Maximize Clicks, $4.00 max CPC
c.network_settings.target_google_search = True
c.network_settings.target_search_network = False
c.network_settings.target_content_network = False
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

# ── 4. Ad groups + keywords (Greece/EU-specific ONLY) ───────────
AD_GROUPS = {
  "Greece Golden Visa": [
    ("greece golden visa","E"),("golden visa greece","E"),("greece golden visa program","P"),
    ("greece golden visa 2026","P"),("greek golden visa","P"),("golden visa greece requirements","P"),
    ("greece golden visa real estate","P"),("greece golden visa cost","P"),
    ("greece investor golden visa","P"),("golden visa europe","P")],
  "Greece Residency by Investment": [
    ("greece residency by investment","E"),("greece permanent residency","P"),
    ("greece residence permit by investment","P"),("greece residency by investment 2026","P"),
    ("greece permanent residence by investment","P"),("greece residence permit","P")],
  "Greece Property & Real Estate": [
    ("greece property investment visa","E"),("buy property in greece residency","P"),
    ("greece real estate golden visa","P"),("buy property in greece","P"),
    ("greece real estate investment","P"),("greece property for residency","P"),
    ("invest in greece real estate","P"),("greece property golden visa","P"),
    ("greece real estate residency","P"),("buy house in greece residency permit","P")],
  "EU Residency & Schengen": [
    ("eu residency by investment","E"),("european golden visa","P"),
    ("schengen residency by investment","P"),("eu residence permit by investment","P"),
    ("european residency by investment","P"),("residency in europe by investment","P"),
    ("schengen residence permit investment","P"),("eu golden visa","P"),
    ("europe residence by investment","P"),("best eu golden visa","P")],
  "Greece Investment Migration": [
    ("invest in greece residency","E"),("greece investor visa","E"),
    ("greece investment migration","P"),("greece investment visa","P"),
    ("invest in greece","P"),("greece immigration by investment","P"),
    ("greece visa by investment","P"),("investor visa greece","P"),
    ("greece investment for residency","P"),("move to greece by investment","P")],
  "Greece vs Europe (Comparison)": [
    ("cheapest golden visa in europe","P"),("best golden visa in europe","P"),
    ("cheapest eu residency","P"),("greece vs portugal golden visa","P")],
}
# Residency-accurate, policy-safe RSA (no symbols, no citizenship/passport promise,
# no unverified 'official/govt partner' claim). Same strong ad across all ad groups.
HEADLINES = ["Greece Golden Visa","Greek Residence Permit","Greece Residency Program",
  "EU Residency by Investment","Schengen Travel Access","5-Year Renewable Permit",
  "Invest in Greek Real Estate","Whole Family Included","Path to EU Residency",
  "Book a Free Consultation","Greek Property Residency","Renewable EU Residency",
  "Stable EU Base for Family","Free Expert Consultation"]
DESCS = ["Gain a 5-year renewable EU residence permit through property investment in Greece.",
  "Visa-free travel across the Schengen Area for your whole family. Book a free consultation.",
  "A renewable Greek residence permit, not citizenship. Clear, honest guidance from Mercan.",
  "Invest in Greek real estate and secure residency for your family in the EU."]
for h in HEADLINES: assert len(h) <= 30, (h, len(h))
for d in DESCS: assert len(d) <= 90, (d, len(d))

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
    # RSA (per-ad-group try/except so one policy issue can't abort the build)
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
    try:
        aas.mutate_ad_group_ads(customer_id=CID, operations=[adop])
        print(f"ad group [{ag_name}]: {len(kws)} kw + 1 RSA")
    except Exception as e:
        print(f"ad group [{ag_name}]: {len(kws)} kw + RSA FAILED -> {str(e)[:120]}")

print("\nDONE (PAUSED). campaign_id =", campaign_id)
open("/tmp/greece_gv_omjo_campaign_id.txt", "w").write(campaign_id)
