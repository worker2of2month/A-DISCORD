"""Native landmark placement and regional reward contracts."""
import csv
import re
import unittest

from PIL import Image
from tools.lib.paths import repository_root

ROOT = repository_root()
KEY = "ADISCORD_kefreyt_arms_combine"


class KefreytLandmarkTests(unittest.TestCase):
    def test_unique_starting_building_has_only_small_state_rewards(self):
        buildings = (ROOT / "common/buildings/01_landmark_buildings.txt").read_text()
        block = buildings.split(KEY + " = {", 1)[1]
        self.assertIn("is_buildable = no", block)
        self.assertIn("state_production_speed_buildings_factor = 0.05", block)
        self.assertIn("state_resources_factor = 0.05", block)
        self.assertNotIn("country_modifiers", block)
        states = [p for p in (ROOT / "history/states").glob("*.txt") if KEY in p.read_text(encoding="utf-8-sig")]
        self.assertEqual([p.name for p in states], ["48-Depoitodron.txt"])
        self.assertRegex(states[0].read_text(), KEY + r"\s*=\s*1\b")

    def test_footprint_stays_on_capital_land_and_foundation_meets_terrain(self):
        source = (ROOT / "map/ambient_object.txt").read_text()
        block = source.split('type = "' + KEY + '_entity"', 1)[1]
        x, y, z = map(float, re.search(r"position\s*=\s*\{([^}]+)", block)[1].split())
        with (ROOT / "map/definition.csv").open() as stream:
            colors = {tuple(map(int, row[1:4])) for row in csv.reader(stream, delimiter=";")
                      if row and row[0] in {"16514", "16515", "16519", "16521", "16530", "16535"}}
        with Image.open(ROOT / "map/provinces.bmp") as provinces, Image.open(ROOT / "map/heightmap.bmp") as heights:
            # 32 x 22 mesh footprint at scale 0.20; foundation extends 0.4 below ground.
            for px in range(int(x - 3.2), int(x + 3.2) + 1):
                for pz in range(int(z - 2.2), int(z + 2.2) + 1):
                    self.assertIn(provinces.getpixel((px, provinces.height - 1 - pz)), colors)
                    terrain = heights.getpixel((px, heights.height - 1 - pz)) / 10
                    self.assertLessEqual(y - 0.4, terrain)
                    self.assertGreaterEqual(y + 0.08, terrain)

    def test_localisation_and_native_asset_chain(self):
        for language in ("russian", "english"):
            path = ROOT / f"localisation/{language}/buildings_l_{language}.yml"
            raw = path.read_bytes()
            if language == "russian":
                self.assertTrue(raw.startswith(b"\xef\xbb\xbf"))
            for suffix in ("", "_plural", "_desc"):
                line = next((line for line in raw.decode("utf-8-sig").splitlines()
                             if line.startswith(" " + KEY + suffix + ":")), "")
                self.assertRegex(line, r'^ ' + KEY + suffix + r':(?:0)? "[^\n]+"$')
        gfx = (ROOT / "gfx/entities/mapitems_custom.gfx").read_text()
        self.assertIn('name = "' + KEY + '_mesh"', gfx)
        asset = (ROOT / "gfx/entities/mapitems_custom.asset").read_text()
        self.assertIn('pdxmesh = "' + KEY + '_mesh"', asset)
        folder = ROOT / "gfx/models/buildings/VAL_arms_combine"
        self.assertTrue((folder / (KEY + ".mesh")).is_file())
        for suffix in ("diffuse", "normal", "specular"):
            with Image.open(folder / f"Combine_{suffix}.dds") as texture:
                self.assertEqual(texture.size, (512, 512))


if __name__ == "__main__":
    unittest.main()
