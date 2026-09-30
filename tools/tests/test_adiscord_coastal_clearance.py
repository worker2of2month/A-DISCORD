#!/usr/bin/env python3
"""Shoreline clearance shared by tree and city-model generators."""

from __future__ import annotations

import unittest

import numpy as np
from PIL import Image

from tools.lib import coastal_clearance as clearance
from tools.lib.paths import repository_root


ROOT = repository_root()


class CoastalClearanceTests(unittest.TestCase):
    def test_urban_band_is_two_pixels_wide(self) -> None:
        water = np.zeros((9, 9), dtype=bool)
        water[:, :2] = True
        blocked = clearance.urban_blocked(water)
        self.assertTrue(blocked[4, 2] and blocked[4, 3])
        self.assertFalse(blocked[4, 4])

    def test_tree_cells_touching_band_are_blocked(self) -> None:
        water = np.zeros((12, 12), dtype=bool)
        water[:, :1] = True
        cells = clearance.tree_cells_blocked(water, 4, 4)
        self.assertTrue(cells[:, 0].all())
        self.assertFalse(cells[:, 2:].any())

    def test_live_map_has_no_city_or_tree_on_the_waterline(self) -> None:
        with Image.open(ROOT / "map/provinces.bmp") as provinces:
            rgb = np.asarray(provinces.convert("RGB"))
        definition = ROOT / "map/definition.csv"
        water = clearance.water_mask(rgb, clearance.water_colours(definition))
        band = clearance.urban_blocked(water, rgb, definition) & ~water
        with Image.open(ROOT / "map/terrain.bmp") as terrain:
            urban = np.asarray(terrain) == 13
        self.assertEqual(int((urban & band).sum()), 0)
        with Image.open(ROOT / "map/trees.bmp") as trees:
            tree_pixels = np.asarray(trees)
        cells = clearance.tree_cells_blocked(water, tree_pixels.shape[1], tree_pixels.shape[0])
        self.assertEqual(int((cells & (tree_pixels > 0)).sum()), 0)


if __name__ == "__main__":
    unittest.main()
