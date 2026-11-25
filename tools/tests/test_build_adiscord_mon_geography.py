"""Contracts of the Montar Empire and eastern neighbours geography builder."""

from __future__ import annotations

import json
import re
import tempfile
import unittest
from collections import Counter
from io import BytesIO
from math import ceil
from pathlib import Path
from unittest.mock import patch

import numpy as np
from PIL import Image
from scipy.ndimage import distance_transform_edt, label

from tools.builders import build_adiscord_coastal_geography as coastal
from tools.builders import build_adiscord_mon_geography as mon
from tools.builders.build_adiscord_ivn_geography import (
    FIELD_MAX_SHARE,
    FIELD_MIN_PATCH,
    FIELD_SHORE_PIXELS,
    normal_from_height,
)
from tools.builders.build_adiscord_new_states import STATE_SPLITS
from tools.lib import adiscord_vorkerland_theatre_manifest as theatre
from tools.lib.adiscord_planned_geography import east_stage_labels, east_stages


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
NEIGHBOUR_STATES = {
    "BOR": [89, 126, 135, 139, 140, 142, 143],
    "DOL": [133, 136, 137, 138, 141],
    "RIN": [134, 147, 148, 149],
    "TMR": [409, 410, 416, 419, 423, 426, 429, 431, 436, 443, 454, 455],
    "VEL": [414, 417, 418, 421, 428, 434],
    "DRV": [440, 450, 451, 458, 463, 465],
}
CAPITAL_VP = {"BOR": 8, "DOL": 8, "RIN": 8, "TMR": 10, "VEL": 10, "DRV": 10}
# The first Stage 2 id follows the last province of the map Stage 1 left.
STAGE2_FIRST_ID = 19306
# Course pixels that cannot reach a province border: each turns on a diagonal
# step of the state line with an IVN province, whose pixels and rivers the IVN
# geography builder owns, and no other province of the scope lies beside it.
IVN_EDGE_TURNS = frozenset(
    {(2959, 999), (2905, 1028), (2924, 1028), (2904, 1029), (2922, 1029), (2903, 1030), (2902, 1031)}
)
# Stage 3 states without a settlement of their own. Westerholm (202) is one
# coastal province of 66 px, too small for a city and its remainder.
CITYLESS_STATES = frozenset({202})
# Stage 3 states without a town: the Vorkensberg conurbation (32-40) and the
# all-urban states (102, 104, 105, 121) have no rural province to carve it from;
# Remmel (200) and Kairholm (201) are single port provinces; the theatre
# package of Upper Solarino (310) totals one VP, which its city holds.
TOWNLESS_STATES = frozenset({32, 33, 34, 35, 36, 37, 38, 39, 40, 102, 104, 105, 121, 200, 201, 202, 310})
# The coastal builder places the unit anchors of the provinces it repairs.
COASTAL_ANCHOR_PROVINCES = frozenset(coastal.PROVINCE_REPAIR_PROVINCES)
# Moving slots 1-8 and 22-29 and the attacking slot 9 point at a neighbour.
SEAWARD_SLOTS = frozenset((*range(1, 10), *range(22, 30)))
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


def current(path, mode: str | None = None) -> np.ndarray:
    with Image.open(mon.ROOT / path) as image:
        return np.array(image if mode is None else image.convert(mode))


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

    def test_a_river_cuts_a_ridge_with_a_wide_gentle_valley(self) -> None:
        size = 200
        ridge = 100.0 + 60.0 * np.exp(-(((np.arange(size) - 100) / 10.0) ** 2))
        field = np.tile(ridge, (size, 1))
        rivers = np.full((size, size), mon.RIVER_LAND_PALETTE, np.uint8)
        rivers[100, 4:196] = 10
        rivers[100, 4] = mon.RIVER_SOURCE_PALETTE
        water = np.zeros((size, size), bool)
        water[:, 196:] = True
        scope = np.zeros((size, size), bool)
        scope[3:197, 3:196] = True
        before = field.copy()
        mon.carve_river_beds(field, rivers, water, scope, before.copy(), np.ones((size, size)))
        bed = field[100, 4:196]
        self.assertLessEqual(float(np.max(bed - np.minimum.accumulate(bed))), 0.01)
        self.assertLessEqual(float(bed.max()), 100.01)
        # Across the river the walls of the 60-unit cut rise gently, not as a trench.
        walls = np.abs(np.diff(field[88:113, 80:121], axis=0))
        self.assertLessEqual(float(walls.max()), 2.5)
        np.testing.assert_array_equal(field[~scope], before[~scope])

    def test_field_states_follow_the_fields_flag_of_mon_and_each_region(self) -> None:
        data = {"states": [1, 2], "regions": {"A": {"states": [3], "fields": True}, "B": {"states": [4]}}}
        self.assertEqual(mon.field_states(data), [3])
        self.assertEqual(mon.field_states({**data, "fields": True}), [1, 2, 3])


class Stage2HelperTests(unittest.TestCase):
    def test_nested_sections_open_one_record_per_line(self) -> None:
        data = {
            "stage2": {
                "existing_rivers": {"900": [[3000, 6]], "901": [[3001, 6]]},
                "planned": {"origin": [1, 2], "provinces": [{"province": 1}, {"province": 2}], "towns": {"5": 5}},
            },
            "regions": {"BOR": {"states": [89], "levels": [{"name": "a"}], "terrain_bands": {"plains": [1, 2]}}},
        }
        text = mon.dump_data(data)
        self.assertEqual(json.loads(text), data)
        lines = text.splitlines()
        self.assertIn('      "900": [[3000, 6]],', lines)
        self.assertIn('        {"province": 1},', lines)
        self.assertIn('      "towns": {"5": 5}', lines)
        self.assertIn('      "terrain_bands": {"plains": [1, 2]}', lines)

    def test_geometry_layers_stack_the_two_plans(self) -> None:
        sheet = np.zeros((10, 6, 4), np.uint8)
        data = {"planned": {"origin": [5, 6]}, "stage2": {"planned": {"sheet_row": 4, "origin": [1, 2], "provinces": [{}]}}}
        layers = mon.geometry_layers(data, sheet)
        self.assertEqual([(origin, layer.shape[0]) for origin, layer in layers], [([5, 6], 4), ([1, 2], 6)])
        self.assertEqual(len(mon.geometry_layers(mon.stage1_data(data), sheet)), 1)
        self.assertEqual(mon.geometry_layers(mon.stage1_data(data), sheet)[0][1].shape[0], 4)

    def test_partition_gives_round_whole_parts(self) -> None:
        region = np.zeros((16, 26), bool)
        region[1:15, 1:25] = True
        parts = ceil(int(region.sum()) / mon.SPLIT_PART_PIXELS)
        owner, whole, lowest = mon.partition_province(region, parts)
        self.assertTrue(whole)
        self.assertGreaterEqual(lowest, mon.PART_MIN_ROUNDNESS)
        for index in range(parts):
            part = owner == index
            self.assertEqual(label(part)[1], 1)
            self.assertGreaterEqual(int(part.sum()), mon.PART_MIN_PIXELS)
        self.assertFalse((owner[region] < 0).any())

    def test_partition_lets_a_river_run_between_parts(self) -> None:
        region = np.zeros((18, 14), bool)
        region[1:17, 1:13] = True
        river = np.zeros(region.shape, bool)
        river[9, 1:13] = True
        owner, whole, _lowest = mon.partition_province(region, 2, river=river)
        self.assertTrue(whole)
        nothing = np.zeros(region.shape, bool)
        for index in range(2):
            self.assertFalse(mon.stray_land(owner == index, river, nothing).any())

    def test_mending_gives_a_cut_off_piece_to_its_land_neighbour(self) -> None:
        labels = np.full((7, 9), 9, np.int32)
        labels[1:6, 1:5] = 1
        labels[1:6, 5:8] = 2
        labels[3, 5] = 1
        river = np.zeros(labels.shape, bool)
        river[2:5, 4] = True
        mon.mend_river_cuts(labels, river, [1, 2])
        self.assertEqual(int(labels[3, 5]), 2)
        self.assertEqual(int(labels[2, 2]), 1)

    def test_corners_move_only_between_editable_provinces_of_one_state(self) -> None:
        labels = np.array([[1, 2], [3, 4]], np.int32)
        labels = np.pad(labels, 1, mode="edge")
        editable = np.ones(labels.shape, bool)
        mon.clear_corners(labels, editable, {1: 10, 2: 10, 3: 10, 4: 10})
        a, b, c, d = labels[1, 1], labels[1, 2], labels[2, 1], labels[2, 2]
        self.assertFalse(len({int(a), int(b), int(c), int(d)}) == 4)
        frozen = np.array([[1, 2], [3, 4]], np.int32)
        frozen = np.pad(frozen, 1, mode="edge")
        with self.assertRaises(RuntimeError):
            mon.clear_corners(frozen, editable, {1: 10, 2: 11, 3: 12, 4: 13})

    def test_a_fork_becomes_a_tributary(self) -> None:
        rivers = np.full((14, 14), mon.RIVER_LAND_PALETTE, np.uint8)
        rivers[1, 5] = mon.RIVER_SOURCE_PALETTE
        rivers[2:12, 5] = 6
        rivers[6, 6:9] = 4
        water = np.zeros(rivers.shape, bool)
        _visits, forks, _walks = mon.walk_courses(rivers, water)
        self.assertEqual(forks, [(5, 6)])
        mon.settle_existing_markers(rivers, water, np.ones(rivers.shape, bool))
        visits, forks, _walks = mon.walk_courses(rivers, water)
        self.assertEqual(forks, [])
        self.assertTrue((visits[rivers < mon.RIVER_SEA_PALETTE] == 1).all())
        self.assertEqual(int(rivers[6, 6]), mon.RIVER_FLOW_IN_PALETTE)

    def test_a_course_without_markers_gets_a_source_away_from_water(self) -> None:
        rivers = np.full((12, 12), mon.RIVER_LAND_PALETTE, np.uint8)
        rivers[2:9, 6] = 6
        water = np.zeros(rivers.shape, bool)
        water[9:, :] = True
        mon.settle_existing_markers(rivers, water, np.ones(rivers.shape, bool))
        self.assertEqual(int(rivers[2, 6]), mon.RIVER_SOURCE_PALETTE)
        visits, forks, _walks = mon.walk_courses(rivers, water)
        self.assertEqual(forks, [])
        self.assertTrue((visits[(rivers < mon.RIVER_SEA_PALETTE) & ~water] == 1).all())

    def test_a_corner_inside_a_province_turns_on_the_border_instead(self) -> None:
        labels = np.zeros((8, 8), np.int64)
        labels[:, 4:] = 1
        labels[4:, 3] = 1
        rivers = np.full((8, 8), mon.RIVER_LAND_PALETTE, np.uint8)
        rivers[1:4, 3] = 6
        rivers[3, 2] = 6
        rivers[4:7, 2] = 6
        owned = np.ones((8, 8), bool)
        border = mon.province_borders(labels)
        self.assertFalse(border[3, 2])
        mon.flip_corners(rivers, owned, border, np.zeros((8, 8), bool), labels, owned)
        river = rivers < mon.RIVER_SEA_PALETTE
        self.assertFalse((river & ~border).any())
        self.assertEqual(label(river)[1], 1)

    def test_a_cut_off_piece_joins_its_land_neighbour_of_the_same_state(self) -> None:
        labels = np.full((9, 9), 9, np.int32)
        labels[1:8, 1:5] = 1
        labels[1:8, 5:8] = 2
        labels[4, 5] = 1
        river = np.zeros(labels.shape, bool)
        river[3:6, 4] = True
        river[3, 5] = True
        river[5, 5] = True
        scope = mon.Scope([10], {1: 10, 2: 10}, frozenset({1, 2}), {}, {}, frozenset(), {})
        mender = mon.GeometryMender(labels, river, scope)
        mender.mend_cut(1)
        self.assertEqual(int(labels[4, 5]), 2)
        self.assertEqual(mender.unresolved, [])
        nothing = np.zeros(labels.shape, bool)
        self.assertFalse(mon.stray_land(labels == 1, river, nothing).any())

    def test_a_split_marker_starts_its_own_walk(self) -> None:
        rivers = np.full((12, 12), mon.RIVER_LAND_PALETTE, np.uint8)
        rivers[1, 5] = mon.RIVER_SOURCE_PALETTE
        rivers[2:10, 5] = 9
        rivers[5, 6] = mon.RIVER_FLOW_OUT_PALETTE
        rivers[5, 7:10] = 4
        visits, forks, _walks = mon.walk_courses(rivers, np.zeros(rivers.shape, bool))
        self.assertEqual(forks, [])
        self.assertTrue((visits[rivers < mon.RIVER_SEA_PALETTE] == 1).all())

    def test_state_names_give_every_scope_state_one_landform(self) -> None:
        data = mon.read_json(mon.ROOT)
        states = [state_id for states in mon.region_states(data).values() for state_id in states]
        landforms = mon.state_landforms(mon.ROOT, states, data)
        self.assertEqual(set(landforms), set(states))
        expected = {126: "lowland", 140: "lowland", 143: "upland", 138: "upland", 147: "plains", 133: "forest", 135: "hills"}
        self.assertEqual({state_id: landforms[state_id] for state_id in expected}, expected)

    def test_roundness_prefers_a_disc_to_a_strip(self) -> None:
        ys, xs = np.mgrid[-8:9, -8:9]
        disc = xs * xs + ys * ys <= 64
        strip = np.zeros((4, 40), bool)
        strip[1:3, 1:39] = True
        self.assertGreater(mon.roundness(disc), 0.7)
        self.assertLess(mon.roundness(strip), mon.PART_MIN_ROUNDNESS)


