"""Contracts for the generated market skin and its engine-owned controls."""

import io
import re
import unittest

from PIL import Image

from tools.builders import build_adiscord_market_ui_assets as builder
from tools.lib.adiscord_ui_contracts import native_sprite_blocks
from tools.tests.test_validate_adiscord_gui_contracts import gui_node_body


def horizontal_span(body):
    left = int(re.search(r'position\s*=\s*\{\s*x\s*=\s*(-?\d+)', body)[1])
    width = int(re.search(r'\bmaxWidth\s*=\s*(\d+)', body)[1])
    return left, left + width


class MarketUiContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.outputs = builder.expected_outputs()

    def test_all_market_windows_preserve_widgets_geometry_and_localisation(self):
        for name in builder.GUI_FILES:
            with self.subTest(window=name):
                native = (builder.VANILLA_DIR / name).read_text(encoding="utf-8-sig")
                native = "\n".join(line.rstrip() for line in native.splitlines()) + "\n"
                rendered = builder.render_gui(name)
                for source, role in builder.SURFACES.items():
                    rendered = rendered.replace(f'"GFX_ADISCORD_market_{role}"', f'"{source}"')
                if name == "marketequipmentstockpilewindow.gui":
                    rendered = re.sub(r'(name = "add_to_market_button".*?font = )"hoi_16mbs"', r'\1"hoi_18mbs"', rendered, count=1, flags=re.S)
                elif name == "pricelevelswidgets.gui":
                    rendered = rendered.replace('font = "hoi_16mbs"', 'font = "hoi_18mbs"').replace('maxWidth = 150', 'maxWidth = 100')
                elif name == "marketpurchasedraftwindow.gui":
                    for widget in ("name", "stockpile_amount", "cic_cost", "equipment_header",
                                   "value_header", "applied_header", "applied_text"):
                        rendered = rendered.replace(gui_node_body(rendered, widget),
                                                    gui_node_body(native, widget), 1)
                    row = gui_node_body(rendered, "subsidies_draft_item")
                    native_row = gui_node_body(native, "subsidies_draft_item")
                    restored_row = row.replace(gui_node_body(row, "stockpile_amount_bg"),
                                               gui_node_body(native_row, "stockpile_amount_bg"), 1)
                    rendered = rendered.replace(row, restored_row, 1)
                self.assertEqual(rendered, native)

    def test_surface_dimensions_alpha_and_frame_metadata_match_native_controls(self):
        gfx = self.outputs[builder.GFX_OUTPUT].decode("utf-8")
        for name, block in native_sprite_blocks(builder.BASE_GAME, set(builder.SURFACES)).items():
            with self.subTest(sprite=name):
                source = re.search(r'\btexturefile\s*=\s*"([^"]+)"', block, re.I)
                texture = builder.BASE_GAME / source[1]
                if not texture.is_file():
                    texture = texture.with_suffix(".dds")
                role = builder.SURFACES[name]
                path = builder.OUTPUT_DIR / f"ADISCORD_market_{role}.dds"
                with Image.open(texture) as image:
                    native = image.convert("RGBA")
                rendered = Image.open(io.BytesIO(self.outputs[path])).convert("RGBA")
                self.assertEqual(rendered.size, native.size)
                self.assertEqual(rendered.getchannel("A").tobytes(), native.getchannel("A").tobytes())
                expected = block.replace(f'"{name}"', f'"GFX_ADISCORD_market_{role}"')
                expected = expected.replace(source[0], f'textureFile = "gfx/interface/international_market/adiscord/{path.name}"')
                self.assertIn(expected, gfx)

    def test_generated_outputs_are_current_and_have_no_vanilla_gfx_override(self):
        self.assertFalse((builder.ROOT / "interface/international_market/international_market.gfx").exists())
        for path, data in self.outputs.items():
            with self.subTest(path=path.relative_to(builder.ROOT)):
                self.assertTrue(path.is_file())
                self.assertTrue(path.read_bytes() == data)

    def test_purchase_equipment_labels_leave_room_for_quantity_and_convoys(self):
        gui = builder.render_gui("marketpurchasedraftwindow.gui")
        row = gui_node_body(gui, "market_draft_equipment_entry")
        for label, limit in (("name", 190), ("stockpile_amount", 277), ("cic_cost", 390)):
            with self.subTest(label=label):
                left, right = horizontal_span(gui_node_body(row, label))
                self.assertGreaterEqual(left, 0)
                self.assertLessEqual(right + 4, limit)

    def test_subsidy_headers_do_not_overlap_and_align_with_amounts(self):
        gui = builder.render_gui("marketpurchasedraftwindow.gui")
        panel = gui_node_body(gui, "subsidy_draft")
        spans = [horizontal_span(gui_node_body(panel, name)) for name in
                 ("equipment_header", "value_header", "applied_header")]
        for previous, following in zip(spans, spans[1:]):
            self.assertLessEqual(previous[1] + 3, following[0])
        self.assertLessEqual(spans[-1][1], 375 - 10)
        row = gui_node_body(gui, "subsidies_draft_item")
        for span, name in zip(spans[1:], ("cic_text", "applied_text")):
            left, right = horizontal_span(gui_node_body(row, name))
            # Rows are placed at x=12 by the parent grid.
            self.assertLessEqual(abs(sum(span) / 2 - (12 + (left + right) / 2)), 2)


if __name__ == "__main__":
    unittest.main()
