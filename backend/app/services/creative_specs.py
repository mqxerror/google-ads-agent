"""Creative Spec Registry — THE single source of truth for every creative limit.

Epic 14 (Unified Creative Engine). This module replaces the mirrored limit
constants that used to live in ≥4 places (orchestrator ``TEXT_RULES`` ×2, router
draft clamps ×2, wizard ``RULES`` ×2) and had already drifted apart from each
other and from Google (the DG 30-vs-40 bug). From here on, every consumer —
server validators, drafter clamps, and the frontend wizards — reads ONE object.

Design (architecture AD-1, fences F1–F4):

- **F1 — limits import-only.** Enforcement code receives ``CampaignSpec`` objects;
  the old constant tables are deleted and tombstoned by the CI guard
  (``test_spec_registry_guard.py``). A resurrected literal fails CI.
- **F2 — geometry single-source.** Image-slot geometry (aspect / min dims) is
  NOT copied here; it is resolved BY IMPORT from
  ``creative_images.IMAGE_SLOT_SPECS`` via :pyattr:`ImageSlotSpec.geometry`. The
  registry physically cannot disagree with the crop pipeline.
- **F3 — policy without branches.** Prompt builders and validators read
  ``spec.policy``; campaign type appears exactly once, as the registry key.
- **F4 — frozen dataclasses.** Every spec is immutable at runtime; there is no
  code path that writes a limit (mirrors the fleet's "no mint site" discipline).

Seed values are the PRD §8 citation anchor, EACH carrying a ``verified`` flag and
a ``source``. Where the PRD's proposed value was UNVERIFIED (aggregator-sourced
or conflicted), it ships ``verified=False`` and is soft-validated (warn, never
block) per FR1.3 / decision D6.

IMPORTANT — count minimums are Google-verified (2026-08-03):
  The PRD §8 "count" ranges list a *recommended* 3–5 for PMax/DG headlines and
  descriptions, but Google's live help pages give the true HARD minimums, which
  match this repo's pre-existing behavior:
    * PMax  — headlines 3–15, long_headlines 1–5, descriptions **2**–5
      [https://support.google.com/google-ads/answer/14528373]
    * DG    — headlines **1**–5, descriptions **1**–5
      [https://support.google.com/google-ads/answer/17091672]
  Seeding the registry to the *recommended* minimums would reject valid live
  campaigns (a behavior change the PRD does not sanction) AND make the registry
  disagree with Google — the opposite of its purpose. We therefore seed the
  verified HARD minimums and enforce the PRD's real gap-closures on the MAX /
  char-cap / cross-field side (see FR1.4). The PMax "≥1 description ≤60" short
  rule is NOT present in Google's current docs (verified 2026-08-03) → it ships
  ``verified=False`` and soft-validates only.

RDA activation + verification (story 19.1, 2026-08-04):
  The ``rda`` entry shipped as data in P1 with every field ``verified=False``
  (aggregator-sourced). Story 19.1 verified each number against CURRENT Google
  documentation and flipped the confirmed ones to ``verified=True`` with the
  Google source cited. Verified against:
    * Google Ads Help 9050310 (Manage your responsive display ads, 2026-08-04):
      up to 5 short headlines × 30 chars, 1 long headline × 90 chars, up to 5
      descriptions × 90 chars, up to 15 marketing images, up to 5 logos in a
      "1:1 or 4:1 aspect ratio".
    * Google Ads API v23 ``ResponsiveDisplayAdInfo`` (proto): ``long_headline``
      is a SINGULAR field ⇒ exactly 1 (enforced structurally, see
      ``check_text_fields``); ``business_name`` max 25; ``marketing_images``
      (1.91:1) + ``square_marketing_images`` (1:1) are the ONLY marketing-image
      fields — there is NO portrait field for RDA; ``logo_images`` (4:1) +
      ``square_logo_images`` (1:1).
  Two places where the CURRENT DOCS beat the P1 seed (docs win, D6):
    1. **No portrait slot.** The seed carried an optional ``portrait`` (4:5)
       image slot from the aggregator table; the API's ``ResponsiveDisplayAdInfo``
       has no portrait marketing-image field, so it is REMOVED (an RDA can never
       carry a portrait asset — offering the slot would be a lie).
    2. **Total image cap is 15 COMBINED, not 15/ratio.** ``marketing_images``
       combined with ``square_marketing_images`` maxes at 15 (API), so
       ``total_image_cap=15`` (the seed left it ``None`` per an aggregator
       "≤15/ratio" reading).
  RDA VIDEO stays ``verified=False``: Google publishes no firm per-orientation
  video count for RDA (the ``youtube_videos`` field exists, but "≤5" is
  aggregator-sourced), so it soft-validates only — the honest remaining unknown.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from google_ads.services.campaign.creative_images import IMAGE_SLOT_SPECS

# Citation shorthands used in `source` fields.
_G_PMAX_TEXT = "Google Ads Help 14528373 (verified 2026-08-03)"
_G_PMAX_ASSETS = "Google Ads Help 14528220 (verified 2026-08-03)"
_G_DG_TEXT = "Google Ads Help 17091672 (verified 2026-08-03)"
_G_DG_SPECS = "Google Ads Help 13695777 / DG specs (verified 2026-08-03)"
_REPO_PROVEN = "repo-proven post-create attach (pmax_orchestrator.py)"
_RESEARCH_2A = "research §2a (aggregator — UNVERIFIED)"
_RESEARCH_2C = "research §2c (RDA aggregator — UNVERIFIED)"
_RESEARCH_62 = "research §6-2 (5-vs-15 conflict — UNVERIFIED)"
# RDA verified against CURRENT Google docs in story 19.1 (see module docstring).
_G_RDA_TEXT = "Google Ads Help 9050310 + API v23 ResponsiveDisplayAdInfo (verified 2026-08-04)"
_G_RDA_ASSETS = "Google Ads Help 9050310 + API v23 ResponsiveDisplayAdInfo assets (verified 2026-08-04)"
_RDA_VIDEO_U = "research §2c (RDA video ≤5 — aggregator, no firm Google figure — UNVERIFIED)"


@dataclass(frozen=True)
class TextFieldSpec:
    """A text asset field's count + char limits (FR1.1)."""

    min_count: int
    max_count: int
    max_chars: int
    verified: bool          # False ⇒ soft-validate (warn, never block) — FR1.3
    source: str             # citation key


