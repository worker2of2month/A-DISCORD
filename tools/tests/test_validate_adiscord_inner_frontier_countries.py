import unittest
from pathlib import Path

from tools.builders.build_adiscord_inner_frontier_countries import (
    COUNTRY_HISTORY_PROFILES,
    build_profiles,
    render_common_country,
    render_country_history,
)
from tools.validators.validate_adiscord_inner_frontier_countries import validate, validate_external_gate_cleanup


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
                for field in ("graphical_culture =", "graphical_culture_2d =", "color ="):
                    self.assertIn(field, common)
                    self.assertNotIn(field, history)

    def test_external_gate_units_are_removed_before_the_country_disappears(self):
        split_effect = (ROOT / "common/scripted_effects/ADISCORD_inner_frontier_effects.txt").read_text(
            encoding="utf-8-sig"
        )
        collapse_on_actions = (
            ROOT / "common/on_actions/01_ADISCORD_vorkerland_collapse_on_actions.txt"
        ).read_text(encoding="utf-8-sig")
        self.assertEqual([], validate_external_gate_cleanup(split_effect, collapse_on_actions))

    def test_inner_frontier_country_contract(self):
        self.assertEqual([], validate())


if __name__ == "__main__":
    unittest.main()
