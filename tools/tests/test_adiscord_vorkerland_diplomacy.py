from __future__ import annotations

import unittest

from tools.validators.validate_adiscord_division_templates import parse_clausewitz
from tools.lib.paths import source_section
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


    def test_late_front_retains_actual_coalition_but_reopens_after_dissolution(self) -> None:
        effects = read(DIPLOMACY_EFFECTS)
        helper = named_block(effects, "ADISCORD_vorkerland_leave_inherited_faction")
        detach_limits = [next(child.value for child in branch.value if child.key == "limit")
                         for branch in parse_clausewitz(helper)[0].value
                         if branch.key in ("if", "else_if")]
        auxiliary = "ADISCORD_vorkerland_regional_auxiliary"
        factions = {"WKR": "WKR", "VHV": "WKR", "TVA": None, "VAD": None}
        flags = {"VHV": {auxiliary}}
        root = "TVA"

        def evaluate(items, scope, previous=None):
            def matches(entry):
                key, value = entry.key, entry.value
                if key == "AND":
                    return evaluate(value, scope, previous)
                if key == "NOT":
                    return not any(evaluate([child], scope, previous) for child in value)
                if key == "OR":
                    return any(evaluate([child], scope, previous) for child in value)
                if key == "faction_leader":
                    leader = factions.get(scope)
                    return bool(leader) and evaluate(value, leader, scope)
                if key == "any_allied_country":
                    return any(tag != scope and faction and faction == factions.get(scope)
                               and evaluate(value, tag, scope) for tag, faction in factions.items())
                if key in factions and isinstance(value, list):
                    return evaluate(value, key, scope)
                if key == "is_in_faction_with":
                    target = {"ROOT": root, "PREV": previous}.get(value, value)
                    return bool(factions.get(scope)) and factions.get(scope) == factions.get(target)
                if key == "tag":
                    return scope == value
                if key == "has_country_flag":
                    return value in flags.get(scope, set())
                if key == "has_global_flag":
                    return True
                if key == "ADISCORD_vorkerland_is_main_claimant":
                    return (scope in ("WKR", "VAD", "TVA")) == (value == "yes")
                if key in ("is_in_faction", "is_faction_leader", "exists", "is_subject", "has_capitulated"):
                    actual = {"is_in_faction": bool(factions.get(scope)),
                              "is_faction_leader": factions.get(scope) == scope,
                              "exists": scope in factions, "is_subject": False,
                              "has_capitulated": False}[key]
                    return actual == (value == "yes")
                if key == "has_war_with":
                    return False
                raise AssertionError(f"Unsupported coalition predicate: {key}")
            return all(matches(entry) for entry in items)

        def detaches(scope):
            return any(evaluate(limit, scope) for limit in detach_limits)

        remaining = named_block(effects, "ADISCORD_vorkerland_attempt_remaining_central_fronts")
        front = next(branch for branch in named_blocks(remaining, "if")
                     if "declare_war_on = { target = VHV type = annex_everything }" in compact(branch)
                     and branch.count("declare_war_on") == 1)
        front_limit = parse_clausewitz(named_block(front, "limit"))[0].value
        self.assertTrue(evaluate(front_limit, "TVA"))
        self.assertFalse(detaches("VHV"), "a new attacker must not remove the auxiliary")
        self.assertFalse(detaches("WKR"), "a new offensive must not dismantle its own coalition")
        root = "WKR"
        self.assertFalse(evaluate(front_limit, "WKR"), "the host cannot attack its own auxiliary")
        factions["VHV"] = None
        self.assertTrue(evaluate(front_limit, "WKR"), "a historical marker cannot protect a former ally")
        self.assertTrue(detaches("WKR"), "the empty coalition no longer needs protection")
        factions["VHV"] = "OLD"
        factions["OLD"] = "OLD"
        self.assertTrue(detaches("VHV"), "an inherited unrelated faction remains detachable")
        terminal = named_block(effects, "ADISCORD_vorkerland_prepare_claimants_for_formation")
        self.assertNotIn("ADISCORD_vorkerland_leave_inherited_faction", terminal)
        self.assertEqual(terminal.count("dismantle_faction = yes"), 3)
        events = read(DIPLOMACY_EFFECTS.parents[2] / "events/ADISCORD_vorkerland_events.txt")
        for event_id, recipient, host, pending in (
            (2, "SOL", "VAD", "vad_sol"), (3, "VLA", "WKR", "wkr_vla"),
        ):
            invitation = event_block(events, f"ADISCORD_vorkerland_diplomacy.{event_id}")
            option = named_block(invitation, "option")
            option_limit = parse_clausewitz(named_block(option, "trigger"))[0].value
            root = recipient
            flags[host] = {f"ADISCORD_vorkerland_{pending}_invitation_pending"}
            flags[recipient] = {auxiliary}
            other = "WKR" if host == "VAD" else "VAD"
            for leader, expected in ((None, True), (host, True), (other, False), ("OLD", True)):
                factions.update({host: host, other: other, recipient: leader})
                self.assertEqual(evaluate(option_limit, recipient), expected, (recipient, leader))
        hooks = read(DIPLOMACY_EFFECTS.parents[2] / "common/on_actions/01_ADISCORD_vorkerland_collapse_on_actions.txt")
        war_hook = named_block(hooks, "on_war_relation_added")
        for host, enemy in (("ROOT", "FROM"), ("FROM", "ROOT")):
            host_scope = named_block(war_hook, host)
            self.assertIn("ADISCORD_vorkerland_is_main_claimant = yes", named_block(host_scope, "limit"))
            allies = named_block(host_scope, "every_allied_country")
            self.assertIn("is_in_faction_with = PREV", named_block(allies, "limit"))
            self.assertIn(f"NOT = {{ has_war_with = {enemy} }}", named_block(allies, "limit"))
            self.assertIn("country_event = { id = ADISCORD_vorkerland_collapse.93 days = 1 }", allies)
        self.assertNotIn("every_country", war_hook)
        membership = named_block(effects, "ADISCORD_vorkerland_verify_coalition_membership")
        self.assertIn("NOT = { any_enemy_country = { NOT = { has_war_with = ROOT } } }",
                      compact(named_block(named_block(membership, "if"), "limit")))


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

        effects = source_section(read(DIPLOMACY_EFFECTS), 'diplomacy_effects')
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
