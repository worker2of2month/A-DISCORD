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

    def test_startup_and_weekly_recover_only_unseen_war_windows(self):
        for entry in ("VAL_initialize_logistics_market", "VAL_update_refugees_weekly"):
            calls = [e for e in self.effects[entry] if e.key == "VAL_open_refugee_waves"]
            self.assertEqual(len(calls), 1, f"{entry} must recover a missed war notification")
            self.assertEqual(calls[0].value, "yes")
            for region in REGIONS:
                with self.subTest(entry=entry, region=region):
                    self.setUp()
                    self.facts[("VAL", f"VAL_refugee_{region}_war", "yes")] = True
                    self.run_effect(self.effects[calls[0].key])
                    window = f"VAL_refugee_{region}_window"
                    self.assertTrue(self.visible(region))
                    self.assertEqual(self.windows[window], 180)
                    self.facts[("VAL", "has_country_flag", window)] = False
                    self.run_effect(self.effects[calls[0].key])
                    self.assertFalse(self.visible(region), "Expired windows must not be restarted")

    def test_each_war_opens_once_and_expiry_does_not_reopen(self):
        for region in REGIONS:
            with self.subTest(region=region):
                self.facts[("VAL", f"VAL_refugee_{region}_war", "yes")] = True
                self.run_effect(self.effects["VAL_open_refugee_waves"])
                flag = f"VAL_refugee_{region}_window"
                self.assertEqual(self.windows[flag], 180)
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
            self.assertEqual(scalar(body, "days_re_enable"), "30")
            reward = next(e.value for e in body if e.key == "complete_effect")
            self.assertEqual(sum(e.key == "ADISCORD_economy_spend_250" for e in reward), 1)
            self.assertFalse(any(e.key == "clr_country_flag" for e in reward))
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
            facts[("VAL", "variable", "VAL_displaced_population")] = 0
            facts[("VAL", "variable", f"VAL_refugee_{region}_admitted")] = 3
            self.assertFalse(matches_conditions(available, facts, "VAL"))
            facts[("VAL", "variable", f"VAL_refugee_{region}_admitted")] = 2
            facts[("VAL", "has_variable", "VAL_refugee_training_escrow")] = True
            facts[("VAL", "variable", "VAL_displaced_population")] = 81
            self.assertFalse(matches_conditions(available, facts, "VAL"))
            facts[("VAL", "variable", "VAL_displaced_population")] = 80
            self.assertTrue(matches_conditions(available, facts, "VAL"))

    def test_perimeter_opening_creates_one_bounded_admission_window(self):
        trigger = self.triggers["VAL_refugee_perimeter_open"]
        self.assertTrue(matches_conditions(
            trigger,
            {("VAL", "has_global_flag", "ADISCORD_vorkerland_dirty_opened"): True},
            "VAL",
        ))
        self.facts[("VAL", "VAL_refugee_perimeter_open", "yes")] = True
        self.run_effect(self.effects["VAL_open_refugee_waves"])
        flag = "VAL_refugee_perimeter_window"
        self.assertEqual(self.windows[flag], 180)
        self.assertTrue(self.visible("perimeter"))
        self.facts[("VAL", "has_country_flag", flag)] = False
        self.run_effect(self.effects["VAL_open_refugee_waves"])
        self.assertFalse(self.visible("perimeter"), "The one-time Perimeter window must not renew")

    def test_resettlement_depots_move_people_into_low_population_home_states(self):
        body = self.decisions["VAL_fund_resettlement_depots"]
        self.assertEqual(scalar(body, "state_target"), "yes")
        targets = next(e.value for e in body if e.key == "targets")
        self.assertEqual({int(e.value) for e in targets}, {24, 42, 55, 56})
        self.assertEqual(scalar(body, "cost"), "0")
        self.assertEqual(scalar(body, "custom_cost_text"), "VAL_logistics_cost_250")

        available = next(e.value for e in body if e.key == "available")
        state_gate = next(e.value for e in available if e.key == "FROM")
        def negates(key, value=None):
            for entry in state_gate:
                if entry.key != "NOT":
                    continue
                for child in entry.value:
                    if child.key != key:
                        continue
                    if value is None and child.value:
                        return True
                    if key == "has_dynamic_modifier" and scalar(child.value, "modifier") == value:
                        return True
                    if child.value == value:
                        return True
            return False
        self.assertTrue(negates("has_state_flag", "VAL_refugee_resettled_once"))
        for modifier in (
            "ADISCORD_vorkerland_dirty_state",
            "VAL_reclamation_stage_1_modifier",
            "VAL_reclamation_stage_2_modifier",
        ):
            self.assertTrue(negates("has_dynamic_modifier", modifier), modifier)

        reward = next(e.value for e in body if e.key == "complete_effect")
        self.assertEqual(sum(e.key == "ADISCORD_economy_spend_250" for e in reward), 1)
        pool = [e.value for e in reward if e.key == "add_to_variable"
                and scalar(e.value, "var") == "VAL_displaced_population"]
        self.assertEqual(len(pool), 1)
        self.assertEqual(scalar(pool[0], "value"), "-10")
        destination = next(e.value for e in reward if e.key == "FROM")
        self.assertEqual(scalar(destination, "add_manpower"), "100000")
        self.assertEqual(scalar(destination, "set_state_flag"), "VAL_refugee_resettled_once")
        self.assertFalse(any(e.key == "add_manpower" for e in reward),
                         "Resettlement must increase state population, not the country manpower pool")

        for language in ("english", "russian"):
            loc = (ROOT / f"localisation/{language}/ADISCORD_VAL_logistics_market_l_{language}.yml").read_text(encoding="utf-8-sig")
            self.assertIn("VAL_accept_perimeter_refugees:", loc)
            self.assertIn("[FROM.GetName]", loc)
            self.assertIn("VAL_fund_resettlement_depots:", loc)
            self.assertIn("180", loc)

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
        self.decisions = {e.key: e.value for e in load("common/decisions/ADISCORD_VAL_decisions.txt")["VAL_foreign_sales"]}
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
                try:
                    amount = float(raw)
                except ValueError:
                    amount = self.variables.get(raw, 0)
                self.variables[name] = amount + (self.variables.get(name, 0) if key == "add_to_variable" else 0)
            elif key == "clear_variable":
                self.variables.pop(value, None)
            elif key == "set_country_flag":
                self.facts[("VAL", "has_country_flag", value)] = True
            elif key in {"ADISCORD_economy_initialize_country", "ADISCORD_economy_mark_dirty", "VAL_refresh_trade_network", "VAL_refresh_refugee_state", "VAL_change_black_market_pressure", "set_temp_variable", "force_update_dynamic_modifier", "custom_effect_tooltip"}:
                continue
            elif key in ("add_manpower", "add_political_power"):
                self.rewards.append((key, int(value)))
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



