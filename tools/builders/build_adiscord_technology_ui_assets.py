#!/usr/bin/env python3
"""Build the A-Discord research-window surface set."""

from __future__ import annotations

import argparse
from pathlib import Path
import re

from PIL import Image

from tools.lib.adiscord_ui_surfaces import (
    PALETTES,
    apply_or_check,
    dds_bytes,
    framed_panel,
    load_surface_source,
    metal_surface,
    replace_counted,
)
from tools.lib.paths import repository_root


ROOT = repository_root()
BASE_GAME = Path(r"Z:\SteamLibrary\steamapps\common\Hearts of Iron IV")
VANILLA_GUI = BASE_GAME / "interface/countrytechnologyview.gui"
SOURCE = ROOT / "gfx/interface/production/source/production_surface_source.png"
OUTPUT_DIR = ROOT / "gfx/interface/technology/ui"
GUI_OUTPUT = ROOT / "interface/countrytechnologyview.gui"
GFX_OUTPUT = ROOT / "interface/ADISCORD_technology_ui.gfx"

WINDOW = OUTPUT_DIR / "ADISCORD_technology_window.dds"
PANEL = OUTPUT_DIR / "ADISCORD_technology_panel.dds"
SLOT = OUTPUT_DIR / "ADISCORD_technology_slot.dds"
CARD = OUTPUT_DIR / "ADISCORD_technology_card.dds"
TAB = OUTPUT_DIR / "ADISCORD_technology_tab.dds"
TOP = OUTPUT_DIR / "ADISCORD_technology_top.dds"
BOTTOM = OUTPUT_DIR / "ADISCORD_technology_bottom.dds"
TREE_PANEL = OUTPUT_DIR / "ADISCORD_technology_tree_panel.dds"
TREE_STRIPES = OUTPUT_DIR / "ADISCORD_technology_tree_stripes.dds"
TREE_INFO_TOP = OUTPUT_DIR / "ADISCORD_technology_tree_info_top.dds"
TREE_INFO = OUTPUT_DIR / "ADISCORD_technology_tree_info.dds"

SPRITE_REPLACEMENTS = {
    "GFX_tiled_window2_1b_border": ("GFX_ADISCORD_technology_window", 1),
    "GFX_tiled_plain_bg": ("GFX_ADISCORD_technology_panel", 1),
    "GFX_tiled_generic_overlay_bg1": ("GFX_ADISCORD_technology_panel", 1),
    "GFX_tiled_window_transparent": ("GFX_ADISCORD_technology_panel", 1),
    "GFX_tech_idea_bg": ("GFX_ADISCORD_technology_card", 1),
    "GFX_research_line_bg": ("GFX_ADISCORD_technology_slot", 1),
    "GFX_tab_large": ("GFX_ADISCORD_technology_tab", 2),
    "GFX_research_top_win": ("GFX_ADISCORD_technology_top", 1),
    "GFX_production_win_bottom": ("GFX_ADISCORD_technology_bottom", 1),
}

TREE_SPRITE_REPLACEMENTS = {
    "GFX_tiled_plain_bg2": ("GFX_ADISCORD_technology_tree_panel", 1),
    "GFX_tiled_window_2b_border": ("GFX_ADISCORD_technology_tree_panel", 12),
    "GFX_techtree_stripes": ("GFX_ADISCORD_technology_tree_stripes", 12),
    "GFX_tiled_paper_bg": ("GFX_ADISCORD_technology_tree_panel", 2),
    "GFX_tiled_window_thin_border2": ("GFX_ADISCORD_technology_tree_panel", 2),
    "GFX_tech_info_top_win": ("GFX_ADISCORD_technology_tree_info_top", 2),
    "GFX_technology_info_bg": ("GFX_ADISCORD_technology_tree_info", 2),
}


def _two_state_tab(source: Image.Image) -> Image.Image:
    palette = PALETTES["technology"]
    output = Image.new("RGBA", (516, 42), (0, 0, 0, 0))
    normal = framed_panel(source, (258, 42), palette, 0.70)
    selected = framed_panel(source, (258, 42), palette, 0.96)
    output.alpha_composite(normal, (0, 0))
    output.alpha_composite(selected, (258, 0))
    return output


def render_gui() -> str:
    if not VANILLA_GUI.is_file():
        raise RuntimeError(f"missing vanilla research GUI: {VANILLA_GUI}")
    text = VANILLA_GUI.read_text(encoding="utf-8-sig")
    for old, (new, expected) in SPRITE_REPLACEMENTS.items():
        text = replace_counted(text, old, new, expected)
    text = "\n".join(line.rstrip() for line in text.splitlines()) + "\n"
    return re.sub(r"(?m)^ +(?=\t)", "", text)


