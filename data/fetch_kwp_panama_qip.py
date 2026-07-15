"""
One-shot Keyword Planner fetch for the Panama QIP · Oman+Jordan campaign artifact.

READ-ONLY: calls KeywordPlanIdeaService.GenerateKeywordHistoricalMetrics.
Does NOT create a keyword plan resource or mutate the account.

Runs 4 calls: (Oman, EN), (Jordan, EN), (Oman, AR), (Jordan, AR).
Writes results to panama-qip-kwp-raw.json next to this file.
"""

from __future__ import annotations

import json
import os
import sys
import time

from google.ads.googleads.client import GoogleAdsClient
from google.ads.googleads.errors import GoogleAdsException

from app.config import settings

CUSTOMER_ID = "7178239091"
GEO = {"Oman": "geoTargetConstants/2512", "Jordan": "geoTargetConstants/2400"}
LANG = {"EN": "languageConstants/1000", "AR": "languageConstants/1019"}
KWP_NETWORK = "GOOGLE_SEARCH"  # excludes search partners

# ── Keyword catalog (verbatim from panama-qip-oman-jordan-keyword-research.md) ──
# Each row: (cluster, keyword_text, lang, match, intent)
# Arabic transliteration/gloss is carried in a separate map keyed by the AR text.

KEYWORDS: list[tuple[str, str, str, str, str]] = [
    # ── Cluster A · Golden / Investor Visa ──
    ("A", "golden visa", "EN", "PHRASE", "RESEARCH"),
    ("A", "panama golden visa", "EN", "EXACT", "READY"),
    ("A", "golden visa program", "EN", "PHRASE", "RESEARCH"),
    ("A", "investor visa", "EN", "PHRASE", "RESEARCH"),
    ("A", "investment visa", "EN", "PHRASE", "RESEARCH"),
    ("A", "real estate golden visa", "EN", "PHRASE", "READY"),
    ("A", "golden visa real estate", "EN", "PHRASE", "READY"),
    ("A", "golden visa by investment", "EN", "PHRASE", "READY"),
    ("A", "golden visa for family", "EN", "PHRASE", "READY"),
    ("A", "golden visa $300,000", "EN", "PHRASE", "READY"),
    ("A", "property investment visa", "EN", "PHRASE", "READY"),
    ("A", "golden visa consultants", "EN", "PHRASE", "READY"),
    ("A", "الفيزا الذهبية", "AR", "PHRASE", "RESEARCH"),
    ("A", "التأشيرة الذهبية", "AR", "PHRASE", "RESEARCH"),
    ("A", "الإقامة الذهبية", "AR", "PHRASE", "RESEARCH"),
    ("A", "الفيزا الذهبية بنما", "AR", "EXACT", "READY"),
    ("A", "تأشيرة المستثمر", "AR", "PHRASE", "READY"),
    ("A", "فيزا المستثمر", "AR", "PHRASE", "READY"),
    ("A", "الفيزا الذهبية عن طريق الاستثمار العقاري", "AR", "PHRASE", "READY"),
    ("A", "الإقامة الذهبية للعائلة", "AR", "PHRASE", "READY"),
    # ── Cluster B · Residency by Investment ──
    ("B", "residency by investment", "EN", "PHRASE", "RESEARCH"),
    ("B", "panama residency by investment", "EN", "EXACT", "READY"),
    ("B", "permanent residency by investment", "EN", "PHRASE", "READY"),
    ("B", "residence by investment", "EN", "PHRASE", "RESEARCH"),
    ("B", "residency through investment", "EN", "PHRASE", "RESEARCH"),
    ("B", "real estate residency", "EN", "PHRASE", "READY"),
    ("B", "invest for residency", "EN", "PHRASE", "READY"),
    ("B", "second residency", "EN", "PHRASE", "RESEARCH"),
    ("B", "second residency program", "EN", "PHRASE", "RESEARCH"),
    ("B", "fast permanent residency", "EN", "PHRASE", "READY"),
    ("B", "permanent residency real estate investment", "EN", "PHRASE", "READY"),
    ("B", "residency by investment programs", "EN", "PHRASE", "RESEARCH"),
    ("B", "الإقامة عن طريق الاستثمار", "AR", "PHRASE", "RESEARCH"),
    ("B", "الإقامة عبر الاستثمار", "AR", "PHRASE", "RESEARCH"),
    ("B", "الإقامة الدائمة عن طريق الاستثمار", "AR", "PHRASE", "READY"),
    ("B", "الإقامة عن طريق الاستثمار العقاري", "AR", "PHRASE", "READY"),
    ("B", "الإقامة الاستثمارية", "AR", "PHRASE", "RESEARCH"),
    ("B", "الإقامة في بنما عن طريق الاستثمار", "AR", "EXACT", "READY"),
    ("B", "الإقامة الثانية", "AR", "PHRASE", "RESEARCH"),
    ("B", "برنامج الإقامة عن طريق الاستثمار", "AR", "PHRASE", "RESEARCH"),
    # ── Cluster C · Citizenship / Second Passport ──
    ("C", "citizenship by investment", "EN", "PHRASE", "RESEARCH"),
    ("C", "second passport", "EN", "PHRASE", "RESEARCH"),
    ("C", "second citizenship", "EN", "PHRASE", "RESEARCH"),
    ("C", "panama citizenship by investment", "EN", "EXACT", "READY"),
    ("C", "panama second passport", "EN", "EXACT", "READY"),
    ("C", "passport by investment", "EN", "PHRASE", "RESEARCH"),
    ("C", "get a second passport", "EN", "PHRASE", "READY"),
    ("C", "dual citizenship by investment", "EN", "PHRASE", "RESEARCH"),
    ("C", "second passport for family", "EN", "PHRASE", "READY"),
    ("C", "citizenship through real estate", "EN", "PHRASE", "READY"),
    ("C", "strongest second passport", "EN", "PHRASE", "RESEARCH"),
    ("C", "visa free passport investment", "EN", "PHRASE", "RESEARCH"),
    ("C", "الجنسية عن طريق الاستثمار", "AR", "PHRASE", "RESEARCH"),
    ("C", "الجنسية عبر الاستثمار", "AR", "PHRASE", "RESEARCH"),
    ("C", "جواز سفر ثاني", "AR", "PHRASE", "RESEARCH"),
    ("C", "جواز سفر ثان", "AR", "PHRASE", "RESEARCH"),
    ("C", "الجنسية الثانية", "AR", "PHRASE", "RESEARCH"),
    ("C", "المواطنة عن طريق الاستثمار", "AR", "PHRASE", "RESEARCH"),
    ("C", "الجنسية عن طريق الاستثمار العقاري", "AR", "PHRASE", "READY"),
    ("C", "جنسية بنما عن طريق الاستثمار", "AR", "EXACT", "READY"),
    ("C", "الحصول على جواز سفر ثاني", "AR", "PHRASE", "READY"),
    ("C", "جواز سفر أوروبي بديل", "AR", "PHRASE", "RESEARCH"),
    # ── Cluster D · Panama-specific ──
    ("D", "panama golden visa", "EN", "EXACT", "READY"),
    ("D", "panama residency by investment", "EN", "EXACT", "READY"),
    ("D", "panama qualified investor visa", "EN", "EXACT", "READY"),
    ("D", "panama qualified investor program", "EN", "EXACT", "READY"),
    ("D", "panama investor visa", "EN", "EXACT", "READY"),
    ("D", "panama permanent residency", "EN", "EXACT", "READY"),
    ("D", "panama residency", "EN", "PHRASE", "RESEARCH"),
    ("D", "panama citizenship", "EN", "PHRASE", "RESEARCH"),
    ("D", "panama passport by investment", "EN", "EXACT", "READY"),
    ("D", "panama real estate residency", "EN", "PHRASE", "READY"),
    ("D", "panama $300,000 visa", "EN", "PHRASE", "READY"),
    ("D", "invest in panama residency", "EN", "PHRASE", "READY"),
    ("D", "panama friendly nations visa", "EN", "PHRASE", "RESEARCH"),
    ("D", "الإقامة في بنما", "AR", "PHRASE", "READY"),
    ("D", "الجنسية البنمية", "AR", "PHRASE", "RESEARCH"),
    ("D", "جواز سفر بنما", "AR", "PHRASE", "RESEARCH"),
    ("D", "الاستثمار العقاري في بنما", "AR", "PHRASE", "READY"),
    ("D", "الإقامة الدائمة في بنما", "AR", "PHRASE", "READY"),
    ("D", "برنامج المستثمر المؤهل بنما", "AR", "EXACT", "READY"),
    ("D", "فيزا بنما للمستثمرين", "AR", "EXACT", "READY"),
    ("D", "شراء عقار في بنما للإقامة", "AR", "PHRASE", "READY"),
    # ── Cluster E · Tax / Territorial / Plan-B / Base ──
    ("E", "territorial tax country", "EN", "PHRASE", "RESEARCH"),
    ("E", "tax free residency", "EN", "PHRASE", "RESEARCH"),
    ("E", "tax friendly second residency", "EN", "PHRASE", "RESEARCH"),
    ("E", "plan b residency", "EN", "PHRASE", "RESEARCH"),
    ("E", "plan b citizenship", "EN", "PHRASE", "RESEARCH"),
    ("E", "offshore residency", "EN", "PHRASE", "RESEARCH"),
    ("E", "relocate for tax", "EN", "PHRASE", "RESEARCH"),
    ("E", "no tax on foreign income country", "EN", "PHRASE", "RESEARCH"),
    ("E", "best country for tax residency", "EN", "PHRASE", "RESEARCH"),
    ("E", "dollarized economy residency", "EN", "PHRASE", "RESEARCH"),
    ("E", "family relocation plan b", "EN", "PHRASE", "RESEARCH"),
    ("E", "wealth protection second passport", "EN", "PHRASE", "RESEARCH"),
    ("E", "دولة بدون ضرائب", "AR", "PHRASE", "RESEARCH"),
    ("E", "الإقامة بدون ضرائب", "AR", "PHRASE", "RESEARCH"),
    ("E", "دولة معفاة من الضرائب", "AR", "PHRASE", "RESEARCH"),
    ("E", "الإقامة الضريبية", "AR", "PHRASE", "RESEARCH"),
    ("E", "خطة بديلة للعائلة", "AR", "PHRASE", "RESEARCH"),
    ("E", "بلد آمن للاستثمار والإقامة", "AR", "PHRASE", "RESEARCH"),
    ("E", "حماية الثروة جنسية ثانية", "AR", "PHRASE", "RESEARCH"),
    # ── Cluster F · Comparison / Superlative ──
    ("F", "best golden visa", "EN", "PHRASE", "RESEARCH"),
    ("F", "cheapest golden visa", "EN", "PHRASE", "RESEARCH"),
    ("F", "cheapest citizenship by investment", "EN", "PHRASE", "RESEARCH"),
    ("F", "best residency by investment", "EN", "PHRASE", "RESEARCH"),
    ("F", "fastest residency by investment", "EN", "PHRASE", "READY"),
    ("F", "cheapest second passport", "EN", "PHRASE", "RESEARCH"),
    ("F", "best second passport for family", "EN", "PHRASE", "RESEARCH"),
    ("F", "best country residency by investment", "EN", "PHRASE", "RESEARCH"),
    ("F", "affordable golden visa", "EN", "PHRASE", "RESEARCH"),
    ("F", "cheapest golden visa 2026", "EN", "PHRASE", "RESEARCH"),
    ("F", "easiest golden visa", "EN", "PHRASE", "RESEARCH"),
    ("F", "golden visa vs citizenship by investment", "EN", "PHRASE", "RESEARCH"),
    ("F", "أفضل الفيزا الذهبية", "AR", "PHRASE", "RESEARCH"),
    ("F", "أرخص جنسية عن طريق الاستثمار", "AR", "PHRASE", "RESEARCH"),
    ("F", "أرخص إقامة عن طريق الاستثمار", "AR", "PHRASE", "RESEARCH"),
    ("F", "أسرع إقامة عن طريق الاستثمار", "AR", "PHRASE", "READY"),
    ("F", "أفضل جواز سفر ثاني", "AR", "PHRASE", "RESEARCH"),
    ("F", "أرخص جواز سفر ثاني", "AR", "PHRASE", "RESEARCH"),
    ("F", "أفضل دول الإقامة عن طريق الاستثمار", "AR", "PHRASE", "RESEARCH"),
]


