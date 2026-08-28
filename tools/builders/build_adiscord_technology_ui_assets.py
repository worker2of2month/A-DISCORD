#!/usr/bin/env python3
"""Build the semantic A-Discord technology overview and detail surfaces."""

from __future__ import annotations

import argparse
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
VANILLA_GUI = BASE_GAME / "interface/countrytechnologyview.gui"
SOURCE = ROOT / "gfx/interface/production/source/production_surface_source.png"
OUTPUT_DIR = ROOT / "gfx/interface/technology/ui"
PREVIEW = (
    ROOT
    / "gfx/interface/technology/preview/ADISCORD_technology_overview_preview.png"
)
TREE_PREVIEW = (
    ROOT
    / "gfx/interface/technology/preview/ADISCORD_technology_tree_preview.png"
)
GUI_OUTPUT = ROOT / "interface/countrytechnologyview.gui"
GFX_OUTPUT = ROOT / "interface/ADISCORD_technology_ui.gfx"
STATE_GFX_OUTPUT = ROOT / "interface/zz_ADISCORD_technology_states.gfx"

EFFECT = "gfx/FX/buttonstate_nodowneffect.lua"
MUTED_GOLD = (146, 116, 62, 255)
NEUTRAL_GREY = (88, 92, 92, 255)
MUTED_GREEN = (64, 112, 76, 255)
MUTED_BRANCH = (74, 88, 108, 255)
COLD_WRITING_DARK = (118, 134, 137, 255)
COLD_WRITING_LIGHT = (225, 234, 235, 255)
COLD_WRITING_EDGE = (76, 94, 96, 255)
COLD_WRITING_HIGHLIGHT = (188, 201, 202, 255)


