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
            "manpower": 0,
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
                result.append(any(self.matches([child], scope) for child in value))
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
            elif isinstance(value, list) and (key.isdigit() or key in ("VAL", "RUS", "FROM", "owner", "controller")):
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
        world.run("VAL_nw_begin_restoration")
        self.assertEqual(world.data["VAL"]["vars"]["ADISCORD_economy_treasury"], 2000)


class NewWorldRouteTests(unittest.TestCase):
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
                if re.match(r"\s+(?:VAL_nw_|val_rework\.(?:12[5-9]|13[01]))", line):
                    match = re.fullmatch(r' ([\w.]+):\d+ "([^"\\]*(?:\\.[^"\\]*)*)"', line)
                    self.assertIsNotNone(match, line)
                    self.assertNotIn(match[1], rows)
                    rows[match[1]] = match[2]
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
        self.assertEqual(len(focuses), 27)
        reachable = set()
        for _ in range(27):
            for name, focus in focuses.items():
                prerequisites = [e.value for e in focus if e.key == "prerequisite"]
                if all(any(p.value in reachable for p in group) for group in prerequisites):
                    reachable.add(name)
                for group in prerequisites:
                    self.assertTrue(all(p.value in focuses for p in group), name)
                self.assertNotIn("allow_branch", {e.key for e in focus}, name)
        self.assertEqual(reachable, set(focuses))
        self.assertEqual(len({(scalar(f, "x"), scalar(f, "y")) for f in focuses.values()}), 27)

    def test_emergency_preparation_does_not_require_late_tree(self):
        decisions = block(entries(DECISIONS), "VAL_new_world_category")
        for name in ("VAL_nw_emergency_arsenals", "VAL_nw_emergency_reserve"):
            decision = block(decisions, name)
            self.assertEqual(scalar(block(decision, "visible"), "VAL_nw_khan_threat"), "yes")
            self.assertFalse([e for e in walk(block(decision, "available")) if e.key == "has_completed_focus"])
            self.assertLessEqual(int(scalar(decision, "days_remove")), 30)


if __name__ == "__main__":
    unittest.main()
