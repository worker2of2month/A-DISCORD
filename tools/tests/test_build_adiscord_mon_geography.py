"""Contracts of the Montar Empire geography builder."""

from __future__ import annotations

import unittest
from collections import Counter
from io import BytesIO

import numpy as np
from PIL import Image
from scipy.ndimage import label

from tools.builders import build_adiscord_mon_geography as mon
from tools.builders.build_adiscord_ivn_geography import normal_from_height


CITY_TABLE = {
    2845: (469, 20, "Монтера"),
    9899: (459, 10, "Аркен"),
    6028: (460, 8, "Вальд"),
    4018: (468, 8, "Кронау"),
    6748: (471, 6, "Валтор"),
    10815: (473, 6, "Зольден"),
    212: (425, 5, "Келвор"),
    8865: (448, 5, "Салвен"),
    3859: (456, 5, "Брейден"),
    10541: (438, 4, "Гельмар"),
    2090: (444, 4, "Ольдерн"),
    7404: (445, 4, "Рендар"),
    6835: (453, 4, "Таллер"),
    10504: (464, 4, "Ульвар"),
    418: (467, 4, "Эрдин"),
    8729: (470, 4, "Вирен"),
    10095: (472, 4, "Фейвар"),
    9322: (439, 3, "Лирен"),
    11365: (462, 3, "Терлан"),
    8159: (466, 3, "Хальден"),
}
VILLAGE_TABLE = [
    (425, "Верхний Келвор", 1),
    (438, "Гельмарский рудник", 1),
    (439, "Лиренский брод", 1),
    (444, "Хорн", 1),
    (445, "Таннвальд", 1),
    (448, "Брайтгоф", 1),
    (453, "Тихая Гать", 1),
    (456, "Ормен", 1),
    (459, "Старый Аркен", 2),
    (460, "Корвель", 1),
    (462, "Стейнау", 1),
    (464, "Ульварский брод", 1),
    (466, "Хальденский перевал", 2),
    (467, "Гердау", 1),
    (468, "Кронауские шахты", 1),
    (469, "Фаллен", 2),
    (469, "Коронный тракт", 1),
    (470, "Дравенская сторожка", 1),
    (471, "Ланнау", 1),
    (472, "Фейварская мельница", 1),
    (473, "Зольденские промыслы", 1),
]


def decode(data: bytes) -> np.ndarray:
    with Image.open(BytesIO(data)) as image:
        return np.array(image)


def current(path) -> np.ndarray:
    with Image.open(mon.ROOT / path) as image:
        return np.array(image)


