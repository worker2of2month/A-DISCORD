import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8-sig")


def named_block(text: str, name: str) -> str:
    match = re.search(rf"(?m)^\s*{re.escape(name)}\s*=\s*\{{", text)
    if not match:
        raise AssertionError(f"missing block: {name}")
    start = text.find("{", match.start())
    depth = 0
    for index in range(start, len(text)):
        if text[index] == "{":
            depth += 1
        elif text[index] == "}":
            depth -= 1
            if depth == 0:
                return text[match.start() : index + 1]
    raise AssertionError(f"unterminated block: {name}")


class NorthernEscalationTests(unittest.TestCase):
    canonical = (
        ("ZAO", "WPA", 25),
        ("WPS", "ZAO", 33),
        ("ZAO", "PSD", 25),
        ("PWR", "ZAO", 25),
        ("WPA", "PSD", 33),
        ("WPA", "PWR", 33),
        ("WPS", "PSD", 33),
        ("WPS", "PWR", 33),
        ("PWR", "PSD", 25),
    )

    def test_northern_militia_is_line_infantry_not_garrison(self) -> None:
        templates = read("common/ai_templates/ADISCORD_land_templates.txt")
        line = named_block(
            templates, "ADISCORD_vorkerland_northern_militia_templates"
        )
        self.assertIn("role = infantry", line)
        self.assertIn("ADISCORD_vorkerland_northern_line_militia", line)
        self.assertIn("regiments = { ADISCORD_militia = 4 }", line)
        for tag in ("ZAO", "WPA", "WPS", "PWR", "PSD"):
            self.assertIn(f"tag = {tag}", line)
        garrison = named_block(templates, "ADISCORD_garrison_levy")
        self.assertIn("ADISCORD_vorkerland_collapse_wars_started", garrison)
        self.assertIn("NOT =", garrison)

    def test_base_front_ratios_are_bounded_per_country(self) -> None:
        strategies = read("common/ai_strategy/ADISCORD_vorkerland_collapse_ai.txt")
        expected = {"ZAO": 0.25, "WPA": 0.33, "WPS": 0.33, "PWR": 0.25, "PSD": 0.25}
        totals = {tag: 0.0 for tag in expected}
        for attacker, target in (
            ("ZAO", "WPA"), ("WPA", "ZAO"), ("WPS", "ZAO"),
            ("ZAO", "WPS"), ("ZAO", "PSD"), ("PSD", "ZAO"),
            ("ZAO", "PWR"), ("PWR", "ZAO"), ("WPA", "PSD"),
            ("PSD", "WPA"), ("WPA", "PWR"), ("PWR", "WPA"),
            ("WPS", "PSD"), ("PSD", "WPS"), ("WPS", "PWR"),
            ("PWR", "WPS"), ("PWR", "PSD"), ("PSD", "PWR"),
        ):
            block = named_block(
                strategies,
                f"ADISCORD_vorkerland_front_{attacker.lower()}_{target.lower()}",
            )
            ratio = expected[attacker]
            self.assertIn(f"tag = {target} ratio = {ratio:.2f}", block)
            self.assertIn(f"tag = {target} value = {round(ratio * 100)}", block)
            totals[attacker] += ratio
        for tag, total in totals.items():
            self.assertLessEqual(total, 1.0, f"{tag} requests {total:.2f} fronts")

    def test_escalation_consumers_are_target_specific_and_do_not_stack(self) -> None:
        strategies = read("common/ai_strategy/ADISCORD_vorkerland_collapse_ai.txt")
        for attacker, target, request in self.canonical:
            suffix = f"{attacker.lower()}_{target.lower()}"
            base = named_block(strategies, f"ADISCORD_vorkerland_front_{suffix}")
            aggressive = named_block(
                strategies, f"ADISCORD_vorkerland_escalation_{suffix}"
            )
            selector = f"ADISCORD_vorkerland_northern_escalation_{suffix}"
            self.assertIn(selector, base)
            self.assertIn("ADISCORD_vorkerland_northern_escalation_stage_2", base)
            self.assertIn(selector, aggressive)
            self.assertIn("has_idea = ADISCORD_vorkerland_northern_operational_initiative", aggressive)
            self.assertIn(f"front_unit_request tag = {target} value = {request}", aggressive)
            self.assertIn(f"type = conquer id = {target}", aggressive)
            self.assertIn("execution_type = rush", aggressive)
            self.assertIn("manual_attack = yes", aggressive)

    def test_timers_are_one_shot_from_graph_launch_and_have_no_forced_outcome(self) -> None:
        effects = read("common/scripted_effects/ADISCORD_vorkerland_collapse_effects.txt")
        schedule = named_block(effects, "ADISCORD_vorkerland_schedule_northern_escalation")
        launch = named_block(effects, "ADISCORD_vorkerland_open_regional_fronts_after_detach")
        select = named_block(effects, "ADISCORD_vorkerland_select_northern_escalation_front")
        intensify = named_block(effects, "ADISCORD_vorkerland_intensify_surviving_northern_fronts")
        self.assertEqual(schedule.count("ADISCORD_vorkerland_collapse.83 days = 730"), 2)
        self.assertEqual(schedule.count("ADISCORD_vorkerland_collapse.84 days = 1095"), 2)
        self.assertIn("NOT = { has_global_flag = ADISCORD_vorkerland_northern_escalation_scheduled }", schedule)
        self.assertIn("ADISCORD_vorkerland_schedule_northern_escalation = yes", launch)
        self.assertEqual(select.count("ADISCORD_vorkerland_northern_escalation_stage_1"), 9)
        self.assertEqual(select.count("add_timed_idea = { idea = ADISCORD_vorkerland_northern_operational_initiative"), 9)
        self.assertEqual(intensify.count("set_global_flag = ADISCORD_vorkerland_northern_escalation_stage_2"), 1)

        events = read("events/ADISCORD_vorkerland_collapse_events.txt")
        for event_id, effect in (
            (83, "ADISCORD_vorkerland_select_northern_escalation_front"),
            (84, "ADISCORD_vorkerland_intensify_surviving_northern_fronts"),
        ):
            marker = f"id = ADISCORD_vorkerland_collapse.{event_id}"
            marker_start = events.index(marker)
            start = events.rfind("country_event = {", 0, marker_start)
            block = named_block(events[start:], "country_event")
            self.assertIn(f"{effect} = yes", block)
            for forbidden in ("declare_war_on", "annex_country", "white_peace"):
                self.assertNotIn(forbidden, block)

        on_actions = "\n".join(
            path.read_text(encoding="utf-8-sig")
            for path in (ROOT / "common/on_actions").glob("*.txt")
        )
        self.assertNotIn("ADISCORD_vorkerland_collapse.83", on_actions)
        self.assertNotIn("ADISCORD_vorkerland_collapse.84", on_actions)


if __name__ == "__main__":
    unittest.main()
