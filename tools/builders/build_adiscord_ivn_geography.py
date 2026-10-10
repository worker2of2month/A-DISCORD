"""Generate Ivanland/IIA relief, terrain, trees and rivers; sync declared terrain."""

from __future__ import annotations

import argparse
import heapq
import json
import os
import re
from array import array
from collections import Counter, deque
from dataclasses import dataclass
from io import BytesIO
from itertools import zip_longest
from math import cos, exp, floor, pi, sin, sqrt
from pathlib import Path
from typing import Sequence

import numpy as np
from PIL import Image
from scipy.ndimage import distance_transform_edt

from tools.builders.build_adiscord_terrain_snow import (
    CITIES_PATH,
    CITY_PALETTE_INDEX,
    CITY_PALETTE_INDICES,
)
from tools.lib.coastal_clearance import (
    URBAN_FALLBACK_PALETTE,
    tree_cells_blocked,
    urban_blocked,
    water_colours,
    water_mask,
)


ROOT = Path(__file__).resolve().parents[2]
TERRAIN_PATH = ROOT / "map/terrain.bmp"
TREES_PATH = ROOT / "map/trees.bmp"
PROVINCES_PATH = ROOT / "map/provinces.bmp"
DEFINITION_PATH = ROOT / "map/definition.csv"
HEIGHTMAP_PATH = ROOT / "map/heightmap.bmp"
WORLD_NORMAL_PATH = ROOT / "map/world_normal.bmp"
TERRAIN_CONFIG_PATH = ROOT / "common/terrain/00_terrain.txt"
STATE_DIR = ROOT / "history/states"

IVN_STATE_IDS = frozenset(
    {
        25,
        92,
        95,
        96,
        97,
        98,
        99,
        100,
        101,
        127,
        129,
        130,
        131,
        132,
        164,
        695,
        696,
        697,
        698,
        713,
        714,
        715,
        716,
        717,
    }
)
IIA_STATE_IDS = frozenset({128, 693, 694})
SCOPED_STATE_IDS = IVN_STATE_IDS | IIA_STATE_IDS
ISLAND_HEIGHT_STATE_IDS = frozenset({128, 693, 694})
NORTHERN_LANDSCAPE_STATE_IDS = frozenset(
    {127, 128, 129, 130, 131, 132, 164, 693, 694, 715}
)
MAINLAND_FOREST_STATE_IDS = (
    NORTHERN_LANDSCAPE_STATE_IDS - ISLAND_HEIGHT_STATE_IDS - {164}
)
PROVINCE_MANIFEST_PATH = ROOT / "tools/data/adiscord_ivn_provinces.json"
PROVINCE_MANIFEST = json.loads(PROVINCE_MANIFEST_PATH.read_text(encoding="utf-8"))
# Every IVN victory point is a whole urban province; the island
# administration keeps compact urban footprints inside rural provinces.
CITY_PROVINCES = frozenset(int(city) for city in PROVINCE_MANIFEST["cities"].values())
SETTLEMENT_PROVINCES = frozenset({579, 6905, 11841}) | CITY_PROVINCES
# Mainland relief of the Itoran civil-war theatre. Heights are a pure function
# of position, coast and the unchanged foreign border, so repeated passes
# converge. The detached western islands keep their authored relief.
RELIEF_STATE_IDS = IVN_STATE_IDS
MARCH_RELIEF_STATE_IDS = IVN_STATE_IDS - NORTHERN_LANDSCAPE_STATE_IDS
RELIEF_EXCLUDED_PROVINCES = frozenset({8885, 9037, 10675, 11000})
# The March Ridge separates the northern lobe from the marches; its spur and
# the Longar heights continue along the eastern march.
RIDGE_SPINE = (
    (2833, 1009),
    (2846, 1004),
    (2860, 1002),
    (2874, 999),
    (2887, 999),
    (2899, 1006),
    (2908, 1014),
)
RIDGE_SPUR = ((2896, 1004), (2890, 1022), (2886, 1036), (2884, 1050), (2880, 1058))
# (x, y, x radius, y radius, amplitude): Longar heights, the Olsia upland and
# its summit, and the Lakora hills.
RELIEF_DOMES = (
    (2919, 1050, 10.0, 9.0, 34.0),
    (2826, 1230, 30.0, 16.0, 50.0),
    (2830, 1232, 13.0, 10.0, 74.0),
    (2872, 1203, 8.0, 7.0, 32.0),
)
# The Rinval fens lie between the western march and the Old March capital.
FEN_LINE = ((2786, 1099), (2800, 1095), (2815, 1093), (2830, 1093), (2843, 1097))
FEN_HALF_WIDTH = 5.0
# The Old March forest screens the capital from the eastern marches.
FOREST_ZONES = ((2850, 1112, 17.0, 12.0),)
RIVERS_PATH = ROOT / "map/rivers.bmp"
UNITSTACKS_PATH = ROOT / "map/unitstacks.txt"
# Reviewed province geometry of the IVN mainland: an RGBA crop whose opaque
# pixels are stamped into provinces.bmp. PROVINCE_MANIFEST lists new provinces.
PROVINCE_GEOMETRY_PATH = ROOT / "tools/data/adiscord_ivn_province_geometry.png"
# A victory-point province up to this size becomes the city itself; a larger
# one yields a compact city of CITY_PIXELS and rural sectors around it.
CITY_WHOLE_PROVINCE_PIXELS = 115
CITY_PIXELS = 45
SECTOR_PIXELS = 150
SPLIT_PIXELS = 300
LOCKED_PROVINCE_PIXELS = 60
# Provinces that already carried authored rivers. Their river pixels, and
# every pixel touching them, stay outside this builder's river layer.
_AUTHORED_RIVER_PARENTS = frozenset(
    {
        1304, 1421, 1697, 2058, 2752, 3131, 3447, 3462, 3598, 3847, 4103, 4217,
        4553, 4576, 5573, 5586, 6020, 6507, 7603, 7713, 7911, 8536, 9100, 9183,
        9685, 9894, 11115, 11132, 11382, 11480, 11613, 12160, 12317, 12342, 12463,
    }
)
AUTHORED_RIVER_PROVINCES = _AUTHORED_RIVER_PARENTS | frozenset(
    int(entry["province"])
    for entry in PROVINCE_MANIFEST["provinces"]
    if entry["parent"] in _AUTHORED_RIVER_PARENTS
)
# Waypoints from the source to the mouth. Rivers run only on province-border
# pixels, so they separate provinces instead of crossing them.
RIVER_COURSES = (
    ((2853, 1016), (2849, 1045), (2846, 1075), (2836, 1090), (2815, 1094), (2795, 1099), (2782, 1101)),
    ((2858, 996), (2853, 980), (2850, 962), (2855, 948)),
    ((2860, 1066), (2863, 1086), (2858, 1110), (2845, 1128), (2828, 1136), (2806, 1122)),
    ((2827, 1228), (2840, 1232), (2850, 1236), (2858, 1244)),
)
RIVER_MOUTH_RADIUS = 14
RIVER_SIDE_SWITCH_COST = 30.0
RIVER_SOURCE_PALETTE = 0
RIVER_SEA_PALETTE = 254
RIVER_LAND_PALETTE = 255
TERRAIN_PRIORITY = (
    "urban",
    "mountain",
    "hills",
    "marsh",
    "forest",
    "plains",
    "jungle",
    "desert",
)
WATER_TYPES = frozenset({"ocean", "lakes"})
WATER_PALETTES = frozenset({14, 15})
PLAINS_PALETTE = 0
FOREST_PALETTE = 4
MARSH_PALETTE = 9
URBAN_PALETTE = 13
HILLS_PALETTE = 17
MOUNTAIN_PALETTE = 20
MIN_URBAN_PIXELS = 24
URBAN_SHARE = 0.12
MAX_URBAN_SHARE = 0.65
HEIGHT_MIN = 97
HEIGHT_MAX = 175
NORMAL_CENTER = 127
NORMAL_SCALE = 1.65
NORMAL_BLUE = 253


@dataclass(frozen=True)
class LandscapeMasks:
    island: bytearray
    north: bytearray
    island_bbox: tuple[int, int, int, int]
    state_by_pixel: array


@dataclass(frozen=True)
class TreeCellSample:
    state_id: int | None
    terrain_type: str


@dataclass(frozen=True)
class CoverageMetrics:
    island_forest_share: float
    mainland_forest_shares: dict[int, float]
    tree_occupancy: dict[str, float]
    forbidden_tree_cells: int
    terrain_changes_outside_scope: int
    tree_changes_outside_scope: int
    mountain_pixels: int
    hill_pixels: int
    mountain_transition_violations: int
    mountain_components_without_shoulders: int


@dataclass
class GeographyOutputs:
    terrain: Image.Image
    definition: bytes
    heightmap: Image.Image
    world_normal: Image.Image
    trees: Image.Image
    rivers: Image.Image
    unitstacks: bytes
    river_issues: list[str]
    desired: dict[int, str]
    counts: dict[int, Counter[str]]
    footprints: dict[int, set[int]]
    metrics: CoverageMetrics


def state_path(state_id: int) -> Path:
    matches = tuple(STATE_DIR.glob(f"{state_id}-*.txt"))
    if len(matches) != 1:
        raise RuntimeError(f"state {state_id}: expected one file, found {len(matches)}")
    return matches[0]


def province_ids_for_states(state_ids: frozenset[int]) -> frozenset[int]:
    result: set[int] = set()
    for state_id in state_ids:
        source = state_path(state_id).read_text(encoding="utf-8-sig", errors="strict")
        match = re.search(r"\bprovinces\s*=\s*\{([^}]*)\}", source, re.DOTALL)
        if match is None:
            raise RuntimeError(f"state {state_id}: missing provinces block")
        province_ids = {int(value) for value in re.findall(r"\d+", match.group(1))}
        overlap = result & province_ids
        if overlap:
            raise RuntimeError(f"IVN/IIA state provinces overlap: {sorted(overlap)}")
        result.update(province_ids)
    return frozenset(result)


def scoped_provinces() -> frozenset[int]:
    return province_ids_for_states(SCOPED_STATE_IDS)


def province_state_contract(state_ids: frozenset[int]) -> dict[int, int]:
    result: dict[int, int] = {}
    for state_id in sorted(state_ids):
        for province_id in province_ids_for_states(frozenset({state_id})):
            if province_id in result:
                raise RuntimeError(
                    f"province {province_id}: assigned to states {result[province_id]} and {state_id}"
                )
            result[province_id] = state_id
    return result


def landscape_masks(
    provinces: Image.Image,
    definition_colors: dict[int, tuple[int, int, int]],
) -> LandscapeMasks:
    island_provinces = province_ids_for_states(ISLAND_HEIGHT_STATE_IDS)
    north_provinces = province_ids_for_states(NORTHERN_LANDSCAPE_STATE_IDS)
    state_by_province = province_state_contract(NORTHERN_LANDSCAPE_STATE_IDS)
    missing = sorted(north_provinces - definition_colors.keys())
    if missing:
        raise RuntimeError(
            f"definition.csv: missing northern landscape provinces {missing}"
        )

    color_to_id = {
        color: province_id for province_id, color in definition_colors.items()
    }
    if len(color_to_id) != len(definition_colors):
        raise RuntimeError(
            "definition.csv: duplicate RGB inside northern landscape scope"
        )
    try:
        rgb = provinces.convert("RGB")
        pixels = rgb.tobytes()
    except (OSError, ValueError) as exc:
        raise RuntimeError("provinces bitmap cannot convert to RGB") from exc

    island = bytearray(provinces.width * provinces.height)
    north = bytearray(provinces.width * provinces.height)
    state_by_pixel = array("H", [0]) * (provinces.width * provinces.height)
    seen_northern_provinces: set[int] = set()
    min_x = provinces.width
    min_y = provinces.height
    max_x = -1
    max_y = -1
    for index in range(provinces.width * provinces.height):
        color = tuple(pixels[index * 3 : index * 3 + 3])
        province_id = color_to_id.get(color)
        if province_id in north_provinces:
            north[index] = 1
            state_by_pixel[index] = state_by_province[province_id]
            seen_northern_provinces.add(province_id)
        if province_id in island_provinces:
            island[index] = 1
            x = index % provinces.width
            y = index // provinces.width
            min_x = min(min_x, x)
            min_y = min(min_y, y)
            max_x = max(max_x, x)
            max_y = max(max_y, y)
    if max_x < 0:
        raise RuntimeError("provinces bitmap has no island landscape pixels")
    missing_pixels = sorted(north_provinces - seen_northern_provinces)
    if missing_pixels:
        raise RuntimeError(
            f"provinces bitmap: missing northern landscape bitmap provinces {missing_pixels}"
        )
    return LandscapeMasks(island, north, (min_x, min_y, max_x, max_y), state_by_pixel)


