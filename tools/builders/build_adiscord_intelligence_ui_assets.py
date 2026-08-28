#!/usr/bin/env python3
"""Build the semantic A-Discord intelligence-agency and operative surface set."""

from __future__ import annotations

import argparse
import hashlib
from io import BytesIO
from pathlib import Path
import re

from PIL import Image, ImageDraw, ImageEnhance, ImageOps

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
    outer_frame,
    partial_rails,
    raised_field,
    recessed_well,
    replace_counted,
    status_band,
)
from tools.lib.paths import repository_root


ROOT = repository_root()
BASE_GAME = Path(r"Z:\SteamLibrary\steamapps\common\Hearts of Iron IV")
BASE_INTERFACE = BASE_GAME / "interface"
METAL_SOURCE = ROOT / "gfx/interface/production/source/production_surface_source.png"
HEADER_SOURCE = (
    ROOT
    / "gfx/interface/intelligence/source/ADISCORD_intelligence_header_source.png"
)
OUTPUT_DIR = ROOT / "gfx/interface/intelligence/ui"
PREVIEW = ROOT / "gfx/interface/intelligence/preview/ADISCORD_intelligence_preview.png"
GFX_OUTPUT = ROOT / "interface/ADISCORD_intelligence_ui.gfx"

EFFECT = "gfx/FX/buttonstate_nodowneffect.lua"
VIOLET = (104, 78, 128, 255)
VIOLET_LIGHT = (143, 111, 164, 255)
STEEL_BLUE = (67, 103, 133, 255)
WARM_COMPLETE = (148, 119, 71, 255)


INTELLIGENCE_CONTRACTS = (
    SpriteContract(
        "GFX_tiled_window_insigna",
        "GFX_ADISCORD_intelligence_window_shell",
        "ADISCORD_intelligence_window_shell.dds",
        "corneredTileSpriteType",
        (317, 444),
        border_size=(64, 222),
        effect_file=EFFECT,
    ),
    SpriteContract(
        "GFX_tiled_bg",
        "GFX_ADISCORD_intelligence_content_tile",
        "ADISCORD_intelligence_content_tile.dds",
        "corneredTileSpriteType",
        (192, 192),
        border_size=(64, 64),
        effect_file=EFFECT,
        tiling_center=True,
    ),
    SpriteContract(
        "GFX_tiled_paper_bg",
        "GFX_ADISCORD_intelligence_paper_tile",
        "ADISCORD_intelligence_paper_tile.dds",
        "corneredTileSpriteType",
        (192, 192),
        border_size=(64, 64),
        effect_file=EFFECT,
        tiling_center=True,
    ),
    SpriteContract(
        "GFX_tiled_window_transparent",
        "GFX_ADISCORD_intelligence_transparent_tile",
        "ADISCORD_intelligence_transparent_tile.dds",
        "corneredTileSpriteType",
        (3, 3),
        border_size=(1, 1),
        effect_file=EFFECT,
    ),
    SpriteContract(
        "GFX_agency_upgrade_cost_background",
        "GFX_ADISCORD_intelligence_cost_tile",
        "ADISCORD_intelligence_cost_tile.dds",
        "corneredTileSpriteType",
        (40, 50),
        border_size=(8, 8),
        always_transparent=True,
    ),
    SpriteContract(
        "GFX_intel_header_bg",
        "GFX_ADISCORD_intelligence_header",
        "ADISCORD_intelligence_header.dds",
        "spriteType",
        (519, 109),
    ),
    SpriteContract(
        "GFX_create_agency_bg",
        "GFX_ADISCORD_intelligence_create",
        "ADISCORD_intelligence_create.dds",
        "spriteType",
        (508, 99),
    ),
    SpriteContract(
        "GFX_agency_branch_upgrades_popup_bg",
        "GFX_ADISCORD_intelligence_branches_popup",
        "ADISCORD_intelligence_branches_popup.dds",
        "spriteType",
        (1092, 91),
        effect_file=EFFECT,
    ),
    SpriteContract(
        "GFX_agency_branch_upgrade_entry_bg",
        "GFX_ADISCORD_intelligence_branch_row",
        "ADISCORD_intelligence_branch_row.dds",
        "spriteType",
        (1040, 136),
        effect_file=EFFECT,
    ),
    SpriteContract(
        "GFX_operatives_bg",
        "GFX_ADISCORD_intelligence_operatives",
        "ADISCORD_intelligence_operatives.dds",
        "spriteType",
        (522, 76),
    ),
    SpriteContract(
        "GFX_operations_tab_large",
        "GFX_ADISCORD_intelligence_tabs",
        "ADISCORD_intelligence_tabs.dds",
        "spriteType",
        (524, 53),
        frames=2,
    ),
    SpriteContract(
        "GFX_operation_entry_bg",
        "GFX_ADISCORD_intelligence_operation_row",
        "ADISCORD_intelligence_operation_row.dds",
        "spriteType",
        (1038, 89),
        frames=2,
    ),
    SpriteContract(
        "GFX_cryptology_country_entry_bg",
        "GFX_ADISCORD_intelligence_crypto_row",
        "ADISCORD_intelligence_crypto_row.dds",
        "spriteType",
        (516, 87),
    ),
    SpriteContract(
        "GFX_cryptology_country_entry_selected_bg",
        "GFX_ADISCORD_intelligence_crypto_selected",
        "ADISCORD_intelligence_crypto_selected.dds",
        "spriteType",
        (516, 87),
    ),
    SpriteContract(
        "GFX_operatives_required_bg",
        "GFX_ADISCORD_intelligence_required",
        "ADISCORD_intelligence_required.dds",
        "spriteType",
        (33, 29),
    ),
    SpriteContract(
        "GFX_group_add_operative_bg",
        "GFX_ADISCORD_intelligence_add_operative",
        "ADISCORD_intelligence_add_operative.dds",
        "spriteType",
        (61, 83),
    ),
    SpriteContract(
        "GFX_operative_missionbar_bg",
        "GFX_ADISCORD_intelligence_mission_bar",
        "ADISCORD_intelligence_mission_bar.dds",
        "spriteType",
        (402, 79),
        effect_file=EFFECT,
    ),
)


