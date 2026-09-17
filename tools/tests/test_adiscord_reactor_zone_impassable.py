from __future__ import annotations

import re
import unittest
from pathlib import Path

from PIL import Image

from tools.builders import build_adiscord_new_states as builder
from tools.lib.paths import repository_root


ROOT = repository_root()
AMBIENT = ROOT / "map" / "ambient_object.txt"
HEIGHTMAP = ROOT / "map" / "heightmap.bmp"
EXCLUSION_LANDMARKS = (
    "ADISCORD_factory_entity",
    "ADISCORD_reactor_entity",
    "ADISCORD_reactor_2_entity",
)


def _height_at(heights: Image.Image, x: float, z: float) -> float:
    pixel = heights.getpixel((int(x), heights.height - 1 - int(z)))
    if isinstance(pixel, tuple):
        pixel = pixel[0]
    return pixel / 10


def _landmark_positions(source: str) -> list[tuple[str, float, float, float]]:
    rows: list[tuple[str, float, float, float]] = []
    current = None
    for match in re.finditer(r'type="([^"]+)"|position=\{\s*([^\n}]+)', source):
        if match.group(1):
            current = match.group(1)
            continue
        if current in EXCLUSION_LANDMARKS and match.group(2):
            x, y, z = map(float, match.group(2).split())
            rows.append((current, x, y, z))
    return rows


class ReactorZoneImpassableContract(unittest.TestCase):
    def test_reactor_zone_remains_impassable_after_legacy_regeneration(self) -> None:
        self.assertIn(125, builder.IMPASSABLE_LEGACY_STATE_IDS)
        source = builder.state_path(125).read_text(encoding="utf-8-sig", errors="strict")
        self.assertIn("impassable = yes", source)


class ExclusionZoneLandmarkHeightContract(unittest.TestCase):
    def test_wasteland_landmarks_use_absolute_terrain_height(self) -> None:
        positions = _landmark_positions(AMBIENT.read_text(encoding="utf-8"))
        self.assertEqual(
            [row[0] for row in positions],
            [
                "ADISCORD_factory_entity",
                "ADISCORD_factory_entity",
                "ADISCORD_factory_entity",
                "ADISCORD_reactor_entity",
                "ADISCORD_reactor_entity",
                "ADISCORD_reactor_2_entity",
            ],
        )
        with Image.open(HEIGHTMAP) as heights:
            for entity, x, y, z in positions:
                terrain = _height_at(heights, x, z)
                with self.subTest(entity=entity, x=x, z=z, y=y, terrain=terrain):
                    self.assertGreaterEqual(y, terrain - 0.5)
                    self.assertLessEqual(y, terrain + 6.0)


if __name__ == "__main__":
    unittest.main()
