#!/usr/bin/env python3
"""Build the semantic A-Discord division-deployment surface set."""

from __future__ import annotations

import argparse
from io import BytesIO
from pathlib import Path

from PIL import Image

from tools.lib.adiscord_ui_contracts import (
    SpriteContract,
    contact_sheet,
    render_gfx_entry,
    validate_contract_image,
)
from tools.lib.adiscord_ui_surfaces import (
    PALETTES,
    apply_or_check,
    dds_bytes,
    framed_panel,
    load_surface_source,
    metal_surface,
    partial_rails,
    raised_field,
    recessed_well,
    replace_counted,
    status_band,
)
from tools.lib.paths import repository_root


ROOT = repository_root()
BASE_GAME = Path(r"Z:\SteamLibrary\steamapps\common\Hearts of Iron IV")
VANILLA_GUI = BASE_GAME / "interface/countrydeploymentview.gui"
SOURCE = ROOT / "gfx/interface/production/source/production_surface_source.png"
OUTPUT_DIR = ROOT / "gfx/interface/deployment/ui"
PREVIEW = ROOT / "gfx/interface/deployment/preview/ADISCORD_deployment_preview.png"
GUI_OUTPUT = ROOT / "interface/countrydeploymentview.gui"
GFX_OUTPUT = ROOT / "interface/ADISCORD_deployment_ui.gfx"

EFFECT = "gfx/FX/buttonstate_nodowneffect.lua"
OLIVE = (101, 124, 63, 255)
RUST = (150, 83, 50, 255)
SUPPLY_STEEL = (81, 111, 124, 255)
VIOLET = (112, 82, 136, 255)


DEPLOYMENT_CONTRACTS = (
    SpriteContract("GFX_tiled_window2_1b_border", "GFX_ADISCORD_deployment_window", "ADISCORD_deployment_window.dds", "corneredTileSpriteType", (192, 192), border_size=(64, 64), effect_file=EFFECT, tiling_center=True),
    SpriteContract("GFX_tiled_window", "GFX_ADISCORD_deployment_shell", "ADISCORD_deployment_shell.dds", "corneredTileSpriteType", (192, 192), border_size=(64, 64), effect_file=EFFECT, tiling_center=True),
    SpriteContract("GFX_tiled_window_1b_thin_border", "GFX_ADISCORD_deployment_thin_shell", "ADISCORD_deployment_thin_shell.dds", "corneredTileSpriteType", (192, 192), border_size=(64, 64), effect_file=EFFECT, tiling_center=True),
    SpriteContract("GFX_tiled_generic_overlay_bg1", "GFX_ADISCORD_deployment_overlay", "ADISCORD_deployment_overlay.dds", "corneredTileSpriteType", (549, 600), border_size=(268, 268), effect_file=EFFECT, always_transparent=True, tiling_center=True),
    SpriteContract("GFX_tiled_plain_bg_small", "GFX_ADISCORD_deployment_small_panel", "ADISCORD_deployment_small_panel.dds", "corneredTileSpriteType", (48, 48), border_size=(16, 16), effect_file=EFFECT, tiling_center=True),
    SpriteContract("GFX_tiled_window_transparent", "GFX_ADISCORD_deployment_transparent", "ADISCORD_deployment_transparent.dds", "corneredTileSpriteType", (3, 3), border_size=(1, 1), effect_file=EFFECT),
    SpriteContract("GFX_subview_header_bg_375x101", "GFX_ADISCORD_deployment_header", "ADISCORD_deployment_header.dds", "spriteType", (375, 101)),
    SpriteContract("GFX_deploy_icon_tiled_bg", "GFX_ADISCORD_deployment_icon_well", "ADISCORD_deployment_icon_well.dds", "corneredTileSpriteType", (77, 40), border_size=(16, 16), always_transparent=True),
    SpriteContract("GFX_deploy_reinforcements_entry", "GFX_ADISCORD_deployment_reinforcement_row", "ADISCORD_deployment_reinforcement_row.dds", "spriteType", (493, 57), effect_file=EFFECT),
    SpriteContract("GFX_deploy_reinforcements_entry", "GFX_ADISCORD_deployment_supply_row", "ADISCORD_deployment_supply_row.dds", "spriteType", (493, 57), effect_file=EFFECT),
    SpriteContract("GFX_deploy_upgrades_entry", "GFX_ADISCORD_deployment_upgrade_row", "ADISCORD_deployment_upgrade_row.dds", "spriteType", (493, 57), effect_file=EFFECT),
    SpriteContract("GFX_deploy_garrisons_entry", "GFX_ADISCORD_deployment_garrison_row", "ADISCORD_deployment_garrison_row.dds", "spriteType", (493, 57), effect_file=EFFECT),
    SpriteContract("GFX_deploy_operations_entry", "GFX_ADISCORD_deployment_operations_row", "ADISCORD_deployment_operations_row.dds", "spriteType", (493, 57), effect_file=EFFECT),
    SpriteContract("GFX_deployment_named_division_bg", "GFX_ADISCORD_deployment_template", "ADISCORD_deployment_template.dds", "spriteType", (346, 78), effect_file=EFFECT),
    SpriteContract("GFX_deployment_named_division_obsolete_bg", "GFX_ADISCORD_deployment_template_obsolete", "ADISCORD_deployment_template_obsolete.dds", "spriteType", (348, 79), effect_file=EFFECT),
    SpriteContract("GFX_military_deployment_conveyor_view_bg", "GFX_ADISCORD_deployment_conveyor", "ADISCORD_deployment_conveyor.dds", "spriteType", (490, 84), effect_file=EFFECT),
    SpriteContract("GFX_military_deployment_line_view_bg", "GFX_ADISCORD_deployment_line", "ADISCORD_deployment_line.dds", "spriteType", (514, 40), effect_file=EFFECT),
    SpriteContract("GFX_military_deployment_end_line_view_bg", "GFX_ADISCORD_deployment_end_line", "ADISCORD_deployment_end_line.dds", "spriteType", (518, 40), effect_file=EFFECT),
    SpriteContract("GFX_deploy_priority_title_bg", "GFX_ADISCORD_deployment_priority_title", "ADISCORD_deployment_priority_title.dds", "spriteType", (159, 26)),
    SpriteContract("GFX_deploy_priority_equipment_meter_bg", "GFX_ADISCORD_deployment_priority_meter", "ADISCORD_deployment_priority_meter.dds", "spriteType", (108, 33)),
)

