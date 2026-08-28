import io
from pathlib import Path
import re
import unittest

from PIL import Image, ImageChops, ImageStat

from tools.builders.build_adiscord_technology_system import FOLDER_BACKGROUNDS
from tools.builders import build_adiscord_technology_ui_assets as builder


ROOT = Path(__file__).resolve().parents[2]
GUI = ROOT / "interface/countrytechnologyview.gui"
GFX = ROOT / "interface/ADISCORD_technology_ui.gfx"
ASSET_DIR = ROOT / "gfx/interface/technology/ui"
PREVIEW = (
    ROOT
    / "gfx/interface/technology/preview/ADISCORD_technology_overview_preview.png"
)
LEGACY_GENERIC_ROLES = (
    "window",
    "panel",
    "card",
    "tab",
    "tree_panel",
    "tree_info_top",
    "tree_info",
)


EXPECTED_OVERVIEW = {
    "GFX_ADISCORD_technology_slot": ((508, 99), 1),
    "GFX_ADISCORD_technology_idea": ((63, 63), 1),
    "GFX_ADISCORD_technology_tabs": ((516, 42), 2),
    "GFX_ADISCORD_technology_top": ((548, 138), 1),
    "GFX_ADISCORD_technology_bottom": ((546, 66), 1),
    "GFX_ADISCORD_technology_info_top": ((548, 220), 1),
    "GFX_ADISCORD_technology_info": ((508, 517), 1),
}


def mean_luminance(image: Image.Image, box: tuple[int, int, int, int]) -> float:
    return ImageStat.Stat(image.convert("L").crop(box)).mean[0]


