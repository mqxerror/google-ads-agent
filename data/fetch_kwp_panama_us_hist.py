"""Panama QIP — US angles, Step A2: GenerateKeywordHistoricalMetrics (READ-ONLY).
Canonical US/EN volumes + bid estimates for the final candidate set.
Writes data/panama-us-angles-kwp-hist-raw.json.
"""
from __future__ import annotations

import json, sys, time

sys.path.insert(0, "/Users/mqxerrormac16/Documents/LangarAI/google-ads-agent/backend")
from google.ads.googleads.client import GoogleAdsClient
from google.ads.googleads.errors import GoogleAdsException
from app.config import settings

CUSTOMER_ID = "7178239091"
GEO_US = "geoTargetConstants/2840"
LANG_EN = "languageConstants/1000"

# (angle, keyword) — angle keys used downstream in processing
CANDIDATES: list[tuple[str, str]] = [
    # A · Panama program / residency core (buyer)
    ("panama_program", "panama qualified investor program"),
    ("panama_program", "panama qualified investor visa"),
    ("panama_program", "panama golden visa"),
    ("panama_program", "panama residency by investment"),
    ("panama_program", "panama residency by investment program"),
    ("panama_program", "panama investor visa"),
    ("panama_program", "panama investment visa"),
    ("panama_program", "panama permanent residency"),
    ("panama_program", "panama permanent residency by investment"),
    ("panama_program", "panama residency"),
    ("panama_program", "panama residency requirements"),
    ("panama_program", "panama residency visa"),
    ("panama_program", "residency visa panama"),
    ("panama_program", "panama residency for americans"),
    ("panama_program", "panama residency program"),
    ("panama_program", "how to get residency in panama"),
    ("panama_program", "panama residency cost"),
    ("panama_program", "panama immigration lawyer"),
    ("panama_program", "panama immigration lawyers"),
    ("panama_program", "immigrate to panama from us"),
    ("panama_program", "panama visa for us citizens"),
    # B · Property + residency (capital-holder)
    ("property", "buy property in panama"),
    ("property", "buying property in panama"),
    ("property", "buy real estate in panama"),
    ("property", "buying real estate in panama"),
    ("property", "buy house in panama"),
    ("property", "buy apartment in panama"),
    ("property", "buy condo in panama"),
    ("property", "panama real estate"),
    ("property", "panama real estate for sale"),
    ("property", "panama real estate investment"),
    ("property", "real estate investment in panama"),
    ("property", "investing in panama real estate"),
    ("property", "invest in panama real estate"),
    ("property", "panama investment property"),
    ("property", "panama property for sale"),
    ("property", "homes for sale in panama"),
    ("property", "houses for sale in panama"),
    ("property", "panama city panama real estate"),
    ("property", "panama city panama condos for sale"),
    ("property", "apartments for sale in panama city panama"),
    ("property", "santa maria panama real estate"),
    ("property", "panama real estate for expats"),
    ("property", "best place to buy real estate in panama"),
    ("property", "panama beachfront property for sale"),
    # C · Friendly Nations Visa (named program)
    ("friendly_nations", "panama friendly nations visa"),
    ("friendly_nations", "friendly nations visa"),
    ("friendly_nations", "panama friendly nations visa requirements"),
    ("friendly_nations", "friendly nations visa panama requirements"),
    # D · Golden visa / RBI category generics
    ("golden_visa_generic", "golden visa"),
    ("golden_visa_generic", "golden visa program"),
    ("golden_visa_generic", "golden visa programs"),
    ("golden_visa_generic", "golden visa countries"),
    ("golden_visa_generic", "best golden visa"),
    ("golden_visa_generic", "best golden visa programs"),
    ("golden_visa_generic", "cheapest golden visa"),
    ("golden_visa_generic", "golden visa real estate"),
    ("golden_visa_generic", "real estate golden visa"),
    ("golden_visa_generic", "golden visa cost"),
    ("rbi_generic", "residency by investment"),
    ("rbi_generic", "residency by investment programs"),
    ("rbi_generic", "residence by investment"),
    ("rbi_generic", "best residency by investment"),
    ("rbi_generic", "permanent residency by investment"),
    ("rbi_generic", "residency by investment countries"),
    ("rbi_generic", "cheapest residency by investment"),
    # E · Second residency / plan B
    ("second_residency", "second residency"),
    ("second_residency", "second residency program"),
    ("second_residency", "second residence"),
    ("second_residency", "plan b residency"),
    ("second_residency", "plan b citizenship"),
    ("second_residency", "backup residency"),
    # F · Investor/investment visa generics (direction-ambiguous)
    ("investor_visa_generic", "investor visa"),
    ("investor_visa_generic", "investment visa"),
    ("investor_visa_generic", "investor residency"),
    ("investor_visa_generic", "investment residency"),
    ("investor_visa_generic", "countries with investment visa"),
    ("investor_visa_generic", "real estate investment visa"),
    ("investor_visa_generic", "property investment visa"),
    # G · Tax / territorial (HNW motive)
    ("tax", "territorial tax countries"),
    ("tax", "panama tax residency"),
    ("tax", "tax residency panama"),
    ("tax", "panama taxes for expats"),
    ("tax", "countries with no tax on foreign income"),
    ("tax", "no tax on foreign income"),
    ("tax", "best tax residency countries"),
    ("tax", "panama territorial tax"),
    # H · Citizenship / passport (POLICY-FLAG, document only)
    ("citizenship_flag", "citizenship by investment"),
    ("citizenship_flag", "citizenship by investment programs"),
    ("citizenship_flag", "second passport"),
    ("citizenship_flag", "second citizenship"),
    ("citizenship_flag", "golden passport"),
    ("citizenship_flag", "panama citizenship"),
    ("citizenship_flag", "panama citizenship by investment"),
    ("citizenship_flag", "panama passport"),
    ("citizenship_flag", "panama passport by investment"),
    ("citizenship_flag", "panama dual citizenship"),
    ("citizenship_flag", "cheapest citizenship by investment"),
    # X · Retirement (EXCLUDED — documented for the negative list)
    ("retirement_excluded", "panama retirement visa"),
    ("retirement_excluded", "panama pensionado visa"),
    ("retirement_excluded", "pensionado visa panama"),
    ("retirement_excluded", "retiring to panama"),
]


