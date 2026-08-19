"""Shared deterministic helpers for the HOI4 map raster builders.

The Clausewitz map layers are strongly coupled: ``map/definition.csv`` declares
the gameplay terrain, ``map/terrain.bmp`` decides what the player sees,
``map/heightmap.bmp`` drives relief and the derived ``map/world_normal.bmp``,
``map/rivers.bmp`` carries the channel topology and ``map/trees.bmp`` is a
low-resolution vegetation mask.  Every helper here is pure, deterministic and
free of floating-point accumulation order surprises so the builders that use it
stay idempotent.

This module owns no output of its own.
"""

from __future__ import annotations

import csv
from array import array
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping, Sequence

from PIL import Image


WATER_PALETTE = frozenset({14, 15})
URBAN_PALETTE = 13

# ``common/terrain/00_terrain.txt`` maps every graphical palette index onto a
# terrain category.  Keep this table in sync with that file.
PALETTE_TYPES: Mapping[int, str] = {
    0: "plains", 1: "forest", 2: "hills", 3: "desert", 4: "forest",
    5: "plains", 6: "mountain", 7: "desert", 8: "desert", 9: "marsh",
    10: "mountain", 11: "mountain", 12: "desert", 13: "urban",
    14: "lakes", 15: "ocean", 16: "mountain", 17: "hills",
    18: "mountain", 19: "plains", 20: "mountain", 21: "jungle",
    22: "jungle", 27: "mountain", 31: "mountain",
}

# Palette indices used when a builder needs to *write* a category.  The first
# entry is the primary index and the rest provide local variety so a repaint
# never degenerates into a single flat colour.
CATEGORY_PALETTE: Mapping[str, tuple[int, ...]] = {
    "plains": (0, 5),
    "forest": (4, 1),
    "hills": (17, 2),
    "mountain": (20, 11, 10),
    "marsh": (9,),
    "desert": (3, 7, 8, 12),
    "urban": (13,),
}

# Declared terrain values in definition.csv that have no graphical palette
# index at all, so their provinces can never be made visually readable.
UNPAINTABLE_TERRAIN = frozenset({"contaminated", "vorkernsberg", "unknown"})

SEA_LEVEL = 95
MIN_LAND_HEIGHT = 96


@dataclass(frozen=True)
class DefinitionRow:
    """One ``map/definition.csv`` record."""

    province_id: int
    color: tuple[int, int, int]
    kind: str
    coastal: bool
    terrain: str
    continent: int

    @property
    def is_land(self) -> bool:
        return self.kind == "land"


def read_definition(path: Path) -> dict[int, DefinitionRow]:
    """Parse ``definition.csv`` strictly, preserving its declared order."""

    rows: dict[int, DefinitionRow] = {}
    with path.open(encoding="utf-8-sig", newline="") as handle:
        for fields in csv.reader(handle, delimiter=";"):
            if len(fields) < 8 or not fields[0].isdigit():
                continue
            province_id = int(fields[0])
            if province_id in rows:
                raise RuntimeError(f"definition.csv: duplicate province id {province_id}")
            rows[province_id] = DefinitionRow(
                province_id,
                (int(fields[1]), int(fields[2]), int(fields[3])),
                fields[4],
                fields[5].strip().lower() == "true",
                fields[6],
                int(fields[7]),
            )
    if not rows:
        raise RuntimeError("definition.csv: no province rows parsed")
    return rows


def packed_colour(colour: Sequence[int]) -> int:
    red, green, blue = colour
    return (red << 16) | (green << 8) | blue


def packed_province_values(provinces: Image.Image) -> list[int]:
    """Return one packed 24-bit colour per pixel of ``provinces.bmp``.

    The three channel views come from C-speed strided slices of the raw buffer,
    so a full 5632x2048 province bitmap only pays for one Python zip pass.
    """

    if provinces.mode != "RGB":
        provinces = provinces.convert("RGB")
    raw = provinces.tobytes()
    expected = provinces.width * provinces.height
    if len(raw) != expected * 3:
        raise RuntimeError("provinces.bmp buffer is not three bytes per pixel")
    values = [
        (red << 16) | (green << 8) | blue
        for red, green, blue in zip(raw[0::3], raw[1::3], raw[2::3])
    ]
    if len(values) != expected:
        raise RuntimeError("province colour packing produced the wrong pixel count")
    return values


