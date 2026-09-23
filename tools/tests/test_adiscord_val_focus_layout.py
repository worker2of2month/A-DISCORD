from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FOCUS_PATH = ROOT / "common/national_focus/ADISCORD_national_focus_VAL.txt"


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8-sig")


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


class KefreytFocusLayoutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.focuses = FOCUS_PATH.read_text(encoding="utf-8")

    def position(self, focus_id: str) -> tuple[int, int]:
        block = focus_block(self.focuses, focus_id)
        return scalar(block, "x"), scalar(block, "y")

    def test_campaign_reads_in_three_vertical_layers(self) -> None:
        # Development first.
        for focus_id in (
            "VAL_State_Contract",
            "VAL_Industrial_Mobilization_Plan",
            "VAL_Army_Of_The_Ledger",
        ):
            self.assertLessEqual(self.position(focus_id)[1], 10, focus_id)
        self.assertEqual(self.position("VAL_Contracts_Outlive_Kings")[1], 12)

        # Main wars occupy the middle of the tree.
        self.assertEqual(self.position("VAL_Stelander_Crisis_Opens")[1], 14)
        for focus_id in (
            "VAL_Arms_For_The_Burning",
            "VAL_Keep_The_Arsenals",
            "VAL_Seize_The_Northern_Passes",
        ):
            self.assertEqual(self.position(focus_id)[1], 15, focus_id)
        self.assertEqual(self.position("VAL_The_Steel_Contract")[1], 16)
        self.assertEqual(self.position("VAL_frontier_conference")[1], 18)
        self.assertEqual(self.position("VAL_frontier_security_plan")[1], 22)

        # Expansion and settlement continue below the main-war layer.
        for focus_id in (
            "VAL_Return_Southern_Tsaygen",
            "VAL_Bezhaysk_Operation",
            "VAL_Occidian_Registries",
        ):
            self.assertGreaterEqual(self.position(focus_id)[1], 20, focus_id)
        for focus_id in (
            "VAL_frontier_treaty_offices",
            "VAL_Northern_Settlement",
            "VAL_Stelander_Ultimatum",
            "VAL_Southern_Expansion",
            "VAL_Eastern_Expansion",
        ):
            self.assertGreaterEqual(self.position(focus_id)[1], 24, focus_id)

    def test_main_campaign_nodes_do_not_share_coordinates(self) -> None:
        focus_ids = (
            "VAL_Contracts_Outlive_Kings",
            "VAL_Stelander_Crisis_Opens",
            "VAL_Arms_For_The_Burning",
            "VAL_Keep_The_Arsenals",
            "VAL_Seize_The_Northern_Passes",
            "VAL_The_Steel_Contract",
            "VAL_frontier_conference",
            "VAL_frontier_logistics",
            "VAL_frontier_commissioners",
            "VAL_frontier_provincial_offices",
            "VAL_frontier_security_plan",
            "VAL_Return_Southern_Tsaygen",
            "VAL_Bezhaysk_Operation",
            "VAL_frontier_return_irem",
            "VAL_Wasteland_Charter",
            "VAL_Southern_Expansion",
            "VAL_Eastern_Expansion",
        )
        positions = [self.position(focus_id) for focus_id in focus_ids]
        self.assertEqual(len(positions), len(set(positions)))

    def test_existing_campaign_gates_are_preserved(self) -> None:
        conference = focus_block(self.focuses, "VAL_frontier_conference")
        prerequisite = re.search(r"prerequisite\s*=\s*\{([^}]+)\}", conference)
        self.assertIsNotNone(prerequisite)
        for focus_id in (
            "VAL_Contracts_Outlive_Kings",
            "VAL_The_Steel_Contract",
            "VAL_Market_Roads_North",
        ):
            self.assertIn(f"focus = {focus_id}", prerequisite.group(1))

        contracts = focus_block(self.focuses, "VAL_Contracts_Outlive_Kings")
        for focus_id in (
            "VAL_State_Contract",
            "VAL_Industrial_Mobilization_Plan",
            "VAL_Army_Of_The_Ledger",
        ):
            self.assertIn(f"prerequisite = {{ focus = {focus_id} }}", contracts)


class KefreytWarTooltipTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.focuses = FOCUS_PATH.read_text(encoding="utf-8")
        cls.ru = read("localisation/russian/ADISCORD_VAL_decisions_l_russian.yml")
        cls.en = read("localisation/english/ADISCORD_VAL_decisions_l_english.yml")

    def test_every_direct_war_focus_has_an_explicit_war_tooltip(self) -> None:
        expected = {
            "VAL_Return_Southern_Tsaygen": "VAL_return_southern_tsaygen_war_tt",
            "VAL_frontier_return_irem": "VAL_frontier_return_irem_war_tt",
            "VAL_Southern_Expansion": "VAL_southern_expansion_war_tt",
            "VAL_Eastern_Expansion": "VAL_eastern_expansion_war_tt",
            "VAL_Bezhaysk_Operation": "VAL_bezhaysk_operation_war_tt",
        }
        direct_wars = []
        for match in re.finditer(r"(?m)^\s*focus\s*=\s*\{", self.focuses):
            start = match.start()
            opening = self.focuses.find("{", start)
            depth = 0
            quoted = False
            escaped = False
            for index in range(opening, len(self.focuses)):
                char = self.focuses[index]
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
                        block = self.focuses[start:index + 1]
                        id_match = re.search(r"\bid\s*=\s*([A-Za-z0-9_]+)", block)
                        if id_match and "declare_war_on" in block:
                            direct_wars.append(id_match.group(1))
                        break

        self.assertEqual(set(direct_wars), set(expected))
        for focus_id, tooltip in expected.items():
            block = focus_block(self.focuses, focus_id)
            self.assertIn(f"custom_effect_tooltip = {tooltip}", block)
            ru_line = next(line for line in self.ru.splitlines() if line.strip().startswith(tooltip + ":"))
            en_line = next(line for line in self.en.splitlines() if line.strip().startswith(tooltip + ":"))
            self.assertIn("Объявляет войну", ru_line)
            self.assertIn("Declares war", en_line)

    def test_preparation_focuses_do_not_pretend_to_declare_war(self) -> None:
        passes = focus_block(self.focuses, "VAL_Seize_The_Northern_Passes")
        self.assertNotIn("declare_war_on", passes)
        self.assertIn("custom_effect_tooltip = VAL_stelander_military_course_tt", passes)
        self.assertIn("Сам фокус войну не объявляет", self.ru)

        mandate = focus_block(self.focuses, "VAL_frontier_security_plan")
        self.assertNotIn("declare_war_on", mandate)
        self.assertIn("custom_effect_tooltip = VAL_frontier_security_plan_war_tt", mandate)
        self.assertIn("Отказ позволяет начать войну отдельным решением", self.ru)

    def test_localisation_files_keep_bom(self) -> None:
        for relative in (
            "localisation/english/ADISCORD_VAL_decisions_l_english.yml",
            "localisation/russian/ADISCORD_VAL_decisions_l_russian.yml",
            "localisation/english/ADISCORD_VAL_logistics_market_l_english.yml",
            "localisation/russian/ADISCORD_VAL_logistics_market_l_russian.yml",
        ):
            self.assertTrue((ROOT / relative).read_bytes().startswith(b"\xef\xbb\xbf"), relative)


if __name__ == "__main__":
    unittest.main()
