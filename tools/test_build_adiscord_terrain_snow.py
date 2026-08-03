#!/usr/bin/env python3
"""Unit tests for permanent-snow terrain classification."""

from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from PIL import Image

import build_adiscord_terrain_snow as snow


class TerrainSnowTests(unittest.TestCase):
    def test_polar_cap_preserves_mountain_category(self) -> None:
        self.assertEqual(
            snow.classify_terrain(10, snow.POLAR_CAP_Y - 1, 100), snow.SNOW_MOUNTAIN
        )
        self.assertEqual(
            snow.classify_terrain(4, snow.POLAR_CAP_Y - 1, 100), snow.SNOW_PLAIN
        )

    def test_water_never_becomes_snow_terrain(self) -> None:
        self.assertEqual(snow.classify_terrain(15, 0, 255), 15)
        self.assertEqual(snow.classify_terrain(14, 0, 255), 14)

    def test_northern_and_high_mountains_remain_snowy(self) -> None:
        self.assertEqual(
            snow.classify_terrain(11, snow.POLAR_MOUNTAIN_Y - 1, 100),
            snow.SNOW_MOUNTAIN,
        )
        self.assertEqual(
            snow.classify_terrain(11, 1000, snow.PERMANENT_PEAK_HEIGHT),
            snow.SNOW_MOUNTAIN,
        )
        self.assertEqual(
            snow.classify_terrain(11, 1000, snow.PERMANENT_PEAK_HEIGHT - 1), 11
        )

    def test_old_generated_snow_is_removed_outside_target(self) -> None:
        self.assertEqual(snow.classify_terrain(snow.SNOW_MOUNTAIN, 1000, 100), 11)
        self.assertEqual(snow.classify_terrain(snow.SNOW_PLAIN, 1000, 100), 0)

    def test_polar_cap_matches_generated_climate_boundary(self) -> None:
        self.assertEqual(snow.POLAR_CAP_Y, 300)
        self.assertEqual(snow.classify_terrain(4, 299, 100), snow.SNOW_PLAIN)
        self.assertEqual(snow.classify_terrain(4, 300, 100), 4)

    def test_coverage_contract_accepts_generated_target(self) -> None:
        pixels = [snow.SNOW_MOUNTAIN] * 10_205 + [snow.SNOW_PLAIN] * 339_720
        self.assertEqual(snow.coverage_issues(pixels), [])

    def test_apply_stops_before_writing_rejected_coverage(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            terrain_path = root / "terrain.bmp"
            heightmap_path = root / "heightmap.bmp"
            definition_path = root / "00_terrain.txt"
            terrain = Image.new("P", (2, 2), color=4)
            terrain.putpalette(
                [value for channel in range(3) for value in range(256)]
            )
            terrain.save(terrain_path, format="BMP")
            Image.new("L", (2, 2), color=100).save(heightmap_path, format="BMP")
            definition_path.write_text(
                "snow_16 = { type = mountain color = { 16 } texture = 11 perm_snow = yes }\n"
                "plains_17 = { type = plains color = { 19 } texture = 0 perm_snow = yes }\n",
                encoding="utf-8",
            )
            original = terrain_path.read_bytes()
            with (
                patch.object(snow, "TERRAIN_PATH", terrain_path),
                patch.object(snow, "HEIGHTMAP_PATH", heightmap_path),
                patch.object(snow, "TERRAIN_DEFINITION_PATH", definition_path),
                patch.object(snow, "coverage_issues", return_value=["coverage rejected"]),
            ):
                with self.assertRaisesRegex(RuntimeError, "coverage rejected"):
                    snow.apply()
            self.assertEqual(terrain_path.read_bytes(), original)


if __name__ == "__main__":
    unittest.main()
