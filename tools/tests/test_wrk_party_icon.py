from __future__ import annotations

import re
import unittest
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[2]
VANILLA_ROOT = Path("Z:/SteamLibrary/steamapps/common/Hearts of Iron IV")
ICON = ROOT / "gfx/texticons/adiscord/parties/WRK/WRK_worker_revolutionary_party.png"
SPRITE = "GFX_WRK_worker_revolutionary_party_texticon"
IDEOLOGY_PARTIES = {
    "humanism": "Временное Национальное Собрание",
    "utilitarism": "Комитет Реконструкции Воркерланда",
    "chauvinism": "Движение Возрождения Воркерланда",
    "anarchism": "Федерация Советов Воркерланда",
    "technocracy": "Совет Инженеров Воркерланда",
    "etatism": "Служба Государства Воркерланда",
    "hedonism": "Партия Новой Роскоши",
}
IDEOLOGY_TEXTURES = {
    "humanism": "gfx/texticons/adiscord/parties/generic/humanism/humanism_civic_party.png",
    "utilitarism": "gfx/texticons/adiscord/parties/generic/utilitarism/utilitarism_planning_party.png",
    "chauvinism": "gfx/texticons/adiscord/parties/generic/chauvinism/chauvinism_national_front_party.png",
    "anarchism": "gfx/texticons/adiscord/parties/generic/anarchism/anarchism_communal_federation_party.png",
    "technocracy": "gfx/texticons/adiscord/parties/generic/technocracy/technocracy_engineering_directorate_party.png",
    "etatism": "gfx/texticons/adiscord/parties/generic/etatism/etatism_emergency_administration_party.png",
    "hedonism": "gfx/texticons/adiscord/parties/generic/hedonism/hedonism_guild_elite_party.png",
}


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8-sig")


class WrkPartyIconContractTests(unittest.TestCase):
    def test_party_icon_has_texticon_dimensions_and_alpha(self) -> None:
        self.assertTrue(ICON.is_file(), ICON)
        with Image.open(ICON) as image:
            self.assertEqual(image.size, (25, 25))
            self.assertEqual(image.mode, "RGBA")

    def test_wrk_sprite_resolves_to_party_icon(self) -> None:
        gfx = read("interface/parties_texticons.gfx")
        block = re.search(
            rf'(?s)spriteType\s*=\s*\{{(?:(?!spriteType).)*name\s*=\s*"{SPRITE}"(?:(?!spriteType).)*\}}',
            gfx,
        )
        self.assertIsNotNone(block)
        self.assertIn(
            'texturefile = "gfx/texticons/adiscord/parties/WRK/WRK_worker_revolutionary_party.png"',
            block.group(0),
        )
        self.assertIn("legacy_lazy_load = no", block.group(0))

    def test_remaining_wrk_ideologies_have_drop_in_sprites_and_loc(self) -> None:
        gfx = read("interface/ADISCORD_wrk_party_texticons.gfx")
        localisation = read("localisation/russian/parties_l_russian.yml")
        for ideology, name in IDEOLOGY_PARTIES.items():
            sprite = f"GFX_WRK_{ideology}_party_texticon"
            texture = IDEOLOGY_TEXTURES[ideology]
            with self.subTest(ideology=ideology):
                block = re.search(
                    rf'(?s)spriteType\s*=\s*\{{(?:(?!spriteType).)*name\s*=\s*"{sprite}"(?:(?!spriteType).)*\}}',
                    gfx,
                )
                self.assertIsNotNone(block)
                self.assertIn(f'texturefile = "{texture}"', block.group(0))
                self.assertIn("legacy_lazy_load = no", block.group(0))
                expected = f"£{sprite} {name}"
                self.assertIn(f'WRK_{ideology}_party: "{expected}"', localisation)
                self.assertIn(f'WRK_{ideology}_party_long: "{expected}"', localisation)

    def test_remaining_wrk_ideology_textures_resolve(self) -> None:
        gfx = read("interface/ADISCORD_wrk_party_texticons.gfx")
        paths = re.findall(r'\btexturefile\s*=\s*"([^"]+)"', gfx)
        missing = [
            relative
            for relative in paths
            if not (ROOT / relative).is_file()
            and not (VANILLA_ROOT / relative).is_file()
        ]
        self.assertEqual(missing, [])

    def test_russian_pragmatist_party_uses_wrk_icon_and_name(self) -> None:
        localisation = read("localisation/russian/parties_l_russian.yml")
        expected = f"£{SPRITE} Рабочая революционная партия"
        self.assertIn(f'WRK_pragmatism_party: "{expected}"', localisation)
        self.assertIn(f'WRK_pragmatism_party_long: "{expected}"', localisation)

    def test_russian_party_localisation_keeps_utf8_bom(self) -> None:
        path = ROOT / "localisation/russian/parties_l_russian.yml"
        self.assertTrue(path.read_bytes().startswith(b"\xef\xbb\xbf"))


if __name__ == "__main__":
    unittest.main()
