#!/usr/bin/env python3
"""Smooth jagged northern political and coastline province borders.

The pass only rewrites pixels inside the northern right-continent box used by
HON/NVR/AUR and their immediate neighbours. Province ids and colours stay the
same; thin one-pixel jogs, coastal spikes and one-pixel inlets are reassigned
to an orthogonally adjacent province. Height, terrain, rivers, trees and
normals follow land/sea changes. Run without ``--apply`` to compare.
"""

from __future__ import annotations

import argparse
import os
import re
import time
from array import array
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from PIL import Image

from tools.lib.paths import repository_root


ROOT = repository_root()
PROVINCES_PATH = ROOT / "map" / "provinces.bmp"
DEFINITION_PATH = ROOT / "map" / "definition.csv"
HEIGHTMAP_PATH = ROOT / "map" / "heightmap.bmp"
TERRAIN_PATH = ROOT / "map" / "terrain.bmp"
RIVERS_PATH = ROOT / "map" / "rivers.bmp"
TREES_PATH = ROOT / "map" / "trees.bmp"
CITIES_PATH = ROOT / "map" / "cities.bmp"
WORLD_NORMAL_PATH = ROOT / "map" / "world_normal.bmp"
STATE_DIR = ROOT / "history" / "states"

FOCUS_TAGS = frozenset({
    "AUR", "DRV", "ELN", "HON", "KDL", "LYS", "MON", "NVR", "SKN", "SVL", "TMR", "VES",
})
MIN_MAP_X = 2900
SCOPE_PAD = 16
ARCTIC_MAX_Y = 640
MIN_PROVINCE_PIXELS = 8
MAX_PASSES = 8
CITY_PALETTE = 15
URBAN_TERRAIN = 13
WATER_TERRAIN = 15
SEA_HEIGHT = 89
LAND_RIVER = 255
SEA_RIVER = 254
NORMAL_CENTER = 127
NORMAL_SCALE = 1.65
NORMAL_BLUE = 253
ORTHO = ((-1, 0), (1, 0), (0, -1), (0, 1))
NEIGH8 = ORTHO + ((-1, -1), (-1, 1), (1, -1), (1, 1))


@dataclass(frozen=True)
class ProvinceInfo:
    province_id: int
    color: int
    rgb: tuple[int, int, int]
    kind: str
    coastal: bool
    terrain: str
    continent: str


@dataclass
class BorderState:
    width: int
    height: int
    colors: array
    province_ids: array
    land: bytearray
    blocked: bytearray
    owners: dict[int, str]
    by_id: dict[int, ProvinceInfo]
    counts: dict[int, int]


@dataclass
class LayerBundle:
    height: bytearray
    terrain: bytearray
    terrain_image: Image.Image
    rivers: bytearray
    rivers_image: Image.Image
    trees: bytearray
    trees_image: Image.Image
    cities: bytearray
    city_width: int
    city_height: int
    normal: Image.Image


def pack_rgb(red: int, green: int, blue: int) -> int:
    return (red << 16) | (green << 8) | blue


def unpack_rgb(color: int) -> tuple[int, int, int]:
    return (color >> 16) & 255, (color >> 8) & 255, color & 255


def load_definition(path: Path = DEFINITION_PATH) -> tuple[list[str], str, bool, dict[int, ProvinceInfo]]:
    raw = path.read_bytes()
    bom = raw.startswith(b"\xef\xbb\xbf")
    text = raw.decode("utf-8-sig")
    newline = "\r\n" if "\r\n" in text else "\n"
    lines = text.splitlines()
    by_id: dict[int, ProvinceInfo] = {}
    for line in lines:
        fields = line.split(";")
        if len(fields) < 7 or not fields[0].isdigit():
            continue
        province_id = int(fields[0])
        rgb = (int(fields[1]), int(fields[2]), int(fields[3]))
        by_id[province_id] = ProvinceInfo(
            province_id=province_id,
            color=pack_rgb(*rgb),
            rgb=rgb,
            kind=fields[4],
            coastal=fields[5].lower() == "true",
            terrain=fields[6],
            continent=fields[7] if len(fields) > 7 else "0",
        )
    return lines, newline, bom, by_id


