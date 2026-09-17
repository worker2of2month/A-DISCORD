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
    def test_northern_war_ignores_peacetime_besjaysk_border(self) -> None:
        source = AI_PATH.read_text(encoding="utf-8-sig")
        block = named_block(source, "NOD_cw_northern_ignore_besjaysk")

        self.assertTrue(block, "missing northern-war Besjaysk border suppression")
        self.assertIn("allowed = { original_tag = NOD }", block)
        for enemy in ("YPR", "COF", "TFF"):
            self.assertIn(f"has_war_with = {enemy}", block)
        self.assertRegex(block, r"NOT\s*=\s*\{\s*has_war_with\s*=\s*BJK\s*\}")
        self.assertIn("abort_when_not_enabled = yes", block)
        self.assertIn("type = ignore id = BJK value = 1000", block)


if __name__ == "__main__":
    unittest.main()
