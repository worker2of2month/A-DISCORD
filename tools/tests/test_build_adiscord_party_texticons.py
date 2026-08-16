from __future__ import annotations

import io
import tempfile
import unittest
from pathlib import Path

from PIL import Image, ImageDraw

from tools.builders import build_adiscord_party_texticons as builder


EXPECTED_KEYS = {
    "ivn_roar_of_freedom",
    "ivn_emergency_committee",
    "tva_wartime_technocratic_worker",
    "vad_vorkerland_imperial",
    "zao_independent_party",
    "pwr_independent_party",
    "vla_independent_party",
    "rom_independent_party",
    "sol_independent_party",
    "tru_independent_party",
}


class PartyTexticonBuilderTests(unittest.TestCase):
    def test_manifest_covers_exactly_the_ten_approved_icons(self) -> None:
        self.assertEqual({asset.key for asset in builder.ASSETS}, EXPECTED_KEYS)
        self.assertEqual(len(builder.ASSETS), 10)
        self.assertEqual(len({asset.source for asset in builder.ASSETS}), 10)
        self.assertEqual(len({asset.output for asset in builder.ASSETS}), 10)

    def test_render_icon_is_deterministic_25px_rgba_with_clear_padding(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "source.png"
            image = Image.new("RGBA", (512, 512), (0, 0, 0, 0))
            draw = ImageDraw.Draw(image)
            draw.ellipse((72, 36, 440, 476), fill=(190, 30, 20, 255))
            image.save(source)
            first = builder.render_icon(source)
            second = builder.render_icon(source)
            self.assertEqual(first, second)
            with Image.open(io.BytesIO(first)) as rendered:
                self.assertEqual(rendered.mode, "RGBA")
                self.assertEqual(rendered.size, (25, 25))
                self.assertIsNotNone(rendered.getchannel("A").getbbox())
                for corner in ((0, 0), (24, 0), (0, 24), (24, 24)):
                    self.assertEqual(rendered.getpixel(corner)[3], 0)

    def test_runtime_outputs_are_current(self) -> None:
        self.assertEqual(builder.drift(), [])
        for asset in builder.ASSETS:
            with self.subTest(asset=asset.key), Image.open(builder.ROOT / asset.output) as image:
                self.assertEqual(image.mode, "RGBA")
                self.assertEqual(image.size, (25, 25))
                self.assertIsNotNone(image.getchannel("A").getbbox())


if __name__ == "__main__":
    unittest.main()
