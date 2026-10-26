"""Execute the postwar contracts against parsed scripts, without simulating HOI4."""

from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
import re
import unittest

from tools.tests.test_adiscord_stp_preparation import block, matches_conditions, scalar
from tools.validators.validate_adiscord_division_templates import parse_clausewitz


ROOT = Path(__file__).resolve().parents[2]


def read(path):
    return (ROOT / path).read_text(encoding="utf-8-sig")


def definitions(path):
    return {e.key: e.value for e in parse_clausewitz(read(path))}


EFFECTS = definitions("common/scripted_effects/ADISCORD_vorkerland_effects.txt")
TRIGGERS = definitions("common/scripted_triggers/ADISCORD_vorkerland_triggers.txt")
DECISIONS = {
    e.key: e.value
    for e in definitions("common/decisions/ADISCORD_vorkerland_decisions.txt")[
        "WRK_worx_research_category"
    ]
}


class Scenario:
    """Only the effects used by this mechanic are supported; unknown effects fail."""

    def __init__(self):
        self.values = {}
        self.flags = {"ADISCORD_vorkerland_route_utilitarian"}
        self.focuses = set()
        self.modifiers = set()
        self.pp = 1000.0
        self.stability = 0.5
        self.xp = 0
        self.bonuses = 0
        self.subject = False
        self.capitulated = False
        self.worx = True
        self.events = []
        self.pending = {}
        self.dirty = 0
        self.war = False
        self.manpower = 5000.0
        self.support = 500.0
        self.run(EFFECTS["WRK_worx_initialize"])

    def number(self, value):
        try:
            return float(value)
        except ValueError:
            return self.values.get(value, 0)

    def expand(self, entries):
        result = []
        for entry in entries:
            if entry.key in TRIGGERS:
                self.assert_boolean(entry.value)
                predicate = replace(entry, key="AND", value=self.expand(TRIGGERS[entry.key]))
                result.append(predicate if entry.value == "yes" else
                              replace(entry, key="NOT", value=[predicate]))
            elif entry.key == "has_country_leader":
                result.append(replace(entry, key="always", value="yes" if self.worx else "no"))
            elif entry.key == "has_dynamic_modifier":
                present = scalar(entry.value, "modifier") in self.modifiers
                result.append(replace(entry, key="always", value="yes" if present else "no"))
            elif isinstance(entry.value, list):
                result.append(replace(entry, value=self.expand(entry.value)))
            else:
                result.append(entry)
        return result

    @staticmethod
    def assert_boolean(value):
        if value not in ("yes", "no"):
            raise AssertionError("Scripted triggers require boolean calls")

    def matches(self, entries):
        facts = {("WRK", "variable", key): value for key, value in self.values.items()}
        facts.update({("WRK", "has_variable", key): True for key in self.values})
        facts.update({("WRK", "has_country_flag", flag): True for flag in self.flags})
        facts.update({("WRK", "has_completed_focus", focus): True for focus in self.focuses})
        facts[("WRK", "is_subject", "no")] = not self.subject
        facts[("WRK", "has_capitulated", "no")] = not self.capitulated
        facts[("WRK", "numeric", "has_political_power")] = self.pp
        facts[("WRK", "numeric", "has_manpower")] = self.manpower
        facts[("WRK", "equipment", "support_equipment")] = self.support
        facts[("WRK", "has_war", "yes")] = self.war
        return matches_conditions(self.expand(entries), facts, "WRK")

    def run(self, entries):
        branch_taken = False
        for entry in entries:
            key, value = entry.key, entry.value
            if key == "if":
                branch_taken = self.matches(block(value, "limit"))
                if branch_taken:
                    self.run([e for e in value if e.key != "limit"])
            elif key == "else_if":
                if not branch_taken and self.matches(block(value, "limit")):
                    branch_taken = True
                    self.run([e for e in value if e.key != "limit"])
            elif key == "else":
                if not branch_taken:
                    self.run(value)
                branch_taken = True
            elif key in ("hidden_effect",):
                self.run(value)
            elif key.startswith("WRK_worx_") and key in EFFECTS:
                self.assert_boolean(value)
                self.run(EFFECTS[key])
            elif key in ("set_variable", "set_temp_variable", "add_to_variable",
                         "subtract_from_variable", "multiply_variable", "multiply_temp_variable"):
                var = scalar(value, "var")
                amount = self.number(scalar(value, "value"))
                old = self.values.get(var, 0)
                if key.startswith("set_"):
                    self.values[var] = amount
                elif key.startswith("multiply_"):
                    self.values[var] = old * amount
                elif key == "subtract_from_variable":
                    self.values[var] = old - amount
                else:
                    self.values[var] = old + amount
            elif key == "clamp_variable":
                var = scalar(value, "var")
                self.values[var] = min(self.number(scalar(value, "max")),
                                       max(self.number(scalar(value, "min")), self.values.get(var, 0)))
            elif key == "clear_variable":
                self.values.pop(value, None)
            elif key == "set_country_flag":
                self.flags.add(value)
            elif key == "add_political_power":
                self.pp += self.number(value)
            elif key == "add_stability":
                self.stability += float(value)
            elif key == "army_experience":
                self.xp += float(value)
            elif key == "add_manpower":
                self.manpower += self.number(value)
            elif key == "add_equipment_to_stockpile":
                if scalar(value, "type") != "support_equipment":
                    raise AssertionError("Only support deposits are modelled")
                self.support += self.number(scalar(value, "amount"))
            elif key == "add_tech_bonus":
                self.bonuses += 1
            elif key == "add_dynamic_modifier":
                self.modifiers.add(scalar(value, "modifier"))
            elif key == "remove_dynamic_modifier":
                self.modifiers.remove(scalar(value, "modifier"))
            elif key == "country_event":
                self.events.append(scalar(value, "id"))
            elif key == "ADISCORD_economy_mark_dirty":
                self.dirty += 1
            elif key not in ("custom_effect_tooltip", "effect_tooltip", "unlock_decision_tooltip",
                             "ADISCORD_reform_state_development"):
                raise AssertionError(f"Unsupported effect: {key}")

    def start(self, kind):
        decision = DECISIONS["WRK_worx_" + kind]
        if kind in self.pending or not all(self.matches(block(decision, gate))
                                          for gate in ("visible", "available", "custom_cost_trigger")):
            return False
        self.run(block(decision, "complete_effect"))
        self.pending[kind] = int(scalar(decision, "days_remove"))
        return True

    def day(self):
        self.run(EFFECTS["WRK_worx_daily"])
        for kind in list(self.pending):
            decision = DECISIONS["WRK_worx_" + kind]
            if self.matches(block(decision, "cancel_trigger")):
                del self.pending[kind]
                self.run(block(decision, "cancel_effect"))
            else:
                self.pending[kind] -= 1
                if self.pending[kind] == 0:
                    del self.pending[kind]
                    self.run(block(decision, "remove_effect"))


