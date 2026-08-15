"""Synchronize Ivanland/IIA declared terrain with the painted terrain map."""

from __future__ import annotations

import argparse
import os
import re
from array import array
from collections import Counter, deque
from dataclasses import dataclass
from io import BytesIO
from math import cos, exp, pi, sin
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[2]
TERRAIN_PATH = ROOT / "map/terrain.bmp"
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
SETTLEMENT_PROVINCES = frozenset({16568, 3462, 3318, 888, 838, 2448, 882, 702, 9327, 595, 579, 1971, 3447, 2262, 423, 4217, 6905, 11841, 1763, 5573, 9160, 12076})
TERRAIN_PRIORITY = ("urban", "mountain", "hills", "marsh", "forest", "plains", "jungle", "desert")
WATER_TYPES = frozenset({"ocean", "lakes"})
URBAN_PALETTE = 13
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


@dataclass
class GeographyOutputs:
    terrain: Image.Image
    definition: bytes
    heightmap: Image.Image
    world_normal: Image.Image
    trees: Image.Image | None
    desired: dict[int, str]
    counts: dict[int, Counter[str]]
    footprints: dict[int, set[int]]


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


def landscape_masks(
    provinces: Image.Image,
    definition_colors: dict[int, tuple[int, int, int]],
) -> LandscapeMasks:
    island_provinces = province_ids_for_states(ISLAND_HEIGHT_STATE_IDS)
    north_provinces = province_ids_for_states(NORTHERN_LANDSCAPE_STATE_IDS)
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
    return LandscapeMasks(island, north, (min_x, min_y, max_x, max_y))


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


def compact_footprint(indices: list[int], width: int) -> set[int]:
    if not indices:
        raise RuntimeError("cannot build an urban footprint for an empty province")
    maximum = int(len(indices) * MAX_URBAN_SHARE)
    if maximum < MIN_URBAN_PIXELS:
        raise RuntimeError(f"province has only {len(indices)} pixels; cannot preserve 35% biome")
    target = min(max(MIN_URBAN_PIXELS, round(len(indices) * URBAN_SHARE)), maximum)
    province = set(indices)
    mean_x = sum(index % width for index in indices) / len(indices)
    mean_y = sum(index // width for index in indices) / len(indices)
    anchor = min(indices, key=lambda index: (index % width - mean_x) ** 2 + (index // width - mean_y) ** 2)
    selected = {anchor}
    queue = deque([anchor])
    while queue and len(selected) < target:
        index = queue.popleft()
        for neighbour in (index - 1, index + 1, index - width, index + width):
            if neighbour in province and neighbour not in selected:
                selected.add(neighbour)
                queue.append(neighbour)
                if len(selected) == target:
                    break
    if len(selected) < target:
        raise RuntimeError("province urban footprint cannot reach its target as one connected component")
    return selected


def expected() -> GeographyOutputs:
    lines, newline, bom, province_colors, _declared = definition_contract()
    palette = palette_types()
    color_to_id = {color: province_id for province_id, color in province_colors.items()}
    if len(color_to_id) != len(province_colors):
        raise RuntimeError("definition.csv: duplicate RGB inside IVN/IIA scope")

    with Image.open(BytesIO(TERRAIN_PATH.read_bytes())) as terrain_source, Image.open(BytesIO(PROVINCES_PATH.read_bytes())) as provinces_source:
        if terrain_source.mode != "P" or terrain_source.size != provinces_source.size:
            raise RuntimeError("terrain.bmp must be paletted and match provinces.bmp dimensions")
        terrain = terrain_source.copy()
        terrain_pixels = list(terrain_source.get_flattened_data())
        province_bytes = provinces_source.convert("RGB").tobytes()
        masks = landscape_masks(provinces_source, province_colors)

    with Image.open(BytesIO(HEIGHTMAP_PATH.read_bytes())) as height_source:
        if height_source.mode != "L" or height_source.size != terrain.size:
            raise RuntimeError("heightmap.bmp must use mode L and match provinces.bmp dimensions")
        heightmap = render_heightmap(height_source, masks.island, masks.island_bbox)
    with Image.open(BytesIO(WORLD_NORMAL_PATH.read_bytes())) as normal_source:
        if normal_source.mode != "RGB":
            raise RuntimeError("world_normal.bmp must use mode RGB")
        world_normal = normal_from_height(heightmap, normal_source, masks.island)

    counts = {province_id: Counter() for province_id in province_colors}
    settlement_indices = {province_id: [] for province_id in SETTLEMENT_PROVINCES}
    for index, terrain_index in enumerate(terrain_pixels):
        color = tuple(province_bytes[index * 3:index * 3 + 3])
        province_id = color_to_id.get(color)
        if province_id is None:
            continue
        terrain_type = palette.get(terrain_index)
        if terrain_type is None:
            raise RuntimeError(f"province {province_id}: unknown graphical terrain palette {terrain_index}")
        if terrain_type not in WATER_TYPES:
            counts[province_id][terrain_type] += 1
        if province_id in settlement_indices:
            settlement_indices[province_id].append(index)

    missing_settlements = sorted(SETTLEMENT_PROVINCES - province_colors.keys())
    if missing_settlements:
        raise RuntimeError(f"settlement provinces outside IVN/IIA scope: {missing_settlements}")

    desired: dict[int, str] = {}
    priority = {terrain_type: len(TERRAIN_PRIORITY) - rank for rank, terrain_type in enumerate(TERRAIN_PRIORITY)}
    for province_id, terrain_counts in counts.items():
        if not terrain_counts:
            raise RuntimeError(f"province {province_id}: no painted land terrain")
        desired[province_id] = max(
            terrain_counts,
            key=lambda terrain_type: (terrain_counts[terrain_type], priority.get(terrain_type, 0)),
        )
    for province_id in SETTLEMENT_PROVINCES:
        desired[province_id] = "urban"

    footprints = {
        province_id: compact_footprint(indices, terrain.width)
        for province_id, indices in settlement_indices.items()
    }
    for indices in footprints.values():
        for index in indices:
            terrain_pixels[index] = URBAN_PALETTE
    terrain.putdata(terrain_pixels)

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
        trees=None,
        desired=desired,
        counts=counts,
        footprints=footprints,
    )


def validate() -> list[str]:
    outputs = expected()
    issues: list[str] = []
    with Image.open(BytesIO(TERRAIN_PATH.read_bytes())) as current:
        differences = sum(
            before != after
            for before, after in zip(current.get_flattened_data(), outputs.terrain.get_flattened_data())
        )
    if differences:
        issues.append(f"map/terrain.bmp: {differences} IVN/IIA urban-footprint pixels drifted")
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
    if DEFINITION_PATH.read_bytes() != outputs.definition:
        issues.append("map/definition.csv: IVN/IIA declared terrain drifted")
    for province_id, footprint in outputs.footprints.items():
        if len(footprint) < MIN_URBAN_PIXELS:
            issues.append(f"province {province_id}: urban footprint has only {len(footprint)} pixels")
        total = sum(outputs.counts[province_id].values())
        if len(footprint) > total * MAX_URBAN_SHARE:
            issues.append(f"province {province_id}: urban footprint erases too much biome")
        if outputs.desired[province_id] != "urban":
            issues.append(f"province {province_id}: settlement is not declared urban")
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
