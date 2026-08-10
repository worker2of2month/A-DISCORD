"""Generate A-Discord's minimap and coherent lower-right HUD skin."""

from __future__ import annotations

import argparse
from io import BytesIO
from pathlib import Path
from typing import Callable

from PIL import Image, ImageChops, ImageDraw, ImageEnhance, ImageFilter, ImageOps


ROOT = Path(__file__).resolve().parents[2]
TERRAIN_PATH = ROOT / "map" / "terrain.bmp"
HEIGHTMAP_PATH = ROOT / "map" / "heightmap.bmp"

MINIMAP_PATH = ROOT / "gfx" / "minimap" / "minimap.dds"
MINIMAP_BORDER_PATH = ROOT / "gfx" / "minimap" / "border.dds"
MINIMAP_HANDLE_PATH = ROOT / "gfx" / "minimap" / "handle_default.dds"
MINIMAP_HANDLE_PINGED_PATH = ROOT / "gfx" / "minimap" / "handle_pinged.dds"
MINIMAP_OFFENSIVE_PATH = ROOT / "gfx" / "minimap" / "offensive_ping_btn.dds"
MINIMAP_DEFENSIVE_PATH = ROOT / "gfx" / "minimap" / "defensive_ping_btn.dds"
MINIMAP_QUAD_PATH = ROOT / "gfx" / "minimap" / "minimap_quad_pixel.dds"

MAPMODE_ROOT = ROOT / "gfx" / "interface" / "mapmode"
MAPMODE_MAIN_BG_PATH = MAPMODE_ROOT / "mapmode_main_bg.dds"
MAPMODE_BOTTOM_BG_PATH = MAPMODE_ROOT / "mapmode_bottom_bg.dds"
MAPMODE_BIG_BG_PATH = MAPMODE_ROOT / "mapmode_button_bg.dds"
MAPMODE_SMALL_BG_PATH = MAPMODE_ROOT / "mapmode_button_depressed.dds"
MAPMODE_FIND_PATH = MAPMODE_ROOT / "find_screen_button.dds"
MAPMODE_ALL_PATH = MAPMODE_ROOT / "mapmode_button_all.dds"
MAPMODE_CONFIGURE_PATH = MAPMODE_ROOT / "mapmode_buttons_configure.dds"
MAPMODE_CONFIGURE_BG_PATH = MAPMODE_ROOT / "mapmode_configure_bg.dds"
MAPMODE_BIG_SELECTED_PATH = MAPMODE_ROOT / "mapmode_buttons_selected_big.dds"
MAPMODE_BIG_DESELECTED_PATH = MAPMODE_ROOT / "mapmode_buttons_deselected_big.dds"
MAPMODE_SMALL_SELECTED_PATH = MAPMODE_ROOT / "mapmode_buttons_selected_small.dds"
MAPMODE_SMALL_DESELECTED_PATH = MAPMODE_ROOT / "mapmode_buttons_deselected_small.dds"
MAPMODE_DAY_NIGHT_PATH = MAPMODE_ROOT / "day_night_toggle.dds"
MAPMODE_FOG_PATH = MAPMODE_ROOT / "fog_of_war_toggle.dds"
MAPMODE_RADAR_PATH = MAPMODE_ROOT / "radar_toggle.dds"
MAPMODE_ALLIED_PLANS_PATH = MAPMODE_ROOT / "allied_plans_button.dds"
MAPMODE_COUNTERS_PATH = MAPMODE_ROOT / "player_counters_toggle.dds"
MAPMODE_COUNTER_COLOUR_PATH = MAPMODE_ROOT / "counters_color_mode_button.dds"

MINIMAP_SIZE = (268, 97)
OCEAN_TERRAIN_INDEX = 15

BLACK = (4, 6, 7, 255)
DEEP = (9, 14, 16, 255)
DEEP_SOFT = (15, 22, 24, 255)
STEEL = (82, 95, 97, 255)
STEEL_SOFT = (45, 57, 59, 255)
PALE = (207, 216, 212, 255)
CYAN = (43, 132, 136, 245)
CYAN_SOFT = (29, 96, 101, 235)
CYAN_DARK = (16, 55, 59, 255)
BRASS = (184, 139, 48, 255)
RED = (184, 72, 56, 255)