TECHNOLOGY_OVERVIEW_CONTRACTS = (
    SpriteContract(
        "GFX_tiled_window2_1b_border",
        "GFX_ADISCORD_technology_window_shell",
        "ADISCORD_technology_window_shell.dds",
        "corneredTileSpriteType",
        (190, 190),
        border_size=(64, 64),
        effect_file=EFFECT,
        tiling_center=True,
    ),
    SpriteContract(
        "GFX_tiled_plain_bg",
        "GFX_ADISCORD_technology_content_tile",
        "ADISCORD_technology_content_tile.dds",
        "corneredTileSpriteType",
        (190, 190),
        border_size=(64, 64),
        effect_file=EFFECT,
        tiling_center=True,
    ),
    SpriteContract(
        "GFX_tiled_generic_overlay_bg1",
        "GFX_ADISCORD_technology_overlay",
        "ADISCORD_technology_overlay.dds",
        "corneredTileSpriteType",
        (549, 600),
        border_size=(268, 268),
        effect_file=EFFECT,
        always_transparent=True,
        tiling_center=True,
    ),
    SpriteContract(
        "GFX_tiled_window_transparent",
        "GFX_ADISCORD_technology_transparent_tile",
        "ADISCORD_technology_transparent_tile.dds",
        "corneredTileSpriteType",
        (3, 3),
        border_size=(1, 1),
        effect_file=EFFECT,
    ),
    SpriteContract(
        "GFX_research_line_bg",
        "GFX_ADISCORD_technology_slot",
        "ADISCORD_technology_slot.dds",
        "spriteType",
        (508, 99),
    ),
    SpriteContract(
        "GFX_tech_idea_bg",
        "GFX_ADISCORD_technology_idea",
        "ADISCORD_technology_idea.dds",
        "spriteType",
        (63, 63),
        effect_file=EFFECT,
    ),
    SpriteContract(
        "GFX_tab_large",
        "GFX_ADISCORD_technology_tabs",
        "ADISCORD_technology_tabs.dds",
        "spriteType",
        (516, 42),
        frames=2,
    ),
    SpriteContract(
        "GFX_research_top_win",
        "GFX_ADISCORD_technology_top",
        "ADISCORD_technology_top.dds",
        "spriteType",
        (548, 138),
        effect_file=EFFECT,
    ),
    SpriteContract(
        "GFX_production_win_bottom",
        "GFX_ADISCORD_technology_bottom",
        "ADISCORD_technology_bottom.dds",
        "corneredTileSpriteType",
        (546, 66),
        border_size=(182, 22),
        effect_file=EFFECT,
        tiling_center=True,
    ),
    SpriteContract(
        "GFX_tiled_plain_bg2",
        "GFX_ADISCORD_technology_tree_content_tile",
        "ADISCORD_technology_tree_content_tile.dds",
        "corneredTileSpriteType",
        (182, 186),
        border_size=(64, 64),
        effect_file=EFFECT,
        tiling_center=True,
    ),
    SpriteContract(
        "GFX_tiled_window_2b_border",
        "GFX_ADISCORD_technology_tree_window_tile",
        "ADISCORD_technology_tree_window_tile.dds",
        "corneredTileSpriteType",
        (190, 190),
        border_size=(64, 64),
        effect_file=EFFECT,
        tiling_center=True,
    ),
    SpriteContract(
        "GFX_techtree_stripes",
        "GFX_ADISCORD_technology_tree_stripes",
        "ADISCORD_technology_tree_stripes.dds",
        "corneredTileSpriteType",
        (122, 244),
        border_size=(0, 0),
        effect_file=EFFECT,
        always_transparent=True,
        tiling_center=True,
    ),
    SpriteContract(
        "GFX_tiled_paper_bg",
        "GFX_ADISCORD_technology_detail_content_tile",
        "ADISCORD_technology_detail_content_tile.dds",
        "corneredTileSpriteType",
        (192, 192),
        border_size=(64, 64),
        effect_file=EFFECT,
        tiling_center=True,
    ),
    SpriteContract(
        "GFX_tech_info_top_win",
        "GFX_ADISCORD_technology_info_top",
        "ADISCORD_technology_info_top.dds",
        "spriteType",
        (548, 220),
        effect_file=EFFECT,
    ),
    SpriteContract(
        "GFX_technology_info_bg",
        "GFX_ADISCORD_technology_info",
        "ADISCORD_technology_info.dds",
        "spriteType",
        (508, 517),
        effect_file=EFFECT,
    ),
)

TECHNOLOGY_STATE_CONTRACTS = (
    SpriteContract(
        "GFX_technology_unavailable_item_bg",
        "GFX_technology_unavailable_item_bg",
        "ADISCORD_technology_node_unavailable.dds",
        "spriteType",
        (183, 84),
    ),
    SpriteContract(
        "GFX_technology_available_item_bg",
        "GFX_technology_available_item_bg",
        "ADISCORD_technology_node_available.dds",
        "spriteType",
        (183, 84),
    ),
    SpriteContract(
        "GFX_technology_researched_item_bg",
        "GFX_technology_researched_item_bg",
        "ADISCORD_technology_node_researched.dds",
        "spriteType",
        (183, 84),
    ),
    SpriteContract(
        "GFX_technology_branch_item_bg",
        "GFX_technology_branch_item_bg",
        "ADISCORD_technology_node_branch.dds",
        "spriteType",
        (183, 84),
    ),
    SpriteContract(
        "GFX_technology_currently_researching_item_bg",
        "GFX_technology_currently_researching_item_bg",
        "ADISCORD_technology_node_researching.dds",
        "frameAnimatedSpriteType",
        (1647, 84),
        frames=9,
        extra_lines=(
            'loadType = "INGAME"',
            "transparencecheck = yes",
            "animation_rate_fps = 15",
            "looping = yes",
            "play_on_show = yes",
            "pause_on_loop = 0.0",
        ),
    ),
)

CONTRACTS_BY_TARGET = {
    contract.target_name: contract for contract in TECHNOLOGY_OVERVIEW_CONTRACTS
}


def _output_path(target_name: str) -> Path:
    return OUTPUT_DIR / CONTRACTS_BY_TARGET[target_name].filename


