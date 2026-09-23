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


class WeeklyTradeTests(unittest.TestCase):
    def setUp(self):
        self.effects = load("common/scripted_effects/ADISCORD_VAL_logistics_market_effects.txt")
        self.triggers = load("common/scripted_triggers/ADISCORD_VAL_logistics_market_triggers.txt")
        self.facts = {("VAL", "has_completed_focus", "VAL_Reopen_Trade_Routes"): True,
                      ("VAL", "has_idea", "VAL_emergency_bypass"): True,
                      ("VAL", "has_country_flag", "VAL_route_occidia_upgraded"): True}
        self.variables = {"ADISCORD_economy_treasury": 100, "VAL_black_market_pressure": 10,
                          "VAL_trade_corridors_capacity": 4, "VAL_trade_corridors_active": 4}
        self.route_reads = []
        self.consumer = None
        for route in ("occidia", "north", "stelander", "vorkerland"):
            self.facts["VAL", "has_country_flag", f"VAL_route_{route}_commissioned"] = True
            self.variables[f"VAL_route_{route}_active"] = 1

    def matches(self, items, scope="VAL"):
        def match(e):
            key, value = e.key, e.value
            if key == "OR":
                return any(self.matches([c], scope) for c in value)
            if key == "NOT":
                return not any(self.matches([c], scope) for c in value)
            if key == "AND":
                return self.matches(value, scope)
            if key in self.triggers:
                if key.startswith("VAL_trade_route_"):
                    self.route_reads.append(self.consumer)
                result = self.matches(self.triggers[key], scope)
                return result if value == "yes" else not result
            if isinstance(value, list) and (key.isdigit() or re.fullmatch("[A-Z]{3}", key)):
                return self.matches(value, key)
            facts = {**self.facts, **{("VAL", "variable", k): v for k, v in self.variables.items()}}
            return matches_conditions([e], facts, scope)
        return all(match(e) for e in items)

    def execute(self, items):
        matched = False
        for e in items:
            key, value = e.key, e.value
            if key in ("if", "else_if", "else"):
                if key == "if":
                    matched = False
                guard = next((c.value for c in value if c.key == "limit"), [])
                if not matched and self.matches(guard):
                    matched = True
                    self.execute([c for c in value if c.key != "limit"])
            elif key in ("set_variable", "add_to_variable", "set_temp_variable",
                         "add_to_temp_variable", "subtract_from_temp_variable", "subtract_from_variable",
                         "multiply_variable", "divide_variable", "multiply_temp_variable", "divide_temp_variable"):
                name, raw = scalar(value, "var"), scalar(value, "value")
                try:
                    amount = float(raw)
                except ValueError:
                    amount = self.variables.get(raw, 0)
                if key.startswith("set_"):
                    self.variables[name] = amount
                elif key.startswith("multiply_"):
                    self.variables[name] = self.variables.get(name, 0) * amount
                elif key.startswith("divide_"):
                    self.variables[name] = self.variables.get(name, 0) / amount
                else:
                    self.variables[name] = self.variables.get(name, 0) + (-amount if key.startswith("subtract_") else amount)
            elif key == "clamp_variable":
                name = scalar(value, "var")
                self.variables[name] = max(float(scalar(value, "min")), min(float(scalar(value, "max")), self.variables[name]))
            elif key in ("add_ideas", "remove_ideas"):
                self.facts["VAL", "has_idea", value] = key == "add_ideas"
            elif key == "set_country_flag":
                self.facts["VAL", "has_country_flag", scalar(value, "flag") if isinstance(value, list) else value] = True
            elif key in ("ADISCORD_economy_initialize_country", "ADISCORD_economy_mark_dirty"):
                # The fixture starts with an initialized treasury; cache invalidation
                # does not change corridor ownership, control or war relations.
                continue
            elif key in self.effects:
                previous = self.consumer
                if key in ("VAL_pay_trade_corridors", "VAL_update_black_market_weekly"):
                    self.consumer = key
                self.execute(self.effects[key])
                self.consumer = previous
            else:
                self.fail(f"Unhandled weekly trade effect: {key}")

    def test_reconciliation_precedes_payment_and_pressure_for_every_route_combination(self):
        for mask in range(16):
            with self.subTest(open_routes=mask):
                self.setUp()
                for bit, nodes in enumerate(((43, 44, 88), (59, 60, 61), (29, 46), (33,))):
                    for state in nodes:
                        for key in ("is_owned_by", "is_controlled_by"):
                            self.facts[str(state), key, "VAL"] = bool(mask & (1 << bit))
                self.execute(self.effects["VAL_logistics_market_weekly"])
                count = mask.bit_count()
                self.assertEqual(self.variables["VAL_trade_corridors_active"], count)
                income = 20 * count + (10 if mask & 1 else 0) + (20 if count < 4 else 0)
                delta = 3 * (4 - count) if count < 4 else -2
                self.assertEqual(self.variables["ADISCORD_economy_treasury"], 100 + income)
                self.assertEqual(self.variables["ADISCORD_economy_current_month_action_income"], income)
                self.assertEqual(self.variables["VAL_black_market_pressure"], 10 + delta)
                self.assertFalse(any(self.route_reads), "Consumers must reuse this pulse's reconciled routes")
                self.execute(self.effects["VAL_logistics_market_weekly"])
                self.assertEqual(self.variables["ADISCORD_economy_treasury"], 100 + 2 * income)

    def test_locked_trade_and_uncommissioned_routes_produce_no_income_or_penalty(self):
        self.facts.clear()
        self.variables.clear()
        self.execute(self.effects["VAL_logistics_market_weekly"])
        self.assertEqual(self.variables.get("ADISCORD_economy_treasury", 0), 0)
        self.assertEqual(self.variables["VAL_black_market_pressure"], 0)

    def test_partner_war_closes_and_peace_reopens_route_without_control_change(self):
        self.facts["33", "is_owned_by", "WRK"] = True
        self.facts["33", "is_controlled_by", "WRK"] = True
        for peaceful, treasury, pressure in ((True, 140, 19), (False, 160, 31), (True, 196, 40)):
            with self.subTest(peaceful=peaceful, treasury=treasury):
                self.facts["WRK", "has_war", "no"] = peaceful
                self.execute(self.effects["VAL_logistics_market_weekly"])
                self.assertEqual(self.variables["ADISCORD_economy_treasury"], treasury)
                self.assertEqual(self.variables["VAL_black_market_pressure"], pressure)
                self.assertEqual(self.variables["VAL_route_vorkerland_active"], int(peaceful))


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
                    self.assertTrue(self.visible(region), "Opened directions must remain visible after expiry")
                    self.assertFalse(self.facts[("VAL", "has_country_flag", window)], "Expired windows must not be restarted")

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
                self.assertTrue(self.visible(region))
                self.assertFalse(self.facts[("VAL", "has_country_flag", flag)])

    def test_expired_direction_stays_visible_but_cannot_take_payment(self):
        for region in (*REGIONS, "perimeter"):
            with self.subTest(region=region):
                self.facts = {("VAL", "has_country_flag", f"VAL_refugee_{region}_seen"): True,
                              ("VAL", "ADISCORD_economy_can_spend_100", "yes"): True}
                self.assertTrue(self.visible(region))
                available = next(e.value for e in self.decisions[f"VAL_accept_{region}_refugees"] if e.key == "available")
                self.assertFalse(matches_conditions(available, self.facts, "VAL"))

    def test_opened_offer_remains_visible_after_the_war_ends(self):
        self.facts[("VAL", "has_country_flag", "VAL_refugee_stelander_seen")] = True
        self.assertTrue(self.visible("stelander"))
        self.facts[("VAL", "VAL_refugee_stelander_war", "yes")] = True
        self.assertTrue(self.visible("stelander"))

    def test_refugee_windows_require_actual_outbreaks(self):
        vorkerland = self.triggers["VAL_refugee_vorkerland_war"]
        stelander = self.triggers["VAL_refugee_stelander_war"]
        self.assertTrue(matches_conditions(
            vorkerland,
            {("VAL", "has_global_flag", "ADISCORD_vorkerland_collapse_wars_started"): True,
             ("WKR", "exists", "yes"): True,
             ("WKR", "has_war", "yes"): True},
            "VAL",
        ))
        self.assertTrue(matches_conditions(
            stelander,
            {("STP", "has_war_with", "STS"): True},
            "VAL",
        ))

    def test_prewar_split_and_nod_crisis_do_not_open_refugee_windows(self):
        facts = {("VAL", "has_global_flag", "STP_cw_started"): True,
                 ("VAL", "VAL_final_crisis_available", "yes"): True,
                 ("VAL", "variable", "VAL_final_crisis_phase"): 1}
        for region in ("stelander", "nodrul"):
            self.assertFalse(matches_conditions(self.triggers[f"VAL_refugee_{region}_war"], facts, "VAL"))

    def test_weekly_update_does_not_clear_timed_admission_windows_on_peace(self):
        weekly = self.effects["VAL_update_refugees_weekly"]
        self.assertFalse(any(e.key == "clr_country_flag" for e in weekly))

    def test_unrelated_wars_do_not_qualify(self):
        facts = {("STP", "has_war_with", "NOD"): True}
        for region in REGIONS:
            self.assertEqual(matches_conditions(self.triggers[f"VAL_refugee_{region}_war"], facts, "VAL"), region == "nodrul")

    def test_admission_cost_capacity_and_single_payment(self):
        for region in REGIONS:
            body = self.decisions[f"VAL_accept_{region}_refugees"]
            self.assertEqual(scalar(body, "days_re_enable"), "90")
            self.assertEqual(scalar(body, "custom_cost_text"), "VAL_logistics_cost_100")
            reward = next(e.value for e in body if e.key == "complete_effect")
            self.assertEqual(sum(e.key == "ADISCORD_economy_spend_100" for e in reward), 1)
            pressure = next(e.value for e in reward if e.key == "set_temp_variable" and scalar(e.value, "var") == "VAL_black_market_pressure_change")
            self.assertEqual(scalar(pressure, "value"), "3")
            self.assertFalse(any(e.key == "clr_country_flag" for e in reward))
            population = next(e.value for e in reward if e.key == "add_to_variable" and scalar(e.value, "var") == "VAL_displaced_population")
            expected_amount = {"vorkerland": "30", "stelander": "20", "nodrul": "10", "north": "10"}[region]
            self.assertEqual(scalar(population, "value"), expected_amount)
            available = next(e.value for e in body if e.key == "available")
            facts = {("VAL", "ADISCORD_economy_can_spend_100", "yes"): True, ("VAL", f"VAL_refugee_{region}_war", "yes"): True}
            self.assertTrue(matches_conditions(available, facts, "VAL"))
            facts[("VAL", "has_country_flag", "VAL_refugee_border_closed")] = True
            self.assertFalse(matches_conditions(available, facts, "VAL"))
            facts[("VAL", "has_country_flag", "VAL_refugee_border_closed")] = False
            capacity_limit = {"vorkerland": 70, "stelander": 80, "nodrul": 90, "north": 90}[region]
            facts[("VAL", "variable", "VAL_population_present")] = capacity_limit + 0.01
            self.assertFalse(matches_conditions(available, facts, "VAL"))
            facts[("VAL", "variable", "VAL_population_present")] = 0
            facts[("VAL", "has_variable", "VAL_refugee_training_escrow")] = True
            facts[("VAL", "variable", "VAL_population_present")] = capacity_limit + 0.5
            self.assertFalse(matches_conditions(available, facts, "VAL"))
            facts[("VAL", "variable", "VAL_population_present")] = capacity_limit
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
        self.assertTrue(self.visible("perimeter"))
        self.assertFalse(self.facts[("VAL", "has_country_flag", flag)], "The one-time Perimeter window must not renew")

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

    def test_story_outbreaks_open_refugee_windows_immediately(self):
        vorkerland_events = (ROOT / "events/ADISCORD_vorkerland_events.txt").read_text(encoding="utf-8-sig")
        stelander_effects = (ROOT / "common/scripted_effects/ADISCORD_STP_scripted_effects.txt").read_text(encoding="utf-8-sig")
        outbreak = vorkerland_events.index("set_global_flag = ADISCORD_vorkerland_collapse_wars_started")
        dirty = vorkerland_events.index("set_global_flag = ADISCORD_vorkerland_dirty_opened")
        self.assertIn("VAL_open_refugee_waves = yes", vorkerland_events[outbreak:outbreak + 500])
        self.assertIn("VAL_open_refugee_waves = yes", vorkerland_events[dirty:dirty + 500])
        civil = stelander_effects.index("set_global_flag = STP_cw_started")
        self.assertIn("VAL_open_refugee_waves = yes", stelander_effects[civil:civil + 500])

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
        self.assertFalse(any(e.key == "add_manpower" for e in labor))
        self.assertTrue(any(e.key == "set_variable" and scalar(e.value, "var") == "VAL_refugee_labor_escrow" for e in labor))


    def test_contract_state_does_not_reveal_peacetime_admission(self):
        self.facts[("VAL", "has_completed_focus", "VAL_The_Contract_State")] = True
        for region in (*REGIONS, "perimeter"):
            with self.subTest(region=region):
                self.assertFalse(self.visible(region))

    def test_expired_admission_rows_show_reason_without_renewal(self):
        self.facts[("VAL", "has_completed_focus", "VAL_The_Contract_State")] = True
        self.facts[("VAL", "ADISCORD_economy_can_spend_100", "yes")] = True
        for region in (*REGIONS, "perimeter"):
            with self.subTest(region=region):
                self.facts[("VAL", "has_country_flag", f"VAL_refugee_{region}_seen")] = True
                self.run_effect(self.effects["VAL_open_refugee_waves"])
                self.assertTrue(self.visible(region))
                available = next(e.value for e in self.decisions[f"VAL_accept_{region}_refugees"] if e.key == "available")
                self.assertFalse(matches_conditions(available, self.facts, "VAL"))
                self.assertNotIn(f"VAL_refugee_{region}_window", self.windows)

    def test_visible_admission_requires_a_live_war_and_localised_reason(self):
        self.facts[("VAL", "has_completed_focus", "VAL_The_Contract_State")] = True
        self.facts[("VAL", "ADISCORD_economy_can_spend_100", "yes")] = True
        for region in (*REGIONS, "perimeter"):
            with self.subTest(region=region):
                available = next(e.value for e in self.decisions[f"VAL_accept_{region}_refugees"] if e.key == "available")
                self.assertFalse(matches_conditions(available, self.facts, "VAL"))
                if region == "perimeter":
                    self.facts[("VAL", "VAL_refugee_perimeter_open", "yes")] = True
                else:
                    self.facts[("VAL", f"VAL_refugee_{region}_war", "yes")] = True
                self.assertTrue(self.visible(region))
                self.assertTrue(matches_conditions(available, self.facts, "VAL"))
        for language in ("russian", "english"):
            loc = (ROOT / f"localisation/{language}/ADISCORD_VAL_logistics_market_l_{language}.yml").read_text(encoding="utf-8-sig")
            self.assertIn(" VAL_refugee_window_open_tt:", loc)


