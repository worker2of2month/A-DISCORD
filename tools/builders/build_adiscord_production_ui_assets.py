#!/usr/bin/env python3
"""Build the original A-Discord production-window surface set.

The checked-in source is original project art.  This builder crops that
material and draws the fixed Clausewitz panels, nine-slice borders, factory
slots, and naval row variants deterministically.  Check mode is the default;
use ``--apply`` only after inspecting the planned output.
"""

from __future__ import annotations

import argparse
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageEnhance, ImageFilter, ImageOps

from tools.lib.paths import repository_root


ROOT = repository_root()
SOURCE = ROOT / "gfx/interface/production/source/production_surface_source.png"
SOURCE_DIR = ROOT / "gfx/interface/production/source"
FACTORY_GLYPH_SOURCE = SOURCE_DIR / "factory_glyph_source.png"
BUTTON_GLYPH_SOURCES = {
    "infantry_artillery": SOURCE_DIR / "infantry_artillery_glyph_source.png",
    "armour": SOURCE_DIR / "armour_glyph_source.png",
    "aircraft": SOURCE_DIR / "aircraft_glyph_source.png",
    "naval": SOURCE_DIR / "naval_glyph_source.png",
    "repair": SOURCE_DIR / "repair_glyph_source.png",
}
OUTPUT_DIR = ROOT / "gfx/interface/production/ui"

WINDOW_TILE = OUTPUT_DIR / "ADISCORD_production_window_tile.dds"
LINES_TILE = OUTPUT_DIR / "ADISCORD_production_lines_tile.dds"
LINES_OVERLAY = OUTPUT_DIR / "ADISCORD_production_lines_overlay.dds"
TOP_PANEL = OUTPUT_DIR / "ADISCORD_production_top_panel.dds"
MILITARY_ITEM = OUTPUT_DIR / "ADISCORD_production_military_item.dds"
COLLAPSED_ITEM = OUTPUT_DIR / "ADISCORD_production_collapsed_item.dds"
NAVAL_ITEM_STRIP = OUTPUT_DIR / "ADISCORD_production_naval_item_strip.dds"
CONSUMER_ITEM = OUTPUT_DIR / "ADISCORD_production_consumer_item.dds"
EQUIPMENT_CARD = OUTPUT_DIR / "ADISCORD_production_equipment_card.dds"
FACTORY_ICON_STRIP = OUTPUT_DIR / "ADISCORD_production_factory_icon_strip.dds"
FACTORY_HALF_STRIP = OUTPUT_DIR / "ADISCORD_production_factory_half_strip.dds"
FACTORY_SLOT_BG = OUTPUT_DIR / "ADISCORD_production_factory_slot_bg.dds"
ADD_INFANTRY_BUTTON = OUTPUT_DIR / "ADISCORD_production_add_infantry_button.dds"
ADD_ARMOUR_BUTTON = OUTPUT_DIR / "ADISCORD_production_add_armour_button.dds"
ADD_AIRCRAFT_BUTTON = OUTPUT_DIR / "ADISCORD_production_add_aircraft_button.dds"
ADD_NAVAL_BUTTON = OUTPUT_DIR / "ADISCORD_production_add_naval_button.dds"
NAVAL_REPAIR_BUTTON = OUTPUT_DIR / "ADISCORD_production_naval_repair_button.dds"

INK = (3, 5, 6, 255)
DEEP = (8, 11, 12, 255)
RECESS = (11, 15, 16, 255)
EDGE = (50, 58, 60, 255)
EDGE_LIGHT = (92, 101, 99, 255)
BRASS = (114, 88, 45, 255)
BRASS_LIGHT = (158, 124, 62, 255)
OXIDE = (55, 70, 67, 255)
OLIVE = (48, 61, 39, 255)
NAVAL = (42, 61, 70, 255)


def _source_image() -> Image.Image:
    if not SOURCE.is_file():
        raise RuntimeError(f"missing production surface source: {SOURCE.relative_to(ROOT)}")
    with Image.open(SOURCE) as source_image:
        source = source_image.convert("RGBA")
    if source.width < 1024 or source.height < 1024:
        raise RuntimeError(f"production source must be at least 1024x1024, got {source.size}")
    return source


