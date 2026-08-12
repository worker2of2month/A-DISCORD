import re
import unittest

from PIL import Image

from tools.builders.build_adiscord_resource_assets import (
    ROOT,
    STATEVIEW_BUILD_SLOT,
    STATEVIEW_OUTPUT_SIZES,
    STATEVIEW_WW_BACKGROUND,
    STATEVIEW_WW_ENTRY,
    expected_outputs,
)


def named_gui_block(text: str, declaration: str, name: str) -> str:
    for match in re.finditer(rf"\b{re.escape(declaration)}\s*=\s*\{{", text):
        depth = 0
        for index in range(match.end() - 1, len(text)):
            if text[index] == "{":
                depth += 1
            elif text[index] == "}":
                depth -= 1
                if depth == 0:
                    block = text[match.start() : index + 1]
                    if re.search(rf'\bname\s*=\s*"{re.escape(name)}"', block):
                        return block
                    break
    raise AssertionError(f"Missing {declaration} named {name}")


class StateViewUIContracts(unittest.TestCase):
    def test_native_stateview_paths_are_current_and_keep_engine_dimensions(self) -> None:
        outputs = expected_outputs()
        for path, size in STATEVIEW_OUTPUT_SIZES.items():
            self.assertIn(path, outputs)
            self.assertTrue(path.is_file(), path)
            self.assertEqual(path.read_bytes(), outputs[path], path)
            with Image.open(path) as image:
                self.assertEqual(image.size, size, path.name)

    def test_stateview_shell_has_transparent_corners_and_visible_section_accents(self) -> None:
        with Image.open(STATEVIEW_WW_BACKGROUND) as image:
            panel = image.convert("RGBA")
        alpha = panel.getchannel("A")
        self.assertEqual(alpha.getpixel((0, 0)), 0)
        self.assertEqual(alpha.getpixel((panel.width - 1, panel.height - 1)), 0)
        self.assertEqual(alpha.getpixel((panel.width // 2, panel.height // 2)), 255)
        pixels = panel.load()
        cyan_pixels = sum(
            1
            for y in range(panel.height)
            for x in range(panel.width)
            if (pixel := pixels[x, y])[3]
            and pixel[1] > pixel[0] + 25
            and pixel[2] > pixel[0] + 25
        )
        self.assertGreater(cyan_pixels, 1000)

    def test_building_cards_and_shared_slots_are_separate_compact_surfaces(self) -> None:
        with Image.open(STATEVIEW_WW_ENTRY) as image:
            standing = image.convert("RGBA")
        with Image.open(STATEVIEW_BUILD_SLOT) as image:
            slot = image.convert("RGBA")
        standing_box = standing.getchannel("A").getbbox()
        self.assertIsNotNone(standing_box)
        self.assertLessEqual(standing_box[2] - standing_box[0], 58)
        self.assertLessEqual(standing_box[3] - standing_box[1], 79)
        self.assertEqual(slot.getchannel("A").getbbox(), (0, 0, 56, 46))
        self.assertNotEqual(standing.resize(slot.size).tobytes(), slot.tobytes())

    def test_state_resources_have_a_baked_panel_under_the_hard_coded_grid(self) -> None:
        with Image.open(STATEVIEW_WW_BACKGROUND) as image:
            panel = image.convert("RGBA")
        # Vertical and horizontal separators of the two-by-four resource bay.
        self.assertNotEqual(panel.getpixel((76, 290)), panel.getpixel((75, 290)))
        self.assertNotEqual(panel.getpixel((45, 303)), panel.getpixel((45, 302)))

        gui = (ROOT / "interface/countrystateview.gui").read_text(encoding="utf-8-sig")
        resources = named_gui_block(gui, "containerWindowType", "state_resources")
        entries = named_gui_block(resources, "gridBoxType", "state_resources_entries")
        self.assertRegex(
            entries,
            r"\bposition\s*=\s*\{\s*x\s*=\s*-44\s+y\s*=\s*-1\s*\}",
        )

    def test_building_icons_and_overlays_are_centered_in_custom_cards(self) -> None:
        gui = (ROOT / "interface/countrystateview.gui").read_text(encoding="utf-8-sig")
        expected_positions = {
            "state_building_entry": {
                ("buttonType", "building_picture"): (8, 5),
                ("iconType", "damage_bar"): (6, 41),
            },
            "state_shared_slot_building_entry": {
                ("buttonType", "building_picture"): (5, 0),
                ("iconType", "building_status_overlay"): (5, 0),
                ("buttonType", "remove"): (35, 29),
                ("iconType", "damage_bar"): (2, 36),
            },
            "province_building_entry": {
                ("buttonType", "building_picture"): (8, 5),
                ("iconType", "damage_bar"): (6, 42),
            },
        }
        for container_name, entries in expected_positions.items():
            container = named_gui_block(gui, "containerWindowType", container_name)
            for (declaration, entry_name), (x, y) in entries.items():
                entry = named_gui_block(container, declaration, entry_name)
                self.assertRegex(
                    entry,
                    rf"\bposition\s*=\s*\{{\s*x\s*=\s*{x}\s+y\s*=\s*{y}\s*\}}",
                    f"{container_name}.{entry_name}",
                )


if __name__ == "__main__":
    unittest.main()
