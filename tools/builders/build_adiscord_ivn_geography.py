"""Synchronize Ivanland/IIA declared terrain with the painted terrain map."""

from __future__ import annotations

import argparse
import heapq
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

from PIL import Image


ROOT = Path(__file__).resolve().parents[2]
TERRAIN_PATH = ROOT / "map/terrain.bmp"
TREES_PATH = ROOT / "map/trees.bmp"
PROVINCES_PATH = ROOT / "map/provinces.bmp"
DEFINITION_PATH = ROOT / "map/definition.csv"
HEIGHTMAP_PATH = ROOT / "map/heightmap.bmp"
WORLD_NORMAL_PATH = ROOT / "map/world_normal.bmp"
TERRAIN_CONFIG_PATH = ROOT / "common/terrain/00_terrain.txt"
STATE_DIR = ROOT / "history/states"

IVN_STATE_IDS = frozenset({25, 92, 95, 96, 97, 98, 99, 100, 101, 127, 129, 130, 131, 132, 164, 695, 696, 697, 698})
IIA_STATE_IDS = frozenset({128, 693, 694})
SCOPED_STATE_IDS = IVN_STATE_IDS | IIA_STATE_IDS
ISLAND_HEIGHT_STATE_IDS = frozenset({128, 693, 694})
NORTHERN_LANDSCAPE_STATE_IDS = frozenset({127, 128, 129, 130, 131, 132, 164, 693, 694})
MAINLAND_FOREST_STATE_IDS = NORTHERN_LANDSCAPE_STATE_IDS - ISLAND_HEIGHT_STATE_IDS - {164}
SETTLEMENT_PROVINCES = frozenset({16568, 3462, 3318, 888, 838, 2448, 882, 702, 9327, 595, 579, 1971, 3447, 2262, 423, 4217, 6905, 11841, 1763, 5573, 9160, 12076})
TERRAIN_PRIORITY = ("urban", "mountain", "hills", "marsh", "forest", "plains", "jungle", "desert")
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
        raise RuntimeError(f"definition.csv: missing northern landscape provinces {missing}")

    color_to_id = {color: province_id for province_id, color in definition_colors.items()}
    if len(color_to_id) != len(definition_colors):
        raise RuntimeError("definition.csv: duplicate RGB inside northern landscape scope")
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
        color = tuple(pixels[index * 3:index * 3 + 3])
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
        raise RuntimeError(f"provinces bitmap: missing northern landscape bitmap provinces {missing_pixels}")
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
    ridge = exp(-((u - ridge_x) / 0.17) ** 2)
    ridge_spine = exp(-((u - ridge_x) / 0.026) ** 2)
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


def height_slope(pixels: list[int] | bytes | bytearray, width: int, height: int, index: int) -> int:
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
        raise ValueError("world normal dimensions must equal half the heightmap dimensions")
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
            full_indices = (top + left, top + left + 1, bottom + left, bottom + left + 1)
            normal_index = ny * normal_width + nx
            means[normal_index] = sum(heights[index] for index in full_indices) / 4.0
            island_cells[normal_index] = any(island_mask[index] for index in full_indices)

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
        pixels[offset:offset + 3] = bytes((red, green, NORMAL_BLUE))
    return Image.frombytes("RGB", source.size, bytes(pixels))


def moisture_value(u: float, v: float, x: int, y: int) -> float:
    broad = 0.50 + 0.22 * sin(5.0 * u + 3.0 * v) + 0.18 * cos(4.0 * u - 6.0 * v)
    return broad + 0.10 * (stable_unit_hash(x, y, 11) - 0.5)


def tree_probability(terrain_type: str) -> float:
    return {
        "forest": 0.62,
        "plains": 0.11,
        "hills": 0.04,
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


def definition_contract() -> tuple[list[str], str, bytes, dict[int, tuple[int, int, int]], dict[int, str]]:
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
            raise RuntimeError(f"province {province_id}: IVN/IIA scope contains non-land province")
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
        raise RuntimeError(f"province has only {len(indices)} pixels; cannot preserve 35% biome")
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
            if neighbour not in province or neighbour in selected or neighbour in queued:
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
        raise RuntimeError("province urban footprint cannot reach its target as one connected component")
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
    if not (
        len(north_mask) == len(island_mask) == len(state_by_pixel) == pixel_count
    ):
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
        if included and state_by_pixel[index] == 164 and original[index] == MARSH_PALETTE
    }
    land = {
        index
        for index, included in enumerate(north_mask)
        if included and original[index] not in WATER_PALETTES
    }
    classifiable = land - urban - preserved_marsh
    slopes = {
        index: masked_height_slope(heights, north_mask, width, index)
        for index in land
    }
    mountains = {
        index
        for index in classifiable
        if heights[index] >= 158 or slopes[index] >= 12
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
                raise RuntimeError(f"tree sample uses unknown terrain palette {terrain_index}")
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
            if stable_unit_hash(tx, ty, 23) < probability:
                pixels[tree_index] = (
                    6 if stable_unit_hash(tx, ty, 29) < 0.65 else 5
                )
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
        {terrain_type: (values[0], values[1]) for terrain_type, values in counts.items()},
        forbidden,
        outside_changes,
    )


def render_trees(
    source: Image.Image,
    terrain: Image.Image,
    state_by_pixel: Sequence[int],
    palette: dict[int, str],
) -> Image.Image:
    return _render_trees_with_metrics(source, terrain, state_by_pixel, palette)[0]


