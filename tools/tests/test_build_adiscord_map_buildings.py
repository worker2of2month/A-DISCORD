"""Map anchors obey native province and state ownership checks."""

from __future__ import annotations

import json
import tempfile
import unittest
from math import dist
from pathlib import Path
from struct import pack, unpack
from unittest import mock

from PIL import Image

from tools.builders import build_adiscord_map_buildings as builder


# Columns 0-1 are the first bank, column 2 the second and column 3 the inland dam.
FIXTURE_DAM_ANCHORS = {
    28: ("1.99", "10.00", "1.00", "0.00"),
    53: ("2.00", "10.00", "1.00", "0.00"),
    688: ("1.99", "10.00", "1.00", "0.00"),
    67: ("2.00", "10.00", "1.00", "0.00"),
}


class BorderDamTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        (self.root / "map").mkdir()
        (self.root / "history/states").mkdir(parents=True)
        for state, province in ((28, 145), (53, 70), (42, 16436)):
            (self.root / f"history/states/{state}.txt").write_text(
                f"state = {{ id = {state} provinces = {{ {province} }} "
                f"history = {{ buildings = {{ {province} = {{ dam = 1 }} }} }} }}",
                encoding="utf-8",
            )
        (self.root / "map/definition.csv").write_text(
            "145;255;0;0;land;false;plains;1\n"
            "70;0;255;0;land;false;plains;1\n"
            "16436;0;0;255;land;false;plains;1\n",
            encoding="utf-8",
        )
        provinces = Image.new("RGB", (4, 4), (255, 0, 0))
        for y in range(4):
            provinces.putpixel((2, y), (0, 255, 0))
            provinces.putpixel((3, y), (0, 0, 255))
        provinces.save(self.root / "map/provinces.bmp")
        Image.new("L", (4, 4), 100).save(self.root / "map/heightmap.bmp")
        self.lines = [
            "28;dam_spawn;1.00;10.00;1.00;0.00;0",
            "53;dam_spawn;2.00;10.00;1.00;0.00;0",
            "42;dam_spawn;2.00;10.00;1.00;0.00;0",
        ]
        self.write_buildings(self.lines)
        anchor = mock.patch.object(builder, "BORDER_DAM_ANCHORS", FIXTURE_DAM_ANCHORS)
        anchor.start()
        self.addCleanup(anchor.stop)

    def write_buildings(self, lines):
        (self.root / "map/buildings.txt").write_bytes("\r\n".join(lines).encode("utf-8"))

    def test_audit_rejects_a_shared_anchor_on_the_other_bank(self):
        shared = [
            "28;dam_spawn;1.86;10.00;1.00;0.00;0",
            "53;dam_spawn;1.86;10.00;1.00;0.00;0",
            "42;dam_spawn;2.00;10.00;1.00;0.00;0",
        ]
        self.write_buildings(shared)
        _lines, mismatches = builder.audit_buildings(self.root)
        self.assertEqual([(item.recorded_state, item.actual_state) for item in mismatches], [(53, 28), (42, 53)])

    def test_dam_plan_keeps_both_banks_and_moves_other_invalid_anchor(self):
        planned, changed = builder.dam_province_plan(self.root, self.lines)
        self.assertEqual(changed, [1, 3])
        self.assertEqual(planned[0], "28;dam_spawn;1.99;10.00;1.00;0.00;0")
        self.assertEqual(planned[1], "53;dam_spawn;2.00;10.00;1.00;0.00;0")
        self.assertEqual(planned[2], "42;dam_spawn;3.00;10.00;1.00;0.00;0")
        self.write_buildings(planned)
        self.assertEqual(builder.audit_buildings(self.root)[1], [])
        self.assertEqual(builder.dam_province_plan(self.root, planned), (planned, []))

    def test_synchronization_moves_dams_instead_of_transferring_their_states(self):
        builder.synchronize_buildings(self.root, apply=True)
        lines, mismatches = builder.audit_buildings(self.root)
        self.assertEqual(mismatches, [])
        self.assertEqual([line.split(";")[0] for line in lines], ["28", "53", "42"])
        before = (self.root / "map/buildings.txt").read_bytes()
        self.assertEqual(builder.synchronize_buildings(self.root, apply=True), [])
        self.assertEqual((self.root / "map/buildings.txt").read_bytes(), before)

    def test_scripted_dam_has_both_anchors_without_starting_buildings(self):
        for state, province in ((688, 145), (67, 70)):
            (self.root / f"history/states/{state}.txt").write_text(
                f"state = {{ id = {state} provinces = {{ {province} }} }}",
                encoding="utf-8",
            )
        with mock.patch.object(builder, "NAM_DAM_PROVINCES", {688: 145, 67: 70}):
            planned, changed = builder.dam_province_plan(self.root, self.lines)
            self.assertEqual(planned[-2:], [
                "688;dam_spawn;1.99;10.00;1.00;0.00;0",
                "67;dam_spawn;2.00;10.00;1.00;0.00;0",
            ])
            self.assertIn(4, changed)
            self.assertIn(5, changed)
            self.assertEqual(builder.dam_province_plan(self.root, planned), (planned, []))


