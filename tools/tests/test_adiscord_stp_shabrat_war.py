"""Resistance war contracts: Shabrat's mandate, coalition, courses and victory.

These tests inspect authored scripts, not the Clausewitz runtime.
"""

import json
import re
import unittest

from tools.tests.test_adiscord_stp_party_inheritance import (
    CIVIL_WAR,
    DECISIONS,
    DYNAMIC,
    EFFECTS,
    EN,
    EVENTS,
    IDEAS,
    ON_ACTIONS,
    REGISTRY,
    RU,
    SUPER_EN,
    SUPER_RU,
    SUPEREVENT_LOC,
    TRIGGERS,
    definition,
    focus_blocks,
    loc_keys,
    text,
)

PLANS = "common/ai_strategy_plans/ADISCORD_STP_plans.txt"

HW_FOCUSES = (
    "STP_hw_mountain_mandate",
    "STP_hw_leaflets_over_fada",
    "STP_hw_council_of_passes",
    "STP_hw_open_black_book",
    "STP_hw_unified_district_command",
    "STP_hw_kefreyt_contract",
    "STP_hw_mountains_pay",
    "STP_hw_coalition_congress",
    "STP_hw_course_staff",
    "STP_hw_course_councils",
    "STP_hw_course_truth",
)
COURSES = {
    "STP_hw_course_staff": (1, "officers", "staff"),
    "STP_hw_course_councils": (2, "councils", "councils"),
    "STP_hw_course_truth": (3, "underground", "truth"),
}
HW_EVENTS = (1, 10, 11, 20, 21, 22)
HW_DECISIONS = ("STP_hw_staff_briefing", "STP_hw_council_guarantees", "STP_hw_night_printing")
HW_IDEAS = (
    "STP_hw_kefreyt_quartermasters_idea",
    "STP_hw_mountain_levies_idea",
    "STP_hw_officers_sulk_idea",
    "STP_hw_course_staff_idea",
    "STP_hw_course_councils_idea",
    "STP_hw_course_truth_idea",
    "STP_hw_republic_of_mountains_idea",
    "STP_hw_victory_on_credit_idea",
)


def compact(source):
    return " ".join(re.sub(r"(?m)#.*$", "", source).split())


def position(body):
    x = int(re.search(r"\n\t\tx = (-?\d+)", body).group(1))
    y = int(re.search(r"\n\t\ty = (-?\d+)", body).group(1))
    return x, y


class ResistanceFocusTests(unittest.TestCase):
    def test_focuses_are_resistance_only_and_localised(self):
        focuses = focus_blocks(CIVIL_WAR)
        ru, en = loc_keys(RU), loc_keys(EN)
        for focus_id in HW_FOCUSES:
            body = focuses[focus_id]
            self.assertIn("allow_branch = { NOT = { has_country_flag = STP_cw_postwar } tag = STS }", body)
            for key in (focus_id, f"{focus_id}_desc"):
                self.assertTrue(ru.get(key), key)
                self.assertTrue(en.get(key), key)
            for tooltip in re.findall(r"custom_effect_tooltip = (\S+)", body):
                self.assertTrue(ru.get(tooltip) and en.get(tooltip), tooltip)

    def test_courses_are_exclusive_and_need_their_pillar(self):
        focuses = focus_blocks(CIVIL_WAR)
        for course, (number, pillar, _) in COURSES.items():
            body = compact(focuses[course])
            for other in COURSES:
                if other != course:
                    self.assertIn(f"focus = {other}", body)
            self.assertIn(f"STP_hw_{pillar}_can_lead = yes", body)
            self.assertIn(f"set_variable = {{ var = STP_hw_course value = {number} }}", body)
            self.assertIn(f"STP_hw_{pillar}_can_lead = {{", compact(text(TRIGGERS)))
        self.assertIn("focus = STP_hw_mountains_pay", focuses["STP_hw_kefreyt_contract"])
        self.assertIn("focus = STP_hw_kefreyt_contract", focuses["STP_hw_mountains_pay"])

    def test_branch_keeps_two_columns_from_every_visible_resistance_focus(self):
        focuses = focus_blocks(CIVIL_WAR)
        visible = {}
        for focus_id, body in focuses.items():
            branch = re.search(r"allow_branch = \{([^\n]*)\}", body)
            if not branch or "has_country_flag = STP_cw_postwar }" not in branch.group(1):
                continue
            if "tag = STP" in branch.group(1) or "tag = SRP" in branch.group(1):
                continue
            visible[focus_id] = position(body)
        for focus_id in HW_FOCUSES:
            x, y = visible[focus_id]
            for other, (other_x, other_y) in visible.items():
                if other != focus_id and other_y == y:
                    self.assertGreaterEqual(abs(other_x - x), 2, f"{focus_id} overlaps {other}")

    def test_ai_plan_takes_the_branch_after_the_last_banquet(self):
        plan = definition(PLANS, "STS_shabrat_civil_war_plan")
        order = re.findall(r"(?m)^\s*(STP_\w+)\s*$", plan[plan.index("ai_national_focuses"):])
        self.assertLess(order.index("STP_cw_last_banquet"), order.index("STP_hw_mountain_mandate"))
        self.assertIn("STP_hw_course_staff", order)
        self.assertNotIn("STP_hw_mountains_pay", order)