def distance_from_edge(mask: bytearray, width: int, height: int) -> list[int]:
    if len(mask) != width * height:
        raise ValueError("mask dimensions do not match its byte count")
    distances = [-1] * len(mask)
    frontier: deque[int] = deque()
    for index, value in enumerate(mask):
        if not value:
            continue
        x = index % width
        y = index // width
        neighbours = []
        if x:
            neighbours.append(index - 1)
        if x + 1 < width:
            neighbours.append(index + 1)
        if y:
            neighbours.append(index - width)
        if y + 1 < height:
            neighbours.append(index + width)
        if any(not mask[neighbour] for neighbour in neighbours):
            distances[index] = 0
            frontier.append(index)
    while frontier:
        index = frontier.popleft()
        x = index % width
        y = index // width
        for neighbour in (
            (index - 1 if x else None),
            (index + 1 if x + 1 < width else None),
            (index - width if y else None),
            (index + width if y + 1 < height else None),
        ):
            if neighbour is not None and mask[neighbour] and distances[neighbour] < 0:
                distances[neighbour] = distances[index] + 1
                frontier.append(neighbour)
    return distances


def stable_unit_hash(x: int, y: int, salt: int) -> float:
    value = (x * 73856093) ^ (y * 19349663) ^ (salt * 83492791)
    value = (value ^ (value >> 13)) * 1274126177
    return ((value ^ (value >> 16)) & 0xFFFFFFFF) / 0xFFFFFFFF


def island_height_value(u: float, v: float, coast_distance: int) -> int:
    coast = min(1.0, coast_distance / 11.0)
    ridge_x = 0.50 + 0.12 * sin((v - 0.12) * pi * 1.35)
    ridge = exp(-(((u - ridge_x) / 0.17) ** 2))
    ridge_spine = exp(-(((u - ridge_x) / 0.026) ** 2))
    north_lobe = exp(-(((u - 0.43) / 0.25) ** 2 + ((v - 0.27) / 0.19) ** 2))
    south_lobe = exp(-(((u - 0.57) / 0.24) ** 2 + ((v - 0.73) / 0.22) ** 2))
    valley = exp(-(((u - 0.67) / 0.13) ** 2 + ((v - 0.52) / 0.26) ** 2))
    texture = 0.5 + 0.25 * sin(7.0 * u + 4.0 * v) + 0.25 * cos(5.0 * u - 6.0 * v)
    raw = 97.0 + coast * (
        12.0
        + 43.0 * ridge
        + 60.0 * ridge_spine
        + 13.0 * north_lobe
        + 10.0 * south_lobe
        - 8.0 * valley
        + 6.0 * texture
    )
    return max(HEIGHT_MIN, min(HEIGHT_MAX, round(raw)))


def render_heightmap(
    source: Image.Image,
    island_mask: bytearray,
    bbox: tuple[int, int, int, int],
) -> Image.Image:
    if source.mode != "L":
        raise ValueError("heightmap source must use mode L")
    width, height = source.size
    if len(island_mask) != width * height:
        raise ValueError("island mask dimensions do not match heightmap")
    min_x, min_y, max_x, max_y = bbox
    if not (0 <= min_x <= max_x < width and 0 <= min_y <= max_y < height):
        raise ValueError("island bounding box lies outside heightmap")

    x_span = max(1, max_x - min_x)
    y_span = max(1, max_y - min_y)
    distances = distance_from_edge(island_mask, width, height)
    pixels = bytearray(source.tobytes())
    for index, included in enumerate(island_mask):
        if not included:
            continue
        x = index % width
        y = index // width
        u = (x - min_x) / x_span
        v = (y - min_y) / y_span
        pixels[index] = island_height_value(u, v, distances[index])
    return Image.frombytes("L", source.size, bytes(pixels))


def height_slope(
    pixels: list[int] | bytes | bytearray, width: int, height: int, index: int
) -> int:
    if len(pixels) != width * height:
        raise ValueError("height pixels do not match dimensions")
    if not 0 <= index < len(pixels):
        raise IndexError("height pixel index is outside dimensions")
    x = index % width
    y = index // width
    neighbours: list[int] = []
    if x:
        neighbours.append(index - 1)
    if x + 1 < width:
        neighbours.append(index + 1)
    if y:
        neighbours.append(index - width)
    if y + 1 < height:
        neighbours.append(index + width)
    value = pixels[index]
    return max((abs(value - pixels[neighbour]) for neighbour in neighbours), default=0)


def normal_from_height(
    heightmap: Image.Image,
    source: Image.Image,
    island_mask: bytearray,
) -> Image.Image:
    if heightmap.mode != "L":
        raise ValueError("heightmap must use mode L")
    if source.mode != "RGB":
        raise ValueError("world normal source must use mode RGB")
    width, height = heightmap.size
    normal_width, normal_height = source.size
    if (normal_width * 2, normal_height * 2) != (width, height):
        raise ValueError(
            "world normal dimensions must equal half the heightmap dimensions"
        )
    if len(island_mask) != width * height:
        raise ValueError("island mask dimensions do not match heightmap")

    heights = heightmap.tobytes()
    cell_count = normal_width * normal_height
    means = array("f", [0.0]) * cell_count
    island_cells = bytearray(cell_count)
    for ny in range(normal_height):
        top = (ny * 2) * width
        bottom = top + width
        for nx in range(normal_width):
            left = nx * 2
            full_indices = (
                top + left,
                top + left + 1,
                bottom + left,
                bottom + left + 1,
            )
            normal_index = ny * normal_width + nx
            means[normal_index] = sum(heights[index] for index in full_indices) / 4.0
            island_cells[normal_index] = any(
                island_mask[index] for index in full_indices
            )

    affected = bytearray(cell_count)
    for index, included in enumerate(island_cells):
        if not included:
            continue
        nx = index % normal_width
        ny = index // normal_width
        affected[index] = 1
        if nx:
            affected[index - 1] = 1
        if nx + 1 < normal_width:
            affected[index + 1] = 1
        if ny:
            affected[index - normal_width] = 1
        if ny + 1 < normal_height:
            affected[index + normal_width] = 1

    pixels = bytearray(source.tobytes())
    for index, included in enumerate(affected):
        if not included:
            continue
        nx = index % normal_width
        ny = index // normal_width
        west = index - 1 if nx else index
        east = index + 1 if nx + 1 < normal_width else index
        north = index - normal_width if ny else index
        south = index + normal_width if ny + 1 < normal_height else index
        dx = (means[east] - means[west]) / 2.0
        dy = (means[south] - means[north]) / 2.0
        red = max(0, min(255, round(NORMAL_CENTER - NORMAL_SCALE * dx)))
        green = max(0, min(255, round(NORMAL_CENTER + NORMAL_SCALE * dy)))
        offset = index * 3
        pixels[offset : offset + 3] = bytes((red, green, NORMAL_BLUE))
    return Image.frombytes("RGB", source.size, bytes(pixels))


def moisture_value(u: float, v: float, x: int, y: int) -> float:
    broad = 0.50 + 0.22 * sin(5.0 * u + 3.0 * v) + 0.18 * cos(4.0 * u - 6.0 * v)
    return broad + 0.10 * (stable_unit_hash(x, y, 11) - 0.5)


def tree_probability(terrain_type: str) -> float:
    return {
        "forest": 0.62,
        "plains": 0.04,
        "hills": 0.025,
        "marsh": 0.08,
    }.get(terrain_type, 0.0)


def palette_types() -> dict[int, str]:
    source = TERRAIN_CONFIG_PATH.read_text(encoding="utf-8-sig", errors="strict")
    result: dict[int, str] = {}
    for terrain_type, palette in re.findall(
        r"\btype\s*=\s*(\w+)[^}\n]*\bcolor\s*=\s*\{\s*(\d+)\s*\}", source
    ):
        index = int(palette)
        if index in result and result[index] != terrain_type:
            raise RuntimeError(f"terrain palette {index}: conflicting types")
        result[index] = terrain_type
    if result.get(URBAN_PALETTE) != "urban":
        raise RuntimeError(f"terrain palette {URBAN_PALETTE} must be urban")
    return result


def definition_contract() -> (
    tuple[list[str], str, bytes, dict[int, tuple[int, int, int]], dict[int, str]]
):
    raw = DEFINITION_PATH.read_bytes()
    bom = raw.startswith(b"\xef\xbb\xbf")
    decoded = raw.decode("utf-8-sig")
    newline = "\r\n" if "\r\n" in decoded else "\n"
    trailing = decoded.endswith(("\n", "\r"))
    lines = decoded.splitlines()
    scoped = scoped_provinces()
    colors: dict[int, tuple[int, int, int]] = {}
    declared: dict[int, str] = {}
    for line in lines:
        fields = line.split(";")
        if len(fields) < 7 or not fields[0].isdigit():
            continue
        province_id = int(fields[0])
        if province_id not in scoped:
            continue
        if fields[4] != "land":
            raise RuntimeError(
                f"province {province_id}: IVN/IIA scope contains non-land province"
            )
        colors[province_id] = tuple(map(int, fields[1:4]))
        declared[province_id] = fields[6]
    missing = sorted(scoped - colors.keys())
    if missing:
        raise RuntimeError(f"definition.csv: missing IVN/IIA provinces {missing}")
    return lines, newline, (b"\xef\xbb\xbf" if bom else b""), colors, declared


def pixel_neighbours(index: int, width: int, pixel_count: int) -> tuple[int, ...]:
    x = index % width
    neighbours: list[int] = []
    if x:
        neighbours.append(index - 1)
    if x + 1 < width and index + 1 < pixel_count:
        neighbours.append(index + 1)
    if index >= width:
        neighbours.append(index - width)
    if index + width < pixel_count:
        neighbours.append(index + width)
    return tuple(neighbours)


