"""Local naval theatres must remain small without changing distant sea borders."""

from __future__ import annotations

import re
import unittest
from pathlib import Path

from tools.builders import build_adiscord_strategic_regions as builder
from tools.lib.localisation import sync_builder_english_localisation
from tools.validators.validate_adiscord_strategic_regions import parse_regions


ROOT = Path(__file__).resolve().parents[2]


class CoastalSeaRegionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        errors: list[str] = []
        cls.regions = parse_regions(errors)
        if errors:
            raise AssertionError(errors)
        cls.types, colors = builder.load_province_definitions()
        cls.physical = builder.load_province_adjacency(
            cls.types, colors, include_special_adjacencies=False
        )
        cls.navigable = builder.load_province_adjacency(cls.types, colors)
        cls.positions = builder.load_province_positions()
        cls.sea = {p for p, kind in cls.types.items() if kind == "sea"}

    def assert_region(self, region_id: int, provinces: set[int]) -> None:
        self.assertIn(region_id, set(self.regions), "local naval region was not generated")
        self.assertEqual(set(self.regions[region_id]["provinces"]), provinces)
        self.assertEqual(len(builder.connected_components(provinces, self.physical)), 1)
        self.assertTrue(provinces <= self.sea)

    def test_kefreite_coast_is_separate_from_the_eastern_ocean(self) -> None:
        self.assert_region(230, {13389, 14721, 15477})

    def test_stelander_approaches_are_a_compact_connected_region(self) -> None:
        self.assert_region(231, {13256, 13493, 13596, 14089, 14414, 15500})

    def test_canal_approaches_include_the_connected_northern_inlets(self) -> None:
        self.assert_region(
            232,
            {
                13393, 13801, 13961, 14011, 14153, 14225, 14234, 14274,
                14360, 14416, 14482, 14634, 14761, 14816, 14973, 15190,
                15590, 15723, 16030,
            },
        )

    def test_antolla_has_separate_western_and_nodrul_sectors(self) -> None:
        self.assert_region(228, {16262, 16264, 16265})
        self.assert_region(229, {16258, 16266, 16268})
        for region_id in (228, 229):
            self.assertIn("naval_terrain=water_shallow_sea", self.regions[region_id]["text"])
        self.assertIn(16266, self.navigable[14634], "the existing canal link must survive")

    def test_local_cuts_preserve_every_other_macro_ocean_boundary(self) -> None:
        ocean = builder.connected_components(self.sea, self.navigable)[0]
        macro = builder.partition_connected_sea(ocean, self.navigable, self.positions)
        dedicated = set().union(*builder.DEDICATED_SEA_PROVINCES.values())
        for region in builder.SEA_REGIONS:
            with self.subTest(region=region.region_id):
                self.assertEqual(
                    set(self.regions[region.region_id]["provinces"]),
                    macro[region.region_id] - dedicated,
                )

    def test_all_naval_regions_are_connected_and_cover_the_ocean_once(self) -> None:
        seen: set[int] = set()
        ids = [region.region_id for region in (*builder.REGIONS, *builder.ALL_SEA_REGIONS)]
        self.assertEqual(len(ids), len(set(ids)))
        for region in builder.ALL_SEA_REGIONS:
            provinces = set(self.regions[region.region_id]["provinces"])
            with self.subTest(region=region.region_id):
                self.assertFalse(seen & provinces)
                self.assertTrue(provinces)
                self.assertEqual(len(builder.connected_components(provinces, self.physical)), 1)
            seen.update(provinces)
        self.assertEqual(seen, builder.connected_components(self.sea, self.navigable)[0])

    def test_both_localisations_and_weather_markers_cover_new_regions(self) -> None:
        for language in ("russian", "english"):
            path = ROOT / f"localisation/replace/strategic_region_names_l_{language}.yml"
            self.assertTrue(path.read_bytes().startswith(b"\xef\xbb\xbf"))
            names = dict(re.findall(
                r'^\s*(STRATEGICREGION_\d+):(?:\d+)?\s*"(.+)"',
                path.read_text(encoding="utf-8-sig"),
                re.M,
            ))
            for region_id in range(228, 233):
                self.assertIn(f"STRATEGICREGION_{region_id}", names)
        weather_ids = {
            int(line.split(";", 1)[0])
            for line in (ROOT / "map/weatherpositions.txt").read_text().splitlines()
            if line.strip()
        }
        self.assertTrue(set(range(228, 233)) <= weather_ids)
        self.assertEqual(sync_builder_english_localisation(
            ROOT, "tools.builders.build_adiscord_strategic_regions", apply=False
        ), 0)


if __name__ == "__main__":
    unittest.main()
