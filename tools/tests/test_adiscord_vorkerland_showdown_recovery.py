from __future__ import annotations

import unittest
from pathlib import Path

from tools.validators.validate_adiscord_vorkerland_recovery import (
    SHOWDOWN_PAIRS,
    event_block,
    named_block,
    named_blocks,
    validate_bounded_retry,
)


ROOT = Path(__file__).resolve().parents[2]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8-sig")


def issue_report(issues: list[str]) -> str:
    return "\n" + "\n".join(f"- {issue}" for issue in issues)


class CentralShowdownRecoveryTests(unittest.TestCase):
    def test_bounded_retry_validator_includes_recoverable_terminal_failure(self) -> None:
        issues = validate_bounded_retry()
        self.assertEqual(issues, [], issue_report(issues))

    def test_terminal_launch_failure_unwinds_the_entire_round_and_arms_cooldown(self) -> None:
        effects = read("common/scripted_effects/ADISCORD_vorkerland_phase_effects.txt")
        unwind = named_block(effects, "ADISCORD_vorkerland_unwind_failed_showdown_launch")
        self.assertTrue(unwind)

        unwind_limit = named_block(unwind, "limit")
        self.assertIn(
            "has_global_flag = ADISCORD_vorkerland_central_showdown_launch_failed",
            unwind_limit,
        )
        self.assertIn(
            "NOT = { has_global_flag = ADISCORD_vorkerland_central_showdown_started }",
            unwind_limit,
        )

        flags = [
            "ADISCORD_vorkerland_focus_central_showdown_requested",
            "ADISCORD_vorkerland_showdown_queue_initialized",
            "ADISCORD_vorkerland_showdown_launch_round_started",
            "ADISCORD_vorkerland_central_showdown_launch_failed",
        ]
        flags.extend(
            f"ADISCORD_vorkerland_showdown_edge_{slug}_{state}"
            for slug, _, _, _ in SHOWDOWN_PAIRS
            for state in ("required", "attempted", "retry", "verified", "failed")
        )
        for flag in flags:
            self.assertEqual(unwind.count(f"clr_global_flag = {flag}"), 1, flag)

        cooldowns = [
            block
            for block in named_blocks(unwind, "set_global_flag")
            if "flag = ADISCORD_vorkerland_showdown_retry_cooldown" in block
        ]
        self.assertEqual(len(cooldowns), 1)
        self.assertEqual(cooldowns[0].count("days = 7"), 1)

        advance = named_block(effects, "ADISCORD_vorkerland_advance_showdown_launch")
        unwind_call = "ADISCORD_vorkerland_unwind_failed_showdown_launch = yes"
        self.assertEqual(advance.count(unwind_call), 1)
        self.assertGreater(
            advance.find(unwind_call),
            advance.find("has_global_flag = ADISCORD_vorkerland_central_showdown_launch_failed"),
        )

    def test_visible_commit_returns_after_the_timed_cooldown(self) -> None:
        decisions = read("common/decisions/ADISCORD_vorkerland_focus_decisions.txt")
        commit = named_block(decisions, "ADISCORD_vorkerland_commit_to_central_showdown")
        self.assertTrue(commit)
        self.assertNotIn("fire_only_once = yes", commit)
        self.assertEqual(commit.count("fire_only_once = no"), 1)
        self.assertEqual(commit.count("days_re_enable = 7"), 1)
        available = named_block(commit, "available")
        cooldown_guard = (
            "NOT = { has_global_flag = ADISCORD_vorkerland_showdown_retry_cooldown }"
        )
        self.assertIn(cooldown_guard, available)

        effects = read("common/scripted_effects/ADISCORD_vorkerland_focus_decision_effects.txt")
        scheduler = named_block(effects, "ADISCORD_vorkerland_focus_schedule_final_showdown")
        request_branches = [
            block
            for block in named_blocks(scheduler, "if")
            if "set_global_flag = ADISCORD_vorkerland_focus_central_showdown_requested" in block
        ]
        self.assertEqual(len(request_branches), 1)
        self.assertIn(cooldown_guard, named_block(request_branches[0], "limit"))

    def test_queued_reunification_rechecks_the_integrated_central_map(self) -> None:
        events = read("events/ADISCORD_vorkerland_phase_events.txt")
        phase_six = event_block(events, "ADISCORD_vorkerland_phase.6")
        self.assertIn("id = ADISCORD_vorkerland_phase.6", phase_six)
        self.assertEqual(
            phase_six.count(
                "ADISCORD_vorkerland_central_districts_owned_and_controlled = yes"
            ),
            3,
        )

        for target in ("EYR", "EGC", "RIV", "REV", "YOR", "NDN", "SWB", "VHV", "OSV"):
            self.assertIn(f"NOT = {{ country_exists = {target} }}", phase_six)
        for flag in (
            "ADISCORD_vorkerland_focus_central_minor_launch_pending",
            "ADISCORD_vorkerland_focus_central_minor_deadline_active",
        ):
            self.assertEqual(phase_six.count(flag), 3)
        for state in (
            102, 109, 111, 325, 81, 110, 124, 79, 306, 308, 309, 327,
            82, 323, 108, 122, 123, 27, 35, 315, 316, 317, 318, 320,
        ):
            self.assertIn(
                f"{state} = {{ OR = {{ is_core_of = WKR is_core_of = VAD is_core_of = TVA }} }}",
                phase_six,
            )

    def test_startup_repairs_each_missing_controller_event_once_in_claimant_priority(self) -> None:
        on_actions = read("common/on_actions/01_ADISCORD_vorkerland_collapse_on_actions.txt")
        startup = named_block(on_actions, "on_startup")
        repair_flag = "ADISCORD_vorkerland_showdown_startup_repair_scheduled"

        phase_branches: dict[str, tuple[str, str]] = {}
        for branch_type in ("if", "else_if"):
            for branch in named_blocks(startup, branch_type):
                for phase_id in ("4", "5"):
                    if (
                        f"ADISCORD_vorkerland_phase.{phase_id} days = 1" in branch
                        and f"flag = {repair_flag}" in branch
                    ):
                        self.assertNotIn(phase_id, phase_branches)
                        phase_branches[phase_id] = (branch_type, branch)

        self.assertEqual(set(phase_branches), {"4", "5"})
        self.assertEqual(phase_branches["4"][0], "if")
        self.assertEqual(phase_branches["5"][0], "else_if")

        for phase_id, (_, branch) in phase_branches.items():
            branch_limit = named_block(branch, "limit")
            for guard in (
                "has_global_flag = ADISCORD_vorkerland_phase_central_preparation",
                "NOT = { has_global_flag = ADISCORD_vorkerland_central_showdown_started }",
                f"NOT = {{ has_global_flag = {repair_flag} }}",
                "OR = { country_exists = WKR country_exists = VAD country_exists = TVA }",
            ):
                self.assertIn(guard, branch_limit)
            schedules = [
                block
                for block in named_blocks(branch, "set_global_flag")
                if f"flag = {repair_flag}" in block
            ]
            self.assertEqual(len(schedules), 1)
            self.assertEqual(schedules[0].count("days = 3"), 1)

            dispatch = (
                f"country_event = {{ id = ADISCORD_vorkerland_phase.{phase_id} days = 1 }}"
            )
            claimant_dispatches = [
                f"WKR = {{ {dispatch} }}",
                f"VAD = {{ {dispatch} }}",
                f"TVA = {{ {dispatch} }}",
            ]
            positions = [branch.find(token) for token in claimant_dispatches]
            self.assertTrue(all(position >= 0 for position in positions))
            self.assertEqual(positions, sorted(positions))
            self.assertEqual(branch.count(dispatch), 3)

        phase_four_limit = named_block(phase_branches["4"][1], "limit")
        self.assertIn(
            "has_global_flag = ADISCORD_vorkerland_focus_central_showdown_requested",
            phase_four_limit,
        )
        self.assertIn(
            "NOT = { has_global_flag = ADISCORD_vorkerland_showdown_queue_initialized }",
            phase_four_limit,
        )
        phase_five_limit = named_block(phase_branches["5"][1], "limit")
        self.assertIn(
            "has_global_flag = ADISCORD_vorkerland_showdown_queue_initialized",
            phase_five_limit,
        )

        for monthly in named_blocks(on_actions, "on_monthly"):
            self.assertNotIn(repair_flag, monthly)
            self.assertNotIn("ADISCORD_vorkerland_showdown_retry_cooldown", monthly)
            self.assertNotIn("ADISCORD_vorkerland_unwind_failed_showdown_launch", monthly)


if __name__ == "__main__":
    unittest.main()