def straight_boundary_run(selected: set[int], width: int) -> int:
    if not selected:
        return 0
    pixel_count = (max(selected) // width + 1) * width
    maximum = 0
    rows: dict[int, set[int]] = {}
    columns: dict[int, set[int]] = {}
    for index in selected:
        x = index % width
        y = index // width
        if index - width not in selected:
            rows.setdefault(y * 2, set()).add(x)
        if index + width not in selected:
            rows.setdefault(y * 2 + 1, set()).add(x)
        if not x or index - 1 not in selected:
            columns.setdefault(x * 2, set()).add(y)
        if x + 1 == width or index + 1 >= pixel_count or index + 1 not in selected:
            columns.setdefault(x * 2 + 1, set()).add(y)
    for values in (*rows.values(), *columns.values()):
        run = 0
        previous: int | None = None
        for value in sorted(values):
            run = run + 1 if previous is not None and value == previous + 1 else 1
            maximum = max(maximum, run)
            previous = value
    return maximum


def compact_footprint(indices: list[int], width: int, province_id: int = 0) -> set[int]:
    if not indices:
        raise RuntimeError("cannot build an urban footprint for an empty province")
    maximum = int(len(indices) * MAX_URBAN_SHARE)
    if maximum < MIN_URBAN_PIXELS:
        raise RuntimeError(
            f"province has only {len(indices)} pixels; cannot preserve 35% biome"
        )
    target = min(max(MIN_URBAN_PIXELS, round(len(indices) * URBAN_SHARE)), maximum)
    province = set(indices)
    mean_x = sum(index % width for index in indices) / len(indices)
    mean_y = sum(index // width for index in indices) / len(indices)
    anchor = min(
        indices,
        key=lambda index: (
            (index % width - mean_x) ** 2 + (index // width - mean_y) ** 2,
            stable_unit_hash(index % width, index // width, province_id),
            index,
        ),
    )
    selected = {anchor}
    pixel_count = (max(indices) // width + 1) * width
    frontier: list[tuple[float, int]] = []
    queued: set[int] = set()

    def add_frontier(index: int) -> None:
        for neighbour in pixel_neighbours(index, width, pixel_count):
            if (
                neighbour not in province
                or neighbour in selected
                or neighbour in queued
            ):
                continue
            x = neighbour % width
            y = neighbour // width
            priority = (x - mean_x) ** 2 + (y - mean_y) ** 2
            priority += 0.35 * stable_unit_hash(x, y, province_id)
            heapq.heappush(frontier, (priority, neighbour))
            queued.add(neighbour)

    add_frontier(anchor)
    maximum_run = floor(round(sqrt(target)) / 2)
    while frontier and len(selected) < target:
        deferred: list[tuple[float, int]] = []
        chosen: tuple[float, int] | None = None
        while frontier:
            candidate = heapq.heappop(frontier)
            queued.discard(candidate[1])
            index = candidate[1]
            if index in selected or not any(
                neighbour in selected
                for neighbour in pixel_neighbours(index, width, pixel_count)
            ):
                continue
            if straight_boundary_run(selected | {index}, width) <= maximum_run:
                chosen = candidate
                break
            deferred.append(candidate)
        if chosen is None and deferred:
            chosen = deferred.pop(0)
        for candidate in deferred:
            heapq.heappush(frontier, candidate)
            queued.add(candidate[1])
        if chosen is None:
            break
        selected.add(chosen[1])
        add_frontier(chosen[1])
    if len(selected) < target:
        raise RuntimeError(
            "province urban footprint cannot reach its target as one connected component"
        )
    return selected


def masked_height_slope(
    pixels: bytes | bytearray,
    mask: bytearray,
    width: int,
    index: int,
) -> int:
    return max(
        (
            abs(pixels[index] - pixels[neighbour])
            for neighbour in pixel_neighbours(index, width, len(pixels))
            if mask[neighbour]
        ),
        default=0,
    )


def settlement_buffer(
    footprints: dict[int, set[int]],
    north_mask: bytearray,
    width: int,
    radius: int = 6,
) -> bytearray:
    result = bytearray(len(north_mask))
    frontier = {
        index
        for footprint in footprints.values()
        for index in footprint
        if north_mask[index]
    }
    for index in frontier:
        result[index] = 1
    for _distance in range(radius):
        following: set[int] = set()
        for index in frontier:
            for neighbour in pixel_neighbours(index, width, len(north_mask)):
                if north_mask[neighbour] and not result[neighbour]:
                    result[neighbour] = 1
                    following.add(neighbour)
        frontier = following
        if not frontier:
            break
    return result


def render_northern_terrain(
    source: Image.Image,
    heightmap: Image.Image,
    north_mask: bytearray,
    island_mask: bytearray,
    state_by_pixel: Sequence[int],
    footprints: dict[int, set[int]],
) -> Image.Image:
    if source.mode != "P":
        raise ValueError("terrain source must use mode P")
    if heightmap.mode != "L" or heightmap.size != source.size:
        raise ValueError("heightmap must use mode L and match terrain dimensions")
    width, height = source.size
    pixel_count = width * height
    if not (len(north_mask) == len(island_mask) == len(state_by_pixel) == pixel_count):
        raise ValueError("northern terrain masks do not match terrain dimensions")

    original = bytearray(source.get_flattened_data())
    heights = heightmap.tobytes()
    pixels = bytearray(original)
    urban = {
        index
        for footprint in footprints.values()
        for index in footprint
        if north_mask[index]
    }
    urban.update(
        index
        for index, included in enumerate(north_mask)
        if included and original[index] == URBAN_PALETTE
    )
    preserved_marsh = {
        index
        for index, included in enumerate(north_mask)
        if included
        and state_by_pixel[index] == 164
        and original[index] == MARSH_PALETTE
    }
    land = {
        index
        for index, included in enumerate(north_mask)
        if included and original[index] not in WATER_PALETTES
    }
    classifiable = land - urban - preserved_marsh
    slopes = {
        index: masked_height_slope(heights, north_mask, width, index) for index in land
    }
    mountains = {
        index for index in classifiable if heights[index] >= 158 or slopes[index] >= 12
    }

    first_shoulder: set[int] = set()
    for index in mountains:
        first_shoulder.update(
            neighbour
            for neighbour in pixel_neighbours(index, width, pixel_count)
            if neighbour in classifiable and neighbour not in mountains
        )
    second_candidates: set[int] = set()
    for index in first_shoulder:
        second_candidates.update(
            neighbour
            for neighbour in pixel_neighbours(index, width, pixel_count)
            if neighbour in classifiable
            and neighbour not in mountains
            and neighbour not in first_shoulder
        )
    second_shoulder = {
        index
        for index in second_candidates
        if heights[index] >= 125 or slopes[index] >= 4
    }
    shoulders = first_shoulder | second_shoulder
    hills = shoulders | {
        index
        for index in classifiable - mountains - shoulders
        if heights[index] >= 132 or slopes[index] >= 6
    }

    for index in land:
        if index in urban:
            pixels[index] = URBAN_PALETTE
        elif index in preserved_marsh:
            pixels[index] = MARSH_PALETTE
        elif index in mountains:
            pixels[index] = MOUNTAIN_PALETTE
        elif index in hills:
            pixels[index] = HILLS_PALETTE
        else:
            pixels[index] = PLAINS_PALETTE

    coast_distances = distance_from_edge(north_mask, width, height)
    buffered = settlement_buffer(footprints, north_mask, width)
    min_x = min(index % width for index in land)
    max_x = max(index % width for index in land)
    min_y = min(index // width for index in land)
    max_y = max(index // width for index in land)
    x_span = max(1, max_x - min_x)
    y_span = max(1, max_y - min_y)
    state_land: dict[int, list[int]] = {}
    forest_candidates: dict[int, list[int]] = {}
    for index in land:
        state_id = state_by_pixel[index]
        if not state_id or index in urban:
            continue
        state_land.setdefault(state_id, []).append(index)
        if (
            index not in preserved_marsh
            and index not in mountains
            and index not in hills
            and not buffered[index]
            and not (0 <= coast_distances[index] < 2)
        ):
            forest_candidates.setdefault(state_id, []).append(index)
    for state_id, state_indices in state_land.items():
        quota_share = 0.275 if state_id in ISLAND_HEIGHT_STATE_IDS else 0.225
        quota = round(len(state_indices) * quota_share)
        candidates = forest_candidates.get(state_id, [])
        if len(candidates) < quota:
            raise RuntimeError(
                f"state {state_id}: only {len(candidates)} forest candidates for quota {quota}"
            )
        ranked = sorted(
            candidates,
            key=lambda index: (
                -moisture_value(
                    (index % width - min_x) / x_span,
                    (index // width - min_y) / y_span,
                    index % width,
                    index // width,
                ),
                index,
            ),
        )
        for index in ranked[:quota]:
            pixels[index] = FOREST_PALETTE

    result = source.copy()
    result.putdata(pixels)
    return result


def _tree_cell_sample_from_pixels(
    tx: int,
    ty: int,
    tree_width: int,
    tree_height: int,
    full_width: int,
    full_height: int,
    terrain_pixels: Sequence[int],
    state_by_pixel: Sequence[int],
    palette: dict[int, str],
) -> TreeCellSample:
    if len(state_by_pixel) != full_width * full_height:
        raise ValueError("tree state mask does not match terrain dimensions")
    if not (0 <= tx < tree_width and 0 <= ty < tree_height):
        raise IndexError("tree cell lies outside tree dimensions")
    x0 = tx * full_width // tree_width
    x1 = (tx + 1) * full_width // tree_width
    y0 = ty * full_height // tree_height
    y1 = (ty + 1) * full_height // tree_height
    states: Counter[int] = Counter()
    terrain_counts: Counter[str] = Counter()
    for y in range(y0, y1):
        offset = y * full_width
        for x in range(x0, x1):
            index = offset + x
            state_id = state_by_pixel[index]
            if state_id:
                states[state_id] += 1
            terrain_index = terrain_pixels[index]
            terrain_type = palette.get(terrain_index)
            if terrain_type is None:
                raise RuntimeError(
                    f"tree sample uses unknown terrain palette {terrain_index}"
                )
            terrain_counts[terrain_type] += 1
    sample_size = (x1 - x0) * (y1 - y0)
    state_id = None
    if sum(states.values()) > sample_size / 2:
        state_id = max(states, key=lambda value: (states[value], -value))
    priority = {
        terrain_type: len(TERRAIN_PRIORITY) - rank
        for rank, terrain_type in enumerate(TERRAIN_PRIORITY)
    }
    terrain_type = max(
        terrain_counts,
        key=lambda value: (terrain_counts[value], priority.get(value, 0)),
    )
    return TreeCellSample(state_id, terrain_type)


def tree_cell_sample(
    tx: int,
    ty: int,
    tree_width: int,
    tree_height: int,
    terrain: Image.Image,
    state_by_pixel: Sequence[int],
    palette: dict[int, str],
) -> TreeCellSample:
    return _tree_cell_sample_from_pixels(
        tx,
        ty,
        tree_width,
        tree_height,
        terrain.width,
        terrain.height,
        terrain.get_flattened_data(),
        state_by_pixel,
        palette,
    )


def _render_trees_with_metrics(
    source: Image.Image,
    terrain: Image.Image,
    state_by_pixel: Sequence[int],
    palette: dict[int, str],
    blocked: "np.ndarray | None" = None,
) -> tuple[Image.Image, dict[str, tuple[int, int]], int, int]:
    if source.mode != "P":
        raise RuntimeError("trees.bmp must remain paletted")
    tree_width, tree_height = source.size
    source_pixels = bytearray(source.get_flattened_data())
    pixels = bytearray(source_pixels)
    terrain_pixels = terrain.get_flattened_data()
    counts: dict[str, list[int]] = {}
    forbidden = 0
    outside_changes = 0
    for ty in range(tree_height):
        for tx in range(tree_width):
            tree_index = ty * tree_width + tx
            sample = _tree_cell_sample_from_pixels(
                tx,
                ty,
                tree_width,
                tree_height,
                terrain.width,
                terrain.height,
                terrain_pixels,
                state_by_pixel,
                palette,
            )
            if sample.state_id is None:
                if pixels[tree_index] != source_pixels[tree_index]:
                    outside_changes += 1
                continue
            probability = tree_probability(sample.terrain_type)
            if blocked is not None and blocked[ty, tx]:
                pixels[tree_index] = 0
            elif stable_unit_hash(tx, ty, 23) < probability:
                pixels[tree_index] = 6 if stable_unit_hash(tx, ty, 29) < 0.65 else 5
            else:
                pixels[tree_index] = 0
            terrain_counts = counts.setdefault(sample.terrain_type, [0, 0])
            terrain_counts[0] += 1
            if pixels[tree_index]:
                terrain_counts[1] += 1
                if sample.terrain_type in WATER_TYPES | {"urban", "mountain"}:
                    forbidden += 1
    result = source.copy()
    result.putdata(pixels)
    return (
        result,
        {
            terrain_type: (values[0], values[1])
            for terrain_type, values in counts.items()
        },
        forbidden,
        outside_changes,
    )


def render_trees(
    source: Image.Image,
    terrain: Image.Image,
    state_by_pixel: Sequence[int],
    palette: dict[int, str],
    blocked: "np.ndarray | None" = None,
) -> Image.Image:
    return _render_trees_with_metrics(source, terrain, state_by_pixel, palette, blocked)[0]


def packed_rgb(province_rgb: np.ndarray) -> np.ndarray:
    return (
        (province_rgb[..., 0].astype(np.uint32) << 16)
        | (province_rgb[..., 1].astype(np.uint32) << 8)
        | province_rgb[..., 2].astype(np.uint32)
    )


def province_mask(
    packed: np.ndarray,
    province_colors: dict[int, tuple[int, int, int]],
    province_ids: frozenset[int],
) -> np.ndarray:
    keys = [
        (red << 16) | (green << 8) | blue
        for province_id, (red, green, blue) in province_colors.items()
        if province_id in province_ids
    ]
    return np.isin(packed, np.array(keys, dtype=np.uint32))


def relief_province_ids(state_ids: frozenset[int]) -> frozenset[int]:
    return province_ids_for_states(state_ids) - RELIEF_EXCLUDED_PROVINCES


def polyline_distance(
    xs: np.ndarray, ys: np.ndarray, points: Sequence[tuple[int, int]]
) -> tuple[np.ndarray, np.ndarray]:
    """Distance to a polyline and the normalised position along it."""
    lengths = [
        float(np.hypot(bx - ax, by - ay))
        for (ax, ay), (bx, by) in zip(points, points[1:])
    ]
    total = sum(lengths)
    best = np.full(xs.shape, np.inf)
    along = np.zeros(xs.shape)
    offset = 0.0
    for (ax, ay), (bx, by), length in zip(points, points[1:], lengths):
        dx = bx - ax
        dy = by - ay
        t = np.clip(((xs - ax) * dx + (ys - ay) * dy) / (length * length), 0.0, 1.0)
        distance = np.hypot(xs - (ax + t * dx), ys - (ay + t * dy))
        closer = distance < best
        best = np.where(closer, distance, best)
        along = np.where(closer, (offset + t * length) / total, along)
        offset += length
    return best, along


def relief_target(
    xs: np.ndarray, ys: np.ndarray, coast_distance: np.ndarray
) -> tuple[np.ndarray, np.ndarray]:
    """Return mainland heights and the fen mask for absolute map coordinates."""
    base = (
        106.0
        + 5.0 * np.sin(xs / 19.0 + ys / 27.0)
        + 4.0 * np.cos(xs / 13.0 - ys / 23.0)
        + 3.0 * np.sin((xs + ys) / 41.0)
    )
    spine, along = polyline_distance(xs, ys, RIDGE_SPINE)
    ridge = (34.0 + 44.0 * np.sin(pi * along)) * np.exp(-((spine / 12.0) ** 2))
    spur_distance, spur_along = polyline_distance(xs, ys, RIDGE_SPUR)
    spur = (
        42.0
        * (0.6 + 0.4 * np.sin(pi * spur_along))
        * np.exp(-((spur_distance / 10.0) ** 2))
    )
    raised = np.maximum(ridge, spur)
    for cx, cy, sx, sy, amplitude in RELIEF_DOMES:
        raised = np.maximum(
            raised,
            amplitude * np.exp(-(((xs - cx) / sx) ** 2 + ((ys - cy) / sy) ** 2)),
        )
    fen, _ = polyline_distance(xs, ys, FEN_LINE)
    # Lowland undulation fades over nine pixels; uplands meet the sea in
    # three, so the narrow Olsia peninsula keeps its relief.
    lowland = np.minimum(1.0, coast_distance / 9.0)
    upland = np.minimum(1.0, coast_distance / 3.0)
    height = (
        HEIGHT_MIN
        + lowland * (base - HEIGHT_MIN)
        + upland * raised
        - lowland * 9.0 * np.exp(-((fen / 6.0) ** 2))
    )
    return height, fen <= FEN_HALF_WIDTH


def render_relief_heights(
    heights: np.ndarray, relief: np.ndarray, water: np.ndarray
) -> tuple[np.ndarray, np.ndarray]:
    """Rebuild relief heights, blending into unchanged foreign land."""
    ys, xs = np.nonzero(relief)
    y0 = max(0, int(ys.min()) - 24)
    y1 = min(heights.shape[0], int(ys.max()) + 25)
    x0 = max(0, int(xs.min()) - 24)
    x1 = min(heights.shape[1], int(xs.max()) + 25)
    crop = (slice(y0, y1), slice(x0, x1))
    foreign = ~water[crop] & ~relief[crop]
    coast_distance = distance_transform_edt(~water[crop])
    foreign_distance, (fy, fx) = distance_transform_edt(~foreign, return_indices=True)
    gy, gx = np.mgrid[y0:y1, x0:x1].astype(float)
    target, fen = relief_target(gx, gy, coast_distance)
    weight = np.minimum(1.0, foreign_distance / 8.0)
    blended = weight * target + (1.0 - weight) * heights[crop][fy, fx].astype(float)
    values = np.clip(np.rint(blended), HEIGHT_MIN, HEIGHT_MAX).astype(np.uint8)
    result = heights.copy()
    result[crop] = np.where(relief[crop], values, heights[crop])
    fen_mask = np.zeros(heights.shape, bool)
    fen_mask[crop] = fen & relief[crop]
    return result, fen_mask


def neighbours_of(mask: np.ndarray) -> np.ndarray:
    result = np.zeros(mask.shape, bool)
    for axis, shift in ((0, 1), (0, -1), (1, 1), (1, -1)):
        result |= np.roll(mask, shift, axis)
    return result


def masked_slopes(heights: np.ndarray, mask: np.ndarray) -> np.ndarray:
    values = heights.astype(np.int16)
    slope = np.zeros(values.shape, np.int16)
    for axis, shift in ((0, 1), (0, -1), (1, 1), (1, -1)):
        neighbour = np.roll(values, shift, axis)
        inside = np.roll(mask, shift, axis)
        slope = np.maximum(slope, np.where(inside, np.abs(values - neighbour), 0))
    return np.where(mask, slope, 0)


def ellipse_mask(
    shape: tuple[int, int], zones: Sequence[tuple[int, int, float, float]]
) -> np.ndarray:
    result = np.zeros(shape, bool)
    for cx, cy, rx, ry in zones:
        y0 = int(cy - ry - 1)
        x0 = int(cx - rx - 1)
        gy, gx = np.mgrid[y0 : int(cy + ry + 2), x0 : int(cx + rx + 2)]
        inside = ((gx - cx) / rx) ** 2 + ((gy - cy) / ry) ** 2 <= 1.0
        result[y0 : y0 + inside.shape[0], x0 : x0 + inside.shape[1]] |= inside
    return result


def palette_indices(palette: dict[int, str], *terrain_types: str) -> list[int]:
    return [index for index, value in palette.items() if value in terrain_types]


def classify_march_terrain(
    pixels: np.ndarray,
    heights: np.ndarray,
    march: np.ndarray,
    relief: np.ndarray,
    fen: np.ndarray,
    forest_zone: np.ndarray,
    palette: dict[int, str],
) -> np.ndarray:
    """Derive march and southern terrain from relief and the authored zones.

    The northern thresholds apply, so the ridge stays continuous across the
    northern landscape border. Existing forest and lowland textures survive
    on flat ground; painted relief without matching height becomes plains.
    """
    land = march & ~np.isin(pixels, palette_indices(palette, "ocean", "lakes"))
    urban = land & (pixels == URBAN_PALETTE)
    marsh = land & ~urban & (fen | (pixels == MARSH_PALETTE))
    classifiable = land & ~urban & ~marsh
    slope = masked_slopes(heights, relief)
    mountains = classifiable & ((heights >= 158) | (slope >= 12))
    first = classifiable & ~mountains & neighbours_of(mountains)
    second = (
        classifiable
        & ~mountains
        & ~first
        & neighbours_of(first)
        & ((heights >= 125) | (slope >= 4))
    )
    hills = classifiable & ~mountains & (first | second | (heights >= 132) | (slope >= 6))
    flat = classifiable & ~mountains & ~hills
    old_forest = np.isin(pixels, palette_indices(palette, "forest"))
    old_relief = np.isin(pixels, palette_indices(palette, "hills", "mountain"))
    result = pixels.copy()
    result[marsh] = MARSH_PALETTE
    result[mountains] = MOUNTAIN_PALETTE
    result[hills] = HILLS_PALETTE
    result[flat & forest_zone & ~old_forest] = FOREST_PALETTE
    result[flat & ~forest_zone & old_relief] = PLAINS_PALETTE
    return result


def _snap_river_point(point: tuple[int, int], allowed: np.ndarray) -> tuple[int, int]:
    x, y = point
    for radius in range(12):
        window = allowed[y - radius : y + radius + 1, x - radius : x + radius + 1]
        ys, xs = np.nonzero(window)
        if len(xs):
            order = np.argsort((xs - radius) ** 2 + (ys - radius) ** 2, kind="stable")
            return (x - radius + int(xs[order[0]]), y - radius + int(ys[order[0]]))
    raise RuntimeError(f"river waypoint {point} has no province-border pixel nearby")


def _route_river(
    start: tuple[int, int],
    goals: list[tuple[int, int]],
    allowed: np.ndarray,
    heights: np.ndarray,
    packed: np.ndarray,
) -> list[tuple[int, int]]:
    """Cheapest 4-connected path along one side of each border.

    Climbing costs extra so rivers run downhill. Stepping onto the pixels of
    another province is expensive, so the course does not weave across the
    border line it follows.
    """
    goal_set = set(goals)
    gx = sum(x for x, _ in goals) / len(goals)
    gy = sum(y for _, y in goals) / len(goals)
    frontier = [(0.0, 0.0, start)]
    previous: dict[tuple[int, int], tuple[int, int] | None] = {start: None}
    best = {start: 0.0}
    while frontier:
        _estimate, spent, current = heapq.heappop(frontier)
        if current in goal_set:
            path = []
            step: tuple[int, int] | None = current
            while step is not None:
                path.append(step)
                step = previous[step]
            return path[::-1]
        if spent > best[current]:
            continue
        x, y = current
        for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if not allowed[ny, nx]:
                continue
            climb = max(0, int(heights[ny, nx]) - int(heights[y, x]))
            switch = RIVER_SIDE_SWITCH_COST if packed[ny, nx] != packed[y, x] else 0.0
            value = spent + 1.0 + 0.8 * climb + switch
            if value < best.get((nx, ny), float("inf")):
                best[(nx, ny)] = value
                previous[(nx, ny)] = current
                heapq.heappush(
                    frontier, (value + abs(nx - gx) + abs(ny - gy), value, (nx, ny))
                )
    raise RuntimeError(f"river from {start} cannot reach its next waypoint along borders")


def _prune_river_loops(path: list[tuple[int, int]]) -> list[tuple[int, int]]:
    """Cut joined segments where the river would touch its own earlier course."""
    result: list[tuple[int, int]] = []
    position: dict[tuple[int, int], int] = {}
    for point in path:
        x, y = point
        touching = [
            position[neighbour]
            for neighbour in ((x, y), (x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1))
            if neighbour in position and position[neighbour] < len(result) - 1
        ]
        if touching:
            del result[min(touching) + 1 :]
            position = {value: index for index, value in enumerate(result)}
            if point in position:
                continue
        position[point] = len(result)
        result.append(point)
    return result


def river_width_palette(fraction: float, length: int) -> int:
    if fraction < 0.35:
        return 3
    if fraction < 0.7:
        return 4
    if length >= 150 and fraction >= 0.8:
        return 7
    return 6


def province_borders(packed: np.ndarray) -> np.ndarray:
    border = np.zeros(packed.shape, bool)
    for axis, shift in ((0, 1), (0, -1), (1, 1), (1, -1)):
        border |= np.roll(packed, shift, axis) != packed
    return border


def route_rivers(
    rivers: np.ndarray,
    packed: np.ndarray,
    relief: np.ndarray,
    authored: np.ndarray,
    water: np.ndarray,
    heights: np.ndarray,
) -> tuple[np.ndarray, list[list[tuple[int, int]]]]:
    """Redraw this builder's rivers on province borders inside the relief."""
    owned = relief & ~authored
    result = rivers.copy()
    result[owned & (result < RIVER_SEA_PALETTE)] = RIVER_LAND_PALETTE
    foreign_river = (result < RIVER_SEA_PALETTE) & ~owned
    blocked = foreign_river.copy()
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            blocked |= np.roll(np.roll(foreign_river, dy, 0), dx, 1)
    coast = owned & neighbours_of(water)
    border = province_borders(packed)
    paths: list[list[tuple[int, int]]] = []
    for course in RIVER_COURSES:
        allowed = owned & border & ~blocked & ~coast
        mouth = owned & ~blocked & coast
        path = [_snap_river_point(course[0], allowed)]
        for waypoint in course[1:-1]:
            target = _snap_river_point(waypoint, allowed)
            path.extend(_route_river(path[-1], [target], allowed, heights, packed)[1:])
        mx, my = course[-1]
        reach = RIVER_MOUTH_RADIUS
        window = mouth[my - reach : my + reach + 1, mx - reach : mx + reach + 1]
        goals = [
            (mx - reach + int(x), my - reach + int(y)) for y, x in zip(*np.nonzero(window))
        ]
        if not goals:
            raise RuntimeError(f"river mouth {course[-1]} has no coastal border pixel")
        path.extend(_route_river(path[-1], goals, allowed | mouth, heights, packed)[1:])
        path = _prune_river_loops(path)
        for index, (x, y) in enumerate(path):
            result[y, x] = (
                RIVER_SOURCE_PALETTE
                if index == 0
                else river_width_palette(index / len(path), len(path))
            )
            blocked[y - 1 : y + 2, x - 1 : x + 2] = True
        paths.append(path)
    return result, paths


def relief_unit_anchors(
    original: bytes, provinces: frozenset[int], heights: np.ndarray
) -> bytes:
    """Rest every unit anchor of a relief province on the generated surface."""
    text = original.decode("utf-8")
    newline = "\r\n" if "\r\n" in text else "\n"
    map_height = heights.shape[0]
    result = []
    for line in text.splitlines():
        row = line.split(";")
        if len(row) >= 5 and row[0].isdigit() and int(row[0]) in provinces:
            x = round(float(row[2]))
            y = map_height - 1 - round(float(row[4]))
            row[3] = f"{heights[y, x] / 10:.2f}"
            line = ";".join(row)
        result.append(line)
    return (newline.join(result) + newline).encode("utf-8")


def _grow_compact_region(
    candidates: np.ndarray, anchor: tuple[int, int], size: int
) -> np.ndarray:
    """Take the ``size`` connected pixels nearest to ``anchor`` (y, x)."""
    selected = np.zeros(candidates.shape, bool)
    ay, ax = anchor
    frontier = [(0.0, ay, ax)]
    seen = {(ay, ax)}
    count = 0
    while frontier and count < size:
        _distance, y, x = heapq.heappop(frontier)
        selected[y, x] = True
        count += 1
        for ny, nx in ((y + 1, x), (y - 1, x), (y, x + 1), (y, x - 1)):
            if (ny, nx) in seen or not candidates[ny, nx]:
                continue
            seen.add((ny, nx))
            heapq.heappush(frontier, ((ny - ay) ** 2 + (nx - ax) ** 2, ny, nx))
    return selected


def _geodesic_partition(region: np.ndarray, seeds: list[tuple[int, int]]) -> np.ndarray:
    """Assign region pixels to the nearest seed along 4-connected paths."""
    owner = np.full(region.shape, -1, np.int32)
    queue: deque[tuple[int, int]] = deque()
    for index, (y, x) in enumerate(seeds):
        owner[y, x] = index
        queue.append((y, x))
    while queue:
        y, x = queue.popleft()
        for ny, nx in ((y + 1, x), (y - 1, x), (y, x + 1), (y, x - 1)):
            if region[ny, nx] and owner[ny, nx] < 0:
                owner[ny, nx] = owner[y, x]
                queue.append((ny, nx))
    return owner


def _nearest_member(region: np.ndarray, y: float, x: float) -> tuple[int, int]:
    ys, xs = np.nonzero(region)
    index = int(np.argmin((ys - y) ** 2 + (xs - x) ** 2))
    return int(ys[index]), int(xs[index])


def compact_partition(region: np.ndarray, parts: int) -> np.ndarray:
    """Split a region into compact connected parts (geodesic k-means).

    Detached pieces outside the largest component stay unassigned (-1).
    """
    from scipy.ndimage import label as connected_components

    pieces, count = connected_components(region)
    if count > 1:
        sizes = np.bincount(pieces.ravel())
        sizes[0] = 0
        region = pieces == int(np.argmax(sizes))
    ys, xs = np.nonzero(region)
    cy, cx = ys.mean(), xs.mean()
    first = int(np.argmax((ys - cy) ** 2 + (xs - cx) ** 2))
    seeds = [(int(ys[first]), int(xs[first]))]
    while len(seeds) < parts:
        distance = np.min(
            [(ys - sy) ** 2 + (xs - sx) ** 2 for sy, sx in seeds], axis=0
        )
        index = int(np.argmax(distance))
        seeds.append((int(ys[index]), int(xs[index])))
    owner = _geodesic_partition(region, seeds)
    for _iteration in range(8):
        moved = []
        for index in range(parts):
            part = owner == index
            py, px = np.nonzero(part)
            moved.append(_nearest_member(part, py.mean(), px.mean()))
        if moved == seeds:
            break
        seeds = moved
        owner = _geodesic_partition(region, seeds)
    return owner


def _relabel_fragments(labels: np.ndarray, editable: np.ndarray) -> None:
    """Merge detached pieces of every province into their main neighbour."""
    from scipy.ndimage import label as connected_components

    for value in np.unique(labels[editable]):
        mask = labels == value
        pieces, count = connected_components(mask)
        if count <= 1:
            continue
        sizes = np.bincount(pieces.ravel())
        sizes[0] = 0
        keep = int(np.argmax(sizes))
        for piece in range(1, count + 1):
            if piece == keep:
                continue
            fragment = pieces == piece
            ring = neighbours_of(fragment) & ~fragment & editable & ~mask
            choices = labels[ring]
            if len(choices):
                labels[fragment] = int(np.bincount(choices).argmax())


def smooth_province_labels(
    labels: np.ndarray, editable: np.ndarray, locked: np.ndarray, sigma: float = 1.6
) -> np.ndarray:
    """Round province borders by an iterated Gaussian majority vote.

    Only editable pixels change and they only take editable province IDs, so
    coastlines and foreign borders stay exact. Locked provinces keep their
    pixels; the vote repeats until it is stable.
    """
    from scipy.ndimage import gaussian_filter

    result = labels.copy()
    values = [int(value) for value in np.unique(result[editable])]
    original_area = {value: int((result == value).sum()) for value in values}
    for _iteration in range(24):
        best = np.full(result.shape, -1.0)
        choice = result.copy()
        for value in values:
            mask = result == value
            ys, xs = np.nonzero(mask)
            y0 = max(0, ys.min() - 6)
            y1 = min(result.shape[0], ys.max() + 7)
            x0 = max(0, xs.min() - 6)
            x1 = min(result.shape[1], xs.max() + 7)
            score = gaussian_filter(mask[y0:y1, x0:x1].astype(float), sigma)
            # Ties keep the current owner.
            score += 1e-6 * mask[y0:y1, x0:x1]
            window = best[y0:y1, x0:x1]
            better = score > window
            window[better] = score[better]
            choice[y0:y1, x0:x1][better] = value
        changed = editable & ~locked & ~np.isin(choice, list(np.unique(result[locked])))
        changed &= choice != result
        if not changed.any():
            break
        previous = result.copy()
        result[changed] = choice[changed]
        _relabel_fragments(result, editable)
        # A province squeezed below 70% of its area is restored and frozen.
        for value in values:
            if (result == value).sum() < 0.7 * original_area[value]:
                restored = previous == value
                result[restored] = value
                locked = locked | restored
        _relabel_fragments(result, editable)
    return result


def remove_four_province_corners(labels: np.ndarray, editable: np.ndarray) -> None:
    """Give one pixel of every four-province corner to a neighbour's province.

    HOI4 rejects a point where four provinces meet diagonally.
    """
    while True:
        a = labels[:-1, :-1]
        b = labels[:-1, 1:]
        c = labels[1:, :-1]
        d = labels[1:, 1:]
        corners = (a != b) & (a != c) & (a != d) & (b != c) & (b != d) & (c != d)
        found = np.argwhere(corners)
        if not len(found):
            return
        for y, x in found:
            for dy, dx, ny, nx in (
                (0, 0, 0, 1),
                (0, 1, 0, 0),
                (1, 0, 1, 1),
                (1, 1, 1, 0),
                (0, 0, 1, 0),
                (1, 0, 0, 0),
                (0, 1, 1, 1),
                (1, 1, 0, 1),
            ):
                if editable[y + dy, x + dx] and editable[y + ny, x + nx]:
                    labels[y + dy, x + dx] = labels[y + ny, x + nx]
                    break
            else:
                raise RuntimeError(f"four-province corner at {(x, y)} has no editable pixel")
        _relabel_fragments(labels, editable)


def province_colour(province_id: int, used: set[tuple[int, int, int]]) -> tuple[int, int, int]:
    salt = 0
    while True:
        value = stable_unit_hash(province_id, 7919, salt)
        packed = int(value * 0xFFFFFF) | 0x101010
        colour = ((packed >> 16) & 255, (packed >> 8) & 255, packed & 255)
        if colour not in used:
            used.add(colour)
            return colour
        salt += 1


def plan_province_geometry() -> None:
    """Write the reviewed IVN mainland province geometry and its manifest.

    Victory-point cities become whole urban provinces: small city provinces
    are kept whole, larger ones yield a compact city and rural sectors. Giant
    or ragged provinces are split, then every internal border is smoothed.
    The result is stored as data so the map pass only stamps it.
    """
    from tools.builders import build_adiscord_new_states as states

    rows = [
        line.split(";")
        for line in DEFINITION_PATH.read_text(encoding="utf-8-sig").splitlines()
        if line[:1].isdigit()
    ]
    colours = {int(row[0]): (int(row[1]), int(row[2]), int(row[3])) for row in rows}
    used = set(colours.values())
    next_id = max(colours) + 1
    sea = {int(row[0]) for row in rows if row[4] != "land"}

    state_by_province = {
        province: state_id
        for state_id in IVN_STATE_IDS
        for province in states.IVANLAND_OVERHAUL_PROVINCES[state_id]
    }
    scoped = frozenset(state_by_province)
    with Image.open(PROVINCES_PATH) as source:
        province_rgb = np.asarray(source.convert("RGB"))
    with Image.open(TERRAIN_PATH) as source:
        terrain = np.asarray(source)
    packed = packed_rgb(province_rgb)
    lookup = {
        (red << 16) | (green << 8) | blue: province
        for province, (red, green, blue) in colours.items()
    }
    scope = province_mask(packed, colours, scoped)
    ys, xs = np.nonzero(scope)
    y0, y1 = int(ys.min()) - 8, int(ys.max()) + 9
    x0, x1 = int(xs.min()) - 8, int(xs.max()) + 9
    crop = (slice(y0, y1), slice(x0, x1))
    keys = packed[crop]
    labels = np.zeros(keys.shape, np.int32)
    for key in np.unique(keys):
        labels[keys == key] = lookup.get(int(key), 0)
    editable = np.isin(labels, list(scoped))
    water = np.isin(labels, list(sea))

    victory_points = {
        province: value
        for state_id, points in states.IVANLAND_SETTLEMENT_VICTORY_POINTS.items()
        if state_id in IVN_STATE_IDS
        for province, value in points
    }
    entries: list[dict[str, object]] = []
    cities: dict[int, int] = {}

    def new_province(parent: int, kind: str) -> int:
        nonlocal next_id
        province = next_id
        next_id += 1
        state_by_province[province] = state_by_province[parent]
        entries.append(
            {
                "province": province,
                "parent": parent,
                "state": state_by_province[parent],
                "kind": kind,
                "rgb": list(province_colour(province, used)),
            }
        )
        return province

    for parent in sorted(victory_points):
        region = labels == parent
        area = int(region.sum())
        if area <= CITY_WHOLE_PROVINCE_PIXELS:
            cities[parent] = parent
            continue
        urban = region & (terrain[crop] == URBAN_PALETTE)
        anchor_source = urban if urban.sum() >= 6 else region
        py, px = np.nonzero(anchor_source)
        anchor = _nearest_member(region & ~neighbours_of(~region), py.mean(), px.mean())
        city_pixels = _grow_compact_region(region & ~water, anchor, CITY_PIXELS)
        city = new_province(parent, "city")
        labels[city_pixels] = city
        cities[parent] = city
        ring = labels == parent
        sectors = max(2, round(int(ring.sum()) / SECTOR_PIXELS))
        owner = compact_partition(ring, sectors)
        keep = int(np.bincount(owner[owner >= 0]).argmax())
        for index in range(sectors):
            if index != keep:
                labels[owner == index] = new_province(parent, "sector")

    for parent in sorted(int(value) for value in np.unique(labels[editable])):
        if parent in cities.values():
            continue
        region = labels == parent
        area = int(region.sum())
        ry, rx = np.nonzero(region)
        sub = region[ry.min() - 1 : ry.max() + 2, rx.min() - 1 : rx.max() + 2]
        perimeter = int((sub[:, 1:] != sub[:, :-1]).sum() + (sub[1:, :] != sub[:-1, :]).sum())
        compactness = 4 * pi * area / perimeter**2
        if area <= SPLIT_PIXELS and not (compactness < 0.3 and area > 200):
            continue
        parts = max(2, round(area / SECTOR_PIXELS))
        owner = compact_partition(region, parts)
        keep = int(np.bincount(owner[owner >= 0]).argmax())
        for index in range(parts):
            if index != keep:
                labels[owner == index] = new_province(parent, "split")

    editable = labels > 0
    editable &= ~water & np.isin(
        labels, list(scoped | {int(entry["province"]) for entry in entries})
    )
    # Cities and very small provinces keep their exact outline.
    small = [
        int(value)
        for value in np.unique(labels[editable])
        if (labels == value).sum() < LOCKED_PROVINCE_PIXELS
    ]
    locked = np.isin(labels, list(set(cities.values()) | set(small)))
    labels = smooth_province_labels(labels, editable, locked)
    remove_four_province_corners(labels, editable & ~locked)

    palette = {province: colour for province, colour in colours.items()}
    palette.update({int(entry["province"]): tuple(entry["rgb"]) for entry in entries})
    image = np.zeros((*labels.shape, 4), np.uint8)
    for value in np.unique(labels[editable]):
        mask = editable & (labels == value)
        image[mask, :3] = palette[int(value)]
        image[mask, 3] = 255
    Image.fromarray(image).save(PROVINCE_GEOMETRY_PATH, optimize=True)
    manifest = {
        "schema": 1,
        "origin": [x0, y0],
        "provinces": entries,
        "cities": {str(parent): city for parent, city in sorted(cities.items())},
    }
    PROVINCE_MANIFEST_PATH.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


RAILWAYS_PATH = ROOT / "map/railways.txt"


@dataclass(frozen=True)
class ProvinceGeometry:
    provinces: bytes
    definition: bytes
    unitstacks: bytes
    railways: bytes
    issues: tuple[str, ...]


def province_adjacency(labels: np.ndarray) -> dict[int, set[int]]:
    adjacency: dict[int, set[int]] = {}
    for first, second in ((labels[:, 1:], labels[:, :-1]), (labels[1:, :], labels[:-1, :])):
        differs = first != second
        for a, b in zip(first[differs].tolist(), second[differs].tolist()):
            adjacency.setdefault(a, set()).add(b)
            adjacency.setdefault(b, set()).add(a)
    return adjacency


def _shortest_province_path(
    start: int, goal: int, adjacency: dict[int, set[int]], allowed: frozenset[int]
) -> list[int]:
    previous = {start: start}
    queue = deque([start])
    while queue:
        current = queue.popleft()
        if current == goal:
            break
        # Cities first, so repaired lines pass through them.
        for neighbour in sorted(
            adjacency.get(current, ()), key=lambda value: (value not in CITY_PROVINCES, value)
        ):
            if neighbour in allowed and neighbour not in previous:
                previous[neighbour] = current
                queue.append(neighbour)
    if goal not in previous:
        raise RuntimeError(f"railway {start}-{goal}: no IVN province path")
    path = [goal]
    while path[-1] != start:
        path.append(previous[path[-1]])
    return path[::-1]


def repair_railways(
    original: bytes, adjacency: dict[int, set[int]], scoped: frozenset[int]
) -> bytes:
    """Route IVN railway segments through the city provinces and close gaps."""
    text = original.decode("utf-8-sig")
    newline = "\r\n" if "\r\n" in text else "\n"
    cities = {
        int(parent): int(city)
        for parent, city in PROVINCE_MANIFEST["cities"].items()
        if int(parent) != int(city)
    }
    lines = []
    for line in text.splitlines():
        fields = line.split()
        if len(fields) < 3:
            lines.append(line)
            continue
        chain = [cities.get(int(value), int(value)) for value in fields[2:]]
        repaired = chain[:1]
        for province in chain[1:]:
            previous = repaired[-1]
            if province in adjacency.get(previous, ()) or not (
                previous in scoped and province in scoped
            ):
                repaired.append(province)
            else:
                repaired.extend(
                    _shortest_province_path(previous, province, adjacency, scoped)[1:]
                )
        updated = f"{fields[0]} {len(repaired)} " + " ".join(map(str, repaired)) + " "
        lines.append(updated if repaired != [int(value) for value in fields[2:]] else line)
    return (newline.join(lines) + newline).encode("utf-8")


def _definition_rows() -> tuple[list[list[str]], str, bytes]:
    raw = DEFINITION_PATH.read_bytes()
    text = raw.decode("utf-8-sig")
    newline = "\r\n" if "\r\n" in text else "\n"
    bom = b"\xef\xbb\xbf" if raw.startswith(b"\xef\xbb\xbf") else b""
    return [line.split(";") for line in text.splitlines()], newline, bom


def _snap_anchor(mask: np.ndarray, x: float, y: float) -> tuple[int, int]:
    row = int(round(y))
    column = int(round(x))
    if 0 <= row < mask.shape[0] and 0 <= column < mask.shape[1] and mask[row, column]:
        return column, row
    sy, sx = _nearest_member(mask, y, x)
    return sx, sy


def expected_province_geometry() -> ProvinceGeometry:
    """Stamp the reviewed IVN province geometry and register its provinces."""
    rows, newline, bom = _definition_rows()
    by_id = {int(row[0]): row for row in rows if row[0].isdigit()}
    entries = sorted(PROVINCE_MANIFEST["provinces"], key=lambda entry: entry["province"])
    issues: list[str] = []
    for entry in entries:
        province = int(entry["province"])
        row = by_id.get(province)
        if row is None:
            if province != max(by_id) + 1:
                raise RuntimeError(f"province {province}: non-contiguous IVN province ID")
            parent = by_id[int(entry["parent"])]
            row = [str(province), *map(str, entry["rgb"]), "land", "false", parent[6], parent[7]]
            rows.append(row)
            by_id[province] = row
        elif list(map(int, row[1:4])) != list(entry["rgb"]):
            raise RuntimeError(f"province {province}: ID is occupied by another colour")

    colours = {province: tuple(map(int, row[1:4])) for province, row in by_id.items()}
    scoped = province_ids_for_states(IVN_STATE_IDS) | {
        int(entry["province"]) for entry in entries
    }
    with Image.open(PROVINCES_PATH) as source:
        province_rgb = np.array(source.convert("RGB"))
    with Image.open(PROVINCE_GEOMETRY_PATH) as source:
        geometry = np.asarray(source.convert("RGBA"))
    x0, y0 = PROVINCE_MANIFEST["origin"]
    height, width = geometry.shape[:2]
    region = province_rgb[y0 : y0 + height, x0 : x0 + width]
    stamped = geometry[..., 3] > 0
    allowed = province_mask(packed_rgb(region), colours, frozenset(scoped))
    if (stamped & ~allowed).any():
        raise RuntimeError("IVN province geometry would overwrite land outside its scope")
    region[stamped] = geometry[..., :3][stamped]
    lookup = {
        (red << 16) | (green << 8) | blue: province
        for province, (red, green, blue) in colours.items()
    }
    keys = packed_rgb(region)
    labels = np.zeros(keys.shape, np.int32)
    for key in np.unique(keys):
        labels[keys == key] = lookup.get(int(key), 0)
    sea_ids = [province for province, row in by_id.items() if row[4] == "sea"]
    coast = neighbours_of(np.isin(labels, sea_ids))
    masks = {province: labels == province for province in scoped}
    for province in sorted(scoped):
        if not masks[province].any():
            raise RuntimeError(f"province {province}: empty IVN geometry")
        by_id[province][5] = "true" if (masks[province] & coast).any() else "false"

    stack_text = UNITSTACKS_PATH.read_bytes().decode("utf-8")
    stack_newline = "\r\n" if "\r\n" in stack_text else "\n"
    stacks = [line.split(";") for line in stack_text.splitlines()]
    parents = {int(entry["province"]): int(entry["parent"]) for entry in entries}
    templates = {parent: [row for row in stacks if int(row[0]) == parent] for parent in set(parents.values())}
    existing = {int(row[0]) for row in stacks}
    with Image.open(HEIGHTMAP_PATH) as source:
        heights = np.asarray(source)
    map_height = province_rgb.shape[0]

    def place(row: list[str], province: int, x: float, y: float) -> None:
        sx, sy = _snap_anchor(masks[province], x - x0, y - y0)
        row[2] = f"{sx + x0:.2f}"
        row[3] = f"{heights[sy + y0, sx + x0] / 10:.2f}"
        row[4] = f"{map_height - 1 - (sy + y0):.2f}"

    for row in stacks:
        province = int(row[0])
        if province in masks:
            x = float(row[2])
            y = map_height - 1 - float(row[4])
            inside = masks[province]
            column = int(round(x)) - x0
            line = int(round(y)) - y0
            if not (0 <= line < inside.shape[0] and 0 <= column < inside.shape[1] and inside[line, column]):
                place(row, province, x, y)
    for province, parent in sorted(parents.items()):
        if province in existing:
            continue
        template = templates[parent]
        if not template:
            raise RuntimeError(f"province {parent}: no unit anchors to copy")
        ys, xs = np.nonzero(masks[province])
        cx, cy = xs.mean() + x0, ys.mean() + y0
        origin_x = float(template[0][2])
        origin_y = map_height - 1 - float(template[0][4])
        for source_row in template:
            row = source_row.copy()
            row[0] = str(province)
            place(
                row,
                province,
                cx + float(source_row[2]) - origin_x,
                cy + (map_height - 1 - float(source_row[4])) - origin_y,
            )
            stacks.append(row)

    railways = repair_railways(
        RAILWAYS_PATH.read_bytes(), province_adjacency(labels), frozenset(scoped)
    )
    encoded = BytesIO()
    Image.fromarray(province_rgb).save(encoded, format="BMP")
    definition = newline.join(";".join(row) for row in rows) + newline
    unitstacks = stack_newline.join(";".join(row) for row in stacks) + stack_newline
    return ProvinceGeometry(
        encoded.getvalue(),
        bom + definition.encode("utf-8"),
        unitstacks.encode("utf-8"),
        railways,
        tuple(issues),
    )


def province_geometry_issues() -> list[str]:
    expected_geometry = expected_province_geometry()
    issues = list(expected_geometry.issues)
    with Image.open(PROVINCES_PATH) as current, Image.open(
        BytesIO(expected_geometry.provinces)
    ) as planned:
        if not np.array_equal(
            np.asarray(current.convert("RGB")), np.asarray(planned.convert("RGB"))
        ):
            issues.append("map/provinces.bmp: IVN province geometry drifted")
    current_rows = DEFINITION_PATH.read_bytes().decode("utf-8-sig").splitlines()
    planned_rows = expected_geometry.definition.decode("utf-8-sig").splitlines()
    for before, after in zip_longest(current_rows, planned_rows):
        if before is None or after is None or before.split(";")[:6] != after.split(";")[:6]:
            issues.append("map/definition.csv: IVN province rows drifted")
            break
    stacks = UNITSTACKS_PATH.read_bytes().decode("utf-8").splitlines()
    planned_stacks = expected_geometry.unitstacks.decode("utf-8").splitlines()
    if len(stacks) != len(planned_stacks) or any(
        before.split(";")[:3] + before.split(";")[4:]
        != after.split(";")[:3] + after.split(";")[4:]
        for before, after in zip(stacks, planned_stacks)
    ):
        issues.append("map/unitstacks.txt: IVN unit anchors drifted")
    if RAILWAYS_PATH.read_bytes() != expected_geometry.railways:
        issues.append("map/railways.txt: IVN railway segments are not adjacent")
    return issues


def apply_province_geometry() -> None:
    expected_geometry = expected_province_geometry()
    PROVINCES_PATH.write_bytes(expected_geometry.provinces)
    DEFINITION_PATH.write_bytes(expected_geometry.definition)
    UNITSTACKS_PATH.write_bytes(expected_geometry.unitstacks)
    RAILWAYS_PATH.write_bytes(expected_geometry.railways)


def river_issues(
    rivers: np.ndarray,
    paths: list[list[tuple[int, int]]],
    packed: np.ndarray,
    water: np.ndarray,
) -> list[str]:
    border = province_borders(packed)
    issues = []
    for number, path in enumerate(paths, start=1):
        cells = set(path)
        if rivers[path[0][1], path[0][0]] != RIVER_SOURCE_PALETTE:
            issues.append(f"river {number}: source pixel is not palette 0")
        off_border = sum(not border[y, x] for x, y in path)
        if off_border:
            issues.append(f"river {number}: {off_border} pixels cross province interiors")
        for (ax, ay), (bx, by) in zip(path, path[1:]):
            if abs(ax - bx) + abs(ay - by) != 1:
                issues.append(f"river {number}: course is not 4-connected at {(ax, ay)}")
                break
        branching = [
            (x, y)
            for x, y in path
            if sum((n in cells) for n in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1))) > 2
        ]
        if branching:
            issues.append(f"river {number}: branches at {branching[:3]}")
        mx, my = path[-1]
        if not water[my - 1 : my + 2, mx - 1 : mx + 2].any():
            issues.append(f"river {number}: mouth {(mx, my)} does not reach the sea")
    return issues


def _build_expected() -> GeographyOutputs:
    lines, newline, bom, province_colors, declared = definition_contract()
    palette = palette_types()
    color_to_id = {color: province_id for province_id, color in province_colors.items()}
    if len(color_to_id) != len(province_colors):
        raise RuntimeError("definition.csv: duplicate RGB inside IVN/IIA scope")

    with (
        Image.open(BytesIO(TERRAIN_PATH.read_bytes())) as terrain_source,
        Image.open(BytesIO(CITIES_PATH.read_bytes())) as cities_source,
        Image.open(BytesIO(PROVINCES_PATH.read_bytes())) as provinces_source,
    ):
        if terrain_source.mode != "P" or terrain_source.size != provinces_source.size:
            raise RuntimeError(
                "terrain.bmp must be paletted and match provinces.bmp dimensions"
            )
        if cities_source.mode != "P" or cities_source.size != terrain_source.size:
            raise RuntimeError(
                "cities.bmp must be paletted and match terrain.bmp dimensions"
            )
        terrain_original = terrain_source.copy()
        terrain_pixels = bytearray(terrain_source.get_flattened_data())
        city_pixels = bytearray(cities_source.get_flattened_data())
        province_rgb = np.asarray(provinces_source.convert("RGB"))
        province_bytes = province_rgb.tobytes()
        masks = landscape_masks(provinces_source, province_colors)
    water = water_mask(province_rgb, water_colours(DEFINITION_PATH))
    shore_blocked = urban_blocked(water, province_rgb, DEFINITION_PATH).reshape(-1)
    packed = packed_rgb(province_rgb)
    relief = province_mask(
        packed, province_colors, relief_province_ids(RELIEF_STATE_IDS)
    )
    march = province_mask(
        packed, province_colors, relief_province_ids(MARCH_RELIEF_STATE_IDS)
    )
    authored_rivers = province_mask(packed, province_colors, AUTHORED_RIVER_PROVINCES)

    with Image.open(BytesIO(HEIGHTMAP_PATH.read_bytes())) as height_source:
        if height_source.mode != "L" or height_source.size != terrain_original.size:
            raise RuntimeError(
                "heightmap.bmp must use mode L and match provinces.bmp dimensions"
            )
        heightmap = render_heightmap(height_source, masks.island, masks.island_bbox)
    relief_heights, fen = render_relief_heights(np.asarray(heightmap), relief, water)
    heightmap = Image.fromarray(relief_heights)
    normal_scope = bytearray(
        (
            np.frombuffer(bytes(masks.island), dtype=np.uint8).reshape(relief.shape).astype(bool)
            | relief
        )
        .astype(np.uint8)
        .tobytes()
    )
    with Image.open(BytesIO(WORLD_NORMAL_PATH.read_bytes())) as normal_source:
        if normal_source.mode != "RGB":
            raise RuntimeError("world_normal.bmp must use mode RGB")
        world_normal = normal_from_height(heightmap, normal_source, normal_scope)

    province_by_pixel = array("H", [0]) * len(terrain_pixels)
    settlement_indices = {province_id: [] for province_id in SETTLEMENT_PROVINCES}
    for index in range(len(terrain_pixels)):
        color = tuple(province_bytes[index * 3 : index * 3 + 3])
        province_id = color_to_id.get(color)
        if province_id is None:
            continue
        province_by_pixel[index] = province_id
        if province_id in settlement_indices:
            settlement_indices[province_id].append(index)

    missing_settlements = sorted(SETTLEMENT_PROVINCES - province_colors.keys())
    if missing_settlements:
        raise RuntimeError(
            f"settlement provinces outside IVN/IIA scope: {missing_settlements}"
        )

    priority = {
        terrain_type: len(TERRAIN_PRIORITY) - rank
        for rank, terrain_type in enumerate(TERRAIN_PRIORITY)
    }
    # City meshes must not spill into the sea: settlements grow only from
    # pixels outside the shared shoreline clearance band.
    footprints = {
        province_id: (
            set(indices)
            if province_id in CITY_PROVINCES
            else compact_footprint(
                [index for index in indices if not shore_blocked[index]],
                terrain_original.width,
                province_id,
            )
        )
        for province_id, indices in settlement_indices.items()
    }
    old_urban = {
        province_id: {
            index for index in indices if terrain_pixels[index] == URBAN_PALETTE
        }
        for province_id, indices in settlement_indices.items()
    }
    working_pixels = bytearray(terrain_pixels)
    for province_id, indices in settlement_indices.items():
        nonurban = Counter(
            terrain_pixels[index]
            for index in indices
            if terrain_pixels[index] != URBAN_PALETTE
            and palette.get(terrain_pixels[index]) not in WATER_TYPES
        )
        base = (
            max(
                nonurban,
                key=lambda value: (
                    nonurban[value],
                    priority.get(palette.get(value, ""), 0),
                    -value,
                ),
            )
            if nonurban
            else PLAINS_PALETTE
        )
        for index in old_urban[province_id]:
            working_pixels[index] = base
        for index in footprints[province_id]:
            working_pixels[index] = URBAN_PALETTE
    # On the IVN mainland only city provinces are urban. Former settlement
    # footprints left in rural provinces return to the province's own biome.
    working_array = np.frombuffer(working_pixels, dtype=np.uint8).reshape(relief.shape)
    rural_urban = (
        relief
        & (working_array == URBAN_PALETTE)
        & ~province_mask(packed, province_colors, SETTLEMENT_PROVINCES)
    )
    if rural_urban.any():
        stale_ids = np.frombuffer(province_by_pixel, dtype=np.uint16).reshape(relief.shape)
        for province_id in np.unique(stale_ids[rural_urban]):
            inside = stale_ids == province_id
            biome = working_array[inside & (working_array != URBAN_PALETTE)]
            biome = biome[~np.isin(biome, list(WATER_PALETTES))]
            base = int(np.bincount(biome).argmax()) if len(biome) else PLAINS_PALETTE
            for index in np.flatnonzero(inside & rural_urban):
                working_pixels[index] = base
    # Clear the shoreline band before rendering as well, so neighbourhood-aware
    # rendering sees identical input on every pass.
    for index, province_id in enumerate(province_by_pixel):
        if (
            province_id
            and working_pixels[index] == URBAN_PALETTE
            and shore_blocked[index]
        ):
            working_pixels[index] = URBAN_FALLBACK_PALETTE
    working = terrain_original.copy()
    working.putdata(working_pixels)
    terrain = render_northern_terrain(
        working,
        heightmap,
        masks.north,
        masks.island,
        masks.state_by_pixel,
        footprints,
    )
    march_pixels = classify_march_terrain(
        np.asarray(terrain),
        relief_heights,
        march,
        relief,
        fen,
        ellipse_mask(relief.shape, FOREST_ZONES) & march,
        palette,
    )
    terrain.putdata(march_pixels.tobytes())
    generated_pixels = bytearray(terrain.get_flattened_data())
    shore_cleared: set[int] = set()
    for index, province_id in enumerate(province_by_pixel):
        if not province_id:
            continue
        if city_pixels[index] in CITY_PALETTE_INDICES:
            generated_pixels[index] = URBAN_PALETTE
        if (
            generated_pixels[index] == URBAN_PALETTE
            and shore_blocked[index]
        ):
            generated_pixels[index] = URBAN_FALLBACK_PALETTE
            shore_cleared.add(index)
    terrain.putdata(generated_pixels)

    counts = {province_id: Counter() for province_id in province_colors}
    for index, province_id in enumerate(province_by_pixel):
        if not province_id:
            continue
        terrain_type = palette.get(generated_pixels[index])
        if terrain_type is None:
            raise RuntimeError(
                f"province {province_id}: unknown graphical terrain palette {generated_pixels[index]}"
            )
        # The shoreline band is cosmetic clearance: in a province already
        # declared urban, its cleared pixels still count as city.
        if (
            shore_blocked[index]
            and generated_pixels[index] == URBAN_FALLBACK_PALETTE
            and declared.get(province_id) == "urban"
        ):
            terrain_type = "urban"
        if terrain_type not in WATER_TYPES:
            counts[province_id][terrain_type] += 1

    desired: dict[int, str] = {}
    for province_id, terrain_counts in counts.items():
        if not terrain_counts:
            raise RuntimeError(f"province {province_id}: no painted land terrain")
        desired[province_id] = max(
            terrain_counts,
            key=lambda terrain_type: (
                terrain_counts[terrain_type],
                priority.get(terrain_type, 0),
            ),
        )
    for province_id in SETTLEMENT_PROVINCES:
        desired[province_id] = "urban"

    with Image.open(BytesIO(TREES_PATH.read_bytes())) as tree_source:
        if tree_source.mode != "P" or tree_source.size != (1650, 600):
            raise RuntimeError("trees.bmp must remain paletted at 1650x600")
        tree_palette = tree_source.getpalette()
        tree_states = np.frombuffer(bytes(masks.state_by_pixel), dtype=np.uint16).copy()
        for state_id in sorted(MARCH_RELIEF_STATE_IDS):
            state_pixels = province_mask(
                packed, province_colors, relief_province_ids(frozenset({state_id}))
            )
            tree_states[state_pixels.reshape(-1)] = state_id
        trees, tree_counts, forbidden_trees, outside_tree_changes = (
            _render_trees_with_metrics(
                tree_source,
                terrain,
                array("H", tree_states.tobytes()),
                palette,
                tree_cells_blocked(water, tree_source.width, tree_source.height),
            )
        )
        if trees.getpalette() != tree_palette:
            raise RuntimeError("trees.bmp palette changed during generation")

    state_forest_counts: dict[int, list[int]] = {
        state_id: [0, 0] for state_id in NORTHERN_LANDSCAPE_STATE_IDS
    }
    mountain_pixels = 0
    hill_pixels = 0
    for index, state_id in enumerate(masks.state_by_pixel):
        if not state_id:
            continue
        terrain_type = palette[generated_pixels[index]]
        if terrain_type in WATER_TYPES or terrain_type == "urban":
            continue
        state_forest_counts[state_id][1] += 1
        if terrain_type == "forest":
            state_forest_counts[state_id][0] += 1
        if generated_pixels[index] == MOUNTAIN_PALETTE:
            mountain_pixels += 1
        elif generated_pixels[index] == HILLS_PALETTE:
            hill_pixels += 1
    island_forest = sum(
        state_forest_counts[state_id][0] for state_id in ISLAND_HEIGHT_STATE_IDS
    )
    island_land = sum(
        state_forest_counts[state_id][1] for state_id in ISLAND_HEIGHT_STATE_IDS
    )
    island_forest_share = island_forest / island_land
    mainland_forest_shares = {
        state_id: state_forest_counts[state_id][0] / state_forest_counts[state_id][1]
        for state_id in sorted(MAINLAND_FOREST_STATE_IDS)
    }
    tree_occupancy = {
        terrain_type: (
            tree_counts.get(terrain_type, (0, 0))[1]
            / tree_counts.get(terrain_type, (1, 0))[0]
        )
        for terrain_type in ("forest", "plains", "hills", "marsh")
    }

    coast_distances = distance_from_edge(masks.north, terrain.width, terrain.height)
    transition_violations = 0
    mountains = {
        index
        for index, included in enumerate(masks.north)
        if included and generated_pixels[index] == MOUNTAIN_PALETTE
    }
    for index in mountains:
        for neighbour in pixel_neighbours(index, terrain.width, len(generated_pixels)):
            if not masks.north[neighbour]:
                continue
            neighbour_value = generated_pixels[neighbour]
            if neighbour_value == URBAN_PALETTE or 0 <= coast_distances[neighbour] < 2:
                continue
            if neighbour_value not in (MOUNTAIN_PALETTE, HILLS_PALETTE):
                transition_violations += 1
    components_without_shoulders = 0
    remaining = set(mountains)
    while remaining:
        component = {remaining.pop()}
        frontier = list(component)
        while frontier:
            index = frontier.pop()
            connected = (
                set(pixel_neighbours(index, terrain.width, len(generated_pixels)))
                & remaining
            )
            remaining.difference_update(connected)
            component.update(connected)
            frontier.extend(connected)
        if not any(
            generated_pixels[neighbour] == HILLS_PALETTE
            for index in component
            for neighbour in pixel_neighbours(
                index, terrain.width, len(generated_pixels)
            )
        ):
            components_without_shoulders += 1

    relief_pixels = relief.reshape(-1)
    outside_terrain_changes = 0
    for index, (before, after) in enumerate(zip(terrain_pixels, generated_pixels)):
        if before == after or masks.north[index] or relief_pixels[index]:
            continue
        if index in shore_cleared and before == URBAN_PALETTE:
            continue
        province_id = province_by_pixel[index]
        if (
            province_id not in SETTLEMENT_PROVINCES
            or index not in old_urban[province_id] | footprints[province_id]
        ):
            outside_terrain_changes += 1
    metrics = CoverageMetrics(
        island_forest_share=island_forest_share,
        mainland_forest_shares=mainland_forest_shares,
        tree_occupancy=tree_occupancy,
        forbidden_tree_cells=forbidden_trees,
        terrain_changes_outside_scope=outside_terrain_changes,
        tree_changes_outside_scope=outside_tree_changes,
        mountain_pixels=mountain_pixels,
        hill_pixels=hill_pixels,
        mountain_transition_violations=transition_violations,
        mountain_components_without_shoulders=components_without_shoulders,
    )

    with Image.open(BytesIO(RIVERS_PATH.read_bytes())) as river_source:
        if river_source.mode != "P" or river_source.size != terrain.size:
            raise RuntimeError("rivers.bmp must be paletted and match terrain.bmp dimensions")
        river_pixels, river_paths = route_rivers(
            np.asarray(river_source),
            packed,
            relief,
            authored_rivers,
            water,
            relief_heights,
        )
        rivers = river_source.copy()
    rivers.putdata(river_pixels.tobytes())

    updated_lines = []
    for line in lines:
        fields = line.split(";")
        if len(fields) >= 7 and fields[0].isdigit() and int(fields[0]) in desired:
            fields[6] = desired[int(fields[0])]
            line = ";".join(fields)
        updated_lines.append(line)
    definition = newline.join(updated_lines)
    if lines:
        definition += newline
    return GeographyOutputs(
        terrain=terrain,
        definition=bom + definition.encode("utf-8"),
        heightmap=heightmap,
        world_normal=world_normal,
        trees=trees,
        rivers=rivers,
        unitstacks=relief_unit_anchors(
            UNITSTACKS_PATH.read_bytes(),
            relief_province_ids(RELIEF_STATE_IDS),
            relief_heights,
        ),
        river_issues=river_issues(river_pixels, river_paths, packed, water),
        desired=desired,
        counts=counts,
        footprints=footprints,
        metrics=metrics,
    )


_EXPECTED_SIGNATURE: tuple[tuple[int, int], ...] | None = None
_EXPECTED_OUTPUTS: GeographyOutputs | None = None


def expected() -> GeographyOutputs:
    global _EXPECTED_SIGNATURE, _EXPECTED_OUTPUTS
    input_paths = (
        TERRAIN_PATH,
        TREES_PATH,
        PROVINCES_PATH,
        DEFINITION_PATH,
        HEIGHTMAP_PATH,
        WORLD_NORMAL_PATH,
        RIVERS_PATH,
        UNITSTACKS_PATH,
        TERRAIN_CONFIG_PATH,
        *(state_path(state_id) for state_id in sorted(SCOPED_STATE_IDS)),
    )
    signature = tuple(
        (path.stat().st_mtime_ns, path.stat().st_size) for path in input_paths
    )
    if signature != _EXPECTED_SIGNATURE or _EXPECTED_OUTPUTS is None:
        _EXPECTED_OUTPUTS = _build_expected()
        _EXPECTED_SIGNATURE = signature
    return _EXPECTED_OUTPUTS


def coverage_issues(outputs: GeographyOutputs) -> list[str]:
    metrics = outputs.metrics
    issues: list[str] = []
    if not 0.25 <= metrics.island_forest_share <= 0.30:
        issues.append(
            f"island forest share {metrics.island_forest_share:.4f} is outside 0.25..0.30"
        )
    for state_id, share in metrics.mainland_forest_shares.items():
        if not 0.20 <= share <= 0.25:
            issues.append(
                f"state {state_id}: forest share {share:.4f} is outside 0.20..0.25"
            )
    occupancy = metrics.tree_occupancy
    for terrain_type, minimum, maximum in (
        ("forest", 0.50, 0.72),
        ("plains", 0.02, 0.07),
        ("hills", 0.01, 0.05),
    ):
        if not minimum <= occupancy[terrain_type] <= maximum:
            issues.append(
                f"{terrain_type} tree occupancy {occupancy[terrain_type]:.4f} "
                f"is outside {minimum:.2f}..{maximum:.2f}"
            )
    if occupancy["hills"] >= occupancy["plains"]:
        issues.append("hills tree occupancy is not lower than plains occupancy")
    if occupancy["hills"] > occupancy["forest"] / 5:
        issues.append("hills tree occupancy exceeds one fifth of forest occupancy")
    if metrics.forbidden_tree_cells:
        issues.append(
            f"map/trees.bmp: {metrics.forbidden_tree_cells} generated cells sample water, urban, or mountain"
        )
    if metrics.terrain_changes_outside_scope:
        issues.append(
            f"map/terrain.bmp: {metrics.terrain_changes_outside_scope} changes escape the north/settlement scope"
        )
    if metrics.tree_changes_outside_scope:
        issues.append(
            f"map/trees.bmp: {metrics.tree_changes_outside_scope} changes escape the approved low-resolution mask"
        )
    if metrics.mountain_transition_violations:
        issues.append(
            f"map/terrain.bmp: {metrics.mountain_transition_violations} interior mountain edges lack a hill shoulder"
        )
    if metrics.mountain_components_without_shoulders:
        issues.append(
            f"map/terrain.bmp: {metrics.mountain_components_without_shoulders} mountain components lack a hill shoulder"
        )
    return issues


def validate(outputs: GeographyOutputs | None = None) -> list[str]:
    outputs = outputs or expected()
    issues: list[str] = []
    with Image.open(BytesIO(TERRAIN_PATH.read_bytes())) as current:
        differences = sum(
            before != after
            for before, after in zip(
                current.get_flattened_data(), outputs.terrain.get_flattened_data()
            )
        )
    if differences:
        issues.append(f"map/terrain.bmp: {differences} northern terrain pixels drifted")
    with Image.open(BytesIO(HEIGHTMAP_PATH.read_bytes())) as current:
        differences = sum(
            before != after
            for before, after in zip(
                current.get_flattened_data(), outputs.heightmap.get_flattened_data()
            )
        )
    if differences:
        issues.append(f"map/heightmap.bmp: {differences} island height pixels drifted")
    with Image.open(BytesIO(WORLD_NORMAL_PATH.read_bytes())) as current:
        differences = sum(
            before != after
            for before, after in zip(
                current.get_flattened_data(), outputs.world_normal.get_flattened_data()
            )
        )
    if differences:
        issues.append(
            f"map/world_normal.bmp: {differences} island normal cells drifted"
        )
    with Image.open(BytesIO(TREES_PATH.read_bytes())) as current:
        if current.mode != "P" or current.size != (1650, 600):
            issues.append(
                f"map/trees.bmp: expected mode P at 1650x600, found {current.mode} at {current.size}"
            )
        if current.getpalette() != outputs.trees.getpalette():
            issues.append("map/trees.bmp: palette bytes drifted")
        differences = sum(
            before != after
            for before, after in zip(
                current.get_flattened_data(), outputs.trees.get_flattened_data()
            )
        )
    if differences:
        issues.append(f"map/trees.bmp: {differences} northern tree cells drifted")
    with Image.open(BytesIO(RIVERS_PATH.read_bytes())) as current:
        if current.getpalette() != outputs.rivers.getpalette():
            issues.append("map/rivers.bmp: palette bytes drifted")
        differences = sum(
            before != after
            for before, after in zip(
                current.get_flattened_data(), outputs.rivers.get_flattened_data()
            )
        )
    if differences:
        issues.append(f"map/rivers.bmp: {differences} IVN river pixels drifted")
    issues.extend(f"map/rivers.bmp: {issue}" for issue in outputs.river_issues)
    if UNITSTACKS_PATH.read_bytes() != outputs.unitstacks:
        issues.append("map/unitstacks.txt: IVN relief unit heights drifted")
    current_definition = DEFINITION_PATH.read_bytes().decode("utf-8-sig").splitlines()
    expected_definition = outputs.definition.decode("utf-8-sig").splitlines()
    definition_differences = sum(
        before != after
        for before, after in zip_longest(current_definition, expected_definition)
    )
    if definition_differences:
        issues.append(
            f"map/definition.csv: {definition_differences} IVN/IIA declared terrain rows drifted"
        )
    for province_id, footprint in outputs.footprints.items():
        if province_id in CITY_PROVINCES:
            if outputs.desired[province_id] != "urban":
                issues.append(f"city province {province_id} is not declared urban")
            continue
        if len(footprint) < MIN_URBAN_PIXELS:
            issues.append(
                f"province {province_id}: urban footprint has only {len(footprint)} pixels"
            )
        total = sum(outputs.counts[province_id].values())
        if len(footprint) > total * MAX_URBAN_SHARE:
            issues.append(
                f"province {province_id}: urban footprint erases too much biome"
            )
        if outputs.desired[province_id] != "urban":
            issues.append(f"province {province_id}: settlement is not declared urban")
        maximum_run = floor(round(sqrt(len(footprint))) / 2)
        actual_run = straight_boundary_run(footprint, outputs.terrain.width)
        if actual_run > maximum_run:
            issues.append(
                f"province {province_id}: urban boundary run {actual_run} exceeds {maximum_run}"
            )
    issues.extend(coverage_issues(outputs))
    return issues


def atomic_save_bmp(image: Image.Image, path: Path) -> None:
    temporary = path.with_suffix(".bmp.tmp")
    try:
        image.save(temporary, format="BMP")
        with temporary.open("r+b") as generated:
            generated.flush()
            os.fsync(generated.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def apply() -> None:
    apply_province_geometry()
    outputs = expected()
    atomic_save_bmp(outputs.terrain, TERRAIN_PATH)
    atomic_save_bmp(outputs.trees, TREES_PATH)
    atomic_save_bmp(outputs.rivers, RIVERS_PATH)
    UNITSTACKS_PATH.write_bytes(outputs.unitstacks)
    atomic_save_bmp(outputs.heightmap, HEIGHTMAP_PATH)
    atomic_save_bmp(outputs.world_normal, WORLD_NORMAL_PATH)
    DEFINITION_PATH.write_bytes(outputs.definition)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_mutually_exclusive_group()
    actions.add_argument(
        "--check",
        action="store_true",
        help="validate synchronized terrain outputs (default)",
    )
    actions.add_argument(
        "--apply", action="store_true", help="write synchronized terrain outputs"
    )
    actions.add_argument(
        "--plan-provinces",
        action="store_true",
        help="replan the reviewed IVN province geometry data from the current map",
    )
    args = parser.parse_args()
    if args.plan_provinces:
        plan_province_geometry()
        print(f"Wrote {PROVINCE_GEOMETRY_PATH.name} and {PROVINCE_MANIFEST_PATH.name}.")
        return 0
    if args.apply:
        apply()
    issues = province_geometry_issues()
    if not issues:
        issues = validate()
    if issues:
        for issue in issues:
            print(f"ERROR: {issue}")
        return 1
    print(
        f"Ivanland geography validation passed for {len(scoped_provinces())} land provinces and {len(SETTLEMENT_PROVINCES)} settlements."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