class RefugeeTrainingTests(unittest.TestCase):
    execute = CorridorProjectTests.execute
    run_effect = CorridorProjectTests.run_effect
    decision_effect = CorridorProjectTests.decision_effect

    def setUp(self):
        self.effects = load("common/scripted_effects/ADISCORD_VAL_logistics_market_effects.txt")
        self.decisions = {e.key: e.value for e in load("common/decisions/ADISCORD_VAL_logistics_market_decisions.txt")["VAL_population_markets"]}
        self.variables = {"VAL_displaced_population": 10}
        self.facts = {("VAL", "has_capitulated", "no"): True, ("VAL", "is_subject", "no"): True}
        self.rewards = []

    def test_training_reserves_people_and_cannot_deliver_twice(self):
        self.decision_effect("VAL_train_refugee_volunteers", "complete_effect")
        self.assertEqual(self.variables["VAL_displaced_population"], 0)
        self.assertEqual(self.variables["VAL_refugee_training_escrow"], 10)
        self.assertEqual(self.rewards, [])
        for _ in range(2):
            self.decision_effect("VAL_train_refugee_volunteers", "remove_effect")
        self.decision_effect("VAL_train_refugee_volunteers", "cancel_effect")
        self.assertEqual(self.rewards, [("add_manpower", 5000)])
        self.assertNotIn("VAL_refugee_training_escrow", self.variables)

    def test_country_loss_refunds_people_and_pp_once_without_recruits(self):
        for failed in ("has_capitulated", "is_subject"):
            with self.subTest(failed=failed):
                self.setUp()
                self.decision_effect("VAL_train_refugee_volunteers", "complete_effect")
                self.facts[("VAL", failed, "no")] = False
                self.decision_effect("VAL_train_refugee_volunteers", "remove_effect")
                self.decision_effect("VAL_train_refugee_volunteers", "cancel_effect")
                self.assertEqual(self.variables["VAL_displaced_population"], 10)
                self.assertEqual(self.rewards, [("add_political_power", 75)])
                self.assertNotIn("VAL_refugee_training_escrow", self.variables)

    def test_active_training_and_fractional_shortage_block_new_payment(self):
        body = next(e.value for e in self.decisions["VAL_train_refugee_volunteers"] if e.key == "available")
        for people, active, expected in ((9.9, False, False), (10, False, True), (20, True, False)):
            facts = {**self.facts, ("VAL", "variable", "VAL_displaced_population"): people,
                     ("VAL", "has_variable", "VAL_refugee_training_escrow"): active}
            self.assertEqual(matches_conditions(body, facts, "VAL"), expected)



