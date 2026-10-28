"""Native oilfield assets, map ownership and shared-registry boundaries."""

import json
import re
import unittest
from collections import Counter

import numpy as np
from PIL import Image

from tools.builders import build_adiscord_nam_oilfields as builder


class NamOilfieldTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sites = builder.placements()

    def test_large_deposits_receive_clusters_on_clear_land(self):
        self.assertEqual(Counter(site["state"] for site in self.sites), {67: 2, 689: 1, 690: 1})
        provinces = np.asarray(Image.open(builder.ROOT / "map/provinces.bmp").convert("RGB"))
        heights = np.asarray(Image.open(builder.ROOT / "map/heightmap.bmp"), dtype=float) / 10
        definitions = {}
        for line in (builder.ROOT / "map/definition.csv").read_text(encoding="utf-8-sig").splitlines():
            fields = line.split(";")
            if fields[0].isdigit():
                definitions[int(fields[0])] = fields
        states = {s["state"]: s for s in builder.oil_states()}
        for site in self.sites:
            with self.subTest(site=site):
                state = states[site["state"]]
                self.assertGreaterEqual(state["oil"], 24)
                self.assertIn(site["province"], state["provinces"])
                self.assertNotIn(site["province"], state["cities"])
                x, y, z = site["position"]
                row, col = len(heights) - 1 - int(z), int(x)
                rgb = np.array(list(map(int, definitions[site["province"]][1:4])))
                self.assertTrue(np.all(provinces[row - 3:row + 4, col - 3:col + 4] == rgb))
                ground = heights[row - 3:row + 4, col - 3:col + 4]
                self.assertGreaterEqual(float(ground.min()), 10)
                self.assertLess(y - 3 * site["scale"], float(ground.min()))
                self.assertGreater(y + .75 * site["scale"], float(ground.max()))

    def test_native_package_and_shared_bindings_are_current(self):
        self.assertEqual(builder.stale_outputs(), [])
        report = json.loads((builder.ROOT / builder.REPORT).read_text())
        self.assertTrue(report["native_reimport"])
        self.assertEqual(report["derricks_per_cluster"], 3)
        self.assertEqual(report["materials"], 1)
        self.assertLess(report["triangles"], 12000)
        self.assertEqual(report["placements"], self.sites)
        for path, expected in builder.section_outputs().items():
            self.assertEqual(path.read_bytes(), expected)
            self.assertEqual(expected.count(("# BEGIN " + builder.MARKER).encode()), 1)

    def test_no_gameplay_or_dynamic_polling_in_ambient_actor(self):
        text = builder.ambient_text()
        self.assertEqual(len(re.findall(r"\bobject\s*=", text)), 4)
        self.assertIn("use_animation = no", text)
        self.assertIn("always_visible = yes", text)
        self.assertNotIn("trigger", text)


if __name__ == "__main__":
    unittest.main()