SPRITE_REPLACEMENTS = {
    "GFX_tiled_window2_1b_border": ("GFX_ADISCORD_deployment_window", 1),
    "GFX_tiled_window": ("GFX_ADISCORD_deployment_shell", 1),
    "GFX_tiled_window_1b_thin_border": ("GFX_ADISCORD_deployment_thin_shell", 4),
    "GFX_tiled_generic_overlay_bg1": ("GFX_ADISCORD_deployment_overlay", 1),
    "GFX_tiled_plain_bg_small": ("GFX_ADISCORD_deployment_small_panel", 1),
    "GFX_tiled_window_transparent": ("GFX_ADISCORD_deployment_transparent", 1),
    "GFX_subview_header_bg_375x101": ("GFX_ADISCORD_deployment_header", 1),
    "GFX_deployment_named_division_bg": ("GFX_ADISCORD_deployment_template", 1),
    "GFX_deployment_named_division_obsolete_bg": ("GFX_ADISCORD_deployment_template_obsolete", 1),
    "GFX_military_deployment_conveyor_view_bg": ("GFX_ADISCORD_deployment_conveyor", 1),
    "GFX_military_deployment_line_view_bg": ("GFX_ADISCORD_deployment_line", 1),
    "GFX_military_deployment_end_line_view_bg": ("GFX_ADISCORD_deployment_end_line", 1),
    "GFX_deploy_priority_title_bg": ("GFX_ADISCORD_deployment_priority_title", 2),
    "GFX_deploy_priority_equipment_meter_bg": ("GFX_ADISCORD_deployment_priority_meter", 2),
    "GFX_deploy_icon_tiled_bg": ("GFX_ADISCORD_deployment_icon_well", 2),
}


