#!/usr/bin/env python3
"""Build the A-Discord arms-market skin with native widget and frame geometry."""

from __future__ import annotations

import argparse
from io import BytesIO
from pathlib import Path
import re

from PIL import Image, ImageDraw, ImageOps

from tools.builders.build_adiscord_resource_assets import (
    _fit_glyph, _international_market_source_icon,
)
from tools.lib.adiscord_ui_contracts import contact_sheet, native_sprite_blocks, replace_gui_block
from tools.lib.adiscord_ui_surfaces import (
    PALETTES, apply_or_check, dds_bytes, load_surface_source, metal_surface,
)
from tools.lib.paths import repository_root


ROOT = repository_root()
BASE_GAME = Path(r"Z:\SteamLibrary\steamapps\common\Hearts of Iron IV")
VANILLA_DIR = BASE_GAME / "interface/international_market"
SOURCE = ROOT / "gfx/interface/production/source/production_surface_source.png"
OUTPUT_DIR = ROOT / "gfx/interface/international_market/adiscord"
GFX_OUTPUT = ROOT / "interface/ADISCORD_market_ui.gfx"
PREVIEW = OUTPUT_DIR / "preview.png"
GUI_FILES = (
    "countryinternationalmarketview.gui", "marketaccessoverviewwindow.gui",
    "marketpurchasableequipmentwindow.gui", "marketpurchasedraftwindow.gui",
    "marketequipmentstockpilewindow.gui", "addequipmenttomarketwindow.gui",
    "edit_market_stockpile_window.gui", "requestautomationoptionswindow.gui",
    "pricelevelswidgets.gui", "markettutorialhint.gui",
)

# Icons, flags, price-state controls and progressbars remain engine-owned.
# Every surface below retains its native size, alpha silhouette and frame count.
SURFACES = {
    "GFX_tiled_bg": "content",
    "GFX_tiled_window2_1b_border": "window",
    "GFX_tiled_window_1b_border": "panel",
    "GFX_tiled_window_1b_thin_border": "thin_panel",
    "GFX_tiled_window_w_close": "dialog",
    "GFX_tiled_generic_overlay_bg1_small": "overlay",
    "GFX_tiled_plain_bg": "plain",
    "GFX_tiled_decisions_bg_small": "options",
    "GFX_generic_background": "generic",
    "GFX_tab_diplomacy_bg": "tabs_backing",
    "GFX_main_screens_bottom": "footer",
    "GFX_deployment_binding": "summary",
    "GFX_market_ui": "armory",
    "GFX_Access_&_buy_equipment": "buy_tab",
    "GFX_Add_equipment_to_markete": "sell_tab",
    "GFX_land_equipment_market_entry": "land_offer",
    "GFX_naval_equipment_market_entry": "naval_offer",
    "GFX_equipment_on_market": "stockpile",
    "GFX_diplo_filter_entry": "contract_filter",
    "GFX_government_button": "command",
    "GFX_button_123x34": "button_123",
    "GFX_button_221x34": "button_221",
    "GFX_button_94x31": "button_94",
    "GFX_generic_text_bg_60": "amount_60",
    "GFX_generic_text_bg_88": "amount_88",
    "GFX_mini_bg": "counter",
    "GFX_diplo_action_lend_lease_bg": "purchase_summary",
    "GFX_diplo_response_bg": "response",
    "GFX_lend_lease_equip_header": "equipment_header",
    "GFX_lendlease_big_bg": "equipment_large",
    "GFX_lendlease_small_bg": "equipment_small",
    "GFX_equipment_upgrade_designer_bg": "equipment_detail",
    "GFX_idea_entry_bg_3": "access_row",
    "GFX_hint_bg": "hint",
}
ENGINE_SURFACES = {
    "GFX_land_equipment_market_entry", "GFX_naval_equipment_market_entry",
    "GFX_equipment_on_market",
}


def render_gui(name: str) -> str:
    text = (VANILLA_DIR / name).read_text(encoding="utf-8-sig")
    for native, role in SURFACES.items():
        text = text.replace(f'"{native}"', f'"GFX_ADISCORD_market_{role}"')
    if name == "marketequipmentstockpilewindow.gui":
        text = replace_gui_block(text, "buttonType", "add_to_market_button", (
            (r'font\s*=\s*"hoi_18mbs"', 'font = "hoi_16mbs"'),
        ))
    elif name == "pricelevelswidgets.gui":
        text = replace_gui_block(text, "instantTextboxType", "price_label", (
            (r'maxWidth\s*=\s*100', 'maxWidth = 150'),
            (r'font\s*=\s*"hoi_18mbs"', 'font = "hoi_16mbs"'),
        ))
    elif name == "marketpurchasedraftwindow.gui":
        # Keep the long model name, stock count and convoy cost in separate
        # columns. The native name field extends through both amount controls.
        for widget, old_width, width in (
            ("name", 308, 170), ("stockpile_amount", 100, 50), ("cic_cost", 160, 50),
        ):
            text = replace_gui_block(text, "instantTextboxType", widget, (
                (rf'maxWidth\s*=\s*{old_width}', f'maxWidth = {width}'),
            ))
        for widget, old_x, x, width in (
            ("equipment_header", 10, 10, 160),
            ("value_header", 150, 188, 82),
            ("applied_header", 220, 273, 84),
        ):
            text = replace_gui_block(text, "instantTextboxType", widget, (
                (rf'position\s*=\s*\{{\s*x={old_x}\s+y=47\s*\}}',
                 f'position = {{ x={x} y=47 }}'),
                (r'maxWidth\s*=\s*160', f'maxWidth = {width}'),
                (r'font\s*=\s*"hoi_18mbs"', 'font = "hoi_16mbs"'),
            ))
        # The applied amount follows its header; both stay inside the row.
        text = replace_gui_block(text, "containerWindowType", "subsidies_draft_item", (
            (r'position\s*=\s*\{\s*x=290\s+y=49\s*\}',
             'position = { x=303 y=49 }'),
            (r'position\s*=\s*\{\s*x=260\s+y=40\s*\}',
             'position = { x=273 y=40 }'),
        ))
    return "\n".join(line.rstrip() for line in text.splitlines()) + "\n"


