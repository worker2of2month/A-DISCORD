"""Vectorised field math for the HOI4 relief and normal-map passes.

The map is 5632x2048, so a full-map relief pass touches 11.5 million pixels and
a per-pixel Python loop cannot finish inside the builder check timeout.  These
helpers do the same arithmetic as the scalar versions in
:mod:`tools.lib.map_raster` with NumPy, and :func:`value_noise` is bit-for-bit
identical to :func:`tools.lib.map_raster.value_noise` so the two can be tested
against each other.

Nothing here reads or writes a file; this module owns no output.

Design notes
------------
``heightmap.bmp`` on this map is quantised: the inherited terrain was linearly
stretched by 5/3 at some point, so only every third or so integer is populated
and 68.5% of neighbouring land pixels sit at exactly the same value.  A gentle
slope is therefore unrepresentable, which is why flanks read as dead-flat
plateaus separated by single-pixel steps.  :func:`dequantise` restores the
missing sub-rung detail with band-limited noise.

``world_normal.bmp`` is not a unit-length tangent-space normal.  It is an
unnormalised Sobel encoding with the blue channel pinned, which is why
:func:`sobel_normal` deliberately skips normalisation.
"""

from __future__ import annotations

from typing import Iterable, Sequence

import numpy as np

UINT32_MAX = 4294967295.0

# Vanilla HOI4 treats heights below 95 as water.  This map stores every water
# pixel as exactly 89 and its lowest land pixel as 97; both invariants are
# asserted by the builders so a relief pass can never move the coastline.
WATER_HEIGHT = 89
SEA_LEVEL = 95
MIN_LAND_HEIGHT = 97


def hash_unit(gx: np.ndarray, gy: np.ndarray, salt: int) -> np.ndarray:
    """Return deterministic values in ``[0, 1)`` for an integer lattice.

    Matches :func:`tools.lib.map_raster.stable_unit_hash` exactly.  The scalar
    version uses Python's arbitrary-precision integers, but only the low 32 bits
    survive its final mask, and those depend solely on the low 48 bits of the
    intermediate product - so 64-bit wraparound here is not an approximation.
    """

    x = gx.astype(np.int64) * np.int64(73856093)
    y = gy.astype(np.int64) * np.int64(19349663)
    mixed = np.bitwise_xor(np.bitwise_xor(x, y), np.int64(salt) * np.int64(83492791))
    value = mixed.astype(np.uint64)
    value = (value ^ (value >> np.uint64(13))) * np.uint64(1274126177)
    value = (value ^ (value >> np.uint64(16))) & np.uint64(0xFFFFFFFF)
    return (value.astype(np.float64) / UINT32_MAX).astype(np.float32)


def _smoothstep(fraction: np.ndarray) -> np.ndarray:
    return fraction * fraction * (np.float32(3.0) - np.float32(2.0) * fraction)


def value_noise(x: np.ndarray, y: np.ndarray, cell: int, salt: int) -> np.ndarray:
    """Return smooth deterministic value noise in ``[-1, 1]``."""

    if cell <= 0:
        raise ValueError("noise cell size must be positive")
    gx = np.floor_divide(x, cell).astype(np.int64)
    gy = np.floor_divide(y, cell).astype(np.int64)
    fx = _smoothstep(((x - gx * cell) / cell).astype(np.float32))
    fy = _smoothstep(((y - gy * cell) / cell).astype(np.float32))
    c00 = hash_unit(gx, gy, salt)
    c10 = hash_unit(gx + 1, gy, salt)
    c01 = hash_unit(gx, gy + 1, salt)
    c11 = hash_unit(gx + 1, gy + 1, salt)
    top = c00 + (c10 - c00) * fx
    bottom = c01 + (c11 - c01) * fx
    return (top + (bottom - top) * fy) * np.float32(2.0) - np.float32(1.0)