@dataclass(frozen=True)
class ImageSlotSpec:
    """An image/logo slot. Geometry is NOT stored — it is resolved by import
    from ``creative_images.IMAGE_SLOT_SPECS`` (fence F2). ``slot`` is the key."""

    slot: str               # key into creative_images.IMAGE_SLOT_SPECS
    max_count: int
    required: bool
    verified: bool
    source: str

    @property
    def geometry(self) -> Optional[dict]:
        """The SAME dict object as ``creative_images.IMAGE_SLOT_SPECS[slot]``
        (identity, not a copy — fence F2). ``None`` for slots not yet present in
        the crop pipeline (e.g. ``landscape_logo``, added in P3 / story 17.5)."""
        return IMAGE_SLOT_SPECS.get(self.slot)

    @property
    def aspect(self) -> Optional[float]:
        g = self.geometry
        return None if g is None else g["aspect"]

    @property
    def min_w(self) -> Optional[int]:
        g = self.geometry
        return None if g is None else g["min_w"]

    @property
    def min_h(self) -> Optional[int]:
        g = self.geometry
        return None if g is None else g["min_h"]

    @property
    def label(self) -> Optional[str]:
        g = self.geometry
        return None if g is None else g["label"]


@dataclass(frozen=True)
class VideoSpec:
    """Video-asset limits. Never a hard gate (policy.video_gate == 'nudge')."""

    max_per_orientation: Optional[int]
    min_seconds: Optional[int]
    required: bool
    verified: bool
    source: str


