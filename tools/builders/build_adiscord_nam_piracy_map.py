"""Render Svetlogorye's exile sea chart and bind its raid lanes to the piracy window.

The chart is drawn from native geography: land, sea and lakes from
map/definition.csv and map/provinces.bmp, relief from map/heightmap.bmp, the
island exile from the state histories of 225-231. Each raid lane starts at the
naval base of its target, from the state histories, that lies closest to the
islands by sea and follows the cheapest sea passage to the nearest island
harbour; canals listed in map/adjacencies.csv are passable. Shared stretches of
several lanes are drawn as parallel lanes.

The flotillas raid local shipping only: no lane may be longer by sea than half
the width of the mainland the exiles left (the land connected to state 67).
The chart is cropped around the islands and these lanes.

The builder needs numpy only and writes PNG through zlib, so the output bytes
do not depend on an installed imaging library. --check is the default; --apply
writes changed assets and the generated GUI/GFX sections.
"""

from __future__ import annotations

import argparse
import csv
import heapq
import math
import re
import struct
import zlib
from pathlib import Path

import numpy as np

from tools.lib.paths import repository_root


ROOT = repository_root()
OUT = Path("gfx/interface/NAM_piracy")
GUI = Path("interface/ADISCORD_NAM_piracy.gui")
GFX = Path("interface/ADISCORD_NAM_piracy.gfx")
BEGIN = "# BEGIN GENERATED NAM PIRACY MAP"
END = "# END GENERATED NAM PIRACY MAP"
WIDTH, HEIGHT = 436, 246
# Map origin inside ADISCORD_NAM_piracy_window.
MAP_X, MAP_Y = 12, 66
ISLANDS = (225, 226, 227, 228, 229, 230, 231)
# A state of the mainland the exiles left; its landmass sets the raid radius.
MAINLAND_STATE = 67
# NAM_pirate_raid targets in decision order: the coalition, then the nearest
# coastal countries with harbours of their own.
TARGETS = ("EFL", "AZH", "ULV", "RIV", "LUR", "CHD")
FRAMES = ("idle", "raid", "guarded", "closed")
# Route search cell in map pixels; the map size is a multiple of it.
GRID = 4
# The chart scale is a multiple of 1 / SCALE_STEPS map pixels per chart pixel;
# WIDTH and HEIGHT times the scale stay whole numbers.
SCALE_STEPS = 2
LANE_SPACING = 3.0
MARKER = 24
MARKER_GAP = 44
LABEL_WIDTH, LABEL_HEIGHT = 80, 18
ISLAND_LABEL_WIDTH = 140

# Levels panel geometry, shared with the authored labels of the window.
LEVELS_TOP = 356
BAR_X = 150
NOTORIETY_ROW = LEVELS_TOP + 6
REVENGE_ROW = LEVELS_TOP + 50
FLEET_ROW = LEVELS_TOP + 94
MARINE_ROW = LEVELS_TOP + 118
PIP_X = (152, 172, 192)
SEGMENTS = 20
NOTORIETY_TICKS = (50, 75)
REVENGE_TICKS = (70,)

SEA = (18, 35, 43)
LAND = (48, 57, 55)
GOLD = (219, 187, 121)
SAND = (233, 201, 128)
RAID = (240, 104, 70)
ESCORT = (122, 172, 204)
CLOSED = (112, 118, 122)


# ----- Raster primitives -----

def read_bmp(path: Path) -> np.ndarray:
    """Read a 24-bit or 8-bit paletted BMP as RGB rows or palette values."""
    data = path.read_bytes()
    if data[:2] != b"BM":
        raise ValueError(f"{path} is not a BMP")
    offset = struct.unpack_from("<I", data, 10)[0]
    header_size = struct.unpack_from("<I", data, 14)[0]
    width, height = struct.unpack_from("<ii", data, 18)
    bits = struct.unpack_from("<H", data, 28)[0]
    rows = abs(height)
    if bits == 24:
        stride = (width * 3 + 3) & ~3
        pixels = np.frombuffer(data, np.uint8, stride * rows, offset).reshape(rows, stride)
        pixels = pixels[:, : width * 3].reshape(rows, width, 3)[:, :, ::-1]
    elif bits == 8:
        colours = struct.unpack_from("<I", data, 46)[0] or 256
        palette = np.frombuffer(data, np.uint8, colours * 4, 14 + header_size).reshape(colours, 4)
        stride = (width + 3) & ~3
        indices = np.frombuffer(data, np.uint8, stride * rows, offset).reshape(rows, stride)[:, :width]
        pixels = palette[:, 2][indices]
    else:
        raise ValueError(f"{path}: unsupported {bits}-bit BMP")
    if height > 0:
        pixels = pixels[::-1]
    return np.ascontiguousarray(pixels)


def png_bytes(image: np.ndarray) -> bytes:
    """Encode an RGBA float image (0..1) as a deterministic 8-bit PNG."""
    rgba = np.rint(np.clip(image, 0, 1) * 255).astype(np.uint8)
    rgba[rgba[..., 3] == 0] = 0
    height, width = rgba.shape[:2]
    raw = np.zeros((height, width * 4 + 1), np.uint8)
    raw[:, 1:] = rgba.reshape(height, width * 4)

    def chunk(kind: bytes, payload: bytes) -> bytes:
        return (struct.pack(">I", len(payload)) + kind + payload
                + struct.pack(">I", zlib.crc32(kind + payload) & 0xFFFFFFFF))

    header = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header)
            + chunk(b"IDAT", zlib.compress(raw.tobytes(), 9)) + chunk(b"IEND", b""))


def canvas(width: int, height: int) -> np.ndarray:
    return np.zeros((height, width, 4), np.float64)


def over(target: np.ndarray, colour: tuple[int, ...], coverage: np.ndarray, alpha: float = 1.0) -> None:
    """Composite a flat colour with the given coverage over a straight-alpha canvas."""
    source = np.clip(coverage, 0, 1) * alpha
    below = target[..., 3]
    result = source + below * (1 - source)
    safe = np.where(result > 0, result, 1)
    for channel in range(3):
        target[..., channel] = (colour[channel] / 255 * source
                                + target[..., channel] * below * (1 - source)) / safe
    target[..., 3] = result


