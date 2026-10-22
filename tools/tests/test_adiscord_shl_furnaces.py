"""Execute bounded SHL accounting scripts; native loader/UI still need game QA."""

import unittest
import re
from collections import defaultdict
from copy import deepcopy
from functools import lru_cache
from pathlib import Path

from tools.validators.validate_adiscord_division_templates import parse_clausewitz

ROOT = Path(__file__).resolve().parents[2]
NEIGHBOURS = ("KYZ", "GLP", "MZR")
NEIGHBOUR_STATES = {
    "KYZ": (280, 284, 285, 286),
    "GLP": (297, 298, 299, 708),
    "MZR": (269, 273, 275),
}
EFFECT_PATH = ROOT / "common/scripted_effects/ADISCORD_SHL_scripted_effects.txt"
TRIGGER_PATH = ROOT / "common/scripted_triggers/ADISCORD_SHL_scripted_triggers.txt"
SOUTH_TRIGGER_PATH = ROOT / "common/scripted_triggers/ADISCORD_south_final_war_triggers.txt"


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


@lru_cache(maxsize=None)
def shared_definitions(relative_path, names):
    definitions = {
        entry.key: entry.value
        for entry in parse_clausewitz((ROOT / relative_path).read_text(encoding="utf-8"))
    }
    return {name: definitions[name] for name in names}


class ScriptMachine:
    def __init__(self, effects, triggers):
        self.effects = {e.key: e.value for e in effects}
        self.triggers = {e.key: e.value for e in triggers}
        # Shared southern triggers referenced by SHL campaign conditions.
        self.triggers.update({e.key: e.value for e in parse_clausewitz(SOUTH_TRIGGER_PATH.read_text(encoding="utf-8"))})
        # Execute shared settlement and development rules from their owning sources.
        self.effects.update(shared_definitions(
            "common/scripted_effects/ADISCORD_RUS_scripted_effects.txt",
            ("RUS_crisis_release_other_major",),
        ))
        self.triggers.update(shared_definitions(
            "common/scripted_triggers/ADISCORD_RUS_scripted_triggers.txt",
            ("RUS_crisis_other_major_required",),
        ))
        self.effects.update(shared_definitions(
            "common/scripted_effects/ADISCORD_society_development_effects.txt",
            ("ADISCORD_reform_social_system_development", "ADISCORD_initialize_society_development_variables"),
        ))
        self.variables = defaultdict(dict)
        self.flags = defaultdict(set)
        self.global_flags = {"ADISCORD_fresh_campaign_contract_v1"}
        self.flag_days = defaultdict(dict)
        self.control = {str(i): "SHL" for i in range(287, 296)}
        self.ownership = dict(self.control)
        self.control["294"] = "SHL"
        self.focuses = set()
        self.factories = 0
        self.infrastructure = 0
        self.state_buildings = defaultdict(int)
        self.cores = set()
        self.idea_days = {}
        self.event_days = {}
        self.anti_air = 0
        self.free_slots = True
        self.capitulated = False
        self.root_scope = "SHL"
        self.neighbours = {"KYZ", "GLP", "MZR"}
        self.majors = set()
        self.scheduled = []
        self.values = {"political_power": 200.0, "stability": 0.0}
        self.dynamic = set()
        self.calls = []
        self.equipment = defaultdict(float)
        self.previous_scope = "SHL"
        # Neighbour countries and simple engine facts used by the crisis layer.
        self.ai = False
        self.countries = {tag: {"exists": True, "is_subject": False, "has_war": False} for tag in NEIGHBOURS}
        self.wars = set()
        self.factions = {}
        self.missions = set()
        self.ideas = set()
        self.enabled_advisors = defaultdict(set)
        self.stability = 0.5
        self.manpower = 100000.0
        self.country_manpower = defaultdict(float)
        self.unit_owners = []
        self.divisions = 2
        self.ownership.update({str(state): owner for owner, states in NEIGHBOUR_STATES.items() for state in states})
        self.ownership["296"] = "SHL"
        self.ownership["699"] = "SHL"
        self.ownership["707"] = "SHL"
        self.control.update(self.ownership)
        self.target_scope = None
        self.variables["SHL"]["ADISCORD_economy_treasury"] = 1000.0

    def value(self, value, scope):
        try:
            return float(value)
        except (ValueError, TypeError):
            if "." in value:
                owner, name = value.split(".", 1)
                if owner.isdigit():
                    raise AssertionError("Numeric state variable prefixes are not native syntax")
                if owner == "FROM":
                    owner = self.target_scope
                elif owner == "PREV":
                    owner = self.previous_scope
                return self.variables[owner].get(name, 0.0)
            return self.variables[scope].get(value, 0.0)

    def matches(self, items, scope, target=None):
        def units(children):
            grouped = []
            index = 0
            while index < len(children):
                if not children[index].key:
                    grouped.append(children[index:index + 3])
                    index += 3
                else:
                    grouped.append([children[index]])
                    index += 1
            return grouped

        def unit(entries):
            return self.matches(entries, scope, target)

        def match(e):
            if e.key == "OR":
                return any(unit(child) for child in units(e.value))
            if e.key == "AND" or e.key in ("hidden_trigger", "custom_trigger_tooltip"):
                return all(unit(child) for child in units([c for c in e.value if c.key != "tooltip"]))
            if e.key == "NOT":
                return not any(unit(child) for child in units(e.value))
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
            if e.key == "has_global_flag":
                return e.value in self.global_flags
            if e.key == "has_country_flag" or e.key == "has_state_flag":
                if isinstance(e.value, list):
                    name = scalar(e.value, "flag")
                    tokens = [child.value for child in e.value if not child.key]
                    if tokens != ["days", ">", "27"]:
                        raise AssertionError("Unsupported flag-age predicate")
                    return name in self.flags[scope] and self.flag_days[scope].get(name, 0) > 27
                return e.value in self.flags[scope]
            if e.key in ("ROOT", "SHL"):
                country = self.root_scope if e.key == "ROOT" else "SHL"
                return self.condition_scope(e.value, country, scope, target)
            if e.key in NEIGHBOURS:
                return self.condition_scope(e.value, e.key, scope, target)
            if e.key == "exists" and scope in NEIGHBOURS:
                return self.countries[scope]["exists"] == (e.value == "yes")
            if e.key in ("is_subject", "has_war") and scope in self.countries:
                value = self.countries[scope][e.key]
                if e.key == "has_war":
                    value = value or any(scope in war for war in self.wars)
                return value == (e.value == "yes")
            if e.key == "is_neighbor_of":
                return e.value == "SHL" and scope in self.neighbours
            if e.key == "is_subject" and scope == "SHL":
                return e.value == "no"
            if e.key == "has_war" and scope == "SHL":
                return any("SHL" in war for war in self.wars) == (e.value == "yes")
            if e.key == "has_war_with":
                return frozenset((scope, e.value)) in self.wars
            if e.key == "is_in_faction_with":
                return self.factions.get(scope) is not None and self.factions.get(scope) == self.factions.get(e.value)
            if e.key == "is_in_faction":
                return (self.factions.get(scope) is not None) == (e.value == "yes")
            if e.key == "is_faction_leader":
                return (self.factions.get(scope) == scope) == (e.value == "yes")
            if e.key == "has_active_mission":
                return e.value in self.missions
            if e.key == "has_character":
                return True
            if e.key == "has_template":
                return e.value.strip('"') in self.calls
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
            if e.key == "is_major":
                return (scope in self.majors) == (e.value == "yes")
            if e.key == "has_capitulated":
                return self.capitulated == (e.value == "yes")
            if e.key == "has_political_power":
                raise AssertionError("Political power requires a native < or > comparison")
            if e.key == "has_idea":
                return e.value in self.ideas
            if e.key == "has_equipment":
                tokens = [c.value for c in e.value if not c.key]
                if len(tokens) != 3 or tokens[1] != "<":
                    raise AssertionError("Unsupported equipment comparison: " + repr(tokens))
                return self.equipment[(scope, tokens[0])] < float(tokens[2])
            if e.key == "has_dynamic_modifier":
                return (scalar(e.value, "modifier") if isinstance(e.value, list) else e.value) in self.dynamic
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
                return self.ai == (e.value == "yes")
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
                native = {
                    "has_stability": self.stability,
                    "has_political_power": self.values["political_power"],
                    "num_divisions": self.divisions,
                    "has_manpower": self.manpower,
                    "infrastructure": self.infrastructure,
                    "anti_air_building": self.anti_air,
                    "industrial_complex": self.state_buildings[(scope, "industrial_complex")],
                }
                if comparison[0] not in native or comparison[1] not in ("<", ">"):
                    raise AssertionError("Unsupported native comparison: " + repr(comparison))
                if comparison[0] in ("infrastructure", "anti_air_building") and comparison[1:] != ["<", "5"]:
                    raise AssertionError("Unsupported native comparison: " + repr(comparison))
                left = native[comparison[0]]
                right = float(comparison[2])
                results.append(left < right if comparison[1] == "<" else left > right)
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
                country = self.root_scope if e.key == "ROOT" else "SHL"
                self.switch_scope(e.value, country, scope, target)
            elif e.key == "PREV":
                self.switch_scope(e.value, self.previous_scope, scope, target)
            elif e.key in NEIGHBOURS:
                self.switch_scope(e.value, e.key, scope, target)
            elif e.key == "declare_war_on":
                self.wars.add(frozenset((scope, scalar(e.value, "target"))))
                self.calls.append(("declare_war_on", scope, scalar(e.value, "target")))
            elif e.key == "add_to_war":
                ally = scalar(e.value, "targeted_alliance")
                enemy = scalar(e.value, "enemy")
                if frozenset((ally, enemy)) not in self.wars:
                    raise AssertionError("Cannot join a war that does not exist")
                # Joining the existing war includes opponents already fighting
                # the requested side, including the other coalition member.
                enemies = {enemy}
                for war in self.wars:
                    if ally in war:
                        enemies.update(war - {ally})
                for opponent in enemies:
                    self.wars.add(frozenset((scope, opponent)))
                self.calls.append(("add_to_war", scope))
            elif e.key == "white_peace":
                self.wars.discard(frozenset((scope, e.value)))
            elif e.key == "transfer_state":
                state = self.previous_scope if e.value == "PREV" else e.value
                self.ownership[state] = scope
            elif e.key == "set_state_controller_to":
                self.control[scope] = e.value
            elif e.key in ("activate_mission", "remove_mission"):
                (self.missions.add if e.key == "activate_mission" else self.missions.discard)(e.value)
            elif e.key == "owner":
                self.switch_scope(e.value, self.ownership[scope], scope, target)
            elif e.key == "add_core_of":
                self.cores.add((scope, e.value))
            elif e.key == "remove_ideas":
                self.ideas.discard(e.value)
                self.idea_days.pop(e.value, None)
            elif e.key == "add_timed_idea":
                self.ideas.add(scalar(e.value, "idea"))
                self.idea_days[scalar(e.value, "idea")] = int(scalar(e.value, "days"))
            elif e.key == "add_ideas":
                self.ideas.add(e.value)
            elif e.key == "activate_advisor":
                self.enabled_advisors[scope].add(e.value)
            elif e.key == "add_manpower":
                if scope == "SHL":
                    self.manpower += self.value(e.value, scope)
                else:
                    self.country_manpower[scope] += self.value(e.value, scope)
            elif e.key == "add_equipment_to_stockpile":
                self.equipment[(scope, scalar(e.value, "type"))] += self.value(scalar(e.value, "amount"), scope)
                self.calls.append((e.key, scope))
            elif e.key == "create_unit":
                self.divisions += 1
                owner = scalar(e.value, "owner")
                self.unit_owners.append((scope, self.previous_scope if owner == "PREV" else owner))
                self.calls.append(("create_unit", scope))
            elif e.key == "division_template":
                self.calls.append(scalar(e.value, "name").strip('"'))
            elif e.key == "create_faction_from_template":
                self.factions[scope] = scope
            elif e.key == "add_to_faction":
                member = self.previous_scope if e.value == "PREV" else e.value
                self.factions[member] = self.factions.get(scope, scope)
            elif e.key == "dismantle_faction":
                leader = self.factions.get(scope)
                if leader != scope:
                    raise AssertionError("Only the faction leader can dissolve it")
                self.factions = {tag: faction for tag, faction in self.factions.items() if faction != leader}
            elif e.key == "damage_building":
                building = scalar(e.value, "type")
                assert self.state_buildings[(scope, building)] > 0, "Cannot damage an absent building"
                self.calls.append((e.key, scope))
            elif e.key in (
                "set_politics", "add_popularity", "promote_character", "retire_character",
                "mark_focus_tree_layout_dirty", "force_update_dynamic_modifier", "add_war_support",
                "ADISCORD_release_non_participating_minor_optimization",
                "ADISCORD_south_crisis_add_campaign", "ADISCORD_south_crisis_cycle",
                "SHL_crisis_draw",
                "add_claim_by",
            ):
                self.calls.append((e.key, scope))
            elif e.key == "FROM":
                self.switch_scope(e.value, target, scope, target)
            elif e.key.isdigit():
                self.switch_scope(e.value, e.key, scope, target)
            elif e.key == "set_major":
                (self.majors.add if e.value == "yes" else self.majors.discard)(scope)
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
            elif e.key == "set_global_flag":
                self.global_flags.add(e.value)
            elif e.key == "add_building_construction":
                self.state_buildings[(scope, scalar(e.value, "type"))] += int(scalar(e.value, "level"))
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
                self.event_days[scalar(e.value, "id")] = int(scalar(e.value, "days", "0"))
            elif e.key in ("ADISCORD_economy_mark_dirty", "ADISCORD_economy_clamp_treasury"):
                self.calls.append(e.key)
            elif e.key in ("custom_effect_tooltip", "add_to_array", "log", "air_experience"):
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

    def test_training_requires_the_full_political_power_price(self):
        for power, allowed in ((24.99, False), (25.0, True), (25.01, True)):
            with self.subTest(power=power):
                self.setUp()
                m = self.machine
                m.values["political_power"] = power
                decision = decision_definition("SHL_training_furnace")
                self.assertEqual(m.matches(block(decision, "custom_cost_trigger"), "SHL"), allowed)
                m.run("SHL_begin_training", target="287")
                self.assertAlmostEqual(m.values["political_power"], power - (25 if allowed else 0))
                self.assertEqual(m.variables["SHL"]["ADISCORD_economy_treasury"], 900 if allowed else 1000)
                self.assertEqual(m.variables["287"].get("SHL_operation", 0), 3 if allowed else 0)

    def test_furnace_overview_reads_each_states_values_without_crossing_scopes(self):
        m = self.machine
        for index, state in enumerate(range(287, 296), 1):
            m.variables[str(state)].update({
                "SHL_furnace_wear": index * 3,
                "SHL_furnace_stock": index + 2,
                "SHL_furnace_owner": index % 2,
                "SHL_furnace_training": index % 2,
            })
        m.run("SHL_refresh_furnaces")
        for index, state in enumerate(range(287, 296), 1):
            with self.subTest(state=state):
                for field in ("wear", "stock", "owner"):
                    self.assertEqual(m.variables["SHL"][f"SHL_{field}_{index}"],
                                     m.variables[str(state)][f"SHL_furnace_{field}"])
                m.variables["SHL"]["SHL_selected_furnace"] = index
                m.run("SHL_refresh_selected_furnace")
                self.assertEqual(m.variables["SHL"]["SHL_selected_training"], index % 2)

    def test_event_timeout_choices_are_first_and_use_native_option_fields(self):
        source = (ROOT / "events/ADISCORD_SHL_events.txt").read_text(encoding="utf-8")
        self.assertNotIn("default_option", source)
        defaults = {20: "b", 21: "b", 30: "b", 31: "b", 40: "b", 70: "b",
                    75: "b", 112: "b", 120: "c", 121: "b"}
        for entry in parse_clausewitz(source):
            if entry.key != "country_event":
                continue
            identifier = scalar(entry.value, "id")
            number = int(identifier.rsplit(".", 1)[1])
            if number in defaults:
                options = [e.value for e in entry.value if e.key == "option"]
                self.assertEqual(scalar(options[0], "name"), f"{identifier}.{defaults[number]}")

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
        self.assertEqual(m.variables["SHL"]["ADISCORD_economy_treasury"], 1480)
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
        self.assertEqual(m.variables["SHL"]["ADISCORD_economy_treasury"], 85)
        self.assertEqual(m.variables["287"]["SHL_furnace_shortages"], 0)

    def test_planned_supply_never_borrows_or_buys_fractional_packets(self):
        m = self.machine
        m.variables["SHL"]["SHL_regular_supply"] = 1
        m.variables["SHL"]["ADISCORD_economy_treasury"] = 24.99
        m.variables["287"]["SHL_furnace_stock"] = 0
        m.run("SHL_produce_site", scope="287")
        self.assertEqual(m.variables["SHL"]["ADISCORD_economy_treasury"], 24.99)
        self.assertEqual(m.variables["287"]["SHL_furnace_stock"], 0)

    def test_native_focus_tree_has_unique_reachable_focuses_on_free_cells(self):
        path = ROOT / "focus_trees/SHL/main/focuses.txt"
        self.assertTrue(path.exists())
        tree = block(parse_clausewitz(path.read_text(encoding="utf-8")), "focus_tree")
        focuses = [e.value for e in tree if e.key == "focus"]
        ids = [scalar(f, "id") for f in focuses]
        self.assertEqual(len(ids), 115)
        self.assertEqual(len(set(ids)), 115)
        cells = [(scalar(f, "x"), scalar(f, "y")) for f in focuses]
        self.assertEqual(len(cells), len(set(cells)))
        for focus in focuses:
            for prerequisite in [e.value for e in focus if e.key == "prerequisite"]:
                for item in prerequisite:
                    self.assertIn(item.value, ids)

    def test_hidden_courses_are_gated_by_their_crisis_flags(self):
        for identifier, flag in (("SHL_regency_council", "SHL_regency_path"), ("SHL_shift_councils", "SHL_commune_path")):
            allow = block(focus_definition(identifier), "allow_branch")
            self.assertEqual([(e.key, e.value) for e in allow], [("has_country_flag", flag)])

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
        self.assertEqual(country["SHL_last_cycle_income"], 900)
        self.assertEqual(country["ADISCORD_economy_treasury"], 1850)

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
        self.assertEqual(m.variables["SHL"]["SHL_selected_period_income"], 90)
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
        self.assertEqual(m.enabled_advisors["SHL"], {"ADISCORD_staff_SHL_Navid_Azari"})
        self.assertNotIn("MZR", m.enabled_advisors)

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


