"""Native landmark placement and regional reward contracts."""

import csv
import hashlib
import json
from pathlib import Path
import re
import struct
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image
from tools.lib.paths import repository_root
from tools.builders import build_adiscord_azhar_palace as azhar

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
        states = [
            p
            for p in (ROOT / "history/states").glob("*.txt")
            if KEY in p.read_text(encoding="utf-8-sig")
        ]
        self.assertEqual([p.name for p in states], ["48-Depoitodron.txt"])
        self.assertRegex(states[0].read_text(), KEY + r"\s*=\s*1\b")

    def test_footprint_stays_on_capital_land_and_foundation_meets_terrain(self):
        source = (ROOT / "map/ambient_object.txt").read_text()
        block = source.split('type = "' + KEY + '_entity"', 1)[1]
        self.assertIn("always_visible = yes", block)
        x, y, z = map(float, re.search(r"position\s*=\s*\{([^}]+)", block)[1].split())
        with (ROOT / "map/definition.csv").open() as stream:
            colors = {
                tuple(map(int, row[1:4]))
                for row in csv.reader(stream, delimiter=";")
                if row
                and row[0] in {"16514", "16515", "16519", "16521", "16530", "16535"}
            }
        with (
            Image.open(ROOT / "map/provinces.bmp") as provinces,
            Image.open(ROOT / "map/heightmap.bmp") as heights,
        ):
            # 32 x 22 mesh footprint at scale 0.20; foundation extends 0.4 below ground.
            for px in range(int(x - 3.2), int(x + 3.2) + 1):
                for pz in range(int(z - 2.2), int(z + 2.2) + 1):
                    self.assertIn(
                        provinces.getpixel((px, provinces.height - 1 - pz)), colors
                    )
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
                line = next(
                    (
                        line
                        for line in raw.decode("utf-8-sig").splitlines()
                        if line.startswith(" " + KEY + suffix + ":")
                    ),
                    "",
                )
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


class NamHarbourTests(unittest.TestCase):
    def test_verified_native_package_matches_installed_bytes(self):
        report = json.loads((ROOT / "docs/development/model-verification/NAM_harbour.json").read_text())
        self.assertTrue(report["native_reimport"])
        self.assertEqual(report["materials"], 1)
        self.assertLess(report["triangles"], 20000)
        folder = ROOT / "gfx/models/buildings/NAM_harbour"
        for name, expected in report["files"].items():
            self.assertEqual(hashlib.sha256((folder / name).read_bytes()).hexdigest(), expected)
        source = ROOT / "tools/assets/source/build_nam_harbour.py"
        self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(), report["source_sha256"])
        for suffix in ("diffuse", "normal", "specular"):
            raw = (folder / f"ADISCORD_NAM_harbour_{suffix}.dds").read_bytes()
            self.assertEqual(raw[84:88], b"DXT5")
            self.assertEqual(struct.unpack_from("<I", raw, 28)[0], 11)
            with Image.open(folder / f"ADISCORD_NAM_harbour_{suffix}.dds") as image:
                self.assertEqual(image.size, (1024, 1024))

    def test_native_binding_has_one_placement_and_leaves_port_mechanics_native(self):
        key = "ADISCORD_NAM_harbour"
        gfx = (ROOT / "gfx/entities/mapitems_custom.gfx").read_text()
        entities = (ROOT / "gfx/entities/mapitems_custom.asset").read_text()
        ambient = (ROOT / "map/ambient_object.txt").read_text()
        self.assertEqual(gfx.count(f'name = "{key}_mesh"'), 1)
        self.assertEqual(entities.count(f'name = "{key}_entity"'), 1)
        self.assertEqual(ambient.count(f'type = "{key}_entity"'), 1)
        self.assertIn(f'pdxmesh = "{key}_mesh"', entities)
        self.assertIn(f'file = "gfx/models/buildings/NAM_harbour/{key}.mesh"', gfx)
        block = ambient.split("# BEGIN ADISCORD NAM harbour", 1)[1].split("# END ADISCORD NAM harbour", 1)[0]
        self.assertIn("always_visible = yes", block)
        self.assertIn("use_animation = no", block)
        state = (ROOT / "history/states/700-South-Harbour.txt").read_text()
        self.assertIn("16716 = { naval_base = 1 }", state)

    def test_quay_reaches_water_while_rear_wing_meets_south_harbour_land(self):
        report = json.loads((ROOT / "docs/development/model-verification/NAM_harbour.json").read_text())
        x, elevation, z = report["placement"]["position"]
        scale = report["placement"]["scale"]
        with (ROOT / "map/definition.csv").open() as stream:
            definitions = {tuple(map(int, row[1:4])): (int(row[0]), row[4])
                           for row in csv.reader(stream, delimiter=";") if row}
        with Image.open(ROOT / "map/provinces.bmp") as provinces, Image.open(ROOT / "map/heightmap.bmp") as heights:
            def sample(px, pz):
                point = (int(x + px * scale), provinces.height - 1 - int(z + pz * scale))
                return definitions[provinces.getpixel(point)], heights.getpixel(point) / 10

            for px in (-8, 0, 12):
                for pz in (4, 8):
                    definition, terrain = sample(px, pz)
                    self.assertIn(definition[0], {16716, 16892})
                    self.assertLessEqual(terrain, elevation + 1.2 * scale)
                    self.assertGreater(terrain, elevation - 9.2 * scale)
            for px, pz in ((-15, -13), (12, -9)):
                definition, _ = sample(px, pz)
                self.assertEqual(definition[1], "sea")


