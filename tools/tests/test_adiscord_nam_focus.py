"""Parsed NAM campaign scenarios; native loading and UI need a fresh game."""

from dataclasses import replace
from itertools import product
from pathlib import Path
import json
import re
import unittest

from tools.builders.build_adiscord_focus_trees import expected_outputs
from tools.tests.test_adiscord_stp_preparation import (
    block, scalar, walk, matches_conditions, selected_effects,
)
from tools.validators.validate_adiscord_division_templates import parse_clausewitz
from tools.validators.validate_adiscord_nam_resource_war import balanced_braces

ROOT = Path(__file__).resolve().parents[2]
BASE = "ADISCORD_nam_resource_war"


def read(path):
    return (ROOT / path).read_text(encoding="utf-8-sig")


def parsed(path):
    return parse_clausewitz(read(path))


class NamCampaignTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tree = block(parsed("focus_trees/NAM/main/focuses.txt"), "focus_tree")
        cls.focuses = {scalar(e.value, "id"): e.value for e in cls.tree if e.key == "focus"}
        cls.triggers = {e.key: e.value for e in parsed(f"common/scripted_triggers/{BASE}_triggers.txt")}
        cls.effects = {}
        for path in (f"common/scripted_effects/{BASE}_effects.txt", "common/scripted_effects/ADISCORD_shared_action_effects.txt"):
            cls.effects.update({e.key: e.value for e in parsed(path)})
        cls.decisions = {e.key: e.value for e in block(parsed(f"common/decisions/{BASE}_decisions.txt"), "NAM_national_programmes")}
        cls.events = {scalar(e.value, "id"): e.value for e in parsed(f"events/{BASE}_events.txt") if e.key == "country_event"}
        cls.ideas = {e.key: e.value for e in block(block(parsed(f"common/ideas/{BASE}_ideas.txt"), "ideas"), "country")}

    def expand(self, entries):
        """Expand only native boolean scripted-trigger calls, never macro blocks."""
        result = []
        for entry in entries:
            if entry.key in self.triggers:
                self.assertIn(entry.value, ("yes", "no"), entry.key)
                result.append(replace(entry, key="AND" if entry.value == "yes" else "NOT", value=self.expand(self.triggers[entry.key])))
            elif isinstance(entry.value, list):
                result.append(replace(entry, value=self.expand(entry.value)))
            else:
                result.append(entry)
        return result

    def matches(self, entries, facts):
        return matches_conditions(self.expand(entries), facts, "NAM")

    def apply(self, entries, facts):
        """Execute selected accounting statements, leaving engine timing unmodelled."""
        for scope, entry in selected_effects(self.expand(entries), facts, "NAM"):
            if entry.key in self.effects:
                self.apply(self.effects[entry.key], facts)
            elif entry.key == "add_political_power":
                key = (scope, "numeric", "has_political_power")
                facts[key] = facts.get(key, 0) + float(entry.value)
            elif entry.key == "add_fuel":
                key = (scope, "numeric", "has_fuel")
                facts[key] = facts.get(key, 0) + float(entry.value)
            elif entry.key == "add_to_variable":
                key = (scope, "variable", scalar(entry.value, "var"))
                facts[key] = facts.get(key, 0) + float(scalar(entry.value, "value"))
            elif entry.key in ("set_country_flag", "clr_country_flag"):
                facts[(scope, "has_country_flag", entry.value)] = entry.key == "set_country_flag"
            elif entry.key == "add_equipment_to_stockpile":
                key = (scope, "equipment", scalar(entry.value, "type"))
                facts[key] = facts.get(key, 0) + float(scalar(entry.value, "amount"))
            elif entry.key == "add_timed_idea":
                facts[(scope, "has_idea", scalar(entry.value, "idea"))] = True
            elif entry.key == "add_stability":
                facts[(scope, "reward", "stability")] = facts.get((scope, "reward", "stability"), 0) + float(entry.value)

    def facts(self, pp=1000, treasury=10000, fuel=20000):
        result = {
            ("NAM", "exists", "yes"): True,
            ("NAM", "has_capitulated", "no"): True,
            ("NAM", "has_war", "yes"): True,
            ("NAM", "has_war", "no"): True,
            ("NAM", "has_war_with", "SLF"): True,
            ("NAM", "numeric", "has_political_power"): pp,
            ("NAM", "numeric", "has_fuel"): fuel,
            ("NAM", "variable", "ADISCORD_economy_treasury"): treasury,
            ("NAM", "has_global_flag", BASE + "_started"): True,
        }
        for state in (67, 688, 700):
            for condition in ("owns_state", "controls_state"):
                result[("NAM", condition, str(state))] = True
        for focus in self.focuses:
            result[("NAM", "has_completed_focus", focus)] = True
        result[("NAM", "has_completed_focus", "NAM_recognition")] = False
        return result

    def test_tree_selection_and_generated_owner(self):
        self.assertEqual(scalar(self.tree, "id"), "NAM_focus")
        country = block(self.tree, "country")
        self.assertEqual(scalar(block(country, "modifier"), "tag"), "NAM")
        output = ROOT / "common/national_focus/ADISCORD_NAM_focus.txt"
        self.assertEqual(output.read_bytes(), expected_outputs()[output])
        owners = json.loads(read("tools/data/generated_output_owners.json"))
        self.assertIn("common/national_focus/ADISCORD_NAM_focus.txt", str(owners))

    def test_unique_layout_and_real_rewards(self):
        coordinates = set()
        self.assertEqual(len(self.focuses), 40)
        filters = set()
        for name, focus in self.focuses.items():
            coordinate = (scalar(focus, "x"), scalar(focus, "y"))
            self.assertNotIn(coordinate, coordinates, name)
            coordinates.add(coordinate)
            self.assertTrue(block(focus, "completion_reward"), name)
            self.assertIn(int(scalar(focus, "cost")), range(1, 6))
            filters.add(tuple(e.value for e in block(focus, "search_filters")))
            self.assertEqual(scalar(block(focus, "available"), "has_capitulated"), "no")
        self.assertGreaterEqual(len(filters), 4)

    def test_all_sixteen_policy_combinations_reach_a_final(self):
        pairs = (("vertical", "districts"), ("export_quays", "domestic_refining"),
                 ("field_guards", "mobile_columns"), ("civil_dividend", "armed_peace"))
        for choices in product(*pairs):
            blocked = {"NAM_" + other for pair, chosen in zip(pairs, choices) for other in pair if other != chosen}
            completed = set()
            while True:
                ready = set()
                for name, focus in self.focuses.items():
                    if name in completed or name in blocked:
                        continue
                    requirements = [entry.value for entry in focus if entry.key == "prerequisite"]
                    if all(any(child.value in completed for child in group) for group in requirements):
                        ready.add(name)
                if not ready:
                    break
                completed.update(ready)
            self.assertIn("NAM_svetlogorye", completed, choices)
            for pair, chosen in zip(pairs, choices):
                group = block(self.focuses["NAM_" + chosen], "mutually_exclusive")
                self.assertEqual({e.value for e in group}, {"NAM_" + n for n in pair if n != chosen})

    def test_normal_preparation_fits_external_clock(self):
        path = ("inventory", "open_ledgers", "districts", "public_payroll", "district_guarantees")
        days = sum(int(scalar(self.focuses["NAM_" + key], "cost")) * 7 for key in path)
        self.assertEqual(days, 77)
        self.assertLess(days + 60, 850)
        self.assertNotIn("prerequisite", [e.key for e in self.focuses["NAM_alarm"]])
        self.assertNotIn("prerequisite", [e.key for e in self.focuses["NAM_recognition"]])
        self.assertEqual(int(scalar(self.focuses["NAM_alarm"], "cost")), 1)

    def test_late_political_routes_still_have_a_usable_result(self):
        facts = self.facts()
        facts[("NAM", "has_global_flag", BASE + "_resolved")] = True
        reward = block(self.focuses["NAM_emergency_writ"], "completion_reward")
        self.assertIn("NAM_supply_order", [e.value for e in walk(reward) if e.key == "unlock_decision_tooltip"])
        self.assertTrue(self.matches(block(self.decisions["NAM_supply_order"], "visible"), facts))
        self.assertTrue(self.matches(block(self.decisions["NAM_supply_order"], "available"), facts))
        reward = block(self.focuses["NAM_district_guarantees"], "completion_reward")
        self.apply(reward, facts)
        self.assertEqual(facts[("NAM", "reward", "stability")], 0.03)

    def test_quartermaster_delivers_when_procurement_is_already_unlocked(self):
        for emergency_first in (False, True):
            facts = self.facts()
            facts[("NAM", "has_completed_focus", "NAM_emergency_writ")] = emergency_first
            self.apply(block(self.focuses["NAM_quartermaster"], "completion_reward"), facts)
            self.assertEqual(facts[("NAM", "equipment", "infantry_equipment")], 1500)
            self.assertEqual(facts[("NAM", "equipment", "support_equipment")], 60)

    def test_fractional_affordability_and_actual_debits(self):
        expected = {
            "NAM_export_fuel": (25, 0, 5000), "NAM_workshop_batch": (35, 0, 3000),
            "NAM_supply_order": (25, 500, 0), "NAM_emergency_arsenal": (35, 500, 0),
            "NAM_counterinsurgency": (75, 500, 0), "NAM_relief_batch": (35, 0, 3000),
            "NAM_veteran_housing": (35, 250, 0), "NAM_postwar_rearmament": (35, 500, 0),
            "NAM_sign_compact": (75, 500, 0),
        }
        for name, (pp, treasury, fuel) in expected.items():
            decision = self.decisions[name]
            self.assertEqual(scalar(decision, "cost"), "0")
            for currency, amount, field in (
                ("pp", pp, ("NAM", "numeric", "has_political_power")),
                ("treasury", treasury, ("NAM", "variable", "ADISCORD_economy_treasury")),
                ("fuel", fuel, ("NAM", "numeric", "has_fuel")),
            ):
                if not amount:
                    continue
                facts = self.facts(pp=pp, treasury=treasury, fuel=fuel)
                if name == "NAM_sign_compact":
                    facts[("NAM", "has_global_flag", BASE + "_started")] = False
                self.assertTrue(self.matches(block(decision, "custom_cost_trigger"), facts), name)
                facts[field] = amount - 0.01
                self.assertFalse(self.matches(block(decision, "custom_cost_trigger"), facts), (name, currency))
                before = dict(facts)
                self.apply(block(decision, "complete_effect"), facts)
                self.assertEqual(facts, before, (name, currency, "stale click must not pay"))
            facts = self.facts(pp=pp, treasury=treasury, fuel=fuel)
            if name == "NAM_sign_compact":
                facts[("NAM", "has_global_flag", BASE + "_started")] = False
            self.apply(block(decision, "complete_effect"), facts)
            self.assertEqual(facts[("NAM", "numeric", "has_political_power")], 0, name)
            self.assertEqual(facts[("NAM", "numeric", "has_fuel")], 0, name)
            expected_treasury = 250 if name == "NAM_export_fuel" else 0
            self.assertEqual(facts[("NAM", "variable", "ADISCORD_economy_treasury")], expected_treasury, name)
            self.assertEqual(facts.get(("NAM", "variable", "ADISCORD_economy_current_month_action_costs"), 0), treasury, name)

    def test_compact_age_loss_repayment_and_delayed_rebellion(self):
        facts = self.facts(pp=150, treasury=1000)
        facts[("NAM", "has_global_flag", BASE + "_started")] = False
        effect = block(self.decisions["NAM_sign_compact"], "complete_effect")
        self.apply(effect, facts)
        balance = facts[("NAM", "variable", "ADISCORD_economy_treasury")]
        self.apply(effect, facts)
        self.assertEqual(facts[("NAM", "variable", "ADISCORD_economy_treasury")], balance)
        facts[("NAM", "flag_days", "NAM_district_compact")] = 59
        self.assertFalse(self.matches(self.triggers["NAM_compact_effective"], facts))
        facts[("NAM", "flag_days", "NAM_district_compact")] = 60
        self.assertTrue(self.matches(self.triggers["NAM_compact_effective"], facts))
        facts[("NAM", "has_country_flag", "NAM_compact_ratified")] = True
        facts[("NAM", "controls_state", "688")] = False
        self.apply(self.effects["NAM_invalidate_lost_compact"], facts)
        self.assertTrue(facts[("NAM", "has_country_flag", "NAM_compact_ratified")])
        self.assertFalse(facts[("NAM", "has_country_flag", "NAM_district_compact")])
        facts[("NAM", "controls_state", "688")] = True
        self.assertTrue(self.matches(self.triggers["NAM_can_sign_compact"], facts))
        rebellion = block(self.effects[BASE + "_start_mainland_rebellion"], "if")
        self.assertNotIn("NAM_compact_effective", [e.key for e in walk(rebellion)])
        self.assertIn("NAM_compact_ratified", [e.value for e in walk(rebellion) if e.key == "has_country_flag"])

    def test_compact_report_does_not_promote_a_late_signature_during_war(self):
        definitions = parsed("common/scripted_localisation/ADISCORD_nam_resource_war_scripted_loc.txt")
        status = next(e.value for e in definitions if scalar(e.value, "name") == "NAMGetCompactStatus")

        def report(facts):
            for entry in status:
                if entry.key != "text":
                    continue
                triggers = [e.value for e in entry.value if e.key == "trigger"]
                if not triggers or self.matches(triggers[0], facts):
                    return scalar(entry.value, "localization_key")
            self.fail("Missing compact status fallback")

        facts = self.facts()
        facts[("NAM", "has_country_flag", "NAM_district_compact")] = True
        facts[("NAM", "flag_days", "NAM_district_compact")] = 90
        self.assertEqual(report(facts), "NAM_compact_wartime_unavailable")
        facts[("NAM", "has_country_flag", "NAM_compact_ratified")] = True
        self.assertEqual(report(facts), "NAM_compact_ratified_status")
        facts[("NAM", "controls_state", "688")] = False
        self.apply(self.effects["NAM_invalidate_lost_compact"], facts)
        self.assertEqual(report(facts), "NAM_compact_interrupted_status")
        facts[("NAM", "has_global_flag", BASE + "_resolved")] = True
        self.assertEqual(report(facts), "NAM_compact_war_closed")

    def test_intro_uses_the_actual_collapse_phase(self):
        descriptions = [e.value for e in self.events[BASE + ".10"] if e.key == "desc"]
        for collapsed in (False, True):
            facts = self.facts()
            facts[("NAM", "has_global_flag", "ADISCORD_vorkerland_collapse_wars_started")] = collapsed
            shown = [scalar(d, "text") for d in descriptions if self.matches(block(d, "trigger"), facts)]
            self.assertEqual(shown, [BASE + (".10.d" if collapsed else ".10.before")])

    def test_mission_never_succeeds_automatically_and_all_treaties_clean_up(self):
        mission = self.decisions["NAM_defend_fields"]
        self.assertFalse(self.matches(block(mission, "available"), self.facts()))
        self.assertEqual(scalar(mission, "days_mission_timeout"), "420")
        self.assertFalse(block(mission, "timeout_effect"))
        for outcome in ("resolve_nam_victory", "resolve_coalition_victory", "resolve_peaceful_withdrawal"):
            self.assertIn(BASE + "_clear_temporary_support", [e.key for e in walk(self.effects[BASE + "_" + outcome])])
        self.assertIn("NAM_close_war_programmes", [e.key for e in walk(self.effects[BASE + "_clear_temporary_support"])])
        cleanup = self.effects["NAM_close_war_programmes"]
        self.assertIn("NAM_defend_fields", [e.value for e in cleanup if e.key == "remove_mission"])
        self.assertEqual({e.value for e in cleanup if e.key == "remove_ideas"}, {"NAM_wartime_entrenchment", "NAM_counterstroke_staff", "NAM_rebel_depot_maps"})

    def test_open_payroll_event_cannot_spend_after_money_or_route_changes(self):
        options = [e.value for e in self.events[BASE + ".10"] if e.key == "option"]
        facts = self.facts(treasury=249.99)
        self.apply(options[0], facts)
        self.assertEqual(facts[("NAM", "variable", "ADISCORD_economy_treasury")], 249.99)
        facts[("NAM", "has_completed_focus", "NAM_recognition")] = True
        facts[("NAM", "variable", "ADISCORD_economy_treasury")] = 1000
        self.apply(options[0], facts)
        self.apply(options[1], facts)
        self.assertEqual(facts[("NAM", "variable", "ADISCORD_economy_treasury")], 1000)
        self.assertNotIn(("NAM", "has_idea", "NAM_wage_arrears"), facts)
        self.assertTrue(self.matches(block(options[2], "trigger"), facts))

    def test_bilingual_costs_story_limits_and_encoding(self):
        for language in ("russian", "english"):
            path = ROOT / f"localisation/{language}/{BASE}_l_{language}.yml"
            self.assertTrue(path.read_bytes().startswith(b"\xef\xbb\xbf"))
            text = path.read_text(encoding="utf-8-sig")
            values = dict(re.findall(r'^\s*([^ #:\s]+):\s*"(.*)"\s*$', text, re.M))
            for name in self.focuses:
                self.assertIn(name, values)
                self.assertIn(name + "_desc", values)
            for name, decision in self.decisions.items():
                self.assertIn(name, values)
                self.assertIn(name + "_desc", values)
                for cost in (e.value for e in decision if e.key == "custom_cost_text"):
                    for suffix in ("", "_blocked", "_tooltip"):
                        self.assertIn(cost + suffix, values)
            for number in range(10, 14):
                descriptions = [e.value for e in self.events[f"{BASE}.{number}"] if e.key == "desc"]
                keys = [scalar(d, "text") if isinstance(d, list) else d for d in descriptions]
                for key in keys:
                    prose = values[key].replace("\\n", "\n")
                    self.assertLessEqual(len(prose), 3000)
                    self.assertLessEqual(len(prose.encode("utf-8")), 5500)
                    self.assertNotIn("§Y", prose)
        for path in ("focus_trees/NAM/main/focuses.txt", f"common/decisions/{BASE}_decisions.txt", f"common/ideas/{BASE}_ideas.txt", f"events/{BASE}_events.txt"):
            self.assertFalse((ROOT / path).read_bytes().startswith(b"\xef\xbb\xbf"))
            self.assertTrue(balanced_braces(read(path)), path)

    def test_institution_changes_invalidate_economy_without_polling(self):
        for name, idea in self.ideas.items():
            if not name.startswith("NAM_"):
                continue
            for hook in ("on_add", "on_remove"):
                self.assertIn("ADISCORD_economy_mark_dirty", [e.key for e in block(idea, hook)], name)
        hooks = read("common/on_actions/03_ADISCORD_nam_resource_war_on_actions.txt")
        self.assertNotIn("on_daily", hooks)
        self.assertNotIn("every_country", hooks)


if __name__ == "__main__":
    unittest.main()