class ObligationAccountingTests(unittest.TestCase):
    def setUp(self):
        FurnaceAccountingTests.setUp(self)
        self.m = self.machine
        self.c = self.m.variables["SHL"]
        self.c.update({"SHL_political_course": 0, "SHL_cycle_number": 0})

    def begin(self, kind, site="287"):
        preparation = {
            1: ("SHL_new_house", 0),
            2: ("SHL_open_conclave", 0),
            3: ("SHL_nur_directorate", 0),
            4: ("SHL_regency_council", 4),
            5: ("SHL_furnaces_to_workers", 5),
        }
        focus, course = preparation[kind]
        self.m.focuses.add(focus)
        self.c["SHL_political_course"] = course
        if kind == 5:
            for state in range(287, 296):
                self.m.variables[str(state)]["SHL_furnace_owner"] = 1
        effect = {1: "export", 2: "civic_order", 3: "arsenal_order", 4: "pledge", 5: "relief"}[kind]
        self.m.run("SHL_begin_" + effect, target=site)

    def cycle(self):
        self.m.run("SHL_produce_period")
        self.m.run("SHL_check_obligation_deadline")

    def test_export_has_one_advance_and_uses_actual_selected_production(self):
        self.begin(1)
        self.m.run("SHL_begin_export", target="288")
        self.assertEqual(self.c["ADISCORD_economy_treasury"], 1060)
        self.assertEqual(self.c["SHL_obligation_site"], 287)
        self.c["SHL_selected_furnace"] = 9
        self.cycle()
        self.assertEqual(self.c["SHL_obligation_progress"], 1)
        self.assertEqual(self.c["ADISCORD_economy_treasury"], 1540)
        self.cycle()
        self.assertNotIn("SHL_obligation_kind", self.c)
        self.assertEqual(self.c["ADISCORD_economy_treasury"], 2140)

    def test_shortage_cannot_create_weapons_or_consume_the_deposit(self):
        self.begin(3)
        self.m.variables["287"]["SHL_furnace_stock"] = 0
        self.cycle()
        self.assertEqual(self.c["SHL_obligation_deposit"], 90)
        self.assertEqual(self.c["SHL_obligation_progress"], 0)
        self.assertEqual(self.m.equipment[("SHL", "infantry_equipment")], 0)

    def test_partial_arsenal_delivery_refunds_only_unmade_batch_once(self):
        self.begin(3)
        self.cycle()
        self.assertEqual(self.m.equipment[("SHL", "infantry_equipment")], 750)
        self.assertEqual(self.m.equipment[("SHL", "ADISCORD_squad_weapons_equipment_0")], 5)
        self.assertEqual(self.c["SHL_obligation_deposit"], 45)
        before = self.c["ADISCORD_economy_treasury"]
        self.m.run("SHL_cancel_obligation")
        self.m.run("SHL_cancel_obligation")
        self.assertEqual(self.c["ADISCORD_economy_treasury"], before + 45)
        self.cycle()
        self.assertEqual(self.m.equipment[("SHL", "infantry_equipment")], 1050)

    def test_overtime_delivers_two_paid_batches_without_normal_revenue(self):
        self.begin(3)
        self.c["SHL_shift_policy"] = 1
        self.cycle()
        self.assertEqual(self.m.equipment[("SHL", "infantry_equipment")], 1500)
        self.assertEqual(self.m.equipment[("SHL", "ADISCORD_squad_weapons_equipment_0")], 10)
        self.assertEqual(self.c["ADISCORD_economy_treasury"], 1630)
        self.assertNotIn("SHL_obligation_kind", self.c)

    def test_civic_order_builds_only_after_real_pours_and_refunds_at_cap(self):
        self.begin(2)
        self.cycle()
        self.assertEqual(self.m.infrastructure, 0)
        self.m.infrastructure = 5
        before = self.c["ADISCORD_economy_treasury"]
        self.cycle()
        self.assertEqual(self.m.infrastructure, 5)
        self.assertEqual(self.c["ADISCORD_economy_treasury"], before + 480 + 90)
        self.assertNotIn("SHL_obligation_kind", self.c)

    def test_civic_order_delivers_infrastructure_and_civic_constituency(self):
        self.begin(2)
        self.cycle()
        self.cycle()
        self.assertEqual(self.m.infrastructure, 1)
        self.assertEqual(self.c["SHL_city_support"], 5)
        self.assertEqual(self.c["ADISCORD_economy_treasury"], 1870)

    def test_occupation_pauses_but_ownership_loss_settles_once(self):
        self.begin(2)
        self.m.control["287"] = "MZR"
        self.cycle()
        self.assertEqual(self.c["SHL_obligation_progress"], 0)
        self.assertEqual(self.c["SHL_obligation_deposit"], 90)
        self.m.control["287"] = "SHL"
        self.cycle()
        self.assertEqual(self.c["SHL_obligation_progress"], 1)
        self.m.ownership["287"] = "MZR"
        before = self.c["ADISCORD_economy_treasury"]
        self.m.run("SHL_refresh_furnaces")
        self.m.run("SHL_refresh_furnaces")
        self.assertEqual(self.c["ADISCORD_economy_treasury"], before + 90)
        self.assertNotIn("SHL_obligation_kind", self.c)

    def test_compatible_ratification_keeps_paid_progress_and_new_owner(self):
        for kind, commit in [(1, "SHL_commit_house_course"), (2, "SHL_commit_city_course"), (3, "SHL_commit_state_course")]:
            with self.subTest(kind=kind):
                self.setUp()
                self.begin(kind)
                self.cycle()
                before = self.c["ADISCORD_economy_treasury"]
                self.m.run(commit)
                self.assertEqual(self.c["SHL_obligation_kind"], kind)
                self.assertEqual(self.c["SHL_obligation_progress"], 1)
                self.assertEqual(self.c["ADISCORD_economy_treasury"], before)

    def test_incompatible_course_change_preserves_money_and_existing_weapons(self):
        self.begin(3)
        self.cycle()
        before = self.c["ADISCORD_economy_treasury"]
        self.m.run("SHL_commit_regency_course")
        self.assertNotIn("SHL_obligation_kind", self.c)
        self.assertEqual(self.c["ADISCORD_economy_treasury"], before + 45)
        self.assertEqual(self.m.equipment[("SHL", "infantry_equipment")], 750)

    def test_pledge_uses_cash_after_deductions_and_returns_excess(self):
        self.begin(4)
        self.c.update({"SHL_shift_policy": 1, "SHL_income_deduction": 8, "SHL_obligation_liability": 30})
        self.cycle()
        self.assertEqual(self.c["ADISCORD_economy_treasury"], 1858)
        self.assertNotIn("SHL_obligation_kind", self.c)

    def test_unpaid_advance_becomes_real_public_debt_once(self):
        self.begin(1)
        self.c["ADISCORD_economy_treasury"] = 20
        self.m.run("SHL_cancel_obligation")
        self.m.run("SHL_cancel_obligation")
        self.assertEqual(self.c["ADISCORD_economy_treasury"], 0)
        self.assertEqual(self.c["ADISCORD_economy_debt"], 70)

    def test_export_deadline_one_extension_and_reduced_final_payment(self):
        self.begin(1)
        self.m.control["287"] = "MZR"
        for _ in range(3):
            self.cycle()
        self.assertIn("ADISCORD_SHL.101", self.m.scheduled)
        self.m.run("SHL_extend_export")
        self.m.run("SHL_extend_export")
        self.assertEqual(self.c["SHL_obligation_deadline"], 5)
        self.assertEqual(self.c["SHL_obligation_liability"], 120)
        self.m.control["287"] = "SHL"
        self.c["SHL_shift_policy"] = 1
        self.m.variables["287"]["SHL_furnace_stock"] = 2
        before = self.c["ADISCORD_economy_treasury"]
        self.cycle()
        self.assertNotIn("SHL_obligation_kind", self.c)
        self.assertEqual(self.c["ADISCORD_economy_treasury"], before + 90)

    def relief(self, donor="287", recipient="288", stopped=False):
        self.begin(5, donor)
        self.m.variables[recipient].update({"SHL_furnace_wear": 50, "SHL_furnace_stock": 1, "SHL_furnace_running": 0 if stopped else 1})
        self.m.run("SHL_choose_relief_recipient", target=recipient)

    def test_running_relief_delivers_independently_of_state_order(self):
        for donor, recipient in [("287", "288"), ("288", "287")]:
            with self.subTest(donor=donor):
                self.setUp()
                self.relief(donor, recipient)
                self.c["SHL_obligation_progress"] = 1
                self.cycle()
                self.assertEqual(self.m.variables[recipient]["SHL_furnace_wear"], 26)
                self.assertNotIn("SHL_obligation_kind", self.c)

    def test_completed_relief_waits_if_recipient_goes_cold_in_same_cycle(self):
        self.relief()
        self.c["SHL_obligation_progress"] = 1
        recipient = self.m.variables["288"]
        recipient.update({"SHL_furnace_stock": 0, "SHL_furnace_shortages": 1})
        self.cycle()
        self.assertEqual(self.c["SHL_obligation_progress"], 2)
        self.assertEqual(recipient["SHL_furnace_running"], 0)
        self.m.run("SHL_refresh_furnaces")
        self.c["SHL_selected_furnace"] = 1
        self.m.run("SHL_refresh_selected_furnace")
        self.assertEqual(self.c["SHL_selected_period_income"], 0)
        recipient["SHL_furnace_stock"] = 1
        self.cycle()
        self.assertEqual(recipient["SHL_furnace_running"], 1)
        self.assertEqual(recipient["SHL_furnace_stock"], 0)
        self.assertEqual(recipient["SHL_furnace_wear"], 20)
        self.assertNotIn("SHL_obligation_kind", self.c)

    def test_relief_cannot_replace_a_paid_repair_or_its_receipt(self):
        self.relief(stopped=True)
        self.m.variables["288"]["SHL_operation_deposit"] = 80
        self.cycle()
        self.assertEqual(self.c["SHL_obligation_progress"], 0)
        self.assertEqual(self.m.variables["288"]["SHL_operation_deposit"], 80)
        self.assertEqual(self.c["SHL_last_cycle_income"], 420)

    def test_relief_preview_follows_recipient_readiness(self):
        self.relief(stopped=True)
        self.c["SHL_selected_furnace"] = 1
        self.m.run("SHL_refresh_furnaces")
        self.assertEqual(self.c["SHL_selected_period_income"], 0)
        self.m.variables["288"]["SHL_operation_deposit"] = 80
        self.m.run("SHL_refresh_furnaces")
        self.assertEqual(self.c["SHL_selected_period_income"], 0)

    def test_foreclosure_removes_a_real_vote_and_cannot_repeat(self):
        self.begin(4)
        self.m.focuses.add("SHL_debt_shifts")
        self.m.run("SHL_refresh_furnaces")
        self.assertEqual(self.c["SHL_house_votes"], 9)
        self.m.run("SHL_foreclose_pledge")
        self.m.run("SHL_foreclose_pledge")
        self.assertEqual(self.c["SHL_house_votes"], 8)
        self.assertEqual(self.m.variables["287"]["SHL_furnace_owner"], 1)
        self.assertEqual(self.c["ADISCORD_economy_treasury"], 1150)
        self.assertNotIn("SHL_obligation_kind", self.c)

    def test_affordability_and_second_site_cannot_overwrite_receipt(self):
        self.c["ADISCORD_economy_treasury"] = 89.99
        self.begin(3)
        self.assertNotIn("SHL_obligation_kind", self.c)
        self.c["ADISCORD_economy_treasury"] = 90
        self.begin(3)
        self.m.run("SHL_begin_arsenal_order", target="288")
        self.assertEqual(self.c["ADISCORD_economy_treasury"], 0)
        self.assertEqual(self.c["SHL_obligation_site"], 287)

    def test_early_platforms_precede_capital_ratification(self):
        for focus in ("SHL_new_house", "SHL_open_conclave", "SHL_nur_directorate"):
            self.assertEqual(scalar(block(focus_definition(focus), "prerequisite"), "focus"), "SHL_conclave_rules")
        for focus in ("SHL_admit_tenth_house", "SHL_rights_without_fire", "SHL_state_furnaces"):
            prerequisites = [scalar(e.value, "focus") for e in focus_definition(focus) if e.key == "prerequisite"]
            self.assertIn("SHL_workers_charter", prerequisites)
            self.assertEqual(len(prerequisites), 2)
        self.c["SHL_political_course"] = 3
        self.assertTrue(self.m.matches(self.m.triggers["SHL_arsenal_access"], "SHL"))