def dilate(mask: np.ndarray, radius: int = 1) -> np.ndarray:
    grown = mask.copy()
    for _ in range(radius):
        step = grown.copy()
        step[1:] |= grown[:-1]
        step[:-1] |= grown[1:]
        step[:, 1:] |= grown[:, :-1]
        step[:, :-1] |= grown[:, 1:]
        grown = step
    return grown


def erode(mask: np.ndarray, radius: int = 1) -> np.ndarray:
    return ~dilate(~mask, radius)


def stroke(shape: tuple[int, int], points: np.ndarray, width: float) -> np.ndarray:
    """Antialiased coverage of a polyline of the given width."""
    height, wide = shape
    coverage = np.zeros(shape)
    half = width / 2
    reach = int(math.ceil(half + 1))
    for (x0, y0), (x1, y1) in zip(points[:-1], points[1:]):
        left = max(0, int(math.floor(min(x0, x1))) - reach)
        right = min(wide, int(math.ceil(max(x0, x1))) + reach + 1)
        top = max(0, int(math.floor(min(y0, y1))) - reach)
        bottom = min(height, int(math.ceil(max(y0, y1))) + reach + 1)
        if left >= right or top >= bottom:
            continue
        ys, xs = np.mgrid[top:bottom, left:right] + 0.5
        dx, dy = x1 - x0, y1 - y0
        length = dx * dx + dy * dy
        t = np.zeros_like(xs) if length == 0 else np.clip(((xs - x0) * dx + (ys - y0) * dy) / length, 0, 1)
        distance = np.hypot(xs - (x0 + t * dx), ys - (y0 + t * dy))
        local = np.clip(half + 0.5 - distance, 0, 1)
        coverage[top:bottom, left:right] = np.maximum(coverage[top:bottom, left:right], local)
    return coverage


def disc(shape: tuple[int, int], centre: tuple[float, float], radius: float, inner: float = 0.0) -> np.ndarray:
    ys, xs = np.mgrid[0:shape[0], 0:shape[1]] + 0.5
    distance = np.hypot(xs - centre[0], ys - centre[1])
    coverage = np.clip(radius + 0.5 - distance, 0, 1)
    if inner > 0:
        coverage = np.minimum(coverage, np.clip(distance - inner + 0.5, 0, 1))
    return coverage


def polygon(shape: tuple[int, int], vertices: list[tuple[float, float]]) -> np.ndarray:
    """Even-odd fill sampled at four points per pixel."""
    coverage = np.zeros(shape)
    for oy, ox in ((0.25, 0.25), (0.25, 0.75), (0.75, 0.25), (0.75, 0.75)):
        ys, xs = np.mgrid[0:shape[0], 0:shape[1]].astype(float)
        xs += ox
        ys += oy
        inside = np.zeros(shape, bool)
        for (x0, y0), (x1, y1) in zip(vertices, vertices[1:] + vertices[:1]):
            crosses = (y0 > ys) != (y1 > ys)
            with np.errstate(divide="ignore", invalid="ignore"):
                at = x0 + (ys - y0) * (x1 - x0) / (y1 - y0)
            inside ^= crosses & (xs < at)
        coverage += inside * 0.25
    return coverage


def rectangle(shape: tuple[int, int], box: tuple[int, int, int, int]) -> np.ndarray:
    left, top, right, bottom = box
    coverage = np.zeros(shape)
    coverage[top:bottom + 1, left:right + 1] = 1
    return coverage


def outline(shape: tuple[int, int], box: tuple[int, int, int, int]) -> np.ndarray:
    left, top, right, bottom = box
    return rectangle(shape, box) - rectangle(shape, (left + 1, top + 1, right - 1, bottom - 1))


# ----- Native geography -----

def read_geography() -> dict:
    kinds = {}
    colours = {}
    with (ROOT / "map/definition.csv").open(encoding="utf-8-sig") as source:
        for row in csv.reader(source, delimiter=";"):
            if len(row) < 5 or not row[0].isdigit():
                continue
            province = int(row[0])
            colours[province] = int(row[1]) * 65536 + int(row[2]) * 256 + int(row[3])
            kinds[province] = row[4]
    rgb = read_bmp(ROOT / "map/provinces.bmp")
    packed = rgb[..., 0].astype(np.int32) * 65536 + rgb[..., 1].astype(np.int32) * 256 + rgb[..., 2]
    order = sorted(colours, key=colours.get)
    keys = np.array([colours[p] for p in order], np.int32)
    values = np.array(order, np.int32)
    index = np.clip(np.searchsorted(keys, packed), 0, len(keys) - 1)
    provinces = np.where(keys[index] == packed, values[index], 0)
    states = {}
    for path in sorted((ROOT / "history/states").glob("*.txt")):
        source = path.read_text(encoding="utf-8-sig", errors="replace")
        number = re.search(r"\bid\s*=\s*(\d+)", source)
        owner = re.search(r"\bowner\s*=\s*([A-Z0-9]{3})\b", source)
        members = re.search(r"provinces\s*=\s*\{([^}]+)\}", source)
        if not (number and members):
            continue
        states[int(number[1])] = {
            "owner": owner[1] if owner else None,
            "provinces": [int(p) for p in re.findall(r"\d+", members[1])],
            "naval_bases": [(int(p), int(level)) for p, level in
                            re.findall(r"\b(\d+)\s*=\s*\{\s*naval_base\s*=\s*(\d+)", source)],
        }
    canals = []
    for line in (ROOT / "map/adjacencies.csv").read_text(encoding="utf-8-sig").splitlines()[1:]:
        fields = line.split(";")
        if len(fields) < 4 or not fields[0].isdigit() or not fields[1].isdigit() or not fields[3].isdigit():
            continue
        start, stop, through = int(fields[0]), int(fields[1]), int(fields[3])
        if fields[2] == "sea" and kinds.get(start) == kinds.get(stop) == "sea" and kinds.get(through) == "land":
            canals.append(through)
    heights = read_bmp(ROOT / "map/heightmap.bmp")
    return {"kinds": kinds, "provinces": provinces, "states": states, "canals": canals, "heights": heights}


