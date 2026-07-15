"""Join the raw Keyword Planner pull to the keyword catalog (cluster/match/intent/
transliteration) and emit a render-ready dataset for the campaign artifact.

Output: panama-qip-kwp-processed.json  — one row per catalog keyword, with
Oman + Jordan avg-monthly-searches, competition, CPC range, priority.
"""
from __future__ import annotations
import json, os

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "panama-qip-kwp-raw.json")

# Re-import the catalog from the fetch script to stay single-source.
import importlib.util
spec = importlib.util.spec_from_file_location("fetchmod", os.path.join(HERE, "fetch_kwp_panama_qip.py"))
# fetchmod imports app.config at module load; guard by only pulling KEYWORDS.
# Instead, redefine the catalog rows here would duplicate — so read them via exec of just the list.
# Simpler: parse KEYWORDS out of the fetch module source without importing app.
import re
src = open(os.path.join(HERE, "fetch_kwp_panama_qip.py"), encoding="utf-8").read()
m = re.search(r"KEYWORDS:.*?=\s*\[(.*?)\n\]", src, re.S)
rows_src = m.group(1)
KEYWORDS = eval("[" + rows_src + "]")  # list of (cluster, kw, lang, match, intent)

# ── Arabic transliteration + gloss map (verbatim from research doc) ──
AR_META = {
    "الفيزا الذهبية": ("al-fīzā al-dhahabiyya", "golden visa"),
    "التأشيرة الذهبية": ("al-taʾshīra al-dhahabiyya", "golden visa (formal)"),
    "الإقامة الذهبية": ("al-iqāma al-dhahabiyya", "golden residency"),
    "الفيزا الذهبية بنما": ("al-fīzā al-dhahabiyya Banamā", "Panama golden visa"),
    "تأشيرة المستثمر": ("taʾshīrat al-mustathmir", "investor visa"),
    "فيزا المستثمر": ("fīzā al-mustathmir", "investor visa (colloquial)"),
    "الفيزا الذهبية عن طريق الاستثمار العقاري": ("al-fīzā al-dhahabiyya ʿan ṭarīq al-istithmār al-ʿaqārī", "golden visa via real-estate investment"),
    "الإقامة الذهبية للعائلة": ("al-iqāma al-dhahabiyya lil-ʿāʾila", "golden residency for the family"),
    "الإقامة عن طريق الاستثمار": ("al-iqāma ʿan ṭarīq al-istithmār", "residency by investment"),
    "الإقامة عبر الاستثمار": ("al-iqāma ʿabr al-istithmār", "residency via investment"),
    "الإقامة الدائمة عن طريق الاستثمار": ("al-iqāma al-dāʾima ʿan ṭarīq al-istithmār", "permanent residency by investment"),
    "الإقامة عن طريق الاستثمار العقاري": ("al-iqāma ʿan ṭarīq al-istithmār al-ʿaqārī", "residency via real-estate investment"),
    "الإقامة الاستثمارية": ("al-iqāma al-istithmāriyya", "investment residency"),
    "الإقامة في بنما عن طريق الاستثمار": ("al-iqāma fī Banamā ʿan ṭarīq al-istithmār", "residency in Panama by investment"),
    "الإقامة الثانية": ("al-iqāma al-thāniya", "second residency"),
    "برنامج الإقامة عن طريق الاستثمار": ("barnāmaj al-iqāma ʿan ṭarīq al-istithmār", "residency-by-investment program"),
    "الجنسية عن طريق الاستثمار": ("al-jinsiyya ʿan ṭarīq al-istithmār", "citizenship by investment"),
    "الجنسية عبر الاستثمار": ("al-jinsiyya ʿabr al-istithmār", "citizenship via investment"),
    "جواز سفر ثاني": ("jawāz safar thānī", "second passport"),
    "جواز سفر ثان": ("jawāz safar thān", "second passport (variant)"),
    "الجنسية الثانية": ("al-jinsiyya al-thāniya", "second citizenship"),
    "المواطنة عن طريق الاستثمار": ("al-muwāṭana ʿan ṭarīq al-istithmār", "citizenship/nationality by investment"),
    "الجنسية عن طريق الاستثمار العقاري": ("al-jinsiyya ʿan ṭarīq al-istithmār al-ʿaqārī", "citizenship via real-estate investment"),
    "جنسية بنما عن طريق الاستثمار": ("jinsiyyat Banamā ʿan ṭarīq al-istithmār", "Panama citizenship by investment"),
    "الحصول على جواز سفر ثاني": ("al-ḥuṣūl ʿalā jawāz safar thānī", "obtaining a second passport"),
    "جواز سفر أوروبي بديل": ("jawāz safar ʾūrūbbī badīl", "alternative 'European' passport"),
    "الإقامة في بنما": ("al-iqāma fī Banamā", "residency in Panama"),
    "الجنسية البنمية": ("al-jinsiyya al-Banamiyya", "Panamanian citizenship"),
    "جواز سفر بنما": ("jawāz safar Banamā", "Panama passport"),
    "الاستثمار العقاري في بنما": ("al-istithmār al-ʿaqārī fī Banamā", "real-estate investment in Panama"),
    "الإقامة الدائمة في بنما": ("al-iqāma al-dāʾima fī Banamā", "permanent residency in Panama"),
    "برنامج المستثمر المؤهل بنما": ("barnāmaj al-mustathmir al-muʾahhal Banamā", "Qualified Investor Program Panama"),
    "فيزا بنما للمستثمرين": ("fīzā Banamā lil-mustathmirīn", "Panama visa for investors"),
    "شراء عقار في بنما للإقامة": ("shirāʾ ʿaqār fī Banamā lil-iqāma", "buying property in Panama for residency"),
    "دولة بدون ضرائب": ("dawla bidūn ḍarāʾib", "country without taxes"),
    "الإقامة بدون ضرائب": ("al-iqāma bidūn ḍarāʾib", "tax-free residency"),
    "دولة معفاة من الضرائب": ("dawla muʿfāt min al-ḍarāʾib", "tax-exempt country"),
    "الإقامة الضريبية": ("al-iqāma al-ḍarībiyya", "tax residency"),
    "خطة بديلة للعائلة": ("khuṭṭa badīla lil-ʿāʾila", "a Plan B for the family"),
    "بلد آمن للاستثمار والإقامة": ("balad āmin lil-istithmār wal-iqāma", "safe country for investment & residency"),
    "حماية الثروة جنسية ثانية": ("ḥimāyat al-tharwa jinsiyya thāniya", "wealth protection second citizenship"),
    "أفضل الفيزا الذهبية": ("afḍal al-fīzā al-dhahabiyya", "best golden visa"),
    "أرخص جنسية عن طريق الاستثمار": ("arkhaṣ jinsiyya ʿan ṭarīq al-istithmār", "cheapest citizenship by investment"),
    "أرخص إقامة عن طريق الاستثمار": ("arkhaṣ iqāma ʿan ṭarīq al-istithmār", "cheapest residency by investment"),
    "أسرع إقامة عن طريق الاستثمار": ("asraʿ iqāma ʿan ṭarīq al-istithmār", "fastest residency by investment"),
    "أفضل جواز سفر ثاني": ("afḍal jawāz safar thānī", "best second passport"),
    "أرخص جواز سفر ثاني": ("arkhaṣ jawāz safar thānī", "cheapest second passport"),
    "أفضل دول الإقامة عن طريق الاستثمار": ("afḍal duwal al-iqāma ʿan ṭarīq al-istithmār", "best countries for residency by investment"),
}

