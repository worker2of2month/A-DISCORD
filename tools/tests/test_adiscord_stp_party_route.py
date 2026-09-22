"""Party route contracts: branch reachability, displayed deltas and delayed settlement.

These tests inspect authored scripts, not the Clausewitz runtime.
"""
from pathlib import Path
import re
import unittest

from tools.validators.validate_adiscord_division_templates import parse_clausewitz
from tools.tests.test_adiscord_stp_preparation import matches_conditions, selected_effects

ROOT = Path(__file__).resolve().parents[2]
FOCUS = "common/national_focus/ADISCORD_national_focus_STP.txt"
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
    return (ROOT / path).read_text(encoding="utf-8-sig")


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
        self.assertIn("STP_PARTY_ELECTION_BRIEFING", [one(t,"localization_key") for t in texts])
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

    def test_negotiation_caps_fractional_influence_at_sixty(self):
        for influence in (54.5, 55, 55.5, 59.999, 60):
            values, flags = self.simulate("STP_pf_initialize")
            for key in self.KEYS:
                values[f"STP_pf_{key}_influence"] = 0
            values["STP_pf_conservatives_influence"] = str(100 - influence)
            values["STP_pf_army_influence"] = str(influence)
            values["STP_pf_selected"] = 4
            self.simulate("STP_pf_shift", values, flags)
            self.assertAlmostEqual(float(values["STP_pf_army_influence"]), min(60, influence + 5))
            self.assertAlmostEqual(sum(float(values[f"STP_pf_{key}_influence"]) for key in self.KEYS), 100)

    def simulate(self, effect, values=None, flags=None, tag="STP", nod=True, quantize=False):
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
        decisions = [e for e in one(categories, "STP_elections_in_the_party") if e.key.startswith("STP_pf_negotiate_")]
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


if __name__ == "__main__":
    unittest.main()
