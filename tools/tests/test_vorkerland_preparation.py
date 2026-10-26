"""Execute the preparation accounting subset from source, not a second model.

Native unit spawning, faction membership and GUI rendering still require HOI4.
Those engine boundaries are recorded explicitly; unknown syntax fails closed.
"""

from __future__ import annotations

from collections import defaultdict
from copy import deepcopy
from dataclasses import dataclass, field
from pathlib import Path
from itertools import product
import re
import unittest

from tools.validators.validate_adiscord_division_templates import parse_clausewitz


ROOT = Path(__file__).resolve().parents[2]
P = "ADISCORD_vorkerland_prep_"
V = "ADISCORD_vorkerland_"
SITES = (32, 33, 36, 37, 38, 40)


def read(path):
    return (ROOT / path).read_text(encoding="utf-8-sig")


def normalized(entries):
    result = []
    index = 0
    while index < len(entries):
        entry = entries[index]
        if not entry.key and index + 2 < len(entries):
            operator = entries[index + 1].value
            if operator in ("<", ">", "<=", ">="):
                result.append((entry.value, operator, entries[index + 2].value))
                index += 3
                continue
        value = normalized(entry.value) if isinstance(entry.value, list) else entry.value
        result.append((entry.key, "=", value))
        index += 1
    return result


def parse(text):
    return normalized(parse_clausewitz(text))


def fields(block):
    return {key: value for key, _, value in block}


def walk(block):
    for key, operator, value in block:
        yield key, operator, value
        if isinstance(value, list):
            yield from walk(value)


EFFECTS = fields(parse(read("common/scripted_effects/ADISCORD_vorkerland_effects.txt")))
TRIGGERS = fields(parse(read("common/scripted_triggers/ADISCORD_vorkerland_triggers.txt")))
DECISIONS = {
    key: value
    for key, _, value in walk(parse(read("common/decisions/ADISCORD_vorkerland_decisions.txt")))
    if key.startswith(P) and isinstance(value, list)
}
EVENTS = {
    fields(value)["id"]: value
    for key, _, value in parse(read("events/ADISCORD_vorkerland_events.txt"))
    if key == "country_event"
}
PROJECTS = {
    name: block for name, block in DECISIONS.items()
    if "days_remove" in fields(block) and "state_target" in fields(block)
}


@dataclass
class Scope:
    variables: dict = field(default_factory=dict)
    flags: set = field(default_factory=set)
    resources: dict = field(default_factory=lambda: defaultdict(float))
    focuses: set = field(default_factory=set)
    owner: str = "WRK"
    controller: str = "WRK"
    exists: bool = True
    subject: str | None = None
    faction: str | None = None
    capitulated: bool = False
    enemies: set = field(default_factory=set)


