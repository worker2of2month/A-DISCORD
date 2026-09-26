from pathlib import Path
import re
import unittest

from tools.validators.validate_adiscord_vorkerland_collapse import named_block

ROOT = Path(__file__).resolve().parents[2]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8-sig")


class VorkerlandClaimantOpeningBalanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.effects = read("common/scripted_effects/ADISCORD_vorkerland_effects.txt")
        cls.initial = named_block(cls.effects, "ADISCORD_vorkerland_prepare_initial_combatants")
        cls.wkr = named_block(cls.initial, "WKR")

    def test_wkr_no_longer_has_double_vadl_deployed_air(self):
        wkr_air = read("history/units/WRK_vorkerland_collapse_air.txt")
        vad_air = read("history/units/VAD_vorkerland_collapse_air.txt")
        self.assertEqual(wkr_air.count('owner = "WKR" amount = 100'), vad_air.count('owner = "VAD" amount = 100'))
        self.assertEqual(wkr_air.count('owner = "WKR" amount = 50'), vad_air.count('owner = "VAD" amount = 50'))
        self.assertNotIn("central-air-command edge", wkr_air)

    def test_wkr_opening_air_reserve_and_fuel_are_bounded(self):
        self.assertIn("type = ADISCORD_fighter_airframe_2163 amount = 30 producer = WKR", self.wkr)
        self.assertIn("type = ADISCORD_cas_airframe_2170 amount = 15 producer = WKR", self.wkr)
        self.assertIn("add_fuel = 10000", self.wkr)
        self.assertNotIn("add_fuel = 15000", self.wkr)

    def test_wkr_opens_with_one_ready_mobile_group(self):
        mobile = re.search(
            r'division = "name = \\"1st Workerland Mobile Group\\".*?"\s*owner = WKR\s*count = (\d+)',
            self.wkr,
            re.S,
        )
        self.assertIsNotNone(mobile)
        self.assertEqual(mobile.group(1), "1")

    def test_balance_pass_keeps_wkr_home_guard_bounded(self):
        home = named_block(self.effects, "ADISCORD_vorkerland_ensure_wkr_home_guard")
        self.assertIn("add_manpower = 12000", home)
        self.assertIn("amount = 960 producer = WKR", home)
        self.assertEqual(home.count("count = 2"), 2)

    def test_theatre_package_is_not_rewritten_as_a_balance_shortcut(self):
        manifest = read("tools/lib/adiscord_vorkerland_theatre_manifest.py")
        self.assertIn('"WKR": 62', manifest)
        self.assertIn('"VAD": 66', manifest)
        self.assertIn('"TVA": 77', manifest)


if __name__ == "__main__":
    unittest.main()
