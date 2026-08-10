from pathlib import Path
import unittest

from PIL import Image


ROOT = Path(__file__).resolve().parents[2]
GUI = ROOT / "interface" / "countrydecisionview.gui"
GFX = ROOT / "interface" / "ADISCORD_decisions.gfx"
ASSET_DIR = ROOT / "gfx" / "interface" / "decisions" / "ui"


class DecisionsUiContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.gui = GUI.read_text(encoding="utf-8-sig")
        cls.gfx = GFX.read_text(encoding="utf-8-sig")

    def test_live_decisions_surfaces_use_adiscord_sprites(self):
        expected_counts = {
            "GFX_ADISCORD_decisions_window_bg": 1,
            "GFX_ADISCORD_decisions_title_bg": 1,
            "GFX_ADISCORD_decisions_event_header_bg": 1,
            "GFX_ADISCORD_decisions_category_header_bg": 1,
            "GFX_ADISCORD_decisions_category_desc_bg": 1,
            "GFX_ADISCORD_decisions_category_end_bg": 1,
            "GFX_ADISCORD_decisions_event_item_bg": 1,
            "GFX_ADISCORD_decisions_item_bg": 4,
            "GFX_ADISCORD_decisions_item_progress_good": 3,
            "GFX_ADISCORD_decisions_item_progress_bad": 3,
            "GFX_ADISCORD_decisions_select_icon_strip": 3,
        }
        for sprite, expected in expected_counts.items():
            self.assertEqual(self.gui.count(f'"{sprite}"'), expected, sprite)

        for retired in (
            "GFX_tiled_window2_1b_border",
            "GFX_header_bg",
            "GFX_category_header_bg",
            "GFX_tiled_decisions_bg_small",
            "GFX_event_header_bg",
            "GFX_category_end_bg",
            "GFX_event_item_bg",
            "GFX_decision_item_bg",
            "GFX_decision_item_progress_good",
            "GFX_decision_item_progress_bad",
            "GFX_decision_select_icon_strip",
            "hoi4_typewriter22",
            "hoi4_typewriter16",
        ):
            self.assertNotIn(retired, self.gui)

    def test_decisions_sprite_definitions_point_to_mod_assets(self):
        textures = {
            "GFX_ADISCORD_decisions_window_bg": "ADISCORD_decisions_window_tile.dds",
            "GFX_ADISCORD_decisions_title_bg": "ADISCORD_decisions_title_bg.dds",
            "GFX_ADISCORD_decisions_event_header_bg": "ADISCORD_decisions_event_header_bg.dds",
            "GFX_ADISCORD_decisions_category_header_bg": "ADISCORD_decisions_category_header_bg.dds",
            "GFX_ADISCORD_decisions_category_desc_bg": "ADISCORD_decisions_category_desc_tile.dds",
            "GFX_ADISCORD_decisions_category_end_bg": "ADISCORD_decisions_category_end_bg.dds",
            "GFX_ADISCORD_decisions_event_item_bg": "ADISCORD_decisions_event_item_bg.dds",
            "GFX_ADISCORD_decisions_item_bg": "ADISCORD_decisions_item_bg.dds",
            "GFX_ADISCORD_decisions_select_icon_strip": "ADISCORD_decisions_select_icon_strip.dds",
        }
        for sprite, filename in textures.items():
            self.assertRegex(
                self.gfx,
                rf'name\s*=\s*"{sprite}"[\s\S]*?'
                rf'textureFile\s*=\s*"gfx/interface/decisions/ui/{filename}"',
            )
            self.assertTrue((ASSET_DIR / filename).is_file(), filename)

        for sprite, fill in (
            ("GFX_ADISCORD_decisions_item_progress_good", "ADISCORD_decisions_progress_good.dds"),
            ("GFX_ADISCORD_decisions_item_progress_bad", "ADISCORD_decisions_progress_bad.dds"),
        ):
            self.assertRegex(
                self.gfx,
                rf'name\s*=\s*"{sprite}"[\s\S]*?'
                rf'textureFile1\s*=\s*"gfx/interface/decisions/ui/{fill}"[\s\S]*?'
                r'textureFile2\s*=\s*"gfx/interface/decisions/ui/ADISCORD_decisions_progress_bg\.dds"',
            )

    def test_live_decisions_textures_have_exact_dimensions(self):
        sizes = {
            "ADISCORD_decisions_window_tile.dds": (192, 192),
            "ADISCORD_decisions_title_bg.dds": (543, 41),
            "ADISCORD_decisions_event_header_bg.dds": (515, 83),
            "ADISCORD_decisions_category_header_bg.dds": (516, 53),
            "ADISCORD_decisions_category_desc_tile.dds": (48, 48),
            "ADISCORD_decisions_category_end_bg.dds": (512, 20),
            "ADISCORD_decisions_event_item_bg.dds": (512, 33),
            "ADISCORD_decisions_item_bg.dds": (1536, 40),
            "ADISCORD_decisions_progress_bg.dds": (503, 40),
            "ADISCORD_decisions_progress_good.dds": (503, 40),
            "ADISCORD_decisions_progress_bad.dds": (503, 40),
            "ADISCORD_decisions_select_icon_strip.dds": (160, 28),
        }
        for filename, expected in sizes.items():
            with Image.open(ASSET_DIR / filename) as image:
                self.assertEqual(image.size, expected, filename)
                self.assertEqual(image.mode, "RGBA", filename)

        with Image.open(ASSET_DIR / "ADISCORD_decisions_progress_bg.dds") as image:
            self.assertEqual(image.getchannel("A").getextrema(), (0, 0))

    def test_decisions_source_material_is_kept_with_project_assets(self):
        source = ROOT / "gfx/interface/decisions/source/decisions_surface_source.png"
        self.assertTrue(source.is_file())
        with Image.open(source) as image:
            self.assertGreaterEqual(image.width, 1024)
            self.assertGreaterEqual(image.height, 1024)

        approval = ROOT / "gfx/interface/decisions/source/decision_approval_seal_source.png"
        self.assertTrue(approval.is_file())
        with Image.open(approval) as image:
            rgba = image.convert("RGBA")
            alpha = rgba.getchannel("A")
            self.assertEqual(alpha.getextrema(), (0, 255))
            self.assertEqual(
                [
                    alpha.getpixel((0, 0)),
                    alpha.getpixel((rgba.width - 1, 0)),
                    alpha.getpixel((0, rgba.height - 1)),
                    alpha.getpixel((rgba.width - 1, rgba.height - 1)),
                ],
                [0, 0, 0, 0],
            )


if __name__ == "__main__":
    unittest.main()
