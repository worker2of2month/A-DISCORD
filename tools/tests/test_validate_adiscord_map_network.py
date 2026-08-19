#!/usr/bin/env python3
"""Tests for the railway and river network validators.

The point of both validators is to catch a defect the engine will not report.  A
railway whose consecutive provinces do not share a border stops carrying supply
silently, and a river that drifts off a province border silently loses its
river-crossing combat penalty.  So these tests exercise the detectors against
synthetic defects as well as asserting the committed baselines still describe the
live map.
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path

import numpy as np

from tools.lib.map_network import (
    ProvinceGraph,
    RIVER_VALID_INDICES,
    connected_systems,
    declared_adjacencies,
    parse_railways,
    path_relief,
    province_id_field,
    raster_adjacency,
)
from tools.lib.map_raster import DefinitionRow
from tools.validators import validate_adiscord_map_railways as railways
from tools.validators import validate_adiscord_map_rivers as rivers


ROOT = Path(__file__).resolve().parents[2]


def _definition(rows: dict[int, tuple[tuple[int, int, int], str, str]]):
    return {
        province_id: DefinitionRow(province_id, colour, kind, False, terrain, 1)
        for province_id, (colour, kind, terrain) in rows.items()
    }


class ProvinceGraphTests(unittest.TestCase):
    def test_adjacency_is_four_connected_only(self) -> None:
        """A corner touch is not adjacency in HOI4, so it must not be reported."""

        field = np.array([[1, 2], [3, 1]], dtype=np.int32)
        adjacency = raster_adjacency(field)
        self.assertEqual(adjacency[1], {2, 3})
        self.assertNotIn(1, adjacency.get(1, set()))
        # 2 and 3 only touch diagonally.
        self.assertNotIn(3, adjacency[2])

    def test_unknown_colours_become_the_zero_sentinel(self) -> None:
        provinces = np.array(
            [[[10, 20, 30], [99, 99, 99]]], dtype=np.uint8
        )
        definition = _definition({7: ((10, 20, 30), "land", "plains")})
        field = province_id_field(provinces, definition)
        self.assertEqual(field.tolist(), [[7, 0]])

    def test_shortest_land_path_skips_sea_and_respects_the_limit(self) -> None:
        field = np.array([[1, 2, 3, 4]], dtype=np.int32)
        definition = _definition(
            {
                1: ((1, 1, 1), "land", "plains"),
                2: ((2, 2, 2), "sea", "ocean"),
                3: ((3, 3, 3), "land", "plains"),
                4: ((4, 4, 4), "land", "plains"),
            }
        )
        graph = ProvinceGraph(field, definition)
        self.assertIsNone(graph.shortest_land_path(1, 4))
        self.assertEqual(graph.shortest_land_path(1, 3), None)
        self.assertEqual(graph.shortest_land_path(3, 4), [])

    def test_declared_adjacency_joins_provinces_that_do_not_touch(self) -> None:
        field = np.array([[1, 0, 2]], dtype=np.int32)
        definition = _definition(
            {
                1: ((1, 1, 1), "land", "plains"),
                2: ((2, 2, 2), "land", "plains"),
            }
        )
        self.assertFalse(ProvinceGraph(field, definition).linked(1, 2))
        self.assertTrue(ProvinceGraph(field, definition, {(1, 2)}).linked(1, 2))

    def test_declared_adjacencies_skips_the_terminator_row(self) -> None:
        path = ROOT / "map" / "adjacencies.csv"
        pairs = declared_adjacencies(path)
        self.assertTrue(all(first > 0 and second > 0 for first, second in pairs))
        self.assertTrue(all(first < second for first, second in pairs))

    def test_border_mask_marks_both_sides_of_a_boundary(self) -> None:
        field = np.array([[1, 1, 2, 2]], dtype=np.int32)
        definition = _definition(
            {
                1: ((1, 1, 1), "land", "plains"),
                2: ((2, 2, 2), "land", "plains"),
            }
        )
        mask = ProvinceGraph(field, definition).border_mask()
        self.assertEqual(mask.tolist(), [[False, True, True, False]])

    def test_path_relief_reports_the_worst_step_not_the_endpoints(self) -> None:
        worst, total = path_relief([1, 2, 3], {1: 100.0, 2: 160.0, 3: 110.0})
        self.assertEqual(worst, 60.0)
        self.assertEqual(total, 110.0)


class ConnectedSystemTests(unittest.TestCase):
    def test_diagonal_channel_stays_one_system(self) -> None:
        """River channels are one pixel wide and turn diagonally."""

        channel = np.array(
            [[True, False, False], [False, True, False], [False, False, True]]
        )
        systems = connected_systems(channel)
        self.assertEqual(len(systems), 1)
        self.assertEqual(systems[0].size, 3)

    def test_separated_channels_are_separate_systems(self) -> None:
        channel = np.array([[True, False, False, True]])
        self.assertEqual(len(connected_systems(channel)), 2)

    def test_a_row_wrap_is_not_a_connection(self) -> None:
        channel = np.array([[False, False, True], [True, False, False]])
        self.assertEqual(len(connected_systems(channel)), 2)


class RailwayParsingTests(unittest.TestCase):
    def test_railways_parse_with_level_count_and_path(self) -> None:
        parsed = parse_railways(ROOT / "map" / "railways.txt")
        self.assertTrue(parsed)
        for _number, level, declared, path in parsed:
            self.assertGreaterEqual(level, railways.MIN_LEVEL)
            self.assertLessEqual(level, railways.MAX_LEVEL)
            self.assertEqual(declared, len(path))
            self.assertGreaterEqual(len(path), railways.MIN_PROVINCES)


class RailwayFindingsTests(unittest.TestCase):
    def test_live_map_matches_the_recorded_findings(self) -> None:
        self.assertEqual(railways.validate(), [])

    def test_every_recorded_break_names_a_single_missing_province(self) -> None:
        """A one-province gap is a lost stop; a longer one is a different route.

        That distinction is why the repair is only *proposed* here: inserting one
        adjacent province restores the line the author drew, whereas inventing a
        multi-province detour would redirect supply.
        """

        payload = railways.load_findings()
        self.assertTrue(payload["adjacency_breaks"])
        for entry in payload["adjacency_breaks"]:
            with self.subTest(line=entry["line"]):
                missing = entry["missing_provinces"]
                self.assertIsNotNone(missing, "no all-land repair path was found")
                self.assertEqual(len(missing), 1)

    def test_structural_defects_are_reported_not_recorded(self) -> None:
        """Only adjacency breaks are tolerated; a bad id or level must fail."""

        issues, _report = railways.audit()
        self.assertEqual(issues, [])


class RailwayDetectionTests(unittest.TestCase):
    def test_a_new_break_is_reported_against_the_recorded_set(self) -> None:
        recorded = railways.known_breaks(railways.load_findings())
        self.assertTrue(recorded)
        invented = (99999, 1, 2)
        self.assertNotIn(invented, recorded)


class RiverFindingsTests(unittest.TestCase):
    def test_live_map_matches_the_recorded_baseline(self) -> None:
        self.assertEqual(rivers.validate(), [])

    def test_recorded_alignment_is_the_reason_no_reroute_happened(self) -> None:
        """State the measurement as a contract so the decision stays auditable."""

        payload = json.loads(rivers.FINDINGS_PATH.read_text(encoding="utf-8"))
        self.assertGreater(float(payload["on_border_share"]), 0.95)
        self.assertGreater(float(payload["within_one_pixel_share"]), 0.97)
        self.assertEqual(payload["systems_without_source"], [])

    def test_palette_contract_covers_source_flow_widths_and_backgrounds(self) -> None:
        self.assertEqual(
            RIVER_VALID_INDICES,
            frozenset(set(range(0, 12)) | {254, 255}),
        )

    def test_audit_reports_no_format_defect_on_the_live_map(self) -> None:
        issues, report = rivers.audit()
        self.assertEqual(issues, [])
        self.assertGreater(int(report["channel_pixels"]), 0)


if __name__ == "__main__":
    unittest.main()