@dataclass(frozen=True)
class PolicyKnobs:
    """Per-campaign-type policy — table-driven, never a code branch (NFR-C1)."""

    on_image_text: str      # 'forbid' | 'allow_warned'   (FR1.6, D3)
    logo_overlay: str       # 'forbid' | 'allow_warned'   (FR2.2)
    video_gate: str         # always 'nudge'              (FR5.4)


@dataclass(frozen=True)
class CampaignSpec:
    """Everything the engine needs to know about one campaign type's creative."""

    text: Dict[str, TextFieldSpec]
    images: Dict[str, ImageSlotSpec]
    logos: Dict[str, ImageSlotSpec]
    business_name_max: int
    total_image_cap: Optional[int]              # cross-slot sum cap; None ⇒ per-slot only
    search_themes: Optional[Tuple[int, int]]    # (max_count, max_chars) — PMax only
    video: VideoSpec
    final_url_max: int
    policy: PolicyKnobs
    # PMax "≥1 description ≤60" short-desc rule. AD-1's CampaignSpec had no home
    # for this cross-field soft constraint, so it is added here as an optional
    # TextFieldSpec (min_count = how many descriptions must be ≤ max_chars).
    # Only PMax populates it, and verified=False → warn only (see module note).
    short_description: Optional[TextFieldSpec] = None


@dataclass(frozen=True)
class EngineConfig:
    """Engine-wide knobs, same single-source discipline (used from Epic 16+)."""

    near_dup_threshold: float   # read by BOTH near-dup detectors (AD-2)
    batch_tile_cap: int         # FR2.6 "config-driven, not a literal"
    batch_retry_max: int        # NFR-Q1


# ─────────────────────────────────────────────────────────────────────────────
# The registry. Seed values from PRD §8 (normative), reconciled with Google's
# live help pages for the count minimums (see the module docstring).
# ─────────────────────────────────────────────────────────────────────────────