WINDOW_SHELL = _output_path("GFX_ADISCORD_technology_window_shell")
CONTENT_TILE = _output_path("GFX_ADISCORD_technology_content_tile")
OVERLAY = _output_path("GFX_ADISCORD_technology_overlay")
TRANSPARENT_TILE = _output_path("GFX_ADISCORD_technology_transparent_tile")
SLOT = _output_path("GFX_ADISCORD_technology_slot")
IDEA = _output_path("GFX_ADISCORD_technology_idea")
TABS = _output_path("GFX_ADISCORD_technology_tabs")
TOP = _output_path("GFX_ADISCORD_technology_top")
BOTTOM = _output_path("GFX_ADISCORD_technology_bottom")
TREE_CONTENT_TILE = _output_path("GFX_ADISCORD_technology_tree_content_tile")
TREE_WINDOW_TILE = _output_path("GFX_ADISCORD_technology_tree_window_tile")
TREE_STRIPES = _output_path("GFX_ADISCORD_technology_tree_stripes")
DETAIL_CONTENT_TILE = _output_path("GFX_ADISCORD_technology_detail_content_tile")
INFO_TOP = _output_path("GFX_ADISCORD_technology_info_top")
INFO = _output_path("GFX_ADISCORD_technology_info")


SPRITE_REPLACEMENTS = {
    contract.source_name: (contract.target_name, count)
    for contract, count in (
        (CONTRACTS_BY_TARGET["GFX_ADISCORD_technology_window_shell"], 1),
        (CONTRACTS_BY_TARGET["GFX_ADISCORD_technology_content_tile"], 1),
        (CONTRACTS_BY_TARGET["GFX_ADISCORD_technology_overlay"], 1),
        (CONTRACTS_BY_TARGET["GFX_ADISCORD_technology_transparent_tile"], 1),
        (CONTRACTS_BY_TARGET["GFX_ADISCORD_technology_idea"], 1),
        (CONTRACTS_BY_TARGET["GFX_ADISCORD_technology_slot"], 1),
        (CONTRACTS_BY_TARGET["GFX_ADISCORD_technology_tabs"], 2),
        (CONTRACTS_BY_TARGET["GFX_ADISCORD_technology_top"], 1),
        (CONTRACTS_BY_TARGET["GFX_ADISCORD_technology_bottom"], 1),
    )
}

TREE_SPRITE_REPLACEMENTS = {
    "GFX_tiled_plain_bg2": ("GFX_ADISCORD_technology_tree_content_tile", 1),
    "GFX_tiled_window_2b_border": (
        "GFX_ADISCORD_technology_tree_window_tile",
        12,
    ),
    "GFX_techtree_stripes": ("GFX_ADISCORD_technology_tree_stripes", 12),
    "GFX_tiled_paper_bg": (
        "GFX_ADISCORD_technology_detail_content_tile",
        2,
    ),
    "GFX_tech_info_top_win": ("GFX_ADISCORD_technology_info_top", 2),
}

LEGACY_OUTPUTS = tuple(
    OUTPUT_DIR / f"ADISCORD_technology_{role}.dds"
    for role in (
        "window",
        "panel",
        "card",
        "tab",
        "tree_panel",
        "tree_info_top",
        "tree_info",
    )
)


def render_gui() -> str:
    if not VANILLA_GUI.is_file():
        raise RuntimeError(f"missing vanilla research GUI: {VANILLA_GUI}")
    text = VANILLA_GUI.read_text(encoding="utf-8-sig")
    for old, (new, expected) in SPRITE_REPLACEMENTS.items():
        text = replace_counted(text, old, new, expected)
    text = "\n".join(line.rstrip() for line in text.splitlines()) + "\n"
    return re.sub(r"(?m)^ +(?=\t)", "", text)


