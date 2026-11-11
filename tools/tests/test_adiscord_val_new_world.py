"""Parsed campaign contracts; native focus history and UI still need a cold load."""

from pathlib import Path
from collections import defaultdict
import re
import unittest

from tools.builders.build_adiscord_focus_trees import SOURCES
from tools.tests.test_adiscord_stp_preparation import block, entries, scalar, walk


ROOT = Path(__file__).resolve().parents[2]
EFFECTS = "common/scripted_effects/ADISCORD_VAL_effects.txt"
TRIGGERS = "common/scripted_triggers/ADISCORD_VAL_rework_triggers.txt"
DECISIONS = "common/decisions/ADISCORD_VAL_decisions.txt"
TREE = "focus_trees/VAL/new_world/focuses.txt"
EVENTS = "events/ADISCORD_VAL_contract_events.txt"
IDEAS = "common/ideas/ADISCORD_VAL_rework_ideas.txt"
PARTNERS = ("SLA", "RZA", "MLR", "ERT", "IRT", "SCA", "TMR", "VEL", "RLY")


def country_event(event_id):
    return next(e.value for e in entries(EVENTS) if e.key == "country_event" and scalar(e.value, "id") == event_id)


def tree_focuses():
    return {scalar(e.value, "id"): e.value for e in block(entries(TREE), "focus_tree") if e.key == "focus"}


class ContractWorld:
    """Execute the parsed receipts; external economy refresh and native timers are boundaries."""

    def __init__(self):
        self.effects = {}
        self.triggers = {}
        for path in (
            EFFECTS,
            "common/scripted_effects/ADISCORD_vorkerland_effects.txt",
            "common/scripted_effects/ADISCORD_RUS_scripted_effects.txt",
        ):
            self.effects.update({e.key: e.value for e in entries(path)})
        for path in (TRIGGERS, "common/scripted_triggers/ADISCORD_vorkerland_triggers.txt"):
            self.triggers.update({e.key: e.value for e in entries(path)})
        self.data = defaultdict(lambda: {
            "vars": {}, "flags": set(), "flag_days": {}, "pp": 1000,
            "rifles": {"VAL": 5000}, "wars": set(), "rights": {},
            "buildings": defaultdict(int), "resources": defaultdict(int),
            "slots": 0, "exists": True, "owner": "VAL", "controller": "VAL",
            "subject": None, "capitulated": False, "focuses": set(),
            "manpower": 0, "army_experience": 0, "modifiers": set(),
            "research_bonuses": [], "faction": None, "leader": False, "ai": True,
            "bop": {}, "missions": set(),
        })
        self.data["VAL"]["vars"]["ADISCORD_economy_treasury"] = 2000
        self.target = "176"
        self.targets = {}
        self.events = []
        self.dirty = set()

    def scope(self, key, current):
        if key == "FROM":
            return self.target
        if key in ("owner", "controller"):
            return self.data[current][key]
        if key.startswith("event_target:"):
            return self.targets.get(key.split(":", 1)[1], "missing")
        return key

    def number(self, value, scope):
        try:
            return float(value)
        except ValueError:
            return self.data[scope]["vars"].get(value, 0)

    @staticmethod
    def condition_groups(rows):
        index = 0
        while index < len(rows):
            width = 1 if rows[index].key else 3
            group = rows[index:index + width]
            if len(group) != width:
                raise AssertionError(("incomplete comparison", group))
            yield group
            index += width

    def matches(self, rows, scope="VAL"):
        result = []
        index = 0
        while index < len(rows):
            row = rows[index]
            key, value = row.key, row.value
            index += 1
            country = self.data[scope]
            if not key:
                op, threshold = rows[index:index + 2]
                index += 2
                current = country["pp"] if value == "has_political_power" else country["buildings"][value]
                result.append(current < float(threshold.value) if op.value == "<" else current > float(threshold.value))
            elif key in self.triggers:
                result.append(self.matches(self.triggers[key], scope) == (value == "yes"))
            elif key in ("AND", "hidden_trigger"):
                result.append(self.matches(value, scope))
            elif key == "custom_trigger_tooltip":
                result.append(self.matches([child for child in value if child.key != "tooltip"], scope))
            elif key == "OR":
                result.append(any(self.matches(group, scope) for group in self.condition_groups(value)))
            elif key == "count_triggers":
                amount = int(scalar(value, "amount"))
                conditions = [child for child in value if child.key != "amount"]
                result.append(sum(self.matches([child], scope) for child in conditions) >= amount)
            elif key == "NOT":
                result.append(not self.matches(value, scope))
            elif key == "check_variable":
                left = self.number(scalar(value, "var"), scope)
                right = self.number(scalar(value, "value"), scope)
                op = scalar(value, "compare")
                result.append({"equals": left == right, "greater_than_or_equals": left >= right,
                               "greater_than": left > right, "less_than": left < right}[op])
            elif key in ("has_variable", "has_country_flag", "has_state_flag", "has_completed_focus"):
                collection = {"has_variable": "vars", "has_country_flag": "flags",
                              "has_state_flag": "flags", "has_completed_focus": "focuses"}[key]
                if isinstance(value, list):
                    flag = scalar(value, "flag")
                    result.append(flag in country[collection] and country["flag_days"].get(flag, 0) > 13)
                else:
                    result.append(value in country[collection])
            elif key == "has_equipment":
                _, op, amount = [child.value for child in value]
                quantity = sum(country["rifles"].values())
                result.append(quantity < float(amount) if op == "<" else quantity > float(amount))
            elif key in ("tag", "state"):
                result.append(scope == self.scope(value, scope))
            elif key == "is_subject":
                result.append((country["subject"] is not None) == (value == "yes"))
            elif key == "is_subject_of":
                result.append(country["subject"] == value)
            elif key == "has_capitulated":
                result.append(country["capitulated"] == (value == "yes"))
            elif key == "has_dynamic_modifier":
                result.append(scalar(value, "modifier") in country["modifiers"])
            elif key == "exists":
                result.append(country["exists"] == (value == "yes"))
            elif key == "has_war_with":
                result.append(value in country["wars"])
            elif key == "has_war":
                result.append(bool(country["wars"]) == (value == "yes"))
            elif key == "is_in_faction_with":
                other = self.data[self.scope(value, scope)]["faction"]
                result.append(country["faction"] is not None and country["faction"] == other)
            elif key == "is_in_faction":
                result.append((country["faction"] is not None) == (value == "yes"))
            elif key == "is_faction_leader":
                result.append(country["leader"] == (value == "yes"))
            elif key == "is_ai":
                result.append(country["ai"] == (value == "yes"))
            elif key == "has_power_balance":
                result.append(scalar(value, "id") in country["bop"])
            elif key == "power_balance_value":
                name = scalar(value, "id")
                _, op, threshold = [child.value for child in value if not child.key]
                current = country["bop"].get(name)
                result.append(current is not None and (current < float(threshold) if op == "<" else current > float(threshold)))
            elif key == "owns_state":
                result.append(self.data[value]["owner"] == scope)
            elif key == "is_owned_by":
                result.append(country["owner"] == value)
            elif key == "is_controlled_by":
                result.append(country["controller"] == value)
            elif isinstance(value, list) and (key.isdigit() or key in ("VAL", "RUS", "NAM", "FROM", "owner", "controller") + PARTNERS):
                result.append(self.matches(value, self.scope(key, scope)))
            else:
                raise AssertionError(("unsupported condition", scope, key, value))
        return all(result)

    def run(self, name, scope="VAL"):
        self.execute(self.effects[name], scope)

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
            elif key == "ADISCORD_economy_mark_dirty":
                self.dirty.add(scope)
            elif key.startswith("ADISCORD_economy_receive_") and key[len("ADISCORD_economy_receive_"):].isdigit():
                # Shared fixed-amount treasury receipt from ADISCORD_shared_action_effects.txt.
                amount = int(key[len("ADISCORD_economy_receive_"):])
                for name in ("ADISCORD_economy_treasury", "ADISCORD_economy_current_month_action_income"):
                    country["vars"][name] = country["vars"].get(name, 0) + amount
                self.dirty.add(scope)
            elif key in ("VAL_refresh_arsenal_reputation", "ADISCORD_release_non_participating_minor_optimization"):
                pass
            elif key in self.effects:
                self.run(key, scope)
            elif key in ("hidden_effect", "effect"):
                self.execute(value, scope)
            elif key in ("set_variable", "add_to_variable", "subtract_from_variable"):
                name = scalar(value, "var")
                amount = self.number(scalar(value, "value"), scope)
                previous = country["vars"].get(name, 0)
                country["vars"][name] = amount if key == "set_variable" else previous + amount * (-1 if key == "subtract_from_variable" else 1)
            elif key == "clear_variable":
                country["vars"].pop(value, None)
            elif key == "clamp_variable":
                name = scalar(value, "var")
                lower = float(scalar(value, "min"))
                upper = float(scalar(value, "max"))
                country["vars"][name] = max(lower, min(upper, country["vars"].get(name, 0)))
            elif key in ("set_country_flag", "set_state_flag"):
                flag = value if isinstance(value, str) else scalar(value, "flag")
                country["flags"].add(flag)
                country["flag_days"][flag] = 0
            elif key in ("clr_country_flag", "clr_state_flag"):
                country["flags"].discard(value)
            elif key == "add_political_power":
                country["pp"] += float(value)
            elif key == "add_manpower":
                country["manpower"] += float(value)
            elif key == "army_experience":
                country["army_experience"] += float(value)
            elif key == "add_tech_bonus":
                country["research_bonuses"].append(scalar(value, "name"))
            elif key == "add_dynamic_modifier":
                country["modifiers"].add(scalar(value, "modifier"))
            elif key == "force_update_dynamic_modifier":
                pass
            elif key == "add_equipment_to_stockpile":
                self.assert_rifle(value)
                amount = float(scalar(value, "amount"))
                producer = next((e.value for e in value if e.key == "producer"), None)
                if amount >= 0:
                    country["rifles"][producer] = country["rifles"].get(producer, 0) + amount
                else:
                    remaining = -amount
                    for tag in ([producer] if producer else list(country["rifles"])):
                        removed = min(remaining, country["rifles"].get(tag, 0))
                        country["rifles"][tag] = country["rifles"].get(tag, 0) - removed
                        remaining -= removed
            elif key == "save_global_event_target_as":
                self.targets[value] = scope
            elif key == "clear_global_event_target":
                self.targets.pop(value, None)
            elif key == "add_extra_state_shared_building_slots":
                country["slots"] += int(value)
            elif key == "add_building_construction":
                country["buildings"][scalar(value, "type")] += int(scalar(value, "level"))
            elif key == "add_resource":
                country["resources"][scalar(value, "type")] += int(scalar(value, "amount"))
            elif key == "give_resource_rights":
                state = scalar(value, "state")
                self.data[scalar(value, "receiver")]["rights"][state] = scope
            elif key == "remove_resource_rights":
                country["rights"].pop(value, None)
            elif key == "country_event":
                self.events.append((scope, scalar(value, "id")))
            elif key in ("custom_effect_tooltip", "effect_tooltip"):
                pass
            elif key == "leave_faction":
                country["faction"] = None
                country["leader"] = False
            elif key == "transfer_state":
                self.data[value]["owner"] = scope
            elif key == "set_state_controller_to":
                country["controller"] = value
            elif key == "remove_power_balance":
                country["bop"].pop(scalar(value, "id"), None)
            elif key == "remove_mission":
                country["missions"].discard(value)
            elif isinstance(value, list) and (key.isdigit() or key in ("VAL", "RUS", "NAM", "FROM", "owner", "controller") + PARTNERS):
                self.execute(value, self.scope(key, scope))
            else:
                raise AssertionError(("unsupported effect", scope, key, value))

    @staticmethod
    def assert_rifle(rows):
        assert scalar(rows, "type") == "infantry_equipment"


