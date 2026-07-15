"""DataForSEO Labs ranked_keywords for Panama-residency competitor domains (US).
Creds from env (sourced from ~/.langarai-secrets/seo/_shared/dataforseo.env).
7 live tasks, limit 700 rows each, relevance-filtered server-side.
Writes data/panama-us-dfs-ranked-raw.json (trimmed rows).
"""
import base64, json, os, sys, time
import urllib.request

AUTH = base64.b64encode(
    f"{os.environ['DATAFORSEO_LOGIN']}:{os.environ['DATAFORSEO_PASSWORD']}".encode()
).decode()

# (domain, panama_pure) — panama-pure sites skip the relevance filter
DOMAINS = [
    ("kraemerlaw.com", True),
    ("panamasovereign.com", True),
    ("henleyglobal.com", False),
    ("goldenvisas.com", False),
    ("getgoldenvisa.com", False),
    ("immigrantinvest.com", False),
    ("nomadcapitalist.com", False),
]

RELEVANCE_FILTER = [
    ["keyword_data.keyword", "like", "%panama%"], "or",
    ["keyword_data.keyword", "like", "%residency%"], "or",
    ["keyword_data.keyword", "like", "%residence%"], "or",
    ["keyword_data.keyword", "like", "%golden visa%"], "or",
    ["keyword_data.keyword", "like", "%citizenship%"], "or",
    ["keyword_data.keyword", "like", "%second passport%"], "or",
    ["keyword_data.keyword", "like", "%investor visa%"], "or",
    ["keyword_data.keyword", "like", "%investment visa%"],
]


def post(path, payload):
    req = urllib.request.Request(
        f"https://api.dataforseo.com/v3/{path}",
        data=json.dumps(payload).encode(),
        headers={"Authorization": f"Basic {AUTH}", "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=180) as r:
        return json.loads(r.read().decode())


def main():
    out = {"cost": 0.0, "domains": {}}
    for domain, pure in DOMAINS:
        task = {
            "target": domain, "location_code": 2840, "language_code": "en",
            "limit": 700, "order_by": ["keyword_data.keyword_info.search_volume,desc"],
            "item_types": ["organic"],
        }
        if not pure:
            task["filters"] = RELEVANCE_FILTER
        try:
            resp = post("dataforseo_labs/google/ranked_keywords/live", [task])
        except Exception as ex:  # noqa: BLE001
            out["domains"][domain] = {"__error__": str(ex)}
            print(f"[{domain}] HTTP ERROR {ex}", file=sys.stderr)
            continue
        out["cost"] += resp.get("cost") or 0
        t = (resp.get("tasks") or [{}])[0]
        if t.get("status_code") != 20000:
            out["domains"][domain] = {"__error__": t.get("status_message")}
            print(f"[{domain}] ERROR {t.get('status_message')}", file=sys.stderr)
            continue
        rows = []
        for res in t.get("result") or []:
            for it in res.get("items") or []:
                kd = it.get("keyword_data") or {}
                ki = kd.get("keyword_info") or {}
                si = (kd.get("search_intent_info") or {}).get("main_intent")
                serp = (it.get("ranked_serp_element") or {}).get("serp_item") or {}
                rows.append({
                    "keyword": kd.get("keyword"),
                    "volume_us": ki.get("search_volume"),
                    "cpc": ki.get("cpc"),
                    "competition": ki.get("competition"),
                    "intent": si,
                    "rank": serp.get("rank_absolute"),
                    "url": serp.get("url"),
                    "etv": round(serp.get("etv") or 0, 1),
                })
        out["domains"][domain] = rows
        print(f"[{domain}] {len(rows)} keywords", file=sys.stderr)
        time.sleep(1.5)
    path = "/Users/mqxerrormac16/Documents/LangarAI/google-ads-agent/data/panama-us-dfs-ranked-raw.json"
    with open(path, "w") as f:
        json.dump(out, f, indent=2)
    print("total cost:", round(out["cost"], 4), file=sys.stderr)
    print("WROTE", path, file=sys.stderr)


if __name__ == "__main__":
    main()
