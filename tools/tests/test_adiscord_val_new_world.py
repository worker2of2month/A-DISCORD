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


class ContractWorld:
    """Execute the parsed receipts; external economy refresh and native timers are boundaries."""

    def __init__(self):
        self.effects = {}
        self.triggers = {}
        for path in (EFFECTS, "common/scripted_effects/ADISCORD_vorkerland_effects.txt"):
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
            "research_bonuses": [],
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
                result.append(False)
            elif key == "is_in_faction":
                result.append(value == "no")
            elif isinstance(value, list) and (key.isdigit() or key in ("VAL", "RUS", "FROM", "owner", "controller", "SLA", "RZA", "MLR", "ERT", "IRT", "SCA", "TMR", "VEL", "RLY")):
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
            elif key == "custom_effect_tooltip":
                pass
            elif isinstance(value, list) and (key.isdigit() or key in ("VAL", "RUS", "FROM", "owner", "controller")):
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
        world.data["VAL"]["focuses"].add("VAL_nw_" + kind)
        return world

    def test_expanded_orders_preserve_quotes_and_reject_other_tier_callbacks(self):
        for kind, base_price, expanded_price, expected_rifles, expected_manpower in (
            ("arsenals", 150, 250, 6800, 0),
            ("reserve", 200, 300, 5000, 5000),
        ):
            with self.subTest(kind=kind):
                world = self.warning(kind)
                country = world.data["VAL"]
                country["focuses"].clear()
                base = "VAL_nw_emergency_" + kind
                expanded = "VAL_nw_expanded_" + kind
                world.run(base + "_begin")
                country["focuses"].add("VAL_nw_" + kind)
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
                    country["focuses"].update({"VAL_nw_reserve", "VAL_nw_perimeter", "VAL_nw_archives"})
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

    def test_recognition_updates_open_offer_but_keeps_player_refusal_and_cooldown(self):
        world = ContractWorld()
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
        self.assertTrue(world.matches(block(decision, "available")))
        partner["flags"].add("VAL_nw_offer_pending")
        world.execute(block(acceptance, "hidden_effect"), "SLA")
        self.assertEqual(world.data["VAL"]["vars"]["ADISCORD_economy_treasury"], 1800)
        self.assertIn("VAL_nw_concession", partner["flags"])

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
            expected = (5600, 0) if name == "emergency_arsenals" else (5000, 2000)
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
        world.data["VAL"]["rifles"] = {"STS": 600, "VAL": 0}
        world.data["SLA"]["rifles"] = {}
        world.run("VAL_nw_accept_concession", "SLA")
        self.assertEqual(sum(world.data["VAL"]["rifles"].values()), 600)
        world.data["SLA"]["flags"].add("VAL_nw_offer_pending")
        world.run("VAL_nw_accept_concession", "SLA")
        world.run("VAL_nw_accept_concession", "SLA")
        self.assertEqual(sum(world.data["VAL"]["rifles"].values()), 0)
        self.assertEqual(sum(world.data["SLA"]["rifles"].values()), 600)
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
        focuses = {scalar(e.value, "id"): e.value for e in block(entries(TREE), "focus_tree") if e.key == "focus"}
        plan = block(entries("common/ai_strategy_plans/ADISCORD_VAL_plans.txt"), "VAL_new_world_plan")
        order = [e.value for e in block(plan, "ai_national_focuses")]
        days = 0
        finishes = {}
        completed = set()
        for name in order:
            focus = focuses[name]
            prerequisites = [e.value for e in focus if e.key == "prerequisite"]
            self.assertTrue(all(any(p.value in completed for p in group) for group in prerequisites), name)
            days += int(scalar(focus, "cost")) * 7
            completed.add(name)
            if name == "VAL_nw_reserve":
                finishes["reserve"] = days + 30
            if name == "VAL_nw_arsenals":
                finishes["arsenals"] = days + 21
                break
        self.assertEqual(finishes, {"reserve": 79, "arsenals": 84})

    def test_finale_does_not_require_finishing_the_military_or_all_side_programmes(self):
        focuses = {scalar(e.value, "id"): e.value for e in block(entries(TREE), "focus_tree") if e.key == "focus"}
        skipped = {"VAL_nw_" + name for name in ("khan", "defence", "staff", "arsenals", "reserve", "break_ring", "last_account", "zones", "roads", "restitution", "guarantor", "observers")}
        reachable = set()
        for _ in range(len(focuses)):
            for name, focus in focuses.items():
                if name in skipped:
                    continue
                prerequisites = [e.value for e in focus if e.key == "prerequisite"]
                if all(any(p.value in reachable for p in group) for group in prerequisites):
                    reachable.add(name)
        self.assertIn("VAL_nw_steel_peace", reachable)
        final_conditions = block(focuses["VAL_nw_steel_peace"], "available")
        world = ContractWorld()
        world.data["RUS"]["vars"]["RUS_crisis_phase"] = 5
        for state in ("176", "177"):
            world.data[state]["flags"].add("RUS_reactor_works_restored")
            world.data[state]["buildings"]["industrial_complex"] = 1
        self.assertTrue(world.matches(final_conditions))

    def test_recognition_is_rechecked_in_the_shared_settlement_effect(self):
        roots = entries("common/decisions/ADISCORD_vorkerland_decisions.txt")
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
                if re.match(r"\s+(?:VAL_nw_|val_rework\.(?:12[4-9]|13[014-8]))", line):
                    match = re.fullmatch(r' ([\w.]+):\d+ "([^"\\]*(?:\\.[^"\\]*)*)"', line)
                    self.assertIsNotNone(match, line)
                    self.assertNotIn(match[1], rows)
                    rows[match[1]] = match[2]
                    if re.match(r"val_rework\.(?:124|129|13[4-8])\.d", match[1]):
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
        focuses = {scalar(e.value, "id") for e in block(entries(TREE), "focus_tree") if e.key == "focus"}
        self.assertEqual({e.value for e in block(plan, "ai_national_focuses")}, focuses)

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
        tree = block(entries(TREE), "focus_tree")
        focuses = {scalar(e.value, "id"): e.value for e in tree if e.key == "focus"}
        self.assertEqual(len(focuses), 36)
        reachable = set()
        for _ in range(len(focuses)):
            for name, focus in focuses.items():
                prerequisites = [e.value for e in focus if e.key == "prerequisite"]
                if all(any(p.value in reachable for p in group) for group in prerequisites):
                    reachable.add(name)
                for group in prerequisites:
                    self.assertTrue(all(p.value in focuses for p in group), name)
                self.assertNotIn("allow_branch", {e.key for e in focus}, name)
        self.assertEqual(reachable, set(focuses))
        self.assertEqual(len({(scalar(f, "x"), scalar(f, "y")) for f in focuses.values()}), 36)

    def test_emergency_preparation_does_not_require_late_tree(self):
        decisions = block(entries(DECISIONS), "VAL_new_world_category")
        for name in ("VAL_nw_emergency_arsenals", "VAL_nw_emergency_reserve"):
            decision = block(decisions, name)
            self.assertEqual(scalar(block(decision, "visible"), "VAL_nw_khan_threat"), "yes")
            self.assertFalse([e for e in walk(block(decision, "available")) if e.key == "has_completed_focus"])
            self.assertLessEqual(int(scalar(decision, "days_remove")), 30)


if __name__ == "__main__":
    unittest.main()