REGISTRY: Dict[str, CampaignSpec] = {
    "pmax": CampaignSpec(
        text={
            "headlines": TextFieldSpec(3, 15, 30, True, _G_PMAX_TEXT),
            "long_headlines": TextFieldSpec(1, 5, 90, True, _G_PMAX_TEXT),
            "descriptions": TextFieldSpec(2, 5, 90, True, _G_PMAX_TEXT),
        },
        images={
            "landscape": ImageSlotSpec("landscape", 20, True, True, _G_PMAX_ASSETS),
            "square": ImageSlotSpec("square", 20, True, True, _G_PMAX_ASSETS),
            "portrait": ImageSlotSpec("portrait", 20, False, True, _G_PMAX_ASSETS),
        },
        logos={
            "logos": ImageSlotSpec("logos", 5, True, True, _G_PMAX_ASSETS),
            # 4:1 landscape logo — field type absent repo-wide until P3 (17.5).
            "landscape_logo": ImageSlotSpec("landscape_logo", 5, False, False, _RESEARCH_2A),
        },
        business_name_max=25,
        total_image_cap=20,
        search_themes=(25, 80),
        video=VideoSpec(max_per_orientation=15, min_seconds=10, required=False,
                        verified=False, source=_RESEARCH_62),
        final_url_max=2048,
        policy=PolicyKnobs(on_image_text="forbid", logo_overlay="allow_warned",
                           video_gate="nudge"),
        short_description=TextFieldSpec(
            1, 5, 60, False,
            "PRD D6 — NOT in current Google docs (14528373, verified 2026-08-03); soft advisory",
        ),
    ),
    "demand_gen": CampaignSpec(
        text={
            "headlines": TextFieldSpec(1, 5, 40, True, _G_DG_TEXT),
            "descriptions": TextFieldSpec(1, 5, 90, True, _G_DG_TEXT),
        },
        images={
            "landscape": ImageSlotSpec("landscape", 20, True, True, _G_DG_SPECS),
            "square": ImageSlotSpec("square", 20, True, True, _G_DG_SPECS),
            "portrait": ImageSlotSpec("portrait", 20, False, True, _G_DG_SPECS),
            "tall_portrait": ImageSlotSpec("tall_portrait", 20, False, True, _G_DG_SPECS),
        },
        logos={
            "logos": ImageSlotSpec("logos", 5, True, True, _G_DG_SPECS),
        },
        business_name_max=25,
        total_image_cap=20,
        search_themes=None,
        video=VideoSpec(max_per_orientation=None, min_seconds=5, required=False,
                        verified=True, source=_G_DG_SPECS),
        final_url_max=2048,
        policy=PolicyKnobs(on_image_text="forbid", logo_overlay="forbid",
                           video_gate="nudge"),
        short_description=None,
    ),
    # RDA data shipped in P1 (costs nothing); FR6.1 *activates* it in P5. Story
    # 19.1 verified every number below against CURRENT Google docs and flipped the
    # confirmed ones to verified=True (see module docstring). Video stays
    # verified=False — the one figure Google does not firmly publish for RDA.
    "rda": CampaignSpec(
        text={
            "headlines": TextFieldSpec(1, 5, 30, True, _G_RDA_TEXT),
            # long_headline is a SINGULAR proto field ⇒ exactly 1 (min==max==1);
            # check_text_fields enforces the singular over-count as a HARD error
            # structurally, independent of the verified flag.
            "long_headlines": TextFieldSpec(1, 1, 90, True, _G_RDA_TEXT),
            "descriptions": TextFieldSpec(1, 5, 90, True, _G_RDA_TEXT),
        },
        images={
            # RDA marketing images are landscape (1.91:1) + square (1:1) ONLY —
            # the API has no portrait field for RDA (removed from the P1 seed).
            "landscape": ImageSlotSpec("landscape", 15, True, True, _G_RDA_ASSETS),
            "square": ImageSlotSpec("square", 15, True, True, _G_RDA_ASSETS),
        },
        logos={
            "logos": ImageSlotSpec("logos", 5, True, True, _G_RDA_ASSETS),
            "landscape_logo": ImageSlotSpec("landscape_logo", 5, False, True, _G_RDA_ASSETS),
        },
        business_name_max=25,
        # Combined marketing + square-marketing images max 15 (API), not 15/ratio.
        total_image_cap=15,
        search_themes=None,
        video=VideoSpec(max_per_orientation=5, min_seconds=None, required=False,
                        verified=False, source=_RDA_VIDEO_U),
        final_url_max=2048,
        policy=PolicyKnobs(on_image_text="forbid", logo_overlay="forbid",
                           video_gate="nudge"),
        short_description=None,
    ),
}

ENGINE = EngineConfig(near_dup_threshold=0.65, batch_tile_cap=20, batch_retry_max=2)

# ─────────────────────────────────────────────────────────────────────────────
# Copy-Workbench taxonomy (Epic 16, AD-2). ONE source of truth for the angle +
# tier vocabulary — served over the specs endpoint so the frontend never bakes
# its own list (the string analogue of the numeric-literal fence). ``creative_
# copy.py`` imports these for row validation; the wizards read them from the
# served ``taxonomy`` block.
#   angle = the persuasion strategy a copy row uses (FR1.7).
#   tier  = which Google-native slot the row targets (FR1.7).
# ─────────────────────────────────────────────────────────────────────────────

ANGLES: Tuple[str, ...] = (
    "promotional", "feature", "benefit", "urgency",
    "social_proof", "aspiration", "specificity",
)

TIERS: Tuple[str, ...] = (
    "headline", "long_headline", "description", "short_description",
)

# tier → the ``spec.text`` field whose char cap governs it (short_description
# shares the descriptions slot but is capped by ``spec.short_description``).
TIER_TEXTKEY: Dict[str, str] = {
    "headline": "headlines",
    "long_headline": "long_headlines",
    "description": "descriptions",
    "short_description": "descriptions",
}

# ``spec.text`` field → the tier a legacy (bare-string-list) draft maps its rows
# to. Taxonomy constants live beside ANGLES/TIERS (their single source, AD-2).
FIELD_TIER: Dict[str, str] = {
    "headlines": "headline",
    "long_headlines": "long_headline",
    "descriptions": "description",
}