def apply_tree_skin(text: str) -> str:
    detail_background = re.compile(
        r'#SpriteType\s*=\s*"GFX_technology_info_bg"'
        r'(?P<gap>\s*)'
        r'SpriteType\s*=\s*"GFX_tiled_window_thin_border2"'
    )
    text, count = detail_background.subn(
        'SpriteType = "GFX_ADISCORD_technology_info"'
        r'\g<gap>'
        '#SpriteType = "GFX_tiled_window_thin_border2"',
        text,
    )
    if count != 2:
        raise ValueError(f"technology detail background: expected 2, found {count}")
    for old, (new, expected) in TREE_SPRITE_REPLACEMENTS.items():
        text = replace_counted(text, old, new, expected)
    return text


def technology_tree_gfx_entries() -> str:
    tree_sources = {
        "GFX_tiled_plain_bg2",
        "GFX_tiled_window_2b_border",
        "GFX_techtree_stripes",
        "GFX_tiled_paper_bg",
        "GFX_tech_info_top_win",
        "GFX_technology_info_bg",
    }
    return "\n" + "".join(
        render_gfx_entry(
            contract,
            f"gfx/interface/technology/ui/{contract.filename}",
        )
        for contract in TECHNOLOGY_OVERVIEW_CONTRACTS
        if contract.source_name in tree_sources
    )


def _window_shell(source: Image.Image) -> Image.Image:
    palette = PALETTES["technology"]
    output = metal_surface(source, (190, 190), palette, 0.66)
    outer_frame(output, (0, 0, 189, 189), palette)
    return output


def _content_tile(source: Image.Image) -> Image.Image:
    palette = PALETTES["technology"]
    output = metal_surface(source, (190, 190), palette, 0.68)
    partial_rails(output, (4, 5, 185, 184), palette)
    return output


def _overlay(source: Image.Image) -> Image.Image:
    palette = PALETTES["technology"]
    output = metal_surface(source, (549, 600), palette, 0.64)
    partial_rails(output, (5, 6, 543, 593), palette)
    return output


def _research_slot(source: Image.Image) -> Image.Image:
    palette = PALETTES["technology"]
    output = metal_surface(source, (508, 99), palette, 0.76)
    recessed_well(output, (7, 8, 52, 90), palette)
    raised_field(output, (57, 8, 326, 70), palette)
    recessed_well(output, (331, 8, 499, 73), palette)
    recessed_well(output, (59, 75, 445, 93), palette)
    raised_field(output, (450, 77, 500, 93), palette)
    status_band(output, (62, 89, 442, 92), palette.accent)
    partial_rails(output, (3, 3, 504, 95), palette)
    return output


def _idea_button(source: Image.Image) -> Image.Image:
    palette = PALETTES["technology"]
    output = metal_surface(source, (63, 63), palette, 0.77)
    recessed_well(output, (5, 5, 57, 57), palette)
    status_band(output, (8, 55, 54, 58), MUTED_GOLD)
    return output


def _overview_tabs(source: Image.Image) -> Image.Image:
    palette = PALETTES["technology"]
    output = Image.new("RGBA", (516, 42), (0, 0, 0, 0))
    base = metal_surface(source, (258, 42), palette, 0.76)
    partial_rails(base, (3, 4, 254, 38), palette)
    normal = base.copy()
    selected = base.copy()
    status_band(normal, (8, 36, 249, 39), palette.edge)
    status_band(selected, (8, 35, 249, 39), palette.accent_light)
    ImageDraw.Draw(selected, "RGBA").line((10, 5, 247, 5), fill=palette.edge_light)
    output.alpha_composite(normal, (0, 0))
    output.alpha_composite(selected, (258, 0))
    return output


def _overview_top(source: Image.Image) -> Image.Image:
    palette = PALETTES["technology"]
    output = metal_surface(source, (548, 138), palette, 0.80)
    partial_rails(output, (5, 5, 542, 133), palette)
    raised_field(output, (324, 5, 520, 101), palette)
    recessed_well(output, (44, 104, 271, 132), palette)
    recessed_well(output, (290, 104, 513, 132), palette)
    status_band(output, (8, 2, 539, 4), palette.accent)
    return output


