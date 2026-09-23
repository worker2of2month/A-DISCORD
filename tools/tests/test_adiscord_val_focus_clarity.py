from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8-sig")


def block(source: str, name: str) -> str:
    match = re.search(rf"(?m)^\s*{re.escape(name)}\s*=\s*\{{", source)
    if match is None:
        raise AssertionError(f"missing block: {name}")
    opening = source.find("{", match.start())
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
                return source[match.start():index + 1]
    raise AssertionError(f"unterminated block: {name}")


def focus(source: str, focus_id: str) -> str:
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


class KefreytFocusClarityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.focuses = read("common/national_focus/ADISCORD_national_focus_VAL.txt")
        self.decisions = read("common/decisions/ADISCORD_VAL_decisions.txt")
        self.ru = read("localisation/russian/ADISCORD_VAL_decisions_l_russian.yml")
        self.en = read("localisation/english/ADISCORD_VAL_decisions_l_english.yml")

    def test_main_wars_are_visually_above_continuation(self) -> None:
        def xy(focus_id: str) -> tuple[int, int]:
            body = focus(self.focuses, focus_id)
            return (
                int(re.search(r"(?m)^\s*x\s*=\s*(-?\d+)", body).group(1)),
                int(re.search(r"(?m)^\s*y\s*=\s*(-?\d+)", body).group(1)),
            )

        continuation_y = xy("VAL_Contracts_Outlive_Kings")[1]
        for focus_id in (
            "VAL_The_Harvest_Of_Ash",
            "VAL_Stelander_Crisis_Opens",
            "VAL_The_Steel_Contract",
            "VAL_frontier_conference",
            "VAL_frontier_security_plan",
        ):
            self.assertLess(xy(focus_id)[1], continuation_y, focus_id)
        for focus_id in (
            "VAL_Bezhaysk_Operation",
            "VAL_Return_Southern_Tsaygen",
            "VAL_Wasteland_Charter",
            "VAL_Southern_Expansion",
            "VAL_Eastern_Expansion",
        ):
            self.assertGreater(xy(focus_id)[1], continuation_y, focus_id)

        tsaygen = focus(self.focuses, "VAL_Return_Southern_Tsaygen")
        self.assertIn("prerequisite = { focus = VAL_Contracts_Outlive_Kings }", tsaygen)
        self.assertIn("prerequisite = { focus = VAL_Foreign_Broker_Licences }", tsaygen)

    def test_same_row_focuses_keep_visual_clearance(self) -> None:
        positions: list[tuple[str, int, int]] = []
        for match in re.finditer(r"(?m)^\\s*focus\\s*=\\s*\\{", self.focuses):
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
                        body = self.focuses[start:index + 1]
                        id_match = re.search(r"\\bid\\s*=\\s*([A-Za-z0-9_]+)", body)
                        x_match = re.search(r"(?m)^\\s*x\\s*=\\s*(-?\\d+)", body)
                        y_match = re.search(r"(?m)^\\s*y\\s*=\\s*(-?\\d+)", body)
                        if id_match and x_match and y_match:
                            positions.append((id_match.group(1), int(x_match.group(1)), int(y_match.group(1))))
                        break

        rows: dict[int, list[tuple[int, str]]] = {}
        for focus_id, x, y in positions:
            rows.setdefault(y, []).append((x, focus_id))

        for y, row in rows.items():
            row.sort()
            for (left_x, left_id), (right_x, right_id) in zip(row, row[1:]):
                self.assertGreaterEqual(
                    right_x - left_x,
                    2,
                    f"Focus nodes visually merge on row {y}: {left_id} at x={left_x}, {right_id} at x={right_x}",
                )

    def test_population_and_cannibal_routes_no_longer_wait_for_late_spine(self) -> None:
        harvest = focus(self.focuses, "VAL_The_Harvest_Of_Ash")
        self.assertIn("prerequisite = { focus = VAL_The_Contract_State }", harvest)
        self.assertNotIn("focus = VAL_One_Ledger_One_Banner", harvest)

        frontier = focus(self.focuses, "VAL_frontier_conference")
        self.assertIn("prerequisite = { focus = VAL_One_Ledger_One_Banner }", frontier)
        self.assertIn("prerequisite = { focus = VAL_Trading_Partners focus = VAL_October_Of_2160 }", frontier)
        self.assertNotIn("VAL_Different_Views_On_Freedom", frontier)
        self.assertNotIn("VAL_The_Steel_Contract", frontier)
        self.assertNotIn("VAL_Contracts_Outlive_Kings", frontier)

    def test_every_direct_war_focus_has_an_explicit_red_tooltip(self) -> None:
        cases = {
            "VAL_Bezhaysk_Operation": ("BJK", "VAL_declares_war_bezhaysk_tt"),
            "VAL_Return_Southern_Tsaygen": ("ERT", "VAL_return_southern_tsaygen_war_tt"),
            "VAL_frontier_return_irem": ("ERT", "VAL_declares_war_ert_irem_tt"),
            "VAL_Southern_Expansion": ("ERT", "VAL_declares_war_ert_south_tt"),
            "VAL_Eastern_Expansion": ("IRT", "VAL_declares_war_irt_tt"),
        }
        for focus_id, (target, tooltip) in cases.items():
            body = focus(self.focuses, focus_id)
            self.assertIn(f"custom_effect_tooltip = {tooltip}", body, focus_id)
            self.assertRegex(body, rf"declare_war_on\s*=\s*\{{\s*target\s*=\s*{target}\b")
            for loc in (self.ru, self.en):
                line = next(row for row in loc.splitlines() if row.startswith(f" {tooltip}:"))
                self.assertIn("§R", line)

        for tooltip in cases.values():
            ru_key = tooltip[1]
            line = next(row for row in self.ru.splitlines() if row.startswith(f" {ru_key}:"))
            self.assertIn("Объявляет войну", line)

    def test_indirect_war_routes_state_exactly_where_war_is_declared(self) -> None:
        passes = focus(self.focuses, "VAL_Seize_The_Northern_Passes")
        self.assertIn("custom_effect_tooltip = VAL_stelander_war_route_tt", passes)
        self.assertNotIn("declare_war_on", passes)

        mobilize = block(self.decisions, "VAL_cw_begin_mobilization")
        self.assertIn("custom_effect_tooltip = VAL_cw_begin_mobilization_war_tt", mobilize)
        self.assertIn("VAL_cw_start_intervention = yes", mobilize)

        security = focus(self.focuses, "VAL_frontier_security_plan")
        self.assertIn("custom_effect_tooltip = VAL_cannibal_war_route_tt", security)
        offensive = block(self.decisions, "VAL_frontier_begin_offensive")
        self.assertIn("custom_effect_tooltip = VAL_frontier_war_tt", offensive)

        for key in (
            "VAL_stelander_war_route_tt",
            "VAL_cw_begin_mobilization_war_tt",
            "VAL_cannibal_war_route_tt",
            "VAL_frontier_war_tt",
        ):
            line = next(row for row in self.ru.splitlines() if row.startswith(f" {key}:"))
            self.assertIn("объявляет войну", line.lower(), key)

    def test_touched_focus_ui_copy_avoids_old_ai_style_punctuation(self) -> None:
        keys = (
            "VAL_frontier_conference_desc",
            "VAL_frontier_security_plan_desc",
            "VAL_Bezhaysk_Operation_desc",
            "VAL_frontier_return_irem_desc",
            "VAL_Southern_Expansion_desc",
            "VAL_Eastern_Expansion_desc",
            "VAL_cw_begin_mobilization_desc",
            "VAL_startup_guide",
        )
        for source in (self.ru, self.en):
            for key in keys:
                line = next(row for row in source.splitlines() if row.startswith(f" {key}:"))
                self.assertNotIn("—", line, key)
                self.assertNotIn(";", line, key)


if __name__ == "__main__":
    unittest.main()
