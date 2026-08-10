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

from PIL import Image, ImageDraw, ImageEnhance, ImageOps

from tools.lib.paths import repository_root


ROOT = repository_root()
SOURCE = ROOT / "gfx/interface/production/source/production_surface_source.png"
OUTPUT_DIR = ROOT / "gfx/interface/production/ui"

WINDOW_TILE = OUTPUT_DIR / "ADISCORD_production_window_tile.dds"
LINES_TILE = OUTPUT_DIR / "ADISCORD_production_lines_tile.dds"
LINES_OVERLAY = OUTPUT_DIR / "ADISCORD_production_lines_overlay.dds"
TOP_PANEL = OUTPUT_DIR / "ADISCORD_production_top_panel.dds"
MILITARY_ITEM = OUTPUT_DIR / "ADISCORD_production_military_item.dds"
COLLAPSED_ITEM = OUTPUT_DIR / "ADISCORD_production_collapsed_item.dds"
NAVAL_ITEM_STRIP = OUTPUT_DIR / "ADISCORD_production_naval_item_strip.dds"
CONSUMER_ITEM = OUTPUT_DIR / "ADISCORD_production_consumer_item.dds"

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

    draw.rectangle((290, 33, 507, 104), fill=(8, 11, 12, 245), outline=INK, width=2)
    _recess(output, (292, 35, 317, 102), (10, 13, 14, 255))
    if factory_rows == 1:
        grid_box = (320, 44, 475, 69)
    elif factory_rows == 2:
        grid_box = (320, 36, 475, 86)
    else:
        grid_box = (320, 35, 475, 102)
    _cell_grid(output, grid_box, 5, factory_rows)
    _cell_grid(output, (478, 35, 507, 102), 1, 3)
    for point in ((7, 8), (503, 8), (7, 100), (503, 100)):
        _rivet(draw, *point)
    return output


def _military_item() -> Image.Image:
    return _item_base((7, 13, 9), (63, 76, 43), 3)


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
