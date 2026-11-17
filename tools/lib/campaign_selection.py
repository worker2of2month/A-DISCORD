"""Compile the bookmark roster into a scrollable gallery of equal-size campaign cards."""

from __future__ import annotations

import csv
import json
import re
from pathlib import Path

from PIL import Image, ImageDraw, ImageOps

from tools.lib.paths import repository_root
from tools.validators.validate_adiscord_division_templates import parse_clausewitz


ROOT = repository_root()
TEMPLATE = ROOT / 'tools/data/campaign_selection.gui.in'
CATALOG = ROOT / 'tools/data/campaign_selection.json'
BOOKMARK = ROOT / 'common/bookmarks/the_gathering_storm.txt'
GALLERY_GUI = ROOT / 'interface/ADISCORD_campaign_selection.gui'
CARD = (178, 304)
PRINT = (170, 273)
STRIDE = 184
BADGE = (35, 24)
BANNER = (300, 127)
SHEET_CAPACITY = 64
ATLAS = '---'
GOLD = (184, 140, 77)
LIGHT = (243, 212, 145)
DARK = (39, 28, 25)


def campaign_roster():
    ast = parse_clausewitz(BOOKMARK.read_text(encoding='utf-8-sig'))
    bookmarks = next(node.value for node in ast if node.key == 'bookmarks')
    start = next(node.value for node in bookmarks if node.key == 'bookmark')
    tags = [node.key for node in start if re.fullmatch(r'[A-Z]{3}|---', node.key)]
    catalog = json.loads(CATALOG.read_text(encoding='utf-8'))
    if tags.count(ATLAS) != 1 or len(set(tags)) != len(tags) or set(tags) != set(catalog) | {ATLAS}:
        raise ValueError(f'Country gallery and bookmark roster differ: {tags} / {list(catalog)}')
    if not any(node.key == 'sort_unplayed_first' and node.value == 'no' for node in start):
        raise ValueError('Campaign cards need stable native bookmark order')
    return {tag: ({} if tag == ATLAS else catalog[tag]) for tag in tags}


def sheet_name(index):
    page = index // SHEET_CAPACITY
    return 'route_flags' if page == 0 else f'route_flags_{page + 1}'


def sprite(role):
    return f'GFX_ADISCORD_setup_{role}'


def gui_block(kind, fields, children=()):
    parts = ['\n'.join(fields), *children]
    contents = '\n\n'.join(part for part in parts if part)
    return f'{kind} = {{\n' + '\n'.join('\t' + line if line else '' for line in contents.splitlines()) + '\n}'


def position(x, y):
    return f'position = {{ x = {x} y = {y} }}'


def size(width, height):
    return f'size = {{ width = {width} height = {height} }}'


def icon(name, x, y, role, *, frame=0, scale=1, tip=''):
    fields = [f'name = "{name}"', position(x, y), f'spriteType = "{sprite(role)}"']
    if frame:
        fields.append(f'frame = {frame}')
    if scale != 1:
        fields.append(f'scale = {scale}')
    fields.append(f'pdx_tooltip = {tip}' if tip else 'alwaystransparent = yes')
    return gui_block('iconType', fields)


def label(name, x, y, width, height, key, font, tip=''):
    return gui_block('instantTextBoxType', [
        f'name = "{name}"', position(x, y), f'font = "{font}"', f'text = "{key}"',
        f'maxWidth = {width}', f'maxHeight = {height}', 'format = centre',
        'fixedsize = yes', 'vertical_alignment = center',
        f'pdx_tooltip = {tip}' if tip else 'alwaystransparent = yes',
    ])