def _glyph_source(path: Path, max_size: tuple[int, int]) -> Image.Image:
    if not path.is_file():
        raise RuntimeError(f"missing production glyph source: {path.relative_to(ROOT)}")
    with Image.open(path) as source_image:
        source = source_image.convert("RGBA")
    alpha = source.getchannel("A")
    bbox = alpha.getbbox()
    if bbox is None:
        raise RuntimeError(f"production glyph source is fully transparent: {path.relative_to(ROOT)}")
    if any(
        alpha.getpixel(point) != 0
        for point in (
            (0, 0),
            (source.width - 1, 0),
            (0, source.height - 1),
            (source.width - 1, source.height - 1),
        )
    ):
        raise RuntimeError(f"production glyph source corners must be transparent: {path.relative_to(ROOT)}")
    glyph = source.crop(bbox)
    glyph.thumbnail(max_size, Image.Resampling.LANCZOS)
    return glyph


def _surface(
    size: tuple[int, int],
    centering: tuple[float, float],
    brightness: float,
    contrast: float = 0.90,
) -> Image.Image:
    source = ImageOps.fit(
        _source_image(),
        size,
        method=Image.Resampling.LANCZOS,
        centering=centering,
    )
    source = ImageEnhance.Contrast(source).enhance(contrast)
    source = ImageEnhance.Color(source).enhance(0.58)
    source = ImageEnhance.Brightness(source).enhance(brightness)
    source.putalpha(255)
    return source


def _tinted_surface(
    size: tuple[int, int],
    centering: tuple[float, float],
    brightness: float,
    shadow: tuple[int, int, int],
    highlight: tuple[int, int, int],
) -> Image.Image:
    base = _surface(size, centering, brightness)
    luminance = ImageOps.grayscale(base.convert("RGB"))
    tint = ImageOps.colorize(luminance, black=shadow, white=highlight).convert("RGBA")
    tint.putalpha(255)
    return Image.blend(base, tint, 0.68)


def _rivet(draw: ImageDraw.ImageDraw, x: int, y: int) -> None:
    draw.ellipse((x - 3, y - 3, x + 3, y + 3), fill=INK, outline=EDGE, width=1)
    draw.point((x - 1, y - 1), fill=EDGE_LIGHT)
    draw.point((x + 1, y + 1), fill=(9, 11, 11, 255))


def _outer_frame(image: Image.Image, box: tuple[int, int, int, int], width: int = 4) -> None:
    draw = ImageDraw.Draw(image, "RGBA")
    left, top, right, bottom = box
    draw.rectangle(box, outline=INK, width=width)
    draw.rectangle((left + width, top + width, right - width, bottom - width), outline=EDGE, width=1)
    draw.line((left + 7, top + 6, right - 7, top + 6), fill=(116, 125, 120, 85), width=1)
    draw.line((left + 7, bottom - 6, right - 7, bottom - 6), fill=(99, 72, 35, 145), width=1)


def _recess(image: Image.Image, box: tuple[int, int, int, int], tint: tuple[int, int, int, int] = RECESS) -> None:
    draw = ImageDraw.Draw(image, "RGBA")
    left, top, right, bottom = box
    draw.rectangle(box, fill=tint, outline=INK, width=2)
    draw.line((left + 2, top + 2, right - 2, top + 2), fill=(0, 0, 0, 185), width=1)
    draw.line((left + 2, bottom - 2, right - 2, bottom - 2), fill=EDGE, width=1)


def _window_tile() -> Image.Image:
    output = _surface((192, 192), (0.43, 0.58), 0.82)
    draw = ImageDraw.Draw(output, "RGBA")
    draw.rectangle((0, 0, 191, 191), outline=INK, width=6)
    draw.rectangle((6, 6, 185, 185), outline=EDGE, width=2)
    draw.rectangle((10, 10, 181, 181), outline=(18, 23, 24, 255), width=3)
    draw.line((12, 12, 179, 12), fill=(122, 133, 128, 72), width=1)
    draw.line((12, 179, 179, 179), fill=(117, 81, 37, 115), width=1)
    for point in ((17, 17), (174, 17), (17, 174), (174, 174)):
        _rivet(draw, *point)
    return output


