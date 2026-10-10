"""Country vehicle selection and native export contracts."""

import hashlib
import json
import re
import unittest

from tools.lib.paths import repository_root

ROOT = repository_root()
SOURCE = ROOT / "tools/assets/source/country_vehicles"
DEST = ROOT / "gfx/models/units/ADISCORD_country_vehicles"
NAMES = tuple(
    f"{tag}_{role}"
    for tag in ("VAL", "NOD", "STP")
    for role in ("tank", "fighter", "cas")
)
NEW_NAMES = tuple(
    f"{tag}_{generation}_{role}"
    for tag in ("VAL", "NOD", "STP")
    for generation in ("early", "future")
    for role in ("fighter", "cas")
)


class CountryVehicleTests(unittest.TestCase):
    def test_late_equipment_uses_the_future_visual_level(self):
        text = (ROOT / "common/units/equipment/ADISCORD_air_equipment.txt").read_text()
        for equipment in (
            "ADISCORD_interceptor_airframe_2183",
            "ADISCORD_drone_airframe_2183",
            "ADISCORD_fighter_airframe_2170",
            "ADISCORD_fighter_airframe_2175",
            "ADISCORD_attack_airframe_2170",
            "ADISCORD_attack_airframe_2175",
        ):
            block = text.split(equipment + " = {", 1)[1].split("\n\t}", 1)[0]
            with self.subTest(equipment=equipment):
                self.assertRegex(block, r"\bvisual_level\s*=\s*2\b")

    def test_new_native_aircraft_have_distinct_verified_meshes_and_spinning_props(self):
        report = json.loads((SOURCE / "verification.json").read_text())
        hashes = set()
        for name in NEW_NAMES:
            with self.subTest(name=name):
                row = report[name]
                for filename, digest in row["files"].items():
                    self.assertEqual(hashlib.sha256((DEST / filename).read_bytes()).hexdigest(), digest)
                hashes.add(row["files"][name + ".mesh"])
                self.assertGreater(row["triangles"], 100)
                self.assertLess(row["triangles"], 16000)
                self.assertEqual(row["materials"], 1)
                self.assertTrue(row["rigid_skin_slots_validated"])
                self.assertTrue({"root", "gun1", "gun2", "bomb"}.issubset(row["locators"]))
                idle = row["animations"]["idle"]
                self.assertLess(idle["loop_error"], 0.001)
                if "_early_" in name:
                    self.assertGreater(idle["max_vertex_motion"], 0.1)
        self.assertEqual(len(hashes), len(NEW_NAMES))

    def test_aircraft_generations_resolve_for_each_country_and_successor(self):
        text = (ROOT / "gfx/entities/zz_ADISCORD_country_vehicles.asset").read_text()
        routes = dict(
            (name, parent)
            for parent, name in re.findall(
                r'entity = \{ clone = "([^"]+)" name = "([^"]+)" \}', text
            )
        )
        generations = {
            "ADISCORD_fighter_airframe_2163": "early_fighter",
            "ADISCORD_fighter_airframe_2161": "fighter",
            "ADISCORD_fighter_airframe_2166": "fighter",
            "ADISCORD_fighter_airframe_2170": "future_fighter",
            "ADISCORD_fighter_airframe_2175": "future_fighter",
            "ADISCORD_interceptor_airframe_2183": "future_fighter",
            "ADISCORD_cas_airframe_2170": "early_cas",
            "ADISCORD_attack_airframe_2163": "cas",
            "ADISCORD_vtol_airframe_2170": "cas",
            "ADISCORD_attack_airframe_2170": "future_cas",
            "ADISCORD_attack_airframe_2175": "future_cas",
            "ADISCORD_drone_airframe_2183": "future_cas",
        }
        countries = {
            "VAL": "VAL",
            "NOD": "NOD",
            "STP": "NOD",
            "STS": "STP",
            "SRP": "STP",
        }
        for tag, source in countries.items():
            for equipment, model in generations.items():
                with self.subTest(tag=tag, equipment=equipment):
                    self.assertEqual(
                        routes.get(f"{tag}_{equipment}_entity"),
                        f"ADISCORD_{source}_{model}_entity",
                    )
            for role in ("fighter", "cas"):
                for level, prefix in ((0, "early_"), (1, ""), (2, "future_")):
                    self.assertEqual(
                        routes.get(f"{tag}_ADISCORD_{role}_{level}_entity"),
                        f"ADISCORD_{source}_{prefix}{role}_entity",
                    )

    def test_supersonic_flyby_does_not_draw_pulsing_clouds(self):
        path = ROOT / "gfx/particles/vehicles/sonic_boom.asset"
        self.assertTrue(path.is_file(), "native sonic-boom emitters are still visible")
        particle = path.read_text(encoding="utf-8")
        self.assertRegex(particle, r'name\s*=\s*"sonic_boom_file"')
        self.assertEqual(len(re.findall(r"\bsubsystem\s*=", particle)), 3)
        self.assertEqual(re.findall(r"\bhide\s*=\s*(\w+)", particle), ["no"] * 3)
        self.assertEqual(re.findall(r"\bmax_amount\s*=\s*(\d+)", particle), ["0"] * 3)

    def test_vehicles_keep_their_paint_in_snow(self):
        for name in NAMES:
            with self.subTest(name=name):
                mesh = (DEST / (name + ".mesh")).read_bytes()
                self.assertTrue(b"PdxMeshAdvanced\x00" in mesh, "missing paint shader")
                self.assertFalse(
                    b"PdxMeshAdvancedSnow" in mesh, "snow shader changes vehicle paint"
                )

    def test_nine_distinct_native_meshes_have_current_verification(self):
        report = json.loads((SOURCE / "verification.json").read_text())
        self.assertEqual(set(report), set(NAMES + NEW_NAMES))
        digests = set()
        for name in NAMES:
            with self.subTest(name=name):
                row = report[name]
                for filename, digest in row["files"].items():
                    self.assertEqual(
                        hashlib.sha256((DEST / filename).read_bytes()).hexdigest(),
                        digest,
                    )
                digests.add(row["files"][name + ".mesh"])
                self.assertGreater(row["triangles"], 100)
                self.assertLess(row["triangles"], 16000)
                self.assertEqual(row["materials"], 1)
                self.assertGreater(row["bones"], 0)
                self.assertTrue(row["rigid_skin_slots_validated"])
                self.assertGreater(row["animations"]["idle"]["samples"], 1)
                if name.endswith("_tank"):
                    self.assertGreater(
                        row["animations"]["move"]["max_vertex_motion"], 0.1
                    )
                    self.assertGreater(
                        row["animations"]["attack"]["max_vertex_motion"], 0.1
                    )
                    self.assertLess(row["animations"]["move"]["loop_error"], 0.001)
                    self.assertTrue(
                        {
                            "barrel",
                            "left_tracks",
                            "right_tracks",
                            "left_exhaust",
                            "right_exhaust",
                        }.issubset(row["locators"])
                    )
                else:
                    self.assertTrue(
                        {"root", "gun1", "gun2", "bomb"}.issubset(row["locators"])
                    )
        self.assertEqual(len(digests), 9)

    def test_country_and_equipment_routes_do_not_replace_generic_entities(self):
        asset = (ROOT / "gfx/entities/zz_ADISCORD_country_vehicles.asset").read_text()
        names = re.findall(r'entity\s*=\s*\{[^{}]*?\bname\s*=\s*"([^"\n]+)"', asset)
        self.assertEqual(len(names), len(set(names)))
        self.assertNotIn("medium_armor_entity", names)
        self.assertNotIn("light_plane_entity", names)
        for tag in ("VAL", "NOD", "STP", "STS", "SRP"):
            for suffix in (
                "medium_armor",
                "ADISCORD_combat_platform_2170",
                "ADISCORD_combat_platform_2183",
                "ADISCORD_combat_platform_2200",
                "ADISCORD_fighter_airframe_2163",
                "ADISCORD_cas_airframe_2170",
            ):
                self.assertIn(f"{tag}_{suffix}_entity", names)
            fighter = re.search(
                r'entity\s*=\s*\{[^{}]*name\s*=\s*"'
                + tag
                + r'_ADISCORD_fighter_airframe_2163_entity"[^{}]*\}',
                asset,
            )[0]
            cas = re.search(
                r'entity\s*=\s*\{[^{}]*name\s*=\s*"'
                + tag
                + r'_ADISCORD_cas_airframe_2170_entity"[^{}]*\}',
                asset,
            )[0]
            self.assertIn("_fighter_entity", fighter)
            self.assertIn("_cas_entity", cas)

    def test_air_roles_have_distinct_sprites_with_generic_fallbacks(self):
        units = (ROOT / "common/units/ADISCORD_air_units.txt").read_text()
        equipment = (
            ROOT / "common/units/equipment/ADISCORD_air_equipment.txt"
        ).read_text()
        assets = (ROOT / "gfx/entities/zz_ADISCORD_country_vehicles.asset").read_text()
        for role in ("fighter", "cas"):
            self.assertRegex(units, role + r"\s*=\s*\{\s*sprite = ADISCORD_" + role)
            block = equipment.split("ADISCORD_" + role + "_archetype = {", 1)[1].split(
                "\n\t}", 1
            )[0]
            self.assertIn("sprite = ADISCORD_" + role, block)
            self.assertIn(
                'clone = "ADISCORD_DEF_early_' + role + '_entity"',
                assets,
            )

    def test_packaging_is_idempotent(self):
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "country_vehicles_package", SOURCE / "package_vehicles.py"
        )
        package = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(package)
        self.assertEqual(package.package(apply=False), [])


