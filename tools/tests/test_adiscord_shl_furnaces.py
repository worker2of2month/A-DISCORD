"""Execute bounded SHL accounting scripts; native loader/UI still need game QA."""

import unittest
import re
from collections import defaultdict
from pathlib import Path

from tools.validators.validate_adiscord_division_templates import parse_clausewitz

ROOT = Path(__file__).resolve().parents[2]
EFFECT_PATH = ROOT / "common/scripted_effects/ADISCORD_SHL_scripted_effects.txt"
TRIGGER_PATH = ROOT / "common/scripted_triggers/ADISCORD_SHL_scripted_triggers.txt"


def block(items, key):
    return next((e.value for e in items if e.key == key and isinstance(e.value, list)), [])


def scalar(items, key, default=None):
    return next((e.value for e in items if e.key == key), default)


def decision_definition(identifier):
    source = parse_clausewitz((ROOT / "common/decisions/ADISCORD_SHL_decisions.txt").read_text(encoding="utf-8"))
    for category in source:
        for decision in category.value:
            if decision.key == identifier:
                return decision.value
    raise AssertionError("Missing decision: " + identifier)


def focus_definition(identifier):
    tree = block(parse_clausewitz((ROOT / "focus_trees/SHL/main/focuses.txt").read_text(encoding="utf-8")), "focus_tree")
    return next(entry.value for entry in tree if entry.key == "focus" and scalar(entry.value, "id") == identifier)