def fbm(x: np.ndarray, y: np.ndarray, cell: int, salt: int, octaves: int = 4) -> np.ndarray:
    """Return fractal value noise in roughly ``[-1, 1]``."""

    total = np.zeros(x.shape, dtype=np.float32)
    amplitude = 1.0
    normaliser = 0.0
    size = cell
    for octave in range(octaves):
        if size < 1:
            break
        total += np.float32(amplitude) * value_noise(x, y, size, salt + octave * 7919)
        normaliser += amplitude
        amplitude *= 0.5
        size //= 2
    if normaliser:
        total /= np.float32(normaliser)
    return total


def warped_fbm(
    x: np.ndarray, y: np.ndarray, cell: int, salt: int, octaves: int = 4
) -> np.ndarray:
    """Return domain-warped fractal noise, which reads as organic terrain."""

    warp = np.float32(cell * 0.45)
    wx = x + warp * value_noise(x, y, cell * 2, salt + 104729)
    wy = y + warp * value_noise(x, y, cell * 2, salt + 224737)
    return fbm(wx, wy, cell, salt, octaves)


def ridged(
    x: np.ndarray,
    y: np.ndarray,
    cell: int,
    salt: int,
    trend_degrees: float,
    across_scale: float,
    sharpness: float,
    octaves: int = 4,
) -> np.ndarray:
    """Return an anisotropic ridged crest field in ``[0, 1]``.

    Rotating into a range's strike and compressing the across-strike axis turns
    isotropic fractal noise into linked ridge lines with perpendicular spurs,
    which is what a real massif looks like from above.
    """

    angle = np.deg2rad(np.float32(trend_degrees))
    along = x * np.float32(np.cos(angle)) + y * np.float32(np.sin(angle))
    across = (
        -x * np.float32(np.sin(angle)) + y * np.float32(np.cos(angle))
    ) * np.float32(across_scale)
    crest = np.float32(1.0) - np.abs(warped_fbm(along, across, cell, salt, octaves))
    return np.power(np.clip(crest, 0.0, 1.0), np.float32(sharpness))


def coordinate_grid(
    shape: tuple[int, int], y_offset: int = 0
) -> tuple[np.ndarray, np.ndarray]:
    """Return float32 ``(xs, ys)`` grids for one horizontal stripe."""

    height, width = shape
    xs = np.tile(np.arange(width, dtype=np.float32), (height, 1))
    ys = np.repeat(
        np.arange(y_offset, y_offset + height, dtype=np.float32)[:, None], width, axis=1
    )
    return xs, ys


def striped_field(
    shape: tuple[int, int],
    builder,
    stripe_rows: int = 256,
    dtype=np.float32,
) -> np.ndarray:
    """Evaluate ``builder(xs, ys)`` over the map in memory-bounded stripes."""

    height, width = shape
    result = np.empty((height, width), dtype=dtype)
    for start in range(0, height, stripe_rows):
        stop = min(height, start + stripe_rows)
        xs, ys = coordinate_grid((stop - start, width), start)
        result[start:stop] = builder(xs, ys)
    return result


def edge_distance(mask: np.ndarray, limit: int) -> np.ndarray:
    """Return the 4-connected distance of every ``mask`` pixel from its edge.

    Distances saturate at ``limit``, which keeps the iteration count bounded -
    a coastal ramp only needs the first dozen pixels of the shore.
    """

    if limit < 1:
        raise ValueError("distance limit must be at least one pixel")
    distance = np.zeros(mask.shape, dtype=np.int16)
    inside = mask.copy()
    for step in range(1, limit + 1):
        shrunk = inside.copy()
        shrunk[1:, :] &= inside[:-1, :]
        shrunk[:-1, :] &= inside[1:, :]
        shrunk[:, 1:] &= inside[:, :-1]
        shrunk[:, :-1] &= inside[:, 1:]
        # Pixels on the array border have no outside neighbour to consult, so
        # treat the map edge as solid rather than as a coastline.
        distance[shrunk] = step
        inside = shrunk
        if not inside.any():
            break
    return distance


