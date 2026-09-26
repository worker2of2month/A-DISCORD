"""Party route contracts: branch reachability, displayed deltas and delayed settlement.

These tests inspect authored scripts, not the Clausewitz runtime.
"""
from pathlib import Path
import re
import unittest

from tools.validators.validate_adiscord_division_templates import parse_clausewitz
from tools.tests.test_adiscord_stp_preparation import matches_conditions, selected_effects
from tools.lib.focus_sources import read_focus_source

ROOT = Path(__file__).resolve().parents[2]
FOCUS = "common/national_focus/ADISCORD_STP_preparation.txt"
DECISIONS = "common/decisions/ADISCORD_STP_decisions.txt"
LOC = "localisation/russian/ADISCORD_STP_l_russian.yml"
SCRIPTED_LOC = "common/scripted_localisation/ADISCORD_STP_scripted_loc.txt"
EFFECTS = "common/scripted_effects/ADISCORD_STP_scripted_effects.txt"
DYNAMIC = "common/dynamic_modifiers/ADISCORD_dynamic_modifiers_STP.txt"
IDEAS = "common/ideas/ADISCORD_STP_civil_war_ideas.txt"
PLANS = "common/ai_strategy_plans/ADISCORD_STP_plans.txt"
EVENTS = "events/ADISCORD_STP_events.txt"
SCRIPTED_PEACE = "common/on_actions/09_ADISCORD_scripted_peace_on_actions.txt"
AI = "common/ai_strategy/ADISCORD_STP_civil_war.txt"


def read(path):
    return read_focus_source(ROOT / path)


def children(items, key):
    return [e.value for e in items if e.key == key]


def one(items, key):
    values = children(items, key)
    if len(values) != 1:
        raise AssertionError(f"expected one {key}, found {len(values)}")
    return values[0]


def walk(items):
    for item in items:
        yield item
        if isinstance(item.value, list):
            yield from walk(item.value)


def signature(items):
    return [(e.key, signature(e.value) if isinstance(e.value, list) else e.value) for e in items]


class PartyRouteContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.trees = parse_clausewitz(read(FOCUS))
        cls.focus = {one(f, "id"): f for t in children(cls.trees, "focus_tree") for f in children(t, "focus")}
        cls.decisions = {d.key: d.value for c in parse_clausewitz(read(DECISIONS)) for d in c.value if isinstance(d.value, list)}
        cls.loc = dict(re.findall(r'^\s*([^#\s:]+):(?:\d+)?\s*"(.*)"\s*$', read(LOC), re.M))
        cls.scripted_loc = {one(v.value, "name"): v.value for v in parse_clausewitz(read(SCRIPTED_LOC))}
        cls.effects = {e.key: e.value for e in parse_clausewitz(read(EFFECTS))}
        cls.dynamic = {e.key: e.value for e in parse_clausewitz(read(DYNAMIC))}
        cls.ideas = {e.key: e.value for c in children(parse_clausewitz(read(IDEAS)), "ideas") for group in children(c, "country") for e in group}

    def test_entire_election_briefing_switches_side(self):
        self.assertEqual(self.loc["STP_elections_in_the_party_desc"], "[STPGetElectionBriefing]")
        switch = self.scripted_loc["STPGetElectionBriefing"]
        texts = children(switch, "text")
        self.assertEqual(one(texts[0], "localization_key"), "STP_PARTY_ELECTION_BRIEFING")
        self.assertEqual(one(texts[-1], "localization_key"), "STP_RESISTANCE_ELECTION_BRIEFING")
        party = self.loc["STP_PARTY_ELECTION_BRIEFING"]
        self.assertNotIn("ложный след", party.lower())
        self.assertNotIn("пороги подозрения", party.lower())
        self.assertIn("70", party)
        self.assertIn("25", party)
        self.assertIn("ложный след", self.loc["STP_RESISTANCE_ELECTION_BRIEFING"])

    def test_search_outcome_colors_follow_the_observers_side(self):
        texts = children(self.scripted_loc["STPGetLastPartyResponse"], "text")
        self.assertEqual(one(texts[0], "localization_key"), "STP_PARTY_LAST_RESPONSE")
        self.assertTrue(self.loc["STP_PARTY_OUTCOME_10"].startswith("§G"))
        self.assertTrue(self.loc["STP_PARTY_OUTCOME_11"].startswith("§R"))
        self.assertTrue(self.loc["STP_PARTY_RESPONSE_COURIER_SEIZED"].startswith("§R"))

    def test_map_instructions_switch_without_exposing_the_army_ledger(self):
        description = self.loc["STP_battle_for_stelander_desc"]
        self.assertIn("[STPGetPreparationInstructions]", description)
        self.assertNotIn("STP_cw_report_party_brigades", description)
        self.assertNotIn("STP_cw_report_resistance_brigades", description)
        self.assertIn("STP_political_action_slots_available", description)
        self.assertIn("STP_PARTY_MAP_INSTRUCTIONS", str(signature(self.scripted_loc["STPGetPreparationInstructions"])))
        self.assertEqual(one(children(self.scripted_loc["STPGetInspectionStatus"], "text")[0], "localization_key"), "STP_REGION_PARTY_INSPECTION_STATUS")

    def reachable(self, chosen):
        done = {"STP_Govern_In_His_Name", "STP_cw_restore_civil_authority"}
        changed = True
        while changed:
            changed = False
            for fid, f in self.focus.items():
                if fid in done:
                    continue
                excludes = [e.value for group in children(f, "mutually_exclusive") for e in group if e.key == "focus"]
                if any(ex in chosen or ex in done for ex in excludes):
                    continue
                prereqs = children(f, "prerequisite")
                if not prereqs:
                    continue
                if all(any(e.value in done for e in p if e.key == "focus") for p in prereqs):
                    done.add(fid)
                    changed = True
        return done

    def test_fiscal_specialization_does_not_remove_basic_state_or_defence(self):
        for chosen in ("STP_GUARANTEE_MINISTERS", "STP_defense_budget"):
            with self.subTest(chosen=chosen):
                done = self.reachable({chosen})
                self.assertIn(chosen, done)
                for fid in ("STP_DISTRICT_GOVERNMENT", "STP_cw_capital_reserve", "STP_cw_protect_congress", "STP_cw_press_office"):
                    self.assertIn(fid, done)

    def test_both_district_methods_reach_presidium_and_mandate(self):
        for chosen in ("STP_party_district_compact", "STP_ROTATE_DISTRICT_COMMAND"):
            with self.subTest(chosen=chosen):
                self.assertIn(chosen, self.focus)
                done = self.reachable({chosen})
                self.assertIn("STP_EMERGENCY_PRESIDIUM", done)
                self.assertIn("STP_cw_party_mandate", done)
        self.assertNotIn("STP_cw_secure_party_district", str(signature(one(self.focus["STP_party_district_compact"], "completion_reward"))))

    def test_prewar_tactical_combinations_reach_supply_and_mandate(self):
        from itertools import product
        axes = (("STP_GUARANTEE_MINISTERS", "STP_defense_budget"),
                ("STP_party_district_compact", "STP_ROTATE_DISTRICT_COMMAND"),
                ("STP_cw_protect_congress", "STP_cw_capital_oath"))
        for choices in product(*axes):
            with self.subTest(choices=choices):
                done = self.reachable(set(choices))
                self.assertTrue(set(choices) <= done)
                self.assertTrue({"STP_party_supply_directorate", "STP_cw_party_mandate"} <= done)
                for axis, chosen in zip(axes, choices):
                    self.assertNotIn(next(fid for fid in axis if fid != chosen), done)

    def test_district_courses_unlock_only_their_own_operation(self):
        for operation, chosen, other in (
            ("STP_cw_agree_with_commander", "STP_party_district_compact", "STP_ROTATE_DISTRICT_COMMAND"),
            ("STP_cw_check_district_command", "STP_ROTATE_DISTRICT_COMMAND", "STP_party_district_compact"),
        ):
            for section in ("visible", "available"):
                gate = one(self.decisions[operation], section)
                self.assertIn(chosen, [e.value for e in walk(gate) if e.key == "has_completed_focus"])
                self.assertNotIn(other, [e.value for e in walk(gate) if e.key == "has_completed_focus"])
        survey = one(self.focus["STP_PARTY_DISCIPLINE"], "completion_reward")
        self.assertNotIn("STP_cw_secure_party_district", [e.key for e in walk(survey)])

    def test_mobile_reserve_is_paid_before_base_army_and_bonus_waits_for_hostilities(self):
        marker = "STP_party_mobile_reserve_ready"
        start = self.effects["STP_cw_start"]
        mobile = next(e.value for e in walk(start) if e.key == "if"
                      and marker in str(signature(one(e.value, "limit"))))
        self.assertEqual([e.key for e in mobile].count("STP_cw_mobilize_brigade"), 2)
        source = str(signature(start))
        self.assertLess(source.index(marker), source.index("STP_cw_mobilize_assault_division"))
        self.assertNotIn("STP_cw_offensive_preparation", source)
        for ready in (False, True):
            facts = {("STP", "has_country_flag", marker): ready}
            issued = [e.key for _, e in selected_effects([next(e for e in walk(start)
                      if e.key == "if" and e.value == mobile)], facts)]
            self.assertEqual(issued.count("STP_cw_mobilize_brigade"), 2 if ready else 0)
        begin = str(signature(self.effects["STP_cw_begin_hostilities"]))
        self.assertIn("STP_cw_offensive_preparation", begin)
        self.assertIn("('clr_country_flag', '" + marker + "')", begin)
        self.assertIn(marker, str(signature(self.effects["STP_cw_finish_mobilization"])))
        forecast = str(signature(self.effects["STP_cw_refresh_army_report"]))
        self.assertIn(marker, forecast)

    def test_first_intercept_includes_every_prerequisite_day(self):
        root = "STP_Govern_In_His_Name"
        def days(fid):
            if fid == root:
                return 0  # side selection completes this focus by event
            f = self.focus[fid]
            blocks = children(f, "prerequisite")
            return int(float(one(f, "cost")) * 7) + sum(min(days(e.value) for e in p if e.key == "focus") for p in blocks)
        response = days("STP_cw_security_collegium") + int(one(self.decisions["STP_cw_interrupt_opposition"], "days_remove"))
        # First mission: 28 + 32 days, reduced by seven at loyalty below 25.
        self.assertLess(response, 53)
        self.assertIn("value = 70", read(EFFECTS))

    def test_late_election_callbacks_cannot_move_a_finished_election(self):
        for name in ("STP_cw_seal_protocol", "STP_cw_publish_directive"):
            payload = one(self.decisions[name], "remove_effect")
            actual = list(selected_effects(payload, {}))
            self.assertFalse(any(e.key in ("add_power_balance_value", "add_stability") for _, e in actual), name)
            self.assertTrue(any(e.key == "STP_political_action_slot_release" for _, e in actual), name)
            facts = {("STP", "STP_cw_preparation_open", "yes"): True,
                     ("STP", "has_country_flag", "STP_battle_for_stelander_active"): True,
                     ("STP", "has_active_mission", "STP_cw_election_window"): True}
            self.assertTrue(any(e.key == "add_power_balance_value" for _, e in selected_effects(payload, facts)), name)

    def test_both_postwar_settlements_keep_distinct_capstones_before_the_charter(self):
        paths = {
            "STP_pw_party_open_settlement": (
                "STP_party_district_charters", "STP_party_local_cadres", "STP_pw_party_district_congress"),
            "STP_pw_party_firm_settlement": (
                "STP_party_personnel_commissions", "STP_party_chain_of_command", "STP_pw_party_executive_secretariat"),
        }
        for choice, branch in paths.items():
            done = self.reachable({choice})
            for fid in branch:
                self.assertIn(fid, done)
            self.assertIn("STP_pw_party_civil_charter", done)
        charter = children(self.focus["STP_pw_party_civil_charter"], "prerequisite")
        self.assertEqual(len(charter), 1)
        self.assertEqual(set(e.value for e in charter[0]), {v[-1] for v in paths.values()})

    def test_economic_choice_stays_separate_until_branch_capstone(self):
        paths = {
            "STP_pw_party_civil_workshops": ("STP_party_port_contracts", "STP_pw_party_commercial_recovery"),
            "STP_pw_party_accountable_arsenals": ("STP_party_industrial_board", "STP_pw_party_defence_combine"),
        }
        for chosen, branch in paths.items():
            done = self.reachable({chosen})
            self.assertIn("STP_party_revenue_service", done)
            for fid in branch:
                self.assertIn(fid, done)
            self.assertIn("STP_pw_party_industrial_settlement", done)
        settlement = children(self.focus["STP_pw_party_industrial_settlement"], "prerequisite")
        self.assertEqual(set(e.value for e in settlement[0]), {v[-1] for v in paths.values()})

    def test_army_choice_is_logistics_or_field_service_not_a_linear_chain(self):
        supply = self.focus["STP_pw_party_supply_service"]
        field = self.focus["STP_pw_party_professional_service"]
        self.assertIn("STP_pw_party_professional_service",
                      [e.value for g in children(supply, "mutually_exclusive") for e in g])
        self.assertIn("STP_pw_party_supply_service",
                      [e.value for g in children(field, "mutually_exclusive") for e in g])
        for chosen, capstone in (
            ("STP_pw_party_supply_service", "STP_pw_party_fortress_corps"),
            ("STP_pw_party_professional_service", "STP_pw_party_field_staff"),
        ):
            done = self.reachable({chosen})
            self.assertIn(capstone, done)
            self.assertIn("STP_pw_party_border_staff", done)
            self.assertIn("STP_pw_party_southern_defence", done)

    def test_foreign_axis_is_independent_and_required_for_final_settlement(self):
        forbidden = {"STP_pw_party_open_settlement", "STP_pw_party_firm_settlement",
                     "STP_party_local_cadres", "STP_party_chain_of_command"}
        for fid in ("STP_pw_party_northern_protocol", "STP_pw_party_protectorate", "STP_pw_party_sovereignty"):
            f = self.focus[fid]
            self.assertFalse(any(e.value in forbidden for p in children(f, "prerequisite") for e in p))
        self.assertEqual(one(self.focus["STP_pw_party_protectorate"], "cancel_if_invalid"), "yes")
        foreign = children(self.focus["STP_pw_party_foreign_settlement"], "prerequisite")
        self.assertEqual(set(e.value for e in foreign[0]),
                         {"STP_pw_party_joint_defence_board", "STP_pw_party_armed_neutrality"})
        final_requirements = {
            e.value for p in children(self.focus["STP_pw_party_settled_state"], "prerequisite") for e in p
        }
        self.assertIn("STP_pw_party_foreign_settlement", final_requirements)

    def test_postwar_party_gets_bezhaysk_and_kefreyt_campaigns(self):
        root = self.focus["STP_pw_party_external_mandate"]
        self.assertIn(
            "STP_pw_party_settled_state",
            [e.value for p in children(root, "prerequisite") for e in p],
        )
        for focus_id, decision_id, target in (
            ("STP_pw_party_bezhaysk_campaign", "STP_pw_party_launch_bezhaysk_operation", "BJK"),
            ("STP_pw_party_kefreyt_campaign", "STP_pw_party_launch_kefreyt_operation", "VAL"),
        ):
            focus = self.focus[focus_id]
            self.assertIn(
                "STP_pw_party_external_mandate",
                [e.value for p in children(focus, "prerequisite") for e in p],
            )
            reward = one(focus, "completion_reward")
            self.assertIn(decision_id, [e.value for e in walk(reward) if e.key == "decision"])
            decision = self.decisions[decision_id]
            self.assertIn("tag", [e.key for e in one(decision, "allowed")])
            self.assertIn(target, [e.value for e in walk(one(decision, "complete_effect")) if e.key == "target"])

        final = self.focus["STP_pw_party_regional_order"]
        prerequisites = {e.value for p in children(final, "prerequisite") for e in p if e.key == "focus"}
        self.assertEqual(prerequisites, {"STP_pw_party_bezhaysk_campaign", "STP_pw_party_kefreyt_campaign"})
        triggers = read("common/scripted_triggers/ADISCORD_STP_scripted_triggers.txt")
        self.assertIn("STP_pw_party_can_attack_bezhaysk = {", triggers)
        self.assertIn("STP_pw_party_can_attack_kefreyt = {", triggers)
        self.assertIn("STP_pw_party_external_order_resolved = {", triggers)
        plan = read(PLANS)
        for focus_id in (
            "STP_pw_party_external_mandate",
            "STP_pw_party_bezhaysk_campaign",
            "STP_pw_party_kefreyt_campaign",
            "STP_pw_party_regional_order",
        ):
            self.assertIn(focus_id, plan)

    def test_sovereignty_opens_a_terminal_nod_invasion_crisis(self):
        sovereignty = one(self.focus["STP_pw_party_sovereignty"], "completion_reward")
        self.assertIn("STP_pw_party_start_nod_invasion_threat", str(signature(sovereignty)))
        mission = self.decisions["STP_pw_party_nod_invasion_countdown"]
        self.assertEqual(one(mission, "days_mission_timeout"), "90")
        self.assertEqual(one(mission, "selectable_mission"), "no")
        self.assertIn("always", str(signature(one(mission, "available"))))
        self.assertIn("STP_pw_party_launch_nod_invasion", str(signature(one(mission, "timeout_effect"))))
        effects = read(EFFECTS)
        launch = effects[effects.index("STP_pw_party_launch_nod_invasion = {"):]
        launch = launch[:launch.index("\nSTP_pw_party_settle_nod_invasion_defeat = {")]
        self.assertIn("declare_war_on = { target = STP type = annex_everything }", launch)
        self.assertIn("add_timed_idea = { idea = STP_pw_nod_invasion_mandate days = 365 }", launch)
        ideas = read(IDEAS)
        mandate = ideas[ideas.index("STP_pw_nod_invasion_mandate = {"):]
        mandate = mandate[:mandate.index("\n\t\t}") + 4]
        for token in ("army_attack_factor = 0.20", "army_org_factor = 0.15",
                      "army_org_regain = 0.10", "planning_speed = 0.25",
                      "breakthrough_factor = 0.15", "supply_consumption_factor = -0.15"):
            self.assertIn(token, mandate)
        events = read(EVENTS)
        nod_offer = events[events.index("\tid = ADISCORD_STP_pc.19\n"):]
        nod_offer = nod_offer[:nod_offer.index("\n}\ncountry_event", 1)]
        self.assertIn("name = ADISCORD_STP_pc.19.refuse\n\t\tai_chance = { base = 0 }", nod_offer)
        self.assertIn("name = ADISCORD_STP_pc.19.accept", nod_offer)
        self.assertIn("ai_chance = { base = 100 }", nod_offer)

    def test_nod_crisis_has_three_real_preparation_decisions(self):
        expected = {
            "STP_pw_party_nod_emergency_mobilization": ("900", "50", "3", "STP_pf_security_deal_tt"),
            "STP_pw_party_nod_fortify_border": ("1080", "35", "2", "STP_pf_borons_deal_tt"),
            "STP_pw_party_nod_staff_readiness": ("720", "35", "4", "STP_pf_army_deal_tt"),
        }
        raw = read(DECISIONS)
        selectors = []
        for decision_id, (money, pp, selector, tooltip) in expected.items():
            decision = self.decisions[decision_id]
            self.assertEqual(one(decision, "cost"), "0")
            self.assertTrue(any(e.key == "add_political_power" and e.value == "-" + pp for e in walk(one(decision, "complete_effect"))))
            self.assertIn("STP_pw_party_nod_threat_active", str(signature(one(decision, "visible"))))
            reward = one(decision, "complete_effect")
            self.assertTrue(any(e.key == "custom_effect_tooltip" and e.value == tooltip for e in walk(reward)))
            self.assertTrue(any(e.key == "var" and e.value == "STP_pf_selected" for e in walk(reward)))
            from tools.tests.test_adiscord_stp_party_balance import named_block
            snippet = named_block(raw, decision_id)
            self.assertIn(f"value = {money}", snippet)
            self.assertIn(f"var = STP_pf_selected value = {selector}", snippet)
            self.assertEqual(snippet.count("STP_pf_shift = yes"), 1)
            selectors.append(selector)
        self.assertEqual(selectors, ["3", "2", "4"])
        self.assertEqual(selectors.count("4"), 1, "automatic crisis preparation must not create an army monopoly")
        self.assertIn("any_neighbor_state", str(signature(self.decisions["STP_pw_party_nod_fortify_border"])))

    def test_protectorate_deepens_adviser_influence_in_paid_and_institutional_steps(self):
        effects = read(EFFECTS)
        arms = effects[effects.index("STP_pw_party_settle_nod_arms = {"):]
        arms = arms[:arms.index("\n# COUNTRY STS:", 1)]
        self.assertIn("var = STP_pf_selected value = 5", arms)
        self.assertEqual(arms.count("STP_pf_shift = yes"), 1)
        board = one(self.focus["STP_pw_party_joint_defence_board"], "completion_reward")
        self.assertTrue(any(e.key == "var" and e.value == "STP_pf_selected" for e in walk(board)))
        self.assertTrue(any(e.key == "STP_pf_shift" and e.value == "yes" for e in walk(board)))

    def test_independent_foreign_settlement_waits_for_nod_outcome(self):
        available = str(signature(one(self.focus["STP_pw_party_foreign_settlement"], "available")))
        self.assertIn("is_subject_of", available)
        self.assertIn("STP_pw_party_nod_invasion_defeated", available)

    def test_nod_invasion_loss_is_terminal_for_the_party_country(self):
        peace = read(SCRIPTED_PEACE)
        self.assertIn("STP_pw_party_settle_nod_invasion_victory = yes", peace)
        self.assertIn("STP_pw_party_settle_nod_invasion_defeat = yes", peace)
        effects = read(EFFECTS)
        terminal = effects[effects.index("STP_pw_party_settle_nod_invasion_victory = {"):]
        self.assertIn("annex_country = { target = STP transfer_troops = yes }", terminal)
        self.assertIn("set_country_flag = STP_pw_party_nod_invasion_lost", terminal)

    def test_nod_victory_closes_competing_kefreyt_ultimatum_before_annex(self):
        effects = read(EFFECTS)
        start = effects.index("STP_pw_party_settle_nod_invasion_victory = {")
        end = effects.index("\n# Party defensive recovery.", start)
        terminal = effects[start:end]
        cleanup = terminal.index("STP_close_competing_ultimatum_wars_after_defeat = yes")
        annex = terminal.index("annex_country = { target = STP transfer_troops = yes }")
        self.assertLess(cleanup, annex)

    def test_nod_invasion_events_and_ai_profile_are_registered(self):
        events = read(EVENTS)
        for number in (28, 29, 30):
            event_id = f"ADISCORD_STP_pc.{number}"
            self.assertEqual(events.count(f"\tid = {event_id}\n"), 1)
            for suffix in ("t", "d", "a"):
                self.assertIn(f"{event_id}.{suffix}", self.loc)
        ai = read(AI)
        self.assertIn("NOD_pw_party_invasion_front = {", ai)
        self.assertIn("front_unit_request tag = STP value = 140", ai)
        self.assertIn("conquer id = STP value = 300", ai)

    def test_party_income_and_credit_deltas_have_real_consumers(self):
        d = self.dynamic["STP_pw_party_dynamic"]
        for modifier in ("ADISCORD_economy_overall_income_factor", "ADISCORD_economy_creditworthiness_factor", "ADISCORD_economy_treasury_capacity_factor"):
            self.assertEqual(one(d, modifier), "STP_pw_" + modifier)
        self.assertIn("ADISCORD_economy_mark_dirty", str(signature(self.effects["STP_pw_refresh_modifier"])))

    def test_new_focus_dummies_exactly_match_live_aggregate_deltas(self):
        found = 0
        for fid, f in self.focus.items():
            if not fid.startswith("STP_party_"):
                continue
            found += 1
            reward = one(f, "completion_reward")
            modifiers = {}
            for e in walk(reward):
                if e.key == "add_to_variable":
                    var = one(e.value, "var")
                    if var.startswith(("STP_pw_", "STP_cw_party_", "STP_cw_army_")):
                        modifiers[var] = float(one(e.value, "value"))
            previews = [e.value for e in walk(reward) if e.key == "add_idea" and isinstance(e.value, str) and e.value.endswith("_delta")]
            displayed = {}
            for key in previews:
                idea = self.ideas[key]
                self.assertEqual(signature(one(idea, "allowed")), [("always", "no")])
                dynamic = self.dynamic[one(idea, "name")]
                for e in one(idea, "modifier"):
                    displayed[one(dynamic, e.key)] = float(e.value)
            self.assertEqual(displayed, modifiers, fid)
        self.assertGreaterEqual(found, 18)

    def test_assault_focus_unlocks_a_paid_order_instead_of_silent_spawn_attempt(self):
        reward = one(self.focus["STP_cw_assault_columns"], "completion_reward")
        self.assertNotIn("STP_cw_mobilize_assault_division", str(signature(reward)))
        self.assertIn("STP_party_form_assault_column",
                      {v if isinstance(v, str) else one(v, "decision")
                       for v in children(reward, "unlock_decision_tooltip")})
        d = self.decisions["STP_party_form_assault_column"]
        self.assertEqual(one(d, "cost"), "0")
        self.assertEqual(one(d, "days_re_enable"), "21")
        self.assertIn("STP_cw_can_pay_assault_division", str(signature(one(d, "available"))))
        self.assertIn("STP_cw_mobilize_assault_division", str(signature(one(d, "complete_effect"))))
        for suffix in ("", "_blocked", "_tooltip"):
            self.assertIn("STP_party_assault_price" + suffix, self.loc)

    def test_party_plans_abort_at_phase_boundaries(self):
        plans = {e.key:e.value for e in parse_clausewitz(read(PLANS))}
        for name in ("STP_party_preparation_plan", "STP_party_civil_war_plan", "STP_party_reconstruction_plan"):
            self.assertIn(name, plans)
            self.assertTrue(children(plans[name], "enable"))
            self.assertTrue(children(plans[name], "abort"))
            self.assertTrue(children(plans[name], "ai_national_focuses"))

    def test_new_focuses_and_tooltips_are_localized_and_phase_scoped(self):
        for fid, f in self.focus.items():
            if fid.startswith("STP_party_"):
                for suffix in ("", "_desc"):
                    self.assertIn(fid + suffix, self.loc)
                self.assertEqual(one(f, "cancel_if_invalid"), "yes")
                self.assertTrue(children(f, "available"))
                for e in walk(f):
                    if e.key in ("custom_effect_tooltip", "tooltip"):
                        self.assertIn(e.value, self.loc)

    def test_party_order_template_is_fixed_before_any_wartime_edit(self):
        locks = self.effects["STP_cw_apply_wartime_template_locks"]
        for tag in ("STP", "STS", "SRP"):
            facts = {(tag, "tag", tag): True}
            chosen = [e for _, e in selected_effects(locks, facts, tag) if e.key == "set_division_template_lock" and one(e.value, "division_template") == "Stelander Assault Division"]
            self.assertEqual(len(chosen), 1)
            self.assertEqual(one(chosen[0].value, "is_locked"), "yes" if tag == "STP" else "no")
        finish = self.effects["STP_cw_finish_mobilization"]
        self.assertIn(("set_division_template_lock", [("division_template", "Stelander Assault Division"), ("is_locked", "no")]), [x for _, e in selected_effects(finish, {("STP", "has_country_flag", "STP_cw_templates_loaded"): True}) for x in signature([e])])

    def test_assault_price_checks_every_exact_fractional_boundary(self):
        triggers = {e.key: e.value for e in parse_clausewitz(read("common/scripted_triggers/ADISCORD_STP_scripted_triggers.txt"))}
        prices = {"manpower":7900, "infantry_equipment":610, "ADISCORD_squad_weapons_equipment":48,
                  "support_equipment":30, "artillery_equipment":60, "anti_air_equipment":20}
        for currency, amount in prices.items():
            for delta in (-0.01, 0, 0.01):
                facts = {("STP", "numeric", "has_manpower"):prices["manpower"]}
                facts.update({("STP", "equipment", key): value for key, value in prices.items() if key != "manpower"})
                key = ("STP", "numeric", "has_manpower") if currency == "manpower" else ("STP", "equipment", currency)
                facts[key] = amount + delta
                with self.subTest(currency=currency, delta=delta):
                    self.assertEqual(matches_conditions(triggers["STP_cw_can_pay_assault_division"], facts), delta >= 0)

    def test_party_narrative_responses_are_context_specific(self):
        labels = [
            self.loc["ADISCORD_STP_pc.23.a"],
            self.loc["ADISCORD_STP_pc.24.accepted_a"],
            self.loc["ADISCORD_STP_pc.24.refused_a"],
            self.loc["ADISCORD_STP_pc.25.a"],
            self.loc["ADISCORD_STP_pc.26.a"],
            self.loc["ADISCORD_STP_pc.27.a"],
        ]
        self.assertEqual(len(labels), len(set(labels)))
        for generic in ("Продолжать", "Принять доклад.", "Принять к сведению"):
            self.assertNotIn(generic, labels)
        events = read(EVENTS)
        self.assertIn("name = ADISCORD_STP_pc.24.accepted_a", events)
        self.assertIn("trigger = { has_country_flag = STP_pw_party_nod_arms_delivered }", events)
        self.assertIn("name = ADISCORD_STP_pc.24.refused_a", events)
        self.assertIn("trigger = { NOT = { has_country_flag = STP_pw_party_nod_arms_delivered } }", events)
        self.assertNotRegex(events, r"(?m)^\s*name = ADISCORD_STP_pc\.24\.a\s*$")

    def test_no_internal_party_balance_added(self):
        text = read("common/bop/STP.txt")
        self.assertNotIn("STP_party_cells", text)
        self.assertNotIn("STP_party_factions", text)
        for fid, f in self.focus.items():
            if fid.startswith("STP_party_"):
                self.assertNotIn("set_power_balance", str(signature(f)))

    def test_encoding_and_one_line_localisation(self):
        self.assertTrue((ROOT / LOC).read_bytes().startswith(b"\xef\xbb\xbf"))
        for path in (FOCUS, DECISIONS, EFFECTS, SCRIPTED_LOC, DYNAMIC, IDEAS):
            self.assertFalse((ROOT / path).read_bytes().startswith(b"\xef\xbb\xbf"), path)
        for line in read(LOC).splitlines():
            if not line.strip() or line.lstrip().startswith(("#", "l_russian:")):
                continue
            self.assertRegex(line, r'^\s*[^\s:]+:(?:\d+)?\s*".*"\s*(?:#.*)?$')


