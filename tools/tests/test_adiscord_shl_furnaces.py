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
# Regional countries that SHL scripts address directly (consolidation targets,
# satellites and the northern leader).
REGIONAL = NEIGHBOURS + ("RHM", "SDR", "KDR", "NAM", "EFL", "AZH", "WEF")
NEIGHBOUR_STATES = {
    "KYZ": (280, 284, 285, 286),
    "GLP": (297, 298, 299, 708),
    "MZR": (269, 273, 275),
}
EFFECT_PATH = ROOT / "common/scripted_effects/ADISCORD_SHL_scripted_effects.txt"
TRIGGER_PATH = ROOT / "common/scripted_triggers/ADISCORD_SHL_scripted_triggers.txt"
SOUTH_TRIGGER_PATH = ROOT / "common/scripted_triggers/ADISCORD_south_final_war_triggers.txt"
BOP_PATH = ROOT / "common/bop/SHL.txt"
BALANCE = "SHL_conclave_balance"


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


FOCUS_TREE_SOURCES = {
    name: ROOT / f"focus_trees/SHL/{name}/focuses.txt"
    for name in ("main", "houses", "cities", "directorate", "regency", "commune")
}
SHARED_FOCUS_SOURCE = ROOT / "focus_trees/SHL/shared/focuses.txt"
FOCUS_OUTPUTS = {
    "main": "ADISCORD_SHL_focus.txt",
    "houses": "ADISCORD_SHL_houses.txt",
    "cities": "ADISCORD_SHL_cities.txt",
    "directorate": "ADISCORD_SHL_directorate.txt",
    "regency": "ADISCORD_SHL_regency.txt",
    "commune": "ADISCORD_SHL_commune.txt",
    "shared": "ADISCORD_SHL_shared.txt",
}
COURSE_TREES = {"houses": 1, "cities": 2, "directorate": 3, "regency": 4, "commune": 5}
# commit effect suffix -> (course tree, cosmetic tag)
COURSE_COMMITS = {
    "house": ("houses", "SHL_conclave_of_ten"),
    "city": ("cities", "SHL_southern_compact"),
    "state": ("directorate", "SHL_iron_directorate"),
    "regency": ("regency", "SHL_hereditary_republic"),
    "commune": ("commune", "SHL_commune_of_fire"),
}


@lru_cache(maxsize=None)
def focus_tree(name):
    """Parsed body of one authored SHL focus_tree."""
    return block(parse_clausewitz(FOCUS_TREE_SOURCES[name].read_text(encoding="utf-8")), "focus_tree")


@lru_cache(maxsize=None)
def tree_focuses(name):
    """id -> body of the focuses authored inside one tree."""
    return {scalar(entry.value, "id"): entry.value for entry in focus_tree(name) if entry.key == "focus"}


@lru_cache(maxsize=None)
def shared_focuses():
    """id -> body of the top-level shared focuses of the southern front."""
    return {
        scalar(entry.value, "id"): entry.value
        for entry in parse_clausewitz(SHARED_FOCUS_SOURCE.read_text(encoding="utf-8"))
        if entry.key == "shared_focus"
    }


@lru_cache(maxsize=None)
def all_focus_definitions():
    definitions = {}
    for name in FOCUS_TREE_SOURCES:
        definitions.update(tree_focuses(name))
    definitions.update(shared_focuses())
    return definitions


def shl_focus_text():
    paths = (*FOCUS_TREE_SOURCES.values(), SHARED_FOCUS_SOURCE)
    return "\n".join(path.read_text(encoding="utf-8") for path in paths)


def focus_definition(identifier):
    return all_focus_definitions()[identifier]


@lru_cache(maxsize=None)
def shared_definitions(relative_path, names):
    definitions = {
        entry.key: entry.value
        for entry in parse_clausewitz((ROOT / relative_path).read_text(encoding="utf-8"))
    }
    return {name: definitions[name] for name in names}


