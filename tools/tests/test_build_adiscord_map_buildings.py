"""Map anchors obey native province and state ownership checks."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from PIL import Image

from tools.builders import build_adiscord_map_buildings as builder


class BorderDamTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        (self.root / "map").mkdir()
        (self.root / "history/states").mkdir(parents=True)
        for state, province in ((28, 145), (53, 70)):
            (self.root / f"history/states/{state}.txt").write_text(
                f"state = {{ id = {state} provinces = {{ {province} }} "
                f"history = {{ buildings = {{ {province} = {{ dam = 1 }} }} }} }}",
                encoding="utf-8",
            )
        (self.root / "map/definition.csv").write_text(
            "145;255;0;0;land;false;plains;1\n70;0;255;0;land;false;plains;1\n",
            encoding="utf-8",
        )
        provinces = Image.new("RGB", (4, 4), (255, 0, 0))
        for y in range(4):
            provinces.putpixel((2, y), (0, 255, 0))
            provinces.putpixel((3, y), (0, 255, 0))
        provinces.save(self.root / "map/provinces.bmp")
        Image.new("L", (4, 4), 100).save(self.root / "map/heightmap.bmp")
        self.lines = [
            "28;dam_spawn;1.00;10.00;1.00;0.00;0",
            "53;dam_spawn;1.00;10.00;1.00;0.00;0",
        ]
        self.write_buildings(self.lines)

    def write_buildings(self, lines):
        (self.root / "map/buildings.txt").write_bytes("\r\n".join(lines).encode("utf-8"))

    def test_audit_rejects_border_dam_in_neighbour_state(self):
        _lines, mismatches = builder.audit_buildings(self.root)
        self.assertEqual([(item.recorded_state, item.actual_state) for item in mismatches], [(53, 28)])

    def test_dam_plan_preserves_each_state_and_moves_only_invalid_anchor(self):
        planned, changed = builder.dam_province_plan(self.root, self.lines)
        self.assertEqual(changed, [2])
        self.assertEqual(planned[0], self.lines[0])
        self.assertEqual(planned[1], "53;dam_spawn;2.00;10.00;1.00;0.00;0")
        self.write_buildings(planned)
        self.assertEqual(builder.audit_buildings(self.root)[1], [])
        self.assertEqual(builder.dam_province_plan(self.root, planned), (planned, []))

    def test_synchronization_moves_dam_instead_of_transferring_its_state(self):
        builder.synchronize_buildings(self.root, apply=True)
        lines, mismatches = builder.audit_buildings(self.root)
        self.assertEqual(mismatches, [])
        self.assertEqual([line.split(";")[0] for line in lines], ["28", "53"])
        before = (self.root / "map/buildings.txt").read_bytes()
        self.assertEqual(builder.synchronize_buildings(self.root, apply=True), [])
        self.assertEqual((self.root / "map/buildings.txt").read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
