from __future__ import annotations

import re
import unittest
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
ICON = ROOT / "gfx/interface/ideologies/vorkerism_group.png"


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8-sig")


class WrkIdeologyContractTests(unittest.TestCase):
    def test_vorkerism_is_a_non_random_pragmatist_subtype(self) -> None:
        ideologies = read("common/ideologies/00_ideologies.txt")
        pragmatism = re.search(
            r"(?s)\bpragmatism\s*=\s*\{.*?\btypes\s*=\s*\{(.*?)\n\s*\}\s*\n\s*dynamic_faction_names",
            ideologies,
        )
        self.assertIsNotNone(pragmatism)
        self.assertRegex(
            pragmatism.group(1),
            r"(?s)\bvorkerism\s*=\s*\{.*?can_be_randomly_selected\s*=\s*no.*?\}",
        )

    def test_nikita_worcker_uses_vorkerism(self) -> None:
        characters = read("common/characters/WRK.txt")
        nikita = re.search(
            r"(?s)\bWRK_Nikita_Worcker\s*=\s*\{(.*?)\n\s*\}\s*\n\s*WRK_Vlad_Petrichev",
            characters,
        )
        self.assertIsNotNone(nikita)
        self.assertIn("ideology = vorkerism", nikita.group(1))

    def test_icon_was_renamed_and_keeps_source_quality(self) -> None:
        self.assertTrue(ICON.is_file(), ICON)
        self.assertFalse((ICON.parent / "wrk_ideology.png").exists())
        with Image.open(ICON) as image:
            self.assertEqual(image.size, (183, 189))
            self.assertEqual(image.mode, "RGBA")

    def test_both_vorkerism_sprites_resolve_to_the_renamed_icon(self) -> None:
        gfx = read("interface/ADISCORD_ideology.gfx")
        self.assertIn('name = "GFX_ideology_vorkerism"', gfx)
        self.assertIn('name = "GFX_ideology_vorkerism_countryview"', gfx)
        self.assertNotRegex(
            gfx,
            r"(?s)corneredTileSpriteType\s*=\s*\{[^}]*GFX_ideology_vorkerism",
        )
        self.assertEqual(
            gfx.count('texturefile = "gfx/interface/ideologies/vorkerism_group.png"'),
            2,
        )

    def test_country_view_routes_name_icon_and_description(self) -> None:
        scripted_loc = read("common/scripted_localisation/ADISCORD_ideologies.txt")
        scripted_gui = read("common/scripted_guis/CountryView_ScriptedGui.txt")
        gui = read("interface/countrypoliticsview.gui")
        self.assertIn("has_country_leader_ideology = vorkerism", scripted_loc)
        self.assertIn("localization_key = vorkerism", scripted_loc)
        self.assertIn("ideology_icon_vorkerism_visible", scripted_gui)
        self.assertIn("NOT = { has_country_leader_ideology = vorkerism }", scripted_gui)
        self.assertIn('name = "ideology_icon_vorkerism"', gui)
        self.assertIn('spriteType = "GFX_ideology_vorkerism_countryview"', gui)
        self.assertIn("scale = 0.66", gui)
        self.assertIn('pdx_tooltip = "vorkerism_desc"', gui)

    def test_russian_localisation_explains_structural_instability(self) -> None:
        localisation = read("localisation/russian/parties_l_russian.yml")
        self.assertIn('vorkerism: "Революционный конституционализм"', localisation)
        description = re.search(r'^\s*vorkerism_desc:\s*"(.+)"$', localisation, re.MULTILINE)
        self.assertIsNotNone(description)
        for concept in (
            "неустойчив",
            "чрезвычайные полномочия",
            "замороженные выборы",
            "собственными администрациями",
            "вооружёнными силами",
        ):
            self.assertIn(concept, description.group(1))

    def test_russian_localisation_keeps_utf8_bom(self) -> None:
        path = ROOT / "localisation/russian/parties_l_russian.yml"
        self.assertTrue(path.read_bytes().startswith(b"\xef\xbb\xbf"))

    def test_wrk_lore_uses_the_visible_ideology_name(self) -> None:
        profile = read("docs/lore/countries/WRK.md")
        index = read("docs/lore/countries.md")
        self.assertIn(
            "революционный конституционализм (подтип прагматизма)",
            profile,
        )
        self.assertIn(
            "Партия Перехода Воркерланда, революционный конституционализм",
            index,
        )


if __name__ == "__main__":
    unittest.main()