class StageGeneralisationTests(unittest.TestCase):
    """Synthetic contracts of the stage list, the per-region parameters and the rail repair."""

    @staticmethod
    def layered_data() -> dict:
        return {
            "states": [469],
            "settlements": [{"state": 469, "kind": "city", "parent": 2845, "value": 20, "name": "a"}],
            "levels": [{"name": "mon", "states": [469], "range": [100, 120]}],
            "heights": {"min": 97, "max": 190, "feather": 8},
            "terrain_bands": {},
            "existing_rivers": {"1": [[2, 3]]},
            "planned": {"origin": [5, 6], "first_id": 10, "provinces": [{"province": 10, "parent": 2845, "state": 469, "kind": "remainder"}]},
            "stage2": {
                "ring_rivers": {"7": [[3, 4]]},
                "existing_rivers": {"2": [[4, 6]]},
                "planned": {"sheet_row": 4, "origin": [1, 2], "first_id": 11, "provinces": [{"province": 11, "parent": 1, "state": 89, "kind": "part"}]},
            },
            "regions": {
                "BOR": {"states": [89], "settlements": []},
                "WRK": {"stage": 3, "states": [32], "settlements": [{"state": 32, "kind": "adopt", "province": 7}]},
            },
        }

    def test_stage_layers_read_the_older_keys_then_the_stage_records(self) -> None:
        data = self.layered_data()
        self.assertEqual(sorted(mon.stage_layers(data)), [1, 2])
        self.assertEqual(mon.unplanned_stages(data), [3])
        self.assertEqual(mon.next_stage(data), 3)
        self.assertEqual(set(mon.active_data(data)["regions"]), {"BOR"})
        data["stages"] = [{"stage": 3, "sheet_row": 7, "origin": [9, 9], "first_id": 12, "provinces": [{"province": 12, "parent": 7, "state": 32, "kind": "part"}]}]
        self.assertEqual(sorted(mon.stage_layers(data)), [1, 2, 3])
        self.assertEqual(mon.unplanned_stages(data), [])
        self.assertIsNone(mon.next_stage(data))
        self.assertEqual([entry["province"] for entry in mon.planned_entries(data)], [10, 11, 12])
        self.assertEqual([entry["province"] for entry in mon.later_entries(data)], [11, 12])
        data["stages"].append({"stage": 3})
        with self.assertRaisesRegex(RuntimeError, "increasing order"):
            mon.stage_layers(data)

    def test_geometry_layers_stack_every_stage(self) -> None:
        data = self.layered_data()
        data["stage2"]["planned"]["provinces"] = [{}]
        data["stages"] = [{"stage": 3, "sheet_row": 7, "origin": [9, 9], "provinces": [{}]}]
        layers = mon.geometry_layers(data, np.zeros((10, 6, 4), np.uint8))
        self.assertEqual([(origin, layer.shape[0]) for origin, layer in layers], [([5, 6], 4), ([1, 2], 3), ([9, 9], 3)])

    def test_a_later_stage_plans_only_its_own_regions(self) -> None:
        data = self.layered_data()
        third = mon.stage_data(data, 3)
        self.assertEqual(set(third["regions"]), {"WRK"})
        self.assertEqual((third["states"], third["settlements"], third["planned"]["provinces"]), ([], [], []))
        self.assertEqual((third["levels"], third["existing_rivers"], third["stage2"]), ([], {}, {}))
        self.assertEqual(mon.region_states(third), {"MON": [], "WRK": [32]})
        second = mon.stage_data(data, 2)
        self.assertEqual(set(second["regions"]), {"BOR"})
        self.assertIs(second["stage2"], data["stage2"])

    def test_the_view_merges_the_river_snapshots_of_every_stage(self) -> None:
        data = self.layered_data()
        data["stages"] = [{"stage": 3, "existing_rivers": {"1": [[9, 4]]}, "ring_rivers": {"8": [[1, 6]]}}]
        view = mon.geography_view(mon.active_data(data))
        self.assertEqual(view["existing_rivers"], {"1": [[2, 3], [9, 4]], "2": [[4, 6]]})
        self.assertEqual(view["ring_rivers"], {"7": [[3, 4]], "8": [[1, 6]]})
        del data["stages"]
        self.assertIs(mon.geography_view(mon.active_data(data))["ring_rivers"], data["stage2"]["ring_rivers"])

    def test_the_shared_reader_follows_the_older_keys_with_the_stage_records(self) -> None:
        data = self.layered_data()
        data["stages"] = [{"stage": 3, "provinces": []}]
        stages = east_stages(data)
        self.assertEqual(len(stages), 3)
        self.assertEqual(east_stage_labels(stages), ("East stage 1", "East stage 2", "East stage 3"))

    def test_a_desert_zone_gives_desert_where_relief_and_forest_allow(self) -> None:
        heights = np.full((6, 8), 100, np.uint8)
        scope = np.ones(heights.shape, bool)
        nothing = np.zeros(heights.shape, bool)
        desert = np.zeros(heights.shape, bool)
        desert[:, :4] = True
        forest = np.zeros(heights.shape, bool)
        forest[:, 3] = True
        classes = mon.classify_pixels(heights, scope, forest, nothing, desert)
        names = np.array(mon.TYPE_ORDER)[classes]
        self.assertEqual(set(names[:, :3].ravel()), {"desert"})
        self.assertEqual(set(names[:, 3]), {"forest"})
        self.assertEqual(set(names[:, 4:].ravel()), {"plains"})
        self.assertTrue(np.array_equal(mon.classify_pixels(heights, scope, forest, nothing), mon.classify_pixels(heights, scope, forest, nothing, None)))
        self.assertEqual(mon.rural_terrain(Counter({"desert": 6, "plains": 4})), "desert")
        self.assertEqual(mon.rural_terrain(Counter({"desert": 3, "plains": 7})), "plains")
        self.assertEqual(mon.rural_terrain(Counter({"desert": 5, "hills": 5})), "hills")
        self.assertEqual(mon.rural_terrain(Counter({"forest": 6, "plains": 4})), mon.province_terrain_type(Counter({"forest": 6, "plains": 4})))
        self.assertEqual(mon.RURAL_PALETTES["desert"], mon.DESERT_PALETTE)

    def test_a_region_demotes_the_classes_it_does_not_allow(self) -> None:
        index = {name: position for position, name in enumerate(mon.TYPE_ORDER)}
        classes = np.array([[index["mountain"], index["forest"], index["desert"], index["mountain"]]], np.int8)
        states = np.array([[1, 1, 1, 2]])
        data = {"regions": {"X": {"states": [1], "terrain_classes": ["plains", "hills"]}}}
        mon.restrict_classes(classes, states, data)
        self.assertEqual([mon.TYPE_ORDER[value] for value in classes[0]], ["hills", "plains", "plains", "mountain"])
        with self.assertRaises(RuntimeError):
            mon.restrict_classes(classes, states, {"regions": {"X": {"states": [1], "terrain_classes": ["hills"]}}})

    def test_city_terrains_adopted_cities_and_pins_keep_their_terrain(self) -> None:
        def row(province: int, terrain: str) -> list[str]:
            return [str(province), "1", "2", "3", "land", "false", terrain, "1"]

        rows = {1: row(1, "vorkernsberg"), 2: row(2, "urban"), 3: row(3, "plains"), 4: row(4, "plains"), 5: row(5, "hills")}
        definition = mon.Definition([], "\n", b"", rows)
        scope = mon.Scope(
            [9], {province: 9 for province in rows}, frozenset(rows), {}, {2: 2}, frozenset(), {}, region_of={9: "X"},
            adopted=frozenset({4}), pinned={3: "mountain"},
        )
        self.assertEqual(mon.kept_terrains(scope, definition), {1: "vorkernsberg", 3: "mountain", 4: "plains"})
        labels = np.array([[1, 2, 3, 4, 5]])
        classes = np.full(labels.shape, mon.TYPE_ORDER.index("plains"), np.int8)
        desired, _counts = mon.province_types(classes, labels, scope, np.zeros(labels.shape, bool), mon.kept_terrains(scope, definition))
        self.assertEqual(desired, {1: "vorkernsberg", 2: "urban", 3: "mountain", 4: "plains", 5: "plains"})

    def test_a_province_kept_in_its_city_terrain_counts_in_no_band(self) -> None:
        scope = mon.Scope([9], {1: 9, 2: 9, 3: 9}, frozenset({1, 2, 3}), {}, {}, frozenset(), {}, region_of={9: "X"})
        desired = {1: "vorkernsberg", 2: "plains", 3: "plains"}
        issues, report = mon.terrain_issues(desired, scope, {9: "plains"}, {"plains": [2, 2]}, "X", frozenset({1}))
        self.assertEqual(issues, [])
        self.assertEqual(report["totals"], {"plains": 2})

    def test_keep_provinces_and_keep_above_freeze_their_ground(self) -> None:
        labels = np.full((5, 6), 900001, np.int32)
        labels[:, 4:] = 900002
        states = np.full(labels.shape, 7)
        states[4, :] = 8
        heights = np.full(labels.shape, 150, np.uint8)
        heights[0, 0] = 210
        heights[4, 1] = 210
        scope = np.ones(labels.shape, bool)
        region = {"name": "X", "states": [7], "keep_provinces": [900002], "keep_above": 205, "heights": {"min": 97, "max": 200}}
        data = {"heights": {"min": 97, "max": 190}, "regions": {"X": region}}
        frozen = mon.frozen_pixels(data, labels, scope, mon.Window(0, 5, 0, 6), heights, states)
        expected = labels == 900002
        expected[0, 0] = True
        self.assertTrue(np.array_equal(frozen, expected))
        region["heights"] = {"min": 97, "max": 210}
        with self.assertRaisesRegex(RuntimeError, "below keep_above"):
            mon.frozen_pixels(data, labels, scope, mon.Window(0, 5, 0, 6), heights, states)

    def test_a_later_stage_is_a_relief_group_with_a_frozen_belt(self) -> None:
        early = {"name": "early", "states": [2], "range": [100, 110]}
        late = {"name": "late", "states": [3], "range": [140, 150]}
        zone = {"name": "wood", "centre": [0, 0], "radii": [4, 4], "angle": 0}
        view = {
            "states": [1],
            "heights": {"feather": 2},
            "levels": [{"name": "mon", "states": [1], "range": [97, 99]}, early, late],
            "forest_zones": [zone],
            "regions": {"A": {"states": [2], "levels": [early]}, "B": {"stage": 3, "states": [3], "levels": [late], "forest_zones": [zone]}},
        }
        groups = mon.relief_groups(view)
        self.assertEqual([states for states, _view in groups], [[1, 2], [3]])
        self.assertEqual([level["name"] for level in groups[0][1]["levels"]], ["mon", "early"])
        self.assertEqual((groups[0][1]["forest_zones"], groups[1][1]["forest_zones"]), ([], [zone]))
        states = np.array([[1, 2, 3, 3, 3, 3]])
        belt = mon.stage_belt(view, np.ones(states.shape, bool), states)
        self.assertEqual(belt.tolist(), [[False, False, True, True, False, False]])
        del view["regions"]["B"]
        self.assertEqual(mon.relief_groups(view), [([1, 2], view)])

    def test_heights_follow_the_range_of_each_region(self) -> None:
        states = np.array([[469, 32]])
        data = {"heights": {"min": 97, "max": 190}, "states": [469], "regions": {"WRK": {"states": [32], "heights": {"min": 100, "max": 238}}}}
        low, high = mon.height_limits(data, states)
        self.assertEqual(low.tolist(), [[97, 100]])
        self.assertEqual(high.tolist(), [[190, 238]])
        self.assertEqual(mon.height_limits({"heights": {"min": 97, "max": 190}, "regions": {}}, states), (97.0, 190.0))

    @staticmethod
    def split_planner() -> mon.StagePlanner:
        """A planner over a synthetic window: WRK state 32 is never split, 41 splits above 40 px."""
        planner = mon.StagePlanner.__new__(mon.StagePlanner)
        labels = np.zeros((12, 20), np.int32)
        labels[0:6, 0:10] = 1
        labels[6:12, 0:10] = 2
        labels[0:5, 10:16] = 3
        labels[6:12, 10:20] = 4
        labels[0:6, 16:20] = 5
        planner.labels = labels
        planner.data = {"states": [], "regions": {"WRK": {"states": [32, 41]}}}
        planner.state_of = {1: 32, 2: 41, 3: 41, 4: 41, 5: 41}
        planner.kinds = {province: "land" for province in range(6)}
        planner.settled = set()
        planner.foreign = frozenset({4})
        planner.no_split_states = frozenset({32})
        planner.split_threshold = {32: 40, 41: 40}
        planner.sea = np.zeros(labels.shape, bool)
        planner.coastal_kept = []
        planner.adopted = []
        planner.cities = []
        planner.towns = []
        planner.scope = mon.Scope([32, 41], dict(planner.state_of), frozenset(planner.state_of), {}, {}, frozenset(), {})
        planner.city_terrain = {5: "vorkernsberg"}
        return planner

    def test_no_split_states_and_locked_provinces_are_never_split(self) -> None:
        planner = self.split_planner()
        self.assertEqual(planner.split_candidates(), [2])
        planner.split_threshold = {32: 40, 41: 70}
        self.assertEqual(planner.split_candidates(), [])

    def test_an_adopted_city_is_kept_and_a_never_split_state_carves_no_city(self) -> None:
        planner = self.split_planner()
        entry = {"state": 41, "kind": "adopt", "province": None}
        planner.plan_entry(entry)
        self.assertEqual(entry["province"], 5)
        self.assertEqual(planner.adopted, [5])
        self.assertIn(5, planner.settled)
        self.assertNotIn(5, planner.split_candidates())
        with self.assertRaisesRegex(RuntimeError, "only towns are carved"):
            planner.plan_entry({"state": 32, "kind": "city", "parent": 1})
        with self.assertRaisesRegex(RuntimeError, "outside state"):
            planner.plan_entry({"state": 32, "kind": "adopt", "province": 3})

    def test_settlement_issues_keep_an_adopted_city_whole(self) -> None:
        scope = mon.Scope([9], {5: 9, 6: 9}, frozenset({5}), {6: {"parent": 5, "kind": "part", "state": 9}}, {}, frozenset(), {}, parts={6: 5})
        data = {"settlements": [], "regions": {"X": {"states": [9], "settlements": [{"state": 9, "kind": "adopt", "province": 5}]}}}
        issues = mon.settlement_issues(data, scope, None)
        self.assertEqual(len(issues), 1)
        self.assertIn("keeps its geometry", issues[0])

    @staticmethod
    def literal_planner(literals: frozenset[int], naval: frozenset[int] = frozenset()) -> mon.StagePlanner:
        """A planner over a synthetic window: province 7 (10x20 px) splits in two; its west half has the railway."""
        planner = mon.StagePlanner.__new__(mon.StagePlanner)
        labels = np.full((14, 26), 9, np.int32)
        labels[2:12, 0:3] = 8
        labels[2:12, 3:23] = 7
        planner.labels = labels
        planner.state_of = {7: 41, 8: 41, 9: 41}
        planner.split_part = {41: 100}
        planner.part_minimum = {41: 40}
        planner.pairs = {(7, 8)}
        planner.river = np.zeros(labels.shape, bool)
        planner.sea = np.zeros(labels.shape, bool)
        planner.sea[12, 3:13] = True
        planner.window = mon.Window(0, 14, 0, 26)
        # The standing anchor of 7 stands in its east half, at map pixel (x 20, row 7).
        planner.points = {7: {"anchor": (20, 7)}}
        planner.literals = literals
        planner.naval = naval
        planner.victory_points = {}
        planner.hubs = frozenset()
        planner.entries = []
        planner.first_id = 100
        planner.splits = {}
        return planner

    def test_the_part_with_the_literal_anchors_keeps_the_id_before_the_railway(self) -> None:
        planner = self.literal_planner(frozenset())
        planner.split(7)
        self.assertEqual((planner.labels[7, 4], planner.labels[7, 20]), (7, 100))
        planner = self.literal_planner(frozenset({7}))
        planner.split(7)
        self.assertEqual((planner.labels[7, 4], planner.labels[7, 20]), (100, 7))
        self.assertEqual(planner.entries, [{"province": 100, "parent": 7, "state": 41, "kind": "part"}])
        # A naval base keeps its sea contact before its anchors.
        planner = self.literal_planner(frozenset({7}), frozenset({7}))
        planner.split(7)
        self.assertEqual((planner.labels[7, 4], planner.labels[7, 20]), (7, 100))

    def test_literal_issues_name_a_lost_id_and_a_naval_base_without_sea(self) -> None:
        scope = mon.Scope([41], {1: 41, 2: 41, 3: 41}, frozenset({1, 2, 3}), {}, {}, frozenset(), {})
        kinds = {1: "land", 2: "land", 3: "land", 5: "sea", 6: "land"}
        labels = np.array([[1, 1, 6], [3, 6, 6], [6, 6, 5]])
        with patch.object(mon, "script_literal_provinces", return_value=(frozenset({1, 2, 3}), frozenset({3}))):
            issues = mon.literal_issues(mon.ROOT, scope, labels, kinds)
            self.assertEqual(issues, ["literal province 2: its id left the map", "literal province 3: its naval base lost the sea"])
            labels[2, 1] = 3
            labels[1, 1] = 3
            self.assertEqual(mon.literal_issues(mon.ROOT, scope, labels, kinds), ["literal province 2: its id left the map"])

    def test_the_literal_list_reads_the_battle_orders_ports_and_hubs(self) -> None:
        literals, naval = mon.script_literal_provinces(mon.ROOT, [75, 200])
        self.assertLessEqual(mon.SCRIPT_LITERAL_PROVINCES | mon.NAVAL_LITERAL_PROVINCES, literals)
        self.assertLessEqual(mon.NAVAL_LITERAL_PROVINCES, naval)
        self.assertIn(16622, literals)
        self.assertLessEqual(mon.supply_hubs(mon.ROOT), literals)
        self.assertLessEqual(mon.unit_locations(mon.ROOT), literals)
        self.assertIn(4443, naval)
        self.assertTrue(naval <= literals)

    @staticmethod
    def rail_scope() -> mon.Scope:
        planned = {20: {"province": 20, "parent": 10, "state": 1, "kind": "part"}}
        return mon.Scope([1], {10: 1, 20: 1}, frozenset({10}), planned, {}, frozenset(), {}, parts={20: 10})

    def test_the_rail_repair_passes_a_broken_line_through_the_new_part(self) -> None:
        adjacency = {9: {10}, 10: {9, 20}, 20: {10, 11}, 11: {20}, 5: {6}, 6: {5}}
        original = b"1 3 9 10 11 \r\n1 2 5 6 \r\n2 3 11 10 9\r\n"
        repair = mon.repair_railways(original, adjacency, self.rail_scope(), frozenset({(11, 10, 9)}))
        self.assertEqual(repair.text, b"1 4 9 10 20 11 \r\n1 2 5 6 \r\n2 3 11 10 9\r\n")
        self.assertEqual(repair.repairs, [{"line": [9, 10, 11], "repaired": [9, 10, 20, 11], "detours": [{"segment": [10, 11], "via": [20]}]}])
        self.assertEqual(repair.managed, [{"line": [11, 10, 9], "detours": [{"segment": [11, 10], "via": [20]}]}])
        self.assertEqual(repair.issues, [])
        for line in repair.text.decode("utf-8").splitlines():
            fields = line.split()
            self.assertEqual(int(fields[1]), len(fields) - 2)
            self.assertEqual(len(set(fields[2:])), len(fields) - 2)

    def test_the_rail_repair_never_visits_a_province_twice(self) -> None:
        adjacency = {10: {20}, 20: {10, 11}, 11: {20}}
        original = b"1 3 20 10 11 \r\n"
        repair = mon.repair_railways(original, adjacency, self.rail_scope(), frozenset())
        self.assertEqual(repair.text, original)
        self.assertEqual(len(repair.issues), 1)
        self.assertIn("split a spur", repair.issues[0])

    def test_an_intact_railway_file_keeps_its_bytes(self) -> None:
        original = (mon.ROOT / mon.RAILWAYS).read_bytes()
        repair = mon.repair_railways(original, {}, mon.Scope([], {}, frozenset(), {}, {}, frozenset(), {}), frozenset())
        self.assertIs(repair.text, original)

    def test_the_planner_refuses_a_plan_that_breaks_the_border_margin(self) -> None:
        self.assertIsNone(mon.border_margin_issue(mon.BORDER_BUDGET - mon.BORDER_MARGIN))
        self.assertIn("less than", mon.border_margin_issue(mon.BORDER_BUDGET - mon.BORDER_MARGIN + 1))
        planner = mon.StagePlanner.__new__(mon.StagePlanner)
        planner.labels = np.array([[1, 2], [3, 4]], np.int32)
        planner.sea = np.zeros((2, 2), bool)
        planner.entries = []
        planner.grid = planner.labels.copy()
        planner.window = mon.Window(0, 2, 0, 2)
        planner.used = set()
        with patch.object(mon, "province_border_count", return_value=mon.BORDER_BUDGET - mon.BORDER_MARGIN + 1):
            with self.assertRaisesRegex(RuntimeError, "the plan is refused"):
                planner.finish([])

    def test_plans_and_dry_runs_stay_outside_the_repository(self) -> None:
        for directory in (mon.ROOT, mon.ROOT / "docs/development/previews/MON_dry_run"):
            with self.assertRaisesRegex(RuntimeError, "outside the repository"):
                mon.outside_repository(directory)
            with self.assertRaisesRegex(RuntimeError, "outside the repository"):
                mon.dry_run(directory)
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaisesRegex(RuntimeError, "no plan"):
                mon.dry_run(Path(temp))

    def test_the_dry_run_copies_plain_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp)
            with patch.object(mon, "DRY_RUN_INPUTS", (mon.RAILWAYS, mon.STATE_NAMES)):
                mon.copy_inputs(target)
            copied = target / mon.RAILWAYS
            self.assertFalse(copied.is_symlink())
            self.assertEqual(copied.read_bytes(), (mon.ROOT / mon.RAILWAYS).read_bytes())
            self.assertTrue(any((target / "history/states").glob("*.txt")))


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
            self.assertNotIn(entry["province"], [province for province in self.scope.planned if province < STAGE2_FIRST_ID])
            recorded.setdefault(str(entry["state"]), []).append(entry["province"])
        self.assertEqual(recorded, planned["villages"])

    def test_the_scope_is_a_set_of_state_ids(self) -> None:
        regions = {tag: region["states"] for tag, region in self.data["regions"].items() if mon.region_stage(region) == 2}
        self.assertEqual(regions, NEIGHBOUR_STATES)
        states = [state_id for states in mon.region_states(self.data).values() for state_id in states]
        self.assertEqual(len(states), len(set(states)))
        self.assertEqual(self.data["canyons"][0]["far_states"], NEIGHBOUR_STATES["RIN"])
        self.assertNotIn("owner", json.dumps(self.data["regions"]))
        self.assertTrue(all(region["capital_state"] in region["states"] for region in self.data["regions"].values()))

    def test_the_scope_stays_clear_of_other_geography_builders(self) -> None:
        provinces = self.scope.provinces
        self.assertFalse(provinces & mon.scoped_provinces())
        owned = (
            coastal.RELIEF_SURFACE_PROVINCES
            | coastal.CITIES
            | coastal.URBAN_GROWTH
            | coastal.ARCHIPELAGO_PROVINCES
            | coastal.HAND_PAINTED_PROVINCES
        )
        # A later region may hold coastal-owned provinces; it keeps their geometry and ground.
        kept = {int(province) for region in self.data["regions"].values() for province in region.get("keep_provinces", [])}
        self.assertFalse((provinces & frozenset(owned)) - kept)
        # The coastal builder repairs single pixels of a few scope provinces; those are never carved or split.
        repaired = provinces & frozenset(coastal.PROVINCE_REPAIR_PROVINCES)
        parents = {entry["parent"] for entry in mon.planned_entries(self.data)}
        self.assertFalse(repaired & parents)
        # An adopted city keeps its geometry, so a repaired province may be adopted.
        towns = {mon.settlement_province(entry) for _tag, entry in mon.all_settlements(self.data) if entry["kind"] != "adopt"}
        self.assertFalse(repaired & towns)
        southern = json.loads((mon.ROOT / "tools/data/adiscord_southern_cities.json").read_text(encoding="utf-8"))
        self.assertFalse(set(self.scope.states) & {int(state) for state in re.findall(r'"state"\s*:\s*(\d+)', json.dumps(southern))})

    def test_neighbour_settlements_follow_the_country_scale(self) -> None:
        vp_states = existing_victory_points()
        for tag, region in self.data["regions"].items():
            if mon.region_stage(region) != 2:
                continue
            entries = region["settlements"]
            for state_id in region["states"]:
                kinds = Counter(entry["kind"] for entry in entries if entry["state"] == state_id)
                expected = {"city": 1, "town": 1}
                if state_id == region["capital_state"]:
                    expected["district"] = 1
                self.assertEqual(dict(kinds), expected, (tag, state_id))
            for entry in entries:
                if entry["kind"] == "city" and entry["state"] == region["capital_state"]:
                    self.assertEqual(entry["value"], CAPITAL_VP[tag], entry["name"])
                elif entry["kind"] == "city":
                    self.assertTrue(3 <= entry["value"] <= 5, entry["name"])
                elif entry["kind"] == "town":
                    self.assertTrue(1 <= entry["value"] <= 2, entry["name"])
                if entry["kind"] == "city" and entry["state"] in vp_states:
                    self.assertEqual(entry["parent"], vp_states[entry["state"]], entry["name"])

    def test_later_states_hold_one_city_and_one_town(self) -> None:
        """Stage 3 states adopt or carve one city and carve one town where their land allows it.

        A state split in two keeps that pair between its halves. Each half
        holds a settlement, or its centre counts as one (spec 13.5).
        """
        centres = {child: split["centre"] for child, split in STATE_SPLITS.items()}
        children = {split["parent"]: child for child, split in STATE_SPLITS.items()}
        for tag, region in self.data["regions"].items():
            if mon.region_stage(region) < 3:
                continue
            for state_id in region["states"]:
                if state_id in centres:
                    continue
                family = {state_id, children[state_id]} if state_id in children else {state_id}
                kinds = Counter(entry["kind"] for entry in region["settlements"] if entry["state"] in family)
                self.assertEqual(kinds["city"] + kinds["adopt"], 0 if state_id in CITYLESS_STATES else 1, (tag, state_id))
                self.assertEqual(kinds["town"], 0 if state_id in TOWNLESS_STATES else 1, (tag, state_id))
                self.assertEqual(kinds["district"], int(state_id == region["capital_state"] and kinds["city"] == 1), (tag, state_id))
                if state_id in children:
                    for member in (state_id, children[state_id]):
                        own = [
                            entry
                            for entry in region["settlements"]
                            if entry["state"] == member and entry["kind"] in ("city", "adopt", "town")
                        ]
                        centre = centres.get(member)
                        self.assertTrue(own or (centre is not None and self.scope.state_of.get(centre) == member), (tag, member))
            for entry in region["settlements"]:
                if entry["kind"] == "city":
                    self.assertTrue(3 <= entry["value"] <= 5, entry["name"])
                elif entry["kind"] == "town":
                    self.assertTrue(1 <= entry["value"] <= 2, entry["name"])

    def test_later_theatre_settlements_keep_the_package_totals(self) -> None:
        """A new theatre city or town takes its points from the other VPs of its package."""
        authored = theatre.AUTHORED_THEATRE_VICTORY_POINTS
        values = {province: value for points in authored.values() for province, value in points}
        state_of_vp = {province: state_id for state_id, points in authored.items() for province, _value in points}
        package_of = {state_id: package for package, states in theatre.VORKERLAND_THEATRE_PACKAGES.items() for state_id in states}
        added: Counter = Counter()
        moved: Counter = Counter()
        for region in self.data["regions"].values():
            if mon.region_stage(region) < 3:
                continue
            for entry in region["settlements"]:
                if entry["kind"] in ("city", "town") and entry["state"] in package_of:
                    added[package_of[entry["state"]]] += entry["value"]
            for province, value in region.get("vp_overrides", {}).items():
                self.assertIn(int(province), values)
                self.assertGreaterEqual(value, 1)
                moved[package_of[state_of_vp[int(province)]]] += values[int(province)] - value
        self.assertEqual(+added, +moved)

    def test_large_montar_states_get_a_second_city(self) -> None:
        if not mon.has_stage2_plan(self.data):
            self.skipTest("no Stage 2 plan yet")
        counts = Counter(self.scope.state_of[province] for province in self.scope.provinces)
        expected = sorted(state_id for state_id in self.data["states"] if counts[state_id] > mon.SECOND_CITY_PROVINCES)
        second = self.data["stage2"]["settlements"]
        self.assertEqual(sorted(entry["state"] for entry in second), expected)
        for entry in second:
            self.assertTrue(2 <= entry["value"] <= 3, entry["name"])
            self.assertEqual(self.scope.state_of[entry["parent"]], entry["state"], entry["name"])

    def test_new_names_are_paired_unique_and_unused(self) -> None:
        values = localisation_values()
        stage1 = {entry["name"].lower() for entry in self.data["settlements"] if "name" in entry}
        seen = set()
        existing = existing_victory_points()
        later_states = [
            state_id for region in self.data["regions"].values() if mon.region_stage(region) > 2 for state_id in region["states"]
        ]
        later_points = mon.state_victory_points(mon.ROOT, later_states)
        for tag, entry in mon.all_settlements(self.data):
            if entry["kind"] == "district" or "name_en" not in entry:
                continue
            # A city carved round an existing VP keeps the name of that VP.
            parent = entry.get("parent")
            if entry["kind"] == "city" and parent is not None and (existing.get(entry["state"]) == parent or parent in later_points):
                self.assertIn(entry["name"].lower(), values, entry["name"])
                continue
            # Once integrated, a name is the victory-point name of its own province.
            own = f"VICTORY_POINTS_{mon.settlement_province(entry)}"
            for name in (entry["name"], entry["name_en"]):
                self.assertFalse(values.get(name.lower(), set()) - {own}, (tag, name))
                self.assertNotIn(name.lower(), seen, (tag, name))
                self.assertNotIn(name.lower(), stage1, (tag, name))
                seen.add(name.lower())
            self.assertRegex(entry["name_en"], r"^[A-Za-z' -]+$")
        for _tag, entry in mon.all_settlements(self.data):
            for key in ("name", "name_en"):
                self.assertFalse(set(entry.get(key, "")) & set("\u2013\u2014\u00ab\u00bb"), entry.get(key))

    def test_stage2_plan_continues_the_ids(self) -> None:
        if not mon.has_stage2_plan(self.data):
            self.skipTest("no Stage 2 plan yet")
        later = mon.stage2_plan(self.data)
        ids = [entry["province"] for entry in later["provinces"]]
        self.assertEqual(later["first_id"], STAGE2_FIRST_ID)
        self.assertEqual(ids, list(range(later["first_id"], later["first_id"] + len(ids))))
        self.assertEqual({entry["kind"] for entry in later["provinces"]}, {"remainder", "district", "part"})
        for entry in later["provinces"]:
            self.assertEqual(self.scope.state_of[entry["parent"]], entry["state"])
        towns = {entry["province"] for entry in self.data["settlements"] if entry["kind"] == "village"}
        cities = {entry["parent"] for entry in self.data["stage2"]["settlements"]}
        for region in self.data["regions"].values():
            if mon.region_stage(region) != 2:
                continue
            towns |= {entry["province"] for entry in region["settlements"] if entry["kind"] == "town"}
            cities |= {entry["parent"] for entry in region["settlements"] if entry["kind"] == "city"}
        self.assertEqual({int(town) for town in later["towns"]}, towns)
        self.assertEqual({int(city) for city in later["cities"]}, cities)

    def test_river_snapshot_holds_only_neighbour_pixels(self) -> None:
        if not mon.has_stage2_plan(self.data):
            self.skipTest("no Stage 2 plan yet")
        snapshot = self.data["stage2"]["existing_rivers"]
        mon_rows = self.data["existing_rivers"]
        for row, pixels in snapshot.items():
            mon_pixels = {x for x, _palette in mon_rows.get(row, [])}
            self.assertFalse({x for x, _palette in pixels} & mon_pixels, row)


