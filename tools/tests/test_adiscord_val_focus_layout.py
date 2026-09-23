from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FOCUSES = ROOT / "common/national_focus/ADISCORD_national_focus_VAL.txt"


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8-sig")


def focus_blocks(source: str) -> dict[str, str]:
    blocks: dict[str, str] = {}
    cursor = 0
    while True:
        start = source.find("focus = {", cursor)
        if start < 0:
            return blocks
        opening = source.find("{", start)
        depth = 0
        quoted = False
        escaped = False
        end = -1
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
                    end = index + 1
                    break
        if end < 0:
            raise AssertionError("unterminated focus block")
        block = source[start:end]
        match = re.search(r"(?m)^\s*id\s*=\s*([A-Za-z0-9_]+)\s*$", block)
        if match:
            blocks[match.group(1)] = block
        cursor = end


def scalar(block: str, key: str) -> str:
    match = re.search(rf"(?m)^\s*{re.escape(key)}\s*=\s*([^\s#}}]+)", block)
    if not match:
        raise AssertionError(f"missing {key}")
    return match.group(1)


class KefreytFocusLayoutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = FOCUSES.read_text(encoding="utf-8-sig")
        cls.focuses = focus_blocks(cls.source)

    def position(self, focus_id: str) -> tuple[int, int]:
        block = self.focuses[focus_id]
        return int(scalar(block, "x")), int(scalar(block, "y"))

    def test_main_story_reads_top_to_bottom(self) -> None:
        expected = {
            "VAL_Stelander_Crisis_Opens": (20, 12),
            "VAL_Arms_For_The_Burning": (18, 13),
            "VAL_Keep_The_Arsenals": (20, 13),
            "VAL_Seize_The_Northern_Passes": (22, 13),
            "VAL_The_Steel_Contract": (20, 14),
            "VAL_Contracts_Outlive_Kings": (20, 15),
            "VAL_frontier_conference": (20, 16),
            "VAL_frontier_security_plan": (20, 19),
            "VAL_frontier_treaty_offices": (20, 20),
        }
        for focus_id, position in expected.items():
            with self.subTest(focus_id=focus_id):
                self.assertEqual(self.position(focus_id), position)

    def test_postwar_expansion_sits_below_main_wars(self) -> None:
        for focus_id in (
            "VAL_Occidian_Registries",
            "VAL_Return_Southern_Tsaygen",
            "VAL_frontier_return_irem",
            "VAL_Bezhaysk_Operation",
            "VAL_Wasteland_Charter",
            "VAL_Southern_Expansion",
            "VAL_Eastern_Expansion",
        ):
            with self.subTest(focus_id=focus_id):
                self.assertGreaterEqual(self.position(focus_id)[1], 21)

    def test_focus_nodes_do_not_share_coordinates(self) -> None:
        occupied: dict[tuple[int, int], str] = {}
        for focus_id, block in self.focuses.items():
            if not re.search(r"(?m)^\s*x\s*=", block) or not re.search(r"(?m)^\s*y\s*=", block):
                continue
            position = self.position(focus_id)
            self.assertNotIn(position, occupied, f"{focus_id} overlaps {occupied.get(position)}")
            occupied[position] = focus_id

    def test_direct_war_focuses_have_explicit_player_tooltips(self) -> None:
        expected = {
            "VAL_Return_Southern_Tsaygen": "VAL_return_southern_tsaygen_war_tt",
            "VAL_frontier_return_irem": "VAL_frontier_return_irem_war_tt",
            "VAL_Southern_Expansion": "VAL_southern_expansion_war_tt",
            "VAL_Eastern_Expansion": "VAL_eastern_expansion_war_tt",
            "VAL_Bezhaysk_Operation": "VAL_bezhaysk_operation_war_tt",
        }
        for focus_id, tooltip in expected.items():
            block = self.focuses[focus_id]
            with self.subTest(focus_id=focus_id):
                self.assertIn("declare_war_on = {", block)
                self.assertIn(f"custom_effect_tooltip = {tooltip}", block)

        russian = read("localisation/russian/ADISCORD_VAL_decisions_l_russian.yml")
        for tooltip in expected.values():
            line = next(line for line in russian.splitlines() if line.lstrip().startswith(tooltip + ":"))
            self.assertIn("объявляет войну", line.lower(), tooltip)

    def test_indirect_war_nodes_explain_the_extra_step(self) -> None:
        passes = self.focuses["VAL_Seize_The_Northern_Passes"]
        cannibals = self.focuses["VAL_frontier_security_plan"]
        self.assertIn("custom_effect_tooltip = VAL_cw_military_course_focus_tt", passes)
        self.assertIn("custom_effect_tooltip = VAL_frontier_security_plan_war_tt", cannibals)

        russian = read("localisation/russian/ADISCORD_VAL_decisions_l_russian.yml")
        self.assertIn("Сам фокус войну не объявляет", russian)
        self.assertIn("объявляет войну", russian.lower())


if __name__ == "__main__":
    unittest.main()