VANILLA_FILES = {
    "countryintelligenceagencyview.gui": "00153f0968113c3f29d914bda227c729ba5d95f5888135c0dd98db89748ef3e5",
    "countryintelligenceagencyview.gfx": "5c4eb6c934654ff9d8c188c2560d51656b084d8b0de61d18fa4fb16b00c3d7da",
    "operative.gui": "bcdfa922932131db91c26dab7323e24456ae094b65c2aa2e7b77478c8dc5aa22",
    "operativeleader.gui": "cd80a14a5e2b70d11511eadf52a89b15be5188e4e03dce2e1acbc0040ecd79e0",
    "operativeleader.gfx": "f3ff58f344a1dcae6db664bcea70d3fe44ec1e64571f7165f5a135d927218f0f",
}


FILE_REPLACEMENTS = {
    "countryintelligenceagencyview.gui": {
        "GFX_tiled_window_1b_thin_border": (
            "GFX_ADISCORD_intelligence_content_tile",
            1,
        ),
        "GFX_tiled_bg": ("GFX_ADISCORD_intelligence_content_tile", 1),
        "GFX_tiled_paper_bg": ("GFX_ADISCORD_intelligence_paper_tile", 2),
        "GFX_tiled_paper_flat_bg": (
            "GFX_ADISCORD_intelligence_paper_tile",
            1,
        ),
        "GFX_tiled_paper_w_frame_bg": (
            "GFX_ADISCORD_intelligence_paper_tile",
            1,
        ),
        "GFX_tiled_window_insigna": (
            "GFX_ADISCORD_intelligence_window_shell",
            1,
        ),
        "GFX_tiled_window_transparent": (
            "GFX_ADISCORD_intelligence_transparent_tile",
            1,
        ),
        "GFX_intel_header_bg": ("GFX_ADISCORD_intelligence_header", 2),
        "GFX_operations_tab_large": ("GFX_ADISCORD_intelligence_tabs", 2),
        "GFX_agency_branch_upgrades_popup_bg": (
            "GFX_ADISCORD_intelligence_branches_popup",
            1,
        ),
        "GFX_operatives_bg": ("GFX_ADISCORD_intelligence_operatives", 1),
        "GFX_create_agency_bg": ("GFX_ADISCORD_intelligence_create", 1),
        "GFX_agency_branch_upgrade_entry_bg": (
            "GFX_ADISCORD_intelligence_branch_row",
            1,
        ),
        "GFX_agency_upgrade_cost_background": (
            "GFX_ADISCORD_intelligence_cost_tile",
            1,
        ),
        "GFX_cryptology_country_entry_bg": (
            "GFX_ADISCORD_intelligence_crypto_row",
            1,
        ),
        "GFX_operation_entry_bg": (
            "GFX_ADISCORD_intelligence_operation_row",
            1,
        ),
        "GFX_operatives_required_bg": (
            "GFX_ADISCORD_intelligence_required",
            2,
        ),
        "GFX_cryptology_country_entry_selected_bg": (
            "GFX_ADISCORD_intelligence_crypto_selected",
            1,
        ),
    },
    "operative.gui": {
        "GFX_tiled_paper_bg2": ("GFX_ADISCORD_intelligence_paper_tile", 1),
    },
    "operativeleader.gui": {
        "GFX_group_add_operative_bg": (
            "GFX_ADISCORD_intelligence_add_operative",
            1,
        ),
        "GFX_operative_missionbar_bg": (
            "GFX_ADISCORD_intelligence_mission_bar",
            1,
        ),
    },
}


