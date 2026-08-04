"""RDA policy rules + P5 structural exit checks (story 19.4 · FR6.4/FR6.2/FR6.3).

FR6.4 — RDA's image rules ride in the REGISTRY, not the shell: the >20%-text
discount avoidance (the ``on_image_text=forbid`` knob → clean, text-free
generation) and the "no logo overlaid on the photo" rule (the
``logo_overlay=forbid`` knob → the logo routes to its dedicated slot). Both are
proven registry-driven by FIXTURE FLIP: flip the knob, the behavior changes with
ZERO code diff (NFR-C1). The >80%-blank guideline is a Google review-time image-
quality rule with no dedicated registry knob in v1; the clean-generation (forbid)
instruction is what keeps generated tiles full — noted, not faked.

FR6.2/FR6.3 — the P5 diff-scope exit gate: across the whole Display epic, the diff
from the epic base to HEAD must contain ZERO changes to ``creative_images.py`` or
any ``frontend/src/components/creative/*`` core file. The Display builder is the
acceptance test of the core; it may only CONSUME it.

Run:  cd backend && .venv/bin/python -m pytest tests/test_rda_policy.py -q
"""

from __future__ import annotations

import subprocess
from dataclasses import replace
from pathlib import Path

import pytest

from app.services import batch_render as br
from app.services import creative_specs as cs


# ── FR6.4 — text-free generation from the forbid knob (fixture flip) ──────────

def test_rda_text_free_instruction_from_forbid_knob():
    # RDA defaults to on_image_text=forbid → the generation guidance is text-free
    # (the >20%-text discount avoidance rule, read from the registry entry).
    assert cs.get("rda").policy.on_image_text == "forbid"
    note = cs.on_image_text_instruction(cs.get("rda"))
    assert "OUT of generated images" in note


def test_generation_prompt_reads_forbid_knob_flip_zero_code_diff(monkeypatch):
    # The batch renderer's generation prompt appends the registry instruction. A
    # forbid RDA emits the text-free clause; flipping the DATA to allow_warned
    # changes the emitted prompt with zero code diff (NFR-C1).
    base_prompt = br._generation_prompt("rda", "panama city skyline at golden hour")
    assert "panama city skyline" in base_prompt
    assert "OUT of generated images" in base_prompt

    flipped = replace(cs.get("rda"),
                      policy=replace(cs.get("rda").policy, on_image_text="allow_warned"))
    monkeypatch.setitem(cs.REGISTRY, "rda", flipped)

    flipped_prompt = br._generation_prompt("rda", "panama city skyline at golden hour")
    assert flipped_prompt != base_prompt
    assert "permitted but will be WARNED" in flipped_prompt


def test_generation_prompt_unknown_type_degrades_to_art_direction():
    # An unknown campaign type must not raise — it degrades to the raw art
    # direction (fail-open on guidance, never on generation).
    assert br._generation_prompt("nope", "raw art direction") == "raw art direction"


# ── FR6.4/FR2.2 — with-logo overlay under rda routes to the logo slot ─────────

def test_rda_logo_overlay_routes_to_logo_slot():
    # forbid → the logo ships in its dedicated slot, never composited on the photo
    # (research #8). PMax (allow_warned) is the composite counterexample.
    assert br._logo_overlay_policy("rda") == "forbid"
    assert br._logo_overlay_policy("pmax") == "allow_warned"


def test_flip_rda_logo_overlay_to_composite_zero_code_diff(monkeypatch):
    assert br._logo_overlay_policy("rda") == "forbid"
    flipped = replace(cs.get("rda"),
                      policy=replace(cs.get("rda").policy, logo_overlay="allow_warned"))
    monkeypatch.setitem(cs.REGISTRY, "rda", flipped)
    # Data flip alone moves rda onto the composite branch — no code change.
    assert br._logo_overlay_policy("rda") == "allow_warned"


def test_unknown_type_logo_policy_is_safest_forbid():
    assert br._logo_overlay_policy("nope") == "forbid"


# ── FR6.2/FR6.3 — P5 diff-scope exit gate (zero core changes across the epic) ──

_REPO = Path(__file__).resolve().parents[2]
_FROZEN_FILE = "backend/google_ads/services/campaign/creative_images.py"
_FROZEN_DIR = "frontend/src/components/creative/"


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(_REPO), *args],
        capture_output=True, text=True, check=True,
    ).stdout.strip()


def _epic19_base() -> str | None:
    """The epic base = parent of the FIRST Epic-19 commit (feat(19.1)). Located
    dynamically so the gate survives added commits; None if history was squashed
    or the commit isn't reachable (then the test skips)."""
    try:
        shas = _git("log", "--format=%H", "--grep=feat(19.1)").splitlines()
        if not shas:
            return None
        return _git("rev-parse", f"{shas[-1]}^")
    except subprocess.CalledProcessError:
        return None


def test_p5_diff_scope_zero_core_changes():
    base = _epic19_base()
    if base is None:
        pytest.skip("Epic-19 base commit not found (squashed / shallow history)")
    changed = _git("diff", "--name-only", base, "HEAD").splitlines()
    frozen_touched = [
        f for f in changed
        if f == _FROZEN_FILE or f.startswith(_FROZEN_DIR)
    ]
    assert frozen_touched == [], (
        "P5 exit gate (FR6.2/FR6.3): the Display epic must make ZERO changes to "
        f"the frozen core, but these were modified: {frozen_touched}"
    )
