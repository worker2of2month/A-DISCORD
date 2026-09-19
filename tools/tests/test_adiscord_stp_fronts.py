"""Static front-allocation contracts; native AI movement needs an in-game check."""
from __future__ import annotations
from tools.lib.on_actions import country_on_actions_entries

import re
import unittest
from pathlib import Path

from tools.tests.test_adiscord_generic_wartime_fronts import named_block, named_blocks


ROOT = Path(__file__).resolve().parents[2]
AI_PATH = ROOT / "common/ai_strategy/ADISCORD_STP_civil_war.txt"
NEUTRAL = "STS_cw_deprioritize_neutral_borders"
RESERVE = "STS_cw_defend_abilia"


def compact(source: str) -> str:
    return " ".join(re.sub(r"(?m)#.*$", "", source).split())


class ShabratFrontTests(unittest.TestCase):
    def setUp(self) -> None:
        self.source = re.sub(r"(?m)#.*$", "", AI_PATH.read_text(encoding="utf-8"))

    def profile(self, name: str) -> str:
        result = named_block(self.source, name)
        self.assertTrue(result, f"missing AI profile: {name}")
        return result

    def test_neutral_demand_has_one_shared_owner(self) -> None:
        self.assertFalse(named_block(self.source, NEUTRAL))
        shared = (ROOT / "common/ai_strategy/default.txt").read_text(encoding="utf-8")
        profile = named_block(shared, "ADISCORD_wartime_neutral_borders")
        self.assertTrue(profile)
        self.assertIn("ADISCORD_ai_front_has_prewar_threat = no", profile)
        self.assertNotIn("original_tag", profile)
        self.assertNotIn("enemies^num", profile)

    def test_reserve_requires_a_live_civil_war_and_control_of_abilia(self) -> None:
        profile = self.profile(RESERVE)
        self.assertEqual(compact(named_block(profile, "allowed")),
                         "allowed = { original_tag = STS }")
        enable = named_block(profile, "enable")
        nod = named_block(enable, "NOD")
        self.assertTrue(nod, "reserve must track the external threat")
        self.assertEqual(compact(enable.replace(nod, "")),
                         "enable = { is_ai = yes has_capitulated = no "
                         "has_global_flag = STP_cw_started "
                         "NOT = { has_global_flag = STP_cw_union_wars_finished } "
                         "has_war_with = STP controls_state = 1 }")

    def test_reserve_requires_approved_eligible_intervention_and_peace_with_nod(self) -> None:
        enable = named_block(self.profile(RESERVE), "enable")
        self.assertEqual(compact(named_block(enable, "NOD")),
                         "NOD = { NOD_cw_intervention_possible = yes "
                         "has_country_flag = NOD_cw_intervention_approved "
                         "NOT = { has_war_with = STS } }")

    def test_reserve_is_five_percent_in_abilia(self) -> None:
        strategies = named_blocks(self.profile(RESERVE), "ai_strategy")
        self.assertEqual(len(strategies), 1)
        self.assertEqual(compact(strategies[0]),
                         "ai_strategy = { type = put_unit_buffers ratio = 0.05 "
                         "states = { 1 } subtract_invasions_from_need = yes "
                         "subtract_fronts_from_need = no }")

    def test_shabrat_profiles_cannot_stack_additional_buffers(self) -> None:
        buffers = []
        for name in re.findall(r"(?m)^(\w+)\s*=\s*\{", self.source):
            profile = self.profile(name)
            allowed = named_block(profile, "allowed")
            if not re.search(r"\boriginal_tag\s*=\s*STS\b", allowed):
                continue
            buffers.extend(name for strategy in named_blocks(profile, "ai_strategy")
                           if re.search(r"\btype\s*=\s*put_unit_buffers\b", strategy))
        self.assertEqual(buffers, [RESERVE])

    def test_temporary_profiles_abort_after_peace_or_threat_cancellation(self) -> None:
        for name in (RESERVE, "STS_prepare_against_NOD"):
            with self.subTest(profile=name):
                self.assertIn("abort_when_not_enabled = yes", self.profile(name))

    def test_actual_external_fronts_do_not_depend_on_the_party_war(self) -> None:
        for name, enemy, enable in (
                ("STP_cw_front_against_nod", "NOD", "enable = { has_war_with = NOD }"),
                ("STS_shabrat_val_front", "VAL", "enable = { is_ai = yes has_war_with = VAL }")):
            with self.subTest(enemy=enemy):
                profile = self.profile(name)
                self.assertEqual(compact(named_block(profile, "enable")), enable)
                self.assertIn("abort_when_not_enabled = yes", profile)
                self.assertRegex(profile, rf"type = front_unit_request tag = {enemy} value = [1-9]\d*")
                self.assertIn(f"type = front_control tag = {enemy}", profile)

    def test_party_front_requests_are_not_inflated_to_mask_neutral_demand(self) -> None:
        for name, demand in (("STS_cw_front_against_stp", 100),
                             ("STS_shabrat_civil_war_army", 120)):
            with self.subTest(profile=name):
                profile = self.profile(name)
                self.assertIn(f"type = front_unit_request tag = STP value = {demand}", profile)
                self.assertIn("execution_type = rush_weak", profile)

    def test_gameplay_source_is_utf8_without_bom_and_has_unique_profiles(self) -> None:
        self.assertFalse(AI_PATH.read_bytes().startswith(b"\xef\xbb\xbf"))
        names = re.findall(r"(?m)^(\w+)\s*=\s*\{", self.source)
        self.assertEqual(len(names), len(set(names)))
        for name in names:
            self.profile(name)


