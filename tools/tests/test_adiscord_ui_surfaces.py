from pathlib import Path
from contextlib import redirect_stdout
from io import StringIO
from tempfile import TemporaryDirectory
import unittest

from PIL import Image

from tools.lib.adiscord_ui_surfaces import (
    PALETTES,
    apply_or_check,
    button_strip,
    dds_bytes,
    framed_panel,
    horizontal_state_strip,
    outer_frame,
    partial_rails,
    raised_field,
    recessed_well,
    replace_counted,
    status_band,
    surface,
)


class UiSurfaceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.source = Image.new("RGBA", (1024, 1024), (39, 43, 44, 255))

    def assert_changes_stay_inside(
        self,
        before: Image.Image,
        after: Image.Image,
        box: tuple[int, int, int, int],
    ) -> None:
        left, top, right, bottom = box
        changed = [
            (x, y)
            for y in range(after.height)
            for x in range(after.width)
            if before.getpixel((x, y)) != after.getpixel((x, y))
        ]
        self.assertTrue(changed)
        self.assertTrue(
            all(left <= x <= right and top <= y <= bottom for x, y in changed),
            changed,
        )

    def test_four_section_palettes_produce_distinct_accents(self) -> None:
        self.assertEqual(
            set(PALETTES),
            {"technology", "logistics", "deployment", "intelligence"},
        )
        self.assertEqual(len({palette.accent for palette in PALETTES.values()}), 4)

    def test_panel_and_three_state_button_have_engine_dimensions(self) -> None:
        panel = framed_panel(
            self.source,
            (192, 192),
            PALETTES["technology"],
            0.82,
        )
        strip = button_strip(
            self.source,
            (81, 41),
            PALETTES["technology"],
        )

        self.assertEqual(panel.size, (192, 192))
        self.assertEqual(strip.size, (243, 41))
        self.assertEqual(panel.getchannel("A").getextrema(), (255, 255))

    def test_counted_replacement_rejects_upstream_contract_drift(self) -> None:
        source = 'spriteType = "GFX_old"\nquadTextureSprite = "GFX_old"\n'
        self.assertEqual(
            replace_counted(source, "GFX_old", "GFX_new", 2).count('"GFX_new"'),
            2,
        )
        with self.assertRaisesRegex(ValueError, "expected 1, found 2"):
            replace_counted(source, "GFX_old", "GFX_new", 1)

    def test_apply_or_check_writes_only_in_apply_mode(self) -> None:
        with TemporaryDirectory() as temp:
            path = Path(temp) / "panel.dds"
            outputs = {path: dds_bytes(self.source)}

            with redirect_stdout(StringIO()):
                self.assertEqual(apply_or_check(outputs, apply=False, label="test"), 1)
            self.assertFalse(path.exists())
            with redirect_stdout(StringIO()):
                self.assertEqual(apply_or_check(outputs, apply=True, label="test"), 0)
            self.assertTrue(path.exists())
            with redirect_stdout(StringIO()):
                self.assertEqual(apply_or_check(outputs, apply=False, label="test"), 0)

    def test_recess_and_status_band_change_only_their_declared_zones(self) -> None:
        image = Image.new("RGBA", (96, 64), (40, 42, 44, 255))
        recessed_well(image, (8, 10, 55, 48), PALETTES["deployment"])
        status_band(image, (60, 10, 90, 15), (132, 151, 78, 255))

        self.assertEqual(image.getpixel((2, 2)), (40, 42, 44, 255))
        self.assertNotEqual(image.getpixel((8, 10)), (40, 42, 44, 255))
        self.assertEqual(image.getpixel((70, 12)), (132, 151, 78, 255))

    def test_partial_rails_do_not_draw_a_repeated_full_outer_frame(self) -> None:
        image = Image.new("RGBA", (96, 64), (40, 42, 44, 255))
        partial_rails(image, (5, 6, 90, 58), PALETTES["intelligence"])

        self.assertEqual(image.getpixel((5, 6)), (40, 42, 44, 255))
        self.assertNotEqual(image.getpixel((48, 6)), (40, 42, 44, 255))

    def test_surface_frame_field_and_state_strip_remain_inside_their_boxes(self) -> None:
        image = Image.new("RGBA", (96, 64), (40, 42, 44, 255))
        palette = PALETTES["technology"]

        surface(image, (10, 10, 35, 30), palette)
        outer_frame(image, (40, 10, 65, 30), palette)
        raised_field(image, (10, 35, 35, 55), palette)
        horizontal_state_strip(
            image,
            (40, 35, 65, 55),
            palette,
            (palette.edge, palette.accent_light),
        )

        self.assertNotEqual(image.getpixel((20, 20)), (40, 42, 44, 255))
        self.assertNotEqual(image.getpixel((40, 10)), (40, 42, 44, 255))
        self.assertNotEqual(image.getpixel((20, 45)), (40, 42, 44, 255))
        self.assertNotEqual(image.getpixel((45, 45)), (40, 42, 44, 255))
        self.assertEqual(image.getpixel((2, 2)), (40, 42, 44, 255))

    def test_inset_primitives_keep_narrow_boxes_isolated(self) -> None:
        palette = PALETTES["intelligence"]
        cases = (
            (outer_frame, (10, 10, 12, 20)),
            (partial_rails, (20, 10, 22, 20)),
        )

        for primitive, box in cases:
            with self.subTest(primitive=primitive.__name__):
                image = Image.new("RGBA", (48, 32), (40, 42, 44, 255))
                before = image.copy()
                primitive(image, box, palette)
                self.assert_changes_stay_inside(before, image, box)

    def test_wells_keep_one_pixel_boxes_isolated(self) -> None:
        palette = PALETTES["deployment"]
        cases = (recessed_well, raised_field)

        for primitive in cases:
            with self.subTest(primitive=primitive.__name__):
                image = Image.new("RGBA", (48, 32), (40, 42, 44, 255))
                before = image.copy()
                primitive(image, (10, 10, 10, 10), palette)
                self.assert_changes_stay_inside(before, image, (10, 10, 10, 10))


if __name__ == "__main__":
    unittest.main()
