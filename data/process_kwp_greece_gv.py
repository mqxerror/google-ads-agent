"""Join the raw Keyword Planner pull to the Greece GV keyword catalog (cluster/match/
intent/transliteration) and emit a render-ready dataset for the campaign artifact.

Output: greece-gv-kwp-processed.json — one row per catalog keyword, with
Oman + Jordan avg-monthly-searches, competition, CPC range, priority, plus a
totals_deduplicated block and a cpc_summary.

Greece note: residency-accurate. No citizenship / second-passport cluster.
"""
from __future__ import annotations
import json, os, re

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "greece-gv-kwp-raw.json")

# Parse KEYWORDS out of the fetch module source without importing app.config.
src = open(os.path.join(HERE, "fetch_kwp_greece_gv.py"), encoding="utf-8").read()
m = re.search(r"KEYWORDS:.*?=\s*\[(.*?)\n\]", src, re.S)
rows_src = m.group(1)
KEYWORDS = eval("[" + rows_src + "]")  # list of (cluster, kw, lang, match, intent)

# ── Arabic transliteration + gloss map (Greece GV, residency-accurate) ──
AR_META = {
    # A · Greece Golden Visa
    "الفيزا الذهبية اليونان": ("al-fīzā al-dhahabiyya al-Yūnān", "Greece golden visa"),
    "الإقامة الذهبية اليونان": ("al-iqāma al-dhahabiyya al-Yūnān", "Greece golden residency"),
    "الفيزا الذهبية": ("al-fīzā al-dhahabiyya", "golden visa"),
    "التأشيرة الذهبية": ("al-taʾshīra al-dhahabiyya", "golden visa (formal)"),
    "الإقامة الذهبية": ("al-iqāma al-dhahabiyya", "golden residency"),
    "الفيزا الذهبية اليونانية": ("al-fīzā al-dhahabiyya al-Yūnāniyya", "Greek golden visa"),
    "برنامج الفيزا الذهبية اليونان": ("barnāmaj al-fīzā al-dhahabiyya al-Yūnān", "Greece golden visa program"),
    "الإقامة الذهبية في اليونان": ("al-iqāma al-dhahabiyya fī al-Yūnān", "golden residency in Greece"),
    # B · Greece Residency by Investment
    "الإقامة في اليونان عن طريق الاستثمار": ("al-iqāma fī al-Yūnān ʿan ṭarīq al-istithmār", "residency in Greece by investment"),
    "الإقامة عن طريق الاستثمار": ("al-iqāma ʿan ṭarīq al-istithmār", "residency by investment"),
    "الإقامة الدائمة في اليونان": ("al-iqāma al-dāʾima fī al-Yūnān", "permanent residency in Greece"),
    "تصريح الإقامة في اليونان": ("taṣrīḥ al-iqāma fī al-Yūnān", "residence permit in Greece"),
    "الإقامة عبر الاستثمار": ("al-iqāma ʿabr al-istithmār", "residency via investment"),
    "الإقامة الدائمة عن طريق الاستثمار": ("al-iqāma al-dāʾima ʿan ṭarīq al-istithmār", "permanent residency by investment"),
    "الإقامة الاستثمارية": ("al-iqāma al-istithmāriyya", "investment residency"),
    "الإقامة الثانية": ("al-iqāma al-thāniya", "second residency"),
    # C · Greece Property / Real-estate Investment Visa
    "شراء عقار في اليونان للإقامة": ("shirāʾ ʿaqār fī al-Yūnān lil-iqāma", "buying property in Greece for residency"),
    "الاستثمار العقاري في اليونان": ("al-istithmār al-ʿaqārī fī al-Yūnān", "real-estate investment in Greece"),
    "شراء عقار في اليونان": ("shirāʾ ʿaqār fī al-Yūnān", "buying property in Greece"),
    "عقارات اليونان للاستثمار": ("ʿaqārāt al-Yūnān lil-istithmār", "Greece real estate for investment"),
    "الفيزا الذهبية عن طريق العقار في اليونان": ("al-fīzā al-dhahabiyya ʿan ṭarīq al-ʿaqār fī al-Yūnān", "golden visa via property in Greece"),
    "تملك عقار في اليونان": ("tamalluk ʿaqār fī al-Yūnān", "owning property in Greece"),
    "الاستثمار العقاري للحصول على الإقامة": ("al-istithmār al-ʿaqārī lil-ḥuṣūl ʿalā al-iqāma", "real-estate investment to obtain residency"),
    # D · EU Residency / Schengen Access
    "الإقامة في أوروبا عن طريق الاستثمار": ("al-iqāma fī Ūrūbbā ʿan ṭarīq al-istithmār", "residency in Europe by investment"),
    "الفيزا الذهبية الأوروبية": ("al-fīzā al-dhahabiyya al-Ūrūbbiyya", "European golden visa"),
    "الإقامة الأوروبية عن طريق الاستثمار": ("al-iqāma al-Ūrūbbiyya ʿan ṭarīq al-istithmār", "European residency by investment"),
    "إقامة شنغن عن طريق الاستثمار": ("iqāmat Shanghan ʿan ṭarīq al-istithmār", "Schengen residency by investment"),
    "الإقامة في الاتحاد الأوروبي بالاستثمار": ("al-iqāma fī al-Ittiḥād al-Ūrūbbī bil-istithmār", "residency in the EU by investment"),
    "تأشيرة شنغن عن طريق الاستثمار": ("taʾshīrat Shanghan ʿan ṭarīq al-istithmār", "Schengen visa by investment"),
    "الإقامة الأوروبية": ("al-iqāma al-Ūrūbbiyya", "European residency"),
    # E · Greece Investment Migration / Investor Visa
    "الاستثمار في اليونان": ("al-istithmār fī al-Yūnān", "investing in Greece"),
    "الهجرة إلى اليونان عن طريق الاستثمار": ("al-hijra ilā al-Yūnān ʿan ṭarīq al-istithmār", "immigrating to Greece by investment"),
    "تأشيرة المستثمر اليونان": ("taʾshīrat al-mustathmir al-Yūnān", "Greece investor visa"),
    "الاستثمار في اليونان للإقامة": ("al-istithmār fī al-Yūnān lil-iqāma", "investing in Greece for residency"),
    "فيزا المستثمر": ("fīzā al-mustathmir", "investor visa (colloquial)"),
    "الهجرة إلى اليونان": ("al-hijra ilā al-Yūnān", "immigrating to Greece"),
    # F · Comparison / Best-Cheapest-Fastest
    "أفضل الفيزا الذهبية": ("afḍal al-fīzā al-dhahabiyya", "best golden visa"),
    "أرخص فيزا ذهبية": ("arkhaṣ fīzā dhahabiyya", "cheapest golden visa"),
    "أرخص إقامة عن طريق الاستثمار": ("arkhaṣ iqāma ʿan ṭarīq al-istithmār", "cheapest residency by investment"),
    "أرخص فيزا ذهبية في أوروبا": ("arkhaṣ fīzā dhahabiyya fī Ūrūbbā", "cheapest golden visa in Europe"),
    "أفضل دول الإقامة عن طريق الاستثمار": ("afḍal duwal al-iqāma ʿan ṭarīq al-istithmār", "best countries for residency by investment"),
    "أفضل فيزا ذهبية في أوروبا": ("afḍal fīzā dhahabiyya fī Ūrūbbā", "best golden visa in Europe"),
    "أسرع إقامة عن طريق الاستثمار": ("asraʿ iqāma ʿan ṭarīq al-istithmār", "fastest residency by investment"),
}