class MandateMechanicTests(unittest.TestCase):
    def test_effects_and_triggers_are_defined_once(self):
        effects, triggers = text(EFFECTS), text(TRIGGERS)
        for name in (
            "STP_hw_begin_war", "STP_hw_refresh", "STP_hw_change_mandate", "STP_hw_monthly",
            "STP_hw_check_mandate_thresholds", "STP_hw_check_pillar_crisis",
            "STP_hw_operation_won", "STP_hw_operation_failed", "STP_hw_resolve_victory", "STP_hw_close_war",
        ):
            self.assertEqual(len(re.findall(rf"(?m)^{name} = {{", effects)), 1, name)
        for name in ("STP_hw_war_current", "STP_hw_black_book_ready"):
            self.assertEqual(len(re.findall(rf"(?m)^{name} = {{", triggers)), 1, name)

    def test_mandate_scale_is_neutral_at_fifty_and_bounded(self):
        refresh = compact(definition(EFFECTS, "STP_hw_refresh"))
        self.assertIn("clamp_variable = { var = STP_hw_mandate min = 0 max = 100 }", refresh)

        def run(mandate, variable):
            chain = refresh[refresh.index(f"set_variable = {{ var = {variable} value = STP_hw_mandate }}"):]
            value = mandate
            for op, amount in re.findall(rf"(subtract_from|multiply|divide)_variable = {{ var = {variable} value = (\d+) }}", chain)[:3]:
                amount = int(amount)
                value = value - amount if op == "subtract_from" else value * amount if op == "multiply" else value / amount
            return value

        self.assertEqual(run(50, "STP_hw_mandate_stability"), 0)
        self.assertAlmostEqual(run(100, "STP_hw_mandate_stability"), 0.10)
        self.assertAlmostEqual(run(0, "STP_hw_mandate_stability"), -0.10)
        self.assertAlmostEqual(run(100, "STP_hw_mandate_conscription"), 0.15)
        dynamic = compact(definition(DYNAMIC, "STP_hw_mandate_dynamic"))
        for variable in ("STP_hw_mandate_stability", "STP_hw_mandate_war_support", "STP_hw_mandate_conscription"):
            self.assertIn(variable, dynamic)
        self.assertTrue(loc_keys(RU).get("STP_hw_mandate_dynamic"))

    def test_war_start_monthly_tick_operations_and_victory_are_wired(self):
        actions = compact(text(ON_ACTIONS))
        weekly = actions[actions.index("on_weekly_STS = {"):]
        self.assertIn("STP_hw_begin_war = yes", weekly)
        monthly = actions[actions.index("on_monthly_STS = {"):]
        self.assertIn("STP_hw_monthly = yes", monthly[:200])
        self.assertIn("STP_hw_operation_won = yes", compact(definition(EFFECTS, "STP_cw_win_operation")))
        self.assertIn("STP_hw_operation_failed = yes", compact(definition(EFFECTS, "STP_cw_fail_operation")))
        settle = compact(definition(EFFECTS, "STP_cw_settle_union_victory"))
        self.assertIn("if = { limit = { tag = STS } STP_hw_resolve_victory = yes }", settle)
        # The victory report reads the course one hour later.
        self.assertLess(settle.index("STP_hw_resolve_victory"), settle.index("ADISCORD_STP_cw.72"))
        self.assertNotIn("clear_variable = STP_hw_course", compact(definition(EFFECTS, "STP_hw_close_war")))

    def test_victory_always_names_a_course_and_grants_its_spirit(self):
        resolve = compact(definition(EFFECTS, "STP_hw_resolve_victory"))
        self.assertIn("NOT = { has_variable = STP_hw_course }", resolve)
        for _, _, name in COURSES.values():
            self.assertIn(f"STP_hw_course_{name}_idea", resolve)
        self.assertIn("STP_hw_republic_of_mountains_idea", resolve)
        self.assertIn("STP_hw_victory_on_credit_idea", resolve)

    def test_ideas_are_defined_and_localised(self):
        ideas = text(IDEAS)
        ru, en = loc_keys(RU), loc_keys(EN)
        for idea in HW_IDEAS:
            self.assertEqual(len(re.findall(rf"\b{idea} = {{", ideas)), 1, idea)
            for key in (idea, f"{idea}_desc"):
                self.assertTrue(ru.get(key) and en.get(key), key)