def province_centre(provinces: np.ndarray, province: int) -> tuple[float, float]:
    ys, xs = np.nonzero(provinces == province)
    if not len(xs):
        raise ValueError(f"Province {province} is not on the map")
    return float(xs.mean()) + 0.5, float(ys.mean()) + 0.5


def strongest_base(states: dict, numbers: list[int]) -> int:
    bases = [(level, -province) for number in numbers for province, level in states[number]["naval_bases"]]
    if not bases:
        raise ValueError(f"No naval base in states {numbers}")
    return -max(bases)[1]


def target_bases(states: dict) -> dict[str, list[int]]:
    """Every naval base of each target in the state histories."""
    bases = {}
    for tag in TARGETS:
        bases[tag] = sorted(province for state in states.values() if state["owner"] == tag
                            for province, _ in state["naval_bases"])
        if not bases[tag]:
            raise ValueError(f"{tag} owns no naval base")
    return bases


def mainland_span(geography: dict) -> tuple[int, int]:
    """West and east edge in map pixels of the landmass that holds MAINLAND_STATE.

    Land is traced on the route grid with four-way steps, so a sea strait one
    cell wide already separates the islands from the mainland.
    """
    provinces = geography["provinces"]
    kinds = geography["kinds"]
    land_ids = np.array(sorted(p for p, kind in kinds.items() if kind == "land"), np.int32)
    rows, columns = provinces.shape[0] // GRID, provinces.shape[1] // GRID
    cells = np.isin(provinces, land_ids)[:rows * GRID, :columns * GRID].reshape(rows, GRID, columns, GRID).any(axis=(1, 3))
    seed = np.isin(provinces, geography["states"][MAINLAND_STATE]["provinces"])
    region = seed[:rows * GRID, :columns * GRID].reshape(rows, GRID, columns, GRID).any(axis=(1, 3)) & cells
    while True:
        grown = dilate(region) & cells
        if np.array_equal(grown, region):
            break
        region = grown
    occupied = np.nonzero(region.any(axis=0))[0]
    return int(occupied.min()) * GRID, (int(occupied.max()) + 1) * GRID


# ----- Sea lanes -----

def route_grid(geography: dict) -> tuple[np.ndarray, np.ndarray]:
    provinces = geography["provinces"]
    kinds = geography["kinds"]
    sea_ids = np.array(sorted(p for p, kind in kinds.items() if kind == "sea"), np.int32)
    water = np.isin(provinces, sea_ids) | np.isin(provinces, geography["canals"])
    rows, columns = provinces.shape[0] // GRID, provinces.shape[1] // GRID
    passable = water[:rows * GRID, :columns * GRID].reshape(rows, GRID, columns, GRID).any(axis=(1, 3))
    # Distance in cells to the nearest coast keeps lanes in open water.
    coast = np.zeros(passable.shape, np.int32)
    inner = passable.copy()
    for step in range(1, 9):
        coast[inner] = step
        inner = erode(inner) & passable
    return passable, coast