CLUSTER_NAMES = {
    "A": "Greece Golden Visa",
    "B": "Greece Residency by Investment",
    "C": "Greece Property / Real-estate Investment Visa",
    "D": "EU Residency / Schengen Access",
    "E": "Greece Investment Migration",
    "F": "Comparison / Best-Cheapest-Fastest",
}

raw = json.load(open(RAW, encoding="utf-8"))

def look(lang, country, kw):
    return raw[lang][country].get(kw.lower())

def cpc_str(rec_om, rec_jo):
    los, his = [], []
    for rec in (rec_om, rec_jo):
        if rec:
            if rec.get("low_top_of_page_bid_usd"): los.append(rec["low_top_of_page_bid_usd"])
            if rec.get("high_top_of_page_bid_usd"): his.append(rec["high_top_of_page_bid_usd"])
    if not los and not his:
        return "no data"
    lo = min(los) if los else (min(his) if his else None)
    hi = max(his) if his else (max(los) if los else None)
    return f"${lo:.2f}–${hi:.2f}"

def vol_disp(rec):
    if not rec:
        return "<10 / no data"
    v = rec["avg_monthly_searches"]
    return str(v) if v and v > 0 else "<10 / no data"

def competition(rec_om, rec_jo):
    order = {"HIGH": 3, "MEDIUM": 2, "LOW": 1, "UNSPECIFIED": 0, "UNKNOWN": 0}
    best = None
    for rec in (rec_om, rec_jo):
        if rec:
            c = rec["competition"]
            if best is None or order.get(c, 0) > order.get(best, 0):
                best = c
    if best in (None, "UNSPECIFIED", "UNKNOWN"):
        return "—"
    return best.title()

