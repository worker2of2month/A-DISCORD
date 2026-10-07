"""Parsed RUS accounting and campaign contracts; not native-engine simulation."""

from copy import deepcopy
from itertools import permutations, product
from pathlib import Path
import json
import re
import unittest

from tools.builders.build_adiscord_focus_trees import expected_outputs
from tools.tests.test_adiscord_stp_preparation import block, scalar, walk
from tools.validators.validate_adiscord_division_templates import parse_clausewitz


ROOT = Path(__file__).resolve().parents[2]
BASE = "ADISCORD_vorkerland"


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
        self.flags = {"RUS_campaign_start_pending"}
        self.focuses = set() if fresh else set(campaign.focuses)
        self.ideas = set()
        self.modifiers = set()
        self.active = set()
        self.events = []
        self.ruler = "RUS_Mark_Rustan"
        self.characters = {self.ruler, "RUS_Varlam_Oskol"}
        self.held_states = set()
        self.templates = set()
        self.tech_bonuses = []
        self.cores = set()
        self.claims = set()
        self.ideology = "etatism"
        self.bop_id = None
        self.bop = 0.0
        self.army_experience = 0.0
        self.command_power = 0.0
        self.manpower = 0.0
        self.stability = 0.0
        self.subject = False
        self.capitulated = False
        self.war = True
        self.ai = True
        self.owner = True
        self.controller = True
        self.divisions = 2
        self.dirty = 0
        self.buildings = {"infrastructure": 2, "arms_factory": 5, "industrial_complex": 0}
        self.building_slots = 6
        self.run("RUS_campaign_initialize")

    def value(self, token):
        try:
            return float(token)
        except ValueError:
            return self.temporary.get(token, self.variables.get(token, 0))

    @staticmethod
    def compare(left, operator, right):
        return {"equals": left == right, "less_than": left < right,
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
                assert value in ("has_political_power", "has_manpower", "infrastructure"), value
                operator, amount = rows[index:index + 2]
                index += 2
                current = {"has_political_power": self.pp, "has_manpower": self.manpower}.get(value)
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
            elif key == "is_ai":
                result = self.ai == (value == "yes")
            elif key == "tag":
                result = value == "RUS"
            elif key == "has_variable":
                result = value in self.variables
            elif key == "has_country_flag":
                result = value in self.flags
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
            elif key == "every_state":
                state_id = next((child.value for child in value if child.key == "limit" for child in child.value if child.key == "id"), None)
                result = state_id is not None
            elif key == "free_building_slots":
                occupied = self.buildings["arms_factory"] + self.buildings["industrial_complex"]
                result = self.building_slots - occupied >= int(scalar(value, "size"))
            elif key in ("owns_state", "controls_state"):
                if value == "66":
                    result = self.owner if key == "owns_state" else self.controller
                else:
                    result = value in self.held_states
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
            elif key == "capital_scope":
                self.execute(value)
            elif key == "create_unit":
                count = [row.value for row in value if row.key == "count"]
                self.divisions += int(count[0]) if count else 1
            elif key == "division_template":
                self.templates.add(scalar(value, "name"))
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
            elif key in ("set_variable", "add_to_variable", "subtract_from_variable", "multiply_variable", "set_temp_variable", "multiply_temp_variable"):
                target = self.temporary if "temp" in key else self.variables
                name = scalar(value, "var")
                amount = self.value(scalar(value, "value"))
                if key.startswith("set_"):
                    target[name] = amount
                elif key.startswith("add_"):
                    target[name] = target.get(name, 0) + amount
                elif key.startswith("subtract_"):
                    target[name] = target.get(name, 0) - amount
                else:
                    target[name] = target.get(name, 0) * amount
            elif key == "clear_variable":
                self.variables.pop(value, None)
            elif key == "clamp_variable":
                name = scalar(value, "var")
                self.variables[name] = min(float(scalar(value, "max")), max(float(scalar(value, "min")), self.value(name)))
            elif key == "add_political_power":
                self.pp += self.value(value)
            elif key == "army_experience":
                self.army_experience += self.value(value)
            elif key == "add_command_power":
                self.command_power += self.value(value)
            elif key == "add_manpower":
                self.manpower += self.value(value)
            elif key == "add_stability":
                self.stability = max(0, min(1, self.stability + self.value(value)))
            elif key == "recruit_character":
                self.characters.add(value)
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
                self.equipment[equipment] = self.equipment.get(equipment, 0) + self.value(scalar(value, "amount"))
            elif key == "set_country_flag":
                self.flags.add(value)
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
                    self.ideas.update(names)
                else:
                    self.ideas.difference_update(names)
            elif key == "country_event":
                self.events.append(scalar(value, "id"))
            elif key == "activate_decision":
                self.begin(value)
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
        cls.effects = {e.key: e.value for e in parse(f"common/scripted_effects/{BASE}_effects.txt")}
        cls.triggers = {e.key: e.value for e in parse(f"common/scripted_triggers/{BASE}_triggers.txt")}
        cls.effects.update({e.key: e.value for e in parse("common/scripted_effects/ADISCORD_shared_action_effects.txt") if e.key.startswith("ADISCORD_campaign_slot_")})
        cls.triggers.update({e.key: e.value for e in parse("common/scripted_triggers/ADISCORD_shared_action_triggers.txt") if e.key == "ADISCORD_has_campaign_slot"})
        cls.decisions = {e.key: e.value for e in block(parse(f"common/decisions/{BASE}_decisions.txt"), "RUS_bunker_construction")}
        cls.programmes = {e.key: e.value for e in block(parse(f"common/decisions/{BASE}_decisions.txt"), "RUS_development_programmes")}
        cls.campaigns = {e.key: e.value for e in block(parse(f"common/decisions/{BASE}_decisions.txt"), "RUS_public_campaigns")}
        cls.balance = {e.key: e.value for e in block(parse(f"common/decisions/{BASE}_decisions.txt"), "RUS_state_balance_category")}
        cls.belt = {e.key: e.value for e in block(parse(f"common/decisions/{BASE}_decisions.txt"), "RUS_reactor_belt_category")}
        cls.labs = {e.key: e.value for e in block(parse(f"common/decisions/{BASE}_decisions.txt"), "RUS_experimental_labs_category")}
        tree = block(parse("focus_trees/RUS/main/focuses.txt"), "focus_tree")
        cls.focuses = {scalar(e.value, "id"): e.value for e in tree if e.key == "focus"}
        cls.ideas = {e.key: e.value for e in block(block(parse(f"common/ideas/{BASE}_ideas.txt"), "ideas"), "country")}
        cls.projects = [name for name, rows in cls.decisions.items() if any(e.key == "days_remove" for e in rows)]
        cls.loc = dict(re.findall(r'^\s+([A-Za-z0-9_.]+):(?:\d+)?\s+"(.*)"\s*$', read(f"localisation/russian/{BASE}_l_russian.yml"), re.M))

    def world(self):
        return BunkerWorld(self)

    def test_generation_and_one_hundred_twenty_seven_focuses(self):
        self.assertEqual(len(self.focuses), 127)
        path = ROOT / "common/national_focus/ADISCORD_national_focus_RUS.txt"
        self.assertEqual(path.read_bytes(), expected_outputs()[path])

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
        self.assertEqual(world.equipment["support_equipment"] - equipment, 300)
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
                world.variables["ADISCORD_economy_treasury"] = 499.99
                world.run("RUS_bunker_refresh")
                before = world.balances()
                world.run("RUS_bunker_resupply")
                self.assertEqual(world.balances(), before)
                self.assertEqual(world.value("RUS_bunker_food"), 0)
                world.variables["ADISCORD_economy_treasury"] = 1500
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
                proceeds = int(total_bought // 40) * 300
                self.assertEqual(world.value("ADISCORD_economy_treasury"), proceeds)
                self.assertLess(proceeds, 1500)

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
            for name, amount in (("GetRUSBunkerFoodCash", 500), ("GetRUSBunker31cash", 100)):
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

    def test_programmes_charge_exact_prices_and_deliver_material_results(self):
        prices = {
            "defensive_preparation": (25, 250, 35),
            "mobile_preparation": (30, 200, 30),
            "aimaq_public_works": (25, 300, 35),
            "chancery_reconstruction": (25, 400, 45),
            "surface_industrial_contract": (25, 400, 45),
            "subterranean_supply_contract": (25, 350, 40),
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

    def test_programmes_recheck_current_ownership_unlocks_and_capacity(self):
        for name, rows in self.programmes.items():
            for changed in ("owner", "controller", "subject", "ruler", "focus"):
                world = self.world()
                if changed in ("owner", "controller"):
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
        pairs = (("reaffirm_khan", "army_mandate", "reconstruction_cabinet"), ("aimaq_council", "seal_chancery"), ("patient_war", "swift_columns"), ("bunker_open_city", "bunker_sealed_throne"), ("surface_contracts", "underground_fund"))
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
            (("district_ledger", "courier_stations", "district_paramedics"), "covenant_of_service", 3, 91),
            (("field_evacuation_service", "rifle_inspection_board", "artillery_observers"), "staff_field_exercise", 6, 91),
            (("recovery_depots", "interchangeable_parts", "second_arsenal_shift"), "strategic_freight_reserve", 3, 105),
            (("register_conquered_lands", "empire_without_rivals", "postwar_roads", "imperial_academy"), "tomorrow_above_ground", 6, 154),
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
        self.assertEqual(int(scalar(self.focuses["RUS_summon_the_aimaqs"], "cost")) * 7 + int(scalar(self.focuses["RUS_bunker_survey"], "cost")) * 7, 42)
        world = BunkerWorld(self, fresh=True)
        category = block(parse(f"common/decisions/categories/{BASE}_categories.txt"), "RUS_bunker_construction")
        self.assertTrue(world.matches(block(category, "visible")))
        self.assertFalse(world.focuses)
        self.assertEqual(world.balances(), (20, 250, 20))
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

    def test_each_module_preview_equals_its_actual_modifier_delta(self):
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
                self.assertAlmostEqual(world.value(key) - before.get(key, 0), float(entry.value), msg=room)
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
        cash = world.value("ADISCORD_economy_treasury")
        rifles = world.equipment["infantry_equipment"]
        pp = world.pp
        world.execute(block(self.decisions["RUS_rifle_order"], "complete_effect"))
        world.execute(block(self.decisions["RUS_market_surplus"], "complete_effect"))
        self.assertEqual(world.equipment["infantry_equipment"], rifles)
        self.assertEqual(world.value("ADISCORD_economy_treasury"), cash - 30)
        self.assertEqual(world.pp, pp - 45)

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
        window = block(block(parse("interface/ADISCORD_RUS.gui"), "guiTypes"), "containerWindowType")
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
            self.assertEqual(world.value("ADISCORD_economy_current_month_action_income"), 300)
            self.assertEqual(world.value("ADISCORD_economy_current_month_action_costs"), 150)

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
        self.assertEqual(world.value("RUS_bunker_integrity"), 70)
        self.assertEqual(world.value("RUS_bunker_army_org_factor"), 0)

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
        self.assertAlmostEqual(world.value("RUS_bunker_army_org_factor"), org - .05)
        self.assertAlmostEqual(world.value("RUS_bunker_stability_factor"), stability - .05)
        before = world.balances()
        world.run("RUS_bunker_resupply")
        self.assertEqual(world.value("RUS_bunker_food"), 40)
        self.assertEqual(world.balances(), (before[0] - 15, before[1] - 500, before[2]))
        self.assertAlmostEqual(world.value("RUS_bunker_army_org_factor"), org)
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
        world.variables["ADISCORD_economy_treasury"] = 500
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
        self.assertAlmostEqual(world.value("RUS_bunker_stability_factor"), 0.13)
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
            parse(f"common/dynamic_modifiers/{BASE}_dynamic_modifiers.txt"),
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
        self.assertEqual(world.balances(), (before[0] - 15, before[1] - 500, before[2]))
        income = world.value("ADISCORD_economy_current_month_action_income")
        world.run("RUS_bunker_food_sale")
        self.assertEqual(world.value("RUS_bunker_food"), 100)
        self.assertEqual(world.value("ADISCORD_economy_treasury"), before[1] - 500 + 300)
        self.assertEqual(world.value("ADISCORD_economy_current_month_action_income") - income, 300)
        world.variables["RUS_bunker_food"] = 39.99
        cash = world.value("ADISCORD_economy_treasury")
        world.run("RUS_bunker_food_sale")
        self.assertEqual((world.value("RUS_bunker_food"), world.value("ADISCORD_economy_treasury")), (39.99, cash))
        depot = block(self.focuses["RUS_recovery_depots"], "completion_reward")
        self.assertEqual(scalar(depot, "add_ideas"), "RUS_repair_depots_spirit")
        self.assertFalse(any(entry.key == "add_equipment_to_stockpile" for entry in depot))
        output = world.value("RUS_bunker_food_output")
        world.execute(depot)
        self.assertEqual(world.value("RUS_bunker_food_output"), output + 2)
        self.assertIn("RUS_bunker_food_sale", self.decisions)

    def test_emergency_ration_focus_reports_bounded_delivery(self):
        for stock, expected in ((60, 100), (140, 160)):
            world = self.world()
            world.variables["RUS_bunker_food_capacity_bonus"] = 40
            world.variables["RUS_bunker_food"] = stock
            world.run("RUS_bunker_refresh")
            world.execute(block(self.focuses["RUS_bunker_emergency_rations"], "completion_reward"))
            self.assertEqual(world.value("RUS_bunker_food"), expected)
            self.assertEqual(world.value("RUS_bunker_food_capacity"), 160)
        self.assertIn("до §G+40§!", self.loc["RUS_bunker_food_reserve_focus_tt"])
        self.assertIn("Излишек не сохраняется", self.loc["RUS_bunker_food_reserve_focus_tt"])

    def test_food_pulse_is_tag_scoped_and_stocks_are_not_gui_mutations(self):
        on = block(parse("common/on_actions/01_ADISCORD_vorkerland_collapse_on_actions.txt"), "on_actions")
        weekly = list(walk(block(on, "on_weekly_RUS")))
        self.assertIn("RUS_bunker_weekly_supply", [entry.key for entry in weekly])
        self.assertFalse(any(entry.key in ("every_country", "every_possible_country") for entry in weekly))
        actions = block(block(block(parse("common/scripted_guis/ADISCORD_RUS_scripted_gui.txt"), "scripted_gui"), "ADISCORD_RUS_bunker_panel"), "effects")
        for layer in range(1, 6):
            click = list(walk(block(actions, f"RUS_bunker_floor_{layer}_click")))
            self.assertEqual([entry.key for entry in click if entry.key not in ("var", "value")], ["set_variable"])
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
        window = block(block(parse("interface/ADISCORD_RUS.gui"), "guiTypes"), "containerWindowType")
        widgets = {scalar(child.value, "name"): child.value for child in window if child.key in ("buttonType", "instantTextBoxType")}
        panel = block(block(parse("common/scripted_guis/ADISCORD_RUS_scripted_gui.txt"), "scripted_gui"), "ADISCORD_RUS_bunker_panel")
        visibility = block(panel, "triggers")
        actions = (("guard", 1), ("shelter", 1), ("water", 2), ("signals", 2), ("workshop", 3), ("granary", 3), ("clinic", 4), ("laboratory", 4), ("archive", 5), ("command", 5))
        actions += tuple((f"upgrade_{layer}", layer) for layer in range(1, 6))
        world = self.world()
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
                    self.assertEqual(world.matches(block(visibility, row_name + "_visible")), selected == layer, row_name)

    def test_panel_pictures_and_widgets_fit_declared_bounds(self):
        window = block(block(parse("interface/ADISCORD_RUS.gui"), "guiTypes"), "containerWindowType")
        dimensions = block(window, "size")
        width = float(scalar(dimensions, "width"))
        height = float(scalar(dimensions, "height"))
        pictures = []
        for child in window:
            if child.key not in ("buttonType", "iconType", "instantTextBoxType"):
                continue
            name = scalar(child.value, "name")
            position = block(child.value, "position")
            x = float(scalar(position, "x"))
            y = float(scalar(position, "y"))
            if child.key == "iconType":
                sprite = scalar(child.value, "spriteType")
                self.assertRegex(sprite, r"^GFX_RUS_bunker_layer_[1-5]$")
                scale = float(scalar(child.value, "scale"))
                w, h = 464 * scale, 256 * scale
                pictures.append(name)
            elif child.key == "buttonType":
                size = block(child.value, "size")
                w, h = float(scalar(size, "x")), float(scalar(size, "y"))
            else:
                w = float(scalar(child.value, "maxWidth"))
                h = float(scalar(child.value, "maxHeight"))
            self.assertGreaterEqual(x, 0, name)
            self.assertGreaterEqual(y, 0, name)
            self.assertLessEqual(x + w, width, name)
            self.assertLessEqual(y + h, height, name)
        self.assertEqual(len(pictures), 10)
        panel = block(block(parse("common/scripted_guis/ADISCORD_RUS_scripted_gui.txt"), "scripted_gui"), "ADISCORD_RUS_bunker_panel")
        visibility = block(panel, "triggers")
        world = self.world()
        for selected in range(1, 6):
            world.variables["RUS_bunker_selected_layer"] = selected
            shown = [layer for layer in range(1, 6) if world.matches(block(visibility, f"RUS_bunker_selected_picture_{layer}_visible"))]
            self.assertEqual(shown, [selected])

    def test_gui_tooltips_are_leaf_strings_and_buttons_use_scalable_sprites(self):
        gui = parse("interface/ADISCORD_RUS.gui")
        keys = {entry.value.strip('"') for entry in walk(gui) if entry.key == "pdx_tooltip"}
        functions = {
            scalar(row.value, "name"): row.value
            for row in parse("common/scripted_localisation/ADISCORD_RUS_scripted_loc.txt")
            if row.key == "defined_text"
        }
        seen = set()
        while keys:
            key = keys.pop()
            if key in seen:
                continue
            seen.add(key)
            self.assertTrue(key in self.loc, key)
            text = self.loc[key]
            self.assertNotIn("$", text, key)
            for name in re.findall(r"\[(GetRUS\w+)\]", text):
                self.assertTrue(name in functions, name)
                keys.update(entry.value for entry in walk(functions[name]) if entry.key == "localization_key")
        sprites = block(parse("interface/ADISCORD_RUS.gfx"), "spriteTypes")
        buttons = [row for row in sprites if isinstance(row.value, list) and scalar(row.value, "name").strip('"') == "GFX_RUS_bunker_button"]
        self.assertEqual(len(buttons), 1)
        self.assertEqual(buttons[0].key, "corneredTileSpriteType")
        self.assertNotIn("GFX_SHL_furnace_button", read("interface/ADISCORD_RUS.gui"))

    def test_terminal_shutdown_refunds_and_clears_policies(self):
        world = self.world()
        world.ideas = {name for name in self.ideas if name.startswith("RUS_") and not name.endswith(("_delta", "_bookmark"))}
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
        self.assertEqual(len(events), 11)
        registry = json.loads(read("tools/data/adiscord_event_ids.json"))["events"]
        for event in events:
            name = scalar(event, "id")
            registered = [row for row in registry if row["id"] == name]
            self.assertEqual(len(registered), 1)
            self.assertEqual(registered[0]["number"], int(name.rsplit(".", 1)[1]))
            option = block(event, "option")
            self.assertEqual([e.key for e in option], ["name"])

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
        decisions = {entry.key: entry.value for entry in block(parse(f"common/decisions/{BASE}_decisions.txt"), "RUS_state_balance_category")}
        prices = {"RUS_bop_relief": (25, "RUS_bunker_food", 20), "RUS_bop_reserve": (30, "RUS_bunker_food", 30), "RUS_bop_mediation": (40, "ADISCORD_economy_treasury", 200)}
        for name, (pp, resource, amount) in prices.items():
            rows = decisions[name]
            world = self.world()
            world.decisions = decisions
            world.pp = pp
            world.variables[resource] = amount
            world.bop = 0.45
            self.assertTrue(world.matches(block(rows, "custom_cost_trigger")), name)
            for shortage in ("pp", "resource"):
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
            self.assertEqual(world.value("ADISCORD_economy_current_month_action_costs") - spent, 200 if name == "RUS_bop_mediation" else 0, name)
            self.assertEqual(scalar(rows, "cost"), "0", name)
            self.assertEqual(scalar(rows, "days_re_enable"), "90", name)

    def test_bop_food_orders_refresh_hunger_without_touching_construction_receipt(self):
        decisions = {entry.key: entry.value for entry in block(parse(f"common/decisions/{BASE}_decisions.txt"), "RUS_state_balance_category")}
        for name, food in (("RUS_bop_relief", 20), ("RUS_bop_reserve", 30)):
            world = self.world()
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
            self.assertAlmostEqual(world.value("RUS_bunker_army_org_factor"), org - 0.05, msg=name)
            self.assertAlmostEqual(world.value("RUS_bunker_stability_factor"), stability - 0.05, msg=name)
            self.assertIn("RUS_bunker_excavate", world.active, name)
            self.assertEqual(world.equipment, equipment, name)
            self.assertEqual(world.value("ADISCORD_economy_treasury"), cash, name)
            self.assertEqual({key: world.variables[key] for key in receipt}, receipt, name)

    def test_bop_directions_and_eligibility_respect_exact_boundaries(self):
        decisions = {entry.key: entry.value for entry in block(parse(f"common/decisions/{BASE}_decisions.txt"), "RUS_state_balance_category")}
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
            "army_defence_factor": "RUS_army_defence",
            "supply_consumption_factor": "RUS_army_supply",
            "army_speed_factor": "RUS_army_speed",
            "planning_speed": "RUS_army_planning",
            "training_time_army_factor": "RUS_army_training",
        }
        modifier = block(parse(f"common/dynamic_modifiers/{BASE}_dynamic_modifiers.txt"), "RUS_black_army")
        actual = {entry.key: entry.value for entry in modifier if entry.key not in ("icon", "enable", "custom_modifier_tooltip")}
        self.assertEqual(actual, mapping)
        expected = {"RUS_army_org": 0.08, "RUS_army_attack": 0.05, "RUS_army_recruitment": 0.06, "RUS_army_growth": 0.05}
        for variable in mapping.values():
            self.assertAlmostEqual(world.value(variable), expected.get(variable, 0), msg=variable)
        self.assertIn("RUS_black_army", world.modifiers)
        static = block(block(parse("common/ideas/ADISCORD_country_unique_ideas.txt"), "ideas"), "country")
        for name in ("RUS_national_spirit", "RUS_last_empire_spirit"):
            values = {entry.key for entry in block(block(static, name), "modifier")}
            self.assertFalse(values & mapping.keys(), name)

    def test_bookmark_previews_match_startup_and_are_never_installed(self):
        world = BunkerWorld(self, fresh=True)
        bookmark = block(block(parse("common/bookmarks/the_gathering_storm.txt"), "bookmarks"), "bookmark")
        displayed = {entry.value for entry in block(block(bookmark, "RUS"), "ideas")}
        previews = {"RUS_black_army_bookmark", "RUS_bunker_complex_bookmark"}
        self.assertEqual(displayed, previews | {"RUS_national_spirit"})
        dynamic = block(parse(f"common/dynamic_modifiers/{BASE}_dynamic_modifiers.txt"), "RUS_black_army")
        initial = {row.key: world.value(row.value) for row in dynamic if isinstance(row.value, str) and row.value.startswith("RUS_army_") and world.value(row.value)}
        preview = {row.key: float(row.value) for row in block(self.ideas["RUS_black_army_bookmark"], "modifier")}
        self.assertEqual(preview, initial)
        self.assertFalse(any(row.key == "modifier" for row in self.ideas["RUS_bunker_complex_bookmark"]))
        for name in previews:
            self.assertEqual(scalar(block(self.ideas[name], "allowed"), "always"), "no")
            self.assertNotIn(name, world.ideas)
        definitions = {f"common/ideas/{BASE}_ideas.txt", "common/bookmarks/the_gathering_storm.txt"}
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
        }
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
        army = block(parse(f"common/dynamic_modifiers/{BASE}_dynamic_modifiers.txt"), "RUS_black_army")
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
        dynamic = parse(f"common/dynamic_modifiers/{BASE}_dynamic_modifiers.txt")
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
        self.assertAlmostEqual(world.value("RUS_bunker_army_org_factor"), org - 0.05)
        self.assertAlmostEqual(world.value("RUS_bunker_stability_factor"), stability - 0.05)
        self.assertEqual(world.dirty, dirty + 1)
        world.run("RUS_bunker_weekly_supply")
        self.assertEqual(world.dirty, dirty + 1)
        self.assertEqual(world.value("RUS_bunker_food"), 0)
        world.variables["RUS_bunker_food_output_bonus"] = 2
        world.run("RUS_bunker_refresh")
        dirty = world.dirty
        world.run("RUS_bunker_weekly_supply")
        self.assertEqual(world.value("RUS_bunker_food"), 1)
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
        self.assertEqual(scalar(block(self.focuses["RUS_aimaq_council"], "prerequisite"), "focus"), "RUS_scientists_council")
        self.assertEqual(scalar(block(self.focuses["RUS_seal_chancery"], "prerequisite"), "focus"), "RUS_black_army_oath")
        for focus in ("RUS_scientists_council", "RUS_black_army_oath"):
            self.assertFalse(any(entry.key == "mutually_exclusive" for entry in self.focuses[focus]), focus)
        removed = {"RUS_reaffirm_khan", "RUS_army_mandate", "RUS_reconstruction_cabinet", "RUS_political_course_chosen", "RUS_political_choice_open"}
        self.assertFalse(removed & self.focuses.keys())
        self.assertFalse(removed & self.triggers.keys())
        sources = [read(f"common/{path}") for path in (
            f"decisions/{BASE}_decisions.txt", f"scripted_effects/{BASE}_effects.txt",
            f"scripted_triggers/{BASE}_triggers.txt", f"dynamic_modifiers/{BASE}_dynamic_modifiers.txt",
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
        modifier = block(parse(f"common/dynamic_modifiers/{BASE}_dynamic_modifiers.txt"), "RUS_faction_support")
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
        world.run("RUS_retire_current_ruler")
        self.assertIsNone(world.ruler)
        self.assertEqual(world.characters, {"RUS_Varlam_Oskol"})
        defeat = self.effects["RUS_crisis_dissolve_empire"]
        self.assertTrue(any(entry.key == "RUS_retire_current_ruler" for entry in defeat))
        winner = next(entry.value for entry in defeat if entry.key == "event_target:RUS_crisis_hegemon")
        self.assertEqual(scalar(winner[-1].value, "id"), "ADISCORD_rus_crisis.4")
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
        self.assertEqual([(scalar(row, "var"), scalar(row, "value")) for row in debits], [("ADISCORD_economy_treasury", "400")])
        refund = block(self.effects["RUS_reactor_works_refund"], "if")
        self.assertEqual(scalar(refund, "add_political_power"), "50")
        self.assertEqual(scalar(block(refund, "limit"), "has_variable"), "RUS_reactor_works_deposit")
        self.assertEqual(refund[1].key, "clear_variable", "The deposit is cleared before any payout")
        world = self.world()
        world.pp = 50
        world.variables["ADISCORD_economy_treasury"] = 400
        self.assertTrue(world.matches(self.triggers["RUS_reactor_works_affordable"]))
        world.variables["ADISCORD_economy_treasury"] = 399.99
        self.assertFalse(world.matches(self.triggers["RUS_reactor_works_affordable"]))
        world.variables["ADISCORD_economy_treasury"] = 400
        world.variables["RUS_reactor_works_deposit"] = 400
        before = world.pp, world.value("ADISCORD_economy_treasury")
        self.assertFalse(world.matches(self.triggers["RUS_reactor_works_idle"]))
        shutdown = self.effects["RUS_campaign_shutdown"]
        self.assertTrue(any(entry.key == "RUS_reactor_works_refund" for entry in shutdown))
        self.assertEqual(before, (50, 400))

    def test_reactor_sortie_charges_losses_once_and_pays_its_haul_once(self):
        for decontaminated, losses, haul in ((False, 1000, 150), (True, 500, 250)):
            world = self.world()
            world.decisions = {**world.decisions, **self.belt}
            world.held_states = {"188"}
            world.manpower = losses
            if not decontaminated:
                world.focuses.discard("RUS_reactor_decontamination")
            short = deepcopy(world)
            short.manpower = losses - 0.01
            self.assertFalse(short.matches(block(self.belt["RUS_reactor_sortie"], "custom_cost_trigger")))
            pp, cash = world.pp, world.value("ADISCORD_economy_treasury")
            world.begin("RUS_reactor_sortie")
            self.assertEqual((world.pp, world.manpower), (pp - 25, 0))
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

    def test_lab_projects_require_any_reactor_zone_one_slot_and_no_black_army_rule(self):
        focus = self.focuses["RUS_experimental_laboratories"]
        self.assertEqual(scalar(block(focus, "prerequisite"), "focus"), "RUS_bunker_science_wing")
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
        world.bop = 0.6001
        self.assertFalse(world.matches(block(alloys, "available")))
        world.bop = 0.60
        self.assertTrue(world.matches(block(alloys, "available")))
        world.begin("RUS_lab_reactor_alloys")
        self.assertFalse(world.matches(block(alloys, "available")))
        self.assertFalse(world.matches(block(self.labs["RUS_lab_zeppelin"], "visible")))
        world.owner = False
        self.assertTrue(world.matches(block(alloys, "cancel_trigger")))

    def test_lab_projects_charge_exact_prices_and_settle_once(self):
        world = self.lab_world()
        pp, cash = world.pp, world.value("ADISCORD_economy_treasury")
        world.begin("RUS_lab_reactor_alloys")
        self.assertEqual((world.pp, world.value("ADISCORD_economy_treasury")), (pp - 50, cash - 300))
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
                short.variables["ADISCORD_economy_treasury"] = 999.99
            else:
                short.manpower = 399.99
            self.assertFalse(short.matches(block(zeppelin, "custom_cost_trigger")), shortage)
        pp, cash, divisions = world.pp, world.value("ADISCORD_economy_treasury"), world.divisions
        world.begin("RUS_lab_zeppelin")
        self.assertEqual((world.pp, world.value("ADISCORD_economy_treasury"), world.manpower), (pp - 100, cash - 1000, 0))
        world.finish("RUS_lab_zeppelin")
        self.assertEqual(world.divisions, divisions + 1)
        self.assertEqual(world.templates, {"Rusnian Airship"})
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

    def test_ai_order_has_no_duplicates_and_keeps_crisis_preparations_together(self):
        plan = block(parse(f"common/ai_strategy_plans/{BASE}_plans.txt"), "ADISCORD_vorkerland_rus_last_empire_plan")
        order = [e.value for e in block(plan, "ai_national_focuses")]
        self.assertEqual(len(order), len(set(order)))
        self.assertTrue(set(order) <= self.focuses.keys())
        self.assertLess(order.index("RUS_bunker_survey"), order.index("RUS_claim_the_opened_zone"))
        start = order.index("RUS_imperial_general_staff")
        self.assertEqual(order[start:start + 4], ["RUS_imperial_general_staff", "RUS_western_supply_lines", "RUS_imperial_arsenals", "RUS_aimaq_reserve"])


if __name__ == "__main__":
    unittest.main()
