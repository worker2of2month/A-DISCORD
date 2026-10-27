"""Build campaign briefing and setup surfaces; country artwork is source art."""

from __future__ import annotations

import argparse
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw

from tools.lib.adiscord_ui_surfaces import apply_or_check
from tools.lib.paths import repository_root


ROOT = repository_root()
OUTPUT = ROOT / 'gfx/interface/startup'
SIZES = {
    'background': (1000, 620),
    'tab': (146, 36),
    'page': (359, 36),
    'launcher': (98, 26),
    'close': (36, 36),
}
PORTRAIT = (220, 440)
# Country portraits cut from existing campaign art at the briefing's 1:2 ratio:
# the desert city of the southern superevent and the oil towers of a loading screen.
PORTRAIT_CROPS = {
    'shl': ('gfx/interface/superevents/NAM/namestnik lost.png', (290, 86, 542, 590)),
    'nam': ('gfx/loadingscreens/load_3.dds', (1180, 0, 1900, 1440)),
}


def frame(size: tuple[int, int], button: bool = False) -> Image.Image:
    width, height = size
    image = Image.new('RGBA', size, (19, 23, 29, 255))
    draw = ImageDraw.Draw(image)
    for y in range(height):
        grain = ((y * 37 + 11) % 7) - 3
        shade = (32 if button else 23) + grain
        draw.line((0, y, width - 1, y), fill=(shade, shade + 4, shade + 9, 255))
    draw.rectangle((0, 0, width - 1, height - 1), outline=(5, 7, 9), width=2)
    draw.rectangle((2, 2, width - 3, height - 3), outline=(92, 101, 111))
    draw.line((4, 4, width - 5, 4), fill=(123, 131, 139))
    draw.line((4, height - 5, width - 5, height - 5), fill=(8, 10, 13))
    if button:
        draw.line((6, 8, 6, height - 9), fill=(177, 151, 103), width=2)
    else:
        # The central recess keeps text contrast independent of frame texture.
        draw.rectangle((18, 54, 981, 555), fill=(13, 17, 22), outline=(57, 66, 76))
        draw.line((24, 55, 975, 55), fill=(5, 8, 11))
        draw.line((34, 49, 190, 49), fill=(177, 151, 103), width=2)
        for x, y in ((11, 11), (988, 11), (11, 608), (988, 608)):
            draw.ellipse(
                (x - 2, y - 2, x + 2, y + 2), fill=(8, 10, 13), outline=(81, 90, 100)
            )
    return image


def setup_surface(size: tuple[int, int], accent=(177, 151, 103), selected=False) -> Image.Image:
    width, height = size
    image = Image.new('RGBA', size, (17, 21, 27, 255))
    draw = ImageDraw.Draw(image)
    for y in range(height):
        shade = 22 + ((y * 19 + 3) % 5) + (8 if selected else 0)
        draw.line((0, y, width - 1, y), fill=(shade, shade + 4, shade + 8))
    draw.rectangle((0, 0, width - 1, height - 1), outline=(5, 7, 10), width=2)
    draw.rectangle((2, 2, width - 3, height - 3), outline=accent if selected else (72, 79, 85))
    draw.line((4, 4, width - 5, 4), fill=accent if selected else (93, 99, 104))
    return image