class CrisisLayerTests(unittest.TestCase):
    def setUp(self):
        effects = parse_clausewitz(EFFECT_PATH.read_text(encoding="utf-8"))
        triggers = parse_clausewitz(TRIGGER_PATH.read_text(encoding="utf-8"))
        self.m = ScriptMachine(effects, triggers)
        for state in range(287, 296):
            self.m.variables[str(state)].update({
                "SHL_furnace_stock": 3.0,
                "SHL_furnace_wear": 20.0,
                "SHL_furnace_owner": 0.0,
                "SHL_furnace_running": 1.0,
                "SHL_furnace_training": 0.0,
            })
        self.m.flags["SHL"].add("SHL_furnaces_initialized")
        self.m.variables["SHL"]["SHL_shift_policy"] = 0.0
        self.m.run("SHL_initialize_tensions")
        self.m.run("SHL_refresh_furnaces")

    def country(self):
        return self.m.variables["SHL"]

    def test_overtime_and_idle_sites_raise_unrest_once_per_cycle(self):
        c = self.country()
        c["SHL_shift_policy"] = 1
        c["SHL_cycle_idle_sites"] = 2
        self.m.run("SHL_update_tensions")
        self.assertEqual(c["SHL_unrest"], 31)
        self.assertEqual(c["SHL_house_pressure"], 25)

    def test_reform_courses_move_crest_pressure(self):
        c = self.country()
        c["SHL_political_course"] = 3
        self.m.run("SHL_update_tensions")
        self.assertEqual(c["SHL_house_pressure"], 28)
        c["SHL_political_course"] = 1
        self.m.run("SHL_update_tensions")
        self.assertEqual(c["SHL_house_pressure"], 31)

    def test_strike_fires_once_and_charges_every_producing_furnace(self):
        c = self.country()
        c["SHL_unrest"] = 60
        self.m.run("SHL_check_crises")
        self.m.run("SHL_check_crises")
        self.assertEqual(self.m.scheduled.count("ADISCORD_SHL.20"), 1)
        self.assertEqual(c["SHL_income_deduction"], 10)
        before = c["ADISCORD_economy_treasury"]
        self.m.run("SHL_produce_period")
        self.assertEqual(c["ADISCORD_economy_treasury"] - before, 9 * 50)

    def test_strike_concession_is_paid_once_and_sets_cooldown(self):
        c = self.country()
        c["SHL_unrest"] = 70
        c["SHL_cycle_number"] = 5
        self.m.run("SHL_check_crises")
        self.m.run("SHL_strike_concede")
        self.m.run("SHL_strike_concede")
        self.assertEqual(c["ADISCORD_economy_treasury"], 850)
        self.assertEqual(c["SHL_unrest"], 35)
        self.assertEqual(c["SHL_strike_ready_cycle"], 9)
        self.assertEqual(c["SHL_income_deduction"], 0)
        c["SHL_unrest"] = 80
        self.m.run("SHL_check_crises")
        self.assertEqual(self.m.scheduled.count("ADISCORD_SHL.20"), 1)

    def test_second_crackdown_escalates_to_the_councils(self):
        c = self.country()
        c["SHL_unrest"] = 70
        self.m.run("SHL_check_crises")
        self.m.run("SHL_strike_suppress")
        self.assertNotIn("ADISCORD_SHL.21", self.m.scheduled)
        c["SHL_strike_ready_cycle"] = 0
        c["SHL_unrest"] = 70
        self.m.run("SHL_check_crises")
        self.m.run("SHL_strike_suppress")
        self.assertIn("ADISCORD_SHL.21", self.m.scheduled)

    def test_commune_transfers_every_owned_furnace_and_stops_crests(self):
        c = self.country()
        self.m.variables["290"]["SHL_furnace_running"] = 0
        self.m.run("SHL_commit_commune_course")
        self.m.run("SHL_give_furnaces_to_workers")
        self.assertEqual(c["SHL_political_course"], 5)
        self.assertEqual(self.m.variables["287"]["SHL_furnace_owner"], 1)
        self.assertEqual(self.m.variables["290"]["SHL_restart_settled"], 1)
        self.assertEqual(c["SHL_pp_gain"], 0.06)
        c["SHL_house_pressure"] = 90
        self.assertFalse(self.m.matches(parse_clausewitz("SHL_conspiracy_ready = yes"), "SHL"))

    def test_regency_cannot_replace_the_commune(self):
        c = self.country()
        self.m.run("SHL_commit_commune_course")
        self.m.run("SHL_commit_regency_course")
        self.assertEqual(c["SHL_political_course"], 5)
        self.assertNotIn("SHL_regency_path", self.m.flags["SHL"])

    def test_accident_extinguishes_only_the_flagged_site(self):
        c = self.country()
        self.m.state_buildings[("288", "industrial_complex")] = 1
        self.m.variables["288"]["SHL_furnace_wear"] = 86
        self.m.run("SHL_produce_period")
        self.assertIn("ADISCORD_SHL.40", self.m.scheduled)
        self.assertIn("SHL_accident_site", self.m.flags["288"])
        c["SHL_cycle_number"] = 3
        self.m.flags["SHL"].add("SHL_accident_commission")
        self.m.run("SHL_resolve_accident")
        self.assertEqual(self.m.variables["288"]["SHL_furnace_running"], 0)
        self.assertEqual(self.m.variables["288"]["SHL_furnace_training"], 1)
        self.assertEqual(self.m.variables["287"]["SHL_furnace_running"], 1)
        self.assertEqual(c["SHL_accident_ready_cycle"], 9)
        self.assertNotIn("SHL_accident_pending", self.m.flags["SHL"])
        self.assertIn(("damage_building", "288"), self.m.calls)

    def test_accident_without_a_factory_still_closes_the_furnace_and_settles(self):
        self.m.flags["287"].add("SHL_accident_site")
        self.m.flags["SHL"].update({"SHL_accident_pending", "SHL_accident_commission"})
        self.country()["SHL_cycle_number"] = 3
        self.m.run("SHL_resolve_accident")
        self.assertEqual(self.m.variables["287"]["SHL_furnace_running"], 0)
        self.assertEqual(self.m.variables["287"]["SHL_furnace_training"], 1)
        self.assertNotIn(("damage_building", "287"), self.m.calls)
        self.assertNotIn("SHL_accident_site", self.m.flags["287"])
        self.assertNotIn("SHL_accident_pending", self.m.flags["SHL"])
        self.assertNotIn("SHL_accident_commission", self.m.flags["SHL"])
        self.assertEqual(self.country()["SHL_accident_ready_cycle"], 9)

    def test_water_crisis_wakes_keyzan_and_wears_only_border_furnaces(self):
        c = self.country()
        c["SHL_cycle_number"] = 8
        self.m.run("SHL_check_crises")
        self.assertEqual(c["SHL_water_crisis"], 1)
        self.assertIn(("ADISCORD_release_non_participating_minor_optimization", "KYZ"), self.m.calls)
        self.m.run("SHL_produce_period")
        self.assertEqual(self.m.variables["287"]["SHL_furnace_wear"], 30)
        self.assertEqual(self.m.variables["290"]["SHL_furnace_wear"], 26)

    def test_water_treaty_is_paid_only_after_keyzan_accepts(self):
        c = self.country()
        c["SHL_water_crisis"] = 1
        self.m.flags["SHL"].add("SHL_water_offer_pending")
        self.assertEqual(c["ADISCORD_economy_treasury"], 1000)
        self.m.run("SHL_sign_water_treaty", scope="KYZ")
        self.m.run("SHL_sign_water_treaty", scope="KYZ")
        self.assertEqual(c["ADISCORD_economy_treasury"], 900)
        self.assertEqual(c["SHL_water_crisis"], 2)
        self.assertEqual(c["SHL_income_deduction"], 3)

    def test_wells_refund_when_the_dispute_closed_first(self):
        c = self.country()
        c["SHL_water_crisis"] = 1
        self.m.run("SHL_begin_wells")
        self.assertEqual(c["ADISCORD_economy_treasury"], 750)
        c["SHL_water_crisis"] = 2
        self.m.run("SHL_finish_wells")
        self.m.run("SHL_finish_wells")
        self.assertEqual(c["ADISCORD_economy_treasury"], 1000)
        self.assertEqual(c["SHL_water_crisis"], 2)

    def test_qanat_war_victory_transfers_only_keyzan_land_once(self):
        c = self.country()
        c["SHL_water_crisis"] = 1
        self.m.focuses.add("SHL_qanat_guard")
        self.m.ownership["285"] = "MZR"
        self.m.run("SHL_start_kyz_war")
        self.assertIn(frozenset(("SHL", "KYZ")), self.m.wars)
        self.m.run("SHL_kyz_war_victory")
        self.m.run("SHL_kyz_war_victory")
        self.assertEqual(self.m.ownership["280"], "SHL")
        self.assertEqual(self.m.ownership["285"], "MZR")
        self.assertEqual(c["SHL_water_crisis"], 4)
        self.assertEqual(self.m.scheduled.count("ADISCORD_SHL.57"), 1)
        self.assertNotIn(frozenset(("SHL", "KYZ")), self.m.wars)

    def test_qanat_war_defeat_cedes_arbin_and_imposes_quota(self):
        c = self.country()
        c["SHL_water_crisis"] = 1
        self.m.focuses.add("SHL_qanat_guard")
        self.m.run("SHL_start_kyz_war")
        self.m.run("SHL_kyz_war_defeat")
        self.assertEqual(self.m.ownership["287"], "KYZ")
        self.assertEqual(c["SHL_water_quota"], 1)
        self.assertEqual(c["SHL_income_deduction"], 3)

    def test_port_war_sea_goal_follows_key_to_sea(self):
        c = self.country()
        c["SHL_veyr_crisis"] = 1
        self.m.focuses.add("SHL_key_to_sea")
        self.m.run("SHL_start_glp_war")
        self.m.run("SHL_glp_war_victory")
        for state in ("297", "298", "299", "708"):
            self.assertEqual(self.m.ownership[state], "SHL")
        self.assertEqual(c["SHL_veyr_crisis"], 4)
        self.assertEqual(c["SHL_income_deduction"], 0)

    def test_mazar_warned_demand_begins_at_cycle_ten(self):
        c = self.country()
        c["SHL_cycle_number"] = 9
        self.m.stability = 0.5
        self.m.run("SHL_check_crises")
        self.assertNotIn("ADISCORD_SHL.70", self.m.scheduled)
        c["SHL_cycle_number"] = 10
        self.m.run("SHL_check_crises")
        self.assertIn("ADISCORD_SHL.70", self.m.scheduled)

    def test_mazar_refusal_leads_to_war_and_buyout_closes_the_threat(self):
        c = self.country()
        c["SHL_mazar_state"] = 1
        self.m.run("SHL_mazar_refuse")
        self.assertIn("SHL_mazar_deadline", self.m.missions)
        self.m.run("SHL_mazar_buyout")
        self.assertEqual(c["SHL_mazar_state"], 3)
        self.assertNotIn("SHL_mazar_deadline", self.m.missions)
        self.m.run("SHL_start_mzr_war")
        self.assertNotIn(frozenset(("MZR", "SHL")), self.m.wars)

    def test_busy_mazar_postpones_instead_of_discarding(self):
        c = self.country()
        c["SHL_mazar_state"] = 5
        c["SHL_cycle_number"] = 20
        self.m.countries["MZR"]["has_war"] = True
        self.m.run("SHL_start_mzr_war")
        self.assertEqual(c["SHL_mazar_state"], 2)
        self.assertEqual(c["SHL_mazar_repeat_cycle"], 24)

    def test_mazar_defeat_takes_two_fifths_of_a_positive_treasury(self):
        c = self.country()
        c["SHL_mazar_state"] = 5
        self.m.run("SHL_start_mzr_war")
        self.assertIn(frozenset(("MZR", "SHL")), self.m.wars)
        self.m.run("SHL_mzr_war_defeat")
        self.assertAlmostEqual(c["ADISCORD_economy_treasury"], 600)
        self.assertEqual(c["SHL_mazar_state"], 3)
        self.assertIn("SHL_mazar_ration", self.m.ideas)
        self.assertEqual(self.m.ownership["707"], "SHL")

    def test_guard_levy_refunds_exactly_when_capital_is_lost(self):
        c = self.country()
        self.m.run("SHL_begin_guard_order")
        self.m.run("SHL_begin_guard_order")
        self.assertEqual(c["ADISCORD_economy_treasury"], 850)
        self.assertEqual(self.m.manpower, 97000)
        self.m.control["699"] = "MZR"
        self.m.run("SHL_finish_guard_order")
        self.assertEqual(c["ADISCORD_economy_treasury"], 1000)
        self.assertEqual(self.m.manpower, 100000)
        self.assertEqual(self.m.values["political_power"], 200)
        self.assertEqual(self.m.divisions, 2)

    def test_guard_levy_spawns_one_division_in_the_capital(self):
        self.m.control["294"] = "MZR"
        self.m.run("SHL_begin_guard_order")
        self.m.run("SHL_finish_guard_order")
        self.m.run("SHL_finish_guard_order")
        self.assertEqual(self.m.divisions, 3)
        self.assertIn("Furnace Levy", self.m.calls)
        self.assertEqual(self.m.unit_owners, [("699", "SHL")])
        self.assertEqual(self.m.scheduled.count("ADISCORD_SHL.122"), 1)

    def test_partner_joins_only_a_free_shahrabad_alliance(self):
        self.country()["SHL_political_course"] = 2
        self.m.run("SHL_request_southern_alliance")
        self.m.run("SHL_join_southern_compact", scope="KYZ")
        self.assertEqual(self.m.factions.get("KYZ"), "SHL")
        self.country()["SHL_political_course"] = 1
        self.m.run("SHL_request_golden_alliance")
        self.m.run("SHL_join_golden_gate", scope="GLP")
        self.assertEqual(self.m.factions.get("GLP"), "SHL")
        self.assertIn("ADISCORD_SHL.92", self.m.scheduled)

    def test_late_alliance_enters_existing_mazar_war_on_shahrabad_side(self):
        self.country()["SHL_political_course"] = 1
        self.country()["SHL_war_mzr"] = 1
        self.m.wars.add(frozenset(("SHL", "MZR")))
        self.m.run("SHL_request_golden_alliance")
        self.m.run("SHL_join_golden_gate", scope="GLP")
        self.assertEqual(self.m.factions["GLP"], "SHL")
        self.assertIn(frozenset(("GLP", "MZR")), self.m.wars)
        self.m.run("SHL_join_golden_gate", scope="GLP")
        self.assertEqual(self.m.calls.count(("add_to_war", "GLP")), 1)

    def test_late_trade_acceptance_reaches_finished_conclave_and_preserves_harbour(self):
        self.country()["SHL_political_course"] = 1
        self.country()["SHL_veyr_crisis"] = 3
        self.m.focuses.add("SHL_conclave_of_ten")
        self.m.run("SHL_sign_veyr_union", scope="GLP")
        self.assertEqual(self.country()["SHL_veyr_crisis"], 3)
        self.assertIn("ADISCORD_SHL.91", self.m.scheduled)
        self.m.run("SHL_request_golden_alliance")
        self.assertEqual(self.m.scheduled.count("ADISCORD_SHL.91"), 1)

    def test_alliance_refusal_can_be_renewed_but_regime_change_invalidates_acceptance(self):
        self.country()["SHL_political_course"] = 1
        self.m.run("SHL_request_golden_alliance")
        events = parse_clausewitz((ROOT / "events/ADISCORD_SHL_events.txt").read_text(encoding="utf-8"))
        offer = next(e.value for e in events if e.key == "country_event" and scalar(e.value, "id") == "ADISCORD_SHL.91")
        refusal = next(e.value for e in offer if e.key == "option" and scalar(e.value, "name") == "ADISCORD_SHL.91.b")
        self.m.execute(block(refusal, "hidden_effect"), "GLP")
        self.m.run("SHL_request_golden_alliance")
        self.assertEqual(self.m.scheduled.count("ADISCORD_SHL.91"), 2)
        self.country()["SHL_political_course"] = 5
        self.m.run("SHL_join_golden_gate", scope="GLP")
        self.assertNotIn("GLP", self.m.factions)
        self.assertNotIn("SHL_golden_alliance_pending", self.m.flags["SHL"])

    def test_finals_require_both_nonexclusive_preparations(self):
        for identifier in ("SHL_conclave_of_ten", "SHL_southern_compact", "SHL_iron_shahrabad", "SHL_hereditary_republic", "SHL_commune_of_fire"):
            prerequisites = [e.value for e in focus_definition(identifier) if e.key == "prerequisite"]
            self.assertEqual(len(prerequisites), 2, identifier)
            self.assertTrue(all(len(blocks) == 1 for blocks in prerequisites), identifier)

    def test_directorate_final_handles_neighbour_lost_before_crisis(self):
        available = block(focus_definition("SHL_iron_shahrabad"), "available")
        for tag, crisis, effect in (
            ("KYZ", "SHL_water_crisis", "SHL_start_water_crisis"),
            ("GLP", "SHL_veyr_crisis", "SHL_start_veyr_crisis"),
        ):
            with self.subTest(neighbour=tag):
                self.setUp()
                self.country().update({
                    "SHL_political_course": 3,
                    "SHL_water_crisis": 3,
                    "SHL_veyr_crisis": 3,
                    crisis: 0,
                })
                self.assertFalse(self.m.matches(available, "SHL"))
                self.m.countries[tag]["exists"] = False
                self.m.run(effect)
                self.assertEqual(self.country()[crisis], 0)
                self.assertTrue(self.m.matches(available, "SHL"))
                self.country()["SHL_running_count"] = 5
                self.assertFalse(self.m.matches(available, "SHL"))
                self.country()["SHL_running_count"] = 9
                self.country()[crisis] = 1
                self.assertFalse(self.m.matches(available, "SHL"))

    def test_every_crisis_event_and_decision_key_is_localised(self):
        effects = EFFECT_PATH.read_text(encoding="utf-8")
        events = (ROOT / "events/ADISCORD_SHL_events.txt").read_text(encoding="utf-8")
        decisions = (ROOT / "common/decisions/ADISCORD_SHL_decisions.txt").read_text(encoding="utf-8")
        focuses = (ROOT / "focus_trees/SHL/main/focuses.txt").read_text(encoding="utf-8")
        keys = set(re.findall(r"\b(ADISCORD_SHL\.\d+\.[a-z])\b", events))
        keys |= set(re.findall(r"custom_effect_tooltip = (\w+)", effects + events + decisions + focuses))
        keys |= set(re.findall(r"tooltip = (\w+)", events + decisions + focuses))
        keys |= set(re.findall(r"custom_cost_text = (\w+)", decisions))
        for language in ("russian", "english"):
            text = (ROOT / f"localisation/{language}/ADISCORD_SHL_l_{language}.yml").read_text(encoding="utf-8-sig")
            # Shared southern final war keys stay in their own system file.
            text += (ROOT / f"localisation/{language}/ADISCORD_south_final_war_l_{language}.yml").read_text(encoding="utf-8-sig")
            defined = set(re.findall(r"^ ([\w.]+):", text, re.M))
            self.assertEqual(sorted(keys - defined), [], language)


