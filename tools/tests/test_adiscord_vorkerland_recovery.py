from __future__ import annotations

import re
import unittest
from pathlib import Path

from tools.validators.validate_adiscord_vorkerland_recovery import (
    PLAYER_PREFERENCE_FLAGS,
    collect_issues,
    event_block,
    named_block,
    named_blocks,
    validate_bounded_retry,
    validate_new_save_materialization,
    validate_retired_legacy_events,
    validate_phase_controller,
    validate_reunification_formation,
    validate_wkr_semantics,
)


ROOT = Path(__file__).resolve().parents[2]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8-sig")


def issue_report(issues: list[str]) -> str:
    return "\n" + "\n".join(f"- {issue}" for issue in issues)


class RecoveryValidatorHelperTests(unittest.TestCase):
    def test_structural_helpers_follow_balanced_blocks(self) -> None:
        source = """
outer = {
    inner = { token = yes }
}
country_event = {
    id = ADISCORD_vorkerland_phase.5
    immediate = { token = yes }
}
"""
        self.assertIn("inner = { token = yes }", named_block(source, "outer"))
        self.assertIn(
            "immediate = { token = yes }",
            event_block(source, "ADISCORD_vorkerland_phase.5"),
        )

    def test_multiline_wrk_scope_exposes_the_nested_prewar_setter(self) -> None:
        startup = """
on_startup = {
    effect = {
        if = {
            limit = { WRK = { exists = yes } }
            WRK = {
                ADISCORD_vorkerland_set_phase_prewar = yes
                country_event = { id = ADISCORD_vorkerland_phase.1 }
            }
        }
    }
}
"""
        wrk_scopes = named_blocks(startup, "WRK")
        self.assertTrue(
            any(
                "ADISCORD_vorkerland_set_phase_prewar = yes" in scope
                for scope in wrk_scopes
            )
        )


class WkrTagSemanticTests(unittest.TestCase):
    def test_wkr_tag_country_flags_and_names(self) -> None:
        issues = validate_wkr_semantics()
        self.assertEqual(issues, [], issue_report(issues))


class NewSaveMaterializationTests(unittest.TestCase):
    def test_atomic_split_handoff_annex_and_strict_postconditions(self) -> None:
        issues = validate_new_save_materialization()
        self.assertEqual(issues, [], issue_report(issues))

    def test_startup_choice_selects_control_then_invokes_atomic_collapse(self) -> None:
        phase_events = read("events/ADISCORD_vorkerland_phase_events.txt")
        choice = event_block(phase_events, "ADISCORD_vorkerland_phase.1")
        self.assertIn("fire_only_once = yes", choice)
        choice_trigger = named_block(choice, "trigger")
        self.assertIn("tag = WRK", choice_trigger)
        self.assertIn("ADISCORD_vorkerland_collapse_not_started = yes", choice_trigger)

        options = named_blocks(choice, "option")
        self.assertEqual(len(options), 3)
        collapse_dispatch = "country_event = { id = ADISCORD_vorkerland_collapse.1 }"
        for option, selected_flag in zip(options, PLAYER_PREFERENCE_FLAGS):
            for preference_flag in PLAYER_PREFERENCE_FLAGS:
                self.assertEqual(
                    option.count(f"clr_global_flag = {preference_flag}"),
                    1,
                    preference_flag,
                )
            self.assertEqual(option.count(f"set_global_flag = {selected_flag}"), 1)
            self.assertEqual(option.count(collapse_dispatch), 1)

        startup = named_block(
            read("common/on_actions/01_ADISCORD_vorkerland_collapse_on_actions.txt"),
            "on_startup",
        )
        delayed_choices = [
            block
            for block in named_blocks(startup, "country_event")
            if "id = ADISCORD_vorkerland_phase.1" in block
        ]
        self.assertEqual(len(delayed_choices), 1)
        self.assertIn("days = 120", delayed_choices[0])
        self.assertIn("random_days = 60", delayed_choices[0])
        direct_collapses = [
            block
            for block in named_blocks(startup, "country_event")
            if re.search(r"\bid\s*=\s*ADISCORD_vorkerland_collapse\.1\b", block)
        ]
        self.assertEqual(direct_collapses, [])

    def test_human_handoff_is_exact_ai_safe_and_clears_preferences_before_annex(self) -> None:
        collapse_events = read("events/ADISCORD_vorkerland_collapse_events.txt")
        collapse = event_block(collapse_events, "ADISCORD_vorkerland_collapse.1")
        immediate = named_block(collapse, "immediate")
        handoffs = [
            block
            for block in named_blocks(immediate, "if")
            if "limit = { is_ai = no }" in block and "change_tag_from = WRK" in block
        ]
        self.assertEqual(len(handoffs), 1)
        handoff = handoffs[0]
        for claimant in ("WKR", "VAD", "TVA"):
            self.assertEqual(handoff.count(f"{claimant} = {{ change_tag_from = WRK }}"), 1)
        self.assertEqual(immediate.count("change_tag_from = WRK"), 3)

        worker_branches = [
            block
            for block in named_blocks(handoff, "if")
            if "ADISCORD_vorkerland_preference_worker" in named_block(block, "limit")
            and "WKR = { change_tag_from = WRK }" in block
        ]
        self.assertEqual(len(worker_branches), 1)
        worker_limit = named_block(worker_branches[0], "limit")
        self.assertIn("has_global_flag = ADISCORD_vorkerland_preference_worker", worker_limit)
        for preference_flag in PLAYER_PREFERENCE_FLAGS:
            self.assertIn(f"NOT = {{ has_global_flag = {preference_flag} }}", worker_limit)

        handoff_end = immediate.find(handoff) + len(handoff)
        annex_position = immediate.find("annex_country = {", handoff_end)
        self.assertGreater(annex_position, handoff_end)
        for preference_flag in PLAYER_PREFERENCE_FLAGS:
            clear_position = immediate.find(f"clr_global_flag = {preference_flag}")
            self.assertGreater(clear_position, handoff_end)
            self.assertLess(clear_position, annex_position)

        fate_rolls = [
            block
            for block in named_blocks(immediate, "random_list")
            if "ADISCORD_vorkerland_worker_safe_with_loyalists" in block
        ]
        self.assertEqual(len(fate_rolls), 1)
        for preference_flag in PLAYER_PREFERENCE_FLAGS:
            self.assertNotIn(preference_flag, fate_rolls[0])

    def test_choice_localisation_explains_control_only_and_names_vlad_and_armi(self) -> None:
        english = read("localisation/english/ADISCORD_vorkerland_recovery_l_english.yml")
        russian_path = ROOT / "localisation/russian/ADISCORD_vorkerland_recovery_l_russian.yml"
        russian = russian_path.read_text(encoding="utf-8-sig")
        for fragment in ("country controlled by the player", "Worker's fate", "Vlad and Armi"):
            self.assertIn(fragment, english)
        for fragment in ("только страну под управлением игрока", "судьба Уоркера", "Влада и Арми"):
            self.assertIn(fragment, russian)
        self.assertTrue(russian_path.read_bytes().startswith(b"\xef\xbb\xbf"))