def setup_outputs() -> tuple[dict[Path, bytes], list[str]]:
    outputs = {}
    definitions = []

    def add(role, image, frames=1, kind='spriteType', effect=None):
        stream = BytesIO()
        image.save(stream, 'PNG')
        outputs[OUTPUT / f'setup_{role}.png'] = stream.getvalue()
        definitions.extend([
            f'\t{kind} = {{',
            f'\t\tname = "GFX_ADISCORD_setup_{role}"',
            f'\t\ttexturefile = "gfx/interface/startup/setup_{role}.png"',
        ])
        if kind == 'corneredTileSpriteType':
            definitions.extend([
                f'\t\tsize = {{ x = {image.width} y = {image.height} }}',
                '\t\tborderSize = { x = 14 y = 14 }',
                '\t\ttilingCenter = yes',
            ])
        else:
            definitions.append(f'\t\tnoOfFrames = {frames}')
        if kind == 'frameAnimatedSpriteType':
            definitions.extend([
                '\t\tanimation_rate_fps = 1.5',
                '\t\tlooping = yes',
                '\t\tplay_on_show = yes',
                '\t\tpause_on_loop = 0.0',
                '\t\talwaystransparent = yes',
            ])
        if effect:
            definitions.append(f'\t\teffectFile = "gfx/FX/{effect}.lua"')
        definitions.append('\t}')

    panel = setup_surface((598, 330))
    draw = ImageDraw.Draw(panel)
    draw.line((16, 39, 581, 39), fill=(177, 151, 103))
    draw.line((16, 242, 581, 242), fill=(72, 79, 85))
    draw.rectangle((16, 248, 581, 276), fill=(15, 19, 24))
    add('panel', panel)
    colors = [(115, 153, 136), (133, 158, 146), (177, 151, 103),
              (194, 131, 75), (178, 82, 73)]
    for level, color in enumerate(colors):
        strip = Image.new('RGBA', (1132, 34))
        for selected in (False, True):
            row = setup_surface((566, 34), color, selected)
            draw = ImageDraw.Draw(row)
            draw.rectangle((5, 6, 8, 27), fill=color)
            for mark in range(5):
                draw.rectangle((16 + mark * 4, 22 - mark * 3, 18 + mark * 4, 24),
                               fill=color if mark <= level else (51, 57, 63))
            if selected:
                draw.line((557, 10, 562, 16, 557, 23), fill=color, width=2)
            strip.paste(row, (566 if selected else 0, 0))
        add(f'level_{level}', strip, 2)
    for role, size in (('button', (148, 36)), ('rules', (226, 34)),
                       ('header_button', (261, 36))):
        add(role, setup_surface(size), kind='textSpriteType', effect='buttonstate')
    footer = setup_surface((484, 128))
    ImageDraw.Draw(footer).line((14, 6, 469, 6), fill=(177, 151, 103))
    add('footer', footer, kind='corneredTileSpriteType', effect='buttonstate_nodowneffect')
    header = setup_surface((484, 128))
    ImageDraw.Draw(header).line((14, 121, 469, 121), fill=(177, 151, 103))
    add('header', header, kind='corneredTileSpriteType', effect='buttonstate_nodowneffect')
    scenario = setup_surface((388, 116))
    ImageDraw.Draw(scenario).line((16, 65, 371, 65), fill=(177, 151, 103))
    add('scenario', scenario)
    add('nation', setup_surface((250, 58)))
    flag_frame = setup_surface((92, 58))
    # Preserve the native masked flag's 82x52 opening and its (5, 3) offset.
    ImageDraw.Draw(flag_frame).rectangle((5, 3, 86, 54), fill=(0, 0, 0, 0))
    add('flag_frame', flag_frame)
    observer = setup_surface((64, 64))
    draw = ImageDraw.Draw(observer)
    draw.line((10, 32, 21, 22, 32, 19, 43, 22, 54, 32,
               43, 42, 32, 45, 21, 42, 10, 32), fill=(190, 180, 155), width=2)
    draw.ellipse((25, 25, 39, 39), fill=(177, 151, 103))
    add('observer', observer, effect='buttonstate')
    observer_overlay = Image.new('RGBA', (128, 64))
    draw = ImageDraw.Draw(observer_overlay)
    for index, color in enumerate(((177, 151, 103, 190), (222, 201, 153, 255))):
        draw.rectangle((index * 64 + 2, 2, index * 64 + 61, 61), outline=color, width=2)
    add('observer_overlay', observer_overlay, 2, kind='frameAnimatedSpriteType',
        effect='buttonstate_blendframes')
    for selected in (False, True):
        strip = Image.new('RGBA', (100, 50))
        for index in range(2):
            tile = setup_surface((50, 50), selected=selected)
            draw = ImageDraw.Draw(tile)
            ink = (208, 183, 132) if selected else (169, 177, 180)
            if index == 0:
                draw.line((10, 14, 20, 10, 30, 14, 40, 10, 40, 36,
                           30, 40, 20, 36, 10, 40, 10, 14), fill=ink, width=2)
                draw.line((20, 10, 20, 36), fill=ink)
                draw.line((30, 14, 30, 40), fill=ink)
            else:
                for x, y in ((17, 21), (33, 21), (25, 14)):
                    draw.ellipse((x - 4, y - 4, x + 4, y + 4), fill=ink)
                    draw.rounded_rectangle((x - 6, y + 6, x + 6, y + 18), radius=3, fill=ink)
            strip.paste(tile, (index * 50, 0))
        add('mapmode_selected' if selected else 'mapmode', strip, 2, effect='buttonstate')
    details = Image.new('RGBA', (82, 57))
    for index in range(2):
        tile = setup_surface((41, 57), selected=bool(index))
        draw = ImageDraw.Draw(tile)
        for y in (23, 31):
            points = (13, y, 20, y + 5, 27, y) if index == 0 else (13, y + 5, 20, y, 27, y + 5)
            draw.line(points, fill=(208, 183, 132), width=2)
        details.paste(tile, (index * 41, 0))
    add('country_details', details, 2, effect='buttonstate')
    play = Image.new('RGBA', (723, 60))
    for index, active in enumerate((False, True, True)):
        tile = setup_surface((241, 60), (177, 151, 103), active)
        ImageDraw.Draw(tile).line((12, 10, 12, 49), fill=(177, 151, 103), width=3)
        play.paste(tile, (index * 241, 0))
    add('play', play, 3, effect='buttonstate_onlydisable')
    add('ready', play.crop((241, 0, 482, 60)), effect='buttonstate_onlydisable')
    checkbox = Image.new('RGBA', (68, 30))
    for selected in (False, True):
        tile = setup_surface((34, 30), selected=selected)
        if selected:
            ImageDraw.Draw(tile).line((8, 15, 14, 21, 26, 8), fill=(208, 183, 132), width=3)
        checkbox.paste(tile, (34 if selected else 0, 0))
    add('checkbox', checkbox, 2)
    return outputs, definitions


