"""Map anchors obey native province and state ownership checks."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from PIL import Image

from tools.builders import build_adiscord_map_buildings as builder


# Columns 0-1 are province 145, column 2 is 70 and column 3 is 16436. The shared
# border anchor lies in 145 by truncation and in 70 by rounding.
FIXTURE_BORDER_ANCHOR = ("1.86", "10.00", "1.00", "0.00")


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
        anchor = mock.patch.object(builder, "BORDER_DAM_ANCHOR", FIXTURE_BORDER_ANCHOR)
        anchor.start()
        self.addCleanup(anchor.stop)

    def write_buildings(self, lines):
        (self.root / "map/buildings.txt").write_bytes("\r\n".join(lines).encode("utf-8"))

    def test_audit_accepts_shared_border_anchor_but_rejects_other_dams(self):
        shared = [
            "28;dam_spawn;1.86;10.00;1.00;0.00;0",
            "53;dam_spawn;1.86;10.00;1.00;0.00;0",
            "42;dam_spawn;2.00;10.00;1.00;0.00;0",
        ]
        self.write_buildings(shared)
        _lines, mismatches = builder.audit_buildings(self.root)
        self.assertEqual([(item.recorded_state, item.actual_state) for item in mismatches], [(42, 53)])

    def test_dam_plan_shares_border_anchor_and_moves_other_invalid_anchor(self):
        planned, changed = builder.dam_province_plan(self.root, self.lines)
        self.assertEqual(changed, [1, 2, 3])
        self.assertEqual(planned[0], "28;dam_spawn;1.86;10.00;1.00;0.00;0")
        self.assertEqual(planned[1], "53;dam_spawn;1.86;10.00;1.00;0.00;0")
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
        with (
            mock.patch.object(builder, "NAM_DAM_PROVINCES", {688: 145, 67: 70}),
            mock.patch.object(builder, "NAM_DAM_ANCHOR", FIXTURE_BORDER_ANCHOR),
        ):
            planned, changed = builder.dam_province_plan(self.root, self.lines)
            self.assertEqual(planned[-2:], [
                "688;dam_spawn;1.86;10.00;1.00;0.00;0",
                "67;dam_spawn;1.86;10.00;1.00;0.00;0",
            ])
            self.assertIn(4, changed)
            self.assertIn(5, changed)
            self.assertEqual(builder.dam_province_plan(self.root, planned), (planned, []))

    def test_svetlogorsk_anchor_crosses_the_actual_river_and_scripted_provinces(self):
        x, _height, z, _angle = map(float, builder.NAM_DAM_ANCHOR)
        colors = builder.load_province_by_color()
        with (
            Image.open(builder.ROOT / "map/provinces.bmp") as provinces,
            Image.open(builder.ROOT / "map/rivers.bmp") as rivers,
        ):
            banks = {
                colors[provinces.getpixel((convert(x), provinces.height - 1 - convert(z)))]
                for convert in (int, round)
            }
            self.assertEqual(banks, set(builder.NAM_DAM_PROVINCES.values()))
            self.assertIn(rivers.getpixel((int(x), rivers.height - 1 - int(z))), range(3, 12))


if __name__ == "__main__":
    unittest.main()
