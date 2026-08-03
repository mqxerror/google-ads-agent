"""Story 14.2 ★ — CI spec-drift guard (NFR-D1).

The tripwire that keeps the mirrored-constant failure class (the DG 30-vs-40 bug)
dead for every story after this one. Three checks, all in the DEFAULT pytest
collection (no marker, no opt-in), so no later story can merge past them:

1. **Tombstone check** — a registered list of RETIRED constant names fails the
   build if any name reappears in its enforcement file (AST walk for ``.py``,
   whole-word scan for ``.tsx``). The list starts EMPTY; stories 14.3 / 14.4 /
   14.5 register their deleted constants in the SAME commit that deletes them.

2. **Sentinel-literal scan** — an AST walk (``.py``) / string-and-comment-stripped
   scan (``.tsx``) over a curated enforcement-file list, failing on any numeric
   literal in the sentinel set that is NOT the registry itself, unless the line
   carries a ``# spec-ok: <reason>`` / ``// spec-ok: <reason>`` pragma. Each
   file's pragma count is snapshot-asserted so additions are visible in review.
   The file list ACCRETES: a file joins it in the story that makes it literal-
   free (14.3 orchestrators, 14.4 routers, 14.5 wizards, 16.x copy/workbench) —
   which is exactly how the guard catches each refactor story's own work.

3. **Round-trip check** — ``GET /api/creative/specs`` deep-equals ``REGISTRY``;
   the endpoint cannot drift from the module.

The scan is a tripwire, not a proof — the STRUCTURAL fence is that the second
copy has been deleted (tombstone), so there is nothing left to disagree.

Run: cd backend && .venv/bin/python -m pytest tests/test_spec_registry_guard.py -q
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Dict, List, Tuple

import pytest
from fastapi.testclient import TestClient

from app.services import creative_specs as cs

_BACKEND = Path(__file__).resolve().parents[1]
_REPO = Path(__file__).resolve().parents[2]
_FRONTEND = _REPO / "frontend"

# The sentinel set: numbers that have been (or could be) a creative limit. Any of
# these appearing as a bare literal in an enforcement file is drift unless
# explicitly waived with a `spec-ok` pragma.
SENTINELS = frozenset({15, 20, 25, 30, 40, 60, 80, 90, 128, 2048})

PRAGMA = "spec-ok"


# ─────────────────────────────────────────────────────────────────────────────
# Registries of what the guard watches. These grow as the strangler proceeds.
# ─────────────────────────────────────────────────────────────────────────────

# (constant_name, path_relative_to_backend_or_frontend, kind) — kind in {py, tsx}
_TOMBSTONES: List[Tuple[str, Path, str]] = []


def register_tombstone(name: str, path: Path, kind: str) -> None:
    """Register a retired constant so the guard fails if it is ever resurrected.

    Stories 14.3 / 14.4 / 14.5 call this (at import time, below) in the same
    commit that deletes the constant. ``path`` is absolute; ``kind`` in
    {'py', 'tsx'}."""
    _TOMBSTONES.append((name, path, kind))


# Enforcement files under the sentinel-literal scan, each with its EXPECTED
# number of `spec-ok`-pragma'd sentinel literals (snapshot). A file joins this
# list in the story that deletes its limit constants:
#   14.3 → google_ads/.../pmax_orchestrator.py, demand_gen_orchestrator.py (validate paths)
#   14.4 → app/routers/pmax.py, demand_gen.py (draft clamps)
#   14.5 → frontend .../PMaxWizard.tsx, DemandGenWizard.tsx
#   16.x → creative_copy.py, TextWorkbench.tsx (once they exist)
# (path, kind, expected_pragma_count)
_SENTINEL_SCAN_FILES: List[Tuple[Path, str, int]] = []


def register_scan_file(path: Path, kind: str, expected_pragmas: int) -> None:
    _SENTINEL_SCAN_FILES.append((path, kind, expected_pragmas))


# ── Story 14.3 — orchestrator validators read the registry (local tables gone) ─
_ORCH = _BACKEND / "google_ads" / "services" / "campaign"
register_tombstone("TEXT_RULES", _ORCH / "pmax_orchestrator.py", "py")
register_tombstone("TEXT_RULES", _ORCH / "demand_gen_orchestrator.py", "py")
register_tombstone("BUSINESS_NAME_MAX_CHARS", _ORCH / "demand_gen_orchestrator.py", "py")
register_tombstone("MAX_LOGOS", _ORCH / "demand_gen_orchestrator.py", "py")
register_scan_file(_ORCH / "pmax_orchestrator.py", "py", 0)
register_scan_file(_ORCH / "demand_gen_orchestrator.py", "py", 0)

# ── Story 14.4 — router draft clamps + prompts read the registry ──
_ROUTERS = _BACKEND / "app" / "routers"
register_tombstone("_DRAFT_LIMITS", _ROUTERS / "pmax.py", "py")
register_tombstone("_DG_DRAFT_LIMITS", _ROUTERS / "demand_gen.py", "py")
register_tombstone("_DG_BUSINESS_NAME_MAX", _ROUTERS / "demand_gen.py", "py")
register_scan_file(_ROUTERS / "pmax.py", "py", 0)
register_scan_file(_ROUTERS / "demand_gen.py", "py", 0)


# ─────────────────────────────────────────────────────────────────────────────
# Scanner primitives (reused by mechanism self-tests, so they are proven at 14.2
# even while the real file lists accrete).
# ─────────────────────────────────────────────────────────────────────────────

def _py_sentinel_hits(src: str) -> List[Tuple[int, int]]:
    """Return [(lineno, value)] for every int literal in SENTINELS, via AST.

    Numbers inside strings/comments are NOT ast.Constant ints, so they never
    appear here — the Python scan is false-positive-free by construction."""
    hits: List[Tuple[int, int]] = []
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, int) \
                and not isinstance(node.value, bool) and node.value in SENTINELS:
            hits.append((node.lineno, node.value))
    return hits


def _strip_strings_and_comments(src: str) -> str:
    """Blank out string/template-literal contents and comments, preserving line
    numbers (newlines kept, everything else → space). So Tailwind classNames
    (`w-20`, `text-[40px]`) and comment prose never trip the .tsx scan; only
    bare CODE numerals remain."""
    out: List[str] = []
    i, n = 0, len(src)
    while i < n:
        c = src[i]
        # line comment
        if c == "/" and i + 1 < n and src[i + 1] == "/":
            while i < n and src[i] != "\n":
                out.append(" ")
                i += 1
            continue
        # block comment
        if c == "/" and i + 1 < n and src[i + 1] == "*":
            while i < n and not (src[i] == "*" and i + 1 < n and src[i + 1] == "/"):
                out.append("\n" if src[i] == "\n" else " ")
                i += 1
            out.append("  ")  # the closing */
            i += 2
            continue
        # string / template literal
        if c in ("'", '"', "`"):
            quote = c
            out.append(" ")
            i += 1
            while i < n:
                if src[i] == "\\" and i + 1 < n:
                    out.append("  ")
                    i += 2
                    continue
                if src[i] == quote:
                    out.append(" ")
                    i += 1
                    break
                out.append("\n" if src[i] == "\n" else " ")
                i += 1
            continue
        out.append(c)
        i += 1
    return "".join(out)


def _tsx_sentinel_hits(src: str) -> List[Tuple[int, int]]:
    """Return [(lineno, value)] for bare CODE sentinel numerals in .tsx source
    (strings + comments stripped first)."""
    import re
    stripped = _strip_strings_and_comments(src)
    pat = re.compile(r"(?<![\w.])(\d+)(?![\w.])")
    hits: List[Tuple[int, int]] = []
    for lineno, line in enumerate(stripped.splitlines(), start=1):
        for m in pat.finditer(line):
            val = int(m.group(1))
            if val in SENTINELS:
                hits.append((lineno, val))
    return hits


def _scan_file(path: Path, kind: str) -> Tuple[List[str], int]:
    """Scan one enforcement file. Returns (violations, pragma_count)."""
    src = path.read_text(encoding="utf-8")
    lines = src.splitlines()
    hits = _py_sentinel_hits(src) if kind == "py" else _tsx_sentinel_hits(src)
    violations: List[str] = []
    pragma_count = 0
    for lineno, val in hits:
        line = lines[lineno - 1] if 0 < lineno <= len(lines) else ""
        if PRAGMA in line:
            pragma_count += 1
        else:
            violations.append(f"{path.name}:{lineno}: bare sentinel literal {val} "
                              f"(add `{PRAGMA}: <reason>` or read the registry)")
    return violations, pragma_count


def _py_defines_name(src: str, name: str) -> bool:
    """True if ``name`` is referenced anywhere in the module's AST (assignment
    target, Name load, or attribute) — i.e. the retired constant is back."""
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id == name:
            return True
        if isinstance(node, ast.Attribute) and node.attr == name:
            return True
    return False


def _tsx_defines_name(src: str, name: str) -> bool:
    import re
    stripped = _strip_strings_and_comments(src)
    return re.search(rf"\b{re.escape(name)}\b", stripped) is not None


# ─────────────────────────────────────────────────────────────────────────────
# Check 1 — tombstones
# ─────────────────────────────────────────────────────────────────────────────

def test_tombstoned_constants_are_not_resurrected():
    resurrected: List[str] = []
    for name, path, kind in _TOMBSTONES:
        if not path.exists():
            continue
        src = path.read_text(encoding="utf-8")
        present = _py_defines_name(src, name) if kind == "py" else _tsx_defines_name(src, name)
        if present:
            resurrected.append(f"{name} reappeared in {path.name} — read creative_specs instead")
    assert not resurrected, "Tombstoned creative-limit constants resurrected:\n" + "\n".join(resurrected)


def test_tombstone_mechanism_flags_a_resurrection():
    # Proves the tombstone scanner works even while the real list accretes.
    assert _py_defines_name("TEXT_RULES = {'a': 1}\n", "TEXT_RULES") is True
    assert _py_defines_name("x = other_thing\n", "TEXT_RULES") is False
    assert _tsx_defines_name("const RULES = { headlines: 3 };", "RULES") is True
    assert _tsx_defines_name('const label = "RULES apply";', "RULES") is False  # in a string


# ─────────────────────────────────────────────────────────────────────────────
# Check 2 — sentinel-literal scan
# ─────────────────────────────────────────────────────────────────────────────

def test_no_bare_sentinel_literals_in_enforcement_files():
    all_violations: List[str] = []
    for path, kind, expected_pragmas in _SENTINEL_SCAN_FILES:
        assert path.exists(), f"scan file missing: {path}"
        violations, pragma_count = _scan_file(path, kind)
        all_violations.extend(violations)
        assert pragma_count == expected_pragmas, (
            f"{path.name}: {pragma_count} `{PRAGMA}` pragmas, snapshot expects "
            f"{expected_pragmas} — update the snapshot in register_scan_file() "
            f"and justify the change in review"
        )
    assert not all_violations, (
        "Bare creative-limit literals outside the registry:\n" + "\n".join(all_violations)
    )


def test_sentinel_scan_mechanism_py():
    # bare sentinel flagged; pragma'd sentinel allowed; string/comment ignored.
    assert _py_sentinel_hits("x = 40\n") == [(1, 40)]
    assert _py_sentinel_hits("x = 41\n") == []          # not a sentinel
    assert _py_sentinel_hits("s = '40 chars'\n") == []  # inside a string
    v, p = _scan_file_from_src("x = 40  # spec-ok: doc example\n", "py")
    assert v == [] and p == 1
    v, p = _scan_file_from_src("x = 40\n", "py")
    assert len(v) == 1 and p == 0


def test_sentinel_scan_mechanism_tsx():
    assert _tsx_sentinel_hits("const max = 40;") == [(1, 40)]
    assert _tsx_sentinel_hits('<div className="w-20 h-40" />') == []   # Tailwind in strings
    assert _tsx_sentinel_hits("const x = 41;") == []                    # not a sentinel
    assert _tsx_sentinel_hits("const y = arr[15];") == [(1, 15)]        # bare code numeral
    v, p = _scan_file_from_src("const max = 40; // spec-ok: legacy\n", "tsx")
    assert v == [] and p == 1


def _scan_file_from_src(src: str, kind: str) -> Tuple[List[str], int]:
    """In-memory twin of `_scan_file` for the mechanism self-tests."""
    lines = src.splitlines()
    hits = _py_sentinel_hits(src) if kind == "py" else _tsx_sentinel_hits(src)
    violations: List[str] = []
    pragma_count = 0
    for lineno, val in hits:
        line = lines[lineno - 1] if 0 < lineno <= len(lines) else ""
        if PRAGMA in line:
            pragma_count += 1
        else:
            violations.append(f"line {lineno}: {val}")
    return violations, pragma_count


# ─────────────────────────────────────────────────────────────────────────────
# Check 3 — endpoint round-trip
# ─────────────────────────────────────────────────────────────────────────────

def test_endpoint_round_trips_to_registry():
    from app.main import app
    client = TestClient(app)
    body = client.get("/api/creative/specs").json()
    assert cs.deserialize_registry(body["campaign_types"]) == cs.REGISTRY
