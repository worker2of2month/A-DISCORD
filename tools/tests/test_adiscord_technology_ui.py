from pathlib import Path
import re
import unittest

from PIL import Image

from tools.builders.build_adiscord_technology_system import FOLDER_BACKGROUNDS
from tools.builders.build_adiscord_technology_ui_assets import expected_outputs


ROOT = Path(__file__).resolve().parents[2]
GUI = ROOT / "interface/countrytechnologyview.gui"
GFX = ROOT / "interface/ADISCORD_technology_ui.gfx"
ASSET_DIR = ROOT / "gfx/interface/technology/ui"


class TechnologyUiContractTests(unittest.TestCase):
    def test_custom_gfx_is_additive_not_a_vanilla_path_override(self) -> None:
        self.assertTrue(GFX.is_file())
        self.assertFalse((ROOT / "interface/countrytechnologyview.gfx").exists())

    def test_research_shell_preserves_engine_bound_elements(self) -> None:
        gui = GUI.read_text(encoding="utf-8-sig")
        for name in (
            "countrytechnologyview",
            "research_slots",
            "facilities",
            "research_slots_grid",
            "research_groups_grid",
            "close_button",
        ):
            self.assertEqual(
                len(re.findall(rf'name\s*=\s*"{re.escape(name)}"', gui)),
                1,
                name,
            )

    def test_research_shell_uses_adiscord_surfaces(self) -> None:
        gui = GUI.read_text(encoding="utf-8-sig")
        for sprite in (
            "GFX_ADISCORD_technology_window",
            "GFX_ADISCORD_technology_panel",
            "GFX_ADISCORD_technology_slot",
            "GFX_ADISCORD_technology_tab",
        ):
            self.assertIn(f'"{sprite}"', gui)

    def test_generated_tree_keeps_all_custom_folders(self) -> None:
        gui = (ROOT / "interface/countrytechtreeview.gui").read_text(
            encoding="utf-8-sig"
        )
        for folder in FOLDER_BACKGROUNDS:
            self.assertEqual(gui.count(f'name = "{folder}"'), 1, folder)

    def test_generated_tree_uses_adiscord_surfaces(self) -> None:
        gui = (ROOT / "interface/countrytechtreeview.gui").read_text(
            encoding="utf-8-sig"
        )
        for sprite in (
            "GFX_ADISCORD_technology_tree_panel",
            "GFX_ADISCORD_technology_tree_stripes",
            "GFX_ADISCORD_technology_tree_info",
        ):
            self.assertIn(f'"{sprite}"', gui)

    def test_expected_outputs_match_checked_in_assets(self) -> None:
        outputs = expected_outputs()
        self.assertIn(GUI, outputs)
        self.assertIn(GFX, outputs)
        for path, data in outputs.items():
            self.assertTrue(path.is_file(), path)
            self.assertEqual(path.read_bytes(), data, path)
            if path.suffix == ".gui":
                self.assertNotRegex(data.decode("utf-8"), r"(?m)[ \t]+$")
        for path in ASSET_DIR.glob("*.dds"):
            with Image.open(path) as image:
                self.assertEqual(image.mode, "RGBA", path.name)


if __name__ == "__main__":
    unittest.main()
