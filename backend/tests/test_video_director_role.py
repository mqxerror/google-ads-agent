"""Video Director role + model-catalog origin/strengths (studio redesign §5, §10.2).

Pure in-process assertions on the ROLES registry and the model catalog —
no DB, no live calls. Verifies the new `video_director` persona is registered
with the right identity + the load-bearing prompt substrings, and that the
video catalog entries carry `origin`/`strengths` while image entries do not.

Run:  cd backend && .venv/bin/python -m unittest tests.test_video_director_role -v
"""

from __future__ import annotations

import unittest

from app.services.roles import ROLES
from app.services.model_catalog import get_model


class VideoDirectorRole(unittest.TestCase):
    def test_registered(self):
        self.assertIn("video_director", ROLES)

    def test_identity(self):
        role = ROLES["video_director"]
        self.assertEqual(role.name, "Video Director")
        self.assertEqual(role.avatar, "clapperboard")
        self.assertEqual(role.tools_focus, [])

    def test_prompt_encodes_pacing_and_scaffold(self):
        prompt = ROLES["video_director"].system_prompt
        for substr in ("2.5", "problem-led", "aspirational", "social-proof"):
            self.assertIn(substr, prompt, f"video_director prompt missing '{substr}'")


class CatalogOriginStrengths(unittest.TestCase):
    def test_video_entry_has_origin(self):
        self.assertEqual(get_model("veo3_1")["origin"], "Google (US)")

    def test_video_entry_has_strengths(self):
        self.assertIn("strengths", get_model("kling3_0"))

    def test_image_entry_lacks_origin(self):
        # IMAGE entries must NOT get the new video-only fields.
        self.assertNotIn("origin", get_model("nano_banana_2"))


if __name__ == "__main__":
    unittest.main()
