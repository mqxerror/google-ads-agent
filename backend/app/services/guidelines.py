"""Service for reading / writing campaign guideline markdown files."""

from __future__ import annotations

import os
import re
import tempfile
from pathlib import Path

from app.config import settings
from app.models.schemas import GuidelineContentResponse, GuidelineFileResponse, GuidelineSection

_NEW_CAMPAIGN_TEMPLATE = """\
# Campaign Guidelines: {campaign_name}

## Campaign ID
{campaign_id}

## Global Rules
- Follow all account-level policies.

## Budget & Bidding
- Daily budget: TBD
- Bidding strategy: TBD

## Targeting
- Locations: TBD
- Languages: TBD

## Ad Copy Rules
- Headline guidelines: TBD
- Description guidelines: TBD

## Negative Keywords
- (none yet)

## Notes
- Created automatically.
"""


class GuidelinesService:
    """Manage guideline markdown files on disk."""

    def __init__(self, guidelines_dir: Path | None = None):
        self.dir = guidelines_dir or settings.GUIDELINES_DIR
        self.dir.mkdir(parents=True, exist_ok=True)

    # ── List files ──────────────────────────────────────────────────

    def list_files(self) -> list[GuidelineFileResponse]:
        """Return metadata for every ``.md`` file in the guidelines dir."""
        results: list[GuidelineFileResponse] = []
        for entry in sorted(self.dir.iterdir()):
            if entry.suffix.lower() != ".md":
                continue
            stat = entry.stat()
            content = entry.read_text(encoding="utf-8")
            sections = self.parse_sections(content)
            campaign_id, campaign_name = self._extract_campaign_info(content)
            results.append(
                GuidelineFileResponse(
                    filename=entry.name,
                    campaign_id=campaign_id,
                    campaign_name=campaign_name,
                    last_modified=stat.st_mtime,
                    sections=sections,
                )
            )
        return results

    # ── Read ────────────────────────────────────────────────────────

    def read_file(self, filename: str) -> GuidelineContentResponse:
        """Read a single guideline file."""
        path = self._safe_path(filename)
        content = path.read_text(encoding="utf-8")
        sections = self.parse_sections(content)
        return GuidelineContentResponse(
            filename=filename, content=content, sections=sections
        )

    # ── Write (atomic) ──────────────────────────────────────────────

    def write_file(self, filename: str, content: str) -> GuidelineContentResponse:
        """Atomically overwrite a guideline file."""
        path = self._safe_path(filename)
        # Write to a temp file in the same directory, then rename.
        fd, tmp = tempfile.mkstemp(dir=str(self.dir), suffix=".tmp")
        try:
            os.write(fd, content.encode("utf-8"))
            os.close(fd)
            # On Windows, we need to remove the target first if it exists.
            if path.exists():
                path.unlink()
            os.rename(tmp, str(path))
        except Exception:
            # Clean up temp file on error
            if os.path.exists(tmp):
                os.unlink(tmp)
            raise
        sections = self.parse_sections(content)
        return GuidelineContentResponse(
            filename=filename, content=content, sections=sections
        )

    # ── Create from template ────────────────────────────────────────

    def create_file(
        self,
        filename: str,
        campaign_id: str | None = None,
        campaign_name: str | None = None,
    ) -> GuidelineContentResponse:
        """Create a new guideline file from the built-in template."""
        path = self.dir / filename
        if path.exists():
            raise FileExistsError(f"File already exists: {filename}")
        content = _NEW_CAMPAIGN_TEMPLATE.format(
            campaign_name=campaign_name or "Unnamed Campaign",
            campaign_id=campaign_id or "N/A",
        )
        path.write_text(content, encoding="utf-8")
        sections = self.parse_sections(content)
        return GuidelineContentResponse(
            filename=filename, content=content, sections=sections
        )

    # ── Sections ────────────────────────────────────────────────────

    @staticmethod
    def parse_sections(content: str) -> list[GuidelineSection]:
        """Extract markdown headings as sections."""
        sections: list[GuidelineSection] = []
        lines = content.splitlines()
        heading_re = re.compile(r"^(#{1,6})\s+(.*)")
        for idx, line in enumerate(lines):
            m = heading_re.match(line)
            if m:
                level = len(m.group(1))
                heading = m.group(2).strip()
                sections.append(
                    GuidelineSection(
                        heading=heading,
                        level=level,
                        start_line=idx + 1,
                        end_line=idx + 1,  # updated below
                    )
                )
        # Fill end_line for each section (up to the next section or EOF)
        for i, sec in enumerate(sections):
            if i + 1 < len(sections):
                sec.end_line = sections[i + 1].start_line - 1
            else:
                sec.end_line = len(lines)
        return sections

    def get_global_rules(self, content: str) -> str | None:
        """Extract the 'Global Rules' section from content."""
        return self._extract_section(content, "Global Rules")

    def get_campaign_section(
        self, content: str, campaign_id_or_name: str
    ) -> str | None:
        """Extract a campaign-specific section by ID or name."""
        return self._extract_section(content, campaign_id_or_name)

    # ── Helpers ─────────────────────────────────────────────────────

    def _safe_path(self, filename: str) -> Path:
        """Resolve *filename* inside the guidelines dir, preventing traversal."""
        # Strip any path components -- only bare filename allowed
        safe = Path(filename).name
        path = self.dir / safe
        if not path.exists():
            raise FileNotFoundError(f"Guideline file not found: {safe}")
        return path

    @staticmethod
    def _extract_section(content: str, heading_text: str) -> str | None:
        """Return the body text under the first heading matching *heading_text*."""
        lines = content.splitlines()
        heading_re = re.compile(r"^(#{1,6})\s+(.*)")
        capture = False
        captured: list[str] = []
        capture_level = 0

        for line in lines:
            m = heading_re.match(line)
            if m:
                level = len(m.group(1))
                title = m.group(2).strip()
                if capture:
                    # Stop if we hit a heading at same or higher level
                    if level <= capture_level:
                        break
                elif title.lower() == heading_text.lower():
                    capture = True
                    capture_level = level
                    continue
            if capture:
                captured.append(line)

        if not captured:
            return None
        return "\n".join(captured).strip() or None

    @staticmethod
    def _extract_campaign_info(content: str) -> tuple[str | None, str | None]:
        """Try to pull campaign id and name from the file content."""
        campaign_id = None
        campaign_name = None

        # Look for "# Campaign Guidelines: <name>"
        m = re.search(r"^#\s+Campaign Guidelines:\s*(.+)", content, re.MULTILINE)
        if m:
            campaign_name = m.group(1).strip()

        # Look for "## Campaign ID\n<id>"
        m = re.search(r"^##\s+Campaign ID\s*\n+(.+)", content, re.MULTILINE)
        if m:
            val = m.group(1).strip()
            if val and val != "N/A":
                campaign_id = val

        return campaign_id, campaign_name
