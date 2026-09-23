"""Build the shared Kefreyt and postwar Stelander operations map."""

from __future__ import annotations

import argparse
import csv
import re
import math
from collections import deque
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter
from tools.lib.paths import repository_root


ROOT = repository_root()
OUT = ROOT / "gfx" / "interface" / "VAL_operations"
WIDTH, HEIGHT = 420, 340
STATE_IDS = (43, 44, 45, 88, 58, 59, 60, 61, 62, 63, 64, 65)
VAL_STATES = (24, 42, 48, 54, 55, 56, 57)
STP_STATES = (1, 2, 3, 28, 29, 43, 44, 45, 46, 53, 88)
NOD_STATES = (10, 11, 12, 13, 17, 18, 30)
BJK_STATES = (4, 5, 6, 7, 9, 31, 41)
COF_STATES = (14,)
YPR_STATES = (8, 15, 16, 19, 20, 21, 22)
TFF_STATES = (83, 84, 85, 86, 87, 303)
AINHOLM_TRANSFER_STATES = (118, 119)
# Keep only states selected by VAL's southern and eastern state-focus war goals.
SOUTHERN_STATES = (168, 169, 167, 170, 171, 184, 185, 203,
                   178, 180, 181, 182, 183, 193, 206, 207)
STATE_IDS = tuple(dict.fromkeys((*STATE_IDS, *VAL_STATES, *STP_STATES, *NOD_STATES,
                               *BJK_STATES, *COF_STATES, *YPR_STATES, *TFF_STATES,
                               *AINHOLM_TRANSFER_STATES, *SOUTHERN_STATES)))

# Countries participating in the northern and Stelander campaigns; the last frame
# represents a controller from outside this theatre.
MAP_TAGS = ("VAL", "STP", "STS", "SRP", "NOD", "CIN", "OSF", "APH", "ERT", "NKA", "OCA", "YPR", "COF", "TFF", "EXZ", "IRT", "BJK", "BLD", "BHG", "BGT", "BBV", "BCM", "WCA")
FRAME_COUNT = len(MAP_TAGS) + 1


def country_colors() -> list[tuple[int, int, int]]:
    registry = "\n".join(p.read_text(encoding="utf-8-sig") for p in sorted((ROOT / "common/country_tags").glob("*.txt")))
    result = []
    for tag in MAP_TAGS:
        relative = re.search(rf'(?m)^\s*{tag}\s*=\s*"([^"]+)"', registry).group(1)
        source = (ROOT / "common" / relative).read_text(encoding="utf-8-sig")
        color = re.search(r"\bcolor\s*=\s*(?:rgb\s*)?\{\s*(\d+)\s+(\d+)\s+(\d+)\s*\}", source)
        if color is None:
            raise ValueError(f"No RGB map color for {tag}")
        result.append(tuple(map(int, color.groups())))
    return [*result, (103, 103, 107)]


def state_provinces(state_id: int) -> set[int]:
    candidates = sorted((ROOT / "history" / "states").glob(f"{state_id}-*.txt"))
    if not candidates:
        raise FileNotFoundError(f"state {state_id}")
    text = candidates[0].read_text(encoding="utf-8-sig", errors="replace")
    match = re.search(r"provinces\s*=\s*\{([^}]*)\}", text, re.S)
    if not match:
        raise ValueError(f"no provinces block in {candidates[0]}")
    return {int(value) for value in re.findall(r"\d+", match.group(1))}


def province_colors() -> tuple[dict[int, tuple[int, int, int]], set[tuple[int, int, int]]]:
    colors: dict[int, tuple[int, int, int]] = {}
    land: set[tuple[int, int, int]] = set()
    with (ROOT / "map" / "definition.csv").open(encoding="utf-8-sig", errors="replace") as source:
        for row in csv.reader(source, delimiter=";"):
            if len(row) < 5 or not row[0].isdigit():
                continue
            province = int(row[0])
            color = tuple(map(int, row[1:4]))
            colors[province] = color
            if row[4] == "land":
                land.add(color)
    return colors, land