class KefreytDecisionVisibilityTests(unittest.TestCase):
    def test_viceroy_offer_is_visible_from_foreign_broker_licences(self):
        categories = load("common/decisions/categories/ADISCORD_VAL_rework_categories.txt")
        decisions = {e.key: e.value for e in load("common/decisions/ADISCORD_VAL_decisions.txt")["VAL_foreign_sales"]}
        facts = {("VAL", "has_completed_focus", "VAL_Foreign_Broker_Licences"): True,
                 ("NAM", "exists", "yes"): True}
        category = next(e.value for e in categories["VAL_foreign_sales"] if e.key == "visible")
        visible = next(e.value for e in decisions["VAL_negotiate_nam_metals"] if e.key == "visible")
        self.assertTrue(matches_conditions(category, facts, "VAL"))
        self.assertTrue(matches_conditions(visible, facts, "VAL"))
        for flag in ("VAL_nam_concession_agreed", "VAL_nam_concession_granted"):
            with self.subTest(flag=flag):
                self.assertFalse(matches_conditions(visible, {**facts, ("VAL", "has_country_flag", flag): True}, "VAL"))
        self.assertFalse(matches_conditions(visible, {**facts, ("NAM", "exists", "yes"): False}, "VAL"))

    def test_viceroy_offer_exposes_the_required_focus_without_bypassing_it(self):
        decisions = {e.key: e.value for e in load("common/decisions/ADISCORD_VAL_decisions.txt")["VAL_foreign_sales"]}
        available = next(e.value for e in decisions["VAL_negotiate_nam_metals"] if e.key == "available")
        self.assertEqual(scalar(available, "has_completed_focus"), "VAL_Resource_War_Contracts")
        facts = {("VAL", "VAL_nam_concession_negotiable", "yes"): True}
        self.assertFalse(matches_conditions(available, facts, "VAL"))
        facts[("VAL", "has_completed_focus", "VAL_Resource_War_Contracts")] = True
        self.assertTrue(matches_conditions(available, facts, "VAL"))
        facts[("VAL", "has_country_flag", "VAL_nam_concession_offer_pending")] = True
        self.assertFalse(matches_conditions(available, facts, "VAL"))

    def test_resource_war_focus_announces_the_viceroy_treaty(self):
        tree = load("common/national_focus/ADISCORD_national_focus_VAL.txt")["focus_tree"]
        focus = next(e.value for e in tree if e.key == "focus" and scalar(e.value, "id") == "VAL_Resource_War_Contracts")
        reward = next(e.value for e in focus if e.key == "completion_reward")
        unlocks = {scalar(e.value, "decision") for e in reward if e.key == "unlock_decision_tooltip"}
        self.assertTrue({"VAL_negotiate_nam_metals", "VAL_resource_war_arms", "VAL_resource_war_personnel"} <= unlocks)

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
            elif key == "add_equipment_to_stockpile":
                self.rewards.append(("equipment", int(scalar(value, "amount"))))
            elif key in ("add_ideas", "remove_ideas"):
                self.facts[("VAL", "has_idea", value)] = key == "add_ideas"
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
        self.facts = {("VAL", "has_capitulated", "no"): True, ("VAL", "is_subject", "no"): True,
                      ("VAL", "numeric", "has_political_power"): 75}
        self.rewards = []

    def test_training_reserves_people_and_cannot_deliver_twice(self):
        self.decision_effect("VAL_train_refugee_volunteers", "complete_effect")
        self.assertEqual(self.variables["VAL_displaced_population"], 9)
        self.assertEqual(self.variables["VAL_refugee_training_escrow"], 1)
        self.assertEqual(self.rewards, [("add_political_power", -75), ("equipment", -5000)])
        for _ in range(2):
            self.decision_effect("VAL_train_refugee_volunteers", "remove_effect")
        self.decision_effect("VAL_train_refugee_volunteers", "cancel_effect")
        self.assertEqual(self.rewards, [("add_political_power", -75), ("equipment", -5000), ("add_manpower", 10000)])
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
                self.assertEqual(self.rewards, [("add_political_power", -75), ("equipment", -5000), ("add_political_power", 75), ("equipment", 5000)])
                self.assertNotIn("VAL_refugee_training_escrow", self.variables)

    def test_active_training_and_fractional_shortage_block_new_payment(self):
        body = next(e.value for e in self.decisions["VAL_train_refugee_volunteers"] if e.key == "available")
        for people, active, expected in ((0.999, False, False), (1, False, True), (20, True, False)):
            facts = {**self.facts, ("VAL", "variable", "VAL_displaced_population"): people,
                     ("VAL", "has_variable", "VAL_refugee_training_escrow"): active}
            self.assertEqual(matches_conditions(body, facts, "VAL"), expected)



    def test_labor_payment_rechecks_people_power_and_existing_contract(self):
        for people, pp, active, paid in ((0, 75, False, False), (9.999, 75, False, False),
                                          (10, 74.999, False, False), (10, 75, False, True),
                                          (20, 75, True, False)):
            with self.subTest(people=people, pp=pp, active=active):
                self.setUp()
                self.variables["VAL_displaced_population"] = people
                self.facts[("VAL", "numeric", "has_political_power")] = pp
                if active:
                    self.variables["VAL_refugee_labor_escrow"] = 10
                self.decision_effect("VAL_contract_refugee_labor", "complete_effect")
                self.assertEqual(self.variables["VAL_displaced_population"], people - (10 if paid else 0))
                self.assertEqual(self.rewards, [("add_political_power", -75)] if paid else [])
                if paid:
                    self.decision_effect("VAL_contract_refugee_labor", "complete_effect")
                    self.assertEqual(self.variables["VAL_displaced_population"], 0)
                    self.assertEqual(self.rewards, [("add_political_power", -75)])

    def test_labor_returns_every_worker_once_on_completion_or_cancellation(self):
        for result in ("remove_effect", "cancel_effect"):
            self.setUp()
            self.decision_effect("VAL_contract_refugee_labor", "complete_effect")
            self.assertEqual(self.variables["VAL_displaced_population"], 0)
            self.assertEqual(self.variables["VAL_refugee_labor_escrow"], 10)
            self.assertTrue(self.facts[("VAL", "has_idea", "VAL_refugee_contract_labor")])
            self.decision_effect("VAL_contract_refugee_labor", result)
            self.decision_effect("VAL_contract_refugee_labor", result)
            self.assertEqual(self.variables["VAL_displaced_population"], 10)
            self.assertNotIn("VAL_refugee_labor_escrow", self.variables)
            self.assertFalse(self.facts[("VAL", "has_idea", "VAL_refugee_contract_labor")])
            self.assertEqual(self.rewards, [("add_political_power", -75)])

    def test_local_training_spends_its_own_finite_reserve(self):
        self.variables["VAL_local_volunteer_pool"] = 1
        self.decision_effect("VAL_recruit_local_volunteers", "complete_effect")
        self.assertEqual(self.variables["VAL_local_volunteer_pool"], 0.5)
        self.assertEqual(self.variables["VAL_displaced_population"], 10)
        self.decision_effect("VAL_recruit_local_volunteers", "remove_effect")
        self.decision_effect("VAL_recruit_local_volunteers", "remove_effect")
        self.assertEqual(self.rewards.count(("add_manpower", 5000)), 1)
        self.assertEqual(self.variables["VAL_local_volunteer_pool"], 0.5)

    def test_housing_expansion_costs_250_for_200k_capacity(self):
        decision = self.decisions["VAL_expand_refugee_housing"]
        self.assertEqual(scalar(decision, "custom_cost_text"), "VAL_logistics_cost_250")
        complete = next(e.value for e in decision if e.key == "complete_effect")
        self.assertEqual(sum(e.key == "ADISCORD_economy_spend_250" for e in complete), 1)
        deposit = next(e.value for e in complete if e.key == "set_variable")
        self.assertEqual(scalar(deposit, "var"), "VAL_housing_deposit")
        self.assertEqual(scalar(deposit, "value"), "250")

    def test_housing_completion_and_failed_completion_cannot_duplicate_receipt(self):
        for sovereign in (True, False):
            self.setUp()
            self.variables.update(VAL_housing_deposit=500, VAL_refugee_housing=20, ADISCORD_economy_treasury=0)
            self.facts[("VAL", "is_subject", "no")] = sovereign
            self.run_effect("VAL_finish_housing")
            self.run_effect("VAL_finish_housing")
            self.run_effect("VAL_refund_housing")
            self.assertNotIn("VAL_housing_deposit", self.variables)
            self.assertEqual(self.variables["VAL_refugee_housing"], 40 if sovereign else 20)
            self.assertEqual(self.variables["ADISCORD_economy_treasury"], 0 if sovereign else 500)


