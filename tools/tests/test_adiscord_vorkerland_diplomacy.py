from __future__ import annotations

import unittest

from tools.validators.validate_adiscord_vorkerland_diplomacy import (
    CORE_PACKAGES,
    DIPLOMACY_EFFECTS,
    DIPLOMACY_ON_ACTIONS,
    HISTORICAL_WRK_VAD_STATES,
    LIVE_ALLY_OR_FOREIGN_STATES,
    MATERIALIZE_WKR_PROTECTORATE,
    SOLAR_STATES,
    TERMINAL_CONTRACTS,
    VAD_SOLAR_BORDER_PAIRS,
    VERIFY_WKR_PROTECTORATE,
    VOLNOGRAD_STATES,
    WKR_SOLAR_BORDER_PAIRS,
    collect_issues,
    compact,
    direct_named_blocks,
    event_block,
    named_block,
    named_blocks,
    read,
    validate_bounded_outcome_hook,
    validate_core_packages,
    validate_counter_intervention,
    validate_peaceful_invitations,
    validate_showdown_allies,
    validate_terminal_outcomes,
    validate_vad_egc_route_priority,
    validate_vad_intervention_and_restoration,
    validate_wkr_solyarino_intervention,
)


def issue_report(issues: list[str]) -> str:
    return "\n" + "\n".join(f"- {issue}" for issue in issues)


class DiplomacyValidatorHelperTests(unittest.TestCase):
    def test_balanced_helpers_do_not_escape_parent_blocks(self) -> None:
        source = """
outer = {
    inner = { token = yes }
}
country_event = {
    id = ADISCORD_vorkerland_phase.3
    immediate = { token = yes }
}
"""
        self.assertIn("inner = { token = yes }", named_block(source, "outer"))
        self.assertIn(
            "immediate = { token = yes }",
            event_block(source, "ADISCORD_vorkerland_phase.3"),
        )

    def test_direct_children_do_not_flatten_nested_border_branches(self) -> None:
        source = """
AND = {
    OR = {
        AND = {
            81 = { is_owned_by = VAD }
            307 = { is_owned_by = SRA }
        }
    }
}
"""
        outer = named_block(source, "AND")
        self.assertEqual(direct_named_blocks(outer, "81"), [])
        inner = named_block(named_block(outer, "OR"), "AND")
        self.assertEqual(len(direct_named_blocks(inner, "81")), 1)
        self.assertEqual(len(direct_named_blocks(inner, "307")), 1)


class RegionalTerminalManifestTests(unittest.TestCase):
    def test_exact_solar_and_volnograd_packages_have_three_winners_each(self) -> None:
        solar = [contract for contract in TERMINAL_CONTRACTS.values() if contract[2] == SOLAR_STATES]
        volnograd = [
            contract for contract in TERMINAL_CONTRACTS.values() if contract[2] == VOLNOGRAD_STATES
        ]
        self.assertEqual({contract[0] for contract in solar}, {"SOL", "SRA", "CSL"})
        self.assertEqual({contract[0] for contract in volnograd}, {"VLA", "EBA", "TGD"})
        self.assertEqual(len(solar), 3)
        self.assertEqual(len(volnograd), 3)

    def test_terminal_winners_are_exact_owned_controlled_postconditions(self) -> None:
        issues = validate_terminal_outcomes()
        self.assertEqual(issues, [], issue_report(issues))

    def test_outcome_recorder_is_one_day_event_driven_not_polling(self) -> None:
        issues = validate_bounded_outcome_hook()
        self.assertEqual(issues, [], issue_report(issues))


class PeacefulAllianceTests(unittest.TestCase):
    def test_sol_and_vla_accept_through_delayed_events_without_offer_side_effects(self) -> None:
        issues = validate_peaceful_invitations()
        self.assertEqual(issues, [], issue_report(issues))

    def test_verified_showdown_joins_four_existing_war_edges(self) -> None:
        issues = validate_showdown_allies()
        self.assertEqual(issues, [], issue_report(issues))


