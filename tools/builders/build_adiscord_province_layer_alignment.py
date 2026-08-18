#!/usr/bin/env python3
"""Align the 2026-08-18 province delta across HOI4 map raster layers.

This builder owns only the explicit province scope in ``NEW_PROVINCE_IDS`` and
``TERRAIN_CHANGED_PROVINCE_IDS``.  It deliberately leaves legacy mixed-biome
provinces outside that scope untouched.  The pass synchronizes graphical
terrain, tree occupancy, selected relief contradictions, and the corresponding
world-normal patch while preserving pixels outside the scoped masks.
"""

from __future__ import annotations

import argparse
from collections import Counter, deque
from dataclasses import dataclass
from io import BytesIO
from math import ceil, cos, pi, sin, sqrt
import os
from pathlib import Path
from statistics import median, pstdev
from typing import Mapping, Sequence

from PIL import Image


ROOT = Path(__file__).resolve().parents[2]
PROVINCES_PATH = ROOT / "map" / "provinces.bmp"
DEFINITION_PATH = ROOT / "map" / "definition.csv"
TERRAIN_PATH = ROOT / "map" / "terrain.bmp"
TREES_PATH = ROOT / "map" / "trees.bmp"
HEIGHTMAP_PATH = ROOT / "map" / "heightmap.bmp"
WORLD_NORMAL_PATH = ROOT / "map" / "world_normal.bmp"

NEW_PROVINCE_IDS = frozenset(range(16654, 16707))
TERRAIN_CHANGED_PROVINCE_IDS = frozenset({
    579, 5245, 5636, 5772, 6905, 6928, 7678, 8877, 9664,
    11209, 11392, 11443, 12189, 12250, 12296, 12955, 16563,
    16611, 16612,
})
TARGET_PROVINCE_IDS = NEW_PROVINCE_IDS | TERRAIN_CHANGED_PROVINCE_IDS

CANONICAL_PALETTE = {
    "plains": 0,
    "forest": 4,
    "hills": 17,
    "mountain": 20,
    "marsh": 9,
    "desert": 3,
    "urban": 13,
}
PALETTE_TYPES = {
    0: "plains", 1: "forest", 2: "hills", 3: "desert", 4: "forest",
    5: "plains", 6: "mountain", 7: "desert", 8: "desert", 9: "marsh",
    10: "mountain", 11: "mountain", 12: "desert", 13: "urban",
    14: "lakes", 15: "ocean", 16: "mountain", 17: "hills",
    18: "mountain", 19: "plains", 20: "mountain", 21: "jungle",
    22: "jungle", 27: "mountain", 31: "mountain",
}
WATER_TYPES = frozenset({"ocean", "lakes"})
TREE_PROBABILITIES = {"forest": 0.62, "plains": 0.11, "hills": 0.04, "marsh": 0.08}
NORMAL_CENTER = 127
NORMAL_SCALE = 1.65
NORMAL_BLUE = 253


@dataclass(frozen=True)
class DefinitionRow:
    province_id: int
    color: tuple[int, int, int]
    kind: str
    coastal: bool
    terrain: str
    continent: int


@dataclass(frozen=True)
class TerrainChange:
    before_counts: Counter[str]
    after_counts: Counter[str]
    changed_indices: set[int]


def stable_unit_hash(x: int, y: int, salt: int) -> float:
    value = (x * 73856093) ^ (y * 19349663) ^ (salt * 83492791)
    value = (value ^ (value >> 13)) * 1274126177
    return ((value ^ (value >> 16)) & 0xFFFFFFFF) / 0xFFFFFFFF


def pixel_neighbours(index: int, width: int, pixel_count: int) -> tuple[int, ...]:
    x = index % width
    result: list[int] = []
    if x:
        result.append(index - 1)
    if x + 1 < width and index + 1 < pixel_count:
        result.append(index + 1)
    if index >= width:
        result.append(index - width)
    if index + width < pixel_count:
        result.append(index + width)
    return tuple(result)


def terrain_counts(
    terrain_pixels: Sequence[int],
    indices: Sequence[int],
    palette_types: Mapping[int, str],
) -> Counter[str]:
    return Counter(palette_types.get(terrain_pixels[index], f"palette_{terrain_pixels[index]}") for index in indices)


def height_slope(heights: Sequence[int], width: int, index: int) -> int:
    return max(
        (abs(heights[index] - heights[neighbour]) for neighbour in pixel_neighbours(index, width, len(heights))),
        default=0,
    )


