from pathlib import Path
import re
import unittest

from PIL import Image, ImageChops, ImageStat

from tools.builders import build_adiscord_intelligence_ui_assets as builder


ROOT = Path(__file__).resolve().parents[2]
AGENCY_GUI = ROOT / "interface/countryintelligenceagencyview.gui"
OPERATIVE_GUI = ROOT / "interface/operative.gui"
LEADER_GUI = ROOT / "interface/operativeleader.gui"
GFX = ROOT / "interface/ADISCORD_intelligence_ui.gfx"
HEADER_SOURCE = (
    ROOT
    / "gfx/interface/intelligence/source/ADISCORD_intelligence_header_source.png"
)
OUTPUT_DIR = ROOT / "gfx/interface/intelligence/ui"


EXPECTED_FIXED = {
    "GFX_ADISCORD_intelligence_header": ((519, 109), 1),
    "GFX_ADISCORD_intelligence_create": ((508, 99), 1),
    "GFX_ADISCORD_intelligence_branches_popup": ((1092, 91), 1),
    "GFX_ADISCORD_intelligence_branch_row": ((1040, 136), 1),
    "GFX_ADISCORD_intelligence_operatives": ((522, 76), 1),
    "GFX_ADISCORD_intelligence_tabs": ((524, 53), 2),
    "GFX_ADISCORD_intelligence_operation_row": ((1038, 89), 2),
    "GFX_ADISCORD_intelligence_crypto_row": ((516, 87), 1),
    "GFX_ADISCORD_intelligence_crypto_selected": ((516, 87), 1),
    "GFX_ADISCORD_intelligence_required": ((33, 29), 1),
    "GFX_ADISCORD_intelligence_add_operative": ((61, 83), 1),
    "GFX_ADISCORD_intelligence_mission_bar": ((402, 79), 1),
}


def named_button_block(text: str, name: str) -> str:
    marker = f'name = "{name}"'
    marker_at = text.index(marker)
    start = text.rfind("buttonType = {", 0, marker_at)
    opening = text.index("{", start, marker_at)
    depth = 0
    for offset in range(opening, len(text)):
        if text[offset] == "{":
            depth += 1
        elif text[offset] == "}":
            depth -= 1
            if depth == 0:
                return text[start : offset + 1]
    raise AssertionError(f"unclosed button block: {name}")


def mean_luminance(image: Image.Image, box: tuple[int, int, int, int]) -> float:
    return ImageStat.Stat(image.convert("L").crop(box)).mean[0]


