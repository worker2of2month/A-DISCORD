"""Execute authored Council transactions; native timers, UI and combat need a cold campaign."""

from dataclasses import replace
from copy import deepcopy
from io import BytesIO
from pathlib import Path
import itertools
import re
import unittest

from PIL import Image

from tools.builders import build_adiscord_val_flags
from tools.tests.test_adiscord_stp_preparation import block, entries, matches_conditions, scalar, walk
from tools.tests.test_adiscord_val_new_world import ContractWorld
from tools.tests.test_adiscord_val_focus_layout import PERSONAL_FOCUSES


ROOT = Path(__file__).resolve().parents[2]
EFFECTS = "common/scripted_effects/ADISCORD_VAL_effects.txt"
TRIGGERS = "common/scripted_triggers/ADISCORD_VAL_rework_triggers.txt"
DECISIONS = "common/decisions/ADISCORD_VAL_decisions.txt"
FOCUSES = "focus_trees/VAL/main/focuses.txt"
PREFIX = "VAL_council_"


class CouncilWorld(ContractWorld):
    """Add only primitives used by these receipts; fail on unhandled gameplay operations."""

    def __init__(self):
        super().__init__()
        self.decisions = {e.key: e.value for e in block(entries(DECISIONS), PREFIX + "government_category")}
        self.decisions.update({e.key: e.value for e in block(entries(DECISIONS), PREFIX + "balance_category")})
        self.decisions.update({e.key: e.value for e in block(entries(DECISIONS), "VAL_command_balance_category")})
        self.stack = ["VAL"]
        self.countries = ["VAL", "STP", "CIN"]
        for tag in self.countries:
            self.data[tag].update(cp=100, stability=0.5, missions={}, bop=None, council_bop=None,
                                  leader="VAL_Valera_Solgalov", tree="VAL_focus", neighbors=[],
                                  cores={"VAL"}, characters={"VAL_Valera_Solgalov"})
        self.val = self.data["VAL"]
        self.val["characters"].update(
            entry.value for entry in entries("history/countries/VAL - ValeraLand.txt")
            if entry.key == "recruit_character"
        )
        self.val["flags"].add(PREFIX + "in_power")
        self.val["leader"] = "VAL_Commanders_Council"
        self.val["capital"] = "176"
        self.data["176"].update(cores={"VAL"}, free_slots=5)
        self.calls = []
        self.debug = False
        self.val["characters"].add("VAL_Commanders_Council")
        self.run(PREFIX + "initialize_seats")

    def visible_council_focuses(self):
        return {
            scalar(entry.value, "id")
            for entry in block(entries(FOCUSES), "focus_tree")
            if entry.key == "focus"
            and scalar(entry.value, "id").startswith(PREFIX)
            and self.matches(block(entry.value, "allow_branch"))
        }

    def scope(self, key, current):
        if key == "ROOT":
            return self.stack[0]
        return self.stack[-2] if key == "PREV" else super().scope(key, current)

    def number(self, value, scope):
        if value == "num_equipment@infantry_equipment":
            return sum(self.data[scope]["rifles"].values())
        if value.startswith("days_mission_timeout@"):
            return self.data[scope]["missions"].get(value.split("@", 1)[1], 0)
        if "." in value:
            tag, name = value.split(".", 1)
            if tag == "PREV" or tag in self.countries:
                return self.data[self.scope(tag, scope)]["vars"].get(name, 0)
        return super().number(value, scope)

    def matches(self, rows, scope="VAL"):
        results = []
        for group in self.condition_groups(rows):
            row = group[0]
            key, value = row.key, row.value
            country = self.data[scope]
            if not key:
                left = country[{"has_political_power": "pp", "command_power": "cp"}[value]]
                op, right = group[1].value, float(group[2].value)
                results.append(left < right if op == "<" else left > right)
            elif key == "always":
                results.append(value == "yes")
            elif key == "is_debug":
                results.append(self.debug == (value == "yes"))
            elif key == "has_active_mission":
                results.append(value in country["missions"])
            elif key == "has_power_balance":
                results.append(country[self.balance_field(value)] is not None)
            elif key == "power_balance_value":
                operator, amount = value[-2].value, float(value[-1].value)
                current = country[self.balance_field(value)]
                results.append(current is not None and (current < amount if operator == "<" else current > amount))
            elif key == "has_focus_tree":
                results.append(country["tree"] == value)
            elif key == "has_country_leader":
                results.append(country["leader"] == scalar(value, "character"))
            elif key == "has_character":
                results.append(value in country["characters"])
            elif key == "check_variable":
                left = self.number(scalar(value, "var"), scope)
                right = self.number(scalar(value, "value"), scope)
                op = scalar(value, "compare")
                results.append({"equals": left == right, "greater_than": left > right,
                                "greater_than_or_equals": left >= right, "less_than": left < right,
                                "less_than_or_equals": left <= right}[op])
            elif key in ("is_owned_by", "is_controlled_by", "is_core_of"):
                field = {"is_owned_by": "owner", "is_controlled_by": "controller", "is_core_of": "cores"}[key]
                value = self.scope(value, scope)
                results.append(value in country[field] if field == "cores" else value == country[field])
            elif key == "capital_scope":
                results.append(self.matches(value, country["capital"]))
            elif key == "free_building_slots":
                self.assert_free_factory_slot_check(value)
                results.append(country["free_slots"] > 0)
            elif key == "any_owned_state":
                owned = [state for state, data in list(self.data.items()) if state.isdigit() and data["owner"] == scope]
                results.append(any(self.matches(value, state) for state in owned))
            elif key == "any_neighbor_state":
                results.append(any(self.matches(value, state) for state in country["neighbors"]))
            elif key.startswith("event_target:") or key == "PREV":
                results.append(self.matches(value, self.scope(key, scope)))
            elif key == "has_cosmetic_tag":
                results.append(country.get("cosmetic") == value)
            elif key in ("OCA", "NKA") and isinstance(value, list):
                results.append(self.matches(value, key))
            else:
                results.append(super().matches(group, scope))
        return all(results)

    @staticmethod
    def balance_field(rows):
        """The old Solgalov balance keeps `bop`; the Council balance is separate."""
        return "bop" if scalar(rows, "id") == "VAL_command_balance" else "council_bop"

    @staticmethod
    def assert_free_factory_slot_check(rows):
        assert scalar(rows, "building") == "arms_factory"
        assert scalar(rows, "include_locked") == "yes"
        comparison = next(group for group in CouncilWorld.condition_groups(rows) if group[0].key == "")
        assert [entry.value for entry in comparison] == ["size", ">", "0"]

    def execute(self, rows, scope="VAL"):
        taken = False
        for row in rows:
            key, value = row.key, row.value
            country = self.data[scope]
            if key in ("if", "else_if", "else"):
                if key == "if":
                    taken = False
                active = not taken and (key == "else" or self.matches(block(value, "limit"), scope))
                if active:
                    self.execute([e for e in value if e.key != "limit"], scope)
                taken |= active
            elif key in ("VAL_refresh_contract_modifier", "VAL_council_finish_political_reform", "log", "mark_focus_tree_layout_dirty"):
                self.calls.append(key)
            elif key in ("effect_tooltip", "unlock_decision_tooltip"):
                pass
            elif key == "set_power_balance":
                country[self.balance_field(value)] = float(scalar(value, "set_value"))
            elif key == "news_event":
                self.events.append((scope, scalar(value, "id")))
            elif key == "capital_scope":
                target = country["capital"]
                self.stack.append(target)
                self.execute(value, target)
                self.stack.pop()
            elif key == "random_neighbor_state":
                candidates = [state for state in country["neighbors"] if self.matches(block(value, "limit"), state)]
                if len(candidates) != 1:
                    raise AssertionError(("Fixture requires one eligible neighbor", scope, candidates))
                self.stack.append(candidates[0])
                self.execute([entry for entry in value if entry.key != "limit"], candidates[0])
                self.stack.pop()
            elif key == "every_possible_country":
                for tag in self.countries:
                    self.stack.append(tag)
                    if self.matches(block(value, "limit"), tag):
                        self.execute([e for e in value if e.key != "limit"], tag)
                    self.stack.pop()
            elif isinstance(value, list) and (key in self.countries or key in ("PREV", "FROM") or key.startswith("event_target:")):
                target = self.scope(key, scope)
                self.stack.append(target)
                self.execute(value, target)
                self.stack.pop()
            elif key in ("set_temp_variable", "add_to_temp_variable", "subtract_from_temp_variable", "multiply_temp_variable", "clamp_temp_variable"):
                self.execute([replace(row, key=key.replace("temp_", ""))], scope)
            elif key == "multiply_variable":
                name = scalar(value, "var")
                country["vars"][name] = country["vars"].get(name, 0) * self.number(scalar(value, "value"), scope)
            elif key in ("add_command_power", "add_stability"):
                country["cp" if key == "add_command_power" else "stability"] += float(value)
            elif key == "activate_mission":
                country["missions"][value] = int(scalar(self.decisions[value], "days_mission_timeout"))
            elif key == "remove_mission":
                country["missions"].pop(value, None)
            elif key == "add_days_mission_timeout":
                country["missions"][scalar(value, "mission")] += self.number(scalar(value, "days"), scope)
            elif key == "add_power_balance_value":
                field = self.balance_field(value)
                if country[field] is None:
                    raise AssertionError(("unguarded balance change", scope, scalar(value, "id")))
                country[field] += float(scalar(value, "value"))
            elif key == "remove_power_balance":
                country[self.balance_field(value)] = None
            elif key == "set_cosmetic_tag":
                country["cosmetic"] = value
            elif key == "drop_cosmetic_tag":
                country["cosmetic"] = None
            elif key == "add_field_marshal_role":
                country.setdefault("field_marshals", set()).add(scalar(value, "character"))
            elif key == "add_dynamic_modifier":
                country["modifiers"].add(scalar(value, "modifier"))
                country.setdefault("modifier_days", {})[scalar(value, "modifier")] = scalar(value, "days")
            elif key == "retire_character":
                country["characters"].discard(value)
            elif key == "add_country_leader_role":
                character = scalar(value, "character")
                assert character in country["characters"], character
                country.setdefault("leader_roles", {})[character] = scalar(
                    block(value, "country_leader"), "ideology"
                )
                if scalar(value, "promote_leader") == "yes":
                    country["leader"] = character
            elif key == "promote_character":
                country["leader"] = scalar(value, "character")
            elif key == "set_politics":
                self.calls.append(key)
            elif key == "add_equipment_to_stockpile":
                kind = scalar(value, "type")
                amount = self.number(scalar(value, "amount"), scope)
                producer = self.scope(scalar(value, "producer"), scope)
                stock = country["rifles"] if kind == "infantry_equipment" else country.setdefault(kind, {})
                stock[producer] = max(0, stock.get(producer, 0) + amount)
            else:
                super().execute([row], scope)

    def choose(self, suffix, stale=False):
        body = self.decisions[PREFIX + suffix]
        if not stale and not self.matches(block(body, "available")):
            return False
        self.execute(block(body, "complete_effect"))
        return True

    def expire(self, suffix):
        name = PREFIX + suffix
        self.val["missions"].pop(name, None)
        self.execute(block(self.decisions[name], "timeout_effect"))

    def balance(self):
        return self.val["vars"]["ADISCORD_economy_treasury"]