class StageSmoothingTests(unittest.TestCase):
    """The state-line smoothing of the latest stage: its inputs, its raster layer and the stored plan."""

    def test_history_states_follow_the_state_files(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            states = Path(directory) / "history/states"
            states.mkdir(parents=True)
            (states / "71-Parent.txt").write_text("state={\n\tid=71\n\tprovinces={\n\t\t10 11\n\t}\n}\n", encoding="utf-8")
            (states / "734-Child.txt").write_text("state={\n\tid=734\n\tprovinces={ 12 }\n}\n", encoding="utf-8")
            self.assertEqual(mon.history_states(Path(directory)), {10: 71, 11: 71, 12: 734})

    def test_moves_widen_the_layer_of_the_latest_stage(self) -> None:
        sheet = np.zeros((5, 4, 4), np.uint8)
        sheet[:2] = 9
        sheet[2:, :2] = (1, 2, 3, 255)
        record = {"sheet_row": 2, "origin": [10, 10]}
        origin, result = mon.widen_stage_layer(sheet, record, {(8, 11): (7, 7, 7)})
        self.assertEqual(origin, [8, 10])
        np.testing.assert_array_equal(result[:2, :4], sheet[:2])
        self.assertEqual(tuple(result[2 + 1, 0]), (7, 7, 7, 255))
        np.testing.assert_array_equal(result[2:5, 2:4], sheet[2:5, 0:2])

    def test_smoothed_pixels_may_change_state_and_no_others(self) -> None:
        sheet = np.zeros((3, 4, 4), np.uint8)
        _origin, result = mon.widen_stage_layer(sheet, {"sheet_row": 1, "origin": [0, 0]}, {(1, 0): (5, 5, 5)}, mon.SMOOTHED_ALPHA)
        self.assertEqual(int(result[1, 1, 3]), mon.SMOOTHED_ALPHA)
        scope = mon.Scope([1, 2], {10: 1, 20: 2}, frozenset({10, 20}), {}, {}, frozenset(), {})
        before = np.array([[10, 10, 20, 20]])
        after = np.array([[10, 10, 10, 20]])
        smoothed = np.array([[False, False, True, False]])
        self.assertEqual(len(mon.state_area_issues(scope, before, after)), 2)
        self.assertEqual(mon.state_area_issues(scope, before, after, smoothed), [])
        self.assertEqual(mon.state_area_issues(scope, after, after, smoothed), [])

    def test_limits_follow_the_carve_checks(self) -> None:
        planned = {
            20: {"province": 20, "parent": 5, "state": 71, "kind": "remainder"},
            21: {"province": 21, "parent": 6, "state": 71, "kind": "part"},
            22: {"province": 22, "parent": 6, "state": 71, "kind": "part"},
        }
        scope = mon.Scope([71], {5: 71, 6: 71, 20: 71, 21: 71, 22: 71}, frozenset({5, 6}), planned, {}, frozenset(), {5: 20})
        scope.parts.update({21: 6, 22: 6})
        data = {
            "states": [],
            "regions": {"PWR": {"states": [71], "stage": 3, "part_min_pixels": 70, "split_part": 100, "split_threshold": 180}},
            "planned": {"provinces": []},
            "stages": [{"stage": 3, "irregular_parts": [22]}],
        }
        limits = mon.smoothing_limits(scope, data)
        self.assertEqual(limits.sizes, {20: mon.REMAINDER_MIN_PIXELS, 21: 70, 6: 70, 22: 70})
        self.assertEqual(limits.shapes, {21: mon.PART_MIN_ROUNDNESS, 6: mon.PART_MIN_ROUNDNESS})
        # The family of 6 keeps two to four parts' worth of land; other rural provinces stay below the split threshold.
        self.assertEqual(limits.group_of, {6: 6, 21: 6, 22: 6})
        self.assertEqual(limits.areas, {6: (201, 400), 5: (0, 180), 20: (0, 180)})

    def test_the_latest_stage_smooths_without_losing_contracts(self) -> None:
        data, sheet, report, _arrays = mon.smooth_stage_plan(mon.ROOT)
        self.assertTrue(report["stable"])
        self.assertEqual(report["rail_segments_lost"], [])
        self.assertGreaterEqual(report["border_margin"], mon.BORDER_MARGIN)
        self.assertEqual(report["frozen_states"], list(range(32, 41)))
        self.assertFalse(set(report["smoothed_states"]) & set(report["frozen_states"]))
        self.assertEqual(report["interior_river_pixels_after"], report["interior_river_pixels_before"])
        stored = mon.read_json(mon.ROOT)
        record = mon.stage_layers(stored)[report["stage"]]
        changed = {key for key in record if mon.stage_layers(data)[report["stage"]][key] != record[key]}
        self.assertLessEqual(changed, {"origin"})
        split = int(record["sheet_row"])
        with Image.open(mon.ROOT / mon.GEOMETRY_PATH) as source:
            stored_sheet = np.asarray(source.convert("RGBA"))
        np.testing.assert_array_equal(sheet[:split, : stored_sheet.shape[1]], stored_sheet[:split])


@unittest.skipUnless(mon.has_stage2_plan(mon.read_json(mon.ROOT)), "no Stage 2 plan yet")
class PlannedGeometryTests(unittest.TestCase):
    """The stamped Stage 2 geometry: splits, sizes, shapes and the border budget."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.data = mon.active_data(mon.read_json(mon.ROOT))
        cls.scope = mon.load_scope(mon.ROOT, cls.data)
        definition = mon.read_definition(mon.ROOT)
        mon.register_planned_rows(definition, cls.data)
        cls.definition = definition
        rgb = mon.stamp_geometry(mon.ROOT, current(mon.PROVINCES, "RGB"), cls.data, definition.colours(), cls.scope)
        cls.grid = mon.province_grid(rgb, definition.colours())
        cls.sizes = np.bincount(cls.grid.ravel())
        sea = np.isin(cls.grid, [province for province, row in definition.rows.items() if row[4] == "sea"])
        cls.coastal = set(np.unique(cls.grid[mon.neighbours_of(sea) & ~sea]).tolist())

    def test_the_border_count_keeps_its_margin(self) -> None:
        borders = mon.province_border_count(self.grid)
        self.assertLessEqual(borders, mon.BORDER_BUDGET - mon.BORDER_MARGIN)

    def test_large_rural_provinces_are_split_into_round_parts(self) -> None:
        irregular = {province for record in mon.later_layers(self.data) for province in record.get("irregular_parts", [])}
        split_part = mon.state_parameter(self.data, "split_part", mon.SPLIT_PART_PIXELS)
        part_minimum = mon.state_parameter(self.data, "part_min_pixels", mon.PART_MIN_PIXELS)
        children = {}
        for part, parent in self.scope.parts.items():
            children.setdefault(parent, [parent]).append(part)
        for parent, ids in children.items():
            area = int(sum(self.sizes[province] for province in ids))
            expected = ceil(area / split_part[self.scope.state_of[parent]])
            self.assertIn(len(ids), (expected, expected - 1), parent)
            for province in ids:
                self.assertEqual(self.scope.state_of[province], self.scope.state_of[parent])
                mask = self.grid == province
                self.assertEqual(label(mask)[1], 1, province)
                self.assertGreaterEqual(int(mask.sum()), part_minimum[self.scope.state_of[province]], province)
                if province not in irregular:
                    self.assertGreaterEqual(mon.roundness(mask), mon.PART_MIN_ROUNDNESS, province)
        self.assertLess(len(irregular), 0.05 * len(self.scope.parts))

    def test_no_large_rural_province_stays_whole(self) -> None:
        kinds = self.definition.kinds()
        threshold = mon.state_parameter(self.data, "split_threshold", mon.SPLIT_THRESHOLD)
        kept = set(coastal.PROVINCE_REPAIR_PROVINCES) | set(self.scope.adopted)
        for region in self.data["regions"].values():
            kept |= {int(province) for key in ("never_parent", "keep_provinces") for province in region.get(key, [])}
            kept |= {province for province, state_id in self.scope.state_of.items() if state_id in region.get("no_split_states", [])}
        for province in self.scope.provinces:
            if kinds.get(province) != "land" or province in self.scope.urban or province in self.coastal:
                continue
            if province in kept or self.definition.rows[province][6] in mon.CITY_TERRAINS:
                continue
            self.assertLessEqual(int(self.sizes[province]), threshold[self.scope.state_of[province]], province)

    def test_settlement_sizes(self) -> None:
        for city in self.scope.cities:
            self.assertTrue(mon.CITY_SIZE[0] <= self.sizes[city] <= mon.CITY_SIZE[1], city)
        for town in self.scope.towns:
            self.assertTrue(mon.TOWN_SIZE[0] <= self.sizes[town] <= mon.TOWN_SIZE[1], town)

    def test_new_rows_carry_the_coastal_flag_of_their_shore(self) -> None:
        for entry in mon.later_entries(self.data):
            province = entry["province"]
            self.assertEqual(bool(entry.get("coastal")), province in self.coastal, province)
            parent = entry["parent"]
            self.assertEqual(self.definition.rows[parent][5] == "true", parent in self.coastal, parent)


class PlanTests(unittest.TestCase):
    """Properties of the computed outputs; they hold before and after the apply."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.plan = mon.build_plan(mon.ROOT)
        cls.data = mon.active_data(mon.read_json(mon.ROOT))
        cls.view = mon.geography_view(cls.data)
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
        cls.window = window
        ground = mon.prepare_ground(
            mon.ROOT, cls.view, cls.scope, cls.grid, cls.kinds, current(mon.HEIGHTMAP)[window.s], window
        )
        cls.relief_scope = np.zeros(cls.grid.shape, bool)
        cls.relief_scope[window.s] = ground.relief_scope
        cls.frozen = np.zeros(cls.grid.shape, bool)
        cls.frozen[window.s] = ground.frozen
        held, _cities = mon.held_pixels(
            cls.view, cls.scope, definition, ground.labels, ground.mon, ground.states, ground.frozen
        )
        cls.held = np.zeros(cls.grid.shape, bool)
        cls.held[window.s] = held
        cls.rivers = decode(cls.plan.outputs[mon.RIVERS])
        cls.water = np.isin(cls.grid, [province for province, kind in cls.kinds.items() if kind != "land"])
        cls.declared = {
            int(line.split(";")[0]): line.split(";")[6]
            for line in cls.plan.outputs[mon.DEFINITION].decode("utf-8-sig").splitlines()
        }

    def test_only_the_scope_changes(self) -> None:
        for path in (mon.TERRAIN, mon.CITIES):
            changed = current(path) != decode(self.plan.outputs[path])
            self.assertFalse((changed & ~self.mon).any(), path)
            self.assertFalse((changed & self.held).any(), path)
        # A frozen pixel of a rural province keeps its heights and takes only the terrain its province declares.
        terrain = decode(self.plan.outputs[mon.TERRAIN])
        changed = (current(mon.TERRAIN) != terrain) & self.frozen
        shown = mon.palette_types()
        for y, x in zip(*np.nonzero(changed)):
            declared = self.declared[int(self.grid[y, x])]
            if declared != "urban":
                self.assertEqual(shown[int(terrain[y, x])], declared, (int(x), int(y)))
        before = current(mon.RIVERS)
        after = self.rivers
        outside = (before != after) & ~self.mon
        reach, issues = mon.owned_reach_mask(
            self.data, self.window, after[self.window.s], self.grid[self.window.s].astype(np.int64), self.water[self.window.s]
        )
        self.assertEqual(issues, [])
        owned = np.zeros(self.grid.shape, bool)
        owned[self.window.s] = reach
        # Outside the scope an owned reach only widens, closes its diagonal
        # steps, applies its authored pixel edits, takes over the flow-in
        # marker on its course, gives the river it meets a flow-in pixel
        # beside it and turns that river's source pixel into plain width.
        widened = owned & ((after >= before) | (before >= mon.RIVER_SEA_PALETTE))
        for reach in self.data["owned_reaches"]:
            for x, y in reach.get("drop", []):
                widened[y, x] = after[y, x] == mon.RIVER_LAND_PALETTE
        flow_in = (after == mon.RIVER_FLOW_IN_PALETTE) & mon.neighbours_of(owned) & (before < mon.RIVER_SEA_PALETTE)
        sourceless = (before == mon.RIVER_SOURCE_PALETTE) & (after >= mon.WIDTH_STEPS[0]) & (after < mon.RIVER_SEA_PALETTE)
        # A course on the state line may turn on a foreign pixel beside the scope.
        ring = np.zeros(self.grid.shape, bool)
        ring[self.window.s] = mon.corner_takers(
            self.grid[self.window.s], self.mon[self.window.s], self.water[self.window.s], self.window
        )
        self.assertFalse((outside & ~(widened | flow_in | sourceless | ring)).any())
        heights = current(mon.HEIGHTMAP) != decode(self.plan.outputs[mon.HEIGHTMAP])
        self.assertFalse((heights & ~self.relief_scope).any())
        self.assertFalse((heights & self.frozen).any())
        self.assertFalse((self.relief_scope & ~self.mon & self.water).any())
        changed_provinces = (current(mon.PROVINCES) != self.rgb).any(axis=2)
        self.assertTrue(set(np.unique(self.before[changed_provinces]).tolist()) <= self.scope.provinces)

    def test_frozen_band_keeps_the_ivn_geography_inputs(self) -> None:
        trees = current(mon.TREES) != decode(self.plan.outputs[mon.TREES])
        cells = mon.tree_cells_touching(self.held, mon.Window(0, self.grid.shape[0], 0, self.grid.shape[1]), self.grid.shape, trees.shape)
        self.assertFalse((trees & cells).any())
        ivn = np.isin(self.grid, list(mon.scoped_provinces()))
        distance = distance_transform_edt(~ivn)
        self.assertFalse((self.relief_scope & (distance <= mon.IVN_CLEARANCE)).any())

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
            self.assertEqual(int(np.isin(self.before, members).sum()), int(np.isin(self.grid, members).sum()), state_id)
        for path in (mon.DEFINITION, mon.UNITSTACKS):
            original = (mon.ROOT / path).read_bytes()
            output = self.plan.outputs[path]
            if b"\r\n" in original:
                self.assertEqual(output.count(b"\n"), output.count(b"\r\n"), path)
            else:
                self.assertNotIn(b"\r\n", output, path)
        old_rows = (mon.ROOT / mon.DEFINITION).read_bytes().decode("utf-8-sig").splitlines()
        new_rows = self.plan.outputs[mon.DEFINITION].decode("utf-8-sig").splitlines()
        # A parent that lost its shore to its remainder takes the coastal flag of its geometry.
        parents = {int(entry["parent"]) for entry in mon.later_entries(self.data)}
        for before, after in zip(old_rows, new_rows):
            if before != after:
                province = int(before.split(";")[0])
                self.assertIn(province, self.scope.provinces)
                kept = 5 if province in parents else 6
                self.assertEqual(before.split(";")[:kept] + before.split(";")[7:], after.split(";")[:kept] + after.split(";")[7:])

    def test_cities_and_towns_are_compact_urban_junctions_without_rivers(self) -> None:
        cities_bmp = decode(self.plan.outputs[mon.CITIES])
        terrain = decode(self.plan.outputs[mon.TERRAIN])
        shore = mon.urban_blocked(self.water)
        adjacency = mon.province_adjacency(self.grid[self.window.s])
        river = self.rivers < mon.RIVER_SEA_PALETTE
        settlements = [(city, mon.CITY_SIZE, 3) for city in [*self.scope.cities, *self.scope.districts]]
        settlements += [(town, mon.TOWN_SIZE, mon.TOWN_MIN_NEIGHBOURS) for town in self.scope.towns]
        for province, (low, high), neighbours in settlements:
            mask = self.grid == province
            self.assertTrue(low <= mask.sum() <= high, province)
            self.assertEqual(label(mask)[1], 1, province)
            land = {other for other in adjacency[province] if self.kinds.get(other) == "land"}
            self.assertGreaterEqual(len(land), neighbours, province)
            self.assertFalse((mask & river).any(), province)
            self.assertEqual(self.declared[province], "urban")
            houses = mask & ~shore & (terrain == mon.URBAN_PALETTE)
            self.assertTrue(houses.any(), province)
            self.assertTrue(np.isin(cities_bmp[houses], [mon.CITY_HOUSES_INDEX, mon.SMALL_CITY_INDEX]).all(), province)
        for parent, remainder in self.scope.remainders.items():
            self.assertNotEqual(self.declared[remainder], "urban")
            if remainder not in self.scope.parts.values():
                minimum = mon.TOWN_REMAINDER_MIN_PIXELS if parent in self.scope.towns else mon.REMAINDER_MIN_PIXELS
                self.assertGreaterEqual((self.grid == remainder).sum(), minimum, remainder)

    def test_settlement_houses_cover_their_provinces(self) -> None:
        """Houses cover at least 75 % of an urban province off the shore, with a frayed edge, and stay inside it."""
        cities_bmp = decode(self.plan.outputs[mon.CITIES])
        terrain = decode(self.plan.outputs[mon.TERRAIN])
        shore = mon.urban_blocked(self.water)
        urban = np.isin(self.grid, sorted(self.scope.urban))
        values = mon.settlement_values(self.data)
        shares = []
        for province in sorted(self.scope.urban):
            inland = (self.grid == province) & ~self.held & ~shore
            if not inland.any():
                continue
            built = inland & (terrain == mon.URBAN_PALETTE)
            shares.append(built.sum() / inland.sum())
            self.assertGreaterEqual(shares[-1], 0.75, province)
            large = province in self.scope.districts or (
                province not in self.scope.towns and values.get(province, 1) >= mon.LARGE_CITY_VALUE
            )
            expected = mon.CITY_HOUSES_INDEX if large else mon.SMALL_CITY_INDEX
            self.assertTrue((cities_bmp[built] == expected).all(), province)
            self.assertTrue((cities_bmp[inland & ~built] == mon.CITY_BACKGROUND_INDEX).all(), province)
        # The outlines stay frayed: most urban provinces keep some open ground.
        self.assertGreater(sum(share < 1 for share in shares), len(shares) // 2)
        # No houses or urban ground in the rural provinces this pass paints.
        rural = self.mon & ~urban & ~self.held & ~self.frozen
        self.assertFalse((rural & (terrain == mon.URBAN_PALETTE)).any())
        self.assertFalse((rural & (cities_bmp == mon.CITY_HOUSES_INDEX)).any())

    def test_forest_provinces_are_wooded_throughout(self) -> None:
        """Forest provinces show the forest palette off the shore; every tree cell wholly on their forest is wooded."""
        terrain = decode(self.plan.outputs[mon.TERRAIN])
        trees = decode(self.plan.outputs[mon.TREES])
        shore = mon.urban_blocked(self.water)
        forest_palettes = [index for index, kind in mon.palette_types().items() if kind == "forest"]
        forest_ids = sorted(province for province in self.scope.provinces if self.declared[province] == "forest")
        painted = self.mon & ~self.held
        for province in forest_ids:
            inland = (self.grid == province) & painted & ~shore
            if inland.any():
                self.assertGreaterEqual(np.isin(terrain[inland], forest_palettes).mean(), 0.95, province)
        forest = np.isin(self.grid, forest_ids) & painted & np.isin(terrain, forest_palettes)
        cells = wholly_covered_cells(forest, trees.shape)
        cells &= ~mon.tree_cells_blocked(self.water, trees.shape[1], trees.shape[0])
        # Kept ground keeps its trees, and the cells round a town stay bare.
        whole = mon.Window(0, self.grid.shape[0], 0, self.grid.shape[1])
        towns = np.isin(self.grid, sorted(self.scope.urban))
        cells &= ~mon.tree_cells_touching(self.held | towns, whole, self.grid.shape, trees.shape)
        self.assertTrue(cells.any())
        self.assertTrue((trees[cells] > 0).all())

    def test_settlements_stand_on_their_planned_provinces(self) -> None:
        self.assertEqual([issue for issue in self.plan.issues if "planned province" in issue or "is not urban" in issue], [])
        for _tag, entry in mon.all_settlements(self.data):
            # Districts have no settlement province; adopted cities keep their own province as it is.
            if entry["kind"] in ("district", "adopt"):
                continue
            province = mon.settlement_province(entry)
            self.assertEqual(self.scope.state_of[province], entry["state"], entry["name"])
            self.assertEqual(self.declared[province], "urban", entry["name"])

    def test_rivers_run_on_borders_and_cut_no_province(self) -> None:
        """Every river pixel of every region touches another province across an edge, and none cuts a province."""
        river = (self.rivers < mon.RIVER_SEA_PALETTE) & ~self.water
        borders = mon.province_borders(self.grid.astype(np.int64))
        inside = {(int(x), int(y)) for y, x in zip(*np.nonzero(river & self.mon & ~borders))}
        coastal_courses = set(coastal.RIVER_COURSES)
        self.assertEqual(inside - coastal_courses, set(IVN_EDGE_TURNS))
        for x, y in IVN_EDGE_TURNS:
            near = {int(self.grid[y + dy, x + dx]) for dy in (-1, 1) for dx in (-1, 1)} - self.scope.provinces
            self.assertTrue(near & mon.scoped_provinces(), (x, y))
        self.assertEqual([issue for issue in self.plan.issues if "river" in issue and "railway" not in issue], [])
        labels = self.grid[self.window.s]
        turns = mon.ivn_edge_turns(labels, self.mon[self.window.s])
        inside_turns = turns & river[self.window.s] & ~borders[self.window.s]
        found = {(int(x) + self.window.x0, int(y) + self.window.y0) for y, x in zip(*np.nonzero(inside_turns))}
        self.assertEqual(found, set(IVN_EDGE_TURNS))
        labels = self.grid[self.window.s].astype(np.int64)
        nothing = np.zeros(labels.shape, bool)
        split = mon.rivers_splitting_provinces(labels, river[self.window.s], self.mon[self.window.s], nothing)
        self.assertEqual(split, [])

    def test_unit_anchors_stand_in_their_own_provinces(self) -> None:
        height = self.grid.shape[0]
        outside = []
        for line in self.plan.outputs[mon.UNITSTACKS].decode("utf-8").splitlines():
            row = line.split(";")
            province = int(row[0])
            if province not in self.scope.provinces or province in COASTAL_ANCHOR_PROVINCES:
                continue
            x = round(float(row[2]))
            y = height - 1 - round(float(row[4]))
            found = int(self.grid[y, x])
            if found == province:
                continue
            # A moving or attacking slot towards a sea neighbour stands on that sea.
            toward_sea = (
                int(row[1]) in SEAWARD_SLOTS
                and self.kinds.get(found) != "land"
                and (mon.neighbours_of(self.grid == province) & (self.grid == found)).any()
            )
            if not toward_sea:
                outside.append((province, int(row[1])))
        self.assertEqual(outside, [])
        slots = Counter(int(line.split(";")[0]) for line in self.plan.outputs[mon.UNITSTACKS].decode("utf-8").splitlines())
        for province in self.scope.provinces:
            if self.kinds.get(province) == "land":
                self.assertGreaterEqual(slots[province], 5, province)

    def test_declared_terrain_meets_the_bands_and_the_state_names(self) -> None:
        words = ("provinces lie outside", "unexpected declared terrain", "forbidden terrain")
        self.assertEqual([issue for issue in self.plan.issues if any(word in issue for word in words) or issue.startswith("state ")], [])
        self.assertEqual(set(self.plan.report["region_terrain"]), set(self.data["regions"]))
        for tag, report in self.plan.report["region_terrain"].items():
            bands = self.data["regions"][tag]["terrain_bands"]
            for terrain, count in report["totals"].items():
                self.assertTrue(bands[terrain][0] <= count <= bands[terrain][1], (tag, terrain, count))
            # Adopted cities and kept city terrains count in no band.
            original = [p for p in self.scope.original if self.scope.region_of[self.scope.state_of[p]] == tag]
            self.assertEqual(sum(report["totals"].values()) + report["unbanded"], len(original))
        # Every region keeps the height range it authors; MON keeps its own.
        window = self.window
        states = mon.lookup_raster(self.grid[window.s].astype(np.int32), self.scope.state_of)
        floor, ceiling = (np.broadcast_to(limit, states.shape) for limit in mon.height_limits(self.data, states))
        inside = (self.mon & self.relief_scope)[window.s]
        heights = decode(self.plan.outputs[mon.HEIGHTMAP])[window.s]
        self.assertTrue((heights[inside] >= floor[inside]).all())
        self.assertTrue((heights[inside] <= ceiling[inside]).all())
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
        required = {river["name"] for river in self.view["rivers"] if "river" in river["mouth"] and not river.get("optional")}
        self.assertLessEqual(required, set(confluences))
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
        river = self.rivers[self.mon & self.relief_scope]
        self.assertFalse(np.isin(river, (5, 8)).any())

    def test_junctions_keep_their_spacing(self) -> None:
        points = [tuple(join["flow_in"]) for join in self.plan.report["confluences"].values()]
        for index, (x, y) in enumerate(points):
            for ox, oy in points[index + 1:]:
                self.assertGreater(max(abs(x - ox), abs(y - oy)), mon.JUNCTION_GAP)

    def test_owned_reaches_carry_their_width_down_to_the_lake(self) -> None:
        reach, _issues = mon.owned_reach_mask(
            self.data, self.window, self.rivers[self.window.s], self.grid[self.window.s].astype(np.int64), self.water[self.window.s]
        )
        widths = self.rivers[self.window.s][reach]
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
        for river in self.view["rivers"]:
            path = self.plan.report["rivers"].get(river["name"])
            if path is None:
                self.assertTrue(river.get("optional"), river["name"])
                continue
            x, y = path["source"]
            is_source = int(self.rivers[y, x]) == mon.RIVER_SOURCE_PALETTE
            self.assertEqual(is_source, "lake" in river["mouth"], river["name"])
        visits, forks, _walks = mon.walk_courses(self.rivers, self.water)
        drawn = (self.rivers < mon.RIVER_SEA_PALETTE) & ~self.water & self.relief_scope
        self.assertTrue((visits[drawn] == 1).all())
        self.assertEqual([fork for fork in forks if self.relief_scope[fork[1], fork[0]]], [])

    def test_rivers_entering_a_canyon_descend_to_its_floor(self) -> None:
        self.assertEqual([issue for issue in self.plan.issues if "ravine" in issue or "gorge floor" in issue], [])
        ravines = self.plan.report["ravines"]
        self.assertIn("Valta", ravines)
        for name, ravine in ravines.items():
            profile = ravine["profile"]
            self.assertLessEqual(profile[-1], ravine["floor"] + mon.RAVINE_FLOOR_TOLERANCE, name)
            self.assertGreaterEqual(profile[0] - profile[-1], 8, name)

    def test_railway_segments_touch_or_pass_through_new_provinces(self) -> None:
        """A segment that loses contact names its detour; the theatre chains take it at integration."""
        for issue in self.plan.issues:
            if "railway" in issue:
                self.assertIn("pass it through [", issue)
        others = [issue for issue in self.plan.issues if "railway segment" not in issue]
        self.assertEqual(others, [])

    def test_literal_provinces_keep_their_ids_on_land_and_their_sea(self) -> None:
        """Every id script names stays on the map as land; a naval base keeps its sea contact."""
        self.assertEqual([issue for issue in self.plan.issues if issue.startswith("literal province")], [])
        literals, naval = mon.script_literal_provinces(mon.ROOT, self.scope.states)
        present = set(np.unique(self.grid).tolist())
        sea = np.isin(self.grid, [province for province, kind in self.kinds.items() if kind == "sea"])
        for province in sorted(literals & self.scope.provinces):
            self.assertIn(province, present)
            self.assertEqual(self.kinds[province], "land", province)
            if province in naval:
                self.assertTrue((mon.neighbours_of(sea) & (self.grid == province)).any(), province)

    def test_the_settlement_table_lists_every_settlement(self) -> None:
        table = mon.names_table(self.data)
        for _tag, entry in mon.all_settlements(self.data):
            if entry["kind"] not in ("district", "adopt"):
                self.assertIn(f"| {entry['name']} |", table)

    def test_fields_cover_rural_plains_of_the_field_regions_only(self) -> None:
        """Farmland stays on declared plains, off the city mask, houses and shore, within its share."""
        terrain = decode(self.plan.outputs[mon.TERRAIN])
        cities_bmp = decode(self.plan.outputs[mon.CITIES])
        painted = self.mon & ~self.held & ~self.frozen
        fields = painted & (terrain == mon.FIELD_PALETTE)
        self.assertTrue(fields.any())
        self.assertFalse(np.isin(cities_bmp[fields], list(mon.CITY_PALETTE_INDICES)).any())
        self.assertGreater(float(distance_transform_edt(~self.water)[fields].min()), FIELD_SHORE_PIXELS)
        field_states = set(mon.field_states(self.data))
        owners = self.grid[fields]
        for province in np.unique(owners).tolist():
            with self.subTest(province=province):
                self.assertEqual(self.declared[province], "plains")
                self.assertIn(self.scope.state_of[province], field_states)
                land = int(((self.grid == province) & ~self.water).sum())
                self.assertLessEqual(int((owners == province).sum()), FIELD_MAX_SHARE * land)
        pieces, _count = label(fields)
        self.assertGreaterEqual(int(np.bincount(pieces.ravel())[1:].min()), FIELD_MIN_PATCH)


def wholly_covered_cells(mask: np.ndarray, tree_shape: tuple[int, int]) -> np.ndarray:
    """Tree cells whose whole footprint, as the tree sampler reads it, lies in ``mask``."""
    tree_height, tree_width = tree_shape
    height, width = mask.shape
    rows = np.searchsorted((np.arange(tree_height) * height) // tree_height, np.arange(height), "right") - 1
    columns = np.searchsorted((np.arange(tree_width) * width) // tree_width, np.arange(width), "right") - 1
    cell = (rows[:, None] * tree_width + columns[None, :]).ravel()
    total = np.bincount(cell, minlength=tree_height * tree_width)
    inside = np.bincount(cell, weights=mask.ravel().astype(float), minlength=tree_height * tree_width)
    return (inside == total).reshape(tree_shape)


def stage2_applied() -> bool:
    data = mon.read_json(mon.ROOT)
    if not mon.has_stage2_plan(data):
        return False
    rows = (mon.ROOT / mon.DEFINITION).read_bytes().decode("utf-8-sig").splitlines()
    return any(row.startswith(f"{mon.stage2_plan(data)['first_id']};") for row in rows)


def applied() -> bool:
    planned = mon.read_json(mon.ROOT)["planned"]
    rows = (mon.ROOT / mon.DEFINITION).read_bytes().decode("utf-8-sig").splitlines()
    return bool(planned["provinces"]) and any(row.startswith(f"{planned['first_id']};") for row in rows)


@unittest.skipUnless(applied() and not stage2_applied(), "Stage 1 alone is not the current map")
class Stage1ReproductionTests(unittest.TestCase):
    def test_stage1_sections_reproduce_the_current_map(self) -> None:
        plan = mon.build_plan(mon.ROOT, mon.stage1_data(mon.read_json(mon.ROOT)))
        self.assertEqual(plan.issues, [])
        self.assertEqual(mon.stale_outputs(plan, mon.ROOT), [])


@unittest.skipUnless(stage2_applied(), "the Stage 2 geography has not been applied yet")
class AppliedMapTests(unittest.TestCase):
    def test_check_is_clean_after_the_apply(self) -> None:
        plan = mon.build_plan(mon.ROOT)
        self.assertEqual(mon.stale_outputs(plan, mon.ROOT), [])


def existing_victory_points() -> dict[int, int]:
    """The victory-point province of every neighbour state that holds one in its history file."""
    result = {}
    for states in NEIGHBOUR_STATES.values():
        for state_id in states:
            path = next((mon.ROOT / "history/states").glob(f"{state_id}-*.txt"))
            match = re.search(r"victory_points\s*=\s*\{\s*(\d+)", path.read_text(encoding="utf-8-sig"))
            if match:
                result[state_id] = int(match.group(1))
    return result


def localisation_values() -> dict[str, set[str]]:
    """Every localisation value with the keys that carry it."""
    values: dict[str, set[str]] = {}
    for path in (mon.ROOT / "localisation").rglob("*.yml"):
        for line in path.read_text(encoding="utf-8-sig", errors="replace").splitlines():
            match = re.match(r'\s*([^\s#][^:]*):\d*\s*"(.*)"\s*$', line)
            if match:
                values.setdefault(match.group(2).strip().lower(), set()).add(match.group(1).strip())
    return values


if __name__ == "__main__":
    unittest.main()
