"""Planned Montar provinces join their parent's region without regrouping it."""

from __future__ import annotations

import json
import unittest
from unittest import mock

from tools.builders import build_adiscord_strategic_regions as builder
from tools.validators.validate_adiscord_strategic_regions import planned_parent_region_issues


GEOGRAPHY = json.loads(
    (builder.ROOT / "tools/data/adiscord_mon_geography.json").read_text(encoding="utf-8")
)
CITY, REMAINDER, DISTRICT, OTHER = 19901, 19902, 19903, 19904


class PlannedProvinceRegionTests(unittest.TestCase):
    def test_planned_children_count_as_their_parent_in_weather_samples(self):
        positions = {
            CITY: (10.0, 1.0, 100.0),
            REMAINDER: (12.0, 1.0, 120.0),
            OTHER: (30.0, 1.0, 300.0),
        }
        with mock.patch.dict(builder.DISTRICT_PARENT, {REMAINDER: CITY}):
            samples = builder.climate_sample_latitudes({CITY, REMAINDER, OTHER}, positions)
        self.assertEqual(sorted(samples), [builder.MAP_HEIGHT - 300.0, builder.MAP_HEIGHT - 110.0])

    def test_planned_children_do_not_weigh_in_region_grouping(self):
        states = {469: {CITY, REMAINDER, DISTRICT}, 470: {OTHER}}
        with mock.patch.object(builder, "MON_PLANNED_PARENT", {REMAINDER: CITY, DISTRICT: CITY}):
            self.assertEqual(builder.grouping_states(states), {469: {CITY}, 470: {OTHER}})
        self.assertEqual(states[469], {CITY, REMAINDER, DISTRICT})

    def test_empty_plan_leaves_grouping_unchanged(self):
        states = {469: {CITY, REMAINDER}}
        with mock.patch.object(builder, "MON_PLANNED_PARENT", {}):
            self.assertEqual(builder.grouping_states(states), states)

    def test_validator_requires_the_parent_region_once_both_are_mapped(self):
        regions = {CITY: [68], REMAINDER: [68], DISTRICT: [65]}
        planned = {REMAINDER: CITY, DISTRICT: CITY, OTHER: CITY}
        issues = planned_parent_region_issues(regions, planned)
        self.assertEqual(len(issues), 1)
        self.assertIn(f"planned province {DISTRICT}", issues[0])

    def test_plan_is_wired_into_the_weather_parents(self):
        expected = {
            entry["province"]: entry["parent"] for entry in GEOGRAPHY["planned"]["provinces"]
        }
        self.assertEqual(builder.MON_PLANNED_PARENT, expected)
        self.assertLessEqual(expected.items(), builder.DISTRICT_PARENT.items())

    def test_every_montar_state_keeps_a_pinned_grouping_centre(self):
        self.assertEqual(set(builder.MON_GROUPING_CENTRES), set(GEOGRAPHY["states"]))

    def test_planned_children_share_their_parent_state_region(self):
        region_by_state = {
            state_id: region.region_id for region in builder.REGIONS for state_id in region.states
        }
        state_by_province = {
            province: state_id
            for state_id, provinces in builder.load_states().items()
            for province in provinces
        }
        for entry in GEOGRAPHY["planned"]["provinces"]:
            with self.subTest(province=entry["province"]):
                self.assertEqual(
                    region_by_state[entry["state"]],
                    region_by_state[state_by_province[entry["parent"]]],
                )


if __name__ == "__main__":
    unittest.main()