class CasProgressionTests(unittest.TestCase):
    def test_nine_cas_exports_and_editable_sources_are_verified(self):
        source = ROOT / "tools/assets/source/country_cas"
        manifest = source / "verification.json"
        self.assertTrue(manifest.is_file(), "Three-tier CAS package has not been built")
        report = json.loads(manifest.read_text())
        expected = {
            f"{tag}_{prefix}cas"
            for tag in ("NOD", "STP", "VAL")
            for prefix in ("early_", "", "future_")
        }
        self.assertEqual(set(report), expected)
        hashes = set()
        for name, row in report.items():
            with self.subTest(name=name):
                self.assertTrue(row["native_reimport"])
                self.assertTrue(row["rigid_skin_slots_validated"])
                self.assertFalse(row["hoi4_runtime_verified"])
                self.assertGreater(row["triangles"], 500)
                self.assertLess(row["triangles"], 16000)
                self.assertEqual(row["materials"], 1)
                self.assertTrue({"root", "gun1", "gun2", "bomb"}.issubset(row["locators"]))
                self.assertLess(row["animation"]["loop_error"], 0.001)
                if "_early_" in name:
                    self.assertGreater(row["animation"]["max_vertex_motion"], 0.1)
                for filename, digest in row["files"].items():
                    self.assertEqual(hashlib.sha256((DEST / filename).read_bytes()).hexdigest(), digest)
                self.assertEqual(
                    hashlib.sha256((source / f"{name}.blend").read_bytes()).hexdigest(),
                    row["blend_sha256"],
                )
                hashes.add(row["files"][f"{name}.mesh"])
        self.assertEqual(len(hashes), 9)

    def test_cas_visual_levels_resolve_to_three_distinct_meshes(self):
        text = (ROOT / "gfx/entities/zz_ADISCORD_country_vehicles.asset").read_text()
        routes = {name: parent for parent, name in re.findall(
            r'entity = \{ clone = "([^"]+)" name = "([^"]+)" \}', text
        )}
        for tag, source in (("STP", "NOD"), ("NOD", "NOD"), ("STS", "STP"), ("VAL", "VAL")):
            for level, prefix in enumerate(("early_", "", "future_")):
                self.assertEqual(routes[f"{tag}_ADISCORD_cas_{level}_entity"],
                                 f"ADISCORD_{source}_{prefix}cas_entity")


