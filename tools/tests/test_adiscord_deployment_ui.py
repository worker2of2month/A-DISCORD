from pathlib import Path
import re
import unittest

from PIL import Image

from tools.builders.build_adiscord_deployment_ui_assets import expected_outputs


ROOT = Path(__file__).resolve().parents[2]
GUI = ROOT / "interface/countrydeploymentview.gui"
GFX = ROOT / "interface/ADISCORD_deployment_ui.gfx"


class DeploymentUiContractTests(unittest.TestCase):
    def test_custom_gfx_is_additive_not_a_vanilla_path_override(self) -> None:
        self.assertTrue(GFX.is_file())
        self.assertFalse((ROOT / "interface/countrydeploymentview.gfx").exists())

    def test_engine_bound_deployment_widgets_remain_unique(self) -> None:
        gui = GUI.read_text(encoding="utf-8-sig")
        for name in (
            "countrydeploymentview",
            "templatedeploymentwindow",
            "templates_grid",
            "deployments_list_gridbox",
            "foreign_templates_grid",
            "symbols_grid",
        ):
            self.assertEqual(
                len(re.findall(rf'name\s*=\s*"{re.escape(name)}"', gui)),
                1,
                name,
            )

    def test_deployment_chrome_uses_adiscord_surfaces(self) -> None:
        gui = GUI.read_text(encoding="utf-8-sig")
        for sprite in (
            "GFX_ADISCORD_deployment_window",
            "GFX_ADISCORD_deployment_panel",
            "GFX_ADISCORD_deployment_template",
            "GFX_ADISCORD_deployment_line",
        ):
            self.assertIn(f'"{sprite}"', gui)

    def test_training_equipment_and_hq_controls_keep_engine_names(self) -> None:
        gui = GUI.read_text(encoding="utf-8-sig")
        for name in (
            "equipment_progressbar",
            "training_progressbar",
            "deploy_line_button",
            "cancel_line_button",
            "allow_as_hq_icon",
        ):
            self.assertIn(f'name = "{name}"', gui)

    def test_generated_gui_and_assets_are_clean_and_current(self) -> None:
        gui = GUI.read_text(encoding="utf-8-sig")
        self.assertNotRegex(gui, r"(?m)[ \t]+$")
        outputs = expected_outputs()
        for path, data in outputs.items():
            self.assertTrue(path.is_file(), path)
            self.assertEqual(path.read_bytes(), data, path)
            if path.suffix == ".dds":
                with Image.open(path) as image:
                    self.assertEqual(image.mode, "RGBA", path.name)


if __name__ == "__main__":
    unittest.main()