class PartyFactionContracts(unittest.TestCase):
    """Exercise authored arithmetic; this is not proof of native script loading."""

    KEYS = ("conservatives", "borons", "security", "army", "advisers", "merchants", "radicals")

    @classmethod
    def setUpClass(cls):
        cls.effects = {e.key: e.value for e in parse_clausewitz(read(EFFECTS))}
        cls.triggers = {e.key: e.value for e in parse_clausewitz(read("common/scripted_triggers/ADISCORD_STP_scripted_triggers.txt"))}

    def test_dominant_faction_can_recover_support_without_more_influence(self):
        for influence in (60, 64.999, 96, 99, 100):
            values, flags = self.simulate("STP_pf_initialize")
            for key in self.KEYS:
                values[f"STP_pf_{key}_influence"] = 0
            values["STP_pf_conservatives_influence"] = str(100 - influence)
            values["STP_pf_army_influence"] = influence
            values["STP_pf_army_support"] = 0
            for _ in range(5):
                values["STP_pf_selected"] = 4
                self.simulate("STP_pf_shift", values, flags)
            self.assertAlmostEqual(float(values["STP_pf_army_influence"]), influence)
            self.assertEqual(values["STP_pf_army_support"], 60)

    def simulate(self, effect, values=None, flags=None, tag="STP", nod=True, quantize=False, focuses=()):
        from decimal import Decimal, ROUND_DOWN
        values = {} if values is None else values
        flags = {"STP_sided_with_the_party_flag"} if flags is None else flags

        def number(value):
            try:
                return Decimal(value)
            except Exception:
                return Decimal(str(values.get(value, 0)))

        def condition(items):
            results = []
            for e in items:
                if e.key in ("AND", "hidden_trigger"):
                    result = condition(e.value)
                elif e.key == "OR":
                    result = any(condition([child]) for child in e.value)
                elif e.key == "NOT":
                    result = not condition(e.value)
                elif e.key == "STP_pf_nod_contacts":
                    result = nod == (e.value == "yes")
                elif e.key in self.triggers:
                    result = condition(self.triggers[e.key]) == (e.value == "yes")
                elif e.key == "tag":
                    result = tag == e.value
                elif e.key == "exists":
                    result = e.value == "yes"
                elif e.key == "has_country_flag":
                    result = e.value in flags
                elif e.key == "has_completed_focus":
                    result = e.value in focuses
                elif e.key == "has_variable":
                    result = e.value in values
                elif e.key == "has_dynamic_modifier":
                    result = False
                elif e.key == "check_variable":
                    left, right = number(one(e.value, "var")), number(one(e.value, "value"))
                    result = {"equals": left == right, "greater_than": left > right,
                              "greater_than_or_equals": left >= right, "less_than": left < right,
                              "less_than_or_equals": left <= right}[one(e.value, "compare")]
                else:
                    raise AssertionError(f"Unsupported arithmetic fixture condition: {e.key}")
                results.append(result)
            return all(results)

        def execute(items):
            taken = False
            for e in items:
                if e.key in ("if", "else_if", "else"):
                    if e.key == "if":
                        taken = False
                    if not taken and (e.key == "else" or condition(one(e.value, "limit"))):
                        taken = True
                        execute([child for child in e.value if child.key != "limit"])
                elif e.key in self.effects and e.key.startswith(("STP_pf_", "STP_refresh_apparatus", "STP_change_apparatus")):
                    self.assertEqual(e.value, "yes")
                    execute(self.effects[e.key])
                elif e.key in ("set_variable", "add_to_variable", "subtract_from_variable", "multiply_variable", "divide_variable",
                               "set_temp_variable", "add_to_temp_variable", "subtract_from_temp_variable", "multiply_temp_variable", "divide_temp_variable"):
                    name, amount = one(e.value, "var"), number(one(e.value, "value"))
                    old = number(name)
                    operation = e.key.split("_")[0]
                    if operation == "set": result = amount
                    elif operation == "add": result = old + amount
                    elif operation == "subtract": result = old - amount
                    elif operation == "multiply": result = old * amount
                    else: result = old / amount
                    values[name] = result.quantize(Decimal("0.001"), rounding=ROUND_DOWN) if quantize else result
                elif e.key == "clamp_variable":
                    name = one(e.value, "var")
                    values[name] = max(number(one(e.value, "min")), min(number(one(e.value, "max")), number(name)))
                elif e.key == "clear_variable":
                    values.pop(e.value, None)
                elif e.key == "set_country_flag":
                    flags.add(e.value)
                elif e.key == "clr_country_flag":
                    flags.discard(e.value)
                elif e.key in ("force_update_dynamic_modifier", "add_dynamic_modifier", "remove_dynamic_modifier", "ADISCORD_economy_mark_dirty"):
                    pass
                else:
                    raise AssertionError(f"Unsupported arithmetic fixture effect: {e.key}")
        execute(self.effects[effect])
        return values, flags

    def test_initialization_preserves_old_loyalty_and_does_not_reset_on_reopen(self):
        for initial in (0, 40, 73, 100):
            values, flags = self.simulate("STP_pf_initialize", {"STP_apparatus_loyalty": initial})
            self.assertEqual(values["STP_apparatus_loyalty"], initial)
            self.assertEqual(sum(values[f"STP_pf_{k}_influence"] for k in self.KEYS), 100)
            snapshot = dict(values)
            self.simulate("STP_pf_initialize", values, flags)
            self.assertEqual(values, snapshot)
        values, flags = self.simulate("STP_pf_initialize", tag="STS")
        self.assertNotIn("STP_pf_initialized", flags)
        self.assertFalse(values)

    def test_long_redistribution_sequences_conserve_influence_and_bound_support(self):
        import random
        for quantize in (False, True):
            values, flags = self.simulate("STP_pf_initialize", quantize=quantize)
            rng = random.Random(2160)
            for _ in range(500):
                values["STP_pf_selected"] = rng.randint(1, 7)
                self.simulate("STP_pf_shift", values, flags, quantize=quantize)
                weights = [values[f"STP_pf_{k}_influence"] for k in self.KEYS]
                self.assertAlmostEqual(float(sum(weights)), 100, places=8)
                self.assertTrue(all(0 <= weight <= 100 for weight in weights))
                self.assertTrue(all(0 <= values[f"STP_pf_{k}_support"] <= 100 for k in self.KEYS))
                expected = sum(values[f"STP_pf_{k}_support"] * values[f"STP_pf_{k}_influence"] for k in self.KEYS) / 100
                self.assertAlmostEqual(float(values["STP_apparatus_loyalty"]), float(expected), delta=0.008)

    def test_general_rewards_and_opposed_deals_have_no_free_support_cycle(self):
        values, flags = self.simulate("STP_pf_initialize")
        values["STP_apparatus_loyalty_change"] = 6
        self.simulate("STP_change_apparatus_loyalty", values, flags)
        self.assertEqual(values["STP_apparatus_loyalty"], 46)
        for selected in (1, 7):
            values["STP_pf_selected"] = selected
            self.simulate("STP_pf_shift", values, flags)
        self.assertTrue(all(values[f"STP_pf_{k}_support"] == 46 for k in self.KEYS))
        values["STP_apparatus_loyalty_change"] = 100
        self.simulate("STP_change_apparatus_loyalty", values, flags)
        self.assertAlmostEqual(float(values["STP_apparatus_loyalty"]), 100)

    def test_invalid_selector_does_not_mutate_factions_and_no_contacts_removes_aid(self):
        values, flags = self.simulate("STP_pf_initialize")
        snapshot = {k: v for k, v in values.items() if k.endswith(("_influence", "_support"))}
        for selected in (0, 8):
            values["STP_pf_selected"] = selected
            self.simulate("STP_pf_shift", values, flags)
            self.assertEqual({k: v for k, v in values.items() if k in snapshot}, snapshot)
        values["STP_pf_advisers_support"] = 100
        self.simulate("STP_refresh_apparatus_loyalty", values, flags, nod=False)
        self.assertEqual(values["STP_pf_advisers_effect"], 0)
        self.assertEqual(values["STP_pf_advisers_support"], 100)

    def test_terminal_cleanup_and_wartime_persistence(self):
        values, flags = self.simulate("STP_pf_initialize")
        self.simulate("STP_pf_clear", values, flags)
        self.assertNotIn("STP_pf_initialized", flags)
        self.assertFalse(any(f"STP_pf_{k}_influence" in values for k in self.KEYS))
        self.assertIn("STP_pf_active", str(signature(self.effects["STP_end_battle_for_stelander"])))
        self.assertIn("STP_pf_clear", str(signature(self.effects["STP_cw_settle_union_victory"])))

    def test_all_cards_actions_and_cooldowns_use_the_same_seven_factions(self):
        categories = parse_clausewitz(read(DECISIONS))
        decisions = [e for e in one(categories, "STP_party_factions")
                     if e.key.startswith("STP_pf_negotiate_")]
        self.assertEqual(len(decisions), 7)
        gui = read("interface/ADISCORD_STP_regions.gui")
        script = read("common/scripted_guis/ADISCORD_STP_regions_scripted_gui.txt")
        for k in self.KEYS:
            action = one(decisions, f"STP_pf_negotiate_{k}")
            self.assertEqual(one(action, "cost"), "35")
            writes = list(walk(one(action, "complete_effect")))
            self.assertFalse(any(e.key == "add_political_power" for e in writes))
            cooldown = next(e.value for e in writes if e.key == "set_country_flag")
            self.assertEqual(one(cooldown, "flag"), "STP_pf_negotiation_cooldown")
            self.assertEqual(one(cooldown, "days"), "30")
            self.assertEqual(one(cooldown, "value"), "1")
            self.assertIn(f'name = "STP_pf_{k}_card"', gui)
            self.assertIn(f"frame = STP_pf_{k}_frame", script)