FONT_REPLACEMENTS = (
    ("operations_tab_button", "hoi4_typewriter16", "hoi_18mbs"),
    ("crypto_tab_button", "hoi4_typewriter16", "hoi_18mbs"),
)


LEGACY_OUTPUTS = tuple(
    OUTPUT_DIR / f"ADISCORD_intelligence_{role}.dds"
    for role in ("window", "panel", "card", "selected")
)


def _verified_source(name: str) -> bytes:
    path = BASE_INTERFACE / name
    data = path.read_bytes()
    actual = hashlib.sha256(data).hexdigest()
    expected = VANILLA_FILES[name]
    if actual != expected:
        raise RuntimeError(
            f"vanilla interface mismatch for {name}: expected {expected}, found {actual}"
        )
    return data


def _named_button_bounds(text: str, name: str) -> tuple[int, int]:
    marker = f'name = "{name}"'
    marker_at = text.find(marker)
    if marker_at < 0:
        raise ValueError(f"missing intelligence button block: {name}")
    start = text.rfind("buttonType = {", 0, marker_at)
    if start < 0:
        raise ValueError(f"missing buttonType opener for: {name}")
    opening = text.find("{", start, marker_at)
    depth = 0
    for offset in range(opening, len(text)):
        if text[offset] == "{":
            depth += 1
        elif text[offset] == "}":
            depth -= 1
            if depth == 0:
                return start, offset + 1
    raise ValueError(f"unclosed intelligence button block: {name}")


def _replace_named_button_font(
    text: str,
    name: str,
    old_font: str,
    new_font: str,
) -> str:
    start, end = _named_button_bounds(text, name)
    block = text[start:end]
    replacement = replace_counted(block, old_font, new_font, 1)
    return text[:start] + replacement + text[end:]


def render_gui_files() -> dict[Path, bytes]:
    for name in VANILLA_FILES:
        _verified_source(name)
    outputs: dict[Path, bytes] = {}
    for name, replacements in FILE_REPLACEMENTS.items():
        text = _verified_source(name).decode("utf-8-sig")
        for old, (new, expected) in replacements.items():
            text = replace_counted(text, old, new, expected)
        if name == "countryintelligenceagencyview.gui":
            for block_name, old_font, new_font in FONT_REPLACEMENTS:
                text = _replace_named_button_font(
                    text,
                    block_name,
                    old_font,
                    new_font,
                )
        text = "\n".join(line.rstrip() for line in text.splitlines()) + "\n"
        text = re.sub(r"(?m)^ +(?=\t)", "", text)
        outputs[ROOT / "interface" / name] = text.encode("utf-8")
    return outputs


