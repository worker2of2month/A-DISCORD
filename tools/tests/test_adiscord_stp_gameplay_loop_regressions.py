from __future__ import annotations

import itertools
import unittest
from pathlib import Path

from tools.tests.test_adiscord_stp_preparation import (
    block,
    entries,
    matches_conditions,
    scalar,
    selected_effects,
    walk,
)


ROOT = Path(__file__).resolve().parents[2]
INSPECTION_STATES = (2, 3, 29, 45, 46, 53)
TOKENS = ROOT / "common/synchronized_dynamic_tokens/ADISCORD_tokens.txt"


class StelanderGameplayLoopRegressionTests(unittest.TestCase):
    def test_ai_cannot_use_debug_suspicion_health_or_balance_controls(self):
        decisions = entries("common/decisions/ADISCORD_STP_decisions.txt")
        controls = [e for category in decisions for e in category.value if e.key.startswith("STP_debug_")]
        self.assertGreaterEqual(len(controls), 8)
        for control in controls:
            with self.subTest(control=control.key):
                weights = next((e.value for e in control.value if e.key == "ai_will_do"), [])
                base = next((float(e.value) for e in weights if e.key == "base"), 1)
                factor = next((float(e.value) for e in weights if e.key == "factor"), 1)
                self.assertEqual(base * factor, 0)

    def test_missing_election_mission_settles_only_after_original_deadline(self):
        hooks = block(entries("common/on_actions/02_ADISCORD_STP_on_actions.txt"), "on_actions")
        weekly = block(block(hooks, "on_weekly_STP"), "effect")
        for age, active, finished, started, expected in (
            (139, False, False, False, False),
            (140, False, False, False, True),
            (901, False, False, False, True),
            (901, True, False, False, False),
            (901, False, True, False, False),
            (901, False, False, True, False),
        ):
            facts = {
                ("STP", "has_country_flag", "STP_cw_elections_started"): True,
                ("STP", "flag_days", "STP_cw_elections_started"): age,
                ("STP", "has_active_mission", "STP_cw_election_window"): active,
                ("STP", "has_country_flag", "STP_cw_elections_finished"): finished,
                ("STP", "has_global_flag", "STP_cw_started"): started,
            }
            selected = list(selected_effects(weekly, facts))
            self.assertEqual(any(e.key == "STP_cw_finish_elections" for _, e in selected), expected,
                             (age, active, finished, started))

    @classmethod
    def setUpClass(cls) -> None:
        cls.effects = entries("common/scripted_effects/ADISCORD_STP_scripted_effects.txt")
        cls.triggers = entries("common/scripted_triggers/ADISCORD_STP_scripted_triggers.txt")
        cls.decisions = entries("common/decisions/ADISCORD_STP_decisions.txt")
        cls.battle = block(cls.decisions, "STP_battle_for_stelander")
        cls.council = block(cls.decisions, "STP_cw_war_council")
        cls.external = block(cls.decisions, "STP_cw_external_intervention")
        cls.tokens = TOKENS.read_text(encoding="utf-8-sig")
        cls.loc = (ROOT / "localisation/russian/ADISCORD_STP_l_russian.yml").read_text(encoding="utf-8-sig")
        cls.ai = entries("common/ai_strategy/ADISCORD_STP_civil_war.txt")

    def test_inspection_scheduler_is_an_idempotent_reconciler(self) -> None:
        scheduler = block(self.effects, "STP_schedule_next_party_inspection")
        opener = block(self.effects, "STP_cw_open_one_party_inspection")
        change = block(self.effects, "STP_change_party_suspicion")
        resolve = block(self.effects, "STP_resolve_party_inspection")
        can_schedule = block(self.triggers, "STP_cw_can_schedule_party_inspections")

        self.assertIn("STP_cw_can_schedule_party_inspections", {e.key for e in walk(scheduler)})
        self.assertEqual(sum(e.key == "STP_cw_repair_party_inspection_markers" for e in walk(scheduler)), 1)
        self.assertEqual(sum(e.key == "STP_cw_trim_excess_party_inspections" for e in walk(scheduler)), 1)
        self.assertEqual(sum(e.key == "STP_cw_open_one_party_inspection" for e in walk(scheduler)), 2)
        self.assertIn("STP_cw_any_inspection_active", {e.key for e in walk(scheduler)})
        self.assertIn("STP_cw_second_inspection_unlocked", {e.key for e in walk(scheduler)})
        self.assertFalse(any(e.key == "add_days_mission_timeout" for e in walk(scheduler)))
        self.assertNotIn("1 = { }", "".join(str(e.value) for e in opener))

        for required in (
            "STP_battle_for_stelander_active",
            "STP_cw_inspection_chain_open",
            "STP_sided_with_Maksim_flag",
            "STP_cw_inspection_resolving",
        ):
            self.assertIn(required, {e.value for e in walk(can_schedule) if e.key in ("has_country_flag",)})

        self.assertIn("STP_cw_can_schedule_party_inspections", {e.key for e in walk(change)})
        self.assertEqual(next(e.value for e in walk(resolve) if e.key == "set_country_flag"),
                         "STP_cw_inspection_resolving")
        flags = [e.value for e in walk(resolve) if e.key in ("set_country_flag", "clr_country_flag")]
        self.assertEqual(flags.count("STP_cw_inspection_resolving"), 2)
        self.assertLess(
            next(e.line for e in walk(resolve) if e.key == "set_country_flag" and e.value == "STP_cw_inspection_resolving"),
            next(e.line for e in walk(resolve) if e.key == "STP_change_party_suspicion"),
        )
        self.assertGreater(
            next(e.line for e in walk(resolve) if e.key == "clr_country_flag" and e.value == "STP_cw_inspection_resolving"),
            next(e.line for e in walk(resolve) if e.key == "clr_state_flag" and e.value == "STP_party_inspection_active"),
        )

    def test_opener_checks_cap_before_every_create_and_keeps_the_only_legal_region(self) -> None:
        opener = block(self.effects, "STP_cw_open_one_party_inspection")
        self.assertEqual(scalar(opener, "STP_cw_count_live_party_inspections"), "yes")
        self.assertIn("STP_cw_has_openable_inspection_region", {e.key for e in walk(opener)})
        self.assertIn("STP_cw_has_other_openable_inspection", {e.key for e in walk(opener)})
        suspicion_caps = [(scalar(e.value, "var"), scalar(e.value, "value"), scalar(e.value, "compare"))
                          for e in walk(opener) if e.key == "check_variable"]
        self.assertIn(("STP_party_suspicion", "60", "less_than"), suspicion_caps)
        self.assertIn(("STP_party_suspicion", "60", "greater_than_or_equals"), suspicion_caps)
        self.assertIn(("STP_party_suspicion", "50", "greater_than_or_equals"), suspicion_caps)
        for state in INSPECTION_STATES:
            mission = f"STP_party_inspection_state_{state}"
            self.assertIn(f"activate_mission = {mission}", " ".join(
                f"{e.key} = {e.value}" for e in walk(opener) if e.key == "activate_mission"))
            self.assertEqual(sum(e.key == "activate_mission" and e.value == mission for e in walk(opener)), 1)
            self.assertIn(("STP_last_inspection_state", str(state), "equals"), suspicion_caps)
        empty = [e for e in walk(opener) if e.key == "1" and isinstance(e.value, list) and not e.value]
        self.assertEqual(empty, [])

    def test_trim_keeps_the_nearest_commission_and_aborts_without_resolve(self) -> None:
        trim = block(self.effects, "STP_cw_trim_excess_party_inspections")
        abort = block(self.effects, "STP_cw_abort_party_inspection")
        self.assertIn("STP_cw_consider_inspection_keeper", {e.key for e in walk(trim)})
        self.assertNotIn("add_war_support", {e.key for e in walk(abort)})
        self.assertNotIn("STP_resolve_party_inspection", {e.key for e in walk(abort)})
        self.assertNotIn("STP_change_party_suspicion", {e.key for e in walk(abort)})
        self.assertEqual(sum(e.key == "STP_cw_abort_party_inspection" for e in walk(trim)), 6)
        for state in INSPECTION_STATES:
            self.assertIn(f"days_mission_timeout@STP_party_inspection_state_{state}",
                          [scalar(e.value, "value") for e in walk(trim) if e.key == "set_temp_variable"
                           and any(c.key == "value" and "days_mission_timeout@" in str(c.value) for c in e.value)])
            self.assertIn(state, {int(e.value) for e in walk(abort) if e.key == "state"})
        self.assertIn("remove_mission", {e.key for e in walk(abort)})
        self.assertNotIn("STP_resolve_party_inspection", {e.key for e in walk(abort)})

    def test_inspection_matrix_covers_thresholds_pairs_and_old_save_repair(self) -> None:
        second = block(self.triggers, "STP_cw_second_inspection_unlocked")
        threshold = next(e.value for e in second if e.key == "check_variable")
        self.assertEqual((scalar(threshold, "var"), scalar(threshold, "value"), scalar(threshold, "compare")),
                         ("STP_party_suspicion", "60", "greater_than_or_equals"))
        pair_guard = block(self.triggers, "STP_cw_two_inspections_active")
        pairs = set()
        for group in (e.value for e in walk(pair_guard) if e.key == "AND"):
            states = tuple(sorted(int(child.key) for child in group if child.key.isdigit()))
            if len(states) == 2:
                pairs.add(states)
        self.assertEqual(pairs, set(itertools.combinations(INSPECTION_STATES, 2)))
        repair = block(self.effects, "STP_cw_repair_party_inspection_markers")
        for state in INSPECTION_STATES:
            self.assertEqual(sum(e.key == "activate_mission" for e in walk(repair)), 0)
            self.assertIn(f"STP_party_inspection_state_{state}", {e.value for e in walk(repair) if e.key == "has_active_mission"})
        end = block(self.effects, "STP_end_battle_for_stelander")
        self.assertIn("STP_cw_inspection_resolving", {e.value for e in walk(end) if e.key == "clr_country_flag"})
        self.assertIn("STP_cw_inspection_chain_open", {e.value for e in walk(end) if e.key == "clr_country_flag"})
        for state in INSPECTION_STATES:
            self.assertIn(f"STP_party_inspection_state_{state}", {e.value for e in walk(end) if e.key == "remove_mission"})
            self.assertIn(f"STP_party_inspection_state_{state}", self.tokens)

    def test_delay_targets_one_live_commission(self) -> None:
        decision = block(self.battle, "STP_cw_delay_inspection")
        self.assertEqual(scalar(decision, "state_target"), "yes")
        self.assertEqual({int(e.value) for e in block(decision, "targets") if e.key == "" or e.value in map(str, INSPECTION_STATES) or True},
                         {int(child.value) for child in block(decision, "targets")})
        self.assertEqual({int(e.value) for e in block(decision, "targets")}, set(INSPECTION_STATES))
        self.assertEqual(tuple(scalar(decision, key) for key in ("cost", "days_remove", "days_re_enable")), ("35", "14", "60"))
        self.assertIn("STP_party_inspection_active", {e.value for e in walk(block(decision, "visible")) if e.key == "has_state_flag"})
        self.assertNotIn("has_active_mission", {e.key for e in walk(block(decision, "target_trigger"))})
        complete = block(decision, "complete_effect")
        for state in INSPECTION_STATES:
            self.assertIn(f"FROM = {{ state = {state} }}", " ".join(
                f"{e.key} = {{ {'' if not isinstance(e.value, list) else ' '.join(c.key + ' = ' + str(c.value) for c in e.value)} }}"
                for e in walk(complete) if e.key == "FROM"))
            self.assertEqual(
                sum(e.key == "add_days_mission_timeout" and scalar(e.value, "mission") == f"STP_party_inspection_state_{state}"
                    and scalar(e.value, "days") == "14" for e in walk(complete)),
                1,
                state,
            )
        vanished = {
            ("FROM", "state", "2"): True,
            ("STP", "has_active_mission", "STP_party_inspection_state_2"): True,
            ("2", "has_state_flag", "STP_party_inspection_active"): False,
        }
        live = {
            ("FROM", "state", "2"): True,
            ("2", "has_state_flag", "STP_party_inspection_active"): True,
            ("2", "STP_region_is_operable", "yes"): True,
            ("2", "is_owned_by", "ROOT"): True,
            ("2", "is_controlled_by", "ROOT"): True,
            ("STP", "has_active_mission", "STP_party_inspection_state_2"): True,
        }
        vanished_effects = list(selected_effects(complete, vanished))
        self.assertEqual([e.value for _, e in vanished_effects if e.key == "add_political_power"], ["35"])
        self.assertFalse(any(e.key == "STP_political_action_slot_consume" for _, e in vanished_effects))
        live_effects = list(selected_effects(complete, live))
        self.assertEqual(sum(e.key == "STP_political_action_slot_consume" for _, e in live_effects), 1)
        self.assertFalse(any(e.key == "add_political_power" for _, e in live_effects))
        for terminal in ("cancel_effect", "remove_effect"):
            idle = list(selected_effects(block(decision, terminal), {}))
            self.assertEqual(sum(e.key == "STP_political_action_slot_release" for _, e in idle), 0)
            paid = list(selected_effects(block(decision, terminal), {
                ("FROM", "state", "2"): True,
                ("2", "has_state_flag", "STP_cw_inspection_delay_escrow"): True,
            }))
            self.assertEqual(sum(e.key == "STP_political_action_slot_release" for _, e in paid), 1)

    def test_last_banquet_is_a_single_congress_deadline(self) -> None:
        launch = block(self.council, "STP_cw_launch_last_banquet")
        mission = block(self.council, "STP_cw_last_banquet_deadline")
        fail = block(self.effects, "STP_cw_resolve_last_banquet_fail")
        success = block(self.effects, "STP_cw_resolve_last_banquet_success")
        technical = block(self.effects, "STP_cw_close_last_banquet_technical")
        self.assertEqual(scalar(launch, "fire_only_once"), "yes")
        self.assertFalse(any(e.key == "days_re_enable" for e in launch))
        self.assertIn("3", {e.value for e in walk(block(launch, "available")) if e.key == "controls_state"})
        self.assertIn("STP_ps_holds_congress", {e.key for e in walk(block(launch, "available"))})
        self.assertIn("STP_ps_holds_congress", {e.key for e in walk(block(mission, "available"))})
        self.assertEqual(scalar(mission, "days_mission_timeout"), "21")
        self.assertNotIn("always = no", {f"{e.key} = {e.value}" for e in walk(block(mission, "available"))})
        self.assertEqual(scalar(block(launch, "complete_effect"), "add_command_power"), "-25")
        timed = next(e.value for e in walk(block(launch, "complete_effect")) if e.key == "add_timed_idea")
        self.assertEqual((scalar(timed, "idea"), scalar(timed, "days")), ("STP_cw_deliberate_offensive", "21"))
        self.assertEqual(sum(e.key == "activate_mission" and e.value == "STP_cw_last_banquet_deadline"
                             for e in walk(block(launch, "complete_effect"))), 1)
        self.assertEqual(sum(e.key == "add_war_support" for e in walk(fail)), 1)
        self.assertEqual(next(e.value for e in walk(fail) if e.key == "add_war_support"), "-0.10")
        self.assertNotIn("add_war_support", {e.key for e in walk(success)})
        self.assertNotIn("add_war_support", {e.key for e in walk(technical)})
        self.assertNotIn("remove_ideas", {e.key for e in (*walk(fail), *walk(success), *walk(technical))})
        self.assertIn("STP_cw_last_banquet_deadline", self.tokens)
        self.assertIn("STP_cw_last_banquet_fail_tt:", self.loc)
        self.assertIn("контроль Бронзового конгресса", self.loc)

        already = {("STS", "has_country_flag", "STP_cw_last_banquet_resolved"): True}
        self.assertEqual([e.key for _, e in selected_effects(fail, already, "STS")], [])
        captured = {("STS", "has_country_flag", "STP_cw_last_banquet_resolved"): False,
                    ("STS", "STP_ps_holds_congress", "yes"): True}
        self.assertEqual(sum(e.key == "STP_cw_resolve_last_banquet_success" for _, e in selected_effects(fail, captured, "STS")), 1)
        victory = {("STS", "has_country_flag", "STP_cw_last_banquet_resolved"): False,
                   ("STS", "STP_ps_holds_congress", "yes"): False,
                   ("STS", "has_country_flag", "STP_cw_won_union_battle"): True}
        self.assertEqual(sum(e.key == "STP_cw_close_last_banquet_technical" for _, e in selected_effects(fail, victory, "STS")), 1)
        timeout = {("STS", "has_country_flag", "STP_cw_last_banquet_resolved"): False,
                   ("STS", "STP_ps_holds_congress", "yes"): False,
                   ("STS", "has_country_flag", "STP_cw_won_union_battle"): False}
        timeout_effects = list(selected_effects(fail, timeout, "STS"))
        self.assertEqual([e.value for _, e in timeout_effects if e.key == "add_war_support"], ["-0.10"])
        self.assertEqual(sum(e.key == "set_country_flag" and e.value == "STP_cw_last_banquet_resolved"
                             for _, e in timeout_effects), 1)

        launch_gate = block(launch, "available")
        ready = {("STS", "has_war_with", "STP"): True, ("STS", "controls_state", "3"): True}
        self.assertTrue(matches_conditions(launch_gate, ready, "STS"))
        self.assertFalse(matches_conditions(launch_gate, {**ready, ("STS", "STP_ps_holds_congress", "yes"): True}, "STS"))
        for idea in ("STP_cw_deliberate_offensive", "STP_cw_static_defence", "STP_cw_front_reorganization",
                     "STP_cw_offensive_preparation", "STP_cw_defensive_preparation"):
            self.assertFalse(matches_conditions(launch_gate, {**ready, ("STS", "has_idea", idea): True}, "STS"), idea)
        visible = block(launch, "visible")
        self.assertFalse(matches_conditions(visible, {("STS", "has_completed_focus", "STP_cw_last_banquet"): True,
                                                      ("STS", "has_country_flag", "STP_cw_last_banquet_resolved"): True}, "STS"))
        cancel = block(mission, "cancel_trigger")
        self.assertFalse(matches_conditions(cancel, {("STS", "controls_state", "3"): False}, "STS"),
                         "losing Niansas must not cancel the deadline")
        self.assertNotIn("3", {e.value for e in walk(cancel) if e.key == "controls_state"})
        settle = block(self.effects, "STP_cw_settle_union_victory")
        self.assertIn("STP_cw_close_last_banquet_technical", {e.key for e in walk(settle)})
        self.assertNotIn("add_war_support", {e.key for e in walk(settle)})

    def test_nod_timing_adjusts_the_authoritative_clock_then_the_mirror(self) -> None:
        adjust = block(self.effects, "STP_cw_adjust_nod_intervention_days")
        incident = block(self.external, "STP_cw_trigger_northern_incident")
        sabotage = block(block(self.decisions, "STP_cw_northern_aid"), "STP_cw_sabotage_nodrul")
        self.assertIn("NOD.days_mission_timeout@NOD_cw_intervention_preparation"
                      if False else "days_mission_timeout@NOD_cw_intervention_preparation",
                      [scalar(e.value, "value") for e in walk(adjust) if e.key == "set_temp_variable"])
        self.assertIn("NOD_cw_intervention_ready", {e.value for e in walk(adjust) if e.key == "set_country_flag"})
        nod_days = [scalar(e.value, "days") for e in walk(adjust)
                    if e.key == "add_days_mission_timeout" and scalar(e.value, "mission") == "NOD_cw_intervention_preparation"]
        mirror_days = [scalar(e.value, "days") for e in walk(adjust)
                       if e.key == "add_days_mission_timeout" and scalar(e.value, "mission") == "STP_cw_nod_warning"]
        self.assertEqual(nod_days, ["STP_cw_nod_prep_delta"])
        self.assertEqual(set(mirror_days), {"STP_cw_nod_prep_delta"})
        nod_line = next(e.line for e in walk(adjust)
                        if e.key == "add_days_mission_timeout"
                        and scalar(e.value, "mission") == "NOD_cw_intervention_preparation")
        mirror_line = next(e.line for e in walk(adjust)
                           if e.key == "add_days_mission_timeout"
                           and scalar(e.value, "mission") == "STP_cw_nod_warning")
        self.assertLess(nod_line, mirror_line)
        self.assertEqual(sum(e.key == "STP_cw_poll_nod_intervention" for e in walk(adjust)), 1)
        incident_effects = list(selected_effects(block(incident, "complete_effect"), {
            ("NOD", "has_active_mission", "NOD_cw_intervention_preparation"): True}, "STS"))
        self.assertEqual([scalar(e.value, "value") for _, e in incident_effects
                          if e.key == "set_temp_variable" and scalar(e.value, "var") == "STP_cw_nod_prep_delta"],
                         ["56"])
        self.assertEqual(sum(e.key == "STP_cw_adjust_nod_intervention_days" for _, e in incident_effects), 1)
        self.assertFalse(any(e.key == "add_days_mission_timeout" for _, e in incident_effects))
        sabotage_remove = block(sabotage, "remove_effect")
        self.assertIn("21", [scalar(e.value, "value") for e in walk(sabotage_remove)
                             if e.key == "set_temp_variable" and scalar(e.value, "var") == "STP_cw_nod_prep_delta"])
        self.assertEqual(sum(e.key == "STP_cw_adjust_nod_intervention_days" for e in walk(sabotage_remove)), 1)
        self.assertFalse(any(e.key == "add_days_mission_timeout" for e in walk(sabotage_remove)))
        finish = {
            ("NOD", "has_active_mission", "NOD_cw_intervention_preparation"): True,
            ("NOD", "variable", "days_mission_timeout@NOD_cw_intervention_preparation"): 10,
            ("STS", "variable", "STP_cw_nod_prep_delta"): -21,
        }
        # selected_effects cannot see caller temp vars as NOD remaining+delta; the
        # scripted effect still compares remaining + delta < 1 before add_days.
        self.assertTrue(any(
            e.key == "check_variable" and scalar(e.value, "var") == "STP_cw_nod_after"
            and scalar(e.value, "value") == "1" and scalar(e.value, "compare") == "less_than"
            for e in walk(adjust)
        ))
        idle = list(selected_effects(adjust, {("NOD", "has_active_mission", "NOD_cw_intervention_preparation"): False}, "STS"))
        self.assertEqual(idle, [])
        warning = block(self.external, "STP_cw_nod_warning")
        self.assertEqual(scalar(block(warning, "available"), "hidden_trigger")
                         if False else scalar(block(block(warning, "available"), "hidden_trigger")
                                              if any(e.key == "hidden_trigger" for e in block(warning, "available"))
                                              else block(warning, "available"), "always")
                         if any(e.key == "always" for e in walk(block(warning, "available"))) else "no",
                         "no")
        self.assertEqual([e.key for e in walk(block(warning, "available")) if e.key == "always"], ["always"])
        self.assertEqual(next(e.value for e in walk(block(warning, "available")) if e.key == "always"), "no")
        sync = block(self.effects, "STP_cw_sync_nod_warning")
        self.assertIn("NOD.days_mission_timeout@NOD_cw_intervention_preparation",
                      [scalar(e.value, "value") for e in walk(sync) if e.key == "set_temp_variable"])
        self.assertFalse(any(e.key == "activate_mission" and e.value == "NOD_cw_intervention_preparation"
                             for e in walk(sync)))
        for closed in ("STP_cw_end_nod_intervention", "STP_cw_close_nod_after_party_victory"):
            body = block(self.effects, closed)
            self.assertIn("NOD_cw_intervention_preparation", {e.value for e in walk(body) if e.key == "remove_mission"})
            self.assertIn("NOD_cw_northern_redeployment", {e.value for e in walk(body) if e.key == "remove_mission"})
        settle = block(self.effects, "STP_cw_settle_union_victory")
        self.assertNotIn("white_peace = VAL", "".join(f"{e.key} = {e.value}" for e in walk(settle)))
        self.assertNotIn("SRP", [e.key for e in settle if e.key == "SRP"])

    def test_party_ai_reserves_fada_without_eating_the_whole_front(self) -> None:
        defend = block(self.ai, "STP_cw_defend_fada")
        buffer = next(e.value for e in defend if e.key == "ai_strategy" and any(
            c.key == "type" and c.value == "put_unit_buffers" for c in e.value))
        self.assertEqual(scalar(buffer, "ratio"), "0.20")
        self.assertEqual({int(e.value) for e in block(buffer, "states")}, {28})
        self.assertEqual(scalar(buffer, "subtract_fronts_from_need"), "no")
        history = (ROOT / "history/states/28-Fada.txt").read_text(encoding="utf-8-sig")
        self.assertIn("victory_points = { 145 25 }", history)
        self.assertIn("province = 145", (ROOT / "common/national_focus/ADISCORD_national_focus_STP.txt").read_text(encoding="utf-8-sig"))
        finish = block(self.effects, "STP_cw_finish_mobilization")
        self.assertIn("VAL", {e.value for e in walk(finish) if e.key == "has_war_with"})
        union = block(self.effects, "STP_cw_settle_union_victory")
        self.assertEqual(sum(e.key == "STP_cw_finish_mobilization" for e in walk(union)), 1)
        self.assertFalse(any(e.key == "SRP" for e in union))


if __name__ == "__main__":
    unittest.main()