def priority(cluster, intent, vom, vjo):
    maxv = max(vom or 0, vjo or 0)
    if cluster == "D":  # EU/Schengen bridge — high reach, treat like a reach cluster
        if maxv >= 10:
            return "P1 (reach)" if maxv >= 30 else "P2"
        return "P3 (long-tail)"
    if maxv >= 30:
        return "P1 (reach)"
    if maxv >= 10:
        return "P2"
    return "P3 (long-tail)"

# Greece-named "money term" clusters = A (Greece GV), C (Greece property), E (Greece invest-migration)
GREECE_NAMED = {"A", "C", "E"}

def greece_money(cluster, kw):
    """A Greece-named keyword is a 'money term' (high intent) regardless of volume."""
    return cluster in GREECE_NAMED and ("greece" in kw.lower() or "greek" in kw.lower()
                                        or "اليونان" in kw or "يوناني" in kw)

out_rows = []
for cluster, kw, lang, match, intent in KEYWORDS:
    rec_om = look(lang, "Oman", kw)
    rec_jo = look(lang, "Jordan", kw)
    vom = rec_om["avg_monthly_searches"] if rec_om else 0
    vjo = rec_jo["avg_monthly_searches"] if rec_jo else 0
    prio = priority(cluster, intent, vom, vjo)
    if greece_money(cluster, kw):
        prio = "P1 (money term)"
    row = {
        "cluster": cluster,
        "cluster_name": CLUSTER_NAMES[cluster],
        "keyword": kw,
        "lang": lang,
        "match": match,
        "intent": intent,
        "vol_oman": vom, "vol_oman_disp": vol_disp(rec_om),
        "vol_jordan": vjo, "vol_jordan_disp": vol_disp(rec_jo),
        "vol_max": max(vom, vjo),
        "competition": competition(rec_om, rec_jo),
        "cpc": cpc_str(rec_om, rec_jo),
        "priority": prio,
    }
    if lang == "AR":
        tl, gloss = AR_META.get(kw, ("", ""))
        row["translit"] = tl
        row["gloss"] = gloss
    out_rows.append(row)

# ── Totals (deduplicated: unique keyword+lang, max volume across geos not summed;
#    per-country we sum unique keyword rows once) ──
def dedup_rows():
    """Return one row per (keyword, lang), keeping the max-volume instance
    (a keyword can appear in >1 cluster, e.g. 'golden visa' or 'real estate golden visa')."""
    best = {}
    for r in out_rows:
        key = (r["keyword"], r["lang"])
        if key not in best or r["vol_max"] > best[key]["vol_max"]:
            best[key] = r
    return list(best.values())

