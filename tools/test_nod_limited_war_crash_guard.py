from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EFFECTS = ROOT / "common/scripted_effects/ADISCORD_STP_VAL_crisis_war_effects.txt"


def read_effects() -> str:
    return EFFECTS.read_text(encoding="utf-8-sig")


def named_block(text: str, name: str) -> str:
    match = re.search(rf"(?m)^\s*{re.escape(name)}\s*=\s*\{{", text)
    if not match:
        return ""
    start = match.start()
    opening = text.find("{", match.start())
    depth = 0
    for index in range(opening, len(text)):
        if text[index] == "{":
            depth += 1
        elif text[index] == "}":
            depth -= 1
            if depth == 0:
                return text[start : index + 1]
    return ""


def compact(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


class NodLimitedWarCrashGuardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.effects = read_effects()

    def test_global_event_targets_are_cleared_only_when_defined(self) -> None:
        cleanup = compact(named_block(self.effects, "NOD_clear_limited_conflict_state"))
        for target in (
            "NOD_limited_war_nod",
            "NOD_limited_war_target_country",
        ):
            self.assertIn(
                f"limit = {{ has_event_target = {target} }} "
                f"clear_global_event_target = {target}",
                cleanup,
            )
            self.assertEqual(cleanup.count(f"clear_global_event_target = {target}"), 1)

    def test_white_peace_blocks_reentrant_on_peace_cleanup(self) -> None:
        addressed = named_block(self.effects, "NOD_addressed_limited_white_peace")
        set_guard = addressed.find("set_country_flag = NOD_limited_resolution_in_progress")
        white_peace_match = re.search(r"(?m)^\s*white_peace\s*=\s*\{", addressed)
        self.assertIsNotNone(white_peace_match)
        white_peace = white_peace_match.start()
        clear_guard = addressed.find("clr_country_flag = NOD_limited_resolution_in_progress")
        self.assertGreaterEqual(set_guard, 0)
        self.assertGreater(white_peace, set_guard)
        self.assertGreater(clear_guard, white_peace)
        self.assertEqual(len(re.findall(r"(?m)^\s*white_peace\s*=\s*\{", addressed)), 1)

        integrity = compact(named_block(self.effects, "NOD_check_limited_war_integrity"))
        self.assertIn(
            "NOT = { has_country_flag = NOD_limited_resolution_in_progress }",
            integrity,
        )

    def test_emergency_resolution_uses_the_guarded_white_peace_path(self) -> None:
        emergency = named_block(self.effects, "NOD_emergency_limited_white_peace")
        self.assertIn("NOD_addressed_limited_white_peace = yes", emergency)
        self.assertIn("NOD_clear_limited_conflict_state = yes", emergency)
        self.assertIsNone(re.search(r"(?m)^\s*white_peace\s*=\s*\{", emergency))


if __name__ == "__main__":
    unittest.main()
