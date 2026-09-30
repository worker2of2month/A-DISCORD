import unittest
from unittest.mock import patch

from tools.builders.build_adiscord_northern_countries import build_profiles
from tools.validators.validate_adiscord_northern_countries import validate


class NorthernCountryContractsTest(unittest.TestCase):
    def test_northern_country_contract(self):
        self.assertEqual([], validate())

    def test_starting_factories_fit_native_state_categories(self):
        profiles, _principal_provinces = build_profiles()
        native_slots = {"pastoral": 1, "rural": 2, "town": 4, "large_town": 5}
        for state_id, profile in profiles.items():
            with self.subTest(state_id=state_id):
                factories = profile["civilian"] + profile["military"]
                self.assertLessEqual(factories, native_slots[profile["category"]])

    def test_validator_rejects_starting_factory_overflow(self):
        profiles, principal_provinces = build_profiles()
        profiles[425]["category"] = "rural"
        with patch(
            "tools.validators.validate_adiscord_northern_countries.build_profiles",
            return_value=(profiles, principal_provinces),
        ):
            issues = validate()
        self.assertIn(
            "state 425 has 3 starting factories but rural supports only 2 shared slots",
            issues,
        )


if __name__ == "__main__":
    unittest.main()