def load_owners(state_dir: Path = STATE_DIR) -> dict[int, str]:
    owners: dict[int, str] = {}
    identity = re.compile(r"\bid\s*=\s*(\d+)")
    owner = re.compile(r"\bowner\s*=\s*([A-Z]{3})")
    provinces = re.compile(r"\bprovinces\s*=\s*\{([^}]*)\}", re.DOTALL)
    for path in sorted(state_dir.glob("*.txt")):
        text = path.read_text(encoding="utf-8-sig")
        state_match = identity.search(text)
        owner_match = owner.search(text)
        province_match = provinces.search(text)
        if not (state_match and owner_match and province_match):
            continue
        tag = owner_match.group(1)
        for province_id in map(int, re.findall(r"\d+", province_match.group(1))):
            owners[province_id] = tag
    return owners


def _image_bytes(image: Image.Image, mode: str) -> bytearray:
    if image.mode != mode:
        raise RuntimeError(f"expected mode {mode}, found {image.mode}")
    return bytearray(image.get_flattened_data() if mode == "P" else image.convert("L").tobytes())


def load_layers() -> LayerBundle:
    with Image.open(HEIGHTMAP_PATH) as heightmap:
        height = bytearray(heightmap.convert("L").tobytes())
    with Image.open(TERRAIN_PATH) as terrain:
        terrain_copy = terrain.copy()
        terrain_pixels = _image_bytes(terrain, "P")
    with Image.open(RIVERS_PATH) as rivers:
        rivers_copy = rivers.copy()
        rivers_pixels = _image_bytes(rivers, "P")
    with Image.open(TREES_PATH) as trees:
        trees_copy = trees.copy()
        trees_pixels = _image_bytes(trees, "P")
    with Image.open(CITIES_PATH) as cities:
        city_width, city_height = cities.size
        city_pixels = _image_bytes(cities, "P")
    with Image.open(WORLD_NORMAL_PATH) as normal:
        normal_copy = normal.convert("RGB").copy()
    return LayerBundle(
        height=height,
        terrain=terrain_pixels,
        terrain_image=terrain_copy,
        rivers=rivers_pixels,
        rivers_image=rivers_copy,
        trees=trees_pixels,
        trees_image=trees_copy,
        cities=city_pixels,
        city_width=city_width,
        city_height=city_height,
        normal=normal_copy,
    )


def load_border_state(
    provinces: Image.Image,
    by_id: dict[int, ProvinceInfo],
    owners: dict[int, str],
    blocked: bytearray | None = None,
) -> BorderState:
    if provinces.mode != "RGB":
        provinces = provinces.convert("RGB")
    width, height = provinces.size
    packed: dict[int, ProvinceInfo] = {info.color: info for info in by_id.values()}
    raw = provinces.tobytes()
    colors = array("I", [0]) * (width * height)
    province_ids = array("I", [0]) * (width * height)
    land = bytearray(width * height)
    counts: dict[int, int] = {}
    for index in range(width * height):
        offset = index * 3
        color = pack_rgb(raw[offset], raw[offset + 1], raw[offset + 2])
        info = packed.get(color)
        if info is None:
            raise RuntimeError(f"provinces.bmp uses undefined colour {unpack_rgb(color)}")
        colors[index] = color
        province_ids[index] = info.province_id
        land[index] = 1 if info.kind == "land" else 0
        counts[info.province_id] = counts.get(info.province_id, 0) + 1
    return BorderState(
        width=width,
        height=height,
        colors=colors,
        province_ids=province_ids,
        land=land,
        blocked=blocked if blocked is not None else bytearray(width * height),
        owners=owners,
        by_id=by_id,
        counts=counts,
    )


def focus_box(state: BorderState) -> tuple[int, int, int, int]:
    left, top, right, bottom = state.width, state.height, -1, -1
    for index, province_id in enumerate(state.province_ids):
        if not state.land[index]:
            continue
        if state.owners.get(province_id) not in FOCUS_TAGS:
            continue
        x = index % state.width
        y = index // state.width
        if x < MIN_MAP_X:
            continue
        left = min(left, x)
        right = max(right, x)
        top = min(top, y)
        bottom = max(bottom, y)
    if right < 0:
        raise RuntimeError("northern focus countries were not found on provinces.bmp")
    return (
        max(MIN_MAP_X, left - SCOPE_PAD),
        max(0, top - SCOPE_PAD),
        min(state.width - 1, right + SCOPE_PAD),
        min(state.height - 1, bottom + SCOPE_PAD),
    )