def _container_block(text: str, name: str) -> tuple[int, int]:
    anchor = f'name = "{name}"'
    name_offset = text.find(anchor)
    if name_offset < 0:
        raise ValueError(f"missing deployment container: {name}")
    start = text.rfind("containerWindowType", 0, name_offset)
    opening = text.find("{", start, name_offset)
    depth = 0
    for offset in range(opening, len(text)):
        if text[offset] == "{":
            depth += 1
        elif text[offset] == "}":
            depth -= 1
            if depth == 0:
                return start, offset + 1
    raise ValueError(f"unclosed deployment container: {name}")


def _replace_container_sprite(text: str, container: str, old: str, new: str) -> str:
    start, end = _container_block(text, container)
    block = replace_counted(text[start:end], old, new, 1)
    return text[:start] + block + text[end:]


def render_gui() -> str:
    if not VANILLA_GUI.is_file():
        raise RuntimeError(f"missing vanilla deployment GUI: {VANILLA_GUI}")
    text = VANILLA_GUI.read_text(encoding="utf-8-sig")
    for old, (new, expected) in SPRITE_REPLACEMENTS.items():
        text = replace_counted(text, old, new, expected)
    text = _replace_container_sprite(text, "deploy_entry", "GFX_deploy_reinforcements_entry", "GFX_ADISCORD_deployment_reinforcement_row")
    text = _replace_container_sprite(text, "supply_deploy_entry", "GFX_deploy_reinforcements_entry", "GFX_ADISCORD_deployment_supply_row")
    manifest = "\n".join(
        f'# semantic deployment asset: "{item.target_name}"'
        for item in DEPLOYMENT_CONTRACTS
    )
    return manifest + "\n" + "\n".join(line.rstrip() for line in text.splitlines()) + "\n"


def _priority_row(source: Image.Image, accent: tuple[int, int, int, int]) -> Image.Image:
    palette = PALETTES["deployment"]
    output = metal_surface(source, (493, 57), palette, 0.78)
    status_band(output, (0, 0, 492, 3), accent)
    recessed_well(output, (5, 7, 102, 50), palette)
    partial_rails(output, (106, 9, 309, 47), palette)
    raised_field(output, (313, 7, 487, 50), palette)
    return output


def _template_row(source: Image.Image, size: tuple[int, int], obsolete: bool) -> Image.Image:
    palette = PALETTES["deployment"]
    width, height = size
    output = metal_surface(source, size, palette, 0.68 if obsolete else 0.82)
    recessed_well(output, (8, 8, 74, height - 9), palette)
    raised_field(output, (83, 9, width - 77, height - 10), palette)
    recessed_well(output, (width - 68, 9, width - 9, height - 10), palette)
    status_band(output, (83, height - 7, width - 77, height - 4), RUST if obsolete else OLIVE)
    return output


def _conveyor_row(source: Image.Image) -> Image.Image:
    palette = PALETTES["deployment"]
    output = metal_surface(source, (490, 84), palette, 0.80)
    recessed_well(output, (7, 10, 86, 74), palette)
    raised_field(output, (96, 12, 302, 41), palette)
    recessed_well(output, (96, 47, 302, 76), palette)
    raised_field(output, (312, 9, 410, 43), palette)
    recessed_well(output, (420, 12, 481, 75), palette)
    partial_rails(output, (96, 4, 481, 80), palette)
    return output


def _line_row(source: Image.Image, size: tuple[int, int], end_line: bool) -> Image.Image:
    palette = PALETTES["deployment"]
    width, height = size
    output = metal_surface(source, size, palette, 0.75)
    partial_rails(output, (5, 4, width - 6, height - 5), palette)
    raised_field(output, (8, 7, 177 if not end_line else 196, height - 8), palette)
    recessed_well(output, (width - 90, 7, width - 9, height - 8), palette)
    status_band(output, (0, height - 3, width - 1, height - 1), RUST if end_line else OLIVE)
    return output


def _priority_title(source: Image.Image) -> Image.Image:
    palette = PALETTES["deployment"]
    output = metal_surface(source, (159, 26), palette, 0.84)
    raised_field(output, (1, 2, 157, 23), palette)
    return output


