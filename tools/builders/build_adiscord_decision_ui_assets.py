#!/usr/bin/env python3
"""Build the original A-Discord decisions-window surface set.

The checked-in source material is original project art.  This builder crops it
deterministically and draws the functional borders needed by Clausewitz GUI
sprites.  Use the default check mode before ``--apply``.
"""

from __future__ import annotations

import argparse
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageOps

from tools.lib.paths import repository_root


ROOT = repository_root()
SOURCE = ROOT / "gfx/interface/decisions/source/decisions_surface_source.png"
APPROVAL_SOURCE = ROOT / "gfx/interface/decisions/source/decision_approval_seal_source.png"
OUTPUT_DIR = ROOT / "gfx/interface/decisions/ui"

WINDOW_TILE = OUTPUT_DIR / "ADISCORD_decisions_window_tile.dds"
TITLE_BG = OUTPUT_DIR / "ADISCORD_decisions_title_bg.dds"
EVENT_HEADER_BG = OUTPUT_DIR / "ADISCORD_decisions_event_header_bg.dds"
CATEGORY_HEADER_BG = OUTPUT_DIR / "ADISCORD_decisions_category_header_bg.dds"
CATEGORY_DESC_TILE = OUTPUT_DIR / "ADISCORD_decisions_category_desc_tile.dds"
CATEGORY_END_BG = OUTPUT_DIR / "ADISCORD_decisions_category_end_bg.dds"
EVENT_ITEM_BG = OUTPUT_DIR / "ADISCORD_decisions_event_item_bg.dds"
DECISION_ITEM_BG = OUTPUT_DIR / "ADISCORD_decisions_item_bg.dds"
PROGRESS_BG = OUTPUT_DIR / "ADISCORD_decisions_progress_bg.dds"
PROGRESS_GOOD = OUTPUT_DIR / "ADISCORD_decisions_progress_good.dds"
PROGRESS_BAD = OUTPUT_DIR / "ADISCORD_decisions_progress_bad.dds"
SELECT_ICON = OUTPUT_DIR / "ADISCORD_decisions_select_icon_strip.dds"

FRAME_WIDTH = 512

INK = (3, 4, 5, 255)
DEEP = (9, 10, 10, 255)
SEAM = (35, 36, 34, 255)
EDGE = (67, 66, 59, 255)
EDGE_LIGHT = (102, 96, 79, 255)
TOBACCO = (105, 74, 39, 255)
TOBACCO_LIGHT = (142, 104, 55, 255)
OXBLOOD = (104, 45, 40, 255)
OLIVE = (88, 99, 55, 255)


def _source_image() -> Image.Image:
    if not SOURCE.is_file():
        raise RuntimeError(f"missing decisions surface source: {SOURCE.relative_to(ROOT)}")
    with Image.open(SOURCE) as source_image:
        source = source_image.convert("RGBA")
    if source.width < 1024 or source.height < 1024:
        raise RuntimeError(f"decisions source must be at least 1024x1024, got {source.size}")
    return source


def _surface(size: tuple[int, int], centering: tuple[float, float], brightness: float) -> Image.Image:
    """Crop the source weave without turning it into another metal skin."""
    source = _source_image()
    surface = ImageOps.fit(
        source,
        size,
        method=Image.Resampling.LANCZOS,
        centering=centering,
    )
    surface = ImageEnhance.Contrast(surface).enhance(0.94)
    surface = ImageEnhance.Color(surface).enhance(0.58)
    surface = ImageEnhance.Brightness(surface).enhance(brightness)
    surface.putalpha(255)
    return surface


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
    return Image.blend(base, tint, 0.62)


def _rounded_surface(
    size: tuple[int, int],
    box: tuple[int, int, int, int],
    radius: int,
    centering: tuple[float, float],
    brightness: float,
) -> Image.Image:
    left, top, right, bottom = box
    panel_size = (right - left + 1, bottom - top + 1)
    panel = _surface(panel_size, centering, brightness)
    mask = Image.new("L", panel_size, 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        (0, 0, panel_size[0] - 1, panel_size[1] - 1),
        radius=radius,
        fill=255,
    )
    panel.putalpha(mask)
    output = Image.new("RGBA", size, (0, 0, 0, 0))
    output.alpha_composite(panel, (left, top))
    return output


def _bevel(
    image: Image.Image,
    box: tuple[int, int, int, int],
    radius: int,
    lower: tuple[int, int, int, int] = TOBACCO,
) -> None:
    draw = ImageDraw.Draw(image, "RGBA")
    left, top, right, bottom = box
    draw.rounded_rectangle(box, radius=radius, outline=INK, width=3)
    draw.rounded_rectangle(
        (left + 3, top + 3, right - 3, bottom - 3),
        radius=max(0, radius - 2),
        outline=EDGE,
        width=1,
    )
    draw.line((left + 8, top + 5, right - 8, top + 5), fill=(57, 56, 50, 255), width=1)
    draw.line((left + 8, bottom - 4, right - 8, bottom - 4), fill=lower, width=1)
    draw.line((left + 7, bottom - 2, right - 7, bottom - 2), fill=INK, width=1)


