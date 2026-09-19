from __future__ import annotations
from tools.lib.on_actions import read_country_on_actions

import re
import unittest
from pathlib import Path

from PIL import Image


from tools.lib.paths import source_section


ROOT = Path(__file__).resolve().parents[2]
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
        effects = source_section(read("common/scripted_effects/ADISCORD_vorkerland_effects.txt"), 'collapse_effects')
        on_actions = read_country_on_actions("common/on_actions/01_ADISCORD_vorkerland_collapse_on_actions.txt", 'vorkerland_collapse')
        claimant_cosmetics = re.search(
            r"(?s)ADISCORD_vorkerland_apply_claimant_cosmetics\s*=\s*\{(.*?)\n\}",
            effects,
        )
        nikita_promotion = re.search(
            r"(?s)ADISCORD_vorkerland_promote_nikita_worcker\s*=\s*\{(.*?)\n\}",
            effects,
        )
        self.assertIsNotNone(claimant_cosmetics)
        self.assertIsNotNone(nikita_promotion)
        worker_survives = re.search(
            r"(?s)has_global_flag\s*=\s*ADISCORD_vorkerland_worker_safe_with_loyalists.*?"
            r"ADISCORD_vorkerland_promote_nikita_worcker\s*=\s*yes",
            claimant_cosmetics.group(1),
        )
        self.assertIsNotNone(worker_survives)
        self.assertIn("character = WRK_Nikita_Worcker", nikita_promotion.group(1))
        self.assertEqual(nikita_promotion.group(1).count("ideology = neo_vorkerism"), 2)
        self.assertNotIn("WKR_Worker_Emergency_Presidium", claimant_cosmetics.group(1))
        self.assertNotIn("set_country_leader_ideology = neo_vorkerism", on_actions)
        self.assertNotIn("Save-compatible ideology migration", on_actions)

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

    def test_nikita_election_win_keeps_neo_vorkerism(self) -> None:
        from tools.validators.validate_adiscord_vorkerland_collapse import named_block

        effects = source_section(
            read("common/scripted_effects/ADISCORD_vorkerland_effects.txt"),
            "phase_effects",
        )
        elect_worker = named_block(effects, "ADISCORD_vorkerland_wrk_elect_worcker")
        usurp = named_block(effects, "ADISCORD_vorkerland_wrk_usurp_mandate")
        self.assertIn("ideology = neo_vorkerism", elect_worker)
        self.assertIn("ideology = neo_vorkerism", usurp)
        self.assertIn("GFX_portrait_WRK_Nikita_Worcker_victory", usurp)
        self.assertNotIn("GFX_portrait_WRK_Nikita_Worcker_victory", elect_worker)