def spread_maximum(
    field: np.ndarray, mask: np.ndarray, steps: int, decay: float
) -> np.ndarray:
    """Grow the strongest values of ``field`` outwards with a linear decay.

    Averaging across a province border would drag a mountain core down to its
    plains neighbour's amplitude.  Spreading the maximum instead keeps the range
    at full height and lets its foothills reach a few pixels into the
    neighbouring provinces, which is how a real massif meets its lowland.
    """

    current = np.where(mask, field, np.float32(-1.0)).astype(np.float32)
    for _step in range(steps):
        shifted = current.copy()
        shifted[1:, :] = np.maximum(shifted[1:, :], current[:-1, :] - np.float32(decay))
        shifted[:-1, :] = np.maximum(shifted[:-1, :], current[1:, :] - np.float32(decay))
        shifted[:, 1:] = np.maximum(shifted[:, 1:], current[:, :-1] - np.float32(decay))
        shifted[:, :-1] = np.maximum(shifted[:, :-1], current[:, 1:] - np.float32(decay))
        current = np.where(mask, shifted, np.float32(-1.0))
    return np.where(mask, current, np.float32(0.0))


def masked_blur(values: np.ndarray, mask: np.ndarray, passes: int = 1) -> np.ndarray:
    """Average each masked pixel with its masked 4-neighbours.

    Water is excluded from the average so a shoreline pixel is never pulled down
    towards sub-sea-level water, which would move the coast.
    """

    weight = mask.astype(np.float32)
    current = np.where(mask, values, np.float32(0.0)).astype(np.float32)
    for _pass in range(passes):
        total = current * np.float32(2.0)
        count = weight * np.float32(2.0)
        for axis, shift in ((0, 1), (0, -1), (1, 1), (1, -1)):
            total += np.roll(current, shift, axis=axis) * np.roll(weight, shift, axis=axis)
            count += np.roll(weight, shift, axis=axis)
        current = np.where(mask, total / np.maximum(count, np.float32(1e-6)), np.float32(0.0))
    return current


def neighbour_step_histogram(
    heights: np.ndarray, mask: np.ndarray, maximum: int = 64
) -> tuple[np.ndarray, int, float]:
    """Return the 4-neighbour absolute step histogram over ``mask`` pairs.

    Both pixels of a pair must be inside ``mask``, so the shoreline drop into
    water never enters the statistics.  Returns ``(histogram, pairs, mean)``.
    """

    values = heights.astype(np.int32)
    steps: list[np.ndarray] = []
    horizontal = mask[:, :-1] & mask[:, 1:]
    steps.append(np.abs(values[:, :-1] - values[:, 1:])[horizontal])
    vertical = mask[:-1, :] & mask[1:, :]
    steps.append(np.abs(values[:-1, :] - values[1:, :])[vertical])
    joined = np.concatenate(steps)
    histogram = np.bincount(np.minimum(joined, maximum), minlength=maximum + 1)
    return histogram, int(joined.size), float(joined.mean()) if joined.size else 0.0


def dequantise(
    heights: np.ndarray,
    land: np.ndarray,
    amplitude: np.ndarray,
    cell: int,
    salt: int,
    strength: float,
) -> np.ndarray:
    """Restore sub-rung detail to a heightmap that was stretched and rounded.

    The result is a float field; the caller is responsible for clamping and
    rounding so the land/sea mask cannot move.
    """

    detail = striped_field(
        heights.shape, lambda xs, ys: warped_fbm(xs, ys, cell, salt, octaves=3)
    )
    smoothed = masked_blur(heights.astype(np.float32), land, passes=1)
    return np.where(
        land,
        smoothed + detail * amplitude * np.float32(strength),
        heights.astype(np.float32),
    )


