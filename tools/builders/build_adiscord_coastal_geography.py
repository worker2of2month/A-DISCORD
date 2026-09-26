"""Build bounded coastal, settlement and Svetlogorye mountain geography.

Province geometry and state membership remain authored inputs. Only the explicit
island masks acquire new land; mainland edits use explicit province masks.
"""

from __future__ import annotations

import argparse
from collections import defaultdict, deque
from io import BytesIO
from math import cos, sin
from pathlib import Path

import numpy as np
from PIL import Image
from scipy.ndimage import distance_transform_edt, gaussian_filter

from tools.builders.build_adiscord_ivn_geography import normal_from_height
from tools.builders.build_adiscord_new_states import SOUTHERN_CITIES, SOUTHERN_CITY_POINTS
from tools.lib.paths import repository_root


ROOT = repository_root()
ISLANDS = frozenset({16709, 16710, 16712})
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
SPLIT_PARENTS = {16707: 6008, 16708: 6008, 16711: 11627}
ANCHOR_REFERENCES = {**SPLIT_PARENTS, 16709: 65, 16710: 65, 16712: 6261}
DISPLACED_PROVINCES = frozenset({6008, 7739, 11627})
CITIES = frozenset(range(16713, 16722)) | frozenset(province for province, _value in SOUTHERN_CITY_POINTS.values())
ARAB_CITIES = frozenset({16713, 16714, 16715, 16718, 16719, 16720}) | frozenset(entry["province"] for entry in SOUTHERN_CITIES)
RURAL_SECTORS = tuple(
    {**sector, "parent": city["parent"], "parent_terrain": city["parent_terrain"], "terrain": city["parent_terrain"]}
    for city in SOUTHERN_CITIES for sector in city.get("sectors", ())
)
SOUTHERN_GEOMETRY = (*SOUTHERN_CITIES, *RURAL_SECTORS)
ANCHOR_REFERENCES.update({entry["province"]: entry["parent"] for entry in SOUTHERN_CITIES})
ANCHOR_REFERENCES.update({entry["province"]: entry["parent"] for entry in RURAL_SECTORS})
DISPLACED_PROVINCES |= frozenset(entry["parent"] for entry in SOUTHERN_CITIES)
ANCHOR_REFERENCES.update({
    16713: 7968, 16714: 9659, 16715: 12876, 16716: 2038,
    16717: 8904, 16718: 12876, 16719: 2625, 16720: 9101, 16721: 689,
})
DISPLACED_PROVINCES |= frozenset({9659, 7968, 12876, 2625, 2056, 2038, 7618, 8904, 8194, 9101, 10931, 9630, 689, 8635})
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


def unit_anchors(
    original: bytes,
    masks: dict[int, np.ndarray],
    heights: np.ndarray,
) -> bytes:
    rows = [line.split(";") for line in original.decode("utf-8").splitlines()]
    references = {
        province: [row for row in rows if int(row[0]) == reference]
        for province, reference in ANCHOR_REFERENCES.items()
    }
    points = {province: np.argwhere(mask) for province, mask in masks.items()}
    map_height = heights.shape[0]
    result = []
    for row in rows:
        province = int(row[0])
        if province in ANCHOR_REFERENCES:
            continue
        if province in DISPLACED_PROVINCES:
            x = float(row[2])
            y = map_height - 1 - float(row[4])
            if not masks[province][round(y), round(x)]:
                x, y = closest_pixel(points[province], x, y)
                row[2:5] = [f"{x:.2f}", f"{heights[y, x] / 10:.2f}", f"{map_height - 1 - y:.2f}"]
        if province in RELIEF_PROVINCES:
            x = round(float(row[2]))
            y = map_height - 1 - round(float(row[4]))
            row[3] = f"{heights[y, x] / 10:.2f}"
        result.append(";".join(row))
    for province, template in sorted(references.items()):
        if not template or not len(points[province]):
            raise ValueError(f"province {province}: missing unit anchor reference or pixels")
        center_y, center_x = points[province].mean(axis=0)
        for source in template:
            slot = int(source[1])
            radius = 0.0 if slot == 0 else 1.0
            x = center_x + radius * cos(slot * 2.4)
            y = center_y + radius * sin(slot * 2.4)
            x, y = closest_pixel(points[province], x, y)
            row = source.copy()
            row[0] = str(province)
            row[2:5] = [f"{x:.2f}", f"{heights[y, x] / 10:.2f}", f"{map_height - 1 - y:.2f}"]
            row[6] = "0.12" if province in ISLANDS else "0.24"
            result.append(";".join(row))
    newline = "\r\n" if b"\r\n" in original else "\n"
    return (newline.join(result) + newline).encode("utf-8")


def railway_plan(original: bytes, provinces: np.ndarray, definitions: dict[int, tuple[int, int, int]]) -> bytes:
    """Insert local sector crossings while preserving existing railway levels."""
    groups = {}
    for city in SOUTHERN_CITIES:
        members = {city["parent"], city["province"], *(sector["province"] for sector in city.get("sectors", ()))}
        groups.update({province: members for province in members})
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
                if tuple(provinces[y, x]) not in (definitions[entry["parent"]], tuple(entry["rgb"])):
                    raise ValueError(f"southern city {entry['province']}: geometry changed at {x}, {y}")
                provinces[y, x] = entry["rgb"]
    selected = set(ANCHOR_REFERENCES) | DISPLACED_PROVINCES | CITIES | RELIEF_PROVINCES
    masks = {
        province: np.all(provinces == definitions[province], axis=2)
        for province in selected
    }
    for province, mask in masks.items():
        if not mask.any():
            raise ValueError(f"province {province}: empty coastal geometry")
    islands = np.logical_or.reduce([masks[province] for province in ISLANDS])
    cities = np.logical_or.reduce([masks[province] for province in CITIES])
    arab_cities = np.logical_or.reduce([masks[province] for province in ARAB_CITIES])
    mountains = np.logical_or.reduce([masks[province] for province in RELIEF_PROVINCES])
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
                    pixels[cities] = 13
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
        outputs[tree_path] = bmp_bytes(source, pixels, original)
    stack_path = Path("map/unitstacks.txt")
    outputs[stack_path] = unit_anchors((root / stack_path).read_bytes(), masks, heights)
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
