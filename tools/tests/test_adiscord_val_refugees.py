import re
import unittest
import wave
from pathlib import Path

from tools.tests.test_adiscord_stp_preparation import matches_conditions, scalar
from tools.validators.validate_adiscord_division_templates import parse_clausewitz

ROOT = Path(__file__).resolve().parents[2]
REGIONS = ("vorkerland", "stelander", "nodrul", "north")


def load(path):
    return {e.key: e.value for e in parse_clausewitz((ROOT / path).read_text(encoding="utf-8-sig"))}


class RefugeeAdmissionTests(unittest.TestCase):
    def setUp(self):
        self.effects = load("common/scripted_effects/ADISCORD_VAL_logistics_market_effects.txt")
        self.triggers = load("common/scripted_triggers/ADISCORD_VAL_logistics_market_triggers.txt")
        self.decisions = {e.key: e.value for e in load("common/decisions/ADISCORD_VAL_logistics_market_decisions.txt")["VAL_population_markets"]}
        self.facts = {}
        self.windows = {}

    def run_effect(self, items):
        for e in items:
            if e.key == "if":
                if matches_conditions(next(c.value for c in e.value if c.key == "limit"), self.facts, "VAL"):
                    self.run_effect([c for c in e.value if c.key != "limit"])
            elif e.key == "set_country_flag":
                flag = scalar(e.value, "flag") if isinstance(e.value, list) else e.value
                self.facts[("VAL", "has_country_flag", flag)] = True
                if isinstance(e.value, list):
                    self.windows[flag] = int(scalar(e.value, "days"))
            else:
                self.fail(f"Unhandled admission effect: {e.key}")

    def visible(self, region):
        body = next(e.value for e in self.decisions[f"VAL_accept_{region}_refugees"] if e.key == "visible")
        return matches_conditions(body, self.facts, "VAL")

    def test_each_war_opens_once_and_expiry_does_not_reopen(self):
        for region in REGIONS:
            with self.subTest(region=region):
                self.facts[("VAL", f"VAL_refugee_{region}_war", "yes")] = True
                self.run_effect(self.effects["VAL_open_refugee_waves"])
                flag = f"VAL_refugee_{region}_window"
                self.assertEqual(self.windows[flag], 60)
                self.assertTrue(self.visible(region))
                self.facts[("VAL", "has_country_flag", flag)] = False
                for _ in range(4):
                    self.run_effect(self.effects["VAL_open_refugee_waves"])
                self.assertFalse(self.visible(region))

    def test_peace_hides_unspent_offer_immediately(self):
        self.facts[("VAL", "has_country_flag", "VAL_refugee_stelander_window")] = True
        self.assertFalse(self.visible("stelander"))
        self.facts[("VAL", "VAL_refugee_stelander_war", "yes")] = True
        self.assertTrue(self.visible("stelander"))

    def test_unrelated_wars_do_not_qualify(self):
        facts = {("STP", "has_war_with", "NOD"): True}
        for region in REGIONS:
            self.assertEqual(matches_conditions(self.triggers[f"VAL_refugee_{region}_war"], facts, "VAL"), region == "nodrul")

    def test_admission_cost_capacity_and_single_payment(self):
        for region in REGIONS:
            body = self.decisions[f"VAL_accept_{region}_refugees"]
            self.assertEqual(scalar(body, "fire_only_once"), "yes")
            reward = next(e.value for e in body if e.key == "complete_effect")
            self.assertEqual(sum(e.key == "ADISCORD_economy_spend_250" for e in reward), 1)
            self.assertEqual(scalar(reward, "clr_country_flag"), f"VAL_refugee_{region}_window")
            population = next(e.value for e in reward if e.key == "add_to_variable")
            self.assertEqual(scalar(population, "value"), "10")
            available = next(e.value for e in body if e.key == "available")
            facts = {("VAL", "ADISCORD_economy_can_spend_250", "yes"): True}
            self.assertTrue(matches_conditions(available, facts, "VAL"))
            facts[("VAL", "has_country_flag", "VAL_refugee_border_closed")] = True
            self.assertFalse(matches_conditions(available, facts, "VAL"))
            facts[("VAL", "has_country_flag", "VAL_refugee_border_closed")] = False
            facts[("VAL", "variable", "VAL_displaced_population")] = 91
            self.assertFalse(matches_conditions(available, facts, "VAL"))

    def test_no_population_faucet_or_permanent_stability_farming(self):
        def walk(items):
            for e in items:
                yield e
                if isinstance(e.value, list):
                    yield from walk(e.value)
        for e in walk(self.effects["VAL_update_refugees_weekly"]):
            if e.key == "add_to_variable":
                self.assertLess(float(scalar(e.value, "value")), 0)
        for body in self.decisions.values():
            self.assertFalse(any(e.key == "add_stability" for e in walk(body)))
        labor = list(walk(self.decisions["VAL_contract_refugee_labor"]))
        self.assertEqual(next(e.value for e in labor if e.key == "add_manpower"), "2500")


