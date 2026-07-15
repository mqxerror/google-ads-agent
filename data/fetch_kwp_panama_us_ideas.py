"""Panama QIP — US buyer-intent angle research (RESEARCH ONLY, read-only APIs).

Step A1: KeywordPlanIdeaService.GenerateKeywordIdeas (US geo 2840, EN 1000)
seeded (a) keyword batches per angle, (b) LP url_seed.
Writes data/panama-us-angles-kwp-ideas-raw.json. NO mutations.
"""
from __future__ import annotations

import json, os, sys, time

sys.path.insert(0, "/Users/mqxerrormac16/Documents/LangarAI/google-ads-agent/backend")
from google.ads.googleads.client import GoogleAdsClient
from google.ads.googleads.errors import GoogleAdsException
from app.config import settings

CUSTOMER_ID = "7178239091"
GEO_US = "geoTargetConstants/2840"
LANG_EN = "languageConstants/1000"
LP = "https://www.mercan.com/lp/panama-qualified-investor-program"

SEED_BATCHES = {
    "seeds_core": [
        "panama residency", "panama investment visa", "residency by investment",
        "buy property in panama", "panama real estate", "second residency",
        "friendly nations visa",
    ],
    "seeds_angles": [
        "panama golden visa", "panama qualified investor visa",
        "panama permanent residency", "second passport", "plan b residency",
        "territorial tax countries", "citizenship by investment",
        "panama friendly nations visa",
    ],
}


def build_client() -> GoogleAdsClient:
    return GoogleAdsClient.load_from_dict({
        "developer_token": settings.GOOGLE_ADS_DEVELOPER_TOKEN,
        "client_id": settings.GOOGLE_ADS_CLIENT_ID,
        "client_secret": settings.GOOGLE_ADS_CLIENT_SECRET,
        "refresh_token": settings.GOOGLE_ADS_REFRESH_TOKEN,
        "login_customer_id": settings.GOOGLE_ADS_LOGIN_CUSTOMER_ID,
        "use_proto_plus": True,
    }, version="v23")


def run_ideas(client, seed_kind: str, seeds=None, url=None, cap=800) -> list[dict]:
    svc = client.get_service("KeywordPlanIdeaService")
    req = client.get_type("GenerateKeywordIdeasRequest")
    req.customer_id = CUSTOMER_ID
    req.geo_target_constants.append(GEO_US)
    req.language = LANG_EN
    req.include_adult_keywords = False
    req.keyword_plan_network = client.enums.KeywordPlanNetworkEnum.GOOGLE_SEARCH
    if seeds and url:
        req.keyword_and_url_seed.url = url
        req.keyword_and_url_seed.keywords.extend(seeds)
    elif seeds:
        req.keyword_seed.keywords.extend(seeds)
    elif url:
        req.url_seed.url = url

    out = []
    for attempt in range(6):
        try:
            pager = svc.generate_keyword_ideas(request=req)
            for idea in pager:
                m = idea.keyword_idea_metrics
                out.append({
                    "text": idea.text,
                    "avg_monthly_searches": m.avg_monthly_searches or 0,
                    "competition": m.competition.name if m.competition else "UNSPECIFIED",
                    "competition_index": m.competition_index or 0,
                    "low_bid_usd": round((m.low_top_of_page_bid_micros or 0) / 1e6, 2) or None,
                    "high_bid_usd": round((m.high_top_of_page_bid_micros or 0) / 1e6, 2) or None,
                    "close_variants": list(idea.close_variants),
                })
                if len(out) >= cap:
                    break
            return out
        except GoogleAdsException as ex:
            msgs = "; ".join(e.message or "" for e in ex.failure.errors)
            if ("Retry in" in msgs or "Too many requests" in msgs) and attempt < 5:
                import re
                mm = re.search(r"Retry in (\d+) second", msgs)
                wait = int(mm.group(1)) + 2 if mm else 10 * (attempt + 1)
                print(f"  [{seed_kind}] 429 — sleep {wait}s", file=sys.stderr)
                time.sleep(wait)
                continue
            raise
    return out


def main():
    client = build_client()
    results = {"meta": {
        "customer_id": CUSTOMER_ID, "geo": "US/2840", "lang": "EN/1000",
        "network": "GOOGLE_SEARCH", "api_version": "v23", "lp": LP,
        "fetched": time.strftime("%Y-%m-%d %H:%M"),
    }}
    plan = [(k, v, None) for k, v in SEED_BATCHES.items()] + [("url_seed_lp", None, LP)]
    for i, (kind, seeds, url) in enumerate(plan):
        if i:
            time.sleep(8)
        try:
            rows = run_ideas(client, kind, seeds=seeds, url=url)
            rows.sort(key=lambda r: -r["avg_monthly_searches"])
            results[kind] = rows
            print(f"[{kind}] {len(rows)} ideas", file=sys.stderr)
        except Exception as ex:  # noqa: BLE001
            results[kind] = {"__error__": str(ex)}
            print(f"[{kind}] ERROR: {ex}", file=sys.stderr)

    out = "/Users/mqxerrormac16/Documents/LangarAI/google-ads-agent/data/panama-us-angles-kwp-ideas-raw.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print("WROTE", out, file=sys.stderr)


if __name__ == "__main__":
    main()