OUTPUT_SIZES: dict[Path, tuple[int, int]] = {
    MINIMAP_PATH: MINIMAP_SIZE,
    MINIMAP_BORDER_PATH: (276, 105),
    MINIMAP_HANDLE_PATH: (24, 64),
    MINIMAP_HANDLE_PINGED_PATH: (24, 64),
    MINIMAP_OFFENSIVE_PATH: (64, 31),
    MINIMAP_DEFENSIVE_PATH: (64, 31),
    MINIMAP_QUAD_PATH: (2, 2),
    MAPMODE_MAIN_BG_PATH: (87, 206),
    MAPMODE_BOTTOM_BG_PATH: (86, 59),
    MAPMODE_BIG_BG_PATH: (42, 51),
    MAPMODE_SMALL_BG_PATH: (23, 20),
    MAPMODE_FIND_PATH: (39, 39),
    MAPMODE_ALL_PATH: (44, 21),
    MAPMODE_CONFIGURE_PATH: (44, 21),
    MAPMODE_CONFIGURE_BG_PATH: (519, 23),
    MAPMODE_BIG_SELECTED_PATH: (136, 31),
    MAPMODE_BIG_DESELECTED_PATH: (136, 31),
    MAPMODE_SMALL_SELECTED_PATH: (360, 18),
    MAPMODE_SMALL_DESELECTED_PATH: (360, 18),
    MAPMODE_DAY_NIGHT_PATH: (44, 22),
    MAPMODE_FOG_PATH: (44, 22),
    MAPMODE_RADAR_PATH: (44, 22),
    MAPMODE_ALLIED_PLANS_PATH: (44, 22),
    MAPMODE_COUNTERS_PATH: (44, 22),
    MAPMODE_COUNTER_COLOUR_PATH: (44, 22),
}


def _land_mask() -> Image.Image:
    with Image.open(TERRAIN_PATH) as terrain:
        if terrain.mode != "P":
            raise RuntimeError(f"terrain.bmp must be paletted, found {terrain.mode}")
        lookup = [255] * 256
        lookup[OCEAN_TERRAIN_INDEX] = 0
        mask = terrain.point(lookup, mode="L")
    return mask.resize(MINIMAP_SIZE, Image.Resampling.LANCZOS)