def corridor_allowance(
    heights: np.ndarray, corridor: np.ndarray, band: int, slope: float
) -> np.ndarray:
    """Return the height ceiling that makes ``corridor`` sit in a valley.

    Every pixel within ``band`` of the corridor is allowed to stand no higher than
    the nearest corridor pixel plus ``slope`` per pixel of separation.  Applying it
    as a ceiling guarantees the banks *descend* to the channel: the defect it
    exists to remove is a river running along the top of a raised embankment,
    which is what happens when relief is added without regard to the water.

    The value and the distance propagate together, so no separate distance
    transform or nearest-neighbour lookup is needed.
    """

    if band < 1:
        raise ValueError("corridor band must be at least one pixel")
    infinite = np.float32(np.inf)
    allowance = np.where(corridor, heights.astype(np.float32), infinite).astype(np.float32)
    rise = np.float32(slope)
    for _step in range(band):
        for axis, shift in ((0, 1), (0, -1), (1, 1), (1, -1)):
            allowance = np.minimum(allowance, np.roll(allowance, shift, axis=axis) + rise)
    return allowance


def enforce_descent(
    heights: np.ndarray, corridor: np.ndarray, outlet: np.ndarray
) -> tuple[np.ndarray, int, float]:
    """Lower ``corridor`` pixels until no path climbs on its way to an outlet.

    Breadth-first from the outlets establishes how far each corridor pixel is from
    the sea; sweeping back from the far end and taking a running minimum
    downstream leaves every upstream pixel at least as high as the pixel below it.
    Only lowering is ever applied, so this cannot push a channel up through a
    ceiling, and the returned climb is the worst ascent that had to be removed.

    Returns the corrected field, the number of pixels moved and the largest climb.
    """

    height, width = heights.shape
    values = heights.astype(np.float32).copy()
    flat = values.reshape(-1)
    channel = corridor.reshape(-1)
    seeds = np.flatnonzero((outlet & corridor).reshape(-1))
    level = np.full(height * width, -1, dtype=np.int32)
    level[seeds] = 0
    frontier = list(int(index) for index in seeds)
    order: list[list[int]] = [frontier]
    offsets = (-width - 1, -width, -width + 1, -1, 1, width - 1, width, width + 1)
    while frontier:
        following: list[int] = []
        depth = len(order)
        for index in frontier:
            column = index % width
            for offset in offsets:
                neighbour = index + offset
                if neighbour < 0 or neighbour >= level.size:
                    continue
                if abs((neighbour % width) - column) > 1:
                    continue
                if not channel[neighbour] or level[neighbour] >= 0:
                    continue
                level[neighbour] = depth
                following.append(neighbour)
        if following:
            order.append(following)
        frontier = following

    moved = 0
    climb = 0.0
    for depth in range(len(order) - 1, 0, -1):
        for index in order[depth]:
            column = index % width
            upstream = flat[index]
            for offset in offsets:
                neighbour = index + offset
                if neighbour < 0 or neighbour >= level.size:
                    continue
                if abs((neighbour % width) - column) > 1:
                    continue
                if level[neighbour] != depth - 1:
                    continue
                if flat[neighbour] > upstream:
                    climb = max(climb, float(flat[neighbour] - upstream))
                    flat[neighbour] = upstream
                    moved += 1
    return values, moved, climb