def province_pixel_index(
    provinces: Image.Image,
    definition: Mapping[int, DefinitionRow],
    wanted: Iterable[int],
) -> tuple[dict[int, list[int]], bytearray]:
    """Index the pixels of ``wanted`` provinces and flag every water pixel.

    Returns ``(indices_by_province, water_mask)`` where ``water_mask`` marks
    every pixel whose province is a sea or lake province, plus any pixel whose
    colour is absent from ``definition.csv``.  Both results come from a single
    pass over the packed province colours.
    """

    wanted_ids = set(wanted)
    missing = sorted(wanted_ids - set(definition))
    if missing:
        raise RuntimeError(f"definition.csv: missing requested provinces {missing}")

    province_by_colour: dict[int, int] = {}
    for row in definition.values():
        key = packed_colour(row.color)
        if key in province_by_colour:
            raise RuntimeError(f"definition.csv: duplicate colour for province {row.province_id}")
        province_by_colour[key] = row.province_id
    water_colours = {
        packed_colour(row.color) for row in definition.values() if not row.is_land
    }
    wanted_colours = {
        packed_colour(definition[province_id].color): province_id
        for province_id in wanted_ids
    }

    values = packed_province_values(provinces)
    indices: dict[int, list[int]] = {province_id: [] for province_id in wanted_ids}
    water = bytearray(len(values))
    for index, value in enumerate(values):
        if value in water_colours:
            water[index] = 1
        elif value not in province_by_colour:
            water[index] = 1
        province_id = wanted_colours.get(value)
        if province_id is not None:
            indices[province_id].append(index)
    empty = sorted(province_id for province_id, pixels in indices.items() if not pixels)
    if empty:
        raise RuntimeError(f"provinces.bmp: requested provinces have no pixels {empty}")
    return indices, water


def stable_unit_hash(x: int, y: int, salt: int) -> float:
    """Return a deterministic value in ``[0, 1)`` for one integer lattice cell."""

    value = (x * 73856093) ^ (y * 19349663) ^ (salt * 83492791)
    value = (value ^ (value >> 13)) * 1274126177
    return ((value ^ (value >> 16)) & 0xFFFFFFFF) / 0xFFFFFFFF


def _smoothstep(fraction: float) -> float:
    return fraction * fraction * (3.0 - 2.0 * fraction)