class NewWorldAccountingTests(unittest.TestCase):
    def warning(self, kind):
        world = ContractWorld()
        world.data["VAL"]["flags"].add("RUS_crisis_warned")
        world.data["RUS"]["vars"]["RUS_crisis_phase"] = 1
        # Both expanded orders are unlocked by reading the Khan's order.
        world.data["VAL"]["focuses"].add("VAL_nw_khan")
        return world

    def test_expanded_orders_preserve_quotes_and_reject_other_tier_callbacks(self):
        for kind, base_price, expanded_price, expected_rifles, expected_manpower in (
            ("arsenals", 150, 250, 21200, 0),
            ("reserve", 200, 300, 5000, 5000),
        ):
            with self.subTest(kind=kind):
                world = self.warning(kind)
                country = world.data["VAL"]
                country["focuses"].clear()
                base = "VAL_nw_emergency_" + kind
                expanded = "VAL_nw_expanded_" + kind
                world.run(base + "_begin")
                country["focuses"].add("VAL_nw_khan")
                world.run(expanded + "_begin")
                self.assertEqual(country["vars"][base + "_deposit"], base_price)
                world.run(expanded + "_finish")
                self.assertIn(base + "_deposit", country["vars"])
                world.run(base + "_finish")
                world.run(expanded + "_begin")
                world.run(base + "_finish")
                category = block(entries(DECISIONS), "VAL_new_world_category")
                world.execute(block(block(category, base), "cancel_effect"))
                self.assertEqual(country["vars"][base + "_deposit"], expanded_price)
                world.run(expanded + "_finish")
                world.run(expanded + "_finish")
                self.assertEqual(sum(country["rifles"].values()), expected_rifles)
                self.assertEqual(country["manpower"], expected_manpower)
                self.assertEqual(country["vars"]["ADISCORD_economy_treasury"], 2000 - base_price - expanded_price)
                self.assertEqual(country["pp"], 950)

    def test_expanded_order_exact_affordability_and_one_time_refund(self):
        for kind, price in (("arsenals", 250), ("reserve", 300)):
            for treasury, political_power, paid in ((price - 0.01, 25, False), (price, 24.99, False), (price, 25, True)):
                with self.subTest(kind=kind, treasury=treasury, pp=political_power):
                    world = self.warning(kind)
                    country = world.data["VAL"]
                    country["vars"]["ADISCORD_economy_treasury"] = treasury
                    country["pp"] = political_power
                    name = "VAL_nw_expanded_" + kind
                    world.run(name + "_begin")
                    self.assertEqual("VAL_nw_emergency_" + kind + "_deposit" in country["vars"], paid)
                    world.data["RUS"]["vars"]["RUS_crisis_phase"] = 5
                    world.run(name + "_finish")
                    world.run("VAL_nw_refund_orders")
                    self.assertEqual(country["vars"]["ADISCORD_economy_treasury"], treasury)
                    self.assertEqual(country["pp"], political_power)
                    self.assertEqual(sum(country["rifles"].values()), 5000)
                    self.assertEqual(country["manpower"], 0)

    def test_survey_delivery_is_required_for_the_first_restoration_unlock(self):
        world = ContractWorld()
        self.assertFalse(world.matches(world.triggers["VAL_nw_survey_completed"]))
        world.run("VAL_nw_survey_begin")
        self.assertFalse(world.matches(world.triggers["VAL_nw_survey_completed"]))
        world.run("VAL_nw_survey_finish")
        world.run("VAL_nw_survey_finish")
        self.assertTrue(world.matches(world.triggers["VAL_nw_survey_completed"]))
        self.assertEqual(world.data["VAL"]["army_experience"], 10)
        self.assertEqual(world.events, [("VAL", "val_rework.135")])

    def test_two_distinct_working_plants_need_current_access_and_control(self):
        world = ContractWorld()
        world.data["176"]["flags"].add("RUS_reactor_works_restored")
        world.data["176"]["buildings"]["industrial_complex"] = 1
        self.assertFalse(world.matches(world.triggers["VAL_nw_two_restored_works"]))
        world.data["177"]["flags"].add("RUS_reactor_works_restored")
        world.data["177"]["buildings"]["industrial_complex"] = 1
        self.assertTrue(world.matches(world.triggers["VAL_nw_two_restored_works"]))
        world.data["177"].update(owner="SLA", controller="SLA")
        self.assertFalse(world.matches(world.triggers["VAL_nw_two_restored_works"]))
        world.data["SLA"]["flags"].add("VAL_nw_concession")
        self.assertTrue(world.matches(world.triggers["VAL_nw_two_restored_works"]))
        world.data["177"]["controller"] = "RUS"
        self.assertFalse(world.matches(world.triggers["VAL_nw_two_restored_works"]))
        world.data["176"]["buildings"]["infrastructure"] = 3
        self.assertTrue(world.matches(world.triggers["VAL_nw_has_connected_works"]))
        world.data["176"]["flags"].clear()
        self.assertFalse(world.matches(world.triggers["VAL_nw_has_connected_works"]))

    def test_independence_recognition_is_targeted_and_blocks_later_subjugation(self):
        world = ContractWorld()
        world.target = "SLA"
        world.data["RUS"]["vars"]["RUS_crisis_phase"] = 5
        world.data["VAL"]["focuses"].update({"VAL_nw_charters", "VAL_nw_zones"})
        self.assertTrue(world.matches(world.triggers["VAL_nw_special_zone_permitted"]))
        world.run("VAL_nw_recognize_republic")
        world.run("VAL_nw_recognize_republic")
        self.assertIn("VAL_nw_sovereignty_recognized", world.data["SLA"]["flags"])
        self.assertIsNone(world.data["SLA"]["subject"])
        self.assertNotIn("VAL_nw_concession", world.data["SLA"]["flags"])
        self.assertFalse(world.matches(world.triggers["VAL_nw_special_zone_permitted"]))
        self.assertEqual(world.events, [("SLA", "val_rework.138")])
        self.assertEqual(world.data["VAL"]["vars"]["ADISCORD_economy_treasury"], 2000)
        world.target = "RZA"
        self.assertTrue(world.matches(world.triggers["VAL_nw_special_zone_permitted"]))
        self.assertTrue(world.matches(world.triggers["VAL_nw_special_zone_permitted"], "STP"))

    def test_ending_uses_current_partners_and_administrations(self):
        world = ContractWorld()
        independent = world.triggers["VAL_nw_has_independent_partner"]
        administration = world.triggers["VAL_nw_has_contract_administration"]
        self.assertFalse(world.matches(independent))
        self.assertFalse(world.matches(administration))
        world.data["SLA"]["flags"].add("VAL_nw_concession")
        self.assertTrue(world.matches(independent))
        world.data["SLA"]["subject"] = "VAL"
        self.assertFalse(world.matches(independent))
        self.assertTrue(world.matches(administration))
        world.data["SLA"]["subject"] = "RUS"
        self.assertFalse(world.matches(independent))
        self.assertFalse(world.matches(administration))

    def test_network_caps_follow_single_nonrepeatable_focus_rewards(self):
        world = ContractWorld()
        for effect in ("VAL_nw_improve_industry", "VAL_nw_improve_trade", "VAL_nw_improve_administration"):
            owners = [entry.value for entry in block(entries(TREE), "focus_tree")
                      if entry.key == "focus"
                      and any(row.key == effect for row in walk(block(entry.value, "completion_reward")))]
            self.assertEqual(len(owners), 1, effect)
            self.assertFalse(any(row.key == "repeatable" and row.value == "yes" for row in owners[0]))
            calls = []
            for directory in ("common", "events"):
                for path in (ROOT / directory).rglob("*.txt"):
                    if re.search(rf"\b{effect}\s*=\s*yes\b", path.read_text(encoding="utf-8-sig")):
                        calls.append(path.relative_to(ROOT).as_posix())
            self.assertEqual(calls, ["common/national_focus/ADISCORD_VAL_new_world.txt"], effect)
            world.run(effect)
        variables = world.data["VAL"]["vars"]
        self.assertEqual(variables["VAL_nw_factory_output"], 0.05)
        self.assertEqual(variables["VAL_nw_trade_income"], 0.05)
        self.assertEqual(variables["VAL_nw_admin_expense"], -0.05)
        self.assertEqual(world.data["VAL"]["modifiers"], {"VAL_nw_industrial_network"})
        self.assertEqual(world.dirty, {"VAL"})

    def test_cancelled_one_time_orders_can_retry_after_liberation(self):
        decisions = block(entries(DECISIONS), "VAL_new_world_category")
        names = ("survey", "salvage_archives", "emergency_arsenals", "emergency_reserve",
                 "expanded_arsenals", "expanded_reserve")
        for name in names:
            for interruption in ("subject", "capitulated"):
                with self.subTest(order=name, interruption=interruption):
                    world = self.warning("arsenals")
                    country = world.data["VAL"]
                    country["focuses"].update({"VAL_nw_perimeter", "VAL_nw_archives"})
                    key = "VAL_nw_" + name
                    decision = block(decisions, key)
                    self.assertFalse(any(row.key == "fire_only_once" and row.value == "yes" for row in decision))
                    self.assertTrue(world.matches(block(decision, "visible")))
                    self.assertTrue(world.matches(block(decision, "available")))
                    world.run(key + "_begin")
                    country[interruption] = "RUS" if interruption == "subject" else True
                    self.assertTrue(world.matches(block(decision, "cancel_trigger")))
                    world.execute(block(decision, "cancel_effect"))
                    self.assertEqual(country["vars"]["ADISCORD_economy_treasury"], 2000)
                    self.assertEqual(country["pp"], 1000)
                    country[interruption] = None if interruption == "subject" else False
                    self.assertTrue(world.matches(block(decision, "visible")))
                    self.assertTrue(world.matches(block(decision, "available")))
                    world.run(key + "_begin")
                    world.run(key + "_finish")
                    self.assertIn(key + "_complete", country["flags"])
                    self.assertFalse(world.matches(block(decision, "visible")))
                    settled = (dict(country["vars"]), country["pp"], dict(country["rifles"]),
                               country["manpower"], country["army_experience"],
                               list(country["research_bonuses"]), list(world.events))
                    world.run(key + "_finish")
                    world.run(key + "_begin")
                    self.assertEqual(settled, (dict(country["vars"]), country["pp"], dict(country["rifles"]),
                                              country["manpower"], country["army_experience"],
                                              list(country["research_bonuses"]), list(world.events)))
                    if name == "survey":
                        self.assertEqual(country["army_experience"], 10)
                        self.assertEqual(world.events, [("VAL", "val_rework.135")])

    def test_lost_assets_rebuild_at_full_price_without_duplicate_resources_or_slots(self):
        world = ContractWorld()
        state = world.data["176"]
        for effect, building, price in (("restoration", "industrial_complex", 400),
                                         ("foundry", "arms_factory", 300)):
            world.run("VAL_nw_begin_" + effect)
            world.run("VAL_nw_finish_project")
            slots, resources = state["slots"], dict(state["resources"])
            state["buildings"][building] = 0
            before = world.data["VAL"]["vars"]["ADISCORD_economy_treasury"]
            world.run("VAL_nw_begin_" + effect)
            world.run("VAL_nw_finish_project")
            world.run("VAL_nw_finish_project")
            self.assertEqual(world.data["VAL"]["vars"]["ADISCORD_economy_treasury"], before - price)
            self.assertEqual(state["buildings"][building], 1)
            self.assertEqual((state["slots"], dict(state["resources"])), (slots, resources))
        state["flags"].add("VAL_nw_roads_restored")
        state["buildings"]["infrastructure"] = 1
        for level in (2, 3):
            self.assertFalse(world.matches(world.triggers["VAL_nw_connected_site"], "176"))
            world.run("VAL_nw_begin_roads")
            world.run("VAL_nw_finish_project")
            self.assertEqual(state["buildings"]["infrastructure"], level)
        self.assertTrue(world.matches(world.triggers["VAL_nw_connected_site"], "176"))
        world.run("VAL_nw_begin_roads")
        self.assertNotIn("VAL_nw_project_deposit", world.data["VAL"]["vars"])

    def test_restoration_delivers_each_sites_actual_resource_package_once(self):
        packages = {
            "176": {"steel": 80, "tungsten": 40, "chromium": 25},
            "177": {"steel": 50, "aluminium": 65, "rare_components": 5, "rare_alloys": 4},
            "187": {"steel": 50, "aluminium": 25, "chromium": 25},
            "188": {"steel": 65, "tungsten": 40, "chromium": 55},
            "189": {"steel": 80, "aluminium": 40, "rare_components": 8, "rare_alloys": 4},
            "192": {"steel": 50, "aluminium": 40, "tungsten": 25, "rare_alloys": 5},
        }
        for state_id, resources in packages.items():
            with self.subTest(state=state_id):
                world = ContractWorld()
                world.target = state_id
                state = world.data[state_id]
                world.run("VAL_nw_begin_restoration")
                world.run("VAL_nw_finish_project")
                self.assertEqual(dict(state["resources"]), resources)
                self.assertEqual(state["buildings"]["industrial_complex"], 1)
                self.assertEqual(state["slots"], 1)
                state["buildings"]["industrial_complex"] = 0
                world.run("VAL_nw_begin_restoration")
                world.run("VAL_nw_finish_project")
                world.run("VAL_nw_finish_project")
                self.assertEqual(dict(state["resources"]), resources)
                self.assertEqual(state["slots"], 1)
                self.assertEqual(state["buildings"]["industrial_complex"], 1)
                self.assertEqual(world.data["VAL"]["vars"]["ADISCORD_economy_treasury"], 1200)

    def test_nam_aid_refusal_is_final_but_failed_settlement_is_not(self):
        event = next(e.value for e in entries("events/ADISCORD_VAL_contract_events.txt")
                     if e.key == "country_event" and scalar(e.value, "id") == "val_contract.375")
        refusal = next(e.value for e in event if e.key == "option" and scalar(e.value, "name") == "val_contract.375.decline")
        for explicit in (True, False):
            with self.subTest(explicit=explicit):
                world = ContractWorld()
                world.data["VAL"]["vars"]["VAL_nam_request_terms"] = 2
                if explicit:
                    world.execute(block(refusal, "hidden_effect"), "VAL")
                else:
                    world.run("VAL_decline_nam_aid_request")
                self.assertEqual("VAL_nam_aid_requests_declined" in world.data["VAL"]["flags"], explicit)
                self.assertNotIn("VAL_nam_request_terms", world.data["VAL"]["vars"])
                self.assertEqual(world.data["VAL"]["vars"]["ADISCORD_economy_treasury"], 2000)
                after = list(world.events)
                world.execute(block(refusal, "hidden_effect"), "VAL")
                self.assertEqual(world.events, after)

    def test_stelander_refusal_closes_both_arms_packages(self):
        world = ContractWorld()
        world.data["VAL"]["flags"].update({"VAL_cw_arms_offer_pending", "VAL_cw_trade_course"})
        event = next(e.value for e in entries("events/ADISCORD_STP_events.txt")
                     if e.key == "country_event" and scalar(e.value, "id") == "ADISCORD_STP_cw.50")
        refusal = next(e.value for e in event if e.key == "option" and scalar(e.value, "name") == "ADISCORD_STP_cw.50.b")
        world.execute(block(refusal, "hidden_effect"), "STS")
        self.assertIn("VAL_cw_arms_offer_declined", world.data["VAL"]["flags"])
        self.assertNotIn("VAL_cw_arms_offer_pending", world.data["VAL"]["flags"])
        after = list(world.events)
        world.execute(block(refusal, "hidden_effect"), "STS")
        self.assertEqual(world.events, after)
        for category in entries(DECISIONS):
            if not isinstance(category.value, list):
                continue
            for decision in category.value:
                if decision.key in ("VAL_cw_sell_arms_to_resistance", "VAL_cw_offer_contract_formations"):
                    self.assertFalse(world.matches(block(decision.value, "visible")))

    def test_recognition_preserves_refusal_after_the_offer_cooldown_expires(self):
        world = ContractWorld()
        world.data["VAL"]["rifles"] = {"VAL": 5400}
        world.target = "SLA"
        world.data["RUS"]["vars"]["RUS_crisis_phase"] = 5
        world.data["VAL"]["focuses"].add("VAL_nw_charters")
        partner = world.data["SLA"]
        partner["flags"].update({"VAL_nw_offer_pending", "VAL_nw_offer_cooldown"})
        offer = next(row.value for row in entries("events/ADISCORD_VAL_contract_events.txt")
                     if row.key == "country_event" and scalar(row.value, "id") == "val_rework.125")
        refusal, acceptance = [row.value for row in offer if row.key == "option"]
        ai_guard = [row for row in block(block(refusal, "ai_chance"), "modifier") if row.key != "factor"]
        self.assertFalse(world.matches(ai_guard, "SLA"))
        world.run("VAL_nw_recognize_republic")
        self.assertTrue(world.matches(ai_guard, "SLA"))
        self.assertTrue(world.matches(block(acceptance, "trigger"), "SLA"))
        self.assertFalse(any(row.key == "trigger" for row in refusal))
        world.execute(block(refusal, "hidden_effect"), "SLA")
        self.assertNotIn("VAL_nw_offer_pending", partner["flags"])
        self.assertIn("VAL_nw_offer_cooldown", partner["flags"])
        decision = block(block(entries(DECISIONS), "VAL_new_world_category"), "VAL_nw_offer_concession")
        self.assertFalse(world.matches(block(decision, "available")))
        partner["flags"].discard("VAL_nw_offer_cooldown")
        self.assertIn("VAL_nw_offer_declined", partner["flags"])
        self.assertFalse(world.matches(block(decision, "available")))
        self.assertFalse(world.matches(block(decision, "visible")))
        world.execute(block(decision, "complete_effect"), "VAL")
        self.assertNotIn("VAL_nw_offer_pending", partner["flags"])
        partner["flags"].add("VAL_nw_offer_pending")
        world.execute(block(acceptance, "hidden_effect"), "SLA")
        self.assertEqual(world.data["VAL"]["vars"]["ADISCORD_economy_treasury"], 2000)
        self.assertNotIn("VAL_nw_concession", partner["flags"])

    def test_project_and_resource_rights_invalidate_the_actual_owners_budget(self):
        world = ContractWorld()
        world.data["176"].update(owner="SLA", controller="SLA")
        world.data["SLA"]["subject"] = "VAL"
        world.run("VAL_nw_begin_restoration")
        world.dirty.clear()
        world.run("VAL_nw_finish_project")
        self.assertEqual(world.dirty, {"VAL", "SLA"})
        world.data["SLA"]["flags"].add("VAL_nw_concession")
        world.dirty.clear()
        world.run("VAL_nw_reconcile_rights")
        self.assertEqual(world.dirty, {"VAL", "SLA"})
        world.data["SLA"]["flags"].clear()
        world.dirty.clear()
        world.run("VAL_nw_reconcile_rights")
        self.assertEqual(world.dirty, {"VAL", "SLA"})

    def test_emergency_orders_deliver_during_the_warning_and_refund_when_it_ends(self):
        for name in ("emergency_arsenals", "emergency_reserve"):
            world = ContractWorld()
            world.data["VAL"]["flags"].add("RUS_crisis_warned")
            world.data["RUS"]["vars"]["RUS_crisis_phase"] = 1
            world.run(f"VAL_nw_{name}_begin")
            self.assertIn(f"VAL_nw_{name}_deposit", world.data["VAL"]["vars"])
            world.run(f"VAL_nw_{name}_finish")
            world.run(f"VAL_nw_{name}_finish")
            self.assertNotIn(f"VAL_nw_{name}_deposit", world.data["VAL"]["vars"])
            expected = (10400, 0) if name == "emergency_arsenals" else (5000, 2000)
            self.assertEqual((sum(world.data["VAL"]["rifles"].values()), world.data["VAL"]["manpower"]), expected)
            ended = ContractWorld()
            ended.data["VAL"]["flags"].add("RUS_crisis_warned")
            ended.data["RUS"]["vars"]["RUS_crisis_phase"] = 1
            ended.run(f"VAL_nw_{name}_begin")
            ended.data["RUS"]["vars"]["RUS_crisis_phase"] = 5
            ended.run(f"VAL_nw_{name}_finish")
            self.assertEqual(ended.data["VAL"]["vars"]["ADISCORD_economy_treasury"], 2000)
            self.assertEqual(ended.data["VAL"]["pp"], 1000)

    def test_restoration_charges_once_blocks_other_target_and_delivers_once(self):
        world = ContractWorld()
        self.assertTrue("VAL_nw_begin_restoration" in world.effects, "Restoration receipt is missing")
        world.run("VAL_nw_begin_restoration")
        world.target = "177"
        world.run("VAL_nw_begin_restoration")
        self.assertEqual(world.data["VAL"]["vars"]["ADISCORD_economy_treasury"], 1600)
        self.assertEqual(world.data["VAL"]["pp"], 950)
        self.assertEqual(world.data["VAL"]["vars"]["ADISCORD_economy_current_month_action_costs"], 400)
        world.target = "176"
        world.run("VAL_nw_finish_project")
        world.run("VAL_nw_finish_project")
        self.assertEqual(world.data["176"]["buildings"]["industrial_complex"], 1)
        self.assertEqual(world.data["176"]["slots"], 1)
        self.assertTrue(world.data["176"]["resources"])
        self.assertNotIn("VAL_nw_project_deposit", world.data["VAL"]["vars"])
        world.run("VAL_nw_begin_restoration")
        self.assertEqual(world.data["VAL"]["vars"]["ADISCORD_economy_treasury"], 1600)

    def test_owner_change_refunds_even_when_new_owner_is_another_client(self):
        world = ContractWorld()
        self.assertTrue("VAL_nw_begin_restoration" in world.effects, "Restoration receipt is missing")
        world.run("VAL_nw_begin_restoration")
        world.data["SLA"]["subject"] = "VAL"
        world.data["176"]["owner"] = "SLA"
        world.data["176"]["controller"] = "SLA"
        world.run("VAL_nw_finish_project")
        world.run("VAL_nw_refund_project")
        self.assertEqual(world.data["VAL"]["vars"]["ADISCORD_economy_treasury"], 2000)

    def test_annexation_returns_each_paid_receipt_once_to_the_original_country(self):
        world = ContractWorld()
        world.run("VAL_nw_begin_restoration")
        world.run("VAL_nw_survey_begin")
        world.data["VAL"]["exists"] = False
        world.run("VAL_nw_refund_orders")
        world.run("VAL_nw_refund_orders")
        self.assertEqual(world.data["VAL"]["vars"]["ADISCORD_economy_treasury"], 2000)
        self.assertEqual(world.data["VAL"]["pp"], 1000)
        self.assertFalse([key for key in world.data["VAL"]["vars"] if key.endswith("_deposit")])
        self.assertNotIn("VAL_nw_project_in_progress", world.data["176"]["flags"])
        hooks = entries("common/on_actions/09_ADISCORD_scripted_peace_on_actions.txt")
        annex = block(block(hooks, "on_actions"), "on_annex")
        self.assertEqual(len([e for e in walk(annex) if e.key == "VAL_nw_refund_orders"]), 1)

    def test_roads_at_cap_during_construction_refund_without_marking_completion(self):
        world = ContractWorld()
        world.data["176"]["buildings"]["infrastructure"] = 4
        world.run("VAL_nw_begin_roads")
        world.data["176"]["buildings"]["infrastructure"] = 5
        world.run("VAL_nw_finish_project")
        self.assertEqual(world.data["VAL"]["vars"]["ADISCORD_economy_treasury"], 2000)
        self.assertEqual(world.data["VAL"]["pp"], 1000)
        self.assertNotIn("VAL_nw_roads_restored", world.data["176"]["flags"])

    def test_foreign_stock_is_debited_only_after_consent_and_cannot_be_paid_twice(self):
        world = ContractWorld()
        world.data["VAL"]["rifles"] = {"STS": 5400, "VAL": 0}
        world.data["SLA"]["rifles"] = {}
        world.run("VAL_nw_accept_concession", "SLA")
        self.assertEqual(sum(world.data["VAL"]["rifles"].values()), 5400)
        world.data["SLA"]["flags"].add("VAL_nw_offer_pending")
        world.data["VAL"]["rifles"]["STS"] = 5399.99
        world.run("VAL_nw_accept_concession", "SLA")
        self.assertEqual(sum(world.data["VAL"]["rifles"].values()), 5399.99)
        self.assertEqual(sum(world.data["SLA"]["rifles"].values()), 0)
        self.assertEqual(world.data["VAL"]["vars"]["ADISCORD_economy_treasury"], 2000)
        world.data["VAL"]["rifles"]["STS"] = 5400
        world.run("VAL_nw_accept_concession", "SLA")
        world.run("VAL_nw_accept_concession", "SLA")
        self.assertEqual(sum(world.data["VAL"]["rifles"].values()), 0)
        self.assertEqual(sum(world.data["SLA"]["rifles"].values()), 5400)
        self.assertEqual(world.data["VAL"]["vars"]["ADISCORD_economy_treasury"], 1800)

    def test_ownership_reconciles_rights_between_clients_then_cleans_lost_access(self):
        world = ContractWorld()
        for tag in ("SLA", "RZA"):
            world.data[tag]["flags"].add("VAL_nw_concession")
        world.data["176"]["owner"] = "SLA"
        world.run("VAL_nw_reconcile_rights")
        self.assertEqual(world.data["VAL"]["rights"]["176"], "SLA")
        world.data["176"]["owner"] = "RZA"
        world.run("VAL_nw_reconcile_rights")
        self.assertEqual(world.data["VAL"]["rights"]["176"], "RZA")
        world.data["176"]["owner"] = "RUS"
        world.run("VAL_nw_reconcile_rights")
        self.assertNotIn("176", world.data["VAL"]["rights"])
        self.assertNotIn("VAL_nw_resource_rights", world.data["176"]["flags"])

    def test_new_concession_in_existing_war_starts_protection_without_monthly_wait(self):
        world = ContractWorld()
        world.data["VAL"]["rifles"] = {"VAL": 5400}
        world.data["SLA"]["flags"].add("VAL_nw_offer_pending")
        world.data["SLA"]["wars"].add("RUS")
        world.run("VAL_nw_accept_concession", "SLA")
        self.assertIn("VAL_nw_defence_pending", world.data["SLA"]["flags"])
        self.assertIn(("SLA", "val_rework.131"), world.events)

    def test_peace_clears_pending_before_a_new_threat_gets_its_own_deadline(self):
        world = ContractWorld()
        partner = world.data["SLA"]
        partner["flags"].update({"VAL_nw_concession", "VAL_nw_defence_pending"})
        partner["flag_days"]["VAL_nw_defence_pending"] = 12
        world.run("VAL_nw_reconcile_partner", "SLA")
        self.assertNotIn("VAL_nw_defence_pending", partner["flags"])
        partner["wars"].add("RUS")
        world.run("VAL_nw_reconcile_partner", "SLA")
        self.assertEqual(partner["flag_days"]["VAL_nw_defence_pending"], 0)
        events = entries("events/ADISCORD_VAL_contract_events.txt")
        timeout = next(e.value for e in events if e.key == "country_event"
                       and scalar(e.value, "id") == "val_rework.130")
        world.execute(block(timeout, "immediate"), "SLA")
        self.assertIn("VAL_nw_concession", partner["flags"])
        partner["flag_days"]["VAL_nw_defence_pending"] = 14
        world.execute(block(timeout, "immediate"), "SLA")
        self.assertNotIn("VAL_nw_concession", partner["flags"])
        self.assertEqual(world.data["VAL"]["pp"], 1000)
        self.assertEqual(world.data["176"]["slots"], 0)

    def test_obsolete_visible_notice_timeout_cannot_revoke_a_new_protection_period(self):
        world = ContractWorld()
        partner = world.data["SLA"]
        partner["flags"].add("VAL_nw_concession")
        partner["wars"].add("RUS")
        world.run("VAL_nw_reconcile_partner", "SLA")
        partner["wars"].clear()
        world.run("VAL_nw_reconcile_partner", "SLA")
        partner["wars"].add("RUS")
        world.run("VAL_nw_reconcile_partner", "SLA")
        partner["flag_days"]["VAL_nw_defence_pending"] = 7
        world.target = "SLA"
        notice = next(e.value for e in entries("events/ADISCORD_VAL_contract_events.txt")
                      if e.key == "country_event" and scalar(e.value, "id") == "val_rework.127")
        default = next(e.value for e in notice if e.key == "option")
        self.assertFalse([e for e in walk(default) if e.key not in {"name", "ai_chance", "factor"}])
        world.execute([e for e in default if e.key not in {"name", "ai_chance"}])
        self.assertIn("VAL_nw_concession", partner["flags"])
        self.assertEqual(partner["flag_days"]["VAL_nw_defence_pending"], 7)

    def test_fractional_affordability_and_khan_restoration_cannot_duplicate(self):
        for money, pp in ((399.99, 50), (400, 49.99)):
            world = ContractWorld()
            self.assertTrue("VAL_nw_begin_restoration" in world.effects, "Restoration receipt is missing")
            world.data["VAL"]["vars"]["ADISCORD_economy_treasury"] = money
            world.data["VAL"]["pp"] = pp
            world.run("VAL_nw_begin_restoration")
            self.assertNotIn("VAL_nw_project_deposit", world.data["VAL"]["vars"])
        world = ContractWorld()
        world.data["176"]["flags"].add("RUS_reactor_works_restored")
        world.data["176"]["buildings"]["industrial_complex"] = 1
        world.run("VAL_nw_begin_restoration")
        self.assertEqual(world.data["VAL"]["vars"]["ADISCORD_economy_treasury"], 2000)