class AzharPalaceTests(unittest.TestCase):
    def test_landmark_is_on_black_harbor_land_above_terrain(self):
        source = (ROOT / "map/ambient_object.txt").read_text()
        block = azhar.ambient_block(source.encode()).decode()
        self.assertEqual(len(re.findall(r'type\s*=\s*"' + azhar.NAME + '_entity"', source)), 1)
        self.assertRegex(block, r"always_visible\s*=\s*yes")
        x, y, z = map(float, re.search(r"position\s*=\s*\{([^}]+)", block)[1].split())
        scale = float(re.search(r"scale\s*=\s*([\d.]+)", block)[1])
        state = (ROOT / "history/states/692-Black-Coast.txt").read_text()
        self.assertRegex(state, r"owner\s*=\s*AZH\b")
        self.assertRegex(state, r"victory_points\s*=\s*\{\s*493\s+1\s*\}")
        report = json.loads((ROOT / azhar.REPORT).read_text())
        self.assertEqual(report["placement"]["province"], 493)
        self.assertEqual(report["placement"]["position"], [x, y, z])
        self.assertEqual(report["placement"]["scale"], scale)
        bounds = report["bounds_blender_xyz"]
        with Image.open(ROOT / "map/provinces.bmp") as provinces, Image.open(ROOT / "map/heightmap.bmp") as heightmap:
            # Check the complete projected footprint, including the approach paving.
            for ix in range(45):
                px = x + scale * (bounds[0][0] + ix * (bounds[0][1] - bounds[0][0]) / 44)
                for iz in range(36):
                    pz = z + scale * (bounds[1][0] + iz * (bounds[1][1] - bounds[1][0]) / 35)
                    point = (round(px), provinces.height - 1 - round(pz))
                    self.assertEqual(provinces.getpixel(point), (254, 232, 65))
                    ground = heightmap.getpixel(point) / 10
                    self.assertLessEqual(y + scale * bounds[2][0], ground)
                    self.assertGreaterEqual(y + scale * 1.36, ground)

    def test_exported_asset_chain_and_source_are_current(self):
        self.assertEqual(azhar.stale_outputs(), [])
        report = json.loads((ROOT / azhar.REPORT).read_text())
        self.assertTrue(report["native_reimport"])
        self.assertEqual(report["materials"], 1)
        self.assertLess(report["triangles"], 15000)
        self.assertLess(report["vertices"], 65536)
        for name, sha256 in report["files"].items():
            raw = (ROOT / azhar.MODEL_DIR / name).read_bytes()
            self.assertEqual(hashlib.sha256(raw).hexdigest(), sha256)
            if name.endswith(".dds"):
                self.assertEqual(raw[84:88], b"DXT5")
                self.assertEqual(struct.unpack_from("<II", raw, 12), (1024, 1024))
                self.assertEqual(struct.unpack_from("<I", raw, 28)[0], 11)
        gfx = (ROOT / "gfx/entities/mapitems_custom.gfx").read_text()
        self.assertEqual(gfx.count('name = "' + azhar.NAME + '_mesh"'), 1)
        self.assertIn((azhar.MODEL_DIR / azhar.FILES[0]).as_posix(), gfx)
        asset = (ROOT / "gfx/entities/mapitems_custom.asset").read_text()
        self.assertEqual(asset.count('pdxmesh = "' + azhar.NAME + '_mesh"'), 1)

    def test_installer_preserves_unrelated_registry_bytes(self):
        original = b'# Authored actors\r\ntype={\r\n\ttype="other_entity"\r\n}\r\n'
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for relative in ("gfx/entities/mapitems_custom.gfx", "gfx/entities/mapitems_custom.asset", "map/ambient_object.txt"):
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(original)
            with patch.object(azhar, "ROOT", root):
                first = azhar.section_outputs()
                for path, data in first.items():
                    self.assertTrue(data.startswith(original + b"\r\n"))
                    path.write_bytes(data)
                self.assertEqual(azhar.section_outputs(), first)

    def test_nudge_serialization_is_preserved_but_moved_actor_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for relative in ("gfx/entities/mapitems_custom.gfx", "gfx/entities/mapitems_custom.asset", "map/ambient_object.txt"):
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b"# Existing registry\r\n")
            with patch.object(azhar, "ROOT", root):
                for path, data in azhar.section_outputs().items():
                    path.write_bytes(data)
                path = root / "map/ambient_object.txt"
                serialized = re.sub(rb"#[^\r\n]*\r?\n", b"", path.read_bytes())
                serialized = serialized.replace(b" = ", b"=").replace(b"3876.000", b"3876")
                path.write_bytes(serialized)
                self.assertEqual(azhar.section_outputs()[path], serialized)
                path.write_bytes(serialized.replace(b"3876", b"3886"))
                with self.assertRaisesRegex(AssertionError, "placement changed in Nudge"):
                    azhar.section_outputs()


if __name__ == "__main__":
    unittest.main()
