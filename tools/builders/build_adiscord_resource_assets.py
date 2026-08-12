#!/usr/bin/env python3
"""Build the strategic-resource, topbar and core map-interface assets.

The builder owns one coherent nine-resource icon set, its deficit treatment,
the widened trade-entry background, the topbar skin and the state-view shell.
Use ``--check`` before ``--apply``.
"""

from __future__ import annotations

import argparse
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageOps

from tools.lib.paths import repository_root


ROOT = repository_root()
RESOURCE_STRIP = ROOT / "gfx/interface/resources_strip.dds"
MISSING_STRIP = ROOT / "gfx/interface/missing_resources_strip.dds"
TOPBAR_BUTTON = ROOT / "gfx/interface/ADISCORD_economy_gui/economy_topbar_button.dds"
TREASURY_ICON = ROOT / "gfx/interface/ADISCORD_economy_gui/treasury_icon.dds"
TRADE_ENTRY = ROOT / "gfx/interface/ADISCORD_trade_gui/country_trade_entry_bg.dds"
RESOURCE_SOURCE = ROOT / "gfx/interface/ADISCORD_trade_gui/source/strategic_resources_source.png"
TRADE_ENTRY_SOURCE = ROOT / "gfx/interface/ADISCORD_trade_gui/source/country_trade_entry_source.png"
TOPBAR_SOURCE = ROOT / "gfx/interface/ADISCORD_trade_gui/source/topbar_glyphs_source.png"
INDICATOR_SOURCE = ROOT / "gfx/interface/ADISCORD_trade_gui/source/topbar_indicators_source.png"
MARKET_SOURCE = ROOT / "gfx/interface/ADISCORD_trade_gui/source/international_market_source.png"
COMMAND_POWER_SOURCE = ROOT / "gfx/interface/ADISCORD_trade_gui/source/command_power_phone_source.png"
TOPBAR_BACKGROUND_SOURCE = ROOT / "gfx/interface/ADISCORD_trade_gui/source/topbar_background_extended_source.png"
TREASURY_SOURCE = ROOT / "gfx/interface/ADISCORD_economy_gui/source/treasury_topbar_source.png"
INTERNATIONAL_MARKET_BUTTON = ROOT / "gfx/interface/topbar/toolbar/international_market_button.dds"
WORLD_TENSION_ICON = ROOT / "gfx/interface/world_tension_icon_big_strip.dds"
WORLD_TENSION_SOURCE = ROOT / "gfx/interface/ADISCORD_trade_gui/source/world_tension_defcon_tfr.dds"
COMMAND_POWER_ICON = ROOT / "gfx/interface/command_power_icon.dds"
COMMAND_POWER_TEXTICON = ROOT / "gfx/texticons/command_power.dds"
TOPBAR_BACKGROUND = ROOT / "gfx/interface/topbar/background_extended.dds"
RIGHT_CLUSTER_BACKGROUND = ROOT / "gfx/interface/topbar/armyoverview_buttons_bg.dds"
DATE_CONTROL_BACKGROUND = ROOT / "gfx/interface/date_pause_button_bg.dds"
DATE_CONTROL_PAUSED = ROOT / "gfx/interface/date_pause_button.dds"
SPEED_DOWN_BUTTON = ROOT / "gfx/interface/topbar/zoom_out.dds"
SPEED_UP_BUTTON = ROOT / "gfx/interface/topbar/zoom_in.dds"
SPEED_STEP_BUTTON = ROOT / "gfx/interface/topbar/speed_step.dds"
MENU_BUTTON = ROOT / "gfx/interface/topbar/button_menu.dds"
HELP_BUTTON = ROOT / "gfx/interface/topbar/button_help.dds"
ACHIEVEMENTS_BUTTON = ROOT / "gfx/interface/topbar/achievements_button.dds"
PLAYLIST_BUTTON = ROOT / "gfx/interface/topbar/musicplayer/playlist_button.dds"
DISMISSED_ALERTS_BUTTON = ROOT / "gfx/interface/topbar/show_dismissed_alerts_icon.dds"
TOPBAR_FLAG_FRAME = ROOT / "gfx/interface/topbar/ADISCORD_flag_frame_overlay.dds"
TOPBAR_FLAG_OVERLAY = ROOT / "gfx/interface/topbar/ADISCORD_flag_overlay.dds"
TOPBAR_FLAG_MASK = ROOT / "gfx/interface/topbar/ADISCORD_flag_alpha_mask.tga"
STATEVIEW_WW_BACKGROUND = ROOT / "gfx/interface/stateview/ww_stateview_bg.dds"
STATEVIEW_BACKGROUND = ROOT / "gfx/interface/stateview/stateview_bg.dds"
STATEVIEW_WW_ENTRY = ROOT / "gfx/interface/stateview/ww_building_standing_entry_stateview.dds"
STATEVIEW_ENTRY = ROOT / "gfx/interface/stateview/building_standing_entry_stateview.dds"
STATEVIEW_BUILDING_ENTRY = ROOT / "gfx/interface/stateview/building_entry_stateview.dds"
STATEVIEW_LANDMARK_ENTRY = ROOT / "gfx/interface/stateview/province_landmark_bg.dds"
STATEVIEW_BUILD_SLOT = ROOT / "gfx/interface/buildings/build_slot_bg.dds"
STATEVIEW_PROVINCE_HEADER = ROOT / "gfx/interface/province_header.dds"
STATEVIEW_POPULATION_ICON = ROOT / "gfx/interface/population_icon.dds"
STATEVIEW_VALUE_BG = ROOT / "gfx/interface/victorypoint_stateview_bg.dds"
STATEVIEW_RESOURCE_BG = ROOT / "gfx/interface/stateview_resource_transp_bg.dds"

FRAME_WIDTH = 26
TOTAL_FRAMES = 9
STRIP_SIZE = (FRAME_WIDTH * TOTAL_FRAMES, 27)
MISSING_SIZE = (FRAME_WIDTH * TOTAL_FRAMES, 28)
TOPBAR_SIZE = (110, 41)
SMALL_TOPBAR_SIZE = (76, 38)
TREASURY_ICON_SIZE = (24, 24)
TRADE_ENTRY_FRAME_SIZE = (806, 45)
TRADE_ENTRY_SIZE = (TRADE_ENTRY_FRAME_SIZE[0] * 3, TRADE_ENTRY_FRAME_SIZE[1])
WORLD_TENSION_FRAME_SIZE = (49, 49)
WORLD_TENSION_FRAMES = 10
RIGHT_CLUSTER_SIZE = (403, 101)
DATE_CONTROL_SIZE = (206, 28)
TOPBAR_FLAG_FRAME_SIZE = (88, 58)
TOPBAR_FLAG_OVERLAY_SIZE = (82, 52)
TOPBAR_FLAG_MASK_SIZE = (82, 52)

STATEVIEW_OUTPUT_SIZES = {
    STATEVIEW_WW_BACKGROUND: (463, 653),
    STATEVIEW_BACKGROUND: (463, 542),
    STATEVIEW_WW_ENTRY: (62, 84),
    STATEVIEW_ENTRY: (61, 100),
    STATEVIEW_BUILDING_ENTRY: (110, 50),
    STATEVIEW_LANDMARK_ENTRY: (50, 43),
    STATEVIEW_BUILD_SLOT: (56, 46),
    STATEVIEW_PROVINCE_HEADER: (417, 29),
    STATEVIEW_POPULATION_ICON: (32, 33),
    STATEVIEW_VALUE_BG: (44, 26),
    STATEVIEW_RESOURCE_BG: (155, 63),
}

# The approved source sheet contains a deliberately irregular 5x3 icon grid.
# Explicit content boxes keep the generator deterministic and avoid treating
# the separate helmet chevrons as another icon.
TOPBAR_GLYPH_BOXES = (
    (117, 112, 320, 315),   # faction (reserved for the dynamic faction logo)
    (407, 99, 568, 319),    # decisions
    (659, 108, 868, 317),   # intelligence
    (936, 103, 1143, 315),  # technology
    (1204, 126, 1431, 319), # diplomacy
    (91, 399, 311, 598),    # trade
    (392, 405, 589, 591),   # economy
    (656, 387, 864, 602),   # construction
    (933, 398, 1145, 607),  # production
    (1235, 406, 1402, 601), # deployment, including chevrons
    (89, 687, 312, 882),    # logistics
    (383, 699, 602, 868),   # officer corps
    (649, 720, 874, 864),   # army
    (939, 668, 1139, 890),  # navy
    (1211, 678, 1435, 898), # air
)

