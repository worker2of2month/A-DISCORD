from __future__ import annotations

import re
import unittest
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
PRE_CIVIL_WAR_ICON = ROOT / "gfx/interface/ideologies/vorkerism_pre_civil_war.png"
NEO_ICON = ROOT / "gfx/interface/ideologies/vorkerism_group.png"


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8-sig")


class WrkIdeologyContractTests(unittest.TestCase):
    def test_both_vorkerism_versions_are_non_random_pragmatist_subtypes(self) -> None:
        ideologies = read("common/ideologies/00_ideologies.txt")
        pragmatism = re.search(
            r"(?s)\bpragmatism\s*=\s*\{.*?\btypes\s*=\s*\{(.*?)\n\s*\}\s*\n\s*dynamic_faction_names",
            ideologies,
        )
        self.assertIsNotNone(pragmatism)
        for subtype in ("vorkerism", "neo_vorkerism"):
            with self.subTest(subtype=subtype):
                self.assertRegex(
                    pragmatism.group(1),
                    rf"(?s)\b{subtype}\s*=\s*\{{.*?can_be_randomly_selected\s*=\s*no.*?\}}",
                )

    def test_nikita_worcker_uses_vorkerism(self) -> None:
        characters = read("common/characters/WRK.txt")
        nikita = re.search(
            r"(?s)\bWRK_Nikita_Worcker\s*=\s*\{(.*?)\n\s*\}\s*\n\s*WRK_Vlad_Petrichev",
            characters,
        )
        self.assertIsNotNone(nikita)
        self.assertIn("ideology = vorkerism", nikita.group(1))

    def test_icons_have_semantic_names_and_keep_source_quality(self) -> None:
        for icon in (PRE_CIVIL_WAR_ICON, NEO_ICON):
            with self.subTest(icon=icon.name):
                self.assertTrue(icon.is_file(), icon)
                with Image.open(icon) as image:
                    self.assertEqual(image.size, (183, 189))
                    self.assertEqual(image.mode, "RGBA")
        self.assertFalse((PRE_CIVIL_WAR_ICON.parent / "wrk_ideology.png").exists())
        self.assertFalse((PRE_CIVIL_WAR_ICON.parent / "wrk_ideology_2.png").exists())

    def test_both_versions_have_small_and_country_view_sprites(self) -> None:
        gfx = read("interface/ADISCORD_ideology.gfx")
        expected_sizes = {
            "GFX_ideology_vorkerism": 70,
            "GFX_ideology_neo_vorkerism": 70,
            "GFX_ideology_vorkerism_countryview": 125,
            "GFX_ideology_neo_vorkerism_countryview": 125,
        }
        for sprite, size in expected_sizes.items():
            with self.subTest(sprite=sprite):
                block = re.search(
                    rf'(?s)(corneredTileSpriteType|spriteType)\s*=\s*\{{'
                    rf'(?:(?!(?:corneredTileSpriteType|spriteType)\s*=).)*'
                    rf'name\s*=\s*"{sprite}"'
                    rf'(?:(?!(?:corneredTileSpriteType|spriteType)\s*=).)*?\n\s*\}}',
                    gfx,
                )
                self.assertIsNotNone(block)
                self.assertEqual(block.group(1), "corneredTileSpriteType")
                self.assertRegex(block.group(0), rf"(?s)size\s*=\s*\{{\s*x\s*=\s*{size}\s+y\s*=\s*{size}\s*\}}")
        self.assertEqual(
            gfx.count('texturefile = "gfx/interface/ideologies/vorkerism_group.png"'),
            2,
        )
        self.assertEqual(
            gfx.count('texturefile = "gfx/interface/ideologies/vorkerism_pre_civil_war.png"'),
            2,
        )

    def test_country_view_routes_name_icon_and_description(self) -> None:
        scripted_loc = read("common/scripted_localisation/ADISCORD_ideologies.txt")
        scripted_gui = read("common/scripted_guis/CountryView_ScriptedGui.txt")
        gui = read("interface/countrypoliticsview.gui")
        self.assertIn("has_country_leader_ideology = vorkerism", scripted_loc)
        self.assertIn("has_country_leader_ideology = neo_vorkerism", scripted_loc)
        self.assertIn("localization_key = vorkerism", scripted_loc)
        self.assertIn("localization_key = neo_vorkerism", scripted_loc)
        self.assertIn("ideology_icon_vorkerism_visible", scripted_gui)
        self.assertIn("ideology_icon_neo_vorkerism_visible", scripted_gui)
        self.assertIn("NOT = { has_country_leader_ideology = vorkerism }", scripted_gui)
        self.assertIn("NOT = { has_country_leader_ideology = neo_vorkerism }", scripted_gui)
        self.assertIn('name = "ideology_icon_vorkerism"', gui)
        self.assertIn('name = "ideology_icon_neo_vorkerism"', gui)
        self.assertIn('spriteType = "GFX_ideology_vorkerism_countryview"', gui)
        self.assertIn('spriteType = "GFX_ideology_neo_vorkerism_countryview"', gui)
        for subtype in ("vorkerism", "neo_vorkerism"):
            with self.subTest(subtype=subtype):
                icon = re.search(
                    rf'(?s)iconType\s*=\s*\{{\s*name\s*=\s*"ideology_icon_{subtype}"(.*?)\n\s*\}}',
                    gui,
                )
                self.assertIsNotNone(icon)
                self.assertNotIn("scale =", icon.group(1))
        self.assertIn('pdx_tooltip = "vorkerism_desc"', gui)
        self.assertIn('pdx_tooltip = "neo_vorkerism_desc"', gui)

    def test_collapse_promotes_surviving_worker_to_neo_vorkerism(self) -> None:
        effects = read("common/scripted_effects/ADISCORD_vorkerland_collapse_effects.txt")
        on_actions = read("common/on_actions/01_ADISCORD_vorkerland_collapse_on_actions.txt")
        claimant_cosmetics = re.search(
            r"(?s)ADISCORD_vorkerland_apply_claimant_cosmetics\s*=\s*\{(.*?)\n\}",
            effects,
        )
        self.assertIsNotNone(claimant_cosmetics)
        worker_survives = re.search(
            r"(?s)has_global_flag\s*=\s*ADISCORD_vorkerland_worker_safe_with_loyalists.*?"
            r"set_country_leader_ideology\s*=\s*neo_vorkerism",
            claimant_cosmetics.group(1),
        )
        self.assertIsNotNone(worker_survives)
        self.assertRegex(
            on_actions,
            r"(?s)has_global_flag\s*=\s*ADISCORD_vorkerland_collapse_started.*?"
            r"has_global_flag\s*=\s*ADISCORD_vorkerland_worker_safe_with_loyalists.*?"
            r"has_country_leader_ideology\s*=\s*vorkerism.*?"
            r"set_country_leader_ideology\s*=\s*neo_vorkerism",
        )

    def test_russian_localisation_explains_structural_instability(self) -> None:
        localisation = read("localisation/russian/parties_l_russian.yml")
        self.assertIn('vorkerism: "Воркеризм"', localisation)
        self.assertIn('neo_vorkerism: "Неоворкеризм"', localisation)
        pre_description = re.search(r'^\s*vorkerism_desc:\s*"(.+)"$', localisation, re.MULTILINE)
        neo_description = re.search(r'^\s*neo_vorkerism_desc:\s*"(.+)"$', localisation, re.MULTILINE)
        self.assertIsNotNone(pre_description)
        self.assertIsNotNone(neo_description)
        pre_text = pre_description.group(1).lower()
        for concept in (
            "неустойчив",
            "первая революция не завершена",
            "переход не имеет конечной даты",
            "чрезвычайные полномочия",
            "откладывать выборы",
            "собственными администрациями",
            "вооружёнными силами",
        ):
            self.assertIn(concept, pre_text)
        for concept in (
            "новой революции",
            "военное управление",
            "культ Уоркера",
            "осаждённый режим",
        ):
            self.assertIn(concept, neo_description.group(1))

    def test_russian_localisation_keeps_utf8_bom(self) -> None:
        path = ROOT / "localisation/russian/parties_l_russian.yml"
        self.assertTrue(path.read_bytes().startswith(b"\xef\xbb\xbf"))

    def test_wrk_lore_uses_the_visible_ideology_name(self) -> None:
        localisation = read("localisation/russian/parties_l_russian.yml")
        profile = read("docs/lore/countries/WRK.md")
        index = read("docs/lore/countries.md")
        self.assertIn(
            "воркеризм (подтип прагматизма)",
            profile,
        )
        self.assertIn("переходит к неоворкеризму", profile)
        self.assertIn(
            "Партия Перехода Воркерланда, воркеризм",
            index,
        )
        retired_names = (
            "конституционал" + "изм",
            "революционный федера" + "лизм",
            "доктрина непрерывного пере" + "хода",
        )
        for retired_name in retired_names:
            self.assertNotIn(retired_name, localisation.lower())
            self.assertNotIn(retired_name, profile.lower())
            self.assertNotIn(retired_name, index.lower())


if __name__ == "__main__":
    unittest.main()
