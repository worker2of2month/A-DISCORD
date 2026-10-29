"""Parsed NAM campaign scenarios; native loading and UI need a fresh game."""

from dataclasses import replace
from decimal import Decimal
from collections import Counter
from contextlib import redirect_stdout
from io import StringIO
from itertools import product
from pathlib import Path
import json
import re
import unittest
from unittest.mock import patch

from tools.builders.build_adiscord_focus_trees import expected_outputs
from tools.tests.test_adiscord_stp_preparation import (
    block, scalar, walk, matches_conditions, selected_effects,
)
from tools.validators.validate_adiscord_division_templates import parse_clausewitz
from tools.validators.validate_adiscord_nam_resource_war import (
    balanced_braces,
    has_script_fragment,
)

ROOT = Path(__file__).resolve().parents[2]
BASE = "ADISCORD_nam_resource_war"
TREES = {
    "main": ("focus_trees/NAM/main/focuses.txt", "NAM_focus", "ADISCORD_NAM_focus.txt"),
    "postwar": ("focus_trees/NAM/postwar/focuses.txt", "NAM_postwar_focus", "ADISCORD_NAM_postwar.txt"),
    "defeated": ("focus_trees/NAM/defeated/focuses.txt", "NAM_defeated_focus", "ADISCORD_NAM_defeated.txt"),
    "exile_radical": ("focus_trees/NAM/exile_radical/focuses.txt", "NAM_exile_radical_focus",
                      "ADISCORD_NAM_exile_radical.txt"),
    "exile_humanist": ("focus_trees/NAM/exile_humanist/focuses.txt", "NAM_exile_humanist_focus",
                       "ADISCORD_NAM_exile_humanist.txt"),
    "exile_corporate": ("focus_trees/NAM/exile_corporate/focuses.txt", "NAM_exile_corporate_focus",
                        "ADISCORD_NAM_exile_corporate.txt"),
}
EXILE = ("exile_radical", "exile_humanist", "exile_corporate")


def read(path):
    return (ROOT / path).read_text(encoding="utf-8-sig")


def parsed(path):
    return parse_clausewitz(read(path))


def tree_focuses(kind):
    tree = block(parsed(TREES[kind][0]), "focus_tree")
    return tree, {scalar(e.value, "id"): e.value for e in tree if e.key == "focus"}


def reachable(focuses, blocked):
    """Prerequisite closure only; availability and bypass are engine-evaluated."""
    completed = set()
    while True:
        ready = set()
        for name, focus in focuses.items():
            if name in completed or name in blocked:
                continue
            requirements = [entry.value for entry in focus if entry.key == "prerequisite"]
            if all(any(child.value in completed for child in group) for group in requirements):
                ready.add(name)
        if not ready:
            return completed
        completed.update(ready)


