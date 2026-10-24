"""Build bounded coastal, settlement and Svetlogorye mountain geography.

Province geometry and state membership remain authored inputs. Only the explicit
island masks acquire new land; mainland edits use explicit province masks.
"""

from __future__ import annotations

import argparse
from collections import defaultdict, deque
from io import BytesIO
from math import atan2
from pathlib import Path

import numpy as np
from PIL import Image
from scipy.ndimage import distance_transform_edt, gaussian_filter

from tools.builders.build_adiscord_ivn_geography import normal_from_height
from tools.builders.build_adiscord_new_states import SOUTHERN_CITIES, SOUTHERN_CITY_POINTS
from tools.lib.coastal_clearance import (
    URBAN_FALLBACK_PALETTE,
    tree_cells_blocked,
    urban_blocked,
    water_colours,
    water_mask,
)
from tools.lib.paths import repository_root


ROOT = repository_root()
MANDATE_ISLANDS = frozenset(range(16802, 16809))
ISLANDS = frozenset({16709, 16710, 16712}) | MANDATE_ISLANDS
RELIEF_PROVINCES = frozenset({
    334, 1710, 2935, 4287, 4321, 4912, 6099, 7324, 8351, 8445,
    8888, 9116, 10909, 11069, 11696, 11942, 12480, 12668,
    461, 1015, 2231, 6961, 8058, 9016, 9641, 11926, 12982,
})
RELIEF_TERRAIN = {
    **{province: "desert" for province in RELIEF_PROVINCES},
    **{province: "hills" for province in (1015, 2935, 4287, 9016, 11696, 12480, 12982)},
    **{province: "mountain" for province in (6099, 8351, 8888, 10909, 11942)},
}
# Provinces later split out of the massif keep its generated surface, while
# their combat and graphical terrain remain authored in definition.csv.
RELIEF_SURFACE_PROVINCES = RELIEF_PROVINCES | frozenset({16874, 16878, 16879, 16880, 16885, 16887, 16890})
SPLIT_PARENTS = {16707: 6008, 16708: 6008, 16711: 11627}
ANCHOR_REFERENCES = {**SPLIT_PARENTS, 16709: 65, 16710: 65, 16712: 6261}
ANCHOR_REFERENCES.update({province: 65 for province in MANDATE_ISLANDS})
DISPLACED_PROVINCES = frozenset({6008, 7739, 11627})
CITIES = frozenset(range(16713, 16722)) | frozenset(province for province, _value in SOUTHERN_CITY_POINTS.values())
ARAB_CITIES = frozenset({16713, 16714, 16715, 16718, 16719, 16720}) | frozenset(entry["province"] for entry in SOUTHERN_CITIES)
# Urban growth authored in Nudge: expanded southern cities and their new
# districts receive city rasters without becoming manifest cities.
ARAB_URBAN_GROWTH = frozenset({
    488, 971, 1349, 4089, 16745, 16746, 16751, 16753, 16784, 16785, 16786,
    16882, 16883, 16886, 16888, 16889, 16891, 16893, 16894,
})
URBAN_GROWTH = ARAB_URBAN_GROWTH | frozenset({16881, 16884, 16885, 16887, 16890, 16892})
RURAL_SECTORS = tuple(
    {**sector, "parent": city["parent"], "parent_terrain": city["parent_terrain"], "terrain": city["parent_terrain"]}
    for city in SOUTHERN_CITIES for sector in city.get("sectors", ())
)
SOUTHERN_GEOMETRY = (*SOUTHERN_CITIES, *RURAL_SECTORS)
# Break four-province corners without changing state membership or splitting a province.
# Coordinates use the top-left raster origin.
PROVINCE_CORNER_REPAIRS = {
    (3971, 1447): (971, 16746),
    (3805, 1171): (10375, 16777),
    (3957, 1149): (16788, 16787),
    (3959, 1034): (834, 16738),
}
ANCHOR_REFERENCES.update({entry["province"]: entry["parent"] for entry in SOUTHERN_CITIES})
ANCHOR_REFERENCES.update({entry["province"]: entry["parent"] for entry in RURAL_SECTORS})
DISPLACED_PROVINCES |= frozenset(entry["parent"] for entry in SOUTHERN_CITIES)
ANCHOR_REFERENCES.update({
    16713: 7968, 16714: 9659, 16715: 12876, 16716: 2038,
    16717: 8904, 16718: 12876, 16719: 2625, 16720: 9101, 16721: 689,
})
DISPLACED_PROVINCES |= frozenset({9659, 7968, 12876, 2625, 2056, 2038, 7618, 8904, 8194, 9101, 10931, 9630, 689, 8635})
# Southern Nudge splits copy unit anchors from the province that gave most of
# their pixels; every donor keeps its own anchors inside the remaining shape.
# Railways that crossed a donor are rerouted through these splits.
NUDGE_SPLIT_PARENTS = {
    16864: 8635, 16865: 689, 16866: 10967, 16867: 689, 16868: 5305,
    16869: 4025, 16870: 9211, 16871: 7079, 16872: 9633, 16873: 7618,
    16874: 2231, 16875: 8635, 16876: 3706, 16877: 5156, 16878: 2231,
    16879: 6099, 16880: 8888, 16881: 2038, 16882: 13019, 16883: 7413,
    16884: 2038, 16885: 4321, 16886: 7737, 16887: 9016, 16888: 729,
    16889: 6184, 16890: 4287, 16891: 9119, 16892: 2038, 16893: 4380,
    16894: 4380,
}
ANCHOR_REFERENCES.update(NUDGE_SPLIT_PARENTS)
# Every province whose pixels the southern Nudge pass moved, splits excluded.
NUDGE_SPLIT_DONORS = frozenset({
    461, 729, 971, 1015, 2231, 2374, 2411, 3127, 3584, 3706, 4025, 4089,
    4287, 4321, 4380, 5156, 5305, 5348, 5594, 6099, 6184, 7079, 7413, 7737,
    8452, 8888, 9016, 9119, 9211, 9633, 10967, 11069, 12458, 12668, 13019,
    13248, 13382, 13882, 16745, 16746, 16747, 16752, 16753,
})
DISPLACED_PROVINCES |= NUDGE_SPLIT_DONORS
COLOURMAP = Path("map/terrain/colormap_rgb_cityemissivemask_a.dds")