def build_client() -> GoogleAdsClient:
    cfg = {
        "developer_token": settings.GOOGLE_ADS_DEVELOPER_TOKEN,
        "client_id": settings.GOOGLE_ADS_CLIENT_ID,
        "client_secret": settings.GOOGLE_ADS_CLIENT_SECRET,
        "refresh_token": settings.GOOGLE_ADS_REFRESH_TOKEN,
        "login_customer_id": settings.GOOGLE_ADS_LOGIN_CUSTOMER_ID,
        "use_proto_plus": True,
    }
    return GoogleAdsClient.load_from_dict(cfg, version="v23")


def chunked(seq, n):
    for i in range(0, len(seq), n):
        yield seq[i : i + n]


def _call_with_retry(svc, req, max_tries: int = 6):
    """Call the API, honoring the server's 'Retry in N seconds' on QPS 429s."""
    for attempt in range(max_tries):
        try:
            return svc.generate_keyword_historical_metrics(request=req)
        except GoogleAdsException as ex:
            retriable = False
            wait = 5 * (attempt + 1)
            for e in ex.failure.errors:
                # QuotaError.RESOURCE_TEMPORARY_EXHAUSTED / per-method QPS throttle
                if "Retry in" in (e.message or "") or "Too many requests" in (e.message or ""):
                    retriable = True
                    # parse the suggested seconds if present
                    import re
                    m = re.search(r"Retry in (\d+) second", e.message or "")
                    if m:
                        wait = int(m.group(1)) + 2
            if retriable and attempt < max_tries - 1:
                print(f"    429 throttle — sleeping {wait}s (attempt {attempt+1})", file=sys.stderr)
                time.sleep(wait)
                continue
            raise


