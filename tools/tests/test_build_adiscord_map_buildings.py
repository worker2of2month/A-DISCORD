"""Map anchors obey native province and state ownership checks."""

from __future__ import annotations

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
