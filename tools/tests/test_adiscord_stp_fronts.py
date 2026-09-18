"""Static front-allocation contracts; native AI movement needs an in-game check."""
from __future__ import annotations

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

    def test_neutral_policy_is_ai_sts_only(self) -> None:
        profile = self.profile(NEUTRAL)
        self.assertEqual(compact(named_block(profile, "allowed")),
                         "allowed = { original_tag = STS }")
        self.assertEqual(compact(named_block(profile, "enable")),
                         "enable = { is_ai = yes has_capitulated = no "
                         "has_global_flag = STP_cw_started "
                         "NOT = { has_global_flag = STP_cw_union_wars_finished } "
                         "has_war_with = STP }")

    def test_neutral_filter_excludes_every_actual_enemy(self) -> None:
        profile = self.profile(NEUTRAL)
        requests = named_blocks(profile, "ai_strategy")
        self.assertEqual(len(requests), 1)
        # FROM must remain the allocating country. A fixed tag, a peace flag,
        # or an enemy-count gate would fail when NOD/VAL enters the same war.
        self.assertEqual(compact(named_block(requests[0], "country_trigger")),
                         "country_trigger = { NOT = { has_war_with = FROM } }")
        self.assertNotRegex(requests[0], r"\b(?:tag|id|state|area|strategic_region)\s*=")

    def test_neutral_policy_changes_demand_not_orders_or_diplomacy(self) -> None:
        profile = self.profile(NEUTRAL)
        self.assertEqual(re.findall(r"\btype\s*=\s*(\w+)", profile),
                         ["front_unit_request"])
        self.assertEqual(re.findall(r"\bvalue\s*=\s*(-?\d+)", profile), ["-100"])
        self.assertNotIn("enemies^num", profile)
        self.assertNotIn("add_ai_strategy", profile)

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
        for name in (NEUTRAL, RESERVE):
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


if __name__ == "__main__":
    unittest.main()
