from pathlib import Path
import re
import unittest

from PIL import Image

from tools.builders.build_adiscord_intelligence_ui_assets import expected_outputs


ROOT = Path(__file__).resolve().parents[2]
AGENCY_GUI = ROOT / "interface/countryintelligenceagencyview.gui"
OPERATIVE_GUI = ROOT / "interface/operative.gui"
LEADER_GUI = ROOT / "interface/operativeleader.gui"
GFX = ROOT / "interface/ADISCORD_intelligence_ui.gfx"


class IntelligenceUiContractTests(unittest.TestCase):
    def test_agency_nested_windows_remain_present(self) -> None:
        gui = AGENCY_GUI.read_text(encoding="utf-8-sig")
        for name in (
            "countryintelligenceagencyview",
            "name_logo_agency_selection_window",
            "intelligence_agency_upgrades_window",
            "operations_grid",
            "country_list",
            "logo_list",
        ):
            self.assertEqual(
                len(re.findall(rf'name\s*=\s*"{re.escape(name)}"', gui)),
                1,
                name,
            )

    def test_operative_controls_remain_engine_bound(self) -> None:
        leader = LEADER_GUI.read_text(encoding="utf-8-sig")
        for name in (
            "operative_leader_window",
            "operative_order_bar",
            "operative_badge_view",
            "operative_status_window",
            "operative_view",
        ):
            self.assertEqual(
                len(re.findall(rf'name\s*=\s*"{re.escape(name)}"', leader)),
                1,
                name,
            )

    def test_all_three_gui_families_use_intelligence_surfaces(self) -> None:
        combined = "\n".join(
            path.read_text(encoding="utf-8-sig")
            for path in (AGENCY_GUI, OPERATIVE_GUI, LEADER_GUI)
        )
        for sprite in (
            "GFX_ADISCORD_intelligence_window",
            "GFX_ADISCORD_intelligence_panel",
            "GFX_ADISCORD_intelligence_card",
            "GFX_ADISCORD_intelligence_selected",
        ):
            self.assertIn(f'"{sprite}"', combined)

    def test_custom_gfx_is_additive_and_outputs_are_current(self) -> None:
        self.assertTrue(GFX.is_file())
        self.assertFalse((ROOT / "interface/countryintelligenceagencyview.gfx").exists())
        self.assertFalse((ROOT / "interface/operativeleader.gfx").exists())
        outputs = expected_outputs()
        for path, data in outputs.items():
            self.assertTrue(path.is_file(), path)
            self.assertEqual(path.read_bytes(), data, path)
            if path.suffix == ".gui":
                gui = data.decode("utf-8")
                self.assertNotRegex(gui, r"(?m)[ \t]+$")
                self.assertNotRegex(gui, r"(?m)^ +\t")
            if path.suffix == ".dds":
                with Image.open(path) as image:
                    self.assertEqual(image.mode, "RGBA", path.name)


if __name__ == "__main__":
    unittest.main()