class MazarBorderPactTests(unittest.TestCase):
    setUp = CrisisLayerTests.setUp
    country = CrisisLayerTests.country

    def prepare(self, partner="KYZ"):
        self.m.flags[partner].add("SHL_mzr_border_grievance")
        self.country()["SHL_mazar_state"] = 1
        self.m.run("SHL_mazar_refuse")

    def start(self, partner="KYZ", ally=None):
        self.prepare(partner)
        self.m.run("SHL_accept_mzr_pact", scope=partner)
        if ally:
            self.m.factions.update({"SHL": "SHL", ally: "SHL"})
        self.m.run("SHL_start_mzr_war")

    def event(self, number):
        events = parse_clausewitz((ROOT / "events/ADISCORD_SHL_events.txt").read_text(encoding="utf-8"))
        return next(e.value for e in events if e.key == "country_event" and scalar(e.value, "id") == f"ADISCORD_SHL.{number}")

    def capitulate(self, loser, winner):
        source = (ROOT / "common/on_actions/09_ADISCORD_scripted_peace_on_actions.txt").read_text(encoding="utf-8")
        section = source.split("# BEGIN shahrabad:on_capitulation", 1)[1].split("# END shahrabad:on_capitulation", 1)[0]
        self.m.root_scope = loser
        self.m.execute(parse_clausewitz(section), loser, winner)

    def test_only_actual_military_action_creates_a_grievance(self):
        for partner, crisis, focus, start, armistice in (
            ("KYZ", "SHL_water_crisis", "SHL_right_to_water", "SHL_start_kyz_war", "SHL_kyz_war_armistice"),
            ("GLP", "SHL_veyr_crisis", "SHL_veyr_ultimatum", "SHL_start_glp_war", "SHL_glp_war_armistice"),
        ):
            with self.subTest(partner=partner):
                self.setUp()
                self.country()[crisis] = 1
                self.m.focuses.add(focus)
                self.country()["SHL_mazar_state"] = 1
                self.m.run("SHL_mazar_refuse")
                self.assertNotIn("ADISCORD_SHL.124", self.m.scheduled)
                self.m.run(start)
                self.m.run(armistice)
                self.assertIn("SHL_mzr_border_grievance", self.m.flags[partner])
                self.m.run("SHL_clear_mzr_diplomacy")
                self.m.run("SHL_prepare_mzr_partner")
                self.assertIn("SHL_mzr_pact_pending", self.m.flags[partner])

    def test_at_most_one_announced_candidate_and_no_replacement_after_refusal(self):
        self.m.flags["GLP"].add("SHL_mzr_border_grievance")
        self.prepare()
        self.m.run("SHL_prepare_mzr_partner")
        self.assertEqual(self.m.scheduled.count("ADISCORD_SHL.124"), 1)
        self.assertIn("SHL_mzr_pact_pending", self.m.flags["KYZ"])
        self.assertNotIn("SHL_mzr_pact_pending", self.m.flags["GLP"])
        first_option = block(self.event(125), "option")
        self.m.execute(block(first_option, "hidden_effect"), "KYZ")
        self.m.run("SHL_prepare_mzr_partner")
        self.m.run("SHL_start_mzr_war")
        self.assertNotIn(frozenset(("KYZ", "SHL")), self.m.wars)
        self.assertNotIn(frozenset(("GLP", "SHL")), self.m.wars)

    def test_subject_foreign_faction_war_or_lost_border_blocks_candidate(self):
        for reason in ("subject", "faction", "war", "border", "absent", "mazar_faction"):
            with self.subTest(reason=reason):
                self.setUp()
                if reason == "subject":
                    self.m.countries["KYZ"]["is_subject"] = True
                elif reason == "faction":
                    self.m.factions["KYZ"] = "VAL"
                elif reason == "war":
                    self.m.wars.add(frozenset(("KYZ", "VAL")))
                elif reason == "border":
                    self.m.neighbours.remove("KYZ")
                elif reason == "absent":
                    self.m.countries["KYZ"]["exists"] = False
                else:
                    self.m.factions["MZR"] = "VAL"
                self.prepare()
                self.assertNotIn("ADISCORD_SHL.125", self.m.scheduled)

    def test_both_candidates_join_the_existing_war_with_no_extra_declaration(self):
        for partner, ally in (("KYZ", "GLP"), ("GLP", "KYZ")):
            with self.subTest(partner=partner):
                self.setUp()
                self.start(partner, ally)
                self.assertEqual(self.m.factions[partner], "MZR")
                self.assertEqual(self.m.majors, {"SHL", "MZR"})
                self.assertEqual(len([call for call in self.m.calls if call[0] == "declare_war_on"]), 1)
                for opponent in ("MZR", partner):
                    for friend in ("SHL", ally):
                        self.assertIn(frozenset((opponent, friend)), self.m.wars)
                self.assertNotIn("SHL_mzr_pact_pending", self.m.flags[partner])

    def test_offensive_warns_during_the_existing_28_day_mobilization(self):
        self.m.flags["GLP"].add("SHL_mzr_border_grievance")
        self.m.focuses.add("SHL_no_more_rations")
        self.m.run("SHL_begin_mzr_mobilization")
        self.assertIn("ADISCORD_SHL.124", self.m.scheduled)
        self.assertFalse(self.m.wars)
        self.m.run("SHL_accept_mzr_pact", scope="GLP")
        self.m.run("SHL_finish_mzr_mobilization")
        self.assertIn(("declare_war_on", "SHL", "MZR"), self.m.calls)
        self.assertIn(frozenset(("GLP", "SHL")), self.m.wars)

    def test_neutrality_payment_requires_choice_and_is_exactly_once(self):
        for partner in ("KYZ", "GLP"):
            with self.subTest(partner=partner):
                self.setUp()
                self.prepare(partner)
                self.m.run("SHL_accept_mzr_pact", scope=partner)
                self.country()["ADISCORD_economy_treasury"] = 100
                self.m.values["political_power"] = 30
                self.m.run("SHL_request_mzr_neutrality")
                self.m.run("SHL_request_mzr_neutrality")
                self.assertEqual(self.m.scheduled.count("ADISCORD_SHL.126"), 1)
                self.assertEqual(self.country()["ADISCORD_economy_treasury"], 100)
                self.m.run("SHL_accept_mzr_neutrality", scope=partner)
                self.m.run("SHL_accept_mzr_neutrality", scope=partner)
                self.assertEqual(self.country()["ADISCORD_economy_treasury"], 0)
                self.assertEqual(self.m.values["political_power"], 0)
                self.assertEqual(self.m.variables[partner]["ADISCORD_economy_treasury"], 100)
                self.m.run("SHL_accept_mzr_pact", scope=partner)
                self.m.run("SHL_start_mzr_war")
                self.assertNotIn(frozenset((partner, "SHL")), self.m.wars)

    def test_changed_funds_and_late_answers_never_charge_or_change_sides(self):
        for reason in ("treasury", "political_power", "war", "peace", "faction", "subject"):
            with self.subTest(reason=reason):
                self.setUp()
                self.prepare()
                self.m.run("SHL_accept_mzr_pact", scope="KYZ")
                self.m.run("SHL_request_mzr_neutrality")
                if reason == "treasury":
                    self.country()["ADISCORD_economy_treasury"] = 99.9
                elif reason == "political_power":
                    self.m.values["political_power"] = 29.9
                elif reason == "war":
                    self.m.run("SHL_start_mzr_war")
                elif reason == "peace":
                    self.m.run("SHL_mazar_buyout")
                elif reason == "faction":
                    self.m.factions["KYZ"] = "VAL"
                else:
                    self.m.countries["KYZ"]["is_subject"] = True
                balances = (self.country()["ADISCORD_economy_treasury"], self.m.values["political_power"])
                self.m.run("SHL_accept_mzr_neutrality", scope="KYZ")
                self.assertEqual(balances, (self.country()["ADISCORD_economy_treasury"], self.m.values["political_power"]))
                self.assertNotIn("ADISCORD_economy_treasury", self.m.variables["KYZ"])
                if reason == "war":
                    self.assertIn(frozenset(("KYZ", "SHL")), self.m.wars)

    def test_existing_treaties_and_alliance_supersede_the_pact(self):
        for partner, effect, course in (
            ("KYZ", "SHL_sign_water_treaty", 0),
            ("KYZ", "SHL_sign_water_brotherhood", 0),
            ("GLP", "SHL_sign_veyr_union", 0),
            ("KYZ", "SHL_join_southern_compact", 2),
            ("GLP", "SHL_join_golden_gate", 1),
        ):
            with self.subTest(effect=effect):
                self.setUp()
                self.prepare(partner)
                self.m.run("SHL_accept_mzr_pact", scope=partner)
                self.country().update({"SHL_water_crisis": 1, "SHL_political_course": course})
                self.m.flags["SHL"].update({"SHL_southern_alliance_pending", "SHL_golden_alliance_pending"})
                self.m.run(effect, scope=partner)
                self.assertNotIn("SHL_mzr_border_grievance", self.m.flags[partner])
                self.m.run("SHL_start_mzr_war")
                self.assertNotIn(frozenset((partner, "SHL")), self.m.wars)

    def test_late_trade_offer_does_not_reconcile_an_active_enemy(self):
        self.start("GLP")
        self.m.run("SHL_sign_veyr_union", scope="GLP")
        self.assertNotIn("SHL_veyr_partner", self.m.flags["SHL"])
        self.assertIn("SHL_mzr_war_partner", self.m.flags["GLP"])

    def test_every_settlement_closes_both_fronts_and_preserves_unrelated_wars(self):
        for effect in ("SHL_mzr_war_victory", "SHL_mzr_war_defeat", "SHL_mzr_war_armistice", "SHL_close_external_mzr_war"):
            with self.subTest(effect=effect):
                self.setUp()
                self.start("KYZ", "GLP")
                foreign_war = frozenset(("KYZ", "VAL"))
                self.m.wars.add(foreign_war)
                if effect == "SHL_close_external_mzr_war":
                    self.m.countries["MZR"]["is_subject"] = True
                self.m.run(effect)
                self.assertEqual(self.m.wars, {foreign_war})
                self.assertNotIn("MZR", self.m.factions)
                self.assertEqual(self.m.factions["GLP"], "SHL")
                self.assertFalse(self.m.majors)
                for tag in ("KYZ", "GLP"):
                    self.assertFalse(self.m.flags[tag] & {"SHL_mzr_war_partner", "SHL_mzr_shl_partner", "SHL_mzr_neutrality_pending"})

    def test_neighbour_capitulations_remain_occupied_until_principal_settlement(self):
        for loser, winner in (("KYZ", "SHL"), ("KYZ", "GLP"), ("GLP", "KYZ")):
            with self.subTest(loser=loser, winner=winner):
                self.setUp()
                self.start("KYZ", "GLP")
                before = set(self.m.wars)
                self.capitulate(loser, winner)
                self.assertIn("skip_default_capitulation", self.m.global_flags)
                self.assertEqual(self.m.wars, before)
                self.assertEqual(self.country()["SHL_war_mzr"], 1)

    def test_shahrabad_defeat_by_partner_uses_mazar_terms(self):
        self.start()
        self.capitulate("SHL", "KYZ")
        self.assertEqual(self.country()["SHL_mzr_outcome"], 4)
        self.assertEqual(self.country()["ADISCORD_economy_treasury"], 600)
        self.assertFalse(self.m.wars)
        self.assertEqual(self.m.ownership["707"], "SHL")

    def test_mazar_defeat_by_shahrabad_ally_ends_partner_war(self):
        self.start("KYZ", "GLP")
        self.capitulate("MZR", "GLP")
        self.assertEqual(self.country()["SHL_mzr_outcome"], 1)
        self.assertFalse(self.m.wars)
        self.assertEqual(self.m.ownership["269"], "SHL")
        self.assertEqual(self.m.ownership["280"], "KYZ")

    def test_absent_or_busy_partner_is_not_replaced_at_declaration(self):
        self.m.flags["GLP"].add("SHL_mzr_border_grievance")
        self.prepare()
        self.m.run("SHL_accept_mzr_pact", scope="KYZ")
        self.m.countries["KYZ"]["is_subject"] = True
        self.m.run("SHL_start_mzr_war")
        self.assertEqual(self.m.wars, {frozenset(("SHL", "MZR"))})

    def test_postponement_and_cancelled_preparation_clear_open_offers(self):
        self.prepare()
        self.m.run("SHL_accept_mzr_pact", scope="KYZ")
        self.m.countries["MZR"]["has_war"] = True
        self.m.run("SHL_start_mzr_war")
        self.assertNotIn("SHL_mzr_pact_signed", self.m.flags["KYZ"])
        self.assertNotIn("SHL_mzr_diplomacy_started", self.m.flags["SHL"])
        self.m.run("SHL_accept_mzr_pact", scope="KYZ")
        self.assertNotIn("SHL_mzr_pact_signed", self.m.flags["KYZ"])

    def test_cancelled_offensive_clears_invitation_without_a_remaining_deadline(self):
        self.m.flags["KYZ"].add("SHL_mzr_border_grievance")
        self.m.focuses.add("SHL_no_more_rations")
        self.m.run("SHL_begin_mzr_mobilization")
        self.m.run("SHL_request_mzr_neutrality")
        self.m.run("SHL_cancel_mzr_mobilization")
        self.assertNotIn("SHL_mzr_diplomacy_started", self.m.flags["SHL"])
        self.assertNotIn("SHL_mzr_pact_pending", self.m.flags["KYZ"])
        self.assertNotIn("SHL_mzr_neutrality_pending", self.m.flags["KYZ"])

    def test_annexed_mazar_cleans_up_the_pacts_successor_leader(self):
        self.start()
        self.m.countries["MZR"]["exists"] = False
        self.m.factions.pop("MZR")
        self.m.factions["KYZ"] = "KYZ"
        self.m.run("SHL_close_external_mzr_war")
        self.assertFalse(self.m.factions)
        self.assertFalse(self.m.wars)
        self.assertFalse(self.m.majors)

    def test_nonparticipant_war_and_preexisting_major_are_preserved(self):
        self.m.majors.add("MZR")
        self.country()["SHL_mazar_state"] = 5
        self.m.run("SHL_start_mzr_war")
        foreign_war = frozenset(("KYZ", "MZR"))
        self.m.wars.add(foreign_war)
        self.m.run("SHL_mzr_war_armistice")
        self.assertEqual(self.m.wars, {foreign_war})
        self.assertEqual(self.m.majors, {"MZR"})

    def test_major_release_preserves_another_campaign_and_transfers_the_khan_receipt(self):
        for country in ("SHL", "MZR"):
            for other_receipt, keeps_major, khan_receipt in (
                (None, False, False),
                ("ADISCORD_south_added_major", True, False),
                ("RUS_crisis_defender", True, True),
            ):
                with self.subTest(country=country, other_receipt=other_receipt):
                    self.setUp()
                    self.m.majors.add(country)
                    self.m.flags[country].add("SHL_mzr_added_major")
                    if other_receipt:
                        self.m.flags[country].add(other_receipt)
                    other_country = "MZR" if country == "SHL" else "SHL"
                    self.m.flags[other_country].add("ADISCORD_west_added_major")
                    self.m.run("SHL_release_mzr_principal", scope=country)
                    self.m.run("SHL_release_mzr_principal", scope=country)
                    self.assertNotIn("SHL_mzr_added_major", self.m.flags[country])
                    self.assertEqual(country in self.m.majors, keeps_major)
                    self.assertEqual("RUS_crisis_added_major" in self.m.flags[country], khan_receipt)
                    if other_receipt:
                        self.assertIn(other_receipt, self.m.flags[country])

    def test_neutrality_timeout_is_free_and_keeps_the_existing_pact(self):
        self.prepare()
        self.m.run("SHL_accept_mzr_pact", scope="KYZ")
        self.m.run("SHL_request_mzr_neutrality")
        self.m.execute(block(block(self.event(126), "option"), "hidden_effect"), "KYZ")
        self.assertEqual(self.country()["ADISCORD_economy_treasury"], 1000)
        self.assertEqual(self.m.values["political_power"], 200)
        self.assertIn("SHL_mzr_pact_signed", self.m.flags["KYZ"])
        self.assertNotIn("SHL_mzr_neutrality_pending", self.m.flags["KYZ"])


