from __future__ import annotations

import unittest

from tools.validators.validate_adiscord_vorkerland_recovery import (
    collect_issues,
    event_block,
    named_block,
    validate_bounded_retry,
    validate_new_save_materialization,
    validate_retired_legacy_events,
    validate_phase_controller,
    validate_reunification_formation,
    validate_wkr_semantics,
)


def issue_report(issues: list[str]) -> str:
    return "\n" + "\n".join(f"- {issue}" for issue in issues)


class RecoveryValidatorHelperTests(unittest.TestCase):
    def test_structural_helpers_follow_balanced_blocks(self) -> None:
        source = """
outer = {
    inner = { token = yes }
}
country_event = {
    id = ADISCORD_vorkerland_phase.5
    immediate = { token = yes }
}
"""
        self.assertIn("inner = { token = yes }", named_block(source, "outer"))
        self.assertIn(
            "immediate = { token = yes }",
            event_block(source, "ADISCORD_vorkerland_phase.5"),
        )


class WkrTagSemanticTests(unittest.TestCase):
    def test_wkr_tag_country_flags_and_names(self) -> None:
        issues = validate_wkr_semantics()
        self.assertEqual(issues, [], issue_report(issues))


class NewSaveMaterializationTests(unittest.TestCase):
    def test_atomic_split_handoff_annex_and_strict_postconditions(self) -> None:
        issues = validate_new_save_materialization()
        self.assertEqual(issues, [], issue_report(issues))


class PhaseControllerTests(unittest.TestCase):
    def test_exact_seven_phase_and_wartime_claimant_contract(self) -> None:
        issues = validate_phase_controller()
        self.assertEqual(issues, [], issue_report(issues))


class BoundedRetryTests(unittest.TestCase):
    def test_three_required_edges_launch_together_and_are_postcondition_driven(self) -> None:
        issues = validate_bounded_retry()
        self.assertEqual(issues, [], issue_report(issues))


class ReunificationFormationTests(unittest.TestCase):
    def test_winner_forms_wrk_only_after_loser_subject_release(self) -> None:
        issues = validate_reunification_formation()
        self.assertEqual(issues, [], issue_report(issues))


class RetiredLegacyEventTests(unittest.TestCase):
    def test_old_save_scheduler_events_are_removed(self) -> None:
        issues = validate_retired_legacy_events()
        self.assertEqual(issues, [], issue_report(issues))


class VorkerlandRecoveryValidatorTests(unittest.TestCase):
    def test_integrated_recovery_contract(self) -> None:
        issues = collect_issues()
        self.assertEqual(issues, [], issue_report(issues))


if __name__ == "__main__":
    unittest.main()