class WorxMadnessTests(unittest.TestCase):
    def test_initializer_does_not_reset_paid_work_or_progress(self):
        s = Scenario()
        self.assertTrue(s.start("basic"))
        s.day()
        snapshot = deepcopy(s.__dict__)
        s.run(EFFECTS["WRK_worx_initialize"])
        self.assertEqual(s.__dict__, snapshot)

    def test_exact_prices_and_shared_slot_at_every_tier(self):
        for kind, prices in (("basic", (75, 100, 125, 150)), ("expanded", (150, 200, 250, 300))):
            for tier, price in enumerate(prices, 1):
                with self.subTest(kind=kind, tier=tier):
                    s = Scenario()
                    s.focuses.add("WRK_worx_operating_table")
                    s.values["WRK_worx_demand"] = tier
                    s.run(EFFECTS["WRK_worx_refresh"])
                    s.pp = price - 0.01
                    self.assertFalse(s.start(kind))
                    s.pp = price
                    self.assertTrue(s.start(kind))
                    self.assertEqual(s.pp, 0)
                    s.pp = 1000
                    self.assertFalse(s.start("expanded" if kind == "basic" else "basic"))
                    self.assertEqual(s.values["WRK_worx_receipt"], price)

    def test_delivery_occurs_once_after_full_duration(self):
        s = Scenario()
        self.assertTrue(s.start("basic"))
        for _ in range(13):
            s.day()
        self.assertEqual(s.xp, 0)
        restored = deepcopy(s)
        restored.day()
        self.assertEqual(restored.xp, 5)
        self.assertEqual(restored.values["WRK_worx_madness"], 14)
        restored.run(EFFECTS["WRK_worx_finish_basic"])
        self.assertEqual(restored.xp, 5)
        self.assertNotIn("WRK_worx_receipt", restored.values)

    def test_cancellation_refunds_original_price_and_preserves_progress(self):
        for loss in ("subject", "capitulated", "worx"):
            with self.subTest(loss=loss):
                s = Scenario()
                s.start("basic")
                s.values["WRK_worx_demand"] = 4
                setattr(s, loss, loss != "worx")
                s.day()
                self.assertEqual(s.pp, 1000)
                self.assertEqual(s.xp, 0)
                self.assertEqual(s.values["WRK_worx_madness"], 20)
                self.assertNotIn("WRK_worx_receipt", s.values)
                self.assertFalse(s.modifiers)
                s.run(EFFECTS["WRK_worx_refund"])
                self.assertEqual(s.pp, 1000)
                setattr(s, loss, loss == "worx")
                s.day()
                self.assertEqual(s.values["WRK_worx_madness"], 21)
                self.assertEqual(s.values["WRK_worx_demand"], 4)

    def test_thresholds_invalidate_economy_only_on_change(self):
        s = Scenario()
        for value, band in ((24, 0), (25, 1), (49, 1), (50, 2), (74, 2), (75, 3)):
            s.values["WRK_worx_madness"] = value
            s.run(EFFECTS["WRK_worx_refresh"])
            self.assertEqual(s.values.get("WRK_worx_band", 0), band)
            self.assertAlmostEqual(s.values.get("WRK_worx_output", 0), -0.02 * band)
            before = s.dirty
            s.run(EFFECTS["WRK_worx_refresh"])
            self.assertEqual(s.dirty, before)

    def test_crisis_settles_without_reading_event_and_depends_on_institutions(self):
        for controlled, loss, madness, event in ((False, 100, 70, 22), (True, 50, 60, 21)):
            s = Scenario()
            if controlled:
                s.focuses.add("WRK_worx_dissenting_protocol")
            s.values["WRK_worx_madness"] = 99
            s.day()
            self.assertEqual(s.pp, 1000 - loss)
            self.assertEqual(s.values["WRK_worx_madness"], madness)
            self.assertEqual(s.events[-1], f"ADISCORD_vorkerland_postwar.{event}")
            s.day()
            self.assertEqual(s.values["WRK_worx_crises"], 1)

    def test_three_results_raise_demands_and_cap_at_four(self):
        s = Scenario()
        for index in range(12):
            s.pp = 1000
            self.assertTrue(s.start("basic"))
            s.run(EFFECTS["WRK_worx_finish_basic"])
            s.pending.clear()
            self.assertEqual(s.values["WRK_worx_demand"], min(4, 1 + (index + 1) // 3))

    def test_oversight_is_a_real_terminal_path(self):
        s = Scenario()
        self.assertFalse(s.start("oversight"))
        s.focuses.add("WRK_worx_time_is_up")
        self.assertTrue(s.start("oversight"))
        for _ in range(35):
            s.day()
        self.assertIn("WRK_worx_supervised", s.flags)
        self.assertFalse(s.modifiers)
        self.assertEqual(s.values["WRK_worx_madness"], 0)
        self.assertFalse(s.start("basic"))
        s.day()
        self.assertEqual(s.values["WRK_worx_madness"], 0)

    def test_civilian_route_can_finish_before_crisis_at_normal_focus_speed(self):
        tree = block(parse_clausewitz(read(
            "focus_trees/Vorkerland/technical_directorate/focuses.txt"
        )), "focus_tree")
        focuses = {scalar(e.value, "id"): e.value for e in tree if e.key == "focus"}
        route = ("WRK_tech_directorate_plan", "WRK_worx_last_provisional",
                 "WRK_worx_operating_table", "WRK_worx_right_to_error",
                 "WRK_worx_dissenting_protocol", "WRK_worx_second_signature",
                 "WRK_worx_time_is_up")
        s = Scenario()
        s.pp = 0
        elapsed = 0
        for index, focus in enumerate(route):
            if index:
                self.assertEqual(scalar(block(focuses[focus], "prerequisite"), "focus"), route[index - 1])
            for _ in range(int(scalar(focuses[focus], "cost")) * 7):
                s.day()
                elapsed += 1
            # Rewards execute before the native completed-focus marker is available.
            s.run(block(focuses[focus], "completion_reward"))
            s.focuses.add(focus)
        self.assertEqual(elapsed, 77)
        self.assertTrue(s.start("oversight"))
        for _ in range(35):
            s.day()
        self.assertNotIn("WRK_worx_crises", s.values)
        self.assertEqual(s.pp, 125)
        self.assertIn("WRK_worx_supervised", s.flags)

    def test_council_review_never_raises_demands(self):
        s = Scenario()
        s.focuses.add("WRK_worx_right_to_error")
        s.values["WRK_worx_growth"] = 0.25
        self.assertTrue(s.start("review"))
        for _ in range(21):
            s.day()
        self.assertAlmostEqual(s.values["WRK_worx_madness"], 10.25)
        self.assertEqual(s.values["WRK_worx_results"], 0)
        self.assertEqual(s.values["WRK_worx_demand"], 1)

    def test_personal_and_council_demands_have_different_thresholds(self):
        for threshold in (2, 5):
            s = Scenario()
            s.values["WRK_worx_result_threshold"] = threshold
            for _ in range(threshold - 1):
                s.run(EFFECTS["WRK_worx_record_result"])
            self.assertEqual(s.values["WRK_worx_demand"], 1)
            s.run(EFFECTS["WRK_worx_record_result"])
            self.assertEqual(s.values["WRK_worx_demand"], 2)

    def test_front_trials_require_actual_war_and_refund_all_deposits(self):
        for kind, unlock, currency, price in (
            ("field_trials", "WRK_tech_engineering_corps", "support", 100),
            ("mass_trials", "WRK_tech_fire_superiority", "manpower", 1000),
        ):
            with self.subTest(kind=kind):
                s = Scenario()
                s.focuses.add(unlock)
                self.assertFalse(s.start(kind))
                s.war = True
                setattr(s, currency, price - .01)
                self.assertFalse(s.start(kind))
                setattr(s, currency, price)
                self.assertTrue(s.start(kind))
                self.assertEqual(getattr(s, currency), 0)
                self.assertFalse(s.start("basic"))
                s.war = False
                s.day()
                self.assertEqual(getattr(s, currency), price)
                self.assertEqual(s.pp, 1000)
                self.assertNotIn("WRK_worx_field_results", s.values)
                s.war = True
                self.assertTrue(s.start(kind))
                duration = int(scalar(DECISIONS["WRK_worx_" + kind], "days_remove"))
                for _ in range(duration):
                    s.day()
                self.assertEqual(getattr(s, currency), 0)
                self.assertEqual(s.values["WRK_worx_field_results"], 1)

    def test_emergency_timeout_and_success_are_single_settlements(self):
        for answer in (False, True):
            s = Scenario()
            s.run(EFFECTS["WRK_worx_begin_emergency"])
            self.assertFalse(s.start("basic"))
            if answer:
                self.assertTrue(s.start("restore_obedience"))
            for _ in range(35):
                s.day()
            self.assertEqual(s.values["WRK_worx_constitution"], 3 if answer else 4)
            self.assertNotIn("WRK_worx_emergency_days", s.values)
            self.assertNotIn("WRK_worx_receipt", s.values)
            self.assertEqual("WRK_worx_supervised" in s.flags, not answer)
            before = deepcopy(s.__dict__)
            s.run(EFFECTS["WRK_worx_emergency_failure"])
            self.assertEqual(before, s.__dict__)

    def test_late_emergency_response_is_blocked_and_cannot_overwrite_failure(self):
        s = Scenario()
        s.run(EFFECTS["WRK_worx_begin_emergency"])
        for _ in range(25):
            s.day()
        self.assertFalse(s.start("restore_obedience"))
        for _ in range(14):
            s.day()
        self.assertEqual(s.pp, 1000)
        self.assertEqual(s.values["WRK_worx_constitution"], 4)
        s.run(EFFECTS["WRK_worx_finish_restore_obedience"])
        self.assertEqual(s.values["WRK_worx_constitution"], 4)
        self.assertNotIn("ADISCORD_vorkerland_postwar.27", s.events)

    def test_last_safe_response_has_time_for_delivery_before_timeout(self):
        for remaining, allowed in ((15, True), (14, False)):
            s = Scenario()
            s.run(EFFECTS["WRK_worx_begin_emergency"])
            for _ in range(35 - remaining):
                s.day()
            self.assertEqual(s.start("restore_obedience"), allowed)
            if allowed:
                for _ in range(14):
                    s.day()
                self.assertEqual(s.values["WRK_worx_constitution"], 3)

    def test_emergency_pauses_under_subjugation_without_losing_its_clock(self):
        s = Scenario()
        s.run(EFFECTS["WRK_worx_begin_emergency"])
        self.assertTrue(s.start("restore_obedience"))
        s.day()
        s.subject = True
        s.day()
        self.assertEqual(s.values["WRK_worx_emergency_days"], 34)
        self.assertEqual(s.pp, 1000)
        s.subject = False
        self.assertTrue(s.start("restore_obedience"))
        for _ in range(14):
            s.day()
        self.assertEqual(s.values["WRK_worx_constitution"], 3)

    def test_supervision_closes_forced_research_but_preserves_civil_programmes(self):
        s = Scenario()
        s.focuses.update(("WRK_worx_even_genius", "WRK_worx_genius_permission",
                          "WRK_worx_correct_humanity", "WRK_worx_operating_table"))
        s.flags.add("WRK_worx_supervised")
        for key in ("basic", "expanded", "accelerated", "grand_programme"):
            self.assertFalse(s.start(key))
        self.assertTrue(s.start("civil_science"))
        for _ in range(35):
            s.day()
        self.assertEqual(s.bonuses, 1)

    def test_focus_graph_choices_unlocks_localisation_and_ai_route(self):
        tree = block(parse_clausewitz(read(
            "focus_trees/Vorkerland/technical_directorate/focuses.txt"
        )), "focus_tree")
        focuses = {scalar(e.value, "id"): e.value for e in tree if e.key == "focus"}
        self.assertEqual(len(focuses), 32)
        positions = [(scalar(f, "x"), scalar(f, "y")) for f in focuses.values()]
        self.assertEqual(len(set(positions)), len(positions))

        def walk(entries):
            for entry in entries:
                yield entry
                if isinstance(entry.value, list):
                    yield from walk(entry.value)

        def ancestors(key, visiting=()):
            self.assertNotIn(key, visiting)
            for group in (e.value for e in focuses[key] if e.key == "prerequisite"):
                for parent in group:
                    self.assertIn(parent.value, focuses)
                    ancestors(parent.value, (*visiting, key))

        plan = definitions("common/ai_strategy_plans/ADISCORD_vorkerland_plans.txt")
        route = set(e.value for e in block(
            plan["ADISCORD_vorkerland_wrk_postwar_utilitarian_plan"], "ai_national_focuses"
        ))
        # The plan also includes the integration tree preceding the directorate.
        all_focus_ids = set(re.findall(r"\bid\s*=\s*(\w+)", "\n".join(
            p.read_text(encoding="utf-8-sig") for p in (ROOT / "focus_trees/Vorkerland").rglob("*.txt")
        )))
        self.assertTrue(route <= all_focus_ids)
        for key, focus in focuses.items():
            ancestors(key)
            for group in (e.value for e in focus if e.key == "mutually_exclusive"):
                for other in group:
                    self.assertIn(other.value, focuses)
                    other_exclusions = [e.value for g in focuses[other.value]
                                        if g.key == "mutually_exclusive" for e in g.value]
                    self.assertIn(key, other_exclusions)
                    self.assertFalse(key in route and other.value in route)
            for entry in walk(block(focus, "completion_reward")):
                if entry.key == "unlock_decision_tooltip" and entry.value.startswith("WRK_worx_"):
                    self.assertIn(entry.value, DECISIONS)
            for language in ("russian", "english"):
                localisation = read(f"localisation/{language}/ADISCORD_vorkerland_l_{language}.yml")
                self.assertRegex(localisation, rf'(?m)^ {key}:\d* "[^"\n]+"$')
                self.assertRegex(localisation, rf'(?m)^ {key}_desc:\d* "[^"\n]+"$')

    def test_directorate_dummy_deltas_match_applied_focus_variables(self):
        modifier = definitions("common/dynamic_modifiers/ADISCORD_vorkerland_dynamic_modifiers.txt")["WRK_worx_directorate"]
        mapping = {e.value: e.key for e in modifier if e.key not in ("icon", "enable")}
        ideas = block(definitions("common/ideas/ADISCORD_vorkerland_ideas.txt")["ideas"], "country")
        displays = {e.key: e.value for e in ideas}
        for name, values in (
            ("second_signature", {"research": .05}),
            ("consent", {"authority": 1}),
            ("human_variable", {"research": .05}),
            ("humanity", {"research": .10, "production": .10, "order": -.05}),
            ("protocol", {"research": .05, "order": .05}),
        ):
            expected = {mapping["WRK_worx_" + key]: value for key, value in values.items()}
            actual = {e.key: float(e.value) for e in block(displays["WRK_worx_delta_" + name], "modifier")}
            self.assertEqual(actual, expected)

    def test_event_registration_localisation_and_source_encoding(self):
        ids = {e["id"] for e in json.loads(read("tools/data/adiscord_event_ids.json"))["events"]}
        for num in range(20, 31):
            self.assertIn(f"ADISCORD_vorkerland_postwar.{num}", ids)
        for language in ("russian", "english"):
            path = ROOT / f"localisation/{language}/ADISCORD_vorkerland_l_{language}.yml"
            self.assertTrue(path.read_bytes().startswith(b"\xef\xbb\xbf"))
            for line in path.read_text(encoding="utf-8-sig").splitlines():
                if re.match(r" (WRK_worx_|ADISCORD_vorkerland_postwar\.2[0-3])", line):
                    self.assertRegex(line, r'^ [\w.]+:\d* "[^"\r\n]*"$')
                    self.assertNotRegex(line, "[\u2013\u2014]")


if __name__ == "__main__":
    unittest.main()