# Bump when the shape or any value changes (surfaced by the endpoint + guard).
VERSION = "2026-08-04"


def get(campaign_type: str) -> CampaignSpec:
    """Resolve a ``CampaignSpec`` by type ('pmax' | 'demand_gen' | 'rda').

    This is the ONLY sanctioned way an enforcement path obtains its limits
    (fence F1). Raises ``KeyError`` for an unknown type."""
    return REGISTRY[campaign_type]


# ─────────────────────────────────────────────────────────────────────────────
# Serialization — one canonical shape used by BOTH the HTTP endpoint and the
# guard's round-trip check, so the wire form can never drift from the module.
# ─────────────────────────────────────────────────────────────────────────────

def _text_to_dict(t: TextFieldSpec) -> dict:
    return {
        "min_count": t.min_count,
        "max_count": t.max_count,
        "max_chars": t.max_chars,
        "verified": t.verified,
        "source": t.source,
    }


def _image_to_dict(i: ImageSlotSpec) -> dict:
    return {
        "slot": i.slot,
        "max_count": i.max_count,
        "required": i.required,
        "verified": i.verified,
        "source": i.source,
        # geometry echoed for the client (from IMAGE_SLOT_SPECS; None until the
        # slot lands in the crop pipeline). Not part of equality (derived).
        "geometry": i.geometry,
    }


def _video_to_dict(v: VideoSpec) -> dict:
    return {
        "max_per_orientation": v.max_per_orientation,
        "min_seconds": v.min_seconds,
        "required": v.required,
        "verified": v.verified,
        "source": v.source,
    }


def _spec_to_dict(s: CampaignSpec) -> dict:
    return {
        "text": {k: _text_to_dict(v) for k, v in s.text.items()},
        "images": {k: _image_to_dict(v) for k, v in s.images.items()},
        "logos": {k: _image_to_dict(v) for k, v in s.logos.items()},
        "business_name_max": s.business_name_max,
        "total_image_cap": s.total_image_cap,
        "search_themes": list(s.search_themes) if s.search_themes else None,
        "video": _video_to_dict(s.video),
        "final_url_max": s.final_url_max,
        "policy": {
            "on_image_text": s.policy.on_image_text,
            "logo_overlay": s.policy.logo_overlay,
            "video_gate": s.policy.video_gate,
        },
        "short_description": (
            _text_to_dict(s.short_description) if s.short_description else None
        ),
    }


def serialize_registry() -> Dict[str, dict]:
    """The registry as plain JSON-able dicts (campaign_type → spec dict)."""
    return {k: _spec_to_dict(v) for k, v in REGISTRY.items()}


def _text_from_dict(d: dict) -> TextFieldSpec:
    return TextFieldSpec(
        min_count=d["min_count"], max_count=d["max_count"], max_chars=d["max_chars"],
        verified=d["verified"], source=d["source"],
    )


def _image_from_dict(d: dict) -> ImageSlotSpec:
    return ImageSlotSpec(
        slot=d["slot"], max_count=d["max_count"], required=d["required"],
        verified=d["verified"], source=d["source"],
    )


def _video_from_dict(d: dict) -> VideoSpec:
    return VideoSpec(
        max_per_orientation=d["max_per_orientation"], min_seconds=d["min_seconds"],
        required=d["required"], verified=d["verified"], source=d["source"],
    )


def _spec_from_dict(d: dict) -> CampaignSpec:
    st = d.get("search_themes")
    return CampaignSpec(
        text={k: _text_from_dict(v) for k, v in d["text"].items()},
        images={k: _image_from_dict(v) for k, v in d["images"].items()},
        logos={k: _image_from_dict(v) for k, v in d["logos"].items()},
        business_name_max=d["business_name_max"],
        total_image_cap=d["total_image_cap"],
        search_themes=tuple(st) if st else None,
        video=_video_from_dict(d["video"]),
        final_url_max=d["final_url_max"],
        policy=PolicyKnobs(**d["policy"]),
        short_description=(
            _text_from_dict(d["short_description"]) if d.get("short_description") else None
        ),
    )


