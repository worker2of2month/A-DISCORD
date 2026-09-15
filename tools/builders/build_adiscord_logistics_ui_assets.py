#!/usr/bin/env python3
"""Build the A-Discord logistics-window surface set."""

from __future__ import annotations

import argparse
from pathlib import Path
import re

from PIL import Image, ImageDraw

from tools.lib.adiscord_ui_contracts import native_sprite_blocks, replace_gui_block

from tools.lib.adiscord_ui_surfaces import (
    PALETTES,
    apply_or_check,
    dds_bytes,
    framed_panel,
    load_surface_source,
    metal_surface,
    partial_rails,
    replace_counted,
)
from tools.lib.paths import repository_root


ROOT = repository_root()
BASE_GAME = Path(r"Z:\SteamLibrary\steamapps\common\Hearts of Iron IV")
VANILLA_GUI = BASE_GAME / "interface/countrylogisticsview.gui"
SOURCE = ROOT / "gfx/interface/production/source/production_surface_source.png"
OUTPUT_DIR = ROOT / "gfx/interface/logistics/ui"
GUI_OUTPUT = ROOT / "interface/countrylogisticsview.gui"
GFX_OUTPUT = ROOT / "interface/ADISCORD_logistics_ui.gfx"

WINDOW = OUTPUT_DIR / "ADISCORD_logistics_window.dds"
PANEL = OUTPUT_DIR / "ADISCORD_logistics_panel.dds"
ROW = OUTPUT_DIR / "ADISCORD_logistics_row.dds"
GRAPH = OUTPUT_DIR / "ADISCORD_logistics_graph.dds"

SPRITE_REPLACEMENTS = {
    "GFX_tiled_window2_1b_border": ("GFX_ADISCORD_logistics_window", 3),
    "GFX_tiled_window_1b_border": ("GFX_ADISCORD_logistics_panel", 3),
    "GFX_tiled_generic_overlay_bg1": ("GFX_ADISCORD_logistics_panel", 1),
    "GFX_tiled_plain_bg": ("GFX_ADISCORD_logistics_panel", 2),
    "GFX_trade_filter_bg": ("GFX_ADISCORD_logistics_panel", 2),
    "GFX_logistics_entry_bg": ("GFX_ADISCORD_logistics_row", 2),
    "GFX_logistics_equipment_entry_bg": ("GFX_ADISCORD_logistics_row", 1),
    "GFX_logistics_air_equipment_entry_bg": ("GFX_ADISCORD_logistics_row", 1),
    "GFX_logistics_naval_equipment_entry_bg": ("GFX_ADISCORD_logistics_row", 1),
    "GFX_logistics_other_entry_bg": ("GFX_ADISCORD_logistics_row", 1),
    "GFX_logistics_info_equip_variant_entry": ("GFX_ADISCORD_logistics_row", 1),
    "GFX_fuel_logisctics_graph_entry_bg": ("GFX_ADISCORD_logistics_row", 1),
    "GFX_unit_list_header": ("GFX_ADISCORD_logistics_row", 3),
    "GFX_strategicair_details_linechart_bg": ("GFX_ADISCORD_logistics_graph", 2),
}

# Fixed native rows must keep their own dimensions; a resizable 256x64 tile
# stretches them to the GUI container and draws borders outside the window.
FIXED_ROWS = {
    "GFX_logistics_entry_bg": "entry",
    "GFX_logistics_equipment_entry_bg": "equipment",
    "GFX_logistics_air_equipment_entry_bg": "air_equipment",
    "GFX_logistics_naval_equipment_entry_bg": "naval_equipment",
    "GFX_logistics_other_entry_bg": "other",
    "GFX_logistics_info_equip_variant_entry": "variant",
    "GFX_fuel_logisctics_graph_entry_bg": "fuel",
    "GFX_unit_list_header": "header",
}