class KefreytVoiceTests(unittest.TestCase):
    def test_every_playable_clip_fits_shared_cooldown_at_slowest_pitch(self):
        text = (ROOT / "sound/adiscord_val_vo.asset").read_text()
        self.assertNotIn('sound = "VAL_neutral_003"', text)
        files = dict(re.findall(r'name = "(VAL_[^"]+)" file = "([^"]+)"', text))
        cooldown = float(re.search(r'VOICE_OVER_COOL_DOWN = ([0-9.]+)', (ROOT / "common/defines/ADISCORD_defines_changes.lua").read_text()).group(1))
        for effect in parse_clausewitz(text):
            if effect.key != "soundeffect":
                continue
            self.assertEqual(scalar(effect.value, "max_audible"), "1")
            sounds = next(e.value for e in effect.value if e.key == "sounds")
            for entry in sounds:
                with wave.open(str(ROOT / "sound" / files[entry.value])) as audio:
                    duration = audio.getnframes() / audio.getframerate()
                self.assertLess(duration / 0.85, cooldown, entry.value)


class CorridorProjectTests(unittest.TestCase):
    def setUp(self):
        self.effects = load("common/scripted_effects/ADISCORD_VAL_logistics_market_effects.txt")
        self.effects.update(load("common/scripted_effects/ADISCORD_shared_action_effects.txt"))
        self.decisions = {e.key: e.value for e in load("common/decisions/ADISCORD_VAL_logistics_market_decisions.txt")["VAL_trade_corridors"]}
        self.variables = {"ADISCORD_economy_treasury": 3000}
        self.facts = {("VAL", "has_capitulated", "no"): True}
        for region in ("occidia", "north", "stelander", "vorkerland"):
            self.facts[("VAL", f"VAL_trade_route_{region}_open", "yes")] = True
        self.rewards = []

    def execute(self, items):
        matched = False
        for e in items:
            key, value = e.key, e.value
            if key in ("if", "else_if", "else"):
                if key == "if":
                    matched = False
                facts = dict(self.facts)
                for name, amount in self.variables.items():
                    facts[("VAL", "variable", name)] = amount
                    facts[("VAL", "has_variable", name)] = True
                guard = next((c.value for c in value if c.key == "limit"), [])
                if not matched and matches_conditions(guard, facts, "VAL"):
                    matched = True
                    self.execute([c for c in value if c.key != "limit"])
            elif key == "hidden_effect":
                self.execute(value)
            elif key in ("set_variable", "add_to_variable"):
                name, raw = scalar(value, "var"), scalar(value, "value")
                amount = self.variables.get(raw, 0) if not raw.lstrip("-").isdigit() else int(raw)
                self.variables[name] = amount + (self.variables.get(name, 0) if key == "add_to_variable" else 0)
            elif key == "clear_variable":
                self.variables.pop(value, None)
            elif key == "set_country_flag":
                self.facts[("VAL", "has_country_flag", value)] = True
            elif key in {"ADISCORD_economy_initialize_country", "ADISCORD_economy_mark_dirty", "VAL_refresh_trade_network", "VAL_change_black_market_pressure", "set_temp_variable", "custom_effect_tooltip"}:
                continue
            elif key in self.effects:
                self.execute(self.effects[key])
            elif key.isdigit() or key == "build_railway":
                self.rewards.append(key)
            else:
                self.fail(f"Unsupported corridor effect: {key}")

    def run_effect(self, name):
        self.execute(self.effects[name])

    def decision_effect(self, name, effect):
        self.execute(next(e.value for e in self.decisions[name] if e.key == effect))

    def test_one_paid_project_blocks_other_routes_and_delivers_only_once(self):
        self.run_effect("VAL_begin_occidia_corridor_project")
        self.assertEqual(self.variables["ADISCORD_economy_treasury"], 2250)
        self.assertEqual(self.variables["ADISCORD_economy_current_month_action_costs"], 750)
        self.assertEqual(self.rewards, [])
        self.run_effect("VAL_begin_north_corridor_project")
        self.assertEqual(self.variables["VAL_corridor_project"], 1)
        self.assertEqual(self.variables["ADISCORD_economy_treasury"], 2250)
        self.decision_effect("VAL_invest_northern_corridor", "cancel_effect")
        self.assertEqual(self.variables["VAL_corridor_deposit"], 750)
        self.decision_effect("VAL_invest_occidian_corridor", "remove_effect")
        count = len(self.rewards)
        self.assertGreater(count, 0)
        self.assertNotIn("VAL_corridor_deposit", self.variables)
        self.decision_effect("VAL_invest_occidian_corridor", "remove_effect")
        self.assertEqual(len(self.rewards), count)
        self.run_effect("VAL_begin_occidia_corridor_project")
        self.assertNotIn("VAL_corridor_deposit", self.variables)

    def test_loss_at_delivery_refunds_exact_payment_and_allows_retry(self):
        self.run_effect("VAL_begin_north_corridor_project")
        self.assertEqual(self.variables["ADISCORD_economy_treasury"], 2000)
        self.facts[("VAL", "VAL_trade_route_north_open", "yes")] = False
        self.decision_effect("VAL_invest_northern_corridor", "remove_effect")
        self.assertEqual(self.variables["ADISCORD_economy_treasury"], 3000)
        self.assertEqual(self.variables["ADISCORD_economy_current_month_action_income"], 1000)
        self.assertEqual(self.rewards, [])
        self.decision_effect("VAL_invest_northern_corridor", "cancel_effect")
        self.assertEqual(self.variables["ADISCORD_economy_treasury"], 3000)
        self.facts[("VAL", "VAL_trade_route_north_open", "yes")] = True
        self.run_effect("VAL_begin_north_corridor_project")
        self.assertEqual(self.variables["ADISCORD_economy_treasury"], 2000)

    def test_affordability_boundary(self):
        self.variables["ADISCORD_economy_treasury"] = 749
        self.run_effect("VAL_begin_occidia_corridor_project")
        self.assertNotIn("VAL_corridor_deposit", self.variables)
        self.variables["ADISCORD_economy_treasury"] = 750
        self.run_effect("VAL_begin_occidia_corridor_project")
        self.assertEqual(self.variables["ADISCORD_economy_treasury"], 0)

    def test_formations_are_offered_after_assembly_with_time_left_for_reply(self):
        categories = load("common/decisions/ADISCORD_VAL_decisions.txt")
        decision = next(d.value for cat in categories.values() for d in cat if d.key == "VAL_cw_offer_contract_formations")
        def walk(items):
            for e in items:
                yield e
                if isinstance(e.value, list):
                    yield from walk(e.value)
        complete = next(e.value for e in decision if e.key == "complete_effect")
        finish = next(e.value for e in decision if e.key == "remove_effect")
        self.assertFalse(any(e.key == "country_event" for e in walk(complete)))
        self.assertTrue(any(e.key == "country_event" for e in walk(finish)))
        pending = next(e.value for e in walk(complete) if e.key == "set_country_flag")
        self.assertEqual(int(scalar(pending, "days")) - int(scalar(decision, "days_remove")), 14)


if __name__ == "__main__":
    unittest.main()