class NamCampaignTests(unittest.TestCase):
    def preparation_route(self, administration, economy, army, lean=False):
        """One sequential focus queue; national and local projects run alongside it."""
        route = ["independence_day", "count_garrisons", "mobilisation_office", "open_ledgers", administration,
                 "well_register", economy, ("machine_shops" if lean else "refinery_programme") if economy == "domestic_refining" else "contract_bureau"]
        route += ["public_payroll", "district_guarantees"] if administration == "districts" else ["inspectors", "emergency_writ"]
        route += [army, "engineer_depots", "line_survey", "line_engineers"] if army == "field_guards" else [army, "motor_pool", "motor_column_orders"]
        return ["NAM_" + name for name in route + ["one_budget", "neutral_basin"]]

    def run_preparation_budget(self, administration, economy, army, lean=False):
        """Bounded source scenario, not an engine/economy simulation.

        The colony has earmarked 200 PP, 1000 treasury and 8000 fuel. Assume
        0.25 net PP/day while focusing, no tax/trade income, no new recruits
        and no factory output. Only this queue and explicitly bought projects
        can increase stocks. Random crises and the weekly budget are separate
        runtime inputs, so the resulting reserve is not a guaranteed forecast.
        """
        route = self.preparation_route(administration, economy, army, lean)
        facts = self.economy_facts()
        for name in self.focuses:
            facts[("NAM", "has_completed_focus", name)] = name in ("NAM_inventory", "NAM_letters_to_the_centre")
        facts[("NAM", "has_global_flag", "ADISCORD_vorkerland_collapse_wars_started")] = True
        facts[("NAM", "has_war", "yes")] = False
        facts[("NAM", "fixture_power_balance", "NAM_ladder_bop")] = True
        facts[("NAM", "power_balance_value", "NAM_ladder_bop")] = 0
        facts[("67", "fixture_foreign_land_border", "yes")] = True
        for name, value in (("has_political_power", 150 if lean else 200), ("has_fuel", 4000 if lean else 8000), ("has_manpower", 0)):
            facts[("NAM", "numeric", name)] = value
        for name, value in (("ADISCORD_economy_treasury", 300 if lean else 1000), ("NAM_order_cap", 4), ("NAM_orders_paid", 0),
                            ("NAM_line_slots", 2), ("NAM_lines_in_progress", 0), ("NAM_project_slots", 1),
                            ("NAM_grp_dist_support", 40), ("NAM_grp_nam_support", 55),
                            ("NAM_grp_oil_support", 40), ("NAM_grp_garr_support", 50), ("NAM_grp_trade_support", 45)):
            facts[("NAM", "variable", name)] = value
        facts[("67", "numeric", "synthetic_refinery")] = 0
        facts[("67", "fixture_free_building_slots", "synthetic_refinery:1:yes")] = True
        projects = dict(self.decisions)
        for category in parsed(f"common/decisions/{BASE}_decisions.txt"):
            if category.key == "NAM_mobilisation":
                projects.update({e.key: e.value for e in category.value})
        wanted = {"NAM_ind_sovereign_collections": 2,
                  "NAM_mil_recruit_depots": 2 if administration == "vertical" and army == "field_guards" else 1}
        wanted["NAM_admin_compulsory_delivery" if administration == "vertical" else "NAM_admin_voluntary_enrolment"] = 1
        if administration == "districts":
            wanted["NAM_sign_compact"] = 1
        if economy == "domestic_refining":
            wanted.update(NAM_project_refinery=1, NAM_econ_petrochemical_batch=1)
        else:
            wanted["NAM_export_fuel"] = 1
        if army == "field_guards":
            wanted.update(NAM_order_resource_guard=1, NAM_prepare_line=1, NAM_mil_forward_supply=1)
        else:
            wanted.update(NAM_order_motor_column=1, NAM_mil_carrier_contract=1)
        if lean:
            wanted["NAM_mil_recruit_depots"] = 1
            if administration == "districts":
                del wanted["NAM_admin_voluntary_enrolment"]
            if economy == "domestic_refining":
                del wanted["NAM_project_refinery"]
                del wanted["NAM_econ_petrochemical_batch"]
                wanted["NAM_workshop_batch"] = 1
            if army == "field_guards":
                del wanted["NAM_order_resource_guard"]
                wanted["NAM_order_field_infantry"] = 1
            else:
                del wanted["NAM_mil_carrier_contract"]
        # Keep real accounting and local delivery effects. Aggregate modifiers,
        # stories, trade offers and war dispatch are outside this budget fixture.
        accounting = {name: body for name, body in self.effects.items() if name in (
            "NAM_add_treasury", "NAM_spend_treasury", "NAM_receive_250", "NAM_line_begin", "NAM_line_complete",
            "NAM_line_release", "NAM_project_begin", "NAM_project_close", "NAM_project_complete_refinery", "NAM_order_register")}
        counts = Counter()
        pending = {}
        cooldown = {}
        completed = {}
        focus_days = {}
        focus_index = 0
        focus_due = 0
        windows = [e.value for e in walk(self.triggers["NAM_rw_war_window_open"])
                   if e.key == "has_global_flag" and isinstance(e.value, list)
                   and scalar(e.value, "flag") == BASE + "_scheduled"]
        first_war_day = min(int([e.value for e in window if not e.key][-1]) + 1 for window in windows)
        self.assertLessEqual(sum(int(scalar(self.focuses[n], "cost")) * 7 for n in route), 280)
        with patch.object(self, "effects", accounting):
            for day in range(first_war_day):
                facts[("NAM", "numeric", "has_political_power")] += 0.25
                for name in list(pending):
                    if pending[name] != day:
                        continue
                    body = self.bind_field(projects[name])
                    self.assertFalse(self.matches(next((e.value for e in body if e.key == "cancel_trigger"), []), facts)
                                     if any(e.key == "cancel_trigger" for e in body) else False, (name, day))
                    self.apply(block(body, "remove_effect"), facts)
                    if name == "NAM_project_refinery":
                        self.assertEqual(facts[("67", "building", "synthetic_refinery")], 1)
                        facts[("67", "numeric", "synthetic_refinery")] = 1
                    del pending[name]
                    facts[("NAM", "has_decision", name)] = False
                    completed[name] = day
                if day == focus_due and focus_index:
                    name = route[focus_index - 1]
                    self.apply(block(self.focuses[name], "completion_reward"), facts)
                    facts[("NAM", "has_completed_focus", name)] = True
                    focus_days[name] = day
                if day == focus_due and focus_index < len(route):
                    name = route[focus_index]
                    body = self.focuses[name]
                    for requirement in (e.value for e in body if e.key == "prerequisite"):
                        self.assertTrue(any(facts.get(("NAM", "has_completed_focus", e.value)) for e in requirement), name)
                    for group in (e.value for e in body if e.key == "mutually_exclusive"):
                        self.assertFalse(any(facts.get(("NAM", "has_completed_focus", e.value)) for e in group), name)
                    self.assertTrue(self.matches(block(body, "available"), facts), name)
                    focus_due = day + int(scalar(body, "cost")) * 7
                    focus_index += 1
                for name, limit in wanted.items():
                    if counts[name] >= limit or name in pending or day < cooldown.get(name, 0):
                        continue
                    body = self.bind_field(projects[name])
                    predicates = [e.value for e in body if e.key in ("visible", "available", "custom_cost_trigger")]
                    price = int(next((e.value for e in body if e.key == "cost"), "0"))
                    if not all(self.matches(p, facts) for p in predicates) or facts[("NAM", "numeric", "has_political_power")] < price:
                        continue
                    facts[("NAM", "numeric", "has_political_power")] -= price
                    self.apply(block(body, "complete_effect"), facts)
                    counts[name] += 1
                    duration = int(next((e.value for e in body if e.key == "days_remove"), "0"))
                    cooldown[name] = day + duration + int(next((e.value for e in body if e.key == "days_re_enable"), "0"))
                    if duration:
                        pending[name] = day + duration
                        facts[("NAM", "has_decision", name)] = True
                    else:
                        completed[name] = day
                for key in (("numeric", "has_political_power"), ("numeric", "has_fuel"), ("numeric", "has_manpower"),
                            ("variable", "ADISCORD_economy_treasury"), ("equipment", "support_equipment")):
                    self.assertGreaterEqual(facts.get(("NAM", *key), 0), 0, (administration, economy, army, day, key))
        self.assertEqual(dict(counts), wanted, (administration, economy, army, counts))
        self.assertFalse(pending, (administration, economy, army, pending))
        self.assertLess(max(completed.values()), first_war_day)
        if administration == "districts":
            self.assertLessEqual(completed["NAM_sign_compact"] + 60, 280)
        self.assertEqual(facts[("NAM", "variable", "NAM_lines_in_progress")], 0)
        self.assertEqual(facts[("NAM", "variable", "NAM_projects_in_progress")], 0)
        formation = "infantry" if lean and army == "field_guards" else "guard" if army == "field_guards" else "motor"
        self.assertEqual(facts[("NAM", "variable", "NAM_order_" + formation + "_paid")], 1)
        self.assertEqual(facts[("NAM", "variable", "NAM_orders_paid")], 1)
        if army == "field_guards":
            self.assertTrue(facts[("67", "has_state_flag", "NAM_line_prepared")])
            self.assertTrue(facts[("67", "has_dynamic_modifier", "NAM_mil_forward_depot")])
        elif not lean:
            self.assertEqual(facts[("NAM", "equipment", "ADISCORD_armored_carrier_2163")], 160)
        if economy == "domestic_refining" and not lean:
            self.assertGreaterEqual(facts[("NAM", "equipment", "motorized_equipment")], 150)
            self.assertGreaterEqual(facts[("NAM", "equipment", "artillery_equipment")], 60)
        return focus_days, completed

    def test_combined_preparation_routes_pay_and_deliver_before_the_war(self):
        for administration, economy, army in product(("vertical", "districts"), ("export_quays", "domestic_refining"), ("field_guards", "mobile_columns")):
            with self.subTest(administration=administration, economy=economy, army=army):
                self.run_preparation_budget(administration, economy, army)

    def test_colonial_saving_route_funds_the_preparation_reserve(self):
        route = ("inventory", "centre_hourglass", "second_ledger", "quiet_officer_lists", "sand_runs_out",
                 "last_centre_register", "metropolitan_quota", "concealed_reserve", "wrk_trade_house",
                 "wrk_return_cargo", "metropolitan_depots", "letters_to_the_centre", "colonial_watch",
                 "oilfield_militia", "pipeline_patrols")
        facts = self.colonial_facts()
        for name in self.focuses:
            facts[("NAM", "has_completed_focus", name)] = False
        facts[("NAM", "has_variable", "NAM_hidden_reserve")] = False
        for name in ("has_political_power", "has_fuel", "has_manpower"):
            facts[("NAM", "numeric", name)] = 0
        defaults = block(parsed("common/scripted_effects/ADISCORD_economy_effects.txt"), "ADISCORD_economy_set_default_values")
        treasury = next(e.value for e in defaults if e.key == "set_variable" and scalar(e.value, "var") == "ADISCORD_economy_treasury")
        facts[("NAM", "variable", "ADISCORD_economy_treasury")] = float(scalar(treasury, "value"))
        projects = block(parsed(f"common/decisions/{BASE}_decisions.txt"), "NAM_colony")
        fuel_order = block(projects, "NAM_colonial_fuel_reserve")
        shipment = block(projects, "NAM_wrk_fuel_shipment")
        accounting = {name: body for name, body in self.effects.items() if name in (
            "NAM_add_treasury", "NAM_wrk_trade_refresh", "NAM_colony_monthly", "NAM_colony_hourglass_payout")}
        day = 0
        completions = {}
        for name in route:
            name = "NAM_" + name
            day += int(scalar(self.focuses[name], "cost")) * 7
            completions[day] = name
        self.assertEqual(day, 343)
        startup = parsed("common/on_actions/01_ADISCORD_vorkerland_collapse_on_actions.txt")
        collapse = next(e.value for e in walk(startup) if e.key == "country_event"
                        and scalar(e.value, "id") == "ADISCORD_vorkerland_phase.1")
        self.assertLess(day, int(scalar(collapse, "days")))
        paid_day = next(day for day, name in completions.items() if name == "NAM_concealed_reserve")
        fuel_due = paid_day + int(scalar(fuel_order, "days_remove"))
        first_shipment = next(day for day, name in completions.items() if name == "NAM_wrk_trade_house")
        shipment_days = (first_shipment, first_shipment + int(scalar(shipment, "days_re_enable")))
        with patch.object(self, "effects", accounting):
            for day in range(1, 351):
                facts[("NAM", "numeric", "has_political_power")] += 0.25
                if day in completions:
                    name = completions[day]
                    focus = self.focuses[name]
                    for requirement in (e.value for e in focus if e.key == "prerequisite"):
                        self.assertTrue(any(facts.get(("NAM", "has_completed_focus", e.value)) for e in requirement), name)
                    self.assertTrue(self.matches(block(focus, "available"), facts), name)
                    self.apply(block(focus, "completion_reward"), facts)
                    facts[("NAM", "has_completed_focus", name)] = True
                if day == paid_day:
                    self.assertTrue(self.matches(block(fuel_order, "visible"), facts))
                    self.assertTrue(self.matches(block(fuel_order, "available"), facts))
                    facts[("NAM", "numeric", "has_political_power")] -= int(scalar(fuel_order, "cost"))
                    self.apply(block(fuel_order, "complete_effect"), facts)
                if day == fuel_due:
                    self.apply(block(fuel_order, "remove_effect"), facts)
                if day in shipment_days:
                    for key in ("visible", "available", "custom_cost_trigger"):
                        self.assertTrue(self.matches(block(shipment, key), facts), (day, key))
                    self.apply(block(shipment, "complete_effect"), facts)
                # At most 31 days per monthly pulse is a conservative calendar.
                if day % 31 == 0:
                    self.apply(self.effects["NAM_colony_monthly"], facts)
                self.assertGreaterEqual(facts[("NAM", "numeric", "has_political_power")], 0)
                self.assertGreaterEqual(facts[("NAM", "numeric", "has_fuel")], 0)
            self.apply(self.effects["NAM_colony_hourglass_payout"], facts)
        self.assertEqual(facts[("NAM", "numeric", "has_political_power")], 252.5)
        self.assertEqual(facts[("NAM", "variable", "ADISCORD_economy_treasury")], 1195)
        self.assertEqual(facts[("NAM", "numeric", "has_fuel")], 11500)

    def test_low_reserve_routes_prioritise_preparation_over_capital_projects(self):
        for administration, economy, army in product(("vertical", "districts"), ("export_quays", "domestic_refining"), ("field_guards", "mobile_columns")):
            with self.subTest(administration=administration, economy=economy, army=army):
                self.run_preparation_budget(administration, economy, army, lean=True)

    def test_prewar_depot_survives_waiting_for_the_attack(self):
        body = self.decisions["NAM_mil_forward_supply"]
        installation = [e.value for e in walk(block(body, "remove_effect")) if e.key == "add_dynamic_modifier"]
        self.assertEqual(len(installation), 1)
        self.assertEqual(scalar(installation[0], "modifier"), "NAM_mil_forward_depot")
        self.assertNotIn("days", [e.key for e in installation[0]])
        dynamic = block(parsed("common/dynamic_modifiers/ADISCORD_dynamic_modifiers_NAM.txt"), "NAM_mil_forward_depot")
        for war in (False, True):
            facts = self.economy_facts()
            facts[("NAM", "has_global_flag", BASE + "_started")] = war
            facts[("NAM", "has_global_flag", BASE + "_scheduled")] = not war
            self.assertTrue(matches_conditions(self.expand(block(dynamic, "enable")), facts, "67"))
            facts[("NAM", "has_global_flag", BASE + "_resolved")] = True
            facts[("NAM", "has_global_flag", BASE + "_scheduled")] = False
            self.assertFalse(matches_conditions(self.expand(block(dynamic, "enable")), facts, "67"))

    def test_ai_prepares_the_compact_refinery_and_lines_before_other_programmes(self):
        plan = block(parsed("common/ai_strategy_plans/ADISCORD_NAM_plans.txt"), "NAM_prewar_plan")
        queue = [e.value for e in block(plan, "ai_national_focuses")]
        start = queue.index("NAM_independence_day")
        route = self.preparation_route("districts", "domestic_refining", "field_guards")
        self.assertEqual(queue[start:start + len(route)], route)
        self.assertLess(queue.index("NAM_alarm"), start)
        days, deliveries = self.run_preparation_budget("districts", "domestic_refining", "field_guards")
        self.assertLessEqual(deliveries["NAM_sign_compact"] + 60, 280)
        self.assertLess(deliveries["NAM_econ_petrochemical_batch"], 300)
        self.assertLess(deliveries["NAM_mil_forward_supply"], 300)

    def test_azhar_focus_and_ultimatum_share_one_paid_delay(self):
        body = self.focuses["NAM_court_azhar"]
        for first_strike, receiver in ((True, True), (False, False)):
            facts = self.independent_facts()
            facts[("AZH", "exists", "yes")] = receiver
            facts[("NAM", "has_country_flag", "NAM_rw_first_strike")] = first_strike
            self.assertFalse(self.matches(block(body, "available"), facts))
            before = dict(facts)
            self.apply(block(body, "completion_reward"), facts)
            self.assertEqual(facts, before)
        for fuel, allowed in ((5999.99, False), (6000, True)):
            facts = self.independent_facts()
            facts[("AZH", "exists", "yes")] = True
            facts[("NAM", "numeric", "has_fuel")] = fuel
            self.assertEqual(self.matches(block(body, "available"), facts), allowed)
            with patch.object(self, "effects", {}):
                self.apply(block(body, "completion_reward"), facts)
                self.assertEqual(facts[("NAM", "numeric", "has_fuel")], fuel - (6000 if allowed else 0))
                self.assertEqual(facts.get(("AZH", "numeric", "has_fuel"), 0), 6000 if allowed else 0)
                paid = dict(facts)
                self.apply(block(body, "completion_reward"), facts)
                self.assertEqual(facts, paid)
            if allowed:
                self.assertTrue(self.matches(block(body, "bypass"), facts))
                self.apply(self.effects["NAM_rw_buy_time"], facts)
                self.assertEqual(facts, paid)
                facts[("NAM", "global_flag_days", BASE + "_scheduled")] = 500
                for age in (74, 75):
                    facts[("NAM", "flag_days", "NAM_rw_time_bought")] = age
                    self.assertEqual(self.matches(self.triggers["NAM_rw_time_bought_active"], facts), age < 75)
        entry = block(self.events[BASE + ".1"], "immediate")
        delay = next(e.value for e in entry if e.key == "else_if" and "NAM_rw_time_bought" in repr(e.value))
        facts = self.independent_facts()
        facts[("NAM", "has_country_flag", "NAM_rw_time_bought")] = True
        facts[("NAM", "flag_days", "NAM_rw_time_bought")] = 200
        self.assertTrue(self.matches(block(delay, "limit"), facts))
        self.assertEqual(scalar(block(delay, "country_event"), "days"), "75")
        facts[("NAM", "has_global_flag", BASE + "_time_deferred")] = True
        self.assertFalse(self.matches(block(delay, "limit"), facts))

    def test_restitution_desk_funds_an_existing_note_instead_of_unlocking_it_twice(self):
        reward = block(self.focuses["NAM_restitution_desk"], "completion_reward")
        for neutral in (False, True):
            facts = self.independent_facts()
            facts[("NAM", "has_completed_focus", "NAM_neutral_basin")] = neutral
            before = facts[("NAM", "numeric", "has_political_power")]
            selected = list(selected_effects(self.expand(reward), facts, "NAM"))
            unlocks = [e.value for scope, e in selected if e.key == "unlock_decision_tooltip"]
            self.assertEqual(unlocks, [] if neutral else ["NAM_restitution_note"])
            with patch.object(self, "effects", {}):
                self.apply(reward, facts)
            self.assertEqual(facts[("NAM", "numeric", "has_political_power")] - before, 25 if neutral else 0)


    def military_facts(self):
        facts = self.economy_facts()
        facts[("NAM", "has_war", "no")] = False
        facts[("NAM", "variable", "NAM_line_slots")] = 3
        facts[("NAM", "variable", "NAM_lines_in_progress")] = 0
        facts[("NAM", "equipment", "support_equipment")] = 300
        for state in ("67", "688", "689", "690", "719", "700"):
            facts[(state, "has_state_flag", "NAM_line_prepared")] = True
            facts[(state, "has_variable", "NAM_field_condition")] = True
        facts[("700", "numeric", "arms_factory")] = 1
        return facts

    def military_projects(self):
        return {name: body for name, body in self.decisions.items() if name.startswith("NAM_mil_")}

    def test_military_focus_actions_and_real_bypass_boundaries(self):
        section = read(TREES["main"][0]).split("# ----- Garrisons, mobilisation orders and defence lines -----", 1)[1].split("# ----- Harbour", 1)[0]
        names = re.findall(r"\bid = (NAM_\w+)", section)
        self.assertEqual(len(names), 13)
        for name in names:
            self.assertTrue(any(e.key == "unlock_decision_tooltip" for e in walk(block(self.focuses[name], "completion_reward"))), name)
        self.assertEqual(len(self.military_projects()), 9)
        facts = self.military_facts()
        for name, body in self.military_projects().items():
            self.assertTrue(self.matches(block(self.bind_field(body), "visible"), facts), name)
            self.assertTrue(self.matches(block(self.bind_field(body), "available"), facts), name)
        depot = self.decisions["NAM_mil_forward_supply"]
        facts[("NAM", "variable", "NAM_line_slots")] = 2
        self.assertFalse(self.matches(block(depot, "visible"), facts))
        # Bypassed prewar focuses do not reopen supply orders after settlement.
        facts[("NAM", "has_global_flag", BASE + "_scheduled")] = False
        facts[("NAM", "has_global_flag", BASE + "_resolved")] = True
        self.assertFalse(self.matches(block(self.decisions["NAM_mil_reserve_arsenal"], "visible"), facts))

    def test_military_prices_and_debits_use_exact_balances(self):
        prices = {
            "recruit_depots": (35, 200, 0, 0), "engineer_supplies": (25, 150, 0, 0),
            "carrier_contract": (35, 250, 0, 0), "reserve_arsenal": (30, 300, 0, 0),
            "arsenal_batch": (35, 250, 0, 0), "command_course": (35, 150, 0, 0),
            "mobile_surge": (40, 0, 3000, 0), "forward_supply": (25, 150, 0, 60),
        }
        keys = (("NAM", "numeric", "has_political_power"), ("NAM", "variable", "ADISCORD_economy_treasury"),
                ("NAM", "numeric", "has_fuel"), ("NAM", "equipment", "support_equipment"))
        for suffix, amounts in prices.items():
            body = self.bind_field(self.decisions["NAM_mil_" + suffix])
            for key, price in zip(keys, amounts):
                if not price:
                    continue
                facts = self.military_facts()
                facts.update(zip(keys, amounts))
                self.assertTrue(self.matches(block(body, "custom_cost_trigger"), facts), suffix)
                facts[key] -= 0.001
                self.assertFalse(self.matches(block(body, "custom_cost_trigger"), facts), suffix)
                before = dict(facts)
                self.apply(block(body, "complete_effect"), facts)
                self.assertEqual(facts, before, (suffix, key))
            facts = self.military_facts()
            facts.update(zip(keys, amounts))
            self.apply(block(body, "complete_effect"), facts)
            self.assertEqual([facts[k] for k in keys], [0, 0, 0, 0], suffix)
            paid = dict(facts)
            self.apply(block(body, "complete_effect"), facts)
            self.assertEqual(facts, paid, suffix)
        security = self.decisions["NAM_mil_field_security"]
        self.assertEqual(scalar(security, "cost"), "35")
        self.assertFalse(any(e.key == "custom_cost_text" for e in security))
        depot = self.decisions["NAM_mil_forward_supply"]
        debit = [e.value for e in walk(block(depot, "complete_effect"))
                 if e.key == "add_equipment_to_stockpile" and scalar(e.value, "amount") == "-60"]
        self.assertEqual(len(debit), 1)
        self.assertFalse(any(e.key == "producer" for e in debit[0]))

    def test_military_procurement_delivers_once_and_refunds_interrupted_orders(self):
        rewards = {
            "recruit_depots": (("numeric", "has_manpower", 6000),),
            "engineer_supplies": (("equipment", "support_equipment", 180), ("equipment", "artillery_equipment", 36)),
            "carrier_contract": (("equipment", "ADISCORD_armored_carrier_2163", 160), ("equipment", "support_equipment", 60)),
            "reserve_arsenal": (("equipment", "infantry_equipment", 9000), ("equipment", "support_equipment", 80)),
            "arsenal_batch": (("equipment", "artillery_equipment", 60), ("equipment", "anti_air_equipment", 36), ("equipment", "anti_tank_equipment", 36)),
            "command_course": (("numeric", "army_experience", 25), ("numeric", "command_power", 20)),
        }
        for suffix, deltas in rewards.items():
            body = self.decisions["NAM_mil_" + suffix]
            facts = self.military_facts()
            self.apply(block(body, "complete_effect"), facts)
            before = dict(facts)
            facts[("NAM", "has_global_flag", BASE + "_scheduled")] = False
            facts[("NAM", "has_global_flag", BASE + "_started")] = True
            self.assertFalse(self.matches(block(body, "cancel_trigger"), facts), suffix)
            self.apply(block(body, "remove_effect"), facts)
            for kind, resource, delta in deltas:
                key = ("NAM", kind, resource)
                self.assertEqual(facts[key] - before.get(key, 0), delta, suffix)
            settled = dict(facts)
            self.apply(block(body, "remove_effect"), facts)
            self.apply(block(body, "cancel_effect"), facts)
            self.assertEqual(facts, settled, suffix)
            for ended in (("NAM", "is_subject", "no"), ("NAM", "has_capitulated", "no")):
                for exit_name in ("remove_effect", "cancel_effect"):
                    facts = self.military_facts()
                    self.apply(block(body, "complete_effect"), facts)
                    facts[ended] = False
                    self.apply(block(body, exit_name), facts)
                    self.assertEqual(facts[("NAM", "numeric", "has_political_power")], 1000, suffix)
                    self.assertEqual(facts[("NAM", "variable", "ADISCORD_economy_treasury")], 10000, suffix)
                    settled = dict(facts)
                    self.apply(block(body, "remove_effect"), facts)
                    self.apply(block(body, "cancel_effect"), facts)
                    self.assertEqual(facts, settled, suffix)

    def test_oilfield_security_mitigates_held_fields_but_not_scorched_ceded_land(self):
        with patch.dict(self.effects, {"NAM_oil_refresh": []}):
            for damage in (15, 20, 70):
                for active, owned, controlled, independent in product((False, True), repeat=4):
                    facts = self.military_facts()
                    facts[("NAM", "has_decision", "NAM_mil_field_security")] = active
                    facts[("67", "is_owned_by", "NAM")] = owned
                    facts[("67", "is_controlled_by", "NAM")] = controlled
                    facts[("NAM", "is_subject", "no")] = independent
                    facts[("67", "variable", "NAM_field_damage_amount")] = damage
                    self.apply(self.effects["NAM_field_apply_damage"], facts, "67")
                    mitigation = 0.5 if active and owned and controlled and independent else 1
                    self.assertEqual(facts[("67", "variable", "NAM_field_condition")], 80 - damage * mitigation)
                    self.assertEqual(facts[("67", "variable", "NAM_field_damage_amount")], damage)
        scorched = self.decisions.get("NAM_scorch_wells")
        if scorched is None:
            scorched = block(block(parsed(f"common/decisions/{BASE}_decisions.txt"), "NAM_mobilisation"), "NAM_scorch_wells")
        self.assertFalse(any(e.key == "NAM_field_apply_damage" for e in walk(scorched)))

    def test_mobile_operation_spends_fuel_and_closes_on_every_terminal_condition(self):
        body = self.decisions["NAM_mil_mobile_surge"]
        modifier = "NAM_mil_mobile_operation"
        definition = block(parsed("common/dynamic_modifiers/ADISCORD_dynamic_modifiers_NAM.txt"), modifier)
        for key in (("NAM", "has_war", "yes"), ("NAM", "is_subject", "no"), ("NAM", "has_capitulated", "no")):
            facts = self.military_facts()
            self.apply(block(body, "complete_effect"), facts)
            self.assertTrue(facts[("NAM", "has_dynamic_modifier", modifier)])
            self.assertEqual(facts[("NAM", "numeric", "has_fuel")], 17000)
            self.assertEqual(facts[("NAM", "numeric", "has_political_power")], 960)
            facts[key] = False
            self.assertTrue(self.matches(block(body, "cancel_trigger"), facts))
            self.assertFalse(self.matches(block(definition, "enable"), facts))
            self.assertTrue(self.matches(block(definition, "remove_trigger"), facts))
            self.apply(block(body, "cancel_effect"), facts)
            self.assertFalse(facts[("NAM", "has_dynamic_modifier", modifier)])
            settled = dict(facts)
            self.apply(block(body, "remove_effect"), facts)
            self.assertEqual(facts, settled)
        self.assertEqual(scalar(definition, "army_speed_factor"), "0.10")
        self.assertEqual(scalar(definition, "army_fuel_consumption_factor"), "0.15")

    def test_forward_supply_uses_line_slots_and_refunds_every_paid_resource(self):
        body = self.bind_field(self.decisions["NAM_mil_forward_supply"])
        for ended in (("67", "is_owned_by", "NAM"), ("67", "is_controlled_by", "NAM"),
                      ("NAM", "is_subject", "no"), ("NAM", "has_capitulated", "no"), ("campaign",)):
            facts = self.military_facts()
            self.apply(block(body, "complete_effect"), facts)
            self.assertEqual(facts[("NAM", "variable", "NAM_lines_in_progress")], 1)
            self.assertEqual(facts[("NAM", "equipment", "support_equipment")], 240)
            paid = dict(facts)
            self.apply(block(body, "complete_effect"), facts)
            self.assertEqual(facts, paid)
            ordinary = self.bind_field(block(block(parsed(f"common/decisions/{BASE}_decisions.txt"), "NAM_mobilisation"), "NAM_prepare_line"))
            self.assertFalse(self.matches(block(ordinary, "available"), facts))
            if ended == ("campaign",):
                facts[("NAM", "has_global_flag", BASE + "_scheduled")] = False
                facts[("NAM", "has_global_flag", BASE + "_resolved")] = True
            else:
                facts[ended] = False
            self.assertTrue(self.matches(block(body, "cancel_trigger"), facts))
            self.apply(block(body, "remove_effect"), facts)
            self.assertEqual(facts[("NAM", "numeric", "has_political_power")], 1000)
            self.assertEqual(facts[("NAM", "variable", "ADISCORD_economy_treasury")], 10000)
            self.assertEqual(facts[("NAM", "equipment", "support_equipment")], 300)
            self.assertEqual(facts[("NAM", "variable", "NAM_lines_in_progress")], 0)
            settled = dict(facts)
            self.apply(block(body, "cancel_effect"), facts)
            self.assertEqual(facts, settled)
        facts = self.military_facts()
        facts[("NAM", "variable", "NAM_lines_in_progress")] = 3
        before = dict(facts)
        self.apply(block(body, "complete_effect"), facts)
        self.assertEqual(facts, before)

    def test_completed_forward_depot_stays_local_and_ordinary_lines_keep_their_price(self):
        body = self.bind_field(self.decisions["NAM_mil_forward_supply"])
        facts = self.military_facts()
        self.apply(block(body, "complete_effect"), facts)
        self.apply(block(body, "remove_effect"), facts)
        self.assertTrue(facts[("67", "has_dynamic_modifier", "NAM_mil_forward_depot")])
        self.assertFalse(facts[("67", "has_variable", "NAM_line_supply_deposit")])
        self.assertEqual(facts[("NAM", "variable", "NAM_lines_in_progress")], 0)
        settled = dict(facts)
        self.apply(block(body, "cancel_effect"), facts)
        self.apply(block(body, "remove_effect"), facts)
        self.assertEqual(facts, settled)
        definition = block(parsed("common/dynamic_modifiers/ADISCORD_dynamic_modifiers_NAM.txt"), "NAM_mil_forward_depot")
        self.assertTrue(matches_conditions(self.expand(block(definition, "enable")), facts, "67"))
        facts[("67", "is_controlled_by", "NAM")] = False
        self.assertFalse(matches_conditions(self.expand(block(definition, "enable")), facts, "67"))
        self.assertTrue(matches_conditions(self.expand(block(definition, "remove_trigger")), facts, "67"))
        facts = self.military_facts()
        facts[("67", "has_state_flag", "NAM_line_in_progress")] = True
        facts[("NAM", "variable", "NAM_lines_in_progress")] = 1
        facts[("NAM", "variable", "ADISCORD_economy_treasury")] = 9900
        facts[("NAM", "numeric", "has_political_power")] = 970
        self.apply(self.effects["NAM_line_release"], facts, "67")
        self.assertEqual(facts[("NAM", "variable", "ADISCORD_economy_treasury")], 10000)
        self.assertEqual(facts[("NAM", "numeric", "has_political_power")], 970)
        self.assertEqual(facts[("NAM", "equipment", "support_equipment")], 300)

    def test_carrier_order_matches_the_real_column_and_quartermaster_upgrades_supply(self):
        unit = block(block(parsed("common/units/ADISCORD_land_units.txt"), "sub_units"), "ADISCORD_mechanized_infantry")
        self.assertEqual(scalar(block(unit, "need"), "ADISCORD_armored_carrier_archetype"), "40")
        self.assertEqual(sum(e.key == "ADISCORD_mechanized_infantry" for e in walk(self.effects["NAM_order_ensure_templates"])), 4)
        body = self.decisions["NAM_mil_carrier_contract"]
        facts = self.military_facts()
        technology = ("NAM", "has_tech", "ADISCORD_tech_armored_carrier_program")
        self.apply(block(body, "complete_effect"), facts)
        self.assertFalse(facts.get(technology, False))
        self.apply(block(body, "remove_effect"), facts)
        self.assertTrue(facts[technology])
        self.assertEqual(facts[("NAM", "equipment", "ADISCORD_armored_carrier_2163")], 160)
        for quartermaster in (False, True):
            facts = self.military_facts()
            facts[("NAM", "has_completed_focus", "NAM_quartermaster")] = quartermaster
            self.apply(block(self.decisions["NAM_supply_order"], "complete_effect"), facts)
            self.assertEqual(facts.get(("NAM", "equipment", "ADISCORD_squad_weapons_equipment"), 0), 80 if quartermaster else 0)

    def test_military_programmes_fit_the_normal_preparation_window(self):
        paths = (
            (("count_garrisons", "mobile_columns", "motor_pool"), 28, 77),
            (("count_garrisons", "mobilisation_office", "line_survey", "reserve_rolls"), 21, 84),
            (("count_garrisons", "mobile_columns", "motor_pool", "quartermaster", "officer_courses"), 21, 119),
        )
        for path, duration, expected in paths:
            days = sum(int(scalar(self.focuses["NAM_" + f], "cost")) * 7 for f in path)
            self.assertEqual(days + duration, expected)
            self.assertLess(expected, 300)
        surveyed = sum(int(scalar(self.focuses["NAM_" + f], "cost")) * 7 for f in ("count_garrisons", "field_guards", "mobilisation_office", "line_survey"))
        engineers = surveyed + int(scalar(self.focuses["NAM_line_engineers"], "cost")) * 7
        self.assertEqual(max(surveyed + 35, engineers) + 14, 112)

    def economy_facts(self):
        facts = self.independent_facts()
        facts[("NAM", "variable", "NAM_oil_contracts")] = 2
        facts[("NAM", "variable", "NAM_project_slots")] = 2
        facts[("NAM", "variable", "NAM_projects_in_progress")] = 0
        facts[("fixture", "previous_state")] = "67"
        for state in ("67", "688", "689", "690", "719", "700"):
            for predicate in ("is_owned_by", "is_controlled_by"):
                facts[(state, predicate, "NAM")] = True
            for predicate in ("owns_state", "controls_state"):
                facts[("NAM", predicate, state)] = True
            facts[(state, "variable", "NAM_field_capacity")] = 8
            facts[(state, "has_variable", "NAM_field_capacity")] = True
            facts[(state, "variable", "NAM_field_condition")] = 80
        facts[("67", "numeric", "synthetic_refinery")] = 1
        facts[("700", "numeric", "fuel_silo")] = 1
        facts[("67", "fixture_free_building_slots", "arms_factory:1:yes")] = True
        return facts

    def bind_field(self, entries, state="67"):
        """Resolve the native decision target; shared effects retain their state scope."""
        return [replace(e, key=state if e.key == "FROM" else e.key,
                        value=self.bind_field(e.value, state) if isinstance(e.value, list)
                        else "NAM" if e.value == "ROOT" else e.value) for e in entries]

    def economy_projects(self):
        return {name: body for name, body in self.decisions.items() if name.startswith("NAM_econ_")}

    def test_economic_focuses_all_unlock_actions_and_orders_fit_the_deadline(self):
        source = read(TREES["main"][0])
        section = source.split("# ----- Oil economy -----", 1)[1].split("# ----- Garrisons", 1)[0]
        names = re.findall(r"\bid = (NAM_\w+)", section)
        self.assertEqual(len(names), 16)
        for name in names:
            self.assertTrue(any(e.key == "unlock_decision_tooltip" for e in walk(block(self.focuses[name], "completion_reward"))), name)
        projects = self.economy_projects()
        self.assertEqual(len(projects), 9)
        for name, project in projects.items():
            facts = self.economy_facts()
            project = self.bind_field(project)
            self.assertTrue(self.matches(block(project, "visible"), facts), name)
            self.assertTrue(self.matches(block(project, "available"), facts), name)
            if name.endswith("export_dispatch"):
                facts[("NAM", "has_country_flag", "NAM_econ_dispatch_paid")] = True
            self.assertFalse(self.matches(block(project, "cancel_trigger"), facts), name)
        paths = (
            (("well_register", "export_quays", "insured_cargoes"), 21),
            (("well_register", "domestic_refining", "refinery_programme"), 90 + 28),
            (("well_register", "contract_bureau", "field_repair_crews", "klyuchevsk_pipeline", "deep_wells"), 42),
            (("well_register", "domestic_refining", "machine_shops", "civilian_combine", "technical_college"), 35),
        )
        for focuses, duration in paths:
            days = sum(int(scalar(self.focuses["NAM_" + f], "cost")) * 7 for f in focuses)
            self.assertLess(days + duration, 300, focuses)

    def test_economic_prices_check_fractional_balances_and_cannot_double_charge(self):
        prices = {
            "insured_freighters": (35, 200, 0), "petrochemical_batch": (40, 200, 4000),
            "strategic_reserve": (30, 650, 0), "combine_arsenal": (40, 350, 0),
            "road_columns": (25, 150, 1500), "engineer_practice": (40, 200, 0),
            "deep_drilling": (30, 200, 0), "emergency_service": (30, 250, 0),
            "export_dispatch": (25, 50, 0),
        }
        keys = (("NAM", "numeric", "has_political_power"), ("NAM", "variable", "ADISCORD_economy_treasury"), ("NAM", "numeric", "has_fuel"))
        for suffix, amounts in prices.items():
            name = "NAM_econ_" + suffix
            project = self.bind_field(self.decisions[name])
            self.assertEqual(scalar(project, "cost"), "0")
            for key, price in zip(keys, amounts):
                if price == 0:
                    continue
                facts = self.economy_facts()
                facts.update(zip(keys, amounts))
                self.assertTrue(self.matches(block(project, "custom_cost_trigger"), facts), name)
                facts[key] -= 0.001
                self.assertFalse(self.matches(block(project, "custom_cost_trigger"), facts), name)
                before = dict(facts)
                self.apply(block(project, "complete_effect"), facts)
                self.assertEqual(facts, before, (name, key))
            facts = self.economy_facts()
            facts.update(zip(keys, amounts))
            self.apply(block(project, "complete_effect"), facts)
            for key in keys:
                self.assertEqual(facts[key], 0, name)
            self.assertEqual(facts[("NAM", "variable", "ADISCORD_economy_current_month_action_costs")], amounts[1])
            if suffix != "export_dispatch":
                paid = dict(facts)
                self.apply(block(project, "complete_effect"), facts)
                self.assertEqual(facts, paid, name)

    def test_national_economic_orders_refund_and_deliver_once(self):
        for name, project in self.economy_projects().items():
            if any(e.key == "state_target" for e in project) or name.endswith("export_dispatch"):
                continue
            for failed in (("NAM", "is_subject", "no"), ("NAM", "has_capitulated", "no")):
                for exit_name in ("remove_effect", "cancel_effect"):
                    facts = self.economy_facts()
                    self.apply(block(project, "complete_effect"), facts)
                    facts[failed] = False
                    self.assertTrue(self.matches(block(project, "cancel_trigger"), facts))
                    self.apply(block(project, exit_name), facts)
                    self.assertEqual(facts[("NAM", "numeric", "has_political_power")], 1000, name)
                    self.assertEqual(facts[("NAM", "variable", "ADISCORD_economy_treasury")], 10000, name)
                    self.assertEqual(facts[("NAM", "numeric", "has_fuel")], 20000, name)
                    facts[failed] = True
                    settled = dict(facts)
                    self.apply(block(project, "remove_effect"), facts)
                    self.apply(block(project, "cancel_effect"), facts)
                    self.assertEqual(facts, settled, name)
            facts = self.economy_facts()
            self.apply(block(project, "complete_effect"), facts)
            self.apply(block(project, "remove_effect"), facts)
            self.assertFalse(facts[("NAM", "has_country_flag", name + "_paid")])
            settled = dict(facts)
            self.apply(block(project, "remove_effect"), facts)
            self.apply(block(project, "cancel_effect"), facts)
            self.assertEqual(facts, settled, name)
            if name.endswith("petrochemical_batch"):
                self.assertEqual(facts[("NAM", "equipment", "motorized_equipment")], 150)
                self.assertEqual(facts[("NAM", "equipment", "artillery_equipment")], 60)
            if name.endswith("insured_freighters"):
                self.assertEqual(facts[("NAM", "equipment", "convoy")], 25)
            if name.endswith("strategic_reserve"):
                self.assertEqual(facts[("NAM", "numeric", "has_fuel")], 28000)
            if name.endswith("combine_arsenal"):
                self.assertEqual(facts[("67", "building", "arms_factory")], 1)
            if name.endswith("road_columns"):
                self.assertEqual(facts[("NAM", "equipment", "motorized_equipment")], 100)
            if name.endswith("engineer_practice"):
                self.assertEqual(facts[("NAM", "tech_bonus", name)], (0.5, 2, "industry"))

    def test_processing_requires_a_real_controlled_refinery_and_refunds_its_loss(self):
        project = self.decisions["NAM_econ_petrochemical_batch"]
        for lost in (("67", "numeric", "synthetic_refinery"), ("67", "is_owned_by", "NAM"), ("67", "is_controlled_by", "NAM")):
            facts = self.economy_facts()
            self.apply(block(project, "complete_effect"), facts)
            facts[lost] = 0
            self.assertFalse(self.matches(block(project, "available"), facts))
            self.assertTrue(self.matches(block(project, "cancel_trigger"), facts))
            self.apply(block(project, "remove_effect"), facts)
            self.assertEqual(facts[("NAM", "numeric", "has_fuel")], 20000)
            self.assertEqual(facts[("NAM", "variable", "ADISCORD_economy_treasury")], 10000)
            self.assertNotIn(("NAM", "equipment", "artillery_equipment"), facts)
            facts[("689", "numeric", "synthetic_refinery")] = 1
            self.assertTrue(self.matches(block(project, "available"), facts))

    def test_export_dispatch_only_pays_for_actual_deliveries_without_debiting_buyers(self):
        for fuel, active, paid, harbour, expected_revenue, deliveries in (
            (1499.99, True, True, True, 0, 0), (1500, True, True, True, 70, 1),
            (3000, True, True, True, 140, 2), (3000, False, True, True, 80, 2),
            (3000, True, True, False, 80, 2), (3000, True, False, True, 80, 2),
        ):
            facts = self.economy_facts()
            facts[("NAM", "numeric", "has_fuel")] = fuel
            facts[("NAM", "has_decision", "NAM_econ_export_dispatch")] = active
            facts[("NAM", "has_country_flag", "NAM_econ_dispatch_paid")] = paid
            facts[("NAM", "controls_state", "700")] = harbour
            for buyer in ("EFL", "AZH"):
                facts[(buyer, "has_country_flag", "NAM_oil_client")] = True
                facts[(buyer, "variable", "ADISCORD_economy_treasury")] = 123
            self.apply(self.effects["NAM_oil_settle_clients"], facts)
            self.assertEqual(facts[("NAM", "variable", "ADISCORD_economy_treasury")], 10000 + expected_revenue)
            self.assertEqual(facts[("NAM", "numeric", "has_fuel")], fuel - deliveries * 1500)
            self.assertEqual(sum(facts.get((buyer, "numeric", "has_fuel"), 0) for buyer in ("EFL", "AZH")), deliveries * 1500)
            for buyer in ("EFL", "AZH"):
                self.assertEqual(facts[(buyer, "variable", "ADISCORD_economy_treasury")], 123)
        dispatch = self.decisions["NAM_econ_export_dispatch"]
        facts = self.economy_facts()
        facts[("NAM", "variable", "NAM_oil_contracts")] = 0
        self.assertFalse(self.matches(block(dispatch, "available"), facts))
        facts[("NAM", "has_country_flag", "NAM_econ_dispatch_paid")] = True
        self.assertFalse(self.matches(block(dispatch, "cancel_trigger"), facts))
        before = facts[("NAM", "variable", "ADISCORD_economy_treasury")]
        self.apply(block(dispatch, "cancel_effect"), facts)
        self.assertFalse(facts[("NAM", "has_country_flag", "NAM_econ_dispatch_paid")])
        self.assertEqual(facts[("NAM", "variable", "ADISCORD_economy_treasury")], before)

    def test_field_orders_share_slots_and_cannot_overwrite_another_payment(self):
        projects = [self.bind_field(self.decisions["NAM_econ_" + name]) for name in ("deep_drilling", "emergency_service")]
        for project in projects:
            facts = self.economy_facts()
            self.apply(block(project, "complete_effect"), facts)
            self.assertEqual(facts[("NAM", "variable", "NAM_projects_in_progress")], 1)
            self.assertTrue(facts[("67", "has_state_flag", "NAM_project_in_progress")])
            paid = dict(facts)
            for contender in projects:
                self.assertFalse(self.matches(block(contender, "available"), facts))
                self.apply(block(contender, "complete_effect"), facts)
                self.assertEqual(facts, paid)
            for name in ("NAM_project_repair_wells", "NAM_project_refinery"):
                contender = self.bind_field(self.decisions[name])
                self.assertFalse(self.matches(block(contender, "available"), facts), name)
            # A second state may use the second slot; a third state cannot pay.
            second = self.bind_field(self.decisions["NAM_econ_deep_drilling"], "689")
            self.apply(block(second, "complete_effect"), facts)
            self.assertEqual(facts[("NAM", "variable", "NAM_projects_in_progress")], 2)
            third = self.bind_field(self.decisions["NAM_econ_emergency_service"], "690")
            paid = dict(facts)
            self.assertFalse(self.matches(block(third, "available"), facts))
            self.apply(block(third, "complete_effect"), facts)
            self.assertEqual(facts, paid)
            self.apply(block(project, "cancel_effect"), facts)
            self.assertEqual(facts[("NAM", "variable", "NAM_projects_in_progress")], 1)
            self.assertEqual(facts[("NAM", "numeric", "has_political_power")], 970)
            self.assertEqual(facts[("NAM", "variable", "ADISCORD_economy_treasury")], 9800)
            self.assertTrue(facts[("689", "has_state_flag", "NAM_project_in_progress")])
            self.assertEqual(facts[("689", "variable", "NAM_project_deposit")], 200)

    def test_field_delivery_and_refund_release_only_their_own_escrow(self):
        with patch.dict(self.effects, {"NAM_oil_refresh": []}):
            for suffix, variable, delta in (("deep_drilling", "NAM_field_capacity", 2), ("emergency_service", "NAM_field_condition", 20)):
                project = self.bind_field(self.decisions["NAM_econ_" + suffix])
                facts = self.economy_facts()
                self.apply(block(project, "complete_effect"), facts)
                before = facts[("67", "variable", variable)]
                self.apply(block(project, "remove_effect"), facts)
                self.assertEqual(facts[("67", "variable", variable)], before + delta)
                self.assertEqual(facts[("NAM", "variable", "NAM_projects_in_progress")], 0)
                self.assertFalse(facts[("67", "has_variable", "NAM_project_pp_deposit")])
                settled = dict(facts)
                self.apply(block(project, "cancel_effect"), facts)
                self.apply(block(project, "remove_effect"), facts)
                self.assertEqual(facts, settled)
                for lost in (("67", "is_owned_by", "NAM"), ("67", "is_controlled_by", "NAM"), ("NAM", "is_subject", "no"), ("NAM", "has_capitulated", "no")):
                    facts = self.economy_facts()
                    self.apply(block(project, "complete_effect"), facts)
                    facts[lost] = False
                    self.assertTrue(self.matches(block(project, "cancel_trigger"), facts))
                    self.apply(block(project, "remove_effect"), facts)
                    self.assertEqual(facts[("NAM", "numeric", "has_political_power")], 1000)
                    self.assertEqual(facts[("NAM", "variable", "ADISCORD_economy_treasury")], 10000)
                    self.assertEqual(facts[("NAM", "variable", "NAM_projects_in_progress")], 0)
                    settled = dict(facts)
                    self.apply(block(project, "cancel_effect"), facts)
                    self.assertEqual(facts, settled)
            old = self.bind_field(self.decisions["NAM_econ_deep_drilling"])
            new = self.bind_field(self.decisions["NAM_econ_emergency_service"])
            facts = self.economy_facts()
            self.apply(block(old, "complete_effect"), facts)
            self.apply(block(old, "cancel_effect"), facts)
            self.apply(block(new, "complete_effect"), facts)
            paid = dict(facts)
            self.apply(block(old, "cancel_effect"), facts)
            self.apply(block(old, "remove_effect"), facts)
            self.assertEqual(facts, paid)
            # Ordinary repairs escrow money only; the optional PP receipt must not invent a refund.
            facts = self.economy_facts()
            facts[("67", "has_state_flag", "NAM_project_in_progress")] = True
            facts[("67", "variable", "NAM_project_deposit")] = 150
            facts[("NAM", "variable", "NAM_projects_in_progress")] = 1
            facts[("NAM", "variable", "ADISCORD_economy_treasury")] = 9850
            facts[("NAM", "numeric", "has_political_power")] = 975
            self.apply(self.effects["NAM_project_release"], facts, "67")
            self.assertEqual(facts[("NAM", "variable", "ADISCORD_economy_treasury")], 10000)
            self.assertEqual(facts[("NAM", "numeric", "has_political_power")], 975)
            self.assertEqual(facts[("NAM", "variable", "NAM_projects_in_progress")], 0)

    def test_deep_drilling_ceiling_and_scorched_fields_block_payment(self):
        for suffix in ("deep_drilling", "emergency_service"):
            project = self.bind_field(self.decisions["NAM_econ_" + suffix])
            facts = self.economy_facts()
            facts[("67", "has_state_flag", "NAM_wells_scorched")] = True
            self.assertFalse(self.matches(block(project, "available"), facts))
            before = dict(facts)
            self.apply(block(project, "complete_effect"), facts)
            self.assertEqual(facts, before)
        project = self.bind_field(self.decisions["NAM_econ_deep_drilling"])
        for capacity, possible in ((10, True), (10.001, False), (12, False)):
            facts = self.economy_facts()
            facts[("67", "variable", "NAM_field_capacity")] = capacity
            self.assertEqual(self.matches(block(project, "available"), facts), possible)

    def admin_projects(self):
        return {name: body for name, body in self.decisions.items() if name.startswith("NAM_admin_")}

    def admin_facts(self):
        facts = self.independent_facts()
        facts[("NAM", "fixture_power_balance", "NAM_ladder_bop")] = True
        facts[("NAM", "power_balance_value", "NAM_ladder_bop")] = 0
        facts[("688", "fixture_free_building_slots", "industrial_complex:1:yes")] = True
        for group in ("nam", "dist", "oil", "garr", "trade"):
            facts[("NAM", "variable", "NAM_grp_" + group + "_support")] = 70
        return facts

    def start_admin_project(self, project, facts):
        facts[("NAM", "numeric", "has_political_power")] -= int(scalar(project, "cost"))
        self.apply(block(project, "complete_effect"), facts)

    def test_admin_focus_unlocks_follow_the_exclusive_courses(self):
        owners = {
            "common_stores": "open_ledgers", "compulsory_delivery": "vertical",
            "warehouse_inspection": "inspectors", "tax_arrears": "tax_rolls",
            "transport_requisition": "emergency_writ", "governor_levy": "namestnik_circuits",
            "voluntary_enrolment": "districts", "pay_local_arrears": "public_payroll",
            "district_guard_contract": "district_guarantees",
            "svetlogorsk_cooperative": "district_assemblies", "seal_appeal": "seal_courts",
        }
        projects = self.admin_projects()
        self.assertEqual(set(projects), {"NAM_admin_" + name for name in owners})
        for suffix, owner in owners.items():
            name = "NAM_admin_" + suffix
            reward = block(self.focuses["NAM_" + owner], "completion_reward")
            self.assertIn(name, {e.value for e in walk(reward) if e.key == "unlock_decision_tooltip"})
            facts = self.admin_facts()
            self.assertTrue(self.matches(block(projects[name], "visible"), facts), name)
            self.assertTrue(self.matches(block(projects[name], "available"), facts), name)
            facts[("NAM", "has_completed_focus", "NAM_" + owner)] = False
            self.assertFalse(self.matches(block(projects[name], "visible"), facts), name)
        budget = block(self.focuses["NAM_one_budget"], "completion_reward")
        self.assertIn("NAM_emergency_decrees", {e.value for e in walk(budget) if e.key == "unlock_decision_tooltip"})

    def test_admin_custom_prices_have_exact_boundaries_and_single_debit(self):
        for suffix, pp, cash in (("voluntary_enrolment", 30, 150), ("pay_local_arrears", 20, 200),
                                 ("district_guard_contract", 35, 200), ("svetlogorsk_cooperative", 30, 300)):
            name = "NAM_admin_" + suffix
            project = self.decisions[name]
            self.assertEqual(scalar(project, "cost"), "0")
            for political, treasury, affordable in ((pp - 0.001, cash, False), (pp, cash - 0.001, False), (pp, cash, True)):
                facts = self.admin_facts()
                facts[("NAM", "numeric", "has_political_power")] = political
                facts[("NAM", "variable", "ADISCORD_economy_treasury")] = treasury
                self.assertEqual(self.matches(block(project, "custom_cost_trigger"), facts), affordable, name)
                self.apply(block(project, "complete_effect"), facts)
                self.assertEqual(facts[("NAM", "numeric", "has_political_power")], political - (pp if affordable else 0))
                self.assertEqual(facts[("NAM", "variable", "ADISCORD_economy_treasury")], treasury - (cash if affordable else 0))
                self.assertEqual(facts.get(("NAM", "has_country_flag", name + "_paid"), False), affordable)
            facts = self.admin_facts()
            self.start_admin_project(project, facts)
            paid = dict(facts)
            self.apply(block(project, "complete_effect"), facts)
            self.assertEqual(facts, paid, name)
            self.assertEqual(facts[("NAM", "variable", "ADISCORD_economy_current_month_action_costs")], cash)

    def test_admin_orders_refund_both_currencies_once_on_every_exit(self):
        for name, project in self.admin_projects().items():
            for failed in (("NAM", "is_subject", "no"), ("NAM", "has_capitulated", "no"),
                           ("NAM", "fixture_power_balance", "NAM_ladder_bop")):
                for exit_name in ("remove_effect", "cancel_effect"):
                    facts = self.admin_facts()
                    self.start_admin_project(project, facts)
                    facts[failed] = False
                    self.assertTrue(self.matches(block(project, "cancel_trigger"), facts), name)
                    self.apply(block(project, exit_name), facts)
                    self.assertEqual(facts[("NAM", "numeric", "has_political_power")], 1000, name)
                    self.assertEqual(facts[("NAM", "variable", "ADISCORD_economy_treasury")], 10000, name)
                    self.assertFalse(facts[("NAM", "has_country_flag", name + "_paid")])
                    facts[failed] = True
                    settled = dict(facts)
                    self.apply(block(project, "remove_effect"), facts)
                    self.apply(block(project, "cancel_effect"), facts)
                    self.assertEqual(facts, settled, name)
                    self.assertFalse(any(key[1] in ("equipment", "reward", "building") for key in facts))

    def test_district_trust_is_required_through_delivery_but_payroll_can_restore_it(self):
        for suffix, threshold in (("voluntary_enrolment", 50), ("district_guard_contract", 55), ("svetlogorsk_cooperative", 60)):
            name = "NAM_admin_" + suffix
            project = self.decisions[name]
            facts = self.admin_facts()
            support = ("NAM", "variable", "NAM_grp_dist_support")
            facts[support] = threshold - 0.001
            self.assertFalse(self.matches(block(project, "available"), facts), name)
            self.apply(block(project, "complete_effect"), facts)
            self.assertFalse(facts.get(("NAM", "has_country_flag", name + "_paid"), False))
            facts[support] = threshold
            self.assertTrue(self.matches(block(project, "available"), facts), name)
            self.start_admin_project(project, facts)
            facts[support] = threshold - 0.001
            self.assertTrue(self.matches(block(project, "cancel_trigger"), facts), name)
            self.apply(block(project, "remove_effect"), facts)
            self.assertEqual(facts[("NAM", "variable", "ADISCORD_economy_treasury")], 10000)
            self.assertEqual(facts[("NAM", "numeric", "has_political_power")], 1000)
        payroll = self.decisions["NAM_admin_pay_local_arrears"]
        facts = self.admin_facts()
        facts[("NAM", "variable", "NAM_grp_dist_support")] = 10
        self.assertTrue(self.matches(block(payroll, "available"), facts))
        self.start_admin_project(payroll, facts)
        self.apply(block(payroll, "remove_effect"), facts)
        self.assertEqual(facts[("NAM", "variable", "NAM_grp_dist_support")], 22)

    def test_admin_deliveries_have_distinct_material_and_political_results(self):
        expected = {
            "common_stores": {("equipment", "support_equipment"): 100, ("numeric", "has_fuel"): 2000},
            "compulsory_delivery": {("equipment", "infantry_equipment"): 4500, ("variable", "NAM_grp_dist_support"): -6, ("variable", "NAM_grp_oil_support"): -3},
            "warehouse_inspection": {("equipment", "artillery_equipment"): 40, ("equipment", "support_equipment"): 90, ("variable", "NAM_grp_garr_support"): -4},
            "tax_arrears": {("variable", "ADISCORD_economy_treasury"): 350, ("variable", "NAM_grp_trade_support"): -3},
            "transport_requisition": {("equipment", "motorized_equipment"): 100, ("numeric", "has_fuel"): 1500, ("variable", "NAM_grp_dist_support"): -5},
            "governor_levy": {("variable", "ADISCORD_economy_treasury"): 400, ("variable", "NAM_grp_nam_support"): -5},
            "voluntary_enrolment": {("numeric", "has_manpower"): 6000},
            "pay_local_arrears": {("reward", "stability"): 0.02, ("variable", "NAM_grp_dist_support"): 12},
            "district_guard_contract": {("equipment", "infantry_equipment"): 6000, ("equipment", "support_equipment"): 60},
            "svetlogorsk_cooperative": {},
            "seal_appeal": {("variable", "NAM_grp_nam_support"): 4, ("variable", "NAM_grp_dist_support"): 8},
        }
        for suffix, deltas in expected.items():
            project = self.decisions["NAM_admin_" + suffix]
            facts = self.admin_facts()
            self.start_admin_project(project, facts)
            before = dict(facts)
            self.apply(block(project, "remove_effect"), facts)
            for key, delta in deltas.items():
                full_key = ("NAM", *key)
                self.assertAlmostEqual(facts[full_key] - before.get(full_key, 0), delta, msg=suffix)
            settled = dict(facts)
            self.apply(block(project, "remove_effect"), facts)
            self.apply(block(project, "cancel_effect"), facts)
            self.assertEqual(facts, settled, suffix)
            if suffix in ("compulsory_delivery", "warehouse_inspection", "transport_requisition", "governor_levy"):
                self.assertLess(facts[("NAM", "power_balance_value", "NAM_ladder_bop")], 0)
            if suffix in ("voluntary_enrolment", "pay_local_arrears", "district_guard_contract", "svetlogorsk_cooperative"):
                self.assertGreater(facts[("NAM", "power_balance_value", "NAM_ladder_bop")], 0)
            if suffix == "svetlogorsk_cooperative":
                self.assertEqual(facts[("688", "building", "industrial_complex")], 1)
                self.assertEqual(facts[("688", "reward", "building_slots")], 1)

    def test_cooperative_refunds_lost_site_but_general_orders_survive_war_and_exile(self):
        for name, project in self.admin_projects().items():
            facts = self.admin_facts()
            self.start_admin_project(project, facts)
            facts[("NAM", "has_global_flag", BASE + "_started")] = True
            facts[("NAM", "has_global_flag", BASE + "_resolved")] = True
            facts[("NAM", "has_global_flag", BASE + "_island_exile")] = True
            facts[("NAM", "owns_state", "688")] = False
            self.assertEqual(self.matches(block(project, "cancel_trigger"), facts), name.endswith("svetlogorsk_cooperative"))
        project = self.decisions["NAM_admin_svetlogorsk_cooperative"]
        for lost in (("NAM", "owns_state", "688"), ("NAM", "controls_state", "688"),
                     ("688", "fixture_free_building_slots", "industrial_complex:1:yes")):
            facts = self.admin_facts()
            self.start_admin_project(project, facts)
            facts[lost] = False
            self.apply(block(project, "remove_effect"), facts)
            self.assertEqual(facts[("NAM", "variable", "ADISCORD_economy_treasury")], 10000)
            self.assertEqual(facts[("NAM", "numeric", "has_political_power")], 1000)
            self.assertNotIn(("688", "building", "industrial_complex"), facts)
            facts[lost] = True
            self.assertTrue(self.matches(block(project, "available"), facts))
        self.assertEqual(scalar(project, "fire_only_once"), "no")

    def test_seal_appeals_moderate_both_extremes_without_crossing_the_centre(self):
        project = self.decisions["NAM_admin_seal_appeal"]
        key = ("NAM", "power_balance_value", "NAM_ladder_bop")
        for initial, final in ((-0.8, -0.7), (-0.11, -0.01), (-0.1, -0.1), (0, 0), (0.1, 0.1), (0.11, 0.01), (0.8, 0.7)):
            facts = self.admin_facts()
            facts[key] = initial
            self.start_admin_project(project, facts)
            self.apply(block(project, "remove_effect"), facts)
            self.assertAlmostEqual(facts[key], final)

    def test_admin_timeline_and_emergency_budget(self):
        for course in (("vertical", "inspectors", "emergency_writ", "namestnik_circuits"),
                       ("districts", "public_payroll", "district_guarantees", "district_assemblies")):
            sequence = ("open_ledgers", *course[:3], "one_budget", course[3], "seal_courts")
            days = sum(int(scalar(self.focuses["NAM_" + name], "cost")) * 7 for name in sequence)
            self.assertEqual(days, 161)
            self.assertLess(days + 14 + 21, 300)
        budget = block(block(parsed(f"common/decisions/{BASE}_decisions.txt"), "NAM_treasury"), "NAM_emergency_decrees")
        self.assertEqual(scalar(budget, "cost"), "50")
        facts = self.admin_facts()
        self.apply(block(budget, "complete_effect"), facts)
        self.assertEqual(facts[("NAM", "variable", "ADISCORD_economy_treasury")], 10500)
        self.assertEqual(facts[("NAM", "variable", "ADISCORD_economy_current_month_action_income")], 500)

    def independence_projects(self):
        source = parsed(f"common/decisions/{BASE}_decisions.txt")
        return {e.key: e.value for category in ("NAM_national_programmes", "NAM_restitution")
                for e in block(source, category) if e.key.startswith("NAM_ind_")}

    def independent_facts(self):
        facts = self.facts()
        facts[("NAM", "is_subject", "no")] = True
        facts[("NAM", "has_country_flag", "NAM_center_vanished")] = True
        facts[("NAM", "has_global_flag", BASE + "_started")] = False
        facts[("NAM", "has_global_flag", BASE + "_scheduled")] = True
        facts[("EFL", "exists", "yes")] = True
        facts[("NAM", "variable", "NAM_rw_tension")] = 30
        return facts

    def test_independence_focuses_unlock_usable_programmes(self):
        expected = {
            "NAM_independence_day": {"NAM_ind_sovereign_collections"},
            "NAM_neutral_basin": {"NAM_ind_border_dossier", "NAM_restitution_note"},
            "NAM_basin_is_ours": {"NAM_ind_defence_supply"},
            "NAM_provisional_statute": {"NAM_ind_statute_commissions", "NAM_ind_reservist_register"},
            "NAM_rom_address": {"NAM_campaign_our_own_word"},
        }
        for focus_id, names in expected.items():
            reward = block(self.focuses[focus_id], "completion_reward")
            self.assertEqual({e.value for e in reward if e.key == "unlock_decision_tooltip"}, names)
        projects = self.independence_projects()
        self.assertEqual(len(projects), 5)
        for name, project in projects.items():
            facts = self.independent_facts()
            facts[("NAM", "has_country_flag", "NAM_ind_defence_supply_authorised")] = True
            self.assertTrue(self.matches(block(project, "visible"), facts), name)
            self.assertTrue(self.matches(block(project, "available"), facts), name)
            self.assertFalse(self.matches(block(project, "cancel_trigger"), facts), name)
            self.assertGreater(int(scalar(project, "cost")), 0)
            self.assertFalse(any(e.key in ("custom_cost_text", "custom_cost_trigger") for e in project))
            self.assertFalse(any(e.key == "add_political_power" for e in walk(block(project, "complete_effect"))))
        address = block(self.focuses["NAM_rom_address"], "completion_reward")
        self.assertEqual(sum(e.key == "ADISCORD_campaign_slot_grant" for e in walk(address)), 1)
        self.assertEqual(scalar(block(address, "country_event"), "id"), BASE + ".70")

    def test_independent_institutions_survive_war_and_settlement_but_refund_subjugation(self):
        for name, project in self.independence_projects().items():
            if name == "NAM_ind_border_dossier":
                continue
            for phase in ("preparation", "war", "nam_victory", "compromise", "island_exile"):
                facts = self.independent_facts()
                if phase != "preparation":
                    facts[("NAM", "has_global_flag", BASE + "_scheduled")] = False
                    facts[("NAM", "has_global_flag", BASE + "_started")] = True
                if phase not in ("preparation", "war"):
                    facts[("NAM", "has_global_flag", BASE + "_resolved")] = True
                    facts[("NAM", "has_global_flag", BASE + "_" + phase)] = True
                if phase == "island_exile":
                    facts[("NAM", "owns_state", "688")] = False
                    facts[("NAM", "controls_state", "688")] = False
                self.assertTrue(self.matches(block(project, "available"), facts), (name, phase))
                self.assertFalse(self.matches(block(project, "cancel_trigger"), facts), (name, phase))
                for key in (("NAM", "is_subject", "no"), ("NAM", "has_capitulated", "no")):
                    ended = dict(facts)
                    ended[key] = False
                    self.assertFalse(self.matches(block(project, "available"), ended))
                    self.assertTrue(self.matches(block(project, "cancel_trigger"), ended))

    def test_independence_orders_refund_once_and_cannot_deliver_after_refund(self):
        for name, project in self.independence_projects().items():
            for first_exit in ("cancel_effect", "remove_effect"):
                with self.subTest(project=name, exit=first_exit):
                    facts = self.independent_facts()
                    facts[("NAM", "numeric", "has_political_power")] -= int(scalar(project, "cost"))
                    self.apply(block(project, "complete_effect"), facts)
                    receipt = ("NAM", "has_country_flag", name + "_paid")
                    self.assertTrue(facts[receipt])
                    facts[("NAM", "is_subject", "no")] = False
                    self.apply(block(project, first_exit), facts)
                    self.assertEqual(facts[("NAM", "numeric", "has_political_power")], 1000)
                    self.assertFalse(facts[receipt])
                    # Liberation and an ordinary reload preserve the settled receipt.
                    facts = dict(facts)
                    facts[("NAM", "is_subject", "no")] = True
                    self.apply(block(project, "remove_effect"), facts)
                    self.apply(block(project, "cancel_effect"), facts)
                    self.assertEqual(facts[("NAM", "numeric", "has_political_power")], 1000)
                    self.assertEqual(facts[("NAM", "variable", "ADISCORD_economy_treasury")], 10000)
                    self.assertFalse(any(key[1] == "equipment" for key in facts))

    def test_independence_deliveries_reach_nam_and_update_real_accounts(self):
        projects = self.independence_projects()
        for name, deltas in (
            ("NAM_ind_sovereign_collections", {("NAM", "variable", "ADISCORD_economy_treasury"): 250,
                                                ("NAM", "variable", "ADISCORD_economy_current_month_action_income"): 250}),
            ("NAM_ind_defence_supply", {("NAM", "equipment", "infantry_equipment"): 6000,
                                        ("NAM", "equipment", "support_equipment"): 60}),
            ("NAM_ind_statute_commissions", {("NAM", "variable", "NAM_grp_dist_support"): 6,
                                             ("NAM", "variable", "NAM_grp_nam_support"): 3,
                                             ("NAM", "reward", "stability"): 0.02}),
            ("NAM_ind_border_dossier", {("NAM", "variable", "NAM_rw_tension"): -12,
                                        ("NAM", "variable", "NAM_grp_trade_support"): 3}),
        ):
            facts = self.independent_facts()
            # The threshold dispatcher is tested separately; no threshold is crossed here.
            facts[("NAM", "has_global_flag", BASE + "_scheduled")] = name == "NAM_ind_border_dossier"
            before = dict(facts)
            self.apply(block(projects[name], "complete_effect"), facts)
            self.apply(block(projects[name], "remove_effect"), facts)
            for key, delta in deltas.items():
                self.assertAlmostEqual(facts[key] - before.get(key, 0), delta, msg=name)
            settled = dict(facts)
            self.apply(block(projects[name], "remove_effect"), facts)
            self.apply(block(projects[name], "cancel_effect"), facts)
            self.assertEqual(facts, settled, name)
        treasury = self.effects["NAM_receive_250"]
        self.assertEqual(scalar(treasury, "ADISCORD_economy_mark_dirty"), "yes")
        recruits = projects["NAM_ind_reservist_register"]
        self.assertEqual([e.value for e in walk(block(recruits, "remove_effect")) if e.key == "add_manpower"], ["4000"])

    def test_neutral_dossier_closes_with_its_claim_and_defence_is_not_a_bypass_reward(self):
        projects = self.independence_projects()
        dossier = projects["NAM_ind_border_dossier"]
        cases = (
            (("NAM", "has_global_flag", BASE + "_scheduled"), False),
            (("NAM", "has_global_flag", BASE + "_started"), True),
            (("NAM", "has_global_flag", BASE + "_resolved"), True),
            (("NAM", "has_country_flag", "NAM_rw_war_dispatched"), True),
            (("EFL", "exists", "yes"), False),
            (("NAM", "variable", "NAM_rw_tension"), 0),
        )
        for key, value in cases:
            facts = self.independent_facts()
            self.apply(block(dossier, "complete_effect"), facts)
            facts[key] = value
            tension = facts[("NAM", "variable", "NAM_rw_tension")]
            self.assertFalse(self.matches(block(dossier, "available"), facts))
            self.assertTrue(self.matches(block(dossier, "cancel_trigger"), facts))
            self.apply(block(dossier, "remove_effect"), facts)
            self.assertEqual(facts[("NAM", "variable", "NAM_rw_tension")], tension)
        defence = projects["NAM_ind_defence_supply"]
        facts = self.independent_facts()
        # Both focuses may be bypassed when the threat ends, without running either reward.
        self.assertFalse(self.matches(block(defence, "visible"), facts))
        reward = block(self.focuses["NAM_basin_is_ours"], "completion_reward")
        marker = next(e for e in walk(reward) if e.key == "set_country_flag" and e.value == "NAM_ind_defence_supply_authorised")
        self.apply([marker], facts)
        self.assertTrue(self.matches(block(defence, "visible"), facts))
        notes = block(block(parsed(f"common/decisions/{BASE}_decisions.txt"), "NAM_restitution"), "NAM_restitution_note")
        facts[("NAM", "has_completed_focus", "NAM_restitution_desk")] = False
        self.assertTrue(self.matches(block(notes, "visible"), facts))
        facts[("NAM", "has_completed_focus", "NAM_neutral_basin")] = False
        self.assertFalse(self.matches(block(notes, "visible"), facts))

    def test_independence_campaign_slot_survives_peace_and_returns_once_on_subjugation(self):
        campaign = block(block(parsed(f"common/decisions/{BASE}_decisions.txt"), "NAM_public_campaigns"), "NAM_campaign_our_own_word")
        shared = {e.key: e.value for e in parsed("common/scripted_triggers/ADISCORD_shared_action_triggers.txt")}
        with patch.dict(self.triggers, shared):
            facts = self.independent_facts()
            slots = ("NAM", "variable", "ADISCORD_available_campaign_slots")
            facts[slots] = 0
            self.assertFalse(self.matches(block(campaign, "available"), facts))
            facts[slots] = 1
            self.assertTrue(self.matches(block(campaign, "available"), facts))
            self.apply(block(campaign, "complete_effect"), facts)
            self.assertEqual(facts[slots], 0)
            for phase in ("started", "resolved", "island_exile"):
                facts[("NAM", "has_global_flag", BASE + "_" + phase)] = True
                self.assertFalse(self.matches(block(campaign, "cancel_trigger"), facts))
            facts[("NAM", "is_subject", "no")] = False
            self.assertTrue(self.matches(block(campaign, "cancel_trigger"), facts))
            self.apply(block(campaign, "cancel_effect"), facts)
            self.assertEqual(facts[slots], 1)
            self.apply(block(campaign, "remove_effect"), facts)
            self.apply(block(campaign, "cancel_effect"), facts)
            self.assertEqual(facts[slots], 1)

    def test_independence_programmes_fit_both_normal_focus_routes(self):
        projects = self.independence_projects()
        for course in ("NAM_neutral_basin", "NAM_basin_is_ours"):
            days = 0
            for focus_id in ("NAM_independence_day", course, "NAM_provisional_statute", "NAM_rom_address"):
                days += int(scalar(self.focuses[focus_id], "cost")) * 7
                unlocks = [e.value for e in block(self.focuses[focus_id], "completion_reward") if e.key == "unlock_decision_tooltip"]
                for name in unlocks:
                    if name in projects:
                        self.assertLess(days + int(scalar(projects[name], "days_remove")), 300, name)
            self.assertEqual(days, 70)
            self.assertLess(days + 60, 300)

    def colonial_projects(self):
        category = block(parsed(f"common/decisions/{BASE}_decisions.txt"), "NAM_colony")
        return {e.key: e.value for e in category if e.key.startswith("NAM_colonial_")}

    def colonial_facts(self):
        facts = self.facts()
        facts[("NAM", "is_subject", "yes")] = True
        facts[("WRK", "exists", "yes")] = True
        facts[("NAM", "has_global_flag", BASE + "_started")] = False
        facts[("NAM", "has_variable", "NAM_underground")] = True
        facts[("NAM", "has_variable", "NAM_hidden_reserve")] = True
        facts[("NAM", "variable", "NAM_underground")] = 30
        facts[("700", "fixture_free_building_slots", "arms_factory:1:yes")] = True
        return facts

    def test_colonial_projects_unlock_before_collapse_and_recheck_delivery(self):
        projects = self.colonial_projects()
        self.assertEqual(len(projects), 12)
        for name, decision in projects.items():
            with self.subTest(project=name):
                focus_id = scalar(block(decision, "visible"), "has_completed_focus")
                reward = block(self.focuses[focus_id], "completion_reward")
                self.assertIn(name, [e.value for e in reward if e.key == "unlock_decision_tooltip"])
                facts = self.colonial_facts()
                self.assertTrue(self.matches(block(decision, "visible"), facts))
                self.assertTrue(self.matches(block(decision, "available"), facts))
                self.assertFalse(self.matches(block(decision, "cancel_trigger"), facts))
                self.assertNotIn("custom_cost_text", [e.key for e in decision])
                # The engine pays the native cost once; no script debits it again.
                self.assertFalse(any(e.key == "add_political_power" for e in walk(block(decision, "complete_effect"))))
                settlement = block(block(decision, "remove_effect"), "if")
                self.assertEqual(scalar(block(settlement, "limit"), "NAM_colonial_programme_operable"), "yes")
                for key in (
                    ("NAM", "has_country_flag", "NAM_center_vanished"),
                    ("NAM", "has_global_flag", "ADISCORD_vorkerland_collapse_wars_started"),
                ):
                    ended = dict(facts)
                    ended[key] = True
                    self.assertFalse(self.matches(block(decision, "visible"), ended))
                    self.assertFalse(self.matches(block(decision, "available"), ended))
                    self.assertTrue(self.matches(block(decision, "cancel_trigger"), ended))
                for key in (("WRK", "exists", "yes"), ("NAM", "has_capitulated", "no"), ("NAM", "is_subject", "yes")):
                    ended = dict(facts)
                    ended[key] = False
                    self.assertTrue(self.matches(block(decision, "cancel_trigger"), ended))

    def test_colonial_refunds_are_once_only_and_prevent_late_delivery(self):
        for name, decision in self.colonial_projects().items():
            for first_exit in ("cancel_effect", "remove_effect"):
                with self.subTest(project=name, exit=first_exit):
                    facts = self.colonial_facts()
                    cost = int(scalar(decision, "cost"))
                    facts[("NAM", "numeric", "has_political_power")] -= cost
                    self.apply(block(decision, "complete_effect"), facts)
                    receipt = ("NAM", "has_country_flag", name + "_paid")
                    self.assertTrue(facts[receipt])
                    facts[("NAM", "has_country_flag", "NAM_center_vanished")] = True
                    self.apply(block(decision, first_exit), facts)
                    self.assertFalse(facts[receipt])
                    self.assertEqual(facts[("NAM", "numeric", "has_political_power")], 1000)
                    # A second callback, including after ordinary save/load, cannot refund or deliver twice.
                    facts = dict(facts)
                    self.apply(block(decision, "cancel_effect"), facts)
                    self.apply(block(decision, "remove_effect"), facts)
                    self.assertEqual(facts[("NAM", "numeric", "has_political_power")], 1000)
                    self.assertFalse(any(key[1] == "equipment" for key in facts))

    def test_colonial_delivery_consumes_receipt_and_lost_harbour_cancels(self):
        projects = self.colonial_projects()
        for name, resource, expected in (
            ("NAM_colonial_rifle_contract", ("NAM", "equipment", "infantry_equipment"), 4500),
            ("NAM_colonial_fuel_reserve", ("NAM", "numeric", "has_fuel"), 26000),
        ):
            decision = projects[name]
            facts = self.colonial_facts()
            self.apply(block(decision, "complete_effect"), facts)
            self.apply(block(decision, "remove_effect"), facts)
            self.assertEqual(facts[resource], expected)
            self.apply(block(decision, "remove_effect"), facts)
            self.apply(block(decision, "cancel_effect"), facts)
            self.assertEqual(facts[resource], expected)
            self.assertEqual(facts[("NAM", "numeric", "has_political_power")], 1000)
        factory = projects["NAM_colonial_workshops"]
        self.assertEqual(scalar(factory, "fire_only_once"), "no")
        self.assertEqual(scalar(factory, "days_re_enable"), "120")
        for condition in ("owns_state", "controls_state"):
            facts = self.colonial_facts()
            facts[("NAM", condition, "700")] = False
            self.assertFalse(self.matches(block(factory, "available"), facts))
            self.assertTrue(self.matches(block(factory, "cancel_trigger"), facts))
            limit = block(block(block(factory, "remove_effect"), "if"), "limit")
            facts[("NAM", "has_country_flag", "NAM_colonial_workshops_paid")] = True
            self.assertFalse(self.matches(limit, facts))

    def test_colonial_workshop_refunds_when_another_project_fills_the_site(self):
        factory = self.colonial_projects()["NAM_colonial_workshops"]
        self.assertEqual(sum(e.key == "free_building_slots" for e in walk(factory)), 3)
        facts = self.colonial_facts()
        self.assertTrue(self.matches(block(factory, "available"), facts))
        facts[("NAM", "numeric", "has_political_power")] -= 60
        self.apply(block(factory, "complete_effect"), facts)
        facts[("700", "fixture_free_building_slots", "arms_factory:1:yes")] = False
        self.assertFalse(self.matches(block(factory, "available"), facts))
        self.assertTrue(self.matches(block(factory, "cancel_trigger"), facts))
        self.apply(block(factory, "remove_effect"), facts)
        self.assertEqual(facts[("NAM", "numeric", "has_political_power")], 1000)
        self.assertFalse(facts[("NAM", "has_country_flag", "NAM_colonial_workshops_paid")])

    def test_colonial_propaganda_opens_early_without_bypass_unlocks(self):
        campaigns = block(parsed(f"common/decisions/{BASE}_decisions.txt"), "NAM_public_campaigns")
        early = {
            "NAM_campaign_every_seal_counts": "NAM_inventory",
            "NAM_campaign_wages_on_time": "NAM_centre_hourglass",
            "NAM_campaign_ladder_holds": "NAM_imperial_gendarmes",
            "NAM_campaign_charter_of_districts": "NAM_oilfield_militia",
            "NAM_campaign_oil_is_ours": "NAM_sand_runs_out",
            "NAM_campaign_answer_leaflets": "NAM_colonial_watch",
        }
        for name, focus_id in early.items():
            facts = self.colonial_facts()
            for key in tuple(facts):
                if key[1] == "has_completed_focus":
                    facts[key] = False
            facts[("NAM", "has_completed_focus", focus_id)] = True
            decision = block(campaigns, name)
            self.assertTrue(self.matches(block(decision, "visible"), facts), name)
            facts[("NAM", "variable", "ADISCORD_available_campaign_slots")] = 0
            # The shared slot predicate is supplied explicitly by the test expander.
            available = block(decision, "available")
            shared = {e.key: e.value for e in parsed("common/scripted_triggers/ADISCORD_shared_action_triggers.txt")}
            with patch.dict(self.triggers, shared):
                self.assertFalse(self.matches(available, facts), name)
                facts[("NAM", "variable", "ADISCORD_available_campaign_slots")] = 1
                self.assertTrue(self.matches(available, facts), name)
            facts[("NAM", "has_country_flag", "NAM_center_vanished")] = True
            self.assertFalse(self.matches(block(decision, "visible"), facts), name)
        inventory = block(self.focuses["NAM_inventory"], "completion_reward")
        self.assertEqual(sum(e.key == "ADISCORD_campaign_slot_grant" for e in walk(inventory)), 1)
        guard = block(block(parsed(f"common/decisions/{BASE}_decisions.txt"), "NAM_underground"), "NAM_colonial_pipeline_guard")
        facts = self.colonial_facts()
        self.assertFalse(self.matches(block(guard, "visible"), facts))
        facts[("NAM", "has_country_flag", "NAM_pipeline_guard_authorised")] = True
        facts[("NAM", "has_country_flag", "NAM_center_vanished")] = True
        self.assertTrue(self.matches(block(guard, "visible"), facts))

    def test_counterpropaganda_returns_its_slot_once_on_every_exit(self):
        campaigns = block(parsed(f"common/decisions/{BASE}_decisions.txt"), "NAM_public_campaigns")
        campaign = block(campaigns, "NAM_campaign_answer_leaflets")
        shared = {e.key: e.value for e in parsed("common/scripted_triggers/ADISCORD_shared_action_triggers.txt")}
        with patch.dict(self.triggers, shared):
            for exit_name in ("remove_effect", "cancel_effect"):
                facts = self.colonial_facts()
                slot = ("NAM", "variable", "ADISCORD_available_campaign_slots")
                facts[slot] = 1
                self.apply(block(campaign, "complete_effect"), facts)
                self.assertEqual(facts[slot], 0)
                # Independence does not cancel a paid mainland campaign.
                facts[("NAM", "has_country_flag", "NAM_center_vanished")] = True
                self.assertFalse(self.matches(block(campaign, "cancel_trigger"), facts))
                facts[("NAM", "has_country_flag", "NAM_weber_amnesty")] = True
                self.assertTrue(self.matches(block(campaign, "cancel_trigger"), facts))
                self.apply(block(campaign, exit_name), facts)
                self.assertEqual(facts[slot], 1)
                self.apply(block(campaign, "remove_effect"), facts)
                self.apply(block(campaign, "cancel_effect"), facts)
                self.assertEqual(facts[slot], 1)

    def test_security_programmes_change_the_reported_growth_only_while_active(self):
        monthly = block(self.effects["NAM_underground_monthly"], "if")
        names = ("NAM_disrupt_print_supply", "NAM_colonial_pipeline_guard", "NAM_campaign_answer_leaflets")
        rules = [e for e in monthly if e.key == "if" and any(n in repr(e) for n in names)]
        self.assertEqual(len(rules), 3)
        for flags in product((False, True), repeat=3):
            facts = {("NAM", "has_decision", name): active for name, active in zip(names, flags)}
            selected = [e for _, e in selected_effects(rules, facts, "NAM")]
            delta = sum(int(scalar(e.value, "value")) for e in selected if e.key == "add_to_temp_variable")
            self.assertEqual(delta, sum(change for change, active in zip((-3, -2, -2), flags) if active))
        snapshot = next(e for e in monthly if e.key == "set_variable")
        self.assertTrue(all(monthly.index(e) < monthly.index(snapshot) for e in rules))

    def test_colonial_route_timing_includes_the_paid_response(self):
        routes = (
            ("NAM_inventory", "NAM_metropolitan_quota", "NAM_deliver_the_quota", "NAM_wrk_trade_house", "NAM_wrk_return_cargo", "NAM_metropolitan_depots", "NAM_letters_to_the_centre"),
            ("NAM_inventory", "NAM_colonial_watch", "NAM_oilfield_militia", "NAM_pipeline_patrols", "NAM_print_shop_raid", "NAM_colony_order", "NAM_letters_to_the_centre"),
            ("NAM_inventory", "NAM_centre_hourglass", "NAM_second_ledger", "NAM_quiet_officer_lists", "NAM_sand_runs_out", "NAM_last_centre_register"),
        )
        projects = self.colonial_projects()
        for route in routes:
            complete = set()
            day = 0
            for focus_id in route:
                focus = self.focuses[focus_id]
                for group in (e.value for e in focus if e.key == "prerequisite"):
                    self.assertTrue(any(e.value in complete for e in group), focus_id)
                day += int(scalar(focus, "cost")) * 7
                complete.add(focus_id)
                for name, project in projects.items():
                    if scalar(block(project, "visible"), "has_completed_focus") == focus_id:
                        self.assertLess(day + int(scalar(project, "days_remove")), 350, name)
        letters = self.focuses["NAM_letters_to_the_centre"]
        self.assertEqual(len([e for e in letters if e.key == "prerequisite"]), 1)

    def test_rom_changes_ideology_only_once_when_confederation_is_dismantled(self):
        characters = block(parsed("common/characters/NAM.txt"), "characters")
        initial = block(block(characters, "NAM_Egor_Rom"), "country_leader")
        self.assertEqual(scalar(initial, "ideology"), "etatism_ideology")
        teardown = block(parsed("common/scripted_effects/ADISCORD_vorkerland_effects.txt"),
                         "ADISCORD_vorkerland_teardown_confederation")
        self.assertEqual(scalar(block(teardown, "NAM"), "NAM_adopt_service_etatism"), "yes")
        transition = self.effects["NAM_adopt_service_etatism"]
        for leader, ideology, expected in (
            ("NAM_Egor_Rom", "etatism_ideology", True),
            ("NAM_Egor_Rom", "service_etatism", False),
            ("another_leader", "etatism_ideology", False),
            ("NAM_Egor_Rom", "humanism_ideology", False),
        ):
            with self.subTest(leader=leader, ideology=ideology):
                facts = {
                    ("NAM", "ruling_leader"): leader,
                    ("NAM", "has_country_leader_ideology", ideology): True,
                }
                selected = [entry for _, entry in selected_effects(transition, facts, "NAM")]
                roles = [entry.value for entry in selected if entry.key == "add_country_leader_role"]
                self.assertEqual(bool(roles), expected)
                if expected:
                    self.assertEqual(len(roles), 1)
                    self.assertEqual(scalar(roles[0], "character"), "NAM_Egor_Rom")
                    self.assertEqual(scalar(roles[0], "promote_leader"), "yes")
                    self.assertEqual(scalar(block(roles[0], "country_leader"), "ideology"), "service_etatism")
                    old_role = block(block(selected, "NAM_Egor_Rom"), "remove_country_leader_role")
                    self.assertEqual(scalar(old_role, "ideology"), "etatism_ideology")
                else:
                    self.assertEqual(selected, [])

    def test_print_shop_focus_opens_two_paid_underground_operations(self):
        reward = block(self.focuses["NAM_print_shop_raid"], "completion_reward")
        self.assertEqual(scalar(reward, "add_political_power"), "35")
        unlocks = [e.value for e in reward if e.key == "unlock_decision_tooltip"]
        self.assertEqual(unlocks, ["NAM_disrupt_print_supply", "NAM_intercept_underground_couriers"])
        self.assertNotIn("NAM_underground", repr(reward))
        decisions = block(parsed(f"common/decisions/{BASE}_decisions.txt"), "NAM_underground")
        for name, cost in zip(unlocks, (25, 40)):
            decision = block(decisions, name)
            self.assertEqual(scalar(decision, "cost"), str(cost))
            self.assertEqual(scalar(block(decision, "visible"), "has_completed_focus"), "NAM_print_shop_raid")
            self.assertFalse(any(e.key == "add_political_power" for e in walk(decision)))
        russian = (ROOT / f"localisation/russian/{BASE}_l_russian.yml").read_bytes()
        self.assertTrue(russian.startswith(b"\xef\xbb\xbf"))
        self.assertIn(' NAM_print_shop_raid:0 "Найти чернила будущего восстания"', russian.decode("utf-8-sig"))

    def test_print_operations_close_when_the_network_or_campaign_phase_ends(self):
        decisions = block(parsed(f"common/decisions/{BASE}_decisions.txt"), "NAM_underground")
        control = block(decisions, "NAM_disrupt_print_supply")
        self.assertEqual(scalar(control, "days_remove"), "60")
        for amnesty, started, resolved, owns_capital, operable in product((False, True), repeat=5):
            facts = self.facts()
            facts[("NAM", "has_country_flag", "NAM_weber_amnesty")] = amnesty
            facts[("NAM", "has_global_flag", BASE + "_started")] = started
            facts[("NAM", "has_global_flag", BASE + "_resolved")] = resolved
            facts[("NAM", "owns_state", "688")] = owns_capital
            facts[("NAM", "has_capitulated", "no")] = operable
            facts[("NAM", "has_variable", "NAM_underground")] = True
            facts[("NAM", "variable", "NAM_underground")] = 12
            expected = not amnesty and not started and not resolved and owns_capital and operable
            for name in ("NAM_disrupt_print_supply", "NAM_intercept_underground_couriers"):
                self.assertEqual(self.matches(block(block(decisions, name), "available"), facts), expected)
            self.assertEqual(self.matches(block(control, "cancel_trigger"), facts), not expected)
        facts = self.facts()
        facts[("NAM", "has_global_flag", BASE + "_started")] = False
        facts[("NAM", "has_variable", "NAM_underground")] = True
        facts[("NAM", "variable", "NAM_underground")] = 0
        for name in ("NAM_disrupt_print_supply", "NAM_intercept_underground_couriers"):
            self.assertFalse(self.matches(block(block(decisions, name), "available"), facts))

    def test_print_control_uses_active_decision_and_courier_raids_have_a_tradeoff(self):
        monthly = block(self.effects["NAM_underground_monthly"], "if")
        control = next(e for e in monthly if e.key == "if" and "NAM_disrupt_print_supply" in repr(e))
        for active in (False, True):
            facts = {("NAM", "has_decision", "NAM_disrupt_print_supply"): active}
            selected = [e for _, e in selected_effects([control], facts, "NAM")]
            delta = sum(int(scalar(e.value, "value")) for e in selected if e.key == "add_to_temp_variable")
            self.assertEqual(delta, -3 if active else 0)
        snapshot = next(e for e in monthly if e.key == "set_variable")
        self.assertLess(monthly.index(control), monthly.index(snapshot))
        self.assertEqual(scalar(snapshot.value, "var"), "NAM_underground_growth")
        decisions = block(parsed(f"common/decisions/{BASE}_decisions.txt"), "NAM_underground")
        raid = block(decisions, "NAM_intercept_underground_couriers")
        self.assertEqual(scalar(raid, "days_re_enable"), "60")
        payload = block(block(raid, "complete_effect"), "hidden_effect")
        self.assertEqual(scalar(block(payload, "set_temp_variable"), "value"), "-12")
        self.assertEqual(scalar(payload, "NAM_underground_add"), "yes")
        self.assertEqual(scalar(block(payload, "add_to_variable"), "var"), "NAM_grp_dist_support")
        self.assertEqual(scalar(block(payload, "add_to_variable"), "value"), "-4")
        self.assertEqual(scalar(payload, "NAM_groups_refresh"), "yes")

    def test_manual_nam_icons_do_not_require_archived_originals(self):
        import tempfile
        from tools.builders import build_adiscord_nam_focus_icons as icons

        records = json.loads(read("tools/assets/source/focus_icons/NAM/focus_art_prompts.json"))
        focus_ids = tuple(
            entry["focus_id"] for entry in records["focus_compositions"]
            if entry.get("export_runtime", True) is False
        )
        self.assertTrue(focus_ids)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = root / icons.MANIFEST
            manifest.parent.mkdir(parents=True)
            manifest.write_text(json.dumps({"focus_compositions": [{
                "focus_id": focus_id,
                "export_runtime": False,
                "file": "missing_original.png",
            } for focus_id in focus_ids]}), encoding="utf-8")
            for focus_id in focus_ids:
                runtime = root / icons.OUTPUT / f"GFX_focus_{focus_id}.png"
                runtime.parent.mkdir(parents=True, exist_ok=True)
                runtime.write_bytes(b"manual runtime image")
            with patch.object(icons, "ROOT", root):
                self.assertEqual(icons.expected_outputs(), {})
                self.assertEqual(icons.expected_outputs(), {})
            for focus_id in focus_ids:
                runtime = root / icons.OUTPUT / f"GFX_focus_{focus_id}.png"
                self.assertEqual(runtime.read_bytes(), b"manual runtime image")
        manifest = json.loads(read("tools/assets/source/focus_icons/NAM/focus_art_prompts.json"))
        registry = json.loads(read("tools/data/generated_output_owners.json"))
        family = next(e for e in registry["families"] if e["id"] == "nam_focus_icons")
        for focus_id in focus_ids:
            entry = next(e for e in manifest["focus_compositions"] if e["focus_id"] == focus_id)
            self.assertIs(entry["export_runtime"], False)
            self.assertNotIn(f"gfx/interface/goals/NAM/GFX_focus_{focus_id}.png", family["output_globs"])

    def test_settlement_fragment_accepts_multiline_script(self):
        fragment = "688 = { remove_core_of = SLF add_core_of = NAM }"
        source = (
            "688 = {\n"
            "\tremove_core_of = SLF\n"
            "\t# Restore the national core after the uprising.\n"
            "\tadd_core_of = NAM\n"
            "}"
        )
        self.assertTrue(has_script_fragment(source, fragment))
        self.assertFalse(has_script_fragment(source.replace("NAM", "EFL"), fragment))
        self.assertFalse(
            has_script_fragment("688 = { add_core_of = NAM remove_core_of = SLF }", fragment)
        )

    @classmethod
    def setUpClass(cls):
        cls.tree, cls.focuses = tree_focuses("main")
        cls.postwar_tree, cls.postwar = tree_focuses("postwar")
        cls.defeated_tree, cls.defeated = tree_focuses("defeated")
        cls.exile_trees = {kind: tree_focuses(kind) for kind in EXILE}
        cls.triggers = {e.key: e.value for e in parsed(f"common/scripted_triggers/{BASE}_triggers.txt")}
        cls.effects = {}
        for path in (f"common/scripted_effects/{BASE}_effects.txt", "common/scripted_effects/ADISCORD_shared_action_effects.txt"):
            cls.effects.update({e.key: e.value for e in parsed(path)})
        cls.decisions = {e.key: e.value for e in block(parsed(f"common/decisions/{BASE}_decisions.txt"), "NAM_national_programmes")}
        cls.events = {scalar(e.value, "id"): e.value for e in parsed(f"events/{BASE}_events.txt") if e.key == "country_event"}
        cls.ideas = {e.key: e.value for e in block(block(parsed(f"common/ideas/{BASE}_ideas.txt"), "ideas"), "country")}

    def expand(self, entries):
        """Expand boolean triggers and bind explicit native building-slot fixtures."""
        result = []
        for entry in entries:
            if entry.key in self.triggers:
                self.assertIn(entry.value, ("yes", "no"), entry.key)
                result.append(replace(entry, key="AND" if entry.value == "yes" else "NOT", value=self.expand(self.triggers[entry.key])))
            elif entry.key == "has_country_flag" and isinstance(entry.value, list) and any(e.value == "<" for e in entry.value):
                comparison = [e.value for e in entry.value if not e.key]
                self.assertEqual(comparison[:2], ["days", "<"])
                flag = scalar(entry.value, "flag")
                age = int(comparison[2])
                # Native flag age is an integer: present and not older than
                # N-1 is precisely younger than N, including the absent case.
                older = [replace(e, value=">" if e.value == "<" else str(age - 1) if e.value == comparison[2] else e.value)
                         for e in entry.value]
                result.append(replace(entry, key="AND", value=[replace(entry, value=flag),
                              replace(entry, key="NOT", value=[replace(entry, value=older)])]))
            elif entry.key == "check_variable" and all(not e.key for e in entry.value):
                variable, operator, value = (e.value for e in entry.value)
                comparison = {">": "greater_than", "<": "less_than", "=": "equals"}[operator]
                result.append(replace(entry, value=[replace(entry, key=k, value=v) for k, v in
                                                    (("var", variable), ("value", value), ("compare", comparison))]))
            elif entry.key == "free_building_slots":
                self.assertEqual({e.key for e in entry.value}, {"building", "size", "include_locked"})
                key = ":".join(scalar(entry.value, name) for name in ("building", "size", "include_locked"))
                result.append(replace(entry, key="fixture_free_building_slots", value=key))
            elif entry.key == "has_power_balance":
                self.assertEqual({e.key for e in entry.value}, {"id"})
                result.append(replace(entry, key="fixture_power_balance", value=scalar(entry.value, "id")))
            elif entry.key == "any_neighbor_state":
                self.assertEqual(scalar(block(entry.value, "NOT"), "is_owned_by"), "NAM")
                result.append(replace(entry, key="fixture_foreign_land_border", value="yes"))
            elif isinstance(entry.value, list):
                result.append(replace(entry, value=self.expand(entry.value)))
            else:
                result.append(entry)
        return result

    def matches(self, entries, facts):
        return matches_conditions(self.expand(entries), facts, "NAM")

    def apply(self, entries, facts, current_scope="NAM"):
        """Execute selected accounting statements, leaving engine timing unmodelled."""
        def amount(value, scope):
            try:
                return float(value)
            except ValueError:
                if "." in value:
                    holder, variable = value.split(".", 1)
                    if holder == "PREV":
                        holder = facts[("fixture", "previous_state")]
                    return facts[(holder, "variable", variable)]
                return facts[(scope, "variable", value)]

        for scope, entry in selected_effects(self.expand(entries), facts, current_scope):
            if entry.key in self.effects:
                self.apply(self.effects[entry.key], facts, scope)
            elif entry.key == "add_political_power":
                key = (scope, "numeric", "has_political_power")
                facts[key] = facts.get(key, 0) + amount(entry.value, scope)
            elif entry.key == "add_fuel":
                key = (scope, "numeric", "has_fuel")
                facts[key] = facts.get(key, 0) + float(entry.value)
            elif entry.key in ("army_experience", "add_command_power"):
                key = (scope, "numeric", "command_power" if entry.key == "add_command_power" else "army_experience")
                facts[key] = facts.get(key, 0) + float(entry.value)
            elif entry.key in ("multiply_temp_variable", "multiply_variable"):
                key = (scope, "variable", scalar(entry.value, "var"))
                facts[key] *= amount(scalar(entry.value, "value"), scope)
            elif entry.key in ("set_variable", "set_temp_variable", "add_to_variable", "subtract_from_variable", "add_to_temp_variable"):
                key = (scope, "variable", scalar(entry.value, "var"))
                value = amount(scalar(entry.value, "value"), scope)
                if entry.key in ("set_variable", "set_temp_variable"):
                    facts[key] = value
                else:
                    facts[key] = facts.get(key, 0) + value * (-1 if entry.key == "subtract_from_variable" else 1)
                facts[(scope, "has_variable", key[2])] = True
            elif entry.key == "clear_variable":
                facts.pop((scope, "variable", entry.value), None)
                facts[(scope, "has_variable", entry.value)] = False
            elif entry.key == "clamp_variable":
                key = (scope, "variable", scalar(entry.value, "var"))
                facts[key] = max(float(scalar(entry.value, "min")), min(float(scalar(entry.value, "max")), facts[key]))
            elif entry.key == "add_manpower":
                key = (scope, "numeric", "has_manpower")
                facts[key] = facts.get(key, 0) + float(entry.value)
            elif entry.key == "add_power_balance_value":
                key = (scope, "power_balance_value", scalar(entry.value, "id"))
                facts[key] = max(-1, min(1, facts.get(key, 0) + float(scalar(entry.value, "value"))))
            elif entry.key == "add_building_construction":
                key = (scope, "building", scalar(entry.value, "type"))
                facts[key] = facts.get(key, 0) + int(scalar(entry.value, "level"))
            elif entry.key == "add_extra_state_shared_building_slots":
                key = (scope, "reward", "building_slots")
                facts[key] = facts.get(key, 0) + int(entry.value)
            elif entry.key in ("set_country_flag", "clr_country_flag"):
                facts[(scope, "has_country_flag", entry.value)] = entry.key == "set_country_flag"
            elif entry.key in ("set_state_flag", "clr_state_flag"):
                facts[(scope, "has_state_flag", entry.value)] = entry.key == "set_state_flag"
            elif entry.key == "add_tech_bonus":
                facts[(scope, "tech_bonus", scalar(entry.value, "name"))] = (
                    float(scalar(entry.value, "bonus")), int(scalar(entry.value, "uses")), scalar(entry.value, "category"))
            elif entry.key == "set_technology":
                for technology in entry.value:
                    if technology.key != "popup":
                        facts[(scope, "has_tech", technology.key)] = technology.value == "1"
            elif entry.key in ("add_dynamic_modifier", "remove_dynamic_modifier"):
                name = scalar(entry.value, "modifier")
                facts[(scope, "has_dynamic_modifier", name)] = entry.key == "add_dynamic_modifier"
            elif entry.key == "add_equipment_to_stockpile":
                key = (scope, "equipment", scalar(entry.value, "type"))
                facts[key] = facts.get(key, 0) + float(scalar(entry.value, "amount"))
            elif entry.key == "add_timed_idea":
                facts[(scope, "has_idea", scalar(entry.value, "idea"))] = True
            elif entry.key == "add_stability":
                facts[(scope, "reward", "stability")] = facts.get((scope, "reward", "stability"), 0) + float(entry.value)

    def facts(self, pp=1000, treasury=10000, fuel=20000):
        result = {
            ("NAM", "exists", "yes"): True,
            ("NAM", "has_capitulated", "no"): True,
            ("NAM", "has_war", "yes"): True,
            ("NAM", "has_war", "no"): True,
            ("NAM", "has_war_with", "SLF"): True,
            ("NAM", "numeric", "has_political_power"): pp,
            ("NAM", "numeric", "has_fuel"): fuel,
            ("NAM", "variable", "ADISCORD_economy_treasury"): treasury,
            ("NAM", "has_global_flag", BASE + "_started"): True,
        }
        for state in (67, 688, 700):
            for condition in ("owns_state", "controls_state"):
                result[("NAM", condition, str(state))] = True
        for focus in self.focuses:
            result[("NAM", "has_completed_focus", focus)] = True
        result[("NAM", "has_completed_focus", "NAM_recognition")] = False
        return result

    def test_tree_selection_and_generated_owner(self):
        self.assertEqual(scalar(self.tree, "id"), "NAM_focus")
        country = block(self.tree, "country")
        self.assertEqual(scalar(block(country, "modifier"), "tag"), "NAM")
        selection = {"postwar": self.postwar_tree, "defeated": self.defeated_tree}
        for kind, tree in selection.items():
            self.assertEqual(scalar(tree, "id"), TREES[kind][1])
            modifier = block(block(tree, "country"), "modifier")
            self.assertEqual(scalar(modifier, "original_tag"), "NAM")
            conditions = [entry for entry in modifier if entry.key != "add"]
            for outcome in (None, "nam_victory", "compromise", "island_exile", "standoff"):
                facts = {("NAM", "original_tag", "NAM"): True}
                if outcome is not None:
                    facts[("NAM", "has_global_flag", BASE + "_" + outcome)] = True
                expected = outcome in (("nam_victory",) if kind == "postwar" else ("compromise",))
                self.assertEqual(self.matches(conditions, facts), expected, (kind, outcome))
        # Event .100 and the corporate takeover load the exile trees; each one
        # also selects only its own course.
        courses = {
            "exile_radical": {"NAM_exile_radical"},
            "exile_humanist": {"NAM_exile_humanist"},
            "exile_corporate": {"NAM_exile_humanist", "NAM_corp_takeover"},
        }
        for kind, own_flags in courses.items():
            tree = self.exile_trees[kind][0]
            self.assertEqual(scalar(tree, "id"), TREES[kind][1])
            modifier = block(block(tree, "country"), "modifier")
            self.assertEqual(scalar(modifier, "original_tag"), "NAM")
            conditions = [entry for entry in modifier if entry.key != "add"]
            for flags in courses.values():
                facts = {
                    ("NAM", "original_tag", "NAM"): True,
                    ("NAM", "has_global_flag", BASE + "_island_exile"): True,
                }
                for flag in flags:
                    facts[("NAM", "has_country_flag", flag)] = True
                self.assertEqual(self.matches(conditions, facts), flags == own_flags, (kind, flags))
        owners = json.loads(read("tools/data/generated_output_owners.json"))
        for kind, (_, _, filename) in TREES.items():
            output = ROOT / "common/national_focus" / filename
            self.assertEqual(output.read_bytes(), expected_outputs()[output], kind)
            self.assertIn(f"common/national_focus/{filename}", str(owners))

    def test_unique_layout_and_real_rewards(self):
        expected = {
            "main": (self.focuses, 117), "postwar": (self.postwar, 54), "defeated": (self.defeated, 24),
            "exile_radical": (self.exile_trees["exile_radical"][1], 74),
            "exile_humanist": (self.exile_trees["exile_humanist"][1], 73),
            "exile_corporate": (self.exile_trees["exile_corporate"][1], 34),
        }
        names = [name for focuses, _ in expected.values() for name in focuses]
        self.assertEqual(len(names), len(set(names)))
        for kind, (focuses, count) in expected.items():
            coordinates = set()
            self.assertEqual(len(focuses), count, kind)
            filters = set()
            for name, focus in focuses.items():
                coordinate = (scalar(focus, "x"), scalar(focus, "y"))
                self.assertNotIn(coordinate, coordinates, name)
                coordinates.add(coordinate)
                self.assertTrue(block(focus, "completion_reward"), name)
                self.assertIn(int(scalar(focus, "cost")), range(1, 13))
                filters.add(tuple(e.value for e in block(focus, "search_filters")))
                self.assertEqual(scalar(block(focus, "available"), "has_capitulated"), "no")
                for group in (e.value for e in focus if e.key == "prerequisite"):
                    for child in group:
                        self.assertIn(child.value, focuses, (name, "prerequisite leaves its tree"))
            self.assertGreaterEqual(len(filters), 4, kind)

    def test_every_policy_combination_reaches_the_branch_finals(self):
        pairs = (("vertical", "districts"), ("export_quays", "domestic_refining"),
                 ("field_guards", "mobile_columns"), ("supports_oil_compact", "supports_export_houses"),
                 ("court_azhar", "fuel_leverage"), ("island_levy_office", "island_concession"))
        # Course-gated alternatives follow the ladder course chosen in the first pair.
        course = {
            "vertical": {"NAM_district_assemblies", "NAM_weber_channel", "NAM_district_volunteers"},
            "districts": {"NAM_namestnik_circuits", "NAM_cache_hunters", "NAM_martial_seals"},
        }
        finals = ("NAM_seal_courts", "NAM_quiet_wells", "NAM_civilian_combine", "NAM_quartermaster",
                  "NAM_pillar_arbitration", "NAM_general_staff_plan", "NAM_island_governors", "NAM_rom_address")
        for choices in product(*pairs):
            blocked = {"NAM_" + other for pair, chosen in zip(pairs, choices) for other in pair if other != chosen}
            completed = reachable(self.focuses, blocked | course[choices[0]])
            for final in finals:
                self.assertIn(final, completed, choices)
            for pair, chosen in zip(pairs, choices):
                group = block(self.focuses["NAM_" + chosen], "mutually_exclusive")
                self.assertEqual({e.value for e in group}, {"NAM_" + n for n in pair if n != chosen})
        for state, federal in (("service_state", "federal_charter"), ("federal_charter", "service_state")):
            for peace in (("civil_dividend", "armed_peace"), ("armed_peace", "civil_dividend")):
                completed = reachable(self.postwar, {"NAM_" + federal, "NAM_" + peace[1]})
                self.assertIn("NAM_svetlogorye", completed)
                ending = "NAM_ladder_of_seals" if state == "service_state" else "NAM_common_fuel_market"
                self.assertIn(ending, completed, state)
        for chosen, other in (("revenge", "accommodation"), ("accommodation", "revenge")):
            completed = reachable(self.defeated, {"NAM_defeat_" + other})
            self.assertIn("NAM_defeat_second_chapter", completed, chosen)
        finals = {
            "exile_radical": "NAM_rad_dominion_of_pillars",
            "exile_humanist": "NAM_hum_union_constitution",
            "exile_corporate": "NAM_board_union_of_boards",
        }
        for kind, final in finals.items():
            focuses = self.exile_trees[kind][1]
            pairs = sorted({
                tuple(sorted((name, entry.value)))
                for name, focus in focuses.items()
                for group in (e.value for e in focus if e.key == "mutually_exclusive")
                for entry in group
            })
            self.assertGreaterEqual(len(pairs), 4, kind)
            for side in (0, 1):
                blocked = {pair[1 - side] for pair in pairs}
                self.assertIn(final, reachable(focuses, blocked), (kind, side))

    def test_each_exile_tree_owns_its_wars_and_script_gates(self):
        from tools.builders.build_adiscord_focus_trees import SHARED_HISTORY_SOURCES

        for kind in EXILE:
            focuses = self.exile_trees[kind][1]
            self.assertNotIn("allow_branch", read(TREES[kind][0]), kind)
            for effect in ("NAM_war_of_return_start", "NAM_great_war_start"):
                callers = [
                    name for name, focus in focuses.items()
                    if effect in [e.key for e in walk(block(focus, "completion_reward"))]
                ]
                self.assertEqual(len(callers), 1, (kind, effect))
        # The return operation requires the final focus of every exile branch.
        capstones = {
            "NAM_rad_war_of_return": ("exile_radical", {
                "NAM_rad_return_plan", "NAM_rad_fortress_capital", "NAM_rad_island_fuel_dumps",
                "NAM_exile_army_of_return", "NAM_exile_corsair_admiralty"}),
            "NAM_hum_war_of_return": ("exile_humanist", {
                "NAM_hum_return_manifesto", "NAM_exile_overseas_districts", "NAM_hum_free_city_charter",
                "NAM_hum_army_of_citizens", "NAM_hum_charter_commission"}),
            "NAM_board_war_of_return": ("exile_corporate", {
                "NAM_board_landing_contracts", "NAM_board_private_navy", "NAM_board_mercenary_battalions"}),
        }
        for name, (kind, expected) in capstones.items():
            groups = [[e.value for e in g] for g in (e.value for e in self.exile_trees[kind][1][name]
                                                      if e.key == "prerequisite")]
            self.assertTrue(all(len(group) == 1 for group in groups), name)
            self.assertEqual({group[0] for group in groups}, expected, name)
        self.assertNotIn("allow_branch", read(TREES["defeated"][0]))
        # Decisions, categories and the piracy window read these completions.
        gates = {
            "exile_radical": ("NAM_exile_general_staff", "NAM_exile_sea_raiders", "NAM_exile_black_market",
                              "NAM_exile_fences", "NAM_exile_marine_orders", "NAM_rad_labour_camps",
                              "NAM_rad_spoils_of_return", "NAM_rad_garrison_belt", "NAM_rad_martial_law"),
            "exile_humanist": ("NAM_hum_citizen_army", "NAM_hum_free_zones", "NAM_hum_steel_exchange",
                               "NAM_hum_labour_bureau", "NAM_hum_innovation_parks", "NAM_hum_credit_arms",
                               "NAM_hum_regulated_partnership", "NAM_hum_charter_commission",
                               "NAM_hum_open_doors", "NAM_hum_marine_contracts", "NAM_hum_union_council",
                               "NAM_hum_federal_treaties", "NAM_hum_harbour_rebuilding"),
            "exile_corporate": ("NAM_hum_company_guard", "NAM_board_landing_contracts", "NAM_board_constitution",
                                "NAM_board_shareholders", "NAM_board_district_auction"),
        }
        for kind, names in gates.items():
            for name in names:
                self.assertIn(name, self.exile_trees[kind][1], (kind, name))
        # The takeover replaces the humanist tree; its completions must survive.
        self.assertIn(TREES["exile_humanist"][0].removeprefix("focus_trees/"), SHARED_HISTORY_SOURCES)

    def test_normal_preparation_fits_external_clock(self):
        path = ("inventory", "open_ledgers", "districts", "public_payroll", "district_guarantees")
        days = sum(int(scalar(self.focuses["NAM_" + key], "cost")) * 7 for key in path)
        self.assertEqual(days, 84)
        self.assertLess(days + 60, 300)
        self.assertNotIn("prerequisite", [e.key for e in self.focuses["NAM_alarm"]])
        self.assertNotIn("prerequisite", [e.key for e in self.postwar["NAM_recognition"]])
        self.assertNotIn("prerequisite", [e.key for e in self.defeated["NAM_defeat_count_losses"]])
        self.assertEqual(int(scalar(self.focuses["NAM_alarm"], "cost")), 1)
        for name, focus in self.focuses.items():
            if "NAM_restitution_clock_tt" in repr(block(focus, "available")):
                self.assertIn("ADISCORD_nam_resource_war_started", repr(block(focus, "bypass")), name)

    def test_late_political_routes_still_have_a_usable_result(self):
        facts = self.facts()
        facts[("NAM", "has_global_flag", BASE + "_resolved")] = True
        reward = block(self.focuses["NAM_emergency_writ"], "completion_reward")
        self.assertIn("NAM_supply_order", [e.value for e in walk(reward) if e.key == "unlock_decision_tooltip"])
        self.assertTrue(self.matches(block(self.decisions["NAM_supply_order"], "visible"), facts))
        self.assertTrue(self.matches(block(self.decisions["NAM_supply_order"], "available"), facts))
        reward = block(self.focuses["NAM_district_guarantees"], "completion_reward")
        self.apply(reward, facts)
        self.assertEqual(facts[("NAM", "reward", "stability")], 0.03)

    def test_quartermaster_delivers_when_procurement_is_already_unlocked(self):
        for emergency_first in (False, True):
            facts = self.facts()
            facts[("NAM", "has_completed_focus", "NAM_emergency_writ")] = emergency_first
            self.apply(block(self.focuses["NAM_quartermaster"], "completion_reward"), facts)
            self.assertEqual(facts[("NAM", "equipment", "infantry_equipment")], 13500)
            self.assertEqual(facts[("NAM", "equipment", "support_equipment")], 60)

    def test_fractional_affordability_and_actual_debits(self):
        expected = {
            "NAM_export_fuel": (25, 0, 5000), "NAM_workshop_batch": (35, 0, 3000),
            "NAM_supply_order": (25, 500, 0), "NAM_emergency_arsenal": (35, 500, 0),
            "NAM_counterinsurgency": (75, 500, 0), "NAM_relief_batch": (35, 0, 3000),
            "NAM_veteran_housing": (35, 250, 0), "NAM_postwar_rearmament": (35, 500, 0),
            "NAM_sign_compact": (50, 350, 0),
        }
        for name, (pp, treasury, fuel) in expected.items():
            decision = self.decisions[name]
            self.assertEqual(scalar(decision, "cost"), "0")
            for currency, amount, field in (
                ("pp", pp, ("NAM", "numeric", "has_political_power")),
                ("treasury", treasury, ("NAM", "variable", "ADISCORD_economy_treasury")),
                ("fuel", fuel, ("NAM", "numeric", "has_fuel")),
            ):
                if not amount:
                    continue
                facts = self.facts(pp=pp, treasury=treasury, fuel=fuel)
                if name == "NAM_sign_compact":
                    facts[("NAM", "has_global_flag", BASE + "_started")] = False
                self.assertTrue(self.matches(block(decision, "custom_cost_trigger"), facts), name)
                facts[field] = amount - 0.01
                self.assertFalse(self.matches(block(decision, "custom_cost_trigger"), facts), (name, currency))
                before = dict(facts)
                self.apply(block(decision, "complete_effect"), facts)
                self.assertEqual(facts, before, (name, currency, "stale click must not pay"))
            facts = self.facts(pp=pp, treasury=treasury, fuel=fuel)
            if name == "NAM_sign_compact":
                facts[("NAM", "has_global_flag", BASE + "_started")] = False
            self.apply(block(decision, "complete_effect"), facts)
            self.assertEqual(facts[("NAM", "numeric", "has_political_power")], 0, name)
            self.assertEqual(facts[("NAM", "numeric", "has_fuel")], 0, name)
            expected_treasury = 400 if name == "NAM_export_fuel" else 0
            self.assertEqual(facts[("NAM", "variable", "ADISCORD_economy_treasury")], expected_treasury, name)
            self.assertEqual(facts.get(("NAM", "variable", "ADISCORD_economy_current_month_action_costs"), 0), treasury, name)
            rifles = {
                "NAM_supply_order": 13500, "NAM_emergency_arsenal": 18000,
                "NAM_counterinsurgency": 9000, "NAM_relief_batch": 7200,
                "NAM_postwar_rearmament": 18000,
            }
            if name in rifles:
                self.assertEqual(facts[("NAM", "equipment", "infantry_equipment")], rifles[name], name)

    def test_compact_age_loss_repayment_and_delayed_rebellion(self):
        facts = self.facts(pp=150, treasury=1000)
        facts[("NAM", "has_global_flag", BASE + "_started")] = False
        effect = block(self.decisions["NAM_sign_compact"], "complete_effect")
        self.apply(effect, facts)
        balance = facts[("NAM", "variable", "ADISCORD_economy_treasury")]
        self.apply(effect, facts)
        self.assertEqual(facts[("NAM", "variable", "ADISCORD_economy_treasury")], balance)
        facts[("NAM", "flag_days", "NAM_district_compact")] = 59
        self.assertFalse(self.matches(self.triggers["NAM_compact_effective"], facts))
        facts[("NAM", "flag_days", "NAM_district_compact")] = 60
        self.assertTrue(self.matches(self.triggers["NAM_compact_effective"], facts))
        facts[("NAM", "has_country_flag", "NAM_compact_ratified")] = True
        facts[("NAM", "controls_state", "688")] = False
        self.apply(self.effects["NAM_invalidate_lost_compact"], facts)
        self.assertTrue(facts[("NAM", "has_country_flag", "NAM_compact_ratified")])
        self.assertFalse(facts[("NAM", "has_country_flag", "NAM_district_compact")])
        facts[("NAM", "controls_state", "688")] = True
        self.assertTrue(self.matches(self.triggers["NAM_can_sign_compact"], facts))
        rebellion = block(self.effects[BASE + "_start_mainland_rebellion"], "if")
        self.assertNotIn("NAM_compact_effective", [e.key for e in walk(rebellion)])
        self.assertIn("NAM_compact_ratified", [e.value for e in walk(rebellion) if e.key == "has_country_flag"])

    def test_compact_report_does_not_promote_a_late_signature_during_war(self):
        definitions = parsed("common/scripted_localisation/ADISCORD_nam_resource_war_scripted_loc.txt")
        status = next(e.value for e in definitions if scalar(e.value, "name") == "NAMGetCompactStatus")

        def report(facts):
            for entry in status:
                if entry.key != "text":
                    continue
                triggers = [e.value for e in entry.value if e.key == "trigger"]
                if not triggers or self.matches(triggers[0], facts):
                    return scalar(entry.value, "localization_key")
            self.fail("Missing compact status fallback")

        facts = self.facts()
        facts[("NAM", "has_country_flag", "NAM_district_compact")] = True
        facts[("NAM", "flag_days", "NAM_district_compact")] = 90
        self.assertEqual(report(facts), "NAM_compact_wartime_unavailable")
        facts[("NAM", "has_country_flag", "NAM_compact_ratified")] = True
        self.assertEqual(report(facts), "NAM_compact_ratified_status")
        facts[("NAM", "controls_state", "688")] = False
        self.apply(self.effects["NAM_invalidate_lost_compact"], facts)
        self.assertEqual(report(facts), "NAM_compact_interrupted_status")
        facts[("NAM", "has_global_flag", BASE + "_resolved")] = True
        self.assertEqual(report(facts), "NAM_compact_war_closed")

    def test_completed_inventory_chains_memory_to_payroll(self):
        focus = self.focuses["NAM_inventory"]
        self.assertNotIn("select_effect", [entry.key for entry in focus])
        memory = self.events[BASE + ".109"]
        self.assertEqual(scalar(memory, "fire_only_once"), "yes")
        self.assertGreater(float(scalar(memory, "timeout_days")), 0)
        options = [entry.value for entry in memory if entry.key == "option"]
        self.assertEqual(len(options), 1)
        continuation = block(options[0], "hidden_effect")
        self.assertEqual([entry.key for entry in continuation], ["country_event"])
        self.assertEqual(scalar(block(continuation, "country_event"), "id"), BASE + ".10")
        self.assertNotIn("immediate", [entry.key for entry in memory])
        reward = block(focus, "completion_reward")
        self.assertEqual(scalar(reward, "add_political_power"), "35")
        self.assertEqual(scalar(block(reward, "country_event"), "id"), BASE + ".109")
        self.assertEqual(scalar(block(reward, "country_event"), "hours"), "1")

    def test_intro_uses_the_actual_collapse_phase(self):
        descriptions = [e.value for e in self.events[BASE + ".10"] if e.key == "desc"]
        for collapsed in (False, True):
            facts = self.facts()
            facts[("NAM", "has_global_flag", "ADISCORD_vorkerland_collapse_wars_started")] = collapsed
            shown = [scalar(d, "text") for d in descriptions if self.matches(block(d, "trigger"), facts)]
            self.assertEqual(shown, [BASE + (".10.d" if collapsed else ".10.before")])

    def test_rom_story_uses_current_ruler_and_actual_peace_terms(self):
        event_ids = [f"{BASE}.{number}" for number in (11, 12, 13, 20, 21, 70, 80)]
        event_ids.append("ADISCORD_nam_groups.12")
        for event_id, leader, recognised in product(
            event_ids, ("NAM_Egor_Rom", "another_leader"), (False, True)
        ):
            with self.subTest(event=event_id, leader=leader, recognised=recognised):
                facts = self.facts()
                facts[("NAM", "ruling_leader")] = leader
                facts[("NAM", "has_country_flag", "NAM_treaty_independence_recognised")] = recognised
                descriptions = [entry.value for entry in self.events[event_id] if entry.key == "desc"]
                shown = [scalar(desc, "text") for desc in descriptions if self.matches(block(desc, "trigger"), facts)]
                suffix = ".d_standoff" if event_id == BASE + ".12" and not recognised else ".d"
                if leader != "NAM_Egor_Rom":
                    suffix += "_successor"
                self.assertEqual(shown, [event_id + suffix])
                if event_id == BASE + ".70":
                    titles = [entry.value for entry in self.events[event_id] if entry.key == "title"]
                    shown_titles = [scalar(title, "text") for title in titles if self.matches(block(title, "trigger"), facts)]
                    self.assertEqual(shown_titles, [event_id + (".t" if leader == "NAM_Egor_Rom" else ".t_successor")])

    def test_mission_never_succeeds_automatically_and_all_treaties_clean_up(self):
        mission = self.decisions["NAM_defend_fields"]
        self.assertFalse(self.matches(block(mission, "available"), self.facts()))
        self.assertEqual(scalar(mission, "days_mission_timeout"), "420")
        self.assertFalse(block(mission, "timeout_effect"))
        for outcome in ("resolve_nam_victory", "resolve_coalition_victory", "resolve_compromise", "resolve_standoff"):
            self.assertIn(BASE + "_clear_temporary_support", [e.key for e in walk(self.effects[BASE + "_" + outcome])])
        self.assertIn("NAM_close_war_programmes", [e.key for e in walk(self.effects[BASE + "_clear_temporary_support"])])
        cleanup = self.effects["NAM_close_war_programmes"]
        self.assertIn("NAM_defend_fields", [e.value for e in cleanup if e.key == "remove_mission"])
        self.assertEqual({e.value for e in cleanup if e.key == "remove_ideas"}, {"NAM_wartime_entrenchment", "NAM_counterstroke_staff", "NAM_rebel_depot_maps"})

    def test_border_archive_does_not_invent_recognition_after_standoff(self):
        event_id = "ADISCORD_nam_archive.6"
        descriptions = [entry.value for entry in self.events[event_id] if entry.key == "desc"]
        for recognised in (False, True):
            facts = self.facts()
            facts[("NAM", "has_country_flag", "NAM_treaty_independence_recognised")] = recognised
            shown = [scalar(desc, "text") for desc in descriptions if self.matches(block(desc, "trigger"), facts)]
            self.assertEqual(shown, [event_id + (".d" if recognised else ".d_standoff")])

    def test_memoir_pages_keep_full_exit_and_no_gameplay_settlement(self):
        for chapter in range(1, 6):
            first = self.events[f"ADISCORD_nam_memoir.{chapter}"]
            last = self.events[f"ADISCORD_nam_memoir.{chapter + 10}"]
            first_options = [entry.value for entry in first if entry.key == "option"]
            last_options = [entry.value for entry in last if entry.key == "option"]
            exit_options = [option for option in first_options if scalar(option, "name") == "ADISCORD_nam_memoir.put_away"]
            self.assertEqual(len(exit_options), 1)
            self.assertEqual([entry.key for entry in exit_options[0]], ["name"])
            self.assertEqual(len(last_options), 1)
            self.assertEqual([entry.key for entry in last_options[0]], ["name"])
            self.assertNotIn("immediate", [entry.key for entry in first + last])
            continuation = next(option for option in first_options if scalar(option, "name") == "ADISCORD_nam_memoir.read_on")
            effects = block(continuation, "hidden_effect")
            self.assertEqual([entry.key for entry in effects], ["country_event"])
            self.assertEqual(scalar(block(effects, "country_event"), "id"), f"ADISCORD_nam_memoir.{chapter + 10}")

    def test_open_payroll_event_cannot_spend_after_money_or_route_changes(self):
        options = {
            scalar(e.value, "name"): e.value
            for e in self.events[BASE + ".10"] if e.key == "option"
        }
        facts = self.facts(treasury=249.99)
        self.apply(options[BASE + ".10.a"], facts)
        self.assertEqual(facts[("NAM", "variable", "ADISCORD_economy_treasury")], 249.99)
        facts[("NAM", "variable", "ADISCORD_economy_treasury")] = 99.99
        self.apply(options[BASE + ".10.c"], facts)
        self.assertEqual(facts[("NAM", "variable", "ADISCORD_economy_treasury")], 99.99)
        facts[("NAM", "has_completed_focus", "NAM_recognition")] = True
        facts[("NAM", "variable", "ADISCORD_economy_treasury")] = 1000
        for suffix in ("a", "b", "c"):
            option = options[BASE + ".10." + suffix]
            self.assertFalse(self.matches(block(option, "trigger"), facts))
            self.apply(option, facts)
        self.assertEqual(facts[("NAM", "variable", "ADISCORD_economy_treasury")], 1000)
        self.assertNotIn(("NAM", "has_idea", "NAM_wage_arrears"), facts)
        close = options[BASE + ".close"]
        self.assertTrue(self.matches(block(close, "trigger"), facts))
        before = facts.copy()
        self.apply(close, facts)
        self.assertEqual(facts, before)

    def test_bilingual_costs_story_limits_and_encoding(self):
        for language in ("russian", "english"):
            path = ROOT / f"localisation/{language}/{BASE}_l_{language}.yml"
            self.assertTrue(path.read_bytes().startswith(b"\xef\xbb\xbf"))
            text = path.read_text(encoding="utf-8-sig")
            values = dict(re.findall(r'^[ \t]*([^ #:\s]+):\d*[ \t]*"(.*)"[ \t]*$', text, re.M))
            exile = [name for kind in EXILE for name in self.exile_trees[kind][1]]
            for name in (*self.focuses, *self.postwar, *self.defeated, *exile):
                self.assertIn(name, values.keys())
                self.assertIn(name + "_desc", values.keys())
            for name, decision in self.decisions.items():
                self.assertIn(name, values)
                self.assertIn(name + "_desc", values)
                for cost in (e.value for e in decision if e.key == "custom_cost_text"):
                    for suffix in ("", "_blocked", "_tooltip"):
                        self.assertIn(cost + suffix, values)
            story_ids = [f"{BASE}.{number}" for number in (10, 11, 12, 13, 20, 21, 70, 80, 109)]
            story_ids.append("ADISCORD_nam_groups.12")
            story_ids.extend(f"ADISCORD_nam_memoir.{number}" for number in (*range(1, 6), *range(11, 16)))
            story_ids.extend(f"ADISCORD_nam_archive.{number}" for number in range(1, 7))
            for event_id in story_ids:
                descriptions = [e.value for e in self.events[event_id] if e.key == "desc"]
                keys = [scalar(d, "text") if isinstance(d, list) else d for d in descriptions]
                for key in keys:
                    prose = values[key].replace("\\n", "\n")
                    self.assertLessEqual(len(prose), 3000)
                    self.assertLessEqual(len(prose.encode("utf-8")), 5500)
                    self.assertNotIn("§Y", prose)
        for path in (*(source for source, _, _ in TREES.values()), "common/ai_strategy_plans/ADISCORD_NAM_plans.txt",
                     f"common/decisions/{BASE}_decisions.txt", f"common/ideas/{BASE}_ideas.txt", f"events/{BASE}_events.txt"):
            self.assertFalse((ROOT / path).read_bytes().startswith(b"\xef\xbb\xbf"))
            self.assertTrue(balanced_braces(read(path)), path)

    def test_institution_changes_invalidate_economy_without_polling(self):
        for name, idea in self.ideas.items():
            if not name.startswith("NAM_"):
                continue
            # Display-only aggregate deltas are never installed; their refresh owns invalidation.
            allowed = [entry.value for entry in idea if entry.key == "allowed"]
            self.assertLessEqual(len(allowed), 1, name)
            if allowed and [(e.key, e.value) for e in allowed[0]] == [("always", "no")]:
                continue
            for hook in ("on_add", "on_remove"):
                self.assertIn("ADISCORD_economy_mark_dirty", [e.key for e in block(idea, hook)], name)
        hooks = read("common/on_actions/03_ADISCORD_nam_resource_war_on_actions.txt")
        self.assertNotIn("on_daily", hooks)
        self.assertNotIn("every_country", hooks)