def _priority_meter(source: Image.Image) -> Image.Image:
    palette = PALETTES["deployment"]
    output = metal_surface(source, (108, 33), palette, 0.80)
    recessed_well(output, (2, 4, 105, 28), palette)
    status_band(output, (4, 25, 103, 27), OLIVE)
    return output


def render_asset(contract: SpriteContract, source: Image.Image) -> Image.Image:
    target = contract.target_name
    if target == "GFX_ADISCORD_deployment_reinforcement_row":
        return _priority_row(source, OLIVE)
    if target == "GFX_ADISCORD_deployment_supply_row":
        return _priority_row(source, SUPPLY_STEEL)
    if target == "GFX_ADISCORD_deployment_upgrade_row":
        return _priority_row(source, RUST)
    if target == "GFX_ADISCORD_deployment_garrison_row":
        return _priority_row(source, SUPPLY_STEEL)
    if target == "GFX_ADISCORD_deployment_operations_row":
        return _priority_row(source, VIOLET)
    if target == "GFX_ADISCORD_deployment_template":
        return _template_row(source, contract.total_size, obsolete=False)
    if target == "GFX_ADISCORD_deployment_template_obsolete":
        return _template_row(source, contract.total_size, obsolete=True)
    if target == "GFX_ADISCORD_deployment_conveyor":
        return _conveyor_row(source)
    if target == "GFX_ADISCORD_deployment_line":
        return _line_row(source, contract.total_size, end_line=False)
    if target == "GFX_ADISCORD_deployment_end_line":
        return _line_row(source, contract.total_size, end_line=True)
    if target == "GFX_ADISCORD_deployment_priority_title":
        return _priority_title(source)
    if target == "GFX_ADISCORD_deployment_priority_meter":
        return _priority_meter(source)
    if target == "GFX_ADISCORD_deployment_header":
        output = metal_surface(source, contract.total_size, PALETTES["deployment"], 0.78)
        partial_rails(output, (8, 8, 366, 92), PALETTES["deployment"])
        return output
    if target == "GFX_ADISCORD_deployment_icon_well":
        output = metal_surface(source, contract.total_size, PALETTES["deployment"], 0.72)
        recessed_well(output, (2, 2, 74, 37), PALETTES["deployment"])
        return output
    if target == "GFX_ADISCORD_deployment_transparent":
        return Image.new("RGBA", contract.total_size, (0, 0, 0, 0))
    return framed_panel(source, contract.total_size, PALETTES["deployment"], 0.74)


def render_gfx() -> str:
    entries = "".join(render_gfx_entry(item, f"gfx/interface/deployment/ui/{item.filename}") for item in DEPLOYMENT_CONTRACTS)
    return f"spriteTypes = {{\n{entries}}}\n"


def _png_bytes(image: Image.Image) -> bytes:
    stream = BytesIO()
    image.save(stream, format="PNG", optimize=False, compress_level=9)
    return stream.getvalue()


def expected_outputs() -> dict[Path, bytes]:
    source = load_surface_source(SOURCE)
    assets: list[tuple[SpriteContract, Image.Image]] = []
    for contract in DEPLOYMENT_CONTRACTS:
        image = render_asset(contract, source)
        validate_contract_image(contract, image)
        assets.append((contract, image))
    outputs = {
        GUI_OUTPUT: render_gui().encode("utf-8"),
        GFX_OUTPUT: render_gfx().encode("utf-8"),
        PREVIEW: _png_bytes(contact_sheet([(item.target_name, image) for item, image in assets], 640)),
    }
    outputs.update({OUTPUT_DIR / item.filename: dds_bytes(image) for item, image in assets})
    return outputs


def main() -> int:
    parser = argparse.ArgumentParser(description="Build A-Discord deployment UI assets.")
    actions = parser.add_mutually_exclusive_group()
    actions.add_argument("--check", action="store_true")
    actions.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    return apply_or_check(expected_outputs(), args.apply, "Deployment UI")


if __name__ == "__main__":
    raise SystemExit(main())