class SouthernCampaignTests(unittest.TestCase):
    setUp = CrisisLayerTests.setUp
    country = CrisisLayerTests.country

    def ready(self, course=1, outcome=6):
        c = self.country()
        c.update({"SHL_political_course": course, "SHL_mazar_state": 3, "SHL_mzr_outcome": outcome})
        self.m.focuses.add("SHL_peace_has_a_price")
        return c

    def captured_cisterns(self, course):
        self.ready(course, 1)
        for state in ("269", "273"):
            self.m.ownership[state] = "SHL"
            self.m.control[state] = "SHL"

    def equipment(self):
        self.m.equipment[("SHL", "infantry_equipment")] = 2700
        self.m.equipment[("SHL", "ADISCORD_squad_weapons_equipment_0")] = 16
        self.m.manpower = 3000

    def convoy(self, overtime=False):
        self.m.focuses.add("SHL_campaign_logistics")
        self.country()["SHL_shift_policy"] = int(overtime)
        self.m.run("SHL_begin_campaign_convoy", target="287")

    def pour(self):
        self.m.run("SHL_produce_period")
        self.m.run("SHL_reconcile_obligation")
        if self.country().get("SHL_obligation_progress", 0) >= 2:
            self.m.run("SHL_complete_obligation")

    def test_initial_spirits_survive_initialization_and_leave_on_real_reforms(self):
        history = parse_clausewitz((ROOT / "history/countries/SHL - Shahrabad League.txt").read_text(encoding="utf-8"))
        ideas = {e.value for e in block(history, "add_ideas")}
        self.assertTrue({"SHL_hereditary_seats", "SHL_divided_guard", "SHL_external_freight"} <= ideas)
        self.m.ideas.update(ideas)
        self.m.run("SHL_refresh_furnaces")
        self.assertTrue(ideas - {"SHL_nine_furnaces_compact"} <= self.m.ideas)
        for focus in ("SHL_admit_tenth_house", "SHL_rights_without_fire", "SHL_state_furnaces", "SHL_restore_privileges", "SHL_furnaces_to_workers"):
            self.assertEqual(scalar(block(focus_definition(focus), "completion_reward"), "remove_ideas"), "SHL_hereditary_seats")
        self.m.focuses.add("SHL_rights_without_fire")
        self.m.run("SHL_refresh_furnaces")
        self.assertNotIn("SHL_hereditary_seats", self.m.ideas)
        self.assertIn("ADISCORD_economy_mark_dirty", self.m.calls)
        self.m.focuses.add("SHL_own_transport")
        self.country()["SHL_water_crisis"] = 2
        self.m.run("SHL_refresh_furnaces")
        self.assertIn("SHL_external_freight", self.m.ideas)
        self.country()["SHL_veyr_crisis"] = 4
        self.m.run("SHL_refresh_furnaces")
        self.assertNotIn("SHL_external_freight", self.m.ideas)
        self.assertEqual(scalar(block(focus_definition("SHL_southern_watch"), "completion_reward"), "remove_ideas"), "SHL_divided_guard")

    def test_ordinary_ai_queue_can_prepare_before_first_deadline(self):
        plan = parse_clausewitz((ROOT / "common/ai_strategy_plans/ADISCORD_SHL_plans.txt").read_text(encoding="utf-8"))[0].value
        queue = [e.value for e in block(plan, "ai_national_focuses")]
        completed = set()
        elapsed = 0
        dates = {}
        for identifier in queue:
            focus = focus_definition(identifier)
            for prerequisite in [e.value for e in focus if e.key == "prerequisite"]:
                self.assertTrue(any(e.value in completed for e in prerequisite), identifier)
            elapsed += int(scalar(focus, "cost")) * 7
            dates[identifier] = elapsed
            completed.add(identifier)
            if identifier == "SHL_city_war_mandate":
                break
        self.assertLessEqual(dates["SHL_campaign_logistics"] + 56, 280)
        self.assertLessEqual(dates["SHL_factory_militia"] + 21, 280)
        self.assertLess(dates["SHL_city_war_mandate"], 340)
        source = EFFECT_PATH.read_text(encoding="utf-8")
        self.assertIn("id = ADISCORD_SHL.110 days = 168", source)
        self.assertEqual(scalar(decision_definition("SHL_mazar_deadline"), "days_mission_timeout"), "60")

    def test_convoy_costs_two_actual_pours_and_is_consumed_once(self):
        self.convoy()
        c = self.country()
        self.m.run("SHL_begin_campaign_convoy", target="288")
        self.assertEqual(c["ADISCORD_economy_treasury"], 880)
        self.assertEqual(c["SHL_obligation_site"], 287)
        self.pour()
        self.assertNotIn("SHL_campaign_reserve", c)
        self.assertEqual(c["SHL_last_cycle_income"], 480)
        self.pour()
        self.assertEqual(c["SHL_campaign_reserve"], 1)
        self.assertEqual(self.m.variables["287"]["SHL_furnace_stock"], 1)
        self.assertNotIn("SHL_obligation_kind", c)
        self.m.run("SHL_use_campaign_reserve")
        self.assertEqual(self.m.idea_days["SHL_prepared_columns"], 90)
        self.m.run("SHL_demobilise_convoy")
        self.assertEqual(self.m.equipment[("SHL", "infantry_equipment")], 0)

    def test_overtime_accelerates_convoy_at_real_stock_and_wear_cost(self):
        self.convoy(True)
        self.pour()
        self.assertEqual(self.country()["SHL_campaign_reserve"], 1)
        self.assertEqual(self.m.variables["287"]["SHL_furnace_stock"], 1)
        self.assertEqual(self.m.variables["287"]["SHL_furnace_wear"], 30)

    def test_convoy_survives_course_change_but_refunds_lost_furnace(self):
        self.convoy()
        self.m.run("SHL_commit_state_course")
        self.m.run("SHL_reconcile_obligation")
        self.assertEqual(self.country()["SHL_obligation_kind"], 6)
        self.m.control["287"] = "MZR"
        self.m.run("SHL_reconcile_obligation")
        self.assertEqual(self.country()["ADISCORD_economy_treasury"], 880)
        self.assertEqual(self.country()["SHL_obligation_kind"], 6)
        self.m.ownership["287"] = "MZR"
        self.m.run("SHL_reconcile_obligation")
        self.assertEqual(self.country()["ADISCORD_economy_treasury"], 1000)
        self.assertNotIn("SHL_campaign_reserve", self.country())

    def test_proactive_march_has_correct_declarer_and_one_settlement(self):
        self.m.focuses.add("SHL_no_more_rations")
        self.m.values["political_power"] -= 50
        self.m.run("SHL_begin_mzr_mobilization")
        self.assertIn("ADISCORD_SHL.111", self.m.scheduled)
        self.m.run("SHL_finish_mzr_mobilization")
        self.m.run("SHL_finish_mzr_mobilization")
        declarations = [call for call in self.m.calls if isinstance(call, tuple) and call[0] == "declare_war_on"]
        self.assertEqual(declarations, [("declare_war_on", "SHL", "MZR")])
        self.assertEqual(self.m.values["political_power"], 150)

    def test_peace_during_mobilization_refunds_once_and_prevents_war(self):
        self.m.focuses.add("SHL_no_more_rations")
        self.m.values["political_power"] -= 50
        self.m.run("SHL_begin_mzr_mobilization")
        self.country()["SHL_mazar_state"] = 5
        self.m.run("SHL_mazar_buyout")
        self.m.run("SHL_finish_mzr_mobilization")
        self.m.run("SHL_cancel_mzr_mobilization")
        self.assertEqual(self.m.values["political_power"], 150)
        self.assertEqual(self.country()["ADISCORD_economy_treasury"], 650)
        self.assertEqual(self.m.wars, set())

    def test_paid_reserve_can_arrive_during_war_and_cleanup_removes_bonuses(self):
        self.convoy(True)
        self.country()["SHL_mazar_state"] = 5
        self.m.run("SHL_start_mzr_war")
        self.pour()
        self.assertIn("SHL_prepared_columns", self.m.ideas)
        self.assertNotIn("SHL_campaign_reserve", self.country())
        self.m.run("SHL_mzr_war_armistice")
        self.assertNotIn("SHL_prepared_columns", self.m.ideas)
        self.assertEqual(self.m.majors, set())

    def test_directorate_can_prepare_the_next_war_after_settling_mazar(self):
        for neighbour, crisis, focus, start in (
            ("KYZ", "SHL_water_crisis", "SHL_right_to_water", "SHL_start_kyz_war"),
            ("GLP", "SHL_veyr_crisis", "SHL_key_to_sea", "SHL_start_glp_war"),
        ):
            with self.subTest(neighbour=neighbour):
                self.setUp()
                c = self.ready(3)
                c.update({crisis: 1, "SHL_reserve_stock": 2})
                self.m.focuses.update({focus, "SHL_directorate_war_mandate"})
                self.convoy(True)
                self.pour()
                self.assertEqual(c["SHL_campaign_reserve"], 1)
                self.m.run("SHL_take_directorate_campaign_aid")
                self.m.run(start)
                self.assertIn(frozenset(("SHL", neighbour)), self.m.wars)
                self.assertEqual(self.m.idea_days["SHL_forced_columns"], 45)
                self.assertEqual(self.m.idea_days["SHL_prepared_columns"], 90)

    def test_peace_payment_closes_old_assistance_but_preserves_an_active_other_war(self):
        for parallel in (False, True):
            with self.subTest(parallel=parallel):
                self.setUp()
                self.country()["SHL_mazar_state"] = 1
                self.m.flags["SHL"].add("SHL_campaign_assistance_used")
                self.m.ideas.add("SHL_prepared_columns")
                if parallel:
                    self.m.wars.add(frozenset(("SHL", "KYZ")))
                self.m.run("SHL_mazar_pay_final")
                self.assertEqual("SHL_campaign_assistance_used" in self.m.flags["SHL"], parallel)
                self.assertEqual("SHL_prepared_columns" in self.m.ideas, parallel)
                self.assertEqual(self.country()["SHL_mazar_state"], 3)

    def test_objectives_accept_fighting_allies_and_reject_other_occupiers(self):
        self.country()["SHL_mazar_state"] = 5
        self.m.factions.update({"SHL": "SHL", "KYZ": "SHL"})
        self.m.run("SHL_start_mzr_war")
        self.m.control.update({"269": "KYZ", "273": "SHL", "707": "KYZ"})
        trigger = self.m.triggers["SHL_mzr_objectives_held"]
        self.assertTrue(self.m.matches(trigger, "SHL"))
        self.m.wars.discard(frozenset(("KYZ", "MZR")))
        self.assertFalse(self.m.matches(trigger, "SHL"))
        self.m.control.update({"269": "SHL", "707": "SHL"})
        decision = decision_definition("SHL_secure_cistern_corridor")
        self.assertEqual(scalar(decision, "days_remove"), "14")
        self.m.execute(block(decision, "remove_effect"), "SHL")
        self.assertEqual(self.m.ownership["269"], "SHL")
        self.assertEqual(self.country()["SHL_mzr_outcome"], 1)
        self.assertFalse(self.m.wars)

    def test_lost_objective_cancels_corridor_without_victory(self):
        self.country()["SHL_mazar_state"] = 5
        self.m.run("SHL_start_mzr_war")
        self.m.control["269"] = "SHL"
        decision = decision_definition("SHL_secure_cistern_corridor")
        self.assertTrue(self.m.matches(block(decision, "cancel_trigger"), "SHL"))
        self.m.execute(block(decision, "remove_effect"), "SHL")
        self.assertEqual(self.m.ownership["269"], "MZR")
        self.assertNotIn("SHL_mzr_outcome", self.country())

    def test_permanent_loss_of_threat_opens_peace_but_temporary_war_waits(self):
        self.m.countries["MZR"]["has_war"] = True
        self.m.run("SHL_close_lost_mazar_threat")
        self.assertNotEqual(self.country().get("SHL_mazar_state"), 3)
        for change in ("absent", "subject", "lost_one_cistern", "ally"):
            with self.subTest(change=change):
                self.setUp()
                if change == "absent":
                    self.m.countries["MZR"]["exists"] = False
                elif change == "subject":
                    self.m.countries["MZR"]["is_subject"] = True
                elif change == "lost_one_cistern":
                    self.m.ownership["269"] = "AZH"
                else:
                    self.m.factions.update({"SHL": "SHL", "MZR": "SHL"})
                self.m.run("SHL_close_lost_mazar_threat")
                self.assertEqual(self.country()["SHL_mzr_outcome"], 7)
                self.assertEqual(self.country()["SHL_mazar_state"], 3)
                self.assertNotIn("SHL_victory_over_ration", self.m.ideas)

    def test_five_assistance_packages_have_actual_distinct_payments(self):
        for course, name in enumerate(("house", "city", "directorate", "regent", "commune"), 1):
            with self.subTest(course=course):
                self.setUp()
                c = self.country()
                c.update({"SHL_political_course": course, "SHL_city_support": 35, "SHL_reserve_stock": 2, "SHL_campaign_reserve": 1, "SHL_unrest": 30})
                if course == 4:
                    c.update({"SHL_obligation_kind": 4, "SHL_obligation_liability": 180})
                self.m.focuses.add(f"SHL_{name}_war_mandate")
                self.equipment()
                self.m.manpower = 6000
                self.m.run(f"SHL_take_{name}_campaign_aid")
                balances = (dict(c), self.m.manpower, dict(self.m.equipment), list(self.m.unit_owners))
                self.m.run(f"SHL_take_{name}_campaign_aid")
                self.assertEqual(balances, (dict(c), self.m.manpower, dict(self.m.equipment), list(self.m.unit_owners)))
                if course == 1:
                    self.assertEqual((c["ADISCORD_economy_treasury"], c["ADISCORD_economy_debt"]), (1400, 500))
                    self.assertEqual(self.m.values["political_power"], 175)
                elif course == 2:
                    self.assertEqual((c["ADISCORD_economy_treasury"], c["SHL_city_support"], self.m.manpower), (850, 20, 0))
                    self.assertEqual(len(self.m.unit_owners), 2)
                elif course == 3:
                    self.assertEqual((c["SHL_reserve_stock"], c["SHL_unrest"]), (0, 38))
                    self.m.run("SHL_use_campaign_reserve")
                    self.assertEqual(self.m.idea_days["SHL_forced_columns"], 45)
                elif course == 4:
                    self.assertEqual((c["SHL_obligation_liability"], c["SHL_unrest"], self.m.manpower), (360, 45, 0))
                    self.assertEqual(len(self.m.unit_owners), 2)
                else:
                    self.assertEqual((self.m.equipment[("SHL", "infantry_equipment")], self.m.manpower), (0, 3000))
                    self.assertEqual((c["SHL_unrest"], self.m.unit_owners), (18, [("699", "SHL")]))

    def test_commune_fractional_shortage_cannot_create_a_levy(self):
        self.country()["SHL_political_course"] = 5
        self.m.focuses.add("SHL_commune_war_mandate")
        self.equipment()
        self.m.equipment[("SHL", "infantry_equipment")] = 2699.99
        self.m.run("SHL_take_commune_campaign_aid")
        self.assertFalse(self.m.unit_owners)
        self.assertEqual(self.m.manpower, 3000)

    def test_city_support_price_is_separate_from_political_eligibility(self):
        self.country().update({"SHL_political_course": 2, "SHL_city_support": 20})
        self.m.focuses.add("SHL_city_war_mandate")
        decision = decision_definition("SHL_city_campaign_aid")
        self.assertTrue(self.m.matches(block(decision, "custom_cost_trigger"), "SHL"))
        self.assertFalse(self.m.matches(block(decision, "available"), "SHL"))
        self.m.run("SHL_take_city_campaign_aid")
        self.assertFalse(self.m.unit_owners)

    def test_concession_first_pays_pledge_and_cannot_repeat(self):
        for liability, cash, remaining in ((180, 1420, 0), (600, 1150, 150)):
            with self.subTest(liability=liability):
                self.setUp()
                self.captured_cisterns(4)
                c = self.country()
                self.m.focuses.add("SHL_regency_council")
                self.m.run("SHL_begin_pledge", target="288")
                c["SHL_obligation_liability"] = liability
                self.m.run("SHL_take_cistern_concession")
                self.m.run("SHL_take_cistern_concession")
                self.assertEqual(c["ADISCORD_economy_treasury"], cash)
                self.assertEqual(c.get("SHL_obligation_liability", 0), remaining)
                self.assertEqual(self.m.ownership["269"], "MZR")
                self.assertEqual(c["SHL_mzr_outcome"], 2)

    def test_charter_requires_recipient_choice_and_rechecks_changed_course(self):
        self.captured_cisterns(2)
        self.m.run("SHL_request_cistern_charter")
        self.assertEqual(self.m.ownership["269"], "SHL")
        self.country()["SHL_political_course"] = 3
        self.m.run("SHL_accept_cistern_charter", scope="MZR")
        self.assertEqual(self.m.ownership["269"], "SHL")
        self.assertNotIn("MZR", self.m.factions)
        self.country()["SHL_political_course"] = 2
        self.m.run("SHL_request_cistern_charter")
        self.m.run("SHL_accept_cistern_charter", scope="MZR")
        self.assertEqual(self.m.ownership["269"], "MZR")
        self.assertEqual(self.m.factions["MZR"], "SHL")
        self.assertFalse(self.m.countries["MZR"]["is_subject"])

    def test_five_peace_projects_are_paid_once_with_distinct_results(self):
        for course in range(1, 6):
            with self.subTest(course=course):
                self.setUp()
                c = self.ready(course)
                self.equipment()
                self.m.run("SHL_begin_southern_programme", target="287")
                self.m.run("SHL_begin_southern_programme", target="288")
                self.assertEqual(c["SHL_south_site"], 287)
                self.assertEqual(c["ADISCORD_economy_treasury"], 800)
                self.m.run("SHL_finish_southern_programme")
                self.m.run("SHL_finish_southern_programme")
                self.assertEqual(c["SHL_southern_programme"], course)
                self.assertNotIn("SHL_south_deposit", c)
                self.assertEqual(c["ADISCORD_economy_treasury"], 800)
                if course == 1:
                    self.assertEqual(self.m.state_buildings[("287", "industrial_complex")], 1)
                elif course == 2:
                    self.assertIn(("287", "SHL"), self.m.cores)
                    self.assertEqual(self.m.state_buildings[("287", "infrastructure")], 1)
                elif course == 3:
                    self.assertEqual(self.m.state_buildings[("287", "arms_factory")], 1)
                elif course == 4:
                    self.assertIn("SHL_restored_house_guard", self.m.ideas)
                    self.assertEqual(self.m.variables["287"]["SHL_furnace_training"], 2)
                else:
                    self.assertEqual(self.m.unit_owners, [("287", "SHL")])
                    self.assertEqual(self.m.manpower, 0)
                    self.assertEqual(self.m.equipment[("SHL", "infantry_equipment")], 0)

    def test_capped_peaceful_frontier_still_has_paid_material_results(self):
        for course in (1, 2, 3, 5):
            with self.subTest(course=course):
                self.setUp()
                self.ready(course)
                self.equipment()
                self.m.free_slots = False
                self.m.infrastructure = 5
                self.m.run("SHL_begin_southern_programme", target="707")
                self.m.run("SHL_finish_southern_programme")
                self.assertEqual(self.country()["SHL_southern_programme"], course)
                self.assertEqual(self.m.infrastructure, 5)
                if course == 1:
                    self.assertEqual(self.m.equipment[("SHL", "infantry_equipment")], 5400)
                elif course == 2:
                    self.assertEqual(self.m.manpower, 5000)
                elif course == 3:
                    self.assertEqual(self.m.equipment[("SHL", "ADISCORD_squad_weapons_equipment_0")], 48)
                else:
                    self.assertEqual(self.m.unit_owners, [("707", "SHL")])

    def test_allied_project_delivers_to_owner_without_claiming_foreign_land(self):
        for course in (2, 5):
            with self.subTest(course=course):
                self.setUp()
                self.captured_cisterns(course)
                self.m.run("SHL_request_cistern_charter")
                self.m.run("SHL_accept_cistern_charter", scope="MZR")
                self.equipment()
                self.m.run("SHL_begin_southern_programme", target="269")
                self.m.run("SHL_finish_southern_programme")
                self.assertEqual(self.m.ownership["269"], "MZR")
                self.assertNotIn(("269", "SHL"), self.m.cores)
                if course == 5:
                    self.assertEqual(self.m.unit_owners, [("269", "MZR")])
                    self.assertEqual(self.m.manpower, 0)

    def test_project_cancellation_preserves_exact_escrow_on_all_terminal_paths(self):
        for reason in ("war", "course", "occupation", "alliance"):
            with self.subTest(reason=reason):
                self.setUp()
                self.ready(5, 3)
                self.m.factions.update({"SHL": "SHL", "MZR": "SHL"})
                self.equipment()
                self.m.run("SHL_begin_southern_programme", target="269")
                if reason == "war":
                    self.m.wars.add(frozenset(("SHL", "GLP")))
                elif reason == "course":
                    self.country()["SHL_political_course"] = 3
                elif reason == "occupation":
                    self.m.control["269"] = "AZH"
                else:
                    del self.m.factions["MZR"]
                self.m.run("SHL_finish_southern_programme")
                self.m.run("SHL_cancel_southern_programme")
                self.assertEqual(self.country()["ADISCORD_economy_treasury"], 1000)
                self.assertEqual(self.m.equipment[("SHL", "infantry_equipment")], 2700)
                self.assertEqual(self.m.manpower, 3000)
                self.assertFalse(self.m.unit_owners)

    def test_wrong_target_callback_cannot_settle_another_project(self):
        self.ready(1)
        self.m.run("SHL_begin_southern_programme", target="287")
        decision = decision_definition("SHL_reconstruct_south")
        for callback in ("remove_effect", "cancel_effect"):
            self.m.execute(block(decision, callback), "SHL", target="288")
        self.assertEqual(self.country()["SHL_south_deposit"], 200)
        self.m.execute(block(decision, "remove_effect"), "SHL", target="287")
        self.assertEqual(self.country()["SHL_southern_programme"], 1)

    def test_regent_reform_keeps_liability_and_requires_real_postwar_work(self):
        c = self.ready(4)
        self.m.focuses.add("SHL_regency_council")
        self.m.run("SHL_begin_pledge", target="288")
        self.m.variables["287"]["SHL_furnace_owner"] = 1
        self.m.run("SHL_refresh_furnaces")
        votes = c["SHL_house_votes"]
        self.m.run("SHL_begin_southern_programme", target="287")
        self.m.run("SHL_finish_southern_programme")
        self.assertEqual(c["SHL_house_votes"], votes + 1)
        self.assertEqual(c["SHL_obligation_liability"], 180)
        self.assertEqual(self.m.variables["287"]["SHL_furnace_wear"], 0)
        available = block(focus_definition("SHL_southern_horizon"), "available")
        self.assertTrue(self.m.matches(available, "SHL"))
        del c["SHL_southern_programme"]
        self.assertFalse(self.m.matches(available, "SHL"))

    def test_unanswered_charter_closes_offer_without_transferring_land(self):
        self.captured_cisterns(2)
        self.m.run("SHL_request_cistern_charter")
        events = parse_clausewitz((ROOT / "events/ADISCORD_SHL_events.txt").read_text(encoding="utf-8"))
        event = next(e.value for e in events if e.key == "country_event" and scalar(e.value, "id") == "ADISCORD_SHL.112")
        default = next(e.value for e in event if e.key == "option")
        self.m.execute(block(default, "hidden_effect"), "MZR")
        self.assertEqual(self.m.ownership["269"], "SHL")
        self.assertNotIn("SHL_cistern_charter_pending", self.m.flags["SHL"])
        self.assertNotIn("MZR", self.m.factions)

    def test_campaign_localisation_values_parse_and_story_pages_stay_bounded(self):
        for language in ("russian", "english"):
            path = ROOT / f"localisation/{language}/ADISCORD_SHL_l_{language}.yml"
            self.assertTrue(path.read_bytes().startswith(b"\xef\xbb\xbf"))
            values = {}
            for line in path.read_text(encoding="utf-8-sig").splitlines()[1:]:
                if not line.strip() or line.lstrip().startswith("#"):
                    continue
                match = re.fullmatch(r' ([\w.]+):(?:\d+)? "((?:[^"\\]|\\.)*)"', line)
                self.assertIsNotNone(match, line)
                self.assertNotIn(match[1], values)
                values[match[1]] = match[2].replace("\\n", "\n")
            longest = max((text for key, text in values.items() if key.startswith("SHL_epilogue_")), key=lambda text: len(text.encode("utf-8")))
            for identifier in range(110, 116):
                text = values[f"ADISCORD_SHL.{identifier}.d"].replace("[SHLGetSouthernEpilogue]", longest)
                self.assertLessEqual(len(text), 3000)
                self.assertLessEqual(len(text.encode("utf-8")), 5500)
                self.assertNotIn("§Y", text)
            for suffix in ("pp25", "city_aid", "directorate_aid", "regent_aid", "commune_aid", "south"):
                for variant in ("", "_blocked", "_tooltip"):
                    self.assertIn("SHL_cost_" + suffix + variant, values)