class PhaseControllerTests(unittest.TestCase):
    def test_exact_seven_phase_and_wartime_claimant_contract(self) -> None:
        issues = validate_phase_controller()
        self.assertEqual(issues, [], issue_report(issues))

    def test_startup_bridge_restores_three_trees_and_one_wkr_phase_two_check(self) -> None:
        on_actions = read("common/on_actions/01_ADISCORD_vorkerland_collapse_on_actions.txt")
        startup = named_block(on_actions, "on_startup")
        bridge_flag = "ADISCORD_vorkerland_materialization_bridge_v1_scheduled"
        focus_tree_load = (
            "load_focus_tree = { tree = ADISCORD_vorkerland_civil_war_focus "
            "keep_completed = yes }"
        )
        bridges = [
            block
            for block in named_blocks(startup, "if")
            if f"set_global_flag = {bridge_flag}" in block
            and focus_tree_load in block
        ]
        self.assertEqual(len(bridges), 1)
        bridge = bridges[0]
        bridge_limit = named_block(bridge, "limit")
        for token in (
            "has_global_flag = ADISCORD_vorkerland_collapse_wars_started",
            "NOT = { has_global_flag = ADISCORD_vorkerland_collapse_finished }",
            "NOT = { has_global_flag = ADISCORD_vorkerland_collapse_materialized_verified }",
            f"NOT = {{ has_global_flag = {bridge_flag} }}",
            "country_exists = WKR",
            "country_exists = VAD",
            "country_exists = TVA",
            "NOT = { country_exists = WRK }",
        ):
            self.assertIn(token, bridge_limit)
        self.assertEqual(bridge.count(f"set_global_flag = {bridge_flag}"), 1)

        phase_two = "country_event = { id = ADISCORD_vorkerland_phase.2 days = 1 }"
        for claimant in ("WKR", "VAD", "TVA"):
            scopes = [
                scope
                for scope in named_blocks(bridge, claimant)
                if focus_tree_load in scope
            ]
            self.assertEqual(len(scopes), 1, claimant)
            claimant_scope = scopes[0]
            self.assertIn(focus_tree_load, claimant_scope)
            self.assertIn("focus_unlock = yes", claimant_scope)
            self.assertIn("mark_focus_tree_layout_dirty = yes", claimant_scope)
            if claimant == "WKR":
                self.assertIn(phase_two, claimant_scope)
            else:
                self.assertNotIn(phase_two, claimant_scope)
        self.assertEqual(bridge.count(focus_tree_load), 3)
        self.assertEqual(bridge.count(phase_two), 1)


class BoundedRetryTests(unittest.TestCase):
    def test_three_required_edges_launch_together_and_are_postcondition_driven(self) -> None:
        issues = validate_bounded_retry()
        self.assertEqual(issues, [], issue_report(issues))


class ReunificationFormationTests(unittest.TestCase):
    def test_winner_forms_wrk_only_after_loser_subject_release(self) -> None:
        issues = validate_reunification_formation()
        self.assertEqual(issues, [], issue_report(issues))


class RetiredLegacyEventTests(unittest.TestCase):
    def test_old_save_scheduler_events_are_removed(self) -> None:
        issues = validate_retired_legacy_events()
        self.assertEqual(issues, [], issue_report(issues))


class VorkerlandRecoveryValidatorTests(unittest.TestCase):
    def test_integrated_recovery_contract(self) -> None:
        issues = collect_issues()
        self.assertEqual(issues, [], issue_report(issues))


if __name__ == "__main__":
    unittest.main()
