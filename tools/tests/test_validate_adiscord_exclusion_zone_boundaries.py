import unittest

from tools.validators.validate_adiscord_exclusion_zone_boundaries import validate


class ExclusionZoneBoundaryContractsTest(unittest.TestCase):
    def test_sla_capital_and_starting_unit_stay_outside_khan_state(self):
        from tools.builders.build_adiscord_map_buildings import ROOT, load_state_by_province
        from tools.lib.vorkerland_collapse_manifest import CAPITALS
        state, province = CAPITALS["SLA"]
        self.assertEqual(state, 49)
        self.assertEqual(load_state_by_province()[province], state)
        source = (ROOT / "history/units/SLA_vorkerland_collapse.txt").read_text()
        self.assertIn(f"location = {province}", source)
        self.assertNotIn("location = 16639", source)

    def test_khan_border_is_preserved_by_boundary_source(self):
        from tools.builders.build_adiscord_exclusion_zone_boundaries import load_source
        self.assertFalse({16512, 16523, 16639} & load_source()[49])

    def test_khan_unit_anchors_remain_inside_their_provinces(self):
        from PIL import Image
        from tools.builders.build_adiscord_map_buildings import ROOT, load_province_by_color
        colors = load_province_by_color()
        with Image.open(ROOT / "map/provinces.bmp") as raster:
            for line in (ROOT / "map/unitstacks.txt").read_text().splitlines():
                fields = line.split(";")
                if fields[0] not in {"16512", "16523", "16531", "16639"}:
                    continue
                for convert in (int, round):
                    x = convert(float(fields[2]))
                    y = raster.height - 1 - convert(float(fields[4]))
                    self.assertEqual(colors[raster.getpixel((x, y))], int(fields[0]), line)

    def test_carved_mon_provinces_join_their_snapshot_state(self):
        from unittest.mock import patch

        from tools.builders import build_adiscord_exclusion_zone_boundaries as boundaries

        with patch.object(boundaries, "mon_planned_provinces", return_value={}):
            baseline = boundaries.load_source()
        planned = {460: frozenset({90001}), 472: frozenset({90002}), 469: frozenset({90003})}
        with patch.object(boundaries, "mon_planned_provinces", return_value=planned):
            extended = boundaries.load_source()
        self.assertEqual(baseline[460] | {90001}, extended[460])
        self.assertEqual(baseline[472] | {90002}, extended[472])
        self.assertNotIn(469, extended)
        for state_id in set(baseline) - {460, 472}:
            self.assertEqual(baseline[state_id], extended[state_id])

    def test_exclusion_zone_boundary_contract(self):
        self.assertEqual([], validate())


if __name__ == "__main__":
    unittest.main()
