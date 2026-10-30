"""Execute the postwar contracts against parsed scripts, without simulating HOI4."""

from copy import deepcopy
from dataclasses import replace
from functools import lru_cache
import json
from pathlib import Path
import re
import unittest

from tools.tests.test_adiscord_stp_preparation import block, matches_conditions, scalar
from tools.validators.validate_adiscord_division_templates import parse_clausewitz
from tools.validators.validate_tc import LOCALISATION_ENTRY


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
        self.stockpiles = {}
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
                equipment = scalar(value, "type")
                amount = self.number(scalar(value, "amount"))
                if equipment == "support_equipment":
                    self.support += amount
                else:
                    self.stockpiles[equipment] = self.stockpiles.get(equipment, 0) + amount
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
    def test_story_thresholds_follow_madness_once_and_pause_under_oversight(self):
        s = Scenario()
        for level, event in ((25, 32), (50, 33), (75, 34)):
            s.values["WRK_worx_madness"] = level
            s.run(EFFECTS["WRK_worx_story_progress"])
            self.assertEqual(s.events.count(f"ADISCORD_vorkerland_postwar.{event}"), 1)
            s.run(EFFECTS["WRK_worx_story_progress"])
            self.assertEqual(s.events.count(f"ADISCORD_vorkerland_postwar.{event}"), 1)
        self.assertEqual(s.values["WRK_worx_story_stage"], 3)
        s = Scenario()
        s.flags.add("WRK_worx_supervised")
        s.values["WRK_worx_madness"] = 90
        s.run(EFFECTS["WRK_worx_story_progress"])
        self.assertEqual(s.values["WRK_worx_story_stage"], 0)
        s = Scenario()
        s.values["WRK_worx_story_stage"] = 2
        s.values["WRK_worx_madness"] = 99
        s.day()
        self.assertEqual(s.values["WRK_worx_story_stage"], 3)
        self.assertIn("ADISCORD_vorkerland_postwar.34", s.events)
        self.assertEqual(s.values["WRK_worx_madness"], 70)

    def test_experiment_story_counts_deliveries_not_paid_or_cancelled_work(self):
        s = Scenario()
        self.assertTrue(s.start("basic"))
        self.assertEqual(s.values["WRK_worx_total_results"], 0)
        s.subject = True
        s.day()
        self.assertEqual(s.values["WRK_worx_total_results"], 0)
        s.subject = False
        for result in range(1, 7):
            self.assertTrue(s.start("basic"))
            for _ in range(14):
                s.day()
            self.assertEqual(s.values["WRK_worx_total_results"], result)
        for event in (35, 36, 37):
            self.assertEqual(s.events.count(f"ADISCORD_vorkerland_postwar.{event}"), 1)

    def test_research_choice_keeps_several_distinct_following_focuses(self):
        tree = block(parse_clausewitz(read(
            "focus_trees/Vorkerland/technical_directorate/focuses.txt"
        )), "focus_tree")
        focuses = {scalar(e.value, "id"): e.value for e in tree if e.key == "focus"}
        for child, parent in (
            ("glass_walls", "control_group"),
            ("returned_reports", "glass_walls"),
            ("honest_failure", "glass_walls"),
            ("black_boxes", "names_obstruct"),
            ("night_shift", "black_boxes"),
            ("new_material", "black_boxes"),
            ("ambulance_columns", "soldier_returns"),
            ("calibrated_fire", "return_unplanned"),
            ("school_of_answers", "compulsory_welfare"),
            ("normal_range", "complaints_deviations"),
        ):
            groups = [[e.value for e in g.value] for g in focuses["WRK_worx_" + child]
                      if g.key == "prerequisite"]
            self.assertEqual(groups, [["WRK_worx_" + parent]], child)

    def test_story_pages_fit_and_choices_cannot_restore_personal_rule(self):
        entries = parse_clausewitz(read("events/ADISCORD_vorkerland_events.txt"))
        scenes = {scalar(e.value, "id"): e.value for e in entries
                  if e.key == "country_event" and scalar(e.value, "id") in
                  {f"ADISCORD_vorkerland_postwar.{n}" for n in range(31, 51)}}
        self.assertEqual(len(scenes), 20)
        for key, scene in scenes.items():
            self.assertEqual(scalar(scene, "fire_only_once"), "yes", key)
            options = [e.value for e in scene if e.key == "option"]
            self.assertNotIn("trigger", {e.key for e in options[0]}, key)
            self.assertTrue({e.key for e in options[0]} <= {"name", "ai_chance"}, key)
            for option in options[1:]:
                s = Scenario()
                s.flags.add("WRK_worx_supervised")
                before = deepcopy(s.__dict__)
                s.run([e for e in option if e.key not in ("name", "trigger", "ai_chance")])
                self.assertEqual(s.__dict__, before, key)
            texts = [e.value if isinstance(e.value, str) else scalar(e.value, "text")
                     for e in scene if e.key == "desc"]
            for language in ("russian", "english"):
                localisation = read(f"localisation/{language}/ADISCORD_vorkerland_l_{language}.yml")
                entries = dict(match.groups() for line in localisation.splitlines()
                               if (match := LOCALISATION_ENTRY.fullmatch(line)))
                for text_key in texts:
                    self.assertIn(text_key, entries)
                    value = entries[text_key]
                    self.assertNotRegex(value, r'\\(?![n"\\])', text_key)
                    expanded = re.sub(r'\\([n"\\])',
                                      lambda match: "\n" if match[1] == "n" else match[1], value)
                    self.assertLessEqual(len(expanded), 3000, text_key)
                    self.assertLessEqual(len(expanded.encode("utf-8")), 5500, text_key)

    def test_story_variants_match_the_actual_course_and_madness_boundary(self):
        entries = parse_clausewitz(read("events/ADISCORD_vorkerland_events.txt"))
        scenes = {scalar(e.value, "id"): e.value for e in entries if e.key == "country_event"}

        def selected(number, scenario):
            descriptions = [e.value for e in scenes[f"ADISCORD_vorkerland_postwar.{number}"]
                            if e.key == "desc"]
            return [scalar(value, "text") for value in descriptions
                    if scenario.matches(block(value, "trigger"))]

        for supervised, madness, suffix in (
            (False, 0, "quiet"), (False, 74.99, "quiet"),
            (False, 75, "crisis"), (False, 100, "crisis"), (True, 100, "council"),
        ):
            s = Scenario()
            s.values["WRK_worx_madness"] = madness
            if supervised:
                s.flags.add("WRK_worx_supervised")
            self.assertEqual(selected(50, s), ["ADISCORD_vorkerland_postwar.50." + suffix])
            for number in (32, 33, 34):
                expected = "after" if supervised else "d"
                self.assertEqual(selected(number, s), [f"ADISCORD_vorkerland_postwar.{number}.{expected}"])
        s = Scenario()
        self.assertEqual(selected(49, s), ["ADISCORD_vorkerland_postwar.49.administrative"])
        s.flags.add("WRK_worx_civil_charters")
        self.assertEqual(selected(49, s), ["ADISCORD_vorkerland_postwar.49.civil"])
        s.focuses.add("WRK_worx_black_boxes")
        self.assertEqual(selected(44, s), ["ADISCORD_vorkerland_postwar.44.boxes"])
        s.focuses = {"WRK_worx_glass_walls"}
        self.assertEqual(selected(44, s), ["ADISCORD_vorkerland_postwar.44.glass"])

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
        self.assertEqual(len(focuses), 120)
        positions = [(scalar(f, "x"), scalar(f, "y")) for f in focuses.values()]
        self.assertEqual(len(set(positions)), len(positions))
        for row in {y for x, y in positions}:
            columns = sorted(int(x) for x, y in positions if y == row)
            self.assertTrue(all(right - left >= 2 for left, right in zip(columns, columns[1:])), row)

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
            if key in route:
                for group in (e.value for e in focus if e.key == "prerequisite"):
                    self.assertTrue(any(parent.value in route for parent in group), key)
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

    def test_extended_programmes_share_escrow_and_refund_every_currency(self):
        programmes = (
            ("archive_audit", "control_group", 75, 0, 0),
            ("clinical_series", "names_obstruct", 125, 100, 50),
            ("tooling_order", "serial_numbers", 150, 0, 100),
            ("rehabilitation", "soldier_returns", 75, 0, 60),
            ("conditioning", "return_unplanned", 100, 150, 60),
            ("district_clinics", "compulsory_welfare", 100, 0, 100),
            ("population_registry", "complaints_deviations", 75, 100, 0),
            ("corridor_depots", "maps_have_weight", 125, 0, 80),
        )
        for kind, unlock, price, manpower, support in programmes:
            with self.subTest(kind=kind):
                s = Scenario()
                s.focuses.add("WRK_worx_" + unlock)
                s.pp = price - .01
                self.assertFalse(s.start(kind))
                s.pp = price
                s.manpower = manpower
                s.support = support
                for currency, amount in (("manpower", manpower), ("support", support)):
                    if amount:
                        setattr(s, currency, amount - .01)
                        self.assertFalse(s.start(kind))
                        setattr(s, currency, amount)
                self.assertTrue(s.start(kind))
                self.assertEqual((s.pp, s.manpower, s.support), (0, 0, 0))
                s.pp = 500
                self.assertFalse(s.start("basic"))
                s.pp = 0
                # The paid receipt survives an ordinary save/load of this version.
                s.__dict__ = deepcopy(s.__dict__)
                s.subject = True
                s.day()
                self.assertEqual((s.pp, s.manpower, s.support), (price, manpower, support))
                self.assertNotIn("WRK_worx_operation", s.values)
                s.run(EFFECTS["WRK_worx_finish_" + kind])
                self.assertEqual((s.pp, s.manpower, s.support), (price, manpower, support))

    def test_archive_audit_relief_does_not_feed_demands(self):
        s = Scenario()
        s.focuses.add("WRK_worx_control_group")
        s.values["WRK_worx_growth"] = .25
        s.values["WRK_worx_madness"] = 50
        self.assertTrue(s.start("archive_audit"))
        for _ in range(20):
            s.day()
        self.assertEqual(s.values["WRK_worx_madness"], 55)
        s.day()
        self.assertEqual(s.values["WRK_worx_madness"], 43.25)
        self.assertEqual(s.values["WRK_worx_results"], 0)
        before = deepcopy(s.__dict__)
        s.run(EFFECTS["WRK_worx_finish_archive_audit"])
        self.assertEqual(s.__dict__, before)

    def test_new_material_deliveries_are_once_only_and_use_current_upgrade(self):
        for kind, unlock, upgrade, days, trucks, support in (
            ("tooling_order", "serial_numbers", "conveyor_memory", 35, 300, 700),
            ("corridor_depots", "maps_have_weight", "corridor_dispatch", 28, 500, 520),
        ):
            with self.subTest(kind=kind):
                s = Scenario()
                s.focuses.add("WRK_worx_" + unlock)
                self.assertTrue(s.start(kind))
                for _ in range(days - 1):
                    s.day()
                self.assertEqual(s.stockpiles, {})
                s.focuses.add("WRK_worx_" + upgrade)
                s.day()
                self.assertEqual(s.stockpiles["motorized_equipment_1"], trucks)
                self.assertEqual(s.support, support)
                self.assertNotIn("WRK_worx_receipt", s.values)
                before = deepcopy(s.__dict__)
                s.run(EFFECTS["WRK_worx_finish_" + kind])
                self.assertEqual(s.__dict__, before)

    def test_paid_experimental_result_consumes_deposits_and_increases_demands(self):
        for kind, unlock, manpower, support, relief, xp in (
            ("clinical_series", "names_obstruct", 100, 50, 35, 0),
            ("conditioning", "return_unplanned", 150, 60, 20, 30),
            ("population_registry", "complaints_deviations", 100, 0, 15, 15),
        ):
            with self.subTest(kind=kind):
                s = Scenario()
                s.focuses.add("WRK_worx_" + unlock)
                s.values["WRK_worx_results"] = 2
                s.values["WRK_worx_madness"] = 50
                s.values["WRK_worx_growth"] = .25
                self.assertTrue(s.start(kind))
                for _ in range(21):
                    s.day()
                self.assertEqual(s.values["WRK_worx_madness"], 55.25 - relief)
                self.assertEqual(s.values["WRK_worx_demand"], 2)
                self.assertEqual((s.manpower, s.support, s.xp), (5000 - manpower, 500 - support, xp))
                self.assertNotIn("WRK_worx_manpower_deposit", s.values)
                self.assertNotIn("WRK_worx_support_deposit", s.values)

    def test_civil_programmes_work_under_oversight_without_restarting_madness(self):
        for kind, unlock, days, manpower, stability in (
            ("rehabilitation", "soldier_returns", 28, 5800, .51),
            ("district_clinics", "compulsory_welfare", 28, 5400, .54),
        ):
            with self.subTest(kind=kind):
                s = Scenario()
                s.focuses.update(("WRK_worx_" + unlock, "WRK_worx_safety_confirmed"))
                s.flags.add("WRK_worx_supervised")
                s.values["WRK_worx_madness"] = 0
                self.assertTrue(s.start(kind))
                for _ in range(days):
                    s.day()
                self.assertEqual(s.manpower, manpower)
                self.assertAlmostEqual(s.stability, stability)
                self.assertEqual(s.values["WRK_worx_madness"], 0)
                self.assertEqual(s.values["WRK_worx_growth_total"], 0)

    def test_scientific_pressure_survives_selecting_a_political_course(self):
        tree = block(parse_clausewitz(read(
            "focus_trees/Vorkerland/technical_directorate/focuses.txt"
        )), "focus_tree")
        focuses = {scalar(e.value, "id"): e.value for e in tree if e.key == "focus"}
        s = Scenario()
        s.run(block(focuses["WRK_worx_black_boxes"], "completion_reward"))
        self.assertAlmostEqual(s.values["WRK_worx_growth_total"], 1.05)
        s.run(block(focuses["WRK_worx_genius_permission"], "completion_reward"))
        before = s.values["WRK_worx_madness"]
        s.day()
        self.assertAlmostEqual(s.values["WRK_worx_growth_total"], .55)
        self.assertAlmostEqual(s.values["WRK_worx_madness"] - before, .55)

    def test_every_focus_has_a_route_without_exclusive_ancestors(self):
        tree = block(parse_clausewitz(read(
            "focus_trees/Vorkerland/technical_directorate/focuses.txt"
        )), "focus_tree")
        focuses = {scalar(e.value, "id"): e.value for e in tree if e.key == "focus"}
        exclusions = {key: {e.value for group in value if group.key == "mutually_exclusive"
                            for e in group.value}
                      for key, value in focuses.items()}

        @lru_cache(None)
        def routes(key):
            paths = {frozenset((key,))}
            for group in (e.value for e in focuses[key] if e.key == "prerequisite"):
                alternatives = {path for parent in group for path in routes(parent.value)}
                paths = {left | right for left in paths for right in alternatives
                         if not any(exclusions[node] & (left | right) for node in left | right)}
            return paths

        for key in focuses:
            self.assertTrue(routes(key), key)
        war_routes = routes("WRK_utilitarian_west_engineering_border")
        shortest = min(sum(float(scalar(focuses[key], "cost")) * 7 for key in route)
                       for route in war_routes)
        self.assertLessEqual(shortest, 180)

    def test_clinical_series_is_cancelled_when_council_ends_experiments(self):
        s = Scenario()
        s.focuses.add("WRK_worx_names_obstruct")
        before = (s.pp, s.manpower, s.support)
        self.assertTrue(s.start("clinical_series"))
        s.flags.add("WRK_worx_supervised")
        s.day()
        self.assertEqual((s.pp, s.manpower, s.support), before)
        self.assertEqual(s.values["WRK_worx_results"], 0)

    def test_event_registration_localisation_and_source_encoding(self):
        ids = {e["id"] for e in json.loads(read("tools/data/adiscord_event_ids.json"))["events"]}
        for num in range(20, 51):
            self.assertIn(f"ADISCORD_vorkerland_postwar.{num}", ids)
        for language in ("russian", "english"):
            path = ROOT / f"localisation/{language}/ADISCORD_vorkerland_l_{language}.yml"
            self.assertTrue(path.read_bytes().startswith(b"\xef\xbb\xbf"))
            for line in path.read_text(encoding="utf-8-sig").splitlines():
                if re.match(r" (WRK_worx_|ADISCORD_vorkerland_postwar\.2[0-3])", line):
                    self.assertIsNotNone(LOCALISATION_ENTRY.fullmatch(line), line)
                    self.assertNotRegex(line, "[\u2013\u2014]")


if __name__ == "__main__":
    unittest.main()