class ScriptMachine:
    def __init__(self, effects, triggers):
        self.effects = {e.key: e.value for e in effects}
        self.triggers = {e.key: e.value for e in triggers}
        self.variables = defaultdict(dict)
        self.flags = defaultdict(set)
        self.flag_days = defaultdict(dict)
        self.control = {str(i): "SHL" for i in range(287, 296)}
        self.ownership = dict(self.control)
        self.control["294"] = "SHL"
        self.focuses = set()
        self.factories = 0
        self.infrastructure = 0
        self.anti_air = 0
        self.free_slots = True
        self.capitulated = False
        self.scheduled = []
        self.values = {"political_power": 200.0, "stability": 0.0}
        self.dynamic = set()
        self.calls = []
        self.previous_scope = "SHL"
        self.target_scope = None
        self.variables["SHL"]["ADISCORD_economy_treasury"] = 1000.0

    def value(self, value, scope):
        try:
            return float(value)
        except (ValueError, TypeError):
            if "." in value:
                owner, name = value.split(".", 1)
                if owner == "FROM":
                    owner = self.target_scope
                elif owner == "PREV":
                    owner = self.previous_scope
                return self.variables[owner].get(name, 0.0)
            return self.variables[scope].get(value, 0.0)

    def matches(self, items, scope, target=None):
        def match(e):
            if e.key == "OR":
                return any(match(child) for child in e.value)
            if e.key == "AND" or e.key in ("hidden_trigger", "custom_trigger_tooltip"):
                return all(match(child) for child in e.value if child.key != "tooltip")
            if e.key == "NOT":
                return not any(match(child) for child in e.value)
            if e.key == "check_variable":
                name = scalar(e.value, "var")
                left = self.variables[scope].get(name, 0.0)
                right = self.value(scalar(e.value, "value"), scope)
                comparison = scalar(e.value, "compare", "greater_than_or_equals")
                return {
                    "equals": left == right,
                    "greater_than": left > right,
                    "greater_than_or_equals": left >= right,
                    "less_than": left < right,
                    "less_than_or_equals": left <= right,
                }[comparison]
            if e.key == "has_variable":
                return e.value in self.variables[scope]
            if e.key == "has_country_flag" or e.key == "has_state_flag":
                if isinstance(e.value, list):
                    name = scalar(e.value, "flag")
                    tokens = [child.value for child in e.value if not child.key]
                    if tokens != ["days", ">", "27"]:
                        raise AssertionError("Unsupported flag-age predicate")
                    return name in self.flags[scope] and self.flag_days[scope].get(name, 0) > 27
                return e.value in self.flags[scope]
            if e.key in ("ROOT", "SHL"):
                return self.condition_scope(e.value, "SHL", scope, target)
            if e.key == "FROM":
                return self.condition_scope(e.value, target, scope, target)
            if e.key.isdigit():
                return self.condition_scope(e.value, e.key, scope, target)
            if e.key in ("is_owned_by", "is_controlled_by"):
                expected = "SHL" if e.value == "ROOT" else e.value
                owners = self.ownership if e.key == "is_owned_by" else self.control
                return owners.get(scope) == expected
            if e.key == "has_completed_focus":
                return e.value in self.focuses
            if e.key == "has_capitulated":
                return self.capitulated == (e.value == "yes")
            if e.key == "has_political_power":
                return self.values["political_power"] >= float(e.value)
            if e.key == "has_dynamic_modifier":
                return e.value in self.dynamic
            if e.key == "has_building":
                return self.factories > 0
            if e.key == "free_building_slots":
                return self.free_slots
            if e.key == "tag":
                return scope == e.value
            if e.key == "state":
                return scope == e.value
            if e.key == "exists" or e.key == "always":
                return e.value == "yes"
            if e.key == "is_ai":
                return e.value == "no"
            if e.key in self.triggers:
                result = self.matches(self.triggers[e.key], scope, target)
                return result == (e.value == "yes")
            raise AssertionError("Unsupported predicate: " + e.key)
        results = []
        index = 0
        while index < len(items):
            entry = items[index]
            if not entry.key:
                comparison = [item.value for item in items[index:index + 3]]
                if comparison[1:] != ["<", "5"] or comparison[0] not in ("infrastructure", "anti_air_building"):
                    raise AssertionError("Unsupported native comparison: " + repr(comparison))
                value = self.infrastructure if comparison[0] == "infrastructure" else self.anti_air
                results.append(value < 5)
                index += 3
            else:
                results.append(match(entry))
                index += 1
        return all(results)

    def condition_scope(self, items, scope, previous, target):
        saved = self.previous_scope
        self.previous_scope = previous
        result = self.matches(items, scope, target)
        self.previous_scope = saved
        return result

    def run(self, name, scope="SHL", target=None):
        if name not in self.effects:
            raise AssertionError("Missing SHL effect: " + name)
        self.target_scope = target
        self.execute(self.effects[name], scope, target)

    def switch_scope(self, items, scope, previous, target):
        saved = self.previous_scope
        self.previous_scope = previous
        self.execute(items, scope, target)
        self.previous_scope = saved

    def execute(self, items, scope, target=None):
        taken = False
        for e in items:
            if e.key in ("if", "else_if", "else"):
                if e.key == "if":
                    taken = False
                if not taken and (e.key == "else" or self.matches(block(e.value, "limit"), scope, target)):
                    taken = True
                    self.execute([c for c in e.value if c.key != "limit"], scope, target)
            elif e.key in ("hidden_effect",):
                self.execute(e.value, scope, target)
            elif e.key in ("ROOT", "SHL"):
                self.switch_scope(e.value, "SHL", scope, target)
            elif e.key == "FROM":
                self.switch_scope(e.value, target, scope, target)
            elif e.key.isdigit():
                self.switch_scope(e.value, e.key, scope, target)
            elif e.key in self.effects:
                if e.value != "yes":
                    raise AssertionError("Effects must use native boolean calls")
                self.run(e.key, scope, target)
            elif e.key in ("set_variable", "add_to_variable", "subtract_from_variable", "multiply_variable", "divide_variable"):
                name = scalar(e.value, "var")
                amount = self.value(scalar(e.value, "value"), scope)
                previous = self.variables[scope].get(name, 0.0)
                if e.key == "set_variable":
                    self.variables[scope][name] = amount
                elif e.key == "add_to_variable":
                    self.variables[scope][name] = previous + amount
                elif e.key == "subtract_from_variable":
                    self.variables[scope][name] = previous - amount
                elif e.key == "multiply_variable":
                    self.variables[scope][name] = previous * amount
                else:
                    self.variables[scope][name] = previous / amount
            elif e.key == "clamp_variable":
                name = scalar(e.value, "var")
                value = self.variables[scope].get(name, 0.0)
                minimum = self.value(scalar(e.value, "min", "-1000000"), scope)
                maximum = self.value(scalar(e.value, "max", "1000000"), scope)
                self.variables[scope][name] = max(minimum, min(maximum, value))
            elif e.key == "clear_variable":
                self.variables[scope].pop(e.value, None)
            elif e.key in ("set_country_flag", "set_state_flag"):
                self.flags[scope].add(e.value)
                self.flag_days[scope][e.value] = 0
            elif e.key in ("clr_country_flag", "clr_state_flag"):
                self.flags[scope].discard(e.value)
            elif e.key == "add_building_construction":
                if scalar(e.value, "type") == "industrial_complex":
                    self.factories += int(scalar(e.value, "level"))
                elif scalar(e.value, "type") == "infrastructure":
                    self.infrastructure += int(scalar(e.value, "level"))
                elif scalar(e.value, "type") == "anti_air_building":
                    self.anti_air += int(scalar(e.value, "level"))
            elif e.key == "add_political_power":
                self.values["political_power"] += self.value(e.value, scope)
            elif e.key == "add_stability":
                self.values["stability"] += self.value(e.value, scope)
            elif e.key == "add_dynamic_modifier":
                self.dynamic.add(scalar(e.value, "modifier"))
            elif e.key == "remove_dynamic_modifier":
                self.dynamic.discard(e.value)
            elif e.key == "country_event":
                self.scheduled.append(scalar(e.value, "id"))
            elif e.key in ("ADISCORD_economy_mark_dirty", "ADISCORD_economy_clamp_treasury"):
                self.calls.append(e.key)
            elif e.key in ("custom_effect_tooltip", "remove_ideas", "add_to_array", "log", "air_experience"):
                self.calls.append(e.key)
            else:
                raise AssertionError("Unsupported effect: " + e.key)


