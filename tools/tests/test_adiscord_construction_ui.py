from pathlib import Path
import re
import unittest

from PIL import Image


ROOT = Path(__file__).resolve().parents[2]
GUI = ROOT / "interface" / "countryconstructionsview.gui"
GFX = ROOT / "interface" / "ADISCORD_buildings.gfx"
ASSET_DIR = ROOT / "gfx" / "interface" / "buildings"


class ConstructionUiContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.gui = GUI.read_text(encoding="utf-8-sig")
        cls.gfx = GFX.read_text(encoding="utf-8-sig")

    def test_live_construction_surfaces_use_adiscord_sprites(self):
        expected_counts = {
            "GFX_ADISCORD_constructions_window_bg": 1,
            "GFX_ADISCORD_constructions_queue_bg": 1,
            "GFX_ADISCORD_constructions_panel_bg": 1,
            "GFX_ADISCORD_construction_screen_top_bg": 1,
            "GFX_ADISCORD_construction_header_bg": 1,
            "GFX_ADISCORD_constructions_category_header": 4,
            "GFX_ADISCORD_construction_entry_bg": 2,
            "GFX_ADISCORD_construction_special_entry_bg": 4,
        }
        for sprite, expected in expected_counts.items():
            self.assertEqual(self.gui.count(f'"{sprite}"'), expected, sprite)

        for retired in (
            "GFX_tiled_window_thin_border",
            "GFX_tiled_generic_overlay_bg1_small",
            "GFX_diplo_details_header",
        ):
            self.assertNotIn(retired, self.gui)

    def test_construction_sprite_definitions_point_to_mod_assets(self):
        textures = {
            "GFX_ADISCORD_constructions_window_bg": "ADISCORD_constructions_window_tile.dds",
            "GFX_ADISCORD_constructions_queue_bg": "ADISCORD_constructions_queue_tile.dds",
            "GFX_ADISCORD_constructions_panel_bg": "ADISCORD_constructions_panel_tile.dds",
            "GFX_ADISCORD_construction_screen_top_bg": "ADISCORD_construction_screen_top.dds",
            "GFX_ADISCORD_construction_header_bg": "ADISCORD_construction_header_bg.dds",
            "GFX_ADISCORD_constructions_category_header": "ADISCORD_constructions_category_header.dds",
            "GFX_ADISCORD_construction_entry_bg": "ADISCORD_construction_entry_bg.dds",
            "GFX_ADISCORD_construction_special_entry_bg": "ADISCORD_construction_special_entry_bg.dds",
        }
        for sprite, filename in textures.items():
            self.assertRegex(
                self.gfx,
                rf'name\s*=\s*"{sprite}"[\s\S]*?'
                rf'textureFile\s*=\s*"gfx/interface/buildings/{filename}"',
            )
            self.assertTrue((ASSET_DIR / filename).is_file(), filename)

    def test_live_construction_textures_have_exact_dimensions_and_opaque_alpha(self):
        sizes = {
            "ADISCORD_constructions_window_tile.dds": (192, 192),
            "ADISCORD_constructions_queue_tile.dds": (192, 192),
            "ADISCORD_constructions_panel_tile.dds": (192, 192),
            "ADISCORD_construction_screen_top.dds": (433, 98),
            "ADISCORD_construction_header_bg.dds": (689, 43),
            "ADISCORD_constructions_category_header.dds": (241, 51),
            "ADISCORD_construction_entry_bg.dds": (402, 54),
            "ADISCORD_construction_special_entry_bg.dds": (402, 54),
        }
        for filename, expected in sizes.items():
            with Image.open(ASSET_DIR / filename) as image:
                self.assertEqual(image.size, expected, filename)
                self.assertEqual(image.mode, "RGBA", filename)
                self.assertEqual(image.getchannel("A").getextrema(), (255, 255), filename)

    def test_construction_source_material_is_kept_with_project_assets(self):
        source = ASSET_DIR / "source" / "construction_surface_source.png"
        self.assertTrue(source.is_file())
        with Image.open(source) as image:
            self.assertGreaterEqual(image.width, 1024)
            self.assertGreaterEqual(image.height, 1024)


if __name__ == "__main__":
    unittest.main()
