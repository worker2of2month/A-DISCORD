"""Shared shoreline clearance for generated tree and city-model layers.

HOI4 places tree and city meshes with a small random offset around their
source pixels, so a mesh generated on the last dry pixel can float over the
water.  Every builder that writes ``map/trees.bmp`` or urban palette pixels in
``map/terrain.bmp`` uses these masks so that repeated passes agree exactly.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
from scipy.ndimage import distance_transform_edt

# Dry pixels whose Euclidean distance to sea or lake is at most this value
# never carry city meshes (urban palette 13 falls back to plains palette 0).
URBAN_CLEARANCE_PIXELS = 2.0
# A tree cell is cleared when any full-resolution pixel of its footprint lies
# within this distance of sea or lake.
TREE_CLEARANCE_PIXELS = 2.0
URBAN_FALLBACK_PALETTE = 0
# Settlement provinces too small to host a compact urban footprint behind the
# band keep their whole dry area eligible (9327: 46 pixels, 12 inland).
URBAN_CLEARANCE_EXEMPT_PROVINCES = frozenset({9327})

_CACHE: dict[tuple, np.ndarray] = {}


def water_colours(definition: Path | str | bytes) -> set[int]:
    """Return packed RGB values of every sea and lake province."""
    if isinstance(definition, (str, Path)):
        text = Path(definition).read_text(encoding="utf-8-sig", errors="strict")
    else:
        text = definition.decode("utf-8-sig")
    result: set[int] = set()
    for line in text.splitlines():
        fields = line.split(";")
        if len(fields) < 5 or not fields[0].isdigit():
            continue
        if fields[4] in ("sea", "lake"):
            red, green, blue = map(int, fields[1:4])
            result.add((red << 16) | (green << 8) | blue)
    return result


def province_colours(definition: Path | str | bytes, province_ids) -> set[int]:
    """Return packed RGB values of the given province IDs."""
    if isinstance(definition, (str, Path)):
        text = Path(definition).read_text(encoding="utf-8-sig", errors="strict")
    else:
        text = definition.decode("utf-8-sig")
    wanted = set(province_ids)
    result: set[int] = set()
    for line in text.splitlines():
        fields = line.split(";")
        if len(fields) >= 4 and fields[0].isdigit() and int(fields[0]) in wanted:
            red, green, blue = map(int, fields[1:4])
            result.add((red << 16) | (green << 8) | blue)
    return result


def water_mask(provinces_rgb: np.ndarray, colours: set[int]) -> np.ndarray:
    packed = (
        (provinces_rgb[..., 0].astype(np.uint32) << 16)
        | (provinces_rgb[..., 1].astype(np.uint32) << 8)
        | provinces_rgb[..., 2].astype(np.uint32)
    )
    return np.isin(packed, np.fromiter(colours, dtype=np.uint32, count=len(colours)))


def shore_distance(water: np.ndarray) -> np.ndarray:
    """Distance of every pixel to the nearest water pixel (0 on water)."""
    key = ("distance", water.shape, hash(np.packbits(water).tobytes()))
    if key not in _CACHE:
        _CACHE.clear()
        _CACHE[key] = distance_transform_edt(~water)
    return _CACHE[key]


def urban_blocked(
    water: np.ndarray,
    provinces_rgb: np.ndarray | None = None,
    definition: Path | str | bytes | None = None,
) -> np.ndarray:
    """Pixels that must not carry the urban palette: water and its shore band.

    With ``provinces_rgb`` and ``definition`` the exempt settlement provinces
    are removed from the band (their water pixels stay blocked).
    """
    blocked = shore_distance(water) <= URBAN_CLEARANCE_PIXELS
    if provinces_rgb is not None and definition is not None:
        exempt = water_mask(
            provinces_rgb,
            province_colours(definition, URBAN_CLEARANCE_EXEMPT_PROVINCES),
        )
        blocked &= ~exempt | water
    return blocked


def tree_cells_blocked(water: np.ndarray, tree_width: int, tree_height: int) -> np.ndarray:
    """Boolean (tree_height, tree_width) mask of tree cells too close to water.

    Cell footprints use the same integer bounds as the IVN tree sampler.
    """
    height, width = water.shape
    near = shore_distance(water) <= TREE_CLEARANCE_PIXELS
    xs = (np.arange(tree_width + 1) * width) // tree_width
    ys = (np.arange(tree_height + 1) * height) // tree_height
    # Summed-area table gives any() over each rectangular footprint.
    table = np.zeros((height + 1, width + 1), dtype=np.int64)
    table[1:, 1:] = near.cumsum(0).cumsum(1)
    y0, y1 = ys[:-1][:, None], ys[1:][:, None]
    x0, x1 = xs[:-1][None, :], xs[1:][None, :]
    counts = table[y1, x1] - table[y0, x1] - table[y1, x0] + table[y0, x0]
    return counts > 0
