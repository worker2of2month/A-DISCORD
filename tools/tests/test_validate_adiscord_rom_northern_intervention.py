from __future__ import annotations

import re
import unittest
from pathlib import Path

from tools.validators.validate_adiscord_vorkerland_collapse import named_block


ROOT = Path(__file__).resolve().parents[2]
DECISIONS = "common/decisions/ADISCORD_vorkerland_collapse_decisions.txt"
EFFECTS = "common/scripted_effects/ADISCORD_vorkerland_collapse_effects.txt"
EVENTS = "events/ADISCORD_vorkerland_collapse_events.txt"
ON_ACTIONS = "common/on_actions/01_ADISCORD_vorkerland_collapse_on_actions.txt"
RESOLUTION_TOKENS = (
    "ADISCORD_vorkerland_rom_northern_intervention_active",
    "ADISCORD_vorkerland_rom_northern_intervention_success",
    "ADISCORD_vorkerland_rom_northern_intervention_failure",
    "ADISCORD_vorkerland_end_rom_northern_intervention_wars",
)


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8-sig")


def named_blocks(source: str, name: str) -> list[str]:
    blocks: list[str] = []
    cursor = 0
    pattern = re.compile(rf"(?m)^\s*{re.escape(name)}\s*=\s*\{{")
    while match := pattern.search(source, cursor):
        block = named_block(source[match.start():], name)
        if not block:
            break
        blocks.append(block)
        cursor = match.start() + len(block)
    return blocks


class RomNorthernInterventionRegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        decisions = read(DECISIONS)
        effects = read(EFFECTS)
        cls.events = read(EVENTS)
        cls.on_actions = read(ON_ACTIONS)
        cls.intervention = named_block(
            decisions, "ADISCORD_vorkerland_rom_northern_intervention"
        )
        cls.success = named_block(
            effects, "ADISCORD_vorkerland_rom_northern_intervention_success"
        )
        cls.failure = named_block(
            effects, "ADISCORD_vorkerland_rom_northern_intervention_failure"
        )
        cls.cleanup = named_block(
            effects, "ADISCORD_vorkerland_end_rom_northern_intervention_wars"
        )
        cls.checker = named_block(
            effects, "ADISCORD_vorkerland_check_rom_northern_intervention"
        )
        cls.timeout = named_block(
            effects, "ADISCORD_vorkerland_resolve_rom_northern_intervention_timeout"
        )

    @classmethod
    def event(cls, event_id: int) -> str:
        match = re.search(
            rf"(?ms)^country_event\s*=\s*\{{\s*id\s*=\s*"
            rf"ADISCORD_vorkerland_collapse\.{event_id}\b"
            r"(.*?)(?=^country_event\s*=\s*\{|^add_namespace\s*=|\Z)",
            cls.events,
        )
        return match.group(0) if match else ""

    def test_success_requires_rom_control_of_every_target_state(self) -> None:
        cancel_trigger = named_block(self.intervention, "cancel_trigger")
        cancel_effect = named_block(self.intervention, "cancel_effect")

        for state_id in (72, 196, 322):
            control = f"controls_state = {state_id}"
            self.assertIn(control, cancel_trigger)
            self.assertIn(control, self.success)
            self.assertIn(control, self.timeout)
            self.assertIn(control, self.checker)

        self.assertEqual(
            cancel_effect.count(
                "ADISCORD_vorkerland_rom_northern_intervention_success = yes"
            ),
            1,
        )
        self.assertEqual(
            cancel_effect.count(
                "ADISCORD_vorkerland_rom_northern_intervention_failure = yes"
            ),
            1,
        )

    def test_success_and_failure_are_idempotent_and_exclusive(self) -> None:
        cleanup_call = "ADISCORD_vorkerland_end_rom_northern_intervention_wars = yes"

        for route in (self.success, self.failure):
            self.assertIn(
                "NOT = { has_global_flag = ADISCORD_vorkerland_rom_northern_intervention_resolved }",
                route,
            )
            self.assertIn(cleanup_call, route)
            self.assertIn(
                "set_global_flag = ADISCORD_vorkerland_rom_northern_intervention_resolved",
                route,
            )
            self.assertIn(
                "clr_global_flag = ADISCORD_vorkerland_rom_northern_intervention_active",
                route,
            )

        self.assertLess(self.success.index("rom_northern_intervention_resolved"), self.success.index(cleanup_call))
        self.assertLess(self.failure.index("rom_northern_intervention_resolved"), self.failure.index(cleanup_call))
        self.assertIn(
            "set_global_flag = ADISCORD_vorkerland_rom_northern_intervention_succeeded",
            self.success,
        )
        self.assertIn("clr_global_flag = ADISCORD_vorkerland_rom_northern_intervention_failed", self.success)
        self.assertIn(
            "set_global_flag = ADISCORD_vorkerland_rom_northern_intervention_failed",
            self.failure,
        )
        self.assertIn("clr_global_flag = ADISCORD_vorkerland_rom_northern_intervention_succeeded", self.failure)
        self.assertNotIn("transfer_state", self.failure)

    def test_shared_cleanup_ends_every_northern_co_belligerent_war(self) -> None:
        self.assertIn("ROM = {", self.cleanup)
        for target in ("ZAO", "WPA", "WPS", "PWR", "PSD"):
            self.assertIn(
                f"limit = {{ country_exists = {target} has_war_with = {target} }}",
                self.cleanup,
            )
            self.assertEqual(self.cleanup.count(f"white_peace = {target}"), 1)

        self.assertNotIn("declare_war_on", self.cleanup)
        self.assertNotIn("transfer_state", self.cleanup)

    def test_timeout_routes_by_physical_control_and_has_independent_watchdog(self) -> None:
        timeout = named_block(self.intervention, "timeout_effect")

        self.assertIn("days_mission_timeout = 240", self.intervention)
        self.assertIn("ADISCORD_vorkerland_resolve_rom_northern_intervention_timeout = yes", timeout)
        self.assertIn("ADISCORD_vorkerland_collapse.45 days = 240", self.intervention)
        self.assertIn("ADISCORD_vorkerland_collapse.46 days = 1", self.intervention)
        watchdog = self.event(45)
        self.assertIn("ADISCORD_vorkerland_resolve_rom_northern_intervention_timeout = yes", watchdog)
        self.assertIn("ADISCORD_vorkerland_rom_northern_intervention_success = yes", self.timeout)
        self.assertIn("ADISCORD_vorkerland_rom_northern_intervention_failure = yes", self.timeout)
        self.assertNotIn("transfer_state", timeout)

    def test_resolution_is_driven_by_bounded_edges_without_startup_repair(self) -> None:
        startup = named_block(self.on_actions, "on_startup")
        on_peace = named_block(self.on_actions, "on_peace")
        capitulation = named_block(self.on_actions, "on_capitulation")
        state_control = named_block(self.on_actions, "on_state_control_changed")
        cleanup_event = self.event(46)

        for forbidden in (
            "has_active_mission = ADISCORD_vorkerland_rom_northern_intervention",
            "ADISCORD_vorkerland_resolve_rom_northern_intervention_timeout = yes",
            "ADISCORD_vorkerland_schedule_rom_northern_intervention_check = yes",
        ):
            self.assertNotIn(forbidden, startup)
        self.assertIn("ADISCORD_vorkerland_schedule_rom_northern_intervention_check = yes", on_peace)
        self.assertIn("ROOT = { tag = ROM }", capitulation)
        self.assertIn("ADISCORD_vorkerland_rom_northern_intervention_failure = yes", capitulation)
        self.assertIn("ADISCORD_vorkerland_rom_northern_intervention_success = yes", state_control)
        self.assertEqual(cleanup_event.count("ADISCORD_vorkerland_collapse.46 days = 1"), 1)
        self.assertIn("ADISCORD_vorkerland_rom_northern_cleanup_retry", cleanup_event)

    def test_resolution_is_not_run_from_recurring_on_actions(self) -> None:
        for path in sorted((ROOT / "common/on_actions").glob("*.txt")):
            source = path.read_text(encoding="utf-8-sig")
            for cadence in ("on_daily", "on_weekly", "on_monthly"):
                for index, recurring in enumerate(named_blocks(source, cadence)):
                    for token in RESOLUTION_TOKENS:
                        with self.subTest(
                            file=path.name,
                            cadence=cadence,
                            block=index,
                            token=token,
                        ):
                            self.assertNotIn(token, recurring)


if __name__ == "__main__":
    unittest.main()