def in_box(x: int, y: int, box: tuple[int, int, int, int]) -> bool:
    left, top, right, bottom = box
    return left <= x <= right and top <= y <= bottom


def neighbour_index(state: BorderState, x: int, y: int, dx: int, dy: int) -> int | None:
    nx, ny = x + dx, y + dy
    if 0 <= nx < state.width and 0 <= ny < state.height:
        return ny * state.width + nx
    return None


def on_arctic_shore(state: BorderState, index: int) -> bool:
    x, y = index % state.width, index // state.width
    if y > ARCTIC_MAX_Y:
        return False
    if state.land[index]:
        north = neighbour_index(state, x, y, 0, -1)
        return north is not None and not state.land[north]
    south = neighbour_index(state, x, y, 0, 1)
    return south is not None and state.land[south]


def majority_destination(state: BorderState, index: int, *, coast: bool, strong: bool) -> int | None:
    x, y = index % state.width, index // state.width
    own_id = state.province_ids[index]
    own_tag = state.owners.get(own_id, "")
    ortho: list[int] = []
    for dx, dy in ORTHO:
        neighbour = neighbour_index(state, x, y, dx, dy)
        if neighbour is not None:
            ortho.append(neighbour)
    if coast and not strong:
        land_ortho = [neighbour for neighbour in ortho if state.land[neighbour]]
        sea_ortho = [neighbour for neighbour in ortho if not state.land[neighbour]]
        if not state.land[index] and len(land_ortho) >= 3:
            return state.province_ids[land_ortho[0]]
        if state.land[index] and len(sea_ortho) >= 3:
            return state.province_ids[sea_ortho[0]]
        return None
    land_votes = 0
    sea_votes = 0
    tag_counts: Counter[str] = Counter()
    nearest_by_tag: dict[str, int] = {}
    nearest_land = None
    nearest_sea = None
    for dx, dy in NEIGH8:
        neighbour = neighbour_index(state, x, y, dx, dy)
        if neighbour is None:
            continue
        province_id = state.province_ids[neighbour]
        if state.land[neighbour]:
            land_votes += 1
            tag = state.owners.get(province_id, "")
            tag_counts[tag] += 1
            nearest_by_tag.setdefault(tag, province_id)
            if nearest_land is None:
                nearest_land = province_id
        else:
            sea_votes += 1
            if nearest_sea is None:
                nearest_sea = province_id
    if coast:
        if state.land[index] and sea_votes >= 5:
            return nearest_sea
        if not state.land[index] and land_votes >= 5:
            return nearest_land
        return None
    if not state.land[index] or not tag_counts:
        return None
    winner, win_count = tag_counts.most_common(1)[0]
    if winner != own_tag and win_count > tag_counts.get(own_tag, 0):
        return nearest_by_tag.get(winner)
    other_counts: Counter[str] = Counter()
    for neighbour in ortho:
        if not state.land[neighbour]:
            continue
        tag = state.owners.get(state.province_ids[neighbour], "")
        if tag and tag != own_tag:
            other_counts[tag] += 1
            nearest_by_tag.setdefault(tag, state.province_ids[neighbour])
    if other_counts and other_counts.most_common(1)[0][1] >= 3:
        other, _count = other_counts.most_common(1)[0]
        return nearest_by_tag[other]
    return None