class SolarInterventionTests(unittest.TestCase):
    def test_intervention_has_exact_reachable_edges_and_verified_restoration(self) -> None:
        self.assertEqual(VAD_SOLAR_BORDER_PAIRS, ((81, 307), (110, 198), (110, 307)))
        issues = validate_vad_intervention_and_restoration()
        self.assertEqual(issues, [], issue_report(issues))

    def test_vad_solar_route_does_not_serialize_the_central_wave(self) -> None:
        issues = validate_vad_egc_route_priority()
        self.assertEqual(issues, [], issue_report(issues))

    def test_startup_cleanup_enters_vad_country_scope(self) -> None:
        issues = validate_vad_intervention_and_restoration()
        self.assertNotIn(
            "VAD intervention startup cleanup must enter exactly one explicit VAD country scope",
            issues,
            issue_report(issues),
        )

    def test_wkr_counter_uses_exact_edges_and_only_accelerates_phase_four(self) -> None:
        self.assertEqual(len(WKR_SOLAR_BORDER_PAIRS), 8)
        self.assertEqual(
            set(WKR_SOLAR_BORDER_PAIRS),
            {
                (79, 310),
                (308, 307),
                (309, 307),
                (309, 310),
                (327, 310),
                (81, 307),
                (110, 198),
                (110, 307),
            },
        )
        issues = validate_counter_intervention()
        self.assertEqual(issues, [], issue_report(issues))

    def test_wkr_solyarino_intervention_and_protectorate_are_bounded(self) -> None:
        self.assertEqual(SOLAR_STATES, (76, 104, 198, 307, 310))
        issues = validate_wkr_solyarino_intervention()
        self.assertEqual(issues, [], issue_report(issues))

    def test_gordon_is_carried_across_annex_and_returned_before_promotion(self) -> None:
        on_capitulation = named_block(read(DIPLOMACY_ON_ACTIONS), "on_capitulation")
        settlement = next(
            block
            for block in named_blocks(on_capitulation, "if")
            if "ADISCORD_vorkerland_wkr_solyarino_intervention_active" in block
            and "set_global_flag = skip_default_capitulation" in block
            and "tag = WKR" in block
        )
        settlement = compact(settlement)
        self.assertLess(
            settlement.index("target_country = WKR"),
            settlement.index("annex_country = { target = ROOT transfer_troops = no }"),
        )

        effects = read(DIPLOMACY_EFFECTS)
        materialize = compact(named_block(effects, MATERIALIZE_WKR_PROTECTORATE))
        self.assertLess(
            materialize.index("target_country = WKR"),
            materialize.index("target_country = SOL"),
        )
        self.assertLess(
            materialize.index("target_country = SOL"),
            materialize.index(
                "country_event = { id = ADISCORD_vorkerland_diplomacy.15 days = 1 }"
            ),
        )

        verify = compact(named_block(effects, VERIFY_WKR_PROTECTORATE))
        self.assertLess(
            verify.index(
                "has_country_flag = ADISCORD_vorkerland_wkr_solyarino_gordon_returned"
            ),
            verify.index("promote_character = { character = WRK_Richard_Gordon"),
        )


class IndependentCorePackageTests(unittest.TestCase):
    def test_manifest_is_disjoint_complete_and_excludes_live_allies(self) -> None:
        states = [state for package in CORE_PACKAGES.values() for state in package]
        self.assertEqual(len(CORE_PACKAGES), 7)
        self.assertEqual(len(states), len(set(states)))
        self.assertEqual(frozenset(states), HISTORICAL_WRK_VAD_STATES)
        self.assertFalse(set(states) & LIVE_ALLY_OR_FOREIGN_STATES)

    def test_public_decisions_are_independent_explicit_packages(self) -> None:
        issues = validate_core_packages()
        self.assertEqual(issues, [], issue_report(issues))


class IntegratedDiplomacyContractTests(unittest.TestCase):
    def test_integrated_contract(self) -> None:
        issues = collect_issues()
        self.assertEqual(issues, [], issue_report(issues))


if __name__ == "__main__":
    unittest.main()