class CommandConsolidationTests(unittest.TestCase):
    """Execute payment and terminal callbacks; native countdown scheduling remains external."""

    def world(self):
        world = CouncilWorld()
        world.val["flags"].discard(PREFIX + "in_power")
        world.val["leader"] = "VAL_Valera_Solgalov"
        world.val["bop"] = 0.75
        world.val["focuses"].add("VAL_Captains_Cannot_Veto")
        world.run("VAL_expose_command_conspiracy")
        return world

    def start(self, world, route):
        decision = world.decisions["VAL_command_" + route]
        world.execute(block(decision, "complete_effect"))

    def timeout(self, world, route):
        timer = "VAL_command_" + route + "_timer"
        world.val["missions"].pop(timer, None)
        world.execute(block(world.decisions[timer], "timeout_effect"))

    def test_focus_threshold_and_exact_costs_gate_both_routes(self):
        for route in ("trial", "retirements"):
            for missing in ("focus", "balance", "political_power", "second_currency"):
                with self.subTest(route=route, missing=missing):
                    world = self.world()
                    world.val["pp"] = 100
                    world.val["cp"] = 50
                    world.val["vars"]["ADISCORD_economy_treasury"] = 250
                    if missing == "focus":
                        world.val["focuses"].clear()
                    elif missing == "balance":
                        world.val["bop"] = 0.749999
                    elif missing == "political_power":
                        world.val["pp"] = 99.99
                    elif route == "trial":
                        world.val["cp"] = 49.99
                    else:
                        world.val["vars"]["ADISCORD_economy_treasury"] = 249.99
                    before = world.balance(), world.val["pp"], world.val["cp"]
                    self.start(world, route)
                    self.assertEqual((world.balance(), world.val["pp"], world.val["cp"]), before)
                    self.assertNotIn("VAL_command_consolidation_kind", world.val["vars"])

    def test_paid_routes_finish_once_with_distinct_costs_and_consequences(self):
        for route, days, treasury, cp in (("trial", 90, 2000, 50), ("retirements", 120, 1750, 100)):
            with self.subTest(route=route):
                world = self.world()
                self.start(world, route)
                self.assertEqual(world.val["bop"], 0.75)
                self.assertEqual(world.val["missions"]["VAL_command_" + route + "_timer"], days)
                self.assertFalse(world.matches(block(world.decisions["VAL_command_" + route + "_timer"], "available")))
                self.start(world, route)
                self.start(world, "retirements" if route == "trial" else "trial")
                self.assertEqual((world.balance(), world.val["pp"], world.val["cp"]), (treasury, 900, cp))
                # A saved campaign retains the paid receipt and native mission state.
                world.val = world.data["VAL"] = deepcopy(world.val)
                self.timeout(world, route)
                self.timeout(world, route)
                world.run("VAL_cancel_command_consolidation")
                self.assertIsNone(world.val["bop"])
                self.assertEqual((world.balance(), world.val["pp"], world.val["cp"]), (treasury, 900, cp))
                self.assertNotIn("VAL_command_consolidation_kind", world.val["vars"])
                self.assertEqual(world.events.count(("VAL", "val_council.28")), 1)
                self.assertAlmostEqual(world.val["stability"], 0.45 if route == "trial" else 0.5)
                if route == "trial":
                    self.assertEqual(world.val["modifier_days"]["VAL_command_trial_disruption"], "180")
                    modifier = block(entries("common/dynamic_modifiers/ADISCORD_VAL_contract_dynamic_modifier.txt"), "VAL_command_trial_disruption")
                    self.assertEqual(scalar(modifier, "army_org_factor"), "-0.05")
                else:
                    self.assertNotIn("VAL_command_trial_disruption", world.val["modifiers"])

    def test_exact_affordability_is_available_and_debited_to_zero(self):
        for route in ("trial", "retirements"):
            world = self.world()
            world.val["pp"] = 100
            world.val["cp"] = 50
            world.val["vars"]["ADISCORD_economy_treasury"] = 250
            decision = world.decisions["VAL_command_" + route]
            self.assertTrue(world.matches(block(decision, "visible")))
            self.assertTrue(world.matches(block(decision, "available")))
            self.assertTrue(world.matches(block(decision, "custom_cost_trigger")))
            self.assertEqual(scalar(decision, "cost"), "0")
            self.start(world, route)
            self.assertEqual(world.val["pp"], 0)
            self.assertEqual(world.val["cp"] if route == "trial" else world.balance(), 0)

    def test_exact_threshold_does_not_cancel_and_all_cost_tooltips_load(self):
        world = self.world()
        self.start(world, "retirements")
        balance = block(entries("common/bop/VAL.txt"), "VAL_command_balance")
        dominance = next(row.value for side in balance if side.key == "side" for row in side.value
                         if row.key == "range" and scalar(row.value, "id") == "VAL_solgalov_dominance")
        world.execute(block(dominance, "on_deactivate"))
        self.assertEqual(world.balance(), 1750)
        self.assertEqual(world.val["missions"]["VAL_command_retirements_timer"], 120)
        required = set()
        for route in ("trial", "retirements"):
            for name in ("VAL_command_" + route, "VAL_command_" + route + "_timer"):
                required.update((name, name + "_desc"))
                for row in walk(world.decisions[name]):
                    if row.key in ("custom_effect_tooltip", "tooltip", "custom_cost_text"):
                        required.add(row.value)
                    if row.key == "custom_cost_text":
                        required.update((row.value + "_blocked", row.value + "_tooltip"))
        for language in ("russian", "english"):
            text = (ROOT / f"localisation/{language}/ADISCORD_VAL_decisions_l_{language}.yml").read_text(encoding="utf-8-sig")
            for key in required:
                self.assertRegex(text, rf'(?m)^ {re.escape(key)}:(?:0)? "(?:[^"\\\r\n]|\\.)*"$', key)

    def test_range_exit_refunds_only_unused_pensions_and_restarts_full_term(self):
        balance = block(entries("common/bop/VAL.txt"), "VAL_command_balance")
        dominance = next(row.value for side in balance if side.key == "side" for row in side.value
                         if row.key == "range" and scalar(row.value, "id") == "VAL_solgalov_dominance")
        for route, days in (("trial", 90), ("retirements", 120)):
            world = self.world()
            self.start(world, route)
            world.val["bop"] = 0.749999
            world.execute(block(dominance, "on_deactivate"))
            world.val["bop"] = 0.8
            self.timeout(world, route)
            world.run("VAL_cancel_command_consolidation")
            self.assertEqual(world.val["bop"], 0.8)
            self.assertEqual(world.balance(), 2000)
            self.assertEqual(world.val["pp"], 900)
            self.assertEqual(world.val["cp"], 50 if route == "trial" else 100)
            self.assertAlmostEqual(world.val["stability"], 0.5)
            self.start(world, route)
            self.assertEqual(world.val["missions"]["VAL_command_" + route + "_timer"], days)

    def test_terminal_changes_cancel_and_late_timeout_cannot_close_balance(self):
        for change in ("subject", "capitulated", "leader", "defeat", "balance_removed"):
            for route in ("trial", "retirements"):
                with self.subTest(change=change, route=route):
                    world = self.world()
                    self.start(world, route)
                    if change == "subject":
                        world.val["subject"] = "STP"
                    elif change == "capitulated":
                        world.val["capitulated"] = True
                    elif change == "leader":
                        world.val["leader"] = "VAL_Commanders_Council"
                    elif change == "defeat":
                        world.val["flags"].add("VAL_stelander_defeated")
                    else:
                        world.val["bop"] = None
                    timer = world.decisions["VAL_command_" + route + "_timer"]
                    self.assertTrue(world.matches(block(timer, "cancel_trigger")))
                    self.timeout(world, route)
                    world.execute(block(timer, "cancel_effect"))
                    self.assertEqual(world.balance(), 2000)
                    self.assertEqual(world.val["pp"], 900)
                    self.assertNotIn("VAL_command_consolidation_kind", world.val["vars"])
                    self.assertNotIn(("VAL", "val_council.28"), world.events)

    def test_unpaid_and_other_route_callbacks_cannot_settle_a_new_operation(self):
        world = self.world()
        self.timeout(world, "trial")
        self.timeout(world, "retirements")
        self.assertEqual(world.val["bop"], 0.75)
        self.start(world, "retirements")
        self.timeout(world, "trial")
        self.assertEqual(world.val["vars"]["VAL_command_consolidation_kind"], 2)
        self.assertEqual(world.balance(), 1750)
        self.timeout(world, "retirements")
        self.assertIsNone(world.val["bop"])