def deserialize_registry(data: Dict[str, dict]) -> Dict[str, CampaignSpec]:
    """Rebuild ``{type: CampaignSpec}`` from a serialized payload — the round-trip
    half of the CI guard. ``deserialize_registry(serialize_registry())`` deep-
    equals ``REGISTRY`` (frozen-dataclass ``__eq__``; geometry is a derived
    property, excluded from equality)."""
    return {k: _spec_from_dict(v) for k, v in data.items()}


# ─────────────────────────────────────────────────────────────────────────────
# Validation — the shared, registry-driven checks the orchestrators call. All
# limits come from the passed ``spec`` (no literals here either); ``verified=
# False`` violations land in ``warnings`` (soft), verified ones in ``errors``
# (hard). ValidationReport lives beside the registry per story 14.3.
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class ValidationReport:
    """Accumulates the outcome of validating a bundle against a ``CampaignSpec``.

    ``errors`` block the create (the caller raises); ``warnings`` ride the create
    response's existing ``warnings`` field and never block (FR1.3)."""

    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


_URL_RE = re.compile(r"^https?://[^\s/]+\.[^\s]+$", re.IGNORECASE)


def is_malformed_url(url: str) -> bool:
    """True if ``url`` is not a plausible absolute http(s) URL (FR1.4)."""
    return not bool(_URL_RE.match((url or "").strip()))


def extract_search_themes(audience_signals: Optional[List[Any]]) -> List[str]:
    """Pull the search-theme strings out of a bundle's ``audience_signals`` list.

    Mirrors ``pmax_orchestrator._signal_operation``: a signal is a search theme
    when it is a non-empty string, or a dict carrying ``search_theme``/``text``
    that is NOT a saved audience (``audience``/``audience_resource_name``)."""
    themes: List[str] = []
    for sig in audience_signals or []:
        if isinstance(sig, str):
            t = sig.strip()
            if t:
                themes.append(t)
        elif isinstance(sig, dict):
            if sig.get("audience_resource_name") or sig.get("audience"):
                continue
            t = str(sig.get("search_theme") or sig.get("text") or "").strip()
            if t:
                themes.append(t)
    return themes


def check_text_fields(bundle: Dict[str, Any], spec: CampaignSpec,
                      report: ValidationReport) -> None:
    """Count + char-length checks for every text field in ``spec.text``.
    Verified fields → errors; unverified → warnings. Empty entries are always
    errors."""
    for name, fs in spec.text.items():
        items = bundle.get(name) or []
        channel = report.errors if fs.verified else report.warnings
        n = len(items)
        if n < fs.min_count:
            channel.append(f"need ≥{fs.min_count} {name} (got {n})")
        if n > fs.max_count:
            # A SINGULAR field (max_count == 1, e.g. RDA long_headline, a singular
            # proto field) can never hold >1 — that is enforceable STRUCTURE, not a
            # soft aggregator limit, so it is a HARD error even when verified=False
            # (FR6.1: "2 long headlines rejected"). Other over-counts follow the
            # field's verified flag.
            over_channel = report.errors if fs.max_count == 1 else channel
            over_channel.append(f"too many {name}: {n} (max {fs.max_count})")
        for i, txt in enumerate(items):
            if not isinstance(txt, str) or not txt.strip():
                report.errors.append(f"{name}[{i}] is empty")
            elif len(txt) > fs.max_chars:
                channel.append(f"{name}[{i}] is {len(txt)} chars (max {fs.max_chars})")


def check_short_description(bundle: Dict[str, Any], spec: CampaignSpec,
                           report: ValidationReport) -> None:
    """PMax "≥N descriptions ≤ short.max_chars" soft rule (FR1.4/D6). Always a
    warning (short_description.verified is False — not in current Google docs)."""
    sd = spec.short_description
    if sd is None:
        return
    descriptions = bundle.get("descriptions") or []
    short = sum(1 for d in descriptions if isinstance(d, str) and len(d) <= sd.max_chars)
    if short < sd.min_count:
        channel = report.errors if sd.verified else report.warnings
        channel.append(
            f"need ≥{sd.min_count} description ≤{sd.max_chars} chars "
            f"(a short description); found {short}"
        )