def _lines_tile() -> Image.Image:
    output = _tinted_surface((192, 192), (0.62, 0.47), 0.72, (5, 8, 9), (45, 55, 55))
    draw = ImageDraw.Draw(output, "RGBA")
    draw.rectangle((0, 0, 191, 191), outline=INK, width=6)
    draw.rectangle((6, 6, 185, 185), outline=(66, 75, 74, 255), width=2)
    draw.rectangle((11, 11, 180, 180), outline=(14, 19, 20, 255), width=2)
    draw.line((13, 13, 178, 13), fill=(122, 130, 123, 70), width=1)
    draw.line((13, 178, 178, 178), fill=(105, 76, 38, 125), width=1)
    for point in ((18, 18), (173, 18), (18, 173), (173, 173)):
        _rivet(draw, *point)
    return output


def _lines_overlay() -> Image.Image:
    output = Image.new("RGBA", (549, 600), (0, 0, 0, 0))
    draw = ImageDraw.Draw(output, "RGBA")
    # Restrained structural rails replace the oversized ornamental machinery.
    for x in (6, 542):
        draw.line((x, 18, x, 581), fill=(8, 11, 12, 205), width=5)
        draw.line((x + (-3 if x > 200 else 3), 22, x + (-3 if x > 200 else 3), 577), fill=(76, 84, 81, 120), width=1)
    draw.line((18, 8, 531, 8), fill=(7, 10, 11, 210), width=5)
    draw.line((18, 591, 531, 591), fill=(7, 10, 11, 225), width=6)
    draw.line((24, 586, 525, 586), fill=(112, 80, 37, 100), width=1)
    for y in (42, 558):
        for x in (16, 533):
            _rivet(draw, x, y)
    # Small stamped gussets anchor the lower corners without filling the empty list.
    for mirror in (False, True):
        xs = (18, 74, 18) if not mirror else (531, 475, 531)
        draw.polygon(((xs[0], 574), (xs[1], 574), (xs[2], 522)), fill=(19, 25, 26, 145), outline=(61, 70, 69, 135))
        for offset in (12, 24, 36):
            x1 = 20 + offset if not mirror else 529 - offset
            x2 = 20 if not mirror else 529
            draw.line((x1, 570, x2, 532 + offset), fill=(101, 75, 39, 70), width=1)
    return output


def _cell_grid(
    image: Image.Image,
    box: tuple[int, int, int, int],
    columns: int,
    rows: int,
) -> None:
    left, top, right, bottom = box
    _recess(image, box, (6, 8, 9, 246))
    draw = ImageDraw.Draw(image, "RGBA")
    cell_width = (right - left - 4) / columns
    cell_height = (bottom - top - 4) / rows
    for column in range(1, columns):
        x = round(left + 2 + column * cell_width)
        draw.line((x, top + 2, x, bottom - 2), fill=(66, 57, 45, 220), width=1)
    for row in range(1, rows):
        y = round(top + 2 + row * cell_height)
        draw.line((left + 2, y, right - 2, y), fill=(66, 57, 45, 220), width=1)
    for column in range(columns):
        for row in range(rows):
            x = round(left + 5 + column * cell_width)
            y = round(top + 5 + row * cell_height)
            draw.line((x, y, min(right - 3, x + 8), y), fill=(105, 78, 40, 48), width=1)


def _top_panel() -> Image.Image:
    output = _surface((550, 253), (0.54, 0.48), 0.84)
    _outer_frame(output, (0, 0, 549, 252), 5)
    # Resource totals, industrial modifiers, available factories, add-line buttons, filters.
    bands = ((8, 7, 541, 39), (8, 43, 541, 76), (8, 80, 541, 117), (8, 121, 541, 173), (8, 177, 541, 250))
    for box in bands:
        _recess(output, box, (10, 14, 15, 235))
    draw = ImageDraw.Draw(output, "RGBA")
    for column in range(1, 7):
        x = 8 + round(column * 533 / 7)
        draw.line((x, 9, x, 37), fill=(54, 62, 62, 175), width=1)
    for column in range(1, 6):
        x = 8 + round(column * 533 / 6)
        draw.line((x, 45, x, 74), fill=(54, 62, 62, 160), width=1)
        draw.line((x, 179, x, 248), fill=(45, 52, 52, 145), width=1)
    draw.line((275, 82, 275, 115), fill=BRASS, width=1)
    draw.line((10, 118, 539, 118), fill=(133, 96, 43, 135), width=1)
    draw.line((10, 209, 539, 209), fill=(52, 59, 58, 155), width=1)
    for point in ((11, 11), (538, 11), (11, 247), (538, 247)):
        _rivet(draw, *point)
    return output


