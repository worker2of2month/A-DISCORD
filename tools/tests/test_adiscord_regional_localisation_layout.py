from __future__ import annotations

import codecs
import re
import unittest
from collections import Counter
from pathlib import Path

from tools.builders.build_adiscord_ainholm_mandate import AIN_LOCALISATION


ROOT = Path(__file__).resolve().parents[2]
RUSSIAN = ROOT / "localisation" / "russian"
REMOVED_REGIONAL_FILES = (
    "ADISCORD_ainholm_l_russian.yml",
    "ADISCORD_inner_frontier_countries_l_russian.yml",
    "ADISCORD_northern_countries_l_russian.yml",
    "ADISCORD_southern_desert_l_russian.yml",
)
REMOVED_TYPED_FILES = (
    "ADISCORD_autonomy_l_russian.yml",
    "ADISCORD_economy_modifiers_l_russian.yml",
    "ADISCORD_event_ui_test_l_russian.yml",
    "ADISCORD_factions_l_russian.yml",
    "ADISCORD_menu_tooltips_l_russian.yml",
    "ADISCORD_minor_optimization_l_russian.yml",
    "ADISCORD_national_focuses_l_russian.yml",
    "ADISCORD_shared_actions_l_russian.yml",
    "ADISCORD_STP_ideas_l_russian.yml",
    "ADISCORD_test_wars_l_russian.yml",
    "ADISCORD_terrain_l_russian.yml",
    "ADISCORD_vorkerland_buildings_l_russian.yml",
    "ADISORD_minister_names_l_russian.yml",
    "ADISORD_minister_traits_l_russian.yml",
    "ADISORD_modifiers_l_russian.yml",
    "ADISORD_news_l_russian.yml",
    "countries_cosmetic_l_russian.yml",
    "ZZ_ADISCORD_exclusion_zone_l_russian.yml",
)
CONSOLIDATED_COUNTS = {
    "ADISCORD_inner_frontier_countries_l_russian": 93,
    "ADISCORD_northern_countries_l_russian": 179,
    "ADISCORD_southern_desert_l_russian": 99,
    "ADISCORD_autonomy_l_russian.yml": 9,
    "ADISCORD_economy_modifiers_l_russian.yml": 42,
    "ADISCORD_event_ui_test_l_russian.yml": 21,
    "ADISCORD_factions_l_russian.yml": 9,
    "ADISCORD_menu_tooltips_l_russian.yml: generic UI": 3,
    "ADISCORD_menu_tooltips_l_russian.yml: energy": 1,
    "ADISCORD_minor_optimization_l_russian.yml": 2,
    "ADISCORD_national_focuses_l_russian.yml: live STP bookmark focuses": 6,
    "ADISCORD_national_focuses_l_russian.yml: live VAL focuses": 50,
    "ADISCORD_shared_actions_l_russian.yml": 16,
    "ADISCORD_STP_ideas_l_russian.yml": 12,
    "ADISCORD_test_wars_l_russian.yml": 4,
    "ADISCORD_terrain_l_russian.yml": 4,
    "ADISCORD_vorkerland_buildings_l_russian.yml": 6,
    "ADISORD_minister_names_l_russian.yml": 168,
    "ADISORD_minister_traits_l_russian.yml": 168,
    "ADISORD_modifiers_l_russian.yml: ideology": 24,
    "ADISORD_modifiers_l_russian.yml: society development": 1,
    "ADISORD_news_l_russian.yml": 12,
    "countries_cosmetic_l_russian.yml": 34,
}


def localisation_keys(source: str) -> list[str]:
    return re.findall(r"(?m)^\s*([^#\s][^:]*):", source)


class RegionalLocalisationLayoutTests(unittest.TestCase):
    def test_regional_container_files_are_removed(self) -> None:
        for filename in REMOVED_REGIONAL_FILES + REMOVED_TYPED_FILES:
            self.assertFalse((RUSSIAN / filename).exists(), filename)

    def test_every_consolidated_key_survives_exactly_once(self) -> None:
        all_sources = {
            path: path.read_text(encoding="utf-8-sig", errors="strict")
            for path in RUSSIAN.glob("*.yml")
        }
        all_counts = Counter(
            key
            for source in all_sources.values()
            for key in localisation_keys(source)
            if key != "l_russian"
        )

        for marker, expected_count in CONSOLIDATED_COUNTS.items():
            moved_keys: list[str] = []
            begin = f"# BEGIN CONSOLIDATED: {marker}"
            end = f"# END CONSOLIDATED: {marker}"
            for source in all_sources.values():
                if begin not in source:
                    continue
                blocks = re.findall(
                    rf"(?ms)^\s*{re.escape(begin)}\n(.*?)^\s*{re.escape(end)}$",
                    source,
                )
                self.assertEqual(len(blocks), 1, marker)
                moved_keys.extend(localisation_keys(blocks[0]))
            self.assertEqual(len(moved_keys), expected_count, marker)
            self.assertTrue(all(all_counts[key] == 1 for key in moved_keys), marker)

    def test_ainholm_generated_keys_use_shared_bom_safe_files(self) -> None:
        expected_count = 0
        for path, entries in AIN_LOCALISATION.items():
            expected_count += len(entries)
            self.assertTrue(path.read_bytes().startswith(codecs.BOM_UTF8), path.name)
            source = path.read_text(encoding="utf-8-sig", errors="strict")
            for key, value in entries.items():
                self.assertEqual(
                    len(re.findall(rf'(?m)^\s*{re.escape(key)}:\s*"{re.escape(value)}"\s*$', source)),
                    1,
                    key,
                )
        self.assertEqual(expected_count, 11)


if __name__ == "__main__":
    unittest.main()
