"""Office actor replacement, terrain bounds and shared placement contracts."""

import json
import re
import unittest
from collections import Counter

import numpy as np
from PIL import Image

from tools.builders import build_adiscord_nam_export_offices as builder
from tools.builders.build_adiscord_map_buildings import nam_export_office_clearance


class ExportOfficeModelsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = json.loads((builder.ROOT / builder.REPORT).read_text())

    def test_replacement_uses_one_stable_actor_per_region(self):
        script = (builder.ROOT / builder.EFFECTS).read_text()
        self.assertEqual(re.findall(r"destroy_entity = (\d+)", script), [str(620000 + s) for s in builder.STATES])
        self.assertEqual(Counter(re.findall(r"\bid = (\d+)", script)), {str(620000 + s): 5 for s in builder.STATES})
        for level in range(1, 6):
            self.assertEqual(script.count(f"entity = ADISCORD_NAM_export_office_level_{level}_entity"), 5)
            self.assertEqual(script.count(f"value = {level} compare = equals"), 5)
        self.assertNotIn("add_building_construction", script)
        self.assertNotIn("on_daily", script)

    def test_native_exports_have_distinct_silhouettes_and_one_material(self):
        self.assertTrue(self.report["native_reimport"])
        self.assertFalse(self.report["hoi4_runtime_verified"])
        previous_width = 0
        for stage in builder.STAGES:
            model = self.report["models"][stage]
            self.assertEqual(model["materials"], 1)
            self.assertLess(model["triangles"], 24000)
            self.assertGreater(model["bounds"][0][1] - model["bounds"][0][0], previous_width)
            previous_width = model["bounds"][0][1] - model["bounds"][0][0]
        self.assertEqual(builder.stale(), [])

    def test_giant_terminal_bounds_match_every_reserved_site(self):
        def footprint(stage):
            bounds = self.report["models"][stage]["bounds"]
            return np.array([high - low for low, high in bounds[:2]]) * self.report["native_scale"]

        final = footprint("level_5")
        self.assertGreater(np.prod(final), 3 * np.prod(footprint("level_4")))
        manifest = json.loads((builder.ROOT / "tools/data/nam_export_office_sites.json").read_text())
        sites = {site["state"]: site for site in manifest["sites"]}
        for placement in self.report["placements"]:
            site = sites[placement["state"]]
            np.testing.assert_allclose(site["maximum_model_footprint"], final)
            self.assertTrue(np.all(site["reserved_footprint"] >= final))
            for key, value in site.items():
                self.assertEqual(placement[key], value, (site["state"], key))

    def test_each_tier_covers_the_actual_ground_without_an_absolute_height_offset(self):
        heights = np.asarray(Image.open(builder.ROOT / "map/heightmap.bmp"), dtype=float) / 10
        for site in self.report["placements"]:
            x, _, y = site["position"]
            center = heights[len(heights) - 1 - int(y), int(x)]
            for index, (width, depth) in enumerate(builder.SIZES):
                tier = site["tier_terrain"][index]
                self.assertLess(abs(tier["height_offset"]), 1)
                bottom = center + tier["height_offset"] - 12.2 * builder.SCALE
                grid = site["terrain_grid"]
                hx = int(np.ceil(width * builder.SCALE / 2 - .5))
                hy = int(np.ceil(depth * builder.SCALE / 2 - .5))
                actual = np.asarray(grid)[6 - hy:7 + hy, 6 - hx:7 + hx] + center
                self.assertLess(bottom, actual.min())
                self.assertAlmostEqual(center + tier["height_offset"] + .02, actual.max(), places=5)

    def test_building_clearance_is_idempotent_and_preserves_types(self):
        lines = (builder.ROOT / "map/buildings.txt").read_text().splitlines()
        manifest = json.loads((builder.ROOT / "tools/data/nam_export_office_sites.json").read_text())
        samples = [f"{p['state']};{p['type']};{p['from'][0]};10;{p['from'][1]};0;0" for p in manifest["relocations"]]
        moved = nam_export_office_clearance(samples)
        self.assertEqual(nam_export_office_clearance(moved), moved)
        self.assertEqual(nam_export_office_clearance(lines), lines)
        self.assertEqual([s.split(";")[:2] for s in samples], [s.split(";")[:2] for s in moved])


if __name__ == "__main__":
    unittest.main()