class PartySecondPackageContracts(unittest.TestCase):
    """Authored-script contracts, not a native HOI4 playtest."""

    KEYS = PartyFactionContracts.KEYS
    simulate = PartyFactionContracts.simulate
    TARGETED = {
        'STP_PRESIDENT_REMAINS_IN_OFFICE': {'conservatives': 8},
        'STP_PARTY_DISCIPLINE': {'security': 10},
        'STP_EMERGENCY_PRESIDIUM': {'conservatives': 6, 'security': 6},
        'STP_THE_PARTY_CLOSES_RANKS': {'conservatives': 8, 'army': 4},
        'STP_cw_protocol_office': {'conservatives': 8},
        'STP_cw_press_office': {'radicals': 8},
        'STP_cw_party_mandate': {'conservatives': 10, 'borons': 10},
        'STP_cw_quiet_registers': {'conservatives': 10, 'borons': 6},
    }
    SPECIALIZATIONS = {
        'STP_GUARANTEE_MINISTERS': (1, -4),
        'STP_defense_budget': (2, -4),
        'STP_cw_protect_congress': (1, -3),
        'STP_cw_capital_oath': (3, -7),
    }

    @classmethod
    def setUpClass(cls):
        cls.effects = {e.key: e.value for e in parse_clausewitz(read(EFFECTS))}
        cls.triggers = {e.key: e.value for e in parse_clausewitz(read('common/scripted_triggers/ADISCORD_STP_scripted_triggers.txt'))}
        cls.focus = {one(f.value, 'id'): f.value for tree in parse_clausewitz(read(FOCUS))
                     if tree.key == 'focus_tree' for f in tree.value if f.key == 'focus'}
        cls.decisions = {d.key: d.value for c in parse_clausewitz(read(DECISIONS))
                         for d in c.value if isinstance(d.value, list)}

    def test_institutional_rewards_support_named_factions_not_everyone(self):
        for fid, targets in self.TARGETED.items():
            with self.subTest(focus=fid):
                reward = one(self.focus[fid], 'completion_reward')
                self.assertNotIn('STP_change_apparatus_loyalty', {e.key for e in walk(reward)})
                support = {one(e.value, 'var'): float(one(e.value, 'value'))
                           for e in walk(reward) if e.key == 'add_to_variable'
                           and one(e.value, 'var').endswith('_support')}
                self.assertEqual(support, {'STP_pf_' + k + '_support': v for k, v in targets.items()})
                self.assertIn('STP_refresh_apparatus_loyalty', {e.key for e in walk(reward)})

    def test_concessions_do_not_cancel_their_own_rival_penalty(self):
        for fid, selector in (('STP_GUARANTEE_MINISTERS', 1), ('STP_ROTATE_DISTRICT_COMMAND', 3), ('STP_cw_capital_oath', 4)):
            reward = one(self.focus[fid], 'completion_reward')
            self.assertNotIn('STP_change_apparatus_loyalty', {e.key for e in walk(reward)}, fid)
            self.assertEqual(sum(e.key == 'STP_pf_shift' for e in walk(reward)), 1)

    def test_strategic_courses_have_real_persistent_duration_budgets(self):
        for fid, (stage, days) in self.SPECIALIZATIONS.items():
            variable = f'STP_ps_reorg_{stage}_specialization_days'
            writes = [float(one(e.value, 'value')) for e in walk(one(self.focus[fid], 'completion_reward'))
                      if e.key == 'add_to_variable' and one(e.value, 'var') == variable]
            self.assertEqual(writes, [days], fid)
            close = str(signature(self.effects['STP_ps_close_defence']))
            self.assertIn(variable, close)
        startup = read('common/on_actions/02_ADISCORD_STP_on_actions.txt')
        self.assertNotIn('specialization_days', startup)

    def test_recovery_time_reads_current_faction_support_with_exact_boundary(self):
        for stage, faction, bonus in ((1, 'conservatives', -7), (2, 'merchants', -4), (3, 'army', -7)):
            name = f'STP_ps_adjust_reorg_{stage}'
            self.assertIn(name, self.effects)
            for support in (0, 34.999, 35, 100):
                facts = {('STP', 'STP_ps_war_active', 'yes'): True,
                         ('STP', 'has_active_mission', f'STP_ps_reorg_{stage}'): True,
                         ('STP', 'has_country_flag', 'STP_pf_initialized'): True,
                         ('STP', 'has_variable', f'STP_ps_reorg_{stage}_specialization_days'): True,
                         ('STP', 'variable', f'STP_pf_{faction}_support'): support}
                selected = list(selected_effects(self.effects[name], facts))
                delta = 0
                for scope, entry in selected:
                    if entry.key == 'add_days_mission_timeout':
                        self.assertEqual(scope, 'STP')
                        self.assertEqual(one(entry.value, 'mission'), f'STP_ps_reorg_{stage}')
                        value = one(entry.value, 'days')
                        delta += bonus if value == f'STP_ps_reorg_{stage}_specialization_days' else float(value)
                self.assertEqual(delta, bonus + (7 if support < 35 else 0))
                facts[('STP', 'STP_ps_war_active', 'yes')] = False
                self.assertFalse(list(selected_effects(self.effects[name], facts)))

    def test_time_adjustments_run_only_on_new_orders_not_load_or_resume(self):
        for stage in (1, 2, 3):
            name = f'STP_ps_adjust_reorg_{stage}'
            for mode in ('funded', 'administrative'):
                reward = one(self.decisions[f'STP_ps_reorg_{stage}_{mode}'], 'complete_effect')
                keys = [e.key for e in walk(reward)]
                self.assertEqual(keys.count(name), 1)
                self.assertLess(keys.index('activate_mission'), keys.index(name))
            self.assertNotIn(name, str(signature(self.effects['STP_ps_resume_reorganisation'])))
            self.assertNotIn(name, read('common/on_actions/02_ADISCORD_STP_on_actions.txt'))

    def test_every_faction_caps_new_concessions_without_losing_support_recovery(self):
        for faction in self.KEYS:
            for influence in (59, 59.999, 60, 65, 99, 100):
                with self.subTest(faction=faction, influence=influence):
                    values, flags = self.simulate('STP_pf_initialize')
                    other = next(k for k in self.KEYS if k != faction)
                    for key in self.KEYS:
                        values[f'STP_pf_{key}_influence'] = 0
                    values[f'STP_pf_{other}_influence'] = 100 - influence
                    values[f'STP_pf_{faction}_influence'] = influence
                    values[f'STP_pf_{faction}_support'] = 0
                    values['STP_pf_selected'] = self.KEYS.index(faction) + 1
                    self.simulate('STP_pf_shift', values, flags)
                    self.assertAlmostEqual(float(values[f'STP_pf_{faction}_influence']), min(60, influence + 5) if influence < 60 else influence)
                    self.assertEqual(values[f'STP_pf_{faction}_support'], 12)
                    self.assertAlmostEqual(float(sum(values[f'STP_pf_{k}_influence'] for k in self.KEYS)), 100)
                    self.assertTrue(all(values[f'STP_pf_{k}_influence'] >= 0 for k in self.KEYS))

    def test_recovery_keeps_all_free_paths_and_original_escrow_prices(self):
        for stage, price in ((1, 900), (2, 1800), (3, 2500)):
            free = self.decisions[f'STP_ps_reorg_{stage}_administrative']
            funded = self.decisions[f'STP_ps_reorg_{stage}_funded']
            self.assertEqual(one(free, 'cost'), '0')
            self.assertNotIn('custom_cost_trigger', {e.key for e in free})
            for phase in ('custom_cost_trigger', 'complete_effect'):
                self.assertIn(str(price), str(signature(one(funded, phase))))
            self.assertNotIn('support', str(signature(one(free, 'available'))))
            writes = [e for e in walk(one(funded, 'complete_effect')) if e.key == 'subtract_from_variable'
                      and one(e.value, 'var') == 'ADISCORD_economy_treasury']
            self.assertEqual(len(writes), 1)
            self.assertEqual(one(writes[0].value, 'value'), str(price))

    def test_strategy_tooltips_are_bilingual_and_not_a_new_decision_category(self):
        for lang in ('russian', 'english'):
            loc = dict(re.findall(r'^\s*([^#\s:]+):(?:\d+)?\s*"(.*)"\s*$', read(f'localisation/{lang}/ADISCORD_STP_l_{lang}.yml'), re.M))
            for fid in (*self.TARGETED, *self.SPECIALIZATIONS):
                key = fid + '_strategy_tt'
                self.assertIn(key, loc)
                self.assertIn(key, str(signature(one(self.focus[fid], 'completion_reward'))))
            for stage in (1, 2, 3):
                for mode in ('funded', 'administrative'):
                    self.assertIn('35', loc[f'STP_ps_reorg_{stage}_{mode}_desc'])
        categories = read('common/decisions/categories/ADISCORD_decision_categories_STP.txt')
        self.assertNotIn('STP_party_strategy', categories)

    def test_sovereignty_initializer_is_idempotent_and_does_not_depend_on_itself(self):
        start = str(signature(self.effects['STP_pw_party_start_nod_invasion_threat']))
        self.assertNotIn('STP_pw_party_sovereignty', start)
        self.assertIn('STP_pw_party_nod_threat_active', start)
        self.assertIn('STP_pw_party_nod_invasion_active', start)
        self.assertIn('STP_pw_party_nod_invasion_defeated', start)



    def test_coalition_tooltips_match_the_sixty_percent_cap(self):
        for language in ('russian', 'english'):
            text = read(f'localisation/{language}/ADISCORD_STP_l_{language}.yml')
            for faction in self.KEYS:
                key = 'STP_pf_' + faction + '_deal_tt'
                value = next(line for line in text.splitlines() if line.startswith(' ' + key + ':'))
                self.assertNotIn('до 100%', value)
                self.assertNotIn('up to 100%', value)
                self.assertIn('60%', value)
                self.assertIn('+12', value)
                self.assertIn('-12', value)

    def test_fixed_point_cap_and_legacy_shares_do_not_drift(self):
        from decimal import Decimal, ROUND_DOWN
        quantum = Decimal('0.001')
        for faction in self.KEYS:
            for initial in ('59.999', '60.000', '65.001', '99.999', '100.000'):
                with self.subTest(faction=faction, initial=initial):
                    values, flags = self.simulate('STP_pf_initialize')
                    old = Decimal(initial)
                    others = [k for k in self.KEYS if k != faction]
                    share = ((100 - old) / 6).quantize(quantum, rounding=ROUND_DOWN)
                    for k in others:
                        values[f'STP_pf_{k}_influence'] = share
                    values[f'STP_pf_{others[-1]}_influence'] = 100 - old - 5 * share
                    values[f'STP_pf_{faction}_influence'] = old
                    values['STP_pf_selected'] = self.KEYS.index(faction) + 1
                    self.simulate('STP_pf_shift', values, flags, quantize=True)
                    self.assertEqual(values[f'STP_pf_{faction}_influence'], max(old, Decimal(60)))
                    self.assertEqual(sum(values[f'STP_pf_{k}_influence'] for k in self.KEYS), 100)
                    self.assertTrue(all(values[f'STP_pf_{k}_influence'] >= 0 for k in self.KEYS))


class PartyPostwarCoalitionContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.triggers = {e.key: e.value for e in parse_clausewitz(read('common/scripted_triggers/ADISCORD_STP_scripted_triggers.txt'))}
        cls.effects = {e.key: e.value for e in parse_clausewitz(read(EFFECTS))}
        cls.events = {one(e.value, 'id'): e.value for e in parse_clausewitz(read(EVENTS)) if e.key == 'country_event'}

    def expanded(self, items):
        from dataclasses import replace
        result = []
        for entry in items:
            if entry.key in self.triggers:
                self.assertIn(entry.value, ('yes', 'no'))
                result.append(replace(entry, key='AND' if entry.value == 'yes' else 'NOT',
                                      value=self.expanded(self.triggers[entry.key])))
            else:
                result.append(replace(entry, value=self.expanded(entry.value)) if isinstance(entry.value, list) else entry)
        return result

    def test_every_cabinet_needs_its_own_live_support(self):
        self.assertIn('STP_pw_party_cabinet_backed', self.triggers.keys())
        for cabinet, faction in ((1, 'conservatives'), (2, 'borons'), (3, 'radicals')):
            for support in (59.999, 60, 100):
                facts = {('STP', 'variable', 'STP_pw_party_cabinet'): cabinet,
                         ('STP', 'variable', f'STP_pf_{faction}_support'): support}
                self.assertEqual(matches_conditions(self.expanded(self.triggers['STP_pw_party_cabinet_backed']), facts), support >= 60)

    def test_compact_rechecks_both_countries_and_exact_payment(self):
        self.assertIn('STP_pw_party_compact_current', self.triggers.keys())
        # Keep the coalition predicate independent here: this checks settlement lifecycle.
        facts = {('NOD', 'exists', 'yes'): True, ('NOD', 'is_subject', 'no'): True,
                 ('NOD', 'has_capitulated', 'no'): True,
                 ('STP', 'exists', 'yes'): True, ('STP', 'is_subject', 'no'): True,
                 ('STP', 'has_capitulated', 'no'): True,
                 ('STP', 'has_country_flag', 'STP_cw_postwar'): True,
                 ('STP', 'has_country_flag', 'STP_sided_with_the_party_flag'): True,
                 ('STP', 'has_country_flag', 'STP_pw_party_nod_threat_active'): True,
                 ('STP', 'has_country_flag', 'STP_pw_party_compact_pending'): True,
                 ('STP', 'STP_pw_party_compact_coalition', 'yes'): True,
                 ('STP', 'variable', 'ADISCORD_economy_treasury'): 1350}
        from dataclasses import replace
        def expand_lifecycle(items):
            result = []
            for e in items:
                if e.key in self.triggers and e.key != 'STP_pw_party_compact_coalition':
                    result.append(replace(e, key='AND' if e.value == 'yes' else 'NOT', value=expand_lifecycle(self.triggers[e.key])))
                else:
                    result.append(replace(e, value=expand_lifecycle(e.value)) if isinstance(e.value, list) else e)
            return result
        gate = expand_lifecycle(self.triggers['STP_pw_party_compact_current'])
        self.assertTrue(matches_conditions(gate, facts, 'NOD'))
        changes = [(('STP', 'variable', 'ADISCORD_economy_treasury'), 1349.999),
                   (('STP', 'has_war_with', 'NOD'), True),
                   (('STP', 'has_country_flag', 'STP_pw_party_compact_pending'), False),
                   (('STP', 'has_country_flag', 'STP_pw_party_nod_compact'), True),
                   (('STP', 'has_country_flag', 'STP_pw_party_nod_threat_active'), False),
                   (('STP', 'STP_pw_party_compact_coalition', 'yes'), False),
                   (('NOD', 'is_subject', 'no'), False),
                   (('STP', 'has_capitulated', 'no'), False)]
        for key, value in changes:
            with self.subTest(key=key):
                self.assertFalse(matches_conditions(gate, facts | {key: value}, 'NOD'))

    def test_settlement_is_atomic_and_clears_threat_before_mission(self):
        self.assertIn('STP_pw_party_settle_compact', self.effects.keys())
        effect = self.effects['STP_pw_party_settle_compact']
        branches = children(effect, 'if')
        self.assertEqual(len(branches), 1)
        self.assertIn(('STP_pw_party_compact_current', 'yes'), signature(one(branches[0], 'limit')))
        writes = [(e.key, one(e.value, 'var'), one(e.value, 'value')) for e in walk(effect)
                  if e.key in ('subtract_from_variable', 'add_to_variable')]
        self.assertEqual(writes.count(('subtract_from_variable', 'ADISCORD_economy_treasury', '1350')), 1)
        self.assertEqual(writes.count(('add_to_variable', 'ADISCORD_economy_treasury', '1350')), 1)
        text = str(signature(effect))
        self.assertLess(text.index("('clr_country_flag', 'STP_pw_party_nod_threat_active')"), text.index("('remove_decision', 'STP_pw_party_nod_invasion_countdown')"))
        for name in ('STP_pw_party_launch_nod_invasion', 'STP_pw_party_start_nod_invasion_threat'):
            self.assertIn('STP_pw_party_nod_compact', str(signature(self.effects[name])))

    def test_story_choices_recheck_receipts_and_expired_offer_has_exit(self):
        for eid, variable in (('ADISCORD_STP_pc.23', 'STP_pw_party_cabinet'),
                              ('ADISCORD_STP_pc.34', 'STP_pw_party_command'),
                              ('ADISCORD_STP_pc.35', 'STP_pw_party_credit')):
            self.assertIn(eid, self.events)
            event = self.events[eid]
            self.assertEqual(one(event, 'timeout_days'), '14')
            options = children(event, 'option')
            self.assertGreaterEqual(len(options), 3)
            for option in options:
                if children(option, 'if'):
                    gate = str(signature(one(one(option, 'if'), 'limit')))
                    self.assertIn(variable, gate)
                    self.assertIn('STP_pw_party_story_current', gate)
            self.assertIn('STP_pc_offer_closed', [one(o, 'name') for o in options])
        self.assertIn('ADISCORD_STP_pc.36', self.events)
        offer = self.events['ADISCORD_STP_pc.36']
        self.assertEqual(one(offer, 'timeout_days'), '21')
        self.assertEqual(one(children(offer, 'option')[0], 'name'), 'ADISCORD_STP_pc.36.refuse')
        self.assertIn('STP_pc_offer_closed', [one(o, 'name') for o in children(offer, 'option')])

    def coalition_facts(self, cabinet=1, command=1, credit=1):
        values = {'STP_pw_party_cabinet': cabinet, 'STP_pw_party_command': command,
                  'STP_pw_party_credit': credit, 'STP_pw_recovery_industry': 1,
                  'STP_pw_recovery_services': 1, 'ADISCORD_economy_treasury': 2700}
        values.update({f'STP_pf_{f}_support': 60 for f in
                       ('conservatives', 'borons', 'radicals', 'army', 'security', 'merchants')})
        facts = {('STP', 'variable', k): v for k, v in values.items()}
        for country in ('STP', 'NOD'):
            for key, value in (('exists', 'yes'), ('is_subject', 'no'), ('has_capitulated', 'no')):
                facts[(country, key, value)] = True
        for flag in ('STP_cw_postwar', 'STP_sided_with_the_party_flag',
                     'STP_pw_party_nod_threat_active', 'STP_pw_party_compact_pending'):
            facts[('STP', 'has_country_flag', flag)] = True
        for focus in ('STP_pw_party_officer_school', 'STP_pw_party_supply_service'):
            facts[('STP', 'has_completed_focus', focus)] = True
        return facts

    def test_all_twelve_coalitions_can_negotiate_but_need_actual_recovery(self):
        from itertools import product
        gate = self.expanded(self.triggers['STP_pw_party_compact_coalition'])
        for cabinet, command, credit in product((1, 2, 3), (1, 2), (1, 2)):
            facts = self.coalition_facts(cabinet, command, credit)
            with self.subTest(cabinet=cabinet, command=command, credit=credit):
                self.assertTrue(matches_conditions(gate, facts))
                self.assertFalse(matches_conditions(gate, facts | {('STP', 'variable', 'STP_pw_recovery_industry'): 0}))
                self.assertFalse(matches_conditions(gate, facts | {('STP', 'has_completed_focus', 'STP_pw_party_officer_school'): False}))
                self.assertFalse(matches_conditions(gate, facts | {('STP', 'has_completed_focus', 'STP_pw_party_supply_service'): False}))
                professional = facts | {('STP', 'has_completed_focus', 'STP_pw_party_supply_service'): False,
                                        ('STP', 'has_completed_focus', 'STP_pw_party_professional_service'): True}
                self.assertTrue(matches_conditions(gate, professional))
                no_services = facts | {('STP', 'variable', 'STP_pw_recovery_services'): 0}
                self.assertEqual(matches_conditions(gate, no_services), credit == 1)

    def test_security_and_requisition_paths_have_recoverable_support_boundaries(self):
        gate = self.expanded(self.triggers['STP_pw_party_compact_coalition'])
        facts = self.coalition_facts(command=2, credit=2)
        for faction in ('army', 'merchants'):
            for value in (44.999, 45, 59.999, 60):
                self.assertEqual(matches_conditions(gate, facts | {('STP', 'variable', f'STP_pf_{faction}_support'): value}), value >= 45)
        for value in (59.999, 60):
            self.assertEqual(matches_conditions(gate, facts | {('STP', 'variable', 'STP_pf_security_support'): value}), value >= 60)

    def test_a_second_consent_cannot_charge_even_when_funds_remain(self):
        facts = self.coalition_facts()
        facts[('NOD', 'variable', 'ADISCORD_economy_treasury')] = 700
        effect = self.expanded(self.effects['STP_pw_party_settle_compact'])
        for attempt in range(2):
            issued = list(selected_effects(effect, facts, 'NOD'))
            if attempt:
                self.assertEqual(issued, [])
            for scope, e in issued:
                if e.key in ('add_to_variable', 'subtract_from_variable'):
                    key = (scope, 'variable', one(e.value, 'var'))
                    facts[key] = facts.get(key, 0) + float(one(e.value, 'value')) * (1 if e.key == 'add_to_variable' else -1)
                elif e.key in ('set_country_flag', 'clr_country_flag'):
                    facts[(scope, 'has_country_flag', e.value)] = e.key == 'set_country_flag'
            self.assertEqual(facts[('STP', 'variable', 'ADISCORD_economy_treasury')], 1350)
            self.assertEqual(facts[('NOD', 'variable', 'ADISCORD_economy_treasury')], 2050)
            self.assertFalse(facts[('STP', 'has_country_flag', 'STP_pw_party_nod_threat_active')])
            self.assertFalse(facts[('STP', 'has_country_flag', 'STP_pw_party_compact_pending')])

    def test_offer_leaves_room_for_recipient_timeout_and_does_not_pause_mission(self):
        decisions = {d.key: d.value for c in parse_clausewitz(read(DECISIONS)) for d in c.value if isinstance(d.value, list)}
        offer = decisions['STP_pw_party_offer_compact']
        facts = self.coalition_facts()
        facts[('STP', 'has_country_flag', 'STP_pw_party_compact_pending')] = False
        facts[('STP', 'has_active_mission', 'STP_pw_party_nod_invasion_countdown')] = True
        gate = self.expanded(one(offer, 'available'))
        for days in (21, 21.999, 22, 90):
            scenario = facts | {('STP', 'variable', 'days_mission_timeout@STP_pw_party_nod_invasion_countdown'): days}
            self.assertEqual(matches_conditions(gate, scenario), days >= 22)
        keys = [e.key for e in walk(one(offer, 'complete_effect'))]
        self.assertFalse({'remove_decision', 'activate_mission', 'add_days_mission_timeout', 'subtract_from_variable'} & set(keys))
        self.assertIn('STP_pw_party_nod_invasion_countdown', read('common/synchronized_dynamic_tokens/ADISCORD_tokens.txt').splitlines())

    def test_story_pages_and_substitutions_fit_both_editorial_limits(self):
        for language in ('russian', 'english'):
            path = f'localisation/{language}/ADISCORD_STP_l_{language}.yml'
            self.assertTrue((ROOT / path).read_bytes().startswith(b'\xef\xbb\xbf'))
            loc = dict(re.findall(r'^\s*([^#\s:]+):(?:\d+)?\s*"(.*)"\s*$', read(path), re.M))
            expansions = {}
            for entry in parse_clausewitz(read(SCRIPTED_LOC)):
                name = one(entry.value, 'name')
                if name.startswith('STPGetPostwar'):
                    values = [loc[e.value] for e in walk(entry.value) if e.key == 'localization_key']
                    expansions[name] = max(values, key=lambda v: len(v.encode('utf-8')))
            keys = ['ADISCORD_STP_pc.23.d', 'ADISCORD_STP_pc.28.d',
                    'ADISCORD_STP_pc.34.d', 'ADISCORD_STP_pc.35.d', 'ADISCORD_STP_pc.36.d',
                    'ADISCORD_STP_pc.37.accepted', 'ADISCORD_STP_pc.37.refused',
                    'ADISCORD_STP_pc.38.d', 'ADISCORD_STP_pc.39.d']
            for key in keys:
                text = loc[key]
                for name, value in expansions.items():
                    text = text.replace('[' + name + ']', value)
                text = text.replace(r'\n', '\n')
                self.assertNotIn('[STPGet', text, key)
                self.assertLessEqual(len(text), 3000, key)
                self.assertLessEqual(len(text.encode('utf-8')), 5500, key)
                self.assertNotIn('§Y', text, key)


class PartyNorthernRevolutionContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.triggers = {e.key: e.value for e in parse_clausewitz(read('common/scripted_triggers/ADISCORD_STP_scripted_triggers.txt'))}
        cls.effects = {e.key: e.value for e in parse_clausewitz(read(EFFECTS))}
        cls.events = {one(e.value, 'id'): e.value for e in parse_clausewitz(read(EVENTS)) if e.key == 'country_event'}
        cls.focus = {one(f, 'id'): f for t in children(parse_clausewitz(read(FOCUS)), 'focus_tree') for f in children(t, 'focus')}

    def test_northern_consent_cannot_survive_winner_loss_or_other_overlord(self):
        name = 'STP_pw_party_nod_congress_current'
        self.assertIn(name, self.triggers.keys())
        gate = self.triggers[name]
        facts = {('NOD', 'tag', 'NOD'): True, ('NOD', 'exists', 'yes'): True,
                 ('NOD', 'is_subject', 'no'): True, ('NOD', 'has_capitulated', 'no'): True,
                 ('STP', 'STP_pw_party_revolution_current', 'yes'): True,
                 ('STP', 'has_country_flag', 'STP_pw_party_nod_congress_pending'): True}
        self.assertTrue(matches_conditions(gate, facts, 'NOD'))
        for key in [('NOD', 'is_subject', 'no'), ('NOD', 'has_capitulated', 'no'),
                    ('STP', 'STP_pw_party_revolution_current', 'yes'),
                    ('STP', 'has_country_flag', 'STP_pw_party_nod_congress_pending')]:
            self.assertFalse(matches_conditions(gate, facts | {key: False}, 'NOD'), key)

    def test_northern_subject_settlement_is_guarded_and_consumes_pending_consent(self):
        name = 'STP_pw_party_accept_nod_congress'
        self.assertIn(name, self.effects.keys())
        effect = self.effects[name]
        yes = {('NOD', 'STP_pw_party_nod_congress_current', 'yes'): True}
        no = {('NOD', 'STP_pw_party_nod_congress_current', 'yes'): False}
        self.assertTrue(list(selected_effects(effect, yes, 'NOD')))
        self.assertEqual(list(selected_effects(effect, no, 'NOD')), [])
        settle = self.effects['STP_pw_party_begin_nod_subject']
        self.assertIn('STP_pw_party_close_northern_operations', [e.key for e in walk(settle)])
        leaves = list(walk(settle)) + list(walk(self.effects['STP_pw_party_close_northern_operations']))
        self.assertTrue(any(e.key == 'clr_country_flag' and e.value == 'STP_pw_party_nod_congress_pending' for e in leaves))
        self.assertTrue(any(e.key == 'clr_country_flag' and e.value == 'STP_pw_party_nod_invasion_active' for e in leaves))
        self.assertTrue(any(e.key == 'white_peace' and e.value == 'NOD' for e in leaves))

    def test_timeout_refuses_and_stale_window_only_closes(self):
        self.assertIn('ADISCORD_STP_pc.40', self.events.keys())
        event = self.events['ADISCORD_STP_pc.40']
        self.assertEqual(one(event, 'timeout_days'), '21')
        options = children(event, 'option')
        self.assertEqual(one(options[0], 'name'), 'ADISCORD_STP_pc.40.refuse')
        self.assertEqual(one(options[-1], 'name'), 'STP_pc_offer_closed')
        self.assertFalse(any(e.key in ('puppet', 'set_autonomy', 'declare_war_on') for e in walk(options[-1])))
        self.assertIn('STP_pw_party_refuse_nod_congress', [e.key for e in walk(self.events['ADISCORD_STP_pc.41'])])

    def test_congress_is_reachable_during_invasion_and_campaign_is_optional_after_consent(self):
        self.assertIn('STP_pw_party_revolution_capital', self.focus.keys())
        chain = ('STP_pw_party_revolution_capital', 'STP_pw_party_northern_contacts', 'STP_pw_party_nod_congress')
        for fid in chain:
            self.assertFalse(any(e.key == 'has_war' and e.value == 'no' for e in walk(one(self.focus[fid], 'available'))))
        final = self.focus['STP_pw_party_former_patron']
        self.assertEqual(children(one(final, 'prerequisite'), 'focus'), ['STP_pw_party_nod_congress'])
        self.assertTrue(any(e.key == 'is_subject_of' and e.value == 'STP' for e in walk(one(final, 'available'))))

    def test_conquest_dispatch_precedes_defensive_white_peace(self):
        text = read(SCRIPTED_PEACE)
        self.assertIn('STP_pw_party_win_nod_campaign = yes', text)
        self.assertLess(text.index('STP_pw_party_win_nod_campaign = yes'), text.index('STP_pw_party_settle_nod_invasion_defeat = yes'))

    def test_third_country_capitulation_cannot_award_nodrul_to_stelander(self):
        from dataclasses import replace
        hook = one(one(parse_clausewitz(read(SCRIPTED_PEACE)), 'on_actions'), 'on_capitulation')
        dispatch = next(e.value for e in one(hook, 'effect') if e.key == 'if'
                        and any(v.key == 'STP_pw_party_win_nod_campaign' for v in walk(e.value)))
        def scopes(items, winner):
            return [replace(e, key={'ROOT': 'NOD', 'FROM': winner}.get(e.key, e.key),
                            value=scopes(e.value, winner)) if isinstance(e.value, list) else e for e in items]
        for winner, completed, expected in [('STP', True, True), ('BJK', True, True),
                                            ('VAL', True, False), ('STP', False, False)]:
            facts = {('NOD', 'tag', 'NOD'): True, ('NOD', 'is_subject', 'no'): True,
                     ('NOD', 'has_war_with', 'STP'): True, ('STP', 'tag', 'STP'): True,
                     ('BJK', 'is_subject_of', 'STP'): True,
                     ('STP', 'STP_pw_party_revolution_current', 'yes'): True,
                     ('STP', 'has_completed_focus', 'STP_pw_party_nod_congress'): completed}
            self.assertEqual(matches_conditions(scopes(one(dispatch, 'limit'), winner), facts), expected)

    def test_preparation_checks_exact_prices_and_cannot_overwrite_another_receipt(self):
        decisions = {d.key: d.value for c in parse_clausewitz(read(DECISIONS)) for d in c.value if isinstance(d.value, list)}
        for suffix, focus, pp, price in [('fund_northern_contacts', 'northern_contacts', 35, 540),
                                        ('prepare_northern_campaign', 'northern_campaign', 50, 900)]:
            decision = decisions['STP_pw_party_' + suffix]
            self.assertEqual(one(decision, 'cost'), '0')
            for treasury, power, busy in [(price, pp, False), (price - .001, pp, False),
                                          (price, pp - .001, False), (price, pp, True)]:
                facts = {('STP', 'STP_pw_party_northern_work_current', 'yes'): True,
                         ('STP', 'has_completed_focus', 'STP_pw_party_' + focus): True,
                         ('STP', 'has_variable', 'STP_pw_party_north_deposit'): busy,
                         ('STP', 'variable', 'ADISCORD_economy_treasury'): treasury,
                         ('STP', 'numeric', 'has_political_power'): power}
                issued = list(selected_effects(one(decision, 'complete_effect'), facts))
                debits = [e for scope, e in issued if e.key == 'subtract_from_variable']
                expected = int(treasury >= price and power >= pp and not busy)
                self.assertEqual(len(debits), expected, (suffix, treasury, power, busy))
                if expected:
                    self.assertEqual(one(debits[0].value, 'value'), str(price))

    def test_delayed_delivery_or_refund_uses_current_recipient_not_historical_focus(self):
        effect = self.effects['STP_pw_party_finish_northern_work']
        for kind in (1, 2):
            for current, receipt in [(True, True), (False, True), (True, False)]:
                facts = {('STP', 'has_variable', 'STP_pw_party_north_deposit'): receipt,
                         ('STP', 'STP_pw_party_northern_work_current', 'yes'): current,
                         ('STP', 'variable', 'STP_pw_party_north_work_kind'): kind}
                issued = list(selected_effects(effect, facts))
                keys = [e.key for scope, e in issued]
                self.assertEqual('STP_pw_party_refund_northern_work' in keys, receipt and not current)
                self.assertEqual('add_equipment_to_stockpile' in keys, receipt and current and kind == 2)
                self.assertEqual('add_intel' in keys, receipt and current and kind == 1)

    def test_subject_creation_cannot_replay_after_receipt_consumed(self):
        effect = self.effects['STP_pw_party_finalize_nod_subject']
        facts = {('STP', 'has_country_flag', 'STP_pw_party_nod_subject_pending'): True,
                 ('STP', 'STP_pw_party_revolution_current', 'yes'): True,
                 ('NOD', 'exists', 'yes'): True, ('NOD', 'is_subject', 'no'): True}
        first = list(selected_effects(effect, facts))
        self.assertEqual(sum(e.key == 'puppet' for _, e in first), 1)
        self.assertIn(('STP', 'STP_pw_party_nod_subject_pending'),
                      [(scope, e.value) for scope, e in first if e.key == 'clr_country_flag'])
        facts[('STP', 'has_country_flag', 'STP_pw_party_nod_subject_pending')] = False
        self.assertEqual(list(selected_effects(effect, facts)), [])

    def test_refund_after_weekly_reset_preserves_unrelated_spending(self):
        effect = self.effects['STP_pw_party_refund_northern_work']
        facts = {('STP', 'has_variable', 'STP_pw_party_north_deposit'): True}
        balances = {'ADISCORD_economy_treasury': 200, 'ADISCORD_economy_current_month_action_costs': 75,
                    'ADISCORD_economy_current_month_action_income': 0, 'STP_pw_party_north_deposit': 540}
        for scope, entry in selected_effects(effect, facts):
            if entry.key in ('add_to_variable', 'subtract_from_variable'):
                name = one(entry.value, 'var')
                amount = balances[one(entry.value, 'value')]
                balances[name] += amount * (1 if entry.key == 'add_to_variable' else -1)
        self.assertEqual(balances['ADISCORD_economy_treasury'], 740)
        self.assertEqual(balances['ADISCORD_economy_current_month_action_costs'], 75)
        self.assertEqual(balances['ADISCORD_economy_current_month_action_income'], 540)

    def test_wrong_preparation_callback_cancels_without_touching_another_receipt(self):
        decisions = {d.key: d.value for c in parse_clausewitz(read(DECISIONS)) for d in c.value if isinstance(d.value, list)}
        for name, own_kind in [('fund_northern_contacts', 1), ('prepare_northern_campaign', 2)]:
            decision = decisions['STP_pw_party_' + name]
            for receipt, kind in [(True, own_kind), (True, 3 - own_kind), (False, own_kind), (False, 0)]:
                facts = {('STP', 'has_variable', 'STP_pw_party_north_deposit'): receipt,
                         ('STP', 'variable', 'STP_pw_party_north_work_kind'): kind}
                self.assertEqual(matches_conditions(one(decision, 'cancel_trigger'), facts),
                                 not receipt or kind != own_kind, (name, receipt, kind))
                issued = list(selected_effects(one(decision, 'cancel_effect'), facts))
                if kind != own_kind:
                    self.assertEqual(issued, [])


if __name__ == "__main__":
    unittest.main()