MAIN_TOPBAR_BUTTONS = {
    "gfx/interface/topbar/toolbar/topbar_decisionview_button.dds": 1,
    "gfx/interface/topbar/toolbar/intelligence_button.dds": 2,
    "gfx/interface/topbar/toolbar/science_button.dds": 3,
    "gfx/interface/topbar/toolbar/diplomacy_button.dds": 4,
    "gfx/interface/topbar/toolbar/trade_button.dds": 5,
    "gfx/interface/topbar/toolbar/construction_button.dds": 7,
    "gfx/interface/topbar/toolbar/production_button.dds": 8,
    "gfx/interface/topbar/toolbar/deployment_button.dds": 9,
    "gfx/interface/topbar/toolbar/ledger_button.dds": 10,
    "gfx/interface/topbar/toolbar/staff_office_button.dds": 11,
}
SMALL_TOPBAR_BUTTONS = {
    "gfx/interface/topbar/armyoverview_button.dds": 12,
    "gfx/interface/topbar/navyoverview_button.dds": 13,
    "gfx/interface/topbar/airoverview_button.dds": 14,
}

TOPBAR_INDICATORS = {
    "gfx/interface/pol_power_icon.dds": (0, (27, 27)),
    "gfx/interface/stability_icon.dds": (1, (27, 24)),
    "gfx/interface/war_support_icon.dds": (2, (26, 24)),
    "gfx/interface/manpower_icon.dds": (3, (27, 27)),
    "gfx/interface/equipment_icon.dds": (6, (22, 18)),
    "gfx/interface/topbar/topbar_convoys.dds": (7, (28, 18)),
    "gfx/texticons/army_experience_20x20.dds": (9, (14, 14)),
    "gfx/texticons/navy_experience_20x20.dds": (10, (14, 14)),
    "gfx/texticons/air_experience_20x20.dds": (11, (14, 14)),
    "gfx/interface/topbar/nuke_icon.dds": (12, (27, 28)),
}
INDICATOR_TINTS = {
    # Keep the nuclear glyph's warm identity while lifting it from the dark
    # source palette. Convoy and XP icons retain their original colours.
    12: ((84, 81, 64), (255, 235, 160)),  # nuclear: warm ivory radiation mark
}
INDUSTRY_ICON = ROOT / "gfx/interface/industrial_capacity_icon.dds"
FUEL_ICON = ROOT / "gfx/interface/topbar/fuel_state_icon.dds"