class NamPillarsTests(unittest.TestCase):
    """Pillars of power: five weighted groups, programme progress and endings."""

    GROUPS = ("nam", "oil", "dist", "garr", "trade")

    @classmethod
    def setUpClass(cls):
        cls.focuses = {}
        for kind in TREES:
            cls.focuses.update(tree_focuses(kind)[1])
        cls.effects = {e.key: e.value for e in parsed(f"common/scripted_effects/{BASE}_effects.txt")}

    def changes(self, entries, kind):
        result = {}
        for entry in walk(entries):
            if entry.key != "add_to_variable":
                continue
            name = scalar(entry.value, "var")
            for group in self.GROUPS:
                if name == f"NAM_grp_{group}_{kind}":
                    result[group] = result.get(group, 0) + float(scalar(entry.value, "value"))
        return result

    def test_initial_influence_is_complete_and_endings_redistribute_it(self):
        initial = {}
        for entry in walk(self.effects["NAM_groups_initialize"]):
            if entry.key == "set_variable" and scalar(entry.value, "var").endswith("_influence"):
                initial[scalar(entry.value, "var")] = float(scalar(entry.value, "value"))
        self.assertEqual(len(initial), 5)
        self.assertEqual(sum(initial.values()), 100)
        endings = [name for name in self.focuses if "_ending_" in name]
        self.assertEqual(len(endings), 4)
        for name in endings:
            shift = self.changes(block(self.focuses[name], "completion_reward"), "influence")
            self.assertTrue(shift, name)
            self.assertEqual(sum(shift.values()), 0, name)
            for group, value in shift.items():
                self.assertGreaterEqual(initial[f"NAM_grp_{group}_influence"] + value, 0, name)

    def test_each_path_final_offers_two_exclusive_endings(self):
        finals = {
            "NAM_ladder_of_seals": ("NAM_ladder_ending_iron", "NAM_ladder_ending_service"),
            "NAM_common_fuel_market": ("NAM_charter_ending_federation", "NAM_charter_ending_oil_union"),
        }
        effects = {
            "NAM_ladder_ending_iron": "NAM_apply_ending_iron",
            "NAM_ladder_ending_service": "NAM_apply_ending_service",
            "NAM_charter_ending_federation": "NAM_apply_ending_federation",
            "NAM_charter_ending_oil_union": "NAM_apply_ending_oil_union",
        }
        for final, pair in finals.items():
            for name in pair:
                focus = self.focuses[name]
                self.assertEqual([e.value for e in block(focus, "prerequisite")], [final], name)
                other = next(n for n in pair if n != name)
                self.assertEqual([e.value for e in block(focus, "mutually_exclusive")], [other], name)
                reward = block(focus, "completion_reward")
                self.assertIn("NAM_prog_ending", repr(reward), name)
                self.assertIn((effects[name], "yes"), [(e.key, e.value) for e in reward], name)
        for source, _, _ in TREES.values():
            self.assertNotIn("NAM_programme", read(source))

    def test_every_support_shift_refreshes_and_is_localised(self):
        texts = {language: read(f"localisation/{language}/{BASE}_l_{language}.yml") for language in ("russian", "english")}
        shifted = 0
        for name, focus in self.focuses.items():
            reward = block(focus, "completion_reward")
            if not self.changes(reward, "support"):
                continue
            shifted += 1
            tooltips = [e.value for e in walk(reward) if e.key == "custom_effect_tooltip"]
            self.assertIn(f"NAM_grp_{name[4:]}_tt", tooltips, name)
            self.assertIn("NAM_groups_refresh", [e.key for e in walk(reward)], name)
            for language, text in texts.items():
                self.assertIn(f" NAM_grp_{name[4:]}_tt:", text, (language, name))
        self.assertGreaterEqual(shifted, 30)

    def test_refresh_covers_every_group_without_world_scans(self):
        source = read(f"common/scripted_effects/{BASE}_effects.txt")
        start = source.index("NAM_groups_refresh = {")
        refresh = source[start:source.index("\n}\n", start)]
        for group in self.GROUPS:
            self.assertIn(f"NAM_grp_{group}_support", refresh)
            self.assertIn(f"NAM_grp_{group}_influence", refresh)
        self.assertIn("force_update_dynamic_modifier = yes", refresh)
        self.assertNotIn("every_country", refresh)
        hooks = read("common/on_actions/03_ADISCORD_nam_resource_war_on_actions.txt")
        self.assertIn("on_monthly_NAM", hooks)
        self.assertIn("NAM = {\n\t\t\t\t\tNAM_groups_initialize = yes", read("common/on_actions/00_ADISCORD_on_actions.txt"))