class ShahrabadCabinetTests(unittest.TestCase):
    setUp = CrisisLayerTests.setUp
    country = CrisisLayerTests.country

    def history_ideas(self):
        history = parse_clausewitz((ROOT / "history/countries/SHL - Shahrabad League.txt").read_text(encoding="utf-8"))
        self.assertEqual(scalar(history, "capital"), "699")
        return {e.value for e in block(history, "add_ideas")}

    def event(self, identifier):
        events = parse_clausewitz((ROOT / "events/ADISCORD_SHL_events.txt").read_text(encoding="utf-8"))
        return next(e.value for e in events if e.key == "country_event" and scalar(e.value, "id") == identifier)

    def test_starting_cabinet_fills_seven_distinct_native_slots(self):
        roster = {idea for idea in self.history_ideas() if idea.startswith("minister_SHL_")}
        definitions = block(parse_clausewitz((ROOT / "common/ideas/ADISCORD_ministers_all_countries.txt").read_text(encoding="utf-8")), "ideas")
        entries = [(slot.key, entry.key, entry.value) for slot in definitions for entry in slot.value if entry.key.startswith("minister_SHL_")]
        self.assertEqual(len({identifier for _, identifier, _ in entries}), len(entries))
        self.assertEqual(len(roster), 7)
        self.assertEqual(len({slot for slot, identifier, _ in entries if identifier in roster}), 7)
        self.assertTrue(roster <= {identifier for _, identifier, _ in entries})
        for _, identifier, definition in entries:
            if identifier in roster:
                self.assertTrue(self.m.matches(block(definition, "available"), "SHL"), identifier)
        traits = block(parse_clausewitz((ROOT / "common/country_leader/ADISCORD_minister_traits.txt").read_text(encoding="utf-8")), "leader_traits")
        trait_ids = {entry.key for entry in traits}
        for _, identifier, definition in entries:
            self.assertTrue({entry.value for entry in block(definition, "traits")} <= trait_ids, identifier)
        for language in ("russian", "english"):
            localisations = "\n".join(path.read_text(encoding="utf-8-sig") for path in (ROOT / f"localisation/{language}").glob("*.yml"))
            keys = set(re.findall(r"^\s*([\w.]+):", localisations, re.M))
            for _, identifier, definition in entries:
                self.assertIn(identifier, keys)
                self.assertIn(identifier + "_desc", keys)
                self.assertTrue({entry.value for entry in block(definition, "traits")} <= keys)

    def test_ratification_replaces_only_head_and_story_fires_once_per_change(self):
        heads = {"minister_SHL_" + name for name in ("Amin_Rashad", "Mariam_Arbin", "Rauf_Darban", "Darius_Safir", "Salima_Darzi")}
        for course, head in (("house", "Amin_Rashad"), ("city", "Mariam_Arbin"), ("state", "Rauf_Darban"), ("regency", "Darius_Safir"), ("commune", "Salima_Darzi")):
            with self.subTest(course=course):
                self.setUp()
                initial = self.history_ideas()
                self.m.ideas.update(initial)
                self.m.run("SHL_commit_" + course + "_course")
                self.m.run("SHL_commit_" + course + "_course")
                self.assertEqual(self.m.ideas & heads, {"minister_SHL_" + head})
                self.assertTrue({idea for idea in initial - heads if idea.startswith("minister_SHL_")} <= self.m.ideas)
                self.assertEqual(self.m.scheduled.count("ADISCORD_SHL.123"), 1)
                self.assertIn("ADISCORD_economy_mark_dirty", self.m.calls)
        self.setUp()
        self.m.ideas.update(self.history_ideas())
        for course, head in (("city", "Mariam_Arbin"), ("regency", "Darius_Safir")):
            self.m.run("SHL_commit_" + course + "_course")
            self.assertEqual(self.m.ideas & heads, {"minister_SHL_" + head})
        self.m.run("SHL_commit_commune_course")
        self.assertEqual(self.m.ideas & heads, {"minister_SHL_Darius_Safir"})
        self.assertEqual(self.m.scheduled.count("ADISCORD_SHL.123"), 2)
        self.setUp()
        self.m.ideas.update(self.history_ideas())
        self.m.run("SHL_commit_state_course")
        self.m.run("SHL_commit_commune_course")
        self.m.run("SHL_commit_regency_course")
        self.assertEqual(self.m.ideas & heads, {"minister_SHL_Salima_Darzi"})
        self.assertEqual(self.m.scheduled.count("ADISCORD_SHL.123"), 2)

    def test_registers_check_exact_price_and_cannot_charge_after_charter(self):
        self.m.ideas.add("SHL_unregistered_quarters")
        c = self.country()
        c["SHL_city_support"] = 20
        support, pressure = c["SHL_city_support"], c["SHL_house_pressure"]
        decision = decision_definition("SHL_register_quarters")
        c["ADISCORD_economy_treasury"] = 79.99
        self.assertFalse(self.m.matches(block(decision, "custom_cost_trigger"), "SHL"))
        self.m.run("SHL_recognise_quarter_registers")
        self.assertIn("SHL_unregistered_quarters", self.m.ideas)
        self.assertEqual(c["ADISCORD_economy_treasury"], 79.99)
        c["ADISCORD_economy_treasury"] = 80
        self.assertTrue(self.m.matches(block(decision, "custom_cost_trigger"), "SHL"))
        self.m.run("SHL_recognise_quarter_registers")
        self.m.run("SHL_recognise_quarter_registers")
        self.assertEqual(c["ADISCORD_economy_treasury"], 0)
        self.assertEqual((c["SHL_city_support"], c["SHL_house_pressure"]), (support + 8, pressure + 5))
        self.assertFalse(self.m.matches(block(decision, "visible"), "SHL"))
        self.m.ideas.add("SHL_unregistered_quarters")
        c["ADISCORD_economy_treasury"] = 500
        charter = block(focus_definition("SHL_workers_charter"), "completion_reward")
        self.m.execute(charter, "SHL")
        self.assertEqual(c["ADISCORD_social_system_development_level"], 1)
        self.assertEqual(c["ADISCORD_social_system_development_progress"], 25)
        self.assertEqual(c["ADISCORD_social_system_development_monthly_growth"], 2)
        self.assertIn("ADISCORD_economy_mark_dirty", self.m.calls)
        self.m.run("SHL_recognise_quarter_registers")
        self.assertEqual(c["ADISCORD_economy_treasury"], 500)
        self.assertNotIn("SHL_unregistered_quarters", self.m.ideas)
        options = [e.value for e in self.event("ADISCORD_SHL.121") if e.key == "option"]
        self.assertFalse(self.m.matches(block(options[1], "trigger"), "SHL"))
        default = options[0]
        self.assertTrue(self.m.matches(block(default, "trigger"), "SHL"))

    def test_social_charter_preserves_existing_development_before_adding_its_reward(self):
        c = self.country()
        c.update({
            "ADISCORD_social_system_development_level": 3,
            "ADISCORD_social_system_development_progress": 53,
            "ADISCORD_social_system_development_monthly_growth": 3,
        })
        charter = block(focus_definition("SHL_workers_charter"), "completion_reward")
        self.m.execute(charter, "SHL")
        self.assertEqual(c["ADISCORD_social_system_development_level"], 3)
        self.assertEqual(c["ADISCORD_social_system_development_progress"], 78)
        self.assertEqual(c["ADISCORD_social_system_development_monthly_growth"], 5)
        self.assertIn("ADISCORD_economy_mark_dirty", self.m.calls)

    def test_initial_story_clock_does_not_need_focuses_and_open_cabinet_has_safe_exit(self):
        effects = parse_clausewitz(EFFECT_PATH.read_text(encoding="utf-8"))
        m = ScriptMachine(effects, parse_clausewitz(TRIGGER_PATH.read_text(encoding="utf-8")))
        m.run("SHL_initialize_furnaces")
        m.run("SHL_initialize_furnaces")
        self.assertEqual(m.scheduled.count("ADISCORD_SHL.120"), 1)
        self.assertEqual(m.scheduled.count("ADISCORD_SHL.121"), 1)
        self.assertEqual(m.event_days["ADISCORD_SHL.120"], 14)
        self.assertEqual(m.event_days["ADISCORD_SHL.121"], 70)
        self.country()["SHL_political_course"] = 5
        options = [entry.value for entry in self.event("ADISCORD_SHL.120") if entry.key == "option"]
        for option in options[1:]:
            self.assertFalse(self.m.matches(block(option, "trigger"), "SHL"))
        self.assertEqual(scalar(options[0], "name"), "ADISCORD_SHL.120.c")
        self.assertTrue(self.m.matches(block(options[0], "trigger"), "SHL"))

    def test_first_guard_story_requires_delivery_and_remains_unique_across_orders(self):
        for _ in range(2):
            self.m.run("SHL_begin_guard_order")
            self.m.run("SHL_finish_guard_order")
        self.assertEqual(self.m.unit_owners, [("699", "SHL"), ("699", "SHL")])
        self.assertEqual(self.m.scheduled.count("ADISCORD_SHL.122"), 1)
        self.setUp()
        self.m.run("SHL_begin_guard_order")
        self.m.control["699"] = "MZR"
        self.m.run("SHL_finish_guard_order")
        self.assertNotIn("ADISCORD_SHL.122", self.m.scheduled)
        self.assertNotIn("SHL_first_guard_reported", self.m.flags["SHL"])

    def test_new_story_localisation_is_bounded_after_all_course_expansions(self):
        for language in ("russian", "english"):
            path = ROOT / f"localisation/{language}/ADISCORD_SHL_l_{language}.yml"
            values = dict(re.findall(r'^ ([\w.]+):(?:\d+)? "((?:[^"\\]|\\.)*)"$', path.read_text(encoding="utf-8-sig"), re.M))
            variants = [value for key, value in values.items() if key.startswith("SHL_cabinet_story_")]
            self.assertEqual(len(variants), 6)
            for identifier in range(120, 124):
                for variant in variants:
                    text = values[f"ADISCORD_SHL.{identifier}.d"].replace("[SHLGetCabinetStory]", variant).replace("\\n", "\n")
                    self.assertLessEqual(len(text), 3000)
                    self.assertLessEqual(len(text.encode("utf-8")), 5500)
                    self.assertNotIn("§Y", text)
                    self.assertNotIn("•", text)

