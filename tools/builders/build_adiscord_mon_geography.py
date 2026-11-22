"""Generate the Montar Empire geography: carved cities, relief, rivers, terrain and trees.

The default mode and ``--check`` list differences against the expected outputs.
``--plan-provinces`` writes the reviewed province geometry once, ``--preview``
writes review images and ``--apply`` writes the map outputs.
"""

from __future__ import annotations

import argparse
import heapq
import json
import os
import re
from bisect import bisect_right
from collections import Counter, defaultdict, deque
from dataclasses import dataclass, field
from io import BytesIO
from math import cos, radians, sin
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw
from scipy.ndimage import distance_transform_edt, find_objects, gaussian_filter, label

from tools.builders.build_adiscord_coastal_geography import (
    STANDING_SLOTS,
    border_contacts,
    complete_native_anchors,
    moving_anchors_native,
    native_slots,
    province_grid,
    province_interior,
    province_neighbours,
    standing_anchor_central,
)
from tools.builders.build_adiscord_ivn_geography import (
    CITY_DONOR_SHARE,
    CITY_MIN_NEIGHBOURS,
    CITY_PIXELS,
    CITY_SITE_DISTANCE,
    RIVER_LAND_PALETTE,
    RIVER_MOUTH_RADIUS,
    RIVER_SEA_PALETTE,
    RIVER_SHORE_CLEARANCE,
    RIVER_SOURCE_PALETTE,
    UNIFORM_TERRAIN_PALETTES,
    URBAN_PALETTE,
    _grow_compact_region,
    _prune_river_loops,
    _route_river,
    _snap_river_point,
    _tree_cell_sample_from_pixels,
    carve_junction_city,
    lattice_noise,
    level_towns_with_surroundings,
    masked_slopes,
    native_river_bmp,
    neighbours_of,
    normal_from_height,
    palette_types,
    polyline_distance,
    province_adjacency,
    province_borders,
    province_colour,
    province_terrain_type,
    remove_four_province_corners,
    river_width_palette,
    stable_unit_hash,
    tree_probability,
)
from tools.lib.coastal_clearance import (
    URBAN_FALLBACK_PALETTE,
    tree_cells_blocked,
    urban_blocked,
)
from tools.lib.paths import repository_root


ROOT = repository_root()
DATA_PATH = Path("tools/data/adiscord_mon_geography.json")
GEOMETRY_PATH = Path("tools/data/adiscord_mon_province_geometry.png")
PREVIEW_DIR = Path("docs/development/previews/MON_map")
PROVINCES = Path("map/provinces.bmp")
DEFINITION = Path("map/definition.csv")
HEIGHTMAP = Path("map/heightmap.bmp")
WORLD_NORMAL = Path("map/world_normal.bmp")
TERRAIN = Path("map/terrain.bmp")
TREES = Path("map/trees.bmp")
RIVERS = Path("map/rivers.bmp")
CITIES = Path("map/cities.bmp")
UNITSTACKS = Path("map/unitstacks.txt")
RAILWAYS = Path("map/railways.txt")
STATE_NAMES = Path("localisation/russian/state_names_l_russian.yml")

WINDOW_MARGIN = 40
REMAINDER_MIN_PIXELS = 60
DISTRICT_PIXELS = 45
# Placeholder label of a district while its site is evaluated.
DISTRICT_MARKER = -2
DISTRICT_ANCHOR_DISTANCE = 4.0
LEFTOVER_MARKER = -1
SITE_MARGIN = 30
VILLAGE_CITY_DISTANCE = 10.0
VILLAGE_SPACING = 15.0
VILLAGE_CORE_PIXELS = 8
URBAN_FRINGE_CITIES = frozenset({2845, 9899, 6028, 4018})
URBAN_FRINGE_SHARE = 0.18
# Settlements stay out of a canyon: town levelling would fill the gorge.
CANYON_SETTLEMENT_CLEARANCE = 8.0
# The state base field is smoothed this much, so no step appears on a state border.
LEVEL_SIGMA = 12.0
# Valleys deepen from 1.5 height units under the narrowest river to 4 under the widest.
VALLEY_RADIUS = 2.0
VALLEY_MIN_DEPTH = 1.5
VALLEY_MAX_DEPTH = 4.0
WIDEST_RIVER_PALETTE = 11
RIVER_FLOW_IN_PALETTE = 1
REPAIR_WINDOW = 8
# A run blocked by its own course takes in up to this many rings of course pixels.
REPAIR_RINGS = 6
# A river may meet its receiver within this distance of its last waypoint.
CONFLUENCE_RADIUS = 18
# An owned reach is traced through side neighbours first, then diagonal ones.
REACH_DIAGONAL_COST = 3
REACH_STEPS = ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1))
# Shipped width palettes from narrow to wide; native river maps never use 5 and 8.
WIDTH_STEPS = (3, 4, 6, 7, 9, 10, 11)
# A river joins an existing one at least this wide when such a reach is in range.
JOIN_MIN_WIDTH = 6
# Pixels at either end of a course where no other river may join it.
JOIN_END_CLEARANCE = 3
# A new join keeps this far from every other flow-in pixel; no two junctions lie within JUNCTION_GAP.
JUNCTION_SPACING = 8
JUNCTION_GAP = 3
# A river entering a canyon cuts a side ravine over this many last pixels.
RAVINE_PIXELS = 10
RAVINE_BANK_SLOPE = 2.0
RAVINE_RADIUS = 2.5
RAVINE_FLOOR_TOLERANCE = 3
REACHABLE_PIECE_PIXELS = 50
# A course that cuts a province is routed again without the cutting pixels.
ROUTE_ATTEMPTS = 12
SLIVER_PIXELS = 3
MOUNTAIN_HEIGHT = 160
MOUNTAIN_SLOPE = 12
HILLS_HEIGHT = 132
HILLS_SLOPE = 6
MARSH_HEIGHT = 106
CITY_HOUSES_INDEX = 15
CITY_BACKGROUND_INDEX = 1
TREE_PALETTES = (6, 5)
TERRAIN_BANDS = {
    "plains": (185, 215),
    "hills": (110, 140),
    "forest": (110, 140),
    "mountain": (16, 30),
    "marsh": (8, 16),
}
# Frozen state names: the relief must agree with the landform each name gives.
NAMED_LANDFORMS = {"нагорье": "upland", "холмы": "hills", "леса": "forest", "равнина": "plains"}
UPLAND_HIGH_SHARE = 0.6
UPLAND_MIN_MOUNTAINS = 3
FORBIDDEN_TERRAINS = frozenset({"contaminated", "reactor_zone"})
# Village names that describe the place pick the matching province.
RIVER_VILLAGE_WORDS = ("брод", "мельница", "Фаллен")
PASS_VILLAGE_WORDS = ("перевал",)
MARSH_VILLAGE_WORDS = ("Гать",)


@dataclass(frozen=True)
class Window:
    y0: int
    y1: int
    x0: int
    x1: int

    @property
    def s(self) -> tuple[slice, slice]:
        return (slice(self.y0, self.y1), slice(self.x0, self.x1))

    def local(self, point: list[int] | tuple[int, int]) -> tuple[int, int]:
        """Return a map point (x, row) in window coordinates (x, row)."""
        return int(point[0]) - self.x0, int(point[1]) - self.y0


@dataclass
class Definition:
    lines: list[str]
    newline: str
    bom: bytes
    rows: dict[int, list[str]] = field(default_factory=dict)

    def colours(self) -> dict[int, tuple[int, int, int]]:
        return {province: tuple(map(int, row[1:4])) for province, row in self.rows.items()}

    def kinds(self) -> dict[int, str]:
        return {province: row[4] for province, row in self.rows.items()}

    def encode(self) -> bytes:
        text = self.newline.join(";".join(self.rows[int(line.split(";")[0])]) if line[:1].isdigit() else line for line in self.lines)
        return self.bom + (text + self.newline).encode("utf-8")


@dataclass
class Scope:
    """Province sets of the MON scope; planned ids are children of a parent."""

    states: list[int]
    state_of: dict[int, int]
    original: frozenset[int]
    planned: dict[int, dict]
    cities: dict[int, int]
    districts: frozenset[int]
    remainders: dict[int, int]

    @property
    def provinces(self) -> frozenset[int]:
        return frozenset(self.state_of)

    @property
    def urban(self) -> frozenset[int]:
        return frozenset(self.cities) | self.districts


@dataclass
class RiverNetwork:
    pixels: np.ndarray
    existing: np.ndarray
    routes: dict[str, list[tuple[int, int]]]
    confluences: dict
    mouths: dict[str, dict]
    issues: list[str]


@dataclass
class MonPlan:
    outputs: dict[Path, bytes]
    issues: list[str]
    report: dict


def read_json(root: Path) -> dict:
    return json.loads((root / DATA_PATH).read_text(encoding="utf-8"))


def _inline(value) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(", ", ": "))


def dump_data(data: dict) -> str:
    """Serialise the data file in its authored layout: one record per line."""
    lines = ["{"]
    items = list(data.items())
    for index, (key, value) in enumerate(items):
        comma = "," if index + 1 < len(items) else ""
        if isinstance(value, dict):
            lines.append(f"  {_inline(key)}: {{")
            inner = list(value.items())
            for inner_index, (inner_key, inner_value) in enumerate(inner):
                inner_comma = "," if inner_index + 1 < len(inner) else ""
                if isinstance(inner_value, list) and inner_value and isinstance(inner_value[0], dict):
                    lines.append(f"    {_inline(inner_key)}: [")
                    lines.extend(
                        f"      {_inline(item)}{',' if item_index + 1 < len(inner_value) else ''}"
                        for item_index, item in enumerate(inner_value)
                    )
                    lines.append(f"    ]{inner_comma}")
                else:
                    lines.append(f"    {_inline(inner_key)}: {_inline(inner_value)}{inner_comma}")
            lines.append(f"  }}{comma}")
        elif isinstance(value, list) and value and isinstance(value[0], dict):
            lines.append(f"  {_inline(key)}: [")
            lines.extend(
                f"    {_inline(item)}{',' if item_index + 1 < len(value) else ''}"
                for item_index, item in enumerate(value)
            )
            lines.append(f"  ]{comma}")
        else:
            lines.append(f"  {_inline(key)}: {_inline(value)}{comma}")
    lines.append("}")
    return "\n".join(lines) + "\n"


def state_provinces(root: Path, state_id: int) -> frozenset[int]:
    matches = sorted((root / "history/states").glob(f"{state_id}-*.txt"))
    if len(matches) != 1:
        raise RuntimeError(f"state {state_id}: expected one history file, found {len(matches)}")
    source = matches[0].read_text(encoding="utf-8-sig")
    block = re.search(r"\bprovinces\s*=\s*\{([^}]*)\}", source)
    if block is None:
        raise RuntimeError(f"state {state_id}: missing provinces block")
    return frozenset(int(value) for value in re.findall(r"\d+", block.group(1)))


def load_scope(root: Path, data: dict) -> Scope:
    planned = {int(entry["province"]): entry for entry in data["planned"]["provinces"]}
    state_of: dict[int, int] = {}
    for state_id in data["states"]:
        for province in state_provinces(root, state_id):
            if province in state_of:
                raise RuntimeError(f"province {province}: listed by states {state_of[province]} and {state_id}")
            state_of[province] = state_id
    original = frozenset(state_of) - frozenset(planned)
    for province, entry in planned.items():
        if state_of.get(province, entry["state"]) != entry["state"]:
            raise RuntimeError(f"province {province}: planned for state {entry['state']}, listed elsewhere")
        if state_of[int(entry["parent"])] != entry["state"]:
            raise RuntimeError(f"province {province}: its parent lies outside state {entry['state']}")
        state_of[province] = int(entry["state"])
    cities = {int(parent): int(city) for parent, city in data["planned"]["cities"].items()}
    districts = frozenset(province for province, entry in planned.items() if entry["kind"] == "district")
    remainders = {
        int(entry["parent"]): province for province, entry in planned.items() if entry["kind"] == "remainder"
    }
    return Scope(list(data["states"]), state_of, original, planned, cities, districts, remainders)


def read_definition(root: Path) -> Definition:
    raw = (root / DEFINITION).read_bytes()
    text = raw.decode("utf-8-sig")
    newline = "\r\n" if "\r\n" in text else "\n"
    lines = text.splitlines()
    definition = Definition(lines, newline, b"\xef\xbb\xbf" if raw.startswith(b"\xef\xbb\xbf") else b"")
    for line in lines:
        if line[:1].isdigit():
            definition.rows[int(line.split(";")[0])] = line.split(";")
    return definition


def register_planned_rows(definition: Definition, data: dict) -> None:
    """Append the planned provinces, or confirm they were appended before.

    Planned ids continue the id sequence of the plan. Another builder that
    appended provinces since the plan took them, so the plan must be redone.
    """
    entries = sorted(data["planned"]["provinces"], key=lambda entry: entry["province"])
    if not entries:
        return
    present = [int(entry["province"]) in definition.rows for entry in entries]
    if all(present):
        for entry in entries:
            if list(map(int, definition.rows[int(entry["province"])][1:4])) != list(entry["rgb"]):
                raise RuntimeError(f"province {entry['province']}: definition colour differs from the plan")
        return
    if any(present):
        raise RuntimeError("definition.csv holds only part of the planned MON provinces")
    first_id = int(data["planned"]["first_id"])
    if max(definition.rows) + 1 != first_id:
        raise RuntimeError(
            f"definition.csv ends at {max(definition.rows)}, the plan starts at {first_id}: replan the provinces"
        )
    for expected, entry in enumerate(entries, start=first_id):
        if int(entry["province"]) != expected:
            raise RuntimeError(f"planned province {entry['province']}: ids are not contiguous")
        parent = definition.rows[int(entry["parent"])]
        row = [str(expected), *map(str, entry["rgb"]), "land", "false", parent[6], parent[7]]
        definition.rows[expected] = row
        definition.lines.append(";".join(row))


def rail_pairs(root: Path) -> set[tuple[int, int]]:
    pairs = set()
    for line in (root / RAILWAYS).read_text(encoding="utf-8-sig").splitlines():
        fields = line.split()
        if len(fields) < 3 or not all(value.isdigit() for value in fields):
            continue
        chain = [int(value) for value in fields[2:]]
        pairs.update((min(a, b), max(a, b)) for a, b in zip(chain, chain[1:]) if a != b)
    return pairs


def rail_neighbours(pairs: set[tuple[int, int]], province: int) -> set[int]:
    return {b if a == province else a for a, b in pairs if province in (a, b)}


def mon_window(grid: np.ndarray, provinces: frozenset[int]) -> Window:
    ys, xs = np.nonzero(np.isin(grid, list(provinces)))
    return Window(
        max(0, int(ys.min()) - WINDOW_MARGIN),
        min(grid.shape[0], int(ys.max()) + WINDOW_MARGIN + 1),
        max(0, int(xs.min()) - WINDOW_MARGIN),
        min(grid.shape[1], int(xs.max()) + WINDOW_MARGIN + 1),
    )