def _minimap() -> Image.Image:
    land = _land_mask()
    with Image.open(HEIGHTMAP_PATH) as heightmap:
        height = heightmap.convert("L").resize(MINIMAP_SIZE, Image.Resampling.LANCZOS)

    # Subdued terrain keeps markers readable while retaining the custom world.
    relief = ImageOps.autocontrast(height, cutoff=1)
    relief = ImageEnhance.Contrast(relief).enhance(1.25)
    land_colour = ImageOps.colorize(relief, black=(57, 72, 69), white=(184, 171, 126))
    water = Image.new("RGB", MINIMAP_SIZE, (8, 24, 47))
    water_glow = ImageOps.colorize(height, black=(4, 15, 34), white=(12, 34, 61))
    water = Image.blend(water, water_glow, 0.28)
    result = Image.composite(land_colour, water, land)

    land_binary = land.point(lambda value: 255 if value >= 96 else 0)
    eroded_land = land_binary.filter(ImageFilter.MinFilter(3))
    coast = ImageChops.subtract(land_binary, eroded_land)
    coast_colour = Image.new("RGB", MINIMAP_SIZE, (150, 174, 158))
    result = Image.composite(coast_colour, result, coast.point(lambda value: value // 2))
    return result.convert("RGBA")


def _brushed_surface(size: tuple[int, int], mask: Image.Image) -> Image.Image:
    output = Image.new("RGBA", size, (0, 0, 0, 0))
    pixels = output.load()
    alpha = mask.load()
    height_span = max(1, size[1] - 1)
    for y in range(size[1]):
        shade = 32 - round(14 * y / height_span)
        for x in range(size[0]):
            if not alpha[x, y]:
                continue
            grain = ((x * 19 + y * 43 + (x ^ (y * 11))) % 7) - 3
            brush = 2 if (x // 23 + y // 2) % 13 == 0 else 0
            pixels[x, y] = (
                max(0, shade - 4 + grain + brush),
                max(0, shade + grain + brush),
                max(0, shade + 4 + grain + brush),
                255,
            )
    output.putalpha(mask)
    return output


def _chamfered_mask(size: tuple[int, int], chamfer: int = 5) -> Image.Image:
    width, height = size
    mask = Image.new("L", size, 0)
    ImageDraw.Draw(mask).polygon(
        (
            (chamfer, 0),
            (width - chamfer - 1, 0),
            (width - 1, chamfer),
            (width - 1, height - chamfer - 1),
            (width - chamfer - 1, height - 1),
            (chamfer, height - 1),
            (0, height - chamfer - 1),
            (0, chamfer),
        ),
        fill=255,
    )
    return mask


def _minimap_border() -> Image.Image:
    size = OUTPUT_SIZES[MINIMAP_BORDER_PATH]
    outer_mask = _chamfered_mask(size, 5)
    inner_mask = Image.new("L", size, 0)
    ImageDraw.Draw(inner_mask).rounded_rectangle((5, 5, 270, 99), radius=2, fill=255)
    frame_mask = ImageChops.subtract(outer_mask, inner_mask)
    output = _brushed_surface(size, frame_mask)
    draw = ImageDraw.Draw(output)
    outer = ((5, 0), (270, 0), (275, 5), (275, 99), (270, 104), (5, 104), (0, 99), (0, 5), (5, 0))
    inner = ((7, 4), (268, 4), (271, 7), (271, 97), (268, 100), (7, 100), (4, 97), (4, 7), (7, 4))
    draw.line(outer, fill=BLACK, width=2)
    draw.line(inner, fill=STEEL, width=1)
    draw.line(((7, 101), (268, 101)), fill=CYAN_DARK, width=2)
    draw.line(((12, 100), (263, 100)), fill=CYAN, width=1)
    draw.line(((7, 3), (268, 3)), fill=STEEL_SOFT, width=1)
    for x, y in ((6, 6), (269, 6), (6, 98), (269, 98)):
        draw.ellipse((x - 1, y - 1, x + 1, y + 1), fill=BLACK)
        draw.point((x, y), fill=BRASS)
    output.putalpha(frame_mask)
    return output


def _minimap_handle(pinged: bool) -> Image.Image:
    size = OUTPUT_SIZES[MINIMAP_HANDLE_PATH]
    mask = Image.new("L", size, 0)
    ImageDraw.Draw(mask).polygon(((8, 0), (23, 0), (23, 63), (5, 63), (1, 58), (1, 18)), fill=255)
    output = _brushed_surface(size, mask)
    draw = ImageDraw.Draw(output)
    draw.line(((8, 1), (22, 1), (22, 62), (5, 62), (2, 58), (2, 18), (8, 1)), fill=BLACK, width=2)
    draw.line(((6, 59), (19, 59)), fill=CYAN if pinged else CYAN_DARK, width=2)
    draw.line(((20, 5), (20, 55)), fill=CYAN_SOFT if pinged else STEEL_SOFT, width=1)
    accent = BRASS if pinged else STEEL
    for y in (27, 32, 37):
        draw.line(((7, y), (12, y - 4), (12, y + 4), (7, y)), fill=accent, width=1)
    return output


def _draw_shield(draw: ImageDraw.ImageDraw, cx: int, cy: int, colour: tuple[int, int, int, int]) -> None:
    draw.polygon(((cx, cy - 7), (cx + 7, cy - 4), (cx + 5, cy + 4), (cx, cy + 8), (cx - 5, cy + 4), (cx - 7, cy - 4)), fill=colour)
    draw.line(((cx, cy - 4), (cx, cy + 5)), fill=(230, 234, 226, 255), width=1)


def _draw_crossed_blades(draw: ImageDraw.ImageDraw, cx: int, cy: int, colour: tuple[int, int, int, int]) -> None:
    draw.line(((cx - 7, cy - 7), (cx + 7, cy + 7)), fill=colour, width=2)
    draw.line(((cx + 7, cy - 7), (cx - 7, cy + 7)), fill=colour, width=2)
    draw.line(((cx - 8, cy + 5), (cx - 5, cy + 8)), fill=PALE, width=1)
    draw.line(((cx + 8, cy + 5), (cx + 5, cy + 8)), fill=PALE, width=1)


def _ping_button(kind: str) -> Image.Image:
    output = Image.new("RGBA", (64, 31), (0, 0, 0, 0))
    for frame in range(2):
        left = frame * 32
        draw = ImageDraw.Draw(output)
        fill = (10, 16, 18, 255) if frame == 0 else (17, 27, 29, 255)
        rim = STEEL_SOFT if frame == 0 else CYAN
        draw.ellipse((left + 2, 1, left + 30, 29), fill=BLACK, outline=STEEL, width=1)
        draw.ellipse((left + 5, 4, left + 27, 26), fill=fill, outline=rim, width=1)
        if kind == "offensive":
            _draw_crossed_blades(draw, left + 16, 15, RED if frame == 0 else BRASS)
        else:
            _draw_shield(draw, left + 16, 15, CYAN_SOFT if frame == 0 else CYAN)
    return output


def _mapmode_main_background() -> Image.Image:
    size = OUTPUT_SIZES[MAPMODE_MAIN_BG_PATH]
    mask = _chamfered_mask(size, 7)
    output = _brushed_surface(size, mask)
    draw = ImageDraw.Draw(output)
    draw.line(((7, 1), (79, 1), (85, 7), (85, 198), (79, 204), (7, 204), (1, 198), (1, 7), (7, 1)), fill=BLACK, width=2)
    draw.line(((6, 4), (77, 4)), fill=STEEL, width=1)
    draw.line(((3, 9), (3, 194)), fill=CYAN_DARK, width=2)
    draw.line(((4, 12), (4, 191)), fill=CYAN_SOFT, width=1)
    draw.line(((55, 6), (55, 199)), fill=BLACK, width=2)
    draw.line(((57, 8), (57, 197)), fill=STEEL_SOFT, width=1)
    for y in (35, 82, 129, 176):
        draw.line(((8, y), (51, y)), fill=BLACK, width=1)
    for y in (31, 58, 85, 112, 139, 166):
        draw.line(((60, y), (82, y)), fill=(28, 37, 39, 255), width=1)
    for x, y in ((8, 8), (77, 8), (8, 196), (77, 196)):
        draw.ellipse((x - 1, y - 1, x + 1, y + 1), fill=BLACK)
        draw.point((x, y), fill=BRASS)
    return output


def _mapmode_bottom_background() -> Image.Image:
    size = OUTPUT_SIZES[MAPMODE_BOTTOM_BG_PATH]
    mask = _chamfered_mask(size, 7)
    output = _brushed_surface(size, mask)
    draw = ImageDraw.Draw(output)
    draw.line(((1, 0), (84, 0)), fill=BLACK, width=2)
    draw.line(((3, 3), (82, 3)), fill=STEEL_SOFT, width=1)
    draw.line(((3, 4), (3, 49), (9, 56), (77, 56), (84, 49)), fill=BLACK, width=2)
    draw.line(((4, 6), (4, 47)), fill=CYAN_DARK, width=2)
    draw.line(((8, 55), (78, 55)), fill=CYAN, width=1)
    draw.line(((57, 4), (57, 51)), fill=STEEL_SOFT, width=1)
    return output


def _mapmode_big_socket() -> Image.Image:
    size = OUTPUT_SIZES[MAPMODE_BIG_BG_PATH]
    output = Image.new("RGBA", size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(output)
    # The La Resistance layout places these 51px textures only 36-37px apart.
    # Keep the engine canvas and hitboxes intact, but confine visible pixels to
    # a 35px socket so adjacent controls never paint over one another.
    draw.ellipse((3, 8, 38, 42), fill=BLACK, outline=STEEL_SOFT, width=1)
    draw.ellipse((6, 11, 35, 39), fill=DEEP, outline=STEEL, width=1)
    draw.arc((8, 13, 33, 37), 200, 338, fill=CYAN_DARK, width=2)
    draw.point((20, 9), fill=BRASS)
    return output


def _mapmode_small_socket() -> Image.Image:
    size = OUTPUT_SIZES[MAPMODE_SMALL_BG_PATH]
    output = Image.new("RGBA", size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(output)
    draw.rounded_rectangle((1, 1, 21, 18), radius=6, fill=BLACK, outline=STEEL_SOFT, width=1)
    draw.ellipse((4, 2, 19, 17), fill=DEEP, outline=(62, 73, 75, 255), width=1)
    return output


def _round_button_strip(
    size: tuple[int, int],
    glyph: Callable[[ImageDraw.ImageDraw, int, int, tuple[int, int, int, int]], None],
    *,
    frame_width: int,
) -> Image.Image:
    output = Image.new("RGBA", size, (0, 0, 0, 0))
    for frame in range(size[0] // frame_width):
        left = frame * frame_width
        draw = ImageDraw.Draw(output)
        draw.ellipse((left + 1, 1, left + frame_width - 2, size[1] - 2), fill=BLACK, outline=STEEL, width=1)
        draw.ellipse((left + 3, 3, left + frame_width - 4, size[1] - 4), fill=DEEP, outline=STEEL_SOFT, width=1)
        if frame:
            draw.arc((left + 3, 3, left + frame_width - 4, size[1] - 4), 195, 340, fill=CYAN, width=1)
        glyph(draw, left + frame_width // 2, size[1] // 2, CYAN if frame else PALE)
    return output


def _draw_search(draw: ImageDraw.ImageDraw, cx: int, cy: int, colour: tuple[int, int, int, int]) -> None:
    draw.ellipse((cx - 6, cy - 7, cx + 4, cy + 3), outline=colour, width=2)
    draw.line(((cx + 3, cy + 2), (cx + 9, cy + 8)), fill=BRASS, width=2)
    draw.line(((cx - 3, cy - 2), (cx + 1, cy - 2)), fill=CYAN_SOFT, width=1)


def _draw_layers(draw: ImageDraw.ImageDraw, cx: int, cy: int, colour: tuple[int, int, int, int]) -> None:
    draw.polygon(((cx, cy - 6), (cx + 7, cy - 2), (cx, cy + 2), (cx - 7, cy - 2)), outline=colour)
    draw.line(((cx - 6, cy + 1), (cx, cy + 5), (cx + 6, cy + 1)), fill=colour, width=1)


def _draw_gear(draw: ImageDraw.ImageDraw, cx: int, cy: int, colour: tuple[int, int, int, int]) -> None:
    draw.ellipse((cx - 5, cy - 5, cx + 5, cy + 5), outline=colour, width=2)
    draw.ellipse((cx - 1, cy - 1, cx + 1, cy + 1), fill=BRASS)
    for dx, dy in ((0, -7), (0, 7), (-7, 0), (7, 0)):
        draw.line(((cx + dx, cy + dy), (cx + dx // 2, cy + dy // 2)), fill=colour, width=2)


def _find_button() -> Image.Image:
    return _round_button_strip((39, 39), _draw_search, frame_width=39)


def _two_state_button(size: tuple[int, int], glyph: Callable[[ImageDraw.ImageDraw, int, int, tuple[int, int, int, int]], None]) -> Image.Image:
    return _round_button_strip(size, glyph, frame_width=size[0] // 2)


def _configure_background() -> Image.Image:
    output = Image.new("RGBA", OUTPUT_SIZES[MAPMODE_CONFIGURE_BG_PATH], (0, 0, 0, 0))
    for frame in range(3):
        left = frame * 173
        mask = _chamfered_mask((173, 23), 5)
        panel = _brushed_surface((173, 23), mask)
        draw = ImageDraw.Draw(panel)
        draw.line(((5, 1), (167, 1), (171, 5)), fill=STEEL, width=1)
        draw.line(((6, 20), (166, 20)), fill=CYAN if frame == 1 else CYAN_DARK, width=2)
        for x in (8, 164):
            draw.point((x, 5), fill=BRASS)
        output.alpha_composite(panel, (left, 0))
    return output


def _draw_person(draw: ImageDraw.ImageDraw, cx: int, cy: int, colour: tuple[int, int, int, int]) -> None:
    draw.ellipse((cx - 3, cy - 9, cx + 3, cy - 3), fill=colour)
    draw.polygon(((cx - 7, cy + 8), (cx - 5, cy - 1), (cx, cy - 3), (cx + 5, cy - 1), (cx + 7, cy + 8)), fill=colour)
    draw.line(((cx - 4, cy + 1), (cx + 4, cy + 1)), fill=CYAN_DARK, width=1)


def _draw_plane(draw: ImageDraw.ImageDraw, cx: int, cy: int, colour: tuple[int, int, int, int]) -> None:
    draw.polygon(((cx, cy - 10), (cx + 2, cy - 3), (cx + 9, cy), (cx + 9, cy + 2), (cx + 2, cy + 1), (cx + 2, cy + 7), (cx + 5, cy + 9), (cx + 5, cy + 10), (cx, cy + 8), (cx - 5, cy + 10), (cx - 5, cy + 9), (cx - 2, cy + 7), (cx - 2, cy + 1), (cx - 9, cy + 2), (cx - 9, cy), (cx - 2, cy - 3)), fill=colour)


def _draw_anchor(draw: ImageDraw.ImageDraw, cx: int, cy: int, colour: tuple[int, int, int, int]) -> None:
    draw.ellipse((cx - 3, cy - 10, cx + 3, cy - 4), outline=colour, width=2)
    draw.line(((cx, cy - 4), (cx, cy + 7)), fill=colour, width=2)
    draw.line(((cx - 6, cy - 1), (cx + 6, cy - 1)), fill=colour, width=2)
    draw.arc((cx - 9, cy - 2, cx + 9, cy + 10), 10, 170, fill=colour, width=2)


def _draw_eye(draw: ImageDraw.ImageDraw, cx: int, cy: int, colour: tuple[int, int, int, int]) -> None:
    draw.arc((cx - 9, cy - 6, cx + 9, cy + 6), 200, 340, fill=colour, width=2)
    draw.arc((cx - 9, cy - 6, cx + 9, cy + 6), 20, 160, fill=colour, width=2)
    draw.ellipse((cx - 2, cy - 2, cx + 2, cy + 2), fill=BRASS)


def _big_mapmode_strip(selected: bool) -> Image.Image:
    output = Image.new("RGBA", (136, 31), (0, 0, 0, 0))
    glyphs = (_draw_person, _draw_plane, _draw_anchor, _draw_eye)
    colour = PALE if selected else (131, 142, 140, 245)
    for frame, glyph in enumerate(glyphs):
        left = frame * 34
        draw = ImageDraw.Draw(output)
        if selected:
            draw.arc((left + 3, 1, left + 30, 28), 200, 338, fill=CYAN, width=2)
        glyph(draw, left + 17, 15, colour)
    return output


def _draw_question(draw: ImageDraw.ImageDraw, cx: int, cy: int, colour: tuple[int, int, int, int]) -> None:
    draw.arc((cx - 4, cy - 6, cx + 4, cy + 1), 185, 355, fill=colour, width=2)
    draw.line(((cx + 3, cy - 1), (cx, cy + 3)), fill=colour, width=1)
    draw.point((cx, cy + 6), fill=BRASS)


def _draw_flag(draw: ImageDraw.ImageDraw, cx: int, cy: int, colour: tuple[int, int, int, int]) -> None:
    draw.line(((cx - 5, cy - 6), (cx - 5, cy + 6)), fill=colour, width=1)
    draw.polygon(((cx - 4, cy - 5), (cx + 5, cy - 3), (cx - 4, cy)), fill=colour)


def _draw_document(draw: ImageDraw.ImageDraw, cx: int, cy: int, colour: tuple[int, int, int, int]) -> None:
    draw.rectangle((cx - 5, cy - 6, cx + 5, cy + 6), outline=colour)
    for y in (-3, 0, 3):
        draw.line(((cx - 3, cy + y), (cx + 3, cy + y)), fill=colour, width=1)


def _draw_flame(draw: ImageDraw.ImageDraw, cx: int, cy: int, colour: tuple[int, int, int, int]) -> None:
    draw.polygon(((cx, cy - 7), (cx + 4, cy - 1), (cx + 3, cy + 5), (cx, cy + 7), (cx - 4, cy + 4), (cx - 3, cy - 1)), fill=colour)
    draw.polygon(((cx, cy - 1), (cx + 2, cy + 3), (cx, cy + 5), (cx - 2, cy + 3)), fill=BRASS)


def _draw_radio(draw: ImageDraw.ImageDraw, cx: int, cy: int, colour: tuple[int, int, int, int]) -> None:
    draw.polygon(((cx - 7, cy - 2), (cx + 4, cy - 6), (cx + 4, cy + 4), (cx - 7, cy)), fill=colour)
    draw.line(((cx - 5, cy), (cx - 3, cy + 6)), fill=colour, width=2)


def _draw_tag(draw: ImageDraw.ImageDraw, cx: int, cy: int, colour: tuple[int, int, int, int]) -> None:
    draw.polygon(((cx - 7, cy - 3), (cx + 2, cy - 5), (cx + 7, cy), (cx + 2, cy + 5), (cx - 7, cy + 3)), outline=colour)
    draw.point((cx - 3, cy), fill=BRASS)


def _draw_star(draw: ImageDraw.ImageDraw, cx: int, cy: int, colour: tuple[int, int, int, int]) -> None:
    points = ((cx, cy - 7), (cx + 2, cy - 2), (cx + 7, cy - 2), (cx + 3, cy + 1), (cx + 5, cy + 6), (cx, cy + 3), (cx - 5, cy + 6), (cx - 3, cy + 1), (cx - 7, cy - 2), (cx - 2, cy - 2))
    draw.polygon(points, fill=colour)


def _draw_people(draw: ImageDraw.ImageDraw, cx: int, cy: int, colour: tuple[int, int, int, int]) -> None:
    draw.ellipse((cx - 6, cy - 6, cx - 2, cy - 2), fill=colour)
    draw.ellipse((cx + 2, cy - 6, cx + 6, cy - 2), fill=colour)
    draw.polygon(((cx - 8, cy + 6), (cx - 6, cy), (cx - 2, cy), (cx, cy + 6)), fill=colour)
    draw.polygon(((cx, cy + 6), (cx + 2, cy), (cx + 6, cy), (cx + 8, cy + 6)), fill=colour)


def _draw_binoculars(draw: ImageDraw.ImageDraw, cx: int, cy: int, colour: tuple[int, int, int, int]) -> None:
    draw.ellipse((cx - 8, cy - 4, cx - 1, cy + 5), outline=colour, width=2)
    draw.ellipse((cx + 1, cy - 4, cx + 8, cy + 5), outline=colour, width=2)
    draw.line(((cx - 1, cy - 2), (cx + 1, cy - 2)), fill=colour, width=2)


def _draw_globe(draw: ImageDraw.ImageDraw, cx: int, cy: int, colour: tuple[int, int, int, int]) -> None:
    draw.ellipse((cx - 7, cy - 7, cx + 7, cy + 7), outline=colour, width=1)
    draw.arc((cx - 4, cy - 7, cx + 4, cy + 7), 90, 270, fill=colour)
    draw.arc((cx - 4, cy - 7, cx + 4, cy + 7), 270, 90, fill=colour)
    draw.line(((cx - 6, cy), (cx + 6, cy)), fill=colour, width=1)


def _draw_mountains(draw: ImageDraw.ImageDraw, cx: int, cy: int, colour: tuple[int, int, int, int]) -> None:
    draw.polygon(((cx - 8, cy + 6), (cx - 2, cy - 6), (cx + 2, cy + 1), (cx + 5, cy - 4), (cx + 9, cy + 6)), outline=colour)


def _draw_target(draw: ImageDraw.ImageDraw, cx: int, cy: int, colour: tuple[int, int, int, int]) -> None:
    draw.ellipse((cx - 6, cy - 6, cx + 6, cy + 6), outline=colour)
    draw.line(((cx - 8, cy), (cx + 8, cy)), fill=colour)
    draw.line(((cx, cy - 8), (cx, cy + 8)), fill=colour)
    draw.point((cx, cy), fill=BRASS)


def _draw_grid(draw: ImageDraw.ImageDraw, cx: int, cy: int, colour: tuple[int, int, int, int]) -> None:
    draw.rectangle((cx - 6, cy - 6, cx + 6, cy + 6), outline=colour)
    draw.line(((cx, cy - 6), (cx, cy + 6)), fill=colour)
    draw.line(((cx - 6, cy), (cx + 6, cy)), fill=colour)


def _small_mapmode_strip(selected: bool) -> Image.Image:
    output = Image.new("RGBA", (360, 18), (0, 0, 0, 0))
    glyphs = (
        _draw_question,
        _draw_grid,
        _draw_layers,
        _draw_eye,
        _draw_flag,
        _draw_document,
        _draw_flame,
        _draw_radio,
        _draw_tag,
        _draw_plane,
        _draw_star,
        _draw_people,
        _draw_flame,
        _draw_binoculars,
        _draw_globe,
        _draw_mountains,
        _draw_target,
        _draw_search,
    )
    colour = PALE if selected else (127, 138, 136, 240)
    for frame, glyph in enumerate(glyphs):
        left = frame * 20
        draw = ImageDraw.Draw(output)
        if selected:
            draw.arc((left + 1, 0, left + 18, 17), 200, 338, fill=CYAN, width=1)
        glyph(draw, left + 10, 9, colour)
    return output


def _draw_moon(draw: ImageDraw.ImageDraw, cx: int, cy: int, colour: tuple[int, int, int, int]) -> None:
    draw.ellipse((cx - 6, cy - 6, cx + 5, cy + 5), fill=colour)
    draw.ellipse((cx - 2, cy - 7, cx + 7, cy + 2), fill=DEEP)
    draw.point((cx + 6, cy - 5), fill=BRASS)


def _draw_radar(draw: ImageDraw.ImageDraw, cx: int, cy: int, colour: tuple[int, int, int, int]) -> None:
    draw.line(((cx, cy + 6), (cx, cy - 4)), fill=colour, width=1)
    draw.line(((cx - 5, cy + 6), (cx + 5, cy + 6)), fill=colour, width=1)
    draw.arc((cx - 7, cy - 7, cx + 7, cy + 5), 210, 330, fill=colour, width=1)
    draw.line(((cx, cy - 3), (cx + 5, cy - 6)), fill=BRASS, width=1)


def _draw_arrows(draw: ImageDraw.ImageDraw, cx: int, cy: int, colour: tuple[int, int, int, int]) -> None:
    draw.line(((cx - 7, cy + 4), (cx + 4, cy - 5)), fill=colour, width=2)
    draw.polygon(((cx + 4, cy - 5), (cx + 3, cy + 1), (cx + 8, cy - 6)), fill=colour)
    draw.line(((cx - 4, cy + 7), (cx + 7, cy - 2)), fill=BRASS, width=1)


def _draw_counter(draw: ImageDraw.ImageDraw, cx: int, cy: int, colour: tuple[int, int, int, int]) -> None:
    draw.ellipse((cx - 2, cy - 6, cx + 2, cy - 2), fill=colour)
    draw.polygon(((cx - 5, cy + 6), (cx - 3, cy - 1), (cx + 3, cy - 1), (cx + 5, cy + 6)), fill=colour)


def expected_outputs() -> dict[Path, bytes]:
    return {
        MINIMAP_PATH: _dds_bytes(_minimap()),
        MINIMAP_BORDER_PATH: _dds_bytes(_minimap_border()),
        MINIMAP_HANDLE_PATH: _dds_bytes(_minimap_handle(False)),
        MINIMAP_HANDLE_PINGED_PATH: _dds_bytes(_minimap_handle(True)),
        MINIMAP_OFFENSIVE_PATH: _dds_bytes(_ping_button("offensive")),
        MINIMAP_DEFENSIVE_PATH: _dds_bytes(_ping_button("defensive")),
        MINIMAP_QUAD_PATH: _dds_bytes(Image.new("RGBA", (2, 2), CYAN)),
        MAPMODE_MAIN_BG_PATH: _dds_bytes(_mapmode_main_background()),
        MAPMODE_BOTTOM_BG_PATH: _dds_bytes(_mapmode_bottom_background()),
        MAPMODE_BIG_BG_PATH: _dds_bytes(_mapmode_big_socket()),
        MAPMODE_SMALL_BG_PATH: _dds_bytes(_mapmode_small_socket()),
        MAPMODE_FIND_PATH: _dds_bytes(_find_button()),
        MAPMODE_ALL_PATH: _dds_bytes(_two_state_button((44, 21), _draw_layers)),
        MAPMODE_CONFIGURE_PATH: _dds_bytes(_two_state_button((44, 21), _draw_gear)),
        MAPMODE_CONFIGURE_BG_PATH: _dds_bytes(_configure_background()),
        MAPMODE_BIG_SELECTED_PATH: _dds_bytes(_big_mapmode_strip(True)),
        MAPMODE_BIG_DESELECTED_PATH: _dds_bytes(_big_mapmode_strip(False)),
        MAPMODE_SMALL_SELECTED_PATH: _dds_bytes(_small_mapmode_strip(True)),
        MAPMODE_SMALL_DESELECTED_PATH: _dds_bytes(_small_mapmode_strip(False)),
        MAPMODE_DAY_NIGHT_PATH: _dds_bytes(_two_state_button((44, 22), _draw_moon)),
        MAPMODE_FOG_PATH: _dds_bytes(_two_state_button((44, 22), _draw_eye)),
        MAPMODE_RADAR_PATH: _dds_bytes(_two_state_button((44, 22), _draw_radar)),
        MAPMODE_ALLIED_PLANS_PATH: _dds_bytes(_two_state_button((44, 22), _draw_arrows)),
        MAPMODE_COUNTERS_PATH: _dds_bytes(_two_state_button((44, 22), _draw_counter)),
        MAPMODE_COUNTER_COLOUR_PATH: _dds_bytes(_two_state_button((44, 22), _draw_flag)),
    }


def expected_bytes() -> bytes:
    """Retain the former single-output API for downstream callers."""
    return expected_outputs()[MINIMAP_PATH]


def _dds_bytes(image: Image.Image) -> bytes:
    stream = BytesIO()
    image.save(stream, format="DDS")
    return stream.getvalue()


def validate(outputs: dict[Path, bytes] | bytes) -> list[str]:
    if isinstance(outputs, bytes):
        outputs = {MINIMAP_PATH: outputs}
    issues: list[str] = []
    for path, expected in outputs.items():
        relative = path.relative_to(ROOT)
        if not path.is_file():
            issues.append(f"missing generated lower-HUD asset: {relative}")
            continue
        if path.read_bytes() != expected:
            issues.append(f"generated lower-HUD asset differs: {relative}")
            continue
        with Image.open(path) as image:
            expected_size = OUTPUT_SIZES[path]
            if image.size != expected_size:
                issues.append(
                    f"generated lower-HUD asset {relative} has size {image.size}, expected {expected_size}"
                )
    return issues


def apply(outputs: dict[Path, bytes]) -> None:
    for path, data in outputs.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_mutually_exclusive_group()
    actions.add_argument("--check", action="store_true", help="compare outputs (default)")
    actions.add_argument("--apply", action="store_true", help="write generated lower-HUD assets")
    args = parser.parse_args()

    try:
        outputs = expected_outputs()
        if args.apply:
            apply(outputs)
        issues = validate(outputs)
    except (OSError, RuntimeError) as exc:
        print(f"ERROR: {exc}")
        return 1

    if issues:
        for issue in issues:
            print(f"ERROR: {issue}")
        return 1
    print("A-Discord lower-right HUD is current (custom minimap, gunmetal/cyan map-mode dock).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
