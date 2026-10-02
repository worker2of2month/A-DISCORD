"""Parsed RUS accounting and campaign contracts; not native-engine simulation."""

from copy import deepcopy
from itertools import product
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
        self.subject = False
        self.capitulated = False
        self.war = True
        self.owner = True
        self.controller = True
        self.dirty = 0
        self.buildings = {"infrastructure": 2, "arms_factory": 1, "industrial_complex": 0}
        self.building_slots = 5
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
                assert value in ("has_political_power", "infrastructure"), value
                operator, amount = rows[index:index + 2]
                index += 2
                current = self.pp if value == "has_political_power" else self.buildings[value]
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
            elif key in ("is_subject", "has_capitulated"):
                result = {"is_subject": self.subject, "has_capitulated": self.capitulated}[key] == (value == "yes")
            elif key == "has_war":
                result = self.war == (value == "yes")
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
            elif key == "free_building_slots":
                occupied = self.buildings["arms_factory"] + self.buildings["industrial_complex"]
                result = self.building_slots - occupied >= int(scalar(value, "size"))
            elif key in ("owns_state", "controls_state"):
                assert value == "66"
                result = self.owner if key == "owns_state" else self.controller
            elif key == "always":
                result = value == "yes"
            else:
                raise AssertionError(f"Unsupported condition: {entry}")
            results.append(result)
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
            elif key == "add_building_construction":
                self.buildings[scalar(value, "type")] += int(scalar(value, "level"))
            elif key == "add_timed_idea":
                self.ideas.add(scalar(value, "idea"))
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
                if key.startswith("add"):
                    self.ideas.add(value)
                else:
                    self.ideas.discard(value)
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
        tree = block(parse("focus_trees/RUS/main/focuses.txt"), "focus_tree")
        cls.focuses = {scalar(e.value, "id"): e.value for e in tree if e.key == "focus"}
        cls.ideas = {e.key: e.value for e in block(block(parse(f"common/ideas/{BASE}_ideas.txt"), "ideas"), "country")}
        cls.projects = [name for name, rows in cls.decisions.items() if any(e.key == "days_remove" for e in rows)]
        cls.loc = dict(re.findall(r'^\s+([A-Za-z0-9_.]+):(?:\d+)?\s+"(.*)"\s*$', read(f"localisation/russian/{BASE}_l_russian.yml"), re.M))

    def world(self):
        return BunkerWorld(self)

    def test_generation_and_one_hundred_focuses(self):
        self.assertEqual(len(self.focuses), 100)
        path = ROOT / "common/national_focus/ADISCORD_national_focus_RUS.txt"
        self.assertEqual(path.read_bytes(), expected_outputs()[path])

    def test_propaganda_focuses_grant_two_shared_slots_and_unlock_six_campaigns(self):
        world = self.world()
        self.assertEqual(len(self.campaigns), 6)
        for index, focus in enumerate(("RUS_khan_broadcast_service", "RUS_parallel_public_addresses"), 1):
            reward = block(self.focuses[focus], "completion_reward")
            grants = [entry for entry in walk(reward) if entry.key == "ADISCORD_campaign_slot_grant"]
            self.assertEqual(len(grants), 1)
            before = world.pp
            world.execute(reward)
            self.assertEqual(world.value("ADISCORD_available_campaign_slots"), index)
            self.assertEqual(world.pp, before)
        unlocks = {entry.value for entry in walk(block(self.focuses["RUS_khan_broadcast_service"], "completion_reward")) if entry.key == "unlock_decision_tooltip"}
        self.assertEqual(unlocks, self.campaigns.keys())

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
                self.assertEqual(world.buildings["arms_factory"], 2)
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
            "RUS_chancery_reconstruction": ("arms_factory", 5),
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
        pairs = (("aimaq_council", "seal_chancery"), ("patient_war", "swift_columns"), ("bunker_open_city", "bunker_sealed_throne"), ("surface_contracts", "underground_fund"))
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
        self.assertEqual(world.balances(), (before[0] - 15, before[1] - 100, before[2]))
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
        world.pp = 15
        world.variables["ADISCORD_economy_treasury"] = 100
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
        world.ideas = {name for name in self.ideas if name.startswith("RUS_") and not name.endswith("_delta")}
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
            self.assertIn(name, self.loc)
            self.assertIn(name + "_desc", self.loc)
            key = next((e.value for e in rows if e.key == "custom_cost_text"), None)
            if key:
                self.assertEqual(scalar(rows, "cost"), "0")
                for suffix in ("", "_blocked", "_tooltip"):
                    self.assertIn(key + suffix, self.loc)
        for name in self.focuses:
            self.assertIn(name, self.loc)
            self.assertIn(name + "_desc", self.loc)
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
