#!/usr/bin/env python3
"""Regression tests for the northern permanent-snow texture seam."""

from __future__ import annotations

import unittest

from PIL import Image

from tools.builders import build_adiscord_terrain_snow as snow


class TerrainSnowSeamTests(unittest.TestCase):
    def test_polar_cap_edge_varies_across_longitude(self) -> None:
        width = 1024
        height = 400
        terrain = Image.new("P", (width, height), color=4)
        terrain.putpalette(
            [component for value in range(256) for component in (value, value, value)]
        )
        heightmap = Image.new("L", (width, height), color=100)
        provinces = Image.new("RGB", (width, height), color=(1, 2, 3))

        pixels = snow.generated_pixels(
            terrain,
            heightmap,
            provinces,
            {(9, 9, 9): 1},
        )
        edge_by_x = []
        for x in range(width):
            snowy_rows = [
                y
                for y in range(height)
                if pixels[y * width + x] in {snow.SNOW_MOUNTAIN, snow.SNOW_PLAIN}
            ]
            edge_by_x.append(max(snowy_rows))

        self.assertGreaterEqual(max(edge_by_x) - min(edge_by_x), 24)

    def test_no_single_row_contains_the_whole_polar_transition(self) -> None:
        width = 1024
        height = 400
        terrain = Image.new("P", (width, height), color=4)
        terrain.putpalette(
            [component for value in range(256) for component in (value, value, value)]
        )
        heightmap = Image.new("L", (width, height), color=100)
        provinces = Image.new("RGB", (width, height), color=(1, 2, 3))

        pixels = snow.generated_pixels(
            terrain,
            heightmap,
            provinces,
            {(9, 9, 9): 1},
        )
        snow_rows = [
            [
                pixels[y * width + x] in {snow.SNOW_MOUNTAIN, snow.SNOW_PLAIN}
                for x in range(width)
            ]
            for y in range(height)
        ]
        largest_transition = max(
            sum(first != second for first, second in zip(snow_rows[y - 1], snow_rows[y]))
            for y in range(1, height)
        )

        self.assertLess(largest_transition, width // 4)

    def test_validator_rejects_a_map_wide_horizontal_snow_cutoff(self) -> None:
        width = 200
        height = 400
        pixels = [
            snow.SNOW_PLAIN if y < snow.POLAR_CAP_Y else 4
            for y in range(height)
            for _x in range(width)
        ]

        issues = snow.polar_seam_issues(pixels, width, height)

        self.assertEqual(len(issues), 1)
        self.assertIn("horizontal permanent-snow seam", issues[0])


if __name__ == "__main__":
    unittest.main()
