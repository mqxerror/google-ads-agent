"""DataForSEO SERP harvest — Panama residency head terms, google organic US.
Creds from env (DATAFORSEO_LOGIN/PASSWORD, sourced from
~/.langarai-secrets/seo/_shared/dataforseo.env — never printed).
Writes data/panama-us-dfs-serp-raw.json (organic items only, trimmed).
3 live tasks total.
"""
import json, os, sys
import urllib.request

LOGIN = os.environ["DATAFORSEO_LOGIN"]
PASSWORD = os.environ["DATAFORSEO_PASSWORD"]

import base64
AUTH = base64.b64encode(f"{LOGIN}:{PASSWORD}".encode()).decode()

TERMS = [
    "panama residency by investment",
    "panama qualified investor visa",
    "panama golden visa",
]

def post(path, payload):
    req = urllib.request.Request(
        f"https://api.dataforseo.com/v3/{path}",
        data=json.dumps(payload).encode(),
        headers={"Authorization": f"Basic {AUTH}", "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read().decode())

def main():
    out = {"cost": 0.0, "serps": {}}
    for t in TERMS:
        resp = post("serp/google/organic/live/advanced",
                    [{"keyword": t, "location_code": 2840, "language_code": "en", "depth": 20}])
        out["cost"] += resp.get("cost") or 0
        for task in resp.get("tasks", []):
            kw = task.get("data", {}).get("keyword", t)
            if task.get("status_code") != 20000:
                out["serps"][kw] = {"__error__": task.get("status_message")}
                continue
            items = []
            for res in task.get("result") or []:
                for it in res.get("items") or []:
                    if it.get("type") == "organic":
                        items.append({
                            "rank": it.get("rank_absolute"),
                            "domain": it.get("domain"),
                            "url": it.get("url"),
                            "title": it.get("title"),
                        })
            out["serps"][kw] = items
    path = "/Users/mqxerrormac16/Documents/LangarAI/google-ads-agent/data/panama-us-dfs-serp-raw.json"
    with open(path, "w") as f:
        json.dump(out, f, indent=2)
    print("cost:", out["cost"], file=sys.stderr)
    for kw, items in out["serps"].items():
        if isinstance(items, list):
            print(f"[{kw}] {len(items)} organic", file=sys.stderr)
            for it in items[:12]:
                print(f"   #{it['rank']:>2} {it['domain']}", file=sys.stderr)
        else:
            print(f"[{kw}] ERROR {items}", file=sys.stderr)

if __name__ == "__main__":
    main()