def _window_tile() -> Image.Image:
    output = _surface((192, 192), (0.44, 0.58), 0.84)
    draw = ImageDraw.Draw(output, "RGBA")
    draw.rectangle((0, 0, 191, 191), outline=INK, width=5)
    draw.rectangle((5, 5, 186, 186), outline=EDGE, width=1)
    draw.rectangle((8, 8, 183, 183), outline=DEEP, width=2)
    draw.line((10, 10, 181, 10), fill=(112, 105, 86, 72), width=1)
    draw.line((10, 181, 181, 181), fill=(82, 58, 34, 130), width=1)
    return output


def _title_background() -> Image.Image:
    output = _rounded_surface((543, 41), (0, 2, 542, 39), 2, (0.50, 0.22), 1.03)
    _bevel(output, (0, 2, 542, 39), 2)
    draw = ImageDraw.Draw(output, "RGBA")
    for x in range(13, 505, 10):
        draw.point((x, 35), fill=(85, 66, 39, 255))
    return output


def _event_header_background() -> Image.Image:
    output = _rounded_surface((515, 83), (1, 4, 513, 78), 3, (0.34, 0.20), 1.10)
    _bevel(output, (1, 4, 513, 78), 3)
    draw = ImageDraw.Draw(output, "RGBA")
    draw.rectangle((11, 13, 157, 69), fill=(11, 12, 12, 255), outline=SEAM, width=1)
    draw.line((166, 15, 166, 67), fill=(62, 59, 50, 255), width=1)
    draw.line((173, 41, 497, 41), fill=(17, 18, 17, 255), width=1)
    draw.line((12, 15, 12, 67), fill=TOBACCO_LIGHT, width=1)
    return output


def _category_header_background() -> Image.Image:
    output = _rounded_surface((516, 53), (0, 3, 515, 51), 2, (0.57, 0.31), 0.98)
    _bevel(output, (0, 3, 515, 51), 2)
    draw = ImageDraw.Draw(output, "RGBA")
    draw.rectangle((7, 8, 66, 47), fill=(8, 9, 9, 255), outline=SEAM, width=1)
    draw.line((70, 8, 70, 47), fill=(65, 60, 49, 255), width=1)
    draw.line((77, 10, 503, 10), fill=(50, 49, 44, 255), width=1)
    for x in range(83, 431, 12):
        draw.point((x, 46), fill=(77, 56, 35, 255))
    return output


def _category_description_tile() -> Image.Image:
    output = _surface((48, 48), (0.66, 0.67), 0.78)
    draw = ImageDraw.Draw(output, "RGBA")
    draw.rectangle((0, 0, 47, 47), outline=INK, width=3)
    draw.rectangle((3, 3, 44, 44), outline=EDGE, width=1)
    draw.line((5, 5, 42, 5), fill=(108, 102, 86, 70), width=1)
    draw.line((5, 42, 42, 42), fill=(94, 65, 37, 120), width=1)
    return output


def _category_end_background() -> Image.Image:
    output = Image.new("RGBA", (512, 20), (0, 0, 0, 0))
    draw = ImageDraw.Draw(output, "RGBA")
    draw.line((5, 2, 506, 2), fill=INK, width=3)
    draw.line((9, 5, 502, 5), fill=EDGE, width=1)
    for x in range(24, 488, 8):
        draw.point((x, 7), fill=(72, 54, 36, 255))
    return output