def _overview_bottom(source: Image.Image) -> Image.Image:
    palette = PALETTES["technology"]
    output = metal_surface(source, (546, 66), palette, 0.70)
    partial_rails(output, (4, 3, 541, 61), palette)
    return output


def _tree_content_tile(source: Image.Image) -> Image.Image:
    palette = PALETTES["technology"]
    output = metal_surface(source, (182, 186), palette, 0.52)
    partial_rails(output, (4, 5, 177, 180), palette)
    return output


def _tree_window_tile(source: Image.Image) -> Image.Image:
    palette = PALETTES["technology"]
    output = metal_surface(source, (190, 190), palette, 0.55)
    outer_frame(output, (0, 0, 189, 189), palette)
    return output


def _tree_stripes(source: Image.Image) -> Image.Image:
    palette = PALETTES["technology"]
    output = metal_surface(source, (122, 244), palette, 0.48)
    draw = ImageDraw.Draw(output, "RGBA")
    for x in range(0, 122, 30):
        draw.line((x, 0, x, 243), fill=(55, 77, 78, 90))
    for y in range(0, 244, 30):
        draw.line((0, y, 121, y), fill=(55, 77, 78, 70))
    draw.line((60, 0, 60, 243), fill=palette.accent)
    return output


def _cold_steel_surface(
    source: Image.Image,
    size: tuple[int, int],
) -> Image.Image:
    fitted = ImageOps.fit(
        source.convert("RGBA"),
        size,
        method=Image.Resampling.LANCZOS,
        centering=(0.5, 0.5),
    )
    luminance = ImageEnhance.Contrast(
        ImageOps.grayscale(fitted.convert("RGB"))
    ).enhance(1.5)
    output = ImageOps.colorize(
        luminance,
        black=COLD_WRITING_DARK[:3],
        white=COLD_WRITING_LIGHT[:3],
    ).convert("RGBA")
    output.putalpha(255)
    return output


def _cold_steel_panel(
    output: Image.Image,
    source: Image.Image,
    box: tuple[int, int, int, int],
) -> None:
    left, top, right, bottom = box
    panel = _cold_steel_surface(source, (right - left + 1, bottom - top + 1))
    output.alpha_composite(panel, (left, top))
    draw = ImageDraw.Draw(output, "RGBA")
    draw.rectangle(box, outline=COLD_WRITING_EDGE)
    draw.line((left + 1, top + 1, right - 1, top + 1), fill=COLD_WRITING_HIGHLIGHT)
    draw.line((left + 1, bottom - 1, right - 1, bottom - 1), fill=COLD_WRITING_EDGE)


def _detail_content_tile(source: Image.Image) -> Image.Image:
    palette = PALETTES["technology"]
    output = metal_surface(source, (192, 192), palette, 0.96)
    ImageDraw.Draw(output, "RGBA").rectangle(
        (3, 3, 188, 188),
        outline=palette.edge,
    )
    partial_rails(output, (7, 8, 184, 183), palette)
    return output


def _technology_info_top(source: Image.Image) -> Image.Image:
    palette = PALETTES["technology"]
    output = metal_surface(source, (548, 220), palette, 0.72)
    _cold_steel_panel(output, source, (24, 8, 523, 39))
    recessed_well(output, (25, 44, 151, 110), palette)
    _cold_steel_panel(output, source, (165, 47, 525, 108))
    _cold_steel_panel(output, source, (20, 116, 527, 207))
    draw = ImageDraw.Draw(output, "RGBA")
    draw.line((24, 120, 523, 120), fill=palette.edge_light)
    status_band(output, (8, 212, 539, 216), palette.accent)
    partial_rails(output, (4, 4, 543, 215), palette)
    return output


