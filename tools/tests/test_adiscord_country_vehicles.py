"""Country vehicle selection and native export contracts."""
import hashlib
import json
import re
import unittest

from tools.lib.paths import repository_root

ROOT = repository_root()
SOURCE = ROOT / "tools/assets/source/country_vehicles"
DEST = ROOT / "gfx/models/units/ADISCORD_country_vehicles"
NAMES = tuple(f"{tag}_{role}" for tag in ("VAL", "NOD", "STP") for role in ("tank", "fighter", "cas"))


class CountryVehicleTests(unittest.TestCase):
    def test_nine_distinct_native_meshes_have_current_verification(self):
        report = json.loads((SOURCE / "verification.json").read_text())
        self.assertEqual(set(report), set(NAMES))
        digests = set()
        for name in NAMES:
            with self.subTest(name=name):
                row = report[name]
                for filename, digest in row["files"].items():
                    self.assertEqual(hashlib.sha256((DEST / filename).read_bytes()).hexdigest(), digest)
                digests.add(row["files"][name + ".mesh"])
                self.assertGreater(row["triangles"], 100)
                self.assertLess(row["triangles"], 16000)
                self.assertEqual(row["materials"], 1)
                self.assertGreater(row["bones"], 0)
                self.assertTrue(row["rigid_skin_slots_validated"])
                self.assertGreater(row["animations"]["idle"]["samples"], 1)
                if name.endswith("_tank"):
                    self.assertGreater(row["animations"]["move"]["max_vertex_motion"], .1)
                    self.assertGreater(row["animations"]["attack"]["max_vertex_motion"], .1)
                    self.assertLess(row["animations"]["move"]["loop_error"], .001)
                    self.assertTrue({"barrel", "left_tracks", "right_tracks", "left_exhaust", "right_exhaust"}.issubset(row["locators"]))
                else:
                    self.assertTrue({"root", "gun1", "gun2", "bomb"}.issubset(row["locators"]))
        self.assertEqual(len(digests), 9)

    def test_country_and_equipment_routes_do_not_replace_generic_entities(self):
        asset = (ROOT / "gfx/entities/zz_ADISCORD_country_vehicles.asset").read_text()
        names = re.findall(r'entity\s*=\s*\{[^{}]*?\bname\s*=\s*"([^"\n]+)"', asset)
        self.assertEqual(len(names), len(set(names)))
        self.assertNotIn("medium_armor_entity", names)
        self.assertNotIn("light_plane_entity", names)
        for tag in ("VAL", "NOD", "STP", "STS", "SRP"):
            for suffix in ("medium_armor", "ADISCORD_combat_platform_2170", "ADISCORD_combat_platform_2183",
                           "ADISCORD_combat_platform_2200", "ADISCORD_fighter_airframe_2163", "ADISCORD_cas_airframe_2170"):
                self.assertIn(f"{tag}_{suffix}_entity", names)
            fighter = re.search(r'entity\s*=\s*\{[^{}]*name\s*=\s*"' + tag + r'_ADISCORD_fighter_airframe_2163_entity"[^{}]*\}', asset)[0]
            cas = re.search(r'entity\s*=\s*\{[^{}]*name\s*=\s*"' + tag + r'_ADISCORD_cas_airframe_2170_entity"[^{}]*\}', asset)[0]
            self.assertIn("_fighter_entity", fighter)
            self.assertIn("_cas_entity", cas)

    def test_air_roles_have_distinct_sprites_with_generic_fallbacks(self):
        units = (ROOT / "common/units/ADISCORD_air_units.txt").read_text()
        equipment = (ROOT / "common/units/equipment/ADISCORD_air_equipment.txt").read_text()
        assets = (ROOT / "gfx/entities/zz_ADISCORD_country_vehicles.asset").read_text()
        for role in ("fighter", "cas"):
            self.assertRegex(units, role + r"\s*=\s*\{\s*sprite = ADISCORD_" + role)
            block = equipment.split("ADISCORD_" + role + "_archetype = {", 1)[1].split("\n\t}", 1)[0]
            self.assertIn("sprite = ADISCORD_" + role, block)
            self.assertIn('clone = "light_plane_entity" name = "ADISCORD_' + role + '_entity"', assets)

    def test_packaging_is_idempotent(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("country_vehicles_package", SOURCE / "package_vehicles.py")
        package = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(package)
        self.assertEqual(package.package(apply=False), [])


if __name__ == "__main__":
    unittest.main()
