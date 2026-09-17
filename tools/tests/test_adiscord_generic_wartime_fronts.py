from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
AI_PATH = ROOT / "common/ai_strategy/default.txt"


def named_block(source: str, name: str) -> str:
    match = re.search(rf"(?m)^\s*{re.escape(name)}\s*=\s*\{{", source)
    if match is None:
        return ""
    opening = source.find("{", match.start())
    depth = 0
    for index in range(opening, len(source)):
        if source[index] == "{":
            depth += 1
        elif source[index] == "}":
            depth -= 1
            if depth == 0:
                return source[match.start() : index + 1]
    raise AssertionError(f"unterminated block: {name}")


def named_blocks(source: str, name: str) -> list[str]:
    blocks: list[str] = []
    pattern = re.compile(rf"(?m)^\s*{re.escape(name)}\s*=\s*\{{")
    position = 0
    while True:
        match = pattern.search(source, position)
        if match is None:
            return blocks
        opening = source.find("{", match.start())
        depth = 0
        for index in range(opening, len(source)):
            if source[index] == "{":
                depth += 1
            elif source[index] == "}":
                depth -= 1
                if depth == 0:
                    blocks.append(source[match.start() : index + 1])
                    position = index + 1
                    break
        else:
            raise AssertionError(f"unterminated block: {name}")


class GenericWartimeFrontTests(unittest.TestCase):
    def test_single_enemy_war_gets_a_strong_dynamic_front_request(self) -> None:
        source = AI_PATH.read_text(encoding="utf-8-sig")
        profile = named_block(source, "ADISCORD_single_enemy_front_concentration")
        self.assertTrue(profile, "missing generic one-enemy wartime front policy")

        enable = named_block(profile, "enable")
        self.assertIn("is_ai = yes", enable)
        self.assertIn("has_war = yes", enable)
        self.assertRegex(enable, r"check_variable\s*=\s*\{\s*enemies\^num\s*=\s*1\s*\}")
        self.assertIn("abort_when_not_enabled = yes", profile)

        requests = [
            block
            for block in named_blocks(profile, "ai_strategy")
            if re.search(r"\btype\s*=\s*front_unit_request\b", block)
        ]
        self.assertEqual(len(requests), 1)
        request = requests[0]
        country_trigger = named_block(request, "country_trigger")
        self.assertIn("has_war_with = FROM", country_trigger)
        self.assertIn("has_capitulated = no", country_trigger)
        self.assertRegex(request, r"\bvalue\s*=\s*300\b")

    def test_generic_fallback_changes_allocation_not_campaign_behavior(self) -> None:
        source = AI_PATH.read_text(encoding="utf-8-sig")
        profile = named_block(source, "ADISCORD_single_enemy_front_concentration")
        self.assertTrue(profile)
        self.assertNotIn("type = front_control", profile)
        self.assertNotIn("type = dont_defend_ally_borders", profile)
        self.assertNotIn("type = put_unit_buffers", profile)
        self.assertNotIn("type = role_ratio id = garrison", profile)


if __name__ == "__main__":
    unittest.main()