def _fit_icon(source: Image.Image, height: int) -> Image.Image:
    """Fit one source icon into a mathematically centred 26px frame."""
    alpha_box = source.getchannel("A").getbbox()
    if alpha_box is None:
        raise RuntimeError("resource source contains an empty icon cell")
    icon = source.crop(alpha_box)
    scale = min(24 / icon.width, (height - 2) / icon.height)
    size = (
        max(1, round(icon.width * scale)),
        max(1, round(icon.height * scale)),
    )
    icon = icon.resize(size, Image.Resampling.LANCZOS)
    # The generated source is deliberately pixel-art-like.  A hard alpha edge
    # removes chroma-key speckles that would otherwise become isolated coloured
    # pixels after the icon is reduced to 26x27.
    icon.putalpha(icon.getchannel("A").point(lambda value: 255 if value >= 96 else 0))
    frame = Image.new("RGBA", (FRAME_WIDTH, height), (0, 0, 0, 0))
    frame.alpha_composite(
        icon,
        ((FRAME_WIDTH - icon.width) // 2, (height - icon.height) // 2),
    )
    return frame


def _resource_icons(height: int = 27) -> list[Image.Image]:
    if not RESOURCE_SOURCE.is_file():
        raise RuntimeError(f"missing resource source art: {RESOURCE_SOURCE.relative_to(ROOT)}")
    with Image.open(RESOURCE_SOURCE) as source_image:
        source = source_image.convert("RGBA")
    icons: list[Image.Image] = []
    for index in range(TOTAL_FRAMES):
        left = round(index * source.width / TOTAL_FRAMES)
        right = round((index + 1) * source.width / TOTAL_FRAMES)
        icons.append(_fit_icon(source.crop((left, 0, right, source.height)), height))
    return icons


def _missing(icon: Image.Image, height: int) -> Image.Image:
    source = icon.resize((FRAME_WIDTH, height), Image.Resampling.NEAREST)
    image = Image.new("RGBA", source.size, (0, 0, 0, 0))
    src = source.load()
    dst = image.load()
    for y in range(height):
        for x in range(FRAME_WIDTH):
            r, g, b, a = src[x, y]
            if a:
                light = (r + g + b) // 3
                dst[x, y] = (min(255, 135 + light // 2), 38 + light // 6, 10, a)
    draw = ImageDraw.Draw(image)
    draw.ellipse((2, 2, 23, height - 3), outline=(116, 18, 4, 255), width=2)
    draw.line((5, height - 5, 21, 5), fill=(245, 106, 17, 255), width=2)
    return image


def _resource_strip() -> Image.Image:
    output = Image.new("RGBA", STRIP_SIZE, (0, 0, 0, 0))
    for index, icon in enumerate(_resource_icons(STRIP_SIZE[1])):
        output.alpha_composite(icon, (index * FRAME_WIDTH, 0))
    return output


def _missing_strip() -> Image.Image:
    output = Image.new("RGBA", MISSING_SIZE, (0, 0, 0, 0))
    for index, icon in enumerate(_resource_icons(STRIP_SIZE[1])):
        output.alpha_composite(_missing(icon, MISSING_SIZE[1]), (index * FRAME_WIDTH, 0))
    return output


def _trade_entry_background() -> Image.Image:
    if not TRADE_ENTRY_SOURCE.is_file():
        raise RuntimeError(f"missing trade-entry source art: {TRADE_ENTRY_SOURCE.relative_to(ROOT)}")
    with Image.open(TRADE_ENTRY_SOURCE) as source_image:
        source = source_image.convert("RGBA")
    output = Image.new("RGBA", TRADE_ENTRY_SIZE, (0, 0, 0, 0))
    for index in range(3):
        left = round(index * source.width / 3)
        right = round((index + 1) * source.width / 3)
        cell = source.crop((left, 0, right, source.height))
        luminance = cell.convert("RGB").convert("L")
        panel_box = luminance.point(lambda value: 255 if value > 12 else 0).getbbox()
        if panel_box is None:
            raise RuntimeError(f"trade-entry source frame {index + 1} is empty")
        panel = cell.crop(panel_box).resize(TRADE_ENTRY_FRAME_SIZE, Image.Resampling.LANCZOS)
        output.alpha_composite(panel, (index * TRADE_ENTRY_FRAME_SIZE[0], 0))
    return output


def _defcon_strip_bytes() -> bytes:
    """Return the approved TFR-style textured DEFCON frame strip unchanged."""
    if not WORLD_TENSION_SOURCE.is_file():
        raise RuntimeError(
            f"missing DEFCON source art: {WORLD_TENSION_SOURCE.relative_to(ROOT)}"
        )
    with Image.open(WORLD_TENSION_SOURCE) as source:
        if source.size != (WORLD_TENSION_FRAME_SIZE[0] * WORLD_TENSION_FRAMES, WORLD_TENSION_FRAME_SIZE[1]):
            raise RuntimeError(
                f"DEFCON source must remain 490x49, got {source.width}x{source.height}"
            )
    return WORLD_TENSION_SOURCE.read_bytes()


def _topbar_source_icon(index: int) -> Image.Image:
    if not TOPBAR_SOURCE.is_file():
        raise RuntimeError(f"missing topbar source art: {TOPBAR_SOURCE.relative_to(ROOT)}")
    with Image.open(TOPBAR_SOURCE) as source_image:
        source = source_image.convert("RGBA")
    return source.crop(TOPBAR_GLYPH_BOXES[index])


def _indicator_source_icon(index: int) -> Image.Image:
    if not INDICATOR_SOURCE.is_file():
        raise RuntimeError(f"missing topbar indicator source art: {INDICATOR_SOURCE.relative_to(ROOT)}")
    with Image.open(INDICATOR_SOURCE) as source_image:
        source = source_image.convert("RGBA")
    column = index % 5
    row = index // 5
    left = round(column * source.width / 5)
    right = round((column + 1) * source.width / 5)
    top = round(row * source.height / 3)
    bottom = round((row + 1) * source.height / 3)
    return source.crop((left, top, right, bottom))


def _tinted_indicator_source(source: Image.Image, index: int) -> Image.Image:
    """Lift selected small indicators without changing their silhouettes."""
    palette = INDICATOR_TINTS.get(index)
    if palette is None:
        return source
    alpha = source.getchannel("A")
    luminance = ImageOps.grayscale(source.convert("RGB"))
    tinted = ImageOps.colorize(luminance, black=palette[0], white=palette[1]).convert("RGBA")
    tinted.putalpha(alpha)
    return tinted


def _lift_indicator_source(source: Image.Image, index: int) -> Image.Image:
    """Raise readable detail while preserving the source icon's colour identity."""
    if index not in (7, 9, 10, 11):
        return source
    alpha = source.getchannel("A")
    rgb = ImageOps.autocontrast(source.convert("RGB"), cutoff=1, mask=alpha)
    lifted = rgb.convert("RGBA")
    lifted.putalpha(alpha)
    if index == 7:
        # The source ship is already readable at indicator size. A restrained
        # lift keeps its steel/teal and rust tones instead of bleaching the
        # hull into a generic white silhouette on the dark topbar.
        lifted = ImageEnhance.Brightness(lifted).enhance(1.26)
        lifted = ImageEnhance.Contrast(lifted).enhance(1.08)
        lifted = ImageEnhance.Color(lifted).enhance(1.18)
        pixels = lifted.load()
        for y in range(lifted.height):
            for x in range(lifted.width):
                red, green, blue, pixel_alpha = pixels[x, y]
                if pixel_alpha < 96 or max(red, green, blue) - min(red, green, blue) > 24:
                    continue
                luminance = round(0.299 * red + 0.587 * green + 0.114 * blue)
                steel = max(44, min(220, round(44 + luminance * 0.62)))
                pixels[x, y] = (max(0, steel - 6), steel, min(255, steel + 6), pixel_alpha)
        return lifted
    lifted = ImageEnhance.Brightness(lifted).enhance(1.75 if index == 9 else 1.55)
    lifted = ImageEnhance.Contrast(lifted).enhance(1.12)
    return ImageEnhance.Color(lifted).enhance(1.15)


def _chroma_source(path: Path, description: str) -> Image.Image:
    """Load approved generated art and remove its green matte."""
    if not path.is_file():
        raise RuntimeError(f"missing {description} source art: {path.relative_to(ROOT)}")
    with Image.open(path) as source_image:
        source = source_image.convert("RGBA")
    pixels = source.load()
    for y in range(source.height):
        for x in range(source.width):
            red, green, blue, alpha = pixels[x, y]
            green_dominance = green - max(red, blue)
            if green >= 140 and green_dominance >= 35:
                alpha = min(alpha, max(0, 255 - green_dominance * 3))
                pixels[x, y] = (red, green, blue, alpha)
    return source


def _international_market_source_icon() -> Image.Image:
    return _chroma_source(MARKET_SOURCE, "international-market")


def _command_power_source_icon() -> Image.Image:
    return _chroma_source(COMMAND_POWER_SOURCE, "command-power telephone")


def _bright_command_power_source() -> Image.Image:
    """Lift the telephone's shadows while retaining its red/brass palette."""
    source = _command_power_source_icon()
    alpha = source.getchannel("A")
    rgb = ImageOps.autocontrast(source.convert("RGB"), cutoff=1, mask=alpha)
    lifted = rgb.convert("RGBA")
    lifted.putalpha(alpha)
    lifted = ImageEnhance.Brightness(lifted).enhance(1.22)
    return ImageEnhance.Color(lifted).enhance(1.15)


def _fit_glyph(source: Image.Image, max_size: tuple[int, int]) -> Image.Image:
    source = source.copy()
    # Generated chroma-key sources can retain nearly invisible matte noise far
    # outside the object. Threshold before measuring the bounds, otherwise a
    # 24px treasury icon is fitted against the whole source canvas and shrinks
    # to an unreadable dot.
    source.putalpha(source.getchannel("A").point(lambda value: 255 if value >= 96 else 0))
    alpha_box = source.getchannel("A").getbbox()
    if alpha_box is None:
        raise RuntimeError("topbar source contains an empty glyph")
    glyph = source.crop(alpha_box)
    scale = min(max_size[0] / glyph.width, max_size[1] / glyph.height)
    size = (max(1, round(glyph.width * scale)), max(1, round(glyph.height * scale)))
    glyph = glyph.resize(size, Image.Resampling.LANCZOS)
    glyph.putalpha(glyph.getchannel("A").point(lambda value: 255 if value >= 96 else 0))
    return glyph


def _button_from_glyph(source: Image.Image, frame_size: tuple[int, int]) -> Image.Image:
    output = Image.new("RGBA", (frame_size[0] * 2, frame_size[1]), (0, 0, 0, 0))
    max_glyph_size = (frame_size[0] - 14, frame_size[1] - 10)
    for frame, hover in ((0, False), (1, True)):
        x0 = frame * frame_size[0]
        draw = ImageDraw.Draw(output)
        border = (130, 114, 76, 255) if hover else (75, 70, 58, 255)
        panel = (43, 46, 42, 255) if hover else (29, 32, 30, 255)
        inner = (59, 65, 58, 255) if hover else (39, 44, 40, 255)
        draw.rectangle(
            (x0 + 1, 1, x0 + frame_size[0] - 2, frame_size[1] - 2),
            fill=panel,
            outline=border,
            width=1,
        )
        draw.rectangle(
            (x0 + 4, 4, x0 + frame_size[0] - 5, frame_size[1] - 5),
            fill=inner,
            outline=(19, 21, 20, 255),
            width=1,
        )
        glyph = _fit_glyph(source, max_glyph_size)
        if hover:
            glyph = ImageEnhance.Brightness(glyph).enhance(1.18)
        output.alpha_composite(
            glyph,
            (
                x0 + (frame_size[0] - glyph.width) // 2,
                (frame_size[1] - glyph.height) // 2,
            ),
        )
    return output


def _topbar_button(index: int, frame_size: tuple[int, int]) -> Image.Image:
    return _button_from_glyph(_topbar_source_icon(index), frame_size)


def _international_market_button() -> Image.Image:
    return _button_from_glyph(_international_market_source_icon(), (55, 41))


def _round_topbar_button(index: int) -> Image.Image:
    """Build the shared round army/navy/air overview texture."""
    frame_size = (38, 38)
    output = Image.new("RGBA", SMALL_TOPBAR_SIZE, (0, 0, 0, 0))
    source = _topbar_source_icon(index)
    for frame, hover in ((0, False), (1, True)):
        x0 = frame * frame_size[0]
        draw = ImageDraw.Draw(output)
        border = (145, 125, 81, 255) if hover else (80, 75, 62, 255)
        panel = (52, 57, 52, 255) if hover else (25, 29, 27, 255)
        inner = (68, 76, 68, 255) if hover else (37, 42, 38, 255)
        draw.ellipse((x0 + 1, 1, x0 + 36, 36), fill=panel, outline=border, width=1)
        draw.ellipse((x0 + 4, 4, x0 + 33, 33), fill=inner, outline=(12, 15, 13, 255), width=1)
        glyph = _fit_glyph(source, (24, 24))
        if hover:
            glyph = ImageEnhance.Brightness(glyph).enhance(1.18)
        output.alpha_composite(
            glyph,
            (x0 + (frame_size[0] - glyph.width) // 2, (frame_size[1] - glyph.height) // 2),
        )
    return output


def _indicator_icon(index: int, size: tuple[int, int]) -> Image.Image:
    source = _indicator_source_icon(index)
    source = _lift_indicator_source(source, index)
    source = _tinted_indicator_source(source, index)
    glyph = _fit_glyph(source, (max(1, size[0] - 2), max(1, size[1] - 2)))
    if index in (9, 11):
        # Army and air source cells have different aspect ratios from navy;
        # normalize their visible XP glyphs to the same 12x12 footprint.
        glyph.putalpha(glyph.getchannel("A").point(lambda value: 255 if value >= 96 else 0))
        alpha_box = glyph.getchannel("A").getbbox()
        if alpha_box is None:
            raise RuntimeError(f"XP indicator {index} became empty after fitting")
        glyph = glyph.crop(alpha_box).resize(
            (max(1, size[0] - 2), max(1, size[1] - 2)),
            Image.Resampling.LANCZOS,
        )
    output = Image.new("RGBA", size, (0, 0, 0, 0))
    output.alpha_composite(glyph, ((size[0] - glyph.width) // 2, (size[1] - glyph.height) // 2))
    return output


def _command_power_icon(size: tuple[int, int]) -> Image.Image:
    source = _bright_command_power_source()
    glyph = _fit_glyph(
        source,
        (max(1, size[0] - 2), max(1, size[1] - 2)),
    )
    output = Image.new("RGBA", size, (0, 0, 0, 0))
    output.alpha_composite(glyph, ((size[0] - glyph.width) // 2, (size[1] - glyph.height) // 2))
    return output


def _industry_icon_strip() -> Image.Image:
    normal = _indicator_icon(4, (35, 29))
    hover = ImageEnhance.Brightness(normal).enhance(1.32)
    output = Image.new("RGBA", (70, 29), (0, 0, 0, 0))
    output.alpha_composite(normal, (0, 0))
    output.alpha_composite(hover, (35, 0))
    return output


def _fuel_icon_strip() -> Image.Image:
    base = _indicator_icon(5, (26, 24))
    output = Image.new("RGBA", (78, 24), (0, 0, 0, 0))
    for frame in range(3):
        icon = base.copy()
        if frame:
            draw = ImageDraw.Draw(icon)
            colour = (64, 220, 112, 255) if frame == 1 else (225, 42, 35, 255)
            if frame == 1:
                draw.line((2, 16, 7, 11, 12, 16), fill=colour, width=2)
                draw.line((2, 11, 7, 6, 12, 11), fill=colour, width=2)
            else:
                draw.line((2, 7, 7, 12, 12, 7), fill=colour, width=2)
                draw.line((2, 12, 7, 17, 12, 12), fill=colour, width=2)
        output.alpha_composite(icon, (frame * 26, 0))
    return output


def _treasury_icon() -> Image.Image:
    if not TREASURY_SOURCE.is_file():
        raise RuntimeError(f"missing treasury source art: {TREASURY_SOURCE.relative_to(ROOT)}")
    with Image.open(TREASURY_SOURCE) as source_image:
        source = source_image.convert("RGBA")
    glyph = _fit_glyph(source, (22, 22))
    output = Image.new("RGBA", TREASURY_ICON_SIZE, (0, 0, 0, 0))
    output.alpha_composite(
        glyph,
        ((TREASURY_ICON_SIZE[0] - glyph.width) // 2, (TREASURY_ICON_SIZE[1] - glyph.height) // 2),
    )
    return output


def _extended_topbar_background() -> Image.Image:
    """Build A-Discord's dark gunmetal topbar on the engine's native canvas.

    The source is retained only as a size contract for the game sprite.  The
    visible pixels are rebuilt from scratch so the upper bar, flag recess and
    lower toolbar shelf form one coherent skin.  The source's full native
    canvas stays intact, but the unused centre is transparent after the shelf's
    shallow diagonal cap instead of becoming an empty screen-wide strip.
    """
    if not TOPBAR_BACKGROUND_SOURCE.is_file():
        raise RuntimeError(
            f"missing extended-topbar source art: {TOPBAR_BACKGROUND_SOURCE.relative_to(ROOT)}"
        )
    with Image.open(TOPBAR_BACKGROUND_SOURCE) as source_image:
        source_size = source_image.size
    if source_size != (2346, 87):
        raise RuntimeError(
            f"extended-topbar source must remain 2346x87, got {source_size[0]}x{source_size[1]}"
        )

    width, height = source_size
    upper_bottom = 43
    shelf_right_top = 1116
    shelf_right_bottom = 1074
    shelf_bottom = 84
    upper_right = shelf_right_top

    mask = Image.new("L", source_size, 0)
    mask_draw = ImageDraw.Draw(mask)
    # The visible upper rail ends in a small machined chamfer instead of a raw
    # alpha cut.  It then flows directly into the lower shelf's diagonal cap.
    mask_draw.polygon(
        ((0, 0), (upper_right - 6, 0), (upper_right, 6), (upper_right, upper_bottom), (0, upper_bottom)),
        fill=255,
    )
    mask_draw.polygon(
        (
            (0, upper_bottom),
            (shelf_right_top, upper_bottom),
            (shelf_right_bottom, shelf_bottom),
            (0, shelf_bottom),
        ),
        fill=255,
    )

    output = Image.new("RGBA", source_size, (0, 0, 0, 0))
    pixels = output.load()
    alpha = mask.load()
    for y in range(height):
        if y <= upper_bottom:
            shade = 36 - round(17 * y / upper_bottom)
        else:
            shade = 31 - round(16 * (y - upper_bottom) / (shelf_bottom - upper_bottom))
        for x in range(width):
            if not alpha[x, y]:
                continue
            # Deterministic fine grain and long horizontal brushing keep the
            # metal alive at 1:1 without producing noisy compression artefacts.
            grain = ((x * 19 + y * 47 + (x ^ (y * 13))) % 9) - 4
            brush = 2 if (x // 37 + y // 3) % 11 == 0 else 0
            pixels[x, y] = (
                max(0, shade - 4 + grain + brush),
                max(0, shade + grain + brush),
                max(0, shade + 3 + grain + brush),
                250,
            )

    draw = ImageDraw.Draw(output)
    black = (5, 7, 8, 255)
    deep = (12, 16, 18, 255)
    steel = (83, 94, 96, 255)
    steel_soft = (51, 61, 63, 255)
    cyan = (39, 112, 116, 220)
    cyan_dark = (18, 55, 59, 255)
    brass = (151, 118, 49, 255)

    # Upper rail and its restrained panel breaks.
    draw.line((1, 1, upper_right - 2, 1), fill=black, width=2)
    draw.line((2, 3, upper_right - 3, 3), fill=steel, width=1)
    draw.line((2, 4, upper_right - 3, 4), fill=deep, width=1)
    draw.line((0, upper_bottom - 2, upper_right, upper_bottom - 2), fill=steel_soft, width=1)
    draw.line((0, upper_bottom - 1, upper_right, upper_bottom - 1), fill=black, width=2)
    for seam_x in (98, 620):
        draw.line((seam_x, 4, seam_x, upper_bottom - 3), fill=black, width=2)
        draw.line((seam_x + 2, 5, seam_x + 2, upper_bottom - 4), fill=steel_soft, width=1)

    # Recessed flag bay, with the same cold-metal and brass vocabulary as the
    # custom toolbar glyphs.
    draw.rectangle((3, 4, 98, 82), fill=(9, 13, 15, 252), outline=black, width=2)
    draw.line((6, 6, 95, 6), fill=steel, width=1)
    draw.line((6, 7, 6, 79), fill=steel_soft, width=1)
    draw.line((96, 7, 96, 79), fill=black, width=1)
    draw.rectangle((9, 10, 96, 68), fill=(6, 9, 11, 255), outline=deep, width=1)

    # A shallow mounting plinth remains visible below the 80x52 country flag.
    # Its stepped bevel removes the old empty black gap without competing with
    # the flag colours or the alert row beside it.
    draw.polygon(((9, 69), (96, 69), (92, 80), (12, 80)), fill=(22, 28, 30, 255))
    draw.line((9, 69, 96, 69), fill=steel, width=1)
    draw.line((12, 78, 92, 78), fill=black, width=1)
    draw.line((13, 79, 91, 79), fill=cyan_dark, width=1)
    draw.rectangle((39, 71, 61, 75), fill=(8, 12, 14, 255), outline=steel_soft, width=1)
    draw.line((42, 73, 58, 73), fill=brass, width=1)
    draw.line((7, 81, 95, 81), fill=cyan_dark, width=1)

    # Lower shelf: a long continuous backing for every toolbar and alert icon.
    draw.line((98, upper_bottom + 1, shelf_right_top - 2, upper_bottom + 1), fill=steel_soft, width=1)
    draw.line((99, upper_bottom + 2, shelf_right_top - 3, upper_bottom + 2), fill=deep, width=1)
    draw.line(
        ((0, shelf_bottom), (shelf_right_bottom, shelf_bottom), (shelf_right_top, upper_bottom)),
        fill=black,
        width=3,
    )
    draw.line(
        ((3, shelf_bottom - 3), (shelf_right_bottom - 2, shelf_bottom - 3), (shelf_right_top - 4, upper_bottom + 1)),
        fill=steel_soft,
        width=1,
    )
    # Close the shortened bar with the same cyan double rule as its lower
    # edge.  The inner line rises up the terminal edge and folds into the top
    # chamfer, so the cut reads as a deliberate frame rather than a missing
    # piece of texture.
    draw.line(
        (
            (100, shelf_bottom - 5),
            (shelf_right_bottom - 5, shelf_bottom - 5),
            (upper_right - 4, upper_bottom + 1),
            (upper_right - 4, 8),
        ),
        fill=cyan_dark,
        width=2,
    )
    draw.line(
        (
            (100, shelf_bottom - 6),
            (shelf_right_bottom - 6, shelf_bottom - 6),
            (upper_right - 6, upper_bottom + 1),
            (upper_right - 6, 8),
            (upper_right - 9, 5),
        ),
        fill=cyan,
        width=1,
    )
    draw.line((upper_right - 1, 7, upper_right - 1, upper_bottom - 1), fill=black, width=2)
    draw.line((upper_right - 3, 8, upper_right - 3, upper_bottom - 2), fill=steel_soft, width=1)

    # Small recessed separators make the large surface read as manufactured
    # panels while remaining quiet behind the densely packed controls.
    for seam_x in (100, 620):
        draw.line((seam_x, upper_bottom + 3, seam_x, shelf_bottom - 5), fill=black, width=2)
        draw.line((seam_x + 2, upper_bottom + 4, seam_x + 2, shelf_bottom - 7), fill=steel_soft, width=1)
    for rivet_x, rivet_y in ((9, 9), (91, 9), (9, 76), (91, 76), (1105, 48)):
        draw.ellipse((rivet_x - 2, rivet_y - 2, rivet_x + 2, rivet_y + 2), fill=black)
        draw.point((rivet_x - 1, rivet_y - 1), fill=brass)
        draw.point((rivet_x, rivet_y), fill=steel)

    output.putalpha(mask)
    return output


def _gunmetal_from_mask(mask: Image.Image) -> Image.Image:
    """Paint a deterministic blue-black brushed-metal surface through ``mask``."""
    width, height = mask.size
    output = Image.new("RGBA", mask.size, (0, 0, 0, 0))
    alpha = mask.load()
    pixels = output.load()
    span = max(1, height - 1)
    for y in range(height):
        shade = 34 - round(17 * y / span)
        for x in range(width):
            if not alpha[x, y]:
                continue
            grain = ((x * 23 + y * 41 + (x ^ (y * 17))) % 9) - 4
            brush = 2 if (x // 29 + y // 2) % 13 == 0 else 0
            pixels[x, y] = (
                max(0, shade - 4 + grain + brush),
                max(0, shade + grain + brush),
                max(0, shade + 4 + grain + brush),
                255,
            )
    output.putalpha(mask)
    return output


def _stateview_chamfered_mask(size: tuple[int, int], chamfer: int) -> Image.Image:
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


def _stateview_panel(
    draw: ImageDraw.ImageDraw,
    box: tuple[int, int, int, int],
    *,
    accent: tuple[int, int, int, int] = (18, 63, 67, 255),
    fill: tuple[int, int, int, int] = (10, 15, 17, 248),
) -> None:
    left, top, right, bottom = box
    draw.rectangle(box, fill=fill, outline=(4, 6, 7, 255), width=2)
    draw.line((left + 3, top + 2, right - 3, top + 2), fill=(67, 79, 81, 255), width=1)
    draw.line((left + 3, bottom - 2, right - 3, bottom - 2), fill=accent, width=1)


def _stateview_background(size: tuple[int, int]) -> Image.Image:
    """Build one legible instrument panel around the unchanged state-view layout."""
    width, height = size
    mask = _stateview_chamfered_mask(size, 7)
    output = _gunmetal_from_mask(mask)
    draw = ImageDraw.Draw(output)
    black = (4, 6, 7, 255)
    deep = (8, 12, 14, 255)
    steel = (78, 90, 92, 255)
    steel_soft = (43, 54, 56, 255)
    cyan = (39, 124, 128, 240)
    cyan_dark = (17, 59, 63, 255)
    brass = (166, 125, 43, 255)

    outer = (
        (7, 1),
        (width - 8, 1),
        (width - 2, 7),
        (width - 2, height - 8),
        (width - 8, height - 2),
        (7, height - 2),
        (1, height - 8),
        (1, 7),
        (7, 1),
    )
    draw.line(outer, fill=black, width=3)
    draw.line((10, 3, width - 11, 3), fill=steel, width=1)
    draw.line((3, 10, 3, height - 11), fill=cyan_dark, width=2)
    draw.line((5, 14, 5, height - 15), fill=cyan, width=1)
    draw.line((10, height - 4, width - 11, height - 4), fill=cyan_dark, width=2)
    draw.line((15, height - 5, width - 16, height - 5), fill=cyan, width=1)

    # Title rail: a quiet machined header instead of the vanilla antlers.
    _stateview_panel(draw, (7, 6, width - 8, 35), accent=cyan_dark, fill=(7, 11, 13, 255))
    draw.line((75, 31, width - 52, 31), fill=cyan, width=1)
    draw.line((18, 12, 67, 12), fill=steel_soft, width=1)
    draw.line((width - 75, 12, width - 45, 12), fill=steel_soft, width=1)
    for x in (14, width - 15):
        draw.ellipse((x - 2, 17, x + 2, 21), fill=black)
        draw.point((x, 19), fill=brass)

    # Owner/claims rail and the compact state statistics bay.
    _stateview_panel(draw, (8, 37, 144, 116), accent=steel_soft)
    draw.line((11, 83, 141, 83), fill=steel_soft, width=1)
    _stateview_panel(draw, (8, 118, 144, 398), accent=cyan_dark, fill=(11, 18, 19, 250))
    draw.rounded_rectangle((17, 151, 137, 185), radius=4, fill=deep, outline=steel_soft, width=1)
    draw.line((20, 183, 134, 183), fill=cyan_dark, width=1)
    for y in (205, 263):
        draw.line((13, y, 139, y), fill=(31, 43, 45, 255), width=1)
    # State resources are emitted by a hard-coded grid whose nominal
    # transparent background is not actually rendered.  Bake a quiet two-by-
    # four instrument bay underneath its unchanged icon/value positions.
    _stateview_panel(draw, (13, 267, 140, 396), accent=cyan_dark, fill=(7, 12, 14, 252))
    draw.line((18, 273, 135, 273), fill=brass, width=1)
    draw.line((76, 278, 76, 391), fill=(30, 42, 44, 255), width=1)
    for y in (303, 333, 363):
        draw.line((18, y, 135, y), fill=(30, 42, 44, 255), width=1)

    # Fixed state buildings, slot counter and the five-by-five shared grid.
    _stateview_panel(draw, (146, 37, width - 8, 119), accent=cyan_dark)
    for x in range(153, 454, 60):
        draw.line((x, 42, x, 114), fill=(26, 36, 38, 255), width=1)
    _stateview_panel(draw, (146, 120, width - 8, 151), accent=brass, fill=(8, 13, 15, 255))
    draw.rounded_rectangle((390, 123, 449, 148), radius=4, fill=deep, outline=steel_soft, width=1)
    draw.line((394, 146, 445, 146), fill=cyan_dark, width=1)
    _stateview_panel(draw, (146, 152, width - 8, 398), accent=cyan_dark, fill=(8, 13, 15, 252))
    for column in range(1, 5):
        x = 149 + column * 61
        draw.line((x, 157, x, 393), fill=(23, 32, 34, 255), width=1)
    for row in range(1, 5):
        y = 157 + row * 48
        draw.line((151, y, width - 13, y), fill=(23, 32, 34, 255), width=1)

    # State modifiers remain a distinct rail instead of a loose label on black.
    _stateview_panel(draw, (8, 400, width - 8, 447), accent=cyan_dark)
    draw.line((17, 423, width - 18, 423), fill=(27, 39, 41, 255), width=1)
    draw.rectangle((421, 407, 451, 439), fill=deep, outline=steel_soft, width=1)

    if height >= 600:
        # Expanded province module used by the current game version.
        _stateview_panel(draw, (8, 449, width - 8, 480), accent=brass, fill=(8, 13, 15, 255))
        draw.line((18, 477, width - 18, 477), fill=cyan_dark, width=1)
        _stateview_panel(draw, (23, 481, width - 13, 555), accent=cyan_dark, fill=(5, 9, 11, 255))
        _stateview_panel(draw, (8, 557, width - 8, height - 7), accent=cyan_dark, fill=(5, 8, 10, 255))
        draw.line((16, 563, width - 16, 563), fill=steel_soft, width=1)
    else:
        _stateview_panel(draw, (8, 449, width - 8, height - 7), accent=cyan_dark, fill=(6, 10, 12, 255))

    output.putalpha(mask)
    return output


def _stateview_standing_entry(size: tuple[int, int]) -> Image.Image:
    width, height = size
    # The current five-column grid advances by only 60x52 while the engine
    # retains 62x84/61x100 canvases.  Keep those native canvases, but leave a
    # real alpha gutter around the visible card so neighbouring entries and
    # the shared-slot header never paint over one another.
    visible_bottom = 80 if height == 84 else 96
    mask = Image.new("L", size, 0)
    mask_draw = ImageDraw.Draw(mask)
    # The building strip already supplies its own 46x46 framed icon at x=12.
    # Only retain two mounting brackets and the level shelf beneath it.
    mask_draw.rectangle((7, 5, 11, 49), fill=255)
    mask_draw.rectangle((width - 4, 5, width - 3, 49), fill=255)
    mask_draw.polygon(
        (
            (6, 50),
            (width - 7, 50),
            (width - 3, 54),
            (width - 3, visible_bottom - 5),
            (width - 7, visible_bottom - 1),
            (6, visible_bottom - 1),
            (2, visible_bottom - 5),
            (2, 54),
        ),
        fill=255,
    )
    output = _gunmetal_from_mask(mask)
    draw = ImageDraw.Draw(output)
    draw.line((8, 6, 8, 48), fill=(56, 69, 71, 255), width=1)
    draw.line((width - 3, 7, width - 3, 47), fill=(18, 68, 72, 255), width=1)
    shelf_outline = (
        (6, 50),
        (width - 7, 50),
        (width - 3, 54),
        (width - 3, visible_bottom - 5),
        (width - 7, visible_bottom - 1),
        (6, visible_bottom - 1),
        (2, visible_bottom - 5),
        (2, 54),
        (6, 50),
    )
    draw.line(shelf_outline, fill=(4, 6, 7, 255), width=2)
    draw.rectangle((8, 52, width - 7, visible_bottom - 6), fill=(8, 12, 14, 255), outline=(39, 49, 51, 255), width=1)
    draw.line((11, visible_bottom - 5, width - 10, visible_bottom - 5), fill=(156, 117, 39, 255), width=1)
    output.putalpha(mask)
    return output


def _stateview_building_entry() -> Image.Image:
    size = STATEVIEW_OUTPUT_SIZES[STATEVIEW_BUILDING_ENTRY]
    output = Image.new("RGBA", size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(output)
    for left, right in ((0, 54), (55, 109)):
        draw.rounded_rectangle((left + 1, 1, right - 1, 48), radius=4, fill=(6, 10, 12, 255), outline=(48, 61, 63, 255), width=1)
        draw.line((left + 6, 45, right - 6, 45), fill=(18, 67, 71, 255), width=1)
    return output


def _stateview_slot(size: tuple[int, int], *, brass: bool = False) -> Image.Image:
    width, height = size
    mask = _stateview_chamfered_mask(size, 4)
    output = _gunmetal_from_mask(mask)
    draw = ImageDraw.Draw(output)
    draw.line(((4, 1), (width - 5, 1), (width - 2, 4), (width - 2, height - 5), (width - 5, height - 2), (4, height - 2), (1, height - 5), (1, 4), (4, 1)), fill=(4, 6, 7, 255), width=2)
    # No second inner frame here: occupied slots receive the already framed
    # building-strip art, while empty and locked slots keep this backing.
    draw.line((5, 4, width - 6, 4), fill=(49, 61, 63, 255), width=1)
    draw.line((4, 7, 4, height - 9), fill=(31, 43, 45, 255), width=1)
    accent = (159, 119, 39, 255) if brass else (22, 83, 87, 255)
    draw.line((8, height - 5, width - 9, height - 5), fill=accent, width=1)
    return output


def _stateview_province_header() -> Image.Image:
    width, height = STATEVIEW_OUTPUT_SIZES[STATEVIEW_PROVINCE_HEADER]
    output = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(output)
    draw.polygon(((5, 0), (width - 6, 0), (width - 1, 5), (width - 1, height - 3), (2, height - 3), (2, 3)), fill=(7, 12, 14, 246))
    draw.line((7, 1, width - 8, 1), fill=(70, 82, 84, 255), width=1)
    draw.line((8, height - 4, width - 8, height - 4), fill=(27, 102, 106, 240), width=1)
    draw.point((8, 8), fill=(164, 123, 42, 255))
    return output


def _stateview_population_icon() -> Image.Image:
    output = Image.new("RGBA", STATEVIEW_OUTPUT_SIZES[STATEVIEW_POPULATION_ICON], (0, 0, 0, 0))
    draw = ImageDraw.Draw(output)
    draw.ellipse((1, 1, 30, 30), fill=(4, 7, 8, 255), outline=(74, 87, 89, 255), width=1)
    draw.ellipse((4, 4, 27, 27), fill=(9, 15, 17, 255), outline=(20, 72, 76, 255), width=1)
    pale = (201, 210, 207, 255)
    draw.ellipse((8, 8, 13, 13), fill=pale)
    draw.ellipse((18, 8, 23, 13), fill=pale)
    draw.polygon(((5, 24), (7, 15), (14, 15), (16, 24)), fill=pale)
    draw.polygon(((16, 24), (18, 15), (25, 15), (27, 24)), fill=(126, 140, 139, 255))
    draw.line((7, 27, 25, 27), fill=(39, 127, 131, 255), width=1)
    return output


def _stateview_value_background() -> Image.Image:
    output = Image.new("RGBA", STATEVIEW_OUTPUT_SIZES[STATEVIEW_VALUE_BG], (0, 0, 0, 0))
    draw = ImageDraw.Draw(output)
    draw.rounded_rectangle((1, 2, 42, 23), radius=7, fill=(4, 7, 8, 255), outline=(62, 74, 76, 255), width=1)
    draw.rounded_rectangle((4, 5, 39, 20), radius=5, fill=(9, 14, 16, 255), outline=(26, 56, 59, 255), width=1)
    draw.line((8, 21, 35, 21), fill=(39, 124, 128, 230), width=1)
    return output


def _stateview_resource_background() -> Image.Image:
    size = STATEVIEW_OUTPUT_SIZES[STATEVIEW_RESOURCE_BG]
    mask = _stateview_chamfered_mask(size, 5)
    output = _gunmetal_from_mask(mask)
    draw = ImageDraw.Draw(output)
    draw.line(((5, 1), (149, 1), (153, 5), (153, 57), (149, 61), (5, 61), (1, 57), (1, 5), (5, 1)), fill=(4, 6, 7, 255), width=2)
    draw.line((7, 58, 147, 58), fill=(18, 67, 71, 255), width=1)
    return output


def _right_cluster_background() -> Image.Image:
    """Replace the ornate vanilla right cluster with an A-Discord instrument dock."""
    mask = Image.new("L", RIGHT_CLUSTER_SIZE, 0)
    mask_draw = ImageDraw.Draw(mask)
    mask_draw.rounded_rectangle((0, 1, 248, 36), radius=12, fill=255)
    mask_draw.polygon(((27, 37), (250, 37), (267, 51), (267, 82), (250, 94), (56, 94), (27, 73)), fill=255)
    mask_draw.rounded_rectangle((244, 0, 310, 98), radius=11, fill=255)
    mask_draw.rounded_rectangle((307, 0, 341, 100), radius=8, fill=255)

    output = _gunmetal_from_mask(mask)
    draw = ImageDraw.Draw(output)
    black = (5, 7, 8, 255)
    deep = (11, 15, 17, 255)
    steel = (84, 95, 97, 255)
    steel_soft = (48, 60, 62, 255)
    cyan = (42, 124, 128, 235)
    cyan_dark = (17, 58, 62, 255)
    brass = (157, 121, 48, 255)

    # Date cradle.
    draw.rounded_rectangle((0, 1, 248, 36), radius=12, outline=black, width=2)
    draw.line((13, 3, 238, 3), fill=steel, width=1)
    draw.line((13, 34, 238, 34), fill=cyan_dark, width=2)
    draw.line((17, 33, 234, 33), fill=cyan, width=1)

    # Music/army/navy/air shelf. The controls keep their original names and
    # hitboxes; these circles are only recessed sockets behind them.
    lower_outline = ((27, 38), (250, 38), (266, 52), (266, 81), (249, 93), (56, 93), (28, 72))
    draw.line(lower_outline + (lower_outline[0],), fill=black, width=2)
    draw.line(((57, 90), (247, 90), (262, 79)), fill=cyan_dark, width=2)
    draw.line(((60, 89), (245, 89), (261, 78)), fill=cyan, width=1)
    for center_x, radius in ((49, 18), (82, 12), (125, 20), (174, 20), (220, 20)):
        center_y = 64
        draw.ellipse(
            (center_x - radius, center_y - radius, center_x + radius, center_y + radius),
            fill=deep,
            outline=black,
            width=2,
        )
        draw.arc(
            (center_x - radius + 2, center_y - radius + 2, center_x + radius - 2, center_y + radius - 2),
            205,
            335,
            fill=cyan_dark,
            width=2,
        )

    # DEFCON has its own vertical instrument bay; the TFR texture supplies the
    # coloured number and label, while the engine still supplies the percent.
    draw.rounded_rectangle((244, 0, 310, 98), radius=11, fill=(18, 29, 33, 255), outline=black, width=2)
    draw.rounded_rectangle((247, 3, 307, 95), radius=9, fill=(10, 20, 23, 255), outline=cyan_dark, width=2)
    draw.rounded_rectangle((250, 6, 304, 92), radius=7, outline=steel_soft, width=1)
    draw.line((251, 70, 303, 70), fill=cyan_dark, width=1)
    draw.line((253, 92, 301, 92), fill=cyan, width=1)
    for rivet_x, rivet_y in ((252, 8), (302, 8), (252, 90), (302, 90)):
        draw.ellipse((rivet_x - 1, rivet_y - 1, rivet_x + 1, rivet_y + 1), fill=black)
        draw.point((rivet_x, rivet_y), fill=brass)

    # Compact vertical system rail for menu, help and dismissed alerts.
    draw.rounded_rectangle((307, 0, 341, 100), radius=8, fill=(10, 14, 16, 255), outline=black, width=2)
    draw.line((309, 5, 309, 95), fill=steel_soft, width=1)
    draw.line((338, 6, 338, 94), fill=cyan_dark, width=1)
    for center_y in (19, 46, 74):
        draw.ellipse((310, center_y - 14, 338, center_y + 14), fill=deep, outline=steel_soft, width=1)
    return output


def _round_control_icon(
    size: int,
    glyph: str,
    accent: tuple[int, int, int, int],
    *,
    rim_accent: bool = True,
) -> Image.Image:
    """Create one compact control that remains readable under buttonstate.lua."""
    output = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(output)
    black = (4, 6, 7, 255)
    steel = (89, 101, 103, 255)
    steel_soft = (48, 60, 62, 255)
    pale = (215, 221, 216, 255)
    margin = 1
    draw.ellipse((margin, margin, size - margin - 1, size - margin - 1), fill=black, outline=steel, width=1)
    draw.ellipse((3, 3, size - 4, size - 4), fill=(12, 17, 19, 255), outline=steel_soft, width=1)
    if rim_accent:
        draw.arc((4, 4, size - 5, size - 5), 205, 335, fill=(28, 104, 108, 255), width=2)
    cx = size // 2

    if glyph == "minus":
        draw.line((cx - 6, cx, cx + 6, cx), fill=accent, width=2)
    elif glyph == "plus":
        draw.line((cx - 6, cx, cx + 6, cx), fill=accent, width=2)
        draw.line((cx, cx - 6, cx, cx + 6), fill=accent, width=2)
    elif glyph == "menu":
        for y in (7, 12, 17):
            draw.line((7, y, size - 8, y), fill=pale, width=2)
    elif glyph == "help":
        glyph_x = cx - 1
        draw.arc((7, 6, size - 9, 14), 185, 360, fill=pale, width=2)
        draw.arc((7, 6, size - 9, 14), 0, 60, fill=pale, width=2)
        draw.line((glyph_x + 3, 12, glyph_x, 16), fill=pale, width=2)
        draw.ellipse((glyph_x - 1, 18, glyph_x + 1, 20), fill=accent)
    elif glyph == "alert":
        draw.line((cx, 6, cx, 14), fill=accent, width=3)
        draw.ellipse((cx - 1, 17, cx + 1, 19), fill=pale)
    elif glyph == "trophy":
        draw.polygon(((7, 6), (size - 8, 6), (size - 10, 13), (cx, 16), (9, 13)), fill=accent)
        draw.line((cx, 15, cx, 19), fill=pale, width=2)
        draw.line((cx - 4, 20, cx + 4, 20), fill=pale, width=2)
        draw.arc((4, 7, 10, 14), 90, 270, fill=pale, width=1)
        draw.arc((size - 11, 7, size - 5, 14), 270, 90, fill=pale, width=1)
    elif glyph == "music":
        draw.line((cx + 3, 7, cx + 3, size - 10), fill=pale, width=2)
        draw.line((cx + 3, 7, cx + 8, 9), fill=accent, width=2)
        draw.ellipse((cx - 3, size - 11, cx + 3, size - 6), fill=accent)
    else:
        raise RuntimeError(f"unknown topbar control glyph: {glyph}")
    return output


def _topbar_flag_frame_overlay() -> Image.Image:
    """Frame the full 82x52 country flag without masking or scaling it."""
    scale = 4
    width, height = TOPBAR_FLAG_FRAME_SIZE
    output = Image.new("RGBA", (width * scale, height * scale), (0, 0, 0, 0))
    draw = ImageDraw.Draw(output)

    def points(coords: tuple[tuple[int, int], ...]) -> tuple[tuple[int, int], ...]:
        return tuple((x * scale, y * scale) for x, y in coords)

    outer = points(((3, 0), (84, 0), (87, 3), (87, 54), (84, 57), (3, 57), (0, 54), (0, 3)))
    inner = points(((6, 3), (81, 3), (84, 6), (84, 51), (81, 54), (6, 54), (3, 51), (3, 6)))
    draw.polygon(outer, fill=(4, 7, 8, 246))
    draw.line(outer + (outer[0],), fill=(74, 87, 89, 255), width=scale)
    draw.polygon(inner, fill=(0, 0, 0, 0))
    draw.line(inner + (inner[0],), fill=(12, 46, 50, 245), width=scale)

    cyan_dark = (20, 80, 84, 235)
    cyan = (43, 135, 139, 230)
    brass = (151, 116, 47, 235)
    draw.line(points(((6, 54), (81, 54))), fill=cyan_dark, width=2 * scale)
    draw.line(points(((9, 53), (78, 53))), fill=cyan, width=scale)
    for corner in (
        ((5, 14), (5, 6), (13, 6)),
        ((74, 6), (82, 6), (82, 14)),
        ((5, 43), (5, 51), (13, 51)),
        ((74, 51), (82, 51), (82, 43)),
    ):
        draw.line(points(corner), fill=cyan_dark, width=scale)
    for x, y in ((4, 4), (83, 4), (4, 53), (83, 53)):
        draw.ellipse(
            ((x * scale) - scale, (y * scale) - scale, (x * scale) + scale, (y * scale) + scale),
            fill=(3, 5, 6, 255),
        )
        draw.point((x * scale, y * scale), fill=brass)

    return output.resize(TOPBAR_FLAG_FRAME_SIZE, Image.Resampling.LANCZOS)


def _topbar_flag_alpha_mask() -> Image.Image:
    """Clip the native 82x52 dynamic flag with a real antialiased alpha mask."""
    scale = 4
    width, height = TOPBAR_FLAG_MASK_SIZE
    alpha_large = Image.new("L", (width * scale, height * scale), 0)
    draw = ImageDraw.Draw(alpha_large)
    chamfered_flag = (
        (3 * scale, 0),
        ((width - 4) * scale, 0),
        ((width - 1) * scale, 3 * scale),
        ((width - 1) * scale, (height - 4) * scale),
        ((width - 4) * scale, (height - 1) * scale),
        (3 * scale, (height - 1) * scale),
        (0, (height - 4) * scale),
        (0, 3 * scale),
    )
    draw.polygon(chamfered_flag, fill=255)
    alpha = alpha_large.resize(TOPBAR_FLAG_MASK_SIZE, Image.Resampling.LANCZOS)
    output = Image.new("RGBA", TOPBAR_FLAG_MASK_SIZE, (255, 255, 255, 0))
    output.putalpha(alpha)
    return output


def _topbar_flag_plasma_overlay() -> Image.Image:
    """Treat the topbar flag as a clean plasma display without fabric folds."""
    width, height = TOPBAR_FLAG_OVERLAY_SIZE
    output = Image.new("RGBA", TOPBAR_FLAG_OVERLAY_SIZE, (0, 0, 0, 0))
    pixels = output.load()
    centre_x = (width - 1) / 2
    centre_y = (height - 1) / 2
    for y in range(height):
        for x in range(width):
            nx = abs(x - centre_x) / centre_x
            ny = abs(y - centre_y) / centre_y
            glass_edge = max(0, round((max(nx, ny) - 0.72) * 118))
            hard_edge = max(0, 30 - min(x, y, width - 1 - x, height - 1 - y) * 10)
            panel_tint = 5 + round(3 * y / max(1, height - 1))
            static = 2 if (x * 17 + y * 29 + (x ^ y)) % 31 == 0 else 0
            alpha = min(105, glass_edge + hard_edge + panel_tint + static)
            pixels[x, y] = (3, 9, 12, alpha)

    scale = 4
    glass = output.resize((width * scale, height * scale), Image.Resampling.NEAREST)
    draw = ImageDraw.Draw(glass, "RGBA")

    def box(coords: tuple[int, int, int, int]) -> tuple[int, int, int, int]:
        return tuple(value * scale for value in coords)

    # A wide flat-glass reflection above and a restrained cold emitter line
    # below make the flag read as a plasma panel without covering heraldry.
    draw.rounded_rectangle(box((8, 3, 73, 11)), radius=4 * scale, fill=(180, 215, 211, 13))
    draw.line((13 * scale, 4 * scale, 68 * scale, 4 * scale), fill=(213, 230, 225, 18), width=scale)
    draw.line((7 * scale, 46 * scale, 74 * scale, 46 * scale), fill=(22, 89, 94, 18), width=2 * scale)
    draw.line((7 * scale, 48 * scale, 74 * scale, 48 * scale), fill=(36, 134, 139, 32), width=scale)
    draw.line((13 * scale, 49 * scale, 68 * scale, 49 * scale), fill=(70, 176, 176, 18), width=scale)
    return glass.resize(TOPBAR_FLAG_OVERLAY_SIZE, Image.Resampling.LANCZOS)


def _date_control_panel(symbol: str, pulse: bool = False) -> Image.Image:
    output = Image.new("RGBA", DATE_CONTROL_SIZE, (0, 0, 0, 0))
    mask = Image.new("L", DATE_CONTROL_SIZE, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, 205, 27), radius=13, fill=255)
    output.alpha_composite(_gunmetal_from_mask(mask))
    draw = ImageDraw.Draw(output)
    draw.rounded_rectangle((0, 0, 205, 27), radius=13, outline=(4, 6, 7, 255), width=2)
    draw.line((12, 3, 193, 3), fill=(82, 94, 96, 255), width=1)
    draw.line((12, 24, 193, 24), fill=(20, 74, 78, 255), width=2)
    draw.line((16, 23, 189, 23), fill=(45, 130, 134, 230), width=1)
    if symbol == "play":
        draw.polygon(((31, 8), (31, 20), (42, 14)), fill=(65, 193, 160, 255))
    elif symbol == "pause":
        colour = (224, 171, 60, 255) if pulse else (181, 139, 49, 255)
        draw.rectangle((31, 8, 34, 20), fill=colour)
        draw.rectangle((39, 8, 42, 20), fill=colour)
    else:
        raise RuntimeError(f"unknown date control symbol: {symbol}")
    return output


def _paused_date_strip() -> Image.Image:
    output = Image.new("RGBA", (DATE_CONTROL_SIZE[0] * 2, DATE_CONTROL_SIZE[1]), (0, 0, 0, 0))
    output.alpha_composite(_date_control_panel("pause", pulse=False), (0, 0))
    output.alpha_composite(_date_control_panel("pause", pulse=True), (DATE_CONTROL_SIZE[0], 0))
    return output


def _speed_step_strip() -> Image.Image:
    output = Image.new("RGBA", (84, 10), (0, 0, 0, 0))
    colours = ((40, 48, 50, 255), (42, 137, 141, 255), (181, 130, 47, 255))
    draw = ImageDraw.Draw(output)
    for frame, colour in enumerate(colours):
        left = frame * 28
        draw.rounded_rectangle((left + 1, 1, left + 26, 8), radius=3, fill=(5, 7, 8, 255), outline=(74, 86, 88, 255))
        draw.rounded_rectangle((left + 3, 3, left + 24, 6), radius=2, fill=colour)
    return output


def _dds_bytes(image: Image.Image) -> bytes:
    stream = BytesIO()
    image.save(stream, format="DDS")
    return stream.getvalue()


def _tga_bytes(image: Image.Image) -> bytes:
    stream = BytesIO()
    image.save(stream, format="TGA")
    return stream.getvalue()


def expected_outputs() -> dict[Path, bytes]:
    outputs = {
        RESOURCE_STRIP: _dds_bytes(_resource_strip()),
        MISSING_STRIP: _dds_bytes(_missing_strip()),
        TOPBAR_BUTTON: _dds_bytes(_topbar_button(6, (55, 41))),
        TREASURY_ICON: _dds_bytes(_treasury_icon()),
        TRADE_ENTRY: _dds_bytes(_trade_entry_background()),
        INTERNATIONAL_MARKET_BUTTON: _dds_bytes(_international_market_button()),
        WORLD_TENSION_ICON: _defcon_strip_bytes(),
        # GFX_command_power is duplicated by the engine's topbar and texticon
        # registries, so both native paths must carry the same bright telephone.
        COMMAND_POWER_ICON: _dds_bytes(_command_power_icon((24, 22))),
        COMMAND_POWER_TEXTICON: _dds_bytes(_command_power_icon((22, 20))),
        TOPBAR_BACKGROUND: _dds_bytes(_extended_topbar_background()),
        RIGHT_CLUSTER_BACKGROUND: _dds_bytes(_right_cluster_background()),
        DATE_CONTROL_BACKGROUND: _dds_bytes(_date_control_panel("play")),
        DATE_CONTROL_PAUSED: _dds_bytes(_paused_date_strip()),
        SPEED_DOWN_BUTTON: _dds_bytes(_round_control_icon(27, "minus", (220, 168, 56, 255))),
        SPEED_UP_BUTTON: _dds_bytes(_round_control_icon(27, "plus", (65, 188, 163, 255))),
        SPEED_STEP_BUTTON: _dds_bytes(_speed_step_strip()),
        MENU_BUTTON: _dds_bytes(
            _round_control_icon(24, "menu", (65, 188, 163, 255), rim_accent=False)
        ),
        HELP_BUTTON: _dds_bytes(
            _round_control_icon(24, "help", (220, 168, 56, 255), rim_accent=False)
        ),
        ACHIEVEMENTS_BUTTON: _dds_bytes(_round_control_icon(24, "trophy", (220, 168, 56, 255))),
        PLAYLIST_BUTTON: _dds_bytes(_round_control_icon(33, "music", (220, 168, 56, 255))),
        DISMISSED_ALERTS_BUTTON: _dds_bytes(
            _round_control_icon(24, "alert", (214, 91, 65, 255), rim_accent=False)
        ),
        TOPBAR_FLAG_FRAME: _dds_bytes(_topbar_flag_frame_overlay()),
        TOPBAR_FLAG_OVERLAY: _dds_bytes(_topbar_flag_plasma_overlay()),
        TOPBAR_FLAG_MASK: _tga_bytes(_topbar_flag_alpha_mask()),
    }
    for relative_path, index in MAIN_TOPBAR_BUTTONS.items():
        outputs[ROOT / relative_path] = _dds_bytes(_topbar_button(index, (55, 41)))
    for relative_path, index in SMALL_TOPBAR_BUTTONS.items():
        outputs[ROOT / relative_path] = _dds_bytes(_round_topbar_button(index))
    for relative_path, (index, size) in TOPBAR_INDICATORS.items():
        outputs[ROOT / relative_path] = _dds_bytes(_indicator_icon(index, size))
    outputs[INDUSTRY_ICON] = _dds_bytes(_industry_icon_strip())
    outputs[FUEL_ICON] = _dds_bytes(_fuel_icon_strip())
    outputs.update(
        {
            STATEVIEW_WW_BACKGROUND: _dds_bytes(_stateview_background((463, 653))),
            STATEVIEW_BACKGROUND: _dds_bytes(_stateview_background((463, 542))),
            STATEVIEW_WW_ENTRY: _dds_bytes(_stateview_standing_entry((62, 84))),
            STATEVIEW_ENTRY: _dds_bytes(_stateview_standing_entry((61, 100))),
            STATEVIEW_BUILDING_ENTRY: _dds_bytes(_stateview_building_entry()),
            STATEVIEW_LANDMARK_ENTRY: _dds_bytes(_stateview_slot((50, 43), brass=True)),
            STATEVIEW_BUILD_SLOT: _dds_bytes(_stateview_slot((56, 46))),
            STATEVIEW_PROVINCE_HEADER: _dds_bytes(_stateview_province_header()),
            STATEVIEW_POPULATION_ICON: _dds_bytes(_stateview_population_icon()),
            STATEVIEW_VALUE_BG: _dds_bytes(_stateview_value_background()),
            STATEVIEW_RESOURCE_BG: _dds_bytes(_stateview_resource_background()),
        }
    )
    return outputs


def validate(outputs: dict[Path, bytes]) -> list[str]:
    issues: list[str] = []
    for path, expected in outputs.items():
        if not path.is_file():
            issues.append(f"missing generated resource asset: {path.relative_to(ROOT)}")
        elif path.read_bytes() != expected:
            issues.append(f"generated resource asset differs: {path.relative_to(ROOT)}")
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
    print("Strategic resources and core UI assets are current (trade, topbar and state-view skins).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