CITY, DONOR, REMAINDER, FOREIGN = 19901, 19902, 19903, 19904
MON_COLOURS = {
    DONOR: (10, 0, 0),
    CITY: (20, 0, 0),
    REMAINDER: (30, 0, 0),
    FOREIGN: (40, 0, 0),
}


class MonProvinceAnchorTests(unittest.TestCase):
    """A carved city keeps the parent id; its remainder is a new province."""

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        for folder in ("map", "history/states", "tools/data"):
            (self.root / folder).mkdir(parents=True)
        self.write_state(469, (DONOR, CITY, REMAINDER))
        self.write_state(999, (FOREIGN,))
        (self.root / "map/definition.csv").write_text(
            "".join(
                f"{province};{r};{g};{b};land;false;plains;1\n"
                for province, (r, g, b) in MON_COLOURS.items()
            ),
            encoding="utf-8",
        )
        # Columns 0-1 donor, 2-3 city, 4-6 remainder, 7 a foreign state.
        provinces = Image.new("RGB", (8, 6))
        heights = Image.new("L", (8, 6))
        for x in range(8):
            province = DONOR if x < 2 else CITY if x < 4 else REMAINDER if x < 7 else FOREIGN
            for row in range(6):
                provinces.putpixel((x, row), MON_COLOURS[province])
                heights.putpixel((x, row), 10 * x + row)
        provinces.save(self.root / "map/provinces.bmp")
        heights.save(self.root / "map/heightmap.bmp")
        # The remainder has no unit stack yet, so its rows use the centroid.
        (self.root / "map/unitstacks.txt").write_bytes(
            f"{CITY};0;3.00;9.00;2.00;0.00;0.28\r\n"
            f"{DONOR};0;1.00;9.00;4.00;0.00;0.28\r\n"
            f"{FOREIGN};0;7.00;9.00;1.00;0.00;0.28".encode("utf-8")
        )
        self.write_plan([{"province": REMAINDER, "state": 469, "parent": CITY, "kind": "remainder"}])
        # Carving left the city's old row in the remainder and the donor's in the city.
        self.lines = [
            "469;supply_node;5.00;1.00;3.00;0.50;0",
            "469;supply_node;2.00;1.00;1.00;0.70;0",
            "999;supply_node;7.00;1.00;1.00;0.00;0",
        ]

    def write_state(self, state, provinces):
        (self.root / f"history/states/{state}.txt").write_text(
            f"state = {{ id = {state} provinces = {{ {' '.join(map(str, provinces))} }} }}",
            encoding="utf-8",
        )

    def write_plan(self, provinces):
        cities = {str(entry["parent"]): entry["parent"] for entry in provinces if entry["kind"] == "remainder"}
        geography = {
            "states": [469],
            "planned": {"origin": [0, 0], "first_id": 0, "provinces": provinces, "cities": cities, "villages": {}},
        }
        (self.root / "tools/data/adiscord_mon_geography.json").write_text(json.dumps(geography), encoding="utf-8")

    def test_city_and_remainder_rows_sit_at_their_own_anchors(self):
        planned, changed = builder.mon_province_rows_plan(self.root, self.lines)
        rotation = ((469 * 37 + DONOR * 53) % 628) / 100.0
        self.assertEqual(planned[:4], [
            "469;supply_node;5.00;5.20;3.00;0.50;0",
            "469;supply_node;3.00;3.30;2.00;0.70;0",
            "999;supply_node;7.00;1.00;1.00;0.00;0",
            f"469;supply_node;1.00;1.10;4.00;{rotation:.2f};0",
        ])
        self.assertEqual(changed[:3], [1, 2, 4])
        self.assertEqual(builder.mon_province_rows_plan(self.root, planned), (planned, []))

    def test_children_and_donors_gain_every_province_scoped_type(self):
        planned, _changed = builder.mon_province_rows_plan(self.root, [])
        anchors = {CITY: ("3.00", "2.00"), DONOR: ("1.00", "4.00"), REMAINDER: ("5.00", "3.00")}
        self.assertEqual(len(planned), 3 * len(builder.PROVINCE_ANCHOR_TYPES))
        for building_type in builder.PROVINCE_ANCHOR_TYPES:
            rows = [line.split(";") for line in planned if line.split(";")[1] == building_type]
            self.assertEqual(sorted((row[2], row[4]) for row in rows), sorted(anchors.values()))
            self.assertEqual({row[0] for row in rows}, {"469"})

    def test_surplus_row_moves_to_the_province_that_lost_one(self):
        lines = [
            "469;bunker;3.00;1.00;1.00;0.10;0",
            "469;bunker;2.00;1.00;5.00;0.20;0",
            "469;bunker;6.00;1.00;0.00;0.30;0",
        ]
        planned, changed = builder.mon_province_rows_plan(self.root, lines)
        self.assertEqual(planned[:3], [
            "469;bunker;3.00;3.30;2.00;0.10;0",
            "469;bunker;1.00;1.10;4.00;0.20;0",
            "469;bunker;5.00;5.20;3.00;0.30;0",
        ])
        self.assertEqual(changed[:3], [1, 2, 3])

    def test_slot_zero_split_by_native_rounding_falls_back_to_the_interior(self):
        (self.root / "map/unitstacks.txt").write_bytes(
            f"{CITY};0;3.60;9.00;2.00;0.00;0.28\r\n{DONOR};0;1.00;9.00;4.00;0.00;0.28".encode("utf-8")
        )
        planned, _changed = builder.mon_province_rows_plan(self.root, self.lines)
        # The city centroid is column 2.5, row 2.5; ties take the upper row, then the left column.
        self.assertEqual(planned[1], "469;supply_node;2.00;2.20;3.00;0.70;0")

    def test_empty_or_unapplied_plan_changes_nothing(self):
        for provinces in ([], [{"province": 19999, "state": 469, "parent": CITY, "kind": "remainder"}]):
            self.write_plan(provinces)
            self.assertEqual(builder.mon_province_rows_plan(self.root, self.lines), (self.lines, []))
            self.assertEqual(builder.mon_relief_provinces(self.root, builder.load_province_by_color(self.root)), frozenset())
            self.assertEqual(builder.mountain_building_heights(self.root, self.lines), (self.lines, []))

    def test_heights_follow_the_relief_only_inside_the_mon_scope(self):
        planned, changed = builder.mountain_building_heights(self.root, self.lines)
        self.assertEqual(changed, [1, 2])
        self.assertEqual(planned[0].split(";")[3], "5.20")
        self.assertEqual(planned[1].split(";")[3], "2.40")
        self.assertEqual(planned[2], self.lines[2])

    def test_synchronization_is_idempotent_and_keeps_native_line_endings(self):
        (self.root / "map/buildings.txt").write_bytes("\r\n".join(self.lines).encode("utf-8"))
        builder.synchronize_buildings(self.root, apply=True)
        first = (self.root / "map/buildings.txt").read_bytes()
        self.assertFalse(first.endswith(b"\n"))
        self.assertNotIn(b"\n", first.replace(b"\r\n", b""))
        self.assertEqual(len(first.split(b"\r\n")), 3 + 3 * len(builder.PROVINCE_ANCHOR_TYPES) - 2)
        builder.synchronize_buildings(self.root, apply=True)
        self.assertEqual((self.root / "map/buildings.txt").read_bytes(), first)