dd = dedup_rows()
def total(lang, country):
    return sum(r[f"vol_{country.lower()}"] for r in dd if r["lang"] == lang)

totals = {
    "EN_Oman": total("EN", "Oman"), "EN_Jordan": total("EN", "Jordan"),
    "AR_Oman": total("AR", "Oman"), "AR_Jordan": total("AR", "Jordan"),
}
totals["EN_total"] = totals["EN_Oman"] + totals["EN_Jordan"]
totals["AR_total"] = totals["AR_Oman"] + totals["AR_Jordan"]
totals["Oman_total"] = totals["EN_Oman"] + totals["AR_Oman"]
totals["Jordan_total"] = totals["EN_Jordan"] + totals["AR_Jordan"]
totals["grand"] = totals["EN_total"] + totals["AR_total"]

# ── Top keywords by volume ──
best_by_kw = {}
for r in out_rows:
    key = (r["keyword"], r["lang"])
    if key not in best_by_kw or r["vol_max"] > best_by_kw[key]["vol_max"]:
        best_by_kw[key] = r
top = sorted(best_by_kw.values(), key=lambda r: r["vol_max"], reverse=True)[:14]

# ── CPC summary (which keywords returned bid data + low/high bands) ──
lo_bids, hi_bids, cpc_kws = [], [], []
for lang in ("EN", "AR"):
    for c in ("Oman", "Jordan"):
        for k, v in raw[lang][c].items():
            if v.get("low_top_of_page_bid_usd") or v.get("high_top_of_page_bid_usd"):
                if k not in cpc_kws:
                    cpc_kws.append(k)
                if v.get("low_top_of_page_bid_usd"): lo_bids.append(v["low_top_of_page_bid_usd"])
                if v.get("high_top_of_page_bid_usd"): hi_bids.append(v["high_top_of_page_bid_usd"])

cpc_summary = {
    "keywords_with_bid_data": sorted(cpc_kws),
    "count_keywords_with_bid_data": len(cpc_kws),
    "low_top_of_page_usd": {
        "min": round(min(lo_bids), 2), "max": round(max(lo_bids), 2),
        "avg": round(sum(lo_bids) / len(lo_bids), 2),
    } if lo_bids else None,
    "high_top_of_page_usd": {
        "min": round(min(hi_bids), 2), "max": round(max(hi_bids), 2),
        "avg": round(sum(hi_bids) / len(hi_bids), 2),
    } if hi_bids else None,
}

result = {
    "rows": out_rows,
    "totals": totals,
    "totals_deduplicated": totals,
    "top_keywords": [{"keyword": r["keyword"], "lang": r["lang"],
                      "vol_oman": r["vol_oman"], "vol_jordan": r["vol_jordan"],
                      "vol_max": r["vol_max"], "competition": r["competition"],
                      "cpc": r["cpc"], "cluster": r["cluster"]} for r in top],
    "cpc_summary": cpc_summary,
}

OUT = os.path.join(HERE, "greece-gv-kwp-processed.json")
json.dump(result, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

# ── Console summary ──
print("TOTALS:", json.dumps(totals, indent=2))
print("\nCPC SUMMARY:", json.dumps(cpc_summary, indent=2, ensure_ascii=False))
print("\nTOP 14 KEYWORDS BY MAX VOLUME:")
for r in top:
    print(f"  {r['vol_max']:>4}  [{r['lang']}] {r['competition']:<8} {r['cpc']:<16} {r['keyword']}  (O:{r['vol_oman']}/J:{r['vol_jordan']})")
print(f"\nROWS: {len(out_rows)}  (EN {sum(1 for r in out_rows if r['lang']=='EN')} / AR {sum(1 for r in out_rows if r['lang']=='AR')})")
print(f"WROTE {OUT}")