def stamp_geometry(root: Path, rgb: np.ndarray, data: dict, colours: dict, scope: Scope) -> np.ndarray:
    """Return provinces.bmp pixels with the reviewed MON geometry stamped in."""
    if not data["planned"]["provinces"]:
        return rgb
    with Image.open(root / GEOMETRY_PATH) as source:
        geometry = np.asarray(source.convert("RGBA"))
    x0, y0 = data["planned"]["origin"]
    height, width = geometry.shape[:2]
    result = rgb.copy()
    region = result[y0:y0 + height, x0:x0 + width]
    stamped = geometry[..., 3] > 0
    allowed = {colours[province] for province in scope.provinces}
    current = {tuple(int(value) for value in colour) for colour in np.unique(region[stamped], axis=0)}
    planned = {tuple(int(value) for value in colour) for colour in np.unique(geometry[..., :3][stamped], axis=0)}
    if not current <= allowed or not planned <= allowed:
        raise RuntimeError("MON province geometry would change land outside the MON scope")
    region[stamped] = geometry[..., :3][stamped]
    return result


def ellipse_radius(gx: np.ndarray, gy: np.ndarray, feature: dict) -> np.ndarray:
    """Normalised elliptic radius of a rotated authored feature (1 on its rim)."""
    cx, cy = feature["centre"]
    rx, ry = feature["radii"]
    angle = radians(feature.get("angle", 0))
    dx = gx - cx
    dy = gy - cy
    u = dx * cos(angle) + dy * sin(angle)
    v = -dx * sin(angle) + dy * cos(angle)
    return np.sqrt((u / rx) ** 2 + (v / ry) ** 2)


def zone_mask(gx: np.ndarray, gy: np.ndarray, zones: list[dict]) -> np.ndarray:
    result = np.zeros(gx.shape, bool)
    for zone in zones:
        result |= ellipse_radius(gx, gy, zone) <= 1.0
    return result