class CouncilTransactionsTests(unittest.TestCase):
    def test_loan_default_repayment_and_duplicate_click_conserve_money(self):
        world = CouncilWorld()
        world.val["vars"]["ADISCORD_economy_treasury"] = 0
        self.assertTrue(world.choose("borrow_500"))
        world.choose("borrow_1000", stale=True)
        self.assertEqual(world.balance(), 500)
        world.expire("loan_deadline")
        self.assertIn(PREFIX + "loan_default", world.val["flags"])
        world.val["vars"]["ADISCORD_economy_treasury"] = 550
        world.choose("repay_loan")
        world.choose("repay_loan", stale=True)
        self.assertEqual(world.balance(), 0)
        self.assertNotIn(PREFIX + "loan_debt", world.val["vars"])
        self.assertNotIn(PREFIX + "loan_default", world.val["flags"])

    def test_installment_never_delivers_before_final_payment(self):
        world = CouncilWorld()
        world.val["focuses"].add(PREFIX + "brokers")
        world.val["vars"]["ADISCORD_economy_treasury"] = 550
        world.choose("merchant_guarantee")
        world.choose("buy_installment")
        self.assertEqual(world.val["missions"][PREFIX + "order_arrival"], 14)
        world.expire("order_arrival")
        world.run(PREFIX + "daily")
        self.assertEqual(sum(world.val["rifles"].values()), 5000)
        self.assertFalse(world.choose("withdraw_merchant_guarantee"))
        world.val["vars"]["ADISCORD_economy_treasury"] = 300
        world.run(PREFIX + "daily")
        world.run(PREFIX + "daily")
        self.assertEqual(sum(world.val["rifles"].values()), 20000)
        self.assertEqual(world.balance(), 0)
        world.choose("withdraw_merchant_guarantee")
        self.assertEqual(world.balance(), 250)

    def test_two_batches_partial_cancel_refunds_only_undelivered_payment(self):
        world = CouncilWorld()
        world.choose("schedule_rifles")
        self.assertEqual(world.balance(), 1100)
        world.choose("buy_direct_rifles", stale=True)
        self.assertEqual(world.balance(), 1100)
        world.expire("order_arrival")
        world.run(PREFIX + "daily")
        self.assertEqual(world.val["missions"][PREFIX + "order_arrival"], 30)
        world.choose("cancel_purchase")
        world.choose("cancel_purchase", stale=True)
        world.run(PREFIX + "daily")
        self.assertEqual(world.balance(), 1437.5)
        self.assertEqual(sum(world.val["rifles"].values()), 20000)

    def test_capitulation_defers_paid_delivery_without_losing_receipt(self):
        world = CouncilWorld()
        world.choose("buy_direct_rifles")
        world.val["capitulated"] = True
        world.val["tree"] = "VAL_defeated_focus"
        world.expire("order_arrival")
        world.run(PREFIX + "daily")
        self.assertEqual(sum(world.val["rifles"].values()), 5000)
        world.val["capitulated"] = False
        world.val["subject"] = "STP"
        world.run(PREFIX + "daily")
        self.assertEqual(sum(world.val["rifles"].values()), 20000)
        self.assertEqual(world.balance(), 1550)

    def test_reserve_preserves_mixed_manufacturers_and_fractional_boundary(self):
        world = CouncilWorld()
        world.val["rifles"] = {"VAL": 3000.25, "STP": 6999.5}
        self.assertFalse(world.choose("reserve_rifles"))
        world.val["rifles"]["CIN"] = 0.25
        initial = world.val["rifles"].copy()
        self.assertTrue(world.choose("reserve_rifles"))
        self.assertEqual(sum(world.val["rifles"].values()), 0)
        world.choose("release_reserve")
        world.choose("release_reserve", stale=True)
        self.assertEqual(world.val["rifles"], initial)
        self.assertTrue(all(PREFIX + "reserved_by_producer" not in world.data[tag]["vars"] for tag in world.countries))

    def test_quarter_payment_cannot_be_repeated_after_stale_click(self):
        for suffix in ("reserve_quarter", "consortium_norm"):
            with self.subTest(suffix=suffix):
                world = CouncilWorld()
                world.val["flags"].add("VAL_quarterly_contract_active")
                world.val["missions"]["VAL_quarterly_contract_deadline"] = 45
                world.val["rifles"] = {"VAL": 50000}
                world.choose("reserve_rifles")
                world.choose(suffix)
                before = world.balance(), world.val["pp"], sum(world.val["rifles"].values())
                world.choose(suffix, stale=True)
                self.assertEqual((world.balance(), world.val["pp"], sum(world.val["rifles"].values())), before)
                self.assertEqual(world.val["missions"]["VAL_quarterly_contract_deadline"], 45)

    def test_mandate_deadline_settles_now_and_late_capture_is_not_rewarded(self):
        for kind in (1, 2):
            world = CouncilWorld()
            world.val["wars"].add("STP")
            world.val["vars"][PREFIX + "mandate_kind"] = kind
            world.val["flags"].add(PREFIX + "mandate_active")
            world.targets[PREFIX + "mandate_target"] = "176"
            world.targets[PREFIX + "mandate_enemy"] = "STP"
            world.data["STP"]["wars"].add("VAL")
            world.data["176"]["controller"] = "VAL" if kind == 1 else "STP"
            world.expire("mandate_deadline")
            self.assertNotIn(PREFIX + "mandate_kind", world.val["vars"])
            self.assertEqual(world.val["pp"], 1025 if kind == 1 else 1000)
            world.data["176"]["controller"] = "STP" if kind == 1 else "VAL"
            world.run(PREFIX + "reconcile_mandate")
            self.assertEqual(world.val["pp"], 1025 if kind == 1 else 1000)

    def test_earlier_losses_do_not_open_case_for_new_operation(self):
        world = CouncilWorld()
        world.val["focuses"].add(PREFIX + "losses_review")
        world.val["vars"].update(casualties_k=100, deployed_army_manpower_k=100)
        world.run(PREFIX + "weekly")
        world.val["vars"]["casualties_k"] = 200
        world.val["wars"].add("STP")
        world.choose("emergency_production")
        world.run(PREFIX + "weekly")
        self.assertNotIn(PREFIX + "case_open", world.val["flags"])
        world.val["vars"]["casualties_k"] = 225
        world.run(PREFIX + "weekly")
        self.assertIn(PREFIX + "case_open", world.val["flags"])

    def test_coup_waits_for_war_preserves_receipts_and_fires_after_peace(self):
        world = CouncilWorld()
        self.assertFalse(world.val.get("leader_roles"))
        world.val["flags"].discard(PREFIX + "in_power")
        world.val["leader"] = "VAL_Valera_Solgalov"
        world.val["flags"].add("VAL_quarterly_contract_active")
        world.val["bop"] = -0.9
        world.val["vars"][PREFIX + "loan_debt"] = 550
        self.assertEqual(world.visible_council_focuses(), set())
        world.run(PREFIX + "check_coup")
        self.assertNotIn(PREFIX + "ultimatum", world.val["missions"])
        world.val["wars"].add("STP")
        world.run(PREFIX + "register_stelander_war")
        self.assertEqual(world.val["missions"][PREFIX + "ultimatum"], 14)
        self.assertEqual(world.visible_council_focuses(), set())
        world.val["wars"].clear()
        world.expire("ultimatum")
        self.assertEqual(world.val["leader"], "VAL_Commanders_Council")
        self.assertEqual(world.val["leader_roles"], dict.fromkeys(
            ("VAL_Gleb_Osten", "VAL_Tamara_Greitz", "VAL_Arkadi_Lemm", "VAL_Mikhail_Velsky"),
            "contractual_etatism",
        ))
        self.assertEqual(world.val["tree"], "VAL_focus")
        self.assertEqual(world.val["vars"][PREFIX + "loan_debt"], 550)
        self.assertIn("VAL_quarterly_contract_active", world.val["flags"])
        self.assertEqual(len(world.visible_council_focuses()), 32)
        self.assertIn("mark_focus_tree_layout_dirty", world.calls)

    def test_ultimatum_cancellation_uses_same_boundary_as_coup(self):
        world = CouncilWorld()
        world.val["flags"] = {PREFIX + "stelander_war_started"}
        world.val["leader"] = "VAL_Valera_Solgalov"
        for balance in (-1, -0.75, -0.70, 0):
            world.val["bop"] = balance
            ready = world.matches(world.triggers[PREFIX + "coup_ready"])
            cancel = world.matches(block(world.decisions[PREFIX + "ultimatum"], "cancel_trigger"))
            self.assertNotEqual(ready, cancel)

    def test_separate_war_does_not_keep_an_obsolete_mandate_open(self):
        world = CouncilWorld()
        world.val["vars"][PREFIX + "mandate_kind"] = 1
        world.val["vars"][PREFIX + "mandate_deposit"] = 250
        world.val["flags"].add(PREFIX + "mandate_active")
        world.val["wars"].add("NOD")
        world.targets[PREFIX + "mandate_enemy"] = "STP"
        world.targets[PREFIX + "mandate_target"] = "176"
        world.run(PREFIX + "daily")
        self.assertNotIn(PREFIX + "mandate_kind", world.val["vars"])
        self.assertEqual(world.balance(), 2187.5)
        self.assertEqual(world.val["pp"], 1000)

    def test_other_administration_loses_powers_but_retains_loan_and_paid_order(self):
        world = CouncilWorld()
        world.choose("borrow_500")
        world.choose("buy_direct_rifles")
        world.val["leader"] = "VAL_party_administration"
        self.assertFalse(world.choose("staff_coordination"))
        self.assertFalse(world.choose("borrow_1000"))
        world.val["vars"][PREFIX + "base_stability"] = 0.05
        world.run(PREFIX + "apply_modifiers")
        self.assertEqual(world.val["vars"].get("VAL_contract_stability_factor", 0), 0)
        self.assertEqual(world.val["vars"][PREFIX + "loan_debt"], 550)
        world.expire("order_arrival")
        world.run(PREFIX + "daily")
        self.assertEqual(sum(world.val["rifles"].values()), 20000)

    def test_real_government_handoff_refreshes_after_promoting_the_administration(self):
        world = CouncilWorld()
        transition = world.effects["VAL_frontier_settle_defeat"]
        branches = [e.value for e in walk(transition) if e.key == "if"]
        payload = next(rows for rows in branches if any(e.key == "promote_character" for e in rows))
        promotion = next(e for e in payload if e.key == "promote_character")
        refresh = next(e for e in payload if e.key == "VAL_refresh_contract_modifier")
        layout = next(e for e in payload if e.key == "mark_focus_tree_layout_dirty")
        self.assertLess(payload.index(promotion), payload.index(refresh))
        self.assertLess(payload.index(promotion), payload.index(layout))
        world.execute([promotion, refresh, layout])
        self.assertEqual(world.val["leader"], "VAL_party_administration")
        self.assertIn("VAL_refresh_contract_modifier", world.calls)
        self.assertFalse(world.matches(world.triggers[PREFIX + "operational"]))
        self.assertEqual(world.visible_council_focuses(), set())
        self.assertIn("mark_focus_tree_layout_dirty", world.calls)


class CouncilTreeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.focuses = {scalar(e.value, "id"): e.value for e in block(entries(FOCUSES), "focus_tree") if e.key == "focus"}

    def visible(self, world, name):
        # A focus's own allow_branch overrides the visibility inherited from its parents.
        body = self.focuses[name]
        gate = next((row.value for row in body if row.key == "allow_branch"), None)
        if gate:
            return world.matches(gate)
        parents = [entry.value for row in body if row.key == "prerequisite" for entry in row.value]
        return all(self.visible(world, parent) for parent in parents)

    def test_chapters_reveal_in_stages_under_either_government(self):
        capstone = "VAL_Contracts_Outlive_Kings"
        later = ("VAL_frontier_conference", "VAL_Northern_Settlement", "VAL_Return_Southern_Tsaygen",
                 "VAL_Bezhaysk_Operation", "VAL_Marine_Contract_Corps", "VAL_Shield_Special_Forces")
        for council in (False, True):
            world = CouncilWorld()
            world.val["leader"] = "VAL_Commanders_Council" if council else "VAL_Valera_Solgalov"
            world.val["focuses"].clear()
            for name in (capstone, *later, "VAL_Occidian_Registries", "VAL_econ_development_fund", "VAL_Naval_Contract_Office"):
                self.assertFalse(self.visible(world, name), (council, name))
            programmes = ("VAL_Industrial_Mobilization_Plan", "VAL_Army_Of_The_Ledger")
            endings = (PREFIX + "charter", PREFIX + "permanent_government", PREFIX + "limited_mandate") if council else ("VAL_State_Contract",)
            for programme in (*programmes, *endings):
                world.val["focuses"] = {programme}
                self.assertTrue(self.visible(world, capstone), (council, programme))
                for name in later:
                    self.assertFalse(self.visible(world, name), (council, programme, name))
                groups = [row.value for row in self.focuses[capstone] if row.key == "prerequisite"]
                self.assertFalse(all(any(e.value in world.val["focuses"] for e in group) for group in groups))
            world.val["focuses"] = {capstone, *programmes, endings[0]}
            for name in later:
                self.assertTrue(self.visible(world, name), (council, name))
            world.val["focuses"] = {"VAL_The_Steel_Contract"}
            self.assertTrue(self.visible(world, "VAL_Occidian_Registries"))
            self.assertFalse(self.visible(world, capstone))

    def test_market_recovery_can_reveal_before_northern_expansion(self):
        market = ("VAL_Reopen_Trade_Routes", "VAL_Settle_Industrial_Debts", "VAL_Return_To_World_Market")
        for council in (False, True):
            world = CouncilWorld()
            world.val["leader"] = "VAL_Commanders_Council" if council else "VAL_Valera_Solgalov"
            world.val["focuses"].clear()
            for name in market:
                self.assertFalse(self.visible(world, name))
            for entry in ("VAL_Returning_Buyers", "VAL_Campaign_Secured"):
                world.val["focuses"] = {entry}
                for name in market:
                    self.assertTrue(self.visible(world, name), (council, entry, name))
                self.assertFalse(self.visible(world, "VAL_frontier_conference"))
                self.assertEqual(self.visible(world, "VAL_Veterans_Of_The_Campaign"), entry == "VAL_Campaign_Secured")

    def test_naval_visibility_survives_new_world_handoff(self):
        world = CouncilWorld()
        for tree in ("VAL_focus", "VAL_new_world_focus"):
            world.val["tree"] = tree
            world.val["focuses"] = {"VAL_Industrial_Mobilization_Plan"}
            for name in ("VAL_Naval_Contract_Office", "VAL_Expedition_Escorts", "VAL_Expedition_Cruisers", "VAL_Expedition_Landing_Staff"):
                self.assertTrue(self.visible(world, name), (tree, name))
            self.assertFalse(self.visible(world, "VAL_Marine_Contract_Corps"))

    def test_choices_are_symmetric_and_all_council_nodes_are_reachable(self):
        council = {key: body for key, body in self.focuses.items() if key.startswith(PREFIX)}
        self.assertEqual(len(council), 32)
        seen = set()
        pairs = set()
        for name, body in council.items():
            for row in body:
                if row.key == "mutually_exclusive":
                    for other in row.value:
                        self.assertIn(name, [e.value for e in block(council[other.value], "mutually_exclusive")])
                        pairs.add(tuple(sorted((name, other.value))))
        self.assertEqual(len(pairs), 8)
        for chosen in itertools.product(*sorted(pairs)):
            excluded = {item for pair in pairs for item in pair} - set(chosen)
            complete = set(self.focuses) - set(council)
            while True:
                available = {name for name, body in council.items() if name not in excluded and all(any(e.value in complete for e in row.value) for row in body if row.key == "prerequisite")}
                if available <= complete:
                    break
                complete |= available
            seen |= complete & set(council)
        self.assertEqual(seen, set(council))

    def test_capstone_joins_political_alternatives_but_requires_army_and_economy(self):
        groups = [{e.value for e in row.value} for row in self.focuses["VAL_Contracts_Outlive_Kings"] if row.key == "prerequisite"]
        self.assertCountEqual(groups, [
            {"VAL_State_Contract", PREFIX + "charter", PREFIX + "permanent_government", PREFIX + "limited_mandate"},
            {"VAL_Industrial_Mobilization_Plan"}, {"VAL_Army_Of_The_Ledger"},
        ])

    def test_no_unregistered_focus_references(self):
        for body in self.focuses.values():
            for row in body:
                if row.key in ("prerequisite", "mutually_exclusive"):
                    self.assertTrue(all(e.value in self.focuses for e in row.value))

    def test_naval_entry_is_earned_before_handoff_and_landing_staff_has_two_routes(self):
        def requires(name, target):
            if name == target:
                return True
            groups = [row.value for row in self.focuses[name] if row.key == "prerequisite"]
            return any(all(requires(parent.value, target) for parent in group) for group in groups)

        industry = "VAL_Industrial_Mobilization_Plan"
        self.assertTrue(requires("VAL_Naval_Contract_Office", industry))
        self.assertTrue(requires("VAL_Return_To_World_Market", industry))
        self.assertTrue(requires("VAL_Expedition_Landing_Staff", "VAL_Expedition_Escorts"))
        preparation = block(block(self.focuses["VAL_Expedition_Landing_Staff"], "available"), "OR")
        self.assertEqual({row.value for row in preparation}, {"VAL_Contract_Landing_Craft", "VAL_nw_staff"})
        for completed in (None, "VAL_Contract_Landing_Craft", "VAL_nw_staff"):
            world = CouncilWorld()
            if completed:
                world.val["focuses"].add(completed)
            self.assertEqual(any(world.matches([row]) for row in preparation), completed is not None)

    def test_missions_cannot_auto_succeed_and_dynamic_reads_are_registered(self):
        world = CouncilWorld()
        # The Iron Shield goal is a real target; its focus opens only while one target is still held by the enemy.
        world.data["43"]["controller"] = world.data["44"]["controller"] = "STP"
        world.val["wars"].add("STP")
        world.data["STP"]["wars"].add("VAL")
        tokens = (ROOT / "common/synchronized_dynamic_tokens/ADISCORD_tokens.txt").read_text().splitlines()
        for name, body in world.decisions.items():
            if any(e.key == "days_mission_timeout" for e in body):
                self.assertFalse(world.matches(block(body, "available")), name)
                self.assertIn(name, tokens)

    def test_preview_ideas_are_not_installed_and_localisation_is_loadable(self):
        required = set()
        definitions = entries("common/scripted_localisation/ADISCORD_VAL_contract_scripted_loc.txt")
        scripted_names = {scalar(row.value, "name") for row in definitions if row.key == "defined_text"}
        decisions = CouncilWorld().decisions
        for name in decisions:
            required.update((name, name + "_desc"))
        for name in self.focuses:
            if name.startswith(PREFIX):
                required.update((name, name + "_desc"))
        categories = entries("common/decisions/categories/ADISCORD_VAL_rework_categories.txt")
        for row in categories:
            if row.key.startswith(PREFIX):
                required.update((row.key, row.key + "_desc"))
        for path in (
            DECISIONS, TRIGGERS, EFFECTS, FOCUSES,
            "events/ADISCORD_VAL_contract_events.txt",
            "common/scripted_localisation/ADISCORD_VAL_contract_scripted_loc.txt",
        ):
            for row in walk(entries(path)):
                if not isinstance(row.value, str) or "council" not in row.value.lower():
                    continue
                if row.key in ("custom_cost_text", "tooltip", "custom_effect_tooltip", "localization_key", "title", "desc"):
                    required.add(row.value)
                if row.key == "custom_cost_text":
                    required.update((row.value + "_blocked", row.value + "_tooltip"))
                if row.key == "name" and row.value.startswith("val_council."):
                    required.add(row.value)
        for language in ("russian", "english"):
            path = ROOT / f"localisation/{language}/ADISCORD_VAL_decisions_l_{language}.yml"
            self.assertTrue(path.read_bytes().startswith(b"\xef\xbb\xbf"))
            text = path.read_text(encoding="utf-8-sig")
            keys = set(re.findall(r"(?m)^\s*([\w.]+):", text))
            self.assertFalse(required - keys, (language, sorted(required - keys)))
            authored = text.split("# --- commanders_council ---", 1)[1]
            self.assertNotRegex(authored, "[\u2013\u2014]")
            seen = set()
            for line in authored.splitlines():
                if not line.strip() or line.lstrip().startswith("#"):
                    continue
                self.assertRegex(line, r'^ [\w.]+:0 "(?:[^"\\]|\\.)*"$')
                key = line.split(":", 1)[0].strip()
                self.assertNotIn(key, seen, (language, key))
                seen.add(key)
                for substitution in re.findall(r"\[(VALGetCouncil\w+)\]", line):
                    self.assertIn(substitution, scripted_names, (language, key))
                for substitution in re.findall(r"\$(\w+)\$", line):
                    if "council" in substitution.lower():
                        self.assertIn(substitution, keys, (language, key))
            for event in range(1, 11):
                desc = re.search(rf'^ val_council\.{event}\.d:0 "(.*)"$', authored, re.M).group(1).replace("\\n", "\n")
                self.assertLessEqual(len(desc), 3000)
                self.assertLessEqual(len(desc.encode("utf-8")), 5500)
        effects = (ROOT / EFFECTS).read_text(encoding="utf-8")
        self.assertNotRegex(effects, r"add_ideas\s*=\s*VAL_council_\w+_delta")

    def test_previews_equal_executed_council_modifier_changes(self):
        ideas = {e.key: e.value for e in block(block(entries("common/ideas/ADISCORD_VAL_rework_ideas.txt"), "ideas"), "country")}
        native = {e.value: e.key for e in block(entries("common/dynamic_modifiers/ADISCORD_VAL_contract_dynamic_modifier.txt"), "VAL_contract_state") if isinstance(e.value, str)}
        for focus, choice, preview in (
            ("captains_agreement", None, "agreement"),
            ("charter", "equal_votes", "equal_charter"),
            ("charter", "large_companies", "large_charter"),
            ("permanent_government", None, "permanent"),
            ("limited_mandate", None, "limited"),
            ("public_commission", None, "public_shock"),
            ("equal_votes", None, "equal_votes"),
            ("large_companies", None, "large_companies"),
            ("supreme_command", None, "supreme_command"),
            ("state_inspectors", None, "inspectors_first"),
            ("supplier_consortium", None, "consortium"),
            ("officer_inquiry", None, "officer_inquiry"),
            ("publish_losses", None, "families_first"),
        ):
            with self.subTest(focus=focus, choice=choice):
                world = CouncilWorld()
                if choice:
                    world.val["focuses"].add(PREFIX + choice)
                world.execute(block(self.focuses[PREFIX + focus], "completion_reward"))
                world.run(PREFIX + "apply_modifiers")
                actual = {native[key]: value for key, value in world.val["vars"].items() if key in native and value != 0}
                expected = {e.key: float(e.value) for e in block(ideas[PREFIX + preview + "_delta"], "modifier")}
                self.assertEqual(actual, expected)

    def test_hidden_branch_does_not_hide_shared_routes_and_both_layouts_fit(self):
        world = CouncilWorld()
        common = ("VAL_One_Ledger_One_Banner", "VAL_Quarterly_Contract_Norm", "VAL_Provincial_Contract_Courts")

        for council in (False, True):
            world.val["leader"] = "VAL_Commanders_Council" if council else "VAL_Valera_Solgalov"
            for name in common:
                self.assertTrue(self.visible(world, name), (council, name))
            for name in PERSONAL_FOCUSES:
                self.assertEqual(self.visible(world, name), not council, (council, name))
            positions = {}
            for name, body in self.focuses.items():
                if name.startswith(PREFIX) and not council:
                    self.assertFalse(self.visible(world, name))
                    continue
                if name in PERSONAL_FOCUSES and council:
                    continue
                x, y = int(scalar(body, "x")), int(scalar(body, "y"))
                for offset in (row.value for row in body if row.key == "offset"):
                    if world.matches(block(offset, "trigger")):
                        x += int(scalar(offset, "x"))
                        y += int(scalar(offset, "y"))
                self.assertNotIn((x, y), positions, (council, name, positions.get((x, y))))
                positions[x, y] = name
            if not council:
                self.assertLessEqual(max(x for x, y in positions) - min(x for x, y in positions), 64)
                self.assertEqual(positions[32, 0], "VAL_The_Contract_State")
            else:
                self.assertEqual(positions[44, 0], "VAL_The_Contract_State")

    def test_factory_rechecks_capital_and_pays_cash_when_no_site_survives(self):
        reward = block(self.focuses[PREFIX + "direct_orders"], "completion_reward")
        for case in ("valid", "occupied", "foreign", "not_core", "full"):
            with self.subTest(case=case):
                world = CouncilWorld()
                capital = world.data["176"]
                if case == "occupied":
                    capital["controller"] = "STP"
                elif case == "foreign":
                    capital["owner"] = "STP"
                elif case == "not_core":
                    capital["cores"].clear()
                elif case == "full":
                    capital["free_slots"] = 0
                world.execute(reward)
                self.assertEqual(capital["buildings"]["arms_factory"], int(case == "valid"))
                self.assertEqual(capital["slots"], int(case == "valid"))
                self.assertEqual(world.balance(), 2000 if case == "valid" else 2450)
                if case != "valid":
                    self.assertEqual(world.val["vars"]["ADISCORD_economy_current_month_action_income"], 450)
                    self.assertIn("VAL", world.dirty)

    def test_audit_settlement_default_cash_and_stale_choices_conserve_receipt(self):
        event = next(e.value for e in entries("events/ADISCORD_VAL_contract_events.txt") if e.key == "country_event" and scalar(e.value, "id") == "val_council.9")
        options = [row.value for row in event if row.key == "option"]
        self.assertEqual(scalar(options[0], "name"), "val_council.9.a")
        self.assertFalse(any(row.key == "default_option" for row in walk(entries("events/ADISCORD_VAL_contract_events.txt"))))
        for choice in (0, 1):
            world = CouncilWorld()
            world.execute(block(self.focuses[PREFIX + "contract_review"], "completion_reward"))
            world.val["leader"] = "VAL_party_administration"
            world.val["focuses"].add(PREFIX + "brokers")
            self.assertTrue(world.matches(block(options[choice], "trigger")))
            payload = lambda option: [row for row in option if row.key not in {"name", "trigger", "ai_chance", "default_option"}]
            world.execute(payload(options[choice]))
            world.execute(payload(options[0]))
            world.execute(payload(options[1]))
            self.assertNotIn(PREFIX + "audit_receivable", world.val["vars"])
            self.assertTrue(world.matches(block(options[2], "trigger")))
            self.assertEqual(sum(world.val["rifles"].values()), 15000 if choice == 0 else 5000)
            self.assertEqual(sum(world.val.get("motorized_equipment", {}).values()), 100 if choice == 0 else 0)
            self.assertEqual(world.balance(), 2000 if choice == 0 else 2350)

    def test_first_programmes_expire_and_public_oversight_remains(self):
        for focus, flag, timer, repeat in (
            ("state_inspectors", "inspection_savings", "inspection_savings_timer", "inspect_accounts"),
            ("publish_losses", "family_support", "family_support_timer", "support_families"),
            ("council_inspection", "prevention", "prevention_timer", "preventive_review"),
        ):
            with self.subTest(focus=focus):
                world = CouncilWorld()
                world.execute(block(self.focuses[PREFIX + focus], "completion_reward"))
                self.assertIn(PREFIX + flag, world.val["flags"])
                self.assertEqual(world.val["missions"][PREFIX + timer], 90)
                self.assertFalse(world.matches(block(world.decisions[PREFIX + repeat], "available")))
                world.expire(timer)
                self.assertNotIn(PREFIX + flag, world.val["flags"])
                self.assertTrue(world.matches(block(world.decisions[PREFIX + repeat], "available")))
        world = CouncilWorld()
        world.execute(block(self.focuses[PREFIX + "public_commission"], "completion_reward"))
        self.assertEqual(world.val["missions"][PREFIX + "public_shock_timer"], 60)
        world.expire("public_shock_timer")
        world.run(PREFIX + "apply_modifiers")
        self.assertEqual(world.val["vars"]["VAL_contract_army_expense_factor"], -0.03)
        self.assertEqual(world.val["vars"]["VAL_contract_stability_factor"], 0)

    def test_debug_routes_use_real_coup_and_publish_world_news_once(self):
        category = block(entries(DECISIONS), "VAL_rework_debug")
        decisions = {row.key: row.value for row in category if row.key.startswith("VAL_debug_council_")}
        self.assertEqual(len(decisions), 3)
        world = CouncilWorld()
        world.val["flags"].discard(PREFIX + "in_power")
        world.val["leader"] = "VAL_Valera_Solgalov"
        discontent = decisions["VAL_debug_council_discontent"]
        world.execute(block(discontent, "complete_effect"))
        self.assertIsNone(world.val["bop"])
        world.debug = True
        world.execute(block(discontent, "complete_effect"))
        self.assertEqual(world.val["bop"], -0.9)
        self.assertNotIn(PREFIX + "ultimatum", world.val["missions"])
        world.execute(block(decisions["VAL_debug_council_ultimatum"], "complete_effect"))
        self.assertEqual(world.val["missions"][PREFIX + "ultimatum"], 14)
        self.assertEqual(world.val["leader"], "VAL_Valera_Solgalov")
        world.val["vars"][PREFIX + "loan_debt"] = 550
        world.execute(block(decisions["VAL_debug_council_take_power"], "complete_effect"))
        self.assertEqual(world.val["leader"], "VAL_Commanders_Council")
        self.assertEqual(world.val["vars"][PREFIX + "loan_debt"], 550)
        self.assertEqual(len(world.visible_council_focuses()), 32)
        world.execute(block(decisions["VAL_debug_council_take_power"], "complete_effect"))
        self.assertEqual(world.events.count(("VAL", "val_council.10")), 1)
        news = next(e.value for e in entries("events/ADISCORD_VAL_contract_events.txt") if e.key == "news_event" and scalar(e.value, "id") == "val_council.10")
        self.assertEqual(scalar(news, "major"), "yes")
        self.assertEqual(scalar(news, "fire_only_once"), "yes")

    def test_ai_finishes_alternative_routes_without_choosing_both_sides(self):
        for selected, continuing in (
            ("captains_agreement", ("company_delegates", "equal_votes", "arbitration", "mutual_guarantees", "charter")),
            ("large_companies", ("arbitration", "charter")),
            ("public_commission", ("publish_losses", "recall_right", "limited_mandate")),
            ("brokers", ("supplier_consortium", "common_fund")),
            ("direct_orders", ("staff_acceptance", "common_fund")),
        ):
            world = CouncilWorld()
            world.val["focuses"].add(PREFIX + selected)
            for name in continuing:
                weights = block(self.focuses[PREFIX + name], "ai_will_do")
                score = float(scalar(weights, "base"))
                for modifier in (row.value for row in weights if row.key == "modifier"):
                    conditions = [row for row in modifier if row.key not in ("factor", "add")]
                    if world.matches(conditions):
                        for row in modifier:
                            if row.key == "factor":
                                score *= float(row.value)
                            elif row.key == "add":
                                score += float(row.value)
                self.assertGreater(score, 0, (selected, name))
        plan = block(entries("common/ai_strategy_plans/ADISCORD_VAL_plans.txt"), PREFIX + "government_plan")
        priorities = [e.value for e in block(plan, "ai_national_focuses")]
        self.assertNotIn(PREFIX + "permanent_government", priorities)
        self.assertNotIn(PREFIX + "limited_mandate", priorities)


