"""Regression coverage for Stelander postwar focus unlocks."""
from tools.lib.on_actions import read_country_on_actions
from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[2]
TRIGGERS = ROOT / "common/scripted_triggers/ADISCORD_STP_scripted_triggers.txt"
RECOVERY = ROOT / "common/on_actions/02_ADISCORD_STP_on_actions.txt"
RU_LOC = ROOT / "localisation/russian/ADISCORD_STP_l_russian.yml"
EN_LOC = ROOT / "localisation/replace/ADISCORD_STP_postwar_focus_l_english.yml"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


def named_block(source: str, name: str) -> str:
    match = re.search(rf"(?m)^\s*{re.escape(name)}\s*=\s*\{{", source)
    if match is None:
        raise AssertionError(f"missing block: {name}")
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


class StelanderPostwarUnlockRegressionTests(unittest.TestCase):
    def test_reconstruction_gate_does_not_depend_on_mountain_republics(self) -> None:
        gate = named_block(read(TRIGGERS), "STP_pw_can_reconstruct")
        self.assertIn("OR = { tag = STP tag = STS }", gate)
        self.assertIn("has_country_flag = STP_cw_won_union_battle", gate)
        self.assertIn("has_country_flag = STP_cw_postwar", gate)
        self.assertNotIn("SRP", gate)

    def test_deferred_white_peace_gets_a_self_healing_retry(self) -> None:
        recovery = read_country_on_actions(RECOVERY, 'stelander')
        self.assertIsNone(re.search(r"(?m)^\\s*on_daily\\s*=", recovery))
        for hook in ("on_daily_STP", "on_daily_STS"):
            daily = named_block(recovery, hook)
            for token in (
                "has_global_flag = STP_cw_started",
                "NOT = { has_global_flag = STP_cw_union_wars_finished }",
                "has_country_flag = STP_cw_won_union_battle",
                "has_country_flag = STP_cw_postwar",
                "STP_cw_check_union_wars_finished = yes",
            ):
                self.assertIn(token, daily)
            self.assertNotIn("SRP", daily)

    def test_budget_tooltip_marks_the_republic_condition_as_a_separate_alternative(self) -> None:
        ru = read(RU_LOC)
        en = read(EN_LOC)
        self.assertIn("альтернативные условия для разных стран", ru)
        self.assertIn("не блокируют послевоенное восстановление", ru)
        self.assertIn("alternative country-specific conditions", en)
        self.assertIn("do not block", en)


if __name__ == "__main__":
    unittest.main()
