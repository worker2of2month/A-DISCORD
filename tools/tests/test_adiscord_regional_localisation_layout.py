from __future__ import annotations

import codecs
import re
import unittest
from collections import Counter
from pathlib import Path

from tools.builders.build_adiscord_ainholm_mandate import AIN_LOCALISATION
from tools.validators.validate_adiscord_division_templates import parse_clausewitz


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
CONSOLIDATED_MARKERS = (
    "ADISCORD_inner_frontier_countries_l_russian",
    "ADISCORD_northern_countries_l_russian",
    "ADISCORD_southern_desert_l_russian",
    "ADISCORD_autonomy_l_russian.yml",
    "ADISCORD_economy_modifiers_l_russian.yml",
    "ADISCORD_event_ui_test_l_russian.yml",
    "ADISCORD_factions_l_russian.yml",
    "ADISCORD_menu_tooltips_l_russian.yml: generic UI",
    "ADISCORD_menu_tooltips_l_russian.yml: energy",
    "ADISCORD_national_focuses_l_russian.yml: live VAL focuses",
    "ADISCORD_shared_actions_l_russian.yml",
    "ADISCORD_test_wars_l_russian.yml",
    "ADISCORD_terrain_l_russian.yml",
    "ADISCORD_vorkerland_buildings_l_russian.yml",
    "ADISORD_minister_names_l_russian.yml",
    "ADISORD_minister_traits_l_russian.yml",
    "ADISORD_modifiers_l_russian.yml: ideology",
    "ADISORD_modifiers_l_russian.yml: society development",
    "ADISORD_news_l_russian.yml",
    "countries_cosmetic_l_russian.yml",
)
REGIONAL_FAMILIES = ("inner_frontier", "northern", "southern_desert")
SHARED_IDEAS = (
    "ADISCORD_non_participating_minor_optimization",
    "STP_fading_father",
    "STP_hedonism_with_no_bondaries",
    "STP_hidden_slaves_trade",
    "STP_legalize",
    "STP_worldwide_famous_tourist_destination",
)


def localisation_keys(source: str) -> list[str]:
    return re.findall(r"(?m)^\s*([^#\s][^:]*):", source)


def script_block(items, key):
    matches = [entry.value for entry in items if entry.key == key]
    if len(matches) != 1 or not isinstance(matches[0], list):
        raise AssertionError(f"Expected one script block: {key}")
    return matches[0]


def script_name(items, key, default):
    matches = [entry.value for entry in items if entry.key == key]
    if not matches:
        return default
    if len(matches) != 1 or not isinstance(matches[0], str):
        raise AssertionError(f"Expected one localisation reference: {key}")
    return matches[0]


class RegionalLocalisationLayoutTests(unittest.TestCase):
    def test_stelander_localisation_uses_one_country_file(self) -> None:
        for language in ("russian", "english"):
            with self.subTest(language=language):
                directory = ROOT / "localisation" / language
                path = directory / f"ADISCORD_STP_l_{language}.yml"
                self.assertEqual(list(directory.glob("ADISCORD_STP*.yml")), [path])
                self.assertTrue(path.read_bytes().startswith(codecs.BOM_UTF8))
                keys = localisation_keys(path.read_text(encoding="utf-8-sig"))
                self.assertEqual(keys.count(f"l_{language}"), 1)
                self.assertEqual(len(keys), len(set(keys)))
                all_counts = Counter(
                    key
                    for other in directory.glob("*.yml")
                    for key in localisation_keys(other.read_text(encoding="utf-8-sig"))
                )
                for focus in (
                    "STP_bookmark_support_shabrat",
                    "STP_bookmark_last_banquet",
                    "STP_bookmark_support_party",
                    "STP_pc_heg_administrations",
                    "STP_pc_heg_northern_administration",
                    "STP_pc_heg_cannibal_campaign",
                ):
                    for key in (focus, f"{focus}_desc"):
                        self.assertIn(key, keys)
                        self.assertEqual(all_counts[key], 1, key)

    def test_regional_container_files_are_removed(self) -> None:
        for filename in REMOVED_REGIONAL_FILES + REMOVED_TYPED_FILES:
            self.assertFalse((RUSSIAN / filename).exists(), filename)

    def test_consolidated_sections_have_unique_keys(self) -> None:
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

        for marker in CONSOLIDATED_MARKERS:
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
                self.assertEqual(source.count(begin), 1, marker)
                self.assertEqual(source.count(end), 1, marker)
                self.assertEqual(len(blocks), 1, marker)
                moved_keys.extend(localisation_keys(blocks[0]))
            self.assertTrue(moved_keys, marker)
            for key in moved_keys:
                self.assertEqual(all_counts[key], 1, key)

    def test_live_regional_definitions_keep_unique_localisation(self) -> None:
        # Content may move between sections; script references define required keys.
        required = {
            key
            for idea in SHARED_IDEAS
            for key in (idea, f"{idea}_desc")
        }
        required.update((
            "STP_hedonism_army_restriction_reason",
            "STP_hedonism_army_restriction_tt",
        ))
        for family in REGIONAL_FAMILIES:
            path = ROOT / f"common/ideas/ADISCORD_{family}_ideas.txt"
            ideas = script_block(
                parse_clausewitz(path.read_text(encoding="utf-8-sig")), "ideas"
            )
            for category in ideas:
                self.assertIsInstance(category.value, list, path)
                self.assertTrue(category.value, path)
                for idea in category.value:
                    name = script_name(idea.value, "name", idea.key)
                    desc = script_name(idea.value, "desc", f"{name}_desc")
                    required.update((name, desc))

            path = ROOT / f"common/characters/ADISCORD_{family}_characters.txt"
            characters = script_block(
                parse_clausewitz(path.read_text(encoding="utf-8-sig")), "characters"
            )
            self.assertTrue(characters, path)
            for character in characters:
                required.add(script_name(character.value, "name", character.key))
                for role in character.value:
                    if isinstance(role.value, list):
                        required.update(
                            entry.value for entry in role.value if entry.key == "desc"
                        )

            path = ROOT / f"common/country_leader/ADISCORD_{family}_traits.txt"
            traits = script_block(
                parse_clausewitz(path.read_text(encoding="utf-8-sig")), "leader_traits"
            )
            self.assertTrue(traits, path)
            required.update(trait.key for trait in traits)

        for language in ("russian", "english"):
            counts = Counter(
                key
                for path in (ROOT / "localisation" / language).glob("*.yml")
                for key in localisation_keys(path.read_text(encoding="utf-8-sig"))
            )
            for key in sorted(required):
                with self.subTest(language=language, key=key):
                    self.assertEqual(counts[key], 1)

    def test_ainholm_generated_keys_use_shared_bom_safe_files(self) -> None:
        expected_count = 0
        for path, entries in AIN_LOCALISATION.items():
            expected_count += len(entries)
            self.assertTrue(path.read_bytes().startswith(codecs.BOM_UTF8), path.name)
            source = path.read_text(encoding="utf-8-sig", errors="strict")
            for key, value in entries.items():
                self.assertEqual(
                    len(
                        re.findall(
                            rf'(?m)^\s*{re.escape(key)}:\s*"{re.escape(value)}"\s*$',
                            source,
                        )
                    ),
                    1,
                    key,
                )
        self.assertEqual(expected_count, 11)


if __name__ == "__main__":
    unittest.main()
