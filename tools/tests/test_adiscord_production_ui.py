from pathlib import Path
import re
import unittest

from PIL import Image


ROOT = Path(__file__).resolve().parents[2]
GUI = ROOT / "interface/countryproductionlineview.gui"
GFX = ROOT / "interface/ADISCORD_production.gfx"
ASSET_DIR = ROOT / "gfx/interface/production/ui"


class ProductionUiContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.gui = GUI.read_text(encoding="utf-8-sig")
        cls.gfx = GFX.read_text(encoding="utf-8-sig")

    def test_live_production_surfaces_use_adiscord_sprites(self) -> None:
        expected_counts = {
            "GFX_ADISCORD_production_window_bg": 6,
            "GFX_ADISCORD_production_lines_bg": 1,
            "GFX_ADISCORD_production_lines_overlay": 1,
            "GFX_ADISCORD_production_top_panel": 1,
            "GFX_ADISCORD_production_military_item": 3,
            "GFX_ADISCORD_production_collapsed_item": 4,
            "GFX_ADISCORD_production_naval_item_strip": 3,
            "GFX_ADISCORD_production_consumer_item": 1,
            "GFX_ADISCORD_production_equipment_card": 3,
            "GFX_ADISCORD_production_factory_icon": 5,
            "GFX_ADISCORD_production_factory_half_icon": 1,
            "GFX_ADISCORD_production_factory_slot_bg": 3,
            "GFX_ADISCORD_production_add_infantry_button": 1,
            "GFX_ADISCORD_production_add_armour_button": 1,
            "GFX_ADISCORD_production_add_aircraft_button": 1,
            "GFX_ADISCORD_production_add_naval_button": 1,
            "GFX_ADISCORD_production_naval_repair_button": 1,
        }
        for sprite, expected in expected_counts.items():
            self.assertEqual(self.gui.count(f'"{sprite}"'), expected, sprite)

        for retired in (
            "GFX_tiled_plain_bg",
            "GFX_tiled_window2_1b_border",
            "GFX_tiled_generic_overlay_bg1",
            "GFX_production_win_top",
            "GFX_production_item",
            "GFX_production_item_collapsed",
            "GFX_naval_production_item_bg_strip",
            "GFX_consumer_goods",
            "GFX_prod_land_equipment_item_large",
            "GFX_factory_item",
            "GFX_factory_item_half",
            "GFX_factory_bg",
            "GFX_add_prod_inf_art_line",
            "GFX_add_prod_armour_line",
            "GFX_add_prod_aircraft_line",
            "GFX_add_prod_naval_line",
            "GFX_toggle_naval_repair_window",
        ):
            self.assertNotRegex(self.gui, rf'"{re.escape(retired)}"')

    def test_production_sprite_definitions_point_to_mod_assets(self) -> None:
        textures = {
            "GFX_ADISCORD_production_window_bg": "ADISCORD_production_window_tile.dds",
            "GFX_ADISCORD_production_lines_bg": "ADISCORD_production_lines_tile.dds",
            "GFX_ADISCORD_production_lines_overlay": "ADISCORD_production_lines_overlay.dds",
            "GFX_ADISCORD_production_top_panel": "ADISCORD_production_top_panel.dds",
            "GFX_ADISCORD_production_military_item": "ADISCORD_production_military_item.dds",
            "GFX_ADISCORD_production_collapsed_item": "ADISCORD_production_collapsed_item.dds",
            "GFX_ADISCORD_production_naval_item_strip": "ADISCORD_production_naval_item_strip.dds",
            "GFX_ADISCORD_production_consumer_item": "ADISCORD_production_consumer_item.dds",
            "GFX_ADISCORD_production_equipment_card": "ADISCORD_production_equipment_card.dds",
            "GFX_ADISCORD_production_factory_icon": "ADISCORD_production_factory_icon_strip.dds",
            "GFX_ADISCORD_production_factory_half_icon": "ADISCORD_production_factory_half_strip.dds",
            "GFX_ADISCORD_production_factory_slot_bg": "ADISCORD_production_factory_slot_bg.dds",
            "GFX_ADISCORD_production_add_infantry_button": "ADISCORD_production_add_infantry_button.dds",
            "GFX_ADISCORD_production_add_armour_button": "ADISCORD_production_add_armour_button.dds",
            "GFX_ADISCORD_production_add_aircraft_button": "ADISCORD_production_add_aircraft_button.dds",
            "GFX_ADISCORD_production_add_naval_button": "ADISCORD_production_add_naval_button.dds",
            "GFX_ADISCORD_production_naval_repair_button": "ADISCORD_production_naval_repair_button.dds",
        }
        for sprite, filename in textures.items():
            self.assertRegex(
                self.gfx,
                rf'name\s*=\s*"{sprite}"[\s\S]*?'
                rf'textureFile\s*=\s*"gfx/interface/production/ui/{filename}"',
            )
            self.assertTrue((ASSET_DIR / filename).is_file(), filename)
        self.assertRegex(
            self.gfx,
            r'name\s*=\s*"GFX_ADISCORD_production_naval_item_strip"[\s\S]*?'
            r'noOfFrames\s*=\s*3',
        )
        for sprite, frames in (
            ("GFX_ADISCORD_production_factory_icon", 15),
            ("GFX_ADISCORD_production_factory_half_icon", 15),
            ("GFX_ADISCORD_production_add_infantry_button", 3),
            ("GFX_ADISCORD_production_add_armour_button", 3),
            ("GFX_ADISCORD_production_add_aircraft_button", 3),
            ("GFX_ADISCORD_production_add_naval_button", 3),
            ("GFX_ADISCORD_production_naval_repair_button", 3),
        ):
            self.assertRegex(
                self.gfx,
                rf'name\s*=\s*"{sprite}"[\s\S]*?noOfFrames\s*=\s*{frames}',
            )

    def test_generated_production_textures_have_exact_dimensions(self) -> None:
        sizes = {
            "ADISCORD_production_window_tile.dds": (192, 192),
            "ADISCORD_production_lines_tile.dds": (192, 192),
            "ADISCORD_production_lines_overlay.dds": (549, 600),
            "ADISCORD_production_top_panel.dds": (550, 253),
            "ADISCORD_production_military_item.dds": (511, 108),
            "ADISCORD_production_collapsed_item.dds": (512, 60),
            "ADISCORD_production_naval_item_strip.dds": (1533, 108),
            "ADISCORD_production_consumer_item.dds": (511, 108),
            "ADISCORD_production_equipment_card.dds": (279, 81),
            "ADISCORD_production_factory_icon_strip.dds": (330, 18),
            "ADISCORD_production_factory_half_strip.dds": (330, 18),
            "ADISCORD_production_factory_slot_bg.dds": (28, 22),
            "ADISCORD_production_add_infantry_button.dds": (243, 41),
            "ADISCORD_production_add_armour_button.dds": (243, 41),
            "ADISCORD_production_add_aircraft_button.dds": (243, 41),
            "ADISCORD_production_add_naval_button.dds": (243, 41),
            "ADISCORD_production_naval_repair_button.dds": (243, 41),
        }
        for filename, expected in sizes.items():
            with Image.open(ASSET_DIR / filename) as image:
                self.assertEqual(image.size, expected, filename)
                self.assertEqual(image.mode, "RGBA", filename)

        with Image.open(ASSET_DIR / "ADISCORD_production_lines_overlay.dds") as image:
            self.assertEqual(image.getchannel("A").getextrema(), (0, 255))

    def test_production_source_material_is_kept_with_project_assets(self) -> None:
        source = ROOT / "gfx/interface/production/source/production_surface_source.png"
        self.assertTrue(source.is_file())
        with Image.open(source) as image:
            self.assertGreaterEqual(image.width, 1024)
            self.assertGreaterEqual(image.height, 1024)

        for filename in (
            "factory_glyph_source.png",
            "infantry_artillery_glyph_source.png",
            "armour_glyph_source.png",
            "aircraft_glyph_source.png",
            "naval_glyph_source.png",
            "repair_glyph_source.png",
        ):
            with self.subTest(filename=filename):
                with Image.open(source.parent / filename) as image:
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