class PureHelperTests(unittest.TestCase):
    def test_data_file_keeps_its_authored_layout(self) -> None:
        text = (mon.ROOT / mon.DATA_PATH).read_text(encoding="utf-8")
        self.assertEqual(mon.dump_data(mon.read_json(mon.ROOT)), text)
        self.assertNotIn("\r", text)
        self.assertFalse((mon.ROOT / mon.DATA_PATH).read_bytes().startswith(b"\xef\xbb\xbf"))

    def test_state_line_course_follows_a_diagonal_line_without_gaps(self) -> None:
        ys, xs = np.mgrid[0:20, 0:20]
        foreign = xs + ys >= 20
        mon_land = ~foreign
        course = mon.state_line_course(mon_land, foreign)
        self.assertEqual(label(course)[1], 1)
        near = foreign.copy()
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                near |= np.roll(np.roll(foreign, dy, 0), dx, 1)
        self.assertFalse((course & ~near).any())
        self.assertFalse((course & foreign).any())

    def test_stray_land_finds_a_cut_and_tolerates_a_state_line_sliver(self) -> None:
        inside = np.zeros((9, 9), bool)
        inside[1:8, 1:8] = True
        river = np.zeros((9, 9), bool)
        river[4, 1:8] = True
        self.assertTrue(mon.stray_land(inside, river, np.zeros((9, 9), bool)).any())
        river = np.zeros((9, 9), bool)
        river[2, 1:3] = True
        river[1, 3] = True
        slivers = np.zeros((9, 9), bool)
        slivers[1, 1:3] = True
        self.assertFalse(mon.stray_land(inside, river, slivers).any())
        self.assertTrue(mon.stray_land(inside, river, np.zeros((9, 9), bool)).any())

    def test_width_network_widens_below_joins_and_caps_tributaries(self) -> None:
        data = {
            "rivers": [
                {"name": "main", "points": [], "mouth": {"lake": 1}},
                {"name": "side", "points": [], "mouth": {"river": "main"}},
                {"name": "out", "points": [], "mouth": {"river": "existing"}},
                {"name": "feeder", "points": [], "mouth": {"river": "out"}},
            ]
        }
        main = [(x, 0) for x in range(1, 41)]
        side = [(20, y) for y in range(10, 1, -1)] + [(20, 1)]
        out = [(x, 20) for x in range(1, 61)]
        feeder = [(30, y) for y in range(30, 21, -1)] + [(30, 21)]
        rivers = np.full((40, 70), mon.RIVER_LAND_PALETTE, np.uint8)
        rivers[19, 61] = 4
        routes = {"main": main, "side": side, "out": out, "feeder": feeder}
        confluences = {
            "side": mon.Confluence("side", "main", (20, 1), (20, 0)),
            "out": mon.Confluence("out", "existing", (60, 20), (61, 19)),
            "feeder": mon.Confluence("feeder", "out", (30, 21), (30, 20)),
        }
        mon.assign_widths(data, routes, confluences, rivers)

        def widths(name):
            return [int(rivers[y, x]) for x, y in routes[name][1:-1]]

        for name in routes:
            self.assertEqual(widths(name), sorted(widths(name)), name)
            self.assertFalse(set(widths(name)) - set(mon.WIDTH_STEPS), name)
        side_end = widths("side")[-1]
        self.assertGreaterEqual(int(rivers[0, 20]), mon.wider(max(side_end, int(rivers[0, 19]))))
        self.assertLessEqual(max(widths("out")), 4)
        self.assertLessEqual(max(widths("feeder")), mon.narrower(int(rivers[20, 30])))

    def test_flow_in_pixels_touch_the_receiver_on_one_side_mid_course(self) -> None:
        receiver = np.zeros((12, 12), bool)
        receiver[2:10, 5] = True
        current = receiver.copy()
        lane = np.ones((12, 12), bool)
        window = mon.Window(0, 12, 0, 12)
        river = {"points": [[8, 6]]}
        approaches = mon.confluence_approaches(river, receiver, current, lane, window, np.zeros((12, 12), bool))
        self.assertTrue(approaches)
        taken = np.zeros((12, 12), bool)
        taken[:, 6:] = True
        for (fx, _fy) in mon.confluence_approaches(river, receiver, current, lane, window, taken):
            self.assertLess(fx, 6)
        for (fx, fy), (px, py) in approaches.items():
            self.assertTrue(3 <= py <= 8)
            self.assertEqual(abs(fx - px) + abs(fy - py), 1)
            self.assertEqual(fy, py)

    def test_wide_river_reaches_the_widest_palette_quickly(self) -> None:
        river = {"wide": True}
        palettes = [mon.course_palette(river, index, 200) for index in range(1, 200)]
        self.assertGreaterEqual(palettes.count(mon.WIDEST_RIVER_PALETTE) / len(palettes), 0.85)
        self.assertEqual(palettes, sorted(palettes))
        narrow = [mon.course_palette({}, index, 200) for index in range(1, 200)]
        self.assertEqual(narrow[0], 3)

    def test_canyon_cut_has_a_floor_steep_walls_and_a_mon_rim(self) -> None:
        shape = (40, 30)
        window = mon.Window(0, shape[0], 0, shape[1])
        rows = np.arange(shape[0])[:, None] * np.ones(shape[1])
        mon_land = rows < 20
        foreign = ~mon_land
        distance = np.where(mon_land, 20 - rows, rows - 19) - 0.5
        feature = {"floor": 99, "half_width": 4, "rim_lift": 6, "band": 6}
        band = foreign & (distance <= 6)
        canyon = mon.Canyon(feature, foreign, distance, band, mon_land & (rows == 19))
        heights = np.full(shape, 125.0)
        cut = mon.cut_canyons(heights, [canyon], mon_land, window, 97.0)
        self.assertTrue((cut >= 97.0).all())
        self.assertLessEqual(cut[19, 15], 102.5)
        self.assertLessEqual(cut[20, 15], 102.5)
        self.assertGreater(cut[14, 15], 124.0)
        self.assertGreater(cut[13:16, 15].max(), 127.0)
        self.assertTrue((cut[foreign] <= heights[foreign]).all())
        self.assertTrue(np.array_equal(cut[rows > 30], heights[rows > 30]))

    def test_thinning_leaves_a_simple_line(self) -> None:
        rivers = np.full((8, 8), mon.RIVER_LAND_PALETTE, np.uint8)
        rivers[1:7, 3] = 6
        rivers[3:5, 4] = 6
        water = np.zeros((8, 8), bool)
        editable = np.ones((8, 8), bool)
        self.assertTrue(mon.river_blocks(rivers < 254).any())
        mon.thin_courses(rivers, editable, water, np.zeros((8, 8), bool))
        river = rivers < 254
        self.assertFalse(mon.river_blocks(river).any())
        self.assertTrue(river[1:7, 3].all())
        self.assertEqual(mon.course_shape_issues(rivers, editable, water, (0, 0)), [])

    def test_walks_draw_each_pixel_once(self) -> None:
        rivers = np.full((12, 12), mon.RIVER_LAND_PALETTE, np.uint8)
        rivers[1, 5] = mon.RIVER_SOURCE_PALETTE
        rivers[2:10, 5] = 9
        rivers[5, 6] = mon.RIVER_FLOW_IN_PALETTE
        rivers[5, 7:10] = 4
        water = np.zeros((12, 12), bool)
        visits, forks, walks = mon.walk_courses(rivers, water)
        self.assertEqual(forks, [])
        self.assertTrue((visits[rivers < 254] == 1).all())
        self.assertEqual(walks[(5, 1)][-1], (5, 9))
        self.assertEqual(walks[(6, 5)][-1], (9, 5))
        rivers[5, 6] = 4
        _visits, forks, _walks = mon.walk_courses(rivers, water)
        self.assertEqual(forks, [(5, 5)])

    def test_tributary_starts_lead_away_from_the_receiver(self) -> None:
        river = np.zeros((9, 9), bool)
        river[1:8, 4] = True
        river[4, 5] = True
        river[4, 6:8] = True
        self.assertEqual(mon.tributary_starts(river, (5, 4)), [(6, 4)])

    def test_reference_rivers_restore_the_recorded_pixels(self) -> None:
        data = {"existing_rivers": {"12": [[30, 6], [31, 1]], "13": [[31, 0]]}}
        window = mon.Window(10, 20, 25, 40)
        rivers = mon.reference_rivers(data, window, (10, 15))
        self.assertEqual(int(rivers[2, 5]), 6)
        self.assertEqual(int(rivers[2, 6]), 1)
        self.assertEqual(int(rivers[3, 6]), 0)
        self.assertEqual(int((rivers < mon.RIVER_SEA_PALETTE).sum()), 3)


class DataContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.data = mon.read_json(mon.ROOT)
        cls.scope = mon.load_scope(mon.ROOT, cls.data)

    def test_settlement_table_matches_the_design(self) -> None:
        cities = {
            entry["parent"]: (entry["state"], entry["value"], entry["name"])
            for entry in self.data["settlements"]
            if entry["kind"] == "city"
        }
        self.assertEqual(cities, CITY_TABLE)
        villages = [
            (entry["state"], entry["name"], entry["value"])
            for entry in self.data["settlements"]
            if entry["kind"] == "village"
        ]
        self.assertEqual(villages, VILLAGE_TABLE)
        districts = [entry for entry in self.data["settlements"] if entry["kind"] == "district"]
        self.assertEqual([entry["parent"] for entry in districts], [2845])

    def test_plan_ids_are_contiguous_and_stay_in_their_states(self) -> None:
        planned = self.data["planned"]
        ids = [entry["province"] for entry in planned["provinces"]]
        self.assertEqual(ids, list(range(planned["first_id"], planned["first_id"] + len(ids))))
        kinds = Counter(entry["kind"] for entry in planned["provinces"])
        self.assertEqual(kinds, Counter({"remainder": 20, "district": 1}))
        for entry in planned["provinces"]:
            self.assertEqual(self.scope.state_of[entry["parent"]], entry["state"])
        self.assertEqual({int(key): value for key, value in planned["cities"].items()}, {city: city for city in CITY_TABLE})

    def test_villages_are_recorded_on_rural_provinces_of_their_state(self) -> None:
        planned = self.data["planned"]
        recorded = {}
        for entry in self.data["settlements"]:
            if entry["kind"] != "village":
                continue
            self.assertIsNotNone(entry["province"], entry["name"])
            self.assertEqual(self.scope.state_of[entry["province"]], entry["state"], entry["name"])
            self.assertNotIn(entry["province"], CITY_TABLE)
            self.assertNotIn(entry["province"], self.scope.planned)
            recorded.setdefault(str(entry["state"]), []).append(entry["province"])
        self.assertEqual(recorded, planned["villages"])