def level_pads(
    heights: np.ndarray, labels: np.ndarray, mask: np.ndarray, band: int
) -> np.ndarray:
    """Flatten each labelled region to its own height, ramping out over ``band``.

    Rigid building models sink into or protrude from sloped ground, so a city or a
    landmark footprint has to be genuinely level rather than merely smooth.  Each
    region is levelled to its own median, which keeps its mean elevation where it
    was - important because the stored building heights are corrected separately -
    and means a city spread over several provinces on a hillside becomes a flight
    of level terraces rather than one implausible plane.

    The outward ramp is what stops a level surface from becoming the very defect
    this module exists to remove.  Both the level and its influence propagate
    outwards together, so the surrounding relief rises to meet the terrace instead
    of butting against a vertical rim.
    """

    if not labels.any():
        return heights.astype(np.float32)
    values = heights.astype(np.float32).copy()
    pad = labels > 0
    identifiers = np.unique(labels[pad])
    target = np.zeros(heights.shape, dtype=np.float32)
    for identifier in identifiers:
        selected = labels == identifier
        target[selected] = np.float32(float(np.median(values[selected])))

    # Propagate the terrace level and its weight outwards one ring at a time.
    reach = np.zeros(heights.shape, dtype=np.float32)
    reach[pad] = 1.0
    spread = target.copy()
    for step in range(1, band + 1):
        weight = np.float32(1.0 - step / (band + 1.0))
        grown_reach = reach.copy()
        grown_target = spread.copy()
        for axis, shift in ((0, 1), (0, -1), (1, 1), (1, -1)):
            candidate = np.roll(reach, shift, axis=axis) * weight
            better = candidate > grown_reach
            grown_reach = np.where(better, candidate, grown_reach)
            grown_target = np.where(better, np.roll(spread, shift, axis=axis), grown_target)
        keep = mask & ~pad
        reach = np.where(keep, grown_reach, reach)
        spread = np.where(keep, grown_target, spread)
    blend = np.where(pad, np.float32(1.0), np.clip(reach, 0.0, 1.0))
    return np.where(mask, values * (np.float32(1.0) - blend) + spread * blend, values)


def limit_gradient(
    heights: np.ndarray, mask: np.ndarray, maximum_step: np.ndarray, sweeps: int = 40
) -> int:
    """Raise the low side of every in-mask step above ``maximum_step``.

    ``maximum_step`` is a per-pixel cap, so declared mountain cores can keep
    steeper flanks than lowland provinces.  Returns the number of pixels moved.
    """

    values = heights.astype(np.float32)
    moved = np.zeros(heights.shape, dtype=bool)
    for _sweep in range(sweeps):
        highest = np.full(values.shape, -np.inf, dtype=np.float32)
        for axis, shift in ((0, 1), (0, -1), (1, 1), (1, -1)):
            neighbour = np.roll(values, shift, axis=axis)
            valid = np.roll(mask, shift, axis=axis)
            highest = np.maximum(highest, np.where(valid, neighbour, -np.inf))
        floor = highest - maximum_step
        needs = mask & np.isfinite(floor) & (values < floor)
        if not needs.any():
            break
        values = np.where(needs, floor, values)
        moved |= needs
    heights[...] = values
    return int(moved.sum())


def sobel_normal(heights: np.ndarray, factor: float = 1.0) -> tuple[np.ndarray, np.ndarray]:
    """Return the unnormalised Sobel encoding used by HOI4 world normals.

    ``world_normal.bmp`` is not a unit-length tangent-space normal: blue is
    pinned and the vector is never normalised.  The operator is the raw 3x3
    OpenCV Sobel pair with no division by eight, X negated, Y in screen space
    with the row index increasing downwards, evaluated at full heightmap
    resolution.  Returns ``(red, green)`` as float arrays before rounding.
    """

    values = heights.astype(np.float32)
    padded = np.pad(values, 1, mode="edge")
    north_west = padded[:-2, :-2]
    north = padded[:-2, 1:-1]
    north_east = padded[:-2, 2:]
    west = padded[1:-1, :-2]
    east = padded[1:-1, 2:]
    south_west = padded[2:, :-2]
    south = padded[2:, 1:-1]
    south_east = padded[2:, 2:]
    sobel_x = (
        (north_east + np.float32(2.0) * east + south_east)
        - (north_west + np.float32(2.0) * west + south_west)
    )
    sobel_y = (
        (south_west + np.float32(2.0) * south + south_east)
        - (north_west + np.float32(2.0) * north + north_east)
    )
    red = np.float32(128.0) - np.float32(factor) * sobel_x
    green = np.float32(128.0) + np.float32(factor) * sobel_y
    return red, green