class NamOptimizationTests(unittest.TestCase):
    """Parsed state transitions and work counts; native timing remains unmodelled."""

    GROUPS = NamPillarsTests.GROUPS

    @classmethod
    def setUpClass(cls):
        cls.effects = {
            entry.key: entry.value
            for entry in parsed(f"common/scripted_effects/{BASE}_effects.txt")
        }

    def normalize(self, entries):
        result = []
        comparisons = {">": "greater_than", "<": "less_than"}
        for entry in entries:
            if entry.key == "check_variable" and not any(e.key == "var" for e in entry.value):
                name, operator, value = (e.value for e in entry.value)
                entry = replace(entry, value=parse_clausewitz(
                    f"var = {name} value = {value} compare = {comparisons[operator]}"
                ))
            elif isinstance(entry.value, list):
                entry = replace(entry, value=self.normalize(entry.value))
            result.append(entry)
        return result

    def execute(self, name, facts, calls):
        arithmetic = {
            "set_variable": lambda old, value: value,
            "add_to_variable": lambda old, value: old + value,
            "subtract_from_variable": lambda old, value: old - value,
            "multiply_variable": lambda old, value: old * value,
            "divide_variable": lambda old, value: old / value,
        }
        for scope, entry in selected_effects(self.normalize(self.effects[name]), facts, "NAM"):
            operation = entry.key.replace("_temp_variable", "_variable")
            if operation in arithmetic:
                variable = scalar(entry.value, "var")
                reference = scalar(entry.value, "value")
                try:
                    value = float(reference)
                except ValueError:
                    value = facts.get((scope, "variable", reference), 0)
                key = (scope, "variable", variable)
                facts[key] = arithmetic[operation](facts.get(key, 0), value)
                if "_temp_variable" not in entry.key:
                    facts[(scope, "has_variable", variable)] = True
            elif operation == "clamp_variable":
                key = (scope, "variable", scalar(entry.value, "var"))
                facts[key] = min(float(scalar(entry.value, "max")), max(
                    float(scalar(entry.value, "min")), facts.get(key, 0)
                ))
            elif entry.key in ("NAM_groups_refresh", "NAM_seal_discipline_clamp"):
                calls[entry.key] += 1
                self.execute(entry.key, facts, calls)
            elif entry.key == "add_dynamic_modifier":
                facts[(scope, "has_dynamic_modifier", scalar(entry.value, "modifier"))] = True
            elif entry.key == "set_country_flag":
                self.assertIsInstance(entry.value, str)
                facts[(scope, "has_country_flag", entry.value)] = True
            elif entry.key == "country_event":
                calls[scalar(entry.value, "id")] += 1
            elif entry.key in (
                "force_update_dynamic_modifier", "ADISCORD_economy_mark_dirty",
                "NAM_groups_check_events",
            ):
                calls[entry.key] += 1
            else:
                self.fail(f"Unsupported optimization fixture effect: {entry.key}")

    def test_monthly_drift_preserves_values_and_only_refreshes_changed_inputs(self):
        for group, support in product(self.GROUPS, (0, 20, 49.49, 49.5, 49.99, 50, 50.01, 50.5, 85, 100)):
            with self.subTest(group=group, support=support):
                facts = {
                    ("NAM", "has_country_flag", "NAM_groups_initialized"): True,
                    ("NAM", "has_dynamic_modifier", "NAM_loyalty_dynamic"): True,
                }
                for current in self.GROUPS:
                    facts[("NAM", "variable", f"NAM_grp_{current}_support")] = 50
                    facts[("NAM", "variable", f"NAM_grp_{current}_influence")] = 20
                key = ("NAM", "variable", f"NAM_grp_{group}_support")
                facts[key] = support
                calls = Counter()
                self.execute("NAM_groups_monthly", facts, calls)
                expected = max(50, support - 0.5) if support >= 50 else min(50, support + 0.5)
                self.assertAlmostEqual(facts[key], expected)
                for current in self.GROUPS:
                    if current != group:
                        self.assertEqual(facts[("NAM", "variable", f"NAM_grp_{current}_support")], 50)
                self.assertEqual(calls["NAM_groups_check_events"], 1)
                self.assertEqual(calls["ADISCORD_economy_mark_dirty"], int(support != 50))
                self.assertEqual(calls["force_update_dynamic_modifier"], int(support != 50))

    def test_monthly_drift_keeps_initialization_guard_and_missing_modifier_refresh(self):
        for initialized, modifier in product((False, True), repeat=2):
            facts = {
                ("NAM", "has_country_flag", "NAM_groups_initialized"): initialized,
                ("NAM", "has_dynamic_modifier", "NAM_loyalty_dynamic"): modifier,
            }
            for group in self.GROUPS:
                facts[("NAM", "variable", f"NAM_grp_{group}_support")] = 50
            calls = Counter()
            self.execute("NAM_groups_monthly", facts, calls)
            self.assertEqual(calls["NAM_groups_check_events"], int(initialized))
            self.assertEqual(calls["NAM_groups_refresh"], int(initialized and not modifier))

    def test_discipline_recovers_and_stops_refreshing_at_cap(self):
        facts = {
            ("NAM", "has_dynamic_modifier", "NAM_seal_discipline_dynamic"): True,
            ("NAM", "has_variable", "NAM_seal_org_factor"): True,
            ("NAM", "has_war", "no"): True,
            ("NAM", "variable", "NAM_seal_discipline"): 96,
            ("NAM", "variable", "NAM_seal_org_factor"): 0.046,
        }
        for expected, updates in ((99, 1), (100, 1), (100, 0), (100, 0)):
            calls = Counter()
            self.execute("NAM_seal_discipline_monthly", facts, calls)
            self.assertEqual(facts[("NAM", "variable", "NAM_seal_discipline")], expected)
            self.assertAlmostEqual(facts[("NAM", "variable", "NAM_seal_org_factor")], (expected - 50) / 1000)
            self.assertEqual(calls["force_update_dynamic_modifier"], updates)

    def test_discipline_unchanged_modifier_still_checks_event_thresholds(self):
        for value, event in ((0, 32), (24, 31), (49, 30), (50, None), (100, None)):
            facts = {
                ("NAM", "has_dynamic_modifier", "NAM_seal_discipline_dynamic"): True,
                ("NAM", "has_variable", "NAM_seal_org_factor"): True,
                ("NAM", "ADISCORD_nam_resource_war_active", "yes"): True,
                ("NAM", "variable", "NAM_seal_discipline"): value,
                ("NAM", "variable", "NAM_seal_org_factor"): (value - 50) / 1000,
            }
            calls = Counter()
            self.execute("NAM_seal_discipline_clamp", facts, calls)
            self.assertEqual(calls["force_update_dynamic_modifier"], 0)
            expected = Counter({f"{BASE}.{event}": 1}) if event else Counter()
            self.assertEqual(calls, expected)
            self.execute("NAM_seal_discipline_clamp", facts, calls)
            if value == 0:
                expected[f"{BASE}.31"] = 1
            self.assertEqual(calls, expected)

    def test_discipline_initial_zero_factor_and_casualty_accounting(self):
        facts = {
            ("NAM", "has_dynamic_modifier", "NAM_seal_discipline_dynamic"): True,
            ("NAM", "ADISCORD_nam_resource_war_active", "yes"): True,
            ("NAM", "variable", "NAM_seal_discipline"): 50,
            ("NAM", "variable", "NAM_seal_casualties_seen_k"): 10,
        }
        calls = Counter()
        self.execute("NAM_seal_discipline_clamp", facts, calls)
        self.assertEqual(calls["force_update_dynamic_modifier"], 1)
        self.assertEqual(facts[("NAM", "variable", "NAM_seal_org_factor")], 0)
        for casualties, expected in ((20, 48), (20, 48), (5, 48), (10, 47)):
            facts[("NAM", "variable", "casualties_k")] = casualties
            self.execute("NAM_seal_discipline_monthly", facts, calls)
            self.assertEqual(facts[("NAM", "variable", "NAM_seal_discipline")], expected)
            self.assertEqual(facts[("NAM", "variable", "NAM_seal_casualties_seen_k")], casualties)

    def test_exile_zero_quota_skips_divisions_and_positive_quota_preserves_order(self):
        body = self.normalize(self.effects["NAM_rw_exile_abandon_state"])
        owners = ("EFL", "NAM", "NAM", "AZH", "NAM")
        for quota in (0, 1, 2, 3, 5):
            facts = {("NAM", "variable", "NAM_exile_to_cut"): quota}
            loops = list(selected_effects(body, facts, "NAM"))
            self.assertEqual(len(loops), int(quota > 0))
            abandoned = []
            for _, loop in loops:
                self.assertEqual(loop.key, "every_state_division")
                owner_filter = block(block(loop.value, "limit"), "OWNER")
                for index, owner in enumerate(owners):
                    if not matches_conditions(owner_filter, facts, owner):
                        continue
                    payload = [e for e in loop.value if e.key != "limit"]
                    for _, entry in selected_effects(payload, facts, "NAM"):
                        if entry.key == "change_division_template":
                            self.assertEqual(scalar(entry.value, "division_template"), "Abandoned Columns")
                            abandoned.append(index)
                        elif entry.key == "subtract_from_temp_variable":
                            facts[("NAM", "variable", scalar(entry.value, "var"))] -= float(scalar(entry.value, "value"))
                        else:
                            self.fail(f"Unsupported evacuation effect: {entry.key}")
            self.assertEqual(abandoned, [1, 2, 4][:quota])
            self.assertEqual(facts[("NAM", "variable", "NAM_exile_to_cut")], max(0, quota - 3))

    def test_exile_fallback_and_diagnostic_scans_have_separate_guards(self):
        body = self.normalize(self.effects["NAM_rw_exile_evacuate"])
        fallback = [
            entry.value for entry in walk(body)
            if entry.key == "if"
            and any(
                scan.key == "every_state" and any(
                    condition.key == "state" and condition.value == "700"
                    for condition in walk(block(scan.value, "limit"))
                )
                for scan in entry.value
            )
        ]
        self.assertEqual(len(fallback), 1)
        for quota in (0, 1):
            facts = {("NAM", "variable", "NAM_exile_to_cut"): quota}
            self.assertEqual(matches_conditions(block(fallback[0], "limit"), facts, "NAM"), quota > 0)
        diagnostic = [
            entry.value for entry in body if entry.key == "if"
            and any(e.key == "log" for e in entry.value)
        ]
        self.assertEqual(len(diagnostic), 1)
        for debug in (False, True):
            facts = {("NAM", "is_debug", "yes"): debug}
            self.assertEqual(matches_conditions(block(diagnostic[0], "limit"), facts, "NAM"), debug)
        # Transport and attrition remain unconditional after the abandonment phase.
        self.assertEqual(len([e for e in body if e.key == "every_state"]), 1)
        self.assertIn("NAM_rw_exile_damage_army", [e.key for e in body])


