from __future__ import annotations

import unittest

from tools.validators.validate_adiscord_vorkerland_focus_decisions import (
    CENTRAL_TARGETS,
    CORE_FOCUS_UNLOCK,
    CORE_PACKAGES,
    DECISION_FILE,
    EFFECT_FILE,
    LEVY_DECISIONS,
    ROOT,
    RUSSIAN_LOCALISATION,
    SUPPORT_DECISIONS,
    collect_issues,
    named_block,
    read,
)


class VorkerlandFocusDecisionTests(unittest.TestCase):
    def test_integrated_contract(self) -> None:
        self.assertEqual(collect_issues(), [])

    def test_named_minor_fronts_precede_shared_final_showdown(self) -> None:
        decisions = read(DECISION_FILE)
        effects = read(EFFECT_FILE)
        block = named_block(decisions, "ADISCORD_vorkerland_commit_to_central_showdown")
        effect = named_block(effects, "ADISCORD_vorkerland_focus_schedule_final_showdown")
        self.assertEqual(len(CENTRAL_TARGETS), 9)
        self.assertIn("country_event = { id = ADISCORD_vorkerland_phase.4 days = 1 }", effect)
        for target, decision_id in CENTRAL_TARGETS.items():
            minor = named_block(decisions, decision_id)
            launch = named_block(
                effects, f"ADISCORD_vorkerland_focus_launch_minor_{target.lower()}"
            )
            self.assertIn(f"any_neighbor_country = {{ tag = {target} }}", minor)
            self.assertIn("fire_only_once = no", minor)
            self.assertIn("ADISCORD_vorkerland_focus_central_minor_recovery_cooldown", minor)
            self.assertEqual(launch.count("declare_war_on = {"), 1)
            self.assertIn(f"target = {target}", launch)
        for forbidden in ("declare_war_on", "start_civil_war", "create_wargoal"):
            self.assertNotIn(forbidden, block)
            self.assertNotIn(forbidden, effect)

    def test_minor_fronts_have_one_retry_and_a_240_day_bound(self) -> None:
        decisions = read(DECISION_FILE)
        effects = read(EFFECT_FILE)
        deadline = named_block(
            decisions, "ADISCORD_vorkerland_focus_central_minor_front_deadline"
        )
        self.assertIn("days_mission_timeout = 240", deadline)
        self.assertIn(
            "ADISCORD_vorkerland_focus_resolve_central_minor_deadline = yes", deadline
        )
        first_check = named_block(
            effects, "ADISCORD_vorkerland_focus_confirm_central_minor_launch"
        )
        self.assertIn(
            "activate_mission = ADISCORD_vorkerland_focus_central_minor_retry_check",
            first_check,
        )
        retry_check = named_block(
            effects, "ADISCORD_vorkerland_focus_confirm_central_minor_retry"
        )
        self.assertIn("ADISCORD_vorkerland_focus_central_minor_recovery_cooldown", retry_check)
        self.assertIn("days = 14", retry_check)
        for target in CENTRAL_TARGETS:
            declaration = f"declare_war_on = {{ target = {target} type = annex_everything }}"
            self.assertEqual(effects.count(declaration), 2)

    def test_retreat_levies_are_two_weak_units_per_claimant_at_most(self) -> None:
        decisions = read(DECISION_FILE)
        effects = read(EFFECT_FILE)
        self.assertEqual(len(LEVY_DECISIONS), 6)
        self.assertEqual(effects.count("create_unit = {"), 6)
        for decision_id in LEVY_DECISIONS:
            self.assertIn("fire_only_once = yes", named_block(decisions, decision_id))
        self.assertNotIn("count =", effects)

    def test_core_restoration_is_explicit_disjoint_and_phase_gated(self) -> None:
        decisions = read(DECISION_FILE)
        states = [state for package in CORE_PACKAGES.values() for state in package]
        self.assertEqual(len(CORE_PACKAGES), 6)
        self.assertEqual(len(states), 41)
        self.assertEqual(len(states), len(set(states)))
        self.assertTrue(set(range(331, 341)).isdisjoint(states))
        self.assertNotIn("every_owned_state", decisions)
        for decision_id, package in CORE_PACKAGES.items():
            block = named_block(decisions, decision_id)
            self.assertIn("ADISCORD_vorkerland_phase_postwar_integration", block)
            self.assertIn("ADISCORD_vorkerland_reunification_verified", block)
            self.assertEqual(block.count(f"has_country_flag = {CORE_FOCUS_UNLOCK}"), 1)
            self.assertEqual(block.count("has_country_flag ="), 1)
            self.assertNotIn("set_country_flag =", block)
            self.assertNotRegex(block, r"\b(?:SOL|VLA)\s*=")
            for state in package:
                self.assertIn(f"owns_state = {state}", block)
                self.assertIn(f"controls_state = {state}", block)

    def test_allied_support_is_finite_and_cannot_create_relations(self) -> None:
        decisions = read(DECISION_FILE)
        effects = read(EFFECT_FILE)
        self.assertEqual(len(SUPPORT_DECISIONS), 4)
        for decision_id, (_, ally) in SUPPORT_DECISIONS.items():
            block = named_block(decisions, decision_id)
            self.assertIn("fire_only_once = yes", block)
            effect = named_block(effects, decision_id)
            for forbidden in ("add_to_faction", "create_faction", "puppet =", "set_autonomy"):
                self.assertNotIn(forbidden, effect)
            if ally == "VLA":
                self.assertGreaterEqual(
                    block.count("ADISCORD_vorkerland_wkr_vla_alliance_accepted"), 2
                )
                self.assertNotIn("ADISCORD_vorkerland_joined_worker_republic", block)
                self.assertNotIn("is_subject_of = ROOT", block)
            else:
                self.assertGreaterEqual(
                    block.count("ADISCORD_vorkerland_vad_sol_alliance_accepted"), 2
                )
                self.assertGreaterEqual(
                    block.count("ADISCORD_vorkerland_sol_restoration_verified"), 2
                )
                self.assertIn(
                    "OR = { is_in_faction_with = ROOT is_subject_of = ROOT }", block
                )

    def test_russian_localisation_keeps_utf8_bom(self) -> None:
        self.assertTrue((ROOT / RUSSIAN_LOCALISATION).read_bytes().startswith(b"\xef\xbb\xbf"))


if __name__ == "__main__":
    unittest.main()
