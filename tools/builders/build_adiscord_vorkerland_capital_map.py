"""Build WRK capital street maps, sprite bindings and a self-contained review mockup.

Owns capital PNGs, marked visual/interaction sections in existing interfaces,
scripted GUI and localisation, the compact category description and HTML mockup.
Default mode compares bytes without writing. Requires Pillow and NumPy.
"""

from __future__ import annotations

import argparse
import base64
import csv
import io
import json
import math
from pathlib import Path
import random
import re
import sys

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter


ROOT = Path(__file__).resolve().parents[2]
if __package__ in (None, ""):
    sys.path.insert(0, str(ROOT))
OUT = Path("gfx/interface/vorkerland_capital")
GUI = Path("interface/ADISCORD_vorkerland.gui")
GFX = Path("interface/ADISCORD_vorkerland.gfx")
SGUI = Path("common/scripted_guis/ADISCORD_vorkerland_scripted_gui.txt")
DECISIONS = Path("common/decisions/ADISCORD_vorkerland_decisions.txt")
MOCKUP = Path("docs/mockups/vorkerland_capital.html")
PREVIEW = Path("docs/development/previews/vorkerland_capital/review.png")
STATES = (32, 33, 34, 35, 36, 37, 38, 39, 40)
STREET_ANGLES = {32: -19, 33: 24, 34: 7, 35: -32, 36: 31, 37: -12, 38: 13, 39: -4, 40: 0}
STATE_LABELS = {
    32: "Центральный дистрикт",
    33: "Юго-Восточный дистрикт",
    34: "Нефтегазовый дистрикт",
    35: "Старый Воркенсберг",
    36: "Северный дистрикт",
    37: "Северо-Западный дистрикт",
    38: "Юго-Западный дистрикт",
    39: "Промышленный дистрикт",
    40: "Башня Единства",
}
DEMO_STATE_FRAMES = {32: 2, 33: 3, 34: 3, 35: 2, 36: 4, 37: 5, 38: 6, 39: 4, 40: 3}
DEMO_MARKER_FRAMES = {32: 2, 33: 6, 34: 3, 35: 2, 36: 3, 37: 4, 38: 5, 39: 6, 40: 1}
WIDTH, HEIGHT = 330, 290
MAP_X = 65
SS = 3
SEED = 320336373840
BEGIN = "# BEGIN GENERATED WRK CAPITAL VISUALS"
END = "# END GENERATED WRK CAPITAL VISUALS"
GRAPHITE = (24, 25, 23)
TURQUOISE = (153, 169, 151)
WORKER = (235, 203, 100)
STAFF = (179, 154, 242)
WORX = (169, 214, 111)
RED = (244, 101, 101)
WHITE = (219, 230, 230)
MUTED = (144, 132, 99)
HIT_ALPHA = 8
FRAME_COUNTS = {
    "WRK_capital_marker": 6,
    "WRK_capital_route": 3,
    "WRK_capital_network_link": 2,
    "WRK_intrigue_card": 3,
    **{f"WRK_capital_state_{state}": 6 for state in STATES},
    **{f"WRK_capital_select_{state}": 3 for state in STATES},
    "WRK_capital_action": 3,
    "WRK_capital_marker_select": 3,
}
ACTIONS = (
    ("WRK_issue_capital_rations", "Пайки", "Rations", 0),
    ("WRK_unrest_cede_shop_to_committee", "Цех комитету", "Committee shop", 1),
    ("WRK_unrest_send_plenipotentiary", "Уполномоченный", "Commissioner", 2),
    ("WRK_unrest_workers_patrol", "Рабочий патруль", "Worker patrol", 3),
    ("WRK_cell_plant", "Создать ячейку", "Plant cell", 0),
    ("WRK_cell_expand", "Расширить сеть", "Expand network", 1),
    ("WRK_cell_lie_low", "Залечь на дно", "Lie low", 2),
    ("WRK_cell_forge_passes", "Новые пропуска", "Forge passes", 3),
    ("WRK_cell_legalize", "Легализовать", "Legalize", 4),
)


def canvas(size=(WIDTH, HEIGHT), color=(0, 0, 0, 0)):
    return Image.new("RGBA", (size[0] * SS, size[1] * SS), color)


