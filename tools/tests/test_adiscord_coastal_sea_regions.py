"""Local naval theatres must remain small without changing distant sea borders."""

from __future__ import annotations

import re
import unittest
from pathlib import Path

import numpy as np
from PIL import Image

from tools.builders import build_adiscord_strategic_regions as builder
from tools.builders import build_adiscord_map_buildings as buildings
from tools.builders import build_adiscord_coastal_geography as geography
from tools.builders import build_adiscord_new_states as states
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

    def test_island_bridges_join_land_through_the_actual_shared_sea(self) -> None:
        for first, second in ((16709, 16710), (16710, 16712)):
            self.assertNotIn(second, self.physical[first])
            self.assertIn(second, self.navigable[first])
            self.assertIn(first, self.navigable[second])
            self.assertIn(14089, self.physical[first] & self.physical[second])
        self.assertEqual(
            builder.connected_components({16709, 16710, 16712}, self.navigable),
            [{16709, 16710, 16712}],
        )

    def test_coastal_additions_have_native_ports_in_their_own_land_provinces(self) -> None:
        colors = buildings.load_province_by_color(ROOT)
        state_by_province = buildings.load_state_by_province(ROOT)
        found = set()
        with Image.open(ROOT / "map/provinces.bmp") as provinces:
            for line in (ROOT / "map/buildings.txt").read_text().splitlines():
                fields = line.split(";")
                if fields[1] != "naval_base_spawn":
                    continue
                x = round(float(fields[2]))
                y = provinces.height - 1 - round(float(fields[4]))
                province = colors[provinces.getpixel((x, y))]
                if province not in buildings.COASTAL_ADDITION_PROVINCES:
                    continue
                found.add(province)
                self.assertEqual(int(fields[0]), state_by_province[province])
                self.assertEqual(self.types[int(fields[6])], "sea")
                self.assertIn(int(fields[6]), self.physical[province])
        coastal = {
            int(fields[0])
            for line in (ROOT / "map/definition.csv").read_text().splitlines()
            if len(fields := line.split(";")) >= 8 and fields[5] == "true"
        }
        self.assertEqual(found, buildings.COASTAL_ADDITION_PROVINCES & coastal)

    def test_new_cities_have_urban_rasters_victory_points_and_stable_state_outputs(self) -> None:
        colors = buildings.load_province_by_color(ROOT)
        new_cities = set(range(16713, 16722)) | {
            province for province, _value in states.SOUTHERN_CITY_POINTS.values()
        }
        with (
            Image.open(ROOT / "map/provinces.bmp") as provinces,
            Image.open(ROOT / "map/terrain.bmp") as terrain,
            Image.open(ROOT / "map/cities.bmp") as cities,
        ):
            self.assertEqual(cities.mode, "P")
            seen = set()
            for y in range(provinces.height):
                for x in range(provinces.width):
                    province = colors.get(provinces.getpixel((x, y)))
                    if province in new_cities:
                        seen.add(province)
                        self.assertEqual(terrain.getpixel((x, y)), 13)
                        self.assertEqual(cities.getpixel((x, y)), 2 if province in geography.ARAB_CITIES else 15)
            self.assertEqual(seen, new_cities)
        for state_id, points in states.COASTAL_CITY_POINTS.items():
            source = states.state_path(state_id).read_text(encoding="utf-8-sig")
            for province, _value in points:
                self.assertRegex(source, rf"victory_points\s*=\s*\{{\s*{province}\s+[1-9]\d*\s*\}}")
        for path, expected in states.coastal_city_state_plan().items():
            self.assertEqual(path.read_bytes(), expected, str(path))

    def test_southern_cities_are_small_connected_provinces(self) -> None:
        counts = {}
        with Image.open(ROOT / "map/provinces.bmp") as image:
            color_counts = {color: count for count, color in image.getcolors(image.width * image.height)}
        for entry in states.SOUTHERN_CITIES:
            count = color_counts[tuple(entry["rgb"])]
            self.assertGreaterEqual(count, 9)
            self.assertLessEqual(count, 28)
            self.assertIn(entry["parent"], self.physical[entry["province"]])
            sectors = {entry["parent"], *(sector["province"] for sector in entry.get("sectors", ()))}
            self.assertGreaterEqual(len(self.physical[entry["province"]] & sectors), 3)
            counts[entry["province"]] = count
        self.assertEqual(len(counts), 20)

    def test_svetlogorye_massif_is_on_the_mainland_with_snowy_peaks(self) -> None:
        memberships = builder.load_states()
        self.assertTrue(geography.RELIEF_PROVINCES <= memberships[67] | memberships[690])
        self.assertEqual(len(builder.connected_components(set(geography.RELIEF_PROVINCES), self.physical)), 1)
        definitions = {
            int(fields[0]): fields
            for line in (ROOT / "map/definition.csv").read_text().splitlines()
            if len(fields := line.split(";")) >= 8
        }
        with (
            Image.open(ROOT / "map/provinces.bmp") as provinces,
            Image.open(ROOT / "map/heightmap.bmp") as heights,
            Image.open(ROOT / "map/terrain.bmp") as terrain,
        ):
            rgb = np.array(provinces)
            elevation = np.array(heights)
            terrain_pixels = np.array(terrain)
            masks = []
            for province in geography.RELIEF_PROVINCES:
                fields = definitions[province]
                self.assertEqual(fields[4], "land")
                mask = np.all(rgb == tuple(map(int, fields[1:4])), axis=2)
                masks.append(mask)
                allowed = {"desert": {3}, "hills": {2}, "mountain": {18, 11, 16}}[fields[6]]
                self.assertTrue(set(np.unique(terrain_pixels[mask])) <= allowed, f"province {province} spills into another graphical terrain class")
                if fields[6] == "mountain":
                    self.assertTrue(np.all(terrain_pixels[mask & (elevation >= 205)] == 16))
            mask = np.logical_or.reduce(masks)
            self.assertGreaterEqual(int(elevation[mask].max()), 220)
            self.assertGreaterEqual(int(elevation[mask].min()), 97)
            self.assertEqual(set(np.unique(terrain_pixels[mask])), {2, 3, 11, 16, 18})
            kinds = [definitions[province][6] for province in geography.RELIEF_PROVINCES]
            self.assertGreaterEqual(kinds.count("mountain"), 4)
            self.assertGreaterEqual(kinds.count("hills"), 4)
            self.assertIn("desert", kinds)
            interior = mask.copy()
            interior[1:] &= mask[:-1]
            interior[:-1] &= mask[1:]
            interior[:, 1:] &= mask[:, :-1]
            interior[:, :-1] &= mask[:, 1:]
            for axis in (0, 1):
                pairs = (interior[1:] & interior[:-1]) if axis == 0 else (interior[:, 1:] & interior[:, :-1])
                slopes = np.abs(np.diff(elevation.astype(np.int16), axis=axis))
                self.assertLessEqual(int(slopes[pairs].max()), 6)
            self.assertTrue(np.array_equal(geography.mountain_heights(mask, elevation), elevation))
            for line in (ROOT / "map/unitstacks.txt").read_text().splitlines():
                fields = line.split(";")
                if int(fields[0]) in geography.RELIEF_PROVINCES:
                    x = round(float(fields[2]))
                    y = heights.height - 1 - round(float(fields[4]))
                    self.assertAlmostEqual(float(fields[3]), elevation[y, x] / 10)
        lines, _mismatches = buildings.audit_buildings(ROOT)
        self.assertEqual(buildings.mountain_building_heights(ROOT, lines)[1], [])

    def test_railways_cross_adjacent_southern_sectors(self) -> None:
        affected = set()
        for city in states.SOUTHERN_CITIES:
            affected.update((city["parent"], city["province"]))
            affected.update(sector["province"] for sector in city.get("sectors", ()))
        for line in (ROOT / "map/railways.txt").read_text().splitlines():
            fields = list(map(int, line.split()))
            if len(fields) < 3 or not affected.intersection(fields[2:]):
                continue
            self.assertEqual(fields[1], len(fields) - 2)
            for first, second in zip(fields[2:], fields[3:]):
                if {first, second} & affected:
                    self.assertIn(second, self.physical[first], f"railway {first}-{second}")

    def test_southern_capital_districts_conserve_population_and_industry(self) -> None:
        original_populations = {241: 135000, 253: 105000, 260: 72000, 275: 145000, 283: 112000, 294: 128000, 300: 118000}
        memberships = builder.load_states()
        for capital, (district, _city_population, _rural_population, provinces) in states.SOUTHERN_CAPITAL_DISTRICTS.items():
            city_source = states.state_path(capital).read_text(encoding="utf-8")
            rural_source = states.state_path(district).read_text(encoding="utf-8")
            total = sum(int(re.search(r"\bmanpower\s*=\s*(\d+)", source)[1]) for source in (city_source, rural_source))
            self.assertEqual(total, original_populations[capital])
            for building, amount in (("industrial_complex", 2), ("arms_factory", 1), ("air_base", 1)):
                levels = re.findall(rf"\b{building}\s*=\s*(\d+)", city_source + rural_source)
                self.assertEqual(sum(map(int, levels)), amount)
            self.assertEqual(len(memberships[capital]), 1)
            self.assertEqual(len(builder.connected_components(memberships[district], self.physical)), 1)
            province, value = states.SOUTHERN_CITY_POINTS[capital]
            self.assertEqual(memberships[capital], {province})
            self.assertRegex(city_source, rf"victory_points\s*=\s*\{{\s*{province}\s+{value}\s*\}}")
        for path, expected in states.southern_settlement_plan().items():
            self.assertEqual(path.read_bytes(), expected, str(path))

    def test_orval_and_arsal_have_connected_mainland_and_preserved_capitals(self) -> None:
        memberships = builder.load_states()
        for tag, capital in (("ORV", 455), ("ARS", 441)):
            provinces = set()
            for path in (ROOT / "history/states").glob("*.txt"):
                source = path.read_text(encoding="utf-8-sig")
                if re.search(rf"\bowner\s*=\s*{tag}\b", source):
                    state_id = int(re.search(r"\bid\s*=\s*(\d+)", source)[1])
                    provinces.update(memberships[state_id])
            self.assertEqual(len(builder.connected_components(provinces, self.physical)), 1)
            self.assertTrue(memberships[capital] <= provinces)

    def test_large_city_splits_preserve_population_and_industry(self) -> None:
        for parent, city, population in ((290, 699, 29510), (689, 700, 120000), (691, 701, 280000)):
            sources = [states.state_path(state).read_text() for state in (parent, city)]
            self.assertEqual(sum(int(re.search(r"\bmanpower\s*=\s*(\d+)", source)[1]) for source in sources), population)
        for state_ids, civilian, military in (((689, 700), 1, 2), ((691, 701), 1, 0)):
            source = "\n".join(states.state_path(state).read_text() for state in state_ids)
            self.assertEqual(sum(map(int, re.findall(r"\bindustrial_complex\s*=\s*(\d+)", source))), civilian)
            self.assertEqual(sum(map(int, re.findall(r"\barms_factory\s*=\s*(\d+)", source))), military)

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
