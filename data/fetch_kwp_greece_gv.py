"""
One-shot Keyword Planner fetch for the Greece Golden Visa · Oman+Jordan campaign artifact.

READ-ONLY: calls KeywordPlanIdeaService.GenerateKeywordHistoricalMetrics.
Does NOT create a keyword plan resource or mutate the account.

Runs 4 calls: (Oman, EN), (Jordan, EN), (Oman, AR), (Jordan, AR).
Writes results to greece-gv-kwp-raw.json next to this file.

Greece note: the Greece Golden Visa is RESIDENCY-by-investment, NOT citizenship.
There is NO "citizenship / second passport" cluster (unlike Panama). Cluster C is
"EU Residency / Schengen Access" kept residency-accurate. Cluster D is Greece-specific.
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

# ── Keyword catalog (Greece GV — residency-accurate; adapted from Panama approach) ──
# Each row: (cluster, keyword_text, lang, match, intent)
# Arabic transliteration/gloss carried in the processor's AR_META map.
# Clusters:
#   A · Greece Golden Visa (category head, Greece-named)
#   B · Greece Residency by Investment
#   C · Greece Property / Real-estate Investment Visa
#   D · EU Residency / Schengen Access (residency-accurate — NO citizenship/2nd-passport)
#   E · Greece Investment Migration / Investor Visa
#   F · Comparison / Best-Cheapest-Fastest

KEYWORDS: list[tuple[str, str, str, str, str]] = [
    # ── Cluster A · Greece Golden Visa (the Greece-named category head) ──
    ("A", "greece golden visa", "EN", "EXACT", "READY"),
    ("A", "golden visa greece", "EN", "EXACT", "READY"),
    ("A", "greece golden visa program", "EN", "PHRASE", "READY"),
    ("A", "greece golden visa 2026", "EN", "PHRASE", "READY"),
    ("A", "golden visa", "EN", "PHRASE", "RESEARCH"),
    ("A", "golden visa program", "EN", "PHRASE", "RESEARCH"),
    ("A", "greek golden visa", "EN", "PHRASE", "READY"),
    ("A", "golden visa greece requirements", "EN", "PHRASE", "RESEARCH"),
    ("A", "greece golden visa real estate", "EN", "PHRASE", "READY"),
    ("A", "greece golden visa cost", "EN", "PHRASE", "RESEARCH"),
    ("A", "golden visa europe", "EN", "PHRASE", "RESEARCH"),
    ("A", "greece investor golden visa", "EN", "PHRASE", "READY"),
    ("A", "الفيزا الذهبية اليونان", "AR", "EXACT", "READY"),
    ("A", "الإقامة الذهبية اليونان", "AR", "PHRASE", "READY"),
    ("A", "الفيزا الذهبية", "AR", "PHRASE", "RESEARCH"),
    ("A", "التأشيرة الذهبية", "AR", "PHRASE", "RESEARCH"),
    ("A", "الإقامة الذهبية", "AR", "PHRASE", "RESEARCH"),
    ("A", "الفيزا الذهبية اليونانية", "AR", "PHRASE", "READY"),
    ("A", "برنامج الفيزا الذهبية اليونان", "AR", "PHRASE", "READY"),
    ("A", "الإقامة الذهبية في اليونان", "AR", "PHRASE", "READY"),
    # ── Cluster B · Greece Residency by Investment ──
    ("B", "greece residency by investment", "EN", "EXACT", "READY"),
    ("B", "residency by investment", "EN", "PHRASE", "RESEARCH"),
    ("B", "greece permanent residency", "EN", "PHRASE", "READY"),
    ("B", "greece residence permit by investment", "EN", "PHRASE", "READY"),
    ("B", "greece residency by investment 2026", "EN", "PHRASE", "READY"),
    ("B", "permanent residency by investment", "EN", "PHRASE", "READY"),
    ("B", "residence by investment", "EN", "PHRASE", "RESEARCH"),
    ("B", "greece residence permit", "EN", "PHRASE", "RESEARCH"),
    ("B", "greece permanent residence by investment", "EN", "PHRASE", "READY"),
    ("B", "second residency", "EN", "PHRASE", "RESEARCH"),
    ("B", "residency through investment", "EN", "PHRASE", "RESEARCH"),
    ("B", "residency by investment programs", "EN", "PHRASE", "RESEARCH"),
    ("B", "الإقامة في اليونان عن طريق الاستثمار", "AR", "EXACT", "READY"),
    ("B", "الإقامة عن طريق الاستثمار", "AR", "PHRASE", "RESEARCH"),
    ("B", "الإقامة الدائمة في اليونان", "AR", "PHRASE", "READY"),
    ("B", "تصريح الإقامة في اليونان", "AR", "PHRASE", "RESEARCH"),
    ("B", "الإقامة عبر الاستثمار", "AR", "PHRASE", "RESEARCH"),
    ("B", "الإقامة الدائمة عن طريق الاستثمار", "AR", "PHRASE", "READY"),
    ("B", "الإقامة الاستثمارية", "AR", "PHRASE", "RESEARCH"),
    ("B", "الإقامة الثانية", "AR", "PHRASE", "RESEARCH"),
    # ── Cluster C · Greece Property / Real-estate Investment Visa ──
    ("C", "greece property investment visa", "EN", "EXACT", "READY"),
    ("C", "buy property in greece residency", "EN", "PHRASE", "READY"),
    ("C", "greece real estate golden visa", "EN", "PHRASE", "READY"),
    ("C", "buy property in greece", "EN", "PHRASE", "RESEARCH"),
    ("C", "greece real estate investment", "EN", "PHRASE", "RESEARCH"),
    ("C", "property investment visa", "EN", "PHRASE", "READY"),
    ("C", "greece property for residency", "EN", "PHRASE", "READY"),
    ("C", "invest in greece real estate", "EN", "PHRASE", "READY"),
    ("C", "greece property golden visa", "EN", "PHRASE", "READY"),
    ("C", "real estate golden visa", "EN", "PHRASE", "READY"),
    ("C", "greece real estate residency", "EN", "PHRASE", "READY"),
    ("C", "buy house in greece residency permit", "EN", "PHRASE", "READY"),
    ("C", "شراء عقار في اليونان للإقامة", "AR", "EXACT", "READY"),
    ("C", "الاستثمار العقاري في اليونان", "AR", "PHRASE", "READY"),
    ("C", "شراء عقار في اليونان", "AR", "PHRASE", "RESEARCH"),
    ("C", "عقارات اليونان للاستثمار", "AR", "PHRASE", "READY"),
    ("C", "الفيزا الذهبية عن طريق العقار في اليونان", "AR", "PHRASE", "READY"),
    ("C", "تملك عقار في اليونان", "AR", "PHRASE", "RESEARCH"),
    ("C", "الاستثمار العقاري للحصول على الإقامة", "AR", "PHRASE", "READY"),
    # ── Cluster D · EU Residency / Schengen Access (residency-accurate) ──
    ("D", "eu residency by investment", "EN", "EXACT", "READY"),
    ("D", "european golden visa", "EN", "PHRASE", "RESEARCH"),
    ("D", "schengen residency by investment", "EN", "PHRASE", "READY"),
    ("D", "eu residence permit by investment", "EN", "PHRASE", "READY"),
    ("D", "european residency by investment", "EN", "PHRASE", "READY"),
    ("D", "residency in europe by investment", "EN", "PHRASE", "READY"),
    ("D", "schengen residence permit investment", "EN", "PHRASE", "READY"),
    ("D", "eu golden visa", "EN", "PHRASE", "RESEARCH"),
    ("D", "europe residence by investment", "EN", "PHRASE", "RESEARCH"),
    ("D", "best eu golden visa", "EN", "PHRASE", "RESEARCH"),
    ("D", "الإقامة في أوروبا عن طريق الاستثمار", "AR", "EXACT", "READY"),
    ("D", "الفيزا الذهبية الأوروبية", "AR", "PHRASE", "RESEARCH"),
    ("D", "الإقامة الأوروبية عن طريق الاستثمار", "AR", "PHRASE", "READY"),
    ("D", "إقامة شنغن عن طريق الاستثمار", "AR", "PHRASE", "READY"),
    ("D", "الإقامة في الاتحاد الأوروبي بالاستثمار", "AR", "PHRASE", "READY"),
    ("D", "تأشيرة شنغن عن طريق الاستثمار", "AR", "PHRASE", "READY"),
    ("D", "الإقامة الأوروبية", "AR", "PHRASE", "RESEARCH"),
    # ── Cluster E · Greece Investment Migration / Investor Visa ──
    ("E", "invest in greece residency", "EN", "EXACT", "READY"),
    ("E", "greece investor visa", "EN", "EXACT", "READY"),
    ("E", "greece investment migration", "EN", "PHRASE", "RESEARCH"),
    ("E", "greece investment visa", "EN", "PHRASE", "READY"),
    ("E", "invest in greece", "EN", "PHRASE", "RESEARCH"),
    ("E", "greece immigration by investment", "EN", "PHRASE", "READY"),
    ("E", "greece visa by investment", "EN", "PHRASE", "READY"),
    ("E", "investor visa greece", "EN", "PHRASE", "READY"),
    ("E", "greece investment for residency", "EN", "PHRASE", "READY"),
    ("E", "move to greece by investment", "EN", "PHRASE", "READY"),
    ("E", "الاستثمار في اليونان", "AR", "PHRASE", "RESEARCH"),
    ("E", "الهجرة إلى اليونان عن طريق الاستثمار", "AR", "PHRASE", "READY"),
    ("E", "تأشيرة المستثمر اليونان", "AR", "PHRASE", "READY"),
    ("E", "الاستثمار في اليونان للإقامة", "AR", "PHRASE", "READY"),
    ("E", "فيزا المستثمر", "AR", "PHRASE", "RESEARCH"),
    ("E", "الهجرة إلى اليونان", "AR", "PHRASE", "RESEARCH"),
    # ── Cluster F · Comparison / Best-Cheapest-Fastest ──
    ("F", "best golden visa", "EN", "PHRASE", "RESEARCH"),
    ("F", "cheapest golden visa", "EN", "PHRASE", "RESEARCH"),
    ("F", "cheapest golden visa in europe", "EN", "PHRASE", "RESEARCH"),
    ("F", "best golden visa in europe", "EN", "PHRASE", "RESEARCH"),
    ("F", "best residency by investment", "EN", "PHRASE", "RESEARCH"),
    ("F", "cheapest residency by investment", "EN", "PHRASE", "RESEARCH"),
    ("F", "cheapest eu residency", "EN", "PHRASE", "RESEARCH"),
    ("F", "best country residency by investment", "EN", "PHRASE", "RESEARCH"),
    ("F", "affordable golden visa", "EN", "PHRASE", "RESEARCH"),
    ("F", "cheapest golden visa 2026", "EN", "PHRASE", "RESEARCH"),
    ("F", "easiest golden visa", "EN", "PHRASE", "RESEARCH"),
    ("F", "greece vs portugal golden visa", "EN", "PHRASE", "RESEARCH"),
    ("F", "أفضل الفيزا الذهبية", "AR", "PHRASE", "RESEARCH"),
    ("F", "أرخص فيزا ذهبية", "AR", "PHRASE", "RESEARCH"),
    ("F", "أرخص إقامة عن طريق الاستثمار", "AR", "PHRASE", "RESEARCH"),
    ("F", "أرخص فيزا ذهبية في أوروبا", "AR", "PHRASE", "RESEARCH"),
    ("F", "أفضل دول الإقامة عن طريق الاستثمار", "AR", "PHRASE", "RESEARCH"),
    ("F", "أفضل فيزا ذهبية في أوروبا", "AR", "PHRASE", "RESEARCH"),
    ("F", "أسرع إقامة عن طريق الاستثمار", "AR", "PHRASE", "READY"),
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
                if "Retry in" in (e.message or "") or "Too many requests" in (e.message or ""):
                    retriable = True
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

    for chunk in chunked(keywords, 40):
        req = client.get_type("GenerateKeywordHistoricalMetricsRequest")
        req.customer_id = CUSTOMER_ID
        req.keywords.extend(chunk)
        req.geo_target_constants.append(geo_rn)
        req.language = lang_rn
        req.keyword_plan_network = network_enum
        req.include_adult_keywords = False

        resp = _call_with_retry(svc, req)
        for r in resp.results:
            m = r.keyword_metrics
            comp = m.competition.name if m.competition else "UNSPECIFIED"
            low = m.low_top_of_page_bid_micros or 0
            high = m.high_top_of_page_bid_micros or 0
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

    out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "greece-gv-kwp-raw.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"WROTE {out_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
