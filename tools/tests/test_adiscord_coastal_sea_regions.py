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
from tools.lib import city_terrains
from tools.lib import coastal_clearance as clearance
from tools.lib.localisation import sync_builder_english_localisation
from tools.validators.validate_adiscord_strategic_regions import parse_regions


ROOT = Path(__file__).resolve().parents[2]


class ProvinceCornerTests(unittest.TestCase):
    def test_border_budget_counts_separate_contacts_and_the_world_seam(self):
        stripes = np.array([[1, 2, 1, 2], [1, 2, 1, 2]], dtype=np.uint16)
        self.assertEqual(geography.province_border_count(stripes), 4)
        islands = np.ones((5, 7), dtype=np.uint16)
        islands[2, (1, 4)] = 2
        self.assertEqual(geography.province_border_count(islands), 2)

    def test_ishait_front_has_distinct_northern_and_southern_approaches(self):
        definitions = {
            int(fields[0]): tuple(map(int, fields[1:4]))
            for line in (ROOT / "map/definition.csv").read_text().splitlines()
            if len(fields := line.split(";")) >= 8
        }
        with Image.open(ROOT / "map/provinces.bmp") as image:
            grid = geography.province_grid(np.asarray(image), definitions)
        neighbours = geography.province_neighbours(grid)
        enemy = {48, 85}
        self.assertEqual(set(neighbours[16372]) - enemy, {6, 51})
        self.assertNotIn(48, neighbours[6])
        for first, second in zip((11496, 6, 16372, 51, 108), (6, 16372, 51, 108, 4)):
            self.assertIn(second, neighbours[first])
        for approach in (6, 51):
            edges = sum(int(((a == 16372) & (b == approach)).sum()) for a, b in (
                (grid[:, :-1], grid[:, 1:]), (grid[:, 1:], grid[:, :-1]),
                (grid[:-1, :], grid[1:, :]), (grid[1:, :], grid[:-1, :]),
            ))
            self.assertGreaterEqual(edges, 3, approach)

    def test_yubor_contacts_have_broad_borders(self):
        definitions = {
            int(fields[0]): tuple(map(int, fields[1:4]))
            for line in (ROOT / "map/definition.csv").read_text().splitlines()
            if len(fields := line.split(";")) >= 8
        }
        with Image.open(ROOT / "map/provinces.bmp") as image:
            rgb = np.asarray(image)
        for first_id, second_id in (
            (6, 85), (118, 129), (28, 127), (51, 108),
            (88, 11496), (33, 16649), (81, 16646), (83, 92),
        ):
            with self.subTest(border=(first_id, second_id)):
                first = np.all(rgb == definitions[first_id], axis=2)
                second = np.all(rgb == definitions[second_id], axis=2)
                shared_edges = sum(int(edges.sum()) for edges in (
                    first[:, :-1] & second[:, 1:],
                    second[:, :-1] & first[:, 1:],
                    first[:-1, :] & second[1:, :],
                    second[:-1, :] & first[1:, :],
                ))
                self.assertGreaterEqual(shared_edges, 7)

    def test_repaired_provinces_and_their_donors_remain_connected(self):
        from scipy.ndimage import label

        definitions = {
            int(fields[0]): tuple(map(int, fields[1:4]))
            for line in (ROOT / "map/definition.csv").read_text().splitlines()
            if len(fields := line.split(";")) >= 8
        }
        with Image.open(ROOT / "map/provinces.bmp") as image:
            rgb = np.asarray(image)
        provinces = {
            6, 28, 33, 48, 51, 81, 83, 85, 88, 92, 103, 108, 118, 124, 127, 129, 131,
            729, 971, 7283, 9633, 10926, 11496, 16372, 16597, 16616, 16646, 16649,
            16746, 16872, 16877,
        }
        for province in sorted(provinces):
            with self.subTest(province=province):
                self.assertEqual(label(np.all(rgb == definitions[province], axis=2))[1], 1)

    def test_repaired_unit_anchors_stay_in_their_provinces(self):
        definitions = {
            int(fields[0]): tuple(map(int, fields[1:4]))
            for line in (ROOT / "map/definition.csv").read_text().splitlines()
            if len(fields := line.split(";")) >= 8
        }
        with Image.open(ROOT / "map/provinces.bmp") as image:
            for line in (ROOT / "map/unitstacks.txt").read_text().splitlines():
                fields = line.split(";")
                province = int(fields[0])
                if province not in geography.PROVINCE_REPAIR_PROVINCES:
                    continue
                x = float(fields[2])
                y = image.height - 1 - float(fields[4])
                with self.subTest(province=province, slot=fields[1]):
                    self.assertEqual(image.getpixel((round(x), round(y))), definitions[province])
                    self.assertEqual(image.getpixel((int(x), int(y))), definitions[province])

    @staticmethod
    def reconciled_anchors():
        """Return the province grid, province kinds, the coastal anchor scope and its unit stacks."""
        from collections import defaultdict

        rows = [line.split(";") for line in (ROOT / "map/definition.csv").read_text().splitlines()]
        definitions = {int(fields[0]): tuple(map(int, fields[1:4])) for fields in rows if len(fields) >= 8}
        kinds = {int(fields[0]): fields[4] for fields in rows if len(fields) >= 8}
        with Image.open(ROOT / "map/provinces.bmp") as image:
            grid = geography.province_grid(np.asarray(image.convert("RGB")), definitions)
        neighbours = geography.province_neighbours(grid)
        touched = geography.ANCHOR_TOUCHED_PROVINCES
        scope = set(touched) | {neighbour for province in touched for neighbour in neighbours[province]}
        scope |= geography.DISPLACED_PROVINCES | set(geography.ANCHOR_REFERENCES) | geography.ANCHOR_RECONCILED_PROVINCES
        stacks = defaultdict(dict)
        for line in (ROOT / "map/unitstacks.txt").read_text().splitlines():
            fields = line.split(";")
            stacks[int(fields[0])][int(fields[1])] = tuple(map(float, fields[2:6]))
        return grid, kinds, scope, stacks

    def test_reconciled_land_armies_stand_in_the_province_interior(self):
        from scipy.ndimage import distance_transform_edt, find_objects

        grid, kinds, scope, stacks = self.reconciled_anchors()
        boxes = find_objects(grid)
        for province in sorted(scope):
            if kinds.get(province) != "land" or 0 not in stacks[province]:
                continue
            box = boxes[province - 1]
            # A snapped anchor sits one pixel from the border it crossed.
            inside = np.pad(grid[box] == province, 1)
            depth = distance_transform_edt(inside)
            ys, xs = np.nonzero(inside)
            deep_y, deep_x = np.nonzero(depth >= 0.7 * depth.max())
            nearest = int(np.argmin((deep_x - xs.mean()) ** 2 + (deep_y - ys.mean()) ** 2))
            x_value, _height, z_value, _rotation = stacks[province][0]
            x = round(x_value) - box[1].start + 1
            y = grid.shape[0] - 1 - round(z_value) - box[0].start + 1
            with self.subTest(province=province):
                self.assertTrue(0 <= y < inside.shape[0] and 0 <= x < inside.shape[1] and inside[y, x])
                self.assertGreaterEqual(depth[y, x], depth.max() / 2)
                self.assertLessEqual(np.hypot(x - deep_x[nearest], y - deep_y[nearest]), depth.max())

    def test_reconciled_moving_slots_lead_to_their_neighbours(self):
        from math import atan2, pi

        from scipy.ndimage import find_objects

        grid, kinds, scope, stacks = self.reconciled_anchors()
        height = grid.shape[0]
        boxes = find_objects(grid)
        for province in sorted(scope):
            if kinds.get(province) not in ("land", "sea") or 0 not in stacks[province]:
                continue
            box = boxes[province - 1]
            top, left = max(box[0].start - 1, 0), max(box[1].start - 1, 0)
            window = grid[top:box[0].stop + 1, left:box[1].stop + 1]
            # The engine numbers neighbours by their first contact in a scan
            # of provinces.bmp that starts at the bottom row.
            first = {}
            for a, b, lower in ((window[:, :-1], window[:, 1:], 0), (window[:-1], window[1:], 1)):
                for y, x in zip(*np.nonzero((a == province) != (b == province))):
                    other = int(b[y, x] if a[y, x] == province else a[y, x])
                    key = (height - 1 - (top + y + lower), left + x)
                    first[other] = min(first.get(other, key), key)
            inside = window == province
            padded = np.pad(window, 1)
            x0, _height, z0, _rotation = stacks[province][0]
            x0, z0 = round(x0), round(z0)
            for slot, neighbour in enumerate(sorted(first, key=lambda other: (first[other], other))[:8], 1):
                with self.subTest(province=province, slot=slot):
                    self.assertIn(slot, stacks[province])
                    x, _height, z, rotation = stacks[province][slot]
                    dx, dz = x - x0, z - z0
                    if np.hypot(dx, dz) < 1:
                        continue
                    touching = inside & (
                        (padded[:-2, 1:-1] == neighbour) | (padded[2:, 1:-1] == neighbour)
                        | (padded[1:-1, :-2] == neighbour) | (padded[1:-1, 2:] == neighbour)
                    )
                    ys, xs = np.nonzero(touching)
                    contact_dx = xs.mean() + left - x0
                    contact_dz = height - 1 - (ys.mean() + top) - z0
                    self.assertGreaterEqual(dx * contact_dx + dz * contact_dz, 0)
                    self.assertLessEqual(abs((rotation - atan2(dx, -dz) + pi) % (2 * pi) - pi), 0.5)

    def test_reconciled_fleets_rest_on_the_sea_surface(self):
        # Under water the heightmap holds the seabed. Native sea anchors stand
        # at the surface height 9.5.
        _grid, kinds, scope, stacks = self.reconciled_anchors()
        for province in sorted(scope):
            if kinds.get(province) != "sea":
                continue
            for slot, (_x, height, _z, _rotation) in stacks[province].items():
                with self.subTest(province=province, slot=slot):
                    self.assertGreaterEqual(height, 9.5)

    def test_neftegorsk_southern_contact_has_a_broad_connected_border(self):
        from scipy.ndimage import label

        definitions = {
            int(fields[0]): tuple(map(int, fields[1:4]))
            for line in (ROOT / "map/definition.csv").read_text().splitlines()
            if len(fields := line.split(";")) >= 8
        }
        with Image.open(ROOT / "map/provinces.bmp") as image:
            rgb = np.asarray(image)
        first = np.all(rgb == definitions[4287], axis=2)
        second = np.all(rgb == definitions[6099], axis=2)
        for mask in (first, second):
            self.assertEqual(label(mask)[1], 1)
        shared_edges = sum(int(edges.sum()) for edges in (
            first[:, :-1] & second[:, 1:],
            second[:, :-1] & first[:, 1:],
            first[:-1, :] & second[1:, :],
            second[:-1, :] & first[1:, :],
        ))
        # This is an authored border width, not a native pathfinding threshold.
        self.assertGreaterEqual(shared_edges, 7)

    def test_mandate_islands_have_dry_lowland_rasters(self):
        definitions = {
            int(fields[0]): tuple(map(int, fields[1:4]))
            for line in (ROOT / "map/definition.csv").read_text().splitlines()
            if len(fields := line.split(";")) >= 8
        }
        with (
            Image.open(ROOT / "map/provinces.bmp") as provinces,
            Image.open(ROOT / "map/heightmap.bmp") as heights,
            Image.open(ROOT / "map/terrain.bmp") as terrain,
            Image.open(ROOT / "map/rivers.bmp") as rivers,
        ):
            rgb = np.asarray(provinces)
            for province in range(16802, 16809):
                mask = np.all(rgb == definitions[province], axis=2)
                self.assertTrue(mask.any())
                self.assertGreaterEqual(int(np.asarray(heights)[mask].min()), 97)
                self.assertLessEqual(int(np.asarray(heights)[mask].max()), 106)
                self.assertEqual(set(np.unique(np.asarray(terrain)[mask])), {0})
                self.assertEqual(set(np.unique(np.asarray(rivers)[mask])), {255})

    def test_province_map_has_no_four_colour_crossings(self):
        with Image.open(ROOT / "map/provinces.bmp") as image:
            rgb = np.asarray(image.convert("RGB"), dtype=np.uint32)
        packed = (rgb[:, :, 0] << 16) | (rgb[:, :, 1] << 8) | rgb[:, :, 2]
        a, b = packed[:-1, :-1], packed[:-1, 1:]
        c, d = packed[1:, :-1], packed[1:, 1:]
        crossings = (a != b) & (a != c) & (a != d) & (b != c) & (b != d) & (c != d)
        self.assertEqual(int(crossings.sum()), 0, np.argwhere(crossings).tolist())


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

    def test_country_districts_are_compact_and_inherit_their_parents_region(self):
        from scipy.ndimage import find_objects, label

        definitions = {
            int(row[0]): tuple(map(int, row[1:4]))
            for line in (ROOT / "map/definition.csv").read_text().splitlines()
            if len(row := line.split(";")) >= 8
        }
        with Image.open(ROOT / "map/provinces.bmp") as image:
            grid = geography.province_grid(np.asarray(image), definitions)
        boxes = find_objects(grid)
        memberships = builder.load_states()
        regions = {p: rid for rid, data in self.regions.items() for p in data["provinces"]}
        for district in states.COUNTRY_DISTRICTS:
            parent, child = district["parent"], district["province"]
            self.assertTrue({parent, child} <= memberships[district["state"]])
            self.assertEqual(regions[child], regions[parent])
        for province in geography.COUNTRY_DISTRICT_IDS:
            with self.subTest(province=province):
                mask = grid[boxes[province - 1]] == province
                self.assertEqual(label(mask)[1], 1)
                self.assertGreaterEqual(mask.sum(), 9)
                self.assertLessEqual(mask.sum(), 153)
                axes = np.linalg.eigvalsh(np.cov(np.argwhere(mask).T) + np.eye(2) / 12)
                self.assertLessEqual(np.sqrt(axes[1] / axes[0]), 2.3)

    def test_southern_rural_splits_create_connected_manoeuvre_routes(self):
        from scipy.ndimage import find_objects, label

        rows = {
            int(fields[0]): fields
            for line in (ROOT / "map/definition.csv").read_text().splitlines()
            if len(fields := line.split(";")) >= 8
        }
        colours = {p: tuple(map(int, row[1:4])) for p, row in rows.items()}
        with Image.open(ROOT / "map/provinces.bmp") as image:
            grid = geography.province_grid(np.asarray(image), colours)
        boxes = find_objects(grid)
        region_by_province = {
            p: region for region, data in self.regions.items() for p in data["provinces"]
        }
        for split in states.SOUTHERN_RURAL_SPLITS:
            parent, child = split["parent"], split["province"]
            with self.subTest(parent=parent, province=child):
                source = states.state_path(split["state"]).read_text(encoding="utf-8")
                members = set(map(int, re.search(r"\bprovinces\s*=\s*\{([^}]*)", source)[1].split()))
                self.assertTrue({parent, child} <= members)
                self.assertNotRegex(source, rf"victory_points\s*=\s*\{{\s*{child}\s")
                self.assertEqual(region_by_province[parent], region_by_province[child])
                self.assertEqual(rows[child][4:8], ["land", "false", split["terrain"], rows[parent][7]])
                self.assertEqual(rows[parent][6], split["terrain"])
                self.assertNotIn(split["terrain"], city_terrains.CITY_TERRAINS)
                for province in (parent, child):
                    self.assertEqual(label(grid[boxes[province - 1]] == province)[1], 1)
                neighbours = {p for p in self.physical[child] if self.types[p] == "land"}
                self.assertIn(parent, neighbours)
                self.assertGreaterEqual(len(neighbours - {parent}), 3)
                self.assertTrue(neighbours & self.physical[parent])

    def test_interior_splits_offer_two_domestic_routes_between_approaches(self):
        owners = {}
        for state_id, members in builder.load_states().items():
            source = states.state_path(state_id).read_text(encoding="utf-8-sig")
            owner = re.search(r"\bowner\s*=\s*(\w+)", source)
            if owner:
                owners.update(dict.fromkeys(members, owner[1]))

        for split in states.SOUTHERN_INTERIOR_SPLITS:
            parent, child = split["parent"], split["province"]
            with self.subTest(parent=parent, child=child):
                nearby = self.physical[parent] | self.physical[child]
                land = {p for p in nearby if self.types[p] == "land"}
                self.assertEqual({owners[p] for p in land}, {owners[parent]})
                approaches = self.physical[parent] & self.physical[child] & land
                # Opposite approaches can go through either half of the split.
                self.assertTrue(any(approaches - {p} - self.physical[p] for p in approaches))

    def test_southern_provinces_are_compact_and_the_city_centres_have_rail(self):
        from scipy.ndimage import label

        rails = {
            int(token) for line in (ROOT / "map/railways.txt").read_text().splitlines()
            for token in line.split()[2:]
        }
        with Image.open(ROOT / "map/provinces.bmp") as image:
            for entry in (*states.NEW_CITY_APPROACHES, *states.SOUTHERN_INTERIOR_SPLITS, *states.SOUTHERN_INTERIOR_DISTRICTS):
                with self.subTest(province=entry["province"]):
                    mask = np.array([list(row) for row in entry["mask"]]) == "1"
                    y_size, x_size = mask.shape
                    x, y = entry["origin"]
                    crop = np.asarray(image.crop((x, y, x + x_size, y + y_size)))
                    self.assertTrue(np.array_equal(np.all(crop == entry["rgb"], axis=2), mask))
                    self.assertEqual(label(mask)[1], 1)
                    pixels = np.argwhere(mask)
                    self.assertLessEqual(len(pixels), 130)
                    # Include each square pixel's own variance when measuring the principal axes.
                    axes = np.linalg.eigvalsh(np.cov(pixels.T) + np.eye(2) / 12)
                    self.assertLessEqual(np.sqrt(axes[1] / axes[0]), 2.3)
        centres = {entry["city"]: entry["state"] for entry in states.SOUTHERN_CITY_APPROACHES}
        centres.update({entry["province"]: entry["state"] for entry in states.SOUTHERN_CITIES})
        for city, state in centres.items():
            with self.subTest(city=city):
                self.assertIn(city, rails)
                self.assertGreaterEqual(sum(self.types[p] == "land" for p in self.physical[city]), 3)
                source = states.state_path(state).read_text(encoding="utf-8")
                value = re.search(rf"victory_points\s*=\s*\{{\s*{city}\s+(\d+)", source)
                self.assertIsNotNone(value)
                self.assertGreaterEqual(int(value[1]), 15)

    def assert_region(self, region_id: int, provinces: set[int]) -> None:
        self.assertIn(
            region_id, set(self.regions), "local naval region was not generated"
        )
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

    def test_coastal_additions_have_native_ports_in_their_own_land_provinces(
        self,
    ) -> None:
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

    def test_new_cities_have_urban_rasters_victory_points_and_stable_state_outputs(
        self,
    ) -> None:
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
            rgb = np.asarray(provinces.convert("RGB"))
            water = clearance.water_mask(
                rgb, clearance.water_colours(ROOT / "map/definition.csv")
            )
            shore = clearance.urban_blocked(water, rgb, ROOT / "map/definition.csv")
            seen = set()
            for y in range(provinces.height):
                for x in range(provinces.width):
                    province = colors.get(provinces.getpixel((x, y)))
                    if province in new_cities:
                        seen.add(province)
                        # The shared shoreline band keeps city meshes off the water.
                        self.assertEqual(
                            terrain.getpixel((x, y)),
                            clearance.URBAN_FALLBACK_PALETTE if shore[y, x] else 13,
                        )
                        self.assertEqual(
                            cities.getpixel((x, y)),
                            2 if province in geography.ARAB_CITIES else 15,
                        )
            self.assertEqual(seen, new_cities)
        for state_id, points in states.COASTAL_CITY_POINTS.items():
            source = states.state_path(state_id).read_text(encoding="utf-8-sig")
            for province, _value in points:
                self.assertRegex(
                    source, rf"victory_points\s*=\s*\{{\s*{province}\s+[1-9]\d*\s*\}}"
                )
        for path, expected in states.coastal_city_state_plan().items():
            self.assertEqual(path.read_bytes(), expected, str(path))

    def test_southern_cities_are_small_connected_provinces(self) -> None:
        counts = {}
        with Image.open(ROOT / "map/provinces.bmp") as image:
            color_counts = {
                color: count
                for count, color in image.getcolors(image.width * image.height)
            }
        for entry in states.SOUTHERN_CITIES:
            count = color_counts[tuple(entry["rgb"])]
            self.assertGreaterEqual(count, 9)
            self.assertLessEqual(count, 40)
            if entry.get("regional_town"):
                path = states.state_path(entry["state"])
                self.assertIn(entry["province"], states.state_file_provinces(path))
                point = f"victory_points = {{ {entry['province']} {entry['value']} }}"
                self.assertEqual(path.read_text(encoding="utf-8").count(point), 1)
            approaches = {q for q in self.physical[entry["province"]] if self.types[q] == "land"}
            self.assertGreaterEqual(len(approaches), 3, entry["name"])
            counts[entry["province"]] = count
        self.assertEqual(len(counts), 53)

    SHL_HOUSE_TOWNS = {
        16895: (290, 11806, 15, "Нуран"),
        16896: (292, 6582, 15, "Кердан"),
        16897: (293, 330, 15, "Шарим"),
        16898: (295, 8582, 15, "Вейран"),
        16899: (707, 2407, 15, "Зархан"),
    }
    @staticmethod
    def definition_terrain() -> dict[int, str]:
        terrain = {}
        for line in (ROOT / "map/definition.csv").read_text(encoding="utf-8-sig").splitlines():
            fields = line.split(";")
            if len(fields) >= 8 and fields[0].isdigit():
                terrain[int(fields[0])] = fields[6]
        return terrain

    def test_arab_cities_use_desert_and_hill_city_terrain(self) -> None:
        terrain = self.definition_terrain()
        arab = geography.ARAB_CITIES | geography.ARAB_URBAN_GROWTH
        self.assertEqual(set(geography.ARAB_CITY_TERRAIN), arab)
        self.assertLessEqual(geography.ARAB_HILL_CITIES | geography.ARAB_FARMLAND_CITIES, arab)
        self.assertFalse(geography.ARAB_HILL_CITIES & geography.ARAB_FARMLAND_CITIES)
        self.assertFalse(arab & set(city_terrains.NATIONAL_CITY_TERRAIN))
        for province, expected in geography.ARAB_CITY_TERRAIN.items():
            self.assertEqual(terrain[province], expected, province)
        # Lower Loren keeps ordinary city terrain; Svetlogorye uses its own.
        for province in geography.URBAN_GROWTH - arab:
            expected = city_terrains.NATIONAL_CITY_TERRAIN.get(province, "urban")
            self.assertEqual(terrain[province], expected, province)

    def test_national_city_clusters_share_one_terrain(self) -> None:
        terrain = self.definition_terrain()
        listed = [
            province
            for provinces in city_terrains.NATIONAL_CITY_CLUSTERS.values()
            for province in provinces
        ]
        self.assertEqual(len(listed), len(set(listed)))
        for province, expected in city_terrains.NATIONAL_CITY_TERRAIN.items():
            self.assertEqual(terrain[province], expected, province)
        used = {value for value in terrain.values() if value in city_terrains.CITY_TERRAINS}
        self.assertEqual(used, city_terrains.CITY_TERRAINS)
        # One city is one terrain: no two neighbouring city provinces differ.
        for province, neighbours in self.physical.items():
            if terrain.get(province) not in city_terrains.CITY_TERRAINS:
                continue
            for neighbour in neighbours:
                if terrain.get(neighbour) in city_terrains.CITY_TERRAINS:
                    self.assertEqual(terrain[province], terrain[neighbour], (province, neighbour))

    def test_shahrabad_house_towns_are_urban_provinces_inside_their_parents(self) -> None:
        from scipy.ndimage import label

        definitions = {}
        colours = []
        for line in (ROOT / "map/definition.csv").read_text(encoding="utf-8-sig").splitlines():
            fields = line.split(";")
            if len(fields) >= 8 and fields[0].isdigit():
                definitions[int(fields[0])] = fields
                colours.append(tuple(fields[1:4]))
        self.assertEqual(len(colours), len(set(colours)))
        entries = {entry["province"]: entry for entry in states.SOUTHERN_CITIES}
        memberships = builder.load_states()
        stacks = (ROOT / "map/unitstacks.txt").read_text(encoding="utf-8").splitlines()
        with Image.open(ROOT / "map/provinces.bmp") as image:
            rgb = np.asarray(image.convert("RGB"))
        for province, (state_id, parent, value, name) in self.SHL_HOUSE_TOWNS.items():
            with self.subTest(province=province):
                entry = entries[province]
                self.assertEqual(
                    (entry["state"], entry["parent"], entry["value"], entry["name"]),
                    (state_id, parent, value, name),
                )
                self.assertNotIn("sectors", entry)
                self.assertEqual(
                    definitions[province][4:8],
                    ["land", "false", geography.ARAB_CITY_TERRAIN[province], "3"],
                )
                # The city keeps its authored footprint where the rural approaches meet.
                painted = np.all(rgb == tuple(entry["rgb"]), axis=2)
                expected = np.zeros_like(painted)
                left, top = entry["origin"]
                for y, row in enumerate(entry["mask"], top):
                    for x, pixel in enumerate(row, left):
                        expected[y, x] = pixel == "1"
                self.assertTrue(np.array_equal(painted, expected))
                parent_colour = tuple(map(int, definitions[parent][1:4]))
                self.assertEqual(label(np.all(rgb == parent_colour, axis=2))[1], 1)
                self.assertGreaterEqual(len(self.physical[province]), 3)
                self.assertIn(province, memberships[state_id])
                self.assertIn(parent, memberships[state_id])
                self.assertIn(province, set(self.regions[42]["provinces"]))
                source = states.state_path(state_id).read_text(encoding="utf-8-sig")
                self.assertRegex(source, rf"victory_points\s*=\s*\{{\s*{province}\s+{value}\s*\}}")
                self.assertNotRegex(source, rf"victory_points\s*=\s*\{{\s*{parent}\s+\d+\s*\}}")
                self.assertIn((province, value, name), states.REGIONAL_SETTLEMENTS[state_id])
                anchors = [line.split(";") for line in stacks if line.startswith(f"{province};")]
                self.assertEqual(
                    {int(row[1]) for row in anchors},
                    geography.native_slots("land", len(self.physical[province])),
                )
                for row in anchors:
                    x = round(float(row[2]))
                    y = rgb.shape[0] - 1 - round(float(row[4]))
                    self.assertTrue(painted[y, x], f"anchor {row[1]} outside {province}")
        self.assertIn(16899, states.SOUTHERN_CAPITAL_DISTRICTS[294][3])
        for state_id, residents in states.SHL_POPULATION.items():
            source = states.state_path(state_id).read_text(encoding="utf-8-sig")
            self.assertEqual(int(re.search(r"\bmanpower\s*=\s*(\d+)", source)[1]), residents)

    def test_svetlogorye_massif_is_on_the_mainland_with_snowy_peaks(self) -> None:
        massif = set(states.with_country_districts(geography.RELIEF_PROVINCES))
        memberships = builder.load_states()
        # After the NAM state split Svetlogorsk (688) holds Vysokoye 1710 and
        # the residual coast (689) holds 2231.
        massif_states = (67, 688, 689, 690, 719)
        self.assertTrue(
            massif
            <= set().union(*(memberships[state] for state in massif_states))
        )
        self.assertEqual(
            len(
                builder.connected_components(
                    set(massif), self.physical
                )
            ),
            1,
        )
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
            for province in massif:
                fields = definitions[province]
                self.assertEqual(fields[4], "land")
                mask = np.all(rgb == tuple(map(int, fields[1:4])), axis=2)
                masks.append(mask)
                allowed = {"desert": {3}, "hills": {2}, "mountain": {18, 11, 16}}[
                    fields[6]
                ]
                self.assertTrue(
                    set(np.unique(terrain_pixels[mask])) <= allowed,
                    f"province {province} spills into another graphical terrain class",
                )
                if fields[6] == "mountain":
                    self.assertTrue(
                        np.all(terrain_pixels[mask & (elevation >= 205)] == 16)
                    )
            mask = np.logical_or.reduce(masks)
            self.assertGreaterEqual(int(elevation[mask].max()), 220)
            self.assertGreaterEqual(int(elevation[mask].min()), 97)
            self.assertEqual(set(np.unique(terrain_pixels[mask])), {2, 3, 11, 16, 18})
            kinds = [
                definitions[province][6] for province in massif
            ]
            self.assertGreaterEqual(kinds.count("mountain"), 4)
            self.assertGreaterEqual(kinds.count("hills"), 4)
            self.assertIn("desert", kinds)
            interior = mask.copy()
            interior[1:] &= mask[:-1]
            interior[:-1] &= mask[1:]
            interior[:, 1:] &= mask[:, :-1]
            interior[:, :-1] &= mask[:, 1:]
            for axis in (0, 1):
                pairs = (
                    (interior[1:] & interior[:-1])
                    if axis == 0
                    else (interior[:, 1:] & interior[:, :-1])
                )
                slopes = np.abs(np.diff(elevation.astype(np.int16), axis=axis))
                self.assertLessEqual(int(slopes[pairs].max()), 6)
            # Provinces split out of the massif keep its generated surface, so
            # the relief is recomputed over the whole surface mask.
            surface = np.logical_or.reduce([
                np.all(rgb == tuple(map(int, definitions[province][1:4])), axis=2)
                for province in states.with_country_districts(geography.RELIEF_SURFACE_PROVINCES)
            ])
            self.assertTrue(
                np.array_equal(geography.mountain_heights(surface, elevation), elevation)
            )
            for line in (ROOT / "map/unitstacks.txt").read_text().splitlines():
                fields = line.split(";")
                if int(fields[0]) in massif:
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
                    self.assertIn(
                        second, self.physical[first], f"railway {first}-{second}"
                    )

    def test_southern_capital_district_population_and_industry(self) -> None:
        expected_populations = {
            241: (2_000_000, 480_000),
            253: (1_150_000, 850_000),
            260: (1_650_000, 300_000),
            275: (2_000_000, 520_000),
            283: (1_850_000, 400_000),
            294: (3_300_000, 2_250_000),
            300: (1_900_000, 430_000),
        }
        memberships = builder.load_states()
        for capital, (
            district,
            _city_population,
            _rural_population,
            provinces,
        ) in states.SOUTHERN_CAPITAL_DISTRICTS.items():
            city_source = states.state_path(capital).read_text(encoding="utf-8")
            rural_source = states.state_path(district).read_text(encoding="utf-8")
            populations = tuple(
                int(re.search(r"\bmanpower\s*=\s*(\d+)", source)[1])
                for source in (city_source, rural_source)
            )
            self.assertEqual(
                populations, expected_populations[capital],
                f"capital {capital}, rural district {district}",
            )
            for building, amount in (
                ("industrial_complex", 2),
                ("arms_factory", 1),
                ("air_base", 1),
            ):
                levels = re.findall(
                    rf"\b{building}\s*=\s*(\d+)", city_source + rural_source
                )
                self.assertEqual(sum(map(int, levels)), amount)
            self.assertEqual(
                len(builder.connected_components(memberships[district], self.physical)),
                1,
            )
            province, value = states.SOUTHERN_CITY_POINTS[capital]
            self.assertIn(province, memberships[capital])
            self.assertEqual(memberships[district], set(provinces))
            self.assertTrue(memberships[capital].isdisjoint(memberships[district]))
            self.assertRegex(
                city_source, rf"victory_points\s*=\s*\{{\s*{province}\s+{value}\s*\}}"
            )
        for path, expected in states.southern_settlement_plan().items():
            self.assertEqual(path.read_bytes(), expected, str(path))

    def test_orval_and_arsal_have_connected_mainland_and_preserved_capitals(
        self,
    ) -> None:
        memberships = builder.load_states()
        # Orval starts without territory and holds cores on its former
        # mainland; Arsal owns its states.
        for tag, capital, relation in (("ORV", 455, "add_core_of"), ("ARS", 441, "owner")):
            provinces = set()
            for path in (ROOT / "history/states").glob("*.txt"):
                source = path.read_text(encoding="utf-8-sig")
                if re.search(rf"\b{relation}\s*=\s*{tag}\b", source):
                    state_id = int(re.search(r"\bid\s*=\s*(\d+)", source)[1])
                    provinces.update(memberships[state_id])
            self.assertEqual(
                len(builder.connected_components(provinces, self.physical)), 1
            )
            self.assertTrue(memberships[capital] <= provinces)

    def test_large_city_splits_preserve_population_and_industry(self) -> None:
        for members, population in (
            ((290, 699), states.SHL_POPULATION[290] + states.SHL_POPULATION[699]),
            ((689, 700), states.NAM_POPULATION[689] + states.NAM_POPULATION[700]),
            ((691, 701, 726), 4_860_000),
        ):
            sources = [states.state_path(state).read_text() for state in members]
            self.assertEqual(
                sum(
                    int(re.search(r"\bmanpower\s*=\s*(\d+)", source)[1])
                    for source in sources
                ),
                population,
            )
        for state_ids, civilian, military in (((689, 700), 1, 2), ((691, 701, 726), 1, 0)):
            source = "\n".join(
                states.state_path(state).read_text() for state in state_ids
            )
            self.assertEqual(
                sum(map(int, re.findall(r"\bindustrial_complex\s*=\s*(\d+)", source))),
                civilian,
            )
            self.assertEqual(
                sum(map(int, re.findall(r"\barms_factory\s*=\s*(\d+)", source))),
                military,
            )

    def test_shahrabad_hinterlands_are_connected_and_parents_keep_scripted_borders(self) -> None:
        memberships = builder.load_states()
        owners = {}
        for path in (ROOT / "history/states").glob("*.txt"):
            source = path.read_text(encoding="utf-8-sig")
            owner = re.search(r"\bowner\s*=\s*(\w+)", source)
            if owner:
                owners[int(re.search(r"\bid\s*=\s*(\d+)", source)[1])] = owner[1]
        state_by_province = {
            province: state_id
            for state_id, provinces in memberships.items()
            for province in provinces
        }

        def neighbours(state_id: int) -> set[str]:
            return {
                owners[state_by_province[other]]
                for province in memberships[state_id]
                for other in self.physical[province]
                if other in state_by_province and state_by_province[other] != state_id
            }

        # Every scripted neighbour war addresses the parent state, so the parent
        # must still touch that country after the hinterland is carved out.
        kept_borders = {288: {"KYZ"}, 289: {"KYZ"}, 295: {"GLP"}}
        for parent, (child, original, carved) in states.SHL_SPLIT_FAMILIES.items():
            self.assertEqual(memberships[parent] | memberships[child], set(original))
            self.assertEqual(memberships[child], set(carved))
            for state_id in (parent, child):
                self.assertEqual(
                    len(builder.connected_components(memberships[state_id], self.physical)),
                    1,
                    f"state {state_id} is not connected",
                )
                self.assertEqual(owners[state_id], "SHL")
            self.assertTrue(kept_borders.get(parent, set()) <= neighbours(parent))
            # Both halves stay inside strategic region 42, so weather and naval
            # assignments do not straddle the new border.
            for state_id in (parent, child):
                self.assertTrue(memberships[state_id] <= set(self.regions[42]["provinces"]))
        self.assertTrue({16738, 16790, 16791, 16792} <= memberships[288])
        self.assertIn(7825, memberships[291])
        self.assertIn(16739, memberships[294])
        self.assertEqual(
            sum(
                int(re.search(r"\bmanpower\s*=\s*(\d+)", states.state_path(state).read_text())[1])
                for state in states.SHL_POPULATION
            ),
            30_000_000,
        )

    def test_stelander_approaches_are_a_compact_connected_region(self) -> None:
        self.assert_region(231, {13256, 13493, 13596, 14089, 14414, 15500})

    def test_canal_approaches_include_the_connected_northern_inlets(self) -> None:
        self.assert_region(
            232,
            {
                13393,
                13801,
                13961,
                14011,
                14153,
                14225,
                14234,
                14274,
                14360,
                14416,
                14482,
                14634,
                14761,
                14816,
                14973,
                15190,
                15590,
                15723,
                16030,
            },
        )

    def test_antolla_has_separate_western_and_nodrul_sectors(self) -> None:
        self.assert_region(228, {16262, 16264, 16265})
        self.assert_region(229, {16258, 16266, 16268})
        for region_id in (228, 229):
            self.assertIn(
                "naval_terrain=water_shallow_sea", self.regions[region_id]["text"]
            )
        self.assertIn(
            16266, self.navigable[14634], "the existing canal link must survive"
        )

    def test_local_cuts_preserve_every_other_macro_ocean_boundary(self) -> None:
        ocean = builder.connected_components(self.sea, self.navigable)[0]
        macro = builder.partition_connected_sea(ocean, self.navigable, self.positions)
        for southern in (False, True):
            dedicated = set().union(*(
                provinces for region_id, provinces in builder.DEDICATED_SEA_PROVINCES.items()
                if (region_id in builder.SOUTHERN_SEA_REGION_IDS) == southern
            ))
            for provinces in macro.values():
                provinces.difference_update(dedicated)
            builder.rehome_detached_macro_fragments(macro, self.navigable)
        for region in builder.SEA_REGIONS:
            with self.subTest(region=region.region_id):
                self.assertEqual(
                    set(self.regions[region.region_id]["provinces"]),
                    macro[region.region_id],
                )

    def test_southern_theatres_only_subdivide_the_southern_ocean(self) -> None:
        ocean = builder.connected_components(self.sea, self.navigable)[0]
        original = builder.partition_connected_sea(ocean, self.navigable, self.positions)
        previous_cuts = set().union(*(
            provinces for region_id, provinces in builder.DEDICATED_SEA_PROVINCES.items()
            if region_id < 238
        ))
        for provinces in original.values():
            provinces.difference_update(previous_cuts)
        builder.rehome_detached_macro_fragments(original, self.navigable)
        southern = set(self.regions[38]["provinces"])
        for region_id in range(238, 247):
            provinces = set(self.regions[region_id]["provinces"])
            self.assert_region(region_id, set(builder.DEDICATED_SEA_PROVINCES[region_id]))
            self.assertFalse(southern & provinces)
            southern.update(provinces)
        self.assertEqual(southern, original[38])
        for region_id, provinces in original.items():
            if region_id != 38:
                self.assertEqual(set(self.regions[region_id]["provinces"]), provinces)

    def test_southern_ports_and_islands_have_distinct_operating_waters(self) -> None:
        region_by_province = {
            province: region_id for region_id, region in self.regions.items()
            for province in region["provinces"]
        }
        # Svetlogorsk, the Azhar seaboard and Black Coast retain sea access.
        for port, expected in ((689, 238), (2443, 240), (493, 241)):
            neighbours = {p for p in self.physical[port] if p in self.sea}
            self.assertTrue(neighbours, port)
            self.assertIn(expected, {region_by_province[p] for p in neighbours})
        # The outlying islands raised in the open southern ocean are excepted.
        island_waters = {
            region_by_province[sea]
            for state in range(225, 232)
            for province in builder.load_states()[state] - geography.ARCHIPELAGO_NEW_PROVINCES
            for sea in self.physical[province] if sea in self.sea
        }
        self.assertTrue({242, 243, 244} <= island_waters)
        self.assertNotIn(38, island_waters)

    def test_all_naval_regions_are_connected_and_cover_the_ocean_once(self) -> None:
        seen: set[int] = set()
        ids = [
            region.region_id for region in (*builder.REGIONS, *builder.ALL_SEA_REGIONS)
        ]
        self.assertEqual(len(ids), len(set(ids)))
        for region in builder.ALL_SEA_REGIONS:
            provinces = set(self.regions[region.region_id]["provinces"])
            with self.subTest(region=region.region_id):
                self.assertFalse(seen & provinces)
                self.assertTrue(provinces)
                self.assertEqual(
                    len(builder.connected_components(provinces, self.physical)), 1
                )
            seen.update(provinces)
        self.assertEqual(
            seen, builder.connected_components(self.sea, self.navigable)[0]
        )

    def test_both_localisations_and_weather_markers_cover_new_regions(self) -> None:
        for language in ("russian", "english"):
            path = (
                ROOT / f"localisation/replace/strategic_region_names_l_{language}.yml"
            )
            self.assertTrue(path.read_bytes().startswith(b"\xef\xbb\xbf"))
            names = dict(
                re.findall(
                    r'^\s*(STRATEGICREGION_\d+):(?:\d+)?\s*"(.+)"',
                    path.read_text(encoding="utf-8-sig"),
                    re.M,
                )
            )
            for region_id in (*range(228, 233), *range(238, 247)):
                self.assertIn(f"STRATEGICREGION_{region_id}", names)
        weather_ids = {
            int(line.split(";", 1)[0])
            for line in (ROOT / "map/weatherpositions.txt").read_text().splitlines()
            if line.strip()
        }
        self.assertTrue(set((*range(228, 233), *range(238, 247))) <= weather_ids)
        self.assertEqual(
            sync_builder_english_localisation(
                ROOT, "tools.builders.build_adiscord_strategic_regions", apply=False
            ),
            0,
        )



class ArchipelagoIslandTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.rows = {
            int(fields[0]): fields
            for line in (ROOT / "map/definition.csv").read_text(encoding="utf-8-sig").splitlines()
            if len(fields := line.split(";")) >= 8 and fields[0].isdigit()
        }
        colours = {province: tuple(map(int, row[1:4])) for province, row in cls.rows.items()}
        with Image.open(ROOT / "map/provinces.bmp") as image:
            rgb = np.asarray(image.convert("RGB"))
        cls.grid = geography.province_grid(rgb, colours)
        cls.sea = np.isin(cls.grid, [p for p, row in cls.rows.items() if row[4] == "sea"])
        cls.bridges = [
            line.split(";")
            for line in (ROOT / "map/adjacencies.csv").read_text(encoding="utf-8-sig").splitlines()
            if line.endswith(geography.ISLAND_BRIDGE_COMMENT)
        ]
        rasters = {}
        for name in ("terrain", "cities", "heightmap", "rivers"):
            with Image.open(ROOT / f"map/{name}.bmp") as image:
                rasters[name] = np.asarray(image)
        cls.terrain = rasters["terrain"]
        cls.cities = rasters["cities"]
        cls.heights = rasters["heightmap"]
        cls.rivers = rasters["rivers"]
        definition = ROOT / "map/definition.csv"
        water = clearance.water_mask(rgb, clearance.water_colours(definition))
        cls.shore = clearance.urban_blocked(water, rgb, definition) & ~water
        # Every island state of the shared relief, read from the state files.
        cls.state_provinces = {
            state: states.state_file_provinces(states.state_path(state))
            for state in (
                *geography.ARCHIPELAGO_STATES,
                *(state for group in geography.ARCHIPELAGO_NEIGHBOUR_STATES.values() for state in group),
            )
        }
        svetlogorye = set().union(*(cls.state_provinces[state] for state in geography.ARCHIPELAGO_STATES))
        cls.svetlogorye_provinces = svetlogorye | geography.ARCHIPELAGO_NEW_PROVINCES
        cls.neighbour_provinces = set().union(*(
            cls.state_provinces[state]
            for group in geography.ARCHIPELAGO_NEIGHBOUR_STATES.values()
            for state in group
        )) - geography.ARCHIPELAGO_FOREIGN_SCOPES
        # Svetlogorye towns: every authored settlement of its states, the
        # raised-island towns and the governorate's big-city cluster.
        cls.svetlogorye_cities = {
            province
            for state in geography.ARCHIPELAGO_STATES
            for province, _value, _name in states.REGIONAL_SETTLEMENTS.get(state, ())
        } | {
            island["town"]["province"] for island in states.NAM_ARCHIPELAGO_ISLANDS if "town" in island
        } | (set(city_terrains.NATIONAL_CITY_CLUSTERS.get("svetlogorye_town", ())) & svetlogorye)

    def test_islands_are_isolated_land_of_their_state(self) -> None:
        from scipy.ndimage import binary_dilation, label

        self.assertGreaterEqual(len(states.NAM_ARCHIPELAGO_ISLANDS), 30)
        for island in states.NAM_ARCHIPELAGO_ISLANDS:
            parts = [part["province"] for part in island["provinces"]]
            with self.subTest(island=parts[0]):
                members = states.state_file_provinces(states.state_path(island["state"]))
                self.assertTrue(set(parts) <= members)
                mask = np.isin(self.grid, parts)
                self.assertEqual(label(mask)[1], 1)
                shore = binary_dilation(mask) & ~mask
                # The island touches only its own sea province: no land and no
                # other sea, so the bridge is its only land link.
                self.assertEqual(set(np.unique(self.grid[shore]).tolist()), {island["sea"]})
                self.assertEqual(label(self.grid == island["sea"])[1], 1)
                for part in parts:
                    row = self.rows[part]
                    self.assertEqual(row[4:6], ["land", "true"] if (binary_dilation(self.grid == part) & self.sea).any() else ["land", "false"])
                    # Only the island's harbour town is a city province.
                    if part == island.get("town", {}).get("province"):
                        self.assertEqual(row[6], "svetlogorye_town")
                    else:
                        self.assertNotIn(row[6], city_terrains.CITY_TERRAINS)
                    self.assertEqual(label(self.grid == part)[1], 1)
                    self.assertGreaterEqual(int((self.grid == part).sum()), 12)

    def test_near_islands_have_one_bridge_and_distant_ones_none(self) -> None:
        map_height = self.grid.shape[0]
        self.assertTrue(any(not island["bridge"] for island in states.NAM_ARCHIPELAGO_ISLANDS))
        for island in states.NAM_ARCHIPELAGO_ISLANDS:
            parts = {part["province"] for part in island["provinces"]}
            with self.subTest(island=min(parts)):
                links = [row for row in self.bridges if int(row[0]) in parts or int(row[1]) in parts]
                if not island["bridge"]:
                    self.assertEqual(links, [])
                    # A settled island without a bridge keeps a harbour of its own.
                    if len(parts) > 1:
                        self.assertIn("harbour", island)
                    continue
                self.assertEqual(len(links), 1)
                start, home, kind, through, x0, y0, x1, y1 = links[0][:8]
                self.assertEqual((int(home), kind, int(through)), (island["home"], "sea", island["sea"]))
                self.assertEqual(self.grid[map_height - 1 - int(y0), int(x0)], int(start))
                self.assertEqual(self.grid[map_height - 1 - int(y1), int(x1)], island["home"])
                # The crossing stays over its own sea province.
                ya, xa = map_height - 1 - int(y0), int(x0)
                yb, xb = map_height - 1 - int(y1), int(x1)
                steps = int(np.ceil(np.hypot(yb - ya, xb - xa) * 3)) + 2
                path = self.grid[
                    np.rint(np.linspace(ya, yb, steps)).astype(int),
                    np.rint(np.linspace(xa, xb, steps)).astype(int),
                ]
                self.assertLessEqual(set(np.unique(path).tolist()), parts | {island["home"], island["sea"]})

    def test_island_towns_are_named_harbours(self) -> None:
        russian = (ROOT / "localisation/russian/victory_points_l_russian.yml").read_text(encoding="utf-8-sig")
        english = (ROOT / "localisation/english/victory_points_l_english.yml").read_text(encoding="utf-8-sig")
        towns = [island for island in states.NAM_ARCHIPELAGO_ISLANDS if "town" in island]
        self.assertGreaterEqual(len(towns), 8)
        for island in towns:
            town = island["town"]
            with self.subTest(town=town["province"]):
                source = states.state_path(island["state"]).read_text(encoding="utf-8-sig")
                self.assertRegex(source, rf"victory_points\s*=\s*\{{\s*{town['province']}\s+{town['value']}\s*\}}")
                self.assertRegex(source, rf"\b{town['province']}\s*=\s*\{{\s*naval_base\s*=\s*{island['harbour']}\s*\}}")
                self.assertIn(f'VICTORY_POINTS_{town["province"]}: "{town["name"]}"', russian)
                self.assertRegex(english, rf'(?m)^\s*VICTORY_POINTS_{town["province"]}:\s*"[A-Za-z ]+"')
                self.assertEqual(self.rows[town["province"]][5], "true")

    def test_ulven_straits_are_bridged_between_their_states(self) -> None:
        map_height = self.grid.shape[0]
        rows = [
            line.split(";")
            for line in (ROOT / "map/adjacencies.csv").read_text(encoding="utf-8-sig").splitlines()
            if line.endswith(geography.STRAIT_BRIDGE_COMMENT)
        ]
        self.assertEqual(len(rows), len(geography.STRAIT_BRIDGES) + len(geography.ISLET_BRIDGES))
        sides = [
            (
                states.state_file_provinces(states.state_path(first)),
                states.state_file_provinces(states.state_path(second)),
            )
            for first, second in geography.STRAIT_BRIDGES
        ]
        # An islet is bridged to the rest of its own state.
        sides += [
            ({islet}, states.state_file_provinces(states.state_path(state)) - {islet})
            for state, islet in geography.ISLET_BRIDGES
        ]
        neighbours = geography.province_neighbours(self.grid)
        for state, islet in geography.ISLET_BRIDGES:
            self.assertEqual({self.rows[province][4] for province in neighbours[islet]}, {"sea"})
        for (first, second), row in zip(sides, rows):
            with self.subTest(row=row[:2]):
                start, stop, kind, sea = int(row[0]), int(row[1]), row[2], int(row[3])
                self.assertIn(start, first)
                self.assertIn(stop, second)
                self.assertEqual((kind, self.rows[sea][4]), ("sea", "sea"))
                self.assertEqual(self.grid[map_height - 1 - int(row[5]), int(row[4])], start)
                self.assertEqual(self.grid[map_height - 1 - int(row[7]), int(row[6])], stop)
                self.assertLessEqual(np.hypot(int(row[4]) - int(row[6]), int(row[5]) - int(row[7])), 8)

    def test_raised_islands_leave_every_sea_anchor_on_water(self) -> None:
        raised = np.isin(self.grid, list(geography.ARCHIPELAGO_NEW_PROVINCES))
        anchors = geography.sea_anchor_pixels(
            (ROOT / "map/unitstacks.txt").read_bytes(),
            (ROOT / "map/buildings.txt").read_bytes(),
            self.grid.shape,
            {province for province, row in self.rows.items() if row[4] == "sea"},
        )
        self.assertFalse((raised & anchors).any())

    def test_archipelago_covers_the_neighbouring_island_states(self) -> None:
        import re

        for tag, group in geography.ARCHIPELAGO_NEIGHBOUR_STATES.items():
            for state in group:
                with self.subTest(tag=tag, state=state):
                    source = states.state_path(state).read_text(encoding="utf-8-sig")
                    self.assertEqual(re.search(r"\bowner\s*=\s*(\w+)", source).group(1), tag)
                    expected = self.state_provinces[state] - geography.ARCHIPELAGO_FOREIGN_SCOPES
                    self.assertTrue(expected)
                    self.assertLessEqual(expected, geography.ARCHIPELAGO_PROVINCES)
        for state in geography.ARCHIPELAGO_STATES:
            self.assertLessEqual(self.state_provinces[state], geography.ARCHIPELAGO_PROVINCES)
        # Each island state is surrounded by water, so the relief falls to a
        # coast on every side and never meets foreign land.
        from scipy.ndimage import binary_dilation

        land = np.isin(self.grid, list(geography.ARCHIPELAGO_PROVINCES))
        ring = np.unique(self.grid[binary_dilation(land) & ~land]).tolist()
        self.assertEqual({self.rows[province][4] for province in ring} - {"sea", "lake"}, set())

    def test_svetlogorye_towns_and_cities_are_built_up_city_provinces(self) -> None:
        self.assertGreaterEqual(len(self.svetlogorye_cities), 30)
        neighbour_cities = {
            province for province in self.neighbour_provinces
            if self.rows[province][6] in city_terrains.CITY_TERRAINS
        }
        for province in sorted(self.svetlogorye_cities | neighbour_cities):
            kind = self.rows[province][6]
            with self.subTest(province=province, terrain=kind):
                if province in self.svetlogorye_cities:
                    self.assertEqual(kind, city_terrains.NATIONAL_CITY_TERRAIN.get(province, "svetlogorye_town"))
                self.assertIn(kind, city_terrains.CITY_TERRAINS)
                mask = self.grid == province
                inland = mask & ~self.shore
                # The whole dry area away from the shore band is built up.
                self.assertTrue((self.terrain[inland] == 13).all())
                self.assertTrue((self.cities[inland] == 15).all())
                self.assertTrue((self.terrain[mask & self.shore] == clearance.URBAN_FALLBACK_PALETTE).all())
                if province not in geography.CITIES:
                    self.assertFalse((self.cities[mask & self.shore] == 15).any())

    def test_other_archipelago_provinces_are_painted_in_their_terrain(self) -> None:
        palettes = geography.ARCHIPELAGO_PALETTES
        declared = (ROOT / "common/terrain/00_terrain.txt").read_text(encoding="utf-8-sig")
        for kind, index in palettes.items():
            self.assertRegex(declared, rf"type\s*=\s*{kind}\s+color\s*=\s*\{{\s*{index}\s*\}}")
        rural = sorted(
            province for province in self.svetlogorye_provinces | self.neighbour_provinces
            if self.rows[province][6] not in city_terrains.CITY_TERRAINS
        )
        self.assertEqual(len(set(self.rows[province][6] for province in rural)), len(palettes))
        for province in rural:
            kind = self.rows[province][6]
            with self.subTest(province=province, terrain=kind):
                mask = self.grid == province
                self.assertIn(kind, palettes)
                # One terrain over the whole province, without city models.
                self.assertTrue((self.terrain[mask] == palettes[kind]).all())
                self.assertFalse(np.isin(self.cities[mask], (2, 15)).any())

    def test_archipelago_rivers_run_in_valleys_above_the_sea(self) -> None:
        from scipy.ndimage import distance_transform_edt

        land = np.isin(self.grid, list(geography.ARCHIPELAGO_PROVINCES))
        river = land & (self.rivers < 254)
        neighbours = np.isin(self.grid, list(self.neighbour_provinces))
        # FLR, RSV and CHD carry authored rivers.
        self.assertGreaterEqual(int((river & neighbours).sum()), 600)
        self.assertGreaterEqual(int(self.heights[land].min()), 97)
        self.assertGreaterEqual(int(self.heights[river].min()), 97)
        distance = distance_transform_edt(~river)
        banks = land & (distance >= 2) & (distance <= 3)
        self.assertLess(float(self.heights[river].mean()) + 2.0, float(self.heights[banks].mean()))

    def province_mask(self, province: int) -> tuple[np.ndarray, tuple[slice, slice]]:
        from scipy.ndimage import find_objects

        if not hasattr(type(self), "boxes"):
            type(self).boxes = find_objects(self.grid)
        box = self.boxes[province - 1]
        return self.grid[box] == province, box

    def test_island_districts_are_compact_connected_parts_of_their_parents(self) -> None:
        from scipy.ndimage import label

        districts = states.ISLAND_DISTRICTS
        self.assertGreaterEqual(len(districts), 150)
        ids = [district["province"] for district in districts]
        self.assertEqual(ids, list(range(ids[0], ids[0] + len(ids))))
        colours = [tuple(map(int, row[1:4])) for row in self.rows.values()]
        self.assertEqual(len(colours), len(set(colours)))
        for district in districts:
            province, parent = district["province"], district["parent"]
            with self.subTest(province=province):
                self.assertTrue({province, parent} <= self.state_provinces[district["state"]])
                self.assertNotIn(parent, geography.ISLAND_DISTRICT_PROVINCES)
                self.assertEqual(tuple(map(int, self.rows[province][1:4])), tuple(district["rgb"]))
                self.assertEqual(self.rows[province][4], "land")
                self.assertEqual(self.rows[province][7], self.rows[parent][7])
                # The province is exactly its reviewed mask.
                reviewed = np.array([list(row) for row in district["mask"]]) == "1"
                x, y = district["origin"]
                window = self.grid[y:y + reviewed.shape[0], x:x + reviewed.shape[1]]
                np.testing.assert_array_equal(window == province, reviewed)
                mask, _box = self.province_mask(province)
                self.assertEqual(int(mask.sum()), int(reviewed.sum()))
        # Every part of a split is one compact piece of mainland-like size; a town is smaller.
        for province in sorted(geography.ISLAND_DISTRICT_SCOPE):
            with self.subTest(province=province):
                mask, box = self.province_mask(province)
                self.assertEqual(label(mask)[1], 1)
                size = int(mask.sum())
                if province in geography.ISLAND_TOWN_PROVINCES:
                    self.assertTrue(45 <= size <= 80, size)
                else:
                    self.assertTrue(150 <= size <= 300, size)
                axes = np.linalg.eigvalsh(np.cov(np.argwhere(mask).T) + np.eye(2) / 12)
                self.assertLessEqual(np.sqrt(axes[1] / axes[0]), 2.6)
                ys, xs = np.nonzero(mask)
                ys, xs = ys + box[0].start, xs + box[1].start
                coastal = any(
                    self.sea[ys + dy, xs + dx].any() for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1))
                )
                self.assertEqual(self.rows[province][5], "true" if coastal else "false")

    def test_island_towns_are_built_up_named_city_provinces(self) -> None:
        import re

        towns = states.ISLAND_TOWNS
        self.assertGreaterEqual(len(towns), 6)
        russian = (ROOT / "localisation/russian/victory_points_l_russian.yml").read_text(encoding="utf-8-sig")
        english = (ROOT / "localisation/english/victory_points_l_english.yml").read_text(encoding="utf-8-sig")
        map_height = self.grid.shape[0]
        ports = set()
        for line in (ROOT / "map/buildings.txt").read_text(encoding="utf-8-sig").splitlines():
            fields = line.split(";")
            if len(fields) == 7 and fields[1] == "naval_base_spawn":
                ports.add(int(self.grid[map_height - 1 - round(float(fields[4])), round(float(fields[2]))]))
        centres = {}
        names = [town["town"]["name"] for town in towns]
        self.assertEqual(len(names), len(set(names)))
        for town in towns:
            province, entry = town["province"], town["town"]
            with self.subTest(town=province):
                source = states.state_path(town["state"]).read_text(encoding="utf-8-sig")
                self.assertEqual(self.rows[province][6], "urban")
                mask, box = self.province_mask(province)
                shore = self.shore[box]
                inland = mask & ~shore
                # A usable city core remains behind the shore band, fully built up.
                self.assertGreaterEqual(int(inland.sum()), 30)
                self.assertTrue((self.terrain[box][inland] == 13).all())
                self.assertTrue((self.cities[box][inland] == 15).all())
                self.assertTrue((self.terrain[box][mask & shore] == clearance.URBAN_FALLBACK_PALETTE).all())
                self.assertFalse((self.cities[box][mask & shore] == 15).any())
                # The river beside a town runs on the opposite bank.
                self.assertFalse((self.rivers[box][mask] < 254).any())
                self.assertRegex(source, rf"victory_points\s*=\s*\{{\s*{province}\s+{entry['value']}\s*\}}")
                self.assertEqual(len(re.findall(rf"(?m)^\s*VICTORY_POINTS_{province}:", russian)), 1)
                self.assertIn(f'VICTORY_POINTS_{province}: "{entry["name"]}"', russian)
                self.assertRegex(english, rf'(?m)^\s*VICTORY_POINTS_{province}:\s*"[A-Za-z ]+"')
                harbour = rf"\b{province}\s*=\s*\{{\s*naval_base\s*=\s*(\d+)\s*\}}"
                if "harbour" in entry:
                    self.assertEqual(re.search(harbour, source).group(1), str(entry["harbour"]))
                    self.assertEqual(self.rows[province][5], "true")
                    self.assertIn(province, ports)
                else:
                    self.assertNotRegex(source, harbour)
                ys, xs = np.nonzero(mask)
                centres[province] = (xs.mean() + box[1].start, ys.mean() + box[0].start)
        # Towns stand apart; only the halves of a two-province city adjoin.
        neighbours = geography.province_neighbours(self.grid)
        provinces = sorted(centres)
        for index, first in enumerate(provinces):
            for second in provinces[index + 1:]:
                if second in neighbours[first]:
                    continue
                gap = np.hypot(centres[first][0] - centres[second][0], centres[first][1] - centres[second][1])
                self.assertGreaterEqual(gap, 40, (first, second))
        # The names reach the English file through the reviewed catalogue.
        self.assertEqual(
            sync_builder_english_localisation(ROOT, "tools.builders.build_adiscord_new_states", apply=False), 0
        )

    def test_island_rivers_follow_district_borders_from_a_source_to_the_sea(self) -> None:
        self.assertGreaterEqual(len(geography.ISLAND_RIVERS), 3)
        border = geography.province_borders(self.grid)
        land = np.isin(self.grid, list(geography.ISLAND_DISTRICT_SCOPE - geography.ISLAND_TOWN_PROVINCES))
        for course in geography.ISLAND_RIVERS:
            with self.subTest(source=course[0]):
                self.assertGreaterEqual(len(course), 30)
                self.assertEqual(len(set(course)), len(course))
                xs, ys = np.array(course).T
                self.assertTrue((np.abs(np.diff(xs)) + np.abs(np.diff(ys)) == 1).all())
                self.assertEqual(int(self.rivers[ys[0], xs[0]]), 0)
                body = self.rivers[ys[1:], xs[1:]]
                self.assertTrue(((body > 0) & (body < 254)).all())
                # It never crosses a province interior or a town.
                self.assertTrue((land[ys, xs] & border[ys, xs]).all())
                x, y = course[-1]
                self.assertTrue(self.sea[y - 1, x] or self.sea[y + 1, x] or self.sea[y, x - 1] or self.sea[y, x + 1])
                self.assertFalse(self.sea[ys, xs].any())
                self.assertGreater(int(self.heights[ys[0], xs[0]]), int(self.heights[y, x]) + 10)


if __name__ == "__main__":
    unittest.main()