def render_gfx() -> str:
    return """spriteTypes = {
    corneredTileSpriteType = {
        name = "GFX_ADISCORD_technology_window"
        size = { x = 192 y = 192 }
        textureFile = "gfx/interface/technology/ui/ADISCORD_technology_window.dds"
        borderSize = { x = 32 y = 32 }
        tilingCenter = yes
    }
    corneredTileSpriteType = {
        name = "GFX_ADISCORD_technology_panel"
        size = { x = 192 y = 192 }
        textureFile = "gfx/interface/technology/ui/ADISCORD_technology_panel.dds"
        borderSize = { x = 24 y = 24 }
        tilingCenter = yes
    }
    spriteType = {
        name = "GFX_ADISCORD_technology_slot"
        textureFile = "gfx/interface/technology/ui/ADISCORD_technology_slot.dds"
    }
    spriteType = {
        name = "GFX_ADISCORD_technology_card"
        textureFile = "gfx/interface/technology/ui/ADISCORD_technology_card.dds"
    }
    spriteType = {
        name = "GFX_ADISCORD_technology_tab"
        textureFile = "gfx/interface/technology/ui/ADISCORD_technology_tab.dds"
        noOfFrames = 2
    }
    spriteType = {
        name = "GFX_ADISCORD_technology_top"
        textureFile = "gfx/interface/technology/ui/ADISCORD_technology_top.dds"
    }
    spriteType = {
        name = "GFX_ADISCORD_technology_bottom"
        textureFile = "gfx/interface/technology/ui/ADISCORD_technology_bottom.dds"
    }
}
"""


def apply_tree_skin(text: str) -> str:
    for old, (new, expected) in TREE_SPRITE_REPLACEMENTS.items():
        text = replace_counted(text, old, new, expected)
    return text


def technology_tree_gfx_entries() -> str:
    return """
    corneredTileSpriteType = {
        name = "GFX_ADISCORD_technology_tree_panel"
        size = { x = 192 y = 192 }
        textureFile = "gfx/interface/technology/ui/ADISCORD_technology_tree_panel.dds"
        borderSize = { x = 32 y = 32 }
        tilingCenter = yes
    }
    corneredTileSpriteType = {
        name = "GFX_ADISCORD_technology_tree_stripes"
        size = { x = 122 y = 244 }
        textureFile = "gfx/interface/technology/ui/ADISCORD_technology_tree_stripes.dds"
        borderSize = { x = 0 y = 0 }
        tilingCenter = yes
        alwaystransparent = yes
    }
    spriteType = {
        name = "GFX_ADISCORD_technology_tree_info_top"
        textureFile = "gfx/interface/technology/ui/ADISCORD_technology_tree_info_top.dds"
    }
    spriteType = {
        name = "GFX_ADISCORD_technology_tree_info"
        textureFile = "gfx/interface/technology/ui/ADISCORD_technology_tree_info.dds"
    }
"""


def expected_outputs() -> dict[Path, bytes]:
    source = load_surface_source(SOURCE)
    palette = PALETTES["technology"]
    return {
        GUI_OUTPUT: render_gui().encode("utf-8"),
        GFX_OUTPUT: render_gfx().encode("utf-8"),
        WINDOW: dds_bytes(framed_panel(source, (192, 192), palette, 0.80)),
        PANEL: dds_bytes(framed_panel(source, (192, 192), palette, 0.68)),
        SLOT: dds_bytes(framed_panel(source, (508, 99), palette, 0.76)),
        CARD: dds_bytes(framed_panel(source, (63, 63), palette, 0.82)),
        TAB: dds_bytes(_two_state_tab(source)),
        TOP: dds_bytes(metal_surface(source, (548, 138), palette, 0.78)),
        BOTTOM: dds_bytes(metal_surface(source, (546, 66), palette, 0.72)),
        TREE_PANEL: dds_bytes(framed_panel(source, (192, 192), palette, 0.70)),
        TREE_STRIPES: dds_bytes(metal_surface(source, (122, 244), palette, 0.62)),
        TREE_INFO_TOP: dds_bytes(framed_panel(source, (548, 220), palette, 0.78)),
        TREE_INFO: dds_bytes(framed_panel(source, (508, 517), palette, 0.68)),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build A-Discord technology UI assets.")
    actions = parser.add_mutually_exclusive_group()
    actions.add_argument("--check", action="store_true")
    actions.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    return apply_or_check(
        expected_outputs(),
        apply=args.apply,
        label="Technology UI",
    )


if __name__ == "__main__":
    raise SystemExit(main())