def gradient_magnitude(heights: np.ndarray) -> np.ndarray:
    """Return the smoothed slope in height units per pixel.

    This is the Sobel magnitude divided by eight, which is the quantity the
    reference generator's per-terrain slope figures were measured with, so class
    boundaries can be compared directly against them.
    """

    red, green = sobel_normal(heights, factor=1.0)
    sobel_x = (np.float32(128.0) - red) / np.float32(8.0)
    sobel_y = (green - np.float32(128.0)) / np.float32(8.0)
    return np.sqrt(sobel_x * sobel_x + sobel_y * sobel_y)


def box_downsample(values: np.ndarray, target: tuple[int, int]) -> np.ndarray:
    """Average ``values`` down to ``target`` (height, width) with a box filter."""

    height, width = values.shape
    target_height, target_width = target
    if height % target_height or width % target_width:
        raise ValueError("box downsample requires an integer reduction factor")
    ry = height // target_height
    rx = width // target_width
    return values.reshape(target_height, ry, target_width, rx).mean(axis=(1, 3))


def encode_world_normal(
    heights: np.ndarray, target: tuple[int, int], factor: float = 1.0, blue: int = 255
) -> np.ndarray:
    """Return the ``target`` sized uint8 RGB world-normal image."""

    red, green = sobel_normal(heights, factor)
    reduced_red = box_downsample(red, target)
    reduced_green = box_downsample(green, target)
    out = np.empty((target[0], target[1], 3), dtype=np.uint8)
    out[:, :, 0] = np.clip(np.rint(reduced_red), 0, 255).astype(np.uint8)
    out[:, :, 1] = np.clip(np.rint(reduced_green), 0, 255).astype(np.uint8)
    out[:, :, 2] = blue
    return out


def cell_indices(
    shape: tuple[int, int], target: tuple[int, int]
) -> tuple[np.ndarray, np.ndarray]:
    """Return each pixel's target cell and the pixel count of every cell.

    ``trees.bmp`` is 1650x600 against a 5632x2048 map, so one cell covers 3.41
    pixels and no integer box filter exists.  This reproduces the bucketing the
    tree renderer uses: ``cell = x * target_width // width``.
    """

    height, width = shape
    target_height, target_width = target
    columns = (np.arange(width, dtype=np.int64) * target_width) // width
    rows = (np.arange(height, dtype=np.int64) * target_height) // height
    flat = (rows[:, None] * target_width + columns[None, :]).astype(np.int64)
    counts = np.bincount(flat.ravel(), minlength=target_height * target_width)
    return flat, counts.reshape(target)


def downsampled_fraction(
    mask: np.ndarray, target: tuple[int, int]
) -> np.ndarray:
    """Return the share of each target cell's footprint covered by ``mask``."""

    flat, counts = cell_indices(mask.shape, target)
    totals = np.bincount(
        flat.ravel(),
        weights=mask.reshape(-1).astype(np.float64),
        minlength=target[0] * target[1],
    ).reshape(target)
    return (totals / np.maximum(counts, 1)).astype(np.float32)


def packed_colours(provinces: np.ndarray) -> np.ndarray:
    """Return the packed 24-bit province colour of every pixel."""

    if provinces.ndim != 3 or provinces.shape[2] != 3:
        raise ValueError("provinces array must be HxWx3 RGB")
    values = provinces.astype(np.uint32)
    return (values[:, :, 0] << 16) | (values[:, :, 1] << 8) | values[:, :, 2]


def map_colours_to_codes(
    packed: np.ndarray, colours: Sequence[int], codes: Sequence[int], default: int
) -> np.ndarray:
    """Translate packed province colours into small integer codes."""

    if len(colours) != len(codes):
        raise ValueError("colour and code sequences must be the same length")
    order = np.argsort(np.asarray(colours, dtype=np.uint32), kind="stable")
    sorted_colours = np.asarray(colours, dtype=np.uint32)[order]
    sorted_codes = np.asarray(codes, dtype=np.int16)[order]
    position = np.searchsorted(sorted_colours, packed)
    position = np.minimum(position, len(sorted_colours) - 1)
    matched = sorted_colours[position] == packed
    return np.where(matched, sorted_codes[position], np.int16(default))
