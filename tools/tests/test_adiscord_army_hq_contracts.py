from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8-sig")


def named_block(text: str, name: str) -> str:
    match = re.search(rf"(?m)^\s*{re.escape(name)}\s*=\s*\{{", text)
    if match is None:
        raise AssertionError(f"Missing block {name}")
    start = match.start()
    opening = text.find("{", match.start())
    depth = 0
    for index in range(opening, len(text)):
        if text[index] == "{":
            depth += 1
        elif text[index] == "}":
            depth -= 1
            if depth == 0:
                return text[start : index + 1]
    raise AssertionError(f"Unclosed block {name}")


def division_template_block(text: str, template_name: str) -> str:
    for match in re.finditer(r"(?m)^\s*division_template\s*=\s*\{", text):
        start = match.start()
        opening = text.find("{", match.start())
        depth = 0
        for index in range(opening, len(text)):
            if text[index] == "{":
                depth += 1
            elif text[index] == "}":
                depth -= 1
                if depth == 0:
                    block = text[start : index + 1]
                    if f'name = "{template_name}"' in block:
                        return block
                    break
    raise AssertionError(f"Missing division template {template_name}")


class ArmyHeadquartersContractTests(unittest.TestCase):
    def test_total_conversion_restores_engine_facing_hq_units(self) -> None:
        units = read("common/units/ADISCORD_army_hq_units.txt")
        expected = {
            "hq_support_company",
            "hq_engineer",
            "hq_recon",
            "hq_military_police",
            "hq_maintenance",
            "hq_field_hospital",
            "hq_logistics",
            "hq_signal",
            "hq_naval_liaison",
            "hq_air_liaison",
            "hq_specops",
            "hq_infantry",
            "hq_paratrooper",
            "hq_light_armor",
            "hq_medium_armor",
            "hq_heavy_armor",
        }
        for subunit in expected:
            with self.subTest(subunit=subunit):
                block = named_block(units, subunit)
                self.assertIn("allow_in_army_hq = yes", block)
                self.assertIn("allow_in_non_army_hq = no", block)
                self.assertIn('required_dlc = { "Thunder at Our Gates" }', block)

        self.assertIn("active = yes", named_block(units, "hq_support_company"))
        self.assertIn("active = yes", named_block(units, "hq_infantry"))
        self.assertNotIn("motorized_equipment", units)
        self.assertNotIn("tank_chassis", units)

    def test_every_country_receives_a_dlc_gated_starter_template(self) -> None:
        template = read("history/general/ADISCORD_army_hq_template.txt")
        self.assertIn("every_possible_country = {", template)
        self.assertIn('has_dlc = "Thunder at Our Gates"', template)
        self.assertIn("is_army_hq = yes", template)
        self.assertEqual(template.count("hq_infantry = {"), 2)
        self.assertEqual(template.count("hq_support_company = {"), 1)

    def test_ai_is_allowed_to_deploy_and_design_hqs(self) -> None:
        defines = read("common/defines/ADISCORD_defines_changes.lua")
        self.assertRegex(defines, r"MAX_DEPLOYED_ARMY_HQS\s*=\s*[1-9]\d*")
        self.assertRegex(
            defines,
            r"MAX_CAPTURED_GENERALS_TO_STOP_HQ_DEPLOY\s*=\s*[2-9]\d*",
        )

        templates = read("common/ai_templates/ADISCORD_land_templates.txt")
        hq_ai = named_block(templates, "ADISCORD_army_hq_templates")
        self.assertIn("role = hq_role", hq_ai)
        self.assertIn("hq_support_company = 1", hq_ai)
        self.assertIn("hq_infantry = 2", hq_ai)

    def test_generated_technology_tree_unlocks_hq_modules(self) -> None:
        generated = "\n".join(
            read(relative)
            for relative in (
                "common/technologies/ADISCORD_infantry.txt",
                "common/technologies/ADISCORD_logistics_trains.txt",
                "common/technologies/ADISCORD_electronics.txt",
                "common/technologies/ADISCORD_armor.txt",
            )
        )
        expected_unlocks = {
            "ADISCORD_tech_combat_engineering_sections": "hq_engineer",
            "ADISCORD_tech_fieldcraft_manuals": "hq_recon",
            "ADISCORD_tech_reconstituted_staff_academies": "hq_military_police",
            "ADISCORD_tech_standardized_field_tool_chests": "hq_maintenance",
            "ADISCORD_tech_frequency_hopping_field_sets": "hq_signal",
            "ADISCORD_tech_casualty_evacuation": "hq_field_hospital",
            "ADISCORD_tech_forward_supply_hubs": "hq_logistics",
            "ADISCORD_tech_vertical_assault_training": "hq_paratrooper",
            "ADISCORD_tech_drone_recon_swarms": "hq_light_armor",
            "ADISCORD_tech_semi_autonomous_combat_modules": "hq_medium_armor",
            "ADISCORD_tech_heavy_platform_cores": "hq_heavy_armor",
        }
        for technology, subunit in expected_unlocks.items():
            with self.subTest(technology=technology, subunit=subunit):
                block = named_block(generated, technology)
                unlock = named_block(block, "enable_subunits")
                self.assertRegex(unlock, rf"\b{re.escape(subunit)}\b")

    def test_stp_removed_army_restriction_has_no_runtime_hooks(self) -> None:
        restriction_effect = ROOT / "common/scripted_effects/ADISCORD_STP_army_restriction_effects.txt"
        self.assertFalse(restriction_effect.exists())

        oob = read("history/units/STP.txt")
        for template_name in ("Police division", "Regular army"):
            with self.subTest(template=template_name):
                template = division_template_block(oob, template_name)
                self.assertNotIn("is_locked = yes", template)
                self.assertNotIn("force_allow_recruiting = no", template)

        guard = division_template_block(oob, "Capital Guard")
        self.assertIn("division_cap = 1", guard)
        self.assertIn("is_locked = yes", guard)
        self.assertIn("force_allow_recruiting = no", guard)

        idea = named_block(read("common/ideas/steland.txt"), "STP_hedonism_with_no_bondaries")
        self.assertNotIn("STP_hedonism_army_restriction_tt", idea)
        self.assertNotIn("ADISCORD_STP_unlock_regular_army_templates", idea)

        startup = named_block(
            read("common/on_actions/00_ADISCORD_on_actions.txt"), "on_startup"
        )
        self.assertNotIn("ADISCORD_STP_lock_regular_army_templates", startup)


if __name__ == "__main__":
    unittest.main()