def gallery_gui(roster):
    posters, overlays = [], []
    badge_index = 0
    for index, (tag, spec) in enumerate(roster.items()):
        left = 8 + STRIDE * index
        code = 'atlas' if tag == ATLAS else tag.lower()
        posters.append(icon(f'poster_{code}', left + 4, 7, f'poster_{code}',
                            scale=1 if tag == ATLAS else 0.5))
        if tag == ATLAS:
            overlays.append(icon('atlas_compass', left + 9, 197, 'atlas_compass'))
            overlays.append(icon('atlas_nameplate', left + 3, 281, 'atlas_plate'))
            overlays.append(label('atlas_hint', left + 3, 281, 172, 23,
                                  'ADISCORD_BOOKMARK_ATLAS_HINT', 'hoi_18mbs'))
            continue
        routes = spec['routes']
        if len(routes) > 24 or len({r['key'] for r in routes}) != len(routes):
            raise ValueError(f'{tag} needs unique routes and at most four columns of six')
        # Flags and party emblems form two flanks when both fit independently.
        # More numerous routes flow down six rows before occupying the next column.
        separate = (any('emblem' in r for r in routes) and any('flag' in r for r in routes)
                    and max(sum(kind in r for r in routes) for kind in ('emblem', 'flag')) <= 6)
        counts = {'flag': 0, 'emblem': 0}
        for number, route in enumerate(routes):
            kind = 'emblem' if 'emblem' in route else 'flag'
            if separate:
                x = 10 if kind == 'flag' else CARD[0] - BADGE[0] - 10
                row = counts[kind]
                counts[kind] += 1
            else:
                column, row = divmod(number, 6)
                x = (10, CARD[0] - BADGE[0] - 10, 49, CARD[0] - BADGE[0] - 49)[column]
            name = f"{tag}_bookmark_route_{route['key']}"
            overlays.append(icon(name, left + x, 11 + row * 28, sheet_name(badge_index),
                                 frame=badge_index % SHEET_CAPACITY + 1, tip=f'{name}_tt'))
            badge_index += 1
        if spec.get('in_development', False):
            overlays.append(icon(f'development_sash_{tag}', left + 80, 225, 'development_sash'))
            overlays.append(icon(f'development_plate_{tag}', left + 73, 202, 'development_plate'))
            overlays.append(label(f'development_status_{tag}', left + 73, 202, 98, 20,
                                  'ADISCORD_BOOKMARK_IN_DEVELOPMENT', 'hoi_16mbs',
                                  'ADISCORD_BOOKMARK_IN_DEVELOPMENT_TT'))
    width = len(roster) * STRIDE
    window_width = min(9 * STRIDE + 16, max(1240, width + 16))
    native_grid = gui_block('gridBoxType', [
        'name = "countries_grid"', position(8, 3), size(width, CARD[1]),
        f'slotsize = {{ width = {STRIDE} height = {CARD[1]} }}', 'add_horizontal = yes',
        f'max_slots_horizontal = {len(roster)}', 'max_slots_vertical = 1', 'format = "UPPER_LEFT"',
    ])
    scroller = gui_block('containerWindowType', [
        'name = "countries"', position(620, 43),
        f'size = {{ width = {window_width} height = 334 max = {{ width = 100% height = 334 }} }}',
        'origo = center_up', 'clipping = yes',
        'horizontalScrollbar = "ADISCORD_campaign_gallery_slider"', 'scroll_wheel_factor = 46',
        'drag_scroll = { middle }',
    ], [gui_block('background', ['name = "scroll_surface"', 'quadTextureSprite = "GFX_tiled_window_transparent"']),
        *posters, native_grid, *overlays])
    template = TEMPLATE.read_text(encoding='utf-8')
    return template.replace('@WINDOW_WIDTH@', str(window_width)).replace(
        '\t\t@COUNTRY_SCROLLER@', '\n'.join('\t\t' + line if line else '' for line in scroller.splitlines()))