def _item_base(
    accent_shadow: tuple[int, int, int],
    accent_highlight: tuple[int, int, int],
    factory_rows: int = 3,
) -> Image.Image:
    output = _surface((511, 108), (0.48, 0.63), 0.82)
    _outer_frame(output, (0, 0, 510, 107), 3)
    draw = ImageDraw.Draw(output, "RGBA")
    draw.rectangle((4, 5, 506, 30), fill=(14, 18, 19, 225), outline=(57, 65, 64, 255), width=1)
    draw.line((6, 29, 504, 29), fill=BRASS, width=1)

    equipment = _tinted_surface((284, 72), (0.27, 0.52), 0.88, accent_shadow, accent_highlight)
    output.alpha_composite(equipment, (4, 33))
    draw.rectangle((4, 33, 287, 104), outline=INK, width=2)
    draw.rectangle((7, 36, 284, 101), outline=(65, 75, 70, 255), width=1)
    draw.line((8, 37, 283, 37), fill=(147, 153, 132, 60), width=1)

    draw.rectangle((276, 31, 510, 105), fill=(8, 11, 12, 245), outline=INK, width=2)
    _recess(output, (278, 33, 315, 103), (10, 13, 14, 255))
    if factory_rows == 1:
        grid_box = (317, 44, 461, 66)
    elif factory_rows == 2:
        grid_box = (317, 36, 461, 81)
    else:
        grid_box = (317, 33, 461, 101)
    _cell_grid(output, grid_box, 5, factory_rows)
    _cell_grid(output, (462, 31, 510, 103), 1, 3)
    for point in ((7, 8), (503, 8), (7, 100), (503, 100)):
        _rivet(draw, *point)
    return output


def _military_item() -> Image.Image:
    return _item_base((6, 10, 11), (47, 56, 56), 3)


def _consumer_item() -> Image.Image:
    return _item_base((15, 12, 7), (80, 66, 40), 3)


def _collapsed_item() -> Image.Image:
    output = _surface((512, 60), (0.68, 0.43), 0.79)
    _outer_frame(output, (0, 0, 511, 59), 3)
    draw = ImageDraw.Draw(output, "RGBA")
    draw.rectangle((4, 5, 507, 30), fill=(14, 18, 19, 225), outline=(57, 65, 64, 255), width=1)
    draw.line((6, 29, 505, 29), fill=BRASS, width=1)
    draw.rectangle((4, 33, 507, 56), fill=(9, 12, 13, 225), outline=(41, 49, 49, 255), width=1)
    for point in ((7, 8), (504, 8), (7, 52), (504, 52)):
        _rivet(draw, *point)
    return output


def _naval_item_strip() -> Image.Image:
    output = Image.new("RGBA", (511 * 3, 108), (0, 0, 0, 0))
    for frame, rows in enumerate((1, 2, 3)):
        item = _item_base((6, 11, 15), (49, 70, 79), rows)
        # A slightly colder accent distinguishes dockyard lines from military lines.
        ImageDraw.Draw(item, "RGBA").line((8, 38, 283, 38), fill=(*NAVAL[:3], 155), width=1)
        output.alpha_composite(item, (frame * 511, 0))
    return output


def _equipment_card() -> Image.Image:
    output = _tinted_surface((279, 81), (0.31, 0.56), 0.80, (5, 9, 10), (45, 56, 58))
    draw = ImageDraw.Draw(output, "RGBA")
    draw.rectangle((0, 0, 278, 80), outline=INK, width=3)
    draw.rectangle((3, 3, 275, 77), outline=(65, 75, 74, 255), width=1)
    draw.line((5, 5, 273, 5), fill=(133, 143, 137, 70), width=1)
    draw.line((5, 75, 273, 75), fill=(121, 84, 38, 125), width=1)
    # Subtle drafting marks preserve the technical-card identity without green fill.
    draw.line((28, 15, 28, 65), fill=(91, 107, 108, 36), width=1)
    draw.line((18, 53, 250, 53), fill=(91, 107, 108, 30), width=1)
    draw.arc((15, 18, 75, 78), 190, 312, fill=(111, 125, 123, 34), width=1)
    draw.line((48, 53, 75, 30), fill=(111, 125, 123, 28), width=1)
    for point in ((7, 7), (271, 7), (7, 73), (271, 73)):
        _rivet(draw, *point)
    return output


PIXEL_FONT = {
    "0": ("111", "101", "101", "101", "111"),
    "1": ("010", "110", "010", "010", "111"),
    "5": ("111", "100", "111", "001", "111"),
    "x": ("000", "101", "010", "101", "000"),
}


