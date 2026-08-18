from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
EFFECTS = ROOT / "common/scripted_effects/ADISCORD_STP_scripted_effects.txt"
DECISIONS = ROOT / "common/decisions/ADISCORD_STP_decisions.txt"
DYNAMIC_MODIFIERS = ROOT / "common/dynamic_modifiers/ADISCORD_dynamic_modifiers_STP.txt"
INLAY = ROOT / "common/focus_inlay_windows/ADISCORD_STP_state_face_inlay_window.txt"
SCRIPTED_LOC = ROOT / "common/scripted_localisation/ADISCORD_STP_scripted_loc.txt"
DECISION_LOC = ROOT / "localisation/russian/ADISCORD_STP_decisions_l_russian.yml"
HISTORY = ROOT / "history/countries/STP - StepanLand.txt"
ON_ACTIONS = ROOT / "common/on_actions/00_ADISCORD_on_actions.txt"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


def named_block(text: str, name: str) -> str:
    match = re.search(rf"(?m)^\s*{re.escape(name)}\s*=\s*\{{", text)
    if match is None:
        raise AssertionError(f"missing block: {name}")

    opening = text.find("{", match.start())
    depth = 0
    for index in range(opening, len(text)):
        if text[index] == "{":
            depth += 1
        elif text[index] == "}":
            depth -= 1
            if depth == 0:
                return text[match.start() : index + 1]
    raise AssertionError(f"unterminated block: {name}")


class STPCoreContractTests(unittest.TestCase):
    def test_suspicion_has_one_0_to_100_state_and_linear_pp_mapping(self) -> None:
        effects = read(EFFECTS)
        refresh = named_block(effects, "STP_refresh_party_suspicion")
        change = named_block(effects, "STP_change_party_suspicion")

        self.assertIn("var = STP_party_suspicion", refresh)
        self.assertIn("min = 0", refresh)
        self.assertIn("max = 100", refresh)
        self.assertIn("var = STP_sus_political_power_factor", refresh)
        self.assertIn("value = -0.007", refresh)
        self.assertIn("value = 0.35", refresh)
        self.assertIn("value = STP_party_suspicion_change", change)
        self.assertIn("STP_refresh_party_suspicion = yes", change)

        history = read(HISTORY)
        self.assertRegex(history, r"set_variable\s*=\s*\{\s*var\s*=\s*STP_party_suspicion\s+value\s*=\s*5\s*\}")
        self.assertNotIn("var = STP_sus_political_power_factor", history)

        modifier = named_block(read(DYNAMIC_MODIFIERS), "STP_party_suspicion_dynamic_modifier")
        self.assertIn("political_power_factor = STP_sus_political_power_factor", modifier)

    def test_health_has_one_discrete_five_stage_state_shared_with_inlay(self) -> None:
        effects = read(EFFECTS)
        refresh = named_block(effects, "STP_refresh_leader_health")
        setter = named_block(effects, "STP_set_leader_health_stage")

        self.assertIn("var = STP_leader_health_stage", refresh)
        self.assertIn("min = 1", refresh)
        self.assertIn("max = 5", refresh)
        for value in ("-0.05", "-0.10", "-0.20", "-0.30"):
            self.assertIn(f"value = {value}", refresh)
        self.assertIn("set_country_flag = STP_ivanov_dead", refresh)
        self.assertIn("clr_country_flag = STP_ivanov_dead", refresh)
        self.assertIn("value = STP_requested_health_stage", setter)
        self.assertIn("STP_refresh_leader_health = yes", setter)

        history = read(HISTORY)
        self.assertRegex(history, r"set_variable\s*=\s*\{\s*var\s*=\s*STP_leader_health_stage\s+value\s*=\s*1\s*\}")
        self.assertNotIn("var = STP_fading_father_stability_factor", history)

        inlay = read(INLAY)
        for stage in range(2, 6):
            self.assertIn(f"check_variable = {{ STP_leader_health_stage = {stage} }}", inlay)

        stability = named_block(read(DYNAMIC_MODIFIERS), "STP_fading_father")
        self.assertIn("stability_factor = STP_fading_father_stability_factor", stability)
        self.assertNotIn("political_power", stability)

    def test_runtime_has_no_abandoned_mirror_or_rate_variables(self) -> None:
        runtime_sources = "\n".join(
            read(path)
            for path in (
                EFFECTS,
                DECISIONS,
                DYNAMIC_MODIFIERS,
                INLAY,
                SCRIPTED_LOC,
                DECISION_LOC,
                HISTORY,
            )
        )
        for legacy in (
            "STP_party_suspicion_rate",
            "STP_leader_health_rate",
            "STP_leader_health_temp",
        ):
            with self.subTest(legacy=legacy):
                self.assertNotIn(legacy, runtime_sources)

        self.assertNotRegex(runtime_sources, r"\bvar\s*=\s*STP_state_face_stage\b")
        self.assertNotIn("check_variable = { STP_state_face_stage =", runtime_sources)

    def test_debug_decisions_replace_disposable_test_decision(self) -> None:
        decisions = read(DECISIONS)
        self.assertNotIn("STP_test = {", decisions)
        for decision in (
            "STP_debug_increase_suspicion",
            "STP_debug_decrease_suspicion",
            "STP_debug_worsen_ivanov",
            "STP_debug_improve_ivanov",
        ):
            self.assertIn(f"{decision} = {{", decisions)

        localisation = read(DECISION_LOC)
        for decision in (
            "STP_debug_increase_suspicion",
            "STP_debug_decrease_suspicion",
            "STP_debug_worsen_ivanov",
            "STP_debug_improve_ivanov",
        ):
            self.assertRegex(localisation, rf"(?m)^\s*{decision}:\s+\"§RDEBUG:§!")

    def test_startup_uses_one_core_initializer_for_mechanics_and_army_lock(self) -> None:
        effects = read(EFFECTS)
        initializer = named_block(effects, "STP_initialize_core_mechanics")
        self.assertIn("STP_refresh_party_suspicion = yes", initializer)
        self.assertIn("STP_refresh_leader_health = yes", initializer)
        self.assertIn("STP_party_suspicion_dynamic_modifier", initializer)
        self.assertIn("STP_fading_father", initializer)
        self.assertIn("ADISCORD_STP_lock_regular_army_templates = yes", initializer)

        startup = read(ON_ACTIONS)
        self.assertEqual(startup.count("STP_initialize_core_mechanics = yes"), 1)
        self.assertNotIn("ADISCORD_STP_lock_regular_army_templates = yes", startup)

    def test_scripted_localisation_is_limited_to_status_and_inlay_contracts(self) -> None:
        scripted_loc = read(SCRIPTED_LOC)
        for retained in (
            "STPGetSuspicionValue",
            "STPGetSuspicionBand",
            "STPGetSuspicionExplanation",
            "STP_display_party_suspicion",
            "STPGetStateFaceStageName",
            "STPGetStateFaceTooltip",
        ):
            self.assertIn(f"name = {retained}", scripted_loc)

        for removed in (
            "name = PeterHealth",
            "name = STPGetLeaderHealthStageName",
            "name = STPGetLeaderHealthTooltip",
        ):
            self.assertNotIn(removed, scripted_loc)


if __name__ == "__main__":
    unittest.main()
