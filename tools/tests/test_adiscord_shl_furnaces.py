"""Execute bounded SHL accounting scripts; native loader/UI still need game QA."""

import unittest
import re
from collections import defaultdict
from copy import deepcopy
from functools import lru_cache
from itertools import product
from pathlib import Path
from unittest.mock import patch

from tools.builders import build_adiscord_focus_trees as focus_builder
from tools.validators.validate_adiscord_division_templates import parse_clausewitz

ROOT =Path(__file__).resolve().parents[2]
NEIGHBOURS = ("KYZ", "GLP", "MZR")
# Regional countries that SHL scripts address directly (consolidation targets,
# satellites and the northern leader).
REGIONAL = NEIGHBOURS + ("RHM", "SDR", "KDR", "NAM", "EFL", "AZH", "WEF")
NEIGHBOUR_STATES = {
    "KYZ": (280, 284, 285, 286),
    "GLP": (297, 298, 299, 708),
    "MZR": (268, 269, 275),
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
    for name in ("main", "houses", "cities", "directorate", "regency", "commune", "defeated")
}
SHARED_FOCUS_SOURCE = ROOT / "focus_trees/SHL/shared/focuses.txt"
WAR_TREE_SOURCE = ROOT / "focus_trees/SHL/south_war/focuses.txt"
FOCUS_OUTPUTS = {
    "main": "ADISCORD_SHL_focus.txt",
    "shared": "ADISCORD_SHL_shared.txt",
}
# Course sections of the single tree; each root follows its commit focus.
COURSE_TREES = {"houses": 1, "cities": 2, "directorate": 3, "regency": 4, "commune": 5}
COURSE_COMMIT_FOCUSES = {
    "houses": "SHL_admit_tenth_house",
    "cities": "SHL_rights_without_fire",
    "directorate": "SHL_state_furnaces",
    "regency": "SHL_regency_of_crests",
    "commune": "SHL_commune_of_shift_councils",
}
SOUTHERN_SHARED = ("SHL_south_crown_of_the_south",)
# The common front of the separate war-for-the-South tree; course plans queue it whole.
SOUTHERN_WAR_FRONT = (
    "SHL_south_desert_convoys", "SHL_south_furnaces_to_front",
    "SHL_south_raid_oil_fields", "SHL_south_storm_oil_belt",
)
# commit effect suffix -> (course tree, cosmetic tag)
COURSE_COMMITS = {
    "house": ("houses", "SHL_conclave_of_ten"),
    "city": ("cities", "SHL_southern_compact"),
    "state": ("directorate", "SHL_iron_directorate"),
    "regency": ("regency", "SHL_hereditary_republic"),
    "commune": ("commune", "SHL_commune_of_fire"),
}
# Exclusive pairs of the main trunk and the prerequisite block where each pair rejoins.
MAIN_PAIRS = (
    ("SHL_baryat_mines", "SHL_metal_brokers"),
    ("SHL_quarter_listening", "SHL_heralds_table"),
    ("SHL_mobilise_furnaces", "SHL_desert_guard_contracts"),
)
MAIN_REJOINS = {
    "SHL_smelter_quarters": {"SHL_ore_prospecting", "SHL_metal_brokers"},
    "SHL_incident_office": {"SHL_shift_arbitration", "SHL_counting_chamber"},
    "SHL_conclave_army": {"SHL_mobilise_furnaces", "SHL_desert_guard_contracts"},
}
# Limited border wars: one battery focus, an exclusive pair and its merge.
BORDER_WAR_LAYOUT = {
    "SHL_border_foundries": (33, 6),
    "SHL_siege_founders": (32, 8),
    "SHL_furnace_garrisons": (34, 8),
    "SHL_border_settlement_office": (33, 10),
}


def prerequisite_blocks(focus):
    """One set of alternatives per prerequisite block (blocks are ANDed)."""
    return [{e.value for e in b.value} for b in focus if b.key == "prerequisite"]


def omitted_closure(focuses, queue, omitted):
    """Extend omitted with every focus reachable only through an omitted one."""
    omitted = set(omitted)
    changed = True
    while changed:
        changed = False
        for name, focus in focuses.items():
            if name in omitted or name in queue:
                continue
            blocks = prerequisite_blocks(focus)
            if blocks and any(options <= omitted for options in blocks):
                omitted.add(name)
                changed = True
    return omitted


def reachable_focuses(focuses, blocked):
    """Focuses completable when the blocked ones are never taken."""
    done = set()
    changed = True
    while changed:
        changed = False
        for name, focus in focuses.items():
            if name in done or name in blocked:
                continue
            if all(options & done for options in prerequisite_blocks(focus)):
                done.add(name)
                changed = True
    return done


@lru_cache(maxsize=None)
def focus_tree(name):
    """Parsed body of the authored SHL focus_tree (only the main source is a tree)."""
    return block(parse_clausewitz(FOCUS_TREE_SOURCES[name].read_text(encoding="utf-8")), "focus_tree")


@lru_cache(maxsize=None)
def tree_focuses(name):
    """id -> body of the focuses authored in the main tree or in one course section."""
    if name == "main":
        entries = focus_tree("main")
    else:
        entries = parse_clausewitz(FOCUS_TREE_SOURCES[name].read_text(encoding="utf-8"))
    return {scalar(entry.value, "id"): entry.value for entry in entries if entry.key == "focus"}


def whole_tree_focuses():
    """id -> body of every focus the native SHL tree shows: main, course sections, shared layer."""
    focuses = {}
    for name in FOCUS_TREE_SOURCES:
        focuses.update(tree_focuses(name))
    focuses.update(shared_focuses())
    return focuses


@lru_cache(maxsize=None)
def shared_focuses():
    """id -> body of the top-level shared focuses of the southern front."""
    return {
        scalar(entry.value, "id"): entry.value
        for entry in parse_clausewitz(SHARED_FOCUS_SOURCE.read_text(encoding="utf-8"))
        if entry.key == "shared_focus"
    }


# Every campaign state the course gates distinguish: course 0-5, before and after the South.
COURSE_STATES = tuple(product(range(6), (False, True)))
HEGEMON_FLAG = "ADISCORD_south_hegemon_SHL"


def gate_holds(items, course, hegemon, completed):
    """Evaluate an authored SHL allow_branch; completed=None satisfies every focus check."""
    for entry in items:
        key, value = entry.key, entry.value
        if key == "OR":
            result = any(gate_holds([item], course, hegemon, completed) for item in value)
        elif key == "NOT":
            result = not any(gate_holds([item], course, hegemon, completed) for item in value)
        elif key == "check_variable":
            assert (scalar(value, "var"), scalar(value, "compare")) == ("SHL_political_course", "equals"), value
            result = course == int(scalar(value, "value"))
        elif key == "has_global_flag":
            result = hegemon and value == HEGEMON_FLAG
        elif key == "has_completed_focus":
            result = completed is None or value in completed
        elif key == "has_country_flag":
            # The defeat chapter may open on any course; draw it in every state.
            result = True
        else:
            raise AssertionError("Unsupported allow_branch condition: " + key)
        if not result:
            return False
    return True


def visible_focuses(course, hegemon=False, completed=None):
    """id -> body of the SHL_focus entries drawn in one campaign state.

    An own allow_branch decides its focus; an ungated focus is drawn while one
    of its prerequisites is drawn, as the native tree inherits a hidden branch.
    """
    focuses = whole_tree_focuses()
    drawn = {}

    def is_drawn(identifier):
        if identifier not in drawn:
            drawn[identifier] = False
            focus = focuses[identifier]
            gate = block(focus, "allow_branch")
            parents = set().union(*prerequisite_blocks(focus)) if prerequisite_blocks(focus) else set()
            if gate:
                drawn[identifier] = gate_holds(gate, course, hegemon, completed)
            else:
                drawn[identifier] = not parents or any(is_drawn(parent) for parent in parents)
        return drawn[identifier]

    return {identifier: focus for identifier, focus in focuses.items() if is_drawn(identifier)}


def assert_free_cells(test, focuses, label):
    """Drawn focuses never share a cell and keep one free column between row neighbours."""
    cells = [(int(scalar(f, "x")), int(scalar(f, "y"))) for f in focuses.values()]
    test.assertEqual(len(cells), len(set(cells)), label)
    for row in {y for _, y in cells}:
        columns = sorted(x for x, y in cells if y == row)
        test.assertTrue(all(b - a >= 2 for a, b in zip(columns, columns[1:])), (label, row, columns))


@lru_cache(maxsize=None)
def war_tree_focuses():
    """id -> body of the focuses of the separate war-for-the-South tree."""
    tree = block(parse_clausewitz(WAR_TREE_SOURCE.read_text(encoding="utf-8")), "focus_tree")
    return {scalar(entry.value, "id"): entry.value for entry in tree if entry.key == "focus"}


@lru_cache(maxsize=None)
def all_focus_definitions():
    definitions = {}
    for name in FOCUS_TREE_SOURCES:
        definitions.update(tree_focuses(name))
    definitions.update(shared_focuses())
    definitions.update(war_tree_focuses())
    return definitions


def shl_focus_text():
    paths = (*FOCUS_TREE_SOURCES.values(), SHARED_FOCUS_SOURCE, WAR_TREE_SOURCE)
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


def seat_houses(machine, loyalty):
    """Give every house one loyalty, so the derived pressure reads 100 - loyalty."""
    for state in range(287, 296):
        machine.variables[str(state)]["SHL_house_loyalty"] = float(loyalty)
    machine.run("SHL_refresh_house_pressure")


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
        # Booked treasury receipts used by focus rewards and the brokers' premium.
        self.effects.update(shared_definitions(
            "common/scripted_effects/ADISCORD_shared_action_effects.txt",
            ("ADISCORD_economy_receive_15", "ADISCORD_economy_receive_100"),
        ))
        self.variables = defaultdict(dict)
        self.flags = defaultdict(set)
        self.global_flags = {"ADISCORD_fresh_campaign_contract_v1"}
        self.flag_days = defaultdict(dict)
        self.flag_values = defaultdict(dict)
        self.control = {str(i): "SHL" for i in range(287, 296)}
        self.ownership = dict(self.control)
        self.claims = defaultdict(set)
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
        self.fuel = defaultdict(float)
        self.previous_scope = "SHL"
        # Ruling character and the trees loaded by course ratification.
        self.leader = "SHL_Jalil_Nur"
        self.portraits = {}
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

    def stock_count(self, scope, equipment):
        return self.equipment[scope, equipment]

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
                    "not_equals": left != right,
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
                    if len(tokens) == 3 and tokens[0] == "value":
                        current = self.flag_values[scope].get(name, 0)
                        bound = int(tokens[2])
                        return name in self.flags[scope] and {"<": current < bound, ">": current > bound}[tokens[1]]
                    if tokens[:2] != ["days", ">"] or len(tokens) != 3:
                        raise AssertionError("Unsupported flag-age predicate")
                    return name in self.flags[scope] and self.flag_days[scope].get(name, 0) > int(tokens[2])
                return e.value in self.flags[scope]
            if e.key in ("ROOT", "SHL"):
                country = self.root_scope if e.key == "ROOT" else "SHL"
                return self.condition_scope(e.value, country, scope, target)
            if e.key in self.countries:
                return self.condition_scope(e.value, e.key, scope, target)
            if e.key == "exists" and scope in self.countries:
                return self.countries[scope]["exists"] == (e.value == "yes")
            if e.key == "is_subject_of":
                expected = self.root_scope if e.value == "ROOT" else e.value
                return self.countries.get(scope, {}).get("subject_of") == expected
            if e.key == "has_autonomy_state":
                return self.countries.get(scope, {}).get("autonomy_state") == e.value
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
            if e.key.startswith("var:"):
                state = str(int(self.value(e.key[4:], scope)))
                return state in self.ownership and self.condition_scope(e.value, state, scope, target)
            if e.key == "FROM":
                return self.condition_scope(e.value, target, scope, target)
            if e.key == "controller":
                return self.condition_scope(e.value, self.control[scope], scope, target)
            if e.key.isdigit():
                return self.condition_scope(e.value, e.key, scope, target)
            if e.key in ("is_owned_by", "is_controlled_by"):
                expected = "SHL" if e.value == "ROOT" else e.value
                owners = self.ownership if e.key == "is_owned_by" else self.control
                return owners.get(scope) == expected
            if e.key == "PREV":
                return self.condition_scope(e.value, self.previous_scope, scope, target)
            if e.key == "controls_state":
                return self.control.get(e.value) == scope
            if e.key == "is_claimed_by":
                return e.value in self.claims[scope]
            if e.key == "has_completed_focus":
                return e.value in self.focuses
            if e.key == "has_focus_tree":
                return e.value == (self.loaded_trees[-1] if self.loaded_trees else "SHL_focus")
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
                return self.stock_count(scope, tokens[0]) < float(tokens[2])
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
                return self.countries.get(scope, {}).get("is_ai", self.ai) == (e.value == "yes")
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
                    "has_fuel": self.fuel[scope],
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
            elif e.key.startswith("var:"):
                state = str(int(self.value(e.key[4:], scope)))
                if state not in self.ownership:
                    raise AssertionError("Unknown dispatch state: " + state)
                self.switch_scope(e.value, state, scope, target)
            elif e.key == "PREV":
                self.switch_scope(e.value, self.previous_scope, scope, target)
            elif e.key in self.countries:
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
                if e.key == "add_claim_by":
                    self.claims[scope].add(e.value)
                else:
                    self.claims[scope].discard(e.value)
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
            elif e.key == "controller":
                self.switch_scope(e.value, self.control[scope], scope, target)
            elif e.key == "every_possible_country":
                for tag in self.countries.keys() | {"SHL"}:
                    if self.condition_scope(block(e.value, "limit"), tag, scope, target):
                        self.switch_scope([c for c in e.value if c.key != "limit"], tag, scope, target)
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
            elif e.key == "add_fuel":
                self.fuel[scope] += self.value(e.value, scope)
            elif e.key == "send_equipment":
                equipment = scalar(e.value, "type")
                amount = self.value(scalar(e.value, "amount"), scope)
                recipient = scalar(e.value, "target")
                self.equipment[(scope, equipment)] -= amount
                self.equipment[(recipient, equipment)] += amount
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
            elif e.key == "set_portraits":
                self.portraits[scalar(e.value, "character")] = scalar(block(e.value, "civilian"), "large")
            elif e.key == "promote_character":
                self.leader = scalar(e.value, "character")
                self.calls.append((e.key, scope))
            elif e.key == "retire_character":
                if self.leader == e.value:
                    self.leader = None
                self.calls.append((e.key, scope))
            elif e.key == "SHL_Jalil_Nur":
                self.switch_scope(e.value, scope, scope, target)
            elif e.key == "set_temp_variable" and any(item.key == "ADISCORD_party" for item in e.value):
                self.party_token = scalar(e.value, "ADISCORD_party")
            elif e.key == "ADISCORD_legalise_party":
                self.calls.append((e.key, scope, self.party_token))
            elif e.key == "add_country_leader_role":
                if scalar(e.value, "promote_leader") == "yes":
                    self.leader = scalar(e.value, "character")
                self.calls.append((e.key, scope))
            elif e.key == "load_focus_tree":
                self.loaded_trees.append(scalar(e.value, "tree"))
            elif e.key == "complete_national_focus":
                self.focuses.add(e.value)
            elif e.key == "set_cosmetic_tag":
                self.cosmetic_tags.append(e.value)
            elif e.key in (
                "set_politics", "add_popularity", "remove_country_leader_role",
                "mark_focus_tree_layout_dirty", "force_update_dynamic_modifier", "add_war_support",
                "ADISCORD_release_non_participating_minor_optimization",
                "ADISCORD_south_crisis_add_campaign", "ADISCORD_south_crisis_cycle",
                "ADISCORD_south_pull_clock_war", "ADISCORD_south_pull_clock_campaign",
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
            elif e.key in ("set_variable", "set_temp_variable", "add_to_variable", "add_to_temp_variable", "subtract_from_variable", "multiply_variable", "divide_variable", "multiply_temp_variable", "subtract_from_temp_variable"):
                name = scalar(e.value, "var")
                amount = self.value(scalar(e.value, "value"), scope)
                previous = self.variables[scope].get(name, 0.0)
                if e.key in ("set_variable", "set_temp_variable"):
                    self.variables[scope][name] = amount
                elif e.key in ("add_to_variable", "add_to_temp_variable"):
                    self.variables[scope][name] = previous + amount
                elif e.key in ("subtract_from_variable", "subtract_from_temp_variable"):
                    self.variables[scope][name] = previous - amount
                elif e.key in ("multiply_variable", "multiply_temp_variable"):
                    self.variables[scope][name] = previous * amount
                else:
                    self.variables[scope][name] = previous / amount
            elif e.key in ("clamp_variable", "clamp_temp_variable"):
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
                self.flag_values[scope][name] = int(scalar(e.value, "value", 1)) if isinstance(e.value, list) else 1
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
                self.dynamic.discard(scalar(e.value, "modifier") if isinstance(e.value, list) else e.value)
            elif e.key in ("country_event", "news_event"):
                self.scheduled.append(scalar(e.value, "id"))
                self.event_days[scalar(e.value, "id")] = int(scalar(e.value, "days", "0"))
            elif e.key in ("ADISCORD_economy_mark_dirty", "ADISCORD_economy_reprice_debt", "ADISCORD_economy_initialize_country"):
                self.calls.append(e.key)
            elif e.key in ("effect_tooltip", "custom_effect_tooltip", "unlock_decision_tooltip", "add_to_array", "log", "air_experience", "set_character_name"):
                self.calls.append(e.key)
            else:
                raise AssertionError("Unsupported effect: " + e.key)


class FurnaceAccountingTests(unittest.TestCase):
    def setUp(self):
        effects = parse_clausewitz(EFFECT_PATH.read_text(encoding="utf-8")) if EFFECT_PATH.exists() else []
        triggers = parse_clausewitz(TRIGGER_PATH.read_text(encoding="utf-8")) if TRIGGER_PATH.exists() else []
        self.machine = ScriptMachine(effects, triggers)
        # The packet price is set by the startup initialiser and every refresh.
        self.machine.run("SHL_refresh_packet_price")
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

    def test_raw_material_packets_have_one_symbol_in_costs_stores_and_receipts(self):
        from PIL import Image

        asset = "gfx/interface/SHL_conclave/packet_texticon.png"
        gfx = (ROOT / "interface/ADISCORD_SHL.gfx").read_text(encoding="utf-8")
        self.assertRegex(gfx, r'name = "GFX_SHL_packet_texticon"\s+texturefile = "' + re.escape(asset) + '"')
        with Image.open(ROOT / asset) as icon:
            self.assertEqual(icon.size, (18, 16))
            self.assertEqual(icon.convert("RGBA").getchannel("A").getextrema(), (0, 255))
        keys = ["SHL_panel_stocks", "SHL_forecast_running", "SHL_census_tt", "SHL_supply_result_tt",
                "SHL_tenth_condition_running", "SHL_tenth_condition_stopped"]
        keys.extend(f"SHL_furnace_{index}_tip" for index in range(1, 10))
        for cost in ("SHL_cost_waterworks", "SHL_cost_100_stock", "SHL_cost_directorate_aid"):
            keys.extend(cost + suffix for suffix in ("", "_blocked", "_tooltip"))
        for lang in ("russian", "english"):
            loc = (ROOT / "localisation" / lang / f"ADISCORD_SHL_l_{lang}.yml").read_text(encoding="utf-8-sig")
            for key in keys:
                entry = re.search(rf'(?m)^ {key}:\d* "(.*)"$', loc)
                self.assertIsNotNone(entry, key)
                self.assertIn("£SHL_packet_texticon", entry[1], key)
                self.assertNotIn("£SHL_ore_texticon", entry[1], key)

    def test_all_ten_seals_are_separate_click_targets_inside_the_survey(self):
        from PIL import Image

        gui = parse_clausewitz((ROOT / "interface/ADISCORD_SHL.gui").read_text(encoding="utf-8"))
        panel = block(block(gui, "guiTypes"), "containerWindowType")
        widgets = {scalar(entry.value, "name").strip('"'): entry.value for entry in panel
                   if entry.key in ("buttonType", "iconType")}
        sprites = parse_clausewitz((ROOT / "interface/ADISCORD_SHL.gfx").read_text(encoding="utf-8"))
        textures = {scalar(entry.value, "name"): scalar(entry.value, "texturefile").strip('"')
                    for entry in block(sprites, "spriteTypes")}

        def bounds(widget):
            position = block(widget, "position")
            x, y = int(scalar(position, "x")), int(scalar(position, "y"))
            with Image.open(ROOT / textures[scalar(widget, "quadTextureSprite")]) as texture:
                return x, y, x + texture.width, y + texture.height

        left, top, right, bottom = bounds(widgets["SHL_survey_map"])
        earlier = []
        for number, numeral in enumerate("I II III IV V VI VII VIII IX X".split(), 1):
            seal = widgets[f"SHL_furnace_{number}_button"]
            self.assertEqual(scalar(seal, "buttonText").strip('"'), numeral)
            x, y, end_x, end_y = bounds(seal)
            self.assertTrue(left <= x < end_x <= right and top <= y < end_y <= bottom, numeral)
            for x1, y1, x2, y2 in earlier:
                self.assertTrue(end_x <= x1 or end_y <= y1 or x2 <= x or y2 <= y, numeral)
            earlier.append((x, y, end_x, end_y))

    def test_panel_and_decisions_switch_the_same_supply_order_without_charging(self):
        machine = self.machine
        country = machine.variables["SHL"]
        country.update({"SHL_regular_supply": 0, "SHL_gui_dirty": 0, "ADISCORD_economy_treasury": 125})
        source = (ROOT / "common/scripted_guis/ADISCORD_SHL_scripted_gui.txt").read_text(encoding="utf-8")
        gui = block(block(parse_clausewitz(source), "scripted_gui"), "ADISCORD_SHL_furnaces")
        enabled = block(block(gui, "triggers"), "SHL_supply_toggle_button_click_enabled")
        click = block(block(gui, "effects"), "SHL_supply_toggle_button_click")
        start = decision_definition("SHL_planned_supply")
        stop = decision_definition("SHL_stop_planned_supply")
        self.assertFalse(machine.matches(enabled, "SHL"))
        machine.execute(click, "SHL")
        self.assertEqual(country["SHL_regular_supply"], 0)
        machine.focuses.add("SHL_law_of_continuous_fire")
        self.assertTrue(machine.matches(enabled, "SHL"))
        self.assertFalse(machine.matches(block(start, "visible"), "SHL"))
        self.assertFalse(machine.matches(block(stop, "visible"), "SHL"))
        machine.ai = True
        self.assertTrue(machine.matches(block(start, "visible"), "SHL"))
        machine.execute(click, "SHL")
        self.assertEqual(country["SHL_regular_supply"], 1)
        self.assertFalse(machine.matches(block(start, "visible"), "SHL"))
        self.assertTrue(machine.matches(block(stop, "visible"), "SHL"))
        machine.ai = False
        self.assertFalse(machine.matches(block(stop, "visible"), "SHL"))
        machine.execute(block(start, "complete_effect"), "SHL")
        self.assertEqual(country["SHL_gui_dirty"], 1)
        machine.execute(block(stop, "complete_effect"), "SHL")
        machine.execute(block(start, "complete_effect"), "SHL")
        machine.execute(click, "SHL")
        self.assertEqual(country["SHL_regular_supply"], 0)
        self.assertEqual(country["SHL_gui_dirty"], 4)
        self.assertEqual(country["ADISCORD_economy_treasury"], 125)
        law = block(focus_definition("SHL_law_of_continuous_fire"), "completion_reward")
        self.assertNotIn("SHL_planned_supply", [e.value for e in law if e.key == "unlock_decision_tooltip"])
        self.assertIn("SHL_furnace_supply_unlock_tt", [e.value for e in law if e.key == "custom_effect_tooltip"])
        self.assertIn("SHL_houses_railway", repr(block(start, "ai_will_do")))
        self.assertNotIn("SHL_houses_railway", repr(block(start, "visible")))

    def test_panel_tooltips_resolve_live_values_in_both_languages(self):
        gui = parse_clausewitz((ROOT / "interface/ADISCORD_SHL.gui").read_text(encoding="utf-8"))
        tips = {}
        for panel in block(gui, "guiTypes"):
            for widget in panel.value:
                if not isinstance(widget.value, list):
                    continue
                tooltip = scalar(widget.value, "pdx_tooltip")
                if tooltip:
                    tips[scalar(widget.value, "name").strip('"')] = tooltip.strip('"')
        for lang in ("english", "russian"):
            path = ROOT / f"localisation/{lang}/ADISCORD_SHL_l_{lang}.yml"
            source = path.read_text(encoding="utf-8-sig")
            strings = dict(re.findall(r'^ (\w+):\d* "(.*)"$', source, re.M))
            for widget, token in (
                ("SHL_cycle_line", "[?SHL_preview_income|+2]"),
                ("SHL_panel_totals", "[SHLGetShift]"),
                ("SHL_ledger_line", "[SHLGetProjectStage]"),
            ):
                self.assertIn(token, strings[tips[widget]], (lang, widget))
            for number in range(1, 10):
                tooltip = strings[tips[f"SHL_furnace_{number}_button"]]
                self.assertIn(f"[?SHL_wear_{number}|0]", tooltip)
                self.assertIn(f"[SHLGetRecipient{number}]", tooltip)
            for gauge, value in (("SHL_quarter_gauge", "SHL_unrest"), ("SHL_crest_gauge", "SHL_house_pressure")):
                self.assertIn(f"[?{value}|0]", strings[gauge])
                self.assertIn("60", strings[tips[gauge]])

    def test_next_pour_forecast_columns_fit_each_page_and_use_live_values_in_both_languages(self):
        from PIL import Image

        gui = parse_clausewitz((ROOT / "interface/ADISCORD_SHL.gui").read_text(encoding="utf-8"))
        panel = block(block(gui, "guiTypes"), "containerWindowType")
        fields = {scalar(row.value, "name").strip('"'): row.value for row in panel if row.key == "instantTextBoxType"}
        bounds = block(panel, "size")
        width = int(scalar(bounds, "width"))
        height = int(scalar(bounds, "height"))
        background = next(e.value for e in panel
                          if e.key == "iconType" and scalar(e.value, "name").strip('"') == "SHL_board")
        with Image.open(ROOT / "gfx/interface/SHL_conclave/board.png") as board:
            origin = block(background, "position")
            self.assertLessEqual(int(scalar(origin, "x")) + board.width, width)
            self.assertLessEqual(int(scalar(origin, "y")) + board.height, height)
        rows = (
            (
                ("net", "[?SHL_preview_cycle_net|"),
                ("reserve", "[SHLGetReserveDraw]"),
                ("cost", "[?SHL_preview_autobuy_cost|"),
            ),
            (
                ("packets", "[?SHL_preview_autobuy_packets|"),
                ("rifles", "[?SHL_preview_rifles|"),
                ("politics", "[?SHL_preview_crests|"),
            ),
        )
        for lang in ("english", "russian"):
            source = (ROOT / f"localisation/{lang}/ADISCORD_SHL_l_{lang}.yml").read_text(encoding="utf-8-sig")
            strings = dict(re.findall(r'^ (\w+):\d* "(.*)"$', source, re.M))
            for row in rows:
                right = 0
                for metric, live_text in row:
                    name = "SHL_forecast_" + metric
                    field = fields[name]
                    label = fields[name + "_label"]
                    self.assertIn(live_text, strings[scalar(field, "text").strip('"')])
                    self.assertIn(scalar(label, "text").strip('"'), strings)
                    position = block(field, "position")
                    x, y = int(scalar(position, "x")), int(scalar(position, "y"))
                    self.assertGreaterEqual(x, right)
                    right = x + int(scalar(field, "maxWidth"))
                    self.assertLessEqual(right, width)
                    self.assertLessEqual(int(scalar(block(label, "position"), "y")) + int(scalar(label, "maxHeight")), y)
                    self.assertLessEqual(y + int(scalar(field, "maxHeight")), height)

    def test_supply_hover_resolves_funded_and_skipped_rows_in_both_languages(self):
        gui = parse_clausewitz((ROOT / "interface/ADISCORD_SHL.gui").read_text(encoding="utf-8"))
        panel = block(block(gui, "guiTypes"), "containerWindowType")
        widgets = {scalar(e.value, "name", "").strip('"'): e.value for e in panel if isinstance(e.value, list)}
        source = ROOT / "common/scripted_localisation/ADISCORD_SHL_scripted_loc.txt"
        definitions = {scalar(e.value, "name"): e.value for e in parse_clausewitz(source.read_text(encoding="utf-8"))}

        def selected_key(name):
            return next(scalar(row.value, "localization_key").strip('"') for row in definitions[name]
                        if row.key == "text" and self.machine.matches(block(row.value, "trigger"), "SHL"))

        country = self.machine.variables["SHL"]
        for lang in ("russian", "english"):
            contents = (ROOT / f"localisation/{lang}/ADISCORD_SHL_l_{lang}.yml").read_text(encoding="utf-8-sig")
            strings = dict(re.findall(r'^ (\w+):\d* "(.*)"$', contents, re.M))
            with self.subTest(lang=lang):
                for name in ("SHL_supply_toggle_button", "SHL_supply_packet_quote", "SHL_forecast_packets_label",
                             "SHL_forecast_packets", "SHL_forecast_cost_label", "SHL_forecast_cost"):
                    hover = strings[scalar(widgets[name], "pdx_tooltip").strip('"')]
                    self.assertIn("[SHLGetForecastOrderList]", hover)
                    self.assertNotIn("$", hover)

                self.machine.focuses.discard("SHL_law_of_continuous_fire")
                country.update({"SHL_regular_supply": 0, "SHL_preview_autobuy_packets": 0, "SHL_preview_unfunded_packets": 0})
                locked = strings[selected_key("SHLGetForecastOrderList")]
                self.machine.focuses.add("SHL_law_of_continuous_fire")
                manual = strings[selected_key("SHLGetForecastOrderList")]
                country["SHL_regular_supply"] = 1
                empty = strings[selected_key("SHLGetForecastOrderList")]
                self.assertEqual(len({locked, manual, empty, ""}), 4)
                country["SHL_preview_unfunded_packets"] = 2
                listing = strings[selected_key("SHLGetForecastOrderList")]
                selectors = re.findall(r"\[(SHLGetForecastOrder\d+)\]", listing)
                self.assertEqual(selectors, [f"SHLGetForecastOrder{n}" for n in range(1, 11)])
                for n, selector in enumerate(selectors, 1):
                    packets = f"SHL_forecast_order_packets_{n}"
                    shortfall = f"SHL_forecast_order_shortfall_{n}"
                    country[packets] = 2
                    country[shortfall] = 0
                    paid = strings[selected_key(selector)]
                    country[shortfall] = 0.001
                    refused = strings[selected_key(selector)]
                    for line in (paid, refused):
                        self.assertTrue(line.startswith(r"\n"))
                        self.assertIn(" ".join(strings[f"SHL_furnace_{n}_label"].split()), " ".join(line.split()))
                        self.assertIn(f"[?{packets}|0] £SHL_packet_texticon", line)
                    self.assertNotIn(shortfall, paid)
                    self.assertIn(f"[?{shortfall}|3] £ADISCORD_economy_treasury_texticon", refused)
                    country[packets] = 0
                    self.assertEqual(strings[selected_key(selector)], "")

    def test_alert_navigation_matches_map_badges_and_wraps(self):
        machine = self.machine
        country = machine.variables["SHL"]
        country["SHL_selected_furnace"] = 2
        machine.run("SHL_refresh_furnaces")
        country["SHL_wear_2"] = 74
        country["SHL_delivery_block_6"] = 4
        country["SHL_tenth_wear"] = 90
        self.assertFalse(machine.matches(machine.triggers["SHL_has_furnace_alert"], "SHL"))
        machine.run("SHL_select_next_furnace_alert")
        self.assertEqual(country["SHL_selected_furnace"], 2)
        country["SHL_wear_2"] = 75
        country["SHL_wear_6"] = 80
        for code in (1, 2, 3):
            country["SHL_delivery_block_6"] = code
            self.assertTrue(machine.matches(machine.triggers["SHL_furnace_6_interrupted"], "SHL"))
            self.assertTrue(machine.matches(machine.triggers["SHL_furnace_6_worn"], "SHL"))
        country["SHL_project_stage"] = 4
        for expected in (6, 10, 2):
            machine.run("SHL_select_next_furnace_alert")
            self.assertEqual(country["SHL_selected_furnace"], expected)

    def test_caravan_offers_and_terms_use_the_same_buyers(self):
        source = (ROOT / "common/decisions/ADISCORD_SHL_decisions.txt").read_text(encoding="utf-8")
        categories = parse_clausewitz(source)
        caravans = block(categories, "SHL_caravans")
        catalogue = [
            scalar(e.value, "SHL_caravan_partners")
            for e in self.machine.effects["SHL_initialize_programmes"] if e.key == "add_to_array"
        ]
        for name in ("SHL_metal_contract_offer", "SHL_metal_contract_end"):
            self.assertTrue(block(caravans, name))
            self.assertFalse(block(block(categories, "SHL_quarters_and_borders"), name))
            targets = re.search(r"targets = \{ ([A-Z ]+) \}", source.split(f"\n\t{name} = {{", 1)[1])[1].split()
            self.assertEqual(catalogue, targets)
        gui = parse_clausewitz((ROOT / "interface/ADISCORD_SHL.gui").read_text(encoding="utf-8"))
        panel = next(e.value for e in block(gui, "guiTypes") if scalar(e.value, "name") == "ADISCORD_SHL_caravans_window")
        total = next(e.value for e in panel if e.key == "instantTextBoxType" and scalar(e.value, "name") == "SHL_caravan_forecast_value")
        for lang in ("english", "russian"):
            path = ROOT / f"localisation/{lang}/ADISCORD_SHL_l_{lang}.yml"
            strings = dict(re.findall(r'^ (\w+):\d* "(.*)"$', path.read_text(encoding="utf-8-sig"), re.M))
            journal = strings["SHL_caravans_desc"]
            for getter in ("SHLGetCaravanPending", "SHLGetCaravanRow"):
                self.assertEqual(re.findall(r"\[([A-Z]+)\." + getter + r"\]", journal), catalogue)
            self.assertLess(journal.rindex(".SHLGetCaravanPending]"), journal.index(".SHLGetCaravanRow]"))
            self.assertIn("[?SHL_preview_contract_income|0]", strings[scalar(total, "text")])
            self.assertIn("[SHLGetMetalOfferTitle]", strings["SHL_metal_contract_offer"])
            self.assertIn("[FROM.GetName]", strings["SHL_metal_offer_target_title"])
            self.assertNotIn("[FROM", strings["SHL_metal_offer_unlock_title"])
            self.assertIn("[FROM.GetName]", strings["SHL_metal_contract_end"])
            row = re.sub(r"\$(\w+)\$", lambda m: strings[m[1]], strings["SHL_caravan_contract_entry"])
            self.assertIn("[This.GetName]", row)
            self.assertIn("[?SHL_metal_cycle_price|0]", row)
            self.assertIn("[SHLGetCaravanTerm]", row)
            self.assertIn("[SHLGetCaravanArrears]", row)
            self.assertIn("[?SHL_metal_arrears|0]", strings["SHL_caravan_missed_payment"])
        tokens = (ROOT / "common/synchronized_dynamic_tokens/ADISCORD_tokens.txt").read_text().splitlines()
        for mission in ("SHL_conclave_ballot", "SHL_metal_contract_year", "SHL_metal_contract_two_years"):
            self.assertEqual(tokens.count(mission), 1)

    def test_caravan_reader_moves_a_buyer_from_pending_to_active(self):
        path = ROOT / "common/scripted_localisation/ADISCORD_SHL_scripted_loc.txt"
        definitions = {scalar(e.value, "name"): e.value for e in parse_clausewitz(path.read_text(encoding="utf-8"))}
        def read(getter, buyer):
            for option in definitions[getter]:
                if option.key == "text" and self.machine.matches(block(option.value, "trigger"), buyer):
                    return scalar(option.value, "localization_key")
            self.fail(getter)

        self.machine.flags["VAL"].add("SHL_metal_offer_pending")
        self.assertEqual(read("SHLGetCaravanPending", "VAL"), "SHL_caravan_pending")
        self.assertEqual(read("SHLGetCaravanRow", "VAL"), "SHL_borders_blank")
        self.machine.flags["VAL"].add("SHL_metal_client")
        self.assertEqual(read("SHLGetCaravanPending", "VAL"), "SHL_borders_blank")
        self.assertEqual(read("SHLGetCaravanRow", "VAL"), "SHL_caravan_contract_entry")
        self.machine.flags["VAL"].discard("SHL_metal_offer_pending")
        self.machine.variables["VAL"]["SHL_metal_arrears"] = 1
        self.assertEqual(read("SHLGetCaravanArrears", "VAL"), "SHL_caravan_missed_payment")
        self.machine.variables["VAL"]["SHL_metal_arrears"] = 0
        self.assertEqual(read("SHLGetCaravanArrears", "VAL"), "SHL_caravan_payments_current")
        self.machine.flags["VAL"].discard("SHL_metal_client")
        self.assertEqual(read("SHLGetCaravanPending", "VAL"), "SHL_borders_blank")
        self.assertEqual(read("SHLGetCaravanRow", "VAL"), "SHL_borders_blank")

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
        m.variables["SHL"]["ADISCORD_economy_treasury"] = 39.99
        m.run("SHL_begin_supply", target="287")
        self.assertEqual(m.variables["SHL"]["ADISCORD_economy_treasury"], 39.99)
        m.variables["SHL"]["ADISCORD_economy_treasury"] = 40
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
                    75: "b", 112: "b", 120: "c", 121: "b", 141: "a",
                    200: "a", 201: "a", 202: "a", 203: "a", 204: "a"}
        self.assertTrue(set(range(200, 205)) <= {
            int(scalar(entry.value, "id").rsplit(".", 1)[1])
            for entry in parse_clausewitz(source)
            if entry.key == "country_event" and scalar(entry.value, "id").startswith("ADISCORD_SHL.")
        })
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
        self.assertEqual(m.variables["SHL"]["ADISCORD_economy_treasury"], 960)
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

    def test_convoy_moves_one_pack_and_only_production_releases_the_trip(self):
        m = self.machine
        seat_houses(m, 80)
        m.variables["SHL"]["SHL_selected_furnace"] = 1
        m.run("SHL_refresh_furnaces")
        m.run("SHL_dispatch_ore")
        self.assertEqual(m.variables["291"]["SHL_furnace_stock"], 1)
        self.assertEqual(m.variables["287"]["SHL_furnace_stock"], 3)
        m.variables["SHL"]["SHL_selected_furnace"] = 2
        m.run("SHL_refresh_selected_furnace")
        m.run("SHL_dispatch_sale")
        self.assertEqual(m.variables["288"]["SHL_furnace_stock"], 2)
        m.run("SHL_produce_period")
        m.run("SHL_refresh_house_pressure")
        treasury = m.variables["SHL"]["ADISCORD_economy_treasury"]
        pressure = m.variables["SHL"].get("SHL_house_pressure", 0)
        revenue = m.variables["SHL"]["ADISCORD_economy_current_month_action_income"]
        m.run("SHL_dispatch_sale")
        self.assertEqual(m.variables["288"]["SHL_furnace_stock"], 0)
        self.assertEqual(m.variables["SHL"]["ADISCORD_economy_treasury"], treasury + 40)
        self.assertEqual(m.variables["SHL"]["ADISCORD_economy_current_month_action_income"], revenue + 40)
        self.assertEqual(m.variables["SHL"]["SHL_house_pressure"], pressure + 3)

    def test_convoy_rechecks_stores_commitments_and_control_at_dispatch(self):
        m = self.machine
        m.variables["SHL"]["SHL_selected_furnace"] = 1
        m.run("SHL_refresh_furnaces")
        m.variables["287"]["SHL_furnace_stock"] = 3
        m.run("SHL_dispatch_ore")
        m.variables["287"]["SHL_furnace_stock"] = 1
        m.variables["291"]["SHL_operation_deposit"] = 25
        m.run("SHL_dispatch_ore")
        del m.variables["291"]["SHL_operation_deposit"]
        m.control["287"] = "KYZ"
        m.run("SHL_dispatch_ore")
        self.assertNotIn("SHL_convoy_dispatch", m.variables["SHL"])
        self.assertEqual(m.variables["291"]["SHL_furnace_stock"], 2)
        self.assertEqual(m.variables["287"]["SHL_furnace_stock"], 1)
        m.control["287"] = "SHL"
        m.variables["SHL"].update({"SHL_obligation_kind": 1, "SHL_obligation_site": 287})
        m.run("SHL_dispatch_sale")
        self.assertNotIn("SHL_convoy_dispatch", m.variables["SHL"])
        self.assertEqual(m.variables["287"]["SHL_furnace_stock"], 1)

    def test_waterworks_spend_local_stock_and_compete_for_one_convoy(self):
        m = self.machine
        loop = decision_definition("SHL_fit_cooling_loop")
        taps = decision_definition("SHL_fit_standpipe")
        m.variables["SHL"]["SHL_selected_furnace"] = 1
        self.assertTrue(m.matches(block(loop, "visible"), "SHL", "287"))
        self.assertFalse(m.matches(block(loop, "visible"), "SHL", "288"))
        m.variables["287"]["SHL_furnace_stock"] = 1.99
        self.assertFalse(m.matches(block(loop, "custom_cost_trigger"), "SHL", "287"))
        m.execute(block(loop, "complete_effect"), "SHL", "287")
        self.assertNotIn("SHL_qanat_works", m.variables["287"])
        m.variables["287"]["SHL_furnace_stock"] = 2
        m.execute(block(loop, "complete_effect"), "SHL", "287")
        self.assertEqual(m.variables["287"]["SHL_furnace_stock"], 0)
        self.assertEqual(m.variables["287"]["SHL_qanat_works"], 1)
        self.assertFalse(m.matches(block(taps, "available"), "SHL", "288"))
        m.execute(block(taps, "complete_effect"), "SHL", "288")
        m.run("SHL_dispatch_ore")
        self.assertEqual(m.variables["288"]["SHL_furnace_stock"], 2)
        self.assertEqual(m.variables["291"]["SHL_furnace_stock"], 2)
        m.run("SHL_produce_period")
        m.variables["287"]["SHL_furnace_stock"] = 2
        m.execute(block(taps, "complete_effect"), "SHL", "287")
        self.assertEqual(m.variables["287"]["SHL_qanat_works"], 1)
        self.assertEqual(m.variables["287"]["SHL_furnace_stock"], 2)
        self.assertTrue(m.matches(block(taps, "available"), "SHL", "288"))
        m.variables["288"]["SHL_furnace_stock"] = 2
        m.execute(block(taps, "complete_effect"), "SHL", "288")
        self.assertEqual(m.variables["288"]["SHL_qanat_works"], 2)

    def test_waterworks_respect_closed_disputes_and_protected_stores(self):
        m = self.machine
        decision = decision_definition("SHL_fit_cooling_loop")
        site = m.variables["287"]
        for field, value in (("SHL_operation_deposit", 25), ("SHL_furnace_running", 0)):
            with self.subTest(field=field):
                previous = dict(site)
                site[field] = value
                m.execute(block(decision, "complete_effect"), "SHL", "287")
                self.assertNotIn("SHL_qanat_works", site)
                site.clear()
                site.update(previous)
        m.flags["287"].add("SHL_quota_site")
        self.assertFalse(m.matches(block(decision, "available"), "SHL", "287"))
        m.flags["287"].clear()
        m.control["287"] = "KYZ"
        self.assertFalse(m.matches(block(decision, "available"), "SHL", "287"))
        m.control["287"] = "SHL"
        self.assertFalse(m.matches(block(decision, "available"), "SHL", "290"))
        m.variables["SHL"]["SHL_water_crisis"] = 2
        m.execute(block(decision, "complete_effect"), "SHL", "287")
        self.assertNotIn("SHL_qanat_works", site)
        self.assertEqual(site["SHL_furnace_stock"], 2)

    def test_cooling_loop_matches_forecast_before_during_and_after_drought(self):
        m = self.machine
        country = m.variables["SHL"]
        site = m.variables["287"]
        site["SHL_qanat_works"] = 1
        country["SHL_selected_furnace"] = 1
        for dispute, shift, training, expected in ((0, 0, 0, 4), (1, 1, 1, 7), (2, 2, 2, 0)):
            with self.subTest(dispute=dispute):
                country.update({"SHL_water_crisis": dispute, "SHL_shift_policy": shift})
                site.update({"SHL_furnace_training": training, "SHL_furnace_stock": 2})
                m.run("SHL_refresh_furnaces")
                self.assertEqual(country["SHL_selected_period_wear"], expected)
                before = site["SHL_furnace_wear"]
                m.run("SHL_produce_period")
                self.assertEqual(site["SHL_furnace_wear"] - before, expected)

    def test_standpipe_relief_requires_an_actual_delivery_to_the_quarters(self):
        m = self.machine
        country = m.variables["SHL"]
        site = m.variables["287"]
        site["SHL_qanat_works"] = 2
        country["SHL_selected_furnace"] = 1
        for strike, recipient, stock, control, expected in (
            (False, 2, 1, "SHL", 7), (True, 2, 1, "SHL", 12),
            (True, 0, 1, "SHL", 0), (True, 2, 0, "SHL", 0),
            (True, 2, 1, "KYZ", 0), (False, 2, 1, "SHL", 7),
        ):
            with self.subTest(strike=strike, recipient=recipient, stock=stock, control=control):
                m.flags["SHL"].discard("SHL_strike_active")
                if strike:
                    m.flags["SHL"].add("SHL_strike_active")
                country["SHL_unrest"] = 60
                for state in range(288, 296):
                    m.variables[str(state)]["SHL_furnace_stock"] = 1
                m.control["287"] = control
                site.update({"SHL_furnace_recipient": recipient, "SHL_furnace_stock": stock})
                m.run("SHL_refresh_furnaces")
                self.assertEqual(country["SHL_selected_delivery_quarters"], expected)
                m.run("SHL_produce_period")
                self.assertEqual(country["SHL_unrest"], 60 - expected)

    def test_new_campaign_can_commission_three_loops_before_the_eighth_pour(self):
        m = self.machine
        m.flags["SHL"].remove("SHL_furnaces_initialized")
        m.effects.update(shared_definitions(
            "common/scripted_effects/ADISCORD_economy_effects.txt",
            ("ADISCORD_economy_sync_starting_accounting",),
        ))
        m.run("SHL_apply_starting_economy")
        m.run("SHL_initialize_furnaces")
        install = decision_definition("SHL_fit_cooling_loop")
        supply = decision_definition("SHL_supply_furnace")
        supply_days = int(scalar(supply, "days_remove")) + int(scalar(supply, "days_re_enable"))
        for cycle in range(1, 9):
            for number in range(1, 10):
                target = str(286 + number)
                site = m.variables[target]
                m.variables["SHL"]["SHL_selected_furnace"] = number
                shipments = 0
                if cycle <= 3 and number == cycle:
                    while site["SHL_furnace_stock"] < 2:
                        m.run("SHL_begin_supply", target=target)
                        self.assertIn("SHL_operation_deposit", site)
                        m.run("SHL_finish_supply", target=target)
                        shipments += 1
                    self.assertTrue(m.matches(block(install, "visible"), "SHL", target))
                    self.assertTrue(m.matches(block(install, "available"), "SHL", target))
                    m.execute(block(install, "complete_effect"), "SHL", target)
                if site["SHL_furnace_stock"] < 1:
                    m.run("SHL_begin_supply", target=target)
                    self.assertIn("SHL_operation_deposit", site)
                    m.run("SHL_finish_supply", target=target)
                    shipments += 1
                self.assertLess(shipments * supply_days, 28)
            m.run("SHL_produce_period")
            m.run("SHL_refresh_furnaces")
            m.run("SHL_update_tensions")
            m.run("SHL_check_crises")
        self.assertEqual(m.variables["SHL"]["SHL_cycle_number"], 8)
        decision = decision_definition("SHL_limit_water_intake")
        self.assertTrue(m.matches(block(decision, "available"), "SHL"))
        m.execute(block(decision, "complete_effect"), "SHL")
        self.assertEqual(m.variables["SHL"]["SHL_water_crisis"], 6)

    def test_water_limit_requires_three_tested_loops_and_an_open_dispute(self):
        m = self.machine
        country = m.variables["SHL"]
        decision = decision_definition("SHL_limit_water_intake")
        available = block(decision, "available")
        settle = block(decision, "complete_effect")
        country["SHL_water_crisis"] = 1
        for target in ("287", "288", "289"):
            m.variables[target]["SHL_qanat_works"] = 1
        m.variables["289"]["SHL_furnace_stock"] = 0
        m.run("SHL_produce_period")
        self.assertEqual(m.variables["289"]["SHL_qanat_works"], 1)
        m.execute(settle, "SHL")
        self.assertEqual(country["SHL_water_crisis"], 1)
        m.variables["289"]["SHL_furnace_stock"] = 1
        m.run("SHL_produce_period")
        self.assertTrue(m.matches(available, "SHL"))
        m.control["288"] = "KYZ"
        self.assertFalse(m.matches(available, "SHL"))
        m.control["288"] = "SHL"
        m.flags["SHL"].add("SHL_water_offer_pending")
        self.assertFalse(m.matches(available, "SHL"))
        m.flags["SHL"].remove("SHL_water_offer_pending")
        country["SHL_wells_deposit"] = 0
        self.assertFalse(m.matches(available, "SHL"))
        del country["SHL_wells_deposit"]
        country["SHL_war_kyz"] = 1
        self.assertFalse(m.matches(available, "SHL"))
        country["SHL_war_kyz"] = 0
        m.variables["287"]["SHL_qanat_works"] = 2
        self.assertFalse(m.matches(block(decision, "visible"), "SHL"))
        self.assertFalse(m.matches(available, "SHL"))
        m.variables["287"]["SHL_qanat_works"] = 3
        treasury = country["ADISCORD_economy_treasury"]
        m.execute(settle, "SHL")
        self.assertEqual(country["SHL_water_crisis"], 6)
        self.assertFalse(m.matches(block(decision, "visible"), "SHL"))
        self.assertFalse(m.matches(available, "SHL"))
        self.assertEqual(country.get("SHL_water_quota", 0), 0)
        self.assertEqual(country["ADISCORD_economy_treasury"], treasury)
        self.assertTrue(m.matches(parse_clausewitz("SHL_neighbour_dispute_closed = yes"), "SHL"))

    def test_paid_civic_order_preempts_standpipe_deliveries(self):
        m = self.machine
        country = m.variables["SHL"]
        country.update({"SHL_political_course": 2, "SHL_selected_furnace": 1, "SHL_unrest": 60})
        m.variables["287"]["SHL_qanat_works"] = 2
        m.run("SHL_begin_civic_order", target="287")
        m.flags["SHL"].add("SHL_strike_active")
        m.run("SHL_refresh_furnaces")
        self.assertEqual(country["SHL_selected_delivery_quarters"], 0)
        m.run("SHL_produce_period")
        self.assertEqual(country["SHL_obligation_progress"], 1)
        self.assertEqual(country["SHL_unrest"], 60)

    def test_darban_masons_service_tenth_works_without_changing_the_eighth(self):
        m = self.machine
        m.variables["SHL"].update({"SHL_selected_furnace": 10, "SHL_tenth_wear": 35,
                                   "SHL_tenth_running": 1, "SHL_project_stage": 4})
        m.run("SHL_refresh_furnaces")
        m.run("SHL_dispatch_masons")
        self.assertEqual(m.variables["SHL"]["SHL_tenth_wear"], 35)
        m.focuses.add("SHL_repair_without_extinction")
        m.run("SHL_dispatch_masons")
        self.assertEqual(m.variables["294"]["SHL_furnace_stock"], 1)
        self.assertEqual(m.variables["294"]["SHL_furnace_wear"], 20)
        self.assertEqual(m.variables["SHL"]["SHL_tenth_wear"], 20)
        self.assertIn("SHL_convoy_dispatch", m.variables["SHL"])

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
        self.assertEqual(m.calls.count(("ADISCORD_legalise_party", "SHL", "token:anarchism")), 1)
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
        self.assertEqual(m.variables["SHL"]["ADISCORD_economy_treasury"], 65)
        self.assertEqual(m.variables["287"]["SHL_furnace_shortages"], 0)

    def test_planned_supply_never_borrows_or_buys_fractional_packets(self):
        m = self.machine
        m.variables["SHL"]["SHL_regular_supply"] = 1
        m.variables["SHL"]["ADISCORD_economy_treasury"] = 44.99
        m.variables["287"]["SHL_furnace_stock"] = 0
        m.run("SHL_produce_site", scope="287")
        self.assertEqual(m.variables["SHL"]["ADISCORD_economy_treasury"], 44.99)
        self.assertEqual(m.variables["287"]["SHL_furnace_stock"], 0)

    def test_automatic_supply_buys_only_missing_whole_packets_after_an_earlier_payout(self):
        m = self.machine
        country = m.variables["SHL"]
        country.update({
            "SHL_regular_supply": 1, "SHL_shift_policy": 1, "ADISCORD_economy_treasury": 0,
            "SHL_project_stage": 4, "SHL_tenth_running": 1, "SHL_tenth_stock": 1.25,
        })
        for state in range(287, 296):
            m.variables[str(state)].update({"SHL_furnace_running": 0, "SHL_furnace_stock": 0})
        for state, stock in (("287", 2), ("288", 0), ("290", 0.75), ("291", 1.25)):
            m.variables[state].update({"SHL_furnace_running": 1, "SHL_furnace_stock": stock})
        m.control["288"] = "KYZ"
        m.run("SHL_refresh_furnaces")
        self.assertEqual(country["SHL_preview_income"], 180)
        m.run("SHL_produce_period")
        self.assertEqual(country["ADISCORD_economy_current_month_action_costs"], 4 * 45)
        self.assertEqual(country["ADISCORD_economy_treasury"], 180)
        self.assertEqual(m.variables["290"]["SHL_furnace_stock"], 0.75)
        self.assertEqual(m.variables["291"]["SHL_furnace_stock"], 0.25)
        self.assertEqual(country["SHL_tenth_stock"], 0.25)
        self.assertEqual(m.variables["288"]["SHL_furnace_stock"], 0)
        self.assertEqual(m.variables["289"]["SHL_furnace_stock"], 0)

    def test_waiver_updates_forecast_inside_railway_reward_and_survives_refresh(self):
        m = self.machine
        country = m.variables["SHL"]
        country.update({"SHL_regular_supply": 1, "SHL_selected_furnace": 1, "ADISCORD_economy_treasury": 40})
        for state in range(287, 296):
            m.variables[str(state)].update({"SHL_furnace_running": int(state == 287), "SHL_furnace_stock": 0})
        m.run("SHL_refresh_furnaces")
        self.assertEqual((country["SHL_auto_packet_price"], country["SHL_preview_income"]), (45, 0))
        m.run("SHL_waive_packet_fee")
        self.assertEqual((country["SHL_auto_packet_price"], country["SHL_preview_income"]), (40, 20))
        m.focuses.add("SHL_houses_railway")
        m.run("SHL_refresh_selected_furnace")
        self.assertEqual((country["SHL_auto_packet_price"], country["SHL_preview_income"]), (40, 20))
        m.run("SHL_produce_period")
        self.assertEqual(country["ADISCORD_economy_treasury"], 60)

    def test_native_focus_tree_has_unique_reachable_focuses_on_free_cells(self):
        shared = shared_focuses()
        ids = []
        for name in FOCUS_TREE_SOURCES:
            ids.extend(tree_focuses(name))
        ids.extend(shared)
        # Preparation, five course sections, the defeat chapter and the shared
        # layer form one native tree; the war-for-the-South tree is separate.
        self.assertGreaterEqual(len(ids), 300)
        self.assertEqual(len(set(ids)), len(ids))
        focuses = whole_tree_focuses()
        roots = sorted(identifier for identifier, focus in shared.items() if not block(focus, "prerequisite"))
        references = [e.value for e in focus_tree("main") if e.key == "shared_focus"]
        self.assertEqual(sorted(references), roots)
        main_source = FOCUS_TREE_SOURCES["main"].read_text(encoding="utf-8")
        for name in (*COURSE_TREES, "defeated"):
            self.assertIn(f"# @include SHL/{name}/focuses.txt#{name}\n", main_source)
            self.assertTrue(FOCUS_TREE_SOURCES[name].read_text(encoding="utf-8").startswith(f"# @section {name}\n"), name)
        # The five course sections share their cells under the commit row: each
        # campaign state draws one of them, so cells are unique per state.
        for course, hegemon in COURSE_STATES:
            drawn = visible_focuses(course, hegemon)
            cells = [(int(scalar(f, "x")), int(scalar(f, "y"))) for f in drawn.values()]
            self.assertEqual(len(cells), len(set(cells)), (course, hegemon))
        for focus in focuses.values():
            for prerequisite in [e.value for e in focus if e.key == "prerequisite"]:
                for item in prerequisite:
                    self.assertIn(item.value, focuses)
            for exclusive in block(focus, "mutually_exclusive"):
                self.assertIn(exclusive.value, focuses)
        for name, output in FOCUS_OUTPUTS.items():
            self.assertTrue((ROOT / "common/national_focus" / output).is_file(), name)
        for name in COURSE_TREES:
            self.assertFalse((ROOT / f"common/national_focus/ADISCORD_SHL_{name}.txt").exists(), name)

    def test_war_tree_is_separate_and_shows_only_the_current_course(self):
        war = war_tree_focuses()
        self.assertFalse(set(war) & set(whole_tree_focuses()))
        prefixes = {"SHL_h_": 1, "SHL_c_": 2, "SHL_d_": 3, "SHL_r_": 4, "SHL_k_": 5, "SHL_n_": 0}

        def course_of(identifier):
            return next((value for prefix, value in prefixes.items() if identifier.startswith(prefix)), None)

        # Course branches share their cells: allow_branch shows one course at a time.
        common = [name for name in war if course_of(name) is None]
        for course in set(prefixes.values()):
            visible = common + [name for name in war if course_of(name) == course]
            cells = [(int(scalar(war[name], "x")), int(scalar(war[name], "y"))) for name in visible]
            self.assertEqual(len(cells), len(set(cells)), course)
            for row in {y for _, y in cells}:
                columns = sorted(x for x, y in cells if y == row)
                self.assertTrue(all(b - a >= 2 for a, b in zip(columns, columns[1:])), (course, row, columns))
        for identifier, focus in war.items():
            for prerequisite in [e.value for e in focus if e.key == "prerequisite"]:
                for item in prerequisite:
                    self.assertIn(item.value, war, identifier)
            course = course_of(identifier)
            allow = block(focus, "allow_branch")
            if course is None:
                self.assertFalse(allow, identifier)
                continue
            check = block(allow, "check_variable")
            self.assertEqual((scalar(check, "var"), scalar(check, "value")), ("SHL_political_course", str(course)), identifier)
        self.assertEqual(sum(1 for name in war if course_of(name) is not None), 23)
        self.assertGreaterEqual(len(war), 70)

    def test_hidden_courses_are_gated_by_their_crisis_flags(self):
        # The regency and commune sections hang from entry focuses that only the
        # crisis trigger opens; the crisis events and backing decisions commit the
        # same course and complete the entry so the section stays reachable.
        main = tree_focuses("main")
        for tree, trigger in (("regency", "SHL_can_back_crests"), ("commune", "SHL_can_back_shift_councils")):
            entry = main[COURSE_COMMIT_FOCUSES[tree]]
            available = block(entry, "available")
            self.assertIn((trigger, "yes"), [(e.key, e.value) for e in walk_entries(available)], tree)
            self.assertFalse(block(entry, "bypass"), tree)
            self.assertEqual(scalar(block(entry, "ai_will_do"), "base"), "0", tree)
            reward = block(entry, "completion_reward")
            commits = [e for e in walk_entries(reward) if e.key == f"SHL_commit_{tree}_course"]
            self.assertEqual(len(commits), 1, tree)
            self.assertNotIn(f"SHL_{tree}_prog_ending_a", main)
        self.assertNotIn("SHL_regency_council", main)
        self.assertNotIn("SHL_shift_councils", main)
        focuses = shl_focus_text()
        self.assertEqual(focuses.count("SHL_commit_regency_course = yes"), 1)
        self.assertEqual(focuses.count("SHL_commit_commune_course = yes"), 1)
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

    def test_cycle_survives_callback_that_crosses_midnight_early(self):
        m = self.machine
        m.run("SHL_schedule_cycle")
        m.flag_days["SHL"]["SHL_cycle_pending"] = 27
        m.run("SHL_run_cycle")
        self.assertEqual(m.variables["SHL"]["SHL_cycle_number"], 1)
        self.assertIn("SHL_cycle_pending", m.flags["SHL"])

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
        self.assertEqual(country["ADISCORD_economy_treasury"], 1810)

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

    def test_ai_preliminary_course_reaches_its_ratification_range(self):
        m = self.machine
        m.run("SHL_refresh_furnaces")
        for site in ("287", "288", "289"):
            m.run("SHL_extinguish_site", scope=site)
        m.run("SHL_refresh_furnaces")
        m.focuses.update({"SHL_workers_charter", "SHL_nur_directorate", "SHL_common_dispatch"})
        m.power_balance[BALANCE] = 0.45
        # A player keeps the drift and must use the Conclave levers.
        m.run("SHL_update_tensions")
        self.assertAlmostEqual(m.power_balance[BALANCE], 0.47)
        m.ai = True
        for _ in range(12):
            m.run("SHL_update_tensions")
        low, high = balance_ranges(BALANCE)["SHL_balance_equilibrium"]
        self.assertTrue(low <= m.power_balance[BALANCE] <= high)
        # The directorate can hold equilibrium through the next count.
        m.run("SHL_update_tensions")
        self.assertTrue(low <= m.power_balance[BALANCE] <= high)

        m.focuses.difference_update({"SHL_nur_directorate", "SHL_common_dispatch"})
        m.focuses.update({"SHL_open_conclave", "SHL_city_charters"})
        m.power_balance[BALANCE] = -0.30
        m.variables["SHL"]["SHL_city_support"] = 10
        for _ in range(8):
            m.run("SHL_update_tensions")
        low, high = balance_ranges(BALANCE)["SHL_balance_quarters_influence"]
        self.assertTrue(low <= m.power_balance[BALANCE] <= high)
        self.assertGreaterEqual(m.variables["SHL"]["SHL_city_support"], 30)

    def test_supplier_pressure_applies_one_reserve_surcharge(self):
        m = self.machine
        m.flags["SHL"].add("SHL_supplier_premium")
        m.variables["SHL"]["ADISCORD_economy_treasury"] = 69.99
        m.run("SHL_purchase_reserve")
        self.assertNotIn("SHL_reserve_stock", m.variables["SHL"])
        m.variables["SHL"]["ADISCORD_economy_treasury"] = 190
        m.run("SHL_purchase_reserve")
        self.assertEqual(m.variables["SHL"]["ADISCORD_economy_treasury"], 90)
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
        # The three ballot results share one parent and cannot be picked manually.
        for focus in ("SHL_admit_tenth_house", "SHL_rights_without_fire", "SHL_state_furnaces"):
            definition = focus_definition(focus)
            self.assertEqual(prerequisite_blocks(definition), [{"SHL_workers_charter"}], focus)
            self.assertFalse(self.m.matches(block(definition, "available"), "SHL"), focus)
        # Each platform root forks into its second step and its war mandate.
        for root, second, mandate in (
            ("SHL_new_house", "SHL_house_compromise", "SHL_house_war_mandate"),
            ("SHL_open_conclave", "SHL_city_charters", "SHL_city_war_mandate"),
            ("SHL_nur_directorate", "SHL_common_dispatch", "SHL_directorate_war_mandate"),
        ):
            self.assertEqual(prerequisite_blocks(focus_definition(second)), [{root}], second)
            self.assertEqual(prerequisite_blocks(focus_definition(mandate)), [{root}], mandate)
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

    def test_refused_water_and_port_agreements_do_not_send_new_offers(self):
        events = parse_clausewitz((ROOT / "events/ADISCORD_SHL_events.txt").read_text(encoding="utf-8"))
        for name, number, recipient, stem in (
            ("SHL_offer_water_treaty", 52, "KYZ", "water"),
            ("SHL_renew_veyr_partnership", 61, "GLP", "veyr"),
        ):
            with self.subTest(agreement=name):
                self.setUp()
                decision = decision_definition(name)
                event = next(e.value for e in events if e.key == "country_event" and scalar(e.value, "id") == f"ADISCORD_SHL.{number}")
                refusal = next(e.value for e in event if e.key == "option" and scalar(e.value, "name") == f"ADISCORD_SHL.{number}.b")
                self.m.execute(block(decision, "complete_effect"), "SHL", None)
                self.assertTrue(self.m.matches(block(event, "trigger"), recipient, "SHL"))
                self.m.execute(block(refusal, "hidden_effect"), recipient, "SHL")
                self.assertIn(f"SHL_{stem}_offer_declined", self.m.flags["SHL"])
                self.assertNotIn(f"SHL_{stem}_offer_pending", self.m.flags["SHL"])
                after = list(self.m.scheduled)
                self.m.execute(block(decision, "complete_effect"), "SHL", None)
                self.m.execute(block(refusal, "hidden_effect"), recipient, "SHL")
                self.assertEqual(self.m.scheduled, after)
                self.assertFalse(self.m.matches(block(event, "trigger"), recipient, "SHL"))
                self.assertFalse(self.m.matches(block(decision, "visible"), "SHL", None))

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
        self.m.run("SHL_start_qanat_war")
        self.assertIn(frozenset(("SHL", "KYZ")), self.m.wars)
        self.m.run("SHL_qanat_war_victory")
        self.m.run("SHL_qanat_war_victory")
        self.assertEqual(self.m.ownership["280"], "SHL")
        self.assertEqual(self.m.ownership["285"], "MZR")
        self.assertEqual(c["SHL_water_crisis"], 4)
        self.assertEqual(self.m.scheduled.count("ADISCORD_SHL.57"), 1)
        self.assertNotIn(frozenset(("SHL", "KYZ")), self.m.wars)

    def test_qanat_war_defeat_cedes_arbin_and_imposes_quota(self):
        c = self.country()
        c["SHL_water_crisis"] = 1
        self.m.focuses.add("SHL_qanat_guard")
        self.m.run("SHL_start_qanat_war")
        self.m.run("SHL_qanat_war_defeat")
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
        c["SHL_keizan_state"] = 1
        self.m.run("SHL_keizan_refuse")
        self.assertIn("SHL_keizan_deadline", self.m.missions)
        self.m.run("SHL_keizan_buyout")
        self.assertEqual(c["SHL_keizan_state"], 3)
        self.assertNotIn("SHL_keizan_deadline", self.m.missions)
        self.m.run("SHL_start_kyz_war")
        self.assertNotIn(frozenset(("KYZ", "SHL")), self.m.wars)

    def test_busy_mazar_postpones_instead_of_discarding(self):
        c = self.country()
        c["SHL_keizan_state"] = 5
        c["SHL_cycle_number"] = 20
        self.m.countries["KYZ"]["has_war"] = True
        self.m.run("SHL_start_kyz_war")
        self.assertEqual(c["SHL_keizan_state"], 2)
        self.assertEqual(c["SHL_keizan_repeat_cycle"], 24)

    def test_mazar_defeat_takes_two_fifths_of_a_positive_treasury(self):
        c = self.country()
        c["SHL_keizan_state"] = 5
        self.m.run("SHL_start_kyz_war")
        self.assertIn(frozenset(("KYZ", "SHL")), self.m.wars)
        self.m.run("SHL_kyz_war_defeat")
        self.assertAlmostEqual(c["ADISCORD_economy_treasury"], 600)
        self.assertEqual(c["SHL_keizan_state"], 3)
        self.assertIn("SHL_keizan_ration", self.m.ideas)
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
        self.country()["SHL_war_kyz"] = 2
        self.m.wars.add(frozenset(("SHL", "KYZ")))
        self.m.run("SHL_request_golden_alliance")
        self.m.run("SHL_join_golden_gate", scope="GLP")
        self.assertEqual(self.m.factions["GLP"], "SHL")
        self.assertIn(frozenset(("GLP", "KYZ")), self.m.wars)
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

    def prepare(self, partner="MZR"):
        if partner != "MZR":
            # The refusal hands Mazar its grievance first; a subject Mazar
            # leaves the other partner as the only candidate.
            self.m.countries["MZR"]["is_subject"] = True
        self.m.flags[partner].add("SHL_kyz_border_grievance")
        self.country()["SHL_keizan_state"] = 1
        self.m.run("SHL_keizan_refuse")

    def start(self, partner="MZR", ally=None):
        self.prepare(partner)
        self.m.run("SHL_accept_kyz_pact", scope=partner)
        if ally:
            self.m.factions.update({"SHL": "SHL", ally: "SHL"})
        self.m.run("SHL_start_kyz_war")

    def event(self, number):
        events = parse_clausewitz((ROOT / "events/ADISCORD_SHL_events.txt").read_text(encoding="utf-8"))
        return next(e.value for e in events if e.key == "country_event" and scalar(e.value, "id") == f"ADISCORD_SHL.{number}")

    def capitulate(self, loser, winner):
        source = (ROOT / "common/on_actions/09_ADISCORD_scripted_peace_on_actions.txt").read_text(encoding="utf-8")
        section = source.split("# BEGIN shahrabad:on_capitulation", 1)[1].split("# END shahrabad:on_capitulation", 1)[0]
        self.m.root_scope = loser
        self.m.execute(parse_clausewitz(section), loser, winner)

    def test_only_actual_military_action_creates_a_grievance(self):
        # Keizan is the aggressor of the ration war, so only Veir's limited war
        # can leave a flank grievance; Mazar has no limited war with Shahrabad.
        for partner, crisis, focus, start, armistice in (
            ("GLP", "SHL_veyr_crisis", "SHL_veyr_ultimatum", "SHL_start_glp_war", "SHL_glp_war_armistice"),
        ):
            with self.subTest(partner=partner):
                self.setUp()
                self.m.countries["MZR"]["is_subject"] = True
                self.country()[crisis] = 1
                self.m.focuses.add(focus)
                self.country()["SHL_keizan_state"] = 1
                self.m.run("SHL_keizan_refuse")
                self.assertNotIn("ADISCORD_SHL.124", self.m.scheduled)
                self.m.run(start)
                self.m.run(armistice)
                self.assertIn("SHL_kyz_border_grievance", self.m.flags[partner])
                self.m.run("SHL_clear_kyz_diplomacy")
                self.m.run("SHL_prepare_kyz_partner")
                self.assertIn("SHL_kyz_pact_pending", self.m.flags[partner])

    def test_at_most_one_announced_candidate_and_no_replacement_after_refusal(self):
        self.m.flags["GLP"].add("SHL_kyz_border_grievance")
        self.prepare()
        self.m.run("SHL_prepare_kyz_partner")
        self.assertEqual(self.m.scheduled.count("ADISCORD_SHL.124"), 1)
        self.assertIn("SHL_kyz_pact_pending", self.m.flags["MZR"])
        self.assertNotIn("SHL_kyz_pact_pending", self.m.flags["GLP"])
        first_option = block(self.event(125), "option")
        self.m.execute(block(first_option, "hidden_effect"), "MZR")
        self.m.run("SHL_prepare_kyz_partner")
        self.m.run("SHL_start_kyz_war")
        self.assertNotIn(frozenset(("MZR", "SHL")), self.m.wars)
        self.assertNotIn(frozenset(("GLP", "SHL")), self.m.wars)

    def test_subject_foreign_faction_war_or_lost_border_blocks_candidate(self):
        for reason in ("subject", "faction", "war", "border", "absent", "mazar_faction"):
            with self.subTest(reason=reason):
                self.setUp()
                if reason == "subject":
                    self.m.countries["MZR"]["is_subject"] = True
                elif reason == "faction":
                    self.m.factions["MZR"] = "VAL"
                elif reason == "war":
                    self.m.wars.add(frozenset(("MZR", "VAL")))
                elif reason == "border":
                    self.m.neighbours.remove("MZR")
                elif reason == "absent":
                    self.m.countries["MZR"]["exists"] = False
                else:
                    self.m.factions["KYZ"] = "VAL"
                self.prepare()
                self.assertNotIn("ADISCORD_SHL.125", self.m.scheduled)

    def test_both_candidates_join_the_existing_war_with_no_extra_declaration(self):
        for partner, ally in (("MZR", "GLP"), ("GLP", "MZR")):
            with self.subTest(partner=partner):
                self.setUp()
                self.start(partner, ally)
                self.assertEqual(self.m.factions[partner], "KYZ")
                self.assertEqual(self.m.majors, {"SHL", "KYZ"})
                self.assertEqual(len([call for call in self.m.calls if call[0] == "declare_war_on"]), 1)
                for opponent in ("KYZ", partner):
                    for friend in ("SHL", ally):
                        self.assertIn(frozenset((opponent, friend)), self.m.wars)
                self.assertNotIn("SHL_kyz_pact_pending", self.m.flags[partner])

    def test_offensive_warns_during_the_existing_28_day_mobilization(self):
        self.m.flags["GLP"].add("SHL_kyz_border_grievance")
        self.m.focuses.add("SHL_no_more_rations")
        self.m.run("SHL_begin_kyz_mobilization")
        self.assertIn("ADISCORD_SHL.124", self.m.scheduled)
        self.assertFalse(self.m.wars)
        self.m.run("SHL_accept_kyz_pact", scope="GLP")
        self.m.run("SHL_finish_kyz_mobilization")
        self.assertIn(("declare_war_on", "SHL", "KYZ"), self.m.calls)
        self.assertIn(frozenset(("GLP", "SHL")), self.m.wars)

    def test_neutrality_payment_requires_choice_and_is_exactly_once(self):
        for partner in ("MZR", "GLP"):
            with self.subTest(partner=partner):
                self.setUp()
                self.prepare(partner)
                self.m.run("SHL_accept_kyz_pact", scope=partner)
                self.country()["ADISCORD_economy_treasury"] = 100
                self.m.values["political_power"] = 30
                self.m.run("SHL_request_kyz_neutrality")
                self.m.run("SHL_request_kyz_neutrality")
                self.assertEqual(self.m.scheduled.count("ADISCORD_SHL.126"), 1)
                self.assertEqual(self.country()["ADISCORD_economy_treasury"], 100)
                self.m.run("SHL_accept_kyz_neutrality", scope=partner)
                self.m.run("SHL_accept_kyz_neutrality", scope=partner)
                self.assertEqual(self.country()["ADISCORD_economy_treasury"], 0)
                self.assertEqual(self.m.values["political_power"], 0)
                self.assertEqual(self.m.variables[partner]["ADISCORD_economy_treasury"], 100)
                self.m.run("SHL_accept_kyz_pact", scope=partner)
                self.m.run("SHL_start_kyz_war")
                self.assertNotIn(frozenset((partner, "SHL")), self.m.wars)

    def test_changed_funds_and_late_answers_never_charge_or_change_sides(self):
        for reason in ("treasury", "political_power", "war", "peace", "faction", "subject"):
            with self.subTest(reason=reason):
                self.setUp()
                self.prepare()
                self.m.run("SHL_accept_kyz_pact", scope="MZR")
                self.m.run("SHL_request_kyz_neutrality")
                if reason == "treasury":
                    self.country()["ADISCORD_economy_treasury"] = 99.9
                elif reason == "political_power":
                    self.m.values["political_power"] = 29.9
                elif reason == "war":
                    self.m.run("SHL_start_kyz_war")
                elif reason == "peace":
                    self.m.run("SHL_keizan_buyout")
                elif reason == "faction":
                    self.m.factions["MZR"] = "VAL"
                else:
                    self.m.countries["MZR"]["is_subject"] = True
                balances = (self.country()["ADISCORD_economy_treasury"], self.m.values["political_power"])
                self.m.run("SHL_accept_kyz_neutrality", scope="MZR")
                self.assertEqual(balances, (self.country()["ADISCORD_economy_treasury"], self.m.values["political_power"]))
                self.assertNotIn("ADISCORD_economy_treasury", self.m.variables["MZR"])
                if reason == "war":
                    self.assertIn(frozenset(("MZR", "SHL")), self.m.wars)

    def test_existing_treaties_and_alliance_supersede_the_pact(self):
        for partner, effect, course in (
            ("GLP", "SHL_sign_veyr_union", 0),
            ("MZR", "SHL_join_southern_compact", 2),
            ("GLP", "SHL_join_golden_gate", 1),
        ):
            with self.subTest(effect=effect):
                self.setUp()
                self.prepare(partner)
                self.m.run("SHL_accept_kyz_pact", scope=partner)
                self.country().update({"SHL_water_crisis": 1, "SHL_political_course": course})
                self.m.flags["SHL"].update({"SHL_southern_alliance_pending", "SHL_golden_alliance_pending"})
                self.m.run(effect, scope=partner)
                self.assertNotIn("SHL_kyz_border_grievance", self.m.flags[partner])
                self.m.run("SHL_start_kyz_war")
                self.assertNotIn(frozenset((partner, "SHL")), self.m.wars)

    def test_late_trade_offer_does_not_reconcile_an_active_enemy(self):
        self.start("GLP")
        self.m.run("SHL_sign_veyr_union", scope="GLP")
        self.assertNotIn("SHL_veyr_partner", self.m.flags["SHL"])
        self.assertIn("SHL_kyz_war_partner", self.m.flags["GLP"])

    def test_every_settlement_closes_both_fronts_and_preserves_unrelated_wars(self):
        for effect in ("SHL_kyz_war_victory", "SHL_kyz_war_defeat", "SHL_kyz_war_armistice", "SHL_close_external_kyz_war"):
            with self.subTest(effect=effect):
                self.setUp()
                self.start("MZR", "GLP")
                foreign_war = frozenset(("MZR", "VAL"))
                self.m.wars.add(foreign_war)
                if effect == "SHL_close_external_kyz_war":
                    self.m.countries["KYZ"]["is_subject"] = True
                self.m.run(effect)
                self.assertEqual(self.m.wars, {foreign_war})
                self.assertNotIn("KYZ", self.m.factions)
                self.assertEqual(self.m.factions["GLP"], "SHL")
                self.assertFalse(self.m.majors)
                for tag in ("MZR", "GLP"):
                    self.assertFalse(self.m.flags[tag] & {"SHL_kyz_war_partner", "SHL_kyz_shl_partner", "SHL_kyz_neutrality_pending"})

    def test_neighbour_capitulations_remain_occupied_until_principal_settlement(self):
        for loser, winner in (("MZR", "SHL"), ("MZR", "GLP"), ("GLP", "MZR")):
            with self.subTest(loser=loser, winner=winner):
                self.setUp()
                self.start("MZR", "GLP")
                before = set(self.m.wars)
                self.capitulate(loser, winner)
                self.assertIn("skip_default_capitulation", self.m.global_flags)
                self.assertEqual(self.m.wars, before)
                self.assertEqual(self.country()["SHL_war_kyz"], 2)

    def test_shahrabad_defeat_by_partner_uses_mazar_terms(self):
        self.start()
        self.capitulate("SHL", "MZR")
        self.assertEqual(self.country()["SHL_kyz_outcome"], 4)
        self.assertEqual(self.country()["ADISCORD_economy_treasury"], 600)
        self.assertFalse(self.m.wars)
        self.assertEqual(self.m.ownership["707"], "SHL")

    def test_mazar_defeat_by_shahrabad_ally_ends_partner_war(self):
        self.start("MZR", "GLP")
        self.capitulate("KYZ", "GLP")
        self.assertEqual(self.country()["SHL_kyz_outcome"], 1)
        self.assertFalse(self.m.wars)
        self.assertEqual(self.m.ownership["280"], "SHL")
        # The partner's own land is not a war goal of the ration war.
        self.assertEqual(self.m.ownership["269"], "MZR")

    def test_absent_or_busy_partner_is_not_replaced_at_declaration(self):
        self.m.flags["GLP"].add("SHL_kyz_border_grievance")
        self.prepare()
        self.m.run("SHL_accept_kyz_pact", scope="MZR")
        self.m.countries["MZR"]["is_subject"] = True
        self.m.run("SHL_start_kyz_war")
        self.assertEqual(self.m.wars, {frozenset(("SHL", "KYZ"))})

    def test_postponement_and_cancelled_preparation_clear_open_offers(self):
        self.prepare()
        self.m.run("SHL_accept_kyz_pact", scope="MZR")
        self.m.countries["KYZ"]["has_war"] = True
        self.m.run("SHL_start_kyz_war")
        self.assertNotIn("SHL_kyz_pact_signed", self.m.flags["MZR"])
        self.assertNotIn("SHL_kyz_diplomacy_started", self.m.flags["SHL"])
        self.m.run("SHL_accept_kyz_pact", scope="MZR")
        self.assertNotIn("SHL_kyz_pact_signed", self.m.flags["MZR"])

    def test_cancelled_offensive_clears_invitation_without_a_remaining_deadline(self):
        self.m.flags["MZR"].add("SHL_kyz_border_grievance")
        self.m.focuses.add("SHL_no_more_rations")
        self.m.run("SHL_begin_kyz_mobilization")
        self.m.run("SHL_request_kyz_neutrality")
        self.m.run("SHL_cancel_kyz_mobilization")
        self.assertNotIn("SHL_kyz_diplomacy_started", self.m.flags["SHL"])
        self.assertNotIn("SHL_kyz_pact_pending", self.m.flags["MZR"])
        self.assertNotIn("SHL_kyz_neutrality_pending", self.m.flags["MZR"])

    def test_annexed_mazar_cleans_up_the_pacts_successor_leader(self):
        self.start()
        self.m.countries["KYZ"]["exists"] = False
        self.m.factions.pop("KYZ")
        self.m.factions["MZR"] = "MZR"
        self.m.run("SHL_close_external_kyz_war")
        self.assertFalse(self.m.factions)
        self.assertFalse(self.m.wars)
        self.assertFalse(self.m.majors)

    def test_nonparticipant_war_and_preexisting_major_are_preserved(self):
        self.m.majors.add("KYZ")
        self.country()["SHL_keizan_state"] = 5
        self.m.run("SHL_start_kyz_war")
        foreign_war = frozenset(("MZR", "KYZ"))
        self.m.wars.add(foreign_war)
        self.m.run("SHL_kyz_war_armistice")
        self.assertEqual(self.m.wars, {foreign_war})
        self.assertEqual(self.m.majors, {"KYZ"})

    def test_major_release_preserves_another_campaign_and_transfers_the_khan_receipt(self):
        for country in ("SHL", "KYZ"):
            for other_receipt, keeps_major, khan_receipt in (
                (None, False, False),
                ("ADISCORD_south_added_major", True, False),
                ("RUS_crisis_defender", True, True),
            ):
                with self.subTest(country=country, other_receipt=other_receipt):
                    self.setUp()
                    self.m.majors.add(country)
                    self.m.flags[country].add("SHL_kyz_added_major")
                    if other_receipt:
                        self.m.flags[country].add(other_receipt)
                    other_country = "KYZ" if country == "SHL" else "SHL"
                    self.m.flags[other_country].add("ADISCORD_west_added_major")
                    self.m.run("SHL_release_kyz_principal", scope=country)
                    self.m.run("SHL_release_kyz_principal", scope=country)
                    self.assertNotIn("SHL_kyz_added_major", self.m.flags[country])
                    self.assertEqual(country in self.m.majors, keeps_major)
                    self.assertEqual("RUS_crisis_added_major" in self.m.flags[country], khan_receipt)
                    if other_receipt:
                        self.assertIn(other_receipt, self.m.flags[country])

    def test_neutrality_timeout_is_free_and_keeps_the_existing_pact(self):
        self.prepare()
        self.m.run("SHL_accept_kyz_pact", scope="MZR")
        self.m.run("SHL_request_kyz_neutrality")
        self.m.execute(block(block(self.event(126), "option"), "hidden_effect"), "MZR")
        self.assertEqual(self.country()["ADISCORD_economy_treasury"], 1000)
        self.assertEqual(self.m.values["political_power"], 200)
        self.assertIn("SHL_kyz_pact_signed", self.m.flags["MZR"])
        self.assertNotIn("SHL_kyz_neutrality_pending", self.m.flags["MZR"])


class SouthernCampaignTests(unittest.TestCase):
    setUp = CrisisLayerTests.setUp
    country = CrisisLayerTests.country

    def ready(self, course=1, outcome=6):
        c = self.country()
        c.update({"SHL_political_course": course, "SHL_keizan_state": 3, "SHL_kyz_outcome": outcome})
        self.m.focuses.add("SHL_peace_has_a_price")
        return c

    def captured_cisterns(self, course):
        self.ready(course, 1)
        for state in ("280", "284"):
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
        self.assertTrue({"SHL_hereditary_seats", "SHL_external_freight"} <= ideas)
        self.assertNotIn("SHL_divided_guard", ideas)
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
        self.assertEqual(scalar(block(focus_definition("SHL_southern_watch"), "completion_reward"), "SHL_shahrabad_army_reform"), "yes")

    def test_starting_reforms_apply_the_displayed_deltas_and_keep_campaign_progress(self):
        self.m.flags["SHL"].discard("SHL_furnaces_initialized")
        self.m.run("SHL_initialize_furnaces")
        dynamics = dict((e.key, e.value) for e in parse_clausewitz(
            (ROOT / "common/dynamic_modifiers/ADISCORD_dynamic_modifiers_SHL.txt").read_text(encoding="utf-8")))
        idea_file = ROOT / "common/ideas/ADISCORD_southern_desert_ideas.txt"
        country_ideas = block(block(parse_clausewitz(idea_file.read_text(encoding="utf-8")), "ideas"), "country")
        for spirit, opening, focuses in (
            ("SHL_cartel_influence", {"political_power_gain": -0.20, "consumer_goods_factor": 0.10},
             ("SHL_shift_arbitration",)),
            ("SHL_shahrabad_army", {"army_org_factor": -0.10, "planning_speed": -0.20},
             ("SHL_railway_guard", "SHL_southern_watch", "SHL_conclave_army")),
            ("SHL_conclave_industry", {"industrial_capacity_factory": -0.10, "production_speed_buildings_factor": -0.10},
             ("SHL_houses_railway", "SHL_metal_market")),
        ):
            self.assertIn(spirit, self.m.dynamic)
            variables = {key: scalar(dynamics[spirit], key) for key in opening}
            preview = block(block(country_ideas, spirit + "_reform_preview"), "modifier")
            deltas = {e.key: float(e.value) for e in preview}
            self.assertEqual(deltas, {key: -value / 2 for key, value in opening.items()})
            for step, focus in enumerate(focuses, 1):
                effect = spirit + "_reform"
                self.assertEqual(scalar(block(focus_definition(focus), "completion_reward"), effect), "yes")
                for key, var in variables.items():
                    self.assertAlmostEqual(self.country()[var], opening[key] + (step - 1) * deltas[key])
                self.m.run(effect)
                self.m.run("SHL_initialize_furnaces")
                self.m.run("SHL_refresh_furnaces")
                for key, var in variables.items():
                    self.assertAlmostEqual(self.country()[var], opening[key] + step * deltas[key])
        self.assertEqual(scalar(block(focus_definition("SHL_counting_chamber"), "completion_reward"),
                                "SHL_cartel_influence_reform"), "yes")
        self.assertEqual(prerequisite_blocks(focus_definition("SHL_incident_office")),
                         [{"SHL_shift_arbitration", "SHL_counting_chamber"}])
        finish = block(focus_definition("SHL_incident_office"), "completion_reward")
        self.m.execute([entry for entry in finish if entry.key == "if"], "SHL")
        self.m.run("SHL_refresh_furnaces")
        self.assertNotIn("SHL_cartel_influence", self.m.dynamic)
        self.assertNotIn("SHL_cartel_pp", self.country())
        self.assertNotIn("SHL_cartel_consumer_goods", self.country())

    def test_trade_category_and_ai_wartime_reserve(self):
        path = ROOT / "common/decisions/ADISCORD_SHL_decisions.txt"
        categories = parse_clausewitz(path.read_text(encoding="utf-8"))
        self.assertEqual([c.key for c in categories if block(c.value, "SHL_trade_mission")], ["SHL_caravans"])
        panel = parse_clausewitz((ROOT / "common/decisions/categories/ADISCORD_decision_categories_SHL.txt")
                                 .read_text(encoding="utf-8"))
        visible = block(block(panel, "SHL_caravans"), "visible")
        self.assertFalse(self.m.matches(visible, "SHL"))
        self.m.focuses.add("SHL_sw_keep_the_markets")
        self.assertTrue(self.m.matches(visible, "SHL"))
        for cargo, load in (("rifles", 10000), ("kits", 2000), ("wholesale", 100000)):
            decision = decision_definition("SHL_road_send_" + cargo)
            self.assertFalse(self.m.matches(block(decision, "visible"), "SHL"))
            if cargo == "kits":
                continue
            reserve = block(block(decision, "ai_will_do"), "modifier")
            condition = [entry for entry in reserve if entry.key != "factor"]
            self.assertEqual(scalar(reserve, "factor"), "0")
            self.m.equipment["SHL", "infantry_equipment"] = load + 2699
            self.assertTrue(self.m.matches(condition, "SHL"))
            self.m.equipment["SHL", "infantry_equipment"] += 1
            self.assertFalse(self.m.matches(condition, "SHL"))
        self.m.focuses.add("SHL_law_of_continuous_fire")
        self.assertTrue(self.m.matches(visible, "SHL"))
        self.assertTrue(self.m.matches(block(decision_definition("SHL_road_send_wholesale"), "visible"), "SHL"))

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
        self.assertEqual(scalar(decision_definition("SHL_keizan_deadline"), "days_mission_timeout"), "60")

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
        self.m.run("SHL_begin_kyz_mobilization")
        self.assertIn("ADISCORD_SHL.111", self.m.scheduled)
        self.m.run("SHL_finish_kyz_mobilization")
        self.m.run("SHL_finish_kyz_mobilization")
        declarations = [call for call in self.m.calls if isinstance(call, tuple) and call[0] == "declare_war_on"]
        self.assertEqual(declarations, [("declare_war_on", "SHL", "KYZ")])
        self.assertEqual(self.m.values["political_power"], 150)

    def test_peace_during_mobilization_refunds_once_and_prevents_war(self):
        self.m.focuses.add("SHL_no_more_rations")
        self.m.values["political_power"] -= 50
        self.m.run("SHL_begin_kyz_mobilization")
        self.country()["SHL_keizan_state"] = 5
        self.m.run("SHL_keizan_buyout")
        self.m.run("SHL_finish_kyz_mobilization")
        self.m.run("SHL_cancel_kyz_mobilization")
        self.assertEqual(self.m.values["political_power"], 150)
        self.assertEqual(self.country()["ADISCORD_economy_treasury"], 650)
        self.assertEqual(self.m.wars, set())

    def test_paid_reserve_can_arrive_during_war_and_cleanup_removes_bonuses(self):
        self.convoy(True)
        self.country()["SHL_keizan_state"] = 5
        self.m.run("SHL_start_kyz_war")
        self.pour()
        self.assertIn("SHL_prepared_columns", self.m.ideas)
        self.assertNotIn("SHL_campaign_reserve", self.country())
        self.m.run("SHL_kyz_war_armistice")
        self.assertNotIn("SHL_prepared_columns", self.m.ideas)
        self.assertEqual(self.m.majors, set())

    def test_directorate_can_prepare_the_next_war_after_settling_mazar(self):
        for neighbour, crisis, focus, start in (
            ("KYZ", "SHL_water_crisis", "SHL_right_to_water", "SHL_start_qanat_war"),
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
                self.country()["SHL_keizan_state"] = 1
                self.m.flags["SHL"].add("SHL_campaign_assistance_used")
                self.m.ideas.add("SHL_prepared_columns")
                if parallel:
                    self.m.wars.add(frozenset(("SHL", "MZR")))
                self.m.run("SHL_keizan_pay_final")
                self.assertEqual("SHL_campaign_assistance_used" in self.m.flags["SHL"], parallel)
                self.assertEqual("SHL_prepared_columns" in self.m.ideas, parallel)
                self.assertEqual(self.country()["SHL_keizan_state"], 3)

    def test_objectives_accept_fighting_allies_and_reject_other_occupiers(self):
        self.country()["SHL_keizan_state"] = 5
        self.m.factions.update({"SHL": "SHL", "MZR": "SHL"})
        self.m.run("SHL_start_kyz_war")
        self.m.control.update({"280": "MZR", "284": "SHL", "707": "MZR"})
        trigger = self.m.triggers["SHL_kyz_objectives_held"]
        self.assertTrue(self.m.matches(trigger, "SHL"))
        self.m.wars.discard(frozenset(("MZR", "KYZ")))
        self.assertFalse(self.m.matches(trigger, "SHL"))
        self.m.control.update({"280": "SHL", "707": "SHL"})
        self.m.run("SHL_front_check")
        self.assertIn("SHL_kyz_front_hold", self.m.missions)
        self.m.execute(block(decision_definition("SHL_kyz_front_hold"), "timeout_effect"), "SHL")
        self.assertEqual(self.m.ownership["280"], "SHL")
        self.assertEqual(self.country()["SHL_kyz_outcome"], 1)
        self.assertFalse(self.m.wars)

    def test_lost_objective_cancels_corridor_without_victory(self):
        self.country()["SHL_keizan_state"] = 5
        self.m.run("SHL_start_kyz_war")
        self.m.control["280"] = "SHL"
        self.m.run("SHL_front_check")
        self.assertNotIn("SHL_kyz_front_hold", self.m.missions)
        self.m.execute(block(decision_definition("SHL_kyz_front_hold"), "timeout_effect"), "SHL")
        self.assertEqual(self.m.ownership["280"], "KYZ")
        self.assertNotIn("SHL_kyz_outcome", self.country())

    def test_permanent_loss_of_threat_opens_peace_but_temporary_war_waits(self):
        self.m.countries["KYZ"]["has_war"] = True
        self.m.run("SHL_close_lost_keizan_threat")
        self.assertNotEqual(self.country().get("SHL_keizan_state"), 3)
        for change in ("absent", "subject", "lost_both_cisterns", "ally"):
            with self.subTest(change=change):
                self.setUp()
                if change == "absent":
                    self.m.countries["KYZ"]["exists"] = False
                elif change == "subject":
                    self.m.countries["KYZ"]["is_subject"] = True
                elif change == "lost_both_cisterns":
                    # One cistern left to Keizan keeps the ration claim alive.
                    self.m.ownership["280"] = "AZH"
                    self.m.run("SHL_close_lost_keizan_threat")
                    self.assertNotEqual(self.country().get("SHL_keizan_state"), 3)
                    self.m.ownership["284"] = "AZH"
                else:
                    self.m.factions.update({"SHL": "SHL", "KYZ": "SHL"})
                self.m.run("SHL_close_lost_keizan_threat")
                self.assertEqual(self.country()["SHL_kyz_outcome"], 7)
                self.assertEqual(self.country()["SHL_keizan_state"], 3)
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
                self.assertEqual(self.m.ownership["280"], "KYZ")
                self.assertEqual(c["SHL_kyz_outcome"], 2)

    def test_charter_requires_recipient_choice_and_rechecks_changed_course(self):
        self.captured_cisterns(2)
        self.m.run("SHL_request_cistern_charter")
        self.assertEqual(self.m.ownership["280"], "SHL")
        self.country()["SHL_political_course"] = 3
        self.m.run("SHL_accept_cistern_charter", scope="KYZ")
        self.assertEqual(self.m.ownership["280"], "SHL")
        self.assertNotIn("KYZ", self.m.factions)
        self.country()["SHL_political_course"] = 2
        self.m.run("SHL_request_cistern_charter")
        self.m.run("SHL_accept_cistern_charter", scope="KYZ")
        self.assertEqual(self.m.ownership["280"], "KYZ")
        self.assertEqual(self.m.factions["KYZ"], "SHL")
        self.assertFalse(self.m.countries["KYZ"]["is_subject"])

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
                self.m.run("SHL_accept_cistern_charter", scope="KYZ")
                self.equipment()
                self.m.run("SHL_begin_southern_programme", target="280")
                self.m.run("SHL_finish_southern_programme")
                self.assertEqual(self.m.ownership["280"], "KYZ")
                self.assertNotIn(("280", "SHL"), self.m.cores)
                if course == 5:
                    self.assertEqual(self.m.unit_owners, [("280", "KYZ")])
                    self.assertEqual(self.m.manpower, 0)

    def test_project_cancellation_preserves_exact_escrow_on_all_terminal_paths(self):
        for reason in ("war", "course", "occupation", "alliance"):
            with self.subTest(reason=reason):
                self.setUp()
                self.ready(5, 3)
                self.m.factions.update({"SHL": "SHL", "KYZ": "SHL"})
                self.equipment()
                self.m.run("SHL_begin_southern_programme", target="280")
                if reason == "war":
                    self.m.wars.add(frozenset(("SHL", "GLP")))
                elif reason == "course":
                    self.country()["SHL_political_course"] = 3
                elif reason == "occupation":
                    self.m.control["280"] = "AZH"
                else:
                    del self.m.factions["KYZ"]
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
        self.m.execute(block(default, "hidden_effect"), "KYZ")
        self.assertEqual(self.m.ownership["280"], "SHL")
        self.assertNotIn("SHL_cistern_charter_pending", self.m.flags["SHL"])
        self.assertNotIn("KYZ", self.m.factions)

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

    def test_party_rifle_invoice_keeps_the_quoted_lot_until_settlement(self):
        event = self.event("ADISCORD_SHL.205")
        decline, standard, bulk = [entry.value for entry in event if entry.key == "option"]
        self.assertEqual(scalar(decline, "name"), "ADISCORD_SHL.205.b")
        offers = [
            decision_definition("SHL_offer_party_rifles"),
            decision_definition("SHL_offer_party_rifles_bulk"),
        ]
        for offer in offers:
            self.assertEqual(scalar(offer, "days_re_enable"), "30")
        for lot, (amount, price, accept, other) in enumerate((
            (2700, 100, standard, bulk),
            (13500, 300, bulk, standard),
        )):
            with self.subTest(amount=amount):
                self.setUp()
                self.m.triggers.update(shared_definitions(
                    "common/scripted_triggers/ADISCORD_VAL_rework_triggers.txt",
                    ("VAL_stelander_civil_war_active",),
                ))
                self.m.effects.update(shared_definitions(
                    "common/scripted_effects/ADISCORD_shared_action_effects.txt",
                    ("ADISCORD_economy_receive_300", "ADISCORD_economy_spend_100",
                     "ADISCORD_economy_spend_300"),
                ))
                self.m.countries.update({tag: {"exists": True} for tag in ("STP", "STS")})
                self.m.global_flags.add("STP_cw_started")
                self.m.focuses.add("SHL_law_of_continuous_fire")
                war = frozenset(("STP", "STS"))
                self.m.wars.add(war)
                rifles = ("SHL", "infantry_equipment")
                delivered = ("STP", "infantry_equipment")
                treasury = "ADISCORD_economy_treasury"
                seller = self.country()
                buyer = self.m.variables["STP"]
                initial = seller.get(treasury, 0)
                buyer[treasury] = 300
                self.m.equipment[rifles] = 13500
                offer_effect = block(offers[lot], "complete_effect")

                def available(offer):
                    return self.m.matches(block(offer, "available"), "SHL")

                def select(option):
                    self.m.execute(block(option, "hidden_effect"), "STP")

                self.assertTrue(all(available(offer) for offer in offers))
                self.m.execute(offer_effect, "SHL")
                self.assertFalse(any(available(offer) for offer in offers))
                self.m.execute(block(offers[1 - lot], "complete_effect"), "SHL")
                self.assertFalse(self.m.matches(block(other, "trigger"), "STP"))
                select(other)
                self.assertEqual(buyer[treasury], 300)
                self.assertEqual(self.m.equipment[delivered], 0)
                select(decline)
                select(accept)
                self.assertEqual(seller.get(treasury, 0), initial)
                self.assertEqual(self.m.equipment[rifles], 13500)
                self.assertFalse(any(available(offer) for offer in offers))

                # The next contact opens when the common 30-day flag expires.
                hold = next(e.value for e in self.m.effects["SHL_send_party_invoice"] if e.key == "set_country_flag")
                self.assertEqual((scalar(hold, "flag"), scalar(hold, "days")), ("SHL_party_order_cooldown", "30"))
                self.m.flags["SHL"].discard("SHL_party_order_cooldown")
                self.m.equipment[rifles] = amount
                buyer[treasury] = price
                self.assertTrue(available(offers[lot]))
                if lot == 0:
                    self.assertFalse(available(offers[1]))
                self.m.execute(offer_effect, "SHL")
                for stock, funds, front in (
                    (amount - 0.1, price, True), (amount, price - 0.1, True), (amount, price, False),
                ):
                    self.m.equipment[rifles] = stock
                    buyer[treasury] = funds
                    if not front:
                        self.m.wars.discard(war)
                    self.assertFalse(self.m.matches(block(accept, "trigger"), "STP"))
                    select(accept)
                    self.assertEqual(buyer[treasury], funds)
                    self.assertEqual(self.m.equipment[rifles], stock)
                self.m.wars.add(war)
                self.assertTrue(self.m.matches(block(accept, "trigger"), "STP"))
                select(accept)
                select(accept)
                self.assertEqual(buyer[treasury], 0)
                self.assertEqual(seller[treasury], initial + price)
                self.assertEqual(self.m.equipment[rifles], 0)
                self.assertEqual(self.m.equipment[delivered], amount)
                self.assertEqual(buyer["ADISCORD_economy_current_month_action_costs"], price)
                self.assertEqual(seller["ADISCORD_economy_current_month_action_income"], price)

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
        # The commune has no crests: the derived pressure reads zero.
        self.assertEqual(self.country()["SHL_house_pressure"], 0)

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
        # Houses at 100 absorb part of the house course's gain; the city and
        # the directorate keep Arbin (+15) and Darban (+20) on their side.
        for focus, effect, expected in (
            ("SHL_new_house", "SHL_commit_house_course", 12),
            ("SHL_open_conclave", "SHL_commit_city_course", 46 - 15 / 9),
            ("SHL_nur_directorate", "SHL_commit_state_course", 51 - 20 / 9),
        ):
            with self.subTest(focus=focus):
                self.setUp()
                self.m.focuses.add(focus)
                self.m.run("SHL_update_tensions")
                self.m.run(effect)
                self.m.run("SHL_update_tensions")
                self.assertAlmostEqual(self.country()["SHL_house_pressure"], expected)

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

    def test_platforms_can_win_the_ballot_without_a_finished_tenth_furnace(self):
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
                self.m.run("SHL_open_ballot")
                elapsed = 0
                engineer_finish = 0
                route = ("SHL_law_of_continuous_fire", "SHL_census_of_nine", *extra,
                         "SHL_conclave_rules", first,
                         "SHL_common_industrial_account", "SHL_engineer_society", second,
                         "SHL_right_to_land", "SHL_common_fund", "SHL_workers_charter")
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
                        self.assertEqual(elapsed, 63 + 28 * len(extra))
                    elif identifier == "SHL_engineer_society":
                        self.m.run("SHL_begin_engineers")
                        engineer_finish = elapsed + int(scalar(decision_definition("SHL_project_engineers"), "days_remove"))
                    elif identifier == "SHL_workers_charter":
                        if extra:
                            self.m.run("SHL_recognise_quarter_registers")
                        self.m.execute(block(reward, "hidden_effect"), "SHL")
                self.assertEqual(elapsed, days - 49)
                mission = decision_definition("SHL_conclave_ballot")
                self.assertLess(elapsed, int(scalar(mission, "days_mission_timeout")) + 7)
                self.assertEqual(self.country()["SHL_project_stage"], 1)
                self.assertFalse(self.m.matches(block(focus_definition(ratify), "available"), "SHL"))
                if first == "SHL_new_house":
                    seat_houses(self.m, 80)
                    self.m.run("SHL_refresh_furnaces")
                self.m.execute(block(mission, "timeout_effect"), "SHL")
                self.assertIn(ratify, self.m.focuses)
                settled = dict(self.country())
                self.m.run("SHL_count_ballot")
                self.assertEqual(dict(self.country()), settled)




class AutomaticFurnaceForecastTests(unittest.TestCase):
    def setUp(self):
        FurnaceAccountingTests.setUp(self)
        self.m = self.machine
        self.c = self.m.variables["SHL"]
        for state in range(287, 296):
            self.m.variables[str(state)].update({"SHL_furnace_running": int(state == 287), "SHL_furnace_stock": 0})
        self.c.update({"ADISCORD_economy_treasury": 44.99, "SHL_regular_supply": 1, "SHL_selected_furnace": 1})
        self.m.run("SHL_refresh_furnaces")
        self.m.run("SHL_schedule_cycle")
        self.m.effects.update(shared_definitions("common/scripted_effects/ADISCORD_economy_effects.txt",
                                                 ("ADISCORD_economy_update_gui",)))
        # Loan and emission widgets have independent quotes and do not participate in furnace accounting.
        self.m.effects["ADISCORD_economy_calculate_repayment_quote"] = []
        self.m.effects["ADISCORD_economy_calculate_emission_quote"] = []
        path = ROOT / "common/on_actions/03_ADISCORD_SHL_on_actions.txt"
        hooks = block(parse_clausewitz(path.read_text(encoding="utf-8")), "on_actions")
        self.daily = block(block(hooks, "on_daily_SHL"), "effect")
        self.assertTrue(self.daily)

    def assert_idle_day(self):
        from unittest.mock import patch

        dirty = self.c["SHL_gui_dirty"]
        with patch.object(self.m, "run", wraps=self.m.run) as run:
            self.m.execute(self.daily, "SHL")
        self.assertEqual(self.c["SHL_gui_dirty"], dirty)
        self.assertNotIn("SHL_refresh_delivery_forecast", [call.args[0] for call in run.call_args_list])

    def test_economy_notification_updates_the_open_card_at_the_exact_price(self):
        for balance, packets, cost, net in ((45, 1, 45, 15), (44.99, 0, 0, 0)):
            with self.subTest(balance=balance):
                self.c["ADISCORD_economy_treasury"] = balance
                dirty = self.c["SHL_gui_dirty"]
                self.m.run("ADISCORD_economy_update_gui")
                self.assertGreater(self.c["SHL_gui_dirty"], dirty)
                self.assertEqual((self.c["SHL_preview_autobuy_packets"], self.c["SHL_preview_autobuy_cost"],
                                  self.c["SHL_preview_cycle_net"]), (packets, cost, net))
                self.assertEqual(self.c["SHL_selected_furnace"], 1)
                self.assertEqual(self.m.variables["287"]["SHL_furnace_stock"], 0)
                self.assertEqual(self.c["ADISCORD_economy_treasury"], balance)
                self.assertEqual(self.c.get("ADISCORD_economy_current_month_action_costs", 0), 0)
                self.assert_idle_day()

    def test_cash_notifications_during_settlement_leave_the_completed_forecast_on_screen(self):
        dirty = self.c["SHL_gui_dirty"]
        self.m.flags["SHL"].remove("SHL_cycle_pending")
        self.c["ADISCORD_economy_treasury"] = 45
        self.m.run("ADISCORD_economy_update_gui")
        self.assertEqual((self.c["SHL_gui_dirty"], self.c["SHL_preview_cycle_net"]), (dirty, 0))
        self.m.run("SHL_schedule_cycle")
        self.m.execute(self.daily, "SHL")
        self.assertEqual(self.c["SHL_preview_cycle_net"], 15)

    def test_paying_engineers_updates_the_estimate_before_time_advances(self):
        cash = "ADISCORD_economy_treasury"
        self.c[cash] = 100
        self.m.focuses.add("SHL_engineer_society")
        self.m.execute(self.daily, "SHL")
        self.assertEqual(self.c["SHL_preview_autobuy_packets"], 1)
        dirty = self.c["SHL_gui_dirty"]
        decision = decision_definition("SHL_project_engineers")
        self.m.execute(block(decision, "complete_effect"), "SHL")
        self.assertEqual((self.c[cash], self.c["SHL_project_deposit"]), (0, 100))
        self.assertEqual((self.c["SHL_preview_autobuy_packets"], self.c["SHL_preview_autobuy_cost"],
                          self.c["SHL_preview_cycle_net"]), (0, 0, 0))
        self.assertEqual(self.c["SHL_gui_dirty"], dirty + 1)
        self.m.execute(self.daily, "SHL")
        self.assertEqual(self.c["SHL_gui_dirty"], dirty + 1)

    def test_daily_detects_an_equal_total_transfer_and_preserves_the_selected_card(self):
        self.m.variables["287"]["SHL_furnace_stock"] = 1
        self.m.variables["288"].update({"SHL_furnace_running": 1, "SHL_furnace_recipient": 1})
        self.c.update({"SHL_regular_supply": 0, "SHL_selected_furnace": 2})
        self.m.run("SHL_refresh_furnaces")
        self.assertEqual(self.c["SHL_preview_cycle_net"], 60)
        self.m.variables["287"]["SHL_furnace_stock"] = 0
        self.m.variables["288"]["SHL_furnace_stock"] = 1
        self.m.execute(self.daily, "SHL")
        self.assertEqual((self.c["SHL_preview_cycle_net"], self.c["SHL_preview_rifles"]), (0, 2700))
        self.assertEqual((self.c["SHL_stock_1"], self.c["SHL_stock_2"]), (0, 1))
        self.assertEqual((self.c["SHL_selected_furnace"], self.c["SHL_selected_stock"]), (2, 1))
        self.assertEqual(self.m.equipment["SHL", "infantry_equipment"], 0)
        self.assert_idle_day()

    def test_daily_observes_the_tenth_store_and_the_undistributed_reserve(self):
        self.c.update({"SHL_project_stage": 4, "SHL_tenth_running": 1, "SHL_tenth_stock": 0, "SHL_selected_furnace": 10})
        self.m.run("SHL_refresh_furnaces")
        dirty = self.c["SHL_gui_dirty"]
        self.c["SHL_reserve_stock"] = 2
        self.m.execute(self.daily, "SHL")
        self.assertGreater(self.c["SHL_gui_dirty"], dirty)
        self.assertEqual((self.c["SHL_preview_cycle_net"], self.c["SHL_selected_stock"]), (0, 0))
        self.c["SHL_tenth_stock"] = 1
        self.m.execute(self.daily, "SHL")
        self.assertEqual((self.c["SHL_preview_cycle_net"], self.c["SHL_selected_stock"]), (60, 1))
        self.assertEqual((self.c["SHL_selected_furnace"], self.c["SHL_reserve_stock"]), (10, 2))
        self.assert_idle_day()

    def test_external_treasury_write_catches_up_for_an_initialized_player(self):
        dirty = self.c["SHL_gui_dirty"]
        self.c["ADISCORD_economy_treasury"] = 45
        self.m.ai = True
        self.m.execute(self.daily, "SHL")
        self.assertEqual(self.c["SHL_gui_dirty"], dirty)
        self.m.ai = False
        self.m.flags["SHL"].remove("SHL_furnaces_initialized")
        self.m.execute(self.daily, "SHL")
        self.assertEqual(self.c["SHL_gui_dirty"], dirty)
        self.m.flags["SHL"].add("SHL_furnaces_initialized")
        self.m.execute(self.daily, "SHL")
        self.assertEqual(self.c["SHL_preview_cycle_net"], 15)
        self.assertEqual(self.c["ADISCORD_economy_treasury"], 45)

    def test_daily_picks_up_a_buyers_payment_capacity_without_charging_it(self):
        for tag in ("VAL", "STP", "STS", "RUS"):
            self.m.countries[tag] = {"exists": True, "is_ai": True}
        self.m.flags["VAL"].add("SHL_metal_client")
        buyer = self.m.variables["VAL"]
        buyer.update({"SHL_metal_cycle_price": 20, "ADISCORD_economy_treasury": 19.99})
        self.c["SHL_metal_clients"] = 1
        self.m.run("SHL_refresh_furnaces")
        self.assertEqual(self.c["SHL_preview_cycle_net"], 0)
        for balance, receipt, from_budget in ((20, 20, True), (21, 20, True), (19.99, 0, False)):
            buyer["ADISCORD_economy_treasury"] = balance
            dirty = self.c["SHL_gui_dirty"]
            if from_budget:
                self.m.root_scope = "VAL"
                self.m.run("ADISCORD_economy_update_gui", scope="VAL")
                self.m.root_scope = "SHL"
            else:
                self.m.execute(self.daily, "SHL")
            self.assertEqual((self.c["SHL_preview_contract_income"], self.c["SHL_preview_cycle_net"]), (receipt, receipt))
            if balance == 21:
                self.assertEqual(self.c["SHL_gui_dirty"], dirty)
            self.assertEqual(buyer["ADISCORD_economy_treasury"], balance)
            self.assertEqual(self.c["ADISCORD_economy_treasury"], 44.99)
            self.assert_idle_day()


class FurnaceSupplyButtonTests(unittest.TestCase):
    def setUp(self):
        FurnaceAccountingTests.setUp(self)
        self.m = self.machine
        self.c = self.m.variables["SHL"]
        self.m.focuses.add("SHL_census_of_nine")
        self.m.run("SHL_schedule_cycle")
        self.c.update({"SHL_selected_furnace": 8, "SHL_project_stage": 4, "SHL_tenth_running": 1,
                       "SHL_tenth_stock": 0, "SHL_regular_supply": 1, "SHL_reserve_stock": 1,
                       "ADISCORD_economy_treasury": 45})
        for state in range(287, 296):
            self.m.variables[str(state)].update({"SHL_furnace_recipient": 1,
                                                "SHL_furnace_stock": int(state not in (287, 289, 294))})
        self.m.variables["288"]["SHL_furnace_wear"] = 80
        self.m.run("SHL_refresh_furnaces")
        source = ROOT / "common/scripted_guis/ADISCORD_SHL_scripted_gui.txt"
        panel = block(block(parse_clausewitz(source.read_text(encoding="utf-8")), "scripted_gui"), "ADISCORD_SHL_furnaces")
        self.buttons = block(panel, "effects")
        self.conditions = block(panel, "triggers")

    def enabled(self, name):
        predicate = block(self.conditions, name + "_click_enabled")
        self.assertTrue(predicate, name)
        return self.m.matches(predicate, "SHL")

    def click(self, name):
        effect = block(self.buttons, name + "_click")
        self.assertTrue(effect, name)
        self.m.execute(effect, "SHL")

    def prepare_bulk_orders(self, furnaces, reserve, cash, shift=0):
        self.m.focuses.add("SHL_law_of_continuous_fire")
        for number, state in enumerate(range(287, 296), 1):
            self.m.variables[str(state)].update({
                "SHL_furnace_running": int(number in furnaces),
                "SHL_furnace_wear": 20, "SHL_furnace_stock": 0, "SHL_furnace_recipient": 1,
            })
        self.c.update({
            "SHL_reserve_stock": reserve, "ADISCORD_economy_treasury": cash,
            "SHL_shift_policy": shift, "SHL_tenth_running": int(10 in furnaces),
            "SHL_tenth_stock": 0, "SHL_tenth_recipient": 1,
        })
        self.m.run("SHL_refresh_furnaces")

    def reserve_plan(self, prefix="SHL_bulk_reserve"):
        return {n: self.c[f"{prefix}_{n}"] for n in range(1, 11) if self.c.get(f"{prefix}_{n}")}

    def bulk_stocks(self):
        stocks = [self.m.variables[str(state)]["SHL_furnace_stock"] for state in range(287, 296)]
        return stocks + [self.c["SHL_tenth_stock"]]

    def toggle_priority(self, number):
        action = block(self.buttons, f"SHL_furnace_{number}_button_right_click")
        self.assertTrue(action, number)
        self.m.execute(action, "SHL")

    def test_master_sets_both_policies_from_each_start_and_only_projects_the_next_pour(self):
        master = "SHL_supply_master_button"
        self.c.update({"SHL_regular_supply": 0, "SHL_auto_reserve": 0})
        self.assertFalse(self.enabled(master))
        self.click(master)
        self.assertEqual((self.c["SHL_regular_supply"], self.c["SHL_auto_reserve"]), (0, 0))

        self.prepare_bulk_orders([1, 8, 10], reserve=2, cash=45)
        self.c.update({"SHL_reserve_floor": 1, "SHL_priority_10": 1})
        for regular, reserve in product((0, 1), repeat=2):
            with self.subTest(regular=regular, reserve=reserve):
                self.c.update({"SHL_regular_supply": regular, "SHL_auto_reserve": reserve})
                self.m.run("SHL_refresh_furnaces")
                dirty = self.c["SHL_gui_dirty"]
                self.assertTrue(self.enabled(master))
                self.click(master)
                expected = int((regular, reserve) != (1, 1))
                self.assertEqual((self.c.get("SHL_regular_supply", 0), self.c.get("SHL_auto_reserve", 0)),
                                 (expected, expected))
                self.assertGreater(self.c["SHL_gui_dirty"], dirty)
                self.assertEqual(self.c["SHL_preview_autobuy_packets"], expected)
                self.assertEqual(self.c["SHL_preview_autobuy_cost"], 45 * expected)
                self.assertEqual(self.reserve_plan("SHL_auto_reserve"), {10: 1} if expected else {})
                self.assertEqual(self.bulk_stocks(), [0] * 10)
                self.assertEqual((self.c["ADISCORD_economy_treasury"], self.c["SHL_reserve_stock"]), (45, 2))
                self.assertEqual((self.c["SHL_reserve_floor"], self.c["SHL_priority_10"],
                                  self.c["SHL_selected_furnace"]), (1, 1, 8))

    def test_settings_switches_visible_controls_with_no_forecast_or_supply_side_effects(self):
        layout = (ROOT / "interface/ADISCORD_SHL.gui").read_text(encoding="utf-8")
        windows = block(parse_clausewitz(layout), "guiTypes")
        panel = next(e.value for e in windows if scalar(e.value, "name").strip('"') == "ADISCORD_SHL_furnaces_window")
        widgets = {scalar(e.value, "name").strip('"') for e in panel
                   if isinstance(e.value, list) and scalar(e.value, "name")}
        shared = {"SHL_supply_master_button", "SHL_supply_settings_button", "SHL_survey_map",
                  "SHL_next_alert_button", *(f"SHL_furnace_{n}_button" for n in range(1, 10))}
        overview = {"SHL_panel_selection", "SHL_panel_stocks", "SHL_local_output", "SHL_send_reserve_button",
                    "SHL_recipient_export_button", "SHL_recipient_arsenal_button", "SHL_recipient_quarters_button",
                    "SHL_recipient_crest_button", "SHL_forecast_skips", "SHL_forecast_reserve"}
        settings = {"SHL_supply_toggle_button", "SHL_supply_packet_quote", "SHL_auto_reserve_button",
                    "SHL_raise_reserve_floor_button", "SHL_lower_reserve_floor_button",
                    "SHL_distribute_reserve_button", "SHL_next_unfunded_button", "SHL_ledger_line",
                    "SHL_convoy_ore_button", "SHL_convoy_masons_button", "SHL_convoy_sale_button"}
        self.assertLessEqual(shared | overview | settings, widgets)
        self.prepare_bulk_orders([1, 8, 10], reserve=2, cash=0)
        for expanded in (False, True, False):
            with self.subTest(expanded=expanded):
                self.assertEqual(bool(self.c.get("SHL_supply_settings_open")), expanded)
                shown = {n for n in widgets if self.m.matches(block(self.conditions, n + "_visible"), "SHL")}
                self.assertLessEqual(shared | (settings if expanded else overview), shown)
                self.assertFalse((overview if expanded else settings) & shown)
                before = deepcopy(self.m.variables)
                with patch.object(self.m, "run", wraps=self.m.run) as effects:
                    self.click("SHL_supply_settings_button")
                called = {call.args[0] for call in effects.call_args_list}
                self.assertFalse({"SHL_refresh_furnaces", "SHL_refresh_delivery_forecast",
                                  "SHL_project_furnace_deliveries"} & called)
                self.assertGreater(self.c["SHL_gui_dirty"], before["SHL"]["SHL_gui_dirty"])
                after = deepcopy(self.m.variables)
                for states in (before, after):
                    states["SHL"].pop("SHL_supply_settings_open", None)
                    states["SHL"].pop("SHL_gui_dirty", None)
                self.assertEqual(after, before)

    def test_settings_map_priority_stays_open_and_navigation_returns_to_the_selected_card(self):
        self.prepare_bulk_orders([1, 8, 10], reserve=1, cash=0)
        for number in (1, 8, 10):
            self.click("SHL_supply_settings_button")
            selected = self.c["SHL_selected_furnace"]
            self.toggle_priority(number)
            self.assertEqual(self.c["SHL_selected_furnace"], selected)
            self.assertEqual(self.c["SHL_supply_settings_open"], 1)
            self.click(f"SHL_furnace_{number}_button")
            self.assertEqual(self.c["SHL_selected_furnace"], number)
            self.assertFalse(self.c.get("SHL_supply_settings_open", 0))
        for button in ("SHL_next_alert_button", "SHL_next_unfunded_button"):
            self.click("SHL_supply_settings_button")
            previous = self.c["SHL_selected_furnace"]
            self.assertTrue(self.enabled(button))
            self.click(button)
            self.assertNotEqual(self.c["SHL_selected_furnace"], previous)
            self.assertFalse(self.c.get("SHL_supply_settings_open", 0))

    def test_missed_pours_follow_actual_shortages_with_and_without_paid_orders(self):
        self.prepare_bulk_orders([1, 3, 4, 8, 10], reserve=0, cash=0, shift=1)
        self.m.control["289"] = "NAM"
        self.m.variables["290"]["SHL_furnace_stock"] = 2
        self.c.update({"SHL_project_stage": 3, "SHL_regular_supply": 0})
        for regular in (0, 1):
            self.c["SHL_regular_supply"] = regular
            self.m.run("SHL_refresh_furnaces")
            self.assertEqual(self.c["SHL_preview_missed_pours"], 2)
            self.assertEqual(self.c["SHL_preview_unfunded_packets"], 4 * regular)
            self.assertEqual([n for n in range(1, 11) if self.c.get(f"SHL_delivery_block_{n}") == 3], [1, 8])
            produced = deepcopy(self.m)
            produced.run("SHL_produce_period")
            self.assertEqual([n for n, state in enumerate(range(287, 296), 1)
                              if produced.variables[str(state)].get("SHL_furnace_shortages")], [1, 8])
        self.c["ADISCORD_economy_treasury"] = 180
        self.m.run("SHL_refresh_furnaces")
        self.assertEqual(self.c["SHL_preview_missed_pours"], 0)

    def test_overview_lists_each_missed_pour_and_shows_only_committed_reserve_in_both_languages(self):
        self.prepare_bulk_orders(range(1, 11), reserve=2, cash=0)
        source = ROOT / "common/scripted_localisation/ADISCORD_SHL_scripted_loc.txt"
        selectors = {scalar(e.value, "name"): e.value for e in parse_clausewitz(source.read_text(encoding="utf-8"))}
        numerals = "I II III IV V VI VII VIII IX X".split()
        for lang in ("russian", "english"):
            path = ROOT / f"localisation/{lang}/ADISCORD_SHL_l_{lang}.yml"
            strings = dict(re.findall(r'^ (\w+):\d* "(.*)"$', path.read_text(encoding="utf-8-sig"), re.M))

            def render(key):
                def select(match):
                    options = selectors[match.group(1)]
                    first = next(e.value for e in options if e.key == "text" and
                                 self.m.matches(block(e.value, "trigger"), "SHL"))
                    return render(scalar(first, "localization_key").strip('"'))
                return re.sub(r"\[(SHLGet\w+)\]", select, strings[key])

            for regular, reserve in product((0, 1), repeat=2):
                with self.subTest(language=lang, regular=regular, reserve=reserve):
                    self.c.update({"SHL_regular_supply": regular, "SHL_auto_reserve": reserve,
                                   "ADISCORD_economy_treasury": 0})
                    self.m.run("SHL_refresh_furnaces")
                    missed = re.findall(r"\b[IVX]+\b", render("SHL_forecast_skips"))
                    committed = bool(regular and reserve)
                    self.assertEqual(missed, numerals[2:] if committed else numerals)
                    reported = render("SHL_forecast_reserve")
                    if committed:
                        self.assertIn("[?SHL_auto_reserve_total|0]", reported)
                        self.assertEqual(self.c["SHL_auto_reserve_total"], 2)
                    else:
                        self.assertIn("0 £SHL_packet_texticon", reported)
                    self.assertIn("[?SHL_preview_autobuy_cost|0] £ADISCORD_economy_treasury_texticon",
                                  render("SHL_forecast_cost"))
            self.c["ADISCORD_economy_treasury"] = 450
            self.m.run("SHL_refresh_furnaces")
            self.assertEqual(render("SHL_forecast_skips"), strings["SHL_forecast_skips_clear"])

    def test_each_map_marker_toggles_its_own_priority_without_moving_stocks_or_selection(self):
        self.prepare_bulk_orders(range(1, 11), reserve=2, cash=0)
        self.m.focuses.remove("SHL_law_of_continuous_fire")
        self.assertFalse(self.m.matches(block(self.conditions, "SHL_furnace_8_button_right_click_enabled"), "SHL"))
        self.toggle_priority(8)
        self.assertEqual(self.c.get("SHL_priority_8", 0), 0)
        self.m.focuses.add("SHL_law_of_continuous_fire")
        self.c["SHL_project_stage"] = 3
        self.assertFalse(self.m.matches(block(self.conditions, "SHL_furnace_10_button_right_click_enabled"), "SHL"))
        self.toggle_priority(10)
        self.assertEqual(self.c.get("SHL_priority_10", 0), 0)
        self.c["SHL_project_stage"] = 4
        self.m.run("SHL_disable_planned_supply")
        for number in range(1, 11):
            with self.subTest(number=number):
                visible = block(self.conditions, f"SHL_furnace_{number}_priority_visible")
                self.assertTrue(visible)
                self.assertTrue(self.m.matches(block(self.conditions, f"SHL_furnace_{number}_button_right_click_enabled"),
                                               "SHL"))
                self.toggle_priority(number)
                self.assertTrue(self.m.matches(visible, "SHL"))
                marked = [n for n in range(1, 11) if self.c.get(f"SHL_priority_{n}")]
                self.assertEqual(marked, [number])
                self.toggle_priority(number)
                self.assertFalse(self.m.matches(visible, "SHL"))
        self.assertEqual((self.c["SHL_reserve_stock"], self.c["ADISCORD_economy_treasury"]), (2, 0))
        self.assertEqual((self.c["SHL_selected_furnace"], self.bulk_stocks()), (8, [0] * 10))

    def test_priority_reassigns_only_automatic_packets_in_tie_order_and_preserves_the_floor(self):
        self.prepare_bulk_orders([1, 8, 10], reserve=2, cash=0)
        self.click("SHL_raise_reserve_floor_button")
        self.click("SHL_auto_reserve_button")
        expected_manual = {1: 1, 8: 1}
        for number, winner in ((10, 10), (8, 8), (8, 10), (10, 1), (10, 10)):
            self.toggle_priority(number)
            self.assertEqual(self.reserve_plan("SHL_auto_reserve"), {winner: 1})
            self.assertEqual(self.c["SHL_auto_reserve_total"], 1)
            self.assertEqual(self.reserve_plan(), expected_manual)
            self.assertEqual(self.c["SHL_preview_unfunded_packets"], 2)
        manual = deepcopy(self.m)
        manual.execute(block(self.buttons, "SHL_distribute_reserve_button_click"), "SHL")
        for state in ("287", "294"):
            self.assertEqual(manual.variables[state]["SHL_furnace_stock"], 1)
        self.assertEqual(manual.variables["SHL"]["SHL_tenth_stock"], 0)
        self.assertEqual(manual.variables["SHL"]["SHL_reserve_stock"], 0)
        self.m.run("SHL_produce_period")
        for state in ("287", "294"):
            self.assertEqual(self.m.variables[state]["SHL_furnace_shortages"], 1)
        self.assertEqual((self.c["SHL_tenth_shortages"], self.c["SHL_reserve_stock"]), (0, 1))
        self.assertEqual(self.c["SHL_priority_10"], 1)

    def test_cold_inaccessible_stocked_and_paid_markers_release_the_priority_to_an_unmarked_furnace(self):
        self.prepare_bulk_orders([1, 3, 4, 8, 10], reserve=1, cash=45)
        for number in (1, 2, 3, 8, 10):
            self.toggle_priority(number)
        self.m.control["289"] = "NAM"
        self.m.variables["294"]["SHL_furnace_stock"] = 1
        self.c["SHL_project_stage"] = 3
        self.m.run("SHL_refresh_furnaces")
        self.click("SHL_auto_reserve_button")
        self.assertEqual(self.reserve_plan("SHL_auto_reserve"), {4: 1})
        self.assertEqual(self.c["SHL_preview_autobuy_cost"], 45)
        self.m.run("SHL_produce_period")
        self.assertEqual((self.c["SHL_reserve_stock"], self.c["ADISCORD_economy_treasury"]), (0, 0))
        for state in ("287", "290"):
            self.assertEqual(self.m.variables[state]["SHL_furnace_shortages"], 0)
        self.assertEqual((self.m.variables["289"]["SHL_furnace_stock"], self.c["SHL_tenth_stock"]), (0, 0))

    def test_early_export_funds_a_marked_double_shift_and_lost_income_reassigns_at_the_pour(self):
        self.prepare_bulk_orders([1, 8, 10], reserve=2, cash=0, shift=1)
        self.m.variables["294"].update({"SHL_furnace_stock": 2, "SHL_furnace_recipient": 0})
        self.m.run("SHL_refresh_furnaces")
        self.click("SHL_auto_reserve_button")
        self.toggle_priority(10)
        self.assertEqual(self.reserve_plan("SHL_auto_reserve"), {1: 2})
        self.assertEqual((self.c["SHL_preview_autobuy_cost"], self.c["SHL_preview_unfunded_packets"]), (90, 0))
        self.m.variables["294"]["SHL_furnace_recipient"] = 1
        self.m.run("SHL_produce_period")
        self.assertEqual(self.c["SHL_reserve_stock"], 0)
        self.assertEqual(self.c.get("ADISCORD_economy_current_month_action_costs", 0), 0)
        self.assertEqual((self.m.variables["287"]["SHL_furnace_shortages"], self.c["SHL_tenth_shortages"]), (1, 0))

    def test_priority_does_not_advance_export_income_before_a_furnace_pours(self):
        self.prepare_bulk_orders([1, 10], reserve=1, cash=0)
        self.c["SHL_tenth_recipient"] = 0
        self.click("SHL_auto_reserve_button")
        self.toggle_priority(10)
        self.assertEqual(self.reserve_plan("SHL_auto_reserve"), {10: 1})
        self.assertEqual((self.c["SHL_preview_cycle_net"], self.c["SHL_preview_unfunded_packets"]), (60, 1))
        self.m.run("SHL_produce_period")
        self.assertEqual(self.m.variables["287"]["SHL_furnace_shortages"], 1)
        self.assertEqual((self.c["SHL_tenth_shortages"], self.c["ADISCORD_economy_treasury"]), (0, 60))

    def test_priority_double_shift_uses_one_surplus_packet_with_or_without_one_affordable_purchase(self):
        for cash, bought, end_stock in ((45, 1, 0), (0, 0, 1)):
            with self.subTest(cash=cash):
                self.setUp()
                self.prepare_bulk_orders([1, 10], reserve=2.75, cash=cash, shift=1)
                self.click("SHL_raise_reserve_floor_button")
                self.click("SHL_auto_reserve_button")
                self.toggle_priority(10)
                self.assertEqual(self.reserve_plan("SHL_auto_reserve"), {10: 1})
                self.assertEqual(self.c["SHL_preview_autobuy_packets"], bought)
                self.m.run("SHL_produce_period")
                self.assertEqual(self.c["SHL_reserve_stock"], 1.75)
                self.assertEqual(self.c.get("ADISCORD_economy_current_month_action_costs", 0), 45 * bought)
                self.assertEqual((self.c["SHL_tenth_stock"], self.c["SHL_tenth_shortages"]), (end_stock, 1 - bought))

    def test_priority_keeps_a_paid_order_when_a_nonpriority_partial_delivery_would_take_its_cash(self):
        self.prepare_bulk_orders([1, 10], reserve=1, cash=45, shift=1)
        self.c["SHL_tenth_stock"] = 1
        self.click("SHL_auto_reserve_button")
        self.toggle_priority(10)
        self.assertEqual(self.reserve_plan(), {1: 1})
        self.assertEqual(self.reserve_plan("SHL_auto_reserve"), {})
        self.assertEqual((self.c["SHL_preview_autobuy_cost"], self.c["SHL_preview_unfunded_packets"]), (45, 2))
        self.m.run("SHL_produce_period")
        self.assertEqual((self.m.variables["287"]["SHL_furnace_shortages"], self.c["SHL_tenth_shortages"]), (1, 0))
        self.assertEqual((self.c["SHL_reserve_stock"], self.c["ADISCORD_economy_treasury"]), (1, 0))

    def test_priority_keeps_its_packet_over_an_earlier_unfunded_exporter(self):
        self.prepare_bulk_orders([1, 10], reserve=1, cash=0)
        self.m.variables["287"]["SHL_furnace_recipient"] = 0
        self.click("SHL_auto_reserve_button")
        self.toggle_priority(10)
        self.assertEqual(self.reserve_plan(), {1: 1})
        self.assertEqual(self.reserve_plan("SHL_auto_reserve"), {10: 1})
        self.assertEqual((self.c["SHL_preview_cycle_net"], self.c["SHL_preview_unfunded_packets"]), (0, 1))
        self.m.run("SHL_produce_period")
        self.assertEqual((self.m.variables["287"]["SHL_furnace_shortages"], self.c["SHL_tenth_shortages"]), (1, 0))
        self.assertEqual((self.c["SHL_reserve_stock"], self.c["ADISCORD_economy_treasury"]), (0, 0))

    def test_reserve_tooltips_list_their_own_recipients_and_counts_in_both_languages(self):
        gui = parse_clausewitz((ROOT / "interface/ADISCORD_SHL.gui").read_text(encoding="utf-8"))
        panel = block(block(gui, "guiTypes"), "containerWindowType")
        tooltips = {scalar(row.value, "name").strip('"'): scalar(row.value, "pdx_tooltip").strip('"')
                    for row in panel if row.key == "buttonType"}
        source = ROOT / "common/scripted_localisation/ADISCORD_SHL_scripted_loc.txt"
        selectors = {scalar(entry.value, "name"): entry.value for entry in parse_clausewitz(source.read_text(encoding="utf-8"))}
        self.prepare_bulk_orders(range(1, 11), reserve=12, cash=0, shift=1)
        self.c.update({"SHL_tenth_stock": 1, "SHL_reserve_floor": 2, "SHL_auto_reserve": 1})
        for state in range(287, 296):
            self.m.variables[str(state)]["SHL_furnace_stock"] = int(state != 294)

        for lang in ("english", "russian"):
            source = ROOT / f"localisation/{lang}/ADISCORD_SHL_l_{lang}.yml"
            strings = dict(re.findall(r'^ (\w+):\d* "(.*)"$', source.read_text(encoding="utf-8-sig"), re.M))

            def expand(name):
                def resolve(match):
                    if match[1]:
                        return expand(match[1])
                    result = next(row for row in selectors[match[2]] if row.key == "text"
                                  and self.m.matches(block(row.value, "trigger"), "SHL"))
                    return expand(scalar(result.value, "localization_key").strip('"'))
                return re.sub(r"\$(\w+)\$|\[(SHLGet\w+)\]", resolve, strings[name])

            for reserve in (13, 12, 2):
                self.c["SHL_reserve_stock"] = reserve
                self.m.run("SHL_refresh_furnaces")
                manual = {n: 1 + int(n == 8) for n in range(1, 11)} if reserve >= 12 else {1: 1, 2: 1}
                automatic = {n: manual[n] for n in range(1, 10)} if reserve == 12 else {}
                if reserve == 13:
                    automatic = manual
                    for n in automatic:
                        map_tip = expand(tooltips[f"SHL_furnace_{n}_button"])
                        self.assertIn(f"[?SHL_auto_reserve_{n}|0]", map_tip, (lang, n))
                for n in range(1, 11):
                    visible = block(self.conditions, f"SHL_furnace_{n}_packets_visible")
                    self.assertTrue(visible)
                    self.assertEqual(self.m.matches(visible, "SHL"), n in automatic)
                for button, prefix, expected in (
                    ("SHL_distribute_reserve_button", "SHL_bulk_reserve", manual),
                    ("SHL_auto_reserve_button", "SHL_auto_reserve", automatic),
                ):
                    with self.subTest(language=lang, reserve=reserve, button=button):
                        self.assertEqual(self.reserve_plan(prefix), expected)
                        tooltip = re.sub(r"§.", "", expand(tooltips[button]))
                        lines = [" ".join(line.split()) for line in tooltip.split(r"\n")]
                        shown = []
                        for n in range(1, 11):
                            label = " ".join(strings[f"SHL_furnace_{n}_label"].split())
                            rows = [i for i, line in enumerate(lines) if label in line]
                            if n in expected:
                                self.assertEqual(len(rows), 1, label)
                                self.assertIn(f"[?{prefix}_{n}|0] £SHL_packet_texticon", lines[rows[0]])
                                shown.append(rows[0])
                            else:
                                self.assertEqual(rows, [], label)
                        self.assertEqual(shown, sorted(shown))

    def test_bulk_preview_matches_every_store_and_export_finances_the_next_order(self):
        self.prepare_bulk_orders([1, 2, 3, 8, 10], reserve=4.75, cash=0)
        self.m.variables["287"]["SHL_furnace_recipient"] = 0
        for _ in range(2):
            self.m.run("SHL_refresh_furnaces")
            self.assertEqual(self.reserve_plan(), {1: 1, 3: 1, 8: 1, 10: 1})
            self.assertEqual(self.c["SHL_bulk_reserve_total"], 4)
            self.assertEqual(self.c["SHL_preview_unfunded_packets"], 5)
            self.assertEqual(self.bulk_stocks(), [0] * 10)
            self.assertEqual(self.c["SHL_reserve_stock"], 4.75)

        button = "SHL_distribute_reserve_button"
        self.assertTrue(self.enabled(button))
        expected = self.reserve_plan()
        selection = self.c["SHL_selected_furnace"]
        self.click(button)
        self.assertEqual(self.bulk_stocks(), [expected.get(n, 0) for n in range(1, 11)])
        self.assertEqual((self.c["SHL_reserve_stock"], self.c["SHL_selected_furnace"]), (0.75, selection))
        self.assertEqual(self.reserve_plan(), {})
        self.assertFalse(self.enabled(button))
        self.click(button)
        cash = "ADISCORD_economy_treasury"
        costs = "ADISCORD_economy_current_month_action_costs"
        self.assertEqual((self.c[cash], self.c.get(costs, 0)), (0, 0))
        self.assertEqual((self.c["SHL_preview_autobuy_packets"], self.c["SHL_preview_unfunded_packets"]), (1, 0))
        self.m.run("SHL_produce_period")
        self.assertEqual((self.c[cash], self.c[costs]), (15, 45))

    def test_bulk_two_packet_order_uses_only_the_unaffordable_share(self):
        button = "SHL_distribute_reserve_button"
        for cash, reserve, purchased, unfunded in ((45, 2, 1, 0), (0, 1.75, 0, 1)):
            with self.subTest(cash=cash, reserve=reserve):
                self.prepare_bulk_orders([1], reserve=reserve, cash=cash, shift=1)
                self.assertEqual(self.c["SHL_preview_unfunded_packets"], 2)
                self.assertEqual(self.reserve_plan(), {1: 1})
                self.assertEqual(self.c["SHL_bulk_reserve_total"], 1)
                self.assertTrue(self.enabled(button))
                self.click(button)
                self.assertEqual(self.bulk_stocks(), [1] + [0] * 9)
                self.assertEqual((self.c["SHL_reserve_stock"], self.c["ADISCORD_economy_treasury"]), (reserve - 1, cash))
                self.assertEqual((self.c["SHL_preview_autobuy_packets"], self.c["SHL_preview_unfunded_packets"]),
                                 (purchased, unfunded))
                self.assertFalse(self.enabled(button))
                self.assertEqual(self.c["SHL_bulk_reserve_total"], 0)

    def test_bulk_click_rechecks_changed_treasury_reserve_stock_control_and_auto_supply(self):
        button = "SHL_distribute_reserve_button"
        scenarios = (
            ("treasury", {8: 1, 10: 1}), ("reserve", {1: 1}), ("no_whole_packet", {}),
            ("occupation", {1: 1}), ("store", {8: 1, 10: 1}), ("manual", {}),
        )
        for changed, distribution in scenarios:
            with self.subTest(changed=changed):
                self.setUp()
                self.prepare_bulk_orders([1, 8, 10], reserve=3, cash=0)
                self.assertEqual(self.reserve_plan(), {1: 1, 8: 1, 10: 1})
                self.assertTrue(self.enabled(button))
                if changed == "treasury":
                    self.c["ADISCORD_economy_treasury"] = 45
                elif changed == "reserve":
                    self.c["SHL_reserve_stock"] = 1.75
                elif changed == "no_whole_packet":
                    self.c["SHL_reserve_stock"] = 0.999
                elif changed == "occupation":
                    self.m.control["294"] = "NAM"
                elif changed == "store":
                    self.m.variables["287"]["SHL_furnace_stock"] = 1
                else:
                    self.c["SHL_regular_supply"] = 0
                before = self.bulk_stocks()
                reserve = self.c["SHL_reserve_stock"]
                cash = self.c["ADISCORD_economy_treasury"]
                self.click(button)
                self.assertEqual(self.bulk_stocks(), [stock + distribution.get(n, 0) for n, stock in enumerate(before, 1)])
                self.assertEqual(self.c["SHL_reserve_stock"], reserve - sum(distribution.values()))
                self.assertEqual(self.c["ADISCORD_economy_treasury"], cash)
                self.assertFalse(self.enabled(button))

    def test_auto_reserve_toggle_waits_for_auto_supply_and_a_whole_packet(self):
        toggle = "SHL_auto_reserve_button"
        self.assertFalse(self.enabled(toggle))
        self.click(toggle)
        self.assertEqual(self.c.get("SHL_auto_reserve", 0), 0)
        self.prepare_bulk_orders([1], reserve=0, cash=0)
        self.m.run("SHL_disable_planned_supply")
        self.assertTrue(self.enabled(toggle))
        self.click(toggle)
        self.assertEqual(self.c["SHL_auto_reserve"], 1)

        self.c["SHL_reserve_stock"] = 2
        self.m.run("SHL_produce_period")
        self.assertEqual(self.c["SHL_reserve_stock"], 2)
        self.assertEqual(self.m.variables["287"]["SHL_furnace_shortages"], 1)
        self.m.run("SHL_enable_planned_supply")
        self.assertEqual(self.reserve_plan("SHL_auto_reserve"), {1: 1})
        self.assertEqual(self.c["SHL_preview_unfunded_packets"], 0)
        self.assertEqual(self.bulk_stocks(), [0] * 10)
        self.click(toggle)
        self.assertEqual(self.c.get("SHL_auto_reserve", 0), 0)
        self.assertEqual(self.c["SHL_preview_unfunded_packets"], 1)
        self.m.run("SHL_produce_period")
        self.assertEqual(self.c["SHL_reserve_stock"], 2)

    def test_auto_reserve_forecast_matches_the_pour_and_never_precharges(self):
        toggle = "SHL_auto_reserve_button"
        for cash, reserve, planned, buys, unfunded, stored_at_viii in (
            (45, 4.75, {8: 1, 10: 2}, 1, 0, 0),
            (0, 1.75, {8: 1}, 0, 3, 1),
            (0, 0.999, {}, 0, 4, 0),
        ):
            with self.subTest(cash=cash, reserve=reserve):
                self.setUp()
                self.prepare_bulk_orders([8, 10], reserve=reserve, cash=cash, shift=1)
                self.click(toggle)
                for _ in range(2):
                    self.m.run("SHL_refresh_furnaces")
                    self.assertEqual(self.reserve_plan("SHL_auto_reserve"), planned)
                    self.assertEqual(self.c["SHL_auto_reserve_total"], sum(planned.values()))
                    self.assertEqual(self.c["SHL_preview_unfunded_packets"], unfunded)
                    self.assertEqual(self.c["SHL_preview_autobuy_packets"], buys)
                    self.assertEqual(self.c["SHL_preview_cycle_net"], -45 * buys)
                    self.assertEqual((self.c["SHL_reserve_stock"], self.c["ADISCORD_economy_treasury"]), (reserve, cash))
                    self.assertEqual(self.bulk_stocks(), [0] * 10)
                self.m.run("SHL_produce_period")
                self.assertAlmostEqual(self.c["SHL_reserve_stock"], reserve - sum(planned.values()))
                self.assertEqual(self.c["ADISCORD_economy_treasury"], cash - 45 * buys)
                self.assertEqual(self.c.get("ADISCORD_economy_current_month_action_costs", 0), 45 * buys)
                self.assertEqual(self.m.variables["294"]["SHL_furnace_stock"], stored_at_viii)
                self.assertEqual(self.c["SHL_tenth_stock"], 0)
                self.assertEqual(self.c["SHL_tenth_shortages"], int(unfunded > 0))

    def test_auto_reserve_uses_the_new_exchange_quote_before_x_pours(self):
        self.prepare_bulk_orders([1, 8, 10], reserve=1, cash=20)
        self.m.variables["287"].update({"SHL_furnace_stock": 1, "SHL_furnace_recipient": 0})
        self.c.update({"SHL_export_mode": 1, "SHL_exchange_price": 75})
        self.click("SHL_auto_reserve_button")
        self.assertEqual(self.reserve_plan("SHL_auto_reserve"), {})
        self.assertEqual(self.c["SHL_preview_autobuy_cost"], 90)
        self.assertEqual(self.c["SHL_reserve_stock"], 1)
        self.m.run("SHL_produce_period")
        self.assertEqual(self.c["SHL_exchange_price"], 45)
        self.assertEqual(self.c["SHL_reserve_stock"], 0)
        self.assertEqual(self.c["ADISCORD_economy_current_month_action_costs"], 45)
        self.assertEqual(self.c["ADISCORD_economy_treasury"], 20)
        self.assertEqual(self.m.variables["294"]["SHL_furnace_shortages"], 0)
        self.assertEqual(self.c["SHL_tenth_shortages"], 0)

    def test_auto_reserve_survives_cycles_and_honours_a_manual_transfer_before_the_pour(self):
        self.prepare_bulk_orders([8, 10], reserve=5, cash=0)
        self.click("SHL_auto_reserve_button")
        manual = "SHL_distribute_reserve_button"
        self.assertTrue(self.enabled(manual))
        self.click(manual)
        self.assertEqual((self.m.variables["294"]["SHL_furnace_stock"], self.c["SHL_tenth_stock"]), (1, 1))
        self.assertEqual(self.c["SHL_reserve_stock"], 3)
        self.assertEqual(self.reserve_plan(), {})
        for expected_cycle, remaining, due in ((1, 3, True), (1, 3, False), (2, 1, True)):
            if due:
                self.m.flag_days["SHL"]["SHL_cycle_pending"] = 28
            self.m.run("SHL_run_cycle")
            self.assertEqual(self.c["SHL_auto_reserve"], 1)
            self.assertEqual(self.c["SHL_cycle_number"], expected_cycle)
            self.assertEqual(self.c["SHL_reserve_stock"], remaining)
            self.assertEqual(self.m.variables["294"]["SHL_furnace_shortages"], 0)
            self.assertEqual(self.c["SHL_tenth_shortages"], 0)
            self.assertEqual(self.bulk_stocks(), [0] * 10)

    def test_floor_buttons_work_with_an_empty_warehouse_and_stop_at_zero(self):
        up = "SHL_raise_reserve_floor_button"
        down = "SHL_lower_reserve_floor_button"
        self.m.flags["SHL"].remove("SHL_furnaces_initialized")
        self.m.run("SHL_initialize_furnaces")
        self.assertEqual(self.c["SHL_reserve_floor"], 0)
        self.assertFalse(self.enabled(up))
        self.click(up)
        self.assertEqual(self.c["SHL_reserve_floor"], 0)
        self.prepare_bulk_orders([8], reserve=0, cash=0)
        for amount in range(1, 14):
            self.assertTrue(self.enabled(up))
            self.click(up)
            self.assertEqual(self.c["SHL_reserve_floor"], amount)
        for amount in reversed(range(13)):
            self.assertTrue(self.enabled(down))
            self.click(down)
            self.assertEqual(self.c["SHL_reserve_floor"], amount)
        self.assertFalse(self.enabled(down))
        self.click(down)
        self.assertEqual((self.c["SHL_reserve_floor"], self.c["SHL_reserve_stock"]), (0, 0))

    def test_floor_requotes_double_shift_purchases_and_shortages_immediately(self):
        for stock, auto, manual, bought, unfunded in (
            (2, {}, {8: 1, 10: 1}, 0, 4),
            (2.999, {}, {8: 1, 10: 1}, 0, 4),
            (3, {8: 1}, {8: 1, 10: 2}, 1, 2),
            (4.75, {8: 1, 10: 1}, {8: 1, 10: 2}, 1, 1),
        ):
            with self.subTest(stock=stock):
                self.setUp()
                self.prepare_bulk_orders([8, 10], reserve=stock, cash=45, shift=1)
                self.click("SHL_auto_reserve_button")
                self.click("SHL_raise_reserve_floor_button")
                self.click("SHL_raise_reserve_floor_button")
                self.assertEqual(self.reserve_plan("SHL_auto_reserve"), auto)
                self.assertEqual(self.reserve_plan(), manual)
                self.assertEqual(self.c["SHL_auto_reserve_total"], sum(auto.values()))
                self.assertEqual(self.c["SHL_bulk_reserve_total"], sum(manual.values()))
                self.assertEqual(self.c["SHL_preview_autobuy_packets"], bought)
                self.assertEqual(self.c["SHL_preview_unfunded_packets"], unfunded)
                self.assertEqual(self.c["SHL_preview_cycle_net"], -45 * bought)
                self.assertEqual((self.c["SHL_reserve_stock"], self.c["ADISCORD_economy_treasury"]), (stock, 45))
                self.m.run("SHL_produce_period")
                self.assertAlmostEqual(self.c["SHL_reserve_stock"], stock - sum(auto.values()))
                self.assertEqual(self.c["SHL_reserve_floor"], 2)
                self.assertEqual(self.c["ADISCORD_economy_treasury"], 45 - 45 * bought)
                self.assertEqual(self.m.variables["294"]["SHL_furnace_shortages"], int(not bought))
                self.assertEqual(self.c["SHL_tenth_shortages"], 1)
                self.assertEqual(self.c["SHL_tenth_stock"], auto.get(10, 0))

    def test_protected_packets_can_be_sent_by_both_manual_buttons(self):
        self.prepare_bulk_orders([8, 10], reserve=2, cash=0)
        self.click("SHL_raise_reserve_floor_button")
        self.assertEqual(self.reserve_plan("SHL_auto_reserve"), {8: 1})
        self.assertEqual(self.c["SHL_preview_unfunded_packets"], 2)
        self.click("SHL_raise_reserve_floor_button")
        self.click("SHL_auto_reserve_button")
        self.assertEqual(self.reserve_plan("SHL_auto_reserve"), {})
        self.assertEqual(self.reserve_plan(), {8: 1, 10: 1})
        self.assertTrue(self.enabled("SHL_send_reserve_button"))
        self.click("SHL_send_reserve_button")
        self.assertEqual(self.reserve_plan(), {10: 1})
        self.assertTrue(self.enabled("SHL_distribute_reserve_button"))
        self.click("SHL_distribute_reserve_button")
        self.assertEqual((self.m.variables["294"]["SHL_furnace_stock"], self.c["SHL_tenth_stock"]), (1, 1))
        self.assertEqual((self.c["SHL_reserve_floor"], self.c["SHL_reserve_stock"]), (2, 0))
        self.assertFalse(self.enabled("SHL_distribute_reserve_button"))
        self.m.run("SHL_produce_period")
        self.assertEqual((self.m.variables["294"]["SHL_furnace_shortages"], self.c["SHL_tenth_shortages"]), (0, 0))
        self.assertEqual(self.c["SHL_reserve_stock"], 0)

    def test_changing_the_floor_requotes_receipts_that_finance_later_furnaces(self):
        self.prepare_bulk_orders([1, 2], reserve=2, cash=0)
        self.m.variables["287"]["SHL_furnace_recipient"] = 0
        self.click("SHL_auto_reserve_button")
        self.click("SHL_raise_reserve_floor_button")
        self.click("SHL_raise_reserve_floor_button")
        self.assertEqual(self.reserve_plan(), {1: 1})
        self.assertEqual(self.reserve_plan("SHL_auto_reserve"), {})
        self.assertEqual((self.c["SHL_preview_cycle_net"], self.c["SHL_preview_unfunded_packets"]), (0, 2))
        self.click("SHL_lower_reserve_floor_button")
        self.assertEqual(self.reserve_plan("SHL_auto_reserve"), {1: 1})
        self.assertEqual(self.c["SHL_preview_autobuy_cost"], 45)
        self.assertEqual((self.c["SHL_preview_cycle_net"], self.c["SHL_preview_unfunded_packets"]), (15, 0))
        self.m.run("SHL_produce_period")
        self.assertEqual((self.c["SHL_reserve_stock"], self.c["ADISCORD_economy_treasury"]), (1, 15))
        self.assertEqual(self.m.variables["288"]["SHL_furnace_shortages"], 0)

    def test_refilling_between_cycles_automatically_supplies_only_the_new_surplus(self):
        self.prepare_bulk_orders([8, 10], reserve=3, cash=0)
        self.click("SHL_raise_reserve_floor_button")
        self.click("SHL_raise_reserve_floor_button")
        self.click("SHL_auto_reserve_button")
        self.assertEqual(self.reserve_plan("SHL_auto_reserve"), {8: 1})
        self.m.flag_days["SHL"]["SHL_cycle_pending"] = 28
        self.m.run("SHL_run_cycle")
        self.assertEqual((self.c["SHL_reserve_stock"], self.c["SHL_tenth_shortages"]), (2, 1))
        self.assertEqual(self.reserve_plan("SHL_auto_reserve"), {})
        self.m.run("SHL_refresh_reserve_price")
        self.c["ADISCORD_economy_treasury"] = self.c["SHL_reserve_price"]
        self.m.run("SHL_purchase_reserve")
        self.assertEqual((self.c["SHL_reserve_stock"], self.c["ADISCORD_economy_treasury"]), (4, 0))
        self.assertEqual(self.reserve_plan("SHL_auto_reserve"), {8: 1, 10: 1})
        self.m.flag_days["SHL"]["SHL_cycle_pending"] = 28
        self.m.run("SHL_run_cycle")
        self.assertEqual((self.c["SHL_reserve_floor"], self.c["SHL_reserve_stock"]), (2, 2))
        self.assertEqual((self.m.variables["294"]["SHL_furnace_shortages"], self.c["SHL_tenth_shortages"]), (0, 0))
        self.click("SHL_lower_reserve_floor_button")
        self.assertEqual(self.reserve_plan("SHL_auto_reserve"), {8: 1})
        self.assertEqual(self.c["SHL_reserve_stock"], 2)

    def test_navigation_wraps_only_unpaid_orders_and_skips_a_resupplied_furnace(self):
        cursor = "SHL_next_unfunded_button"
        cash = self.c["ADISCORD_economy_treasury"]
        stocks = [self.m.variables[str(state)]["SHL_furnace_stock"] for state in range(287, 296)]
        for number in (10, 3, 8, 10, 3):
            self.assertTrue(self.enabled(cursor))
            self.click(cursor)
            self.assertEqual(self.c["SHL_selected_furnace"], number)
        self.assertEqual(self.c["SHL_reserve_stock"], 1)
        self.assertEqual([self.m.variables[str(state)]["SHL_furnace_stock"] for state in range(287, 296)], stocks)
        self.assertEqual(self.c["SHL_tenth_stock"], 0)
        self.click("SHL_send_reserve_button")
        self.assertEqual(self.c["SHL_preview_unfunded_packets"], 2)
        for number in (8, 10, 8):
            self.click(cursor)
            self.assertEqual(self.c["SHL_selected_furnace"], number)
        self.assertEqual(self.c["ADISCORD_economy_treasury"], cash)
        self.click("SHL_furnace_1_button")
        self.click("SHL_next_alert_button")
        self.assertEqual(self.c["SHL_selected_furnace"], 2)

    def test_last_unpaid_site_and_already_funded_stale_click(self):
        cursor = "SHL_next_unfunded_button"
        self.m.variables["289"]["SHL_furnace_stock"] = 1
        self.m.variables["294"]["SHL_furnace_stock"] = 1
        self.m.run("SHL_refresh_furnaces")
        self.assertTrue(self.enabled(cursor))
        self.click(cursor)
        self.assertEqual(self.c["SHL_selected_furnace"], 10)
        self.assertFalse(self.enabled(cursor))
        self.click("SHL_furnace_1_button")
        self.assertTrue(self.enabled(cursor))
        self.c["ADISCORD_economy_treasury"] = 90
        self.click(cursor)
        self.assertEqual(self.c["SHL_selected_furnace"], 1)
        self.assertEqual(self.c["SHL_preview_unfunded_packets"], 0)
        self.assertFalse(self.enabled(cursor))
        self.assertEqual(self.c["ADISCORD_economy_treasury"], 90)

    def test_button_and_decisions_deliver_to_independent_viii_and_x_stores(self):
        for number, decision_id, target in ((8, "SHL_use_reserve", "294"), (10, "SHL_supply_tenth", None)):
            with self.subTest(furnace=number):
                if number == 10:
                    self.m.focuses.discard("SHL_census_of_nine")
                self.click(f"SHL_furnace_{number}_button")
                self.assertTrue(self.enabled("SHL_send_reserve_button"))
                decision = decision_definition(decision_id)
                self.assertTrue(self.m.matches(block(decision, "visible"), "SHL", target))
                self.assertTrue(self.m.matches(block(decision, "available"), "SHL", target))
                recipient = deepcopy(self.m)
                # The decision acts on its accepted target even if the player changes the selection.
                recipient.variables["SHL"]["SHL_selected_furnace"] = 1
                recipient.run("SHL_refresh_selected_furnace")
                recipient.execute(block(decision, "complete_effect"), "SHL", target)
                self.click("SHL_send_reserve_button")
                self.assertEqual(self.c["SHL_selected_furnace"], number)
                self.assertFalse(self.enabled("SHL_send_reserve_button"))
                self.click("SHL_send_reserve_button")
                for machine in (recipient, self.m):
                    country = machine.variables["SHL"]
                    self.assertEqual(machine.variables["294"]["SHL_furnace_stock"], int(number == 8))
                    self.assertEqual(country["SHL_tenth_stock"], int(number == 10))
                    self.assertEqual(country["SHL_reserve_stock"], 0)
                    self.assertEqual(country["SHL_preview_unfunded_packets"], 2)
                    self.assertEqual(country["ADISCORD_economy_treasury"], 45)
                # Both routes start with empty stores and a single national packet.
                self.m.variables["294"]["SHL_furnace_stock"] = 0
                self.c.update({"SHL_tenth_stock": 0, "SHL_reserve_stock": 1})
                self.m.run("SHL_refresh_furnaces")

    def test_reserve_dispatch_rechecks_live_capacity_control_and_focus(self):
        button = "SHL_send_reserve_button"
        for number in (8, 10):
            with self.subTest(furnace=number):
                self.click(f"SHL_furnace_{number}_button")
                store = self.c if number == 10 else self.m.variables["294"]
                key = "SHL_tenth_stock" if number == 10 else "SHL_furnace_stock"
                running = "SHL_tenth_running" if number == 10 else "SHL_furnace_running"
                store[running] = 0
                store[key] = 2
                self.c["SHL_reserve_stock"] = 2
                self.assertTrue(self.enabled(button))
                for failure in ("reserve", "capacity", "occupation", "unlock"):
                    store[key] = 2.001 if failure == "capacity" else 2
                    self.c["SHL_reserve_stock"] = 0.999 if failure == "reserve" else 2
                    self.m.control["294"] = "NAM" if failure == "occupation" else "SHL"
                    if failure == "unlock":
                        if number == 8:
                            self.m.focuses.discard("SHL_census_of_nine")
                        else:
                            self.c["SHL_project_stage"] = 3
                    with self.subTest(blocker=failure):
                        before = (store[key], self.c["SHL_reserve_stock"])
                        self.assertFalse(self.enabled(button))
                        self.click(button)
                        self.assertEqual((store[key], self.c["SHL_reserve_stock"]), before)
                self.m.focuses.add("SHL_census_of_nine")
                self.c["SHL_project_stage"] = 4
                self.assertTrue(self.enabled(button))
                self.click(button)
                self.assertEqual((store[key], self.c["SHL_reserve_stock"], store[running]), (3, 1, 0))
                self.assertFalse(self.enabled(button))
                self.click(button)
                self.assertEqual((store[key], self.c["SHL_reserve_stock"]), (3, 1))


class DeliveryAccountingTests(unittest.TestCase):
    def setUp(self):
        ObligationAccountingTests.setUp(self)
        self.c["SHL_unrest"] = 50
        seat_houses(self.m, 50)

    def assign(self, site, recipient):
        self.c.update({"SHL_selected_furnace": site, "SHL_assignment": recipient})
        self.m.run("SHL_assign_selected_delivery")

    def assert_cycle_cash(self, expected):
        cash = "ADISCORD_economy_treasury"
        before = self.c[cash]
        self.m.run("SHL_refresh_furnaces")
        self.assertEqual(self.c["SHL_preview_cycle_net"], expected)
        self.assertEqual(self.c[cash], before)
        self.m.run("SHL_produce_period")
        self.m.run("SHL_refresh_furnaces")
        self.assertEqual(self.c[cash] - before, expected)

    def test_cycle_net_applies_each_live_contract_credit_bond_and_tithe(self):
        cash = "ADISCORD_economy_treasury"
        for state in range(287, 296):
            self.m.variables[str(state)]["SHL_furnace_running"] = int(state <= 288)
        self.m.variables["287"]["SHL_furnace_wear"] = 95
        self.c.update({"SHL_project_stage": 4, "SHL_tenth_running": 1, "SHL_tenth_stock": 1,
                       "SHL_credit_cycles": 1, "SHL_seal_bond_cycles": 1, "SHL_cycle_bonus_income": -11,
                       "SHL_indemnity_due": 240, "SHL_indemnity_recipient": 1, "SHL_metal_clients": 3})
        self.m.flags["SHL"].add("SHL_seal_chapter_open")
        self.m.focuses.add("SHL_metal_brokers")
        self.m.countries["KYZ"] = {"exists": True, "is_subject": False}
        for tag in ("VAL", "STP", "STS", "RUS", "GLP", "NAM"):
            self.m.countries.setdefault(tag, {"exists": True})
        buyers = (("STP", 20, 20), ("RUS", 15, 15), ("VAL", 20, 19.99))
        for buyer, rate, balance in buyers:
            self.m.flags[buyer].add("SHL_metal_client")
            self.m.variables[buyer].update({"SHL_metal_cycle_price": rate, cash: balance})
        self.m.run("SHL_refresh_furnaces")
        self.assertEqual(self.c["SHL_preview_contract_income"], 65)
        self.assertEqual(self.c["SHL_preview_credit_net"], 0)
        self.assertEqual(self.c["SHL_preview_indemnity"], 8)
        for buyer, _, balance in buyers:
            self.assertEqual(self.m.variables[buyer][cash], balance)
        self.assert_cycle_cash(180 + 65 - 11 - 8)
        self.assertEqual((self.c["SHL_credit_cycles"], self.c["SHL_indemnity_due"]), (0, 232))
        self.assertNotIn("SHL_seal_bond_cycles", self.c)
        self.assertEqual(self.m.variables["VAL"]["SHL_metal_arrears"], 1)

    def test_cycle_net_indemnity_uses_lit_furnaces_even_when_they_earn_no_cash(self):
        for state in range(287, 296):
            self.m.variables[str(state)]["SHL_furnace_running"] = int(state == 287)
        self.m.variables["287"]["SHL_furnace_recipient"] = 1
        self.c.update({"ADISCORD_economy_treasury": 1, "SHL_indemnity_due": 6, "SHL_indemnity_recipient": 1})
        self.m.countries["KYZ"] = {"exists": True, "is_subject": False}
        self.assert_cycle_cash(-6)
        self.assertNotIn("SHL_indemnity_due", self.c)

    def test_cycle_net_export_closure_and_unfinished_order_lost_to_extinction(self):
        for progress, extended, expected in ((1, False, 120), (1, True, 90), (0, False, -90)):
            with self.subTest(progress=progress, extended=extended):
                self.setUp()
                ObligationAccountingTests.begin(self, 1)
                self.c["SHL_obligation_progress"] = progress
                if extended:
                    self.c["SHL_obligation_extended"] = 1
                self.m.variables["287"]["SHL_furnace_wear"] = 95
                self.assert_cycle_cash(480 + expected)
                self.assertNotIn("SHL_obligation_kind", self.c)

    def test_cycle_net_returns_civic_escrow_only_if_the_site_cannot_use_it(self):
        for full in (False, True):
            with self.subTest(full=full):
                self.setUp()
                ObligationAccountingTests.begin(self, 2)
                self.c["SHL_obligation_progress"] = 1
                refund = self.c["SHL_obligation_deposit"] if full else 0
                self.m.infrastructure = 5 if full else 2
                self.assert_cycle_cash(480 + refund)
                self.assertNotIn("SHL_obligation_kind", self.c)

    def test_second_missed_pour_returns_partial_civic_deposit_and_retires_tithe_site(self):
        ObligationAccountingTests.begin(self, 2)
        self.m.variables["287"].update({"SHL_furnace_shortages": 1, "SHL_furnace_stock": 0, "SHL_furnace_wear": 20})
        self.c.update({"SHL_indemnity_due": 240, "SHL_indemnity_recipient": 1})
        self.m.countries["KYZ"] = {"exists": True, "is_subject": False}
        self.assert_cycle_cash(480 + self.c["SHL_obligation_deposit"] - 8 * 8)
        self.assertEqual(self.m.variables["287"]["SHL_furnace_running"], 0)
        self.assertNotIn("SHL_obligation_kind", self.c)

    def test_extinguished_pledge_settles_only_the_remaining_liability(self):
        ObligationAccountingTests.begin(self, 4)
        self.m.variables["287"]["SHL_furnace_wear"] = 95
        remaining = self.c["SHL_obligation_liability"] - 60
        self.assert_cycle_cash(480 - remaining)
        self.assertNotIn("SHL_obligation_kind", self.c)

    def test_completed_relief_relights_the_recipient_before_collecting_tithe(self):
        ObligationAccountingTests.relief(self, stopped=True)
        self.c.update({"SHL_obligation_progress": 1, "SHL_indemnity_due": 240, "SHL_indemnity_recipient": 1})
        self.m.countries["KYZ"] = {"exists": True, "is_subject": False}
        self.assert_cycle_cash(420 - 9 * 8)
        self.assertEqual(self.m.variables["288"]["SHL_furnace_running"], 1)

    def test_lease_receipt_can_fund_the_overlords_metal_contract_that_cycle(self):
        cash = "ADISCORD_economy_treasury"
        self.m.countries["SHL"] = {"exists": True, "is_subject": True, "subject_of": "NAM"}
        for tag in ("VAL", "STP", "STS", "RUS", "GLP", "NAM"):
            self.m.countries.setdefault(tag, {"exists": True})
        for state in range(287, 296):
            self.m.variables[str(state)]["SHL_furnace_running"] = int(state == 287)
        self.m.variables["287"].update({"SHL_furnace_recipient": 4, "SHL_seal_service_cycles": 2})
        self.m.variables["NAM"].update({cash: 0, "SHL_metal_cycle_price": 20})
        self.m.flags["NAM"].add("SHL_metal_client")
        self.c["SHL_metal_clients"] = 1
        self.m.run("SHL_refresh_furnaces")
        self.assertEqual(self.c["SHL_preview_contract_income"], 20)
        self.assertEqual(self.m.variables["NAM"][cash], 0)
        self.assert_cycle_cash(20)
        self.assertEqual(self.m.variables["NAM"][cash], 40)

    def test_metal_mission_expiry_skips_only_a_future_payment(self):
        cash = "ADISCORD_economy_treasury"
        for mission, rate in (("SHL_metal_contract_year", 20), ("SHL_metal_contract_two_years", 15)):
            for days, final in ((27, True), (28, False)):
                with self.subTest(mission=mission, days=days):
                    self.setUp()
                    for tag in ("VAL", "STP", "STS", "RUS", "GLP", "NAM"):
                        self.m.countries.setdefault(tag, {"exists": True})
                    self.c["SHL_metal_clients"] = 1
                    self.m.focuses.add("SHL_metal_brokers")
                    self.m.flags["RUS"].add("SHL_metal_client")
                    self.m.missions.add(mission)
                    self.m.variables["RUS"].update({
                        cash: 100, "SHL_metal_cycle_price": rate, "days_mission_timeout@" + mission: days,
                    })
                    self.m.run("SHL_produce_period")
                    self.m.run("SHL_refresh_furnaces")
                    self.assertEqual(self.m.variables["RUS"][cash], 100 - rate)
                    self.assertEqual("SHL_metal_final_pour" in self.m.flags["RUS"], final)
                    self.assertEqual(self.c["SHL_preview_contract_income"], 0 if final else rate + 15)
                    self.m.run("SHL_metal_close_account", scope="RUS")
                    self.assertNotIn("SHL_metal_final_pour", self.m.flags["RUS"])
                    self.assertEqual(self.c["SHL_preview_contract_income"], 0)

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
                        # The site's house: three times the crest figure, export +1,
                        # arsenal -1, quarters -2, overtime -2, careful +1.
                        rate = (1, -1, -2, 3 * crests[shift])[effective] + (0, -2, 1)[shift]
                        self.assertEqual(self.m.variables["287"]["SHL_house_loyalty"], 50 + rate)
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
                    # A cold or lost furnace keeps its house; occupation costs 5, idleness 3.
                    self.assertEqual(self.m.variables["287"]["SHL_house_loyalty"],
                                     {"stopped": 50, "occupied": 45, "lost": 50, "stock": 47}[failure])
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

    def test_loyal_votes_follow_house_loyalty_and_cannot_restore_ownership(self):
        self.c["SHL_shift_policy"] = 1
        for site in range(1, 6):
            self.assign(site, 3)
        self.m.run("SHL_produce_period")
        self.m.run("SHL_refresh_furnaces")
        # 18 crest loyalty minus 2 for overtime lifts five houses to 66.
        self.assertEqual(self.m.variables["287"]["SHL_house_loyalty"], 66)
        self.assertEqual(self.c["SHL_crest_support"], 5)
        self.assertTrue(self.m.matches(self.m.triggers["SHL_has_delivery_majority"], "SHL"))
        self.m.variables["287"]["SHL_furnace_owner"] = 2
        self.m.run("SHL_refresh_furnaces")
        self.assertEqual(self.c["SHL_crest_support"], 4)
        self.assertEqual(self.c["SHL_house_votes"], 8)
        self.assertFalse(self.m.matches(self.m.triggers["SHL_has_delivery_majority"], "SHL"))
        # Loyalty outlasts the cycle; a house without its furnace gets no vote back.
        for site in range(2, 6):
            self.assign(site, 0)
        self.m.run("SHL_produce_period")
        self.m.run("SHL_refresh_furnaces")
        self.assertEqual(self.c["SHL_crest_support"], 4)
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

    def supply_order_rows(self):
        return [(self.c.get(f"SHL_forecast_order_packets_{number}", 0),
                 self.c.get(f"SHL_forecast_order_shortfall_{number}", 0)) for number in range(1, 11)]

    def test_supply_order_detail_uses_the_budget_at_each_furnace(self):
        cash = "ADISCORD_economy_treasury"
        for state in range(287, 296):
            self.m.variables[str(state)]["SHL_furnace_running"] = int(state <= 289)
        self.m.variables["287"]["SHL_furnace_stock"] = 0.5
        self.m.variables["288"]["SHL_furnace_stock"] = 1.25
        self.m.variables["289"].update({"SHL_furnace_stock": 0, "SHL_furnace_recipient": 1})
        self.c.update({cash: 45.501, "SHL_regular_supply": 1, "SHL_shift_policy": 1,
                       "SHL_project_stage": 4, "SHL_tenth_running": 1, "SHL_tenth_stock": 1})
        # I cannot buy two packets. II buys one and exports, financing III's
        # pair. III delivers to the arsenal, leaving 0.501 coins for X.
        expected = [(2, 44.499), (1, 0), (2, 0)] + [(0, 0)] * 6 + [(1, 44.499)]
        self.m.run("SHL_refresh_furnaces")
        for _ in range(2):
            self.m.run("SHL_refresh_delivery_forecast")
            for number, (actual, wanted) in enumerate(zip(self.supply_order_rows(), expected), start=1):
                with self.subTest(furnace=number):
                    self.assertEqual(actual[0], wanted[0])
                    self.assertAlmostEqual(actual[1], wanted[1])
            self.assertEqual((self.c["SHL_preview_autobuy_packets"], self.c["SHL_preview_autobuy_cost"],
                              self.c["SHL_preview_unfunded_packets"]), (3, 135, 3))
            self.assertEqual((self.c[cash], self.c.get("ADISCORD_economy_current_month_action_costs", 0)), (45.501, 0))
            self.assertEqual([self.m.variables[str(state)]["SHL_furnace_stock"] for state in range(287, 290)],
                             [0.5, 1.25, 0])
            self.assertEqual(self.c["SHL_tenth_stock"], 1)
            self.assertEqual(self.m.equipment["SHL", "infantry_equipment"], 0)

    def test_supply_order_detail_clears_old_rows_when_supply_or_a_store_changes(self):
        for state in range(287, 296):
            self.m.variables[str(state)]["SHL_furnace_stock"] = 0
        self.m.focuses.add("SHL_law_of_continuous_fire")
        self.c.update({"ADISCORD_economy_treasury": 44.25, "SHL_regular_supply": 1, "SHL_project_stage": 4,
                       "SHL_tenth_running": 1, "SHL_tenth_stock": 0})
        self.m.run("SHL_refresh_furnaces")
        self.assertEqual(self.supply_order_rows(), [(1, 0.75)] * 10)
        self.assertEqual(self.c["SHL_preview_unfunded_packets"], 10)
        self.m.run("SHL_disable_planned_supply")
        self.assertEqual(self.supply_order_rows(), [(0, 0)] * 10)
        self.assertEqual(self.c["SHL_preview_unfunded_packets"], 0)
        self.m.run("SHL_enable_planned_supply")
        self.assertEqual(self.supply_order_rows(), [(1, 0.75)] * 10)

        self.m.variables["287"]["SHL_furnace_stock"] = 1
        self.m.control["288"] = "NAM"
        self.m.variables["289"]["SHL_furnace_running"] = 0
        self.m.control["294"] = "NAM"
        self.m.run("SHL_refresh_furnaces")
        # District 294 controls both VIII and X. I exports from stock and the
        # remaining working sites can all pay for their packets.
        self.assertEqual(self.supply_order_rows(), [(0, 0)] * 3 + [(1, 0)] * 4 + [(0, 0), (1, 0), (0, 0)])
        self.assertEqual((self.c["SHL_preview_autobuy_packets"], self.c["SHL_preview_unfunded_packets"]), (5, 0))
        self.assertEqual(self.c["ADISCORD_economy_treasury"], 44.25)

    def test_next_pour_projects_only_affordable_packets_and_the_actual_net(self):
        cash = "ADISCORD_economy_treasury"
        costs = "ADISCORD_economy_current_month_action_costs"
        keys = ("SHL_preview_autobuy_packets", "SHL_preview_autobuy_cost", "SHL_preview_cycle_net")
        # In district order, the first furnace exports and the second serves the arsenal.
        # The tenth exports last. Earlier sales can finance its order.
        cases = (
            (False, 0, 150, (0, 0, 0), (0, 0, 0)),
            (True, 0, 0, (1, 1, 1), (0, 0, 120)),
            (True, 0, 44.75, (0, 0, 0), (0, 0, 0)),
            (True, 0, 45, (0, 0, 0), (2, 90, -30)),
            (True, 0, 90, (0, 0, 0), (3, 135, -15)),
            (True, 1, 89.75, (0.5, 1.5, 0), (1, 45, -45)),
            (True, 1, 90, (0.5, 1.5, 2), (3, 135, 45)),
        )
        for enabled, shift, opening, stocks, expected in cases:
            with self.subTest(enabled=enabled, shift=shift, opening=opening, stocks=stocks):
                self.setUp()
                for state in range(287, 296):
                    self.m.variables[str(state)]["SHL_furnace_running"] = int(state < 289)
                self.m.variables["287"]["SHL_furnace_stock"] = stocks[0]
                self.m.variables["288"].update({"SHL_furnace_stock": stocks[1], "SHL_furnace_recipient": 1})
                self.c.update({cash: opening, "SHL_regular_supply": int(enabled), "SHL_shift_policy": shift,
                               "SHL_project_stage": 4, "SHL_tenth_running": 1, "SHL_tenth_stock": stocks[2]})
                self.m.run("SHL_refresh_furnaces")
                for _ in range(2):
                    self.m.run("SHL_refresh_delivery_forecast")
                    self.assertEqual(tuple(self.c[key] for key in keys), expected)
                    self.assertEqual((self.c[cash], self.c.get(costs, 0)), (opening, 0))
                    self.assertEqual((self.m.variables["287"]["SHL_furnace_stock"],
                                      self.m.variables["288"]["SHL_furnace_stock"], self.c["SHL_tenth_stock"]), stocks)
                self.m.run("SHL_produce_period")
                self.assertEqual(self.c.get(costs, 0), expected[1])
                self.assertEqual(self.c[cash] - opening, expected[2])

    def test_lease_refund_funds_the_first_purchase_and_is_counted_only_once(self):
        cash = "ADISCORD_economy_treasury"
        for state in range(287, 296):
            self.m.variables[str(state)]["SHL_furnace_running"] = int(state == 287)
        self.m.variables["287"].update({"SHL_furnace_stock": 0, "SHL_furnace_recipient": 4})
        self.m.flags["SHL"].add("SHL_seal_chapter_open")
        self.c.update({cash: 0, "SHL_seal_petition_site": 287, "SHL_seal_petition_deposit": 60,
                       "SHL_regular_supply": 1})
        self.m.run("SHL_refresh_furnaces")
        self.assertEqual(self.c["SHL_preview_autobuy_cost"], 45)
        self.assertEqual(self.c["SHL_preview_income"], 15)
        self.assertEqual(self.c["SHL_preview_order_income"], 60)
        self.assert_cycle_cash(75)
        self.assertNotIn("SHL_seal_petition_deposit", self.c)

    def test_net_retains_fractional_lease_proceeds(self):
        cash = "ADISCORD_economy_treasury"
        for state in range(287, 296):
            self.m.variables[str(state)]["SHL_furnace_running"] = int(state == 287)
        self.m.variables["287"]["SHL_furnace_recipient"] = 4
        self.m.countries["SHL"] = {"exists": True, "is_subject": True, "subject_of": "NAM"}
        self.m.countries["NAM"] = {"exists": True}
        self.c.update({cash: 100, "SHL_seal_lease_share": 0.65, "SHL_shift_policy": 2})
        self.assert_cycle_cash(8.75)
        self.assertEqual(self.m.variables["NAM"][cash], 16.25)

    def test_exchange_switch_reprices_only_regular_exports_without_rolling_on_inspection(self):
        cash = "ADISCORD_economy_treasury"
        self.c.update({cash: 100, "SHL_project_stage": 4, "SHL_tenth_running": 1, "SHL_tenth_stock": 1})
        self.m.run("SHL_refresh_furnaces")
        self.m.run("SHL_commit_metal_exchange")
        # The test engine chooses the lowest quote, 45, at each actual draw.
        self.assertEqual(self.c["SHL_preview_cycle_net"], 9 * 45 + 60)
        self.c["SHL_exchange_price"] = 75
        self.m.run("SHL_refresh_selected_furnace")
        self.assertEqual((self.c["SHL_exchange_price"], self.c["SHL_preview_cycle_net"]), (75, 9 * 75 + 60))
        self.m.run("SHL_toggle_export_mode")
        self.assertEqual(self.c["SHL_preview_cycle_net"], 10 * 60)
        self.m.run("SHL_produce_period")
        self.assertEqual(self.c[cash] - 100, 10 * 60)

    def test_buying_reserve_updates_the_forecast_before_the_packets_are_distributed(self):
        cash = "ADISCORD_economy_treasury"
        for state in range(287, 296):
            self.m.variables[str(state)]["SHL_furnace_running"] = 0
        self.m.variables["287"].update({"SHL_furnace_running": 1, "SHL_furnace_stock": 0})
        self.c.update({cash: 90, "SHL_regular_supply": 1, "SHL_reserve_stock": 0,
                       "SHL_selected_furnace": 1, "SHL_project_stage": 4,
                       "SHL_tenth_running": 1, "SHL_tenth_stock": 0})
        self.m.run("SHL_refresh_furnaces")
        self.assertEqual(self.c["SHL_preview_income"], 30)
        self.m.execute(block(decision_definition("SHL_buy_reserve"), "complete_effect"), "SHL")
        self.assertEqual((self.c[cash], self.c["SHL_reserve_stock"]), (0, 2))
        self.assertEqual((self.c["SHL_delivery_block_1"], self.c["SHL_delivery_block_10"]), (3, 3))
        self.assertEqual(self.c["SHL_preview_income"], 0)
        self.m.execute(block(decision_definition("SHL_use_reserve"), "complete_effect"), "SHL", "287")
        # The first furnace can now pay for the tenth's automatic order.
        self.assertEqual(self.c["SHL_preview_income"], 75)
        self.m.execute(block(decision_definition("SHL_supply_tenth"), "complete_effect"), "SHL")
        self.assertEqual(self.c["SHL_preview_income"], 120)
        self.assertEqual((self.c[cash], self.c["SHL_reserve_stock"]), (0, 0))
        self.m.run("SHL_produce_period")
        self.assertEqual(self.c[cash], 120)

    def test_tenth_delivery_forecast_follows_the_last_service_pour_at_eight(self):
        cash = "ADISCORD_economy_treasury"
        for running, stock, budget, cold, recipient, redeems in (
            (1, 1, 0, False, 0, True),
            (1, 0, 100, False, 1, True),
            (1, 0, 1, False, 0, False),
            (0, 1, 0, False, 0, False),
            (1, 1, 0, True, 0, False),
        ):
            with self.subTest(running=running, stock=stock, budget=budget, cold=cold):
                self.setUp()
                self.m.countries["SHL"] = {"exists": True, "is_subject": True, "has_war": False, "subject_of": "NAM"}
                for state in range(287, 296):
                    self.m.variables[str(state)]["SHL_furnace_running"] = 0
                # Another lease keeps the autonomy settlement out of this delivery.
                self.m.variables["287"]["SHL_furnace_recipient"] = 4
                site = self.m.variables["294"]
                site.update({"SHL_furnace_running": running, "SHL_furnace_stock": stock,
                             "SHL_furnace_recipient": 4, "SHL_seal_service_cycles": 1})
                if cold:
                    self.m.flags["294"].add("SHL_seal_cold_shift")
                self.c.update({"SHL_project_stage": 4, "SHL_tenth_running": 1, "SHL_tenth_stock": 1,
                               "SHL_tenth_recipient": recipient, "SHL_regular_supply": 1, cash: budget})
                self.m.run("SHL_refresh_furnaces")
                self.m.run("SHL_refresh_delivery_forecast")
                forecast = self.c["SHL_preview_income"]
                expected_rifles = 2700 if redeems and recipient == 1 else 0
                self.assertEqual(self.c["SHL_delivery_cash_10"], 60 if redeems and recipient == 0 else 0)
                self.assertEqual(self.c["SHL_delivery_rifles_10"], expected_rifles)
                self.assertEqual(self.c["SHL_recipient_10"], 4)
                self.assertEqual(site["SHL_seal_service_cycles"], 1)
                self.assertEqual(self.c[cash], budget)
                landlord_cash = self.m.variables["NAM"].get(cash, 0)
                self.m.run("SHL_produce_period")
                self.assertEqual(self.c[cash] - budget, forecast)
                self.assertEqual(self.m.variables["NAM"][cash] - landlord_cash, 60)
                self.assertEqual(self.m.equipment["SHL", "infantry_equipment"], expected_rifles)
                self.assertEqual("SHL_seal_service_cycles" not in site, redeems)

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
                self.m.run("SHL_refresh_house_pressure")
                actual = (self.c["ADISCORD_economy_treasury"] - 75,
                          self.m.equipment[("SHL", "infantry_equipment")],
                          50 - self.c["SHL_unrest"], 50 - self.c["SHL_house_pressure"])
                self.assertEqual(actual[:3], forecast[:3])
                self.assertAlmostEqual(actual[3], forecast[3])
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
        self.c["ADISCORD_economy_treasury"] = 689.99
        self.m.run("SHL_ai_allocate_deliveries")
        self.assertTrue(all(self.m.variables[str(state)]["SHL_furnace_recipient"] == 0 for state in range(287, 296)))
        self.assertEqual(self.c["SHL_ai_delivery_reserve"], 10 * 45 + 240)
        self.c["ADISCORD_economy_treasury"] = 690
        self.m.run("SHL_ai_allocate_deliveries")
        self.assertEqual([self.m.variables[str(state)]["SHL_furnace_recipient"] for state in range(287, 291)], [2, 3, 1, 0])
        self.c["SHL_shift_policy"] = 1
        self.m.focuses.add("SHL_houses_railway")
        self.m.run("SHL_refresh_delivery_terms")
        self.m.run("SHL_ai_allocate_deliveries")
        self.assertEqual(self.c["SHL_ai_delivery_reserve"], 20 * 40 + 240)

    def test_economic_examples_include_real_supply_but_not_hypothetical_repairs(self):
        for arsenal, quarters, expected in ((0, 0, 135), (1, 1, 15), (2, 1, -45)):
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
        # The compensated house gains 12 and the eight export houses 1 each.
        self.assertEqual(self.m.variables["287"]["SHL_house_loyalty"], 62)
        self.assertAlmostEqual(self.c["SHL_house_pressure"], 50 - 20 / 9)
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
                        self.m.variables[str(286 + site)]["SHL_house_loyalty"] = 55.0
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
    MISSIONS = ("SHL_strike_mission", "SHL_conspiracy_mission", "SHL_keizan_deadline")

    def setUp(self):
        CrisisLayerTests.setUp(self)
        self.m.power_balance[BALANCE] = -0.20

    country = CrisisLayerTests.country
    event = ShahrabadCabinetTests.event

    def balance(self):
        return self.m.power_balance[BALANCE]

    def option(self, identifier, name):
        return next(e.value for e in self.event(identifier) if e.key == "option" and scalar(e.value, "name") == name)

    def test_native_balance_uses_distinct_shahrabad_emblems(self):
        from PIL import Image

        balance = block(parse_clausewitz(BOP_PATH.read_text(encoding="utf-8")), BALANCE)
        gfx = (ROOT / "interface/ADISCORD_bop.gfx").read_text(encoding="utf-8")
        sprites = {scalar(entry.value, "name").strip('"'): scalar(entry.value, "texturefile").strip('"')
                   for entry in block(parse_clausewitz(gfx), "spriteTypes") if entry.key == "spriteType"}
        seen = set()
        for name, path in sprites.items():
            if name.startswith("GFX_bop_") and not name.startswith("GFX_bop_SHL_"):
                with Image.open(ROOT / path) as image:
                    seen.add(image.convert("RGBA").tobytes())
        for side in (e.value for e in balance if e.key == "side"):
            side_id = scalar(side, "id")
            path = sprites[scalar(side, "icon")]
            self.assertEqual(path, f"gfx/interface/bop/{side_id}.png")
            with Image.open(ROOT / path) as image:
                self.assertEqual(image.size, (78, 88))
                self.assertEqual(image.mode, "RGBA")
                self.assertEqual(image.getchannel("A").getextrema(), (0, 255))
                pixels = image.tobytes()
            self.assertNotIn(pixels, seen, side_id)
            seen.add(pixels)

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

    def test_ballot_uses_the_current_electorate_and_platform_at_equilibrium(self):
        for balance, votes, support, platform, expected in (
            (-0.3, 5, 20, None, 1),
            (-0.3, 4, 40, "SHL_house_compromise", 3),
            (0.3, 5, 30, None, 2),
            (0.3, 5, 29, "SHL_city_charters", 3),
            (0, 5, 40, "SHL_house_compromise", 1),
            (0, 5, 30, "SHL_city_charters", 2),
            (0, 5, 40, None, 3),
        ):
            with self.subTest(balance=balance, votes=votes, support=support, platform=platform):
                self.setUp()
                self.m.power_balance[BALANCE] = balance
                self.country().update({
                    "SHL_house_votes": 9, "SHL_crest_support": votes,
                    "SHL_crest_support_twice": 2 * votes, "SHL_city_support": support,
                })
                if platform:
                    self.m.focuses.add(platform)
                self.m.run("SHL_open_ballot")
                mission = decision_definition("SHL_conclave_ballot")
                self.assertIn("SHL_conclave_ballot", self.m.missions)
                self.assertFalse(self.m.matches(block(mission, "available"), "SHL"))
                self.m.execute(block(mission, "timeout_effect"), "SHL")
                self.assertEqual(self.country()["SHL_political_course"], expected)
                self.assertNotIn("SHL_ballot_due", self.m.flags["SHL"])

    def test_a_due_ballot_waits_for_liberation_and_respects_a_crisis_result(self):
        mission = decision_definition("SHL_conclave_ballot")
        self.m.capitulated = True
        self.m.execute(block(mission, "timeout_effect"), "SHL")
        self.assertEqual(self.country().get("SHL_political_course", 0), 0)
        self.assertIn("SHL_ballot_due", self.m.flags["SHL"])
        self.m.capitulated = False
        self.m.run("SHL_open_ballot")
        self.assertGreater(self.country()["SHL_political_course"], 0)
        self.setUp()
        self.m.run("SHL_commit_commune_course")
        self.assertTrue(self.m.matches(block(mission, "cancel_trigger"), "SHL"))
        self.m.execute(block(mission, "timeout_effect"), "SHL")
        self.assertEqual(self.country()["SHL_political_course"], 5)
        self.assertNotIn("SHL_ballot_due", self.m.flags["SHL"])

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
                # One native tree: the commit completes the entry focus of a hidden
                # course so its section opens without a tree change.
                self.assertEqual(self.m.loaded_trees, [])
                if tree in ("regency", "commune"):
                    self.assertIn(COURSE_COMMIT_FOCUSES[tree], self.m.focuses)
                else:
                    self.assertEqual(self.m.focuses, set())
                self.assertEqual(self.m.cosmetic_tags, [tag])
                self.assertEqual(self.m.scheduled.count("ADISCORD_SHL.123"), 1)
                self.assertEqual(self.m.variables["SHL"]["SHL_political_course"], COURSE_TREES[tree])
                effect = self.m.effects[f"SHL_commit_{suffix}_course"]
                guard = [e for e in block(effect, "if") if e.key != "limit"]
                self.assertNotIn("load_focus_tree", [e.key for e in guard])
                if tree in ("regency", "commune"):
                    completion = [e for e in walk_entries(guard[-1].value) if e.key == "complete_national_focus"]
                    self.assertEqual([e.value for e in completion], [COURSE_COMMIT_FOCUSES[tree]])
                # The visible rename precedes the hidden tag write.
                hidden = [e for e in guard if e.key == "hidden_effect" and any(c.key == "set_cosmetic_tag" for c in e.value)]
                self.assertEqual(len(hidden), 1)
                self.assertEqual(guard[guard.index(hidden[0]) - 1].value, f"SHL_rename_{suffix}_tt")

    def test_entry_focus_reward_commits_without_completing_itself(self):
        # The focus is not completed inside its own reward; its marker keeps
        # the commit from completing it again.
        for entry, suffix in (("SHL_regency_of_crests", "regency"), ("SHL_commune_of_shift_councils", "commune")):
            with self.subTest(focus=entry):
                self.setUp()
                reward = block(focus_definition(entry), "completion_reward")
                branch = block(block(reward, "hidden_effect"), "if")
                body = [e for e in branch if e.key != "limit"]
                self.assertEqual([e.key for e in body], ["set_temp_variable", f"SHL_commit_{suffix}_course"])
                self.assertEqual(scalar(body[0].value, "var"), "SHL_commit_from_entry")
                self.m.execute(body, "SHL")
                self.assertEqual(self.m.variables["SHL"]["SHL_political_course"], COURSE_TREES[suffix])
                self.assertNotIn(entry, self.m.focuses)

    def test_course_leader_house_is_spared_even_below_the_penalty(self):
        for suffix, leader in (("city", "287"), ("state", "294")):
            with self.subTest(course=suffix):
                self.setUp()
                for state in range(287, 296):
                    self.m.variables[str(state)]["SHL_house_loyalty"] = 50.0
                self.m.variables[leader]["SHL_house_loyalty"] = 5.0
                self.m.run(f"SHL_commit_{suffix}_course")
                self.assertEqual(self.m.variables[leader]["SHL_house_loyalty"], 5.0)
                self.assertNotIn("SHL_loyalty_spared", self.m.flags[leader])
                penalty = 15 if suffix == "city" else 20
                others = {self.m.variables[str(s)]["SHL_house_loyalty"] for s in range(287, 296) if str(s) != leader}
                self.assertEqual(others, {50.0 - penalty})

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

    def test_route_portraits_follow_ratification_and_military_victory(self):
        victory = "ADISCORD_south_hegemon_SHL"
        safir = "SHL_Darius_Safir"
        characters = parse_clausewitz((ROOT / "common/characters/SHL.txt").read_text(encoding="utf-8"))
        definitions = block(characters, "characters")
        starting = {}
        arbin = "SHL_Mariam_Arbin"
        darzi = "SHL_Salima_Darzi"
        for character in ("SHL_Jalil_Nur", safir, arbin, darzi):
            portraits = block(block(definitions, character), "portraits")
            starting[character] = scalar(block(portraits, "civilian"), "large")
        for commit, leader, normal, won in [
            ("SHL_commit_house_course", "SHL_Jalil_Nur", "GFX_portrait_SHL_Jalil_Nur_tenth_house", "GFX_portrait_SHL_Jalil_Nur_victory"),
            ("SHL_commit_state_course", "SHL_Jalil_Nur", "GFX_portrait_SHL_Jalil_Nur_directorate", "GFX_portrait_SHL_Jalil_Nur_victory"),
            ("SHL_commit_regency_course", safir, "GFX_portrait_SHL_Darius_Safir_regent", "GFX_portrait_SHL_Darius_Safir"),
            ("SHL_commit_city_course", arbin, "GFX_portrait_SHL_Mariam_Arbin", "GFX_portrait_SHL_Mariam_Arbin_victory"),
            ("SHL_commit_commune_course", darzi, "GFX_portrait_SHL_Salima_Darzi", "GFX_portrait_SHL_Salima_Darzi_victory"),
        ]:
            with self.subTest(course=commit):
                self.setUp()
                self.m.portraits.update(starting)
                self.m.run(commit)
                self.assertEqual(self.m.portraits[leader], normal)
                self.m.global_flags.add(victory)
                self.m.run("SHL_update_ruler_portrait")
                self.assertEqual(self.m.portraits[leader], won)
                for other in starting.keys() - {leader}:
                    self.assertEqual(self.m.portraits[other], starting[other])
                self.setUp()
                self.m.portraits.update(starting)
                self.m.global_flags.add(victory)
                self.m.run(commit)
                self.assertEqual(self.m.portraits[leader], won)
                self.setUp()
                self.m.portraits.update(starting)
                self.m.global_flags.update((victory, "ADISCORD_south_unopposed"))
                self.m.run(commit)
                self.assertEqual(self.m.portraits[leader], normal)
        self.setUp()
        self.m.run("SHL_commit_commune_course")
        self.assertEqual(self.m.leader, "SHL_Salima_Darzi")
        self.m.global_flags.add(victory)
        self.m.run("SHL_update_ruler_portrait")
        self.assertNotIn("SHL_Jalil_Nur", self.m.portraits)
        self.assertNotIn(safir, self.m.portraits)

    def test_cosmetic_tags_exist_with_three_flag_sizes(self):
        cosmetic = {e.key: e.value for e in parse_clausewitz((ROOT / "common/countries/cosmetic.txt").read_text(encoding="utf-8-sig"))}
        for _, tag in COURSE_COMMITS.values():
            with self.subTest(tag=tag):
                self.assertIn(tag, cosmetic)
                self.assertEqual({e.key for e in cosmetic[tag]}, {"color", "color_ui"})
                for folder in ("", "medium/", "small/"):
                    self.assertTrue((ROOT / f"gfx/flags/{folder}{tag}.tga").is_file(), folder)

    def test_shared_layer_is_defined_once_and_referenced_by_the_main_tree(self):
        shared = shared_focuses()
        source = SHARED_FOCUS_SOURCE.read_text(encoding="utf-8")
        self.assertEqual(source.count("shared_focus = {"), len(shared))
        self.assertNotIn("\nfocus = {", source)
        for identifier in shared:
            self.assertEqual(sum(identifier in focuses for focuses in map(tree_focuses, FOCUS_TREE_SOURCES)), 0, identifier)
        graph = whole_tree_focuses()
        opening = "SHL_law_of_continuous_fire"
        self.assertEqual({name for name, focus in graph.items() if not prerequisite_blocks(focus)}, {opening})
        self.assertEqual(reachable_focuses(graph, set()), set(graph))
        self.assertEqual(reachable_focuses(graph, {opening}), set())
        crown = graph["SHL_south_crown_of_the_south"]
        self.assertEqual([(e.key, e.value) for e in block(crown, "allow_branch")],
                         [("has_global_flag", "ADISCORD_south_hegemon_SHL")])
        war = war_tree_focuses()
        self.assertTrue(set(SOUTHERN_WAR_FRONT) <= set(war))
        self.assertEqual({name for name, focus in war.items() if not prerequisite_blocks(focus)},
                         {"SHL_sw_war_conclave"})
        self.assertEqual(reachable_focuses(war, set()), set(war))
        self.assertFalse(set(war) & set(graph))

    def test_course_focuses_keep_operability_and_cancel_after_a_course_switch(self):
        main = tree_focuses("main")
        commits = set(COURSE_COMMIT_FOCUSES.values())
        for commit in commits:
            exclusive = {e.value for e in block(main[commit], "mutually_exclusive")}
            self.assertEqual(exclusive, commits - {commit}, commit)
        for name, course in COURSE_TREES.items():
            own_course = ("SHL_political_course", str(course), "equals")
            with self.subTest(tree=name):
                roots = []
                for identifier, focus in tree_focuses(name).items():
                    available = block(focus, "available")
                    self.assertIn(("SHL_country_operable", "yes"), [(e.key, e.value) for e in available], identifier)
                    # The only course check is hidden: with cancel_if_invalid it
                    # cancels a focus in progress when a crisis switches the course.
                    checks = [
                        (scalar(e.value, "var"), scalar(e.value, "value"), scalar(e.value, "compare"))
                        for e in walk_entries(available)
                        if e.key == "check_variable" and scalar(e.value, "var") == "SHL_political_course"
                    ]
                    self.assertEqual(checks, [own_course], identifier)
                    hidden = [
                        e.value for e in available
                        if e.key == "hidden_trigger" and [c.key for c in e.value] == ["check_variable"]
                        and scalar(block(e.value, "check_variable"), "var") == "SHL_political_course"
                    ]
                    self.assertEqual(len(hidden), 1, identifier)
                    self.assertEqual(scalar(focus, "cancel_if_invalid"), "yes", identifier)
                    self.assertNotIn("SHL_regency_path", repr(focus), identifier)
                    self.assertNotIn("SHL_commune_path", repr(focus), identifier)
                    parents = [
                        {e.value for e in b.value} for b in focus if b.key == "prerequisite"
                    ]
                    if parents == [{COURSE_COMMIT_FOCUSES[name]}]:
                        roots.append(identifier)
                    else:
                        self.assertTrue(parents, identifier)
                        self.assertNotIn(COURSE_COMMIT_FOCUSES[name], set().union(*parents), identifier)
                self.assertEqual(len(roots), 1, roots)
        native = (ROOT / "common/national_focus/ADISCORD_SHL_focus.txt").read_text(encoding="utf-8")
        # The war for the South swaps the tree, so the course tree keeps its
        # completions as shared focus history.
        self.assertIn("shared focus history", native)
        self.assertNotIn("load_focus_tree", EFFECT_PATH.read_text(encoding="utf-8"))
        for identifier in COURSE_COMMIT_FOCUSES.values():
            self.assertIn(identifier, main)
            reward = block(main[identifier], "completion_reward")
            if identifier in ("SHL_regency_of_crests", "SHL_commune_of_shift_councils"):
                self.assertTrue(any(e.key.startswith("SHL_commit_") for e in walk_entries(reward)), identifier)
            else:
                self.assertIn(identifier, [
                    e.value for e in walk_entries(self.m.effects["SHL_count_ballot"])
                    if e.key == "complete_national_focus"
                ])
            self.assertIn(f"\t\tid = {identifier}\n", native)
        for name in COURSE_TREES:
            for identifier in tree_focuses(name):
                self.assertIn(f"\t\tid = {identifier}\n", native)

    def test_course_sections_open_only_for_the_ratified_course(self):
        main = tree_focuses("main")
        for commit in COURSE_COMMIT_FOCUSES.values():
            self.assertEqual(prerequisite_blocks(main[commit]), [{"SHL_workers_charter"}], commit)
        for suffix in COURSE_COMMITS:
            guard = block(self.m.effects[f"SHL_commit_{suffix}_course"], "if")
            self.assertIn("mark_focus_tree_layout_dirty", [e.key for e in walk_entries(guard)], suffix)
        sections = {name: set(tree_focuses(name)) for name in COURSE_TREES}
        epilogues = {
            name: {
                identifier for identifier, focus in tree_focuses(name).items()
                if ("has_global_flag", HEGEMON_FLAG) in [(e.key, e.value) for e in block(focus, "allow_branch")]
            }
            for name in COURSE_TREES
        }
        platforms = {"SHL_new_house": 1, "SHL_open_conclave": 2, "SHL_nur_directorate": 3}
        for course, hegemon in COURSE_STATES:
            with self.subTest(course=course, hegemon=hegemon):
                drawn = set(visible_focuses(course, hegemon, completed=set()))
                shown = [name for name, focuses in sections.items() if focuses & drawn]
                expected = [name for name, value in COURSE_TREES.items() if value == course]
                self.assertEqual(shown, expected)
                for name in shown:
                    self.assertEqual(sections[name] - drawn, set() if hegemon else epilogues[name])
                self.assertEqual("SHL_south_crown_of_the_south" in drawn, hegemon)
                # A commit stays drawn while its course is current or still reachable.
                for tree, commit in COURSE_COMMIT_FOCUSES.items():
                    if tree == "regency":
                        reachable = course != 5
                    elif tree == "commune":
                        reachable = course != 4
                    else:
                        reachable = course == COURSE_TREES[tree]
                    self.assertEqual(commit in drawn, reachable, commit)
                # Unchosen platform chains hide after ratification; a taken one stays.
                for root, value in platforms.items():
                    self.assertEqual(root in drawn, course in (0, value), root)
                    self.assertIn(root, visible_focuses(course, hegemon, completed={root}))

    def test_main_trunk_branches_offer_exclusive_choices_that_rejoin(self):
        main = tree_focuses("main")
        for first, second in MAIN_PAIRS:
            with self.subTest(pair=first):
                self.assertEqual({e.value for e in block(main[first], "mutually_exclusive")}, {second})
                self.assertEqual({e.value for e in block(main[second], "mutually_exclusive")}, {first})
        for rejoin, options in MAIN_REJOINS.items():
            self.assertEqual(prerequisite_blocks(main[rejoin]), [options], rejoin)
        # The tenth-furnace trunk forms two diamonds instead of one straight line.
        self.assertEqual(prerequisite_blocks(main["SHL_right_to_land"]),
                         [{"SHL_common_industrial_account"}, {"SHL_engineer_society"}])
        self.assertEqual(prerequisite_blocks(main["SHL_tenth_voice"]),
                         [{"SHL_build_tenth_complex"}, {"SHL_first_pour_focus"}])
        self.assertEqual(prerequisite_blocks(main["SHL_cannon_foundries"]),
                         [{"SHL_furnace_arsenals"}, {"SHL_industrial_evacuation"}])

    def test_south_readiness_survives_every_main_choice(self):
        triggers = {e.key: e.value for e in parse_clausewitz(SOUTH_TRIGGER_PATH.read_text(encoding="utf-8"))}
        readiness = triggers["ADISCORD_south_shl_focus_ready"]
        self.assertEqual([e.key for e in readiness], ["has_completed_focus"] * 3)
        ready = {e.value for e in readiness}
        self.assertEqual(ready, {"SHL_conclave_rules", "SHL_metal_market", "SHL_conclave_army"})
        main = tree_focuses("main")
        for choice in product((0, 1), repeat=len(MAIN_PAIRS)):
            blocked = {pair[1 - side] for pair, side in zip(MAIN_PAIRS, choice)}
            with self.subTest(blocked=sorted(blocked)):
                self.assertEqual(ready - reachable_focuses(main, blocked), set())

    def test_main_section_has_no_straight_chains_longer_than_two(self):
        main = tree_focuses("main")
        children = defaultdict(list)
        single_parent = {}
        for identifier, focus in main.items():
            groups = prerequisite_blocks(focus)
            for group in groups:
                for parent in group:
                    children[parent].append(identifier)
            if len(groups) == 1 and len(groups[0]) == 1:
                single_parent[identifier] = next(iter(groups[0]))
        for identifier in main:
            chain = [identifier]
            while (
                chain[-1] in single_parent
                and single_parent[chain[-1]] in main
                and children[single_parent[chain[-1]]] == [chain[-1]]
            ):
                chain.append(single_parent[chain[-1]])
            with self.subTest(focus=identifier):
                self.assertLessEqual(len(chain), 2, " < ".join(chain))
        # Horizontal neighbours drawn together keep one free column in every course state.
        for course, hegemon in COURSE_STATES:
            assert_free_cells(self, visible_focuses(course, hegemon), (course, hegemon))

    def test_neighbour_questions_are_bypassed_once_settled(self):
        main = tree_focuses("main")
        disputes = (
            (("SHL_water_question", "SHL_qanat_guard"), "SHL_water_crisis", "SHL_kyz_brotherhood"),
            (("SHL_veyr_duties", "SHL_veyr_ultimatum"), "SHL_veyr_crisis", "SHL_veyr_partner"),
        )
        for index, (focuses, variable, flag) in enumerate(disputes):
            _, other_variable, other_flag = disputes[1 - index]
            for identifier in focuses:
                bypass = block(main[identifier], "bypass")
                self.assertTrue(bypass, identifier)
                for value in range(6):
                    with self.subTest(focus=identifier, value=value):
                        self.setUp()
                        self.m.variables["SHL"][variable] = value
                        self.assertEqual(self.m.matches(bypass, "SHL"), value >= 2)
                self.setUp()
                self.m.flags["SHL"].add(flag)
                self.assertTrue(self.m.matches(bypass, "SHL"), identifier)
                # Settling the other neighbour does not close this question.
                self.setUp()
                self.m.variables["SHL"][other_variable] = 5
                self.m.flags["SHL"].add(other_flag)
                self.assertFalse(self.m.matches(bypass, "SHL"), identifier)
        self.assertEqual(prerequisite_blocks(main["SHL_southern_horizon"]),
                         [{"SHL_peace_has_a_price"}, {"SHL_qanat_guard", "SHL_veyr_ultimatum"}])

    def test_border_war_focus_layout_and_previews(self):
        main = tree_focuses("main")
        for identifier, cell in BORDER_WAR_LAYOUT.items():
            focus = main[identifier]
            self.assertEqual((int(scalar(focus, "x")), int(scalar(focus, "y"))), cell, identifier)
            self.assertIn(("SHL_country_operable", "yes"), [(e.key, e.value) for e in block(focus, "available")], identifier)
        self.assertEqual(prerequisite_blocks(main["SHL_border_foundries"]),
                         [{"SHL_qanat_guard", "SHL_veyr_ultimatum", "SHL_no_more_rations"}])
        for first, second in (("SHL_siege_founders", "SHL_furnace_garrisons"), ("SHL_furnace_garrisons", "SHL_siege_founders")):
            self.assertEqual({e.value for e in block(main[first], "mutually_exclusive")}, {second})
            self.assertEqual(prerequisite_blocks(main[first]), [{"SHL_border_foundries"}])
        self.assertEqual(prerequisite_blocks(main["SHL_border_settlement_office"]),
                         [{"SHL_siege_founders", "SHL_furnace_garrisons"}])
        for identifier in ("SHL_border_foundries", "SHL_siege_founders", "SHL_furnace_garrisons"):
            self.assertEqual([(e.key, e.value) for e in block(main[identifier], "bypass")],
                             [("SHL_limited_disputes_over", "yes")], identifier)
        self.assertFalse(block(main["SHL_border_settlement_office"], "bypass"))
        reward = block(main["SHL_border_foundries"], "completion_reward")
        self.assertIn(("unlock_decision_tooltip", "SHL_front_battery"), [(e.key, e.value) for e in reward])
        self.assertEqual(scalar(block(decision_definition("SHL_front_battery"), "visible"), "has_completed_focus"),
                         "SHL_border_foundries")
        # Each dummy preview shows exactly the SHL_bw_* deltas its reward adds.
        ideas = {}
        source = (ROOT / "common/ideas/ADISCORD_southern_desert_ideas.txt").read_text(encoding="utf-8-sig")
        for category in block(parse_clausewitz(source), "ideas"):
            ideas.update({e.key: e.value for e in category.value if isinstance(e.value, list)})
        modifier_of = {
            "SHL_bw_army_attack": "army_attack_factor", "SHL_bw_breakthrough": "breakthrough_factor",
            "SHL_bw_army_defence": "army_defence_factor", "SHL_bw_max_dig_in": "max_dig_in",
        }
        for identifier, idea in (("SHL_siege_founders", "SHL_bw_siege_founders_idea"),
                                 ("SHL_furnace_garrisons", "SHL_bw_furnace_garrisons_idea")):
            with self.subTest(focus=identifier):
                reward = block(main[identifier], "completion_reward")
                swap = scalar(block(block(reward, "effect_tooltip"), "swap_ideas"), "add_idea")
                self.assertEqual(swap, idea)
                deltas = {
                    modifier_of[scalar(e.value, "var")]: float(scalar(e.value, "value"))
                    for e in walk_entries(reward) if e.key == "add_to_variable"
                }
                preview = {e.key: float(e.value) for e in block(ideas[idea], "modifier")}
                self.assertEqual(preview, deltas)
                self.assertIn(("SHL_refresh_border_war", "yes"), [(e.key, e.value) for e in walk_entries(reward)])

    def test_house_ledgers_is_a_census_leaf_that_opens_the_favours(self):
        focus = tree_focuses("main")["SHL_house_ledgers"]
        # Row 2 holds the heralds' table at x 9 and the reserve at x 13.
        self.assertEqual((int(scalar(focus, "x")), int(scalar(focus, "y"))), (11, 2))
        self.assertEqual(prerequisite_blocks(focus), [{"SHL_census_of_nine"}])
        self.assertFalse(block(focus, "mutually_exclusive"))
        reward = [(e.key, e.value) for e in walk_entries(block(focus, "completion_reward"))]
        self.assertIn(("custom_effect_tooltip", "SHL_house_ledgers_tt"), reward)
        self.assertIn(("SHL_change_all_loyalty", "yes"), reward)
        children = [name for name, other in whole_tree_focuses().items()
                    if any("SHL_house_ledgers" in group for group in prerequisite_blocks(other))]
        self.assertEqual(children, [])
        plans = {e.key: e.value for e in parse_clausewitz((ROOT / "common/ai_strategy_plans/ADISCORD_SHL_plans.txt").read_text(encoding="utf-8"))}
        self.assertIn("SHL_house_ledgers", [e.value for e in block(plans["SHL_furnaces_plan"], "ai_national_focuses")])

    def test_caravan_upgrades_are_attached_to_existing_diplomatic_and_district_focuses(self):
        focuses = whole_tree_focuses()
        upgrades = {
            "SHL_chancery_of_the_gate": ("stelander_fairs", "fairs"),
            "SHL_sand_patrols": ("relay_posts", "relays"),
            "SHL_desert_caravanserai": ("factor_houses", "factors"),
            "SHL_northern_road": ("svetlogorsk_charter", "charter"),
        }
        for name, (art, benefit) in upgrades.items():
            with self.subTest(focus=name):
                self.assertNotIn("SHL_road_" + art, focuses)
                self.assertEqual(scalar(focuses[name], "icon"), "GFX_focus_SHL_road_" + art)
                shown = {entry.value for entry in block(focuses[name], "completion_reward")
                         if entry.key == "custom_effect_tooltip"}
                self.assertIn("SHL_road_unlock_" + benefit + "_tt", shown)

        patrols, factors = "SHL_sand_patrols", "SHL_desert_caravanserai"
        for choice, alternative in ((patrols, factors), (factors, patrols)):
            self.assertEqual({e.value for e in block(focuses[choice], "mutually_exclusive")}, {alternative})
            accessible = reachable_focuses(focuses, {alternative})
            self.assertTrue({choice, "SHL_chancery_of_the_gate", "SHL_northern_road"} <= accessible)
        self.assertNotIn("SHL_northern_road", reachable_focuses(focuses, {"SHL_chancery_of_the_gate"}))

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
            "SHL_south_war_plan", "SHL_seal_lease_plan", "SHL_seal_cold_fire_plan",
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
            # The course section plus the second-row shared branches; the southern
            # front is queued whole.
            focuses = dict(tree_focuses(tree))
            focuses.update({
                identifier: focus for identifier, focus in shared_focuses().items()
                if identifier not in SOUTHERN_SHARED
            })
            # The queue may leave out the unchosen half of each exclusive pair
            # and every focus reachable only through an omitted one.
            omitted = {f"SHL_{tree}_prog_ending_a", f"SHL_{tree}_prog_ending_b"}
            omitted |= {name for name in focuses if exclusive.get(name, set()) & queue}
            omitted = omitted_closure(focuses, queue, omitted)
            self.assertEqual(set(focuses) - queue - omitted, set(), tree)
            self.assertTrue(set(SOUTHERN_SHARED) <= queue, tree)
            self.assertFalse(set(war_tree_focuses()) & queue, tree)
        # The industrial programme covers the main section except what the
        # preparation plans queue (preliminary courses and mandates),
        # the hidden course entries and the closure of the unchosen alternatives.
        main = tree_focuses("main")
        programme = {e.value for e in block(plans["SHL_furnaces_plan"], "ai_national_focuses")}
        preparation = set()
        for tree in ("houses", "cities", "directorate"):
            preparation |= {e.value for e in block(plans[f"SHL_prepare_{tree}_plan"], "ai_national_focuses")}
        self.assertFalse(programme & preparation)
        omitted = preparation | set(COURSE_COMMIT_FOCUSES.values())
        omitted |= {name for name in main if exclusive.get(name, set()) & programme}
        omitted = omitted_closure(main, programme, omitted)
        self.assertEqual(set(main) - programme - omitted, set())
        self.assertNotIn("SHL_metal_brokers", programme)
        war_queue = {e.value for e in block(plans["SHL_south_war_plan"], "ai_national_focuses")}
        self.assertTrue(set(SOUTHERN_WAR_FRONT) <= war_queue)
        self.assertEqual(war_queue - set(war_tree_focuses()), set())
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


# Defeat chapter "Under the namestnik's seal": cell and prerequisite blocks of
# each focus (blocks are ANDed, the alternatives inside a block are ORed).
DEFEAT_LAYOUT = {
    "SHL_seal_conclave": ((84, 1), [{"SHL_law_of_continuous_fire"}]),
    "SHL_seal_count_the_cold": ((82, 2), [{"SHL_seal_conclave"}]),
    "SHL_seal_houses_in_mourning": ((86, 2), [{"SHL_seal_conclave"}]),
    "SHL_redeem_furnaces_of_the_lease": ((79, 3), [{"SHL_seal_count_the_cold"}, {"SHL_seal_houses_in_mourning"}]),
    "SHL_cold_fire": ((89, 3), [{"SHL_seal_count_the_cold"}, {"SHL_seal_houses_in_mourning"}]),
    "SHL_redeem_lease_ledger": ((77, 4), [{"SHL_redeem_furnaces_of_the_lease"}]),
    "SHL_redeem_namestnik_audience": ((81, 4), [{"SHL_redeem_furnaces_of_the_lease"}]),
    "SHL_redeem_by_coin": ((75, 5), [{"SHL_redeem_lease_ledger"}]),
    "SHL_redeem_by_service": ((79, 5), [{"SHL_redeem_lease_ledger", "SHL_redeem_namestnik_audience"}]),
    "SHL_redeem_quiet_quarters": ((83, 5), [{"SHL_redeem_namestnik_audience"}]),
    "SHL_redeem_guarantor_houses": ((77, 6), [{"SHL_redeem_by_coin", "SHL_redeem_by_service"}]),
    "SHL_redeem_supervised_repairs": ((81, 6), [{"SHL_redeem_by_service", "SHL_redeem_quiet_quarters"}]),
    "SHL_redeem_charter": ((79, 7), [{"SHL_redeem_guarantor_houses"}, {"SHL_redeem_supervised_repairs"}]),
    "SHL_cold_ash_cells": ((87, 4), [{"SHL_cold_fire"}]),
    "SHL_cold_quarter_couriers": ((91, 4), [{"SHL_cold_fire"}]),
    "SHL_cold_hidden_armouries": ((85, 5), [{"SHL_cold_ash_cells"}]),
    "SHL_cold_letters_to_the_sands": ((89, 5), [{"SHL_cold_ash_cells", "SHL_cold_quarter_couriers"}]),
    "SHL_cold_shifts": ((93, 5), [{"SHL_cold_quarter_couriers"}]),
    "SHL_cold_desert_drill": ((87, 6), [{"SHL_cold_hidden_armouries", "SHL_cold_letters_to_the_sands"}]),
    "SHL_cold_raid_martyrs": ((91, 6), [{"SHL_cold_letters_to_the_sands", "SHL_cold_shifts"}]),
    "SHL_cold_night_of_fire": ((89, 7), [{"SHL_cold_desert_drill"}, {"SHL_cold_raid_martyrs"}]),
    "SHL_cold_fire_without_masters": ((87, 8), [{"SHL_cold_night_of_fire"}]),
    "SHL_cold_embers_under_seal": ((91, 8), [{"SHL_cold_night_of_fire"}]),
}
DEFEAT_PAIRS = (
    ("SHL_redeem_furnaces_of_the_lease", "SHL_cold_fire"),
    ("SHL_redeem_by_coin", "SHL_redeem_by_service"),
    ("SHL_cold_hidden_armouries", "SHL_cold_letters_to_the_sands"),
    ("SHL_cold_fire_without_masters", "SHL_cold_embers_under_seal"),
)
DEFEAT_ENDINGS = {"SHL_redeem_charter", "SHL_cold_fire_without_masters", "SHL_cold_embers_under_seal"}
# Effects, unlocks and tooltips each reward must carry; the scripts behind
# the SHL_seal_*/SHL_cold_* names belong to the defeat-chapter effects.
DEFEAT_REWARDS = {
    "SHL_seal_conclave": {"add_political_power", "add_stability", "SHL_repair_worst_site"},
    "SHL_seal_count_the_cold": {"add_political_power", "SHL_seal_stock_free_sites", "SHL_unrest"},
    "SHL_seal_houses_in_mourning": {"add_manpower", "army_experience", "ADISCORD_SHL.201"},
    "SHL_redeem_furnaces_of_the_lease": {"add_political_power", "SHL_receive_250"},
    "SHL_cold_fire": {"add_command_power", "army_experience", "SHL_underground_heat", "SHL_cold_heat_opened_tt"},
    "SHL_redeem_lease_ledger": {"SHL_seal_buy_back_furnace", "add_political_power"},
    "SHL_redeem_namestnik_audience": {"add_political_power", "SHL_ensure_levy_template", "SHL_create_levy"},
    "SHL_redeem_by_coin": {"SHL_receive_250", "SHL_seal_coin_discount_now", "SHL_seal_refresh_terms", "SHL_seal_coin_price_tt"},
    "SHL_redeem_by_service": {"SHL_seal_redeem_by_service", "SHL_repair_worst_site"},
    "SHL_redeem_quiet_quarters": {"add_building_construction", "SHL_unrest"},
    "SHL_redeem_guarantor_houses": {"SHL_seal_house_bond", "SHL_change_all_loyalty"},
    "SHL_redeem_supervised_repairs": {"add_building_construction", "SHL_seal_maintain_leased_sites"},
    "SHL_redeem_charter": {"SHL_redeemed_conclave", "add_political_power", "add_building_construction", "ADISCORD_SHL_news.11"},
    "SHL_cold_ash_cells": {"SHL_cold_forge", "SHL_cold_add_heat"},
    "SHL_cold_quarter_couriers": {"add_political_power", "SHL_cold_add_heat", "SHL_unrest"},
    "SHL_cold_hidden_armouries": {"SHL_cold_hidden_cache", "SHL_cold_cache_cells", "SHL_cold_cache_rifles"},
    "SHL_cold_letters_to_the_sands": {"SHL_cold_send_pledges", "SHL_cold_courier_to_sands", "add_political_power"},
    "SHL_cold_shifts": {"SHL_cold_mark_shifts", "SHL_cold_add_heat"},
    "SHL_cold_desert_drill": {"army_experience", "SHL_cold_cache_cells"},
    "SHL_cold_raid_martyrs": {"add_political_power", "SHL_cold_add_heat", "SHL_cold_raid_guard_tt"},
    "SHL_cold_night_of_fire": {"SHL_cold_raise_rising", "SHL_cold_rising_tt"},
    "SHL_cold_fire_without_masters": {"SHL_cold_fire_without_masters_idea", "add_political_power", "add_building_construction"},
    "SHL_cold_embers_under_seal": {"SHL_seal_buy_back_furnace", "add_political_power", "add_manpower"},
}
# Aggregate variable -> modifier of the two route spirits.
DEFEAT_MODIFIERS = {
    "SHL_rdm_stability": "stability_factor", "SHL_rdm_pp": "political_power_gain",
    "SHL_rdm_war_support": "war_support_factor", "SHL_rdm_consumer_goods": "consumer_goods_factor",
    "SHL_rdm_efficiency": "production_factory_efficiency_gain_factor", "SHL_rdm_trade": "trade_opinion_factor",
    "SHL_rdm_max_efficiency": "production_factory_max_efficiency_factor",
    "SHL_rdm_construction": "production_speed_buildings_factor",
    "SHL_cld_stability": "stability_factor", "SHL_cld_war_support": "war_support_factor",
    "SHL_cld_org": "army_org_factor", "SHL_cld_conscription": "conscription_factor",
    "SHL_cld_defence": "army_defence_factor", "SHL_cld_attack": "army_attack_factor",
    "SHL_cld_dig_in": "max_dig_in",
}


def defeat_preview_idea(identifier):
    """Preview idea of a defeat-chapter focus: the route prefix shortened, plus _idea."""
    for prefix, short in (("SHL_redeem_", "SHL_rdm_"), ("SHL_cold_", "SHL_cld_")):
        if identifier.startswith(prefix):
            return short + identifier[len(prefix):] + "_idea"
    return None


def straight_chains(focuses):
    """Chains of focuses whose single parent has no other child, longest first."""
    children = defaultdict(list)
    single_parent = {}
    for identifier, focus in focuses.items():
        groups = prerequisite_blocks(focus)
        for group in groups:
            for parent in group:
                children[parent].append(identifier)
        if len(groups) == 1 and len(groups[0]) == 1:
            single_parent[identifier] = next(iter(groups[0]))
    chains = []
    for identifier in focuses:
        chain = [identifier]
        while (
            chain[-1] in single_parent
            and single_parent[chain[-1]] in focuses
            and children[single_parent[chain[-1]]] == [chain[-1]]
        ):
            chain.append(single_parent[chain[-1]])
        chains.append(chain)
    return sorted(chains, key=len, reverse=True)


class DefeatChapterTests(unittest.TestCase):
    """The defeat chapter section of SHL_focus: layout, routes, gating and rewards."""

    @classmethod
    def setUpClass(cls):
        cls.focuses = tree_focuses("defeated")

    def test_layout_and_prerequisites_match_the_chapter_grid(self):
        self.assertEqual(set(self.focuses), set(DEFEAT_LAYOUT))
        for identifier, (cell, parents) in DEFEAT_LAYOUT.items():
            with self.subTest(focus=identifier):
                focus = self.focuses[identifier]
                self.assertEqual((int(scalar(focus, "x")), int(scalar(focus, "y"))), cell)
                self.assertEqual(prerequisite_blocks(focus), parents)
        # The chapter keeps to its own block and never shares a row neighbour
        # with another section.
        others = {
            (int(scalar(f, "x")), int(scalar(f, "y")))
            for identifier, f in whole_tree_focuses().items() if identifier not in self.focuses
        }
        for (x, y), _ in DEFEAT_LAYOUT.values():
            self.assertTrue(75 <= x <= 93 and 1 <= y <= 8, (x, y))
            self.assertFalse({(x - 1, y), (x, y), (x + 1, y)} & others, (x, y))
        cells = [cell for cell, _ in DEFEAT_LAYOUT.values()]
        for row in {y for _, y in cells}:
            columns = sorted(x for x, y in cells if y == row)
            self.assertTrue(all(b - a >= 2 for a, b in zip(columns, columns[1:])), (row, columns))

    def test_exclusive_pairs_each_lead_to_an_ending(self):
        exclusive = {
            identifier: {e.value for e in block(focus, "mutually_exclusive")}
            for identifier, focus in self.focuses.items()
        }
        expected = defaultdict(set)
        for first, second in DEFEAT_PAIRS:
            expected[first].add(second)
            expected[second].add(first)
        for identifier in self.focuses:
            self.assertEqual(exclusive[identifier], expected.get(identifier, set()), identifier)
        lease = {name for name in self.focuses if name.startswith("SHL_redeem_")}
        cold = {name for name in self.focuses if name.startswith("SHL_cold_")}
        for choice in product((0, 1), repeat=len(DEFEAT_PAIRS)):
            blocked = {pair[1 - side] for pair, side in zip(DEFEAT_PAIRS, choice)}
            with self.subTest(blocked=sorted(blocked)):
                done = reachable_focuses({**self.focuses, "SHL_law_of_continuous_fire": focus_definition("SHL_law_of_continuous_fire")}, blocked)
                self.assertTrue(done & DEFEAT_ENDINGS)
                # Each route reaches its ending without the other route.
                self.assertFalse(done & lease and done & cold)
                route = lease if done & lease else cold
                self.assertEqual(route - blocked - done, set())

    def test_cold_preparation_is_bypassed_once_the_rising_is_decided(self):
        # A focus taken after either result would re-attach the closed spirit
        # or cool a lease restored by the crushed rising.
        preparation = {
            "SHL_cold_ash_cells", "SHL_cold_quarter_couriers", "SHL_cold_hidden_armouries",
            "SHL_cold_letters_to_the_sands", "SHL_cold_shifts", "SHL_cold_desert_drill",
            "SHL_cold_raid_martyrs",
        }
        for identifier, focus in self.focuses.items():
            with self.subTest(focus=identifier):
                bypass = [(e.key, e.value) for e in block(focus, "bypass")]
                if identifier in preparation:
                    self.assertEqual(bypass, [("has_variable", "SHL_cold_rising")])
                elif identifier != "SHL_cold_night_of_fire":
                    self.assertEqual(bypass, [])

    def test_no_straight_chain_is_longer_than_two(self):
        longest = straight_chains(self.focuses)[0]
        self.assertLessEqual(len(longest), 2, " < ".join(longest))

    def test_only_the_root_is_gated_and_the_swap_carries_it(self):
        for identifier, focus in self.focuses.items():
            with self.subTest(focus=identifier):
                gate = [(e.key, e.value) for e in block(focus, "allow_branch")]
                if identifier == "SHL_seal_conclave":
                    self.assertEqual(gate, [("has_country_flag", "SHL_seal_chapter_open")])
                else:
                    self.assertEqual(gate, [])
                available = [(e.key, e.value) for e in block(focus, "available")]
                self.assertIn(("SHL_country_operable", "yes"), available)
                self.assertEqual(scalar(focus, "cancel_if_invalid"), "yes")
                self.assertTrue(scalar(focus, "icon", "").startswith(("GFX_focus_", "GFX_goal_")))
        names = ("SHL/main/focuses.txt", "SHL/shared/focuses.txt", "SHL/south_war/focuses.txt")
        sources = {name: focus_builder.render_source(name) for name in names}
        self.assertIn("\t\tid = SHL_cold_embers_under_seal\n", sources["SHL/main/focuses.txt"])
        carried, clauses = focus_builder.swap_plan(sources)
        self.assertEqual(carried["SHL/south_war/focuses.txt"], ["SHL_law_of_continuous_fire"])
        self.assertEqual(clauses["SHL_law_of_continuous_fire"], "NOT = { has_focus_tree = SHL_south_war_focus }")
        clause = focus_builder.source_clauses(sources, clauses)["SHL/main/focuses.txt"]
        hidden = focus_builder.hide_carried_roots(sources["SHL/main/focuses.txt"], clause)
        self.assertIn(
            "allow_branch = { NOT = { has_focus_tree = SHL_south_war_focus } has_country_flag = SHL_seal_chapter_open }",
            hidden,
        )

    def test_every_reward_carries_its_effects(self):
        self.assertEqual(set(DEFEAT_REWARDS), set(self.focuses))
        for identifier, tokens in DEFEAT_REWARDS.items():
            with self.subTest(focus=identifier):
                reward = block(self.focuses[identifier], "completion_reward")
                found = set()
                for entry in walk_entries(reward):
                    found.add(entry.key)
                    if isinstance(entry.value, str):
                        found.add(entry.value)
                self.assertEqual(tokens - found, set())
        # Endings read the result of the rising, the lease ending the last buy-back.
        for identifier, (variable, value) in {
            "SHL_cold_fire_without_masters": ("SHL_cold_rising", "2"),
            "SHL_cold_embers_under_seal": ("SHL_cold_rising", "3"),
            "SHL_redeem_charter": ("SHL_seal_leased_count", "0"),
        }.items():
            checks = [
                (scalar(e.value, "var"), scalar(e.value, "value"))
                for e in walk_entries(block(self.focuses[identifier], "available")) if e.key == "check_variable"
            ]
            self.assertEqual(checks, [(variable, value)], identifier)

    def test_aggregate_previews_name_the_route_spirit(self):
        for identifier, focus in self.focuses.items():
            reward = block(focus, "completion_reward")
            deltas = [scalar(e.value, "var") for e in walk_entries(reward) if e.key == "add_to_variable"]
            deltas = [name for name in deltas if name in DEFEAT_MODIFIERS]
            swaps = [e.value for e in walk_entries(reward) if e.key == "swap_ideas"]
            with self.subTest(focus=identifier):
                self.assertNotIn("add_dynamic_modifier", repr(reward))
                if not deltas:
                    self.assertEqual(swaps, [])
                    continue
                route = "rdm" if deltas[0].startswith("SHL_rdm_") else "cld"
                self.assertTrue(all(name.startswith(f"SHL_{route}_") for name in deltas))
                dummy = "SHL_redeem_dummy_idea" if route == "rdm" else "SHL_cold_dummy_idea"
                refresh = "SHL_refresh_redeem_spirit" if route == "rdm" else "SHL_refresh_cold_spirit"
                self.assertEqual(len(swaps), 1)
                self.assertEqual(scalar(swaps[0], "remove_idea"), dummy)
                self.assertEqual(scalar(swaps[0], "add_idea"), defeat_preview_idea(identifier))
                self.assertIn((refresh, "yes"), [(e.key, e.value) for e in walk_entries(reward)])

    def test_previews_equal_applied_deltas(self):
        ideas = {}
        source = (ROOT / "common/ideas/ADISCORD_southern_desert_ideas.txt").read_text(encoding="utf-8-sig")
        for category in block(parse_clausewitz(source), "ideas"):
            ideas.update({e.key: e.value for e in category.value if isinstance(e.value, list)})
        for identifier, focus in self.focuses.items():
            reward = block(focus, "completion_reward")
            deltas = {
                DEFEAT_MODIFIERS[scalar(e.value, "var")]: float(scalar(e.value, "value"))
                for e in walk_entries(reward)
                if e.key == "add_to_variable" and scalar(e.value, "var") in DEFEAT_MODIFIERS
            }
            if not deltas:
                continue
            with self.subTest(focus=identifier):
                preview = defeat_preview_idea(identifier)
                self.assertTrue(preview in ideas, preview)
                applied = {e.key: float(e.value) for e in block(ideas[preview], "modifier")}
                self.assertEqual(applied, deltas)

    def test_ai_plans_take_one_route_each(self):
        plans = {e.key: e.value for e in parse_clausewitz((ROOT / "common/ai_strategy_plans/ADISCORD_SHL_plans.txt").read_text(encoding="utf-8"))}
        lease = [e.value for e in block(plans["SHL_seal_lease_plan"], "ai_national_focuses")]
        cold = [e.value for e in block(plans["SHL_seal_cold_fire_plan"], "ai_national_focuses")]
        trunk = ["SHL_law_of_continuous_fire", "SHL_seal_conclave", "SHL_seal_count_the_cold", "SHL_seal_houses_in_mourning"]
        self.assertEqual(lease[:len(trunk)], trunk)
        self.assertEqual(cold[:len(trunk)], trunk)
        self.assertTrue(all(name.startswith("SHL_redeem_") for name in lease[len(trunk):]))
        self.assertTrue(all(name.startswith("SHL_cold_") for name in cold[len(trunk):]))
        self.assertEqual(lease[-1], "SHL_redeem_charter")
        self.assertEqual(cold[-1], "SHL_cold_fire_without_masters")
        for queue in (lease, cold):
            self.assertEqual(set(queue) - reachable_focuses({**self.focuses, trunk[0]: focus_definition(trunk[0])}, set(self.focuses) - set(queue)), set())
        for name in ("SHL_seal_lease_plan", "SHL_seal_cold_fire_plan"):
            enable = [(e.key, e.value) for e in block(plans[name], "enable")]
            self.assertIn(("has_country_flag", "SHL_seal_chapter_open"), enable, name)
            self.assertEqual(scalar(block(plans[name], "weight"), "factor"), "40", name)


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
        # The desert guard contracts quote 240; the houses' course discount
        # replaces that discount instead of stacking with it.
        for focuses, price in (({"SHL_desert_guard_contracts"}, 240),
                               ({"SHL_desert_guard_contracts", "SHL_h_conclave_mercenaries"}, 225)):
            with self.subTest(guard=sorted(focuses)):
                self.setUp()
                self.m.focuses.update(focuses)
                self.m.run("SHL_refresh_furnaces")
                self.assertEqual(self.c["SHL_guard_price"], price)

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
        self.setUp()
        self.m.focuses.add("SHL_desert_guard_contracts")
        self.m.run("SHL_refresh_furnaces")
        for balance, allowed in ((239.99, False), (240, True)):
            self.c["ADISCORD_economy_treasury"] = balance
            self.assertEqual(self.m.matches(block(decision, "custom_cost_trigger"), "SHL"), allowed, balance)

    def test_desert_guard_reward_raises_two_levies_and_books_retainer(self):
        reward = block(focus_definition("SHL_desert_guard_contracts"), "completion_reward")
        self.assertIn(("unlock_decision_tooltip", "SHL_hire_desert_guard"), [(e.key, e.value) for e in reward])
        self.assertEqual([e.value for e in reward if e.key == "custom_effect_tooltip"],
                         ["SHL_desert_guard_contracts_tt", "SHL_cycle_income_minus_10_tt"])
        divisions = self.m.divisions
        income = self.c["SHL_cycle_bonus_income"]
        self.m.focuses.add("SHL_desert_guard_contracts")
        self.m.execute([e for e in reward if e.key == "hidden_effect"], "SHL")
        self.assertEqual(self.m.divisions, divisions + 2)
        self.assertEqual(self.c["SHL_cycle_bonus_income"], income - 10)
        self.assertEqual(self.c["SHL_guard_price"], 240)

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
        # Bayrat -25, every house -5.
        self.assertEqual(self.m.variables["291"]["SHL_house_loyalty"], 82 - 30)
        self.assertAlmostEqual(self.c["SHL_house_pressure"], 25 + 25 / 9)
        self.assertIn("SHL_house_demand", self.m.missions)
        self.assertNotIn("SHL_demand_pending", self.m.flags["SHL"])
        goal = block(self.decision("SHL_house_demand"), "available")
        self.assertFalse(self.m.matches(goal, "SHL"))
        self.m.variables["291"]["SHL_furnace_wear"] = 39
        self.assertTrue(self.m.matches(goal, "SHL"))
        self.m.variables["291"]["SHL_furnace_wear"] = 85
        self.m.execute(block(self.decision("SHL_house_demand"), "timeout_effect"), "SHL")
        self.assertIn("SHL_house_opposed", self.m.flags["291"])
        self.assertEqual(self.m.variables["291"]["SHL_house_loyalty"], 82 - 45)
        self.assertAlmostEqual(self.c["SHL_house_pressure"], 25 + 40 / 9)
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
        self.m.focuses.add("SHL_k_no_crests")
        self.c["SHL_political_course"] = 5
        self.m.run("SHL_update_tensions")
        self.m.run("SHL_update_tensions")
        self.assertEqual(self.c["SHL_house_pressure"], 0)
        draw = self.m.effects["SHL_crisis_draw"]
        guarded = [
            e for e in walk_entries(draw)
            if e.key == "modifier" and ("has_completed_focus", "SHL_c_open_ledger") in [(c.key, c.value) for c in e.value]
        ]
        self.assertEqual(len(guarded), 2)
        text = repr(draw)
        self.assertLess(text.index("SHL_c_open_ledger"), text.index("ADISCORD_shl_crisis.4"))
        self.assertGreater(text.rindex("SHL_c_open_ledger"), text.index("ADISCORD_shl_crisis.4"))
        self.assertLess(text.rindex("SHL_c_open_ledger"), text.index("ADISCORD_shl_crisis.5"))

    def test_neighbour_revanche_is_scheduled_a_year_after_victory_and_the_revision_buys_the_claim_once(self):
        self.c["SHL_water_crisis"] = 1
        self.m.focuses.add("SHL_qanat_guard")
        self.m.run("SHL_start_qanat_war")
        self.m.run("SHL_qanat_war_victory")
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
        for effect in ("SHL_glp_war_victory", "SHL_kyz_war_victory"):
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
        # Territorial redistribution is verified separately against state ownership.
        source = (ROOT / "common/scripted_effects/ADISCORD_SHL_scripted_effects.txt").read_text(encoding="utf-8")
        integration = source.split("SHL_annex_integration_directorate = {", 1)[1].split("# Regency:", 1)[0]
        self.assertIn("SHL_form_furnace_administrations = yes", integration)
        self.assertNotIn("add_timed_idea", integration)

    def test_sell_stations_pays_once_and_returns_the_stations_to_an_existing_kadir(self):
        decision = self.decision("SHL_sell_stations")
        self.assertEqual(scalar(decision, "fire_only_once"), "yes")
        available = block(decision, "available")
        reward = block(focus_definition("SHL_h_road_stations"), "completion_reward")
        stations = ("234", "242")
        for owners in product(("KDR", "SHL"), repeat=2):
            with self.subTest(owners=owners):
                self.setUp()
                self.m.ownership.update(zip(stations, owners))
                self.m.control.update(zip(stations, owners))
                self.m.execute(reward, "SHL")
                self.assertEqual(self.m.infrastructure, 2 if owners == ("SHL", "SHL") else 0)
                self.assertTrue(self.m.matches(available, "SHL"))
                self.m.control["234"] = "EFL"
                self.assertFalse(self.m.matches(available, "SHL"))
                self.m.run("SHL_sell_road_stations")
                self.assertEqual(self.c["ADISCORD_economy_treasury"], 1000)
                self.m.control["234"] = owners[0]
                self.m.countries["KDR"]["exists"] = False
                self.assertFalse(self.m.matches(available, "SHL"))
                self.m.run("SHL_sell_road_stations")
                self.assertEqual(self.c["ADISCORD_economy_treasury"], 1000)
                self.m.countries["KDR"]["exists"] = True
                self.m.execute(block(decision, "complete_effect"), "SHL")
                self.assertFalse(self.m.matches(available, "SHL"))
                self.m.run("SHL_sell_road_stations")
                self.assertEqual(self.c["ADISCORD_economy_treasury"], 1150)
                for state in stations:
                    self.assertEqual((self.m.ownership[state], self.m.control[state]), ("KDR", "KDR"))
                    self.assertNotIn("SHL", self.m.claims[state])

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
        self.c["SHL_keizan_state"] = 1
        self.m.missions.add("SHL_keizan_deadline")
        self.m.run("SHL_accept_cistern_charter", scope="KYZ")
        self.assertEqual(self.m.factions.get("KYZ"), "SHL")
        self.assertEqual((self.c["SHL_kyz_outcome"], self.c["SHL_keizan_state"]), (3, 3))
        self.assertNotIn("SHL_keizan_deadline", self.m.missions)
        self.assertFalse(self.m.matches(self.m.triggers["SHL_can_offer_cistern_charter"], "SHL"))


class CaravanJourneyTests(unittest.TestCase):
    STOPS = ("sevir", "barak", "fada", "irim", "maren", "loren", "svetlogorsk", "home")
    MARKETS = (("280", "KYZ"), ("267", "MZR"), ("28", "STP"), ("24", "VAL"), ("175", "WEF"), ("70", "EFL"), ("688", "NAM"))
    CASH = "ADISCORD_economy_treasury"
    RIFLES = "infantry_equipment_0"
    KITS = "support_equipment_1"
    TRUCKS = "motorized_equipment_1"
    GUNS = "artillery_equipment_1"

    class Machine(ScriptMachine):
        def __init__(self, effects, triggers):
            super().__init__(effects, triggers)
            self.producer_stock = defaultdict(float)
            self.arrays = defaultdict(list)
            self.wine_grants = []
            self.timer_adjustments = defaultdict(int)
            self.buyer_missions = {}
            self.roll = 99
            self.bid_chances = []

        def matches(self, items, scope, target=None):
            if len(items) == 1 and items[0].key == "has_idea" and items[0].value == "SHL_cellar_wines":
                return any(country == scope for country, _, _ in self.wine_grants)
            if len(items) == 1 and items[0].key == "any_of_scopes":
                fields = items[0].value
                candidates = self.arrays[scope, scalar(fields, "array")]
                conditions = [e for e in fields if e.key != "array"]
                return any(self.condition_scope(conditions, buyer, scope, target) for buyer in candidates)
            if len(items) == 1 and items[0].key == "has_active_mission" and scope != "SHL":
                return (scope, items[0].value) in self.buyer_missions
            return super().matches(items, scope, target)

        def stock_count(self, scope, equipment):
            if equipment in ("infantry_equipment", "artillery_equipment", "motorized_equipment", "support_equipment"):
                return sum(qty for (owner, model), qty in self.equipment.items()
                           if owner == scope and model.removeprefix("ADISCORD_").rsplit("_", 1)[0] == equipment)
            return super().stock_count(scope, equipment)

        def value(self, value, scope):
            if isinstance(value, str) and value.startswith("num_equipment@"):
                return self.stock_count(scope, value.split("@", 1)[1])
            if isinstance(value, str) and "^" in value:
                name, index = value.split("^")
                return self.arrays[scope, name][int(self.value(index, scope))]
            return super().value(value, scope)

        def execute(self, items, scope, target=None):
            # Preserve adjacent if/else branches when delegating the ordinary effects.
            unhandled = []
            for entry in items:
                key, fields = entry.key, entry.value
                name = scalar(fields, "var", "") if isinstance(fields, list) else ""
                if key not in {"for_loop_effect", "clear_array", "add_to_array", "add_equipment_to_stockpile",
                               "clamp_temp_variable", "add_timed_idea", "add_days_mission_timeout", "random"} and "^" not in name:
                    unhandled.append(entry)
                    continue
                super().execute(unhandled, scope, target)
                unhandled = []
                if key == "random":
                    chance = int(scalar(fields, "chance"))
                    self.bid_chances.append(chance)
                    if self.roll < chance:
                        self.execute([effect for effect in fields if effect.key != "chance"], scope, target)
                elif key == "clear_array":
                    self.arrays[scope, fields].clear()
                elif key == "add_to_array":
                    self.arrays[scope, scalar(fields, "array")].append(self.value(scalar(fields, "value"), scope))
                elif key == "add_days_mission_timeout":
                    mission = scalar(fields, "mission")
                    if mission not in self.missions:
                        raise AssertionError(f"Cannot adjust an inactive countdown: {mission}")
                    self.timer_adjustments[mission] += int(scalar(fields, "days"))
                elif key == "add_timed_idea":
                    self.wine_grants.append((scope, scalar(fields, "idea"), int(scalar(fields, "days"))))
                elif key == "for_loop_effect":
                    body = [e for e in fields if e.key not in ("value", "end")]
                    for i in range(int(scalar(fields, "end"))):
                        self.variables[scope][scalar(fields, "value")] = i
                        self.execute(body, scope, target)
                elif key == "clamp_temp_variable":
                    low = self.value(scalar(fields, "min"), scope)
                    high = self.value(scalar(fields, "max"), scope)
                    self.variables[scope][name] = max(low, min(high, self.value(name, scope)))
                elif "^" in name:
                    array, index = name.split("^")
                    change = self.value(scalar(fields, "value"), scope)
                    if key == "subtract_from_variable":
                        change = -change
                    elif key != "add_to_variable":
                        raise AssertionError(f"Unexpected array operation: {key}")
                    self.arrays[scope, array][int(self.value(index, scope))] += change
                else:
                    model = scalar(fields, "type")
                    producer = scalar(fields, "producer", "THIS")
                    producer = {"THIS": scope, "PREV": self.previous_scope}.get(producer, producer)
                    amount = self.value(scalar(fields, "amount"), scope)
                    stock = (scope, model, producer)
                    if amount < 0:
                        amount = -min(-amount, self.producer_stock[stock])
                    self.producer_stock[stock] += amount
                    self.equipment[scope, model] += amount
            super().execute(unhandled, scope, target)

    @classmethod
    def setUpClass(cls):
        cls.effects = parse_clausewitz(EFFECT_PATH.read_text(encoding="utf-8"))
        cls.triggers = parse_clausewitz(TRIGGER_PATH.read_text(encoding="utf-8"))
        source = (ROOT / "common/decisions/ADISCORD_SHL_decisions.txt").read_text(encoding="utf-8")
        cls.decisions = {d.key: d.value for d in block(parse_clausewitz(source), "SHL_caravans")}
        events = parse_clausewitz((ROOT / "events/ADISCORD_SHL_events.txt").read_text(encoding="utf-8"))
        cls.offer = next(e.value for e in events if e.key == "country_event" and scalar(e.value, "id") == "ADISCORD_SHL.206")
        cls.options = {scalar(opt.value, "name").rsplit(".", 1)[-1]: opt.value for opt in cls.offer if opt.key == "option"}
        loc = ROOT / "common/scripted_localisation/ADISCORD_SHL_scripted_loc.txt"
        cls.selectors = {scalar(e.value, "name"): e.value for e in parse_clausewitz(loc.read_text(encoding="utf-8"))}
        cls.strings = {}
        for lang in ("russian", "english"):
            path = ROOT / f"localisation/{lang}/ADISCORD_SHL_l_{lang}.yml"
            cls.strings[lang] = dict(re.findall(r'^ ([\w.]+):\d* "(.*)"$', path.read_text(encoding="utf-8-sig"), re.M))

    def setUp(self):
        self.m = self.Machine(self.effects, self.triggers)
        self.elapsed = 0
        self.m.focuses.add("SHL_law_of_continuous_fire")
        self.m.flags["SHL"].add("SHL_furnaces_initialized")
        for state, tag in self.MARKETS:
            self.m.control[state] = tag
            self.m.countries.setdefault(tag, {"exists": True})
        self.m.fuel["SHL"] = 400
        self.m.variables["SHL"][self.CASH] = 10
        self.c = self.m.variables["SHL"]

    def supply(self, country, model, amount, producer=None):
        self.m.equipment[country, model] += amount
        self.m.producer_stock[country, model, producer or country] += amount

    def dispatch(self, cargo="rifles"):
        self.m.execute(block(self.decisions["SHL_road_send_" + cargo], "complete_effect"), "SHL")

    def open_long_route(self):
        self.m.focuses.update({"SHL_chancery_of_the_gate", "SHL_desert_caravanserai", "SHL_northern_road"})

    def pass_local_markets(self):
        for stop, buyer in (("sevir", "KYZ"), ("barak", "MZR")):
            self.arrive(stop)
            self.answer(buyer, "a")

    def arrive(self, stop):
        mission = "SHL_road_to_" + stop
        self.assertIn(mission, self.m.missions)
        self.elapsed += int(scalar(self.decisions[mission], "days_mission_timeout")) + self.m.timer_adjustments.pop(mission, 0)
        self.m.missions.remove(mission)
        self.m.execute(block(self.decisions[mission], "timeout_effect"), "SHL")

    def answer(self, buyer, choice):
        self.m.execute(block(self.options[choice], "hidden_effect"), buyer)

    def journal_text(self, key, lang, scope="SHL"):
        if key in self.selectors:
            first = next(e.value for e in self.selectors[key] if e.key == "text" and
                         self.m.matches(block(e.value, "trigger"), scope))
            key = scalar(first, "localization_key").strip('"')
        return re.sub(r"\[(?:([A-Z]+)\.)?(SHLGet\w+)\]|\$(\w+)\$",
                      lambda m: self.journal_text(m[2] or m[3], lang, m[1] or scope),
                      self.strings[lang][key]).replace("[This.GetName]", scope)

    def test_metal_offer_headings_and_contract_terms_follow_each_buyer_in_the_journal(self):
        partners = [scalar(e.value, "SHL_caravan_partners") for e in self.m.effects["SHL_initialize_programmes"]
                    if e.key == "add_to_array"]
        self.m.arrays["SHL", "SHL_caravan_partners"] = partners
        for lang in self.strings:
            self.assertEqual(self.journal_text("SHLGetCaravanOfferHeading", lang), "")
            self.assertEqual(self.journal_text("SHLGetCaravanContractHeading", lang),
                             self.journal_text("SHL_caravan_contracts_locked", lang))
        self.m.loaded_trees.append("SHL_south_war_focus")
        for lang in self.strings:
            self.assertEqual(self.journal_text("SHLGetCaravanContractHeading", lang),
                             self.journal_text("SHL_caravan_contracts_locked_war", lang))
        self.m.loaded_trees.clear()
        self.m.focuses.add("SHL_metal_brokers")
        for lang in self.strings:
            self.assertEqual(self.journal_text("SHLGetCaravanOfferHeading", lang),
                             self.strings[lang]["SHL_caravan_pending_empty"])
            self.assertEqual(self.journal_text("SHLGetCaravanContractHeading", lang),
                             self.journal_text("SHL_caravan_contracts_empty", lang))
        self.m.flags["GLP"].add("SHL_metal_offer_pending")
        for buyer, term in (("VAL", "year"), ("STP", "two_years")):
            self.m.flags[buyer].add("SHL_metal_client")
            self.m.buyer_missions[buyer, "SHL_metal_contract_" + term] = 100
        self.m.variables["STP"]["SHL_metal_arrears"] = 1
        for lang in self.strings:
            journal = self.journal_text("SHL_caravans_desc", lang)
            self.assertIn(self.strings[lang]["SHL_caravan_pending_heading"], journal)
            active = self.journal_text("SHLGetCaravanContractHeading", lang)
            offers, contracts = journal.split(active)
            self.assertIn("GLP", offers)
            self.assertNotIn("GLP", contracts)
            self.assertNotIn("VAL", offers)
            self.assertNotIn("STP", offers)
            for buyer, term in (("VAL", "year"), ("STP", "two_years")):
                row = self.journal_text("SHLGetCaravanRow", lang, buyer)
                self.assertIn(row, contracts)
                self.assertIn(buyer, row)
                self.assertIn("[?SHL_metal_cycle_price|0]", row)
                self.assertIn("days_mission_timeout@SHL_metal_contract_" + term + "|0", row)
                self.assertEqual("[?SHL_metal_arrears|0]" in row, buyer == "STP")

    def test_journal_traces_real_leg_clock_and_pending_buyer_until_return(self):
        self.open_long_route()
        self.supply("SHL", self.RIFLES, 10000)
        self.dispatch()
        for i, stop in enumerate(self.STOPS):
            mission = "SHL_road_to_" + stop
            self.assertIn(mission, self.m.missions)
            for lang in self.strings:
                journal = self.journal_text("SHLGetRoadJournal", lang)
                self.assertEqual(re.findall(r"days_mission_timeout@(SHL_road_to_\w+)", journal), [mission])
                pending = re.findall(r"\[(\d+)\.Controller\.GetName\]", journal)
                self.assertEqual(pending, [self.MARKETS[i - 1][0]] if i else [])
            if i == 1:
                self.answer("KYZ", "a")
                for lang in self.strings:
                    self.assertNotIn("Controller.GetName", self.journal_text("SHLGetRoadJournal", lang))
            self.arrive(stop)
        self.assertIn("SHL_road_offer", self.m.flags["NAM"])
        self.m.variables["NAM"][self.CASH] = 75
        self.answer("NAM", "b")
        self.assertEqual(self.m.variables["NAM"][self.CASH], 75)
        self.assertEqual(self.m.equipment["NAM", self.RIFLES], 0)
        self.assertEqual(self.m.equipment["SHL", self.RIFLES], 10000)
        for lang in self.strings:
            for key in ("SHLGetRoadJournal", "SHLGetRoadPending"):
                report = self.journal_text(key, lang)
                self.assertNotIn("Controller.GetName", report)
                self.assertNotIn("days_mission_timeout@", report)
            self.assertEqual(self.journal_text("SHLGetRoadInvitation", lang, "NAM"),
                             self.strings[lang]["SHL_road_invitation_closed"])

    def test_calendar_market_controllers_and_expiry(self):
        self.open_long_route()
        self.supply("SHL", self.RIFLES, 10000)
        self.dispatch()
        days = 0
        for i, stop in enumerate(self.STOPS):
            definition = self.decisions["SHL_road_to_" + stop]
            self.assertFalse(self.m.matches(block(definition, "available"), "SHL"))
            self.assertEqual(scalar(definition, "selectable_mission"), "no")
            days += int(scalar(definition, "days_mission_timeout"))
            self.arrive(stop)
            if i < len(self.MARKETS):
                tag = self.MARKETS[i][1]
                self.assertTrue(self.m.matches(self.m.triggers["SHL_road_quote_current"], tag))
                self.answer(tag, "a")
                self.assertNotIn("SHL_road_offer", self.m.flags[tag])
        self.assertEqual(days, 365)
        self.assertEqual(self.m.scheduled, ["ADISCORD_SHL.206"] * 7 + ["ADISCORD_SHL.207"])
        self.assertEqual(self.m.equipment["SHL", self.RIFLES], 10000)
        self.assertFalse(self.m.missions)
        self.assertEqual(scalar(self.offer, "timeout_days"), "7")
        self.assertEqual(scalar(block(self.offer, "option"), "name"), "ADISCORD_SHL.206.a")
        self.assertEqual(scalar(block(block(self.m.effects["SHL_road_open_market"], "if"), "set_country_flag"), "days"), "7")

    def test_cash_and_barter_balances_and_arrival_once(self):
        self.open_long_route()
        self.supply("SHL", self.RIFLES, 6000)
        self.supply("SHL", self.RIFLES, 4000, "EFL")
        self.dispatch()
        self.assertEqual((self.c[self.CASH], self.m.fuel["SHL"], self.m.equipment["SHL", self.RIFLES]), (0, 0, 0))
        self.dispatch()
        self.assertEqual(self.c["ADISCORD_economy_current_month_action_costs"], 10)
        self.m.control["28"] = "MZR"
        self.pass_local_markets()
        self.arrive("fada")
        self.assertNotIn("SHL_road_offer", self.m.flags["STP"])
        self.supply("MZR", self.GUNS, 12, "KYZ")
        self.answer("MZR", "c")
        self.answer("MZR", "c")
        self.assertEqual(self.m.equipment["MZR", self.GUNS], 0)
        self.arrive("irim")
        self.supply("VAL", self.TRUCKS, 24)
        self.answer("VAL", "c")
        self.assertEqual(self.m.equipment["VAL", self.TRUCKS], 0)
        self.arrive("maren")
        self.answer("WEF", "a")
        self.arrive("loren")
        self.m.variables["EFL"][self.CASH] = 75
        self.answer("EFL", "b")
        self.answer("EFL", "b")
        self.assertEqual(self.m.variables["EFL"][self.CASH], 0)
        self.arrive("svetlogorsk")
        self.m.fuel["NAM"] = 5400
        self.answer("NAM", "c")
        self.assertEqual(self.m.fuel["NAM"], 0)
        self.assertEqual([self.m.equipment[tag, self.RIFLES] for tag in ("MZR", "VAL", "EFL", "NAM")], [2500] * 4)
        def balance():
            return (self.c[self.CASH], self.m.fuel["SHL"], self.m.equipment["SHL", self.GUNS], self.m.equipment["SHL", self.TRUCKS])

        self.assertEqual(balance(), (0, 0, 0, 0))
        self.arrive("home")
        self.m.run("SHL_road_unload")
        self.assertEqual(balance(), (75, 5400, 12, 24))
        self.assertEqual(self.m.bid_chances, [])
        self.assertEqual(self.c["ADISCORD_economy_current_month_action_income"], 75)
        self.assertNotIn("SHL_road_leg", self.c)

    def test_shortages_war_and_inheritance(self):
        self.open_long_route()
        self.supply("SHL", self.KITS, 1999.9)
        self.dispatch("kits")
        self.assertNotIn("SHL_road_leg", self.c)
        self.supply("SHL", self.KITS, 0.1)
        self.m.fuel["SHL"] = 399.9
        self.dispatch("kits")
        self.m.fuel["SHL"] = 400
        self.c[self.CASH] = 9.9
        self.dispatch("kits")
        self.assertEqual(self.m.equipment["SHL", self.KITS], 2000)
        self.c[self.CASH] = 10
        self.dispatch("kits")
        self.m.wars.add(frozenset(("SHL", "STP")))
        self.pass_local_markets()
        self.arrive("fada")
        self.assertNotIn("SHL_road_offer", self.m.flags["STP"])
        self.arrive("irim")
        self.m.variables["VAL"][self.CASH] = 74.99
        self.answer("VAL", "b")
        self.assertEqual(self.c["SHL_road_kits"], 2000)
        self.m.variables["VAL"][self.CASH] = 75
        self.m.control["24"] = "GLP"
        self.answer("VAL", "b")
        self.assertEqual(self.m.variables["VAL"][self.CASH], 75)
        self.arrive("maren")
        self.answer("WEF", "a")
        self.arrive("loren")
        self.m.fuel["EFL"] = 3600
        self.answer("EFL", "c")
        self.assertEqual(self.m.equipment["EFL", self.KITS], 500)
        self.m.run("SHL_road_settle_annexation", "KYZ")
        self.m.run("SHL_road_settle_annexation", "KYZ")
        self.m.execute(block(self.decisions["SHL_road_to_home"], "timeout_effect"), "SHL")
        self.assertEqual((self.m.equipment["KYZ", self.KITS], self.m.fuel["KYZ"]), (1500, 3600))
        self.assertEqual(self.m.bid_chances, [])
        self.assertFalse(self.m.missions)
        self.assertNotIn("SHL_road_leg", self.c)
        self.assertNotIn("SHL_road_cash", self.c)

    def test_wholesale_mixed_lots_wine_and_deferred_receipts(self):
        self.open_long_route()
        modern = "ADISCORD_infantry_equipment_2163"
        self.c[self.CASH] = 110
        self.supply("SHL", self.RIFLES, 16000, "STP")
        self.supply("SHL", modern, 84000, "EFL")
        self.dispatch("wholesale")
        self.assertEqual(self.m.stock_count("SHL", "infantry_equipment"), 0)
        self.assertEqual((self.c[self.CASH], self.m.fuel["SHL"], self.c["SHL_road_wine"]), (0, 0, 5))
        self.pass_local_markets()
        self.arrive("fada")
        self.m.variables["STP"][self.CASH] = 300
        self.answer("STP", "twenty")
        self.assertEqual(self.c["SHL_road_rifles"], 100000)
        self.answer("STP", "ten")
        self.answer("STP", "ten")
        self.assertEqual(self.m.equipment["STP", self.RIFLES], 10000)
        self.arrive("irim")
        self.m.variables["VAL"][self.CASH] = 539.99
        self.answer("VAL", "twenty")
        self.assertEqual(self.c["SHL_road_rifles"], 90000)
        self.m.variables["VAL"][self.CASH] = 540
        self.answer("VAL", "twenty")
        self.assertEqual((self.m.equipment["VAL", self.RIFLES], self.m.equipment["VAL", modern]), (6000, 14000))
        self.arrive("maren")
        self.m.variables["WEF"][self.CASH] = 80
        self.answer("WEF", "wine")
        self.answer("WEF", "wine")
        self.assertEqual(self.m.wine_grants, [("WEF", "SHL_cellar_wines", 90)])
        self.assertEqual((self.c["SHL_road_wine"], self.c["SHL_road_rifles"]), (4, 70000))
        for _, tag in self.MARKETS[2:5]:
            self.assertEqual(self.m.variables[tag][self.CASH], 0)
        self.assertEqual(self.c[self.CASH], 0)
        for lang in self.strings:
            journal = self.journal_text("SHLGetRoadJournal", lang)
            self.assertIn("[?SHL_road_wine|0]", journal)
            self.assertIn("[?SHL_road_cash|0]", journal)
            self.assertNotIn("SHL_road_deposit_refund", journal)
            for absent in ("SHL_road_kits", "SHL_road_guns", "SHL_road_trucks", "SHL_road_fuel"):
                self.assertNotIn("[?" + absent + "|", journal)
        self.m.control["70"] = "WEF"
        self.m.variables["WEF"][self.CASH] = 80
        self.arrive("loren")
        self.answer("WEF", "wine")
        self.assertEqual(self.m.variables["WEF"][self.CASH], 80)
        self.assertEqual(len(self.m.wine_grants), 1)
        self.arrive("svetlogorsk")
        self.arrive("home")
        self.assertEqual(self.c["SHL_road_cash"], 920)
        self.assertEqual(self.c[self.CASH], 1000)
        self.assertEqual(self.c["SHL_road_deposit_refund"], 80)
        for lang in self.strings:
            settlement = self.journal_text("SHL_road_settlement_lines", lang)
            self.assertIn(settlement, self.journal_text("SHLGetRoadJournal", lang))
            self.assertIn(settlement, self.journal_text("ADISCORD_SHL.207.d", lang))
            self.assertIn("[?SHL_road_cash|0]", settlement)
            self.assertIn("[?SHL_road_deposit_refund|0]", settlement)
            self.assertNotIn("[?SHL_road_wine|0]", settlement.split(r"\n")[0])
            self.assertNotRegex(self.journal_text("ADISCORD_SHL.207.d", lang), r"§[YHOG]")
        self.assertEqual(self.m.equipment["SHL", modern], 70000)
        self.m.run("SHL_road_unload")
        self.assertEqual(self.c[self.CASH], 1000)
        self.m.fuel["SHL"] = 400
        self.dispatch()
        self.assertNotIn("SHL_road_leg", self.c)
        self.assertEqual(self.c["SHL_road_deposit_refund"], 80)
        self.supply("SHL", self.RIFLES, 10000)
        self.dispatch()
        self.assertIn("SHL_road_leg", self.c)
        self.assertNotIn("SHL_road_deposit_refund", self.c)
        for lang in self.strings:
            self.assertEqual(self.journal_text("SHLGetRoadRefund", lang), "")
            self.assertEqual(self.journal_text("SHLGetRoadReturnReceipt", lang), "")

    def test_five_bulk_sales_exhaust_the_manifest(self):
        self.open_long_route()
        self.c[self.CASH] = 110
        self.supply("SHL", self.RIFLES, 99999.9)
        self.dispatch("wholesale")
        self.assertNotIn("SHL_road_leg", self.c)
        self.supply("SHL", self.RIFLES, 0.1)
        self.dispatch("wholesale")
        self.pass_local_markets()
        for stop, (_, buyer) in zip(self.STOPS[2:], self.MARKETS[2:]):
            self.arrive(stop)
            self.m.variables[buyer][self.CASH] = 540
            self.answer(buyer, "twenty")
            self.assertEqual(self.m.equipment[buyer, self.RIFLES], 20000)
        self.assertEqual((self.c["SHL_road_rifles"], self.c[self.CASH]), (0, 0))
        self.arrive("home")
        self.assertEqual((self.c["SHL_road_cash"], self.c[self.CASH]), (2700, 2800))

    def test_bulk_failed_loading_and_annexation_return_original_models(self):
        modern = "ADISCORD_infantry_equipment_2200"
        self.c[self.CASH] = 110
        self.supply("SHL", self.RIFLES, 20000)
        self.supply("SHL", modern, 79000, "STP")
        self.supply("SHL", modern, 1000, "unavailable producer")
        self.dispatch("wholesale")
        self.assertNotIn("SHL_road_leg", self.c)
        self.assertEqual((self.m.equipment["SHL", self.RIFLES], self.m.equipment["SHL", modern]), (20000, 80000))
        self.assertEqual((self.c[self.CASH], self.m.fuel["SHL"]), (110, 400))
        self.supply("SHL", modern, 1000)
        self.dispatch("wholesale")
        self.m.run("SHL_road_settle_annexation", "KYZ")
        self.m.run("SHL_road_settle_annexation", "KYZ")
        self.assertEqual((self.m.equipment["KYZ", self.RIFLES], self.m.equipment["KYZ", modern]), (20000, 80000))
        self.assertEqual((self.m.variables["KYZ"][self.CASH], self.m.equipment["SHL", modern]), (100, 1000))
        self.assertFalse(self.m.missions)

    def test_route_and_relay_deadlines_follow_the_focus_tree(self):
        for tier, relays, expected, names in (
            (1, False, 90, ("sevir", "barak", "home")),
            (1, True, 72, ("sevir", "barak", "home")),
            (2, False, 210, ("sevir", "barak", "fada", "irim", "home")),
            (2, True, 168, ("sevir", "barak", "fada", "irim", "home")),
            (3, False, 365, self.STOPS),
            (3, True, 292, self.STOPS),
        ):
            with self.subTest(tier=tier, relays=relays):
                self.setUp()
                if tier >= 2:
                    self.m.focuses.add("SHL_chancery_of_the_gate")
                self.m.focuses.add("SHL_sand_patrols" if relays else "SHL_desert_caravanserai")
                if tier == 3:
                    self.m.focuses.add("SHL_northern_road")
                self.supply("SHL", self.RIFLES, 10000)
                for lang in self.strings:
                    self.assertRegex(self.journal_text("SHLGetRoadPlan", lang), rf"\b{expected}\b")
                self.dispatch()
                self.assertEqual(self.c["SHL_road_itinerary"], tier)
                for stop in names:
                    self.arrive(stop)
                self.assertEqual(self.elapsed, expected)
                self.assertFalse(self.m.missions)

    def test_new_charter_preserves_booked_route_and_relays_apply_from_next_leg(self):
        self.supply("SHL", self.RIFLES, 10000)
        self.dispatch()
        self.m.focuses.update({"SHL_chancery_of_the_gate", "SHL_sand_patrols", "SHL_northern_road"})
        for lang in self.strings:
            self.assertIn(self.strings[lang]["SHL_road_name_local"], self.journal_text("SHLGetRoadJournal", lang))
            self.assertNotIn(self.strings[lang]["SHL_road_name_long"], self.journal_text("SHLGetRoadJournal", lang))
        self.arrive("sevir")
        self.assertEqual(self.elapsed, 30)
        self.arrive("barak")
        self.arrive("home")
        self.assertEqual(self.elapsed, 78)
        self.c[self.CASH] = 10
        self.m.fuel["SHL"] = 400
        self.dispatch()
        self.assertEqual(self.c["SHL_road_itinerary"], 3)

    def test_factor_houses_fill_one_mixed_order_per_market(self):
        self.c[self.CASH] = 110
        self.supply("SHL", self.RIFLES, 100000)
        self.dispatch("wholesale")
        self.arrive("sevir")
        self.m.variables["KYZ"][self.CASH] = 620
        self.answer("KYZ", "fair_order")
        self.assertEqual(self.c["SHL_road_cash"], 0)
        self.m.focuses.update({"SHL_chancery_of_the_gate", "SHL_desert_caravanserai"})
        self.m.variables["KYZ"][self.CASH] = 619.99
        self.answer("KYZ", "fair_order")
        self.assertEqual(self.c["SHL_road_cash"], 0)
        self.m.variables["KYZ"][self.CASH] = 620
        self.answer("KYZ", "fair_order")
        self.answer("KYZ", "fair_order")
        self.assertEqual(self.m.variables["KYZ"][self.CASH], 0)
        self.assertEqual(self.m.equipment["KYZ", self.RIFLES], 20000)
        self.assertEqual(self.m.wine_grants, [("KYZ", "SHL_cellar_wines", 90)])
        self.assertEqual((self.c[self.CASH], self.c["SHL_road_cash"]), (0, 620))
        self.arrive("barak")
        self.arrive("home")
        self.assertEqual((self.c[self.CASH], self.m.equipment["SHL", self.RIFLES]), (700, 80000))

    def test_partial_producer_debit_restores_stock_and_keeps_payment(self):
        self.supply("SHL", self.RIFLES, 9000)
        self.supply("SHL", self.RIFLES, 1000, "unavailable producer")
        self.dispatch()
        self.assertEqual(self.m.equipment["SHL", self.RIFLES], 10000)
        self.assertEqual((self.c[self.CASH], self.m.fuel["SHL"]), (10, 400))
        self.assertNotIn("SHL_road_leg", self.c)

    def test_return_market_thresholds_income_and_receipt(self):
        route = ("sevir", "barak", "fada", "irim")
        for cargo, model, load in (("rifles", self.RIFLES, 10000), ("kits", self.KITS, 2000)):
            for lots_remaining, chance in ((1, 80), (2, 60), (3, 40), (4, 40)):
                for roll in (chance - 1, chance):
                    with self.subTest(cargo=cargo, remaining=lots_remaining, roll=roll):
                        self.setUp()
                        self.m.focuses.add("SHL_chancery_of_the_gate")
                        self.supply("SHL", model, load)
                        self.dispatch(cargo)
                        foreign_lots = 4 - lots_remaining
                        for i, stop in enumerate(route):
                            self.arrive(stop)
                            buyer = self.MARKETS[i][1]
                            self.m.variables[buyer][self.CASH] = 75
                            self.answer(buyer, "b" if i < foreign_lots else "a")
                        self.assertEqual(self.c[self.CASH], 0)
                        self.m.roll = roll
                        self.arrive("home")
                        # A second callback cannot draw a new bid or credit the sale twice.
                        self.m.execute(block(self.decisions["SHL_road_to_home"], "timeout_effect"), "SHL")
                        self.assertEqual(self.m.bid_chances, [chance])
                        home_lots = min(2, lots_remaining) if roll < chance else 0
                        self.assertEqual(self.c["SHL_road_home_cash"], home_lots * 50)
                        self.assertEqual(self.c.get("SHL_road_home_" + cargo, 0), home_lots * load // 4)
                        self.assertEqual(self.m.equipment["SHL", model], (lots_remaining - home_lots) * load // 4)
                        revenue = 75 * foreign_lots + 50 * home_lots
                        self.assertEqual(self.c[self.CASH], revenue)
                        self.assertEqual(self.c["ADISCORD_economy_current_month_action_income"], revenue)

    def test_return_market_checks_the_focus_on_arrival_and_clears_old_receipts(self):
        self.supply("SHL", self.RIFLES, 10000)
        self.m.roll = 0
        self.dispatch()
        self.pass_local_markets()
        self.arrive("home")
        self.assertEqual(self.m.bid_chances, [])
        self.assertNotIn("SHL_road_home_cash", self.c)
        self.c[self.CASH] = 10
        self.m.fuel["SHL"] = 400
        self.dispatch()
        self.pass_local_markets()
        self.m.focuses.add("SHL_chancery_of_the_gate")
        self.arrive("home")
        self.assertEqual(self.m.bid_chances, [40])
        self.assertEqual(self.c["SHL_road_home_rifles"], 5000)
        self.m.fuel["SHL"] = 400
        self.supply("SHL", self.KITS, 2000)
        self.dispatch("kits")
        self.assertIn("SHL_road_leg", self.c)
        self.assertNotIn("SHL_road_home_rifles", self.c)
        self.assertNotIn("SHL_road_home_cash", self.c)

    def test_home_bid_preserves_retained_rifle_models_and_wine_deposit(self):
        modern = "ADISCORD_infantry_equipment_2200"
        self.c[self.CASH] = 110
        self.supply("SHL", self.RIFLES, 30000)
        self.supply("SHL", modern, 70000, "STP")
        self.dispatch("wholesale")
        self.pass_local_markets()
        self.m.focuses.add("SHL_chancery_of_the_gate")
        self.m.roll = 39
        self.arrive("home")
        self.assertEqual(self.m.bid_chances, [40])
        self.assertEqual(self.c["SHL_road_home_rifles"], 50000)
        self.assertEqual(self.c["SHL_road_home_cash"], 1000)
        self.assertEqual(self.c[self.CASH], 1100)
        self.assertEqual(self.c["SHL_road_deposit_refund"], 100)
        self.assertEqual(self.c["SHL_road_wine"], 5)
        self.assertEqual((self.m.equipment["SHL", self.RIFLES], self.m.equipment["SHL", modern]), (30000, 20000))
        self.assertFalse(self.m.arrays["SHL", "SHL_road_rifle_models"])


class ExternalContractTests(unittest.TestCase):
    """Packet price under Svetlogorye's oil policy and the metal contracts of the Golden Gates."""

    BUYERS = ("VAL", "STP", "STS", "RUS", "GLP", "NAM")
    PRICES = {None: 40, "NAM_oil_client": 35, "NAM_fuel_embargo_modifier": 50}

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
        self.m.focuses.add("SHL_metal_market")
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
        self.assertEqual(self.c["SHL_packet_price"], 40)
        for marker, price in self.PRICES.items():
            with self.subTest(marker=marker):
                self.setUp()
                self.price_marker(marker)
                self.m.run("SHL_refresh_furnaces")
                self.assertEqual(self.c["SHL_packet_price"], price)
                self.assertEqual(self.c["SHL_auto_packet_price"], price + 5)
        # The embargo quote wins while both markers are present.
        self.m.flags["SHL"].add("NAM_oil_client")
        self.m.dynamic.add("NAM_fuel_embargo_modifier")
        self.m.run("SHL_refresh_furnaces")
        self.assertEqual(self.c["SHL_packet_price"], 50)
        self.m.dynamic.clear()
        self.m.flags["SHL"].discard("NAM_oil_client")
        self.m.run("SHL_refresh_furnaces")
        self.assertEqual(self.c["SHL_packet_price"], 40)
        for caller, callee in (("SHL_produce_site", "SHL_settle_furnace_order"),
                               ("SHL_produce_period", "SHL_settle_furnace_order"),
                               ("SHL_settle_furnace_order", "SHL_quote_furnace_order"),
                               ("SHL_preview_delivery", "SHL_quote_furnace_order")):
            self.assertIn((callee, "yes"), [(entry.key, entry.value) for entry in walk_entries(self.m.effects[caller])])
        quotes = [entry for entry in walk_entries(self.m.effects["SHL_quote_furnace_order"])
                  if entry.key in ("multiply_variable", "multiply_temp_variable")]
        self.assertTrue(any(scalar(quote.value, "var") == "SHL_order_price"
                            and scalar(quote.value, "value") == "SHL_auto_packet_price" for quote in quotes))
        decision = decision_definition("SHL_supply_furnace")
        self.assertEqual(scalar(decision, "custom_cost_text"), "SHL_cost_packet")
        self.assertIn("SHL_packet_price", repr(block(decision, "custom_cost_trigger")))
        self.assertIn("SHL_packet_price", repr(block(decision, "available")))
        # Bayrat ore takes 5 off every quote while Bayrat (291) is held.
        for marker, price in ((None, 35), ("NAM_oil_client", 30), ("NAM_fuel_embargo_modifier", 45)):
            with self.subTest(mines=marker):
                self.setUp()
                self.m.focuses.add("SHL_baryat_mines")
                self.price_marker(marker)
                self.m.run("SHL_refresh_furnaces")
                self.assertEqual(self.c["SHL_packet_price"], price)
        for lost in ("ownership", "control"):
            with self.subTest(lost=lost):
                self.setUp()
                self.m.focuses.add("SHL_baryat_mines")
                getattr(self.m, lost)["291"] = "KYZ"
                self.m.run("SHL_refresh_furnaces")
                self.assertEqual(self.c["SHL_packet_price"], 40)

    def test_packet_discounts_reach_floor_before_the_automatic_fee(self):
        self.m.focuses.update({"SHL_baryat_mines", "SHL_own_distillery", "SHL_fuel_ledger", "SHL_common_fund"})
        self.m.flags["SHL"].update({"NAM_oil_client", "SHL_smuggler_fuel", "SHL_nam_fuel_treaty"})
        self.m.run("SHL_refresh_oil_supply_quote")
        self.assertEqual((self.c["SHL_packet_price"], self.c["SHL_auto_packet_price"]), (20, 25))
        self.assertEqual((self.c["SHL_reserve_price"], self.c["SHL_reserve_price_premium"]), (70, 80))
        self.m.focuses.add("SHL_houses_railway")
        self.m.dynamic.add("NAM_fuel_embargo_modifier")
        self.m.run("SHL_refresh_oil_supply_quote")
        self.assertEqual((self.c["SHL_packet_price"], self.c["SHL_auto_packet_price"]), (35, 35))

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
        self.assertEqual(self.c["SHL_packet_price"], 40)
        self.c["ADISCORD_economy_treasury"] = 35
        self.m.run("SHL_begin_supply", target="287")
        self.assertEqual(self.c["SHL_packet_price"], 35)
        self.assertEqual(self.c["ADISCORD_economy_treasury"], 0)
        self.assertEqual(self.m.variables["287"]["SHL_operation_deposit"], 35)
        # The cycle adds the handling fee to the current manual quote.
        for marker, price in self.PRICES.items():
            with self.subTest(planned=marker):
                self.setUp()
                self.price_marker(marker)
                self.c["SHL_regular_supply"] = 1
                self.m.variables["287"]["SHL_furnace_stock"] = 0
                self.m.run("SHL_produce_period")
                self.assertEqual(self.c["SHL_packet_price"], price)
                self.assertEqual(self.c["ADISCORD_economy_treasury"], 1540 - price - 5)
                self.assertEqual(self.m.variables["287"]["SHL_furnace_stock"], 0)

    def test_metal_offers_require_a_peacetime_or_wartime_market_focus(self):
        decision = decision_definition("SHL_metal_contract_offer")
        self.m.focuses.clear()
        for buyer in self.BUYERS:
            self.assertFalse(self.m.matches(block(decision, "visible"), "SHL", buyer))
            self.m.execute(block(decision, "complete_effect"), "SHL", buyer)
            self.assertNotIn("SHL_metal_offer_pending", self.m.flags[buyer])
        self.assertNotIn("ADISCORD_SHL.130", self.m.scheduled)
        for focus in ("SHL_metal_brokers", "SHL_metal_market", "SHL_sw_keep_the_markets"):
            with self.subTest(focus=focus):
                self.m.focuses = {focus}
                self.assertTrue(self.m.matches(block(decision, "visible"), "SHL", "VAL"))
                reward = block(focus_definition(focus), "completion_reward")
                self.assertIn(("unlock_decision_tooltip", "SHL_metal_contract_offer"),
                              [(e.key, e.value) for e in walk_entries(reward)])
                self.m.execute(block(decision, "complete_effect"), "SHL", "VAL")
                self.assertIn("SHL_metal_offer_pending", self.m.flags["VAL"])
                self.m.flags["VAL"].remove("SHL_metal_offer_pending")

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
        self.assertFalse(self.m.matches(block(decision, "visible"), "SHL", "VAL"))
        self.assertFalse(self.m.matches(block(decision, "available"), "SHL", "VAL"))
        self.assertTrue(self.m.matches(block(decision, "target_trigger"), "SHL", "STP"))
        self.m.wars.add(frozenset(("STP", "SHL")))
        self.assertFalse(self.m.matches(block(decision, "target_trigger"), "SHL", "STP"))
        self.m.flags["RUS"].add("SHL_metal_client")
        self.assertFalse(self.m.matches(block(decision, "visible"), "SHL", "RUS"))
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

    def test_refusal_closes_repeat_offers_for_each_buyer(self):
        decision = decision_definition("SHL_metal_contract_offer")
        events = parse_clausewitz((ROOT / "events/ADISCORD_SHL_events.txt").read_text(encoding="utf-8"))
        offer = next(e.value for e in events if e.key == "country_event" and scalar(e.value, "id") == "ADISCORD_SHL.130")
        decline = next(e.value for e in offer if e.key == "option")
        self.assertEqual(scalar(decline, "name"), "ADISCORD_SHL.130.b")
        for tag in self.BUYERS:
            with self.subTest(buyer=tag):
                self.setUp()
                self.m.execute(block(decision, "complete_effect"), "SHL", tag)
                self.assertTrue(self.m.matches(block(offer, "trigger"), tag, "SHL"))
                # Re-entry while the first offer is pending cannot queue a second window.
                self.m.execute(block(decision, "complete_effect"), "SHL", tag)
                self.assertEqual(self.m.scheduled.count("ADISCORD_SHL.130"), 1)
                # The first option also handles an unattended event.
                self.m.execute(block(decline, "hidden_effect"), tag, "SHL")
                self.assertIn("SHL_metal_offer_declined", self.m.flags[tag])
                self.assertNotIn("SHL_metal_offer_pending", self.m.flags[tag])
                self.assertFalse(self.m.matches(block(offer, "trigger"), tag, "SHL"))
                for section in ("visible", "available"):
                    self.assertFalse(self.m.matches(block(decision, section), "SHL", tag))
                self.m.execute(block(decision, "complete_effect"), "SHL", tag)
                self.m.run("SHL_metal_decline_contract", scope=tag)
                self.assertEqual(self.m.scheduled, ["ADISCORD_SHL.130", "ADISCORD_SHL.132"])
                self.assertEqual(self.c["SHL_metal_clients"], 0)
                self.assertEqual(self.m.variables[tag]["ADISCORD_economy_treasury"], 500)
                other = next(buyer for buyer in self.BUYERS if buyer != tag)
                self.assertTrue(self.m.matches(block(decision, "visible"), "SHL", other))
                self.assertTrue(self.m.matches(block(decision, "available"), "SHL", other))
                # A stale pending offer cannot bypass the recorded refusal at settlement.
                self.m.flags[tag].add("SHL_metal_offer_pending")
                self.assertFalse(self.m.matches(block(offer, "trigger"), tag, "SHL"))
                self.m.run("SHL_metal_sign_contract", scope=tag)
                self.assertNotIn("SHL_metal_client", self.m.flags[tag])
                self.assertEqual(self.c["SHL_metal_clients"], 0)

    def test_completed_contract_remains_eligible_for_renewal(self):
        decision = decision_definition("SHL_metal_contract_offer")
        for effect in ("SHL_metal_sign_contract", "SHL_metal_sign_contract_two_years"):
            with self.subTest(term=effect):
                self.setUp()
                self.m.execute(block(decision, "complete_effect"), "SHL", "NAM")
                self.m.run(effect, scope="NAM")
                self.assertIn("SHL_metal_client", self.m.flags["NAM"])
                # Closing an obsolete refusal option cannot revoke an accepted contract.
                self.m.run("SHL_metal_decline_contract", scope="NAM")
                self.assertNotIn("SHL_metal_offer_declined", self.m.flags["NAM"])
                self.assertIn("SHL_metal_client", self.m.flags["NAM"])
                self.m.run("SHL_metal_drop_client", scope="NAM")
                self.assertTrue(self.m.matches(block(decision, "visible"), "SHL", "NAM"))
                self.assertTrue(self.m.matches(block(decision, "available"), "SHL", "NAM"))
                self.m.execute(block(decision, "complete_effect"), "SHL", "NAM")
                self.assertEqual(self.m.scheduled.count("ADISCORD_SHL.130"), 2)

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

    def test_cycle_settlement_moves_annual_payment_each_way_and_marks_both_economies_dirty(self):
        settle = self.effects["SHL_metal_settle_clients"]
        self.assertEqual([e.key for e in settle], list(self.BUYERS))
        self.assertNotIn("every_country", repr(settle))
        self.sign("VAL")
        before = self.dirty_calls()
        self.m.run("SHL_produce_period")
        self.assertEqual(self.m.variables["VAL"]["ADISCORD_economy_treasury"], 480)
        self.assertEqual(self.m.variables["VAL"]["ADISCORD_economy_current_month_action_costs"], 20)
        self.assertEqual(self.c["ADISCORD_economy_treasury"], 1560)
        # The ledger books the whole cycle, contract payment included.
        self.assertEqual(self.c["ADISCORD_economy_current_month_action_income"], 560)
        self.assertEqual(self.c["SHL_last_cycle_income"], 560)
        self.assertEqual(self.dirty_calls() - before, 2)
        self.assertIn("SHL_metal_client", self.m.flags["VAL"])
        self.assertEqual(self.m.variables["VAL"]["SHL_metal_arrears"], 0)
        # A buyer without a contract is never touched.
        self.assertEqual(self.m.variables["STP"]["ADISCORD_economy_treasury"], 500)

    def test_each_buyer_pays_its_own_contract_rate(self):
        self.sign("VAL")
        self.m.flags["STP"].add("SHL_metal_offer_pending")
        self.m.run("SHL_metal_sign_contract_two_years", scope="STP")
        self.m.focuses.add("SHL_metal_brokers")
        buyer = self.m.variables["STP"]
        buyer["ADISCORD_economy_treasury"] = 14.99
        self.m.run("SHL_metal_settle_clients")
        self.assertEqual(buyer["SHL_metal_arrears"], 1)
        self.assertEqual(buyer["ADISCORD_economy_treasury"], 14.99)
        self.assertEqual(self.c["ADISCORD_economy_current_month_action_income"], 35)

        buyer["ADISCORD_economy_treasury"] = 15
        self.m.run("SHL_metal_settle_clients")
        self.assertEqual(buyer["SHL_metal_arrears"], 0)
        self.assertEqual(buyer["ADISCORD_economy_treasury"], 0)
        self.assertEqual(buyer["ADISCORD_economy_current_month_action_costs"], 15)
        self.assertEqual(self.m.variables["VAL"]["ADISCORD_economy_current_month_action_costs"], 40)
        self.assertEqual(self.c["ADISCORD_economy_treasury"], 1100)
        self.assertEqual(self.c["ADISCORD_economy_current_month_action_income"], 100)
        self.assertEqual(self.c["SHL_last_cycle_income"], 100)

    def test_brokers_premium_only_on_paid_cycles(self):
        # The buyer pays 20 either way and the brokers add 15 from their own margin.
        for brokers, treasury, received in ((False, 500, 20), (True, 500, 35), (True, 19.99, 0)):
            with self.subTest(brokers=brokers, treasury=treasury):
                self.setUp()
                if brokers:
                    self.m.focuses.add("SHL_metal_brokers")
                self.sign("VAL")
                self.m.variables["VAL"]["ADISCORD_economy_treasury"] = treasury
                self.m.run("SHL_produce_period")
                paid = 20 if received else 0
                self.assertAlmostEqual(self.m.variables["VAL"]["ADISCORD_economy_treasury"], treasury - paid)
                self.assertEqual(self.c["ADISCORD_economy_treasury"], 1540 + received)
                self.assertEqual(self.c["ADISCORD_economy_current_month_action_income"], 540 + received)
                self.assertEqual(self.c["SHL_last_cycle_income"], 540 + received)
        reward = block(focus_definition("SHL_metal_brokers"), "completion_reward")
        before = self.c["SHL_metal_max_clients"]
        self.m.execute([e for e in reward if e.key == "hidden_effect"], "SHL")
        self.assertEqual(self.c["SHL_metal_max_clients"], before + 1)
        self.assertEqual(self.c["ADISCORD_economy_treasury"], 1540 + 100)

    def test_two_unpaid_cycles_or_a_war_end_the_contract_and_remove_the_modifier(self):
        self.sign("VAL")
        self.m.variables["VAL"]["ADISCORD_economy_treasury"] = 19.99
        self.m.run("SHL_produce_period")
        self.assertEqual(self.m.variables["VAL"]["SHL_metal_arrears"], 1)
        self.assertIn("SHL_metal_client", self.m.flags["VAL"])
        self.assertEqual(self.m.variables["VAL"]["ADISCORD_economy_treasury"], 19.99)
        self.assertEqual(self.c["ADISCORD_economy_treasury"], 1540)
        # One paid cycle clears the arrears again.
        self.m.variables["VAL"]["ADISCORD_economy_treasury"] = 20
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
        self.assertFalse(self.m.matches(block(decision, "visible"), "SHL", "VAL"))
        self.m.execute(block(decision, "complete_effect"), "SHL", "RUS")
        self.m.execute(block(decision, "complete_effect"), "SHL", "RUS")
        self.assertNotIn("SHL_metal_client", self.m.flags["RUS"])
        self.assertNotIn("SHL_metal_supply", self.m.dynamic)
        self.assertEqual(self.c["SHL_metal_clients"], 0)
        self.assertNotIn("ADISCORD_SHL.133", self.m.scheduled)
        modifier = shared_definitions("common/dynamic_modifiers/ADISCORD_dynamic_modifiers_SHL.txt", ("SHL_metal_supply",))["SHL_metal_supply"]
        self.assertEqual(scalar(modifier, "production_factory_efficiency_gain_factor"), "SHL_metal_efficiency_growth")
        self.assertEqual(scalar(modifier, "production_factory_max_efficiency_factor"), "SHL_metal_efficiency_cap")
        self.assertEqual(scalar(modifier, "production_lack_of_resource_penalty_factor"), "SHL_metal_resource_penalty")
        self.assertIn("SHL_metal_client", repr(block(modifier, "enable")))
        self.assertIn("country_exists", repr(block(modifier, "remove_trigger")))

    def test_metal_terms_expire_without_further_payments_or_duplicate_slots(self):
        for suffix, duration in (("year", "365"), ("two_years", "730")):
            with self.subTest(term=suffix):
                self.setUp()
                self.m.flags["VAL"].add("SHL_metal_offer_pending")
                effect = "SHL_metal_sign_contract_two_years" if suffix == "two_years" else "SHL_metal_sign_contract"
                self.m.run(effect, scope="VAL")
                mission_id = "SHL_metal_contract_" + suffix
                self.assertIn(mission_id, self.m.missions)
                self.assertEqual(self.c["SHL_metal_clients"], 1)
                mission = decision_definition(mission_id)
                self.assertEqual(self.m.variables["VAL"]["SHL_metal_efficiency_growth"], 0.15)
                self.assertEqual(self.m.variables["VAL"]["SHL_metal_efficiency_cap"], 0.05)
                self.assertEqual(self.m.variables["VAL"]["SHL_metal_resource_penalty"], -0.10)
                ideas = parse_clausewitz((ROOT / "common/ideas/ADISCORD_southern_desert_ideas.txt").read_text(encoding="utf-8"))
                preview = block(block(block(ideas, "ideas"), "country"), "SHL_metal_supply_preview")
                modifiers = block(preview, "modifier")
                self.assertEqual(float(scalar(modifiers, "production_factory_efficiency_gain_factor")), self.m.variables["VAL"]["SHL_metal_efficiency_growth"])
                self.assertEqual(float(scalar(modifiers, "production_factory_max_efficiency_factor")), self.m.variables["VAL"]["SHL_metal_efficiency_cap"])
                self.assertEqual(float(scalar(modifiers, "production_lack_of_resource_penalty_factor")), self.m.variables["VAL"]["SHL_metal_resource_penalty"])
                self.assertEqual(scalar(mission, "days_mission_timeout"), duration)
                self.assertIn("always", repr(block(mission, "available")))
                self.assertIn("no", repr(block(mission, "available")))
                self.m.run(effect, scope="VAL")
                self.assertEqual(self.c["SHL_metal_clients"], 1)
                self.m.execute(block(mission, "timeout_effect"), "VAL")
                self.assertNotIn("SHL_metal_client", self.m.flags["VAL"])
                self.assertNotIn("SHL_metal_cycle_price", self.m.variables["VAL"])
                self.assertNotIn("SHL_metal_supply", self.m.dynamic)
                self.assertNotIn(mission_id, self.m.missions)
                self.assertEqual(self.c["SHL_metal_clients"], 0)
                treasury = self.m.variables["VAL"]["ADISCORD_economy_treasury"]
                self.m.run("SHL_metal_settle_client", scope="VAL")
                self.assertEqual(self.m.variables["VAL"]["ADISCORD_economy_treasury"], treasury)

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


class ConclaveLeversTests(unittest.TestCase):
    """Conclave levers: exact prices, single debits, the measure lockout, charters and war orders."""

    # Localisation fragments of the stage-4 script author until the lead merges them into the hubs.
    LOC_FRAGMENTS = Path(
        r"C:\Users\Admin\AppData\Local\Temp\claude\C--Users-Admin-Documents-Paradox-Interactive-Hearts-of-Iron-IV-mod-A-Discord"
        r"\59918be6-08c2-4e8e-a861-910d8d665f4f\scratchpad\loc"
    )
    STATES = tuple(str(state) for state in range(287, 296))
    MEASURES = {
        # id: (visible focus, native PP cost or None, treasury price, finish effect)
        "SHL_measure_crest_patronage": ("SHL_h_council_of_ten", None, 50, "SHL_finish_crest_patronage"),
        "SHL_measure_golden_fair": ("SHL_h_cartel_price", 25, 0, "SHL_finish_golden_fair"),
        "SHL_measure_quarter_assembly": ("SHL_c_council_delegates", 25, 0, "SHL_finish_quarter_assembly"),
        "SHL_measure_open_books": ("SHL_c_compact_assembly", None, 40, "SHL_finish_open_books"),
        "SHL_measure_directorate_decree": ("SHL_d_nur_director", 30, 0, "SHL_finish_directorate_decree"),
        "SHL_measure_war_bonds": ("SHL_d_iron_crown", 0, 0, "SHL_finish_war_bonds"),
        "SHL_measure_crest_court": ("SHL_r_tolls", 20, 0, "SHL_finish_crest_court"),
        "SHL_measure_fief_grant": ("SHL_r_hereditary_seats_restored", None, 60, "SHL_finish_fief_grant"),
        "SHL_measure_common_assembly": ("SHL_k_delegates", 20, 0, "SHL_finish_common_assembly"),
        "SHL_measure_shift_reserve": ("SHL_k_no_more_crests", None, 30, "SHL_finish_shift_reserve"),
    }

    class Machine(ScriptMachine):
        """Records opinion changes, which the shared machine does not model."""

        def execute(self, items, scope, target=None):
            remaining = []
            for entry in items:
                if entry.key == "add_opinion_modifier":
                    self.calls.append(("add_opinion_modifier", scope, scalar(entry.value, "target"), scalar(entry.value, "modifier")))
                else:
                    remaining.append(entry)
            super().execute(remaining, scope, target)

    def setUp(self):
        effects = parse_clausewitz(EFFECT_PATH.read_text(encoding="utf-8"))
        triggers = parse_clausewitz(TRIGGER_PATH.read_text(encoding="utf-8"))
        self.m = self.Machine(effects, triggers)
        self.c = self.m.variables["SHL"]
        self.m.run("SHL_refresh_packet_price")
        self.c["SHL_shift_policy"] = 0.0
        self.c["SHL_political_course"] = 0.0
        self.c["SHL_unrest"] = 30.0
        self.c["SHL_city_support"] = 20.0
        self.c["SHL_reserve_stock"] = 2.0
        for state in self.STATES:
            self.m.variables[state].update({
                "SHL_furnace_stock": 2.0,
                "SHL_furnace_wear": 20.0,
                "SHL_furnace_owner": 0.0,
                "SHL_furnace_running": 1.0,
                "SHL_furnace_training": 0.0,
                "SHL_furnace_shortages": 0.0,
                "SHL_furnace_recipient": 0.0,
            })
        self.m.flags["SHL"].add("SHL_furnaces_initialized")
        self.m.power_balance[BALANCE] = 0.0
        seat_houses(self.m, 70)

    def available(self, identifier, target=None):
        return self.m.matches(block(decision_definition(identifier), "available"), "SHL", target)

    def run_block(self, identifier, name, target=None):
        self.m.target_scope = target
        self.m.execute(block(decision_definition(identifier), name), "SHL", target)

    def test_country_operable_hides_the_initialisation_flag(self):
        text = TRIGGER_PATH.read_text(encoding="utf-8")
        for name in ("SHL_country_operable", "SHL_furnace_site_controlled"):
            body = re.search(r"^" + name + r" = \{\n(.*?)\n\}", text, re.M | re.S).group(1)
            self.assertIn("hidden_trigger = { has_country_flag = SHL_furnaces_initialized }", body, name)
            self.assertNotRegex(body, r"^\s*has_country_flag = SHL_furnaces_initialized", name)
        self.assertTrue(self.m.matches(self.m.triggers["SHL_country_operable"], "SHL"))

    def test_native_prices_and_cooldowns_are_declared_once(self):
        expected = {
            "SHL_convene_conclave": ("40", "120"),
            "SHL_arbitration_act": ("15", "90"),
            "SHL_house_audit": ("30", "1"),
            "SHL_war_orders_all": ("40", "28"),
        }
        for identifier, (cost, cooldown) in expected.items():
            decision = decision_definition(identifier)
            self.assertEqual(scalar(decision, "cost"), cost, identifier)
            self.assertEqual(scalar(decision, "days_re_enable"), cooldown, identifier)
            self.assertIsNone(scalar(decision, "custom_cost_text"), identifier)
        for identifier in ("SHL_quarter_charter", "SHL_desert_embassy", "SHL_integrate_satellite_decision"):
            decision = decision_definition(identifier)
            self.assertEqual(scalar(decision, "cost"), "0", identifier)
            self.assertIsNotNone(scalar(decision, "custom_cost_text"), identifier)
            self.assertTrue(block(decision, "custom_cost_trigger"), identifier)
        for identifier, (_, pp_cost, treasury_price, _) in self.MEASURES.items():
            decision = decision_definition(identifier)
            self.assertEqual(scalar(decision, "days_re_enable"), "60", identifier)
            self.assertEqual(scalar(decision, "days_remove"), "60", identifier)
            self.assertTrue(block(decision, "modifier"), identifier)
            if treasury_price:
                self.assertEqual(scalar(decision, "cost"), "0", identifier)
                self.assertIsNotNone(scalar(decision, "custom_cost_text"), identifier)
            else:
                self.assertEqual(scalar(decision, "cost"), str(pp_cost), identifier)

    def test_convene_feeds_only_house_run_furnaces_and_caps_the_bunker(self):
        m = self.m
        m.variables["288"]["SHL_furnace_owner"] = 1
        m.variables["289"]["SHL_furnace_running"] = 0
        m.variables["290"]["SHL_furnace_stock"] = 3
        m.control["291"] = "KYZ"
        self.c["SHL_house_votes"] = 1
        self.assertTrue(self.available("SHL_convene_conclave"))
        self.run_block("SHL_convene_conclave", "complete_effect")
        self.assertEqual(m.values["political_power"], 200, "the native cost is the only debit")
        self.assertEqual(m.variables["287"]["SHL_furnace_stock"], 3)
        self.assertEqual(m.variables["288"]["SHL_furnace_stock"], 2)
        self.assertEqual(m.variables["289"]["SHL_furnace_stock"], 2)
        self.assertEqual(m.variables["290"]["SHL_furnace_stock"], 3)
        self.assertEqual(m.variables["291"]["SHL_furnace_stock"], 2)
        self.assertEqual(m.variables["295"]["SHL_furnace_stock"], 3)
        self.assertEqual(self.c["SHL_house_pressure"], 25)
        m.flags["SHL"].add("SHL_political_action")
        self.assertFalse(self.available("SHL_convene_conclave"))
        self.assertFalse(self.available("SHL_arbitration_act"))

    def test_arbitration_lowers_unrest_without_a_second_debit(self):
        self.assertTrue(self.available("SHL_arbitration_act"))
        self.run_block("SHL_arbitration_act", "complete_effect")
        self.assertEqual(self.c["SHL_unrest"], 24)
        self.assertEqual(self.m.values["political_power"], 200)

    def test_charter_is_paid_once_at_the_exact_boundary_and_counted_at_most_three_times(self):
        m = self.m
        self.c["ADISCORD_economy_treasury"] = 59.99
        self.assertFalse(self.available("SHL_quarter_charter", "287"))
        m.run("SHL_begin_charter", target="287")
        self.assertEqual(self.c["ADISCORD_economy_treasury"], 59.99)
        self.c["ADISCORD_economy_treasury"] = 1000
        for state in ("287", "288", "289"):
            self.assertTrue(self.available("SHL_quarter_charter", state))
            m.run("SHL_begin_charter", target=state)
            m.run("SHL_begin_charter", target=state)
            m.run("SHL_finish_charter", target=state)
            m.run("SHL_finish_charter", target=state)
            self.assertIn("SHL_quarter_charter", m.flags[state])
            self.assertNotIn("SHL_operation", m.variables[state])
        self.assertEqual(self.c["ADISCORD_economy_treasury"], 820)
        self.assertEqual(self.c["SHL_charters_active"], 3)
        self.assertFalse(self.available("SHL_quarter_charter", "290"))
        # A fourth charter paid before the third completed is refunded, never granted.
        m.run("SHL_begin_charter", target="290")
        self.assertEqual(self.c["ADISCORD_economy_treasury"], 820)
        m.variables["290"].update({"SHL_operation": 9.0, "SHL_operation_deposit": 60.0, "SHL_operation_pp": 0.0})
        self.c["ADISCORD_economy_treasury"] = 760
        m.run("SHL_finish_charter", target="290")
        self.assertNotIn("SHL_quarter_charter", m.flags["290"])
        self.assertEqual(self.c["ADISCORD_economy_treasury"], 820)
        self.assertEqual(self.c["SHL_charters_active"], 3)
        # Loss of the district and a state takeover both drop the charter.
        m.ownership["287"] = "KYZ"
        m.control["287"] = "KYZ"
        m.variables["288"]["SHL_furnace_owner"] = 2
        m.run("SHL_refresh_furnaces")
        self.assertEqual(self.c["SHL_charters_active"], 1)
        self.assertNotIn("SHL_quarter_charter", m.flags["287"])
        self.assertNotIn("SHL_quarter_charter", m.flags["288"])
        self.assertIn("SHL_quarter_charter", m.flags["289"])
        self.assertTrue(self.available("SHL_quarter_charter", "290"))

    def test_charter_rule_counts_only_lit_chartered_furnaces(self):
        m = self.m
        m.flags["287"].add("SHL_quarter_charter")
        m.flags["288"].add("SHL_quarter_charter")
        m.flags["289"].add("SHL_quarter_charter")
        m.variables["288"]["SHL_furnace_running"] = 0
        m.control["289"] = "AZH"
        baseline = deepcopy(m)
        for flagged in ("287", "288", "289"):
            baseline.flags[flagged].discard("SHL_quarter_charter")
        for machine in (m, baseline):
            machine.run("SHL_refresh_furnaces")
            machine.run("SHL_update_tensions")
        self.assertEqual(self.c["SHL_charters_active"], 3)
        self.assertEqual(self.c["SHL_charters_running"], 1)
        self.assertEqual(self.c["SHL_city_support"] - baseline.variables["SHL"]["SHL_city_support"], 1)
        self.assertEqual(baseline.variables["SHL"]["SHL_unrest"] - self.c["SHL_unrest"], 1)

    def test_dispatch_moves_exactly_one_packet_from_the_donor_to_the_lowest_stock(self):
        m = self.m
        m.variables["287"]["SHL_furnace_stock"] = 3
        m.variables["288"]["SHL_furnace_stock"] = 1
        m.variables["289"]["SHL_furnace_stock"] = 0
        m.variables["289"]["SHL_furnace_running"] = 0
        m.variables["290"]["SHL_furnace_stock"] = 1.5
        self.assertFalse(self.available("SHL_dispatch_order", "290"))
        self.assertTrue(self.available("SHL_dispatch_order", "287"))
        total = sum(m.variables[state]["SHL_furnace_stock"] for state in self.STATES)
        m.run("SHL_begin_dispatch", target="287")
        m.run("SHL_begin_dispatch", target="287")
        self.assertEqual(m.variables["287"]["SHL_furnace_stock"], 2)
        self.assertFalse(self.available("SHL_dispatch_order", "287"), "the donor is busy while the packet travels")
        m.run("SHL_finish_dispatch", target="287")
        m.run("SHL_finish_dispatch", target="287")
        self.assertEqual(m.variables["288"]["SHL_furnace_stock"], 2, "the lit furnace with the smallest stock receives it")
        self.assertEqual(m.variables["289"]["SHL_furnace_stock"], 0, "a cold furnace is never the recipient")
        self.assertEqual(sum(m.variables[state]["SHL_furnace_stock"] for state in self.STATES), total)
        self.assertNotIn("SHL_operation", m.variables["287"])
        self.assertNotIn("SHL_pick_site", self.c)

    def test_audit_reduces_wear_resets_shortages_and_refunds_on_loss(self):
        m = self.m
        m.variables["287"].update({"SHL_furnace_wear": 50.0, "SHL_furnace_shortages": 1.0})
        self.assertTrue(self.available("SHL_house_audit", "287"))
        m.run("SHL_begin_audit", target="287")
        self.assertFalse(self.available("SHL_house_audit", "287"))
        m.run("SHL_finish_audit", target="287")
        m.run("SHL_finish_audit", target="287")
        self.assertEqual(m.variables["287"]["SHL_furnace_wear"], 40)
        self.assertEqual(m.variables["287"]["SHL_furnace_shortages"], 0)
        # The audited house alone pays 15.
        self.assertEqual(m.variables["287"]["SHL_house_loyalty"], 55)
        self.assertAlmostEqual(self.c["SHL_house_pressure"], 30 + 15 / 9)
        self.assertEqual(m.values["political_power"], 200, "the native 30 PP is the only price")
        m.run("SHL_begin_audit", target="288")
        m.control["288"] = "AZH"
        self.assertTrue(m.matches(block(decision_definition("SHL_house_audit"), "cancel_trigger"), "SHL", "288"))
        m.run("SHL_cancel_operation", target="288")
        self.assertEqual(m.values["political_power"], 230, "the escrow returns the native price once")
        self.assertEqual(m.variables["288"]["SHL_furnace_wear"], 20)

    def test_embassy_is_paid_once_opens_once_and_feeds_the_southern_offer(self):
        m = self.m
        self.c["ADISCORD_economy_treasury"] = 49.99
        self.assertFalse(self.available("SHL_desert_embassy", "KDR"))
        self.c["ADISCORD_economy_treasury"] = 50
        self.assertTrue(self.available("SHL_desert_embassy", "KDR"))
        m.run("SHL_begin_embassy", target="KDR")
        m.run("SHL_begin_embassy", target="KDR")
        self.assertEqual(self.c["ADISCORD_economy_treasury"], 0)
        self.assertFalse(self.m.matches(block(decision_definition("SHL_desert_embassy"), "target_trigger"), "SHL", "KDR"))
        self.assertFalse(self.available("SHL_desert_embassy", "RHM"), "one mission travels at a time")
        m.run("SHL_finish_embassy", target="KDR")
        m.run("SHL_finish_embassy", target="KDR")
        self.assertIn("SHL_embassy", m.flags["KDR"])
        self.assertNotIn("SHL_embassy_pending", m.flags["KDR"])
        self.assertEqual(m.calls.count(("add_opinion_modifier", "KDR", "SHL", "ADISCORD_SHL_embassy")), 1)
        self.assertNotIn("SHL_embassy_deposit", self.c)
        self.assertFalse(self.m.matches(block(decision_definition("SHL_desert_embassy"), "target_trigger"), "SHL", "KDR"))
        # A war before arrival returns the deposit.
        self.c["ADISCORD_economy_treasury"] = 50
        m.run("SHL_begin_embassy", target="RHM")
        m.wars.add(frozenset(("SHL", "RHM")))
        self.assertTrue(m.matches(block(decision_definition("SHL_desert_embassy"), "cancel_trigger"), "SHL", "RHM"))
        m.run("SHL_cancel_embassy", target="RHM")
        self.assertEqual(self.c["ADISCORD_economy_treasury"], 50)
        self.assertNotIn("SHL_embassy_pending", m.flags["RHM"])
        events = (ROOT / "events/ADISCORD_south_final_war_events.txt").read_text(encoding="utf-8")
        option = re.search(r"name = ADISCORD_south\.40\.a\n(.*?)\n\s*option = \{", events, re.S).group(1)
        self.assertRegex(option, r"add = 15\s+has_country_flag = SHL_embassy\s+FROM = \{ tag = SHL \}")
        modifiers = shared_definitions("common/opinion_modifiers/ADISCORD_SHL_opinion_modifiers.txt", ("opinion_modifiers",))["opinion_modifiers"]
        self.assertEqual(scalar(block(modifiers, "ADISCORD_SHL_embassy"), "value"), "20")

    def test_reserve_price_adds_supplier_premium_after_discounts(self):
        m = self.m
        for focus, price in ((None, 90), ("SHL_common_fund", 75)):
            if focus:
                m.focuses.add(focus)
            for premium in (False, True):
                m.flags["SHL"].discard("SHL_supplier_premium")
                if premium:
                    m.flags["SHL"].add("SHL_supplier_premium")
                quote = price + (10 if premium else 0)
                self.c["SHL_reserve_stock"] = 2
                self.c["ADISCORD_economy_treasury"] = quote - 0.01
                m.run("SHL_purchase_reserve")
                self.assertEqual(self.c["SHL_reserve_stock"], 2, (focus, premium))
                self.assertEqual(self.c["SHL_reserve_price"], price)
                self.assertEqual(self.c["SHL_reserve_price_premium"], price + 10)
                self.c["ADISCORD_economy_treasury"] = quote
                m.run("SHL_purchase_reserve")
                self.assertEqual(self.c["ADISCORD_economy_treasury"], 0, (focus, premium))
                self.assertEqual(self.c["SHL_reserve_stock"], 4, (focus, premium))
                self.assertNotIn("SHL_supplier_premium", m.flags["SHL"])
        self.assertEqual(scalar(decision_definition("SHL_buy_reserve"), "custom_cost_text"), "SHL_cost_reserve")

    def test_war_orders_flag_every_open_lit_furnace_for_exactly_one_cycle(self):
        m = self.m
        m.variables["288"]["SHL_furnace_running"] = 0
        m.variables["289"]["SHL_furnace_recipient"] = 2
        m.run("SHL_begin_quota", target="290")
        self.assertTrue(self.available("SHL_war_orders_all"))
        self.run_block("SHL_war_orders_all", "complete_effect")
        self.assertEqual(m.values["political_power"], 200)
        flagged = [state for state in self.STATES if "SHL_quota_site" in m.flags[state]]
        self.assertEqual(flagged, [state for state in self.STATES if state != "288"])
        self.assertEqual(m.variables["289"]["SHL_furnace_recipient"], 1)
        self.assertEqual(m.variables["289"]["SHL_war_orders_prev_recipient"], 2)
        self.assertNotIn("SHL_war_orders_prev_recipient", m.variables["290"], "a running quota keeps its own lifecycle")
        self.assertFalse(self.available("SHL_war_orders_all"), "no open furnace remains this cycle")
        unrest = self.c["SHL_unrest"]
        m.run("SHL_produce_period")
        self.assertEqual(self.c["SHL_unrest"], unrest, "war orders add no quota unrest")
        self.assertEqual([state for state in self.STATES if "SHL_quota_site" in m.flags[state]], ["290"])
        self.assertEqual(m.variables["289"]["SHL_furnace_recipient"], 2)
        self.assertEqual(m.variables["287"]["SHL_furnace_recipient"], 0)
        self.assertNotIn("SHL_war_orders_prev_recipient", m.variables["289"])
        m.run("SHL_finish_quota", target="290")
        self.assertNotIn("SHL_quota_site", m.flags["290"])

    def test_integration_prices_follow_the_course_and_refund_when_the_satellite_leaves(self):
        m = self.m
        m.countries["KDR"]["subject_of"] = "SHL"
        m.countries["KDR"]["is_subject"] = True
        self.assertTrue(m.matches(block(decision_definition("SHL_integrate_satellite_decision"), "target_trigger"), "SHL", "KDR"))
        prices = {1: (300, 0), 2: (0, 0), 3: (0, 100), 4: (200, 0), 5: (0, 50)}
        for course, (treasury, power) in prices.items():
            with self.subTest(course=course):
                self.c["SHL_political_course"] = course
                self.c["ADISCORD_economy_treasury"] = max(treasury - 0.01, 0)
                m.values["political_power"] = power - 1
                if treasury or power:
                    self.assertFalse(self.available("SHL_integrate_satellite_decision", "KDR"))
                self.c["ADISCORD_economy_treasury"] = treasury
                m.values["political_power"] = power
                self.assertTrue(self.available("SHL_integrate_satellite_decision", "KDR"))
                m.run("SHL_begin_integration", target="KDR")
                m.run("SHL_begin_integration", target="KDR")
                self.assertEqual(self.c["ADISCORD_economy_treasury"], 0)
                self.assertEqual(m.values["political_power"], 0)
                self.assertIn("SHL_integration_pending", m.flags["KDR"])
                self.assertFalse(self.available("SHL_integrate_satellite_decision", "RHM"), "one accession at a time")
                m.run("SHL_cancel_integration", target="KDR")
                self.assertEqual(self.c["ADISCORD_economy_treasury"], treasury)
                self.assertEqual(m.values["political_power"], power)
                self.assertNotIn("SHL_integration_pending", m.flags["KDR"])
        self.c["SHL_political_course"] = 2
        m.run("SHL_begin_integration", target="KDR")
        m.countries["KDR"]["subject_of"] = None
        self.assertTrue(m.matches(block(decision_definition("SHL_integrate_satellite_decision"), "cancel_trigger"), "SHL", "KDR"))
        m.run("SHL_finish_integration_decision", target="KDR")
        self.assertTrue(m.countries["KDR"]["exists"], "a satellite that left is not annexed")
        self.assertNotIn("SHL_integration_deposit", self.c)
        m.countries["KDR"]["subject_of"] = "SHL"
        self.c["SHL_political_course"] = 1
        self.c["ADISCORD_economy_treasury"] = 300
        m.run("SHL_begin_integration", target="KDR")
        m.run("SHL_finish_integration_decision", target="KDR")
        self.assertEqual(m.calls.count(("annex_country", "SHL", "KDR")), 1)
        self.assertEqual(self.c["ADISCORD_economy_treasury"], 0, "the course price is the only debit")
        self.assertNotIn("SHL_integration_deposit", self.c)
        self.assertNotIn("SHL_integration_price", self.c)

    def test_one_measure_at_a_time_and_results_only_in_remove_effect(self):
        m = self.m
        for identifier, (focus, _, _, finish) in self.MEASURES.items():
            m.focuses.add(focus)
            decision = decision_definition(identifier)
            self.assertNotIn(finish, repr(block(decision, "complete_effect")), identifier)
            self.assertIn(finish, repr(block(decision, "remove_effect")), identifier)
            self.assertIn("SHL_end_measure", repr(block(decision, "cancel_effect")), identifier)
        self.c["ADISCORD_economy_treasury"] = 1000
        self.assertTrue(self.available("SHL_measure_golden_fair"))
        self.run_block("SHL_measure_golden_fair", "complete_effect")
        self.assertIn("SHL_political_action", m.flags["SHL"])
        for identifier in self.MEASURES:
            self.assertFalse(self.available(identifier), identifier)
        self.assertFalse(self.available("SHL_convene_conclave"))
        self.assertTrue(self.available("SHL_war_orders_all"), "war orders stay outside the lockout")
        self.run_block("SHL_measure_golden_fair", "cancel_effect")
        self.assertNotIn("SHL_political_action", m.flags["SHL"])
        self.assertTrue(self.available("SHL_measure_crest_patronage"))
        # Treasury measures debit exactly once at the start and nothing at the end.
        before = dict(self.c)
        self.run_block("SHL_measure_crest_patronage", "complete_effect")
        self.assertEqual(self.c["ADISCORD_economy_treasury"], 950)
        self.assertEqual(self.c["SHL_house_pressure"], before["SHL_house_pressure"])
        self.assertEqual(m.power_balance[BALANCE], 0.0)
        self.run_block("SHL_measure_crest_patronage", "remove_effect")
        self.assertEqual(self.c["ADISCORD_economy_treasury"], 950)
        self.assertEqual(self.c["SHL_house_pressure"], before["SHL_house_pressure"] - 5)
        self.assertEqual(m.power_balance[BALANCE], -0.05)
        self.assertNotIn("SHL_political_action", m.flags["SHL"])

    def test_measure_results_match_the_contract(self):
        m = self.m
        self.c["ADISCORD_economy_treasury"] = 1000
        m.variables["288"]["SHL_furnace_recipient"] = 1
        m.variables["289"]["SHL_furnace_running"] = 0
        m.run("SHL_finish_golden_fair")
        self.assertEqual(self.c["ADISCORD_economy_treasury"], 1000 + 30 * 7)
        m.run("SHL_finish_war_bonds")
        self.assertEqual(self.c["ADISCORD_economy_treasury"], 1210 + 200)
        self.assertEqual(self.c["ADISCORD_economy_debt"], 300)
        m.run("SHL_finish_shift_reserve")
        self.assertEqual(self.c["SHL_reserve_stock"], 4)
        m.run("SHL_finish_quarter_assembly")
        self.assertEqual(m.power_balance[BALANCE], 0.05)
        self.assertEqual(self.c["SHL_city_support"], 23)
        m.run("SHL_finish_open_books")
        self.assertEqual(self.c["SHL_unrest"], 25)
        self.assertEqual(m.values["stability"], 0.01)
        m.run("SHL_finish_crest_court")
        self.assertEqual(m.power_balance[BALANCE], 0.0)
        self.assertEqual(self.c["SHL_unrest"], 29)
        m.run("SHL_finish_fief_grant")
        self.assertEqual(m.power_balance[BALANCE], -0.03)
        self.assertEqual(self.c["SHL_house_pressure"], 20)
        m.run("SHL_finish_common_assembly")
        self.assertEqual(m.power_balance[BALANCE], 0.02)
        self.assertEqual(self.c["SHL_unrest"], 25)
        # The decree feeds the state furnace with the smallest stock only.
        m.variables["290"].update({"SHL_furnace_owner": 2.0, "SHL_furnace_stock": 2.0})
        m.variables["291"].update({"SHL_furnace_owner": 2.0, "SHL_furnace_stock": 1.0})
        m.variables["292"]["SHL_furnace_stock"] = 0
        m.run("SHL_finish_directorate_decree")
        self.assertEqual(m.variables["291"]["SHL_furnace_stock"], 2)
        self.assertEqual(m.variables["290"]["SHL_furnace_stock"], 2)
        self.assertEqual(m.variables["292"]["SHL_furnace_stock"], 0)
        self.assertEqual(self.c["SHL_house_pressure"], 15)
        self.assertEqual(self.c["SHL_unrest"], 28)
        self.assertNotIn("SHL_pick_site", self.c)

    def test_tree_helpers_repair_stock_and_deliver_the_first_batch(self):
        m = self.m
        m.variables["289"]["SHL_furnace_wear"] = 70
        m.variables["290"]["SHL_furnace_wear"] = 95
        m.variables["290"]["SHL_furnace_running"] = 0
        m.run("SHL_repair_worst_site")
        self.assertEqual(m.variables["289"]["SHL_furnace_wear"], 40)
        self.assertEqual(m.variables["290"]["SHL_furnace_wear"], 95, "a cold furnace is not repaired")
        m.variables["287"]["SHL_furnace_owner"] = 1
        m.variables["288"]["SHL_furnace_owner"] = 1
        m.variables["288"]["SHL_furnace_stock"] = 3
        m.run("SHL_stock_city_sites")
        self.assertEqual(m.variables["287"]["SHL_furnace_stock"], 3)
        self.assertEqual(m.variables["288"]["SHL_furnace_stock"], 3)
        self.assertEqual(m.variables["289"]["SHL_furnace_stock"], 2)
        expectations = {
            11: lambda: self.assertEqual(self.c["ADISCORD_economy_treasury"], 1090),
            21: lambda: self.assertEqual(m.infrastructure, 1),
            22: lambda: self.assertEqual(m.equipment[("SHL", "infantry_equipment")], 750),
            32: lambda: self.assertEqual(m.equipment[("SHL", "ADISCORD_squad_weapons_equipment_0")], 5),
            41: lambda: self.assertEqual(self.c["ADISCORD_economy_treasury"], 1150),
            52: lambda: self.assertEqual(m.variables["289"]["SHL_furnace_wear"], 10),
        }
        for ending, check in expectations.items():
            with self.subTest(ending=ending):
                self.c["ADISCORD_economy_treasury"] = 1000
                self.c["SHL_prog_ending"] = ending
                m.run("SHL_prog_first_batch")
                check()
        m.infrastructure = 5
        self.c["SHL_prog_ending"] = 21
        m.run("SHL_prog_first_batch")
        self.assertEqual(m.infrastructure, 5, "a full capital is not overbuilt")

    def test_measures_category_opens_with_ratification(self):
        categories = shared_definitions("common/decisions/categories/ADISCORD_decision_categories_SHL.txt", ("SHL_measures",))
        visible = block(categories["SHL_measures"], "visible")
        self.assertFalse(self.m.matches(visible, "SHL"))
        self.c["SHL_political_course"] = 3
        self.assertTrue(self.m.matches(visible, "SHL"))
        decisions = (ROOT / "common/decisions/ADISCORD_SHL_decisions.txt").read_text(encoding="utf-8")
        measures = re.search(r"^SHL_measures = \{\n(.*?)\n\}", decisions, re.M | re.S).group(1)
        for identifier in self.MEASURES:
            self.assertIn("\t" + identifier + " = {", measures)
        levers = re.search(r"^SHL_quarters_and_borders = \{\n(.*?)\n\}", decisions, re.M | re.S).group(1)
        self.assertIn("# ----- Conclave levers -----", levers)
        for identifier in ("SHL_convene_conclave", "SHL_quarter_charter", "SHL_dispatch_order", "SHL_arbitration_act", "SHL_house_audit", "SHL_desert_embassy", "SHL_integrate_satellite_decision"):
            self.assertIn("\t" + identifier + " = {", levers)
        conclave = re.search(r"^SHL_conclave = \{\n(.*?)\n\}", decisions, re.M | re.S).group(1)
        self.assertIn("\tSHL_war_orders_all = {", conclave)

    def test_every_new_key_is_localised_in_both_languages(self):
        decisions = (ROOT / "common/decisions/ADISCORD_SHL_decisions.txt").read_text(encoding="utf-8")
        effects = EFFECT_PATH.read_text(encoding="utf-8")
        scripted = (ROOT / "common/scripted_localisation/ADISCORD_SHL_scripted_loc.txt").read_text(encoding="utf-8")
        identifiers = [
            "SHL_convene_conclave", "SHL_quarter_charter", "SHL_dispatch_order", "SHL_arbitration_act",
            "SHL_house_audit", "SHL_desert_embassy", "SHL_integrate_satellite_decision", "SHL_war_orders_all",
            *self.MEASURES,
        ]
        keys = set()
        for identifier in identifiers:
            keys |= {identifier, identifier + "_desc"}
            for entry in walk_entries(decision_definition(identifier)):
                if entry.key in ("custom_effect_tooltip", "tooltip"):
                    keys.add(entry.value)
                elif entry.key == "custom_cost_text":
                    keys |= {entry.value + suffix for suffix in ("", "_blocked", "_tooltip")}
        for name in ("SHLGetReservePrice", "SHLGetPrice30", "SHLGetIntegrationPrice"):
            definition = re.search(r"name = " + name + r"\n(.*?)\n\}", scripted, re.S).group(1)
            keys |= set(re.findall(r"localization_key = (\w+)", definition))
        keys |= {"SHL_measures", "SHL_measures_desc", "ADISCORD_SHL_embassy", "SHL_cost_reserve", "SHL_cost_reserve_blocked", "SHL_cost_reserve_tooltip"}
        self.assertIn("SHL_cost_integration_blocked", keys)
        self.assertIn("SHL_price_reserve_premium_red", keys)
        for language, suffix in (("russian", "ru"), ("english", "en")):
            text = (ROOT / f"localisation/{language}/ADISCORD_SHL_l_{language}.yml").read_text(encoding="utf-8-sig")
            fragment = self.LOC_FRAGMENTS / f"stage4_script_{suffix}.yml"
            if fragment.exists():
                raw = fragment.read_bytes()
                self.assertFalse(raw.startswith(b"\xef\xbb\xbf"), "fragments carry no BOM")
                text += raw.decode("utf-8")
            defined = dict(re.findall(r"^ ([\w.]+):\d* \"(.*)\"$", text, re.M))
            self.assertEqual(sorted(keys - set(defined)), [], language)
            for key in keys:
                self.assertNotRegex(defined[key], "[\u2013\u2014\u00ab\u00bb]", key)
                self.assertNotRegex(defined[key], r"£\w+_texticon\s*§[YRG]\d", key)
            for identifier in identifiers:
                self.assertNotRegex(defined[identifier + "_desc"], r"§[GRY][+-]?\d", identifier + " description restates an effect")
        self.assertIn("SHL_political_action", effects)


if __name__ == "__main__":
    unittest.main()