def _header(source_art: Image.Image, metal: Image.Image) -> Image.Image:
    del metal
    palette = PALETTES["intelligence"]
    fitted = ImageOps.fit(
        source_art.convert("RGBA"),
        (519, 109),
        method=Image.Resampling.LANCZOS,
        centering=(0.42, 0.48),
    )
    fitted = ImageEnhance.Contrast(fitted).enhance(0.72)
    fitted = ImageEnhance.Brightness(fitted).enhance(0.57)
    luminance = ImageOps.grayscale(fitted.convert("RGB"))
    output = ImageOps.colorize(
        luminance,
        black=palette.deep[:3],
        white=(78, 99, 119),
    ).convert("RGBA")
    overlay = Image.new("RGBA", output.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay, "RGBA")
    draw.rectangle((0, 0, 518, 108), fill=(4, 7, 11, 38))
    for x in range(245, 519):
        alpha = 28 + (x - 245) * 58 // 273
        draw.line((x, 0, x, 108), fill=(3, 6, 10, alpha))
    output = Image.alpha_composite(output, overlay)
    draw = ImageDraw.Draw(output, "RGBA")
    draw.line((5, 106, 513, 106), fill=palette.edge)
    draw.line((12, 108, 506, 108), fill=palette.accent)
    return output


def _operations_tabs(metal: Image.Image) -> Image.Image:
    palette = PALETTES["intelligence"]
    output = Image.new("RGBA", (524, 53), (0, 0, 0, 0))
    silhouette = Image.new("L", (262, 53), 0)
    ImageDraw.Draw(silhouette).polygon(
        ((0, 9), (10, 0), (251, 0), (261, 9), (261, 52), (0, 52)),
        fill=255,
    )
    for index, selected in enumerate((False, True)):
        frame = metal_surface(
            metal,
            (262, 53),
            palette,
            0.66 if not selected else 0.79,
        )
        frame.putalpha(silhouette)
        draw = ImageDraw.Draw(frame, "RGBA")
        edge = palette.accent_light if selected else palette.edge
        draw.line((10, 1, 251, 1, 260, 10), fill=palette.edge_light)
        draw.line((1, 10, 1, 51, 260, 51, 260, 10), fill=edge)
        draw.line((8, 48, 253, 48), fill=palette.accent if not selected else VIOLET_LIGHT, width=3)
        output.alpha_composite(frame, (index * 262, 0))
    return output


def _create_agency(metal: Image.Image) -> Image.Image:
    palette = PALETTES["intelligence"]
    output = metal_surface(metal, (508, 99), palette, 0.68)
    recessed_well(output, (9, 10, 80, 86), palette)
    raised_field(output, (91, 13, 353, 48), palette)
    recessed_well(output, (91, 57, 353, 80), palette)
    raised_field(output, (365, 16, 497, 78), palette)
    status_band(output, (10, 92, 497, 95), VIOLET)
    partial_rails(output, (5, 5, 502, 96), palette)
    return output


def _operatives_summary(metal: Image.Image) -> Image.Image:
    palette = PALETTES["intelligence"]
    output = metal_surface(metal, (522, 76), palette, 0.72)
    recessed_well(output, (7, 8, 76, 67), palette)
    raised_field(output, (87, 9, 216, 34), palette)
    recessed_well(output, (87, 42, 216, 66), palette)
    for left in (230, 286, 342, 398, 454):
        recessed_well(output, (left, 9, left + 47, 66), palette)
    partial_rails(output, (4, 4, 517, 71), palette)
    return output


def _branch_popup(metal: Image.Image) -> Image.Image:
    palette = PALETTES["intelligence"]
    output = metal_surface(metal, (1092, 91), palette, 0.71)
    raised_field(output, (11, 10, 865, 43), palette)
    recessed_well(output, (878, 10, 1032, 43), palette)
    recessed_well(output, (1042, 10, 1080, 43), palette)
    partial_rails(output, (8, 55, 1083, 82), palette)
    status_band(output, (12, 84, 1079, 87), STEEL_BLUE)
    return output


