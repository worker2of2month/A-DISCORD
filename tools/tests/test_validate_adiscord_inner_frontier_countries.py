from tools.lib.on_actions import read_country_on_actions
import unittest
from pathlib import Path

from tools.builders.build_adiscord_inner_frontier_countries import (
    COUNTRY_HISTORY_PROFILES,
    EXPECTED_STATES,
    build_profiles,
    render_common_country,
    render_country_history,
    settlement_points,
    victory_point_localisation,
)
from tools.builders.build_adiscord_northern_countries import (
    geography_scope_states,
    load_mon_geography,
    mon_city_parents,
)
from tools.validators.validate_adiscord_inner_frontier_countries import (
    validate,
    validate_external_gate_cleanup,
)


ROOT = Path(__file__).resolve().parents[2]


class InnerFrontierCountryContractsTest(unittest.TestCase):
    def test_factory_dense_states_are_not_generated_as_rural(self):
        profiles, _principal_provinces = build_profiles()
        self.assertEqual(profiles[151]["category"], "town")
        for state_id, profile in profiles.items():
            with self.subTest(state=state_id):
                factories = int(profile["civilian"]) + int(profile["military"])
                if profile["category"] == "rural":
                    self.assertLessEqual(factories, 2)

    def test_generated_histories_keep_visual_fields_in_common_country_scope(self):
        for tag in COUNTRY_HISTORY_PROFILES:
            with self.subTest(tag=tag):
                common = render_common_country(tag)
                history = render_country_history(tag)
                for field in (
                    "graphical_culture =",
                    "graphical_culture_2d =",
                    "color =",
                ):
                    self.assertIn(field, common)
                    self.assertNotIn(field, history)

    def test_external_gate_units_are_removed_before_the_country_disappears(self):
        split_effect = (
            ROOT / "common/scripted_effects/ADISCORD_inner_frontier_effects.txt"
        ).read_text(encoding="utf-8-sig")
        collapse_on_actions = read_country_on_actions(
            ROOT / "common/on_actions/01_ADISCORD_vorkerland_collapse_on_actions.txt",
            'vorkerland_collapse',
        )
        self.assertEqual(
            [], validate_external_gate_cleanup(split_effect, collapse_on_actions)
        )
        for forbidden in (
            "ADISCORD_vorkerland_split_external_gate = yes",
            "WCG = { ADISCORD_vorkerland_delete_external_gate_formations = yes }",
            "ADISCORD_vorkerland_external_gate_formations_removed_v4",
        ):
            self.assertNotIn(forbidden, collapse_on_actions)

    def test_geography_states_take_their_settlements_and_city(self):
        geography = load_mon_geography()
        scope = geography_scope_states(geography) & EXPECTED_STATES
        self.assertEqual(
            {89, 126, 133, 134, 135, 136, 137, 138, 139, 140, 141, 142, 143, 147, 148, 149},
            set(scope),
        )
        cities = mon_city_parents(geography)
        planned = {entry["province"] for entry in geography["stage2"]["planned"]["provinces"]}
        profiles, principal_provinces = build_profiles()
        for state_id in sorted(EXPECTED_STATES):
            points = [province for province, _value, _name in profiles[state_id]["victory_points"]]
            with self.subTest(state=state_id):
                if state_id in scope:
                    expected = [
                        province
                        for point_state, province, _value, _name in settlement_points(geography)
                        if point_state == state_id
                    ]
                    self.assertEqual(cities[state_id], principal_provinces[state_id])
                    self.assertEqual(expected, points)
                else:
                    self.assertLessEqual(len(points), 1)
                    self.assertTrue(set(points) <= {principal_provinces[state_id]})
                    self.assertFalse(set(profiles[state_id]["provinces"]) & planned)

    def test_partly_covered_country_keeps_manifest_names_outside_the_scope(self):
        points = ((149, 6779, 8, "Рина"), (149, 1684, 1, "Пескари"))
        principal = {state_id: state_id for state_id in EXPECTED_STATES}
        localisation = victory_point_localisation(principal, points)
        rin = [key for key, name in localisation.items() if name in {"Рина", "Пескари", "Палатинский Двор"}]
        self.assertEqual(
            ["VICTORY_POINTS_6779", "VICTORY_POINTS_1684", "VICTORY_POINTS_147"], rin
        )

    def test_inner_frontier_country_contract(self):
        self.assertEqual([], validate())


if __name__ == "__main__":
    unittest.main()
