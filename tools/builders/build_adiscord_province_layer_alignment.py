#!/usr/bin/env python3
"""Align the 2026-08-18 province delta across HOI4 map raster layers.

This builder owns graphical terrain and tree occupancy for the explicit province
scope in ``NEW_PROVINCE_IDS`` and ``TERRAIN_CHANGED_PROVINCE_IDS``.  It
deliberately leaves legacy mixed-biome provinces outside its scope untouched.

Relief is *not* owned here.  This pass used to raise or flatten province
interiors, and every part of that was a defect generator: it skipped the border
ring and started the interior at ``ring_level + 20``, which ringed each raised
province with a guaranteed 20 unit single-pixel wall; its ``sqrt`` falloff
saturated within a quarter of the province depth, so interiors settled into a
flat tabletop; and its "noise" was an axis-aligned sinusoid with fixed 14 and 18
pixel periods, identical in every province, which showed up as a cross-hatch mesh
across the whole map.  ``map/heightmap.bmp`` and the dependent
``map/world_normal.bmp`` now belong to
:mod:`tools.builders.build_adiscord_map_relief_readability`, which sculpts relief
continuously across province borders and covers a superset of this scope.

Two rules here are shared with other owners of the same bitmaps.  Graphical
urban never covers a river channel, because the channel has to stay readable
through a town - and that is enforced by :func:`shared_river_corridor` rather
than merely intended, because painting every land pixel urban put masonry back
over the corridor the relief pass had just cleared in the four city provinces
both cover.  Permanent snow is left entirely to
:mod:`tools.builders.build_adiscord_terrain_snow`: this pass writes the base
palette index for a category and lets the snow classifier decide whether that
pixel is white.  Because the alignment only ever compares terrain *categories*,
that delegation is idempotent in either apply order.
"""

from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass
from io import BytesIO
import json
from math import ceil
import os
from pathlib import Path
from typing import Mapping, Sequence

import numpy as np
from PIL import Image

from tools.builders import build_adiscord_map_relief_readability as relief
from tools.lib.map_raster import river_corridor_indices


ROOT = Path(__file__).resolve().parents[2]
PROVINCES_PATH = ROOT / "map" / "provinces.bmp"
DEFINITION_PATH = ROOT / "map" / "definition.csv"
TERRAIN_PATH = ROOT / "map" / "terrain.bmp"
TREES_PATH = ROOT / "map" / "trees.bmp"
HEIGHTMAP_PATH = ROOT / "map" / "heightmap.bmp"
RIVERS_PATH = ROOT / "map" / "rivers.bmp"

READABILITY_SCOPE_PATH = ROOT / "tools" / "data" / "adiscord_map_readability_scope.json"

NEW_PROVINCE_IDS = frozenset(range(16654, 16707))
TERRAIN_CHANGED_PROVINCE_IDS = frozenset({
    579, 5245, 5636, 5772, 6905, 6928, 7678, 8877, 9664,
    11209, 11392, 11443, 12189, 12250, 12296, 12955, 16563,
    16611, 16612,
})


def _delegated_province_ids() -> frozenset[int]:
    """Return the northern-island provinces owned by the relief builder."""
    payload = json.loads(READABILITY_SCOPE_PATH.read_text(encoding="utf-8"))
    provinces = payload.get("northern_island_provinces")
    if not isinstance(provinces, list) or not provinces:
        raise RuntimeError(
            "tools/data/adiscord_map_readability_scope.json: "
            "northern_island_provinces must be a non-empty list"
        )
    return frozenset(int(province_id) for province_id in provinces)


RELIEF_DELEGATED_PROVINCE_IDS = _delegated_province_ids()
TARGET_PROVINCE_IDS = (
    NEW_PROVINCE_IDS | TERRAIN_CHANGED_PROVINCE_IDS
) - RELIEF_DELEGATED_PROVINCE_IDS

