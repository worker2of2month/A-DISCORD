#!/usr/bin/env python3
"""Build the restrained A-Discord ordinary-event popup surfaces.

The source illustration is intentionally generic and exists only for the
console-driven event UI QA cases.  All generated outputs are deterministic;
run without ``--apply`` first, then explicitly apply stale outputs.
"""

from __future__ import annotations

import argparse
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageOps

from tools.lib.adiscord_ui_surfaces import (
    PALETTES,
    apply_or_check,
    load_surface_source,
    metal_surface,
    outer_frame,
)
from tools.lib.paths import repository_root


ROOT = repository_root()
METAL_SOURCE = ROOT / "gfx/interface/production/source/production_surface_source.png"
TEST_PICTURE_SOURCE = ROOT / "gfx/event_pictures/source/event_adiscord_ui_test_source.png"

POPUP_BG = ROOT / "gfx/interface/event_popup_bg.png"
POPUP_TOP = ROOT / "gfx/interface/event_popup_top.png"
POPUP_MIDDLE = ROOT / "gfx/interface/event_popup_middle.png"
POPUP_BOTTOM = ROOT / "gfx/interface/event_popup_bottom.png"
OPTION_ENTRY = ROOT / "gfx/interface/event_option_entry_adiscord.png"
PREVIEW = ROOT / "gfx/interface/events/preview/ADISCORD_event_window_preview.png"
TEST_PICTURE = ROOT / "gfx/event_pictures/event_adiscord_ui_test.png"

WINDOW_SIZE = (615, 650)
TOP_SIZE = (615, 100)
MIDDLE_SIZE = (615, 64)
BOTTOM_SIZE = (615, 372)
OPTION_SIZE = (300, 35)
PICTURE_SIZE = (507, 184)
PREVIEW_SIZE = (1600, 900)

PALETTE = PALETTES["technology"]


def _png_bytes(image: Image.Image) -> bytes:
    stream = BytesIO()
    image.save(stream, format="PNG", optimize=False, compress_level=9)
    return stream.getvalue()


def _metal_source() -> Image.Image:
    return load_surface_source(METAL_SOURCE, (1024, 1024))


def _test_picture_source() -> Image.Image:
    if not TEST_PICTURE_SOURCE.is_file():
        raise RuntimeError(
            f"missing event test picture source: {TEST_PICTURE_SOURCE.relative_to(ROOT)}"
        )
    with Image.open(TEST_PICTURE_SOURCE) as source_image:
        return source_image.convert("RGB")


def _popup_background() -> Image.Image:
    output = metal_surface(
        _metal_source(),
        WINDOW_SIZE,
        PALETTE,
        brightness=0.54,
        centering=(0.48, 0.48),
    )
    dim = Image.new("RGBA", WINDOW_SIZE, (3, 7, 8, 116))
    output = Image.alpha_composite(output.convert("RGBA"), dim)
    outer_frame(output, (0, 0, WINDOW_SIZE[0] - 1, WINDOW_SIZE[1] - 1), PALETTE)

    draw = ImageDraw.Draw(output, "RGBA")
    draw.line((48, 96, 566, 96), fill=PALETTE.accent_light, width=2)
    draw.line((54, 481, 560, 481), fill=(74, 112, 113, 128), width=1)
    return output


def _section_surface(
    size: tuple[int, int],
    centering: tuple[float, float],
) -> Image.Image:
    output = metal_surface(
        _metal_source(),
        size,
        PALETTE,
        brightness=0.54,
        centering=centering,
    )
    dim = Image.new("RGBA", size, (3, 7, 8, 116))
    return Image.alpha_composite(output.convert("RGBA"), dim)


def _draw_vertical_shell_edges(output: Image.Image) -> None:
    width, height = output.size
    draw = ImageDraw.Draw(output, "RGBA")
    draw.line((0, 0, 0, height - 1), fill=PALETTE.deep, width=2)
    draw.line((width - 2, 0, width - 2, height - 1), fill=PALETTE.deep, width=2)
    draw.line((2, 0, 2, height - 1), fill=PALETTE.edge, width=1)
    draw.line((width - 3, 0, width - 3, height - 1), fill=PALETTE.edge, width=1)


def _top_overlay() -> Image.Image:
    output = _section_surface(TOP_SIZE, (0.48, 0.30))
    draw = ImageDraw.Draw(output, "RGBA")
    _draw_vertical_shell_edges(output)
    draw.line((0, 0, TOP_SIZE[0] - 1, 0), fill=PALETTE.deep, width=2)
    draw.line((4, 3, TOP_SIZE[0] - 5, 3), fill=PALETTE.edge_light, width=1)
    draw.line((48, 96, 566, 96), fill=PALETTE.accent_light, width=2)
    return output


def _middle_tile() -> Image.Image:
    output = _section_surface(MIDDLE_SIZE, (0.48, 0.48))
    _draw_vertical_shell_edges(output)
    return output