def lowland_heights(mask: np.ndarray) -> np.ndarray:
    """Rise gently from the first dry shoreline pixel toward the interior."""
    result = np.zeros(mask.shape, dtype=np.uint8)
    interior = mask.copy()
    for level in (97, 100, 103, 106):
        result[interior] = level
        padded = np.pad(interior, 1)
        interior = (
            padded[1:-1, 1:-1]
            & padded[:-2, 1:-1]
            & padded[2:, 1:-1]
            & padded[1:-1, :-2]
            & padded[1:-1, 2:]
        )
    return result


def bmp_bytes(source: Image.Image, pixels: np.ndarray, original: bytes) -> bytes:
    if original and np.array_equal(np.asarray(source), pixels):
        return original
    result = source.copy()
    result.putdata(pixels.reshape(-1).tolist())
    output = BytesIO()
    result.save(output, format="BMP")
    return output.getvalue()


def mountain_heights(mask: np.ndarray, heights: np.ndarray) -> np.ndarray:
    """Build a winding watershed, tributary valleys and bounded foothill slopes.

    Boundary samples are immutable inputs, so repeated generation cannot raise
    the land again. A six-level neighbouring-pixel limit prevents sheer walls
    where the authored footprint meets the existing lowlands.
    """
    ys, xs = np.where(mask)
    left, top = int(xs.min()) - 1, int(ys.min()) - 1
    right, bottom = int(xs.max()) + 2, int(ys.max()) + 2
    local = mask[top:bottom, left:right]
    distance, nearest = distance_transform_edt(local, return_indices=True)
    source = heights[top:bottom, left:right].astype(float)
    base = np.clip(gaussian_filter(source[tuple(nearest)], sigma=4), 100, 118)
    y, x = np.mgrid[top:bottom, left:right]
    v = y - 1453
    u = x - (3687 + 0.14 * v + 3.5 * np.sin(v / 14))
    broad = np.exp(-((u / 34) ** 2 + (v / 51) ** 2))
    crest = np.exp(-((u / 12) ** 2 + (v / 43) ** 2))
    crest *= 0.60 + 0.40 * np.cos((v + 5) / 7)
    spurs = np.cos((v + np.abs(u) * 0.85) / 5.5)
    spurs *= broad * (1 - np.exp(-(u / 8) ** 2))
    noise = np.random.default_rng(428710909).standard_normal(local.shape)
    crags = gaussian_filter(noise, sigma=1.1)
    crags /= crags.std()
    ravines = gaussian_filter(noise, sigma=3.2)
    ravines /= ravines.std()
    texture = 7 * crags + 12 * ravines
    uplift = 66 * broad + 64 * crest + 13 * spurs + texture * broad
    taper = np.clip((distance - 1) / 22, 0, 1)
    taper = taper * taper * (3 - 2 * taper)
    profile = base + uplift * taper
    interior = distance > 1
    profile[~interior] = source[~interior]
    # Lower steep edges without lifting adjacent provinces or the coastline.
    for _ in range(max(local.shape)):
        bounded = profile.copy()
        bounded[1:, :] = np.minimum(bounded[1:, :], profile[:-1, :] + 6)
        bounded[:-1, :] = np.minimum(bounded[:-1, :], profile[1:, :] + 6)
        bounded[:, 1:] = np.minimum(bounded[:, 1:], profile[:, :-1] + 6)
        bounded[:, :-1] = np.minimum(bounded[:, :-1], profile[:, 1:] + 6)
        bounded[~interior] = source[~interior]
        if np.array_equal(bounded, profile):
            break
        profile = bounded
    profile = np.rint(np.clip(profile, 0, 255)).astype(np.uint8)
    result = heights.copy()
    result[top:bottom, left:right][interior] = profile[interior]
    return result