def expected_outputs(include_portraits: bool = True) -> dict[Path, bytes]:
    outputs = {}
    definitions = [
        '# Generated by tools/builders/build_adiscord_startup_ui_assets.py.',
        'spriteTypes = {',
    ]
    for role, size in SIZES.items():
        stream = BytesIO()
        frame(size, role != 'background').save(stream, 'PNG')
        outputs[OUTPUT / f'{role}.png'] = stream.getvalue()
        kind = 'spriteType' if role == 'background' else 'textSpriteType'
        definitions.extend(
            [
                f'\t{kind} = {{',
                f'\t\tname = "GFX_ADISCORD_startup_{role}"',
                f'\t\ttexturefile = "gfx/interface/startup/{role}.png"',
                '\t\tnoOfFrames = 1',
            ]
        )
        if role != 'background':
            definitions.append('\t\teffectFile = "gfx/FX/buttonstate.lua"')
        definitions.append('\t}')
    setup_images, setup_definitions = setup_outputs()
    outputs.update(setup_images)
    definitions.extend(setup_definitions)
    if include_portraits:
        for tag, (source, box) in PORTRAIT_CROPS.items():
            with Image.open(ROOT / source) as image:
                portrait = image.convert('RGB').crop(box).resize(PORTRAIT, Image.LANCZOS)
            stream = BytesIO()
            portrait.save(stream, 'PNG')
            outputs[OUTPUT / f'{tag}.png'] = stream.getvalue()
    for tag in ('stp', 'val', 'rus', *PORTRAIT_CROPS):
        definitions.extend(
            [
                '\tspriteType = {',
                f'\t\tname = "GFX_ADISCORD_startup_{tag}"',
                f'\t\ttexturefile = "gfx/interface/startup/{tag}.png"',
                '\t}',
            ]
        )
    definitions.append('}')
    outputs[ROOT / 'interface/ADISCORD_startup_menu.gfx'] = (
        '\n'.join(definitions) + '\n'
    ).encode('utf-8')
    return outputs


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument('--check', action='store_true')
    modes.add_argument('--apply', action='store_true')
    parser.add_argument(
        '--skin-only',
        action='store_true',
        help='Build frames and sprite definitions without reading or changing country artwork.',
    )
    args = parser.parse_args()
    outputs = expected_outputs(include_portraits=not args.skin_only)
    return apply_or_check(outputs, args.apply, 'Campaign briefing UI')


if __name__ == '__main__':
    raise SystemExit(main())
