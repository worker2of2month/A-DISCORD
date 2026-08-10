from __future__ import annotations

import hashlib
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OVERRIDE = ROOT / "interface/countryproductionlineview.gui"
VANILLA_1_19_NORMALIZED_SHA256 = (
    "f1b8d40d28522c2768612888f4168e1f9f49a3632fa0ac80607da4369b31f585"
)


def named_gui_block(source: str, widget_type: str, name: str) -> str:
    match = re.search(
        rf"(?ms)^\s*{re.escape(widget_type)}\s*=\s*\{{"
        rf"(?:(?!^\s*(?:containerWindowType|iconType|buttonType)\s*=).)*?"
        rf"^\s*name\s*=\s*\"{re.escape(name)}\"",
        source,
    )
    if not match:
        return ""
    open_at = source.find("{", match.start())
    depth = 0
    for index in range(open_at, len(source)):
        if source[index] == "{":
            depth += 1
        elif source[index] == "}":
            depth -= 1
            if depth == 0:
                return source[match.start():index + 1]
    return ""


def remove_named_gui_block(source: str, widget_type: str, name: str) -> str:
    widget = named_gui_block(source, widget_type, name)
    if not widget:
        return source
    return source.replace(widget, "", 1)


class CountryProductionLineResourceUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = OVERRIDE.read_text(encoding="utf-8-sig")

    def test_override_preserves_the_complete_vanilla_1_19_gui(self) -> None:
        vanilla_shape = self.source
        for custom, vanilla in (
            ("GFX_ADISCORD_production_window_bg", "GFX_tiled_plain_bg"),
            ("GFX_ADISCORD_production_lines_bg", "GFX_tiled_window2_1b_border"),
            ("GFX_ADISCORD_production_lines_overlay", "GFX_tiled_generic_overlay_bg1"),
            ("GFX_ADISCORD_production_top_panel", "GFX_production_win_top"),
            ("GFX_ADISCORD_production_military_item", "GFX_production_item"),
            ("GFX_ADISCORD_production_collapsed_item", "GFX_production_item_collapsed"),
            ("GFX_ADISCORD_production_naval_item_strip", "GFX_naval_production_item_bg_strip"),
            ("GFX_ADISCORD_production_consumer_item", "GFX_consumer_goods"),
            ("GFX_ADISCORD_production_equipment_card", "GFX_prod_land_equipment_item_large"),
            ("GFX_ADISCORD_production_factory_icon", "GFX_factory_item"),
            ("GFX_ADISCORD_production_factory_half_icon", "GFX_factory_item_half"),
            ("GFX_ADISCORD_production_factory_slot_bg", "GFX_factory_bg"),
            ("GFX_ADISCORD_production_add_infantry_button", "GFX_add_prod_inf_art_line"),
            ("GFX_ADISCORD_production_add_armour_button", "GFX_add_prod_armour_line"),
            ("GFX_ADISCORD_production_add_aircraft_button", "GFX_add_prod_aircraft_line"),
            ("GFX_ADISCORD_production_add_naval_button", "GFX_add_prod_naval_line"),
            ("GFX_ADISCORD_production_naval_repair_button", "GFX_toggle_naval_repair_window"),
        ):
            vanilla_shape = vanilla_shape.replace(custom, vanilla)
        for widget_type, name in (
            ("iconType", "rare_components_icon"),
            ("buttonType", "rare_components_checkbox"),
            ("iconType", "rare_alloys_icon"),
            ("buttonType", "rare_alloys_checkbox"),
        ):
            vanilla_shape = remove_named_gui_block(vanilla_shape, widget_type, name)
        normalized = re.sub(r"\s+", "", vanilla_shape).encode("utf-8")
        self.assertEqual(
            hashlib.sha256(normalized).hexdigest(),
            VANILLA_1_19_NORMALIZED_SHA256,
        )

    def test_resources_container_exposes_all_nine_engine_resources(self) -> None:
        resources = named_gui_block(self.source, "containerWindowType", "resources")
        self.assertTrue(resources)
        expected_frames = {
            "oil": 1,
            "aluminium": 2,
            "rubber": 3,
            "tungsten": 4,
            "steel": 5,
            "chromium": 6,
            "coal": 7,
            "rare_components": 8,
            "rare_alloys": 9,
        }
        for resource, frame in expected_frames.items():
            with self.subTest(resource=resource):
                icon = named_gui_block(resources, "iconType", f"{resource}_icon")
                checkbox = named_gui_block(
                    resources, "buttonType", f"{resource}_checkbox"
                )
                self.assertRegex(icon, rf"\bframe\s*=\s*{frame}\b")
                self.assertIn('quadTextureSprite ="GFX_generic_checkbox"', checkbox)

    def test_new_resource_controls_fit_the_unchanged_military_window(self) -> None:
        military = named_gui_block(
            self.source, "containerWindowType", "production_equipment_window_military"
        )
        self.assertIn("size = { width=495 height=100%% }", military)
        self.assertIn('name = "equipments_grid"', military)
        self.assertIn('name = "production_MIOs"', military)
        resources = named_gui_block(military, "containerWindowType", "resources")
        for name, x in (
            ("rare_components_icon", 395),
            ("rare_components_checkbox", 418),
            ("rare_alloys_icon", 444),
            ("rare_alloys_checkbox", 467),
        ):
            widget_type = "buttonType" if name.endswith("checkbox") else "iconType"
            widget = named_gui_block(resources, widget_type, name)
            self.assertRegex(widget, rf"\bposition\s*=\s*\{{\s*x\s*=\s*{x}\b")
        self.assertLess(467, 495)


if __name__ == "__main__":
    unittest.main()