class FinalSupplySettlementTests(unittest.TestCase):
    execute = CorridorProjectTests.execute
    run_effect = CorridorProjectTests.run_effect
    decision_effect = CorridorProjectTests.decision_effect

    def setUp(self):
        self.effects = load("common/scripted_effects/ADISCORD_VAL_effects.txt")
        self.effects.update(load("common/scripted_effects/ADISCORD_shared_action_effects.txt"))
        self.decisions = {e.key: e.value for e in load("common/decisions/ADISCORD_VAL_decisions.txt")["VAL_frontier"]}
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



class GreyMarketIncomeTests(unittest.TestCase):
    def fixture(self, pressure):
        from tools.tests.test_adiscord_economy_weekly_contracts import EconomyScriptFixture
        fixture = EconomyScriptFixture(
            countries={"VAL": {"VAL_black_market_pressure": pressure}},
            texts=((ROOT / "common/scripted_effects/ADISCORD_VAL_logistics_market_effects.txt").read_text(encoding="utf-8-sig"),),
            stubs=("ADISCORD_economy_initialize_country", "ADISCORD_economy_mark_dirty"),
        )
        return fixture, fixture.scopes["VAL"]

    def test_thresholds_apply_to_budget_bonus_and_corridor_cash(self):
        for pressure, rate in ((0, 0), (24.99, 0), (25, .1), (49.99, .1),
                               (50, .25), (74.99, .25), (75, .5), (100, .5)):
            with self.subTest(pressure=pressure):
                f, v = self.fixture(pressure)
                v.update(ADISCORD_economy_monthly_income=1300,
                         ADISCORD_economy_final_weekly_income_bonus=20,
                         ADISCORD_economy_treasury=100)
                f.run("VAL_black_market_reduce_monthly_income", scope="VAL")
                f.run("VAL_black_market_reduce_weekly_bonus", scope="VAL")
                f.run("VAL_corridor_income_20", scope="VAL")
                f.run("VAL_corridor_income_10", scope="VAL")
                self.assertAlmostEqual(v["ADISCORD_economy_monthly_income"], 1300*(1-rate))
                self.assertAlmostEqual(v["ADISCORD_economy_final_weekly_income_bonus"], 20*(1-rate))
                self.assertAlmostEqual(v["ADISCORD_economy_treasury"], 100+30*(1-rate))
                self.assertAlmostEqual(v["ADISCORD_economy_current_month_action_income"], 30*(1-rate))
                f.run("VAL_black_market_record_budget_loss", scope="VAL")
                self.assertAlmostEqual(v["VAL_black_market_loss_last_week"], 350*rate)
                self.assertAlmostEqual(v["VAL_black_market_loss_total"], 350*rate)
                self.assertEqual(v["VAL_black_market_route_loss_pending"], 0)

    def test_forecasts_do_not_count_as_losses_and_settlement_consumes_pending_once(self):
        f, v = self.fixture(75)
        for _ in range(3):
            v.update(ADISCORD_economy_monthly_income=1300,
                     ADISCORD_economy_final_weekly_income_bonus=20)
            f.run("VAL_black_market_reduce_monthly_income", scope="VAL")
            f.run("VAL_black_market_reduce_weekly_bonus", scope="VAL")
        self.assertEqual(v.get("VAL_black_market_loss_total", 0), 0)
        f.run("VAL_corridor_income_20", scope="VAL")
        f.run("VAL_black_market_record_budget_loss", scope="VAL")
        self.assertAlmostEqual(v["VAL_black_market_loss_last_week"], 170)
        self.assertAlmostEqual(v["VAL_black_market_loss_total"], 170)
        f.run("VAL_black_market_record_budget_loss", scope="VAL")
        self.assertAlmostEqual(v["VAL_black_market_loss_last_week"], 160)
        self.assertAlmostEqual(v["VAL_black_market_loss_total"], 330)

    def test_zero_income_and_negative_bonus_do_not_create_fictitious_losses(self):
        f, v = self.fixture(100)
        v.update(ADISCORD_economy_monthly_income=0,
                 ADISCORD_economy_final_weekly_income_bonus=-5)
        f.run("VAL_black_market_reduce_monthly_income", scope="VAL")
        f.run("VAL_black_market_reduce_weekly_bonus", scope="VAL")
        f.run("VAL_black_market_record_budget_loss", scope="VAL")
        self.assertEqual(v["ADISCORD_economy_final_weekly_income_bonus"], -5)
        self.assertEqual(v["VAL_black_market_loss_last_week"], 0)

    def test_paid_week_reconciles_cash_and_loss_without_double_debit(self):
        f, v = self.fixture(75)
        f.stubs.update(("ADISCORD_economy_update_debt_state_after_settlement",
                        "ADISCORD_economy_queue_debt_notification"))
        v.update(ADISCORD_economy_monthly_income=1300,
                 ADISCORD_economy_monthly_expenses=130,
                 ADISCORD_economy_final_weekly_income_bonus=20,
                 ADISCORD_economy_treasury=100,
                 ADISCORD_economy_treasury_cap=5000,
                 ADISCORD_economy_accounting_period_treasury_start=100)
        f.run("VAL_black_market_reduce_monthly_income", scope="VAL")
        f.run("VAL_black_market_reduce_weekly_bonus", scope="VAL")
        f.run("ADISCORD_economy_calculate_monthly_balance", scope="VAL")
        f.run("ADISCORD_economy_calculate_weekly_budget", scope="VAL")
        self.assertAlmostEqual(v["ADISCORD_economy_monthly_balance"] * 3 / 13, 130)
        f.run("VAL_corridor_income_20", scope="VAL")
        f.run("VAL_corridor_income_10", scope="VAL")
        f.run("ADISCORD_economy_apply_weekly_balance", scope="VAL")
        self.assertAlmostEqual(v["ADISCORD_economy_treasury"], 245)
        self.assertAlmostEqual(v["ADISCORD_economy_last_period_unexplained_delta"], 0)
        self.assertAlmostEqual(v["VAL_black_market_loss_last_week"], 175)
        self.assertAlmostEqual(v["VAL_black_market_loss_total"], 175)

    def test_full_and_tax_only_income_refresh_apply_loss_once(self):
        f, v = self.fixture(75)
        f.stubs.update("ADISCORD_economy_" + name for name in (
            "calculate_personal_income", "calculate_business_income", "calculate_consumer_goods_income",
            "calculate_factory_income", "calculate_resource_income", "calculate_building_income",
            "apply_law_income_modifiers", "cache_tax_dependent_income_base", "apply_tax_burden_to_income",
            "apply_institutional_income_factors", "apply_income_modifier_factors",
            "apply_development_income_multipliers", "apply_overall_income_modifier_factor"))
        for bucket, amount in (("personal", 300), ("business", 400), ("consumer_goods", 300), ("factory", 300)):
            v["ADISCORD_economy_" + bucket + "_income"] = amount
            v["ADISCORD_economy_tax_" + bucket + "_income_base"] = amount
        for name in ("tax_collection", "population_tax_income", "civilian_factory_income",
                     "trade_income", "military_industry_income"):
            v["ADISCORD_economy_final_" + name + "_factor_bp"] = 100
        v["ADISCORD_economy_income_multiplier"] = 100
        for effect in ("calculate_income", "calculate_income", "recalculate_tax_dependent_income",
                       "recalculate_tax_dependent_income"):
            f.run("ADISCORD_economy_" + effect, scope="VAL")
            self.assertEqual(v["ADISCORD_economy_monthly_income"], 650)
            self.assertEqual(v.get("VAL_black_market_loss_total", 0), 0)

    def test_native_bonus_collection_rebuilds_net_value_without_compounding(self):
        f, v = self.fixture(50)
        f.definitions.update(load("common/scripted_effects/ADISCORD_economy_modifier_effects.txt"))
        v["modifier@ADISCORD_economy_weekly_income"] = 20
        for _ in range(3):
            f.run("ADISCORD_economy_calculate_final_modifier_factors", scope="VAL")
            self.assertEqual(v["ADISCORD_economy_final_weekly_income_bonus"], 15)
            self.assertEqual(v["VAL_black_market_bonus_loss"], 5)
        self.assertEqual(v.get("VAL_black_market_loss_total", 0), 0)

    def test_route_display_matches_the_income_actually_paid(self):
        source = (ROOT / "common/scripted_localisation/ADISCORD_VAL_contract_scripted_loc.txt").read_text(encoding="utf-8-sig")
        definitions = {scalar(e.value, "name"): e.value for e in parse_clausewitz(source) if e.key == "defined_text"}
        for lang in ("russian", "english"):
            text = (ROOT / f"localisation/{lang}/ADISCORD_VAL_decisions_l_{lang}.yml").read_text(encoding="utf-8-sig")
            loc = dict(re.findall(r'^ (VAL_trade_net_\w+):0 "([^"\r\n]*)"', text, re.M))
            for pressure in (0, 25, 50, 75):
                for upgraded in (False, True):
                    f, v = self.fixture(pressure)
                    name = "VALTrade" + ("Upgraded" if upgraded else "Base") + "NetIncome"
                    for entry in definitions[name]:
                        if entry.key != "text":
                            continue
                        guard = next((c.value for c in entry.value if c.key == "trigger"), [])
                        if f.condition(guard, scope="VAL"):
                            expected = float(loc[scalar(entry.value, "localization_key")])
                            break
                    f.run("VAL_corridor_income_20", scope="VAL")
                    if upgraded:
                        f.run("VAL_corridor_income_10", scope="VAL")
                    self.assertAlmostEqual(v["ADISCORD_economy_treasury"], expected)

    def test_loading_a_save_preserves_recorded_losses(self):
        f, v = self.fixture(50)
        f.stubs.update(("VAL_refresh_trade_network", "VAL_refresh_black_market_state",
                        "VAL_refresh_refugee_state", "VAL_open_refugee_waves"))
        v.update(VAL_black_market_loss_total=123, VAL_black_market_loss_last_week=50,
                 VAL_black_market_route_loss_pending=3)
        for _ in range(2):
            f.run("VAL_initialize_logistics_market", scope="VAL")
        self.assertEqual(v["VAL_black_market_loss_total"], 123)
        self.assertEqual(v["VAL_black_market_loss_last_week"], 50)
        self.assertEqual(v["VAL_black_market_route_loss_pending"], 3)

    def test_other_country_budget_is_unaffected(self):
        f, v = self.fixture(75)
        f.scopes["OTHER"] = v
        f.stubs.update(("ADISCORD_economy_update_debt_state_after_settlement",
                        "ADISCORD_economy_queue_debt_notification"))
        v.update(ADISCORD_economy_weekly_income=100, ADISCORD_economy_weekly_balance=100,
                 ADISCORD_economy_treasury=100, ADISCORD_economy_treasury_cap=5000,
                 ADISCORD_economy_accounting_period_treasury_start=100)
        f.run("ADISCORD_economy_apply_weekly_balance", scope="OTHER")
        self.assertEqual(v["ADISCORD_economy_treasury"], 200)
        self.assertNotIn("VAL_black_market_loss_total", v)

    def test_route_loss_survives_recovery_before_budget_settlement(self):
        f, v = self.fixture(75)
        f.run("VAL_corridor_income_20", scope="VAL")
        v.update(VAL_black_market_pressure=0, ADISCORD_economy_monthly_income=1300,
                 ADISCORD_economy_final_weekly_income_bonus=20)
        f.run("VAL_black_market_reduce_monthly_income", scope="VAL")
        f.run("VAL_black_market_reduce_weekly_bonus", scope="VAL")
        f.run("VAL_black_market_record_budget_loss", scope="VAL")
        self.assertEqual(v["VAL_black_market_loss_last_week"], 10)
        self.assertEqual(v["VAL_black_market_loss_total"], 10)
        f.run("VAL_black_market_record_budget_loss", scope="VAL")
        self.assertEqual(v["VAL_black_market_loss_last_week"], 0)
        self.assertEqual(v["VAL_black_market_loss_total"], 10)