class PlanTests(unittest.TestCase):
    """Properties of the computed outputs; they hold before and after the apply."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.plan = mon.build_plan(mon.ROOT)
        cls.data = mon.read_json(mon.ROOT)
        cls.scope = mon.load_scope(mon.ROOT, cls.data)
        definition = mon.read_definition(mon.ROOT)
        mon.register_planned_rows(definition, cls.data)
        cls.colours = definition.colours()
        cls.kinds = definition.kinds()
        cls.rgb = decode(cls.plan.outputs[mon.PROVINCES])
        cls.grid = mon.province_grid(cls.rgb, cls.colours)
        cls.before = mon.province_grid(current(mon.PROVINCES), cls.colours)
        cls.mon = np.isin(cls.grid, list(cls.scope.provinces))
        window = mon.mon_window(cls.grid, cls.scope.provinces)
        ground = mon.prepare_ground(
            mon.ROOT, cls.data, cls.scope, cls.grid, cls.kinds, current(mon.HEIGHTMAP)[window.s], window
        )
        cls.relief_scope = np.zeros(cls.grid.shape, bool)
        cls.relief_scope[window.s] = ground.relief_scope
        cls.rivers = decode(cls.plan.outputs[mon.RIVERS])
        cls.water = np.isin(cls.grid, [province for province, kind in cls.kinds.items() if kind != "land"])
        cls.declared = {
            int(line.split(";")[0]): line.split(";")[6]
            for line in cls.plan.outputs[mon.DEFINITION].decode("utf-8-sig").splitlines()
        }

    def test_only_the_mon_scope_changes(self) -> None:
        for path in (mon.TERRAIN, mon.CITIES):
            changed = current(path) != decode(self.plan.outputs[path])
            self.assertFalse((changed & ~self.mon).any(), path)
        before = current(mon.RIVERS)
        after = self.rivers
        outside = (before != after) & ~self.mon
        window = mon.mon_window(self.grid, self.scope.provinces)
        reach, issues = mon.owned_reach_mask(
            self.data, window, after[window.s], self.grid[window.s].astype(np.int64), self.water[window.s]
        )
        self.assertEqual(issues, [])
        owned = np.zeros(self.grid.shape, bool)
        owned[window.s] = reach
        # Outside MON an owned reach only widens, closes its diagonal steps,
        # applies its authored pixel edits, takes over the flow-in marker on its
        # course, gives the river it meets a flow-in pixel beside it and turns
        # that river's source pixel into plain width.
        widened = owned & ((after >= before) | (before >= mon.RIVER_SEA_PALETTE))
        for reach in self.data["owned_reaches"]:
            for x, y in reach.get("drop", []):
                widened[y, x] = after[y, x] == mon.RIVER_LAND_PALETTE
        flow_in = (after == mon.RIVER_FLOW_IN_PALETTE) & mon.neighbours_of(owned) & (before < mon.RIVER_SEA_PALETTE)
        sourceless = (before == mon.RIVER_SOURCE_PALETTE) & (after >= mon.WIDTH_STEPS[0]) & (after < mon.RIVER_SEA_PALETTE)
        self.assertFalse((outside & ~(widened | flow_in | sourceless)).any())
        heights = current(mon.HEIGHTMAP) != decode(self.plan.outputs[mon.HEIGHTMAP])
        self.assertFalse((heights & ~self.relief_scope).any())
        self.assertFalse((self.relief_scope & ~self.mon & self.water).any())
        changed_provinces = (current(mon.PROVINCES) != self.rgb).any(axis=2)
        self.assertTrue(set(np.unique(self.before[changed_provinces]).tolist()) <= self.scope.provinces)

    def test_normals_follow_the_native_formula_inside_the_scope_and_its_feather(self) -> None:
        normal = decode(self.plan.outputs[mon.WORLD_NORMAL])
        with Image.open(mon.ROOT / mon.WORLD_NORMAL) as source:
            expected = normal_from_height(
                Image.fromarray(decode(self.plan.outputs[mon.HEIGHTMAP])),
                source.convert("RGB"),
                bytearray(self.relief_scope.tobytes()),
            )
        self.assertTrue(np.array_equal(normal, np.asarray(expected)))
        cells = self.relief_scope.reshape(normal.shape[0], 2, normal.shape[1], 2).any(axis=(1, 3))
        feather = cells.copy()
        feather[1:] |= cells[:-1]
        feather[:-1] |= cells[1:]
        feather[:, 1:] |= cells[:, :-1]
        feather[:, :-1] |= cells[:, 1:]
        changed = (current(mon.WORLD_NORMAL) != normal).any(axis=2)
        self.assertFalse((changed & ~feather).any())

    def test_state_areas_and_text_files_keep_their_shape(self) -> None:
        for state_id in self.scope.states:
            members = [province for province, owner in self.scope.state_of.items() if owner == state_id]
            self.assertTrue(np.array_equal(np.isin(self.before, members), np.isin(self.grid, members)), state_id)
        for path in (mon.DEFINITION, mon.UNITSTACKS):
            original = (mon.ROOT / path).read_bytes()
            output = self.plan.outputs[path]
            if b"\r\n" in original:
                self.assertEqual(output.count(b"\n"), output.count(b"\r\n"), path)
            else:
                self.assertNotIn(b"\r\n", output, path)
        old_rows = (mon.ROOT / mon.DEFINITION).read_bytes().decode("utf-8-sig").splitlines()
        new_rows = self.plan.outputs[mon.DEFINITION].decode("utf-8-sig").splitlines()
        for before, after in zip(old_rows, new_rows):
            if before != after:
                self.assertIn(int(before.split(";")[0]), self.scope.provinces)
                self.assertEqual(before.split(";")[:6] + before.split(";")[7:], after.split(";")[:6] + after.split(";")[7:])

    def test_cities_are_compact_urban_junctions_without_rivers(self) -> None:
        cities_bmp = decode(self.plan.outputs[mon.CITIES])
        terrain = decode(self.plan.outputs[mon.TERRAIN])
        shore = mon.urban_blocked(self.water)
        adjacency = mon.province_adjacency(self.grid[mon.mon_window(self.grid, self.scope.provinces).s])
        river = self.rivers < mon.RIVER_SEA_PALETTE
        for city in [*CITY_TABLE, *self.scope.districts]:
            mask = self.grid == city
            self.assertTrue(40 <= mask.sum() <= 50, city)
            self.assertEqual(label(mask)[1], 1, city)
            land = {province for province in adjacency[city] if self.kinds.get(province) == "land"}
            self.assertGreaterEqual(len(land), 3, city)
            self.assertFalse((mask & river).any(), city)
            self.assertEqual(self.declared[city], "urban")
            built = mask & ~shore
            self.assertTrue((cities_bmp[built] == mon.CITY_HOUSES_INDEX).all(), city)
            self.assertTrue((terrain[built] == mon.URBAN_PALETTE).all(), city)
        for remainder in self.scope.remainders.values():
            self.assertGreaterEqual((self.grid == remainder).sum(), mon.REMAINDER_MIN_PIXELS)
            self.assertNotEqual(self.declared[remainder], "urban")

    def test_villages_keep_rural_terrain_and_carry_a_small_core(self) -> None:
        cities_bmp = decode(self.plan.outputs[mon.CITIES])
        for entry in self.data["settlements"]:
            if entry["kind"] != "village":
                continue
            province = entry["province"]
            self.assertIn(self.declared[province], mon.TERRAIN_BANDS, entry["name"])
            houses = (self.grid == province) & (cities_bmp == mon.CITY_HOUSES_INDEX)
            self.assertTrue(6 <= houses.sum() <= 9, entry["name"])

    def test_rivers_run_on_borders_and_cut_no_province(self) -> None:
        self.assertEqual([issue for issue in self.plan.issues if "river" in issue and "railway" not in issue], [])
        river = (self.rivers < mon.RIVER_SEA_PALETTE) & ~self.water
        scoped = river & self.relief_scope
        lines = mon.line_pixels(self.grid.astype(np.int64))
        self.assertFalse((scoped & ~lines).any())
        window = mon.mon_window(self.grid, self.scope.provinces)
        labels = self.grid[window.s].astype(np.int64)
        slivers = np.zeros(labels.shape, bool)
        for canyon in mon.canyon_layers(mon.ROOT, self.data, labels, self.mon[window.s], self.water[window.s]):
            slivers |= self.mon[window.s] & mon.neighbours_of(canyon.foreign)
        split = mon.rivers_splitting_provinces(labels, river[window.s], self.relief_scope[window.s], slivers)
        self.assertEqual(split, [])

    def test_declared_terrain_meets_the_bands_and_the_state_names(self) -> None:
        self.assertEqual(
            [issue for issue in self.plan.issues if "provinces lie outside" in issue or issue.startswith("state ")], []
        )
        heights = decode(self.plan.outputs[mon.HEIGHTMAP])[self.mon]
        self.assertGreaterEqual(int(heights.min()), self.data["heights"]["min"])
        self.assertLessEqual(int(heights.max()), self.data["heights"]["max"])
        for province in self.scope.provinces:
            self.assertNotIn(self.declared[province], mon.FORBIDDEN_TERRAINS)

    def test_the_rina_canyon_is_deep_and_carries_a_wide_river(self) -> None:
        profile = self.plan.report["canyons"]["Rina canyon"]
        self.assertLessEqual(profile["floor"], 102.0)
        self.assertGreaterEqual(profile["mon_rim"] - profile["floor"], 15.0)
        self.assertGreaterEqual(profile["far_wall"] - profile["floor"], 15.0)
        route = self.plan.report["rivers"]["Rina gorge"]
        self.assertGreater(route["length"], 150)
        # The gorge river is as wide as the river it joins lets it be.
        join = self.plan.report["confluences"]["Rina gorge"]
        self.assertEqual(join["inflow"], join["receiver_width"])

    def test_every_confluence_meets_a_wider_reach_square_on(self) -> None:
        confluences = self.plan.report["confluences"]
        self.assertEqual(
            set(confluences),
            {river["name"] for river in self.data["rivers"] if "river" in river["mouth"]},
        )
        for name, join in confluences.items():
            self.assertLessEqual(join["inflow"], join["receiver_width"], name)
            self.assertEqual(join["contacts"], 1, name)
            self.assertTrue(join["mid_course"], name)
            self.assertTrue(join["square"], name)
            if join["receiver"] != "existing":
                self.assertGreaterEqual(join["receiver_width"], min(11, mon.wider(max(join["inflow"], join["upstream"]))), name)
        for name, widths in self.plan.report["widths"].items():
            self.assertEqual(widths, sorted(widths), name)
            self.assertFalse(set(widths) - set(mon.WIDTH_STEPS), name)
        river = self.rivers[self.mon]
        self.assertFalse(np.isin(river, (5, 8)).any())

    def test_owned_reaches_carry_their_width_down_to_the_lake(self) -> None:
        window = mon.mon_window(self.grid, self.scope.provinces)
        reach, _issues = mon.owned_reach_mask(
            self.data, window, self.rivers[window.s], self.grid[window.s].astype(np.int64), self.water[window.s]
        )
        widths = self.rivers[window.s][reach]
        self.assertGreater(len(widths), 100)
        self.assertTrue((widths >= self.data["owned_reaches"][0]["width"]).all())
        gorge = self.plan.report["confluences"]["Rina gorge"]
        self.assertGreaterEqual(gorge["inflow"], 10)
        widths = self.plan.report["widths"]["Rina gorge"]
        self.assertGreaterEqual(sum(width >= 9 for width in widths) / len(widths), 0.95)

    def test_markers_follow_the_native_drawing_rules(self) -> None:
        words = ("source pixel", "junctions", "owned reach", "tributary", "2x2", "third course", "walk", "drawn")
        markers = [issue for issue in self.plan.issues if any(word in issue for word in words)]
        self.assertEqual(markers, [])
        for river in self.data["rivers"]:
            path = self.plan.report["rivers"][river["name"]]
            x, y = path["source"]
            is_source = int(self.rivers[y, x]) == mon.RIVER_SOURCE_PALETTE
            self.assertEqual(is_source, "lake" in river["mouth"], river["name"])

    def test_rivers_entering_a_canyon_descend_to_its_floor(self) -> None:
        self.assertEqual([issue for issue in self.plan.issues if "ravine" in issue or "gorge floor" in issue], [])
        ravines = self.plan.report["ravines"]
        self.assertIn("Valta", ravines)
        for name, ravine in ravines.items():
            profile = ravine["profile"]
            self.assertLessEqual(profile[-1], ravine["floor"] + mon.RAVINE_FLOOR_TOLERANCE, name)
            self.assertGreaterEqual(profile[0] - profile[-1], 8, name)

    def test_railway_segments_join_touching_provinces(self) -> None:
        """Passes once the theatre chains run through the remainders the plan names."""
        self.assertEqual([issue for issue in self.plan.issues if "railway" in issue], [])


def applied() -> bool:
    planned = mon.read_json(mon.ROOT)["planned"]
    rows = (mon.ROOT / mon.DEFINITION).read_bytes().decode("utf-8-sig").splitlines()
    return bool(planned["provinces"]) and any(row.startswith(f"{planned['first_id']};") for row in rows)


@unittest.skipUnless(applied(), "the MON geography has not been applied yet")
class AppliedMapTests(unittest.TestCase):
    def test_check_is_clean_after_the_apply(self) -> None:
        plan = mon.build_plan(mon.ROOT)
        self.assertEqual(mon.stale_outputs(plan, mon.ROOT), [])


if __name__ == "__main__":
    unittest.main()
