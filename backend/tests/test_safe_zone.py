"""Story 17.5 — safe-zone heuristic v1 (FR2.5, D1) + `landscape_logo` slot.

The detector is deterministic, Pillow-only, and makes ZERO network / vision-model
calls (the spy AC). Fixtures are synthesized in-memory:

  * a CENTERED subject passes every ratio;
  * an EDGE-positioned subject is flagged for 9:16 but NOT for 1:1.

Run: cd backend && .venv/bin/python -m unittest tests.test_safe_zone -v
"""

from __future__ import annotations

import socket
import unittest
from unittest import mock

from PIL import Image, ImageDraw

from google_ads.services.campaign import creative_images as ci

_SIZE = 320


def _canvas() -> Image.Image:
    return Image.new("RGB", (_SIZE, _SIZE), (8, 8, 8))


def _rect(x0f: float, y0f: float, x1f: float, y1f: float) -> Image.Image:
    """Bright rectangle at fractional coords on a dark canvas."""
    img = _canvas()
    d = ImageDraw.Draw(img)
    d.rectangle(
        [int(x0f * _SIZE), int(y0f * _SIZE), int(x1f * _SIZE), int(y1f * _SIZE)],
        fill=(240, 240, 240),
    )
    return img


# Aspect ratios (w/h) of the standard slots.
R_1x1 = 1.0
R_9x16 = 0.5625
R_4x5 = 0.8
R_16x9 = 16 / 9
R_4x1 = 4.0


class SubjectBbox(unittest.TestCase):
    def test_centered_bbox_is_central(self):
        bbox = ci.subject_bbox(_rect(0.44, 0.44, 0.56, 0.56))
        x0, y0, x1, y1 = bbox
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        self.assertAlmostEqual(cx, 0.5, delta=0.08)
        self.assertAlmostEqual(cy, 0.5, delta=0.08)

    def test_edge_bbox_is_right_of_center(self):
        x0, y0, x1, y1 = ci.subject_bbox(_rect(0.58, 0.40, 0.84, 0.60))
        self.assertGreater((x0 + x1) / 2, 0.6)  # subject centroid on the right


class CropSurvival(unittest.TestCase):
    def test_centered_subject_passes_all_ratios(self):
        img = _rect(0.44, 0.44, 0.56, 0.56)
        bbox = ci.subject_bbox(img)
        for aspect in (R_1x1, R_9x16, R_4x5, R_16x9, R_4x1):
            v = ci.crop_survival(img, aspect, bbox=bbox)
            self.assertFalse(v["flagged"], f"centered subject wrongly flagged for {aspect}")

    def test_edge_subject_flags_9x16_not_1x1(self):
        img = _rect(0.58, 0.40, 0.84, 0.60)
        bbox = ci.subject_bbox(img)
        self.assertFalse(ci.crop_survival(img, R_1x1, bbox=bbox)["flagged"])
        self.assertTrue(ci.crop_survival(img, R_9x16, bbox=bbox)["flagged"])

    def test_survival_is_a_fraction(self):
        v = ci.crop_survival(_rect(0.44, 0.44, 0.56, 0.56), R_1x1)
        self.assertGreaterEqual(v["survival"], 0.0)
        self.assertLessEqual(v["survival"], 1.0)


class ZeroNetwork(unittest.TestCase):
    """Spy: the detector must not open a socket or call a vision model."""

    def test_no_network_during_detection(self):
        def _boom(*a, **k):  # pragma: no cover - only fires on a regression
            raise AssertionError("safe-zone detector attempted a network call")

        with mock.patch.object(socket, "socket", _boom), \
                mock.patch.object(socket, "getaddrinfo", _boom):
            img = _rect(0.58, 0.40, 0.84, 0.60)
            ci.subject_bbox(img)
            ci.crop_survival(img, R_9x16)
            ci.safe_zone_for_slot  # attribute access only; helper opens from disk


class LandscapeLogoSlot(unittest.TestCase):
    def test_landscape_logo_geometry_added(self):
        spec = ci.IMAGE_SLOT_SPECS.get("landscape_logo")
        self.assertIsNotNone(spec, "landscape_logo not added to IMAGE_SLOT_SPECS")
        self.assertEqual(spec["aspect"], 4.0)
        self.assertEqual(spec["min_w"], 512)
        self.assertEqual(spec["min_h"], 128)
        self.assertEqual(spec["label"], "4:1")

    def test_landscape_logo_geometry_flows_to_registry(self):
        # Fence F2: creative_specs composes geometry BY IMPORT — adding the key
        # here makes the registry's landscape_logo geometry non-None.
        from app.services import creative_specs as cs
        pmax = cs.REGISTRY["pmax"]
        self.assertIsNotNone(pmax.logos["landscape_logo"].geometry)
        self.assertEqual(pmax.logos["landscape_logo"].aspect, 4.0)


class SafeZoneForSlot(unittest.TestCase):
    def test_verdict_shape_from_disk(self):
        import tempfile
        from pathlib import Path

        img = _rect(0.58, 0.40, 0.84, 0.60)
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "tile.png"
            img.save(p)
            verdict = ci.safe_zone_for_slot(p, "tall_portrait")
        self.assertEqual(verdict["slot"], "tall_portrait")
        self.assertIn("tall_portrait", verdict["slots"])
        self.assertTrue(verdict["slots"]["tall_portrait"]["flagged"])

    def test_missing_file_is_empty_not_raising(self):
        from pathlib import Path

        verdict = ci.safe_zone_for_slot(Path("/nonexistent/tile.png"), "square")
        self.assertEqual(verdict["slots"], {})


if __name__ == "__main__":
    unittest.main()