class FinalSupplySettlementTests(unittest.TestCase):
    execute = CorridorProjectTests.execute
    run_effect = CorridorProjectTests.run_effect
    decision_effect = CorridorProjectTests.decision_effect

    def setUp(self):
        self.effects = load("common/scripted_effects/ADISCORD_VAL_effects.txt")
        self.effects.update(load("common/scripted_effects/ADISCORD_shared_action_effects.txt"))
        self.decisions = {e.key: e.value for e in load("common/decisions/ADISCORD_VAL_decisions.txt")["VAL_final_war"]}
        self.variables = {"ADISCORD_economy_treasury": 500, "VAL_final_crisis_phase": 1}
        self.facts = {("VAL", "has_capitulated", "no"): True, ("VAL", "is_subject", "no"): True}
        self.rewards = []

    def test_war_start_keeps_paid_supply_order_and_completion_consumes_receipt(self):
        self.decision_effect("VAL_final_stockpile_supplies", "complete_effect")
        self.assertEqual(self.variables["ADISCORD_economy_treasury"], 0)
        self.variables["VAL_final_crisis_phase"] = 2
        self.decision_effect("VAL_final_stockpile_supplies", "remove_effect")
        self.assertEqual(self.variables["VAL_final_supply_bonus"], -0.1)
        self.assertNotIn("VAL_final_supply_deposit", self.variables)
        self.decision_effect("VAL_final_stockpile_supplies", "cancel_effect")
        self.assertEqual(self.variables["ADISCORD_economy_treasury"], 0)

    def test_terminal_phase_refunds_once_and_cannot_deliver_bonus(self):
        for phase in (3, 4):
            with self.subTest(phase=phase):
                self.setUp()
                self.decision_effect("VAL_final_stockpile_supplies", "complete_effect")
                self.variables["VAL_final_crisis_phase"] = phase
                self.run_effect("VAL_final_refund_supply_order")
                self.decision_effect("VAL_final_stockpile_supplies", "cancel_effect")
                self.decision_effect("VAL_final_stockpile_supplies", "remove_effect")
                self.assertEqual(self.variables["ADISCORD_economy_treasury"], 500)
                self.assertEqual(self.variables["ADISCORD_economy_current_month_action_income"], 500)
                self.assertNotIn("VAL_final_supply_deposit", self.variables)
                self.assertNotIn("VAL_final_supply_bonus", self.variables)


if __name__ == "__main__":
    unittest.main()