if __name__ == "__main__":
    unittest.main()


class WastelandCampaignTests(unittest.TestCase):
    def setUp(self):
        self.triggers = load("common/scripted_triggers/ADISCORD_VAL_rework_triggers.txt")
        self.effects = load("common/scripted_effects/ADISCORD_VAL_effects.txt")

    def test_perimeter_and_actual_neighbor_gate_first_invasion(self):
        facts = {
            ("VAL", "has_global_flag", "ADISCORD_vorkerland_dirty_opened"): True,
            ("VAL", "has_capitulated", "no"): True, ("VAL", "is_subject", "no"): True,
            ("VAL", "owns_state", "168"): True, ("VAL", "controls_state", "168"): True,
            ("VAL", "VAL_frontier_idle", "yes"): True,
            ("169", "is_owned_by", "ERT"): True, ("169", "is_controlled_by", "ERT"): True,
            ("ERT", "exists", "yes"): True, ("ERT", "has_capitulated", "no"): True,
            ("ERT", "is_subject", "no"): True, ("ERT", "is_in_faction", "no"): True,
        }
        trigger = self.triggers["VAL_wasteland_invasion_available"]
        self.assertTrue(matches_conditions(trigger, facts, "VAL"))
        for required in list(facts):
            self.assertFalse(matches_conditions(trigger, {**facts, required: False}, "VAL"), required)
        self.assertFalse(matches_conditions(trigger, {**facts, ("VAL", "has_war_with", "ERT"): True}, "VAL"))

    def test_administration_cannot_appear_before_war_or_take_irem(self):
        charter = self.effects["VAL_form_wasteland_administration"]
        guard = next(e.value for e in charter[0].value if e.key == "limit")
        facts = {("VAL", key, value): True for key, value in (
            ("has_global_flag", "ADISCORD_vorkerland_dirty_opened"), ("owns_state", "169"),
            ("controls_state", "169"), ("is_subject", "no"), ("has_capitulated", "no"))}
        facts[("WCA", "exists", "no")] = True
        self.assertTrue(matches_conditions(guard, facts, "VAL"))
        for key in list(facts):
            self.assertFalse(matches_conditions(guard, {**facts, key: False}, "VAL"), key)
        def transfers(items):
            result = []
            for e in items:
                if e.key == "transfer_state": result.append(int(e.value))
                if isinstance(e.value, list): result += transfers(e.value)
            return result
        self.assertEqual(transfers(charter), [169])
        settlement = self.effects["VAL_settle_wasteland_capitulation"]
        targets = set(transfers(settlement))
        self.assertNotIn(168, targets)
        self.assertNotIn(330, targets)
        from tools.builders.build_adiscord_val_operations_map import SOUTHERN_STATES
        self.assertLessEqual(targets, set(SOUTHERN_STATES))

    def test_pressure_counts_overcrowding_and_dependence_but_rewards_secure_routes(self):
        from tools.tests.test_adiscord_stp_preparation import selected_effects
        effects = load("common/scripted_effects/ADISCORD_VAL_logistics_market_effects.txt")
        facts = {("VAL", "variable", "VAL_population_present"): 30,
                 ("VAL", "variable", "VAL_refugee_housing"): 20,
                 ("VAL", "has_war", "yes"): True,
                 ("VAL", "has_country_flag", "VAL_route_occidia_commissioned"): True}
        def delta(facts, dependence, security):
            total = 0
            for _, e in selected_effects(effects["VAL_update_black_market_weekly"], facts, "VAL"):
                if e.key not in ("add_to_temp_variable", "subtract_from_temp_variable"): continue
                raw = scalar(e.value, "value")
                value = {"VAL_broker_dependence": dependence, "VAL_corridor_security": security}.get(raw)
                if value is None: value = float(raw)
                total += value if e.key == "add_to_temp_variable" else -value
            return total
        self.assertEqual(delta(facts, 3, 1), 10)
        healthy = {("VAL", "variable", "VAL_population_present"): 20,
                   ("VAL", "variable", "VAL_refugee_housing"): 20,
                   ("VAL", "variable", "VAL_trade_corridors_active"): 1,
                   ("VAL", "variable", "VAL_trade_corridors_capacity"): 1,
                   ("VAL", "VAL_trade_corridors_unlocked", "yes"): True}
        self.assertEqual(delta(healthy, 0, 3), -5)

    def test_custom_training_price_uses_exact_boundaries(self):
        decisions = {e.key: e.value for e in load("common/decisions/ADISCORD_VAL_logistics_market_decisions.txt")["VAL_population_markets"]}
        for name, pool, threshold, cost_text in (
            ("VAL_train_refugee_volunteers", "VAL_displaced_population", 1, "VAL_refugee_training_cost"),
            ("VAL_recruit_local_volunteers", "VAL_local_volunteer_pool", 0.5, "VAL_training_cost"),
        ):
            decision = decisions[name]
            self.assertEqual(scalar(decision, "cost"), "0")
            self.assertEqual(scalar(decision, "custom_cost_text"), cost_text)
            guard = next(e.value for e in decision if e.key == "custom_cost_trigger")
            for pp, rifles, people, expected in (
                (75, 5000, threshold, True),
                (74.99, 5000, threshold, False),
                (75, 4999.99, threshold, False),
                (75, 5000, threshold - 0.001, False),
            ):
                facts = {
                    ("VAL", "numeric", "political_power"): pp,
                    ("VAL", "equipment", "infantry_equipment"): rifles,
                    ("VAL", "variable", pool): people,
                }
                self.assertEqual(matches_conditions(guard, facts, "VAL"), expected)