def walk_entries(items):
    for entry in items:
        yield entry
        if isinstance(entry.value, list):
            yield from walk_entries(entry.value)


class DeliveryStructureTests(unittest.TestCase):
    """Delivery ownership, course endings and aggregate previews."""

    SHARES = ("crest", "quart", "state", "front")
    COURSES = ("houses", "cities", "directorate", "regency", "commune")

    @classmethod
    def setUpClass(cls):
        tree = block(parse_clausewitz((ROOT / "focus_trees/SHL/main/focuses.txt").read_text(encoding="utf-8")), "focus_tree")
        cls.focuses = {scalar(e.value, "id"): e.value for e in tree if e.key == "focus"}
        cls.effects = {e.key: e.value for e in parse_clausewitz(EFFECT_PATH.read_text(encoding="utf-8"))}

    def test_percentage_system_has_no_runtime_consumers(self):
        for name in self.effects:
            self.assertFalse(name.startswith("SHL_fire_"), name)
        for path in (EFFECT_PATH, ROOT / "focus_trees/SHL/main/focuses.txt",
                     ROOT / "common/decisions/ADISCORD_SHL_decisions.txt",
                     ROOT / "common/dynamic_modifiers/ADISCORD_dynamic_modifiers_SHL.txt"):
            source = path.read_text(encoding="utf-8-sig")
            for token in ("SHL_share_", "SHL_fire_dynamic", "SHL_fire_cycle", "SHL_fire_give_"):
                self.assertNotIn(token, source)

    def test_each_course_final_offers_two_exclusive_delivery_endings(self):
        finals = {
            "houses": "SHL_conclave_of_ten",
            "cities": "SHL_southern_compact",
            "directorate": "SHL_iron_shahrabad",
            "regency": "SHL_hereditary_republic",
            "commune": "SHL_commune_of_fire",
        }
        ideas = (ROOT / "common/ideas/ADISCORD_southern_desert_ideas.txt").read_text(encoding="utf-8")
        for course, final in finals.items():
            for side, other in (("a", "b"), ("b", "a")):
                name = f"SHL_{course}_prog_ending_{side}"
                ending = self.focuses[name]
                self.assertEqual(scalar(block(ending, "prerequisite"), "focus"), final, name)
                self.assertEqual(scalar(block(ending, "mutually_exclusive"), "focus"), f"SHL_{course}_prog_ending_{other}")
                reward = repr(block(ending, "completion_reward"))
                self.assertIn(f"SHL_delivery_{course}_{side}_tt", reward)
                self.assertIn("SHL_refresh_furnaces", reward)
                self.assertIn("SHL_prog_ending", reward)
                self.assertIn(f"SHL_pow_{course}_prog_ending_{side}_idea = {{", ideas)
        tree = (ROOT / "focus_trees/SHL/main/focuses.txt").read_text(encoding="utf-8")
        self.assertNotIn("SHL_programme", tree)
        self.assertNotIn("SHL_fire_align", tree)

    def test_every_conclave_preview_idea_is_defined_once_and_used(self):
        tree = (ROOT / "focus_trees/SHL/main/focuses.txt").read_text(encoding="utf-8")
        ideas = (ROOT / "common/ideas/ADISCORD_southern_desert_ideas.txt").read_text(encoding="utf-8")
        used = set(re.findall(r"add_idea = (SHL_pow_\w+_idea)", tree))
        defined = re.findall(r"(?m)^\t\t(SHL_pow_\w+_idea) = \{", ideas)
        self.assertEqual(len(defined), len(set(defined)))
        self.assertEqual(used, set(defined))

    def test_deliveries_reuse_production_and_no_new_periodic_hook(self):
        self.assertIn("SHL_deliver_site_heat", repr(self.effects["SHL_produce_site"]))
        self.assertIn("SHL_deliver_tenth_heat", repr(self.effects["SHL_produce_period"]))
        hooks = "".join(path.read_text(encoding="utf-8-sig") for path in (ROOT / "common/on_actions").glob("*.txt"))
        self.assertNotIn("on_monthly_SHL", hooks)
        self.assertNotIn("SHL_fire_initialize", hooks)


class EarlyCampaignTests(unittest.TestCase):
    def setUp(self):
        CrisisLayerTests.setUp(self)
        self.country()["SHL_city_support"] = 20

    country = CrisisLayerTests.country
    event = ShahrabadCabinetTests.event

    def test_unanswered_starting_problems_reach_crises_in_seven_and_eight_cycles(self):
        self.m.ideas.add("SHL_unregistered_quarters")
        reached = {}
        for cycle in range(1, 9):
            self.country()["SHL_cycle_number"] = cycle
            self.m.run("SHL_update_tensions")
            for kind, predicate in (("strike", "SHL_strike_ready"), ("crests", "SHL_conspiracy_ready")):
                if kind not in reached and self.m.matches(self.m.triggers[predicate], "SHL"):
                    reached[kind] = cycle * 28
        self.assertEqual(reached, {"strike": 196, "crests": 224})

    def test_pressure_sources_end_when_their_actual_problem_is_resolved(self):
        self.m.ideas.add("SHL_unregistered_quarters")
        self.m.run("SHL_recognise_quarter_registers")
        self.country()["SHL_project_stage"] = 4
        before = (self.country()["SHL_unrest"], self.country()["SHL_house_pressure"])
        self.m.run("SHL_update_tensions")
        self.assertEqual((self.country()["SHL_unrest"], self.country()["SHL_house_pressure"]), before)
        self.country().update({"SHL_project_stage": 0, "SHL_political_course": 5})
        self.m.run("SHL_update_tensions")
        self.assertEqual(self.country()["SHL_house_pressure"], before[1])

    def test_careful_shift_reduces_unrest_despite_unregistered_quarters(self):
        self.m.ideas.add("SHL_unregistered_quarters")
        self.country()["SHL_shift_policy"] = 2
        self.m.run("SHL_update_tensions")
        self.assertEqual(self.country()["SHL_unrest"], 24)

    def test_provisional_course_moves_tensions_before_ownership_ratification(self):
        for focus, unrest, pressure in (
            ("SHL_new_house", 25, 23),
            ("SHL_open_conclave", 23, 28),
            ("SHL_nur_directorate", 25, 28),
        ):
            with self.subTest(focus=focus):
                self.setUp()
                self.m.focuses.add(focus)
                self.m.run("SHL_update_tensions")
                self.assertEqual((self.country()["SHL_unrest"], self.country()["SHL_house_pressure"]), (unrest, pressure))
                self.assertEqual(self.country().get("SHL_political_course", 0), 0)
                self.assertEqual(self.m.variables["287"]["SHL_furnace_owner"], 0)

    def test_ratification_applies_one_course_drift_and_preserves_the_selected_platform(self):
        for focus, effect, expected in (
            ("SHL_new_house", "SHL_commit_house_course", 11),
            ("SHL_open_conclave", "SHL_commit_city_course", 46),
            ("SHL_nur_directorate", "SHL_commit_state_course", 51),
        ):
            with self.subTest(focus=focus):
                self.setUp()
                self.m.focuses.add(focus)
                self.m.run("SHL_update_tensions")
                self.m.run(effect)
                self.m.run("SHL_update_tensions")
                self.assertEqual(self.country()["SHL_house_pressure"], expected)

    def test_crisis_choices_are_available_immediately_and_settle_paid_orders_once(self):
        for kind, crisis, decision, event_id, course in (
            (3, "SHL_strike_active", "SHL_back_shift_councils", "ADISCORD_SHL.20", 5),
            (2, "SHL_conspiracy_active", "SHL_back_crests", "ADISCORD_SHL.30", 4),
        ):
            with self.subTest(course=course):
                self.setUp()
                self.c = self.country()
                ObligationAccountingTests.begin(self, kind)
                self.m.run("SHL_produce_period")
                paid_remainder = self.country()["SHL_obligation_deposit"]
                before = self.country()["ADISCORD_economy_treasury"]
                weapons = dict(self.m.equipment)
                self.m.flags["SHL"].add(crisis)
                entry = decision_definition(decision)
                self.assertTrue(self.m.matches(block(entry, "visible"), "SHL"))
                self.assertTrue(self.m.matches(block(entry, "available"), "SHL"))
                option = next(e.value for e in self.event(event_id) if e.key == "option" and scalar(e.value, "name") == decision)
                self.assertTrue(self.m.matches(block(option, "trigger"), "SHL"))
                self.m.execute(block(entry, "complete_effect"), "SHL")
                self.m.execute(block(entry, "complete_effect"), "SHL")
                self.assertEqual(self.country()["SHL_political_course"], course)
                self.assertNotIn(crisis, self.m.flags["SHL"])
                self.assertNotIn("SHL_obligation_kind", self.country())
                self.assertEqual(self.country()["ADISCORD_economy_treasury"], before + paid_remainder)
                self.assertEqual(dict(self.m.equipment), weapons)
                self.assertFalse(self.m.matches(block(entry, "available"), "SHL"))

    def test_each_production_policy_pays_the_forecast_for_nine_and_tenth_furnaces(self):
        for policy, revenue, wear, packets in ((0, 60, 6, 1), (1, 90, 10, 2), (2, 25, 3, 1)):
            with self.subTest(policy=policy):
                self.setUp()
                c = self.country()
                c.update({"SHL_shift_policy": policy, "SHL_selected_furnace": 1,
                          "SHL_project_stage": 4, "SHL_tenth_running": 1,
                          "SHL_tenth_stock": 3, "SHL_tenth_wear": 20})
                self.m.run("SHL_refresh_furnaces")
                self.assertEqual(c["SHL_selected_period_income"], revenue)
                before = c["ADISCORD_economy_treasury"]
                self.m.run("SHL_produce_period")
                self.assertEqual(c["ADISCORD_economy_treasury"] - before, revenue * 10)
                self.assertEqual(c["SHL_tenth_stock"], 3 - packets)
                self.assertEqual(c["SHL_tenth_wear"], 20 + wear)
                self.assertEqual(self.m.variables["287"]["SHL_furnace_stock"], 3 - packets)
                self.assertEqual(self.m.variables["287"]["SHL_furnace_wear"], 20 + wear)

    def test_open_crisis_answers_cannot_reopen_or_charge_after_a_regime_decision(self):
        for event_id, crisis, decision in (
            ("ADISCORD_SHL.20", "SHL_strike_active", "SHL_back_shift_councils"),
            ("ADISCORD_SHL.21", "SHL_strike_active", "SHL_back_shift_councils"),
            ("ADISCORD_SHL.30", "SHL_conspiracy_active", "SHL_back_crests"),
            ("ADISCORD_SHL.31", "SHL_conspiracy_active", "SHL_back_crests"),
        ):
            options = [e.value for e in self.event(event_id) if e.key == "option"]
            for option in options:
                with self.subTest(event=event_id, option=scalar(option, "name")):
                    self.setUp()
                    self.country()["SHL_political_course"] = 3
                    self.m.focuses.add("SHL_railway_guard")
                    self.m.flags["SHL"].add(crisis)
                    was_available = self.m.matches(block(option, "trigger"), "SHL")
                    self.m.execute(block(decision_definition(decision), "complete_effect"), "SHL")
                    fields = ("variables", "flags", "missions", "ideas", "idea_days", "values",
                              "stability", "equipment", "scheduled")
                    before = deepcopy({field: getattr(self.m, field) for field in fields})
                    # An already-open window or its timeout may still submit an old answer.
                    effects = [e for e in option if e.key not in ("name", "trigger", "ai_chance")]
                    self.m.execute(effects, "SHL")
                    self.assertEqual({field: getattr(self.m, field) for field in fields}, before)
                    if was_available:
                        self.assertFalse(self.m.matches(block(option, "trigger"), "SHL"))

    def test_resolved_crisis_windows_have_one_available_close_only_answer(self):
        for event_id, crisis in (
            ("ADISCORD_SHL.20", "SHL_strike_active"),
            ("ADISCORD_SHL.21", "SHL_strike_active"),
            ("ADISCORD_SHL.30", "SHL_conspiracy_active"),
            ("ADISCORD_SHL.31", "SHL_conspiracy_active"),
        ):
            with self.subTest(event=event_id):
                self.setUp()
                self.m.flags["SHL"].discard(crisis)
                options = [e.value for e in self.event(event_id) if e.key == "option"]
                available = [option for option in options if self.m.matches(block(option, "trigger"), "SHL")]
                self.assertEqual(len(available), 1)
                self.assertEqual(scalar(available[0], "name"), "SHL_crisis_already_resolved")
                self.assertFalse([e for e in available[0] if e.key not in ("name", "trigger", "ai_chance")])

    def test_direct_routes_ratify_on_day_252_without_a_finished_tenth_furnace(self):
        for first, second, ratify in (
            ("SHL_new_house", "SHL_house_compromise", "SHL_admit_tenth_house"),
            ("SHL_open_conclave", "SHL_city_charters", "SHL_rights_without_fire"),
            ("SHL_nur_directorate", "SHL_common_dispatch", "SHL_state_furnaces"),
        ):
            with self.subTest(course=first):
                self.setUp()
                elapsed = 0
                engineer_finish = 0
                route = ("SHL_law_of_continuous_fire", "SHL_census_of_nine",
                         "SHL_reserve_for_next_shift", "SHL_conclave_rules", first,
                         "SHL_common_industrial_account", "SHL_engineer_society", second,
                         "SHL_right_to_land", "SHL_common_fund", "SHL_workers_charter", ratify)
                for identifier in route:
                    if identifier == "SHL_right_to_land":
                        elapsed = max(elapsed, engineer_finish)
                        self.m.run("SHL_finish_project")
                    focus = focus_definition(identifier)
                    for prerequisite in (e.value for e in focus if e.key == "prerequisite"):
                        self.assertTrue(any(e.value in self.m.focuses for e in prerequisite), identifier)
                    self.assertTrue(self.m.matches(block(focus, "available"), "SHL"), identifier)
                    elapsed += int(scalar(focus, "cost")) * 7
                    self.m.focuses.add(identifier)
                    if identifier == first:
                        self.assertEqual(elapsed, 84)
                    elif identifier == "SHL_engineer_society":
                        self.m.run("SHL_begin_engineers")
                        engineer_finish = elapsed + int(scalar(decision_definition("SHL_project_engineers"), "days_remove"))
                    elif identifier == "SHL_workers_charter":
                        self.m.execute(block(block(focus, "completion_reward"), "hidden_effect"), "SHL")
                self.assertEqual(elapsed, 252)
                self.assertEqual(self.country()["SHL_project_stage"], 1)
                reward = block(block(focus_definition(ratify), "completion_reward"), "hidden_effect")
                self.m.execute(reward, "SHL")
                settled = dict(self.country())
                self.m.execute(reward, "SHL")
                self.assertEqual(dict(self.country()), settled)