def _draw_pixel_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    position: tuple[int, int],
    fill: tuple[int, int, int, int],
) -> None:
    x, y = position
    cursor = x
    for character in text:
        pattern = PIXEL_FONT[character]
        for row, pixels in enumerate(pattern):
            for column, pixel in enumerate(pixels):
                if pixel == "1":
                    draw.point((cursor + column, y + row), fill=fill)
        cursor += 4


def _factory_frame(index: int, half: bool) -> Image.Image:
    colours = (
        (188, 147, 68, 255),
        (169, 179, 175, 255),
        (150, 67, 56, 255),
        (72, 79, 78, 235),
        (151, 107, 69, 255),
    )
    glyph = _glyph_source(FACTORY_GLYPH_SOURCE, (20, 16))
    frame = Image.new("RGBA", (22, 18), (0, 0, 0, 0))
    x = (frame.width - glyph.width) // 2
    y = frame.height - glyph.height - 1
    alpha = Image.new("L", frame.size, 0)
    alpha.paste(glyph.getchannel("A"), (x, y))
    if half:
        stripes = Image.new("L", frame.size, 0)
        stripe_draw = ImageDraw.Draw(stripes)
        for offset in range(-18, 40, 6):
            stripe_draw.line((offset, 17, offset + 18, -1), fill=190, width=2)
        alpha = ImageChops.multiply(alpha, stripes)
    outline = alpha.filter(ImageFilter.MaxFilter(3))
    frame.paste((3, 5, 5, 225), (0, 0), outline)
    frame.paste(colours[index % 5], (0, 0), alpha)
    draw = ImageDraw.Draw(frame, "RGBA")
    multiplier = index // 5
    if multiplier:
        label = "x5" if multiplier == 1 else "x10"
        start_x = 12 if multiplier == 1 else 8
        _draw_pixel_text(draw, label, (start_x + 1, 2), (2, 3, 3, 240))
        _draw_pixel_text(draw, label, (start_x, 1), (213, 211, 187, 255))
    return frame


def _factory_strip(half: bool) -> Image.Image:
    output = Image.new("RGBA", (22 * 15, 18), (0, 0, 0, 0))
    for index in range(15):
        output.alpha_composite(_factory_frame(index, half), (index * 22, 0))
    return output


def _factory_slot_bg() -> Image.Image:
    # The line texture now owns the exact 29x23 slot geometry.  Keep only a
    # near-transparent click target here so the old per-slot plate cannot fight it.
    return Image.new("RGBA", (28, 22), (0, 0, 0, 2))


def _button_surface(state: int) -> Image.Image:
    brightness = (0.80, 1.00, 0.61)[state]
    output = _surface((81, 41), (0.34 + state * 0.18, 0.48), brightness)
    if state == 2:
        output = ImageOps.grayscale(output.convert("RGB")).convert("RGBA")
        output.putalpha(255)
    draw = ImageDraw.Draw(output, "RGBA")
    draw.rounded_rectangle((0, 0, 80, 40), radius=2, outline=INK, width=3)
    edge = BRASS_LIGHT if state == 1 else EDGE
    draw.rounded_rectangle((3, 3, 77, 37), radius=1, outline=edge, width=1)
    draw.line((6, 5, 74, 5), fill=(143, 152, 144, 82), width=1)
    draw.line((6, 35, 74, 35), fill=(126, 88, 40, 135), width=1)
    for point in ((6, 6), (74, 6), (6, 34), (74, 34)):
        draw.ellipse((point[0] - 2, point[1] - 2, point[0] + 2, point[1] + 2), fill=INK, outline=EDGE, width=1)
    return output


def _state_glyph(glyph: Image.Image, state: int) -> Image.Image:
    if state == 0:
        return ImageEnhance.Brightness(glyph).enhance(0.88)
    if state == 1:
        return ImageEnhance.Brightness(glyph).enhance(1.15)
    alpha = glyph.getchannel("A").point(lambda value: round(value * 0.52))
    disabled = ImageOps.grayscale(glyph.convert("RGB")).convert("RGBA")
    disabled = ImageEnhance.Brightness(disabled).enhance(0.68)
    disabled.putalpha(alpha)
    return disabled