def state_level_range(data: dict, states: np.ndarray, mon: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    low = np.zeros(states.shape)
    high = np.zeros(states.shape)
    covered = np.zeros(states.shape, bool)
    for level in data["levels"]:
        inside = np.isin(states, level["states"])
        low[inside] = level["range"][0]
        high[inside] = level["range"][1]
        covered |= inside
    if (mon & ~covered).any():
        missing = sorted(set(np.unique(states[mon & ~covered]).tolist()))
        raise RuntimeError(f"states without a relief level: {missing}")
    return low, high


def relief_target(data: dict, window: Window, mon: np.ndarray, states: np.ndarray) -> np.ndarray:
    """Authored relief of the MON window, before the border blend.

    Heights are a pure function of position, the authored features and the
    state membership, so repeated passes converge.
    """
    gy, gx = np.mgrid[window.y0:window.y1, window.x0:window.x1].astype(float)
    low, high = state_level_range(data, states, mon)
    weight = np.maximum(gaussian_filter(mon.astype(float), LEVEL_SIGMA), 1e-6)
    low = gaussian_filter(low * mon, LEVEL_SIGMA) / weight
    high = gaussian_filter(high * mon, LEVEL_SIGMA) / weight
    variation = 0.6 * lattice_noise(gx, gy, 23.0, 101) + 0.4 * lattice_noise(gx, gy, 11.0, 103)
    base = low + (high - low) * variation
    for basin in data["basins"]:
        pull = np.exp(-1.2 * ellipse_radius(gx, gy, basin) ** 2)
        base -= np.maximum(0.0, base - basin["floor"]) * pull
    uplift = np.zeros(base.shape)
    # An upland is a plateau: its crest stays high across most of its radius.
    for upland in data["uplands"]:
        dome = np.exp(-ellipse_radius(gx, gy, upland) ** 4)
        uplift = np.maximum(uplift, np.maximum(0.0, upland["peak"] - base) * dome)
    for ridge in data["ridges"]:
        distance, along = polyline_distance(gx, gy, [tuple(point) for point in ridge["points"]])
        crest = ridge["crest"] * (0.94 + 0.06 * np.sin(np.pi * along))
        uplift = np.maximum(
            uplift, np.maximum(0.0, crest - base) * np.exp(-((distance / ridge["sigma"]) ** 2))
        )
    level = base + uplift
    smooth = 0.65 * lattice_noise(gx, gy, 9.0, 131) + 0.35 * lattice_noise(gx, gy, 4.0, 137)
    ridged = 1.0 - np.abs(2.0 * lattice_noise(gx, gy, 6.0, 139) - 1.0)
    rugged = np.clip(uplift / 25.0, 0.0, 1.0)
    detail = (1.0 - rugged) * (2.0 * smooth - 1.0) + rugged * (2.0 * ridged - 1.0)
    amplitude = 2.0 + 0.1 * np.maximum(0.0, level - 112.0) + 3.0 * rugged
    return level + amplitude * detail


def owner_provinces(root: Path, tag: str) -> frozenset[int]:
    result: set[int] = set()
    for path in sorted((root / "history/states").glob("*.txt")):
        source = path.read_text(encoding="utf-8-sig")
        owner = re.search(r"(?m)^\s*owner\s*=\s*([A-Z0-9]{3})\b", source)
        block = re.search(r"\bprovinces\s*=\s*\{([^}]*)\}", source)
        if owner and owner.group(1) == tag and block:
            result.update(int(value) for value in re.findall(r"\d+", block.group(1)))
    return frozenset(result)


@dataclass
class Canyon:
    """A gorge along the border between MON and a neighbouring country.

    ``distance`` is the distance of each pixel from the border line, on both
    sides. The far wall lies in ``band``, foreign land within the authored
    band width; there only heights change.
    """

    feature: dict
    foreign: np.ndarray
    distance: np.ndarray
    band: np.ndarray
    course: np.ndarray


def canyon_layers(root: Path, data: dict, labels: np.ndarray, mon: np.ndarray, water: np.ndarray) -> list[Canyon]:
    canyons = []
    for feature in data.get("canyons", []):
        own_tag, other_tag = feature["border"]
        if own_tag != "MON":
            raise RuntimeError(f"canyon {feature['name']}: the first side must be MON")
        foreign = np.isin(labels, list(owner_provinces(root, other_tag))) & ~water
        if not (neighbours_of(foreign) & mon).any():
            raise RuntimeError(f"canyon {feature['name']}: MON does not border {other_tag}")
        inside = distance_transform_edt(~foreign)
        outside = distance_transform_edt(~mon)
        distance = np.where(mon, inside, np.where(foreign, outside, np.inf)) - 0.5
        band = foreign & (distance <= feature["band"])
        canyons.append(Canyon(feature, foreign, distance, band, state_line_course(mon, foreign)))
    return canyons


def state_line_course(mon: np.ndarray, foreign: np.ndarray) -> np.ndarray:
    """MON pixels a river may use to follow the state line to ``foreign``.

    The line itself is the MON pixels beside the far side. Where it steps
    diagonally, the one pixel that joins two of its pixels carries the
    course round the step; no other pixel is offered, so the course leaves
    no sliver of a province between itself and the line.
    """
    line = mon & neighbours_of(foreign)
    joins = np.zeros(mon.shape, np.int8)
    for axis, shift in ((0, 1), (0, -1), (1, 1), (1, -1)):
        joins += np.roll(line, shift, axis)
    diagonal = np.zeros(mon.shape, bool)
    for dy, dx in ((1, 1), (1, -1), (-1, 1), (-1, -1)):
        diagonal |= np.roll(np.roll(foreign, dy, 0), dx, 1)
    return line | (mon & ~line & diagonal & (joins >= 2))


def canyon_reference(source: np.ndarray, canyons: list[Canyon], mon: np.ndarray) -> np.ndarray:
    """Heights of the far-wall bands, taken from the unchanged land beyond them.

    The band itself is lowered by this builder, so its own heights would feed
    back into the next pass.
    """
    reference = source.astype(float)
    for canyon in canyons:
        changed = canyon.band | mon
        _distance, (ny, nx) = distance_transform_edt(changed, return_indices=True)
        beyond = source[ny, nx].astype(float)
        weight = np.maximum(gaussian_filter(canyon.band.astype(float), 1.5), 1e-6)
        smooth = gaussian_filter(beyond * canyon.band, 1.5) / weight
        reference = np.where(canyon.band, smooth, reference)
    return reference


def cut_canyons(heights: np.ndarray, canyons: list[Canyon], mon: np.ndarray, window: Window, minimum: float) -> np.ndarray:
    """Sink each gorge: a narrow floor on the border line and steep walls on both sides."""
    gy, gx = np.mgrid[window.y0:window.y1, window.x0:window.x1].astype(float)
    result = heights.copy()
    for canyon in canyons:
        feature = canyon.feature
        scope = (mon | canyon.band) & (canyon.distance <= feature["half_width"] + 4)
        floor = feature["floor"] + 3.0 * lattice_noise(gx, gy, 7.0, 151)
        reach = feature["half_width"] * (0.85 + 0.3 * lattice_noise(gx, gy, 11.0, 157))
        t = np.clip((canyon.distance - 0.5) / reach, 0.0, 1.0)
        wall = t * t * (3.0 - 2.0 * t)
        cut = np.maximum(minimum, floor + (heights - floor) * wall)
        rim = feature["rim_lift"] * np.exp(-(((canyon.distance - reach - 1.0) / 1.5) ** 2))
        lowered = np.minimum(heights, cut) + np.where(mon, rim, 0.0)
        result = np.where(scope, lowered, result)
    return result


def border_blend(target: np.ndarray, source: np.ndarray, mon: np.ndarray, feather: float) -> tuple[np.ndarray, np.ndarray]:
    """Blend MON heights into the unchanged height of the nearest outside pixel."""
    distance, (ny, nx) = distance_transform_edt(mon, return_indices=True)
    weight = np.minimum(1.0, distance / feather)
    blended = weight * target + (1.0 - weight) * source[ny, nx].astype(float)
    return np.where(mon, blended, source.astype(float)), weight


def carve_valleys(heights: np.ndarray, rivers: np.ndarray, mon: np.ndarray, weight: np.ndarray, minimum: float) -> np.ndarray:
    """Sink the ground along MON river pixels, deeper under wider rivers."""
    river = mon & (rivers < RIVER_SEA_PALETTE)
    if not river.any():
        return heights
    width = np.clip(rivers.astype(float), 3.0, WIDEST_RIVER_PALETTE)
    depth = VALLEY_MIN_DEPTH + (VALLEY_MAX_DEPTH - VALLEY_MIN_DEPTH) * (width - 3.0) / (WIDEST_RIVER_PALETTE - 3.0)
    distance, (ny, nx) = distance_transform_edt(~river, return_indices=True)
    cut = depth[ny, nx] * np.exp(-((distance / VALLEY_RADIUS) ** 2)) * weight
    return np.where(mon, np.maximum(minimum, heights - cut), heights)


def window_labels(grid: np.ndarray, window: Window) -> np.ndarray:
    return grid[window.s].astype(np.int32)


def river_masks(rivers: np.ndarray, water: np.ndarray) -> np.ndarray:
    return (rivers < RIVER_SEA_PALETTE) & ~water


def reference_rivers(data: dict, window: Window, shape: tuple[int, int]) -> np.ndarray:
    """The existing MON river pixels the builder starts from on every pass.

    ``existing_rivers`` records them as they stood before this builder drew
    its own courses, so each pass restores them and routes its rivers anew.
    """
    result = np.full(shape, RIVER_LAND_PALETTE, np.uint8)
    for row, pixels in data["existing_rivers"].items():
        for x, palette in pixels:
            result[int(row) - window.y0, x - window.x0] = palette
    return result


def _river_neighbour_points(mask: np.ndarray, river: np.ndarray) -> list[tuple[int, int]]:
    ring = neighbours_of(mask) & ~mask & river
    return [(int(x), int(y)) for y, x in zip(*np.nonzero(ring))]


def _locally_connected(river: np.ndarray, ends: list[tuple[int, int]]) -> bool:
    xs = [x for x, _y in ends]
    ys = [y for _x, y in ends]
    y0 = max(0, min(ys) - REPAIR_WINDOW)
    x0 = max(0, min(xs) - REPAIR_WINDOW)
    local = river[y0:max(ys) + REPAIR_WINDOW + 1, x0:max(xs) + REPAIR_WINDOW + 1]
    pieces, _count = label(local)
    return len({int(pieces[y - y0, x - x0]) for x, y in ends}) == 1


def repair_existing_rivers(
    rivers: np.ndarray,
    existing: np.ndarray,
    owned: np.ndarray,
    border: np.ndarray,
    cities: np.ndarray,
    heights: np.ndarray,
    packed: np.ndarray,
    origin: tuple[int, int],
    slivers: np.ndarray,
) -> list[str]:
    """Move off-border pixels of the existing MON rivers onto province borders, in place.

    Each run of interior pixels is replaced by the cheapest border path
    between the course pixels on either side. When the course itself holds
    the border pixels the path needs, the run takes in its neighbouring MON
    course pixels, one ring at a time. A run whose ends stay joined without
    it is dropped; a moved source keeps palette 0. Pixels outside MON keep
    their place.
    """
    issues = []
    off = existing & owned & ~border
    pieces, count = label(off)
    for piece in range(1, count + 1):
        cluster = pieces == piece
        if not (rivers[cluster] < RIVER_SEA_PALETTE).any():
            continue
        if not any(
            _repair_run(rivers, grown, owned, border, cities, heights, packed, slivers)
            for grown in _grown_runs(rivers, cluster, owned)
        ):
            issues.append(f"existing river pixels at {_map_point(cluster, origin)} cannot move onto a province border")
    return issues


def _grown_runs(rivers: np.ndarray, cluster: np.ndarray, owned: np.ndarray):
    """The off-border run, then the run with each further ring of its MON course pixels."""
    course = (rivers < RIVER_SEA_PALETTE) & owned
    grown = cluster.copy()
    for _ring in range(REPAIR_RINGS + 1):
        yield grown
        ring = grown.copy()
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                ring |= np.roll(np.roll(grown, dy, 0), dx, 1)
        grown = ring & course


def _end_pair(river: np.ndarray, ends: list[tuple[int, int]]) -> list[tuple[int, int]] | None:
    """The two course pixels a replaced run must join, one on each side of it.

    A wide course has several end pixels on one side; they stay joined to
    each other without the run, and the closest pair across the gap is used.
    """
    xs = [x for x, _y in ends]
    ys = [y for _x, y in ends]
    y0 = max(0, min(ys) - REPAIR_WINDOW)
    x0 = max(0, min(xs) - REPAIR_WINDOW)
    pieces, _count = label(river[y0:max(ys) + REPAIR_WINDOW + 1, x0:max(xs) + REPAIR_WINDOW + 1])
    sides: dict[int, list[tuple[int, int]]] = defaultdict(list)
    for x, y in ends:
        sides[int(pieces[y - y0, x - x0])].append((x, y))
    if len(sides) != 2:
        return None
    first, second = sides.values()
    pairs = sorted(((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2, a, b) for a in first for b in second)
    return [pairs[0][1], pairs[0][2]]


def _repair_run(
    rivers: np.ndarray,
    run: np.ndarray,
    owned: np.ndarray,
    border: np.ndarray,
    cities: np.ndarray,
    heights: np.ndarray,
    packed: np.ndarray,
    slivers: np.ndarray,
) -> bool:
    """Replace one run of course pixels by a border course; leave the rivers unchanged on failure."""
    palettes = rivers[run].copy()
    source = bool((palettes == RIVER_SOURCE_PALETTE).any())
    width = int(palettes.max())
    ends = sorted(_river_neighbour_points(run, (rivers < RIVER_SEA_PALETTE) & ~run))
    rivers[run] = RIVER_LAND_PALETTE
    river = rivers < RIVER_SEA_PALETTE
    if not ends or (not source and (len(ends) == 1 or _locally_connected(river, ends))):
        return True
    end_mask = np.zeros(river.shape, bool)
    for x, y in ends:
        end_mask[y, x] = True
    loose = owned & border & ~river & ~cities
    free = loose & ~neighbours_of(river & ~end_mask)
    if source and len(ends) == 1:
        x, y = ends[0]
        options = [(nx, ny) for nx, ny in ((x, y + 1), (x, y - 1), (x + 1, y), (x - 1, y)) if free[ny, nx]]
        if owned[y, x] and border[y, x] and not cities[y, x]:
            rivers[y, x] = RIVER_SOURCE_PALETTE
            return True
        if options:
            nx, ny = sorted(options, key=lambda point: (point[1], point[0]))[0]
            rivers[ny, nx] = RIVER_SOURCE_PALETTE
            return True
        rivers[run] = palettes
        return False
    ends = _end_pair(river, ends)
    if ends is None:
        rivers[run] = palettes
        return False
    # A course beside another river may have to touch it on its way round.
    for allowed in (free | end_mask, loose | end_mask):
        forbidden = np.zeros(river.shape, bool)
        for _attempt in range(ROUTE_ATTEMPTS):
            try:
                path = _route_river(ends[0], [ends[1]], allowed & ~forbidden, heights, packed)
            except RuntimeError:
                break
            cuts = cutting_pixels(packed, river, path[1:-1], slivers)
            if not cuts.any():
                for x, y in path[1:-1]:
                    rivers[y, x] = width
                return True
            forbidden |= cuts
    rivers[run] = palettes
    return False


def line_pixels(labels: np.ndarray) -> np.ndarray:
    """Pixels on a province border line, including the corner pixels of its diagonal steps.

    A 4-connected course along a diagonal border turns on pixels that touch
    the far province only at a corner; where that province lies outside MON
    the course cannot switch to its side.
    """
    result = province_borders(labels)
    for dy, dx in ((1, 1), (1, -1), (-1, 1), (-1, -1)):
        result |= np.roll(np.roll(labels, dy, 0), dx, 1) != labels
    return result


def _map_point(mask: np.ndarray, origin: tuple[int, int]) -> tuple[int, int]:
    ys, xs = np.nonzero(mask)
    return int(xs[0]) + origin[0], int(ys[0]) + origin[1]


def _mouth_goals(
    river: dict, receiver: np.ndarray, lakes: dict[int, np.ndarray], owned: np.ndarray, open_border: np.ndarray, window: Window
) -> tuple[np.ndarray, np.ndarray]:
    """Return the goal pixels of a river mouth and the extra pixels it may use near them."""
    mx, my = window.local(river["points"][-1])
    near = np.zeros(owned.shape, bool)
    reach = RIVER_MOUTH_RADIUS if "lake" in river["mouth"] else CONFLUENCE_RADIUS
    near[max(0, my - reach):my + reach + 1, max(0, mx - reach):mx + reach + 1] = True
    if "lake" in river["mouth"]:
        target = lakes[int(river["mouth"]["lake"])]
    else:
        target = receiver
    goals = open_border & near & neighbours_of(target) & ~target
    return goals, near


def reachable_pixels(allowed: np.ndarray, start: tuple[int, int] | None) -> np.ndarray:
    """Allowed pixels joined to ``start``, or to any sizeable piece without a start.

    A waypoint snapped into a pocket enclosed by cities or other rivers would
    leave the course without a way on.
    """
    pieces, _count = label(allowed)
    if start is not None:
        return pieces == pieces[start[1], start[0]]
    sizes = np.bincount(pieces.ravel())
    sizes[0] = 0
    return allowed & (sizes[pieces] >= REACHABLE_PIECE_PIXELS)


def trace_course(
    points: list[tuple[int, int]],
    allowed: np.ndarray,
    final: np.ndarray,
    goals: list[tuple[int, int]],
    heights: np.ndarray,
    packed: np.ndarray,
) -> list[tuple[int, int]]:
    """Route a course through its waypoints to one of the mouth pixels."""
    path = [_snap_river_point(points[0], reachable_pixels(allowed, None))]
    reachable = reachable_pixels(allowed, path[0])
    for waypoint in points[1:-1]:
        target = _snap_river_point(waypoint, reachable)
        path.extend(_route_river(path[-1], [target], allowed, heights, packed)[1:])
    path.extend(_route_river(path[-1], [goal for goal in goals if final[goal[1], goal[0]]], final, heights, packed)[1:])
    return _prune_river_loops(path)


def stray_land(inside: np.ndarray, river: np.ndarray, slivers: np.ndarray) -> np.ndarray:
    """Land of one province cut off from its main piece by river pixels.

    A piece of at most SLIVER_PIXELS inside ``slivers`` is a bump of the
    province on a state line that a river cannot follow without branching;
    it is tolerated.
    """
    original, count = label(inside)
    pieces, _pieces = label(inside & ~river)
    stray = np.zeros(inside.shape, bool)
    for component in range(1, count + 1):
        values, sizes = np.unique(pieces[(original == component) & (pieces > 0)], return_counts=True)
        if len(values) < 2:
            continue
        main = values[np.argmax(sizes)]
        for value, size in zip(values.tolist(), sizes.tolist()):
            piece = pieces == value
            if value == main or (size <= SLIVER_PIXELS and not (piece & ~slivers).any()):
                continue
            stray |= piece
    return stray


def cutting_pixels(labels: np.ndarray, river: np.ndarray, path: list[tuple[int, int]], slivers: np.ndarray) -> np.ndarray:
    """Course pixels that split their province once the course is drawn.

    Such a course crosses the province instead of running along its border.
    """
    course = np.zeros(river.shape, bool)
    for x, y in path:
        course[y, x] = True
    drawn = river | course
    result = np.zeros(river.shape, bool)
    for province in np.unique(labels[course]).tolist():
        ys, xs = np.nonzero(labels == province)
        box = np.s_[max(0, ys.min() - 1):ys.max() + 2, max(0, xs.min() - 1):xs.max() + 2]
        inside = labels[box] == province
        stray = stray_land(inside, drawn[box], slivers[box])
        result[box] |= inside & course[box] & neighbours_of(stray)
    return result


def course_palette(river: dict, index: int, length: int) -> int:
    """Width palette of a course pixel; a wide river reaches full width within a few pixels."""
    if not river.get("wide"):
        return river_width_palette(index / length, length)
    fraction = index / length
    # Native river maps never use width palettes 5 and 8; keep to the shipped widths.
    if fraction < 0.04:
        return 9
    if fraction < 0.1:
        return 10
    return WIDEST_RIVER_PALETTE


def body_start(river: dict) -> int:
    """Index of the first width pixel of a course.

    Only a river into a lake starts with a source pixel; the engine draws a
    tributary outward from its flow-in pixel, so it has no source pixel.
    """
    return 1 if "lake" in river["mouth"] else 0


def wider(width: int) -> int:
    """The next shipped width palette, or the widest."""
    return next((value for value in WIDTH_STEPS if value > width), WIDTH_STEPS[-1])


def narrower(width: int) -> int:
    """The shipped width palette below ``width``, or the narrowest."""
    return next((value for value in reversed(WIDTH_STEPS) if value < width), WIDTH_STEPS[0])


def mid_course(receiver: np.ndarray) -> np.ndarray:
    """Receiver pixels with course on two sides: a join there is no head-on meeting."""
    count = np.zeros(receiver.shape, np.int8)
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            if dy or dx:
                count += np.roll(np.roll(receiver, dy, 0), dx, 1)
    return receiver & (count >= 2)


@dataclass(frozen=True)
class Confluence:
    """Where a tributary meets its receiver: the flow-in pixel and the receiver pixel beside it."""

    tributary: str
    receiver: str
    flow_in: tuple[int, int]
    point: tuple[int, int]


def confluence_approaches(
    river: dict,
    receiver: np.ndarray,
    current: np.ndarray,
    lane: np.ndarray,
    window: Window,
    taken: np.ndarray,
) -> dict[tuple[int, int], tuple[int, int]]:
    """Flow-in pixels near the last waypoint, each with the receiver pixel it touches.

    A flow-in pixel touches the river at one side only, mid-course, and the
    pixel behind it lies straight away from the receiver. Every other pixel
    beside a river is closed to the course, so the tributary arrives at a
    right angle. ``taken`` pixels lie too close to another junction.
    """
    mx, my = window.local(river["points"][-1])
    touching = np.zeros(current.shape, np.int8)
    for axis, shift in ((0, 1), (0, -1), (1, 1), (1, -1)):
        touching += np.roll(current, shift, axis)
    clear = lane & ~current & ~neighbours_of(current)
    approaches = {}
    for py, px in zip(*np.nonzero(mid_course(receiver))):
        if max(abs(px - mx), abs(py - my)) > CONFLUENCE_RADIUS:
            continue
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            fx, fy = px + dx, py + dy
            if (
                lane[fy, fx]
                and not current[fy, fx]
                and not taken[fy, fx]
                and touching[fy, fx] == 1
                and clear[fy + dy, fx + dx]
            ):
                approaches[(int(fx), int(fy))] = (int(px), int(py))
    return approaches


def receiver_mask(
    river: dict, routes: dict[str, list[tuple[int, int]]], existing: np.ndarray, rivers: np.ndarray, minimum: int
) -> np.ndarray | None:
    """Pixels of the river this one may join, at least ``minimum`` wide when it is an existing river."""
    mouth = river["mouth"]
    if mouth.get("river") == "existing":
        return existing & (rivers < RIVER_SEA_PALETTE) & (rivers >= minimum) & (rivers != RIVER_FLOW_IN_PALETTE)
    if mouth["river"] not in routes:
        return None
    receiver = np.zeros(rivers.shape, bool)
    # The ends of a course are never a join: two courses would meet head-on.
    for x, y in routes[mouth["river"]][JOIN_END_CLEARANCE:-JOIN_END_CLEARANCE]:
        receiver[y, x] = True
    return receiver


def route_authored_rivers(
    data: dict,
    window: Window,
    rivers: np.ndarray,
    existing: np.ndarray,
    owned: np.ndarray,
    border: np.ndarray,
    water: np.ndarray,
    lakes: dict[int, np.ndarray],
    cities: np.ndarray,
    heights: np.ndarray,
    packed: np.ndarray,
    courses: dict[str, np.ndarray],
    slivers: np.ndarray,
) -> tuple[dict[str, list[tuple[int, int]]], dict[str, Confluence], list[str]]:
    """Route the authored rivers on MON province borders, in place.

    A river keeps two pixels from every other river and more than three
    pixels from water, except at its mouth. Its last pixel touches the lake,
    or is a flow-in pixel beside the receiving river, which it approaches
    straight. A join with an existing river prefers a reach at least as wide
    as the joining river becomes. A gorge river runs only on the MON side of
    its canyon's state line.
    """
    shore = distance_transform_edt(~water) <= RIVER_SHORE_CLEARANCE
    routes: dict[str, list[tuple[int, int]]] = {}
    confluences: dict[str, Confluence] = {}
    issues = []
    open_border = owned & border & ~cities & ~water
    for river in data["rivers"]:
        name = river["name"]
        current = rivers < RIVER_SEA_PALETTE
        blocked = current.copy()
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                blocked |= np.roll(np.roll(current, dy, 0), dx, 1)
        lane = open_border
        if "canyon" in river:
            lane = courses[river["canyon"]] & ~cities & ~water
        allowed = lane & ~blocked & ~shore
        mouth = river["mouth"]
        points = [window.local(point) for point in river["points"]]
        if "lake" in mouth:
            goals_mask, near = _mouth_goals(river, np.zeros(current.shape, bool), lakes, owned, lane & ~current, window)
            goals_mask &= ~neighbours_of(current)
            # Near its mouth a river may cross the shore band, but never runs along the water.
            approach = lane & near & ~current & ~neighbours_of(current) & ~neighbours_of(water)
            options = [(goals_mask, approach, {})]
        else:
            options = []
            # A gorge river may leave its state line near the mouth to meet its receiver square.
            mouth_lane = (lane | open_border) & ~shore
            near = np.zeros(current.shape, bool)
            mx, my = points[-1]
            near[max(0, my - CONFLUENCE_RADIUS):my + CONFLUENCE_RADIUS + 1, max(0, mx - CONFLUENCE_RADIUS):mx + CONFLUENCE_RADIUS + 1] = True
            approach = mouth_lane & near & ~blocked
            junctions = rivers == RIVER_FLOW_IN_PALETTE
            taken = distance_transform_edt(~junctions) <= JUNCTION_SPACING if junctions.any() else junctions
            preferred = WIDEST_RIVER_PALETTE if river.get("wide") else JOIN_MIN_WIDTH
            for minimum in sorted({preferred, JOIN_MIN_WIDTH, 0}, reverse=True):
                receiver = receiver_mask(river, routes, existing, rivers, minimum)
                if receiver is None:
                    break
                flow_ins = confluence_approaches(river, receiver, current, mouth_lane, window, taken)
                goals_mask = np.zeros(current.shape, bool)
                for fx, fy in flow_ins:
                    goals_mask[fy, fx] = True
                options.append((goals_mask, approach, flow_ins))
            if not options:
                issues.append(f"river {name}: receiving river {mouth['river']} was not routed")
                continue
        path = None
        failure = "no mouth pixel"
        for goals_mask, approach, flow_ins in options:
            try:
                path = route_with_cuts(points, allowed, approach, goals_mask, heights, packed, current, slivers)
                break
            except RuntimeError as error:
                failure = str(error)
        if path is None:
            if not river.get("optional"):
                issues.append(f"river {name}: {failure}")
            continue
        for index, (x, y) in enumerate(path):
            if index == 0 and "lake" in mouth:
                rivers[y, x] = RIVER_SOURCE_PALETTE
            elif index == len(path) - 1 and "river" in mouth:
                rivers[y, x] = RIVER_FLOW_IN_PALETTE
            else:
                rivers[y, x] = course_palette(river, index, len(path))
        routes[name] = path
        if flow_ins:
            confluences[name] = Confluence(name, mouth["river"], path[-1], flow_ins[path[-1]])
    return routes, confluences, issues


def route_with_cuts(
    points: list[tuple[int, int]],
    allowed: np.ndarray,
    approach: np.ndarray,
    goals_mask: np.ndarray,
    heights: np.ndarray,
    packed: np.ndarray,
    current: np.ndarray,
    slivers: np.ndarray,
) -> list[tuple[int, int]]:
    """Route a course; a course that cuts a province is routed again without the cutting pixels."""
    goals = [(int(x), int(y)) for y, x in zip(*np.nonzero(goals_mask))]
    if not goals:
        raise RuntimeError("no mouth pixel")
    forbidden = np.zeros(allowed.shape, bool)
    for _attempt in range(ROUTE_ATTEMPTS):
        path = trace_course(
            points, allowed & ~forbidden, (allowed | approach | goals_mask) & ~forbidden, goals, heights, packed
        )
        cuts = cutting_pixels(packed, current, path, slivers)
        if not cuts.any():
            return path
        forbidden |= cuts
    raise RuntimeError("every course cuts a province apart")


def assign_widths(
    data: dict,
    routes: dict[str, list[tuple[int, int]]],
    confluences: dict[str, Confluence],
    rivers: np.ndarray,
) -> None:
    """Set the widths of the authored rivers as one network, in place.

    Widths never shrink downstream. Below a confluence the receiver is one
    step wider than the wider of its two inputs. A river joining an existing
    river is never wider than that river at the join; above each of its own
    confluences it stays one step narrower, and so do its tributaries.
    """
    rivers_by_name = {river["name"]: river for river in data["rivers"]}
    first = {name: body_start(rivers_by_name[name]) for name in routes}
    natural = {
        name: [course_palette(rivers_by_name[name], index, len(path)) for index in range(first[name], len(path) - 1)]
        for name, path in routes.items()
    }
    joins: dict[str, list[tuple[int, str]]] = defaultdict(list)
    for name, confluence in sorted(confluences.items()):
        if confluence.receiver in routes:
            course = routes[confluence.receiver]
            joins[confluence.receiver].append((course.index(confluence.point) - first[confluence.receiver], name))
    limits: dict[str, list[int]] = {}

    def limit(name: str) -> list[int]:
        if name in limits:
            return limits[name]
        confluence = confluences.get(name)
        if confluence is None:
            top = WIDEST_RIVER_PALETTE
        elif confluence.receiver == "existing":
            px, py = confluence.point
            top = int(rivers[py, px])
        else:
            join = routes[confluence.receiver].index(confluence.point) - first[confluence.receiver]
            top = narrower(limit(confluence.receiver)[join])
        bounds = [top] * len(natural[name])
        for join, _tributary in sorted(joins[name], reverse=True):
            bounds[:join] = [min(value, narrower(bounds[join])) for value in bounds[:join]]
        limits[name] = bounds
        return bounds

    widths: dict[str, list[int]] = {}

    def settle(name: str) -> list[int]:
        if name in widths:
            return widths[name]
        bounds = limit(name)
        body = [min(value, bound) for value, bound in zip(natural[name], bounds)]
        for join, tributary in sorted(joins[name]):
            inflow = settle(tributary)[-1]
            needed = min(bounds[join], wider(max(inflow, body[join - 1] if join > 0 else inflow)))
            body[join:] = [max(value, needed) for value in body[join:]]
        widths[name] = np.maximum.accumulate(body).tolist() if body else body
        return widths[name]

    for name in natural:
        settle(name)
    for name, body in widths.items():
        path = routes[name]
        for (x, y), width in zip(path[first[name]:-1], body):
            rivers[y, x] = width
        if "lake" in rivers_by_name[name]["mouth"]:
            x, y = path[-1]
            rivers[y, x] = body[-1] if body else WIDTH_STEPS[0]


def mon_rivers(
    data: dict,
    window: Window,
    source: np.ndarray,
    labels: np.ndarray,
    owned: np.ndarray,
    water: np.ndarray,
    lake_ids: list[int],
    cities: np.ndarray,
    heights: np.ndarray,
    canyons: list[Canyon],
) -> RiverNetwork:
    """Rebuild the MON river layer of the window from the existing rivers and the data."""
    rivers = source.copy()
    rivers[owned] = reference_rivers(data, window, rivers.shape)[owned]
    restored = rivers.copy()
    existing = river_masks(rivers, water)
    packed = labels.astype(np.uint32)
    border = province_borders(packed)
    origin = (window.x0, window.y0)
    slivers = np.zeros(labels.shape, bool)
    for canyon in canyons:
        slivers |= owned & neighbours_of(canyon.foreign)
    issues = repair_existing_rivers(rivers, existing, owned, line_pixels(packed), cities, heights, packed, origin, slivers)
    issues.extend(widen_owned_reaches(data, window, rivers, labels, water))
    issues.extend(bend_receivers(data, window, rivers, owned, border, water))
    existing = river_masks(rivers, water)
    lakes = {lake: labels == lake for lake in lake_ids}
    courses = {canyon.feature["name"]: canyon.course for canyon in canyons}
    routes, confluences, route_issues = route_authored_rivers(
        data, window, rivers, existing, owned, border, water, lakes, cities, heights, packed, courses, slivers
    )
    assign_widths(data, routes, confluences, rivers)
    issues.extend(route_issues)
    mouths = {river["name"]: river["mouth"] for river in data["rivers"]}
    network = RiverNetwork(rivers, existing, routes, confluences, mouths, issues)
    gorge = np.zeros(labels.shape, bool)
    for river in data["rivers"]:
        if "canyon" in river and river["name"] in routes:
            for x, y in routes[river["name"]]:
                gorge[y, x] = courses[river["canyon"]][y, x]
    network.issues.extend(river_network_issues(network, labels, owned, water, lakes, cities, restored, gorge, origin, slivers))
    return network


def trace_reach(reach: dict, window: Window, river: np.ndarray, labels: np.ndarray) -> list[tuple[int, int]]:
    """The course of an existing river from its authored start down to its lake.

    Side steps are preferred to diagonal ones, so the course keeps every
    pixel of a staircase instead of cutting its corners.
    """
    start = window.local(reach["start"])
    if not river[start[1], start[0]]:
        raise RuntimeError(f"owned reach {reach['name']}: start {reach['start']} is no river pixel")
    mouth = neighbours_of(labels == int(reach["mouth"]["lake"]))
    previous: dict[tuple[int, int], tuple[int, int] | None] = {start: None}
    best = {start: 0}
    frontier = [(0, start)]
    while frontier:
        cost, (x, y) = heapq.heappop(frontier)
        if cost > best[(x, y)]:
            continue
        if mouth[y, x]:
            path = [(x, y)]
            while previous[path[-1]] is not None:
                path.append(previous[path[-1]])
            return path[::-1]
        for dx, dy in REACH_STEPS:
            step = (x + dx, y + dy)
            value = cost + (1 if dx == 0 or dy == 0 else REACH_DIAGONAL_COST)
            if river[step[1], step[0]] and value < best.get(step, value + 1):
                best[step] = value
                previous[step] = (x, y)
                heapq.heappush(frontier, (value, step))
    raise RuntimeError(f"owned reach {reach['name']}: no river course to lake {reach['mouth']['lake']}")


def _course_component(river: np.ndarray, start: tuple[int, int], closed: np.ndarray) -> dict[tuple[int, int], int]:
    """River pixels reached from ``start`` without entering ``closed`` pixels, with their step count."""
    steps = {start: 0}
    queue = deque([start])
    while queue:
        x, y = queue.popleft()
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            step = (x + dx, y + dy)
            if river[step[1], step[0]] and not closed[step[1], step[0]] and step not in steps:
                steps[step] = steps[(x, y)] + 1
                queue.append(step)
    return steps


def _plain_width(rivers: np.ndarray, point: tuple[int, int]) -> int:
    x, y = point
    widths = [
        int(rivers[ny, nx])
        for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1))
        if WIDTH_STEPS[0] <= rivers[ny, nx] < RIVER_SEA_PALETTE
    ]
    return max(widths, default=WIDTH_STEPS[0])