class IntelligenceUiContractTests(unittest.TestCase):
    def test_fixed_intelligence_assets_keep_native_dimensions_and_frames(self) -> None:
        contracts = {item.target_name: item for item in builder.INTELLIGENCE_CONTRACTS}
        for name, (size, frames) in EXPECTED_FIXED.items():
            with self.subTest(sprite=name):
                self.assertEqual(contracts[name].kind, "spriteType", name)
                self.assertEqual(contracts[name].total_size, size, name)
                self.assertEqual(contracts[name].frames, frames, name)

    def test_operation_strip_keeps_two_equal_frames(self) -> None:
        contract = next(
            item
            for item in builder.INTELLIGENCE_CONTRACTS
            if item.target_name.endswith("operation_row")
        )
        self.assertEqual(contract.total_size, (1038, 89))
        self.assertEqual(contract.frames, 2)
        self.assertEqual(contract.total_size[0] // contract.frames, 519)

    def test_header_source_is_project_owned_and_large_enough(self) -> None:
        self.assertTrue(HEADER_SOURCE.is_file(), HEADER_SOURCE)
        with Image.open(HEADER_SOURCE) as image:
            self.assertIn(image.mode, ("RGB", "RGBA"))
            self.assertGreaterEqual(image.width, 1024)
            self.assertGreaterEqual(image.height, 512)
        header = next(
            item
            for item in builder.INTELLIGENCE_CONTRACTS
            if item.target_name.endswith("intelligence_header")
        )
        self.assertEqual(header.total_size, (519, 109))

    def test_dark_agency_tabs_use_a_pale_font(self) -> None:
        gui = AGENCY_GUI.read_text(encoding="utf-8-sig")
        for block_name in ("operations_tab_button", "crypto_tab_button"):
            block = named_button_block(gui, block_name)
            self.assertIn('font = "hoi_18mbs"', block)
            self.assertNotIn("hoi4_typewriter16", block)

    def test_other_typewriter_fonts_are_not_globally_replaced(self) -> None:
        vanilla = builder._verified_source("countryintelligenceagencyview.gui").decode(
            "utf-8-sig"
        )
        generated = builder.render_gui_files()[AGENCY_GUI].decode("utf-8")
        self.assertEqual(
            generated.count('font = "hoi4_typewriter16"'),
            vanilla.count('font = "hoi4_typewriter16"') - 2,
        )

    def test_decrypt_active_background_keeps_progress_bar_binding(self) -> None:
        gui = builder.render_gui_files()[AGENCY_GUI].decode("utf-8")
        self.assertEqual(
            gui.count('"GFX_decrypt_active_bg"'),
            builder._verified_source("countryintelligenceagencyview.gui")
            .decode("utf-8-sig")
            .count('"GFX_decrypt_active_bg"'),
        )
        additive_gfx = builder.render_gfx()
        self.assertNotIn('"GFX_decrypt_active_bg"', additive_gfx)
        self.assertNotRegex(
            additive_gfx,
            r'(?is)(?:spriteType|corneredTileSpriteType)\s*=\s*\{[^}]*'
            r'name\s*=\s*"GFX_decrypt_active_bg"',
        )

    def test_tab_frames_have_matching_silhouette_and_distinct_selected_edge(self) -> None:
        path = OUTPUT_DIR / "ADISCORD_intelligence_tabs.dds"
        with Image.open(path) as image:
            rgba = image.convert("RGBA")
        first = rgba.crop((0, 0, 262, 53))
        second = rgba.crop((262, 0, 524, 53))
        self.assertEqual(first.getchannel("A").tobytes(), second.getchannel("A").tobytes())
        edge_delta = ImageChops.difference(
            first.convert("RGB").crop((8, 47, 254, 52)),
            second.convert("RGB").crop((8, 47, 254, 52)),
        )
        self.assertIsNotNone(edge_delta.getbbox())

    def test_branch_row_separates_title_and_upgrade_card_zones(self) -> None:
        path = OUTPUT_DIR / "ADISCORD_intelligence_branch_row.dds"
        with Image.open(path) as image:
            rgba = image.convert("RGBA")
        title_value = mean_luminance(rgba, (12, 12, 1028, 39))
        card_value = mean_luminance(rgba, (12, 50, 208, 124))
        gutter_value = mean_luminance(rgba, (204, 50, 214, 124))
        self.assertGreater(title_value, gutter_value + 3)
        self.assertGreater(card_value, gutter_value + 3)

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

    def test_all_semantic_gui_references_resolve_to_additive_gfx(self) -> None:
        combined = "\n".join(
            path.read_text(encoding="utf-8-sig")
            for path in (AGENCY_GUI, OPERATIVE_GUI, LEADER_GUI)
        )
        references = set(
            re.findall(r'"(GFX_ADISCORD_intelligence_[^"]+)"', combined)
        )
        declarations = set(
            re.findall(
                r'name\s*=\s*"(GFX_ADISCORD_intelligence_[^"]+)"',
                GFX.read_text(encoding="utf-8-sig"),
            )
        )
        self.assertTrue(references)
        self.assertEqual(references - declarations, set())

    def test_obsolete_generic_intelligence_surfaces_are_removed(self) -> None:
        combined = "\n".join(
            path.read_text(encoding="utf-8-sig")
            for path in (AGENCY_GUI, OPERATIVE_GUI, LEADER_GUI)
        )
        for role in ("window", "panel", "card", "selected"):
            self.assertNotIn(f'"GFX_ADISCORD_intelligence_{role}"', combined)
            self.assertFalse(
                (OUTPUT_DIR / f"ADISCORD_intelligence_{role}.dds").exists(), role
            )

    def test_custom_gfx_is_additive_and_outputs_are_current(self) -> None:
        self.assertTrue(GFX.is_file())
        self.assertFalse((ROOT / "interface/countryintelligenceagencyview.gfx").exists())
        self.assertFalse((ROOT / "interface/operativeleader.gfx").exists())
        outputs = builder.expected_outputs()
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

    def test_runtime_dds_directory_contains_only_builder_owned_outputs(self) -> None:
        owned = {
            path for path in builder.expected_outputs() if path.suffix == ".dds"
        }
        checked_in = set(OUTPUT_DIR.glob("*.dds"))
        self.assertEqual(checked_in, owned)


if __name__ == "__main__":
    unittest.main()