class CouncilRepresentationTests(unittest.TestCase):
    CAMPS = ("garrison", "front", "supply")

    @classmethod
    def setUpClass(cls):
        cls.root = next(row.value for row in block(entries(FOCUSES), "focus_tree")
                        if row.key == "focus" and scalar(row.value, "id") == PREFIX + "takes_command")

    def seats(self, world):
        return tuple(world.val["vars"].get(PREFIX + "seats_" + camp, 0) for camp in self.CAMPS)

    def set_seats(self, world, values):
        world.val["vars"].update({PREFIX + "seats_" + camp: value for camp, value in zip(self.CAMPS, values)})

    def transfer(self, world, side, delta):
        world.val["vars"].update({PREFIX + "seat_side": side, PREFIX + "seat_delta": delta})
        world.run(PREFIX + "transfer_seat")

    def mandate_world(self, kind, course=None):
        world = CouncilWorld()
        world.val["focuses"].add(PREFIX + "takes_command")
        if kind == "offensive":
            world.val["focuses"].add(PREFIX + "war_plan")
        if course:
            world.val["focuses"].add(PREFIX + course)
        if kind == "supply":
            world.val["flags"].add("VAL_quarterly_contract_active")
            world.val["missions"]["VAL_quarterly_contract_deadline"] = 70
        else:
            world.val["wars"].add("STP")
            world.data["STP"]["wars"].add("VAL")
            world.data["176"]["neighbors"] = ["177"]
            world.data["176"]["controller"] = "VAL" if kind == "defence" else "STP"
            world.data["177"]["controller"] = "STP" if kind == "defence" else "VAL"
        return world

    def assert_mandate_closed(self, world):
        self.assertNotIn(PREFIX + "mandate_kind", world.val["vars"])
        self.assertNotIn(PREFIX + "mandate_deposit", world.val["vars"])
        for suffix in ("mandate_active", "mandate_expired", "mandate_extended", "supply_fulfilled"):
            self.assertNotIn(PREFIX + suffix, world.val["flags"])
        for suffix in ("mandate_approval", "mandate_deadline"):
            self.assertNotIn(PREFIX + suffix, world.val["missions"])
        self.assertIn(PREFIX + "mandate_cooldown", world.val["flags"])
        self.assertFalse(world.matches(world.triggers[PREFIX + "mandate_slot_free"]))

    def test_every_seat_distribution_preserves_total_and_uses_a_real_rival(self):
        world = CouncilWorld()
        for garrison in range(7):
            for front in range(7 - garrison):
                before = (garrison, front, 6 - garrison - front)
                for side, delta in itertools.product(range(1, 4), (-1, 1)):
                    self.set_seats(world, before)
                    self.transfer(world, side, delta)
                    after = self.seats(world)
                    with self.subTest(before=before, side=side, delta=delta):
                        self.assertEqual(sum(after), 6)
                        self.assertTrue(all(0 <= count <= 6 for count in after))
                        blocked = before[side - 1] == (6 if delta == 1 else 0)
                        if blocked:
                            self.assertEqual(after, before)
                        else:
                            rival = max((i for i in range(3) if i != side - 1), key=lambda i: (before[i], -i))
                            expected = list(before)
                            expected[side - 1] += delta
                            expected[rival] -= delta
                            self.assertEqual(after, tuple(expected))

    def test_initialization_preserves_real_receipts_across_governments_and_settlement(self):
        for settlement in ("delivery", "cancel"):
            with self.subTest(settlement=settlement):
                world = CouncilWorld()
                self.assertEqual(self.seats(world), (2, 2, 2))
                self.set_seats(world, (1, 4, 1))
                self.assertTrue(world.choose("borrow_500"))
                self.assertTrue(world.choose("buy_direct_rifles"))
                for tree, subject, leader in (
                    ("VAL_defeated_focus", "STP", "VAL_party_administration"),
                    ("VAL_new_world_focus", None, "VAL_Commanders_Council"),
                ):
                    world.val.update(tree=tree, subject=subject, leader=leader)
                    world.execute(block(self.root, "completion_reward"))
                    world.run(PREFIX + "daily")
                    self.assertEqual(self.seats(world), (1, 4, 1))
                    self.assertEqual(world.val["vars"][PREFIX + "loan_debt"], 550)
                    self.assertEqual(world.val["vars"][PREFIX + "order_paid"], 450)
                    self.assertEqual(world.balance(), 2050)
                if settlement == "cancel":
                    self.assertTrue(world.choose("cancel_purchase"))
                    world.choose("cancel_purchase", stale=True)
                world.expire("order_arrival")
                world.run(PREFIX + "daily")
                world.run(PREFIX + "daily")
                self.assertEqual(world.balance(), 2387.5 if settlement == "cancel" else 2050)
                self.assertEqual(sum(world.val["rifles"].values()), 5000 if settlement == "cancel" else 20000)
                self.assertNotIn(PREFIX + "order_paid", world.val["vars"])
                self.assertEqual(world.val["vars"][PREFIX + "loan_debt"], 550)
                self.assertEqual(self.seats(world), (1, 4, 1))

    def test_lost_defence_target_during_approval_settles_once(self):
        world = self.mandate_world("defence")
        self.assertTrue(world.choose("mandate_defence_ordinary"))
        self.assertEqual(world.targets[PREFIX + "mandate_enemy"], "STP")
        world.data["176"]["controller"] = "STP"
        world.run(PREFIX + "daily")
        self.assert_mandate_closed(world)
        self.assertEqual(self.seats(world), (1, 3, 2))
        self.assertEqual(world.val["stability"], 0.47)
        self.assertEqual(world.val["pp"], 980)
        world.data["176"]["controller"] = "VAL"
        world.expire("mandate_approval")
        world.expire("mandate_deadline")
        world.run(PREFIX + "daily")
        self.assert_mandate_closed(world)
        self.assertEqual(self.seats(world), (1, 3, 2))
        self.assertEqual(world.val["stability"], 0.47)
        self.assertEqual(world.val["pp"], 980)

    def test_supply_paid_before_approval_settles_once_without_moving_the_quarter(self):
        for payment in ("reserve_quarter", "consortium_norm"):
            with self.subTest(payment=payment):
                world = self.mandate_world("supply")
                world.val["rifles"] = {"VAL": 50000}
                self.assertTrue(world.choose("mandate_supply_ordinary"))
                if payment == "reserve_quarter":
                    self.assertTrue(world.choose("reserve_rifles"))
                self.assertTrue(world.choose(payment))
                self.assertIn(PREFIX + "supply_fulfilled", world.val["flags"])
                self.assertEqual(self.seats(world), (2, 2, 2))
                self.assertIn(PREFIX + "mandate_approval", world.val["missions"])
                paid = world.balance(), world.val["pp"], sum(world.val["rifles"].values())
                world.choose(payment, stale=True)
                self.assertEqual((world.balance(), world.val["pp"], sum(world.val["rifles"].values())), paid)
                world.expire("mandate_approval")
                world.run(PREFIX + "reconcile_mandate")
                world.expire("mandate_approval")
                self.assert_mandate_closed(world)
                self.assertEqual(self.seats(world), (1, 2, 3))
                self.assertEqual(world.val["pp"], paid[1] + 25)
                self.assertEqual(world.balance(), paid[0])
                self.assertEqual(world.val["missions"]["VAL_quarterly_contract_deadline"], 70)

    def test_loss_of_independence_or_capitulation_closes_each_mandate_phase(self):
        for phase, disruption in itertools.product(("approval", "active"), ("subject", "capitulated")):
            with self.subTest(phase=phase, disruption=disruption):
                world = self.mandate_world("defence", "equal_votes")
                world.val["focuses"].add(PREFIX + "mutual_guarantees")
                self.set_seats(world, (1, 4, 1))
                self.assertTrue(world.choose("borrow_500"))
                self.assertTrue(world.choose("buy_direct_rifles"))
                self.assertTrue(world.choose("mandate_defence_priority"))
                self.assertFalse(world.choose("guarantee_mandate"))
                refund = 0
                if phase == "active":
                    world.expire("mandate_approval")
                    self.assertTrue(world.choose("guarantee_mandate"))
                    self.assertEqual(world.val["vars"][PREFIX + "mandate_deposit"], 250)
                    refund = 187.5
                paid_balance = world.balance()
                world.val[disruption] = "STP" if disruption == "subject" else True
                world.val["tree"] = "VAL_defeated_focus"
                world.run(PREFIX + "daily")
                world.run(PREFIX + "daily")
                self.assert_mandate_closed(world)
                self.assertEqual(world.balance(), paid_balance + refund)
                self.assertEqual(world.val["vars"][PREFIX + "loan_debt"], 550)
                self.assertEqual(world.val["vars"][PREFIX + "order_paid"], 450)
                self.assertEqual(self.seats(world), (1, 4, 1))
                world.val.update(subject=None, capitulated=False, tree="VAL_focus")
                world.execute(block(self.root, "completion_reward"))
                world.expire("mandate_approval")
                world.expire("mandate_deadline")
                world.run(PREFIX + "daily")
                self.assert_mandate_closed(world)
                self.assertEqual(world.balance(), paid_balance + refund)
                self.assertEqual(self.seats(world), (1, 4, 1))
                world.expire("order_arrival")
                world.run(PREFIX + "daily")
                world.run(PREFIX + "daily")
                self.assertEqual(sum(world.val["rifles"].values()), 20000)
                self.assertEqual(world.balance(), paid_balance + refund)
                self.assertEqual(world.val["vars"][PREFIX + "loan_debt"], 550)

    def test_all_mandate_variants_have_exact_prices_visibility_and_single_payment(self):
        for course, kind, values in itertools.product(
            (None, "equal_votes", "large_companies"),
            ("defence", "offensive", "supply"),
            ((2, 2, 2), (4, 1, 1), (1, 4, 1), (1, 1, 4)),
        ):
            with self.subTest(course=course, kind=kind, seats=values):
                world = self.mandate_world(kind, course)
                self.set_seats(world, values)
                priority = (course == "equal_votes" and kind != "offensive") or (course == "large_companies" and kind == "offensive")
                variant = "ordinary" if course is None else "priority" if priority else "contested"
                price = {"ordinary": 20, "priority": 10, "contested": 35}[variant]
                suffix = "mandate_" + kind + "_" + variant
                for alternative in ("ordinary", "priority", "contested"):
                    body = world.decisions[PREFIX + "mandate_" + kind + "_" + alternative]
                    self.assertEqual(world.matches(block(body, "visible")), alternative == variant)
                body = world.decisions[PREFIX + suffix]
                self.assertEqual(scalar(body, "cost"), "0")
                world.val["pp"] = price - 0.01
                self.assertFalse(world.matches(block(body, "custom_cost_trigger")))
                self.assertFalse(world.choose(suffix))
                world.choose(suffix, stale=True)
                self.assertEqual(world.val["pp"], price - 0.01)
                self.assertNotIn(PREFIX + "mandate_kind", world.val["vars"])
                world.val["pp"] = price
                self.assertTrue(world.matches(block(body, "custom_cost_trigger")))
                self.assertTrue(world.choose(suffix))
                self.assertEqual(world.val["pp"], 0)
                side = ("defence", "offensive", "supply").index(kind)
                delay = 7 if values[side] >= 4 else 21 if max(values) >= 4 else 14
                self.assertEqual(world.val["missions"][PREFIX + "mandate_approval"], delay)
                world.val["pp"] = 100
                world.val["missions"][PREFIX + "mandate_approval"] -= 1
                world.choose(suffix, stale=True)
                self.assertEqual(world.val["pp"], 100)
                self.assertEqual(world.val["missions"][PREFIX + "mandate_approval"], delay - 1)

    def test_root_keeps_defence_and_supply_while_war_plan_opens_offensives(self):
        world = CouncilWorld()
        unlocks = {row.value for row in block(self.root, "completion_reward") if row.key == "unlock_decision_tooltip"}
        expected = {PREFIX + "mandate_" + kind + "_ordinary" for kind in ("defence", "supply")}
        self.assertTrue(expected <= unlocks)
        offensive = PREFIX + "mandate_offensive_ordinary"
        self.assertNotIn(offensive, unlocks)
        plan = next(row.value for row in block(entries(FOCUSES), "focus_tree")
                    if row.key == "focus" and scalar(row.value, "id") == PREFIX + "war_plan")
        self.assertIn(offensive, {row.value for row in walk(block(plan, "completion_reward"))
                                 if row.key == "unlock_decision_tooltip"})
        for course in ("captains_agreement", "supreme_command"):
            world.val["focuses"] = {PREFIX + "takes_command", PREFIX + course}
            for name in expected:
                self.assertTrue(world.matches(block(world.decisions[name], "visible")), (course, name))
            self.assertFalse(world.matches(block(world.decisions[offensive], "visible")))
            world.val["focuses"].add(PREFIX + "war_plan")
            self.assertTrue(world.matches(block(world.decisions[offensive], "visible")))

    def test_offensive_mandates_cannot_be_paid_before_the_war_plan(self):
        for course, variant, price in ((None, "ordinary", 20), ("large_companies", "priority", 10), ("equal_votes", "contested", 35)):
            with self.subTest(course=course):
                world = self.mandate_world("offensive", course)
                world.val["focuses"].discard(PREFIX + "war_plan")
                decision = world.decisions[PREFIX + "mandate_offensive_" + variant]
                self.assertFalse(world.matches(block(decision, "visible")))
                world.execute(block(decision, "complete_effect"))
                self.assertEqual(world.val["pp"], 1000)
                self.assertNotIn(PREFIX + "mandate_kind", world.val["vars"])
                world.val["focuses"].add(PREFIX + "war_plan")
                self.assertTrue(world.matches(block(decision, "visible")))
                self.assertTrue(world.choose("mandate_offensive_" + variant))
                self.assertEqual(world.val["pp"], 1000 - price)
                self.assertEqual(world.val["vars"][PREFIX + "mandate_kind"], 2)
                self.assertEqual(world.val["missions"][PREFIX + "mandate_approval"], 14)

    def test_war_plan_unlock_remains_obtainable_after_stelander_peace(self):
        world = CouncilWorld()
        world.val["focuses"].add(PREFIX + "takes_command")
        plan = next(row.value for row in block(entries(FOCUSES), "focus_tree")
                    if row.key == "focus" and scalar(row.value, "id") == PREFIX + "war_plan")
        self.assertTrue(world.matches(block(plan, "available")))
        bypass = [row for row in plan if row.key == "bypass"]
        self.assertFalse(bypass and world.matches(bypass[0].value))

    def test_approval_uses_current_majority_and_keeps_the_paid_delay(self):
        world = CouncilWorld()
        for values in ((2, 2, 2), (4, 1, 1), (1, 4, 1), (0, 0, 6), (3, 3, 0)):
            for side in range(1, 4):
                self.set_seats(world, values)
                world.val["vars"][PREFIX + "mandate_kind"] = side
                world.run(PREFIX + "schedule_approval")
                expected = 7 if values[side - 1] >= 4 else 21 if max(values) >= 4 else 14
                self.assertEqual(world.val["missions"][PREFIX + "mandate_approval"], expected)
                self.transfer(world, side, -1)
                self.assertEqual(world.val["missions"][PREFIX + "mandate_approval"], expected)
        self.set_seats(world, (4, 2, 0))
        self.transfer(world, 1, -1)
        self.assertEqual(self.seats(world), (3, 3, 0))
        world.run(PREFIX + "schedule_approval")
        self.assertEqual(world.val["missions"][PREFIX + "mandate_approval"], 14)

    def test_real_settlements_transfer_once_and_cancellation_transfers_nothing(self):
        for suffix, expected in (("mandate_success", (1, 3, 2)), ("mandate_failed", (3, 1, 2)), ("withdraw_mandate", (2, 2, 2))):
            world = CouncilWorld()
            world.val["vars"][PREFIX + "mandate_kind"] = 2
            world.val["vars"][PREFIX + "mandate_deposit"] = 250
            world.run(PREFIX + suffix)
            balance = world.balance()
            world.run(PREFIX + suffix)
            self.assertEqual(self.seats(world), expected)
            self.assertEqual(world.balance(), balance)
            self.assertNotIn(PREFIX + "mandate_kind", world.val["vars"])

    def test_each_loan_defaults_once_even_at_six_seats_and_repayment_keeps_votes(self):
        world = CouncilWorld()
        world.val["vars"][PREFIX + "loan_debt"] = 550
        world.run(PREFIX + "register_loan_default")
        self.assertEqual(self.seats(world), (1, 2, 3))
        for _ in range(3):
            world.run(PREFIX + "register_loan_default")
        self.assertEqual(self.seats(world), (1, 2, 3))
        world.choose("repay_loan")
        self.assertEqual(self.seats(world), (1, 2, 3))
        world.choose("borrow_500")
        world.run(PREFIX + "register_loan_default")
        self.assertEqual(self.seats(world), (1, 1, 4))
        self.set_seats(world, (0, 0, 6))
        world.val["flags"].discard(PREFIX + "loan_default")
        world.run(PREFIX + "register_loan_default")
        self.transfer(world, 1, 1)
        world.run(PREFIX + "register_loan_default")
        self.assertEqual(self.seats(world), (1, 0, 5))

    def test_arbitration_exact_cost_duplicate_click_and_shared_cooldown(self):
        world = CouncilWorld()
        world.val["focuses"].add(PREFIX + "arbitration")
        world.val["flags"].add(PREFIX + "case_open")
        world.val["pp"] = 50
        world.val["vars"]["ADISCORD_economy_treasury"] = 200
        for pp, cash in ((49.99, 200), (50, 199.99)):
            world.val["pp"] = pp
            world.val["vars"]["ADISCORD_economy_treasury"] = cash
            self.assertFalse(world.choose("arbitrate_front"))
            world.choose("arbitrate_front", stale=True)
            self.assertEqual(self.seats(world), (2, 2, 2))
            self.assertEqual((world.val["pp"], world.balance()), (pp, cash))
        world.val["pp"] = 50
        world.val["vars"]["ADISCORD_economy_treasury"] = 200
        self.assertTrue(world.choose("arbitrate_front"))
        self.assertEqual(self.seats(world), (1, 3, 2))
        self.assertEqual((world.val["pp"], world.balance()), (0, 0))
        world.val["flags"].add(PREFIX + "case_open")
        world.val["pp"] = 100
        world.val["vars"]["ADISCORD_economy_treasury"] = 500
        for camp in self.CAMPS:
            self.assertFalse(world.choose("arbitrate_" + camp))
            world.choose("arbitrate_" + camp, stale=True)
        self.assertEqual(self.seats(world), (1, 3, 2))
        self.assertEqual((world.val["pp"], world.balance()), (100, 500))
        world.val["flags"].discard(PREFIX + "seat_arbitration_cooldown")
        self.set_seats(world, (6, 0, 0))
        self.assertFalse(world.choose("arbitrate_garrison"))
        world.choose("arbitrate_garrison", stale=True)
        self.assertEqual((world.val["pp"], world.balance()), (100, 500))

    def test_ui_majority_delays_and_donor_follow_the_same_seats(self):
        definitions = {scalar(row.value, "name"): row.value for row in entries("common/scripted_localisation/ADISCORD_VAL_contract_scripted_loc.txt") if row.key == "defined_text"}
        world = CouncilWorld()
        def text(name):
            for row in definitions[name]:
                conditions = next((entry.value for entry in row.value if entry.key == "trigger"), []) if row.key == "text" else []
                if row.key == "text" and world.matches(conditions):
                    return scalar(row.value, "localization_key")
            self.fail(name)
        world.val["flags"].discard(PREFIX + "seats_initialized")
        self.assertEqual(text("VALGetCouncilRepresentation"), "VAL_COUNCIL_SEATS_PENDING")
        world.val["flags"].add(PREFIX + "seats_initialized")
        self.assertEqual(text("VALGetCouncilRepresentation"), "VAL_COUNCIL_REPRESENTATION")
        for pp, cash, pp_key, cash_key in (
            (50, 200, "VAL_COUNCIL_PP50_READY", "VAL_COUNCIL_CASH200_READY"),
            (49.99, 200, "VAL_COUNCIL_PP50_BLOCKED", "VAL_COUNCIL_CASH200_READY"),
            (50, 199.99, "VAL_COUNCIL_PP50_READY", "VAL_COUNCIL_CASH200_BLOCKED"),
        ):
            world.val["pp"] = pp
            world.val["vars"]["ADISCORD_economy_treasury"] = cash
            self.assertEqual(text("VALGetCouncilArbitrationPoliticalCost"), pp_key)
            self.assertEqual(text("VALGetCouncilArbitrationTreasuryCost"), cash_key)
        for values in ((2, 2, 2), (1, 4, 1), (0, 0, 6), (3, 3, 0)):
            self.set_seats(world, values)
            leader = next((i for i, count in enumerate(values) if count >= 4), None)
            self.assertEqual(text("VALGetCouncilMajority"), "VAL_COUNCIL_NO_MAJORITY" if leader is None else "VAL_COUNCIL_" + self.CAMPS[leader].upper())
            for i, kind in enumerate(("Defence", "Offensive", "Supply")):
                expected = 14 if leader is None else 7 if leader == i else 21
                self.assertEqual(text("VALGetCouncil" + kind + "Approval"), "VAL_COUNCIL_APPROVAL_" + str(expected))
                donors = [j for j in range(3) if j != i and values[j] > 0]
                donor = max(donors, key=lambda j: (values[j], -j)) if donors else None
                self.assertEqual(text("VALGetCouncil" + kind + "Donor"), "VAL_COUNCIL_NO_DONOR" if donor is None else "VAL_COUNCIL_" + self.CAMPS[donor].upper())