def _branch_row(metal: Image.Image) -> Image.Image:
    palette = PALETTES["intelligence"]
    output = metal_surface(metal, (1040, 136), palette, 0.64)
    raised_field(output, (10, 8, 1029, 41), palette)
    status_band(output, (12, 38, 1027, 41), WARM_COMPLETE)
    ImageDraw.Draw(output, "RGBA").rectangle((6, 45, 1033, 128), fill=palette.deep)
    for left in (10, 214, 418, 622, 826):
        raised_field(output, (left, 49, left + 193, 125), palette)
        recessed_well(output, (left + 8, 57, left + 65, 117), palette)
        partial_rails(output, (left + 75, 61, left + 184, 114), palette)
    status_band(output, (12, 131, 1027, 133), VIOLET)
    return output


def _operation_frame(metal: Image.Image, selected: bool) -> Image.Image:
    palette = PALETTES["intelligence"]
    output = metal_surface(metal, (519, 89), palette, 0.69 if not selected else 0.78)
    recessed_well(output, (7, 8, 74, 78), palette)
    raised_field(output, (84, 9, 353, 37), palette)
    recessed_well(output, (84, 46, 353, 75), palette)
    raised_field(output, (363, 9, 509, 75), palette)
    edge = VIOLET_LIGHT if selected else STEEL_BLUE
    status_band(output, (8, 83, 509, 87), edge)
    if selected:
        ImageDraw.Draw(output, "RGBA").line((3, 4, 515, 4), fill=palette.accent_light, width=2)
    return output


def _operation_strip(metal: Image.Image) -> Image.Image:
    output = Image.new("RGBA", (1038, 89), (0, 0, 0, 0))
    output.alpha_composite(_operation_frame(metal, False), (0, 0))
    output.alpha_composite(_operation_frame(metal, True), (519, 0))
    return output


def _crypto_row(metal: Image.Image, selected: bool) -> Image.Image:
    palette = PALETTES["intelligence"]
    output = metal_surface(metal, (516, 87), palette, 0.67 if not selected else 0.78)
    recessed_well(output, (7, 7, 70, 77), palette)
    raised_field(output, (80, 8, 361, 36), palette)
    recessed_well(output, (80, 44, 361, 72), palette)
    raised_field(output, (371, 8, 507, 72), palette)
    status_band(
        output,
        (8, 81, 507, 84),
        VIOLET_LIGHT if selected else STEEL_BLUE,
    )
    if selected:
        partial_rails(output, (3, 3, 512, 78), palette)
    return output


def _required(metal: Image.Image) -> Image.Image:
    palette = PALETTES["intelligence"]
    output = metal_surface(metal, (33, 29), palette, 0.72)
    recessed_well(output, (2, 2, 30, 26), palette)
    status_band(output, (4, 24, 28, 26), VIOLET)
    return output


def _add_operative(metal: Image.Image) -> Image.Image:
    palette = PALETTES["intelligence"]
    output = metal_surface(metal, (61, 83), palette, 0.72)
    recessed_well(output, (5, 6, 55, 63), palette)
    raised_field(output, (9, 67, 51, 77), palette)
    status_band(output, (7, 79, 53, 81), STEEL_BLUE)
    return output


def _mission_bar(metal: Image.Image) -> Image.Image:
    palette = PALETTES["intelligence"]
    output = metal_surface(metal, (402, 79), palette, 0.67)
    recessed_well(output, (6, 8, 63, 68), palette)
    raised_field(output, (72, 8, 286, 34), palette)
    recessed_well(output, (72, 42, 286, 67), palette)
    raised_field(output, (296, 8, 394, 67), palette)
    status_band(output, (7, 73, 394, 76), VIOLET)
    return output


def _window_shell(metal: Image.Image) -> Image.Image:
    return framed_panel(metal, (317, 444), PALETTES["intelligence"], 0.69)


def _content_tile(metal: Image.Image) -> Image.Image:
    palette = PALETTES["intelligence"]
    output = metal_surface(metal, (192, 192), palette, 0.63)
    partial_rails(output, (3, 4, 188, 187), palette)
    return output