def _technology_info(source: Image.Image) -> Image.Image:
    palette = PALETTES["technology"]
    output = metal_surface(source, (508, 517), palette, 0.66)
    _cold_steel_panel(output, source, (16, 216, 491, 505))
    draw = ImageDraw.Draw(output, "RGBA")
    for y in range(230, 500, 28):
        draw.line((20, y, 487, y), fill=(103, 120, 122, 255))
    partial_rails(output, (5, 5, 502, 511), palette)
    status_band(output, (8, 8, 499, 11), MUTED_GOLD)
    return output


def _technology_node(
    source: Image.Image,
    edge_color: tuple[int, int, int, int],
) -> Image.Image:
    """Draw one node while keeping icon, title, and 17px status geometry fixed."""
    palette = PALETTES["technology"]
    output = metal_surface(source, (183, 84), palette, 0.68)
    recessed_well(output, (7, 7, 69, 65), palette)
    raised_field(output, (74, 7, 176, 65), palette)
    status_band(output, (0, 67, 182, 83), edge_color)
    draw = ImageDraw.Draw(output, "RGBA")
    draw.rectangle((1, 1, 181, 82), outline=palette.deep, width=1)
    draw.rectangle((2, 2, 180, 81), outline=edge_color, width=3)
    draw.line((8, 65, 175, 65), fill=palette.edge_light)
    return output


def _researching_strip(source: Image.Image) -> Image.Image:
    """Assemble nine identical node frames with a moving teal edge highlight."""
    palette = PALETTES["technology"]
    output = Image.new("RGBA", (183 * 9, 84), (0, 0, 0, 0))
    for index in range(9):
        frame = _technology_node(source, palette.accent)
        segment_start = 8 + index * 18
        ImageDraw.Draw(frame, "RGBA").line(
            (segment_start, 3, segment_start + 17, 3),
            fill=palette.accent_light,
            width=1,
        )
        output.alpha_composite(frame, (183 * index, 0))
    return output


def render_state_asset(contract: SpriteContract, source: Image.Image) -> Image.Image:
    renderers = {
        "GFX_technology_unavailable_item_bg": lambda: _technology_node(
            source, NEUTRAL_GREY
        ),
        "GFX_technology_available_item_bg": lambda: _technology_node(
            source, MUTED_GOLD
        ),
        "GFX_technology_researched_item_bg": lambda: _technology_node(
            source, MUTED_GREEN
        ),
        "GFX_technology_branch_item_bg": lambda: _technology_node(
            source, MUTED_BRANCH
        ),
        "GFX_technology_currently_researching_item_bg": lambda: _researching_strip(
            source
        ),
    }
    if contract.target_name not in renderers:
        raise ValueError(f"missing technology state renderer: {contract.target_name}")
    return renderers[contract.target_name]()


def render_asset(contract: SpriteContract, source: Image.Image) -> Image.Image:
    target = contract.target_name
    renderers = {
        "GFX_ADISCORD_technology_window_shell": _window_shell,
        "GFX_ADISCORD_technology_content_tile": _content_tile,
        "GFX_ADISCORD_technology_overlay": _overlay,
        "GFX_ADISCORD_technology_slot": _research_slot,
        "GFX_ADISCORD_technology_idea": _idea_button,
        "GFX_ADISCORD_technology_tabs": _overview_tabs,
        "GFX_ADISCORD_technology_top": _overview_top,
        "GFX_ADISCORD_technology_bottom": _overview_bottom,
        "GFX_ADISCORD_technology_tree_content_tile": _tree_content_tile,
        "GFX_ADISCORD_technology_tree_window_tile": _tree_window_tile,
        "GFX_ADISCORD_technology_tree_stripes": _tree_stripes,
        "GFX_ADISCORD_technology_detail_content_tile": _detail_content_tile,
        "GFX_ADISCORD_technology_info_top": _technology_info_top,
        "GFX_ADISCORD_technology_info": _technology_info,
    }
    if target == "GFX_ADISCORD_technology_transparent_tile":
        return Image.new("RGBA", contract.total_size, (0, 0, 0, 0))
    if target not in renderers:
        raise ValueError(f"missing technology renderer: {target}")
    return renderers[target](source)