def _button_frame(key: str, state: int) -> Image.Image:
    frame = _button_surface(state)
    draw = ImageDraw.Draw(frame, "RGBA")
    if key == "repair":
        anchor = _state_glyph(_glyph_source(BUTTON_GLYPH_SOURCES["naval"], (28, 29)), state)
        wrench = _state_glyph(_glyph_source(BUTTON_GLYPH_SOURCES["repair"], (29, 27)), state)
        frame.alpha_composite(anchor, (7, (41 - anchor.height) // 2))
        frame.alpha_composite(wrench, (43, (41 - wrench.height) // 2))
    else:
        glyph = _state_glyph(_glyph_source(BUTTON_GLYPH_SOURCES[key], (50, 29)), state)
        frame.alpha_composite(glyph, (5 + (50 - glyph.width) // 2, (41 - glyph.height) // 2))
        plus = (193, 151, 67, 255) if state != 2 else (100, 103, 99, 220)
        draw.line((67, 11, 67, 29), fill=(3, 4, 4, 255), width=5)
        draw.line((58, 20, 76, 20), fill=(3, 4, 4, 255), width=5)
        draw.line((67, 11, 67, 29), fill=plus, width=3)
        draw.line((58, 20, 76, 20), fill=plus, width=3)
    if state == 2:
        draw.ellipse((57, 10, 76, 29), outline=(126, 48, 44, 235), width=2)
        draw.line((59, 28, 74, 12), fill=(126, 48, 44, 245), width=2)
    return frame


def _button_strip(key: str) -> Image.Image:
    output = Image.new("RGBA", (81 * 3, 41), (0, 0, 0, 0))
    for state in range(3):
        output.alpha_composite(_button_frame(key, state), (state * 81, 0))
    return output


def _dds_bytes(image: Image.Image) -> bytes:
    stream = BytesIO()
    image.save(stream, format="DDS")
    return stream.getvalue()


def expected_outputs() -> dict[Path, bytes]:
    return {
        WINDOW_TILE: _dds_bytes(_window_tile()),
        LINES_TILE: _dds_bytes(_lines_tile()),
        LINES_OVERLAY: _dds_bytes(_lines_overlay()),
        TOP_PANEL: _dds_bytes(_top_panel()),
        MILITARY_ITEM: _dds_bytes(_military_item()),
        COLLAPSED_ITEM: _dds_bytes(_collapsed_item()),
        NAVAL_ITEM_STRIP: _dds_bytes(_naval_item_strip()),
        CONSUMER_ITEM: _dds_bytes(_consumer_item()),
        EQUIPMENT_CARD: _dds_bytes(_equipment_card()),
        FACTORY_ICON_STRIP: _dds_bytes(_factory_strip(False)),
        FACTORY_HALF_STRIP: _dds_bytes(_factory_strip(True)),
        FACTORY_SLOT_BG: _dds_bytes(_factory_slot_bg()),
        ADD_INFANTRY_BUTTON: _dds_bytes(_button_strip("infantry_artillery")),
        ADD_ARMOUR_BUTTON: _dds_bytes(_button_strip("armour")),
        ADD_AIRCRAFT_BUTTON: _dds_bytes(_button_strip("aircraft")),
        ADD_NAVAL_BUTTON: _dds_bytes(_button_strip("naval")),
        NAVAL_REPAIR_BUTTON: _dds_bytes(_button_strip("repair")),
    }


def validate(outputs: dict[Path, bytes]) -> list[str]:
    issues: list[str] = []
    for path, expected in outputs.items():
        if not path.is_file():
            issues.append(f"missing generated production UI asset: {path.relative_to(ROOT)}")
        elif path.read_bytes() != expected:
            issues.append(f"generated production UI asset differs: {path.relative_to(ROOT)}")
    return issues


def apply(outputs: dict[Path, bytes]) -> None:
    for path, data in outputs.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_mutually_exclusive_group()
    actions.add_argument("--check", action="store_true", help="compare outputs (default)")
    actions.add_argument("--apply", action="store_true", help="write generated DDS outputs")
    args = parser.parse_args()

    try:
        outputs = expected_outputs()
    except (OSError, RuntimeError) as exc:
        print(f"ERROR: {exc}")
        return 1
    if args.apply:
        apply(outputs)
    issues = validate(outputs)
    if issues:
        for issue in issues:
            print(f"ERROR: {issue}")
        return 1
    print("A-Discord production UI assets are current (gunmetal shell, top controls, and line variants).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