def _bottom_overlay() -> Image.Image:
    output = _section_surface(BOTTOM_SIZE, (0.48, 0.72))
    _draw_vertical_shell_edges(output)
    draw = ImageDraw.Draw(output, "RGBA")
    draw.line((54, 0, 560, 0), fill=(32, 55, 56, 255), width=1)
    # The native country-event picture belongs to the adaptive bottom section.
    draw.rectangle((53, 7, 561, 192), fill=(2, 5, 6, 255), outline=PALETTE.deep, width=2)
    draw.rectangle((55, 9, 559, 190), outline=(113, 139, 140, 230), width=1)
    draw.line((54, 198, 560, 198), fill=(32, 55, 56, 255), width=1)
    draw.line((0, BOTTOM_SIZE[1] - 2, BOTTOM_SIZE[0] - 1, BOTTOM_SIZE[1] - 2), fill=PALETTE.deep, width=2)
    draw.line((4, BOTTOM_SIZE[1] - 4, BOTTOM_SIZE[0] - 5, BOTTOM_SIZE[1] - 4), fill=PALETTE.accent, width=1)
    return output


def _option_entry() -> Image.Image:
    width, height = OPTION_SIZE
    output = metal_surface(
        _metal_source(),
        OPTION_SIZE,
        PALETTE,
        brightness=0.63,
        centering=(0.55, 0.44),
    )
    overlay = Image.new("RGBA", OPTION_SIZE, (4, 10, 11, 76))
    output = Image.alpha_composite(output.convert("RGBA"), overlay)
    draw = ImageDraw.Draw(output, "RGBA")
    draw.rectangle((0, 0, width - 1, height - 1), outline=PALETTE.deep, width=2)
    draw.rectangle((2, 2, width - 3, height - 3), outline=PALETTE.edge, width=1)
    draw.line((4, 3, width - 5, 3), fill=(116, 139, 139, 132), width=1)
    draw.line((4, height - 4, width - 5, height - 4), fill=PALETTE.accent, width=1)
    return output


def _test_picture() -> Image.Image:
    source = _test_picture_source()
    fitted = ImageOps.fit(
        source,
        PICTURE_SIZE,
        method=Image.Resampling.LANCZOS,
        centering=(0.50, 0.52),
    )
    fitted = ImageEnhance.Color(fitted).enhance(0.78)
    fitted = ImageEnhance.Contrast(fitted).enhance(1.04)
    return fitted.convert("RGB")


def _preview() -> Image.Image:
    width, height = PREVIEW_SIZE
    backdrop = Image.new("RGB", PREVIEW_SIZE, (7, 14, 16))
    glow = Image.new("RGBA", PREVIEW_SIZE, (0, 0, 0, 0))
    glow_draw = ImageDraw.Draw(glow, "RGBA")
    glow_draw.ellipse((760, 160, 1500, 900), fill=(50, 77, 79, 66))
    glow = glow.filter(ImageFilter.GaussianBlur(78))
    backdrop = Image.alpha_composite(backdrop.convert("RGBA"), glow)

    grid = ImageDraw.Draw(backdrop, "RGBA")
    for offset in range(-600, 1800, 290):
        grid.line((offset, 54, offset + 570, 900), fill=(76, 114, 116, 36), width=3)
    grid.line((0, 53, width, 53), fill=(61, 119, 120, 120), width=1)

    description_height = 108
    middle_height = 28 + description_height
    bottom_y = 128 + description_height
    shell_height = bottom_y + BOTTOM_SIZE[1]
    shell = Image.new("RGBA", (WINDOW_SIZE[0], shell_height), (0, 0, 0, 0))
    top = _top_overlay()
    middle = _middle_tile().resize((MIDDLE_SIZE[0], middle_height), Image.Resampling.BILINEAR)
    bottom = _bottom_overlay()
    picture = _test_picture().convert("RGBA")
    option = _option_entry()

    shell.alpha_composite(top, (0, 0))
    shell.alpha_composite(middle, (0, 100))
    shell.alpha_composite(bottom, (0, bottom_y))
    shell.alpha_composite(picture, (54, bottom_y + 8))
    preview_draw = ImageDraw.Draw(shell, "RGBA")
    preview_draw.rectangle((54, 114, 560, 126), fill=(196, 207, 204, 182))
    preview_draw.rectangle((54, 136, 520, 147), fill=(172, 186, 183, 145))
    preview_draw.rectangle((54, 158, 548, 169), fill=(172, 186, 183, 145))
    preview_draw.rectangle((54, 180, 456, 191), fill=(172, 186, 183, 145))
    for index in range(4):
        shell.alpha_composite(option, (157, bottom_y + 204 + index * 39))

    left = (width - WINDOW_SIZE[0]) // 2
    top_y = 121
    backdrop.alpha_composite(shell, (left, top_y))
    return backdrop.convert("RGB")


def expected_outputs() -> dict[Path, bytes]:
    return {
        POPUP_BG: _png_bytes(_popup_background()),
        POPUP_TOP: _png_bytes(_top_overlay()),
        POPUP_MIDDLE: _png_bytes(_middle_tile()),
        POPUP_BOTTOM: _png_bytes(_bottom_overlay()),
        OPTION_ENTRY: _png_bytes(_option_entry()),
        PREVIEW: _png_bytes(_preview()),
        TEST_PICTURE: _png_bytes(_test_picture()),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_mutually_exclusive_group()
    actions.add_argument("--check", action="store_true")
    actions.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    return apply_or_check(expected_outputs(), args.apply, "Event UI")


if __name__ == "__main__":
    raise SystemExit(main())
