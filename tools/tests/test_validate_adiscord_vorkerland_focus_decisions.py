from __future__ import annotations

import json
import unittest

from tools.validators.validate_adiscord_vorkerland_focus_decisions import (
    CENTRAL_INTEGRATION_PACKAGES,
    CENTRAL_TARGETS,
    CENTRAL_WAVE_DECISION,
    CENTRAL_WAVE_VERIFIER_EVENTS,
    CLAIMANT_HOME_STATES,
    CORE_FOCUS_UNLOCK,
    CORE_PACKAGES,
    DECISION_FILE,
    EFFECT_FILE,
    EVENT_REGISTRY_FILE,
    LEGACY_CONTROLLER_MISSIONS,
    PHASE_EVENT_FILE,
    PHASE_EFFECT_FILE,
    PHASE_TRIGGER_FILE,
    LEVY_DECISIONS,
    ROOT,
    RUSSIAN_LOCALISATION,
    SUPPORT_DECISIONS,
    collect_issues,
    named_block,
    named_blocks,
    read,
)


class VorkerlandFocusDecisionTests(unittest.TestCase):
    def test_integrated_contract(self) -> None:
        self.assertEqual(collect_issues(), [])

    def test_central_showdown_stays_visible_while_command_readiness_is_explained(self) -> None:
        decisions = read(DECISION_FILE)
        showdown = named_block(
            decisions, "ADISCORD_vorkerland_commit_to_central_showdown"
        )
        visible = named_block(showdown, "visible")
        available = named_block(showdown, "available")

        self.assertIn(
            "has_global_flag = ADISCORD_vorkerland_phase_central_preparation",
            visible,
        )
        self.assertNotIn("ADISCORD_vorkerland_focus_central_front_prepared", visible)
        self.assertNotIn("central_war_unlocked", visible)

        self.assertIn(
            "tooltip = ADISCORD_vorkerland_central_showdown_command_ready_tt",
            available,
        )
        self.assertIn(
            "has_country_flag = ADISCORD_vorkerland_focus_central_front_prepared",
            available,
        )
        for tag in ("wkr", "vad", "tva"):
            self.assertIn(
                f"ADISCORD_vorkerland_focus_{tag}_central_war_unlocked",
                available,
            )

    def test_named_minor_fronts_precede_shared_final_showdown(self) -> None:
        decisions = read(DECISION_FILE)
        effects = read(EFFECT_FILE)
        phase_triggers = read(PHASE_TRIGGER_FILE)
        recovery_phase = named_block(
            phase_triggers, "ADISCORD_vorkerland_central_minor_campaign_phase_available"
        )
        self.assertIn("ADISCORD_vorkerland_phase_central_preparation", recovery_phase)
        for token in (
            "ADISCORD_vorkerland_phase_central_showdown",
            "ADISCORD_vorkerland_phase_reunification",
            "ADISCORD_vorkerland_has_single_surviving_claimant = yes",
            "tag = WRK",
            "ADISCORD_vorkerland_phase_postwar_integration",
            "ADISCORD_vorkerland_reunification_verified",
            "ADISCORD_vorkerland_route_worker",
            "ADISCORD_vorkerland_route_joint",
            "ADISCORD_vorkerland_route_utilitarian",
        ):
            self.assertNotIn(token, recovery_phase)
        district_control = named_block(
            phase_triggers, "ADISCORD_vorkerland_central_districts_owned_and_controlled"
        )
        claimant_graph = named_block(
            phase_triggers, "ADISCORD_vorkerland_central_districts_inside_claimant_graph"
        )
        for _, states, _ in CENTRAL_INTEGRATION_PACKAGES.values():
            for state in states:
                self.assertEqual(district_control.count(f"controls_state = {state}"), 1)
                self.assertIn(
                    f"{state} = {{ OR = {{ is_owned_by = WKR is_owned_by = VAD is_owned_by = TVA }} }}",
                    district_control,
                )
                graph_state = named_block(claimant_graph, str(state))
                self.assertIn(
                    "OR = { is_owned_by = WKR is_owned_by = VAD is_owned_by = TVA }",
                    graph_state,
                )
                self.assertIn(
                    "OR = { is_controlled_by = WKR is_controlled_by = VAD is_controlled_by = TVA }",
                    graph_state,
                )
        block = named_block(decisions, "ADISCORD_vorkerland_commit_to_central_showdown")
        effect = named_block(effects, "ADISCORD_vorkerland_focus_schedule_final_showdown")
        self.assertEqual(len(CENTRAL_TARGETS), 9)
        self.assertIn(
            "ADISCORD_vorkerland_central_districts_inside_claimant_graph = yes",
            block,
        )
        self.assertIn(
            "ADISCORD_vorkerland_central_districts_inside_claimant_graph = yes",
            effect,
        )
        self.assertIn("country_event = { id = ADISCORD_vorkerland_phase.4 days = 1 }", effect)
        self.assertIn("fire_only_once = no", block)
        self.assertIn("days_re_enable = 7", block)
        cooldown = (
            "NOT = { has_global_flag = "
            "ADISCORD_vorkerland_showdown_retry_cooldown }"
        )
        self.assertIn(cooldown, block)
        self.assertIn(cooldown, effect)
        self.assertIn("ai_will_do = { factor = 1000 }", block)
        for tooltip in (
            "ADISCORD_vorkerland_central_showdown_command_ready_tt",
            "ADISCORD_vorkerland_central_showdown_campaigns_closed_tt",
            "ADISCORD_vorkerland_central_districts_integrated_tt",
            "ADISCORD_vorkerland_central_showdown_no_live_intervention_tt",
        ):
            self.assertIn(f"tooltip = {tooltip}", block)
        active_intervention = (
            "NOT = { has_global_flag = "
            "ADISCORD_vorkerland_vad_solar_intervention_active }"
        )
        self.assertIn(active_intervention, block)
        self.assertIn(active_intervention, effect)
        for optional_blocker in (
            "ADISCORD_vorkerland_vad_solar_intervention_reserved",
            "ADISCORD_vorkerland_vad_sol_invitation_pending",
            "ADISCORD_vorkerland_wkr_vla_invitation_pending",
            "ADISCORD_vorkerland_wkr_solar_counter_intervention_ready",
            "ADISCORD_vorkerland_wkr_has_solar_counter_border",
            "ADISCORD_vorkerland_sol_restoration_verified",
        ):
            self.assertNotIn(optional_blocker, block)
            self.assertNotIn(optional_blocker, effect)
        minor = named_block(decisions, CENTRAL_WAVE_DECISION)
        launch = named_block(
            effects, "ADISCORD_vorkerland_focus_launch_central_minor_wave"
        )
        self.assertNotIn("ADISCORD_vorkerland_focus_central_front_prepared", minor)
        self.assertNotIn("ADISCORD_vorkerland_focus_central_front_prepared", launch)
        self.assertIn("tag = WRK", named_block(minor, "allowed"))
        self.assertIn("fire_only_once = no", minor)
        self.assertEqual(launch.count("declare_war_on = {"), 9)
        self.assertNotIn("else_if =", launch)
        for target in CENTRAL_TARGETS:
            self.assertIn(f"any_neighbor_country = {{ tag = {target} }}", minor)
            self.assertIn(
                f"set_country_flag = ADISCORD_vorkerland_focus_central_minor_target_{target.lower()}",
                minor,
            )
            self.assertIn(
                f"declare_war_on = {{ target = {target} type = annex_everything }}",
                launch,
            )
            self.assertIn(f"NOT = {{ country_exists = {target} }}", block)
            self.assertIn(f"NOT = {{ country_exists = {target} }}", effect)
            self.assertNotIn(f"{target} = {{ is_subject = yes }}", block)
            self.assertNotIn(f"{target} = {{ is_subject = yes }}", effect)
        for forbidden in ("declare_war_on", "start_civil_war", "create_wargoal"):
            self.assertNotIn(forbidden, block)
            self.assertNotIn(forbidden, effect)

    def test_wave_ai_no_longer_serializes_a_solarino_target(self) -> None:
        decisions = read(DECISION_FILE)
        marker = "ADISCORD_vorkerland_focus_vad_solland_liaison_prepared"
        block = named_block(decisions, CENTRAL_WAVE_DECISION)
        self.assertIn("ai_will_do = { factor = 900 }", block)
        self.assertNotIn(marker, block)
        self.assertNotIn("ADISCORD_vorkerland_consolidate_egc", decisions)

    def test_minor_wave_requires_a_viable_target_before_recording_pending(self) -> None:
        decisions = read(DECISION_FILE)
        effects = read(EFFECT_FILE)
        phase_triggers = read(PHASE_TRIGGER_FILE)
        wave = named_block(decisions, CENTRAL_WAVE_DECISION)
        viability_name = "ADISCORD_vorkerland_has_adjacent_viable_central_minor"
        self.assertEqual(named_block(wave, "visible").count(f"{viability_name} = yes"), 1)
        self.assertEqual(named_block(wave, "available").count(f"{viability_name} = yes"), 1)

        viability = named_block(phase_triggers, viability_name)
        for target in CENTRAL_TARGETS:
            viable_branch = (
                f"AND = {{ any_neighbor_country = {{ tag = {target} }} "
                f"{target} = {{ exists = yes is_subject = no "
                "NOT = { has_capitulated = yes } "
                "NOT = { OR = { has_war_with = WKR has_war_with = VAD "
                "has_war_with = TVA } } } }"
            )
            self.assertEqual(viability.count(viable_branch), 1)

        complete_effect = named_block(wave, "complete_effect")
        pending_setter = (
            "set_country_flag = ADISCORD_vorkerland_focus_central_minor_launch_pending"
        )
        pending_branches = [
            branch
            for branch in named_blocks(complete_effect, "if")
            if pending_setter in branch
        ]
        self.assertEqual(len(pending_branches), 1)
        for target in CENTRAL_TARGETS:
            self.assertIn(
                "has_country_flag = "
                f"ADISCORD_vorkerland_focus_central_minor_target_{target.lower()}",
                pending_branches[0],
            )
        self.assertEqual(decisions.count(pending_setter) + effects.count(pending_setter), 1)
        self.assertTrue(
            any(
                "ADISCORD_vorkerland_focus_cleanup_central_minor_front = yes" in branch
                for branch in named_blocks(complete_effect, "else")
            )
        )

    def test_minor_front_controller_uses_registered_hidden_delayed_events(self) -> None:
        decisions = read(DECISION_FILE)
        effects = read(EFFECT_FILE)
        phase_triggers = read(PHASE_TRIGGER_FILE)
        phase_events = read(PHASE_EVENT_FILE)
        launcher = named_block(
            effects, "ADISCORD_vorkerland_focus_launch_central_minor_wave"
        )
        launch_call = "country_event = { id = ADISCORD_vorkerland_phase.8 days = 1 }"
        self.assertEqual(launcher.count(launch_call), 1)
        launch_branches = [
            branch for branch in named_blocks(launcher, "if") if launch_call in branch
        ]
        self.assertEqual(len(launch_branches), 1)
        for target in CENTRAL_TARGETS:
            self.assertIn(
                f"ADISCORD_vorkerland_focus_central_minor_target_{target.lower()}",
                launch_branches[0],
            )

        first_confirmation = named_block(
            effects, "ADISCORD_vorkerland_focus_confirm_central_minor_wave_launch"
        )
        retry_call = "country_event = { id = ADISCORD_vorkerland_phase.9 days = 1 }"
        self.assertEqual(effects.count(retry_call), 1)
        retry_branches = [
            branch
            for branch in named_blocks(first_confirmation, "else_if")
            if retry_call in branch
        ]
        self.assertEqual(len(retry_branches), 1)
        self.assertIn(
            "ADISCORD_vorkerland_has_retryable_recorded_central_minor_front = yes",
            retry_branches[0],
        )
        self.assertIn(
            "NOT = { has_country_flag = ADISCORD_vorkerland_focus_central_minor_launch_retry }",
            retry_branches[0],
        )
        self.assertEqual(
            first_confirmation.count(
                "set_country_flag = ADISCORD_vorkerland_focus_central_minor_launch_retry"
            ),
            1,
        )
        self.assertEqual(first_confirmation.count(retry_call), 1)

        retry_confirmation = named_block(
            effects, "ADISCORD_vorkerland_focus_confirm_central_minor_wave_retry"
        )
        for forbidden in (
            "country_event = { id = ADISCORD_vorkerland_phase.8",
            "country_event = { id = ADISCORD_vorkerland_phase.9",
            "set_country_flag = ADISCORD_vorkerland_focus_central_minor_launch_retry",
            "ADISCORD_vorkerland_focus_retry_central_minor_wave_declarations = yes",
        ):
            self.assertNotIn(forbidden, retry_confirmation)

        retryable = named_block(
            phase_triggers, "ADISCORD_vorkerland_has_retryable_recorded_central_minor_front"
        )
        for target in CENTRAL_TARGETS:
            retryable_branch = (
                "AND = { has_country_flag = "
                f"ADISCORD_vorkerland_focus_central_minor_target_{target.lower()} "
                f"NOT = {{ has_war_with = {target} }} "
                f"any_neighbor_country = {{ tag = {target} }} "
                f"{target} = {{ exists = yes is_subject = no "
                "NOT = { has_capitulated = yes } "
                "NOT = { OR = { has_war_with = WKR has_war_with = VAD "
                "has_war_with = TVA } } } }"
            )
            self.assertEqual(retryable.count(retryable_branch), 1)

        controller_sources = decisions + effects + phase_triggers + phase_events
        for mission_id in LEGACY_CONTROLLER_MISSIONS:
            self.assertNotIn(mission_id, controller_sources)
            self.assertNotIn(f"activate_mission = {mission_id}", controller_sources)
            self.assertNotIn(f"remove_mission = {mission_id}", controller_sources)

        event_blocks = named_blocks(phase_events, "country_event")
        registry = json.loads(read(EVENT_REGISTRY_FILE))["events"]
        for number, callback in CENTRAL_WAVE_VERIFIER_EVENTS.items():
            event_id = f"ADISCORD_vorkerland_phase.{number}"
            matching_events = [
                block for block in event_blocks if f"id = {event_id}" in block
            ]
            self.assertEqual(len(matching_events), 1)
            self.assertIn("hidden = yes", matching_events[0])
            self.assertIn("is_triggered_only = yes", matching_events[0])
            self.assertEqual(named_block(matching_events[0], "immediate").count(callback), 1)
            expected = {
                "id": event_id,
                "namespace": "ADISCORD_vorkerland_phase",
                "number": number,
                "owner": PHASE_EVENT_FILE.as_posix(),
                "subsystem": "vorkerland_phase",
                "status": "active",
            }
            self.assertEqual([entry for entry in registry if entry.get("id") == event_id], [expected])

    def test_minor_fronts_have_one_retry_and_a_non_forcing_240_day_marker(self) -> None:
        decisions = read(DECISION_FILE)
        effects = read(EFFECT_FILE)
        deadline = named_block(
            decisions, "ADISCORD_vorkerland_focus_central_minor_front_deadline"
        )
        self.assertIn("days_mission_timeout = 240", deadline)
        self.assertIn(
            "ADISCORD_vorkerland_focus_resolve_central_minor_wave_deadline = yes", deadline
        )
        resolver = named_block(
            effects, "ADISCORD_vorkerland_focus_resolve_central_minor_wave_deadline"
        )
        self.assertIn(
            "ADISCORD_vorkerland_focus_central_minor_front_protracted", resolver
        )
        self.assertIn("days = 180", resolver)
        self.assertIn("live war remains unresolved", resolver)
        for forbidden in ("transfer_state", "white_peace", "annex_country"):
            self.assertNotIn(forbidden, resolver)
        first_check = named_block(
            effects, "ADISCORD_vorkerland_focus_confirm_central_minor_wave_launch"
        )
        self.assertIn("ADISCORD_vorkerland_central_minor_campaign_phase_available = yes", first_check)
        self.assertIn(
            "country_event = { id = ADISCORD_vorkerland_phase.9 days = 1 }",
            first_check,
        )
        retry_check = named_block(
            effects, "ADISCORD_vorkerland_focus_confirm_central_minor_wave_retry"
        )
        self.assertIn(
            "ADISCORD_vorkerland_central_minor_campaign_phase_available = yes",
            retry_check,
        )
        finish = named_block(effects, "ADISCORD_vorkerland_focus_finish_central_minor_wave")
        self.assertIn("ADISCORD_vorkerland_focus_central_minor_recovery_cooldown", finish)
        self.assertIn("days = 14", finish)
        for target in CENTRAL_TARGETS:
            declaration = f"declare_war_on = {{ target = {target} type = annex_everything }}"
            self.assertEqual(effects.count(declaration), 2)

    def test_captured_districts_core_only_after_full_civil_integration(self) -> None:
        decisions = read(DECISION_FILE)
        states: list[int] = []
        for target, (decision_id, package, duration) in CENTRAL_INTEGRATION_PACKAGES.items():
            block = named_block(decisions, decision_id)
            states.extend(package)
            self.assertIn(f"NOT = {{ country_exists = {target} }}", block)
            self.assertIn(
                "ADISCORD_vorkerland_central_minor_campaign_phase_available = yes",
                block,
            )
            self.assertIn("tag = WRK", named_block(block, "allowed"))
            self.assertIn(f"days_remove = {duration}", block)
            self.assertIn("days_re_enable = 7", block)
            self.assertIn("fire_only_once = no", block)
            self.assertIn("remove_effect = {", block)
            self.assertNotIn("complete_effect = {", block)
            self.assertIn(
                "custom_effect_tooltip = ADISCORD_vorkerland_integrate_central_district_tt",
                block,
            )
            self.assertIn("ADISCORD_vorkerland_begin_reunification = yes", block)
            for state in package:
                self.assertGreaterEqual(block.count(f"owns_state = {state}"), 3)
                self.assertGreaterEqual(block.count(f"controls_state = {state}"), 2)
                self.assertRegex(
                    block, rf"\b{state}\s*=\s*\{{\s*add_core_of\s*=\s*ROOT\s*\}}"
                )
        self.assertEqual(len(states), 24)
        self.assertEqual(len(states), len(set(states)))

    def test_final_war_and_reunification_require_integrated_central_map(self) -> None:
        decisions = read(DECISION_FILE)
        effects = read(EFFECT_FILE)
        phase = read(PHASE_EFFECT_FILE)
        showdown = named_block(decisions, "ADISCORD_vorkerland_commit_to_central_showdown")
        scheduler = named_block(
            effects, "ADISCORD_vorkerland_focus_schedule_final_showdown"
        )
        reunification = named_block(phase, "ADISCORD_vorkerland_begin_reunification")
        inheritance = named_block(
            phase, "ADISCORD_vorkerland_inherit_integrated_claimant_cores"
        )
        formation = named_block(phase, "ADISCORD_vorkerland_finalize_wrk_formation")
        states = sorted(
            state
            for _, package, _ in CENTRAL_INTEGRATION_PACKAGES.values()
            for state in package
        )
        for target in CENTRAL_TARGETS:
            self.assertIn(f"NOT = {{ country_exists = {target} }}", reunification)
        self.assertIn("ADISCORD_vorkerland_phase_central_showdown", reunification)
        self.assertIn("ADISCORD_vorkerland_phase_reunification", reunification)
        self.assertEqual(
            reunification.count(
                "ADISCORD_vorkerland_central_districts_owned_and_controlled = yes"
            ),
            3,
        )
        for state in states:
            gate = f"{state} = {{ OR = {{ is_core_of = WKR is_core_of = VAD is_core_of = TVA }} }}"
            self.assertIn(gate, showdown)
            self.assertIn(gate, scheduler)
            self.assertIn(gate, reunification)
        inherited = sorted(set(states).union(CLAIMANT_HOME_STATES))
        for state in inherited:
            block = named_block(inheritance, str(state))
            self.assertIn("is_owned_by = WRK", block)
            self.assertNotIn("is_controlled_by = WRK", block)
            self.assertIn("add_core_of = WRK", block)
        self.assertIn(
            "ADISCORD_vorkerland_inherit_integrated_claimant_cores = yes", formation
        )

    def test_retreat_levies_are_two_weak_units_per_claimant_at_most(self) -> None:
        decisions = read(DECISION_FILE)
        effects = read(EFFECT_FILE)
        self.assertEqual(len(LEVY_DECISIONS), 6)
        self.assertEqual(effects.count("create_unit = {"), 6)
        for decision_id in LEVY_DECISIONS:
            self.assertIn("fire_only_once = no", named_block(decisions, decision_id))
        self.assertNotIn("count =", effects)

    def test_core_restoration_is_explicit_disjoint_and_phase_gated(self) -> None:
        decisions = read(DECISION_FILE)
        states = [state for package in CORE_PACKAGES.values() for state in package]
        self.assertEqual(len(CORE_PACKAGES), 7)
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
            self.assertIn("fire_only_once = no", block)
            effect = named_block(effects, decision_id)
            for forbidden in ("add_to_faction", "create_faction", "puppet =", "set_autonomy"):
                self.assertNotIn(forbidden, effect)
            self.assertIn(
                "add_equipment_to_stockpile = { type = infantry_equipment amount = -300 }",
                effect,
            )
            self.assertIn(
                "add_equipment_to_stockpile = { type = support_equipment amount = -30 }",
                effect,
            )
            if ally == "VLA":
                self.assertGreaterEqual(
                    block.count("ADISCORD_vorkerland_wkr_vla_alliance_accepted"), 2
                )
                relation = "OR = { is_in_faction_with = ROOT is_subject_of = ROOT }"
                self.assertGreaterEqual(block.count(relation), 2)
                self.assertIn(relation, effect)
                self.assertNotIn("ADISCORD_vorkerland_joined_worker_republic", block)
                self.assertNotIn("ADISCORD_vorkerland_joined_worker_republic", block)
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
    PHASE_EFFECT_FILE,