def balance_ranges(identifier):
    """Range id -> (min, max) of one balance of power, root and side ranges alike."""
    balance = block(parse_clausewitz(BOP_PATH.read_text(encoding="utf-8")), identifier)
    rows = [entry.value for entry in balance if entry.key == "range"]
    for side in (entry.value for entry in balance if entry.key == "side"):
        rows.extend(entry.value for entry in side if entry.key == "range")
    return {scalar(row, "id"): (float(scalar(row, "min")), float(scalar(row, "max"))) for row in rows}


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
        # Ruling character and the trees loaded by course ratification.
        self.leader = "SHL_Jalil_Nur"
        self.loaded_trees = []
        self.cosmetic_tags = []
        # Neighbour countries and simple engine facts used by the crisis layer.
        self.ai = False
        self.countries = {tag: {"exists": True, "is_subject": False, "has_war": False} for tag in REGIONAL}
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
        # Balances of power by id; absent until set_power_balance creates them.
        self.power_balance = {}

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
                    if tokens[:2] != ["days", ">"] or len(tokens) != 3:
                        raise AssertionError("Unsupported flag-age predicate")
                    return name in self.flags[scope] and self.flag_days[scope].get(name, 0) > int(tokens[2])
                return e.value in self.flags[scope]
            if e.key in ("ROOT", "SHL"):
                country = self.root_scope if e.key == "ROOT" else "SHL"
                return self.condition_scope(e.value, country, scope, target)
            if e.key in REGIONAL:
                return self.condition_scope(e.value, e.key, scope, target)
            if e.key == "exists" and scope in self.countries:
                return self.countries[scope]["exists"] == (e.value == "yes")
            if e.key == "is_subject_of":
                expected = self.root_scope if e.value == "ROOT" else e.value
                return self.countries.get(scope, {}).get("subject_of") == expected
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
                other = self.root_scope if e.value == "ROOT" else e.value
                return frozenset((scope, other)) in self.wars
            if e.key == "is_in_faction_with":
                other = self.root_scope if e.value == "ROOT" else e.value
                return self.factions.get(scope) is not None and self.factions.get(scope) == self.factions.get(other)
            if e.key == "is_in_faction":
                return (self.factions.get(scope) is not None) == (e.value == "yes")
            if e.key == "is_faction_leader":
                return (self.factions.get(scope) == scope) == (e.value == "yes")
            if e.key == "has_active_mission":
                return e.value in self.missions
            if e.key == "has_character":
                return True
            if e.key == "has_country_leader":
                return scalar(e.value, "character") == self.leader
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
            if e.key == "has_power_balance":
                return scalar(e.value, "id") in self.power_balance
            if e.key == "is_power_balance_in_range":
                identifier = scalar(e.value, "id")
                if identifier not in self.power_balance:
                    return False
                low, high = balance_ranges(identifier)[scalar(e.value, "range")]
                return low <= self.power_balance[identifier] <= high
            if e.key == "power_balance_value":
                identifier = scalar(e.value, "id")
                tokens = [c.value for c in e.value if not c.key]
                if len(tokens) != 3 or tokens[0] != "value" or tokens[1] not in ("<", ">"):
                    raise AssertionError("Unsupported balance comparison: " + repr(tokens))
                if identifier not in self.power_balance:
                    return False
                current = self.power_balance[identifier]
                return current < float(tokens[2]) if tokens[1] == "<" else current > float(tokens[2])
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
                right = self.value(comparison[2], scope)
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
            elif e.key in REGIONAL:
                self.switch_scope(e.value, e.key, scope, target)
            elif e.key == "random_list":
                # Deterministic stand-in: the first weighted branch runs.
                branch = next(c.value for c in e.value if c.key.isdigit())
                self.execute([c for c in branch if c.key != "modifier"], scope, target)
            elif e.key == "annex_country":
                annexed = self.previous_scope if scalar(e.value, "target") == "PREV" else scalar(e.value, "target")
                self.countries.setdefault(annexed, {})["exists"] = False
                self.calls.append(("annex_country", scope, annexed))
            elif e.key in ("add_claim_by", "remove_claim_by"):
                self.calls.append((e.key, scope, e.value))
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
            elif e.key == "promote_character":
                self.leader = scalar(e.value, "character")
                self.calls.append((e.key, scope))
            elif e.key == "retire_character":
                if self.leader == e.value:
                    self.leader = None
                self.calls.append((e.key, scope))
            elif e.key == "SHL_Jalil_Nur":
                self.switch_scope(e.value, scope, scope, target)
            elif e.key == "add_country_leader_role":
                if scalar(e.value, "promote_leader") == "yes":
                    self.leader = scalar(e.value, "character")
                self.calls.append((e.key, scope))
            elif e.key == "load_focus_tree":
                self.loaded_trees.append(scalar(e.value, "tree"))
            elif e.key == "set_cosmetic_tag":
                self.cosmetic_tags.append(e.value)
            elif e.key in (
                "set_politics", "add_popularity", "remove_country_leader_role",
                "mark_focus_tree_layout_dirty", "force_update_dynamic_modifier", "add_war_support",
                "ADISCORD_release_non_participating_minor_optimization",
                "ADISCORD_south_crisis_add_campaign", "ADISCORD_south_crisis_cycle",
                "SHL_crisis_draw",
                "ADISCORD_south_offer_alliance", "ADISCORD_south_demand_annexation",
                "ADISCORD_south_demand_submission", "save_event_target_as",
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
            elif e.key == "set_power_balance":
                self.power_balance[scalar(e.value, "id")] = float(scalar(e.value, "set_value"))
            elif e.key == "add_power_balance_value":
                # The native effect is silent for a balance the country never created.
                identifier = scalar(e.value, "id")
                if identifier in self.power_balance:
                    moved = self.power_balance[identifier] + float(scalar(e.value, "value"))
                    self.power_balance[identifier] = round(max(-1.0, min(1.0, moved)), 4)
            elif e.key in ("set_variable", "set_temp_variable", "add_to_variable", "subtract_from_variable", "multiply_variable", "divide_variable"):
                name = scalar(e.value, "var")
                amount = self.value(scalar(e.value, "value"), scope)
                previous = self.variables[scope].get(name, 0.0)
                if e.key in ("set_variable", "set_temp_variable"):
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
                name = scalar(e.value, "flag") if isinstance(e.value, list) else e.value
                self.flags[scope].add(name)
                self.flag_days[scope][name] = 0
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
            elif e.key in ("country_event", "news_event"):
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
        # The packet price is set by the startup initialiser and every refresh.
        self.machine.variables["SHL"]["SHL_packet_price"] = 25.0
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

    def test_treasury_receipt_pays_250_and_refreshes_the_budget(self):
        machine = self.machine
        machine.variables["SHL"]["ADISCORD_economy_treasury"] = 100
        machine.run("SHL_receive_250")
        self.assertEqual(machine.variables["SHL"]["ADISCORD_economy_treasury"], 350)
        self.assertIn("ADISCORD_economy_mark_dirty", machine.calls)

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
            if not identifier.startswith("ADISCORD_SHL."):
                continue
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
        shared = shared_focuses()
        ids = []
        for name in FOCUS_TREE_SOURCES:
            with self.subTest(tree=name):
                focuses = dict(tree_focuses(name))
                ids.extend(focuses)
                if name != "main":
                    # The front of the South and the crown are placed in every course tree.
                    references = [e.value for e in focus_tree(name) if e.key == "shared_focus"]
                    self.assertEqual(sorted(references), ["SHL_south_crown_of_the_south", "SHL_south_furnaces_to_front"])
                    focuses.update(shared)
                cells = [(int(scalar(f, "x")), int(scalar(f, "y"))) for f in focuses.values()]
                self.assertEqual(len(cells), len(set(cells)))
                for focus in focuses.values():
                    for prerequisite in [e.value for e in focus if e.key == "prerequisite"]:
                        for item in prerequisite:
                            self.assertIn(item.value, focuses)
                    for exclusive in block(focus, "mutually_exclusive"):
                        self.assertIn(exclusive.value, focuses)
        ids.extend(shared)
        # Preparation (57) plus five course trees and the shared front layer.
        self.assertGreaterEqual(len(ids), 240)
        self.assertEqual(len(set(ids)), len(ids))
        for name, output in FOCUS_OUTPUTS.items():
            self.assertTrue((ROOT / "common/national_focus" / output).is_file(), name)

    def test_hidden_courses_are_gated_by_their_crisis_flags(self):
        # The regency and commune trees are selected by the course value that only
        # the crisis events and their backing decisions can set; no focus commits them.
        for tree, course in (("regency", 4), ("commune", 5)):
            modifier = block(block(focus_tree(tree), "country"), "modifier")
            check = block(modifier, "check_variable")
            self.assertEqual((scalar(check, "var"), scalar(check, "value"), scalar(check, "compare")), ("SHL_political_course", str(course), "equals"))
            self.assertEqual(scalar(block(focus_tree(tree), "country"), "factor"), "0")
            self.assertEqual(scalar(focus_tree(tree), "default"), "no")
        self.assertNotIn("SHL_regency_council", tree_focuses("main"))
        self.assertNotIn("SHL_shift_councils", tree_focuses("main"))
        focuses = shl_focus_text()
        self.assertNotIn("SHL_commit_regency_course = yes", focuses)
        self.assertNotIn("SHL_commit_commune_course = yes", focuses)
        events = (ROOT / "events/ADISCORD_SHL_events.txt").read_text(encoding="utf-8")
        decisions = (ROOT / "common/decisions/ADISCORD_SHL_decisions.txt").read_text(encoding="utf-8")
        self.assertIn("SHL_commit_regency_course = yes", events)
        self.assertIn("SHL_commit_commune_course = yes", events)
        for decision, trigger in (("SHL_back_crests", "SHL_can_back_crests"), ("SHL_back_shift_councils", "SHL_can_back_shift_councils")):
            available = block(decision_definition(decision), "available")
            self.assertEqual([(e.key, e.value) for e in available], [(trigger, "yes")])
            self.assertIn(f"{trigger} = yes", decisions)

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
        m.power_balance[BALANCE] = -0.20
        m.run("SHL_refresh_furnaces")
        self.assertAlmostEqual(m.variables["SHL"]["SHL_pp_gain"], 0.05)
        m.run("SHL_update_tensions")
        self.assertAlmostEqual(m.power_balance[BALANCE], -0.20)
        m.run("SHL_extinguish_site", scope="287")
        m.run("SHL_extinguish_site", scope="288")
        m.run("SHL_extinguish_site", scope="289")
        m.run("SHL_refresh_furnaces")
        self.assertAlmostEqual(m.variables["SHL"]["SHL_pp_gain"], 0.05 * 6 / 9)
        # Six votes: the quarters gain two points of the balance every cycle.
        m.run("SHL_update_tensions")
        self.assertAlmostEqual(m.power_balance[BALANCE], -0.18)
        # A ratified course stops counting hereditary votes; the directorate
        # must not drift out of equilibrium while it owns every furnace.
        m.variables["SHL"]["SHL_political_course"] = 3
        m.run("SHL_update_tensions")
        self.assertAlmostEqual(m.power_balance[BALANCE], -0.18)

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
        self.assertEqual(self.m.equipment[("SHL", "infantry_equipment")], 6750)
        self.assertEqual(self.m.equipment[("SHL", "ADISCORD_squad_weapons_equipment_0")], 5)
        self.assertEqual(self.c["SHL_obligation_deposit"], 45)
        before = self.c["ADISCORD_economy_treasury"]
        self.m.run("SHL_cancel_obligation")
        self.m.run("SHL_cancel_obligation")
        self.assertEqual(self.c["ADISCORD_economy_treasury"], before + 45)
        self.cycle()
        self.assertEqual(self.m.equipment[("SHL", "infantry_equipment")], 9450)

    def test_overtime_delivers_two_paid_batches_without_normal_revenue(self):
        self.begin(3)
        self.c["SHL_shift_policy"] = 1
        self.cycle()
        self.assertEqual(self.m.equipment[("SHL", "infantry_equipment")], 13500)
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
        self.assertEqual(self.m.equipment[("SHL", "infantry_equipment")], 6750)

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
            # A block may offer the two halves of an exclusive pair; the two
            # blocks themselves stay separate requirements.
            for blocks in prerequisites:
                names = [e.value for e in blocks]
                self.assertTrue(1 <= len(names) <= 2, identifier)
                if len(names) == 2:
                    first, second = (focus_definition(name) for name in names)
                    self.assertIn(names[1], {e.value for e in block(first, "mutually_exclusive")}, identifier)
                    self.assertIn(names[0], {e.value for e in block(second, "mutually_exclusive")}, identifier)

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
        focuses = shl_focus_text()
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
        # The preparation plan with the higher weight interrupts the industrial
        # programme whenever one of its focuses is available; the merged queue
        # follows that priority for each of the three preliminary courses.
        plans = {e.key: e.value for e in parse_clausewitz((ROOT / "common/ai_strategy_plans/ADISCORD_SHL_plans.txt").read_text(encoding="utf-8"))}
        programme = [e.value for e in block(plans["SHL_furnaces_plan"], "ai_national_focuses")]
        self.assertEqual(scalar(block(plans["SHL_furnaces_plan"], "weight"), "factor"), "20")
        for course, mandate in (("houses", "SHL_house_war_mandate"), ("cities", "SHL_city_war_mandate"), ("directorate", "SHL_directorate_war_mandate")):
            with self.subTest(course=course):
                plan = plans[f"SHL_prepare_{course}_plan"]
                self.assertEqual(scalar(block(plan, "weight"), "factor"), "30")
                pending = [e.value for e in block(plan, "ai_national_focuses")]
                self.assertIn(mandate, pending)
                completed = set()
                elapsed = 0
                dates = {}

                def ready(identifier):
                    focus = focus_definition(identifier)
                    return all(any(e.value in completed for e in prerequisite) for prerequisite in [e.value for e in focus if e.key == "prerequisite"])

                for identifier in programme:
                    while pending and ready(pending[0]):
                        elapsed += int(scalar(focus_definition(pending[0]), "cost")) * 7
                        dates[pending[0]] = elapsed
                        completed.add(pending.pop(0))
                    self.assertTrue(ready(identifier), identifier)
                    elapsed += int(scalar(focus_definition(identifier), "cost")) * 7
                    dates[identifier] = elapsed
                    completed.add(identifier)
                self.assertEqual(pending, [])
                self.assertLessEqual(dates["SHL_campaign_logistics"] + 56, 280)
                self.assertLessEqual(dates["SHL_factory_militia"] + 21, 280)
                self.assertLess(dates[mandate], 340)
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
        cls.focuses = all_focus_definitions()
        cls.effects = {e.key: e.value for e in parse_clausewitz(EFFECT_PATH.read_text(encoding="utf-8"))}

    def test_percentage_system_has_no_runtime_consumers(self):
        for name in self.effects:
            self.assertFalse(name.startswith("SHL_fire_"), name)
        for path in (EFFECT_PATH, *FOCUS_TREE_SOURCES.values(), SHARED_FOCUS_SOURCE,
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
            self.assertIn(final, tree_focuses(course), course)
            for side, other in (("a", "b"), ("b", "a")):
                name = f"SHL_{course}_prog_ending_{side}"
                ending = tree_focuses(course)[name]
                self.assertEqual(scalar(block(ending, "prerequisite"), "focus"), final, name)
                self.assertEqual(scalar(block(ending, "mutually_exclusive"), "focus"), f"SHL_{course}_prog_ending_{other}")
                reward = repr(block(ending, "completion_reward"))
                self.assertIn(f"SHL_delivery_{course}_{side}_tt", reward)
                self.assertIn("SHL_refresh_furnaces", reward)
                self.assertIn("SHL_prog_ending", reward)
                self.assertIn(f"SHL_pow_{course}_prog_ending_{side}_idea = {{", ideas)
        tree = shl_focus_text()
        self.assertNotIn("SHL_programme", tree)
        self.assertNotIn("SHL_fire_align", tree)

    def test_every_conclave_preview_idea_is_defined_once_and_used(self):
        tree = shl_focus_text()
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
                self.m.power_balance[BALANCE] = -0.60 if course == 4 else 0.60
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
                    self.m.power_balance[BALANCE] = -0.60 if crisis == "SHL_conspiracy_active" else 0.60
                    was_available = self.m.matches(block(option, "trigger"), "SHL")
                    self.m.execute(block(decision_definition(decision), "complete_effect"), "SHL")
                    fields = ("variables", "flags", "missions", "ideas", "idea_days", "values",
                              "stability", "equipment", "scheduled", "power_balance")
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

    def test_direct_routes_ratify_without_a_finished_tenth_furnace(self):
        # The city course starts at -0.20 and needs the quarters' influence: the
        # direct route adds one quarters focus and the paid register recognition.
        for first, second, ratify, extra, days in (
            ("SHL_new_house", "SHL_house_compromise", "SHL_admit_tenth_house", (), 252),
            ("SHL_open_conclave", "SHL_city_charters", "SHL_rights_without_fire", ("SHL_quarter_listening",), 280),
            ("SHL_nur_directorate", "SHL_common_dispatch", "SHL_state_furnaces", (), 252),
        ):
            with self.subTest(course=first):
                self.setUp()
                self.m.power_balance[BALANCE] = -0.20
                self.m.ideas.add("SHL_unregistered_quarters")
                elapsed = 0
                engineer_finish = 0
                route = ("SHL_law_of_continuous_fire", "SHL_census_of_nine", *extra,
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
                    reward = block(focus, "completion_reward")
                    self.m.execute([e for e in reward if e.key == "add_power_balance_value"], "SHL")
                    if identifier == first:
                        self.assertEqual(elapsed, 84 + 28 * len(extra))
                    elif identifier == "SHL_engineer_society":
                        self.m.run("SHL_begin_engineers")
                        engineer_finish = elapsed + int(scalar(decision_definition("SHL_project_engineers"), "days_remove"))
                    elif identifier == "SHL_workers_charter":
                        if extra:
                            self.m.run("SHL_recognise_quarter_registers")
                        self.m.execute(block(reward, "hidden_effect"), "SHL")
                self.assertEqual(elapsed, days)
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
        self.assertEqual(self.m.equipment[("SHL", "infantry_equipment")], 2700)
        self.assertEqual(self.c["ADISCORD_economy_treasury"], before + 480)
        self.m.run("SHL_produce_period")
        self.assertEqual(self.m.equipment[("SHL", "infantry_equipment")], 5400)

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
                                         (2700, 5400, 1350)[shift] if effective == 1 else 0)
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
        self.assertEqual(self.m.equipment[("SHL", "infantry_equipment")], 2700)
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
        self.assertEqual(self.m.equipment[("SHL", "infantry_equipment")], 13500)
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
                self.assertEqual(self.m.equipment[("SHL", "infantry_equipment")], arsenal * 2700)

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


class ConclaveBalanceTests(unittest.TestCase):
    REQUIRED_STEPS = (-0.30, -0.25, -0.15, -0.10, -0.05, -0.03, 0.02, 0.03, 0.05, 0.10, 0.15, 0.25, 0.30)
    RANGES = {
        "SHL_balance_crests_dominance": (-1.0, -0.5),
        "SHL_balance_crests_influence": (-0.5, -0.1),
        "SHL_balance_equilibrium": (-0.1, 0.1),
        "SHL_balance_quarters_influence": (0.1, 0.5),
        "SHL_balance_quarters_dominance": (0.5, 1.0),
    }
    MISSIONS = ("SHL_strike_mission", "SHL_conspiracy_mission", "SHL_mazar_deadline")

    def setUp(self):
        CrisisLayerTests.setUp(self)
        self.m.power_balance[BALANCE] = -0.20

    country = CrisisLayerTests.country
    event = ShahrabadCabinetTests.event

    def balance(self):
        return self.m.power_balance[BALANCE]

    def option(self, identifier, name):
        return next(e.value for e in self.event(identifier) if e.key == "option" and scalar(e.value, "name") == name)

    def test_balance_declares_both_sides_and_five_ranges_with_economy_hooks(self):
        balance = block(parse_clausewitz(BOP_PATH.read_text(encoding="utf-8")), BALANCE)
        self.assertEqual(scalar(balance, "left_side"), "SHL_bop_crests")
        self.assertEqual(scalar(balance, "right_side"), "SHL_bop_quarters")
        self.assertEqual(scalar(balance, "decision_category"), "SHL_quarters_and_borders")
        self.assertEqual(balance_ranges(BALANCE), self.RANGES)
        sides = [e.value for e in balance if e.key == "side"]
        self.assertEqual([scalar(side, "id") for side in sides], ["SHL_bop_crests", "SHL_bop_quarters"])
        rows = [e.value for e in balance if e.key == "range"]
        for side in sides:
            rows.extend(e.value for e in side if e.key == "range")
        for row in rows:
            self.assertTrue(block(row, "modifier"), scalar(row, "id"))
            for hook in ("on_activate", "on_deactivate"):
                self.assertEqual([(e.key, e.value) for e in block(row, hook)], [("ADISCORD_economy_mark_dirty", "yes")], scalar(row, "id"))
        sprites = (ROOT / "interface/ADISCORD_bop.gfx").read_text(encoding="utf-8")
        for side in sides:
            icon = scalar(side, "icon")
            texture = re.search(rf'name = "{icon}"\s+texturefile = "([^"]+)"', sprites)
            self.assertIsNotNone(texture, icon)
            self.assertTrue((ROOT / texture.group(1)).is_file(), icon)

    def test_initialization_sets_the_balance_once_inside_the_guard(self):
        effects = parse_clausewitz(EFFECT_PATH.read_text(encoding="utf-8"))
        m = ScriptMachine(effects, parse_clausewitz(TRIGGER_PATH.read_text(encoding="utf-8")))
        init = m.effects["SHL_initialize_furnaces"]
        self.assertEqual([e.key for e in init], ["if"])
        self.assertIn("SHL_furnaces_initialized", [e.value for e in walk_entries(block(block(init, "if"), "limit"))])
        self.assertEqual(scalar(block(block(init, "if"), "set_power_balance"), "set_value"), "-0.20")
        self.assertNotIn(BALANCE, m.power_balance)
        m.run("SHL_initialize_furnaces")
        self.assertEqual(m.power_balance[BALANCE], -0.20)
        m.power_balance[BALANCE] = 0.40
        m.run("SHL_initialize_furnaces")
        self.assertEqual(m.power_balance[BALANCE], 0.40)

    def test_balance_shift_maps_every_caller_step_to_a_fixed_literal(self):
        shift = self.m.effects["SHL_balance_shift"]
        self.assertEqual([e.key for e in shift], ["if"])
        guard = block(shift, "if")
        self.assertEqual(scalar(block(block(guard, "limit"), "has_power_balance"), "id"), BALANCE)
        mapping = {}
        for branch in (e.value for e in guard if e.key in ("if", "else_if")):
            check = block(block(branch, "limit"), "check_variable")
            self.assertEqual((scalar(check, "var"), scalar(check, "compare")), ("SHL_balance_shift", "equals"))
            applied = block(branch, "add_power_balance_value")
            self.assertEqual(scalar(applied, "id"), BALANCE)
            self.assertEqual(scalar(applied, "value"), scalar(check, "value"))
            mapping[scalar(check, "value")] = float(scalar(applied, "value"))
        self.assertEqual(sorted(mapping.values()), sorted(self.REQUIRED_STEPS))
        caller = re.compile(r"set_temp_variable = \{ var = SHL_balance_shift value = (-?\d+\.\d+) \}\n\s*SHL_balance_shift = yes\n")
        steps = []
        for path in (EFFECT_PATH, ROOT / "common/decisions/ADISCORD_SHL_decisions.txt",
                     ROOT / "events/ADISCORD_SHL_events.txt", *FOCUS_TREE_SOURCES.values(), SHARED_FOCUS_SOURCE):
            text = path.read_text(encoding="utf-8")
            steps.extend(caller.findall(text))
            self.assertEqual(text.count("SHL_balance_shift = yes"), len(caller.findall(text)), path.name)
        self.assertTrue(steps)
        self.assertLessEqual(set(steps), set(mapping))

    def test_balance_shift_moves_only_an_existing_balance_by_mapped_steps(self):
        self.country()["SHL_balance_shift"] = -0.15
        self.m.run("SHL_balance_shift")
        self.assertAlmostEqual(self.balance(), -0.35)
        self.country()["SHL_balance_shift"] = 0.07
        self.m.run("SHL_balance_shift")
        self.assertAlmostEqual(self.balance(), -0.35)
        self.country()["SHL_balance_shift"] = -1.0
        self.m.run("SHL_balance_shift")
        self.assertAlmostEqual(self.balance(), -0.35)
        del self.m.power_balance[BALANCE]
        self.country()["SHL_balance_shift"] = 0.30
        self.m.run("SHL_balance_shift")
        self.assertNotIn(BALANCE, self.m.power_balance)

    def test_course_ratifications_shift_by_their_specified_steps(self):
        for effect, delta in (
            ("SHL_commit_house_course", -0.15),
            ("SHL_commit_city_course", 0.15),
            ("SHL_commit_state_course", 0.0),
            ("SHL_commit_regency_course", -0.30),
            ("SHL_commit_commune_course", 0.30),
        ):
            with self.subTest(effect=effect):
                self.setUp()
                self.m.run(effect)
                self.assertAlmostEqual(self.balance(), -0.20 + delta)
                self.m.run(effect)
                self.assertAlmostEqual(self.balance(), -0.20 + delta)

    def test_registers_crackdown_and_cycle_shift_the_balance(self):
        self.m.ideas.add("SHL_unregistered_quarters")
        self.m.run("SHL_recognise_quarter_registers")
        self.m.run("SHL_recognise_quarter_registers")
        self.assertAlmostEqual(self.balance(), -0.15)
        self.m.flags["SHL"].add("SHL_strike_active")
        self.m.run("SHL_strike_suppress")
        self.assertAlmostEqual(self.balance(), -0.25)
        self.m.run("SHL_strike_suppress")
        self.assertAlmostEqual(self.balance(), -0.25)
        self.country()["SHL_house_votes"] = 7
        self.m.run("SHL_update_tensions")
        self.assertAlmostEqual(self.balance(), -0.25)
        self.country()["SHL_house_votes"] = 6
        self.m.run("SHL_update_tensions")
        self.assertAlmostEqual(self.balance(), -0.23)
        # Ratified courses stop counting hereditary votes.
        self.country()["SHL_political_course"] = 3
        self.m.run("SHL_update_tensions")
        self.assertAlmostEqual(self.balance(), -0.23)

    def test_decisions_and_focuses_shift_the_balance_visibly(self):
        for decision, target, delta in (
            ("SHL_house_banquet", None, -0.03),
            ("SHL_soup_kitchens", None, 0.03),
            ("SHL_return_house", "287", -0.05),
            ("SHL_city_ownership", "287", 0.05),
        ):
            with self.subTest(decision=decision):
                self.setUp()
                effect = block(decision_definition(decision), "complete_effect")
                self.assertIn("add_power_balance_value", [e.key for e in effect])
                self.m.target_scope = target
                self.m.execute(effect, "SHL", target)
                self.assertAlmostEqual(self.balance(), -0.20 + delta)
        for focus, delta in (
            ("SHL_workers_charter", 0.15),
            ("SHL_heralds_table", -0.05),
            ("SHL_quarter_listening", 0.05),
            ("SHL_new_house", -0.10),
            ("SHL_open_conclave", 0.10),
            ("SHL_nur_directorate", 0.0),
        ):
            with self.subTest(focus=focus):
                self.setUp()
                reward = block(focus_definition(focus), "completion_reward")
                self.assertEqual("add_power_balance_value" in [e.key for e in reward], delta != 0)
                self.m.execute([e for e in reward if e.key == "add_power_balance_value"], "SHL")
                self.assertAlmostEqual(self.balance(), -0.20 + delta)

    def test_hidden_courses_need_an_open_crisis_and_dominance(self):
        for trigger, flag, dominance in (
            ("SHL_can_back_crests", "SHL_conspiracy_active", -0.60),
            ("SHL_can_back_shift_councils", "SHL_strike_active", 0.60),
        ):
            with self.subTest(trigger=trigger):
                self.setUp()
                self.m.flags["SHL"].add(flag)
                self.m.power_balance[BALANCE] = dominance / 2
                self.assertFalse(self.m.matches(self.m.triggers[trigger], "SHL"))
                self.m.power_balance[BALANCE] = dominance
                self.assertTrue(self.m.matches(self.m.triggers[trigger], "SHL"))
                self.m.flags["SHL"].discard(flag)
                self.assertFalse(self.m.matches(self.m.triggers[trigger], "SHL"))

    def test_crisis_failures_offer_the_hidden_course_with_a_visible_shift(self):
        for identifier, name, flag, dominance, course, delta in (
            ("ADISCORD_SHL.31", "ADISCORD_SHL.31.a", "SHL_conspiracy_active", -0.60, 4, -0.55),
            ("ADISCORD_SHL.21", "ADISCORD_SHL.21.a", "SHL_strike_active", 0.60, 5, 0.55),
        ):
            with self.subTest(event=identifier):
                self.setUp()
                option = self.option(identifier, name)
                effects = [e for e in option if e.key not in ("name", "trigger", "ai_chance")]
                self.assertEqual([e.key for e in effects], ["if"])
                # The crisis shift stays visible beside the course tooltip.
                self.assertIn("add_power_balance_value", [e.key for e in block(effects, "if")])
                self.m.flags["SHL"].add(flag)
                self.m.power_balance[BALANCE] = dominance / 2
                self.assertFalse(self.m.matches(block(option, "trigger"), "SHL"))
                self.m.execute(effects, "SHL")
                self.assertEqual(self.country().get("SHL_political_course", 0), 0)
                self.m.power_balance[BALANCE] = dominance
                self.assertTrue(self.m.matches(block(option, "trigger"), "SHL"))
                self.m.execute(effects, "SHL")
                self.assertEqual(self.country()["SHL_political_course"], course)
                # The crisis step and the ratification step both apply; the balance clamps at its edge.
                expected = max(-1.0, min(1.0, dominance + delta))
                self.assertAlmostEqual(self.balance(), expected)
                self.m.execute(effects, "SHL")
                self.assertAlmostEqual(self.balance(), expected)

    def test_ratification_finals_require_their_balance_range(self):
        for focus, tooltip, ranges, passing, failing in (
            ("SHL_admit_tenth_house", "SHL_ratify_needs_crests_tt",
             {"SHL_balance_crests_influence", "SHL_balance_crests_dominance"}, (-0.60, -0.30), (0.0, 0.30)),
            ("SHL_rights_without_fire", "SHL_ratify_needs_quarters_tt",
             {"SHL_balance_quarters_influence", "SHL_balance_quarters_dominance"}, (0.30, 0.60), (0.0, -0.30)),
            ("SHL_state_furnaces", "SHL_ratify_needs_equilibrium_tt",
             {"SHL_balance_equilibrium"}, (0.0, 0.05), (-0.30, 0.30)),
        ):
            with self.subTest(focus=focus):
                available = block(focus_definition(focus), "available")
                gate = next(e.value for e in available if e.key == "custom_trigger_tooltip" and scalar(e.value, "tooltip") == tooltip)
                found = {scalar(e.value, "range") for e in walk_entries(gate) if e.key == "is_power_balance_in_range"}
                self.assertEqual(found, ranges)
                self.country()["SHL_city_support"] = 40
                for value in passing:
                    self.m.power_balance[BALANCE] = value
                    self.assertTrue(self.m.matches(available, "SHL"), value)
                for value in failing:
                    self.m.power_balance[BALANCE] = value
                    self.assertFalse(self.m.matches(available, "SHL"), value)

    def test_seven_house_votes_gate_only_the_hereditary_republic(self):
        holders = {
            identifier
            for identifier, focus in all_focus_definitions().items()
            if any(
                e.key == "check_variable" and scalar(e.value, "var") == "SHL_house_votes"
                for e in walk_entries(block(focus, "available"))
            )
        }
        self.assertEqual(holders, {"SHL_hereditary_republic"})
        for trigger in ("SHL_can_back_crests", "SHL_can_back_shift_councils"):
            self.assertNotIn("SHL_house_votes", [scalar(e.value, "var") for e in walk_entries(self.m.triggers[trigger]) if e.key == "check_variable"])

    def test_mission_tokens_are_registered_once(self):
        tokens = (ROOT / "common/synchronized_dynamic_tokens/ADISCORD_tokens.txt").read_text(encoding="utf-8").split()
        for name in self.MISSIONS:
            self.assertIsNotNone(scalar(decision_definition(name), "days_mission_timeout"), name)
            self.assertEqual(tokens.count(name), 1, name)

    def test_treasury_category_stays_visible_when_empty(self):
        categories = parse_clausewitz((ROOT / "common/decisions/categories/ADISCORD_decision_categories_SHL.txt").read_text(encoding="utf-8"))
        self.assertEqual(scalar(block(categories, "SHL_treasury"), "visible_when_empty"), "yes")


class CourseTreeStructureTests(unittest.TestCase):
    """Main preparation tree, five course trees and the shared southern layer."""

    def setUp(self):
        effects = parse_clausewitz(EFFECT_PATH.read_text(encoding="utf-8"))
        triggers = parse_clausewitz(TRIGGER_PATH.read_text(encoding="utf-8"))
        self.m = ScriptMachine(effects, triggers)
        self.m.flags["SHL"].add("SHL_furnaces_initialized")

    def test_course_trees_are_selected_by_the_course_value_and_commit_loads_each_once(self):
        for suffix, (tree, tag) in COURSE_COMMITS.items():
            with self.subTest(course=suffix):
                self.setUp()
                self.m.run(f"SHL_commit_{suffix}_course")
                self.m.run(f"SHL_commit_{suffix}_course")
                self.assertEqual(self.m.loaded_trees, [f"SHL_{tree}_focus"])
                self.assertEqual(self.m.cosmetic_tags, [tag])
                self.assertEqual(self.m.scheduled.count("ADISCORD_SHL.123"), 1)
                self.assertEqual(self.m.variables["SHL"]["SHL_political_course"], COURSE_TREES[tree])
                self.assertEqual(scalar(focus_tree(tree), "id"), f"SHL_{tree}_focus")
                effect = self.m.effects[f"SHL_commit_{suffix}_course"]
                guard = [e for e in block(effect, "if") if e.key != "limit"]
                self.assertEqual(guard[-1].key, "load_focus_tree")
                self.assertEqual(scalar(guard[-1].value, "keep_completed"), "yes")
                # The visible rename precedes the hidden tag write.
                hidden = [e for e in guard if e.key == "hidden_effect" and any(c.key == "set_cosmetic_tag" for c in e.value)]
                self.assertEqual(len(hidden), 1)
                self.assertEqual(guard[guard.index(hidden[0]) - 1].value, f"SHL_rename_{suffix}_tt")

    def test_state_course_moves_nur_to_an_etatist_role_only_while_he_rules(self):
        self.m.run("SHL_commit_state_course")
        self.assertEqual(self.m.leader, "SHL_Jalil_Nur")
        self.assertIn(("add_country_leader_role", "SHL"), self.m.calls)
        self.assertIn(("remove_country_leader_role", "SHL"), self.m.calls)
        role = next(e.value for e in walk_entries(self.m.effects["SHL_commit_state_course"]) if e.key == "add_country_leader_role")
        leader = block(role, "country_leader")
        self.assertEqual(scalar(leader, "ideology"), "service_etatism")
        self.assertEqual(scalar(role, "promote_leader"), "yes")
        ideologies = (ROOT / "common/ideologies/00_ideologies.txt").read_text(encoding="utf-8")
        self.assertIn("\t\t\tservice_etatism = {", ideologies)
        politics = next(e.value for e in walk_entries(self.m.effects["SHL_commit_state_course"]) if e.key == "set_politics")
        self.assertEqual(scalar(politics, "ruling_party"), "etatism")
        self.setUp()
        self.m.run("SHL_commit_city_course")
        self.assertEqual(self.m.leader, "SHL_Mariam_Arbin")
        politics = next(e.value for e in walk_entries(self.m.effects["SHL_commit_city_course"]) if e.key == "set_politics")
        self.assertEqual(scalar(politics, "ruling_party"), "pragmatism")
        self.setUp()
        self.m.run("SHL_commit_regency_course")
        self.assertEqual(self.m.leader, "SHL_Darius_Safir")

    def test_cosmetic_tags_exist_with_three_flag_sizes(self):
        cosmetic = {e.key: e.value for e in parse_clausewitz((ROOT / "common/countries/cosmetic.txt").read_text(encoding="utf-8-sig"))}
        for _, tag in COURSE_COMMITS.values():
            with self.subTest(tag=tag):
                self.assertIn(tag, cosmetic)
                self.assertEqual({e.key for e in cosmetic[tag]}, {"color", "color_ui"})
                for folder in ("", "medium/", "small/"):
                    self.assertTrue((ROOT / f"gfx/flags/{folder}{tag}.tga").is_file(), folder)

    def test_shared_front_is_defined_once_and_referenced_by_every_course_tree(self):
        shared = shared_focuses()
        source = SHARED_FOCUS_SOURCE.read_text(encoding="utf-8")
        self.assertEqual(sorted(shared), [
            "SHL_south_crown_of_the_south", "SHL_south_desert_convoys", "SHL_south_furnaces_to_front",
            "SHL_south_raid_oil_fields", "SHL_south_storm_oil_belt",
        ])
        self.assertEqual(source.count("shared_focus = {"), 5)
        self.assertNotIn("\nfocus = {", source)
        for identifier in shared:
            self.assertEqual(sum(identifier in focuses for focuses in map(tree_focuses, FOCUS_TREE_SOURCES)), 0, identifier)
        roots = {identifier for identifier, focus in shared.items() if not block(focus, "prerequisite")}
        self.assertEqual(roots, {"SHL_south_furnaces_to_front", "SHL_south_crown_of_the_south"})
        for name in COURSE_TREES:
            references = [e.value for e in focus_tree(name) if e.key == "shared_focus"]
            self.assertEqual(set(references), roots, name)
            self.assertEqual(len(references), len(roots), name)
        self.assertEqual([e.key for e in focus_tree("main") if e.key == "shared_focus"], [])
        allow = block(shared["SHL_south_crown_of_the_south"], "allow_branch")
        self.assertEqual([(e.key, e.value) for e in allow], [("has_global_flag", "ADISCORD_south_hegemon_SHL")])
        for identifier in roots - {"SHL_south_crown_of_the_south"}:
            allow = block(shared[identifier], "allow_branch")
            self.assertEqual([(e.key, e.value) for e in allow], [("has_global_flag", "ADISCORD_south_final_started")])

    def test_course_focuses_keep_operability_without_redundant_course_gates(self):
        for name, course in COURSE_TREES.items():
            with self.subTest(tree=name):
                selector = block(block(focus_tree(name), "country"), "modifier")
                self.assertEqual(scalar(block(selector, "check_variable"), "value"), str(course))
                self.assertEqual(scalar(selector, "original_tag"), "SHL")
                roots = []
                for identifier, focus in tree_focuses(name).items():
                    available = block(focus, "available")
                    self.assertIn(("SHL_country_operable", "yes"), [(e.key, e.value) for e in available], identifier)
                    self.assertFalse(any(
                        e.key == "check_variable" and scalar(e.value, "var") == "SHL_political_course"
                        for e in walk_entries(available)
                    ), identifier)
                    self.assertNotIn("SHL_regency_path", repr(focus), identifier)
                    self.assertNotIn("SHL_commune_path", repr(focus), identifier)
                    if not block(focus, "prerequisite"):
                        roots.append(identifier)
                self.assertEqual(len(roots), 1, roots)
        for identifier in ("SHL_admit_tenth_house", "SHL_rights_without_fire", "SHL_state_furnaces"):
            self.assertIn(identifier, tree_focuses("main"))
            reward = block(focus_definition(identifier), "completion_reward")
            self.assertTrue(any(e.key.startswith("SHL_commit_") for e in walk_entries(reward)), identifier)
        native = (ROOT / "common/national_focus/ADISCORD_SHL_focus.txt").read_text(encoding="utf-8")
        self.assertIn("shared focus history", native)
        for identifier in ("SHL_admit_tenth_house", "SHL_rights_without_fire", "SHL_state_furnaces"):
            self.assertIn(f"\tid = {identifier}\n", native)

    def test_ai_plans_name_existing_focuses_and_one_alternative_per_exclusive_pair(self):
        definitions = all_focus_definitions()
        exclusive = {
            identifier: {e.value for e in block(focus, "mutually_exclusive")}
            for identifier, focus in definitions.items()
            if block(focus, "mutually_exclusive")
        }
        plans = {e.key: e.value for e in parse_clausewitz((ROOT / "common/ai_strategy_plans/ADISCORD_SHL_plans.txt").read_text(encoding="utf-8"))}
        self.assertEqual(sorted(plans), sorted([
            "SHL_furnaces_plan", "SHL_prepare_houses_plan", "SHL_prepare_cities_plan", "SHL_prepare_directorate_plan",
            "SHL_houses_plan", "SHL_cities_plan", "SHL_directorate_plan", "SHL_regency_plan", "SHL_commune_plan",
        ]))
        for name, plan in plans.items():
            with self.subTest(plan=name):
                queue = [e.value for e in block(plan, "ai_national_focuses")]
                self.assertEqual(len(queue), len(set(queue)))
                for identifier in queue:
                    self.assertIn(identifier, definitions)
                    self.assertFalse(exclusive.get(identifier, set()) & set(queue), identifier)
                enable = block(plan, "enable")
                self.assertIn(("tag", "SHL"), [(e.key, e.value) for e in enable])
                self.assertIn(("is_ai", "yes"), [(e.key, e.value) for e in enable])
        for tree, course in COURSE_TREES.items():
            plan = plans[f"SHL_{tree}_plan"]
            check = block(block(plan, "enable"), "check_variable")
            self.assertEqual((scalar(check, "var"), scalar(check, "value")), ("SHL_political_course", str(course)))
            queue = set(e.value for e in block(plan, "ai_national_focuses"))
            focuses = tree_focuses(tree)
            # The queue may leave out the unchosen half of each exclusive pair
            # and every focus reachable only through an omitted one.
            omitted = {f"SHL_{tree}_prog_ending_a", f"SHL_{tree}_prog_ending_b"}
            omitted |= {name for name in focuses if exclusive.get(name, set()) & queue}
            changed = True
            while changed:
                changed = False
                for name, focus in focuses.items():
                    if name in omitted or name in queue:
                        continue
                    blocks = [{e.value for e in b.value} for b in focus if b.key == "prerequisite"]
                    if blocks and any(options <= omitted for options in blocks):
                        omitted.add(name)
                        changed = True
            self.assertEqual(set(focuses) - queue - omitted, set(), tree)
            self.assertTrue(set(shared_focuses()) <= queue, tree)
        for tree, ranges in (
            ("houses", {"SHL_balance_crests_influence", "SHL_balance_crests_dominance"}),
            ("cities", {"SHL_balance_quarters_influence", "SHL_balance_quarters_dominance"}),
            ("directorate", {"SHL_balance_equilibrium"}),
        ):
            weight = block(plans[f"SHL_prepare_{tree}_plan"], "weight")
            found = {scalar(e.value, "range") for e in walk_entries(weight) if e.key == "is_power_balance_in_range"}
            self.assertEqual(found, ranges, tree)
            self.assertTrue(found <= set(balance_ranges(BALANCE)), tree)
        self.assertNotIn("SHL_political_course value = 0", repr(plans["SHL_houses_plan"]))


class CourseProgrammeTests(unittest.TestCase):
    """Course decisions, consolidation missions, the house demand and the revanche."""

    MISSIONS = {
        "SHL_cons_debt_term": ("SHL_start_cons_debt_term", 180),
        "SHL_cons_charter_round": ("SHL_start_cons_charter_round", 150),
        "SHL_cons_ultimatum": ("SHL_start_cons_ultimatum", 120),
        "SHL_cons_toll_term": ("SHL_start_cons_toll_term", 150),
        "SHL_cons_councils": ("SHL_start_cons_councils", 180),
        "SHL_council_election": ("SHL_start_council_election", 180),
        "SHL_house_demand": ("SHL_start_house_demand", 45),
    }
    # decision -> (begin effect, cancel effect, treasury price, political power, manpower, target, receipt owner, receipt)
    PAID = {
        "SHL_furnace_school": ("SHL_begin_school", "SHL_cancel_operation", 100, 0, 0, "287", "287", "SHL_operation_deposit"),
        "SHL_quarter_hospital": ("SHL_begin_hospital", "SHL_cancel_operation", 120, 0, 0, "287", "287", "SHL_operation_deposit"),
        "SHL_cargo_insurance": ("SHL_begin_cargo_insurance", "SHL_cancel_cargo_insurance", 100, 0, 0, None, "SHL", "SHL_insurance_deposit"),
        "SHL_directorate_railway": ("SHL_begin_directorate_railway", "SHL_cancel_directorate_railway", 200, 0, 0, None, "SHL", "SHL_railway_deposit"),
        "SHL_regent_guard": ("SHL_begin_regent_guard", "SHL_cancel_regent_guard", 150, 0, 3000, None, "SHL", "SHL_regent_guard_deposit"),
        "SHL_shift_school": ("SHL_begin_shift_school", "SHL_cancel_shift_school", 80, 0, 0, None, "SHL", "SHL_shift_school_deposit"),
        "SHL_strike_support": ("SHL_begin_strike_support", "SHL_cancel_strike_support", 50, 20, 0, "GLP", "GLP", "SHL_strike_support_deposit"),
    }
    PRICE_DEFAULTS = {
        "SHL_guard_price": 300, "SHL_wells_price": 250, "SHL_harbour_price": 300, "SHL_export_advance": 60,
        "SHL_convoy_deposit": 120, "SHL_cauldron_repair": 30, "SHL_raid_oil_pp": 40,
    }
    PRICE_FOCUSES = {
        "SHL_guard_price": ("SHL_h_conclave_mercenaries", 225), "SHL_wells_price": ("SHL_c_water_works", 200),
        "SHL_harbour_price": ("SHL_c_harbour_works", 250), "SHL_export_advance": ("SHL_h_export_houses", 90),
        "SHL_convoy_deposit": ("SHL_d_march_logistics", 90), "SHL_cauldron_repair": ("SHL_k_cauldron_plus", 40),
        "SHL_raid_oil_pp": ("SHL_k_strikes_on_fields", 0),
    }
    HEADS = {
        "SHL_Khosrow_Arbin": "287", "SHL_Darius_Safir": "288", "SHL_Golshan_Loran": "289", "SHL_Kamran_Nur": "290",
        "SHL_Tahmuras_Bayrat": "291", "SHL_Fereydun_Kerdan": "292", "SHL_Shirin_Sharim": "293",
        "SHL_Rauf_Darban": "294", "SHL_Behruz_Veyran": "295",
    }

    def setUp(self):
        CrisisLayerTests.setUp(self)
        self.m.power_balance[BALANCE] = -0.20
        self.m.run("SHL_initialize_programmes")
        self.c = self.country()
        self.c.update({"SHL_city_support": 20, "SHL_selected_furnace": 1})

    country = CrisisLayerTests.country

    def decision(self, name):
        return decision_definition(name)

    def test_price_variables_default_to_the_old_quotes_and_follow_course_focuses(self):
        for name, default in self.PRICE_DEFAULTS.items():
            self.assertEqual(self.c[name], default, name)
        for name, (focus, discounted) in self.PRICE_FOCUSES.items():
            with self.subTest(price=name):
                self.setUp()
                self.m.focuses.add(focus)
                self.m.run("SHL_refresh_furnaces")
                self.assertEqual(self.c[name], discounted)
        self.m.focuses.add("SHL_k_workers_wells")
        self.m.run("SHL_refresh_furnaces")
        self.assertEqual(self.c["SHL_wells_price"], 0)
        self.c["SHL_water_crisis"] = 1
        self.m.run("SHL_begin_wells")
        self.assertIn("SHL_free_well_used", self.m.flags["SHL"])
        self.assertEqual(self.c["ADISCORD_economy_treasury"], 1000)
        self.m.run("SHL_refresh_furnaces")
        self.assertEqual(self.c["SHL_wells_price"], 250)
        for decision, variable in (("SHL_artesian_wells", "SHL_wells_price"), ("SHL_harbour_project", "SHL_harbour_price"),
                                   ("SHL_forge_campaign_convoy", "SHL_convoy_deposit"), ("SHL_hire_desert_guard", "SHL_guard_price")):
            self.assertIn(variable, repr(block(self.decision(decision), "custom_cost_trigger")), decision)
        # Order prices derived from the course programmes after the ending discounts.
        self.setUp()
        self.c["SHL_political_course"] = 2
        self.m.focuses.update({"SHL_c_civic_orders_plus", "SHL_d_arsenal_orders_plus", "SHL_r_pledge_plus"})
        self.m.run("SHL_refresh_furnaces")
        self.assertEqual((self.c["SHL_civic_price"], self.c["SHL_arsenal_price"], self.c["SHL_pledge_price"]), (60, 90, 150))

    def test_guard_hire_reads_the_discounted_quote_and_lifts_the_interval_only_in_the_south_war(self):
        self.m.focuses.add("SHL_h_conclave_mercenaries")
        self.m.run("SHL_refresh_furnaces")
        decision = self.decision("SHL_hire_desert_guard")
        for balance, allowed in ((224.99, False), (225, True)):
            self.c["ADISCORD_economy_treasury"] = balance
            self.assertEqual(self.m.matches(block(decision, "custom_cost_trigger"), "SHL"), allowed, balance)
        self.c["ADISCORD_economy_treasury"] = 225
        self.m.run("SHL_hire_guard")
        self.m.run("SHL_hire_guard")
        self.assertEqual(self.c["ADISCORD_economy_treasury"], 0)
        self.assertEqual(self.m.divisions, 3)
        self.assertIn("SHL_guard_hired", self.m.flags["SHL"])
        self.assertFalse(self.m.matches(block(decision, "available"), "SHL"))
        self.setUp()
        self.m.focuses.add("SHL_r_hire_armies")
        self.m.global_flags.add("ADISCORD_south_final_started")
        self.m.run("SHL_hire_guard")
        self.assertNotIn("SHL_guard_hired", self.m.flags["SHL"])
        self.assertEqual(scalar(decision, "days_re_enable"), "1")

    def test_paid_programmes_check_the_exact_boundary_and_debit_once(self):
        for name, (begin, _, price, power, manpower, target, owner, receipt) in self.PAID.items():
            for allowed in (False, True):
                with self.subTest(decision=name, allowed=allowed):
                    self.setUp()
                    self.m.focuses.update({"SHL_c_furnace_schools", "SHL_c_quarter_hospitals", "SHL_h_cargo_insurance",
                                           "SHL_d_directorate_railway", "SHL_r_regent_guard", "SHL_k_shift_school",
                                           "SHL_k_strike_support"})
                    self.c["ADISCORD_economy_treasury"] = price - (0 if allowed else 0.01)
                    self.m.values["political_power"] = power if power else 200
                    self.m.manpower = manpower if manpower else 100000
                    decision = self.decision(name)
                    self.assertEqual(scalar(decision, "cost"), "0")
                    self.assertIsNotNone(scalar(decision, "custom_cost_text"))
                    self.m.target_scope = target
                    self.assertEqual(self.m.matches(block(decision, "custom_cost_trigger"), "SHL", target), allowed)
                    self.m.run(begin, target=target)
                    self.m.run(begin, target=target)
                    expected = price - (price if allowed else 0)
                    self.assertAlmostEqual(self.c["ADISCORD_economy_treasury"], expected - (0 if allowed else 0.01))
                    self.assertEqual(receipt in self.m.variables[owner], allowed)
                    if power:
                        self.assertAlmostEqual(self.m.values["political_power"], power - (power if allowed else 0))
                    if manpower:
                        self.assertEqual(self.m.manpower, manpower - (manpower if allowed else 0))

    def test_cancellation_refunds_every_programme_once(self):
        for name, (begin, cancel, price, power, manpower, target, owner, receipt) in self.PAID.items():
            with self.subTest(decision=name):
                self.setUp()
                self.m.run(begin, target=target)
                self.assertAlmostEqual(self.c["ADISCORD_economy_treasury"], 1000 - price)
                self.m.run(cancel, target=target)
                self.m.run(cancel, target=target)
                self.assertAlmostEqual(self.c["ADISCORD_economy_treasury"], 1000)
                self.assertAlmostEqual(self.m.values["political_power"], 200)
                self.assertEqual(self.m.manpower, 100000)
                self.assertNotIn(receipt, self.m.variables[owner])
                decision = self.decision(name)
                self.assertTrue(block(decision, "cancel_trigger"), name)
                self.assertIn(cancel, repr(block(decision, "cancel_effect")), name)

    def test_lost_sites_refund_at_delivery_and_successful_delivery_pays_once(self):
        self.m.variables["287"]["SHL_furnace_training"] = 1
        self.m.run("SHL_begin_school", target="287")
        self.m.run("SHL_finish_school", target="287")
        self.m.run("SHL_finish_school", target="287")
        self.assertEqual(self.m.variables["287"]["SHL_furnace_training"], 2)
        self.assertEqual(self.c["ADISCORD_economy_treasury"], 900)
        self.assertEqual(self.c["SHL_unrest"], 23)
        self.assertFalse(self.m.matches(block(self.decision("SHL_furnace_school"), "available"), "SHL", "287"))
        self.m.run("SHL_begin_hospital", target="288")
        self.m.control["288"] = "MZR"
        self.m.run("SHL_finish_hospital", target="288")
        self.assertEqual(self.c["ADISCORD_economy_treasury"], 900)
        self.assertNotIn("SHL_quarter_hospital", self.m.flags["288"])
        self.m.control["288"] = "SHL"
        self.m.run("SHL_begin_hospital", target="288")
        self.m.run("SHL_finish_hospital", target="288")
        self.assertIn("SHL_quarter_hospital", self.m.flags["288"])
        self.assertEqual((self.c["SHL_unrest"], self.c["SHL_city_support"]), (19, 23))
        self.assertFalse(self.m.matches(block(self.decision("SHL_quarter_hospital"), "available"), "SHL", "288"))
        self.m.run("SHL_begin_directorate_railway")
        self.m.run("SHL_finish_directorate_railway")
        self.assertEqual(self.m.state_buildings[("294", "infrastructure")], 1)
        self.assertEqual(self.m.state_buildings[("699", "infrastructure")], 1)
        self.m.run("SHL_begin_regent_guard")
        self.m.run("SHL_finish_regent_guard")
        self.assertEqual(self.m.unit_owners, [("699", "SHL")])
        self.assertIn("SHL_restored_house_guard", self.m.ideas)
        self.m.run("SHL_begin_cargo_insurance")
        self.m.run("SHL_finish_cargo_insurance")
        self.assertEqual(self.m.equipment[("SHL", "convoy_1")], 5)
        self.assertEqual(self.m.idea_days["SHL_insured_cargo"], 180)
        self.assertFalse(self.m.matches(block(self.decision("SHL_cargo_insurance"), "available"), "SHL"))

    def test_quota_forces_the_arsenal_recipient_and_pays_the_extra_rifles_once(self):
        self.m.variables["287"]["SHL_furnace_recipient"] = 2
        self.m.run("SHL_begin_quota", target="287")
        self.assertEqual(self.c["SHL_unrest"], 29)
        self.m.variables["287"]["SHL_furnace_recipient"] = 2
        self.m.run("SHL_produce_period")
        self.assertEqual(self.m.variables["287"]["SHL_furnace_recipient"], 1)
        self.assertEqual(self.m.equipment[("SHL", "infantry_equipment")], 2700)
        self.assertFalse(self.m.matches(self.m.triggers["SHL_can_assign_delivery"], "SHL"))
        self.m.run("SHL_finish_quota", target="287")
        self.m.run("SHL_finish_quota", target="287")
        self.assertEqual(self.m.equipment[("SHL", "infantry_equipment")], 3300)
        self.assertNotIn("SHL_quota_site", self.m.flags["287"])
        self.assertTrue(self.m.matches(self.m.triggers["SHL_can_assign_delivery"], "SHL"))

    def test_state_concession_and_tribunal_move_ownership_once(self):
        self.m.variables["287"]["SHL_furnace_owner"] = 2
        self.m.run("SHL_grant_state_concession", target="287")
        self.m.run("SHL_grant_state_concession", target="287")
        self.assertEqual(self.m.variables["287"]["SHL_furnace_owner"], 0)
        self.assertEqual(self.c["ADISCORD_economy_treasury"], 1100)
        self.assertAlmostEqual(self.m.power_balance[BALANCE], -0.25)
        for state in ("288", "289"):
            self.m.variables[state]["SHL_furnace_owner"] = 2
        self.m.run("SHL_lease_all_state_furnaces")
        self.assertEqual(self.c["ADISCORD_economy_treasury"], 1300)
        self.assertAlmostEqual(self.m.power_balance[BALANCE], -0.30)
        self.c.update({"SHL_political_course": 4, "SHL_obligation_kind": 4, "SHL_obligation_site": 290})
        self.m.values["political_power"] = 39.99
        self.m.run("SHL_tribunal_foreclose", target="290")
        self.assertEqual(self.m.variables["290"]["SHL_furnace_owner"], 0)
        self.m.values["political_power"] = 40
        self.m.run("SHL_tribunal_foreclose", target="290")
        self.m.run("SHL_tribunal_foreclose", target="290")
        self.assertEqual(self.m.variables["290"]["SHL_furnace_owner"], 1)
        self.assertEqual(self.m.values["political_power"], 0)
        self.assertNotIn("SHL_obligation_kind", self.c)
        self.assertEqual(self.c["SHL_unrest"], 33)

    def test_brotherly_supply_moves_one_packet_and_refunds_the_donor_on_cancel(self):
        for state in range(287, 296):
            self.m.variables[str(state)]["SHL_furnace_owner"] = 1
        self.m.variables["289"]["SHL_furnace_stock"] = 0
        self.m.variables["287"]["SHL_furnace_stock"] = 1
        self.m.run("SHL_begin_brotherly_supply", target="289")
        self.m.run("SHL_begin_brotherly_supply", target="289")
        self.assertEqual(self.c["SHL_brotherly_donor"], 288)
        self.assertEqual(self.m.variables["288"]["SHL_furnace_stock"], 2)
        self.m.run("SHL_cancel_brotherly_supply", target="289")
        self.m.run("SHL_cancel_brotherly_supply", target="289")
        self.assertEqual(self.m.variables["288"]["SHL_furnace_stock"], 3)
        self.assertNotIn("SHL_brotherly_donor", self.c)
        self.m.run("SHL_begin_brotherly_supply", target="289")
        self.m.run("SHL_finish_brotherly_supply", target="289")
        self.m.run("SHL_finish_brotherly_supply", target="289")
        self.assertEqual(self.m.variables["289"]["SHL_furnace_stock"], 1)
        self.assertEqual(self.m.variables["288"]["SHL_furnace_stock"], 2)
        self.assertEqual(self.c["SHL_unrest"], 23)

    def test_shift_school_trains_the_most_worn_furnace_or_refunds(self):
        self.m.variables["291"]["SHL_furnace_wear"] = 70
        self.m.variables["293"]["SHL_furnace_wear"] = 80
        self.m.variables["293"]["SHL_furnace_training"] = 2
        self.m.run("SHL_begin_shift_school")
        self.m.run("SHL_finish_shift_school")
        self.m.run("SHL_finish_shift_school")
        self.assertEqual(self.m.variables["291"]["SHL_furnace_training"], 1)
        self.assertEqual(self.m.variables["293"]["SHL_furnace_training"], 2)
        self.assertEqual(self.c["ADISCORD_economy_treasury"], 920)
        for state in range(287, 296):
            self.m.variables[str(state)]["SHL_furnace_training"] = 2
        self.m.run("SHL_begin_shift_school")
        self.m.run("SHL_finish_shift_school")
        self.assertEqual(self.c["ADISCORD_economy_treasury"], 920)
        self.assertNotIn("SHL_pick_site", self.c)

    def test_house_credit_marks_the_debtor_and_repays_over_six_cycles(self):
        self.m.run("SHL_grant_house_credit", target="RHM")
        self.m.run("SHL_grant_house_credit", target="RHM")
        self.assertEqual(self.c["ADISCORD_economy_treasury"], 850)
        self.assertIn("ADISCORD_south_indebted_to_SHL", self.m.flags["RHM"])
        self.assertEqual(self.c["SHL_credit_cycles"], 6)
        # Nine furnaces earn 60 each per cycle; a credit cycle adds 25 on top.
        self.m.run("SHL_produce_period")
        self.assertEqual((self.c["SHL_last_cycle_income"], self.c["SHL_credit_cycles"]), (565, 5))
        self.c["SHL_credit_cycles"] = 1
        self.m.run("SHL_produce_period")
        self.assertEqual((self.c["SHL_last_cycle_income"], self.c["SHL_credit_cycles"]), (565, 0))
        self.m.run("SHL_produce_period")
        self.assertEqual(self.c["SHL_last_cycle_income"], 540)

    def test_strike_support_reaches_seventy_five_and_repeats_the_alliance_offer(self):
        for _ in range(3):
            self.m.run("SHL_begin_strike_support", target="GLP")
            self.m.run("SHL_finish_strike_support", target="GLP")
        self.assertEqual(self.m.variables["GLP"]["SHL_cons_councils_support"], 75)
        self.assertIn("SHL_cons_councils_backed", self.m.flags["GLP"])
        self.assertEqual(self.m.calls.count(("ADISCORD_south_offer_alliance", "GLP")), 1)
        self.assertEqual(self.c["ADISCORD_economy_treasury"], 850)
        self.assertEqual(self.m.values["political_power"], 140)
        self.m.run("SHL_begin_strike_support", target="GLP")
        self.m.wars.add(frozenset(("SHL", "GLP")))
        self.m.run("SHL_finish_strike_support", target="GLP")
        self.assertEqual(self.c["ADISCORD_economy_treasury"], 850)
        self.assertEqual(self.m.values["political_power"], 140)

    def test_missions_are_registered_once_and_started_only_by_their_starter(self):
        tokens = (ROOT / "common/synchronized_dynamic_tokens/ADISCORD_tokens.txt").read_text(encoding="utf-8").split()
        for name, (starter, days) in self.MISSIONS.items():
            with self.subTest(mission=name):
                decision = self.decision(name)
                self.assertEqual(tokens.count(name), 1)
                self.assertEqual(scalar(decision, "days_mission_timeout"), str(days))
                self.assertEqual(scalar(block(decision, "activation"), "always"), "no")
                self.assertEqual(scalar(decision, "selectable_mission"), "no")
                self.assertNotIn(name, self.m.missions)
                self.m.run(starter)
                self.m.run(starter)
                self.assertIn(name, self.m.missions)
                if name == "SHL_council_election":
                    available = block(decision, "available")
                    self.assertEqual([(e.key, [(c.key, c.value) for c in e.value]) for e in available],
                                     [("hidden_trigger", [("always", "no")])])
        for name in ("SHL_cons_debt_term", "SHL_cons_toll_term", "SHL_cons_ultimatum"):
            self.setUp()
            self.m.execute(block(self.decision(name), "timeout_effect"), "SHL")
            demands = [call for call in self.m.calls if call[0] == "ADISCORD_south_demand_annexation"]
            self.assertEqual(len(demands), 2, name)
        self.setUp()
        self.m.factions.update({"SHL": "SHL", "RHM": "SHL", "SDR": "SHL"})
        self.assertTrue(self.m.matches(block(self.decision("SHL_cons_debt_term"), "available"), "SHL"))
        self.assertTrue(self.m.matches(block(self.decision("SHL_cons_charter_round"), "available"), "SHL"))
        self.m.factions.pop("SDR")
        self.assertFalse(self.m.matches(block(self.decision("SHL_cons_charter_round"), "available"), "SHL"))
        self.m.countries["SDR"]["subject_of"] = "SHL"
        self.assertTrue(self.m.matches(block(self.decision("SHL_cons_debt_term"), "available"), "SHL"))

    def test_council_election_counts_support_and_schedules_the_next_one(self):
        self.c["SHL_city_support"] = 40
        self.m.run("SHL_hold_council_election")
        self.assertEqual(self.m.values["political_power"], 250)
        self.assertAlmostEqual(self.m.power_balance[BALANCE], -0.17)
        self.assertIn("SHL_council_election", self.m.missions)
        self.c["SHL_city_support"] = 39
        self.m.run("SHL_hold_council_election")
        self.assertAlmostEqual(self.m.power_balance[BALANCE], -0.22)
        self.assertEqual(self.c["SHL_unrest"], 30)

    def test_house_demand_fires_every_fourth_cycle_only_after_ratification_and_marks_the_worst_house(self):
        for state, wear in (("289", 70), ("291", 85), ("295", 90)):
            self.m.variables[state]["SHL_furnace_wear"] = wear
        self.m.variables["295"]["SHL_furnace_owner"] = 1
        for _ in range(8):
            self.m.run("SHL_update_tensions")
        self.assertNotIn("ADISCORD_SHL.140", self.m.scheduled)
        self.c["SHL_political_course"] = 1
        for _ in range(3):
            self.m.run("SHL_update_tensions")
        self.assertNotIn("ADISCORD_SHL.140", self.m.scheduled)
        self.m.run("SHL_update_tensions")
        self.assertEqual(self.m.scheduled.count("ADISCORD_SHL.140"), 1)
        self.assertEqual((self.c["SHL_demand_site"], self.c["SHL_demand_wear"]), (291, 85))
        self.assertIn("SHL_demand_pending", self.m.flags["SHL"])
        for _ in range(4):
            self.m.run("SHL_update_tensions")
        self.assertEqual(self.m.scheduled.count("ADISCORD_SHL.140"), 1)
        self.m.run("SHL_house_demand_pay")
        self.assertEqual(self.c["ADISCORD_economy_treasury"], 900)
        self.assertNotIn("SHL_demand_pending", self.m.flags["SHL"])
        self.assertEqual(self.c["SHL_demand_site"], 0)
        # The city course asks on behalf of the quarter with the worst city furnace.
        self.c["SHL_political_course"] = 2
        for _ in range(4):
            self.m.run("SHL_update_tensions")
        self.assertEqual(self.m.scheduled.count("ADISCORD_SHL.140"), 2)
        self.assertEqual(self.c["SHL_demand_site"], 295)
        self.m.run("SHL_house_demand_yield")
        self.assertAlmostEqual(self.m.power_balance[BALANCE], -0.15)

    def test_refused_demand_runs_the_mission_and_the_opposed_house_loses_its_seat(self):
        self.c["SHL_political_course"] = 1
        self.m.variables["291"]["SHL_furnace_wear"] = 85
        self.m.run("SHL_pick_demand_site")
        self.m.flags["SHL"].add("SHL_demand_pending")
        self.m.run("SHL_house_demand_refuse")
        self.assertEqual(self.c["SHL_house_pressure"], 35)
        self.assertIn("SHL_house_demand", self.m.missions)
        self.assertNotIn("SHL_demand_pending", self.m.flags["SHL"])
        goal = block(self.decision("SHL_house_demand"), "available")
        self.assertFalse(self.m.matches(goal, "SHL"))
        self.m.variables["291"]["SHL_furnace_wear"] = 39
        self.assertTrue(self.m.matches(goal, "SHL"))
        self.m.variables["291"]["SHL_furnace_wear"] = 85
        self.m.execute(block(self.decision("SHL_house_demand"), "timeout_effect"), "SHL")
        self.assertIn("SHL_house_opposed", self.m.flags["291"])
        self.assertEqual(self.c["SHL_house_pressure"], 45)
        self.assertEqual(self.c["SHL_demand_site"], 0)
        timeout = next(e for e in walk_entries(self.m.effects["SHL_mark_site_opposed"]) if e.key == "set_state_flag")
        self.assertEqual(scalar(timeout.value, "days"), "180")
        characters = block(parse_clausewitz((ROOT / "common/characters/SHL.txt").read_text(encoding="utf-8")), "characters")
        for head, state in self.HEADS.items():
            with self.subTest(head=head):
                advisor = block(next(e.value for e in characters if e.key == head), "advisor")
                available = block(advisor, "available")
                self.m.flags[state].discard("SHL_house_opposed")
                self.m.leader = "SHL_Jalil_Nur"
                self.assertTrue(self.m.matches(available, "SHL"))
                self.m.flags[state].add("SHL_house_opposed")
                self.assertFalse(self.m.matches(available, "SHL"))
        # An opposed house is not asked again while its seat is closed.
        self.c["SHL_demand_cycle"] = 3
        self.m.run("SHL_update_tensions")
        self.assertNotEqual(self.c["SHL_demand_site"], 291)

    def test_export_mode_prices_exported_metal_between_45_and_75_and_the_cartel_keeps_60(self):
        self.m.run("SHL_produce_period")
        self.assertEqual(self.c["SHL_last_cycle_income"], 540)
        self.assertEqual(self.c["SHL_exchange_price"], 60)
        branches = [c for c in next(e.value for e in self.m.effects["SHL_roll_exchange_price"] if e.key == "random_list")]
        quotes = [float(scalar(block(b.value, "set_variable"), "value")) for b in branches]
        self.assertEqual((min(quotes), max(quotes)), (45, 75))
        self.m.run("SHL_commit_metal_exchange")
        self.assertEqual(self.c["SHL_export_mode"], 1)
        self.m.variables["287"]["SHL_furnace_recipient"] = 1
        self.m.run("SHL_produce_period")
        self.assertEqual(self.c["SHL_exchange_price"], 45)
        self.assertEqual(self.c["SHL_last_cycle_income"], 8 * 45)
        self.m.run("SHL_toggle_export_mode")
        self.assertEqual((self.c["SHL_export_mode"], self.c["SHL_exchange_price"]), (0, 60))
        self.m.run("SHL_produce_period")
        self.assertEqual(self.c["SHL_last_cycle_income"], 8 * 60)

    def test_no_crests_stops_pressure_growth_and_open_ledger_skips_corruption_draws(self):
        self.c["SHL_house_votes"] = 9
        self.m.run("SHL_update_tensions")
        self.assertEqual(self.c["SHL_house_pressure"], 25)
        self.m.flags["SHL"].add("SHL_no_crests")
        self.c["SHL_house_pressure"] = 0
        self.m.run("SHL_update_tensions")
        self.m.run("SHL_update_tensions")
        self.assertEqual(self.c["SHL_house_pressure"], 0)
        draw = self.m.effects["SHL_crisis_draw"]
        guarded = [
            e for e in walk_entries(draw)
            if e.key == "modifier" and ("has_country_flag", "SHL_open_ledger") in [(c.key, c.value) for c in e.value]
        ]
        self.assertEqual(len(guarded), 2)
        text = repr(draw)
        self.assertLess(text.index("SHL_open_ledger"), text.index("ADISCORD_shl_crisis.4"))
        self.assertGreater(text.rindex("SHL_open_ledger"), text.index("ADISCORD_shl_crisis.4"))
        self.assertLess(text.rindex("SHL_open_ledger"), text.index("ADISCORD_shl_crisis.5"))

    def test_neighbour_revanche_is_scheduled_a_year_after_victory_and_the_revision_buys_the_claim_once(self):
        self.c["SHL_water_crisis"] = 1
        self.m.focuses.add("SHL_qanat_guard")
        self.m.run("SHL_start_kyz_war")
        self.m.run("SHL_kyz_war_victory")
        self.assertEqual(self.m.event_days["ADISCORD_SHL.76"], 365)
        self.assertIn("SHL_revanche_due_KYZ", self.m.flags["SHL"])
        self.assertFalse(self.m.matches(self.m.triggers["SHL_revanche_ready"], "SHL"))
        self.m.flag_days["SHL"]["SHL_revanche_due_KYZ"] = 365
        self.assertTrue(self.m.matches(self.m.triggers["SHL_revanche_ready"], "SHL"))
        self.m.factions.update({"SHL": "SHL", "KYZ": "SHL"})
        self.assertFalse(self.m.matches(self.m.triggers["SHL_revanche_ready"], "SHL"))
        self.m.factions.clear()
        self.m.run("SHL_resolve_revanche")
        self.assertEqual(self.c["SHL_revanche_neighbour"], 1)
        self.assertNotIn("SHL_revanche_due_KYZ", self.m.flags["SHL"])
        self.assertEqual(sorted(call[1] for call in self.m.calls if call[0] == "add_claim_by"), ["280", "284", "285", "286"])
        self.c["ADISCORD_economy_treasury"] = 149.99
        self.m.run("SHL_revanche_revision")
        self.assertEqual(self.c["SHL_revanche_neighbour"], 1)
        self.c["ADISCORD_economy_treasury"] = 150
        self.m.run("SHL_revanche_revision")
        self.m.run("SHL_revanche_revision")
        self.assertEqual(self.c["ADISCORD_economy_treasury"], 0)
        self.assertEqual(sorted(call[1] for call in self.m.calls if call[0] == "remove_claim_by"), ["280", "284", "285", "286"])
        self.assertEqual(self.c["SHL_revanche_neighbour"], 0)
        for effect in ("SHL_glp_war_victory", "SHL_mzr_war_victory"):
            self.assertIn("ADISCORD_SHL.76", repr(self.m.effects[effect]), effect)

    def test_integration_annexes_only_satellites_and_each_course_settles_its_own_way(self):
        for tag in ("KDR", "GLP", "RHM"):
            self.m.countries[tag]["subject_of"] = "SHL"
        self.m.run("SHL_annex_integration_houses")
        annexed = sorted(call[2] for call in self.m.calls if call[0] == "annex_country")
        self.assertEqual(annexed, ["GLP", "KDR", "RHM"])
        self.assertEqual(self.c["ADISCORD_economy_treasury"], 550)
        self.assertNotIn("SHL_integration_price", self.c)
        self.setUp()
        self.m.countries["KDR"]["subject_of"] = "SHL"
        self.m.countries["GLP"]["subject_of"] = "SHL"
        self.m.focuses.update({"SHL_r_kadir_junior", "SHL_h_veyr_junior_partner"})
        self.m.run("SHL_annex_integration_regency")
        self.assertEqual([call for call in self.m.calls if call[0] == "annex_country"], [])
        self.m.focuses.clear()
        self.m.run("SHL_annex_integration_regency")
        self.assertEqual(sorted(call[2] for call in self.m.calls if call[0] == "annex_country"), ["GLP", "KDR"])
        self.assertEqual((self.c["ADISCORD_economy_treasury"], self.c["ADISCORD_economy_debt"]), (1200, 400))
        self.setUp()
        self.m.countries["MZR"]["subject_of"] = "SHL"
        self.m.run("SHL_annex_integration_commune")
        self.assertEqual((self.c["SHL_unrest"], self.c["SHL_city_support"]), (15, 25))
        self.setUp()
        self.m.run("SHL_annex_integration_directorate")
        self.assertNotIn("SHL_general_governorate", self.m.ideas)
        self.m.countries["KYZ"]["subject_of"] = "SHL"
        self.m.run("SHL_annex_integration_directorate")
        self.assertEqual(self.m.idea_days["SHL_general_governorate"], 365)

    def test_sell_stations_pays_once_and_returns_the_stations_to_an_existing_kadir(self):
        self.m.ownership.update({"234": "SHL", "240": "SHL"})
        self.m.control.update({"234": "SHL", "240": "SHL"})
        self.m.run("SHL_sell_road_stations")
        self.m.run("SHL_sell_road_stations")
        self.assertEqual(self.c["ADISCORD_economy_treasury"], 1150)
        self.assertEqual((self.m.ownership["234"], self.m.control["240"]), ("KDR", "KDR"))
        self.assertEqual(scalar(self.decision("SHL_sell_stations"), "fire_only_once"), "yes")

    def test_concession_sales_keep_their_interval_outside_the_south_war(self):
        self.m.run("SHL_sell_crest_concessions")
        self.m.run("SHL_sell_crest_concessions")
        self.assertEqual((self.c["ADISCORD_economy_treasury"], self.c["ADISCORD_economy_debt"]), (1300, 500))
        self.assertIn("SHL_concessions_sold", self.m.flags["SHL"])
        self.setUp()
        self.m.focuses.add("SHL_r_sell_future")
        self.m.global_flags.add("ADISCORD_south_final_started")
        self.m.run("SHL_sell_crest_concessions")
        self.assertNotIn("SHL_concessions_sold", self.m.flags["SHL"])

    def test_demand_sent_while_nam_story_is_pending_is_queued_not_dropped(self):
        self.m.effects.update(shared_definitions(
            "common/scripted_effects/ADISCORD_south_final_war_effects.txt",
            ("ADISCORD_south_demand_submission", "ADISCORD_south_queue_offer"),
        ))
        self.m.triggers["NAM_south_story_pending"] = parse_clausewitz("always = yes")
        self.assertFalse(self.m.matches(self.m.triggers["ADISCORD_south_nam_story_clear"], "SHL"))
        self.m.run("ADISCORD_south_demand_submission", scope="RHM")
        self.assertEqual(self.m.variables["RHM"]["ADISCORD_south_offer_kind"], 1)
        self.assertEqual(self.m.scheduled, ["ADISCORD_south.46"])
        self.assertNotIn("ADISCORD_south_nam_story_clear", repr(self.m.triggers["ADISCORD_south_campaign_target_valid"]))
        events = (ROOT / "events/ADISCORD_south_final_war_events.txt").read_text(encoding="utf-8")
        dispatcher = events[events.index("id = ADISCORD_south.46"):]
        self.assertIn("ADISCORD_south_nam_story_clear", dispatcher[:dispatcher.index("}\n}")])

    def test_cistern_charter_opens_before_the_war_only_through_the_city_focus(self):
        self.c["SHL_political_course"] = 2
        self.m.focuses.add("SHL_council_of_cities")
        self.assertFalse(self.m.matches(self.m.triggers["SHL_can_offer_cistern_charter"], "SHL"))
        self.m.focuses.add("SHL_c_cistern_charter")
        self.assertTrue(self.m.matches(self.m.triggers["SHL_can_offer_cistern_charter"], "SHL"))
        self.m.run("SHL_request_cistern_charter")
        self.c["SHL_mazar_state"] = 1
        self.m.missions.add("SHL_mazar_deadline")
        self.m.run("SHL_accept_cistern_charter", scope="MZR")
        self.assertEqual(self.m.factions.get("MZR"), "SHL")
        self.assertEqual((self.c["SHL_mzr_outcome"], self.c["SHL_mazar_state"]), (3, 3))
        self.assertNotIn("SHL_mazar_deadline", self.m.missions)
        self.assertFalse(self.m.matches(self.m.triggers["SHL_can_offer_cistern_charter"], "SHL"))


class ExternalContractTests(unittest.TestCase):
    """Packet price under Svetlogorye's oil policy and the metal contracts of the Golden Gates."""

    BUYERS = ("VAL", "STP", "STS", "RUS", "GLP", "NAM")
    PRICES = {None: 25, "NAM_oil_client": 20, "NAM_fuel_embargo_modifier": 35}

    @staticmethod
    def flatten_modifier_removal(entries):
        """Give remove_dynamic_modifier blocks the scalar shape the machine discards."""
        for entry in entries:
            if entry.key == "remove_dynamic_modifier" and isinstance(entry.value, list):
                entry.value = scalar(entry.value, "modifier")
            elif isinstance(entry.value, list):
                ExternalContractTests.flatten_modifier_removal(entry.value)

    def setUp(self):
        from unittest import mock
        # The contract buyers beyond the regional set must be addressable scopes.
        patcher = mock.patch(f"{__name__}.REGIONAL", REGIONAL + ("VAL", "STP", "STS", "RUS"))
        patcher.start()
        self.addCleanup(patcher.stop)
        effects = parse_clausewitz(EFFECT_PATH.read_text(encoding="utf-8"))
        self.flatten_modifier_removal(effects)
        self.effects = {e.key: e.value for e in effects}
        self.m = ScriptMachine(effects, parse_clausewitz(TRIGGER_PATH.read_text(encoding="utf-8")))
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
        self.m.run("SHL_initialize_programmes")
        self.m.run("SHL_refresh_furnaces")
        self.c = self.m.variables["SHL"]
        for tag in self.BUYERS:
            self.m.variables[tag]["ADISCORD_economy_treasury"] = 500.0

    def price_marker(self, marker):
        if marker == "NAM_oil_client":
            self.m.flags["SHL"].add(marker)
        elif marker:
            self.m.dynamic.add(marker)

    def sign(self, tag):
        self.m.flags[tag].add("SHL_metal_offer_pending")
        self.m.run("SHL_metal_sign_contract", scope=tag)

    def dirty_calls(self):
        return self.m.calls.count("ADISCORD_economy_mark_dirty")

    def test_packet_price_follows_svetlogorye_contract_and_embargo(self):
        self.assertEqual(self.c["SHL_packet_price"], 25)
        for marker, price in self.PRICES.items():
            with self.subTest(marker=marker):
                self.setUp()
                self.price_marker(marker)
                self.m.run("SHL_refresh_furnaces")
                self.assertEqual(self.c["SHL_packet_price"], price)
        # The embargo quote wins while both markers are present.
        self.m.flags["SHL"].add("NAM_oil_client")
        self.m.dynamic.add("NAM_fuel_embargo_modifier")
        self.m.run("SHL_refresh_furnaces")
        self.assertEqual(self.c["SHL_packet_price"], 35)
        self.m.dynamic.clear()
        self.m.flags["SHL"].discard("NAM_oil_client")
        self.m.run("SHL_refresh_furnaces")
        self.assertEqual(self.c["SHL_packet_price"], 25)
        # Every consumer reads the variable; no literal packet quote remains.
        source = EFFECT_PATH.read_text(encoding="utf-8")
        self.assertNotIn("value = 25 }", repr(self.effects["SHL_produce_site"]))
        self.assertEqual(source.count("multiply_variable = { var = SHL_planned_price value = PREV.SHL_packet_price }"), 1)
        self.assertEqual(source.count("multiply_variable = { var = SHL_tenth_planned_price value = SHL_packet_price }"), 1)
        decision = decision_definition("SHL_supply_furnace")
        self.assertEqual(scalar(decision, "custom_cost_text"), "SHL_cost_packet")
        self.assertIn("SHL_packet_price", repr(block(decision, "custom_cost_trigger")))
        self.assertIn("SHL_packet_price", repr(block(decision, "available")))

    def test_supply_debits_the_current_price_exactly_once_at_the_boundary(self):
        decision = decision_definition("SHL_supply_furnace")
        for marker, price in self.PRICES.items():
            with self.subTest(marker=marker):
                self.setUp()
                self.price_marker(marker)
                self.m.run("SHL_refresh_furnaces")
                self.m.variables["287"]["SHL_furnace_stock"] = 2
                self.c["ADISCORD_economy_treasury"] = price - 0.01
                self.assertFalse(self.m.matches(block(decision, "custom_cost_trigger"), "SHL", "287"))
                self.assertFalse(self.m.matches(block(decision, "available"), "SHL", "287"))
                self.m.run("SHL_begin_supply", target="287")
                self.assertAlmostEqual(self.c["ADISCORD_economy_treasury"], price - 0.01)
                self.assertNotIn("SHL_operation_deposit", self.m.variables["287"])
                self.c["ADISCORD_economy_treasury"] = price
                self.assertTrue(self.m.matches(block(decision, "custom_cost_trigger"), "SHL", "287"))
                self.assertTrue(self.m.matches(block(decision, "available"), "SHL", "287"))
                self.m.run("SHL_begin_supply", target="287")
                self.m.run("SHL_begin_supply", target="287")
                self.assertEqual(self.c["ADISCORD_economy_treasury"], 0)
                self.assertEqual(self.m.variables["287"]["SHL_operation_deposit"], price)
                self.m.run("SHL_cancel_operation", target="287")
                self.assertEqual(self.c["ADISCORD_economy_treasury"], price)
        # A contract signed since the last refresh prices the purchase itself.
        self.setUp()
        self.m.variables["287"]["SHL_furnace_stock"] = 2
        self.m.flags["SHL"].add("NAM_oil_client")
        self.assertEqual(self.c["SHL_packet_price"], 25)
        self.c["ADISCORD_economy_treasury"] = 20
        self.m.run("SHL_begin_supply", target="287")
        self.assertEqual(self.c["SHL_packet_price"], 20)
        self.assertEqual(self.c["ADISCORD_economy_treasury"], 0)
        self.assertEqual(self.m.variables["287"]["SHL_operation_deposit"], 20)
        # The planned supply of the cycle buys at the same quote.
        for marker, price in self.PRICES.items():
            with self.subTest(planned=marker):
                self.setUp()
                self.price_marker(marker)
                self.c["SHL_regular_supply"] = 1
                self.m.variables["287"]["SHL_furnace_stock"] = 0
                self.m.run("SHL_produce_period")
                self.assertEqual(self.c["SHL_packet_price"], price)
                self.assertEqual(self.c["ADISCORD_economy_treasury"], 1540 - price)
                self.assertEqual(self.m.variables["287"]["SHL_furnace_stock"], 0)

    def test_offer_sets_the_pending_flag_and_schedules_the_answer_once(self):
        decision = decision_definition("SHL_metal_contract_offer")
        self.assertEqual(scalar(decision, "cost"), "0")
        self.assertEqual([e.value for e in block(decision, "targets") if not e.key], list(self.BUYERS))
        self.assertTrue(self.m.matches(block(decision, "target_trigger"), "SHL", "VAL"))
        self.assertTrue(self.m.matches(block(decision, "available"), "SHL", "VAL"))
        self.m.execute(block(decision, "complete_effect"), "SHL", "VAL")
        self.assertIn("SHL_metal_offer_pending", self.m.flags["VAL"])
        self.assertIn(("ADISCORD_release_non_participating_minor_optimization", "VAL"), self.m.calls)
        self.assertEqual(self.m.scheduled.count("ADISCORD_SHL.130"), 1)
        self.assertFalse(self.m.matches(block(decision, "target_trigger"), "SHL", "VAL"))
        self.assertTrue(self.m.matches(block(decision, "target_trigger"), "SHL", "STP"))
        self.m.wars.add(frozenset(("STP", "SHL")))
        self.assertFalse(self.m.matches(block(decision, "target_trigger"), "SHL", "STP"))
        self.m.flags["RUS"].add("SHL_metal_client")
        self.assertFalse(self.m.matches(block(decision, "target_trigger"), "SHL", "RUS"))
        self.c["SHL_metal_clients"] = 3
        self.assertFalse(self.m.matches(block(decision, "available"), "SHL", "GLP"))
        self.c["SHL_metal_clients"] = 0
        for state in range(287, 296):
            self.m.variables[str(state)]["SHL_furnace_recipient"] = 1
        self.assertFalse(self.m.matches(block(decision, "available"), "SHL", "GLP"))
        self.m.variables["291"]["SHL_furnace_recipient"] = 0
        self.assertTrue(self.m.matches(block(decision, "available"), "SHL", "GLP"))
        self.c["SHL_obligation_site"] = 291
        self.assertFalse(self.m.matches(block(decision, "available"), "SHL", "GLP"))

    def test_signing_rechecks_war_and_a_free_export_furnace(self):
        self.m.wars.add(frozenset(("VAL", "SHL")))
        self.sign("VAL")
        self.assertNotIn("SHL_metal_offer_pending", self.m.flags["VAL"])
        self.assertNotIn("SHL_metal_client", self.m.flags["VAL"])
        self.assertIn("SHL_metal_offer_lapsed", self.m.flags["VAL"])
        self.assertEqual(self.m.scheduled, ["ADISCORD_SHL.132"])
        self.assertEqual(self.c["SHL_metal_clients"], 0)
        self.setUp()
        for state in range(287, 296):
            self.m.variables[str(state)]["SHL_furnace_recipient"] = 2
        self.sign("VAL")
        self.assertNotIn("SHL_metal_client", self.m.flags["VAL"])
        self.assertEqual(self.m.scheduled, ["ADISCORD_SHL.132"])
        self.setUp()
        self.sign("VAL")
        self.assertNotIn("SHL_metal_offer_pending", self.m.flags["VAL"])
        self.assertIn("SHL_metal_client", self.m.flags["VAL"])
        self.assertIn("SHL_metal_supply", self.m.dynamic)
        self.assertEqual(self.m.variables["VAL"]["SHL_metal_arrears"], 0)
        self.assertEqual(self.c["SHL_metal_clients"], 1)
        self.assertEqual(self.m.scheduled, ["ADISCORD_SHL.131"])
        # A repeated answer cannot count the same buyer twice.
        self.sign("VAL")
        self.assertEqual(self.c["SHL_metal_clients"], 1)
        self.assertEqual(self.m.scheduled, ["ADISCORD_SHL.131", "ADISCORD_SHL.132"])
        self.m.flags["STP"].add("SHL_metal_offer_pending")
        self.m.run("SHL_metal_decline_contract", scope="STP")
        self.assertNotIn("SHL_metal_offer_pending", self.m.flags["STP"])
        self.assertEqual(self.m.scheduled[-1], "ADISCORD_SHL.132")
        self.assertEqual(self.c["SHL_metal_clients"], 1)

    def test_cycle_settlement_moves_sixty_each_way_and_marks_both_economies_dirty(self):
        settle = self.effects["SHL_metal_settle_clients"]
        self.assertEqual([e.key for e in settle], list(self.BUYERS))
        self.assertNotIn("every_country", repr(settle))
        self.sign("VAL")
        before = self.dirty_calls()
        self.m.run("SHL_produce_period")
        self.assertEqual(self.m.variables["VAL"]["ADISCORD_economy_treasury"], 440)
        self.assertEqual(self.m.variables["VAL"]["ADISCORD_economy_current_month_action_costs"], 60)
        self.assertEqual(self.c["ADISCORD_economy_treasury"], 1600)
        self.assertEqual(self.c["ADISCORD_economy_current_month_action_income"], 60)
        self.assertEqual(self.c["SHL_last_cycle_income"], 600)
        self.assertEqual(self.dirty_calls() - before, 2)
        self.assertIn("SHL_metal_client", self.m.flags["VAL"])
        self.assertEqual(self.m.variables["VAL"]["SHL_metal_arrears"], 0)
        # A buyer without a contract is never touched.
        self.assertEqual(self.m.variables["STP"]["ADISCORD_economy_treasury"], 500)

    def test_two_unpaid_cycles_or_a_war_end_the_contract_and_remove_the_modifier(self):
        self.sign("VAL")
        self.m.variables["VAL"]["ADISCORD_economy_treasury"] = 59.99
        self.m.run("SHL_produce_period")
        self.assertEqual(self.m.variables["VAL"]["SHL_metal_arrears"], 1)
        self.assertIn("SHL_metal_client", self.m.flags["VAL"])
        self.assertEqual(self.m.variables["VAL"]["ADISCORD_economy_treasury"], 59.99)
        self.assertEqual(self.c["ADISCORD_economy_treasury"], 1540)
        # One paid cycle clears the arrears again.
        self.m.variables["VAL"]["ADISCORD_economy_treasury"] = 60
        self.m.run("SHL_produce_period")
        self.assertEqual(self.m.variables["VAL"]["ADISCORD_economy_treasury"], 0)
        self.assertEqual(self.m.variables["VAL"]["SHL_metal_arrears"], 0)
        self.m.run("SHL_produce_period")
        self.assertEqual(self.m.variables["VAL"]["SHL_metal_arrears"], 1)
        self.assertNotIn("ADISCORD_SHL.133", self.m.scheduled)
        self.m.run("SHL_produce_period")
        self.assertNotIn("SHL_metal_client", self.m.flags["VAL"])
        self.assertNotIn("SHL_metal_arrears", self.m.variables["VAL"])
        self.assertNotIn("SHL_metal_supply", self.m.dynamic)
        self.assertEqual(self.c["SHL_metal_clients"], 0)
        self.assertEqual(self.m.scheduled.count("ADISCORD_SHL.133"), 1)
        self.m.run("SHL_produce_period")
        self.assertEqual(self.m.scheduled.count("ADISCORD_SHL.133"), 1)
        self.setUp()
        self.sign("GLP")
        self.m.wars.add(frozenset(("GLP", "SHL")))
        self.m.run("SHL_produce_period")
        self.assertNotIn("SHL_metal_client", self.m.flags["GLP"])
        self.assertNotIn("SHL_metal_supply", self.m.dynamic)
        self.assertEqual(self.m.variables["GLP"]["ADISCORD_economy_treasury"], 500)
        self.assertEqual(self.c["SHL_metal_clients"], 0)
        self.assertEqual(self.m.scheduled[-1], "ADISCORD_SHL.133")

    def test_annexation_and_the_end_decision_clear_clients_without_a_report(self):
        self.sign("VAL")
        self.sign("GLP")
        self.assertEqual(self.c["SHL_metal_clients"], 2)
        self.m.run("SHL_abort_annexed_operations")
        for tag in ("VAL", "GLP"):
            self.assertNotIn("SHL_metal_client", self.m.flags[tag])
            self.assertNotIn("SHL_metal_arrears", self.m.variables[tag])
        self.assertNotIn("SHL_metal_supply", self.m.dynamic)
        self.assertEqual(self.c["SHL_metal_clients"], 0)
        self.assertNotIn("ADISCORD_SHL.133", self.m.scheduled)
        self.setUp()
        self.sign("RUS")
        decision = decision_definition("SHL_metal_contract_end")
        self.assertTrue(self.m.matches(block(decision, "target_trigger"), "SHL", "RUS"))
        self.assertFalse(self.m.matches(block(decision, "target_trigger"), "SHL", "VAL"))
        self.m.execute(block(decision, "complete_effect"), "SHL", "RUS")
        self.m.execute(block(decision, "complete_effect"), "SHL", "RUS")
        self.assertNotIn("SHL_metal_client", self.m.flags["RUS"])
        self.assertNotIn("SHL_metal_supply", self.m.dynamic)
        self.assertEqual(self.c["SHL_metal_clients"], 0)
        self.assertNotIn("ADISCORD_SHL.133", self.m.scheduled)
        modifier = shared_definitions("common/dynamic_modifiers/ADISCORD_dynamic_modifiers_SHL.txt", ("SHL_metal_supply",))["SHL_metal_supply"]
        self.assertEqual(scalar(modifier, "production_factory_efficiency_gain_factor"), "0.02")
        self.assertIn("SHL_metal_client", repr(block(modifier, "enable")))
        self.assertIn("country_exists", repr(block(modifier, "remove_trigger")))

    def test_every_new_key_is_localised_in_both_languages(self):
        CrisisLayerTests.test_every_crisis_event_and_decision_key_is_localised(self)
        scripted = (ROOT / "common/scripted_localisation/ADISCORD_SHL_scripted_loc.txt").read_text(encoding="utf-8")
        keys = set(re.findall(r"localization_key = (SHL_price_packet\w*|SHL_packet_price_\w+)", scripted))
        keys |= {
            "SHL_metal_contract_offer", "SHL_metal_contract_offer_desc", "SHL_metal_contract_end",
            "SHL_metal_contract_end_desc", "SHL_metal_supply", "SHL_metal_supply_desc",
            "SHL_cost_packet", "SHL_cost_packet_blocked", "SHL_cost_packet_tooltip",
            "ADISCORD_SHL.132.d_lapsed", "ADISCORD_SHL.133.d_war",
        }
        self.assertIn("SHL_packet_price_embargo", keys)
        for language in ("russian", "english"):
            path = ROOT / f"localisation/{language}/ADISCORD_SHL_l_{language}.yml"
            raw = path.read_bytes()
            self.assertTrue(raw.startswith(b"\xef\xbb\xbf"), language)
            self.assertNotIn(b"\r\n", raw, language)
            text = raw.decode("utf-8-sig")
            defined = dict(re.findall(r"^ ([\w.]+): \"(.*)\"$", text, re.M))
            self.assertEqual(sorted(keys - set(defined)), [], language)
            self.assertNotRegex(text, r"SHLGetPrice25\b", language)
            for number in (130, 131, 132, 133):
                for suffix in ("d", "d_lapsed", "d_war"):
                    key = f"ADISCORD_SHL.{number}.{suffix}"
                    if key in defined:
                        self.assertTrue(400 <= len(defined[key]) <= 800, (key, len(defined[key])))
                        self.assertNotRegex(defined[key], "[–—«»]", key)
        self.assertNotRegex(scripted, r"SHLGetPrice25\b")


if __name__ == "__main__":
    unittest.main()
