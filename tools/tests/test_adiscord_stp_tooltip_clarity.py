from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
TOOLTIPS = ROOT / "localisation/replace/ADISCORD_STP_tooltips_l_russian.yml"


class STPTooltipClarityTests(unittest.TestCase):
    def test_niansas_transfer_requirements_are_explicit_at_every_decision_point(self) -> None:
        self.assertTrue(TOOLTIPS.is_file(), "missing dedicated STP tooltip override localisation")
        self.assertTrue(TOOLTIPS.read_bytes().startswith(b"\xef\xbb\xbf"), "tooltip override must keep UTF-8 BOM")
        localisation = TOOLTIPS.read_text(encoding="utf-8-sig")

        required_keys = (
            "STP_regions_panel_tt",
            "STP_region_3_map_tt",
            "STP_cw_repair_niansas_desc",
            "STP_cw_port_budget_desc",
        )
        for key in required_keys:
            with self.subTest(key=key):
                self.assertEqual(len(re.findall(rf"(?m)^\s*{re.escape(key)}:\s*", localisation)), 1)

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
