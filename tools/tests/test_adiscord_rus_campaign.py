"""Parsed RUS accounting and campaign contracts; not native-engine simulation."""

from copy import deepcopy
from itertools import permutations, product
from pathlib import Path
import json
import re
import unittest
from unittest.mock import patch

from PIL import Image

from tools.builders.build_adiscord_focus_trees import expected_outputs
from tools.lib.paths import source_section
from tools.tests.test_adiscord_stp_preparation import block, matches_conditions, scalar, walk
from tools.validators.validate_adiscord_division_templates import parse_clausewitz


ROOT = Path(__file__).resolve().parents[2]
BASE = "ADISCORD_RUS"


def read(path):
    return (ROOT / path).read_text(encoding="utf-8-sig")


def parse(path):
    return parse_clausewitz(read(path))


class BunkerWorld:
    """Execute actual parsed receipts and rewards; clocks remain explicit callbacks.

    Unsupported conditions/effects fail loudly. This model does not prove the
    game's timer order, icon rendering, or country-event timeout behaviour.
    """

    def __init__(self, campaign, fresh=False):
        self.effects = campaign.effects
        self.triggers = campaign.triggers
        self.decisions = campaign.decisions
        self.variables = {"ADISCORD_economy_treasury": 100.0 if fresh else 10000.0}
        self.temporary = {}
        self.pp = 0.0 if fresh else 1000.0
        self.equipment = {"support_equipment": 0.0 if fresh else 2000.0, "infantry_equipment": 10000.0}
        self.equipment_by_producer = {}
        self.flags = {"RUS_campaign_start_pending"}
        self.global_flags = set()
        # A campaign completes one alternative of each exclusive bunker pair.
        self.focuses = set() if fresh else set(campaign.focuses) - {"RUS_bunker_layer_service_school", "RUS_bunker_contingency_reservoir"}
        self.ideas = set()
        self.modifiers = set()
        self.active = set()
        self.missions = set()
        self.events = []
        self.ruler = "RUS_Mark_Rustan"
        self.characters = set(campaign.initial_characters)
        self.advisor_roles = campaign.advisor_roles
        self.advisors = {}
        self.held_states = set()
        self.val_held_states = set()
        self.state_controllers = {}
        self.subject_overlords = {}
        self.templates = set()
        self.recruitable_templates = set()
        self.created_units = []
        self.technologies = set()
        self.law_groups = getattr(campaign, "law_groups", [])
        self.tech_bonuses = []
        self.cores = set()
        self.claims = set()
        self.ideology = "etatism"
        self.bop_id = None
        self.bop = 0.0
        self.army_experience = 0.0
        self.air_experience = 0.0
        self.fuel = 0.0
        self.command_power = 0.0
        self.manpower = 0.0
        self.stability = 0.0
        self.war_support = 0.0
        self.research_slots = 0
        self.war_support = 0.0
        self.research_slots = 0
        self.subject = False
        self.capitulated = False
        self.war = True
        self.ai = True
        self.owner = True
        self.controller = True
        self.divisions = 2
        self.dirty = 0
        self.buildings = {"infrastructure": 2, "arms_factory": 5, "industrial_complex": 0, "air_base": 2, "fuel_silo": 0}
        self.building_slots = 6
        self.railway_orders = []
        self.state_construction = []
        self.target_state = "329"
        self.regions = {
            state: {"owner": "RUS", "controller": "RUS", "category": "wasteland", "infrastructure": 1, "flags": set()}
            for state in ("329", "330", "292", "296")
        }
        self.run("RUS_campaign_initialize")

    def matches_state(self, rows, state):
        data = self.regions[state]
        results = []
        entries = iter(rows)
        for entry in entries:
            key, value = entry.key, entry.value
            if not key:
                assert value == "infrastructure", entry
                operator, amount = next(entries), next(entries)
                result = self.compare(data[value], operator.value, float(amount.value))
            elif key in self.triggers:
                result = self.matches_state(self.triggers[key], state) == (value == "yes")
            elif key in ("AND", "hidden_trigger"):
                result = self.matches_state(value, state)
            elif key == "OR":
                result = any(self.matches_state([row], state) for row in value)
            elif key == "NOT":
                result = not self.matches_state(value, state)
            elif key == "custom_trigger_tooltip":
                result = self.matches_state([row for row in value if row.key != "tooltip"], state)
            elif key in ("ROOT", "RUS"):
                result = self.matches(value)
            elif key == "state":
                result = state == value
            elif key in ("is_owned_by", "is_controlled_by"):
                owner = "RUS" if value == "ROOT" else value
                result = data["owner" if key == "is_owned_by" else "controller"] == owner
            elif key == "has_state_category":
                result = data["category"] == value
            elif key == "has_state_flag":
                result = value in data["flags"]
            else:
                raise AssertionError(f"Unsupported state condition: {entry}")
            results.append(result)
        return all(results)

    def execute_state(self, rows, state):
        data = self.regions[state]
        taken = False
        for entry in rows:
            key, value = entry.key, entry.value
            if key in ("if", "else_if", "else"):
                if key == "if":
                    taken = False
                gate = next((row.value for row in value if row.key == "limit"), [])
                if not taken and self.matches_state(gate, state):
                    taken = True
                    self.execute_state([row for row in value if row.key != "limit"], state)
            elif key in ("ROOT", "RUS"):
                self.execute(value)
            elif key == "set_state_flag":
                data["flags"].add(value)
            elif key == "clr_state_flag":
                data["flags"].discard(value)
            elif key == "set_state_category":
                data["category"] = value
            elif key == "add_core_of":
                self.cores.add((state, value))
            elif key == "add_claim_by":
                self.claims.add((state, value))
            elif key == "add_building_construction":
                self.assert_infrastructure(value)
                self.state_construction.append((state, int(scalar(value, "level"))))
                data["infrastructure"] = min(5, data["infrastructure"] + int(scalar(value, "level")))
            else:
                raise AssertionError(f"Unsupported state effect: {entry}")

    @staticmethod
    def assert_infrastructure(rows):
        assert scalar(rows, "type") == "infrastructure", rows
        assert scalar(rows, "instant_build") == "yes", rows

    def value(self, token):
        if token == "amount_research_slots":
            return self.research_slots
        try:
            return float(token)
        except ValueError:
            return self.temporary.get(token, self.variables.get(token, 0))

    @staticmethod
    def compare(left, operator, right):
        return {"equals": left == right, "not_equals": left != right, "less_than": left < right,
                "greater_than": left > right, "less_than_or_equals": left <= right,
                "greater_than_or_equals": left >= right, "<": left < right,
                ">": left > right}[operator]

    def matches(self, rows):
        results = []
        index = 0
        while index < len(rows):
            entry = rows[index]
            key, value = entry.key, entry.value
            index += 1
            if not key:
                assert value in ("has_political_power", "has_manpower", "num_of_controlled_states", "infrastructure", "air_base"), value
                operator, amount = rows[index:index + 2]
                index += 2
                current = {
                    "has_political_power": self.pp,
                    "has_manpower": self.manpower,
                    "num_of_controlled_states": self.variables.get("num_controlled_states", 1),
                }.get(value)
                if current is None:
                    current = self.buildings[value]
                result = self.compare(current, operator.value, self.value(amount.value))
            elif key in self.triggers:
                assert value in ("yes", "no"), (key, value)
                result = self.matches(self.triggers[key]) == (value == "yes")
            elif key in ("AND", "hidden_trigger"):
                result = self.matches(value)
            elif key == "OR":
                result = any(self.matches([child]) for child in value)
            elif key == "NOT":
                result = not self.matches(value)
            elif key == "custom_trigger_tooltip":
                result = self.matches([child for child in value if child.key != "tooltip"])
            elif key == "check_variable":
                result = self.compare(self.value(scalar(value, "var")), scalar(value, "compare"), self.value(scalar(value, "value")))
            elif key == "has_equipment":
                equipment, operator, amount = [child.value for child in value]
                result = self.compare(self.equipment.get(equipment, 0), operator, self.value(amount))
            elif key == "has_country_leader":
                assert scalar(value, "ruling_only") == "yes"
                result = self.ruler == scalar(value, "character")
            elif key == "has_character":
                result = value in self.characters
            elif key == "has_power_balance":
                assert isinstance(value, list), value
                result = self.bop_id == scalar(value, "id")
            elif key == "power_balance_value":
                comparison = [row.value for row in value if not row.key]
                assert len(comparison) == 3 and comparison[0] == "value", value
                result = self.bop_id == scalar(value, "id") and self.compare(self.bop, comparison[1], self.value(comparison[2]))
            elif key in ("is_subject", "has_capitulated"):
                result = {"is_subject": self.subject, "has_capitulated": self.capitulated}[key] == (value == "yes")
            elif key == "has_war":
                result = self.war == (value == "yes")
            elif key == "exists":
                result = value == "yes"
            elif key == "is_ai":
                result = self.ai == (value == "yes")
            elif key == "tag":
                result = value == "RUS"
            elif key == "has_variable":
                result = value in self.variables
            elif key == "has_country_flag":
                result = value in self.flags
            elif key == "has_global_flag":
                result = value in self.global_flags
            elif key == "has_completed_focus":
                result = value in self.focuses
            elif key == "has_dynamic_modifier":
                result = scalar(value, "modifier") in self.modifiers
            elif key == "has_decision":
                result = value in self.active
            elif key == "has_idea":
                result = value in self.ideas
            elif key == "66":
                result = self.matches(value)
            elif key == "FROM":
                result = self.matches_state(value, self.target_state)
            elif key == "every_state":
                state_id = next((child.value for child in value if child.key == "limit" for child in child.value if child.key == "id"), None)
                result = state_id is not None
            elif key == "free_building_slots":
                occupied = sum(self.buildings[kind] for kind in ("arms_factory", "industrial_complex", "fuel_silo"))
                result = self.building_slots - occupied >= int(scalar(value, "size"))
            elif key in ("owns_state", "controls_state"):
                if value == "66":
                    result = self.owner if key == "owns_state" else self.controller
                elif value in self.regions:
                    field = "owner" if key == "owns_state" else "controller"
                    result = self.regions[value][field] == "RUS"
                else:
                    result = value in self.held_states
            elif key == "VAL":
                assert value and all(row.key == "controls_state" for row in value), value
                result = all(row.value in self.val_held_states for row in value)
            elif key.isdigit():
                facts = {
                    (state, "controller"): country
                    for state, country in self.state_controllers.items()
                }
                facts.update({
                    (country, "is_subject_of", overlord): True
                    for country, overlord in self.subject_overlords.items()
                })
                result = matches_conditions(value, facts, key)
            elif key == "has_template":
                result = value in self.templates
            elif key == "always":
                result = value == "yes"
            else:
                raise AssertionError(f"Unsupported condition: {entry}")
            results.append(result)
            if not result:
                return False
        return all(results)

    def execute(self, rows):
        taken = False
        for entry in rows:
            key, value = entry.key, entry.value
            if key in ("if", "else_if", "else"):
                if key == "if":
                    taken = False
                gate = next((child.value for child in value if child.key == "limit"), [])
                if not taken and self.matches(gate):
                    taken = True
                    self.execute([child for child in value if child.key != "limit"])
            elif key == "hidden_effect":
                self.execute(value)
            elif key == "66":
                self.execute(value)
            elif key == "FROM":
                self.execute_state(value, self.target_state)
            elif key in self.regions:
                self.execute_state(value, key)
            elif key == "capital_scope":
                self.execute(value)
            elif key == "every_owned_state":
                gate = next((row.value for row in value if row.key == "limit"), [])
                for state, data in self.regions.items():
                    if data["owner"] == "RUS" and self.matches_state(gate, state):
                        self.execute_state([row for row in value if row.key != "limit"], state)
            elif key == "build_railway":
                self.railway_orders.append((scalar(value, "start_state"), scalar(value, "target_state"), int(scalar(value, "level"))))
            elif key == "create_unit":
                count = [row.value for row in value if row.key == "count"]
                self.divisions += int(count[0]) if count else 1
                self.created_units.append((scalar(value, "division"), int(count[0]) if count else 1))
            elif key == "division_template":
                self.templates.add(scalar(value, "name"))
            elif key == "set_division_force_allow_recruiting":
                name = scalar(value, "division_template")
                if scalar(value, "force_allow_recruiting") == "yes":
                    self.recruitable_templates.add(name)
                else:
                    self.recruitable_templates.discard(name)
            elif key == "set_technology":
                self.technologies.update(row.key for row in value if row.value == "1")
            elif key == "add_tech_bonus":
                self.tech_bonuses.append(scalar(value, "name"))
            elif key == "add_extra_state_shared_building_slots":
                self.building_slots += int(value)
            elif key.isdigit():
                for child in value:
                    if child.key == "add_core_of":
                        self.cores.add((key, child.value))
                    elif child.key == "add_claim_by":
                        self.claims.add((key, child.value))
            elif key == "every_state":
                state_id = next((child.value for child in value if child.key == "limit" for child in child.value if child.key == "id"), None)
                if state_id is not None:
                    for child in value:
                        if child.key == "add_core_of":
                            self.cores.add((state_id, child.value))
                        elif child.key == "add_claim_by":
                            self.claims.add((state_id, child.value))
            elif key == "add_building_construction":
                self.buildings[scalar(value, "type")] += int(scalar(value, "level"))
            elif key == "add_timed_idea":
                self.ideas.add(scalar(value, "idea"))
            elif key == "ADISCORD_vorkerland_ensure_limited_conscription":
                self.ideas.add("limited_conscription")
            elif key in ("effect_tooltip", "custom_effect_tooltip", "unlock_decision_tooltip"):
                continue
            elif key in ("set_variable", "add_to_variable", "subtract_from_variable", "multiply_variable", "divide_variable", "set_temp_variable", "add_to_temp_variable", "subtract_from_temp_variable", "multiply_temp_variable", "divide_temp_variable"):
                target = self.temporary if "temp" in key else self.variables
                name = scalar(value, "var")
                amount = self.value(scalar(value, "value"))
                if key.startswith("set_"):
                    target[name] = amount
                elif key.startswith("add_"):
                    target[name] = target.get(name, 0) + amount
                elif key.startswith("subtract_"):
                    target[name] = target.get(name, 0) - amount
                elif key.startswith("divide_"):
                    target[name] = target.get(name, 0) / amount
                else:
                    target[name] = target.get(name, 0) * amount
            elif key == "clear_variable":
                self.variables.pop(value, None)
            elif key in ("clamp_variable", "clamp_temp_variable"):
                target = self.temporary if "temp" in key else self.variables
                name = scalar(value, "var")
                target[name] = min(float(scalar(value, "max")), max(float(scalar(value, "min")), self.value(name)))
            elif key == "add_political_power":
                self.pp += self.value(value)
            elif key == "army_experience":
                self.army_experience += self.value(value)
            elif key == "air_experience":
                self.air_experience += self.value(value)
            elif key == "add_fuel":
                self.fuel += self.value(value)
            elif key == "add_command_power":
                self.command_power += self.value(value)
            elif key == "add_manpower":
                self.manpower += self.value(value)
            elif key == "add_stability":
                self.stability = max(0, min(1, self.stability + self.value(value)))
            elif key == "add_war_support":
                self.war_support = max(0, min(1, self.war_support + self.value(value)))
            elif key == "add_research_slot":
                self.research_slots += int(value)
            elif key == "add_war_support":
                self.war_support = max(0, min(1, self.war_support + self.value(value)))
            elif key == "add_research_slot":
                self.research_slots += int(value)
            elif key == "recruit_character":
                self.characters.add(value)
            elif key == "activate_advisor":
                character, role = self.advisor_roles[value]
                assert character in self.characters, character
                self.advisors[scalar(role, "slot")] = value
            elif key == "set_politics":
                self.ideology = scalar(value, "ruling_party")
            elif key == "set_power_balance":
                self.bop_id = scalar(value, "id")
                self.bop = self.value(scalar(value, "set_value"))
            elif key == "add_power_balance_value":
                assert self.bop_id == scalar(value, "id"), value
                self.bop = max(-1, min(1, self.bop + self.value(scalar(value, "value"))))
            elif key == "remove_power_balance":
                assert self.bop_id == scalar(value, "id"), value
                self.bop_id = None
            elif key == "promote_character":
                character = scalar(value, "character")
                assert character in self.characters, character
                self.ruler = character
            elif key == "retire_character":
                self.characters.discard(value)
                if self.ruler == value:
                    self.ruler = None
            elif key == "add_equipment_to_stockpile":
                equipment = scalar(value, "type")
                if equipment == "infantry_equipment_0":
                    equipment = "infantry_equipment"
                amount = self.value(scalar(value, "amount"))
                if equipment in self.equipment_by_producer:
                    lots = self.equipment_by_producer[equipment]
                    producer = next((row.value for row in value if row.key == "producer"), None)
                    if amount < 0:
                        remaining = -amount
                        for origin in lots:
                            if producer is None or origin == producer:
                                removed = min(remaining, lots[origin])
                                lots[origin] -= removed
                                remaining -= removed
                    else:
                        lots[producer or "RUS"] = lots.get(producer or "RUS", 0) + amount
                    self.equipment[equipment] = sum(lots.values())
                else:
                    self.equipment[equipment] = self.equipment.get(equipment, 0) + amount
            elif key == "set_country_flag":
                self.flags.add(scalar(value, "flag") if isinstance(value, list) else value)
            elif key == "clr_country_flag":
                self.flags.discard(value)
            elif key == "remove_decision":
                self.active.discard(value)
            elif key in ("add_dynamic_modifier", "remove_dynamic_modifier"):
                name = scalar(value, "modifier")
                if key.startswith("add"):
                    self.modifiers.add(name)
                else:
                    self.modifiers.discard(name)
            elif key in ("add_ideas", "remove_ideas"):
                names = [row.value for row in value] if isinstance(value, list) else [value]
                if key.startswith("add"):
                    for name in names:
                        for group in self.law_groups:
                            if name in group:
                                self.ideas.difference_update(group)
                    self.ideas.update(names)
                else:
                    self.ideas.difference_update(names)
            elif key == "country_event":
                self.events.append(scalar(value, "id"))
            elif key == "activate_decision":
                self.begin(value)
            elif key == "activate_mission":
                self.missions.add(value)
            elif key == "force_update_dynamic_modifier":
                continue
            elif key == "ADISCORD_economy_mark_dirty":
                self.dirty += 1
            elif key in self.effects:
                assert value == "yes", (key, value)
                self.run(key)
            else:
                raise AssertionError(f"Unsupported effect: {entry}")

    def run(self, effect):
        self.execute(self.effects[effect])

    def begin(self, name):
        rows = self.decisions[name]
        assert self.matches(block(rows, "available")), name
        assert self.matches(block(rows, "visible")), name
        if any(entry.key == "custom_cost_trigger" for entry in rows):
            assert self.matches(block(rows, "custom_cost_trigger")), name
        price = float(scalar(rows, "cost"))
        assert self.pp >= price, name
        self.pp -= price
        self.active.add(name)
        self.execute(block(rows, "complete_effect"))

    def finish(self, name):
        self.active.discard(name)
        self.execute(block(self.decisions[name], "remove_effect"))

    def balances(self):
        return self.pp, self.value("ADISCORD_economy_treasury"), self.equipment["support_equipment"]


class RusCampaignTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.effects = {}
        for source in ("ADISCORD_vorkerland_effects", "ADISCORD_RUS_scripted_effects"):
            cls.effects.update({e.key: e.value for e in parse(f"common/scripted_effects/{source}.txt")})
        cls.effects.update({e.key: e.value for e in parse("common/scripted_effects/ADISCORD_society_development_effects.txt")})
        development_effects = {
            "ADISCORD_calculate_science_development_gain",
            "ADISCORD_economy_calculate_other_development_gains",
            "ADISCORD_economy_calculate_social_development_gain",
            "ADISCORD_economy_check_economic_development_upgrade",
            "ADISCORD_economy_refresh_existing_economic_development_idea",
        }
        cls.effects.update({e.key: e.value for e in parse("common/scripted_effects/ADISCORD_economy_effects.txt") if e.key in development_effects})
        cls.triggers = {e.key: e.value for e in parse(f"common/scripted_triggers/ADISCORD_RUS_scripted_triggers.txt")}
        cls.triggers.update({e.key: e.value for e in parse("common/scripted_triggers/ADISCORD_vorkerland_triggers.txt")})
        for source in ("ADISCORD_society_development_triggers", "ADISCORD_economy_triggers"):
            cls.triggers.update({e.key: e.value for e in parse(f"common/scripted_triggers/{source}.txt")})
        cls.effects.update({e.key: e.value for e in parse("common/scripted_effects/ADISCORD_shared_action_effects.txt") if e.key.startswith("ADISCORD_campaign_slot_")})
        cls.triggers.update({e.key: e.value for e in parse("common/scripted_triggers/ADISCORD_shared_action_triggers.txt") if e.key == "ADISCORD_has_campaign_slot"})
        cls.decisions = {e.key: e.value for e in block(parse(f"common/decisions/{BASE}_decisions.txt"), "RUS_bunker_construction")}
        cls.programmes = {e.key: e.value for e in block(parse(f"common/decisions/{BASE}_decisions.txt"), "RUS_development_programmes")}
        cls.campaigns = {e.key: e.value for e in block(parse(f"common/decisions/{BASE}_decisions.txt"), "RUS_public_campaigns")}
        cls.balance = {e.key: e.value for e in block(parse(f"common/decisions/{BASE}_decisions.txt"), "RUS_state_balance_measures_category")}
        cls.suspicion = {e.key: e.value for e in block(parse(f"common/decisions/{BASE}_decisions.txt"), "RUS_state_balance_category")}
        cls.belt = {e.key: e.value for e in block(parse(f"common/decisions/{BASE}_decisions.txt"), "RUS_reactor_belt_category")}
        cls.labs = {e.key: e.value for e in block(parse(f"common/decisions/{BASE}_decisions.txt"), "RUS_experimental_labs_category")}
        tree = block(parse("focus_trees/RUS/main/focuses.txt"), "focus_tree")
        cls.focuses = {scalar(e.value, "id"): e.value for e in tree if e.key == "focus"}
        cls.ideas = {}
        for section in ("rus_crisis_ideas", "rus_campaign_ideas"):
            source = source_section(read("common/ideas/ADISCORD_RUS_ideas.txt"), section)
            country_ideas = block(block(parse_clausewitz(source), "ideas"), "country")
            cls.ideas.update({row.key: row.value for row in country_ideas})
        cls.law_groups = []
        for source in ("_economic", "ADISCORD_laws"):
            for group in block(parse(f"common/ideas/{source}.txt"), "ideas"):
                if isinstance(group.value, list):
                    cls.law_groups.append({row.key for row in group.value if isinstance(row.value, list)})
        cls.projects = [name for name, rows in cls.decisions.items() if name != "RUS_bunker_energy_sale" and any(e.key == "days_remove" for e in rows)]
        cls.loc = dict(re.findall(r'^\s+([A-Za-z0-9_.]+):(?:\d+)?\s+"(.*)"\s*$', read(f"localisation/russian/{BASE}_l_russian.yml"), re.M))
        cls.initial_characters = {
            row.value for row in parse("history/countries/RUS - RusniaLand.txt")
            if row.key == "recruit_character"
        }
        cls.advisor_roles = {
            scalar(role.value, "idea_token"): (character.key, role.value)
            for character in block(parse("common/characters/RUS.txt"), "characters")
            for role in character.value if role.key == "advisor"
        }

    def world(self):
        return BunkerWorld(self)

    def test_development_reforms_cover_six_axes_and_reveal_their_programmes(self):
        specs = {
            "RUS_count_the_hearths": ("society", "RUS_community_assemblies"),
            "RUS_school_of_scribes": ("cultural", "RUS_public_reading_rooms"),
            "RUS_officer_courses": ("army", "RUS_regimental_training"),
            "RUS_roadside_clinics": ("social_system", "RUS_district_health_programme"),
            "RUS_machine_school": ("economic", "RUS_workshop_training"),
            "RUS_aimaq_service_charter": ("state", "RUS_civil_service_training"),
            "RUS_civil_service_examinations": ("state", "RUS_civil_service_training"),
        }
        category = block(parse(f"common/decisions/categories/ADISCORD_decision_categories_RUS.txt"), "RUS_development_programmes")
        for focus, (axis, programme) in specs.items():
            with self.subTest(focus=focus):
                world = self.world()
                world.focuses = {focus}
                world.execute(block(self.focuses[focus], "completion_reward"))
                self.assertEqual(world.value(f"ADISCORD_{axis}_development_progress"), 25)
                self.assertEqual(world.value(f"ADISCORD_{axis}_development_monthly_growth"), 2)
                self.assertTrue(world.matches(block(category, "visible")))
                self.assertTrue(world.matches(block(self.programmes[programme], "visible")))
                self.assertTrue(world.matches(block(self.programmes[programme], "available")))

    def test_monthly_development_preserves_fractional_and_large_remainders(self):
        for axis in ("society", "social_system", "army", "cultural", "state", "economic"):
            for initial in (99.5, 130.25, 250):
                with self.subTest(axis=axis, initial=initial):
                    world = self.world()
                    world.run("ADISCORD_initialize_society_development_variables")
                    level = f"ADISCORD_{axis}_development_level"
                    progress = f"ADISCORD_{axis}_development_progress"
                    world.variables.update({
                        level: 2, progress: initial,
                        f"ADISCORD_{axis}_development_monthly_growth": 2,
                        "ADISCORD_economy_monthly_development_gain": 2,
                        "ADISCORD_country_development_final_global_growth_factor_bp": 100,
                        f"ADISCORD_country_development_final_{axis}_growth_factor_bp": 100,
                    })
                    world.run(f"ADISCORD_tick_{axis}_development_monthly")
                    self.assertEqual(world.value(level), 3)
                    self.assertAlmostEqual(world.value(progress), initial + 2 - 100)
                    world.run(f"ADISCORD_tick_{axis}_development_monthly")
                    earned = initial + 4
                    self.assertAlmostEqual((world.value(level) - 2) * 100 + world.value(progress), earned)

    def test_development_display_and_tick_use_the_same_modified_gain(self):
        for axis in ("society", "army", "cultural", "state"):
            world = self.world()
            world.run("ADISCORD_initialize_society_development_variables")
            world.variables.update({
                f"ADISCORD_{axis}_development_monthly_growth": 2,
                "ADISCORD_country_development_final_global_growth_factor_bp": 120,
                f"ADISCORD_country_development_final_{axis}_growth_factor_bp": 150,
            })
            world.run("ADISCORD_economy_calculate_other_development_gains")
            gain = world.value(f"ADISCORD_{axis}_development_monthly_gain")
            world.run(f"ADISCORD_tick_{axis}_development_monthly")
            self.assertAlmostEqual(gain, 3.6)
            self.assertAlmostEqual(world.value(f"ADISCORD_{axis}_development_progress"), gain)
            for language in ("russian", "english"):
                source = read(f"localisation/{language}/ADISCORD_society_development_l_{language}.yml")
                self.assertIn(f"[?ADISCORD_{axis}_development_monthly_gain|=+1]", source)
                self.assertNotIn(f"[?ADISCORD_{axis}_development_monthly_growth|", source)

    def test_science_display_and_tick_use_research_slots_and_current_budget(self):
        world = self.world()
        world.run("ADISCORD_initialize_society_development_variables")
        world.research_slots = 2
        world.variables.update({
            "ADISCORD_science_development_monthly_growth": 2,
            "ADISCORD_country_development_final_global_growth_factor_bp": 120,
        })
        for budget, expected in ((2, 3.12), (4, 9.6), (2, 3.12)):
            with self.subTest(budget=budget):
                world.variables["ADISCORD_economy_research_spending_mode"] = budget
                before = world.value("ADISCORD_science_development_progress")
                world.run("ADISCORD_economy_calculate_other_development_gains")
                self.assertAlmostEqual(world.value("ADISCORD_science_development_monthly_gain"), expected)
                world.run("ADISCORD_tick_science_development_monthly")
                self.assertAlmostEqual(world.value("ADISCORD_science_development_progress") - before, expected)

    def test_focus_advisors_use_recruited_characters_and_registered_slots(self):
        for focus, token, slot in (
            ("RUS_staff_college", "RUS_Vyazemsky_theorist", "theorist"),
            ("RUS_imperial_general_staff", "RUS_Rakitin_army_chief", "army_chief"),
        ):
            with self.subTest(focus=focus):
                world = self.world()
                character, role = self.advisor_roles[token]
                self.assertIn(character, self.initial_characters)
                self.assertEqual(scalar(block(role, "available"), "has_completed_focus"), focus)
                reward = block(self.focuses[focus], "completion_reward")
                world.execute(reward)
                self.assertEqual(world.advisors[slot], token)
                world.characters.remove(character)
                with self.assertRaises(AssertionError):
                    world.execute(reward)

    def test_development_caps_discard_only_progress_beyond_the_terminal_level(self):
        for axis in ("society", "social_system", "army", "cultural", "state", "economic"):
            for level, progress, expected_level, expected_progress in (
                (4, 130, 5, 0), (5, 30, 5, 0),
                (3, -130, 2, -30), (2, -130, 1, 0), (1, -30, 1, 0),
            ):
                with self.subTest(axis=axis, level=level, progress=progress):
                    world = self.world()
                    world.run("ADISCORD_initialize_society_development_variables")
                    world.variables.update({
                        "ADISCORD_state_development_level": 4,
                        f"ADISCORD_{axis}_development_level": level,
                        f"ADISCORD_{axis}_development_progress": progress,
                        "ADISCORD_economy_monthly_development_gain": 0,
                    })
                    world.run(f"ADISCORD_tick_{axis}_development_monthly")
                    self.assertEqual(world.value(f"ADISCORD_{axis}_development_level"), expected_level)
                    self.assertEqual(world.value(f"ADISCORD_{axis}_development_progress"), expected_progress)

    def test_economic_readiness_holds_earned_progress_until_recovery(self):
        world = self.world()
        world.run("ADISCORD_initialize_society_development_variables")
        world.variables.update({
            "ADISCORD_economic_development_progress": 127.5,
            "ADISCORD_economy_monthly_development_gain": 0,
            "ADISCORD_economy_treasury": 24.99,
        })
        world.run("ADISCORD_tick_economic_development_monthly")
        self.assertEqual(world.value("ADISCORD_economic_development_level"), 1)
        self.assertEqual(world.value("ADISCORD_economic_development_progress"), 127.5)
        world.variables["ADISCORD_economy_treasury"] = 25
        world.run("ADISCORD_tick_economic_development_monthly")
        self.assertEqual(world.value("ADISCORD_economic_development_level"), 2)
        self.assertEqual(world.value("ADISCORD_economic_development_progress"), 27.5)

    def test_energy_sale_reserves_capacity_until_completion_without_double_payment(self):
        name = "RUS_bunker_energy_sale"
        rows = self.decisions[name]
        self.assertEqual(scalar(rows, "days_remove"), "90")
        for capacity, permitted in ((0.999, False), (1, True)):
            world = self.world()
            world.variables["RUS_bunker_free_power"] = capacity
            before = world.balances()
            self.assertEqual(world.matches(block(rows, "custom_cost_trigger")), permitted)
            world.run("RUS_bunker_energy_sale_start")
            self.assertEqual(world.value("ADISCORD_economy_treasury") - before[1], 100 if permitted else 0)
        world = self.world()
        before = world.balances()
        capacity = world.value("RUS_bunker_free_power")
        world.begin(name)
        paid = world.balances()
        self.assertEqual(paid[1] - before[1], 100)
        self.assertEqual(world.value("RUS_bunker_free_power"), capacity - 1)
        self.assertEqual(world.value("RUS_bunker_used_power"), 1)
        for _ in range(3):
            world.run("RUS_bunker_refresh")
            world.run("RUS_bunker_energy_sale_start")
            self.assertEqual(world.balances(), paid)
            self.assertEqual(world.value("RUS_bunker_free_power"), capacity - 1)
        self.assertFalse(world.matches(block(rows, "available")))
        loaded = deepcopy(world)
        loaded.finish(name)
        loaded.finish(name)
        loaded.run("RUS_bunker_energy_sale_cancel")
        self.assertEqual(loaded.balances(), paid)
        self.assertEqual(loaded.value("RUS_bunker_free_power"), capacity)
        self.assertNotIn("RUS_bunker_energy_export_power", loaded.variables)

    def test_energy_reservation_limits_construction_and_cannot_interrupt_a_paid_order(self):
        world = self.world()
        world.variables["RUS_bunker_depth"] = 5
        world.run("RUS_bunker_refresh")
        world.begin("RUS_bunker_guard")
        before = world.balances()
        world.run("RUS_bunker_energy_sale_start")
        self.assertEqual(world.balances(), before)
        world.finish("RUS_bunker_guard")
        self.assertEqual(world.value("RUS_bunker_free_power"), 2)
        world.begin("RUS_bunker_energy_sale")
        self.assertEqual(world.value("RUS_bunker_free_power"), 1)
        self.assertFalse(world.matches(self.triggers["RUS_bunker_signals_requirements"]))
        world.finish("RUS_bunker_energy_sale")
        self.assertTrue(world.matches(self.triggers["RUS_bunker_signals_requirements"]))

    def test_energy_contract_failure_returns_advance_once_and_shutdown_releases_power(self):
        name = "RUS_bunker_energy_sale"
        for field, value in (("owner", False), ("controller", False), ("ruler", None), ("subject", True), ("capitulated", True)):
            for callback in ("RUS_bunker_energy_sale_cancel", "RUS_bunker_energy_sale_finish", "RUS_campaign_shutdown"):
                with self.subTest(field=field, callback=callback):
                    world = self.world()
                    before = world.balances()
                    world.begin(name)
                    setattr(world, field, value)
                    self.assertTrue(world.matches(block(self.decisions[name], "cancel_trigger")))
                    world.run(callback)
                    world.run(callback)
                    world.finish(name)
                    self.assertEqual(world.balances(), before)
                    self.assertNotIn("RUS_bunker_energy_export_power", world.variables)
                    self.assertEqual(world.value("RUS_bunker_used_power"), 0)

    def test_generation_and_political_development_focuses(self):
        self.assertEqual(len(self.focuses), 148)
        path = ROOT / "common/national_focus/ADISCORD_national_focus_RUS.txt"
        self.assertEqual(path.read_bytes(), expected_outputs()[path])

    def opening_focus_ready(self, world, name):
        rows = self.focuses[name]
        prerequisites = [row.value for row in rows if row.key == "prerequisite"]
        exclusive = [row.value for group in rows if group.key == "mutually_exclusive"
                     for row in group.value if row.key == "focus"]
        return (
            name not in world.focuses
            and not set(exclusive) & world.focuses
            and all(any(row.value in world.focuses for row in group if row.key == "focus")
                    for group in prerequisites)
            and world.matches(block(rows, "available"))
        )

    def test_opening_four_routes_preserve_paid_construction_and_defer_full_policy(self):
        for purpose, room, opposite, policy, variable in (
            ("RUS_bunker_open_city", "shelter", "RUS_bunker_sealed_throne",
             "RUS_open_city_policy", "RUS_bunker_food_output_bonus"),
            ("RUS_bunker_sealed_throne", "guard", "RUS_bunker_open_city",
             "RUS_sealed_throne_policy", "RUS_bunker_power_bonus"),
        ):
            for course in ("RUS_scientists_council", "RUS_black_army_oath"):
                with self.subTest(purpose=purpose, course=course):
                    world = BunkerWorld(self, fresh=True)
                    world.begin("RUS_bunker_excavate")
                    receipt = {key: value for key, value in world.variables.items()
                               if key.startswith("RUS_bunker_escrow_")
                               or key in ("RUS_bunker_project", "RUS_bunker_project_depth")}
                    elapsed = 0
                    route = ("RUS_summon_the_aimaqs", "RUS_bunker_survey", purpose,
                             "RUS_count_the_hearths", course)
                    for name in route:
                        self.assertTrue(self.opening_focus_ready(world, name), name)
                        world.execute(block(self.focuses[name], "completion_reward"))
                        world.focuses.add(name)
                        elapsed += int(scalar(self.focuses[name], "cost")) * 7
                        self.assertNotIn(policy, world.ideas)
                        for key, value in receipt.items():
                            self.assertEqual(world.variables[key], value, (name, key))
                    self.assertEqual(elapsed, 84)
                    self.assertEqual(world.value(variable), 1)
                    self.assertFalse(self.opening_focus_ready(world, opposite))
                    self.assertTrue(self.opening_focus_ready(world, "RUS_bunker_airlocks"))
                    self.assertFalse(self.opening_focus_ready(world, "RUS_bunker_commission"))
                    for name in ("RUS_bunker_closed_cycle", "RUS_bunker_reserve_turbine",
                                 "RUS_bunker_surface_market", "RUS_bunker_deep_casemates"):
                        self.assertFalse(self.opening_focus_ready(world, name), name)
                    # Callbacks model payment and completion, not the engine's calendar.
                    world.finish("RUS_bunker_excavate")
                    world.begin("RUS_bunker_" + room)
                    world.finish("RUS_bunker_" + room)
                    self.assertEqual(world.value("RUS_bunker_fitted"), 1)
                    self.assertGreaterEqual(world.value("RUS_bunker_free_power"), 0)
                    self.assertEqual(world.ruler, "RUS_Mark_Rustan")
                    self.assertNotIn("RUS_crisis_phase", world.variables)

    def test_commission_installs_selected_policy_and_trial_failure_keeps_programmes_open(self):
        for purpose, policy, opposite_policy, continuation in (
            ("RUS_bunker_open_city", "RUS_open_city_policy", "RUS_sealed_throne_policy",
             "RUS_bunker_closed_cycle"),
            ("RUS_bunker_sealed_throne", "RUS_sealed_throne_policy", "RUS_open_city_policy",
             "RUS_bunker_reserve_turbine"),
        ):
            for hungry in (False, True):
                with self.subTest(purpose=purpose, hungry=hungry):
                    world = self.world()
                    world.stability = 0.5
                    world.focuses = {purpose, "RUS_bunker_science_wing", "RUS_bunker_memory_vault"}
                    world.variables.update({"RUS_bunker_depth": 5, "RUS_bunker_generators": 3,
                                            "RUS_bunker_integrity": 80, "RUS_bunker_food": 60})
                    for layer in range(1, 6):
                        world.variables[f"RUS_bunker_layer_{layer}"] = 1
                    world.run("RUS_bunker_refresh")
                    self.assertTrue(self.opening_focus_ready(world, "RUS_bunker_commission"))
                    world.execute(block(self.focuses["RUS_bunker_commission"], "completion_reward"))
                    world.focuses.add("RUS_bunker_commission")
                    self.assertIn(policy, world.ideas)
                    self.assertNotIn(opposite_policy, world.ideas)
                    self.assertIn("RUS_bunker_silence_trial_active", world.flags)
                    if hungry:
                        world.variables["RUS_bunker_food"] = 0
                        world.run("RUS_bunker_refresh")
                        world.variables["RUS_bunker_food"] = 40
                        world.run("RUS_bunker_refresh")
                    before = world.stability, world.pp
                    world.run("RUS_bunker_silence_trial_settle")
                    self.assertAlmostEqual(world.stability - before[0], -0.05 if hungry else 0.05)
                    self.assertEqual(world.pp - before[1], 0 if hungry else 50)
                    self.assertTrue(self.opening_focus_ready(world, continuation))
                    saved = deepcopy(world.variables), world.stability, world.pp
                    world.run("RUS_bunker_silence_trial_settle")
                    world.run("RUS_campaign_initialize")
                    self.assertEqual((world.variables, world.stability, world.pp), saved)

    def test_ordinary_civil_institutions_are_priorities_not_permanent_exclusions(self):
        world = self.world()
        world.focuses = {"RUS_pay_the_officials"}
        for name in ("RUS_winter_granaries", "RUS_district_courts"):
            self.assertTrue(self.opening_focus_ready(world, name))
            world.execute(block(self.focuses[name], "completion_reward"))
            world.focuses.add(name)
        self.assertTrue(self.opening_focus_ready(world, "RUS_school_of_scribes"))

    def test_merged_artillery_programme_funds_first_order_without_passive_income(self):
        for course in ("RUS_scientists_council", "RUS_black_army_oath"):
            for doctrine in ("RUS_patient_war", "RUS_swift_columns"):
                with self.subTest(course=course, doctrine=doctrine):
                    world = BunkerWorld(self, fresh=True)
                    world.begin("RUS_bunker_excavate")
                    route = ("RUS_summon_the_aimaqs", "RUS_count_the_hearths", course,
                             "RUS_muster_books", "RUS_quartermaster_service", doctrine,
                             "RUS_officer_courses", "RUS_artillery_tables")
                    for name in route:
                        self.assertTrue(self.opening_focus_ready(world, name), name)
                        world.execute(block(self.focuses[name], "completion_reward"))
                        world.focuses.add(name)
                    self.assertEqual(sum(int(scalar(self.focuses[name], "cost")) * 7 for name in route), 161)
                    world.finish("RUS_bunker_excavate")
                    world.decisions.update(self.programmes)
                    order = world.decisions["RUS_artillery_order"]
                    self.assertTrue(world.matches(block(order, "visible")))
                    self.assertTrue(world.matches(block(order, "available")))
                    self.assertTrue(world.matches(block(order, "custom_cost_trigger")))
                    self.assertEqual(world.equipment["artillery_equipment_1"], 80)
                    before = world.balances()
                    world.begin("RUS_artillery_order")
                    self.assertEqual(tuple(a - b for a, b in zip(before, world.balances())), (25, 65, 50))
                    self.assertEqual(world.equipment["artillery_equipment_1"], 80)
                    self.assertEqual(scalar(order, "days_remove"), "30")
                    world.finish("RUS_artillery_order")
                    self.assertEqual(world.equipment["artillery_equipment_1"], 200)
                    world.execute(block(order, "remove_effect"))
                    self.assertEqual(world.equipment["artillery_equipment_1"], 200)

    def test_merged_medical_and_artillery_route_has_bounded_total_focus_time(self):
        for doctrine in ("RUS_patient_war", "RUS_swift_columns"):
            done = set()

            def include(name):
                if name in done:
                    return
                for row in self.focuses[name]:
                    if row.key == "prerequisite":
                        choices = [child.value for child in row.value if child.key == "focus"]
                        include(doctrine if doctrine in choices else choices[0])
                done.add(name)

            include("RUS_staff_field_exercise")
            self.assertTrue({"RUS_field_hospitals", "RUS_artillery_tables", doctrine} <= done)
            self.assertEqual(sum(int(scalar(self.focuses[name], "cost")) * 7 for name in done), 280)
            self.assertFalse({"RUS_battery_training", "RUS_artillery_observers", "RUS_wounded_return_service", "RUS_field_evacuation_service"} & self.focuses.keys())

    def test_engineering_and_transport_focuses_fund_work_and_keep_reforms(self):
        world = self.world()
        equipment = world.equipment["support_equipment"]
        school = block(self.focuses["RUS_bunker_layer_service_school"], "completion_reward")
        world.execute(school)
        self.assertEqual(world.equipment["support_equipment"] - equipment, 300)
        bonus = block(school, "add_tech_bonus")
        self.assertEqual((scalar(bonus, "category"), scalar(bonus, "uses"), scalar(bonus, "bonus")), ("support_tech", "2", "0.5"))
        equipment = world.equipment["support_equipment"]
        cash = world.value("ADISCORD_economy_treasury")
        income = world.value("ADISCORD_economy_current_month_action_income")
        dirty = world.dirty
        world.execute(block(self.focuses["RUS_bunker_machine_depot"], "completion_reward"))
        self.assertEqual(world.equipment["support_equipment"], equipment)
        self.assertEqual(world.value("ADISCORD_economy_treasury"), cash)
        self.assertEqual(world.value("RUS_machine_reserve"), 1)
        world.run("RUS_machine_reserve_release")
        self.assertEqual(world.equipment["support_equipment"] - equipment, 400)
        self.assertEqual(world.value("ADISCORD_economy_treasury") - cash, 600)
        self.assertEqual(world.value("ADISCORD_economy_current_month_action_income") - income, 600)
        self.assertGreater(world.dirty, dirty)
        trucks = world.equipment.get("motorized_equipment", 0)
        supply = world.value("RUS_army_supply")
        world.execute(block(self.focuses["RUS_motor_pool_dispatch"], "completion_reward"))
        self.assertEqual(world.equipment["motorized_equipment"] - trucks, 300)
        self.assertAlmostEqual(world.value("RUS_army_supply") - supply, -0.05)
        world.controller = False
        world.run("RUS_bunker_refresh")
        world.run("RUS_campaign_initialize")
        self.assertAlmostEqual(world.value("RUS_army_supply") - supply, -0.05)
        preview = block(self.ideas["RUS_motor_pool_dispatch_delta"], "modifier")
        self.assertEqual(scalar(preview, "supply_consumption_factor"), "-0.05")
        self.assertNotIn("RUS_motor_pool_dispatch_delta", world.ideas)

    def test_food_trade_prices_and_fractional_affordability_prevent_resale_profit(self):
        for freight in (False, True):
            with self.subTest(freight=freight):
                world = self.world()
                if not freight:
                    world.focuses.discard("RUS_strategic_freight_reserve")
                world.variables["RUS_bunker_food"] = 0
                world.variables["ADISCORD_economy_treasury"] = 164.99
                world.run("RUS_bunker_refresh")
                before = world.balances()
                world.run("RUS_bunker_resupply")
                self.assertEqual(world.balances(), before)
                self.assertEqual(world.value("RUS_bunker_food"), 0)
                world.variables["ADISCORD_economy_treasury"] = 495
                total_bought = 0
                for _ in range(3):
                    world.variables["RUS_bunker_food"] = 0
                    world.run("RUS_bunker_refresh")
                    world.run("RUS_bunker_resupply")
                    total_bought += world.value("RUS_bunker_food")
                self.assertEqual(world.value("ADISCORD_economy_treasury"), 0)
                for _ in range(int(total_bought // 40)):
                    world.variables["RUS_bunker_food"] = 40
                    world.run("RUS_bunker_refresh")
                    world.run("RUS_bunker_food_sale")
                proceeds = int(total_bought // 40) * 100
                self.assertEqual(world.value("ADISCORD_economy_treasury"), proceeds)
                self.assertLess(proceeds, 495)

    def test_food_price_labels_match_debit_in_both_languages_and_keep_repair_price(self):
        definitions = {
            scalar(entry.value, "name"): entry.value
            for entry in parse("common/scripted_localisation/ADISCORD_RUS_scripted_loc.txt")
            if entry.key == "defined_text"
        }
        for language in ("russian", "english"):
            loc = dict(re.findall(
                r'^\s+([A-Za-z0-9_.]+):(?:\d+)?\s+"(.*)"\s*$',
                read(f"localisation/{language}/{BASE}_l_{language}.yml"), re.M,
            ))
            for key in ("RUS_bunker_resupply_label", "RUS_bunker_food_cost", "RUS_bunker_food_cost_blocked", "RUS_bunker_food_cost_tooltip", "RUS_bunker_food_ui_tt"):
                self.assertIn("[GetRUSBunkerFoodCash]", loc[key], (language, key))
                self.assertNotIn("[GetRUSBunker31cash]", loc[key], (language, key))
            self.assertIn("[GetRUSBunkerConvoyAmount]", loc["RUS_bunker_resupply_label"])
            self.assertIn("40", loc["RUS_bunker_convoy_small"])
            self.assertIn("60", loc["RUS_bunker_convoy_large"])
            for name, amount in (("GetRUSBunkerFoodCash", 165), ("GetRUSBunker31cash", 35)):
                choices = [entry.value for entry in definitions[name] if entry.key == "text"]
                world = self.world()
                for treasury, expected in ((amount - 0.01, 1), (amount, 0)):
                    world.variables["ADISCORD_economy_treasury"] = treasury
                    choice = next(
                        rows for rows in choices
                        if world.matches(next((entry.value for entry in rows if entry.key == "trigger"), []))
                    )
                    self.assertEqual(choice, choices[expected], (language, name, treasury))
                    self.assertIn(str(amount), loc[scalar(choice, "localization_key")])

    def test_pre_crisis_muster_reaches_ten_ready_brigades_before_proclamation(self):
        world = self.world()
        self.assertIn(("49", "RUS"), world.cores)
        self.assertIn(("205", "RUS"), world.cores)
        world.execute(block(self.focuses["RUS_arm_the_border_hosts"], "completion_reward"))
        world.execute(block(self.focuses["RUS_aimaq_reserve"], "completion_reward"))
        self.assertEqual(world.divisions, 10)
        self.assertGreaterEqual(world.equipment["infantry_equipment"], 10000)
        border = self.effects["ADISCORD_vorkerland_start_khan_border_war"]
        def reward_stockpile(focus, equipment):
            return sum(
                float(scalar(entry.value, "amount"))
                for entry in walk(block(self.focuses[focus], "completion_reward"))
                if entry.key == "add_equipment_to_stockpile"
                and scalar(entry.value, "type") == equipment
            )
        def effect_stockpile(equipment):
            return sum(
                float(scalar(entry.value, "amount"))
                for entry in walk(border)
                if entry.key == "add_equipment_to_stockpile"
                and scalar(entry.value, "type") == equipment
            )
        full_brigade = 6 * 900 + 4 * 270
        phase1_rifles = 12000 + effect_stockpile("infantry_equipment_0") + reward_stockpile("RUS_arm_the_border_hosts", "infantry_equipment_0") + reward_stockpile("RUS_aimaq_reserve", "infantry_equipment_0")
        phase1_squad = effect_stockpile("ADISCORD_squad_weapons_equipment_0") + reward_stockpile("RUS_arm_the_border_hosts", "ADISCORD_squad_weapons_equipment_0") + reward_stockpile("RUS_aimaq_reserve", "ADISCORD_squad_weapons_equipment_0")
        phase1_aa = 80 + effect_stockpile("ADISCORD_anti_air_equipment_2163") + reward_stockpile("RUS_aimaq_reserve", "ADISCORD_anti_air_equipment_2163")
        phase1_support = 20 + effect_stockpile("support_equipment_1") + reward_stockpile("RUS_arm_the_border_hosts", "support_equipment")
        phase1_artillery = 50 + effect_stockpile("artillery_equipment_1") + reward_stockpile("RUS_arm_the_border_hosts", "artillery_equipment_1") + reward_stockpile("RUS_aimaq_reserve", "artillery_equipment_1")
        phase1_anti_tank = 100 + effect_stockpile("ADISCORD_anti_tank_equipment_2163") + reward_stockpile("RUS_arm_the_border_hosts", "ADISCORD_anti_tank_equipment_2163") + reward_stockpile("RUS_aimaq_reserve", "ADISCORD_anti_tank_equipment_2163")
        self.assertGreaterEqual(phase1_rifles, 2 * full_brigade * 0.32 + 8 * full_brigade * 0.75)
        self.assertGreaterEqual(phase1_squad, 2 * 48 * 0.32 + 8 * 48 * 0.75)
        self.assertGreaterEqual(phase1_aa, 2 * 20 * 0.32 + 8 * 20 * 0.75)
        self.assertGreaterEqual(phase1_support, 2 * 30 * 0.32 + 8 * 30 * 0.75)
        self.assertGreaterEqual(phase1_artillery, 2 * 12 * 0.32 + 8 * 12 * 0.75)
        self.assertGreaterEqual(phase1_anti_tank, 2 * 24 * 0.32 + 8 * 24 * 0.75)
        self.assertGreaterEqual(1532123 + 30000 + 20000, world.divisions * (6 * 1000 + 4 * 300))
        history_units = read("history/units/RUS.txt")
        self.assertRegex(history_units, r"type = infantry_equipment_0\s+amount = 12000")
        self.assertIn("anti_air = { x = 0 y = 1 }", history_units)
        self.assertIn("artillery = { x = 1 y = 0 }", history_units)
        self.assertIn("anti_tank = { x = 1 y = 1 }", history_units)
        self.assertRegex(read("history/states/66-Khan-Bunker.txt"), r"arms_factory\s*=\s*5")
        decision = next(entry.value for entry in walk(parse(f"common/decisions/{BASE}_decisions.txt")) if entry.key == "RUS_proclaim_the_last_empire")
        prepared = {(entry.key, entry.value) for entry in walk(block(decision, "available")) if entry.key == "has_completed_focus"}
        self.assertIn(("has_completed_focus", "RUS_aimaq_reserve"), prepared)
        self.assertIn(("has_completed_focus", "RUS_arm_the_border_hosts"), prepared)

    def test_full_crisis_muster_budget_covers_support_and_air_defence(self):
        history_units = read("history/units/RUS.txt")
        instant = history_units.split("add_equipment_production", 1)[0]

        def history_amount(equipment):
            match = re.search(rf"type = {re.escape(equipment)}\s+amount = (\d+)", instant)
            return float(match.group(1)) if match else 0

        border = self.effects["ADISCORD_vorkerland_start_khan_border_war"]

        def stockpile(rows, equipment):
            return sum(
                float(scalar(entry.value, "amount"))
                for entry in walk(rows)
                if entry.key == "add_equipment_to_stockpile"
                and scalar(entry.value, "type") == equipment
            )

        focus_names = (
            "RUS_arm_the_border_hosts",
            "RUS_aimaq_reserve",
            "RUS_reserve_rotations",
            "RUS_break_the_hegemon",
        )
        new_brigades = 0
        focus_stock = {}
        for name in focus_names:
            reward = block(self.focuses[name], "completion_reward")
            new_brigades += int(scalar(next(entry.value for entry in walk(reward) if entry.key == "create_unit"), "count"))
            for equipment in (
                "infantry_equipment_0",
                "ADISCORD_squad_weapons_equipment_0",
                "ADISCORD_anti_air_equipment_2163",
                "artillery_equipment_1",
                "ADISCORD_anti_tank_equipment_2163",
                "support_equipment",
            ):
                focus_stock[equipment] = focus_stock.get(equipment, 0) + stockpile(reward, equipment)

        declared = {
            "infantry_equipment_0": history_amount("infantry_equipment_0") + stockpile(border, "infantry_equipment_0") + focus_stock.get("infantry_equipment_0", 0),
            "ADISCORD_squad_weapons_equipment_0": stockpile(border, "ADISCORD_squad_weapons_equipment_0") + focus_stock.get("ADISCORD_squad_weapons_equipment_0", 0),
            "ADISCORD_anti_air_equipment_2163": history_amount("ADISCORD_anti_air_equipment_2163") + stockpile(border, "ADISCORD_anti_air_equipment_2163") + focus_stock.get("ADISCORD_anti_air_equipment_2163", 0),
            "artillery_equipment_1": history_amount("artillery_equipment_1") + stockpile(border, "artillery_equipment_1") + focus_stock.get("artillery_equipment_1", 0),
            "ADISCORD_anti_tank_equipment_2163": history_amount("ADISCORD_anti_tank_equipment_2163") + stockpile(border, "ADISCORD_anti_tank_equipment_2163") + focus_stock.get("ADISCORD_anti_tank_equipment_2163", 0),
            "support_equipment": 20 + stockpile(border, "support_equipment_1") + focus_stock.get("support_equipment", 0),
        }
        per_brigade = {
            "infantry_equipment_0": 6480,
            "ADISCORD_squad_weapons_equipment_0": 48,
            "ADISCORD_anti_air_equipment_2163": 20,
            "artillery_equipment_1": 12,
            "ADISCORD_anti_tank_equipment_2163": 24,
            "support_equipment": 30,
        }
        for equipment, need in per_brigade.items():
            required = 2 * 0.32 * need + new_brigades * 0.75 * need
            self.assertGreaterEqual(declared[equipment], required, equipment)
        self.assertEqual(new_brigades, 19)
        self.assertIn("air_wings = {", history_units)
        self.assertIn('ADISCORD_fighter_airframe_2163 = { owner = "RUS" amount = 120 }', history_units)
        self.assertRegex(history_units, r"type = ADISCORD_fighter_airframe_2163 creator = \"RUS\"")
        self.assertRegex(read("history/states/66-Khan-Bunker.txt"), r"air_base\s*=\s*2")
        weekly_supply = self.effects["RUS_bunker_weekly_supply"]
        self.assertTrue(
            any(entry.key == "has_completed_focus" and entry.value == "RUS_anti_air_posts" for entry in walk(weekly_supply))
        )
        self.assertTrue(
            any(
                entry.key == "add_equipment_to_stockpile"
                and scalar(entry.value, "type") == "ADISCORD_anti_air_equipment_2163"
                and scalar(entry.value, "amount") == "2"
                for entry in walk(weekly_supply)
            )
        )

    def test_propaganda_is_distributed_across_political_military_and_economic_focuses(self):
        world = self.world()
        self.assertEqual(len(self.campaigns), 6)
        for index, focus in enumerate(("RUS_khan_broadcast_service", "RUS_parallel_public_addresses"), 1):
            reward = block(self.focuses[focus], "completion_reward")
            grants = [entry for entry in walk(reward) if entry.key == "ADISCORD_campaign_slot_grant"]
            self.assertEqual(len(grants), 1)
            before = world.pp
            world.execute(reward)
            self.assertEqual(world.value("ADISCORD_available_campaign_slots"), index)
            expected_delta = 35 if focus == "RUS_khan_broadcast_service" else 0
            self.assertEqual(world.pp, before + expected_delta)
        unlock_sources = {
            "RUS_campaign_voice_of_the_aimaqs": "RUS_khan_broadcast_service",
            "RUS_campaign_bread_and_shelter": "RUS_khan_broadcast_service",
            "RUS_campaign_rifles_protect_home": "RUS_muster_books",
            "RUS_campaign_the_khan_keeps_his_word": "RUS_written_oaths",
            "RUS_campaign_surface_trade": "RUS_surface_workshops",
            "RUS_campaign_last_order": "RUS_imperial_general_staff",
        }
        self.assertEqual(set(unlock_sources), set(self.campaigns))
        for campaign, focus in unlock_sources.items():
            reward = block(self.focuses[focus], "completion_reward")
            self.assertIn(campaign, {entry.value for entry in walk(reward) if entry.key == "unlock_decision_tooltip"})
            self.assertTrue(any(entry.key == "has_completed_focus" and entry.value == focus for entry in walk(block(self.campaigns[campaign], "visible"))))
        for focus, expected_pp in {
            "RUS_khan_broadcast_service": 35,
            "RUS_muster_books": 30,
            "RUS_written_oaths": 40,
            "RUS_surface_workshops": 35,
            "RUS_imperial_general_staff": 35,
        }.items():
            reward = block(self.focuses[focus], "completion_reward")
            self.assertIn(
                expected_pp,
                {
                    int(entry.value)
                    for entry in walk(reward)
                    if entry.key == "add_political_power"
                },
            )

    def test_every_public_campaign_unlock_reveals_its_category(self):
        category = block(parse(f"common/decisions/categories/ADISCORD_decision_categories_RUS.txt"), "RUS_public_campaigns")
        for campaign, rows in self.campaigns.items():
            world = self.world()
            world.focuses = {
                entry.value for entry in walk(block(rows, "visible"))
                if entry.key == "has_completed_focus"
            }
            self.assertTrue(world.matches(block(category, "visible")), campaign)
            self.assertTrue(world.matches(block(rows, "visible")), campaign)
            self.assertFalse(world.matches(block(rows, "available")), "Unlocking a campaign does not grant a free slot")

    def test_reactor_callbacks_are_bound_to_their_paid_target(self):
        from tools.tests.test_adiscord_rus_last_empire import RusCrisisFixture

        decision = self.belt["RUS_restore_reactor_works"]
        for callback, effect, marker in (
            ("remove_effect", "RUS_reactor_works_finish_state", "set_state_flag = callback_delivered"),
            ("cancel_effect", "RUS_reactor_works_refund", "set_country_flag = callback_refunded"),
        ):
            with self.subTest(callback=callback):
                world = RusCrisisFixture()
                world.variables["RUS", "RUS_reactor_works_deposit"] = 400
                world.state_flags["177"] = {"RUS_reactor_works_in_progress"}
                # Observe dispatch independently of the already tested reward payload.
                world.effects[effect] = parse_clausewitz(marker)
                world.from_country = "176"
                world.execute(block(decision, callback), ["RUS"])
                self.assertFalse(any("callback_delivered" in flags for flags in world.state_flags.values()))
                self.assertNotIn("callback_refunded", world.flags["RUS"])
                self.assertEqual(world.variables["RUS", "RUS_reactor_works_deposit"], 400)
                world.from_country = "177"
                world.execute(block(decision, callback), ["RUS"])
                if callback == "remove_effect":
                    self.assertIn("callback_delivered", world.state_flags["177"])
                else:
                    self.assertIn("callback_refunded", world.flags["RUS"])

    def test_propaganda_consumes_and_releases_only_its_own_slots(self):
        for name, rows in self.campaigns.items():
            world = self.world()
            world.decisions = self.campaigns
            world.variables["ADISCORD_available_campaign_slots"] = 1
            before = world.pp
            world.begin(name)
            self.assertEqual(world.pp, before - float(scalar(rows, "cost")))
            self.assertEqual(world.value("ADISCORD_available_campaign_slots"), 0)
            self.assertTrue(world.flags.intersection({name + "_slot_held"}))
            world.run(name + "_start")
            self.assertEqual(world.value("ADISCORD_available_campaign_slots"), 0)
            for other in self.campaigns:
                self.assertFalse(world.matches(block(self.campaigns[other], "available")), (name, other))
            paid = world.pp
            world.finish(name)
            world.execute(block(rows, "cancel_effect"))
            world.run("RUS_public_campaigns_shutdown")
            self.assertEqual(world.value("ADISCORD_available_campaign_slots"), 1)
            self.assertEqual(world.pp, paid)
            self.assertFalse(world.active)
            self.assertNotIn(name + "_slot_held", world.flags)
        world = self.world()
        world.decisions = self.campaigns
        world.variables["ADISCORD_available_campaign_slots"] = 3
        for name in list(self.campaigns)[:2]:
            world.begin(name)
        self.assertEqual(world.value("ADISCORD_available_campaign_slots"), 1)
        loaded = deepcopy(world)
        loaded.run("RUS_campaign_initialize")
        loaded.run("RUS_campaign_shutdown")
        loaded.run("RUS_campaign_shutdown")
        self.assertEqual(loaded.value("ADISCORD_available_campaign_slots"), 3)
        self.assertFalse(loaded.active)

    def test_propaganda_cancellation_and_economic_cache(self):
        for name, rows in self.campaigns.items():
            for loss in ("ruler", "subject", "capitulated", "crisis"):
                world = self.world()
                world.decisions = self.campaigns
                world.variables["ADISCORD_available_campaign_slots"] = 1
                world.begin(name)
                paid = world.pp
                if loss == "ruler":
                    world.ruler = "another_ruler"
                elif loss == "crisis":
                    world.variables["RUS_crisis_phase"] = 4
                else:
                    setattr(world, loss, True)
                self.assertTrue(world.matches(block(rows, "cancel_trigger")), (name, loss))
                world.active.discard(name)
                world.execute(block(rows, "cancel_effect"))
                self.assertEqual(world.value("ADISCORD_available_campaign_slots"), 1)
                self.assertEqual(world.pp, paid)
            self.assertFalse(any(e.key in ("add_political_power", "declare_war_on", "set_rule") for e in walk(rows)))
            if name.endswith(("bread_and_shelter", "rifles_protect_home", "surface_trade")):
                for suffix in ("start", "settle"):
                    self.assertTrue(any(e.key == "ADISCORD_economy_mark_dirty" for e in walk(self.effects[name + "_" + suffix])))
        world = self.world()
        world.war = False
        world.variables["ADISCORD_available_campaign_slots"] = 1
        rows = self.campaigns["RUS_campaign_last_order"]
        self.assertFalse(world.matches(block(rows, "available")))
        self.assertTrue(world.matches(block(rows, "cancel_trigger")))

    def test_development_programmes_settle_exact_payment_and_persistent_progress(self):
        specs = {
            "RUS_civil_service_training": "state",
            "RUS_district_health_programme": "social_system",
            "RUS_workshop_training": "economic",
            "RUS_community_assemblies": "society",
            "RUS_public_reading_rooms": "cultural",
            "RUS_regimental_training": "army",
        }
        for name, direction in specs.items():
            rows = self.programmes[name]
            for pp, cash, permitted in ((25, 35, True), (24.999, 35, False), (25, 34.999, False)):
                world = self.world()
                world.focuses.difference_update({"RUS_aimaq_service_charter", "RUS_civil_service_examinations"})
                world.owner = world.controller = False
                world.pp = pp
                world.variables["ADISCORD_economy_treasury"] = cash
                progress = f"ADISCORD_{direction}_development_progress"
                world.variables[progress] = 10
                spent = world.value("ADISCORD_economy_current_month_action_costs")
                self.assertEqual(world.matches(block(rows, "custom_cost_trigger")), permitted)
                world.execute(block(rows, "complete_effect"))
                self.assertEqual(world.pp, pp - (25 if permitted else 0))
                self.assertEqual(world.value("ADISCORD_economy_treasury"), cash - (35 if permitted else 0))
                self.assertEqual(world.value(progress), 35 if permitted else 10)
                self.assertEqual(world.value("ADISCORD_economy_current_month_action_costs") - spent, 35 if permitted else 0)
            for variable, value in ((f"ADISCORD_{direction}_development_level", 5), (progress, 100)):
                world = self.world()
                world.variables[variable] = value
                before = world.balances(), deepcopy(world.variables)
                world.execute(block(rows, "complete_effect"))
                self.assertEqual((world.balances(), world.variables), before)
            self.assertEqual(scalar(rows, "cost"), "0")
            self.assertEqual(scalar(rows, "days_re_enable"), "90")
            for suffix in ("", "_blocked", "_tooltip"):
                self.assertIn("RUS_development_programme_cost" + suffix, self.loc)

    def test_both_political_routes_unlock_the_same_civil_service_programme(self):
        for focus in ("RUS_aimaq_service_charter", "RUS_civil_service_examinations"):
            world = self.world()
            world.focuses = {focus}
            rows = self.programmes["RUS_civil_service_training"]
            self.assertTrue(world.matches(block(rows, "visible")))
            self.assertTrue(world.matches(block(rows, "available")))
            reward = block(self.focuses[focus], "completion_reward")
            self.assertIn("RUS_civil_service_training", [e.value for e in reward if e.key == "unlock_decision_tooltip"])
            world.execute(reward)
            self.assertEqual(world.value("ADISCORD_state_development_monthly_growth"), 2)
            self.assertEqual(world.value("ADISCORD_state_development_progress"), 25)

    def test_programmes_charge_exact_prices_and_deliver_material_results(self):
        prices = {
            "defensive_preparation": (25, 85, 35),
            "mobile_preparation": (30, 65, 30),
            "aimaq_public_works": (15, 100, 35),
            "chancery_reconstruction": (25, 135, 45),
            "surface_industrial_contract": (25, 135, 45),
            "subterranean_supply_contract": (25, 115, 40),
        }
        for suffix, price in prices.items():
            name = "RUS_" + suffix
            world = self.world()
            rows = self.programmes[name]
            world.decisions = self.programmes
            world.pp, world.variables["ADISCORD_economy_treasury"], world.equipment["support_equipment"] = price
            self.assertTrue(world.matches(block(rows, "custom_cost_trigger")), name)
            for currency in range(3):
                test = deepcopy(world)
                if currency == 0:
                    test.pp -= 0.01
                elif currency == 1:
                    test.variables["ADISCORD_economy_treasury"] -= 0.01
                else:
                    test.equipment["support_equipment"] -= 0.01
                self.assertFalse(test.matches(block(rows, "custom_cost_trigger")), (name, currency))
                before = test.balances(), deepcopy(test.variables), deepcopy(test.buildings), set(test.ideas)
                test.execute(block(rows, "complete_effect"))
                self.assertEqual((test.balances(), test.variables, test.buildings, test.ideas), before)
            dirty = world.dirty
            spent = world.value("ADISCORD_economy_current_month_action_costs")
            world.begin(name)
            self.assertEqual(world.balances(), (0, 0, 0), name)
            self.assertEqual(world.value("ADISCORD_economy_current_month_action_costs") - spent, price[1])
            self.assertGreater(world.dirty, dirty, name)
            if suffix == "aimaq_public_works":
                self.assertEqual(world.buildings["infrastructure"], 3)
            elif suffix == "chancery_reconstruction":
                self.assertEqual(world.buildings["arms_factory"], 6)
            elif suffix == "surface_industrial_contract":
                self.assertEqual(world.buildings["industrial_complex"], 1)
            elif suffix == "subterranean_supply_contract":
                self.assertEqual(world.value("RUS_bunker_food_output"), 3)
                self.assertEqual(world.value("RUS_bunker_food_capacity"), 120)
            else:
                self.assertIn(name + "_spirit", world.ideas)

    def test_council_budget_discount_quotes_and_charges_only_public_works(self):
        rows = self.programmes["RUS_aimaq_public_works"]
        for funded, price in ((False, 25), (True, 15)):
            for currency in (None, "pp", "cash", "equipment"):
                with self.subTest(funded=funded, currency=currency):
                    world = self.world()
                    world.focuses.discard("RUS_assembly_budget")
                    if funded:
                        cash = world.value("ADISCORD_economy_treasury")
                        income = world.value("ADISCORD_economy_current_month_action_income")
                        world.execute(block(self.focuses["RUS_assembly_budget"], "completion_reward"))
                        self.assertEqual(world.value("ADISCORD_economy_treasury") - cash, 300)
                        self.assertEqual(world.value("ADISCORD_economy_current_month_action_income") - income, 300)
                        world.focuses.add("RUS_assembly_budget")
                    world.pp = price - (0.001 if currency == "pp" else 0)
                    world.variables["ADISCORD_economy_treasury"] = 100 - (0.001 if currency == "cash" else 0)
                    world.equipment["support_equipment"] = 35 - (0.001 if currency == "equipment" else 0)
                    permitted = currency is None
                    self.assertEqual(world.matches(block(rows, "custom_cost_trigger")), permitted)
                    key = self.bunker_text(world, "GetRUSAimaqPublicWorksPP")
                    self.assertIn(str(price), self.loc[key])
                    self.assertIn("§R" if currency == "pp" else "§Y", self.loc[key])
                    before = world.balances()
                    world.execute(block(rows, "complete_effect"))
                    self.assertEqual(tuple(a - b for a, b in zip(before, world.balances())),
                                     (price, 100, 35) if permitted else (0, 0, 0))
                    self.assertEqual(world.buildings["infrastructure"], 3 if permitted else 2)
                    self.assertEqual(world.value("ADISCORD_economy_current_month_action_costs"), 100 if permitted else 0)
                    world.pp = 15
                    self.assertFalse(world.matches(self.triggers["RUS_bunker_workshop_affordable"]))
        self.assertEqual(scalar(rows, "cost"), "0")
        cost_key = scalar(rows, "custom_cost_text")
        for suffix in ("", "_blocked", "_tooltip"):
            self.assertIn("[GetRUSAimaqPublicWorksPP]", self.loc[cost_key + suffix])

    def test_civil_service_courses_add_only_the_selected_development_bonus(self):
        rows = self.programmes["RUS_civil_service_training"]
        for focus, state_gain, society_gain in (
            ("RUS_trained_administrators", 25, 0),
            ("RUS_aimaq_service_charter", 25, 15),
            ("RUS_civil_service_examinations", 40, 0),
        ):
            for bonus, archive, extra in ((0, False, 0), (10, False, 10), (10, True, 25)):
                with self.subTest(focus=focus, bonus=bonus, archive=archive):
                    world = self.world()
                    world.focuses = {focus}
                    world.variables["RUS_civil_service_progress_bonus"] = bonus
                    world.variables["RUS_bunker_layer_5"] = int(archive)
                    world.variables["ADISCORD_state_development_progress"] = 90
                    world.variables["ADISCORD_society_development_progress"] = 95
                    world = deepcopy(world)
                    before = world.balances()
                    world.execute(block(rows, "complete_effect"))
                    self.assertEqual(world.value("ADISCORD_state_development_progress"), 90 + state_gain + extra)
                    self.assertEqual(world.value("ADISCORD_society_development_progress"), 95 + society_gain)
                    self.assertEqual(tuple(a - b for a, b in zip(before, world.balances())), (25, 35, 0))
                    paid = world.balances(), dict(world.variables)
                    world.execute(block(rows, "complete_effect"))
                    self.assertEqual((world.balances(), world.variables), paid)

    def test_logistics_rewards_deliver_stock_and_preserve_army_reforms(self):
        for focus, equipment, variable, delta in (
            ("RUS_single_supply_register", {"support_equipment": 250}, "RUS_army_supply", -0.03),
            ("RUS_railway_coverage", {"train_equipment_1": 20, "support_equipment": 120}, "RUS_army_reinforce_rate", 0.02),
        ):
            world = self.world()
            before = dict(world.equipment)
            cash = world.value("ADISCORD_economy_treasury")
            income = world.value("ADISCORD_economy_current_month_action_income")
            world.execute(block(self.focuses[focus], "completion_reward"))
            for kind, amount in equipment.items():
                self.assertEqual(world.equipment[kind] - before.get(kind, 0), amount)
            self.assertAlmostEqual(world.value(variable), delta)
            if focus == "RUS_single_supply_register":
                self.assertEqual(world.value("ADISCORD_economy_treasury") - cash, 100)
                self.assertEqual(world.value("ADISCORD_economy_current_month_action_income") - income, 100)
            world.controller = False
            world.run("RUS_bunker_refresh")
            world.run("RUS_campaign_initialize")
            self.assertAlmostEqual(world.value(variable), delta)
            self.assertIn("RUS_black_army", world.modifiers)
        world = self.world()
        power, capacity = world.value("RUS_bunker_power"), world.value("RUS_bunker_food_capacity")
        equipment, pp = world.equipment["support_equipment"], world.pp
        world.execute(block(self.focuses["RUS_autonomous_workshops"], "completion_reward"))
        self.assertEqual(world.value("RUS_bunker_power") - power, 2)
        self.assertEqual(world.value("RUS_bunker_food_capacity") - capacity, 40)
        self.assertEqual(world.equipment["support_equipment"] - equipment, 150)
        self.assertEqual(world.pp - pp, 35)

    def test_programmes_recheck_current_ownership_unlocks_and_capacity(self):
        for name, rows in self.programmes.items():
            if any(row.key == "days_mission_timeout" for row in rows):
                continue
            targeted = any(row.key == "state_target" and row.value == "yes" for row in rows)
            national_training = name in {
                "RUS_civil_service_training", "RUS_district_health_programme", "RUS_workshop_training",
                "RUS_community_assemblies", "RUS_public_reading_rooms", "RUS_regimental_training"
            }
            changes = ("subject", "ruler", "focus") if national_training else ("owner", "controller", "subject", "ruler", "focus")
            if targeted:
                changes = ("owner", "controller", "subject", "ruler", "category")
            for changed in changes:
                world = self.world()
                if targeted and changed in ("owner", "controller", "category"):
                    world.regions[world.target_state][changed] = "rural" if changed == "category" else "VAL"
                elif changed in ("owner", "controller"):
                    setattr(world, changed, False)
                elif changed == "subject":
                    world.subject = True
                elif changed == "ruler":
                    world.ruler = "another_ruler"
                else:
                    world.focuses.clear()
                before = world.balances(), deepcopy(world.variables), deepcopy(world.buildings)
                world.execute(block(rows, "complete_effect"))
                self.assertEqual((world.balances(), world.variables, world.buildings), before, (name, changed))
            if not targeted:
                single_use = any(row.key == "fire_only_once" and row.value == "yes" for row in rows)
                if single_use:
                    self.assertNotIn("days_re_enable", [row.key for row in rows], name)
                else:
                    self.assertGreater(int(scalar(rows, "days_re_enable")), 0)
        limits = {
            "RUS_chancery_reconstruction": ("arms_factory", 6),
            "RUS_surface_industrial_contract": ("industrial_complex", 5),
        }
        for name, (building, value) in limits.items():
            world = self.world()
            world.buildings[building] = value
            self.assertFalse(world.matches(block(self.programmes[name], "available")), name)
            before = world.balances()
            world.execute(block(self.programmes[name], "complete_effect"))
            self.assertEqual(world.balances(), before, name)
        world = self.world()
        world.buildings["infrastructure"] = 5
        world.execute(block(self.programmes["RUS_aimaq_public_works"], "complete_effect"))
        self.assertEqual(world.buildings["infrastructure"], 5)
        self.assertIn("RUS_public_works_spirit", world.ideas)
        self.assertFalse(world.matches(block(self.programmes["RUS_aimaq_public_works"], "available")))
        world = self.world()
        rows = self.programmes["RUS_subterranean_supply_contract"]
        for _ in range(2):
            world.execute(block(rows, "complete_effect"))
        self.assertEqual(world.value("RUS_bunker_food_capacity"), 140)
        self.assertEqual(world.value("RUS_bunker_food_output"), 4)
        before = world.balances(), deepcopy(world.variables)
        world.execute(block(rows, "complete_effect"))
        self.assertEqual((world.balances(), world.variables), before)
        world.controller = False
        world.run("RUS_bunker_refresh")
        self.assertEqual(world.value("RUS_bunker_food_output"), 0)
        world.controller = True
        world.run("RUS_bunker_refresh")
        self.assertEqual(world.value("RUS_bunker_food_output"), 4)

    def test_factory_and_research_rewards_invalidate_economy(self):
        for name, rows in self.focuses.items():
            reward = block(rows, "completion_reward")
            needs_refresh = any(
                entry.key == "add_research_slot"
                or entry.key == "add_building_construction"
                and scalar(entry.value, "type") in ("industrial_complex", "arms_factory")
                for entry in walk(reward)
            )
            if needs_refresh:
                effects = list(walk(reward))
                refreshes = [i for i, e in enumerate(effects) if e.key == "ADISCORD_economy_mark_dirty"]
                material = [i for i, e in enumerate(effects) if e.key in ("add_research_slot", "add_building_construction")]
                self.assertTrue(refreshes, name)
                self.assertGreater(max(refreshes), max(material), name)

    def test_all_policy_routes_reach_all_common_capstones(self):
        pairs = (("scientists_council", "black_army_oath"), ("patient_war", "swift_columns"), ("bunker_open_city", "bunker_sealed_throne"), ("surface_contracts", "underground_fund"))
        for choices in product(*pairs):
            blocked = {"RUS_" + other for pair, chosen in zip(pairs, choices) for other in pair if other != chosen}
            while True:
                descendants = {name for name, rows in self.focuses.items() if any(all(child.value in blocked for child in group.value) for group in rows if group.key == "prerequisite")}
                if descendants <= blocked:
                    break
                blocked |= descendants
            done = set()
            while True:
                ready = {name for name, rows in self.focuses.items() if name not in done | blocked and all(any(child.value in done for child in group.value) for group in rows if group.key == "prerequisite")}
                if not ready:
                    break
                done |= ready
            self.assertEqual(done, set(self.focuses) - blocked)
            common = {"RUS_power_grid", "RUS_industrial_belt", "RUS_school_of_scribes", "RUS_covenant_of_service", "RUS_experimental_laboratories", "RUS_watch_the_western_scar", "RUS_reactor_decontamination"}
            self.assertTrue(common <= done, (choices, common - done))

    def test_absolute_coordinates_do_not_overlap(self):
        positions = {}
        def resolve(name):
            if name not in positions:
                rows = self.focuses[name]
                x, y = int(scalar(rows, "x")), int(scalar(rows, "y"))
                relative = next((e.value for e in rows if e.key == "relative_position_id"), None)
                if relative:
                    px, py = resolve(relative)
                    x, y = x + px, y + py
                positions[name] = (x, y)
            return positions[name]
        for name in self.focuses:
            resolve(name)
        self.assertEqual(len(set(positions.values())), len(positions))

    def test_parallel_programmes_allow_reordering_but_require_all_work(self):
        cases = (
            (("school_of_scribes", "roadside_clinics"), "a_country_of_names", 2, 77),
            (("district_ledger", "courier_stations", "district_paramedics"), "covenant_of_service", 3, 84),
            (("field_hospitals", "rifle_inspection_board"), "staff_field_exercise", 2, 70),
            (("recovery_depots", "interchangeable_parts", "second_arsenal_shift"), "strategic_freight_reserve", 3, 105),
            (("register_conquered_lands", "empire_without_rivals", "postwar_roads", "imperial_academy"), "tomorrow_above_ground", 6, 98),
        )

        def ready(name, done):
            return all(
                any(child.value in done for child in group.value)
                for group in self.focuses[name]
                if group.key == "prerequisite"
            )

        for programmes, capstone, expected_orders, expected_days in cases:
            members = tuple("RUS_" + name for name in programmes)
            final = "RUS_" + capstone
            with self.subTest(capstone=final):
                valid_orders = 0
                for order in permutations(members):
                    done = set(self.focuses) - set(members) - {final}
                    for name in order:
                        self.assertFalse(ready(final, done), (final, order, name))
                        if not ready(name, done):
                            break
                        done.add(name)
                    else:
                        self.assertTrue(ready(final, done), (final, order))
                        valid_orders += 1
                self.assertEqual(valid_orders, expected_orders)
                days = sum(float(scalar(self.focuses[name], "cost")) * 7 for name in (*members, final))
                self.assertEqual(days, expected_days)

    def test_opening_is_reachable_without_world_crisis(self):
        for name in ("RUS_bunker_survey", "RUS_surface_workshops", "RUS_count_the_hearths", "RUS_muster_books"):
            self.assertEqual(scalar(block(self.focuses[name], "prerequisite"), "focus"), "RUS_summon_the_aimaqs")
        self.assertEqual(int(scalar(self.focuses["RUS_summon_the_aimaqs"], "cost")) * 7 + int(scalar(self.focuses["RUS_bunker_survey"], "cost")) * 7, 21)
        world = BunkerWorld(self, fresh=True)
        category = block(parse(f"common/decisions/categories/ADISCORD_decision_categories_RUS.txt"), "RUS_bunker_construction")
        self.assertTrue(world.matches(block(category, "visible")))
        self.assertFalse(world.focuses)
        self.assertEqual(world.balances(), (20, 150, 20))
        world.begin("RUS_bunker_excavate")
        self.assertEqual(world.balances(), (0, 100, 0))
        world.finish("RUS_bunker_excavate")
        self.assertEqual(world.value("RUS_bunker_depth"), 1)
        for room in ("guard", "shelter"):
            self.assertTrue(world.matches(block(self.decisions["RUS_bunker_" + room], "visible")))
        before = world.balances(), deepcopy(world.variables)
        world.run("RUS_campaign_initialize")
        self.assertEqual((world.balances(), world.variables), before)

    def test_fresh_start_has_recruitable_law_before_reserves(self):
        world = BunkerWorld(self, fresh=True)
        self.assertIn("limited_conscription", world.ideas)
        self.assertEqual(world.pp, 20)

    def test_new_campaign_init_never_resets_paid_or_completed_state(self):
        world = self.world()
        world.variables["RUS_bunker_depth"] = 2
        world.begin("RUS_bunker_guard")
        before = deepcopy(world.variables)
        world.run("RUS_campaign_initialize")
        self.assertEqual(world.variables, before)
        self.assertEqual(world.events.count("ADISCORD_rus_campaign.1"), 1)

    def test_all_prices_exact_fractional_boundaries(self):
        for name in self.projects:
            world = self.world()
            rows = self.effects[name + "_start"]
            deposits = {scalar(e.value, "var"): float(scalar(e.value, "value")) for e in walk(rows) if e.key == "set_variable" and scalar(e.value, "var").startswith("RUS_bunker_escrow_")}
            world.pp = deposits["RUS_bunker_escrow_pp"]
            world.variables["ADISCORD_economy_treasury"] = deposits["RUS_bunker_escrow_cash"]
            world.equipment["support_equipment"] = deposits["RUS_bunker_escrow_equipment"]
            gate = block(self.decisions[name], "custom_cost_trigger")
            self.assertTrue(world.matches(gate), name)
            for currency in ("pp", "cash", "equipment"):
                test = deepcopy(world)
                if currency == "pp":
                    test.pp -= .01
                elif currency == "cash":
                    test.variables["ADISCORD_economy_treasury"] -= .01
                else:
                    test.equipment["support_equipment"] -= .01
                self.assertFalse(test.matches(gate), (name, currency))

    def test_one_receipt_blocks_every_other_order_and_repeated_payment(self):
        world = self.world()
        world.begin("RUS_bunker_excavate")
        before = deepcopy(world.variables), world.balances()
        for name in self.projects:
            world.run(name + "_start")
            self.assertEqual((world.variables, world.balances()), before, name)

    def test_completion_and_late_callback_are_idempotent(self):
        world = self.world()
        world.begin("RUS_bunker_excavate")
        paid = world.balances()
        world.finish("RUS_bunker_excavate")
        self.assertEqual(world.value("RUS_bunker_depth"), 1)
        self.assertEqual(world.value("RUS_bunker_integrity"), 80)
        world.finish("RUS_bunker_excavate")
        self.assertEqual(world.value("RUS_bunker_depth"), 1)
        self.assertEqual(world.balances(), paid)

    def test_wrong_callback_does_not_settle_current_order(self):
        world = self.world()
        world.begin("RUS_bunker_excavate")
        before = deepcopy(world.variables), world.balances()
        world.finish("RUS_bunker_generator")
        self.assertEqual((world.variables, world.balances()), before)

    def test_every_project_refunds_exactly_its_own_three_prices(self):
        for name in self.projects:
            world = self.world()
            if name not in ("RUS_bunker_excavate", "RUS_bunker_rush"):
                world.variables["RUS_bunker_depth"] = 5
            if name == "RUS_bunker_reinforce":
                world.variables["RUS_bunker_integrity"] = 60
            if name.startswith("RUS_bunker_upgrade_"):
                layer = name.rsplit("_", 1)[1]
                world.variables["RUS_bunker_layer_" + layer] = 2
            world.run("RUS_bunker_refresh")
            before = world.balances()
            world.begin(name)
            self.assertNotEqual(world.balances(), before)
            world.controller = False
            world.run("RUS_bunker_refund")
            world.finish(name)
            self.assertEqual(world.balances(), before, name)
            self.assertFalse(world.active, name)

    def test_each_module_preview_and_layer_bonus_equal_actual_modifier_delta(self):
        layer_bonuses = {
            ("water", "attrition"): -0.05,
            ("signals", "planning_speed"): 0.05,
            ("workshop", "industrial_capacity_factory"): 0.05,
            ("granary", "consumer_goods_factor"): -0.03,
            ("clinic", "casualty_trickleback"): 0.05,
            ("laboratory", "research_speed_factor"): 0.05,
            ("archive", "political_power_gain"): 0.10,
            ("command", "max_planning_factor"): 0.05,
        }
        rooms = ("guard", "shelter", "water", "signals", "workshop", "granary", "clinic", "laboratory", "archive", "command")
        for room in rooms:
            world = self.world()
            world.variables["RUS_bunker_depth"] = 5
            world.run("RUS_bunker_refresh")
            before = dict(world.variables)
            world.begin("RUS_bunker_" + room)
            world.finish("RUS_bunker_" + room)
            preview = block(self.ideas["RUS_bunker_" + room + "_delta"], "modifier")
            for entry in preview:
                key = "RUS_bunker_" + entry.key
                expected = float(entry.value) + layer_bonuses.get((room, entry.key), 0)
                self.assertAlmostEqual(world.value(key) - before.get(key, 0), expected, msg=room)
            self.assertFalse(any(name.endswith("_delta") for name in world.ideas))

    def test_gui_room_rewards_match_the_dummy_and_supply_delta(self):
        rooms = ("guard", "shelter", "water", "signals", "workshop", "granary", "clinic", "laboratory", "archive", "command")
        for room in rooms:
            name = "RUS_bunker_" + room
            key = name + "_gui_reward_tt"
            self.assertNotIn("$", self.loc[name + "_ui_tt"])
            self.assertIn(self.loc[key], self.loc[name + "_ui_tt"])
            amounts = re.findall(r"§G([+-][0-9.]+)(%?)§!", self.loc[key])
            modifiers = block(self.ideas[name + "_delta"], "modifier")
            self.assertEqual(len(amounts), len(modifiers), room)
            for (amount, percentage), modifier in zip(amounts, modifiers):
                actual = float(amount) / (100 if percentage else 1)
                self.assertAlmostEqual(actual, float(modifier.value), msg=room)
            if room in ("water", "granary"):
                world = self.world()
                world.variables["RUS_bunker_depth"] = 5
                world.run("RUS_bunker_refresh")
                before = world.value("RUS_bunker_food_output")
                world.begin(name)
                world.finish(name)
                declared = re.search(r"Продовольствие: §G\+([0-9]+)§!", self.loc[name + "_ui_tt"])
                self.assertEqual(world.value("RUS_bunker_food_output") - before, int(declared[1]))

    def bunker_text(self, world, name):
        functions = {
            scalar(row.value, "name"): row.value
            for row in parse("common/scripted_localisation/ADISCORD_RUS_scripted_loc.txt")
            if row.key == "defined_text"
        }
        self.assertTrue(name in functions, name)
        for entry in functions[name]:
            if entry.key != "text":
                continue
            gate = next((child.value for child in entry.value if child.key == "trigger"), [])
            if world.matches(gate):
                return scalar(entry.value, "localization_key")
        self.fail(f"No text selected for {name}")

    def test_bunker_displayed_durations_match_paid_decision_timers(self):
        rooms = ("guard", "shelter", "water", "signals", "workshop", "granary", "clinic", "laboratory", "archive", "command")
        names = ["excavate", *rooms, *(f"upgrade_{layer}" for layer in range(1, 6)), "generator", "reinforce"]
        for language in ("russian", "english"):
            loc = dict(re.findall(r'^\s+(\w+):\d*\s+"(.*)"\s*$', read(f"localisation/{language}/{BASE}_l_{language}.yml"), re.M))
            for name in names:
                decision = "RUS_bunker_" + name
                days = int(scalar(self.decisions[decision], "days_remove"))
                suffixes = ("_desc", "_order_price", "_service_tt" if name in ("generator", "reinforce") else "_ui_tt")
                for suffix in suffixes:
                    key = decision + suffix
                    with self.subTest(language=language, key=key):
                        plain = re.sub(r"§.", "", loc[key])
                        durations = re.findall(r"\b(\d+)\s+(?:дн\.|дней|день|days\b)", plain)
                        self.assertEqual(durations, [str(days)])

    def test_bunker_work_and_food_tooltips_follow_actual_focus_upgrades(self):
        for upgraded in (False, True):
            world = self.world()
            focuses = {"RUS_bunker_layer_service_school", "RUS_bunker_eternal_headquarters", "RUS_bunker_emergency_rations"}
            world.focuses.difference_update(focuses)
            if upgraded:
                world.focuses.update(focuses)
            world.variables.update({"RUS_bunker_depth": 1, "RUS_bunker_layer_1": 1, "RUS_bunker_food": 0})
            world.run("RUS_bunker_refresh")
            minimum_key = self.bunker_text(world, "GetRUSBunkerRushMinimum")
            minimum = int(re.search(r"\d+", self.loc[minimum_key])[0])
            for integrity, allowed in ((minimum - 0.01, False), (minimum, True)):
                world.variables["RUS_bunker_integrity"] = integrity
                self.assertEqual(world.matches(self.triggers["RUS_bunker_rush_requirements"]), allowed)
            hunger = "RUS_bunker_hunger_rationed" if upgraded else "RUS_bunker_hunger"
            self.assertIn(hunger, world.ideas)
            hunger_key = self.bunker_text(world, "GetRUSBunkerHungerPenalty")
            spoilage_key = self.bunker_text(world, "GetRUSBunkerSpoilageRate")
            for language in ("russian", "english"):
                loc = dict(re.findall(r'^\s+(\w+):\d*\s+"(.*)"\s*$', read(f"localisation/{language}/{BASE}_l_{language}.yml"), re.M))
                for modifier in block(self.ideas[hunger], "modifier"):
                    value = float(modifier.value)
                    amount = f"{value:.2f}" if modifier.key == "political_power_gain" else f"{value * 100:g}%"
                    self.assertIn(f"§R{amount}§!", loc[hunger_key])
                rate = float(re.search(r"([\d.]+)%", loc[spoilage_key])[1]) / 100
                world.variables.update({"RUS_bunker_food": 100, "RUS_bunker_food_capacity": 100})
                world.run("RUS_bunker_spoil_now")
                self.assertAlmostEqual(world.value("RUS_bunker_food_spoiled"), 25 * rate)
                self.assertIn("[?RUS_bunker_food_fed_line|0]", loc["RUS_bunker_metric_food_tt"])
                for variable in ("RUS_bunker_rush_damage", "RUS_bunker_reinforce_amount"):
                    self.assertIn(f"[?{variable}|0]", loc["RUS_bunker_metric_integrity_tt"])

    def test_displayed_energy_contract_cap_matches_each_focus_combination(self):
        focuses = ("RUS_bunker_surface_market", "RUS_bunker_reserve_shaft")
        for completed in product((False, True), repeat=2):
            world = self.world()
            world.focuses.difference_update(focuses)
            world.focuses.update(focus for focus, done in zip(focuses, completed) if done)
            key = self.bunker_text(world, "GetRUSEnergyContractLimit")
            for language in ("russian", "english"):
                loc = dict(re.findall(r'^\s+(\w+):\d*\s+"(.*)"\s*$', read(f"localisation/{language}/{BASE}_l_{language}.yml"), re.M))
                cap = int(re.search(r"\d+", loc[key])[0])
                for contracts, allowed in ((cap - 1, True), (cap, False)):
                    world.variables["RUS_energy_contracts"] = contracts
                    self.assertEqual(world.matches(self.triggers["RUS_energy_contract_room"]), allowed, completed)

    def test_room_forecasts_match_settled_power_and_net_food(self):
        rooms = (
            ("guard", 2, "room"), ("shelter", 1, "room"),
            ("water", 1, "water"), ("signals", 2, "room"),
            ("workshop", 3, "room"), ("granary", 1, "granary"),
            ("clinic", 2, "room"), ("laboratory", 3, "room"),
            ("archive", 1, "room"), ("command", 2, "room"),
        )
        for room, power, food in rooms:
            with self.subTest(room=room):
                world = self.world()
                world.variables["RUS_bunker_depth"] = 5
                world.variables["RUS_bunker_generators"] = 1
                world.run("RUS_bunker_refresh")
                power_after = world.value(f"RUS_bunker_preview_power_{power}")
                food_after = world.value(f"RUS_bunker_preview_food_{food}")
                self.assertEqual(power_after, 8 - power)
                self.assertEqual(food_after, {"room": 1, "water": 3, "granary": 6}[food])
                world.begin(f"RUS_bunker_{room}")
                world.finish(f"RUS_bunker_{room}")
                self.assertEqual(world.value("RUS_bunker_free_power"), power_after)
                self.assertEqual(world.value("RUS_bunker_food_balance"), food_after)
                self.assertEqual(
                    self.bunker_text(world, f"GetRUSBunkerForecast{room}"),
                    "RUS_bunker_forecast_installed",
                )

    def test_service_feedback_names_the_actual_blocker(self):
        world = self.world()
        world.focuses.discard("RUS_bunker_power_school")
        for service in ("generator", "energy_sale"):
            self.assertEqual(self.bunker_text(world, "GetRUSBunkerService" + service), "RUS_bunker_service_need_power_school")
        world.focuses.add("RUS_bunker_power_school")
        world.variables["RUS_bunker_generators"] = 2
        self.assertEqual(self.bunker_text(world, "GetRUSBunkerServicegenerator"), "RUS_bunker_service_generators_full")
        world.variables["RUS_bunker_integrity"] = 61
        self.assertEqual(self.bunker_text(world, "GetRUSBunkerServicereinforce"), "RUS_bunker_service_structure_sound")
        world.variables["RUS_bunker_food"] = 100
        world.variables["RUS_bunker_project"] = 11
        world.run("RUS_bunker_refresh")
        self.assertEqual(self.bunker_text(world, "GetRUSBunkerServiceresupply"), "RUS_bunker_service_storage_full")
        world.variables["RUS_bunker_food"] = 0
        world.run("RUS_bunker_refresh")
        self.assertEqual(self.bunker_text(world, "GetRUSBunkerServiceresupply"), "RUS_bunker_service_ready")
        world.variables["RUS_bunker_energy_export_power"] = 1
        self.assertEqual(self.bunker_text(world, "GetRUSBunkerServiceenergy_sale"), "RUS_bunker_service_contract_active")

    def test_integrity_forecast_matches_settlement_and_emergency_boundary(self):
        for operation, integrity in (("excavate", 59), ("excavate", 60), ("rush", 74), ("rush", 75), ("reinforce", 60)):
            with self.subTest(operation=operation, integrity=integrity):
                world = self.world()
                world.variables["RUS_bunker_integrity"] = integrity
                world.run("RUS_bunker_refresh")
                predicted = world.value(f"RUS_bunker_preview_{operation}")
                self.assertEqual(predicted, integrity + {"excavate": -20, "rush": -35, "reinforce": 40}[operation])
                if operation != "reinforce":
                    suffix = "danger" if predicted < 40 else "safe"
                    self.assertEqual(
                        self.bunker_text(world, f"GetRUSBunkerForecast{operation}"),
                        f"RUS_bunker_forecast_{operation}_{suffix}",
                    )
                world.begin(f"RUS_bunker_{operation}")
                world.finish(f"RUS_bunker_{operation}")
                self.assertEqual(world.value("RUS_bunker_integrity"), predicted)

    def test_feedback_distinguishes_empty_fed_hungry_and_offline_complex(self):
        world = self.world()
        world.variables["RUS_bunker_food"] = 100
        world.run("RUS_bunker_refresh")
        self.assertEqual(self.bunker_text(world, "GetRUSBunkerPriority"), "RUS_bunker_priority_excavate")
        world.variables["RUS_bunker_layer_1"] = 1
        world.variables["RUS_bunker_depth"] = 1
        for stock, expected in ((0, "hungry"), (74, "normal"), (75, "fed")):
            world.variables["RUS_bunker_food"] = stock
            world.run("RUS_bunker_refresh")
            self.assertEqual(self.bunker_text(world, "GetRUSBunkerFoodState"), f"RUS_bunker_food_state_{expected}")
        world.variables["RUS_bunker_integrity"] = 39
        world.run("RUS_bunker_refresh")
        self.assertEqual(self.bunker_text(world, "GetRUSBunkerIntegrityState"), "RUS_bunker_integrity_danger")
        world.variables["RUS_bunker_integrity"] = 40
        world.run("RUS_bunker_refresh")
        self.assertEqual(self.bunker_text(world, "GetRUSBunkerIntegrityState"), "RUS_bunker_integrity_low")
        world.controller = False
        world.run("RUS_bunker_refresh")
        for function in ("GetRUSBunkerPriority", "GetRUSBunkerBenefits", "GetRUSBunkerBenefitDetails", "GetRUSBunkerFoodState"):
            self.assertEqual(self.bunker_text(world, function), "RUS_bunker_feedback_offline")

    def test_upgrade_forecasts_preserve_room_upkeep_and_include_extra_power(self):
        for layer, variant in ((3, 1), (3, 2), (4, 1), (4, 2)):
            with self.subTest(layer=layer, variant=variant):
                world = self.world()
                world.variables["RUS_bunker_depth"] = 5
                world.variables["RUS_bunker_generators"] = 2
                world.variables[f"RUS_bunker_layer_{layer}"] = variant
                world.run("RUS_bunker_refresh")
                power_after = world.value("RUS_bunker_preview_power_1")
                food_after = world.value("RUS_bunker_preview_food_upgrade_granary") if (layer, variant) == (3, 2) else world.value("RUS_bunker_food_balance")
                world.begin(f"RUS_bunker_upgrade_{layer}")
                world.finish(f"RUS_bunker_upgrade_{layer}")
                self.assertEqual(world.value("RUS_bunker_free_power"), power_after)
                self.assertEqual(world.value("RUS_bunker_food_balance"), food_after)
                world.execute(block(self.decisions[f"RUS_bunker_strip_{layer}"], "complete_effect"))
                self.assertEqual(world.value("RUS_bunker_preview_power_3"), 9)
                self.assertEqual(world.value("RUS_bunker_preview_food_room"), 1)

    def test_procurement_cannot_arbitrage_money(self):
        world = self.world()
        world.variables["ADISCORD_economy_treasury"] = 1000
        world.pp = 100
        cash = world.value("ADISCORD_economy_treasury")
        rifles = world.equipment["infantry_equipment"]
        world.execute(block(self.decisions["RUS_rifle_order"], "complete_effect"))
        bought = world.equipment["infantry_equipment"] - rifles
        price = cash - world.value("ADISCORD_economy_treasury")
        self.assertEqual((bought, price, world.pp), (25000, 200, 50))
        stock = world.equipment["infantry_equipment"]
        cash = world.value("ADISCORD_economy_treasury")
        world.execute(block(self.decisions["RUS_market_surplus"], "complete_effect"))
        sold = stock - world.equipment["infantry_equipment"]
        income = world.value("ADISCORD_economy_treasury") - cash
        self.assertEqual((sold, income, world.pp), (10000, 75, 35))
        self.assertLess(income * bought, price * sold)

    def test_only_deficient_currencies_render_red(self):
        functions = {scalar(e.value, "name"): e.value for e in parse("common/scripted_localisation/ADISCORD_RUS_scripted_loc.txt")}
        world = self.world()
        world.pp = 19.99
        world.variables["ADISCORD_economy_treasury"] = 150
        world.equipment["support_equipment"] = 20
        for suffix, expected in (("pp", "§R"), ("cash", "§Y"), ("equipment", "§Y")):
            rows = functions["GetRUSBunker1" + suffix]
            selected = None
            for entry in rows:
                if entry.key != "text":
                    continue
                gate = next((child.value for child in entry.value if child.key == "trigger"), [])
                if world.matches(gate):
                    selected = self.loc[scalar(entry.value, "localization_key")]
                    break
            self.assertTrue(selected.startswith(expected), suffix)

    def test_panel_has_five_clickable_layers_and_native_project_actions(self):
        scripted = block(parse("common/scripted_guis/ADISCORD_RUS_scripted_gui.txt"), "scripted_gui")
        panel = block(scripted, "ADISCORD_RUS_bunker_panel")
        self.assertEqual(scalar(panel, "context_type"), "decision_category")
        self.assertFalse(any(e.key == "dirty" for e in panel))
        actions = block(panel, "effects")
        window = next(row.value for row in block(parse("interface/ADISCORD_RUS.gui"), "guiTypes") if row.key == "containerWindowType" and scalar(row.value, "name") == "ADISCORD_RUS_bunker_window")
        self.assertEqual(scalar(window, "name"), scalar(panel, "window_name"))
        text_keys = [scalar(e.value, "text") for e in window if e.key == "instantTextBoxType"]
        for i in range(1, 6):
            self.assertIn(f"RUS_bunker_panel_floor_{i}", text_keys)
            self.assertIn(f"RUS_bunker_floor_{i}_click", [e.key for e in actions])
        for name in self.projects:
            if name in ("RUS_bunker_excavate", "RUS_bunker_rush", "RUS_bunker_generator", "RUS_bunker_reinforce"):
                continue
            click = block(actions, name + "_button_click")
            self.assertTrue(any(e.key == "activate_decision" and e.value == name for e in walk(click)))
            self.assertFalse(any(e.key == "add_political_power" for e in walk(click)))
        for key in text_keys:
            self.assertIn(key, self.loc)

    def test_owner_control_ruler_subject_and_capitulation_cancel_once(self):
        for field, value in (("owner", False), ("controller", False), ("ruler", None), ("subject", True), ("capitulated", True)):
            world = self.world()
            before = world.balances()
            world.begin("RUS_bunker_excavate")
            setattr(world, field, value)
            world.run("RUS_bunker_refresh")
            world.run("RUS_bunker_refund")
            world.finish("RUS_bunker_excavate")
            self.assertEqual(world.balances(), before, field)
            self.assertEqual(world.value("RUS_bunker_depth"), 0)
            self.assertFalse(world.active)
            self.assertNotIn("RUS_bunker_complex", world.modifiers)
            self.assertEqual(world.value("ADISCORD_economy_current_month_action_income"), 100)
            self.assertEqual(world.value("ADISCORD_economy_current_month_action_costs"), 50)

    def test_changed_depth_invalidates_old_receipt(self):
        world = self.world()
        before = world.balances()
        world.begin("RUS_bunker_excavate")
        world.variables["RUS_bunker_depth"] = 1
        world.finish("RUS_bunker_excavate")
        self.assertEqual(world.value("RUS_bunker_depth"), 1)
        self.assertEqual(world.balances(), before)

    def test_five_layers_all_32_loadouts_can_be_paid_without_deadlock(self):
        choices = (("guard", "shelter"), ("water", "signals"), ("workshop", "granary"), ("clinic", "laboratory"), ("archive", "command"))
        for loadout in product(*choices):
            world = self.world()
            world.variables["RUS_bunker_depth_limit"] = 5
            for layer, room in enumerate(loadout, 1):
                if world.value("RUS_bunker_integrity") < 40:
                    world.begin("RUS_bunker_reinforce")
                    world.finish("RUS_bunker_reinforce")
                world.begin("RUS_bunker_excavate")
                world.finish("RUS_bunker_excavate")
                gate = self.triggers["RUS_bunker_" + room + "_requirements"]
                while not world.matches(gate):
                    self.assertLess(world.value("RUS_bunker_generators"), 2, loadout)
                    world.begin("RUS_bunker_generator")
                    world.finish("RUS_bunker_generator")
                world.begin("RUS_bunker_" + room)
                world.finish("RUS_bunker_" + room)
                self.assertEqual(world.value("RUS_bunker_depth"), layer)
                self.assertGreaterEqual(world.value("RUS_bunker_free_power"), 0)
            while world.value("RUS_bunker_integrity") < 60:
                world.begin("RUS_bunker_reinforce")
                world.finish("RUS_bunker_reinforce")
            self.assertTrue(world.matches(block(self.focuses["RUS_bunker_commission"], "available")))
            self.assertEqual(world.value("RUS_bunker_fitted"), 5)
            self.assertLessEqual(world.value("RUS_bunker_power"), 12)

    def test_fast_excavation_has_a_live_damage_cost_and_repair(self):
        world = self.world()
        world.variables["RUS_bunker_depth_limit"] = 5
        for _ in range(2):
            world.begin("RUS_bunker_rush")
            world.finish("RUS_bunker_rush")
        self.assertEqual(world.value("RUS_bunker_integrity"), 30)
        self.assertEqual(world.value("RUS_bunker_army_org_factor"), -.05)
        self.assertEqual(world.value("RUS_bunker_industrial_capacity_factory"), -.05)
        world.begin("RUS_bunker_reinforce")
        world.finish("RUS_bunker_reinforce")
        self.assertEqual(world.value("RUS_bunker_integrity"), 90, "The airlock focus restores 60")
        self.assertEqual(world.value("RUS_bunker_army_org_factor"), 0)
        plain = self.world()
        plain.focuses.discard("RUS_bunker_airlocks")
        plain.variables["RUS_bunker_integrity"] = 30
        plain.run("RUS_bunker_refresh")
        plain.begin("RUS_bunker_reinforce")
        plain.finish("RUS_bunker_reinforce")
        self.assertEqual(plain.value("RUS_bunker_integrity"), 70)

    def test_liberation_preserves_rooms_and_does_not_duplicate_rewards(self):
        world = self.world()
        world.variables["RUS_bunker_depth"] = 1
        world.begin("RUS_bunker_guard")
        world.finish("RUS_bunker_guard")
        expected = world.value("RUS_bunker_army_org_factor")
        for _ in range(3):
            world.controller = False
            world.run("RUS_bunker_refresh")
            self.assertNotIn("RUS_bunker_complex", world.modifiers)
            world.controller = True
            world.run("RUS_bunker_refresh")
            self.assertIn("RUS_bunker_complex", world.modifiers)
            self.assertEqual(world.value("RUS_bunker_army_org_factor"), expected)
            self.assertEqual(world.value("RUS_bunker_layer_1"), 1)

    def test_demolition_frees_power_and_requires_new_payment(self):
        world = self.world()
        world.variables["RUS_bunker_depth"] = 1
        world.begin("RUS_bunker_guard")
        world.finish("RUS_bunker_guard")
        balance = world.balances()
        world.execute(block(self.decisions["RUS_bunker_strip_1"], "complete_effect"))
        self.assertEqual(world.balances(), balance)
        self.assertEqual(world.value("RUS_bunker_free_power"), 4)
        self.assertEqual(world.value("RUS_bunker_army_org_factor"), 0)
        world.begin("RUS_bunker_shelter")
        world.finish("RUS_bunker_shelter")
        self.assertEqual(world.value("RUS_bunker_layer_1"), 2)
        self.assertLess(world.value("ADISCORD_economy_treasury"), balance[1])

    def test_gui_click_uses_native_timer_and_selection_does_not_cancel_receipt(self):
        world = self.world()
        panel = block(block(parse("common/scripted_guis/ADISCORD_RUS_scripted_gui.txt"), "scripted_gui"), "ADISCORD_RUS_bunker_panel")
        actions = block(panel, "effects")
        world.variables["RUS_bunker_depth"] = 1
        world.execute(block(actions, "RUS_bunker_guard_button_click"))
        self.assertIn("RUS_bunker_guard", world.active)
        self.assertEqual(world.value("RUS_bunker_layer_1"), 0)
        paid = world.balances()
        world.execute(block(actions, "RUS_bunker_guard_button_click"))
        self.assertEqual(world.balances(), paid)
        world.execute(block(actions, "RUS_bunker_floor_5_click"))
        self.assertEqual(world.value("RUS_bunker_selected_layer"), 5)
        self.assertFalse(world.matches(block(self.decisions["RUS_bunker_guard"], "cancel_trigger")))
        world.finish("RUS_bunker_guard")
        self.assertEqual(world.value("RUS_bunker_layer_1"), 1)
        self.assertEqual(world.balances(), paid)

    def test_upgrade_changes_each_existing_room_and_cannot_be_paid_twice(self):
        for layer in range(1, 6):
            for variant in (1, 2):
                world = self.world()
                world.variables["RUS_bunker_depth"] = 5
                world.variables[f"RUS_bunker_layer_{layer}"] = variant
                world.variables["RUS_bunker_generators"] = 2
                world.run("RUS_bunker_refresh")
                base = dict(world.variables)
                name = f"RUS_bunker_upgrade_{layer}"
                world.begin(name)
                paid = world.balances()
                world.finish(name)
                self.assertEqual(world.value(name), 1)
                self.assertEqual(world.value(f"RUS_bunker_layer_{layer}"), variant)
                self.assertTrue(any(world.value(key) != value for key, value in base.items() if key.startswith("RUS_bunker_") and key not in (name, "RUS_bunker_food_space")))
                world.run(name + "_start")
                world.finish(name)
                self.assertEqual(world.balances(), paid)
                self.assertFalse(world.active)
                world.execute(block(self.decisions[f"RUS_bunker_strip_{layer}"], "complete_effect"))
                self.assertEqual(world.value(name), 0)

    def test_all_32_loadouts_can_fit_all_upgrades_with_turbine(self):
        for loadout in product((1, 2), repeat=5):
            world = self.world()
            world.variables["RUS_bunker_depth"] = 5
            world.variables["RUS_bunker_generators"] = 2
            world.variables["RUS_bunker_power_bonus"] = 2
            for layer, variant in enumerate(loadout, 1):
                world.variables[f"RUS_bunker_layer_{layer}"] = variant
            world.run("RUS_bunker_refresh")
            for layer in range(1, 6):
                name = f"RUS_bunker_upgrade_{layer}"
                world.begin(name)
                world.finish(name)
                self.assertEqual(world.value(name), 1)
                self.assertGreaterEqual(world.value("RUS_bunker_free_power"), 0)

    def test_ai_reserves_power_for_fifth_room_before_energy_consuming_upgrades(self):
        world = self.world()
        world.focuses.remove("RUS_bunker_commission")
        world.focuses.remove("RUS_bunker_reserve_turbine")
        world.variables["RUS_bunker_depth_limit"] = 5

        def ai_wants_upgrade(name):
            rows = block(self.decisions[name], "ai_will_do")
            weight = float(scalar(rows, "base"))
            for entry in rows:
                if entry.key == "modifier":
                    conditions = [child for child in entry.value if child.key != "factor"]
                    if world.matches(conditions):
                        weight *= float(scalar(entry.value, "factor"))
            return weight > 0

        for layer, room in enumerate(("guard", "signals", "workshop", "laboratory", "command"), 1):
            if world.value("RUS_bunker_integrity") < 40:
                world.begin("RUS_bunker_reinforce")
                world.finish("RUS_bunker_reinforce")
            world.begin("RUS_bunker_excavate")
            world.finish("RUS_bunker_excavate")
            while not world.matches(self.triggers[f"RUS_bunker_{room}_requirements"]):
                self.assertLess(world.value("RUS_bunker_generators"), 2)
                world.begin("RUS_bunker_generator")
                world.finish("RUS_bunker_generator")
            world.begin(f"RUS_bunker_{room}")
            world.finish(f"RUS_bunker_{room}")
            upgrade = f"RUS_bunker_upgrade_{layer}"
            if ai_wants_upgrade(upgrade):
                world.begin(upgrade)
                world.finish(upgrade)
            elif layer in (3, 4):
                self.assertEqual(world.value(upgrade), 0)
        self.assertEqual(world.value("RUS_bunker_fitted"), 5)
        self.assertEqual(world.value("RUS_bunker_used_power"), 12)
        while world.value("RUS_bunker_integrity") < 60:
            world.begin("RUS_bunker_reinforce")
            world.finish("RUS_bunker_reinforce")
        self.assertTrue(world.matches(block(self.focuses["RUS_bunker_commission"], "available")))
        world.focuses.add("RUS_bunker_commission")
        self.assertTrue(ai_wants_upgrade("RUS_bunker_upgrade_3"))
        self.assertTrue(ai_wants_upgrade("RUS_bunker_upgrade_4"))

    def test_food_weekly_production_consumption_storage_and_shortage(self):
        world = self.world()
        world.focuses.discard("RUS_strategic_freight_reserve")
        world.focuses.discard("RUS_bunker_eternal_headquarters")
        world.variables["RUS_bunker_depth"] = 5
        for layer in range(1, 6):
            world.variables[f"RUS_bunker_layer_{layer}"] = 2 if layer != 3 else 1
        world.variables["RUS_bunker_food"] = 2
        world.run("RUS_bunker_refresh")
        self.assertEqual(world.value("RUS_bunker_food_balance"), -3)
        org = world.value("RUS_bunker_army_org_factor")
        stability = world.value("RUS_bunker_stability_factor")
        world.run("RUS_bunker_weekly_supply")
        self.assertEqual(world.value("RUS_bunker_food"), 0)
        self.assertIn("RUS_bunker_hunger", world.ideas)
        self.assertAlmostEqual(world.value("RUS_bunker_army_org_factor"), org)
        self.assertAlmostEqual(world.value("RUS_bunker_stability_factor"), stability)
        before = world.balances()
        world.run("RUS_bunker_resupply")
        self.assertEqual(world.value("RUS_bunker_food"), 40)
        self.assertEqual(world.balances(), (before[0] - 15, before[1] - 165, before[2]))
        self.assertNotIn("RUS_bunker_hunger", world.ideas)
        world.variables["RUS_bunker_layer_2"] = 1
        world.variables["RUS_bunker_layer_3"] = 2
        world.variables["RUS_bunker_upgrade_3"] = 1
        world.variables["RUS_bunker_food_output_bonus"] = 2
        world.variables["RUS_bunker_food_capacity_bonus"] = 60
        world.variables["RUS_bunker_food"] = 158
        world.run("RUS_bunker_refresh")
        self.assertEqual(world.value("RUS_bunker_food_balance"), 8)
        world.run("RUS_bunker_weekly_supply")
        self.assertEqual(world.value("RUS_bunker_food"), 160)

    def test_food_purchase_boundaries_and_no_stock_reset_on_reopen_or_liberation(self):
        world = self.world()
        world.focuses.discard("RUS_strategic_freight_reserve")
        world.pp = 15
        world.variables["ADISCORD_economy_treasury"] = 165
        world.variables["RUS_bunker_food"] = 60.01
        world.run("RUS_bunker_refresh")
        before = world.balances()
        world.run("RUS_bunker_resupply")
        self.assertEqual(world.balances(), before)
        world.variables["RUS_bunker_food"] = 60
        world.run("RUS_bunker_refresh")
        world.run("RUS_bunker_resupply")
        self.assertEqual(world.balances(), (0, 0, before[2]))
        self.assertEqual(world.value("RUS_bunker_food"), 100)
        world.variables["RUS_bunker_food"] = 37
        world.controller = False
        world.run("RUS_bunker_refresh")
        world.run("RUS_bunker_weekly_supply")
        world.run("RUS_campaign_initialize")
        self.assertEqual(world.value("RUS_bunker_food"), 37)
        world.controller = True
        world.run("RUS_bunker_refresh")
        self.assertEqual(world.value("RUS_bunker_food"), 37)

    def test_ration_states_switch_bonuses_only_when_the_state_changes(self):
        world = self.world()
        world.variables["RUS_bunker_depth"] = 1
        world.variables["RUS_bunker_layer_1"] = 2
        world.variables["RUS_bunker_food"] = 75
        world.run("RUS_bunker_refresh")
        self.assertEqual(world.value("RUS_bunker_food_fed_line"), 75)
        self.assertEqual(world.value("RUS_bunker_food_state"), 2)
        self.assertAlmostEqual(world.value("RUS_bunker_stability_factor"), 0.15)
        self.assertAlmostEqual(world.value("RUS_bunker_reinforce_rate"), 0.05)
        world.variables["RUS_bunker_food"] = 74.99
        world.run("RUS_bunker_refresh")
        self.assertEqual(world.value("RUS_bunker_food_state"), 1)
        self.assertEqual(world.value("RUS_bunker_reinforce_rate"), 0)
        world.variables["RUS_bunker_food"] = 70
        world.run("RUS_bunker_refresh")
        steady = world.dirty
        world.run("RUS_bunker_weekly_supply")
        self.assertEqual(world.value("RUS_bunker_food"), 71)
        self.assertEqual(world.dirty, steady)
        world.variables["RUS_bunker_food"] = 74
        world.run("RUS_bunker_weekly_supply")
        self.assertEqual(world.value("RUS_bunker_food_state"), 2)
        self.assertGreater(world.dirty, steady)
        world.variables["RUS_bunker_layer_1"] = 0
        world.variables["RUS_bunker_food"] = 100
        world.run("RUS_bunker_refresh")
        self.assertEqual(world.value("RUS_bunker_food_state"), 1, "An unfitted bunker has nobody to feed")
        bunker_modifier = block(
            parse(f"common/dynamic_modifiers/ADISCORD_dynamic_modifiers_RUS.txt"),
            "RUS_bunker_complex",
        )
        self.assertEqual(
            scalar(bunker_modifier, "land_reinforce_rate"), "RUS_bunker_reinforce_rate"
        )

    def test_freight_reserve_convoy_and_surplus_sale_settle_exact_amounts(self):
        world = self.world()
        world.variables["RUS_bunker_food_capacity_bonus"] = 40
        world.variables["RUS_bunker_food"] = 80.01
        world.run("RUS_bunker_refresh")
        before = world.balances()
        world.run("RUS_bunker_resupply")
        self.assertEqual(world.balances(), before, "The larger convoy needs room for all 60")
        world.variables["RUS_bunker_food"] = 80
        world.run("RUS_bunker_refresh")
        world.run("RUS_bunker_resupply")
        self.assertEqual(world.value("RUS_bunker_food"), 140)
        self.assertEqual(world.balances(), (before[0] - 15, before[1] - 165, before[2]))
        income = world.value("ADISCORD_economy_current_month_action_income")
        world.run("RUS_bunker_food_sale")
        self.assertEqual(world.value("RUS_bunker_food"), 100)
        self.assertEqual(world.value("ADISCORD_economy_treasury"), before[1] - 165 + 100)
        self.assertEqual(world.value("ADISCORD_economy_current_month_action_income") - income, 100)
        world.variables["RUS_bunker_food"] = 39.99
        cash = world.value("ADISCORD_economy_treasury")
        world.run("RUS_bunker_food_sale")
        self.assertEqual((world.value("RUS_bunker_food"), world.value("ADISCORD_economy_treasury")), (39.99, cash))
        depot = block(self.focuses["RUS_recovery_depots"], "completion_reward")
        self.assertEqual(scalar(block(depot, "effect_tooltip"), "add_ideas"), "RUS_repair_depots_spirit")
        self.assertFalse(any(entry.key == "add_equipment_to_stockpile" for entry in depot))
        output = world.value("RUS_bunker_food_output")
        world.execute(depot)
        self.assertEqual(world.value("RUS_bunker_food_output"), output + 2)
        self.assertIn("RUS_bunker_food_sale", self.decisions)

    def test_food_sale_card_uses_native_payment_and_blocks_repeat_clicks(self):
        panel = block(block(parse("common/scripted_guis/ADISCORD_RUS_scripted_gui.txt"), "scripted_gui"), "ADISCORD_RUS_bunker_panel")
        gates = block(panel, "triggers")
        name = "RUS_bunker_food_sale"
        gate = block(gates, name + "_button_click_enabled")
        action = block(block(panel, "effects"), name + "_button_click")
        for stock in (39.99, 40, 100):
            world = self.world()
            world.variables["RUS_bunker_food"] = stock
            self.assertEqual(world.matches(gate), stock >= 40)
            expected = "RUS_bunker_service_ready" if stock >= 40 else "RUS_bunker_food_sale_need_stock"
            self.assertEqual(self.bunker_text(world, "GetRUSBunkerServicefood_sale"), expected)
            world.owner = False
            self.assertFalse(world.matches(gate))
            self.assertEqual(self.bunker_text(world, "GetRUSBunkerServicefood_sale"), "RUS_bunker_need_operational")
        for native in (False, True):
            world = self.world()
            world.variables["RUS_bunker_food"] = 100
            before = world.value("ADISCORD_economy_treasury")
            if native:
                world.begin(name)
            else:
                world.execute(action)
            self.assertEqual(world.value("RUS_bunker_food"), 60)
            self.assertEqual(world.value("ADISCORD_economy_treasury"), before + 100)
            self.assertFalse(world.matches(gate))
            self.assertEqual(self.bunker_text(world, "GetRUSBunkerServicefood_sale"), "RUS_bunker_food_sale_cooldown")
            world.execute(action)
            self.assertEqual(world.value("RUS_bunker_food"), 60)
            self.assertEqual(world.value("ADISCORD_economy_treasury"), before + 100)
            world.flags.discard(name + "_ui_cooldown")
            self.assertTrue(world.matches(gate))
        decision = self.decisions[name]
        cooldown = next(row.value for row in walk(block(decision, "complete_effect")) if row.key == "set_country_flag")
        self.assertEqual(scalar(cooldown, "days"), scalar(decision, "days_re_enable"))
        world = self.world()
        for service_tab in (False, True):
            if service_tab:
                world.flags.add("RUS_bunker_service_tab")
            for suffix in ("", "_label", "_benefit", "_cost", "_status"):
                self.assertEqual(world.matches(block(gates, name + "_button" + suffix + "_visible")), service_tab)

    def test_emergency_ration_focus_delivers_full_stock_even_to_full_stores(self):
        for stock, expected in ((0, 80), (60, 140), (140, 220)):
            world = self.world()
            world.variables["RUS_bunker_food_capacity_bonus"] = 40
            world.variables["RUS_bunker_food"] = stock
            world.run("RUS_bunker_refresh")
            world.execute(block(self.focuses["RUS_bunker_emergency_rations"], "completion_reward"))
            self.assertEqual(world.value("RUS_bunker_food"), expected)
            self.assertEqual(world.value("RUS_bunker_food_capacity"), 220)

    BUNKER_COURSES = {
        "RUS_bunker_open_city": ("RUS_bunker_closed_cycle", "RUS_bunker_cold_stores", "RUS_bunker_systems_college"),
        "RUS_bunker_sealed_throne": ("RUS_bunker_reserve_turbine", "RUS_bunker_machine_depot", "RUS_bunker_emergency_rations"),
    }

    def test_bunker_courses_reach_only_their_own_chain_and_share_the_story(self):
        children = {name for chain in self.BUNKER_COURSES.values() for name in chain}
        for root, chain in self.BUNKER_COURSES.items():
            with self.subTest(root=root):
                done = {root, "RUS_bunker_commission"}
                while True:
                    ready = {
                        name for name in children - done
                        if all(any(row.value in done for row in group.value)
                               for group in self.focuses[name] if group.key == "prerequisite")
                    }
                    if not ready:
                        break
                    done |= ready
                self.assertEqual(done - {root, "RUS_bunker_commission"}, set(chain))
                self.assertEqual(sum(int(scalar(self.focuses[name], "cost")) * 7 for name in chain), 77)
                world = self.world()
                world.focuses = done
                world.events.clear()
                world.execute(block(self.focuses[chain[-1]], "completion_reward"))
                self.assertEqual(world.events, ["ADISCORD_rus_campaign.25"])
                for name in chain:
                    self.assertTrue(world.matches(block(self.focuses[name], "available")), name)
                    for field in ("owner", "controller"):
                        setattr(world, field, False)
                        self.assertFalse(world.matches(block(self.focuses[name], "available")), (name, field))
                        setattr(world, field, True)
        plan = block(parse(f"common/ai_strategy_plans/{BASE}_plans.txt"), "ADISCORD_vorkerland_rus_last_empire_plan")
        order = {row.value for row in block(plan, "ai_national_focuses")}
        self.assertEqual(order & children, set(self.BUNKER_COURSES["RUS_bunker_open_city"]))

    def test_bunker_course_closed_cycle_feeds_five_rooms_and_turbine_adds_capacity(self):
        world = self.world()
        for layer, room in enumerate((1, 2, 1, 2, 2), 1):
            world.variables[f"RUS_bunker_layer_{layer}"] = room
        world.variables["RUS_bunker_generators"] = 3
        world.run("RUS_bunker_refresh")
        self.assertEqual(world.value("RUS_bunker_food_balance"), -3)
        world.execute(block(self.focuses["RUS_bunker_open_city"], "completion_reward"))
        self.assertEqual(world.value("RUS_bunker_food_balance"), -2)
        world.execute(block(self.focuses["RUS_bunker_closed_cycle"], "completion_reward"))
        self.assertEqual(world.value("RUS_bunker_food_balance"), 0)
        stock = world.value("RUS_bunker_food")
        world.run("RUS_bunker_weekly_supply")
        self.assertEqual(world.value("RUS_bunker_food"), stock)
        power = world.value("RUS_bunker_free_power")
        world.execute(block(self.focuses["RUS_bunker_sealed_throne"], "completion_reward"))
        world.execute(block(self.focuses["RUS_bunker_reserve_turbine"], "completion_reward"))
        world.run("RUS_bunker_refresh")
        self.assertEqual(world.value("RUS_bunker_free_power"), power + 4)

    def test_bunker_course_workshop_rechecks_ownership_before_building(self):
        for owner, controller in ((True, True), (False, True), (True, False)):
            with self.subTest(owner=owner, controller=controller):
                world = self.world()
                world.owner, world.controller = owner, controller
                before = (world.buildings["industrial_complex"], world.building_slots, world.dirty)
                world.execute(block(self.focuses["RUS_bunker_cold_stores"], "completion_reward"))
                built = 1 if owner and controller else 0
                self.assertEqual(world.buildings["industrial_complex"], before[0] + built)
                self.assertEqual(world.building_slots, before[1] + built)
                self.assertEqual(world.dirty, before[2] + built)

    def test_bunker_course_college_applies_preview_and_survives_loss_without_stacking(self):
        world = self.world()
        world.focuses.discard("RUS_bunker_systems_college")
        world.variables["RUS_bunker_layer_4"] = 2
        world.run("RUS_bunker_refresh")
        before = world.value("RUS_bunker_research_speed_factor")
        reward = block(self.focuses["RUS_bunker_systems_college"], "completion_reward")
        world.execute(reward)
        delta = world.value("RUS_bunker_research_speed_factor") - before
        self.assertAlmostEqual(delta, .05)
        preview = block(self.ideas["RUS_bunker_systems_college_delta"], "modifier")
        self.assertAlmostEqual(float(scalar(preview, "research_speed_factor")), delta)
        self.assertNotIn("RUS_bunker_systems_college_delta", world.ideas)
        bonus = block(reward, "add_tech_bonus")
        self.assertEqual((scalar(bonus, "category"), scalar(bonus, "uses"), scalar(bonus, "bonus")), ("industry", "2", "0.75"))
        world = deepcopy(world)
        for field in ("owner", "controller", "subject"):
            with self.subTest(loss=field):
                setattr(world, field, field == "subject")
                world.run("RUS_bunker_refresh")
                self.assertNotIn("RUS_bunker_complex", world.modifiers)
                setattr(world, field, field != "subject")
                world.run("RUS_bunker_refresh")
                world.run("RUS_bunker_refresh")
                self.assertIn("RUS_bunker_complex", world.modifiers)
                self.assertAlmostEqual(world.value("RUS_bunker_research_speed_factor"), before + .05)
        world.run("RUS_campaign_shutdown")
        self.assertNotIn("RUS_bunker_complex", world.modifiers)

    def test_food_pulse_is_tag_scoped_and_stocks_are_not_gui_mutations(self):
        on = block(parse("common/on_actions/01_ADISCORD_vorkerland_collapse_on_actions.txt"), "on_actions")
        weekly = list(walk(block(on, "on_weekly_RUS")))
        self.assertIn("RUS_bunker_weekly_supply", [entry.key for entry in weekly])
        self.assertFalse(any(entry.key in ("every_country", "every_possible_country") for entry in weekly))
        actions = block(block(block(parse("common/scripted_guis/ADISCORD_RUS_scripted_gui.txt"), "scripted_gui"), "ADISCORD_RUS_bunker_panel"), "effects")
        for layer in range(1, 6):
            click = list(walk(block(actions, f"RUS_bunker_floor_{layer}_click")))
            self.assertEqual([entry.key for entry in click if entry.key not in ("var", "value")], ["set_variable", "clr_country_flag"])
            self.assertEqual(scalar(block(actions, f"RUS_bunker_floor_{layer}_click"), "clr_country_flag"), "RUS_bunker_service_tab")
            self.assertEqual(scalar(click[0].value, "var"), "RUS_bunker_selected_layer")

    def test_gui_affordability_matches_native_decisions(self):
        for name in self.projects:
            trigger = name + "_ui_available"
            if trigger not in self.triggers:
                continue
            for layer_value, depth, pp, cash, equipment, power, busy in product((0, 1), (0, 5), (0, 25), (0, 500), (0, 50), (0, 14), (False, True)):
                world = self.world()
                world.variables["RUS_bunker_depth"] = depth
                world.variables["ADISCORD_economy_treasury"] = cash
                world.variables["RUS_bunker_free_power"] = power
                world.pp = pp
                world.equipment["support_equipment"] = equipment
                for layer in range(1, 6):
                    world.variables[f"RUS_bunker_layer_{layer}"] = layer_value
                if busy:
                    world.variables["RUS_bunker_project"] = 1
                native = all(world.matches(block(self.decisions[name], gate)) for gate in ("visible", "available", "custom_cost_trigger"))
                self.assertEqual(world.matches(self.triggers[trigger]), native, (name, layer_value, depth, pp, cash, equipment, power, busy))

    def test_order_text_rows_follow_the_selected_layer_without_overlap(self):
        window = next(row.value for row in block(parse("interface/ADISCORD_RUS.gui"), "guiTypes") if row.key == "containerWindowType" and scalar(row.value, "name") == "ADISCORD_RUS_bunker_window")
        widgets = {scalar(child.value, "name"): child.value for child in window if child.key in ("buttonType", "instantTextBoxType")}
        panel = block(block(parse("common/scripted_guis/ADISCORD_RUS_scripted_gui.txt"), "scripted_gui"), "ADISCORD_RUS_bunker_panel")
        visibility = block(panel, "triggers")
        actions = (("guard", 1), ("shelter", 1), ("water", 2), ("signals", 2), ("workshop", 3), ("granary", 3), ("clinic", 4), ("laboratory", 4), ("archive", 5), ("command", 5))
        actions += tuple((f"upgrade_{layer}", layer) for layer in range(1, 6))
        world = self.world()
        world.variables["RUS_bunker_depth"] = 5
        for action, layer in actions:
            name = f"RUS_bunker_{action}_button"
            button = widgets[name]
            top = float(scalar(block(button, "position"), "y"))
            bottom = top + float(scalar(block(button, "size"), "y"))
            previous_bottom = top
            for suffix in ("label", "benefit", "status"):
                row_name = f"{name}_{suffix}"
                self.assertTrue(row_name in widgets, row_name)
                row = widgets[row_name]
                y = float(scalar(block(row, "position"), "y"))
                end = y + float(scalar(row, "maxHeight"))
                self.assertGreaterEqual(y, previous_bottom, row_name)
                self.assertLessEqual(end, bottom, row_name)
                previous_bottom = end
                for selected in range(1, 6):
                    world.variables["RUS_bunker_selected_layer"] = selected
                    for fitted in (0, 1):
                        world.variables[f"RUS_bunker_layer_{layer}"] = fitted
                        expected = selected == layer and bool(fitted) == action.startswith("upgrade_")
                        self.assertEqual(world.matches(block(visibility, row_name + "_visible")), expected, row_name)

    def test_bunker_decision_rows_follow_navigation_without_hiding_active_orders(self):
        world = self.world()
        world.ai = False
        world.variables["RUS_bunker_depth"] = 5
        world.variables["RUS_bunker_selected_layer"] = 3
        self.assertTrue(world.matches(block(self.decisions["RUS_bunker_workshop"], "visible")))
        self.assertFalse(world.matches(block(self.decisions["RUS_bunker_guard"], "visible")))
        self.assertFalse(world.matches(block(self.decisions["RUS_bunker_generator"], "visible")))
        world.active.add("RUS_bunker_workshop")
        world.flags.add("RUS_bunker_service_tab")
        self.assertTrue(world.matches(block(self.decisions["RUS_bunker_workshop"], "visible")))
        self.assertTrue(world.matches(block(self.decisions["RUS_bunker_generator"], "visible")))
        self.assertFalse(world.matches(block(self.decisions["RUS_bunker_clinic"], "visible")))
        world.ai = True
        self.assertTrue(world.matches(block(self.decisions["RUS_bunker_clinic"], "visible")))

    def test_bunker_panel_uses_registered_fonts(self):
        registered = {scalar(row.value, "name") for path in ("interface/core.gfx", "interface/ADISCORD_RUS.gfx") for row in walk(parse(path)) if row.key == "bitmapfont"}
        window = next(row.value for row in block(parse("interface/ADISCORD_RUS.gui"), "guiTypes") if row.key == "containerWindowType" and scalar(row.value, "name") == "ADISCORD_RUS_bunker_window")
        for widget in window:
            if widget.key == "instantTextBoxType":
                self.assertIn(scalar(widget.value, "font"), registered, scalar(widget.value, "name"))

    def test_floor_status_distinguishes_paid_work_from_empty_or_installed(self):
        world = self.world()
        self.assertEqual(self.bunker_text(world, "GetRUSBunkerFloorStatus1"), "RUS_bunker_floor_state_1")
        world.begin("RUS_bunker_excavate")
        self.assertEqual(self.bunker_text(world, "GetRUSBunkerFloorStatus1"), "RUS_bunker_floor_excavating")
        self.assertEqual(self.bunker_text(world, "GetRUSBunkerFloorStatus2"), "RUS_bunker_floor_state_2")
        world.finish("RUS_bunker_excavate")
        world.begin("RUS_bunker_guard")
        self.assertEqual(self.bunker_text(world, "GetRUSBunkerFloorStatus1"), "RUS_bunker_floor_fitting")
        self.assertEqual(self.bunker_text(world, "GetRUSBunkerOrder11"), "RUS_bunker_order_paid")
        self.assertEqual(self.bunker_text(world, "GetRUSBunkerRoomguard"), "RUS_bunker_in_progress")
        self.assertEqual(self.bunker_text(world, "GetRUSBunkerOrder12"), "RUS_bunker_shelter_order_price")
        world.variables["RUS_bunker_selected_layer"] = 3
        self.assertEqual(self.bunker_text(world, "GetRUSBunkerOrder11"), "RUS_bunker_order_paid")
        world.finish("RUS_bunker_guard")
        self.assertEqual(self.bunker_text(world, "GetRUSBunkerFloorStatus1"), "RUS_bunker_floor_state_1")
        world.begin("RUS_bunker_upgrade_1")
        self.assertEqual(self.bunker_text(world, "GetRUSBunkerFloorStatus1"), "RUS_bunker_floor_upgrading")
        self.assertEqual(self.bunker_text(world, "GetRUSBunkerOrder40"), "RUS_bunker_order_paid")
        world.finish("RUS_bunker_upgrade_1")
        self.assertEqual(self.bunker_text(world, "GetRUSBunkerOrder40"), "RUS_bunker_order_completed")

    def test_bunker_navigation_preserves_a_paid_order_and_all_floor_images(self):
        panel = block(block(parse("common/scripted_guis/ADISCORD_RUS_scripted_gui.txt"), "scripted_gui"), "ADISCORD_RUS_bunker_panel")
        actions = block(panel, "effects")
        visibility = block(panel, "triggers")
        window = next(row.value for row in block(parse("interface/ADISCORD_RUS.gui"), "guiTypes") if row.key == "containerWindowType" and scalar(row.value, "name") == "ADISCORD_RUS_bunker_window")
        for widget in walk(window):
            if widget.key == "containerWindowType":
                self.assertNotIn("alwaystransparent", {row.key for row in widget.value})
        pictures = [row.value for row in walk(window) if row.key == "iconType" and "floor_" in scalar(row.value, "name") and scalar(row.value, "name").endswith("_picture")]
        self.assertEqual(len(pictures), 5)
        self.assertFalse(any("selected_picture" in scalar(row.value, "name") for row in window if row.key == "iconType"))
        self.assertEqual(len({scalar(picture, "scale") for picture in pictures}), 1)
        world = self.world()
        world.variables["RUS_bunker_depth"] = 3
        world.run("RUS_bunker_workshop_start")
        receipt = {key: value for key, value in world.variables.items() if "escrow" in key or key == "RUS_bunker_project"}
        balances = (world.pp, dict(world.equipment), world.value("ADISCORD_economy_treasury"))
        for tab in ("service", "floors"):
            world.execute(block(actions, f"RUS_bunker_tab_{tab}_click"))
            for layer in range(1, 6):
                self.assertEqual(world.matches(block(visibility, f"RUS_bunker_floor_{layer}_viewport_visible")), tab == "floors")
            for layer in range(1, 6):
                world.execute(block(actions, f"RUS_bunker_floor_{layer}_click"))
                for picture in pictures:
                    name = scalar(picture, "name")
                    gate = block(visibility, name + "_visible")
                    self.assertTrue(world.matches(gate), (tab, layer, name))
                self.assertEqual(receipt, {key: value for key, value in world.variables.items() if "escrow" in key or key == "RUS_bunker_project"})
                self.assertEqual(balances, (world.pp, world.equipment, world.value("ADISCORD_economy_treasury")))

    def test_panel_pictures_and_widgets_fit_declared_bounds(self):
        window = next(row.value for row in block(parse("interface/ADISCORD_RUS.gui"), "guiTypes") if row.key == "containerWindowType" and scalar(row.value, "name") == "ADISCORD_RUS_bunker_window")
        dimensions = block(window, "size")
        width = float(scalar(dimensions, "width"))
        height = float(scalar(dimensions, "height"))
        pictures = []

        def check_children(children, parent_width, parent_height, clipped=False):
            for child in children:
                if child.key not in ("buttonType", "iconType", "instantTextBoxType", "containerWindowType"):
                    continue
                name = scalar(child.value, "name")
                position = block(child.value, "position")
                x = float(scalar(position, "x"))
                y = float(scalar(position, "y"))
                if child.key == "iconType":
                    sprite = scalar(child.value, "spriteType")
                    scale = float(next((row.value for row in child.value if row.key == "scale"), 1))
                    with Image.open(ROOT / f"gfx/interface/ADISCORD_RUS/{sprite.removeprefix('GFX_RUS_')}.dds") as picture:
                        w, h = picture.width * scale, picture.height * scale
                    if name.endswith("_picture"):
                        self.assertRegex(sprite, r"^GFX_RUS_bunker_layer_[1-5]$")
                        pictures.append(name)
                elif child.key in ("buttonType", "containerWindowType"):
                    size = block(child.value, "size")
                    horizontal, vertical = ("x", "y") if child.key == "buttonType" else ("width", "height")
                    w, h = float(scalar(size, horizontal)), float(scalar(size, vertical))
                    if child.key == "containerWindowType":
                        self.assertEqual(scalar(child.value, "clipping"), "yes")
                        check_children(child.value, w, h, clipped=True)
                else:
                    w = float(scalar(child.value, "maxWidth"))
                    h = float(scalar(child.value, "maxHeight"))
                self.assertGreaterEqual(x, 0, name)
                self.assertLessEqual(x + w, parent_width, name)
                if not clipped:
                    self.assertGreaterEqual(y, 0, name)
                    self.assertLessEqual(y + h, parent_height, name)
                else:
                    self.assertLessEqual(y, 0, name)
                    self.assertGreaterEqual(y + h, parent_height, name)

        check_children(window, width, height)
        self.assertEqual(len(pictures), 5)
        panel = block(block(parse("common/scripted_guis/ADISCORD_RUS_scripted_gui.txt"), "scripted_gui"), "ADISCORD_RUS_bunker_panel")
        visibility = block(panel, "triggers")
        world = self.world()
        for selected in range(1, 6):
            world.variables["RUS_bunker_selected_layer"] = selected
            shown = [layer for layer in range(1, 6) if world.matches(block(visibility, f"RUS_bunker_floor_{layer}_picture_visible"))]
            self.assertEqual(shown, [1, 2, 3, 4, 5])

    def test_gui_tooltips_are_leaf_strings_and_buttons_use_scalable_sprites(self):
        gui = parse("interface/ADISCORD_RUS.gui")
        tooltip_keys = {entry.value.strip('"') for entry in walk(gui) if entry.key == "pdx_tooltip"}
        functions = {
            scalar(row.value, "name"): row.value
            for row in parse("common/scripted_localisation/ADISCORD_RUS_scripted_loc.txt")
            if row.key == "defined_text"
        }
        for language in ("russian", "english"):
            source = read(f"localisation/{language}/{BASE}_l_{language}.yml")
            loc = dict(re.findall(r'^\s+([A-Za-z0-9_.]+):(?:\d+)?\s+"(.*)"\s*$', source, re.M))
            keys = set(tooltip_keys)
            seen = set()
            while keys:
                key = keys.pop()
                if key in seen:
                    continue
                seen.add(key)
                self.assertIn(key, loc, (language, key))
                text = loc[key]
                self.assertNotIn("$", text, (language, key))
                for name in re.findall(r"\[(GetRUS\w+)\]", text):
                    self.assertIn(name, functions)
                    keys.update(entry.value for entry in walk(functions[name]) if entry.key == "localization_key")
            for faction in ("scientists", "black_army"):
                self.assertIn(loc["RUS_faction_support_effects"], loc[f"RUS_favours_{faction}_support_tt"])
        sprites = block(parse("interface/ADISCORD_RUS.gfx"), "spriteTypes")
        buttons = [row for row in sprites if isinstance(row.value, list) and scalar(row.value, "name").strip('"') == "GFX_RUS_bunker_button"]
        self.assertEqual(len(buttons), 1)
        self.assertEqual(buttons[0].key, "corneredTileSpriteType")
        self.assertNotIn("GFX_SHL_furnace_button", read("interface/ADISCORD_RUS.gui"))

    def suspicion_world(self, value=None):
        world = self.world()
        world.decisions = {**self.decisions, **self.balance, **self.suspicion}
        world.focuses = {"RUS_seat_the_khan_chancery"}
        world.execute(block(self.focuses["RUS_seat_the_khan_chancery"], "completion_reward"))
        world.run("RUS_suspicion_begin")
        if value is not None:
            world.variables["RUS_suspicion"] = value
        world.events.clear()
        return world

    def test_suspicion_opens_once_and_proclamation_closes_it(self):
        world = self.suspicion_world()
        self.assertEqual(world.value("RUS_suspicion"), 10)
        world.variables["RUS_suspicion"] = 40
        world.run("RUS_suspicion_begin")
        self.assertEqual(world.value("RUS_suspicion"), 40)
        self.assertTrue(world.matches(self.triggers["RUS_suspicion_active"]))
        world.flags.add("ADISCORD_vorkerland_rus_last_empire_proclaimed")
        self.assertFalse(world.matches(self.triggers["RUS_suspicion_active"]))
        world.run("RUS_suspicion_monthly")
        self.assertEqual(world.value("RUS_suspicion"), 40)
        self.assertFalse(any(name.startswith("RUS_suspicion_") for name in self.balance))
        for name, rows in self.suspicion.items():
            if name.startswith(("RUS_suspicion_", "RUS_shadow_")):
                self.assertFalse(world.matches(block(rows, "visible")), name)
        proclaimed = self.world()
        proclaimed.flags.add("ADISCORD_vorkerland_rus_last_empire_proclaimed")
        proclaimed.run("RUS_suspicion_begin")
        self.assertNotIn("RUS_suspicion", proclaimed.variables)

    def test_monthly_suspicion_follows_black_army_and_cover_focuses(self):
        cases = (
            (0.0, (), 3),
            (0.3, (), 5),
            (0.7, (), 7),
            (0.7, ("RUS_parallel_public_addresses",), 6),
            (0.0, ("RUS_parallel_public_addresses", "RUS_bunker_sealed_throne"), 2),
            (0.0, ("RUS_parallel_public_addresses", "RUS_bunker_sealed_throne", "RUS_bunker_commission"), 1),
            (0.0, ("RUS_parallel_public_addresses", "RUS_bunker_sealed_throne", "RUS_bunker_commission", "RUS_foreign_press_bureau"), 0),
        )
        for bop, focuses, growth in cases:
            with self.subTest(bop=bop, focuses=focuses):
                world = self.suspicion_world(20)
                world.bop = bop
                world.focuses.update(focuses)
                world.run("RUS_suspicion_monthly")
                self.assertEqual(world.value("RUS_suspicion"), 20 + growth)
        world = self.suspicion_world(99)
        world.bop = 0.7
        world.war = True
        world.run("RUS_suspicion_monthly")
        self.assertEqual(world.value("RUS_suspicion"), 100)

    def test_suspicion_warnings_fire_once_per_tier(self):
        world = self.suspicion_world(48)
        world.run("RUS_suspicion_monthly")
        self.assertEqual(world.events, ["ADISCORD_rus_crisis.17"])
        world.run("RUS_suspicion_monthly")
        self.assertEqual(world.events, ["ADISCORD_rus_crisis.17"])
        world.variables["RUS_suspicion"] = 74
        world.run("RUS_suspicion_monthly")
        self.assertEqual(world.events, ["ADISCORD_rus_crisis.17", "ADISCORD_rus_crisis.17"])
        self.assertEqual(world.value("RUS_suspicion_warning"), 2)
        skipped = self.suspicion_world(45)
        skipped.temporary["RUS_suspicion_delta"] = 40
        skipped.run("RUS_suspicion_add")
        self.assertEqual(skipped.events, ["ADISCORD_rus_crisis.17"])
        skipped.temporary["RUS_suspicion_delta"] = -60
        skipped.run("RUS_suspicion_add")
        self.assertEqual(skipped.value("RUS_suspicion"), 25)
        skipped.temporary["RUS_suspicion_delta"] = 30
        skipped.run("RUS_suspicion_add")
        self.assertEqual(skipped.events, ["ADISCORD_rus_crisis.17"])

    def test_suspicion_relief_decisions_debit_once_and_shift_the_balance(self):
        specs = {
            "RUS_suspicion_energy_cover": (0, 60, 0, 0, -15, -0.05, None),
            "RUS_suspicion_disperse_musters": (0, 0, 500, 15, -15, 0.05, None),
            "RUS_suspicion_envoys": (30, 85, 0, 0, -25, 0.0, None),
            "RUS_suspicion_ration_aid": (0, 0, 0, 30, -10, 0.0, None),
            "RUS_suspicion_border_bribes": (0, 200, 0, 0, -20, 0.0, None),
            "RUS_suspicion_press_tour": (0, 50, 0, 0, -15, -0.05, "RUS_foreign_press_bureau"),
            "RUS_suspicion_reactor_camouflage": (0, 50, 0, 40, -20, 0.05, "RUS_quiet_perimeter"),
            "RUS_suspicion_border_commission": (0, 65, 0, 20, -20, 0.0, "RUS_good_neighbour_charter"),
        }
        for name, (pp, cash, men, food, relief, shift, focus) in specs.items():
            with self.subTest(name=name):
                rows = self.suspicion[name]
                self.assertEqual(scalar(rows, "cost"), "0")
                for suffix in ("", "_desc", "_cost", "_cost_blocked", "_cost_tooltip"):
                    self.assertIn(f"{name}{suffix}", self.loc)
                cost = self.loc[f"{name}_cost"]
                prices = (
                    (pp, "political_power_texticon"),
                    (cash, "ADISCORD_economy_treasury_texticon"),
                    (men, "manpower_texticon"),
                    (food, "supply_texticon"),
                )
                for amount, icon in prices:
                    if amount:
                        self.assertIn(f"§Y{amount}§! £{icon}", cost)
                    else:
                        self.assertNotIn(f"£{icon}", cost)
                world = self.suspicion_world(50)
                if focus:
                    self.assertFalse(world.matches(block(rows, "visible")))
                    world.focuses.add(focus)
                self.assertTrue(world.matches(block(rows, "visible")))
                world.war = False
                world.manpower = 5000.0
                world.variables["ADISCORD_economy_treasury"] = 1000
                world.variables["RUS_bunker_food"] = 80
                before = (world.pp, 1000, world.manpower, 80, world.bop)
                world.begin(name)
                self.assertEqual(world.pp, before[0] - pp)
                self.assertEqual(world.value("ADISCORD_economy_treasury"), before[1] - cash)
                self.assertEqual(world.manpower, before[2] - men)
                self.assertEqual(world.value("RUS_bunker_food"), before[3] - food)
                self.assertAlmostEqual(world.bop, before[4] + shift)
                self.assertEqual(world.value("RUS_suspicion"), 50 + relief)
                poor = self.suspicion_world(50)
                poor.pp = pp - 1
                poor.variables["ADISCORD_economy_treasury"] = cash - 1
                poor.variables["RUS_bunker_food"] = food - 1
                self.assertFalse(poor.matches(block(rows, "custom_cost_trigger")))
                clean = self.suspicion_world(0)
                self.assertFalse(clean.matches(block(rows, "available")))
                effect = block(rows, "complete_effect")
                previews = [row.value for row in effect if row.key == "custom_effect_tooltip"]
                self.assertEqual(previews[0], f"RUS_suspicion_relief_{-relief}_tt")
                self.assertIn(previews[0], self.loc)
                gate = block(block(block(effect, "hidden_effect"), "if"), "limit")
                self.assertIn(f"{name}_affordable", {row.key for row in gate})

    def test_noisy_actions_raise_suspicion_by_their_announced_amounts(self):
        amounts = {
            "RUS_reactor_sortie_begin": ("RUS_reactor_sortie", 4),
            "RUS_reactor_works_begin": ("RUS_restore_reactor_works", 6),
            "RUS_lab_reactor_alloys_start": ("RUS_lab_reactor_alloys", 8),
            "RUS_lab_zeppelin_start": ("RUS_lab_zeppelin", 12),
            "ADISCORD_vorkerland_rus_start_dirty_campaign": ("RUS_campaign_sla", 10),
        }
        decisions = {**self.belt, **self.labs}
        campaign = block(parse(f"common/decisions/{BASE}_decisions.txt"), "ADISCORD_vorkerland_rus_dirty_campaign_category")
        decisions.update({e.key: e.value for e in campaign})
        for effect, (decision, amount) in amounts.items():
            with self.subTest(effect=effect):
                deltas = [
                    scalar(row.value, "value") for row in walk(self.effects[effect])
                    if row.key == "set_temp_variable" and scalar(row.value, "var") == "RUS_suspicion_delta"
                ]
                self.assertEqual(deltas, [str(amount)])
                gates = [row.value for row in block(decisions[decision], "complete_effect") if row.key == "if"]
                self.assertEqual(scalar(gates[0], "custom_effect_tooltip"), f"RUS_suspicion_gain_{amount}_tt")
                self.assertIn(f"RUS_suspicion_gain_{amount}_tt", self.loc)
        world = self.world()
        world.temporary["RUS_suspicion_delta"] = 10
        world.run("RUS_suspicion_add")
        self.assertNotIn("RUS_suspicion", world.variables)

    def test_suspicion_status_and_relief_focuses_are_explained(self):
        for focus in ("RUS_parallel_public_addresses", "RUS_bunker_commission", "RUS_foreign_press_bureau"):
            rewards = [row.value for row in walk(block(self.focuses[focus], "completion_reward")) if row.key == "custom_effect_tooltip"]
            self.assertIn("RUS_suspicion_focus_relief_tt", rewards)
        unlocks = {
            "RUS_foreign_press_bureau": "RUS_suspicion_press_tour",
            "RUS_quiet_perimeter": "RUS_suspicion_reactor_camouflage",
            "RUS_good_neighbour_charter": "RUS_suspicion_border_commission",
        }
        for focus, decision in unlocks.items():
            reward = block(self.focuses[focus], "completion_reward")
            self.assertEqual(scalar(reward, "unlock_decision_tooltip"), decision)
            self.assertIn(decision, self.suspicion)
            self.assertIn(focus, self.loc)
            self.assertIn(f"{focus}_desc", self.loc)
            gate = [row.key for row in walk(block(self.focuses[focus], "available"))]
            self.assertIn("RUS_suspicion_active", gate, focus)
            self.assertEqual(scalar(block(self.focuses[focus], "bypass"), "has_country_flag"), "ADISCORD_vorkerland_rus_last_empire_proclaimed")
        self.assertIn("RUS_suspicion_open_tt", self.loc)
        self.assertIn("[GetRUSSuspicionStatus]", self.loc["RUS_state_balance_category_desc"])
        self.assertIn("decision_category = RUS_state_balance_measures_category", read("common/bop/RUS.txt"))
        for key in ("RUS_suspicion_status", "RUS_suspicion_opens_tt", "RUS_suspicion_relief_15_tt", "RUS_suspicion_relief_25_tt"):
            self.assertIn(key, self.loc)
        names = {row.value for row in walk(parse("common/scripted_localisation/ADISCORD_RUS_scripted_loc.txt")) if row.key == "name"}
        for name in re.findall(r"\[(GetRUSSuspicion\w+)\]", self.loc["RUS_suspicion_status"] + "[GetRUSSuspicionStatus]"):
            self.assertIn(name, names)

    def test_shadow_deals_trade_suspicion_for_material_results(self):
        specs = {
            "RUS_shadow_rifles": (0, 35, 0, 8, 92),
            "RUS_shadow_designs": (15, 0, 0, 12, 88),
            "RUS_shadow_engineers": (0, 0, 25, 10, 90),
        }
        for name, (pp, cash, food, noise, ceiling) in specs.items():
            with self.subTest(name=name):
                rows = self.suspicion[name]
                for suffix in ("", "_desc", "_cost", "_cost_blocked", "_cost_tooltip"):
                    self.assertIn(f"{name}{suffix}", self.loc)
                previews = [row.value for row in block(rows, "complete_effect") if row.key == "custom_effect_tooltip"]
                self.assertEqual(previews[0], f"RUS_suspicion_gain_{noise}_tt")
                world = self.suspicion_world(ceiling - 0.01)
                world.pp = 100
                world.variables["ADISCORD_economy_treasury"] = 100
                world.variables["RUS_bunker_food"] = 80
                world.variables["ADISCORD_economic_development_progress"] = 10
                rifles = world.equipment.get("infantry_equipment", 0)
                world.begin(name)
                self.assertAlmostEqual(world.value("RUS_suspicion"), ceiling - 0.01 + noise)
                self.assertLess(world.value("RUS_suspicion"), 100)
                self.assertEqual(world.pp, 100 - pp)
                self.assertEqual(world.value("ADISCORD_economy_treasury"), 100 - cash)
                self.assertEqual(world.value("RUS_bunker_food"), 80 - food)
                if name == "RUS_shadow_rifles":
                    self.assertEqual(world.equipment["infantry_equipment"] - rifles, 10000)
                elif name == "RUS_shadow_designs":
                    self.assertEqual(world.tech_bonuses, ["RUS_stolen_designs"])
                    self.assertIn("RUS_stolen_designs", self.loc)
                else:
                    self.assertEqual(world.value("ADISCORD_economic_development_progress"), 30)
                loud = self.suspicion_world(ceiling)
                self.assertFalse(loud.matches(block(rows, "available")))

    def test_war_spoils_choice_trades_half_the_haul_for_quiet_and_stability(self):
        event = next(
            row.value for row in parse("events/ADISCORD_RUS_events.txt")
            if row.key == "country_event" and scalar(row.value, "id") == "ADISCORD_rus_crisis.30"
        )
        results = []
        for option in [row.value for row in event if row.key == "option"]:
            world = self.suspicion_world(40)
            world.variables["RUS_bunker_food"] = 10
            world.manpower = 0.0
            cash = world.value("ADISCORD_economy_treasury")
            rifles = world.equipment.get("infantry_equipment", 0)
            stability = world.stability
            world.execute([row for row in option if row.key not in ("name", "ai_chance")])
            results.append((
                world.value("ADISCORD_economy_treasury") - cash,
                world.equipment["infantry_equipment"] - rifles,
                world.manpower,
                world.value("RUS_bunker_food") - 10,
                world.value("RUS_suspicion") - 40,
                round(world.stability - stability, 2),
            ))
        self.assertEqual(results, [(100, 27000, 1500, 30, 4, 0), (50, 13500, 750, 15, 0, 0.03)])
        settle = self.effects["ADISCORD_vorkerland_rus_settle_dirty_target"]
        fired = [row for row in walk(settle) if row.key == "country_event" and scalar(row.value, "id") == "ADISCORD_rus_crisis.30"]
        self.assertEqual(len(fired), 6)
        registry = json.loads(read("tools/data/adiscord_event_ids.json"))["events"]
        self.assertEqual(sum(row["id"] == "ADISCORD_rus_crisis.30" for row in registry), 1)
        for key in ("t", "d", "a", "b"):
            self.assertIn(f"ADISCORD_rus_crisis.30.{key}", self.loc)

    def test_energy_contracts_reserve_power_pay_monthly_and_cut_on_war(self):
        rows = self.suspicion["RUS_energy_contract"]
        self.assertEqual([row.value for row in block(rows, "targets")], ["SLA", "RZA", "MLR", "ERT", "IRT", "SCA"])
        self.assertIn("RUS_bunker_power_school", [row.value for row in walk(block(rows, "target_root_trigger"))])
        for key in ("RUS_energy_contract", "RUS_energy_contract_cost", "RUS_energy_contract_cost_blocked", "RUS_energy_contract_cost_tooltip", "RUS_energy_contract_result_tt", "RUS_energy_contract_end", "RUS_power_cut"):
            self.assertIn(key, self.loc)
        incomes = []
        for contracts in (0, 2):
            world = self.world()
            world.variables["RUS_energy_contracts"] = contracts
            world.run("RUS_bunker_refresh")
            incomes.append((world.value("RUS_bunker_used_power"), world.value("RUS_bunker_income")))
        self.assertEqual((incomes[1][0] - incomes[0][0], incomes[1][1] - incomes[0][1]), (2, 16))
        world = self.suspicion_world(20)
        world.variables["RUS_energy_contracts"] = 2
        world.run("RUS_suspicion_monthly")
        self.assertEqual(world.value("RUS_suspicion"), 21)
        cut = self.effects["RUS_energy_contract_cut"]
        modifier = next(row.value for row in walk(cut) if row.key == "add_dynamic_modifier")
        self.assertEqual((scalar(modifier, "modifier"), scalar(modifier, "days")), ("RUS_power_cut", "90"))
        self.assertIn("RUS_power_cut", [row.key for row in parse("common/dynamic_modifiers/ADISCORD_dynamic_modifiers_RUS.txt")])
        hooks = block(parse("common/on_actions/01_ADISCORD_vorkerland_collapse_on_actions.txt"), "on_actions")
        self.assertIn("RUS_energy_contracts_monthly", [row.key for row in walk(block(hooks, "on_monthly_RUS"))])
        self.assertIn("RUS_energy_contract_cut", [row.key for row in walk(block(hooks, "on_war_relation_added"))])
        self.assertIn("[GetRUSSuspicionEnergyRelief]", self.loc["RUS_suspicion_status"])

    def test_coalition_inspection_answers_have_distinct_prices_and_results(self):
        event = next(
            row.value for row in parse("events/ADISCORD_RUS_events.txt")
            if row.key == "country_event" and scalar(row.value, "id") == "ADISCORD_rus_crisis.17"
        )
        options = {scalar(row.value, "name"): row.value for row in event if row.key == "option"}
        self.assertEqual(list(options), [f"ADISCORD_rus_crisis.17.{name}" for name in ("truth", "hide", "bribe", "expel")])
        self.assertFalse(any(row.key == "trigger" for row in options["ADISCORD_rus_crisis.17.truth"]), "The timeout answer must stay free")
        expected = {
            "truth": (-8, 0, 0, 0, -0.10),
            "hide": (-12, 0, 20, 500, 0.0),
            "bribe": (-15, 65, 0, 0, 0.0),
            "expel": (10, 0, 0, 0, 0.10),
        }
        for suffix, (noise, cash, food, men, shift) in expected.items():
            with self.subTest(answer=suffix):
                name = f"ADISCORD_rus_crisis.17.{suffix}"
                for key in (name, "ADISCORD_rus_crisis.17.rumours.d", "ADISCORD_rus_crisis.17.observers.d"):
                    self.assertIn(key, self.loc)
                rows = options[name]
                world = self.suspicion_world(60)
                world.bop = 0.0
                world.manpower = 2000.0
                world.variables["ADISCORD_economy_treasury"] = 100
                world.variables["RUS_bunker_food"] = 60
                gate = next((row.value for row in rows if row.key == "trigger"), [])
                self.assertTrue(world.matches(gate))
                world.execute([row for row in rows if row.key not in ("name", "trigger", "ai_chance")])
                self.assertEqual(world.value("RUS_suspicion"), 60 + noise)
                self.assertEqual(world.value("ADISCORD_economy_treasury"), 100 - cash)
                self.assertEqual(world.value("RUS_bunker_food"), 60 - food)
                self.assertEqual(world.manpower, 2000 - men)
                self.assertAlmostEqual(world.bop, shift)
                if gate:
                    poor = self.suspicion_world(60)
                    poor.manpower = 499.0
                    poor.variables["ADISCORD_economy_treasury"] = 64.99
                    poor.variables["RUS_bunker_food"] = 19.99
                    self.assertFalse(poor.matches(gate))

    def test_aimaq_levy_is_fed_armed_and_limited_per_war(self):
        rows = self.programmes["RUS_aimaq_levy"]
        for suffix in ("", "_desc", "_cost", "_cost_blocked", "_cost_tooltip", "_room_tt", "_result_tt"):
            self.assertIn(f"RUS_aimaq_levy{suffix}", self.loc)
        world = self.world()
        world.decisions = {**world.decisions, **self.programmes}
        world.focuses.add("RUS_summon_the_aimaqs")
        world.war = False
        self.assertFalse(world.matches(block(rows, "visible")))
        world.war = True
        world.manpower = 1000.0
        world.variables["RUS_bunker_food"] = 80
        world.equipment["infantry_equipment"] = 6000
        divisions = world.divisions
        world.begin("RUS_aimaq_levy")
        self.assertEqual(world.divisions - divisions, 2)
        self.assertIn("Aimaq Levy", world.templates)
        self.assertEqual(world.value("RUS_bunker_food"), 50)
        self.assertEqual(world.equipment["infantry_equipment"], 3300)
        self.assertEqual(world.manpower, 1000)
        self.assertEqual(world.value("RUS_levy_raised"), 1)
        world.focuses.discard("RUS_district_courts")
        world.focuses.discard("RUS_bunker_mountain_garrison")
        world.variables["RUS_levy_raised"] = 3
        self.assertFalse(world.matches(block(rows, "available")))
        world.focuses.add("RUS_district_courts")
        self.assertTrue(world.matches(block(rows, "available")))
        world.variables["RUS_levy_raised"] = 5
        self.assertFalse(world.matches(block(rows, "available")))
        short = self.world()
        short.war = True
        short.variables["RUS_bunker_food"] = 80
        short.equipment["infantry_equipment"] = 2699.99
        self.assertFalse(short.matches(block(rows, "custom_cost_trigger")))
        disband = next(row.value for row in walk(self.effects["RUS_levies_monthly"]) if row.key == "delete_unit")
        self.assertEqual((scalar(disband, "division_template"), scalar(disband, "disband")), ("Aimaq Levy", "no"))
        hooks = block(parse("common/on_actions/01_ADISCORD_vorkerland_collapse_on_actions.txt"), "on_actions")
        self.assertIn("RUS_levies_monthly", [row.key for row in walk(block(hooks, "on_monthly_RUS"))])

    def test_refugee_arrivals_are_discarded_during_shared_cooldown(self):
        event = next(
            row.value for row in parse("events/ADISCORD_RUS_events.txt")
            if row.key == "country_event" and scalar(row.value, "id") == "ADISCORD_rus_crisis.31"
        )
        immediate = block(event, "immediate")
        cooldown = next(row.value for row in walk(immediate) if row.key == "set_country_flag")
        self.assertEqual(scalar(cooldown, "flag"), "RUS_refugees_cooldown")
        self.assertEqual(scalar(cooldown, "days"), "90")
        world = self.world()
        world.events.clear()
        self.assertTrue(world.matches(block(event, "trigger")))
        world.execute(immediate)
        for _ in range(6):
            self.assertFalse(world.matches(block(event, "trigger")))
        self.assertEqual(world.events, [])
        self.assertFalse(any(row.key == "country_event" for row in walk(event)))
        # Model expiry explicitly; native flag clocks require a campaign check.
        world.flags.remove("RUS_refugees_cooldown")
        self.assertTrue(world.matches(block(event, "trigger")))
        self.assertEqual(world.events, [])

    def test_refugees_and_winter_offer_priced_alternatives(self):
        events = {
            scalar(row.value, "id"): row.value for row in parse("events/ADISCORD_RUS_events.txt")
            if row.key == "country_event"
        }
        refugees = [row.value for row in events["ADISCORD_rus_crisis.31"] if row.key == "option"]
        self.assertFalse(any(row.key == "trigger" for row in refugees[0]))
        results = []
        for option in refugees:
            world = self.world()
            world.focuses.discard("RUS_bunker_refugee_quarters")
            world.manpower = 0.0
            world.variables.update({"RUS_bunker_food": 50, "ADISCORD_economy_treasury": 100, "ADISCORD_society_development_progress": 10})
            world.stability = 0.5
            stability = world.stability
            world.execute([row for row in option if row.key not in ("name", "trigger", "ai_chance")])
            results.append((
                world.manpower,
                50 - world.value("RUS_bunker_food"),
                100 - world.value("ADISCORD_economy_treasury"),
                world.value("ADISCORD_society_development_progress") - 10,
                round(world.stability - stability, 2),
            ))
        self.assertEqual(results, [(4000, 30, 0, 0, 0), (2000, 0, 35, 15, 0.02), (0, 0, 0, 0, -0.03)])
        settle = self.effects["ADISCORD_vorkerland_rus_settle_dirty_target"]
        delayed = [row.value for row in walk(settle) if row.key == "country_event" and scalar(row.value, "id") == "ADISCORD_rus_crisis.31"]
        self.assertEqual({scalar(row, "days") for row in delayed}, {"14"})
        self.assertEqual(len(delayed), 6)
        start = [row.value for row in walk(self.effects["RUS_campaign_initialize"]) if row.key == "country_event" and scalar(row.value, "id") == "ADISCORD_rus_crisis.32"]
        self.assertEqual([scalar(row, "days") for row in start], ["334"])
        world = self.world()
        world.focuses.discard("RUS_winter_granaries")
        world.run("RUS_bunker_refresh")
        use = world.value("RUS_bunker_food_use")
        world.events.clear()
        world.run("RUS_winter_begin")
        self.assertIn("RUS_winter", world.flags)
        self.assertEqual(world.value("RUS_bunker_food_use"), use + 3)
        self.assertEqual(world.events, ["ADISCORD_rus_crisis.32", "ADISCORD_rus_crisis.33"])
        world.focuses.add("RUS_winter_granaries")
        world.run("RUS_bunker_refresh")
        self.assertEqual(world.value("RUS_bunker_food_use"), use + 1)
        world.run("RUS_winter_end")
        self.assertNotIn("RUS_winter", world.flags)
        self.assertEqual(world.value("RUS_bunker_food_use"), use)
        registry = json.loads(read("tools/data/adiscord_event_ids.json"))["events"]
        for number in (31, 32, 33):
            self.assertEqual(sum(row["id"] == f"ADISCORD_rus_crisis.{number}" for row in registry), 1)
        for key in ("31.t", "31.d", "31.a", "31.b", "31.c", "32.t", "32.d", "32.a", "32.b", "32.c"):
            self.assertIn(f"ADISCORD_rus_crisis.{key}", self.loc)

    def food_events(self):
        return {
            scalar(row.value, "id"): row.value for row in parse("events/ADISCORD_RUS_events.txt")
            if row.key == "country_event"
        }

    def test_food_mouths_grow_with_states_refugees_levies_and_plague(self):
        world = self.world()
        world.variables["num_controlled_states"] = 1
        world.run("RUS_bunker_refresh")
        base = world.value("RUS_bunker_food_use")
        self.assertEqual(world.value("RUS_bunker_mouths"), 0)
        for states, mouths in ((3, 0), (4, 1), (7, 2), (12, 3), (19, 6), (40, 6)):
            world.variables["num_controlled_states"] = states
            world.run("RUS_bunker_refresh")
            self.assertEqual(world.value("RUS_bunker_food_use") - base, mouths, states)
        world.variables["num_controlled_states"] = 1
        world.variables["RUS_bunker_refugee_mouths"] = 2
        world.variables["RUS_levy_raised"] = 1
        world.flags.add("RUS_bunker_cattle_plague")
        world.run("RUS_bunker_refresh")
        self.assertEqual(world.value("RUS_bunker_food_use") - base, 6)
        world.flags.discard("RUS_bunker_cattle_plague")
        world.run("RUS_bunker_food_pressure")
        self.assertEqual(world.value("RUS_bunker_food_use") - base, 3)

    def test_food_surplus_spoils_every_second_month(self):
        for focus, loss in ((None, 2.5), ("RUS_bunker_emergency_rations", 1.25)):
            world = self.world()
            world.focuses.discard("RUS_bunker_emergency_rations")
            if focus:
                world.focuses.add(focus)
            world.run("RUS_bunker_refresh")
            world.variables["RUS_bunker_food"] = 100
            world.run("RUS_bunker_spoil_food")
            self.assertEqual(world.value("RUS_bunker_food"), 100)
            world.run("RUS_bunker_spoil_food")
            self.assertAlmostEqual(world.value("RUS_bunker_food"), 100 - loss)
            self.assertAlmostEqual(world.value("RUS_bunker_food_spoiled"), loss)
            world.variables["RUS_bunker_food"] = 75
            world.run("RUS_bunker_spoil_food")
            world.run("RUS_bunker_spoil_food")
            self.assertEqual(world.value("RUS_bunker_food"), 75)
            self.assertEqual(world.value("RUS_bunker_food_spoiled"), 0)

    def test_mushroom_farm_reserves_power_pays_once_and_refunds_on_loss(self):
        world = self.world()
        world.variables["RUS_bunker_depth"] = 2
        world.variables["ADISCORD_economy_treasury"] = 130
        world.run("RUS_bunker_refresh")
        world.decisions = dict(world.decisions, **self.programmes)
        output = world.value("RUS_bunker_food_output")
        used = world.value("RUS_bunker_used_power")
        world.begin("RUS_bunker_mushroom_farm")
        self.assertEqual(world.value("ADISCORD_economy_treasury"), 65)
        self.assertEqual(world.value("RUS_bunker_used_power"), used + 1)
        self.assertFalse(world.matches(self.triggers["RUS_bunker_farm_ready"]))
        world.finish("RUS_bunker_mushroom_farm")
        self.assertEqual(world.value("RUS_bunker_farms"), 1)
        self.assertEqual(world.value("RUS_bunker_food_output"), output + 2)
        self.assertEqual(world.value("RUS_bunker_used_power"), used + 1)
        world.begin("RUS_bunker_mushroom_farm")
        self.assertEqual(world.value("ADISCORD_economy_treasury"), 0)
        world.execute(block(self.programmes["RUS_bunker_mushroom_farm"], "cancel_effect"))
        world.execute(block(self.programmes["RUS_bunker_mushroom_farm"], "cancel_effect"))
        self.assertEqual(world.value("ADISCORD_economy_treasury"), 65)
        self.assertEqual(world.value("RUS_bunker_farms"), 1)
        self.assertEqual(world.value("RUS_bunker_used_power"), used + 1)

    def test_food_requisition_needs_annexed_states(self):
        world = self.world()
        world.decisions = dict(world.decisions, **self.programmes)
        world.variables["num_controlled_states"] = 3
        self.assertFalse(world.matches(block(self.programmes["RUS_aimaq_food_requisition"], "available")))
        world.variables["num_controlled_states"] = 4
        world.run("RUS_bunker_refresh")
        world.variables["RUS_bunker_food"] = 10
        world.stability = 0.5
        world.begin("RUS_aimaq_food_requisition")
        self.assertEqual(world.value("RUS_bunker_food"), 50)
        self.assertAlmostEqual(world.stability, 0.46)

    def test_vorkerland_airlift_shrinks_and_collapse_cuts_it(self):
        initialize = list(walk(self.effects["RUS_campaign_initialize"]))
        self.assertIn(("activate_mission", "RUS_vorkerland_airlift"), [(row.key, row.value) for row in initialize])
        mission = self.programmes["RUS_vorkerland_airlift"]
        self.assertEqual(scalar(mission, "days_mission_timeout"), "50")
        self.assertEqual(block(mission, "available")[0].key, "hidden_trigger")
        events = self.food_events()
        world = self.world()
        world.flags.add("RUS_vorkerland_airlift_active")
        world.variables["RUS_vorkerland_airlift_stage"] = 1
        world.run("RUS_bunker_refresh")
        received = []
        for event_id in ("ADISCORD_rus_crisis.34", "ADISCORD_rus_crisis.35", "ADISCORD_rus_crisis.36"):
            world.events.clear()
            world.missions.clear()
            world.run("RUS_vorkerland_airlift_arrive")
            self.assertEqual(world.events, [event_id])
            world.execute(block(events[event_id], "immediate"))
            option = next(row.value for row in events[event_id] if row.key == "option")
            world.variables["RUS_bunker_food"] = 0
            world.execute([row for row in option if row.key not in ("name", "ai_chance")])
            received.append(world.value("RUS_bunker_food"))
            self.assertEqual(bool(world.missions), event_id != "ADISCORD_rus_crisis.36")
        self.assertEqual(received, [60, 35, 15])
        self.assertNotIn("RUS_vorkerland_airlift_active", world.flags)
        world = self.world()
        world.flags.add("RUS_vorkerland_airlift_active")
        world.variables["RUS_vorkerland_airlift_stage"] = 2
        world.global_flags.add("ADISCORD_vorkerland_collapse_started")
        world.events.clear()
        world.run("RUS_vorkerland_airlift_arrive")
        self.assertEqual(world.events, ["ADISCORD_rus_crisis.37"])
        world.execute(block(events["ADISCORD_rus_crisis.37"], "immediate"))
        self.assertNotIn("RUS_vorkerland_airlift_active", world.flags)

    def test_food_disasters_need_their_asset_and_first_answer_is_free(self):
        events = self.food_events()
        draws = block(self.effects["RUS_bunker_disasters_monthly"], "if")
        outcomes = [row.value for row in block(draws, "random_list") if row.value]
        fired = [scalar(block(rows, "country_event"), "id") for rows in outcomes]
        self.assertEqual(fired, ["ADISCORD_rus_crisis.38", "ADISCORD_rus_crisis.39", "ADISCORD_rus_crisis.40"])
        for rows in outcomes:
            self.assertEqual(block(rows, "modifier")[0].value, "0")
            self.assertEqual(scalar(block(rows, "set_country_flag"), "days"), "240")
        losses = {}
        for event_id in fired:
            options = [row.value for row in events[event_id] if row.key == "option"]
            self.assertFalse(any(row.key == "trigger" for row in options[0]), event_id)
            for index, option in enumerate(options):
                world = self.world()
                world.run("RUS_bunker_refresh")
                world.variables["RUS_bunker_food"] = 100
                world.variables["ADISCORD_economy_treasury"] = 100
                world.pp = 50
                world.manpower = 5000
                world.stability = 0.5
                world.execute([row for row in option if row.key not in ("name", "trigger", "ai_chance")])
                losses[(event_id[-2:], index)] = (
                    round(100 - world.value("RUS_bunker_food"), 2),
                    100 - world.value("ADISCORD_economy_treasury"),
                    5000 - world.manpower,
                )
        self.assertEqual(losses[("38", 0)], (25, 0, 0))
        self.assertEqual(losses[("38", 1)], (0, 65, 0))
        self.assertEqual(losses[("38", 2)], (0, 0, 1000))
        self.assertEqual(losses[("39", 0)], (40, 0, 0))
        self.assertEqual(losses[("39", 1)], (10, 35, 0))
        self.assertEqual(losses[("39", 2)], (15, 0, 1000))
        self.assertEqual(losses[("40", 1)], (0, 65, 0))
        world = self.world()
        world.run("RUS_bunker_refresh")
        use = world.value("RUS_bunker_food_use")
        option = next(row.value for row in events["ADISCORD_rus_crisis.40"] if row.key == "option")
        world.execute([row for row in option if row.key not in ("name", "ai_chance")])
        self.assertEqual(world.value("RUS_bunker_food_use"), use + 3)

    def test_faction_favours_spend_support_on_strong_rewards(self):
        specs = {
            "RUS_favour_shock_fist": ("RUS_black_army_support", 0.20, "modifier"),
            "RUS_favour_black_army_musters": ("RUS_black_army_support", 0.15, "manpower"),
            "RUS_favour_guard_instructors": ("RUS_black_army_support", 0.15, "experience"),
            "RUS_favour_night_shifts": ("RUS_scientists_support", 0.20, "modifier"),
            "RUS_favour_prototypes": ("RUS_scientists_support", 0.15, "tech"),
            "RUS_favour_reactor_current": ("RUS_scientists_support", 0.15, "modifier"),
        }
        modifiers = {row.key: row.value for row in parse("common/dynamic_modifiers/ADISCORD_dynamic_modifiers_RUS.txt")}
        for name, (support, price, reward) in specs.items():
            with self.subTest(name=name):
                rows = self.balance[name]
                self.assertEqual(scalar(rows, "cost"), "0")
                self.assertEqual(scalar(rows, "days_re_enable"), "120")
                cost_key = scalar(rows, "custom_cost_text")
                for key in (name, f"{name}_desc", cost_key, f"{cost_key}_blocked", f"{cost_key}_tooltip"):
                    self.assertIn(key, self.loc)
                world = self.world()
                world.decisions = {**world.decisions, **self.balance}
                world.variables.update({"RUS_black_army_support": 0.6, "RUS_scientists_support": 0.6})
                world.manpower = 0.0
                other = "RUS_scientists_support" if support == "RUS_black_army_support" else "RUS_black_army_support"
                world.begin(name)
                self.assertAlmostEqual(world.value(support), 0.6 - price)
                self.assertAlmostEqual(world.value(other), 0.6)
                if reward == "modifier":
                    self.assertIn(name, world.modifiers)
                    self.assertIn(name, modifiers)
                elif reward == "manpower":
                    self.assertEqual(world.manpower, 12000)
                elif reward == "experience":
                    self.assertEqual((world.army_experience, world.command_power), (40, 25))
                else:
                    self.assertEqual(world.tech_bonuses, [name])
                poor = self.world()
                poor.variables.update({support: price - 0.001})
                self.assertFalse(poor.matches(block(rows, "custom_cost_trigger")))
                before = deepcopy(poor.variables), poor.manpower, set(poor.modifiers)
                poor.execute(block(rows, "complete_effect"))
                self.assertEqual((poor.variables, poor.manpower, poor.modifiers), before)

    def test_faction_favours_panel_links_decisions_and_localises_every_label(self):
        panel = block(block(parse("common/scripted_guis/ADISCORD_RUS_scripted_gui.txt"), "scripted_gui"), "ADISCORD_RUS_favours_panel")
        self.assertEqual(scalar(panel, "context_type"), "decision_category")
        self.assertFalse(any(row.key == "dirty" for row in panel))
        category = block(parse("common/decisions/categories/ADISCORD_decision_categories_RUS.txt"), "RUS_state_balance_category")
        self.assertEqual(scalar(category, "scripted_gui"), "ADISCORD_RUS_favours_panel")
        window = next(row.value for row in block(parse("interface/ADISCORD_RUS.gui"), "guiTypes") if row.key == "containerWindowType" and scalar(row.value, "name") == scalar(panel, "window_name"))
        decisions = {name for name in self.balance if name.startswith("RUS_favour_")}
        buttons = {scalar(row.value, "name") for row in walk(window) if row.key == "buttonType"}
        self.assertEqual(buttons, {name + "_button" for name in decisions})
        actions = block(panel, "effects")
        self.assertEqual({row.key for row in actions}, {name + "_click" for name in buttons})
        for name in decisions:
            action = block(actions, name + "_button_click")
            self.assertEqual([(row.key, row.value) for row in action], [("activate_decision", name)])
        self.assertFalse(any(row.key == "properties" for row in panel))
        functions = {scalar(row.value, "name"): row.value for row in parse("common/scripted_localisation/ADISCORD_RUS_scripted_loc.txt") if row.key == "defined_text"}
        keys = {row.value for row in walk(window) if row.key in ("text", "buttonText", "pdx_tooltip") and isinstance(row.value, str) and row.value}
        for language in ("russian", "english"):
            raw = (ROOT / f"localisation/{language}/ADISCORD_RUS_l_{language}.yml").read_bytes()
            self.assertTrue(raw.startswith(b"\xef\xbb\xbf"))
            loc = dict(re.findall(r'^\s+(\w+):\d*\s+"(.*)"\s*$', raw.decode("utf-8-sig"), re.M))
            for faction in ("scientists", "black_army"):
                self.assertIn(f"[?RUS_{faction}_support|%1]", loc[f"RUS_favours_{faction}_value"])
            pending = list(keys)
            seen = set()
            while pending:
                key = pending.pop()
                if key in seen:
                    continue
                seen.add(key)
                self.assertIn(key, loc, (language, key))
                pending.extend(re.findall(r"\$(\w+)\$", loc[key]))
                for function in re.findall(r"\[(GetRUS\w+)\]", loc[key]):
                    self.assertIn(function, functions)
                    pending.extend(row.value for row in walk(functions[function]) if row.key == "localization_key")

    def test_faction_favours_panel_blocks_shortages_cooldowns_and_lost_government(self):
        panel = block(block(parse("common/scripted_guis/ADISCORD_RUS_scripted_gui.txt"), "scripted_gui"), "ADISCORD_RUS_favours_panel")
        gates = block(panel, "triggers")
        for name, decision in self.balance.items():
            if not name.startswith("RUS_favour_"):
                continue
            cost = scalar(decision, "custom_cost_text")
            support = "RUS_black_army_support" if "_army_" in cost else "RUS_scientists_support"
            price = int(cost.split("_")[-2]) / 100
            gate = block(gates, name + "_button_click_enabled")
            for amount in (0, price - .001, price, .5, 1):
                world = self.world()
                world.variables[support] = amount
                expected = all(world.matches(block(decision, field)) for field in ("visible", "available", "custom_cost_trigger"))
                self.assertEqual(world.matches(gate), expected, (name, amount))
                world.flags.add(name + "_ui_cooldown")
                self.assertFalse(world.matches(gate), name)
                world.flags.discard(name + "_ui_cooldown")
                self.assertEqual(world.matches(gate), expected, name)
            world = self.world()
            world.variables[support] = 1
            world.subject = True
            self.assertFalse(world.matches(gate), name)
            world.subject = False
            world.decisions = {**world.decisions, **self.balance}
            world.begin(name)
            self.assertFalse(world.matches(gate), name)
            flags = [row.value for row in walk(block(decision, "complete_effect")) if row.key == "set_country_flag"]
            marker = next(value for value in flags if isinstance(value, list) and scalar(value, "flag") == name + "_ui_cooldown")
            self.assertEqual(scalar(marker, "days"), scalar(decision, "days_re_enable"), name)

    def test_faction_favours_text_matches_support_and_payment_state(self):
        for faction in ("Scientists", "BlackArmy"):
            support = "RUS_scientists_support" if faction == "Scientists" else "RUS_black_army_support"
            for amount, state in ((0, "negative"), (.499, "negative"), (.5, "neutral"), (.501, "positive"), (1, "positive")):
                world = self.world()
                world.variables[support] = amount
                self.assertEqual(self.bunker_text(world, f"GetRUSFavour{faction}Support"), f"RUS_favours_support_{state}")
        for name, decision in self.balance.items():
            if not name.startswith("RUS_favour_"):
                continue
            cost = scalar(decision, "custom_cost_text")
            faction, price = cost.split("_")[2:4]
            support = "RUS_black_army_support" if faction == "army" else "RUS_scientists_support"
            function = "GetRUSFavour" + "".join(word.title() for word in name.removeprefix("RUS_favour_").split("_")) + "Status"
            world = self.world()
            world.variables[support] = 1
            self.assertEqual(self.bunker_text(world, function), "RUS_favours_status_ready")
            self.assertEqual(self.bunker_text(world, f"GetRUSFavour{faction.title()}{price}Cost"), cost)
            world.variables[support] = .01
            self.assertEqual(self.bunker_text(world, function), "RUS_favours_status_shortage")
            self.assertEqual(self.bunker_text(world, f"GetRUSFavour{faction.title()}{price}Cost"), cost + "_blocked")
            world.flags.add(name + "_ui_cooldown")
            self.assertEqual(self.bunker_text(world, function), "RUS_favours_status_cooldown")
            world.flags.discard(name + "_ui_cooldown")
            world.subject = True
            self.assertEqual(self.bunker_text(world, function), "RUS_favours_status_unavailable")

    def test_faction_favours_geometry_and_emblems_fit_the_panel(self):
        window = next(row.value for row in block(parse("interface/ADISCORD_RUS.gui"), "guiTypes") if row.key == "containerWindowType" and scalar(row.value, "name") == "ADISCORD_RUS_favours_window")
        width = int(scalar(block(window, "size"), "width"))
        height = int(scalar(block(window, "size"), "height"))
        self.assertEqual(width, 460)
        self.assertLessEqual(height, 720)
        widgets = {scalar(row.value, "name"): row for row in window if row.key in ("buttonType", "iconType", "instantTextBoxType")}
        sprites = {scalar(row.value, "name"): row for path in ("interface/ADISCORD_RUS.gfx", "interface/ADISCORD_bop.gfx") for row in block(parse(path), "spriteTypes")}
        for faction, x in (("scientists", 8), ("black_army", 234)):
            emblem = widgets[f"RUS_favours_{faction}_emblem"].value
            self.assertEqual(scalar(emblem, "spriteType"), f"GFX_bop_RUS_{faction}")
            for suffix in ("bar", "midpoint", "zero", "half", "full"):
                self.assertNotIn(f"RUS_favours_{faction}_{suffix}", widgets)
            value = widgets[f"RUS_favours_{faction}_value"].value
            status = widgets[f"RUS_favours_{faction}_support_status"].value
            value_bottom = int(scalar(block(value, "position"), "y")) + int(scalar(value, "maxHeight"))
            status_y = int(scalar(block(status, "position"), "y"))
            self.assertGreaterEqual(status_y, value_bottom)
            status_bottom = status_y + int(scalar(status, "maxHeight"))
            for widget in widgets.values():
                if widget.key == "buttonType" and int(scalar(block(widget.value, "position"), "x")) == x:
                    self.assertGreaterEqual(int(scalar(block(widget.value, "position"), "y")), status_bottom)
        for name, widget in widgets.items():
            row = widget.value
            x, y = (int(scalar(block(row, "position"), axis)) for axis in ("x", "y"))
            if widget.key == "instantTextBoxType":
                w, h = (int(scalar(row, key)) for key in ("maxWidth", "maxHeight"))
                if name.startswith("RUS_favour_"):
                    self.assertEqual(scalar(row, "alwaystransparent"), "yes", name)
            elif widget.key == "buttonType":
                w, h = (int(scalar(block(row, "size"), axis)) for axis in ("x", "y"))
                expected_x = 8 if any(part in name for part in ("night_shifts", "prototypes", "reactor_current")) else 234
                self.assertEqual(x, expected_x, name)
            else:
                sprite = sprites[scalar(row, "spriteType")]
                path = next(item.value for item in sprite.value if item.key.lower() == "texturefile")
                with Image.open(ROOT / path) as image:
                    w, h = image.size
            self.assertGreaterEqual(x, 0, name)
            self.assertGreaterEqual(y, 0, name)
            self.assertLessEqual(x + w, width, name)
            self.assertLessEqual(y + h, height, name)

    def test_every_rus_custom_tooltip_is_a_localised_key(self):
        sources = (
            "focus_trees/RUS/main/focuses.txt",
            f"common/decisions/{BASE}_decisions.txt",
            "common/scripted_effects/ADISCORD_RUS_scripted_effects.txt",
            "events/ADISCORD_RUS_events.txt",
        )
        for source in sources:
            for key in re.findall(r"custom_effect_tooltip = (\S+)", read(source)):
                self.assertFalse(key.isdigit(), (source, key))
                self.assertIn(key, self.loc, (source, key))

    def test_bunker_upper_branch_choices_layers_and_silence_trial(self):
        for first, second in (("RUS_bunker_layer_service_school", "RUS_bunker_reserve_shaft"), ("RUS_bunker_water_recycling", "RUS_bunker_contingency_reservoir")):
            self.assertIn(second, [row.value for row in walk(block(self.focuses[first], "mutually_exclusive"))])
            self.assertIn(first, [row.value for row in walk(block(self.focuses[second], "mutually_exclusive"))])
        for focus, damage in ((None, 35), ("RUS_bunker_layer_service_school", 20)):
            world = self.world()
            if focus:
                world.focuses.add(focus)
            world.run("RUS_bunker_refresh")
            self.assertEqual(world.value("RUS_bunker_rush_damage"), damage)
        for focus, share in ((None, 0.75), ("RUS_bunker_contingency_reservoir", 0.60)):
            world = self.world()
            if focus:
                world.focuses.add(focus)
            world.run("RUS_bunker_refresh")
            self.assertAlmostEqual(world.value("RUS_bunker_food_fed_line"), world.value("RUS_bunker_food_capacity") * share)
        for hungry, stability in ((False, 0.05), (True, -0.05)):
            world = self.world()
            world.stability = 0.5
            world.flags.add("RUS_bunker_silence_trial_active")
            world.variables.update({"RUS_bunker_depth": 1, "RUS_bunker_layer_1": 1, "RUS_bunker_food": 0 if hungry else 40, "RUS_bunker_integrity": 80})
            world.run("RUS_bunker_refresh")
            world.run("RUS_bunker_silence_trial_settle")
            self.assertAlmostEqual(world.stability - 0.5, stability)
            self.assertFalse({"RUS_bunker_silence_trial_active", "RUS_bunker_silence_trial_failed"} & world.flags)
        trial = self.programmes["RUS_bunker_silence_trial"]
        self.assertEqual(scalar(trial, "days_mission_timeout"), "30")
        self.assertEqual([row.key for row in block(trial, "available")], ["hidden_trigger"])
        for key in ("RUS_bunker_silence_trial", "RUS_bunker_silence_trial_desc"):
            self.assertIn(key, self.loc)

    def test_layer_focus_bonuses_join_bunker_totals_without_stacking(self):
        cases = (
            (2, 1, "utilities", "attrition", -0.05),
            (2, 2, "utilities", "planning_speed", 0.05),
            (3, 1, "working_heart", "industrial_capacity_factory", 0.05),
            (3, 2, "working_heart", "consumer_goods_factor", -0.03),
            (4, 1, "science_wing", "casualty_trickleback", 0.05),
            (4, 2, "science_wing", "research_speed_factor", 0.05),
            (5, 1, "memory_vault", "political_power_gain", 0.10),
            (5, 2, "memory_vault", "max_planning_factor", 0.05),
        )
        dynamic = parse("common/dynamic_modifiers/ADISCORD_dynamic_modifiers_RUS.txt")
        self.assertNotIn("RUS_bunker_layer_mastery", [row.key for row in dynamic])
        bunker = block(dynamic, "RUS_bunker_complex")
        for layer, variant, suffix, modifier, delta in cases:
            for upgrade in (0, 1):
                with self.subTest(layer=layer, variant=variant, upgrade=upgrade):
                    world = self.world()
                    focus = "RUS_bunker_" + suffix
                    variable = "RUS_bunker_" + modifier
                    room = f"RUS_bunker_layer_{layer}"
                    self.assertEqual(scalar(bunker, modifier), variable)
                    world.variables.update({"RUS_bunker_depth": 5, room: variant,
                                            f"RUS_bunker_upgrade_{layer}": upgrade})
                    world.focuses.discard(focus)
                    world.run("RUS_bunker_refresh")
                    base = world.value(variable)
                    world.focuses.add(focus)
                    world.run("RUS_bunker_refresh")
                    self.assertAlmostEqual(world.value(variable), base + delta)
                    world.run("RUS_bunker_refresh")
                    self.assertAlmostEqual(world.value(variable), base + delta)
                    self.assertIn("RUS_bunker_complex", world.modifiers)
                    self.assertNotIn("RUS_bunker_layer_mastery", world.modifiers)
                    world.variables[room] = 0
                    world.run("RUS_bunker_refresh")
                    empty = world.value(variable)
                    world.focuses.discard(focus)
                    world.run("RUS_bunker_refresh")
                    self.assertAlmostEqual(world.value(variable), empty)
                    world.variables[room] = variant
                    world.focuses.add(focus)
                    world.controller = False
                    world.run("RUS_bunker_refresh")
                    self.assertNotIn("RUS_bunker_complex", world.modifiers)
                    world.controller = True
                    world.run("RUS_bunker_refresh")
                    self.assertAlmostEqual(world.value(variable), base + delta)
                    self.assertIn("RUS_bunker_complex", world.modifiers)

    def test_bunker_finals_offer_free_city_slot_and_paid_headquarters_slot(self):
        name = "RUS_bunker_research_bureau"
        decision = self.programmes[name]
        city = self.world()
        city.execute(block(self.focuses["RUS_bunker_city_charter"], "completion_reward"))
        self.assertEqual(city.research_slots, 1)
        headquarters = self.world()
        reward = block(self.focuses["RUS_bunker_eternal_headquarters"], "completion_reward")
        headquarters.execute(reward)
        self.assertEqual(headquarters.research_slots, 0)
        self.assertEqual(scalar(reward, "unlock_decision_tooltip"), name)
        self.assertEqual(scalar(decision, "fire_only_once"), "yes")
        self.assertEqual(scalar(decision, "cost"), "0")
        self.assertFalse({"days_remove", "days_re_enable", "remove_effect"} & {row.key for row in decision})
        headquarters.focuses.discard("RUS_bunker_eternal_headquarters")
        self.assertFalse(headquarters.matches(block(decision, "visible")))
        headquarters.focuses.add("RUS_bunker_eternal_headquarters")
        self.assertTrue(headquarters.matches(block(decision, "visible")))
        category = block(parse("common/decisions/categories/ADISCORD_decision_categories_RUS.txt"), "RUS_development_programmes")
        self.assertIn("RUS_bunker_eternal_headquarters", [row.value for row in walk(block(category, "visible")) if row.key == "has_completed_focus"])
        for language in ("russian", "english"):
            path = ROOT / f"localisation/{language}/ADISCORD_RUS_l_{language}.yml"
            self.assertTrue(path.read_bytes().startswith(b"\xef\xbb\xbf"))
            loc = dict(re.findall(r'^\s+([A-Za-z0-9_.]+):(?:\d+)?\s+"(.*)"\s*$', read(path), re.M))
            for suffix in ("", "_desc", "_cost", "_cost_blocked", "_cost_tooltip"):
                self.assertIn(name + suffix, loc)
            self.assertEqual(loc[name + "_cost"], "§Y500§! £ADISCORD_economy_treasury_texticon")
            self.assertEqual(loc[name + "_cost_blocked"], "§R500§! £ADISCORD_economy_treasury_texticon")

    def test_headquarters_research_bureau_checks_exact_price_and_records_payment(self):
        name = "RUS_bunker_research_bureau"
        decision = self.programmes[name]
        for treasury in (0, 499.99, 500, 750.5):
            with self.subTest(treasury=treasury):
                world = self.world()
                world.decisions = self.programmes
                world.pp = 0
                world.variables["ADISCORD_economy_treasury"] = treasury
                before_costs = world.value("ADISCORD_economy_current_month_action_costs")
                before_dirty = world.dirty
                affordable = treasury >= 500
                self.assertEqual(world.matches(block(decision, "custom_cost_trigger")), affordable)
                if affordable:
                    world.begin(name)
                else:
                    world.execute(block(decision, "complete_effect"))
                self.assertEqual(world.value("ADISCORD_economy_treasury"), treasury - (500 if affordable else 0))
                self.assertEqual(world.value("ADISCORD_economy_current_month_action_costs") - before_costs, 500 if affordable else 0)
                self.assertEqual(world.research_slots, int(affordable))
                self.assertEqual(world.dirty - before_dirty, int(affordable))
                self.assertEqual(world.pp, 0)
        for missing in ("focus", "owner", "controller", "ruler"):
            with self.subTest(missing=missing):
                world = self.world()
                if missing == "focus":
                    world.focuses.discard("RUS_bunker_eternal_headquarters")
                elif missing == "ruler":
                    world.ruler = "RUS_Varlam_Oskol"
                else:
                    setattr(world, missing, False)
                self.assertFalse(world.matches(block(decision, "visible" if missing == "focus" else "available")))
                before = world.balances(), deepcopy(world.variables), world.dirty
                world.execute(block(decision, "complete_effect"))
                self.assertEqual((world.balances(), world.variables, world.dirty), before)
                self.assertEqual(world.research_slots, 0)

    def test_bunker_courses_extend_with_their_own_mechanics(self):
        positions = {}
        for focus, rows in self.focuses.items():
            key = (scalar(rows, "x"), scalar(rows, "y"))
            self.assertNotIn(key, positions, (focus, positions.get(key)))
            positions[key] = focus
        expected = {
            "RUS_bunker_surface_market": [["RUS_bunker_open_city"], ["RUS_bunker_commission"]],
            "RUS_bunker_refugee_quarters": [["RUS_bunker_surface_market"]],
            "RUS_bunker_city_charter": [["RUS_bunker_systems_college"], ["RUS_bunker_refugee_quarters"]],
            "RUS_bunker_deep_casemates": [["RUS_bunker_sealed_throne"], ["RUS_bunker_commission"]],
            "RUS_bunker_mountain_garrison": [["RUS_bunker_deep_casemates"]],
            "RUS_bunker_eternal_headquarters": [["RUS_bunker_emergency_rations"], ["RUS_bunker_mountain_garrison"]],
        }
        for focus, prerequisites in expected.items():
            rows = self.focuses[focus]
            actual = [[row.value for row in block_rows if row.key == "focus"] for block_rows in (entry.value for entry in rows if entry.key == "prerequisite")]
            self.assertEqual(actual, prerequisites, focus)
            self.assertIn(focus, self.loc)
            self.assertIn(f"{focus}_desc", self.loc)

        def refreshed(*focuses):
            world = self.world()
            for focus in expected:
                world.focuses.discard(focus)
            world.focuses.discard("RUS_bunker_reserve_shaft")
            world.focuses.update(focuses)
            world.run("RUS_bunker_refresh")
            return world

        plain, market = refreshed(), refreshed("RUS_bunker_surface_market")
        self.assertEqual(market.value("RUS_bunker_income") - plain.value("RUS_bunker_income"), 8)
        for world, allowed in ((plain, False), (market, True)):
            world.variables["RUS_energy_contracts"] = 2
            self.assertEqual(world.matches(self.triggers["RUS_energy_contract_room"]), allowed)
        casemates = refreshed("RUS_bunker_deep_casemates")
        self.assertAlmostEqual(casemates.value("RUS_bunker_surrender_limit") - plain.value("RUS_bunker_surrender_limit"), 0.10)
        self.assertAlmostEqual(casemates.value("RUS_bunker_army_defence_factor") - plain.value("RUS_bunker_army_defence_factor"), 0.05)
        for garrison, raised, allowed in ((False, 3, False), (True, 3, True), (True, 4, False)):
            world = refreshed("RUS_bunker_mountain_garrison") if garrison else refreshed()
            world.focuses.discard("RUS_district_courts")
            world.focuses.add("RUS_summon_the_aimaqs")
            world.war = True
            world.variables["RUS_levy_raised"] = raised
            self.assertEqual(world.matches(self.triggers["RUS_levy_room"]), allowed, (garrison, raised))
        for focus, idea in ((None, "RUS_bunker_hunger"), ("RUS_bunker_eternal_headquarters", "RUS_bunker_hunger_rationed")):
            world = refreshed(*([focus] if focus else []))
            world.variables.update({"RUS_bunker_depth": 1, "RUS_bunker_layer_1": 1, "RUS_bunker_food": 0})
            world.run("RUS_bunker_refresh")
            self.assertIn(idea, world.ideas)
            self.assertEqual(len({"RUS_bunker_hunger", "RUS_bunker_hunger_rationed"} & world.ideas), 1)
            world.variables["RUS_bunker_food"] = 30
            world.run("RUS_bunker_refresh")
            self.assertFalse({"RUS_bunker_hunger", "RUS_bunker_hunger_rationed"} & world.ideas)
        event = next(
            row.value for row in parse("events/ADISCORD_RUS_events.txt")
            if row.key == "country_event" and scalar(row.value, "id") == "ADISCORD_rus_crisis.31"
        )
        accept = next(row.value for row in event if row.key == "option")
        for quarters, men, food in ((False, 4000, 30), (True, 6000, 15)):
            world = refreshed("RUS_bunker_refugee_quarters") if quarters else refreshed()
            world.manpower = 0.0
            world.variables["RUS_bunker_food"] = 50
            world.execute([row for row in accept if row.key not in ("name", "ai_chance")])
            self.assertEqual((world.manpower, 50 - world.value("RUS_bunker_food")), (men, food), quarters)

    def morale_world(self, morale=100, casualties=0):
        world = self.world()
        world.decisions = {**self.decisions, **self.balance}
        world.focuses = set()
        world.flags.add("ADISCORD_vorkerland_rus_last_empire_proclaimed")
        world.variables["casualties_k"] = casualties
        world.run("RUS_morale_begin")
        world.variables["RUS_army_morale"] = morale
        world.events.clear()
        return world

    def test_proclamation_opens_full_morale_after_its_casualty_snapshot(self):
        world = self.world()
        world.variables["casualties_k"] = 40
        world.run("RUS_morale_begin")
        self.assertFalse(world.matches(self.triggers["RUS_morale_active"]))
        world.flags.add("ADISCORD_vorkerland_rus_last_empire_proclaimed")
        self.assertTrue(world.matches(self.triggers["RUS_morale_active"]))
        self.assertEqual(world.value("RUS_army_morale"), 100)
        self.assertEqual(world.value("RUS_morale_casualties_seen_k"), 40)
        world.variables["RUS_army_morale"] = 50
        world.run("RUS_morale_begin")
        self.assertEqual(world.value("RUS_army_morale"), 50)
        keys = [row.key for row in block(self.effects["ADISCORD_vorkerland_rus_proclaim_last_empire"], "if")]
        self.assertLess(keys.index("RUS_morale_begin"), keys.index("RUS_crisis_check_start"))

    def test_monthly_morale_counts_new_casualties_and_recovers(self):
        cases = (
            (True, 0.0, 65, 75),
            (True, 0.0, 140, 70),
            (False, 0.0, 10, 83),
            (True, 0.7, 40, 82),
            (True, 0.3, 40, 81),
        )
        for war, bop, casualties, expected in cases:
            with self.subTest(war=war, bop=bop, casualties=casualties):
                world = self.morale_world(80, 40)
                world.war = war
                world.bop = bop
                world.variables["casualties_k"] = casualties
                world.run("RUS_morale_monthly")
                self.assertAlmostEqual(world.value("RUS_army_morale"), expected)
                self.assertEqual(world.value("RUS_morale_casualties_seen_k"), casualties)
                self.assertFalse(world.events)

    def test_morale_bands_fire_once_and_rearm_after_recovery(self):
        world = self.morale_world(62)
        world.variables["casualties_k"] = 15
        world.run("RUS_morale_monthly")
        self.assertEqual(world.events, ["ADISCORD_rus_crisis.18"])
        world.run("RUS_morale_monthly")
        self.assertEqual(world.events, ["ADISCORD_rus_crisis.18"])
        world.variables["RUS_army_morale"] = 36
        world.variables["casualties_k"] = 25
        world.run("RUS_morale_monthly")
        self.assertEqual(world.value("RUS_morale_stage"), 2)
        self.assertEqual(world.events, ["ADISCORD_rus_crisis.18"] * 2)
        world.variables["RUS_army_morale"] = 70
        world.temporary["RUS_morale_delta"] = 0
        world.run("RUS_morale_add")
        self.assertEqual(world.value("RUS_morale_stage"), 0)
        world.temporary["RUS_morale_delta"] = -20
        world.run("RUS_morale_add")
        self.assertEqual(world.events, ["ADISCORD_rus_crisis.18"] * 3)
        world.variables["RUS_army_morale"] = 3
        world.temporary["RUS_morale_delta"] = -5
        world.run("RUS_morale_add")
        self.assertEqual(world.events[-1], "ADISCORD_rus_crisis.19")
        calm = self.morale_world(3)
        calm.war = False
        calm.temporary["RUS_morale_delta"] = -5
        calm.run("RUS_morale_add")
        self.assertNotIn("ADISCORD_rus_crisis.19", calm.events)

    def test_morale_swinging_across_a_threshold_announces_once(self):
        world = self.morale_world(61)
        for delta in (-2, 3, -3, 4, -4, 5, -5):
            world.temporary["RUS_morale_delta"] = delta
            world.run("RUS_morale_add")
        self.assertEqual(world.events, ["ADISCORD_rus_crisis.18"])
        self.assertEqual(world.value("RUS_morale_stage"), 1)
        world.temporary["RUS_morale_delta"] = 15
        world.run("RUS_morale_add")
        self.assertEqual(world.value("RUS_morale_stage"), 0)

    def test_morale_crisis_options_pay_their_costs_and_always_leave_a_choice(self):
        events = parse("events/ADISCORD_RUS_events.txt")
        event = next(row.value for row in events if row.key == "country_event" and scalar(row.value, "id") == "ADISCORD_rus_crisis.18")
        options = {scalar(row.value, "name").rsplit(".", 1)[1]: row.value for row in event if row.key == "option"}
        specs = {
            "rations": (1, {"pp": -50}, 10),
            "endure": (1, {}, 0),
            "barriers": (2, {"stability": -0.05, "bop": 0.10}, 12),
            "release": (2, {"manpower": -3000, "war_support": -0.05}, 15),
            "purge": (3, {"stability": -0.10, "command_power": -30}, 15),
            "yield": (3, {"bop": 0.25}, 20),
        }
        self.assertEqual(set(options), set(specs))
        for stage in range(4):
            world = self.morale_world(30)
            world.variables["RUS_morale_stage"] = stage
            available = [name for name, rows in options.items() if world.matches(block(rows, "trigger"))]
            self.assertTrue(available, stage)
        for name, (stage, costs, gain) in specs.items():
            with self.subTest(name=name):
                world = self.morale_world(30)
                world.variables["RUS_morale_stage"] = stage
                world.stability = 0.5
                world.war_support = 0.5
                world.manpower = 5000.0
                self.assertTrue(world.matches(block(options[name], "trigger")))
                fields = ("pp", "stability", "war_support", "manpower", "command_power", "bop")
                before = {field: getattr(world, field) for field in fields}
                world.execute([row for row in options[name] if row.key not in ("name", "trigger", "ai_chance")])
                for field in fields:
                    self.assertAlmostEqual(getattr(world, field), before[field] + costs.get(field, 0), msg=field)
                self.assertEqual(world.value("RUS_army_morale"), 30 + gain)

    def test_morale_status_reserve_rations_and_texts_are_wired(self):
        reserve = block(self.balance["RUS_bop_reserve"], "complete_effect")
        gates = [row.value for row in walk(reserve) if row.key == "if" and any(
            item.key == "limit" and any(entry.key == "RUS_morale_active" for entry in item.value) for item in row.value)]
        self.assertEqual(len(gates), 1)
        self.assertEqual(scalar(gates[0], "custom_effect_tooltip"), "RUS_morale_gain_5_tt")
        deltas = [scalar(row.value, "value") for row in walk(gates[0]) if row.key == "set_temp_variable"]
        self.assertEqual(deltas, ["5"])
        self.assertIn("[GetRUSMoraleStatus]", self.loc["RUS_state_balance_category_desc"])
        names = {row.value for row in walk(parse("common/scripted_localisation/ADISCORD_RUS_scripted_loc.txt")) if row.key == "name"}
        for name in re.findall(r"\[(GetRUSMorale\w+)\]", self.loc["RUS_morale_status"] + "[GetRUSMoraleStatus]"):
            self.assertIn(name, names)
        keys = ["RUS_morale_status", "ADISCORD_rus_crisis.20.t", "ADISCORD_rus_crisis.20.d", "ADISCORD_rus_crisis.20.a"]
        keys += [f"RUS_morale_gain_{amount}_tt" for amount in (5, 10, 12, 15, 20)]
        keys += [f"ADISCORD_rus_crisis.18.{band}.{part}" for band in ("murmur", "desertion", "conspiracy") for part in ("t", "d")]
        keys += [f"ADISCORD_rus_crisis.18.{name}" for name in ("rations", "endure", "barriers", "release", "purge", "yield")]
        for key in keys:
            self.assertIn(key, self.loc)

    IMPERIAL_FOCUSES = (
        "RUS_oath_of_the_empire", "RUS_imperial_field_kitchens", "RUS_black_army_tribunals",
        "RUS_scientists_at_headquarters", "RUS_reserve_of_the_aimaqs", "RUS_imperial_treasury",
        "RUS_levy_of_the_new_aimaqs", "RUS_reactor_current_for_arsenals", "RUS_imperial_railways",
    )

    def test_zone_and_imperial_branches_stay_hidden_until_their_events(self):
        world = self.world()
        world.flags.discard("ADISCORD_vorkerland_rus_last_empire_proclaimed")
        zone = block(self.focuses["RUS_claim_the_opened_zone"], "allow_branch")
        self.assertFalse(world.matches(zone))
        world.global_flags.add("ADISCORD_vorkerland_dirty_opened")
        self.assertTrue(world.matches(zone))
        roots = ["RUS_break_the_hegemon", "RUS_oath_of_the_empire", "RUS_imperial_treasury"]
        for name in roots:
            self.assertFalse(world.matches(block(self.focuses[name], "allow_branch")), name)
        world.flags.add("ADISCORD_vorkerland_rus_last_empire_proclaimed")
        for name in roots:
            self.assertTrue(world.matches(block(self.focuses[name], "allow_branch")), name)
        hidden = {name for name, rows in self.focuses.items() if any(row.key == "allow_branch" for row in rows)}
        self.assertEqual(hidden, {"RUS_claim_the_opened_zone", *roots})
        proclaim = block(self.effects["ADISCORD_vorkerland_rus_proclaim_last_empire"], "if")
        self.assertEqual(scalar(proclaim, "mark_focus_tree_layout_dirty"), "yes")
        events = parse("events/ADISCORD_vorkerland_events.txt")
        opening = next(row.value for row in events if row.key == "country_event" and scalar(row.value, "id") == "ADISCORD_vorkerland_collapse.85")
        immediate = block(opening, "immediate")
        keys = [row.key for row in immediate]
        self.assertLess(keys.index("set_global_flag"), keys.index("mark_focus_tree_layout_dirty"))

    def test_perimeter_briefing_follows_superevent_close_and_observer_timeout(self):
        presentation = "superevent_vorkerland_dirty_opening"
        opened = "ADISCORD_vorkerland_dirty_opened"
        event_id = "ADISCORD_rus_campaign.39"
        event = next(
            row.value for row in parse("events/ADISCORD_RUS_events.txt")
            if row.key == "country_event" and scalar(row.value, "id") == event_id
        )
        self.assertEqual(scalar(event, "is_triggered_only"), "yes")
        self.assertEqual(scalar(event, "fire_only_once"), "yes")
        gui = block(parse("common/scripted_guis/superevents.txt"), "scripted_gui")
        close = block(block(block(gui, presentation), "effects"), "superevents_button_click")
        timeout = next(
            row.value for row in walk(self.effects["ADISCORD_superevent_observer_tick"])
            if row.key == "if" and any(
                child.key == "clr_global_flag" and child.value == presentation
                for child in row.value
            )
        )
        age = block(block(timeout, "limit"), "has_global_flag")
        self.assertEqual(scalar(age, "flag"), presentation)
        self.assertEqual([row.value for row in age if not row.key], ["days", ">", "6"])
        for source, rows in (("click", close), ("observer", timeout)):
            with self.subTest(source=source):
                keys = [row.key for row in rows]
                self.assertLess(keys.index("clr_global_flag"), keys.index("if"))
                delivery = block(rows, "if")
                self.assertEqual(scalar(block(delivery, "limit"), "has_global_flag"), opened)
                call = block(block(delivery, "RUS"), "country_event")
                self.assertEqual([(row.key, row.value) for row in call], [("id", event_id)])
                world = self.world()
                self.assertFalse(world.matches(block(delivery, "limit")))
                self.assertFalse(world.matches(block(event, "trigger")))
                world.global_flags.update((opened, presentation))
                self.assertTrue(world.matches(block(delivery, "limit")))
                self.assertFalse(world.matches(block(event, "trigger")))
                world.global_flags.discard(presentation)
                self.assertTrue(world.matches(block(event, "trigger")))
                world.ruler = "another_ruler"
                self.assertFalse(world.matches(block(event, "trigger")))
        self.assertLess(
            [row.key for row in close].index("if"),
            [row.key for row in close].index("ADISCORD_superevent_dispatch_next"),
        )
        option = block(event, "option")
        self.assertEqual([row.key for row in option], ["name", "custom_effect_tooltip"])
        tooltip = scalar(option, "custom_effect_tooltip")
        self.assertIn("$RUS_claim_the_opened_zone$", self.loc[tooltip])
        self.assertIn("$RUS_drive_starolesye_back$", self.loc[tooltip])
        self.assertIn("$RUS_press_the_closed_zone$", self.loc[tooltip])

    def test_imperial_focuses_are_reachable_localised_and_do_not_overlap(self):
        positions = {}
        for name, rows in self.focuses.items():
            position = (scalar(rows, "x"), scalar(rows, "y"))
            self.assertNotIn(position, positions, (name, positions.get(position)))
            positions[position] = name
        for name in self.IMPERIAL_FOCUSES:
            with self.subTest(name=name):
                rows = self.focuses[name]
                for row in walk(rows):
                    if row.key == "focus":
                        self.assertIn(row.value, self.focuses)
                available = block(rows, "available")
                self.assertIn("ADISCORD_vorkerland_rus_last_empire_proclaimed", repr(available))
                self.assertIn(name, self.loc)
                self.assertIn(f"{name}_desc", self.loc)
                for row in walk(block(rows, "completion_reward")):
                    if row.key == "custom_effect_tooltip":
                        self.assertIn(row.value, self.loc)
        exclusive = {
            name: scalar(block(self.focuses[name], "mutually_exclusive"), "focus")
            for name in ("RUS_black_army_tribunals", "RUS_scientists_at_headquarters")
        }
        self.assertEqual(exclusive, {
            "RUS_black_army_tribunals": "RUS_scientists_at_headquarters",
            "RUS_scientists_at_headquarters": "RUS_black_army_tribunals",
        })

    def test_imperial_army_focuses_change_morale_rules(self):
        cases = (
            ((), 25, 75),
            (("RUS_imperial_field_kitchens",), 25, 77),
            (("RUS_black_army_tribunals",), 25, 77.5),
        )
        for focuses, losses, expected in cases:
            with self.subTest(focuses=focuses):
                world = self.morale_world(80, 0)
                world.focuses.update(focuses)
                world.variables["casualties_k"] = losses
                world.run("RUS_morale_monthly")
                self.assertAlmostEqual(world.value("RUS_army_morale"), expected)
        world = self.morale_world(50)
        world.execute(block(self.focuses["RUS_oath_of_the_empire"], "completion_reward"))
        self.assertEqual(world.value("RUS_army_morale"), 60)
        world.execute(block(self.focuses["RUS_imperial_field_kitchens"], "completion_reward"))
        self.assertEqual(world.value("RUS_army_morale"), 70)

    def test_bunker_market_income_bypasses_budget_multipliers(self):
        economy = {e.key: e.value for e in parse("common/scripted_effects/ADISCORD_economy_effects.txt")}
        building = economy["ADISCORD_economy_calculate_building_income"]
        self.assertNotIn("RUS_bunker_income", [row.value for row in walk(building)])
        for name in ("ADISCORD_economy_calculate_income", "ADISCORD_economy_recalculate_tax_dependent_income"):
            rows = economy[name]
            keys = [row.key for row in rows]
            direct = next(
                index for index, row in enumerate(rows)
                if row.key == "if" and any(
                    child.key == "add_to_variable" and scalar(child.value, "value") == "ADISCORD_economy_direct_income"
                    for child in row.value
                )
            )
            self.assertLess(keys.index("ADISCORD_economy_apply_overall_income_modifier_factor"), direct, name)
            self.assertLess(keys.index("clamp_variable"), direct, name)
            self.assertEqual(scalar(block(rows[direct].value, "limit"), "tag"), "RUS")
        setter = [
            row.value for row in walk(economy["ADISCORD_economy_calculate_income"])
            if row.key == "set_variable" and scalar(row.value, "var") == "ADISCORD_economy_direct_income"
        ]
        self.assertEqual([scalar(row, "value") for row in setter], ["RUS_bunker_income"])

    def test_imperial_treasury_focus_records_its_income(self):
        world = self.world()
        before = world.value("ADISCORD_economy_treasury")
        income = world.value("ADISCORD_economy_current_month_action_income")
        world.execute(block(self.focuses["RUS_imperial_treasury"], "completion_reward"))
        self.assertEqual(world.value("ADISCORD_economy_treasury"), before + 335)
        self.assertEqual(world.value("ADISCORD_economy_current_month_action_income"), income + 335)
        self.assertIn("335", self.loc["RUS_imperial_treasury_tt"])

    def test_imperial_railways_deliver_transport_without_territorial_rewards(self):
        world = self.world()
        world.owner = False
        world.controller = False
        before = deepcopy(world.regions)
        world.execute(block(self.focuses["RUS_imperial_railways"], "completion_reward"))
        self.assertEqual(world.equipment.get("train_equipment_1", 0), 40)
        self.assertEqual(world.equipment.get("motorized_equipment", 0), 200)
        self.assertEqual(world.railway_orders, [])
        self.assertEqual(world.regions, before)

    def test_imperial_railways_build_only_on_owned_controlled_sites_with_room(self):
        reward = block(self.focuses["RUS_imperial_railways"], "completion_reward")
        for state in ("176", "177", "188", "192", "329"):
            for owner, controller in (("RUS", "RUS"), ("RUS", "VAL"), ("VAL", "RUS")):
                for initial, built in ((0, 2), (1, 2), (3, 2), (4, 1), (5, 0)):
                    with self.subTest(state=state, owner=owner, controller=controller, infrastructure=initial):
                        world = self.world()
                        world.regions = {
                            state: {"owner": owner, "controller": controller, "infrastructure": initial},
                        }
                        world.execute(reward)
                        eligible = state != "329" and owner == controller == "RUS"
                        amount = built if eligible else 0
                        self.assertEqual(world.regions[state]["infrastructure"], initial + amount)
                        self.assertEqual(world.state_construction, [(state, amount)] if amount else [])
                        self.assertEqual(world.railway_orders, [("66", "177", 4)] if state == "177" and eligible else [])

        for owner, controller in ((False, True), (True, False)):
            with self.subTest(capital_owner=owner, capital_controller=controller):
                world = self.world()
                world.owner, world.controller = owner, controller
                world.held_states.add("177")
                world.execute(reward)
                self.assertEqual(world.railway_orders, [])
                self.assertEqual(world.equipment.get("train_equipment_1", 0), 40)

    def test_terminal_shutdown_refunds_and_clears_policies(self):
        world = self.world()
        # Regional winners hold the volunteer mandate; the crisis roster clears it.
        government_previews = {"RUS_council_mandate", "RUS_chancery_mandate", "RUS_repair_depots_spirit"}
        world.ideas = {
            name for name in self.ideas
            if name.startswith("RUS_")
            and not name.endswith(("_delta", "_bookmark"))
            and name != "RUS_crisis_volunteer_mandate"
            and name not in government_previews
        }
        before = world.balances()
        world.begin("RUS_bunker_excavate")
        world.variables["RUS_crisis_phase"] = 4
        world.run("RUS_campaign_shutdown")
        self.assertEqual(world.balances(), before)
        self.assertFalse(world.ideas)
        self.assertFalse(world.modifiers)
        self.assertFalse(world.active)
        self.assertFalse(world.matches(self.triggers["RUS_khan_governing"]))

    def test_save_load_keeps_receipt_and_settlement(self):
        world = self.world()
        world.begin("RUS_bunker_excavate")
        loaded = deepcopy(world)
        loaded.temporary.clear()
        loaded.run("RUS_campaign_initialize")
        loaded.finish("RUS_bunker_excavate")
        world.finish("RUS_bunker_excavate")
        self.assertEqual(loaded.variables, world.variables)
        self.assertEqual(loaded.balances(), world.balances())

    def test_recipes_are_real_focus_unlocks(self):
        for room, gate in (("water", "utilities"), ("signals", "utilities"), ("workshop", "working_heart"), ("granary", "working_heart"), ("clinic", "science_wing"), ("laboratory", "science_wing"), ("archive", "memory_vault"), ("command", "memory_vault")):
            world = self.world()
            world.variables["RUS_bunker_depth"] = 5
            world.focuses.remove("RUS_bunker_" + gate)
            self.assertFalse(world.matches(block(self.decisions["RUS_bunker_" + room], "visible")))
            before = world.balances()
            world.run("RUS_bunker_" + room + "_start")
            self.assertEqual(world.balances(), before)

    def test_cost_variants_encoding_and_story_limits(self):
        for name, rows in self.decisions.items():
            self.assertTrue(name in self.loc, name)
            self.assertTrue(name + "_desc" in self.loc, name + "_desc")
            key = next((e.value for e in rows if e.key == "custom_cost_text"), None)
            if key:
                self.assertEqual(scalar(rows, "cost"), "0")
                for suffix in ("", "_blocked", "_tooltip"):
                    self.assertTrue(key + suffix in self.loc, key + suffix)
        for name in self.focuses:
            self.assertTrue(name in self.loc, name)
            self.assertTrue(name + "_desc" in self.loc, name + "_desc")
        raw = (ROOT / f"localisation/russian/{BASE}_l_russian.yml").read_bytes()
        self.assertTrue(raw.startswith(b"\xef\xbb\xbf"))
        for key, value in self.loc.items():
            if key.startswith("ADISCORD_rus_campaign.") and key.endswith(".d"):
                expanded = value.replace("\\n", "\n")
                self.assertLessEqual(len(expanded), 3000, key)
                self.assertLessEqual(len(expanded.encode("utf-8")), 5500, key)
                self.assertNotIn("§Y", value, key)
        for path in (f"common/decisions/{BASE}_decisions.txt", "focus_trees/RUS/main/focuses.txt"):
            self.assertFalse((ROOT / path).read_bytes().startswith(b"\xef\xbb\xbf"))

    def test_public_story_events_have_no_mandatory_choice_settlement(self):
        events = [e.value for e in parse(f"events/{BASE}_events.txt") if e.key == "country_event" and scalar(e.value, "id").startswith("ADISCORD_rus_campaign.")]
        self.assertEqual(len(events), 41)
        registry = json.loads(read("tools/data/adiscord_event_ids.json"))["events"]
        for event in events:
            name = scalar(event, "id")
            registered = [row for row in registry if row["id"] == name]
            self.assertEqual(len(registered), 1)
            self.assertEqual(registered[0]["number"], int(name.rsplit(".", 1)[1]))
            options = [row.value for row in event if row.key == "option"]
            self.assertTrue(options)
            for option in options:
                reading_pages = {
                    "ADISCORD_rus_campaign.26.continue": "ADISCORD_rus_campaign.27",
                    "ADISCORD_rus_campaign.28.continue": "ADISCORD_rus_campaign.29",
                    "ADISCORD_rus_campaign.30.continue": "ADISCORD_rus_campaign.31",
                    "ADISCORD_rus_campaign.32.continue": "ADISCORD_rus_campaign.33",
                    "ADISCORD_rus_campaign.34.continue": "ADISCORD_rus_campaign.35",
                }
                if scalar(option, "name") in reading_pages:
                    self.assertEqual([row.key for row in option if row.key != "effect_tooltip"], ["name", "hidden_effect"])
                    navigation = block(option, "hidden_effect")
                    self.assertEqual([row.key for row in navigation], ["country_event"])
                    self.assertEqual(scalar(block(navigation, "country_event"), "id"), reading_pages[scalar(option, "name")])
                    continue
                self.assertEqual([row.key for row in option if row.key not in ("trigger", "effect_tooltip", "custom_effect_tooltip")], ["name"])

    def test_childhood_dream_starts_once_and_reading_can_end_on_either_page(self):
        first_id = "ADISCORD_rus_campaign.26"
        last_id = "ADISCORD_rus_campaign.27"
        world = self.world()
        self.assertEqual(world.events.count(first_id), 1)
        world.run("RUS_campaign_initialize")
        self.assertEqual(world.events.count(first_id), 1)
        calls = [
            entry.value for entry in walk(self.effects["RUS_campaign_initialize"])
            if entry.key == "country_event" and scalar(entry.value, "id") == first_id
        ]
        self.assertEqual(len(calls), 1)
        self.assertEqual(scalar(calls[0], "days"), "4")
        self.assertNotIn(last_id, world.events)
        events = {
            scalar(entry.value, "id"): entry.value
            for entry in parse(f"events/{BASE}_events.txt")
            if entry.key == "country_event"
        }
        for number in range(26, 36):
            name = f"ADISCORD_rus_campaign.{number}"
            event = events[name]
            self.assertEqual(scalar(event, "is_triggered_only"), "yes")
            self.assertEqual(scalar(event, "fire_only_once"), "yes")
            if number not in (26, 28, 30, 32):
                self.assertFalse(any(row.key == "immediate" for row in event))
            trigger = block(event, "trigger")
            world.ai = False
            world.ruler = "RUS_Mark_Rustan"
            self.assertTrue(world.matches(trigger))
            world.ai = True
            self.assertFalse(world.matches(trigger))
            world.ai = False
            world.ruler = "RUS_Varlam_Oskol"
            self.assertFalse(world.matches(trigger))
            options = [row.value for row in event if row.key == "option"]
            # The first answer also closes an unattended page without dispatching more text.
            self.assertEqual([row.key for row in options[0] if row.key != "effect_tooltip"], ["name"])
            for language in ("russian", "english"):
                source = read(f"localisation/{language}/{BASE}_l_{language}.yml")
                loc = dict(re.findall(r'^\s+([A-Za-z0-9_.]+):(?:\d+)?\s+"([^"\r\n]*)"\s*$', source, re.M))
                keys = [scalar(event, "title"), scalar(event, "desc")]
                keys.extend(scalar(option, "name") for option in options)
                for key in keys:
                    self.assertIn(key, loc)
                    expanded = loc[key].replace("\\n", "\n")
                    self.assertLessEqual(len(expanded), 3000, key)
                    self.assertLessEqual(len(expanded.encode("utf-8")), 5500, key)
        text = self.loc[first_id + ".d"] + self.loc[last_id + ".d"]
        self.assertIn("Марк Рустан", text)
        self.assertIn("Вейранская империя", text)
        self.assertIn("После революции", text)
        self.assertNotIn("Хан", text)
        self.assertEqual(self.loc[last_id + ".a"], "Урок окончен")
        finale_calls = [
            scalar(row.value, "id") for number in (34, 35)
            for row in walk(events[f"ADISCORD_rus_campaign.{number}"])
            if row.key == "country_event"
        ]
        self.assertEqual(finale_calls, ["ADISCORD_rus_campaign.35"])
        self.assertEqual(
            sum(row.key == "option" for row in events["ADISCORD_rus_campaign.35"]), 1
        )

    def test_followup_dreams_are_scheduled_on_arrival_not_reading_choices(self):
        events = {
            scalar(entry.value, "id"): entry.value
            for entry in parse(f"events/{BASE}_events.txt")
            if entry.key == "country_event"
        }
        for predecessor, number, empire, answer in (
            (26, 28, "Вейранской империи", "Я помню"),
            (28, 30, "Вейранская империя", "Я сюда не за этим пришёл"),
            (30, 32, "Вейранской империи", "Когда будет звонок?"),
            (32, 34, "Вейранской империи", "Оставьте открытой"),
        ):
            with self.subTest(number=number):
                source_id = f"ADISCORD_rus_campaign.{predecessor}"
                event_id = f"ADISCORD_rus_campaign.{number}"
                last_id = f"ADISCORD_rus_campaign.{number + 1}"
                immediate = block(events[source_id], "immediate")
                self.assertEqual([row.key for row in immediate], ["hidden_effect"])
                payload = block(immediate, "hidden_effect")
                self.assertEqual([row.key for row in payload], ["country_event"])
                scheduled = block(payload, "country_event")
                self.assertEqual(scalar(scheduled, "id"), event_id)
                self.assertEqual(scalar(scheduled, "days"), "90")
                world = self.world()
                self.assertNotIn(event_id, world.events)
                before = world.balances(), deepcopy(world.variables), set(world.flags)
                world.execute(immediate)
                self.assertEqual(world.events.count(event_id), 1)
                self.assertEqual((world.balances(), world.variables, world.flags), before)
                def executable(rows):
                    for row in rows:
                        if row.key == "effect_tooltip":
                            continue
                        yield row
                        if isinstance(row.value, list):
                            yield from executable(row.value)

                callers = [
                    name for name, rows in events.items()
                    for entry in executable(rows)
                    if entry.key == "country_event" and scalar(entry.value, "id") == event_id
                ]
                self.assertEqual(callers, [source_id])
                for option in (row.value for row in events[source_id] if row.key == "option"):
                    preview = block(option, "effect_tooltip")
                    self.assertEqual([row.key for row in preview], ["country_event"])
                    self.assertEqual(
                        [(row.key, row.value) for row in block(preview, "country_event")],
                        [(row.key, row.value) for row in scheduled],
                    )
                    self.assertFalse(any(row.key == "custom_effect_tooltip" for row in walk(option)))
                    selected = deepcopy(world)
                    selected.execute([row for row in option if row.key != "name"])
                    self.assertEqual(selected.events.count(event_id), 1)
                    self.assertEqual((selected.balances(), selected.variables, selected.flags), before)
                text = self.loc[event_id + ".d"] + self.loc[last_id + ".d"]
                self.assertIn("Марк Рустан", text)
                self.assertIn(empire, text)
                self.assertNotIn("Хан", text)
                self.assertEqual(self.loc[last_id + ".a"], answer)

    def test_perimeter_stories_are_guarded_discoveries_with_complete_translations(self):
        events = {
            scalar(entry.value, "id"): entry.value
            for entry in parse(f"events/{BASE}_events.txt")
            if entry.key == "country_event"
        }
        translations = {}
        for language in ("russian", "english"):
            raw = (ROOT / f"localisation/{language}/{BASE}_l_{language}.yml").read_bytes()
            self.assertTrue(raw.startswith(b"\xef\xbb\xbf"))
            translations[language] = dict(re.findall(
                r'^\s+([A-Za-z0-9_.]+):(?:\d+)?\s+"([^"\r\n]*)"\s*$',
                raw.decode("utf-8-sig"), re.M,
            ))
        for number in range(14, 26):
            name = f"ADISCORD_rus_campaign.{number}"
            event = events[name]
            self.assertEqual(scalar(event, "is_triggered_only"), "yes")
            self.assertEqual(scalar(event, "fire_only_once"), "yes")
            self.assertEqual(scalar(block(event, "trigger"), "RUS_khan_governing"), "yes")
            self.assertFalse(any(entry.key == "immediate" for entry in event))
            callers = []
            for focus, rows in self.focuses.items():
                reward = block(rows, "completion_reward")
                for entry in reward:
                    if entry.key == "hidden_effect":
                        callers.extend(
                            focus for child in walk(entry.value)
                            if child.key == "country_event" and scalar(child.value, "id") == name
                        )
            if number == 25:
                self.assertCountEqual(callers, [
                    "RUS_bunker_systems_college",
                    "RUS_bunker_emergency_rations",
                ])
            else:
                self.assertEqual(len(callers), 1, name)
            # Optional discoveries must remain reachable from either political course.
            pending = list(callers)
            visited = set()
            while pending:
                focus = pending.pop()
                if focus in visited:
                    continue
                visited.add(focus)
                self.assertNotIn(focus, {"RUS_scientists_council", "RUS_black_army_oath"})
                for entry in self.focuses[focus]:
                    if entry.key == "prerequisite":
                        pending.extend(child.value for child in entry.value if child.key == "focus")
            for language, loc in translations.items():
                for suffix in ("t", "d", "a"):
                    key = f"{name}.{suffix}"
                    self.assertIn(key, loc, language)
                    expanded = loc[key].replace("\\n", "\n")
                    self.assertLessEqual(len(expanded), 3000, key)
                    self.assertLessEqual(len(expanded.encode("utf-8")), 5500, key)
                    for forbidden in ("§Y", "\u2013", "\u2014"):
                        self.assertNotIn(forbidden, expanded, key)

    def test_lifecycle_hooks_and_independent_crisis_timer(self):
        on = block(parse("common/on_actions/01_ADISCORD_vorkerland_collapse_on_actions.txt"), "on_actions")
        for hook, effect in (("on_state_control_changed", "RUS_bunker_refresh"), ("on_puppet", "RUS_bunker_refresh"), ("on_subject_free", "RUS_bunker_refresh")):
            self.assertTrue(any(e.key == effect for e in walk(block(on, hook))), hook)
        startup = read("common/on_actions/00_ADISCORD_on_actions.txt")
        self.assertEqual(startup.count("RUS_campaign_initialize = yes"), 1)
        self.assertLess(startup.index("STP_initialize_core_mechanics"), startup.index("ADISCORD_economy_initialize_country"))
        self.assertLess(startup.index("ADISCORD_economy_initialize_country"), startup.index("RUS_campaign_initialize"))
        source = read("common/on_actions/01_ADISCORD_vorkerland_collapse_on_actions.txt")
        self.assertIn("FROM.FROM = { state = 66 }", source)
        self.assertFalse(any(e.key == "RUS_bunker_refresh" for e in walk(block(on, "on_monthly_RUS"))))
        self.assertTrue(any(e.key == "RUS_campaign_shutdown" for e in self.effects["RUS_crisis_dissolve_empire"]))
        self.assertFalse(any(e.key.startswith("RUS_bunker") for e in walk(self.effects["RUS_crisis_check_start"])))

    def test_bop_decisions_charge_exact_prices_and_reject_fractional_shortages(self):
        decisions = {entry.key: entry.value for entry in block(parse(f"common/decisions/{BASE}_decisions.txt"), "RUS_state_balance_measures_category")}
        prices = {"RUS_bop_relief": (0, "RUS_bunker_food", 30), "RUS_bop_reserve": (0, "RUS_bunker_food", 40), "RUS_bop_mediation": (20, "ADISCORD_economy_treasury", 65)}
        for name, (pp, resource, amount) in prices.items():
            rows = decisions[name]
            world = self.world()
            world.decisions = decisions
            world.pp = pp
            world.variables[resource] = amount
            world.bop = 0.45
            self.assertTrue(world.matches(block(rows, "custom_cost_trigger")), name)
            for shortage in (("pp", "resource") if pp else ("resource",)):
                rejected = deepcopy(world)
                if shortage == "pp":
                    rejected.pp -= 0.01
                else:
                    rejected.variables[resource] -= 0.01
                before = deepcopy(rejected.variables), rejected.pp, rejected.stability, rejected.manpower, rejected.bop, rejected.dirty
                self.assertFalse(rejected.matches(block(rows, "custom_cost_trigger")), (name, shortage))
                rejected.execute(block(rows, "complete_effect"))
                self.assertEqual((rejected.variables, rejected.pp, rejected.stability, rejected.manpower, rejected.bop, rejected.dirty), before, (name, shortage))
            spent = world.value("ADISCORD_economy_current_month_action_costs")
            world.begin(name)
            self.assertEqual(world.pp, 0, name)
            self.assertEqual(world.value(resource), 0, name)
            self.assertAlmostEqual(world.bop, 0.60 if name == "RUS_bop_reserve" else 0.30, msg=name)
            self.assertEqual(world.stability, 0.02 if name == "RUS_bop_relief" else 0, name)
            self.assertEqual(world.manpower, 1000 if name == "RUS_bop_reserve" else 0, name)
            self.assertEqual(world.value("ADISCORD_economy_current_month_action_costs") - spent, 65 if name == "RUS_bop_mediation" else 0, name)
            self.assertEqual(scalar(rows, "cost"), "0", name)
            self.assertEqual(scalar(rows, "days_re_enable"), "90", name)

    def test_bop_food_orders_refresh_hunger_without_touching_construction_receipt(self):
        decisions = {entry.key: entry.value for entry in block(parse(f"common/decisions/{BASE}_decisions.txt"), "RUS_state_balance_measures_category")}
        for name, food in (("RUS_bop_relief", 30), ("RUS_bop_reserve", 40)):
            world = self.world()
            world.focuses.discard("RUS_bunker_eternal_headquarters")
            world.variables.update({"RUS_bunker_depth": 1, "RUS_bunker_depth_limit": 3, "RUS_bunker_layer_1": 1, "RUS_bunker_food": food})
            world.run("RUS_bunker_refresh")
            org = world.value("RUS_bunker_army_org_factor")
            stability = world.value("RUS_bunker_stability_factor")
            world.begin("RUS_bunker_excavate")
            receipt = {key: value for key, value in world.variables.items() if key.startswith("RUS_bunker_escrow_") or key in ("RUS_bunker_project", "RUS_bunker_project_depth")}
            equipment = deepcopy(world.equipment)
            cash = world.value("ADISCORD_economy_treasury")
            world.decisions = {**world.decisions, **decisions}
            world.begin(name)
            self.assertEqual(world.value("RUS_bunker_food"), 0, name)
            self.assertIn("RUS_bunker_hunger", world.ideas, name)
            self.assertAlmostEqual(world.value("RUS_bunker_army_org_factor"), org, msg=name)
            self.assertAlmostEqual(world.value("RUS_bunker_stability_factor"), stability, msg=name)
            self.assertIn("RUS_bunker_excavate", world.active, name)
            self.assertEqual(world.equipment, equipment, name)
            self.assertEqual(world.value("ADISCORD_economy_treasury"), cash, name)
            self.assertEqual({key: world.variables[key] for key in receipt}, receipt, name)

    def test_bop_directions_and_eligibility_respect_exact_boundaries(self):
        decisions = {entry.key: entry.value for entry in block(parse(f"common/decisions/{BASE}_decisions.txt"), "RUS_state_balance_measures_category")}
        boundaries = {"RUS_bop_relief": ((-0.85, False), (-0.8499, True)), "RUS_bop_reserve": ((0.85, False), (0.8499, True)), "RUS_bop_mediation": ((-0.10, False), (0.10, False), (-0.1001, True), (0.1001, True))}
        for name, cases in boundaries.items():
            for value, available in cases:
                world = self.world()
                world.bop = value
                rows = decisions[name]
                self.assertEqual(world.matches(block(rows, "available")), available, (name, value))
                before = world.balances(), deepcopy(world.variables), world.bop
                world.execute(block(rows, "complete_effect"))
                if not available:
                    self.assertEqual((world.balances(), world.variables, world.bop), before, (name, value))
                elif name == "RUS_bop_mediation":
                    self.assertLess(abs(world.bop), abs(value))
                    self.assertLessEqual(abs(world.bop), 0.10)
        for name, rows in decisions.items():
            for failure in ("bop", "subject", "capitulated", "ruler", "phase"):
                world = self.world()
                world.bop = 0.45
                if failure == "bop":
                    world.bop_id = None
                elif failure in ("subject", "capitulated"):
                    setattr(world, failure, True)
                elif failure == "ruler":
                    world.ruler = "unrelated_ruler"
                else:
                    world.variables["RUS_crisis_phase"] = 4
                self.assertFalse(world.matches(block(rows, "available")), (name, failure))
                before = world.balances(), deepcopy(world.variables), world.bop
                world.execute(block(rows, "complete_effect"))
                self.assertEqual((world.balances(), world.variables, world.bop), before, (name, failure))

    def test_bop_ranges_cover_full_domain_and_initializer_preserves_current_value(self):
        balance = block(parse("common/bop/RUS.txt"), "RUS_state_balance")
        ranges = [entry.value for entry in walk(balance) if entry.key == "range"]
        intervals = sorted((float(scalar(rows, "min")), float(scalar(rows, "max"))) for rows in ranges)
        self.assertEqual(intervals, [(-1.0, -0.6), (-0.6, -0.1), (-0.1, 0.1), (0.1, 0.6), (0.6, 1.0)])
        for rows in ranges:
            for callback in ("on_activate", "on_deactivate"):
                self.assertTrue(any(entry.key == "ADISCORD_economy_mark_dirty" for entry in block(rows, callback)), (scalar(rows, "id"), callback))
        world = self.world()
        self.assertEqual(world.bop_id, "RUS_state_balance")
        self.assertEqual(world.bop, 0)
        world.bop = 0.45
        loaded = deepcopy(world)
        loaded.run("RUS_campaign_initialize")
        self.assertEqual(loaded.bop, 0.45)
        guarded = [entry.value for entry in self.effects["RUS_campaign_shutdown"] if entry.key == "if" and any(row.key == "remove_power_balance" for row in entry.value)]
        self.assertEqual(len(guarded), 1)
        self.assertEqual(scalar(block(block(guarded[0], "limit"), "has_power_balance"), "id"), "RUS_state_balance")
        loaded.variables["RUS_crisis_phase"] = 4
        loaded.run("RUS_campaign_shutdown")
        loaded.run("RUS_campaign_shutdown")
        self.assertIsNone(loaded.bop_id)

    def test_black_army_initial_vector_replaces_static_military_bonuses(self):
        world = self.world()
        mapping = {
            "army_org_factor": "RUS_army_org",
            "army_attack_factor": "RUS_army_attack",
            "conscription_factor": "RUS_army_recruitment",
            "ADISCORD_country_development_army_growth_factor": "RUS_army_growth",
            "special_forces_min": "RUS_army_special_forces_min",
            "casualty_trickleback": "RUS_army_casualty_return",
            "production_factory_max_efficiency_factor": "RUS_army_factory_efficiency",
            "air_accidents_factor": "RUS_air_accidents",
            "air_mission_efficiency": "RUS_air_mission_efficiency",
            "ground_attack_factor": "RUS_air_ground_attack",
            "army_defence_factor": "RUS_army_defence",
            "supply_consumption_factor": "RUS_army_supply",
            "land_reinforce_rate": "RUS_army_reinforce_rate",
            "army_speed_factor": "RUS_army_speed",
            "planning_speed": "RUS_army_planning",
            "training_time_army_factor": "RUS_army_training",
        }
        modifier = block(parse(f"common/dynamic_modifiers/ADISCORD_dynamic_modifiers_RUS.txt"), "RUS_black_army")
        actual = {entry.key: entry.value for entry in modifier if entry.key not in ("icon", "enable", "custom_modifier_tooltip")}
        self.assertEqual(actual, mapping)
        expected = {"RUS_army_org": 0.08, "RUS_army_attack": 0.05, "RUS_army_recruitment": 0.06, "RUS_army_growth": 0.05}
        for variable in mapping.values():
            self.assertAlmostEqual(world.value(variable), expected.get(variable, 0), msg=variable)
        self.assertIn("RUS_black_army", world.modifiers)
        static = block(block(parse("common/ideas/ADISCORD_RUS_ideas.txt"), "ideas"), "country")
        for name in ("RUS_aimaq_compact", "RUS_last_empire_spirit"):
            values = {entry.key for entry in block(block(static, name), "modifier")}
            self.assertFalse(values & mapping.keys(), name)

    def test_bookmark_previews_match_startup_and_are_never_installed(self):
        world = BunkerWorld(self, fresh=True)
        bookmark = block(block(parse("common/bookmarks/the_gathering_storm.txt"), "bookmarks"), "bookmark")
        displayed = {entry.value for entry in block(block(bookmark, "RUS"), "ideas")}
        previews = {"RUS_black_army_bookmark", "RUS_bunker_complex_bookmark"}
        self.assertEqual(displayed, previews | {"RUS_aimaq_compact"})
        dynamic = block(parse(f"common/dynamic_modifiers/ADISCORD_dynamic_modifiers_RUS.txt"), "RUS_black_army")
        initial = {row.key: world.value(row.value) for row in dynamic if isinstance(row.value, str) and row.value.startswith("RUS_army_") and world.value(row.value)}
        preview = {row.key: float(row.value) for row in block(self.ideas["RUS_black_army_bookmark"], "modifier")}
        self.assertEqual(preview, initial)
        self.assertFalse(any(row.key == "modifier" for row in self.ideas["RUS_bunker_complex_bookmark"]))
        for name in previews:
            self.assertEqual(scalar(block(self.ideas[name], "allowed"), "always"), "no")
            self.assertNotIn(name, world.ideas)
        definitions = {"common/ideas/ADISCORD_RUS_ideas.txt", "common/bookmarks/the_gathering_storm.txt"}
        for folder in ("common", "history", "events", "focus_trees"):
            for path in (ROOT / folder).rglob("*.txt"):
                if path.relative_to(ROOT).as_posix() not in definitions:
                    text = path.read_text(encoding="utf-8-sig")
                    self.assertFalse(any(name in text for name in previews), str(path))

    def test_black_army_organization_progresses_in_three_material_stages(self):
        world = self.world()
        names = ("RUS_muster_books", "RUS_reserve_rotations", "RUS_army_of_the_khanate")
        rifles = world.equipment["infantry_equipment"]
        for index, name in enumerate(names, 1):
            world.execute(block(self.focuses[name], "completion_reward"))
            expected = (0.10, 0.12, 0.15)[index - 1]
            self.assertAlmostEqual(world.value("RUS_army_org"), expected, msg=name)
        self.assertEqual(world.army_experience, 15)
        self.assertEqual(world.manpower, 16000)
        self.assertEqual(world.equipment["infantry_equipment"] - rifles, 32000)
        self.assertAlmostEqual(world.value("RUS_army_training"), -0.08)
        self.assertFalse(any(name.endswith("_delta") for name in world.ideas))
        self.assertNotIn("RUS_professional_service", world.ideas)

    def test_black_army_doctrines_keep_their_exact_previous_vectors(self):
        cases = {
            "RUS_patient_war": {"RUS_army_defence": 0.07, "RUS_army_supply": -0.05, "RUS_army_speed": -0.03},
            "RUS_swift_columns": {"RUS_army_speed": 0.08, "RUS_army_planning": 0.12, "RUS_army_supply": 0.06},
        }
        for name, expected in cases.items():
            world = self.world()
            before = {key: value for key, value in world.variables.items() if key.startswith("RUS_army_")}
            world.execute(block(self.focuses[name], "completion_reward"))
            for variable, value in before.items():
                self.assertAlmostEqual(world.value(variable) - value, expected.get(variable, 0), msg=(name, variable))
            self.assertEqual(world.ideas, {"limited_conscription"})
        for name in ("RUS_patient_doctrine", "RUS_swift_doctrine", "RUS_professional_service"):
            self.assertNotIn(name, self.ideas)

    def test_black_army_dummy_previews_mirror_real_focus_deltas(self):
        mapping = {
            "army_org_factor": "RUS_army_org",
            "army_attack_factor": "RUS_army_attack",
            "army_defence_factor": "RUS_army_defence",
            "supply_consumption_factor": "RUS_army_supply",
            "army_speed_factor": "RUS_army_speed",
            "planning_speed": "RUS_army_planning",
            "training_time_army_factor": "RUS_army_training",
        }
        cases = {
            "RUS_muster_books": "RUS_army_organization_delta",
            "RUS_reserve_rotations": "RUS_army_organization_delta",
            "RUS_army_of_the_khanate": "RUS_professional_service_delta",
            "RUS_patient_war": "RUS_patient_doctrine_delta",
            "RUS_swift_columns": "RUS_swift_doctrine_delta",
            "RUS_black_army_banner": "RUS_black_army_banner_delta",
            "RUS_watch_the_western_scar": "RUS_hazard_capacity_6_delta",
            "RUS_reactor_decontamination": "RUS_hazard_capacity_3_delta",
        }
        mapping["special_forces_min"] = "RUS_army_special_forces_min"
        for focus, idea in cases.items():
            world = self.world()
            before = {variable: world.value(variable) for variable in mapping.values()}
            reward = block(self.focuses[focus], "completion_reward")
            self.assertTrue(any(entry.key == "add_ideas" and entry.value == idea for entry in walk(block(reward, "effect_tooltip"))), focus)
            world.execute(reward)
            preview = {entry.key: float(entry.value) for entry in block(self.ideas[idea], "modifier")}
            self.assertLessEqual(preview.keys(), mapping.keys(), focus)
            for key, variable in mapping.items():
                self.assertAlmostEqual(world.value(variable) - before[variable], preview.get(key, 0), msg=(focus, key))
            self.assertNotIn(idea, world.ideas)
        self.assertEqual({entry.key: float(entry.value) for entry in block(self.ideas["RUS_black_army_banner_delta"], "modifier")}, {"army_org_factor": 0.03, "army_defence_factor": 0.05, "planning_speed": 0.03})

    def test_black_army_proclamation_delta_has_one_guarded_caller(self):
        helper = "RUS_black_army_empire_reform"
        callers = [name for name, body in self.effects.items() for entry in walk(body) if entry.key == helper]
        self.assertEqual(callers, ["ADISCORD_vorkerland_rus_proclaim_last_empire"])
        self.assertFalse(any(entry.key == helper for rows in self.focuses.values() for entry in walk(rows)))
        self.assertFalse(any(entry.key == helper for entry in walk(parse(f"common/decisions/{BASE}_decisions.txt"))))
        guarded = block(self.effects[callers[0]], "if")
        limit = block(guarded, "limit")
        self.assertTrue(any(entry.key == "has_country_flag" and entry.value == "ADISCORD_vorkerland_rus_last_empire_proclaimed" for entry in walk(block(limit, "NOT"))))
        world = self.world()
        world.triggers = dict(world.triggers)
        world.triggers["ADISCORD_vorkerland_rus_has_empire_territory"] = parse_clausewitz("always = yes")
        world.ruler = "RUS_Varlam_Oskol"
        self.assertFalse(world.matches(limit))
        world.ruler = "RUS_Mark_Rustan"
        self.assertTrue(world.matches(limit))
        before = dict(world.variables)
        world.execute([entry for entry in guarded if entry.key == "set_country_flag"])
        world.run(helper)
        self.assertFalse(world.matches(limit))
        mapping = {"army_org_factor": "RUS_army_org", "conscription_factor": "RUS_army_recruitment", "ADISCORD_country_development_army_growth_factor": "RUS_army_growth"}
        preview = {entry.key: float(entry.value) for entry in block(self.ideas["RUS_army_empire_delta"], "modifier")}
        self.assertEqual(preview, {"army_org_factor": 0.02, "conscription_factor": 0.02, "ADISCORD_country_development_army_growth_factor": 0.03})
        for key, variable in mapping.items():
            self.assertAlmostEqual(world.value(variable) - before[variable], preview[key])
        for variable, value in before.items():
            if variable.startswith("RUS_army_") and variable not in mapping.values():
                self.assertEqual(world.value(variable), value, variable)

    def test_black_army_survives_bunker_loss_and_country_subordination(self):
        army = block(parse(f"common/dynamic_modifiers/ADISCORD_dynamic_modifiers_RUS.txt"), "RUS_black_army")
        for changed in ("owner", "controller", "subject", "capitulated"):
            world = self.world()
            before = {key: value for key, value in world.variables.items() if key.startswith("RUS_army_")}
            setattr(world, changed, changed in ("subject", "capitulated"))
            world.run("RUS_bunker_weekly_supply")
            self.assertNotIn("RUS_bunker_complex", world.modifiers, changed)
            self.assertIn("RUS_black_army", world.modifiers, changed)
            self.assertTrue(world.matches(block(army, "enable")), changed)
            self.assertEqual({key: world.value(key) for key in before}, before, changed)

    def test_black_army_legal_rulers_and_terminal_cleanup_are_independent(self):
        dynamic = parse(f"common/dynamic_modifiers/ADISCORD_dynamic_modifiers_RUS.txt")
        army = block(block(dynamic, "RUS_black_army"), "enable")
        bunker = block(block(dynamic, "RUS_bunker_complex"), "enable")
        world = self.world()
        baseline = dict(world.variables)
        self.assertTrue(world.matches(army))
        self.assertTrue(world.matches(bunker))
        world.run("RUS_black_army_refresh")
        self.assertEqual(world.variables, baseline)
        for ruler in ("RUS_Varlam_Oskol", "unrelated_ruler"):
            world.ruler = ruler
            self.assertFalse(world.matches(army), ruler)
            self.assertFalse(world.matches(bunker), ruler)
        world.ruler = "RUS_Mark_Rustan"
        world.variables["RUS_crisis_phase"] = 4
        self.assertFalse(world.matches(army))
        self.assertFalse(world.matches(bunker))
        shutdown = self.effects["RUS_campaign_shutdown"]
        for modifier in ("RUS_black_army", "RUS_bunker_complex"):
            owners = [entry.value for entry in shutdown if entry.key == "if" and any(row.key == "remove_dynamic_modifier" and scalar(row.value, "modifier") == modifier for row in entry.value)]
            self.assertEqual(len(owners), 1, modifier)
            self.assertTrue(any(row.key == "has_dynamic_modifier" and scalar(row.value, "modifier") == modifier for row in walk(block(owners[0], "limit"))), modifier)
        world.run("RUS_campaign_shutdown")
        world.run("RUS_campaign_shutdown")
        world.run("RUS_black_army_refresh")
        self.assertFalse(world.modifiers)

    def test_black_army_current_state_survives_repeated_initialization(self):
        world = self.world()
        world.execute(block(self.focuses["RUS_muster_books"], "completion_reward"))
        world.execute(block(self.focuses["RUS_patient_war"], "completion_reward"))
        world.run("RUS_black_army_empire_reform")
        world.begin("RUS_bunker_excavate")
        loaded = deepcopy(world)
        before = deepcopy(loaded.variables), loaded.balances(), set(loaded.modifiers), set(loaded.active)
        loaded.run("RUS_campaign_initialize")
        loaded.run("RUS_campaign_initialize")
        self.assertEqual((loaded.variables, loaded.balances(), loaded.modifiers, loaded.active), before)
        loaded.run("RUS_bunker_weekly_supply")
        for key, value in before[0].items():
            if key.startswith("RUS_army_"):
                self.assertEqual(loaded.value(key), value, key)

    def test_black_army_delta_ideas_are_only_referenced_inside_previews(self):
        names = {
            "RUS_patient_doctrine_delta", "RUS_swift_doctrine_delta",
            "RUS_professional_service_delta", "RUS_army_organization_delta",
            "RUS_army_empire_delta", "RUS_black_army_banner_delta", "RUS_motor_pool_dispatch_delta",
        }
        previews = set()

        def inspect(rows, preview=False):
            for entry in rows:
                if entry.key in ("add_ideas", "add_timed_idea"):
                    values = {str(entry.value)} if not isinstance(entry.value, list) else {row.value for row in entry.value if isinstance(row.value, str)}
                    used = values & names
                    self.assertTrue(not used or preview, used)
                    previews.update(used)
                if isinstance(entry.value, list):
                    inspect(entry.value, preview or entry.key == "effect_tooltip")

        for body in (*self.effects.values(), *self.focuses.values(), parse(f"common/decisions/{BASE}_decisions.txt")):
            inspect(body)
        self.assertEqual(previews, names)
        for name in names:
            self.assertEqual(scalar(block(self.ideas[name], "allowed"), "always"), "no", name)

    def test_weekly_supply_steady_state_preserves_modifiers_and_economy_cache(self):
        world = self.world()
        dirty = world.dirty
        modifiers = set(world.modifiers)
        calls = []
        original = world.run

        def tracked(effect):
            calls.append(effect)
            original(effect)

        world.run = tracked
        for _ in range(52):
            world.run("RUS_bunker_weekly_supply")
        self.assertEqual(world.value("RUS_bunker_food"), 100)
        self.assertEqual(world.value("RUS_bunker_food_space"), 0)
        self.assertEqual(world.modifiers, modifiers)
        self.assertEqual(world.dirty, dirty)
        self.assertNotIn("RUS_bunker_refresh", calls)

    def test_weekly_supply_refreshes_exact_hunger_boundaries(self):
        world = self.world()
        world.focuses.discard("RUS_bunker_eternal_headquarters")
        world.variables.update({
            "RUS_bunker_depth": 3,
            "RUS_bunker_generators": 2,
            "RUS_bunker_layer_1": 1,
            "RUS_bunker_layer_2": 2,
            "RUS_bunker_layer_3": 1,
            "RUS_bunker_food": 1,
        })
        world.run("RUS_bunker_refresh")
        org = world.value("RUS_bunker_army_org_factor")
        stability = world.value("RUS_bunker_stability_factor")
        dirty = world.dirty
        world.run("RUS_bunker_weekly_supply")
        self.assertEqual(world.value("RUS_bunker_food"), 0)
        self.assertIn("RUS_bunker_hunger", world.ideas)
        self.assertAlmostEqual(world.value("RUS_bunker_army_org_factor"), org)
        self.assertEqual(world.dirty, dirty + 1)
        world.run("RUS_bunker_weekly_supply")
        self.assertEqual(world.dirty, dirty + 1)
        self.assertEqual(world.value("RUS_bunker_food"), 0)
        world.variables["RUS_bunker_food_output_bonus"] = 2
        world.run("RUS_bunker_refresh")
        dirty = world.dirty
        world.run("RUS_bunker_weekly_supply")
        self.assertEqual(world.value("RUS_bunker_food"), 1)
        self.assertNotIn("RUS_bunker_hunger", world.ideas)
        self.assertAlmostEqual(world.value("RUS_bunker_army_org_factor"), org)
        self.assertAlmostEqual(world.value("RUS_bunker_stability_factor"), stability)
        self.assertEqual(world.dirty, dirty + 1)

    def test_weekly_supply_cleans_unreported_loss_and_refunds_once(self):
        for changed in ("owner", "controller", "ruler", "subject", "capitulated"):
            world = self.world()
            balances = world.balances()
            world.begin("RUS_bunker_excavate")
            food = world.value("RUS_bunker_food")
            if changed == "ruler":
                world.ruler = "another_ruler"
            else:
                setattr(world, changed, changed in ("subject", "capitulated"))
            world.run("RUS_bunker_weekly_supply")
            self.assertEqual(world.balances(), balances, changed)
            self.assertEqual(world.value("RUS_bunker_food"), food, changed)
            self.assertEqual(world.value("RUS_bunker_food_output"), 0, changed)
            self.assertEqual(world.value("RUS_bunker_food_use"), 0, changed)
            self.assertNotIn("RUS_bunker_complex", world.modifiers, changed)
            self.assertNotIn("RUS_bunker_project", world.variables, changed)
            self.assertFalse(world.active, changed)
            dirty = world.dirty
            world.run("RUS_bunker_weekly_supply")
            world.finish("RUS_bunker_excavate")
            self.assertEqual(world.balances(), balances, changed)
            self.assertEqual(world.dirty, dirty, changed)
            self.assertEqual(world.value("RUS_bunker_food"), food, changed)

    def test_weekly_supply_restores_production_before_delivery(self):
        world = self.world()
        world.variables["RUS_bunker_depth"] = 1
        world.variables["RUS_bunker_layer_1"] = 1
        world.run("RUS_bunker_refresh")
        food = world.value("RUS_bunker_food")
        world.owner = False
        world.run("RUS_bunker_weekly_supply")
        self.assertEqual(world.value("RUS_bunker_food_balance"), 0)
        world.owner = True
        world.run("RUS_bunker_weekly_supply")
        self.assertEqual(world.value("RUS_bunker_food"), food + 1)
        self.assertEqual(world.value("RUS_bunker_food_output"), 2)
        self.assertEqual(world.value("RUS_bunker_food_use"), 1)
        self.assertEqual(world.value("RUS_bunker_food_space"), 100 - food - 1)
        self.assertIn("RUS_bunker_complex", world.modifiers)

    def test_weekly_supply_preserves_live_project_receipt_and_current_save_state(self):
        world = self.world()
        world.begin("RUS_bunker_excavate")
        paid = world.balances()
        receipt = {key: value for key, value in world.variables.items() if key.startswith("RUS_bunker_escrow_") or key in ("RUS_bunker_project", "RUS_bunker_project_depth")}
        active = set(world.active)
        world.run("RUS_bunker_weekly_supply")
        resumed = deepcopy(world)
        resumed.run("RUS_bunker_weekly_supply")
        self.assertEqual(resumed.balances(), paid)
        self.assertEqual(resumed.active, active)
        for key, value in receipt.items():
            self.assertEqual(resumed.variables[key], value, key)
        resumed.finish("RUS_bunker_excavate")
        self.assertEqual(resumed.value("RUS_bunker_depth"), 1)
        self.assertNotIn("RUS_bunker_project", resumed.variables)
        self.assertEqual(resumed.balances(), paid)

    def test_weekly_supply_clears_offline_aggregates_after_modifier_removal(self):
        world = self.world()
        food = world.value("RUS_bunker_food")
        world.variables["RUS_crisis_phase"] = 4
        world.run("RUS_campaign_shutdown")
        self.assertNotIn("RUS_bunker_complex", world.modifiers)
        self.assertGreater(world.value("RUS_bunker_food_output"), 0)
        world.run("RUS_bunker_weekly_supply")
        self.assertEqual(world.value("RUS_bunker_food_output"), 0)
        self.assertEqual(world.value("RUS_bunker_food_use"), 0)
        self.assertEqual(world.value("RUS_bunker_food_balance"), 0)
        self.assertEqual(world.value("RUS_bunker_food"), food)
        dirty = world.dirty
        world.run("RUS_bunker_weekly_supply")
        self.assertEqual(world.dirty, dirty)

    def test_faction_branches_keep_rustan_and_paid_orders_while_shifting_balance(self):
        routes = {
            "RUS_scientists_council": (-0.10, 0.60, 0.50),
            "RUS_scientists_workshops": (0, 0.50, 0.50),
            "RUS_scientists_power_compact": (-0.15, 0.60, 0.50),
            "RUS_black_army_oath": (0.10, 0.50, 0.60),
            "RUS_black_army_staff": (0, 0.50, 0.50),
            "RUS_black_army_banner": (0.15, 0.50, 0.60),
        }
        for focus, (movement, scientists, army) in routes.items():
            world = self.world()
            world.bop = 0.05
            world.variables["RUS_crisis_phase"] = 1
            world.variables["RUS_crisis_days"] = 61
            world.begin("RUS_bunker_excavate")
            receipt = {key: value for key, value in world.variables.items() if key.startswith("RUS_bunker_escrow_") or key in ("RUS_bunker_project", "RUS_bunker_project_depth")}
            active = set(world.active)
            reward = block(self.focuses[focus], "completion_reward")
            self.assertTrue(world.matches(block(self.focuses[focus], "available")), focus)
            world.execute(reward)
            self.assertEqual((world.ruler, world.ideology), ("RUS_Mark_Rustan", "etatism"), focus)
            self.assertAlmostEqual(world.bop, 0.05 + movement, msg=focus)
            self.assertAlmostEqual(world.value("RUS_scientists_support"), scientists, msg=focus)
            self.assertAlmostEqual(world.value("RUS_black_army_support"), army, msg=focus)
            self.assertEqual(world.active, active, focus)
            self.assertEqual(world.value("RUS_crisis_days"), 61, focus)
            for key, value in receipt.items():
                self.assertEqual(world.variables[key], value, (focus, key))
            shown = {entry.value for entry in walk(reward) if entry.key == "custom_effect_tooltip"}
            if movement:
                side = "scientists" if movement < 0 else "black_army"
                self.assertIn(f"RUS_course_{side}_{round(abs(movement) * 100)}_tt", shown, focus)
                self.assertIn(f"RUS_support_{side}_10_tt", shown, focus)
                for key in (f"RUS_course_{side}_{round(abs(movement) * 100)}_tt", f"RUS_support_{side}_10_tt"):
                    self.assertIn(key, self.loc, key)

    def test_faction_branches_and_governance_fork_have_one_route_each(self):
        self.assertEqual(scalar(block(self.focuses["RUS_scientists_council"], "prerequisite"), "focus"), "RUS_count_the_hearths")
        self.assertEqual(scalar(block(self.focuses["RUS_black_army_oath"], "prerequisite"), "focus"), "RUS_count_the_hearths")
        self.assertFalse({"RUS_aimaq_council", "RUS_seal_chancery", "RUS_state_budget"} & self.focuses.keys())
        for child, course in (("RUS_local_service_committees", "RUS_scientists_council"),
                              ("RUS_district_representation", "RUS_scientists_council"),
                              ("RUS_inspection_chamber", "RUS_black_army_oath"),
                              ("RUS_military_governors", "RUS_black_army_oath")):
            self.assertEqual(scalar(block(self.focuses[child], "prerequisite"), "focus"), course)
        for focus, other in (("RUS_scientists_council", "RUS_black_army_oath"), ("RUS_black_army_oath", "RUS_scientists_council")):
            self.assertEqual(scalar(block(self.focuses[focus], "mutually_exclusive"), "focus"), other)
        removed = {"RUS_reaffirm_khan", "RUS_army_mandate", "RUS_reconstruction_cabinet", "RUS_political_course_chosen", "RUS_political_choice_open"}
        self.assertFalse(removed & self.focuses.keys())
        self.assertFalse(removed & self.triggers.keys())
        sources = [read(f"common/{path}") for path in (
            f"decisions/{BASE}_decisions.txt", f"scripted_effects/ADISCORD_vorkerland_effects.txt",
            "scripted_effects/ADISCORD_RUS_scripted_effects.txt",
            f"scripted_triggers/ADISCORD_RUS_scripted_triggers.txt", f"dynamic_modifiers/ADISCORD_dynamic_modifiers_RUS.txt",
            f"ai_strategy_plans/{BASE}_plans.txt")] + [read("focus_trees/RUS/main/focuses.txt"), read(f"events/{BASE}_events.txt")]
        for source in sources:
            for name in removed | {"RUS_Pavel_Niva", "character = RUS_Varlam_Oskol"}:
                self.assertNotIn(name, source)

    def test_proclamation_has_no_course_gate_and_names_three_forms(self):
        proclaim = self.effects["ADISCORD_vorkerland_rus_proclaim_last_empire"]
        native_decision = next(entry.value for entry in walk(parse(f"common/decisions/{BASE}_decisions.txt")) if entry.key == "RUS_proclaim_the_last_empire")
        for rows in (proclaim, native_decision):
            self.assertFalse(any(entry.key == "RUS_political_course_chosen" for entry in walk(rows)))
        self.assertFalse(any(entry.value == "chauvinism" for entry in walk(proclaim) if isinstance(entry.value, str)))
        self.assertEqual({entry.value for entry in walk(proclaim) if entry.key == "set_cosmetic_tag"}, {"RUS_last_empire", "RUS_black_banner_empire", "RUS_restoration_state"})
        superevent = self.effects["ADISCORD_vorkerland_show_last_empire_superevent"]
        self.assertEqual({entry.value for entry in walk(superevent) if entry.key == "has_cosmetic_tag"}, {"RUS_black_banner_empire", "RUS_restoration_state"})

    def test_faction_support_pays_power_and_pulls_balance_only_above_half(self):
        world = self.world()
        self.assertIn("RUS_faction_support", world.modifiers)
        self.assertEqual((world.value("RUS_black_army_support"), world.value("RUS_scientists_support")), (0.5, 0.5))
        self.assertEqual(world.value("RUS_faction_political_power_gain"), 0)
        self.assertEqual(world.value("RUS_faction_power_balance_weekly"), 0)
        cases = {
            (0.8, 0.5): (0.06, 0.009),
            (0.5, 0.9): (0.08, -0.012),
            (0.2, 0.3): (-0.10, 0),
            (1.0, 1.0): (0.20, 0),
            (1.0, 0.0): (0.0, 0.015),
        }
        for (army, scientists), (power, weekly) in cases.items():
            world = self.world()
            world.temporary.update({"RUS_black_army_support_delta": army - 0.5, "RUS_scientists_support_delta": scientists - 0.5})
            world.run("RUS_faction_support_change")
            self.assertAlmostEqual(world.value("RUS_faction_political_power_gain"), power, msg=(army, scientists))
            self.assertAlmostEqual(world.value("RUS_faction_power_balance_weekly"), weekly, msg=(army, scientists))
        world = self.world()
        world.temporary.update({"RUS_black_army_support_delta": 0.9, "RUS_scientists_support_delta": -0.9})
        world.run("RUS_faction_support_change")
        self.assertEqual((world.value("RUS_black_army_support"), world.value("RUS_scientists_support")), (1, 0))
        modifier = block(parse(f"common/dynamic_modifiers/ADISCORD_dynamic_modifiers_RUS.txt"), "RUS_faction_support")
        self.assertEqual(scalar(modifier, "political_power_gain"), "RUS_faction_political_power_gain")
        self.assertEqual(scalar(modifier, "power_balance_weekly"), "RUS_faction_power_balance_weekly")
        self.assertEqual(scalar(block(modifier, "enable"), "RUS_state_balance_operational"), "yes")
        world.variables["RUS_crisis_phase"] = 4
        world.run("RUS_campaign_shutdown")
        world.run("RUS_faction_support_refresh")
        self.assertNotIn("RUS_faction_support", world.modifiers)

    def test_balance_measures_move_faction_support(self):
        expected = {"RUS_bop_relief": (0.65, 0.40), "RUS_bop_reserve": (0.40, 0.65), "RUS_bop_mediation": (0.55, 0.55)}
        for name, (scientists, army) in expected.items():
            world = self.world()
            world.decisions = {**world.decisions, **self.balance}
            world.bop = 0.45
            world.begin(name)
            self.assertAlmostEqual(world.value("RUS_scientists_support"), scientists, msg=name)
            self.assertAlmostEqual(world.value("RUS_black_army_support"), army, msg=name)
            tooltips = {entry.value for entry in walk(block(self.balance[name], "complete_effect")) if entry.key == "custom_effect_tooltip"}
            self.assertTrue(tooltips <= self.loc.keys(), tooltips - self.loc.keys())

    def test_empire_defeat_retires_actual_ruler_and_keeps_narrative_receipt(self):
        world = self.world()
        retained = world.characters - {world.ruler}
        world.run("RUS_retire_current_ruler")
        self.assertIsNone(world.ruler)
        self.assertEqual(world.characters, retained)
        defeat = self.effects["RUS_crisis_dissolve_empire"]
        self.assertTrue(any(entry.key == "RUS_retire_current_ruler" for entry in defeat))
        winner = next(entry.value for entry in defeat if entry.key == "event_target:RUS_crisis_hegemon")
        settlement_events = [
            entry for entry in walk(winner)
            if entry.key == "country_event" and scalar(entry.value, "id") == "ADISCORD_rus_crisis.4"
        ]
        self.assertEqual(len(settlement_events), 1)
        receipts = [entry.value for entry in walk(winner) if entry.key == "set_variable" and scalar(entry.value, "var") == "RUS_crisis_defeated_course"]
        self.assertEqual({scalar(rows, "value") for rows in receipts}, {"1", "2", "3"})

    def test_reactor_restoration_returns_exactly_the_buried_deposits(self):
        from tools.builders.build_adiscord_new_states import REACTOR_STATE_RESOURCES
        full = {
            176: {"steel": 120, "tungsten": 60, "chromium": 40},
            177: {"steel": 80, "aluminium": 100, "rare_components": 8, "rare_alloys": 6},
            187: {"steel": 80, "aluminium": 40, "chromium": 40},
            188: {"steel": 100, "tungsten": 60, "chromium": 80},
            189: {"steel": 120, "aluminium": 60, "rare_components": 12, "rare_alloys": 6},
            192: {"steel": 80, "aluminium": 60, "tungsten": 40, "rare_alloys": 8},
        }
        restored = {}
        for entry in self.effects["RUS_reactor_works_restore_resources"]:
            state = int(scalar(block(entry.value, "limit"), "state"))
            restored[state] = {scalar(row.value, "type"): int(scalar(row.value, "amount")) for row in entry.value if row.key == "add_resource"}
        self.assertEqual(set(restored), set(full))
        for state, totals in full.items():
            surface = REACTOR_STATE_RESOURCES[state]
            self.assertEqual(set(surface), set(totals), state)
            for resource, amount in totals.items():
                self.assertEqual(surface[resource] + restored[state][resource], amount, (state, resource))
                self.assertLessEqual(surface[resource] * 2, amount, (state, resource))
            source = read(f"history/states/{state}-{state}.txt")
            for resource, amount in surface.items():
                self.assertRegex(source, rf"(?m)^\s*{resource} = {amount}\s*$")

    def test_reactor_restoration_is_one_paid_project_with_full_refund(self):
        decision = self.belt["RUS_restore_reactor_works"]
        self.assertEqual([row.value for row in block(decision, "targets")], ["176", "177", "187", "188", "189", "192"])
        self.assertEqual(scalar(decision, "cost"), "0")
        self.assertEqual(scalar(decision, "custom_cost_text"), "RUS_restore_reactor_works_cost")
        self.assertEqual(scalar(block(decision, "custom_cost_trigger"), "RUS_reactor_works_affordable"), "yes")
        self.assertTrue(any(entry.key == "RUS_reactor_works_refund" for entry in walk(block(decision, "cancel_effect"))))
        self.assertTrue(any(entry.key == "RUS_reactor_works_idle" for entry in walk(block(decision, "available"))))
        begin = block(self.effects["RUS_reactor_works_begin"], "if")
        self.assertEqual(scalar(begin, "add_political_power"), "-50")
        debits = [entry.value for entry in begin if entry.key == "subtract_from_variable"]
        self.assertEqual([(scalar(row, "var"), scalar(row, "value")) for row in debits], [("ADISCORD_economy_treasury", "135")])
        refund = block(self.effects["RUS_reactor_works_refund"], "if")
        self.assertEqual(scalar(refund, "add_political_power"), "50")
        self.assertEqual(scalar(block(refund, "limit"), "has_variable"), "RUS_reactor_works_deposit")
        self.assertEqual(refund[1].key, "clear_variable", "The deposit is cleared before any payout")
        world = self.world()
        world.pp = 50
        world.variables["ADISCORD_economy_treasury"] = 135
        self.assertTrue(world.matches(self.triggers["RUS_reactor_works_affordable"]))
        world.variables["ADISCORD_economy_treasury"] = 134.99
        self.assertFalse(world.matches(self.triggers["RUS_reactor_works_affordable"]))
        world.variables["ADISCORD_economy_treasury"] = 135
        world.variables["RUS_reactor_works_deposit"] = 135
        before = world.pp, world.value("ADISCORD_economy_treasury")
        self.assertFalse(world.matches(self.triggers["RUS_reactor_works_idle"]))
        shutdown = self.effects["RUS_campaign_shutdown"]
        self.assertTrue(any(entry.key == "RUS_reactor_works_refund" for entry in shutdown))
        self.assertEqual(before, (50, 135))

    def test_reactor_sortie_charges_supplies_once_and_preserves_its_quoted_haul(self):
        for decontaminated, supplies, haul in ((False, 40, 50), (True, 20, 85)):
            world = self.world()
            world.decisions = {**world.decisions, **self.belt}
            world.held_states = {"188"}
            world.manpower = 1000
            world.equipment["support_equipment"] = supplies
            if not decontaminated:
                world.focuses.discard("RUS_reactor_decontamination")
            short = deepcopy(world)
            short.equipment["support_equipment"] = supplies - 0.01
            self.assertFalse(short.matches(block(self.belt["RUS_reactor_sortie"], "custom_cost_trigger")))
            pp, cash = world.pp, world.value("ADISCORD_economy_treasury")
            world.begin("RUS_reactor_sortie")
            self.assertEqual((world.pp, world.manpower, world.equipment["support_equipment"]), (pp - 25, 1000, 0))
            self.assertFalse(world.matches(block(self.belt["RUS_reactor_sortie"], "available")))
            world.run("RUS_reactor_sortie_begin")
            self.assertEqual(world.pp, pp - 25)
            world.focuses.add("RUS_reactor_decontamination")
            world.finish("RUS_reactor_sortie")
            self.assertEqual(world.value("ADISCORD_economy_treasury"), cash + haul)
            self.assertAlmostEqual(world.value("RUS_scientists_support"), 0.55)
            world.execute(block(self.belt["RUS_reactor_sortie"], "remove_effect"))
            self.assertEqual(world.value("ADISCORD_economy_treasury"), cash + haul)
            world.held_states = set()
            self.assertTrue(world.matches(block(self.belt["RUS_reactor_sortie"], "cancel_trigger")))
        for focus in ("RUS_reactor_belt_inventory", "RUS_reactor_foundries", "RUS_reactor_sorties", "RUS_reactor_decontamination"):
            self.assertIn(focus, self.loc)
            self.assertIn(f"{focus}_desc", self.loc)

    def lab_world(self):
        world = self.world()
        world.decisions = {**world.decisions, **self.labs}
        world.held_states = {"177"}
        world.manpower = 400
        return world

    def test_destroyed_world_closes_khan_government_and_laboratory_work(self):
        world = self.lab_world()
        self.assertTrue(world.matches(world.triggers["RUS_khan_governing"]))
        world.global_flags.add("RUS_crisis_world_ended")
        self.assertFalse(world.matches(world.triggers["RUS_khan_governing"]))
        self.assertFalse(world.matches(block(self.labs["RUS_lab_reactor_alloys"], "available")))

    def test_lab_projects_require_a_reactor_zone_and_one_slot_on_both_courses(self):
        focus = self.focuses["RUS_experimental_laboratories"]
        self.assertEqual({row.value for row in block(focus, "prerequisite")}, {"RUS_bunker_science_wing", "RUS_engineers_collegium"})
        self.assertTrue(any(entry.key == "RUS_lab_reactor_access" for entry in walk(block(focus, "available"))))
        self.assertEqual([entry.value for entry in walk(block(focus, "completion_reward")) if entry.key == "unlock_decision_tooltip"], ["RUS_lab_reactor_alloys"])
        alloys = self.labs["RUS_lab_reactor_alloys"]
        world = self.lab_world()
        world.held_states = set()
        self.assertFalse(world.matches(block(alloys, "available")))
        self.assertFalse(world.matches(block(focus, "available")))
        for state in ("176", "177", "188", "192"):
            world.held_states = {state}
            self.assertTrue(world.matches(block(alloys, "available")), state)
            self.assertTrue(world.matches(block(focus, "available")), state)
        for position in (-1, -0.60, 0, 0.6001, 1):
            world.bop = position
            self.assertTrue(world.matches(block(alloys, "available")), position)
        world.begin("RUS_lab_reactor_alloys")
        self.assertFalse(world.matches(block(alloys, "available")))
        self.assertFalse(world.matches(block(self.labs["RUS_lab_zeppelin"], "visible")))
        world.owner = False
        self.assertTrue(world.matches(block(alloys, "cancel_trigger")))

    def test_lab_projects_charge_exact_prices_and_settle_once(self):
        world = self.lab_world()
        pp, cash = world.pp, world.value("ADISCORD_economy_treasury")
        world.begin("RUS_lab_reactor_alloys")
        self.assertEqual((world.pp, world.value("ADISCORD_economy_treasury")), (pp - 50, cash - 100))
        world.finish("RUS_lab_reactor_alloys")
        self.assertEqual(world.tech_bonuses, ["RUS_lab_reactor_alloys"])
        self.assertIn("RUS_lab_reactor_alloys_completed", world.flags)
        self.assertNotIn("RUS_lab_project", world.variables)
        self.assertAlmostEqual(world.value("RUS_scientists_support"), 0.60)
        self.assertAlmostEqual(world.value("RUS_black_army_support"), 0.45)
        world.execute(block(self.labs["RUS_lab_reactor_alloys"], "remove_effect"))
        self.assertEqual(world.tech_bonuses, ["RUS_lab_reactor_alloys"])
        zeppelin = self.labs["RUS_lab_zeppelin"]
        self.assertTrue(world.matches(block(zeppelin, "visible")))
        for shortage in ("pp", "cash", "manpower"):
            short = deepcopy(world)
            if shortage == "pp":
                short.pp = 99.99
            elif shortage == "cash":
                short.variables["ADISCORD_economy_treasury"] = 334.99
            else:
                short.manpower = 399.99
            self.assertFalse(short.matches(block(zeppelin, "custom_cost_trigger")), shortage)
        pp, cash, divisions = world.pp, world.value("ADISCORD_economy_treasury"), world.divisions
        world.begin("RUS_lab_zeppelin")
        self.assertEqual((world.pp, world.value("ADISCORD_economy_treasury"), world.manpower), (pp - 100, cash - 335, 0))
        world.finish("RUS_lab_zeppelin")
        self.assertEqual(world.divisions, divisions + 1)
        self.assertEqual(world.templates, {"Khanate Airship"})
        self.assertIn("RUS_lab_zeppelin_delivered", world.flags)
        self.assertFalse(world.matches(block(zeppelin, "visible")))
        self.assertAlmostEqual(world.value("RUS_scientists_support"), 0.70)
        self.assertAlmostEqual(world.value("RUS_black_army_support"), 0.55)
        world.execute(block(zeppelin, "remove_effect"))
        self.assertEqual(world.divisions, divisions + 1)

    def test_lab_loss_or_shutdown_refunds_the_whole_receipt_once(self):
        for ending in ("reactor", "cancel_after_shutdown", "late_finish"):
            world = self.lab_world()
            world.flags.add("RUS_lab_reactor_alloys_completed")
            before = world.pp, world.value("ADISCORD_economy_treasury"), world.manpower
            world.begin("RUS_lab_zeppelin")
            zeppelin = self.labs["RUS_lab_zeppelin"]
            if ending == "reactor":
                world.held_states = set()
                self.assertTrue(world.matches(block(zeppelin, "cancel_trigger")))
                world.execute(block(zeppelin, "cancel_effect"))
            elif ending == "cancel_after_shutdown":
                world.variables["RUS_crisis_phase"] = 4
                world.run("RUS_campaign_shutdown")
                world.execute(block(zeppelin, "cancel_effect"))
            else:
                world.held_states = set()
                world.finish("RUS_lab_zeppelin")
            self.assertEqual((world.pp, world.value("ADISCORD_economy_treasury"), world.manpower), before, ending)
            self.assertNotIn("RUS_lab_project", world.variables, ending)
            self.assertNotIn("RUS_lab_zeppelin", world.active, ending)
            self.assertNotIn("RUS_lab_zeppelin_delivered", world.flags, ending)
            self.assertEqual(world.templates, set(), ending)
            world.run("RUS_lab_refund")
            self.assertEqual((world.pp, world.value("ADISCORD_economy_treasury"), world.manpower), before, ending)

    def test_airship_spawn_uses_locked_unique_template_and_registered_texts(self):
        spawn = self.effects["RUS_lab_spawn_zeppelin"]
        guarded = block(spawn, "if")
        template = block(guarded, "division_template")
        name = scalar(template, "name")
        self.assertEqual(scalar(block(block(guarded, "limit"), "NOT"), "has_template"), name)
        self.assertEqual(scalar(template, "is_locked"), "yes")
        self.assertEqual(scalar(template, "override_model"), "ADISCORD_zeppelin_entity")
        self.assertEqual([entry.key for entry in block(template, "regiments")], ["ADISCORD_zeppelin"])
        create = block(block(spawn, "capital_scope"), "create_unit")
        self.assertEqual(scalar(create, "owner"), "RUS")
        self.assertEqual(scalar(create, "allow_spawning_on_enemy_provs"), "no")
        self.assertIn(f'division_template = "{name}"', scalar(create, "division"))
        equipment = block(block(parse("common/units/equipment/ADISCORD_air_equipment.txt"), "equipments"), "ADISCORD_zeppelin_equipment_1")
        self.assertNotIn("RUS", [entry.value for entry in walk(block(equipment, "can_be_produced"))])
        english = dict(re.findall(r'^\s+([A-Za-z0-9_.]+):(?:\d+)?\s+"(.*)"\s*$', read(f"localisation/english/{BASE}_l_english.yml"), re.M))
        for name, rows in self.labs.items():
            keys = {name, f"{name}_desc", scalar(rows, "custom_cost_text")}
            keys |= {f"{scalar(rows, 'custom_cost_text')}_{suffix}" for suffix in ("blocked", "tooltip")}
            keys |= {entry.value for entry in walk(rows) if entry.key in ("tooltip", "custom_effect_tooltip")}
            self.assertTrue(keys <= self.loc.keys(), keys - self.loc.keys())
            self.assertTrue(keys <= english.keys(), keys - english.keys())

    def test_modernization_replaces_only_the_starting_laws(self):
        cases = (
            ("RUS_power_grid", "ADISCORD_economic_system_agrarian", "ADISCORD_economic_system_industrializing", "ADISCORD_economic_system_mixed"),
            ("RUS_industrial_belt", "ADISCORD_society_type_traditional", "ADISCORD_society_type_industrial", "ADISCORD_society_type_information"),
            ("RUS_school_of_scribes", "ADISCORD_education_informal_instruction", "ADISCORD_education_basic_schools", "ADISCORD_education_technical_institutes"),
            ("RUS_civilian_shift", "ADISCORD_labor_policy_guild_protections", "ADISCORD_labor_policy_regulated_shifts", "ADISCORD_labor_policy_collective_bargaining"),
            ("RUS_district_ledger", "ADISCORD_taxation_light_dues", "ADISCORD_taxation_balanced_register", "ADISCORD_taxation_progressive_brackets"),
            ("RUS_covenant_of_service", "ADISCORD_welfare_charity_relief", "ADISCORD_welfare_basic_services", "ADISCORD_welfare_universal_provision"),
            ("RUS_scientists_power_compact", "ADISCORD_education_basic_schools", "ADISCORD_education_technical_institutes", "ADISCORD_education_elite_academies"),
            ("RUS_black_army_banner", "ADISCORD_logistics_local_foraging", "ADISCORD_logistics_centralized_depots", "ADISCORD_logistics_motorized_supply"),
        )
        for focus, starting, target, advanced in cases:
            for current in (starting, advanced):
                with self.subTest(focus=focus, current=current):
                    world = self.world()
                    world.ideas.add(current)
                    dirty = world.dirty
                    world.execute(block(self.focuses[focus], "completion_reward"))
                    if current == starting:
                        self.assertIn(target, world.ideas)
                        self.assertNotIn(starting, world.ideas)
                        self.assertGreater(world.dirty, dirty)
                    else:
                        self.assertIn(advanced, world.ideas)
                        self.assertNotIn(target, world.ideas)
        for route, kind in (("RUS_scientists_workshops", "industrial_complex"), ("RUS_black_army_staff", "arms_factory")):
            world = self.world()
            before = world.buildings.copy()
            world.execute(block(self.focuses[route], "completion_reward"))
            self.assertEqual(world.buildings[kind], before[kind] + 1)

    def test_hazard_rewards_deliver_fixed_recruitable_formations_on_both_focuses(self):
        world = self.world()
        template = block(block(self.effects["RUS_prepare_hazard_template"], "if"), "division_template")
        regiments = block(template, "regiments")
        self.assertEqual([row.key for row in regiments], ["ADISCORD_hazard_infantry"] * 3)
        self.assertEqual(scalar(template, "is_locked"), "yes")
        subunit = block(block(parse("common/units/ADISCORD_land_units.txt"), "sub_units"), "ADISCORD_hazard_infantry")
        need = {row.key: float(row.value) for row in block(subunit, "need")}
        self.assertEqual({key: value * 3 for key, value in need.items()}, {
            "infantry_equipment": 2700, "ADISCORD_squad_weapons_equipment": 108, "support_equipment": 60,
        })
        self.assertEqual(float(scalar(subunit, "manpower")) * 3, 3000)
        stock = world.equipment.copy()
        for focus, count in (("RUS_watch_the_western_scar", 2), ("RUS_reactor_decontamination", 1)):
            before = world.divisions
            world.execute(block(self.focuses[focus], "completion_reward"))
            self.assertEqual(world.divisions, before + count)
            division, actual_count = world.created_units[-1]
            self.assertEqual(actual_count, count)
            self.assertIn('division_template = "Khanate CBRN Brigade"', division)
            self.assertIn("start_manpower_factor = 1.0", division)
            self.assertIn("start_equipment_factor = 1.0", division)
            self.assertIn("ADISCORD_tech_radiation_patrols", world.technologies)
            self.assertIn("Khanate CBRN Brigade", world.recruitable_templates)
        self.assertEqual(world.equipment, stock)
        self.assertEqual(world.templates, {"Khanate CBRN Brigade"})
        self.assertEqual(sum(count for _, count in world.created_units) * len(regiments), 9)
        self.assertEqual(world.value("RUS_army_special_forces_min"), 9)
        self.assertFalse(any(name.startswith("RUS_hazard_capacity_") for name in world.ideas))

    def test_completed_bunker_rooms_open_national_programmes_and_improve_delivery(self):
        category = block(parse(f"common/decisions/categories/ADISCORD_decision_categories_RUS.txt"), "RUS_development_programmes")
        for room, programme, direction in (("RUS_bunker_layer_3", "RUS_workshop_training", "economic"), ("RUS_bunker_layer_4", "RUS_district_health_programme", "social_system")):
            world = self.world()
            world.focuses = set()
            world.variables[room] = 1
            world.decisions.update(self.programmes)
            self.assertTrue(world.matches(block(category, "visible")))
            self.assertTrue(world.matches(block(world.decisions[programme], "visible")))
            before = world.pp, world.value("ADISCORD_economy_treasury")
            world.begin(programme)
            self.assertEqual((world.pp, world.value("ADISCORD_economy_treasury")), (before[0] - 25, before[1] - 35))
            self.assertEqual(world.value(f"ADISCORD_{direction}_development_progress"), 40)
            world.owner = False
            world.run("RUS_bunker_refresh")
            self.assertEqual(world.value(f"ADISCORD_{direction}_development_progress"), 40)
            self.assertFalse(world.matches(block(world.decisions[programme], "available")))
        world = self.world()
        world.focuses = set()
        world.variables["RUS_bunker_layer_3"] = 1
        stock = world.equipment["support_equipment"]
        world.begin("RUS_engineering_order")
        self.assertEqual(world.equipment["support_equipment"], stock + 150)
        for installed, active, expected in ((2, True, 2), (0, True, 1), (2, False, 0)):
            world = self.lab_world()
            world.variables["RUS_bunker_layer_4"] = installed
            world.begin("RUS_lab_reactor_alloys")
            world.owner = active
            world.finish("RUS_lab_reactor_alloys")
            self.assertEqual(len(world.tech_bonuses), expected)

    def test_sortie_cancellation_and_late_callbacks_never_pay_or_charge_twice(self):
        for ending in ("cancel", "late_finish", "shutdown"):
            world = self.world()
            world.decisions.update(self.belt)
            world.held_states = {"176"}
            before = world.balances()
            world.begin("RUS_reactor_sortie")
            world.held_states = set()
            if ending == "cancel":
                world.execute(block(self.belt["RUS_reactor_sortie"], "cancel_effect"))
            elif ending == "shutdown":
                world.run("RUS_campaign_shutdown")
            world.finish("RUS_reactor_sortie")
            world.finish("RUS_reactor_sortie")
            self.assertEqual(world.balances(), (before[0] - 25, before[1], before[2] - 20))
            self.assertNotIn("RUS_reactor_sortie_receipt", world.variables)

    def test_both_courses_finish_the_airship_even_at_extreme_balance(self):
        for route, opposite, position in (("RUS_scientists_council", "RUS_black_army_oath", -1), ("RUS_black_army_oath", "RUS_scientists_council", 1)):
            world = self.lab_world()
            world.focuses = {route, "RUS_experimental_laboratories"}
            world.bop = position
            world.begin("RUS_lab_reactor_alloys")
            world.finish("RUS_lab_reactor_alloys")
            self.assertTrue(world.matches(block(self.labs["RUS_lab_zeppelin"], "visible")))
            before = world.divisions
            world.begin("RUS_lab_zeppelin")
            world.bop = -position
            self.assertFalse(world.matches(block(self.labs["RUS_lab_zeppelin"], "cancel_trigger")))
            world.finish("RUS_lab_zeppelin")
            self.assertEqual(world.divisions, before + 1)
            self.assertNotIn(opposite, world.focuses)
            self.assertIn("RUS_lab_zeppelin_delivered", world.flags)

    def test_ai_order_has_no_duplicates_and_keeps_crisis_preparations_together(self):
        plan = block(parse(f"common/ai_strategy_plans/{BASE}_plans.txt"), "ADISCORD_vorkerland_rus_last_empire_plan")
        order = [e.value for e in block(plan, "ai_national_focuses")]
        self.assertEqual(len(order), len(set(order)))
        self.assertTrue(set(order) <= self.focuses.keys())
        self.assertLess(order.index("RUS_bunker_survey"), order.index("RUS_claim_the_opened_zone"))
        start = order.index("RUS_imperial_general_staff")
        self.assertEqual(order[start:start + 4], ["RUS_imperial_general_staff", "RUS_western_supply_lines", "RUS_imperial_arsenals", "RUS_aimaq_reserve"])

    def test_prewar_aviation_finishes_without_war_empire_or_bunker(self):
        order = (
            "summon_the_aimaqs", "flight_school", "capital_airfields", "fighter_cover",
            "assault_squadrons", "aviation_fuel_reserve", "aircraft_workshops",
            "air_control_network", "air_ground_coordination",
        )
        for course, balance in (("scientists_council", -1), ("black_army_oath", 1)):
            world = BunkerWorld(self, fresh=True)
            world.war = False
            world.bop = balance
            world.focuses = {"RUS_" + course}
            days = 0
            for suffix in order:
                name = "RUS_" + suffix
                rows = self.focuses[name]
                for group in (row.value for row in rows if row.key == "prerequisite"):
                    self.assertTrue(any(child.value in world.focuses for child in group), name)
                self.assertTrue(world.matches(block(rows, "available")), name)
                days += float(scalar(rows, "cost")) * 7
                world.execute(block(rows, "completion_reward"))
                world.focuses.add(name)
            self.assertEqual(days, 175)
            self.assertEqual(world.equipment["ADISCORD_fighter_airframe_2163"], 40)
            self.assertEqual(world.equipment["ADISCORD_cas_airframe_2170"], 40)
            self.assertEqual(world.air_experience, 30)
            self.assertEqual(world.buildings["air_base"], 4)
            self.assertEqual(world.buildings["fuel_silo"], 1)
            self.assertEqual(world.buildings["arms_factory"], 6)
            self.assertEqual(world.fuel, 3000)
            self.assertAlmostEqual(world.value("RUS_air_accidents"), -0.05)
            self.assertAlmostEqual(world.value("RUS_air_mission_efficiency"), 0.05)
            self.assertAlmostEqual(world.value("RUS_air_ground_attack"), 0.05)
            self.assertEqual(world.value("RUS_bunker_depth"), 0)
            self.assertNotIn("RUS_claim_the_opened_zone", world.focuses)

    def test_aircraft_rewards_use_unlocked_equipment_and_live_technology_targets(self):
        baseline = block(parse("common/scripted_effects/ADISCORD_technology_baseline_effects.txt"), "ADISCORD_grant_technology_profile_common")
        starting_techs = {row.key for row in walk(baseline) if row.value == "1"}
        technologies = block(parse("common/technologies/ADISCORD_air.txt"), "technologies")
        air_techs = {row.key: row.value for row in technologies}
        enabled = {
            row.value for name in starting_techs & air_techs.keys()
            for entry in air_techs[name] if entry.key == "enable_equipments"
            for row in entry.value
        }
        for suffix, count in (("fighter_cover", 2), ("assault_squadrons", 1)):
            reward = block(self.focuses["RUS_" + suffix], "completion_reward")
            equipment = scalar(block(reward, "add_equipment_to_stockpile"), "type")
            self.assertIn(equipment, enabled)
            bonus = block(reward, "add_tech_bonus")
            self.assertEqual(scalar(bonus, "uses"), str(count))
            targets = {row.value for row in bonus if row.key == "technology"}
            self.assertTrue(targets)
            self.assertTrue(targets <= air_techs.keys())
            self.assertFalse(targets & starting_techs)

    def test_air_base_and_fuel_rewards_require_space_and_current_control(self):
        world = self.world()
        airfield = self.focuses["RUS_capital_airfields"]
        world.buildings["air_base"] = 8
        self.assertTrue(world.matches(block(airfield, "available")))
        world.buildings["air_base"] = 9
        self.assertFalse(world.matches(block(airfield, "available")))
        for suffix in ("capital_airfields", "aviation_fuel_reserve"):
            rows = self.focuses["RUS_" + suffix]
            world = self.world()
            world.controller = False
            self.assertFalse(world.matches(block(rows, "available")))
        world = self.world()
        world.buildings["industrial_complex"] = 1
        occupied = sum(world.buildings[kind] for kind in ("arms_factory", "industrial_complex", "fuel_silo"))
        self.assertEqual(occupied, world.building_slots)
        world.execute(block(self.focuses["RUS_aviation_fuel_reserve"], "completion_reward"))
        self.assertEqual(world.buildings["fuel_silo"], 1)
        self.assertEqual(world.building_slots, occupied + 1)

    def test_bunker_buff_totals_and_existing_upgrade_prices(self):
        cases = (
            (1, 2, "stability_factor", 0.10, 0.15),
            (2, 2, "planning_speed", 0.23, 0.33),
            (4, 1, "casualty_trickleback", 0.21, 0.31),
            (5, 1, "political_power_gain", 0.45, 0.60),
        )
        for layer, variant, modifier, basic, upgraded in cases:
            world = self.world()
            world.variables["RUS_bunker_depth"] = 5
            world.variables["RUS_bunker_generators"] = 2
            world.variables[f"RUS_bunker_layer_{layer}"] = variant
            world.run("RUS_bunker_refresh")
            self.assertAlmostEqual(world.value("RUS_bunker_" + modifier), basic)
            before = world.balances()
            world.begin(f"RUS_bunker_upgrade_{layer}")
            self.assertEqual(tuple(a - b for a, b in zip(before, world.balances())), (25, 85, 35))
            world.finish(f"RUS_bunker_upgrade_{layer}")
            self.assertAlmostEqual(world.value("RUS_bunker_" + modifier), upgraded)
            if layer == 1:
                self.assertAlmostEqual(world.value("RUS_bunker_political_power_gain"), 0.10)

    def test_room_programmes_work_in_either_order_and_survive_rebuilding(self):
        cases = (
            ("integrated_signals", 2, 2, "reinforce_rate", 0.01),
            ("air_control_network", 2, 2, "air_mission_efficiency", 0.03),
            ("serial_ordnance_orders", 3, 1, "industrial_capacity_factory", 0.23),
            ("aircraft_workshops", 3, 1, "production_factory_efficiency_gain_factor", 0.03),
            ("field_hospitals", 4, 1, "casualty_trickleback", 0.26),
            ("air_ground_coordination", 4, 2, "air_accidents_factor", -0.05),
            ("command_accountability", 5, 2, "planning_speed", 0.03),
        )
        for suffix, layer, variant, output, expected in cases:
            for room_first in (False, True):
                world = self.world()
                world.focuses.discard("RUS_" + suffix)
                room = f"RUS_bunker_layer_{layer}"
                if room_first:
                    world.variables[room] = variant
                    world.run("RUS_bunker_refresh")
                world.execute(block(self.focuses["RUS_" + suffix], "completion_reward"))
                world.focuses.add("RUS_" + suffix)
                if not room_first:
                    world.variables[room] = variant
                    world.run("RUS_bunker_refresh")
                self.assertAlmostEqual(world.value("RUS_bunker_" + output), expected, msg=suffix)
                world.variables[room] = 0
                world.run("RUS_bunker_refresh")
                self.assertEqual(world.value("RUS_bunker_" + output), 0, suffix)
                world.variables[room] = variant
                world.run("RUS_bunker_refresh")
                self.assertAlmostEqual(world.value("RUS_bunker_" + output), expected, msg=suffix)
                world.controller = False
                world.run("RUS_bunker_refresh")
                self.assertNotIn("RUS_bunker_complex", world.modifiers)
                self.assertIn("RUS_black_army", world.modifiers)
                world.controller = True
                world.run("RUS_bunker_refresh")
                self.assertAlmostEqual(world.value("RUS_bunker_" + output), expected, msg=suffix)

    def test_mandates_and_depots_share_government_with_their_original_lifetime(self):
        definitions = parse("common/dynamic_modifiers/ADISCORD_dynamic_modifiers_RUS.txt")
        names = ("RUS_government_service", "RUS_government_retained_institutions")
        modifiers = {name: block(definitions, name) for name in names}
        self.assertNotIn("icon", [row.key for row in modifiers[names[1]]])
        fields = ("political_power_gain", "mobilization_speed", "stability_factor",
                  "production_factory_max_efficiency_factor")

        def effective_values(world):
            values = {field: 0 for field in fields}
            for name, rows in modifiers.items():
                if name not in world.modifiers or not world.matches(block(rows, "enable")):
                    continue
                for field in fields:
                    variable = scalar(rows, field)
                    if variable:
                        values[field] += world.value(variable)
            return tuple(values[field] for field in fields)

        cases = (
            (None, None, (0, 0, 0)),
            ("RUS_scientists_council", "RUS_council_mandate", (0.1, -0.05, 0.05)),
            ("RUS_black_army_oath", "RUS_chancery_mandate", (0.2, 0.1, -0.03)),
        )
        for focus, preview, mandate in cases:
            for depots in (False, True):
                with self.subTest(focus=focus, depots=depots):
                    world = self.world()
                    world.variables["RUS_government_political_power"] = 0.35
                    world.variables["RUS_government_mobilization"] = 0.20
                    world.run("RUS_government_refresh")
                    if focus:
                        world.execute(block(self.focuses[focus], "completion_reward"))
                        shown = block(self.ideas[preview], "modifier")
                        self.assertEqual(scalar(self.ideas[preview], "name"), names[0])
                        self.assertEqual(tuple(float(scalar(shown, field)) for field in fields[:3]), mandate)
                    if depots:
                        world.execute(block(self.focuses["RUS_recovery_depots"], "completion_reward"))
                    retained = (*mandate, 0.05 if depots else 0)
                    active = (mandate[0] + 0.35, mandate[1] + 0.20, *retained[2:])
                    for actual, expected in zip(effective_values(world), active):
                        self.assertAlmostEqual(actual, expected)
                    self.assertFalse({"RUS_council_mandate", "RUS_chancery_mandate",
                                      "RUS_repair_depots_spirit"} & world.ideas)
                    for _ in range(2):
                        world.run("RUS_government_refresh")
                        for actual, expected in zip(effective_values(world), active):
                            self.assertAlmostEqual(actual, expected)
                    # Native enable conditions change without another focus or refresh.
                    for attribute, value in (("subject", True), ("capitulated", True),
                                             ("ruler", "another_ruler")):
                        previous = getattr(world, attribute)
                        setattr(world, attribute, value)
                        for actual, expected in zip(effective_values(world), retained):
                            self.assertAlmostEqual(actual, expected, msg=attribute)
                        setattr(world, attribute, previous)
                    world.controller = False
                    world.owner = False
                    for actual, expected in zip(effective_values(world), active):
                        self.assertAlmostEqual(actual, expected)
                    world.run("RUS_campaign_initialize")
                    for actual, expected in zip(effective_values(world), active):
                        self.assertAlmostEqual(actual, expected)
                    world.variables["RUS_crisis_phase"] = 4
                    world.run("RUS_campaign_shutdown")
                    world.run("RUS_government_refresh")
                    self.assertFalse(set(names) & world.modifiers)
                    self.assertEqual(effective_values(world), (0, 0, 0, 0))

    def test_new_institution_and_army_previews_match_accumulated_variables(self):
        modifiers = parse(f"common/dynamic_modifiers/ADISCORD_dynamic_modifiers_RUS.txt")
        cases = (
            "permanent_government", "civil_construction_board",
            "military_governors", "military_contract_board", "staff_college",
            "integrated_signals", "field_hospitals", "serial_ordnance_orders",
            "armoured_repair_service", "flight_school", "air_control_network",
            "air_ground_coordination",
            "single_supply_register", "railway_coverage",
        )
        for suffix in cases:
            world = self.world()
            idea = self.ideas[f"RUS_{suffix}_delta"]
            spirit = scalar(idea, "name")
            bindings = {entry.key: entry.value for entry in block(modifiers, spirit) if isinstance(entry.value, str)}
            before = dict(world.variables)
            dirty = world.dirty
            world.execute(block(self.focuses["RUS_" + suffix], "completion_reward"))
            for entry in block(idea, "modifier"):
                variable = bindings[entry.key]
                self.assertAlmostEqual(world.value(variable) - before.get(variable, 0), float(entry.value), msg=suffix)
            self.assertIn(spirit, world.modifiers)
            self.assertNotIn(f"RUS_{suffix}_delta", world.ideas)
            if spirit == "RUS_government_service" or suffix == "serial_ordnance_orders":
                self.assertGreater(world.dirty, dirty)
            saved = deepcopy(world.variables)
            world.run("RUS_campaign_initialize")
            self.assertEqual(world.variables, saved)
            world.run("RUS_campaign_shutdown")
            self.assertNotIn(spirit, world.modifiers)

    def test_civil_training_adds_current_archive_bonus_without_changing_payment(self):
        for trained, archive, controlled, expected in (
            (False, True, True, 25), (True, False, True, 35),
            (True, True, True, 50), (True, True, False, 35),
        ):
            world = self.world()
            world.decisions = self.programmes
            world.focuses = {"RUS_aimaq_service_charter"}
            if trained:
                world.execute(block(self.focuses["RUS_trained_administrators"], "completion_reward"))
                world.focuses = {"RUS_trained_administrators"}
            world.variables["RUS_bunker_layer_5"] = int(archive)
            world.controller = controlled
            before = world.balances()
            world.begin("RUS_civil_service_training")
            self.assertEqual(world.value("ADISCORD_state_development_progress"), expected)
            self.assertEqual(tuple(a - b for a, b in zip(before, world.balances())), (25, 35, 0))
            world.variables["RUS_bunker_layer_5"] = 0
            world.run("RUS_bunker_refresh")
            self.assertEqual(world.value("ADISCORD_state_development_progress"), expected)

    def test_ai_builds_first_air_force_before_territorial_war(self):
        plan = block(parse(f"common/ai_strategy_plans/{BASE}_plans.txt"), "ADISCORD_vorkerland_rus_last_empire_plan")
        order = [entry.value for entry in block(plan, "ai_national_focuses")]
        for suffix in ("flight_school", "capital_airfields", "fighter_cover", "aviation_fuel_reserve", "assault_squadrons"):
            self.assertLess(order.index("RUS_" + suffix), order.index("RUS_claim_the_opened_zone"))

    def test_rus_modifier_fields_are_valid_and_medical_typos_are_rejected(self):
        from tools.validators import validate_adiscord_modifier_fields as validator

        failures = validator.validate()
        self.assertFalse([failure for failure in failures if "RUS_" in failure])
        original_read = Path.read_text
        target = ROOT / f"common/dynamic_modifiers/ADISCORD_dynamic_modifiers_RUS.txt"

        def read_with_typo(path, *args, **kwargs):
            text = original_read(path, *args, **kwargs)
            if path == target:
                text = text.replace(
                    "casualty_trickleback = RUS_army_casualty_return",
                    "casualty_tricklebak = RUS_army_casualty_return",
                    1,
                )
            return text

        with patch.object(Path, "read_text", read_with_typo):
            failures = validator.validate()
        self.assertTrue(any("RUS_black_army" in failure and "casualty_tricklebak" in failure for failure in failures))


class RusLandRestorationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        RusCampaignTests.setUpClass()
        cls.campaign = RusCampaignTests

    def world(self):
        world = BunkerWorld(self.campaign)
        world.focuses.clear()
        world.decisions = {**self.campaign.programmes, **self.campaign.balance, **self.campaign.suspicion}
        return world

    def decision(self, world):
        self.assertTrue("RUS_restore_wasteland" in world.decisions)
        return world.decisions["RUS_restore_wasteland"]

    def test_early_suspicion_hook_and_chancery_do_not_reset_progress(self):
        hook = block(block(parse("common/on_actions/01_ADISCORD_vorkerland_collapse_on_actions.txt"), "on_actions"), "on_state_control_changed")
        self.assertTrue(any(row.key == "RUS_suspicion_begin" for row in walk(hook)))
        world = self.world()
        self.assertNotIn("RUS_suspicion", world.variables)
        world.run("RUS_suspicion_begin")
        self.assertEqual(world.value("RUS_suspicion"), 10)
        world.run("RUS_suspicion_monthly")
        world.run("RUS_suspicion_begin")
        world.execute(block(self.campaign.focuses["RUS_seat_the_khan_chancery"], "completion_reward"))
        self.assertEqual(world.value("RUS_suspicion"), 13)
        for name in ("RUS_suspicion_energy_cover", "RUS_suspicion_envoys"):
            self.assertTrue(world.matches(block(world.decisions[name], "visible")))
            self.assertTrue(world.matches(block(world.decisions[name], "available")))

    def test_restoration_exact_prices_shared_queue_and_reload_delivery(self):
        for target in ("329", "330", "292", "296"):
            world = self.world()
            rows = self.decision(world)
            world.target_state = target
            world.pp = 75
            world.variables["ADISCORD_economy_treasury"] = 335
            world.equipment["support_equipment"] = 200
            for currency in range(3):
                short = deepcopy(world)
                if currency == 0:
                    short.pp -= 0.01
                elif currency == 1:
                    short.variables["ADISCORD_economy_treasury"] -= 0.01
                else:
                    short.equipment["support_equipment"] -= 0.01
                before = short.balances()
                self.assertFalse(short.matches(block(rows, "custom_cost_trigger")))
                short.execute(block(rows, "complete_effect"))
                self.assertEqual(short.balances(), before)
            world.begin("RUS_restore_wasteland")
            self.assertEqual(world.balances(), (0, 0, 0))
            for other in world.regions:
                world.target_state = other
                self.assertFalse(world.matches(block(rows, "available")))
            world.target_state = target
            restored = deepcopy(world)
            restored.temporary.clear()
            restored.run("RUS_campaign_initialize")
            restored.finish("RUS_restore_wasteland")
            restored.finish("RUS_restore_wasteland")
            self.assertEqual(restored.regions[target]["category"], "rural")
            self.assertEqual(restored.regions[target]["infrastructure"], 2)
            self.assertNotIn("RUS_reclamation_deposit", restored.variables)
            self.assertEqual(restored.balances(), (0, 0, 0))
            self.assertFalse(restored.matches(block(rows, "visible")))

    def test_restoration_hidden_off_target_but_shortages_remain_visible(self):
        world = self.world()
        rows = self.decision(world)
        self.assertEqual({row.value for row in block(rows, "targets")}, set(world.regions))
        self.assertEqual(scalar(rows, "days_remove"), "120")
        self.assertEqual(scalar(rows, "cost"), "0")
        world.pp = 0
        self.assertTrue(world.matches(block(rows, "visible")))
        for field, value in (("category", "rural"), ("owner", "VAL")):
            invalid = deepcopy(world)
            invalid.regions["329"][field] = value
            self.assertFalse(invalid.matches(block(rows, "visible")))
        world.regions["329"]["controller"] = "VAL"
        self.assertTrue(world.matches(block(rows, "visible")))
        self.assertFalse(world.matches(block(rows, "available")))

    def test_restoration_spends_foreign_equipment_and_refunds_without_creating_stock(self):
        world = self.world()
        self.decision(world)
        world.equipment_by_producer["support_equipment"] = {"VAL": 125, "WKR": 75}
        world.equipment["support_equipment"] = 200
        world.begin("RUS_restore_wasteland")
        self.assertEqual(world.equipment["support_equipment"], 0)
        world.run("RUS_reclamation_cancel")
        world.run("RUS_reclamation_cancel")
        self.assertEqual(world.equipment["support_equipment"], 200)

    def test_restoration_refunds_invalid_delivery_and_shutdown_once(self):
        for reason in ("owner", "controller", "category", "shutdown"):
            world = self.world()
            rows = self.decision(world)
            before = world.balances()
            world.begin("RUS_restore_wasteland")
            if reason == "shutdown":
                world.run("RUS_campaign_shutdown")
            else:
                world.regions["329"][reason] = "rural" if reason == "category" else "VAL"
            world.finish("RUS_restore_wasteland")
            world.execute(block(rows, "cancel_effect"))
            self.assertEqual(world.balances(), before, reason)
            self.assertEqual(world.regions["329"]["infrastructure"], 1)
            self.assertFalse(any(state["flags"] for state in world.regions.values()))

    def test_restoration_cancel_for_another_target_cannot_refund_live_project(self):
        world = self.world()
        rows = self.decision(world)
        world.begin("RUS_restore_wasteland")
        paid = world.balances()
        world.target_state = "330"
        world.execute(block(rows, "cancel_effect"))
        world.finish("RUS_restore_wasteland")
        self.assertEqual(world.balances(), paid)
        self.assertIn("RUS_reclamation_deposit", world.variables)
        world.target_state = "329"
        world.execute(block(rows, "cancel_effect"))
        self.assertNotIn("RUS_reclamation_deposit", world.variables)

    def test_restoration_targets_are_passable_wasteland_and_localisation_loads(self):
        world = self.world()
        self.decision(world)
        for target in world.regions:
            paths = list((ROOT / "history/states").glob(target + "-*.txt"))
            state = paths[0].read_text(encoding="utf-8-sig")
            self.assertIn("state_category = wasteland", state)
            self.assertNotIn("impassable = yes", state)
        for language in ("russian", "english"):
            path = ROOT / f"localisation/{language}/ADISCORD_RUS_l_{language}.yml"
            self.assertTrue(path.read_bytes().startswith(b"\xef\xbb\xbf"))
            loc = dict(re.findall(r'^\s+([A-Za-z0-9_.]+):(?:\d+)?\s+"(.*)"\s*$', path.read_text(encoding="utf-8-sig"), re.M))
            for suffix in ("", "_desc", "_cost", "_cost_blocked", "_cost_tooltip", "_result_tt", "_refund_tt"):
                self.assertTrue("RUS_restore_wasteland" + suffix in loc, suffix)


class RusLateProgrammeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        RusCampaignTests.setUpClass()
        cls.campaign = RusCampaignTests
        cls.events = {
            scalar(row.value, "id"): row.value
            for row in parse("events/ADISCORD_RUS_events.txt")
            if row.key == "country_event"
        }

    def world(self):
        world = BunkerWorld(self.campaign)
        world.decisions = {**self.campaign.decisions, **self.campaign.programmes}
        return world

    def test_paid_orders_share_receipt_and_deliver_once_after_reload(self):
        for name, price in (("RUS_civil_factory_order", (40, 100, 60)), ("RUS_artillery_order", (25, 65, 50))):
            with self.subTest(name=name):
                self.assertTrue(name in self.campaign.programmes, name)
                world = self.world()
                world.pp, world.variables["ADISCORD_economy_treasury"], world.equipment["support_equipment"] = price
                for currency in range(3):
                    short = deepcopy(world)
                    if currency == 0:
                        short.pp -= 0.01
                    elif currency == 1:
                        short.variables["ADISCORD_economy_treasury"] -= 0.01
                    else:
                        short.equipment["support_equipment"] -= 0.01
                    before = short.balances()
                    short.execute(block(short.decisions[name], "complete_effect"))
                    self.assertEqual(short.balances(), before)
                    self.assertNotIn("RUS_work_order", short.variables)
                world.begin(name)
                self.assertEqual(world.balances(), (0, 0, 0))
                for other in ("RUS_civil_factory_order", "RUS_artillery_order"):
                    self.assertFalse(world.matches(block(world.decisions[other], "available")))
                world = deepcopy(world)
                world.temporary.clear()
                world.run("RUS_campaign_initialize")
                world.finish(name)
                self.assertNotIn("RUS_work_order", world.variables)
                if name == "RUS_civil_factory_order":
                    self.assertEqual(world.buildings["industrial_complex"], 1)
                else:
                    self.assertEqual(world.equipment["artillery_equipment_1"], 120)
                after = deepcopy(world.variables), deepcopy(world.equipment), deepcopy(world.buildings), world.balances()
                world.finish(name)
                world.run("RUS_work_order_refund")
                self.assertEqual((world.variables, world.equipment, world.buildings, world.balances()), after)

    def test_orders_refund_on_invalid_delivery_or_shutdown(self):
        for name in ("RUS_civil_factory_order", "RUS_artillery_order"):
            self.assertTrue(name in self.campaign.programmes, name)
            for loss in ("owner", "controller", "subject", "ruler", "shutdown", "capacity"):
                if loss == "capacity" and name != "RUS_civil_factory_order":
                    continue
                world = self.world()
                before = world.balances()
                world.begin(name)
                if loss in ("owner", "controller"):
                    setattr(world, loss, False)
                elif loss == "subject":
                    world.subject = True
                elif loss == "ruler":
                    world.ruler = "another_ruler"
                elif loss == "capacity":
                    world.building_slots = 5
                else:
                    world.run("RUS_campaign_shutdown")
                world.finish(name)
                world.run("RUS_work_order_refund")
                self.assertEqual(world.balances(), before, (name, loss))
                self.assertEqual(world.buildings["industrial_complex"], 0)
                self.assertEqual(world.equipment.get("artillery_equipment_1", 0), 0)

    def test_cancelled_order_cannot_refund_a_different_paid_order(self):
        world = self.world()
        world.begin("RUS_civil_factory_order")
        world.run("RUS_work_order_refund")
        world.begin("RUS_artillery_order")
        before = world.balances(), deepcopy(world.variables)
        world.execute(block(world.decisions["RUS_civil_factory_order"], "cancel_effect"))
        self.assertEqual((world.balances(), world.variables), before)
        world.finish("RUS_artillery_order")
        self.assertEqual(world.equipment["artillery_equipment_1"], 120)

    def test_bunker_loss_refunds_commission_before_control_returns(self):
        world = self.world()
        before = world.balances()
        world.begin("RUS_artillery_order")
        world.controller = False
        world.run("RUS_bunker_refresh")
        self.assertEqual(world.balances(), before)
        self.assertNotIn("RUS_work_order", world.variables)
        world.controller = True
        world.run("RUS_bunker_refresh")
        world.finish("RUS_artillery_order")
        self.assertEqual(world.equipment.get("artillery_equipment_1", 0), 0)

    def test_district_aid_uses_food_and_only_imperial_morale(self):
        for imperial in (False, True):
            world = self.world()
            world.pp = 25
            world.variables["ADISCORD_economy_treasury"] = 35
            world.variables["RUS_bunker_food"] = 20
            if imperial:
                world.flags.add("ADISCORD_vorkerland_rus_last_empire_proclaimed")
                world.variables["RUS_army_morale"] = 50
            short = deepcopy(world)
            short.variables["RUS_bunker_food"] = 19.99
            short.run("RUS_district_relief")
            self.assertEqual(short.pp, 25)
            self.assertEqual(short.value("ADISCORD_economy_treasury"), 35)
            world.begin("RUS_district_relief")
            self.assertEqual(world.pp, 0)
            self.assertEqual(world.value("ADISCORD_economy_treasury"), 0)
            self.assertEqual(world.value("RUS_bunker_food"), 0)
            self.assertAlmostEqual(world.value("RUS_scientists_support"), .55)
            self.assertEqual(world.value("RUS_army_morale"), 55 if imperial else 0)

    def test_machine_reserve_is_a_single_choice_and_repair_preserves_paid_work(self):
        for choice in ("RUS_machine_reserve_release", "RUS_machine_reserve_repair"):
            self.assertTrue(choice in self.campaign.programmes, choice)
            world = self.world()
            world.execute(block(self.campaign.focuses["RUS_bunker_machine_depot"], "completion_reward"))
            world.variables["RUS_bunker_integrity"] = 35
            world.begin("RUS_bunker_reinforce")
            receipt = world.value("RUS_bunker_project")
            before = world.balances()
            world.begin(choice)
            self.assertEqual(world.value("RUS_bunker_project"), receipt)
            self.assertNotIn("RUS_machine_reserve", world.variables)
            expected = (before[0], before[1] + (600 if choice.endswith("release") else 300), before[2] + (400 if choice.endswith("release") else 200))
            self.assertEqual(world.balances(), expected)
            self.assertEqual(world.value("RUS_bunker_integrity"), 35 if choice.endswith("release") else 95)
            for other in ("RUS_machine_reserve_release", "RUS_machine_reserve_repair"):
                world.execute(block(world.decisions[other], "complete_effect"))
                self.assertEqual(world.balances(), expected)

    def late_world(self, suffix, event_id):
        world = self.world()
        world.held_states.add("177")
        world.flags.add("ADISCORD_vorkerland_rus_last_empire_proclaimed")
        world.variables.update({"RUS_crisis_phase": 2, "RUS_army_morale": 50, "RUS_bunker_food": 80})
        event = self.events[event_id]
        self.assertTrue(world.matches(block(event, "trigger")))
        world.execute(block(event, "immediate"))
        self.assertEqual(world.value("RUS_last_sky_" + suffix), 1)
        return world, event

    def test_last_sky_choices_charge_once_and_expired_windows_do_nothing(self):
        for suffix, event_id, treasury, equipment, food in (
            ("science", "ADISCORD_rus_crisis.21", 50, 50, 0),
            ("army", "ADISCORD_rus_crisis.22", 35, 0, 30),
            ("districts", "ADISCORD_rus_crisis.23", 35, 0, 40),
        ):
            self.assertTrue(event_id in self.events, event_id)
            world, event = self.late_world(suffix, event_id)
            options = [row.value for row in event if row.key == "option"]
            accept = block(options[1], "hidden_effect")
            before = world.balances(), world.value("RUS_bunker_food")
            world.execute(accept)
            self.assertEqual(world.balances(), (before[0][0], before[0][1] - treasury, before[0][2] - equipment))
            self.assertEqual(world.value("RUS_bunker_food"), before[1] - food)
            self.assertEqual(world.value("RUS_last_sky_" + suffix), 2)
            self.assertEqual(world.value("RUS_army_morale"), 58 if suffix == "army" else 55)
            expected_support = {"science": (.5, .6), "army": (.6, .5), "districts": (.55, .55)}[suffix]
            self.assertAlmostEqual(world.value("RUS_black_army_support"), expected_support[0])
            self.assertAlmostEqual(world.value("RUS_scientists_support"), expected_support[1])
            after = deepcopy(world.variables), world.balances()
            world.execute(accept)
            world.execute(block(options[0], "hidden_effect"))
            self.assertEqual((world.variables, world.balances()), after)
            stale, _ = self.late_world(suffix, event_id)
            stale.variables["RUS_crisis_phase"] = 5
            before = deepcopy(stale.variables), stale.balances()
            stale.execute(accept)
            stale.execute(block(options[0], "hidden_effect"))
            self.assertEqual((stale.variables, stale.balances()), before)

    def test_last_sky_first_option_is_free_refusal_and_short_stocks_block_payment(self):
        for suffix, event_id in (("science", "ADISCORD_rus_crisis.21"), ("army", "ADISCORD_rus_crisis.22"), ("districts", "ADISCORD_rus_crisis.23")):
            self.assertTrue(event_id in self.events, event_id)
            world, event = self.late_world(suffix, event_id)
            options = [row.value for row in event if row.key == "option"]
            before = world.balances(), world.value("RUS_bunker_food")
            world.execute(block(options[0], "hidden_effect"))
            self.assertEqual((world.balances(), world.value("RUS_bunker_food")), before)
            self.assertEqual(world.value("RUS_last_sky_" + suffix), 3)
            refused = deepcopy(world.variables), world.balances()
            world.execute(block(options[1], "hidden_effect"))
            self.assertEqual((world.variables, world.balances()), refused)
            short, _ = self.late_world(suffix, event_id)
            short.variables["ADISCORD_economy_treasury"] = 34.99
            before = deepcopy(short.variables), short.balances()
            short.execute(block(options[1], "hidden_effect"))
            self.assertEqual((short.variables, short.balances()), before)

    def test_new_scene_descriptions_costs_and_registry_are_loadable(self):
        registry = json.loads(read("tools/data/adiscord_event_ids.json"))["events"]
        for language in ("russian", "english"):
            path = ROOT / f"localisation/{language}/ADISCORD_RUS_l_{language}.yml"
            self.assertTrue(path.read_bytes().startswith(b"\xef\xbb\xbf"))
            loc = dict(re.findall(r'^\s*(\S+):\d*\s+"(.*)"\s*$', path.read_text(encoding="utf-8-sig"), re.M))
            for number in (21, 22, 23):
                name = f"ADISCORD_rus_crisis.{number}"
                self.assertEqual(sum(row["id"] == name for row in registry), 1)
                event = self.events[name]
                for row in walk(event):
                    if row.key in ("title", "text", "name", "custom_effect_tooltip"):
                        self.assertIn(row.value, loc)
                for suffix in (".d", ".course.d"):
                    text = loc[name + suffix].replace("\\n", "\n")
                    self.assertLessEqual(len(text), 3000)
                    self.assertLessEqual(len(text.encode("utf-8")), 5500)
                    self.assertNotIn("§Y", text)
            for name in ("RUS_district_relief", "RUS_civil_factory_order", "RUS_artillery_order"):
                for suffix in ("", "_blocked", "_tooltip"):
                    self.assertIn(name + "_cost" + suffix, loc)


if __name__ == "__main__":
    unittest.main()