def _build_expected() -> GeographyOutputs:
    lines, newline, bom, province_colors, _declared = definition_contract()
    palette = palette_types()
    color_to_id = {color: province_id for province_id, color in province_colors.items()}
    if len(color_to_id) != len(province_colors):
        raise RuntimeError("definition.csv: duplicate RGB inside IVN/IIA scope")

    with Image.open(BytesIO(TERRAIN_PATH.read_bytes())) as terrain_source, Image.open(BytesIO(PROVINCES_PATH.read_bytes())) as provinces_source:
        if terrain_source.mode != "P" or terrain_source.size != provinces_source.size:
            raise RuntimeError("terrain.bmp must be paletted and match provinces.bmp dimensions")
        terrain_original = terrain_source.copy()
        terrain_pixels = bytearray(terrain_source.get_flattened_data())
        province_bytes = provinces_source.convert("RGB").tobytes()
        masks = landscape_masks(provinces_source, province_colors)

    with Image.open(BytesIO(HEIGHTMAP_PATH.read_bytes())) as height_source:
        if height_source.mode != "L" or height_source.size != terrain_original.size:
            raise RuntimeError("heightmap.bmp must use mode L and match provinces.bmp dimensions")
        heightmap = render_heightmap(height_source, masks.island, masks.island_bbox)
    with Image.open(BytesIO(WORLD_NORMAL_PATH.read_bytes())) as normal_source:
        if normal_source.mode != "RGB":
            raise RuntimeError("world_normal.bmp must use mode RGB")
        world_normal = normal_from_height(heightmap, normal_source, masks.island)

    province_by_pixel = array("H", [0]) * len(terrain_pixels)
    settlement_indices = {province_id: [] for province_id in SETTLEMENT_PROVINCES}
    for index in range(len(terrain_pixels)):
        color = tuple(province_bytes[index * 3:index * 3 + 3])
        province_id = color_to_id.get(color)
        if province_id is None:
            continue
        province_by_pixel[index] = province_id
        if province_id in settlement_indices:
            settlement_indices[province_id].append(index)

    missing_settlements = sorted(SETTLEMENT_PROVINCES - province_colors.keys())
    if missing_settlements:
        raise RuntimeError(f"settlement provinces outside IVN/IIA scope: {missing_settlements}")

    priority = {terrain_type: len(TERRAIN_PRIORITY) - rank for rank, terrain_type in enumerate(TERRAIN_PRIORITY)}
    footprints = {
        province_id: compact_footprint(indices, terrain_original.width, province_id)
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
    generated_pixels = bytearray(terrain.get_flattened_data())

    counts = {province_id: Counter() for province_id in province_colors}
    for index, province_id in enumerate(province_by_pixel):
        if not province_id:
            continue
        terrain_type = palette.get(generated_pixels[index])
        if terrain_type is None:
            raise RuntimeError(
                f"province {province_id}: unknown graphical terrain palette {generated_pixels[index]}"
            )
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
        trees, tree_counts, forbidden_trees, outside_tree_changes = _render_trees_with_metrics(
            tree_source,
            terrain,
            masks.state_by_pixel,
            palette,
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

    coast_distances = distance_from_edge(
        masks.north, terrain.width, terrain.height
    )
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
            connected = set(
                pixel_neighbours(index, terrain.width, len(generated_pixels))
            ) & remaining
            remaining.difference_update(connected)
            component.update(connected)
            frontier.extend(connected)
        if not any(
            generated_pixels[neighbour] == HILLS_PALETTE
            for index in component
            for neighbour in pixel_neighbours(index, terrain.width, len(generated_pixels))
        ):
            components_without_shoulders += 1

    outside_terrain_changes = 0
    for index, (before, after) in enumerate(zip(terrain_pixels, generated_pixels)):
        if before == after or masks.north[index]:
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
        ("plains", 0.06, 0.16),
        ("hills", 0.01, 0.07),
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
            for before, after in zip(current.get_flattened_data(), outputs.terrain.get_flattened_data())
        )
    if differences:
        issues.append(f"map/terrain.bmp: {differences} northern terrain pixels drifted")
    with Image.open(BytesIO(HEIGHTMAP_PATH.read_bytes())) as current:
        differences = sum(
            before != after
            for before, after in zip(current.get_flattened_data(), outputs.heightmap.get_flattened_data())
        )
    if differences:
        issues.append(f"map/heightmap.bmp: {differences} island height pixels drifted")
    with Image.open(BytesIO(WORLD_NORMAL_PATH.read_bytes())) as current:
        differences = sum(
            before != after
            for before, after in zip(current.get_flattened_data(), outputs.world_normal.get_flattened_data())
        )
    if differences:
        issues.append(f"map/world_normal.bmp: {differences} island normal cells drifted")
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
        if len(footprint) < MIN_URBAN_PIXELS:
            issues.append(f"province {province_id}: urban footprint has only {len(footprint)} pixels")
        total = sum(outputs.counts[province_id].values())
        if len(footprint) > total * MAX_URBAN_SHARE:
            issues.append(f"province {province_id}: urban footprint erases too much biome")
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
    outputs = expected()
    atomic_save_bmp(outputs.terrain, TERRAIN_PATH)
    atomic_save_bmp(outputs.trees, TREES_PATH)
    atomic_save_bmp(outputs.heightmap, HEIGHTMAP_PATH)
    atomic_save_bmp(outputs.world_normal, WORLD_NORMAL_PATH)
    DEFINITION_PATH.write_bytes(outputs.definition)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_mutually_exclusive_group()
    actions.add_argument("--check", action="store_true", help="validate synchronized terrain outputs (default)")
    actions.add_argument("--apply", action="store_true", help="write synchronized terrain outputs")
    args = parser.parse_args()
    if args.apply:
        apply()
    issues = validate()
    if issues:
        for issue in issues:
            print(f"ERROR: {issue}")
        return 1
    print(f"Ivanland geography validation passed for {len(scoped_provinces())} land provinces and {len(SETTLEMENT_PROVINCES)} settlements.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