def value_noise(x: float, y: float, cell: int, salt: int) -> float:
    """Return smooth deterministic value noise in ``[-1, 1]``."""

    if cell <= 0:
        raise ValueError("noise cell size must be positive")
    gx = int(x // cell)
    gy = int(y // cell)
    fx = _smoothstep((x - gx * cell) / cell)
    fy = _smoothstep((y - gy * cell) / cell)
    c00 = stable_unit_hash(gx, gy, salt)
    c10 = stable_unit_hash(gx + 1, gy, salt)
    c01 = stable_unit_hash(gx, gy + 1, salt)
    c11 = stable_unit_hash(gx + 1, gy + 1, salt)
    top = c00 + (c10 - c00) * fx
    bottom = c01 + (c11 - c01) * fx
    return (top + (bottom - top) * fy) * 2.0 - 1.0


def fbm(x: float, y: float, cell: int, salt: int, octaves: int = 4) -> float:
    """Return fractal value noise in roughly ``[-1, 1]``."""

    total = 0.0
    amplitude = 1.0
    normaliser = 0.0
    size = cell
    for octave in range(octaves):
        if size < 1:
            break
        total += amplitude * value_noise(x, y, size, salt + octave * 7919)
        normaliser += amplitude
        amplitude *= 0.5
        size //= 2
    return total / normaliser if normaliser else 0.0


def warped_fbm(x: float, y: float, cell: int, salt: int, octaves: int = 4) -> float:
    """Return domain-warped fractal noise, which reads as organic terrain."""

    warp = cell * 0.45
    wx = x + warp * value_noise(x, y, cell * 2, salt + 104729)
    wy = y + warp * value_noise(x, y, cell * 2, salt + 224737)
    return fbm(wx, wy, cell, salt, octaves)


def neighbours4(index: int, width: int, pixel_count: int) -> tuple[int, ...]:
    x = index % width
    result: list[int] = []
    if x:
        result.append(index - 1)
    if x + 1 < width:
        result.append(index + 1)
    if index >= width:
        result.append(index - width)
    if index + width < pixel_count:
        result.append(index + width)
    return tuple(result)


def bounded_distance(
    sources: Iterable[int],
    inside: set[int],
    width: int,
    pixel_count: int,
    limit: int,
) -> dict[int, int]:
    """Breadth-first 4-connected distance from ``sources`` inside ``inside``."""

    distance: dict[int, int] = {}
    frontier: deque[int] = deque()
    for index in sources:
        if index in inside:
            distance[index] = 0
            frontier.append(index)
    while frontier:
        index = frontier.popleft()
        current = distance[index]
        if current >= limit:
            continue
        for neighbour in neighbours4(index, width, pixel_count):
            if neighbour in inside and neighbour not in distance:
                distance[neighbour] = current + 1
                frontier.append(neighbour)
    return distance


def inward_distance(region: set[int], width: int, pixel_count: int) -> dict[int, int]:
    """Return the 4-connected distance of every ``region`` pixel from its edge."""

    edge = [
        index
        for index in region
        if any(
            neighbour not in region
            for neighbour in neighbours4(index, width, pixel_count)
        )
        or len(neighbours4(index, width, pixel_count)) < 4
    ]
    distance = bounded_distance(edge, region, width, pixel_count, len(region))
    for index in region:
        distance.setdefault(index, 0)
    return distance


def limit_gradient(
    heights: bytearray,
    region: Sequence[int],
    width: int,
    pixel_count: int,
    maximum_step: int,
    sweeps: int = 24,
) -> int:
    """Flatten every in-region step above ``maximum_step`` without cliffs.

    The relaxation is a deterministic ordered Jacobi sweep: each pass walks the
    region in ascending index order and pulls the lower side of an excessive
    step upwards.  Returns the number of pixels that moved.
    """

    if maximum_step < 1:
        raise ValueError("maximum step must be at least one height unit")
    inside = set(region)
    ordered = sorted(inside)
    moved: set[int] = set()
    for _sweep in range(sweeps):
        changed = False
        for index in ordered:
            current = heights[index]
            highest = current
            for neighbour in neighbours4(index, width, pixel_count):
                if neighbour in inside and heights[neighbour] > highest:
                    highest = heights[neighbour]
            if highest - current > maximum_step:
                heights[index] = min(255, highest - maximum_step)
                moved.add(index)
                changed = True
        for index in reversed(ordered):
            current = heights[index]
            highest = current
            for neighbour in neighbours4(index, width, pixel_count):
                if neighbour in inside and heights[neighbour] > highest:
                    highest = heights[neighbour]
            if highest - current > maximum_step:
                heights[index] = min(255, highest - maximum_step)
                moved.add(index)
                changed = True
        if not changed:
            break
    return len(moved)


def maximum_gradient(
    heights: Sequence[int],
    region: Iterable[int],
    width: int,
    pixel_count: int,
) -> int:
    """Return the largest 4-connected height step wholly inside ``region``."""

    inside = set(region)
    worst = 0
    for index in inside:
        for neighbour in neighbours4(index, width, pixel_count):
            if neighbour in inside:
                worst = max(worst, abs(heights[index] - heights[neighbour]))
    return worst


def smooth_region(
    heights: bytearray,
    region: Sequence[int],
    width: int,
    pixel_count: int,
    passes: int = 1,
) -> None:
    """Average every ``region`` pixel with its in-region 4-neighbours."""

    inside = set(region)
    ordered = sorted(inside)
    for _pass in range(passes):
        snapshot = {index: heights[index] for index in ordered}
        for index in ordered:
            total = snapshot[index] * 2
            count = 2
            for neighbour in neighbours4(index, width, pixel_count):
                if neighbour in inside:
                    total += snapshot[neighbour]
                    count += 1
            heights[index] = max(0, min(255, (total + count // 2) // count))


def river_corridor_indices(
    rivers: Image.Image,
    radius: int,
    restrict: Iterable[int] | None = None,
) -> set[int]:
    """Return the channel pixels plus a ``radius`` bank on both sides.

    ``map/rivers.bmp`` reserves palette indices ``0..11`` for sources, flow
    markers and channel widths; ``254`` and ``255`` are the land and sea
    backgrounds.  Nothing here writes to rivers.bmp - the corridor is the set of
    pixels that other layers must keep clear of city masonry so the channel
    stays visually readable through a town.
    """

    if rivers.mode != "P":
        raise RuntimeError(f"rivers.bmp must be paletted, found {rivers.mode}")
    if radius < 0:
        raise ValueError("corridor radius cannot be negative")
    width, height = rivers.size
    pixel_count = width * height
    channel = [index for index, value in enumerate(rivers.tobytes()) if value <= 11]
    if restrict is not None:
        allowed = set(restrict)
        seeds = [index for index in channel if index in allowed]
    else:
        allowed = None
        seeds = channel
    corridor = set(seeds)
    frontier = set(seeds)
    for _step in range(radius):
        grown: set[int] = set()
        for index in frontier:
            for neighbour in neighbours4(index, width, pixel_count):
                if neighbour in corridor:
                    continue
                if allowed is not None and neighbour not in allowed:
                    continue
                grown.add(neighbour)
        corridor |= grown
        frontier = grown
        if not frontier:
            break
    return corridor


def downsampled_fraction(
    mask: bytearray,
    size: tuple[int, int],
    target: tuple[int, int],
) -> list[float]:
    """Return the mean of ``mask`` over each cell of a lower-resolution grid.

    Pillow's box filter does the averaging in C, which keeps the tree-mask
    passes affordable on a full-resolution 5632x2048 water mask.
    """

    width, height = size
    if len(mask) != width * height:
        raise ValueError("mask does not match the declared size")
    source = Image.frombytes("L", size, bytes(255 if value else 0 for value in mask))
    reduced = source.resize(target, Image.BOX)
    return [value / 255.0 for value in reduced.tobytes()]


def save_bitmap_atomically(image: Image.Image, path: Path) -> None:
    """Write ``image`` to ``path`` as an uncompressed BMP via a temporary file."""

    import os

    temporary = path.with_suffix(path.suffix + ".tmp")
    try:
        image.save(temporary, format="BMP")
        with temporary.open("r+b") as stream:
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)