class DeliveryAccountingTests(unittest.TestCase):
    def setUp(self):
        ObligationAccountingTests.setUp(self)
        self.c.update({"SHL_unrest": 50, "SHL_house_pressure": 50})

    def assign(self, site, recipient):
        self.c.update({"SHL_selected_furnace": site, "SHL_assignment": recipient})
        self.m.run("SHL_assign_selected_delivery")

    def test_assignment_persists_without_paying_on_click(self):
        before = self.c["ADISCORD_economy_treasury"]
        self.assign(1, 1)
        self.assign(1, 1)
        self.assertEqual(self.c["ADISCORD_economy_treasury"], before)
        self.assertEqual(self.m.equipment[("SHL", "infantry_equipment")], 0)
        self.m.run("SHL_produce_period")
        self.assertEqual(self.m.equipment[("SHL", "infantry_equipment")], 300)
        self.assertEqual(self.c["ADISCORD_economy_treasury"], before + 480)
        self.m.run("SHL_produce_period")
        self.assertEqual(self.m.equipment[("SHL", "infantry_equipment")], 600)

    def test_every_course_shift_and_recipient_has_exact_outputs(self):
        for course in range(6):
            for shift in range(3):
                for recipient in range(4):
                    with self.subTest(course=course, shift=shift, recipient=recipient):
                        self.setUp()
                        self.c.update({"SHL_political_course": course, "SHL_shift_policy": shift})
                        self.assign(1, recipient)
                        self.m.run("SHL_refresh_delivery_terms")
                        before = self.c["ADISCORD_economy_treasury"]
                        self.m.run("SHL_produce_site", scope="287")
                        effective = 0 if course == 5 and recipient == 3 else recipient
                        self.assertEqual(self.c["ADISCORD_economy_treasury"] - before,
                                         (60, 90, 25)[shift] if effective == 0 else 0)
                        self.assertEqual(self.m.equipment[("SHL", "infantry_equipment")],
                                         (300, 600, 150)[shift] if effective == 1 else 0)
                        quarters = (6, 9, 3) if course in (2, 5) else (4, 6, 2)
                        crests = (6, 9, 3) if course in (1, 4) else (4, 6, 2)
                        self.assertEqual(self.c["SHL_unrest"], 50 - (quarters[shift] if effective == 2 else 0))
                        self.assertEqual(self.c["SHL_house_pressure"], 50 - (crests[shift] if effective == 3 else 0))
                        self.assertEqual(self.m.variables["287"]["SHL_furnace_stock"], 2 - (2 if shift == 1 else 1))

    def test_stopped_occupied_lost_and_unsupplied_sites_deliver_nothing(self):
        for failure in ("stopped", "occupied", "lost", "stock"):
            for recipient in (1, 2, 3):
                with self.subTest(failure=failure, recipient=recipient):
                    self.setUp()
                    self.assign(1, recipient)
                    if failure == "stopped":
                        self.m.variables["287"]["SHL_furnace_running"] = 0
                    elif failure == "occupied":
                        self.m.control["287"] = "MZR"
                    elif failure == "lost":
                        self.m.ownership["287"] = "MZR"
                    else:
                        self.m.variables["287"]["SHL_furnace_stock"] = 0
                    self.m.run("SHL_produce_period")
                    self.m.run("SHL_refresh_furnaces")
                    self.assertEqual(self.m.equipment[("SHL", "infantry_equipment")], 0)
                    self.assertEqual(self.c["SHL_unrest"], 50)
                    self.assertEqual(self.c["SHL_house_pressure"], 50)
                    self.assertEqual(self.c["SHL_crest_support"], 0)

    def test_tenth_assignment_is_independent_of_eighth_furnace(self):
        self.c.update({"SHL_project_stage": 4, "SHL_tenth_running": 1, "SHL_tenth_stock": 2})
        self.assign(8, 2)
        self.assign(10, 1)
        self.m.run("SHL_produce_period")
        self.assertEqual(self.m.variables["294"]["SHL_furnace_recipient"], 2)
        self.assertEqual(self.c["SHL_tenth_recipient"], 1)
        self.assertEqual(self.m.equipment[("SHL", "infantry_equipment")], 300)
        self.assertEqual(self.c["SHL_unrest"], 46)
        self.assertEqual(self.c["SHL_last_cycle_income"], 480)

    def test_support_expires_without_production_and_cannot_restore_ownership(self):
        self.c["SHL_shift_policy"] = 1
        for site in range(1, 6):
            self.assign(site, 3)
        self.m.run("SHL_produce_period")
        self.m.run("SHL_refresh_furnaces")
        self.assertEqual(self.c["SHL_crest_support"], 5)
        self.assertTrue(self.m.matches(self.m.triggers["SHL_has_delivery_majority"], "SHL"))
        self.m.variables["287"]["SHL_furnace_owner"] = 2
        self.m.run("SHL_refresh_furnaces")
        self.assertEqual(self.c["SHL_crest_support"], 4)
        self.assertEqual(self.c["SHL_house_votes"], 8)
        self.assertFalse(self.m.matches(self.m.triggers["SHL_has_delivery_majority"], "SHL"))
        self.m.run("SHL_produce_period")
        self.m.run("SHL_refresh_furnaces")
        self.assertEqual(self.c["SHL_crest_support"], 0)
        self.assertEqual(self.m.variables["287"]["SHL_furnace_owner"], 2)

    def test_order_locks_assignment_and_has_no_duplicate_ordinary_delivery(self):
        ObligationAccountingTests.begin(self, 3)
        self.assign(1, 2)
        self.assertEqual(self.m.variables["287"]["SHL_furnace_recipient"], 1)
        self.c["SHL_shift_policy"] = 1
        self.m.run("SHL_produce_period")
        self.assertEqual(self.m.equipment[("SHL", "infantry_equipment")], 1500)
        self.assertEqual(self.c["SHL_unrest"], 50)
        self.assertNotIn("SHL_obligation_kind", self.c)
        self.assign(1, 2)
        self.assertEqual(self.m.variables["287"]["SHL_furnace_recipient"], 2)

    def test_contract_quote_does_not_change_when_final_is_completed(self):
        ObligationAccountingTests.begin(self, 3)
        self.m.run("SHL_produce_period")
        self.c["SHL_prog_ending"] = 32
        self.c["SHL_political_course"] = 3
        self.m.run("SHL_refresh_delivery_terms")
        self.assertEqual(self.c["SHL_arsenal_price"], 60)
        self.assertEqual(self.c["SHL_obligation_batch_price"], 45)
        before = self.c["ADISCORD_economy_treasury"]
        self.m.run("SHL_cancel_obligation")
        self.assertEqual(self.c["ADISCORD_economy_treasury"], before + 45)

    def test_each_final_changes_terms_without_reassigning_furnaces(self):
        expected = {11: (120, 120, 180, 4), 12: (120, 120, 180, 4),
                    21: (60, 120, 180, 6), 22: (90, 90, 180, 6),
                    31: (90, 90, 180, 4), 32: (120, 60, 180, 4),
                    41: (120, 90, 180, 4), 42: (120, 120, 165, 4),
                    51: (120, 120, 180, 8), 52: (120, 120, 180, 6)}
        courses = ("houses", "cities", "directorate", "regency", "commune")
        for ending, values in expected.items():
            with self.subTest(ending=ending):
                self.setUp()
                self.assign(1, 1)
                self.c["SHL_political_course"] = ending // 10
                focus = f"SHL_{courses[ending // 10 - 1]}_prog_ending_{'a' if ending % 10 == 1 else 'b'}"
                self.m.execute([entry for entry in block(focus_definition(focus), "completion_reward") if entry.key == "hidden_effect"], "SHL")
                self.assertEqual(tuple(self.c[name] for name in ("SHL_civic_price", "SHL_arsenal_price", "SHL_pledge_price", "SHL_delivery_quarters")), values)
                self.assertEqual(self.m.variables["287"]["SHL_furnace_recipient"], 1)
        for ending, access in ((12, "civic"), (22, "arsenal"), (31, "civic"), (41, "arsenal")):
            self.c["SHL_prog_ending"] = ending
            self.c["SHL_political_course"] = ending // 10
            self.assertTrue(self.m.matches(self.m.triggers[f"SHL_{access}_access"], "SHL"))

    def test_export_and_relief_finals_fix_duration_at_order_start(self):
        self.c["SHL_prog_ending"] = 11
        ObligationAccountingTests.begin(self, 1)
        self.assertEqual(self.c["SHL_obligation_deadline"], 4)
        self.c["SHL_prog_ending"] = 12
        self.assertEqual(self.c["SHL_obligation_deadline"], 4)
        self.m.run("SHL_cancel_obligation")
        self.c["SHL_prog_ending"] = 52
        ObligationAccountingTests.relief(self)
        self.m.run("SHL_produce_period")
        self.assertNotIn("SHL_obligation_kind", self.c)
        self.assertEqual(self.m.variables["288"]["SHL_furnace_wear"], 26)

    def test_preview_matches_deliveries_and_does_not_mutate_production(self):
        for shift in range(3):
            with self.subTest(shift=shift):
                self.setUp()
                self.c.update({"SHL_shift_policy": shift, "SHL_regular_supply": 1,
                               "ADISCORD_economy_treasury": 75})
                for state in range(287, 296):
                    self.m.variables[str(state)]["SHL_furnace_stock"] = 0
                for site, recipient in ((1, 1), (3, 2), (4, 3)):
                    self.assign(site, recipient)
                before = deepcopy(self.m.variables)
                self.m.run("SHL_refresh_furnaces")
                forecast = tuple(self.c[name] for name in ("SHL_preview_income", "SHL_preview_rifles", "SHL_preview_quarters", "SHL_preview_crests"))
                for state in range(287, 296):
                    self.assertEqual(self.m.variables[str(state)], before[str(state)])
                self.assertEqual(self.c["ADISCORD_economy_treasury"], 75)
                self.m.run("SHL_produce_period")
                actual = (self.c["ADISCORD_economy_treasury"] - 75,
                          self.m.equipment[("SHL", "infantry_equipment")],
                          50 - self.c["SHL_unrest"], 50 - self.c["SHL_house_pressure"])
                self.assertEqual(actual, forecast)
                self.assertEqual(self.c["SHL_selected_period_income"], self.c["SHL_selected_delivery_cash"])

    def test_save_load_preserves_assignments_and_discounted_receipt(self):
        self.assign(2, 2)
        ObligationAccountingTests.begin(self, 3)
        self.m.run("SHL_produce_period")
        restored = deepcopy(self.m)
        self.m.run("SHL_produce_period")
        restored.run("SHL_produce_period")
        self.assertEqual(dict(self.m.equipment), dict(restored.equipment))
        self.assertEqual(dict(self.m.variables), dict(restored.variables))

    def test_ai_reserves_supply_and_repairs_before_diverting_heat(self):
        self.m.ai = True
        self.m.countries["SHL"] = {"has_war": True}
        self.c["ADISCORD_economy_treasury"] = 100
        self.m.run("SHL_ai_allocate_deliveries")
        self.assertTrue(all(self.m.variables[str(state)]["SHL_furnace_recipient"] == 0 for state in range(287, 296)))
        self.c["ADISCORD_economy_treasury"] = 1000
        self.m.run("SHL_ai_allocate_deliveries")
        self.assertEqual([self.m.variables[str(state)]["SHL_furnace_recipient"] for state in range(287, 291)], [2, 3, 1, 0])

    def test_economic_examples_include_real_supply_but_not_hypothetical_repairs(self):
        for arsenal, quarters, expected in ((0, 0, 315), (1, 1, 195), (2, 1, 135)):
            with self.subTest(arsenal=arsenal, quarters=quarters):
                self.setUp()
                self.c["SHL_regular_supply"] = 1
                for state in range(287, 296):
                    self.m.variables[str(state)]["SHL_furnace_stock"] = 0
                for index in range(1, arsenal + 1):
                    self.assign(index, 1)
                if quarters:
                    self.assign(9, 2)
                self.m.run("SHL_produce_period")
                self.assertEqual(self.c["ADISCORD_economy_treasury"] - 1000, expected)
                self.assertEqual(self.m.equipment[("SHL", "infantry_equipment")], arsenal * 300)

    def test_discount_affordability_and_refund_use_the_same_quote(self):
        for kind, ending, course, price in (("civic", 12, 1, 120), ("civic", 0, 2, 90),
                                            ("civic", 21, 2, 60), ("arsenal", 0, 3, 90),
                                            ("arsenal", 32, 3, 60)):
            for balance, allowed in ((price - 0.01, False), (price, True)):
                with self.subTest(kind=kind, ending=ending, balance=balance):
                    self.setUp()
                    self.c.update({"SHL_political_course": course, "SHL_prog_ending": ending,
                                   "ADISCORD_economy_treasury": balance})
                    self.m.run("SHL_refresh_furnaces")
                    decision = decision_definition("SHL_civic_order" if kind == "civic" else "SHL_war_orders")
                    self.assertEqual(self.m.matches(block(decision, "custom_cost_trigger"), "SHL"), allowed)
                    self.m.run(f"SHL_begin_{kind}_order", target="287")
                    self.assertEqual("SHL_obligation_kind" in self.c, allowed)
                    self.assertAlmostEqual(self.c["ADISCORD_economy_treasury"], balance - (price if allowed else 0))
                    self.m.run("SHL_cancel_obligation")
                    self.assertAlmostEqual(self.c["ADISCORD_economy_treasury"], balance)

    def test_compensation_and_commune_do_not_restore_house_votes(self):
        self.c["SHL_political_course"] = 2
        self.m.variables["287"]["SHL_furnace_owner"] = 1
        self.assign(1, 3)
        self.m.run("SHL_produce_period")
        self.m.run("SHL_refresh_furnaces")
        self.assertEqual(self.c["SHL_house_pressure"], 46)
        self.assertEqual(self.c["SHL_crest_support"], 0)
        self.assertEqual(self.m.variables["287"]["SHL_furnace_owner"], 1)
        self.m.run("SHL_commit_commune_course")
        self.assertEqual(self.m.variables["287"]["SHL_furnace_recipient"], 2)
        self.assign(1, 3)
        self.assertEqual(self.m.variables["287"]["SHL_furnace_recipient"], 2)

    def test_conclave_guarantees_charge_only_without_actual_majority(self):
        events = parse_clausewitz((ROOT / "events/ADISCORD_SHL_events.txt").read_text(encoding="utf-8"))
        event = next(e.value for e in events if isinstance(e.value, list) and scalar(e.value, "id") == "ADISCORD_SHL.30")
        option = next(e.value for e in event if e.key == "option" and scalar(e.value, "name") == "ADISCORD_SHL.30.a")
        for supported in (False, True):
            with self.subTest(supported=supported):
                self.setUp()
                if supported:
                    for site in range(1, 6):
                        self.assign(site, 3)
                self.m.run("SHL_produce_period")
                self.m.run("SHL_refresh_furnaces")
                self.m.flags["SHL"].add("SHL_conspiracy_active")
                before = self.m.values["political_power"]
                self.assertTrue(self.m.matches(block(option, "trigger"), "SHL"))
                self.m.execute([e for e in option if e.key == "if"], "SHL")
                self.assertEqual(self.m.values["political_power"], before - (0 if supported else 40))
                self.assertNotIn("SHL_conspiracy_active", self.m.flags["SHL"])

    begin = ObligationAccountingTests.begin


if __name__ == "__main__":
    unittest.main()