CLUSTER_NAMES = {
    "A": "Golden / Investor Visa",
    "B": "Residency by Investment",
    "C": "Citizenship / Second Passport",
    "D": "Panama-specific",
    "E": "Tax / Plan-B / Base",
    "F": "Comparison / Best-Cheapest-Fastest",
}

raw = json.load(open(RAW, encoding="utf-8"))

def look(lang, country, kw):
    rec = raw[lang][country].get(kw.lower())
    if not rec:
        return None
    return rec

def cpc_str(rec_om, rec_jo):
    """Merge CPC range across both geos into one display string."""
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
    if cluster == "D":  # Panama-specific = money terms, always high priority
        return "P1 (money term)"
    if maxv >= 30:
        return "P1 (reach)"
    if maxv >= 10:
        return "P2"
    return "P3 (long-tail)"

out_rows = []
for cluster, kw, lang, match, intent in KEYWORDS:
    rec_om = look(lang, "Oman", kw)
    rec_jo = look(lang, "Jordan", kw)
    vom = rec_om["avg_monthly_searches"] if rec_om else 0
    vjo = rec_jo["avg_monthly_searches"] if rec_jo else 0
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
        "priority": priority(cluster, intent, vom, vjo),
    }
    if lang == "AR":
        tl, gloss = AR_META.get(kw, ("", ""))
        row["translit"] = tl
        row["gloss"] = gloss
    out_rows.append(row)

# ── Totals ──
def total(lang, country):
    return sum(r[f"vol_{country.lower()}"] for r in out_rows if r["lang"] == lang)

totals = {
    "EN_Oman": total("EN", "Oman"), "EN_Jordan": total("EN", "Jordan"),
    "AR_Oman": total("AR", "Oman"), "AR_Jordan": total("AR", "Jordan"),
}
totals["EN_total"] = totals["EN_Oman"] + totals["EN_Jordan"]
totals["AR_total"] = totals["AR_Oman"] + totals["AR_Jordan"]
totals["Oman_total"] = totals["EN_Oman"] + totals["AR_Oman"]
totals["Jordan_total"] = totals["EN_Jordan"] + totals["AR_Jordan"]
totals["grand"] = totals["EN_total"] + totals["AR_total"]

# ── Top keywords by volume (dedupe by keyword+lang, use max across geos) ──
best_by_kw = {}
for r in out_rows:
    key = (r["keyword"], r["lang"])
    if key not in best_by_kw or r["vol_max"] > best_by_kw[key]["vol_max"]:
        best_by_kw[key] = r
top = sorted(best_by_kw.values(), key=lambda r: r["vol_max"], reverse=True)[:12]

result = {"rows": out_rows, "totals": totals,
          "top_keywords": [{"keyword": r["keyword"], "lang": r["lang"],
                            "vol_oman": r["vol_oman"], "vol_jordan": r["vol_jordan"],
                            "vol_max": r["vol_max"], "competition": r["competition"],
                            "cpc": r["cpc"], "cluster": r["cluster"]} for r in top]}

OUT = os.path.join(HERE, "panama-qip-kwp-processed.json")
json.dump(result, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

# ── Console summary ──
print("TOTALS:", json.dumps(totals, indent=2))
print("\nTOP 12 KEYWORDS BY MAX VOLUME:")
for r in top:
    print(f"  {r['vol_max']:>4}  [{r['lang']}] {r['competition']:<8} {r['cpc']:<14} {r['keyword']}  (O:{r['vol_oman']}/J:{r['vol_jordan']})")
print(f"\nWROTE {OUT}  ({len(out_rows)} rows)")