def settle_owned_reach_markers(data: dict, rivers: np.ndarray, labels: np.ndarray, water: np.ndarray) -> None:
    """Make each owned reach one drawn course into its lake, in place.

    The engine draws a river to the water from its single source pixel and a
    tributary outward from its flow-in pixel. A flow-in marker on the reach
    itself would stop the drawn course there, so the reach takes it over as
    plain width and the river it met becomes the tributary: its last pixel
    beside the reach turns into its flow-in marker and its own source pixel
    into plain width. The course above the reach start, up to its farthest
    head, is the head of the main stem and carries the one source pixel.
    """
    full = Window(0, rivers.shape[0], 0, rivers.shape[1])
    for reach in data.get("owned_reaches", []):
        river = river_masks(rivers, water)
        path = trace_reach(reach, full, river, labels)
        on_path = np.zeros(rivers.shape, bool)
        for x, y in path:
            on_path[y, x] = True
        width = int(reach["width"])
        junctions = [(x, y) for x, y in path if rivers[y, x] == RIVER_FLOW_IN_PALETTE]
        for x, y in path:
            if rivers[y, x] < WIDTH_STEPS[0]:
                rivers[y, x] = width
        for jx, jy in junctions:
            near = np.zeros(rivers.shape, bool)
            near[jy - 2:jy + 3, jx - 2:jx + 3] = True
            contacts = river & ~on_path & near & neighbours_of(on_path) & (rivers != width)
            for cy, cx in sorted(zip(*np.nonzero(contacts))):
                rivers[cy, cx] = RIVER_FLOW_IN_PALETTE
                closed = on_path | (rivers == RIVER_FLOW_IN_PALETTE)
                closed[cy, cx] = False
                for point in _course_component(river, (int(cx), int(cy)), closed | on_path):
                    if rivers[point[1], point[0]] == RIVER_SOURCE_PALETTE:
                        rivers[point[1], point[0]] = _plain_width(rivers, point)
        closed = on_path | (rivers == RIVER_FLOW_IN_PALETTE)
        sx, sy = path[0]
        closed[sy, sx] = False
        stem = _course_component(river, path[0], closed)
        head = max(stem, key=lambda point: (stem[point], -point[1], -point[0]))
        for point in stem:
            if rivers[point[1], point[0]] == RIVER_SOURCE_PALETTE and point != head:
                rivers[point[1], point[0]] = _plain_width(rivers, point)
        if head != path[0]:
            rivers[head[1], head[0]] = RIVER_SOURCE_PALETTE


def marker_issues(
    data: dict, rivers: np.ndarray, labels: np.ndarray, water: np.ndarray, mon: np.ndarray, routes: dict, window: Window
) -> list[str]:
    """Check the source and flow-in markers the engine draws rivers from.

    A tributary runs away from its flow-in pixel to a dead end or another
    junction, never to a source pixel; a river into a lake has exactly one
    source pixel; no two junctions lie within JUNCTION_GAP pixels; an owned
    reach carries no marker of its own.
    """
    issues = []
    river = river_masks(rivers, water)
    full = Window(0, rivers.shape[0], 0, rivers.shape[1])
    reach_path = np.zeros(rivers.shape, bool)
    for reach in data.get("owned_reaches", []):
        path = trace_reach(reach, full, river, labels)
        for x, y in path:
            reach_path[y, x] = True
        markers = [(x, y) for x, y in path if rivers[y, x] < WIDTH_STEPS[0]]
        if markers:
            issues.append(f"owned reach {reach['name']}: markers on its course at {markers[:3]}")
        closed = reach_path | (rivers == RIVER_FLOW_IN_PALETTE)
        closed[path[0][1], path[0][0]] = False
        stem = _course_component(river, path[0], closed)
        sources = [point for point in stem if rivers[point[1], point[0]] == RIVER_SOURCE_PALETTE]
        if len(sources) != 1:
            issues.append(f"owned reach {reach['name']}: its main stem has {len(sources)} source pixels")
    scope = mon | neighbours_of(reach_path)
    reds = [(int(x), int(y)) for y, x in zip(*np.nonzero(scope & river & (rivers == RIVER_FLOW_IN_PALETTE)))]
    for index, (x, y) in enumerate(reds):
        for ox, oy in reds[index + 1:]:
            if max(abs(x - ox), abs(y - oy)) <= JUNCTION_GAP:
                issues.append(f"junctions {(x, y)} and {(ox, oy)} lie within {JUNCTION_GAP} pixels")
        for tx, ty in tributary_starts(river, (x, y)):
            closed = rivers == RIVER_FLOW_IN_PALETTE
            closed[ty, tx] = False
            reached = _course_component(river, (tx, ty), closed)
            if any(rivers[point[1], point[0]] == RIVER_SOURCE_PALETTE for point in reached):
                issues.append(f"tributary flowing in at {(x, y)} has a source pixel")
    for river_data in data["rivers"]:
        path = routes.get(river_data["name"])
        if path is None:
            continue
        sources = sum(rivers[y + window.y0, x + window.x0] == RIVER_SOURCE_PALETTE for x, y in path)
        expected = 1 if "lake" in river_data["mouth"] else 0
        if sources != expected:
            issues.append(f"river {river_data['name']}: {sources} source pixels, expected {expected}")
    return issues


def tributary_starts(river: np.ndarray, red: tuple[int, int]) -> list[tuple[int, int]]:
    """Course pixels beside a flow-in pixel that lead away from the receiver.

    The receiver continues on both sides of the pixel it shares with the
    flow-in; the tributary pixel has the flow-in as its only course on one side.
    """
    x, y = red
    result = []
    for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
        if not river[ny, nx]:
            continue
        others = sum(
            bool(river[my, mx]) for mx, my in ((nx + 1, ny), (nx - 1, ny), (nx, ny + 1), (nx, ny - 1)) if (mx, my) != red
        )
        if others <= 1:
            result.append((nx, ny))
    return result


def owned_reach_mask(
    data: dict, window: Window, rivers: np.ndarray, labels: np.ndarray, water: np.ndarray
) -> tuple[np.ndarray, list[str]]:
    """Width pixels of every owned reach: its course and the pixels that only thicken it.

    Source, flow-in and split markers keep their palette; a tributary meets
    the reach through its flow-in pixel, so its own course stays outside.
    """
    river = river_masks(rivers, water)
    widths = river & (rivers >= WIDTH_STEPS[0])
    result = np.zeros(rivers.shape, bool)
    issues = []
    for reach in data.get("owned_reaches", []):
        try:
            path = trace_reach(reach, window, river, labels)
        except RuntimeError as error:
            issues.append(str(error))
            continue
        course = np.zeros(rivers.shape, bool)
        for x, y in path:
            course[y, x] = True
        thickening = widths & neighbours_of(course) & ~course
        others = river & ~course & ~thickening
        result |= (course | (thickening & ~neighbours_of(others))) & widths
    return result, issues


def widen_owned_reaches(
    data: dict, window: Window, rivers: np.ndarray, labels: np.ndarray, water: np.ndarray
) -> list[str]:
    """Raise the width palette of every owned reach to its authored width, in place.

    Widths only grow, so a widened reach stays as it is on the next pass.
    """
    issues = []
    for reach in data.get("owned_reaches", []):
        mask, reach_issues = owned_reach_mask({"owned_reaches": [reach]}, window, rivers, labels, water)
        issues.extend(reach_issues)
        rivers[mask] = np.maximum(rivers[mask], int(reach["width"]))
    return issues


def bend_receivers(
    data: dict, window: Window, rivers: np.ndarray, owned: np.ndarray, border: np.ndarray, water: np.ndarray
) -> list[str]:
    """Add the authored bend pixels of existing receivers, in place.

    Where an existing river turns a corner exactly at a join, a flow-in
    pixel would touch it on two sides; one MON border pixel added at the
    corner gives the join a single side to meet.
    """
    issues = []
    for river in data["rivers"]:
        for point in river["mouth"].get("bend", []):
            x, y = window.local(point)
            current = river_masks(rivers, water)
            beside = [
                int(rivers[ny, nx]) for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)) if current[ny, nx]
            ]
            if current[y, x]:
                continue
            if not (owned[y, x] and border[y, x] and beside):
                issues.append(f"river {river['name']}: bend {point} is no MON border pixel beside its receiver")
                continue
            rivers[y, x] = max(beside)
    return issues


def rivers_splitting_provinces(labels: np.ndarray, river: np.ndarray, owned: np.ndarray, slivers: np.ndarray) -> list[int]:
    """Provinces whose land falls apart when their river pixels are taken out.

    A river on a genuine border never cuts the province it runs beside.
    """
    result = []
    boxes = find_objects(np.where(owned & river, labels, 0))
    for index, box in enumerate(boxes):
        if box is None:
            continue
        province = index + 1
        ys, xs = np.nonzero(labels == province)
        window = np.s_[max(0, ys.min() - 1):ys.max() + 2, max(0, xs.min() - 1):xs.max() + 2]
        if stray_land(labels[window] == province, river[window], slivers[window]).any():
            result.append(province)
    return result