class NamValidatorTests(unittest.TestCase):
    """Exercise the production validator without changing loaded game files."""

    def validate(self, sources=None, states=None):
        from tools.validators import validate_adiscord_nam_resource_war as validator

        original_read = validator.read
        original_state = validator.state_source
        sources = sources or {}
        states = states or {}

        def read_source(path):
            return sources[path] if path in sources else original_read(path)

        def read_state(state):
            return states[state] if state in states else original_state(state)

        with patch.object(validator, "ISSUES", []), patch.object(
            validator, "read", read_source
        ), patch.object(validator, "state_source", read_state), redirect_stdout(StringIO()):
            result = validator.main()
            return result, list(validator.ISSUES)

    def assert_rejected(self, message, **overrides):
        result, issues = self.validate(**overrides)
        self.assertEqual(result, 1)
        self.assertTrue(any(message in issue for issue in issues), issues)

    def test_current_campaign_passes(self):
        result, issues = self.validate()
        self.assertEqual((result, issues), (0, []))

    def front_ai_issues(self, source):
        from tools.validators import validate_adiscord_nam_resource_war as validator

        with patch.object(validator, "ISSUES", []):
            validator.check_front_ai(source)
            return list(validator.ISSUES)

    def test_front_ai_accepts_conditional_overrides_and_multiline_baselines(self):
        source = read("common/ai_strategy/ADISCORD_nam_resource_war_ai.txt")
        self.assertEqual(self.front_ai_issues(source), [])
        self.assertEqual(self.front_ai_issues(source.replace(" = ", "\n=\n")), [])

    def test_front_ai_rejects_each_missing_baseline_despite_difficulty_overrides(self):
        from tools.validators.validate_adiscord_nam_resource_war import typed_blocks

        source = read("common/ai_strategy/ADISCORD_nam_resource_war_ai.txt")
        baselines = [
            strategy for strategy in typed_blocks(source, "ai_strategy")
            if "type = front_control" in strategy and "country_trigger" not in strategy
        ]
        self.assertEqual(len(baselines), 9)
        for baseline in baselines:
            with self.subTest(baseline=baseline.strip()):
                issues = self.front_ai_issues(source.replace(baseline, "", 1))
                self.assertTrue(any("expected one baseline front_control" in issue for issue in issues), issues)

    def test_front_ai_rejects_wrong_target_priority_and_attack_policy(self):
        source = read("common/ai_strategy/ADISCORD_nam_resource_war_ai.txt")
        for original, replacement, field in (
            ("tag = NAM ratio", "tag = EFL ratio", "tag"),
            ("priority = 1500", "priority = 1200", "priority"),
            ("execution_type = rush ", "execution_type = careful ", "execution_type"),
            ("manual_attack = yes", "manual_attack = no", "manual_attack"),
        ):
            with self.subTest(field=field):
                issues = self.front_ai_issues(source.replace(original, replacement, 1))
                expected = f"ADISCORD_nam_resource_war_eflor_offensive: baseline front_control requires {field} ="
                self.assertTrue(any(expected in issue for issue in issues), issues)

    def test_front_ai_checks_nested_difficulty_coverage_ratios(self):
        source = read("common/ai_strategy/ADISCORD_nam_resource_war_ai.txt")
        for replacement in ("ratio = 1", "ratio = -0.1", "ratio = invalid", ""):
            with self.subTest(replacement=replacement):
                changed = source.replace("\t\tratio = 0.01", f"\t\t{replacement}", 1)
                self.assertNotEqual(changed, source)
                issues = self.front_ai_issues(changed)
                self.assertTrue(any("front_control needs one coverage ratio" in issue for issue in issues), issues)

    def test_orders_cannot_reuse_or_lock_ordinary_templates(self):
        units_path = "history/units/NAM.txt"
        units = read(units_path)
        effects_path = f"common/scripted_effects/{BASE}_effects.txt"
        effects = read(effects_path)
        for role, ordinary, mobilisation in (
            ("guard", "Capital Guard", "Mobilisation Guard"),
            ("infantry", "Line Infantry Brigade", "Mobilisation Infantry Brigade"),
        ):
            with self.subTest(role=role):
                locked = units.replace(
                    f'name = "{ordinary}"',
                    f'name = "{ordinary}"\n\tis_locked = yes',
                )
                self.assert_rejected(
                    f"ordinary {ordinary} must stay editable",
                    sources={units_path: locked},
                )
                rerouted = effects.replace(f'\\"{mobilisation}\\"', f'\\"{ordinary}\\"')
                self.assert_rejected(
                    f"paid {role} must use its fixed mobilisation template",
                    sources={effects_path: rerouted},
                )

    def test_wrong_stockpiles_still_fail(self):
        path = f"common/scripted_effects/{BASE}_effects.txt"
        source = read(path)
        for tag, amount in (("EFL", 30000), ("AZH", 18000), ("SLF", 18000), ("NAM", 15000)):
            with self.subTest(tag=tag):
                token = f"type = infantry_equipment amount = {amount} producer = {tag}"
                self.assertEqual(source.count(token), 1)
                changed = source.replace(token, token.replace(str(amount), str(amount // 10)))
                message = "emergency defence" if tag == "NAM" else f"stockpile for {tag}"
                self.assert_rejected(message, sources={path: changed})

    def test_global_one_shot_news_still_fail(self):
        from tools.validators.validate_adiscord_nam_resource_war import typed_blocks

        path = f"events/{BASE}_events.txt"
        source = read(path)
        for event in typed_blocks(source, "news_event"):
            event_id = re.search(r"\bid\s*=\s*(\S+)", event)[1]
            with self.subTest(event=event_id):
                self.assertEqual(event.count("fire_only_once = no"), 1)
                changed = source.replace(event, event.replace("fire_only_once = no", "fire_only_once = yes"))
                self.assert_rejected(event_id, sources={path: changed})

    def test_return_war_news_require_each_terminal_dispatch(self):
        from tools.validators.validate_adiscord_nam_resource_war import named_block

        path = f"common/scripted_effects/{BASE}_effects.txt"
        source = read(path)
        for effect, event_id in (
            ("NAM_wor_annex_svetlogorye", "ADISCORD_nam_resource_news.8"),
            ("NAM_war_of_return_resolve_victory", "ADISCORD_nam_resource_news.9"),
            ("NAM_great_war_resolve_victory", "ADISCORD_nam_resource_news.9"),
        ):
            with self.subTest(effect=effect):
                body = named_block(source, effect)
                call = f"news_event = {{ id = {event_id} hours = 1 }}"
                self.assertEqual(body.count(call), 1)
                changed = source.replace(body, body.replace(call, ""))
                self.assert_rejected(effect, sources={path: changed})

    def test_debug_category_remains_debug_only_and_country_independent(self):
        path = "common/decisions/categories/ADISCORD_scenario_debug_categories.txt"
        source = read(path)
        for before, after in (("always = yes", "tag = NAM"), ("is_debug = yes", "always = yes")):
            with self.subTest(condition=before):
                self.assert_rejected("shared scenario debug category", sources={path: source.replace(before, after)})

    def test_old_capital_and_victory_points_still_fail(self):
        from tools.validators.validate_adiscord_nam_resource_war import state_source

        path = "history/countries/NAM - NamestnikLand.txt"
        self.assert_rejected("history capital", sources={path: read(path).replace("capital = 700", "capital = 689")})
        for state, before, after in (
            (67, "victory_points = { 6099 1 }", "victory_points = { 6099 1 }\n victory_points = { 1710 1 }"),
            (688, "victory_points = { 16721 5 }", "victory_points = { 689 5 }"),
            (689, "history = {", "history = {\n victory_points = { 2038 5 }"),
            (700, "victory_points = { 16716 5 }", "victory_points = { 16716 4 }"),
        ):
            source = state_source(state)
            with self.subTest(state=state):
                self.assertIn(before, source)
                self.assert_rejected(f"state {state}", states={state: source.replace(before, after)})


class NamBasinGuiTests(unittest.TestCase):
    """Map navigation must never pay for or start a district operation."""

    @classmethod
    def setUpClass(cls):
        root = block(parsed("common/scripted_guis/ADISCORD_NAM_scripted_gui.txt"), "scripted_gui")
        cls.panel = block(root, "ADISCORD_NAM_basin_panel")
        cls.effects = block(cls.panel, "effects")
        cls.triggers = block(cls.panel, "triggers")

    def test_all_six_map_markers_only_select_their_district(self):
        for state in (67, 688, 689, 690, 719, 700):
            click = block(self.effects, f"NAM_bw_select_{state}_click")
            self.assertEqual([entry.key for entry in click], ["set_variable"])
            self.assertEqual(scalar(block(click, "set_variable"), "NAM_bw_selected_state"), str(state))
            visible = block(self.triggers, f"NAM_bw_card_{state}_title_visible")
            if state == 67:
                visible = block(visible, "OR")
                self.assertEqual(scalar(block(visible, "NOT"), "has_variable"), "NAM_bw_selected_state")
            check = block(visible, "check_variable")
            self.assertEqual(scalar(check, "var"), "NAM_bw_selected_state")
            self.assertEqual(scalar(check, "value"), str(state))
            self.assertEqual(scalar(check, "compare"), "equals")

    def test_map_is_embedded_in_the_native_decision_category(self):
        self.assertEqual(scalar(self.panel, "context_type"), "decision_category")
        category = block(parsed(f"common/decisions/categories/{BASE}_categories.txt"), "NAM_national_programmes")
        self.assertEqual(scalar(category, "scripted_gui"), "ADISCORD_NAM_basin_panel")
        source = read("common/scripted_guis/ADISCORD_NAM_scripted_gui.txt")
        self.assertNotIn("NAM_bw_open", source)
        self.assertNotIn("NAM_bw_close_button", source)
        self.assertNotIn("every_country", source)

    def test_map_operations_keep_the_existing_targeted_decision_dispatch(self):
        for state in (67, 688, 689, 690, 719, 700):
            operations = ("line",) if state == 700 else ("repair", "refinery", "line")
            for operation in operations:
                click = block(self.effects, f"NAM_bw_{state}_{operation}_click")
                guarded = block(click, "if")
                limit = block(block(guarded, "limit"), str(state))
                self.assertEqual(scalar(limit, f"NAM_bw_{operation}_startable"), "yes")
                dispatch = block(guarded, "activate_targeted_decision")
                self.assertEqual(scalar(dispatch, "target"), str(state))
                decision = {"repair": "NAM_project_repair_wells", "refinery": "NAM_project_refinery", "line": "NAM_prepare_line"}[operation]
                self.assertEqual(scalar(dispatch, "decision"), decision)
                self.assertEqual([entry.key for entry in guarded], ["limit", "activate_targeted_decision"])

    def test_compact_categories_keep_every_group_input_and_rules(self):
        gui = read("interface/ADISCORD_NAM_basin.gui")
        for language in ("russian", "english"):
            loc = read(f"localisation/{language}/{BASE}_l_{language}.yml")
            for group in ("nam", "oil", "dist", "garr", "trade"):
                self.assertIn(f'NAM_bw_support_{group}', gui)
                row = re.search(rf'^ NAM_bw_support_{group}:.*$', loc, re.M).group()
                self.assertIn(f"NAM_grp_{group}_support", row)
                self.assertIn(f"NAM_grp_{group}_influence", row)
            self.assertRegex(loc, r'(?m)^ NAM_bw_support_rules:.*120.*')
            self.assertRegex(loc, r'(?m)^ NAM_bw_programme_rules:.*420.*')
            self.assertFalse("[?]" in loc, language)

    def test_card_controls_are_direct_scripted_gui_children(self):
        roots = block(parsed("interface/ADISCORD_NAM_basin.gui"), "guiTypes")
        window = next(e.value for e in roots if scalar(e.value, "name") == "ADISCORD_NAM_basin_window")
        controls = {scalar(e.value, "name"): e.value for e in window if isinstance(e.value, list) and e.key.endswith("Type")}
        for state in (67, 688, 689, 690, 719, 700):
            for part in ("title", "body"):
                name = f"NAM_bw_card_{state}_{part}"
                self.assertIn(name, controls)
                self.assertTrue(block(self.triggers, name + "_visible"))
            operations = ("line",) if state == 700 else ("repair", "refinery", "line")
            for operation in operations:
                for suffix in ("", "_price", "_duration"):
                    name = f"NAM_bw_{state}_{operation}{suffix}"
                    self.assertIn(name, controls)
                    self.assertIn("NAM_bw_selected_state", repr(block(self.triggers, name + "_visible")))
        self.assertIn("NAM_bw_port_guidance", controls)
        self.assertIn("NAM_bw_selected_state", repr(block(self.triggers, "NAM_bw_port_guidance_visible")))

    def test_gui_uses_native_decision_panels_and_resolved_tooltip_text(self):
        gui = read("interface/ADISCORD_NAM_basin.gui")
        self.assertNotIn('quadTextureSprite = "GFX_NAM_bw_panel"', gui)
        self.assertIn('quadTextureSprite = "GFX_ADISCORD_decisions_category_desc_bg"', gui)
        for language in ("russian", "english"):
            loc = read(f"localisation/{language}/{BASE}_l_{language}.yml")
            for line in loc.splitlines():
                if line.startswith(" NAM_bw_"):
                    self.assertNotIn("$", line)

    def test_each_selection_shows_one_card_with_its_own_operations(self):
        states = (67, 688, 689, 690, 719, 700)
        for selected in (None, *states):
            facts = {
                ("NAM", "has_variable", "NAM_bw_selected_state"): selected is not None,
                ("NAM", "variable", "NAM_bw_selected_state"): selected or 0,
                ("NAM", "has_completed_focus", "NAM_field_repair_crews"): True,
                ("NAM", "has_completed_focus", "NAM_refinery_programme"): True,
            }
            for state in states:
                facts[(str(state), "is_owned_by", "NAM")] = True
                facts[(str(state), "NAM_bw_line_offered", "yes")] = True
            for state in states:
                names = [f"NAM_bw_card_{state}_title", f"NAM_bw_card_{state}_body"]
                operations = ("line",) if state == 700 else ("repair", "refinery", "line")
                names.extend(f"NAM_bw_{state}_{operation}{suffix}" for operation in operations for suffix in ("", "_price", "_duration"))
                if state == 700:
                    names.append("NAM_bw_port_guidance")
                for name in names:
                    with self.subTest(selected=selected, widget=name):
                        self.assertEqual(matches_conditions(block(self.triggers, name + "_visible"), facts, "NAM"), state == (selected or 67))

    def test_map_geometry_and_generated_files_match(self):
        from tools.builders.build_adiscord_nam_basin_map import build_outputs, check_outputs

        outputs, geometry = build_outputs()
        self.assertEqual(set(geometry), {67, 688, 689, 690, 719, 700})
        for state, node in geometry.items():
            self.assertTrue(node["mask"].getbbox(), state)
            self.assertGreater(node["mask"].getpixel(node["anchor"]), 0, state)
        self.assertEqual(check_outputs(outputs), [])

    def test_support_texticons_cover_focus_and_decision_rewards(self):
        from PIL import Image

        sprites = block(parsed("interface/ADISCORD_NAM_basin.gfx"), "spriteTypes")
        definitions = {scalar(entry.value, "name"): entry.value for entry in sprites}
        for group in ("nam", "oil", "dist", "garr", "trade"):
            sprite = definitions[f"GFX_NAM_support_{group}_texticon"]
            with Image.open(ROOT / scalar(sprite, "texturefile")) as icon:
                self.assertEqual(icon.size, (20, 20))
                self.assertEqual(icon.mode, "RGBA")
            for language in ("russian", "english"):
                loc = read(f"localisation/{language}/{BASE}_l_{language}.yml")
                values = dict(re.findall(r'^ ([^ :]+):\d* "(.*)"$', loc, re.M))
                for key in (f"NAM_concede_{group}_tt", f"NAM_bribe_{group}_tt", f"NAM_favour_{group}_tt"):
                    self.assertRegex(values[key], rf'§[GRY][+-]\d+§! £NAM_support_{group}_texticon')
                self.assertIn(f"£NAM_support_{group}_texticon", values["NAM_grp_independence_day_tt"])


class NamPanelOptimizationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root = block(parsed("common/scripted_guis/ADISCORD_NAM_scripted_gui.txt"), "scripted_gui")
        cls.basin = block(root, "ADISCORD_NAM_basin_panel")
        cls.piracy = block(root, "ADISCORD_NAM_piracy_panel")

    def test_hidden_card_buttons_skip_availability_and_selected_cards_keep_it(self):
        class ReadFacts(dict):
            def get(self, key, default=None):
                if key[1].endswith("_startable"):
                    self.reads.append(key)
                return super().get(key, default)

        states = (67, 688, 689, 690, 719, 700)
        triggers = block(self.basin, "triggers")
        for selection, available in product((None, *states, 0), (False, True)):
            for state in states:
                for operation in (("line",) if state == 700 else ("repair", "refinery", "line")):
                    facts = ReadFacts({
                        ("NAM", "has_variable", "NAM_bw_selected_state"): selection is not None,
                        ("NAM", "variable", "NAM_bw_selected_state"): selection or 0,
                        (str(state), f"NAM_bw_{operation}_startable", "yes"): available,
                    })
                    facts.reads = []
                    selected = state == (67 if selection is None else selection)
                    with self.subTest(selection=selection, state=state, operation=operation, available=available):
                        result = matches_conditions(block(triggers, f"NAM_bw_{state}_{operation}_click_enabled"), facts, "NAM")
                        self.assertEqual(result, selected and available)
                        self.assertEqual(len(facts.reads), int(selected))

    def test_line_offer_preserves_conditions_and_skips_neighbours_before_unlock(self):
        source = parsed(f"common/scripted_triggers/{BASE}_triggers.txt")
        offered = block(source, "NAM_bw_line_offered")
        neighbours = block(offered, "any_neighbor_state")
        self.assertEqual(scalar(block(neighbours, "NOT"), "is_owned_by"), "NAM")
        self.assertEqual(offered[-1].key, "any_neighbor_state")
        # Supply the result of the native neighbour predicate independently.
        fixture = [replace(e, value="yes") if e.key == "any_neighbor_state" else e for e in offered]
        for owned, prepared, focus, programme, foreign_neighbour in product((False, True), repeat=5):
            facts = {
                ("67", "is_owned_by", "NAM"): owned,
                ("67", "has_state_flag", "NAM_line_prepared"): prepared,
                ("NAM", "has_completed_focus", "NAM_line_survey"): focus,
                ("NAM", "NAM_line_programme_open", "yes"): programme,
                ("67", "any_neighbor_state", "yes"): foreign_neighbour,
            }
            self.assertEqual(matches_conditions(fixture, facts, "67"),
                             owned and not prepared and focus and programme and foreign_neighbour)
            if not focus or not programme:
                # An unsupported native iterator would fail this fixture if reached.
                self.assertFalse(matches_conditions(offered, facts, "67"))
        startable = block(source, "NAM_bw_line_startable")
        self.assertEqual(startable[-1].key, "NAM_bw_line_offered")
        for controlled, busy, operable, slot, price, offer in product((False, True), repeat=6):
            facts = {
                ("67", "is_controlled_by", "NAM"): controlled,
                ("67", "has_state_flag", "NAM_line_in_progress"): busy,
                ("NAM", "NAM_country_operable", "yes"): operable,
                ("NAM", "NAM_line_slot_free", "yes"): slot,
                ("NAM", "NAM_bw_can_pay_line", "yes"): price,
                ("67", "NAM_bw_line_offered", "yes"): offer,
            }
            self.assertEqual(matches_conditions(startable, facts, "67"),
                             controlled and not busy and operable and slot and price and offer)

    def gauge_frame(self, gauge, facts):
        """Evaluate only the documented temporary arithmetic used by GUI properties."""
        arithmetic = {
            "set_temp_variable": lambda old, value: value,
            "subtract_from_temp_variable": lambda old, value: old - value,
            "divide_temp_variable": lambda old, value: old / value,
            "modulo_temp_variable": lambda old, value: old % value,
            "add_to_temp_variable": lambda old, value: old + value,
        }
        trigger = block(block(self.piracy, "triggers"), f"NAM_pw_{gauge}_track_visible")
        for scope, entry in selected_effects(trigger, facts, "NAM"):
            if entry.key in arithmetic:
                name = scalar(entry.value, "var")
                reference = scalar(entry.value, "value")
                value = facts.get((scope, "variable", reference))
                if value is None:
                    value = Decimal(0) if reference.startswith("NAM_") else Decimal(reference)
                key = (scope, "variable", name)
                facts[key] = arithmetic[entry.key](facts.get(key, Decimal(0)), value)
            elif entry.key == "clamp_temp_variable":
                key = (scope, "variable", scalar(entry.value, "var"))
                facts[key] = min(Decimal(scalar(entry.value, "max")),
                                 max(Decimal(scalar(entry.value, "min")), facts[key]))
            elif entry.key == "always":
                self.assertEqual(entry.value, "yes")
            else:
                self.fail(f"Unexpected GUI arithmetic or persistent write: {entry.key}")
        return facts[("NAM", "variable", f"NAM_pw_{gauge}_frame")]

    def test_gauge_frames_match_strict_thresholds_and_refresh_in_both_directions(self):
        thresholds = [Decimal("2.5") + 5 * i for i in range(20)]
        values = {Decimal(v) / 1000 for v in range(0, 100001, 137)}
        values.update(t + offset for t in thresholds for offset in (Decimal("-0.001"), Decimal(0), Decimal("0.001")))
        values.update(map(Decimal, (-20, 0, 100, 120)))
        for gauge, variable in (("notoriety", "NAM_pirate_notoriety"), ("revenge", "NAM_revenge_readiness")):
            facts = {}
            for value in [*sorted(values), *sorted(values, reverse=True), None]:
                key = ("NAM", "variable", variable)
                if value is None:
                    facts.pop(key, None)
                else:
                    facts[key] = value
                expected = 1 + sum((value or 0) > threshold for threshold in thresholds)
                with self.subTest(gauge=gauge, value=value):
                    self.assertEqual(self.gauge_frame(gauge, facts), expected)
                    self.assertEqual(facts.get(key), value)

    def test_gauge_atlas_pixels_match_the_track_and_twenty_individual_cells(self):
        from PIL import Image
        from tools.builders.build_adiscord_nam_piracy_map import gauge_image, png_bytes
        from io import BytesIO

        with Image.open(ROOT / "gfx/interface/NAM_piracy/segment.png") as source:
            cells = source.copy()
        for gauge, ticks in (("notoriety", (50, 75)), ("revenge", (70,))):
            with Image.open(ROOT / f"gfx/interface/NAM_piracy/gauge_{gauge}.png") as source:
                atlas = source.copy()
            self.assertEqual(atlas.size, (204 * 21, 18))
            with Image.open(BytesIO(png_bytes(gauge_image(ticks)))) as source:
                expected = source.copy()
            for lit in range(21):
                if lit:
                    colour = (1 if lit <= 10 else 2 if lit <= 15 else 3) if gauge == "notoriety" else (4 if lit <= 14 else 5)
                    cell = cells.crop(((colour - 1) * 9, 0, colour * 9, 10))
                    expected.alpha_composite(cell, (2 + (lit - 1) * 10, 4))
                self.assertEqual(atlas.crop((lit * 204, 0, (lit + 1) * 204, 18)).tobytes(), expected.tobytes(), (gauge, lit))

    def test_two_direct_gauge_controls_have_live_frame_bindings_and_no_dirty(self):
        roots = block(parsed("interface/ADISCORD_NAM_piracy.gui"), "guiTypes")
        window = next(e.value for e in roots if scalar(e.value, "name") == "ADISCORD_NAM_piracy_window")
        controls = {scalar(e.value, "name"): e.value for e in window if e.key.endswith("Type")}
        self.assertFalse(any(re.fullmatch(r"NAM_pw_(notoriety|revenge)_\d+", name) for name in controls))
        sprites = {scalar(e.value, "name"): e.value for e in block(parsed("interface/ADISCORD_NAM_piracy.gfx"), "spriteTypes")}
        for gauge, row in (("notoriety", 362), ("revenge", 406)):
            name = f"NAM_pw_{gauge}_track"
            position = block(controls[name], "position")
            self.assertEqual((scalar(position, "x"), scalar(position, "y")), ("150", str(row)))
            self.assertEqual(scalar(block(block(self.piracy, "properties"), name), "frame"), f"NAM_pw_{gauge}_frame")
            self.assertEqual(scalar(sprites[f"GFX_NAM_pw_gauge_{gauge}"], "noOfFrames"), "21")
        for panel in (self.basin, self.piracy):
            self.assertNotIn("dirty", [e.key for e in panel])


class NamQolTests(unittest.TestCase):
    def test_petitions_share_a_pause_without_blocking_an_existing_coup(self):
        effects = parsed(f"common/scripted_effects/{BASE}_effects.txt")
        groups = block(effects, "NAM_groups_check_events")
        guard = block(block(groups, "if"), "limit")
        self.assertTrue(matches_conditions(guard, {}, "NAM"))
        for key, value in (
            ("has_country_flag", "NAM_grp_event_pending"),
            ("has_country_flag", "NAM_rival_event_pending"),
            ("has_country_flag", "NAM_political_petition_cooldown"),
            ("has_active_mission", "NAM_rival_demand"),
        ):
            self.assertFalse(matches_conditions(guard, {("NAM", key, value): True}, "NAM"))
        close = block(effects, "NAM_groups_close_event")
        self.assertEqual(close[0].key, "set_country_flag")
        self.assertEqual(scalar(close[0].value, "flag"), "NAM_political_petition_cooldown")
        self.assertEqual(scalar(close[0].value, "days"), "90")
        self.assertEqual(close[-1].key, "NAM_groups_refresh")
        for entry in walk(groups):
            if entry.key == "set_country_flag" and isinstance(entry.value, list):
                flag = scalar(entry.value, "flag")
                expected = "90" if flag == "NAM_political_petition_cooldown" else "360"
                self.assertEqual(scalar(entry.value, "days"), expected)
        rivals = block(effects, "NAM_rivals_monthly")
        coup = block(block(rivals, "if"), "limit")
        self.assertNotIn("NAM_political_petition_cooldown", repr(coup))
        triggers = parsed(f"common/scripted_triggers/{BASE}_triggers.txt")
        cycle = block(triggers, "NAM_rival_cycle_open")
        self.assertIn("NAM_political_petition_cooldown", repr(cycle))
        self.assertIn("NAM_grp_event_pending", repr(cycle))

    def test_underground_actions_explain_temporary_blockers(self):
        categories = parsed(f"common/decisions/categories/{BASE}_categories.txt")
        underground = block(categories, "NAM_underground")
        self.assertEqual(scalar(block(underground, "visible"), "has_variable"), "NAM_underground")
        for name in ("NAM_underground", "NAM_national_programmes", "NAM_treasury", "NAM_overseas_districts"):
            self.assertEqual(scalar(block(categories, name), "visible_when_empty"), "yes")
        decisions = block(parsed(f"common/decisions/{BASE}_decisions.txt"), "NAM_underground")
        for number in (1, 2, 3):
            decision = block(decisions, f"NAM_weber_talks_{number}")
            self.assertNotIn("NAM_weber_talks_possible", repr(block(decision, "visible")))
            self.assertIn("NAM_weber_talks_possible", repr(block(decision, "available")))
        searches = block(decisions, "NAM_hunt_caches")
        self.assertNotIn("NAM_caches_searched", repr(block(searches, "visible")))
        self.assertIn("NAM_caches_searched", repr(block(searches, "available")))

    def test_support_colours_respect_fractional_thresholds(self):
        definitions = parsed(f"common/scripted_localisation/{BASE}_scripted_loc.txt")
        cases = ((25, "penalty"), (25.5, "neutral"), (69.5, "neutral"),
                 (70, "bonus"), (84.5, "bonus"), (85, "demand"))
        for group, name in (("nam", "Nam"), ("oil", "Oil"), ("dist", "Dist"), ("garr", "Garr"), ("trade", "Trade")):
            definition = next(e.value for e in definitions if scalar(e.value, "name") == f"NAMSupport{name}Colour")
            for support, colour in cases:
                facts = {("NAM", "variable", f"NAM_grp_{group}_support"): support}
                for entry in definition:
                    if entry.key != "text":
                        continue
                    triggers = [e.value for e in entry.value if e.key == "trigger"]
                    if not triggers or matches_conditions(triggers[0], facts, "NAM"):
                        self.assertEqual(scalar(entry.value, "localization_key"), f"NAM_bw_colour_{colour}")
                        break
                else:
                    self.fail("Missing support colour fallback")


if __name__ == "__main__":
    unittest.main()