CANONICAL_PALETTE = {
    "plains": 0,
    "forest": 4,
    "hills": 17,
    # Palette 20 is ``mountain_variation_grass`` on texture 7, so a province
    # aligned to it renders as green pasture however high it is.  Index 11 is a
    # rocky mountain texture, which is what a mountain province has to read as.
    "mountain": 11,
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
WATER_PALETTE = frozenset({14, 15})
TREE_PROBABILITIES = {"forest": 0.62, "plains": 0.11, "hills": 0.04, "marsh": 0.08}


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
    # There is deliberately no latitude rule here.  Selecting the permanent-snow
    # palettes above a bare ``y < 300`` drew a perfectly straight seam across the
    # whole map at exactly that row.  Snow belongs to
    # :mod:`tools.builders.build_adiscord_terrain_snow`, whose classifier picks it
    # from a graded, noise-broken boundary; because this pass only ever compares
    # terrain *categories* and both snow palettes share the category of their
    # base index, that delegation stays idempotent in either apply order.
    del index, width
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
    corridor: frozenset[int] = frozenset(),
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
        # The river corridor is honoured here rather than merely documented.
        # Painting every land pixel urban put masonry straight back over the
        # channel that
        # :mod:`tools.builders.build_adiscord_map_relief_readability` had just
        # cleared, in the four city provinces both passes cover - which is
        # exactly the 30 bytes that made the relief builder's ``--check`` report
        # its own output as drift.
        bank = relief.CATEGORY_PALETTE[relief.CORRIDOR_BANK_CATEGORY][0]
        for index in land:
            if index in corridor:
                value = bank
            else:
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


def tree_probability(terrain_type: str) -> float:
    return TREE_PROBABILITIES.get(terrain_type, 0.0)


def render_tree_patch(
    source: Image.Image,
    terrain: Image.Image,
    target_mask: bytearray,
    palette_types: Mapping[int, str] = PALETTE_TYPES,
    land: np.ndarray | None = None,
) -> tuple[Image.Image, set[int]]:
    """Repaint tree occupancy for the cells this pass's terrain changes touch.

    A tree cell covers 3.41 x 3.41 terrain pixels, so a majority vote alone let a
    cell that was 49% ocean still grow trees and its canopy rendered over the
    surf.  The shoreline rule is shared with
    :func:`tools.builders.build_adiscord_map_relief_readability.rejected_tree_cells`
    so both owners of ``map/trees.bmp`` agree regardless of apply order.

    ``land`` must be the caller's land mask, because sharing the *rule* is not
    enough if the two passes disagree about what land is.  Deriving it from the
    water palette here while the relief pass derives it from ``definition.csv``
    left seven shoreline cells that one owner rejected and the other planted.
    """

    if source.mode != "P" or terrain.mode != "P":
        raise ValueError("trees and terrain must remain paletted")
    full_width, full_height = terrain.size
    if len(target_mask) != full_width * full_height:
        raise ValueError("target mask does not match terrain dimensions")
    tree_width, tree_height = source.size
    terrain_pixels = list(terrain.get_flattened_data())
    if land is None:
        land = ~np.isin(
            np.array(terrain_pixels, dtype=np.uint8).reshape(full_height, full_width),
            np.array(sorted(WATER_PALETTE), dtype=np.uint8),
        )
    if land.shape != (full_height, full_width):
        raise ValueError("land mask does not match terrain dimensions")
    rejected = relief.rejected_tree_cells(land, (tree_height, tree_width))
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
            tree_index = ty * tree_width + tx
            if rejected[ty, tx]:
                value = 0
            else:
                counts = Counter(palette_types.get(terrain_pixels[index], "unknown") for index in full_indices)
                terrain_type = max(counts, key=lambda value: (counts[value], value))
                probability = tree_probability(terrain_type)
                value = 6 if stable_unit_hash(tx, ty, 23) < probability and stable_unit_hash(tx, ty, 29) < 0.65 else 5 if stable_unit_hash(tx, ty, 23) < probability else 0
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


def shared_river_corridor(
    provinces: Image.Image,
    indices_by_province: Mapping[int, Sequence[int]],
) -> frozenset[int]:
    """Return the river corridor for the city provinces both builders cover.

    The corridor is computed with the relief builder's own helper against the
    same frozen scope, so both owners of ``map/terrain.bmp`` agree on which
    pixels stay a readable bank in whichever order they are applied.
    """

    shared = set(indices_by_province) & set(
        relief.load_scope()["urban_river_provinces"]
    )
    if not shared:
        return frozenset()
    width, height = provinces.size
    pixel_count = width * height
    with Image.open(BytesIO(RIVERS_PATH.read_bytes())) as rivers:
        if rivers.size != provinces.size:
            raise RuntimeError("rivers.bmp dimensions differ from provinces.bmp")
        channel = frozenset(river_corridor_indices(rivers, 0))
    corridor: set[int] = set()
    for province_id in sorted(shared):
        corridor |= relief.province_corridor(
            channel, indices_by_province[province_id], width, pixel_count
        )
    return frozenset(corridor)


def target_share(province_id: int, terrain_type: str) -> float:
    if terrain_type == "urban":
        return 1.0
    return 0.70 if province_id in NEW_PROVINCE_IDS else 0.65


@dataclass
class BuildOutputs:
    terrain: Image.Image
    trees: Image.Image
    terrain_changes: dict[int, TerrainChange]
    tree_changes: set[int]


def build_expected() -> BuildOutputs:
    definition = read_definition()
    with Image.open(BytesIO(PROVINCES_PATH.read_bytes())) as provinces_source:
        provinces = provinces_source.copy()
    with Image.open(BytesIO(TERRAIN_PATH.read_bytes())) as terrain_source:
        terrain = terrain_source.copy()
    with Image.open(BytesIO(HEIGHTMAP_PATH.read_bytes())) as height_source:
        heightmap = height_source.copy()
    with Image.open(BytesIO(TREES_PATH.read_bytes())) as tree_source:
        trees = tree_source.copy()
    if terrain.mode != "P" or heightmap.mode != "L" or trees.mode != "P":
        raise RuntimeError("unexpected map bitmap modes")
    if terrain.size != provinces.size or heightmap.size != provinces.size:
        raise RuntimeError("terrain/heightmap/provinces dimensions differ")

    indices_by_province = collect_target_indices(provinces, definition)
    # Relief is read-only here: the terrain scoring wants to know which pixels sit
    # high and steep, but the heightmap belongs to the relief builder.
    heights = heightmap.tobytes()
    corridor = shared_river_corridor(provinces, indices_by_province)

    terrain_pixels = bytearray(terrain.get_flattened_data())
    terrain_changes: dict[int, TerrainChange] = {}
    for province_id in sorted(TARGET_PROVINCE_IDS):
        desired = definition[province_id].terrain
        terrain_changes[province_id] = align_province_terrain(
            terrain_pixels, heights, terrain.width, terrain.height,
            indices_by_province[province_id], desired, province_id,
            PALETTE_TYPES, target_share(province_id, desired), corridor,
        )
    generated_terrain = terrain.copy()
    generated_terrain.putdata(terrain_pixels)

    target_mask = bytearray(terrain.width * terrain.height)
    for indices in indices_by_province.values():
        for index in indices:
            target_mask[index] = 1
    # Read through the shared parser: ``terrain_code_field`` needs the library's
    # row type, and its land flag comes from definition.csv rather than from the
    # water palette.
    _codes, land, _names = relief.terrain_code_field(
        provinces, relief.read_definition(DEFINITION_PATH)
    )
    trees, tree_changes = render_tree_patch(
        trees, generated_terrain, target_mask, PALETTE_TYPES, land
    )
    return BuildOutputs(generated_terrain, trees, terrain_changes, tree_changes)


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
    _save_atomic(outputs.terrain, TERRAIN_PATH)
    _save_atomic(outputs.trees, TREES_PATH)
    return outputs


def validate() -> list[str]:
    outputs = build_expected()
    expected = {
        TERRAIN_PATH: outputs.terrain,
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
        print(
            f"Aligned {len(TARGET_PROVINCE_IDS)} provinces: "
            f"{terrain_pixels} terrain pixels, {len(outputs.tree_changes)} tree cells."
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