class FurnaceAccountingTests(unittest.TestCase):
    def setUp(self):
        effects = parse_clausewitz(EFFECT_PATH.read_text(encoding="utf-8")) if EFFECT_PATH.exists() else []
        triggers = parse_clausewitz(TRIGGER_PATH.read_text(encoding="utf-8")) if TRIGGER_PATH.exists() else []
        self.machine = ScriptMachine(effects, triggers)
        for state in range(287, 296):
            self.machine.variables[str(state)].update({
                "SHL_furnace_stock": 2.0,
                "SHL_furnace_wear": 20.0,
                "SHL_furnace_owner": 0.0,
                "SHL_furnace_running": 1.0,
                "SHL_furnace_training": 0.0,
            })
        self.machine.flags["SHL"].add("SHL_furnaces_initialized")
        self.machine.variables["SHL"]["SHL_shift_policy"] = 0.0

    def test_source_exists(self):
        self.assertTrue(EFFECT_PATH.exists(), "SHL implementation is absent")

    def test_paid_repair_is_single_payment_and_single_delivery(self):
        m = self.machine
        m.run("SHL_begin_repair", target="287")
        m.run("SHL_begin_repair", target="287")
        self.assertEqual(m.variables["SHL"]["ADISCORD_economy_treasury"], 920)
        self.assertEqual(m.variables["287"]["SHL_operation"], 2)
        m.run("SHL_finish_repair", target="287")
        m.run("SHL_finish_repair", target="287")
        self.assertEqual(m.variables["287"]["SHL_furnace_wear"], 0)
        self.assertEqual(m.variables["SHL"]["ADISCORD_economy_treasury"], 920)
        self.assertEqual(m.variables["287"].get("SHL_operation", 0), 0)

    def test_supply_affordability_fractional_boundary(self):
        m = self.machine
        m.variables["SHL"]["ADISCORD_economy_treasury"] = 24.99
        m.run("SHL_begin_supply", target="287")
        self.assertEqual(m.variables["SHL"]["ADISCORD_economy_treasury"], 24.99)
        m.variables["SHL"]["ADISCORD_economy_treasury"] = 25
        m.run("SHL_begin_supply", target="287")
        self.assertEqual(m.variables["SHL"]["ADISCORD_economy_treasury"], 0)

    def test_cancel_refunds_once_and_releases_slot(self):
        m = self.machine
        m.run("SHL_begin_training", target="287")
        self.assertEqual(m.values["political_power"], 175)
        m.run("SHL_cancel_operation", target="287")
        m.run("SHL_cancel_operation", target="287")
        self.assertEqual(m.variables["SHL"]["ADISCORD_economy_treasury"], 1000)
        self.assertEqual(m.values["political_power"], 200)
        self.assertEqual(m.variables["287"].get("SHL_operation", 0), 0)

    def test_lost_region_refunds_without_delivering(self):
        m = self.machine
        m.run("SHL_begin_supply", target="287")
        m.control["287"] = "AZH"
        m.run("SHL_finish_supply", target="287")
        self.assertEqual(m.variables["287"]["SHL_furnace_stock"], 2)
        self.assertEqual(m.variables["SHL"]["ADISCORD_economy_treasury"], 1000)

    def test_parallel_sites_do_not_overwrite_receipts(self):
        m = self.machine
        m.run("SHL_begin_repair", target="287")
        m.run("SHL_begin_supply", target="288")
        m.run("SHL_cancel_operation", target="287")
        m.run("SHL_finish_supply", target="288")
        self.assertEqual(m.variables["SHL"]["ADISCORD_economy_treasury"], 975)
        self.assertEqual(m.variables["288"]["SHL_furnace_stock"], 3)

    def test_supply_returns_payment_if_reserve_filled_the_bunker_during_delivery(self):
        m = self.machine
        m.run("SHL_begin_supply", target="287")
        m.variables["287"]["SHL_furnace_stock"] = 3
        m.run("SHL_finish_supply", target="287")
        self.assertEqual(m.variables["287"]["SHL_furnace_stock"], 3)
        self.assertEqual(m.variables["SHL"]["ADISCORD_economy_treasury"], 1000)

    def test_gui_selection_does_not_move_a_paid_receipt_and_forecast_matches_training(self):
        m = self.machine
        m.run("SHL_begin_repair", target="287")
        m.variables["288"]["SHL_furnace_training"] = 1
        m.variables["SHL"].update({"SHL_selected_furnace": 2, "SHL_shift_policy": 2})
        m.run("SHL_refresh_furnaces")
        self.assertEqual(m.variables["SHL"]["SHL_selected_period_wear"], 2)
        m.run("SHL_finish_repair", target="287")
        self.assertEqual(m.variables["287"]["SHL_furnace_wear"], 0)
        self.assertEqual(m.variables["288"]["SHL_furnace_wear"], 20)

    def test_state_course_preserves_ownership_and_governance_when_refreshing(self):
        m = self.machine
        m.run("SHL_commit_state_course")
        m.run("SHL_extinguish_site", scope="287")
        m.run("SHL_refresh_furnaces")
        self.assertEqual(m.variables["287"]["SHL_furnace_owner"], 2)
        self.assertEqual(m.variables["SHL"]["SHL_pp_gain"], 0.10)

    def test_one_period_pays_exactly_one_output_per_controlled_running_site(self):
        m = self.machine
        m.control["288"] = "AZH"
        m.run("SHL_produce_period")
        self.assertEqual(m.variables["SHL"]["ADISCORD_economy_treasury"], 1280)
        self.assertEqual(m.variables["287"]["SHL_furnace_stock"], 1)
        self.assertEqual(m.variables["287"]["SHL_furnace_wear"], 26)
        self.assertEqual(m.variables["288"]["SHL_furnace_stock"], 2)

    def test_two_shortages_stop_the_furnace_without_repeated_ownership_gain(self):
        m = self.machine
        site = m.variables["287"]
        site["SHL_furnace_stock"] = 0
        m.run("SHL_produce_period")
        self.assertEqual(site["SHL_furnace_running"], 1)
        m.run("SHL_produce_period")
        self.assertEqual(site["SHL_furnace_running"], 0)
        self.assertEqual(site["SHL_furnace_owner"], 1)
        stopped_wear = site["SHL_furnace_wear"]
        m.run("SHL_produce_period")
        self.assertEqual(site["SHL_furnace_wear"], stopped_wear)

    def test_overtime_requires_two_whole_packets(self):
        m = self.machine
        m.variables["SHL"]["SHL_shift_policy"] = 1
        m.variables["287"]["SHL_furnace_stock"] = 1.99
        before = m.variables["SHL"]["ADISCORD_economy_treasury"]
        m.run("SHL_produce_site", scope="287")
        self.assertEqual(m.variables["SHL"]["ADISCORD_economy_treasury"], before)
        self.assertEqual(m.variables["287"]["SHL_furnace_stock"], 1.99)

    def test_project_duplicate_delivery_creates_one_factory(self):
        m = self.machine
        m.variables["SHL"]["SHL_project_stage"] = 2
        m.focuses.add("SHL_build_tenth_complex")
        m.run("SHL_begin_construction")
        m.run("SHL_finish_project")
        m.run("SHL_finish_project")
        self.assertEqual(m.factories, 1)
        self.assertEqual(m.variables["SHL"]["SHL_project_stage"], 3)
        self.assertEqual(m.variables["SHL"]["ADISCORD_economy_treasury"], 700)

    def test_project_slot_exhaustion_refunds_and_keeps_stage(self):
        m = self.machine
        m.variables["SHL"]["SHL_project_stage"] = 2
        m.focuses.add("SHL_build_tenth_complex")
        m.run("SHL_begin_construction")
        m.free_slots = False
        m.run("SHL_finish_project")
        self.assertEqual(m.factories, 0)
        self.assertEqual(m.variables["SHL"]["SHL_project_stage"], 2)
        self.assertEqual(m.variables["SHL"]["ADISCORD_economy_treasury"], 1000)

    def test_cycle_queue_has_single_pending_guard(self):
        m = self.machine
        m.run("SHL_schedule_cycle")
        m.run("SHL_schedule_cycle")
        self.assertEqual(m.scheduled.count("ADISCORD_SHL.1"), 1)

    def test_cancel_first_pour_returns_its_material_packet_once(self):
        m = self.machine
        m.variables["SHL"]["SHL_project_stage"] = 3
        m.variables["SHL"]["SHL_reserve_stock"] = 1
        m.focuses.add("SHL_first_pour_focus")
        m.run("SHL_begin_first_pour")
        self.assertEqual(m.variables["SHL"]["SHL_reserve_stock"], 0)
        m.run("SHL_cancel_project")
        m.run("SHL_cancel_project")
        self.assertEqual(m.variables["SHL"]["SHL_reserve_stock"], 1)
        self.assertEqual(m.variables["SHL"]["ADISCORD_economy_treasury"], 1000)

    def test_restart_requires_ownership_settlement_and_preserves_owner(self):
        m = self.machine
        m.variables["287"]["SHL_furnace_running"] = 0
        m.variables["287"]["SHL_furnace_owner"] = 1
        m.run("SHL_begin_restart", target="287")
        self.assertEqual(m.variables["SHL"]["ADISCORD_economy_treasury"], 1000)
        m.variables["287"]["SHL_restart_settled"] = 1
        m.run("SHL_begin_restart", target="287")
        m.run("SHL_finish_restart", target="287")
        self.assertEqual(m.variables["287"]["SHL_furnace_owner"], 1)
        self.assertEqual(m.variables["287"]["SHL_furnace_running"], 1)
        self.assertEqual(m.variables["287"]["SHL_furnace_wear"], 20)
        self.assertEqual(m.variables["SHL"]["ADISCORD_economy_treasury"], 880)

    def test_city_course_is_terminal_and_transfers_owned_sites_only(self):
        m = self.machine
        m.ownership["288"] = "AZH"
        m.run("SHL_commit_city_course")
        m.run("SHL_commit_state_course")
        self.assertEqual(m.variables["SHL"]["SHL_political_course"], 2)
        self.assertEqual(m.variables["287"]["SHL_furnace_owner"], 1)
        self.assertEqual(m.variables["288"]["SHL_furnace_owner"], 0)

    def test_training_reduces_wear_on_the_real_cycle(self):
        m = self.machine
        m.variables["287"]["SHL_furnace_training"] = 1
        m.run("SHL_produce_site", scope="287")
        self.assertEqual(m.variables["287"]["SHL_furnace_wear"], 25)

    def test_planned_supply_buys_the_missing_packet_at_full_price(self):
        m = self.machine
        m.variables["SHL"]["SHL_regular_supply"] = 1
        m.variables["SHL"]["ADISCORD_economy_treasury"] = 50
        m.variables["287"]["SHL_furnace_stock"] = 0
        m.run("SHL_produce_site", scope="287")
        self.assertEqual(m.variables["SHL"]["ADISCORD_economy_treasury"], 60)
        self.assertEqual(m.variables["287"]["SHL_furnace_shortages"], 0)

    def test_planned_supply_never_borrows_or_buys_fractional_packets(self):
        m = self.machine
        m.variables["SHL"]["SHL_regular_supply"] = 1
        m.variables["SHL"]["ADISCORD_economy_treasury"] = 24.99
        m.variables["287"]["SHL_furnace_stock"] = 0
        m.run("SHL_produce_site", scope="287")
        self.assertEqual(m.variables["SHL"]["ADISCORD_economy_treasury"], 24.99)
        self.assertEqual(m.variables["287"]["SHL_furnace_stock"], 0)

    def test_native_focus_tree_has_thirty_unique_reachable_focuses(self):
        path = ROOT / "focus_trees/SHL/main/focuses.txt"
        self.assertTrue(path.exists())
        tree = block(parse_clausewitz(path.read_text(encoding="utf-8")), "focus_tree")
        focuses = [e.value for e in tree if e.key == "focus"]
        ids = [scalar(f, "id") for f in focuses]
        self.assertEqual(len(ids), 30)
        self.assertEqual(len(set(ids)), 30)
        for focus in focuses:
            for prerequisite in [e.value for e in focus if e.key == "prerequisite"]:
                for item in prerequisite:
                    self.assertIn(item.value, ids)

    def test_annexation_clears_site_receipts_without_paying_new_owner(self):
        m = self.machine
        m.run("SHL_begin_training", target="287")
        m.run("SHL_abort_annexed_operations")
        self.assertNotIn("SHL_operation_deposit", m.variables["287"])
        self.assertEqual(m.variables["SHL"]["ADISCORD_economy_treasury"], 900)
        self.assertEqual(m.values["political_power"], 175)

    def test_old_queued_cycle_cannot_advance_a_new_liberation_clock(self):
        m = self.machine
        m.run("SHL_schedule_cycle")
        m.run("SHL_abort_annexed_operations")
        m.run("SHL_schedule_cycle")
        m.flag_days["SHL"]["SHL_cycle_pending"] = 5
        m.run("SHL_run_cycle")
        self.assertEqual(m.variables["SHL"].get("SHL_cycle_number", 0), 0)
        self.assertEqual(m.variables["287"]["SHL_furnace_stock"], 2)
        m.flag_days["SHL"]["SHL_cycle_pending"] = 28
        m.run("SHL_run_cycle")
        m.run("SHL_run_cycle")
        self.assertEqual(m.variables["SHL"]["SHL_cycle_number"], 1)

    def test_four_project_stages_deliver_one_site_and_consume_exact_prices(self):
        m = self.machine
        m.variables["SHL"]["SHL_reserve_stock"] = 1
        m.focuses.update({"SHL_engineer_society", "SHL_right_to_land", "SHL_build_tenth_complex", "SHL_first_pour_focus"})
        for stage in ("engineers", "foundation", "construction", "first_pour"):
            m.run("SHL_begin_" + stage)
            m.run("SHL_finish_project")
        self.assertEqual(m.variables["SHL"]["SHL_project_stage"], 4)
        self.assertEqual(m.variables["SHL"]["ADISCORD_economy_treasury"], 300)
        self.assertEqual(m.values["political_power"], 175)
        self.assertEqual(m.variables["SHL"]["SHL_reserve_stock"], 0)
        self.assertEqual(m.factories, 1)
        self.assertEqual(m.infrastructure, 1)

    def test_maximum_infrastructure_refunds_foundation_and_advances_stage(self):
        m = self.machine
        m.infrastructure = 5
        m.variables["SHL"]["SHL_project_stage"] = 1
        m.focuses.add("SHL_right_to_land")
        m.run("SHL_begin_foundation")
        m.run("SHL_finish_project")
        self.assertEqual(m.variables["SHL"]["SHL_project_stage"], 2)
        self.assertEqual(m.variables["SHL"]["ADISCORD_economy_treasury"], 1000)
        self.assertEqual(m.infrastructure, 5)

    def test_tenth_obeys_overtime_policy_and_planned_supply(self):
        m = self.machine
        country = m.variables["SHL"]
        country.update({"SHL_project_stage": 4, "SHL_tenth_running": 1, "SHL_tenth_stock": 0, "SHL_tenth_wear": 10, "SHL_shift_policy": 1, "SHL_regular_supply": 1})
        m.run("SHL_produce_period")
        self.assertEqual(country["SHL_tenth_stock"], 0)
        self.assertEqual(country["SHL_tenth_wear"], 20)
        self.assertEqual(country["SHL_last_cycle_income"], 500)
        self.assertEqual(country["ADISCORD_economy_treasury"], 1450)

    def test_tenth_restart_waits_and_lost_capital_refunds(self):
        m = self.machine
        country = m.variables["SHL"]
        country.update({"SHL_project_stage": 4, "SHL_tenth_running": 0, "SHL_tenth_stock": 1, "SHL_tenth_wear": 100})
        m.run("SHL_begin_tenth_restart")
        self.assertEqual(country["SHL_tenth_running"], 0)
        self.assertEqual(country["ADISCORD_economy_treasury"], 880)
        m.control["294"] = "AZH"
        m.run("SHL_finish_project")
        m.run("SHL_finish_project")
        self.assertEqual(country["ADISCORD_economy_treasury"], 1000)
        self.assertEqual(country["SHL_tenth_running"], 0)

    def test_house_votes_have_a_governance_consumer(self):
        m = self.machine
        m.run("SHL_refresh_furnaces")
        self.assertAlmostEqual(m.variables["SHL"]["SHL_pp_gain"], 0.05)
        m.run("SHL_extinguish_site", scope="287")
        m.run("SHL_refresh_furnaces")
        self.assertAlmostEqual(m.variables["SHL"]["SHL_pp_gain"], 0.05 * 8 / 9)

    def test_supplier_pressure_applies_one_reserve_surcharge(self):
        m = self.machine
        m.flags["SHL"].add("SHL_supplier_premium")
        m.variables["SHL"]["ADISCORD_economy_treasury"] = 69.99
        m.run("SHL_purchase_reserve")
        self.assertNotIn("SHL_reserve_stock", m.variables["SHL"])
        m.variables["SHL"]["ADISCORD_economy_treasury"] = 130
        m.run("SHL_purchase_reserve")
        self.assertEqual(m.variables["SHL"]["ADISCORD_economy_treasury"], 60)
        m.run("SHL_purchase_reserve")
        self.assertEqual(m.variables["SHL"]["ADISCORD_economy_treasury"], 0)
        self.assertEqual(m.variables["SHL"]["SHL_reserve_stock"], 4)

    def test_capital_occupation_cancels_each_paid_project_under_native_not_semantics(self):
        m = self.machine
        m.control["294"] = "AZH"
        for identifier in ("SHL_project_engineers", "SHL_project_foundation", "SHL_project_construction", "SHL_project_first_pour", "SHL_service_tenth", "SHL_restart_tenth"):
            with self.subTest(decision=identifier):
                self.assertTrue(m.matches(block(decision_definition(identifier), "cancel_trigger"), "SHL"))

    def test_shift_decision_updates_forecast_immediately(self):
        m = self.machine
        m.variables["SHL"]["SHL_selected_furnace"] = 1
        m.run("SHL_refresh_furnaces")
        m.execute(block(decision_definition("SHL_shift_overtime"), "complete_effect"), "SHL")
        self.assertEqual(m.variables["SHL"]["SHL_selected_period_income"], 50)
        self.assertEqual(m.variables["SHL"]["SHL_selected_period_cost"], 2)

    def test_air_defence_never_builds_for_an_enemy_or_above_the_native_cap(self):
        m = self.machine
        focus = focus_definition("SHL_factory_air_defence")
        m.control["294"] = "AZH"
        self.assertFalse(m.matches(block(focus, "available"), "SHL"))
        m.execute(block(focus, "completion_reward"), "SHL")
        self.assertEqual(m.anti_air, 0)
        m.control["294"] = "SHL"
        m.anti_air = 5
        self.assertFalse(m.matches(block(focus, "available"), "SHL"))
        m.execute(block(focus, "completion_reward"), "SHL")
        self.assertEqual(m.anti_air, 5)

    def test_ai_never_spends_on_a_cold_or_unworn_repair(self):
        m = self.machine
        ai = block(decision_definition("SHL_repair_furnace"), "ai_will_do")
        for wear in (0, 20):
            m.variables["287"]["SHL_furnace_wear"] = wear
            weight = float(scalar(ai, "base"))
            for modifier in [entry.value for entry in ai if entry.key == "modifier"]:
                condition = [entry for entry in modifier if entry.key != "factor"]
                if m.matches(condition, "SHL", "287"):
                    weight *= float(scalar(modifier, "factor"))
            self.assertEqual(weight, 0)

    def test_extinction_unlock_is_not_available_before_conclave_rules(self):
        m = self.machine
        m.variables["SHL"]["SHL_selected_furnace"] = 1
        self.assertFalse(m.matches(block(decision_definition("SHL_allow_extinction"), "visible"), "SHL", "287"))
        m.focuses.add("SHL_conclave_rules")
        self.assertTrue(m.matches(block(decision_definition("SHL_allow_extinction"), "visible"), "SHL", "287"))

    def test_english_localisation_contains_no_untranslated_cyrillic(self):
        text = (ROOT / "localisation/english/ADISCORD_SHL_l_english.yml").read_text(encoding="utf-8-sig")
        self.assertIsNone(re.search(r"[А-Яа-яЁё]", text))


if __name__ == "__main__":
    unittest.main()