class NewWorldRouteTests(unittest.TestCase):
    def test_both_expanded_orders_can_finish_within_a_fresh_warning(self):
        focuses = tree_focuses()
        plan = block(entries("common/ai_strategy_plans/ADISCORD_VAL_plans.txt"), "VAL_new_world_plan")
        order = [e.value for e in block(plan, "ai_national_focuses")]
        days = 0
        for name in order:
            days += int(scalar(focuses[name], "cost")) * 7
            if name == "VAL_nw_khan":
                break
        self.assertEqual(days, 14)
        decisions = block(entries(DECISIONS), "VAL_new_world_category")
        # The expanded order reuses the emergency deposit, so each pair runs in sequence.
        finishes = {kind: days + 2 * int(scalar(block(decisions, "VAL_nw_emergency_" + kind), "days_remove"))
                    for kind in ("arsenals", "reserve")}
        self.assertEqual(finishes, {"arsenals": 56, "reserve": 74})

    def test_finale_does_not_require_finishing_the_military_or_all_side_programmes(self):
        focuses = tree_focuses()
        war = {"VAL_nw_tsaygen_strike", "VAL_nw_beyond_perimeter", "VAL_nw_zones"}
        roots = {"VAL_peace_throne", "VAL_peace_cabinet", "VAL_peace_charter", "VAL_peace_captains"}
        for chosen in (
            {"VAL_nw_register", "VAL_nw_bloc_accord", "VAL_nw_foundries", "VAL_peace_water_convoys",
             "VAL_peace_registry_audit", "VAL_peace_workers_charter", "VAL_east_shards"},
            {"VAL_nw_charters", "VAL_nw_bloc_confront", "VAL_nw_dispatch", "VAL_peace_gate_garrison",
             "VAL_peace_share_ledger", "VAL_peace_shift_law", "VAL_east_arsenal"},
        ):
            for regime in sorted(roots):
                excluded = set(war) | (roots - {regime})
                for name in chosen:
                    excluded |= {e.value for group in (e.value for e in focuses[name] if e.key == "mutually_exclusive")
                                 for e in group if e.key == "focus"}
                reachable = set()
                for _ in range(len(focuses)):
                    for name, focus in focuses.items():
                        if name in excluded:
                            continue
                        prerequisites = [e.value for e in focus if e.key == "prerequisite"]
                        if all(any(p.value in reachable for p in group) for group in prerequisites):
                            reachable.add(name)
                self.assertIn("VAL_nw_steel_peace", reachable, (chosen, regime))
        final_conditions = [e.value for e in walk(block(focuses["VAL_nw_steel_peace"], "available"))
                            if e.key == "has_global_flag"]
        self.assertEqual(final_conditions, ["VAL_east_final_resolved", "VAL_east_hegemon_rival"])

    def test_recognition_is_rechecked_in_the_shared_settlement_effect(self):
        roots = entries("common/decisions/ADISCORD_RUS_decisions.txt")
        candidates = [e.value for e in walk(roots) if e.key == "RUS_crisis_establish_special_zone"]
        self.assertEqual(len(candidates), 1)
        for field in ("available", "complete_effect"):
            self.assertIn("VAL_nw_special_zone_permitted", {e.key for e in walk(block(candidates[0], field))})

    def test_dynamic_delta_previews_are_never_installed(self):
        tree = block(entries(TREE), "focus_tree")
        for name in ("VAL_nw_industry_delta", "VAL_nw_trade_delta", "VAL_nw_admin_delta"):
            owners = [e.value for e in tree if e.key == "focus"
                      and any(x.key == "add_ideas" and x.value == name for x in walk(e.value))]
            self.assertEqual(len(owners), 1)
            reward = block(owners[0], "completion_reward")
            self.assertEqual(scalar(block(reward, "effect_tooltip"), "add_ideas"), name)
            real = [e for e in reward if e.key != "effect_tooltip"]
            self.assertFalse([e for e in walk(real) if e.key == "add_ideas"])

    def test_new_localisation_quotes_encodings_and_cost_variants(self):
        languages = {}
        for language in ("russian", "english"):
            path = ROOT / f"localisation/{language}/ADISCORD_VAL_decisions_l_{language}.yml"
            self.assertTrue(path.read_bytes().startswith(b"\xef\xbb\xbf"))
            rows = {}
            for line in path.read_text(encoding="utf-8-sig").splitlines():
                if re.match(r"\s+(?:VAL_nw_|VAL_peace_|VAL_throne_|VAL_cabinet_|VAL_charter_|VAL_captains_|VAL_east_|val_peace\.|val_rework\.(?:12[4-9]|13[014-8]|18[0-4]))", line):
                    match = re.fullmatch(r' ([\w.]+):\d+ "([^"\\]*(?:\\.[^"\\]*)*)"', line)
                    self.assertIsNotNone(match, line)
                    self.assertNotIn(match[1], rows)
                    rows[match[1]] = match[2]
                    if re.match(r"val_rework\.(?:124|129|13[4-8]|18[0-4])\.(?:d|solgalov|staff)$", match[1]):
                        rendered = match[2].replace(r"\n", "\n")
                        self.assertLessEqual(len(rendered), 3000, match[1])
                        self.assertLessEqual(len(rendered.encode("utf-8")), 5500, match[1])
            languages[language] = rows
        self.assertEqual(languages["russian"].keys(), languages["english"].keys())
        for decision in block(entries(DECISIONS), "VAL_new_world_category"):
            costs = [e.value for e in decision.value if e.key == "custom_cost_text"]
            for key in costs:
                self.assertEqual(scalar(decision.value, "cost"), "0")
                for suffix in ("", "_blocked", "_tooltip"):
                    self.assertIn(key + suffix, languages["russian"])
        tree = block(entries(TREE), "focus_tree")
        for focus in (e.value for e in tree if e.key == "focus"):
            name = scalar(focus, "id")
            self.assertIn(name, languages["russian"])
            self.assertIn(name + "_desc", languages["russian"])
        for name in (TREE, EFFECTS, TRIGGERS, DECISIONS):
            self.assertFalse((ROOT / name).read_bytes().startswith(b"\xef\xbb\xbf"))

    def test_ai_plan_covers_the_new_tree_and_stops_with_its_replacement(self):
        plans = entries("common/ai_strategy_plans/ADISCORD_VAL_plans.txt")
        plan = next(e.value for e in plans if e.key == "VAL_new_world_plan")
        self.assertIn("VAL_new_world_focus", [e.value for e in walk(block(plan, "enable")) if e.key == "has_focus_tree"])
        self.assertIn("VAL_new_world_focus", [e.value for e in walk(block(plan, "abort")) if e.key == "has_focus_tree"])
        focuses = tree_focuses()
        order = [e.value for e in block(plan, "ai_national_focuses")]
        self.assertLessEqual(set(order), set(focuses))
        self.assertIn("VAL_nw_steel_peace", order)
        completed = set()
        for name in order:
            prerequisites = [e.value for e in focuses[name] if e.key == "prerequisite"]
            self.assertTrue(all(any(p.value in completed for p in group) for group in prerequisites), name)
            completed.add(name)
        for name, focus in focuses.items():
            for exclusive in (e.value for e in focus if e.key == "mutually_exclusive"):
                group = {name} | {e.value for e in exclusive if e.key == "focus"}
                self.assertEqual(len(group & completed), 1, group)

    def test_transition_preserves_completed_unlocks_and_runs_without_event_answer(self):
        events = entries("events/ADISCORD_VAL_contract_events.txt")
        event = next(e.value for e in events if e.key == "country_event"
                     and scalar(e.value, "id") == "val_rework.124")
        self.assertEqual(scalar(block(event, "immediate"), "VAL_nw_open_chapter"), "yes")
        transition = block(entries(EFFECTS), "VAL_nw_open_chapter")
        loads = [e.value for e in walk(transition) if e.key == "load_focus_tree"]
        self.assertEqual(len(loads), 1)
        self.assertEqual(scalar(loads[0], "tree"), "VAL_new_world_focus")
        self.assertEqual(scalar(loads[0], "keep_completed"), "yes")
        destructive = {"clear_variable", "clr_country_flag", "remove_decision", "remove_mission"}
        self.assertFalse([e.key for e in walk(transition) if e.key in destructive])

    def test_new_tree_is_registered_complete_and_has_no_unreachable_prerequisites(self):
        self.assertEqual(SOURCES.get("VAL/new_world/focuses.txt"), "ADISCORD_VAL_new_world.txt")
        focuses = tree_focuses()
        self.assertEqual(len(focuses), 88)
        reachable = set()
        for _ in range(len(focuses)):
            for name, focus in focuses.items():
                prerequisites = [e.value for e in focus if e.key == "prerequisite"]
                if all(any(p.value in reachable for p in group) for group in prerequisites):
                    reachable.add(name)
                for group in prerequisites:
                    self.assertTrue(all(p.value in focuses for p in group), name)
                # Only the settlement-rights branch and the chosen regime are gated.
                gates = [e.value for e in focus if e.key == "allow_branch"]
                if name != "VAL_nw_zones" and gates:
                    self.assertEqual(len(gates[0]), 1, name)
                    self.assertTrue(gates[0][0].key.startswith("VAL_peace_regime_"), name)
        self.assertEqual(reachable, set(focuses))
        # Regime lanes never share a cell, so any set of visible branches stays readable.
        places = {(scalar(f, "x"), scalar(f, "y")) for f in focuses.values()}
        self.assertEqual(len(places), 88)

    def test_every_branch_has_a_symmetric_exclusive_pair(self):
        focuses = tree_focuses()
        pairs = set()
        for name, focus in focuses.items():
            for exclusive in (e.value for e in focus if e.key == "mutually_exclusive"):
                rivals = {e.value for e in exclusive if e.key == "focus"}
                for rival in rivals:
                    rival_list = {e.value for group in (g.value for g in focuses[rival] if g.key == "mutually_exclusive")
                                  for e in group if e.key == "focus"}
                    self.assertIn(name, rival_list)
                pairs.add(frozenset({name} | rivals))
        self.assertEqual(pairs, {
            frozenset(("VAL_nw_register", "VAL_nw_charters")),
            frozenset(("VAL_nw_bloc_accord", "VAL_nw_bloc_confront")),
            frozenset(("VAL_nw_foundries", "VAL_nw_dispatch")),
            frozenset(("VAL_peace_water_convoys", "VAL_peace_gate_garrison")),
            frozenset(("VAL_peace_registry_audit", "VAL_peace_share_ledger")),
            frozenset(("VAL_peace_land_for_service", "VAL_peace_workers_charter", "VAL_peace_shift_law")),
            frozenset(("VAL_throne_heir_officer", "VAL_throne_heir_clerk")),
            frozenset(("VAL_throne_purge", "VAL_throne_patents")),
            frozenset(("VAL_throne_memorial", "VAL_throne_confession")),
            frozenset(("VAL_cabinet_open_estimates", "VAL_cabinet_velsky_apparatus")),
            frozenset(("VAL_cabinet_highland_bread", "VAL_cabinet_zone_clearing")),
            frozenset(("VAL_charter_district_captains", "VAL_charter_single_staff")),
            frozenset(("VAL_charter_tribunal", "VAL_charter_silence")),
            frozenset(("VAL_captains_common_purse", "VAL_captains_shares_forever")),
            frozenset(("VAL_captains_greitz_passes", "VAL_captains_river_raids")),
            frozenset(("VAL_east_trade_missions", "VAL_east_krutov_network")),
            frozenset(("VAL_east_shards", "VAL_east_arsenal")),
        })
        for pair in pairs:
            self.assertEqual(len({scalar(focuses[name], "y") for name in pair}), 1, pair)
            for name in pair:
                rewards = [e.key for e in block(focuses[name], "completion_reward")]
                self.assertTrue(rewards, name)

    def test_main_tree_campaign_operations_accept_the_new_tree_route(self):
        for name, trigger in (
            ("VAL_operation_return_southern_tsaygen", "VAL_tsaygen_campaign_opened"),
            ("VAL_frontier_demand_ERT", "VAL_tsaygen_campaign_opened"),
            ("VAL_operation_cross_perimeter", "VAL_perimeter_campaign_opened"),
            ("VAL_operation_secure_perimeter", "VAL_perimeter_campaign_opened"),
        ):
            decision = next(e.value for e in walk(entries(DECISIONS)) if e.key == name)
            self.assertEqual(scalar(block(decision, "visible"), trigger), "yes", name)
        world = ContractWorld()
        self.assertFalse(world.matches(world.triggers["VAL_tsaygen_campaign_opened"]))
        world.data["VAL"]["focuses"].add("VAL_nw_tsaygen_strike")
        self.assertTrue(world.matches(world.triggers["VAL_tsaygen_campaign_opened"]))
        begin = block(entries(EFFECTS), "VAL_begin_southern_tsaygen_campaign")
        self.assertEqual(scalar(block(block(begin, "if"), "limit"), "VAL_tsaygen_campaign_opened"), "yes")