def render_surface(
    native: Image.Image, block: str, metal: Image.Image,
    role: str, market_art: Image.Image,
) -> Image.Image:
    palette = PALETTES["logistics"]
    if role == "armory":
        output = metal_surface(metal, native.size, palette, 0.94)
        art = _fit_glyph(market_art, (300, native.height - 6))
        output.alpha_composite(art, (55, 3))
        draw = ImageDraw.Draw(output)
        draw.line((8, 2, native.width - 9, 2), fill=palette.edge_light)
        draw.line((8, native.height - 3, native.width - 9, native.height - 3), fill=palette.accent)
        output.putalpha(native.getchannel("A"))
        return output
    frames_match = re.search(r'\bnoOfFrames\s*=\s*(\d+)', block, re.IGNORECASE)
    frames = int(frames_match[1]) if frames_match else 1
    if native.width % frames:
        raise ValueError(f"{role}: atlas width is not divisible by frame count")
    frame_width = native.width // frames
    output = Image.new("RGBA", native.size)
    for index in range(frames):
        original = native.crop((index * frame_width, 0, (index + 1) * frame_width, native.height))
        # Preserve actual recesses, controls and armory art rather than painting
        # arbitrary rectangles over the coordinates used by the live widgets.
        structure = ImageOps.colorize(
            ImageOps.grayscale(original), black=(10, 13, 14), white=(159, 165, 159),
        ).convert("RGBA")
        surface = metal_surface(metal, original.size, palette, 0.94)
        output_frame = Image.blend(structure, surface, 0.28)
        if frames > 1:
            accent = palette.edge if index == 0 else palette.accent_light
            ImageDraw.Draw(output_frame).line(
                (7, native.height - 5, frame_width - 8, native.height - 5),
                fill=accent, width=2,
            )
        output_frame.putalpha(original.getchannel("A"))
        output.alpha_composite(output_frame, (index * frame_width, 0))
    return output


def expected_outputs() -> dict[Path, bytes]:
    metal = load_surface_source(SOURCE)
    market_art = _international_market_source_icon()
    outputs = {
        ROOT / "interface/international_market" / name: render_gui(name).encode("utf-8")
        for name in GUI_FILES
    }
    entries = []
    previews = []
    for name, block in native_sprite_blocks(BASE_GAME, set(SURFACES)).items():
        match = re.search(r'\btexturefile\s*=\s*"([^"]+)"', block, re.IGNORECASE)
        if match is None:
            raise ValueError(f"{name}: missing texture")
        texture = BASE_GAME / match[1]
        if not texture.is_file():
            texture = texture.with_suffix(".dds")
        with Image.open(texture) as source:
            native = source.convert("RGBA")
        role = SURFACES[name]
        rendered = render_surface(native, block, metal, role, market_art)
        filename = f"ADISCORD_market_{role}.dds"
        data = dds_bytes(rendered)
        outputs[OUTPUT_DIR / filename] = data
        if name in ENGINE_SURFACES:
            outputs[ROOT / match[1]] = data
        block = block.replace(f'"{name}"', f'"GFX_ADISCORD_market_{role}"')
        block = block.replace(match[0], f'textureFile = "gfx/interface/international_market/adiscord/{filename}"')
        entries.append(block)
        if role in {"buy_tab", "sell_tab", "land_offer", "stockpile", "armory", "command"}:
            previews.append((role, rendered))
    outputs[GFX_OUTPUT] = ("# Generated by build_adiscord_market_ui_assets.py\nspriteTypes = {\n" + "\n".join(entries) + "\n}\n").encode("utf-8")
    stream = BytesIO()
    contact_sheet(previews, 640).save(stream, "PNG")
    outputs[PREVIEW] = stream.getvalue()
    return outputs


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--check", action="store_true")
    modes.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    return apply_or_check(expected_outputs(), args.apply, "Arms market UI")


if __name__ == "__main__":
    raise SystemExit(main())
