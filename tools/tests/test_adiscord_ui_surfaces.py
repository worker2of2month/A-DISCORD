from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from PIL import Image

from tools.lib.adiscord_ui_surfaces import (
    PALETTES,
    apply_or_check,
    button_strip,
    dds_bytes,
    framed_panel,
    replace_counted,
)


class UiSurfaceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.source = Image.new("RGBA", (1024, 1024), (39, 43, 44, 255))

    def test_four_section_palettes_produce_distinct_accents(self) -> None:
        self.assertEqual(
            set(PALETTES),
            {"technology", "logistics", "deployment", "intelligence"},
        )
        self.assertEqual(len({palette.accent for palette in PALETTES.values()}), 4)

    def test_panel_and_three_state_button_have_engine_dimensions(self) -> None:
        panel = framed_panel(
            self.source,
            (192, 192),
            PALETTES["technology"],
            0.82,
        )
        strip = button_strip(
            self.source,
            (81, 41),
            PALETTES["technology"],
        )

        self.assertEqual(panel.size, (192, 192))
        self.assertEqual(strip.size, (243, 41))
        self.assertEqual(panel.getchannel("A").getextrema(), (255, 255))

    def test_counted_replacement_rejects_upstream_contract_drift(self) -> None:
        source = 'spriteType = "GFX_old"\nquadTextureSprite = "GFX_old"\n'
        self.assertEqual(
            replace_counted(source, "GFX_old", "GFX_new", 2).count('"GFX_new"'),
            2,
        )
        with self.assertRaisesRegex(ValueError, "expected 1, found 2"):
            replace_counted(source, "GFX_old", "GFX_new", 1)

    def test_apply_or_check_writes_only_in_apply_mode(self) -> None:
        with TemporaryDirectory() as temp:
            path = Path(temp) / "panel.dds"
            outputs = {path: dds_bytes(self.source)}

            self.assertEqual(apply_or_check(outputs, apply=False, label="test"), 1)
            self.assertFalse(path.exists())
            self.assertEqual(apply_or_check(outputs, apply=True, label="test"), 0)
            self.assertTrue(path.exists())
            self.assertEqual(apply_or_check(outputs, apply=False, label="test"), 0)


if __name__ == "__main__":
    unittest.main()