class Script:
    def __init__(self):
        self.scopes = defaultdict(Scope)
        self.globals = {V + "phase_prewar"}
        self.calls = []
        self.root = "WRK"
        self.source = "32"
        self.scopes["WRK"].variables[P + "patron"] = 1
        self.scopes["WRK"].resources.update(
            pp=1000, command=100, people=30000,
            infantry_equipment=30000, support_equipment=1000, train_equipment=100,
        )
        self.scopes["WRK"].focuses = {
            value for _, block in PROJECTS.items()
            for key, _, value in walk(block) if key == "has_completed_focus"
        }

    def scope(self, key, current, previous):
        if key == "ROOT":
            return self.root
        if key == "FROM":
            return self.source
        if key == "PREV":
            return previous
        if key == "capital_scope":
            return "capital_" + current
        if key.isdigit() or re.fullmatch(r"[A-Z]{3}", key):
            return key
        return None

    def number(self, value, current, previous):
        try:
            return float(value)
        except ValueError:
            if "." in value:
                prefix, name = value.split(".", 1)
                current = self.scope(prefix, current, previous)
            else:
                name = value
            return self.scopes[current].variables.get(name, 0)

    def conditions(self, block, current=None, previous=None):
        current = current or self.root
        state = self.scopes[current]
        for key, operator, value in block:
            if operator != "=":
                resource = {"has_political_power": "pp", "command_power": "command", "has_manpower": "people"}.get(key, key)
                actual = state.resources[resource]
                expected = self.number(value, current, previous)
                ok = {"<": actual < expected, ">": actual > expected, "<=": actual <= expected, ">=": actual >= expected}[operator]
            elif key in ("AND", "hidden_trigger", "has_equipment"):
                ok = self.conditions(value, current, previous)
            elif key == "custom_trigger_tooltip":
                ok = self.conditions([item for item in value if item[0] != "tooltip"], current, previous)
            elif key == "OR":
                ok = any(self.conditions([item], current, previous) for item in value)
            elif key == "NOT":
                ok = not any(self.conditions([item], current, previous) for item in value)
            elif key in TRIGGERS:
                assert value in ("yes", "no")
                ok = self.conditions(TRIGGERS[key], current, previous) == (value == "yes")
            elif self.scope(key, current, previous) is not None:
                ok = self.conditions(value, self.scope(key, current, previous), current)
            elif key == "check_variable":
                data = fields(value)
                actual = state.variables.get(data["var"], 0)
                expected = self.number(data["value"], current, previous)
                ok = {"equals": actual == expected, "greater_than": actual > expected, "greater_than_or_equals": actual >= expected}[data.get("compare", "greater_than_or_equals")]
            elif key == "has_variable":
                ok = value in state.variables
            elif key in ("has_state_flag", "has_country_flag"):
                ok = value in state.flags
            elif key == "has_global_flag":
                ok = value in self.globals
            elif key == "has_completed_focus":
                ok = value in state.focuses
            elif key in ("tag", "state"):
                ok = current == value
            elif key == "is_owned_by":
                ok = state.owner == self.scope(value, current, previous)
            elif key == "is_controlled_by":
                ok = state.controller == self.scope(value, current, previous)
            elif key == "is_subject_of":
                ok = state.subject == value
            elif key == "has_war_with":
                ok = self.scope(value, current, previous) in state.enemies
            elif key == "is_in_faction_with":
                target = self.scope(value, current, previous)
                ok = state.faction is not None and state.faction == self.scopes[target].faction
            elif key in ("exists", "is_subject", "has_capitulated", "is_in_faction", "is_faction_leader", "always"):
                actual = {"exists": state.exists, "is_subject": state.subject is not None,
                          "has_capitulated": state.capitulated, "is_in_faction": state.faction is not None,
                          "is_faction_leader": state.faction == current, "always": True}[key]
                ok = actual == (value == "yes")
            else:
                raise AssertionError(f"Unsupported condition: {key} {operator} {value}")
            if not ok:
                return False
        return True

    def effect(self, name, current=None, previous=None):
        self.run(EFFECTS[name], current, previous)

    def run(self, block, current=None, previous=None):
        current = current or self.root
        state = self.scopes[current]
        chain = False
        for key, _, value in block:
            if key in ("if", "else_if", "else"):
                if key == "if":
                    chain = False
                data = fields(value)
                if not chain and self.conditions(data.get("limit", []), current, previous):
                    chain = True
                    self.run([item for item in value if item[0] != "limit"], current, previous)
            elif key in ("hidden_effect",):
                self.run(value, current, previous)
            elif key in ("custom_effect_tooltip", "unlock_decision_tooltip"):
                continue
            elif self.scope(key, current, previous) is not None:
                self.run(value, self.scope(key, current, previous), current)
            elif key.startswith(P) and key in EFFECTS:
                self.effect(key, current, previous)
            elif key in ("set_variable", "set_temp_variable", "add_to_variable", "subtract_from_variable", "clamp_variable"):
                data = fields(value)
                name = data.get("var", next(iter(data)))
                before = state.variables.get(name, 0)
                amount = self.number(data.get("value", data.get(name, "0")), current, previous)
                if key in ("set_variable", "set_temp_variable"):
                    state.variables[name] = amount
                elif key == "clamp_variable":
                    state.variables[name] = min(float(data["max"]), max(float(data["min"]), before))
                else:
                    state.variables[name] = before + amount * (-1 if key == "subtract_from_variable" else 1)
            elif key == "clear_variable":
                state.variables.pop(value, None)
            elif key in ("set_state_flag", "set_country_flag"):
                state.flags.add(value)
            elif key in ("clr_state_flag", "clr_country_flag"):
                state.flags.discard(value)
            elif key == "set_global_flag":
                self.globals.add(value)
            elif key in ("add_political_power", "add_command_power", "add_manpower", "add_stability"):
                resource = {"add_political_power": "pp", "add_command_power": "command", "add_manpower": "people", "add_stability": "stability"}[key]
                state.resources[resource] += self.number(value, current, previous)
            elif key == "add_equipment_to_stockpile":
                data = fields(value)
                equipment = re.sub(r"_\d+$", "", data["type"])
                state.resources[equipment] += self.number(data["amount"], current, previous)
            elif key in ("create_unit", "add_tech_bonus", "activate_mission", "country_event", "add_dynamic_modifier",
                         V + "ensure_emergency_militia_template", V + "add_legitimacy", V + "join_coalition_of_FROM"):
                self.calls.append((key, current, value))
            else:
                raise AssertionError(f"Unsupported effect: {key} {value}")

    def start(self, name):
        block = fields(PROJECTS[name])
        self.source = fields(block["targets"])[""]
        self.run(block["complete_effect"])