def entry_cells(provinces: np.ndarray, passable: np.ndarray, province: int) -> list[int]:
    ys, xs = np.nonzero(provinces == province)
    cells = np.zeros(passable.shape, bool)
    cells[ys // GRID, xs // GRID] = True
    centre = (xs.mean() / GRID, ys.mean() / GRID)
    for radius in range(1, 4):
        candidates = dilate(cells, radius) & passable
        if candidates.any():
            cy, cx = np.nonzero(candidates)
            order = np.lexsort((cy * passable.shape[1] + cx, np.hypot(cx + 0.5 - centre[0], cy + 0.5 - centre[1])))
            return [int(cy[i] * passable.shape[1] + cx[i]) for i in order]
    raise ValueError(f"Province {province} has no sea access")


def sea_routes(geography: dict, bases: dict[str, list[int]],
               harbours: list[int]) -> tuple[dict[str, int], dict[str, list[int]]]:
    """Each target's naval base nearest to the islands and its cheapest passage
    to the nearest island harbour."""
    provinces = geography["provinces"]
    passable, coast = route_grid(geography)
    rows, columns = passable.shape
    open_cells = passable.ravel().tolist()
    weights = (1 + 3 * np.exp(-(coast.ravel() - 1) / 2.0)).tolist()
    cost = [math.inf] * (rows * columns)
    previous = [-1] * (rows * columns)
    heap = []
    for harbour in harbours:
        for cell in entry_cells(provinces, passable, harbour)[:3]:
            if cost[cell] > 0:
                cost[cell] = 0.0
                heap.append((0.0, cell))
    heapq.heapify(heap)
    starts = {port: entry_cells(provinces, passable, port)[0] for members in bases.values() for port in members}
    pending = set(starts.values())
    steps = [(dx, dy, math.hypot(dx, dy)) for dy in (-1, 0, 1) for dx in (-1, 0, 1) if dx or dy]
    while heap and pending:
        here, cell = heapq.heappop(heap)
        if here > cost[cell]:
            continue
        pending.discard(cell)
        y, x = divmod(cell, columns)
        for dx, dy, length in steps:
            nx, ny = x + dx, y + dy
            if not (0 <= nx < columns and 0 <= ny < rows):
                continue
            target = ny * columns + nx
            if not open_cells[target]:
                continue
            if dx and dy and not (open_cells[y * columns + nx] or open_cells[ny * columns + x]):
                continue
            candidate = here + length * (weights[cell] + weights[target]) / 2
            if candidate < cost[target]:
                cost[target] = candidate
                previous[target] = cell
                heapq.heappush(heap, (candidate, target))
    ports = {}
    routes = {}
    for tag, members in bases.items():
        port = min(members, key=lambda province: (cost[starts[province]], province))
        start = starts[port]
        if math.isinf(cost[start]):
            raise ValueError(f"No sea passage from a {tag} naval base to the islands")
        path = [start]
        while previous[path[-1]] >= 0:
            path.append(previous[path[-1]])
        ports[tag] = port
        routes[tag] = path
    return ports, routes


def sailing_length(points: list[tuple[float, float]]) -> float:
    return sum(math.dist(a, b) for a, b in zip(points[:-1], points[1:]))


def cell_centre(cell: int, columns: int) -> tuple[float, float]:
    y, x = divmod(cell, columns)
    return x * GRID + GRID / 2, y * GRID + GRID / 2


def resample(points: np.ndarray, spacing: float) -> tuple[np.ndarray, np.ndarray]:
    """Even arc-length samples and the source vertex nearest to each sample."""
    lengths = np.hypot(*np.diff(points, axis=0).T)
    arc = np.concatenate(([0.0], np.cumsum(lengths)))
    samples = np.arange(0, arc[-1], spacing)
    samples = np.append(samples, arc[-1])
    xs = np.interp(samples, arc, points[:, 0])
    ys = np.interp(samples, arc, points[:, 1])
    source = np.clip(np.searchsorted(arc, samples), 0, len(points) - 1)
    return np.stack([xs, ys], 1), source


def smooth(values: np.ndarray, window: int) -> np.ndarray:
    """Moving average that keeps both ends in place."""
    if len(values) < 3:
        return values.copy()
    half = window // 2
    result = values.copy()
    for index in range(1, len(values) - 1):
        reach = min(half, index, len(values) - 1 - index)
        result[index] = values[index - reach:index + reach + 1].mean(axis=0)
    return result


def lane_geometry(routes: dict[str, list[int]], ports: dict[str, int], columns: int,
                  port_points: dict[str, tuple[float, float]], harbour_points: dict[int, tuple[float, float]],
                  view: tuple[float, float, float]) -> dict[str, dict]:
    """Smoothed lanes in chart pixels with parallel offsets on shared stretches."""
    left, top, scale = view
    groups = {}
    for tag in TARGETS:
        groups.setdefault(ports[tag], []).append(tag)
    users = {}
    for port, members in groups.items():
        for cell in routes[members[0]]:
            users.setdefault(cell, []).append(port)
    lanes = {}
    for tag in TARGETS:
        path = routes[tag]
        cells = [cell_centre(cell, columns) for cell in path]
        end = min(harbour_points.values(), key=lambda p: math.dist(p, cells[-1]))
        raw = np.array([port_points[tag], *cells, end])
        raw = (raw - (left, top)) / scale
        points, source = resample(raw, 1.0)
        centre = smooth(points, 9)
        lane_offsets = []
        exclusive = []
        for vertex in source:
            # raw starts with the port point, so vertex n lies on path cell n - 1.
            cell = path[min(max(vertex - 1, 0), len(path) - 1)]
            sharing = sorted({member for port in users[cell] for member in groups[port]}, key=TARGETS.index)
            lane_offsets.append((sharing.index(tag) - (len(sharing) - 1) / 2) * LANE_SPACING)
            exclusive.append(users[cell] == [ports[tag]])
        offsets = smooth(np.array(lane_offsets), 15)
        tangent = np.gradient(centre, axis=0)
        norm = np.hypot(tangent[:, 0], tangent[:, 1])
        norm[norm == 0] = 1
        normal = np.stack([-tangent[:, 1] / norm, tangent[:, 0] / norm], 1)
        lanes[tag] = {"points": centre + normal * offsets[:, None], "exclusive": np.array(exclusive)}
    return lanes


def overlaps(box: tuple[float, ...], others: list[tuple[float, ...]]) -> bool:
    left, top, right, bottom = box
    return any(left < o_right and o_left < right and top < o_bottom and o_top < bottom
               for o_left, o_top, o_right, o_bottom in others)


def marker_box(point: tuple[float, float], margin: float = 0.0) -> tuple[float, ...]:
    half = MARKER / 2 + margin
    return point[0] - half, point[1] - half, point[0] + half, point[1] + half


def place_markers(lanes: dict[str, dict], land: np.ndarray,
                  blocked: list[tuple[float, ...]]) -> dict[str, tuple[float, float]]:
    """One raid marker per lane, on its own stretch where possible, never stacked
    and clear of the blocked chart areas."""
    placed = {}
    order = sorted(TARGETS, key=lambda tag: (int(lanes[tag]["exclusive"].sum()), TARGETS.index(tag)))
    margin = MARKER / 2 + 3
    for tag in order:
        points = lanes[tag]["points"]
        own = np.nonzero(lanes[tag]["exclusive"])[0]
        stretch = int(own.max()) if len(own) else len(points) - 1
        preferred = min(max(stretch * 0.5, 16), 70)
        candidates = sorted(range(len(points)), key=lambda i: (abs(i - preferred) + (0 if i <= stretch else 40), i))
        for index in candidates:
            x, y = points[index]
            if not (margin <= x <= WIDTH - margin and margin <= y <= HEIGHT - margin):
                continue
            if land[int(y), int(x)] > 0.35:
                continue
            if any(math.dist((x, y), other) < MARKER_GAP for other in placed.values()):
                continue
            if overlaps(marker_box((x, y)), blocked):
                continue
            placed[tag] = (float(x), float(y))
            break
        else:
            raise ValueError(f"No free marker position on the {tag} lane")
    return placed


def place_labels(markers: dict[str, tuple[float, float]],
                 blocked: list[tuple[float, ...]]) -> dict[str, tuple[int, int, str]]:
    """Name boxes beside each marker: right, left, above or below, whichever
    first stays on the chart and clear of markers and earlier labels."""
    # The window places markers at rounded positions.
    taken = blocked + [marker_box((round(x), round(y)), 2) for x, y in markers.values()]
    labels = {}
    gap = MARKER // 2 + 2
    for tag in TARGETS:
        x, y = (int(round(value)) for value in markers[tag])
        candidates = (
            (x + gap, y - LABEL_HEIGHT // 2, "left"),
            (x - gap - LABEL_WIDTH, y - LABEL_HEIGHT // 2, "right"),
            (x - LABEL_WIDTH // 2, y - gap - LABEL_HEIGHT, "centre"),
            (x - LABEL_WIDTH // 2, y + gap, "centre"),
        )
        for left, top, align in candidates:
            box = (left, top, left + LABEL_WIDTH, top + LABEL_HEIGHT)
            if left < 4 or top < 4 or box[2] > WIDTH - 4 or box[3] > HEIGHT - 4:
                continue
            if overlaps(box, taken):
                continue
            labels[tag] = (left, top, align)
            taken.append(box)
            break
        else:
            raise ValueError(f"No free label position beside the {tag} marker")
    return labels


# ----- Chart -----

def chart(geography: dict) -> tuple[dict[str, np.ndarray], dict]:
    provinces = geography["provinces"]
    states = geography["states"]
    kinds = geography["kinds"]
    harbours = [strongest_base(states, [number]) for number in ISLANDS]
    ports, routes = sea_routes(geography, target_bases(states), harbours)
    columns = provinces.shape[1] // GRID
    port_points = {tag: province_centre(provinces, port) for tag, port in ports.items()}
    harbour_points = {harbour: province_centre(provinces, harbour) for harbour in harbours}
    west, east = mainland_span(geography)
    radius = (east - west) / 2
    lengths = {}
    for tag in TARGETS:
        cells = [cell_centre(cell, columns) for cell in routes[tag]]
        end = min(harbour_points.values(), key=lambda p: math.dist(p, cells[-1]))
        lengths[tag] = sailing_length([port_points[tag], *cells, end])
        if lengths[tag] > radius:
            raise ValueError(f"The {tag} lane is {lengths[tag]:.0f} px by sea, beyond the raid radius {radius:.0f} px")

    island_ids = [p for number in ISLANDS for p in states[number]["provinces"]]
    island_mask = np.isin(provinces, island_ids)
    ys, xs = np.nonzero(island_mask)
    xs_all = [float(xs.min()), float(xs.max())] + [p[0] for p in port_points.values()]
    ys_all = [float(ys.min()), float(ys.max())] + [p[1] for p in port_points.values()]
    for path in routes.values():
        for cell in path:
            x, y = cell_centre(cell, columns)
            xs_all.append(x)
            ys_all.append(y)
    pad = 40
    box = (min(xs_all) - pad, min(ys_all) - pad, max(xs_all) + pad, max(ys_all) + pad)
    steps = max(SCALE_STEPS, math.ceil(SCALE_STEPS * max((box[2] - box[0]) / WIDTH, (box[3] - box[1]) / HEIGHT)))
    scale = steps / SCALE_STEPS
    crop_width, crop_height = WIDTH * steps // SCALE_STEPS, HEIGHT * steps // SCALE_STEPS
    left = int(round((box[0] + box[2] - crop_width) / 2))
    top = int(round((box[1] + box[3] - crop_height) / 2))
    left = min(max(left, 0), provinces.shape[1] - crop_width)
    top = min(max(top, 0), provinces.shape[0] - crop_height)

    def block(array: np.ndarray) -> np.ndarray:
        """Area average of the crop; repeating it SCALE_STEPS times lets a chart
        pixel cover a fractional number of map pixels."""
        window = array[top:top + crop_height, left:left + crop_width].astype(np.float64)
        window = window.repeat(SCALE_STEPS, axis=0).repeat(SCALE_STEPS, axis=1)
        return window.reshape(HEIGHT, steps, WIDTH, steps).mean(axis=(1, 3))

    window = provinces[top:top + crop_height, left:left + crop_width]
    land_ids = np.array(sorted(p for p, kind in kinds.items() if kind == "land"), np.int32)
    sea_ids = np.array(sorted(p for p, kind in kinds.items() if kind == "sea"), np.int32)
    land = block(np.isin(provinces, land_ids))
    islands = block(island_mask)
    heights = block(geography["heights"])
    sea_window = np.isin(window, sea_ids)
    seams = np.zeros(window.shape, bool)
    seams[1:] |= (window[1:] != window[:-1]) & sea_window[1:] & sea_window[:-1]
    seams[:, 1:] |= (window[:, 1:] != window[:, :-1]) & sea_window[:, 1:] & sea_window[:, :-1]
    seams = seams.repeat(SCALE_STEPS, axis=0).repeat(SCALE_STEPS, axis=1)
    seams = seams.reshape(HEIGHT, steps, WIDTH, steps).any(axis=(1, 3))

    shape = (HEIGHT, WIDTH)
    dy, dx = np.gradient(heights)
    shade = np.clip((heights - 100) * 0.16 - dx * 0.4 - dy * 0.3, -10, 24)
    shallow = np.clip((heights - 70) / 26, 0, 1)
    base = canvas(WIDTH, HEIGHT)
    for channel in range(3):
        sea = SEA[channel] + shallow * (6, 13, 14)[channel]
        ground = np.clip(LAND[channel] + shade, 0, 255)
        base[..., channel] = (sea * (1 - land) + ground * land) / 255
    base[..., 3] = 1
    # Sea province seams read as the chart's sailing zones.
    over(base, (52, 84, 92), seams & (land < 0.2), 0.2)
    contours = heights // 16
    contour = np.zeros(shape, bool)
    contour[1:] |= contours[1:] != contours[:-1]
    contour[:, 1:] |= contours[:, 1:] != contours[:, :-1]
    over(base, (191, 180, 142), contour & (land > 0.6), 22 / 255)
    shore = land > 0.5
    over(base, (68, 106, 111), dilate(shore, 2) & ~shore, 180 / 255)
    over(base, (196, 168, 104), islands, 0.22)
    island_shape = islands > 0.4
    over(base, (166, 156, 113), island_shape & ~erode(island_shape), 210 / 255)
    grid = np.zeros(shape, bool)
    grid[:, 20::40] = True
    grid[8::40, :] = True
    over(base, (183, 185, 157), grid, 22 / 255)
    for point in harbour_points.values():
        x, y = (point[0] - left) / scale, (point[1] - top) / scale
        over(base, (203, 186, 139), disc(shape, (x, y), 1.6))
    over(base, (128, 119, 90), outline(shape, (0, 0, WIDTH - 1, HEIGHT - 1)))
    over(base, (56, 72, 72), outline(shape, (3, 3, WIDTH - 4, HEIGHT - 4)))
    compass_x, compass_y = 24, HEIGHT - 64
    over(base, (203, 186, 139), stroke(shape, np.array([[compass_x, compass_y], [compass_x, compass_y + 40]]), 1))
    over(base, (203, 186, 139), stroke(shape, np.array([[compass_x - 11, compass_y + 20], [compass_x + 11, compass_y + 20]]), 1))
    over(base, (203, 186, 139), polygon(shape, [(compass_x, compass_y), (compass_x - 4, compass_y + 12), (compass_x + 4, compass_y + 12)]))

    view = (float(left), float(top), float(scale))
    lanes = lane_geometry(routes, ports, columns, port_points, harbour_points, view)
    # The islands' name sits under their southern shore; it and the compass
    # stay clear of markers and lane names.
    islands_y, islands_x = np.nonzero(island_shape)
    island_label = (int(round(islands_x.mean())) - ISLAND_LABEL_WIDTH // 2,
                    min(int(islands_y.max()) + 1, HEIGHT - 20))
    blocked = [
        (island_label[0], island_label[1], island_label[0] + ISLAND_LABEL_WIDTH, island_label[1] + LABEL_HEIGHT),
        (compass_x - 12, compass_y - 2, compass_x + 12, compass_y + 42),
    ]
    markers = place_markers(lanes, land, blocked)
    labels = place_labels(markers, blocked)
    images = {"map.png": base}
    for tag in TARGETS:
        images[f"lane_{tag}.png"] = lane_strip(lanes[tag]["points"])
    geometry = {
        "view": view,
        "ports": ports,
        "radius": radius,
        "lengths": lengths,
        "lanes": lanes,
        "markers": markers,
        "labels": labels,
        "island_label": island_label,
    }
    return images, geometry


def dashes(points: np.ndarray, on: float, off: float) -> list[np.ndarray]:
    lengths = np.hypot(*np.diff(points, axis=0).T)
    arc = np.concatenate(([0.0], np.cumsum(lengths)))
    pieces = []
    start = 0.0
    while start < arc[-1]:
        stop = min(start + on, arc[-1])
        inside = (arc > start) & (arc < stop)
        xs = np.interp([start, *arc[inside], stop], arc, points[:, 0])
        ys = np.interp([start, *arc[inside], stop], arc, points[:, 1])
        pieces.append(np.stack([xs, ys], 1))
        start += on + off
    return pieces


def dashed(shape: tuple[int, int], points: np.ndarray, width: float, on: float, off: float) -> np.ndarray:
    coverage = np.zeros(shape)
    for piece in dashes(points, on, off):
        coverage = np.maximum(coverage, stroke(shape, piece, width))
    return coverage


def lane_strip(points: np.ndarray) -> np.ndarray:
    """Four frames of one lane: idle, raid at sea, escorted convoys, closed."""
    shape = (HEIGHT, WIDTH)
    port = tuple(points[0])
    frames = []
    idle = canvas(WIDTH, HEIGHT)
    over(idle, SEA, stroke(shape, points, 4.2), 0.55)
    over(idle, SAND, dashed(shape, points, 1.7, 6, 4), 0.95)
    over(idle, SAND, disc(shape, port, 3.2, 1.6))
    frames.append(idle)
    raid = canvas(WIDTH, HEIGHT)
    over(raid, RAID, stroke(shape, points, 6.5), 0.28)
    over(raid, RAID, stroke(shape, points, 2.3))
    over(raid, RAID, disc(shape, port, 3.6))
    frames.append(raid)
    escort = canvas(WIDTH, HEIGHT)
    over(escort, SEA, stroke(shape, points, 4.2), 0.55)
    over(escort, ESCORT, dashed(shape, points, 1.7, 3, 3), 0.95)
    over(escort, ESCORT, disc(shape, port, 3.2, 1.6))
    frames.append(escort)
    closed = canvas(WIDTH, HEIGHT)
    over(closed, CLOSED, dashed(shape, points, 1.2, 2, 4), 0.6)
    over(closed, CLOSED, disc(shape, port, 2.8, 1.4), 0.6)
    frames.append(closed)
    return np.concatenate(frames, axis=1)


# ----- Window sprites -----

def marker_image() -> np.ndarray:
    shape = (MARKER, MARKER)
    image = canvas(MARKER, MARKER)
    middle = MARKER / 2
    over(image, (19, 30, 32), disc(shape, (middle, middle), 11.2))
    over(image, GOLD, disc(shape, (middle, middle), 11.2, 9.4))
    over(image, GOLD, disc(shape, (middle, 6.6), 2.0, 0.9))
    over(image, GOLD, stroke(shape, np.array([[middle, 8.4], [middle, 18.2]]), 1.6))
    over(image, GOLD, stroke(shape, np.array([[middle - 4.2, 10.8], [middle + 4.2, 10.8]]), 1.4))
    arc = np.array([[middle + 6 * math.cos(a), 12.6 + 6 * math.sin(a)] for a in np.linspace(0.15, math.pi - 0.15, 14)])
    over(image, GOLD, stroke(shape, arc, 1.5))
    return image


def gauge_image(ticks: tuple[int, ...]) -> np.ndarray:
    width = SEGMENTS * 10 + 4
    shape = (18, width)
    image = canvas(width, 18)
    over(image, (14, 22, 24), rectangle(shape, (0, 2, width - 1, 15)))
    over(image, (100, 94, 73), outline(shape, (0, 2, width - 1, 15)))
    for segment in range(SEGMENTS):
        over(image, (34, 46, 47), rectangle(shape, (2 + segment * 10, 4, 10 + segment * 10, 13)))
    for value in ticks:
        x = 2 + value * 2 - 1
        over(image, GOLD, rectangle(shape, (x, 0, x + 1, 17)))
    return image


def segment_image() -> np.ndarray:
    """Gauge cells: calm, warning and danger notoriety, readiness and the landing threshold."""
    colours = ((200, 178, 118), (222, 146, 66), (204, 74, 56), (112, 150, 104), (150, 206, 120))
    frames = []
    for colour in colours:
        frame = canvas(9, 10)
        over(frame, colour, rectangle((10, 9), (0, 0, 8, 9)))
        over(frame, (255, 255, 255), rectangle((10, 9), (0, 0, 8, 1)), 0.18)
        frames.append(frame)
    return np.concatenate(frames, axis=1)


def pip_image() -> np.ndarray:
    """Slot pips: flotilla at sea, prepared order, free slot, locked slot."""
    shape = (16, 16)
    frames = []
    at_sea = canvas(16, 16)
    over(at_sea, RAID, disc(shape, (8, 8), 6.6))
    over(at_sea, (19, 30, 32), polygon(shape, [(3.5, 8.5), (12.5, 8.5), (10.5, 11.5), (5.5, 11.5)]))
    over(at_sea, (19, 30, 32), stroke(shape, np.array([[8, 3.5], [8, 8.5]]), 1.2))
    frames.append(at_sea)
    prepared = canvas(16, 16)
    over(prepared, GOLD, disc(shape, (8, 8), 6.6))
    over(prepared, (19, 30, 32), polygon(shape, [(4.5, 4.5), (11.5, 4.5), (11, 9.5), (8, 12), (5, 9.5)]))
    frames.append(prepared)
    free = canvas(16, 16)
    over(free, GOLD, disc(shape, (8, 8), 6.6, 4.8))
    frames.append(free)
    locked = canvas(16, 16)
    over(locked, CLOSED, disc(shape, (8, 8), 6.6, 5.2), 0.8)
    over(locked, CLOSED, stroke(shape, np.array([[4.2, 11.8], [11.8, 4.2]]), 1.2), 0.8)
    frames.append(locked)
    return np.concatenate(frames, axis=1)


def ui_images() -> dict[str, np.ndarray]:
    return {
        "marker.png": marker_image(),
        "gauge_notoriety.png": gauge_image(NOTORIETY_TICKS),
        "gauge_revenge.png": gauge_image(REVENGE_TICKS),
        "segment.png": segment_image(),
        "pip.png": pip_image(),
    }


FRAME_COUNTS = {"segment": 5, "pip": 4}


# ----- GUI and GFX bindings -----

def icon(name: str, x: int, y: int, sprite: str, frame: int | None = None) -> list[str]:
    lines = ["\t\ticonType = {", f'\t\t\tname = "{name}"', f"\t\t\tposition = {{ x = {x} y = {y} }}",
             f'\t\t\tquadTextureSprite = "{sprite}"']
    if frame is not None:
        lines.append(f"\t\t\tframe = {frame}")
    return lines + ["\t\t}", ""]


def notoriety_frame(segment: int) -> int:
    value = segment * 5
    if value > 75:
        return 3
    if value > 50:
        return 2
    return 1


def revenge_frame(segment: int) -> int:
    return 5 if segment * 5 > 70 else 4


def gui_block(geometry: dict) -> str:
    lines = []
    for tag in TARGETS:
        for frame, state in enumerate(FRAMES, 1):
            lines.extend(icon(f"NAM_pw_lane_{tag}_{state}", MAP_X, MAP_Y, f"GFX_NAM_pw_lane_{tag}", frame))
    island_x, island_y = geometry["island_label"]
    lines.extend(("\t\tinstantTextBoxType = {", '\t\t\tname = "NAM_pw_islands_label"',
                  f"\t\t\tposition = {{ x = {MAP_X + island_x} y = {MAP_Y + island_y} }}",
                  '\t\t\ttext = "NAM_pw_islands_label"', '\t\t\tfont = "hoi_16mbs"', f"\t\t\tmaxWidth = {ISLAND_LABEL_WIDTH}",
                  f"\t\t\tmaxHeight = {LABEL_HEIGHT}", "\t\t\tformat = centre", "\t\t\tfixedsize = yes",
                  "\t\t\talwaystransparent = yes", "\t\t}", ""))
    for tag in TARGETS:
        x, y = geometry["markers"][tag]
        left = MAP_X + int(round(x)) - MARKER // 2
        top = MAP_Y + int(round(y)) - MARKER // 2
        label_x, label_y, align = geometry["labels"][tag]
        lines.extend(("\t\tinstantTextBoxType = {", f'\t\t\tname = "NAM_pw_label_{tag}"',
                      f"\t\t\tposition = {{ x = {MAP_X + label_x} y = {MAP_Y + label_y} }}",
                      f'\t\t\ttext = "NAM_pw_lane_{tag}_name"', '\t\t\tfont = "hoi_16mbs"', f"\t\t\tmaxWidth = {LABEL_WIDTH}",
                      f"\t\t\tmaxHeight = {LABEL_HEIGHT}", f"\t\t\tformat = {align}",
                      "\t\t\tfixedsize = yes", "\t\t\talwaystransparent = yes", "\t\t}", ""))
        lines.extend(("\t\tbuttonType = {", f'\t\t\tname = "NAM_pw_raid_{tag}"',
                      f"\t\t\tposition = {{ x = {left} y = {top} }}",
                      '\t\t\tquadTextureSprite = "GFX_NAM_pw_marker"', "\t\t\tclicksound = click_default",
                      f'\t\t\tpdx_tooltip = "NAM_pw_route_{tag}_tt"', "\t\t}", ""))
    for gauge, row, colour in (("notoriety", NOTORIETY_ROW, notoriety_frame), ("revenge", REVENGE_ROW, revenge_frame)):
        lines.extend(icon(f"NAM_pw_{gauge}_track", BAR_X, row, f"GFX_NAM_pw_gauge_{gauge}"))
        for segment in range(1, SEGMENTS + 1):
            lines.extend(icon(f"NAM_pw_{gauge}_{segment}", BAR_X + 2 + (segment - 1) * 10, row + 4,
                              "GFX_NAM_pw_segment", colour(segment)))
    for group, row, states in (("fleet", FLEET_ROW, (("sea", 1), ("free", 3), ("locked", 4))),
                               ("marine", MARINE_ROW, (("ready", 2), ("open", 3), ("locked", 4)))):
        for slot, x in enumerate(PIP_X, 1):
            for state, frame in states:
                lines.extend(icon(f"NAM_pw_{group}_{slot}_{state}", x, row + 1, "GFX_NAM_pw_pip", frame))
    return "\n".join(lines).rstrip()


def gfx_block(images: dict[str, np.ndarray]) -> str:
    lines = []
    for filename in images:
        name = Path(filename).stem
        frames = 4 if name.startswith("lane_") else FRAME_COUNTS.get(name, 1)
        lines.extend(("\tspriteType = {", f'\t\tname = "GFX_NAM_pw_{name}"',
                      f'\t\ttexturefile = "{(OUT / filename).as_posix()}"', f"\t\tnoOfFrames = {frames}"))
        if name == "marker":
            lines.append('\t\teffectFile = "gfx/FX/buttonstate.lua"')
        lines.extend(("\t}", ""))
    return "\n".join(lines).rstrip()


def replace_generated(path: Path, content: str, indent: str) -> bytes:
    """Replace the generated section and keep the checkout's line endings."""
    source = (ROOT / path).read_bytes().decode("utf-8")
    newline = "\r\n" if "\r\n" in source else "\n"
    source = source.replace("\r\n", "\n")
    pattern = rf"(?m)^[\t ]*{BEGIN}.*?^[\t ]*{END}"
    replacement = f"{indent}{BEGIN}\n{content}\n{indent}{END}"
    updated, count = re.subn(pattern, lambda _: replacement, source, flags=re.S)
    if count != 1:
        raise ValueError(f"Expected one generated map section in {path}")
    return updated.replace("\n", newline).encode("utf-8")


def build_outputs() -> tuple[dict[Path, bytes], dict, dict[str, np.ndarray]]:
    images, geometry = chart(read_geography())
    images.update(ui_images())
    outputs = {OUT / filename: png_bytes(image) for filename, image in images.items()}
    outputs[GUI] = replace_generated(GUI, gui_block(geometry), "\t\t")
    outputs[GFX] = replace_generated(GFX, gfx_block(images), "\t")
    return outputs, geometry, images


def check_outputs(outputs: dict[Path, bytes]) -> list[str]:
    return [path.as_posix() for path, expected in outputs.items()
            if not (ROOT / path).is_file() or (ROOT / path).read_bytes() != expected]


def preview(images: dict[str, np.ndarray], geometry: dict) -> np.ndarray:
    """The chart with every lane in a different state and its raid markers, doubled."""
    image = images["map.png"].copy()
    states = {"EFL": 1, "AZH": 0, "ULV": 2, "RIV": 0, "LUR": 3, "CHD": 0}
    for tag in TARGETS:
        strip = images[f"lane_{tag}.png"]
        frame = strip[:, states[tag] * WIDTH:(states[tag] + 1) * WIDTH]
        alpha = frame[..., 3:4]
        image[..., :3] = frame[..., :3] * alpha + image[..., :3] * (1 - alpha)
    marker = images["marker.png"]
    for x, y in geometry["markers"].values():
        left = int(round(x)) - MARKER // 2
        top = int(round(y)) - MARKER // 2
        area = image[top:top + MARKER, left:left + MARKER]
        alpha = marker[..., 3:4]
        area[..., :3] = marker[..., :3] * alpha + area[..., :3] * (1 - alpha)
    # Text boxes are rendered by the game; the preview outlines their areas.
    shape = (HEIGHT, WIDTH)
    island_x, island_y = geometry["island_label"]
    boxes = [(island_x, island_y, island_x + ISLAND_LABEL_WIDTH - 1, island_y + LABEL_HEIGHT - 1)]
    boxes += [(x, y, x + LABEL_WIDTH - 1, y + LABEL_HEIGHT - 1) for x, y, _ in geometry["labels"].values()]
    for box in boxes:
        over(image, SAND, outline(shape, box), 0.5)
    return image.repeat(2, axis=0).repeat(2, axis=1)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true", help="check generated assets (default)")
    mode.add_argument("--apply", action="store_true", help="write changed assets and map bindings")
    parser.add_argument("--preview", type=Path, help="also write a review image to this path outside the mod")
    args = parser.parse_args()
    outputs, geometry, images = build_outputs()
    changed = check_outputs(outputs)
    if args.apply:
        for relative in changed:
            path = ROOT / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(outputs[Path(relative)])
        print(f"NAM piracy assets written: {len(changed)}")
    else:
        for relative in changed:
            print(f"Different or missing: {relative}")
    if args.preview:
        args.preview.write_bytes(png_bytes(preview(images, geometry)))
        print(f"Preview written: {args.preview}")
    left, top, scale = geometry["view"]
    print(f"Raid radius: {geometry['radius']:.0f} px by sea; chart origin ({left:.0f}, {top:.0f}), scale {scale}")
    for tag in TARGETS:
        x, y = geometry["markers"][tag]
        print(f"{tag}: port {geometry['ports'][tag]}, lane {geometry['lengths'][tag]:.0f} px, marker ({x:.0f}, {y:.0f})")
    remaining = check_outputs(outputs)
    print(f"NAM piracy assets checked: {len(outputs)}; differences: {len(remaining)}")
    return int(bool(remaining))


if __name__ == "__main__":
    raise SystemExit(main())