def render_gui() -> str:
    if not VANILLA_GUI.is_file():
        raise RuntimeError(f"missing vanilla logistics GUI: {VANILLA_GUI}")
    text = VANILLA_GUI.read_text(encoding="utf-8-sig")
    for old, (new, expected) in SPRITE_REPLACEMENTS.items():
        if old in FIXED_ROWS:
            new = f"GFX_ADISCORD_logistics_{FIXED_ROWS[old]}_row"
        text = replace_counted(text, old, new, expected)
    text = replace_gui_block(text, "instantTextboxType", "equipment_type", (
        (r'maxWidth\s*=\s*115', 'maxWidth = 170'),
        (r'position\s*=\s*\{[^}]+\}', 'position = { x = 37 y = 2 }'),
    ), expected=3)
    return "\n".join(line.rstrip() for line in text.splitlines()) + "\n"


def _cornered(name: str, filename: str, size: tuple[int, int], border: int) -> str:
    return f"""    corneredTileSpriteType = {{
        name = "{name}"
        size = {{ x = {size[0]} y = {size[1]} }}
        textureFile = "gfx/interface/logistics/ui/{filename}"
        borderSize = {{ x = {border} y = {border} }}
        tilingCenter = yes
    }}
"""


def render_gfx() -> str:
    entries = (
        _cornered("GFX_ADISCORD_logistics_window", WINDOW.name, (192, 192), 32)
        + _cornered("GFX_ADISCORD_logistics_panel", PANEL.name, (192, 192), 24)
        + _cornered("GFX_ADISCORD_logistics_row", ROW.name, (256, 64), 12)
        + _cornered("GFX_ADISCORD_logistics_graph", GRAPH.name, (512, 256), 24)
    )
    return f"spriteTypes = {{\n{entries}}}\n"


def expected_outputs() -> dict[Path, bytes]:
    source = load_surface_source(SOURCE)
    palette = PALETTES["logistics"]
    outputs = {
        GUI_OUTPUT: render_gui().encode("utf-8"),
        GFX_OUTPUT: render_gfx().encode("utf-8"),
        WINDOW: dds_bytes(framed_panel(source, (192, 192), palette, 0.78)),
        PANEL: dds_bytes(framed_panel(source, (192, 192), palette, 0.68)),
        ROW: dds_bytes(framed_panel(source, (256, 64), palette, 0.76)),
        GRAPH: dds_bytes(framed_panel(source, (512, 256), palette, 0.62)),
    }
    entries = []
    for name, block in native_sprite_blocks(BASE_GAME, set(FIXED_ROWS)).items():
        match = re.search(r'\btexturefile\s*=\s*"([^"]+)"', block, re.IGNORECASE)
        if match is None:
            raise ValueError(f"{name}: missing texture")
        native = Image.open(BASE_GAME / match[1]).convert("RGBA")
        role = FIXED_ROWS[name]
        target = f"GFX_ADISCORD_logistics_{role}_row"
        filename = f"ADISCORD_logistics_{role}_row.dds"
        image = metal_surface(source, native.size, palette, 0.86)
        width, height = image.size
        partial_rails(image, (1, 1, width - 2, height - 2), palette)
        if role in {"equipment", "air_equipment", "naval_equipment"}:
            draw = ImageDraw.Draw(image)
            for x in (147, 205, 287, 342, 401):
                draw.line((x, 26, x, height - 7), fill=palette.edge)
        image.putalpha(native.getchannel("A"))
        outputs[OUTPUT_DIR / filename] = dds_bytes(image)
        block = block.replace(f'"{name}"', f'"{target}"')
        block = block.replace(match[0], f'textureFile = "gfx/interface/logistics/ui/{filename}"')
        entries.append(block)
    gfx = render_gfx().rstrip()
    outputs[GFX_OUTPUT] = (gfx[:-1] + "\n" + "\n".join(entries) + "\n}\n").encode("utf-8")
    return outputs


def main() -> int:
    parser = argparse.ArgumentParser(description="Build A-Discord logistics UI assets.")
    actions = parser.add_mutually_exclusive_group()
    actions.add_argument("--check", action="store_true")
    actions.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    return apply_or_check(expected_outputs(), args.apply, "Logistics UI")


if __name__ == "__main__":
    raise SystemExit(main())