def _event_item_background() -> Image.Image:
    output = _tinted_surface(
        (512, 33), (0.27, 0.74), 1.02, (11, 8, 5), (142, 92, 47)
    )
    mask = Image.new("L", output.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((1, 1, 510, 31), radius=2, fill=242)
    output.putalpha(mask)
    _bevel(output, (1, 1, 510, 31), 2, TOBACCO_LIGHT)
    draw = ImageDraw.Draw(output, "RGBA")
    draw.line((45, 5, 45, 27), fill=(74, 54, 36, 255), width=1)
    return output


def _decision_frame(index: int) -> Image.Image:
    brightness = (1.03, 1.10, 1.04)[index]
    centering = ((0.20, 0.36), (0.51, 0.51), (0.81, 0.68))[index]
    shadows = ((12, 4, 4), (7, 8, 8), (5, 8, 4))
    highlights = ((111, 43, 39), (78, 78, 69), (92, 105, 55))
    output = _tinted_surface((FRAME_WIDTH, 40), centering, brightness, shadows[index], highlights[index])
    mask = Image.new("L", output.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((1, 1, 510, 38), radius=2, fill=255)
    output.putalpha(mask)
    draw = ImageDraw.Draw(output, "RGBA")
    edge = (OXBLOOD, EDGE, OLIVE)[index]
    draw.rounded_rectangle((1, 1, 510, 38), radius=2, outline=INK, width=3)
    draw.rounded_rectangle((4, 4, 507, 35), radius=1, outline=edge, width=1)
    draw.line((7, 6, 504, 6), fill=(51, 49, 43, 255), width=1)
    draw.line((56, 6, 56, 34), fill=(7, 7, 7, 255), width=1)
    return output


def _decision_item_background() -> Image.Image:
    output = Image.new("RGBA", (FRAME_WIDTH * 3, 40), (0, 0, 0, 0))
    for index in range(3):
        output.alpha_composite(_decision_frame(index), (index * FRAME_WIDTH, 0))
    return output


def _progress_background() -> Image.Image:
    # The row itself is the trough.  An opaque progress background creates a
    # black slab over active timed decisions, so only the coloured segments
    # are drawn by textureFile1.
    return Image.new("RGBA", (503, 40), (0, 0, 0, 0))


def _segmented_progress(colour: tuple[int, int, int, int]) -> Image.Image:
    output = Image.new("RGBA", (503, 40), (0, 0, 0, 0))
    draw = ImageDraw.Draw(output, "RGBA")
    dark = tuple(max(0, channel - 34) for channel in colour[:3]) + (colour[3],)
    light = tuple(min(255, channel + 24) for channel in colour[:3]) + (colour[3],)
    for x in range(1, 501, 6):
        draw.rectangle((x, 1, min(500, x + 4), 8), fill=colour)
        draw.line((x, 1, min(500, x + 4), 1), fill=light, width=1)
        draw.line((min(500, x + 4), 2, min(500, x + 4), 8), fill=dark, width=1)
    return output


def _approval_seal() -> Image.Image:
    if not APPROVAL_SOURCE.is_file():
        raise RuntimeError(f"missing decision approval source: {APPROVAL_SOURCE.relative_to(ROOT)}")
    with Image.open(APPROVAL_SOURCE) as source_image:
        source = source_image.convert("RGBA")
    bbox = source.getchannel("A").getbbox()
    if bbox is None:
        raise RuntimeError("decision approval source is fully transparent")
    icon = source.crop(bbox)
    icon.thumbnail((25, 25), Image.Resampling.LANCZOS)
    return icon


def _approval_frame(state: int) -> Image.Image:
    icon = _approval_seal()
    if state == 0:
        alpha = icon.getchannel("A").point(lambda value: round(value * 0.42))
        icon = ImageOps.grayscale(icon.convert("RGB")).convert("RGBA")
        icon = ImageEnhance.Brightness(icon).enhance(0.58)
        icon.putalpha(alpha)
    elif state == 2:
        icon = ImageEnhance.Brightness(icon).enhance(1.14)
        icon = ImageEnhance.Contrast(icon).enhance(1.08)
    elif state == 3:
        alpha = icon.getchannel("A").point(lambda value: round(value * 0.62))
        icon = ImageOps.grayscale(icon.convert("RGB")).convert("RGBA")
        icon.putalpha(alpha)

    frame = Image.new("RGBA", (40, 28), (0, 0, 0, 0))
    x = (frame.width - icon.width) // 2
    y = (frame.height - icon.height) // 2
    frame.alpha_composite(icon, (x, y))
    if state == 2:
        ImageDraw.Draw(frame, "RGBA").ellipse((5, 0, 34, 27), outline=(169, 128, 57, 150), width=1)
    elif state == 3:
        draw = ImageDraw.Draw(frame, "RGBA")
        draw.line((8, 22, 31, 5), fill=(157, 47, 39, 255), width=3)
        draw.line((9, 23, 32, 6), fill=(48, 7, 7, 255), width=1)
    return frame


def _approval_strip() -> Image.Image:
    output = Image.new("RGBA", (160, 28), (0, 0, 0, 0))
    for state in range(4):
        output.alpha_composite(_approval_frame(state), (state * 40, 0))
    return output


def _dds_bytes(image: Image.Image) -> bytes:
    stream = BytesIO()
    image.save(stream, format="DDS")
    return stream.getvalue()


def expected_outputs() -> dict[Path, bytes]:
    return {
        WINDOW_TILE: _dds_bytes(_window_tile()),
        TITLE_BG: _dds_bytes(_title_background()),
        EVENT_HEADER_BG: _dds_bytes(_event_header_background()),
        CATEGORY_HEADER_BG: _dds_bytes(_category_header_background()),
        CATEGORY_DESC_TILE: _dds_bytes(_category_description_tile()),
        CATEGORY_END_BG: _dds_bytes(_category_end_background()),
        EVENT_ITEM_BG: _dds_bytes(_event_item_background()),
        DECISION_ITEM_BG: _dds_bytes(_decision_item_background()),
        PROGRESS_BG: _dds_bytes(_progress_background()),
        PROGRESS_GOOD: _dds_bytes(_segmented_progress((111, 126, 61, 255))),
        PROGRESS_BAD: _dds_bytes(_segmented_progress((132, 52, 45, 255))),
        SELECT_ICON: _dds_bytes(_approval_strip()),
    }


def validate(outputs: dict[Path, bytes]) -> list[str]:
    issues: list[str] = []
    for path, expected in outputs.items():
        if not path.is_file():
            issues.append(f"missing generated decisions UI asset: {path.relative_to(ROOT)}")
        elif path.read_bytes() != expected:
            issues.append(f"generated decisions UI asset differs: {path.relative_to(ROOT)}")
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
    print("A-Discord decisions UI assets are current (dossier surfaces, three-state rows, and segmented progress).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