def transform(mask: Image.Image, box: tuple[int, int, int, int]) -> Image.Image:
    cropped = mask.crop(box)
    scale = min(WIDTH / cropped.width, HEIGHT / cropped.height)
    size = (max(1, round(cropped.width * scale)), max(1, round(cropped.height * scale)))
    resized = cropped.resize(size, Image.Resampling.NEAREST)
    canvas = Image.new("L", (WIDTH, HEIGHT), 0)
    canvas.paste(resized, ((WIDTH - size[0]) // 2, (HEIGHT - size[1]) // 2))
    return canvas


def render_outputs() -> tuple[dict[str, Image.Image], tuple[int, int, int, int], tuple[int, int], tuple[int, int]]:
    province_to_color, land_colors = province_colors()
    state_sets = {
        state: state_provinces(state)
        for state in STATE_IDS
    }
    color_to_state = {
        province_to_color[province]: state
        for state, provinces in state_sets.items()
        for province in provinces
        if province in province_to_color
    }

    provinces = Image.open(ROOT / "map" / "provinces.bmp").convert("RGB")
    focus_colors = set(color_to_state)
    min_x, min_y = provinces.width, provinces.height
    max_x = max_y = -1
    pixels = provinces.load()
    for y in range(provinces.height):
        for x in range(provinces.width):
            if pixels[x, y] in focus_colors:
                min_x = min(min_x, x)
                min_y = min(min_y, y)
                max_x = max(max_x, x)
                max_y = max(max_y, y)
    if max_x < 0:
        raise RuntimeError("target states were not found in provinces.bmp")
    pad = 24
    box = (
        max(0, min_x - pad),
        max(0, min_y - pad),
        min(provinces.width, max_x + pad + 1),
        min(provinces.height, max_y + pad + 1),
    )

    cropped = provinces.crop(box)
    state_masks: dict[int, Image.Image] = {}
    for state in state_sets:
        colors = {province_to_color[p] for p in state_sets[state] if p in province_to_color}
        raw = Image.new("L", cropped.size, 0)
        raw.putdata([255 if pixel in colors else 0 for pixel in cropped.getdata()])
        state_masks[state] = transform(raw, (0, 0, cropped.width, cropped.height))

    scale = min(WIDTH / cropped.width, HEIGHT / cropped.height)
    size = (max(1, round(cropped.width * scale)), max(1, round(cropped.height * scale)))
    offset = ((WIDTH - size[0]) // 2, (HEIGHT - size[1]) // 2)
    land_raw = Image.new("L", cropped.size, 0)
    land_raw.putdata([255 if pixel in land_colors else 0 for pixel in cropped.getdata()])
    land_mask = transform(land_raw, (0, 0, cropped.width, cropped.height))

    background = Image.new("RGBA", (WIDTH, HEIGHT), (12, 13, 15, 255))
    terrain = Image.new("RGBA", (WIDTH, HEIGHT), (48, 49, 48, 255))
    background.alpha_composite(Image.composite(terrain, Image.new("RGBA", background.size), land_mask))
    draw = ImageDraw.Draw(background)
    for y in range(0, HEIGHT, 32):
        draw.line((0, y, WIDTH, y), fill=(34, 37, 38, 255), width=1)
    for x in range(0, WIDTH, 32):
        draw.line((x, 0, x, HEIGHT), fill=(34, 37, 38, 255), width=1)

    all_mask = Image.new("L", background.size, 0)
    for mask in state_masks.values():
        all_mask = ImageChops.lighter(all_mask, mask)
    outer = all_mask.filter(ImageFilter.MaxFilter(5))
    border = Image.eval(outer, lambda p: p)
    border = Image.frombytes("L", border.size, bytes(max(a - b, 0) for a, b in zip(border.getdata(), all_mask.getdata())))
    background.alpha_composite(Image.composite(Image.new("RGBA", background.size, (190, 178, 145, 150)), Image.new("RGBA", background.size), border))

    vignette = Image.new("RGBA", background.size, (0, 0, 0, 0))
    vd = ImageDraw.Draw(vignette)
    for i in range(18):
        vd.rectangle((i, i, WIDTH - i - 1, HEIGHT - i - 1), outline=(0, 0, 0, max(0, 9 - i // 2)))
    background.alpha_composite(vignette)
    outputs = {"VAL_ops_map_background.png": background}

    palette = country_colors()
    for state in STATE_IDS:
        frames = Image.new("RGBA", (WIDTH * FRAME_COUNT, HEIGHT), (0, 0, 0, 0))
        mask = state_masks[state]
        expanded = mask.filter(ImageFilter.MaxFilter(3))
        rim = Image.frombytes("L", mask.size, bytes(max(a - b, 0) for a, b in zip(expanded.getdata(), mask.getdata())))
        for index, color in enumerate(palette):
            frame = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
            frame.alpha_composite(Image.composite(Image.new("RGBA", frame.size, (*color, 255)), Image.new("RGBA", frame.size), mask))
            frames.paste(frame, (WIDTH * index, 0))
        outputs[f"VAL_ops_state_{state}.png"] = frames
        # The same colour atlas serves both countries; borders follow the viewer.
        outputs[f"VAL_ops_border_{state}.png"] = Image.composite(
            Image.new("RGBA", (WIDTH, HEIGHT), (235, 215, 160, 235)),
            Image.new("RGBA", (WIDTH, HEIGHT)), rim,
        )
        # Mark divided control independently of the state's majority controller.
        stripes = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
        stripe_draw = ImageDraw.Draw(stripes)
        for x in range(-HEIGHT, WIDTH, 8):
            stripe_draw.line((x, 0, x + HEIGHT, HEIGHT), fill=(255, 205, 90, 210), width=2)
        outputs[f"VAL_ops_contested_{state}.png"] = Image.composite(stripes, Image.new("RGBA", stripes.size), mask)


    return outputs, box, size, offset


def validate_outputs(outputs: dict[str, Image.Image]) -> list[str]:
    issues: list[str] = []
    expected_filenames = set(outputs)
    for path in sorted(OUT.glob("VAL_ops_*.png")):
        if path.is_file() and path.name not in expected_filenames:
            issues.append(f"unexpected generated operations-map image: {path.name}")
    for filename, expected in outputs.items():
        path = OUT / filename
        if not path.is_file():
            issues.append(f"missing generated operations-map image: {path.relative_to(ROOT)}")
            continue
        try:
            with Image.open(path) as source:
                actual = source.convert("RGBA")
        except OSError as exc:
            issues.append(f"cannot read {path.relative_to(ROOT)}: {exc}")
            continue
        if actual.size != expected.size:
            issues.append(
                f"{path.relative_to(ROOT)} has size {actual.size}, expected {expected.size}"
            )
            continue
        if any(channel.getbbox() is not None for channel in ImageChops.difference(actual, expected.convert("RGBA")).split()):
            issues.append(f"{path.relative_to(ROOT)} pixels differ from deterministic render")
    return issues


def apply(outputs: dict[str, Image.Image]) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    expected_filenames = set(outputs)
    for path in sorted(OUT.glob("VAL_ops_*.png")):
        if path.is_file() and path.name not in expected_filenames:
            path.unlink()
    for filename, image in outputs.items():
        image.save(OUT / filename, optimize=True)


def compact_overlays(outputs: dict[str, Image.Image]) -> tuple[dict[str, Image.Image], dict[int, tuple[int, int, int, int]]]:
    # Store only the region's occupied rectangle, not fifteen full-map canvases.
    compact = {"VAL_ops_map_background.png": outputs["VAL_ops_map_background.png"]}
    boxes = {}
    for state in STATE_IDS:
        source = outputs[f"VAL_ops_state_{state}.png"]
        box = ImageChops.lighter(source.crop((0, 0, WIDTH, HEIGHT)).getchannel("A"),
                                 outputs[f"VAL_ops_border_{state}.png"].getchannel("A")).getbbox()
        if box is None:
            raise ValueError(f"Empty map region {state}")
        boxes[state] = box
        left, top, right, bottom = box
        width, height = right - left, bottom - top
        strip = Image.new("RGBA", (width * FRAME_COUNT, height))
        for frame in range(FRAME_COUNT):
            strip.paste(source.crop((left + frame * WIDTH, top, right + frame * WIDTH, bottom)), (frame * width, 0))
        compact[f"VAL_ops_state_{state}.png"] = strip
        compact[f"VAL_ops_contested_{state}.png"] = outputs[f"VAL_ops_contested_{state}.png"].crop(box)
        compact[f"VAL_ops_border_{state}.png"] = outputs[f"VAL_ops_border_{state}.png"].crop(box)
    return compact, boxes


def trade_route_states() -> dict[str, tuple[int, ...]]:
    """Read the authored corridor nodes from their authoritative predicates."""
    text = (ROOT / "common/scripted_triggers/ADISCORD_VAL_logistics_market_triggers.txt").read_text(encoding="utf-8")
    result = {}
    for route in ("occidia", "west", "stelander", "vorkerland", "south", "north"):
        if route == "north":
            result[route] = ()
            continue
        start = text.index(f"VAL_trade_route_{route}_open = {{")
        end = text.index("\n}", start)
        result[route] = tuple(int(n) for n in re.findall(r"(?m)^\s+(\d+) = \{", text[start:end]))
        if not result[route]:
            raise ValueError(f"No corridor nodes: {route}")
    return result


def operations_controller_branches() -> list[tuple[tuple[str, ...], int]]:
    branches = [
        (("OR = {", "\ttag = STP", "\thas_cosmetic_tag = STL_VAL_administration", "}"), MAP_TAGS.index("STP") + 1),
        (("OR = {", "\ttag = BJK", "\tis_subject_of = BJK", "}"), MAP_TAGS.index("BJK") + 1),
    ]
    branches.extend(((f"tag = {tag}",), frame)
                    for frame, tag in enumerate(MAP_TAGS, 1)
                    if tag not in ("STP", "BJK"))
    return branches


def operations_map_effects() -> str:
    lines = ["# Generated by tools/builders/build_adiscord_val_operations_map.py; do not edit.\n"]
    lines.extend((
        "VAL_unlock_operations_map = {\n",
        "\tset_country_flag = VAL_operations_map_unlocked\n",
        "\tVAL_operations_map_refresh_cache = yes\n",
        "\tVAL_trade_routes_map_refresh_cache = yes\n",
        "}\n\n",
    ))
    lines.append("VAL_operations_map_refresh_cache = {\n")
    for state in STATE_IDS:
        variable = f"operations_state_{state}_frame"
        lines.append(f"\tset_variable = {{ var = {variable} value = {FRAME_COUNT} }}\n")
        for index, (condition_lines, frame) in enumerate(operations_controller_branches()):
            branch = "if" if index == 0 else "else_if"
            lines.append(f"\t{branch} = {{\n")
            lines.append("\t\tlimit = {\n")
            lines.append(f"\t\t\t{state} = {{\n")
            lines.append("\t\t\t\tcontroller = {\n")
            lines.extend(f"\t\t\t\t\t{condition_line}\n" for condition_line in condition_lines)
            lines.append("\t\t\t\t}\n")
            lines.append("\t\t\t}\n")
            lines.append("\t\t}\n")
            lines.append(f"\t\tset_variable = {{ var = {variable} value = {frame} }}\n")
            lines.append("\t}\n")
    lines.append("}\n\n")

    lines.append("VAL_trade_routes_map_refresh_cache = {\n")
    pressure = "check_variable = { var = VAL_black_market_pressure value = 50 compare = greater_than_or_equals }"
    insecurity = "check_variable = { var = VAL_corridor_security value = 3 compare = less_than }"
    for route in trade_route_states():
        variable = f"trade_{route}_map_frame"
        status_conditions = (
            (f"NOT = {{ VAL_trade_route_{route}_open = yes }}",
             f"NOT = {{ has_country_flag = VAL_route_{route}_commissioned }}"),
            (f"VAL_trade_route_{route}_open = yes",
             "NOT = {",
             "\tAND = {",
             f"\t\t{pressure}",
             f"\t\t{insecurity}",
             "\t}",
             "}"),
            (f"VAL_trade_route_{route}_open = yes", pressure, insecurity),
            (f"NOT = {{ VAL_trade_route_{route}_open = yes }}",
             f"has_country_flag = VAL_route_{route}_commissioned"),
        )
        lines.append(f"\tset_variable = {{ var = {variable} value = 1 }}\n")
        for index, condition_lines in enumerate(status_conditions):
            branch = "if" if index == 0 else "else_if"
            lines.append(f"\t{branch} = {{\n")
            lines.append("\t\tlimit = {\n")
            lines.extend(f"\t\t\t{condition_line}\n" for condition_line in condition_lines)
            lines.append("\t\t}\n")
            lines.append(f"\t\tset_variable = {{ var = {variable} value = {index + 1} }}\n")
            lines.append("\t}\n")
    lines.append("}\n")
    return "".join(lines)


def read_rail_graph() -> dict[int, set[int]]:
    graph: dict[int, set[int]] = {}
    for line in (ROOT / "map/railways.txt").read_text(encoding="utf-8-sig").splitlines():
        values = [int(n) for n in line.split("#", 1)[0].split()]
        if not values:
            continue
        if len(values) < 3 or len(values[2:]) != values[1]:
            raise ValueError(f"Malformed railway: {line}")
        for a, b in zip(values[2:], values[3:]):
            graph.setdefault(a, set()).add(b)
            graph.setdefault(b, set()).add(a)
    return graph


def rail_path(graph: dict[int, set[int]], start: int, end: int) -> list[int] | None:
    queue = deque([start])
    previous = {start: None}
    while queue:
        current = queue.popleft()
        if current == end:
            path = [current]
            while previous[current] is not None:
                current = previous[current]
                path.append(current)
            return list(reversed(path))
        for neighbour in sorted(graph.get(current, ())):
            if neighbour not in previous:
                previous[neighbour] = current
                queue.append(neighbour)
    return None


def render_trade_routes() -> dict[str, Image.Image]:
    """Project native rail chains; disconnected links remain dashed trade roads."""
    import numpy as np

    routes = trade_route_states()
    colors, land = province_colors()
    graph = read_rail_graph()
    provinces = Image.open(ROOT / "map/provinces.bmp").convert("RGB")
    pixels = np.asarray(provinces, dtype=np.uint32)
    codes = (pixels[:, :, 0] << 16) | (pixels[:, :, 1] << 8) | pixels[:, :, 2]
    unique, inverse = np.unique(codes.ravel(), return_inverse=True)
    counts = np.bincount(inverse)
    yy, xx = np.indices(codes.shape)
    xs = np.bincount(inverse, weights=xx.ravel()) / counts
    ys = np.bincount(inverse, weights=yy.ravel()) / counts
    centers = {int(code): (float(x), float(y)) for code, x, y in zip(unique, xs, ys)}
    def center(p):
        r, g, b = colors[p]
        return centers[(r << 16) | (g << 8) | b]
    def node(state):
        candidates = sorted(state_provinces(state))
        rails = [p for p in candidates if p in graph]
        points = [center(p) for p in candidates]
        cx = sum(p[0] for p in points) / len(points)
        cy = sum(p[1] for p in points) / len(points)
        return min(rails or candidates, key=lambda p: ((center(p)[0]-cx)**2 + (center(p)[1]-cy)**2, p))
    origin = node(24)
    chains = {}
    all_points = [center(origin)]
    for route, states in routes.items():
        if route == "north":
            # Standing external route: keep it out of the land-corridor crop.
            chains[route] = None
            continue
        anchors = [origin, *(node(state) for state in states)]
        segments = []
        for a, b in zip(anchors, anchors[1:]):
            path = rail_path(graph, a, b)
            points = [center(p) for p in (path or [a, b])]
            segments.append((points, path is not None))
            all_points.extend(points)
        chains[route] = segments
    left = max(0, int(min(p[0] for p in all_points))-80)
    top = max(0, int(min(p[1] for p in all_points))-80)
    right = min(provinces.width, int(max(p[0] for p in all_points))+80)
    bottom = min(provinces.height, int(max(p[1] for p in all_points))+80)
    crop = provinces.crop((left, top, right, bottom))
    scale = min(WIDTH / crop.width, HEIGHT / crop.height)
    size = (max(1, round(crop.width*scale)), max(1, round(crop.height*scale)))
    offset = ((WIDTH-size[0])//2, (HEIGHT-size[1])//2)
    background = Image.new("RGBA", (WIDTH, HEIGHT), (17, 25, 29, 255))
    shaded = Image.new("RGBA", crop.size)
    shaded.putdata([(49, 58, 57, 255) if p in land else (17, 25, 29, 255) for p in crop.getdata()])
    background.paste(shaded.resize(size, Image.Resampling.LANCZOS), offset)
    ImageDraw.Draw(background).rectangle((0, 0, WIDTH-1, HEIGHT-1), outline=(125, 114, 87), width=1)
    output = {"VAL_trade_map.png": background}
    def project(p):
        return (offset[0]+(p[0]-left)*scale, offset[1]+(p[1]-top)*scale)
    palette = ((130, 139, 144, 255), (115, 196, 127, 255), (240, 192, 69, 255), (230, 93, 79, 255))
    for route_index, (route, segments) in enumerate(chains.items(), 1):
        strip = Image.new("RGBA", (WIDTH*4, HEIGHT))
        if route == "north":
            glyph_6 = ("111", "100", "111", "101", "111")
            for frame, color in enumerate(palette):
                layer = Image.new("RGBA", (WIDTH, HEIGHT))
                draw = ImageDraw.Draw(layer)
                if frame == 0:
                    for y in range(30, 92, 8):
                        draw.rectangle((301, y, 302, min(y + 3, 91)), fill=color)
                elif frame == 3:
                    draw.rectangle((301, 30, 302, 54), fill=color)
                    draw.rectangle((301, 62, 302, 91), fill=color)
                    draw.line((297, 55, 306, 64), fill=color, width=1)
                    draw.line((306, 55, 297, 64), fill=color, width=1)
                else:
                    draw.rectangle((301, 30, 302, 91), fill=color)
                draw.rectangle((297, 21, 306, 29), fill=(17, 25, 29, 255), outline=color, width=1)
                draw.rectangle((300, 18, 303, 20), fill=color)
                for gy, row in enumerate(glyph_6):
                    for gx, bit in enumerate(row):
                        if bit == "1":
                            draw.point((300 + gx, 23 + gy), fill=color)
                strip.paste(layer, (frame * WIDTH, 0))
            output["VAL_trade_route_north.png"] = strip
            continue
        for frame, color in enumerate(palette):
            layer = Image.new("RGBA", (WIDTH, HEIGHT))
            draw = ImageDraw.Draw(layer)
            for points, is_rail in segments:
                points = [project(p) for p in points]
                for a, b in zip(points, points[1:]):
                    dx, dy = b[0]-a[0], b[1]-a[1]
                    length = math.hypot(dx, dy)
                    if length < 0.1:
                        continue
                    nx, ny = -dy/length*3, dx/length*3
                    if frame != 0 and is_rail:
                        draw.line((a,b), fill=(9, 14, 16, 255), width=5)
                        draw.line((a,b), fill=color, width=2)
                    for distance in range(0, max(1, int(length)), 7):
                        x,y = a[0]+dx*distance/length, a[1]+dy*distance/length
                        if frame == 0 or not is_rail:
                            t = min(length, distance+4)/length
                            draw.line(((x,y),(a[0]+dx*t,a[1]+dy*t)), fill=color, width=2)
                        else:
                            draw.line(((x-nx,y-ny),(x+nx,y+ny)), fill=color, width=1)
                x,y = points[-1]
                draw.ellipse((x-4,y-4,x+4,y+4), fill=(17,25,29,255), outline=color, width=2)
                if frame == 3:
                    draw.line((x-3,y-3,x+3,y+3), fill=color, width=2)
                if frame == 2:
                    draw.text((x+5,y-8), "!", fill=color)
            # Match endpoint numbers to the native translated route rows.
            x, y = project(segments[-1][0][-1])
            ox, oy = {"occidia": (-16, -19), "west": (6, -18),
                      "stelander": (-18, 5), "vorkerland": (7, -5), "south": (7, 5)}[route]
            draw.rectangle((x+ox-2, y+oy-1, x+ox+9, y+oy+13), fill=(17, 25, 29, 255), outline=color)
            draw.text((x+ox, y+oy), str(route_index), fill=color)
            strip.paste(layer,(frame*WIDTH,0))
        output[f"VAL_trade_route_{route}.png"] = strip
    return output


def interface_outputs(boxes: dict[int, tuple[int, int, int, int]]) -> dict[str, str]:
    header = "# Generated by tools/builders/build_adiscord_val_operations_map.py; do not edit.\n"
    gui = [header, "guiTypes = {\n"]
    gfx = [header, 'spriteTypes = {\n spriteType = { name = "GFX_VAL_ops_map_background" texturefile = "gfx/interface/VAL_operations/VAL_ops_map_background.png" }\n']
    script = [header, "scripted_gui = {\n"]
    for state in STATE_IDS:
        gfx.append(f' spriteType = {{ name = "GFX_VAL_ops_state_{state}" texturefile = "gfx/interface/VAL_operations/VAL_ops_state_{state}.png" noOfFrames = {FRAME_COUNT} transparencecheck = yes }}\n')
        for layer in ("border", "contested"):
            gfx.append(f' spriteType = {{ name = "GFX_VAL_ops_{layer}_{state}" texturefile = "gfx/interface/VAL_operations/VAL_ops_{layer}_{state}.png" }}\n')
    for prefix, viewer in (("VAL", "VAL"), ("STP", "STS")):
        gui.append(f' containerWindowType = {{\n  name = "ADISCORD_{prefix}_operations_panel_window"\n  position = {{ x = 0 y = 0 }}\n  size = {{ width = 460 height = 398 }}\n  clipping = no\n')
        gui.append(f'  iconType = {{ name = "{prefix}_operations_map" position = {{ x = 20 y = 38 }} quadTextureSprite = "GFX_VAL_ops_map_background" pdx_tooltip = "{prefix}_operations_map_tt" }}\n')
        script.append(f' ADISCORD_{prefix}_operations_panel = {{\n  context_type = decision_category\n  window_name = "ADISCORD_{prefix}_operations_panel_window"\n  visible = {{ always = yes }}\n  triggers = {{\n')
        for state in STATE_IDS:
            left, top, _, _ = boxes[state]
            name = f"{prefix}_ops_{state}_controller"
            frame_variable = f"operations_state_{state}_frame"
            # Controller colors are cached in country variables outside the GUI trigger path.
            gui.append(f'  iconType = {{ name = "{name}" position = {{ x = {20 + left} y = {38 + top} }} quadTextureSprite = "GFX_VAL_ops_state_{state}" }}\n')
            script.append(f'   {name}_visible = {{ always = yes }}\n')
        # Draw borders after all fills so adjacent regions cannot cover their rims.
        for state in STATE_IDS:
            left, top, _, _ = boxes[state]
            for layer in ("border", "contested"):
                gui.append(f'  iconType = {{ name = "{prefix}_ops_{state}_{layer}" position = {{ x = {20 + left} y = {38 + top} }} quadTextureSprite = "GFX_VAL_ops_{layer}_{state}" }}\n')
            script.append(f'   {prefix}_ops_{state}_border_visible = {{ {state} = {{ controller = {{ tag = {viewer} }} }} }}\n')
            provinces = " ".join(f"NOT = {{ controls_province = {p} }}" for p in sorted(state_provinces(state)))
            script.append(f'   {prefix}_ops_{state}_contested_visible = {{ {state} = {{ controller = {{ tag = {viewer} OR = {{ {provinces} }} }} }} }}\n')
        gui.append(" }\n")
        script.append("  }\n  properties = {\n")
        for state in STATE_IDS:
            name = f"{prefix}_ops_{state}_controller"
            frame_variable = f"operations_state_{state}_frame"
            script.append(f'   {name} = {{ frame = {frame_variable} }}\n')
        script.append("  }\n }\n")
    gui.append(' containerWindowType = { name = "ADISCORD_VAL_trade_routes_window" position = { x = 0 y = 0 } size = { width = 460 height = 570 }\n')
    gui.append('  iconType = { name = "trade_map" position = { x = 20 y = 8 } quadTextureSprite = "GFX_VAL_trade_map" pdx_tooltip = "VAL_trade_map_tt" }\n')
    gfx.append(' spriteType = { name = "GFX_VAL_trade_map" texturefile = "gfx/interface/VAL_operations/VAL_trade_map.png" }\n')
    script.append(' ADISCORD_VAL_trade_routes_panel = { context_type = decision_category window_name = "ADISCORD_VAL_trade_routes_window" visible = { always = yes } triggers = {\n')
    risk = 'check_variable = { var = VAL_black_market_pressure value = 50 compare = greater_than_or_equals } check_variable = { var = VAL_corridor_security value = 3 compare = less_than }'
    for row, route in enumerate(trade_route_states()):
        gfx.append(f' spriteType = {{ name = "GFX_VAL_trade_route_{route}" texturefile = "gfx/interface/VAL_operations/VAL_trade_route_{route}.png" noOfFrames = 4 }}\n')
        conditions = (
            f'NOT = {{ VAL_trade_route_{route}_open = yes }} NOT = {{ has_country_flag = VAL_route_{route}_commissioned }}',
            f'VAL_trade_route_{route}_open = yes NOT = {{ AND = {{ {risk} }} }}',
            f'VAL_trade_route_{route}_open = yes {risk}',
            f'NOT = {{ VAL_trade_route_{route}_open = yes }} has_country_flag = VAL_route_{route}_commissioned',
        )
        route_gate = (
            "always = yes"
            if route == "north"
            else (
            "OR = { VAL_trade_corridors_unlocked = yes "
            "has_completed_focus = VAL_Southern_Trade_Charter "
            "has_country_flag = ADISCORD_debug_val_south_route_active }"
            if route == "south"
            else "VAL_trade_corridors_unlocked = yes"
            )
        )
        icon_name = f"trade_{route}_map"
        frame_variable = f"{icon_name}_frame"
        gui.append(f'  iconType = {{ name = "{icon_name}" position = {{ x = 20 y = 8 }} quadTextureSprite = "GFX_VAL_trade_route_{route}" }}\n')
        script.append(f'  {icon_name}_visible = {{ {route_gate} }}\n')
        for frame, condition in enumerate(conditions, 1):
            name = f'trade_{route}_{frame}'
            # A separate status row gives each overlapping route its own hit area.
            gui.append(f'  instantTextBoxType = {{ name = "{name}_label" position = {{ x = 20 y = {354+row*25} }} font = "hoi_16mbs" text = "VAL_trade_{route}_{frame}" maxWidth = 420 maxHeight = 24 pdx_tooltip = "VAL_trade_{route}_tt" }}\n')
            script.append(f'  {name}_label_visible = {{ {route_gate} {condition} }}\n')
    gui.append('  instantTextBoxType = { name = "legend" position = { x = 20 y = 515 } font = "hoi_16mbs" text = "VAL_trade_map_legend" maxWidth = 420 maxHeight = 48 }\n }\n}\n')
    gfx.append('}\n')
    script.append(' }\n  properties = {\n')
    for route in trade_route_states():
        icon_name = f"trade_{route}_map"
        script.append(f'   {icon_name} = {{ frame = {icon_name}_frame }}\n')
    script.append('  }\n }\n}\n')
    return {
        "interface/ADISCORD_VAL_operations.gui": "".join(gui),
        "interface/ADISCORD_VAL_operations.gfx": "".join(gfx),
        "common/scripted_guis/ADISCORD_VAL_operations_scripted_gui.txt": "".join(script),
        "common/scripted_effects/ADISCORD_VAL_operations_map_effects.txt": operations_map_effects(),
    }



def main() -> int:
    parser = argparse.ArgumentParser(description="Generate Kefreyt's local operations map.")
    actions = parser.add_mutually_exclusive_group()
    actions.add_argument("--check", action="store_true", help="compare current PNGs with a deterministic render (default)")
    actions.add_argument("--apply", action="store_true", help="write the deterministic operations-map PNGs")
    args = parser.parse_args()
    outputs, box, size, offset = render_outputs()
    outputs, boxes = compact_overlays(outputs)
    outputs.update(render_trade_routes())
    interfaces = interface_outputs(boxes)
    if args.apply:
        for name, source in interfaces.items():
            (ROOT / name).write_text(source, encoding="utf-8")
        apply(outputs)
        (OUT / "VAL_vorkerland_aid_map.png").unlink(missing_ok=True)
        print(f"Wrote operations map to {OUT.relative_to(ROOT)}; source crop={box}, resized={size}, offset={offset}")
    issues = validate_outputs(outputs)
    for name, source in interfaces.items():
        if not (ROOT / name).exists() or (ROOT / name).read_text(encoding="utf-8") != source:
            issues.append(f"generated interface differs: {name}")
    if issues:
        for issue in issues:
            print(f"ERROR: {issue}")
        return 1
    print("VAL operations-map validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