def thin_feature_destination(state: BorderState, index: int, *, arctic: bool) -> int | None:
    width = state.width
    x, y = index % width, index // width
    ortho: list[int | None] = [neighbour_index(state, x, y, dx, dy) for dx, dy in ORTHO]
    left, right, up, down = ortho
    if None in ortho:
        return None

    def landish(neighbour: int | None) -> bool:
        return bool(neighbour is not None and state.land[neighbour])

    if state.land[index]:
        if landish(left) == landish(right) and not landish(left):
            return state.province_ids[left] if left is not None else None
        if landish(up) == landish(down) and not landish(up):
            return state.province_ids[up] if up is not None else None
        if arctic:
            sea_ortho = [neighbour for neighbour in ortho if neighbour is not None and not state.land[neighbour]]
            if len(sea_ortho) >= 3:
                return state.province_ids[sea_ortho[0]]
        own_tag = state.owners.get(state.province_ids[index], "")
        for first, second in ((left, right), (up, down)):
            if first is None or second is None:
                continue
            if not (state.land[first] and state.land[second]):
                continue
            first_tag = state.owners.get(state.province_ids[first], "")
            second_tag = state.owners.get(state.province_ids[second], "")
            if first_tag and first_tag == second_tag != own_tag:
                return state.province_ids[first]
        return None
    if landish(left) and landish(right) and not landish(up) and not landish(down):
        return state.province_ids[left] if left is not None else None
    if landish(up) and landish(down) and not landish(left) and not landish(right):
        return state.province_ids[up] if up is not None else None
    return None


def locally_connected(state: BorderState, index: int, province_id: int) -> bool:
    width, height = state.width, state.height
    x, y = index % width, index // width
    members = []
    for dx, dy in ORTHO:
        neighbour = neighbour_index(state, x, y, dx, dy)
        if neighbour is not None and state.province_ids[neighbour] == province_id:
            members.append(neighbour)
    if len(members) <= 1:
        return True
    start = members[0]
    seen = {start}
    queue = [start]
    while queue:
        current = queue.pop()
        cx, cy = current % width, current // width
        for dx, dy in ORTHO:
            nx, ny = cx + dx, cy + dy
            if abs(nx - x) > 3 or abs(ny - y) > 3:
                continue
            if not (0 <= nx < width and 0 <= ny < height):
                continue
            candidate = ny * width + nx
            if candidate == index or candidate in seen:
                continue
            if state.province_ids[candidate] != province_id:
                continue
            seen.add(candidate)
            queue.append(candidate)
    return all(member in seen for member in members)


def can_reassign(state: BorderState, index: int, destination: int) -> bool:
    if destination == state.province_ids[index]:
        return False
    dest = state.by_id.get(destination)
    if dest is None:
        return False
    source_id = state.province_ids[index]
    remaining = state.counts.get(source_id, 0) - 1
    if remaining < 1:
        return False
    if remaining < MIN_PROVINCE_PIXELS and state.counts.get(source_id, 0) > MIN_PROVINCE_PIXELS:
        return False
    if not locally_connected(state, index, source_id):
        return False
    x, y = index % state.width, index // state.width
    adjacent = False
    for dx, dy in ORTHO:
        neighbour = neighbour_index(state, x, y, dx, dy)
        if neighbour is not None and state.province_ids[neighbour] == destination:
            adjacent = True
            break
    return adjacent


def assign(state: BorderState, index: int, destination: int) -> None:
    source = state.province_ids[index]
    info = state.by_id[destination]
    state.counts[source] = state.counts.get(source, 0) - 1
    state.counts[destination] = state.counts.get(destination, 0) + 1
    state.province_ids[index] = destination
    state.colors[index] = info.color
    state.land[index] = 1 if info.kind == "land" else 0


