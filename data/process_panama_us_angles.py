"""Build data/panama-us-angles-kwp.json — processed Panama-QIP US angle research.
Merges KWP historical metrics (canonical volumes), KWP ideas (context),
and DataForSEO competitor ranked keywords (ownership).
Variant-pool dedupe: rows sharing (volume, bids, comp_index) within one angle
are one demand pool — counted once (KWP folds close variants into shared stats).
"""
import json, re
from collections import defaultdict

BASE = "/Users/mqxerrormac16/Documents/LangarAI/google-ads-agent/data"
hist = json.load(open(f"{BASE}/panama-us-angles-kwp-hist-raw.json"))
dfs = json.load(open(f"{BASE}/panama-us-dfs-ranked-raw.json"))
serp = json.load(open(f"{BASE}/panama-us-dfs-serp-raw.json"))

M = hist["metrics"]
ANGLES = hist["angles"]

# buyer-intent score per angle (1-5, Wassim's constraint: intent NOT research)
SCORE = {
    "panama_program": 5, "friendly_nations": 4, "property": 4,
    "rbi_generic": 4, "golden_visa_generic": 3, "investor_visa_generic": 2,
    "second_residency": 3, "tax": 2, "citizenship_flag": 2,
    "retirement_excluded": 0,
}
POLICY = {
    "panama_program": "SAFE — program/residency wording only",
    "friendly_nations": "SAFE — named Panama program; NOTE: FNV is the $200K/employment route, not QIP; LP must bridge",
    "property": "SAFE — but geo-ambiguity: Panama City Beach FLORIDA pollutes generic 'panama homes/houses' queries; needs FL negatives",
    "rbi_generic": "SAFE — category generic",
    "golden_visa_generic": "SAFE terms, but EU-leaning demand; needs country negatives (spain/dubai/uae/malta/italy/cyprus on top of existing greece/portugal/europe)",
    "investor_visa_generic": "CAUTION — direction-ambiguous: most 'investment visa' US searches mean EB-5 INTO the US",
    "second_residency": "SAFE but near-zero US volume",
    "tax": "CAUTION — tax-benefit claims restricted in ads; near-zero volume anyway",
    "citizenship_flag": "POLICY-RISKY — LP sells residency, not citizenship; ad copy must never promise passport/citizenship; v2 'passport' negative currently blocks part of this",
    "retirement_excluded": "EXCLUDED — pensionado searchers are not QIP buyers ($300K threshold mismatch)",
}

# DFS competitor ownership: keyword -> {domain: rank}
own = defaultdict(dict)
for dom, rows in dfs["domains"].items():
    if not isinstance(rows, list):
        continue
    for r in rows:
        if r["keyword"]:
            own[r["keyword"].lower()][dom] = r["rank"]

clusters = {}
grand_total = 0
counted_signatures = set()  # cross-angle dedupe
for angle, kws in ANGLES.items():
    rows, pools = [], {}
    for k in kws:
        r = M.get(k.lower())
        if not r:
            # folded into a close variant elsewhere
            rows.append({"keyword": k, "avg_monthly_searches_us": None,
                         "note": "folded into close variant", "counted": False})
            continue
        sig = (r["avg_monthly_searches"], r["low_bid_usd"], r["high_bid_usd"],
               r["competition_index"])
        counted = False
        if r["avg_monthly_searches"] and sig not in counted_signatures:
            counted_signatures.add(sig)
            counted = True
        pools.setdefault(sig, []).append(k)
        rows.append({
            "keyword": k,
            "avg_monthly_searches_us": r["avg_monthly_searches"],
            "competition": r["competition"],
            "competition_index": r["competition_index"],
            "top_of_page_bid_low_usd": r["low_bid_usd"],
            "top_of_page_bid_high_usd": r["high_bid_usd"],
            "counted_in_cluster_total": counted,
            "competitors_ranking": own.get(k.lower(), {}),
        })
    total = sum(r["avg_monthly_searches_us"] or 0 for r in rows
                if r.get("counted_in_cluster_total"))
    grand_total += total if angle != "retirement_excluded" else 0
    clusters[angle] = {
        "buyer_intent_score": SCORE[angle],
        "policy_note": POLICY[angle],
        "cluster_total_us_monthly_deduped": total,
        "priority_index": SCORE[angle] * total,
        "keywords": rows,
        "variant_pools": [sorted(v) for v in pools.values() if len(v) > 1],
    }

out = {
    "meta": {
        **hist["meta"],
        "sources": {
            "kwp_ideas_raw": "panama-us-angles-kwp-ideas-raw.json (2,116 idea rows, 3 seed calls)",
            "kwp_historical_raw": "panama-us-angles-kwp-hist-raw.json (97 canonical rows)",
            "dfs_serp_raw": "panama-us-dfs-serp-raw.json (3 head-term SERPs, google US)",
            "dfs_ranked_raw": "panama-us-dfs-ranked-raw.json (7 domains x 700 ranked kws)",
        },
        "dedupe_method": "variant pools — identical (volume, bids, comp_index) within candidate set counted once; cross-angle",
        "grand_total_addressable_us_monthly": grand_total,
    },
    "serp_competitors": {
        kw: [f"{it['domain']}#{it['rank']}" for it in items[:12]]
        for kw, items in serp["serps"].items() if isinstance(items, list)
    },
    "clusters": dict(sorted(clusters.items(),
                            key=lambda x: -x[1]["priority_index"])),
}
path = f"{BASE}/panama-us-angles-kwp.json"
with open(path, "w") as f:
    json.dump(out, f, indent=2)
print("WROTE", path)
print("grand total addressable (excl retirement):", f"{grand_total:,}/mo")
for a, c in out["clusters"].items():
    print(f"  {a:<22} score={c['buyer_intent_score']} total={c['cluster_total_us_monthly_deduped']:>7,} priority={c['priority_index']:>8,}")
EOF_MARKER_NOT_USED = None