def finish(image):
    return image.resize((image.width // SS, image.height // SS), Image.Resampling.LANCZOS)


def scaled_box(box):
    return tuple(round(value * SS) for value in box)


def ellipse(image, box, fill, outline=None, width=1):
    ImageDraw.Draw(image).ellipse(scaled_box(box), fill=fill, outline=outline, width=round(width * SS))


def rectangle(image, box, fill=None, outline=None, width=1):
    ImageDraw.Draw(image).rectangle(scaled_box(box), fill=fill, outline=outline, width=round(width * SS))


def polygon(image, points, fill):
    ImageDraw.Draw(image).polygon([(round(x * SS), round(y * SS)) for x, y in points], fill=fill)


def stroke(image, points, color, width=1, caps=False):
    ImageDraw.Draw(image).line(
        [(round(x * SS), round(y * SS)) for x, y in points],
        fill=color, width=max(1, round(width * SS)), joint="curve",
    )
    if caps:
        radius = width / 2
        for x, y in (points[0], points[-1]):
            ellipse(image, (x - radius, y - radius, x + radius, y + radius), color)


def rounded_path(points, radius=9):
    """Round bends geometrically so route corners do not depend on line-join support."""
    result = [points[0]]
    for previous, corner, following in zip(points, points[1:], points[2:]):
        left = math.dist(previous, corner)
        right = math.dist(corner, following)
        distance = min(radius, left / 3, right / 3)
        if not distance:
            continue
        before = tuple(c + (p - c) * distance / left for p, c in zip(previous, corner))
        after = tuple(c + (n - c) * distance / right for c, n in zip(corner, following))
        result.append(before)
        for index in range(1, 13):
            t = index / 12
            result.append(tuple((1 - t) ** 2 * a + 2 * (1 - t) * t * c + t * t * b
                                for a, c, b in zip(before, corner, after)))
    return [*result, points[-1]]


def geography():
    colors = {}
    with (ROOT / "map/definition.csv").open(encoding="utf-8-sig") as source:
        for row in csv.reader(source, delimiter=";"):
            if len(row) >= 5 and row[0].isdigit():
                colors[int(row[0])] = int(row[1]) * 65536 + int(row[2]) * 256 + int(row[3])
    state_colors = {}
    for state in STATES:
        paths = sorted((ROOT / "history/states").glob(f"{state}-*.txt"))
        if len(paths) != 1:
            raise ValueError(f"Expected one history file for state {state}")
        source = re.sub(r"#.*", "", paths[0].read_text(encoding="utf-8-sig"))
        match = re.search(r"\bprovinces\s*=\s*\{([^}]+)\}", source)
        if not match:
            raise ValueError(f"Missing provinces in state {state}")
        state_colors[state] = {colors[int(value)] for value in re.findall(r"\d+", match[1])}
    with Image.open(ROOT / "map/provinces.bmp") as source:
        rgb = np.asarray(source.convert("RGB"), dtype=np.uint32)
    packed = rgb[:, :, 0] * 65536 + rgb[:, :, 1] * 256 + rgb[:, :, 2]
    selected = np.isin(packed, list(set.union(*state_colors.values())))
    yy, xx = np.nonzero(selected)
    if not len(xx):
        raise ValueError("Capital provinces absent from provinces.bmp")
    box = (int(xx.min()), int(yy.min()), int(xx.max()) + 1, int(yy.max()) + 1)
    crop = packed[box[1]:box[3], box[0]:box[2]]
    scale = min((WIDTH - 24) / crop.shape[1], (HEIGHT - 24) / crop.shape[0])
    size = (round(crop.shape[1] * scale), round(crop.shape[0] * scale))
    offset = ((WIDTH - size[0]) // 2, (HEIGHT - size[1]) // 2)
    masks = {}
    anchors = {}
    for state, values in state_colors.items():
        raw = Image.fromarray(np.isin(crop, list(values)).astype(np.uint8) * 255)
        mask = Image.new("L", (WIDTH, HEIGHT))
        mask.paste(raw.resize(size, Image.Resampling.NEAREST), offset)
        if not mask.getbbox():
            raise ValueError(f"State {state} disappeared in projection")
        masks[state] = mask
        interior = mask
        while True:
            smaller = interior.filter(ImageFilter.MinFilter(3))
            if not smaller.getbbox():
                break
            interior = smaller
        y, x = np.nonzero(np.asarray(interior))
        index = int(np.argmin((x - x.mean()) ** 2 + (y - y.mean()) ** 2))
        anchors[state] = (int(x[index]), int(y[index]))
    return {"masks": masks, "anchors": anchors, "source_box": box}


def street_network(geometry):
    """Small irregular blocks, district-specific grids, then continuous avenues."""
    image = canvas()
    for state in STATES:
        angle = STREET_ANGLES[state]
        rng = random.Random(SEED + state)
        local = canvas()
        cx, cy = geometry["anchors"][state]
        radians = math.radians(angle)

        def project(u, v):
            return (cx + u * math.cos(radians) - v * math.sin(radians),
                    cy + u * math.sin(radians) + v * math.cos(radians))

        # Shared grid nodes keep side streets connected across adjacent blocks.
        axes = []
        for axis in range(2):
            values = [-400.0]
            while values[-1] < 400:
                values.append(values[-1] + rng.uniform(5.5, 10.5))
            axes.append(values)
        nodes = {(i, j): project(u + rng.uniform(-1.1, 1.1), v + rng.uniform(-1.1, 1.1))
                 for i, u in enumerate(axes[0]) for j, v in enumerate(axes[1])}
        for i in range(len(axes[0]) - 1):
            for j in range(len(axes[1]) - 1):
                point = nodes[i, j]
                if not (-15 < point[0] < WIDTH + 15 and -15 < point[1] < HEIGHT + 15):
                    continue
                if rng.random() > 0.13:
                    stroke(local, [point, nodes[i + 1, j]], (*TURQUOISE, 100), 0.55)
                if rng.random() > 0.12:
                    stroke(local, [point, nodes[i, j + 1]], (*TURQUOISE, 100), 0.55)
        for axis in range(2):
            for lane in (-38, 0, 42):
                points = [project(lane + 3 * math.sin(v / 37), v) if axis == 0
                          else project(v, lane + 3 * math.sin(v / 41))
                          for v in range(-400, 401, 8)]
                stroke(local, points, (*TURQUOISE, 230), 1.5)
        mask = geometry["masks"][state].resize(local.size, Image.Resampling.NEAREST)
        local.putalpha(ImageChops.multiply(local.getchannel("A"), mask))
        image.alpha_composite(local)
    anchors = geometry["anchors"]
    avenues = canvas()
    for states in ((36, 35, 34, 33), (37, 38, 39, 33), (35, 32, 40, 39)):
        stroke(avenues, rounded_path([anchors[state] for state in states], 18), (*TURQUOISE, 245), 2)
    union = Image.new("L", (WIDTH, HEIGHT))
    for mask in geometry["masks"].values():
        union = ImageChops.lighter(union, mask)
    avenues.putalpha(ImageChops.multiply(avenues.getchannel("A"), union.resize(image.size, Image.Resampling.NEAREST)))
    image.alpha_composite(avenues)
    return finish(image)


def state_strip(streets, mask):
    strip = Image.new("RGBA", (WIDTH * 6, HEIGHT))
    alpha = ImageChops.multiply(streets.getchannel("A"), mask)
    for index, color in enumerate((WORKER, STAFF, WORX, None, RED), 1):
        if color:
            frame = Image.new("RGBA", (WIDTH, HEIGHT), color)
        else:
            y, x = np.indices((HEIGHT, WIDTH))
            stripes = np.array((WORKER, STAFF, WORX), dtype=np.uint8)[((x + y) // 9) % 3]
            frame = Image.fromarray(stripes).convert("RGBA")
        frame.putalpha(alpha)
        strip.paste(frame, (WIDTH * index, 0))
    return strip


def marker_strip():
    strip = Image.new("RGBA", (28 * 6, 28))
    for frame in range(2, 7):
        image = canvas((28, 28))
        danger = frame in (3, 4, 5)
        color = RED if danger else WHITE
        ellipse(image, (1.5, 1.5, 26, 26), (*GRAPHITE, 255), color, 2.8 if danger else 1.5)
        if frame == 2:
            for x, y in ((9, 10), (19, 10), (14, 19)):
                ellipse(image, (x - 2, y - 2, x + 2, y + 2), color)
            stroke(image, [(9, 10), (14, 19), (19, 10), (9, 10)], color, 1)
        elif frame == 3:
            stroke(image, [(7, 21), (21, 7)], color, 3.5, True)
        elif frame == 4:
            stroke(image, [(14, 7), (14, 15)], color, 3, True)
            ellipse(image, (12.5, 19, 15.5, 22), color)
        elif frame == 5:
            stroke(image, [(7, 14), (21, 14)], color, 4.2, True)
        else:
            polygon(image, [(14, 6), (21, 9), (20, 17), (14, 22), (8, 17), (7, 9)], color)
            stroke(image, [(14, 10), (14, 18)], GRAPHITE, 1.5)
        strip.paste(finish(image), (28 * (frame - 1), 0))
    return strip


def dashed_stroke(image, points, color, width=4, dash=8, gap=5):
    distance = 0.0
    for start, end in zip(points, points[1:]):
        length = math.dist(start, end)
        if not length:
            continue
        offset = 0.0
        while offset < length - 1e-6:
            phase = distance % (dash + gap)
            on = phase < dash
            step = min(length - offset, (dash if on else dash + gap) - phase)
            if step < 1e-6:
                step = min(length - offset, 1e-5)
            if on:
                a = tuple(s + (e - s) * offset / length for s, e in zip(start, end))
                b = tuple(s + (e - s) * (offset + step) / length for s, e in zip(start, end))
                stroke(image, [a, b], color, width, True)
            offset += step
            distance += step


def route_strip(geometry):
    anchors = geometry["anchors"]
    tx, ty = anchors[40]
    civil = [anchors[40], (tx + 4, ty - 26), (tx + 24, ty - 26),
             (anchors[33][0] - 25, anchors[33][1] - 8), anchors[33], (WIDTH - 11, anchors[33][1])]
    military = [anchors[40], (tx - 17, ty + 20), anchors[38], anchors[37], anchors[36], (anchors[36][0], 11)]
    geometry["routes"] = [civil, military]
    strip = Image.new("RGBA", (WIDTH * 3, HEIGHT))
    for frame, points in enumerate((civil, military), 1):
        image = canvas()
        path = rounded_path(points)
        split = max(2, int(len(path) * 0.63))
        stroke(image, path, (*GRAPHITE, 255), 6, True)
        stroke(image, path[:split], RED, 3.6, True)
        dashed_stroke(image, path[split - 1:], RED, 3.6)
        x, y = points[0]
        polygon(image, [(x, y + 1), (x - 5, y - 7), (x + 5, y - 7)], RED)
        ellipse(image, (x - 5, y - 12, x + 5, y - 2), RED)
        ellipse(image, (x - 1.7, y - 8.7, x + 1.7, y - 5.3), GRAPHITE)
        x, y = points[-1]
        rectangle(image, (x - 6, y - 4, x + 6, y + 6), GRAPHITE, RED, 2)
        stroke(image, [(x - 8, y - 3), (x, y - 10), (x + 8, y - 3)], RED, 2.4, True)
        stroke(image, [(x, y + 5), (x, y + 1)], RED, 2)
        strip.paste(finish(image), (WIDTH * frame, 0))
    return strip


def card_strip():
    strip = Image.new("RGBA", (660, 100))
    for frame, accent in enumerate((MUTED, STAFF, WHITE)):
        image = canvas((220, 100), (*GRAPHITE, 255))
        rectangle(image, (0.5, 0.5, 219, 99), outline=(*MUTED, 125), width=0.7)
        rectangle(image, (1, 1, 3, 98), accent)
        rectangle(image, (10, 10, 55, 71), outline=(*accent, 210), width=0.7)
        stroke(image, [(66, 61), (207, 61)], (*MUTED, 115), 0.7)
        ellipse(image, (199, 10, 211, 22), None, accent, 1)
        if frame:
            stroke(image, [(202, 16), (208, 16)], accent, 1)
        if frame == 1:
            stroke(image, [(205, 13), (205, 19)], accent, 1)
        strip.paste(finish(image), (220 * frame, 0))
    return strip


def network_link_strip(geometry):
    """Show a logical connection to the Central cell, not a third street route."""
    tower, central = geometry['anchors'][40], geometry['anchors'][32]
    elbow = max(tower[0], central[0]) + 22
    points = [tower, (elbow, tower[1]), (elbow, central[1]), central]
    path = rounded_path(points, 6)
    strip = Image.new('RGBA', (WIDTH * 2, HEIGHT))
    for frame, color in enumerate((WORX, MUTED)):
        image = canvas()
        stroke(image, path, (*GRAPHITE, 235), 4, True)
        dashed_stroke(image, path, (*color, 255), 2, dash=4, gap=3)
        for x, y in (tower, central):
            ellipse(image, (x - 5, y - 5, x + 5, y + 5), (*GRAPHITE, 235), color, 1.5)
        if frame:
            x, y = elbow, (tower[1] + central[1]) / 2
            stroke(image, [(x - 4, y - 4), (x + 4, y + 4)], RED, 2)
            stroke(image, [(x - 4, y + 4), (x + 4, y - 4)], RED, 2)
        strip.paste(finish(image), (frame * WIDTH, 0))
    return strip


def render_images():
    geometry = geography()
    streets = street_network(geometry)
    # A translucent engraved plan lets the native decision-category paper show.
    background = Image.new("RGBA", (WIDTH, HEIGHT))
    grid = ImageDraw.Draw(background)
    for x in range(8, WIDTH, 24):
        grid.line((x, 0, x, HEIGHT), fill=(*MUTED, 18))
    for y in range(8, HEIGHT, 24):
        grid.line((0, y, WIDTH, y), fill=(*MUTED, 18))
    background.alpha_composite(streets)
    for mask in geometry["masks"].values():
        rim = ImageChops.subtract(mask, mask.filter(ImageFilter.MinFilter(3)))
        edge = Image.new("RGBA", background.size, (*MUTED, 120))
        edge.putalpha(rim.point(lambda value: value * 190 // 255))
        background.alpha_composite(edge)
    ornament = canvas()
    x, y = geometry["anchors"][40]
    # The tower is offset above its tiny state; the leader terminates at its anchor.
    stroke(ornament, [(x - 10, y - 7), (x, y)], WHITE, 0.8)
    rectangle(ornament, (x - 17, y - 27, x - 7, y - 7), GRAPHITE)
    polygon(ornament, [(x - 17, y - 7), (x - 7, y - 7), (x - 9, y - 19),
                      (x - 11, y - 19), (x - 12, y - 27), (x - 13, y - 19), (x - 15, y - 19)], WHITE)
    stroke(ornament, [(x - 12, y - 15), (x - 12, y - 9)], GRAPHITE, 1)
    tower = finish(ornament)
    background.alpha_composite(tower)
    # The offset tower and its leader belong to state 40 for hover purposes.
    # Dilate the rendered footprint by two pixels, including antialiased edges.
    tower_area = tower.getchannel("A").point(lambda value: 255 if value else 0)
    tower_area = tower_area.filter(ImageFilter.MaxFilter(5))
    tower_hit = ImageChops.lighter(geometry["masks"][40], tower_area)
    images = {"WRK_capital_map_background.png": background}
    for state, mask in geometry["masks"].items():
        images[f"WRK_capital_state_{state}.png"] = state_strip(streets, mask)
        # Reserve the complete tower hit area before assigning neighbouring
        # districts, so each pixel has one tooltip owner in every street frame.
        hit_mask = tower_hit if state == 40 else ImageChops.subtract(mask, tower_hit)
        hit = Image.new("RGBA", (WIDTH, HEIGHT), GRAPHITE)
        hit.putalpha(hit_mask.point(lambda value: HIT_ALPHA if value else 0))
        images[f"WRK_capital_hit_{state}.png"] = hit
        select = Image.new("RGBA", (WIDTH * 3, HEIGHT))
        edge = ImageChops.subtract(hit_mask, hit_mask.filter(ImageFilter.MinFilter(3)))
        for frame, opacity in enumerate((HIT_ALPHA, 42, 60)):
            layer = Image.new("RGBA", (WIDTH, HEIGHT), WORKER)
            alpha = hit_mask.point(lambda value: opacity if value else 0)
            if frame:
                alpha = ImageChops.lighter(alpha, edge)
            layer.putalpha(alpha)
            select.paste(layer, (frame * WIDTH, 0))
        images[f"WRK_capital_select_{state}.png"] = select
        selected = Image.new("RGBA", (WIDTH, HEIGHT), WORKER)
        selected.putalpha(edge)
        images[f"WRK_capital_selected_{state}.png"] = selected
    images["WRK_capital_marker.png"] = marker_strip()
    images["WRK_capital_route.png"] = route_strip(geometry)
    images["WRK_capital_network_link.png"] = network_link_strip(geometry)
    images["WRK_intrigue_card.png"] = card_strip()
    panel = canvas((460, 524))
    stroke(panel, [(10, 39), (450, 39)], (*MUTED, 125), 0.7)
    stroke(panel, [(10, 352), (450, 352)], (*MUTED, 160), 0.7)
    images["WRK_capital_panel.png"] = finish(panel)
    action = Image.new("RGBA", (214 * 3, 28))
    for frame, color in enumerate(((37, 38, 32), (65, 62, 44), (88, 78, 47))):
        draw = ImageDraw.Draw(action)
        x = frame * 214
        draw.rectangle((x, 0, x + 213, 27), fill=(*color, 245), outline=(*MUTED, 255))
        draw.line((x + 2, 2, x + 211, 2), fill=(174, 158, 113))
    images["WRK_capital_action.png"] = action
    marker_select = Image.new('RGBA', (84, 28))
    draw = ImageDraw.Draw(marker_select)
    for frame in range(3):
        x = frame * 28
        draw.ellipse((x + 1, 1, x + 26, 26), fill=(*WORKER, 8),
                     outline=(*WORKER, 8 if frame == 0 else 200), width=1)
    images['WRK_capital_marker_select.png'] = marker_select
    portrait = canvas((156, 210), (*GRAPHITE, 255))
    ellipse(portrait, (48, 30, 108, 98), (67, 83, 90, 255))
    ellipse(portrait, (14, 107, 142, 257), (67, 83, 90, 255))
    images["WRK_intrigue_portrait_empty.png"] = finish(portrait)
    geometry["markers"] = dict(geometry["anchors"])
    ax, ay = geometry["anchors"][32]
    geometry["markers"][32] = (ax, ay - 22)
    ax, ay = geometry["anchors"][40]
    geometry["markers"][40] = (ax + 26, ay + 18)
    return images, geometry


def icon(name, sprite, x, y, frame=1, scale=None, transparent=False, tooltip=None):
    lines = ["\t\ticonType = {", f'\t\t\tname = "{name}"',
             f"\t\t\tposition = {{ x = {x} y = {y} }}", f'\t\t\tquadTextureSprite = "{sprite}"',
             f"\t\t\tframe = {frame}"]
    if scale is not None:
        lines.append(f"\t\t\tscale = {scale}")
    if transparent:
        lines.append("\t\t\talwaystransparent = yes")
    if tooltip is not None:
        lines.append(f'\t\t\tpdx_tooltip = "{tooltip}"')
    return "\n".join([*lines, "\t\t}"])


def textbox(name, text, x, y, width, height, font="hoi_16mbs", centered=False, tooltip=None):
    lines = ["\t\tinstantTextBoxType = {", f'\t\t\tname = "{name}"',
             f"\t\t\tposition = {{ x = {x} y = {y} }}", f'\t\t\ttext = "{text}"',
             f'\t\t\tfont = "{font}"', f"\t\t\tmaxWidth = {width}", f"\t\t\tmaxHeight = {height}",
             "\t\t\tfixedsize = yes"]
    lines.append(f'\t\t\tpdx_tooltip = "{tooltip}"' if tooltip else "\t\t\talwaystransparent = yes")
    if centered:
        lines.append("\t\t\tformat = center")
    return "\n".join([*lines, "\t\t}"])


def button(name, sprite, x, y, tooltip, label=""):
    return '\n'.join(['\t\tbuttonType = {', f'\t\t\tname = "{name}"',
                      f'\t\t\tposition = {{ x = {x} y = {y} }}',
                      f'\t\t\tquadTextureSprite = "{sprite}"',
                      f'\t\t\tbuttonText = "{label}"', '\t\t\tbuttonFont = "hoi_16mbs"',
                      '\t\t\tclicksound = click_default', f'\t\t\tpdx_tooltip = "{tooltip}"', '\t\t}'])


def gui_block(geometry):
    parts = ['\n'.join(['\t# Generated by tools/builders/build_adiscord_vorkerland_capital_map.py.',
             '\tcontainerWindowType = {', '\t\tname = "ADISCORD_vorkerland_capital_window"',
             '\t\tposition = { x = 0 y = 0 }', '\t\tsize = { width = 460 height = 524 }',
             '\t\tclipping = no']), icon("WRK_capital_panel", "GFX_WRK_capital_panel", 0, 0, transparent=True),
             textbox("WRK_capital_title", "WRK_capital_title", 10, 6, 330, 24, "hoi_20b"),
             textbox("WRK_capital_overview", "WRK_capital_overview", 350, 10, 100, 22,
                     centered=True, tooltip="WRK_capital_overview_tt"),
             icon("WRK_capital_map", "GFX_WRK_capital_map_background", MAP_X, 48, transparent=True)]
    for state in STATES:
        parts.append(icon(f"WRK_capital_{state}_hit", f"GFX_WRK_capital_hit_{state}", MAP_X, 48,
                          tooltip=f"WRK_capital_{state}_tt"))
    for state in STATES:
        parts.append(icon(f"WRK_capital_{state}_selected", f"GFX_WRK_capital_selected_{state}",
                          MAP_X, 48, transparent=True))
    for state in STATES:
        parts.append(icon(f"WRK_capital_{state}_state", f"GFX_WRK_capital_state_{state}", MAP_X, 48, transparent=True))
    parts.append(icon("WRK_capital_route", "GFX_WRK_capital_route", MAP_X, 48, transparent=True))
    for frame, status in enumerate(('open', 'closed'), 1):
        parts.append(icon(f'WRK_capital_network_{status}', 'GFX_WRK_capital_network_link',
                          MAP_X, 48, frame=frame, transparent=True))
    for state in STATES:
        x, y = geometry["markers"][state]
        parts.append(icon(f"WRK_capital_{state}_marker", "GFX_WRK_capital_marker", MAP_X + x - 14, 48 + y - 14,
                          tooltip=f"WRK_capital_{state}_tt"))
    # Native input surfaces are the last map children, above every decorative layer.
    for state in STATES:
        parts.append(button(f"WRK_capital_{state}_select", f"GFX_WRK_capital_select_{state}",
                            MAP_X, 48, f"WRK_capital_{state}_tt"))
    for state in STATES:
        x, y = geometry["markers"][state]
        parts.append(button(f"WRK_capital_{state}_marker_select", "GFX_WRK_capital_marker_select",
                            MAP_X + x - 14, 48 + y - 14, f"WRK_capital_{state}_tt"))
    for number, y in enumerate((65, 155, 245), 1):
        parts.append(icon(f"WRK_capital_legend_icon_{number}", "GFX_WRK_capital_marker", 386, y, number + 2, transparent=True))
        parts.append(textbox(f"WRK_capital_legend_text_{number}", f"WRK_capital_legend_{number}",
                             350, y + 36, 100, 44, centered=True))
    for state in STATES:
        parts.append(textbox(f"WRK_capital_{state}_detail", f"WRK_capital_detail_{state}",
                             12, 360, 436, 52, tooltip=f"WRK_capital_{state}_tt"))
        if state == 40:
            parts.append(textbox('WRK_capital_network_status', 'WRK_capital_network_status',
                                 12, 418, 436, 58, tooltip='WRK_capital_network_tt'))
            parts.append(button('WRK_capital_tower_central', 'GFX_WRK_capital_action',
                                12, 486, 'WRK_capital_network_tt', 'WRK_capital_tower_central'))
            continue
        for decision, _, _, slot in ACTIONS:
            parts.append(button(f"WRK_capital_{state}_{decision}", "GFX_WRK_capital_action",
                                12 + (slot % 2) * 222, 418 + (slot // 2) * 34,
                                f"WRK_capital_action_{decision}_tt", f"WRK_capital_action_{decision}"))
    parts.append('\n'.join(['\t}', '', '\tcontainerWindowType = {', '\t\tname = "ADISCORD_vorkerland_intrigue_window"',
                           '\t\tposition = { x = 0 y = 0 }', '\t\tsize = { width = 460 height = 360 }', '\t\tclipping = no']))
    for number in range(1, 7):
        x = 5 + ((number - 1) % 2) * 230
        y = 14 + ((number - 1) // 2) * 112
        prefix = f"WRK_intrigue_{number}"
        parts.extend([icon(prefix + "_card", "GFX_WRK_intrigue_card", x, y, tooltip=prefix + "_tt"),
                      icon(prefix + "_portrait", "GFX_WRK_intrigue_portrait_empty", x + 11, y + 11, scale=0.28, transparent=True),
                      textbox(prefix + "_name", prefix + "_name", x + 66, y + 11, 130, 44),
                      textbox(prefix + "_status", prefix + "_status", x + 12, y + 76, 196, 20)])
    parts.append('\t}')
    return "\n\n".join(parts) + "\n"


def decision_definitions():
    from tools.validators.validate_adiscord_division_templates import parse_clausewitz

    roots = parse_clausewitz((ROOT / DECISIONS).read_text(encoding="utf-8-sig"))
    return {decision.key: {entry.key: entry.value for entry in decision.value}
            for category in roots if isinstance(category.value, list)
            for decision in category.value if isinstance(decision.value, list)}


def native_conditions(entries, state, indent=4):
    """Bind the native decision's FROM target without duplicating its conditions."""
    lines = []
    for entry in entries:
        key = str(state) if entry.key == "FROM" else entry.key
        prefix = '\t' * indent
        if isinstance(entry.value, list):
            lines.extend([f'{prefix}{key} = {{', native_conditions(entry.value, state, indent + 1), prefix + '}'])
        else:
            value = str(state) if entry.value == "FROM" else entry.value
            if not key:
                raise ValueError('Unsupported bare token in decision condition')
            if entry.quoted:
                value = json.dumps(value, ensure_ascii=False)
            lines.append(f'{prefix}{key} = {value}')
    return '\n'.join(lines)


def selection_condition(state):
    check = f'check_variable = {{ var = WRK_capital_selected_state value = {state} compare = equals }}'
    if state == 32:
        return f'OR = {{ NOT = {{ has_variable = WRK_capital_selected_state }} {check} }}'
    return check


def network_display_triggers():
    project = '40 = { check_variable = { var = ADISCORD_vorkerland_prep_project value = 3 compare = equals } }'
    blocks = []
    for status, clear in (('open', 'yes'), ('closed', 'no')):
        blocks.append(f'\t\t\tWRK_capital_network_{status}_visible = {{\n'
                      f'\t\t\t\t{project}\n'
                      f'\t\t\t\tWRK_network_exfiltration_route_clear = {clear}\n\t\t\t}}')
    for name in ('WRK_capital_network_status', 'WRK_capital_tower_central'):
        blocks.append(f'\t\t\t{name}_visible = {{\n\t\t\t\t{project}\n'
                      f'\t\t\t\t{selection_condition(40)}\n\t\t\t}}')
    blocks.append('\t\t\tWRK_capital_tower_central_click_enabled = { always = yes }')
    return '\n'.join(blocks)


def interaction_sections():
    definitions = decision_definitions()
    effects = ['\t\t\tWRK_capital_tower_central_click = {\n'
               '\t\t\t\tset_variable = { var = WRK_capital_selected_state value = 32 }\n\t\t\t}']
    triggers = [f'\t\t\tWRK_capital_legend_text_{n}_visible = {{ always = no }}' for n in range(1, 4)]
    triggers.append(network_display_triggers())
    for state in STATES:
        selected = selection_condition(state)
        effects.append(f'\t\t\tWRK_capital_{state}_select_click = {{\n'
                       f'\t\t\t\tset_variable = {{ var = WRK_capital_selected_state value = {state} }}\n\t\t\t}}')
        effects.append(f'\t\t\tWRK_capital_{state}_marker_select_click = {{\n'
                       f'\t\t\t\tset_variable = {{ var = WRK_capital_selected_state value = {state} }}\n\t\t\t}}')
        for suffix in ('select', 'marker_select'):
            triggers.append(f'\t\t\tWRK_capital_{state}_{suffix}_click_enabled = {{ always = yes }}')
        if state == 40:
            triggers.append('\t\t\tWRK_capital_40_marker_select_visible = { always = no }')
        else:
            triggers.append(f'\t\t\tWRK_capital_{state}_marker_select_visible = {{\n'
                            f'\t\t\t\t{state} = {{ WRK_capital_set_marker_frame = yes }}\n'
                            '\t\t\t\tcheck_variable = { var = WRK_capital_frame value = 1 compare = greater_than }\n\t\t\t}')
        for suffix in ('selected', 'detail'):
            triggers.append(f'\t\t\tWRK_capital_{state}_{suffix}_visible = {{ {selected} }}')
        if state == 40:
            continue
        for decision, _, _, _ in ACTIONS:
            fields = definitions[decision]
            # These decisions gate repetition through their own district flags.
            # Reject incompatible additions rather than bypass an engine cooldown.
            if any(key in fields for key in ('days_re_enable', 'custom_cost_trigger', 'custom_cost_text')):
                raise ValueError(f'Unsupported native decision cost/cooldown: {decision}')
            conditions = [*fields.get('visible', []), *fields.get('target_trigger', []), *fields.get('available', [])]
            native = native_conditions(conditions, state)
            price = int(fields['cost'])
            enabled = native + f'\n\t\t\t\tNOT = {{ has_political_power < {price} }}'
            name = f'WRK_capital_{state}_{decision}'
            visibility = native_conditions(fields.get('visible', []), state)
            triggers.append(f'\t\t\t{name}_visible = {{\n\t\t\t\t{selected}\n{visibility}\n\t\t\t}}')
            triggers.append(f'\t\t\t{name}_click_enabled = {{\n{enabled}\n\t\t\t}}')
            effects.append(f'\t\t\t{name}_click = {{\n\t\t\t\tif = {{\n\t\t\t\t\tlimit = {{\n'
                           f'\t\t\t\t\t\t{selected}\n' + '\n'.join('\t\t' + line for line in enabled.splitlines()) + '\n\t\t\t\t\t}\n'
                           f'\t\t\t\t\tactivate_targeted_decision = {{ target = {state} decision = {decision} }}\n'
                           '\t\t\t\t}\n\t\t\t}')
    return '\n'.join(effects), '\n'.join(triggers)


def interaction_gui():
    source = (ROOT / SGUI).read_bytes()
    newline = '\r\n' if b'\r\n' in source else '\n'
    text = source.decode('utf-8')
    start = text.index('\tADISCORD_vorkerland_capital_panel = {')
    end = text.index('\tADISCORD_vorkerland_intrigue_panel = {', start)
    panel = text[start:end]
    # Keep named frame bindings available to the mechanical script, but hide the
    # redundant legend icons together with their text; district tooltips explain them.
    for n in range(1, 4):
        pattern = rf'(WRK_capital_legend_icon_{n}_visible = \{{.*?)(always = (?:yes|no))(\s*\}})'
        panel, count = re.subn(pattern, lambda match: match[1] + 'always = no' + match[3], panel, flags=re.S)
        if count != 1:
            raise ValueError(f'Expected one capital legend frame binding: {n}')
    effects, triggers = interaction_sections()
    for kind, body in (('EFFECTS', '\t\teffects = {\n' + effects + '\n\t\t}'), ('TRIGGERS', triggers)):
        begin, finish = f'# BEGIN WRK CAPITAL {kind}', f'# END WRK CAPITAL {kind}'
        block = ('\t\t' + begin + '\n' + body + '\n\t\t' + finish + '\n').replace('\n', newline)
        if begin in panel:
            pattern = r'(?m)^[\t ]*' + begin + r'\r?\n.*?^[\t ]*' + finish + r'\r?\n'
            panel = re.sub(pattern, lambda _: block, panel, flags=re.S)
        elif kind == 'EFFECTS':
            panel = panel.replace('\t\ttriggers = {', block + '\t\ttriggers = {', 1)
        else:
            panel = panel.replace('\t\ttriggers = {' + newline, '\t\ttriggers = {' + newline + block, 1)
    return (text[:start] + panel + text[end:]).encode('utf-8')


def interaction_localisation(language):
    path = Path(f'localisation/{language}/ADISCORD_vorkerland_l_{language}.yml')
    source = (ROOT / path).read_text(encoding='utf-8-sig')
    russian = language == 'russian'
    old = re.search(r'(?m)^ WRK_capital_overview_tt:\d* "(.*)"$', source)
    if old is None:
        old = re.search(r'(?m)^ ADISCORD_vorkerland_prewar_category_desc:\d* "(.*)"$', source)
    report = old[1]
    compact = ('Комитеты' if russian else 'Committees') + ': §Y[?global.ADISCORD_vorkerland_camp_committees|0]§!   '
    compact += ('Штаб' if russian else 'Staff') + ': §Y[?global.ADISCORD_vorkerland_camp_staff|0]§!   '
    compact += ('Инженеры' if russian else 'Engineers') + ': §Y[?global.ADISCORD_vorkerland_camp_engineers|0]§!'
    source = re.sub(r'(?m)^( ADISCORD_vorkerland_prewar_category_desc:\d* )".*"$',
                    lambda match: match[1] + '"' + compact + '"', source)
    texts = {'WRK_capital_overview': 'Сводка' if russian else 'Report',
             'WRK_capital_overview_tt': report,
             'WRK_capital_symbols_tt': ('Щит - патруль. Восклицательный знак - волнения. Знак запрета - бунт. Наклонная черта - раскрытая ячейка.' if russian else
                                        'Shield: patrol. Exclamation mark: unrest. No-entry sign: riot. Diagonal slash: exposed cell.')}
    texts['WRK_capital_tower_central'] = 'Центральный дистрикт' if russian else 'Central District'
    texts['WRK_capital_network_status'] = ('§YУвести Уоркера по линиям сети§!\\nКанал связи с Центром: ' if russian else
                                         '§YExtract Worker through the network§!\\nCentral link: ') + '[GetVorkerlandNetworkRouteStatus]'
    texts['WRK_capital_network_tt'] = (
        '§YБашня - Центральный дистрикт§!\\nСостояние проекта: [GetVorkerlandPrepCommunications]\\n'
        'Канал: [GetVorkerlandNetworkRouteStatus]. Нужна скрытая ячейка уровня 2 или выше в Центральном дистрикте. '
        'Затаившаяся подходит; раскрытая или легализованная - нет.\\n'
        'Зелёный пунктир обозначает связь с ячейкой, крест - закрытую связь. Это не уличный маршрут.\\n'
        'Прогноз: [GetVorkerlandWorkerFateForecast]' if russian else
        '§YTower - Central District§!\\nProject status: [GetVorkerlandPrepCommunications]\\n'
        'Link: [GetVorkerlandNetworkRouteStatus]. Requires a hidden level 2 or higher cell in the Central District. '
        'Dormant cells qualify; exposed or legalized cells do not.\\n'
        'Green dashes show the cell connection; a cross marks a closed link. This is not a street route.\\n'
        'Forecast: [GetVorkerlandWorkerFateForecast]')
    previous_symbols = re.search(r'(?m)^ WRK_capital_symbols_tt:\d* "(.*)"$', source)

    def district_tooltip(match):
        body = match[2]
        suffixes = ['\\n\\n$WRK_capital_symbols_tt$']
        if previous_symbols:
            suffixes.append('\\n\\n' + previous_symbols[1])
        for suffix in suffixes:
            if body.endswith(suffix):
                body = body[:-len(suffix)]
        if match[1].startswith(' WRK_capital_40_tt:'):
            body = '§Y[40.GetName]§!\\n[GetVorkerlandPrepCommunications]\\n' + (
                'Судьба Уоркера: ' if russian else "Worker's fate: ") + '[GetVorkerlandWorkerFateForecast]'
        # Export complete tooltip text, without a second localisation lookup.
        return match[1] + body + '\\n\\n' + texts['WRK_capital_symbols_tt'] + match[3]

    for state in STATES:
        pattern = rf'(?m)^( WRK_capital_{state}_tt:\d* ")(.*)(")$'
        source = re.sub(pattern, district_tooltip, source)
    for state in STATES:
        note = f'[{state}.WRKGetCapitalDistrictNote]' if state != 40 else (
            '[GetVorkerlandPrepCommunications]')
        texts[f'WRK_capital_detail_{state}'] = f'§Y[{state}.GetName]§!\\n' + note
    results_ru = ('Недовольство -25; с хлебным резервом -30. Без бунта. Перерыв между мерами [?ROOT.WRK_unrest_cooldown|0] дн.',
                  'Недовольство -30, прекращает бунт. Баланс сил +0.05 к округам. Перерыв [?ROOT.WRK_unrest_cooldown|0] дн.',
                  'Недовольство -35, прекращает бунт. Стабильность -1%; другие районы без патруля +8. Перерыв [?ROOT.WRK_unrest_cooldown|0] дн.',
                  '21 день без роста недовольства, затем -40 и прекращение бунта. Патрулей одновременно: [?ROOT.WRK_unrest_patrol_limit|0].',
                  'Через 21 день ячейка уровня 1. Внимание +10; с аварийными мастерскими +5. Проектов сети одновременно: [?ROOT.WRK_cells_work_limit|0].',
                  'Через 28 дней уровень ячейки +1, внимание +15. Нужна скрытая действующая ячейка ниже уровня 3. Проектов сети одновременно: [?ROOT.WRK_cells_work_limit|0].',
                  'Внимание -[?ROOT.WRK_cell_cover|0]. Ячейка бездействует 45 дней. Нельзя применить к раскрытой или уже бездействующей ячейке.',
                  'Раскрытая ячейка снова скрыта; внимание становится 50.',
                  'Внимание 0, ячейка защищена от раскрытия. Расширение закрывается; при расколе учитывается как уровень 1. Нельзя во время работ.')
    results_en = ('Unrest -25, or -30 with the ration reserve. No riot. Shared measure cooldown: [?ROOT.WRK_unrest_cooldown|0] days.',
                  'Unrest -30; ends the riot. Balance +0.05 toward districts. Shared cooldown: [?ROOT.WRK_unrest_cooldown|0] days.',
                  'Unrest -35; ends the riot. Stability -1%; other unpatrolled districts +8. Shared cooldown: [?ROOT.WRK_unrest_cooldown|0] days.',
                  'No unrest growth for 21 days, then -40 and ends the riot. Patrols at a time: [?ROOT.WRK_unrest_patrol_limit|0].',
                  'Level 1 cell after 21 days. Heat +10, or +5 with emergency workshops. Network projects at a time: [?ROOT.WRK_cells_work_limit|0].',
                  'After 28 days: cell level +1, heat +15. Requires an active hidden cell below level 3. Network projects at a time: [?ROOT.WRK_cells_work_limit|0].',
                  'Heat -[?ROOT.WRK_cell_cover|0]. Cell dormant for 45 days. Requires a hidden, active cell.',
                  'Exposed cell becomes hidden; heat becomes 50.',
                  'Heat 0; protected from exposure. Cannot expand; counts as level 1 on collapse. Requires no ongoing work.')
    definitions = decision_definitions()
    for index, (decision, ru, en, _) in enumerate(ACTIONS):
        price = definitions[decision]['cost']
        key = 'WRK_capital_action_' + decision
        texts[key] = f'{ru if russian else en}  {price} £political_power_texticon'
        texts[key + '_tt'] = f'§Y${decision}$§!\\n{price} £political_power_texticon\\n' + (results_ru if russian else results_en)[index]
        focus = next((e.value for e in definitions[decision].get('visible', []) if e.key == 'has_completed_focus'), None)
        if focus:
            texts[key + '_tt'] += ('\\nНужен фокус: ' if russian else '\\nRequires focus: ') + f'${focus}$'
    begin, end = '# BEGIN WRK CAPITAL INTERACTION TEXT', '# END WRK CAPITAL INTERACTION TEXT'
    content = begin + '\n' + '\n'.join(f' {key}:0 "{value}"' for key, value in texts.items()) + '\n' + end + '\n'
    if begin in source:
        source = re.sub(re.escape(begin) + r'\n.*?' + re.escape(end) + r'\n', lambda _: content, source, flags=re.S)
    else:
        source = source.rstrip('\n') + '\n\n' + content
    return path, source.encode('utf-8-sig')


def gfx_block(images):
    parts = ['\t# Generated by tools/builders/build_adiscord_vorkerland_capital_map.py.']
    for filename in images:
        name = Path(filename).stem
        parts.append("\n".join(['\tspriteType = {', f'\t\tname = "GFX_{name}"',
                                f'\t\ttexturefile = "{(OUT / filename).as_posix()}"',
                                f'\t\tnoOfFrames = {FRAME_COUNTS.get(name, 1)}',
                                '\t\ttransparencecheck = yes', '\t}']))
    return "\n\n".join(parts) + "\n"


def replace_section(source: bytes, content: str) -> bytes:
    """Patch only our marked bytes; preserve existing windows and line endings."""
    newline = b"\r\n" if b"\r\n" in source else b"\n"
    begin, end = BEGIN.encode(), END.encode()
    body = content.rstrip("\n").replace("\n", newline.decode()).encode("utf-8")
    replacement = b"\t" + begin + newline + body + newline + b"\t" + end + newline
    if begin in source or end in source:
        if source.count(begin) != 1 or source.count(end) != 1:
            raise ValueError("Ambiguous generated capital section")
        pattern = rb"(?m)^[\t ]*" + begin + rb"[^\r\n]*\r?\n.*?^[\t ]*" + end + rb"\r?\n"
        result, count = re.subn(pattern, lambda _: replacement, source, flags=re.S)
        if count != 1:
            raise ValueError("Unterminated generated capital section")
        return result
    match = re.search(rb"(?m)^}[ \t]*(?:\r?\n)?\Z", source)
    if not match:
        raise ValueError("Expected existing root GUI/GFX closing brace")
    return source[:match.start()] + newline + replacement + source[match.start():]


def png_bytes(image):
    stream = io.BytesIO()
    image.save(stream, format="PNG", optimize=True)
    return stream.getvalue()


def hit_rows(image):
    """Browser backgrounds ignore alpha for pointer tests; export exact PNG runs."""
    rows = []
    for row in np.asarray(image.getchannel("A")):
        occupied = np.pad((row > 0).astype(np.int8), (1, 1))
        edges = np.flatnonzero(np.diff(occupied))
        rows.append(edges.reshape(-1, 2).tolist())
    return rows


def mockup_html(images, geometry):
    assets = {Path(name).stem: "data:image/png;base64," + base64.b64encode(png_bytes(image)).decode()
              for name, image in images.items()}
    with Image.open(ROOT / "gfx/interface/decisions/ui/ADISCORD_decisions_category_desc_tile.dds") as texture:
        assets["paper"] = "data:image/png;base64," + base64.b64encode(png_bytes(texture.crop((16, 16, 32, 32)).convert("RGBA"))).decode()
    data = json.dumps({"assets": assets, "markers": geometry["markers"], "states": STATES, "labels": STATE_LABELS,
                       "hitRows": {state: hit_rows(images[f"WRK_capital_hit_{state}.png"]) for state in STATES}}, separators=(",", ":"))
    return (r'''<!doctype html><html lang="ru"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<!-- Generated by tools/builders/build_adiscord_vorkerland_capital_map.py. -->
<title>Столица Воркерланда</title><style>
*{box-sizing:border-box}body{margin:0;background:#171714;color:#e0dfd5;font:14px Arial,sans-serif}
main{margin:30px auto;width:480px;max-width:100%}.category{border:1px solid #72674b;padding:8px;background:#11110f}
h1{text-align:center;font-size:17px;margin:0;padding:12px;border:1px solid #514a36;background:#1d1c18}
.camps{font-size:13px;margin:12px 4px 0}.camps b{color:#dac375}.panel{position:relative;width:460px;height:524px;margin:auto}
.sprite{position:absolute;pointer-events:none;background-repeat:no-repeat}.title{position:absolute;left:10px;top:8px;font-size:20px;font-weight:bold}
.report{position:absolute;right:10px;top:10px;font-size:13px;color:#d7c395}.legend{position:absolute;left:350px;width:100px;text-align:center;font-size:13px;pointer-events:none}
.detail{position:absolute;left:12px;top:360px;width:436px;height:52px;line-height:22px}.detail b{color:#ddc680}
.actions{position:absolute;left:12px;top:418px;width:436px;display:grid;grid-template-columns:214px 214px;gap:6px 8px}
button{font:13px Arial;color:#ddd9ca;background:#28271f;border:1px solid #88794f;padding:5px 3px;height:28px;cursor:pointer}
button:hover{background:#49432c;border-color:#dcc482}button:disabled{opacity:.35;cursor:default}
.controls{display:flex;gap:8px;margin:14px 0}.controls button[aria-pressed=true]{color:#eacf8a;border-color:#eacf8a}
.demo{display:grid;gap:8px;margin-bottom:14px}.demo label{display:flex;justify-content:space-between;align-items:center}.demo select{background:#28271f;color:#ddd9ca;padding:4px;width:280px}.network{grid-column:1 / -1;height:62px;line-height:24px}.network b{color:#ddc680}
.note{font-size:12px;color:#a8a38e;line-height:1.5}
</style><main><div class="controls"><button id="mode-unrest">Комитеты</button><button id="mode-cells" aria-pressed="true">Сеть Воркса</button></div>
<div class="demo"><label>Башня<select id="tower-project"><option value="0">Проект не выбран</option><option value="1">Гражданская эвакуация</option><option value="2">Военная эвакуация</option><option value="3" selected>Увести Уоркера по линиям сети</option></select></label><label>Проект<select id="tower-stage"><option value="pending">Работы идут</option><option value="contested">Идёт спор за Башню</option><option value="ready" selected>Готов</option></select></label><label>Ячейка в Центре<select id="central-cell"><option value="weak">Уровень 1</option><option value="hidden" selected>Уровень 2, скрытая</option><option value="dormant">Уровень 2, затаившаяся</option><option value="exposed">Уровень 2, раскрытая</option><option value="legal">Уровень 2, легализованная</option></select></label></div>
<section class="category" id="category"><h1>Наследство Конфедерации</h1><div class="camps">Комитеты: <b>40</b> &nbsp; Штаб: <b>30</b> &nbsp; Инженеры: <b>30</b></div>
<div class="panel" id="capital"><div class="title">Столица Воркерланда</div><span class="report" title="Объекты наследства, лагеря, баланс центра и округов, правила недовольства и сети.">Сводка</span><div class="detail" id="detail"></div><div class="actions" id="actions"></div></div></section>
<p class="note">Нажмите на район. Наведение выделяет контур; карточка и меры относятся к выбранному району. Значения демонстрационные. Кнопки здесь изменяют только макет.</p>
</main><script>
const data=__DATA__,cap=document.getElementById('capital');
document.getElementById('category').style.backgroundImage=`url("${data.assets.paper}")`;
function sprite(name,w,h,x,y,frame=1){const e=document.createElement('div');e.className='sprite';Object.assign(e.style,{width:w+'px',height:h+'px',left:x+'px',top:y+'px',backgroundImage:`url("${data.assets[name]}")`,backgroundPosition:`-${(frame-1)*w}px 0`});cap.append(e);return e;}
function capitalHitAt(x,y){if(x<0||x>=330||y<0||y>=290)return null;x=Math.floor(x);y=Math.floor(y);for(const s of data.states)if(data.hitRows[s][y].some(([a,b])=>x>=a&&x<b))return s;return null;}
sprite('WRK_capital_panel',460,524,0,0);sprite('WRK_capital_map_background',330,290,65,48);
const streets={},selects={},markers={};
data.states.forEach(s=>{selects[s]=sprite('WRK_capital_selected_'+s,330,290,65,48);streets[s]=sprite('WRK_capital_state_'+s,330,290,65,48);});
const route=sprite('WRK_capital_route',330,290,65,48),link=sprite('WRK_capital_network_link',330,290,65,48);
data.states.forEach(s=>{const [x,y]=data.markers[s];markers[s]=sprite('WRK_capital_marker',28,28,x+51,y+34);});
let selected=40,hover=null,mode='cells',project=3,stage='ready',central='hidden';const unrest={32:25,33:30,34:35,35:30,36:40,37:65,38:35,39:45,40:0},cells={32:2,33:1,34:0,35:2,36:0,37:1,38:0,39:3,40:0},patrol=new Set();
function linkOpen(){return cells[32]>=2&&['hidden','dormant'].includes(central);}
function forecast(){if(stage!=='ready')return 'Исход ещё не обеспечен: проект не завершён или оспаривается.';return linkOpen()?'Уоркер исчезнет: ни комитеты, ни штаб не узнают, где он.':'Канал закрыт: судьбу решит обычный бросок с рычагами сети.';}
function networkTip(){return 'Нужна скрытая ячейка уровня 2 или выше в Центральном дистрикте. Затаившаяся подходит; раскрытая или легализованная - нет.\nЗелёный пунктир - связь с ячейкой; крест - закрытая связь.\n'+forecast();}
function status(s){if(s===40)return project===0?'Проект не выбран':stage==='pending'?'Работы идут':stage==='contested'?'Идёт спор за Башню':project===3?'Проект сети готов':'Эвакуация готова';if(mode==='cells')return 'Сеть: '+(cells[s]?'ячейка уровня '+cells[s]:'ячейки нет');return 'Недовольство: '+unrest[s]+' / 100 - '+(patrol.has(s)?'патруль':unrest[s]>=100?'бунт':unrest[s]>=60?'волнения':unrest[s]>=40?'напряжённо':'спокойно');}
function paint(){for(const s of data.states){let f=mode==='cells'?(cells[s]?4:1):unrest[s]>=100?6:unrest[s]>=60?5:unrest[s]<40?2:1;if(s===40)f=1;streets[s].style.backgroundPosition=`-${(f-1)*330}px 0`;let m=mode==='cells'?(cells[s]?2:1):patrol.has(s)?6:unrest[s]>=100?5:unrest[s]>=60?4:1;markers[s].style.backgroundPosition=`-${(m-1)*28}px 0`;selects[s].style.display=s===selected||s===hover?'block':'none';selects[s].style.opacity=s===selected?'1':'.5';}
route.style.backgroundPosition=`-${(project===1?1:project===2?2:0)*330}px 0`;link.style.display=project===3?'block':'none';link.style.backgroundPosition=linkOpen()?'0 0':'-330px 0';
}
function detail(){const d=document.getElementById('detail');d.innerHTML='<b>'+data.labels[selected]+'</b><br>'+status(selected);d.title=selected===40&&project===3?networkTip():status(selected);const box=document.getElementById('actions');box.replaceChildren();if(selected===40){if(project===3){const text=document.createElement('div');text.className='network';text.innerHTML='<b>Увести Уоркера по линиям сети</b><br>Канал связи с Центром: '+(linkOpen()?'открыт':'закрыт');text.title=networkTip();const jump=document.createElement('button');jump.textContent='Центральный дистрикт';jump.title=networkTip();jump.onclick=()=>{selected=32;paint();detail();};box.append(text,jump);}return;}
const actions=mode==='unrest'?[['Пайки 35',()=>unrest[selected]=Math.max(0,unrest[selected]-25)],['Цех комитету 45',()=>unrest[selected]=Math.max(0,unrest[selected]-30)],['Уполномоченный 30',()=>unrest[selected]=Math.max(0,unrest[selected]-35)],['Рабочий патруль 40',()=>patrol.add(selected)]]:[['Создать ячейку 30',()=>cells[selected]=1],['Расширить сеть 40',()=>cells[selected]=Math.min(3,cells[selected]+1)],['Залечь на дно 20',()=>{}],['Новые пропуска 45',()=>{}],['Легализовать 35',()=>{}]];
actions.forEach(([label,run],i)=>{let b=document.createElement('button');b.textContent=label+' ◆';b.title='Демонстрация. В игре проверяются фокус, цена, состояние района и занятость операции.';b.disabled=mode==='cells'&&((i===0&&cells[selected]>0)||(i>0&&cells[selected]===0));b.onclick=()=>{run();paint();detail();};box.append(b);});}
function point(e){const r=cap.getBoundingClientRect();return capitalHitAt(e.clientX-r.left-65,e.clientY-r.top-48);}
cap.addEventListener('pointermove',e=>{hover=point(e);cap.style.cursor=hover?'pointer':'default';cap.title=hover?data.labels[hover]+'\n'+status(hover)+(hover===40&&project===3?'\n'+networkTip():'\nЩит - патруль; ! - волнения; запрет - бунт.'):'';paint();});
cap.addEventListener('pointerleave',()=>{hover=null;paint();});cap.addEventListener('click',e=>{const s=point(e);if(s){selected=s;paint();detail();}});
document.getElementById('tower-project').onchange=e=>{project=Number(e.target.value);paint();detail();};
document.getElementById('tower-stage').onchange=e=>{stage=e.target.value;paint();detail();};
document.getElementById('central-cell').onchange=e=>{central=e.target.value;cells[32]=central==='weak'?1:2;paint();detail();};
for(const m of ['unrest','cells'])document.getElementById('mode-'+m).onclick=()=>{mode=m;for(const n of ['unrest','cells'])document.getElementById('mode-'+n).setAttribute('aria-pressed',n===m);paint();detail();};paint();detail();
</script></html>'''.replace('__DATA__',data)).encode('utf-8')


def review_image(images, geometry, network=False):
    """Compose the native-size category with demonstration values in memory."""
    from PIL import ImageFont

    def font(size):
        for name in ('C:/Windows/Fonts/arial.ttf', 'DejaVuSans.ttf'):
            try:
                return ImageFont.truetype(name, size)
            except OSError:
                pass
        return ImageFont.load_default()

    with Image.open(ROOT / 'gfx/interface/decisions/ui/ADISCORD_decisions_category_desc_tile.dds') as texture:
        tile = texture.crop((16, 16, 32, 32)).convert('RGBA')
    sheet = Image.new('RGBA', (480, 602), (*GRAPHITE, 255))
    for y in range(0, 602, 16):
        for x in range(0, 480, 16):
            sheet.alpha_composite(tile, (x, y))
    panel = images['WRK_capital_panel.png'].copy()
    panel.alpha_composite(images['WRK_capital_map_background.png'], (MAP_X, 48))
    for state in STATES:
        frame = 5 if state == 37 else 2 if state in (32, 33, 34, 35, 38) else 1
        if network:
            frame = 4 if state in (32, 35, 39, 40) else 1
        panel.alpha_composite(images[f'WRK_capital_state_{state}.png'].crop(((frame - 1) * WIDTH, 0, frame * WIDTH, HEIGHT)), (MAP_X, 48))
    selected = 40 if network else 37
    panel.alpha_composite(images[f'WRK_capital_selected_{selected}.png'], (MAP_X, 48))
    if network:
        panel.alpha_composite(images['WRK_capital_network_link.png'].crop((0, 0, WIDTH, HEIGHT)), (MAP_X, 48))
    x, y = geometry['markers'][32 if network else 37]
    marker_frame = 1 if network else 3
    panel.alpha_composite(images['WRK_capital_marker.png'].crop((28 * marker_frame, 0, 28 * (marker_frame + 1), 28)), (MAP_X + x - 14, y + 34))
    draw = ImageDraw.Draw(panel)
    draw.text((10, 8), 'Столица Воркерланда', font=font(19), fill=WHITE)
    draw.text((353, 12), 'Сводка', font=font(13), fill=WORKER)
    draw.text((12, 360), 'Башня Единства' if network else 'Северо-Западный дистрикт', font=font(17), fill=WORKER)
    draw.text((12, 386), 'Проект сети готов' if network else 'Недовольство: 65 / 100 - волнения', font=font(14), fill=WHITE)
    prices = (35, 45, 30, 40)
    for index, (_, label, _, slot) in enumerate(ACTIONS[:0 if network else 4]):
        x, y = 12 + (slot % 2) * 222, 418 + (slot // 2) * 34
        panel.alpha_composite(images['WRK_capital_action.png'].crop((0, 0, 214, 28)), (x, y))
        draw.text((x + 107, y + 6), f'{label}  {prices[index]}', font=font(13), fill=WHITE, anchor='mt')
    if network:
        draw.text((12, 418), 'Увести Уоркера по линиям сети', font=font(16), fill=WORKER)
        draw.text((12, 442), 'Канал связи с Центром: открыт', font=font(14), fill=WORX)
        panel.alpha_composite(images['WRK_capital_action.png'].crop((0, 0, 214, 28)), (12, 486))
        draw.text((119, 492), 'Центральный дистрикт', font=font(13), fill=WHITE, anchor='mt')
    sheet.alpha_composite(panel, (10, 70))
    draw = ImageDraw.Draw(sheet)
    draw.rectangle((1, 1, 478, 600), outline=(*MUTED, 255))
    draw.rectangle((8, 8, 471, 41), outline=(*MUTED, 200))
    draw.text((240, 16), 'Наследство Конфедерации', font=font(16), fill=WHITE, anchor='mt')
    draw.text((22, 50), 'Комитеты: 40     Штаб: 30     Инженеры: 30', font=font(14), fill=WORKER)
    return sheet


def build_outputs(include_preview=False):
    images, geometry = render_images()
    outputs = {OUT / name: png_bytes(image) for name, image in images.items()}
    outputs[GUI] = replace_section((ROOT / GUI).read_bytes(), gui_block(geometry))
    outputs[GFX] = replace_section((ROOT / GFX).read_bytes(), gfx_block(images))
    outputs[SGUI] = interaction_gui()
    for language in ('russian', 'english'):
        path, contents = interaction_localisation(language)
        outputs[path] = contents
    outputs[MOCKUP] = mockup_html(images, geometry)
    if include_preview:
        outputs[PREVIEW] = png_bytes(review_image(images, geometry))
    return outputs, geometry


def differences(outputs):
    return [path for path, expected in outputs.items()
            if not (ROOT / path).is_file() or (ROOT / path).read_bytes() != expected]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true", help="compare deterministic outputs without writing (default)")
    mode.add_argument("--apply", action="store_true", help="write changed owned outputs only")
    parser.add_argument("--preview", action="store_true", help="include the temporary development review image")
    args = parser.parse_args(argv)
    outputs, geometry = build_outputs(args.preview)
    changed = differences(outputs)
    if args.apply:
        for relative in changed:
            target = ROOT / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(outputs[relative])
        print(f"WRK capital outputs written: {len(changed)}")
    else:
        for relative in changed:
            print(f"Different or missing: {relative.as_posix()}")
    remaining = differences(outputs)
    print(f"WRK capital outputs checked: {len(outputs)}; differences: {len(remaining)}; source crop: {geometry['source_box']}")
    return int(bool(remaining))


if __name__ == "__main__":
    sys.exit(main())