class CouncilStoryTests(unittest.TestCase):
    """Delegation plans, favours, demands and the regime endings share the seat ledger."""

    @staticmethod
    def seats(world):
        return tuple(world.val["vars"][PREFIX + "seats_" + camp] for camp in ("garrison", "front", "supply"))

    @staticmethod
    def set_seats(world, values):
        for camp, count in zip(("garrison", "front", "supply"), values):
            world.val["vars"][PREFIX + "seats_" + camp] = count

    def war_world(self):
        world = CouncilWorld()
        world.val["wars"].add("STP")
        world.val["vars"][PREFIX + "loyalists"] = 40
        world.data["176"].update(owner="VAL", controller="VAL", cores={"VAL"})
        for state in ("43", "44"):
            world.data[state].update(owner="STP", controller="STP", cores={"STP"})
        return world

    def start(self, world, kind):
        world.val["vars"][PREFIX + "plan_choice"] = kind
        world.run(PREFIX + "start_plan")

    def test_successful_plan_rewards_its_delegation_once(self):
        world = self.war_world()
        self.start(world, 2)
        self.assertEqual(world.val["missions"][PREFIX + "plan_iron_shield"], 90)
        mission = world.decisions[PREFIX + "plan_iron_shield"]
        self.assertFalse(world.matches(block(mission, "available")))
        world.data["43"]["controller"] = world.data["44"]["controller"] = "VAL"
        self.assertTrue(world.matches(block(mission, "available")))
        world.execute(block(mission, "complete_effect"))
        self.assertEqual(self.seats(world), (1, 3, 2))
        self.assertAlmostEqual(world.val["council_bop"], 0.10)
        self.assertEqual(world.val["vars"][PREFIX + "loyalists"], 30)
        self.assertNotIn(PREFIX + "plan_kind", world.val["vars"])
        self.assertNotIn(PREFIX + "plan_iron_shield", world.val["missions"])
        world.run(PREFIX + "plan_success")
        self.assertEqual(self.seats(world), (1, 3, 2))

    def test_lost_district_fails_the_line_and_the_report_assigns_blame(self):
        world = self.war_world()
        self.start(world, 1)
        world.run(PREFIX + "reconcile_plan")
        self.assertEqual(world.val["vars"][PREFIX + "plan_kind"], 1)
        world.data["176"]["controller"] = "STP"
        world.run(PREFIX + "reconcile_plan")
        self.assertNotIn(PREFIX + "plan_kind", world.val["vars"])
        self.assertAlmostEqual(world.val["council_bop"], -0.10)
        self.assertEqual(world.val["vars"][PREFIX + "loyalists"], 50)
        self.assertAlmostEqual(world.val["stability"], 0.47)
        self.assertIn(("VAL", "val_council.17"), world.events)
        report = next(e.value for e in entries("events/ADISCORD_VAL_contract_events.txt")
                      if e.key == "country_event" and scalar(e.value, "id") == "val_council.17")
        option = next(r.value for r in report if r.key == "option")
        world.execute([row for row in option if row.key not in ("name", "ai_chance")])
        self.assertEqual(self.seats(world), (1, 3, 2))

    def test_peace_settles_each_plan_by_its_current_goal(self):
        world = self.war_world()
        self.start(world, 3)
        world.val["wars"].clear()
        world.run(PREFIX + "reconcile_plan")
        self.assertEqual(self.seats(world), (1, 2, 3))
        world = self.war_world()
        self.start(world, 2)
        world.val["wars"].clear()
        world.run(PREFIX + "reconcile_plan")
        self.assertEqual(self.seats(world), (2, 2, 2))
        self.assertIsNotNone(world.val["council_bop"])
        self.assertNotIn(PREFIX + "plan_kind", world.val["vars"])
        self.assertNotIn(("VAL", "val_council.17"), world.events)

    def test_favour_moves_a_seat_and_shares_one_interval(self):
        world = self.war_world()
        self.assertEqual(scalar(world.decisions[PREFIX + "favour_front"], "cost"), "30")
        self.assertTrue(world.choose("favour_front"))
        self.assertIn(PREFIX + "favour_front", world.val["modifiers"])
        self.assertEqual(self.seats(world), (1, 3, 2))
        self.assertAlmostEqual(world.val["council_bop"], -0.05)
        self.assertFalse(world.choose("favour_supply"))
        world.val["flags"].discard(PREFIX + "favour_cooldown")
        self.set_seats(world, (0, 0, 6))
        self.assertFalse(world.choose("favour_supply"))
        world.val["wars"].clear()
        self.set_seats(world, (2, 2, 2))
        self.assertFalse(world.choose("favour_front"))
        self.assertTrue(world.choose("favour_supply"))

    def test_five_seats_raise_one_demand_per_interval(self):
        world = self.war_world()
        self.set_seats(world, (4, 1, 1))
        world.val["vars"].update({PREFIX + "seat_side": 1, PREFIX + "seat_delta": 1})
        world.run(PREFIX + "transfer_seat")
        self.assertEqual(self.seats(world), (5, 0, 1))
        self.assertEqual(world.events.count(("VAL", "val_council.18")), 1)
        world.val["vars"].update({PREFIX + "seat_side": 1, PREFIX + "seat_delta": 1})
        world.run(PREFIX + "transfer_seat")
        self.assertEqual(world.events.count(("VAL", "val_council.18")), 1)

    def test_permanent_government_installs_the_largest_delegation_head(self):
        for values, leader in (((2, 2, 2), "VAL_Gleb_Osten"), ((1, 4, 1), "VAL_Tamara_Greitz"),
                               ((1, 2, 3), "VAL_Arkadi_Lemm"), ((2, 3, 1), "VAL_Tamara_Greitz")):
            world = self.war_world()
            world.val["characters"].update({"VAL_Gleb_Osten", "VAL_Tamara_Greitz", "VAL_Arkadi_Lemm"})
            world.val["vars"][PREFIX + "identity"] = 2
            self.set_seats(world, values)
            world.run(PREFIX + "install_commander")
            self.assertEqual(world.val["leader"], leader, values)
            self.assertEqual(world.val["field_marshals"], {leader})
            self.assertEqual(world.val["cosmetic"], "VAL_valden_republic")
            self.assertTrue(world.matches(world.triggers[PREFIX + "operational"]))
            self.assertEqual(len(world.visible_council_focuses()), 32)
            self.assertIn("mark_focus_tree_layout_dirty", world.calls)

    def test_peace_offers_the_bill_and_the_mandate_term_once(self):
        world = self.war_world()
        world.val["flags"].add(PREFIX + "stelander_war_started")
        world.run(PREFIX + "check_postwar")
        self.assertNotIn(("VAL", "val_council.15"), world.events)
        world.val["wars"].clear()
        world.val["focuses"].add(PREFIX + "limited_mandate")
        world.run(PREFIX + "check_postwar")
        world.run(PREFIX + "check_postwar")
        self.assertEqual(world.events.count(("VAL", "val_council.15")), 1)
        self.assertEqual(world.events.count(("VAL", "val_council.24")), 1)
        world = self.war_world()
        world.val["flags"].update({PREFIX + "stelander_war_started", "VAL_stelander_defeated"})
        world.val["wars"].clear()
        world.run(PREFIX + "check_postwar")
        self.assertNotIn(("VAL", "val_council.15"), world.events)

    def test_solgalov_keeps_velsky_as_starting_prime_minister(self):
        history = entries("history/countries/VAL - ValeraLand.txt")
        installed = [row.value for row in block(history, "add_ideas")]
        self.assertIn("minister_VAL_Mikhail_Velsky", installed)
        self.assertNotIn("minister_VAL_Valerian_Kraith", installed)
        ideas = block(entries("common/ideas/ADISCORD_VAL_rework_ideas.txt"), "ideas")
        cabinet_heads = block(ideas, "political_advisor_head_of_state")
        minister = block(cabinet_heads, "minister_VAL_Mikhail_Velsky")
        removal = block(minister, "allowed_to_remove")
        for leader, expected in (
            ("VAL_Valera_Solgalov", False),
            ("VAL_Commanders_Council", True),
            ("VAL_Mikhail_Velsky", True),
            ("VAL_Valera_Solgalov", False),
        ):
            with self.subTest(leader=leader):
                facts = {("VAL", "ruling_leader"): leader}
                self.assertEqual(matches_conditions(removal, facts, "VAL"), expected)

    def test_velsky_cabinet_keeps_the_council_institutions(self):
        world = self.war_world()
        world.val["leader"] = "VAL_Mikhail_Velsky"
        self.assertTrue(world.matches(world.triggers[PREFIX + "operational"]))
        world.val["leader"] = "VAL_party_administration"
        self.assertFalse(world.matches(world.triggers[PREFIX + "operational"]))

    def test_regime_closure_removes_the_balance_and_the_plan(self):
        world = self.war_world()
        self.start(world, 1)
        world.run(PREFIX + "close_regime")
        self.assertIsNone(world.val["council_bop"])
        self.assertNotIn(PREFIX + "plan_kind", world.val["vars"])
        self.assertNotIn(PREFIX + "plan_hold_line", world.val["missions"])
        for name in ("VAL_frontier_settle_defeat", "VAL_enter_stelander_defeat"):
            self.assertIn(PREFIX + "close_regime", {row.key for row in walk(world.effects[name])}, name)

    def test_loyalist_network_is_clamped_and_reaches_the_aggregate(self):
        world = self.war_world()
        world.val["vars"][PREFIX + "loyalists_delta"] = 75
        world.run(PREFIX + "change_loyalists")
        self.assertEqual(world.val["vars"][PREFIX + "loyalists"], 100)
        self.assertEqual(world.events.count(("VAL", "val_council.21")), 1)
        world.val["vars"][PREFIX + "loyalists_delta"] = 5
        world.run(PREFIX + "change_loyalists")
        self.assertEqual(world.events.count(("VAL", "val_council.21")), 1)
        world.run(PREFIX + "apply_modifiers")
        self.assertAlmostEqual(world.val["vars"]["VAL_contract_org_factor"], -0.05)
        self.assertAlmostEqual(world.val["vars"]["VAL_contract_planning_factor"], -0.10)

    def test_loyalist_preview_excludes_other_bonuses_and_clears_when_inactive(self):
        world = self.war_world()
        variables = world.val["vars"]
        for support, organization, planning in (
            (100, -0.05, -0.10),
            (80, -0.04, -0.08),
            (40, -0.02, -0.04),
            (0, 0, 0),
        ):
            with self.subTest(support=support):
                variables[PREFIX + "loyalists"] = support
                variables["VAL_contract_org_factor"] = 0.20
                variables["VAL_contract_planning_factor"] = 0.30
                variables[PREFIX + "base_organization"] = 0.01
                variables[PREFIX + "base_planning_speed"] = 0.02
                world.run(PREFIX + "apply_modifiers")
                self.assertAlmostEqual(variables.get(PREFIX + "loyalist_org_penalty", 1), organization)
                self.assertAlmostEqual(variables.get(PREFIX + "loyalist_planning_penalty", 1), planning)
                self.assertAlmostEqual(variables["VAL_contract_org_factor"], 0.21 + organization)
                self.assertAlmostEqual(variables["VAL_contract_planning_factor"], 0.32 + planning)

        for absent in ("network", "government"):
            with self.subTest(absent=absent):
                variables[PREFIX + "loyalists"] = 100
                world.run(PREFIX + "apply_modifiers")
                if absent == "network":
                    del variables[PREFIX + "loyalists"]
                else:
                    world.val["leader"] = "VAL_Valera_Solgalov"
                    world.val["flags"].discard(PREFIX + "in_power")
                world.run(PREFIX + "apply_modifiers")
                self.assertEqual(variables.get(PREFIX + "loyalist_org_penalty", 1), 0)
                self.assertEqual(variables.get(PREFIX + "loyalist_planning_penalty", 1), 0)

    def test_solgalov_dominance_reveals_but_does_not_remove_the_balance(self):
        balance = block(entries("common/bop/VAL.txt"), "VAL_command_balance")
        ranges = {scalar(r.value, "id"): r.value for side in balance if side.key == "side" for r in side.value if r.key == "range"}
        event = next(e.value for e in entries("events/ADISCORD_VAL_contract_events.txt")
                     if e.key == "country_event" and scalar(e.value, "id") == "val_council.27")
        options = [row.value for row in event if row.key == "option"]
        world = CouncilWorld()
        world.val["flags"].discard(PREFIX + "in_power")
        world.val["leader"] = "VAL_Valera_Solgalov"
        world.val["flags"].add(PREFIX + "stelander_war_started")
        world.val["bop"] = 0.8
        world.execute(block(ranges["VAL_solgalov_dominance"], "on_activate"))
        world.execute(block(ranges["VAL_solgalov_dominance"], "on_activate"))
        self.assertEqual(world.val["bop"], 0.8)
        self.assertEqual(world.events.count(("VAL", "val_council.27")), 1)
        for option in options:
            before = world.balance(), world.val["pp"], world.val["cp"]
            world.execute([row for row in option if row.key not in ("name", "ai_chance", "trigger")])
            self.assertEqual((world.balance(), world.val["pp"], world.val["cp"]), before)
            self.assertEqual(world.val["bop"], 0.8)
        world.val["bop"] = -0.8
        self.assertTrue(world.matches(world.triggers[PREFIX + "coup_ready"]))

    def test_personal_branch_balance_decisions_have_real_prices(self):
        category = {e.key: e.value for e in block(entries(DECISIONS), "VAL_command_balance_category")}
        honours, review = category["VAL_honour_loyal_captains"], category["VAL_staff_loyalty_review"]
        def values(rows):
            return {row.value for row in walk(rows) if isinstance(row.value, str)}

        self.assertIn("VAL_Loyal_Captains_Honours", values(block(honours, "visible")))
        self.assertIn("VAL_Krutovs_Eyes", values(block(review, "visible")))
        honour_effect = {row.key for row in walk(block(honours, "complete_effect"))}
        self.assertIn("subtract_from_variable", honour_effect)
        self.assertIn("ADISCORD_economy_mark_dirty", honour_effect)
        review_effect = {row.key: row.value for row in walk(block(review, "complete_effect"))}
        self.assertEqual(review_effect["add_command_power"], "-30")
        self.assertEqual(scalar(review_effect["add_dynamic_modifier"], "modifier"), "VAL_staff_review_disruption")
        settle = category["VAL_settle_command_crisis"]
        self.assertNotIn("VAL_solgalov_dominance", values(block(settle, "available")))

    def test_contract_administrations_follow_identity_with_their_own_shade(self):
        world = self.war_world()
        world.countries += ["OCA", "NKA"]
        for tag in ("OCA", "NKA"):
            world.data[tag].update(subject="VAL", exists=True)
        for identity, suffix in ((2, "republic"), (3, "districts")):
            world.val["vars"][PREFIX + "identity"] = identity
            world.run(PREFIX + "tint_administrations")
            self.assertEqual(world.data["OCA"]["cosmetic"], "OCA_VAL_" + suffix)
            self.assertEqual(world.data["NKA"]["cosmetic"], "NKA_VAL_" + suffix)
        world.val["vars"][PREFIX + "identity"] = 1
        world.run(PREFIX + "tint_administrations")
        self.assertIsNone(world.data["OCA"]["cosmetic"])
        world.val["vars"][PREFIX + "identity"] = 3
        world.data["NKA"].update(subject="STS", cosmetic="NKA_STS_administration")
        world.run(PREFIX + "tint_administrations")
        self.assertEqual(world.data["NKA"]["cosmetic"], "NKA_STS_administration")
        world.val["leader"] = "VAL_party_administration"
        world.run(PREFIX + "tint_administrations")
        self.assertIsNone(world.data["OCA"]["cosmetic"])
        cosmetic = (ROOT / "common/countries/cosmetic.txt").read_text(encoding="utf-8")
        for tag in ("OCA", "NKA"):
            for suffix in ("republic", "districts"):
                name = f"{tag}_VAL_{suffix}"
                self.assertIn(name + " = {", cosmetic)
                for folder in ("gfx/flags", "gfx/flags/medium", "gfx/flags/small"):
                    self.assertTrue((ROOT / folder / (name + ".tga")).exists(), (folder, name))
        apply = self.effects_body("VAL_council_apply_identity")
        self.assertEqual(apply[-1].key, PREFIX + "tint_administrations")

    @staticmethod
    def effects_body(name):
        return next(e.value for e in entries(EFFECTS) if e.key == name)

    def test_balance_extremes_open_council_crises(self):
        rows = entries("common/bop/VAL.txt")
        balance = block(rows, PREFIX + "balance")
        ranges = {scalar(r.value, "id"): r.value for side in balance if side.key == "side" for r in side.value if r.key == "range"}
        for name, event in ((PREFIX + "collegial_dominance", "val_council.19"), (PREFIX + "command_dominance", "val_council.20")):
            calls = [scalar(row.value, "id") for row in walk(block(ranges[name], "on_activate")) if row.key == "country_event"]
            self.assertEqual(calls, [event])
        self.assertEqual(scalar(balance, "decision_category"), PREFIX + "balance_category")