def render_gfx() -> str:
    overview_sources = {
        "GFX_tiled_window2_1b_border",
        "GFX_tiled_plain_bg",
        "GFX_tiled_generic_overlay_bg1",
        "GFX_tiled_window_transparent",
        "GFX_research_line_bg",
        "GFX_tech_idea_bg",
        "GFX_tab_large",
        "GFX_research_top_win",
        "GFX_production_win_bottom",
    }
    entries = "".join(
        render_gfx_entry(
            contract,
            f"gfx/interface/technology/ui/{contract.filename}",
        )
        for contract in TECHNOLOGY_OVERVIEW_CONTRACTS
        if contract.source_name in overview_sources
    )
    return f"spriteTypes = {{\n{entries}}}\n"


def render_state_gfx() -> str:
    entries = "".join(
        render_gfx_entry(
            contract,
            f"gfx/interface/technology/ui/{contract.filename}",
        )
        for contract in TECHNOLOGY_STATE_CONTRACTS
    )
    return f"spriteTypes = {{\n{entries}}}\n"


def expected_technology_state_gfx_bytes() -> bytes:
    """Return the one UI-owned state declaration snapshot shared read-only."""
    return render_state_gfx().encode("utf-8")


def _png_bytes(image: Image.Image) -> bytes:
    stream = BytesIO()
    image.save(stream, format="PNG", optimize=False, compress_level=9)
    return stream.getvalue()


def expected_outputs() -> dict[Path, bytes]:
    source = load_surface_source(SOURCE)
    assets: list[tuple[SpriteContract, Image.Image]] = []
    for contract in TECHNOLOGY_OVERVIEW_CONTRACTS:
        image = render_asset(contract, source)
        validate_contract_image(contract, image)
        assets.append((contract, image))
    state_assets: list[tuple[SpriteContract, Image.Image]] = []
    for contract in TECHNOLOGY_STATE_CONTRACTS:
        image = render_state_asset(contract, source)
        validate_contract_image(contract, image)
        state_assets.append((contract, image))
    preview_targets = {
        "GFX_ADISCORD_technology_slot",
        "GFX_ADISCORD_technology_idea",
        "GFX_ADISCORD_technology_tabs",
        "GFX_ADISCORD_technology_top",
        "GFX_ADISCORD_technology_bottom",
        "GFX_ADISCORD_technology_tree_window_tile",
        "GFX_ADISCORD_technology_info_top",
        "GFX_ADISCORD_technology_info",
    }
    outputs = {
        GUI_OUTPUT: render_gui().encode("utf-8"),
        GFX_OUTPUT: render_gfx().encode("utf-8"),
        STATE_GFX_OUTPUT: expected_technology_state_gfx_bytes(),
        PREVIEW: _png_bytes(
            contact_sheet(
                [
                    (contract.target_name, image)
                    for contract, image in assets
                    if contract.target_name in preview_targets
                ],
                580,
            )
        ),
        TREE_PREVIEW: _png_bytes(
            contact_sheet(
                [
                    (contract.target_name, image)
                    for contract, image in state_assets
                ],
                580,
            )
        ),
    }
    outputs.update(
        {OUTPUT_DIR / contract.filename: dds_bytes(image) for contract, image in assets}
    )
    outputs.update(
        {
            OUTPUT_DIR / contract.filename: dds_bytes(image)
            for contract, image in state_assets
        }
    )
    return outputs


def _remove_legacy_outputs() -> None:
    for path in LEGACY_OUTPUTS:
        if path.is_file():
            path.unlink()
            print(f"REMOVED: {path}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build A-Discord technology UI assets.")
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
    result = apply_or_check(expected_outputs(), args.apply, "Technology UI")
    if result == 0 and args.apply:
        _remove_legacy_outputs()
    return result


if __name__ == "__main__":
    raise SystemExit(main())