def _paper_tile(metal: Image.Image) -> Image.Image:
    palette = PALETTES["intelligence"]
    output = metal_surface(metal, (192, 192), palette, 0.79)
    ImageDraw.Draw(output, "RGBA").rectangle((3, 3, 188, 188), outline=palette.edge)
    partial_rails(output, (7, 8, 184, 183), palette)
    return output


def _cost_tile(metal: Image.Image) -> Image.Image:
    palette = PALETTES["intelligence"]
    output = metal_surface(metal, (40, 50), palette, 0.73)
    recessed_well(output, (4, 5, 35, 44), palette)
    return output


def render_asset(
    contract: SpriteContract,
    metal: Image.Image,
    source_art: Image.Image,
) -> Image.Image:
    target = contract.target_name
    if target.endswith("window_shell"):
        return _window_shell(metal)
    if target.endswith("content_tile"):
        return _content_tile(metal)
    if target.endswith("paper_tile"):
        return _paper_tile(metal)
    if target.endswith("transparent_tile"):
        return Image.new("RGBA", contract.total_size, (0, 0, 0, 0))
    if target.endswith("cost_tile"):
        return _cost_tile(metal)
    if target.endswith("intelligence_header"):
        return _header(source_art, metal)
    if target.endswith("intelligence_create"):
        return _create_agency(metal)
    if target.endswith("branches_popup"):
        return _branch_popup(metal)
    if target.endswith("branch_row"):
        return _branch_row(metal)
    if target.endswith("intelligence_operatives"):
        return _operatives_summary(metal)
    if target.endswith("intelligence_tabs"):
        return _operations_tabs(metal)
    if target.endswith("operation_row"):
        return _operation_strip(metal)
    if target.endswith("crypto_row"):
        return _crypto_row(metal, False)
    if target.endswith("crypto_selected"):
        return _crypto_row(metal, True)
    if target.endswith("intelligence_required"):
        return _required(metal)
    if target.endswith("add_operative"):
        return _add_operative(metal)
    if target.endswith("mission_bar"):
        return _mission_bar(metal)
    raise ValueError(f"missing intelligence renderer: {target}")


def render_gfx() -> str:
    entries = "".join(
        render_gfx_entry(
            contract,
            f"gfx/interface/intelligence/ui/{contract.filename}",
        )
        for contract in INTELLIGENCE_CONTRACTS
    )
    return f"spriteTypes = {{\n{entries}}}\n"


def _png_bytes(image: Image.Image) -> bytes:
    stream = BytesIO()
    image.save(stream, format="PNG", optimize=False, compress_level=9)
    return stream.getvalue()


def expected_outputs() -> dict[Path, bytes]:
    metal = load_surface_source(METAL_SOURCE)
    source_art = load_surface_source(HEADER_SOURCE, minimum_size=(1024, 512))
    assets: list[tuple[SpriteContract, Image.Image]] = []
    for contract in INTELLIGENCE_CONTRACTS:
        image = render_asset(contract, metal, source_art)
        validate_contract_image(contract, image)
        assets.append((contract, image))
    outputs = render_gui_files()
    outputs.update(
        {
            GFX_OUTPUT: render_gfx().encode("utf-8"),
            PREVIEW: _png_bytes(
                contact_sheet(
                    [(item.target_name, image) for item, image in assets],
                    1120,
                )
            ),
        }
    )
    outputs.update(
        {OUTPUT_DIR / item.filename: dds_bytes(image) for item, image in assets}
    )
    return outputs


def _remove_legacy_outputs() -> None:
    for path in LEGACY_OUTPUTS:
        if path.is_file():
            path.unlink()
            print(f"REMOVED: {path}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build A-Discord intelligence UI assets.")
    actions = parser.add_mutually_exclusive_group()
    actions.add_argument("--check", action="store_true")
    actions.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    if not args.apply:
        obsolete = [path for path in LEGACY_OUTPUTS if path.is_file()]
        if obsolete:
            for path in obsolete:
                print(f"OBSOLETE: {path}")
            return 1
    result = apply_or_check(expected_outputs(), args.apply, "Intelligence UI")
    if result == 0 and args.apply:
        _remove_legacy_outputs()
    return result


if __name__ == "__main__":
    raise SystemExit(main())
