from pathlib import Path
import re
import unittest

from PIL import Image

from tools.builders.build_adiscord_logistics_ui_assets import expected_outputs


ROOT = Path(__file__).resolve().parents[2]
GUI = ROOT / "interface/countrylogisticsview.gui"
GFX = ROOT / "interface/countrylogisticsview.gfx"


class LogisticsUiContractTests(unittest.TestCase):
    def test_all_logistics_windows_remain_present(self) -> None:
        gui = GUI.read_text(encoding="utf-8-sig")
        for name in (
            "countrylogisticsview",
            "materiel",
            "fuel_info",
            "logistics_info_window",
            "logistics_fuel_window",
            "variants",
        ):
            self.assertEqual(
                len(re.findall(rf'name\s*=\s*"{re.escape(name)}"', gui)),
                1,
                name,
            )

    def test_logistics_chrome_uses_adiscord_surfaces(self) -> None:
        gui = GUI.read_text(encoding="utf-8-sig")
        for sprite in (
            "GFX_ADISCORD_logistics_window",
            "GFX_ADISCORD_logistics_panel",
            "GFX_ADISCORD_logistics_row",
            "GFX_ADISCORD_logistics_graph",
        ):
            self.assertIn(f'"{sprite}"', gui)

    def test_semantic_icons_are_preserved(self) -> None:
        gui = GUI.read_text(encoding="utf-8-sig")
        for sprite in (
            "GFX_need_icon",
            "GFX_in_stock_icon",
            "GFX_fuel_logisctics_icon",
            "GFX_efficiency_icon",
        ):
            self.assertIn(f'"{sprite}"', gui)

    def test_generated_gui_has_no_trailing_whitespace(self) -> None:
        gui = GUI.read_text(encoding="utf-8-sig")
        self.assertNotRegex(gui, r"(?m)[ \t]+$")

    def test_builder_outputs_are_byte_current_rgba_assets(self) -> None:
        outputs = expected_outputs()
        self.assertIn(GUI, outputs)
        self.assertIn(GFX, outputs)
        for path, data in outputs.items():
            self.assertTrue(path.is_file(), path)
            self.assertEqual(path.read_bytes(), data, path)
            if path.suffix == ".dds":
                with Image.open(path) as image:
                    self.assertEqual(image.mode, "RGBA", path.name)


if __name__ == "__main__":
    unittest.main()
