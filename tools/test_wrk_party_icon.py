from __future__ import annotations

import re
import unittest
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
ICON = ROOT / "gfx/texticons/adiscord/parties/WRK/WRK_worker_revolutionary_party.png"
SPRITE = "GFX_WRK_worker_revolutionary_party_texticon"


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