def river_network_issues(
    network: RiverNetwork,
    labels: np.ndarray,
    owned: np.ndarray,
    water: np.ndarray,
    lakes: dict[int, np.ndarray],
    cities: np.ndarray,
    source: np.ndarray,
    gorge: np.ndarray,
    origin: tuple[int, int],
    slivers: np.ndarray,
) -> list[str]:
    """Validate the MON rivers: sources, borders, connectivity, branching and mouths.

    A gorge river may turn round a staircase step of its state line on a
    pixel that touches the far side only diagonally.
    """
    rivers = network.pixels
    river = river_masks(rivers, water)
    issues = []
    off_border = river & owned & ~line_pixels(labels) & ~gorge
    if off_border.any():
        issues.append(f"{int(off_border.sum())} MON river pixels cross province interiors, first at {_map_point(off_border, origin)}")
    in_city = river & cities
    if in_city.any():
        issues.append(f"{int(in_city.sum())} river pixels lie inside carved cities")
    split = rivers_splitting_provinces(labels, river, owned, slivers)
    if split:
        issues.append(f"rivers cut provinces {split} into pieces")
    before = label(river_masks(source, water))[1]
    after = label(network.existing & river)[1]
    if after > before:
        issues.append(f"existing rivers split into {after} pieces instead of {before}")
    for name, path in network.routes.items():
        cells = set(path)
        is_lake = "lake" in network.mouths[name]
        if (rivers[path[0][1], path[0][0]] == RIVER_SOURCE_PALETTE) != is_lake:
            issues.append(f"river {name}: a source pixel belongs only to a river into a lake")
        for (ax, ay), (bx, by) in zip(path, path[1:]):
            if abs(ax - bx) + abs(ay - by) != 1:
                issues.append(f"river {name}: course is not 4-connected at {(ax, ay)}")
                break
        branching = [
            (x, y)
            for x, y in path
            if sum((point in cells) for point in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1))) > 2
        ]
        if branching:
            issues.append(f"river {name}: branches at {branching[:3]}")
        body = [int(rivers[y, x]) for x, y in path[(1 if is_lake else 0):-1]]
        if any(later < earlier for earlier, later in zip(body, body[1:])):
            issues.append(f"river {name}: widths shrink downstream")
        if set(body) - set(WIDTH_STEPS):
            issues.append(f"river {name}: uses width palettes {sorted(set(body) - set(WIDTH_STEPS))}")
        mx, my = path[-1]
        mouth = network.mouths[name]
        if "lake" in mouth:
            if not neighbours_of(lakes[int(mouth["lake"])])[my, mx]:
                issues.append(f"river {name}: mouth does not touch lake {mouth['lake']}")
            continue
        confluence = network.confluences.get(name)
        if confluence is None:
            issues.append(f"river {name}: no confluence")
            continue
        issues.extend(confluence_issues(network, confluence, river))
    return issues


def confluence_issues(network: RiverNetwork, confluence: Confluence, river: np.ndarray) -> list[str]:
    """A join: one flow-in pixel on one side of the receiver, a straight approach, a wide enough receiver."""
    rivers = network.pixels
    name = confluence.tributary
    path = network.routes[name]
    if confluence.receiver == "existing":
        receiver = network.existing & river
    else:
        receiver = np.zeros(river.shape, bool)
        for x, y in network.routes[confluence.receiver]:
            receiver[y, x] = True
    issues = []
    fx, fy = confluence.flow_in
    px, py = confluence.point
    contacts = [(x, y) for x, y in ((fx + 1, fy), (fx - 1, fy), (fx, fy + 1), (fx, fy - 1)) if receiver[y, x]]
    if rivers[fy, fx] != RIVER_FLOW_IN_PALETTE or contacts != [(px, py)]:
        issues.append(f"river {name}: flow-in pixel must touch its receiver at exactly one side")
    if not mid_course(receiver)[py, px]:
        issues.append(f"river {name}: meets {confluence.receiver} head-on")
    dx, dy = fx - px, fy - py
    if path[-2] != (fx + dx, fy + dy):
        issues.append(f"river {name}: does not approach {confluence.receiver} straight")
    inflow = int(rivers[path[-2][1], path[-2][0]])
    if int(rivers[py, px]) < inflow:
        issues.append(f"river {name}: {inflow} wide, joins a reach {int(rivers[py, px])} wide")
    if confluence.receiver != "existing":
        course = network.routes[confluence.receiver]
        index = course.index((px, py))
        upstream = int(rivers[course[index - 1][1], course[index - 1][0]]) if index > 1 else inflow
        needed = min(WIDEST_RIVER_PALETTE, wider(max(inflow, upstream)))
        if int(rivers[py, px]) < needed:
            issues.append(f"river {confluence.receiver}: {int(rivers[py, px])} wide below {name}, needs {needed}")
    return issues


def classify_pixels(
    heights: np.ndarray, mon: np.ndarray, forest_zone: np.ndarray, marsh_zone: np.ndarray
) -> np.ndarray:
    """Return a terrain-type index per pixel (TYPE_ORDER), -1 outside MON."""
    slope = masked_slopes(heights, mon)
    mountain = mon & ((heights >= MOUNTAIN_HEIGHT) | (slope >= MOUNTAIN_SLOPE))
    shoulder = mon & ~mountain & neighbours_of(mountain)
    hills = mon & ~mountain & (shoulder | (heights >= HILLS_HEIGHT) | (slope >= HILLS_SLOPE))
    marsh = mon & ~mountain & ~hills & marsh_zone & (heights < MARSH_HEIGHT)
    forest = mon & ~mountain & ~hills & ~marsh & forest_zone
    result = np.full(heights.shape, -1, np.int8)
    result[mon] = TYPE_ORDER.index("plains")
    result[forest] = TYPE_ORDER.index("forest")
    result[marsh] = TYPE_ORDER.index("marsh")
    result[hills] = TYPE_ORDER.index("hills")
    result[mountain] = TYPE_ORDER.index("mountain")
    return result


TYPE_ORDER = ("plains", "forest", "marsh", "hills", "mountain")


def province_types(
    classes: np.ndarray, labels: np.ndarray, scope: Scope, urban_pixels: np.ndarray
) -> tuple[dict[int, str], dict[int, Counter]]:
    counts: dict[int, Counter] = {}
    rural = (classes >= 0) & ~urban_pixels
    values, indices = np.unique(
        labels[rural].astype(np.int64) * len(TYPE_ORDER) + classes[rural], return_counts=False, return_inverse=True
    )
    totals = np.bincount(indices)
    for value, total in zip(values.tolist(), totals.tolist()):
        province, kind = divmod(value, len(TYPE_ORDER))
        counts.setdefault(province, Counter())[TYPE_ORDER[kind]] = total
    desired = {}
    for province in scope.provinces:
        if province in scope.urban:
            desired[province] = "urban"
        elif province in counts:
            desired[province] = province_terrain_type(counts[province])
        else:
            raise RuntimeError(f"province {province}: no rural MON pixels")
    return desired, counts


def village_cores(
    data: dict, labels: np.ndarray, grid: np.ndarray, window: Window, forbidden: np.ndarray
) -> dict[int, np.ndarray]:
    """Grow the compact core of every planned village around its interior centre."""
    boxes = find_objects(grid)
    cores = {}
    for entry in data["settlements"]:
        province = entry.get("province")
        if entry["kind"] != "village" or province is None:
            continue
        _oy, _ox, _inside, _depth, (cx, cy) = province_interior(grid, province, boxes[province - 1])
        candidates = (labels == province) & ~forbidden
        if not candidates.any():
            raise RuntimeError(f"village province {province}: no pixel can hold its core")
        ly, lx = cy - window.y0, cx - window.x0
        if not candidates[ly, lx]:
            ys, xs = np.nonzero(candidates)
            nearest = int(np.argmin((ys - ly) ** 2 + (xs - lx) ** 2))
            ly, lx = int(ys[nearest]), int(xs[nearest])
        cores[province] = _grow_compact_region(candidates, (ly, lx), VILLAGE_CORE_PIXELS)
    return cores


def urban_fringe(labels: np.ndarray, scope: Scope, forbidden: np.ndarray) -> np.ndarray:
    """Built-up edge of the largest cities: the remainder pixels nearest the city."""
    fringe = np.zeros(labels.shape, bool)
    for parent in sorted(URBAN_FRINGE_CITIES & frozenset(scope.cities)):
        remainder = labels == scope.remainders[parent]
        distance = distance_transform_edt(labels != parent)
        candidates = remainder & ~forbidden
        ys, xs = np.nonzero(candidates)
        order = np.lexsort((xs, ys, distance[ys, xs]))
        count = int(URBAN_FRINGE_SHARE * remainder.sum())
        fringe[ys[order[:count]], xs[order[:count]]] = True
    return fringe


