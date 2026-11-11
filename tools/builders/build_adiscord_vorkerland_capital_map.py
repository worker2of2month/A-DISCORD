"""Build WRK capital street maps, sprite bindings and a self-contained review mockup.

Owns gfx/interface/vorkerland_capital/*.png, the marked sections in the existing
ADISCORD_vorkerland.gui/gfx, and docs/mockups/vorkerland_capital.html.
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
OUT = Path("gfx/interface/vorkerland_capital")
GUI = Path("interface/ADISCORD_vorkerland.gui")
GFX = Path("interface/ADISCORD_vorkerland.gfx")
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
SS = 3
SEED = 320336373840
BEGIN = "# BEGIN GENERATED WRK CAPITAL VISUALS"
END = "# END GENERATED WRK CAPITAL VISUALS"
GRAPHITE = (32, 39, 43)
TURQUOISE = (162, 218, 213)
WORKER = (235, 203, 100)
STAFF = (179, 154, 242)
WORX = (169, 214, 111)
RED = (244, 101, 101)
WHITE = (219, 230, 230)
MUTED = (109, 129, 136)
FRAME_COUNTS = {
    "WRK_capital_marker": 6,
    "WRK_capital_route": 3,
    "WRK_intrigue_card": 3,
    **{f"WRK_capital_state_{state}": 6 for state in STATES},
}


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
                    stroke(local, [point, nodes[i + 1, j]], (*TURQUOISE, 150), 0.65)
                if rng.random() > 0.12:
                    stroke(local, [point, nodes[i, j + 1]], (*TURQUOISE, 150), 0.65)
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


def render_images():
    geometry = geography()
    streets = street_network(geometry)
    background = Image.new("RGBA", (WIDTH, HEIGHT), (*GRAPHITE, 255))
    background.alpha_composite(streets)
    for mask in geometry["masks"].values():
        rim = ImageChops.subtract(mask, mask.filter(ImageFilter.MinFilter(3)))
        edge = Image.new("RGBA", background.size, (*MUTED, 120))
        edge.putalpha(rim.point(lambda value: value * 100 // 255))
        background.alpha_composite(edge)
    ornament = canvas()
    x, y = geometry["anchors"][40]
    # The tower is offset above its tiny state; the leader terminates at its anchor.
    stroke(ornament, [(x - 10, y - 7), (x, y)], WHITE, 0.8)
    rectangle(ornament, (x - 17, y - 27, x - 7, y - 7), GRAPHITE)
    polygon(ornament, [(x - 17, y - 7), (x - 7, y - 7), (x - 9, y - 19),
                      (x - 11, y - 19), (x - 12, y - 27), (x - 13, y - 19), (x - 15, y - 19)], WHITE)
    stroke(ornament, [(x - 12, y - 15), (x - 12, y - 9)], GRAPHITE, 1)
    background.alpha_composite(finish(ornament))
    images = {"WRK_capital_map_background.png": background}
    for state, mask in geometry["masks"].items():
        images[f"WRK_capital_state_{state}.png"] = state_strip(streets, mask)
    images["WRK_capital_marker.png"] = marker_strip()
    images["WRK_capital_route.png"] = route_strip(geometry)
    images["WRK_intrigue_card.png"] = card_strip()
    panel = canvas((460, 360), (*GRAPHITE, 255))
    rectangle(panel, (0.5, 0.5, 459, 359), outline=(65, 81, 87, 255), width=1)
    stroke(panel, [(10, 39), (450, 39)], (*MUTED, 125), 0.7)
    stroke(panel, [(345, 48), (345, 338)], (*MUTED, 125), 0.7)
    images["WRK_capital_panel.png"] = finish(panel)
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


def icon(name, sprite, x, y, frame=1, scale=None, transparent=False):
    lines = ["\t\ticonType = {", f'\t\t\tname = "{name}"',
             f"\t\t\tposition = {{ x = {x} y = {y} }}", f'\t\t\tquadTextureSprite = "{sprite}"',
             f"\t\t\tframe = {frame}"]
    if scale is not None:
        lines.append(f"\t\t\tscale = {scale}")
    if transparent:
        lines.append("\t\t\talwaystransparent = yes")
    return "\n".join([*lines, "\t\t}"])


def textbox(name, text, x, y, width, height, font="hoi_16mbs", centered=False):
    lines = ["\t\tinstantTextBoxType = {", f'\t\t\tname = "{name}"',
             f"\t\t\tposition = {{ x = {x} y = {y} }}", f'\t\t\ttext = "{text}"',
             f'\t\t\tfont = "{font}"', f"\t\t\tmaxWidth = {width}", f"\t\t\tmaxHeight = {height}",
             "\t\t\tfixedsize = yes", "\t\t\talwaystransparent = yes"]
    if centered:
        lines.append("\t\t\tformat = center")
    return "\n".join([*lines, "\t\t}"])


def gui_block(geometry):
    parts = ['\n'.join(['\t# Generated by tools/builders/build_adiscord_vorkerland_capital_map.py.',
             '\tcontainerWindowType = {', '\t\tname = "ADISCORD_vorkerland_capital_window"',
             '\t\tposition = { x = 0 y = 0 }', '\t\tsize = { width = 460 height = 360 }',
             '\t\tclipping = no']), icon("WRK_capital_panel", "GFX_WRK_capital_panel", 0, 0, transparent=True),
             textbox("WRK_capital_title", "WRK_capital_title", 10, 8, 440, 26, "hoi_20b", True),
             icon("WRK_capital_map", "GFX_WRK_capital_map_background", 10, 48, transparent=True)]
    for state in STATES:
        parts.append(icon(f"WRK_capital_{state}_state", f"GFX_WRK_capital_state_{state}", 10, 48, transparent=True))
    parts.append(icon("WRK_capital_route", "GFX_WRK_capital_route", 10, 48, transparent=True))
    for state in STATES:
        x, y = geometry["markers"][state]
        parts.append(icon(f"WRK_capital_{state}_marker", "GFX_WRK_capital_marker", 10 + x - 14, 48 + y - 14))
    for number, y in enumerate((65, 155, 245), 1):
        parts.append(icon(f"WRK_capital_legend_icon_{number}", "GFX_WRK_capital_marker", 386, y, number + 2, transparent=True))
        parts.append(textbox(f"WRK_capital_legend_text_{number}", f"WRK_capital_legend_{number}",
                             350, y + 36, 100, 44, centered=True))
    parts.append('\n'.join(['\t}', '', '\tcontainerWindowType = {', '\t\tname = "ADISCORD_vorkerland_intrigue_window"',
                           '\t\tposition = { x = 0 y = 0 }', '\t\tsize = { width = 460 height = 360 }', '\t\tclipping = no']))
    for number in range(1, 7):
        x = 5 + ((number - 1) % 2) * 230
        y = 14 + ((number - 1) // 2) * 112
        prefix = f"WRK_intrigue_{number}"
        parts.extend([icon(prefix + "_card", "GFX_WRK_intrigue_card", x, y),
                      icon(prefix + "_portrait", "GFX_WRK_intrigue_portrait_empty", x + 11, y + 11, scale=0.28, transparent=True),
                      textbox(prefix + "_name", prefix + "_name", x + 66, y + 11, 130, 44),
                      textbox(prefix + "_status", prefix + "_status", x + 12, y + 76, 196, 20)])
    parts.append('\t}')
    return "\n\n".join(parts) + "\n"


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


def mockup_html(images, geometry):
    assets = {Path(name).stem: "data:image/png;base64," + base64.b64encode(png_bytes(image)).decode()
              for name, image in images.items()}
    data = json.dumps({"assets": assets, "markers": geometry["markers"], "anchors": geometry["anchors"],
                       "states": STATES, "labels": STATE_LABELS,
                       "stateFrames": DEMO_STATE_FRAMES, "markerFrames": DEMO_MARKER_FRAMES}, separators=(",", ":"))
    template = r'''<!doctype html>
<!-- Generated by tools/builders/build_adiscord_vorkerland_capital_map.py. -->
<html lang="ru"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>WRK | Политическая карта столицы</title>
<style>
:root{color-scheme:dark;--bg:#151b1f;--panel:#20272b;--line:#3e5057;--text:#dbe6e6;--muted:#9bafb6}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);font:14px system-ui,sans-serif}
main{max-width:1120px;margin:40px auto;padding:0 30px}h1{font-size:32px;letter-spacing:-1px;margin:12px 0}
h2{font-size:18px;font-weight:550;margin:0 0 18px}p{line-height:1.6;color:var(--muted)}
.eyebrow{font-size:11px;letter-spacing:3px;color:#a2dad5}.intro{max-width:740px;margin-bottom:30px}
.workbench{display:flex;gap:32px;align-items:flex-start;flex-wrap:wrap}.panel{position:relative;width:460px;height:360px;flex-shrink:0}
.sprite{position:absolute;background-repeat:no-repeat;pointer-events:none}.title{position:absolute;top:8px;left:10px;width:440px;text-align:center;font-size:20px;font-weight:650;line-height:26px}
.legend{position:absolute;left:350px;width:100px;text-align:center;font-size:14px;line-height:20px}
.card-name{position:absolute;width:130px;font-size:15px;line-height:19px}.card-status{position:absolute;width:196px;font-size:14px;line-height:20px}
.controls{width:460px;display:flex;gap:9px;flex-wrap:wrap;margin:16px 0 28px}button,select{border:1px solid var(--line);background:var(--panel);color:var(--text);padding:8px 10px;border-radius:3px;font:inherit;cursor:pointer}
button[aria-pressed=true]{border-color:#a2dad5}label{display:grid;gap:5px;color:var(--muted);font-size:12px}select{max-width:146px;font-size:12px}
.swatches{display:flex;gap:22px;flex-wrap:wrap;margin:28px 0}.swatch{display:flex;align-items:center;gap:9px}.swatch i{width:23px;height:3px;display:block}
.samples{padding:24px 0;border-top:1px solid var(--line)}.sample-row{display:flex;gap:16px;flex-wrap:wrap;margin:16px 0}.sample{width:134px;color:var(--muted);font-size:12px;line-height:1.5}.sample .tile{position:relative;height:40px}
.note{border-left:2px solid #a2dad5;padding-left:14px;font-size:13px;max-width:900px}.small{font-size:12px}footer{padding:24px 0 40px;border-top:1px solid var(--line);color:var(--muted);font-size:12px}
</style><main>
<div class="eyebrow">ВОРКЕРЛАНД / WRK / ДОВОЕННЫЙ ЭТАП</div>
<h1>Город под наблюдением</h1>
<p class="intro">Политическое влияние читается по улицам. Опасность - по красным знакам.
Геометрия девяти штатов столицы взята из карты мода, включая Старый Воркенсберг,
Нефтегазовый и Промышленный дистрикты; уличная сеть процедурная.
Окна ниже показаны в размере 1:1, 460x360. Это макет, не снимок из игры.</p>
<div class="workbench"><section><h2>Столица / карта влияния</h2><div id="capital" class="panel"></div>
<div class="controls" id="routes"></div><div class="controls" id="districts"></div></section>
<section><h2>Фигуры / отношение к штабу</h2><div id="intrigue" class="panel"></div>
<p class="small">Шесть мест для персонажей. Имена и силуэты демонстрационные.<br>Карточки: нейтрален, за штаб, против. Портреты назначает механика.</p></section></div>
<div class="swatches"><span class="swatch"><i style="background:#ebcb64"></i>Комитеты Уоркера</span>
<span class="swatch"><i style="background:#b39af2"></i>Штаб Петрищева</span>
<span class="swatch"><i style="background:#a9d66f"></i>Сеть Воркса</span>
<span class="swatch"><i style="background:#a2dad5"></i>Базовые улицы</span></div>
<section class="samples"><h2>Метки / порядок кадров</h2><div class="sample-row" id="markers"></div></section>
<section class="samples"><h2>Улицы / порядок кадров</h2><div class="sample-row" id="states"></div></section>
<p class="note">Гражданский путь: Башня (40), дистрикты 32 и 33, восточный край.
Военный путь: Башня (40), дистрикты 38, 37 и 36, северный край. Сплошная часть переходит в пунктир.
Булавка отмечает начало, дом - выход. Светлый силуэт со шпилем обозначает Башню Единства.</p>
<footer>Легенда в игре: WRK_capital_legend_1..3. Тексты здесь нужны только для согласования оформления.
GUI и спрайты готовы к подключению внешним scripted GUI; смена кадров в макете не реализует игровые механики.</footer>
</main><script>
const data=__DATA__;
function sprite(parent,name,w,h,x,y,frame=1,scale=1){const el=document.createElement('div');el.className='sprite';
Object.assign(el.style,{width:w+'px',height:h+'px',left:x+'px',top:y+'px',backgroundImage:`url("${data.assets[name]}")`,backgroundPosition:`-${(frame-1)*w}px 0`,transform:`scale(${scale})`,transformOrigin:'top left'});parent.append(el);return el}
function text(parent,cls,value,x,y){let el=document.createElement('div');el.className=cls;el.textContent=value;el.style.left=x+'px';el.style.top=y+'px';parent.append(el);return el}
const cap=document.getElementById('capital');sprite(cap,'WRK_capital_panel',460,360,0,0);
text(cap,'title','Политическая карта столицы',10,8);sprite(cap,'WRK_capital_map_background',330,290,10,48);
const stateIds=data.states,stateNames=['Без подсветки','Комитеты Уоркера','Штаб Петрищева','Сеть Воркса','Оспаривается','Бунт'];
const markerNames=['Пусто','Ячейка','Ячейка раскрыта','Волнения','Бунт','Патруль'];
const overlays={},markers={};stateIds.forEach(s=>overlays[s]=sprite(cap,'WRK_capital_state_'+s,330,290,10,48,data.stateFrames[s]));
const route=sprite(cap,'WRK_capital_route',330,290,10,48,2);
stateIds.forEach(s=>{const [x,y]=data.markers[s];markers[s]=sprite(cap,'WRK_capital_marker',28,28,x-4,y+34,data.markerFrames[s]);});
['Ячейка раскрыта','Волнения','Бунт'].forEach((s,i)=>{sprite(cap,'WRK_capital_marker',28,28,386,65+i*90,i+3);text(cap,'legend',s,350,101+i*90);});
['Без маршрута','Гражданский','Военный'].forEach((name,i)=>{let b=document.createElement('button');b.textContent=name;b.setAttribute('aria-pressed',i===1);b.onclick=()=>{route.style.backgroundPosition=`-${i*330}px 0`;document.querySelectorAll('#routes button').forEach(el=>el.setAttribute('aria-pressed',el===b));};document.getElementById('routes').append(b);});
stateIds.forEach(s=>{let l=document.createElement('div');l.style.width='146px';let name=document.createElement('div');name.textContent=s+' / '+data.labels[s];name.style.minHeight='38px';l.append(name);
for(const [names,frames,layer,width,label] of [[stateNames,data.stateFrames,overlays,330,'Влияние'],[markerNames,data.markerFrames,markers,28,'Метка']]){let select=document.createElement('select');select.setAttribute('aria-label',label+': '+data.labels[s]);select.style.width='146px';names.forEach((n,j)=>{let o=document.createElement('option');o.textContent=n;o.value=j;o.selected=j===frames[s]-1;select.append(o);});select.onchange=()=>layer[s].style.backgroundPosition=`-${select.value*width}px 0`;l.append(select);}document.getElementById('districts').append(l);});
const intrigue=document.getElementById('intrigue');for(let i=0;i<6;i++){let x=5+(i%2)*230,y=14+Math.floor(i/2)*112;
sprite(intrigue,'WRK_intrigue_card',220,100,x,y,i%3+1);sprite(intrigue,'WRK_intrigue_portrait_empty',156,210,x+11,y+11,1,.28);
text(intrigue,'card-name','Фигура '+String(i+1).padStart(2,'0'),x+66,y+11);text(intrigue,'card-status',['Нейтрален','За штаб','Против'][i%3],x+12,y+76);}
markerNames.forEach((name,i)=>{let s=document.createElement('div');s.className='sample';let tile=document.createElement('div');tile.className='tile';s.append(tile);sprite(tile,'WRK_capital_marker',28,28,0,0,i+1);s.append(document.createTextNode((i+1)+' / '+name));document.getElementById('markers').append(s);});
stateNames.forEach((name,i)=>{let s=document.createElement('div');s.className='sample';let tile=document.createElement('div');tile.className='tile';tile.style.height='110px';tile.style.overflow='hidden';
sprite(tile,'WRK_capital_map_background',330,290,-190,-160);sprite(tile,'WRK_capital_state_33',330,290,-190,-160,i+1);s.append(tile,document.createTextNode((i+1)+' / '+name));document.getElementById('states').append(s);});
</script></html>
'''
    return template.replace("__DATA__", data).encode("utf-8")


def review_image(images, geometry):
    sheet = Image.new("RGBA", (960, 810), (21, 27, 31, 255))
    draw = ImageDraw.Draw(sheet)
    draw.text((20, 10), "WRK CAPITAL / CIVILIAN + MILITARY ROUTES / 1:1", fill=WHITE)
    for route, origin in ((1, (10, 40)), (2, (490, 40))):
        panel = images["WRK_capital_panel.png"].copy()
        panel.alpha_composite(images["WRK_capital_map_background.png"], (10, 48))
        for state in STATES:
            frame = DEMO_STATE_FRAMES[state] - 1
            panel.alpha_composite(images[f"WRK_capital_state_{state}.png"].crop((frame * WIDTH, 0, (frame + 1) * WIDTH, HEIGHT)), (10, 48))
        panel.alpha_composite(images["WRK_capital_route.png"].crop((route * WIDTH, 0, (route + 1) * WIDTH, HEIGHT)), (10, 48))
        for state in STATES:
            frame = DEMO_MARKER_FRAMES[state] - 1
            x, y = geometry["markers"][state]
            panel.alpha_composite(images["WRK_capital_marker.png"].crop((frame * 28, 0, (frame + 1) * 28, 28)), (x - 4, y + 34))
        pd = ImageDraw.Draw(panel)
        pd.text((14, 14), "CAPITAL / " + ("CIVILIAN" if route == 1 else "MILITARY"), fill=WHITE)
        for n, label in enumerate(("Exposed", "Unrest", "Revolt")):
            panel.alpha_composite(images["WRK_capital_marker.png"].crop(((n + 2) * 28, 0, (n + 3) * 28, 28)), (386, 65 + n * 90))
            pd.text((365, 104 + n * 90), label, fill=WHITE)
        sheet.alpha_composite(panel, origin)
    for n in range(6):
        x, y = 15 + n % 2 * 230, 430 + n // 2 * 112
        frame = n % 3
        sheet.alpha_composite(images["WRK_intrigue_card.png"].crop((frame * 220, 0, (frame + 1) * 220, 100)), (x, y))
        portrait = images["WRK_intrigue_portrait_empty.png"].resize((44, 59), Image.Resampling.LANCZOS)
        sheet.alpha_composite(portrait, (x + 11, y + 11))
        draw.text((x + 66, y + 12), f"FIGURE {n + 1:02}", fill=WHITE)
        draw.text((x + 12, y + 78), ("Neutral", "For staff", "Against")[frame], fill=WHITE)
    draw.text((500, 430), "MARKER FRAMES / 1 EMPTY", fill=WHITE)
    sheet.alpha_composite(images["WRK_capital_marker.png"], (500, 460))
    draw.text((500, 520), "STATE FRAMES / 1 EMPTY", fill=WHITE)
    for n in range(6):
        patch = images["WRK_capital_map_background.png"].crop((225, 170, 285, 240))
        patch.alpha_composite(images["WRK_capital_state_33.png"].crop((n * WIDTH + 225, 170, n * WIDTH + 285, 240)))
        sheet.alpha_composite(patch, (500 + n * 70, 550))
        draw.text((500 + n * 70, 628), str(n + 1), fill=WHITE)
    return sheet


def build_outputs(include_preview=False):
    images, geometry = render_images()
    outputs = {OUT / name: png_bytes(image) for name, image in images.items()}
    outputs[GUI] = replace_section((ROOT / GUI).read_bytes(), gui_block(geometry))
    outputs[GFX] = replace_section((ROOT / GFX).read_bytes(), gfx_block(images))
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
