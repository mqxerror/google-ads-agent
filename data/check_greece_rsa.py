#!/usr/bin/env python3
"""Self-check for greece_rsa_copy.json.

Enforces (aborts on any violation):
  - headlines <= 30 chars, descriptions <= 90 chars
  - forbidden symbol set never appears
  - exactly 14 headlines + 4 descriptions per ad group
  - the 6 exact ad group names are present (no more, no less)
  - "citizenship" appears at most once, and only in a description
"""
import json
import re
import sys

PATH = "/Users/mqxerrormac16/Documents/LangarAI/google-ads-agent/data/greece_rsa_copy.json"

EXPECTED_GROUPS = [
    "Greece Golden Visa",
    "Greece Residency by Investment",
    "Greece Property & Real Estate",
    "EU Residency & Schengen",
    "Greece Investment Migration",
    "Greece vs Europe (Comparison)",
]

# Forbidden individual characters (Google flagged as SYMBOLS/PROHIBITED).
# NOTE: hyphen "-" is ALLOWED (single, in genuine compounds). "&" is allowed
# only inside ad GROUP NAMES (keys), never scanned in ad text.
FORBIDDEN_CHARS = set("~+·•|*^_@#<>{}[]")

# Repeated punctuation patterns (!!!, ...) — any run of 2+ of ! . ? , ; :
REPEATED_PUNCT = re.compile(r"([!.?,;:])\1{1,}")

# Extra guard: reject any standalone "&" that leaked into ad TEXT
AMPERSAND = "&"


def scan_text(label, text, limit, violations):
    if len(text) > limit:
        violations.append(f"[LEN>{limit}] {label}: {len(text)} chars :: {text!r}")
    bad = sorted({c for c in text if c in FORBIDDEN_CHARS})
    if bad:
        violations.append(f"[SYMBOL] {label}: found {bad} :: {text!r}")
    if AMPERSAND in text:
        violations.append(f"[AMPERSAND] {label}: '&' in ad text :: {text!r}")
    m = REPEATED_PUNCT.search(text)
    if m:
        violations.append(f"[REPEAT-PUNCT] {label}: {m.group()!r} :: {text!r}")


def main():
    with open(PATH, encoding="utf-8") as f:
        data = json.load(f)

    violations = []

    # Ad-group key integrity
    if list(data.keys()) != EXPECTED_GROUPS:
        violations.append(
            f"[GROUPS] keys mismatch.\n  got: {list(data.keys())}\n  exp: {EXPECTED_GROUPS}"
        )

    citizenship_hits = []  # (group, where, text)
    max_h = 0
    max_d = 0

    for group, block in data.items():
        heads = block.get("headlines", [])
        descs = block.get("descriptions", [])

        if len(heads) != 14:
            violations.append(f"[COUNT] {group}: {len(heads)} headlines (need 14)")
        if len(descs) != 4:
            violations.append(f"[COUNT] {group}: {len(descs)} descriptions (need 4)")

        # duplicate headlines within a group (Google penalizes redundancy)
        seen = {}
        for h in heads:
            key = h.strip().lower()
            seen[key] = seen.get(key, 0) + 1
        dups = [k for k, v in seen.items() if v > 1]
        if dups:
            violations.append(f"[DUP-HEADLINE] {group}: {dups}")

        for i, h in enumerate(heads):
            scan_text(f"{group}/H{i}", h, 30, violations)
            max_h = max(max_h, len(h))
            if "citizen" in h.lower():
                violations.append(f"[CITIZEN-IN-HEADLINE] {group}/H{i} :: {h!r}")

        for i, d in enumerate(descs):
            scan_text(f"{group}/D{i}", d, 90, violations)
            max_d = max(max_d, len(d))
            if "citizen" in d.lower():
                citizenship_hits.append((group, f"D{i}", d))

    # citizenship: at most once, only in a description (headline case caught above)
    if len(citizenship_hits) > 1:
        violations.append(
            f"[CITIZEN-COUNT] appears {len(citizenship_hits)}x (max 1): {citizenship_hits}"
        )
    for g, where, text in citizenship_hits:
        # must be the honest qualified phrasing, never a promise / passport
        low = text.lower()
        if "passport" in low or "second passport" in low:
            violations.append(f"[CITIZEN-PHRASING] passport wording :: {g}/{where} {text!r}")
        if "guarantee" in low:
            violations.append(f"[GUARANTEE] :: {g}/{where} {text!r}")
        if "path to greek citizenship after 7 years" not in low:
            violations.append(
                f"[CITIZEN-PHRASING] not the approved qualified fact :: {g}/{where} {text!r}"
            )

    # global guarantee guard across everything
    for group, block in data.items():
        for i, d in enumerate(block["descriptions"]):
            if "guarantee" in d.lower():
                violations.append(f"[GUARANTEE] {group}/D{i} :: {d!r}")
        for i, h in enumerate(block["headlines"]):
            if "guarantee" in h.lower():
                violations.append(f"[GUARANTEE] {group}/H{i} :: {h!r}")

    print(f"Ad groups: {len(data)}")
    for group, block in data.items():
        print(f"  {group}: {len(block['headlines'])} headlines, "
              f"{len(block['descriptions'])} descriptions")
    print(f"Max headline length observed:    {max_h} (limit 30)")
    print(f"Max description length observed: {max_d} (limit 90)")
    print(f"Citizenship mentions: {len(citizenship_hits)} "
          f"{[(g, w) for g, w, _ in citizenship_hits]}")
    print("-" * 60)

    if violations:
        print(f"FAIL — {len(violations)} violation(s):")
        for v in violations:
            print("  " + v)
        sys.exit(1)

    print("PASS — zero violations. Char limits OK, zero forbidden symbols.")
    sys.exit(0)


if __name__ == "__main__":
    main()
