from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FOCUS_PATH = ROOT / "common/national_focus/ADISCORD_national_focus_VAL.txt"


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8-sig")


def focus_block(source: str, focus_id: str) -> str:
    marker = f"id = {focus_id}"
    pos = source.index(marker)
    start = source.rfind("focus = {", 0, pos)
    opening = source.index("{", start)
    depth = 0
    quoted = False
    escaped = False
    for index in range(opening, len(source)):
        char = source[index]
        if quoted:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                quoted = False
            continue
        if char == '"':
            quoted = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return source[start:index + 1]
    raise AssertionError(f"unterminated focus: {focus_id}")


def scalar(block: str, key: str) -> int:
    match = re.search(rf"(?m)^\s*{re.escape(key)}\s*=\s*(-?\d+)\s*$", block)
    if match is None:
        raise AssertionError(f"missing {key}")
    return int(match.group(1))


class KefreytFocusClarityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = FOCUS_PATH.read_text(encoding="utf-8")
        cls.blocks = {
            focus_id: focus_block(cls.source, focus_id)
            for focus_id in (
                "VAL_Stelander_Crisis_Opens",
                "VAL_Arms_For_The_Burning",
                "VAL_Keep_The_Arsenals",
                "VAL_Seize_The_Northern_Passes",
                "VAL_The_Steel_Contract",
                "VAL_Contracts_Outlive_Kings",
                "VAL_frontier_conference",
                "VAL_frontier_security_plan",
                "VAL_frontier_treaty_offices",
                "VAL_Return_Southern_Tsaygen",
                "VAL_frontier_return_irem",
                "VAL_Southern_Expansion",
                "VAL_Eastern_Expansion",
                "VAL_Bezhaysk_Operation",
                "VAL_Reopen_Trade_Routes",
                "VAL_Return_To_World_Market",
            )
        }

    def test_story_tree_has_clear_prewar_and_postwar_layers(self) -> None:
        crisis_y = scalar(self.blocks["VAL_Stelander_Crisis_Opens"], "y")
        steel_y = scalar(self.blocks["VAL_The_Steel_Contract"], "y")
        state_y = scalar(self.blocks["VAL_Contracts_Outlive_Kings"], "y")
        conference_y = scalar(self.blocks["VAL_frontier_conference"], "y")
        continuation = (
            "VAL_Return_Southern_Tsaygen",
            "VAL_Bezhaysk_Operation",
            "VAL_frontier_return_irem",
            "VAL_Southern_Expansion",
            "VAL_Eastern_Expansion",
            "VAL_Reopen_Trade_Routes",
            "VAL_Return_To_World_Market",
        )
        self.assertLess(crisis_y, steel_y)
        self.assertLess(steel_y, state_y)
        self.assertLessEqual(state_y, conference_y)
        for focus_id in continuation:
            with self.subTest(focus=focus_id):
                self.assertGreaterEqual(scalar(self.blocks[focus_id], "y"), 21)

    def test_stelander_choice_is_visually_grouped(self) -> None:
        self.assertEqual(
            {
                (scalar(self.blocks["VAL_Arms_For_The_Burning"], "x"), scalar(self.blocks["VAL_Arms_For_The_Burning"], "y")),
                (scalar(self.blocks["VAL_Keep_The_Arsenals"], "x"), scalar(self.blocks["VAL_Keep_The_Arsenals"], "y")),
                (scalar(self.blocks["VAL_Seize_The_Northern_Passes"], "x"), scalar(self.blocks["VAL_Seize_The_Northern_Passes"], "y")),
            },
            {(18, 13), (20, 13), (22, 13)},
        )
        self.assertEqual(
            (scalar(self.blocks["VAL_Stelander_Crisis_Opens"], "x"), scalar(self.blocks["VAL_Stelander_Crisis_Opens"], "y")),
            (20, 12),
        )
        self.assertEqual(
            (scalar(self.blocks["VAL_The_Steel_Contract"], "x"), scalar(self.blocks["VAL_The_Steel_Contract"], "y")),
            (20, 14),
        )

    def test_every_direct_war_focus_has_an_explicit_war_tooltip(self) -> None:
        expected = {
            "VAL_Return_Southern_Tsaygen": "VAL_return_southern_tsaygen_war_tt",
            "VAL_frontier_return_irem": "VAL_frontier_return_irem_war_tt",
            "VAL_Southern_Expansion": "VAL_southern_expansion_war_tt",
            "VAL_Eastern_Expansion": "VAL_eastern_expansion_war_tt",
            "VAL_Bezhaysk_Operation": "VAL_bezhaysk_operation_war_tt",
        }
        for focus_id, tooltip in expected.items():
            with self.subTest(focus=focus_id):
                block = self.blocks[focus_id]
                self.assertIn("declare_war_on =", block)
                self.assertIn(f"custom_effect_tooltip = {tooltip}", block)

    def test_indirect_war_focuses_say_they_only_unlock_the_next_step(self) -> None:
        self.assertIn(
            "custom_effect_tooltip = VAL_cw_military_course_focus_tt",
            self.blocks["VAL_Seize_The_Northern_Passes"],
        )
        self.assertNotIn("declare_war_on =", self.blocks["VAL_Seize_The_Northern_Passes"])
        self.assertIn(
            "custom_effect_tooltip = VAL_frontier_security_plan_war_tt",
            self.blocks["VAL_frontier_security_plan"],
        )
        self.assertNotIn("declare_war_on =", self.blocks["VAL_frontier_security_plan"])

    def test_war_tooltips_exist_in_both_languages(self) -> None:
        keys = (
            "VAL_cw_military_course_focus_tt",
            "VAL_frontier_security_plan_war_tt",
            "VAL_return_southern_tsaygen_war_tt",
            "VAL_frontier_return_irem_war_tt",
            "VAL_southern_expansion_war_tt",
            "VAL_eastern_expansion_war_tt",
            "VAL_bezhaysk_operation_war_tt",
        )
        for language in ("english", "russian"):
            loc = read(f"localisation/{language}/ADISCORD_VAL_decisions_l_{language}.yml")
            for key in keys:
                with self.subTest(language=language, key=key):
                    self.assertIn(f"{key}:", loc)


if __name__ == "__main__":
    unittest.main()
