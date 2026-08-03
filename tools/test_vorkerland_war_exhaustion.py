from __future__ import annotations

import re
import unittest
from pathlib import Path

from tools.validate_adiscord_vorkerland_collapse import SECTIONS, named_block, validate


ROOT = Path(__file__).resolve().parents[1]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8-sig")


class VorkerlandWarExhaustionTests(unittest.TestCase):
    def test_validator_has_a_clean_exhaustion_section(self) -> None:
        self.assertIn("exhaustion", SECTIONS)
        self.assertEqual(validate(ROOT, "exhaustion"), [])

    def test_monthly_update_is_country_scoped_to_wrk_and_vad(self) -> None:
        on_actions = read("common/on_actions/01_ADISCORD_vorkerland_collapse_on_actions.txt")
        monthly = named_block(on_actions, "on_monthly")
        self.assertIn("tag = WRK", monthly)
        self.assertIn("tag = VAD", monthly)
        self.assertIn("ADISCORD_vorkerland_update_civil_war_exhaustion = yes", monthly)
        self.assertNotIn("every_country", monthly)
        self.assertNotIn("every_state", monthly)
        self.assertNotIn("on_daily", on_actions)

    def test_each_country_uses_new_casualties_and_duration_once_per_month(self) -> None:
        effects = read("common/scripted_effects/ADISCORD_vorkerland_collapse_effects.txt")
        update = named_block(effects, "ADISCORD_vorkerland_update_civil_war_exhaustion")
        self.assertIn("ADISCORD_vorkerland_civil_war_casualties_snapshot_k", update)
        self.assertIn("value = casualties_k", update)
        self.assertIn(
            "value = ADISCORD_vorkerland_civil_war_casualties_snapshot_k",
            update,
        )
        self.assertIn("has_war_with = VAD", update)
        self.assertIn("has_war_with = WRK", update)
        self.assertRegex(
            update,
            r"add_to_variable\s*=\s*\{\s*var\s*=\s*ADISCORD_vorkerland_civil_war_exhaustion\s*value\s*=\s*2\s*\}",
        )
        for threshold, gain in ((100, 6), (25, 3), (5, 1)):
            self.assertRegex(
                update,
                rf"(?s)ADISCORD_vorkerland_civil_war_casualties_delta_k\s+value\s*=\s*{threshold}\b.*?"
                rf"ADISCORD_vorkerland_civil_war_exhaustion\s+value\s*=\s*{gain}\b",
            )

    def test_peace_recovers_score_and_all_values_are_clamped(self) -> None:
        effects = read("common/scripted_effects/ADISCORD_vorkerland_collapse_effects.txt")
        update = named_block(effects, "ADISCORD_vorkerland_update_civil_war_exhaustion")
        self.assertRegex(
            update,
            r"ADISCORD_vorkerland_civil_war_exhaustion\s+value\s*=\s*-8\b",
        )
        self.assertRegex(
            update,
            r"clamp_variable\s*=\s*\{\s*var\s*=\s*ADISCORD_vorkerland_civil_war_exhaustion\s+min\s*=\s*0\s+max\s*=\s*100\s*\}",
        )
        self.assertRegex(
            update,
            r"clamp_variable\s*=\s*\{\s*var\s*=\s*ADISCORD_vorkerland_civil_war_casualties_delta_k\s+min\s*=\s*0\s+max\s*=\s*10000\s*\}",
        )

    def test_one_modifier_scales_without_attack_or_organisation_penalties(self) -> None:
        dynamic = read(
            "common/dynamic_modifiers/ADISCORD_vorkerland_collapse_dynamic_modifiers.txt"
        )
        modifier = named_block(dynamic, "ADISCORD_vorkerland_civil_war_exhaustion")
        for key in (
            "war_support_factor",
            "stability_factor",
            "industrial_capacity_factory",
            "army_morale_factor",
            "surrender_limit",
        ):
            self.assertIn(key, modifier)
        self.assertNotIn("factory_output =", modifier)
        self.assertNotIn("army_attack_factor", modifier)
        self.assertNotIn("army_org_factor", modifier)

        effects = read("common/scripted_effects/ADISCORD_vorkerland_collapse_effects.txt")
        refresh = named_block(effects, "ADISCORD_vorkerland_refresh_civil_war_exhaustion")
        for coefficient in ("-0.002", "-0.001", "-0.0005"):
            self.assertIn(f"value = {coefficient}", refresh)
        self.assertIn("force_update_dynamic_modifier = yes", refresh)
        self.assertIn("remove_dynamic_modifier", refresh)

    def test_debug_controls_are_player_only_and_refresh_or_reset(self) -> None:
        categories = read(
            "common/decisions/categories/ADISCORD_scenario_debug_categories.txt"
        )
        category = named_block(categories, "ADISCORD_scenario_debug_category")
        self.assertIn("visible = { is_debug = yes }", category)
        decisions = read("common/decisions/ADISCORD_scenario_debug_decisions.txt")
        add = named_block(decisions, "ADISCORD_debug_add_vorkerland_war_exhaustion")
        reset = named_block(decisions, "ADISCORD_debug_reset_vorkerland_war_exhaustion")
        for block in (add, reset):
            self.assertIn("tag = WRK", block)
            self.assertIn("tag = VAD", block)
            self.assertIn("ai_will_do = { factor = 0 }", block)
        self.assertIn("value = 25", add)
        self.assertIn("ADISCORD_vorkerland_refresh_civil_war_exhaustion = yes", add)
        self.assertIn("ADISCORD_vorkerland_reset_civil_war_exhaustion = yes", reset)

    def test_russian_localisation_is_bom_safe_and_shows_own_score(self) -> None:
        collapse_path = ROOT / "localisation/russian/ADISCORD_vorkerland_collapse_l_russian.yml"
        debug_path = ROOT / "localisation/russian/ADISCORD_scenario_debug_l_russian.yml"
        self.assertTrue(collapse_path.read_bytes().startswith(b"\xef\xbb\xbf"))
        self.assertTrue(debug_path.read_bytes().startswith(b"\xef\xbb\xbf"))
        collapse = collapse_path.read_text(encoding="utf-8-sig")
        debug = debug_path.read_text(encoding="utf-8-sig")
        self.assertIn("ADISCORD_vorkerland_civil_war_exhaustion:", collapse)
        self.assertIn("[?ADISCORD_vorkerland_civil_war_exhaustion|0]/100", collapse)
        self.assertIn("§RDEBUG:§!", debug)
        self.assertIn("ADISCORD_debug_add_vorkerland_war_exhaustion:", debug)
        self.assertIn("ADISCORD_debug_reset_vorkerland_war_exhaustion:", debug)


if __name__ == "__main__":
    unittest.main()