class VadlAndBagleyIdeologyContractTests(unittest.TestCase):
    IMPERIAL_ICON = ROOT / "gfx/interface/ideologies/imperial_restorationism_group.png"
    ACCELERATION_ICON = ROOT / "gfx/interface/ideologies/utilitarian_accelerationism_group.png"

    def test_subtypes_are_non_random_under_their_groups(self) -> None:
        ideologies = read("common/ideologies/00_ideologies.txt")
        utilitarism = re.search(
            r"(?s)\butilitarism\s*=\s*\{.*?\btypes\s*=\s*\{(.*?)\n\s*\}\s*\n\s*dynamic_faction_names",
            ideologies,
        )
        pragmatism = re.search(
            r"(?s)\bpragmatism\s*=\s*\{.*?\btypes\s*=\s*\{(.*?)\n\s*\}\s*\n\s*dynamic_faction_names",
            ideologies,
        )
        self.assertIsNotNone(utilitarism)
        self.assertIsNotNone(pragmatism)
        self.assertRegex(
            utilitarism.group(1),
            r"(?s)\butilitarian_accelerationism\s*=\s*\{.*?can_be_randomly_selected\s*=\s*no.*?\}",
        )
        self.assertRegex(
            pragmatism.group(1),
            r"(?s)\bimperial_restorationism\s*=\s*\{.*?can_be_randomly_selected\s*=\s*no.*?\}",
        )

    def test_vlad_and_bagley_use_the_new_subtypes(self) -> None:
        from tools.validators.validate_adiscord_vorkerland_collapse import named_block

        vlad = re.search(
            r"(?s)\bWRK_Vlad_Petrichev\s*=\s*\{(.*?)\n\s*\}\s*\n\s*WRK_Richard_Gordon",
            read("common/characters/WRK.txt"),
        )
        self.assertIsNotNone(vlad)
        self.assertIn("ideology = imperial_restorationism", vlad.group(1))
        effects = source_section(
            read("common/scripted_effects/ADISCORD_vorkerland_effects.txt"),
            "collapse_effects",
        )
        phase_effects = source_section(
            read("common/scripted_effects/ADISCORD_vorkerland_effects.txt"),
            "phase_effects",
        )
        self.assertIn(
            "ideology = utilitarian_accelerationism",
            named_block(effects, "ADISCORD_vorkerland_promote_anton_bagley"),
        )
        self.assertIn(
            "ideology = utilitarian_accelerationism",
            named_block(phase_effects, "ADISCORD_vorkerland_repair_claimant_identities"),
        )
        self.assertIn(
            "ideology = imperial_restorationism",
            named_block(phase_effects, "ADISCORD_vorkerland_repair_claimant_identities"),
        )
        self.assertIn(
            "ideology = imperial_restorationism",
            named_block(phase_effects, "ADISCORD_vorkerland_form_wrk_from_vad"),
        )

    def test_icons_have_semantic_names_and_keep_source_quality(self) -> None:
        for icon in (self.IMPERIAL_ICON, self.ACCELERATION_ICON):
            with self.subTest(icon=icon.name):
                self.assertTrue(icon.is_file(), icon)
                with Image.open(icon) as image:
                    self.assertEqual(image.size, (183, 189))
                    self.assertEqual(image.mode, "RGBA")
        leftovers = (
            "Имперская идеология Вадла.png",
            "аксилирационизм утилитарный.png",
        )
        for leftover in leftovers:
            self.assertFalse((self.IMPERIAL_ICON.parent / leftover).exists(), leftover)

    def test_both_versions_have_small_and_country_view_sprites(self) -> None:
        gfx = read("interface/ADISCORD_ideology.gfx")
        expected_sizes = {
            "GFX_ideology_imperial_restorationism": 70,
            "GFX_ideology_utilitarian_accelerationism": 70,
            "GFX_ideology_imperial_restorationism_countryview": 125,
            "GFX_ideology_utilitarian_accelerationism_countryview": 125,
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
            gfx.count('texturefile = "gfx/interface/ideologies/imperial_restorationism_group.png"'),
            2,
        )
        self.assertEqual(
            gfx.count('texturefile = "gfx/interface/ideologies/utilitarian_accelerationism_group.png"'),
            2,
        )

    def test_country_view_routes_name_icon_and_description(self) -> None:
        scripted_loc = read("common/scripted_localisation/ADISCORD_ideologies.txt")
        scripted_gui = read("common/scripted_guis/CountryView_ScriptedGui.txt")
        gui = read("interface/countrypoliticsview.gui")
        for subtype in ("imperial_restorationism", "utilitarian_accelerationism"):
            with self.subTest(subtype=subtype):
                self.assertIn(f"has_country_leader_ideology = {subtype}", scripted_loc)
                self.assertIn(f"localization_key = {subtype}", scripted_loc)
                self.assertIn(f"ideology_icon_{subtype}_visible", scripted_gui)
                self.assertIn(f"NOT = {{ has_country_leader_ideology = {subtype} }}", scripted_gui)
                self.assertIn(f'name = "ideology_icon_{subtype}"', gui)
                self.assertIn(f'spriteType = "GFX_ideology_{subtype}_countryview"', gui)
                self.assertIn(f'pdx_tooltip = "{subtype}_desc"', gui)
                icon = re.search(
                    rf'(?s)iconType\s*=\s*\{{\s*name\s*=\s*"ideology_icon_{subtype}"(.*?)\n\s*\}}',
                    gui,
                )
                self.assertIsNotNone(icon)
                self.assertNotIn("scale =", icon.group(1))

    def test_russian_localisation_names_the_new_courses(self) -> None:
        localisation = read("localisation/russian/parties_l_russian.yml")
        self.assertIn('imperial_restorationism: "Имперский реставрационизм"', localisation)
        self.assertIn('utilitarian_accelerationism: "Утилитарный акселерационизм"', localisation)
        imperial = re.search(r'^\s*imperial_restorationism_desc:\s*"(.+)"$', localisation, re.MULTILINE)
        acceleration = re.search(r'^\s*utilitarian_accelerationism_desc:\s*"(.+)"$', localisation, re.MULTILINE)
        self.assertIsNotNone(imperial)
        self.assertIsNotNone(acceleration)
        self.assertIn("иерархия", imperial.group(1).lower())
        self.assertIn("поставк", acceleration.group(1).lower())
        path = ROOT / "localisation/russian/parties_l_russian.yml"
        self.assertTrue(path.read_bytes().startswith(b"\xef\xbb\xbf"))


if __name__ == "__main__":
    unittest.main()