def build_client() -> GoogleAdsClient:
    return GoogleAdsClient.load_from_dict({
        "developer_token": settings.GOOGLE_ADS_DEVELOPER_TOKEN,
        "client_id": settings.GOOGLE_ADS_CLIENT_ID,
        "client_secret": settings.GOOGLE_ADS_CLIENT_SECRET,
        "refresh_token": settings.GOOGLE_ADS_REFRESH_TOKEN,
        "login_customer_id": settings.GOOGLE_ADS_LOGIN_CUSTOMER_ID,
        "use_proto_plus": True,
    }, version="v23")


def chunked(seq, n):
    for i in range(0, len(seq), n):
        yield seq[i:i + n]


def main():
    client = build_client()
    svc = client.get_service("KeywordPlanIdeaService")
    kws = sorted({k for _, k in CANDIDATES})
    print(f"{len(kws)} unique candidates", file=sys.stderr)

    out: dict[str, dict] = {}
    for chunk in chunked(kws, 40):
        req = client.get_type("GenerateKeywordHistoricalMetricsRequest")
        req.customer_id = CUSTOMER_ID
        req.keywords.extend(chunk)
        req.geo_target_constants.append(GEO_US)
        req.language = LANG_EN
        req.keyword_plan_network = client.enums.KeywordPlanNetworkEnum.GOOGLE_SEARCH
        req.include_adult_keywords = False
        for attempt in range(6):
            try:
                resp = svc.generate_keyword_historical_metrics(request=req)
                break
            except GoogleAdsException as ex:
                msgs = "; ".join(e.message or "" for e in ex.failure.errors)
                if ("Retry in" in msgs or "Too many requests" in msgs) and attempt < 5:
                    import re
                    m = re.search(r"Retry in (\d+) second", msgs)
                    wait = int(m.group(1)) + 2 if m else 10 * (attempt + 1)
                    print(f"  429 — sleep {wait}s", file=sys.stderr)
                    time.sleep(wait)
                    continue
                raise
        for r in resp.results:
            m = r.keyword_metrics
            out[r.text.lower()] = {
                "avg_monthly_searches": m.avg_monthly_searches or 0,
                "competition": m.competition.name if m.competition else "UNSPECIFIED",
                "competition_index": m.competition_index or 0,
                "low_bid_usd": round((m.low_top_of_page_bid_micros or 0) / 1e6, 2) or None,
                "high_bid_usd": round((m.high_top_of_page_bid_micros or 0) / 1e6, 2) or None,
                "close_variants": list(r.close_variants),
            }
        time.sleep(5)

    result = {
        "meta": {"customer_id": CUSTOMER_ID, "geo": "US/2840", "lang": "EN/1000",
                 "network": "GOOGLE_SEARCH", "api_version": "v23",
                 "fetched": time.strftime("%Y-%m-%d %H:%M")},
        "angles": {a: [k for aa, k in CANDIDATES if aa == a]
                   for a in dict.fromkeys(a for a, _ in CANDIDATES)},
        "metrics": out,
    }
    path = "/Users/mqxerrormac16/Documents/LangarAI/google-ads-agent/data/panama-us-angles-kwp-hist-raw.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"WROTE {path} ({len(out)} canonical rows)", file=sys.stderr)


if __name__ == "__main__":
    main()