class CoalitionEventTests(unittest.TestCase):
    def test_events_are_registered_and_localised(self):
        events = text(EVENTS)
        registry = {entry["id"] for entry in json.loads(text(REGISTRY))["events"]}
        ru, en = loc_keys(RU), loc_keys(EN)
        self.assertIn("add_namespace = ADISCORD_STP_hw", events)
        for number in HW_EVENTS:
            event_id = f"ADISCORD_STP_hw.{number}"
            self.assertEqual(events.count(f"id = {event_id}\n"), 1, event_id)
            self.assertIn(event_id, registry)
            body = events[events.index(f"id = {event_id}\n"):]
            body = body[:body.index("\n}\n")]
            keys = set(re.findall(r"(?:title|desc|name|custom_effect_tooltip) = (\S+)", body))
            for key in keys:
                self.assertTrue(ru.get(key) and en.get(key), key)

    def test_each_crisis_fires_once_with_a_shared_cooldown(self):
        crisis = compact(definition(EFFECTS, "STP_hw_check_pillar_crisis"))
        for pillar, number in (("officers", 20), ("councils", 21), ("underground", 22)):
            self.assertIn(f"STP_hw_crisis_{pillar}_seen", crisis)
            self.assertIn(f"ADISCORD_STP_hw.{number}", crisis)
        self.assertEqual(crisis.count("flag = STP_hw_crisis_cooldown value = 1 days = 45"), 3)

    def test_coalition_decisions_are_resistance_only_and_localised(self):
        decisions = text(DECISIONS)
        ru, en = loc_keys(RU), loc_keys(EN)
        for decision in HW_DECISIONS:
            self.assertEqual(len(re.findall(rf"\b{decision} = {{", decisions)), 1, decision)
            body = compact(decisions[decisions.index(f"{decision} = {{"):][:1500])
            self.assertIn("allowed = { tag = STS }", body)
            self.assertIn("STP_hw_war_current = yes", body)
            for key in (decision, f"{decision}_desc", f"{decision}_tt"):
                self.assertTrue(ru.get(key) and en.get(key), key)

    def test_superevent_varies_with_the_course(self):
        scripted = compact(text(SUPEREVENT_LOC))
        super_ru, super_en = loc_keys(SUPER_RU), loc_keys(SUPER_EN)
        for number, _, name in COURSES.values():
            for kind in ("title", "quote", "comment"):
                key = f"superevent_stelander_shabrat_victory_{name}_{kind}"
                self.assertIn(key, scripted)
                self.assertTrue(super_ru.get(key) and super_en.get(key), key)
            self.assertIn(f"STS = {{ check_variable = {{ var = STP_hw_course value = {number} compare = equals }} }}", scripted)
        # Variants must precede the generic fallback in each defined_text.
        self.assertLess(
            scripted.index("superevent_stelander_shabrat_victory_staff_title"),
            scripted.index("localization_key = superevent_stelander_shabrat_victory_title"),
        )


if __name__ == "__main__":
    unittest.main()
