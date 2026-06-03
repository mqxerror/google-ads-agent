"""Changelog endpoint — reads markdown files from data/changelog/.

Entry format (each .md file):

    ---
    date: 2026-04-22
    type: fix          # fix | feature | improvement | research | breaking
    title: Campaign memory pollution cleanup
    tags: [memory, currency]
    ---

    Markdown body explaining what changed for the user (no code).

The endpoint sorts by date descending so the newest work shows first.
"""

from __future__ import annotations

import logging
import re
from datetime import date as _date
from pathlib import Path

from fastapi import APIRouter
from pydantic import BaseModel

from app.config import settings

logger = logging.getLogger(__name__)

CHANGELOG_DIR = settings.DATA_DIR / "changelog"
CHANGELOG_DIR.mkdir(parents=True, exist_ok=True)

router = APIRouter(prefix="/api/changelog", tags=["changelog"])


# Allowed entry types. Anything else falls back to "improvement".
VALID_TYPES = {"fix", "feature", "improvement", "research", "breaking"}


class ChangelogEntry(BaseModel):
    id: str            # the filename without extension
    date: str          # YYYY-MM-DD
    type: str
    title: str
    tags: list[str] = []
    body: str          # markdown


_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n(.*)$", re.DOTALL)


def _parse_entry(path: Path) -> ChangelogEntry | None:
    """Parse a single markdown file with YAML-ish frontmatter.

    Kept deliberately simple — we don't need a full YAML parser for our
    purposes (date / title / type / tags), and avoiding a yaml dep keeps the
    backend lighter.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except Exception:
        return None

    m = _FRONTMATTER_RE.match(text)
    if not m:
        # No frontmatter — treat the whole file as body and use the filename
        # for ordering. Filename should start with YYYY-MM-DD for sort to work.
        date_match = re.match(r"(\d{4}-\d{2}-\d{2})", path.stem)
        return ChangelogEntry(
            id=path.stem,
            date=date_match.group(1) if date_match else "1970-01-01",
            type="improvement",
            title=path.stem.replace("-", " ").title(),
            body=text.strip(),
        )

    front, body = m.group(1), m.group(2).strip()
    fields: dict[str, str | list[str]] = {}
    for raw_line in front.splitlines():
        line = raw_line.strip()
        if not line or ":" not in line:
            continue
        key, _, value = line.partition(":")
        key = key.strip().lower()
        value = value.strip()
        # Inline list: tags: [a, b, c]
        if value.startswith("[") and value.endswith("]"):
            items = [s.strip().strip("'\"") for s in value[1:-1].split(",") if s.strip()]
            fields[key] = items
        else:
            fields[key] = value.strip("'\"")

    raw_date = str(fields.get("date", "1970-01-01"))
    # Allow YYYY-MM-DD or full ISO timestamp
    date_str = raw_date[:10]

    raw_type = str(fields.get("type", "improvement")).lower()
    if raw_type not in VALID_TYPES:
        raw_type = "improvement"

    raw_tags = fields.get("tags", [])
    if isinstance(raw_tags, str):
        raw_tags = [t.strip() for t in raw_tags.split(",") if t.strip()]

    return ChangelogEntry(
        id=path.stem,
        date=date_str,
        type=raw_type,
        title=str(fields.get("title", path.stem)),
        tags=list(raw_tags),
        body=body,
    )


@router.get("", response_model=list[ChangelogEntry])
async def list_entries(
    limit: int = 100,
    type: str | None = None,
    tag: str | None = None,
    q: str | None = None,
):
    """List changelog entries newest first. Filters are optional."""
    entries: list[ChangelogEntry] = []
    for path in sorted(CHANGELOG_DIR.glob("*.md")):
        entry = _parse_entry(path)
        if entry is None:
            continue
        if type and entry.type != type:
            continue
        if tag and tag not in entry.tags:
            continue
        if q:
            needle = q.lower()
            if needle not in entry.title.lower() and needle not in entry.body.lower():
                continue
        entries.append(entry)

    # Stable sort: date desc, then id desc as a tiebreaker
    entries.sort(key=lambda e: (e.date, e.id), reverse=True)
    return entries[:limit]


@router.get("/types")
async def list_types():
    """Return the set of types currently used + the union of all tags."""
    types: set[str] = set()
    tags: set[str] = set()
    for path in CHANGELOG_DIR.glob("*.md"):
        entry = _parse_entry(path)
        if not entry:
            continue
        types.add(entry.type)
        tags.update(entry.tags)
    return {"types": sorted(types), "tags": sorted(tags)}
