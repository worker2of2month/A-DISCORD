#!/usr/bin/env python3
"""Build the A-Discord division-deployment surface set."""

from __future__ import annotations

import argparse
from pathlib import Path

from tools.lib.adiscord_ui_surfaces import (
    PALETTES,
    apply_or_check,
    dds_bytes,
    framed_panel,
    load_surface_source,
    replace_counted,
)
from tools.lib.paths import repository_root


ROOT = repository_root()
BASE_GAME = Path(r"Z:\SteamLibrary\steamapps\common\Hearts of Iron IV")
VANILLA_GUI = BASE_GAME / "interface/countrydeploymentview.gui"
SOURCE = ROOT / "gfx/interface/production/source/production_surface_source.png"
OUTPUT_DIR = ROOT / "gfx/interface/deployment/ui"
GUI_OUTPUT = ROOT / "interface/countrydeploymentview.gui"
GFX_OUTPUT = ROOT / "interface/ADISCORD_deployment_ui.gfx"

WINDOW = OUTPUT_DIR / "ADISCORD_deployment_window.dds"
PANEL = OUTPUT_DIR / "ADISCORD_deployment_panel.dds"
TEMPLATE = OUTPUT_DIR / "ADISCORD_deployment_template.dds"
LINE = OUTPUT_DIR / "ADISCORD_deployment_line.dds"

SPRITE_REPLACEMENTS = {
    "GFX_tiled_window2_1b_border": ("GFX_ADISCORD_deployment_window", 1),
    "GFX_tiled_window": ("GFX_ADISCORD_deployment_panel", 1),
    "GFX_tiled_window_1b_thin_border": ("GFX_ADISCORD_deployment_panel", 4),
    "GFX_tiled_generic_overlay_bg1": ("GFX_ADISCORD_deployment_panel", 1),
    "GFX_tiled_plain_bg_small": ("GFX_ADISCORD_deployment_panel", 1),
    "GFX_tiled_window_transparent": ("GFX_ADISCORD_deployment_panel", 1),
    "GFX_subview_header_bg_375x101": ("GFX_ADISCORD_deployment_panel", 1),
    "GFX_deployment_named_division_bg": ("GFX_ADISCORD_deployment_template", 1),
    "GFX_deployment_named_division_obsolete_bg": ("GFX_ADISCORD_deployment_template", 1),
    "GFX_deploy_reinforcements_entry": ("GFX_ADISCORD_deployment_line", 2),
    "GFX_military_deployment_conveyor_view_bg": ("GFX_ADISCORD_deployment_line", 1),
    "GFX_military_deployment_end_line_view_bg": ("GFX_ADISCORD_deployment_line", 1),
    "GFX_military_deployment_line_view_bg": ("GFX_ADISCORD_deployment_line", 1),
    "GFX_deploy_priority_title_bg": ("GFX_ADISCORD_deployment_panel", 2),
    "GFX_deploy_priority_equipment_meter_bg": ("GFX_ADISCORD_deployment_panel", 2),
    "GFX_deploy_icon_tiled_bg": ("GFX_ADISCORD_deployment_panel", 2),
}


def render_gui() -> str:
    if not VANILLA_GUI.is_file():
        raise RuntimeError(f"missing vanilla deployment GUI: {VANILLA_GUI}")
    text = VANILLA_GUI.read_text(encoding="utf-8-sig")
    for old, (new, expected) in SPRITE_REPLACEMENTS.items():
        text = replace_counted(text, old, new, expected)
    return "\n".join(line.rstrip() for line in text.splitlines()) + "\n"


def _cornered(name: str, filename: str, size: tuple[int, int], border: int) -> str:
    return f"""    corneredTileSpriteType = {{
        name = "{name}"
        size = {{ x = {size[0]} y = {size[1]} }}
        textureFile = "gfx/interface/deployment/ui/{filename}"
        borderSize = {{ x = {border} y = {border} }}
        tilingCenter = yes
    }}
"""


def render_gfx() -> str:
    entries = (
        _cornered("GFX_ADISCORD_deployment_window", WINDOW.name, (192, 192), 32)
        + _cornered("GFX_ADISCORD_deployment_panel", PANEL.name, (192, 192), 24)
        + _cornered("GFX_ADISCORD_deployment_template", TEMPLATE.name, (512, 64), 12)
        + _cornered("GFX_ADISCORD_deployment_line", LINE.name, (512, 96), 14)
    )
    return f"spriteTypes = {{\n{entries}}}\n"


def expected_outputs() -> dict[Path, bytes]:
    source = load_surface_source(SOURCE)
    palette = PALETTES["deployment"]
    return {
        GUI_OUTPUT: render_gui().encode("utf-8"),
        GFX_OUTPUT: render_gfx().encode("utf-8"),
        WINDOW: dds_bytes(framed_panel(source, (192, 192), palette, 0.77)),
        PANEL: dds_bytes(framed_panel(source, (192, 192), palette, 0.67)),
        TEMPLATE: dds_bytes(framed_panel(source, (512, 64), palette, 0.75)),
        LINE: dds_bytes(framed_panel(source, (512, 96), palette, 0.72)),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build A-Discord deployment UI assets.")
    actions = parser.add_mutually_exclusive_group()
    actions.add_argument("--check", action="store_true")
    actions.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    return apply_or_check(expected_outputs(), args.apply, "Deployment UI")


if __name__ == "__main__":
    raise SystemExit(main())