def patch_colourmap(data: bytes, island_mask: np.ndarray, color: tuple[int, int, int, int] = (85, 105, 60, 1)) -> bytes:
    """Replace only intersecting DXT5 blocks; retain all other compressed bytes.

The water shader hides the land tint outside the shore. Painting a complete
compression block avoids repeated lossy recompression of its untouched pixels.
"""
    with Image.open(BytesIO(data)) as source:
        width, height = source.size
    if data[:4] != b"DDS " or data[84:88] != b"DXT5":
        raise ValueError("coastal colourmap requires a legacy DXT5 DDS")
    if int.from_bytes(data[28:32], "little") not in (0, 1):
        raise ValueError("coastal colourmap requires a single mip level")
    if island_mask.shape != (height * 2, width * 2):
        raise ValueError("colourmap dimensions must be half the province map")
    cells = island_mask.reshape(height, 2, width, 2).any(axis=(1, 3))
    blocks = cells.reshape(height // 4, 4, width // 4, 4).any(axis=(1, 3))
    tile = Image.new("RGBA", (4, 4), color)
    encoded = BytesIO()
    tile.save(encoded, format="DDS", pixel_format="DXT5")
    block = encoded.getvalue()[128:144]
    result = bytearray(data)
    for y, x in zip(*np.where(blocks)):
        offset = 128 + (int(y) * (width // 4) + int(x)) * 16
        result[offset:offset + 16] = block
    return bytes(result)


def closest_pixel(points: np.ndarray, x: float, y: float) -> tuple[int, int]:
    distances = (points[:, 1] - x) ** 2 + (points[:, 0] - y) ** 2
    row, column = points[int(np.argmin(distances))]
    return int(column), int(row)


def province_grid(provinces: np.ndarray, definitions: dict[int, tuple[int, int, int]]) -> np.ndarray:
    lookup = np.zeros(1 << 24, dtype=np.uint16)
    for province, (red, green, blue) in definitions.items():
        lookup[(red << 16) | (green << 8) | blue] = province
    rgb = provinces.astype(np.uint32)
    return lookup[(rgb[:, :, 0] << 16) | (rgb[:, :, 1] << 8) | rgb[:, :, 2]]


def province_neighbours(grid: np.ndarray) -> dict[int, set[int]]:
    neighbours = defaultdict(set)
    for first, second in ((grid[:-1], grid[1:]), (grid[:, :-1], grid[:, 1:])):
        mask = first != second
        pairs = np.unique(np.stack((first[mask], second[mask]), axis=1), axis=0)
        for first_id, second_id in pairs:
            neighbours[int(first_id)].add(int(second_id))
            neighbours[int(second_id)].add(int(first_id))
    return neighbours


def native_slots(kind: str, neighbour_count: int) -> set[int]:
    """Native slot ids: fixed 0, 9, 10, 21, 38 and up to eight per border row."""
    count = min(neighbour_count, 8)
    rows = (1, 22, 11, 30) if kind == "sea" else (1, 22)
    return {0, 9, 10, 21, 38} | {base + index for base in rows for index in range(count)}


def complete_native_anchors(
    province: int,
    kind: str,
    existing: dict[int, list[str]],
    grid: np.ndarray,
    heights: np.ndarray,
    neighbours: list[int],
) -> dict[int, list[str]]:
    """Keep valid rows of a native slot set and add the slots its borders now need."""
    top, bottom = np.nonzero((grid == province).any(axis=1))[0][[0, -1]]
    left, right = np.nonzero((grid == province).any(axis=0))[0][[0, -1]]
    origin_y, origin_x = max(top - 1, 0), max(left - 1, 0)
    window = grid[origin_y:bottom + 2, origin_x:right + 2]
    inside = window == province
    points = np.argwhere(inside) + (origin_y, origin_x)
    map_height = heights.shape[0]
    centre = None
    if 0 in existing:
        x = round(float(existing[0][2]))
        y = map_height - 1 - round(float(existing[0][4]))
        if grid[y, x] == province:
            centre = (x, y)
    if centre is None:
        centre = closest_pixel(points, points[:, 1].mean(), points[:, 0].mean())
    cx, cy = centre
    offset = existing[0][6] if 0 in existing else ("0.12" if kind == "sea" else "0.24")

    def row(slot: int, x: float, y: float, rotation: float) -> list[str]:
        x, y = closest_pixel(points, x, y)
        return [str(province), str(slot), f"{x:.2f}", f"{heights[y, x] / 10:.2f}",
                f"{map_height - 1 - y:.2f}", f"{rotation:.2f}", offset]

    generated = {0: row(0, cx, cy, 0.0), 9: row(9, cx - 3, cy, 1.57), 10: row(10, cx + 3, cy, -1.57),
                 21: row(21, cx - 3, cy, 0.0)}
    generated[38] = list(generated[10])
    generated[38][1] = "38"
    padded = np.pad(window, 1)
    for index, neighbour in enumerate(neighbours[:8], 1):
        touching = inside & (
            (padded[:-2, 1:-1] == neighbour) | (padded[2:, 1:-1] == neighbour)
            | (padded[1:-1, :-2] == neighbour) | (padded[1:-1, 2:] == neighbour)
        )
        ys, xs = np.nonzero(touching)
        dx = xs.mean() + origin_x - cx
        dy = ys.mean() + origin_y - cy
        length = max(float(np.hypot(dx, dy)), 1.0)
        generated[index] = row(index, cx + 3 * dx / length, cy + 3 * dy / length, atan2(dx, -dy))
        for base in (22, 11, 30):
            copy = list(generated[index])
            copy[1] = str(base + index - 1)
            generated[base + index - 1] = copy
    return {
        slot: existing[slot] if slot in existing else generated[slot]
        for slot in sorted(native_slots(kind, len(neighbours)))
    }


def unit_anchors(
    original: bytes,
    masks: dict[int, np.ndarray],
    heights: np.ndarray,
    grid: np.ndarray,
    kinds: dict[int, str],
) -> bytes:
    """Keep native unit anchors inside their provinces.

    A province has slots 0, 9, 10, 21 and 38 plus up to eight slots per border
    row (two rows on land, four at sea), sized by its neighbour count. A slot
    set copied from another province or left over from an older border is
    unsafe at game start, so every province around the southern Nudge pass
    keeps its valid rows, loses slots for borders it no longer has and gains
    the slots its new borders need. Rows stay grouped by slot type in the
    native order.
    """
    rows = [line.split(";") for line in original.decode("utf-8").splitlines()]
    neighbours = province_neighbours(grid)
    slots = defaultdict(dict)
    for row in rows:
        slots[int(row[0])][int(row[1])] = row
    touched = set(NUDGE_SPLIT_PARENTS) | NUDGE_SPLIT_DONORS
    scope = touched | {neighbour for province in touched for neighbour in neighbours[province]}
    map_height = heights.shape[0]
    rebuilt = {}
    for province in sorted(scope):
        kind = kinds.get(province)
        if kind not in ("land", "sea") or set(slots[province]) == native_slots(kind, len(neighbours[province])):
            continue
        rebuilt[province] = complete_native_anchors(
            province, kind, slots[province], grid, heights, sorted(neighbours[province])
        )
    points = {province: np.argwhere(mask) for province, mask in masks.items()}

    def normalise(row: list[str]) -> list[str]:
        province = int(row[0])
        if province in DISPLACED_PROVINCES or province in ANCHOR_REFERENCES:
            x = float(row[2])
            y = map_height - 1 - float(row[4])
            # Half-pixel anchors must resolve to the province under both
            # truncation and rounding.
            if not (masks[province][round(y), round(x)] and masks[province][int(y), int(x)]):
                x, y = closest_pixel(points[province], x, y)
                row[2:5] = [f"{x:.2f}", f"{heights[y, x] / 10:.2f}", f"{map_height - 1 - y:.2f}"]
        if province in RELIEF_PROVINCES:
            x = round(float(row[2]))
            y = map_height - 1 - round(float(row[4]))
            row[3] = f"{heights[y, x] / 10:.2f}"
        return row

    blocks = defaultdict(list)
    for row in rows:
        if int(row[0]) not in rebuilt:
            blocks[int(row[1])].append(normalise(row))
    for province, anchors in rebuilt.items():
        for slot, row in anchors.items():
            block = blocks[slot]
            index = next((i for i, other in enumerate(block) if int(other[0]) > province), len(block))
            block.insert(index, normalise(list(row)))
    newline = "\r\n" if b"\r\n" in original else "\n"
    ordered = [";".join(row) for slot in sorted(blocks) for row in blocks[slot]]
    return (newline.join(ordered) + newline).encode("utf-8")


def railway_plan(original: bytes, provinces: np.ndarray, definitions: dict[int, tuple[int, int, int]]) -> bytes:
    """Insert local sector crossings while preserving existing railway levels."""
    groups = {}
    for city in SOUTHERN_CITIES:
        members = {city["parent"], city["province"], *(sector["province"] for sector in city.get("sectors", ()))}
        groups.update({province: members for province in members})
    split_members = set(NUDGE_SPLIT_PARENTS) | set(NUDGE_SPLIT_PARENTS.values()) | DISPLACED_PROVINCES
    groups.update({province: groups.get(province, set()) | split_members for province in split_members})
    lookup = np.zeros(1 << 24, dtype=np.uint16)
    for province, (red, green, blue) in definitions.items():
        lookup[(red << 16) | (green << 8) | blue] = province
    rgb = provinces.astype(np.uint32)
    grid = lookup[(rgb[:, :, 0] << 16) | (rgb[:, :, 1] << 8) | rgb[:, :, 2]]
    adjacency = defaultdict(set)
    for first, second in ((grid[:-1], grid[1:]), (grid[:, :-1], grid[:, 1:])):
        mask = (first != second) & (np.isin(first, list(groups)) | np.isin(second, list(groups)))
        pairs = np.unique(np.sort(np.stack((first[mask], second[mask]), axis=1), axis=1), axis=0)
        for first_id, second_id in pairs:
            adjacency[int(first_id)].add(int(second_id))
            adjacency[int(second_id)].add(int(first_id))
    result = []
    for line in original.decode("utf-8").splitlines(keepends=True):
        fields = list(map(int, line.split()))
        if len(fields) < 3:
            result.append(line)
            continue
        route = fields[2:]
        repaired = [route[0]]
        for first, second in zip(route, route[1:]):
            if not ({first, second} & groups.keys()) or second in adjacency[first]:
                repaired.append(second)
                continue
            allowed = groups.get(first, {first}) | groups.get(second, {second})
            queue = deque([[first]])
            seen = {first}
            while queue:
                path = queue.popleft()
                if path[-1] == second:
                    repaired.extend(path[1:])
                    break
                for neighbour in sorted(adjacency[path[-1]] & allowed - seen):
                    seen.add(neighbour)
                    queue.append([*path, neighbour])
            else:
                raise ValueError(f"railway {first}-{second}: no route through the southern sectors")
        if repaired == route:
            result.append(line)
        else:
            ending = "\r\n" if line.endswith("\r\n") else "\n" if line.endswith("\n") else ""
            result.append(" ".join(map(str, (fields[0], len(repaired), *repaired))) + ending)
    return "".join(result).encode("utf-8")


def build_plan(root: Path = ROOT, source_overrides: dict[Path, bytes] | None = None) -> dict[Path, bytes]:
    def read(path: Path) -> bytes:
        if source_overrides and path in source_overrides:
            return source_overrides[path]
        return (root / path).read_bytes()

    definitions = {}
    definition_path = root / "map/definition.csv"
    definition_bytes = definition_path.read_bytes()
    definition_lines = definition_bytes.decode("utf-8-sig").splitlines()
    entries_by_id = {int(line.split(";")[0]): index for index, line in enumerate(definition_lines)}
    for entry in SOUTHERN_GEOMETRY:
        parent_index = entries_by_id[entry["parent"]]
        fields = definition_lines[parent_index].split(";")
        fields[6] = entry["parent_terrain"]
        definition_lines[parent_index] = ";".join(fields)
        province = entry["province"]
        if province not in entries_by_id:
            if province != max(entries_by_id) + 1:
                raise ValueError(f"province {province}: non-contiguous southern city ID")
            entries_by_id[province] = len(definition_lines)
            definition_lines.append(";".join(map(str, (province, *entry["rgb"], "land", "false", entry.get("terrain", "urban"), 3))))
        elif tuple(map(int, definition_lines[entries_by_id[province]].split(";")[1:4])) != tuple(entry["rgb"]):
            raise ValueError(f"province {province}: city ID is occupied by another color")
    sea_colors = []
    for line in definition_lines:
        fields = line.split(";")
        if len(fields) >= 8:
            definitions[int(fields[0])] = tuple(map(int, fields[1:4]))
            if fields[4] == "sea":
                red, green, blue = definitions[int(fields[0])]
                sea_colors.append((red << 16) | (green << 8) | blue)
    with Image.open(root / "map/provinces.bmp") as source:
        provinces = np.array(source.convert("RGB"))
    for entry in SOUTHERN_GEOMETRY:
        left, top = entry["origin"]
        for y, row in enumerate(entry["mask"], top):
            for x, selected_pixel in enumerate(row, left):
                if selected_pixel != "1":
                    continue
                permitted = {definitions[entry["parent"]], tuple(entry["rgb"])}
                if (x, y) in PROVINCE_CORNER_REPAIRS:
                    permitted.add(definitions[PROVINCE_CORNER_REPAIRS[x, y][1]])
                if tuple(provinces[y, x]) not in permitted:
                    raise ValueError(f"southern city {entry['province']}: geometry changed at {x}, {y}")
                provinces[y, x] = entry["rgb"]
    for (x, y), (original, replacement) in PROVINCE_CORNER_REPAIRS.items():
        if tuple(provinces[y, x]) not in (definitions[original], definitions[replacement]):
            raise ValueError(f"province corner changed at {x}, {y}")
        provinces[y, x] = definitions[replacement]
    selected = set(ANCHOR_REFERENCES) | DISPLACED_PROVINCES | CITIES | URBAN_GROWTH | RELIEF_SURFACE_PROVINCES
    masks = {
        province: np.all(provinces == definitions[province], axis=2)
        for province in selected
    }
    for province, mask in masks.items():
        if not mask.any():
            raise ValueError(f"province {province}: empty coastal geometry")
    islands = np.logical_or.reduce([masks[province] for province in ISLANDS])
    cities = np.logical_or.reduce([masks[province] for province in CITIES | URBAN_GROWTH])
    arab_cities = np.logical_or.reduce([masks[province] for province in ARAB_CITIES | ARAB_URBAN_GROWTH])
    mountains = np.logical_or.reduce([masks[province] for province in RELIEF_SURFACE_PROVINCES])
    with Image.open(root / "map/heightmap.bmp") as source:
        mountain_heightmap = mountain_heights(mountains, np.array(source))
    outputs = {}
    original_provinces = (root / "map/provinces.bmp").read_bytes()
    with Image.open(BytesIO(original_provinces)) as source:
        if np.array_equal(np.asarray(source), provinces):
            outputs[Path("map/provinces.bmp")] = original_provinces
        else:
            encoded = BytesIO()
            Image.fromarray(provinces).save(encoded, format="BMP")
            outputs[Path("map/provinces.bmp")] = encoded.getvalue()
    packed = provinces.astype(np.uint32)
    sea = np.isin((packed[:, :, 0] << 16) | (packed[:, :, 1] << 8) | packed[:, :, 2], sea_colors)
    # Shared shoreline clearance: no city meshes or trees at the waterline.
    definition_text = "\n".join(definition_lines).encode("utf-8")
    water = water_mask(provinces, water_colours(definition_text))
    shore = urban_blocked(water, provinces, definition_text) & ~water
    relief_terrain = {}
    for index, line in enumerate(definition_lines):
        fields = line.split(";")
        if int(fields[0]) not in masks:
            continue
        ys, xs = np.where(masks[int(fields[0])])
        coastal = any(sea[ys + dy, xs + dx].any() for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)))
        fields[5] = "true" if coastal else "false"
        if int(fields[0]) in CITIES:
            fields[6] = "urban"
        elif int(fields[0]) in RELIEF_PROVINCES:
            fields[6] = RELIEF_TERRAIN[int(fields[0])]
            relief_terrain[int(fields[0])] = fields[6]
        definition_lines[index] = ";".join(fields)
    newline = "\r\n" if b"\r\n" in definition_bytes else "\n"
    outputs[Path("map/definition.csv")] = (newline.join(definition_lines) + newline).encode("utf-8")
    heights = None
    for name, mode, value in (("terrain", "P", 0), ("heightmap", "L", None), ("rivers", "P", 255), ("cities", "P", None)):
        path = Path(f"map/{name}.bmp")
        original = read(path)
        with Image.open(BytesIO(original)) as source:
            converted = False
            if name == "cities" and source.mode == "RGB":
                with Image.open(root / "map/terrain.bmp") as reference:
                    palette = reference.getpalette()
                palette_indices = {}
                for index in range(256):
                    palette_indices.setdefault(tuple(palette[index * 3:index * 3 + 3]), index)
                rgb = np.asarray(source)
                indexed = np.zeros(rgb.shape[:2], dtype=np.uint8)
                for _count, color in source.getcolors(256) or ():
                    if color not in palette_indices:
                        raise ValueError(f"cities.bmp: color {color} has no native palette entry")
                    indexed[np.all(rgb == color, axis=2)] = palette_indices[color]
                if source.getcolors(256) is None:
                    raise ValueError("cities.bmp contains more than 256 colors")
                source = Image.fromarray(indexed).convert("P")
                source.putpalette(palette)
                converted = True
            if source.mode != mode or source.size != (provinces.shape[1], provinces.shape[0]):
                raise ValueError(f"{path}: unexpected format or dimensions")
            pixels = np.array(source)
            if name == "heightmap":
                pixels[mountains] = mountain_heightmap[mountains]
                pixels[islands] = lowland_heights(islands)[islands]
                heights = pixels
            elif name == "cities":
                pixels[cities] = 15
                pixels[arab_cities] = 2
            else:
                pixels[islands] = value
                if name == "terrain":
                    pixels[cities & ~shore] = 13
                    pixels[cities & shore] = URBAN_FALLBACK_PALETTE
                    for province, kind in relief_terrain.items():
                        province_mask = masks[province]
                        pixels[province_mask] = {"desert": 3, "hills": 2, "mountain": 18}[kind]
                        if kind == "mountain":
                            pixels[province_mask & (mountain_heightmap >= 180)] = 11
                            pixels[province_mask & (mountain_heightmap >= 205)] = 16
            outputs[path] = bmp_bytes(source, pixels, b"" if converted else original)
    normal_path = Path("map/world_normal.bmp")
    original = (root / normal_path).read_bytes()
    with Image.open(BytesIO(original)) as source:
        normal = normal_from_height(Image.fromarray(heights), source, bytearray((islands | mountains).tobytes()))
        if normal.tobytes() == source.tobytes():
            outputs[normal_path] = original
        else:
            encoded = BytesIO()
            normal.save(encoded, format="BMP")
            outputs[normal_path] = encoded.getvalue()
    outputs[COLOURMAP] = patch_colourmap(read(COLOURMAP), islands)
    outputs[COLOURMAP] = patch_colourmap(outputs[COLOURMAP], cities, (102, 99, 88, 1))
    tree_path = Path("map/trees.bmp")
    original = read(tree_path)
    with Image.open(BytesIO(original)) as source:
        pixels = np.array(source)
        # Remove trees from every cell intersecting the new urban footprint.
        # The tree map uses a different grid, so point sampling misses narrow cities.
        ys, xs = np.where(cities | (mountains & (mountain_heightmap >= 165)))
        tx = xs * source.width // provinces.shape[1]
        ty = ys * source.height // provinces.shape[0]
        pixels[ty, tx] = 0
        pixels[tree_cells_blocked(water, source.width, source.height)] = 0
        outputs[tree_path] = bmp_bytes(source, pixels, original)
    stack_path = Path("map/unitstacks.txt")
    kinds = {int(line.split(";")[0]): line.split(";")[4] for line in definition_lines}
    outputs[stack_path] = unit_anchors(
        (root / stack_path).read_bytes(), masks, heights, province_grid(provinces, definitions), kinds
    )
    railways = Path("map/railways.txt")
    outputs[railways] = railway_plan((root / railways).read_bytes(), provinces, definitions)
    return outputs


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--apply", action="store_true")
    mode.add_argument("--check", action="store_true")
    args = parser.parse_args()
    outputs = build_plan()
    changed = [path for path, data in outputs.items() if (ROOT / path).read_bytes() != data]
    for path in changed:
        print(f"{'WRITE' if args.apply else 'STALE'} {path.as_posix()}")
        if args.apply:
            (ROOT / path).write_bytes(outputs[path])
    if args.apply:
        repeated = build_plan()
        if any((ROOT / path).read_bytes() != data for path, data in repeated.items()):
            raise RuntimeError("coastal geography is not idempotent")
    elif changed:
        return 1
    print("Coastal geography is current; repeated generation preserves output bytes.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