class CouncilIdentityTests(unittest.TestCase):
    TAGS = ("VAL_kefreyt_state", "VAL_valden_republic", "VAL_united_military_districts")

    @classmethod
    def setUpClass(cls):
        cls.event = next(e.value for e in entries("events/ADISCORD_VAL_contract_events.txt")
                         if e.key == "country_event" and scalar(e.value, "id") == "val_council.25")
        cls.options = [e.value for e in cls.event if e.key == "option"]

    def visible_options(self, world):
        return [option for option in self.options if world.matches(block(option, "trigger"))]

    def choose(self, world, index):
        world.execute(block(self.options[index], "hidden_effect"))

    def test_three_choices_change_one_identity_without_charging_resources(self):
        template = CouncilWorld()
        for index, tag in enumerate(self.TAGS):
            with self.subTest(tag=tag):
                world = deepcopy(template)
                self.assertEqual(self.visible_options(world), self.options[:3])
                before = deepcopy(world.val)
                self.choose(world, index)
                expected = deepcopy(before)
                expected["vars"][PREFIX + "identity"] = index + 1
                expected["cosmetic"] = tag
                self.assertEqual(world.val, expected)
                self.assertEqual(self.visible_options(world), self.options[3:])
                for repeated in range(3):
                    self.choose(world, repeated)
                    self.assertEqual(world.val, expected)

    def test_stale_window_cannot_rename_a_subject_or_replacement_government(self):
        template = CouncilWorld()
        for field, value in (("subject", "STP"), ("leader", "VAL_party_administration"),
                             ("capitulated", True), ("exists", False)):
            world = deepcopy(template)
            world.val[field] = value
            world.val["cosmetic"] = "VAL_STS_administration"
            before = deepcopy(world.val)
            self.assertEqual(self.visible_options(world), self.options[3:])
            for index in range(3):
                self.choose(world, index)
                self.assertEqual(world.val, before)

    def test_defeated_council_can_choose_without_the_coup_flag(self):
        world = CouncilWorld()
        world.val["flags"].discard(PREFIX + "in_power")
        world.val["flags"].add("VAL_stelander_defeated")
        world.val["tree"] = "VAL_defeated_focus"
        world.run(PREFIX + "offer_identity")
        self.assertIn(("VAL", "val_council.25"), world.events)
        self.assertTrue(world.matches(block(self.event, "trigger")))
        self.choose(world, 2)
        world.run(PREFIX + "offer_identity")
        self.assertEqual(world.events.count(("VAL", "val_council.25")), 1)
        for transition in ("VAL_enter_stelander_defeat", PREFIX + "take_power"):
            payload = block(world.effects[transition], "if")
            keys = [entry.key for entry in payload]
            self.assertLess(keys.index("set_politics"), keys.index(PREFIX + "offer_identity"))

    def test_default_option_and_reforms_preserve_each_selection(self):
        self.assertEqual(scalar(self.options[0], "name"), "val_council.25.a")
        self.assertEqual(scalar(self.event, "fire_only_once"), "yes")
        focuses = {scalar(e.value, "id"): e.value for e in block(entries(FOCUSES), "focus_tree")
                   if e.key == "focus"}
        template = CouncilWorld()
        for index, tag in enumerate(self.TAGS):
            world = deepcopy(template)
            self.choose(world, index)
            world.execute(block(focuses[PREFIX + "charter"], "completion_reward"))
            self.assertEqual(world.val["cosmetic"], tag)
            world.run(PREFIX + "install_commander")
            self.assertEqual(world.val["cosmetic"], tag)
            world.run(PREFIX + "close_regime")
            world.val["subject"] = "STP"
            world.val["cosmetic"] = "VAL_STS_administration"
            world.run(PREFIX + "apply_identity")
            self.assertEqual(world.val["cosmetic"], "VAL_STS_administration")
            world.val["subject"] = None
            world.run(PREFIX + "offer_identity")
            self.assertEqual(world.val["cosmetic"], tag)
            self.assertNotIn(("VAL", "val_council.25"), world.events)

    def test_commonwealth_proclamation_keeps_council_identity(self):
        template = CouncilWorld()
        # Exercise proclamation after its separately tested territorial gate succeeds.
        body = block(template.effects["VAL_adopt_commonwealth"], "if")
        payload = [e for e in body if e.key not in
                   ("limit", "VAL_sync_solgalov_portrait", "VAL_grant_contract_warlord")]
        for index, tag in enumerate(self.TAGS):
            world = deepcopy(template)
            self.choose(world, index)
            world.execute(payload)
            self.assertEqual(world.val["cosmetic"], tag)
            self.assertIn("VAL_commonwealth_proclaimed", world.val["flags"])
        world = deepcopy(template)
        world.val["leader"] = "VAL_Valera_Solgalov"
        world.execute(payload)
        self.assertEqual(world.val["cosmetic"], "VAL_commonwealth")

    def test_flags_colours_and_localised_names_are_bound_to_all_three_tags(self):
        cosmetics = entries("common/countries/cosmetic.txt")
        for tag, colour in zip(self.TAGS, ((127, 15, 2), (69, 100, 122), (116, 121, 75))):
            body = block(cosmetics, tag)
            self.assertEqual(tuple(int(e.value) for e in block(body, "color")), colour)
            for language in ("russian", "english"):
                raw = (ROOT / f"localisation/{language}/ADISCORD_VAL_decisions_l_{language}.yml").read_bytes()
                self.assertTrue(raw.startswith(b"\xef\xbb\xbf"))
                for suffix in ("", "_DEF", "_ADJ"):
                    self.assertRegex(raw.decode("utf-8-sig"), rf'(?m)^ {tag}{suffix}:0 "[^"\r\n]+"$')
        for path, expected in build_adiscord_val_flags.outputs(self.TAGS):
            self.assertEqual(path.read_bytes(), expected)
            folder = path.parent.name if path.parent.name != "flags" else ""
            with Image.open(BytesIO(expected)) as texture:
                self.assertEqual(texture.size, build_adiscord_val_flags.SIZES[folder])
                self.assertEqual(texture.mode, "RGBA")
                self.assertEqual(texture.getchannel("A").getextrema(), (255, 255))
            if path.stem == "VAL_kefreyt_state":
                self.assertEqual(expected, path.with_name("VAL.tga").read_bytes())


if __name__ == "__main__":
    unittest.main()
