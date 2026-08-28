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
STATE_GFX = ROOT / "interface/zz_ADISCORD_technology_states.gfx"
EXPECTED_STATES = {
    "GFX_technology_unavailable_item_bg": ((183, 84), 1),
    "GFX_technology_available_item_bg": ((183, 84), 1),
    "GFX_technology_researched_item_bg": ((183, 84), 1),
    "GFX_technology_branch_item_bg": ((183, 84), 1),
    "GFX_technology_currently_researching_item_bg": ((1647, 84), 9),
}
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

    def test_tree_skin_uses_tree_and_detail_roles(self) -> None:
        gui = (ROOT / "interface/countrytechtreeview.gui").read_text(
            encoding="utf-8-sig"
        )
        self.assertEqual(gui.count('"GFX_ADISCORD_technology_tree_window_tile"'), 12)
        self.assertEqual(gui.count('"GFX_ADISCORD_technology_info_top"'), 2)
        self.assertEqual(gui.count('"GFX_ADISCORD_technology_info"'), 2)
        self.assertNotIn('"GFX_ADISCORD_technology_tree_panel"', gui)

    def test_state_overrides_are_additive_late_loaded_and_single_owner(self) -> None:
        self.assertTrue(STATE_GFX.is_file())
        self.assertFalse((ROOT / "interface/countrytechtreeview.gfx").exists())
        self.assertGreater(STATE_GFX.name.lower(), "countrytechtreeview.gfx")

        state_text = STATE_GFX.read_text(encoding="utf-8-sig")
        declared = re.findall(r'name\s*=\s*"(GFX_technology_[^"]+_item_bg)"', state_text)
        self.assertEqual(set(declared), set(EXPECTED_STATES))
        self.assertEqual(len(declared), len(EXPECTED_STATES))
        for engine_state in EXPECTED_STATES:
            declaration = re.compile(
                rf'name\s*=\s*"{re.escape(engine_state)}"'
            )
            owners = [
                path
                for path in (ROOT / "interface").glob("*.gfx")
                if declaration.search(path.read_text(encoding="utf-8-sig"))
            ]
            self.assertEqual(owners, [STATE_GFX], engine_state)

    def test_technology_states_preserve_engine_names_dimensions_and_metadata(self) -> None:
        contracts = {
            item.target_name: item for item in builder.TECHNOLOGY_STATE_CONTRACTS
        }
        for name, (size, frames) in EXPECTED_STATES.items():
            with self.subTest(sprite=name):
                self.assertEqual(contracts[name].total_size, size)
                self.assertEqual(contracts[name].frames, frames)
                self.assertIsNone(contracts[name].effect_file)

        for name in EXPECTED_STATES.keys() - {
            "GFX_technology_currently_researching_item_bg"
        }:
            self.assertEqual(contracts[name].kind, "spriteType")
            self.assertEqual(contracts[name].extra_lines, ())
        researching = contracts["GFX_technology_currently_researching_item_bg"]
        self.assertEqual(researching.kind, "frameAnimatedSpriteType")
        self.assertEqual(
            researching.extra_lines,
            (
                'loadType = "INGAME"',
                "transparencecheck = yes",
                "animation_rate_fps = 15",
                "looping = yes",
                "play_on_show = yes",
                "pause_on_loop = 0.0",
            ),
        )

    def test_node_states_share_geometry_and_use_only_muted_edge_status_identity(self) -> None:
        outputs = builder.expected_outputs()
        filenames = {
            "unavailable": "ADISCORD_technology_node_unavailable.dds",
            "available": "ADISCORD_technology_node_available.dds",
            "researched": "ADISCORD_technology_node_researched.dds",
            "branch": "ADISCORD_technology_node_branch.dds",
        }
        images = {
            state: Image.open(io.BytesIO(outputs[ASSET_DIR / filename])).convert("RGBA")
            for state, filename in filenames.items()
        }
        shared_interior = images["unavailable"].crop((8, 8, 175, 67)).tobytes()
        for state, image in images.items():
            with self.subTest(state=state):
                self.assertEqual(image.crop((8, 8, 175, 67)).tobytes(), shared_interior)
                self.assertEqual(image.size, (183, 84))

        unavailable_edge = images["unavailable"].getpixel((3, 3))[:3]
        self.assertLessEqual(max(unavailable_edge) - min(unavailable_edge), 8)
        available_edge = images["available"].getpixel((3, 3))[:3]
        self.assertGreater(available_edge[0], available_edge[1])
        self.assertGreater(available_edge[1], available_edge[2])
        researched_edge = images["researched"].getpixel((3, 3))[:3]
        self.assertGreater(researched_edge[1], researched_edge[0] + 20)
        self.assertGreater(researched_edge[1], researched_edge[2] + 12)

        researching_path = ASSET_DIR / "ADISCORD_technology_node_researching.dds"
        strip = Image.open(io.BytesIO(outputs[researching_path])).convert("RGBA")
        frame_interiors = []
        bright_segments = []
        for index in range(9):
            frame = strip.crop((183 * index, 0, 183 * (index + 1), 84))
            frame_interiors.append(frame.crop((8, 8, 175, 67)).tobytes())
            bright_segments.append(
                tuple(
                    x
                    for x in range(183)
                    if frame.getpixel((x, 3))[1] > 140
                    and frame.getpixel((x, 3))[2] > 140
                )
            )
        self.assertEqual(len(set(frame_interiors)), 1)
        self.assertTrue(all(bright_segments))
        self.assertEqual(len(set(bright_segments)), 9)

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

    def test_runtime_dds_directory_contains_only_builder_owned_outputs(self) -> None:
        owned = {
            path for path in builder.expected_outputs() if path.suffix == ".dds"
        }
        checked_in = set(ASSET_DIR.glob("*.dds"))
        self.assertEqual(checked_in, owned)


if __name__ == "__main__":
    unittest.main()
