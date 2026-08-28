from pathlib import Path
import re
import unittest

from PIL import Image

from tools.builders.build_adiscord_deployment_ui_assets import (
    DEPLOYMENT_CONTRACTS,
    VANILLA_GUI,
    expected_outputs,
)


ROOT = Path(__file__).resolve().parents[2]
GUI = ROOT / "interface/countrydeploymentview.gui"
GFX = ROOT / "interface/ADISCORD_deployment_ui.gfx"
TRANSPARENT_DDS = ROOT / "gfx/interface/deployment/ui/ADISCORD_deployment_transparent.dds"


EXPECTED_FIXED = {
    "GFX_ADISCORD_deployment_reinforcement_row": ((493, 57), 1),
    "GFX_ADISCORD_deployment_supply_row": ((493, 57), 1),
    "GFX_ADISCORD_deployment_upgrade_row": ((493, 57), 1),
    "GFX_ADISCORD_deployment_garrison_row": ((493, 57), 1),
    "GFX_ADISCORD_deployment_operations_row": ((493, 57), 1),
    "GFX_ADISCORD_deployment_template": ((346, 78), 1),
    "GFX_ADISCORD_deployment_template_obsolete": ((348, 79), 1),
    "GFX_ADISCORD_deployment_conveyor": ((490, 84), 1),
    "GFX_ADISCORD_deployment_line": ((514, 40), 1),
    "GFX_ADISCORD_deployment_end_line": ((518, 40), 1),
    "GFX_ADISCORD_deployment_priority_title": ((159, 26), 1),
    "GFX_ADISCORD_deployment_priority_meter": ((108, 33), 1),
}

LIVE_FIXED = {
    "GFX_ADISCORD_deployment_reinforcement_row",
    "GFX_ADISCORD_deployment_supply_row",
    "GFX_ADISCORD_deployment_template",
    "GFX_ADISCORD_deployment_template_obsolete",
    "GFX_ADISCORD_deployment_conveyor",
    "GFX_ADISCORD_deployment_line",
    "GFX_ADISCORD_deployment_end_line",
    "GFX_ADISCORD_deployment_priority_title",
    "GFX_ADISCORD_deployment_priority_meter",
}

DORMANT_ROLE_SOURCES = {
    "GFX_deploy_upgrades_entry": "GFX_ADISCORD_deployment_upgrade_row",
    "GFX_deploy_garrisons_entry": "GFX_ADISCORD_deployment_garrison_row",
    "GFX_deploy_operations_entry": "GFX_ADISCORD_deployment_operations_row",
}


def named_container_block(text: str, name: str) -> str:
    anchor = f'name = "{name}"'
    name_offset = text.index(anchor)
    start = text.rfind("containerWindowType", 0, name_offset)
    opening = text.find("{", start, name_offset)
    depth = 0
    for offset in range(opening, len(text)):
        if text[offset] == "{":
            depth += 1
        elif text[offset] == "}":
            depth -= 1
            if depth == 0:
                return text[start : offset + 1]
    raise AssertionError(f"unclosed deployment container: {name}")


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

    def test_fixed_deployment_assets_keep_native_semantic_dimensions(self) -> None:
        contracts = {item.target_name: item for item in DEPLOYMENT_CONTRACTS}
        for name, (size, frames) in EXPECTED_FIXED.items():
            with self.subTest(sprite=name):
                self.assertEqual(contracts[name].kind, "spriteType", name)
                self.assertEqual(contracts[name].total_size, size, name)
                self.assertEqual(contracts[name].frames, frames, name)

    def test_deployment_gui_uses_only_live_semantic_role_bindings(self) -> None:
        gui = GUI.read_text(encoding="utf-8-sig")
        bindings = set(
            re.findall(
                r'(?:quadTextureSprite|spriteType)\s*=\s*"(GFX_ADISCORD_deployment_[^"]+)"',
                gui,
            )
        )
        self.assertTrue(LIVE_FIXED <= bindings)
        for target in DORMANT_ROLE_SOURCES.values():
            self.assertNotIn(target, bindings)
        self.assertNotIn('"GFX_ADISCORD_deployment_panel"', gui)

    def test_dormant_role_contracts_do_not_invent_live_gui_widgets(self) -> None:
        vanilla = VANILLA_GUI.read_text(encoding="utf-8-sig")
        for source, target in DORMANT_ROLE_SOURCES.items():
            with self.subTest(source=source):
                self.assertEqual(vanilla.count(f'"{source}"'), 0)
                self.assertIn(f'name = "{target}"', GFX.read_text(encoding="utf-8-sig"))

    def test_transparent_tiled_background_keeps_native_alpha(self) -> None:
        with Image.open(TRANSPARENT_DDS) as image:
            alpha = image.convert("RGBA").getchannel("A")
            self.assertLessEqual(alpha.getextrema()[1], 1)

    def test_reinforcement_and_supply_entries_have_distinct_semantic_rows(self) -> None:
        gui = GUI.read_text(encoding="utf-8-sig")
        reinforcement = named_container_block(gui, "deploy_entry")
        supply = named_container_block(gui, "supply_deploy_entry")
        self.assertIn('"GFX_ADISCORD_deployment_reinforcement_row"', reinforcement)
        self.assertIn('"GFX_ADISCORD_deployment_supply_row"', supply)

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
