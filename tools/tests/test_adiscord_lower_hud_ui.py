import json
import unittest
from pathlib import Path

from PIL import Image

from tools.builders.build_adiscord_minimap import (
    MAPMODE_BIG_DESELECTED_PATH,
    MAPMODE_BIG_BG_PATH,
    MAPMODE_BIG_SELECTED_PATH,
    MAPMODE_MAIN_BG_PATH,
    MINIMAP_BORDER_PATH,
    MINIMAP_PATH,
    OUTPUT_SIZES,
    expected_outputs,
)


ROOT = Path(__file__).resolve().parents[2]


class LowerHudUIContracts(unittest.TestCase):
    def test_generated_output_registry_assigns_every_lower_hud_asset(self) -> None:
        registry = json.loads(
            (ROOT / "tools/data/generated_output_owners.json").read_text(encoding="utf-8")
        )
        minimap = next(family for family in registry["families"] if family["id"] == "minimap")
        self.assertEqual(
            set(minimap["output_globs"]),
            {path.relative_to(ROOT).as_posix() for path in OUTPUT_SIZES},
        )

    def test_builder_owns_current_complete_lower_hud_skin(self) -> None:
        outputs = expected_outputs()
        self.assertEqual(set(outputs), set(OUTPUT_SIZES))
        for path, expected in outputs.items():
            self.assertTrue(path.is_file(), f"missing generated asset: {path.relative_to(ROOT)}")
            self.assertEqual(path.read_bytes(), expected, f"stale generated asset: {path.relative_to(ROOT)}")
            with Image.open(path) as image:
                self.assertEqual(image.size, OUTPUT_SIZES[path], path.name)

    def test_minimap_frame_keeps_the_world_visible(self) -> None:
        with Image.open(MINIMAP_PATH) as image:
            self.assertEqual(image.size, (268, 97))
        with Image.open(MINIMAP_BORDER_PATH) as image:
            border = image.convert("RGBA")
        alpha = border.getchannel("A")
        self.assertEqual(alpha.getpixel((138, 52)), 0)
        self.assertGreater(alpha.getpixel((2, 52)), 0)
        self.assertGreater(alpha.getpixel((138, 102)), 0)

    def test_mapmode_dock_has_real_selected_and_deselected_states(self) -> None:
        with Image.open(MAPMODE_MAIN_BG_PATH) as image:
            dock = image.convert("RGBA")
        self.assertIsNotNone(dock.getchannel("A").getbbox())
        pixels = dock.load()
        cyan_pixels = sum(
            1
            for y in range(dock.height)
            for x in range(dock.width)
            if (pixel := pixels[x, y])[3]
            and pixel[1] > pixel[0] + 25
            and pixel[2] > pixel[0] + 25
        )
        self.assertGreater(cyan_pixels, 100)
        self.assertNotEqual(
            MAPMODE_BIG_SELECTED_PATH.read_bytes(),
            MAPMODE_BIG_DESELECTED_PATH.read_bytes(),
        )

    def test_big_mapmode_sockets_fit_the_tight_dlc_spacing(self) -> None:
        with Image.open(MAPMODE_BIG_BG_PATH) as image:
            alpha_box = image.convert("RGBA").getchannel("A").getbbox()
        self.assertIsNotNone(alpha_box)
        self.assertLessEqual(alpha_box[3] - alpha_box[1], 35)
        self.assertGreaterEqual(alpha_box[1], 8)


if __name__ == "__main__":
    unittest.main()