def _canonical_palette(desired_type: str, index: int, width: int) -> int:
    if desired_type == "mountain" and index // width < 300:
        return 16
    if desired_type == "plains" and index // width < 300:
        return 19
    try:
        return CANONICAL_PALETTE[desired_type]
    except KeyError as exc:
        raise RuntimeError(f"unsupported graphical terrain type {desired_type!r}") from exc


def _candidate_score(
    index: int,
    desired_type: str,
    terrain_pixels: Sequence[int],
    heights: Sequence[int],
    width: int,
    palette_types: Mapping[int, str],
    min_height: int,
    height_span: int,
    max_slope: int,
) -> tuple[float, int]:
    current = palette_types.get(terrain_pixels[index], "unknown")
    h = (heights[index] - min_height) / height_span
    s = height_slope(heights, width, index) / max_slope
    penalties = {
        "forest": {"plains": 0.0, "hills": 0.25, "marsh": 0.35, "desert": 0.8, "mountain": 1.4},
        "plains": {"forest": 0.1, "desert": 0.2, "marsh": 0.4, "hills": 0.7, "mountain": 1.7},
        "hills": {"plains": 0.0, "forest": 0.15, "desert": 0.2, "mountain": 0.35, "marsh": 0.8},
        "mountain": {"hills": 0.0, "desert": 0.1, "plains": 0.4, "forest": 0.5, "marsh": 1.0},
        "marsh": {"plains": 0.0, "forest": 0.2, "hills": 0.8, "desert": 1.0, "mountain": 1.5},
        "desert": {"plains": 0.0, "hills": 0.05, "mountain": 0.15, "forest": 0.8, "marsh": 1.2},
    }
    penalty = penalties.get(desired_type, {}).get(current, 0.4)
    if desired_type == "mountain":
        score = penalty - 1.6 * h - 1.2 * s
    elif desired_type == "hills":
        score = penalty + abs(h - 0.55) + 0.5 * abs(s - 0.50)
    elif desired_type == "marsh":
        score = penalty + 1.2 * h + 1.5 * s
    elif desired_type == "forest":
        score = penalty + 0.15 * h + 0.8 * s
    elif desired_type == "plains":
        score = penalty + 0.35 * h + 1.4 * s
    else:
        score = penalty + 0.20 * s
    return score + 0.03 * stable_unit_hash(index % width, index // width, 41), index


def align_province_terrain(
    terrain_pixels: bytearray,
    heights: Sequence[int],
    width: int,
    height: int,
    indices: Sequence[int],
    desired_type: str,
    province_id: int,
    palette_types: Mapping[int, str] = PALETTE_TYPES,
    target_share: float = 0.70,
) -> TerrainChange:
    del height
    if not indices:
        raise RuntimeError(f"province {province_id}: no bitmap pixels")
    before = terrain_counts(terrain_pixels, indices, palette_types)
    changed: set[int] = set()
    land = [index for index in indices if palette_types.get(terrain_pixels[index]) not in WATER_TYPES]
    if not land:
        raise RuntimeError(f"province {province_id}: no land terrain pixels")

    if desired_type == "urban":
        for index in land:
            value = _canonical_palette(desired_type, index, width)
            if terrain_pixels[index] != value:
                terrain_pixels[index] = value
                changed.add(index)
    else:
        # Urban pixels are semantic settlements rather than a harmless blend;
        # never retain them inside a province declared as a non-urban biome.
        for index in land:
            if palette_types.get(terrain_pixels[index]) == "urban":
                terrain_pixels[index] = _canonical_palette(desired_type, index, width)
                changed.add(index)

        desired = [index for index in land if palette_types.get(terrain_pixels[index]) == desired_type]
        target = min(len(land), ceil(len(land) * target_share))
        if len(desired) < target:
            candidates = [index for index in land if palette_types.get(terrain_pixels[index]) != desired_type]
            local_heights = [heights[index] for index in land]
            min_height = min(local_heights)
            height_span = max(1, max(local_heights) - min_height)
            max_slope = max(1, max(height_slope(heights, width, index) for index in land))
            candidates.sort(key=lambda index: _candidate_score(
                index, desired_type, terrain_pixels, heights, width, palette_types,
                min_height, height_span, max_slope,
            ))
            for index in candidates[: target - len(desired)]:
                value = _canonical_palette(desired_type, index, width)
                if terrain_pixels[index] != value:
                    terrain_pixels[index] = value
                    changed.add(index)

    after = terrain_counts(terrain_pixels, indices, palette_types)
    return TerrainChange(before, after, changed)


def _inward_distances(indices: Sequence[int], width: int, pixel_count: int) -> dict[int, int]:
    province = set(indices)
    distances: dict[int, int] = {}
    frontier: deque[int] = deque()
    for index in province:
        if any(neighbour not in province for neighbour in pixel_neighbours(index, width, pixel_count)):
            distances[index] = 0
            frontier.append(index)
    while frontier:
        index = frontier.popleft()
        for neighbour in pixel_neighbours(index, width, pixel_count):
            if neighbour in province and neighbour not in distances:
                distances[neighbour] = distances[index] + 1
                frontier.append(neighbour)
    for index in province:
        distances.setdefault(index, 0)
    return distances


def _outside_ring(indices: Sequence[int], width: int, pixel_count: int) -> set[int]:
    province = set(indices)
    return {
        neighbour
        for index in province
        for neighbour in pixel_neighbours(index, width, pixel_count)
        if neighbour not in province
    }


def align_province_height(
    heights: bytearray,
    width: int,
    height: int,
    indices: Sequence[int],
    desired_type: str,
    province_id: int,
) -> set[int]:
    del height
    if not indices:
        raise RuntimeError(f"province {province_id}: no height pixels")
    values = [heights[index] for index in indices]
    centre = float(median(values))
    spread = float(pstdev(values))
    policy: str | None = None
    if desired_type == "mountain" and centre < 145:
        policy = "raise"
    elif desired_type == "hills" and centre < 112 and spread < 4:
        policy = "roll"
    elif desired_type == "plains" and (centre > 130 or spread > 18):
        policy = "flatten"
    elif desired_type == "marsh" and (centre > 120 or spread > 8):
        policy = "flatten"
    if policy is None:
        return set()

    distances = _inward_distances(indices, width, len(heights))
    maximum = max(distances.values(), default=0)
    if maximum <= 0:
        return set()
    ring = _outside_ring(indices, width, len(heights))
    ring_level = float(median([heights[index] for index in ring])) if ring else centre
    changed: set[int] = set()
    for index in indices:
        distance = distances[index]
        if distance <= 0:
            continue
        weight = sqrt(distance / maximum)
        x = index % width
        y = index // width
        wave = 0.5 * sin((x + province_id % 17) * pi / 7.0) + 0.5 * cos((y + province_id % 13) * pi / 9.0)
        original = heights[index]
        if policy == "raise":
            target = round(ring_level + 20 + 40 * weight + 5 * wave)
            value = max(original, target)
        elif policy == "roll":
            value = round(ring_level + 4 + 12 * weight + 5 * wave)
        else:
            value = round(ring_level + 3 * wave)
        value = max(89, min(255, value))
        if value != original:
            heights[index] = value
            changed.add(index)
    return changed


def _normal_cell_mean(heights: bytes, width: int, nx: int, ny: int) -> float:
    left = nx * 2
    top = ny * 2
    first = top * width + left
    second = first + width
    return (heights[first] + heights[first + 1] + heights[second] + heights[second + 1]) / 4.0


def render_world_normal_patch(
    heightmap: Image.Image,
    source: Image.Image,
    changed_height_indices: set[int],
) -> tuple[Image.Image, set[int]]:
    if heightmap.mode != "L" or source.mode != "RGB":
        raise ValueError("heightmap/world_normal modes must be L/RGB")
    width, height = heightmap.size
    normal_width, normal_height = source.size
    if (normal_width * 2, normal_height * 2) != (width, height):
        raise ValueError("world_normal dimensions must be half the heightmap dimensions")
    if not changed_height_indices:
        return source.copy(), set()
    changed_cells = {
        (index // width // 2) * normal_width + (index % width // 2)
        for index in changed_height_indices
    }
    affected = set(changed_cells)
    for index in tuple(changed_cells):
        affected.update(pixel_neighbours(index, normal_width, normal_width * normal_height))
    heights = heightmap.tobytes()
    pixels = bytearray(source.tobytes())
    changed: set[int] = set()
    for index in affected:
        nx = index % normal_width
        ny = index // normal_width
        west = index - 1 if nx else index
        east = index + 1 if nx + 1 < normal_width else index
        north = index - normal_width if ny else index
        south = index + normal_width if ny + 1 < normal_height else index
        dx = (_normal_cell_mean(heights, width, east % normal_width, east // normal_width) - _normal_cell_mean(heights, width, west % normal_width, west // normal_width)) / 2.0
        dy = (_normal_cell_mean(heights, width, south % normal_width, south // normal_width) - _normal_cell_mean(heights, width, north % normal_width, north // normal_width)) / 2.0
        value = (
            max(0, min(255, round(NORMAL_CENTER - NORMAL_SCALE * dx))),
            max(0, min(255, round(NORMAL_CENTER + NORMAL_SCALE * dy))),
            NORMAL_BLUE,
        )
        offset = index * 3
        if tuple(pixels[offset:offset + 3]) != value:
            pixels[offset:offset + 3] = bytes(value)
            changed.add(index)
    return Image.frombytes("RGB", source.size, bytes(pixels)), changed


def tree_probability(terrain_type: str) -> float:
    return TREE_PROBABILITIES.get(terrain_type, 0.0)


def render_tree_patch(
    source: Image.Image,
    terrain: Image.Image,
    target_mask: bytearray,
    palette_types: Mapping[int, str] = PALETTE_TYPES,
) -> tuple[Image.Image, set[int]]:
    if source.mode != "P" or terrain.mode != "P":
        raise ValueError("trees and terrain must remain paletted")
    full_width, full_height = terrain.size
    if len(target_mask) != full_width * full_height:
        raise ValueError("target mask does not match terrain dimensions")
    tree_width, tree_height = source.size
    terrain_pixels = list(terrain.get_flattened_data())
    pixels = bytearray(source.get_flattened_data())
    changed: set[int] = set()
    for ty in range(tree_height):
        y0 = ty * full_height // tree_height
        y1 = (ty + 1) * full_height // tree_height
        for tx in range(tree_width):
            x0 = tx * full_width // tree_width
            x1 = (tx + 1) * full_width // tree_width
            full_indices = [y * full_width + x for y in range(y0, y1) for x in range(x0, x1)]
            if not any(target_mask[index] for index in full_indices):
                continue
            counts = Counter(palette_types.get(terrain_pixels[index], "unknown") for index in full_indices)
            terrain_type = max(counts, key=lambda value: (counts[value], value))
            probability = tree_probability(terrain_type)
            value = 6 if stable_unit_hash(tx, ty, 23) < probability and stable_unit_hash(tx, ty, 29) < 0.65 else 5 if stable_unit_hash(tx, ty, 23) < probability else 0
            tree_index = ty * tree_width + tx
            if pixels[tree_index] != value:
                pixels[tree_index] = value
                changed.add(tree_index)
    result = source.copy()
    result.putdata(pixels)
    return result, changed


def read_definition(path: Path = DEFINITION_PATH) -> dict[int, DefinitionRow]:
    result: dict[int, DefinitionRow] = {}
    for line in path.read_text(encoding="utf-8-sig", errors="strict").splitlines():
        fields = line.split(";")
        if len(fields) < 8 or not fields[0].isdigit():
            continue
        province_id = int(fields[0])
        result[province_id] = DefinitionRow(
            province_id,
            tuple(map(int, fields[1:4])),
            fields[4],
            fields[5].lower() == "true",
            fields[6],
            int(fields[7]),
        )
    return result


def collect_target_indices(
    provinces: Image.Image,
    definition: Mapping[int, DefinitionRow],
) -> dict[int, list[int]]:
    missing = sorted(TARGET_PROVINCE_IDS - definition.keys())
    if missing:
        raise RuntimeError(f"definition.csv: missing target provinces {missing}")
    by_color = {definition[province_id].color: province_id for province_id in TARGET_PROVINCE_IDS}
    result = {province_id: [] for province_id in TARGET_PROVINCE_IDS}
    raw = provinces.convert("RGB").tobytes()
    for index in range(provinces.width * provinces.height):
        province_id = by_color.get(tuple(raw[index * 3:index * 3 + 3]))
        if province_id is not None:
            result[province_id].append(index)
    vanished = sorted(province_id for province_id, indices in result.items() if not indices)
    if vanished:
        raise RuntimeError(f"provinces.bmp: target provinces have no pixels {vanished}")
    return result


def target_share(province_id: int, terrain_type: str) -> float:
    if terrain_type == "urban":
        return 1.0
    return 0.70 if province_id in NEW_PROVINCE_IDS else 0.65


@dataclass
class BuildOutputs:
    terrain: Image.Image
    heightmap: Image.Image
    world_normal: Image.Image
    trees: Image.Image
    terrain_changes: dict[int, TerrainChange]
    height_changes: dict[int, set[int]]
    normal_changes: set[int]
    tree_changes: set[int]


def build_expected() -> BuildOutputs:
    definition = read_definition()
    with Image.open(BytesIO(PROVINCES_PATH.read_bytes())) as provinces_source:
        provinces = provinces_source.copy()
    with Image.open(BytesIO(TERRAIN_PATH.read_bytes())) as terrain_source:
        terrain = terrain_source.copy()
    with Image.open(BytesIO(HEIGHTMAP_PATH.read_bytes())) as height_source:
        heightmap = height_source.copy()
    with Image.open(BytesIO(WORLD_NORMAL_PATH.read_bytes())) as normal_source:
        world_normal = normal_source.copy()
    with Image.open(BytesIO(TREES_PATH.read_bytes())) as tree_source:
        trees = tree_source.copy()
    if terrain.mode != "P" or heightmap.mode != "L" or world_normal.mode != "RGB" or trees.mode != "P":
        raise RuntimeError("unexpected map bitmap modes")
    if terrain.size != provinces.size or heightmap.size != provinces.size:
        raise RuntimeError("terrain/heightmap/provinces dimensions differ")

    indices_by_province = collect_target_indices(provinces, definition)
    heights = bytearray(heightmap.tobytes())
    height_changes: dict[int, set[int]] = {}
    all_height_changes: set[int] = set()
    for province_id in sorted(TARGET_PROVINCE_IDS):
        desired = definition[province_id].terrain
        changed = align_province_height(
            heights, heightmap.width, heightmap.height,
            indices_by_province[province_id], desired, province_id,
        )
        height_changes[province_id] = changed
        all_height_changes.update(changed)
    heightmap = Image.frombytes("L", heightmap.size, bytes(heights))

    terrain_pixels = bytearray(terrain.get_flattened_data())
    terrain_changes: dict[int, TerrainChange] = {}
    for province_id in sorted(TARGET_PROVINCE_IDS):
        desired = definition[province_id].terrain
        terrain_changes[province_id] = align_province_terrain(
            terrain_pixels, heights, terrain.width, terrain.height,
            indices_by_province[province_id], desired, province_id,
            PALETTE_TYPES, target_share(province_id, desired),
        )
    generated_terrain = terrain.copy()
    generated_terrain.putdata(terrain_pixels)

    world_normal, normal_changes = render_world_normal_patch(
        heightmap, world_normal, all_height_changes
    )
    target_mask = bytearray(terrain.width * terrain.height)
    for indices in indices_by_province.values():
        for index in indices:
            target_mask[index] = 1
    trees, tree_changes = render_tree_patch(trees, generated_terrain, target_mask)
    return BuildOutputs(
        generated_terrain, heightmap, world_normal, trees,
        terrain_changes, height_changes, normal_changes, tree_changes,
    )


def _save_atomic(image: Image.Image, path: Path) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    try:
        image.save(temporary, format="BMP")
        with temporary.open("r+b") as stream:
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def apply() -> BuildOutputs:
    outputs = build_expected()
    _save_atomic(outputs.heightmap, HEIGHTMAP_PATH)
    _save_atomic(outputs.terrain, TERRAIN_PATH)
    _save_atomic(outputs.world_normal, WORLD_NORMAL_PATH)
    _save_atomic(outputs.trees, TREES_PATH)
    return outputs


def validate() -> list[str]:
    outputs = build_expected()
    expected = {
        TERRAIN_PATH: outputs.terrain,
        HEIGHTMAP_PATH: outputs.heightmap,
        WORLD_NORMAL_PATH: outputs.world_normal,
        TREES_PATH: outputs.trees,
    }
    issues: list[str] = []
    for path, image in expected.items():
        with Image.open(BytesIO(path.read_bytes())) as current:
            if current.mode != image.mode or current.size != image.size:
                issues.append(f"{path.relative_to(ROOT)}: mode or dimensions differ")
            elif current.tobytes() != image.tobytes():
                differences = sum(a != b for a, b in zip(current.tobytes(), image.tobytes()))
                issues.append(f"{path.relative_to(ROOT)}: {differences} generated bytes differ")
            if current.mode == "P" and current.getpalette() != image.getpalette():
                issues.append(f"{path.relative_to(ROOT)}: palette differs")
    return issues


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group()
    action.add_argument("--apply", action="store_true", help="write the aligned bitmap layers")
    action.add_argument("--check", action="store_true", help="validate generated outputs (default)")
    args = parser.parse_args()
    if args.apply:
        outputs = apply()
        terrain_pixels = sum(len(change.changed_indices) for change in outputs.terrain_changes.values())
        height_pixels = sum(len(change) for change in outputs.height_changes.values())
        print(
            f"Aligned {len(TARGET_PROVINCE_IDS)} provinces: "
            f"{terrain_pixels} terrain pixels, {height_pixels} height pixels, "
            f"{len(outputs.tree_changes)} tree cells, {len(outputs.normal_changes)} normal cells."
        )
    issues = validate()
    if issues:
        for issue in issues:
            print(f"ERROR: {issue}")
        return 1
    print("Province layer alignment validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
