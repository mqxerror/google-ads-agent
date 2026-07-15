"""WS3 — role-notes freshness parser.

NO live calls: role_notes_age_days is pure header parsing over a string (no CLI,
no network, no DB). Asserts age-from-header for fresh / stale / unparseable
bodies against the EXACT header format save_role_notes writes
(`**Last updated:** YYYY-MM-DD HH:MM`).

Run:  cd backend && .venv/bin/python -m unittest tests.test_role_notes_freshness -v
"""

from __future__ import annotations

import unittest
from datetime import datetime, timedelta

from app.services.campaign_memory import (
    ROLE_NOTES_STALE_DAYS,
    role_notes_age_days,
)


def _body(dt: datetime) -> str:
    # Mirror the header save_role_notes/append_role_notes write.
    return f"# PPC Strategist Notes\n\n**Last updated:** {dt.strftime('%Y-%m-%d %H:%M')}\n\nsome findings"


class RoleNotesAgeDays(unittest.TestCase):
    def test_fresh_date_small_age(self):
        age, date_str = role_notes_age_days(_body(datetime.now() - timedelta(hours=2)))
        self.assertEqual(age, 0)
        self.assertIsNotNone(date_str)
        self.assertLessEqual(age, ROLE_NOTES_STALE_DAYS)

    def test_old_date_over_threshold(self):
        age, date_str = role_notes_age_days(_body(datetime.now() - timedelta(days=30)))
        self.assertIsNotNone(age)
        self.assertGreater(age, ROLE_NOTES_STALE_DAYS)
        self.assertIsNotNone(date_str)

    def test_garbage_returns_none(self):
        age, date_str = role_notes_age_days("# Notes\n\nno header here at all")
        self.assertIsNone(age)
        self.assertIsNone(date_str)

    def test_unparseable_timestamp_returns_none_age_keeps_string(self):
        # Header present but the date is malformed → age None, raw string kept.
        body = "# Notes\n\n**Last updated:** 2026-13-99 99:99\n\nx"
        age, date_str = role_notes_age_days(body)
        self.assertIsNone(age)


if __name__ == "__main__":
    unittest.main()