def check_business_name(bundle: Dict[str, Any], spec: CampaignSpec,
                        report: ValidationReport, *, required: bool = True) -> None:
    name = bundle.get("business_name")
    if not name:
        if required:
            report.errors.append("'business_name' is required")
        return
    if len(str(name)) > spec.business_name_max:
        report.errors.append(
            f"business_name is {len(str(name))} chars (max {spec.business_name_max})"
        )


def check_image_caps(bundle: Dict[str, Any], spec: CampaignSpec,
                     report: ValidationReport) -> None:
    """Cross-slot marketing-image total (FR1.4 honesty #8) + logo cap. Reads the
    caps from the registry (``total_image_cap``, ``logos['logos'].max_count``)."""
    marketing = bundle.get("marketing_images") or {}
    if spec.total_image_cap is not None:
        total = sum(len(marketing.get(slot) or []) for slot in spec.images)
        if total > spec.total_image_cap:
            report.errors.append(
                f"too many images: {total} across ratios "
                f"(max {spec.total_image_cap} per asset group)"
            )
    logo_spec = spec.logos.get("logos")
    if logo_spec is not None:
        logos = bundle.get("logos") or []
        if len(logos) > logo_spec.max_count:
            report.errors.append(f"too many logos: {len(logos)} (max {logo_spec.max_count})")


def check_search_themes(bundle: Dict[str, Any], spec: CampaignSpec,
                        report: ValidationReport) -> None:
    """≤max_count search themes × ≤max_chars each (FR1.4). No-op when the type
    has no search themes (search_themes is None)."""
    if spec.search_themes is None:
        return
    max_count, max_chars = spec.search_themes
    themes = extract_search_themes(bundle.get("audience_signals"))
    if len(themes) > max_count:
        report.errors.append(f"too many search themes: {len(themes)} (max {max_count})")
    for t in themes:
        if len(t) > max_chars:
            report.errors.append(
                f"search theme is {len(t)} chars (max {max_chars}): {t[:30]!r}"
            )


def check_final_urls(bundle: Dict[str, Any], spec: CampaignSpec,
                     report: ValidationReport) -> None:
    """Final-URL presence + format + length (FR1.4). Presence is a hard error;
    a malformed or over-length URL is a hard error."""
    urls = bundle.get("final_urls") or []
    if not urls:
        report.errors.append("'final_urls' is required (at least one URL)")
        return
    for u in urls:
        if is_malformed_url(str(u)):
            report.errors.append(f"malformed final URL: {str(u)[:60]!r}")
        elif len(str(u)) > spec.final_url_max:
            report.errors.append(
                f"final URL is {len(str(u))} chars (max {spec.final_url_max})"
            )


# ─────────────────────────────────────────────────────────────────────────────
# Drafting — clamp tuples + prompt blocks derived from the SAME spec, so a
# drafter prompt can never promise a number the validator would reject (AD-1,
# FR1.5/FR1.6). Used by the draft routes now; by creative_copy.py in Epic 16.
# ─────────────────────────────────────────────────────────────────────────────

def draft_clamps(spec: CampaignSpec) -> Dict[str, Tuple[int, int, int]]:
    """``{field: (min_count, max_count, max_chars)}`` for server-side draft
    clamping — the exact numbers the validator enforces (one source)."""
    return {name: (fs.min_count, fs.max_count, fs.max_chars)
            for name, fs in spec.text.items()}


def hard_limits_prompt(spec: CampaignSpec) -> str:
    """The 'HARD LIMITS' prompt line, built from ``spec.text`` so the prompt can
    never promise a different char cap than the validator enforces (FR1.5)."""
    parts = [f"{name} ≤{fs.max_chars} chars each" for name, fs in spec.text.items()]
    return ("HARD LIMITS (Google rejects violations): " + ", ".join(parts)
            + f". business_name ≤{spec.business_name_max} chars.")