class SharedAircraftTests(unittest.TestCase):
    def routes(self):
        text = (ROOT / "gfx/entities/zz_ADISCORD_country_vehicles.asset").read_text()
        return {
            name: parent
            for parent, name in re.findall(
                r'entity\s*=\s*\{\s*clone\s*=\s*"([^"]+)"\s*name\s*=\s*"([^"]+)"\s*\}', text
            )
        }

    def test_default_and_regional_families_cover_all_visual_levels(self):
        routes = self.routes()
        groups = {
            "": "DEF",
            "SHL": "ARB", "AZH": "ARB", "GLP": "ARB", "KDR": "ARB",
            "KYZ": "ARB", "MZR": "ARB", "RHM": "ARB", "SDR": "ARB", "SLF": "ARB",
            "WRK": "WRK", "DAN": "WRK", "EYR": "WRK", "EGC": "WRK",
            "RIV": "WRK", "YOR": "WRK", "ZAO": "WRK", "PWR": "WRK",
            "VLA": "WRK", "ROM": "WRK", "SOL": "WRK", "TRU": "WRK",
            "WCG": "WRK", "VAD": "WRK", "WKR": "WRK", "TVA": "WRK", "IBA": "WRK",
            "RUS": "RUS", "NAM": "NAM",
        }
        for tag, family in groups.items():
            for role in ("fighter", "cas"):
                for level, prefix in enumerate(("early_", "", "future_")):
                    name = f"{tag + '_' if tag else ''}ADISCORD_{role}_{level}_entity"
                    with self.subTest(name=name):
                        self.assertEqual(routes.get(name), f"ADISCORD_{family}_{prefix}{role}_entity")

    def test_cosmetic_names_preserve_the_regional_family(self):
        routes = self.routes()
        for tag in (
            "WRK_confederation", "WRK_vorkerland_technocracy",
            "VAD_vorkerland_restoration", "SOL_vorkerland_worker_protectorate",
            "ZAO_zaozersk_republic", "SLF_svetlogorsk_republic",
        ):
            family = "ARB" if tag.startswith("SLF_") else "WRK"
            self.assertEqual(
                routes.get(f"{tag}_ADISCORD_fighter_2_entity"),
                f"ADISCORD_{family}_future_fighter_entity",
            )
        for tag, family in (
            ("RUS_last_empire", "RUS"), ("RUS_black_banner_empire", "RUS"),
            ("RUS_restoration_state", "RUS"), ("NAM_confederation", "NAM"),
        ):
            self.assertEqual(routes.get(f"{tag}_ADISCORD_fighter_2_entity"),
                             f"ADISCORD_{family}_future_fighter_entity")

    def test_registered_minors_and_native_air_sprites_have_a_complete_fallback(self):
        from tools.assets.source.country_vehicles import package_vehicles as package
        from tools.assets.source.build_northern_infantry import ARAB_TAGS

        self.assertEqual(set(package.ARAB_TAGS), {"SHL", *ARAB_TAGS})
        routes = self.routes()
        families = package.country_families()
        history = (ROOT / "history/countries/WRK - WorkerLand.txt").read_text()
        subjects = re.findall(r'set_autonomy\s*=\s*\{\s*target\s*=\s*(\w+)', history)
        for tag in subjects:
            self.assertEqual(families[tag], "NAM" if tag == "NAM" else "WRK")
        self.assertEqual(families["BJK"], "DEF")
        self.assertEqual(families["APH"], "DEF")
        for tag, family in families.items():
            for sprite, role in (("light_plane", "fighter"), ("medium_plane", "cas")):
                for tier, prefix in enumerate(("early_", "", "future_")):
                    self.assertEqual(routes.get(f"{tag}_{sprite}_{tier}_entity"),
                                     f"ADISCORD_{family}_{prefix}{role}_entity")

    def test_shared_native_exports_match_the_installed_verification(self):
        path = ROOT / "docs/development/model-verification/aircraft_verification.json"
        self.assertTrue(path.is_file(), "Shared aircraft package has not been built")
        report = json.loads(path.read_text())
        hashes = set()
        for family in ("DEF", "ARB", "WRK", "RUS", "NAM"):
            for role in ("fighter", "cas"):
                for prefix in ("early_", "", "future_"):
                    name = f"{family}_{prefix}{role}"
                    row = report[name]
                    self.assertTrue(row["native_reimport"])
                    self.assertTrue(row["rigid_skin_slots_validated"])
                    self.assertLess(row["triangles"], 16000)
                    self.assertEqual(row["materials"], 1)
                    self.assertLess(row["animation"]["loop_error"], .001)
                    if prefix == "early_":
                        self.assertGreater(row["animation"]["max_vertex_motion"], .1)
                    for filename, expected in row["files"].items():
                        self.assertEqual(hashlib.sha256((DEST / filename).read_bytes()).hexdigest(), expected)
                    hashes.add(row["files"][name + ".mesh"])
        self.assertEqual(len(hashes), 30)


if __name__ == "__main__":
    unittest.main()
