from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
AI_PATH = ROOT / "common/ai_strategy/ADISCORD_STP_civil_war.txt"


def named_block(source: str, name: str) -> str:
    match = re.search(rf"(?m)^\s*{re.escape(name)}\s*=\s*\{{", source)
    if not match:
        return ""
    start = source.find("{", match.start())
    depth = 0
    for index in range(start, len(source)):
        if source[index] == "{":
            depth += 1
        elif source[index] == "}":
            depth -= 1
            if depth == 0:
                return source[match.start() : index + 1]
    raise AssertionError(f"unclosed block: {name}")


class NodrulNorthernFrontTests(unittest.TestCase):
    def test_northern_war_drops_neutral_besjaysk_front_demand(self) -> None:
        source = AI_PATH.read_text(encoding="utf-8-sig")
        block = named_block(source, "NOD_cw_northern_deprioritize_besjaysk")

        self.assertTrue(block, "missing northern-war Besjaysk front suppression")
        self.assertIn("allowed = { original_tag = NOD }", block)
        for enemy in ("YPR", "COF", "TFF"):
            self.assertIn(f"has_war_with = {enemy}", block)
        self.assertRegex(block, r"NOT\s*=\s*\{\s*has_war_with\s*=\s*BJK\s*\}")
        self.assertIn("abort_when_not_enabled = yes", block)
        self.assertIn("type = front_unit_request tag = BJK value = -100", block)

        # `ignore` is a diplomacy strategy; it must not be used as a fake troop-allocation fix.
        self.assertNotIn("type = ignore id = BJK", block)

    def test_northern_offensive_does_not_use_diplomatic_ignore_for_fronts(self) -> None:
        source = AI_PATH.read_text(encoding="utf-8-sig")
        block = named_block(source, "NOD_cw_northern_offensive_army")

        self.assertTrue(block)
        self.assertIn("type = dont_defend_ally_borders value = 1", block)
        for tag in ("STP", "STS", "SRP", "VAL"):
            self.assertNotIn(f"type = ignore id = {tag}", block)

    def test_northern_common_profile_reserves_only_five_percent_and_concentrates(self) -> None:
        source = AI_PATH.read_text(encoding="utf-8-sig")
        block = named_block(source, "NOD_cw_northern_offensive_army")

        self.assertIn("type = role_ratio id = garrison value = -100", block)
        self.assertIn("type = role_ratio id = militias value = -100", block)
        self.assertIn("type = force_concentration_factor value = 80", block)
        self.assertNotIn("type = put_unit_buffers", block)

        # Real front allocation belongs to enemy-specific blocks so a dead/peaceful
        # coalition member cannot keep phantom demand in the planner.
        self.assertNotIn("type = front_unit_request tag = YPR", block)
        self.assertNotIn("type = front_unit_request tag = COF", block)
        self.assertNotIn("type = front_unit_request tag = TFF", block)
        self.assertNotIn("type = front_control tag = YPR", block)
        self.assertNotIn("type = front_control tag = COF", block)
        self.assertNotIn("type = front_control tag = TFF", block)


    def test_nodrul_wartime_home_buffer_is_one_five_percent_reserve(self) -> None:
        source = AI_PATH.read_text(encoding="utf-8-sig")
        block = named_block(source, "NOD_cw_wartime_home_buffer")

        self.assertTrue(block, "missing shared NOD wartime reserve")
        self.assertIn("allowed = { original_tag = NOD }", block)
        for enemy in ("YPR", "COF", "TFF", "STS"):
            self.assertIn(f"has_war_with = {enemy}", block)
        self.assertIn("abort_when_not_enabled = yes", block)
        self.assertRegex(block, r"(?s)type\s*=\s*put_unit_buffers.*?ratio\s*=\s*0\.05")
        self.assertIn("states = { 30 }", block)

    def test_each_active_northern_enemy_has_its_own_high_priority_front(self) -> None:
        source = AI_PATH.read_text(encoding="utf-8-sig")
        enemies = ("YPR", "COF", "TFF")

        for enemy in enemies:
            with self.subTest(enemy=enemy):
                block = named_block(source, f"NOD_cw_northern_front_{enemy.lower()}")
                self.assertTrue(block, f"missing dedicated NOD front block for {enemy}")
                self.assertIn("allowed = { original_tag = NOD }", block)
                self.assertIn(f"enable = {{ has_war_with = {enemy} }}", block)
                self.assertIn("abort_when_not_enabled = yes", block)
                self.assertIn(
                    f"type = front_unit_request tag = {enemy} value = 220",
                    block,
                )
                self.assertIn(
                    f"type = front_control tag = {enemy} ratio = 0.01 priority = 1800 "
                    "ordertype = front execution_type = rush_weak execute_order = yes "
                    "manual_attack = no",
                    block,
                )
                self.assertIn(f"type = conquer id = {enemy} value = 250", block)
                for other in enemies:
                    if other == enemy:
                        continue
                    self.assertNotIn(f"tag = {other}", block)
                    self.assertNotIn(f"id = {other}", block)

    def test_stelander_intervention_uses_same_field_army_concentration_contract(self) -> None:
        source = AI_PATH.read_text(encoding="utf-8-sig")
        block = named_block(source, "NOD_cw_stelander_intervention_army")

        self.assertIn("type = role_ratio id = garrison value = -100", block)
        self.assertIn("type = role_ratio id = militias value = -100", block)
        self.assertIn("type = force_concentration_factor value = 80", block)
        self.assertNotIn("type = put_unit_buffers", block)
        self.assertIn("type = front_unit_request tag = STS value = 220", block)
        self.assertIn(
            "type = front_control tag = STS ratio = 0.01 priority = 1800 "
            "ordertype = front execution_type = rush_weak execute_order = yes "
            "manual_attack = no",
            block,
        )


if __name__ == "__main__":
    unittest.main()