class MapDamPlacementTests(unittest.TestCase):
    def test_runtime_rows_are_on_their_own_province_at_the_same_river_crossing(self):
        rows = builder.BUILDINGS_PATH.read_text(encoding="utf-8").splitlines()
        colors = builder.load_province_by_color()
        owners = builder.load_state_by_province()
        sites = builder.load_dam_province_by_state()
        with (
            Image.open(builder.ROOT / "map/provinces.bmp") as provinces,
            Image.open(builder.ROOT / "map/rivers.bmp") as rivers,
            Image.open(builder.ROOT / "map/heightmap.bmp") as heights,
        ):
            for banks in (((28, 145), (53, 70)), ((688, 3127), (67, 12668))):
                poses = []
                river_pixels = []
                for state, province in banks:
                    matches = [row.split(";") for row in rows if row.startswith(f"{state};dam_spawn;")]
                    self.assertEqual(len(matches), 1)
                    pose = [unpack("f", pack("f", float(value)))[0] for value in matches[0][2:6]]
                    x, height, z, _angle = pose
                    pixel = int(x), provinces.height - 1 - int(z)
                    self.assertEqual(colors[provinces.getpixel(pixel)], province)
                    self.assertEqual(sites[state], province)
                    self.assertEqual(owners[province], state)
                    self.assertAlmostEqual(height, heights.getpixel(pixel) / 10, delta=0.101)
                    if state != 28:
                        rounded = round(x), provinces.height - 1 - round(z)
                        self.assertEqual(colors[provinces.getpixel(rounded)], province)
                    poses.append(pose)
                    river_pixels.append(rivers.getpixel(pixel))
                self.assertLess(dist(poses[0], poses[1]), 0.023)
                self.assertTrue(any(index in range(3, 12) for index in river_pixels))


if __name__ == "__main__":
    unittest.main()