def mark_blocked(state: BorderState, layers: LayerBundle | None) -> None:
    if layers is None:
        return
    width, height = state.width, state.height
    city_w, city_h = layers.city_width, layers.city_height
    for index in range(width * height):
        if layers.terrain[index] == URBAN_TERRAIN:
            state.blocked[index] = 1
            continue
        x, y = index % width, index // width
        cx = min(city_w - 1, x * city_w // width)
        cy = min(city_h - 1, y * city_h // height)
        if layers.cities[cy * city_w + cx] == CITY_PALETTE:
            state.blocked[index] = 1


def on_border(state: BorderState, index: int, *, coast: bool) -> bool:
    x, y = index % state.width, index // state.width
    own_land = state.land[index]
    own_tag = state.owners.get(state.province_ids[index], "")
    for dx, dy in ORTHO:
        neighbour = neighbour_index(state, x, y, dx, dy)
        if neighbour is None:
            continue
        if coast and state.land[neighbour] != own_land:
            return True
        if not coast and own_land and state.land[neighbour] and state.owners.get(state.province_ids[neighbour], "") != own_tag:
            return True
    return False


def smooth_pass(state: BorderState, box: tuple[int, int, int, int], *, coast: bool) -> int:
    left, top, right, bottom = box
    changed = 0
    for y in range(top, bottom + 1):
        row = y * state.width
        for x in range(left, right + 1):
            index = row + x
            if state.blocked[index]:
                continue
            if not on_border(state, index, coast=coast):
                destination = thin_feature_destination(state, index, arctic=coast and y <= ARCTIC_MAX_Y)
            else:
                strong = (not coast) or on_arctic_shore(state, index)
                destination = majority_destination(state, index, coast=coast, strong=strong)
                if destination is None:
                    destination = thin_feature_destination(
                        state, index, arctic=coast and y <= ARCTIC_MAX_Y
                    )
            if destination is None or not can_reassign(state, index, destination):
                continue
            assign(state, index, destination)
            changed += 1
    return changed


def smooth_borders(state: BorderState, box: tuple[int, int, int, int] | None = None) -> int:
    scope = box or focus_box(state)
    changed = 0
    for _ in range(MAX_PASSES):
        step = smooth_pass(state, scope, coast=False) + smooth_pass(state, scope, coast=True)
        changed += step
        if step == 0:
            break
    return changed


def provinces_image(state: BorderState) -> Image.Image:
    raw = bytearray(state.width * state.height * 3)
    for index, color in enumerate(state.colors):
        offset = index * 3
        raw[offset], raw[offset + 1], raw[offset + 2] = unpack_rgb(color)
    return Image.frombytes("RGB", (state.width, state.height), bytes(raw))


def neighbour_sample(state: BorderState, layers: LayerBundle, index: int, *, want_land: bool) -> tuple[int, int]:
    x, y = index % state.width, index // state.width
    heights: list[int] = []
    terrains: list[int] = []
    for dx, dy in NEIGH8:
        neighbour = neighbour_index(state, x, y, dx, dy)
        if neighbour is None or state.land[neighbour] != want_land:
            continue
        heights.append(layers.height[neighbour])
        terrains.append(layers.terrain[neighbour])
    if want_land:
        terrains = [value for value in terrains if value not in (WATER_TERRAIN, 14)]
        height = sorted(heights)[len(heights) // 2] if heights else 110
        terrain = Counter(terrains).most_common(1)[0][0] if terrains else 0
        return height, terrain
    return SEA_HEIGHT, WATER_TERRAIN


def sync_layers(state: BorderState, original: BorderState, layers: LayerBundle, box: tuple[int, int, int, int]) -> None:
    left, top, right, bottom = box
    tree_w, tree_h = layers.trees_image.size
    dirty_trees: set[int] = set()
    dirty_normals: set[int] = set()
    for y in range(top, bottom + 1):
        for x in range(left, right + 1):
            index = y * state.width + x
            if state.land[index] == original.land[index]:
                continue
            if state.land[index]:
                height, terrain = neighbour_sample(state, layers, index, want_land=True)
                layers.height[index] = height
                layers.terrain[index] = terrain
                layers.rivers[index] = LAND_RIVER
            else:
                layers.height[index] = SEA_HEIGHT
                layers.terrain[index] = WATER_TERRAIN
                layers.rivers[index] = SEA_RIVER
            tx = min(tree_w - 1, x * tree_w // state.width)
            ty = min(tree_h - 1, y * tree_h // state.height)
            dirty_trees.add(ty * tree_w + tx)
            dirty_normals.add((y // 2) * (state.width // 2) + (x // 2))
    for tree_index in dirty_trees:
        tx = tree_index % tree_w
        ty = tree_index // tree_w
        x0 = tx * state.width // tree_w
        x1 = (tx + 1) * state.width // tree_w
        y0 = ty * state.height // tree_h
        y1 = (ty + 1) * state.height // tree_h
        water = 0
        area = 0
        for py in range(y0, y1):
            for px in range(x0, x1):
                area += 1
                if not state.land[py * state.width + px]:
                    water += 1
        if area and water * 2 >= area:
            layers.trees[tree_index] = 0
    if dirty_normals:
        update_normals(layers, state, dirty_normals)


def update_normals(layers: LayerBundle, state: BorderState, dirty: set[int]) -> None:
    normal_w, normal_h = layers.normal.size
    if (normal_w * 2, normal_h * 2) != (state.width, state.height):
        raise RuntimeError("world_normal.bmp must be half of the heightmap size")
    means = array("f", [0.0]) * (normal_w * normal_h)
    heights = layers.height
    for ny in range(normal_h):
        top = (ny * 2) * state.width
        bottom = top + state.width
        for nx in range(normal_w):
            left = nx * 2
            means[ny * normal_w + nx] = (
                heights[top + left]
                + heights[top + left + 1]
                + heights[bottom + left]
                + heights[bottom + left + 1]
            ) / 4.0
    pixels = bytearray(layers.normal.tobytes())
    affected = set(dirty)
    for index in dirty:
        nx, ny = index % normal_w, index // normal_w
        if nx:
            affected.add(index - 1)
        if nx + 1 < normal_w:
            affected.add(index + 1)
        if ny:
            affected.add(index - normal_w)
        if ny + 1 < normal_h:
            affected.add(index + normal_w)
    for index in affected:
        nx, ny = index % normal_w, index // normal_w
        west = index - 1 if nx else index
        east = index + 1 if nx + 1 < normal_w else index
        north = index - normal_w if ny else index
        south = index + normal_w if ny + 1 < normal_h else index
        dx = (means[east] - means[west]) / 2.0
        dy = (means[south] - means[north]) / 2.0
        offset = index * 3
        pixels[offset] = max(0, min(255, round(NORMAL_CENTER - NORMAL_SCALE * dx)))
        pixels[offset + 1] = max(0, min(255, round(NORMAL_CENTER + NORMAL_SCALE * dy)))
        pixels[offset + 2] = NORMAL_BLUE
    layers.normal = Image.frombytes("RGB", (normal_w, normal_h), bytes(pixels))


def coastal_flags(state: BorderState, scoped: set[int]) -> dict[int, bool]:
    flags = {province_id: False for province_id in scoped}
    width, height = state.width, state.height
    for index, province_id in enumerate(state.province_ids):
        if province_id not in flags:
            continue
        x, y = index % width, index // width
        own_land = state.land[index]
        for dx, dy in ORTHO:
            neighbour = neighbour_index(state, x, y, dx, dy)
            if neighbour is None:
                continue
            if state.land[neighbour] != own_land:
                flags[province_id] = True
                break
    return flags


def render_definition(
    lines: list[str],
    newline: str,
    bom: bool,
    flags: dict[int, bool],
) -> bytes:
    rendered: list[str] = []
    for line in lines:
        fields = line.split(";")
        if len(fields) >= 7 and fields[0].isdigit():
            province_id = int(fields[0])
            if province_id in flags:
                fields[5] = "true" if flags[province_id] else "false"
                line = ";".join(fields)
        rendered.append(line)
    text = newline.join(rendered)
    if lines:
        text += newline
    payload = text.encode("utf-8")
    return (b"\xef\xbb\xbf" + payload) if bom else payload


def paletted_image(source: Image.Image, pixels: bytearray) -> Image.Image:
    result = source.copy()
    result.putdata(pixels)
    return result


def expected(owners: dict[int, str] | None = None) -> tuple[BorderState, BorderState, tuple[int, int, int, int], LayerBundle, bytes]:
    lines, newline, bom, by_id = load_definition()
    owner_map = owners if owners is not None else load_owners()
    with Image.open(PROVINCES_PATH) as source:
        original = load_border_state(source.convert("RGB"), by_id, owner_map)
    layers = load_layers()
    mark_blocked(original, layers)
    state = BorderState(
        width=original.width,
        height=original.height,
        colors=array("I", original.colors),
        province_ids=array("I", original.province_ids),
        land=bytearray(original.land),
        blocked=original.blocked,
        owners=original.owners,
        by_id=original.by_id,
        counts=dict(original.counts),
    )
    box = focus_box(state)
    smooth_borders(state, box)
    sync_layers(state, original, layers, box)
    scoped = {
        state.province_ids[y * state.width + x]
        for y in range(box[1], box[3] + 1)
        for x in range(box[0], box[2] + 1)
    }
    definition = render_definition(lines, newline, bom, coastal_flags(state, scoped))
    return original, state, box, layers, definition


def scoped_differences(original: BorderState, state: BorderState, box: tuple[int, int, int, int]) -> int:
    left, top, right, bottom = box
    changed = 0
    for y in range(top, bottom + 1):
        for x in range(left, right + 1):
            index = y * state.width + x
            if original.colors[index] != state.colors[index]:
                changed += 1
    return changed


def outside_changed(original: BorderState, state: BorderState, box: tuple[int, int, int, int]) -> int:
    changed = 0
    for index, color in enumerate(state.colors):
        x, y = index % state.width, index // state.width
        if in_box(x, y, box):
            continue
        if color != original.colors[index]:
            changed += 1
    return changed


def atomic_save_bmp(image: Image.Image, path: Path) -> None:
    temporary = path.with_suffix(".bmp.tmp")
    try:
        image.save(temporary, format="BMP")
        with temporary.open("r+b") as generated:
            generated.flush()
            os.fsync(generated.fileno())
        last_error: OSError | None = None
        for _attempt in range(8):
            try:
                os.replace(temporary, path)
                return
            except OSError as error:
                last_error = error
                if getattr(error, "winerror", None) != 5:
                    raise
                time.sleep(0.25)
        raise last_error if last_error is not None else OSError("failed to replace bitmap")
    finally:
        temporary.unlink(missing_ok=True)


def apply() -> None:
    _original, state, _box, layers, definition = expected()
    atomic_save_bmp(provinces_image(state), PROVINCES_PATH)
    atomic_save_bmp(Image.frombytes("L", (state.width, state.height), bytes(layers.height)), HEIGHTMAP_PATH)
    atomic_save_bmp(paletted_image(layers.terrain_image, layers.terrain), TERRAIN_PATH)
    atomic_save_bmp(paletted_image(layers.rivers_image, layers.rivers), RIVERS_PATH)
    atomic_save_bmp(paletted_image(layers.trees_image, layers.trees), TREES_PATH)
    atomic_save_bmp(layers.normal, WORLD_NORMAL_PATH)
    DEFINITION_PATH.write_bytes(definition)


def validate() -> list[str]:
    issues: list[str] = []
    original, state, box, layers, definition = expected()
    escaped = outside_changed(original, state, box)
    if escaped:
        issues.append(f"northern border smoother escaped its box at {escaped} pixels")
    with Image.open(PROVINCES_PATH) as current:
        current_state = load_border_state(current.convert("RGB"), state.by_id, state.owners)
    drifted = scoped_differences(current_state, state, box)
    if drifted:
        issues.append(f"map/provinces.bmp: {drifted} northern border pixels still need smoothing")
    if DEFINITION_PATH.read_bytes() != definition:
        issues.append("map/definition.csv: coastal flags drifted in the northern box")
    with Image.open(HEIGHTMAP_PATH) as heightmap:
        if bytearray(heightmap.convert("L").tobytes()) != layers.height:
            issues.append("map/heightmap.bmp: land/sea heights drifted in the northern box")
    with Image.open(TERRAIN_PATH) as terrain:
        if bytearray(terrain.get_flattened_data()) != layers.terrain:
            issues.append("map/terrain.bmp: land/sea terrain drifted in the northern box")
    with Image.open(RIVERS_PATH) as rivers:
        if bytearray(rivers.get_flattened_data()) != layers.rivers:
            issues.append("map/rivers.bmp: river mask drifted in the northern box")
    with Image.open(TREES_PATH) as trees:
        if bytearray(trees.get_flattened_data()) != layers.trees:
            issues.append("map/trees.bmp: water tree cells drifted in the northern box")
    with Image.open(WORLD_NORMAL_PATH) as normal:
        if normal.convert("RGB").tobytes() != layers.normal.tobytes():
            issues.append("map/world_normal.bmp: coastal normals drifted in the northern box")
    return issues


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_mutually_exclusive_group()
    actions.add_argument("--check", action="store_true", help="validate smoothed northern borders (default)")
    actions.add_argument("--apply", action="store_true", help="write smoothed northern borders")
    args = parser.parse_args()
    if args.apply:
        apply()
    issues = validate()
    if issues:
        for issue in issues:
            print(f"ERROR: {issue}")
        return 1
    print("Northern border smoothing validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