def route_texture(route):
    badge = Image.new('RGBA', BADGE)
    ink = ImageDraw.Draw(badge)
    ink.rectangle((0, 0, 34, 23), fill=(17, 15, 17), outline=(58, 39, 25))
    ink.rectangle((1, 1, 33, 22), fill=(35, 29, 30), outline=GOLD)
    if 'flag' in route:
        path = ROOT / f"gfx/flags/medium/{route['flag']}.tga"
        bounds = (30, 19)
    else:
        path = ROOT / route['emblem']
        bounds = (25, 21)
    with Image.open(path) as source:
        art = source.convert('RGBA')
        if 'emblem' in route:
            edges = art.getchannel('A').point(lambda alpha: 255 if alpha > 110 else 0).getbbox()
            if edges:
                art = art.crop(edges)
            alpha = art.getchannel('A')
            art = art.convert('RGB').point([round((value / 255) ** 0.7 * 255)
                                            for value in range(256)] * 3).convert('RGBA')
            art.putalpha(alpha)
            ink.rectangle((3, 3, 31, 20), fill=(104, 85, 65))
        image = ImageOps.contain(art, bounds, Image.Resampling.LANCZOS)
    badge.alpha_composite(image, ((35 - image.width) // 2, (24 - image.height) // 2))
    if 'badge' in route:
        with Image.open(ROOT / route['badge']) as source:
            pin = ImageOps.contain(source.convert('RGBA'), (12, 13), Image.Resampling.LANCZOS)
        badge.alpha_composite(pin, (21, 9))
    return badge


def dossier_panel(size, plate):
    panel = plate(size)
    width, height = size
    ink = ImageDraw.Draw(panel)
    for end, direction in ((14, 1), (width - 15, -1)):
        for step in range(3):
            x = end + direction * step * 4
            ink.line([(x, 12), (x, 18 + 4 * step),
                      (x + 11 * direction, 29 + 4 * step)], fill=(141, 101, 58))
    ink.line((18, 45, width - 19, 45), fill=(106, 78, 53))
    cx = width // 2
    ink.polygon([(cx - 5, 45), (cx, 42), (cx + 5, 45), (cx, 48)], fill=GOLD)
    return panel


def lacquer_wing(architecture):
    # Etch a single fan from the original theatre surround onto dark lacquer.
    wing = Image.new('RGBA', (196, 315), (28, 23, 26, 255))
    source = architecture.crop((352, 173, 743, 630))
    engraving = ImageOps.fit(ImageOps.grayscale(source), (wing.width - 13, 284), Image.Resampling.LANCZOS)
    engraving = ImageOps.colorize(engraving, (28, 23, 26), (68, 48, 40)).convert('RGBA')
    wing.alpha_composite(engraving, (6, 15))
    ink = ImageDraw.Draw(wing)
    for x in (5, wing.width - 7):
        ink.line((x, 16, x, 298), fill=(83, 60, 47))
    for y in (13, 301):
        ink.line((8, y, wing.width - 10, y), fill=(83, 60, 47))
    return wing


def campaign_scroll_art(add):
    track = Image.new('RGBA', (12, 12))
    ink = ImageDraw.Draw(track)
    ink.rectangle((2, 0, 9, 11), fill=(23, 18, 20))
    ink.rectangle((3, 0, 8, 11), fill=(34, 25, 25), outline=(100, 71, 44))
    ink.line((4, 2, 4, 9), fill=(138, 99, 59))
    ink.line((5, 2, 5, 9), fill=(17, 14, 16))
    for axis, image in (('vertical', track), ('horizontal', track.transpose(Image.Transpose.ROTATE_90))):
        add(f'scroll_track_{axis}', image, kind='corneredTileSpriteType', border=4)

    bed = Image.new('RGBA', (36, 18))
    ink = ImageDraw.Draw(bed)
    ink.polygon([(3, 0), (32, 0), (35, 3), (35, 14), (32, 17), (3, 17), (0, 14), (0, 3)],
                fill=(30, 23, 25), outline=(78, 56, 41))
    add('scroll_bed', bed, kind='corneredTileSpriteType', border=5)

    bezel = Image.new('RGBA', (16, 16))
    ink = ImageDraw.Draw(bezel)
    ink.polygon([(4, 0), (11, 0), (15, 4), (15, 11), (11, 15), (4, 15), (0, 11), (0, 4)],
                fill=(28, 20, 21), outline=(97, 69, 43))
    ink.line([(1, 7), (1, 4), (4, 1), (11, 1)], fill=(191, 147, 87))
    ink.line([(4, 14), (11, 14), (14, 11), (14, 5)], fill=(69, 49, 34))
    arrow = Image.new('RGBA', (16, 16))
    ImageDraw.Draw(arrow).polygon([(3, 9), (7, 5), (8, 5), (12, 9), (12, 11),
                                   (8, 8), (7, 8), (3, 11)], fill=LIGHT)
    directions = {'up': arrow, 'down': arrow.transpose(Image.Transpose.ROTATE_180),
                  'left': arrow.transpose(Image.Transpose.ROTATE_90),
                  'right': arrow.transpose(Image.Transpose.ROTATE_270)}
    for direction, glyph in directions.items():
        add(f'scroll_{direction}', Image.alpha_composite(bezel, glyph),
            effect='buttonstate', rectangular_hitbox=True)

    # A bright, faceted pull remains distinguishable from the dark enamel arrows at native size.
    thumb = bezel.copy()
    ink = ImageDraw.Draw(thumb)
    ink.polygon([(5, 1), (10, 1), (14, 5), (14, 10), (10, 14), (5, 14), (1, 10), (1, 5)],
                fill=(180, 133, 75), outline=(119, 82, 47))
    ink.line([(2, 9), (2, 5), (5, 2), (10, 2)], fill=LIGHT)
    ink.line([(5, 13), (10, 13), (13, 10), (13, 5)], fill=(98, 66, 39))
    grip = Image.new('RGBA', (16, 16))
    ink = ImageDraw.Draw(grip)
    for y, left, right in ((5, 6, 9), (7, 4, 11), (9, 6, 9)):
        ink.line((left, y, right, y), fill=(87, 57, 35))
        ink.line((left, y + 1, right, y + 1), fill=(233, 196, 128))
    for axis, grooves in (('vertical', grip), ('horizontal', grip.transpose(Image.Transpose.ROTATE_90))):
        add(f'scroll_thumb_{axis}', Image.alpha_composite(thumb, grooves),
            effect='buttonstate_nodowneffect', rectangular_hitbox=True)


def atlas_print():
    # Province colour IDs are categorical. Sample nearest neighbours before mapping land and sea.
    with (ROOT / 'map/definition.csv').open(encoding='utf-8-sig') as stream:
        land = {tuple(map(int, row[1:4])) for row in csv.reader(stream, delimiter=';')
                if len(row) >= 5 and row[4].strip() == 'land' and row[0] != '0'}
    with Image.open(ROOT / 'map/provinces.bmp') as source:
        small = source.convert('RGB')
        small.thumbnail((576, 320), Image.Resampling.NEAREST)
    pixels = small.load()
    mask = Image.frombytes('L', small.size, bytes(
        255 if pixels[x, y] in land else 0 for y in range(small.height) for x in range(small.width)))
    world = ImageOps.colorize(mask, (33, 56, 55), (167, 145, 91)).convert('RGBA')
    page = ImageOps.fit(world, PRINT, Image.Resampling.LANCZOS, centering=(0.52, 0.5))
    draw = ImageDraw.Draw(page, 'RGBA')
    for x in range(0, page.width, 28):
        draw.line((x, 0, x, page.height), fill=(93, 97, 66))
    for y in range(0, page.height, 28):
        draw.line((0, y, page.width, y), fill=(93, 97, 66))
    for radius in (49, 54, 58):
        draw.ellipse((85 - radius, 107 - radius, 85 + radius, 107 + radius), outline=LIGHT)
    for dx, dy in ((0, -66), (58, 0), (0, 66), (-58, 0), (28, -28), (28, 28), (-28, 28), (-28, -28)):
        nx, ny = -dy // 6, dx // 6
        draw.polygon([(85, 107), (85 + nx, 107 + ny), (85 + dx, 107 + dy)], fill=LIGHT)
        draw.polygon([(85, 107), (85 - nx, 107 - ny), (85 + dx, 107 + dy)], fill=(112, 74, 42))
    return page, world


def gallery_art(add, roster, plate):
    campaign_scroll_art(add)
    with Image.open(ROOT / 'gfx/interface/country_selection_bg.dds') as source:
        architecture = source.convert('RGBA')
    case = Image.new('RGBA', (48, 48), (27, 23, 26, 255))
    ink = ImageDraw.Draw(case)
    for pad, colour in ((0, (49, 34, 27)), (2, GOLD), (4, (105, 74, 46)), (7, (39, 29, 27))):
        ink.rectangle((pad, pad, 47 - pad, 47 - pad), outline=colour)
    add('gallery_case', case, kind='corneredTileSpriteType')

    inlay = Image.new('RGBA', (1240, 704))
    ink = ImageDraw.Draw(inlay)
    inlay.alpha_composite(plate((380, 41), selected=True), (430, 0))
    for direction in (1, -1):
        origin = 430 if direction == 1 else 809
        def point(distance, y):
            return (origin - direction * distance, y)
        for off, span in ((0, 400), (4, 362), (8, 321)):
            ink.line((point(3 + off, 15 + off), point(span, 15 + off)), fill=GOLD)
        for n in range(4):
            ink.line([point(6 + n * 6, 6), point(23 + n * 6, 23),
                      point(48 + n * 9, 23)], fill=LIGHT)
    left = dossier_panel((318, 315), plate)
    middle = dossier_panel((423, 315), plate)
    ink = ImageDraw.Draw(left)
    ink.line((16, 194, 301, 194), fill=(94, 69, 53))
    ink = ImageDraw.Draw(middle)
    for y in (147, 266):
        ink.line((17, y, 405, y), fill=(94, 69, 53))
    inlay.alpha_composite(left, (7, 379))
    inlay.alpha_composite(middle, (331, 379))
    add('country_gallery', inlay)
    add('dossier_history', dossier_panel((475, 315), plate))
    wing = lacquer_wing(architecture)
    add('gallery_left_wing', wing)
    add('gallery_right_wing', ImageOps.mirror(wing))
    portrait = plate((102, 139))
    ink = ImageDraw.Draw(portrait)
    ink.rectangle((4, 5, 97, 132), fill=(0, 0, 0, 0))
    ink.rectangle((3, 4, 98, 133), outline=GOLD)
    add('dossier_portrait', portrait)

    cards = Image.new('RGBA', (CARD[0] * 2, CARD[1]))
    for selected in (False, True):
        tile = plate(CARD, selected)
        pen = ImageDraw.Draw(tile)
        pen.rectangle((4, 4, 173, 276), fill=(0, 0, 0, 0))
        for box in ((11, 200, 69, 278), (78, 220, 165, 277)):
            pen.rectangle(box, outline=(33, 23, 19), width=3)
            pen.rectangle(box, outline=LIGHT if selected else GOLD)
        pen.line((8, 277, 169, 277), fill=LIGHT if selected else GOLD)
        if selected:
            pen.rectangle((1, 1, 176, 302), outline=LIGHT, width=2)
            for x, direction in ((3, 1), (174, -1)):
                pen.polygon([(x, 3), (x + direction * 13, 3), (x, 17)], fill=LIGHT)
            pen.polygon([(83, 301), (89, 296), (95, 301)], fill=LIGHT)
        cards.paste(tile, (CARD[0] if selected else 0, 0))
    add('country_card', cards, 2, effect='buttonstate_nodowneffect', rectangular_hitbox=True)

    atlas, world = atlas_print()
    add('poster_atlas', atlas)
    inset = plate((161, 85))
    small_map = ImageOps.contain(world, (147, 70), Image.Resampling.LANCZOS)
    inset.alpha_composite(small_map, ((161 - small_map.width) // 2, (85 - small_map.height) // 2))
    add('atlas_compass', inset)
    add('atlas_plate', plate((172, 23)))
    add('development_plate', plate((98, 20)))

    sash = Image.new('RGBA', (252, 162))
    mask = Image.new('L', sash.size)
    ImageDraw.Draw(mask).line((4, 4, 248, 158), fill=255, width=34)
    stripe = Image.new('RGBA', sash.size, DARK)
    pen = ImageDraw.Draw(stripe)
    for x in range(-50, 330, 37):
        pen.polygon([(x, 0), (x + 21, 0), (x - 47, 162), (x - 68, 162)], fill=(225, 178, 73))
    pen.line((0, -11, 253, 149), fill=LIGHT, width=4)
    pen.line((0, 21, 244, 176), fill=GOLD, width=4)
    sash.paste(stripe, (0, 0), mask)
    add('development_sash', sash.resize((84, 54), Image.Resampling.LANCZOS))

    routes = [route for spec in roster.values() for route in spec.get('routes', [])]
    for offset in range(0, len(routes), SHEET_CAPACITY):
        page = routes[offset:offset + SHEET_CAPACITY]
        sheet = Image.new('RGBA', (len(page) * BADGE[0], BADGE[1]))
        for i, route in enumerate(page):
            sheet.alpha_composite(route_texture(route), (i * BADGE[0], 0))
        add(sheet_name(offset), sheet, len(page))