def fetch_historical(client, keywords: list[str], geo_rn: str, lang_rn: str) -> dict:
    """Return {keyword_text_lower: metrics_dict} for one (geo, lang) call."""
    svc = client.get_service("KeywordPlanIdeaService")
    network_enum = client.enums.KeywordPlanNetworkEnum.GOOGLE_SEARCH
    out: dict[str, dict] = {}

    # GenerateKeywordHistoricalMetrics caps keywords per request (~10k),
    # but keep chunks small for resilience.
    for chunk in chunked(keywords, 40):
        req = client.get_type("GenerateKeywordHistoricalMetricsRequest")
        req.customer_id = CUSTOMER_ID
        req.keywords.extend(chunk)
        req.geo_target_constants.append(geo_rn)
        req.language = lang_rn
        req.keyword_plan_network = network_enum
        req.include_adult_keywords = False
        # historical_metrics_options left default (last-12-months, all-locations off)

        resp = _call_with_retry(svc, req)
        for r in resp.results:
            m = r.keyword_metrics
            comp = m.competition.name if m.competition else "UNSPECIFIED"
            low = m.low_top_of_page_bid_micros or 0
            high = m.high_top_of_page_bid_micros or 0
            # the API may fold near-duplicate queries into one result with
            # `close_variants`; key on the canonical `text`
            out[r.text.lower()] = {
                "avg_monthly_searches": m.avg_monthly_searches or 0,
                "competition": comp,
                "competition_index": m.competition_index or 0,
                "low_top_of_page_bid_usd": round(low / 1_000_000, 2) if low else None,
                "high_top_of_page_bid_usd": round(high / 1_000_000, 2) if high else None,
                "close_variants": list(r.close_variants),
            }
        time.sleep(0.3)
    return out


