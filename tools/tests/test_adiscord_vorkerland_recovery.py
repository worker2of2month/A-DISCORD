from __future__ import annotations

import re
import unittest
from pathlib import Path

from tools.validators.validate_adiscord_vorkerland_recovery import (
    PHASE_FLAGS,
    PLAYER_PREFERENCE_FLAGS,
    collect_issues,
    event_block,
    event_blocks,
    named_block,
    named_blocks,
    validate_bounded_retry,
    validate_new_save_materialization,
    validate_premature_wrk_recovery,
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

    def test_wars_wait_for_structure_and_a_completed_identity_assertion(self) -> None:
        collapse_events = read("events/ADISCORD_vorkerland_collapse_events.txt")
        outbreak = event_block(collapse_events, "ADISCORD_vorkerland_collapse.2")
        outbreak_trigger = named_block(outbreak, "trigger")
        for token in (
            "has_global_flag = ADISCORD_vorkerland_collapse_materialized_verified",
            "ADISCORD_vorkerland_collapse_materialized = yes",
            "has_global_flag = ADISCORD_vorkerland_claimant_identity_assertion_started_v2",
        ):
            self.assertIn(token, outbreak_trigger)

        collapse = event_block(collapse_events, "ADISCORD_vorkerland_collapse.1")
        immediate = named_block(collapse, "immediate")
        self.assertNotIn(
            "country_event = { id = ADISCORD_vorkerland_collapse.2 days = 1 }",
            immediate,
        )

        phase_effects = read("common/scripted_effects/ADISCORD_vorkerland_phase_effects.txt")
        verifier = named_block(
            phase_effects, "ADISCORD_vorkerland_verify_collapse_materialized"
        )
        self.assertEqual(
            verifier.count(
                "country_event = { id = ADISCORD_vorkerland_collapse.2 days = 1 }"
            ),
            1,
        )
        self.assertNotIn(
            "ADISCORD_vorkerland_claimant_identities_materialized = yes",
            outbreak_trigger,
        )

    def test_bounded_materialization_repair_is_complete_and_war_safe(self) -> None:
        phase_effects = read("common/scripted_effects/ADISCORD_vorkerland_phase_effects.txt")
        repair = named_block(
            phase_effects, "ADISCORD_vorkerland_repair_collapse_materialization"
        )
        self.assertIn(
            "NOT = { has_global_flag = ADISCORD_vorkerland_collapse_wars_started }",
            repair,
        )
        for tag, states in {
            "WKR": (32, 33, 40, 200, 201),
            "VAD": (75, 106, 107, 121),
            "TVA": (36, 37, 38, 39, 324),
        }.items():
            for state in states:
                self.assertRegex(repair, rf"\btransfer_state\s*=\s*{state}\b")
                self.assertIn(f"{state} = {{ set_state_controller_to = {tag} }}", repair)
        self.assertEqual(
            repair.count("ADISCORD_vorkerland_reset_temporary_claimant_cores = yes"),
            1,
        )
        self.assertEqual(
            repair.count("ADISCORD_vorkerland_ensure_claimant_home_cores = yes"),
            1,
        )
        self.assertEqual(
            repair.count("ADISCORD_vorkerland_repair_claimant_identities = yes"),
            1,
        )

        verifier = named_block(
            phase_effects, "ADISCORD_vorkerland_verify_collapse_materialized"
        )
        self.assertEqual(
            verifier.count(
                "ADISCORD_vorkerland_repair_collapse_materialization = yes"
            ),
            2,
        )
        self.assertEqual(
            verifier.count(
                "country_event = { id = ADISCORD_vorkerland_phase.2 days = 1 }"
            ),
            2,
        )

    def test_identity_cache_is_a_separate_postcondition(self) -> None:
        triggers = read("common/scripted_triggers/ADISCORD_vorkerland_phase_triggers.txt")
        structural = named_block(triggers, "ADISCORD_vorkerland_collapse_materialized")
        identities = named_block(
            triggers, "ADISCORD_vorkerland_claimant_identities_materialized"
        )
        self.assertNotIn("has_country_leader", structural)
        for token in (
            "character = WRK_Nikita_Worcker",
            "character = WRK_Anton_Bagley",
            "character = WRK_Vlad_Petrichev",
            "character = WRK_VAD_Joint_Council",
            "character = TVA_Dorian_Worx",
            "has_government = pragmatism",
            "has_country_leader_ideology = neo_vorkerism",
            "has_government = utilitarism",
            "has_government = technocracy",
        ):
            self.assertIn(token, identities)

        effects = read("common/scripted_effects/ADISCORD_vorkerland_phase_effects.txt")
        verifier = named_block(effects, "ADISCORD_vorkerland_verify_collapse_materialized")
        self.assertIn(
            "has_global_flag = ADISCORD_vorkerland_claimant_identity_assertion_started_v2",
            verifier,
        )
        self.assertNotIn(
            "ADISCORD_vorkerland_claimant_identities_materialized = yes",
            verifier,
        )

    def test_identity_cache_has_bounded_non_blocking_repair(self) -> None:
        effects = read("common/scripted_effects/ADISCORD_vorkerland_phase_effects.txt")
        events = read("events/ADISCORD_vorkerland_phase_events.txt")
        identity_event = event_block(events, "ADISCORD_vorkerland_phase.14")
        for token in (
            "ADISCORD_vorkerland_repair_claimant_identities = yes",
            "ADISCORD_vorkerland_claimant_identities_materialized = yes",
            "set_global_flag = ADISCORD_vorkerland_claimant_identities_verified_v2",
            "set_global_flag = ADISCORD_vorkerland_claimant_identity_retry_v2",
            "set_global_flag = ADISCORD_vorkerland_claimant_identity_degraded_v2",
            "country_event = { id = ADISCORD_vorkerland_phase.14 days = 2 }",
        ):
            self.assertIn(token, identity_event)
        self.assertNotIn("ADISCORD_vorkerland_collapse_materialization_failed", identity_event)

        identity_repair = named_block(
            effects, "ADISCORD_vorkerland_repair_claimant_identities"
        )
        self.assertEqual(
            identity_repair.count(
                "set_global_flag = ADISCORD_vorkerland_claimant_identity_assertion_started_v2"
            ),
            1,
        )
        certificate = [
            block
            for block in named_blocks(identity_repair, "if")
            if "set_global_flag = ADISCORD_vorkerland_claimant_identity_assertion_started_v2"
            in block
        ]
        self.assertEqual(len(certificate), 1)
        certificate_limit = named_block(certificate[0], "limit")
        for token in (
            "tag = WKR",
            "country_exists = WKR",
            "country_exists = VAD",
            "country_exists = TVA",
        ):
            self.assertIn(token, certificate_limit)

    def test_nikita_uses_an_explicit_transferred_country_leader_role(self) -> None:
        collapse_effects = read(
            "common/scripted_effects/ADISCORD_vorkerland_collapse_effects.txt"
        )
        helper = named_block(
            collapse_effects, "ADISCORD_vorkerland_promote_nikita_worcker"
        )
        for token in (
            "add_country_leader_role = {",
            "character = WRK_Nikita_Worcker",
            "promote_leader = yes",
            "ideology = neo_vorkerism",
            "set_country_flag = ADISCORD_vorkerland_nikita_wkr_role_added_v2",
        ):
            self.assertIn(token, helper)

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
        self.assertEqual(len(PHASE_FLAGS), 7)
        self.assertNotIn(
            "ADISCORD_vorkerland_phase_worx_client_administration", PHASE_FLAGS
        )
        self.assertNotIn(
            "ADISCORD_vorkerland_phase_worx_fragmentation", PHASE_FLAGS
        )
        issues = validate_phase_controller()
        self.assertEqual(issues, [], issue_report(issues))

    def test_phase_event_file_owns_hidden_wave_verifiers_in_exact_id_set(self) -> None:
        events = read("events/ADISCORD_vorkerland_phase_events.txt")
        actual_ids = [event_id for event_id, _ in event_blocks(events)]
        expected_ids = {
            *(f"ADISCORD_vorkerland_phase.{number}" for number in range(1, 10)),
            "ADISCORD_vorkerland_phase.14",
        }
        self.assertEqual(set(actual_ids), expected_ids)
        self.assertEqual(len(actual_ids), len(expected_ids))

        for event_number, callback in (
            (8, "ADISCORD_vorkerland_focus_confirm_central_minor_wave_launch = yes"),
            (9, "ADISCORD_vorkerland_focus_confirm_central_minor_wave_retry = yes"),
        ):
            verifier = event_block(
                events, f"ADISCORD_vorkerland_phase.{event_number}"
            )
            self.assertEqual(verifier.count("hidden = yes"), 1)
            self.assertEqual(verifier.count("is_triggered_only = yes"), 1)
            self.assertEqual(named_block(verifier, "immediate").count(callback), 1)

    def test_startup_has_no_old_materialization_bridges(self) -> None:
        startup = named_block(
            read("common/on_actions/01_ADISCORD_vorkerland_collapse_on_actions.txt"),
            "on_startup",
        )
        for token in (
            "ADISCORD_vorkerland_materialization_bridge_v1_scheduled",
            "ADISCORD_vorkerland_materialization_bridge_v2_scheduled",
            "ADISCORD_vorkerland_materialization_prewar_failed_bridge_v1_scheduled",
            "ADISCORD_vorkerland_materialized_outbreak_bridge_v1_scheduled",
            "load_focus_tree = { tree = ADISCORD_vorkerland_civil_war_focus",
        ):
            self.assertNotIn(token, startup)

    def test_startup_does_not_requeue_failed_or_dropped_materialization(self) -> None:
        startup = named_block(
            read("common/on_actions/01_ADISCORD_vorkerland_collapse_on_actions.txt"),
            "on_startup",
        )
        for token in (
            "ADISCORD_vorkerland_phase.2",
            "clr_global_flag = ADISCORD_vorkerland_collapse_materialization_failed",
            "clr_global_flag = ADISCORD_vorkerland_collapse_materialization_retry",
            "clr_global_flag = ADISCORD_vorkerland_collapse_materialization_final_retry",
            "clr_global_flag = ADISCORD_vorkerland_collapse_war_outbreak_scheduled",
        ):
            self.assertNotIn(token, startup)

    def test_materialization_verifier_cannot_run_after_wars_start(self) -> None:
        triggers = read("common/scripted_triggers/ADISCORD_vorkerland_phase_triggers.txt")
        self.assertNotIn(
            "ADISCORD_vorkerland_collapse_materialized_for_active_war_recovery",
            triggers,
        )
        phase_two = event_block(
            read("events/ADISCORD_vorkerland_phase_events.txt"),
            "ADISCORD_vorkerland_phase.2",
        )
        phase_two_trigger = named_block(phase_two, "trigger")
        self.assertIn(
            "NOT = { has_global_flag = ADISCORD_vorkerland_collapse_wars_started }",
            phase_two_trigger,
        )


class BoundedRetryTests(unittest.TestCase):
    def test_three_required_edges_launch_together_and_are_postcondition_driven(self) -> None:
        issues = validate_bounded_retry()
        self.assertEqual(issues, [], issue_report(issues))


class ReunificationFormationTests(unittest.TestCase):
    def test_winner_forms_wrk_only_after_loser_subject_release(self) -> None:
        issues = validate_reunification_formation()
        self.assertEqual(issues, [], issue_report(issues))

    def test_phase_six_forms_wrk_immediately_from_all_three_claimants(self) -> None:
        phase_six = event_block(
            read("events/ADISCORD_vorkerland_phase_events.txt"),
            "ADISCORD_vorkerland_phase.6",
        )
        for winner in ("WKR", "VAD", "TVA"):
            with self.subTest(winner=winner):
                self.assertRegex(
                    phase_six,
                    rf"(?s)\b{winner}\s*=\s*\{{.*?"
                    rf"ADISCORD_vorkerland_form_wrk_from_{winner.lower()}\s*=\s*yes"
                    r".*?country_event\s*=\s*\{\s*id\s*=\s*"
                    r"ADISCORD_vorkerland_phase\.7\s+days\s*=\s*1\s*\}",
                )


class PrematureWrkRecoveryTests(unittest.TestCase):
    def test_release_guards_and_package_routing_are_coherent(self) -> None:
        issues = validate_premature_wrk_recovery()
        self.assertEqual(issues, [], issue_report(issues))

    def test_fresh_release_with_mixed_winners_restores_exact_packages(self) -> None:
        effects = read(
            "common/scripted_effects/ZZ_ADISCORD_capitulation_distribution_effects.txt"
        )
        wkr_router = named_block(
            effects, "ADISCORD_vorkerland_restore_premature_wrk_packages_to_wkr"
        )
        tva_router = named_block(
            effects, "ADISCORD_vorkerland_restore_premature_wrk_packages_to_tva"
        )
        for district, states in (
            ("RIV", (79, 306, 308, 309, 327)),
            ("SWB", (35,)),
        ):
            with self.subTest(winner="WKR", district=district):
                self.assertIn(
                    f"{district} = {{ has_country_flag = "
                    "ADISCORD_vorkerland_central_minor_winner_wkr }",
                    wkr_router,
                )
                for state_id in states:
                    self.assertRegex(
                        wkr_router,
                        rf"(?s){state_id}\s*=\s*\{{\s*is_owned_by\s*=\s*WRK\s*\}}"
                        rf".*?transfer_state\s*=\s*{state_id}\b"
                        rf".*?set_state_controller_to\s*=\s*WKR",
                    )
        for district, states in (("REV", (82, 323)), ("OSV", (318, 320))):
            with self.subTest(winner="TVA", district=district):
                self.assertIn(
                    f"{district} = {{ has_country_flag = "
                    "ADISCORD_vorkerland_central_minor_winner_tva }",
                    tva_router,
                )
                for state_id in states:
                    self.assertRegex(
                        tva_router,
                        rf"(?s){state_id}\s*=\s*\{{\s*is_owned_by\s*=\s*WRK\s*\}}"
                        rf".*?transfer_state\s*=\s*{state_id}\b"
                        rf".*?set_state_controller_to\s*=\s*TVA",
                    )

    def test_human_handoff_precedes_false_wrk_annex(self) -> None:
        effects = read(
            "common/scripted_effects/ZZ_ADISCORD_capitulation_distribution_effects.txt"
        )
        dissolve = named_block(
            effects, "ADISCORD_vorkerland_dissolve_premature_wrk_as_claimant"
        )
        route_end = max(
            dissolve.index(
                f"ADISCORD_vorkerland_restore_premature_wrk_packages_to_{tag} = yes"
            )
            for tag in ("wkr", "vad", "tva")
        )
        handoff = dissolve.index("change_tag_from = WRK")
        annex = dissolve.index("annex_country = { target = WRK transfer_troops = yes }")
        self.assertLess(route_end, handoff)
        self.assertLess(handoff, annex)

    def test_old_save_claimant_inference_is_absent(self) -> None:
        combined = "\n".join(
            (
                read("common/scripted_triggers/ADISCORD_vorkerland_collapse_triggers.txt"),
                read("common/scripted_effects/ZZ_ADISCORD_capitulation_distribution_effects.txt"),
                read("common/on_actions/01_ADISCORD_vorkerland_collapse_on_actions.txt"),
            )
        )
        for token in (
            "ADISCORD_vorkerland_repair_premature_wrk",
            "ADISCORD_vorkerland_premature_wrk_records_wkr_claimant",
            "ADISCORD_vorkerland_premature_wrk_records_vad_claimant",
            "ADISCORD_vorkerland_premature_wrk_records_tva_claimant",
            "ADISCORD_vorkerland_premature_wrk_recorded_wkr",
            "ADISCORD_vorkerland_premature_wrk_recorded_vad",
            "ADISCORD_vorkerland_premature_wrk_recorded_tva",
        ):
            with self.subTest(token=token):
                self.assertNotIn(token, combined)


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