def deliberate_length_note(spec: CampaignSpec, field: str = "headlines") -> str:
    """FR1.5: tell the drafter to USE the (raised) char budget deliberately, not
    pad. Reads the cap from the registry — no literal — so the note tracks the
    real limit (e.g. DG headlines at 40)."""
    cap = spec.text[field].max_chars
    return (f"Use the full {cap}-char {field.rstrip('s')} budget DELIBERATELY for a "
            f"fuller, specific message — do NOT pad or repeat words just to fill it.")


def _clean_text_list(lst: Any) -> List[str]:
    return [s for s in (lst or []) if isinstance(s, str) and s.strip()]


def _normalize_draft_bundle(raw: Dict[str, Any]) -> Dict[str, Any]:
    """Map a WIZARD bundle onto the registry validators' expected keys (story
    15.2 PUT re-validation).

    The wizards persist camelCase, flat image slots, and a singular ``finalUrl``;
    the validators read snake_case, a nested ``marketing_images`` dict, and a
    ``final_urls`` list. This is best-effort — a draft may be incomplete, so a
    missing field just yields an empty value rather than raising. Empty text rows
    are dropped so a placeholder blank row never reads as "empty" noise."""
    marketing = raw.get("marketing_images")
    if not isinstance(marketing, dict):
        marketing = {
            "landscape": raw.get("landscape") or [],
            "square": raw.get("square") or [],
            "portrait": raw.get("portrait") or [],
            "tall_portrait": raw.get("tallPortrait") or raw.get("tall_portrait") or [],
        }
    final_urls = raw.get("final_urls")
    if not final_urls:
        fu = raw.get("finalUrl") or raw.get("final_url")
        final_urls = [fu] if fu else []
    audience = (
        raw.get("audience_signals")
        or raw.get("audienceSignals")
        or raw.get("searchThemes")
    )
    return {
        "headlines": _clean_text_list(raw.get("headlines")),
        "long_headlines": _clean_text_list(raw.get("long_headlines") or raw.get("longHeadlines")),
        "descriptions": _clean_text_list(raw.get("descriptions")),
        "business_name": raw.get("business_name") or raw.get("businessName"),
        "final_urls": final_urls,
        "logos": raw.get("logos") or [],
        "marketing_images": marketing,
        "audience_signals": audience,
    }


def validate_draft_bundle(raw_bundle: Dict[str, Any], campaign_type: str) -> List[str]:
    """Re-validate a saved draft against the registry (story 15.2 PUT AC).

    A draft is work-in-progress, so NOTHING blocks the save — every registry
    finding is returned as an advisory warning (soft limits per FR1.3, plus
    over-limit / still-incomplete notes) so the operator sees them before the
    real create ever runs. All numbers come from the passed spec (no literals)."""
    try:
        spec = get(campaign_type)
    except KeyError:
        return [f"unknown campaign_type {campaign_type!r}"]
    bundle = _normalize_draft_bundle(raw_bundle)
    report = ValidationReport()
    check_text_fields(bundle, spec, report)
    check_short_description(bundle, spec, report)
    check_business_name(bundle, spec, report, required=False)
    check_image_caps(bundle, spec, report)
    check_search_themes(bundle, spec, report)
    if bundle.get("final_urls"):
        check_final_urls(bundle, spec, report)
    # Draft save is never blocked: fold both channels into one advisory list.
    return report.errors + report.warnings


def on_image_text_instruction(spec: CampaignSpec) -> str:
    """Policy-driven on-image-text guidance (FR1.6/D3, NFR-C1). The campaign type
    never appears as a branch — only the registry knob does, so flipping the
    knob in a fixture changes the emitted prompt with zero code diff."""
    if spec.policy.on_image_text == "forbid":
        return ("Keep ALL text OUT of generated images — no overlaid words, "
                "captions, or logos baked into the photo.")
    return ("Text on images is permitted but will be WARNED and may be discounted "
            "— use it sparingly and only when it adds real value.")