def main():
    client = build_client()

    # partition keyword catalog by language
    en_kw = sorted({row[1] for row in KEYWORDS if row[2] == "EN"})
    ar_kw = sorted({row[1] for row in KEYWORDS if row[2] == "AR"})
    print(f"EN unique keywords: {len(en_kw)} | AR unique keywords: {len(ar_kw)}", file=sys.stderr)

    results: dict = {"EN": {}, "AR": {}, "meta": {
        "customer_id": CUSTOMER_ID,
        "geo": GEO, "lang": LANG, "network": KWP_NETWORK,
        "api_version": "v23",
    }}

    plan = [
        ("EN", "Oman", en_kw), ("EN", "Jordan", en_kw),
        ("AR", "Oman", ar_kw), ("AR", "Jordan", ar_kw),
    ]
    for idx, (lang, country, kw) in enumerate(plan):
        if idx > 0:
            time.sleep(6)  # space out per-method QPS between the 4 calls
        try:
            data = fetch_historical(client, kw, GEO[country], LANG[lang])
            print(f"[{lang}/{country}] fetched {len(data)} keyword rows", file=sys.stderr)
            results[lang][country] = data
        except GoogleAdsException as ex:
            msg = "; ".join(e.message for e in ex.failure.errors)
            print(f"[{lang}/{country}] ERROR: {msg}", file=sys.stderr)
            results[lang][country] = {"__error__": msg}
        except Exception as ex:  # noqa: BLE001
            print(f"[{lang}/{country}] ERROR: {ex}", file=sys.stderr)
            results[lang][country] = {"__error__": str(ex)}

    out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "panama-qip-kwp-raw.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"WROTE {out_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