class NewWorldSettlementTests(unittest.TestCase):
    @staticmethod
    def modifier_variables():
        modifiers = entries("common/dynamic_modifiers/ADISCORD_VAL_contract_dynamic_modifier.txt")
        variables = {}
        for name in ("VAL_nw_industrial_network", "VAL_peace_order"):
            variables.update({e.value: e.key for e in block(modifiers, name) if e.key not in ("enable", "icon")})
        return variables

    @staticmethod
    def preview(name):
        ideas = block(block(entries(IDEAS), "ideas"), "country")
        return {e.key: float(e.value) for e in block(block(ideas, name), "modifier")}

    def applied(self, world, before):
        variables = self.modifier_variables()
        after = world.data["VAL"]["vars"]
        delta = {}
        for variable, modifier in variables.items():
            change = round(after.get(variable, 0) - before.get(variable, 0), 6)
            if change:
                delta[modifier] = round(delta.get(modifier, 0) + change, 6)
        return delta

    def test_root_waits_for_paid_consolidation_and_opens_the_settlement(self):
        root = tree_focuses()["VAL_nw_price"]
        world = ContractWorld()
        world.data["VAL"]["vars"]["VAL_command_consolidation_kind"] = 2
        self.assertFalse(world.matches(block(root, "available")))
        del world.data["VAL"]["vars"]["VAL_command_consolidation_kind"]
        self.assertTrue(world.matches(block(root, "available")))
        world.data["VAL"]["bop"]["VAL_command_balance"] = 0.3
        world.execute(block(root, "completion_reward"))
        self.assertEqual(world.events, [("VAL", "val_rework.180")])
        self.assertEqual(world.data["VAL"]["pp"], 1000)
        council = ContractWorld()
        council.execute(block(root, "completion_reward"))
        self.assertEqual((council.events, council.data["VAL"]["pp"]), ([], 1050))

    def test_each_command_range_keeps_two_answers_and_settles_once(self):
        event = country_event("val_rework.180")
        options = [e.value for e in event if e.key == "option"]
        expected = {0.5: ["val_rework.180.a", "val_rework.180.b"],
                    0.0: ["val_rework.180.a", "val_rework.180.b", "val_rework.180.c"],
                    -0.5: ["val_rework.180.b", "val_rework.180.c"]}
        for value, names in expected.items():
            with self.subTest(value=value):
                world = ContractWorld()
                world.data["VAL"]["bop"]["VAL_command_balance"] = value
                available = [option for option in options
                             if not [e for e in option if e.key == "trigger"]
                             or world.matches(block(option, "trigger"))]
                self.assertEqual([scalar(option, "name") for option in available], names)
                descriptions = [e.value for e in event if e.key == "desc"]
                self.assertEqual(sum(world.matches(block(desc, "trigger")) for desc in descriptions), 1)
        for option in options:
            with self.subTest(option=scalar(option, "name")):
                world = ContractWorld()
                world.data["VAL"]["bop"]["VAL_command_balance"] = 0.0
                world.data["VAL"]["flags"].add("VAL_command_conspiracy_exposed")
                world.data["VAL"]["missions"].add("VAL_council_ultimatum")
                world.execute(block(option, "hidden_effect"))
                preview = scalar(block(option, "effect_tooltip"), "add_ideas")
                self.assertEqual(self.applied(world, {}), self.preview(preview))
                self.assertNotIn("VAL_command_balance", world.data["VAL"]["bop"])
                self.assertNotIn("VAL_command_conspiracy_exposed", world.data["VAL"]["flags"])
                self.assertFalse(world.data["VAL"]["missions"])
                self.assertEqual(world.data["VAL"]["modifiers"], {"VAL_nw_industrial_network"})
                # The answer removes the balance that the event requires, so it cannot fire again.
                self.assertFalse(world.matches(block(event, "trigger")))
        root = tree_focuses()["VAL_nw_price"]
        self.assertFalse(any(e.key == "repeatable" for e in root))
        senders = [path for path in (ROOT / "common").rglob("*.txt")
                   if "id = val_rework.180 " in path.read_text(encoding="utf-8-sig", errors="replace")]
        self.assertEqual([p.relative_to(ROOT).as_posix() for p in senders],
                         ["common/national_focus/ADISCORD_VAL_new_world.txt"])

    def test_focus_delta_previews_match_applied_values(self):
        for name, focus in tree_focuses().items():
            reward = block(focus, "completion_reward")
            previews = [e.value for e in reward if e.key == "effect_tooltip"]
            if not previews:
                continue
            with self.subTest(focus=name):
                world = ContractWorld()
                world.execute(block(reward, "hidden_effect"))
                self.assertEqual(self.applied(world, {}), self.preview(scalar(previews[0], "add_ideas")))

    def tsaygen_world(self):
        world = ContractWorld()
        world.data["VAL"]["focuses"].add("VAL_nw_bloc_accord")
        world.data["168"].update(owner="ERT", controller="ERT")
        world.data["ERT"]["faction"] = "victors"
        world.data["ERT"]["vars"]["ADISCORD_economy_treasury"] = 0
        return world

    def test_tsaygen_sale_is_paid_only_after_consent_and_transfers_once(self):
        world = self.tsaygen_world()
        world.run("VAL_nw_offer_tsaygen_sale")
        world.run("VAL_nw_offer_tsaygen_sale")
        self.assertEqual(world.events, [("ERT", "val_rework.181")])
        self.assertEqual(world.data["VAL"]["vars"]["ADISCORD_economy_treasury"], 2000)
        self.assertIn("VAL_nw_tsaygen_offer_cooldown", world.data["VAL"]["flags"])
        world.run("VAL_nw_accept_tsaygen_sale", "ERT")
        world.run("VAL_nw_accept_tsaygen_sale", "ERT")
        self.assertEqual(world.data["VAL"]["vars"]["ADISCORD_economy_treasury"], 1500)
        self.assertEqual(world.data["VAL"]["pp"], 925)
        self.assertEqual(world.data["ERT"]["vars"]["ADISCORD_economy_treasury"], 500)
        self.assertEqual((world.data["168"]["owner"], world.data["168"]["controller"]), ("VAL", "VAL"))
        self.assertEqual(world.events[1:], [("VAL", "val_rework.182")])
        for treasury, pp in ((499.99, 75), (500, 74.99)):
            with self.subTest(treasury=treasury, pp=pp):
                short = self.tsaygen_world()
                short.run("VAL_nw_offer_tsaygen_sale")
                short.data["VAL"]["vars"]["ADISCORD_economy_treasury"] = treasury
                short.data["VAL"]["pp"] = pp
                short.run("VAL_nw_accept_tsaygen_sale", "ERT")
                self.assertEqual(short.data["168"]["owner"], "ERT")
                self.assertEqual(short.data["ERT"]["vars"]["ADISCORD_economy_treasury"], 0)
                self.assertEqual(short.events[1:], [("VAL", "val_rework.183")])
                self.assertNotIn("VAL_nw_tsaygen_offer_pending", short.data["ERT"]["flags"])
        offer = country_event("val_rework.181")
        refusal = next(e.value for e in offer if e.key == "option")
        self.assertFalse([e for e in refusal if e.key == "trigger"])
        self.assertEqual(scalar(block(refusal, "hidden_effect"), "VAL_nw_decline_tsaygen_sale"), "yes")

    def bloc_world(self):
        world = ContractWorld()
        world.data["VAL"]["focuses"].add("VAL_nw_bloc_confront")
        for tag in ("ERT", "SLA"):
            world.data[tag]["faction"] = "victors"
        world.data["MON"].update(faction="victors", leader=True)
        world.target = "ERT"
        return world

    def test_alliance_campaign_holds_one_deposit_and_detaches_once(self):
        world = self.bloc_world()
        world.run("VAL_nw_detach_begin")
        world.target = "SLA"
        world.run("VAL_nw_detach_begin")
        self.assertEqual(world.data["VAL"]["vars"]["ADISCORD_economy_treasury"], 1750)
        self.assertEqual(world.data["VAL"]["pp"], 900)
        self.assertNotIn("VAL_nw_detach_target", world.data["SLA"]["flags"])
        world.run("VAL_nw_detach_finish")
        self.assertEqual(world.data["SLA"]["faction"], "victors")
        world.target = "ERT"
        world.run("VAL_nw_detach_finish")
        world.run("VAL_nw_detach_finish")
        self.assertIsNone(world.data["ERT"]["faction"])
        self.assertNotIn("VAL_nw_detach_deposit", world.data["VAL"]["vars"])
        self.assertEqual(world.events, [("VAL", "val_rework.184")])
        self.assertEqual(world.data["VAL"]["vars"]["ADISCORD_economy_treasury"], 1750)
        for interruption in ("left", "player", "war"):
            with self.subTest(interruption=interruption):
                failed = self.bloc_world()
                failed.run("VAL_nw_detach_begin")
                if interruption == "left":
                    failed.data["ERT"]["faction"] = None
                elif interruption == "player":
                    failed.data["ERT"]["ai"] = False
                else:
                    failed.data["ERT"]["wars"].add("SCA")
                failed.run("VAL_nw_detach_finish")
                self.assertEqual(failed.data["VAL"]["vars"]["ADISCORD_economy_treasury"], 2000)
                self.assertEqual(failed.data["VAL"]["pp"], 1000)
                self.assertNotIn("VAL_nw_detach_target", failed.data["ERT"]["flags"])
                self.assertFalse(failed.events)
        annexed = self.bloc_world()
        annexed.run("VAL_nw_detach_begin")
        annexed.run("VAL_nw_refund_orders")
        annexed.run("VAL_nw_refund_orders")
        self.assertEqual(annexed.data["VAL"]["vars"]["ADISCORD_economy_treasury"], 2000)
        decision = block(block(entries(DECISIONS), "VAL_new_world_category"), "VAL_nw_detach_republic")
        self.assertEqual([e.value for e in block(decision, "targets")], list(PARTNERS))
        self.assertEqual(scalar(block(decision, "cancel_effect")[0].value, "VAL_nw_detach_refund"), "yes")

    def test_accord_admits_members_of_the_khans_victors_as_partners(self):
        world = ContractWorld()
        world.target = "SLA"
        world.data["SLA"]["faction"] = "victors"
        self.assertFalse(world.matches(world.triggers["VAL_nw_partner_eligible"], "SLA"))
        world.data["VAL"]["focuses"].add("VAL_nw_bloc_accord")
        self.assertTrue(world.matches(world.triggers["VAL_nw_partner_eligible"], "SLA"))
        world.data["RUS"]["faction"] = "victors"
        self.assertFalse(world.matches(world.triggers["VAL_nw_partner_eligible"], "SLA"))

    def test_emergency_preparation_does_not_require_late_tree(self):
        decisions = block(entries(DECISIONS), "VAL_new_world_category")
        for name in ("VAL_nw_emergency_arsenals", "VAL_nw_emergency_reserve"):
            decision = block(decisions, name)
            self.assertEqual(scalar(block(decision, "visible"), "VAL_nw_khan_threat"), "yes")
            self.assertFalse([e for e in walk(block(decision, "available")) if e.key == "has_completed_focus"])
            self.assertLessEqual(int(scalar(decision, "days_remove")), 30)


if __name__ == "__main__":
    unittest.main()