class TechnologyUiContractTests(unittest.TestCase):
    def test_overview_assets_keep_native_dimensions_frames_and_metadata(self) -> None:
        contracts = {
            item.target_name: item for item in builder.TECHNOLOGY_OVERVIEW_CONTRACTS
        }
        for name, (size, frames) in EXPECTED_OVERVIEW.items():
            with self.subTest(sprite=name):
                self.assertEqual(contracts[name].total_size, size, name)
                self.assertEqual(contracts[name].frames, frames, name)

        self.assertEqual(contracts["GFX_ADISCORD_technology_slot"].kind, "spriteType")
        self.assertEqual(contracts["GFX_ADISCORD_technology_idea"].kind, "spriteType")
        self.assertEqual(contracts["GFX_ADISCORD_technology_tabs"].kind, "spriteType")
        self.assertEqual(contracts["GFX_ADISCORD_technology_top"].kind, "spriteType")
        self.assertEqual(
            contracts["GFX_ADISCORD_technology_bottom"].kind,
            "corneredTileSpriteType",
        )
        self.assertEqual(contracts["GFX_ADISCORD_technology_info_top"].kind, "spriteType")
        self.assertEqual(contracts["GFX_ADISCORD_technology_info"].kind, "spriteType")
        self.assertIsNone(contracts["GFX_ADISCORD_technology_slot"].effect_file)
        self.assertEqual(
            contracts["GFX_ADISCORD_technology_idea"].effect_file,
            builder.EFFECT,
        )
        self.assertEqual(
            contracts["GFX_ADISCORD_technology_bottom"].border_size,
            (182, 22),
        )
        self.assertTrue(contracts["GFX_ADISCORD_technology_bottom"].tiling_center)
        self.assertEqual(
            contracts["GFX_ADISCORD_technology_info_top"].effect_file,
            builder.EFFECT,
        )
        self.assertEqual(
            contracts["GFX_ADISCORD_technology_info"].effect_file,
            builder.EFFECT,
        )

    def test_outer_content_overlay_and_tree_tiles_have_distinct_contracts(self) -> None:
        contracts = {
            item.source_name: item for item in builder.TECHNOLOGY_OVERVIEW_CONTRACTS
        }
        expected_tiles = {
            "GFX_tiled_window2_1b_border": (
                "GFX_ADISCORD_technology_window_shell",
                (190, 190),
            ),
            "GFX_tiled_plain_bg": (
                "GFX_ADISCORD_technology_content_tile",
                (190, 190),
            ),
            "GFX_tiled_generic_overlay_bg1": (
                "GFX_ADISCORD_technology_overlay",
                (549, 600),
            ),
            "GFX_tiled_window_2b_border": (
                "GFX_ADISCORD_technology_tree_window_tile",
                (190, 190),
            ),
            "GFX_techtree_stripes": (
                "GFX_ADISCORD_technology_tree_stripes",
                (122, 244),
            ),
        }
        for source, (target, size) in expected_tiles.items():
            with self.subTest(source=source):
                self.assertEqual(contracts[source].target_name, target)
                self.assertEqual(contracts[source].kind, "corneredTileSpriteType")
                self.assertEqual(contracts[source].total_size, size)
        self.assertEqual(len({target for target, _ in expected_tiles.values()}), 5)

    def test_fixed_sprite_targets_are_not_declared_as_cornered_tiles(self) -> None:
        contracts = {
            item.target_name: item for item in builder.TECHNOLOGY_OVERVIEW_CONTRACTS
        }
        for name in EXPECTED_OVERVIEW:
            if name == "GFX_ADISCORD_technology_bottom":
                continue
            with self.subTest(sprite=name):
                self.assertEqual(contracts[name].kind, "spriteType")

    def test_research_slot_has_distinct_icon_title_progress_and_time_zones(self) -> None:
        outputs = builder.expected_outputs()
        image = Image.open(io.BytesIO(outputs[builder.SLOT])).convert("RGBA")
        self.assertNotEqual(image.getpixel((34, 46)), image.getpixel((250, 46)))
        self.assertNotEqual(image.getpixel((250, 46)), image.getpixel((430, 73)))

    def test_tabs_share_silhouette_but_use_a_distinct_selected_edge(self) -> None:
        outputs = builder.expected_outputs()
        image = Image.open(io.BytesIO(outputs[builder.TABS])).convert("RGBA")
        normal = image.crop((0, 0, 258, 42))
        selected = image.crop((258, 0, 516, 42))
        self.assertEqual(
            normal.getchannel("A").tobytes(),
            selected.getchannel("A").tobytes(),
        )
        edge_delta = ImageChops.difference(
            normal.convert("RGB").crop((8, 35, 250, 41)),
            selected.convert("RGB").crop((8, 35, 250, 41)),
        )
        self.assertIsNotNone(edge_delta.getbbox())
        self.assertLess(
            abs(mean_luminance(normal, (12, 8, 246, 31)) - mean_luminance(selected, (12, 8, 246, 31))),
            18,
        )

    def test_detail_writing_surfaces_are_lighter_than_tree_background(self) -> None:
        outputs = builder.expected_outputs()
        tree = Image.open(io.BytesIO(outputs[builder.TREE_WINDOW_TILE])).convert("RGBA")
        top = Image.open(io.BytesIO(outputs[builder.INFO_TOP])).convert("RGBA")
        info = Image.open(io.BytesIO(outputs[builder.INFO])).convert("RGBA")
        tree_value = mean_luminance(tree, (20, 20, 170, 170))
        self.assertGreater(mean_luminance(top, (25, 25, 523, 195)), tree_value + 12)
        self.assertGreater(mean_luminance(info, (25, 25, 483, 492)), tree_value + 12)

    def test_tree_skin_uses_tree_and_detail_roles_without_node_state_overrides(self) -> None:
        gui = (ROOT / "interface/countrytechtreeview.gui").read_text(
            encoding="utf-8-sig"
        )
        self.assertEqual(gui.count('"GFX_ADISCORD_technology_tree_window_tile"'), 12)
        self.assertEqual(gui.count('"GFX_ADISCORD_technology_info_top"'), 2)
        self.assertEqual(gui.count('"GFX_ADISCORD_technology_info"'), 2)
        self.assertNotIn('"GFX_ADISCORD_technology_tree_panel"', gui)
        gfx = "\n".join(
            path.read_text(encoding="utf-8-sig")
            for path in (GFX, ROOT / "interface/ADISCORD_technologies.gfx")
        )
        for engine_state in (
            "GFX_technology_unavailable_item_bg",
            "GFX_technology_available_item_bg",
            "GFX_technology_currently_researching_item_bg",
            "GFX_technology_researched_item_bg",
        ):
            self.assertNotIn(f'name = "{engine_state}"', gfx)
        self.assertFalse((ROOT / "interface/zz_ADISCORD_technology_states.gfx").exists())

    def test_obsolete_generic_technology_surfaces_are_unreferenced_and_removed(self) -> None:
        combined = "\n".join(
            path.read_text(encoding="utf-8-sig")
            for path in (
                GUI,
                GFX,
                ROOT / "interface/countrytechtreeview.gui",
            )
        )
        for role in LEGACY_GENERIC_ROLES:
            with self.subTest(role=role):
                stem = f"ADISCORD_technology_{role}"
                self.assertNotIn(f'"GFX_{stem}"', combined)
                self.assertFalse((ASSET_DIR / f"{stem}.dds").exists())

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

    def test_research_gui_changes_only_counted_sprite_bindings(self) -> None:
        vanilla = builder.VANILLA_GUI.read_text(encoding="utf-8-sig")
        normalized = "\n".join(line.rstrip() for line in vanilla.splitlines()) + "\n"
        normalized = re.sub(r"(?m)^ +(?=\t)", "", normalized)
        restored = builder.render_gui()
        for old, (new, expected) in builder.SPRITE_REPLACEMENTS.items():
            self.assertEqual(restored.count(f'"{new}"'), expected, new)
            restored = restored.replace(f'"{new}"', f'"{old}"')
        self.assertEqual(restored, normalized)

    def test_research_shell_uses_adiscord_surfaces(self) -> None:
        gui = GUI.read_text(encoding="utf-8-sig")
        for sprite in (
            "GFX_ADISCORD_technology_window_shell",
            "GFX_ADISCORD_technology_content_tile",
            "GFX_ADISCORD_technology_overlay",
            "GFX_ADISCORD_technology_slot",
            "GFX_ADISCORD_technology_tabs",
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
            "GFX_ADISCORD_technology_tree_window_tile",
            "GFX_ADISCORD_technology_tree_stripes",
            "GFX_ADISCORD_technology_info",
        ):
            self.assertIn(f'"{sprite}"', gui)

    def test_all_semantic_gui_references_resolve_to_additive_gfx(self) -> None:
        gui = "\n".join(
            path.read_text(encoding="utf-8-sig")
            for path in (GUI, ROOT / "interface/countrytechtreeview.gui")
        )
        declarations = "\n".join(
            path.read_text(encoding="utf-8-sig")
            for path in (GFX, ROOT / "interface/ADISCORD_technologies.gfx")
        )
        references = set(re.findall(r'"(GFX_ADISCORD_technology_[^"]+)"', gui))
        declared = set(
            re.findall(
                r'name\s*=\s*"(GFX_ADISCORD_technology_[^"]+)"',
                declarations,
            )
        )
        self.assertTrue(references)
        self.assertEqual(references - declared, set())

    def test_expected_outputs_match_checked_in_assets(self) -> None:
        outputs = builder.expected_outputs()
        self.assertIn(GUI, outputs)
        self.assertIn(GFX, outputs)
        self.assertIn(PREVIEW, outputs)
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