class PreparationAccounting(unittest.TestCase):
    def test_all_projects_charge_once_and_refund_once(self):
        self.assertEqual(len(PROJECTS), 12)
        for name in PROJECTS:
            with self.subTest(project=name):
                script = Script()
                before = deepcopy(script.scopes["WRK"].resources)
                script.start(name)
                paid = deepcopy(script.scopes["WRK"].resources)
                self.assertNotEqual(before, paid)
                script.start(name)
                self.assertEqual(script.scopes["WRK"].resources, paid)
                script.effect(P + "refund_project", script.source)
                script.effect(P + "refund_project", script.source)
                self.assertEqual(script.scopes["WRK"].resources, before)
                self.assertEqual(script.scopes["WRK"].variables[P + "active"], 0)
                self.assertNotIn(P + "project", script.scopes[script.source].variables)

    def test_fractional_shortages_cannot_pay_any_currency(self):
        for name, project in PROJECTS.items():
            costs = fields(project)["custom_cost_trigger"]
            for key, op, value in walk(costs):
                if op != "<":
                    continue
                resource = {"has_political_power": "pp", "has_manpower": "people", "command_power": "command"}.get(key, key)
                with self.subTest(project=name, currency=resource):
                    script = Script()
                    script.scopes["WRK"].resources[resource] = float(value) - 0.01
                    before = deepcopy(script.scopes["WRK"].resources)
                    script.start(name)
                    self.assertEqual(before, script.scopes["WRK"].resources)
                    self.assertNotIn(P + "project", script.scopes[script.source].variables)
                    script.scopes["WRK"].resources[resource] = float(value)
                    script.start(name)
                    self.assertEqual(script.scopes["WRK"].resources[resource], 0)

    def test_two_slots_reject_a_third_and_finish_releases_only_once(self):
        script = Script()
        script.start(P + "open_stores")
        script.start(P + "protect_rail")
        script.start(P + "public_charter")
        self.assertNotIn(P + "project", script.scopes["38"].variables)
        script.effect(P + "finish_project", "32")
        script.effect(P + "finish_project", "32")
        self.assertEqual(script.scopes["WRK"].variables[P + "active"], 1)
        self.assertEqual(len(script.calls), 1)
        script.start(P + "public_charter")
        self.assertIn(P + "pending", script.scopes["38"].flags)

    def test_collapse_returns_unfinished_and_concedes_finished_packages(self):
        script = Script()
        script.start(P + "open_stores")
        script.effect(P + "finish_project", "32")
        script.start(P + "cadre_school")
        paid_people = script.scopes["WRK"].resources["people"]
        script.effect(P + "close_prewar")
        script.effect(P + "close_prewar")
        self.assertEqual(script.scopes["WRK"].resources["people"], paid_people + 3000)
        self.assertEqual(script.scopes["WRK"].variables[P + "active"], 0)
        self.assertNotIn(P + "project", script.scopes["37"].variables)
        script.effect(P + "settle_assets")
        script.effect(P + "settle_assets")
        self.assertEqual(script.scopes["VAD"].resources["infantry_equipment"], 5400)
        self.assertEqual(script.scopes["WKR"].resources["infantry_equipment"], 0)

    def test_every_project_reaches_each_selected_claimant_exactly_once(self):
        for patron, tag in enumerate(("WKR", "VAD", "TVA"), 1):
            for name in PROJECTS:
                with self.subTest(project=name, recipient=tag):
                    script = Script()
                    script.scopes["WRK"].variables[P + "patron"] = patron
                    script.start(name)
                    site = script.source
                    script.effect(P + "finish_project", site)
                    script.run(fields(DECISIONS[P + "defend_object"])["complete_effect"])
                    self.assertNotIn(P + "contested", script.scopes[site].flags)
                    script.calls.clear()
                    script.effect(P + "settle_assets")
                    first = deepcopy((script.scopes, script.calls))
                    self.assertTrue(script.scopes[tag].resources or script.scopes[tag].variables or script.calls)
                    script.effect(P + "settle_assets")
                    self.assertEqual((script.scopes, script.calls), first)
                    for other in {"WKR", "VAD", "TVA"} - {tag}:
                        self.assertFalse(script.scopes[other].resources)
                        self.assertFalse(script.scopes[other].variables)

    def test_evacuations_determine_fate_and_concession_changes_it(self):
        for name, flag in (("civil_evacuation", "worker_safe_with_loyalists"), ("military_evacuation", "worker_rescued_by_vlad")):
            script = Script()
            script.start(P + name)
            script.effect(P + "finish_project", "40")
            script.run(fields(DECISIONS[P + "defend_object"])["complete_effect"])
            script.effect(P + "resolve_fate")
            self.assertIn(V + flag, script.globals)
        script = Script()
        script.start(P + "civil_evacuation")
        script.effect(P + "finish_project", "40")
        script.effect(P + "yield_object", "40")
        script.effect(P + "resolve_fate")
        self.assertIn(V + "worker_rescued_by_vlad", script.globals)

    def test_pending_reserves_are_recovered_before_successor_annexation(self):
        for suffix in ("wkr", "vad", "tva"):
            effect = EFFECTS[V + "complete_wrk_from_" + suffix]
            keys = [key for key, _, _ in walk(effect)]
            self.assertLess(keys.index(P + "return_reserves_to_successor"), keys.index("annex_country"))
        script = Script()
        script.scopes["VAD"].variables.update({P + "reserve_rifles": 8100, P + "reserve_guard": 1})
        before = deepcopy(script.scopes["WRK"].resources)
        script.effect(P + "return_reserves_to_successor", "VAD")
        script.effect(P + "return_reserves_to_successor", "VAD")
        self.assertEqual(script.scopes["WRK"].resources["infantry_equipment"], before["infantry_equipment"] + 10800)
        self.assertEqual(script.scopes["WRK"].resources["people"], before["people"] + 3000)

    def test_offer_requires_consent_and_rechecks_donor_stocks(self):
        for tag, stock, amount in (("EYR", "infantry_equipment", 13500), ("EGC", "support_equipment", 100), ("RIV", "train_equipment", 5), ("YOR", "infantry_equipment", 18000)):
            script = Script()
            script.source = tag
            script.scopes[tag].subject = "WRK"
            before = deepcopy(script.scopes["WRK"].resources)
            script.run(fields(DECISIONS[P + "offer_" + tag.lower()])["complete_effect"])
            self.assertEqual(script.scopes["WRK"].resources, before)
            script.root, script.source = tag, "WRK"
            script.scopes["WRK"].resources[stock] = amount - 0.01
            script.effect(P + "accept_offer")
            self.assertNotIn(P + "treaty_signed", script.scopes[tag].flags)
            script.scopes["WRK"].resources[stock] = amount
            script.effect(P + "accept_offer")
            script.effect(P + "accept_offer")
            self.assertEqual(script.scopes["WRK"].resources[stock], 0)
            self.assertEqual(script.scopes[tag].resources[stock], amount)
            self.assertEqual(script.scopes["WRK"].resources["pp"], before["pp"] - 35)
            self.assertEqual(script.scopes[tag].variables[P + "treaty_patron"], 1)
            self.assertFalse(any(call[0] == V + "join_coalition_of_FROM" for call in script.calls))

    def test_dormant_offer_cannot_spend_after_the_split(self):
        script = Script()
        script.root, script.source = "EYR", "WRK"
        script.scopes["EYR"].flags.add(P + "offer_pending")
        script.globals.clear()
        before = deepcopy(script.scopes["WRK"].resources)
        script.effect(P + "accept_offer")
        self.assertEqual(script.scopes["WRK"].resources, before)
        self.assertNotIn(P + "treaty_signed", script.scopes["EYR"].flags)

    def test_prewar_contract_joins_only_its_own_surviving_host(self):
        recipient = fields(EVENTS["ADISCORD_vorkerland_preparation.22"])["immediate"]
        for patron, host in enumerate(("WKR", "VAD", "TVA"), 1):
            for blocked in (None, "wrong_host", "war", "other_faction", "capitulated"):
                with self.subTest(host=host, blocked=blocked):
                    script = Script()
                    script.root, script.source = "EYR", host
                    script.globals = {V + "phase_central_preparation"}
                    district = script.scopes["EYR"]
                    district.flags.add(P + "treaty_signed")
                    district.variables[P + "treaty_patron"] = patron
                    if blocked == "wrong_host":
                        district.variables[P + "treaty_patron"] = patron % 3 + 1
                    elif blocked == "war":
                        district.enemies.add(host)
                    elif blocked == "other_faction":
                        district.faction = "RUS"
                    elif blocked == "capitulated":
                        district.capitulated = True
                    script.run(recipient)
                    joins = [call for call in script.calls if call[0] == V + "join_coalition_of_FROM"]
                    self.assertEqual(len(joins), int(blocked is None))
                    if blocked is None:
                        self.assertIn(V + "preserve_wartime_faction", script.scopes[host].flags)

    def test_only_a_winning_partner_that_remained_an_ally_gets_independence(self):
        for winner, flag in enumerate(("worker_won", "vlad_won", "dorian_won"), 1):
            for allied in (False, True):
                for promised in (1, 2, 3):
                    script = Script()
                    script.globals = {V + flag}
                    script.scopes["WRK"].faction = "WRK"
                    district = script.scopes["EYR"]
                    district.flags.add(P + "treaty_signed")
                    district.variables[P + "treaty_patron"] = promised
                    district.faction = "WRK" if allied else None
                    script.effect(P + "settle_treaties")
                    self.assertEqual(P + "independence_guaranteed" in district.flags, allied and winner == promised)

    def test_zshat_treaty_does_not_grant_postwar_independence(self):
        for winner, flag in enumerate(("worker_won", "vlad_won", "dorian_won"), 1):
            with self.subTest(winner=winner):
                script = Script()
                script.globals = {V + flag}
                script.scopes["WRK"].faction = "WRK"
                district = script.scopes["EGC"]
                district.flags.add(P + "treaty_signed")
                district.variables[P + "treaty_patron"] = winner
                district.faction = "WRK"
                script.effect(P + "settle_treaties")
                self.assertNotIn(P + "independence_guaranteed", district.flags)

    def test_reserve_delivery_waits_for_a_live_capital_and_cannot_repeat(self):
        script = Script()
        script.root = "VAD"
        script.globals = {V + "collapse_wars_started"}
        script.scopes["VAD"].variables[P + "reserve_rifles"] = 8100
        script.effect(P + "deliver_rifles")
        self.assertEqual(script.scopes["VAD"].resources["infantry_equipment"], 0)
        script.scopes["capital_VAD"].owner = "VAD"
        script.scopes["capital_VAD"].controller = "VAD"
        script.effect(P + "deliver_rifles")
        script.effect(P + "deliver_rifles")
        self.assertEqual(script.scopes["VAD"].resources["infantry_equipment"], 8100)

    def test_all_programmes_have_real_focus_gates_and_fit_the_prewar_window(self):
        focus_blocks = {
            fields(value)["id"]: fields(value)
            for key, _, value in walk(parse(read("focus_trees/Vorkerland/prewar/focuses.txt")))
            if key == "focus" and isinstance(value, list)
        }

        def finish_day(name):
            focus = focus_blocks[name]
            prerequisites = [value for key, _, value in focus.get("prerequisite", []) if key == "focus"]
            return float(focus["cost"]) * 7 + min((finish_day(p) for p in prerequisites), default=0)

        for name, block in PROJECTS.items():
            gate = fields(fields(block)["visible"])["has_completed_focus"]
            self.assertIn(("unlock_decision_tooltip", "=", name), focus_blocks[gate]["completion_reward"])
            self.assertLessEqual(finish_day(gate), 77)
            self.assertLess(finish_day(gate) + int(fields(block)["days_remove"]) + 21, 350)

    def test_complete_preparation_routes_fit_with_paid_work_and_contests(self):
        focuses = {
            fields(value)["id"]: fields(value)
            for key, _, value in walk(parse(read("focus_trees/Vorkerland/prewar/focuses.txt")))
            if key == "focus" and isinstance(value, list)
        }
        branches = (
            ("WRK_prioritize_arsenal_output", "WRK_preserve_machine_tools"),
            ("WRK_contract_local_garrisons", "WRK_prepare_officer_reserve"),
            ("WRK_convene_council_of_republics", "WRK_inventory_emergency_stores"),
            ("WRK_prepare_civil_evacuation", "WRK_prepare_military_evacuation"),
            ("WRK_open_worker_vadl_backchannel", "WRK_mobilize_loyal_republics"),
        )
        for industry, army, politics, evacuation, course in product(*branches):
            route = [
                "WRK_measure_confederation_fault_lines",
                "WRK_reopen_emergency_workshops", industry,
                "WRK_collect_officer_returns", army, politics,
                "WRK_bind_districts_to_charter" if politics == branches[2][0] else "WRK_disperse_railway_reserves",
                "WRK_issue_continuity_orders", evacuation, course,
                "WRK_offer_emergency_compact" if course == branches[4][0] else "WRK_place_reserves_under_worker",
            ]
            with self.subTest(route=route):
                elapsed = 0
                completed = set()
                # Slots are released when paid work finishes; contests run separately.
                slots = [0, 0]
                for name in route:
                    focus = focuses[name]
                    required = [v for k, _, v in focus.get("prerequisite", []) if k == "focus"]
                    self.assertTrue(not required or completed.intersection(required), name)
                    exclusive = [v for k, _, v in focus.get("mutually_exclusive", []) if k == "focus"]
                    self.assertFalse(completed.intersection(exclusive), name)
                    elapsed += int(focus["cost"]) * 7
                    completed.add(name)
                    if name not in (industry, army, evacuation):
                        continue
                    unlocked = [v for k, _, v in focus["completion_reward"] if k == "unlock_decision_tooltip"]
                    self.assertEqual(len(unlocked), 1)
                    job = fields(PROJECTS[unlocked[0]])
                    self.assertEqual(fields(job["visible"])["has_completed_focus"], name)
                    self.assertIn(("has_completed_focus", "=", name), list(walk(job["complete_effect"])))
                    slot = slots.index(min(slots))
                    finish = max(elapsed, slots[slot]) + int(job["days_remove"])
                    slots[slot] = finish
                    self.assertLessEqual(finish + 21, 161)
                self.assertEqual(elapsed, 140)

    def test_prewar_ai_plans_select_reachable_nonconflicting_programmes(self):
        focuses = {
            fields(value)["id"]: fields(value)
            for key, _, value in walk(parse(read("focus_trees/Vorkerland/prewar/focuses.txt")))
            if key == "focus" and isinstance(value, list)
        }
        plans = fields(parse(read("common/ai_strategy_plans/ADISCORD_vorkerland_plans.txt")))
        for course in ("compact", "hardline"):
            plan = fields(plans[V + "wrk_prewar_" + course + "_plan"])
            route = [value for _, _, value in plan["ai_national_focuses"]]
            completed = set()
            elapsed = 0
            for name in route:
                focus = focuses[name]
                parents = [v for k, _, v in focus.get("prerequisite", []) if k == "focus"]
                exclusive = [v for k, _, v in focus.get("mutually_exclusive", []) if k == "focus"]
                self.assertTrue(not parents or completed.intersection(parents), name)
                self.assertFalse(completed.intersection(exclusive), name)
                completed.add(name)
                elapsed += int(focus["cost"]) * 7
            self.assertEqual(elapsed, 140)
            for pair in (
                ("WRK_prioritize_arsenal_output", "WRK_preserve_machine_tools"),
                ("WRK_contract_local_garrisons", "WRK_prepare_officer_reserve"),
                ("WRK_prepare_civil_evacuation", "WRK_prepare_military_evacuation"),
            ):
                self.assertEqual(len(completed.intersection(pair)), 1)

    def test_timeout_missions_never_auto_succeed(self):
        missions = {name: fields(block) for name, block in DECISIONS.items() if name.startswith(P + "contest_")}
        self.assertEqual(len(missions), 6)
        for name, mission in missions.items():
            self.assertFalse(Script().conditions(mission["available"]), name)
            self.assertEqual(mission["days_mission_timeout"], "21")
            self.assertIn(name, read("common/synchronized_dynamic_tokens/ADISCORD_tokens.txt"))


if __name__ == "__main__":
    unittest.main()