class CivilWarVictorFallbackTests(unittest.TestCase):
    def setUp(self):
        from tools.tests.test_adiscord_stp_preparation import entries, block, walk
        hooks = block(country_on_actions_entries("common/on_actions/02_ADISCORD_STP_on_actions.txt", 'stelander'), "on_actions")
        immediate = block(block(hooks, "on_capitulation_immediate"), "effect")
        self.block = block
        candidates = [e.value for e in walk(immediate) if e.key == "if"
                      and any(x.key == "else_if" for x in e.value)
                      and "STP_cw_capitulation_occupier" in str(block(e.value, "limit"))]
        self.assertEqual(len(candidates), 1)
        self.fallback = candidates[0]

    def outcome(self, loser, victor, enemies, flags=(), snapshot=0, exists=True):
        from tools.tests.test_adiscord_stp_preparation import scalar
        def matches(items, scope):
            def one(e):
                if e.key == "OR":
                    return any(one(x) for x in e.value)
                if e.key == "AND":
                    return matches(e.value, scope)
                if e.key == "NOT":
                    return not matches(e.value, scope)
                if e.key in ("ROOT", "FROM"):
                    return matches(e.value, loser if e.key == "ROOT" else victor)
                if e.key == "any_enemy_country":
                    return any(matches(e.value, enemy) for enemy in enemies)
                if e.key == "tag":
                    return scope == e.value
                if e.key == "exists":
                    return exists
                if e.key == "has_capitulated":
                    return e.value == "no"
                if e.key == "has_war_with":
                    return victor in enemies
                if e.key == "has_country_flag":
                    return (scope, e.value) in flags
                if e.key == "check_variable":
                    self.assertEqual(scalar(e.value, "var"), "STP_cw_capitulation_occupier")
                    return snapshot == float(scalar(e.value, "value"))
                raise AssertionError(f"Unsupported test predicate: {e.key}")
            return all(one(e) for e in items)
        if not matches(self.block(self.fallback, "limit"), loser):
            return snapshot
        for branch in self.fallback:
            if branch.key in ("if", "else_if") and matches(self.block(branch.value, "limit"), loser):
                return int(scalar(self.block(self.block(branch.value, "ROOT"), "set_variable"), "value"))
        return snapshot

    def test_isolated_fronts_settle_without_original_capital_capture(self):
        cases = (("STS", "STP", 1), ("STP", "STS", 2),
                 ("SRP", "VAL", 5), ("VAL", "SRP", 3))
        for loser, victor, code in cases:
            with self.subTest(loser=loser):
                self.assertEqual(self.outcome(loser, victor, [victor],
                    flags={("VAL", "VAL_cw_entered")}), code)

    def test_nod_participation_is_required_and_has_distinct_credit(self):
        flags = {("NOD", "NOD_cw_entered")}
        self.assertEqual(self.outcome("STS", "STP", ["STP", "NOD"], flags), 1)
        self.assertEqual(self.outcome("STS", "NOD", ["STP", "NOD"], flags), 4)
        self.assertEqual(self.outcome("STS", "NOD", ["STP", "NOD"]), 0)

    def test_conflicting_war_or_snapshot_never_gets_overwritten(self):
        self.assertEqual(self.outcome("STS", "STP", ["STP", "VAL"]), 0)
        self.assertEqual(self.outcome("SRP", "VAL", ["VAL", "STS"],
                                    {("VAL", "VAL_cw_entered")}), 0)
        self.assertEqual(self.outcome("STS", "STP", ["STP"], snapshot=5), 5)
        self.assertEqual(self.outcome("STS", "STP", [], exists=True), 0)
        self.assertEqual(self.outcome("STS", "STP", ["STP"], exists=False), 0)


if __name__ == "__main__":
    unittest.main()