def render_trees(
    trees: np.ndarray,
    terrain: np.ndarray,
    state_pixels: np.ndarray,
    palette: dict[int, str],
    blocked: np.ndarray,
    window: Window,
) -> np.ndarray:
    """Regenerate tree cells where MON holds the majority of the cell footprint."""
    tree_height, tree_width = trees.shape
    height, width = terrain.shape
    result = trees.copy()
    flat_terrain = terrain.reshape(-1)
    flat_states = state_pixels.reshape(-1)
    for ty in range(window.y0 * tree_height // height, window.y1 * tree_height // height + 1):
        for tx in range(window.x0 * tree_width // width, window.x1 * tree_width // width + 1):
            sample = _tree_cell_sample_from_pixels(
                tx, ty, tree_width, tree_height, width, height, flat_terrain, flat_states, palette
            )
            if sample.state_id is None:
                continue
            if blocked[ty, tx]:
                result[ty, tx] = 0
            elif stable_unit_hash(tx, ty, 23) < tree_probability(sample.terrain_type):
                result[ty, tx] = TREE_PALETTES[stable_unit_hash(tx, ty, 29) >= 0.65]
            else:
                result[ty, tx] = 0
    return result


def tree_cells_touching(mask: np.ndarray, window: Window, shape: tuple[int, int], tree_shape: tuple[int, int]) -> np.ndarray:
    """Tree cells whose footprint touches the mask, grown by one cell."""
    tree_height, tree_width = tree_shape
    height, width = shape
    cells = np.zeros(tree_shape, bool)
    ys, xs = np.nonzero(mask)
    cells[(ys + window.y0) * tree_height // height, (xs + window.x0) * tree_width // width] = True
    return cells | neighbours_of(cells) | np.roll(neighbours_of(cells), 1, 0) | np.roll(neighbours_of(cells), -1, 0)


def read_unitstacks(data: bytes) -> tuple[list[list[str]], str]:
    text = data.decode("utf-8")
    return [line.split(";") for line in text.splitlines()], ("\r\n" if "\r\n" in text else "\n")


def reconcile_unitstacks(
    original: bytes,
    grid: np.ndarray,
    before: np.ndarray,
    heights: np.ndarray,
    kinds: dict[int, str],
    scope: Scope,
    window: Window,
) -> tuple[bytes, list[int]]:
    """Give every MON province and every changed neighbour native unit anchors.

    A province without rows, or whose standing army stands off its interior
    centre, receives a fresh native set. A province whose slot set or moving
    rows no longer match its borders keeps its standing slots and has its
    moving slots rebuilt in the engine's neighbour order. Every MON row then
    rests on the new heightmap. Rows stay grouped by slot in province order.
    """
    rows, newline = read_unitstacks(original)
    slots: dict[int, dict[int, list[str]]] = defaultdict(dict)
    for row in rows:
        slots[int(row[0])][int(row[1])] = row
    neighbours = province_neighbours(grid)
    local = province_neighbours(grid[window.s])
    old_local = province_neighbours(before[window.s])
    # Outside MON only a province whose borders this pass changed is touched.
    candidates = set(scope.provinces) | {
        province
        for province in set(local) | set(old_local)
        if local.get(province) != old_local.get(province)
    }
    boxes = find_objects(grid)
    map_height = grid.shape[0]
    rebuilt: dict[int, dict[int, list[str]]] = {}
    for province in sorted(candidates):
        kind = kinds.get(province)
        if kind != "land":
            continue
        interior = province_interior(grid, province, boxes[province - 1])
        contacts = border_contacts(grid, province, boxes[province - 1], interior)
        existing = slots.get(province, {})
        offset = None
        if province in scope.planned:
            parent_rows = slots.get(int(scope.planned[province]["parent"]), {})
            offset = parent_rows[0][6] if 0 in parent_rows else None
        if 0 not in existing or not standing_anchor_central(existing[0], grid, interior):
            keep = {}
            offset = existing[0][6] if 0 in existing else offset
        elif set(existing) != native_slots(kind, len(neighbours[province])) or not moving_anchors_native(
            existing, contacts, map_height
        ):
            keep = {slot: row for slot, row in existing.items() if slot in STANDING_SLOTS}
        else:
            continue
        rebuilt[province] = complete_native_anchors(
            province, kind, keep, grid, heights, interior, contacts, offset=offset
        )

    # An anchor rests on the ground under it, also when it lies just across
    # the border; one over water keeps its height.
    def rest(row: list[str]) -> list[str]:
        province = int(row[0])
        if province in scope.provinces:
            x = round(float(row[2]))
            y = map_height - 1 - round(float(row[4]))
            if kinds.get(int(grid[y, x])) == "land":
                row = list(row)
                row[3] = f"{heights[y, x] / 10:.2f}"
        return row

    blocks: dict[int, list[list[str]]] = defaultdict(list)
    for row in rows:
        if int(row[0]) not in rebuilt:
            blocks[int(row[1])].append(rest(row))
    for province, anchors in sorted(rebuilt.items()):
        for slot, row in anchors.items():
            block = blocks[slot]
            prefix = np.maximum.accumulate([int(item[0]) for item in block]).tolist() if block else []
            block.insert(bisect_right(prefix, province), rest(list(row)))
    ordered = [";".join(row) for slot in sorted(blocks) for row in blocks[slot]]
    return (newline.join(ordered) + newline).encode("utf-8"), sorted(rebuilt)


def state_landforms(root: Path, states: list[int]) -> dict[int, str]:
    text = (root / STATE_NAMES).read_text(encoding="utf-8-sig")
    result = {}
    for state_id in states:
        match = re.search(rf"^\s*STATE_{state_id}:\d*\s*\"([^\"]*)\"", text, re.MULTILINE)
        if match is None:
            raise RuntimeError(f"STATE_{state_id}: no Russian name")
        kinds = [kind for word, kind in NAMED_LANDFORMS.items() if word in match.group(1).lower()]
        if len(kinds) != 1:
            raise RuntimeError(f"STATE_{state_id}: name {match.group(1)!r} names no single landform")
        result[state_id] = kinds[0]
    return result


def terrain_issues(desired: dict[int, str], scope: Scope, landforms: dict[int, str]) -> tuple[list[str], dict]:
    """Check the declared terrain against the acceptance bands and the state names.

    A carved parent is urban; the band counts its rural remainder in its place,
    so the bands still cover the 488 original provinces.
    """
    issues = []
    stand_in = {parent: remainder for parent, remainder in scope.remainders.items()}
    counted = [stand_in.get(province, province) for province in scope.original]
    totals = Counter(desired[province] for province in counted)
    for terrain, (low, high) in TERRAIN_BANDS.items():
        if not low <= totals.get(terrain, 0) <= high:
            issues.append(f"{totals.get(terrain, 0)} {terrain} provinces lie outside the band {low}-{high}")
    other = set(totals) - set(TERRAIN_BANDS)
    if other:
        issues.append(f"unexpected declared terrain {sorted(other)}")
    per_state = {}
    for state_id in scope.states:
        rural = [
            desired[province]
            for province, owner in scope.state_of.items()
            if owner == state_id and province not in scope.urban
        ]
        counts = Counter(rural)
        per_state[state_id] = dict(counts)
        landform = landforms[state_id]
        if landform == "upland":
            high = (counts["hills"] + counts["mountain"]) / len(rural)
            if high < UPLAND_HIGH_SHARE or counts["mountain"] < UPLAND_MIN_MOUNTAINS:
                issues.append(f"state {state_id} upland: {counts['hills']} hills and {counts['mountain']} mountain of {len(rural)}")
        elif counts[landform] * 2 <= len(rural):
            issues.append(f"state {state_id} {landform}: only {counts[landform]} of {len(rural)} rural provinces")
    forbidden = sorted(province for province in scope.provinces if desired[province] in FORBIDDEN_TERRAINS)
    if forbidden:
        issues.append(f"forbidden terrain in {forbidden}")
    return issues, {"totals": dict(totals), "states": per_state}


@dataclass
class Geography:
    """Every derived layer of the MON window, shared by the plan and the previews."""

    window: Window
    labels: np.ndarray
    mon: np.ndarray
    states: np.ndarray
    water: np.ndarray
    cities: np.ndarray
    heights: np.ndarray
    network: RiverNetwork
    classes: np.ndarray
    desired: dict[int, str]
    counts: dict[int, Counter]
    cores: dict[int, np.ndarray]
    fringe: np.ndarray
    shore: np.ndarray
    relief_scope: np.ndarray
    canyons: list[Canyon]


@dataclass
class Ground:
    """Province masks and the authored relief of the MON window, before rivers."""

    labels: np.ndarray
    mon: np.ndarray
    water: np.ndarray
    states: np.ndarray
    cities: np.ndarray
    canyons: list[Canyon]
    relief_scope: np.ndarray
    canyon_clearance: np.ndarray
    field: np.ndarray
    weight: np.ndarray
    lake_ids: list[int]


def prepare_ground(
    root: Path, data: dict, scope: Scope, grid: np.ndarray, kinds: dict[int, str], heights: np.ndarray, window: Window
) -> Ground:
    """Build the relief of MON and of its canyon walls from unchanging inputs only.

    The border blend reads the heights outside MON, and inside a far-wall
    band the heights of the land beyond it, so the relief never feeds back on
    itself.
    """
    labels = window_labels(grid, window)
    mon = np.isin(labels, list(scope.provinces))
    water = np.isin(labels, [province for province, kind in kinds.items() if kind in ("sea", "lake")])
    states = np.zeros(labels.shape, np.int32)
    for province, state_id in scope.state_of.items():
        states[labels == province] = state_id
    cities = np.isin(labels, list(scope.urban))
    canyons = canyon_layers(root, data, labels, mon, water)
    reference = canyon_reference(heights, canyons, mon)
    target = relief_target(data, window, mon, states)
    blended, weight = border_blend(target, reference, mon, float(data["heights"]["feather"]))
    relief_scope = mon.copy()
    clearance = np.zeros(mon.shape, bool)
    for canyon in canyons:
        blended = np.where(canyon.band, reference, blended)
        relief_scope |= canyon.band
        clearance |= mon & (canyon.distance < CANYON_SETTLEMENT_CLEARANCE)
    field = cut_canyons(blended, canyons, mon, window, float(data["heights"]["min"]))
    lake_ids = sorted(province for province in np.unique(labels[water]).tolist() if kinds[province] == "lake")
    return Ground(labels, mon, water, states, cities, canyons, relief_scope, clearance, field, weight, lake_ids)


def ground_rivers(data: dict, window: Window, ground: Ground, rivers: np.ndarray) -> RiverNetwork:
    routing = np.clip(np.rint(ground.field), 0, 255).astype(np.int16)
    return mon_rivers(
        data, window, rivers, ground.labels, ground.mon, ground.water, ground.lake_ids, ground.cities, routing, ground.canyons
    )


def build_geography(
    root: Path,
    data: dict,
    scope: Scope,
    grid: np.ndarray,
    definition: Definition,
    sources: dict[str, np.ndarray],
    window: Window,
) -> Geography:
    ground = prepare_ground(root, data, scope, grid, definition.kinds(), sources["heightmap"][window.s], window)
    labels = ground.labels
    mon = ground.mon
    network = ground_rivers(data, window, ground, sources["rivers"][window.s])
    shore = urban_blocked(ground.water) & mon
    river = network.pixels < RIVER_SEA_PALETTE
    forbidden = river | neighbours_of(river) | shore | ground.canyon_clearance
    cores = village_cores(data, labels, grid, window, forbidden | ground.cities)
    fringe = urban_fringe(labels, scope, forbidden)
    floor = float(data["heights"]["min"])
    carved = carve_valleys(ground.field, network.pixels, mon, ground.weight, floor)
    towns = ground.cities | fringe
    for core in cores.values():
        towns |= core
    level_towns_with_surroundings(carved, mon, towns)
    carve_ravines(carved, data, network, ground.relief_scope)
    heights = np.clip(np.rint(carved), floor, float(data["heights"]["max"])).astype(np.uint8)
    heights = np.where(ground.relief_scope, heights, sources["heightmap"][window.s])
    gy, gx = np.mgrid[window.y0:window.y1, window.x0:window.x1].astype(float)
    classes = classify_pixels(
        heights, mon, zone_mask(gx, gy, data["forest_zones"]), zone_mask(gx, gy, data["marsh_zones"])
    )
    urban_pixels = ground.cities | fringe
    for core in cores.values():
        urban_pixels |= core
    desired, counts = province_types(classes, labels, scope, urban_pixels)
    return Geography(
        window, labels, mon, ground.states, ground.water, ground.cities, heights, network, classes, desired, counts,
        cores, fringe, shore, ground.relief_scope, ground.canyons,
    )


def canyon_confluences(data: dict, network: RiverNetwork) -> list[Confluence]:
    gorges = {river["name"] for river in data["rivers"] if "canyon" in river}
    return [confluence for confluence in network.confluences.values() if confluence.receiver in gorges]


def carve_ravines(field: np.ndarray, data: dict, network: RiverNetwork, scope: np.ndarray) -> None:
    """Cut a side ravine down to the gorge floor for every river entering a canyon, in place.

    Over its last RAVINE_PIXELS pixels the river falls evenly from the ground
    above the canyon to the height beside the gorge river; the banks rise
    from the ravine bed at RAVINE_BANK_SLOPE per pixel.
    """
    reach = int(np.ceil(RAVINE_RADIUS))
    offsets = [
        (dx, dy, float(np.hypot(dx, dy)))
        for dy in range(-reach, reach + 1)
        for dx in range(-reach, reach + 1)
        if np.hypot(dx, dy) <= RAVINE_RADIUS
    ]
    for confluence in canyon_confluences(data, network):
        path = network.routes[confluence.tributary]
        tail = path[-RAVINE_PIXELS:]
        top_x, top_y = path[max(0, len(path) - RAVINE_PIXELS - 1)]
        px, py = confluence.point
        top = float(field[top_y, top_x])
        bottom = min(top, float(field[py, px]) + 1.0)
        for index, (x, y) in enumerate(tail, start=1):
            bed = top + (bottom - top) * index / len(tail)
            for dx, dy, distance in offsets:
                if scope[y + dy, x + dx]:
                    field[y + dy, x + dx] = min(field[y + dy, x + dx], bed + RAVINE_BANK_SLOPE * distance)


def ravine_issues(data: dict, geography: Geography) -> list[str]:
    """A river entering a canyon descends to the gorge floor without climbing on its way."""
    issues = []
    for confluence in canyon_confluences(data, geography.network):
        path = geography.network.routes[confluence.tributary]
        profile = [int(geography.heights[y, x]) for x, y in path[-RAVINE_PIXELS - 1:]]
        px, py = confluence.point
        floor = int(geography.heights[py, px])
        if profile[-1] > floor + RAVINE_FLOOR_TOLERANCE:
            issues.append(f"river {confluence.tributary}: ends {profile[-1]} high above a gorge floor of {floor}")
        if any(later > earlier + 1 for earlier, later in zip(profile, profile[1:])):
            issues.append(f"river {confluence.tributary}: climbs in its ravine {profile}")
    return issues


def load_sources(root: Path) -> dict[str, np.ndarray]:
    sources = {}
    for name, path in (("heightmap", HEIGHTMAP), ("rivers", RIVERS), ("terrain", TERRAIN), ("cities", CITIES), ("trees", TREES), ("world_normal", WORLD_NORMAL)):
        with Image.open(root / path) as image:
            sources[name] = np.array(image)
    return sources


def encode_like(original: bytes, pixels: np.ndarray, path: Path) -> bytes:
    """Encode a raster in the mode and palette of the original bitmap."""
    with Image.open(BytesIO(original)) as source:
        if np.array_equal(np.asarray(source), pixels):
            return original
        image = Image.frombytes(source.mode, source.size, np.ascontiguousarray(pixels).tobytes())
        if source.mode == "P":
            image.putpalette(source.getpalette())
    encoded = BytesIO()
    image.save(encoded, format="BMP")
    data = encoded.getvalue()
    return native_river_bmp(data) if path == RIVERS else data


def build_plan(root: Path = ROOT) -> MonPlan:
    """Compute every MON output in memory, with validation issues and a report."""
    data = read_json(root)
    scope = load_scope(root, data)
    definition = read_definition(root)
    register_planned_rows(definition, data)
    colours = definition.colours()
    with Image.open(root / PROVINCES) as source:
        original_rgb = np.asarray(source.convert("RGB"))
    rgb = stamp_geometry(root, original_rgb, data, colours, scope)
    grid = province_grid(rgb, colours)
    before = province_grid(original_rgb, colours)
    window = mon_window(grid, scope.provinces)
    sources = load_sources(root)
    geography = build_geography(root, data, scope, grid, definition, sources, window)
    issues = list(geography.network.issues)
    issues.extend(carve_issues(root, data, scope, grid, definition.kinds(), window))

    heights = sources["heightmap"].copy()
    heights[window.s] = geography.heights
    rivers = sources["rivers"].copy()
    rivers[window.s] = geography.network.pixels
    full_water = np.isin(grid, [province for province, kind in definition.kinds().items() if kind in ("sea", "lake")])
    settle_owned_reach_markers(data, rivers, grid, full_water)
    full_mon = np.zeros(grid.shape, bool)
    full_mon[window.s] = geography.mon
    issues.extend(marker_issues(data, rivers, grid, full_water, full_mon, geography.network.routes, window))
    terrain = sources["terrain"].copy()
    cities = sources["cities"].copy()
    paint_layers(geography, scope, terrain[window.s], cities[window.s])
    state_pixels = np.zeros(grid.shape, np.int64)
    state_pixels[window.s] = geography.states
    kinds = definition.kinds()
    water = np.isin(grid, [province for province, kind in kinds.items() if kind in ("sea", "lake")])
    trees_shape = sources["trees"].shape
    settled = geography.cities | geography.fringe
    for core in geography.cores.values():
        settled |= core
    blocked = tree_cells_blocked(water, trees_shape[1], trees_shape[0])
    blocked |= tree_cells_touching(settled, window, grid.shape, trees_shape)
    trees = render_trees(sources["trees"], terrain, state_pixels, palette_types(), blocked, window)
    relief_scope = np.zeros(grid.shape, bool)
    relief_scope[window.s] = geography.relief_scope
    normal = np.asarray(
        normal_from_height(
            Image.fromarray(heights), Image.fromarray(sources["world_normal"]), bytearray(relief_scope.tobytes())
        )
    )

    for province, terrain_type in geography.desired.items():
        definition.rows[province][6] = terrain_type
    unitstacks, rebuilt = reconcile_unitstacks(
        (root / UNITSTACKS).read_bytes(), grid, before, heights, kinds, scope, window
    )
    outputs = {
        PROVINCES: encode_like((root / PROVINCES).read_bytes(), rgb, PROVINCES),
        DEFINITION: definition.encode(),
        HEIGHTMAP: encode_like((root / HEIGHTMAP).read_bytes(), heights, HEIGHTMAP),
        WORLD_NORMAL: encode_like((root / WORLD_NORMAL).read_bytes(), normal, WORLD_NORMAL),
        TERRAIN: encode_like((root / TERRAIN).read_bytes(), terrain, TERRAIN),
        TREES: encode_like((root / TREES).read_bytes(), trees, TREES),
        RIVERS: encode_like((root / RIVERS).read_bytes(), rivers, RIVERS),
        CITIES: encode_like((root / CITIES).read_bytes(), cities, CITIES),
        UNITSTACKS: unitstacks,
    }
    term_issues, terrain_report = terrain_issues(geography.desired, scope, state_landforms(root, scope.states))
    issues.extend(term_issues)
    mon_heights = geography.heights[geography.mon]
    if mon_heights.min() < data["heights"]["min"] or mon_heights.max() > data["heights"]["max"]:
        issues.append(f"MON heights {mon_heights.min()}-{mon_heights.max()} leave the authored range")
    issues.extend(settlement_issues(data, scope, geography))
    issues.extend(ravine_issues(data, geography))
    issues.extend(state_area_issues(scope, before[window.s], geography.labels))
    report = {
        "terrain": terrain_report,
        "heights": {
            "min": int(mon_heights.min()),
            "max": int(mon_heights.max()),
            "median": float(np.median(mon_heights)),
        },
        "rivers": {
            name: {"length": len(path), "source": _global(path[0], window), "mouth": _global(path[-1], window)}
            for name, path in geography.network.routes.items()
        },
        "rebuilt_anchors": rebuilt,
        "canyons": {canyon.feature["name"]: canyon_profile(canyon, geography) for canyon in geography.canyons},
        **hydrology_report(data, geography),
    }
    return MonPlan(outputs, issues, report)


def hydrology_report(data: dict, geography: Geography) -> dict:
    """Widths of every authored course, every confluence and every ravine profile."""
    network = geography.network
    rivers = network.pixels
    window = geography.window
    rivers_by_name = {river["name"]: river for river in data["rivers"]}
    widths = {
        name: [int(rivers[y, x]) for x, y in path[body_start(rivers_by_name[name]):-1]]
        for name, path in network.routes.items()
    }
    confluences = {}
    for name, confluence in network.confluences.items():
        path = network.routes[name]
        fx, fy = confluence.flow_in
        px, py = confluence.point
        if confluence.receiver == "existing":
            receiver = network.existing & (rivers < RIVER_SEA_PALETTE)
            upstream = None
        else:
            course = network.routes[confluence.receiver]
            receiver = np.zeros(rivers.shape, bool)
            for x, y in course:
                receiver[y, x] = True
            index = course.index((px, py))
            upstream = int(rivers[course[index - 1][1], course[index - 1][0]])
        confluences[name] = {
            "receiver": confluence.receiver,
            "flow_in": _global(confluence.flow_in, window),
            "point": _global(confluence.point, window),
            "inflow": int(rivers[path[-2][1], path[-2][0]]),
            "receiver_width": int(rivers[py, px]),
            "upstream": upstream,
            "contacts": sum(bool(receiver[y, x]) for x, y in ((fx + 1, fy), (fx - 1, fy), (fx, fy + 1), (fx, fy - 1))),
            "mid_course": bool(mid_course(receiver)[py, px]),
            "square": path[-2] == (2 * fx - px, 2 * fy - py),
        }
    ravines = {}
    for confluence in canyon_confluences(data, network):
        path = network.routes[confluence.tributary]
        px, py = confluence.point
        ravines[confluence.tributary] = {
            "profile": [int(geography.heights[y, x]) for x, y in path[-RAVINE_PIXELS - 1:]],
            "floor": int(geography.heights[py, px]),
        }
    return {"widths": widths, "confluences": confluences, "ravines": ravines}


def state_area_issues(scope: Scope, before: np.ndarray, after: np.ndarray) -> list[str]:
    """Every state keeps exactly its pixels; carving only moves land between its own provinces."""
    issues = []
    for state_id in scope.states:
        members = [province for province, owner in scope.state_of.items() if owner == state_id]
        if (np.isin(before, members) != np.isin(after, members)).any():
            issues.append(f"state {state_id}: its pixels changed")
    return issues


def canyon_profile(canyon: Canyon, geography: Geography) -> dict:
    """Mean heights of the canyon floor, its MON rim and its far wall."""
    heights = geography.heights.astype(float)
    floor = (canyon.distance <= 1.0) & (geography.mon | canyon.band)
    rim = geography.mon & (np.abs(canyon.distance - canyon.feature["half_width"] - 1.5) <= 1.0)
    wall = canyon.band & (canyon.distance >= canyon.feature["band"] - 1.0)
    gorge = geography.network.pixels[canyon.course & (geography.network.pixels < RIVER_SEA_PALETTE)]
    return {
        "floor": round(float(heights[floor].mean()), 1),
        "mon_rim": round(float(heights[rim].mean()), 1),
        "far_wall": round(float(heights[wall].mean()), 1),
        "band_pixels": int(canyon.band.sum()),
        "river_palettes": {str(key): value for key, value in sorted(Counter(gorge.tolist()).items())},
    }


def _global(point: tuple[int, int], window: Window) -> list[int]:
    return [point[0] + window.x0, point[1] + window.y0]


def paint_layers(geography: Geography, scope: Scope, terrain: np.ndarray, cities: np.ndarray) -> None:
    """Paint the MON terrain palettes and city masks of the window, in place.

    Every rural province takes the one palette of its declared terrain. City
    provinces, the urban fringe and village cores carry palette 13 and the
    western houses, except on the shoreline band, where city meshes would
    float over the water.
    """
    labels = geography.labels
    mon = geography.mon
    palette_of = np.zeros(int(labels.max()) + 1, np.uint8)
    for province, terrain_type in geography.desired.items():
        palette_of[province] = URBAN_PALETTE if terrain_type == "urban" else UNIFORM_TERRAIN_PALETTES[terrain_type]
    terrain[mon] = palette_of[labels[mon]]
    built = (geography.cities | geography.fringe)
    for core in geography.cores.values():
        built |= core
    terrain[built & ~geography.shore] = URBAN_PALETTE
    terrain[built & geography.shore] = URBAN_FALLBACK_PALETTE
    cities[mon] = CITY_BACKGROUND_INDEX
    cities[built & ~geography.shore] = CITY_HOUSES_INDEX


def settlement_issues(data: dict, scope: Scope, geography: Geography) -> list[str]:
    issues = []
    for entry in data["settlements"]:
        if entry["kind"] == "village":
            province = entry.get("province")
            if province is None:
                issues.append(f"village {entry['name']}: no planned province")
            elif scope.state_of.get(province) != entry["state"]:
                issues.append(f"village {entry['name']}: province {province} lies outside state {entry['state']}")
            elif geography.desired[province] == "urban":
                issues.append(f"village {entry['name']}: province {province} is urban")
    return issues


def carve_issues(root: Path, data: dict, scope: Scope, grid: np.ndarray, kinds: dict[int, str], window: Window) -> list[str]:
    """Check the carved geometry: sizes, neighbours, rail contacts and state areas."""
    if not scope.planned:
        return ["no planned MON province geometry: run --plan-provinces"]
    issues = []
    labels = window_labels(grid, window)
    adjacency = province_adjacency(labels)
    pairs = rail_pairs(root)
    for parent in sorted(scope.cities):
        size = int((labels == parent).sum())
        if not 40 <= size <= 50:
            issues.append(f"city {parent}: {size} pixels")
        land = {province for province in adjacency.get(parent, ()) if kinds.get(province) == "land"}
        if len(land) < CITY_MIN_NEIGHBOURS:
            issues.append(f"city {parent}: only {len(land)} land neighbours")
    for province, entry in scope.planned.items():
        size = int((labels == province).sum())
        if entry["kind"] == "remainder" and size < REMAINDER_MIN_PIXELS:
            issues.append(f"remainder {province}: {size} pixels")
        if entry["kind"] == "district" and int(entry["parent"]) not in adjacency.get(province, ()):
            issues.append(f"district {province}: does not touch its city")
        if label(labels == province)[1] != 1:
            issues.append(f"planned province {province}: not one connected piece")
    for a, b in sorted(pairs):
        if (a in scope.provinces or b in scope.provinces) and b not in adjacency.get(a, set()):
            detour = [
                remainder
                for parent, remainder in scope.remainders.items()
                if parent in (a, b) and {a, b} - {parent} <= adjacency.get(remainder, set())
            ]
            via = f": pass it through remainder {detour[0]}" if detour else ""
            issues.append(f"railway segment {a}-{b} joins provinces that do not touch{via}")
    return issues


# --- province planning ---


def _evaluate_site(
    labels: np.ndarray,
    region: np.ndarray,
    site: np.ndarray,
    owner: int,
    pairs: set[tuple[int, int]],
    kinds: dict[int, str],
    site_label: int,
) -> tuple[list[str], list[int], int]:
    """Return hard failures, lost rail contacts and land neighbours of a carved site.

    ``owner`` is the province whose ``region`` the site is carved from; its
    leftover must stay one piece of at least REMAINDER_MIN_PIXELS. The site
    takes ``site_label``; when that is the owner itself, the site inherits
    the owner's rail contacts. Only a window around the region is examined.
    """
    ys, xs = np.nonzero(region)
    crop = np.s_[
        max(0, ys.min() - SITE_MARGIN):ys.max() + SITE_MARGIN + 1,
        max(0, xs.min() - SITE_MARGIN):xs.max() + SITE_MARGIN + 1,
    ]
    before = labels[crop]
    after = before.copy()
    leftover = region[crop] & ~site[crop]
    after[leftover] = LEFTOVER_MARKER
    after[site[crop]] = site_label
    failures = []
    if leftover.sum() < REMAINDER_MIN_PIXELS:
        failures.append(f"remainder below {REMAINDER_MIN_PIXELS} pixels")
    if leftover.any() and label(leftover)[1] != 1:
        failures.append("remainder split")
    donors = set(np.unique(before[site[crop]]).tolist()) - {owner}
    for donor in sorted(donors):
        rest = after == donor
        if not rest.any() or label(rest)[1] != 1:
            failures.append(f"donor {donor} split")
    adjacency = province_adjacency(after)
    land = {province for province in adjacency.get(site_label, ()) if kinds.get(province, "land") == "land"}
    lost = []
    for a, b in sorted(pairs):
        if site_label == owner and owner in (a, b):
            other = b if a == owner else a
            if other not in adjacency.get(owner, set()):
                lost.append(other)
        elif (a in donors or b in donors) and b not in adjacency.get(a, set()):
            lost.append(a if b in donors else b)
    return failures, lost, len(land)


def grow_city(labels: np.ndarray, allowed: np.ndarray, region: np.ndarray, anchor: tuple[int, int], size: int) -> np.ndarray:
    """Grow a compact site from ``anchor``; no donor outside ``region`` gives more than its share.

    The same rule as ``carve_junction_city``, from a chosen anchor.
    """
    allowed = allowed.copy()
    city = _grow_compact_region(allowed, anchor, size)
    for _attempt in range(8):
        shrunk = [
            int(value)
            for value in np.unique(labels[city])
            if (labels[city] == value).sum() > (1.0 - CITY_DONOR_SHARE) * (labels == value).sum()
        ]
        if not shrunk:
            return city
        allowed &= ~np.isin(labels, shrunk) | region
        city = _grow_compact_region(allowed, anchor, size)
    return city


def carve_site(
    labels: np.ndarray,
    donors: np.ndarray,
    region: np.ndarray,
    hint: tuple[float, float],
    parent: int,
    pairs: set[tuple[int, int]],
    kinds: dict[int, str],
    shore: np.ndarray | None,
) -> tuple[np.ndarray, list[int], int]:
    """Carve a compact city inside its parent; keep rail contacts when a site allows it.

    The junction site of ``carve_junction_city`` comes first. When it breaks a
    rule or a rail contact, the sites near the hint are tried, then the rest
    of the parent while a rail contact is still lost; the fewest losses win.
    """
    city = carve_junction_city(labels, donors, region, hint, shore=shore)
    failures, lost, land = _evaluate_site(labels, region, city, parent, pairs, kinds, parent)
    if city.sum() == CITY_PIXELS and not failures and not lost and land >= CITY_MIN_NEIGHBOURS:
        return city, lost, land
    ys, xs = np.nonzero(region & donors)
    distance = np.hypot(ys - hint[0], xs - hint[1])
    order = np.lexsort((xs, ys, distance))
    best = None
    for index in order:
        if distance[index] > CITY_SITE_DISTANCE and best is not None and not best[4] and not best[2]:
            break
        city = grow_city(labels, donors, region, (int(ys[index]), int(xs[index])), CITY_PIXELS)
        if city.sum() != CITY_PIXELS:
            continue
        failures, lost, land = _evaluate_site(labels, region, city, parent, pairs, kinds, parent)
        if land < CITY_MIN_NEIGHBOURS:
            failures = [*failures, f"only {land} land neighbours"]
        score = (len(failures), len(lost), -min(land, CITY_MIN_NEIGHBOURS + 1), float(distance[index]))
        if best is None or score < best[0]:
            best = (score, city, lost, land, failures)
        if not failures and not lost and land > CITY_MIN_NEIGHBOURS:
            break
    if best is None or best[4]:
        raise RuntimeError(f"city {parent}: no site satisfies the carving rules {best[4] if best else ''}")
    return best[1], best[2], best[3]


def plan_provinces(root: Path = ROOT) -> dict:
    """Carve the MON cities, the capital district and the remainders; pick the villages.

    The result is stored as data, so the map pass only stamps it. A stored
    plan is never replanned from a map that already carries it.
    """
    data = read_json(root)
    planned = data["planned"]
    if planned["provinces"] or planned["first_id"] or planned["cities"] or planned["villages"]:
        raise RuntimeError("the MON province plan exists: restore the pre-apply map and empty planned first")
    scope = load_scope(root, data)
    definition = read_definition(root)
    colours = definition.colours()
    kinds = definition.kinds()
    used = set(colours.values())
    first_id = max(definition.rows) + 1
    with Image.open(root / PROVINCES) as source:
        grid = province_grid(np.asarray(source.convert("RGB")), colours)
    window = mon_window(grid, scope.provinces)
    with Image.open(root / HEIGHTMAP) as source:
        ground = prepare_ground(root, data, scope, grid, kinds, np.asarray(source)[window.s], window)
    labels = ground.labels.copy()
    original = ground.labels
    with Image.open(root / RIVERS) as source:
        river = river_masks(np.asarray(source)[window.s], ground.water)
    # Both banks of a river keep their provinces, so it keeps running on a border.
    locked = river | neighbours_of(river) | ground.water | ground.canyon_clearance
    shore = neighbours_of(ground.water) & ~ground.water
    pairs = rail_pairs(root)
    entries: list[dict] = []
    report: dict = {"first_id": first_id, "cities": {}, "district": None}
    for settlement in data["settlements"]:
        if settlement["kind"] == "village":
            continue
        parent = int(settlement["parent"])
        state_id = int(settlement["state"])
        if scope.state_of.get(parent) != state_id:
            raise RuntimeError(f"settlement parent {parent} lies outside state {state_id}")
        settled = [int(entry["parent"]) for entry in entries] + [
            int(entry["province"]) for entry in entries if entry["kind"] == "district"
        ]
        state_ids = [province for province, owner in scope.state_of.items() if owner == state_id]
        state_ids += [int(entry["province"]) for entry in entries if entry["state"] == state_id]
        donors = np.isin(labels, state_ids) & ~np.isin(labels, settled) & ~locked
        hint = (settlement["hint"][1] - window.y0, settlement["hint"][0] - window.x0)
        if settlement["kind"] == "city":
            region = labels == parent
            port = shore if (region & shore).any() else None
            city, lost, land = carve_site(labels, donors, region, hint, parent, pairs, kinds, port)
            remainder = first_id + len(entries)
            labels[region & ~city] = remainder
            labels[city] = parent
            entries.append(_planned_entry(remainder, parent, state_id, "remainder", used))
            report["cities"][parent] = {
                "pixels": int(city.sum()),
                "land_neighbours": land,
                "rail_neighbours": sorted(rail_neighbours(pairs, parent)),
                "lost_rail": lost,
                "remainder": remainder,
                "remainder_pixels": int((labels == remainder).sum()),
            }
        else:
            remainder = next(
                int(entry["province"]) for entry in entries if entry["parent"] == parent and entry["kind"] == "remainder"
            )
            district_id = first_id + len(entries)
            district = grow_district(labels, donors & (labels != parent), labels == remainder, hint, parent, pairs, kinds)
            labels[district] = district_id
            entries.append(_planned_entry(district_id, parent, state_id, "district", used))
            report["district"] = {"province": district_id, "pixels": int(district.sum())}
            report["cities"][parent]["remainder_pixels"] = int((labels == remainder).sum())
    new_ids = [int(entry["province"]) for entry in entries]
    changed_ids = set(new_ids) | set(np.unique(original[labels != original]).tolist())
    remove_four_province_corners(labels, np.isin(labels, list(changed_ids)) & ~locked)
    for state_id in data["states"]:
        provinces = [province for province, owner in scope.state_of.items() if owner == state_id]
        members = provinces + [int(entry["province"]) for entry in entries if entry["state"] == state_id]
        if (np.isin(original, provinces) != np.isin(labels, members)).any():
            raise RuntimeError(f"state {state_id}: its pixel area changed")
    planned["origin"], image = geometry_image(labels, original, colours, entries, window)
    planned["first_id"] = first_id
    planned["provinces"] = entries
    planned["cities"] = {str(parent): parent for parent in sorted(report["cities"])}
    scope = load_scope(root, data)
    stamped = grid.copy()
    stamped[window.s] = labels
    pick_villages(root, data, scope, stamped, definition, window, pairs, original)
    report["villages"] = data["planned"]["villages"]
    Image.fromarray(image, "RGBA").save(root / GEOMETRY_PATH, optimize=True)
    (root / DATA_PATH).write_text(dump_data(data), encoding="utf-8", newline="\n")
    return report


def geometry_image(
    labels: np.ndarray, original: np.ndarray, colours: dict, entries: list[dict], window: Window
) -> tuple[list[int], np.ndarray]:
    """RGBA crop of every changed pixel in its new province colour."""
    changed = labels != original
    palette = dict(colours)
    palette.update({int(entry["province"]): tuple(entry["rgb"]) for entry in entries})
    ys, xs = np.nonzero(changed)
    top, bottom, left, right = int(ys.min()), int(ys.max()) + 1, int(xs.min()), int(xs.max()) + 1
    image = np.zeros((bottom - top, right - left, 4), np.uint8)
    crop = labels[top:bottom, left:right]
    crop_changed = changed[top:bottom, left:right]
    for value in np.unique(crop[crop_changed]).tolist():
        mask = crop_changed & (crop == value)
        image[mask, :3] = palette[value]
        image[mask, 3] = 255
    return [left + window.x0, top + window.y0], image


def _planned_entry(province: int, parent: int, state_id: int, kind: str, used: set) -> dict:
    return {
        "province": province,
        "rgb": list(province_colour(province, used)),
        "state": state_id,
        "parent": parent,
        "kind": kind,
    }


def grow_district(
    labels: np.ndarray,
    donors: np.ndarray,
    region: np.ndarray,
    hint: tuple[float, float],
    parent: int,
    pairs: set[tuple[int, int]],
    kinds: dict[int, str],
) -> np.ndarray:
    """Carve the urban district of the capital beside its city.

    The remainder of the capital and its neighbours in the state give at
    most their donor share each, so every one keeps its size.
    """
    remainder = int(np.unique(labels[region])[0])
    allowed = donors
    near_city = distance_transform_edt(labels != parent) <= DISTRICT_ANCHOR_DISTANCE
    ys, xs = np.nonzero(allowed & near_city)
    order = np.lexsort((xs, ys, np.hypot(ys - hint[0], xs - hint[1])))
    nothing = np.zeros(region.shape, bool)
    for index in order:
        district = grow_city(labels, allowed, nothing, (int(ys[index]), int(xs[index])), DISTRICT_PIXELS)
        if district.sum() != DISTRICT_PIXELS:
            continue
        failures, lost, _land = _evaluate_site(labels, region, district, remainder, pairs, kinds, DISTRICT_MARKER)
        if failures or lost:
            continue
        after = labels.copy()
        after[district] = DISTRICT_MARKER
        if parent in province_adjacency(after).get(DISTRICT_MARKER, set()):
            return district
    raise RuntimeError("capital district: no site beside the city keeps the remainder whole")


def pick_villages(
    root: Path,
    data: dict,
    scope: Scope,
    grid: np.ndarray,
    definition: Definition,
    window: Window,
    pairs: set[tuple[int, int]],
    original: np.ndarray,
) -> None:
    """Choose the province of every village and record it in the data.

    A village stands in its state, at least ten pixels from the city, never on
    a donor, parent or remainder and clear of a canyon; a river bank or a
    railway is preferred, and a descriptive name picks the matching landform.
    """
    sources = load_sources(root)
    ground = prepare_ground(root, data, scope, grid, definition.kinds(), sources["heightmap"][window.s], window)
    labels = ground.labels
    touched = set(np.unique(original[labels != original]).tolist())
    network = ground_rivers(data, window, ground, sources["rivers"][window.s])
    river = network.pixels < RIVER_SEA_PALETTE
    banks = set(np.unique(labels[neighbours_of(river) & ground.mon]).tolist())
    on_rail = {province for pair in pairs for province in pair}
    city_distance = distance_transform_edt(~ground.cities)
    boxes = find_objects(grid)
    chosen: dict[int, list[int]] = defaultdict(list)
    centres: dict[int, tuple[int, int]] = {}
    for entry in data["settlements"]:
        if entry["kind"] != "village":
            continue
        state_id = int(entry["state"])
        options = []
        for province in sorted(province for province, owner in scope.state_of.items() if owner == state_id):
            if province in scope.planned or province in scope.cities or province in touched:
                continue
            _oy, _ox, _inside, _depth, (cx, cy) = province_interior(grid, province, boxes[province - 1])
            lx, ly = cx - window.x0, cy - window.y0
            if city_distance[ly, lx] < VILLAGE_CITY_DISTANCE or ground.canyon_clearance[ly, lx]:
                continue
            if any(np.hypot(lx - centres[other][0], ly - centres[other][1]) < VILLAGE_SPACING for other in chosen[state_id]):
                continue
            centres[province] = (lx, ly)
            height = float(ground.field[labels == province].mean())
            options.append((province, province in banks, province in on_rail, height, float(city_distance[ly, lx])))
        if not options:
            raise RuntimeError(f"village {entry['name']}: no province fits in state {state_id}")
        options.sort(key=lambda option: village_preference(entry["name"], option))
        entry["province"] = options[0][0]
        chosen[state_id].append(options[0][0])
    data["planned"]["villages"] = {str(state_id): provinces for state_id, provinces in sorted(chosen.items())}


def village_preference(name: str, option: tuple) -> tuple:
    province, bank, rail, height, distance = option
    if any(word in name for word in PASS_VILLAGE_WORDS):
        return (-height, province)
    if any(word in name for word in MARSH_VILLAGE_WORDS):
        return (not bank, height, province)
    if any(word in name for word in RIVER_VILLAGE_WORDS):
        return (not bank, not rail, abs(distance - 20.0), province)
    return (not (bank or rail), abs(distance - 20.0), province)


# --- previews ---


HEIGHT_RAMP = ((97, (70, 120, 70)), (115, (150, 180, 100)), (135, (200, 180, 120)), (160, (150, 110, 80)), (190, (245, 245, 245)))


def hillshade(heights: np.ndarray) -> np.ndarray:
    """Height-tinted relief lit from the north-west."""
    values = heights.astype(float)
    gy, gx = np.gradient(gaussian_filter(values, 0.7))
    shade = np.clip(0.8 - 0.09 * (gx + gy), 0.35, 1.25)
    levels = [level for level, _colour in HEIGHT_RAMP]
    tint = np.stack(
        [np.interp(values, levels, [colour[channel] for _level, colour in HEIGHT_RAMP]) for channel in range(3)], axis=-1
    )
    return np.clip(tint * shade[..., None], 0, 255).astype(np.uint8)


TERRAIN_COLOURS = {
    "plains": (196, 214, 140),
    "forest": (64, 128, 64),
    "marsh": (110, 150, 150),
    "hills": (190, 160, 100),
    "mountain": (130, 110, 100),
    "urban": (200, 40, 40),
}


def _borders(labels: np.ndarray) -> np.ndarray:
    return province_borders(labels.astype(np.uint32))


def _upscale(image: np.ndarray, scale: int) -> Image.Image:
    return Image.fromarray(image).resize((image.shape[1] * scale, image.shape[0] * scale), Image.NEAREST)


def preview_images(root: Path = ROOT) -> dict[Path, Image.Image]:
    data = read_json(root)
    scope = load_scope(root, data)
    definition = read_definition(root)
    register_planned_rows(definition, data)
    colours = definition.colours()
    with Image.open(root / PROVINCES) as source:
        original_rgb = np.asarray(source.convert("RGB"))
    rgb = stamp_geometry(root, original_rgb, data, colours, scope)
    grid = province_grid(rgb, colours)
    before = window_labels(province_grid(original_rgb, colours), mon_window(grid, scope.provinces))
    window = mon_window(grid, scope.provinces)
    geography = build_geography(root, data, scope, grid, definition, load_sources(root), window)
    scale = 3
    labels = geography.labels
    borders = _borders(labels) & (geography.mon | neighbours_of(geography.mon))
    state_borders = _borders(geography.states)
    water = geography.water
    river = geography.network.pixels < RIVER_SEA_PALETTE

    relief = hillshade(geography.heights)
    relief[borders] = (relief[borders] * 0.8).astype(np.uint8)
    relief[state_borders & geography.mon] = (30, 30, 30)
    relief[water] = (80, 120, 200)
    relief[river] = (20, 60, 230)
    relief[geography.cities] = (220, 40, 40)
    for core in geography.cores.values():
        relief[core] = (250, 150, 20)
    relief[geography.fringe] = (240, 110, 110)

    terrain = np.full(labels.shape + (3,), 235, np.uint8)
    for province, terrain_type in geography.desired.items():
        terrain[labels == province] = TERRAIN_COLOURS[terrain_type]
    terrain[borders] = (terrain[borders] * 0.75).astype(np.uint8)
    terrain[state_borders & geography.mon] = (20, 20, 20)
    terrain[water] = (80, 120, 200)
    terrain[river] = (20, 60, 230)
    for core in geography.cores.values():
        terrain[core] = (250, 150, 20)

    images = {}
    for name, array in (("plan_relief_rivers.png", relief), ("plan_terrain.png", terrain)):
        image = _upscale(array, scale)
        draw = ImageDraw.Draw(image)
        _label_settlements(draw, data, scope, grid, window, scale)
        images[PREVIEW_DIR / name] = image
    images[PREVIEW_DIR / "plan_cities.png"] = city_sheet(data, scope, labels, before, geography)
    for canyon in geography.canyons:
        name = re.sub(r"[^a-z]+", "_", canyon.feature["name"].lower()).strip("_")
        images[PREVIEW_DIR / f"plan_{name}.png"] = canyon_sheet(canyon, geography, load_sources(root)["heightmap"][window.s])
    return images


def canyon_sheet(canyon: Canyon, geography: Geography, before: np.ndarray) -> Image.Image:
    """Zoomed relief of a canyon and height cross-sections across it, before and after."""
    scale = 5
    ys, xs = np.nonzero(canyon.band)
    crop = np.s_[ys.min() - 12:ys.max() + 13, xs.min() - 6:xs.max() + 7]
    relief = hillshade(geography.heights[crop])
    relief[_borders(geography.labels[crop]) & geography.mon[crop]] //= 2
    relief[_borders(geography.states[crop].astype(np.int64) + canyon.foreign[crop])] = (30, 30, 30)
    relief[geography.network.pixels[crop] < RIVER_SEA_PALETTE] = (20, 60, 230)
    top = _upscale(relief, scale)
    draw = ImageDraw.Draw(top)
    columns = np.linspace(xs.min() + 10, xs.max() - 10, 4).astype(int)
    for column in columns:
        x = (column - crop[1].start) * scale + scale // 2
        draw.line((x, 0, x, top.height), fill=(255, 255, 255), width=1)
    plot_height = 220
    sheet = Image.new("RGB", (top.width, top.height + plot_height * len(columns)), (255, 255, 255))
    sheet.paste(top, (0, 0))
    draw = ImageDraw.Draw(sheet)
    rows = np.arange(crop[0].start, crop[0].stop)
    step = sheet.width / len(rows)

    def point(row: int, value: float, y0: int) -> tuple[float, float]:
        return ((row - rows[0] + 0.5) * step, y0 + plot_height - 10 - (value - 90) * 2)

    for index, column in enumerate(columns):
        y0 = top.height + index * plot_height
        draw.text((6, y0 + 4), f"x {column + geography.window.x0}, north to south: before grey, after black, river blue", fill=(0, 0, 0))
        for heights, colour in ((before, (170, 170, 170)), (geography.heights, (0, 0, 0))):
            profile = heights[crop[0], column].astype(float)
            draw.line([point(row, value, y0) for row, value in zip(rows, profile)], fill=colour, width=2)
        for row in rows:
            if geography.network.pixels[row, column] < RIVER_SEA_PALETTE:
                x, y = point(row, float(geography.heights[row, column]), y0)
                draw.ellipse((x - 4, y - 4, x + 4, y + 4), outline=(20, 60, 230), width=2)
    return sheet


def _label_settlements(draw: ImageDraw.ImageDraw, data: dict, scope: Scope, grid: np.ndarray, window: Window, scale: int) -> None:
    boxes = find_objects(grid)
    for entry in data["settlements"]:
        province = entry.get("parent") if entry["kind"] == "city" else entry.get("province")
        if province is None or entry["kind"] == "district":
            continue
        _oy, _ox, _inside, _depth, (cx, cy) = province_interior(grid, province, boxes[province - 1])
        x = (cx - window.x0) * scale
        y = (cy - window.y0) * scale
        text = f"{province} VP{entry['value']}"
        draw.text((x + 4, y - 6), text, fill=(0, 0, 0) if entry["kind"] == "city" else (90, 40, 0))


def city_sheet(data: dict, scope: Scope, labels: np.ndarray, before: np.ndarray, geography: Geography) -> Image.Image:
    """Old and new province borders around each city, side by side."""
    radius = 16
    scale = 6
    tiles = []
    for parent in sorted(scope.cities):
        ys, xs = np.nonzero(labels == parent)
        cy, cx = int(ys.mean()), int(xs.mean())
        crop = np.s_[cy - radius:cy + radius + 1, cx - radius:cx + radius + 1]
        pair = []
        for grid in (before, labels):
            tile = np.full((2 * radius + 1, 2 * radius + 1, 3), 225, np.uint8)
            local = grid[crop]
            tile[local == parent] = (240, 200, 120)
            if grid is labels:
                tile[local == parent] = (220, 60, 60)
                tile[np.isin(local, list(scope.planned))] = (240, 200, 120)
                tile[np.isin(local, list(scope.districts))] = (200, 120, 200)
            tile[geography.water[crop]] = (80, 120, 200)
            tile[_borders(local)] = (40, 40, 40)
            tile[(geography.network.pixels[crop] < RIVER_SEA_PALETTE)] = (20, 60, 230)
            pair.append(tile)
        combined = np.concatenate((pair[0], np.full((pair[0].shape[0], 2, 3), 255, np.uint8), pair[1]), axis=1)
        image = _upscale(combined, scale)
        ImageDraw.Draw(image).text((4, 4), f"{parent}", fill=(0, 0, 0))
        tiles.append(image)
    columns = 4
    width = tiles[0].width + 8
    height = tiles[0].height + 8
    sheet = Image.new("RGB", (columns * width, ((len(tiles) + columns - 1) // columns) * height), (255, 255, 255))
    for index, tile in enumerate(tiles):
        sheet.paste(tile, ((index % columns) * width, (index // columns) * height))
    return sheet


def write_previews(root: Path = ROOT) -> list[Path]:
    paths = []
    for path, image in preview_images(root).items():
        (root / path).parent.mkdir(parents=True, exist_ok=True)
        image.save(root / path, optimize=True)
        paths.append(path)
    return paths


# --- check and apply ---


def stale_outputs(plan: MonPlan, root: Path) -> list[Path]:
    return [path for path, data in plan.outputs.items() if (root / path).read_bytes() != data]


def atomic_write(path: Path, data: bytes) -> None:
    temporary = path.with_name(path.name + ".tmp")
    try:
        with temporary.open("wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def apply(root: Path = ROOT) -> MonPlan:
    plan = build_plan(root)
    for path in stale_outputs(plan, root):
        atomic_write(root / path, plan.outputs[path])
    return plan


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true", help="list differences against the expected outputs (default)")
    mode.add_argument("--apply", action="store_true", help="write the MON map outputs")
    mode.add_argument("--plan-provinces", action="store_true", help="carve cities and pick villages into the data file")
    mode.add_argument("--preview", action="store_true", help="write review images")
    args = parser.parse_args()
    if args.plan_provinces:
        report = plan_provinces(ROOT)
        print(json.dumps(report, ensure_ascii=False, indent=1))
        return 0
    if args.preview:
        for path in write_previews(ROOT):
            print(f"WROTE {path.as_posix()}")
        return 0
    plan = apply(ROOT) if args.apply else build_plan(ROOT)
    if args.apply:
        repeated = build_plan(ROOT)
        if stale_outputs(repeated, ROOT):
            raise RuntimeError("MON geography is not idempotent")
    stale = stale_outputs(plan, ROOT) if not args.apply else []
    for path in stale:
        print(f"STALE {path.as_posix()}")
    for issue in plan.issues:
        print(f"ERROR: {issue}")
    if stale or plan.issues:
        return 1
    print(f"MON geography is current: {len(plan.report['rivers'])} rivers, terrain {plan.report['terrain']['totals']}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
