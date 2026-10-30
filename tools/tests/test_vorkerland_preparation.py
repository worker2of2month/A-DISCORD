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
    flag_ages: dict = field(default_factory=dict)
    resources: dict = field(default_factory=lambda: defaultdict(float))
    focuses: set = field(default_factory=set)
    cores: set = field(default_factory=set)
    owner: str = "WRK"
    controller: str = "WRK"
    fully_controlled: bool = True
    exists: bool = True
    subject: str | None = None
    faction: str | None = None
    capitulated: bool = False
    demilitarized: bool = False
    enemies: set = field(default_factory=set)
    war_sides: dict = field(default_factory=dict)
    ai: bool = True
    government: str = "pragmatism"
    cosmetic: str = ""
    leader: str = ""
    leader_ideology: str = ""
    character_roles: dict = field(default_factory=dict)
    power_balances: dict = field(default_factory=dict)
    templates: dict = field(default_factory=dict)
    template_locks: dict = field(default_factory=dict)
    template_recruitment: dict = field(default_factory=dict)
    rules: dict = field(default_factory=dict)
    victory_points: set = field(default_factory=set)
    province_buildings: dict = field(default_factory=dict)


class Script:
    def __init__(self):
        self.scopes = defaultdict(Scope)
        self.globals = {V + "phase_prewar"}
        self.calls = []
        self.random_index = 0
        self.random_weights = []
        self.game_rules = {"allow_volunteers": "LIMITED"}
        self.arrays = defaultdict(list)
        self.event_targets = {}
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
        if key.startswith("event_target:"):
            return self.event_targets.get(key.split(":", 1)[1])
        if key == "THIS":
            return current
        if key.startswith("var:"):
            return str(int(self.number(key[4:], current, previous)))
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
        if value in ("FROM", "THIS"):
            return float(self.scope(value, current, previous))
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
            elif key == "any_enemy_country":
                ok = any(self.conditions(value, enemy, current) for enemy in state.enemies)
            elif key == "any_country":
                countries = [name for name in self.scopes if re.fullmatch(r"[A-Z]{3}", name)]
                ok = any(self.conditions(value, name, current) for name in countries)
            elif key == "any_owned_state":
                owned = [name for name, candidate in self.scopes.items()
                         if name.isdigit() and candidate.owner == current]
                ok = any(self.conditions(value, name, current) for name in owned)
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
                ok = {"equals": actual == expected, "greater_than": actual > expected,
                      "greater_than_or_equals": actual >= expected, "less_than": actual < expected,
                      "less_than_or_equals": actual <= expected}[data.get("compare", "greater_than_or_equals")]
            elif key == "has_power_balance":
                ok = fields(value)["id"] in state.power_balances
            elif key == "power_balance_value":
                actual = state.power_balances.get(fields(value)["id"], 0)
                comparison = next(item for item in value if item[0] == "value")
                expected = float(comparison[2])
                ok = {"<": actual < expected, ">": actual > expected, "=": actual == expected}[comparison[1]]
            elif key == "has_variable":
                ok = value in state.variables
            elif key == "is_in_array":
                data = fields(value)
                target = self.scope(data["value"], current, previous)
                assert target is not None, data
                ok = target in self.arrays[data["array"]]
            elif key in ("has_state_flag", "has_country_flag", "has_idea"):
                if isinstance(value, list):
                    data = fields(value)
                    comparison = next(item for item in value if item[0] == "days")
                    assert comparison[1] == ">"
                    ok = data["flag"] in state.flags and state.flag_ages.get(data["flag"], 0) > float(comparison[2])
                else:
                    ok = value in state.flags
            elif key == "has_event_target":
                ok = value in self.event_targets
            elif key == "has_global_flag":
                ok = value in self.globals
            elif key == "has_completed_focus":
                ok = value in state.focuses
            elif key == "has_template":
                ok = value in state.templates
            elif key == "has_government":
                ok = state.government == value
            elif key == "has_game_rule":
                data = fields(value)
                ok = self.game_rules.get(data["rule"]) == data["option"]
            elif key == "has_cosmetic_tag":
                ok = state.cosmetic == value
            elif key == "has_country_leader":
                data = fields(value)
                ok = state.leader == data["character"]
                if data.get("ruling_only") == "no":
                    ok = ok or bool(state.character_roles.get(data["character"]))
            elif key == "has_character":
                ok = value in state.character_roles
            elif key == "country_exists":
                ok = self.scopes[value].exists
            elif key == "has_country_leader_ideology":
                ok = state.leader_ideology == value
            elif key in ("tag", "state"):
                expected = self.scope(value, current, previous) or value
                ok = current == expected
            elif key == "is_owned_by":
                ok = state.owner == self.scope(value, current, previous)
            elif key == "is_core_of":
                ok = self.scope(value, current, previous) in state.cores
            elif key == "is_controlled_by":
                ok = state.controller == self.scope(value, current, previous)
            elif key == "is_fully_controlled_by":
                ok = state.fully_controlled and state.controller == self.scope(value, current, previous)
            elif key == "is_owned_and_controlled_by":
                ok = state.owner == state.controller == self.scope(value, current, previous)
            elif key == "owns_state":
                ok = self.scopes[value].owner == current
            elif key == "controls_state":
                ok = self.scopes[value].controller == current
            elif key == "any_province_building_level":
                data = fields(value)
                assert fields(data["province"]) == {"all_provinces": "yes", "limit_to_victory_point": "yes"}
                level = next(item for item in value if item[0] == "level")
                expected = float(level[2])
                checks = []
                for province in state.victory_points:
                    actual = state.province_buildings.get(province, {}).get(data["building"], 0)
                    checks.append({"<": actual < expected, ">": actual > expected}[level[1]])
                ok = any(checks)
            elif key == "free_building_slots":
                data = fields(value)
                size = next(item for item in value if item[0] == "size")
                available = state.resources[data["building"] + "_slots"]
                required = self.number(size[2], current, previous)
                ok = {"=": available >= required, ">": available > required,
                      "<": available < required, ">=": available >= required,
                      "<=": available <= required}[size[1]]
            elif key == "is_demilitarized_zone":
                ok = state.demilitarized == (value == "yes")
            elif key == "has_dynamic_modifier":
                ok = fields(value)["modifier"] in state.flags
            elif key == "is_subject_of":
                ok = state.subject == value
            elif key == "has_war_with":
                ok = self.scope(value, current, previous) in state.enemies
            elif key == "has_war_together_with":
                target = self.scopes[self.scope(value, current, previous)]
                ok = any(target.war_sides.get(war) == side for war, side in state.war_sides.items())
            elif key == "is_in_faction_with":
                target = self.scope(value, current, previous)
                ok = state.faction is not None and state.faction == self.scopes[target].faction
            elif key in ("exists", "is_subject", "has_capitulated", "is_in_faction", "is_faction_leader", "always", "is_ai", "has_war"):
                actual = {"exists": state.exists, "is_subject": state.subject is not None,
                          "has_capitulated": state.capitulated, "is_in_faction": state.faction is not None,
                          "is_faction_leader": state.faction == current, "always": True,
                          "is_ai": state.ai, "has_war": bool(state.enemies)}[key]
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
            elif key in ("custom_effect_tooltip", "unlock_decision_tooltip", "effect_tooltip"):
                continue
            elif self.scope(key, current, previous) is not None:
                self.run(value, self.scope(key, current, previous), current)
            elif key in EFFECTS and (
                key.startswith((P, V + "wkr_", V + "tva_", V + "vad_", "TVA_", "VAD_", "WKR_"))
                or key in (V + "refresh_doctrine_dynamic_state", V + "apply_focus_doctrine",
                           V + "ensure_worker_home_guard_template", V + "promote_nikita_worcker",
                           V + "promote_anton_bagley", V + "form_joint_government",
                           V + "appoint_joint_council", V + "establish_petrichev_empire",
                           V + "initialize_world_empire", V + "empire_grant_estate",
                           V + "empire_install_governor")
            ):
                self.effect(key, current, previous)
            elif key == "random_list":
                choices = [(self.number(weight, current, previous), effects) for weight, _, effects in value]
                self.random_weights.append(tuple(weight for weight, _ in choices))
                self.run(choices[self.random_index][1], current, previous)
            elif key in ("set_variable", "set_temp_variable", "add_to_variable", "add_to_temp_variable", "subtract_from_variable",
                         "subtract_from_temp_variable", "multiply_variable", "multiply_temp_variable",
                         "divide_variable", "clamp_variable", "clamp_temp_variable"):
                data = fields(value)
                name = data.get("var", next(iter(data)))
                before = state.variables.get(name, 0)
                amount = self.number(data.get("value", data.get(name, "0")), current, previous)
                if key in ("set_variable", "set_temp_variable"):
                    state.variables[name] = amount
                elif key in ("clamp_variable", "clamp_temp_variable"):
                    state.variables[name] = min(float(data["max"]), max(float(data["min"]), before))
                elif key in ("multiply_variable", "multiply_temp_variable"):
                    state.variables[name] = before * amount
                elif key == "divide_variable":
                    state.variables[name] = before / amount
                else:
                    state.variables[name] = before + amount * (-1 if key.startswith("subtract_from_") else 1)
            elif key == "clear_variable":
                state.variables.pop(value, None)
            elif key in ("set_state_flag", "set_country_flag"):
                flag = fields(value)["flag"] if isinstance(value, list) else value
                state.flags.add(flag)
                state.flag_ages[flag] = 0
            elif key in ("clr_state_flag", "clr_country_flag"):
                state.flags.discard(value)
                state.flag_ages.pop(value, None)
            elif key == "save_global_event_target_as":
                self.event_targets[value] = current
            elif key == "clear_global_event_target":
                self.event_targets.pop(value, None)
            elif key == "set_global_flag":
                self.globals.add(value)
            elif key == "set_cosmetic_tag":
                state.cosmetic = value
                self.calls.append((key, current, value))
            elif key in ("add_political_power", "add_command_power", "add_manpower", "add_stability", "add_war_support"):
                resource = {"add_political_power": "pp", "add_command_power": "command", "add_manpower": "people",
                            "add_stability": "stability", "add_war_support": "war_support"}[key]
                state.resources[resource] += self.number(value, current, previous)
            elif key == "add_equipment_to_stockpile":
                data = fields(value)
                equipment = re.sub(r"_\d+$", "", data["type"])
                state.resources[equipment] += self.number(data["amount"], current, previous)
            elif key == "send_equipment":
                data = fields(value)
                equipment = data["type"]
                amount = self.number(data["amount"], current, previous)
                target = self.scopes[self.scope(data["target"], current, previous)]
                assert state.resources[equipment] >= amount
                state.resources[equipment] -= amount
                target.resources[equipment] += amount
                self.calls.append((key, current, value))
            elif key in ("army_experience", "add_fuel"):
                state.resources[key] += self.number(value, current, previous)
            elif key == "add_building_construction":
                data = fields(value)
                if "province" in data:
                    assert fields(data["province"]) == {"all_provinces": "yes", "limit_to_victory_point": "yes"}
                    for province in state.victory_points:
                        buildings = state.province_buildings.setdefault(province, {})
                        buildings[data["type"]] = min(10, buildings.get(data["type"], 0) + float(data["level"]))
                else:
                    state.resources[data["type"]] += float(data["level"])
                    state.resources[data["type"] + "_slots"] -= float(data["level"])
            elif key == "add_dynamic_modifier":
                state.flags.add(fields(value)["modifier"])
                self.calls.append((key, current, value))
            elif key == "remove_dynamic_modifier":
                state.flags.discard(fields(value)["modifier"])
            elif key == "add_timed_idea":
                state.flags.add(fields(value)["idea"])
                self.calls.append((key, current, value))
            elif key == "remove_ideas":
                assert isinstance(value, str), value
                state.flags.discard(value)
                self.calls.append((key, current, value))
            elif key == "set_power_balance":
                state.power_balances[fields(value)["id"]] = float(fields(value)["set_value"])
            elif key == "add_power_balance_value":
                name = fields(value)["id"]
                state.power_balances[name] = min(1, max(-1, state.power_balances.get(name, 0) + float(fields(value)["value"])))
            elif key == "remove_power_balance":
                state.power_balances.pop(fields(value)["id"], None)
            elif key == "set_politics":
                state.government = fields(value)["ruling_party"]
            elif key == "set_rule":
                state.rules.update(fields(value))
                self.calls.append((key, current, value))
            elif key == "add_country_leader_role":
                data = fields(value)
                ideology = fields(data["country_leader"])["ideology"]
                roles = state.character_roles.setdefault(data["character"], set())
                assert ideology not in roles, (data["character"], ideology)
                roles.add(ideology)
                if data.get("promote_leader") == "yes":
                    state.leader = data["character"]
                    state.leader_ideology = ideology
            elif key == "promote_character":
                data = fields(value)
                assert data["ideology"] in state.character_roles[data["character"]]
                state.leader = data["character"]
                state.leader_ideology = data["ideology"]
            elif key == "set_nationality":
                data = fields(value)
                target = self.scopes[data["target_country"]]
                target.character_roles[data["character"]] = state.character_roles.pop(data["character"])
                if state.leader == data["character"]:
                    state.leader = ""
                    state.leader_ideology = ""
            elif key == "retire_character":
                state.character_roles.pop(value, None)
            elif key in ("add_to_array", "remove_from_array"):
                data = fields(value)
                target = self.scope(data["value"], current, previous)
                assert target is not None, data
                values = self.arrays[data["array"]]
                if key == "add_to_array":
                    values.append(target)
                else:
                    assert target in values, f"Invalid array removal: {data['array']} does not contain {target}"
                    values.remove(target)
            elif key == "clear_array":
                self.arrays[value].clear()
            elif key == "for_each_scope_loop":
                data = fields(value)
                for target in tuple(self.arrays[data["array"]]):
                    self.run([item for item in value if item[0] != "array"], target, current)
            elif key == "for_loop_effect":
                data = fields(value)
                self.assert_loop_fields(data)
                end = int(self.number(data["end"], current, previous))
                assert 0 <= end <= 100, end
                for index in range(end):
                    state.variables[data.get("value", "v")] = index
                    self.run([item for item in value if item[0] not in ("end", "value")], current, previous)
            elif key == "division_template":
                data = fields(value)
                state.templates[data["name"]] = value
                state.template_locks[data["name"]] = data.get("is_locked") == "yes"
                state.template_recruitment[data["name"]] = data.get("force_allow_recruiting") == "yes"
            elif key in ("set_division_template_lock", "set_division_force_allow_recruiting"):
                data = fields(value)
                name = data["division_template"]
                assert name in state.templates, name
                if key == "set_division_template_lock":
                    state.template_locks[name] = data["is_locked"] == "yes"
                else:
                    state.template_recruitment[name] = data["force_allow_recruiting"] == "yes"
            elif key in ("create_unit", "add_tech_bonus", "activate_mission", "country_event", "add_intel",
                         "diplomatic_relation", "puppet", "set_autonomy", "declare_war_on",
                         "set_country_leader_portrait", "set_portraits", "load_focus_tree", "news_event",
                         "mark_focus_tree_layout_dirty", "set_party_name", "set_popularities",
                         "force_update_dynamic_modifier", "ADISCORD_economy_mark_dirty",
                         V + "story_report_variant_declaration",
                         V + "ensure_emergency_militia_template", V + "add_legitimacy", V + "join_coalition_of_FROM"):
                self.calls.append((key, current, value))
            else:
                raise AssertionError(f"Unsupported effect: {key} {value}")

    @staticmethod
    def assert_loop_fields(data):
        # Only the native default 0..end-1 form is exercised by this fixture.
        assert not set(data) & {"start", "add", "compare", "break"}, data

    def start(self, name):
        block = fields(PROJECTS[name])
        self.source = fields(block["targets"])[""]
        self.run(block["complete_effect"])


class ClaimantPreparationScheduleTests(unittest.TestCase):
    """Source-driven focus scheduling; combat, production and native AI polling are external."""

    @classmethod
    def setUpClass(cls):
        cls.plans = fields(parse(read("common/ai_strategy_plans/ADISCORD_vorkerland_plans.txt")))
        cls.focuses = {}
        for tag in ("wkr", "vad", "tva"):
            cls.focuses.update({
                fields(value)["id"]: value
                for key, _, value in walk(parse(read(f"focus_trees/Vorkerland/{tag}/focuses.txt")))
                if key == "focus" and isinstance(value, list)
            })

    def campaign(self, tag, variant):
        script = Script()
        script.root = tag
        script.globals = {V + "collapse_started", V + "collapse_wars_started",
                          V + "phase_central_preparation"}
        country = script.scopes[tag]
        country.focuses.clear()
        country.resources.update(infantry_equipment=6000, support_equipment=200, has_stability=0.6)
        if tag == "WKR":
            country.leader = "WRK_Nikita_Worcker" if variant == "worker" else "WRK_Anton_Bagley"
            country.government = "pragmatism" if variant == "worker" else "utilitarism"
            country.leader_ideology = "neo_vorkerism"
            if variant == "worker":
                script.globals.add(V + "worker_safe_with_loyalists")
        elif tag == "VAD":
            country.leader = "WRK_Vlad_Petrichev"
            country.character_roles = {
                "WRK_Vlad_Petrichev": {"imperial_restorationism"},
                "WRK_VAD_Joint_Council": {"pragmatism_ideology"},
            }
            script.effect("VAD_initialize_administration")
            if variant == "joint":
                script.globals.add(V + "worker_rescued_by_vlad")
        else:
            country.leader = "TVA_Dorian_Worx"
            country.government = "technocracy"
        return script

    def active_plans(self, script):
        result = []
        for name, raw in self.plans.items():
            if not name.startswith(V + script.root.lower() + "_"):
                continue
            plan = fields(raw)
            if script.conditions(plan.get("enable", [])) and not script.conditions(plan.get("abort", [])):
                result.append((name, plan))
        return result

    def eligible(self, script, name):
        raw = self.focuses[name]
        country = script.scopes[script.root]
        if name in country.focuses:
            return False
        for key, _, group in raw:
            if key == "prerequisite" and not {value for _, _, value in group} & country.focuses:
                return False
            if key == "mutually_exclusive" and {value for _, _, value in group} & country.focuses:
                return False
        return (
            script.conditions(fields(raw).get("allow_branch", []))
            and script.conditions(fields(raw).get("available", []))
        )

    def complete(self, script, name):
        country = script.scopes[script.root]
        if name == "VAD_form_field_commandantures":
            script.run(fields(self.focuses[name])["completion_reward"])
        country.focuses.add(name)
        # Scheduling markers come from the actual reward. No units or stock income are simulated.
        for key, _, value in walk(fields(self.focuses[name])["completion_reward"]):
            if key == "set_country_flag" and isinstance(value, str):
                country.flags.add(value)

    def run_readiness(self, tag, variant, political="algorithm", trial="remote", response_days=0,
                      surrender=0):
        script = self.campaign(tag, variant)
        script.scopes[tag].resources["surrender_progress"] = surrender
        elapsed = 0
        route = []
        trial_due = None
        trial_options = [value for key, _, value in EVENTS[V + "claimant.23"] if key == "option"]
        capstone = V + "focus_" + tag.lower() + "_central_war_unlocked"
        while capstone not in script.scopes[tag].flags:
            self.assertLess(len(route), 30, route)
            if tag == "TVA":
                resources = script.scopes[tag].resources
                resources["infantry_equipment"] = 4999 if political == "throughput" else 5000
                resources["has_stability"] = 0.49 if political == "specialist" else 0.50
                if trial_due is not None and elapsed >= trial_due:
                    option = trial_options[("technical", "remote", "adaptive").index(trial)]
                    script.run([item for item in option if item[0] not in ("name", "ai_chance")])
                    trial_due = None
            candidates = []
            for name, plan in self.active_plans(script):
                route_names = [value for _, _, value in plan.get("ai_national_focuses", [])]
                next_focus = next((focus for focus in route_names if self.eligible(script, focus)), None)
                if next_focus:
                    candidates.append((float(fields(plan["weight"])["factor"]), name, next_focus))
            self.assertTrue(candidates, (tag, variant, route))
            highest = max(weight for weight, _, _ in candidates)
            best = [(name, focus) for weight, name, focus in candidates if weight == highest]
            self.assertEqual(len(best), 1, best)
            plan, focus = best[0]
            self.assertNotIn("variant_plan", plan)
            self.assertNotIn("depth_plan", plan)
            elapsed += float(fields(self.focuses[focus])["cost"]) * 7
            self.complete(script, focus)
            route.append(focus)
            for key, _, value in walk(fields(self.focuses[focus])["completion_reward"]):
                if key == "country_event" and fields(value)["id"] == V + "claimant.23":
                    trial_due = elapsed + float(fields(value)["days"]) + response_days
        return script, elapsed, route

    def test_all_claimants_complete_readiness_within_180_days(self):
        for tag, variant in (("WKR", "worker"), ("WKR", "bagley"), ("VAD", "imperial"), ("VAD", "joint")):
            with self.subTest(tag=tag, variant=variant):
                script, elapsed, route = self.run_readiness(tag, variant)
                self.assertLessEqual(elapsed, 175, route)
                self.assertTrue(any("variant_plan" in name for name, _ in self.active_plans(script)))
        for political, trial, response_days in product(("throughput", "algorithm", "specialist"), ("technical", "remote", "adaptive"), (0, 14)):
            with self.subTest(political=political, trial=trial, response_days=response_days):
                script, elapsed, route = self.run_readiness("TVA", "worx", political, trial, response_days)
                self.assertLessEqual(elapsed, 175, route)
                self.assertTrue(any(political + "_" + trial + "_depth_plan" in name for name, _ in self.active_plans(script)))

    def test_tva_choices_are_disjoint_at_fractional_resource_boundaries(self):
        political = {"throughput_priority", "specialist_priority", "algorithmic_priority"}
        trials = {"technical_trial", "adaptive_trial", "remote_trial"}
        for rifles, stability in product((4999.99, 5000, 5000.01), (0.4999, 0.50, 0.5001)):
            script = self.campaign("TVA", "worx")
            country = script.scopes["TVA"]
            country.focuses.update({"TVA_publish_operational_metrics", "TVA_select_trial_protocol"})
            country.resources.update(infantry_equipment=rifles, has_stability=stability)
            active = {name.removeprefix(V + "tva_").removesuffix("_plan") for name, _ in self.active_plans(script)}
            self.assertEqual(len(active & political), 1)
            self.assertFalse(active & trials)
        for option in (value for key, _, value in EVENTS[V + "claimant.23"] if key == "option"):
            script = self.campaign("TVA", "worx")
            script.scopes["TVA"].focuses.add("TVA_select_trial_protocol")
            script.run([item for item in option if item[0] not in ("name", "ai_chance")])
            active = {name.removeprefix(V + "tva_").removesuffix("_plan") for name, _ in self.active_plans(script)}
            self.assertEqual(len(active & trials), 1)
        script.globals.add(V + "collapse_finished")
        active = {name.removeprefix(V + "tva_").removesuffix("_plan") for name, _ in self.active_plans(script)}
        self.assertFalse(active & (political | trials))

    def test_tva_political_variant_covers_exact_surrender_boundary(self):
        for progress in (0.04999, 0.05, 0.05001):
            script = self.campaign("TVA", "worx")
            script.scopes["TVA"].flags.add(V + "focus_tva_central_war_unlocked")
            script.scopes["TVA"].resources["surrender_progress"] = progress
            variants = [name for name, _ in self.active_plans(script) if name.endswith("_variant_plan")]
            self.assertEqual(len(variants), 1)
            expected = "throughput" if progress > 0.05 else "preservation"
            self.assertIn(expected, variants[0])

    def test_tva_mandate_is_chosen_in_the_first_month_without_delaying_readiness(self):
        for progress, choice in ((0.05, "TVA_enact_the_preservation_protocol"),
                                 (0.05001, "TVA_declare_continuous_mobilization")):
            for political, trial in product(("throughput", "algorithm", "specialist"),
                                            ("technical", "remote", "adaptive")):
                with self.subTest(progress=progress, political=political, trial=trial):
                    _, elapsed, route = self.run_readiness(
                        "TVA", "worx", political, trial, 14, surrender=progress,
                    )
                    self.assertEqual(route[:2], ["TVA_codify_utilitarian_directorate", choice])
                    mandate_day = sum(float(fields(self.focuses[name])["cost"]) * 7
                                      for name in route[:2])
                    self.assertEqual(mandate_day, 21)
                    self.assertLessEqual(elapsed, 175)

    def test_tva_programmes_can_finish_before_the_central_war(self):
        category = fields(fields(parse(read("common/decisions/ADISCORD_vorkerland_decisions.txt")))[
            "ADISCORD_vorkerland_tva_administration"
        ])
        cases = (
            ("TVA_maintenance_programme", ("TVA_codify_utilitarian_directorate", "TVA_reroute_city_grid")),
            ("TVA_cadre_training_programme", ("TVA_codify_utilitarian_directorate", "TVA_deploy_field_laboratories")),
            ("TVA_emergency_series_programme", ("TVA_codify_utilitarian_directorate", "TVA_declare_continuous_mobilization")),
        )
        for decision, route in cases:
            with self.subTest(decision=decision):
                script = self.campaign("TVA", "worx")
                script.effect("TVA_initialize_administration")
                script.scopes["TVA"].enemies.clear()
                elapsed = 0
                for focus in route:
                    self.assertTrue(self.eligible(script, focus), focus)
                    elapsed += float(fields(self.focuses[focus])["cost"]) * 7
                    self.complete(script, focus)
                    reward = fields(self.focuses[focus])["completion_reward"]
                    metric_effects = [item for item in walk(reward) if item[0] in (
                        "add_to_variable", "subtract_from_variable", "add_power_balance_value",
                    )]
                    script.run(metric_effects)
                    script.effect("TVA_refresh_administration")
                programme = fields(category[decision])
                self.assertTrue(script.conditions(programme["visible"]))
                self.assertTrue(script.conditions(programme["available"]))
                self.assertLessEqual(elapsed + float(programme["days_remove"]), 49)

    def test_vad_followup_plan_reaches_its_final_focus_during_the_central_war(self):
        for variant, plan_variant in (("imperial", "vlad"), ("joint", "joint")):
            with self.subTest(variant=variant):
                script, _, _ = self.run_readiness("VAD", variant)
                script.globals.discard(V + "phase_central_preparation")
                script.globals.update({V + "phase_central_showdown", V + "central_showdown_started"})
                plan = fields(self.plans[V + "vad_" + plan_variant + "_depth_plan"])
                route = [value for _, _, value in plan["ai_national_focuses"]]
                self.assertEqual(route[-1], "VAD_publish_interim_restoration_register")
                # Build the paid institution through its normal decision before the levy focus.
                administration = VADDistrictAdministrationTests()
                administration.setUpClass()
                country = script.scopes["VAD"]
                country.resources.update(pp=100, people=2000)
                script.scopes["75"].owner = script.scopes["75"].controller = "VAD"
                institution = "charter" if variant == "imperial" else "commandant"
                self.assertTrue(administration.start(script, institution))
                operation = administration.orders[institution]
                script.run(operation["remove_effect"])
                elapsed = int(operation["days_remove"])
                for focus in route:
                    self.assertTrue(script.conditions(plan["enable"]), focus)
                    self.assertFalse(script.conditions(plan["abort"]), focus)
                    bypass = fields(self.focuses[focus]).get("bypass")
                    if bypass is not None and script.conditions(bypass):
                        self.assertEqual(focus, "VAD_define_the_solar_settlement")
                        script.scopes["VAD"].focuses.add(focus)
                    else:
                        self.assertTrue(self.eligible(script, focus), focus)
                        self.complete(script, focus)
                        elapsed += int(fields(self.focuses[focus])["cost"]) * 7
                self.assertLess(elapsed, 720)
                self.assertTrue(script.conditions(plan["abort"]))
                self.assertNotIn(V + "focus_vad_solar_settlement_defined", script.scopes["VAD"].flags)

    def test_solar_intervention_is_available_before_war_and_skipped_after_it(self):
        script, _, _ = self.run_readiness("VAD", "imperial")
        script.globals.add(V + "solar_terminal_verified")
        script.scopes["VAD"].focuses.update({"VAD_preposition_restoration_columns", "VAD_settle_restoration_authority"})
        focus = self.focuses["VAD_define_the_solar_settlement"]
        self.assertTrue(self.eligible(script, "VAD_define_the_solar_settlement"))
        self.assertFalse(script.conditions(fields(focus)["bypass"]))
        script.globals.add(V + "central_showdown_started")
        self.assertFalse(self.eligible(script, "VAD_define_the_solar_settlement"))
        self.assertTrue(script.conditions(fields(focus)["bypass"]))


class FieldTrialAccountingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        decisions = parse(read("common/decisions/ADISCORD_vorkerland_decisions.txt"))
        cls.order = next(fields(value) for key, _, value in walk(decisions)
                         if key == V + "tva_run_field_trial")
        from tools.lib.on_actions import read_scripted_peace
        cls.hooks = fields(fields(parse(read_scripted_peace(
            ROOT / "common/on_actions/09_ADISCORD_scripted_peace_on_actions.txt",
            "vorkerland_collapse",
        )))["on_actions"])

    def campaign(self):
        script = Script()
        script.root = "TVA"
        script.globals = {V + "collapse_wars_started"}
        country = script.scopes["TVA"]
        country.focuses.add("TVA_select_trial_protocol")
        country.enemies.add("WKR")
        country.resources.update(pp=100, infantry_equipment=10000)
        script.effect("TVA_initialize_administration")
        script.calls.clear()
        return script

    def start(self, script):
        for field in ("visible", "available", "custom_cost_trigger"):
            if not script.conditions(self.order[field]):
                return False
        script.run(self.order["complete_effect"])
        return True

    def test_fractional_prices_and_duplicate_payment(self):
        for pp, rifles, affordable in ((29.99, 9000, False), (30, 8999.99, False),
                                       (30, 9000, True), (30.01, 9000.01, True)):
            with self.subTest(pp=pp, rifles=rifles):
                script = self.campaign()
                resources = script.scopes["TVA"].resources
                resources.update(pp=pp, infantry_equipment=rifles)
                self.assertEqual(self.start(script), affordable)
                paid = deepcopy(resources)
                script.effect(V + "tva_begin_field_trial")
                self.assertEqual(resources, paid)
                self.assertAlmostEqual(resources["pp"], pp - 30 * affordable)
                self.assertAlmostEqual(resources["infantry_equipment"], rifles - 9000 * affordable)

    def test_each_probability_and_outcome_settles_once(self):
        for iteration, chance in ((0, 40), (1, 55), (2, 70), (3, 85), (8, 85)):
            for outcome in (0, 1):
                with self.subTest(iteration=iteration, outcome=outcome):
                    script = self.campaign()
                    country = script.scopes["TVA"]
                    country.variables[V + "tva_iterations"] = iteration
                    self.assertTrue(self.start(script))
                    script = deepcopy(script)
                    country = script.scopes["TVA"]
                    script.random_index = outcome
                    script.run(self.order["remove_effect"])
                    self.assertEqual(script.random_weights, [(chance, 100 - chance)])
                    self.assertEqual(country.variables[V + "tva_iterations"], iteration + 1)
                    self.assertEqual(country.resources["pp"], 70)
                    self.assertEqual(country.resources["infantry_equipment"], 1000)
                    self.assertNotIn(V + "tva_trial_paid", country.flags)
                    if outcome == 0:
                        self.assertEqual(sum(key == "add_tech_bonus" for key, _, _ in script.calls), 1)
                    else:
                        self.assertEqual(country.resources["army_experience"], 10)
                        self.assertFalse([call for call in script.calls if call[0] == "add_tech_bonus"])
                        self.assertTrue(any(key == "country_event" and fields(value)["id"] == V + "claimant.26" for key, _, value in script.calls))
                    settled = deepcopy((script.scopes, script.calls, script.random_weights))
                    script.run(self.order["remove_effect"])
                    script.run(self.order["cancel_effect"])
                    self.assertEqual((script.scopes, script.calls, script.random_weights), settled)

    def test_success_uses_the_selected_research_protocol(self):
        for focus, category in (("TVA_raise_technical_battalions", "infantry_weapons"),
                                ("TVA_test_remote_fire_control", "electronics"),
                                ("TVA_test_adaptive_logistics", "support_tech")):
            with self.subTest(focus=focus):
                script = self.campaign()
                script.scopes["TVA"].resources.update(people=600, support_equipment=120)
                script.scopes["TVA"].focuses.add(focus)
                self.assertTrue(self.start(script))
                script.run(self.order["remove_effect"])
                bonus = [fields(value) for key, _, value in script.calls if key == "add_tech_bonus"]
                self.assertEqual([entry["category"] for entry in bonus], [category])

    def test_interruption_refunds_without_a_result_or_iteration(self):
        for reason in ("peace", "capitulation", "subject", "central_end", "campaign_end"):
            for callback in ("remove_effect", "cancel_effect"):
                with self.subTest(reason=reason, callback=callback):
                    script = self.campaign()
                    self.assertTrue(self.start(script))
                    country = script.scopes["TVA"]
                    if reason == "peace":
                        country.enemies.clear()
                    elif reason == "capitulation":
                        country.capitulated = True
                    elif reason == "subject":
                        country.subject = "VAD"
                    else:
                        script.globals.add(V + ("central_war_finished" if reason == "central_end" else "collapse_finished"))
                    self.assertTrue(script.conditions(self.order["cancel_trigger"]))
                    script.run(self.order[callback])
                    script.run(self.order["remove_effect"])
                    script.run(self.order["cancel_effect"])
                    self.assertEqual(country.resources["pp"], 100)
                    self.assertEqual(country.resources["infantry_equipment"], 10000)
                    self.assertNotIn(V + "tva_iterations", country.variables)
                    self.assertFalse([call for call in script.calls if call[0] in ("add_tech_bonus", "country_event")])
                    self.assertNotIn(V + "tva_trial_paid", country.flags)
                    self.assertFalse(self.start(script))

    def trial_callback(self, hook):
        body = fields(self.hooks[hook])["effect"]
        callbacks = [item for item in body if any(
            key in (V + "tva_cancel_field_trial", V + "tva_settle_trial_handoff")
            for key, _, _ in walk([item]))]
        self.assertEqual(len(callbacks), 1)
        return callbacks

    def test_native_callbacks_use_victim_and_annexer_scopes(self):
        for hook in ("on_capitulation_immediate", "on_capitulation", "on_puppet", "on_annex"):
            with self.subTest(hook=hook):
                script = self.campaign()
                self.assertTrue(self.start(script))
                recipient = "TVA"
                if hook == "on_annex":
                    script.root = recipient = "VAD"
                    script.source = "TVA"
                    script.scopes["TVA"].exists = False
                else:
                    script.source = "VAD"
                before = deepcopy(script.scopes[recipient].resources)
                script.run(self.trial_callback(hook))
                script.run(self.trial_callback(hook))
                self.assertEqual(script.scopes[recipient].resources["pp"], before["pp"] + 30)
                self.assertEqual(script.scopes[recipient].resources["infantry_equipment"], before["infantry_equipment"] + 9000)
                self.assertNotIn(V + "tva_trial_paid", script.scopes["TVA"].flags)
                script.root = "TVA"
                script.run(self.order["remove_effect"])
                self.assertFalse([call for call in script.calls if call[0] in ("add_tech_bonus", "country_event")])

    def test_handoff_transfers_payment_before_annexation(self):
        script = self.campaign()
        self.assertTrue(self.start(script))
        before = deepcopy(script.scopes["WRK"].resources)
        script.effect(V + "tva_settle_trial_handoff", "WRK")
        script.effect(V + "tva_settle_trial_handoff", "WRK")
        self.assertEqual(script.scopes["WRK"].resources["pp"], before["pp"] + 30)
        self.assertEqual(script.scopes["WRK"].resources["infantry_equipment"], before["infantry_equipment"] + 9000)
        script.run(self.order["remove_effect"])
        script.run(self.order["cancel_effect"])
        self.assertFalse([call for call in script.calls if call[0] in ("add_tech_bonus", "country_event")])
        for route in ("wkr", "vad", "tva"):
            keys = [key for key, _, _ in walk(EFFECTS[V + "form_wrk_from_" + route])]
            self.assertLess(keys.index("transfer_state"), keys.index(V + "tva_settle_trial_handoff"))
            self.assertLess(keys.index(V + "tva_settle_trial_handoff"), keys.index("load_focus_tree"))

    def test_war_cleanup_settles_the_receipt_before_old_callbacks(self):
        script = self.campaign()
        self.assertTrue(self.start(script))
        cleanup = [item for item in EFFECTS[V + "clear_claimant_war_modifiers"]
                   if item[0] == V + "tva_cancel_field_trial"]
        self.assertEqual(len(cleanup), 1)
        script.run(cleanup)
        script.run(self.order["remove_effect"])
        self.assertEqual(script.scopes["TVA"].resources["pp"], 100)
        self.assertEqual(script.scopes["TVA"].resources["infantry_equipment"], 10000)
        self.assertFalse([call for call in script.calls if call[0] in ("add_tech_bonus", "country_event")])


class TVAAdministrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        categories = fields(parse(read("common/decisions/ADISCORD_vorkerland_decisions.txt")))
        cls.category = fields(categories["ADISCORD_vorkerland_tva_administration"])
        cls.trial = fields(cls.category[V + "tva_run_field_trial"])
        cls.orders = {name: fields(cls.category["TVA_" + name + "_programme"])
                      for name in ("maintenance", "cadre_training", "emergency_series")}

    def campaign(self):
        script = FieldTrialAccountingTests.campaign(self)
        country = script.scopes["TVA"]
        country.resources.update(pp=1000, support_equipment=500, people=6000)
        country.variables.update(TVA_network_load=50, TVA_cadre_reserve=50)
        country.power_balances["TVA_bop"] = -0.3
        country.focuses.update({"TVA_reroute_city_grid", "TVA_deploy_field_laboratories",
                                "TVA_optimize_for_throughput"})
        script.effect("TVA_refresh_administration")
        script.calls.clear()
        return script

    def start(self, script, name):
        order = self.orders[name]
        for field in ("visible", "available", "custom_cost_trigger"):
            if not script.conditions(order[field]):
                return False
        script.run(order["complete_effect"])
        return True

    def test_reopening_preserves_balance_inputs_and_current_campaign_state(self):
        script = self.campaign()
        script.scopes["TVA"].variables.update(TVA_network_load=92, TVA_cadre_reserve=18,
                                             TVA_policy_industrial_capacity_factory=.17)
        script.scopes["TVA"].power_balances["TVA_bop"] = -0.75
        script.effect("TVA_refresh_administration")
        before = deepcopy(script.scopes["TVA"])
        script = deepcopy(script)
        script.effect("TVA_initialize_administration")
        self.assertEqual(script.scopes["TVA"], before)

    def test_metrics_drive_bounded_modifiers_and_trial_probabilities(self):
        cases = ((35, 60, 0, 40), (69.99, 60, 0, 40), (70, 60, 0, 20),
                 (89.99, 60, 0, 20), (90, 60, 0, 5), (35, 29.99, 0, 25),
                 (35, 30, 0, 40), (35, 74.99, 0, 40), (35, 75, 0, 50),
                 (90, 0, 0, 5), (0, 100, 8, 95))
        for load, reserve, iterations, chance in cases:
            with self.subTest(load=load, reserve=reserve, iterations=iterations):
                script = self.campaign()
                values = script.scopes["TVA"].variables
                values.update(TVA_network_load=load, TVA_cadre_reserve=reserve)
                values[V + "tva_iterations"] = iterations
                script.effect("TVA_refresh_administration")
                self.assertEqual(values["TVA_trial_success_chance"], chance)
                self.assertAlmostEqual(values["TVA_network_output"], -max(0, load - 50) * .002)
                self.assertAlmostEqual(values["TVA_cadre_research"], (reserve - 50) * .001)
        values.update(TVA_network_load=200, TVA_cadre_reserve=-20)
        script.effect("TVA_refresh_administration")
        self.assertEqual((values["TVA_network_load"], values["TVA_cadre_reserve"]), (100, 0))

    def test_paid_trial_keeps_its_risk_when_other_work_finishes(self):
        script = self.campaign()
        trial = self.trial
        script.run(trial["complete_effect"])
        paid_chance = script.scopes["TVA"].variables["TVA_trial_chance"]
        script.scopes["TVA"].variables.update(TVA_network_load=95, TVA_cadre_reserve=5)
        script.effect("TVA_refresh_administration")
        self.assertNotEqual(script.scopes["TVA"].variables["TVA_trial_success_chance"], paid_chance)
        script.run(trial["remove_effect"])
        self.assertEqual(script.random_weights, [(paid_chance, 100 - paid_chance)])
        self.assertNotIn("TVA_trial_chance", script.scopes["TVA"].variables)

    def test_all_prices_have_exact_fractional_boundaries(self):
        prices = {"maintenance": {"pp": 40, "support_equipment": 80},
                  "cadre_training": {"pp": 35, "people": 600}, "emergency_series": {"pp": 30}}
        for name, currencies in prices.items():
            for resource, price in currencies.items():
                with self.subTest(order=name, currency=resource):
                    script = self.campaign()
                    resources = script.scopes["TVA"].resources
                    resources[resource] = price - .01
                    self.assertFalse(self.start(script, name))
                    script.effect("TVA_begin_" + name)
                    self.assertNotIn("TVA_programme_pp", script.scopes["TVA"].variables)
                    resources[resource] = price
                    self.assertTrue(self.start(script, name))
                    self.assertAlmostEqual(resources[resource], 0)

    def test_orders_share_one_slot_and_repeated_callbacks_cannot_duplicate_delivery(self):
        for name, order in self.orders.items():
            with self.subTest(order=name):
                script = self.campaign()
                self.assertTrue(self.start(script, name))
                paid = deepcopy(script.scopes)
                for other in self.orders:
                    self.assertFalse(self.start(script, other))
                    script.effect("TVA_begin_" + other)
                self.assertEqual(script.scopes, paid)
                script.run(order["remove_effect"])
                country = script.scopes["TVA"]
                self.assertNotIn("TVA_programme_pp", country.variables)
                if name == "maintenance":
                    self.assertEqual(country.variables["TVA_network_load"], 25)
                elif name == "cadre_training":
                    self.assertEqual(country.variables["TVA_cadre_reserve"], 70)
                    self.assertAlmostEqual(country.power_balances["TVA_bop"], -.2)
                else:
                    self.assertEqual(country.resources["infantry_equipment"], 14500)
                    self.assertEqual(country.resources["support_equipment"], 560)
                    self.assertEqual(country.variables["TVA_network_load"], 70)
                    self.assertEqual(country.variables["TVA_cadre_reserve"], 40)
                delivered = deepcopy(script.scopes)
                script.run(order["remove_effect"])
                script.run(order["cancel_effect"])
                self.assertEqual(script.scopes, delivered)

    def test_cancellation_refunds_every_currency_and_old_orders_cannot_refund_new_work(self):
        for name, order in self.orders.items():
            for terminal in ("subject", "capitulation", "war_end"):
                with self.subTest(order=name, terminal=terminal):
                    script = self.campaign()
                    resources = deepcopy(script.scopes["TVA"].resources)
                    self.assertTrue(self.start(script, name))
                    if terminal == "subject":
                        script.scopes["TVA"].subject = "VAD"
                    elif terminal == "capitulation":
                        script.scopes["TVA"].capitulated = True
                    else:
                        script.globals.add(V + "central_war_finished")
                    self.assertTrue(script.conditions(order["cancel_trigger"]))
                    script.run(order["remove_effect"])
                    script.run(order["cancel_effect"])
                    self.assertEqual(script.scopes["TVA"].resources, resources)
        script = self.campaign()
        self.assertTrue(self.start(script, "maintenance"))
        script.run(self.orders["maintenance"]["cancel_effect"])
        self.assertTrue(self.start(script, "cadre_training"))
        paid = deepcopy(script.scopes)
        script.run(self.orders["maintenance"]["cancel_effect"])
        script.run(self.orders["maintenance"]["remove_effect"])
        self.assertEqual(script.scopes, paid)

    def test_emergency_series_rechecks_the_political_and_material_limits(self):
        for field, value in (("TVA_network_load", 75.01), ("TVA_cadre_reserve", 19.99), ("bop", -.1)):
            script = self.campaign()
            resources = deepcopy(script.scopes["TVA"].resources)
            self.assertTrue(self.start(script, "emergency_series"))
            if field == "bop":
                script.scopes["TVA"].power_balances["TVA_bop"] = value
            else:
                script.scopes["TVA"].variables[field] = value
            script.run(self.orders["emergency_series"]["remove_effect"])
            self.assertEqual(script.scopes["TVA"].resources, resources)

    def test_successor_receives_escrow_and_terminal_cleanup_removes_the_wartime_balance(self):
        for name, order in self.orders.items():
            script = self.campaign()
            self.assertTrue(self.start(script, name))
            values = script.scopes["TVA"].variables
            receipt = {key: values["TVA_programme_" + var] for key, var in
                       (("pp", "pp"), ("people", "manpower"), ("support_equipment", "support"))}
            before = deepcopy(script.scopes["WRK"].resources)
            script.effect("TVA_settle_administration_handoff", "WRK")
            script.effect("TVA_settle_administration_handoff", "WRK")
            for resource, amount in receipt.items():
                self.assertEqual(script.scopes["WRK"].resources[resource], before[resource] + amount)
            script.effect("TVA_close_administration")
            script.run(order["remove_effect"])
            self.assertNotIn("TVA_bop", script.scopes["TVA"].power_balances)
            self.assertNotIn("TVA_administration_dynamic", script.scopes["TVA"].flags)
            self.assertNotIn("TVA_programme_pp", values)

    def test_result_windows_are_repeatable_reports_without_second_settlement(self):
        for number in (25, 26):
            event = fields(EVENTS[V + "claimant." + str(number)])
            self.assertNotIn("fire_only_once", event)
            self.assertEqual(set(fields(event["option"])), {"name"})

    def test_retained_cadres_carry_trial_practice_into_the_successor(self):
        for reserve, iterations in product((0, 25, 60, 100), (0, 2, 8, 20)):
            script = self.campaign()
            script.scopes["TVA"].variables.update(TVA_cadre_reserve=reserve)
            script.scopes["TVA"].variables[V + "tva_iterations"] = iterations
            script.effect(V + "pw_record_trial_iterations", "WRK")
            self.assertAlmostEqual(script.scopes["WRK"].variables[V + "pw_iteration_efficiency"],
                                   min(iterations, 8) * .01 * reserve / 100)

    def test_policy_previews_match_the_live_aggregate_after_each_focus_and_programme(self):
        from tools.validators.validate_adiscord_vorkerland_civil_war_focus import TVA_AGGREGATE_PREVIEWS

        focuses = {
            fields(value)["id"]: fields(value)
            for key, _, value in walk(parse(read("focus_trees/Vorkerland/tva/focuses.txt")))
            if key == "focus" and isinstance(value, list)
        }
        ideas = {
            key: fields(value) for key, _, value in walk(parse(read("common/ideas/ADISCORD_vorkerland_ideas.txt")))
            if key in TVA_AGGREGATE_PREVIEWS
        }
        consumer = fields(fields(parse(read("common/dynamic_modifiers/ADISCORD_vorkerland_dynamic_modifiers.txt")))[
            "TVA_administration_dynamic"
        ])
        routes = (
            ("TVA_declare_continuous_mobilization", "TVA_run_the_republic_as_one_process",
             "TVA_doctrine_of_continuous_assault", "TVA_print_unattended_strike_packages"),
            ("TVA_enact_the_preservation_protocol", "TVA_certify_the_surviving_cadre",
             "TVA_doctrine_of_the_measured_front", "TVA_keep_the_interdictors_on_station"),
        )
        visited = set()
        for route in routes:
            script = self.campaign()
            expected = defaultdict(float)
            for focus in route:
                reward = focuses[focus]["completion_reward"]
                preview = fields(fields(reward)["effect_tooltip"])["add_ideas"]
                visited.add(preview)
                for modifier, value in fields(ideas[preview]["modifier"]).items():
                    expected[modifier] += float(value)
                script.run(reward)
                values = script.scopes["TVA"].variables
                for modifier, total in expected.items():
                    self.assertAlmostEqual(values["TVA_policy_" + modifier], total, focus)
                    applied = values[consumer[modifier]]
                    if modifier == "industrial_capacity_factory":
                        total -= max(0, values["TVA_network_load"] - 50) * .002
                    elif modifier == "research_speed_factor":
                        total += (values["TVA_cadre_reserve"] - 50) * .001
                    self.assertAlmostEqual(applied, total, focus)
                self.assertFalse(any(key == "add_ideas" for key, _, _ in walk([
                    item for item in reward if item[0] != "effect_tooltip"
                ])))
            policy = {key: value for key, value in values.items() if key.startswith("TVA_policy_")}
            self.assertTrue(self.start(script, "maintenance"))
            script.run(self.orders["maintenance"]["remove_effect"])
            self.assertEqual(policy, {key: value for key, value in values.items() if key.startswith("TVA_policy_")})
            script.effect("TVA_close_administration")
            self.assertNotIn("TVA_administration_dynamic", script.scopes["TVA"].flags)
        self.assertEqual(visited, TVA_AGGREGATE_PREVIEWS)


class VADDistrictAdministrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        categories = fields(parse(read("common/decisions/ADISCORD_vorkerland_decisions.txt")))
        cls.category = fields(categories[V + "vad_administration"])
        cls.orders = {
            "charter": fields(cls.category[V + "vad_grant_district_charter"]),
            "commandant": fields(cls.category[V + "vad_impose_commandant_rule"]),
        }

    def campaign(self):
        script = Script()
        script.root = "VAD"
        script.source = "75"
        script.globals = {V + "collapse_started", V + "collapse_wars_started",
                          V + "phase_central_preparation"}
        country = script.scopes["VAD"]
        country.resources.update(pp=1000, people=10000, infantry_equipment=6000)
        country.focuses.update({"VAD_open_imperial_registers", "VAD_form_field_commandantures"})
        for site in (75, 106, 107, 121, 102, 109, 111):
            script.scopes[str(site)].owner = "VAD"
            script.scopes[str(site)].controller = "VAD"
        script.effect("VAD_initialize_administration")
        script.calls.clear()
        return script

    def start(self, script, name, target="75"):
        script.source = target
        order = self.orders[name]
        if not all(script.conditions(order[field]) for field in
                   ("visible", "target_trigger", "available", "custom_cost_trigger")):
            return False
        script.run(order["complete_effect"])
        return True

    def assert_released(self, script, target="75"):
        self.assertFalse(any(key.startswith("VAD_oath_") for key in script.scopes["VAD"].variables))
        self.assertNotIn("VAD_oath_in_progress", script.scopes[target].flags)

    def test_price_boundaries_are_exact_and_debited_once(self):
        for name, pp, people in (("charter", 40, 500), ("commandant", 30, 1000)):
            for balance, recruits, expected in ((pp, people, True), (pp - .01, people, False),
                                                (pp, people - .01, False)):
                with self.subTest(name=name, balance=balance, recruits=recruits):
                    script = self.campaign()
                    country = script.scopes["VAD"]
                    country.resources.update(pp=balance, people=recruits)
                    self.assertEqual(self.start(script, name), expected)
                    after = deepcopy(country.resources)
                    script.effect("VAD_begin_" + name)
                    self.assertEqual(country.resources, after)
                    self.assertEqual(country.resources["pp"], balance - pp * expected)
                    self.assertEqual(country.resources["people"], recruits - people * expected)

    def test_one_country_receipt_blocks_other_targets_and_other_orders(self):
        for first, second in product(self.orders, repeat=2):
            with self.subTest(first=first, second=second):
                script = self.campaign()
                self.assertTrue(self.start(script, first))
                before = deepcopy(script.scopes["VAD"])
                self.assertFalse(self.start(script, second, "106"))
                script.effect("VAD_begin_" + second)
                self.assertEqual(script.scopes["VAD"], before)
                self.assertNotIn("VAD_oath_in_progress", script.scopes["106"].flags)

    def test_delivery_applies_one_local_result_and_never_creates_free_troops(self):
        for name, pp, people, suffix, counter, shift in (
            ("charter", 40, 500, "chartered", "charters", .15),
            ("commandant", 30, 1000, "commandant", "commandants", -.15),
        ):
            with self.subTest(name=name):
                script = self.campaign()
                self.assertTrue(self.start(script, name))
                self.assertEqual(self.orders[name]["days_remove"], "30")
                self.assertNotIn(V + "vad_district_oath", script.scopes["75"].flags)
                script.run(self.orders[name]["remove_effect"])
                before = deepcopy(script.scopes)
                script.run(self.orders[name]["remove_effect"])
                self.assertEqual(script.scopes, before)
                self.assert_released(script)
                country = script.scopes["VAD"]
                self.assertEqual((country.resources["pp"], country.resources["people"]),
                                 (1000 - pp, 10000 - people))
                self.assertEqual(country.resources["infantry_equipment"], 6000)
                self.assertEqual(country.variables[V + "vad_" + counter], 1)
                self.assertAlmostEqual(country.power_balances["VAD_bop"], -.15 + shift)
                self.assertIn(V + "vad_" + suffix + "_district", script.scopes["75"].flags)
                self.assertEqual(script.arrays["global." + V + "vad_oath_states"], ["75"])
                self.assertFalse(self.start(script, name))

    def test_charter_capacity_is_three_then_six_and_pending_work_cannot_overbook(self):
        script = self.campaign()
        for target in ("75", "106", "107"):
            self.assertTrue(self.start(script, "charter", target))
            self.assertFalse(self.start(script, "charter", "121"))
            script.source = target
            script.run(self.orders["charter"]["remove_effect"])
        self.assertFalse(self.start(script, "charter", "121"))
        script.scopes["VAD"].focuses.add("VAD_restore_crown_commissions")
        for target in ("121", "102", "109"):
            self.assertTrue(self.start(script, "charter", target))
            script.run(self.orders["charter"]["remove_effect"])
        self.assertFalse(self.start(script, "charter", "111"))
        self.assertEqual(script.scopes["VAD"].variables[V + "vad_charters"], 6)

    def test_loss_before_delivery_refunds_once_and_ignores_a_different_hook_source(self):
        for name, field in product(self.orders, ("owner", "controller")):
            script = self.campaign()
            self.assertTrue(self.start(script, name))
            setattr(script.scopes["75"], field, "TVA")
            script.source = "TVA"
            script.effect("VAD_lose_district_administration", "75")
            self.assert_released(script)
            script.source = "75"
            script.run(self.orders[name]["cancel_effect"])
            script.run(self.orders[name]["remove_effect"])
            self.assertEqual(script.scopes["VAD"].resources["pp"], 1000)
            self.assertEqual(script.scopes["VAD"].resources["people"], 10000)
            self.assertNotIn(V + "vad_district_oath", script.scopes["75"].flags)

    def test_delivery_rechecks_country_and_target_even_without_a_control_callback(self):
        for name, failure in product(self.orders, ("owner", "controller", "capitulated", "subject", "peace")):
            script = self.campaign()
            self.assertTrue(self.start(script, name))
            if failure in ("owner", "controller"):
                setattr(script.scopes["75"], failure, "TVA")
            elif failure == "peace":
                script.globals.add(V + "central_war_finished")
            elif failure == "capitulated":
                script.scopes["VAD"].capitulated = True
            else:
                script.scopes["VAD"].subject = "TVA"
            self.assertTrue(script.conditions(self.orders[name]["cancel_trigger"]))
            script.run(self.orders[name]["remove_effect"])
            self.assert_released(script)
            self.assertEqual(script.scopes["VAD"].resources["pp"], 1000)
            self.assertEqual(script.scopes["VAD"].resources["people"], 10000)

    def test_lost_completed_district_can_be_rebuilt_for_its_full_price(self):
        for name, counter, pp, people in (("charter", "charters", 40, 500),
                                         ("commandant", "commandants", 30, 1000)):
            script = self.campaign()
            self.assertTrue(self.start(script, name))
            script.run(self.orders[name]["remove_effect"])
            script.scopes["75"].controller = "TVA"
            for _ in range(2):
                script.effect("VAD_lose_district_administration", "75")
            self.assertEqual(script.scopes["VAD"].variables[V + "vad_" + counter], 0)
            self.assertFalse(script.scopes["75"].flags)
            self.assertFalse(script.arrays["global." + V + "vad_oath_states"])
            script.scopes["75"].controller = "VAD"
            self.assertTrue(self.start(script, name))
            script.run(self.orders[name]["remove_effect"])
            self.assertEqual(script.scopes["VAD"].variables[V + "vad_" + counter], 1)
            self.assertEqual(script.scopes["VAD"].resources["pp"], 1000 - 2 * pp)
            self.assertEqual(script.scopes["VAD"].resources["people"], 10000 - 2 * people)

    def test_old_target_callbacks_cannot_refund_or_complete_a_new_order(self):
        for first, second in product(self.orders, repeat=2):
            script = self.campaign()
            self.assertTrue(self.start(script, first))
            script.scopes["75"].controller = "TVA"
            script.effect("VAD_lose_district_administration", "75")
            self.assertTrue(self.start(script, second, "106"))
            before = deepcopy(script.scopes)
            script.source = "75"
            script.run(self.orders[first]["cancel_effect"])
            script.run(self.orders[first]["remove_effect"])
            self.assertEqual(script.scopes, before)

    def test_handoff_refunds_the_receipt_to_the_living_successor_only_once(self):
        for name, pp, people in (("charter", 40, 500), ("commandant", 30, 1000)):
            for successor in ("WRK", "WKR", "TVA"):
                script = self.campaign()
                self.assertTrue(self.start(script, name))
                before = deepcopy(script.scopes[successor].resources)
                script.root = successor
                script.source = "VAD"
                script.effect("VAD_settle_oath_handoff")
                script.effect("VAD_settle_oath_handoff")
                script.effect("VAD_close_administration", "VAD")
                self.assert_released(script)
                self.assertEqual(script.scopes[successor].resources["pp"], before["pp"] + pp)
                self.assertEqual(script.scopes[successor].resources["people"], before["people"] + people)
                self.assertEqual(script.scopes["VAD"].resources["pp"], 1000 - pp)
                self.assertEqual(script.scopes["VAD"].resources["people"], 10000 - people)
                self.assertNotIn("VAD_bop", script.scopes["VAD"].power_balances)

    def test_reopening_preserves_balance_and_paid_work_in_the_current_campaign(self):
        script = self.campaign()
        self.assertTrue(self.start(script, "charter"))
        script.scopes["VAD"].power_balances["VAD_bop"] = .65
        before = deepcopy(script.scopes)
        script = deepcopy(script)
        script.effect("VAD_initialize_administration")
        self.assertEqual(script.scopes, before)
        script.effect("VAD_close_administration")
        self.assert_released(script)
        script.effect("VAD_initialize_administration")
        self.assertNotIn("VAD_bop", script.scopes["VAD"].power_balances)

    def test_retirement_removes_local_modifiers_but_retains_the_settlement_record(self):
        script = self.campaign()
        for name, target in (("charter", "75"), ("commandant", "106")):
            self.assertTrue(self.start(script, name, target))
            script.run(self.orders[name]["remove_effect"])
        self.assertTrue(self.start(script, "charter", "107"))
        script.effect("VAD_close_administration")
        script.effect(V + "vad_retire_district_oaths")
        self.assert_released(script, "107")
        for target in ("75", "106"):
            self.assertFalse(script.scopes[target].flags)
        self.assertFalse(script.arrays["global." + V + "vad_oath_states"])
        for counter in ("charters", "commandants"):
            self.assertEqual(script.scopes["VAD"].variables[V + "vad_" + counter], 1)


class VADPoliticalMandateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.schedule = ClaimantPreparationScheduleTests()
        cls.schedule.setUpClass()
        cls.entries = ("VAD_open_imperial_registers", "VAD_form_field_commandantures")
        cls.debug = next(fields(value) for key, _, value in walk(parse(read(
            "common/decisions/ADISCORD_scenario_debug_decisions.txt")))
            if isinstance(value, list)
            and any(item == (V + "form_joint_government", "=", "yes") for item in walk(value))
            and "available" in fields(value))

    def campaign(self, rescued=True):
        script = self.schedule.campaign("VAD", "joint" if rescued else "imperial")
        country = script.scopes["VAD"]
        country.leader_ideology = "imperial_restorationism"
        country.cosmetic = "VAD_vorkerland_restoration"
        if rescued:
            country.character_roles["WRK_Nikita_Worcker"] = {"neo_vorkerism"}
        else:
            country.character_roles.pop("WRK_VAD_Joint_Council")
        return script

    def complete(self, script, name):
        self.assertTrue(self.schedule.eligible(script, name), name)
        # Execute before adding the focus to completed history: the reward
        # must not depend on the native completion-marker evaluation order.
        script.run(fields(self.schedule.focuses[name])["completion_reward"])
        script.scopes["VAD"].focuses.add(name)

    def test_rescue_does_not_select_a_government_and_both_entries_remain_visible(self):
        opening = fields(EVENTS[V + "collapse.1"])["immediate"]
        self.assertFalse(any(key == V + "form_joint_government" for key, _, _ in walk(opening)))
        for rescued in (False, True):
            script = self.campaign(rescued)
            self.complete(script, "VAD_proclaim_joint_charter")
            self.assertEqual(script.scopes["VAD"].leader, "WRK_Vlad_Petrichev")
            self.assertNotIn(V + "joint_government_formed", script.globals)
            for entry in self.entries:
                self.assertTrue(script.conditions(fields(self.schedule.focuses[entry])["allow_branch"]))
            self.assertTrue(self.schedule.eligible(script, self.entries[0]))
            self.assertEqual(self.schedule.eligible(script, self.entries[1]), rescued)

    def test_imperial_choice_preserves_rescued_nikita_and_blocks_later_council(self):
        script = self.campaign()
        self.complete(script, "VAD_proclaim_joint_charter")
        self.complete(script, self.entries[0])
        country = script.scopes["VAD"]
        self.assertIn("WRK_Nikita_Worcker", country.character_roles)
        self.assertEqual(country.leader, "WRK_Vlad_Petrichev")
        self.assertFalse(self.schedule.eligible(script, self.entries[1]))
        script.root = "WRK"
        self.assertFalse(script.conditions(self.debug["available"]))
        script.effect(V + "form_joint_government")
        self.assertNotIn(V + "joint_government_formed", script.globals)

    def test_joint_choice_installs_council_without_western_claimant_and_runs_once(self):
        script = self.campaign()
        self.complete(script, "VAD_proclaim_joint_charter")
        script.scopes["WKR"].exists = False
        country = script.scopes["VAD"]
        country.variables.update(VAD_oath_pp=30, VAD_oath_manpower=1000, VAD_oath_kind=2)
        receipt = dict(country.variables)
        self.complete(script, self.entries[1])
        self.assertEqual(country.leader, "WRK_VAD_Joint_Council")
        self.assertEqual(country.variables, receipt)
        self.assertIn(V + "joint_government_formed", script.globals)
        self.assertFalse(self.schedule.eligible(script, self.entries[0]))
        self.assertTrue(self.schedule.eligible(script, "VAD_guarantee_worker_committees"))
        refreshes = [(key, current) for key, current, _ in script.calls if key == "mark_focus_tree_layout_dirty"]
        self.assertEqual(refreshes, [("mark_focus_tree_layout_dirty", "VAD")])
        before = deepcopy((country, script.calls, script.globals))
        script.effect(V + "form_joint_government")
        self.assertEqual((country, script.calls, script.globals), before)

    def test_council_guard_requires_root_rescue_and_active_administration(self):
        for missing in ("root", "rescue", "subject", "capitulated", "finished", "absent"):
            with self.subTest(missing=missing):
                script = self.campaign(missing != "rescue")
                country = script.scopes["VAD"]
                if missing != "root":
                    self.complete(script, "VAD_proclaim_joint_charter")
                if missing == "subject":
                    country.subject = "TVA"
                elif missing == "capitulated":
                    country.capitulated = True
                elif missing == "finished":
                    script.globals.add(V + "central_war_finished")
                elif missing == "absent":
                    country.exists = False
                script.effect(V + "form_joint_government")
                self.assertNotIn(V + "joint_government_formed", script.globals)
                self.assertEqual(country.leader, "WRK_Vlad_Petrichev")

    def test_delayed_leader_assertion_expires_with_the_administration(self):
        event = fields(EVENTS[V + "collapse.62"])
        for terminal in (None, "subject", "capitulated", "finished", "absent"):
            with self.subTest(terminal=terminal):
                script = self.campaign()
                self.complete(script, "VAD_proclaim_joint_charter")
                self.complete(script, self.entries[1])
                country = script.scopes["VAD"]
                country.leader = ""
                if terminal == "subject":
                    country.subject = "TVA"
                elif terminal == "capitulated":
                    country.capitulated = True
                elif terminal == "finished":
                    script.globals.add(V + "central_war_finished")
                elif terminal == "absent":
                    country.exists = False
                self.assertEqual(script.conditions(event["trigger"]), terminal is None)
                if script.conditions(event["trigger"]):
                    script.run(event["immediate"])
                    self.assertEqual(country.leader, "WRK_VAD_Joint_Council")

    def test_ai_reaches_choice_by_day_twenty_one_and_honours_player_imperial_course(self):
        for rescued in (False, True):
            script = self.campaign(rescued)
            core = next(plan for name, plan in self.schedule.active_plans(script) if name.endswith("core_plan"))
            route = [name for _, _, name in core["ai_national_focuses"]][:2]
            self.assertEqual(route, ["VAD_proclaim_joint_charter", self.entries[int(rescued)]])
            elapsed = 0
            for name in route:
                self.complete(script, name)
                elapsed += int(fields(self.schedule.focuses[name])["cost"]) * 7
            self.assertEqual(elapsed, 21)
        script = self.campaign()
        self.complete(script, "VAD_proclaim_joint_charter")
        self.complete(script, self.entries[0])
        cores = [name for name, _ in self.schedule.active_plans(script) if name.endswith("core_plan")]
        self.assertEqual(cores, [V + "vad_vlad_core_plan"])

    def test_identity_reassertion_and_reload_preserve_chosen_mandate(self):
        repair = next(item for item in EFFECTS[V + "repair_claimant_identities"]
                      if item[0] == "if" and ("country_exists", "=", "VAD") in fields(item[2])["limit"])
        for entry in self.entries:
            script = self.campaign()
            self.complete(script, "VAD_proclaim_joint_charter")
            self.complete(script, entry)
            expected = deepcopy(script.scopes["VAD"])
            # A serialized in-campaign state keeps flags, history and balances;
            # native save-file parsing is outside this interpreter.
            restored = deepcopy(script)
            restored.scopes["VAD"].leader = ""
            restored.scopes["VAD"].leader_ideology = ""
            restored.run([repair])
            restored.effect("VAD_initialize_administration")
            self.assertEqual(restored.scopes["VAD"], expected)

    def test_handoff_uses_selected_course_not_rescue_and_keeps_nikita(self):
        handoff = EFFECTS[V + "form_wrk_from_vad"]
        transfers = [item for item in handoff if item[0] == "if"
                     and any(key == "set_nationality" for key, _, _ in walk(item[2]))]
        completion = EFFECTS[V + "complete_wrk_from_vad"]
        final = next(i for i, item in enumerate(completion) if item[0] == "if"
                     and ("has_global_flag", "=", V + "joint_government_formed") in fields(item[2])["limit"])
        for entry in self.entries:
            script = self.campaign()
            self.complete(script, "VAD_proclaim_joint_charter")
            self.complete(script, entry)
            expected = script.scopes["VAD"].leader
            script.run(transfers, "WRK")
            self.assertIn(expected, script.scopes["WRK"].character_roles)
            self.assertIn("WRK_Nikita_Worcker", script.scopes["WRK"].character_roles)
            script.run(completion[final:final + 3], "WRK")
            self.assertEqual(script.scopes["WRK"].leader, expected)


class VADCollegialMandateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base = VADPoliticalMandateTests()
        cls.base.setUpClass()

    def campaign(self, outcome="dead"):
        script = self.base.campaign(rescued=outcome == "rescued")
        self.base.complete(script, "VAD_proclaim_joint_charter")
        if outcome == "dead":
            script.globals.add(V + "worker_killed")
        elif outcome == "escaped":
            script.scopes["WKR"].character_roles["WRK_Nikita_Worcker"] = {"neo_vorkerism"}
            script.scopes["WKR"].leader = "WRK_Nikita_Worcker"
        return script

    def test_unrescued_worker_allows_an_actual_petrichev_staff_mandate(self):
        for outcome in ("dead", "escaped"):
            script = self.campaign(outcome)
            country = script.scopes["VAD"]
            country.variables.update(VAD_oath_pp=30, VAD_oath_manpower=1000, VAD_oath_kind=2)
            receipt = {key: value for key, value in country.variables.items() if key.startswith("VAD_oath_")}
            balance = deepcopy(country.power_balances)
            script.effect("VAD_form_collegial_staff")
            self.assertIn(V + "collegial_staff_formed", script.globals)
            self.assertNotIn(V + "joint_government_formed", script.globals)
            self.assertEqual((country.leader, country.leader_ideology), ("WRK_Vlad_Petrichev", "pragmatism_ideology"))
            self.assertEqual(country.cosmetic, "VAD_vorkerland_collegial_staff")
            self.assertNotIn("WRK_Nikita_Worcker", country.character_roles)
            self.assertEqual({key: value for key, value in country.variables.items() if key.startswith("VAD_oath_")}, receipt)
            self.assertEqual(country.power_balances, balance)
            before = deepcopy((script.scopes, script.globals, script.calls))
            script.effect("VAD_form_collegial_staff")
            self.assertEqual((script.scopes, script.globals, script.calls), before)
            if outcome == "escaped":
                self.assertEqual(script.scopes["WKR"].leader, "WRK_Nikita_Worcker")

    def test_staff_formation_cannot_override_a_rescue_or_existing_course(self):
        for reason in ("rescue", "imperial", "joint", "subject", "capitulation", "finished", "root"):
            script = self.campaign("rescued" if reason == "rescue" else "dead")
            country = script.scopes["VAD"]
            if reason == "imperial":
                country.focuses.add("VAD_open_imperial_registers")
            elif reason == "joint":
                script.globals.add(V + "joint_government_formed")
            elif reason == "subject":
                country.subject = "TVA"
            elif reason == "capitulation":
                country.capitulated = True
            elif reason == "finished":
                script.globals.add(V + "central_war_finished")
            elif reason == "root":
                country.focuses.discard("VAD_proclaim_joint_charter")
            before = deepcopy((script.scopes, script.globals, script.calls))
            script.effect("VAD_form_collegial_staff")
            self.assertEqual((script.scopes, script.globals, script.calls), before)

    def test_staff_mode_blocks_both_other_core_courses_after_selection(self):
        script = self.campaign()
        script.effect("VAD_form_collegial_staff")
        self.assertFalse(script.conditions(TRIGGERS["VAD_imperial_core_course"]))
        self.assertFalse(script.conditions(TRIGGERS["VAD_joint_core_course"]))
        self.assertTrue(script.conditions(TRIGGERS["VAD_collegial_core_course"]))

    def test_bounded_identity_repair_preserves_the_staff_role_and_local_receipt(self):
        script = self.campaign()
        script.effect("VAD_form_collegial_staff")
        country = script.scopes["VAD"]
        country.variables.update(VAD_oath_pp=25, VAD_oath_support=60, VAD_oath_manpower=500)
        expected = deepcopy(country)
        repair = next(item for item in EFFECTS[V + "repair_claimant_identities"]
                      if item[0] == "if" and any(key == "VAD" for key, _, _ in item[2]))
        country.leader = ""
        country.leader_ideology = ""
        script.run([repair])
        self.assertEqual(country, expected)

    def test_successor_keeps_petrichev_staff_role_and_the_exact_mandate_values(self):
        script = self.campaign()
        script.effect("VAD_form_collegial_staff")
        country = script.scopes["VAD"]
        mandate = {"VAD_staff_planning": .10, "VAD_staff_recovery": .03,
                   "VAD_staff_reinforce": 0, "VAD_staff_speed": 0,
                   "VAD_staff_supply": 0, "VAD_staff_authority": -.05,
                   "VAD_staff_stability": 0, "VAD_staff_command": 0}
        country.variables.update(mandate)
        handoff = EFFECTS[V + "form_wrk_from_vad"]
        actions = [item for item in handoff if item[0] == "VAD_transfer_collegial_mandate"
                   or item[0] == "if" and any(key == "set_nationality" for key, _, _ in walk(item[2]))]
        script.run(actions, "WRK")
        target = script.scopes["WRK"]
        self.assertEqual({key: target.variables.get(key) for key in mandate}, mandate)
        self.assertIn("pragmatism_ideology", target.character_roles["WRK_Vlad_Petrichev"])
        completion = EFFECTS[V + "complete_wrk_from_vad"]
        start = next(i for i, item in enumerate(completion) if item[0] == "if"
                     and ("has_global_flag", "=", V + "joint_government_formed") in fields(item[2])["limit"])
        script.run(completion[start:start + 3], "WRK")
        self.assertEqual((target.leader, target.leader_ideology), ("WRK_Vlad_Petrichev", "pragmatism_ideology"))
        self.assertEqual(target.cosmetic, "VAD_vorkerland_collegial_staff")
        target.flags.add(V + "route_joint")
        target.focuses.add("WRK_joint_restore_unity_tower")
        script.globals.update({V + "collapse_finished", V + "reunification_verified"})
        self.assertFalse(script.conditions(TRIGGERS[V + "petrichev_empire_can_form"], "WRK"))
        self.assertFalse(script.conditions(TRIGGERS[V + "world_empire_can_form"], "WRK"))

    def test_both_staff_policies_rejoin_readiness_with_exact_aggregate_previews(self):
        options = {
            "VAD_require_collective_directives": {"planning_speed": .10, "army_org_regain": .03, "political_power_gain": -.05},
            "VAD_delegate_to_front_commands": {"land_reinforce_rate": .03, "army_speed_factor": .05, "supply_consumption_factor": .03},
        }
        modifiers = fields(parse(read("common/dynamic_modifiers/ADISCORD_vorkerland_dynamic_modifiers.txt")))
        ideas = fields(fields(parse(read("common/ideas/ADISCORD_vorkerland_ideas.txt")))["ideas"])
        for policy, expected in options.items():
            script = self.campaign()
            self.base.complete(script, "VAD_convene_collegial_staff")
            self.base.complete(script, policy)
            self.base.complete(script, "VAD_codify_staff_mandate")
            country = script.scopes["VAD"]
            other = next(name for name in options if name != policy)
            self.assertFalse(self.base.schedule.eligible(script, other))
            self.assertTrue(self.base.schedule.eligible(script, "VAD_settle_restoration_authority"))
            self.assertIn("VAD_collegial_staff_dynamic", country.flags)
            dynamic = fields(modifiers["VAD_collegial_staff_dynamic"])
            actual = {key: country.variables.get(variable, 0) for key, variable in dynamic.items()
                      if isinstance(variable, str) and variable.startswith("VAD_staff_") and country.variables.get(variable, 0)}
            self.assertEqual(actual, expected)
            dummy = "VAD_staff_collective_delta" if policy.endswith("collective_directives") else "VAD_staff_delegation_delta"
            preview = fields(fields(fields(ideas["country"])[dummy])["modifier"])
            self.assertEqual({key: float(value) for key, value in preview.items()}, expected)
            self.assertNotIn(dummy, country.flags)


    def test_successor_aggregate_survives_without_departed_tree_focus_history(self):
        for policy in ("VAD_require_collective_directives", "VAD_delegate_to_front_commands"):
            script = self.campaign()
            self.base.complete(script, "VAD_convene_collegial_staff")
            self.base.complete(script, policy)
            self.base.complete(script, "VAD_codify_staff_mandate")
            mandate = {key: value for key, value in script.scopes["VAD"].variables.items()
                       if key.startswith("VAD_staff_")}
            handoff = EFFECTS[V + "form_wrk_from_vad"]
            actions = [item for item in handoff if item[0] == "VAD_transfer_collegial_mandate"
                       or item[0] == "if" and any(key == "set_nationality" for key, _, _ in walk(item[2]))]
            script.run(actions, "WRK")
            script.effect("VAD_close_administration", "VAD")
            target = script.scopes["WRK"]
            target.flags.add(V + "route_joint")
            # Ordinary IDs absent from the destination tree are not copied by load_focus_tree.
            target.focuses.clear()
            completion = EFFECTS[V + "complete_wrk_from_vad"]
            start = next(i for i, item in enumerate(completion) if item[0] == "if"
                         and ("has_global_flag", "=", V + "joint_government_formed") in fields(item[2])["limit"])
            script.run(completion[start:start + 3], "WRK")
            self.assertEqual({key: target.variables.get(key) for key in mandate}, mandate)
            self.assertIn("VAD_collegial_staff_dynamic", target.flags)
            self.assertNotIn("VAD_collegial_staff_dynamic", script.scopes["VAD"].flags)
            self.assertEqual(target.leader_ideology, "pragmatism_ideology")

    def test_ai_takeover_reaches_readiness_without_reversing_either_staff_policy(self):
        for policy in ("VAD_require_collective_directives", "VAD_delegate_to_front_commands"):
            script = self.campaign()
            self.base.complete(script, "VAD_convene_collegial_staff")
            self.base.complete(script, policy)
            country = script.scopes["VAD"]
            route = []
            while V + "focus_vad_central_war_unlocked" not in country.flags:
                self.assertLess(len(route), 20, route)
                plans = self.base.schedule.active_plans(script)
                core = [(name, plan) for name, plan in plans if name.endswith("_core_plan")]
                self.assertEqual([name for name, _ in core], [V + "vad_collegial_core_plan"])
                focus = next((value for _, _, value in core[0][1]["ai_national_focuses"]
                              if self.base.schedule.eligible(script, value)), None)
                self.assertIsNotNone(focus, route)
                if focus == "VAD_codify_staff_mandate":
                    self.base.complete(script, focus)
                else:
                    self.base.schedule.complete(script, focus)
                route.append(focus)
            self.assertIn(policy, country.focuses)
            self.assertNotIn("VAD_open_imperial_registers", country.focuses)
            self.assertNotIn("VAD_form_field_commandantures", country.focuses)
            active = [name for name, _ in self.base.schedule.active_plans(script)]
            self.assertNotIn(V + "vad_vlad_depth_plan", active)

    def test_formation_news_is_once_only_and_the_constitution_cannot_be_announced_by_another_cabinet(self):
        script = self.campaign()
        script.effect("VAD_form_collegial_staff")
        script.effect("VAD_form_collegial_staff")
        news = [fields(value)["id"] for key, _, value in script.calls if key == "news_event"]
        self.assertEqual(news, [V + "story.48"])
        target = script.scopes["WRK"]
        target.focuses.add("WRK_joint_restore_unity_tower")
        before = deepcopy((script.scopes, script.calls))
        script.effect("VAD_ratify_staff_constitution", "WRK")
        self.assertEqual((script.scopes, script.calls), before)

    def test_postwar_reconstruction_preserves_staff_and_cannot_unlock_the_empire(self):
        from tools.validators.validate_adiscord_vorkerland_civil_war_focus import focus_blocks
        blocks = focus_blocks(read("focus_trees/Vorkerland/joint_postwar/focuses.txt"))
        script = self.campaign()
        self.base.complete(script, "VAD_convene_collegial_staff")
        self.base.complete(script, "VAD_require_collective_directives")
        self.base.complete(script, "VAD_codify_staff_mandate")
        target = deepcopy(script.scopes["VAD"])
        script.scopes["WRK"] = target
        script.root = "WRK"
        target.flags.add(V + "route_joint")
        script.globals.add(V + "phase_postwar_integration")
        for name in ("WRK_joint_issue_integration_warrants", "WRK_joint_impose_reunification_settlement", "WRK_joint_restore_unity_tower"):
            reward = fields(fields(parse(blocks[name]))["focus"])["completion_reward"]
            # Execute the political consequences independently of unrelated reconstruction.
            script.run([item for item in reward if item[0] in {"if", "else_if", "else", "hidden_effect"}], "WRK")
            target.focuses.add(name)
        self.assertNotIn(V + "vad_imperial_reclamation_unlocked", target.flags)
        self.assertEqual(target.cosmetic, "VAD_vorkerland_collegial_staff")
        self.assertFalse(script.conditions(TRIGGERS[V + "petrichev_empire_can_form"], "WRK"))
        finale = fields(fields(parse(blocks["WRK_joint_ratify_staff_constitution"]))["focus"])
        self.assertTrue(script.conditions(finale["allow_branch"], "WRK"))
        self.assertTrue(script.conditions(finale["available"], "WRK"))
        script.run(finale["completion_reward"], "WRK")
        target.focuses.add("WRK_joint_ratify_staff_constitution")
        self.assertEqual(target.cosmetic, "VAD_vorkerland_staff_republic")
        self.assertEqual(target.variables["VAD_staff_stability"], .05)
        self.assertEqual(target.variables["VAD_staff_command"], .10)
        self.assertEqual(target.variables["VAD_staff_planning"], .10)
        script.effect("VAD_appoint_collegial_staff", "WRK")
        self.assertEqual(target.cosmetic, "VAD_vorkerland_staff_republic")


class VADCollegialProgrammeTests(unittest.TestCase):
    programmes = {
        "rotation": (8, "VAD_require_collective_directives", 500, 60, "VAD_staff_rotated_garrison"),
        "depot": (9, "VAD_delegate_to_front_commands", 0, 100, "VAD_staff_field_depot"),
    }

    @classmethod
    def setUpClass(cls):
        cls.base = VADDistrictAdministrationTests()
        cls.base.setUpClass()
        cls.orders = {kind: fields(cls.base.category["VAD_staff_" + kind + "_programme"])
                      for kind in cls.programmes}

    def campaign(self, kind):
        script = self.base.campaign()
        country = script.scopes["VAD"]
        country.focuses.discard("VAD_form_field_commandantures")
        country.focuses.discard("VAD_open_imperial_registers")
        country.focuses.update({"VAD_proclaim_joint_charter", "VAD_convene_collegial_staff", self.programmes[kind][1]})
        script.effect("VAD_form_collegial_staff")
        self.assertTrue(self.base.start(script, "commandant", "75"))
        script.run(self.base.orders["commandant"]["remove_effect"])
        country.resources.update(pp=1000, people=10000, support_equipment=500)
        script.calls.clear()
        return script

    def start(self, script, kind, target="75"):
        script.source = target
        order = self.orders[kind]
        if not all(script.conditions(order[key]) for key in ("visible", "target_trigger", "available", "custom_cost_trigger")):
            return False
        script.run(order["complete_effect"])
        return True

    def test_staff_programmes_reserve_exact_prices_and_the_shared_district_slot(self):
        for kind, (receipt, _, people, support, _) in self.programmes.items():
            for scarce in (None, "pp", "support_equipment", *(('people',) if people else ())):
                script = self.campaign(kind)
                country = script.scopes["VAD"]
                country.resources.update(pp=25, people=people, support_equipment=support)
                if scarce:
                    country.resources[scarce] -= .01
                before = deepcopy(country.resources)
                self.assertEqual(self.start(script, kind), scarce is None)
                if scarce:
                    self.assertEqual(country.resources, before)
                    continue
                self.assertEqual(country.variables["VAD_oath_kind"], receipt)
                self.assertEqual(country.variables["VAD_oath_state"], 75)
                self.assertIn("VAD_oath_in_progress", script.scopes["75"].flags)
                self.assertEqual((country.resources["pp"], country.resources["people"], country.resources["support_equipment"]), (0, 0, 0))
                self.assertFalse(self.base.start(script, "charter", "106"))
                self.assertFalse(self.start(script, kind))
                self.assertEqual(self.orders[kind]["days_remove"], "21")

    def test_rotation_and_depot_have_distinct_delivered_local_consequences(self):
        for kind, initial, expected in (("rotation", 100, 70), ("depot", 90, 100)):
            script = self.campaign(kind)
            district = script.scopes["75"]
            district.variables["VAD_district_unrest"] = initial
            if kind == "rotation":
                district.flags.add(V + "vad_district_uprising")
            self.assertTrue(self.start(script, kind))
            script.run(self.orders[kind]["remove_effect"])
            self.assertEqual(district.variables["VAD_district_unrest"], expected)
            self.assertEqual(V + "vad_district_uprising" in district.flags, kind == "depot")
            self.assertIn(self.programmes[kind][4], district.flags)
            self.base.assert_released(script)
            self.assertFalse(self.start(script, kind))
            before = deepcopy((script.scopes, script.calls))
            script.run(self.orders[kind]["remove_effect"])
            script.run(self.orders[kind]["cancel_effect"])
            self.assertEqual((script.scopes, script.calls), before)

    def test_target_and_kind_guards_reject_unrelated_callbacks(self):
        for kind in self.programmes:
            script = self.campaign(kind)
            self.assertTrue(self.start(script, kind))
            before = deepcopy(script.scopes)
            script.source = "106"
            script.run(self.orders[kind]["remove_effect"])
            script.run(self.orders[kind]["cancel_effect"])
            self.assertEqual(script.scopes, before)
            script.source = "75"
            other = "depot" if kind == "rotation" else "rotation"
            script.run(self.orders[other]["remove_effect"])
            script.run(self.orders[other]["cancel_effect"])
            self.assertEqual(script.scopes, before)

    def test_loss_and_terminal_context_refund_the_exact_receipt_once(self):
        for kind, reason in product(self.programmes, ("control", "institution", "leader", "subject", "capitulation", "end")):
            script = self.campaign(kind)
            country = script.scopes["VAD"]
            before = deepcopy(country.resources)
            self.assertTrue(self.start(script, kind))
            if reason == "control":
                script.scopes["75"].controller = "TVA"
            elif reason == "institution":
                script.scopes["75"].flags.discard(V + "vad_commandant_district")
            elif reason == "leader":
                country.leader = "WRK_VAD_Joint_Council"
            elif reason == "subject":
                country.subject = "TVA"
            elif reason == "capitulation":
                country.capitulated = True
            else:
                script.globals.add(V + "central_war_finished")
            self.assertTrue(script.conditions(self.orders[kind]["cancel_trigger"]))
            script.run(self.orders[kind]["remove_effect"])
            script.run(self.orders[kind]["cancel_effect"])
            self.assertEqual(country.resources, before)
            self.base.assert_released(script)

    def test_successor_refund_and_institution_cleanup_do_not_leave_local_bonuses(self):
        for kind, (_, _, people, support, modifier) in self.programmes.items():
            script = self.campaign(kind)
            self.assertTrue(self.start(script, kind))
            target = script.scopes["WRK"]
            before = deepcopy(target.resources)
            script.effect("VAD_settle_oath_handoff", "WRK")
            script.effect("VAD_settle_oath_handoff", "WRK")
            self.assertEqual(target.resources["pp"], before["pp"] + 25)
            self.assertEqual(target.resources["people"], before["people"] + people)
            self.assertEqual(target.resources["support_equipment"], before["support_equipment"] + support)
            script.run(self.orders[kind]["remove_effect"])
            self.assertNotIn(modifier, script.scopes["75"].flags)
            self.assertTrue(self.start(script, kind))
            script.run(self.orders[kind]["remove_effect"])
            script.effect("VAD_remove_district_administration", "75")
            self.assertNotIn(modifier, script.scopes["75"].flags)


class WKRPoliticalMandateTests(unittest.TestCase):
    """Exercise authored political effects; native BOP callbacks are explicit boundaries."""

    def campaign(self, fate="safe_with_loyalists"):
        script = Script()
        script.root = "WKR"
        script.globals = {V + "collapse_wars_started", V + "phase_central_preparation", V + "worker_" + fate}
        script.scopes["WRK"].character_roles = {
            "WRK_Nikita_Worcker": set(), "WRK_Anton_Bagley": set(), "WRK_VAD_Joint_Council": set(),
        }
        country = script.scopes["WKR"]
        country.character_roles["WKR_Emergency_Coordination_Committee"] = {"neo_vorkerism"}
        script.effect(V + "prepare_claimant_characters")
        script.effect("WKR_appoint_chairman" if fate == "safe_with_loyalists" else "WKR_appoint_executive")
        script.effect("WKR_initialize_administration")
        return script

    def select(self, script, suffix):
        option = next(fields(value) for key, _, value in EVENTS[V + "claimant.1"]
                      if key == "option" and fields(value)["name"].endswith("." + suffix))
        if not script.conditions(option["trigger"]):
            return False
        script.run([item for item in next(value for key, _, value in EVENTS[V + "claimant.1"]
                                          if key == "option" and fields(value)["name"] == option["name"])
                    if item[0] not in ("name", "trigger", "ai_chance")])
        self.resolve(script)
        return True

    def resolve(self, script):
        # Invoke the source range callback and then the source event's immediate
        # payload. The native event queue and leader-cache timing are not modeled.
        bop = fields(parse(read("common/bop/WRK.txt")))["WKR_bop"]
        country = script.scopes["WKR"]
        balance = country.power_balances.get("WKR_bop", 0)
        for key, _, value in walk(bop):
            if key != "range":
                continue
            data = fields(value)
            if float(data["min"]) <= balance <= float(data["max"]):
                script.run(data["on_activate"])
        calls = list(script.calls)
        script.calls.clear()
        for key, current, data in calls:
            if key == "country_event" and fields(data)["id"] in (V + "claimant.5", V + "claimant.6"):
                event = fields(EVENTS[fields(data)["id"]])
                if script.conditions(event["trigger"], current):
                    script.run(event["immediate"], current)

    def test_all_fates_allow_both_courses_without_reviving_or_stealing_nikita(self):
        for fate, option in product(("safe_with_loyalists", "rescued_by_vlad", "killed", "missing"), ("a", "b")):
            with self.subTest(fate=fate, option=option):
                script = self.campaign(fate)
                globals_before = set(script.globals)
                self.assertTrue(self.select(script, option))
                country = script.scopes["WKR"]
                expected = "WRK_Anton_Bagley" if option == "b" else (
                    "WRK_Nikita_Worcker" if fate == "safe_with_loyalists" else "WKR_Emergency_Coordination_Committee")
                self.assertEqual(country.leader, expected)
                self.assertEqual(script.globals, globals_before)
                self.assertTrue(script.conditions(TRIGGERS["WKR_executive_course" if option == "b" else "WKR_presidential_course"]))
                if fate == "rescued_by_vlad":
                    self.assertIn("WRK_Nikita_Worcker", script.scopes["VAD"].character_roles)
                    self.assertNotIn("WRK_Nikita_Worcker", country.character_roles)

    def test_initialize_once_and_open_without_any_focus_by_day_seven(self):
        for fate, initial in (("safe_with_loyalists", -.3), ("missing", .3)):
            script = self.campaign(fate)
            country = script.scopes["WKR"]
            self.assertEqual(country.power_balances["WKR_bop"], initial)
            opening = [fields(value) for key, _, value in script.calls
                       if key == "country_event" and fields(value)["id"] == V + "claimant.1"]
            self.assertEqual(len(opening), 1)
            self.assertEqual(int(opening[0]["days"]), 7)
            self.assertEqual(int(fields(EVENTS[V + "claimant.1"])["timeout_days"]) + int(opening[0]["days"]), 21)
            country.power_balances["WKR_bop"] = .77
            script.effect("WKR_initialize_administration")
            self.assertEqual(country.power_balances["WKR_bop"], .77)
            self.assertEqual(len([key for key, _, value in script.calls if key == "country_event"]), 1)

    def test_exact_majorities_change_leadership_only_before_the_mandate(self):
        for value, changed in ((.599999, False), (.60, True), (1, True)):
            script = self.campaign()
            script.scopes["WKR"].power_balances["WKR_bop"] = value
            self.resolve(script)
            self.assertEqual(script.scopes["WKR"].leader == "WRK_Anton_Bagley", changed)
        for value, changed in ((-.599999, False), (-.60, True), (-1, True)):
            script = self.campaign("missing")
            script.scopes["WKR"].power_balances["WKR_bop"] = value
            self.resolve(script)
            self.assertEqual(script.scopes["WKR"].leader == "WKR_Emergency_Coordination_Committee", changed)
        for focus, suffix in (("WKR_convene_front_soviets", "a"), ("WKR_empower_front_executive", "b")):
            script = self.campaign()
            self.select(script, suffix)
            country = script.scopes["WKR"]
            country.focuses.add(focus)
            incumbent = country.leader
            country.power_balances["WKR_bop"] *= -1
            self.resolve(script)
            self.assertEqual(country.leader, incumbent)
            self.assertFalse(self.select(script, "a"))
            self.assertFalse(self.select(script, "b"))
            self.assertTrue(self.select(script, "c"))

    def test_open_event_closes_safely_after_campaign_end_or_subjugation(self):
        for terminal in ("capitulated", "subject", "finished"):
            script = self.campaign()
            country = script.scopes["WKR"]
            if terminal == "finished":
                script.globals.add(V + "central_war_finished")
            elif terminal == "subject":
                country.subject = "VAD"
            else:
                country.capitulated = True
            before = country.leader, dict(country.power_balances)
            self.assertFalse(self.select(script, "a"))
            self.assertFalse(self.select(script, "b"))
            self.assertTrue(self.select(script, "c"))
            self.assertEqual((country.leader, country.power_balances), before)

    def test_handoff_preserves_actual_course_after_leader_cache_is_cleared(self):
        handoff = EFFECTS[V + "form_wrk_from_wkr"]
        choice = next(item for item in handoff if item[0] == "if"
                      and any(key == "WKR_executive_course" for key, _, _ in walk(item[2])))
        index = handoff.index(choice)
        completion = EFFECTS[V + "complete_wrk_from_wkr"]
        final = next(i for i, item in enumerate(completion) if item[0] == "if"
                     and any(key == "has_country_flag" and value == V + "worker_utilitarian_outcome"
                             for key, _, value in walk(item[2])))
        for fate, suffix in product(("safe_with_loyalists", "rescued_by_vlad", "killed", "missing"), ("a", "b")):
            with self.subTest(fate=fate, suffix=suffix):
                script = self.campaign(fate)
                self.select(script, suffix)
                expected = script.scopes["WKR"].leader
                script.run(handoff[index:index + 2], "WRK")
                self.assertEqual(script.scopes["WKR"].leader, "")
                self.assertIn(expected, script.scopes["WRK"].character_roles)
                script.run(completion[final:final + 3], "WRK")
                self.assertEqual(script.scopes["WRK"].leader, expected)
                self.assertEqual(script.scopes["WRK"].government, "utilitarism" if suffix == "b" else "pragmatism")

    def test_leadership_change_preserves_paid_factory_order(self):
        factory = WKRCouncilFormationTests()
        factory.setUpClass()
        for fate in ("safe_with_loyalists", "missing"):
            script = self.campaign(fate)
            country = script.scopes["WKR"]
            country.resources.update(pp=100, people=10000, infantry_equipment=10000)
            country.focuses.add("WKR_organize_factory_battalions")
            country.variables[V + "wkr_councils"] = 2
            capital = script.scopes["capital_WKR"]
            capital.owner = capital.controller = "WKR"
            script.effect(V + "wkr_refresh_councils")
            self.assertTrue(factory.start(script, 1))
            receipt = dict(country.variables)
            self.select(script, "b" if fate == "safe_with_loyalists" else "a")
            self.assertEqual(country.variables, receipt)
            script.run(factory.orders[1]["remove_effect"])
            self.assertEqual(len([call for call in script.calls if call[0] == "create_unit"]), 1)
            factory.assert_receipt_closed(script)

    def test_ai_commits_either_mandate_in_twenty_one_days_and_keeps_both_lines_visible(self):
        schedule = ClaimantPreparationScheduleTests()
        schedule.setUpClass()
        entries = {"a": "WKR_convene_front_soviets", "b": "WKR_empower_front_executive"}
        for fate, suffix in product(("safe_with_loyalists", "missing"), ("a", "b")):
            script = self.campaign(fate)
            self.select(script, suffix)
            country = script.scopes["WKR"]
            for entry in entries.values():
                self.assertTrue(script.conditions(fields(schedule.focuses[entry])["allow_branch"]))
            core = next(plan for name, plan in schedule.active_plans(script) if name.endswith("core_plan"))
            route = [name for _, _, name in core["ai_national_focuses"]][:2]
            self.assertEqual(route, ["WKR_affirm_worker_mandate", entries[suffix]])
            elapsed = 0
            for name in route:
                self.assertTrue(schedule.eligible(script, name), name)
                elapsed += int(fields(schedule.focuses[name])["cost"]) * 7
                schedule.complete(script, name)
            self.assertEqual(elapsed, 21)
            self.assertFalse(script.conditions(TRIGGERS["WKR_mandate_open"]))
            self.assertFalse(schedule.eligible(script, entries["b" if suffix == "a" else "a"]))
        for name, raw in schedule.focuses.items():
            if name.startswith("WKR_"):
                keys = {key for key, _, _ in walk(fields(raw)["allow_branch"])}
                self.assertFalse(keys & {"WKR_presidential_course", "WKR_executive_course"}, name)

    def test_initial_identity_reassertion_cannot_overwrite_chosen_course(self):
        repair = EFFECTS[V + "repair_claimant_identities"][0]
        for fate, suffix in (("safe_with_loyalists", "b"), ("missing", "a")):
            script = self.campaign(fate)
            self.select(script, suffix)
            country = script.scopes["WKR"]
            before = country.leader, country.government, dict(country.power_balances)
            script.run([repair])
            self.assertEqual((country.leader, country.government, country.power_balances), before)
            country.leader = ""
            country.leader_ideology = ""
            script.run([repair])
            self.assertEqual((country.leader, country.government, country.power_balances), before)
            identity = TRIGGERS[V + "claimant_identities_materialized"][0]
            self.assertTrue(script.conditions([identity]))

    def test_close_removes_balance_after_refund_and_cannot_reinitialize_it(self):
        script = self.campaign()
        country = script.scopes["WKR"]
        script.effect("WKR_close_administration")
        self.assertNotIn("WKR_bop", country.power_balances)
        script.effect("WKR_initialize_administration")
        self.assertNotIn("WKR_bop", country.power_balances)
        close = [key for key, _, _ in EFFECTS["WKR_close_administration"]]
        self.assertEqual(close[0], "WKR_close_council_orders")

    def test_first_available_timeout_option_still_has_a_valid_course(self):
        for fate in ("safe_with_loyalists", "rescued_by_vlad", "killed", "missing"):
            script = self.campaign(fate)
            options = [fields(value) for key, _, value in EVENTS[V + "claimant.1"] if key == "option"]
            first = next(option for option in options if script.conditions(option["trigger"]))
            self.assertEqual(first["name"], V + "claimant.1.a")
            self.assertTrue(self.select(script, "a"))
            self.assertTrue(script.conditions(TRIGGERS["WKR_presidential_course"]))


class WKRCouncilFormationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        categories = fields(parse(read("common/decisions/ADISCORD_vorkerland_decisions.txt")))
        cls.category = fields(categories[V + "wkr_administration"])
        cls.orders = {
            1: fields(cls.category[V + "wkr_mobilize_council"]),
            2: fields(cls.category["WKR_mobilize_factory_columns"]),
        }

    def campaign(self, seats=5):
        script = Script()
        script.root = "WKR"
        script.globals = {V + "collapse_started", V + "collapse_wars_started",
                          V + "phase_central_preparation"}
        country = script.scopes["WKR"]
        country.focuses.update({"WKR_organize_factory_battalions", "WKR_requisition_in_the_republics_name"})
        country.resources.update(pp=200, people=20000, infantry_equipment=20000)
        country.variables[V + "wkr_councils"] = seats
        capital = script.scopes["capital_WKR"]
        capital.owner = capital.controller = "WKR"
        script.effect(V + "wkr_refresh_councils")
        script.calls.clear()
        return script

    def start(self, script, count):
        order = self.orders[count]
        if not all(script.conditions(order[key]) for key in ("visible", "available", "custom_cost_trigger")):
            return False
        script.run(order["complete_effect"])
        return True

    def assert_receipt_closed(self, script):
        self.assertFalse(any(key.startswith("WKR_council_order_") for key in script.scopes["WKR"].variables))

    def test_price_matches_the_actual_three_battalion_template(self):
        script = self.campaign()
        self.assertTrue(self.start(script, 1))
        template = fields(script.scopes["WKR"].templates["Worker Home Guard"])
        regiments = template["regiments"]
        self.assertEqual([name for name, _, _ in regiments], ["ADISCORD_militia"] * 3)
        self.assertNotIn("support", template)
        units = fields(fields(parse(read("common/units/ADISCORD_land_units.txt")))["sub_units"])
        manpower = sum(float(fields(units[name])["manpower"]) for name, _, _ in regiments)
        rifles = sum(float(fields(fields(units[name])["need"])["infantry_equipment"]) for name, _, _ in regiments)
        receipt = script.scopes["WKR"].variables
        self.assertEqual((receipt["WKR_council_order_manpower"], receipt["WKR_council_order_rifles"]),
                         (manpower, rifles))
        self.assertTrue(script.scopes["WKR"].template_locks["Worker Home Guard"])
        self.assertTrue(script.scopes["WKR"].template_recruitment["Worker Home Guard"])

    def test_first_formation_is_available_during_preparation_and_finishes_on_day_35(self):
        focuses = {
            fields(value)["id"]: fields(value)
            for key, _, value in walk(parse(read("focus_trees/Vorkerland/wkr/focuses.txt")))
            if key == "focus" and isinstance(value, list)
        }
        script = self.campaign(seats=0)
        country = script.scopes["WKR"]
        country.focuses.clear()
        elapsed = 0
        self.assertFalse(self.start(script, 1))
        for name in ("WKR_affirm_worker_mandate", "WKR_organize_factory_battalions"):
            focus = focuses[name]
            self.assertTrue(script.conditions(focus["allow_branch"]))
            self.assertTrue(script.conditions(focus["available"]))
            country.focuses.add(name)
            script.run(focus["completion_reward"])
            elapsed += 7 * float(focus["cost"])
        self.assertEqual(country.variables["WKR_working_councils"], 1)
        self.assertTrue(self.start(script, 1))
        self.assertFalse(country.enemies)
        self.assertEqual(elapsed + float(self.orders[1]["days_remove"]), 35)
        self.assertLess(float(self.orders[2]["days_remove"]), float(self.orders[1]["days_remove"]))

    def test_requisition_focus_cannot_spend_time_on_an_exhausted_council_pool(self):
        focuses = {
            fields(value)["id"]: fields(value)
            for key, _, value in walk(parse(read("focus_trees/Vorkerland/wkr/focuses.txt")))
            if key == "focus" and isinstance(value, list)
        }
        available = focuses["WKR_requisition_in_the_republics_name"]["available"]
        for seats in (0, 1, 2, 5):
            script = self.campaign(seats=seats)
            self.assertEqual(script.conditions(available), seats >= 2)
        self.assertTrue(self.start(script, 1))
        self.assertFalse(script.conditions(available))

    def test_fractional_prices_and_repeat_clicks_cannot_underpay(self):
        for count in self.orders:
            prices = {"pp": 25 * count, "people": 3000 * count, "infantry_equipment": 2700 * count}
            for short in (None, *prices):
                script = self.campaign()
                country = script.scopes["WKR"]
                country.resources.update(prices)
                if short:
                    country.resources[short] -= .01
                before = deepcopy(country.resources)
                self.assertEqual(self.start(script, count), short is None)
                paid = deepcopy(country.resources)
                script.run(self.orders[count]["complete_effect"])
                self.assertEqual(country.resources, paid)
                for resource, price in prices.items():
                    self.assertAlmostEqual(country.resources[resource], before[resource] - price * (short is None))

    def test_orders_share_one_receipt_and_reserve_real_councils(self):
        for first, second in product(self.orders, repeat=2):
            script = self.campaign()
            self.assertTrue(self.start(script, first))
            before = deepcopy(script.scopes)
            self.assertFalse(self.start(script, second))
            script.run(self.orders[second]["complete_effect"])
            self.assertEqual(script.scopes, before)
            country = script.scopes["WKR"]
            self.assertEqual(country.variables["WKR_working_councils"], 5 - first)
            self.assertAlmostEqual(country.variables[V + "wkr_council_output"], (5 - first) * .03)
            self.assertAlmostEqual(country.variables[V + "wkr_council_conscription"], first * .004)
            self.assertFalse([call for call in script.calls if call[0] == "create_unit"])
        self.assertFalse(self.start(self.campaign(seats=0), 1))
        self.assertFalse(self.start(self.campaign(seats=1), 2))

    def test_delivery_spawns_only_the_paid_units_and_old_callbacks_are_inert(self):
        for count in self.orders:
            script = self.campaign()
            self.assertTrue(self.start(script, count))
            paid = deepcopy(script.scopes["WKR"].resources)
            script = deepcopy(script)
            script.run(self.orders[count]["remove_effect"])
            units = [(scope, fields(payload)) for key, scope, payload in script.calls if key == "create_unit"]
            self.assertEqual(len(units), count)
            for scope, unit in units:
                self.assertEqual(scope, "capital_WKR")
                self.assertEqual(unit["owner"], "PREV")
                self.assertEqual(unit["allow_spawning_on_enemy_provs"], "no")
                for token in ('division_template = "Worker Home Guard"',
                              "start_manpower_factor = 1.0", "start_equipment_factor = 1.0"):
                    self.assertIn(token, unit["division"])
            self.assert_receipt_closed(script)
            settled = deepcopy((script.scopes, script.calls))
            script.run(self.orders[count]["remove_effect"])
            script.run(self.orders[count]["cancel_effect"])
            self.assertEqual((script.scopes, script.calls), settled)
            self.assertEqual(script.scopes["WKR"].resources, paid)
            self.assertEqual(script.scopes["WKR"].variables[V + "wkr_councils_mobilized"], count)

    def test_cancellation_returns_all_payment_and_restores_output_once(self):
        for count, cause, callback in product(self.orders, ("owner", "controller", "capitulation", "subject", "central_end", "campaign_end"),
                                              ("cancel_effect", "remove_effect")):
            script = self.campaign()
            country = script.scopes["WKR"]
            before = deepcopy(country.resources)
            self.assertTrue(self.start(script, count))
            if cause in ("owner", "controller"):
                setattr(script.scopes["capital_WKR"], cause, "TVA")
            elif cause == "capitulation":
                country.capitulated = True
            elif cause == "subject":
                country.subject = "VAD"
            else:
                script.globals.add(V + ("central_war_finished" if cause == "central_end" else "collapse_finished"))
            self.assertTrue(script.conditions(self.orders[count]["cancel_trigger"]))
            script.run(self.orders[count][callback])
            script.run(self.orders[count][callback])
            self.assert_receipt_closed(script)
            self.assertEqual(country.resources, before)
            self.assertEqual(country.variables[V + "wkr_councils_mobilized"], 0)
            self.assertAlmostEqual(country.variables[V + "wkr_council_output"], .15)
            self.assertAlmostEqual(country.variables[V + "wkr_council_conscription"], 0)
            self.assertFalse([call for call in script.calls if call[0] == "create_unit"])

    def test_regional_peace_and_new_leadership_preserve_paid_training(self):
        for count in self.orders:
            script = self.campaign()
            self.assertTrue(self.start(script, count))
            country = script.scopes["WKR"]
            before = deepcopy(country.resources)
            country.enemies.clear()
            country.leader = "WRK_Anton_Bagley"
            country.government = "utilitarism"
            self.assertFalse(script.conditions(self.orders[count]["cancel_trigger"]))
            script.run(self.orders[count]["remove_effect"])
            self.assertEqual(country.resources, before)
            self.assertEqual(sum(key == "create_unit" for key, _, _ in script.calls), count)

    def test_callback_of_the_other_order_cannot_settle_the_receipt(self):
        for first, second in ((1, 2), (2, 1)):
            script = self.campaign()
            self.assertTrue(self.start(script, first))
            before = deepcopy((script.scopes, script.calls))
            script.run(self.orders[second]["cancel_effect"])
            script.run(self.orders[second]["remove_effect"])
            self.assertEqual((script.scopes, script.calls), before)

    def test_reunification_refunds_the_successor_and_keeps_untrained_councils_out_of_veterans(self):
        for count, successor in product(self.orders, ("WRK", "VAD", "TVA")):
            script = self.campaign()
            self.assertTrue(self.start(script, count))
            paid = deepcopy(script.scopes["WKR"].resources)
            original = deepcopy(script.scopes[successor].resources)
            script.root = successor
            script.source = "WKR"
            for _ in range(2):
                script.effect("WKR_settle_council_order_handoff")
                script.effect("WKR_close_council_orders", "WKR")
            self.assert_receipt_closed(script)
            self.assertEqual(script.scopes["WKR"].resources, paid)
            for key, price in (("pp", 25), ("people", 3000), ("infantry_equipment", 2700)):
                self.assertEqual(script.scopes[successor].resources[key], original[key] + price * count)
            self.assertEqual(script.scopes["WKR"].variables[V + "wkr_councils_mobilized"], 0)
            self.assertFalse(script.scopes["WKR"].template_locks["Worker Home Guard"])
            self.assertTrue(script.scopes["WKR"].template_recruitment["Worker Home Guard"])

    def test_terminal_cleanup_refunds_before_unlocking_and_never_reopens_orders(self):
        script = self.campaign()
        self.assertTrue(self.start(script, 1))
        script.globals.add(V + "central_war_finished")
        script.effect("WKR_close_council_orders")
        country = script.scopes["WKR"]
        self.assertEqual(country.resources["people"], 20000)
        self.assertFalse(country.template_locks["Worker Home Guard"])
        self.assertTrue(country.template_recruitment["Worker Home Guard"])
        country.enemies.add("TVA")
        self.assertFalse(self.start(script, 1))
        script.run(self.orders[1]["remove_effect"])
        self.assertFalse([call for call in script.calls if call[0] == "create_unit"])

    def test_both_previews_match_the_applied_aggregate_delta(self):
        ideas = fields(fields(parse(read("common/ideas/ADISCORD_vorkerland_ideas.txt")))["ideas"])
        ideas = fields(ideas["country"])
        aggregate = fields(fields(parse(read("common/dynamic_modifiers/ADISCORD_vorkerland_dynamic_modifiers.txt")))[V + "wkr_councils"])
        for count in self.orders:
            script = self.campaign()
            before = deepcopy(script.scopes["WKR"].variables)
            preview = fields(self.orders[count]["complete_effect"])["effect_tooltip"]
            name = fields(preview)["add_ideas"]
            delta = fields(fields(ideas[name])["modifier"])
            self.assertTrue(self.start(script, count))
            for modifier, amount in delta.items():
                variable = aggregate[modifier]
                self.assertAlmostEqual(script.scopes["WKR"].variables[variable] - before[variable], float(amount))


class WKRPresidentialDoctrineTests(unittest.TestCase):
    programme = "WKR_assault_column_programme"
    template = "Worker Assault Column"
    prices = {"pp": 60, "people": 6000, "infantry_equipment": 5400}
    deltas = {"conscription": .02, "training_time_army_factor": -.15,
              "army_attack_factor": .05, "army_org_factor": -.05,
              "experience_gain_army_factor": -.10}

    @classmethod
    def setUpClass(cls):
        cls.base = WKRCouncilFormationTests()
        cls.base.setUpClass()
        cls.focuses = {fields(value)["id"]: fields(value)
                       for key, _, value in walk(parse(read("focus_trees/Vorkerland/wkr/focuses.txt")))
                       if key == "focus" and isinstance(value, list)}

    def order(self):
        self.assertTrue(self.programme in self.base.category, "Assault-column programme is missing")
        return fields(self.base.category[self.programme])

    def campaign(self, seats=5):
        script = self.base.campaign(seats)
        country = script.scopes["WKR"]
        country.leader = "WRK_Nikita_Worcker"
        country.leader_ideology = "neo_vorkerism"
        country.focuses.update({"WKR_doctrine_of_the_armed_people", "WKR_break_them_with_numbers"})
        return script

    def start(self, script, kind=3):
        order = self.order() if kind == 3 else self.base.orders[kind]
        if not all(script.conditions(order[key]) for key in ("visible", "available", "custom_cost_trigger")):
            return False
        script.run(order["complete_effect"])
        return True

    def test_doctrine_preview_applies_before_completion_and_survives_council_recalculation(self):
        script = self.campaign()
        country = script.scopes["WKR"]
        country.focuses.discard("WKR_doctrine_of_the_armed_people")
        script.effect("WKR_initialize_administration")
        aggregate = fields(fields(parse(read("common/dynamic_modifiers/ADISCORD_vorkerland_dynamic_modifiers.txt")))[V + "wkr_councils"])
        before = deepcopy(country.variables)
        reward = self.focuses["WKR_doctrine_of_the_armed_people"]["completion_reward"]
        self.assertTrue("effect_tooltip" in fields(reward), "Doctrine needs an exact aggregate preview")
        preview_id = fields(fields(reward)["effect_tooltip"])["add_ideas"]
        ideas = fields(fields(fields(parse(read("common/ideas/ADISCORD_vorkerland_ideas.txt")))["ideas"])["country"])
        self.assertEqual({key: float(value) for key, _, value in fields(ideas[preview_id])["modifier"]}, self.deltas)
        script.run(reward)
        for modifier, amount in self.deltas.items():
            self.assertIn(modifier, aggregate)
            variable = aggregate[modifier]
            self.assertAlmostEqual(country.variables[variable] - before.get(variable, 0), amount)
        self.assertNotIn(preview_id, country.flags)
        expected = {modifier: country.variables[aggregate[modifier]] for modifier in self.deltas}
        script.effect("WKR_initialize_administration")
        script.effect(V + "wkr_refresh_councils")
        for modifier, amount in expected.items():
            self.assertAlmostEqual(country.variables[aggregate[modifier]], amount)
        self.assertTrue(self.start(script))
        self.assertAlmostEqual(country.variables[aggregate["conscription"]], .028)
        script.run(self.order()["cancel_effect"])
        self.assertAlmostEqual(country.variables[aggregate["conscription"]], .02)
        for cause in ("central_war_finished", "collapse_finished"):
            closed = deepcopy(script)
            closed.globals.add(V + cause)
            self.assertFalse(closed.conditions(aggregate["enable"]))

    def test_focus_requires_usable_capacity_and_unlocks_a_stable_recruitable_template(self):
        focus = self.focuses["WKR_break_them_with_numbers"]
        self.assertEqual(focus["cost"], "3")
        for seats in (0, 1, 2, 5):
            script = self.campaign(seats)
            self.assertEqual(script.conditions(focus["available"]), seats >= 2)
        self.assertTrue(self.start(script, 1))
        self.assertFalse(script.conditions(focus["available"]))
        script = self.campaign()
        country = script.scopes["WKR"]
        country.focuses.discard("WKR_break_them_with_numbers")
        reward = focus["completion_reward"]
        self.assertEqual(fields(reward)["unlock_decision_tooltip"], self.programme)
        script.run(reward)
        self.assertTrue(country.template_locks[self.template])
        self.assertTrue(country.template_recruitment[self.template])
        self.assertFalse(self.start(script))
        country.focuses.add("WKR_break_them_with_numbers")
        self.assertTrue(self.start(script))
        country.focuses.remove("WKR_organize_factory_battalions")
        self.assertFalse(script.conditions(focus["available"]))

    def test_paid_template_and_fractional_prices_match_six_militia(self):
        for short in (None, *self.prices):
            script = self.campaign()
            country = script.scopes["WKR"]
            country.resources.update(self.prices)
            if short:
                country.resources[short] -= .01
            before = deepcopy(country.resources)
            self.assertEqual(self.start(script), short is None)
            for resource, price in self.prices.items():
                self.assertAlmostEqual(country.resources[resource], before[resource] - price * (short is None))
            if short:
                continue
            template = fields(country.templates[self.template])
            self.assertEqual([name for name, _, _ in template["regiments"]], ["ADISCORD_militia"] * 6)
            self.assertNotIn("support", template)
            units = fields(fields(parse(read("common/units/ADISCORD_land_units.txt")))["sub_units"])
            militia = fields(units["ADISCORD_militia"])
            self.assertEqual(float(militia["manpower"]) * 6, self.prices["people"])
            self.assertEqual(float(fields(militia["need"])["infantry_equipment"]) * 6, self.prices["infantry_equipment"])
            self.assertEqual(country.variables["WKR_council_order_kind"], 3)
            self.assertEqual(country.variables["WKR_council_order_units"], 2)
            self.assertEqual(country.variables["WKR_working_councils"], 3)
            self.assertTrue(country.template_locks[self.template])
            self.assertTrue(country.template_recruitment[self.template])
        self.assertEqual(self.order()["days_remove"], "21")

    def test_all_three_orders_exclude_each_other_and_wrong_callbacks_cannot_settle(self):
        orders = {**self.base.orders, 3: self.order()}
        for first, other in product(orders, repeat=2):
            script = self.campaign()
            self.assertTrue(self.start(script, first))
            self.assertEqual(script.scopes["WKR"].variables["WKR_council_order_kind"], first)
            before = deepcopy((script.scopes, script.calls))
            self.assertFalse(self.start(script, other))
            script.run(orders[other]["complete_effect"])
            self.assertEqual((script.scopes, script.calls), before)
            if other != first:
                script.run(orders[other]["cancel_effect"])
                script.run(orders[other]["remove_effect"])
                self.assertEqual((script.scopes, script.calls), before)

    def test_delivery_is_one_trained_column_and_paid_course_survives_leader_change(self):
        script = self.campaign()
        self.assertTrue(self.start(script))
        script = deepcopy(script)
        country = script.scopes["WKR"]
        country.leader = "WRK_Anton_Bagley"
        country.government = "utilitarism"
        country.enemies.clear()
        before = deepcopy(country.resources)
        self.assertFalse(script.conditions(self.order()["cancel_trigger"]))
        script.run(self.order()["remove_effect"])
        units = [(scope, fields(payload)) for key, scope, payload in script.calls if key == "create_unit"]
        self.assertEqual(len(units), 1)
        scope, unit = units[0]
        self.assertEqual(scope, "capital_WKR")
        self.assertEqual(unit["owner"], "PREV")
        self.assertEqual(unit["allow_spawning_on_enemy_provs"], "no")
        for token in ('division_template = "Worker Assault Column"', 'start_experience_factor = 0.30',
                      'start_manpower_factor = 1.0', 'start_equipment_factor = 1.0'):
            self.assertIn(token, unit["division"])
        self.assertEqual(country.resources, before)
        self.assertEqual(country.variables[V + "wkr_councils_mobilized"], 2)
        self.base.assert_receipt_closed(script)
        settled = deepcopy((script.scopes, script.calls))
        script.run(self.order()["remove_effect"])
        script.run(self.order()["cancel_effect"])
        self.assertEqual((script.scopes, script.calls), settled)
        self.assertFalse(self.start(script))

    def test_cancellation_and_handoff_refund_once_before_unlocking(self):
        for cause, callback in product(("owner", "controller", "subject", "capitulation", "central_war_finished", "collapse_finished"),
                                       ("remove_effect", "cancel_effect")):
            script = self.campaign()
            country = script.scopes["WKR"]
            before = deepcopy(country.resources)
            self.assertTrue(self.start(script))
            if cause in ("owner", "controller"):
                setattr(script.scopes["capital_WKR"], cause, "TVA")
            elif cause == "subject":
                country.subject = "VAD"
            elif cause == "capitulation":
                country.capitulated = True
            else:
                script.globals.add(V + cause)
            self.assertTrue(script.conditions(self.order()["cancel_trigger"]))
            script.run(self.order()[callback])
            script.run(self.order()[callback])
            self.assertEqual(country.resources, before)
            self.assertEqual(country.variables["WKR_working_councils"], 5)
            self.base.assert_receipt_closed(script)
        for recipient in ("WRK", "VAD", "TVA"):
            script = self.campaign()
            self.assertTrue(self.start(script))
            before = deepcopy(script.scopes[recipient].resources)
            script.root = recipient
            for _ in range(2):
                script.effect("WKR_settle_council_order_handoff")
                script.effect("WKR_close_council_orders", "WKR")
            for resource, price in self.prices.items():
                self.assertEqual(script.scopes[recipient].resources[resource], before[resource] + price)
            self.assertFalse(script.scopes["WKR"].template_locks[self.template])
            self.assertTrue(script.scopes["WKR"].template_recruitment[self.template])
            self.assertEqual(script.scopes["WKR"].variables[V + "wkr_councils_mobilized"], 0)
            self.base.assert_receipt_closed(script)
        cleanup = [key for key, _, _ in EFFECTS["WKR_close_council_orders"]]
        self.assertEqual(cleanup[0], "WKR_refund_council_order")
        script = self.campaign()
        self.assertTrue(self.start(script))
        script.globals.add(V + "central_war_finished")
        script.effect("WKR_close_council_orders")
        script.scopes["WKR"].enemies.add("RUS")
        self.assertFalse(self.start(script))

    def test_native_loss_callbacks_return_all_three_resources_to_the_actual_recipient(self):
        native = FieldTrialAccountingTests()
        native.setUpClass()
        for hook in ("on_capitulation_immediate", "on_capitulation", "on_puppet", "on_annex"):
            script = self.campaign()
            self.assertTrue(self.start(script))
            recipient = "WKR"
            if hook == "on_annex":
                script.root = recipient = "TVA"
                script.source = "WKR"
                script.scopes["WKR"].exists = False
            else:
                script.source = "TVA"
                script.scopes["WKR"].capitulated = hook != "on_puppet"
                script.scopes["WKR"].subject = "TVA" if hook == "on_puppet" else None
            callbacks = [item for item in fields(native.hooks[hook])["effect"] if any(
                key in ("WKR_refund_council_order", "WKR_settle_council_order_handoff")
                for key, _, _ in walk([item]))]
            self.assertEqual(len(callbacks), 1)
            before = deepcopy(script.scopes[recipient].resources)
            script.run(callbacks)
            script.run(callbacks)
            for resource, price in self.prices.items():
                self.assertEqual(script.scopes[recipient].resources[resource], before[resource] + price)
            self.base.assert_receipt_closed(script)
            script.root = "WKR"
            script.source = None
            before = deepcopy((script.scopes, script.calls))
            script.run(self.order()["remove_effect"])
            self.assertEqual((script.scopes, script.calls), before)

    def test_summary_preview_and_localisation_distinguish_one_column_from_two_orders(self):
        order = self.order()
        self.assertEqual(order["cost"], "0")
        preview = fields(order["complete_effect"])["effect_tooltip"]
        self.assertEqual(fields(preview)["add_ideas"], "WKR_councils_batch_mobilized_dummy")
        loc = parse(read("common/scripted_localisation/ADISCORD_vorkerland_scripted_loc.txt"))
        definition = next(value for key, _, value in loc
                          if key == "defined_text" and fields(value).get("name") == "GetWKRCouncilOrder")
        for kind in (1, 2, 3):
            script = self.campaign()
            self.assertTrue(self.start(script, kind))
            selected = next(fields(value)["localization_key"] for key, _, value in definition
                            if key == "text" and script.conditions(fields(value)["trigger"]))
            self.assertEqual(selected, "WKR_assault_column_pending" if kind == 3 else "WKR_council_order_pending")
        for language in ("russian", "english"):
            path = ROOT / f"localisation/{language}/ADISCORD_vorkerland_l_{language}.yml"
            self.assertTrue(path.read_bytes().startswith(b"\xef\xbb\xbf"))
            rows = dict(re.findall(r'^\s*(\w+):\d*\s*"((?:\\.|[^"\\])*)"\s*$', path.read_text(encoding="utf-8-sig"), re.M))
            for key in (self.programme, self.programme + "_desc", "WKR_assault_column_unlock_tt",
                        "WKR_assault_column_result_tt", "WKR_assault_column_pending",
                        "WKR_assault_column_unit", "WKR_assault_column_cost",
                        "WKR_assault_column_cost_blocked", "WKR_assault_column_cost_tooltip"):
                self.assertIn(key, rows)
            self.assertIn("6000", rows["WKR_assault_column_cost"])
            self.assertIn("5400", rows["WKR_assault_column_cost"])
            self.assertNotIn("[?WKR_council_order_units", rows["WKR_assault_column_pending"])


class WKRRailwayCouncilTests(unittest.TestCase):
    prices = {"pp": 40, "people": 500, "support_equipment": 40, "train_equipment": 5}
    modifier = "WKR_railway_council"
    registry = "global.WKR_railway_council_states"

    @classmethod
    def setUpClass(cls):
        categories = fields(parse(read("common/decisions/ADISCORD_vorkerland_decisions.txt")))
        cls.order = fields(fields(categories[V + "wkr_administration"])["WKR_organize_railway_council"])
        modifiers = fields(parse(read("common/dynamic_modifiers/ADISCORD_vorkerland_dynamic_modifiers.txt")))
        cls.bonus = fields(modifiers[cls.modifier])

    def campaign(self):
        script = Script()
        script.root = "WKR"
        script.globals = {V + "collapse_started", V + "collapse_wars_started",
                          V + "phase_central_preparation"}
        country = script.scopes["WKR"]
        country.focuses.add("WKR_put_railways_under_councils")
        country.resources.update(pp=200, people=20000, support_equipment=400, train_equipment=50)
        for target in ("32", "33"):
            state = script.scopes[target]
            state.owner = state.controller = "WKR"
            state.resources["supply_node"] = 1
        return script

    def start(self, script, target="32"):
        script.source = target
        if not all(script.conditions(self.order[key]) for key in
                   ("target_trigger", "visible", "available", "custom_cost_trigger")):
            return False
        script.run(self.order["complete_effect"])
        return True

    def assert_closed(self, script):
        self.assertFalse(any(key.startswith("WKR_railway_order_") for key in script.scopes["WKR"].variables))
        for scope in script.scopes.values():
            self.assertNotIn("WKR_railway_in_progress", scope.flags)

    def test_targets_match_real_theatre_hubs_and_include_two_home_states(self):
        from tools.lib.adiscord_vorkerland_theatre_manifest import VORKERLAND_THEATRE_PACKAGES

        theatre = {number for package in VORKERLAND_THEATRE_PACKAGES.values() for number in package}
        hubs = set()
        for line in read("map/supply_nodes.txt").splitlines():
            tokens = line.split("#", 1)[0].split()
            if tokens:
                hubs.add(int(tokens[1]))
        expected = set()
        for path in (ROOT / "history/states").glob("*.txt"):
            state = fields(fields(parse(path.read_text(encoding="utf-8-sig")))["state"])
            number = int(state["id"])
            provinces = {int(value) for _, _, value in state["provinces"]}
            if number in theatre and provinces & hubs:
                expected.add(number)
        targets = {int(value) for _, _, value in self.order["targets"]}
        self.assertEqual(targets, expected)
        self.assertEqual(targets & set(VORKERLAND_THEATRE_PACKAGES["WKR"]), {32, 33})

    def test_first_focus_order_has_materials_and_finishes_on_day_49(self):
        focuses = {fields(value)["id"]: fields(value)
                   for key, _, value in walk(parse(read("focus_trees/Vorkerland/wkr/focuses.txt")))
                   if key == "focus" and isinstance(value, list)}
        script = self.campaign()
        country = script.scopes["WKR"]
        country.focuses.clear()
        country.resources.update(support_equipment=0, train_equipment=0)
        elapsed = 0
        self.assertFalse(self.start(script))
        for name in ("WKR_affirm_worker_mandate", "WKR_put_railways_under_councils"):
            focus = focuses[name]
            self.assertTrue(script.conditions(focus["allow_branch"]))
            self.assertTrue(script.conditions(focus["available"]))
            country.focuses.add(name)
            script.run(focus["completion_reward"])
            elapsed += 7 * float(focus["cost"])
        self.assertEqual(elapsed, 21)
        self.assertEqual(country.resources["train_equipment"], self.prices["train_equipment"])
        self.assertEqual(country.resources["support_equipment"], self.prices["support_equipment"])
        self.assertTrue(self.start(script))
        self.assertEqual(elapsed + float(self.order["days_remove"]), 49)

    def test_fractional_costs_and_shared_queue_cannot_underpay_or_overwrite(self):
        self.assertEqual(self.order["cost"], "0")
        for short in (None, *self.prices):
            with self.subTest(short=short):
                script = self.campaign()
                country = script.scopes["WKR"]
                country.resources.update(self.prices)
                if short:
                    country.resources[short] -= .01
                before = deepcopy(country.resources)
                self.assertEqual(self.start(script), short is None)
                paid = deepcopy(country.resources)
                script.run(self.order["complete_effect"])
                self.assertEqual(country.resources, paid)
                for resource, price in self.prices.items():
                    self.assertAlmostEqual(country.resources[resource], before[resource] - price * (short is None))
        script = self.campaign()
        self.assertTrue(self.start(script, "32"))
        before = deepcopy(script.scopes)
        self.assertFalse(self.start(script, "33"))
        script.run(self.order["complete_effect"])
        self.assertEqual(script.scopes, before)
        self.assertEqual(script.scopes["WKR"].variables["WKR_railway_order_state"], 32)

    def test_delivery_and_preview_apply_the_same_local_bonus_once(self):
        script = self.campaign()
        self.assertTrue(self.start(script))
        paid = deepcopy(script.scopes["WKR"].resources)
        script = deepcopy(script)
        script.run(self.order["remove_effect"])
        self.assertIn(self.modifier, script.scopes["32"].flags)
        self.assertNotIn(self.modifier, script.scopes["WKR"].flags)
        self.assertEqual(script.arrays[self.registry], ["32"])
        self.assert_closed(script)
        self.assertEqual(script.scopes["WKR"].resources, paid)
        preview = fields(self.order["complete_effect"])["effect_tooltip"]
        self.assertEqual([value for key, _, value in walk(preview) if key == "add_dynamic_modifier"],
                         [value for key, _, value in script.calls if key == "add_dynamic_modifier"])
        self.assertEqual(float(self.bonus["local_supplies_for_controller"]), .25)
        self.assertEqual(float(self.bonus["army_speed_factor_for_controller"]), .10)
        self.assertTrue(script.conditions(self.bonus["enable"], "32"))
        self.assertFalse(self.start(script))
        before = deepcopy((script.scopes, script.calls, script.arrays))
        script.run(self.order["remove_effect"])
        script.run(self.order["cancel_effect"])
        self.assertEqual((script.scopes, script.calls, script.arrays), before)

    def test_invalid_delivery_or_cancellation_refunds_each_resource_once(self):
        causes = ("owner", "controller", "full_control", "hub", "capitulation", "subject", "central_end", "campaign_end")
        for cause, callback in product(causes, ("cancel_effect", "remove_effect")):
            with self.subTest(cause=cause, callback=callback):
                script = self.campaign()
                country = script.scopes["WKR"]
                state = script.scopes["32"]
                before = deepcopy(country.resources)
                self.assertTrue(self.start(script))
                if cause in ("owner", "controller"):
                    setattr(state, cause, "TVA")
                elif cause == "full_control":
                    state.fully_controlled = False
                elif cause == "hub":
                    state.resources["supply_node"] = 0
                elif cause == "capitulation":
                    country.capitulated = True
                elif cause == "subject":
                    country.subject = "VAD"
                else:
                    script.globals.add(V + ("central_war_finished" if cause == "central_end" else "collapse_finished"))
                self.assertTrue(script.conditions(self.order["cancel_trigger"]))
                for _ in range(2):
                    script.run(self.order[callback])
                self.assert_closed(script)
                self.assertEqual(country.resources, before)
                self.assertNotIn(self.modifier, state.flags)
                self.assertFalse(script.arrays[self.registry])

    def test_old_target_callbacks_cannot_settle_a_new_target(self):
        script = self.campaign()
        self.assertTrue(self.start(script, "32"))
        script.scopes["32"].controller = "TVA"
        script.effect("WKR_lose_railway_council", "32")
        self.assert_closed(script)
        script.scopes["32"].controller = "WKR"
        self.assertTrue(self.start(script, "33"))
        script.source = "32"
        self.assertTrue(script.conditions(self.order["cancel_trigger"]))
        before = deepcopy(script.scopes)
        script.run(self.order["cancel_effect"])
        script.run(self.order["remove_effect"])
        self.assertEqual(script.scopes, before)
        script.source = "33"
        script.run(self.order["remove_effect"])
        self.assertIn(self.modifier, script.scopes["33"].flags)
        self.assertNotIn(self.modifier, script.scopes["32"].flags)
        self.assert_closed(script)

    def test_regional_peace_and_leadership_change_preserve_paid_work(self):
        script = self.campaign()
        self.assertTrue(self.start(script))
        country = script.scopes["WKR"]
        paid = deepcopy(country.resources)
        country.enemies.clear()
        country.government = "utilitarism"
        country.leader = "WRK_Anton_Bagley"
        self.assertFalse(script.conditions(self.order["cancel_trigger"]))
        script.run(self.order["remove_effect"])
        self.assertEqual(country.resources, paid)
        self.assertIn(self.modifier, script.scopes["32"].flags)

    def test_completed_council_suspends_for_partial_control_and_hub_loss(self):
        script = self.campaign()
        self.assertTrue(self.start(script))
        script.run(self.order["remove_effect"])
        state = script.scopes["32"]
        state.fully_controlled = False
        script.effect("WKR_lose_railway_council", "32")
        self.assertFalse(script.conditions(self.bonus["enable"], "32"))
        self.assertIn(self.modifier, state.flags)
        state.fully_controlled = True
        self.assertTrue(script.conditions(self.bonus["enable"], "32"))
        state.resources["supply_node"] = 0
        self.assertFalse(script.conditions(self.bonus["enable"], "32"))
        state.resources["supply_node"] = 1
        self.assertTrue(script.conditions(self.bonus["enable"], "32"))

    def test_completed_state_loss_cleans_registry_and_recapture_requires_full_price(self):
        script = self.campaign()
        self.assertTrue(self.start(script))
        script.run(self.order["remove_effect"])
        state = script.scopes["32"]
        paid = deepcopy(script.scopes["WKR"].resources)
        state.controller = "TVA"
        for _ in range(2):
            script.effect("WKR_lose_railway_council", "32")
        self.assertNotIn(self.modifier, state.flags)
        self.assertFalse(script.arrays[self.registry])
        self.assertEqual(script.scopes["WKR"].resources, paid)
        state.controller = "WKR"
        self.assertTrue(self.start(script))
        for resource, price in self.prices.items():
            self.assertEqual(script.scopes["WKR"].resources[resource], paid[resource] - price)

    def test_first_reunification_transfer_refunds_the_live_successor(self):
        script = self.campaign()
        self.assertTrue(self.start(script))
        paid = deepcopy(script.scopes["WKR"].resources)
        recipient = script.scopes["WRK"]
        before = deepcopy(recipient.resources)
        script.globals.add(V + "phase_reunification")
        script.scopes["32"].owner = script.scopes["32"].controller = "WRK"
        script.effect("WKR_lose_railway_council", "32")
        script.root = "WRK"
        script.effect("WKR_settle_railway_handoff")
        script.effect("WKR_close_railway_councils", "WKR")
        self.assert_closed(script)
        self.assertEqual(script.scopes["WKR"].resources, paid)
        for resource, price in self.prices.items():
            self.assertEqual(recipient.resources[resource], before[resource] + price)

    def test_annexed_country_defers_receipt_to_annexer_without_duplicate_refund(self):
        for successor in ("WRK", "VAD", "TVA"):
            script = self.campaign()
            self.assertTrue(self.start(script))
            paid = deepcopy(script.scopes["WKR"].resources)
            before = deepcopy(script.scopes[successor].resources)
            script.scopes["WKR"].exists = False
            script.scopes["32"].owner = script.scopes["32"].controller = successor
            script.effect("WKR_lose_railway_council", "32")
            self.assertIn("WKR_railway_order_pp", script.scopes["WKR"].variables)
            script.root = successor
            for _ in range(2):
                script.effect("WKR_settle_railway_handoff")
                script.effect("WKR_close_railway_councils", "WKR")
            self.assert_closed(script)
            self.assertEqual(script.scopes["WKR"].resources, paid)
            for resource, price in self.prices.items():
                self.assertEqual(script.scopes[successor].resources[resource], before[resource] + price)

    def test_terminal_cleanup_removes_only_registered_councils_and_refunds_once(self):
        script = self.campaign()
        self.assertTrue(self.start(script, "32"))
        script.run(self.order["remove_effect"])
        paid = deepcopy(script.scopes["WKR"].resources)
        self.assertTrue(self.start(script, "33"))
        script.scopes["TVA"].exists = True
        before = deepcopy((script.scopes, script.arrays))
        script.effect("WKR_close_railway_councils", "TVA")
        self.assertEqual((script.scopes, script.arrays), before)
        script.globals.add(V + "central_war_finished")
        for _ in range(2):
            script.effect("WKR_close_railway_councils")
        self.assert_closed(script)
        self.assertFalse(script.arrays[self.registry])
        self.assertNotIn(self.modifier, script.scopes["32"].flags)
        self.assertEqual(script.scopes["WKR"].resources, paid)
        script.scopes["WKR"].enemies.add("TVA")
        self.assertFalse(self.start(script))


class WKRDiplomaticProgrammeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        categories = fields(parse(read("common/decisions/ADISCORD_vorkerland_decisions.txt")))
        category = fields(categories[V + "wkr_administration"])
        cls.supply = fields(category["WKR_supply_coalition_partner"])
        cls.recognition = fields(category["WKR_negotiate_republic_recognition"])
        cls.event = fields(EVENTS[V + "diplomacy.17"])
        cls.options = [fields(value) for key, _, value in EVENTS[V + "diplomacy.17"] if key == "option"]

    def campaign(self, recognition=False):
        script = Script()
        script.root = "WKR"
        script.globals = {V + "collapse_started", V + "collapse_wars_started", V + "phase_central_showdown"}
        sender = script.scopes["WKR"]
        focus = "WKR_seek_outside_recognition" if recognition else "WKR_arm_the_bracket_victors"
        sender.focuses.add(focus)
        sender.resources.update(pp=100, infantry_equipment=4000, support_equipment=200)
        sender.faction = "WKR"
        sender.enemies.add("TVA")
        sender.war_sides["central"] = "west"
        ally = script.scopes["EYR"]
        ally.faction = "WKR"
        ally.enemies.add("TVA")
        ally.war_sides["central"] = "west"
        for tag in ("ROM", "TRU"):
            script.scopes[tag].faction = "republic_league"
        return script

    def launch(self, script, decision, target):
        script.root = "WKR"
        script.source = target
        if not all(script.conditions(decision[key]) for key in
                   ("target_trigger", "visible", "available", "custom_cost_trigger")):
            return False
        script.run(decision["complete_effect"])
        return True

    def accept(self, script, target):
        script.root = target
        script.source = "WKR"
        option = self.options[1]
        if not script.conditions(option["trigger"]):
            return False
        script.run([item for item in EVENTS[V + "diplomacy.17"][-1][2]
                    if item[0] not in ("name", "trigger", "ai_chance")])
        return True

    def test_supply_transfers_exact_payment_without_minting_equipment(self):
        delivery = EFFECTS["WKR_deliver_coalition_supply"]
        self.assertFalse(any(key == "add_equipment_to_stockpile" for key, _, _ in walk(delivery)))
        self.assertEqual([fields(value) for key, _, value in walk(delivery) if key == "send_equipment"], [
            {"type": "infantry_equipment", "amount": "1000", "target": "FROM"},
            {"type": "support_equipment", "amount": "50", "target": "FROM"},
        ])
        prices = {"pp": 25, "infantry_equipment": 1000, "support_equipment": 50}
        for short in (None, *prices):
            script = self.campaign()
            sender = script.scopes["WKR"]
            recipient = script.scopes["EYR"]
            sender.resources.update(prices)
            if short:
                sender.resources[short] -= .01
            before = deepcopy(sender.resources)
            self.assertEqual(self.launch(script, self.supply, "EYR"), short is None)
            paid = deepcopy((sender.resources, recipient.resources))
            script.run(self.supply["complete_effect"])
            self.assertEqual((sender.resources, recipient.resources), paid)
            for resource, price in prices.items():
                self.assertEqual(sender.resources[resource], before[resource] - price * (short is None))
                if resource != "pp":
                    self.assertEqual(recipient.resources[resource], price * (short is None))
        self.assertEqual(self.supply["cost"], "0")
        self.assertEqual(self.supply["days_re_enable"], "30")

    def test_supply_requires_the_same_side_of_the_same_war_not_only_a_shared_enemy(self):
        for cause in ("separate_war", "opposite_side", "peace", "faction", "capitulation", "sender_subject", "campaign_end"):
            script = self.campaign()
            ally = script.scopes["EYR"]
            if cause == "separate_war":
                ally.war_sides = {"regional": "west"}
            elif cause == "opposite_side":
                ally.war_sides["central"] = "east"
            elif cause == "peace":
                ally.war_sides.clear()
            elif cause == "faction":
                ally.faction = "VAD"
            elif cause == "capitulation":
                ally.capitulated = True
            elif cause == "sender_subject":
                script.scopes["WKR"].subject = "VAD"
            else:
                script.globals.add(V + "central_war_finished")
            before = deepcopy((script.scopes["WKR"].resources, ally.resources))
            self.assertFalse(self.launch(script, self.supply, "EYR"), cause)
            script.run(self.supply["complete_effect"])
            self.assertEqual((script.scopes["WKR"].resources, ally.resources), before, cause)
        self.assertNotIn("ROM", str(self.supply["targets"]))
        self.assertNotIn("TRU", str(self.supply["targets"]))

    def test_offer_is_free_until_consent_and_duplicate_dispatch_is_blocked(self):
        for tag in ("ROM", "TRU"):
            script = self.campaign(recognition=True)
            resources = deepcopy(script.scopes["WKR"].resources)
            self.assertTrue(self.launch(script, self.recognition, tag))
            self.assertEqual(script.scopes["WKR"].resources, resources)
            self.assertFalse(self.launch(script, self.recognition, tag))
            script.run(self.recognition["complete_effect"])
            dispatch = [call for call in script.calls if call[0] == "country_event"]
            self.assertEqual(len(dispatch), 1)
            self.assertEqual(dispatch[0][1], tag)
            self.assertEqual(fields(dispatch[0][2]), {"id": V + "diplomacy.17", "days": "1"})
            self.assertTrue(self.accept(script, tag))
            self.assertEqual(script.scopes["WKR"].resources["pp"], resources["pp"] - 50)
            self.assertEqual(script.scopes["WKR"].variables[V + "legitimacy_delta"], .04)
            self.assertEqual([scope for key, scope, _ in script.calls if key == V + "add_legitimacy"], ["WKR"])
            self.assertNotIn("WKR_recognition_offer_pending", script.scopes[tag].flags)
            self.assertIn("WKR_independence_treaty", script.scopes[tag].flags)
            settled = deepcopy((script.scopes, script.calls))
            script.effect("WKR_accept_republic_recognition")
            self.assertEqual((script.scopes, script.calls), settled)
            self.assertFalse(self.launch(script, self.recognition, tag))

    def test_treaty_keeps_the_republics_alliance_and_own_wars(self):
        script = self.campaign(recognition=True)
        republic = script.scopes["ROM"]
        republic.enemies.add("DVA")
        republic.war_sides["river"] = "republics"
        original = deepcopy((republic.faction, republic.enemies, republic.war_sides, republic.resources))
        self.assertTrue(self.launch(script, self.recognition, "ROM"))
        self.assertTrue(self.accept(script, "ROM"))
        self.assertEqual((republic.faction, republic.enemies, republic.war_sides, republic.resources), original)
        relations = [(scope, fields(payload)) for key, scope, payload in script.calls if key == "diplomatic_relation"]
        self.assertEqual(relations, [("WKR", {"country": "ROOT", "relation": "non_aggression_pact", "active": "yes"})])
        self.assertFalse(any(key in (V + "join_coalition_of_FROM", "declare_war_on") for key, _, _ in script.calls))

    def test_pending_offers_cannot_overdraw_the_last_payment(self):
        script = self.campaign(recognition=True)
        script.scopes["WKR"].resources["pp"] = 50
        for tag in ("ROM", "TRU"):
            self.assertTrue(self.launch(script, self.recognition, tag))
        self.assertTrue(self.accept(script, "ROM"))
        self.assertFalse(self.accept(script, "TRU"))
        self.assertEqual(script.scopes["WKR"].resources["pp"], 0)
        self.assertNotIn("WKR_independence_treaty", script.scopes["TRU"].flags)
        script.run([("hidden_effect", "=", self.options[0]["hidden_effect"])])
        self.assertNotIn("WKR_recognition_offer_pending", script.scopes["TRU"].flags)

    def test_answer_rechecks_both_countries_and_has_a_safe_timeout_option(self):
        self.assertEqual(self.event["timeout_days"], "14")
        self.assertNotIn("trigger", self.options[0])
        for cause in ("shortage", "sender_capitulation", "sender_subject", "sender_gone", "receiver_capitulation",
                      "receiver_subject", "receiver_gone", "hostile", "campaign_end"):
            script = self.campaign(recognition=True)
            self.assertTrue(self.launch(script, self.recognition, "ROM"))
            sender = script.scopes["WKR"]
            receiver = script.scopes["ROM"]
            if cause == "shortage":
                sender.resources["pp"] = 49.99
            elif cause == "sender_capitulation":
                sender.capitulated = True
            elif cause == "sender_subject":
                sender.subject = "VAD"
            elif cause == "sender_gone":
                sender.exists = False
            elif cause == "receiver_capitulation":
                receiver.capitulated = True
            elif cause == "receiver_subject":
                receiver.subject = "IVN"
            elif cause == "receiver_gone":
                receiver.exists = False
            elif cause == "hostile":
                receiver.enemies.add("WKR")
            else:
                script.globals.add(V + "central_war_finished")
            before = deepcopy(sender.resources)
            self.assertFalse(self.accept(script, "ROM"), cause)
            script.effect("WKR_accept_republic_recognition")
            script.run([("hidden_effect", "=", self.options[0]["hidden_effect"])])
            self.assertEqual(sender.resources, before)
            self.assertNotIn("WKR_independence_treaty", receiver.flags)
            self.assertNotIn("WKR_recognition_offer_pending", receiver.flags)

    def test_terminal_cleanup_closes_offers_without_erasing_signed_treaties(self):
        script = self.campaign(recognition=True)
        self.assertTrue(self.launch(script, self.recognition, "ROM"))
        self.assertTrue(self.accept(script, "ROM"))
        self.assertTrue(self.launch(script, self.recognition, "TRU"))
        script.effect("WKR_close_recognition_offers", "VAD")
        self.assertIn("WKR_recognition_offer_pending", script.scopes["TRU"].flags)
        script.effect("WKR_close_recognition_offers", "WKR")
        self.assertNotIn("WKR_recognition_offer_pending", script.scopes["TRU"].flags)
        self.assertIn("WKR_independence_treaty", script.scopes["ROM"].flags)

    def test_worker_victory_honours_each_signatory_before_the_random_settlement(self):
        for signed in ((), ("ROM",), ("TRU",), ("ROM", "TRU")):
            script = self.campaign(recognition=True)
            for tag in signed:
                self.assertTrue(self.launch(script, self.recognition, tag))
                self.assertTrue(self.accept(script, tag))
            script.root = "WRK"
            script.scopes["WKR"].exists = False
            script.scopes["DVA"].exists = script.scopes["ZTA"].exists = False
            script.calls.clear()
            script.random_index = 1
            script.run(EFFECTS[V + "resolve_unguaranteed_free_republics"])
            treaties = {fields(value)["country"] for key, scope, value in script.calls
                        if key == "diplomatic_relation" and scope == "WRK"}
            attacks = {fields(value)["target"] for key, scope, value in script.calls
                       if key == "declare_war_on" and scope == "WRK"}
            self.assertEqual(treaties, set(signed))
            self.assertEqual(attacks, {"ROM", "TRU"} - set(signed))
            self.assertEqual(len(script.random_weights), 2 - len(signed))
            before = deepcopy((script.scopes, script.calls))
            script.run(EFFECTS[V + "resolve_unguaranteed_free_republics"])
            self.assertEqual((script.scopes, script.calls), before)

    def test_exclusive_focus_rewards_open_usable_programmes_with_first_order_funding(self):
        focuses = {fields(value)["id"]: fields(value)
                   for key, _, value in walk(parse(read("focus_trees/Vorkerland/wkr/focuses.txt")))
                   if key == "focus" and isinstance(value, list)}
        arms = focuses["WKR_arm_the_bracket_victors"]
        treaty = focuses["WKR_seek_outside_recognition"]
        self.assertEqual(fields(arms["mutually_exclusive"])["focus"], "WKR_seek_outside_recognition")
        self.assertEqual(fields(treaty["mutually_exclusive"])["focus"], "WKR_arm_the_bracket_victors")
        self.assertEqual(arms["prerequisite"], treaty["prerequisite"])
        for focus, decision in ((arms, "WKR_supply_coalition_partner"), (treaty, "WKR_negotiate_republic_recognition")):
            self.assertEqual(fields(focus["completion_reward"])["unlock_decision_tooltip"], decision)
            self.assertNotIn("bypass", focus)
            self.assertFalse(any(key == "set_country_flag" for key, _, _ in walk(focus["completion_reward"])))
        script = self.campaign()
        script.scopes["WKR"].resources.update(infantry_equipment=0, support_equipment=0)
        script.run(arms["completion_reward"])
        self.assertTrue(self.launch(script, self.supply, "EYR"))
        script = self.campaign(recognition=True)
        script.scopes["WKR"].resources["pp"] = 0
        script.run(treaty["completion_reward"])
        self.assertTrue(self.launch(script, self.recognition, "ROM"))
        script.root = "WKR"
        self.assertTrue(script.conditions(treaty["available"]))
        script.scopes["ROM"].exists = script.scopes["TRU"].exists = False
        self.assertFalse(script.conditions(treaty["available"]))


class WKRForeignPolicyTests(unittest.TestCase):
    volunteers = "WKR_send_republican_volunteers"
    licences = "WKR_license_outside_patterns"
    deltas = {"send_volunteer_size": 2, "send_volunteers_tension": -1,
              "political_power_gain": -.08}

    @classmethod
    def setUpClass(cls):
        cls.base = WKRCouncilFormationTests()
        cls.base.setUpClass()
        cls.contracts = WartimeProgrammeAccounting()
        cls.contracts.setUpClass()
        cls.focuses = {fields(value)["id"]: fields(value)
                       for key, _, value in walk(parse(read("focus_trees/Vorkerland/wkr/focuses.txt")))
                       if key == "focus" and isinstance(value, list)}
        cls.aggregate = fields(fields(parse(read("common/dynamic_modifiers/ADISCORD_vorkerland_dynamic_modifiers.txt")))[V + "wkr_councils"])

    def campaign(self):
        script = self.base.campaign(5)
        script.effect("WKR_initialize_administration")
        return script

    def test_direct_exclusive_choice_and_no_political_capstone_bypass(self):
        self.assertFalse("WKR_open_the_external_desk" in self.focuses)
        for name, other in ((self.volunteers, self.licences), (self.licences, self.volunteers)):
            focus = self.focuses[name]
            self.assertEqual(fields(focus["prerequisite"])["focus"], "WKR_affirm_worker_mandate")
            self.assertEqual(fields(focus["mutually_exclusive"])["focus"], other)
            self.assertEqual(focus["cost"], "3")
            self.assertNotIn("bypass", focus)
            self.assertNotIn("add_political_power", fields(focus["completion_reward"]))
        chairman = self.focuses["WKR_vest_all_power_in_the_chairman"]["completion_reward"]
        self.assertFalse(any(key == "can_send_volunteers" for key, _, _ in walk(chairman)))
        self.assertNotIn("FOCUS_FILTER_WAR_SUPPORT", str(self.focuses["WKR_break_them_with_numbers"]["search_filters"]))

    def test_volunteer_availability_respects_peace_game_rules_and_both_mandates(self):
        for mandate, at_war, rule in product(("pragmatism", "utilitarism"), (False, True),
                                            ("LIMITED", "ALWAYS_FREE", "SAME_IDEOLOGY", "BLOCKED")):
            script = self.campaign()
            country = script.scopes["WKR"]
            country.government = mandate
            country.enemies = {"VAD"} if at_war else set()
            script.game_rules["allow_volunteers"] = rule
            self.assertEqual(script.conditions(self.focuses[self.volunteers]["available"]),
                             not at_war and rule != "BLOCKED", (mandate, at_war, rule))
            self.assertTrue(script.conditions(self.focuses[self.licences]["available"]))
        for terminal in ("central_war_finished", "collapse_finished"):
            script = self.campaign()
            script.globals.add(V + terminal)
            for name in (self.volunteers, self.licences):
                self.assertFalse(script.conditions(self.focuses[name]["available"]))

    def test_exact_dummy_delta_applies_immediately_and_survives_recalculation(self):
        script = self.campaign()
        country = script.scopes["WKR"]
        reward = self.focuses[self.volunteers]["completion_reward"]
        self.assertIn("effect_tooltip", fields(reward))
        preview = fields(fields(reward)["effect_tooltip"])["add_ideas"]
        ideas = fields(fields(fields(parse(read("common/ideas/ADISCORD_vorkerland_ideas.txt")))["ideas"])["country"])
        self.assertEqual({key: float(value) for key, _, value in fields(ideas[preview])["modifier"]}, self.deltas)
        self.assertEqual(fields(ideas[preview])["name"], V + "wkr_councils")
        script.run(reward)
        self.assertNotIn(self.volunteers, country.focuses)
        self.assertEqual(country.rules, {"can_send_volunteers": "yes"})
        self.assertNotIn(preview, country.flags)
        for modifier, amount in self.deltas.items():
            self.assertAlmostEqual(country.variables[self.aggregate[modifier]], amount)
        country.focuses.add(self.volunteers)
        country.government = "utilitarism"
        script.effect("WKR_initialize_administration")
        script.effect(V + "wkr_refresh_councils")
        self.assertTrue(self.base.start(script, 1))
        script.run(self.base.orders[1]["cancel_effect"])
        for modifier, amount in self.deltas.items():
            self.assertAlmostEqual(country.variables[self.aggregate[modifier]], amount)
        self.assertEqual(country.rules["can_send_volunteers"], "yes")

    def test_closure_retires_only_the_focus_owned_permission(self):
        for owns_focus in (False, True):
            script = self.campaign()
            country = script.scopes["WKR"]
            country.rules["can_send_volunteers"] = "yes"
            successor = script.scopes["WRK"]
            successor.rules["can_send_volunteers"] = "yes"
            if owns_focus:
                script.run(self.focuses[self.volunteers]["completion_reward"])
                country.focuses.add(self.volunteers)
            script.globals.add(V + "central_war_finished")
            script.effect("WKR_close_administration")
            script.effect("WKR_close_administration")
            self.assertEqual(country.rules["can_send_volunteers"], "no" if owns_focus else "yes")
            self.assertEqual(successor.rules, {"can_send_volunteers": "yes"})
            self.assertFalse(script.conditions(self.aggregate["enable"]))
        successor.focuses.add(self.volunteers)
        script.effect("WKR_close_administration", "WRK")
        self.assertEqual(successor.rules, {"can_send_volunteers": "yes"})

    def test_licence_choice_keeps_its_real_contract_and_refund(self):
        script = self.contracts.campaign()
        country = script.scopes["WKR"]
        reward = self.focuses[self.licences]["completion_reward"]
        self.assertEqual(fields(reward)["unlock_decision_tooltip"], "WKR_pattern_contract")
        self.assertEqual(fields(reward).get("custom_effect_tooltip"), "WKR_pattern_contract_unlock_tt")
        script.run(reward)
        bonus = fields(next(value for key, _, value in script.calls if key == "add_tech_bonus"))
        self.assertEqual((bonus["bonus"], bonus["uses"], bonus["category"]), ("0.5", "1", "infantry_weapons"))
        self.assertEqual(country.resources["pp"], 1000)
        self.assertTrue(self.contracts.start(script, "WKR_pattern_contract"))
        self.assertEqual(country.resources["pp"], 940)
        paid = deepcopy(script)
        order = self.contracts.orders["WKR_pattern_contract"]
        self.assertEqual(order["days_remove"], "28")
        script.run(order["remove_effect"])
        self.assertEqual(country.resources["support_equipment"], 100)
        self.assertIn(V + "wkr_licensed_patterns", country.flags)
        before = deepcopy((script.scopes, script.calls))
        script.run(order["remove_effect"])
        script.run(order["cancel_effect"])
        self.assertEqual((script.scopes, script.calls), before)
        paid.globals.add(V + "central_war_finished")
        paid.run(order["remove_effect"])
        self.assertEqual(paid.scopes["WKR"].resources["pp"], 1000)
        self.assertEqual(paid.scopes["WKR"].resources["support_equipment"], 0)


class WartimeProgrammeAccounting(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        decisions = parse(read("common/decisions/ADISCORD_vorkerland_decisions.txt"))
        cls.orders = {
            key: fields(value)
            for key, _, value in walk(decisions)
            if key.startswith("WKR_") and isinstance(value, list)
            and "WKR_programme_deposit" in str(value)
        }

    def campaign(self):
        script = Script()
        script.root = "WKR"
        script.globals = {V + "collapse_wars_started", V + "phase_regional_consolidation"}
        script.scopes["WKR"].resources["pp"] = 1000
        script.scopes["WKR"].focuses = {
            value for order in self.orders.values()
            for key, _, value in walk(order["visible"]) if key == "has_completed_focus"
        }
        script.scopes["32"].owner = "WKR"
        script.scopes["32"].controller = "WKR"
        script.scopes["32"].resources["arms_factory_slots"] = 1
        return script

    def start(self, script, name):
        order = self.orders[name]
        treasury = script.scopes["WKR"].resources
        if not script.conditions(order["visible"]) or not script.conditions(order["available"]):
            return False
        price = float(order["cost"])
        if treasury["pp"] < price:
            return False
        treasury["pp"] -= price
        script.run(order["complete_effect"])
        return True

    def test_every_order_excludes_all_other_orders_and_refunds_once(self):
        self.assertEqual(len(self.orders), 8)
        for name, order in self.orders.items():
            with self.subTest(order=name):
                script = self.campaign()
                self.assertTrue(self.start(script, name))
                paid = deepcopy(script.scopes["WKR"].resources)
                for other in self.orders:
                    self.assertFalse(self.start(script, other))
                self.assertEqual(script.scopes["WKR"].resources, paid)
                script.run(order["cancel_effect"])
                script.run(order["cancel_effect"])
                script.run(order["remove_effect"])
                self.assertEqual(script.scopes["WKR"].resources["pp"], 1000)
                self.assertNotIn("WKR_programme_deposit", script.scopes["WKR"].variables)
                self.assertFalse(script.scopes["WKR"].flags)
                self.assertFalse(script.calls)

    def test_fractional_native_price_and_successful_delivery(self):
        for name, order in self.orders.items():
            with self.subTest(order=name):
                script = self.campaign()
                price = float(order["cost"])
                script.scopes["WKR"].resources["pp"] = price - 0.01
                self.assertFalse(self.start(script, name))
                script.scopes["WKR"].resources["pp"] = price
                self.assertTrue(self.start(script, name))
                script = deepcopy(script)
                before = deepcopy((script.scopes, script.calls))
                script.run(order["remove_effect"])
                self.assertNotEqual((script.scopes, script.calls), before)
                self.assertEqual(script.scopes["WKR"].resources["pp"], 0)
                delivered = deepcopy((script.scopes, script.calls))
                script.run(order["remove_effect"])
                script.run(order["cancel_effect"])
                self.assertEqual((script.scopes, script.calls), delivered)
                self.assertNotIn("WKR_programme_deposit", script.scopes["WKR"].variables)

    def test_factory_delivery_rechecks_owner_controller_and_capacity(self):
        for loss in ("owner", "controller", "capacity"):
            with self.subTest(loss=loss):
                script = self.campaign()
                self.start(script, "WKR_workshop_contract")
                site = script.scopes["32"]
                if loss == "capacity":
                    site.resources["arms_factory_slots"] = 0
                else:
                    setattr(site, loss, "VAD")
                script.run(self.orders["WKR_workshop_contract"]["remove_effect"])
                self.assertEqual(site.resources["arms_factory"], 0)
                self.assertEqual(script.scopes["WKR"].resources["pp"], 1000)
                site.owner = site.controller = "WKR"
                site.resources["arms_factory_slots"] = 1
                self.assertTrue(self.start(script, "WKR_workshop_contract"))

    def test_terminal_conditions_cancel_without_delivery(self):
        for terminal in ("capitulated", "subject", "peace"):
            for name, order in self.orders.items():
                with self.subTest(terminal=terminal, order=name):
                    script = self.campaign()
                    self.start(script, name)
                    if terminal == "peace":
                        script.globals.add(V + "central_war_finished")
                    elif terminal == "subject":
                        script.scopes["WKR"].subject = "VAD"
                    else:
                        script.scopes["WKR"].capitulated = True
                    script.run(order["remove_effect"])
                    self.assertEqual(script.scopes["WKR"].resources["pp"], 1000)
                    self.assertFalse(script.calls)
                    self.assertFalse(self.start(script, name))

    def test_handoff_refunds_the_live_successor_and_invalidates_old_callbacks(self):
        for name, order in self.orders.items():
            with self.subTest(order=name):
                script = self.campaign()
                self.start(script, name)
                before = script.scopes["WRK"].resources["pp"]
                script.effect(V + "wkr_settle_programme_handoff", "WRK")
                script.effect(V + "wkr_settle_programme_handoff", "WRK")
                self.assertEqual(script.scopes["WRK"].resources["pp"], before + float(order["cost"]))
                delivered = deepcopy((script.scopes, script.calls))
                script.run(order["remove_effect"])
                script.run(order["cancel_effect"])
                self.assertEqual((script.scopes, script.calls), delivered)
        for route in ("wkr", "vad", "tva"):
            body = EFFECTS[V + "form_wrk_from_" + route]
            keys = [key for key, _, _ in walk(body)]
            self.assertLess(keys.index("transfer_state"), keys.index(V + "wkr_settle_programme_handoff"))

    def test_preview_deltas_equal_actual_cumulative_variables(self):
        source = parse(read("focus_trees/Vorkerland/wkr/focuses.txt"))
        focuses = {
            fields(value)["id"]: fields(value) for key, _, value in walk(source)
            if key == "focus" and isinstance(value, list)
        }
        ideas = {
            key: fields(value) for key, _, value in walk(parse(read("common/ideas/ADISCORD_vorkerland_ideas.txt")))
            if key.startswith(V + "wkr_") and isinstance(value, list) and "modifier" in fields(value)
        }
        script = self.campaign()
        script.effect(V + "wkr_initialize_measured_republic")
        accumulated = defaultdict(float)
        for focus in ("WKR_govern_by_delivered_results", "WKR_bind_the_republic_to_its_norms",
                      "WKR_doctrine_of_measured_force", "WKR_replace_men_with_output"):
            reward = focuses[focus]["completion_reward"]
            preview = fields(reward)["effect_tooltip"]
            idea = fields(preview)["add_ideas"]
            expected = fields(ideas[idea]["modifier"])
            runtime = [item for item in reward if item[0] != "effect_tooltip"]
            self.assertFalse(any(key == "add_ideas" for key, _, _ in walk(runtime)))
            writes = [item for item in walk(runtime) if item[0] == "add_to_variable"]
            script.run(writes)
            for field, value in expected.items():
                accumulated["WKR_norm_" + field] += float(value)
            for field, value in accumulated.items():
                self.assertAlmostEqual(script.scopes["WKR"].variables[field], value)
        consumer = fields(parse(read("common/dynamic_modifiers/ADISCORD_vorkerland_dynamic_modifiers.txt")))["WKR_measured_republic_dynamic"]
        for field, _, variable in consumer:
            if field not in ("icon", "enable"):
                self.assertIn(variable, accumulated)

    def test_wartime_tree_omits_prewar_branches_but_copies_shared_history_first(self):
        wartime = fields(parse(read("common/national_focus/ADISCORD_Vorkerland_wkr.txt")))["focus_tree"]
        self.assertFalse(any(key == "shared_focus" for key, _, _ in wartime))
        event = EVENTS["ADISCORD_vorkerland_collapse.1"]
        materialization = next(
            value for key, _, value in walk(event)
            if key == "WKR" and isinstance(value, list)
            and fields(value).get("inherit_technology") == "WRK"
        )
        trees = [fields(value) for key, _, value in materialization if key == "load_focus_tree"]
        self.assertEqual([tree["tree"] for tree in trees], [V + "prewar_focus", V + "wkr_focus"])
        self.assertEqual(trees[0]["copy_completed_from"], "WRK")
        self.assertEqual(trees[1]["keep_completed"], "yes")
        keys = [key for key, _, _ in materialization]
        self.assertLess(max(i for i, key in enumerate(keys) if key == "load_focus_tree"), keys.index("annex_country"))

    def test_core_plan_fits_preparation_window_and_selects_one_priority(self):
        plans = fields(parse(read("common/ai_strategy_plans/ADISCORD_vorkerland_plans.txt")))
        source = parse(read("focus_trees/Vorkerland/wkr/focuses.txt"))
        focuses = {
            fields(value)["id"]: value for key, _, value in walk(source)
            if key == "focus" and isinstance(value, list)
        }
        plan = fields(plans[V + "wkr_utilitarian_core_plan"])["ai_national_focuses"]
        names = [name for _, _, name in plan]
        self.assertEqual(names[-1], "WKR_republic_fights_as_one")
        done = set()
        for name in names:
            focus = focuses[name]
            for key, _, group in focus:
                if key == "prerequisite":
                    self.assertTrue({value for _, _, value in group} & done, name)
                if key == "mutually_exclusive":
                    self.assertFalse({value for _, _, value in group} & set(names), name)
            done.add(name)
        self.assertLessEqual(sum(float(fields(focuses[name])["cost"]) * 7 for name in names), 168)
        for name, other in (("WKR_authorize_normative_command", "WKR_bind_workshops_to_directive"),
                            ("WKR_bind_workshops_to_directive", "WKR_authorize_normative_command")):
            self.assertIn(other, str(fields(focuses[name])["mutually_exclusive"]))
            self.assertNotIn(V + "focus_wkr_central_war_unlocked", str(fields(focuses[name])["bypass"]))
        for name in ("WKR_govern_by_delivered_results", "WKR_settle_front_authority"):
            groups = [group for key, _, group in focuses[name] if key == "prerequisite"]
            self.assertTrue(any({'WKR_authorize_normative_command', 'WKR_bind_workshops_to_directive'} <=
                                {value for _, _, value in group} for group in groups))

    def test_prewar_plans_leave_time_for_paid_preparation(self):
        plans = fields(parse(read("common/ai_strategy_plans/ADISCORD_vorkerland_plans.txt")))
        source = parse(read("focus_trees/Vorkerland/prewar/focuses.txt"))
        focuses = {
            fields(value)["id"]: fields(value) for key, _, value in walk(source)
            if key == "focus" and isinstance(value, list)
        }
        longest_project = max(float(fields(project)["days_remove"]) for project in PROJECTS.values())
        for route in ("compact", "hardline"):
            plan = fields(plans[V + "wrk_prewar_" + route + "_plan"])["ai_national_focuses"]
            names = [name for _, _, name in plan]
            self.assertIn("WRK_last_common_budget", names)
            duration = sum(float(focuses[name]["cost"]) * 7 for name in names)
            self.assertLessEqual(duration + longest_project, 350)

    def test_all_wkr_icons_and_shines_use_matching_nonplaceholder_textures(self):
        sprites = {}
        for path in ("interface/ADISCORD_national_focus.gfx", "interface/ADISCORD_focus_shines.gfx"):
            for key, _, value in walk(parse(read(path))):
                if key.lower() == "spritetype":
                    data = fields(value)
                    sprites[data["name"].strip('"')] = data
        tree = parse(read("focus_trees/Vorkerland/wkr/focuses.txt"))
        for key, _, value in walk(tree):
            if key != "icon" or not isinstance(value, str) or not value.startswith("GFX_focus_WKR_"):
                continue
            texture = sprites[value]["texturefile"]
            self.assertNotIn("PLACEHOLDER", texture)
            self.assertEqual(sprites[value + "_shine"]["texturefile"], texture)


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
            self.assertLessEqual(finish_day(gate), 84)
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
                    self.assertLessEqual(finish + 21, 168)
                self.assertEqual(elapsed, 147)

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
            self.assertEqual(elapsed, 189)
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


class TVAAirProgrammeTests(unittest.TestCase):
    routes = {
        "strike_aircraft": ("TVA_print_unattended_strike_packages", 7, 120, 300, 21,
                            "ADISCORD_cas_airframe_2170", 24, 65, 25, 20, 10),
        "interceptor_reserve": ("TVA_keep_the_interdictors_on_station", 8, 100, 200, 28,
                                "ADISCORD_fighter_airframe_2163", 30, 80, 20, 10, 5),
    }

    @classmethod
    def setUpClass(cls):
        cls.base = TVAAdministrationTests()
        cls.base.setUpClass()
        cls.orders = {name: fields(cls.base.category[f"TVA_{name}_programme"])
                      for name in cls.routes}
        cls.focuses = {fields(value)["id"]: fields(value)
                       for key, _, value in walk(parse(read("focus_trees/Vorkerland/tva/focuses.txt")))
                       if key == "focus" and isinstance(value, list)}

    def campaign(self, name):
        script = self.base.campaign()
        script.scopes["TVA"].focuses.add(self.routes[name][0])
        script.scopes["38"] = Scope(owner="TVA", controller="TVA")
        script.scopes["38"].resources["air_base"] = 1
        script.scopes["37"] = Scope(owner="TVA", controller="TVA")
        script.scopes["37"].resources["arms_factory"] = 1
        return script

    def start(self, script, name):
        order = self.orders[name]
        if not all(script.conditions(order[key]) for key in ("visible", "available", "custom_cost_trigger")):
            return False
        script.run(order["complete_effect"])
        return True

    def test_exact_prices_and_shared_programme_receipt(self):
        for name, (_, kind, support, people, days, *_) in self.routes.items():
            for scarce in (None, "pp", "support_equipment", "people"):
                script = self.campaign(name)
                country = script.scopes["TVA"]
                country.resources.update(pp=40, support_equipment=support, people=people)
                if scarce:
                    country.resources[scarce] -= .01
                before = deepcopy(country.resources)
                self.assertEqual(self.start(script, name), scarce is None)
                if scarce:
                    self.assertEqual(country.resources, before)
                    continue
                self.assertEqual([country.resources[k] for k in ("pp", "support_equipment", "people")], [0, 0, 0])
                self.assertEqual(country.variables["TVA_programme_kind"], kind)
                self.assertEqual(self.orders[name]["days_remove"], str(days))
                before = deepcopy(script.scopes)
                script.effect("TVA_begin_" + name)
                self.assertEqual(script.scopes, before)
                self.assertFalse(self.base.start(script, "maintenance"))
                script = self.campaign(name)
                self.assertTrue(self.base.start(script, "maintenance"))
                self.assertFalse(self.start(script, name))

    def test_material_delivery_changes_current_capacity_once_and_allows_reordering(self):
        for name, (_, _, _, _, _, equipment, amount, max_load, min_cadre, load, cadre) in self.routes.items():
            script = self.campaign(name)
            country = script.scopes["TVA"]
            country.variables.update(TVA_network_load=max_load, TVA_cadre_reserve=min_cadre)
            self.assertTrue(self.start(script, name))
            script = deepcopy(script)
            country = script.scopes["TVA"]
            script.run(self.orders[name]["remove_effect"])
            self.assertEqual(country.resources[re.sub(r"_\d+$", "", equipment)], amount)
            delivered = [fields(value) for key, _, value in walk(EFFECTS["TVA_finish_" + name])
                         if key == "add_equipment_to_stockpile"]
            self.assertIn({"type": equipment, "amount": str(amount), "producer": "TVA"}, delivered)
            self.assertEqual(country.variables["TVA_network_load"], max_load + load)
            self.assertEqual(country.variables["TVA_cadre_reserve"], min_cadre - cadre)
            self.assertNotIn("TVA_programme_pp", country.variables)
            before = deepcopy(script.scopes)
            script.run(self.orders[name]["remove_effect"])
            script.run(self.orders[name]["cancel_effect"])
            self.assertEqual(script.scopes, before)
            self.assertFalse(self.start(script, name))
            country.variables.update(TVA_network_load=50, TVA_cadre_reserve=50)
            self.assertTrue(self.start(script, name))
            self.assertFalse(any(key == "add_timed_idea" for key, _, _ in script.calls))

    def test_payment_and_delivery_recheck_facilities_capacity_and_lifecycle(self):
        for name, cause in product(self.routes, ("airbase", "factory", "airbase_control", "factory_owner", "load", "cadre", "subject", "capitulation", "end")):
            with self.subTest(route=name, cause=cause):
                script = self.campaign(name)
                country = script.scopes["TVA"]
                before = deepcopy(country.resources)
                self.assertTrue(self.start(script, name))
                if cause == "airbase":
                    script.scopes["38"].resources["air_base"] = 0
                elif cause == "factory":
                    script.scopes["37"].resources["arms_factory"] = 0
                elif cause == "airbase_control":
                    script.scopes["38"].controller = "WKR"
                elif cause == "factory_owner":
                    script.scopes["37"].owner = "WKR"
                elif cause == "load":
                    country.variables["TVA_network_load"] = self.routes[name][7] + .01
                elif cause == "cadre":
                    country.variables["TVA_cadre_reserve"] = self.routes[name][8] - .01
                elif cause == "subject":
                    country.subject = "WKR"
                elif cause == "capitulation":
                    country.capitulated = True
                else:
                    script.globals.add(V + "central_war_finished")
                self.assertTrue(script.conditions(self.orders[name]["cancel_trigger"]))
                script.run(self.orders[name]["remove_effect"])
                script.run(self.orders[name]["cancel_effect"])
                self.assertEqual(country.resources, before)
                self.assertNotIn("TVA_programme_pp", country.variables)
                self.assertFalse(self.start(script, name))

    def test_wrong_kind_and_successor_handoff_cannot_deliver_aircraft(self):
        for name, (_, _, support, people, _, equipment, *_) in self.routes.items():
            script = self.campaign(name)
            self.assertTrue(self.start(script, name))
            before = deepcopy(script.scopes)
            other = next(key for key in self.routes if key != name)
            script.run(self.orders[other]["remove_effect"])
            script.run(self.orders[other]["cancel_effect"])
            self.assertEqual(script.scopes, before)
            recipient = script.scopes["WRK"]
            balances = deepcopy(recipient.resources)
            script.effect("TVA_settle_administration_handoff", "WRK")
            script.effect("TVA_settle_administration_handoff", "WRK")
            self.assertEqual(recipient.resources["pp"], balances["pp"] + 40)
            self.assertEqual(recipient.resources["support_equipment"], balances["support_equipment"] + support)
            self.assertEqual(recipient.resources["people"], balances["people"] + people)
            script.run(self.orders[name]["remove_effect"])
            self.assertEqual(script.scopes["TVA"].resources[re.sub(r"_\d+$", "", equipment)], 0)

    def test_choices_attach_to_laboratories_and_work_between_regional_wars(self):
        self.assertNotIn("TVA_stand_up_the_grid_air_staff", self.focuses)
        for name, (focus_id, *_) in self.routes.items():
            focus = self.focuses[focus_id]
            self.assertEqual(fields(focus["prerequisite"]), {"focus": "TVA_deploy_field_laboratories"})
            self.assertEqual(focus["cost"], "3")
            self.assertNotIn("bypass", focus)
            other = next(value[0] for key, value in self.routes.items() if key != name)
            self.assertEqual(fields(focus["mutually_exclusive"])["focus"], other)
            script = self.campaign(name)
            script.scopes["TVA"].enemies.clear()
            self.assertTrue(script.conditions(focus["available"]))
            self.assertTrue(self.start(script, name))

    def test_native_loss_callbacks_return_all_aircraft_order_payments_once(self):
        native = FieldTrialAccountingTests()
        native.setUpClass()
        for hook, name in product(("on_capitulation_immediate", "on_capitulation", "on_puppet", "on_annex"), self.routes):
            script = self.campaign(name)
            country = script.scopes["TVA"]
            self.assertTrue(self.start(script, name))
            recipient = "TVA"
            if hook == "on_annex":
                script.root = recipient = "VAD"
                script.source = "TVA"
                country.exists = False
            else:
                script.source = "VAD"
                if hook == "on_puppet":
                    country.subject = "VAD"
                else:
                    country.capitulated = True
            before = deepcopy(script.scopes[recipient].resources)
            script.run(native.trial_callback(hook))
            script.run(native.trial_callback(hook))
            self.assertEqual(script.scopes[recipient].resources["pp"], before["pp"] + 40)
            self.assertEqual(script.scopes[recipient].resources["support_equipment"], before["support_equipment"] + self.routes[name][2])
            self.assertEqual(script.scopes[recipient].resources["people"], before["people"] + self.routes[name][3])
            self.assertNotIn("TVA_programme_pp", country.variables)
            saved = deepcopy(script.scopes)
            script.run(self.orders[name]["remove_effect"], "TVA")
            self.assertEqual(script.scopes, saved)

    def test_delivered_airframes_have_native_missions_and_existing_tva_wings(self):
        equipment = fields(fields(parse(read("common/units/equipment/ADISCORD_air_equipment.txt")))["equipments"])
        wings = read("history/units/TVA_vorkerland_collapse_air.txt")
        for name, mission in (("strike_aircraft", "cas"), ("interceptor_reserve", "interception")):
            airframe = self.routes[name][5]
            definition = fields(equipment[airframe])
            self.assertIn(mission, str(definition["allow_mission_type"]))
            self.assertIn(airframe + " = {", wings)

    def test_air_choice_icons_and_shine_masks_use_the_inspected_action_textures(self):
        sprites = {}
        for path in ("interface/ADISCORD_national_focus.gfx", "interface/ADISCORD_focus_shines.gfx"):
            for key, _, value in walk(parse(read(path))):
                if key.lower() == "spritetype":
                    sprite = fields(value)
                    sprites[sprite["name"]] = sprite
        for name, texture in (("strike_aircraft", "focus_generic_cas_aircraft.dds"),
                               ("interceptor_reserve", "focus_generic_air_defense.dds")):
            icon = "GFX_focus_" + self.routes[name][0]
            expected = "gfx/interface/goals/" + texture
            self.assertEqual(sprites[icon]["texturefile"], expected)
            self.assertEqual(sprites[icon + "_shine"]["texturefile"], expected)
            self.assertEqual(fields(sprites[icon + "_shine"]["animation"])["animationmaskfile"], expected)
        self.assertNotIn("GFX_focus_TVA_stand_up_the_grid_air_staff", sprites)
        self.assertNotIn("GFX_focus_TVA_stand_up_the_grid_air_staff_shine", sprites)


class TVAAccountabilityTests(unittest.TestCase):
    routes = {
        "public_audit": ("TVA_publish_the_reconstruction_index", 5, 60, 0),
        "research_conversion": ("TVA_divert_the_research_budget", 6, 100, 600),
    }

    @classmethod
    def setUpClass(cls):
        cls.base = TVAAdministrationTests()
        cls.base.setUpClass()
        cls.orders = {name: fields(cls.base.category[f"TVA_{name}_programme"])
                      for name in cls.routes}

    def campaign(self, name):
        script = self.base.campaign()
        script.scopes["TVA"].focuses.add(self.routes[name][0])
        return script

    def start(self, script, name):
        order = self.orders[name]
        if not all(script.conditions(order[key]) for key in ("visible", "available", "custom_cost_trigger")):
            return False
        script.run(order["complete_effect"])
        return True

    def test_both_choices_open_after_trials_without_factory_or_policy_gate(self):
        source = fields(parse(read("focus_trees/Vorkerland/tva/focuses.txt")))
        focuses = {fields(value)["id"]: fields(value)
                   for key, _, value in source["focus_tree"] if key == "focus"}
        self.assertNotIn("TVA_certify_the_completed_programmes", focuses)
        for name, (focus_id, _, _, _) in self.routes.items():
            focus = focuses[focus_id]
            self.assertEqual(focus["cost"], "3")
            self.assertEqual(fields(focus["prerequisite"]), {"focus": "TVA_integrate_field_results"})
            for policy, trial in product(
                ("TVA_declare_continuous_mobilization", "TVA_enact_the_preservation_protocol"),
                ("TVA_test_adaptive_logistics", "TVA_test_remote_fire_control"),
            ):
                script = self.base.campaign()
                country = script.scopes["TVA"]
                country.focuses.update({policy, trial, "TVA_integrate_field_results"})
                script.globals.add(V + "phase_collapse")
                self.assertTrue(script.conditions(focus["available"]))
                self.assertFalse(self.start(script, name))
                script.run(focus["completion_reward"])
                country.focuses.add(focus_id)
                self.assertTrue(self.start(script, name))
                self.assertNotIn("bypass", focus)

    def test_reading_result_events_cannot_duplicate_or_reverse_settlement(self):
        for number in (27, 28, 29):
            script = self.campaign("public_audit")
            before = deepcopy(script.scopes)
            event = EVENTS[V + f"claimant.{number}"]
            self.assertNotIn("immediate", fields(event))
            options = [value for key, _, value in event if key == "option"]
            self.assertEqual(len(options), 1)
            acknowledgement = [entry for entry in options[0] if entry[0] != "name"]
            script.run(acknowledgement)
            script.run(acknowledgement)
            self.assertEqual(script.scopes, before)
            self.assertFalse(any(key == "country_event" for key, _, _ in script.calls))

    def test_exact_prices_and_shared_receipt_exclude_every_other_programme(self):
        for name, (_, kind, support, people) in self.routes.items():
            prices = {"pp": 35, "support_equipment": support}
            if people:
                prices["people"] = people
            for resource, price in prices.items():
                script = self.campaign(name)
                country = script.scopes["TVA"]
                country.resources[resource] = price - .01
                self.assertFalse(self.start(script, name))
                script.effect(f"TVA_begin_{name}")
                self.assertNotIn("TVA_programme_pp", country.variables)
                country.resources[resource] = price
                self.assertTrue(self.start(script, name))
                self.assertAlmostEqual(country.resources[resource], 0)
                self.assertEqual(country.variables["TVA_programme_kind"], kind)
                receipt = deepcopy(country)
                for other in self.routes:
                    country.focuses.add(self.routes[other][0])
                    self.assertFalse(self.start(script, other))
                script.effect("TVA_begin_maintenance")
                self.assertEqual(country.resources, receipt.resources)
                self.assertEqual(country.variables, receipt.variables)

    def test_old_receipt_cannot_be_overwritten_by_either_new_programme(self):
        for name in self.routes:
            script = self.campaign(name)
            self.assertTrue(self.base.start(script, "maintenance"))
            before = deepcopy(script.scopes["TVA"])
            self.assertFalse(self.start(script, name))
            script.effect(f"TVA_begin_{name}")
            self.assertEqual(script.scopes["TVA"], before)

    def test_public_report_grades_delivery_measurements_at_exact_boundaries(self):
        for load, cadre, successful in ((50, 50, True), (50.01, 50, False),
                                        (50, 49.99, False), (100, 0, False), (0, 100, True)):
            script = self.campaign("public_audit")
            country = script.scopes["TVA"]
            country.variables.update(TVA_network_load=90, TVA_cadre_reserve=10)
            self.assertTrue(self.start(script, "public_audit"))
            paid = deepcopy(country.resources)
            country.variables.update(TVA_network_load=load, TVA_cadre_reserve=cadre)
            self.assertFalse(script.conditions(self.orders["public_audit"]["cancel_trigger"]))
            script.run(self.orders["public_audit"]["remove_effect"])
            idea = "TVA_public_confidence" if successful else "TVA_public_accountability_crisis"
            self.assertIn(idea, country.flags)
            self.assertAlmostEqual(country.power_balances["TVA_bop"], -.2)
            self.assertEqual(country.variables[V + "legitimacy_delta"], .08 if successful else -.04)
            self.assertEqual(country.resources, paid)
            self.assertFalse(any(key.startswith("TVA_programme_") for key in country.variables))
            self.assertFalse(self.start(script, "public_audit"))
            self.assertEqual([fields(value)["id"] for key, _, value in script.calls if key == "country_event"],
                             [V + ("claimant.27" if successful else "claimant.28")])
            before = deepcopy((script.scopes, script.calls))
            script.run(self.orders["public_audit"]["remove_effect"])
            self.assertEqual((script.scopes, script.calls), before)

    def test_research_conversion_produces_paid_weapons_and_real_research_cost(self):
        script = self.campaign("research_conversion")
        country = script.scopes["TVA"]
        before = deepcopy(country.resources)
        country.variables["TVA_network_load"] = 95
        self.assertTrue(self.start(script, "research_conversion"))
        script.run(self.orders["research_conversion"]["remove_effect"])
        self.assertEqual(country.resources["infantry_equipment"], before["infantry_equipment"] + 1800)
        for currency, price in (("pp", 35), ("support_equipment", 100), ("people", 600)):
            self.assertEqual(country.resources[currency], before[currency] - price)
        self.assertEqual(country.variables["TVA_network_load"], 100)
        self.assertEqual(country.variables[V + "legitimacy_delta"], -.05)
        self.assertAlmostEqual(country.power_balances["TVA_bop"], -.4)
        self.assertIn("TVA_research_diversion", country.flags)
        self.assertFalse(self.start(script, "research_conversion"))
        self.assertEqual([fields(value)["days"] for key, _, value in script.calls if key == "add_timed_idea"], ["70"])
        before = deepcopy((script.scopes, script.calls))
        script.run(self.orders["research_conversion"]["remove_effect"])
        self.assertEqual((script.scopes, script.calls), before)

    def test_wrong_kind_callbacks_are_inert_and_loss_refunds_exactly_once(self):
        for name in self.routes:
            for reason in ("subject", "capitulation", "peace", "focus"):
                script = self.campaign(name)
                country = script.scopes["TVA"]
                resources = deepcopy(country.resources)
                self.assertTrue(self.start(script, name))
                other = next(key for key in self.routes if key != name)
                before = deepcopy((script.scopes, script.calls))
                script.run(self.orders[other]["remove_effect"])
                script.run(self.orders[other]["cancel_effect"])
                self.assertEqual((script.scopes, script.calls), before)
                if reason == "subject":
                    country.subject = "WKR"
                elif reason == "capitulation":
                    country.capitulated = True
                elif reason == "peace":
                    script.globals.add(V + "central_war_finished")
                else:
                    country.focuses.remove(self.routes[name][0])
                self.assertTrue(script.conditions(self.orders[name]["cancel_trigger"]))
                script.run(self.orders[name]["remove_effect"])
                script.run(self.orders[name]["cancel_effect"])
                self.assertEqual(country.resources, resources)
                self.assertFalse(any(key.startswith("TVA_programme_") for key in country.variables))
                self.assertFalse(any(key == "country_event" for key, _, _ in script.calls))

    def test_handoff_returns_receipt_to_successor_and_cleanup_removes_timed_results(self):
        for name, (_, _, support, people) in self.routes.items():
            script = self.campaign(name)
            self.assertTrue(self.start(script, name))
            target = script.scopes["WRK"]
            before = deepcopy(target.resources)
            script.effect("TVA_settle_administration_handoff", "WRK")
            script.effect("TVA_settle_administration_handoff", "WRK")
            for currency, price in (("pp", 35), ("support_equipment", support), ("people", people)):
                self.assertEqual(target.resources.get(currency, 0), before.get(currency, 0) + price)
            script.run(self.orders[name]["remove_effect"])
            self.assertFalse(any(key == "country_event" for key, _, _ in script.calls))
            script = self.campaign(name)
            country = script.scopes["TVA"]
            country.flags.update({"TVA_public_confidence", "TVA_public_accountability_crisis", "TVA_research_diversion"})
            script.effect("TVA_close_administration")
            self.assertFalse(country.flags & {"TVA_public_confidence", "TVA_public_accountability_crisis", "TVA_research_diversion"})

    def test_native_loss_callbacks_clear_completed_results_and_settle_pending_payment(self):
        native = FieldTrialAccountingTests()
        native.setUpClass()
        result_ideas = {"TVA_public_confidence", "TVA_public_accountability_crisis", "TVA_research_diversion"}
        for hook, name in product(
            ("on_capitulation_immediate", "on_capitulation", "on_puppet", "on_annex"), self.routes,
        ):
            with self.subTest(hook=hook, route=name):
                script = self.campaign(name)
                country = script.scopes["TVA"]
                self.assertTrue(self.start(script, name))
                script.run(self.orders[name]["remove_effect"])
                self.assertTrue(country.flags & result_ideas)
                self.assertTrue(self.base.start(script, "maintenance"))
                balance = deepcopy(country.power_balances)
                recipient = "TVA"
                if hook == "on_annex":
                    script.root = recipient = "VAD"
                    script.source = "TVA"
                    country.exists = False
                else:
                    script.source = "VAD"
                    if hook == "on_puppet":
                        country.subject = "VAD"
                    else:
                        country.capitulated = True
                before = deepcopy(script.scopes[recipient].resources)
                script.run(native.trial_callback(hook))
                script.run(native.trial_callback(hook))
                self.assertFalse(country.flags & result_ideas)
                self.assertEqual(script.scopes[recipient].resources["pp"], before["pp"] + 40)
                self.assertEqual(script.scopes[recipient].resources["support_equipment"], before["support_equipment"] + 80)
                self.assertFalse(any(key.startswith("TVA_programme_") for key in country.variables))
                self.assertEqual(country.power_balances, balance)
                other = self.campaign(name)
                other.scopes["TVA"].flags.update(result_ideas)
                other.root = "VAD" if hook == "on_annex" else "WKR"
                other.source = "WKR" if hook == "on_annex" else "VAD"
                before_other = deepcopy(other.scopes["TVA"])
                other.run(native.trial_callback(hook))
                self.assertEqual(other.scopes["TVA"], before_other)

    def test_focus_shine_matches_action_art_and_retired_alias_is_absent(self):
        def sprites(path):
            entries = fields(parse(read(path)))["spriteTypes"]
            return {fields(value)["name"].strip('"'): fields(value)
                    for key, _, value in entries if key.lower() == "spritetype"}

        ordinary = sprites("interface/ADISCORD_national_focus.gfx")
        shine = sprites("interface/ADISCORD_focus_shines.gfx")
        for focus_id, _, _, _ in self.routes.values():
            icon = "GFX_focus_" + focus_id
            texture = ordinary[icon]["texturefile"]
            self.assertEqual(shine[icon + "_shine"]["texturefile"], texture)
            self.assertEqual(fields(shine[icon + "_shine"]["animation"])["animationmaskfile"], texture)
        self.assertNotIn("GFX_focus_TVA_certify_the_completed_programmes", ordinary)
        self.assertNotIn("GFX_focus_TVA_certify_the_completed_programmes_shine", shine)


class TVASpecialistExchangeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        categories = fields(parse(read("common/decisions/ADISCORD_vorkerland_decisions.txt")))
        category = fields(categories[V + "tva_administration"])
        cls.offer = fields(category["TVA_offer_specialist_exchange"])
        cls.training = fields(category["TVA_cadre_training_programme"])
        cls.event = EVENTS[V + "diplomacy.18"]
        cls.options = [fields(value) for key, _, value in cls.event if key == "option"]

    def campaign(self):
        script = TVAAdministrationTests.campaign(self)
        script.scopes["TVA"].focuses.add("TVA_open_the_technical_exchange")
        script.scopes["EYR"].resources.update(people=600, support_equipment=0)
        script.scopes["EGC"].resources.update(people=600, support_equipment=0)
        return script

    def offer_to(self, script, target="EYR"):
        script.root = "TVA"
        script.source = target
        if not all(script.conditions(self.offer[key]) for key in ("target_trigger", "visible", "available")):
            return False
        script.scopes["TVA"].resources["pp"] -= float(self.offer["cost"])
        script.run(self.offer["complete_effect"])
        return True

    def accept(self, script, target="EYR"):
        script.root = target
        script.source = "TVA"
        if not script.conditions(self.options[1]["trigger"]):
            return False
        script.run(self.options[1]["hidden_effect"])
        return True

    def test_exact_prices_and_consent_transfer_existing_resources_once(self):
        self.assertNotIn("custom_cost_text", self.offer)
        self.assertEqual(self.offer["cost"], "10")
        delivery = EFFECTS["TVA_accept_specialist_exchange"]
        self.assertFalse(any(key == "add_equipment_to_stockpile" for key, _, _ in walk(delivery)))
        self.assertEqual([fields(value) for key, _, value in walk(delivery) if key == "send_equipment"], [
            {"target": "ROOT", "type": "support_equipment", "amount": "100"},
        ])
        for short in (None, "pp", "support_equipment"):
            script = self.campaign()
            donor = script.scopes["TVA"]
            donor.resources.update(pp=40, support_equipment=100)
            if short:
                donor.resources[short] -= .01
            before = deepcopy(script.scopes["EYR"].resources)
            self.assertEqual(self.offer_to(script), short is None)
            self.assertEqual(script.scopes["EYR"].resources, before)
            if short:
                continue
            self.assertEqual(donor.resources["pp"], 30)
            self.assertEqual(donor.resources["support_equipment"], 100)
            self.assertFalse(self.offer_to(script))
            self.assertTrue(self.accept(script))
            self.assertEqual(donor.resources["pp"], 0)
            self.assertEqual(donor.resources["support_equipment"], 0)
            self.assertEqual(donor.resources["people"], 6600)
            self.assertEqual(donor.variables["TVA_cadre_reserve"], 60)
            self.assertEqual(script.scopes["EYR"].resources["people"], 0)
            self.assertEqual(script.scopes["EYR"].resources["support_equipment"], 100)
            settled = deepcopy(script.scopes)
            script.effect("TVA_accept_specialist_exchange")
            self.assertEqual(script.scopes, settled)

    def test_acceptance_rechecks_both_countries_and_fractional_balances(self):
        cases = ("donor_pp", "donor_stock", "receiver_people", "donor_subject", "receiver_subject",
                 "donor_capitulated", "receiver_capitulated", "donor_absent", "receiver_absent",
                 "war", "central_end", "collapse_end", "unlock_lost")
        for case in cases:
            with self.subTest(case=case):
                script = self.campaign()
                self.assertTrue(self.offer_to(script))
                donor, receiver = script.scopes["TVA"], script.scopes["EYR"]
                if case == "donor_pp":
                    donor.resources["pp"] = 29.99
                elif case == "donor_stock":
                    donor.resources["support_equipment"] = 99.99
                elif case == "receiver_people":
                    receiver.resources["people"] = 599.99
                elif case.endswith("_subject"):
                    (donor if case.startswith("donor") else receiver).subject = "VAD"
                elif case.endswith("_capitulated"):
                    (donor if case.startswith("donor") else receiver).capitulated = True
                elif case.endswith("_absent"):
                    (donor if case.startswith("donor") else receiver).exists = False
                elif case == "war":
                    receiver.enemies.add("TVA")
                    donor.enemies.add("EYR")
                elif case == "central_end":
                    script.globals.add(V + "central_war_finished")
                elif case == "collapse_end":
                    script.globals.add(V + "collapse_finished")
                else:
                    donor.focuses.remove("TVA_open_the_technical_exchange")
                paid = [deepcopy(country.resources) for country in (donor, receiver)]
                self.assertFalse(self.accept(script))
                script.effect("TVA_accept_specialist_exchange")
                self.assertEqual([country.resources for country in (donor, receiver)], paid)
                self.assertNotIn("TVA_exchange_offer_pending", receiver.flags)

    def test_decline_and_unattended_timeout_only_keep_negotiation_fee(self):
        self.assertEqual(fields(self.event)["timeout_days"], "14")
        self.assertNotIn("trigger", self.options[0])
        self.assertGreater(int(self.offer["days_re_enable"]), 1 + int(fields(self.event)["timeout_days"]))
        script = self.campaign()
        initial = deepcopy(script.scopes["TVA"].resources)
        self.assertTrue(self.offer_to(script))
        script.root = "EYR"
        script.source = "TVA"
        script.run(self.options[0]["hidden_effect"])
        initial["pp"] -= 10
        self.assertEqual(script.scopes["TVA"].resources, initial)
        self.assertEqual(script.scopes["EYR"].resources["people"], 600)
        self.assertFalse(self.accept(script))

    def test_parallel_quotes_do_not_overdraw_and_close_on_handoff(self):
        script = self.campaign()
        script.scopes["TVA"].resources.update(pp=50, support_equipment=100)
        self.assertTrue(self.offer_to(script, "EYR"))
        self.assertTrue(self.offer_to(script, "EGC"))
        self.assertTrue(self.accept(script, "EYR"))
        self.assertFalse(self.accept(script, "EGC"))
        script.effect("TVA_accept_specialist_exchange")
        self.assertEqual(script.scopes["TVA"].resources["pp"], 0)
        self.assertEqual(script.scopes["EGC"].resources["people"], 600)
        targets = {value for _, _, value in self.offer["targets"]}
        closed = {key for key, _, _ in fields(EFFECTS["TVA_close_exchange_offers"])["if"] if key != "limit"}
        self.assertEqual(closed, targets)
        script = self.campaign()
        for tag in targets:
            self.assertTrue(self.offer_to(script, tag))
        script.effect("TVA_close_administration", "TVA")
        for tag in targets:
            self.assertNotIn("TVA_exchange_offer_pending", script.scopes[tag].flags)
        self.assertFalse(self.accept(script))

    def test_foreign_course_requires_a_reachable_independent_partner(self):
        script = self.campaign()
        targets = {value for _, _, value in self.offer["targets"]}
        partner_check = fields(TRIGGERS["TVA_exchange_has_partner"])["OR"]
        self.assertEqual({key for key, _, _ in partner_check}, targets)
        for tag in targets:
            script.scopes[tag].exists = False
        check = [("TVA_exchange_has_partner", "=", "yes")]
        self.assertFalse(script.conditions(check))
        script.scopes["EYR"].exists = True
        self.assertTrue(script.conditions(check))
        script.scopes["EYR"].subject = "VAD"
        self.assertFalse(script.conditions(check))
        script.scopes["EYR"].subject = None
        script.scopes["EYR"].enemies.add("TVA")
        self.assertFalse(script.conditions(check))

    def test_engineering_service_upgrades_pending_training_with_same_receipt(self):
        for course, reserve, expected in ((False, 50, 70), (True, 50, 85), (True, 90, 100)):
            script = self.campaign()
            donor = script.scopes["TVA"]
            donor.variables["TVA_cadre_reserve"] = reserve
            script.run(self.training["complete_effect"])
            self.assertEqual(donor.resources["pp"], 965)
            self.assertEqual(donor.resources["people"], 5400)
            if course:
                donor.focuses.add("TVA_build_the_engineering_service")
            script.run(self.training["remove_effect"])
            self.assertEqual(donor.variables["TVA_cadre_reserve"], expected)
            self.assertEqual(donor.variables["TVA_network_load"], 45)
            self.assertAlmostEqual(donor.power_balances["TVA_bop"], -.2)
            settled = deepcopy(script.scopes)
            script.run(self.training["remove_effect"])
            script.run(self.training["cancel_effect"])
            self.assertEqual(script.scopes, settled)

    def test_choice_requires_laboratories_and_each_ai_plan_chooses_one_course(self):
        source = parse(read("focus_trees/Vorkerland/tva/focuses.txt"))
        focuses = {
            fields(value)["id"]: value for key, _, value in walk(source)
            if key == "focus" and isinstance(value, list)
        }
        courses = ("TVA_open_the_technical_exchange", "TVA_build_the_engineering_service")
        for course, sibling in (courses, courses[::-1]):
            focus = focuses[course]
            self.assertEqual(fields(fields(focus)["mutually_exclusive"])["focus"], sibling)
            prerequisites = [{value for _, _, value in group} for key, _, group in focus if key == "prerequisite"]
            self.assertEqual(prerequisites, [{"TVA_publish_operational_metrics"}, {"TVA_deploy_field_laboratories"}])
            reward = fields(focus)["completion_reward"]
            self.assertTrue(any(key == "unlock_decision_tooltip" for key, _, _ in reward))
            self.assertFalse(any(key in ("add_timed_idea", "set_country_flag") for key, _, _ in walk(reward)))
        plans = fields(parse(read("common/ai_strategy_plans/ADISCORD_vorkerland_plans.txt")))
        for course, expected in (("throughput", courses[1]), ("preservation", courses[0])):
            plan = fields(plans[V + "tva_" + course + "_depth_plan"])
            names = {value for _, _, value in plan["ai_national_focuses"]}
            self.assertEqual(names.intersection(courses), {expected})
            self.assertLessEqual(names, set(focuses))

    def test_localisation_quotes_bom_and_dynamic_training_preview(self):
        loc = fields(next(value for key, _, value in parse(read("common/scripted_localisation/ADISCORD_vorkerland_scripted_loc.txt"))
                          if fields(value).get("name") == "GetTVACadreTrainingGain"))
        self.assertEqual(fields(loc["text"])["localization_key"], "TVA_cadre_training_gain_standard")
        for language in ("russian", "english"):
            path = ROOT / f"localisation/{language}/ADISCORD_vorkerland_l_{language}.yml"
            self.assertTrue(path.read_bytes().startswith(b"\xef\xbb\xbf"))
            raw = path.read_text(encoding="utf-8-sig")
            entries = dict(re.findall(r'^ ([\w.]+):\d* "((?:[^"\\\n]|\\.)*)"\r?$', raw, re.M))
            for key in ("TVA_cadre_training_programme_tt", "TVA_cadre_training_result_tt"):
                self.assertIn("[GetTVACadreTrainingGain]", entries[key])
            for key, _, value in walk(self.event):
                if key in ("title", "desc", "name", "custom_effect_tooltip"):
                    self.assertIn(value, entries)
            self.assertEqual(entries["TVA_cadre_training_gain_engineering"], "35")
            self.assertEqual(entries["TVA_cadre_training_gain_standard"], "20")


class TVAEconomyProgrammeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        categories = fields(parse(read("common/decisions/ADISCORD_vorkerland_decisions.txt")))
        category = fields(categories[V + "tva_administration"])
        cls.orders = {
            name: fields(category["TVA_" + name + "_programme"])
            for name in ("maintenance", "cadre_training", "emergency_series")
        }
        source = parse(read("focus_trees/Vorkerland/tva/focuses.txt"))
        cls.focuses = {
            fields(value)["id"]: fields(value) for key, _, value in walk(source)
            if key == "focus" and isinstance(value, list)
        }

    def campaign(self, course="war"):
        script = TVAAdministrationTests.campaign(self)
        country = script.scopes["TVA"]
        if course:
            country.focuses.add("TVA_run_the_grid_at_war_load" if course == "war" else "TVA_hold_back_civil_power")
        return script

    def start(self, script, name):
        return TVAAdministrationTests.start(self, script, name)

    def text_key(self, name, script):
        definitions = parse(read("common/scripted_localisation/ADISCORD_vorkerland_scripted_loc.txt"))
        definition = next((value for key, _, value in definitions if fields(value).get("name") == name), None)
        self.assertIsNotNone(definition, name)
        for key, _, value in definition:
            if key != "text":
                continue
            text = fields(value)
            if script.conditions(text.get("trigger", [])):
                return text["localization_key"]
        self.fail("No applicable localisation for " + name)

    def test_quoted_series_preview_and_delivery_survive_mid_order_course_change(self):
        script = self.campaign(course=None)
        country = script.scopes["TVA"]
        self.assertEqual(self.text_key("GetTVASeriesProgramme", script), "TVA_emergency_series_programme_standard_tt")
        self.assertTrue(self.start(script, "emergency_series"))
        country.focuses.add("TVA_run_the_grid_at_war_load")
        self.assertEqual(self.text_key("GetTVASeriesProgramme", script), "TVA_emergency_series_programme_standard_tt")
        country.variables.update(TVA_network_load=70, TVA_cadre_reserve=20)
        self.assertFalse(script.conditions(self.orders["emergency_series"]["cancel_trigger"]))
        self.assertFalse(script.conditions(TRIGGERS["TVA_emergency_series_available"]))
        script.run(self.orders["emergency_series"]["remove_effect"])
        self.assertEqual(country.resources["infantry_equipment"], 14500)
        self.assertEqual(country.resources["support_equipment"], 560)
        self.assertEqual(country.variables["TVA_network_load"], 90)
        self.assertEqual(country.variables["TVA_cadre_reserve"], 10)
        self.assertEqual(self.text_key("GetTVASeriesProgramme", script), "TVA_emergency_series_programme_war_tt")

    def test_war_course_opens_large_series_on_either_political_mandate(self):
        for balance in (-.5, 0, .5):
            script = self.campaign()
            country = script.scopes["TVA"]
            country.power_balances["TVA_bop"] = balance
            country.focuses.discard("TVA_optimize_for_throughput")
            country.variables.update(TVA_network_load=65, TVA_cadre_reserve=30)
            self.assertTrue(self.start(script, "emergency_series"))
            self.assertEqual(country.resources["pp"], 970)
            self.assertEqual(country.variables["TVA_programme_kind"], 4)
            self.assertEqual(country.resources["infantry_equipment"], 10000)
            script.run(self.orders["emergency_series"]["remove_effect"])
            self.assertEqual(country.resources["infantry_equipment"], 16000)
            self.assertEqual(country.resources["support_equipment"], 590)
            self.assertEqual(country.variables["TVA_network_load"], 95)
            self.assertEqual(country.variables["TVA_cadre_reserve"], 15)
            self.assertAlmostEqual(country.power_balances["TVA_bop"], balance - .1)
            self.assertAlmostEqual(country.variables["TVA_network_output"], -.09)
            self.assertAlmostEqual(country.variables["TVA_cadre_research"], -.035)
            settled = deepcopy(script.scopes)
            script.run(self.orders["emergency_series"]["remove_effect"])
            script.run(self.orders["emergency_series"]["cancel_effect"])
            self.assertEqual(script.scopes, settled)

    def test_large_series_bounds_are_rechecked_at_payment_and_delivery(self):
        for field, value in (("TVA_network_load", 65.01), ("TVA_cadre_reserve", 29.99), ("pp", 29.99)):
            for delay in (False, True):
                if delay and field == "pp":
                    continue
                with self.subTest(field=field, delay=delay):
                    script = self.campaign()
                    country = script.scopes["TVA"]
                    before = deepcopy(country.resources)
                    if delay:
                        self.assertTrue(self.start(script, "emergency_series"))
                    (country.resources if field == "pp" else country.variables)[field] = value
                    if delay:
                        self.assertTrue(script.conditions(self.orders["emergency_series"]["cancel_trigger"]))
                        script.run(self.orders["emergency_series"]["remove_effect"])
                        script.run(self.orders["emergency_series"]["cancel_effect"])
                        self.assertEqual(country.resources, before)
                    else:
                        changed = deepcopy(country.resources)
                        self.assertFalse(self.start(script, "emergency_series"))
                        script.effect("TVA_begin_emergency_series")
                        self.assertEqual(country.resources, changed)

    def test_all_programmes_share_one_slot_and_wrong_callback_cannot_refund_large_series(self):
        script = self.campaign()
        self.assertTrue(self.start(script, "emergency_series"))
        paid = deepcopy(script.scopes)
        for name, order in self.orders.items():
            self.assertFalse(self.start(script, name))
            if name != "emergency_series":
                script.run(order["cancel_effect"])
                script.run(order["remove_effect"])
        self.assertEqual(script.scopes, paid)

    def test_terminal_states_refund_large_series_and_handoff_pays_the_successor(self):
        for terminal in ("subject", "capitulation", "central_end", "collapse_end", "focus_lost"):
            script = self.campaign()
            country = script.scopes["TVA"]
            before = deepcopy(country.resources)
            self.assertTrue(self.start(script, "emergency_series"))
            if terminal == "subject":
                country.subject = "VAD"
            elif terminal == "capitulation":
                country.capitulated = True
            elif terminal == "central_end":
                script.globals.add(V + "central_war_finished")
            elif terminal == "collapse_end":
                script.globals.add(V + "collapse_finished")
            else:
                country.focuses.remove("TVA_run_the_grid_at_war_load")
            self.assertTrue(script.conditions(self.orders["emergency_series"]["cancel_trigger"]))
            script.run(self.orders["emergency_series"]["remove_effect"])
            script.run(self.orders["emergency_series"]["cancel_effect"])
            self.assertEqual(country.resources, before)
        script = self.campaign()
        self.assertTrue(self.start(script, "emergency_series"))
        script.root = "WRK"
        initial = script.scopes["WRK"].resources["pp"]
        script.effect("TVA_settle_administration_handoff")
        self.assertEqual(script.scopes["WRK"].resources["pp"], initial + 30)
        script.effect("TVA_close_administration", "TVA")
        script.effect("TVA_settle_administration_handoff")
        self.assertEqual(script.scopes["WRK"].resources["pp"], initial + 30)
        script.root = "TVA"
        script.run(self.orders["emergency_series"]["remove_effect"])
        self.assertEqual(script.scopes["TVA"].resources["infantry_equipment"], 10000)

    def test_civil_course_improves_pending_maintenance_without_changing_price(self):
        for initial, expected in ((50, 15), (20, 0)):
            script = self.campaign(course=None)
            country = script.scopes["TVA"]
            country.variables["TVA_network_load"] = initial
            self.assertTrue(self.start(script, "maintenance"))
            country.focuses.add("TVA_hold_back_civil_power")
            self.assertEqual(self.text_key("GetTVAMaintenanceReduction", script), "TVA_maintenance_reduction_civil")
            script.run(self.orders["maintenance"]["remove_effect"])
            self.assertEqual(country.resources["pp"], 960)
            self.assertEqual(country.resources["support_equipment"], 420)
            self.assertEqual(country.variables["TVA_network_load"], expected)
            self.assertEqual(country.variables["TVA_cadre_reserve"], 50)
            settled = deepcopy(script.scopes)
            script.run(self.orders["maintenance"]["remove_effect"])
            self.assertEqual(script.scopes, settled)

    def test_focus_choices_unlock_usable_distinct_programmes_after_reachable_prerequisites(self):
        prefix = ("TVA_codify_utilitarian_directorate", "TVA_reroute_city_grid", "TVA_issue_emergency_output_norms")
        for focus, programme in (("TVA_run_the_grid_at_war_load", "emergency_series"),
                                 ("TVA_hold_back_civil_power", "maintenance")):
            script = self.campaign(course=None)
            country = script.scopes["TVA"]
            country.focuses = set()
            country.variables.update(TVA_network_load=35, TVA_cadre_reserve=60)
            country.power_balances["TVA_bop"] = .5
            elapsed = 0
            done = set()
            for name in (*prefix, focus):
                raw = self.focuses[name]
                if "prerequisite" in raw:
                    self.assertTrue({value for _, _, value in raw["prerequisite"]} & done)
                done.add(name)
                country.focuses.add(name)
                elapsed += int(raw["cost"]) * 7
            self.assertEqual(elapsed, 56)
            script.run(self.focuses[focus]["completion_reward"])
            self.assertTrue(self.start(script, programme))
            self.assertEqual(elapsed + int(self.orders[programme]["days_remove"]), 70 if programme == "emergency_series" else 77)
            script.run(self.orders[programme]["remove_effect"])
            self.assertFalse(any(key == "add_dynamic_modifier" and fields(value)["modifier"] == V + "tva_war_economy"
                                 for key, _, value in walk(self.focuses[focus]["completion_reward"])))


class TVAFinalCadreTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        category = fields(fields(parse(read("common/decisions/ADISCORD_vorkerland_decisions.txt")))[V + "tva_administration"])
        cls.orders = {
            course: fields(category["TVA_" + focus + "_activate_plan"])
            for course, focus in (("spend", "spend_the_reserve_cadre"), ("protect", "seal_the_technical_core"))
        }

    def campaign(self, course):
        script = TVAAdministrationTests.campaign(self)
        country = script.scopes["TVA"]
        country.resources.update(pp=100, command=50, support_equipment=200)
        country.variables.update(TVA_cadre_reserve=60, TVA_protected_cadre=0)
        country.focuses.add("TVA_spend_the_reserve_cadre" if course == "spend" else "TVA_seal_the_technical_core")
        country.enemies = {"WKR"}
        for tag in ("WKR", "RUS"):
            script.scopes[tag]
        script.globals.add(V + "phase_central_showdown")
        return script

    def start(self, script, course):
        order = self.orders[course]
        if not all(script.conditions(order.get(key, [])) for key in ("visible", "available", "custom_cost_trigger")):
            return False
        script.run(order["complete_effect"])
        return True

    def test_each_operation_debits_exact_prices_and_never_pays_twice(self):
        for course, pp, command, support, protected in (("spend", 60, 30, 200, 0), ("protect", 65, 50, 100, 30)):
            script = self.campaign(course)
            country = script.scopes["TVA"]
            self.assertTrue(self.start(script, course))
            self.assertEqual(country.resources["pp"], pp)
            self.assertEqual(country.resources["command"], command)
            self.assertEqual(country.resources["support_equipment"], support)
            self.assertEqual(country.variables["TVA_cadre_reserve"], 30)
            self.assertEqual(country.variables["TVA_protected_cadre"], protected)
            self.assertEqual(self.orders[course]["fire_only_once"], "yes")
            durations = [fields(value)["days"] for key, _, value in script.calls if key == "add_timed_idea"]
            self.assertEqual(durations, ["70"])
            paid = deepcopy(script.scopes)
            self.assertFalse(self.start(script, course))
            script.run(self.orders[course]["complete_effect"])
            self.assertEqual(script.scopes, paid)

    def test_fractional_shortages_cannot_take_money_or_cadres(self):
        for course, prices in (("spend", {"pp": 40, "command": 20, "cadre": 30}),
                               ("protect", {"pp": 35, "support_equipment": 100, "cadre": 30})):
            for short in (*prices, None):
                script = self.campaign(course)
                country = script.scopes["TVA"]
                for name, value in prices.items():
                    if name == "cadre":
                        country.variables["TVA_cadre_reserve"] = value - (.01 if name == short else 0)
                    else:
                        country.resources[name] = value - (.01 if name == short else 0)
                before = deepcopy(script.scopes)
                self.assertEqual(self.start(script, course), short is None)
                if short:
                    script.run(self.orders[course]["complete_effect"])
                    self.assertEqual(script.scopes, before)

    def test_preparation_and_unrelated_wars_cannot_activate_the_operation(self):
        for course in self.orders:
            for terminal in ("prepare", "peace", "unrelated", "subject", "capitulation", "central_end", "collapse_end"):
                script = self.campaign(course)
                country = script.scopes["TVA"]
                if terminal == "prepare":
                    script.globals.discard(V + "phase_central_showdown")
                    script.globals.add(V + "phase_central_preparation")
                elif terminal == "peace":
                    country.enemies.clear()
                elif terminal == "unrelated":
                    country.enemies = {"RUS"}
                elif terminal == "subject":
                    country.subject = "VAD"
                elif terminal == "capitulation":
                    country.capitulated = True
                else:
                    script.globals.add(V + ("central_war_finished" if terminal == "central_end" else "collapse_finished"))
                before = deepcopy(script.scopes)
                self.assertFalse(self.start(script, course), (course, terminal))
                script.run(self.orders[course]["complete_effect"])
                self.assertEqual(script.scopes, before)

    def test_protected_reserve_survives_expiry_and_scales_successor_trials(self):
        script = self.campaign("protect")
        country = script.scopes["TVA"]
        self.assertTrue(self.start(script, "protect"))
        country.flags.discard(V + "tva_technical_core_sealed")
        country.variables["TVA_cadre_reserve"] = 0
        country.variables[V + "tva_iterations"] = 8
        script.effect("TVA_initialize_administration")
        self.assertEqual(country.variables["TVA_protected_cadre"], 30)
        self.assertFalse(self.start(script, "protect"))
        script.effect(V + "pw_record_trial_iterations", "WRK")
        self.assertAlmostEqual(script.scopes["WRK"].variables[V + "pw_iteration_efficiency"], .024)
        country.variables["TVA_cadre_reserve"] = 100
        script.effect(V + "pw_record_trial_iterations", "WRK")
        self.assertAlmostEqual(script.scopes["WRK"].variables[V + "pw_iteration_efficiency"], .08)
        script.effect("TVA_close_administration")
        self.assertEqual(country.variables["TVA_protected_cadre"], 30)

    def test_both_ideas_cancel_with_their_actual_conflict(self):
        ideas = fields(fields(parse(read("common/ideas/ADISCORD_vorkerland_ideas.txt")))["ideas"])
        ideas = fields(ideas["country"])
        for course, idea in (("spend", V + "tva_reserve_cadre_spent"), ("protect", V + "tva_technical_core_sealed")):
            script = self.campaign(course)
            self.assertTrue(self.start(script, course))
            cancel = fields(ideas[idea])["cancel"]
            self.assertFalse(script.conditions(cancel))
            script.globals.add(V + "central_war_finished")
            script.scopes["TVA"].enemies.add("RUS")
            self.assertTrue(script.conditions(cancel))


class TVATrialProtocolTests(unittest.TestCase):
    protocols = {
        "baseline": (None, {"pp": 30, "infantry_equipment": 9000}, "industry"),
        "battalion": ("TVA_raise_technical_battalions", {"pp": 30, "infantry_equipment": 6000, "people": 600}, "infantry_weapons"),
        "fire_control": ("TVA_test_remote_fire_control", {"pp": 35, "support_equipment": 120}, "electronics"),
        "logistics": ("TVA_test_adaptive_logistics", {"pp": 25, "support_equipment": 80}, "support_tech"),
    }

    @classmethod
    def setUpClass(cls):
        FieldTrialAccountingTests.setUpClass.__func__(cls)

    def campaign(self, protocol):
        script = FieldTrialAccountingTests.campaign(self)
        country = script.scopes["TVA"]
        country.resources.update(people=6000, support_equipment=500)
        focus = self.protocols[protocol][0]
        if focus:
            country.focuses.add(focus)
        for tag in ("WKR", "RUS", "VAD"):
            script.scopes[tag]
        return script

    def start(self, script):
        return FieldTrialAccountingTests.start(self, script)

    def text_key(self, name, script):
        return TVAEconomyProgrammeTests.text_key(self, name, script)

    def test_prices_have_exact_boundaries_and_duplicate_payment_is_blocked(self):
        for name, (_, prices, _) in self.protocols.items():
            for shortage in (*prices, None):
                with self.subTest(protocol=name, shortage=shortage):
                    script = self.campaign(name)
                    resources = script.scopes["TVA"].resources
                    for resource, price in prices.items():
                        resources[resource] = price - (.01 if shortage == resource else 0)
                    before = deepcopy(resources)
                    self.assertEqual(self.start(script), shortage is None)
                    expected = deepcopy(before)
                    if shortage is None:
                        for resource, price in prices.items():
                            expected[resource] -= price
                    self.assertEqual(resources, expected)
                    script.effect(V + "tva_begin_field_trial")
                    self.assertEqual(resources, expected)

    def test_paid_protocol_and_preview_survive_focus_completion_and_save_load(self):
        for name, (_, prices, category) in self.protocols.items():
            script = self.campaign(name)
            self.assertTrue(self.start(script))
            script = deepcopy(script)
            country = script.scopes["TVA"]
            country.focuses.add("TVA_test_remote_fire_control")
            self.assertEqual(self.text_key("GetTVATrialProtocol", script), "TVA_trial_" + name + "_name")
            self.assertEqual(self.text_key("GetTVATrialCost", script), "TVA_trial_" + name + "_cost")
            self.assertEqual(self.text_key("GetTVATrialCostBlocked", script), "TVA_trial_" + name + "_cost_blocked")
            self.assertFalse(self.start(script))
            script.run(self.order["remove_effect"])
            bonuses = [fields(value)["category"] for key, _, value in script.calls if key == "add_tech_bonus"]
            self.assertEqual(bonuses, [category])
            self.assertNotIn("TVA_trial_kind", country.variables)
            self.assertNotIn("TVA_trial_chance", country.variables)
            settled = deepcopy((script.scopes, script.calls))
            script.run(self.order["remove_effect"])
            script.run(self.order["cancel_effect"])
            self.assertEqual((script.scopes, script.calls), settled)

    def test_success_and_failure_deliver_distinct_results_and_one_iteration(self):
        for name, (_, _, category) in self.protocols.items():
            for outcome in (0, 1):
                with self.subTest(protocol=name, outcome=outcome):
                    script = self.campaign(name)
                    self.assertTrue(self.start(script))
                    script.random_index = outcome
                    script.run(self.order["remove_effect"])
                    country = script.scopes["TVA"]
                    self.assertEqual(country.variables[V + "tva_iterations"], 1)
                    self.assertEqual(country.variables["TVA_network_load"], 45)
                    self.assertEqual(country.variables["TVA_cadre_reserve"], 70 if name == "battalion" and outcome == 0 else 55)
                    self.assertEqual(country.resources["army_experience"], 10 if outcome else 15 if name == "fire_control" else 0)
                    bonuses = [fields(value)["category"] for key, _, value in script.calls if key == "add_tech_bonus"]
                    self.assertEqual(bonuses, [] if outcome else [category])
                    regimes = [fields(value) for key, _, value in script.calls if key == "add_timed_idea"]
                    self.assertEqual(regimes, [{"idea": V + "worx_adaptive_logistics_trial", "days": "70"}] if name == "logistics" and outcome == 0 else [])

    def test_every_interruption_returns_the_paid_resources_after_a_course_change(self):
        for name in self.protocols:
            for reason in ("peace", "unrelated", "subject", "capitulation", "central_end", "collapse_end"):
                with self.subTest(protocol=name, reason=reason):
                    script = self.campaign(name)
                    country = script.scopes["TVA"]
                    before = deepcopy(country.resources)
                    self.assertTrue(self.start(script))
                    country.focuses.add("TVA_test_adaptive_logistics")
                    if reason == "peace":
                        country.enemies.clear()
                    elif reason == "unrelated":
                        country.enemies = {"RUS"}
                    elif reason == "subject":
                        country.subject = "VAD"
                    elif reason == "capitulation":
                        country.capitulated = True
                    else:
                        script.globals.add(V + ("central_war_finished" if reason == "central_end" else "collapse_finished"))
                    self.assertTrue(script.conditions(self.order["cancel_trigger"]))
                    script.run(self.order["remove_effect"])
                    script.run(self.order["cancel_effect"])
                    self.assertEqual(country.resources, before)
                    self.assertNotIn("TVA_trial_kind", country.variables)
                    self.assertNotIn(V + "tva_iterations", country.variables)
                    self.assertFalse(self.start(script))

    def test_each_receipt_follows_the_living_recipient_once(self):
        for name, (_, prices, _) in self.protocols.items():
            for recipient in ("WRK", "VAD"):
                with self.subTest(protocol=name, recipient=recipient):
                    script = self.campaign(name)
                    self.assertTrue(self.start(script))
                    country = script.scopes["TVA"]
                    country.focuses.add("TVA_test_remote_fire_control")
                    country.exists = recipient == "WRK"
                    before = deepcopy(script.scopes[recipient].resources)
                    script.effect(V + "tva_settle_trial_handoff", recipient)
                    script.effect(V + "tva_settle_trial_handoff", recipient)
                    expected = deepcopy(before)
                    for resource, price in prices.items():
                        expected[resource] += price
                    self.assertEqual(script.scopes[recipient].resources, expected)
                    script.run(self.order["remove_effect"])
                    self.assertNotIn("TVA_trial_kind", country.variables)
                    self.assertFalse([call for call in script.calls if call[0] in ("add_tech_bonus", "country_event")])

    def test_logistic_regime_ends_with_independence_or_the_civil_war(self):
        ideas = fields(fields(parse(read("common/ideas/ADISCORD_vorkerland_ideas.txt")))["ideas"])
        cancel = fields(fields(ideas["country"])[V + "worx_adaptive_logistics_trial"])["cancel"]
        for reason in ("subject", "capitulation", "unrelated"):
            script = self.campaign("logistics")
            self.assertTrue(self.start(script))
            script.run(self.order["remove_effect"])
            self.assertFalse(script.conditions(cancel))
            if reason == "subject":
                script.scopes["TVA"].subject = "VAD"
            elif reason == "capitulation":
                script.scopes["TVA"].capitulated = True
            else:
                script.scopes["TVA"].enemies = {"RUS"}
            self.assertTrue(script.conditions(cancel))

    def test_protocol_event_commits_a_course_without_altering_paid_work(self):
        event = EVENTS[V + "claimant.23"]
        options = [value for key, _, value in event if key == "option"]
        for option, protocol, flag in zip(options,
                                          ("battalion", "fire_control", "logistics"),
                                          ("technical_battalions", "remote_fire_control", "adaptive_logistics")):
            script = self.campaign("baseline")
            self.assertTrue(self.start(script))
            country = script.scopes["TVA"]
            before = deepcopy((country.resources, country.variables))
            script.run([entry for entry in option if entry[0] not in ("name", "ai_chance")])
            self.assertEqual((country.resources, country.variables), before)
            self.assertIn(V + "tva_trial_" + flag, country.flags)
            self.assertIn(("custom_effect_tooltip", "=", "TVA_trial_" + protocol + "_choice_tt"), option)
            self.assertEqual(self.text_key("GetTVATrialProtocol", script), "TVA_trial_baseline_name")


class TVADoctrineProgrammeTests(unittest.TestCase):
    dispatch_idea = V + "tva_doctrine_line_replacement"
    training_preview = V + "tva_doctrine_fewer_better_crews"

    @classmethod
    def setUpClass(cls):
        TVAEconomyProgrammeTests.setUpClass.__func__(cls)

    def campaign(self, doctrine=None, war_load=False):
        script = TVAAdministrationTests.campaign(self)
        country = script.scopes["TVA"]
        if doctrine:
            country.focuses.add("TVA_doctrine_of_" + doctrine)
        if war_load:
            country.focuses.add("TVA_run_the_grid_at_war_load")
        for tag in ("WKR", "RUS"):
            script.scopes[tag]
        return script

    def start(self, script, programme):
        return TVAAdministrationTests.start(self, script, programme)

    def test_weapon_delivery_preserves_its_paid_tier_and_requires_a_civil_war(self):
        for war_load, conflict in product((False, True), ("civil", "peace", "external")):
            with self.subTest(war_load=war_load, conflict=conflict):
                script = self.campaign(war_load=war_load)
                country = script.scopes["TVA"]
                self.assertTrue(self.start(script, "emergency_series"))
                country.focuses.update({"TVA_doctrine_of_continuous_assault", "TVA_run_the_grid_at_war_load"})
                country.enemies = {"WKR"} if conflict == "civil" else {"RUS"} if conflict == "external" else set()
                script.run(self.orders["emergency_series"]["remove_effect"])
                self.assertEqual(country.resources["infantry_equipment"], 10000 + (6000 if war_load else 4500))
                self.assertEqual(country.resources["support_equipment"], 500 + (90 if war_load else 60))
                self.assertEqual(country.resources["pp"], 970)
                self.assertEqual(self.dispatch_idea in country.flags, conflict == "civil")
                settled = deepcopy((script.scopes, script.calls))
                script.run(self.orders["emergency_series"]["remove_effect"])
                script.run(self.orders["emergency_series"]["cancel_effect"])
                self.assertEqual((script.scopes, script.calls), settled)
        script = self.campaign()
        self.assertTrue(self.start(script, "emergency_series"))
        script.run(self.orders["emergency_series"]["remove_effect"])
        self.assertNotIn(self.dispatch_idea, script.scopes["TVA"].flags)

    def test_repeated_dispatch_resets_the_native_duration_and_close_removes_it(self):
        script = self.campaign("continuous_assault")
        country = script.scopes["TVA"]
        for _ in range(2):
            country.variables.update(TVA_network_load=50, TVA_cadre_reserve=50)
            self.assertTrue(self.start(script, "emergency_series"))
            script.run(self.orders["emergency_series"]["remove_effect"])
        regimes = [(key, fields(value)["days"] if key == "add_timed_idea" else value)
                   for key, _, value in script.calls if key in ("add_timed_idea", "remove_ideas")]
        self.assertEqual(regimes, [("add_timed_idea", "21"), ("remove_ideas", self.dispatch_idea), ("add_timed_idea", "21")])
        script.effect("TVA_close_administration")
        self.assertNotIn(self.dispatch_idea, country.flags)

    def test_full_reserve_allows_three_training_levels_and_ordinary_training_afterward(self):
        script = self.campaign("the_measured_front")
        country = script.scopes["TVA"]
        country.variables.update(TVA_cadre_reserve=100, TVA_policy_army_org_factor=.05,
                                 TVA_policy_experience_loss_factor=-.10)
        for level in range(1, 4):
            self.assertTrue(self.start(script, "cadre_training"))
            script.run(self.orders["cadre_training"]["remove_effect"])
            self.assertEqual(country.variables["TVA_crew_standards"], level)
            self.assertEqual(country.variables["TVA_cadre_reserve"], 100)
            self.assertAlmostEqual(country.variables["TVA_crew_organization"], .05 + level * .01)
            self.assertAlmostEqual(country.variables["TVA_crew_experience_loss"], -.10 - level * .03)
        self.assertEqual(country.resources["people"], 4200)
        self.assertEqual(country.resources["pp"], 895)
        self.assertFalse(self.start(script, "cadre_training"))
        country.variables["TVA_cadre_reserve"] = 60
        self.assertTrue(self.start(script, "cadre_training"))
        script.run(self.orders["cadre_training"]["remove_effect"])
        self.assertEqual(country.variables["TVA_cadre_reserve"], 80)
        self.assertEqual(country.variables["TVA_crew_standards"], 3)

    def test_pending_training_receives_the_new_course_without_changing_its_price(self):
        for engineering in (False, True):
            script = self.campaign()
            country = script.scopes["TVA"]
            self.assertTrue(self.start(script, "cadre_training"))
            country.focuses.add("TVA_doctrine_of_the_measured_front")
            if engineering:
                country.focuses.add("TVA_build_the_engineering_service")
            script.run(self.orders["cadre_training"]["remove_effect"])
            self.assertEqual(country.variables["TVA_crew_standards"], 1)
            self.assertEqual(country.variables["TVA_cadre_reserve"], 85 if engineering else 70)
            self.assertEqual(country.resources["pp"], 965)
            self.assertEqual(country.resources["people"], 5400)
            settled = deepcopy(script.scopes)
            script.run(self.orders["cadre_training"]["remove_effect"])
            self.assertEqual(script.scopes, settled)

    def test_terminal_callbacks_refund_without_awarding_doctrine_results(self):
        for programme, reason in product(("cadre_training", "emergency_series"),
                                         ("subject", "capitulation", "central_end", "collapse_end")):
            script = self.campaign("the_measured_front" if programme == "cadre_training" else "continuous_assault")
            country = script.scopes["TVA"]
            before = deepcopy(country.resources)
            self.assertTrue(self.start(script, programme))
            if reason == "subject":
                country.subject = "VAD"
            elif reason == "capitulation":
                country.capitulated = True
            else:
                script.globals.add(V + ("central_war_finished" if reason == "central_end" else "collapse_finished"))
            self.assertTrue(script.conditions(self.orders[programme]["cancel_trigger"]))
            script.run(self.orders[programme]["remove_effect"])
            script.run(self.orders[programme]["cancel_effect"])
            self.assertEqual(country.resources, before)
            self.assertEqual(country.variables.get("TVA_crew_standards", 0), 0)
            self.assertNotIn(self.dispatch_idea, country.flags)

    def test_standards_preview_matches_aggregate_and_reopening_preserves_it(self):
        ideas = fields(fields(parse(read("common/ideas/ADISCORD_vorkerland_ideas.txt")))["ideas"])
        preview = fields(fields(ideas["country"])[self.training_preview])
        delta = {key: float(value) for key, _, value in preview["modifier"]}
        self.assertEqual(delta, {"army_org_factor": .01, "experience_loss_factor": -.03})
        consumer = fields(fields(parse(read("common/dynamic_modifiers/ADISCORD_vorkerland_dynamic_modifiers.txt")))["TVA_administration_dynamic"])
        script = self.campaign("the_measured_front")
        country = script.scopes["TVA"]
        script.effect("TVA_refresh_administration")
        before = {modifier: country.variables[consumer[modifier]] for modifier in delta}
        self.assertTrue(self.start(script, "cadre_training"))
        script.run(self.orders["cadre_training"]["remove_effect"])
        for modifier, value in delta.items():
            self.assertAlmostEqual(country.variables[consumer[modifier]] - before[modifier], value)
        self.assertNotIn(self.training_preview, country.flags)
        stored = deepcopy(country.variables)
        script.effect("TVA_initialize_administration")
        self.assertEqual(country.variables, stored)
        script.effect("TVA_close_administration")
        self.assertNotIn("TVA_administration_dynamic", country.flags)
        self.assertEqual(country.variables["TVA_crew_standards"], 1)

    def test_doctrines_open_existing_programmes_without_linear_followups(self):
        self.assertNotIn("TVA_replace_losses_from_the_line", self.focuses)
        self.assertNotIn("TVA_hold_with_fewer_better_crews", self.focuses)
        for focus, programme in (("TVA_doctrine_of_continuous_assault", "emergency_series"),
                                 ("TVA_doctrine_of_the_measured_front", "cadre_training")):
            body = self.focuses[focus]
            self.assertEqual(int(body["cost"]) * 7, 21)
            self.assertIn(("unlock_decision_tooltip", "=", "TVA_" + programme + "_programme"), body["completion_reward"])
            script = self.campaign()
            script.scopes["TVA"].focuses.add(focus)
            script.scopes["TVA"].focuses.discard("TVA_deploy_field_laboratories")
            script.run(body["completion_reward"])
            self.assertTrue(script.conditions(self.orders[programme]["visible"]))
            self.assertTrue(self.start(script, programme))


class VADDistrictUnrestTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base = VADDistrictAdministrationTests()
        cls.base.setUpClass()
        cls.category = cls.base.category
        cls.dynamic = fields(parse(read("common/dynamic_modifiers/ADISCORD_vorkerland_dynamic_modifiers.txt")))
        cls.commandant = V + "vad_commandant_district"
        cls.revolt = V + "vad_district_uprising"

    def campaign(self, target="75"):
        script = self.base.campaign()
        self.assertTrue(self.base.start(script, "commandant", target))
        script.run(self.base.orders["commandant"]["remove_effect"])
        script.calls.clear()
        return script

    def order(self):
        return fields(self.category["VAD_restore_district_order"])

    def start(self, script, target="75"):
        script.source = target
        order = self.order()
        if not all(script.conditions(order[key]) for key in ("visible", "target_trigger", "available", "custom_cost_trigger")):
            return False
        script.run(order["complete_effect"])
        return True

    def test_monthly_pressure_uses_mandate_and_does_not_touch_charters(self):
        for balance, gain in ((-.61, 30), (-.60, 20), (.10, 20), (.11, 10)):
            with self.subTest(balance=balance):
                script = self.campaign()
                self.assertEqual(script.scopes["75"].variables["VAD_district_unrest"], 20)
                self.assertTrue(self.base.start(script, "charter", "106"))
                script.run(self.base.orders["charter"]["remove_effect"])
                script.scopes["VAD"].power_balances["VAD_bop"] = balance
                for _ in range(2):
                    script.effect("VAD_monthly_district_unrest")
                self.assertEqual(script.scopes["75"].variables["VAD_district_unrest"], 20 + 2 * gain)
                self.assertNotIn("VAD_district_unrest", script.scopes["106"].variables)
                self.assertNotIn(self.revolt, script.scopes["106"].flags)

    def test_threshold_disables_benefits_and_reports_once_for_the_whole_pulse(self):
        script = self.campaign()
        self.assertTrue(self.base.start(script, "commandant", "106"))
        script.run(self.base.orders["commandant"]["remove_effect"])
        commandant = fields(self.dynamic[self.commandant])
        revolt = fields(self.dynamic[self.revolt])
        self.assertEqual({key: float(revolt[key]) for key in
                         ("local_factories", "local_manpower", "local_supplies_for_controller", "army_speed_factor_for_controller")},
                         {"local_factories": -.35, "local_manpower": -.30,
                          "local_supplies_for_controller": -.25, "army_speed_factor_for_controller": -.10})
        for target in ("75", "106"):
            script.scopes[target].variables["VAD_district_unrest"] = 99
            self.assertTrue(script.conditions(commandant["enable"], target))
        script.calls.clear()
        for _ in range(3):
            script.effect("VAD_monthly_district_unrest")
        for target in ("75", "106"):
            self.assertEqual(script.scopes[target].variables["VAD_district_unrest"], 100)
            self.assertIn(self.revolt, script.scopes[target].flags)
            self.assertFalse(script.conditions(commandant["enable"], target))
            self.assertTrue(script.conditions(revolt["enable"], target))
        notifications = [fields(value)["id"] for key, _, value in script.calls if key == "country_event"]
        self.assertEqual(notifications, [V + "claimant.15"])

    def test_paid_order_has_exact_prices_one_slot_and_no_early_result(self):
        for pp, people, success in ((25, 500, True), (24.99, 500, False), (25, 499.99, False)):
            with self.subTest(pp=pp, people=people):
                script = self.campaign()
                state = script.scopes["75"]
                state.variables["VAD_district_unrest"] = 60
                country = script.scopes["VAD"]
                country.resources.update(pp=pp, people=people)
                self.assertEqual(self.start(script), success)
                self.assertEqual(country.resources["pp"], pp - 25 * success)
                self.assertEqual(country.resources["people"], people - 500 * success)
                self.assertEqual(state.variables["VAD_district_unrest"], 60)
                if success:
                    self.assertEqual(country.variables["VAD_oath_kind"], 3)
                    self.assertEqual(self.order()["days_remove"], "14")
                    self.assertFalse(self.base.start(script, "charter", "106"))
                    self.assertFalse(self.start(script, "106"))
                    script.source = "75"
                    script.effect("VAD_begin_district_order")
                    self.assertEqual((country.resources["pp"], country.resources["people"]), (0, 0))

    def test_response_handles_a_revolt_during_paid_work_and_repeated_callbacks(self):
        script = self.campaign()
        country = script.scopes["VAD"]
        state = script.scopes["75"]
        state.variables["VAD_district_unrest"] = 90
        self.assertTrue(self.start(script))
        script.effect("VAD_monthly_district_unrest")
        self.assertIn(self.revolt, state.flags)
        script.run(self.order()["remove_effect"])
        self.assertEqual(state.variables["VAD_district_unrest"], 40)
        self.assertNotIn(self.revolt, state.flags)
        self.assertIn(self.commandant, state.flags)
        self.assertTrue(script.conditions(fields(self.dynamic[self.commandant])["enable"], "75"))
        self.assertEqual(country.variables[V + "vad_commandants"], 1)
        self.base.assert_released(script)
        before = deepcopy(script.scopes)
        script.run(self.order()["remove_effect"])
        script.run(self.order()["cancel_effect"])
        self.assertEqual(script.scopes, before)

    def test_response_cancellation_and_living_handoff_return_exact_payment(self):
        for reason in ("owner", "controller", "subject", "capitulation", "peace", "handoff"):
            with self.subTest(reason=reason):
                script = self.campaign()
                state = script.scopes["75"]
                country = script.scopes["VAD"]
                state.variables["VAD_district_unrest"] = 80
                before = deepcopy(country.resources)
                self.assertTrue(self.start(script))
                if reason in ("owner", "controller"):
                    setattr(state, reason, "TVA")
                    script.source = "TVA"
                    script.effect("VAD_lose_district_administration", "75")
                    script.source = "75"
                    self.assertNotIn("VAD_district_unrest", state.variables)
                elif reason == "subject":
                    country.subject = "TVA"
                elif reason == "capitulation":
                    country.capitulated = True
                elif reason == "peace":
                    script.globals.add(V + "central_war_finished")
                else:
                    receiver = script.scopes["WRK"]
                    receiver_before = deepcopy(receiver.resources)
                    script.root = "WRK"
                    for _ in range(2):
                        script.effect("VAD_settle_oath_handoff")
                    self.assertEqual(receiver.resources["pp"], receiver_before["pp"] + 25)
                    self.assertEqual(receiver.resources["people"], receiver_before["people"] + 500)
                    script.root = "VAD"
                script.run(self.order()["remove_effect"])
                script.run(self.order()["cancel_effect"])
                self.base.assert_released(script)
                self.assertEqual(country.resources["pp"], before["pp"] - (25 if reason == "handoff" else 0))
                self.assertEqual(country.resources["people"], before["people"] - (500 if reason == "handoff" else 0))
                if reason in ("subject", "capitulation", "peace"):
                    self.assertEqual(state.variables["VAD_district_unrest"], 80)

    def test_withdrawal_keeps_sunk_costs_and_another_districts_receipt(self):
        script = self.campaign()
        state = script.scopes["75"]
        state.variables["VAD_district_unrest"] = 100
        script.effect("VAD_monthly_district_unrest")
        self.assertTrue(self.base.start(script, "charter", "106"))
        receipt = deepcopy(script.scopes["VAD"].variables)
        balances = deepcopy(script.scopes["VAD"].resources)
        script.source = "75"
        withdrawal = fields(self.category["VAD_withdraw_district_commandant"])
        self.assertTrue(script.conditions(withdrawal["available"]))
        script.run(withdrawal["complete_effect"])
        script.run(withdrawal["complete_effect"])
        self.assertEqual(script.scopes["VAD"].resources, balances)
        for key, value in receipt.items():
            if key.startswith("VAD_oath_"):
                self.assertEqual(script.scopes["VAD"].variables[key], value)
        self.assertEqual(script.scopes["VAD"].variables[V + "vad_commandants"], 0)
        self.assertFalse(state.flags)
        self.assertNotIn("VAD_district_unrest", state.variables)
        self.assertNotIn("75", script.arrays["global." + V + "vad_oath_states"])
        script.source = "106"
        script.run(self.base.orders["charter"]["remove_effect"])
        self.assertTrue(self.base.start(script, "commandant", "75"))
        script.run(self.base.orders["commandant"]["remove_effect"])
        self.assertEqual(state.variables["VAD_district_unrest"], 20)

    def test_old_target_cannot_settle_new_response_and_busy_target_cannot_withdraw(self):
        script = self.campaign()
        script.scopes["75"].variables["VAD_district_unrest"] = 60
        self.assertTrue(self.start(script))
        withdrawal = fields(self.category["VAD_withdraw_district_commandant"])
        self.assertFalse(script.conditions(withdrawal["available"]))
        script.effect("VAD_withdraw_district_commandant")
        self.assertIn(self.commandant, script.scopes["75"].flags)
        script.scopes["75"].controller = "TVA"
        script.effect("VAD_lose_district_administration", "75")
        self.assertTrue(self.base.start(script, "commandant", "106"))
        script.run(self.base.orders["commandant"]["remove_effect"])
        script.scopes["106"].variables["VAD_district_unrest"] = 60
        self.assertTrue(self.start(script, "106"))
        before = deepcopy(script.scopes)
        script.source = "75"
        script.run(self.order()["remove_effect"])
        script.run(self.order()["cancel_effect"])
        self.assertEqual(script.scopes, before)

    def test_notification_only_acknowledges_a_crisis_and_monthly_hook_is_unique(self):
        script = self.campaign()
        event = fields(EVENTS[V + "claimant.15"])
        self.assertNotIn("fire_only_once", event)
        self.assertTrue(script.conditions(event["trigger"]))
        before = deepcopy(script.scopes)
        script.run([entry for entry in event["option"] if entry[0] != "name"])
        self.assertEqual(script.scopes, before)
        script.globals.add(V + "central_war_finished")
        self.assertFalse(script.conditions(event["trigger"]))
        hooks = fields(fields(parse(read("common/on_actions/01_ADISCORD_vorkerland_collapse_on_actions.txt")))["on_actions"])
        calls = [name for name, body in hooks.items()
                 for key, _, _ in walk(body) if key == "VAD_monthly_district_unrest"]
        self.assertEqual(calls, ["on_monthly_VAD"])

    def test_another_claimants_cleanup_cannot_remove_vad_districts(self):
        script = self.campaign()
        before = deepcopy(script.scopes["75"])
        registered = list(script.arrays["global." + V + "vad_oath_states"])
        script.root = "WKR"
        script.effect("VAD_close_administration")
        self.assertEqual(script.scopes["75"], before)
        self.assertEqual(script.arrays["global." + V + "vad_oath_states"], registered)

    def test_current_save_state_survives_reopen_and_terminal_cleanup_stops_pressure(self):
        script = self.campaign()
        script.scopes["75"].variables["VAD_district_unrest"] = 100
        script.effect("VAD_monthly_district_unrest")
        before = deepcopy(script.scopes)
        script = deepcopy(script)
        script.effect("VAD_initialize_administration")
        self.assertEqual(script.scopes, before)
        script.globals.add(V + "central_war_finished")
        script.effect("VAD_close_administration")
        script.effect(V + "vad_retire_district_oaths")
        script.effect("VAD_monthly_district_unrest")
        self.assertFalse(script.scopes["75"].flags)
        self.assertNotIn("VAD_district_unrest", script.scopes["75"].variables)
        self.assertFalse(script.arrays["global." + V + "vad_oath_states"])
        self.assertEqual(script.scopes["VAD"].variables[V + "vad_commandants"], 1)


if __name__ == "__main__":
    unittest.main()


class VADDistrictRecruitmentTests(unittest.TestCase):
    routes = {
        "crown": ("charter", "VAD_issue_crown_mobilization_warrants", 4, 35, 60, 3000),
        "joint": ("commandant", "VAD_merge_guard_and_worker_rolls", 5, 30, 80, 4500),
    }

    @classmethod
    def setUpClass(cls):
        cls.base = VADDistrictAdministrationTests()
        cls.base.setUpClass()
        cls.orders = {name: fields(cls.base.category["VAD_" + name + "_district_recruitment"])
                      for name in cls.routes}
        cls.focuses = {fields(value)["id"]: fields(value)
                       for key, _, value in walk(parse(read("focus_trees/Vorkerland/vad/focuses.txt")))
                       if key == "focus" and isinstance(value, list)}

    def campaign(self, route):
        script = self.base.campaign()
        institution, focus, *_ = self.routes[route]
        self.assertTrue(self.base.start(script, institution))
        script.run(self.base.orders[institution]["remove_effect"])
        country = script.scopes["VAD"]
        country.focuses.add(focus)
        country.resources.update(pp=1000, people=10000, support_equipment=500)
        country.leader = "WRK_Vlad_Petrichev" if route == "crown" else "WRK_VAD_Joint_Council"
        if route == "joint":
            script.globals.update({V + "joint_government_formed", V + "worker_rescued_by_vlad"})
        script.calls.clear()
        return script

    def start(self, script, route, target="75"):
        script.source = target
        order = self.orders[route]
        if not all(script.conditions(order[key]) for key in
                   ("visible", "target_trigger", "available", "custom_cost_trigger")):
            return False
        script.run(order["complete_effect"])
        return True

    def test_exact_prices_shared_receipt_and_no_early_manpower(self):
        for route, (_, _, kind, pp, support, _) in self.routes.items():
            for treasury, stock, success in ((pp, support, True), (pp-.01, support, False),
                                             (pp, support-.01, False)):
                script = self.campaign(route)
                country = script.scopes["VAD"]
                country.resources.update(pp=treasury, support_equipment=stock)
                self.assertEqual(self.start(script, route), success)
                self.assertEqual(country.resources["pp"], treasury - pp * success)
                self.assertEqual(country.resources["support_equipment"], stock - support * success)
                self.assertEqual(country.resources["people"], 10000)
                if success:
                    self.assertEqual(country.variables["VAD_oath_kind"], kind)
                    paid = deepcopy(country.resources)
                    script.effect("VAD_begin_" + route + "_recruitment")
                    self.assertEqual(country.resources, paid)
                    self.assertFalse(self.base.start(script, "commandant", "106"))
                    self.assertFalse(self.start(script, route))
                    self.assertEqual(self.orders[route]["days_remove"], "21")

    def test_delivery_consumes_one_cohort_and_has_route_specific_cost(self):
        for route, (_, _, _, pp, support, recruits) in self.routes.items():
            script = self.campaign(route)
            self.assertTrue(self.start(script, route))
            script = deepcopy(script)
            country = script.scopes["VAD"]
            state = script.scopes["75"]
            script.run(self.orders[route]["remove_effect"])
            self.assertEqual(country.resources["people"], 10000 + recruits)
            self.assertEqual(country.resources["pp"], 1000 - pp)
            self.assertEqual(country.resources["support_equipment"], 500 - support)
            self.assertEqual(state.variables["VAD_district_recruited"], recruits)
            self.base.assert_released(script)
            if route == "crown":
                self.assertIn("VAD_crown_recruitment_disruption", state.flags)
                self.assertNotIn("VAD_district_unrest", state.variables)
            else:
                self.assertEqual(state.variables["VAD_district_unrest"], 50)
            delivered = deepcopy((script.scopes, script.calls))
            script.run(self.orders[route]["remove_effect"])
            script.run(self.orders[route]["cancel_effect"])
            self.assertEqual((script.scopes, script.calls), delivered)
            self.assertFalse(self.start(script, route))

    def test_cancellation_refunds_every_currency_once_without_consuming_cohort(self):
        for route, reason in product(self.routes, ("control", "owner", "subject", "capitulation", "peace")):
            script = self.campaign(route)
            country = script.scopes["VAD"]
            before = deepcopy(country.resources)
            self.assertTrue(self.start(script, route))
            if reason == "control":
                script.scopes["75"].controller = "WKR"
            elif reason == "owner":
                script.scopes["75"].owner = "WKR"
            elif reason == "subject":
                country.subject = "WKR"
            elif reason == "capitulation":
                country.capitulated = True
            else:
                script.globals.add(V + "central_war_finished")
            self.assertTrue(script.conditions(self.orders[route]["cancel_trigger"]))
            script.run(self.orders[route]["remove_effect"])
            script.run(self.orders[route]["cancel_effect"])
            self.assertEqual(country.resources, before)
            self.assertEqual(script.scopes["75"].variables["VAD_district_recruited"], 0)
            self.base.assert_released(script)

    def test_handoff_returns_equipment_to_living_recipient_once(self):
        for route, (_, _, _, pp, support, _) in self.routes.items():
            script = self.campaign(route)
            self.assertTrue(self.start(script, route))
            recipient = script.scopes["WRK"]
            before = deepcopy(recipient.resources)
            script.scopes["VAD"].exists = False
            script.effect("VAD_settle_oath_handoff", "WRK")
            script.effect("VAD_settle_oath_handoff", "WRK")
            self.assertEqual(recipient.resources["pp"], before["pp"] + pp)
            self.assertEqual(recipient.resources["support_equipment"], before["support_equipment"] + support)
            self.assertEqual(recipient.resources["people"], before["people"])
            settled = deepcopy(script.scopes)
            script.run(self.orders[route]["cancel_effect"])
            script.run(self.orders[route]["remove_effect"])
            self.assertEqual(script.scopes, settled)
            self.base.assert_released(script)

    def test_revolt_during_work_cancels_but_recruitment_may_itself_cause_revolt(self):
        for during in (False, True):
            script = self.campaign("joint")
            state = script.scopes["75"]
            state.variables["VAD_district_unrest"] = 80
            before = deepcopy(script.scopes["VAD"].resources)
            self.assertTrue(self.start(script, "joint"))
            if during:
                script.effect("VAD_monthly_district_unrest")
                self.assertTrue(script.conditions(self.orders["joint"]["cancel_trigger"]))
            script.run(self.orders["joint"]["remove_effect"])
            self.assertIn(V + "vad_district_uprising", state.flags)
            self.assertEqual(state.variables["VAD_district_unrest"], 100)
            self.assertEqual(state.variables["VAD_district_recruited"], 0 if during else 4500)
            self.assertEqual(script.scopes["VAD"].resources["people"], before["people"] + (0 if during else 4500))
            if during:
                self.assertEqual(script.scopes["VAD"].resources, before)
            reports = [fields(value)["id"] for key, _, value in script.calls if key == "country_event"]
            self.assertEqual(reports, [V + "claimant.15"])

    def test_loss_rebuilding_and_retirement_preserve_actual_recruited_count(self):
        for route, (institution, _, _, _, _, recruits) in self.routes.items():
            script = self.campaign(route)
            self.assertTrue(self.start(script, route))
            script.run(self.orders[route]["remove_effect"])
            state = script.scopes["75"]
            state.controller = "WKR"
            script.effect("VAD_lose_district_administration", "75")
            self.assertNotIn("VAD_crown_recruitment_disruption", state.flags)
            state.controller = "VAD"
            self.assertTrue(self.base.start(script, institution))
            script.run(self.base.orders[institution]["remove_effect"])
            self.assertEqual(state.variables["VAD_district_recruited"], recruits)
            self.assertFalse(self.start(script, route))
            script.effect("VAD_close_administration")
            self.assertEqual(state.variables["VAD_district_recruited"], recruits)
            self.assertNotIn("VAD_crown_recruitment_disruption", state.flags)

    def test_stale_callbacks_cannot_settle_other_target_or_kind(self):
        for route in self.routes:
            script = self.campaign(route)
            self.assertTrue(self.start(script, route))
            paid = deepcopy(script.scopes)
            script.source = "106"
            script.run(self.orders[route]["remove_effect"])
            script.run(self.orders[route]["cancel_effect"])
            self.assertEqual(script.scopes, paid)
            script.source = "75"
            other = "joint" if route == "crown" else "crown"
            script.run(self.orders[other]["remove_effect"])
            script.run(self.orders[other]["cancel_effect"])
            self.assertEqual(script.scopes, paid)

    def test_focus_programmes_require_local_institution_and_show_real_unlocks(self):
        for route, (_, focus, *_rest) in self.routes.items():
            script = self.campaign(route)
            body = self.focuses[focus]
            self.assertTrue(script.conditions(body["available"]))
            before = deepcopy(script.scopes["VAD"].resources)
            script.run(body["completion_reward"])
            self.assertEqual(script.scopes["VAD"].resources, before)
            self.assertIn(("unlock_decision_tooltip", "=", "VAD_" + route + "_district_recruitment"), body["completion_reward"])
            self.assertTrue(self.start(script, route))
            script.run(self.orders[route]["remove_effect"])
            self.assertFalse(script.conditions(body["available"]))
            self.assertNotIn("bypass", body)


class UnifiedPrewarTreeTests(unittest.TestCase):
    def test_wrk_preparation_has_one_entry_and_every_focus_reaches_it(self):
        focuses = {fields(value)["id"]: fields(value)
                   for key, _, value in walk(parse(read("focus_trees/Vorkerland/prewar/focuses.txt")))
                   if key == "focus" and isinstance(value, list) and fields(value)["id"].startswith("WRK_")}
        parents = {name: {target for key, _, target in walk(body.get("prerequisite", [])) if key == "focus"}
                   for name, body in focuses.items()}
        roots = {name for name, required in parents.items() if not required}
        self.assertEqual(roots, {"WRK_measure_confederation_fault_lines"})
        self.assertNotIn("WRK_face_the_hourglass", focuses)
        reached = set(roots)
        while True:
            expanded = reached | {name for name, required in parents.items() if required & reached}
            if expanded == reached:
                break
            reached = expanded
        self.assertEqual(reached, set(focuses))
        root = focuses["WRK_measure_confederation_fault_lines"]
        self.assertEqual(root["cost"], "3")
        reward = fields(root["completion_reward"])
        self.assertEqual(reward["add_political_power"], "75")
        self.assertIn(("custom_effect_tooltip", "=", "WRK_prewar_programmes_tt"), root["completion_reward"])


class WKRAirRailProgrammeTests(unittest.TestCase):
    routes = {
        "airfield_workshop": ("WKR_commit_shopfloor_squadrons", 2, 40, 80, 400, 21),
        "armoured_train": ("WKR_screen_the_interchange_sky", 3, 35, 120, 600, 35),
    }

    @classmethod
    def setUpClass(cls):
        cls.base = WKRRailwayCouncilTests()
        cls.base.setUpClass()
        category = fields(fields(parse(read("common/decisions/ADISCORD_vorkerland_decisions.txt")))[V + "wkr_administration"])
        cls.orders = {name: fields(category[f"WKR_{name}_programme"]) for name in cls.routes}

    def campaign(self, name):
        script = self.base.campaign()
        country = script.scopes["WKR"]
        for state in ("32", "33"):
            self.assertTrue(self.base.start(script, state))
            script.run(self.base.order["remove_effect"])
            script.scopes[state].resources.update(air_base=2, arms_factory=2)
        country.focuses.add(self.routes[name][0])
        country.resources.update(pp=1000, support_equipment=1000, people=10000)
        script.source = "32"
        script.calls.clear()
        return script

    def start(self, script, name, target="32"):
        script.source = target
        order = self.orders[name]
        if not all(script.conditions(order.get(key, [])) for key in
                   ("visible", "target_trigger", "available", "custom_cost_trigger")):
            return False
        script.run(order["complete_effect"])
        return True

    def test_three_currency_boundaries_and_shared_queue_in_both_directions(self):
        for name, (_, kind, pp, support, people, days) in self.routes.items():
            for missing in (None, "pp", "support_equipment", "people"):
                script = self.campaign(name)
                country = script.scopes["WKR"]
                country.resources.update(pp=pp, support_equipment=support, people=people)
                if missing:
                    country.resources[missing] -= .01
                before = deepcopy(script.scopes)
                self.assertEqual(self.start(script, name), missing is None)
                if missing:
                    self.assertEqual(script.scopes, before)
                    continue
                self.assertEqual([country.resources[key] for key in ("pp", "support_equipment", "people")], [0, 0, 0])
                self.assertEqual(country.variables["WKR_railway_order_kind"], kind)
                self.assertEqual(self.orders[name]["days_remove"], str(days))
                paid = deepcopy(script.scopes)
                script.effect("WKR_begin_" + name)
                self.assertEqual(script.scopes, paid)
                country.resources.update(pp=1000, support_equipment=1000, people=10000)
                script.scopes["34"].owner = script.scopes["34"].controller = "WKR"
                script.scopes["34"].resources["supply_node"] = 1
                self.assertFalse(self.base.start(script, "34"))
                self.assertFalse(self.start(script, name, "33"))
            script = self.campaign(name)
            script.scopes["34"].owner = script.scopes["34"].controller = "WKR"
            script.scopes["34"].resources["supply_node"] = 1
            self.assertTrue(self.base.start(script, "34"))
            self.assertEqual(script.scopes["WKR"].variables["WKR_railway_order_kind"], 1)
            self.assertFalse(self.start(script, name))

    def test_local_workshop_and_preview_agree_and_rebuild_requires_full_payment(self):
        script = self.campaign("airfield_workshop")
        self.assertTrue(self.start(script, "airfield_workshop"))
        script = deepcopy(script)
        script.run(self.orders["airfield_workshop"]["remove_effect"])
        self.assertIn("WKR_airfield_workshop", script.scopes["32"].flags)
        self.assertNotIn("WKR_airfield_workshop", script.scopes["33"].flags)
        self.assertFalse(self.start(script, "airfield_workshop"))
        self.base.assert_closed(script)
        preview = [value for key, _, value in walk(self.orders["airfield_workshop"]["complete_effect"])
                   if key == "add_dynamic_modifier"]
        delivered = [value for key, _, value in script.calls if key == "add_dynamic_modifier"]
        self.assertEqual(preview, delivered)
        modifiers = fields(parse(read("common/dynamic_modifiers/ADISCORD_vorkerland_dynamic_modifiers.txt")))
        bonus = fields(modifiers["WKR_airfield_workshop"])
        self.assertEqual(bonus["state_repair_speed_air_base_factor"], "1.00")
        self.assertEqual(bonus["local_factories"], "-0.05")
        self.assertTrue(script.conditions(bonus["enable"], "32"))
        script.scopes["32"].controller = "VAD"
        self.assertFalse(script.conditions(bonus["enable"], "32"))
        script.effect("WKR_lose_railway_council", "32")
        self.assertNotIn("WKR_airfield_workshop", script.scopes["32"].flags)
        script.scopes["32"].controller = "WKR"
        self.assertTrue(self.base.start(script, "32"))
        script.run(self.base.order["remove_effect"])
        self.assertTrue(self.start(script, "airfield_workshop"))
        script.run(self.orders["airfield_workshop"]["remove_effect"])
        script.effect("WKR_close_railway_councils")
        self.assertNotIn("WKR_airfield_workshop", script.scopes["32"].flags)

    def test_national_train_order_has_no_target_and_delivers_real_armoured_equipment(self):
        script = self.campaign("armoured_train")
        self.assertNotIn("state_target", self.orders["armoured_train"])
        self.assertTrue(self.start(script, "armoured_train", "VAD"))
        self.assertNotIn("WKR_railway_order_state", script.scopes["WKR"].variables)
        self.assertFalse(any("WKR_railway_in_progress" in scope.flags for scope in script.scopes.values()))
        script.scopes.setdefault("35", Scope())
        before = deepcopy(script.scopes)
        script.effect("WKR_lose_railway_council", "35")
        self.assertEqual(script.scopes, before)
        script.run(self.orders["armoured_train"]["remove_effect"])
        country = script.scopes["WKR"]
        self.assertEqual(country.resources["armored_train_equipment"], 8)
        script.effect("WKR_close_administration")
        self.assertEqual(country.resources["armored_train_equipment"], 8)
        equipment = fields(fields(parse(read("common/units/equipment/ADISCORD_train_equipment.txt")))["equipments"])
        train = fields(equipment["armored_train_equipment_1"])
        self.assertEqual(train["archetype"], "train_equipment")
        self.assertGreater(float(train["armor_value"]), 0)
        self.assertGreater(float(train["air_attack"]), 0)

    def test_all_three_kinds_ignore_foreign_callbacks_and_wrong_targets(self):
        for name in self.routes:
            script = self.campaign(name)
            self.assertTrue(self.start(script, name))
            before = deepcopy(script.scopes)
            other = next(key for key in self.routes if key != name)
            for order in (self.base.order, self.orders[other]):
                script.run(order["remove_effect"])
                script.run(order["cancel_effect"])
            if name == "airfield_workshop":
                script.source = "33"
                script.run(self.orders[name]["remove_effect"])
                script.run(self.orders[name]["cancel_effect"])
            self.assertEqual(script.scopes, before)
            script.source = "32"
            script.run(self.orders[name]["remove_effect"])
            before = deepcopy(script.scopes)
            script.run(self.orders[name]["remove_effect"])
            script.run(self.orders[name]["cancel_effect"])
            self.assertEqual(script.scopes, before)

    def test_lost_assets_or_country_context_refund_all_currencies_once(self):
        for name, reason in product(self.routes, ("owner", "controller", "partial", "council", "building", "subject", "capitulation", "peace")):
            with self.subTest(route=name, reason=reason):
                script = self.campaign(name)
                country = script.scopes["WKR"]
                before = deepcopy(country.resources)
                self.assertTrue(self.start(script, name))
                for target in ("32", "33"):
                    state = script.scopes[target]
                    if reason in ("owner", "controller"):
                        setattr(state, reason, "VAD")
                    elif reason == "partial":
                        state.fully_controlled = False
                    elif reason == "council":
                        state.flags.discard("WKR_railway_council")
                    elif reason == "building":
                        state.resources["air_base" if name == "airfield_workshop" else "arms_factory"] = 0
                if reason == "subject":
                    country.subject = "VAD"
                elif reason == "capitulation":
                    country.capitulated = True
                elif reason == "peace":
                    script.globals.add(V + "central_war_finished")
                self.assertTrue(script.conditions(self.orders[name]["cancel_trigger"]))
                script.run(self.orders[name]["remove_effect"])
                script.run(self.orders[name]["cancel_effect"])
                self.assertEqual(country.resources, before)
                self.base.assert_closed(script)
                self.assertNotIn("WKR_airfield_workshop", script.scopes["32"].flags)

    def test_native_callbacks_pay_victim_or_successor_once(self):
        native = FieldTrialAccountingTests()
        native.setUpClass()
        for hook, name in product(("on_capitulation_immediate", "on_capitulation", "on_puppet", "on_annex"), self.routes):
            script = self.campaign(name)
            self.assertTrue(self.start(script, name))
            recipient = "WKR"
            if hook == "on_annex":
                script.root = recipient = "VAD"
                script.source = "WKR"
                script.scopes["WKR"].exists = False
            else:
                script.source = "VAD"
                script.scopes["WKR"].capitulated = hook != "on_puppet"
                script.scopes["WKR"].subject = "VAD" if hook == "on_puppet" else None
            body = fields(native.hooks[hook])["effect"]
            callbacks = [item for item in body if any(key in ("WKR_refund_railway_order", "WKR_settle_railway_handoff")
                         for key, _, _ in walk([item]))]
            self.assertEqual(len(callbacks), 1)
            before = deepcopy(script.scopes[recipient].resources)
            script.run(callbacks)
            script.run(callbacks)
            for resource, price in zip(("pp", "support_equipment", "people"), self.routes[name][2:5]):
                self.assertEqual(script.scopes[recipient].resources[resource], before[resource] + price)
            self.base.assert_closed(script)

    def test_both_mandates_keep_orders_and_summary_names_actual_kind(self):
        body = next(value for key, _, value in parse(read("common/scripted_localisation/ADISCORD_vorkerland_scripted_loc.txt"))
                    if key == "defined_text" and fields(value)["name"] == "GetWKRRailwayOrder")
        for name in self.routes:
            script = self.campaign(name)
            country = script.scopes["WKR"]
            country.leader = "WRK_Nikita_Worcker"
            self.assertTrue(self.start(script, name))
            country.leader = "WRK_Anton_Bagley"
            self.assertFalse(script.conditions(self.orders[name]["cancel_trigger"]))
            selected = next(fields(value)["localization_key"] for key, _, value in body
                            if key == "text" and ("trigger" not in fields(value) or script.conditions(fields(value)["trigger"])))
            self.assertEqual(selected, f"WKR_railway_order_{name}")
            for language in ("russian", "english"):
                line = next(line for line in read(f"localisation/{language}/ADISCORD_vorkerland_l_{language}.yml").splitlines()
                            if line.startswith(" " + selected + ":"))
                self.assertEqual("WKR_railway_order_state.GetName" in line, name == "airfield_workshop")


class WKRFinalOperationsTests(unittest.TestCase):
    routes = {
        "breakthrough": ("WKR_throw_the_reserves_forward", 4, 40, 150, 600, 14),
        "interchange_defence": ("WKR_dig_in_along_the_interchange", 5, 35, 100, 800, 21),
    }

    @classmethod
    def setUpClass(cls):
        cls.air = WKRAirRailProgrammeTests()
        cls.air.setUpClass()
        cls.base = cls.air.base
        cls.category = fields(fields(parse(read("common/decisions/ADISCORD_vorkerland_decisions.txt")))[V + "wkr_administration"])

    def order(self, name):
        key = f"WKR_{name}_programme"
        self.assertIn(key, self.category)
        return fields(self.category[key])

    def campaign(self, name):
        script = self.air.campaign("armoured_train")
        script.scopes["WKR"].focuses.add(self.routes[name][0])
        script.scopes["WKR"].enemies = {"VAD"}
        script.globals.discard(V + "phase_central_preparation")
        script.globals.add(V + "phase_central_showdown")
        return script

    def start(self, script, name, target="32"):
        script.source = target
        order = self.order(name)
        if not all(script.conditions(order.get(key, [])) for key in
                   ("visible", "target_trigger", "available", "custom_cost_trigger")):
            return False
        script.run(order["complete_effect"])
        return True

    def test_focus_prepares_both_mandates_before_war_without_starting_the_bonus(self):
        focuses = {fields(value)["id"]: fields(value) for key, _, value in
                   fields(parse(read("focus_trees/Vorkerland/wkr/focuses.txt")))["focus_tree"] if key == "focus"}
        self.assertNotIn("WKR_the_last_levy", focuses)
        for name, route in self.routes.items():
            focus = focuses[route[0]]
            self.assertEqual(fields(focus["prerequisite"])["focus"], "WKR_republic_fights_as_one")
            self.assertEqual(float(focus["cost"]), 3)
            for leader in ("WRK_Nikita_Worcker", "WRK_Anton_Bagley"):
                script = self.campaign(name)
                script.scopes["WKR"].leader = leader
                script.scopes["WKR"].enemies.clear()
                script.globals.discard(V + "phase_central_showdown")
                script.globals.add(V + "phase_central_preparation")
                self.assertTrue(script.conditions(focus["available"]))
                self.assertNotIn("add_timed_idea", {key for key, _, _ in walk(focus["completion_reward"])})
                self.assertEqual(self.start(script, name), name == "interchange_defence")
                self.assertEqual(21 + route[-1], 35 if name == "breakthrough" else 42)

    def test_exact_prices_and_all_five_orders_share_the_receipt(self):
        for name, (_, kind, pp, support, people, days) in self.routes.items():
            for missing in (None, "pp", "support_equipment", "people"):
                script = self.campaign(name)
                country = script.scopes["WKR"]
                country.resources.update(pp=pp, support_equipment=support, people=people)
                if missing:
                    country.resources[missing] -= .01
                before = deepcopy(country.resources)
                self.assertEqual(self.start(script, name), missing is None)
                for key, price in zip(("pp", "support_equipment", "people"), (pp, support, people)):
                    self.assertAlmostEqual(country.resources[key], before[key] - price * (missing is None))
                if missing:
                    continue
                self.assertEqual(country.variables["WKR_railway_order_kind"], kind)
                self.assertEqual(self.order(name)["days_remove"], str(days))
                paid = deepcopy(script.scopes)
                script.effect("WKR_begin_" + name)
                self.assertEqual(script.scopes, paid)
                for order in (self.base.order, *self.air.orders.values()):
                    script.run(order["complete_effect"])
                    script.run(order["remove_effect"])
                    script.run(order["cancel_effect"])
                other = next(key for key in self.routes if key != name)
                script.scopes["WKR"].focuses.add(self.routes[other][0])
                script.run(self.order(other)["complete_effect"])
                script.run(self.order(other)["remove_effect"])
                script.run(self.order(other)["cancel_effect"])
                self.assertEqual(country.resources, paid["WKR"].resources)
                self.assertEqual(country.variables, paid["WKR"].variables)
            for old in ("council", "airfield_workshop", "armoured_train"):
                script = self.campaign(name)
                if old == "council":
                    script.scopes["34"].owner = script.scopes["34"].controller = "WKR"
                    script.scopes["34"].resources["supply_node"] = 1
                    self.assertTrue(self.base.start(script, "34"))
                else:
                    script.scopes["WKR"].focuses.add(self.air.routes[old][0])
                    self.assertTrue(self.air.start(script, old))
                before = deepcopy(script.scopes)
                self.assertFalse(self.start(script, name))
                script.run(self.order(name)["remove_effect"])
                script.run(self.order(name)["cancel_effect"])
                self.assertEqual(script.scopes, before)

    def test_offensive_delivery_matches_preview_and_requires_the_actual_claimant_war(self):
        script = self.campaign("breakthrough")
        order = self.order("breakthrough")
        self.assertNotIn("state_target", order)
        self.assertTrue(self.start(script, "breakthrough", "VAD"))
        self.assertNotIn("WKR_railway_order_state", script.scopes["WKR"].variables)
        self.assertFalse(any("WKR_railway_in_progress" in scope.flags for scope in script.scopes.values()))
        script.run(order["remove_effect"])
        preview = [value for key, _, value in walk(order["complete_effect"]) if key == "add_timed_idea"]
        delivered = [value for key, _, value in script.calls if key == "add_timed_idea"]
        self.assertEqual(preview, delivered)
        self.assertEqual(fields(delivered[0]), {"idea": V + "wkr_reserves_forward", "days": "35"})
        self.assertFalse(self.start(script, "breakthrough"))
        idea = fields(fields(fields(parse(read("common/ideas/ADISCORD_vorkerland_ideas.txt")))["ideas"])["country"])
        cancel = fields(idea[V + "wkr_reserves_forward"])["cancel"]
        self.assertFalse(script.conditions(cancel))
        script.scopes["WKR"].enemies = {"RUS"}
        self.assertTrue(script.conditions(cancel))
        script.effect("WKR_close_administration")
        self.assertNotIn(V + "wkr_reserves_forward", script.scopes["WKR"].flags)
        self.base.assert_closed(script)

    def test_local_defences_preview_tradeoff_loss_and_paid_rebuild(self):
        script = self.campaign("interchange_defence")
        order = self.order("interchange_defence")
        self.assertTrue(self.start(script, "interchange_defence"))
        before = deepcopy(script.scopes)
        script.source = "33"
        script.run(order["remove_effect"])
        script.run(order["cancel_effect"])
        self.assertEqual(script.scopes, before)
        script.source = "32"
        script.run(order["remove_effect"])
        self.assertIn("WKR_prepared_interchange", script.scopes["32"].flags)
        preview = [value for key, _, value in walk(order["complete_effect"]) if key == "add_dynamic_modifier"]
        self.assertEqual(preview, [value for key, _, value in script.calls if key == "add_dynamic_modifier"])
        modifier = fields(fields(parse(read("common/dynamic_modifiers/ADISCORD_vorkerland_dynamic_modifiers.txt")))["WKR_prepared_interchange"])
        self.assertEqual({key: value for key, value in modifier.items() if key not in ("icon", "enable")}, {
            "local_supplies": "0.25", "enemy_army_speed_factor": "-0.10", "enemy_attrition": "0.10", "local_factories": "-0.10",
        })
        self.assertTrue(script.conditions(modifier["enable"], "32"))
        script.scopes["32"].fully_controlled = False
        self.assertFalse(script.conditions(modifier["enable"], "32"))
        script.scopes["32"].fully_controlled = True
        script.scopes["32"].controller = "VAD"
        script.effect("WKR_lose_railway_council", "32")
        self.assertNotIn("WKR_prepared_interchange", script.scopes["32"].flags)
        script.scopes["32"].controller = "WKR"
        self.assertTrue(self.base.start(script, "32"))
        script.run(self.base.order["remove_effect"])
        self.assertTrue(self.start(script, "interchange_defence"))
        script.run(order["remove_effect"])
        script.effect("WKR_close_railway_councils")
        self.assertNotIn("WKR_prepared_interchange", script.scopes["32"].flags)
        self.assertGreaterEqual(sum(key == "ADISCORD_economy_mark_dirty" for key, _, _ in script.calls), 3)

    def test_context_losses_refund_once_and_external_war_does_not_keep_an_offensive_order(self):
        for name in self.routes:
            for loss in ("owner", "controller", "partial", "council", "hub", "subject", "capitulation", "peace", "external"):
                if loss == "external" and name != "breakthrough":
                    continue
                script = self.campaign(name)
                country = script.scopes["WKR"]
                before = deepcopy(country.resources)
                self.assertTrue(self.start(script, name))
                if loss in ("owner", "controller", "partial", "council", "hub"):
                    for target in ("32", "33"):
                        state = script.scopes[target]
                        if loss in ("owner", "controller"):
                            setattr(state, loss, "TVA")
                        elif loss == "partial":
                            state.fully_controlled = False
                        elif loss == "council":
                            state.flags.discard("WKR_railway_council")
                        else:
                            state.resources["supply_node"] = 0
                elif loss == "subject":
                    country.subject = "TVA"
                elif loss == "capitulation":
                    country.capitulated = True
                elif loss == "external":
                    country.enemies = {"RUS"}
                else:
                    script.globals.add(V + "central_war_finished")
                self.assertTrue(script.conditions(self.order(name)["cancel_trigger"]), (name, loss))
                script.run(self.order(name)["remove_effect"])
                script.run(self.order(name)["cancel_effect"])
                self.assertEqual(country.resources, before)
                self.base.assert_closed(script)

    def test_native_loss_and_handoff_callbacks_refund_current_receipt_once(self):
        native = FieldTrialAccountingTests()
        native.setUpClass()
        for hook, name in product(("on_capitulation_immediate", "on_capitulation", "on_puppet", "on_annex"), self.routes):
            script = self.campaign(name)
            self.assertTrue(self.start(script, name))
            recipient = "WKR"
            if hook == "on_annex":
                script.root = recipient = "TVA"
                script.source = "WKR"
                script.scopes["WKR"].exists = False
            else:
                script.source = "TVA"
                script.scopes["WKR"].capitulated = hook != "on_puppet"
                script.scopes["WKR"].subject = "TVA" if hook == "on_puppet" else None
            callbacks = [item for item in fields(native.hooks[hook])["effect"] if any(
                key in ("WKR_refund_railway_order", "WKR_settle_railway_handoff") for key, _, _ in walk([item]))]
            self.assertEqual(len(callbacks), 1)
            before = deepcopy(script.scopes[recipient].resources)
            script.run(callbacks)
            script.run(callbacks)
            for resource, price in zip(("pp", "support_equipment", "people"), self.routes[name][2:5]):
                self.assertEqual(script.scopes[recipient].resources[resource], before[resource] + price)
            self.base.assert_closed(script)

    def test_pending_summary_and_government_change_keep_the_actual_order(self):
        body = next(value for key, _, value in parse(read("common/scripted_localisation/ADISCORD_vorkerland_scripted_loc.txt"))
                    if key == "defined_text" and fields(value)["name"] == "GetWKRRailwayOrder")
        for name in self.routes:
            script = self.campaign(name)
            self.assertTrue(self.start(script, name))
            script.scopes["WKR"].leader = "WRK_Anton_Bagley"
            self.assertFalse(script.conditions(self.order(name)["cancel_trigger"]))
            selected = next(fields(value)["localization_key"] for key, _, value in body if key == "text"
                            and script.conditions(fields(value).get("trigger", [])))
            self.assertEqual(selected, f"WKR_railway_order_{name}")
            for language in ("russian", "english"):
                line = next(line for line in read(f"localisation/{language}/ADISCORD_vorkerland_l_{language}.yml").splitlines()
                            if line.startswith(" " + selected + ":"))
                self.assertEqual("WKR_railway_order_state.GetName" in line, name == "interchange_defence")


class VADAirDistrictTests(unittest.TestCase):
    routes = {
        "forward_airfield": ("VAD_task_the_guards_for_close_support", 12, 40, 120, 500, 28, "air_base"),
        "district_air_defence": ("VAD_cover_the_district_capitals", 13, 45, 100, 800, 35, "anti_air_building"),
    }

    @classmethod
    def setUpClass(cls):
        cls.base = VADDistrictAdministrationTests()
        cls.base.setUpClass()
        cls.orders = {name: fields(cls.base.category[f"VAD_{name}_programme"])
                      for name in cls.routes}

    def campaign(self, name, charter=False):
        script = self.base.campaign()
        for target in ("75", "106"):
            self.assertTrue(self.base.start(script, "charter" if charter else "commandant", target))
            script.run(self.base.orders["charter" if charter else "commandant"]["remove_effect"])
            script.scopes[target].resources.update(air_base=0, air_base_slots=10,
                                                    anti_air_building=0, anti_air_building_slots=5)
        country = script.scopes["VAD"]
        country.focuses.add(self.routes[name][0])
        country.resources.update(pp=1000, support_equipment=1000, people=10000)
        script.source = "75"
        script.calls.clear()
        return script

    def start(self, script, name, target="75"):
        script.source = target
        order = self.orders[name]
        if not all(script.conditions(order[key]) for key in
                   ("visible", "target_trigger", "available", "custom_cost_trigger")):
            return False
        script.run(order["complete_effect"])
        return True

    def test_exact_payment_shared_slot_and_double_click_guard(self):
        for name, (_, kind, pp, support, people, days, _) in self.routes.items():
            for scarce in (None, "pp", "support_equipment", "people"):
                script = self.campaign(name)
                country = script.scopes["VAD"]
                country.resources.update(pp=pp, support_equipment=support, people=people)
                if scarce:
                    country.resources[scarce] -= .01
                before = deepcopy(country.resources)
                self.assertEqual(self.start(script, name), scarce is None)
                if scarce:
                    self.assertEqual(country.resources, before)
                    continue
                self.assertEqual([country.resources[k] for k in ("pp", "support_equipment", "people")], [0, 0, 0])
                self.assertEqual(country.variables["VAD_oath_kind"], kind)
                self.assertEqual(country.variables["VAD_oath_state"], 75)
                self.assertEqual(self.orders[name]["days_remove"], str(days))
                before = deepcopy(script.scopes)
                script.effect("VAD_begin_" + name)
                self.assertEqual(script.scopes, before)
                self.assertFalse(self.start(script, name, "106"))
                self.assertFalse(self.base.start(script, "commandant", "107"))

    def test_two_levels_arrive_locally_once_and_survive_administration_retirement(self):
        for name, (_, _, _, _, _, _, building) in self.routes.items():
            for charter in (False, True):
                script = self.campaign(name, charter)
                state = script.scopes["75"]
                self.assertTrue(self.start(script, name))
                script = deepcopy(script)
                state = script.scopes["75"]
                script.run(self.orders[name]["remove_effect"])
                self.assertEqual(state.resources[building], 2)
                self.assertEqual(script.scopes["106"].resources[building], 0)
                self.base.assert_released(script)
                before = deepcopy(script.scopes)
                script.run(self.orders[name]["remove_effect"])
                script.run(self.orders[name]["cancel_effect"])
                self.assertEqual(script.scopes, before)
                script.effect("VAD_close_administration")
                self.assertEqual(state.resources[building], 2)

    def test_native_slot_boundaries_and_existing_airfields_limit_new_work(self):
        for name, (_, _, _, _, _, _, building) in self.routes.items():
            for slots in (0, 1, 2):
                script = self.campaign(name)
                script.scopes["75"].resources[building + "_slots"] = slots
                self.assertEqual(self.start(script, name), slots == 2)
        script = self.campaign("forward_airfield")
        script.scopes["75"].resources["air_base"] = 1
        self.assertFalse(self.start(script, "forward_airfield"))
        script = self.campaign("district_air_defence")
        for expected in (2, 4):
            self.assertTrue(self.start(script, "district_air_defence"))
            script.run(self.orders["district_air_defence"]["remove_effect"])
            self.assertEqual(script.scopes["75"].resources["anti_air_building"], expected)
        self.assertFalse(self.start(script, "district_air_defence"))

    def test_delivery_rechecks_ownership_administration_revolt_dmz_and_capacity(self):
        for name, cause in product(self.routes, ("owner", "controller", "administration", "revolt", "dmz", "slots", "subject", "capitulation", "peace")):
            with self.subTest(route=name, cause=cause):
                script = self.campaign(name)
                country = script.scopes["VAD"]
                state = script.scopes["75"]
                before = deepcopy(country.resources)
                self.assertTrue(self.start(script, name))
                if cause in ("owner", "controller"):
                    setattr(state, cause, "WKR")
                elif cause == "administration":
                    state.flags.discard(V + "vad_commandant_district")
                elif cause == "revolt":
                    state.flags.add(V + "vad_district_uprising")
                elif cause == "dmz":
                    state.demilitarized = True
                elif cause == "slots":
                    state.resources[self.routes[name][6] + "_slots"] = 1
                elif cause == "subject":
                    country.subject = "WKR"
                elif cause == "capitulation":
                    country.capitulated = True
                else:
                    script.globals.add(V + "central_war_finished")
                self.assertTrue(script.conditions(self.orders[name]["cancel_trigger"]))
                script.run(self.orders[name]["remove_effect"])
                script.run(self.orders[name]["cancel_effect"])
                self.assertEqual(country.resources, before)
                self.assertEqual(state.resources[self.routes[name][6]], 0)
                self.base.assert_released(script)
                self.assertFalse(self.start(script, name))
        script = self.campaign("forward_airfield")
        before = deepcopy(script.scopes["VAD"].resources)
        self.assertTrue(self.start(script, "forward_airfield"))
        script.scopes["75"].resources["air_base"] = 1
        script.run(self.orders["forward_airfield"]["remove_effect"])
        self.assertEqual(script.scopes["75"].resources["air_base"], 1)
        self.assertEqual(script.scopes["VAD"].resources, before)

    def test_wrong_target_kind_and_old_callbacks_cannot_consume_another_receipt(self):
        for name in self.routes:
            script = self.campaign(name)
            self.assertTrue(self.start(script, name))
            before = deepcopy(script.scopes)
            other = next(key for key in self.routes if key != name)
            script.run(self.orders[other]["remove_effect"])
            script.run(self.orders[other]["cancel_effect"])
            script.source = "106"
            script.run(self.orders[name]["remove_effect"])
            script.run(self.orders[name]["cancel_effect"])
            self.assertEqual(script.scopes, before)
            script.effect("VAD_refund_oath")
            self.assertTrue(self.start(script, name, "106"))
            before = deepcopy(script.scopes)
            script.source = "75"
            script.run(self.orders[name]["remove_effect"])
            script.run(self.orders[name]["cancel_effect"])
            self.assertEqual(script.scopes, before)

    def test_handoff_refunds_all_prices_before_clearing_target(self):
        for name, (_, _, pp, support, people, _, building) in self.routes.items():
            script = self.campaign(name)
            self.assertTrue(self.start(script, name))
            recipient = script.scopes["WRK"]
            before = deepcopy(recipient.resources)
            script.effect("VAD_settle_oath_handoff", "WRK")
            script.effect("VAD_settle_oath_handoff", "WRK")
            self.assertEqual(recipient.resources["pp"], before["pp"] + pp)
            self.assertEqual(recipient.resources["support_equipment"], before["support_equipment"] + support)
            self.assertEqual(recipient.resources["people"], before["people"] + people)
            self.base.assert_released(script)
            script.run(self.orders[name]["remove_effect"])
            self.assertEqual(script.scopes["75"].resources[building], 0)

    def test_native_callbacks_refund_all_prices_in_the_victim_or_successor_scope(self):
        native = FieldTrialAccountingTests()
        native.setUpClass()
        for hook, name in product(("on_capitulation_immediate", "on_capitulation", "on_puppet", "on_annex"), self.routes):
            script = self.campaign(name)
            self.assertTrue(self.start(script, name))
            recipient = "VAD"
            if hook == "on_annex":
                script.root = recipient = "WKR"
                script.source = "VAD"
                script.scopes["VAD"].exists = False
            else:
                script.source = "WKR"
                if hook == "on_puppet":
                    script.scopes["VAD"].subject = "WKR"
                else:
                    script.scopes["VAD"].capitulated = True
            body = fields(native.hooks[hook])["effect"]
            callbacks = [item for item in body if any(key in ("VAD_refund_oath", "VAD_settle_oath_handoff")
                         for key, _, _ in walk([item]))]
            self.assertEqual(len(callbacks), 1)
            before = deepcopy(script.scopes[recipient].resources)
            script.run(callbacks)
            script.run(callbacks)
            for resource, price in zip(("pp", "support_equipment", "people"), self.routes[name][2:5]):
                self.assertEqual(script.scopes[recipient].resources[resource], before[resource] + price)
            self.base.assert_released(script)
            script.root = "VAD"
            script.source = "75"
            before = deepcopy(script.scopes)
            script.run(self.orders[name]["remove_effect"])
            self.assertEqual(script.scopes, before)

    def test_air_choices_need_an_eligible_district_under_each_mandate(self):
        focuses = {fields(value)["id"]: fields(value) for key, _, value in
                   walk(parse(read("focus_trees/Vorkerland/vad/focuses.txt"))) if key == "focus" and isinstance(value, list)}
        self.assertNotIn("VAD_restore_the_restoration_air_arm", focuses)
        for name, (focus_id, *_) in self.routes.items():
            focus = focuses[focus_id]
            self.assertEqual(fields(focus["prerequisite"]), {"focus": "VAD_standardize_district_logistics"})
            self.assertEqual(focus["cost"], "3")
            self.assertNotIn("bypass", focus)
            for mandate in ("imperial", "joint_government_formed", "collegial_staff_formed"):
                script = self.campaign(name, charter=mandate == "imperial")
                script.scopes["VAD"].enemies.clear()
                if mandate != "imperial":
                    script.globals.add(V + mandate)
                self.assertTrue(script.conditions(focus["allow_branch"]))
                self.assertTrue(script.conditions(focus["available"]))
                self.assertTrue(self.start(script, name))
                for state in ("75", "106"):
                    script.scopes[state].flags.discard(V + "vad_chartered_district")
                    script.scopes[state].flags.discard(V + "vad_commandant_district")
                self.assertFalse(script.conditions(focus["available"]))

    def test_air_choices_use_action_art_with_matching_shine_masks(self):
        sprites = {}
        for path in ("interface/ADISCORD_national_focus.gfx", "interface/ADISCORD_focus_shines.gfx"):
            for key, _, value in walk(parse(read(path))):
                if key.lower() == "spritetype":
                    sprite = fields(value)
                    sprites[sprite["name"]] = sprite
        for name, filename in (("forward_airfield", "focus_generic_air_bases.dds"),
                               ("district_air_defence", "focus_PRC_anti_air_effort.dds")):
            icon = "GFX_focus_" + self.routes[name][0]
            texture = "gfx/interface/goals/" + filename
            self.assertEqual(sprites[icon]["texturefile"], texture)
            self.assertEqual(sprites[icon + "_shine"]["texturefile"], texture)
            self.assertEqual(fields(sprites[icon + "_shine"]["animation"])["animationmaskfile"], texture)
        self.assertNotIn("GFX_focus_VAD_restore_the_restoration_air_arm", sprites)
        self.assertNotIn("GFX_focus_VAD_restore_the_restoration_air_arm_shine", sprites)


class VADDoctrineProgrammeTests(unittest.TestCase):
    template = "Imperial Guard Regiment"
    routes = {
        "guards": ("VAD_restore_the_guards_regiments", 14, 35,
                   {"pp": 60, "people": 1300, "infantry_equipment": 3870,
                    "ADISCORD_squad_weapons_equipment": 32, "support_equipment": 90}),
        "local_militia": ("VAD_train_the_council_militias", 15, 21,
                          {"pp": 35, "people": 1000, "infantry_equipment": 900, "support_equipment": 60}),
    }
    doctrines = {
        "guards": ("VAD_doctrine_of_the_officer_estates", "imperial",
                   {"experience_gain_army_factor": .15, "army_leader_start_level": 1,
                    "planning_speed": .10, "conscription": -.015}),
        "local_militia": ("VAD_doctrine_of_the_district_levies", "joint",
                          {"conscription": .025, "training_time_army_factor": -.20,
                           "army_org_factor": -.04, "experience_gain_army_factor": -.10}),
    }

    @classmethod
    def setUpClass(cls):
        cls.base = VADDistrictAdministrationTests()
        cls.base.setUpClass()
        cls.focuses = {fields(value)["id"]: fields(value) for key, _, value in
                       walk(parse(read("focus_trees/Vorkerland/vad/focuses.txt")))
                       if key == "focus" and isinstance(value, list)}
        cls.dynamic = fields(parse(read("common/dynamic_modifiers/ADISCORD_vorkerland_dynamic_modifiers.txt")))

    def order(self, name):
        key = f"VAD_{name}_programme"
        self.assertTrue(key in self.base.category, f"Missing {key}")
        return fields(self.base.category[key])

    def campaign(self, name):
        script = self.base.campaign()
        for target in ("75", "106"):
            kind = "charter" if name == "guards" else "commandant"
            self.assertTrue(self.base.start(script, kind, target))
            script.run(self.base.orders[kind]["remove_effect"])
        country = script.scopes["VAD"]
        country.focuses.update((self.routes[name][0], self.doctrines[name][0]))
        country.flags.add(V + "vad_variant_" + self.doctrines[name][1])
        country.leader = "WRK_Vlad_Petrichev" if name == "guards" else "WRK_VAD_Joint_Council"
        if name == "local_militia":
            script.globals.add(V + "joint_government_formed")
        country.resources.update(pp=1000, people=10000, infantry_equipment=10000,
                                 ADISCORD_squad_weapons_equipment=1000, support_equipment=1000)
        script.source = "75"
        script.calls.clear()
        return script

    def start(self, script, name, target="75"):
        script.source = target
        order = self.order(name)
        if not all(script.conditions(order[key]) for key in
                   ("visible", "target_trigger", "available", "custom_cost_trigger")):
            return False
        script.run(order["complete_effect"])
        return True

    def test_first_doctrines_apply_exact_delta_and_survive_legitimacy_recalculation(self):
        aggregate = fields(self.dynamic[V + "vad_doctrine"])
        ideas = fields(fields(fields(parse(read("common/ideas/ADISCORD_vorkerland_ideas.txt")))["ideas"])["country"])
        for name, (focus_id, variant, deltas) in self.doctrines.items():
            script = self.campaign(name)
            country = script.scopes["VAD"]
            country.focuses.discard(focus_id)
            country.variables[V + "legitimacy"] = .5
            script.effect(V + "refresh_doctrine_dynamic_state")
            baseline = deepcopy(script)
            before = deepcopy(country.variables)
            reward = self.focuses[focus_id]["completion_reward"]
            self.assertIn("effect_tooltip", fields(reward))
            preview = fields(fields(reward)["effect_tooltip"])["add_ideas"]
            self.assertEqual(fields(ideas[preview])["name"], V + "vad_doctrine")
            self.assertEqual({k: float(v) for k, _, v in fields(ideas[preview])["modifier"]}, deltas)
            script.run(reward)
            self.assertNotIn(preview, country.flags)
            for modifier, amount in deltas.items():
                self.assertAlmostEqual(country.variables[aggregate[modifier]] - before.get(aggregate[modifier], 0), amount)
            for legitimacy in (-1, 0, 1):
                country.variables[V + "legitimacy"] = legitimacy
                baseline.scopes["VAD"].variables[V + "legitimacy"] = legitimacy
                script.effect("VAD_initialize_administration")
                script.effect(V + "refresh_doctrine_dynamic_state")
                baseline.effect(V + "refresh_doctrine_dynamic_state")
                for modifier, amount in deltas.items():
                    self.assertAlmostEqual(country.variables[aggregate[modifier]] - baseline.scopes["VAD"].variables.get(aggregate[modifier], 0), amount)
            script.globals.add(V + "central_war_finished")
            self.assertFalse(script.conditions(aggregate["enable"]))

    def test_second_focus_unlocks_usable_programme_without_second_idea(self):
        for name, (focus_id, _, _, _) in self.routes.items():
            script = self.campaign(name)
            focus = self.focuses[focus_id]
            self.assertEqual(focus["cost"], "3")
            self.assertNotIn("bypass", focus)
            reward = fields(focus["completion_reward"])
            self.assertEqual(reward.get("unlock_decision_tooltip"), f"VAD_{name}_programme")
            self.assertNotIn("add_ideas", reward)
            self.assertTrue(script.conditions(focus["available"]))
            script.scopes["VAD"].focuses.discard(focus_id)
            script.run(focus["completion_reward"])
            if name == "guards":
                self.assertTrue(script.scopes["VAD"].template_locks[self.template])
                self.assertTrue(script.scopes["VAD"].template_recruitment[self.template])
            self.assertFalse(self.start(script, name))
            script.scopes["VAD"].focuses.add(focus_id)
            self.assertTrue(self.start(script, name))
            script.effect("VAD_refund_oath")
            script.globals.add(V + "collegial_staff_formed")
            self.assertFalse(script.conditions(focus["available"]))

    def test_fractional_prices_and_shared_slot_cannot_be_overwritten(self):
        for name, (_, kind, days, prices) in self.routes.items():
            for short in (None, *prices):
                script = self.campaign(name)
                country = script.scopes["VAD"]
                country.resources.update(prices)
                if short:
                    country.resources[short] -= .01
                before = deepcopy(country.resources)
                self.assertEqual(self.start(script, name), short is None, (name, short))
                for resource, price in prices.items():
                    self.assertAlmostEqual(country.resources[resource], before[resource] - price * (short is None))
                if short:
                    continue
                self.assertEqual(country.variables["VAD_oath_kind"], kind)
                self.assertEqual(self.order(name)["days_remove"], str(days))
                snapshot = deepcopy(script.scopes)
                script.run(self.order(name)["complete_effect"])
                self.assertFalse(self.start(script, name, "106"))
                self.assertFalse(self.base.start(script, "commandant", "107"))
                self.assertEqual(script.scopes, snapshot)

    def test_guards_consume_the_existing_cohort_and_pay_exact_template_equipment(self):
        script = self.campaign("guards")
        self.assertTrue(self.start(script, "guards"))
        country = script.scopes["VAD"]
        template = fields(country.templates[self.template])
        self.assertEqual([k for k, _, _ in template["regiments"]], ["infantry"] * 4)
        self.assertEqual([k for k, _, _ in template["support"]], ["engineer"])
        units = fields(fields(parse(read("common/units/ADISCORD_land_units.txt")))["sub_units"])
        requirements = defaultdict(float)
        people = 0
        for unit, _, _ in template["regiments"] + template["support"]:
            definition = fields(units[unit])
            people += float(definition["manpower"])
            for equipment, _, amount in definition["need"]:
                requirements[equipment] += float(amount)
        self.assertEqual(people, 4300)
        self.assertEqual(people, self.routes["guards"][3]["people"] + 3000)
        self.assertEqual(dict(requirements), {"infantry_equipment": 3870, "ADISCORD_squad_weapons_equipment": 32, "support_equipment": 30})
        self.assertEqual(script.scopes["75"].variables["VAD_district_recruited"], 0)
        script.run(self.order("guards")["remove_effect"])
        self.assertEqual(script.scopes["75"].variables["VAD_district_recruited"], 3000)
        self.assertIn("VAD_crown_recruitment_disruption", script.scopes["75"].flags)
        spawned = [(scope, fields(value)) for key, scope, value in script.calls if key == "create_unit"]
        self.assertEqual(len(spawned), 1)
        self.assertEqual(spawned[0][0], "75")
        self.assertEqual(spawned[0][1]["owner"], "PREV")
        for fragment in ('division_template = "Imperial Guard Regiment"', 'start_experience_factor = 0.35',
                         'start_manpower_factor = 1.0', 'start_equipment_factor = 1.0'):
            self.assertIn(fragment, spawned[0][1]["division"])
        self.assertFalse(self.start(script, "guards"))
        script.effect("VAD_remove_district_administration", "75")
        script.scopes["75"].flags.add(V + "vad_chartered_district")
        self.assertFalse(self.start(script, "guards"))
        script.effect("VAD_close_administration")
        self.assertFalse(country.template_locks[self.template])
        self.assertTrue(country.template_recruitment[self.template])

    def test_militia_changes_real_monthly_pressure_and_keeps_uprising_threshold(self):
        for balance, increment in ((-.61, 20), (-.60, 10), (.10, 10), (.11, 0)):
            script = self.campaign("local_militia")
            country = script.scopes["VAD"]
            state = script.scopes["75"]
            state.variables["VAD_district_unrest"] = 50
            country.power_balances["VAD_bop"] = balance
            self.assertTrue(self.start(script, "local_militia"))
            script.run(self.order("local_militia")["remove_effect"])
            self.assertEqual(state.variables["VAD_district_unrest"], 30)
            self.assertIn("VAD_local_militia", state.flags)
            self.assertFalse(any(key == "create_unit" for key, _, _ in script.calls))
            script.effect("VAD_monthly_district_unrest")
            self.assertEqual(state.variables["VAD_district_unrest"], 30 + increment)
            self.assertFalse(self.start(script, "local_militia"))
            state.variables["VAD_district_unrest"] = 99
            script.effect("VAD_monthly_district_unrest")
            self.assertEqual(V + "vad_district_uprising" in state.flags, increment > 0)
        modifier = fields(self.dynamic["VAD_local_militia"])
        self.assertEqual(float(modifier["local_manpower"]), .10)
        self.assertEqual(float(modifier["local_factories"]), -.05)

    def test_loss_withdrawal_and_retirement_remove_militia_and_allow_full_price_rebuild(self):
        for cause in ("loss", "withdrawal", "retirement"):
            script = self.campaign("local_militia")
            self.assertTrue(self.start(script, "local_militia"))
            script.run(self.order("local_militia")["remove_effect"])
            state = script.scopes["75"]
            state.variables["VAD_district_recruited"] = 4500
            if cause == "loss":
                state.controller = "WKR"
                script.effect("VAD_lose_district_administration", "75")
            elif cause == "withdrawal":
                script.effect("VAD_withdraw_district_commandant")
            else:
                script.effect("VAD_close_administration")
            self.assertNotIn("VAD_local_militia", state.flags)
            self.assertEqual(state.variables["VAD_district_recruited"], 4500)
            if cause != "retirement":
                state.controller = "VAD"
                self.assertTrue(self.base.start(script, "commandant"))
                script.run(self.base.orders["commandant"]["remove_effect"])
                before = deepcopy(script.scopes["VAD"].resources)
                self.assertTrue(self.start(script, "local_militia"))
                for resource, price in self.routes["local_militia"][3].items():
                    self.assertEqual(script.scopes["VAD"].resources[resource], before[resource] - price)

    def test_delivery_rechecks_current_country_district_mandate_and_cohort(self):
        causes = ("owner", "controller", "revolt", "administration", "dmz", "subject", "capitulation", "peace", "mandate", "cohort")
        for name, cause in product(self.routes, causes):
            if name != "guards" and cause == "cohort":
                continue
            script = self.campaign(name)
            country = script.scopes["VAD"]
            state = script.scopes["75"]
            before = deepcopy(country.resources)
            self.assertTrue(self.start(script, name))
            if cause in ("owner", "controller"):
                setattr(state, cause, "WKR")
            elif cause == "revolt":
                state.flags.add(V + "vad_district_uprising")
            elif cause == "administration":
                state.flags.discard(V + ("vad_chartered_district" if name == "guards" else "vad_commandant_district"))
            elif cause == "dmz":
                state.demilitarized = True
            elif cause == "subject":
                country.subject = "WKR"
            elif cause == "capitulation":
                country.capitulated = True
            elif cause == "peace":
                script.globals.add(V + "central_war_finished")
            elif cause == "mandate":
                script.globals.add(V + "collegial_staff_formed")
            else:
                state.variables["VAD_district_recruited"] = 3000
            script.run(self.order(name)["remove_effect"])
            self.assertEqual(country.resources, before, (name, cause))
            self.base.assert_released(script)
            self.assertNotIn("VAD_local_militia", state.flags)
            self.assertFalse(any(key == "create_unit" for key, _, _ in script.calls))

    def test_stale_targets_and_wrong_kind_cannot_settle_and_handoff_refunds_once(self):
        for name in self.routes:
            script = self.campaign(name)
            self.assertTrue(self.start(script, name))
            before = deepcopy(script.scopes)
            other = "local_militia" if name == "guards" else "guards"
            script.run(self.order(other)["remove_effect"])
            script.run(self.order(other)["cancel_effect"])
            script.source = "106"
            script.run(self.order(name)["remove_effect"])
            script.run(self.order(name)["cancel_effect"])
            self.assertEqual(script.scopes, before)
            recipient = script.scopes["WRK"]
            before_resources = deepcopy(recipient.resources)
            script.effect("VAD_settle_oath_handoff", "WRK")
            script.effect("VAD_settle_oath_handoff", "WRK")
            for resource, price in self.routes[name][3].items():
                self.assertEqual(recipient.resources[resource], before_resources[resource] + price)
            self.base.assert_released(script)
            script.source = "75"
            snapshot = deepcopy(script.scopes)
            script.run(self.order(name)["remove_effect"])
            script.run(self.order(name)["cancel_effect"])
            self.assertEqual(script.scopes, snapshot)


    def test_other_oath_callbacks_cannot_settle_either_new_order(self):
        callbacks = {}
        for decision, body in self.base.category.items():
            if not isinstance(body, list):
                continue
            kinds = {float(fields(value)["value"]) for key, _, value in walk(body)
                     if key == "check_variable" and fields(value).get("var") == "VAD_oath_kind"}
            if len(kinds) == 1:
                callbacks[decision] = (next(iter(kinds)), fields(body))
        self.assertEqual({kind for kind, _ in callbacks.values()}, set(range(1, 16)))
        for name in self.routes:
            script = self.campaign(name)
            self.assertTrue(self.start(script, name))
            before = deepcopy((script.scopes, script.calls))
            for kind, order in callbacks.values():
                if kind == self.routes[name][1]:
                    continue
                script.run(order.get("cancel_effect", []))
                script.run(order.get("remove_effect", []))
                self.assertEqual((script.scopes, script.calls), before, (name, kind))

    def test_ai_reserves_a_cohort_until_guard_unlock_then_can_raise_emergency_recruits(self):
        order = fields(self.base.category["VAD_crown_district_recruitment"])
        guards = [value for key, _, value in order["ai_will_do"]
                  if key == "modifier" and fields(value).get("factor") == "0"]
        self.assertEqual(len(guards), 1)
        conditions = [item for item in guards[0] if item[0] != "factor"]
        script = self.campaign("guards")
        country = script.scopes["VAD"]
        self.assertFalse(script.conditions(conditions))
        country.focuses.remove("VAD_restore_the_guards_regiments")
        self.assertTrue(script.conditions(conditions))
        country.focuses.remove("VAD_doctrine_of_the_officer_estates")
        self.assertFalse(script.conditions(conditions))

    def test_native_hooks_refund_every_currency_once_to_actual_recipient(self):
        native = FieldTrialAccountingTests()
        native.setUpClass()
        for hook, name in product(("on_capitulation_immediate", "on_capitulation", "on_puppet", "on_annex"), self.routes):
            script = self.campaign(name)
            self.assertTrue(self.start(script, name))
            recipient = "VAD"
            if hook == "on_annex":
                script.root = recipient = "WKR"
                script.source = "VAD"
                script.scopes["VAD"].exists = False
            else:
                script.source = "WKR"
                if hook == "on_puppet":
                    script.scopes["VAD"].subject = "WKR"
                else:
                    script.scopes["VAD"].capitulated = True
            body = fields(native.hooks[hook])["effect"]
            callbacks = [item for item in body if any(key in ("VAD_refund_oath", "VAD_settle_oath_handoff")
                         for key, _, _ in walk([item]))]
            self.assertEqual(len(callbacks), 1)
            before = deepcopy(script.scopes[recipient].resources)
            script.run(callbacks)
            script.run(callbacks)
            for resource, price in self.routes[name][3].items():
                self.assertEqual(script.scopes[recipient].resources[resource], before[resource] + price)
            self.base.assert_released(script)
            self.assertEqual(script.scopes["75"].variables["VAD_district_recruited"], 0)


class VADForeignPolicyTests(unittest.TestCase):
    routes = {
        "coalition_guarantees": ("VAD_issue_restoration_guarantees", 18, 50, 0, 7, "EYR", "19"),
        "foreign_observers": ("VAD_seat_the_observer_missions", 19, 40, 100, 14, "ROM", "20"),
    }

    @classmethod
    def setUpClass(cls):
        cls.base = VADDistrictAdministrationTests()
        cls.base.setUpClass()

    def order(self, name):
        key = "VAD_" + name
        self.assertIn(key, self.base.category)
        return fields(self.base.category[key])

    def campaign(self, name):
        script = self.base.campaign()
        country = script.scopes["VAD"]
        country.focuses.add(self.routes[name][0])
        country.enemies = {"TVA"}
        country.resources.update(pp=1000, support_equipment=1000)
        for tag in ("EYR", "EGC", "YOR", "SWB", "NDN", "OSV", "REV", "RIV", "VHV",
                    "ZAO", "WPA", "WPS", "PWR", "PSD", "VLA", "EBA", "TGD", "DVA",
                    "SRA", "ZTA", "CSL", "SOL", "ROM", "TRU"):
            script.scopes[tag].exists = False
        target = self.routes[name][5]
        script.scopes[target].exists = True
        script.scopes["capital_" + target].controller = target
        script.source = target
        script.calls.clear()
        return script

    def start(self, script, name):
        order = self.order(name)
        if not all(script.conditions(order[key]) for key in ("visible", "target_trigger", "available", "custom_cost_trigger")):
            return False
        script.run(order["complete_effect"])
        return True

    def dispatch(self, script, name):
        script.run(self.order(name)["remove_effect"])
        return V + "diplomacy." + self.routes[name][6]

    def answer(self, script, name, accept):
        event_id = V + "diplomacy." + self.routes[name][6]
        self.assertIn(event_id, EVENTS)
        script.root = script.source
        script.source = "VAD"
        options = [value for key, _, value in EVENTS[event_id] if key == "option"]
        choice = options[1 if accept else 0]
        data = fields(choice)
        if "trigger" in data:
            self.assertTrue(script.conditions(data["trigger"]))
        script.run([item for item in choice if item[0] not in ("name", "trigger", "ai_chance")])

    def test_prices_shared_slot_and_partner_are_owned_by_one_receipt(self):
        for name, (_, kind, pp, support, days, target, _) in self.routes.items():
            for scarce in (None, "pp", "support_equipment"):
                if not support and scarce == "support_equipment":
                    continue
                script = self.campaign(name)
                country = script.scopes["VAD"]
                country.resources.update(pp=pp, support_equipment=support)
                if scarce:
                    country.resources[scarce] -= .01
                before = deepcopy(country.resources)
                self.assertEqual(self.start(script, name), scarce is None)
                if scarce:
                    self.assertEqual(country.resources, before)
                    continue
                self.assertEqual(country.resources["pp"], 0)
                self.assertEqual(country.resources["support_equipment"], 0)
                self.assertEqual(country.variables["VAD_oath_kind"], kind)
                self.assertEqual(country.variables["VAD_oath_foreign_stage"], 1)
                self.assertNotIn("VAD_oath_state", country.variables)
                self.assertEqual(script.event_targets["VAD_foreign_partner"], target)
                self.assertEqual(self.order(name)["days_remove"], str(days))
                before = deepcopy(script.scopes)
                script.run(self.order(name)["complete_effect"])
                self.assertEqual(script.scopes, before)
                self.assertFalse(self.base.start(script, "commandant", "107"))

    def test_coalition_entry_needs_real_consent_and_calls_existing_native_contract(self):
        script = self.campaign("coalition_guarantees")
        self.assertTrue(self.start(script, "coalition_guarantees"))
        self.assertFalse(any(key == V + "join_coalition_of_FROM" for key, _, _ in script.calls))
        self.dispatch(script, "coalition_guarantees")
        self.assertEqual(script.scopes["VAD"].variables["VAD_oath_foreign_stage"], 2)
        self.answer(script, "coalition_guarantees", True)
        self.assertIn((V + "join_coalition_of_FROM", "EYR", "yes"), script.calls)
        self.assertEqual(script.source, "VAD")
        self.assertEqual(script.scopes["VAD"].variables["VAD_oath_foreign_stage"], 3)
        # Faction creation and the war splice are native boundaries. The existing
        # verifier invokes settlement only after checking their real postcondition.
        script.scopes["VAD"].faction = "VAD"
        script.scopes["EYR"].faction = "VAD"
        script.scopes["EYR"].enemies = {"TVA"}
        script.scopes["TVA"].enemies = {"VAD", "EYR"}
        script.effect("VAD_settle_coalition_guarantees")
        self.base.assert_released(script)
        self.assertNotIn("VAD_foreign_partner", script.event_targets)
        self.assertNotIn("VAD_foreign_offer_pending", script.scopes["EYR"].flags)

    def test_failed_native_coalition_verification_returns_the_sponsors_deposit(self):
        script = self.campaign("coalition_guarantees")
        before = deepcopy(script.scopes["VAD"].resources)
        self.assertTrue(self.start(script, "coalition_guarantees"))
        self.dispatch(script, "coalition_guarantees")
        self.answer(script, "coalition_guarantees", True)
        script.scopes["EYR"].flags.add(V + "regional_auxiliary_failed")
        script.effect("VAD_settle_coalition_guarantees")
        script.effect("VAD_settle_coalition_guarantees")
        self.assertEqual(script.scopes["VAD"].resources, before)
        self.base.assert_released(script)
        self.assertIn("VAD_settle_coalition_guarantees", fields(EFFECTS[V + "verify_coalition_membership"]))

    def test_observer_report_trades_current_army_information_for_experience_and_recognition(self):
        script = self.campaign("foreign_observers")
        partner_before = deepcopy(script.scopes["ROM"].resources)
        self.assertTrue(self.start(script, "foreign_observers"))
        self.dispatch(script, "foreign_observers")
        self.answer(script, "foreign_observers", True)
        self.assertEqual(script.scopes["VAD"].resources["army_experience"], 20)
        self.assertEqual(script.scopes["VAD"].variables[V + "legitimacy_delta"], .06)
        self.assertEqual(script.scopes["ROM"].resources, partner_before)
        intel = [(scope, fields(value)) for key, scope, value in script.calls if key == "add_intel"]
        self.assertEqual(intel, [("ROM", {"target": "VAD", "army_intel": "20"})])
        self.assertIn("VAD_observer_report_received", script.scopes["ROM"].flags)
        self.base.assert_released(script)
        script.root = "VAD"
        script.source = "ROM"
        self.assertFalse(self.start(script, "foreign_observers"))

    def test_refusal_and_unattended_first_option_refund_every_currency_once(self):
        for name in self.routes:
            script = self.campaign(name)
            before = deepcopy(script.scopes["VAD"].resources)
            self.assertTrue(self.start(script, name))
            event_id = self.dispatch(script, name)
            self.assertEqual(fields(EVENTS[event_id])["timeout_days"], "14")
            self.answer(script, name, False)
            self.assertEqual(script.scopes["VAD"].resources, before)
            self.base.assert_released(script)
            script.root = "VAD"
            script.source = self.routes[name][5]
            self.answer(script, name, False)
            self.assertEqual(script.scopes["VAD"].resources, before)

    def test_candidate_loss_during_preparation_refunds_without_an_offer(self):
        for name, cause in product(self.routes, ("exists", "subject", "capitulation", "war", "campaign")):
            script = self.campaign(name)
            before = deepcopy(script.scopes["VAD"].resources)
            self.assertTrue(self.start(script, name))
            partner = script.scopes[script.source]
            if cause == "exists":
                partner.exists = False
            elif cause == "subject":
                partner.subject = "TVA"
            elif cause == "capitulation":
                partner.capitulated = True
            elif cause == "war":
                partner.enemies.add("VAD")
            else:
                script.globals.add(V + "central_war_finished")
            self.assertTrue(script.conditions(self.order(name)["cancel_trigger"]))
            self.dispatch(script, name)
            self.assertEqual(script.scopes["VAD"].resources, before)
            self.assertNotIn("VAD_foreign_offer_pending", partner.flags)
            self.base.assert_released(script)

    def test_open_old_reply_cannot_refund_a_later_domestic_order(self):
        for name in self.routes:
            script = self.campaign(name)
            self.assertTrue(self.start(script, name))
            self.dispatch(script, name)
            script.effect("VAD_refund_oath")
            self.assertIn("VAD_foreign_offer_pending", script.scopes[self.routes[name][5]].flags)
            self.assertTrue(self.base.start(script, "commandant", "107"))
            before = deepcopy(script.scopes["VAD"])
            script.source = self.routes[name][5]
            self.answer(script, name, False)
            self.assertEqual(script.scopes["VAD"], before)

    def test_dead_partner_watchdog_checks_the_current_receipt_age(self):
        for name in self.routes:
            script = self.campaign(name)
            before = deepcopy(script.scopes["VAD"].resources)
            self.assertTrue(self.start(script, name))
            self.dispatch(script, name)
            script.scopes[script.source].exists = False
            self.assertIn(V + "diplomacy.21", EVENTS)
            event = fields(EVENTS[V + "diplomacy.21"])
            script.scopes["VAD"].flag_ages["VAD_foreign_offer_clock"] = 10
            script.run(event["immediate"])
            self.assertIn("VAD_oath_pp", script.scopes["VAD"].variables)
            script.scopes["VAD"].flag_ages["VAD_foreign_offer_clock"] = 30
            script.run(event["immediate"])
            self.assertEqual(script.scopes["VAD"].resources, before)
            self.base.assert_released(script)
            self.assertNotIn("VAD_foreign_partner", script.event_targets)

    def test_native_country_loss_and_handoff_refund_foreign_receipts(self):
        native = FieldTrialAccountingTests()
        native.setUpClass()
        for name, hook in product(self.routes, ("on_capitulation_immediate", "on_capitulation", "on_puppet", "on_annex")):
            script = self.campaign(name)
            self.assertTrue(self.start(script, name))
            self.dispatch(script, name)
            recipient = "WKR" if hook == "on_annex" else "VAD"
            script.source = "VAD" if hook == "on_annex" else "WKR"
            if hook == "on_annex":
                script.root = "WKR"
                script.scopes["VAD"].exists = False
            elif hook == "on_puppet":
                script.scopes["VAD"].subject = "WKR"
            else:
                script.scopes["VAD"].capitulated = True
            body = fields(native.hooks[hook])["effect"]
            callbacks = [item for item in body if any(key in ("VAD_refund_oath", "VAD_settle_oath_handoff")
                         for key, _, _ in walk([item]))]
            self.assertEqual(len(callbacks), 1)
            before = deepcopy(script.scopes[recipient].resources)
            script.run(callbacks)
            script.run(callbacks)
            _, _, pp, support, *_ = self.routes[name]
            self.assertEqual(script.scopes[recipient].resources["pp"], before["pp"] + pp)
            self.assertEqual(script.scopes[recipient].resources["support_equipment"], before["support_equipment"] + support)
            self.base.assert_released(script)
            self.assertNotIn("VAD_foreign_partner", script.event_targets)

    def test_observers_require_real_campaign_combat_and_coalitions_keep_local_war_order(self):
        script = self.campaign("foreign_observers")
        script.scopes["VAD"].enemies = {"GER"}
        self.assertFalse(self.start(script, "foreign_observers"))
        script = self.campaign("coalition_guarantees")
        script.scopes["YOR"].exists = True
        self.assertFalse(self.start(script, "coalition_guarantees"))
        script.scopes["YOR"].exists = False
        script.scopes["EYR"].faction = "TVA"
        self.assertFalse(self.start(script, "coalition_guarantees"))

    def test_tree_has_one_direct_diplomatic_choice_instead_of_three_filler_entries(self):
        from tools.validators.validate_adiscord_vorkerland_civil_war_focus import focus_blocks
        blocks = focus_blocks(read("focus_trees/Vorkerland/vad/focuses.txt"))
        for obsolete in ("VAD_court_the_bracket_victors", "VAD_seek_legitimist_recognition", "VAD_open_the_foreign_chancery"):
            self.assertNotIn(obsolete, blocks)
        for name, (focus_id, *_) in self.routes.items():
            focus = fields(parse(blocks[focus_id])[0][2])
            self.assertEqual(fields(focus["prerequisite"])["focus"], "VAD_proclaim_joint_charter")
            self.assertEqual(fields(focus["completion_reward"])["unlock_decision_tooltip"], "VAD_" + name)
            self.assertNotIn("bypass", focus)


class VADFinalOperationsTests(unittest.TestCase):
    routes = {
        "district_march": ("VAD_march_on_the_old_capital", 16, 45, 120, 1000, 21),
        "city_redoubts": ("VAD_fortify_the_restoration_line", 17, 40, 150, 800, 35),
    }

    @classmethod
    def setUpClass(cls):
        cls.base = VADDistrictAdministrationTests()
        cls.base.setUpClass()

    def order(self, name):
        key = f"VAD_{name}_programme"
        self.assertIn(key, self.base.category)
        return fields(self.base.category[key])

    def campaign(self, name, charter=False):
        script = self.base.campaign()
        for target in ("75", "106"):
            route = "charter" if charter else "commandant"
            self.assertTrue(self.base.start(script, route, target))
            script.run(self.base.orders[route]["remove_effect"])
            script.scopes[target].victory_points = {1, 2}
            script.scopes[target].province_buildings = {1: {"bunker": 0}, 2: {"bunker": 0}, 3: {"bunker": 8}}
        country = script.scopes["VAD"]
        country.focuses.add(self.routes[name][0])
        country.resources.update(pp=1000, people=10000, support_equipment=1000)
        country.enemies.add("WKR")
        script.globals.discard(V + "phase_central_preparation")
        script.globals.add(V + "phase_central_showdown")
        script.source = "75"
        script.calls.clear()
        return script

    def start(self, script, name, target="75"):
        script.source = target
        order = self.order(name)
        if not all(script.conditions(order[key]) for key in
                   ("visible", "target_trigger", "available", "custom_cost_trigger")):
            return False
        script.run(order["complete_effect"])
        return True

    def test_exact_payment_shared_slot_and_repeated_payment(self):
        for name, (_, kind, pp, support, people, days) in self.routes.items():
            for scarce in (None, "pp", "support_equipment", "people"):
                script = self.campaign(name)
                country = script.scopes["VAD"]
                country.resources.update(pp=pp, people=people, support_equipment=support)
                if scarce:
                    country.resources[scarce] -= .01
                before = deepcopy(country.resources)
                self.assertEqual(self.start(script, name), scarce is None)
                if scarce:
                    self.assertEqual(country.resources, before)
                    continue
                self.assertEqual([country.resources[k] for k in ("pp", "people", "support_equipment")], [0, 0, 0])
                self.assertEqual(country.variables["VAD_oath_kind"], kind)
                self.assertEqual(country.variables["VAD_oath_state"], 75)
                self.assertEqual(self.order(name)["days_remove"], str(days))
                before = deepcopy(script.scopes)
                script.effect("VAD_begin_" + name)
                self.assertEqual(script.scopes, before)
                self.assertFalse(self.start(script, name, "106"))
                self.assertFalse(self.base.start(script, "commandant", "107"))

    def test_march_plan_has_a_local_cost_without_spending_the_district_cohort(self):
        for charter in (False, True):
            script = self.campaign("district_march", charter)
            state = script.scopes["75"]
            state.variables["VAD_district_recruited"] = 3000
            state.variables["VAD_district_unrest"] = 45
            self.assertTrue(self.start(script, "district_march"))
            script.run(self.order("district_march")["remove_effect"])
            self.assertIn(V + "vad_march_on_the_capital", script.scopes["VAD"].flags)
            self.assertIn("VAD_march_commitment", state.flags)
            self.assertEqual(state.variables["VAD_district_recruited"], 3000)
            self.assertEqual(state.variables["VAD_district_unrest"], 45 if charter else 75)
            self.assertFalse(self.start(script, "district_march", "106"))
            self.base.assert_released(script)
            script.effect("VAD_remove_district_administration", "75")
            self.assertNotIn(V + "vad_march_on_the_capital", script.scopes["VAD"].flags)
            self.assertNotIn("VAD_march_commitment", state.flags)

    def test_redoubts_only_build_at_victory_points_and_recheck_each_province(self):
        script = self.campaign("city_redoubts")
        state = script.scopes["75"]
        for level in (2, 4, 6, 8, 10):
            self.assertTrue(self.start(script, "city_redoubts"))
            script = deepcopy(script)
            state = script.scopes["75"]
            script.run(self.order("city_redoubts")["remove_effect"])
            self.assertEqual([state.province_buildings[p]["bunker"] for p in (1, 2, 3)], [level, level, 8])
        self.assertFalse(self.start(script, "city_redoubts"))
        script.effect("VAD_close_administration")
        self.assertEqual(state.province_buildings[1]["bunker"], 10)
        for levels, expected in (((0, 8), True), ((0, 9), False), ((10, 0), False)):
            script = self.campaign("city_redoubts")
            for province, level in zip((1, 2), levels):
                script.scopes["75"].province_buildings[province]["bunker"] = level
            self.assertEqual(self.start(script, "city_redoubts"), expected)
        script = self.campaign("city_redoubts")
        script.scopes["75"].victory_points.clear()
        self.assertFalse(self.start(script, "city_redoubts"))

    def test_delivery_refunds_after_current_context_or_site_is_lost(self):
        for name, cause in product(self.routes, ("owner", "controller", "partial", "administration", "revolt", "dmz", "subject", "capitulation", "peace", "site")):
            with self.subTest(route=name, cause=cause):
                script = self.campaign(name)
                country = script.scopes["VAD"]
                state = script.scopes["75"]
                before = deepcopy(country.resources)
                self.assertTrue(self.start(script, name))
                if cause in ("owner", "controller"):
                    setattr(state, cause, "WKR")
                elif cause == "partial":
                    state.fully_controlled = False
                elif cause == "administration":
                    state.flags.discard(V + "vad_commandant_district")
                elif cause == "revolt":
                    state.flags.add(V + "vad_district_uprising")
                elif cause == "dmz":
                    state.demilitarized = True
                elif cause == "subject":
                    country.subject = "WKR"
                elif cause == "capitulation":
                    country.capitulated = True
                elif cause == "peace":
                    script.globals.add(V + "central_war_finished")
                elif name == "district_march":
                    state.variables["VAD_district_unrest"] = 70
                else:
                    state.province_buildings[1]["bunker"] = 9
                self.assertTrue(script.conditions(self.order(name)["cancel_trigger"]))
                script.run(self.order(name)["remove_effect"])
                self.assertEqual(country.resources, before)
                self.base.assert_released(script)
                before = deepcopy(script.scopes)
                script.run(self.order(name)["cancel_effect"])
                script.run(self.order(name)["remove_effect"])
                self.assertEqual(script.scopes, before)

    def test_actual_central_enemy_and_preparation_have_distinct_uses(self):
        for name in self.routes:
            script = self.campaign(name)
            script.scopes["VAD"].enemies = {"GER"}
            self.assertEqual(self.start(script, name), name == "city_redoubts")
            script = self.campaign(name)
            script.globals.discard(V + "phase_central_showdown")
            script.globals.add(V + "phase_central_preparation")
            self.assertEqual(self.start(script, name), name == "city_redoubts")

    def test_old_district_commitment_blocks_a_second_plan_after_native_cancellation(self):
        script = self.campaign("district_march")
        self.assertTrue(self.start(script, "district_march"))
        script.run(self.order("district_march")["remove_effect"])
        script.scopes["VAD"].flags.discard(V + "vad_march_on_the_capital")
        self.assertFalse(self.start(script, "district_march", "106"))
        script.effect("VAD_clear_march_commitment", "75")
        self.assertTrue(self.start(script, "district_march", "106"))

    def test_native_hooks_refund_both_final_orders_once_to_actual_recipient(self):
        native = FieldTrialAccountingTests()
        native.setUpClass()
        for name, hook in product(self.routes, ("on_capitulation_immediate", "on_capitulation", "on_puppet", "on_annex")):
            script = self.campaign(name)
            self.assertTrue(self.start(script, name))
            recipient = "WKR" if hook == "on_annex" else "VAD"
            if hook == "on_annex":
                script.root = "WKR"
                script.source = "VAD"
                script.scopes["VAD"].exists = False
            else:
                script.source = "WKR"
                if hook == "on_puppet":
                    script.scopes["VAD"].subject = "WKR"
                else:
                    script.scopes["VAD"].capitulated = True
            body = fields(native.hooks[hook])["effect"]
            callbacks = [item for item in body if any(key in ("VAD_refund_oath", "VAD_settle_oath_handoff")
                         for key, _, _ in walk([item]))]
            self.assertEqual(len(callbacks), 1)
            before = deepcopy(script.scopes[recipient].resources)
            script.run(callbacks)
            script.run(callbacks)
            _, _, pp, support, people, _ = self.routes[name]
            for resource, price in (("pp", pp), ("support_equipment", support), ("people", people)):
                self.assertEqual(script.scopes[recipient].resources[resource], before[resource] + price)
            self.base.assert_released(script)

    def test_native_previews_and_plan_expiry_use_the_actual_reward(self):
        for name in self.routes:
            order = self.order(name)
            self.assertIn("effect_tooltip", fields(order["complete_effect"]))
        script = self.campaign("district_march")
        self.assertTrue(self.start(script, "district_march"))
        script.run(self.order("district_march")["remove_effect"])
        timed = [fields(v) for key, _, v in script.calls if key == "add_timed_idea"]
        self.assertIn({"idea": V + "vad_march_on_the_capital", "days": "70"}, timed)
        local = [fields(v) for key, scope, v in script.calls if key == "add_dynamic_modifier" and scope == "75"]
        self.assertIn({"modifier": "VAD_march_commitment", "days": "70"}, local)
        queued = [fields(v) for key, _, v in script.calls if key == "country_event"]
        self.assertIn({"id": V + "claimant.33", "days": "71"}, queued)
        ideas = fields(fields(parse(read("common/ideas/ADISCORD_vorkerland_ideas.txt")))["ideas"])
        idea = fields(fields(ideas["country"])[V + "vad_march_on_the_capital"])
        self.assertFalse(script.conditions(idea["cancel"]))
        script.scopes["VAD"].enemies = {"GER"}
        self.assertTrue(script.conditions(idea["cancel"]))

    def test_stale_target_or_kind_cannot_settle_a_new_receipt(self):
        for old, new in product(self.routes, repeat=2):
            script = self.campaign(old)
            self.assertTrue(self.start(script, old))
            script.run(self.order(old)["cancel_effect"])
            script.scopes["VAD"].focuses.add(self.routes[new][0])
            self.assertTrue(self.start(script, new, "106"))
            script.source = "75"
            before = deepcopy(script.scopes)
            script.run(self.order(old)["cancel_effect"])
            script.run(self.order(old)["remove_effect"])
            self.assertEqual(script.scopes, before)
            script.source = "106"
            script.run(self.order(new)["cancel_effect"])
            self.base.assert_released(script)

    def test_focus_choices_are_direct_and_reward_extractors_follow_new_programmes(self):
        from tools.validators.validate_adiscord_vorkerland_civil_war_focus import focus_blocks, _plan_reward_contract
        blocks = focus_blocks(read("focus_trees/Vorkerland/vad/focuses.txt"))
        self.assertNotIn("VAD_hold_the_historic_capitals", blocks)
        for name, (focus_id, *_) in self.routes.items():
            focus = fields(parse(blocks[focus_id])[0][2])
            self.assertEqual(fields(focus["prerequisite"])["focus"], "VAD_balance_council_and_command")
            self.assertEqual(focus["cost"], "3")
            self.assertEqual(fields(focus["completion_reward"])["unlock_decision_tooltip"], f"VAD_{name}_programme")
            self.assertNotIn("bypass", focus)
            reward = _plan_reward_contract(blocks[focus_id])
            self.assertIn("add_timed_idea" if name == "district_march" else "add_building_construction", reward)
        for focus_id, payload in (("VAD_restore_the_guards_regiments", "create_unit"), ("VAD_train_the_council_militias", "VAD_local_militia")):
            self.assertIn(payload, _plan_reward_contract(blocks[focus_id]))


class VADOathSummaryTests(unittest.TestCase):
    def test_every_paid_receipt_has_an_active_summary_and_real_target_pointer(self):
        summaries = [fields(value) for key, _, value in parse(read("common/scripted_localisation/ADISCORD_vorkerland_scripted_loc.txt"))
                     if key == "defined_text" and fields(value)["name"] == "GetVADOathProject"]
        body = next(value for key, _, value in parse(read("common/scripted_localisation/ADISCORD_vorkerland_scripted_loc.txt"))
                    if key == "defined_text" and fields(value)["name"] == "GetVADOathProject")
        self.assertEqual(len(summaries), 1)
        script = Script()
        script.root = "VAD"
        for kind in range(1, 20):
            script.scopes["VAD"].variables.update(VAD_oath_kind=kind, VAD_oath_state=75, VAD_oath_pp=40)
            selected = next(fields(value)["localization_key"] for key, _, value in body
                            if key == "text" and ("trigger" not in fields(value) or script.conditions(fields(value)["trigger"])))
            self.assertNotEqual(selected, "VAD_oath_idle", kind)
            for language in ("russian", "english"):
                loc = read(f"localisation/{language}/ADISCORD_vorkerland_l_{language}.yml")
                line = next(line for line in loc.splitlines() if line.startswith(" " + selected + ":"))
                self.assertNotIn("VAD_oath_target.GetName", line)
                if kind >= 18:
                    self.assertIn("event_target:VAD_foreign_partner.GetName", line)
                    self.assertNotIn("VAD_oath_state.GetName", line)
                elif kind >= 8:
                    self.assertIn("VAD_oath_state.GetName", line)


class VADCrownPolicyTests(unittest.TestCase):
    routes = {
        "privileges": ("VAD_stage_the_coronation_rites", 10, 30, 80, "VAD_crown_district_privileges"),
        "collateral": ("VAD_mortgage_the_regalia", 11, 35, 60, "VAD_crown_district_collateral"),
    }

    @classmethod
    def setUpClass(cls):
        cls.base = VADDistrictAdministrationTests()
        cls.base.setUpClass()
        cls.orders = {name: fields(cls.base.category[f"VAD_crown_{name}_programme"])
                      for name in cls.routes}
        cls.focuses = {fields(value)["id"]: fields(value)
                       for key, _, value in walk(parse(read("focus_trees/Vorkerland/vad/focuses.txt")))
                       if key == "focus" and isinstance(value, list)}

    def campaign(self, name):
        script = self.base.campaign()
        for target in ("75", "106"):
            self.assertTrue(self.base.start(script, "charter", target))
            script.run(self.base.orders["charter"]["remove_effect"])
            script.scopes[target].resources["industrial_complex"] = 1
        country = script.scopes["VAD"]
        country.focuses.add(self.routes[name][0])
        country.leader = "WRK_Vlad_Petrichev"
        country.resources.update(pp=1000, people=10000, support_equipment=500)
        script.source = "75"
        script.calls.clear()
        return script

    def start(self, script, name, target="75"):
        script.source = target
        order = self.orders[name]
        if not all(script.conditions(order[key]) for key in
                   ("visible", "target_trigger", "available", "custom_cost_trigger")):
            return False
        script.run(order["complete_effect"])
        return True

    def test_fractional_prices_and_one_chancery_receipt(self):
        for name, (_, kind, pp, support, _) in self.routes.items():
            for treasury, stock, success in ((pp, support, True), (pp-.01, support, False), (pp, support-.01, False)):
                script = self.campaign(name)
                country = script.scopes["VAD"]
                country.resources.update(pp=treasury, support_equipment=stock)
                self.assertEqual(self.start(script, name), success)
                self.assertEqual(country.resources["pp"], treasury - pp * success)
                self.assertEqual(country.resources["support_equipment"], stock - support * success)
                self.assertEqual(country.resources["people"], 10000)
                before = deepcopy(script.scopes)
                script.effect(f"VAD_begin_crown_{name}")
                self.assertEqual(script.scopes, before)
                if success:
                    self.assertEqual(country.variables["VAD_oath_kind"], kind)
                    self.assertFalse(self.start(script, name, "106"))
                    self.assertFalse(self.base.start(script, "commandant", "107"))

    def test_delivery_is_local_and_pays_once_with_distinct_outcomes(self):
        for name, (_, _, pp, support, modifier) in self.routes.items():
            script = self.campaign(name)
            country = script.scopes["VAD"]
            before = deepcopy(country.resources)
            balance = country.power_balances["VAD_bop"]
            self.assertTrue(self.start(script, name))
            script = deepcopy(script)
            country = script.scopes["VAD"]
            script.run(self.orders[name]["remove_effect"])
            self.assertIn(modifier, script.scopes["75"].flags)
            self.assertNotIn(modifier, script.scopes["106"].flags)
            self.assertEqual(country.resources["pp"], before["pp"] - pp)
            self.assertEqual(country.resources["support_equipment"], before["support_equipment"] - support)
            self.assertEqual(country.resources["people"], before["people"])
            self.assertEqual(country.resources["infantry_equipment"], before["infantry_equipment"] + (1800 if name == "collateral" else 0))
            self.assertEqual(country.variables[V + "legitimacy_delta"], -.04 if name == "collateral" else .03)
            self.assertAlmostEqual(country.power_balances["VAD_bop"], balance + (-.10 if name == "collateral" else .10))
            self.assertTrue(any(key == "add_dynamic_modifier" and fields(value).get("days") == "90"
                                for key, _, value in script.calls))
            self.base.assert_released(script)
            saved = deepcopy((script.scopes, script.calls))
            script.run(self.orders[name]["remove_effect"])
            script.run(self.orders[name]["cancel_effect"])
            self.assertEqual((script.scopes, script.calls), saved)
            self.assertFalse(self.start(script, name))
            self.assertTrue(self.start(script, name, "106"))

    def test_delivery_rechecks_every_asset_and_current_government(self):
        for name, cause in product(self.routes, ("factory", "charter", "owner", "controller", "subject", "capitulation", "joint", "staff", "leader", "peace")):
            with self.subTest(route=name, cause=cause):
                script = self.campaign(name)
                country = script.scopes["VAD"]
                state = script.scopes["75"]
                before = deepcopy(country.resources)
                self.assertTrue(self.start(script, name))
                if cause == "factory":
                    state.resources["industrial_complex"] = 0
                elif cause == "charter":
                    state.flags.remove(V + "vad_chartered_district")
                elif cause in ("owner", "controller"):
                    setattr(state, cause, "WKR")
                elif cause == "subject":
                    country.subject = "WKR"
                elif cause == "capitulation":
                    country.capitulated = True
                elif cause == "leader":
                    country.leader = "WRK_VAD_Joint_Council"
                else:
                    script.globals.add(V + {"joint": "joint_government_formed", "staff": "collegial_staff_formed", "peace": "central_war_finished"}[cause])
                self.assertTrue(script.conditions(self.orders[name]["cancel_trigger"]))
                script.run(self.orders[name]["remove_effect"])
                script.run(self.orders[name]["cancel_effect"])
                self.assertEqual(country.resources, before)
                self.assertNotIn(self.routes[name][4], state.flags)
                self.base.assert_released(script)

    def test_wrong_target_and_kind_cannot_touch_a_new_receipt(self):
        for name in self.routes:
            script = self.campaign(name)
            self.assertTrue(self.start(script, name))
            country = script.scopes["VAD"]
            before = deepcopy(script.scopes)
            other = next(key for key in self.routes if key != name)
            script.run(self.orders[other]["remove_effect"])
            script.run(self.orders[other]["cancel_effect"])
            script.source = "106"
            script.run(self.orders[name]["remove_effect"])
            script.run(self.orders[name]["cancel_effect"])
            self.assertEqual(script.scopes, before)
            script.effect("VAD_refund_oath")
            self.assertTrue(self.start(script, name, "106"))
            before = deepcopy(script.scopes)
            script.source = "75"
            script.run(self.orders[name]["remove_effect"])
            script.run(self.orders[name]["cancel_effect"])
            self.assertEqual(script.scopes, before)
            self.assertEqual(country.variables["VAD_oath_state"], 106)

    def test_annexation_returns_full_receipt_to_living_successor(self):
        for name, (_, _, pp, support, _) in self.routes.items():
            script = self.campaign(name)
            self.assertTrue(self.start(script, name))
            recipient = script.scopes["WRK"]
            before = deepcopy(recipient.resources)
            script.scopes["VAD"].exists = False
            script.effect("VAD_settle_oath_handoff", "WRK")
            script.effect("VAD_settle_oath_handoff", "WRK")
            self.assertEqual(recipient.resources["pp"], before["pp"] + pp)
            self.assertEqual(recipient.resources["support_equipment"], before["support_equipment"] + support)
            self.assertEqual(recipient.resources["people"], before["people"])
            self.base.assert_released(script)
            before = deepcopy(script.scopes)
            script.run(self.orders[name]["remove_effect"])
            self.assertEqual(script.scopes, before)

    def test_lost_district_and_war_retirement_remove_only_owned_assets(self):
        for name, (_, _, _, _, modifier) in self.routes.items():
            script = self.campaign(name)
            self.assertTrue(self.start(script, name))
            script.run(self.orders[name]["remove_effect"])
            before = deepcopy(script.scopes["75"])
            script.effect("VAD_close_administration", "WKR")
            self.assertEqual(script.scopes["75"], before)
            script.scopes["75"].controller = "WKR"
            script.effect("VAD_lose_district_administration", "75")
            self.assertNotIn(modifier, script.scopes["75"].flags)
            self.assertTrue(self.start(script, name, "106"))
            script.run(self.orders[name]["remove_effect"])
            script.effect("VAD_close_administration")
            self.assertNotIn(modifier, script.scopes["106"].flags)

    def test_monarchy_focuses_are_imperial_only_and_need_an_industrial_charter(self):
        self.assertNotIn("VAD_convene_the_court_of_honours", self.focuses)
        for name, (focus_id, _, _, _, _) in self.routes.items():
            focus = self.focuses[focus_id]
            self.assertEqual(focus["cost"], "3")
            self.assertEqual(fields(focus["prerequisite"]), {"focus": "VAD_bind_officers_to_chancery"})
            script = self.campaign(name)
            script.globals.add(V + "phase_collapse")
            self.assertTrue(script.conditions(focus["available"]))
            for government in ("joint_government_formed", "collegial_staff_formed"):
                changed = deepcopy(script)
                changed.globals.add(V + government)
                self.assertFalse(changed.conditions(focus["available"]))
                self.assertFalse(changed.conditions(focus["allow_branch"]))
                self.assertFalse(self.start(changed, name))
            for target in ("75", "106"):
                script.scopes[target].resources["industrial_complex"] = 0
            self.assertFalse(script.conditions(focus["available"]))
            script.scopes["75"].resources["arms_factory"] = 1
            self.assertTrue(script.conditions(focus["available"]))

    def test_expiry_refresh_is_bounded_and_cannot_settle_a_later_order(self):
        event_id = V + "claimant.33"
        for name in self.routes:
            script = self.campaign(name)
            self.assertTrue(self.start(script, name))
            script.run(self.orders[name]["remove_effect"])
            queued = [fields(value) for key, _, value in script.calls
                      if key == "country_event" and fields(value)["id"] == event_id]
            self.assertEqual(queued, [{"id": event_id, "days": "91"}])
            event = fields(EVENTS[event_id])
            self.assertEqual(event["hidden"], "yes")
            self.assertEqual(event["is_triggered_only"], "yes")
            self.assertNotIn("option", event)
            self.assertNotIn("fire_only_once", event)
            self.assertTrue(self.start(script, name, "106"))
            for exists in (True, False):
                script.scopes["VAD"].exists = exists
                before = deepcopy(script.scopes)
                script.calls.clear()
                script.run(event["immediate"])
                self.assertEqual(script.scopes, before)
                self.assertEqual(script.calls, [("ADISCORD_economy_mark_dirty", "VAD", "yes")] if exists else [])

    def test_imperial_choices_have_matching_action_art_and_shine_masks(self):
        sprites = {}
        for path in ("interface/ADISCORD_national_focus.gfx", "interface/ADISCORD_focus_shines.gfx"):
            for key, _, value in walk(parse(read(path))):
                if key.lower() == "spritetype":
                    sprite = fields(value)
                    sprites[sprite["name"]] = sprite
        for name, filename in (("privileges", "focus_generic_concessions.dds"),
                               ("collateral", "focus_SWI_issue_war_bonds.dds")):
            icon = "GFX_focus_" + self.routes[name][0]
            texture = "gfx/interface/goals/" + filename
            self.assertEqual(sprites[icon]["texturefile"], texture)
            self.assertEqual(sprites[icon + "_shine"]["texturefile"], texture)
            self.assertEqual(fields(sprites[icon + "_shine"]["animation"])["animationmaskfile"], texture)
        self.assertNotIn("GFX_focus_VAD_convene_the_court_of_honours", sprites)
        self.assertNotIn("GFX_focus_VAD_convene_the_court_of_honours_shine", sprites)


class VADJointProgrammeTests(unittest.TestCase):
    kinds = {"congress": (6, 35, 500, 0), "operations": (7, 30, 0, 100)}

    def test_joint_focus_requirements_hide_only_redundant_cabinet_and_phase_flags(self):
        source = Path("focus_trees/Vorkerland/vad/focuses.txt").read_text(encoding="utf-8")
        tree = fields(parse(source))["focus_tree"]
        focuses = {fields(value)["id"]: fields(value) for key, _, value in tree if key == "focus"}
        for focus_id in ("VAD_convene_joint_congress", "VAD_sign_joint_operational_orders"):
            available = fields(focuses[focus_id]["available"])
            self.assertNotIn("has_global_flag", available)
            hidden = fields(available["hidden_trigger"])
            self.assertEqual(hidden["has_global_flag"], V + "joint_government_formed")
            self.assertEqual({value for key, _, value in hidden["OR"] if key == "has_global_flag"}, {
                V + "phase_collapse", V + "phase_regional_consolidation",
                V + "phase_central_preparation", V + "phase_central_showdown",
            })
            self.assertEqual(available["is_subject"], "no")
            self.assertEqual(fields(available["NOT"])["has_capitulated"], "yes")
            if focus_id == "VAD_convene_joint_congress":
                self.assertEqual(fields(available["custom_trigger_tooltip"])["tooltip"], "VAD_joint_congress_district_tt")
            else:
                self.assertEqual(available["has_war"], "yes")

    def test_joint_focus_choices_unlock_distinct_programmes_and_report_the_course(self):
        source = Path("focus_trees/Vorkerland/vad/focuses.txt").read_text(encoding="utf-8")
        tree = fields(parse(source))["focus_tree"]
        focuses = {fields(value)["id"]: fields(value) for key, _, value in tree if key == "focus"}
        pair = ("VAD_convene_joint_congress", "VAD_sign_joint_operational_orders")
        for index, focus_id in enumerate(pair):
            focus = focuses[focus_id]
            self.assertEqual(focus["cost"], "2")
            self.assertEqual(fields(focus["mutually_exclusive"])["focus"], pair[1 - index])
            self.assertEqual(fields(focus["prerequisite"])["focus"], "VAD_seat_the_dual_chamber")
            reward = fields(focus["completion_reward"])
            kind = ("congress", "operations")[index]
            self.assertEqual(reward["unlock_decision_tooltip"], "VAD_joint_" + kind + "_programme")
            self.assertEqual(fields(fields(reward["hidden_effect"])["news_event"])["id"], V + "story." + str(46 + index))

    @classmethod
    def setUpClass(cls):
        cls.base = VADDistrictAdministrationTests()
        cls.base.setUpClass()
        cls.orders = {name: fields(cls.base.category["VAD_joint_" + name + "_programme"])
                      for name in cls.kinds}

    def campaign(self):
        script = self.base.campaign()
        country = script.scopes["VAD"]
        country.leader = "WRK_VAD_Joint_Council"
        country.focuses.update({"VAD_convene_joint_congress", "VAD_sign_joint_operational_orders"})
        script.globals.update({V + "joint_government_formed", V + "worker_rescued_by_vlad"})
        country.enemies = {"WKR"}
        for target in ("75", "106"):
            self.assertTrue(self.base.start(script, "commandant", target))
            script.run(self.base.orders["commandant"]["remove_effect"])
            script.scopes[target].variables["VAD_district_unrest"] = 60
        country.resources.update(pp=1000, people=10000, support_equipment=500)
        script.source = None
        script.calls.clear()
        return script

    def start(self, script, kind):
        order = self.orders[kind]
        if not all(script.conditions(order[key]) for key in ("visible", "available", "custom_cost_trigger")):
            return False
        script.run(order["complete_effect"])
        return True

    def test_prices_and_shared_chancery_do_not_depend_on_from_scope(self):
        for kind, (receipt, pp, people, support) in self.kinds.items():
            for scarce in (None, "pp", "people" if people else "support_equipment"):
                script = self.campaign()
                country = script.scopes["VAD"]
                country.resources.update(pp=pp, people=people, support_equipment=support)
                if scarce:
                    country.resources[scarce] -= .01
                before = deepcopy(country.resources)
                self.assertEqual(self.start(script, kind), scarce is None)
                if scarce:
                    self.assertEqual(country.resources, before)
                    continue
                self.assertEqual(country.variables["VAD_oath_kind"], receipt)
                self.assertNotIn("VAD_oath_state", country.variables)
                self.assertEqual((country.resources["pp"], country.resources["people"], country.resources["support_equipment"]), (0, 0, 0))
                self.assertFalse(self.start(script, kind))
                self.assertFalse(self.base.start(script, "charter", "107"))
                self.assertEqual(self.orders[kind]["days_remove"], "14")

    def test_congress_relief_applies_to_owned_commandantures_and_ends_revolts(self):
        script = self.campaign()
        script.scopes["75"].variables["VAD_district_unrest"] = 100
        script.scopes["75"].flags.add(V + "vad_district_uprising")
        script.scopes["106"].controller = "WKR"
        self.assertTrue(self.start(script, "congress"))
        self.assertEqual(script.scopes["75"].variables["VAD_district_unrest"], 100)
        script.run(self.orders["congress"]["remove_effect"])
        self.assertEqual(script.scopes["75"].variables["VAD_district_unrest"], 80)
        self.assertNotIn(V + "vad_district_uprising", script.scopes["75"].flags)
        self.assertEqual(script.scopes["106"].variables["VAD_district_unrest"], 60)
        self.assertEqual(script.scopes["VAD"].resources["people"], 9500)
        self.base.assert_released(script)

    def test_operations_apply_a_timed_result_and_real_local_pressure(self):
        script = self.campaign()
        script.scopes["75"].variables["VAD_district_unrest"] = 95
        self.assertTrue(self.start(script, "operations"))
        script.run(self.orders["operations"]["remove_effect"])
        self.assertIn("VAD_joint_operational_orders", script.scopes["VAD"].flags)
        self.assertEqual(script.scopes["75"].variables["VAD_district_unrest"], 100)
        self.assertIn(V + "vad_district_uprising", script.scopes["75"].flags)
        timed = [fields(value) for key, _, value in script.calls if key == "add_timed_idea"]
        self.assertEqual(timed, [{"idea": "VAD_joint_operational_orders", "days": "35"}])
        self.assertEqual([fields(value)["id"] for key, _, value in script.calls if key == "country_event"], [V + "claimant.15"])
        delivered = deepcopy((script.scopes, script.calls))
        script.run(self.orders["operations"]["remove_effect"])
        script.run(self.orders["operations"]["cancel_effect"])
        self.assertEqual((script.scopes, script.calls), delivered)
        script.effect("VAD_close_administration")
        self.assertNotIn("VAD_joint_operational_orders", script.scopes["VAD"].flags)

    def test_invalid_cabinet_and_terminal_paths_refund_once(self):
        for kind, reason in product(self.kinds, ("leader", "subject", "capitulation", "end")):
            script = self.campaign()
            country = script.scopes["VAD"]
            before = deepcopy(country.resources)
            self.assertTrue(self.start(script, kind))
            if reason == "leader":
                country.leader = "WRK_Vlad_Petrichev"
            elif reason == "subject":
                country.subject = "WKR"
            elif reason == "capitulation":
                country.capitulated = True
            else:
                script.globals.add(V + "central_war_finished")
            self.assertTrue(script.conditions(self.orders[kind]["cancel_trigger"]))
            script.run(self.orders[kind]["remove_effect"])
            script.run(self.orders[kind]["cancel_effect"])
            self.assertEqual(country.resources, before)
            self.base.assert_released(script)
        script = self.campaign()
        self.assertTrue(self.start(script, "operations"))
        script.scopes["VAD"].enemies.clear()
        self.assertTrue(script.conditions(self.orders["operations"]["cancel_trigger"]))
        script.run(self.orders["operations"]["remove_effect"])
        self.assertEqual(script.scopes["VAD"].resources["support_equipment"], 500)

    def test_handoff_returns_paid_resources_and_does_not_dispatch_pending_reward(self):
        for kind, (_, pp, people, support) in self.kinds.items():
            script = self.campaign()
            self.assertTrue(self.start(script, kind))
            target = script.scopes["WRK"]
            before = deepcopy(target.resources)
            script.effect("VAD_settle_oath_handoff", "WRK")
            script.effect("VAD_settle_oath_handoff", "WRK")
            self.assertEqual(target.resources["pp"], before["pp"] + pp)
            self.assertEqual(target.resources["people"], before["people"] + people)
            self.assertEqual(target.resources["support_equipment"], before["support_equipment"] + support)
            settled = deepcopy(script.scopes)
            script.run(self.orders[kind]["remove_effect"])
            self.assertEqual(script.scopes, settled)

    def test_local_receipt_cannot_be_settled_by_a_national_programme_callback(self):
        script = self.campaign()
        self.assertTrue(self.base.start(script, "commandant", "107"))
        before = deepcopy(script.scopes)
        for order in self.orders.values():
            script.run(order["remove_effect"])
            script.run(order["cancel_effect"])
        self.assertEqual(script.scopes, before)

    def test_joint_foundation_reports_once_when_the_cabinet_is_actually_chosen(self):
        script = self.base.campaign()
        country = script.scopes["VAD"]
        country.focuses.discard("VAD_open_imperial_registers")
        country.focuses.add("VAD_proclaim_joint_charter")
        country.character_roles["WRK_VAD_Joint_Council"] = {"pragmatism_ideology"}
        script.globals.add(V + "worker_rescued_by_vlad")
        for _ in range(2):
            script.effect(V + "form_joint_government")
        news = [fields(value)["id"] for key, _, value in script.calls if key == "news_event"]
        self.assertEqual(news, [V + "story.44"])
