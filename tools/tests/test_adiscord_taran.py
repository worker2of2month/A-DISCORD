"""Shabrat's native siege-project, production and presentation contracts."""

import hashlib
import json
from pathlib import Path
import re
import unittest

from tools.builders import build_adiscord_technology_system as technologies
from tools.tests.test_adiscord_combat_robots import read_script, value, named_blocks


ROOT = Path(__file__).resolve().parents[2]
PROJECT = "STP_sp_taran"
UNIT = "STP_taran"
EQUIPMENT = "STP_taran_equipment"
FOCUS = "STP_pw_republic_shield_corps"


class TaranTests(unittest.TestCase):
    def test_native_project_belongs_to_the_postwar_shabrat_recipient(self):
        projects = read_script("common/special_projects/projects/land_projects.txt")
        self.assertIn(PROJECT, {entry.key for entry in projects})
        project = value(projects, PROJECT)
        self.assertEqual(value(value(project, "allowed"), "tag"), "STS")
        self.assertEqual(len(value(project, "allowed")), 1)
        visible = value(value(project, "visible"), "FROM")
        self.assertEqual(value(visible, "has_completed_focus"), FOCUS)
        available = value(value(project, "available"), "FROM")
        self.assertEqual(value(available, "has_capitulated"), "no")
        required = [entry.value for entry in available if entry.key == "has_tech"]
        self.assertEqual(set(required), {
            "ADISCORD_tech_hardened_computers", "ADISCORD_tech_automated_assembly",
            "ADISCORD_tech_heavy_composite_cores",
        })
        for tech in technologies.technology_prerequisite_closure(required):
            self.assertIn(tech, technologies.TECH_POSITION_BY_ID)
        self.assertEqual(value(project, "specialization"), "specialization_land")
        self.assertEqual(value(project, "prototype_time"), "sp_time.prototype.long")
        self.assertEqual(value(project, "complexity"), "sp_complexity.large")
        self.assertEqual(value(value(project, "breakthrough_cost"), "specialization_land"), "2")

    def test_completion_unlocks_production_and_gives_only_one_inventory_prototype(self):
        projects = read_script("common/special_projects/projects/land_projects.txt")
        self.assertIn(PROJECT, {entry.key for entry in projects})
        output = value(value(projects, PROJECT), "project_output")
        self.assertEqual([entry.value for entry in value(output, "enable_equipments")], [EQUIPMENT + "_1"])
        self.assertEqual([entry.value for entry in value(output, "enable_subunits")], [UNIT])
        self.assertEqual(value(value(output, "country_effects"), "STP_taran_complete_project"), "yes")
        effects = read_script("common/scripted_effects/ADISCORD_STP_scripted_effects.txt")
        completion = value(effects, "STP_taran_complete_project")
        stock = value(completion, "add_equipment_to_stockpile")
        self.assertEqual(value(stock, "type"), EQUIPMENT + "_1")
        self.assertEqual(value(stock, "amount"), "1")
        self.assertEqual(value(stock, "producer"), "ROOT")
        self.assertNotIn("create_unit", repr(completion))
        self.assertNotIn("add_equipment_production", repr(completion))
        template_guard = value(value(completion, "hidden_effect"), "if")
        template = value(template_guard, "division_template")
        self.assertEqual(value(template, "is_locked"), "no")
        self.assertEqual(value(value(value(template_guard, "limit"), "NOT"), "has_template"),
                         value(template, "name"))
        regiments = value(template, "regiments")
        self.assertEqual([entry.key for entry in regiments].count(UNIT), 1)
        self.assertEqual([entry.key for entry in regiments].count("ADISCORD_urban_breacher"), 4)
        self.assertIn("engineer", {entry.key for entry in value(template, "support")})
        for equipment in technologies.ENABLE_EQUIPMENT.values():
            self.assertNotIn(EQUIPMENT + "_1", equipment)

    def test_paid_battalion_has_real_siege_strengths_and_logistical_limits(self):
        units = value(read_script("common/units/ADISCORD_land_units.txt"), "sub_units")
        self.assertIn(UNIT, {entry.key for entry in units})
        unit = value(units, UNIT)
        self.assertEqual(value(unit, "active"), "no")
        self.assertEqual(value(unit, "sprite"), UNIT)
        need = {entry.key: int(entry.value) for entry in value(unit, "need")}
        self.assertEqual(need, {EQUIPMENT: 24, "support_equipment": 30})
        self.assertEqual(float(value(unit, "combat_width")), 3)
        self.assertEqual(float(value(unit, "manpower")), 480)
        self.assertEqual(float(value(unit, "supply_consumption")), .60)
        self.assertGreater(float(value(value(unit, "urban"), "attack")), 0)
        self.assertGreater(float(value(value(unit, "fort"), "attack")), 0)
        for terrain in ("mountain", "marsh"):
            self.assertLess(float(value(value(unit, terrain), "attack")), -.4)
            self.assertLess(float(value(value(unit, terrain), "movement")), -.4)
        equipment = value(read_script("common/units/equipment/ADISCORD_armor_equipment.txt"), "equipments")
        archetype = value(equipment, EQUIPMENT)
        variant = value(equipment, EQUIPMENT + "_1")
        self.assertEqual(value(archetype, "is_buildable"), "no")
        self.assertEqual(value(variant, "active"), "no")
        self.assertEqual(value(variant, "archetype"), EQUIPMENT)
        self.assertEqual(float(value(archetype, "maximum_speed")), 4)
        self.assertEqual(float(value(archetype, "build_cost_ic")) * need[EQUIPMENT], 1560)
        resources = {entry.key: int(entry.value) for entry in value(archetype, "resources")}
        self.assertGreater(resources["rare_alloys"], 0)
        self.assertGreater(resources["rare_components"], 0)
        equipment_enum = value(read_script("common/script_enums.txt"), "script_enum_equipment_bonus_type")
        self.assertTrue({EQUIPMENT, EQUIPMENT + "_1"} <= {entry.value for entry in equipment_enum})

    def test_focus_advertises_the_project_without_skipping_research(self):
        source = (ROOT / "focus_trees/STP/postwar/shabrat/focuses.txt").read_text(encoding="utf-8-sig")
        roots = read_script("common/national_focus/ADISCORD_STP_civil_war.txt")
        tree = value(roots, "focus_tree")
        focus = next(entry.value for entry in tree if entry.key == "focus" and value(entry.value, "id") == FOCUS)
        reward = value(focus, "completion_reward")
        self.assertIn("STP_taran_project_unlocked_tt", source)
        self.assertIn("STP_taran_project_unlocked_tt", repr(reward))
        self.assertNotIn("complete_special_project", repr(reward))
        self.assertNotIn(EQUIPMENT, repr(reward))

    def test_country_localisation_has_bom_and_complete_quoted_values(self):
        required = {PROJECT, PROJECT + "_desc", UNIT, UNIT + "_desc",
                    "STP_taran_project_unlocked_tt", "STP_taran_template_tt"}
        for equipment in (EQUIPMENT, EQUIPMENT + "_1"):
            required.update({equipment, equipment + "_short", equipment + "_desc"})
        for language in ("russian", "english"):
            path = ROOT / f"localisation/{language}/ADISCORD_STP_l_{language}.yml"
            self.assertTrue(path.read_bytes().startswith(b"\xef\xbb\xbf"))
            matches = {}
            for line in path.read_text(encoding="utf-8-sig").splitlines():
                key = re.match(r'\s*([A-Za-z0-9_]+):', line)
                if key and key[1] in required:
                    self.assertRegex(line, r'^ [A-Za-z0-9_]+:0 "(?:[^"\\]|\\.)+"$')
                    self.assertNotIn(key[1], matches)
                    matches[key[1]] = line
            self.assertEqual(set(matches), required)

    def test_native_skeleton_fits_the_engine_limit_and_matches_its_animations(self):
        folder = ROOT / "gfx/models/units/ADISCORD_country_vehicles"
        report = json.loads((folder / "STS_taran_verification.json").read_text())
        self.assertLessEqual(report["bones"], 50)
        self.assertTrue(report["native_reimport"])
        self.assertEqual(set(report["animations"]), {"idle", "move", "attack"})
        for clip, metrics in report["animations"].items():
            self.assertLess(metrics["loop_error"], .001, clip)
            if clip != "idle":
                self.assertGreater(metrics["max_vertex_motion"], .10, clip)
        for name, expected in report["files"].items():
            self.assertEqual(hashlib.sha256((folder / name).read_bytes()).hexdigest(), expected)

    def test_native_model_and_ui_icons_exist(self):
        entities = named_blocks(read_script("gfx/entities/zz_ADISCORD_country_vehicles.asset"), "entity")
        self.assertIn(UNIT + "_entity", entities)
        for tag in ("STS", "STS_steland", "STS_hegemony"):
            self.assertIn(f"{tag}_{UNIT}_entity", entities)
        self.assertEqual(value(entities[UNIT + "_entity"], "clone"), "ADISCORD_STS_taran_entity")
        mesh = ROOT / "gfx/models/units/ADISCORD_country_vehicles/STS_taran.mesh"
        self.assertTrue(mesh.is_file())
        sprites = named_blocks(value(read_script("interface/ADISCORD_subuniticons.gfx"), "spriteTypes"), "spriteType")
        for name in ("GFX_STP_taran_project", "GFX_STP_taran_equipment_medium",
                     "GFX_unit_STP_taran_icon_medium", "GFX_unit_STP_taran_icon_medium_white",
                     "GFX_unit_STP_taran_icon_small"):
            self.assertIn(name, sprites)
            path = value(sprites[name], "texturefile")
            self.assertTrue((ROOT / path).is_file(), path)


if __name__ == "__main__":
    unittest.main()
