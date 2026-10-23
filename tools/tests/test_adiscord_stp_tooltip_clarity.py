from __future__ import annotations

import re
import unittest
from pathlib import Path

from tools.tests.test_adiscord_stp_preparation import matches_conditions, scalar
from tools.validators.validate_adiscord_division_templates import parse_clausewitz


ROOT = Path(__file__).resolve().parents[2]
TOOLTIPS = ROOT / "localisation/russian/ADISCORD_STP_l_russian.yml"


class STPTooltipClarityTests(unittest.TestCase):
    def selected_text(self, name, facts):
        source = (
            ROOT / "common/scripted_localisation/ADISCORD_STP_scripted_loc.txt"
        ).read_text(encoding="utf-8-sig")
        definition = next(
            entry.value for entry in parse_clausewitz(source)
            if entry.key == "defined_text" and scalar(entry.value, "name") == name
        )
        for entry in definition:
            if entry.key != "text":
                continue
            trigger = next((e.value for e in entry.value if e.key == "trigger"), [])
            if matches_conditions(trigger, facts, "2"):
                return scalar(entry.value, "localization_key")
        self.fail(f"No text for {name}")

    def test_administration_countdown_uses_continuous_flag_age(self):
        flag = "STP_resistance_administration_asset"
        for age in range(22):
            with self.subTest(age=age):
                facts = {
                    ("2", "has_state_flag", flag): True,
                    ("2", "flag_days", flag): age,
                }
                asset = self.selected_text("STPGetAdministrationAsset", facts)
                if age >= 21:
                    self.assertEqual(asset, "STP_REGION_ASSET_ADMINISTRATION_READY")
                else:
                    self.assertEqual(asset, "STP_REGION_ASSET_ADMINISTRATION_RECENT")
                    self.assertEqual(
                        self.selected_text("STPGetAdministrationDaysRemaining", facts),
                        f"STP_REGION_ADMIN_DAYS_{21 - age}",
                    )
        self.assertEqual(
            self.selected_text("STPGetAdministrationAsset", {}),
            "STP_REGION_EMPTY_LINE",
        )

    def test_ready_cache_and_pending_delivery_can_both_be_reported(self):
        facts = {
            ("2", "variable", "STP_cw_cached_rifles"): 480,
            ("2", "variable", "STP_cw_pending_rifles"): 960,
        }
        self.assertEqual(self.selected_text("STPGetRifleCache", facts), "STP_CW_CACHE_READY")
        self.assertEqual(self.selected_text("STPGetPendingRifleCache", facts), "STP_CW_CACHE_PENDING")
        facts[("2", "variable", "STP_cw_cached_rifles")] = 0
        self.assertEqual(self.selected_text("STPGetRifleCache", facts), "STP_CW_CACHE_PENDING")
        facts[("2", "variable", "STP_cw_pending_rifles")] = 0
        self.assertEqual(self.selected_text("STPGetRifleCache", facts), "STP_REGION_EMPTY_LINE")

    def test_concession_is_reported_before_waiting_but_never_overrides_transfer(self):
        facts = {
            ("2", "has_state_flag", "STP_inspection_concession_prepared"): True,
            ("2", "STP_region_resistance_entrenched", "yes"): True,
            ("2", "has_state_flag", "STP_resistance_administration_asset"): True,
        }
        self.assertEqual(
            self.selected_text("STPGetCivilWarForecastReason", facts),
            "STP_CW_FORECAST_REASON_CONCESSION",
        )
        facts[("2", "STP_cw_region_goes_to_resistance", "yes")] = True
        facts[("2", "STP_region_resistance_overwhelming", "yes")] = True
        self.assertEqual(
            self.selected_text("STPGetCivilWarForecastReason", facts),
            "STP_CW_FORECAST_REASON_OVERWHELMING",
        )

    def test_niansas_transfer_requirements_are_explicit_at_every_decision_point(
        self,
    ) -> None:
        self.assertTrue(TOOLTIPS.is_file(), "missing canonical STP localisation")
        self.assertTrue(
            TOOLTIPS.read_bytes().startswith(b"\xef\xbb\xbf"),
            "tooltip override must keep UTF-8 BOM",
        )
        localisation = TOOLTIPS.read_text(encoding="utf-8-sig")

        required_keys = (
            "STP_regions_panel_tt",
            "STP_region_3_map_tt",
            "STP_cw_repair_niansas_desc",
            "STP_cw_port_budget_desc",
        )
        for key in required_keys:
            with self.subTest(key=key):
                self.assertEqual(
                    len(re.findall(rf"(?m)^\s*{re.escape(key)}:\s*", localisation)), 1
                )

        for phrase in (
            "90%",
            "21 день",
            "выше §Y55%§!",
            "Дорога через Ниансас",
            "Перехватить областное управление",
            "положительного перевеса легитимности",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, localisation)

        niansas_tooltip = re.search(
            r'(?ms)^\s*STP_region_3_map_tt:\s*"(?P<body>.*?)"\s*$', localisation
        )
        self.assertIsNotNone(niansas_tooltip)
        body = niansas_tooltip.group("body")
        self.assertIn("§YТекущий прогноз при восстании:§!", body)
        self.assertIn("[3.STPGetCivilWarForecast]", body)
        self.assertIn("[3.STPGetCivilWarForecastReason]", body)
        self.assertIn("[3.STPGetAdministrationAsset]", body)


if __name__ == "__main__":
    unittest.main()
