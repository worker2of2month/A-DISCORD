from __future__ import annotations

import re
import unittest
from pathlib import Path

from tools.tests.test_adiscord_stp_preparation import (
    block as parsed_block,
    entries,
    scalar,
)

from tools.lib.focus_sources import read_focus_source

ROOT = Path(__file__).resolve().parents[2]


def read(relative: str) -> str:
    return read_focus_source(ROOT / relative)


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
                return source[match.start() : index + 1]
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
                return source[start : index + 1]
    raise AssertionError(f"unterminated focus: {focus_id}")


class KefreytFocusClarityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.focuses = read("common/national_focus/ADISCORD_national_focus_VAL.txt")
        self.decisions = read("common/decisions/ADISCORD_VAL_decisions.txt")
        self.ru = read("localisation/russian/ADISCORD_VAL_decisions_l_russian.yml")
        self.en = read("localisation/english/ADISCORD_VAL_decisions_l_english.yml")

    def test_opening_crisis_precedes_postwar_and_expansion_layers(self) -> None:
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

        conference_y = xy("VAL_frontier_conference")[1]
        security_y = xy("VAL_frontier_security_plan")[1]
        self.assertLess(continuation_y, conference_y)
        self.assertLess(conference_y, security_y)
        self.assertLess(security_y, xy("VAL_frontier_treaty_offices")[1])

        tsaygen = focus(self.focuses, "VAL_Return_Southern_Tsaygen")
        self.assertIn("prerequisite = { focus = VAL_Contracts_Outlive_Kings }", tsaygen)
        self.assertIn("prerequisite = { focus = VAL_Foreign_Broker_Licences }", tsaygen)

    def test_same_row_focuses_keep_visual_clearance(self) -> None:
        positions: list[tuple[str, int, int]] = []
        tree = parsed_block(
            entries("common/national_focus/ADISCORD_national_focus_VAL.txt"),
            "focus_tree",
        )
        for entry in tree:
            if entry.key == "focus":
                positions.append(
                    (
                        scalar(entry.value, "id"),
                        int(scalar(entry.value, "x")),
                        int(scalar(entry.value, "y")),
                    )
                )
        self.assertGreater(len(positions), 1, "The layout check must visit focus nodes")
        self.assertEqual(len(positions), len({name for name, _, _ in positions}))

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

    def test_population_opens_early_and_frontier_waits_for_contract_readiness(self) -> None:
        harvest = focus(self.focuses, "VAL_The_Harvest_Of_Ash")
        self.assertIn("prerequisite = { focus = VAL_reclamation_survey }", harvest)
        survey = focus(self.focuses, "VAL_reclamation_survey")
        factories = focus(self.focuses, "VAL_Factories_Like_Cathedrals")
        self.assertIn("prerequisite = { focus = VAL_Factories_Like_Cathedrals }", survey)
        self.assertIn("prerequisite = { focus = VAL_The_Contract_State }", factories)
        self.assertNotIn("focus = VAL_One_Ledger_One_Banner", harvest)

        frontier = focus(self.focuses, "VAL_frontier_conference")
        self.assertIn("prerequisite = { focus = VAL_Contracts_Outlive_Kings }", frontier)
        self.assertIn("prerequisite = { focus = VAL_One_Ledger_One_Banner }", frontier)
        self.assertIn(
            "prerequisite = { focus = VAL_Trading_Partners focus = VAL_October_Of_2160 }",
            frontier,
        )
        self.assertNotIn("VAL_Different_Views_On_Freedom", frontier)
        self.assertNotIn("VAL_The_Steel_Contract", frontier)

    def test_every_direct_war_focus_has_an_explicit_red_tooltip(self) -> None:
        cases = {
            "VAL_Bezhaysk_Operation": ("BJK", "VAL_declares_war_bezhaysk_tt"),
        }
        for focus_id, (target, tooltip) in cases.items():
            body = focus(self.focuses, focus_id)
            self.assertIn(f"custom_effect_tooltip = {tooltip}", body, focus_id)
            self.assertRegex(
                body, rf"declare_war_on\s*=\s*\{{\s*target\s*=\s*{target}\b"
            )
            for loc in (self.ru, self.en):
                line = next(
                    row for row in loc.splitlines() if row.startswith(f" {tooltip}:")
                )
                self.assertIn("§R", line)

        for tooltip in cases.values():
            ru_key = tooltip[1]
            line = next(
                row for row in self.ru.splitlines() if row.startswith(f" {ru_key}:")
            )
            self.assertIn("Объявляет войну", line)

    def test_expansion_focuses_unlock_the_orders_that_declare_war(self) -> None:
        effects = read("common/scripted_effects/ADISCORD_VAL_effects.txt")
        cases = (
            (
                "VAL_Return_Southern_Tsaygen",
                "VAL_operation_return_southern_tsaygen",
                "ERT",
                "VAL_return_southern_tsaygen_war_tt",
            ),
            (
                "VAL_frontier_return_irem",
                "VAL_operation_cross_perimeter",
                "ERT",
                "VAL_declares_war_ert_irem_tt",
            ),
            (
                "VAL_Southern_Expansion",
                "VAL_operation_expand_southern_bridgehead",
                "ERT",
                "VAL_declares_war_ert_south_tt",
            ),
            (
                "VAL_Eastern_Expansion",
                "VAL_operation_eastern_security_belt",
                "IRT",
                "VAL_declares_war_irt_tt",
            ),
        )
        for focus_id, decision_id, target, tooltip in cases:
            with self.subTest(focus=focus_id):
                body = focus(self.focuses, focus_id)
                self.assertNotIn("declare_war_on", body)
                self.assertIn(f"unlock_decision_tooltip = {decision_id}", body)
                decision = block(self.decisions, decision_id)
                self.assertIn(f"has_completed_focus = {focus_id}", decision)
                reward = block(decision, "complete_effect")
                self.assertIn(f"custom_effect_tooltip = {tooltip}", reward)
                if focus_id == "VAL_Return_Southern_Tsaygen":
                    self.assertIn("VAL_begin_southern_tsaygen_campaign = yes", reward)
                    reward = block(effects, "VAL_begin_southern_tsaygen_campaign")
                    self.assertIn("set_variable = { var = VAL_frontier_target value = 4 }", reward)
                    self.assertIn("VAL_frontier_start_war = yes", reward)
                    reward = block(effects, "VAL_frontier_start_war")
                self.assertRegex(reward, rf"declare_war_on\s*=\s*\{{\s*target\s*=\s*{target}\b")
                for loc in (self.ru, self.en):
                    line = next(row for row in loc.splitlines() if row.startswith(f" {tooltip}:"))
                    self.assertIn("§R", line)

    def test_indirect_war_routes_state_exactly_where_war_is_declared(self) -> None:
        passes = focus(self.focuses, "VAL_Seize_The_Northern_Passes")
        self.assertIn("custom_effect_tooltip = VAL_stelander_war_route_tt", passes)
        self.assertNotIn("declare_war_on", passes)

        mobilize = block(self.decisions, "VAL_cw_begin_mobilization")
        self.assertIn(
            "custom_effect_tooltip = VAL_cw_begin_mobilization_war_tt", mobilize
        )
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
            line = next(
                row for row in self.ru.splitlines() if row.startswith(f" {key}:")
            )
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
                line = next(
                    row for row in source.splitlines() if row.startswith(f" {key}:")
                )
                self.assertNotIn("\u2014", line, key)
                self.assertNotIn(";", line, key)


if __name__ == "__main__":
    unittest.main()
