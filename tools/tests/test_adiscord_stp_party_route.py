"""Party route contracts: branch reachability, displayed deltas and delayed settlement.

These tests inspect authored scripts, not the Clausewitz runtime.
"""
from pathlib import Path
import re
import unittest

from tools.validators.validate_adiscord_division_templates import parse_clausewitz
from tools.tests.test_adiscord_stp_preparation import matches_conditions, selected_effects

ROOT = Path(__file__).resolve().parents[2]
FOCUS = "common/national_focus/ADISCORD_national_focus_STP.txt"
DECISIONS = "common/decisions/ADISCORD_STP_decisions.txt"
LOC = "localisation/russian/ADISCORD_STP_l_russian.yml"
SCRIPTED_LOC = "common/scripted_localisation/ADISCORD_STP_scripted_loc.txt"
EFFECTS = "common/scripted_effects/ADISCORD_STP_scripted_effects.txt"
DYNAMIC = "common/dynamic_modifiers/ADISCORD_dynamic_modifiers_STP.txt"
IDEAS = "common/ideas/ADISCORD_STP_civil_war_ideas.txt"
PLANS = "common/ai_strategy_plans/ADISCORD_STP_plans.txt"


def read(path):
    return (ROOT / path).read_text(encoding="utf-8-sig")


def children(items, key):
    return [e.value for e in items if e.key == key]


def one(items, key):
    values = children(items, key)
    if len(values) != 1:
        raise AssertionError(f"expected one {key}, found {len(values)}")
    return values[0]


def walk(items):
    for item in items:
        yield item
        if isinstance(item.value, list):
            yield from walk(item.value)


def signature(items):
    return [(e.key, signature(e.value) if isinstance(e.value, list) else e.value) for e in items]


class PartyRouteContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.trees = parse_clausewitz(read(FOCUS))
        cls.focus = {one(f, "id"): f for t in children(cls.trees, "focus_tree") for f in children(t, "focus")}
        cls.decisions = {d.key: d.value for c in parse_clausewitz(read(DECISIONS)) for d in c.value if isinstance(d.value, list)}
        cls.loc = dict(re.findall(r'^\s*([^#\s:]+):(?:\d+)?\s*"(.*)"\s*$', read(LOC), re.M))
        cls.scripted_loc = {one(v.value, "name"): v.value for v in parse_clausewitz(read(SCRIPTED_LOC))}
        cls.effects = {e.key: e.value for e in parse_clausewitz(read(EFFECTS))}
        cls.dynamic = {e.key: e.value for e in parse_clausewitz(read(DYNAMIC))}
        cls.ideas = {e.key: e.value for c in children(parse_clausewitz(read(IDEAS)), "ideas") for group in children(c, "country") for e in group}

    def test_entire_election_briefing_switches_side(self):
        self.assertEqual(self.loc["STP_elections_in_the_party_desc"], "[STPGetElectionBriefing]")
        switch = self.scripted_loc["STPGetElectionBriefing"]
        texts = children(switch, "text")
        self.assertEqual(one(texts[0], "localization_key"), "STP_PARTY_ELECTION_BRIEFING")
        self.assertEqual(one(texts[-1], "localization_key"), "STP_RESISTANCE_ELECTION_BRIEFING")
        party = self.loc["STP_PARTY_ELECTION_BRIEFING"]
        self.assertNotIn("ложный след", party.lower())
        self.assertNotIn("пороги подозрения", party.lower())
        self.assertIn("70", party)
        self.assertIn("25", party)
        self.assertIn("ложный след", self.loc["STP_RESISTANCE_ELECTION_BRIEFING"])

    def test_search_outcome_colors_follow_the_observers_side(self):
        texts = children(self.scripted_loc["STPGetLastPartyResponse"], "text")
        self.assertEqual(one(texts[0], "localization_key"), "STP_PARTY_LAST_RESPONSE")
        self.assertTrue(self.loc["STP_PARTY_OUTCOME_10"].startswith("§G"))
        self.assertTrue(self.loc["STP_PARTY_OUTCOME_11"].startswith("§R"))
        self.assertTrue(self.loc["STP_PARTY_RESPONSE_COURIER_SEIZED"].startswith("§R"))

    def test_map_instructions_switch_without_hiding_army_forecast(self):
        self.assertIn("[STPGetPreparationInstructions]", self.loc["STP_battle_for_stelander_desc"])
        self.assertIn("STP_cw_report_party_brigades", self.loc["STP_battle_for_stelander_desc"])
        self.assertIn("STP_PARTY_MAP_INSTRUCTIONS", str(signature(self.scripted_loc["STPGetPreparationInstructions"])))
        self.assertEqual(one(children(self.scripted_loc["STPGetInspectionStatus"], "text")[0], "localization_key"), "STP_REGION_PARTY_INSPECTION_STATUS")

    def reachable(self, chosen):
        done = {"STP_Govern_In_His_Name", "STP_cw_restore_civil_authority"}
        changed = True
        while changed:
            changed = False
            for fid, f in self.focus.items():
                if fid in done:
                    continue
                excludes = [e.value for group in children(f, "mutually_exclusive") for e in group if e.key == "focus"]
                if any(ex in chosen or ex in done for ex in excludes):
                    continue
                prereqs = children(f, "prerequisite")
                if not prereqs:
                    continue
                if all(any(e.value in done for e in p if e.key == "focus") for p in prereqs):
                    done.add(fid)
                    changed = True
        return done

    def test_fiscal_specialization_does_not_remove_basic_state_or_defence(self):
        for chosen in ("STP_GUARANTEE_MINISTERS", "STP_defense_budget"):
            with self.subTest(chosen=chosen):
                done = self.reachable({chosen})
                self.assertIn(chosen, done)
                for fid in ("STP_DISTRICT_GOVERNMENT", "STP_cw_capital_reserve", "STP_cw_protect_congress", "STP_cw_press_office"):
                    self.assertIn(fid, done)

    def test_both_district_methods_reach_presidium_and_mandate(self):
        for chosen in ("STP_party_district_compact", "STP_ROTATE_DISTRICT_COMMAND"):
            with self.subTest(chosen=chosen):
                self.assertIn(chosen, self.focus)
                done = self.reachable({chosen})
                self.assertIn("STP_EMERGENCY_PRESIDIUM", done)
                self.assertIn("STP_cw_party_mandate", done)
        self.assertNotIn("STP_cw_secure_party_district", str(signature(one(self.focus["STP_party_district_compact"], "completion_reward"))))

    def test_first_intercept_includes_every_prerequisite_day(self):
        root = "STP_Govern_In_His_Name"
        def days(fid):
            if fid == root:
                return 0  # side selection completes this focus by event
            f = self.focus[fid]
            blocks = children(f, "prerequisite")
            return int(float(one(f, "cost")) * 7) + sum(min(days(e.value) for e in p if e.key == "focus") for p in blocks)
        response = days("STP_cw_security_collegium") + int(one(self.decisions["STP_cw_interrupt_opposition"], "days_remove"))
        # First mission: 28 + 32 days, reduced by seven at loyalty below 25.
        self.assertLess(response, 53)
        self.assertIn("value = 70", read(EFFECTS))

    def test_late_election_callbacks_cannot_move_a_finished_election(self):
        for name in ("STP_cw_seal_protocol", "STP_cw_publish_directive"):
            payload = one(self.decisions[name], "remove_effect")
            actual = list(selected_effects(payload, {}))
            self.assertFalse(any(e.key in ("add_power_balance_value", "add_stability") for _, e in actual), name)
            self.assertTrue(any(e.key == "STP_political_action_slot_release" for _, e in actual), name)
            facts = {("STP", "STP_cw_preparation_open", "yes"): True,
                     ("STP", "has_country_flag", "STP_battle_for_stelander_active"): True,
                     ("STP", "has_active_mission", "STP_cw_election_window"): True}
            self.assertTrue(any(e.key == "add_power_balance_value" for _, e in selected_effects(payload, facts)), name)

    def test_both_postwar_settlements_have_substantial_successor_branches(self):
        paths = {
            "STP_pw_party_open_settlement": ("STP_party_district_charters", "STP_party_local_cadres"),
            "STP_pw_party_firm_settlement": ("STP_party_personnel_commissions", "STP_party_chain_of_command"),
        }
        for choice, branch in paths.items():
            done = self.reachable({choice})
            for fid in branch:
                self.assertIn(fid, done)
            self.assertIn("STP_pw_party_civil_charter", done)
            self.assertIn("STP_pw_party_settled_state", done)
        charter = children(self.focus["STP_pw_party_civil_charter"], "prerequisite")
        self.assertEqual(len(charter), 1)
        self.assertEqual(set(e.value for e in charter[0]), {v[-1] for v in paths.values()})

    def test_both_economic_models_reach_industrial_settlement(self):
        for chosen in ("STP_pw_party_civil_workshops", "STP_pw_party_accountable_arsenals"):
            done = self.reachable({chosen})
            self.assertIn("STP_party_revenue_service", done)
            self.assertIn("STP_pw_party_industrial_settlement", done)

    def test_foreign_axis_has_no_domestic_prerequisite(self):
        forbidden = {"STP_pw_party_open_settlement", "STP_pw_party_firm_settlement", "STP_party_local_cadres", "STP_party_chain_of_command"}
        for fid in ("STP_pw_party_northern_protocol", "STP_pw_party_protectorate", "STP_pw_party_sovereignty"):
            f = self.focus[fid]
            self.assertFalse(any(e.value in forbidden for p in children(f, "prerequisite") for e in p))
        self.assertEqual(one(self.focus["STP_pw_party_protectorate"], "cancel_if_invalid"), "yes")

    def test_party_income_and_credit_deltas_have_real_consumers(self):
        d = self.dynamic["STP_pw_party_dynamic"]
        for modifier in ("ADISCORD_economy_overall_income_factor", "ADISCORD_economy_creditworthiness_factor", "ADISCORD_economy_treasury_capacity_factor"):
            self.assertEqual(one(d, modifier), "STP_pw_" + modifier)
        self.assertIn("ADISCORD_economy_mark_dirty", str(signature(self.effects["STP_pw_refresh_modifier"])))

    def test_new_focus_dummies_exactly_match_live_aggregate_deltas(self):
        found = 0
        for fid, f in self.focus.items():
            if not fid.startswith("STP_party_"):
                continue
            found += 1
            reward = one(f, "completion_reward")
            modifiers = {}
            for e in walk(reward):
                if e.key == "add_to_variable":
                    var = one(e.value, "var")
                    if var.startswith(("STP_pw_", "STP_cw_party_", "STP_cw_army_")):
                        modifiers[var] = float(one(e.value, "value"))
            previews = [e.value for e in walk(reward) if e.key == "add_idea" and isinstance(e.value, str) and e.value.endswith("_delta")]
            displayed = {}
            for key in previews:
                idea = self.ideas[key]
                self.assertEqual(signature(one(idea, "allowed")), [("always", "no")])
                dynamic = self.dynamic[one(idea, "name")]
                for e in one(idea, "modifier"):
                    displayed[one(dynamic, e.key)] = float(e.value)
            self.assertEqual(displayed, modifiers, fid)
        self.assertGreaterEqual(found, 18)

    def test_assault_focus_unlocks_a_paid_order_instead_of_silent_spawn_attempt(self):
        reward = one(self.focus["STP_cw_assault_columns"], "completion_reward")
        self.assertNotIn("STP_cw_mobilize_assault_division", str(signature(reward)))
        self.assertIn("STP_party_form_assault_column", children(reward, "unlock_decision_tooltip"))
        d = self.decisions["STP_party_form_assault_column"]
        self.assertEqual(one(d, "cost"), "0")
        self.assertEqual(one(d, "days_re_enable"), "21")
        self.assertIn("STP_cw_can_pay_assault_division", str(signature(one(d, "available"))))
        self.assertIn("STP_cw_mobilize_assault_division", str(signature(one(d, "complete_effect"))))
        for suffix in ("", "_blocked", "_tooltip"):
            self.assertIn("STP_party_assault_price" + suffix, self.loc)

    def test_party_plans_abort_at_phase_boundaries(self):
        plans = {e.key:e.value for e in parse_clausewitz(read(PLANS))}
        for name in ("STP_party_preparation_plan", "STP_party_civil_war_plan", "STP_party_reconstruction_plan"):
            self.assertIn(name, plans)
            self.assertTrue(children(plans[name], "enable"))
            self.assertTrue(children(plans[name], "abort"))
            self.assertTrue(children(plans[name], "ai_national_focuses"))

    def test_new_focuses_and_tooltips_are_localized_and_phase_scoped(self):
        for fid, f in self.focus.items():
            if fid.startswith("STP_party_"):
                for suffix in ("", "_desc"):
                    self.assertIn(fid + suffix, self.loc)
                self.assertEqual(one(f, "cancel_if_invalid"), "yes")
                self.assertTrue(children(f, "available"))
                for e in walk(f):
                    if e.key in ("custom_effect_tooltip", "tooltip"):
                        self.assertIn(e.value, self.loc)

    def test_party_order_template_is_fixed_before_any_wartime_edit(self):
        locks = self.effects["STP_cw_apply_wartime_template_locks"]
        for tag in ("STP", "STS", "SRP"):
            facts = {(tag, "tag", tag): True}
            chosen = [e for _, e in selected_effects(locks, facts, tag) if e.key == "set_division_template_lock" and one(e.value, "division_template") == "Stelander Assault Division"]
            self.assertEqual(len(chosen), 1)
            self.assertEqual(one(chosen[0].value, "is_locked"), "yes" if tag == "STP" else "no")
        finish = self.effects["STP_cw_finish_mobilization"]
        self.assertIn(("set_division_template_lock", [("division_template", "Stelander Assault Division"), ("is_locked", "no")]), [x for _, e in selected_effects(finish, {("STP", "has_country_flag", "STP_cw_templates_loaded"): True}) for x in signature([e])])

    def test_assault_price_checks_every_exact_fractional_boundary(self):
        triggers = {e.key: e.value for e in parse_clausewitz(read("common/scripted_triggers/ADISCORD_STP_scripted_triggers.txt"))}
        prices = {"manpower":7900, "infantry_equipment":610, "ADISCORD_squad_weapons_equipment":48,
                  "support_equipment":30, "artillery_equipment":60, "anti_air_equipment":20}
        for currency, amount in prices.items():
            for delta in (-0.01, 0, 0.01):
                facts = {("STP", "numeric", "has_manpower"):prices["manpower"]}
                facts.update({("STP", "equipment", key): value for key, value in prices.items() if key != "manpower"})
                key = ("STP", "numeric", "has_manpower") if currency == "manpower" else ("STP", "equipment", currency)
                facts[key] = amount + delta
                with self.subTest(currency=currency, delta=delta):
                    self.assertEqual(matches_conditions(triggers["STP_cw_can_pay_assault_division"], facts), delta >= 0)

    def test_no_internal_party_balance_added(self):
        text = read("common/bop/STP.txt")
        self.assertNotIn("STP_party_cells", text)
        self.assertNotIn("STP_party_factions", text)
        for fid, f in self.focus.items():
            if fid.startswith("STP_party_"):
                self.assertNotIn("set_power_balance", str(signature(f)))

    def test_encoding_and_one_line_localisation(self):
        self.assertTrue((ROOT / LOC).read_bytes().startswith(b"\xef\xbb\xbf"))
        for path in (FOCUS, DECISIONS, EFFECTS, SCRIPTED_LOC, DYNAMIC, IDEAS):
            self.assertFalse((ROOT / path).read_bytes().startswith(b"\xef\xbb\xbf"), path)
        for line in read(LOC).splitlines():
            if not line.strip() or line.lstrip().startswith(("#", "l_russian:")):
                continue
            self.assertRegex(line, r'^\s*[^\s:]+:(?:\d+)?\s*".*"\s*(?:#.*)?$')


if __name__ == "__main__":
    unittest.main()
