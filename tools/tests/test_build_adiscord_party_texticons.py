from __future__ import annotations

import io
import inspect
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
EXPECTED_RUNTIME_SIZES = {key: (25, 25) for key in EXPECTED_KEYS}
EXPECTED_RUNTIME_SIZES["ivn_roar_of_freedom"] = (32, 32)


class PartyTexticonBuilderTests(unittest.TestCase):
    def test_manifest_covers_exactly_the_ten_approved_icons(self) -> None:
        self.assertEqual({asset.key for asset in builder.ASSETS}, EXPECTED_KEYS)
        self.assertEqual(
            {asset.key: getattr(asset, "runtime_size", None) for asset in builder.ASSETS},
            EXPECTED_RUNTIME_SIZES,
        )
        self.assertEqual(len(builder.ASSETS), 10)
        self.assertEqual(len({asset.source for asset in builder.ASSETS}), 10)
        self.assertEqual(len({asset.output for asset in builder.ASSETS}), 10)

    def test_render_icon_is_deterministic_rgba_with_clear_padding(self) -> None:
        self.assertIn("runtime_size", inspect.signature(builder.render_icon).parameters)
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "source.png"
            image = Image.new("RGBA", (512, 512), (0, 0, 0, 0))
            draw = ImageDraw.Draw(image)
            draw.ellipse((72, 36, 440, 476), fill=(190, 30, 20, 255))
            image.save(source)

            for runtime_size in ((25, 25), (32, 32)):
                with self.subTest(runtime_size=runtime_size):
                    first = builder.render_icon(source, runtime_size)
                    second = builder.render_icon(source, runtime_size)
                    self.assertEqual(first, second)
                    with Image.open(io.BytesIO(first)) as rendered:
                        self.assertEqual(rendered.mode, "RGBA")
                        self.assertEqual(rendered.size, runtime_size)
                        self.assertIsNotNone(rendered.getchannel("A").getbbox())
                        width, height = runtime_size
                        for corner in (
                            (0, 0),
                            (width - 1, 0),
                            (0, height - 1),
                            (width - 1, height - 1),
                        ):
                            self.assertEqual(rendered.getpixel(corner)[3], 0)

    def test_runtime_outputs_are_current(self) -> None:
        self.assertEqual(builder.drift(), [])
        for asset in builder.ASSETS:
            with self.subTest(asset=asset.key), Image.open(builder.ROOT / asset.output) as image:
                self.assertEqual(image.mode, "RGBA")
                runtime_size = EXPECTED_RUNTIME_SIZES[asset.key]
                self.assertEqual(image.size, runtime_size)
                self.assertIsNotNone(image.getchannel("A").getbbox())
                width, height = runtime_size
                for corner in (
                    (0, 0),
                    (width - 1, 0),
                    (0, height - 1),
                    (width - 1, height - 1),
                ):
                    self.assertEqual(image.getpixel(corner)[3], 0)


if __name__ == "__main__":
    unittest.main()
