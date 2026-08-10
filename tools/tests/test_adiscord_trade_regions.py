"""Focused contracts for lore-native trade-region filtering."""

from __future__ import annotations

import codecs
import json
import unittest
from pathlib import Path

from tools.builders.build_adiscord_trade_regions import (
    EXPECTED_CONTINENT_KEYS,
    build_plan,
    rewrite_continent_column,
    validate as validate_builder,
)
from tools.validators.validate_adiscord_trade_regions import (
    EXPECTED_PROVINCE_COUNTS,
    EXPECTED_STATE_COUNTS,
    GEOGRAPHIC_STATE_ANCHORS,
    validate as validate_trade_regions,
)


ROOT = Path(__file__).resolve().parents[2]


class ADiscordTradeRegionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.plan = build_plan(ROOT)

    def test_continent_ids_follow_the_engine_file_order(self) -> None:
        self.assertEqual(self.plan.continent_keys, EXPECTED_CONTINENT_KEYS)
        manifest = json.loads(
            (ROOT / "tools/data/adiscord_trade_region_map.json").read_text(encoding="utf-8")
        )
        self.assertEqual(manifest["default_continent"], 7)
        self.assertEqual(
            [(entry["id"], entry["key"]) for entry in manifest["continents"]],
            list(enumerate(EXPECTED_CONTINENT_KEYS, 1)),
        )

    def test_approved_geography_covers_every_real_land_province(self) -> None:
        self.assertEqual(dict(self.plan.state_counts), EXPECTED_STATE_COUNTS)
        self.assertEqual(dict(self.plan.province_counts), EXPECTED_PROVINCE_COUNTS)
        self.assertEqual(sum(self.plan.province_counts.values()), 13_384)
        self.assertEqual(set(self.plan.province_continents.values()), set(range(1, 8)))

    def test_mixed_strategic_regions_are_explicitly_resolved_by_state(self) -> None:
        manifest = json.loads(
            (ROOT / "tools/data/adiscord_trade_region_map.json").read_text(encoding="utf-8")
        )
        fully_overridden = set(manifest["fully_overridden_strategic_regions"])
        explicit_states = {
            state_id
            for entry in manifest["continents"]
            for state_id in entry["states"]
        }
        states_in_mixed_regions = {
            state_id
            for state_id, region_id in self.plan.state_regions.items()
            if region_id in fully_overridden
        }
        self.assertEqual(states_in_mixed_regions, states_in_mixed_regions & explicit_states)

    def test_geographic_anchors_do_not_follow_current_country_ownership(self) -> None:
        for state_id, (region_id, continent_id) in GEOGRAPHIC_STATE_ANCHORS.items():
            with self.subTest(state=state_id):
                self.assertEqual(self.plan.state_regions[state_id], region_id)
                self.assertEqual(self.plan.state_continents[state_id], continent_id)

    def test_rewrite_changes_only_continent_field_and_preserves_byte_layout(self) -> None:
        source = codecs.BOM_UTF8 + (
            b"0;0;0;0;land;false;unknown;6\r\n"
            b"1;1;2;3;land;false;forest;1\n"
            b"2;4;5;6;sea;true;ocean;7\r"
            b"3;7;8;9;land;true;urban;2"
        )
        expected = codecs.BOM_UTF8 + (
            b"0;0;0;0;land;false;unknown;0\r\n"
            b"1;1;2;3;land;false;forest;6\n"
            b"2;4;5;6;sea;true;ocean;0\r"
            b"3;7;8;9;land;true;urban;4"
        )
        self.assertEqual(
            rewrite_continent_column(source, {1: 6, 3: 4}, path=Path("fixture.csv")),
            expected,
        )

    def test_generated_definition_and_validator_are_current(self) -> None:
        self.assertEqual(validate_builder(ROOT), [])
        self.assertEqual(validate_trade_regions(ROOT), [])


if __name__ == "__main__":
    unittest.main()
