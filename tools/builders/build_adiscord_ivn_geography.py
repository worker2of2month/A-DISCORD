"""Generate Ivanland/IIA relief, terrain, trees and rivers; sync declared terrain.

The province manifest holds two plans. Stage 1 is the reviewed geometry;
``stage2`` adds smaller rural provinces, a city in every state and a town in
each, stacked below ``stage2.sheet_row`` in the geometry raster.
``--plan-stage2-provinces`` writes that plan under ``--output-root`` and
``--dry-run-stage2`` applies it to copies of the map outside the repository.
``--smooth-stage2-state-borders`` smooths the lines between the states in the
stored plan and writes it only under an explicit ``--output-root``.
"""

from __future__ import annotations

import argparse
import heapq
import json
import os
import re
import shutil
from array import array
from bisect import bisect_right
from collections import Counter, defaultdict, deque
from dataclasses import dataclass
from io import BytesIO
from itertools import zip_longest
from math import ceil, cos, pi, sin
from pathlib import Path
from typing import Mapping, Sequence

import numpy as np
from PIL import Image, ImageDraw
from scipy.ndimage import binary_dilation, distance_transform_edt, find_objects, gaussian_filter, label

from tools.builders.build_adiscord_terrain_snow import (
    CITIES_PATH,
    CITY_PALETTE_INDEX,
    CITY_PALETTE_INDICES,
)
from tools.lib.coastal_clearance import (
    URBAN_FALLBACK_PALETTE,
    tree_cells_blocked,
    urban_blocked,
    water_colours,
    water_mask,
)


ROOT = Path(__file__).resolve().parents[2]
# The root every map, state and manifest path below points at; the Stage 2
# dry run moves it to copies outside the repository.
REPOSITORY_ROOT = ROOT
MAP_ROOT = ROOT
TERRAIN_PATH = ROOT / "map/terrain.bmp"
TREES_PATH = ROOT / "map/trees.bmp"
PROVINCES_PATH = ROOT / "map/provinces.bmp"
DEFINITION_PATH = ROOT / "map/definition.csv"
HEIGHTMAP_PATH = ROOT / "map/heightmap.bmp"
WORLD_NORMAL_PATH = ROOT / "map/world_normal.bmp"
TERRAIN_CONFIG_PATH = ROOT / "common/terrain/00_terrain.txt"
STATE_DIR = ROOT / "history/states"

IVN_STATE_IDS = frozenset(
    {
        25,
        92,
        95,
        96,
        97,
        98,
        99,
        100,
        101,
        127,
        129,
        130,
        131,
        132,
        164,
        695,
        696,
        697,
        698,
        713,
        714,
        715,
        716,
        717,
    }
)
# State 739 is the half of 693 split off by the new-states builder.
IIA_STATE_IDS = frozenset({128, 693, 694, 739})
SCOPED_STATE_IDS = IVN_STATE_IDS | IIA_STATE_IDS
ISLAND_HEIGHT_STATE_IDS = IIA_STATE_IDS
NORTHERN_LANDSCAPE_STATE_IDS = frozenset({127, 129, 130, 131, 132, 164, 715}) | IIA_STATE_IDS
PROVINCE_MANIFEST_PATH = ROOT / "tools/data/adiscord_ivn_provinces.json"
PROVINCE_MANIFEST = json.loads(PROVINCE_MANIFEST_PATH.read_text(encoding="utf-8"))
# Island-administration towns that receive a compact city province. The other
# island victory points stay rural markers.
ISLAND_CITY_SETTLEMENTS = frozenset({579, 6905, 11841})
# Declared terrain of the original island provinces. Rural parents of carved
# cities and former town provinces take the biome of their surroundings.
ISLAND_PARENT_TERRAIN = {
    11841: "urban",
    **dict.fromkeys((1191, 6905, 6928, 7678, 16679, 16680, 16688, 16700), "hills"),
    **dict.fromkeys(
        (2991, 4334, 5448, 7125, 8423, 12189, 16661, 16662, 16685, 16695), "forest"
    ),
    **dict.fromkeys(
        (
            579,
            1744,
            2219,
            2553,
            8048,
            9072,
            10730,
            16659,
            16660,
            16663,
            16664,
            16681,
            16683,
            16686,
            16692,
        ),
        "plains",
    ),
}
# Mainland relief of the Itoran civil-war theatre. Heights are a pure function
# of position, coast and the unchanged foreign border, so repeated passes
# converge. The detached western islands keep their authored relief.
RELIEF_STATE_IDS = IVN_STATE_IDS
MARCH_RELIEF_STATE_IDS = IVN_STATE_IDS - NORTHERN_LANDSCAPE_STATE_IDS
_RELIEF_EXCLUDED_PARENTS = frozenset({8885, 9037, 10675, 11000})
# The March Ridge separates the northern lobe from the marches; its spur and
# the Longar heights continue along the eastern march.
RIDGE_SPINE = (
    (2833, 1009),
    (2846, 1004),
    (2860, 1002),
    (2874, 999),
    (2887, 999),
    (2899, 1006),
    (2908, 1014),
)
RIDGE_SPUR = ((2896, 1004), (2890, 1022), (2886, 1036), (2884, 1050), (2880, 1058))
# (x, y, x radius, y radius, amplitude): Longar heights, the Olsia upland and
# its summit, and the Lakora hills.
RELIEF_DOMES = (
    (2919, 1050, 10.0, 9.0, 34.0),
    (2826, 1230, 30.0, 16.0, 50.0),
    (2830, 1232, 13.0, 10.0, 74.0),
    (2872, 1203, 8.0, 7.0, 32.0),
)
# The Rinval fens lie between the western march and the Old March capital.
FEN_LINE = ((2786, 1099), (2800, 1095), (2815, 1093), (2830, 1093), (2843, 1097))
FEN_HALF_WIDTH = 5.0
# The Old March forest screens the capital from the eastern marches.
FOREST_ZONES = ((2850, 1112, 17.0, 12.0),)
RIVERS_PATH = ROOT / "map/rivers.bmp"
UNITSTACKS_PATH = ROOT / "map/unitstacks.txt"
# Reviewed province geometry of the IVN mainland and the island administration:
# an RGBA crop whose opaque pixels are stamped into provinces.bmp.
# PROVINCE_MANIFEST lists new provinces.
PROVINCE_GEOMETRY_PATH = ROOT / "tools/data/adiscord_ivn_province_geometry.png"
# A victory-point province up to this size becomes the city itself; a larger
# one yields a compact city of CITY_PIXELS at a nearby province junction.
CITY_WHOLE_PROVINCE_PIXELS = 115
CITY_PIXELS = 45
# A city stands where at least this many provinces meet, within
# CITY_SITE_DISTANCE pixels of its historical urban area.
CITY_MIN_NEIGHBOURS = 3
CITY_JUNCTION_RADIUS = 4
CITY_SITE_DISTANCE = 14
# No donor province gives a city more than this share of its pixels.
CITY_DONOR_SHARE = 0.35
SPLIT_PART_PIXELS = 150
SPLIT_MIN_PART_PIXELS = 100
SPLIT_PIXELS = 300
LOCKED_PROVINCE_PIXELS = 60
# Provinces that already carried authored rivers. Their river pixels, and
# every pixel touching them, stay outside this builder's river layer.
_AUTHORED_RIVER_PARENTS = frozenset(
    {
        1304, 1421, 1697, 2058, 2752, 3131, 3447, 3462, 3598, 3847, 4103, 4217,
        4553, 4576, 5573, 5586, 6020, 6507, 7603, 7713, 7911, 8536, 9100, 9183,
        9685, 9894, 11115, 11132, 11382, 11480, 11613, 12160, 12317, 12342, 12463,
    }
)


def stage2_plan(manifest: dict) -> dict:
    """The Stage 2 section of the province manifest; empty before it is planned."""
    return manifest.get("stage2", {})


def has_stage2_plan(manifest: dict) -> bool:
    return bool(stage2_plan(manifest).get("provinces"))


def stage2_parents(manifest: dict) -> dict[int, int]:
    return {
        int(entry["province"]): int(entry["parent"])
        for entry in stage2_plan(manifest).get("provinces", [])
    }


def stage2_root(province: int, parents: dict[int, int]) -> int:
    """The province as it stood before Stage 2, through every Stage 2 parent.

    A part of a remainder has a new id as its direct parent, so tables keyed
    by the provinces before Stage 2 are read through this root.
    """
    while province in parents:
        province = parents[province]
    return province


def split_centres() -> dict[int, int]:
    """The centre province of every state split off its parent by the new-states builder.

    A split half counts its centre, which that builder raises to a victory
    point of 3, as the city and the town of its state; nothing is carved
    for it.
    """
    from tools.builders.build_adiscord_new_states import STATE_SPLITS

    return {int(child): int(split["centre"]) for child, split in STATE_SPLITS.items()}


def stage2_urban_provinces(manifest: dict) -> frozenset[int]:
    """Stage 2 cities keep their parent id; towns and districts take new ids."""
    plan = stage2_plan(manifest)
    districts = {
        int(entry["province"])
        for entry in plan.get("provinces", [])
        if entry["kind"] == "district"
    }
    return frozenset(
        {int(city) for city in plan.get("cities", {}).values()}
        | {int(town) for town in plan.get("towns", {}).values()}
        | districts
    )


@dataclass(frozen=True)
class ManifestTables:
    island_terrain: dict[int, str]
    city_provinces: frozenset[int]
    island_urban: frozenset[int]
    relief_excluded: frozenset[int]
    authored_rivers: frozenset[int]


def manifest_tables(manifest: dict) -> ManifestTables:
    """Province tables of both plans of the manifest.

    Stage 1 entries resolve through their direct parent, as reviewed; Stage 2
    entries resolve through their root before Stage 2.
    """
    parents = stage2_parents(manifest)
    urban = stage2_urban_provinces(manifest)
    island_terrain = {
        **ISLAND_PARENT_TERRAIN,
        **{
            int(entry["province"]): (
                "urban"
                if entry["kind"] == "city"
                else ISLAND_PARENT_TERRAIN[int(entry["parent"])]
            )
            for entry in manifest["provinces"]
            if int(entry["parent"]) in ISLAND_PARENT_TERRAIN
        },
    }
    later_terrain = {
        province: "urban" if province in urban else island_terrain[stage2_root(province, parents)]
        for province in parents
        if stage2_root(province, parents) in island_terrain
    }
    later_terrain.update(
        {province: "urban" for province in urban if province in island_terrain}
    )
    island_terrain.update(later_terrain)
    # Every IVN city victory point and every urban island province is urban
    # in its entirety; rural settlement markers stay ordinary provinces.
    city_provinces = frozenset(
        int(city) for city in manifest["cities"].values()
    ) | urban
    island_urban = frozenset(
        province_id
        for province_id, terrain_type in island_terrain.items()
        if terrain_type == "urban"
    )
    authored = _AUTHORED_RIVER_PARENTS | frozenset(
        int(entry["province"])
        for entry in manifest["provinces"]
        if entry["parent"] in _AUTHORED_RIVER_PARENTS
    )
    return ManifestTables(
        island_terrain=island_terrain,
        city_provinces=city_provinces,
        island_urban=island_urban,
        relief_excluded=_RELIEF_EXCLUDED_PARENTS
        | frozenset(
            province
            for province in parents
            if stage2_root(province, parents) in _RELIEF_EXCLUDED_PARENTS
        ),
        authored_rivers=authored
        | frozenset(
            province for province in parents if stage2_root(province, parents) in authored
        ),
    )


_TABLES = manifest_tables(PROVINCE_MANIFEST)
# Declared terrain of every island-administration province. Carved cities are
# urban and split sectors keep their parent's terrain. The island is painted
# and raised province by province from this table, so its texture, relief and
# definition.csv terrain agree.
ISLAND_PROVINCE_TERRAIN = _TABLES.island_terrain
CITY_PROVINCES = _TABLES.city_provinces
ISLAND_URBAN_PROVINCES = _TABLES.island_urban
SETTLEMENT_PROVINCES = CITY_PROVINCES | ISLAND_URBAN_PROVINCES
RELIEF_EXCLUDED_PROVINCES = _TABLES.relief_excluded
AUTHORED_RIVER_PROVINCES = _TABLES.authored_rivers
# Waypoints from the source to the mouth. Rivers run only on province-border
# pixels, so they separate provinces instead of crossing them.
RIVER_COURSES = (
    ((2853, 1016), (2849, 1045), (2846, 1075), (2836, 1090), (2815, 1094), (2795, 1099), (2782, 1101)),
    ((2858, 996), (2853, 980), (2850, 962), (2855, 948)),
    ((2860, 1066), (2863, 1086), (2858, 1110), (2845, 1128), (2828, 1136), (2806, 1122)),
    ((2827, 1228), (2840, 1232), (2850, 1236), (2858, 1244)),
)
RIVER_MOUTH_RADIUS = 14
RIVER_SIDE_SWITCH_COST = 30.0
# With ``route_rivers(states=...)`` a step onto a pixel of a line between
# states costs this instead of 1, so a course takes a province border that is
# also a state line where one runs beside it. The map pass does not
# pass states: the preference would move the courses it already settled.
RIVER_STATE_LINE_STEP = 0.5
RIVER_SHORE_CLEARANCE = 3.0
RIVER_SOURCE_PALETTE = 0
RIVER_SEA_PALETTE = 254
RIVER_LAND_PALETTE = 255
RIVER_BMP_HEADER_SIZE = 54
UNIFORM_TERRAIN_PALETTES = {
    "plains": 0,
    "forest": 4,
    "hills": 17,
    "mountain": 20,
    "marsh": 9,
}
ISLAND_TERRAIN_PALETTES = {**UNIFORM_TERRAIN_PALETTES, "urban": 13}
# Island relief by declared terrain: (base height, relief amplitude). Uplands
# use ridged noise and rise inside their own provinces; lowlands stay level
# up to their border. A town takes the level of the country around it; its
# base height applies only to a town without rural land within reach.
ISLAND_RELIEF = {
    "plains": (104.0, 3.0),
    "urban": (105.0, 1.5),
    "forest": (108.0, 4.5),
    "hills": (130.0, 11.0),
}
ISLAND_UPLAND_TYPES = frozenset({"hills"})
ISLAND_BLEND_SIGMA = 1.6
ISLAND_COAST_RAMP = 3.0
ISLAND_RIVER_RADIUS = 2.5
ISLAND_RIVER_DEPTH = 0.45
ISLAND_TOWN_SIGMA = 4.0
TERRAIN_PRIORITY = (
    "urban",
    "mountain",
    "hills",
    "marsh",
    "forest",
    "plains",
    "jungle",
    "desert",
)
WATER_TYPES = frozenset({"ocean", "lakes"})
WATER_PALETTES = frozenset({14, 15})
PLAINS_PALETTE = 0
FOREST_PALETTE = 4
MARSH_PALETTE = 9
URBAN_PALETTE = 13
HILLS_PALETTE = 17
MOUNTAIN_PALETTE = 20
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
    state_by_pixel: array


@dataclass(frozen=True)
class TreeCellSample:
    state_id: int | None
    terrain_type: str


@dataclass(frozen=True)
class CoverageMetrics:
    tree_occupancy: dict[str, float]
    forbidden_tree_cells: int
    terrain_changes_outside_scope: int
    tree_changes_outside_scope: int
    mountain_pixels: int
    hill_pixels: int
    mountain_transition_violations: int
    mountain_components_without_shoulders: int
    mountain_provinces_without_foothills: tuple[int, ...]


@dataclass
class GeographyOutputs:
    terrain: Image.Image
    definition: bytes
    heightmap: Image.Image
    world_normal: Image.Image
    trees: Image.Image
    cities: Image.Image
    rivers: Image.Image
    unitstacks: bytes
    river_issues: list[str]
    desired: dict[int, str]
    counts: dict[int, Counter[str]]
    footprints: dict[int, set[int]]
    metrics: CoverageMetrics


def state_path(state_id: int) -> Path:
    matches = tuple(STATE_DIR.glob(f"{state_id}-*.txt"))
    if len(matches) != 1:
        raise RuntimeError(f"state {state_id}: expected one file, found {len(matches)}")
    return matches[0]


def stage2_children(province_ids: set[int]) -> set[int]:
    """Stage 2 provinces made from ``province_ids``, before a state file lists them.

    The state files gain the new ids only after this builder has stamped
    them, so the scope follows the plan from the first pass.
    """
    members = set(province_ids)
    for entry in sorted(
        stage2_plan(PROVINCE_MANIFEST).get("provinces", []),
        key=lambda entry: entry["province"],
    ):
        if int(entry["parent"]) in members:
            members.add(int(entry["province"]))
    return members - set(province_ids)


def province_ids_for_states(state_ids: frozenset[int]) -> frozenset[int]:
    result: set[int] = set()
    for state_id in state_ids:
        source = state_path(state_id).read_text(encoding="utf-8-sig", errors="strict")
        match = re.search(r"\bprovinces\s*=\s*\{([^}]*)\}", source, re.DOTALL)
        if match is None:
            raise RuntimeError(f"state {state_id}: missing provinces block")
        province_ids = {int(value) for value in re.findall(r"\d+", match.group(1))}
        province_ids |= stage2_children(province_ids)
        overlap = result & province_ids
        if overlap:
            raise RuntimeError(f"IVN/IIA state provinces overlap: {sorted(overlap)}")
        result.update(province_ids)
    return frozenset(result)


def scoped_provinces() -> frozenset[int]:
    return province_ids_for_states(SCOPED_STATE_IDS)


def province_state_contract(state_ids: frozenset[int]) -> dict[int, int]:
    result: dict[int, int] = {}
    for state_id in sorted(state_ids):
        for province_id in province_ids_for_states(frozenset({state_id})):
            if province_id in result:
                raise RuntimeError(
                    f"province {province_id}: assigned to states {result[province_id]} and {state_id}"
                )
            result[province_id] = state_id
    return result


def landscape_masks(
    provinces: Image.Image,
    definition_colors: dict[int, tuple[int, int, int]],
) -> LandscapeMasks:
    island_provinces = province_ids_for_states(ISLAND_HEIGHT_STATE_IDS)
    north_provinces = province_ids_for_states(NORTHERN_LANDSCAPE_STATE_IDS)
    state_by_province = province_state_contract(NORTHERN_LANDSCAPE_STATE_IDS)
    missing = sorted(north_provinces - definition_colors.keys())
    if missing:
        raise RuntimeError(
            f"definition.csv: missing northern landscape provinces {missing}"
        )

    color_to_id = {
        color: province_id for province_id, color in definition_colors.items()
    }
    if len(color_to_id) != len(definition_colors):
        raise RuntimeError(
            "definition.csv: duplicate RGB inside northern landscape scope"
        )
    try:
        rgb = provinces.convert("RGB")
        pixels = rgb.tobytes()
    except (OSError, ValueError) as exc:
        raise RuntimeError("provinces bitmap cannot convert to RGB") from exc

    island = bytearray(provinces.width * provinces.height)
    north = bytearray(provinces.width * provinces.height)
    state_by_pixel = array("H", [0]) * (provinces.width * provinces.height)
    seen_northern_provinces: set[int] = set()
    min_x = provinces.width
    min_y = provinces.height
    max_x = -1
    max_y = -1
    for index in range(provinces.width * provinces.height):
        color = tuple(pixels[index * 3 : index * 3 + 3])
        province_id = color_to_id.get(color)
        if province_id in north_provinces:
            north[index] = 1
            state_by_pixel[index] = state_by_province[province_id]
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
        raise RuntimeError(
            f"provinces bitmap: missing northern landscape bitmap provinces {missing_pixels}"
        )
    return LandscapeMasks(island, north, (min_x, min_y, max_x, max_y), state_by_pixel)


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


def lattice_noise(xs: np.ndarray, ys: np.ndarray, cell: float, salt: int) -> np.ndarray:
    """Return smooth 0..1 value noise anchored to absolute map coordinates."""
    gx = xs / cell
    gy = ys / cell
    x0 = np.floor(gx).astype(int)
    y0 = np.floor(gy).astype(int)
    sx = gx - x0
    sy = gy - y0
    sx = sx * sx * (3.0 - 2.0 * sx)
    sy = sy * sy * (3.0 - 2.0 * sy)
    left = int(x0.min())
    top = int(y0.min())
    lattice = np.array(
        [
            [stable_unit_hash(x, y, salt) for x in range(left, int(x0.max()) + 2)]
            for y in range(top, int(y0.max()) + 2)
        ]
    )
    column = x0 - left
    row = y0 - top
    upper = lattice[row, column] * (1.0 - sx) + lattice[row, column + 1] * sx
    lower = lattice[row + 1, column] * (1.0 - sx) + lattice[row + 1, column + 1] * sx
    return upper * (1.0 - sy) + lower * sy


def level_towns_with_surroundings(
    base: np.ndarray, land: np.ndarray, towns: np.ndarray
) -> None:
    """Set each connected town to the mean base level of the land around it.

    The level is a Gaussian-weighted average of the rural base heights, so a
    town in the hills stands on the hills instead of sinking into a pit.
    """
    rural = land & ~towns
    weight = gaussian_filter(rural.astype(float), ISLAND_TOWN_SIGMA)
    surroundings = gaussian_filter(base * rural, ISLAND_TOWN_SIGMA) / np.maximum(weight, 1e-6)
    pieces, count = label(towns)
    for piece in range(1, count + 1):
        town = pieces == piece
        if weight[town].max() > 1e-3:
            base[town] = float(surroundings[town].mean())


def render_island_heights(
    heights: np.ndarray,
    terrain: np.ndarray,
    bbox: tuple[int, int, int, int],
    rivers: np.ndarray,
) -> np.ndarray:
    """Raise the island administration from the declared terrain of each province.

    `terrain` holds an index into ISLAND_RELIEF for island pixels and -1
    elsewhere. Heights depend only on position, that table, the coast and the
    authored river course, so repeated passes converge. Pixels outside the
    island keep their heights.
    """
    if terrain.shape != heights.shape or rivers.shape != heights.shape:
        raise ValueError("island relief inputs must match heightmap dimensions")
    min_x, min_y, max_x, max_y = bbox
    if not (0 <= min_x <= max_x < heights.shape[1] and 0 <= min_y <= max_y < heights.shape[0]):
        raise ValueError("island bounding box lies outside heightmap")
    margin = int(ISLAND_BLEND_SIGMA * 4) + 2
    crop = (
        slice(max(0, min_y - margin), min(heights.shape[0], max_y + margin + 1)),
        slice(max(0, min_x - margin), min(heights.shape[1], max_x + margin + 1)),
    )
    types = terrain[crop]
    land = types >= 0
    base = np.zeros(types.shape)
    amplitude = np.zeros(types.shape)
    upland = np.zeros(types.shape)
    for index, (terrain_type, (level, relief)) in enumerate(ISLAND_RELIEF.items()):
        inside = types == index
        base[inside] = level
        amplitude[inside] = relief
        upland[inside] = terrain_type in ISLAND_UPLAND_TYPES
    level_towns_with_surroundings(base, land, types == list(ISLAND_RELIEF).index("urban"))

    weight = np.maximum(gaussian_filter(land.astype(float), ISLAND_BLEND_SIGMA), 1e-6)

    def blend(field: np.ndarray) -> np.ndarray:
        return gaussian_filter(field * land, ISLAND_BLEND_SIGMA) / weight

    # Uplands climb from their own border; a lowland or town never takes
    # height or roughness from the upland next to it.
    level = np.where(upland > 0, blend(base), np.minimum(blend(base), base + 1.0))
    relief = np.where(upland > 0, blend(amplitude), np.minimum(blend(amplitude), amplitude))
    ridged_share = blend(upland)
    gy, gx = np.mgrid[crop].astype(float)
    smooth = 0.65 * lattice_noise(gx, gy, 9.0, 31) + 0.35 * lattice_noise(gx, gy, 4.0, 37)
    ridged = 0.7 * (1.0 - np.abs(2.0 * lattice_noise(gx, gy, 5.0, 41) - 1.0))
    ridged += 0.3 * lattice_noise(gx, gy, 3.0, 43)
    detail = (1.0 - ridged_share) * smooth + ridged_share * ridged
    height = level + relief * (2.0 * detail - 1.0)

    river = (rivers[crop] < RIVER_SEA_PALETTE) & land
    if river.any():
        valley = np.exp(-((distance_transform_edt(~river) / ISLAND_RIVER_RADIUS) ** 2))
        height -= valley * ISLAND_RIVER_DEPTH * np.maximum(0.0, height - (HEIGHT_MIN + 3))
    ramp = np.clip(distance_transform_edt(land) / ISLAND_COAST_RAMP, 0.0, 1.0)
    ramp = ramp * ramp * (3.0 - 2.0 * ramp)
    height = HEIGHT_MIN + ramp * (height - HEIGHT_MIN)

    values = np.clip(np.rint(height), HEIGHT_MIN, HEIGHT_MAX).astype(np.uint8)
    result = heights.copy()
    result[crop] = np.where(land, values, heights[crop])
    return result


def height_slope(
    pixels: list[int] | bytes | bytearray, width: int, height: int, index: int
) -> int:
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
        raise ValueError(
            "world normal dimensions must equal half the heightmap dimensions"
        )
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
            full_indices = (
                top + left,
                top + left + 1,
                bottom + left,
                bottom + left + 1,
            )
            normal_index = ny * normal_width + nx
            means[normal_index] = sum(heights[index] for index in full_indices) / 4.0
            island_cells[normal_index] = any(
                island_mask[index] for index in full_indices
            )

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
        pixels[offset : offset + 3] = bytes((red, green, NORMAL_BLUE))
    return Image.frombytes("RGB", source.size, bytes(pixels))


def moisture_value(u: float, v: float, x: int, y: int) -> float:
    broad = 0.50 + 0.22 * sin(5.0 * u + 3.0 * v) + 0.18 * cos(4.0 * u - 6.0 * v)
    return broad + 0.10 * (stable_unit_hash(x, y, 11) - 0.5)


def tree_probability(terrain_type: str) -> float:
    return {
        "forest": 0.62,
        "plains": 0.04,
        "hills": 0.025,
        "marsh": 0.08,
    }.get(terrain_type, 0.0)


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


def definition_contract() -> (
    tuple[list[str], str, bytes, dict[int, tuple[int, int, int]], dict[int, str]]
):
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
            raise RuntimeError(
                f"province {province_id}: IVN/IIA scope contains non-land province"
            )
        colors[province_id] = tuple(map(int, fields[1:4]))
        declared[province_id] = fields[6]
    missing = sorted(scoped - colors.keys())
    if missing:
        raise RuntimeError(f"definition.csv: missing IVN/IIA provinces {missing}")
    return lines, newline, (b"\xef\xbb\xbf" if bom else b""), colors, declared


def pixel_neighbours(index: int, width: int, pixel_count: int) -> tuple[int, ...]:
    x = index % width
    neighbours: list[int] = []
    if x:
        neighbours.append(index - 1)
    if x + 1 < width and index + 1 < pixel_count:
        neighbours.append(index + 1)
    if index >= width:
        neighbours.append(index - width)
    if index + width < pixel_count:
        neighbours.append(index + width)
    return tuple(neighbours)


def masked_height_slope(
    pixels: bytes | bytearray,
    mask: bytearray,
    width: int,
    index: int,
) -> int:
    return max(
        (
            abs(pixels[index] - pixels[neighbour])
            for neighbour in pixel_neighbours(index, width, len(pixels))
            if mask[neighbour]
        ),
        default=0,
    )


def settlement_buffer(
    footprints: dict[int, set[int]],
    north_mask: bytearray,
    width: int,
    radius: int = 6,
) -> bytearray:
    result = bytearray(len(north_mask))
    frontier = {
        index
        for footprint in footprints.values()
        for index in footprint
        if north_mask[index]
    }
    for index in frontier:
        result[index] = 1
    for _distance in range(radius):
        following: set[int] = set()
        for index in frontier:
            for neighbour in pixel_neighbours(index, width, len(north_mask)):
                if north_mask[neighbour] and not result[neighbour]:
                    result[neighbour] = 1
                    following.add(neighbour)
        frontier = following
        if not frontier:
            break
    return result


def render_northern_terrain(
    source: Image.Image,
    heightmap: Image.Image,
    north_mask: bytearray,
    state_by_pixel: Sequence[int],
    footprints: dict[int, set[int]],
) -> Image.Image:
    if source.mode != "P":
        raise ValueError("terrain source must use mode P")
    if heightmap.mode != "L" or heightmap.size != source.size:
        raise ValueError("heightmap must use mode L and match terrain dimensions")
    width, height = source.size
    pixel_count = width * height
    if not (len(north_mask) == len(state_by_pixel) == pixel_count):
        raise ValueError("northern terrain masks do not match terrain dimensions")

    original = bytearray(source.get_flattened_data())
    heights = heightmap.tobytes()
    pixels = bytearray(original)
    urban = {
        index
        for footprint in footprints.values()
        for index in footprint
        if north_mask[index]
    }
    urban.update(
        index
        for index, included in enumerate(north_mask)
        if included and original[index] == URBAN_PALETTE
    )
    preserved_marsh = {
        index
        for index, included in enumerate(north_mask)
        if included
        and state_by_pixel[index] == 164
        and original[index] == MARSH_PALETTE
    }
    land = {
        index
        for index, included in enumerate(north_mask)
        if included and original[index] not in WATER_PALETTES
    }
    classifiable = land - urban - preserved_marsh
    slopes = {
        index: masked_height_slope(heights, north_mask, width, index) for index in land
    }
    mountains = {
        index for index in classifiable if heights[index] >= 158 or slopes[index] >= 12
    }

    first_shoulder: set[int] = set()
    for index in mountains:
        first_shoulder.update(
            neighbour
            for neighbour in pixel_neighbours(index, width, pixel_count)
            if neighbour in classifiable and neighbour not in mountains
        )
    second_candidates: set[int] = set()
    for index in first_shoulder:
        second_candidates.update(
            neighbour
            for neighbour in pixel_neighbours(index, width, pixel_count)
            if neighbour in classifiable
            and neighbour not in mountains
            and neighbour not in first_shoulder
        )
    second_shoulder = {
        index
        for index in second_candidates
        if heights[index] >= 125 or slopes[index] >= 4
    }
    shoulders = first_shoulder | second_shoulder
    hills = shoulders | {
        index
        for index in classifiable - mountains - shoulders
        if heights[index] >= 132 or slopes[index] >= 6
    }

    for index in land:
        if index in urban:
            pixels[index] = URBAN_PALETTE
        elif index in preserved_marsh:
            pixels[index] = MARSH_PALETTE
        elif index in mountains:
            pixels[index] = MOUNTAIN_PALETTE
        elif index in hills:
            pixels[index] = HILLS_PALETTE
        else:
            pixels[index] = PLAINS_PALETTE

    coast_distances = distance_from_edge(north_mask, width, height)
    buffered = settlement_buffer(footprints, north_mask, width)
    min_x = min(index % width for index in land)
    max_x = max(index % width for index in land)
    min_y = min(index // width for index in land)
    max_y = max(index // width for index in land)
    x_span = max(1, max_x - min_x)
    y_span = max(1, max_y - min_y)
    state_land: dict[int, list[int]] = {}
    forest_candidates: dict[int, list[int]] = {}
    for index in land:
        state_id = state_by_pixel[index]
        if not state_id or index in urban:
            continue
        state_land.setdefault(state_id, []).append(index)
        if (
            index not in preserved_marsh
            and index not in mountains
            and index not in hills
            and not buffered[index]
            and not (0 <= coast_distances[index] < 2)
        ):
            forest_candidates.setdefault(state_id, []).append(index)
    # The moisture field spans the whole northern landscape, island included,
    # but the island takes its forests from its province table.
    for state_id, state_indices in state_land.items():
        if state_id in ISLAND_HEIGHT_STATE_IDS:
            continue
        quota = round(len(state_indices) * 0.225)
        candidates = forest_candidates.get(state_id, [])
        if len(candidates) < quota:
            raise RuntimeError(
                f"state {state_id}: only {len(candidates)} forest candidates for quota {quota}"
            )
        ranked = sorted(
            candidates,
            key=lambda index: (
                -moisture_value(
                    (index % width - min_x) / x_span,
                    (index // width - min_y) / y_span,
                    index % width,
                    index // width,
                ),
                index,
            ),
        )
        for index in ranked[:quota]:
            pixels[index] = FOREST_PALETTE

    result = source.copy()
    result.putdata(pixels)
    return result


def _tree_cell_sample_from_pixels(
    tx: int,
    ty: int,
    tree_width: int,
    tree_height: int,
    full_width: int,
    full_height: int,
    terrain_pixels: Sequence[int],
    state_by_pixel: Sequence[int],
    palette: dict[int, str],
) -> TreeCellSample:
    if len(state_by_pixel) != full_width * full_height:
        raise ValueError("tree state mask does not match terrain dimensions")
    if not (0 <= tx < tree_width and 0 <= ty < tree_height):
        raise IndexError("tree cell lies outside tree dimensions")
    x0 = tx * full_width // tree_width
    x1 = (tx + 1) * full_width // tree_width
    y0 = ty * full_height // tree_height
    y1 = (ty + 1) * full_height // tree_height
    states: Counter[int] = Counter()
    terrain_counts: Counter[str] = Counter()
    for y in range(y0, y1):
        offset = y * full_width
        for x in range(x0, x1):
            index = offset + x
            state_id = state_by_pixel[index]
            if state_id:
                states[state_id] += 1
            terrain_index = terrain_pixels[index]
            terrain_type = palette.get(terrain_index)
            if terrain_type is None:
                raise RuntimeError(
                    f"tree sample uses unknown terrain palette {terrain_index}"
                )
            terrain_counts[terrain_type] += 1
    sample_size = (x1 - x0) * (y1 - y0)
    state_id = None
    if sum(states.values()) > sample_size / 2:
        state_id = max(states, key=lambda value: (states[value], -value))
    priority = {
        terrain_type: len(TERRAIN_PRIORITY) - rank
        for rank, terrain_type in enumerate(TERRAIN_PRIORITY)
    }
    terrain_type = max(
        terrain_counts,
        key=lambda value: (terrain_counts[value], priority.get(value, 0)),
    )
    return TreeCellSample(state_id, terrain_type)


def tree_cell_sample(
    tx: int,
    ty: int,
    tree_width: int,
    tree_height: int,
    terrain: Image.Image,
    state_by_pixel: Sequence[int],
    palette: dict[int, str],
) -> TreeCellSample:
    return _tree_cell_sample_from_pixels(
        tx,
        ty,
        tree_width,
        tree_height,
        terrain.width,
        terrain.height,
        terrain.get_flattened_data(),
        state_by_pixel,
        palette,
    )


def _render_trees_with_metrics(
    source: Image.Image,
    terrain: Image.Image,
    state_by_pixel: Sequence[int],
    palette: dict[int, str],
    blocked: "np.ndarray | None" = None,
) -> tuple[Image.Image, dict[str, tuple[int, int]], int, int]:
    if source.mode != "P":
        raise RuntimeError("trees.bmp must remain paletted")
    tree_width, tree_height = source.size
    source_pixels = bytearray(source.get_flattened_data())
    pixels = bytearray(source_pixels)
    terrain_pixels = terrain.get_flattened_data()
    counts: dict[str, list[int]] = {}
    forbidden = 0
    outside_changes = 0
    for ty in range(tree_height):
        for tx in range(tree_width):
            tree_index = ty * tree_width + tx
            sample = _tree_cell_sample_from_pixels(
                tx,
                ty,
                tree_width,
                tree_height,
                terrain.width,
                terrain.height,
                terrain_pixels,
                state_by_pixel,
                palette,
            )
            if sample.state_id is None:
                if pixels[tree_index] != source_pixels[tree_index]:
                    outside_changes += 1
                continue
            probability = tree_probability(sample.terrain_type)
            if blocked is not None and blocked[ty, tx]:
                pixels[tree_index] = 0
            elif stable_unit_hash(tx, ty, 23) < probability:
                pixels[tree_index] = 6 if stable_unit_hash(tx, ty, 29) < 0.65 else 5
            else:
                pixels[tree_index] = 0
            terrain_counts = counts.setdefault(sample.terrain_type, [0, 0])
            terrain_counts[0] += 1
            if pixels[tree_index]:
                terrain_counts[1] += 1
                if sample.terrain_type in WATER_TYPES | {"urban", "mountain"}:
                    forbidden += 1
    result = source.copy()
    result.putdata(pixels)
    return (
        result,
        {
            terrain_type: (values[0], values[1])
            for terrain_type, values in counts.items()
        },
        forbidden,
        outside_changes,
    )


def render_trees(
    source: Image.Image,
    terrain: Image.Image,
    state_by_pixel: Sequence[int],
    palette: dict[int, str],
    blocked: "np.ndarray | None" = None,
) -> Image.Image:
    return _render_trees_with_metrics(source, terrain, state_by_pixel, palette, blocked)[0]


def packed_rgb(province_rgb: np.ndarray) -> np.ndarray:
    return (
        (province_rgb[..., 0].astype(np.uint32) << 16)
        | (province_rgb[..., 1].astype(np.uint32) << 8)
        | province_rgb[..., 2].astype(np.uint32)
    )


def province_mask(
    packed: np.ndarray,
    province_colors: dict[int, tuple[int, int, int]],
    province_ids: frozenset[int],
) -> np.ndarray:
    keys = [
        (red << 16) | (green << 8) | blue
        for province_id, (red, green, blue) in province_colors.items()
        if province_id in province_ids
    ]
    return np.isin(packed, np.array(keys, dtype=np.uint32))


def relief_province_ids(state_ids: frozenset[int]) -> frozenset[int]:
    return province_ids_for_states(state_ids) - RELIEF_EXCLUDED_PROVINCES


def polyline_distance(
    xs: np.ndarray, ys: np.ndarray, points: Sequence[tuple[int, int]]
) -> tuple[np.ndarray, np.ndarray]:
    """Distance to a polyline and the normalised position along it."""
    lengths = [
        float(np.hypot(bx - ax, by - ay))
        for (ax, ay), (bx, by) in zip(points, points[1:])
    ]
    total = sum(lengths)
    best = np.full(xs.shape, np.inf)
    along = np.zeros(xs.shape)
    offset = 0.0
    for (ax, ay), (bx, by), length in zip(points, points[1:], lengths):
        dx = bx - ax
        dy = by - ay
        t = np.clip(((xs - ax) * dx + (ys - ay) * dy) / (length * length), 0.0, 1.0)
        distance = np.hypot(xs - (ax + t * dx), ys - (ay + t * dy))
        closer = distance < best
        best = np.where(closer, distance, best)
        along = np.where(closer, (offset + t * length) / total, along)
        offset += length
    return best, along


def relief_target(
    xs: np.ndarray, ys: np.ndarray, coast_distance: np.ndarray
) -> tuple[np.ndarray, np.ndarray]:
    """Return mainland heights and the fen mask for absolute map coordinates."""
    base = (
        106.0
        + 5.0 * np.sin(xs / 19.0 + ys / 27.0)
        + 4.0 * np.cos(xs / 13.0 - ys / 23.0)
        + 3.0 * np.sin((xs + ys) / 41.0)
    )
    spine, along = polyline_distance(xs, ys, RIDGE_SPINE)
    ridge = (34.0 + 44.0 * np.sin(pi * along)) * np.exp(-((spine / 12.0) ** 2))
    spur_distance, spur_along = polyline_distance(xs, ys, RIDGE_SPUR)
    spur = (
        42.0
        * (0.6 + 0.4 * np.sin(pi * spur_along))
        * np.exp(-((spur_distance / 10.0) ** 2))
    )
    raised = np.maximum(ridge, spur)
    for cx, cy, sx, sy, amplitude in RELIEF_DOMES:
        raised = np.maximum(
            raised,
            amplitude * np.exp(-(((xs - cx) / sx) ** 2 + ((ys - cy) / sy) ** 2)),
        )
    fen, _ = polyline_distance(xs, ys, FEN_LINE)
    # Lowland undulation fades over nine pixels; uplands meet the sea in
    # three, so the narrow Olsia peninsula keeps its relief.
    lowland = np.minimum(1.0, coast_distance / 9.0)
    upland = np.minimum(1.0, coast_distance / 3.0)
    height = (
        HEIGHT_MIN
        + lowland * (base - HEIGHT_MIN)
        + upland * raised
        - lowland * 9.0 * np.exp(-((fen / 6.0) ** 2))
    )
    return height, fen <= FEN_HALF_WIDTH


def render_relief_heights(
    heights: np.ndarray, relief: np.ndarray, water: np.ndarray
) -> tuple[np.ndarray, np.ndarray]:
    """Rebuild relief heights, blending into unchanged foreign land."""
    ys, xs = np.nonzero(relief)
    y0 = max(0, int(ys.min()) - 24)
    y1 = min(heights.shape[0], int(ys.max()) + 25)
    x0 = max(0, int(xs.min()) - 24)
    x1 = min(heights.shape[1], int(xs.max()) + 25)
    crop = (slice(y0, y1), slice(x0, x1))
    foreign = ~water[crop] & ~relief[crop]
    coast_distance = distance_transform_edt(~water[crop])
    foreign_distance, (fy, fx) = distance_transform_edt(~foreign, return_indices=True)
    gy, gx = np.mgrid[y0:y1, x0:x1].astype(float)
    target, fen = relief_target(gx, gy, coast_distance)
    weight = np.minimum(1.0, foreign_distance / 8.0)
    blended = weight * target + (1.0 - weight) * heights[crop][fy, fx].astype(float)
    values = np.clip(np.rint(blended), HEIGHT_MIN, HEIGHT_MAX).astype(np.uint8)
    result = heights.copy()
    result[crop] = np.where(relief[crop], values, heights[crop])
    fen_mask = np.zeros(heights.shape, bool)
    fen_mask[crop] = fen & relief[crop]
    return result, fen_mask


def neighbours_of(mask: np.ndarray) -> np.ndarray:
    result = np.zeros(mask.shape, bool)
    for axis, shift in ((0, 1), (0, -1), (1, 1), (1, -1)):
        result |= np.roll(mask, shift, axis)
    return result


def masked_slopes(heights: np.ndarray, mask: np.ndarray) -> np.ndarray:
    values = heights.astype(np.int16)
    slope = np.zeros(values.shape, np.int16)
    for axis, shift in ((0, 1), (0, -1), (1, 1), (1, -1)):
        neighbour = np.roll(values, shift, axis)
        inside = np.roll(mask, shift, axis)
        slope = np.maximum(slope, np.where(inside, np.abs(values - neighbour), 0))
    return np.where(mask, slope, 0)


def ellipse_mask(
    shape: tuple[int, int], zones: Sequence[tuple[int, int, float, float]]
) -> np.ndarray:
    result = np.zeros(shape, bool)
    for cx, cy, rx, ry in zones:
        y0 = int(cy - ry - 1)
        x0 = int(cx - rx - 1)
        gy, gx = np.mgrid[y0 : int(cy + ry + 2), x0 : int(cx + rx + 2)]
        inside = ((gx - cx) / rx) ** 2 + ((gy - cy) / ry) ** 2 <= 1.0
        result[y0 : y0 + inside.shape[0], x0 : x0 + inside.shape[1]] |= inside
    return result


def paint_provinces(
    pixels: np.ndarray,
    scope: np.ndarray,
    province_ids: np.ndarray,
    city_pixels: np.ndarray,
    palettes: dict[int, int],
    shore: np.ndarray,
) -> None:
    """Paint each listed province inside `scope` in its one palette, in place.

    Water and city-model pixels keep their palette, and urban paint stops at
    the shoreline clearance band so city meshes stay out of the sea.
    """
    ys, xs = np.nonzero(scope)
    window = (
        slice(int(ys.min()), int(ys.max()) + 1),
        slice(int(xs.min()), int(xs.max()) + 1),
    )
    view = pixels[window]
    ids = province_ids[window]
    paintable = (
        scope[window]
        & ~np.isin(view, list(WATER_PALETTES))
        & ~np.isin(city_pixels[window], list(CITY_PALETTE_INDICES))
    )
    for province_id, palette_index in sorted(palettes.items()):
        target = paintable & (ids == province_id)
        view[target] = palette_index
        if palette_index == URBAN_PALETTE:
            view[target & shore[window]] = URBAN_FALLBACK_PALETTE


def province_terrain_type(counts: Counter[str]) -> str:
    """Choose the single terrain of a mainland province from its relief."""
    total = sum(counts.values())
    shares = {terrain_type: counts.get(terrain_type, 0) / total for terrain_type in TERRAIN_PRIORITY}
    if shares["marsh"] >= 0.35:
        return "marsh"
    if shares["mountain"] >= 0.4:
        return "mountain"
    if shares["mountain"] + shares["hills"] >= 0.4:
        return "hills"
    if shares["forest"] >= 0.4:
        return "forest"
    landscape = {
        terrain_type: count
        for terrain_type, count in counts.items()
        if terrain_type in UNIFORM_TERRAIN_PALETTES
    }
    return max(landscape, key=lambda terrain_type: landscape[terrain_type], default="plains")


def palette_indices(palette: dict[int, str], *terrain_types: str) -> list[int]:
    return [index for index, value in palette.items() if value in terrain_types]


def classify_march_terrain(
    pixels: np.ndarray,
    heights: np.ndarray,
    march: np.ndarray,
    relief: np.ndarray,
    fen: np.ndarray,
    forest_zone: np.ndarray,
    palette: dict[int, str],
) -> np.ndarray:
    """Derive march and southern terrain from relief and the authored zones.

    The northern thresholds apply, so the ridge stays continuous across the
    northern landscape border. Existing forest and lowland textures survive
    on flat ground; painted relief without matching height becomes plains.
    """
    land = march & ~np.isin(pixels, palette_indices(palette, "ocean", "lakes"))
    urban = land & (pixels == URBAN_PALETTE)
    marsh = land & ~urban & (fen | (pixels == MARSH_PALETTE))
    classifiable = land & ~urban & ~marsh
    slope = masked_slopes(heights, relief)
    mountains = classifiable & ((heights >= 158) | (slope >= 12))
    first = classifiable & ~mountains & neighbours_of(mountains)
    second = (
        classifiable
        & ~mountains
        & ~first
        & neighbours_of(first)
        & ((heights >= 125) | (slope >= 4))
    )
    hills = classifiable & ~mountains & (first | second | (heights >= 132) | (slope >= 6))
    flat = classifiable & ~mountains & ~hills
    old_forest = np.isin(pixels, palette_indices(palette, "forest"))
    old_relief = np.isin(pixels, palette_indices(palette, "hills", "mountain"))
    result = pixels.copy()
    result[marsh] = MARSH_PALETTE
    result[mountains] = MOUNTAIN_PALETTE
    result[hills] = HILLS_PALETTE
    result[flat & forest_zone & ~old_forest] = FOREST_PALETTE
    result[flat & ~forest_zone & old_relief] = PLAINS_PALETTE
    return result


def _snap_river_point(point: tuple[int, int], allowed: np.ndarray) -> tuple[int, int]:
    x, y = point
    for radius in range(12):
        window = allowed[y - radius : y + radius + 1, x - radius : x + radius + 1]
        ys, xs = np.nonzero(window)
        if len(xs):
            order = np.argsort((xs - radius) ** 2 + (ys - radius) ** 2, kind="stable")
            return (x - radius + int(xs[order[0]]), y - radius + int(ys[order[0]]))
    raise RuntimeError(f"river waypoint {point} has no province-border pixel nearby")


def _route_river(
    start: tuple[int, int],
    goals: list[tuple[int, int]],
    allowed: np.ndarray,
    heights: np.ndarray,
    packed: np.ndarray,
    preferred: np.ndarray | None = None,
) -> list[tuple[int, int]]:
    """Cheapest 4-connected path along one side of each border.

    Climbing costs extra so rivers run downhill. Stepping onto the pixels of
    another province is expensive, so the course does not weave across the
    border line it follows. A step onto a ``preferred`` pixel is cheaper;
    where none is in reach the path is the one found without them.
    """
    goal_set = set(goals)
    gx = sum(x for x, _ in goals) / len(goals)
    gy = sum(y for _, y in goals) / len(goals)
    frontier = [(0.0, 0.0, start)]
    previous: dict[tuple[int, int], tuple[int, int] | None] = {start: None}
    best = {start: 0.0}
    while frontier:
        _estimate, spent, current = heapq.heappop(frontier)
        if current in goal_set:
            path = []
            step: tuple[int, int] | None = current
            while step is not None:
                path.append(step)
                step = previous[step]
            return path[::-1]
        if spent > best[current]:
            continue
        x, y = current
        for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if not allowed[ny, nx]:
                continue
            climb = max(0, int(heights[ny, nx]) - int(heights[y, x]))
            switch = RIVER_SIDE_SWITCH_COST if packed[ny, nx] != packed[y, x] else 0.0
            step = RIVER_STATE_LINE_STEP if preferred is not None and preferred[ny, nx] else 1.0
            value = spent + step + 0.8 * climb + switch
            if value < best.get((nx, ny), float("inf")):
                best[(nx, ny)] = value
                previous[(nx, ny)] = current
                heapq.heappush(
                    frontier, (value + abs(nx - gx) + abs(ny - gy), value, (nx, ny))
                )
    raise RuntimeError(f"river from {start} cannot reach its next waypoint along borders")


def _prune_river_loops(path: list[tuple[int, int]]) -> list[tuple[int, int]]:
    """Cut joined segments where the river would touch its own earlier course."""
    result: list[tuple[int, int]] = []
    position: dict[tuple[int, int], int] = {}
    for point in path:
        x, y = point
        touching = [
            position[neighbour]
            for neighbour in ((x, y), (x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1))
            if neighbour in position and position[neighbour] < len(result) - 1
        ]
        if touching:
            del result[min(touching) + 1 :]
            position = {value: index for index, value in enumerate(result)}
            if point in position:
                continue
        position[point] = len(result)
        result.append(point)
    return result


def river_width_palette(fraction: float, length: int) -> int:
    if fraction < 0.35:
        return 3
    if fraction < 0.7:
        return 4
    if length >= 150 and fraction >= 0.8:
        return 7
    return 6


def province_borders(packed: np.ndarray) -> np.ndarray:
    border = np.zeros(packed.shape, bool)
    for axis, shift in ((0, 1), (0, -1), (1, 1), (1, -1)):
        border |= np.roll(packed, shift, axis) != packed
    return border


def _trace_builder_course(
    course: Sequence[tuple[int, int]],
    allowed: np.ndarray,
    final_extra: np.ndarray,
    mouth: np.ndarray,
    heights: np.ndarray,
    packed: np.ndarray,
    preferred: np.ndarray | None = None,
) -> list[tuple[int, int]]:
    """Route one course of RIVER_COURSES from its source to the sea along allowed pixels."""
    path = [_snap_river_point(course[0], allowed)]
    for waypoint in course[1:-1]:
        target = _snap_river_point(waypoint, allowed)
        path.extend(_route_river(path[-1], [target], allowed, heights, packed, preferred)[1:])
    mx, my = course[-1]
    reach = RIVER_MOUTH_RADIUS
    estuary = np.zeros(mouth.shape, bool)
    estuary[my - reach : my + reach + 1, mx - reach : mx + reach + 1] = True
    goals = [
        (int(x), int(y)) for y, x in zip(*np.nonzero(mouth & estuary))
    ]
    if not goals:
        raise RuntimeError(f"river mouth {course[-1]} has no coastal border pixel")
    final = allowed | (final_extra & estuary) | (mouth & estuary)
    path.extend(_route_river(path[-1], goals, final, heights, packed, preferred)[1:])
    return _prune_river_loops(path)


def route_rivers(
    rivers: np.ndarray,
    packed: np.ndarray,
    relief: np.ndarray,
    authored: np.ndarray,
    water: np.ndarray,
    heights: np.ndarray,
    ids: np.ndarray | None = None,
    avoid: np.ndarray | None = None,
    states: np.ndarray | None = None,
) -> tuple[np.ndarray, list[list[tuple[int, int]]]]:
    """Redraw this builder's rivers on province borders inside the relief.

    With province ``ids`` a course that would cut a province apart is routed
    again without the cutting pixels; ``avoid`` pixels, the carved
    settlements, carry no course. With the ``states`` of the pixels a course
    prefers the province borders that are also state lines.
    """
    owned = relief & ~authored
    preferred = None if states is None else state_line_pixels(states, ~water)
    result = rivers.copy()
    cleared = owned & (result < RIVER_SEA_PALETTE)
    if ids is not None:
        # A settled course may turn or detour onto this land; it stays.
        cleared &= ~kept_courses(result < RIVER_SEA_PALETTE, owned)
    result[cleared] = RIVER_LAND_PALETTE
    foreign_river = result < RIVER_SEA_PALETTE
    blocked = foreign_river.copy()
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            blocked |= np.roll(np.roll(foreign_river, dy, 0), dx, 1)
    coast = owned & neighbours_of(water)
    # Rivers keep away from the shoreline and meet the sea only at their mouth.
    shore = distance_transform_edt(~water) <= RIVER_SHORE_CLEARANCE
    border = province_borders(packed)
    paths: list[list[tuple[int, int]]] = []
    for course in RIVER_COURSES:
        if ids is None:
            allowed = owned & border & ~blocked & ~shore
            mouth = owned & ~blocked & coast
            final_extra = owned & border & ~blocked & ~coast
            path = _trace_builder_course(course, allowed, final_extra, mouth, heights, packed, preferred)
        else:
            path = _route_settled_course(
                course, owned, border, blocked, shore, coast, heights, packed, ids, result, avoid, preferred
            )
        for index, (x, y) in enumerate(path):
            result[y, x] = (
                RIVER_SOURCE_PALETTE
                if index == 0
                else river_width_palette(index / len(path), len(path))
            )
            blocked[y - 1 : y + 2, x - 1 : x + 2] = True
        paths.append(path)
    return result, paths


def _route_settled_course(
    course: Sequence[tuple[int, int]],
    owned: np.ndarray,
    border: np.ndarray,
    blocked: np.ndarray,
    shore: np.ndarray,
    coast: np.ndarray,
    heights: np.ndarray,
    packed: np.ndarray,
    ids: np.ndarray,
    rivers: np.ndarray,
    avoid: np.ndarray | None,
    preferred: np.ndarray | None = None,
) -> list[tuple[int, int]]:
    """Route a course clear of ``avoid`` and of pixels that would cut a province apart.

    Where the settlements close every way, the course may pass beside them;
    where every course cuts a province, the first one found stays and the
    river checks report it.
    """
    first = None
    variants = [blocked] if avoid is None else [blocked | avoid, blocked]
    for closed in variants:
        forbidden = np.zeros(owned.shape, bool)
        for _attempt in range(_mon().ROUTE_ATTEMPTS):
            allowed = owned & border & ~closed & ~shore & ~forbidden
            mouth = owned & ~closed & coast & ~forbidden
            final_extra = owned & border & ~closed & ~coast & ~forbidden
            try:
                path = _trace_builder_course(course, allowed, final_extra, mouth, heights, packed, preferred)
            except RuntimeError:
                break
            first = first or path
            cuts = _course_cuts(ids, rivers < RIVER_SEA_PALETTE, path)
            if not cuts.any():
                return path
            forbidden |= cuts
    if first is None:
        raise RuntimeError(f"river from {course[0]} cannot reach the sea along borders")
    return first


def _course_cuts(ids: np.ndarray, river: np.ndarray, path: list[tuple[int, int]]) -> np.ndarray:
    """Course pixels that would cut their province apart, checked in a window round the course."""
    xs = [x for x, _y in path]
    ys = [y for _x, y in path]
    margin = 40
    window = np.s_[
        max(0, min(ys) - margin) : max(ys) + margin + 1,
        max(0, min(xs) - margin) : max(xs) + margin + 1,
    ]
    y0, x0 = window[0].start, window[1].start
    local = [(x - x0, y - y0) for x, y in path]
    result = np.zeros(ids.shape, bool)
    nothing = np.zeros(ids[window].shape, bool)
    result[window] = _mon().cutting_pixels(ids[window], river[window], local, nothing)
    return result


def relief_unit_anchors(
    original: bytes,
    provinces: frozenset[int],
    heights: np.ndarray,
    water: np.ndarray,
) -> bytes:
    """Rest every land unit anchor of a generated-relief province on its surface.

    Anchors over water keep their recorded height: the heightmap there is the
    seabed, not the sea surface naval models float on.
    """
    text = original.decode("utf-8")
    newline = "\r\n" if "\r\n" in text else "\n"
    map_height = heights.shape[0]
    result = []
    for line in text.splitlines():
        row = line.split(";")
        if len(row) >= 5 and row[0].isdigit() and int(row[0]) in provinces:
            x = round(float(row[2]))
            y = map_height - 1 - round(float(row[4]))
            if not water[y, x]:
                row[3] = f"{heights[y, x] / 10:.2f}"
                line = ";".join(row)
        result.append(line)
    return (newline.join(result) + newline).encode("utf-8")


def _grow_compact_region(
    candidates: np.ndarray, anchor: tuple[int, int], size: int
) -> np.ndarray:
    """Take the ``size`` connected pixels nearest to ``anchor`` (y, x)."""
    selected = np.zeros(candidates.shape, bool)
    ay, ax = anchor
    frontier = [(0.0, ay, ax)]
    seen = {(ay, ax)}
    count = 0
    while frontier and count < size:
        _distance, y, x = heapq.heappop(frontier)
        selected[y, x] = True
        count += 1
        for ny, nx in ((y + 1, x), (y - 1, x), (y, x + 1), (y, x - 1)):
            if (ny, nx) in seen or not candidates[ny, nx]:
                continue
            seen.add((ny, nx))
            heapq.heappush(frontier, ((ny - ay) ** 2 + (nx - ax) ** 2, ny, nx))
    return selected


def _geodesic_partition(region: np.ndarray, seeds: list[tuple[int, int]]) -> np.ndarray:
    """Assign region pixels to the nearest seed along 4-connected paths."""
    owner = np.full(region.shape, -1, np.int32)
    queue: deque[tuple[int, int]] = deque()
    for index, (y, x) in enumerate(seeds):
        owner[y, x] = index
        queue.append((y, x))
    while queue:
        y, x = queue.popleft()
        for ny, nx in ((y + 1, x), (y - 1, x), (y, x + 1), (y, x - 1)):
            if region[ny, nx] and owner[ny, nx] < 0:
                owner[ny, nx] = owner[y, x]
                queue.append((ny, nx))
    return owner


def _nearest_member(region: np.ndarray, y: float, x: float) -> tuple[int, int]:
    ys, xs = np.nonzero(region)
    index = int(np.argmin((ys - y) ** 2 + (xs - x) ** 2))
    return int(ys[index]), int(xs[index])


def compact_partition(region: np.ndarray, parts: int) -> np.ndarray:
    """Split a region into compact connected parts (geodesic k-means).

    Detached pieces outside the largest component stay unassigned (-1).
    """
    from scipy.ndimage import label as connected_components

    pieces, count = connected_components(region)
    if count > 1:
        sizes = np.bincount(pieces.ravel())
        sizes[0] = 0
        region = pieces == int(np.argmax(sizes))
    ys, xs = np.nonzero(region)
    cy, cx = ys.mean(), xs.mean()
    first = int(np.argmax((ys - cy) ** 2 + (xs - cx) ** 2))
    seeds = [(int(ys[first]), int(xs[first]))]
    while len(seeds) < parts:
        distance = np.min(
            [(ys - sy) ** 2 + (xs - sx) ** 2 for sy, sx in seeds], axis=0
        )
        index = int(np.argmax(distance))
        seeds.append((int(ys[index]), int(xs[index])))
    owner = _geodesic_partition(region, seeds)
    for _iteration in range(8):
        moved = []
        for index in range(parts):
            part = owner == index
            py, px = np.nonzero(part)
            moved.append(_nearest_member(part, py.mean(), px.mean()))
        if moved == seeds:
            break
        seeds = moved
        owner = _geodesic_partition(region, seeds)
    return owner


def part_sizes(owner: np.ndarray, parts: int) -> np.ndarray:
    return np.bincount(owner[owner >= 0], minlength=parts)


def _relabel_fragments(labels: np.ndarray, editable: np.ndarray) -> None:
    """Merge detached pieces of every province into their main neighbour."""
    from scipy.ndimage import label as connected_components

    for value in np.unique(labels[editable]):
        mask = labels == value
        pieces, count = connected_components(mask)
        if count <= 1:
            continue
        sizes = np.bincount(pieces.ravel())
        sizes[0] = 0
        keep = int(np.argmax(sizes))
        for piece in range(1, count + 1):
            if piece == keep:
                continue
            fragment = pieces == piece
            ring = neighbours_of(fragment) & ~fragment & editable & ~mask
            choices = labels[ring]
            if len(choices):
                labels[fragment] = int(np.bincount(choices).argmax())


def smooth_province_labels(
    labels: np.ndarray, editable: np.ndarray, locked: np.ndarray, sigma: float = 1.6
) -> np.ndarray:
    """Round province borders by an iterated Gaussian majority vote.

    Only editable pixels change and they only take editable province IDs, so
    coastlines and foreign borders stay exact. Locked provinces keep their
    pixels; the vote repeats until it is stable.
    """
    from scipy.ndimage import gaussian_filter

    result = labels.copy()
    values = [int(value) for value in np.unique(result[editable])]
    original_area = {value: int((result == value).sum()) for value in values}
    for _iteration in range(24):
        best = np.full(result.shape, -1.0)
        choice = result.copy()
        for value in values:
            mask = result == value
            ys, xs = np.nonzero(mask)
            y0 = max(0, ys.min() - 6)
            y1 = min(result.shape[0], ys.max() + 7)
            x0 = max(0, xs.min() - 6)
            x1 = min(result.shape[1], xs.max() + 7)
            score = gaussian_filter(mask[y0:y1, x0:x1].astype(float), sigma)
            # Ties keep the current owner.
            score += 1e-6 * mask[y0:y1, x0:x1]
            window = best[y0:y1, x0:x1]
            better = score > window
            window[better] = score[better]
            choice[y0:y1, x0:x1][better] = value
        changed = editable & ~locked & ~np.isin(choice, list(np.unique(result[locked])))
        changed &= choice != result
        if not changed.any():
            break
        previous = result.copy()
        result[changed] = choice[changed]
        _relabel_fragments(result, editable)
        # A province squeezed below 70% of its area is restored and frozen.
        for value in values:
            if (result == value).sum() < 0.7 * original_area[value]:
                restored = previous == value
                result[restored] = value
                locked = locked | restored
        _relabel_fragments(result, editable)
    return result


def remove_four_province_corners(labels: np.ndarray, editable: np.ndarray) -> None:
    """Give one pixel of every four-province corner to a neighbour's province.

    HOI4 rejects a point where four provinces meet diagonally.
    """
    while True:
        a = labels[:-1, :-1]
        b = labels[:-1, 1:]
        c = labels[1:, :-1]
        d = labels[1:, 1:]
        corners = (a != b) & (a != c) & (a != d) & (b != c) & (b != d) & (c != d)
        found = np.argwhere(corners)
        if not len(found):
            return
        for y, x in found:
            for dy, dx, ny, nx in (
                (0, 0, 0, 1),
                (0, 1, 0, 0),
                (1, 0, 1, 1),
                (1, 1, 1, 0),
                (0, 0, 1, 0),
                (1, 0, 0, 0),
                (0, 1, 1, 1),
                (1, 1, 0, 1),
            ):
                if editable[y + dy, x + dx] and editable[y + ny, x + nx]:
                    labels[y + dy, x + dx] = labels[y + ny, x + nx]
                    break
            else:
                raise RuntimeError(f"four-province corner at {(x, y)} has no editable pixel")
        _relabel_fragments(labels, editable)


# A pixel on the line between two scope states joins the state that holds
# this share of the land in the square of this radius round it; passes
# repeat until none moves, at most this many.
STATE_SMOOTHING_RADIUS = 4
STATE_SMOOTHING_SHARE = 0.55
STATE_SMOOTHING_PASSES = 8
STATE_SMOOTHING_MIN_PIXELS = 25
# Pixels this close to land of another geography builder keep their province,
# as that builder keeps its own band beside this geography.
STATE_SMOOTHING_SEAM = 8
_FOUR_STEPS = ((-1, 0), (1, 0), (0, -1), (0, 1))
_EIGHT = np.ones((3, 3), bool)


@dataclass(frozen=True)
class StateSmoothing:
    """New province labels of ``smooth_state_borders`` and what moved."""

    labels: np.ndarray
    moved: int
    passes: int
    pass_moves: tuple[int, ...]
    stable: bool
    state_edges_before: int
    state_edges_after: int
    border_pairs_before: int
    border_pairs_after: int
    transfers: dict[tuple[int, int], int]
    rail_segments: int
    rail_lost: tuple[tuple[int, int], ...]

    def report(self) -> dict:
        return {
            "moved_pixels": self.moved,
            "passes": self.passes,
            "pass_moves": list(self.pass_moves),
            "stable": self.stable,
            "state_edges_before": self.state_edges_before,
            "state_edges_after": self.state_edges_after,
            "border_pairs_before": self.border_pairs_before,
            "border_pairs_after": self.border_pairs_after,
            "border_pair_delta": self.border_pairs_after - self.border_pairs_before,
            "transfers": {
                f"{source}->{target}": count
                for (source, target), count in sorted(self.transfers.items(), key=lambda item: (-item[1], item[0]))
            },
            "rail_segments_checked": self.rail_segments,
            "rail_segments_lost": [list(pair) for pair in self.rail_lost],
        }


def province_states(labels: np.ndarray, state_of: Mapping[int, int]) -> np.ndarray:
    """The state of every pixel; 0 for provinces outside ``state_of``."""
    values, inverse = np.unique(labels, return_inverse=True)
    lookup = np.array([state_of.get(int(value), 0) for value in values], np.int32)
    return lookup[inverse].reshape(labels.shape)


def state_edge_length(states: np.ndarray, scope_states: frozenset[int]) -> int:
    """Pixel edges between two different scope states."""
    inside = np.isin(states, sorted(scope_states))
    total = 0
    for first, second, a, b in (
        (states[:, :-1], states[:, 1:], inside[:, :-1], inside[:, 1:]),
        (states[:-1], states[1:], inside[:-1], inside[1:]),
    ):
        total += int((a & b & (first != second)).sum())
    return total


def province_contacts(labels: np.ndarray) -> Counter[tuple[int, int]]:
    """Pixel edges between every pair of touching provinces, keyed by (low, high) id."""
    keys = []
    for first, second in ((labels[:, :-1], labels[:, 1:]), (labels[:-1], labels[1:])):
        differs = first != second
        low = np.minimum(first[differs], second[differs]).astype(np.int64)
        high = np.maximum(first[differs], second[differs]).astype(np.int64)
        keys.append((low << 32) | high)
    values, counts = np.unique(np.concatenate(keys), return_counts=True)
    return Counter(
        {(int(value >> 32), int(value & 0xFFFFFFFF)): int(count) for value, count in zip(values, counts)}
    )


def state_line_pixels(states: np.ndarray, land: np.ndarray) -> np.ndarray:
    """Land pixels with land of another state across a pixel edge; state 0 is land of no listed state."""
    result = np.zeros(states.shape, bool)
    for first, second in ((np.s_[:, :-1], np.s_[:, 1:]), (np.s_[:-1], np.s_[1:])):
        differs = (states[first] != states[second]) & land[first] & land[second]
        result[first] |= differs
        result[second] |= differs
    return result


def interior_river_pixels_by_state(
    river: np.ndarray, states: np.ndarray, land: np.ndarray, scope_states: frozenset[int]
) -> dict[int, int]:
    """River pixels of each scope state with no land of another state across a pixel edge.

    Water beside a mouth is no state line; such a pixel counts as interior
    unless land of another state touches it too.
    """
    interior = river & land & ~state_line_pixels(states, land) & np.isin(states, sorted(scope_states))
    return {int(state): int(count) for state, count in sorted(Counter(states[interior].tolist()).items())}


def _keeps_connected(labels: np.ndarray, river: np.ndarray, y: int, x: int, province: int) -> bool:
    """Whether ``province`` and its land off the river keep their pieces without pixel (y, x).

    The pixels round (y, x) decide most cases: when its neighbours in the
    province join within that ring, no path is lost. Otherwise the pieces
    are counted in the province's box.
    """
    ring = (labels[y - 1 : y + 2, x - 1 : x + 2] == province) & ~river[y - 1 : y + 2, x - 1 : x + 2]
    ring[1, 1] = False
    sides = [(1 + dy, 1 + dx) for dy, dx in _FOUR_STEPS if ring[1 + dy, 1 + dx]]
    if len(sides) <= 1:
        return True
    pieces, _count = label(ring)
    if len({int(pieces[side]) for side in sides}) == 1:
        return True
    ys, xs = np.nonzero(labels == province)
    box = np.s_[ys.min() : ys.max() + 1, xs.min() : xs.max() + 1]
    whole = labels[box] == province
    for mask in (whole, whole & ~river[box]):
        before = label(mask)[1]
        mask = mask.copy()
        mask[y - box[0].start, x - box[1].start] = False
        if label(mask)[1] > before:
            return False
    return True


def _closes_four_corner(labels: np.ndarray, y: int, x: int, value: int) -> bool:
    """Whether giving (y, x) to ``value`` makes four provinces meet in a 2x2 square."""
    for top in (y - 1, y):
        for left in (x - 1, x):
            if top < 0 or left < 0 or top + 2 > labels.shape[0] or left + 2 > labels.shape[1]:
                continue
            block = labels[top : top + 2, left : left + 2].copy()
            block[y - top, x - left] = value
            if len(set(block.ravel().tolist())) == 4:
                return True
    return False


def _roundness_holds(labels: np.ndarray, province: int, y: int, x: int, value: int, minimum: float) -> bool:
    """Whether ``province`` stays at least ``minimum`` round, or rounder than now, once (y, x) is ``value``."""
    mon = _mon()
    ys, xs = np.nonzero(labels == province)
    box = np.s_[
        min(int(ys.min()), y) : max(int(ys.max()), y) + 1,
        min(int(xs.min()), x) : max(int(xs.max()), x) + 1,
    ]
    before = labels[box] == province
    after = labels[box].copy()
    after[y - box[0].start, x - box[1].start] = value
    after = after == province
    if not after.any():
        return False
    shape = mon.roundness(after)
    return shape >= minimum or shape >= mon.roundness(before)


def smooth_state_borders(
    labels: np.ndarray,
    state_of: Mapping[int, int],
    scope_states: frozenset[int],
    land: np.ndarray,
    river: np.ndarray,
    *,
    settlements: frozenset[int] = frozenset(),
    frozen: np.ndarray | None = None,
    rail_pairs: frozenset[tuple[int, int]] | set[tuple[int, int]] = frozenset(),
    min_pixels: Mapping[int, int] | None = None,
    min_roundness: Mapping[int, float] | None = None,
    radius: int = STATE_SMOOTHING_RADIUS,
    share: float = STATE_SMOOTHING_SHARE,
    passes: int = STATE_SMOOTHING_PASSES,
) -> StateSmoothing:
    """Smooth the land lines between the scope states of a window of province ids.

    A land pixel with a 4-neighbour in another scope state joins the state
    that holds at least ``share`` of the land pixels in the square of
    ``radius`` round it, through the 4-neighbouring province of that state
    it touches most. Passes run in raster order with every move applied at
    once, until a pass moves nothing or ``passes`` have run; ``stable``
    tells whether one more pass would still move a pixel.

    Never moved: pixels outside the scope states, river pixels and the
    pixels round them, pixels of ``settlements`` and the pixels round them,
    land beside water, ``frozen`` pixels and pixels closer than ``radius``
    to the window edge. A move is refused when it would split its province
    or its land off the river, leave it under ``min_pixels`` (default
    STATE_SMOOTHING_MIN_PIXELS), make a ``min_roundness`` province less
    round than its limit and than before, close a four-province 2x2 square,
    or remove the last contact of a ``rail_pairs`` segment or of two
    provinces of one state. Provinces never change state; only their
    pixels move.
    """
    result = labels.astype(np.int32, copy=True)
    height, width = result.shape
    states = province_states(result, state_of)
    states_before = states.copy()
    inside = np.isin(states, sorted(scope_states)) & land
    river = river & land
    edge = np.zeros(result.shape, bool)
    edge[radius : height - radius, radius : width - radius] = True
    protected = ~inside | ~edge
    protected |= binary_dilation(river, _EIGHT)
    protected |= binary_dilation(~land, _EIGHT)
    if settlements:
        protected |= binary_dilation(np.isin(result, sorted(settlements)), _EIGHT)
    if frozen is not None:
        protected |= frozen
    sizes = Counter(result.ravel().tolist())
    contacts = province_contacts(result)
    rails = {(min(a, b), max(a, b)) for a, b in rail_pairs}
    minimum = min_pixels or {}
    shapes = min_roundness or {}
    edges_before = state_edge_length(states, scope_states)
    pairs_before = len(contacts)
    rail_checked = sorted(pair for pair in rails if contacts.get(pair))

    def kept_contact(pair: tuple[int, int]) -> bool:
        """Railway segments and provinces of one state keep at least one pixel edge."""
        state = state_of.get(pair[0], 0)
        return pair in rails or (state != 0 and state == state_of.get(pair[1], 0))

    pass_moves = []
    stable = False
    # The pass after the last one that may move pixels only looks for a move.
    for run in range(passes + 1):
        committing = run < passes
        border = np.zeros(result.shape, bool)
        for first, second in ((np.s_[:, :-1], np.s_[:, 1:]), (np.s_[:-1], np.s_[1:])):
            differs = (states[first] != states[second]) & inside[first] & inside[second]
            border[first] |= differs
            border[second] |= differs
        changes = 0
        for y, x in np.argwhere(border & ~protected).tolist():
            own = int(states[y, x])
            if not any(
                inside[y + dy, x + dx] and states[y + dy, x + dx] != own for dy, dx in _FOUR_STEPS
            ):
                continue
            box = np.s_[y - radius : y + radius + 1, x - radius : x + radius + 1]
            votes = land[box].copy()
            votes[radius, radius] = False
            values, counts = np.unique(states[box][votes], return_counts=True)
            if not len(values):
                continue
            best = int(values[int(np.argmax(counts))])
            if best == own or best not in scope_states or counts.max() < share * counts.sum():
                continue
            touching = Counter(
                int(result[y + dy, x + dx]) for dy, dx in _FOUR_STEPS if states[y + dy, x + dx] == best
            )
            target = min(touching, key=lambda province: (-touching[province], province))
            source = int(result[y, x])
            if sizes[source] - 1 < max(STATE_SMOOTHING_MIN_PIXELS, minimum.get(source, 0)):
                continue
            if not _keeps_connected(result, river, y, x, source):
                continue
            if _closes_four_corner(result, y, x, target):
                continue
            if any(
                province in shapes and not _roundness_holds(result, province, y, x, target, shapes[province])
                for province in (source, target)
            ):
                continue
            delta: Counter[tuple[int, int]] = Counter()
            for dy, dx in _FOUR_STEPS:
                other = int(result[y + dy, x + dx])
                if other != source:
                    delta[(min(source, other), max(source, other))] -= 1
                if other != target:
                    delta[(min(target, other), max(target, other))] += 1
            if any(change < 0 and contacts[pair] + change <= 0 and kept_contact(pair) for pair, change in delta.items()):
                continue
            if not committing:
                changes += 1
                break
            result[y, x] = target
            states[y, x] = best
            sizes[source] -= 1
            sizes[target] += 1
            for pair, change in delta.items():
                contacts[pair] += change
            changes += 1
        if not changes:
            stable = True
            break
        if committing:
            pass_moves.append(changes)
    after = province_contacts(result)
    lost = tuple(pair for pair in rail_checked if not after.get(pair))
    changed = result != labels
    crossed = states_before != states
    transfers = Counter(zip(states_before[crossed].tolist(), states[crossed].tolist()))
    return StateSmoothing(
        labels=result,
        moved=int(changed.sum()),
        passes=len(pass_moves),
        pass_moves=tuple(pass_moves),
        stable=stable,
        state_edges_before=edges_before,
        state_edges_after=state_edge_length(states, scope_states),
        border_pairs_before=pairs_before,
        border_pairs_after=len(after),
        transfers=dict(transfers),
        rail_segments=len(rail_checked),
        rail_lost=lost,
    )


def province_colour(province_id: int, used: set[tuple[int, int, int]]) -> tuple[int, int, int]:
    salt = 0
    while True:
        value = stable_unit_hash(province_id, 7919, salt)
        packed = int(value * 0xFFFFFF) | 0x101010
        colour = ((packed >> 16) & 255, (packed >> 8) & 255, packed & 255)
        if colour not in used:
            used.add(colour)
            return colour
        salt += 1


def _assign_to_neighbours(
    labels: np.ndarray, area: np.ndarray, excluded: set[int]
) -> None:
    """Give each connected piece of ``area`` to its most common neighbour."""
    from scipy.ndimage import label as connected_components

    pieces, count = connected_components(area)
    for piece in range(1, count + 1):
        fragment = pieces == piece
        ring = labels[neighbours_of(fragment) & ~fragment]
        ring = ring[(ring > 0) & ~np.isin(ring, list(excluded))]
        if len(ring):
            labels[fragment] = int(np.bincount(ring).argmax())


def carve_junction_city(
    labels: np.ndarray,
    donors: np.ndarray,
    region: np.ndarray,
    hint: tuple[float, float],
    relocate: bool = False,
    shore: np.ndarray | None = None,
) -> np.ndarray:
    """Place a city where several provinces meet, close to its old site.

    A relocated city may stand outside ``region``; otherwise the junction is
    chosen inside it. With ``shore`` the city keeps a harbour front: its site
    is chosen among those shore pixels when the region has any.

    The city takes pixels from every province it touches, so it borders at
    least CITY_MIN_NEIGHBOURS provinces instead of sitting inside one.
    Donors keep most of their area.
    """
    from scipy.ndimage import binary_dilation

    radius = CITY_JUNCTION_RADIUS
    disk = np.hypot(*np.mgrid[-radius : radius + 1, -radius : radius + 1]) <= radius
    margin = max(3 * radius, CITY_SITE_DISTANCE + radius)
    ys, xs = np.nonzero(region)
    y0 = max(0, ys.min() - margin)
    y1 = min(labels.shape[0], ys.max() + margin + 1)
    x0 = max(0, xs.min() - margin)
    x1 = min(labels.shape[1], xs.max() + margin + 1)
    window = labels[y0:y1, x0:x1]
    window_donors = donors[y0:y1, x0:x1]
    # A relocated city's former province dissolves, so it is no neighbour.
    former = set(np.unique(labels[region]).tolist()) if relocate else set()
    reach = np.zeros(window.shape, np.int32)
    for value in np.unique(window[window_donors]):
        if int(value) not in former:
            reach += binary_dilation(window_donors & (window == value), structure=disk)
    gy, gx = np.mgrid[y0:y1, x0:x1]
    distance = np.hypot(gy - hint[0], gx - hint[1])
    site = window_donors if relocate else region[y0:y1, x0:x1] & window_donors
    if shore is not None and (site & shore[y0:y1, x0:x1]).any():
        site = site & shore[y0:y1, x0:x1]
    candidates = site & (distance <= CITY_SITE_DISTANCE)
    if not candidates.any():
        candidates = site
    if shore is not None and not (candidates & (reach >= CITY_MIN_NEIGHBOURS)).any():
        # A port town without a coastal junction on its own shore moves to the
        # nearest one on the neighbouring coast.
        coast = window_donors & shore[y0:y1, x0:x1]
        junctions = coast & (reach >= CITY_MIN_NEIGHBOURS)
        candidates = junctions if junctions.any() else coast
    score = np.where(
        candidates,
        np.minimum(reach, CITY_MIN_NEIGHBOURS + 1) * 10.0 - distance / 3.0,
        -np.inf,
    )
    ay, ax = np.unravel_index(int(np.argmax(score)), score.shape)
    anchor = (int(ay) + y0, int(ax) + x0)
    allowed = donors.copy()
    for _attempt in range(8):
        city = _grow_compact_region(allowed, anchor, CITY_PIXELS)
        shrunk = [
            int(value)
            for value in np.unique(labels[city])
            if (labels[city] == value).sum()
            > (1.0 - CITY_DONOR_SHARE) * (labels == value).sum()
        ]
        if not shrunk:
            return city
        allowed &= ~np.isin(labels, shrunk) | region
    return city


def plan_province_geometry(state_ids: frozenset[int], settlements: frozenset[int]) -> None:
    """Add the province geometry of ``state_ids`` to the reviewed geometry data.

    Victory points in ``settlements`` become whole urban provinces: small
    city provinces are kept whole, larger ones yield a compact city and a
    rural remainder. Giant or ragged provinces are split, then every internal
    border is smoothed; borders that carry a river keep their course. States
    already in the stored geometry are refused, so the reviewed geometry is
    never replanned from a map that already carries it. The result is stored
    as data so the map pass only stamps it.
    """
    from tools.builders import build_adiscord_new_states as states

    manifest = json.loads(PROVINCE_MANIFEST_PATH.read_text(encoding="utf-8"))
    state_by_province = {
        province: state_id
        for state_id in state_ids
        for province in states.IVANLAND_OVERHAUL_PROVINCES[state_id]
    }
    scoped = frozenset(state_by_province)
    planned_states = {int(entry["state"]) for entry in manifest["provinces"]}
    planned_parents = {int(parent) for parent in manifest["cities"]}
    if planned_states & state_ids or planned_parents & scoped:
        raise RuntimeError(
            f"states {sorted(state_ids)} already have reviewed province geometry"
        )
    if has_stage2_plan(manifest):
        raise RuntimeError("the Stage 2 plan exists: the Stage 1 geometry is closed")
    if not settlements <= scoped:
        raise RuntimeError(
            f"settlements outside the planned states: {sorted(settlements - scoped)}"
        )

    rows = [
        line.split(";")
        for line in DEFINITION_PATH.read_text(encoding="utf-8-sig").splitlines()
        if line[:1].isdigit()
    ]
    colours = {int(row[0]): (int(row[1]), int(row[2]), int(row[3])) for row in rows}
    used = set(colours.values())
    next_id = max(colours) + 1
    sea = {int(row[0]) for row in rows if row[4] != "land"}

    with Image.open(PROVINCES_PATH) as source:
        province_rgb = np.asarray(source.convert("RGB"))
    with Image.open(TERRAIN_PATH) as source:
        terrain = np.asarray(source)
    with Image.open(RIVERS_PATH) as source:
        rivers = np.asarray(source)
    packed = packed_rgb(province_rgb)
    lookup = {
        (red << 16) | (green << 8) | blue: province
        for province, (red, green, blue) in colours.items()
    }
    scope = province_mask(packed, colours, scoped)
    ys, xs = np.nonzero(scope)
    y0, y1 = int(ys.min()) - 8, int(ys.max()) + 9
    x0, x1 = int(xs.min()) - 8, int(xs.max()) + 9
    crop = (slice(y0, y1), slice(x0, x1))
    keys = packed[crop]
    labels = np.zeros(keys.shape, np.int32)
    for key in np.unique(keys):
        labels[keys == key] = lookup.get(int(key), 0)
    editable = np.isin(labels, list(scoped))
    water = np.isin(labels, list(sea))
    # Both banks of a river stay with their provinces, so the river keeps
    # running along a province border.
    river = rivers[crop] < RIVER_SEA_PALETTE
    river_banks = river | neighbours_of(river)
    shore = neighbours_of(water) & ~water

    entries: list[dict[str, object]] = []
    cities: dict[int, int] = {}

    def new_province(parent: int, kind: str) -> int:
        nonlocal next_id
        province = next_id
        next_id += 1
        state_by_province[province] = state_by_province[parent]
        entries.append(
            {
                "province": province,
                "parent": parent,
                "state": state_by_province[parent],
                "kind": kind,
                "rgb": list(province_colour(province, used)),
            }
        )
        return province

    for parent in sorted(settlements):
        region = labels == parent
        area = int(region.sum())
        urban = region & (terrain[crop] == URBAN_PALETTE)
        hint_source = urban if urban.sum() >= 6 else region
        hy, hx = np.nonzero(hint_source)
        donors = (
            np.isin(labels, list(scoped))
            & ~water
            & ~np.isin(labels, [*cities.values(), *settlements])
        )
        donors |= region & ~water
        donors &= ~river_banks
        if area <= CITY_WHOLE_PROVINCE_PIXELS:
            touching = labels[neighbours_of(region) & ~region & ~water]
            touching = touching[(touching > 0) & ~np.isin(touching, list(sea))]
            if len(set(touching.tolist())) >= CITY_MIN_NEIGHBOURS:
                cities[parent] = parent
                continue
            # A small city with too few neighbours moves onto the nearest
            # junction; its former outskirts join the adjacent provinces.
            city_pixels = carve_junction_city(
                labels, donors, region, (hy.mean(), hx.mean()), relocate=True
            )
            outskirts = region & ~city_pixels
            labels[city_pixels] = parent
            _assign_to_neighbours(labels, outskirts, {parent} | sea)
            cities[parent] = parent
            continue
        # A coastal town stays a port.
        city_pixels = carve_junction_city(
            labels,
            donors,
            region,
            (hy.mean(), hx.mean()),
            shore=shore if (region & shore).any() else None,
        )
        city = new_province(parent, "city")
        labels[city_pixels] = city
        cities[parent] = city

    for parent in sorted(int(value) for value in np.unique(labels[editable])):
        if parent in cities.values():
            continue
        region = labels == parent
        area = int(region.sum())
        ry, rx = np.nonzero(region)
        sub = region[ry.min() - 1 : ry.max() + 2, rx.min() - 1 : rx.max() + 2]
        perimeter = int((sub[:, 1:] != sub[:, :-1]).sum() + (sub[1:, :] != sub[:-1, :]).sum())
        compactness = 4 * pi * area / perimeter**2
        if area <= SPLIT_PIXELS and not (compactness < 0.3 and area > 200):
            continue
        parts = max(2, round(area / SPLIT_PART_PIXELS))
        owner = compact_partition(region, parts)
        # Fewer parts replace a split that would leave a sliver.
        while parts > 2 and part_sizes(owner, parts).min() < SPLIT_MIN_PART_PIXELS:
            parts -= 1
            owner = compact_partition(region, parts)
        if part_sizes(owner, parts).min() < SPLIT_MIN_PART_PIXELS:
            continue
        keep = int(np.bincount(owner[owner >= 0]).argmax())
        for index in range(parts):
            if index != keep:
                labels[owner == index] = new_province(parent, "split")

    editable = labels > 0
    editable &= ~water & np.isin(
        labels, list(scoped | {int(entry["province"]) for entry in entries})
    )
    # Cities and very small provinces keep their exact outline.
    small = [
        int(value)
        for value in np.unique(labels[editable])
        if (labels == value).sum() < LOCKED_PROVINCE_PIXELS
    ]
    locked = np.isin(labels, list(set(cities.values()) | set(small)))
    labels = smooth_province_labels(labels, editable, locked | river_banks)
    remove_four_province_corners(labels, editable & ~locked)

    palette = {province: colour for province, colour in colours.items()}
    palette.update({int(entry["province"]): tuple(entry["rgb"]) for entry in entries})
    image = np.zeros((*labels.shape, 4), np.uint8)
    for value in np.unique(labels[editable]):
        mask = editable & (labels == value)
        image[mask, :3] = palette[int(value)]
        image[mask, 3] = 255

    # The stored canvas grows to cover both the reviewed and the new geometry.
    with Image.open(PROVINCE_GEOMETRY_PATH) as source:
        stored = np.asarray(source.convert("RGBA"))
    stored_x, stored_y = manifest["origin"]
    left = min(stored_x, x0)
    top = min(stored_y, y0)
    right = max(stored_x + stored.shape[1], x1)
    bottom = max(stored_y + stored.shape[0], y1)
    canvas = np.zeros((bottom - top, right - left, 4), np.uint8)
    canvas[
        stored_y - top : stored_y - top + stored.shape[0],
        stored_x - left : stored_x - left + stored.shape[1],
    ] = stored
    window = canvas[y0 - top : y1 - top, x0 - left : x1 - left]
    if (window[..., 3][editable] > 0).any():
        raise RuntimeError("new province geometry overlaps the reviewed geometry")
    window[editable] = image[editable]
    Image.fromarray(canvas).save(PROVINCE_GEOMETRY_PATH, optimize=True)
    manifest["origin"] = [left, top]
    manifest["provinces"] = [*manifest["provinces"], *entries]
    manifest["cities"] = {
        str(parent): city
        for parent, city in sorted(
            {
                **{int(parent): city for parent, city in manifest["cities"].items()},
                **cities,
            }.items()
        )
    }
    PROVINCE_MANIFEST_PATH.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


# --- Stage 2: smaller rural provinces, a city in every state and a town in each ---

STAGE2_SPLIT_THRESHOLD = 180
STAGE2_PART_PIXELS = 100
STAGE2_PART_MIN_PIXELS = 50
STAGE2_PART_MIN_ROUNDNESS = 0.35
STAGE2_CITY_SIZE = (40, 50)
STAGE2_TOWN_SIZE = (30, 40)
STAGE2_TOWN_PIXELS = 35
STAGE2_TOWN_MIN_NEIGHBOURS = 2
STAGE2_TOWN_MIN_PARENT = 90
STAGE2_CITY_MIN_PARENT = 90
STAGE2_TOWN_REMAINDER_PIXELS = 50
STAGE2_REMAINDER_PIXELS = 60
# A town keeps at least this distance from every city and town of the scope
# and prefers about the target distance.
STAGE2_TOWN_CITY_DISTANCE = 10.0
STAGE2_TOWN_TARGET_DISTANCE = 22.0
STAGE2_WINDOW_MARGIN = 40
# The engine accepts at most this many adjacent province pairs; a plan
# leaves at least the margin free.
BORDER_BUDGET = 65536
BORDER_MARGIN = 2000
# The port towns of the island administration, Nordholm with its garrison
# among them, keep their reviewed geometry.
STAGE2_FIXED_PROVINCES = frozenset({18993, 18994})
STAGE2_NAVAL_BASES = frozenset({2553, 10730, 11841, 16568, 18994})
NATIVE_RIVER_WIDTHS = (3, 4, 6, 7, 9, 10, 11)
FORBIDDEN_RIVER_WIDTHS = {5: 4, 8: 7}
RIVER_FLOW_IN_PALETTE = 1
RIVER_WIDTH_ROUNDS = 8
# Courses are walked in a window this far round the scope, so the walks that
# reach the scope start at their own markers.
RIVER_WALK_MARGIN = 30
STAGE2_REPORT_NAME = "ivn_stage2_plan_report.json"
STAGE2_PREVIEW_SCALE = 3


@dataclass(frozen=True)
class PlannedSettlement:
    state: int
    kind: str
    name: str
    name_en: str
    value: int
    parent: int | None = None


# Proposed settlements of the Stage 2 plan; the names follow the state and
# victory-point names of each state and were checked against every
# localisation file. State 713 has no city province: its victory point
# Pushchansk becomes its city.
STAGE2_SETTLEMENTS = (
    PlannedSettlement(713, "city", "Пущанск", "Pushchansk", 3, parent=8615),
    PlannedSettlement(25, "town", "Марьин Брод", "Maryin Brod", 2),
    PlannedSettlement(92, "town", "Серенжский Перевоз", "Serenga Ferry", 1),
    PlannedSettlement(95, "town", "Ведринка", "Vedrinka", 1),
    PlannedSettlement(96, "town", "Таларские Мельницы", "Talara Mills", 1),
    PlannedSettlement(97, "town", "Нижняя Кантория", "Lower Kantoriya", 1),
    PlannedSettlement(98, "town", "Малая Моресса", "Little Moressa", 2),
    PlannedSettlement(99, "town", "Лакорский Брод", "Lakora Ford", 2),
    PlannedSettlement(100, "town", "Ильванка", "Ilvanka", 2),
    PlannedSettlement(101, "town", "Верхняя Ольсия", "Upper Olsiya", 1),
    PlannedSettlement(127, "town", "Северомарск", "Severomarsk", 1),
    PlannedSettlement(128, "town", "Фьельстад", "Fjelstad", 1),
    PlannedSettlement(129, "town", "Кордонная Слобода", "Cordon Sloboda", 1),
    PlannedSettlement(130, "town", "Сторожевое", "Storozhevoye", 1),
    PlannedSettlement(131, "town", "Ямщиково", "Yamshchikovo", 1),
    PlannedSettlement(132, "town", "Закатное", "Zakatnoye", 1),
    PlannedSettlement(164, "town", "Восходное", "Voskhodnoye", 1),
    PlannedSettlement(693, "town", "Рейдальсвик", "Reydalsvik", 2),
    PlannedSettlement(694, "town", "Кайрстранд", "Kairstrand", 1),
    PlannedSettlement(695, "town", "Истоково", "Istokovo", 1),
    PlannedSettlement(696, "town", "Восточномарск", "Vostochnomarsk", 1),
    PlannedSettlement(697, "town", "Порубежное", "Porubezhnoye", 1),
    PlannedSettlement(698, "town", "Полуденное", "Poludennoye", 1),
    PlannedSettlement(713, "town", "Боровое", "Borovoye", 1),
    PlannedSettlement(714, "town", "Дюнное", "Dyunnoye", 1),
    PlannedSettlement(715, "town", "Причальное", "Prichalnoye", 1),
    PlannedSettlement(716, "town", "Межмарье", "Mezhmarye", 1),
    PlannedSettlement(717, "town", "Клюквенное", "Klyukvennoye", 1),
)


def _mon():
    """The Montar geography builder, whose carving, partition and river rules Stage 2 shares.

    It imports this module at load time, so it is imported on use.
    """
    from tools.builders import build_adiscord_mon_geography

    return build_adiscord_mon_geography


def _coastal():
    """The coastal geography builder: province grids, border counts and native unit anchors."""
    from tools.builders import build_adiscord_coastal_geography

    return build_adiscord_coastal_geography


def unit_locations(root: Path) -> frozenset[int]:
    """Provinces that any starting order of battle names as a location."""
    result: set[int] = set()
    for path in sorted((root / "history/units").glob("*.txt")):
        text = path.read_text(encoding="utf-8-sig", errors="replace")
        result.update(int(value) for value in re.findall(r"\blocation\s*=\s*(\d+)", text))
    return frozenset(result)


def stage2_literals(root: Path, scope: frozenset[int]) -> frozenset[int]:
    """Scope provinces named by id: naval bases, unit locations, ports and supply hubs."""
    from tools.builders.build_adiscord_vorkerland_theatre import (
        ITORA_CAPITAL_PROVINCE,
        ITORA_SUPPLY_HUB_STATES,
    )
    from tools.lib.adiscord_starting_navies import STARTING_NAVIES

    ports = {navy.port for navy in STARTING_NAVIES.values()}
    named = (
        STAGE2_NAVAL_BASES
        | unit_locations(root)
        | ports
        | supply_hubs(root)
        | {ITORA_CAPITAL_PROVINCE}
        | set(ITORA_SUPPLY_HUB_STATES)
    )
    return frozenset(named) & scope


def supply_hubs(root: Path) -> frozenset[int]:
    """Provinces holding a supply hub on the starting map."""
    lines = (root / "map/supply_nodes.txt").read_text(encoding="utf-8-sig").splitlines()
    return frozenset(int(fields[1]) for fields in (line.split() for line in lines) if len(fields) > 1)


def state_victory_points(state_ids: frozenset[int]) -> dict[int, int]:
    result: dict[int, int] = {}
    for state_id in sorted(state_ids):
        source = state_path(state_id).read_text(encoding="utf-8-sig")
        for province, value in re.findall(r"\bvictory_points\s*=\s*\{\s*(\d+)\s+(\d+)", source):
            result[int(province)] = int(value)
    return result


def slot_points(unitstacks: bytes, map_height: int, slot: int) -> dict[int, tuple[int, int]]:
    """Map pixel (x, row) of one unit-anchor slot of every province."""
    points = {}
    for line in unitstacks.decode("utf-8").splitlines():
        row = line.split(";")
        if len(row) > 4 and row[1] == str(slot):
            points[int(row[0])] = (round(float(row[2])), map_height - 1 - round(float(row[4])))
    return points


def supply_node_points(grid: np.ndarray, root: Path) -> dict[int, list[tuple[int, int]]]:
    """Map pixels (x, row) of the supply-hub models of the hub provinces.

    buildings.txt places a hub model in nearly every province; only the
    provinces of supply_nodes.txt hold a hub.
    """
    hubs = supply_hubs(root)
    result: dict[int, list[tuple[int, int]]] = defaultdict(list)
    path = root / "map/buildings.txt"
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        fields = line.split(";")
        if len(fields) < 5 or fields[1] != "supply_node":
            continue
        x = round(float(fields[2]))
        y = grid.shape[0] - 1 - round(float(fields[4]))
        if int(grid[y, x]) in hubs:
            result[int(grid[y, x])].append((x, y))
    return result


def settlement_name_collisions(root: Path, settlements: Sequence[PlannedSettlement]) -> list[str]:
    """Planned names that are already the full value of another localisation key.

    An existing victory point that becomes a city keeps its own name, and a
    settlement's own victory-point key holds its name once the plan applies.
    """
    values: list[tuple[str, str]] = []
    for path in sorted((root / "localisation").rglob("*.yml")):
        text = path.read_text(encoding="utf-8-sig", errors="replace")
        values += re.findall(r'(?m)^[ 	]*([\w.-]+):\d*[ 	]*"([^"]*)"', text)
    own_keys = {
        name: f"VICTORY_POINTS_{entry['province']}"
        for entry in stage2_plan(PROVINCE_MANIFEST).get("settlements", [])
        for name in (entry["name"], entry["name_en"])
    }
    issues = []
    for settlement in settlements:
        if settlement.parent is not None:
            continue
        for name in (settlement.name, settlement.name_en):
            if any(value == name and key != own_keys.get(name) for key, value in values):
                issues.append(f"settlement name {name} is already used in the localisation")
    return issues


class Stage2Planner:
    """Carve the Stage 2 settlements and split the large rural provinces of IVN and IIA.

    It works on a window of the map Stage 1 left. Settlements come first, so
    no split cuts a city or a town; then every large rural province is split.
    New ids follow in that order from the first free id. A carved city keeps
    the id of its parent and the rest becomes a remainder. A town takes a new
    id and its parent keeps the rest, so a province named by script, units or
    railways stays the rural province it was.
    """

    def __init__(self, manifest: dict) -> None:
        mon = _mon()
        coastal = _coastal()
        if has_stage2_plan(manifest):
            raise RuntimeError(
                "the IVN Stage 2 plan exists: restore the pre-apply map and remove stage2 first"
            )
        self.manifest = manifest
        rows = [
            line.split(";")
            for line in DEFINITION_PATH.read_text(encoding="utf-8-sig").splitlines()
            if line[:1].isdigit()
        ]
        self.colours = {int(row[0]): (int(row[1]), int(row[2]), int(row[3])) for row in rows}
        self.kinds = {int(row[0]): row[4] for row in rows}
        if any(int(entry["province"]) not in self.colours for entry in manifest["provinces"]):
            raise RuntimeError("apply the Stage 1 plan before planning Stage 2")
        self.used = set(self.colours.values())
        self.first_id = max(self.colours) + 1
        with Image.open(BytesIO(PROVINCES_PATH.read_bytes())) as source:
            self.grid = coastal.province_grid(np.asarray(source.convert("RGB")), self.colours)
        self.state_of = province_state_contract(SCOPED_STATE_IDS)
        self.scope_before = dict(self.state_of)
        ys, xs = np.nonzero(np.isin(self.grid, sorted(self.state_of)))
        margin = STAGE2_WINDOW_MARGIN
        self.window = mon.Window(
            max(0, int(ys.min()) - margin),
            min(self.grid.shape[0], int(ys.max()) + margin + 1),
            max(0, int(xs.min()) - margin),
            min(self.grid.shape[1], int(xs.max()) + margin + 1),
        )
        self.labels = self.grid[self.window.s].astype(np.int32)
        self.original = self.labels.copy()
        self.water = np.isin(
            self.labels, [province for province, kind in self.kinds.items() if kind in ("sea", "lake")]
        )
        self.sea = np.isin(self.labels, [province for province, kind in self.kinds.items() if kind == "sea"])
        self.shore = neighbours_of(self.water) & ~self.water
        with Image.open(BytesIO(RIVERS_PATH.read_bytes())) as source:
            self.river = mon.river_masks(np.asarray(source)[self.window.s], self.water)
        # Both banks of a river keep their provinces, so it keeps running on a border.
        self.locked = self.river | neighbours_of(self.river) | self.water
        self.banks = neighbours_of(self.river)
        root = MAP_ROOT
        self.pairs = mon.rail_pairs(root)
        self.on_rail = {province for pair in self.pairs for province in pair}
        scope = frozenset(self.state_of)
        self.settled = set(SETTLEMENT_PROVINCES & scope) | set(STAGE2_FIXED_PROVINCES)
        # The coastal builder repairs single pixels of these provinces by id.
        self.foreign = coastal.PROVINCE_REPAIR_PROVINCES & scope
        self.literals = stage2_literals(root, scope)
        self.victory_points = state_victory_points(SCOPED_STATE_IDS)
        unitstacks = UNITSTACKS_PATH.read_bytes()
        self.anchors = {
            slot: slot_points(unitstacks, self.grid.shape[0], slot) for slot in (0, 38)
        }
        self.hubs = supply_node_points(self.grid, root)
        self.entries: list[dict] = []
        self.cities: list[int] = []
        self.towns: dict[int, int] = {}
        self.settlements: list[dict] = []
        self.splits: dict[int, list[int]] = {}
        self.failed_splits: list[dict] = []
        self.coastal_kept: list[int] = []
        self.rail_losses: list[dict] = []
        # This builder routes its own courses anew on every pass in this land.
        routed_ids = relief_province_ids(RELIEF_STATE_IDS) - AUTHORED_RIVER_PROVINCES
        self.routed = np.isin(self.original, sorted(routed_ids))
        self.mended = 0
        self.unmended: list[dict] = []

    # Province bookkeeping

    def new_id(self) -> int:
        return self.first_id + len(self.entries)

    def add_entry(self, province: int, parent: int, kind: str) -> None:
        state_id = self.state_of[parent]
        self.entries.append({"province": province, "parent": parent, "state": state_id, "kind": kind})
        self.state_of[province] = state_id

    def planned_ids(self) -> set[int]:
        return {int(entry["province"]) for entry in self.entries}

    def members(self, state_id: int) -> list[int]:
        return sorted(province for province, owner in self.state_of.items() if owner == state_id)

    def mask(self, province: int) -> np.ndarray:
        return self.labels == province

    def size(self, province: int) -> int:
        return int(self.mask(province).sum())

    def centre(self, province: int) -> tuple[int, int]:
        """The deepest pixel of a province in window coordinates (y, x)."""
        ys, xs = np.nonzero(self.mask(province))
        y0, x0 = int(ys.min()), int(xs.min())
        y, x = _mon().interior_point(self.labels[y0 : ys.max() + 1, x0 : xs.max() + 1] == province)
        return y + y0, x + x0

    def touches_sea(self, province: int) -> bool:
        return bool((neighbours_of(self.sea) & self.mask(province)).any())

    def donors(self, state_id: int) -> np.ndarray:
        """Pixels a settlement of the state may take: no settlement, no foreign province, no lock."""
        fixed = sorted(self.settled | self.foreign)
        members = np.isin(self.labels, self.members(state_id))
        return members & ~np.isin(self.labels, fixed) & ~self.locked

    def settlement_mask(self) -> np.ndarray:
        """Every city and town of the scope, of any state, carved or reviewed."""
        return np.isin(self.labels, sorted(self.settled))

    def rail_neighbours(self, province: int) -> set[int]:
        return _mon().rail_neighbours(self.pairs, province)

    def lost_rail(self, before: np.ndarray, after: np.ndarray, provinces: set[int]) -> list[list[int]]:
        """Railway contacts of ``provinces`` that touched before and no longer touch."""
        old = province_adjacency(before)
        new = province_adjacency(after)
        return [
            [province, other]
            for province in sorted(provinces)
            for other in sorted(self.rail_neighbours(province))
            if other in old.get(province, set()) and other not in new.get(province, set())
        ]

    # Settlements

    def carve_city(self, settlement: PlannedSettlement) -> None:
        mon = _mon()
        parent = settlement.parent if settlement.parent is not None else self.city_choice(settlement.state)
        if self.state_of.get(parent) != settlement.state:
            raise RuntimeError(f"city {settlement.name_en}: parent {parent} lies outside state {settlement.state}")
        region = self.mask(parent)
        donors = self.donors(settlement.state)
        shore = self.shore if (region & self.shore).any() else None
        rules = (STAGE2_REMAINDER_PIXELS, CITY_MIN_NEIGHBOURS, self.river)
        hint = self.centre(parent)
        try:
            site, lost, _land = mon.carve_site(
                self.labels, donors, region, hint, parent, self.pairs, self.kinds, shore, CITY_PIXELS, *rules
            )
        except RuntimeError:
            # Every site that takes from a neighbour splits it; the parent gives all the pixels.
            site, lost, _land = mon.carve_site(
                self.labels, donors & region, region, hint, parent, self.pairs, self.kinds, shore, CITY_PIXELS, *rules
            )
        remainder = self.new_id()
        self.labels[region & ~site] = remainder
        self.labels[site] = parent
        self.add_entry(remainder, parent, "remainder")
        self.settled.add(parent)
        self.cities.append(parent)
        if lost:
            self.rail_losses.append({"settlement": parent, "lost_rail": lost})
        self.settlements.append(self.settlement_record(settlement, parent, parent))

    def city_choice(self, state_id: int) -> int:
        """A railway province near the middle of the state, else the most central one."""
        ys, xs = np.nonzero(np.isin(self.labels, self.members(state_id)))
        cy, cx = ys.mean(), xs.mean()
        options = []
        for province in self.members(state_id):
            if province in self.settled or province in self.foreign or self.size(province) < STAGE2_CITY_MIN_PARENT:
                continue
            y, x = self.centre(province)
            options.append(((province not in self.on_rail, float(np.hypot(y - cy, x - cx)), province), province))
        if not options:
            raise RuntimeError(f"state {state_id}: no province can hold a city")
        return min(options)[1]

    def town_choices(self, state_id: int) -> list[int]:
        """Rural provinces of the state away from every settlement; river banks and railways first."""
        cities = self.settlement_mask()
        distance = distance_transform_edt(~cities) if cities.any() else None
        planned = self.planned_ids()
        options = []
        for province in self.members(state_id):
            if province in self.settled or province in self.foreign or province in planned:
                continue
            if self.kinds.get(province) != "land" or self.size(province) < STAGE2_TOWN_MIN_PARENT:
                continue
            mask = self.mask(province)
            gap = STAGE2_TOWN_TARGET_DISTANCE if distance is None else float(distance[mask].max())
            if gap < STAGE2_TOWN_CITY_DISTANCE + 4:
                continue
            beside = bool((self.banks & mask).any()) or province in self.on_rail
            rank = (
                self.touches_sea(province),
                province in self.victory_points,
                not beside,
                abs(gap - STAGE2_TOWN_TARGET_DISTANCE),
                province,
            )
            options.append((rank, province))
        return [province for _rank, province in sorted(options)]

    def town_hint(self, state_id: int, parent: int) -> tuple[int, int]:
        """The inner pixel of ``parent`` nearest the target distance from the settlements (y, x)."""
        cities = self.settlement_mask()
        if not cities.any():
            return self.centre(parent)
        region = self.mask(parent)
        depth = distance_transform_edt(region)
        inner = region & (depth >= min(3.0, float(depth.max())))
        gap = distance_transform_edt(~cities)
        ys, xs = np.nonzero(inner)
        index = int(np.lexsort((xs, ys, np.abs(gap[ys, xs] - STAGE2_TOWN_TARGET_DISTANCE)))[0])
        return int(ys[index]), int(xs[index])

    def try_town(self, state_id: int, parent: int) -> tuple[np.ndarray, list[list[int]]]:
        """Site and lost railway contacts of a town carved at the edge of ``parent``."""
        mon = _mon()
        region = self.mask(parent)
        cities = self.settlement_mask()
        donors = self.donors(state_id)
        if cities.any():
            donors &= distance_transform_edt(~cities) >= STAGE2_TOWN_CITY_DISTANCE
        hint = self.town_hint(state_id, parent)
        rules = (STAGE2_TOWN_REMAINDER_PIXELS, STAGE2_TOWN_MIN_NEIGHBOURS, self.river)
        try:
            site, _lost, _land = mon.carve_site(
                self.labels, donors, region, hint, parent, set(), self.kinds, None, STAGE2_TOWN_PIXELS, *rules
            )
        except RuntimeError:
            site, _lost, _land = mon.carve_site(
                self.labels, donors & region, region, hint, parent, set(), self.kinds, None, STAGE2_TOWN_PIXELS, *rules
            )
        if site.sum() != STAGE2_TOWN_PIXELS:
            raise RuntimeError(f"town in {parent}: only {int(site.sum())} pixels")
        ys, xs = np.nonzero(region | site)
        box = np.s_[
            max(0, ys.min() - 3) : ys.max() + 4,
            max(0, xs.min() - 3) : xs.max() + 4,
        ]
        before = self.labels[box]
        after = before.copy()
        after[site[box]] = -1
        touched = set(np.unique(before[site[box]]).tolist())
        return site, self.lost_rail(before, after, touched)

    def carve_town(self, settlement: PlannedSettlement) -> None:
        failures = []
        fallback = None
        for parent in self.town_choices(settlement.state):
            try:
                site, lost = self.try_town(settlement.state, parent)
            except RuntimeError as error:
                failures.append(str(error))
                continue
            if lost and fallback is None:
                fallback = (parent, site, lost)
                continue
            if not lost:
                self.place_town(settlement, parent, site, lost)
                return
        if fallback is None:
            raise RuntimeError(f"town {settlement.name_en}: no province of state {settlement.state} holds it: {failures[:3]}")
        self.place_town(settlement, *fallback)

    def place_town(self, settlement: PlannedSettlement, parent: int, site: np.ndarray, lost: list) -> None:
        town = self.new_id()
        self.labels[site] = town
        self.add_entry(town, parent, "town")
        self.settled.add(town)
        self.towns[parent] = town
        if lost:
            self.rail_losses.append({"settlement": town, "lost_rail": lost})
        self.settlements.append(self.settlement_record(settlement, town, parent))

    @staticmethod
    def settlement_record(settlement: PlannedSettlement, province: int, parent: int) -> dict:
        return {
            "state": settlement.state,
            "kind": settlement.kind,
            "province": province,
            "parent": parent,
            "value": settlement.value,
            "name": settlement.name,
            "name_en": settlement.name_en,
        }

    def plan_settlements(self) -> None:
        with_city = {
            state_id
            for state_id in SCOPED_STATE_IDS
            if any(province in self.settled for province in self.members(state_id))
        }
        cities = [settlement for settlement in STAGE2_SETTLEMENTS if settlement.kind == "city"]
        towns = [settlement for settlement in STAGE2_SETTLEMENTS if settlement.kind == "town"]
        centred = frozenset(split_centres())
        missing_cities = sorted(SCOPED_STATE_IDS - with_city - centred - {settlement.state for settlement in cities})
        missing_towns = sorted(SCOPED_STATE_IDS - centred - {settlement.state for settlement in towns})
        if missing_cities or missing_towns:
            raise RuntimeError(
                f"Stage 2 settlements missing: cities for {missing_cities}, towns for {missing_towns}"
            )
        for settlement in cities:
            self.carve_city(settlement)
        for settlement in towns:
            self.carve_town(settlement)

    # Splitting

    def split_candidates(self) -> list[int]:
        result = []
        for state_id in sorted(SCOPED_STATE_IDS):
            for province in self.members(state_id):
                if province in self.settled or province in self.foreign or province in STAGE2_NAVAL_BASES:
                    continue
                if self.kinds.get(province, "land") != "land" or self.size(province) <= STAGE2_SPLIT_THRESHOLD:
                    continue
                if self.touches_sea(province):
                    self.coastal_kept.append(province)
                    continue
                result.append(province)
        return result

    def partition(self, region: np.ndarray, river: np.ndarray, prefer) -> tuple[np.ndarray, int] | None:
        """The roundest split into parts of about STAGE2_PART_PIXELS, or one part fewer."""
        mon = _mon()
        target = ceil(int(region.sum()) / STAGE2_PART_PIXELS)
        for parts in (target, target - 1):
            if parts < 2:
                return None
            owner, whole, lowest = mon.partition_province(region, parts, prefer, river)
            smallest = min(int((owner == index).sum()) for index in range(parts))
            if whole and lowest >= STAGE2_PART_MIN_ROUNDNESS and smallest >= STAGE2_PART_MIN_PIXELS:
                return owner, parts
        return None

    def holds(self, part: np.ndarray, box: tuple[slice, slice], point: tuple[int, int] | None) -> bool:
        if point is None:
            return False
        y = point[1] - self.window.y0 - box[0].start
        x = point[0] - self.window.x0 - box[1].start
        return 0 <= y < part.shape[0] and 0 <= x < part.shape[1] and bool(part[y, x])

    def keep_score(self, province: int, part: np.ndarray, box: tuple[slice, slice], region: np.ndarray) -> tuple:
        """Rank of a part for keeping the parent id (section 6.1 of the spec).

        In order: the sea contact of a naval base, the standing anchor of a
        province named by id, the victory-point marker, a supply hub, the
        most railway contacts, the standing anchor, the most pixels.
        """
        crop = self.labels[box]
        touching = set(np.unique(crop[neighbours_of(part) & ~region]).tolist())
        standing = self.anchors[0].get(province)
        return (
            province in STAGE2_NAVAL_BASES and bool((part & neighbours_of(self.sea[box])).any()),
            province in self.literals and self.holds(part, box, standing),
            province in self.victory_points and self.holds(part, box, self.anchors[38].get(province)),
            any(self.holds(part, box, point) for point in self.hubs.get(province, ())),
            len(touching & self.rail_neighbours(province)),
            self.holds(part, box, standing),
            int(part.sum()),
        )

    def split(self, province: int) -> None:
        ys, xs = np.nonzero(self.mask(province))
        box = np.s_[max(0, ys.min() - 1) : ys.max() + 2, max(0, xs.min() - 1) : xs.max() + 2]
        crop = self.labels[box]
        region = crop == province
        rail = self.rail_neighbours(province)
        rail_pixels = np.isin(crop, sorted(rail))

        def contacts(owner: np.ndarray) -> int:
            parts = int(owner.max()) + 1
            return max(
                len(set(np.unique(crop[neighbours_of(owner == index) & rail_pixels]).tolist()))
                for index in range(parts)
            )

        result = self.partition(region, self.river[box], contacts if rail else None)
        if result is None:
            self.failed_splits.append({"province": province, "pixels": int(region.sum())})
            return
        owner, parts = result
        kept = max(range(parts), key=lambda index: self.keep_score(province, owner == index, box, region))
        others = sorted(
            (index for index in range(parts) if index != kept),
            key=lambda index: tuple(np.mean(np.nonzero(owner == index), axis=1)),
        )
        ids = [province]
        for index in others:
            child = self.new_id()
            self.add_entry(child, province, "part")
            crop[owner == index] = child
            ids.append(child)
        self.splits[province] = ids

    # Plan

    def mend_rivers(self) -> None:
        """Give the river pixels outside the routed land a province border to run on.

        A piece a course cuts off joins the province of its state it touches
        across land; a course pixel inside a province gets a border by moving
        one land pixel beside it to another province of the same state.
        Settlements keep their pixels and no pixel changes its state. What
        stays unresolved is moved onto a border by the river pass.
        """
        mon = _mon()
        scope = mon.Scope(
            sorted(SCOPED_STATE_IDS),
            self.state_of,
            frozenset(),
            {},
            {province: province for province in self.settled},
            frozenset(),
            {},
        )
        river = self.river & ~self.routed
        editable = np.isin(self.labels, sorted(self.state_of)) & ~self.routed
        editable &= ~mon.coastal_courses(self.window, self.labels.shape)
        mender = mon.GeometryMender(self.labels, river, scope)
        nothing = np.zeros(self.labels.shape, bool)
        for province in mon.rivers_splitting_provinces(self.labels, river, editable, nothing):
            if not mender.movable(province):
                self.unmended.append({"province": province, "case": "cut, fixed province"})
                continue
            for piece, receiver in mon.cut_off_pieces(self.labels, river, province, scope):
                pixels = list(zip(*np.nonzero(piece)))
                if receiver is None or not all(mender.assign(int(y), int(x), receiver) for y, x in pixels):
                    self.unmended.append({"province": province, "case": "cut"})
        for y, x in zip(*np.nonzero(river & editable & ~province_borders(self.labels))):
            mender.give_border(int(y), int(x))
        self.mended = len(mender.changes)
        self.unmended += [
            {"province": province, "at": [x + self.window.x0, y + self.window.y0], "case": case}
            for province, (y, x), case in mender.unresolved
        ]

    def check_states(self) -> None:
        for state_id in sorted(SCOPED_STATE_IDS):
            before = [province for province, owner in self.scope_before.items() if owner == state_id]
            if (np.isin(self.original, before) != np.isin(self.labels, self.members(state_id))).any():
                raise RuntimeError(f"state {state_id}: its pixel area changed")

    def plan(self) -> tuple[dict, np.ndarray, dict]:
        mon = _mon()
        collisions = settlement_name_collisions(MAP_ROOT, STAGE2_SETTLEMENTS)
        if collisions:
            raise RuntimeError("; ".join(collisions))
        self.plan_settlements()
        for province in self.split_candidates():
            self.split(province)
        new_ids = sorted(self.planned_ids())
        changed = self.labels != self.original
        touched = set(new_ids) | set(np.unique(self.original[changed]).tolist())
        mon.clear_corners(self.labels, np.isin(self.labels, sorted(touched)) & ~self.water, self.state_of)
        self.mend_rivers()
        self.check_states()
        return self.finish()

    def full_grid(self) -> np.ndarray:
        full = self.grid.copy()
        full[self.window.s] = self.labels
        return full

    def finish(self) -> tuple[dict, np.ndarray, dict]:
        coastal = _coastal()
        mon = _mon()
        entries = [
            {
                "province": entry["province"],
                "parent": entry["parent"],
                "state": entry["state"],
                "kind": entry["kind"],
                "rgb": list(province_colour(int(entry["province"]), self.used)),
            }
            for entry in self.entries
        ]
        borders_before = coastal.province_border_count(self.grid)
        borders = coastal.province_border_count(self.full_grid())
        if BORDER_BUDGET - borders < BORDER_MARGIN:
            raise RuntimeError(
                f"the plan draws {borders} province borders: less than {BORDER_MARGIN} of {BORDER_BUDGET} stay free"
            )
        with Image.open(PROVINCE_GEOMETRY_PATH) as source:
            first = np.asarray(source.convert("RGBA"))
        palette = dict(self.colours)
        palette.update({int(entry["province"]): tuple(entry["rgb"]) for entry in entries})
        origin, second = mon.geometry_image(self.labels, self.original, palette, [], self.window)
        sheet = np.zeros((first.shape[0] + second.shape[0], max(first.shape[1], second.shape[1]), 4), np.uint8)
        sheet[: first.shape[0], : first.shape[1]] = first
        sheet[first.shape[0] :, : second.shape[1]] = second
        irregular = self.irregular_parts()
        manifest = dict(self.manifest)
        manifest["stage2"] = {
            "origin": origin,
            "sheet_row": int(first.shape[0]),
            "first_id": self.first_id,
            "provinces": entries,
            "cities": {str(city): city for city in sorted(self.cities)},
            "towns": {str(parent): town for parent, town in sorted(self.towns.items())},
            "settlements": self.settlements,
            "irregular_parts": irregular,
        }
        report = self.summary(entries, borders_before, borders, irregular)
        return manifest, sheet, report

    def irregular_parts(self) -> list[int]:
        """Parts that the corner repair left below the minimum size or roundness."""
        result = []
        for ids in self.splits.values():
            for province in ids:
                mask = self.mask(province)
                if mask.sum() < STAGE2_PART_MIN_PIXELS or _mon().roundness(mask) < STAGE2_PART_MIN_ROUNDNESS:
                    result.append(province)
        return sorted(result)

    def summary(self, entries: list[dict], borders_before: int, borders: int, irregular: list[int]) -> dict:
        """Plan statistics per state, settlements, railway chains to reroute and the border budget."""
        mon = _mon()
        adjacency = province_adjacency(self.labels)
        children: dict[int, set[int]] = defaultdict(set)
        for entry in entries:
            children[int(entry["parent"])].add(int(entry["province"]))
        reroutes = []
        for a, b in sorted(self.pairs):
            if (a in self.state_of or b in self.state_of) and b not in adjacency.get(a, set()):
                if b not in province_adjacency(self.original).get(a, set()):
                    continue
                allowed = {a, b} | children.get(a, set()) | children.get(b, set())
                reroutes.append({"segment": [a, b], "via": mon.province_path(adjacency, a, b, allowed)})
        states = {}
        for state_id in sorted(SCOPED_STATE_IDS):
            mine = [entry for entry in entries if entry["state"] == state_id]
            states[str(state_id)] = {
                "provinces_before": sum(owner == state_id for owner in self.scope_before.values()),
                "provinces_after": len(self.members(state_id)),
                "splits": len({entry["parent"] for entry in mine if entry["kind"] == "part"}),
                "new_ids": [int(entry["province"]) for entry in mine],
            }
        sizes = {
            "parts": [self.size(province) for ids in self.splits.values() for province in ids],
            "cities": {str(city): self.size(city) for city in self.cities},
            "towns": {str(town): self.size(town) for town in self.towns.values()},
        }
        roundness = [
            round(mon.roundness(self.mask(province)), 3) for ids in self.splits.values() for province in ids
        ]
        return {
            "first_id": self.first_id,
            "last_id": self.first_id + len(entries) - 1,
            "new_ids": len(entries),
            "borders_before": borders_before,
            "borders": borders,
            "border_margin": BORDER_BUDGET - borders,
            "states": states,
            "splits": {str(province): ids for province, ids in sorted(self.splits.items())},
            "failed_splits": self.failed_splits,
            "coastal_unsplit": sorted(self.coastal_kept),
            "irregular_parts": irregular,
            "part_pixels": [min(sizes["parts"], default=0), max(sizes["parts"], default=0)],
            "part_roundness_min": min(roundness, default=1.0),
            "city_pixels": sizes["cities"],
            "town_pixels": sizes["towns"],
            "settlements": self.settlements,
            "settlement_rail_losses": self.rail_losses,
            "river_pixels_mended": self.mended,
            "river_pixels_unmended": self.unmended,
            "rail_reroutes": reroutes,
        }


def plan_stage2(manifest: dict | None = None) -> tuple[dict, np.ndarray, dict]:
    """Plan Stage 2 on the map Stage 1 left; return the manifest, the geometry sheet and the report.

    A stored Stage 2 plan is never replanned from a map that carries it.
    """
    if manifest is None:
        manifest = json.loads(PROVINCE_MANIFEST_PATH.read_text(encoding="utf-8"))
    return Stage2Planner(manifest).plan()


def write_stage2_plan(output_root: Path) -> dict:
    """Write the planned manifest and raster under ``output_root``; elsewhere than the repository, the report too.

    The manifest keeps the line endings of the stored one, so its Stage 1
    part stays byte for byte as reviewed.
    """
    manifest, sheet, report = plan_stage2()
    write_plan_files(output_root, manifest, sheet)
    if output_root.resolve() != REPOSITORY_ROOT:
        (output_root / STAGE2_REPORT_NAME).write_text(
            json.dumps(report, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
        )
    return report


def write_plan_files(output_root: Path, manifest: dict, sheet: np.ndarray) -> None:
    """Write a manifest and its geometry raster under ``output_root`` with the stored line endings."""
    manifest_path = output_root / PROVINCE_MANIFEST_PATH.relative_to(PROVINCE_MANIFEST_PATH.parents[2])
    geometry_path = output_root / PROVINCE_GEOMETRY_PATH.relative_to(PROVINCE_GEOMETRY_PATH.parents[2])
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    newline = "\r\n" if b"\r\n" in PROVINCE_MANIFEST_PATH.read_bytes() else "\n"
    with manifest_path.open("w", encoding="utf-8", newline=newline) as handle:
        handle.write(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    Image.fromarray(sheet, "RGBA").save(geometry_path, optimize=True)


STATE_SMOOTHING_REPORT_NAME = "ivn_stage2_state_smoothing_report.json"
STATE_SMOOTHING_PREVIEW_DIR = ROOT / "docs/development/previews/vorkerland_states"


@dataclass(frozen=True)
class PlannedGrid:
    """Province ids of the whole map with every plan of the manifest stamped, as the map pass stamps them."""

    grid: np.ndarray
    colours: dict[int, tuple[int, int, int]]
    kinds: dict[int, str]
    terrain: dict[int, str]


def planned_province_grid(manifest: dict, sheet: np.ndarray) -> PlannedGrid:
    rows, _newline, _bom = _definition_rows()
    by_id = {int(row[0]): row for row in rows if row[0].isdigit()}
    colours = {province: tuple(map(int, row[1:4])) for province, row in by_id.items()}
    kinds = {province: row[4] for province, row in by_id.items()}
    terrain = {province: row[6] for province, row in by_id.items()}
    entries = planned_entries(manifest)
    for entry in entries:
        colours.setdefault(int(entry["province"]), tuple(entry["rgb"]))
        kinds.setdefault(int(entry["province"]), "land")
    scoped = province_ids_for_states(SCOPED_STATE_IDS) | {int(entry["province"]) for entry in entries}
    with Image.open(BytesIO(PROVINCES_PATH.read_bytes())) as source:
        province_rgb = np.array(source.convert("RGB"))
    for origin, geometry in geometry_layers(manifest, sheet):
        stamp_layer(province_rgb, geometry, origin, colours, frozenset(scoped))
    grid = _coastal().province_grid(province_rgb, colours).astype(np.int32)
    return PlannedGrid(grid, colours, kinds, terrain)


def stage2_smoothing_frozen(
    grid: np.ndarray, window, river: np.ndarray, land: np.ndarray, scope_ids: frozenset[int]
) -> np.ndarray:
    """Window pixels of the IVN/IIA scope that keep their province while the state lines are smoothed.

    The band beside land of another geography builder, the provinces whose
    pixels the coastal builder repairs, the standing and victory-point
    anchors and supply-hub models, and every province beside a course this
    builder routes anew on every pass, with the pixels round it: a line
    moved there pulls the course onto another border on the next map pass.
    """
    coastal = _coastal()
    labels = grid[window.s]
    frozen = np.zeros(labels.shape, bool)
    foreign = land & ~np.isin(labels, sorted(scope_ids))
    if foreign.any():
        frozen |= distance_transform_edt(~foreign) <= STATE_SMOOTHING_SEAM
    repaired = sorted(coastal.PROVINCE_REPAIR_PROVINCES & scope_ids)
    if repaired:
        frozen |= binary_dilation(np.isin(labels, repaired), _EIGHT)
    unitstacks = UNITSTACKS_PATH.read_bytes()
    points = [point for slot in (0, 38) for point in slot_points(unitstacks, grid.shape[0], slot).values()]
    points += [point for hub in supply_node_points(grid, MAP_ROOT).values() for point in hub]
    for x, y in points:
        local_x, local_y = x - window.x0, y - window.y0
        if 0 <= local_y < labels.shape[0] and 0 <= local_x < labels.shape[1]:
            frozen[local_y, local_x] = True
    routed = np.isin(labels, sorted(relief_province_ids(RELIEF_STATE_IDS) - AUTHORED_RIVER_PROVINCES))
    own_courses = river & routed & ~kept_courses(river, routed)
    if own_courses.any():
        carriers = np.unique(labels[binary_dilation(own_courses, _EIGHT)])
        frozen |= binary_dilation(np.isin(labels, carriers), _EIGHT)
    return frozen


def stage2_sheet_with_moves(
    manifest: dict,
    sheet: np.ndarray,
    moved: np.ndarray,
    labels: np.ndarray,
    window,
    colours: dict[int, tuple[int, int, int]],
) -> tuple[list[int], np.ndarray]:
    """The Stage 2 origin and the raster whose Stage 2 layer also paints the ``moved`` window pixels.

    The layer grows to hold them; the Stage 1 rows stay byte for byte.
    """
    plan = stage2_plan(manifest)
    split = int(plan["sheet_row"])
    ox, oy = plan["origin"]
    layer = sheet[split:]
    old_ys, old_xs = np.nonzero(layer[..., 3] > 0)
    new_ys, new_xs = np.nonzero(moved)
    map_ys = np.concatenate([old_ys + oy, new_ys + window.y0])
    map_xs = np.concatenate([old_xs + ox, new_xs + window.x0])
    top, left = int(map_ys.min()), int(map_xs.min())
    result = np.zeros((int(map_ys.max()) - top + 1, int(map_xs.max()) - left + 1, 4), np.uint8)
    result[old_ys + oy - top, old_xs + ox - left] = layer[old_ys, old_xs]
    for province in np.unique(labels[moved]).tolist():
        mask = moved & (labels == province)
        ys, xs = np.nonzero(mask)
        result[ys + window.y0 - top, xs + window.x0 - left] = (*colours[province], 255)
    width = max(sheet.shape[1], result.shape[1])
    combined = np.zeros((split + result.shape[0], width, 4), np.uint8)
    combined[:split, : sheet.shape[1]] = sheet[:split]
    combined[split:, : result.shape[1]] = result
    return [left, top], combined


def smooth_stage2_plan(manifest: dict | None = None) -> tuple[dict, np.ndarray, dict, dict]:
    """Smooth the lines between the IVN/IIA states of the stored Stage 2 plan.

    Returns the manifest, the raster, the report and the window arrays for
    previews. The moved pixels join the Stage 2 layer, so the map pass
    stamps them with the rest of the plan; a second run on the result
    moves nothing.
    """
    mon = _mon()
    coastal = _coastal()
    if manifest is None:
        manifest = json.loads(PROVINCE_MANIFEST_PATH.read_text(encoding="utf-8"))
    if not has_stage2_plan(manifest):
        raise RuntimeError("no Stage 2 plan to smooth: run --plan-stage2-provinces first")
    with Image.open(PROVINCE_GEOMETRY_PATH) as source:
        sheet = np.asarray(source.convert("RGBA")).copy()
    planned = planned_province_grid(manifest, sheet)
    grid = planned.grid
    plan = stage2_plan(manifest)
    # The state files are authoritative; a plan entry gives the state of a
    # province only until the map pass writes it into its state file.
    state_of = province_state_contract(SCOPED_STATE_IDS)
    for entry in plan["provinces"]:
        state_of.setdefault(int(entry["province"]), int(entry["state"]))
    scope_ids = frozenset(state_of)
    window = scope_window(np.isin(grid, sorted(scope_ids)), STAGE2_WINDOW_MARGIN)
    labels = grid[window.s]
    land = np.isin(labels, [province for province, kind in planned.kinds.items() if kind == "land"])
    water = np.isin(labels, [province for province, kind in planned.kinds.items() if kind in ("sea", "lake")])
    with Image.open(BytesIO(RIVERS_PATH.read_bytes())) as source:
        river = mon.river_masks(np.asarray(source)[window.s], water)
    tables = manifest_tables(manifest)
    urban = {province for province in scope_ids if planned.terrain.get(province) == "urban"}
    settlements = tables.city_provinces | tables.island_urban | STAGE2_FIXED_PROVINCES | urban
    exempt = {int(province) for province in plan.get("irregular_parts", [])}
    shaped = {
        int(entry[key])
        for entry in plan["provinces"]
        if entry["kind"] == "part"
        for key in ("province", "parent")
    } - exempt
    frozen = stage2_smoothing_frozen(grid, window, river, land, scope_ids)
    smoothing = smooth_state_borders(
        labels,
        state_of,
        SCOPED_STATE_IDS,
        land,
        river,
        settlements=frozenset(settlements),
        frozen=frozen,
        rail_pairs=mon.rail_pairs(MAP_ROOT),
        min_pixels={province: STAGE2_PART_MIN_PIXELS for province in shaped},
        min_roundness={province: STAGE2_PART_MIN_ROUNDNESS for province in shaped},
    )
    full = grid.copy()
    full[window.s] = smoothing.labels
    borders_before = coastal.province_border_count(grid)
    borders = coastal.province_border_count(full)
    states_before = province_states(labels, state_of)
    states_after = province_states(smoothing.labels, state_of)
    moved = smoothing.labels != labels
    result = dict(manifest)
    if moved.any():
        origin, sheet = stage2_sheet_with_moves(manifest, sheet, moved, smoothing.labels, window, planned.colours)
        result["stage2"] = {**plan, "origin": origin}
    report = {
        **smoothing.report(),
        "window": [window.x0, window.y0, window.x1, window.y1],
        "frozen_pixels": int((frozen & land & np.isin(labels, sorted(scope_ids))).sum()),
        "borders_before": borders_before,
        "borders": borders,
        "border_margin": BORDER_BUDGET - borders,
        "interior_river_pixels_before": interior_river_pixels_by_state(
            river, states_before, land, SCOPED_STATE_IDS
        ),
        "interior_river_pixels_after": interior_river_pixels_by_state(
            river, states_after, land, SCOPED_STATE_IDS
        ),
    }
    previews = {"before": states_before, "after": states_after, "land": land, "river": river}
    return result, sheet, report, previews


def write_state_smoothing_previews(
    directory: Path,
    arrays: dict,
    scope_states: frozenset[int] = SCOPED_STATE_IDS,
    name: str = "ivn_stage2_state_smoothing.png",
) -> list[Path]:
    """The states before and after smoothing side by side; moved pixels are marked on the right."""
    directory.mkdir(parents=True, exist_ok=True)
    before = arrays["before"]
    after = arrays["after"]
    land = arrays["land"]
    inside = np.isin(after, sorted(scope_states)) & land
    crop = _preview_crop(inside)
    sheets = []
    for states in (before, after):
        local = states[crop]
        picture = np.full((*local.shape, 3), 50.0)
        picture[land[crop]] = 120
        for state in np.unique(local[inside[crop]]).tolist():
            colour = [90 + 140 * stable_unit_hash(state, channel, 31) for channel in range(3)]
            picture[(local == state) & land[crop]] = colour
        line = np.zeros(local.shape, bool)
        line[:, :-1] |= local[:, :-1] != local[:, 1:]
        line[:-1] |= local[:-1] != local[1:]
        picture[line & land[crop]] = 20
        picture[arrays["river"][crop]] = RIVER_PREVIEW_COLOUR
        sheets.append(picture)
    sheets[1][(before != after)[crop]] = CITY_PREVIEW_COLOUR
    gap = np.full((sheets[0].shape[0], 4, 3), 255.0)
    path = directory / name
    _scaled(np.concatenate([sheets[0], gap, sheets[1]], axis=1)).save(path, optimize=True)
    return [path]


def write_smoothed_stage2_plan(output_root: Path | None, previews: bool = False) -> dict:
    """Smooth the stored Stage 2 plan; write it under ``output_root`` only when one is given.

    Nothing is written when no pixel moves or the smoothing did not settle
    within its passes. Elsewhere than the repository the report is written
    beside the plan.
    """
    stored = PROVINCE_MANIFEST_PATH.read_bytes()
    manifest = json.loads(stored.decode("utf-8"))
    newline = b"\r\n" if b"\r\n" in stored else b"\n"
    if (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode("utf-8").replace(b"\n", newline) != stored:
        raise RuntimeError(f"{PROVINCE_MANIFEST_PATH.name} is not in the planner's format; it would be rewritten")
    smoothed, sheet, report, arrays = smooth_stage2_plan(manifest)
    if report["border_margin"] < BORDER_MARGIN:
        raise RuntimeError(
            f"smoothing draws {report['borders']} province borders: less than {BORDER_MARGIN} of {BORDER_BUDGET} stay free"
        )
    report["written"] = False
    if output_root is not None and report["stable"] and report["moved_pixels"]:
        write_plan_files(output_root, smoothed, sheet)
        report["written"] = True
    if previews:
        report["previews"] = [path.as_posix() for path in write_state_smoothing_previews(STATE_SMOOTHING_PREVIEW_DIR, arrays)]
    if output_root is not None and output_root.resolve() != REPOSITORY_ROOT:
        output_root.mkdir(parents=True, exist_ok=True)
        (output_root / STATE_SMOOTHING_REPORT_NAME).write_text(
            json.dumps(report, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
        )
    return report


def reconcile_stage2_anchors(
    stacks: list[list[str]],
    province_rgb: np.ndarray,
    before_rgb: np.ndarray,
    colours: dict[int, tuple[int, int, int]],
    kinds: dict[int, str],
    heights: np.ndarray,
) -> list[list[str]]:
    """Give the provinces the Stage 2 geometry touches native unit anchors.

    New provinces, provinces that gave or took pixels and land provinces
    whose neighbours changed are checked. One without a standing anchor
    inside its interior centre receives a fresh native set; one whose slot
    set or moving rows no longer match its borders keeps its standing slots
    and has the rest rebuilt in the engine's neighbour order. The coastal
    builder places the anchors of the provinces it repairs. Rows stay
    grouped by slot in province order.
    """
    coastal = _coastal()
    grid = coastal.province_grid(province_rgb, colours)
    before = coastal.province_grid(before_rgb, colours)
    new_ids = set(stage2_parents(PROVINCE_MANIFEST))
    changed = grid != before
    ys, xs = np.nonzero(changed | np.isin(grid, sorted(new_ids)))
    window = np.s_[max(0, ys.min() - 2) : ys.max() + 3, max(0, xs.min() - 2) : xs.max() + 3]
    local = coastal.province_neighbours(grid[window])
    old_local = coastal.province_neighbours(before[window])
    candidates = (
        new_ids
        | set(np.unique(before[changed]).tolist())
        | set(np.unique(grid[changed]).tolist())
        | {province for province in set(local) | set(old_local) if local.get(province) != old_local.get(province)}
    )
    candidates -= set(coastal.PROVINCE_REPAIR_PROVINCES)
    slots: dict[int, dict[int, list[str]]] = defaultdict(dict)
    for row in stacks:
        slots[int(row[0])][int(row[1])] = row
    parents = stage2_parents(PROVINCE_MANIFEST)
    boxes = find_objects(grid)
    map_height = grid.shape[0]
    rebuilt: dict[int, dict[int, list[str]]] = {}
    for province in sorted(candidates):
        if kinds.get(province) != "land":
            continue
        interior = coastal.province_interior(grid, province, boxes[province - 1])
        contacts = coastal.border_contacts(grid, province, boxes[province - 1], interior)
        existing = slots.get(province, {})
        root_rows = slots.get(stage2_root(province, parents), {})
        offset = root_rows[0][6] if 0 in root_rows else None
        strays = {slot for slot, row in existing.items() if anchor_on_other_land(row, grid, kinds, province)}
        if 0 not in existing or 0 in strays or not coastal.standing_anchor_central(existing[0], grid, interior):
            keep = {}
            offset = existing[0][6] if 0 in existing else offset
        elif (
            strays
            or set(existing) != coastal.native_slots("land", len(contacts))
            or not coastal.moving_anchors_native(existing, contacts, map_height)
        ):
            keep = {
                slot: row for slot, row in existing.items() if slot in coastal.STANDING_SLOTS and slot not in strays
            }
        else:
            continue
        rebuilt[province] = coastal.complete_native_anchors(
            province, "land", keep, grid, heights, interior, contacts, offset=offset
        )
    blocks: dict[int, list[list[str]]] = defaultdict(list)
    for row in stacks:
        if int(row[0]) not in rebuilt:
            blocks[int(row[1])].append(row)
    for province, anchors in sorted(rebuilt.items()):
        for slot, row in anchors.items():
            block = blocks[slot]
            prefix = np.maximum.accumulate([int(item[0]) for item in block]).tolist() if block else []
            block.insert(bisect_right(prefix, province), list(row))
    return [row for slot in sorted(blocks) for row in blocks[slot]]


def anchor_on_other_land(row: list[str], grid: np.ndarray, kinds: dict[int, str], province: int) -> bool:
    x = round(float(row[2]))
    y = grid.shape[0] - 1 - round(float(row[4]))
    other = int(grid[y, x])
    return other != province and kinds.get(other) == "land"


def all_province_grid(province_rgb: np.ndarray) -> np.ndarray:
    rows, _newline, _bom = _definition_rows()
    colours = {
        int(row[0]): (int(row[1]), int(row[2]), int(row[3])) for row in rows if row[0].isdigit()
    }
    return _coastal().province_grid(province_rgb, colours).astype(np.int32)


def scope_window(scope: np.ndarray, margin: int):
    ys, xs = np.nonzero(scope)
    return _mon().Window(
        max(0, int(ys.min()) - margin),
        min(scope.shape[0], int(ys.max()) + margin + 1),
        max(0, int(xs.min()) - margin),
        min(scope.shape[1], int(xs.max()) + margin + 1),
    )


def settle_stage2_rivers(
    rivers: np.ndarray,
    labels: np.ndarray,
    scope: np.ndarray,
    routed: np.ndarray,
    cities: np.ndarray,
    water: np.ndarray,
    heights: np.ndarray,
) -> np.ndarray:
    """Put every river pixel of the scope outside the routed courses on a province border.

    Runs off a border and pixels that cut a province apart move onto the
    border between the course pixels on either side; courses become simple
    lines, every fork gets a flow-in pixel and no width uses palette 5 or 8.
    The coastal builder's course pixels and their neighbours stay, and so do
    pixels outside the scope, so a course leaving the scope keeps its entry
    and exit. ``labels`` holds province ids; ``routed`` the land where this
    builder routes its own courses anew on every pass. A course may turn or
    detour onto that land; ``route_rivers`` keeps every course that reaches
    land outside it.
    """
    mon = _mon()
    window = scope_window(scope, RIVER_WALK_MARGIN)
    result = rivers.copy()
    local = result[window.s]
    ids = labels[window.s]
    local_water = water[window.s]
    local_cities = cities[window.s]
    local_routed = routed[window.s]
    foreign_course = mon.coastal_courses(window, ids.shape)
    area = scope[window.s] & ~foreign_course & ~neighbours_of(foreign_course)
    border = province_borders(ids)
    nothing = np.zeros(ids.shape, bool)
    mon.flip_corners(local, area & ~local_routed, border, local_cities, ids, area)
    existing = kept_courses(mon.river_masks(local, local_water), local_routed)
    mon.repair_existing_rivers(local, existing, area, border, local_cities, heights[window.s], ids, nothing)
    editable = area & kept_courses(mon.river_masks(local, local_water), local_routed)
    mon.thin_courses(local, editable, local_water, mon.line_pixels(ids))
    # Thinning leaves new turns where a course was two pixels wide.
    mon.flip_corners(local, area & ~local_routed, border, local_cities, ids, area)
    flip_fork_corners(local, area & ~local_routed, border, local_cities)
    editable = area & kept_courses(mon.river_masks(local, local_water), local_routed)
    mon.settle_existing_markers(local, local_water, editable)
    for width, native in FORBIDDEN_RIVER_WIDTHS.items():
        local[editable & (local == width)] = native
    settle_course_widths(local, editable, local_water)
    return result


def flip_fork_corners(rivers: np.ndarray, owned: np.ndarray, border: np.ndarray, cities: np.ndarray) -> None:
    """Move a turn inside a province beside a tributary mouth onto the border, in place.

    ``flip_corners`` leaves a turn beside a flow-in pixel alone. Here the
    turn ``c`` has two course sides ``a`` and ``f``; ``f`` is the fork that a
    flow-in pixel ``m`` joins, and its last course side ``e`` rejoins the
    course at ``g``. Turning at the opposite corner ``q`` instead would close
    the square ``f, q, g, e``, so ``e`` is dropped: the course runs
    ``a, q, g`` along the border and ``f`` becomes the tributary's flow-in
    pixel, with ``m`` taking the tributary's width. ``e`` may lie on the
    foreign side of the state line; it only links two pixels of the scope.
    """
    mon = _mon()
    steps = ((-1, 0), (1, 0), (0, -1), (0, 1))
    river = rivers < RIVER_SEA_PALETTE
    for y, x in zip(*np.nonzero(river & owned & ~border & ~cities)):
        sides = [(y + dy, x + dx) for dy, dx in steps if river[y + dy, x + dx]]
        if len(sides) != 2 or sides[0][0] == sides[1][0] or sides[0][1] == sides[1][1]:
            continue
        qy = sides[0][0] + sides[1][0] - y
        qx = sides[0][1] + sides[1][1] - x
        if river[qy, qx] or not owned[qy, qx] or not border[qy, qx] or cities[qy, qx]:
            continue
        for fy, fx in sides:
            near = [(fy + dy, fx + dx) for dy, dx in steps if river[fy + dy, fx + dx] and (fy + dy, fx + dx) != (y, x)]
            mouths = [point for point in near if rivers[point] == RIVER_FLOW_IN_PALETTE]
            rest = [point for point in near if rivers[point] != RIVER_FLOW_IN_PALETTE]
            if len(mouths) != 1 or len(rest) != 1 or not border[fy, fx]:
                continue
            ey, ex = rest[0]
            gy, gx = ey + qy - fy, ex + qx - fx
            if not river[gy, gx] or abs(gy - qy) + abs(gx - qx) != 1:
                continue
            # A shortcut pixel on foreign land may go when both its ends are ours.
            if sum(river[ey + dy, ex + dx] for dy, dx in steps) != 2 or not (owned[fy, fx] and owned[gy, gx]):
                continue
            my, mx = mouths[0]
            beyond = [
                rivers[my + dy, mx + dx]
                for dy, dx in steps
                if (my + dy, mx + dx) != (fy, fx) and mon.WIDTH_STEPS[0] <= rivers[my + dy, mx + dx] < RIVER_SEA_PALETTE
            ]
            if len(beyond) != 1:
                continue
            rivers[qy, qx] = rivers[y, x]
            rivers[y, x] = RIVER_LAND_PALETTE
            rivers[ey, ex] = RIVER_LAND_PALETTE
            rivers[fy, fx] = RIVER_FLOW_IN_PALETTE
            rivers[my, mx] = beyond[0]
            river = rivers < RIVER_SEA_PALETTE
            break


def kept_courses(river: np.ndarray, routed: np.ndarray) -> np.ndarray:
    """River pixels of every course that reaches land outside ``routed``."""
    pieces, _count = label(river)
    kept = np.unique(pieces[river & ~routed])
    return river & np.isin(pieces, kept[kept > 0])


@dataclass(frozen=True)
class DrawnCourse:
    """One course as the engine draws it, upstream to downstream, markers left out.

    ``head`` is the source pixel of a river, or the far end of a tributary;
    ``junction`` is the flow-in pixel of a tributary.
    """

    pixels: tuple[tuple[int, int], ...]
    head: tuple[int, int]
    junction: tuple[int, int] | None


def drawn_courses(rivers: np.ndarray, water: np.ndarray) -> list[DrawnCourse]:
    """Every walk of the engine from a source or flow-in pixel, turned to run downstream.

    A walk from a flow-in pixel runs up its tributary. The walks run on a
    copy padded with land, so a course may reach the edge of the window.
    """
    padded = np.pad(rivers, 1, constant_values=RIVER_LAND_PALETTE)
    _visits, _forks, walks = _mon().walk_courses(padded, np.pad(water, 1))
    result = []
    for start, walk in walks.items():
        points = tuple((x - 1, y - 1) for x, y in walk)
        marker = int(padded[start[1], start[0]])
        if marker == RIVER_SOURCE_PALETTE:
            result.append(DrawnCourse(points[1:], points[0], None))
        elif marker == RIVER_FLOW_IN_PALETTE and len(points) > 1:
            result.append(DrawnCourse(points[1:][::-1], points[-1], points[0]))
    return result


def receiver_width(rivers: np.ndarray, course: DrawnCourse) -> int:
    """Width of the receiving river beside the flow-in pixel of a tributary."""
    x, y = course.junction
    inside = set(course.pixels)
    widths = [
        int(rivers[ny, nx])
        for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1))
        if 0 <= ny < rivers.shape[0]
        and 0 <= nx < rivers.shape[1]
        and (nx, ny) not in inside
        and int(rivers[ny, nx]) in NATIVE_RIVER_WIDTHS
    ]
    return max(widths, default=0)


def _settle_course(rivers: np.ndarray, editable: np.ndarray, course: DrawnCourse) -> bool:
    """Apply the width rules to one course in place; report whether a pixel changed."""
    changed = False
    if course.junction is not None:
        hx, hy = course.head
        if rivers[hy, hx] == RIVER_SOURCE_PALETTE and editable[hy, hx]:
            following = [int(rivers[y, x]) for x, y in course.pixels[1:2]]
            native = following and following[0] in NATIVE_RIVER_WIDTHS
            rivers[hy, hx] = following[0] if native else NATIVE_RIVER_WIDTHS[0]
            changed = True
    running = 0
    for x, y in course.pixels:
        width = int(rivers[y, x])
        if width not in NATIVE_RIVER_WIDTHS:
            continue
        if width < running and editable[y, x]:
            rivers[y, x] = running
            changed = True
            width = running
        running = max(running, width)
    if course.junction is not None:
        cap = receiver_width(rivers, course)
        for x, y in course.pixels:
            width = int(rivers[y, x])
            if cap and editable[y, x] and width in NATIVE_RIVER_WIDTHS and width > cap:
                rivers[y, x] = cap
                changed = True
    return changed


def settle_course_widths(rivers: np.ndarray, editable: np.ndarray, water: np.ndarray) -> None:
    """Give the editable courses the drawing rules, in place.

    A tributary starts with a width, never a source pixel; widths never
    shrink downstream; a tributary is no wider than its receiver where it
    flows in. A pixel outside ``editable`` keeps its width.
    """
    for _round in range(RIVER_WIDTH_ROUNDS):
        changed = False
        for course in drawn_courses(rivers, water):
            changed |= _settle_course(rivers, editable, course)
        if not changed:
            return


def course_rule_issues(
    rivers: np.ndarray, inside: np.ndarray, water: np.ndarray, origin: tuple[int, int]
) -> list[str]:
    """Width and marker rules of every drawn course that reaches ``inside``."""
    issues = []
    for course in drawn_courses(rivers, water):
        junction = course.junction
        hx, hy = course.head
        name = f"course from {(hx + origin[0], hy + origin[1])}"
        if junction is not None and inside[hy, hx] and rivers[hy, hx] == RIVER_SOURCE_PALETTE:
            issues.append(f"tributary {name} starts with a source pixel")
        widths = [
            (int(rivers[y, x]), bool(inside[y, x]))
            for x, y in course.pixels
            if int(rivers[y, x]) in NATIVE_RIVER_WIDTHS
        ]
        if any(later < earlier and mine for (earlier, _mine), (later, mine) in zip(widths, widths[1:])):
            issues.append(f"{name}: widths shrink downstream")
        if junction is not None and inside[junction[1], junction[0]] and widths:
            if receiver_width(rivers, course) < widths[-1][0]:
                issues.append(f"tributary {name} is wider than its receiver")
    return issues


def stage2_river_issues(
    rivers: np.ndarray, labels: np.ndarray, scope: np.ndarray, cities: np.ndarray, water: np.ndarray
) -> list[str]:
    """The river rules of the IVN/IIA scope once Stage 2 is planned.

    Every river pixel touches another province across a pixel edge, no
    river cuts a province apart or runs through a Stage 2 settlement
    (``cities``), and no width uses palette 5 or 8. The coastal builder
    checks its own courses. A turn of a course on a diagonal step of the
    state line with foreign land is left to the builder of that land, as
    the Montar builder leaves its turns beside IVN.
    """
    mon = _mon()
    window = scope_window(scope, RIVER_WALK_MARGIN)
    local = rivers[window.s]
    ids = labels[window.s]
    inside = scope[window.s]
    river = mon.river_masks(local, water[window.s])
    origin = (window.x0, window.y0)
    off_border = river & inside & ~province_borders(ids) & ~mon.coastal_courses(window, ids.shape)
    off_border &= ~state_line_turns(ids, inside)
    issues = []
    if off_border.any():
        issues.append(
            f"{int(off_border.sum())} IVN/IIA river pixels cross province interiors, first at {mon._map_point(off_border, origin)}"
        )
    split = mon.rivers_splitting_provinces(ids, river, inside, np.zeros(ids.shape, bool))
    if split:
        issues.append(f"rivers cut IVN/IIA provinces {split} into pieces")
    in_city = river & cities[window.s]
    if in_city.any():
        issues.append(f"{int(in_city.sum())} river pixels lie inside carved IVN/IIA settlements")
    forbidden = inside & river & np.isin(local, list(FORBIDDEN_RIVER_WIDTHS))
    if forbidden.any():
        issues.append(f"{int(forbidden.sum())} IVN/IIA river pixels use width palette 5 or 8")
    issues.extend(mon.course_shape_issues(local, inside, water[window.s], origin))
    issues.extend(course_rule_issues(local, inside, water[window.s], origin))
    return issues


def state_line_turns(ids: np.ndarray, inside: np.ndarray) -> np.ndarray:
    """Scope pixels that touch another province only at a corner, and only foreign ones.

    A course on a diagonal step of the state line turns on such a pixel;
    the other turn lies on the foreign land, whose rivers another builder
    owns.
    """
    foreign = np.zeros(ids.shape, bool)
    domestic = np.zeros(ids.shape, bool)
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            if not (dy or dx):
                continue
            other = np.roll(np.roll(ids, dy, 0), dx, 1) != ids
            beside = np.roll(np.roll(inside, dy, 0), dx, 1)
            foreign |= other & ~beside
            domestic |= other & beside
    return inside & ~province_borders(ids) & foreign & ~domestic


def stage2_geometry_issues(labels: np.ndarray, by_id: dict[int, list[str]], root: Path) -> list[str]:
    """Sizes, shapes and kept ids of the Stage 2 geometry on stamped province ids."""
    mon = _mon()
    plan = stage2_plan(PROVINCE_MANIFEST)
    sizes = np.bincount(labels.ravel(), minlength=max(by_id) + 1)
    issues = []
    for city in plan.get("cities", {}).values():
        if not STAGE2_CITY_SIZE[0] <= sizes[int(city)] <= STAGE2_CITY_SIZE[1]:
            issues.append(f"Stage 2 city {city}: {int(sizes[int(city)])} pixels")
    for town in plan.get("towns", {}).values():
        if not STAGE2_TOWN_SIZE[0] <= sizes[int(town)] <= STAGE2_TOWN_SIZE[1]:
            issues.append(f"Stage 2 town {town}: {int(sizes[int(town)])} pixels")
    exempt = set(plan.get("irregular_parts", []))
    boxes = find_objects(labels)
    split_parents = {int(entry["parent"]) for entry in plan.get("provinces", []) if entry["kind"] == "part"}
    parts = {int(entry["province"]) for entry in plan.get("provinces", []) if entry["kind"] == "part"}
    for province in sorted(split_parents | parts):
        mask = labels[boxes[province - 1]] == province
        if province in exempt:
            continue
        if mask.sum() < STAGE2_PART_MIN_PIXELS or mon.roundness(mask) < STAGE2_PART_MIN_ROUNDNESS:
            issues.append(f"Stage 2 part {province}: {int(mask.sum())} pixels, roundness {mon.roundness(mask):.2f}")
    sea = np.isin(labels, [province for province, row in by_id.items() if row[4] == "sea"])
    coast = set(np.unique(labels[neighbours_of(sea) & ~sea]).tolist())
    scope = province_ids_for_states(SCOPED_STATE_IDS)
    for province in sorted(stage2_literals(root, scope)):
        if by_id.get(province, ["", "", "", "", ""])[4] != "land" or not sizes[province]:
            issues.append(f"province {province}: named by id, no longer a land province")
        elif province in STAGE2_NAVAL_BASES and province not in coast:
            issues.append(f"naval base {province}: lost its sea contact")
    return issues


RAILWAYS_PATH = ROOT / "map/railways.txt"


@dataclass(frozen=True)
class ProvinceGeometry:
    provinces: bytes
    definition: bytes
    unitstacks: bytes
    railways: bytes
    issues: tuple[str, ...]


def province_adjacency(labels: np.ndarray) -> dict[int, set[int]]:
    adjacency: dict[int, set[int]] = {}
    for first, second in ((labels[:, 1:], labels[:, :-1]), (labels[1:, :], labels[:-1, :])):
        differs = first != second
        for a, b in zip(first[differs].tolist(), second[differs].tolist()):
            adjacency.setdefault(a, set()).add(b)
            adjacency.setdefault(b, set()).add(a)
    return adjacency


def _shortest_province_path(
    start: int, goal: int, adjacency: dict[int, set[int]], allowed: frozenset[int]
) -> list[int]:
    previous = {start: start}
    queue = deque([start])
    while queue:
        current = queue.popleft()
        if current == goal:
            break
        # Cities first, so repaired lines pass through them.
        for neighbour in sorted(
            adjacency.get(current, ()), key=lambda value: (value not in CITY_PROVINCES, value)
        ):
            if neighbour in allowed and neighbour not in previous:
                previous[neighbour] = current
                queue.append(neighbour)
    if goal not in previous:
        raise RuntimeError(f"railway {start}-{goal}: no IVN province path")
    path = [goal]
    while path[-1] != start:
        path.append(previous[path[-1]])
    return path[::-1]


def _railway_detour(
    start: int,
    goal: int,
    adjacency: dict[int, set[int]],
    scoped: frozenset[int],
    cities: dict[int, int],
    chain: list[int],
    repaired: list[int],
) -> list[int]:
    """The shortest province path that closes a railway gap.

    A line visits no province twice, so the path first avoids the provinces
    of its line. The rural parent of a Stage 1 city is read as the city on
    the next pass, so no detour passes through it while another path exists.
    """
    rural = scoped - frozenset(cities)
    for allowed in (
        (rural - frozenset(chain) - frozenset(repaired)) | {goal},
        rural | {goal},
        scoped,
    ):
        try:
            return _shortest_province_path(start, goal, adjacency, frozenset(allowed))
        except RuntimeError:
            continue
    raise RuntimeError(f"railway {start}-{goal}: no IVN province path")


def repair_railways(
    original: bytes, adjacency: dict[int, set[int]], scoped: frozenset[int]
) -> bytes:
    """Route IVN railway segments through the city provinces and close gaps, frontier segments included."""
    text = original.decode("utf-8-sig")
    newline = "\r\n" if "\r\n" in text else "\n"
    cities = {
        int(parent): int(city)
        for parent, city in PROVINCE_MANIFEST["cities"].items()
        if int(parent) != int(city)
    }
    lines = []
    for line in text.splitlines():
        fields = line.split()
        if len(fields) < 3:
            lines.append(line)
            continue
        chain = [cities.get(int(value), int(value)) for value in fields[2:]]
        repaired = chain[:1]
        for province in chain[1:]:
            previous = repaired[-1]
            # A segment leaving the scope is repaired too: a split may take
            # the frontier contact from its IVN end.
            if province in adjacency.get(previous, ()) or not (
                previous in scoped or province in scoped
            ):
                repaired.append(province)
            else:
                repaired.extend(
                    _railway_detour(previous, province, adjacency, scoped, cities, chain, repaired)[1:]
                )
        updated = f"{fields[0]} {len(repaired)} " + " ".join(map(str, repaired)) + " "
        lines.append(updated if repaired != [int(value) for value in fields[2:]] else line)
    return (newline.join(lines) + newline).encode("utf-8")


def _definition_rows() -> tuple[list[list[str]], str, bytes]:
    raw = DEFINITION_PATH.read_bytes()
    text = raw.decode("utf-8-sig")
    newline = "\r\n" if "\r\n" in text else "\n"
    bom = b"\xef\xbb\xbf" if raw.startswith(b"\xef\xbb\xbf") else b""
    return [line.split(";") for line in text.splitlines()], newline, bom


def _snap_anchor(mask: np.ndarray, x: float, y: float) -> tuple[int, int]:
    row = int(round(y))
    column = int(round(x))
    if 0 <= row < mask.shape[0] and 0 <= column < mask.shape[1] and mask[row, column]:
        return column, row
    sy, sx = _nearest_member(mask, y, x)
    return sx, sy


def geometry_layers(manifest: dict, sheet: np.ndarray) -> list[tuple[list[int], np.ndarray]]:
    """The reviewed geometry of each plan: its map origin and its RGBA crop.

    Stage 1 fills the rows of the raster above ``stage2.sheet_row`` and
    Stage 2 the rows below it. Stage 2 records the pixels it changes on the
    map Stage 1 left, those its state-line smoothing moved among them;
    transparent pixels stay as they are.
    """
    later = stage2_plan(manifest)
    if "sheet_row" not in later:
        return [(manifest["origin"], sheet)]
    split = int(later["sheet_row"])
    layers = [(manifest["origin"], sheet[:split])]
    if has_stage2_plan(manifest):
        layers.append((later["origin"], sheet[split:]))
    return layers


def planned_entries(manifest: dict) -> list[dict]:
    return [*manifest["provinces"], *stage2_plan(manifest).get("provinces", [])]


def stage2_towns(manifest: dict) -> frozenset[int]:
    return frozenset(int(town) for town in stage2_plan(manifest).get("towns", {}).values())


def stamp_layer(
    province_rgb: np.ndarray,
    geometry: np.ndarray,
    origin: Sequence[int],
    colours: dict[int, tuple[int, int, int]],
    scoped: frozenset[int],
) -> None:
    """Stamp one RGBA layer into provinces.bmp pixels, in place, inside the scope only."""
    x0, y0 = origin
    region = province_rgb[y0 : y0 + geometry.shape[0], x0 : x0 + geometry.shape[1]]
    geometry = geometry[: region.shape[0], : region.shape[1]]
    stamped = geometry[..., 3] > 0
    allowed = province_mask(packed_rgb(region), colours, scoped)
    if (stamped & ~allowed).any():
        raise RuntimeError("IVN province geometry would overwrite land outside its scope")
    region[stamped] = geometry[..., :3][stamped]


def expected_province_geometry() -> ProvinceGeometry:
    """Stamp the reviewed IVN and IIA province geometry and register its provinces."""
    rows, newline, bom = _definition_rows()
    by_id = {int(row[0]): row for row in rows if row[0].isdigit()}
    entries = sorted(planned_entries(PROVINCE_MANIFEST), key=lambda entry: entry["province"])
    issues: list[str] = []
    for entry in entries:
        province = int(entry["province"])
        row = by_id.get(province)
        if row is None:
            if province != max(by_id) + 1:
                raise RuntimeError(f"province {province}: non-contiguous IVN province ID")
            parent = by_id[int(entry["parent"])]
            row = [str(province), *map(str, entry["rgb"]), "land", "false", parent[6], parent[7]]
            rows.append(row)
            by_id[province] = row
        elif list(map(int, row[1:4])) != list(entry["rgb"]):
            raise RuntimeError(f"province {province}: ID is occupied by another colour")

    colours = {province: tuple(map(int, row[1:4])) for province, row in by_id.items()}
    scoped = province_ids_for_states(SCOPED_STATE_IDS) | {
        int(entry["province"]) for entry in entries
    }
    with Image.open(PROVINCES_PATH) as source:
        province_rgb = np.array(source.convert("RGB"))
    with Image.open(PROVINCE_GEOMETRY_PATH) as source:
        sheet = np.asarray(source.convert("RGBA"))
    layers = geometry_layers(PROVINCE_MANIFEST, sheet)
    before_stage2 = None
    for index, (origin, geometry) in enumerate(layers):
        if index == 1:
            before_stage2 = province_rgb.copy()
        stamp_layer(province_rgb, geometry, origin, colours, frozenset(scoped))
    x0 = min(origin[0] for origin, _geometry in layers)
    y0 = min(origin[1] for origin, _geometry in layers)
    width = max(origin[0] + geometry.shape[1] for origin, geometry in layers) - x0
    height = max(origin[1] + geometry.shape[0] for origin, geometry in layers) - y0
    region = province_rgb[y0 : y0 + height, x0 : x0 + width]
    lookup = {
        (red << 16) | (green << 8) | blue: province
        for province, (red, green, blue) in colours.items()
    }
    keys = packed_rgb(region)
    labels = np.zeros(keys.shape, np.int32)
    for key in np.unique(keys):
        labels[keys == key] = lookup.get(int(key), 0)
    sea_ids = [province for province, row in by_id.items() if row[4] == "sea"]
    coast = neighbours_of(np.isin(labels, sea_ids))
    masks = {province: labels == province for province in scoped}
    for province in sorted(scoped):
        if not masks[province].any():
            raise RuntimeError(f"province {province}: empty IVN geometry")
        by_id[province][5] = "true" if (masks[province] & coast).any() else "false"

    stack_text = UNITSTACKS_PATH.read_bytes().decode("utf-8")
    stack_newline = "\r\n" if "\r\n" in stack_text else "\n"
    stacks = [line.split(";") for line in stack_text.splitlines()]
    # Stage 1 provinces copy their parent's anchors; Stage 2 ones get native sets below.
    parents = {
        int(entry["province"]): int(entry["parent"])
        for entry in PROVINCE_MANIFEST["provinces"]
    }
    templates = {parent: [row for row in stacks if int(row[0]) == parent] for parent in set(parents.values())}
    existing = {int(row[0]) for row in stacks}
    with Image.open(HEIGHTMAP_PATH) as source:
        heights = np.asarray(source)
    map_height = province_rgb.shape[0]

    def place(row: list[str], province: int, x: float, y: float) -> None:
        sx, sy = _snap_anchor(masks[province], x - x0, y - y0)
        row[2] = f"{sx + x0:.2f}"
        row[3] = f"{heights[sy + y0, sx + x0] / 10:.2f}"
        row[4] = f"{map_height - 1 - (sy + y0):.2f}"

    for row in stacks:
        province = int(row[0])
        if province in masks:
            x = float(row[2])
            y = map_height - 1 - float(row[4])
            inside = masks[province]
            column = int(round(x)) - x0
            line = int(round(y)) - y0
            if not (0 <= line < inside.shape[0] and 0 <= column < inside.shape[1] and inside[line, column]):
                place(row, province, x, y)
    for province, parent in sorted(parents.items()):
        if province in existing:
            continue
        template = templates[parent]
        if not template:
            raise RuntimeError(f"province {parent}: no unit anchors to copy")
        ys, xs = np.nonzero(masks[province])
        cx, cy = xs.mean() + x0, ys.mean() + y0
        origin_x = float(template[0][2])
        origin_y = map_height - 1 - float(template[0][4])
        for source_row in template:
            row = source_row.copy()
            row[0] = str(province)
            place(
                row,
                province,
                cx + float(source_row[2]) - origin_x,
                cy + (map_height - 1 - float(source_row[4])) - origin_y,
            )
            stacks.append(row)
    if before_stage2 is not None:
        stacks = reconcile_stage2_anchors(
            stacks,
            province_rgb,
            before_stage2,
            colours,
            {province: row[4] for province, row in by_id.items()},
            heights,
        )
        issues.extend(stage2_geometry_issues(labels, by_id, MAP_ROOT))

    adjacency = province_adjacency(labels)
    land = {province for province, row in by_id.items() if row[4] == "land"}
    towns = stage2_towns(PROVINCE_MANIFEST)
    for city in sorted(CITY_PROVINCES):
        neighbours = adjacency.get(city, set()) & land
        minimum = STAGE2_TOWN_MIN_NEIGHBOURS if city in towns else CITY_MIN_NEIGHBOURS
        if len(neighbours) < minimum:
            issues.append(
                f"city province {city} borders only {len(neighbours)} land provinces"
            )
    railways = repair_railways(RAILWAYS_PATH.read_bytes(), adjacency, frozenset(scoped))
    encoded = BytesIO()
    Image.fromarray(province_rgb).save(encoded, format="BMP")
    definition = newline.join(";".join(row) for row in rows) + newline
    unitstacks = stack_newline.join(";".join(row) for row in stacks) + stack_newline
    return ProvinceGeometry(
        encoded.getvalue(),
        bom + definition.encode("utf-8"),
        unitstacks.encode("utf-8"),
        railways,
        tuple(issues),
    )


def province_geometry_issues() -> list[str]:
    expected_geometry = expected_province_geometry()
    issues = list(expected_geometry.issues)
    with Image.open(PROVINCES_PATH) as current, Image.open(
        BytesIO(expected_geometry.provinces)
    ) as planned:
        if not np.array_equal(
            np.asarray(current.convert("RGB")), np.asarray(planned.convert("RGB"))
        ):
            issues.append("map/provinces.bmp: IVN province geometry drifted")
    current_rows = DEFINITION_PATH.read_bytes().decode("utf-8-sig").splitlines()
    planned_rows = expected_geometry.definition.decode("utf-8-sig").splitlines()
    for before, after in zip_longest(current_rows, planned_rows):
        if before is None or after is None or before.split(";")[:6] != after.split(";")[:6]:
            issues.append("map/definition.csv: IVN province rows drifted")
            break
    stacks = UNITSTACKS_PATH.read_bytes().decode("utf-8").splitlines()
    planned_stacks = expected_geometry.unitstacks.decode("utf-8").splitlines()
    if len(stacks) != len(planned_stacks) or any(
        before.split(";")[:3] + before.split(";")[4:]
        != after.split(";")[:3] + after.split(";")[4:]
        for before, after in zip(stacks, planned_stacks)
    ):
        issues.append("map/unitstacks.txt: IVN unit anchors drifted")
    if RAILWAYS_PATH.read_bytes() != expected_geometry.railways:
        issues.append("map/railways.txt: IVN railway segments are not adjacent")
    return issues


def apply_province_geometry() -> None:
    expected_geometry = expected_province_geometry()
    PROVINCES_PATH.write_bytes(expected_geometry.provinces)
    DEFINITION_PATH.write_bytes(expected_geometry.definition)
    UNITSTACKS_PATH.write_bytes(expected_geometry.unitstacks)
    RAILWAYS_PATH.write_bytes(expected_geometry.railways)


def river_issues(
    rivers: np.ndarray,
    paths: list[list[tuple[int, int]]],
    packed: np.ndarray,
    water: np.ndarray,
) -> list[str]:
    border = province_borders(packed)
    issues = []
    for number, path in enumerate(paths, start=1):
        cells = set(path)
        if rivers[path[0][1], path[0][0]] != RIVER_SOURCE_PALETTE:
            issues.append(f"river {number}: source pixel is not palette 0")
        off_border = sum(not border[y, x] for x, y in path)
        if off_border:
            issues.append(f"river {number}: {off_border} pixels cross province interiors")
        for (ax, ay), (bx, by) in zip(path, path[1:]):
            if abs(ax - bx) + abs(ay - by) != 1:
                issues.append(f"river {number}: course is not 4-connected at {(ax, ay)}")
                break
        branching = [
            (x, y)
            for x, y in path
            if sum((n in cells) for n in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1))) > 2
        ]
        if branching:
            issues.append(f"river {number}: branches at {branching[:3]}")
        mx, my = path[-1]
        if not water[my - 1 : my + 2, mx - 1 : mx + 2].any():
            issues.append(f"river {number}: mouth {(mx, my)} does not reach the sea")
    return issues


def _build_expected() -> GeographyOutputs:
    lines, newline, bom, province_colors, declared = definition_contract()
    palette = palette_types()
    color_to_id = {color: province_id for province_id, color in province_colors.items()}
    if len(color_to_id) != len(province_colors):
        raise RuntimeError("definition.csv: duplicate RGB inside IVN/IIA scope")

    with (
        Image.open(BytesIO(TERRAIN_PATH.read_bytes())) as terrain_source,
        Image.open(BytesIO(CITIES_PATH.read_bytes())) as cities_source,
        Image.open(BytesIO(PROVINCES_PATH.read_bytes())) as provinces_source,
    ):
        if terrain_source.mode != "P" or terrain_source.size != provinces_source.size:
            raise RuntimeError(
                "terrain.bmp must be paletted and match provinces.bmp dimensions"
            )
        if cities_source.mode != "P" or cities_source.size != terrain_source.size:
            raise RuntimeError(
                "cities.bmp must be paletted and match terrain.bmp dimensions"
            )
        terrain_original = terrain_source.copy()
        cities_original = cities_source.copy()
        terrain_pixels = bytearray(terrain_source.get_flattened_data())
        city_pixels = bytearray(cities_source.get_flattened_data())
        province_rgb = np.asarray(provinces_source.convert("RGB"))
        province_bytes = province_rgb.tobytes()
        masks = landscape_masks(provinces_source, province_colors)
    water = water_mask(province_rgb, water_colours(DEFINITION_PATH))
    shore_blocked = urban_blocked(water, province_rgb, DEFINITION_PATH).reshape(-1)
    packed = packed_rgb(province_rgb)
    relief = province_mask(
        packed, province_colors, relief_province_ids(RELIEF_STATE_IDS)
    )
    march = province_mask(
        packed, province_colors, relief_province_ids(MARCH_RELIEF_STATE_IDS)
    )
    authored_rivers = province_mask(packed, province_colors, AUTHORED_RIVER_PROVINCES)
    island_provinces = province_ids_for_states(ISLAND_HEIGHT_STATE_IDS)
    if island_provinces != ISLAND_PROVINCE_TERRAIN.keys():
        raise RuntimeError(
            "ISLAND_PROVINCE_TERRAIN must list exactly the island provinces: "
            f"missing {sorted(island_provinces - ISLAND_PROVINCE_TERRAIN.keys())}, "
            f"extra {sorted(ISLAND_PROVINCE_TERRAIN.keys() - island_provinces)}"
        )
    unknown_types = sorted(set(ISLAND_PROVINCE_TERRAIN.values()) - ISLAND_RELIEF.keys())
    if unknown_types:
        raise RuntimeError(f"island terrain types without relief: {unknown_types}")
    island_terrain = np.full(relief.shape, -1, np.int8)
    for index, terrain_type in enumerate(ISLAND_RELIEF):
        type_provinces = frozenset(
            province_id
            for province_id, declared_type in ISLAND_PROVINCE_TERRAIN.items()
            if declared_type == terrain_type
        )
        if type_provinces:
            island_terrain[province_mask(packed, province_colors, type_provinces)] = index

    with Image.open(BytesIO(RIVERS_PATH.read_bytes())) as river_source:
        island_rivers = np.asarray(river_source)
    with Image.open(BytesIO(HEIGHTMAP_PATH.read_bytes())) as height_source:
        if height_source.mode != "L" or height_source.size != terrain_original.size:
            raise RuntimeError(
                "heightmap.bmp must use mode L and match provinces.bmp dimensions"
            )
        source_heights = np.asarray(height_source)
    stage2 = has_stage2_plan(PROVINCE_MANIFEST)
    if stage2:
        # The island valleys follow the settled courses within the same pass,
        # so a second pass finds nothing to move.
        scope_ids = all_province_grid(province_rgb)
        scope_mask = province_mask(packed, province_colors, frozenset(province_colors))
        settlement_mask = province_mask(packed, province_colors, SETTLEMENT_PROVINCES)
        island_rivers = settle_stage2_rivers(
            island_rivers,
            scope_ids,
            scope_mask,
            relief & ~authored_rivers,
            settlement_mask,
            water,
            source_heights,
        )
    island_heights = render_island_heights(
        source_heights, island_terrain, masks.island_bbox, island_rivers
    )
    relief_heights, fen = render_relief_heights(island_heights, relief, water)
    heightmap = Image.fromarray(relief_heights)
    island = np.frombuffer(bytes(masks.island), dtype=np.uint8).reshape(relief.shape) > 0
    normal_scope = bytearray((island | relief).astype(np.uint8).tobytes())
    with Image.open(BytesIO(WORLD_NORMAL_PATH.read_bytes())) as normal_source:
        if normal_source.mode != "RGB":
            raise RuntimeError("world_normal.bmp must use mode RGB")
        world_normal = normal_from_height(heightmap, normal_source, normal_scope)

    province_by_pixel = array("H", [0]) * len(terrain_pixels)
    settlement_indices = {province_id: [] for province_id in SETTLEMENT_PROVINCES}
    for index in range(len(terrain_pixels)):
        color = tuple(province_bytes[index * 3 : index * 3 + 3])
        province_id = color_to_id.get(color)
        if province_id is None:
            continue
        province_by_pixel[index] = province_id
        if province_id in settlement_indices:
            settlement_indices[province_id].append(index)

    missing_settlements = sorted(SETTLEMENT_PROVINCES - province_colors.keys())
    if missing_settlements:
        raise RuntimeError(
            f"settlement provinces outside IVN/IIA scope: {missing_settlements}"
        )

    priority = {
        terrain_type: len(TERRAIN_PRIORITY) - rank
        for rank, terrain_type in enumerate(TERRAIN_PRIORITY)
    }
    # A settlement is urban in its entirety; the shoreline clearance below
    # keeps its city meshes out of the sea.
    footprints = {
        province_id: set(indices) for province_id, indices in settlement_indices.items()
    }
    # Every settlement carries the western houses, except on the shoreline
    # band, where city meshes would float over the water.
    house_pixels = bytearray(city_pixels)
    for footprint in footprints.values():
        for index in footprint:
            if not shore_blocked[index]:
                house_pixels[index] = CITY_PALETTE_INDEX
    cities = cities_original.copy()
    cities.putdata(bytes(house_pixels))
    working_pixels = bytearray(terrain_pixels)
    for footprint in footprints.values():
        for index in footprint:
            working_pixels[index] = URBAN_PALETTE
    # On the IVN mainland only city provinces are urban. Former settlement
    # footprints left in rural provinces return to the province's own biome.
    working_array = np.frombuffer(working_pixels, dtype=np.uint8).reshape(relief.shape)
    rural_urban = (
        relief
        & (working_array == URBAN_PALETTE)
        & ~province_mask(packed, province_colors, SETTLEMENT_PROVINCES)
    )
    if rural_urban.any():
        stale_ids = np.frombuffer(province_by_pixel, dtype=np.uint16).reshape(relief.shape)
        for province_id in np.unique(stale_ids[rural_urban]):
            inside = stale_ids == province_id
            biome = working_array[inside & (working_array != URBAN_PALETTE)]
            biome = biome[~np.isin(biome, list(WATER_PALETTES))]
            base = int(np.bincount(biome).argmax()) if len(biome) else PLAINS_PALETTE
            for index in np.flatnonzero(inside & rural_urban):
                working_pixels[index] = base
    # Clear the shoreline band before rendering as well, so neighbourhood-aware
    # rendering sees identical input on every pass.
    for index, province_id in enumerate(province_by_pixel):
        if (
            province_id
            and working_pixels[index] == URBAN_PALETTE
            and shore_blocked[index]
        ):
            working_pixels[index] = URBAN_FALLBACK_PALETTE
    working = terrain_original.copy()
    working.putdata(working_pixels)
    terrain = render_northern_terrain(
        working,
        heightmap,
        masks.north,
        masks.state_by_pixel,
        footprints,
    )
    march_pixels = classify_march_terrain(
        np.asarray(terrain),
        relief_heights,
        march,
        relief,
        fen,
        ellipse_mask(relief.shape, FOREST_ZONES) & march,
        palette,
    )
    terrain.putdata(march_pixels.tobytes())
    generated_pixels = bytearray(terrain.get_flattened_data())
    shore_cleared: set[int] = set()
    for index, province_id in enumerate(province_by_pixel):
        if not province_id:
            continue
        if city_pixels[index] in CITY_PALETTE_INDICES:
            generated_pixels[index] = URBAN_PALETTE
        if (
            generated_pixels[index] == URBAN_PALETTE
            and shore_blocked[index]
        ):
            generated_pixels[index] = URBAN_FALLBACK_PALETTE
            shore_cleared.add(index)
    painted = np.frombuffer(bytes(generated_pixels), dtype=np.uint8).reshape(relief.shape).copy()
    province_ids = np.frombuffer(province_by_pixel, dtype=np.uint16).reshape(relief.shape)
    city_array = np.frombuffer(city_pixels, dtype=np.uint8).reshape(relief.shape)
    shore_array = shore_blocked.reshape(relief.shape)
    # Every island province is painted in its declared terrain.
    paint_provinces(
        painted,
        island,
        province_ids,
        city_array,
        {
            province_id: ISLAND_TERRAIN_PALETTES[terrain_type]
            for province_id, terrain_type in ISLAND_PROVINCE_TERRAIN.items()
        },
        shore_array,
    )
    generated_pixels = bytearray(painted.tobytes())
    terrain.putdata(generated_pixels)

    counts = {province_id: Counter() for province_id in province_colors}
    for index, province_id in enumerate(province_by_pixel):
        if not province_id:
            continue
        terrain_type = palette.get(generated_pixels[index])
        if terrain_type is None:
            raise RuntimeError(
                f"province {province_id}: unknown graphical terrain palette {generated_pixels[index]}"
            )
        # The shoreline band is cosmetic clearance: in a province declared
        # urban, its cleared pixels still count as city.
        if (
            shore_blocked[index]
            and generated_pixels[index] == URBAN_FALLBACK_PALETTE
            and ISLAND_PROVINCE_TERRAIN.get(province_id, declared.get(province_id))
            == "urban"
        ):
            terrain_type = "urban"
        if terrain_type not in WATER_TYPES:
            counts[province_id][terrain_type] += 1

    desired: dict[int, str] = {}
    for province_id, terrain_counts in counts.items():
        if not terrain_counts:
            raise RuntimeError(f"province {province_id}: no painted land terrain")
        desired[province_id] = max(
            terrain_counts,
            key=lambda terrain_type: (
                terrain_counts[terrain_type],
                priority.get(terrain_type, 0),
            ),
        )
    for province_id in SETTLEMENT_PROVINCES:
        desired[province_id] = "urban"
    desired.update(ISLAND_PROVINCE_TERRAIN)

    # Every IVN mainland province is painted in its one terrain type, so the
    # map reads province by province and matches the declared terrain. The
    # detached islands keep their authored relief, not their old textures.
    relief_ids = relief_province_ids(RELIEF_STATE_IDS) - SETTLEMENT_PROVINCES
    for province_id in relief_ids:
        desired[province_id] = province_terrain_type(counts[province_id])
    detached = {
        province_id
        for province_id in RELIEF_EXCLUDED_PROVINCES - SETTLEMENT_PROVINCES
        if desired.get(province_id) in UNIFORM_TERRAIN_PALETTES
    }
    paint_provinces(
        painted,
        relief | province_mask(packed, province_colors, frozenset(detached)),
        province_ids,
        city_array,
        {
            province_id: UNIFORM_TERRAIN_PALETTES[desired[province_id]]
            for province_id in relief_ids | detached
        },
        shore_array,
    )
    generated_pixels = bytearray(painted.tobytes())
    terrain.putdata(generated_pixels)

    with Image.open(BytesIO(TREES_PATH.read_bytes())) as tree_source:
        if tree_source.mode != "P" or tree_source.size != (1650, 600):
            raise RuntimeError("trees.bmp must remain paletted at 1650x600")
        tree_palette = tree_source.getpalette()
        tree_states = np.frombuffer(bytes(masks.state_by_pixel), dtype=np.uint16).copy()
        for state_id in sorted(MARCH_RELIEF_STATE_IDS):
            state_pixels = province_mask(
                packed, province_colors, relief_province_ids(frozenset({state_id}))
            )
            tree_states[state_pixels.reshape(-1)] = state_id
        trees, tree_counts, forbidden_trees, outside_tree_changes = (
            _render_trees_with_metrics(
                tree_source,
                terrain,
                array("H", tree_states.tobytes()),
                palette,
                tree_cells_blocked(water, tree_source.width, tree_source.height),
            )
        )
        if trees.getpalette() != tree_palette:
            raise RuntimeError("trees.bmp palette changed during generation")

    mountain_pixels = 0
    hill_pixels = 0
    for index, state_id in enumerate(masks.state_by_pixel):
        if not state_id:
            continue
        if generated_pixels[index] == MOUNTAIN_PALETTE:
            mountain_pixels += 1
        elif generated_pixels[index] == HILLS_PALETTE:
            hill_pixels += 1
    tree_occupancy = {
        terrain_type: (
            tree_counts.get(terrain_type, (0, 0))[1]
            / tree_counts.get(terrain_type, (1, 0))[0]
        )
        for terrain_type in ("forest", "plains", "hills", "marsh")
    }

    coast_distances = distance_from_edge(masks.north, terrain.width, terrain.height)
    transition_violations = 0
    relief_pixels = relief.reshape(-1)
    mountains = {
        index
        for index, included in enumerate(masks.north)
        if included
        and not relief_pixels[index]
        and generated_pixels[index] == MOUNTAIN_PALETTE
    }
    for index in mountains:
        for neighbour in pixel_neighbours(index, terrain.width, len(generated_pixels)):
            if not masks.north[neighbour] or relief_pixels[neighbour]:
                continue
            neighbour_value = generated_pixels[neighbour]
            if neighbour_value == URBAN_PALETTE or 0 <= coast_distances[neighbour] < 2:
                continue
            if neighbour_value not in (MOUNTAIN_PALETTE, HILLS_PALETTE):
                transition_violations += 1
    components_without_shoulders = 0
    remaining = set(mountains)
    while remaining:
        component = {remaining.pop()}
        frontier = list(component)
        while frontier:
            index = frontier.pop()
            connected = (
                set(pixel_neighbours(index, terrain.width, len(generated_pixels)))
                & remaining
            )
            remaining.difference_update(connected)
            component.update(connected)
            frontier.extend(connected)
        if not any(
            generated_pixels[neighbour] == HILLS_PALETTE
            for index in component
            for neighbour in pixel_neighbours(
                index, terrain.width, len(generated_pixels)
            )
        ):
            components_without_shoulders += 1
    adjacency = province_adjacency(province_ids)
    bare_mountains = sorted(
        province_id
        for province_id in relief_ids
        if desired[province_id] == "mountain"
        and not any(
            desired.get(neighbour) in ("hills", "mountain")
            for neighbour in adjacency.get(province_id, ())
        )
    )

    outside_terrain_changes = 0
    for index, (before, after) in enumerate(zip(terrain_pixels, generated_pixels)):
        if before == after or masks.north[index] or relief_pixels[index]:
            continue
        if index in shore_cleared and before == URBAN_PALETTE:
            continue
        province_id = province_by_pixel[index]
        if (
            province_id not in SETTLEMENT_PROVINCES
            or index not in footprints[province_id]
        ):
            outside_terrain_changes += 1
    metrics = CoverageMetrics(
        tree_occupancy=tree_occupancy,
        forbidden_tree_cells=forbidden_trees,
        terrain_changes_outside_scope=outside_terrain_changes,
        tree_changes_outside_scope=outside_tree_changes,
        mountain_pixels=mountain_pixels,
        hill_pixels=hill_pixels,
        mountain_transition_violations=transition_violations,
        mountain_components_without_shoulders=components_without_shoulders,
        mountain_provinces_without_foothills=tuple(bare_mountains),
    )

    with Image.open(BytesIO(RIVERS_PATH.read_bytes())) as river_source:
        if river_source.mode != "P" or river_source.size != terrain.size:
            raise RuntimeError("rivers.bmp must be paletted and match terrain.bmp dimensions")
        river_pixels, river_paths = route_rivers(
            island_rivers,
            packed,
            relief,
            authored_rivers,
            water,
            relief_heights,
            scope_ids if stage2 else None,
            settlement_mask if stage2 else None,
        )
        rivers = river_source.copy()
    rivers.putdata(river_pixels.tobytes())
    all_river_issues = river_issues(river_pixels, river_paths, packed, water)
    if stage2:
        all_river_issues += stage2_river_issues(
            river_pixels,
            scope_ids,
            scope_mask,
            province_mask(packed, province_colors, stage2_urban_provinces(PROVINCE_MANIFEST)),
            water,
        )

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
        trees=trees,
        cities=cities,
        rivers=rivers,
        unitstacks=relief_unit_anchors(
            UNITSTACKS_PATH.read_bytes(),
            relief_province_ids(RELIEF_STATE_IDS) | island_provinces,
            relief_heights,
            water,
        ),
        river_issues=all_river_issues,
        desired=desired,
        counts=counts,
        footprints=footprints,
        metrics=metrics,
    )


_EXPECTED_SIGNATURE: tuple[tuple[int, int], ...] | None = None
_EXPECTED_OUTPUTS: GeographyOutputs | None = None


def expected() -> GeographyOutputs:
    global _EXPECTED_SIGNATURE, _EXPECTED_OUTPUTS
    input_paths = (
        TERRAIN_PATH,
        TREES_PATH,
        PROVINCES_PATH,
        DEFINITION_PATH,
        HEIGHTMAP_PATH,
        WORLD_NORMAL_PATH,
        RIVERS_PATH,
        UNITSTACKS_PATH,
        TERRAIN_CONFIG_PATH,
        *(state_path(state_id) for state_id in sorted(SCOPED_STATE_IDS)),
    )
    signature = tuple(
        (path.stat().st_mtime_ns, path.stat().st_size) for path in input_paths
    )
    if signature != _EXPECTED_SIGNATURE or _EXPECTED_OUTPUTS is None:
        _EXPECTED_OUTPUTS = _build_expected()
        _EXPECTED_SIGNATURE = signature
    return _EXPECTED_OUTPUTS


def coverage_issues(outputs: GeographyOutputs) -> list[str]:
    metrics = outputs.metrics
    issues: list[str] = []
    for province_id in metrics.mountain_provinces_without_foothills:
        issues.append(f"mountain province {province_id} has no hills or mountain neighbour")
    occupancy = metrics.tree_occupancy
    for terrain_type, minimum, maximum in (
        ("forest", 0.50, 0.72),
        ("plains", 0.02, 0.07),
        ("hills", 0.01, 0.05),
    ):
        if not minimum <= occupancy[terrain_type] <= maximum:
            issues.append(
                f"{terrain_type} tree occupancy {occupancy[terrain_type]:.4f} "
                f"is outside {minimum:.2f}..{maximum:.2f}"
            )
    if occupancy["hills"] >= occupancy["plains"]:
        issues.append("hills tree occupancy is not lower than plains occupancy")
    if occupancy["hills"] > occupancy["forest"] / 5:
        issues.append("hills tree occupancy exceeds one fifth of forest occupancy")
    if metrics.forbidden_tree_cells:
        issues.append(
            f"map/trees.bmp: {metrics.forbidden_tree_cells} generated cells sample water, urban, or mountain"
        )
    if metrics.terrain_changes_outside_scope:
        issues.append(
            f"map/terrain.bmp: {metrics.terrain_changes_outside_scope} changes escape the north/settlement scope"
        )
    if metrics.tree_changes_outside_scope:
        issues.append(
            f"map/trees.bmp: {metrics.tree_changes_outside_scope} changes escape the approved low-resolution mask"
        )
    if metrics.mountain_transition_violations:
        issues.append(
            f"map/terrain.bmp: {metrics.mountain_transition_violations} interior mountain edges lack a hill shoulder"
        )
    if metrics.mountain_components_without_shoulders:
        issues.append(
            f"map/terrain.bmp: {metrics.mountain_components_without_shoulders} mountain components lack a hill shoulder"
        )
    return issues


def validate(outputs: GeographyOutputs | None = None) -> list[str]:
    outputs = outputs or expected()
    issues: list[str] = []
    with Image.open(BytesIO(TERRAIN_PATH.read_bytes())) as current:
        differences = sum(
            before != after
            for before, after in zip(
                current.get_flattened_data(), outputs.terrain.get_flattened_data()
            )
        )
    if differences:
        issues.append(f"map/terrain.bmp: {differences} northern terrain pixels drifted")
    with Image.open(BytesIO(HEIGHTMAP_PATH.read_bytes())) as current:
        differences = sum(
            before != after
            for before, after in zip(
                current.get_flattened_data(), outputs.heightmap.get_flattened_data()
            )
        )
    if differences:
        issues.append(f"map/heightmap.bmp: {differences} island height pixels drifted")
    with Image.open(BytesIO(WORLD_NORMAL_PATH.read_bytes())) as current:
        differences = sum(
            before != after
            for before, after in zip(
                current.get_flattened_data(), outputs.world_normal.get_flattened_data()
            )
        )
    if differences:
        issues.append(
            f"map/world_normal.bmp: {differences} island normal cells drifted"
        )
    with Image.open(BytesIO(TREES_PATH.read_bytes())) as current:
        if current.mode != "P" or current.size != (1650, 600):
            issues.append(
                f"map/trees.bmp: expected mode P at 1650x600, found {current.mode} at {current.size}"
            )
        if current.getpalette() != outputs.trees.getpalette():
            issues.append("map/trees.bmp: palette bytes drifted")
        differences = sum(
            before != after
            for before, after in zip(
                current.get_flattened_data(), outputs.trees.get_flattened_data()
            )
        )
    if differences:
        issues.append(f"map/trees.bmp: {differences} northern tree cells drifted")
    with Image.open(BytesIO(CITIES_PATH.read_bytes())) as current:
        if current.getpalette() != outputs.cities.getpalette():
            issues.append("map/cities.bmp: palette bytes drifted")
        differences = sum(
            before != after
            for before, after in zip(
                current.get_flattened_data(), outputs.cities.get_flattened_data()
            )
        )
    if differences:
        issues.append(f"map/cities.bmp: {differences} IVN/IIA settlement house pixels drifted")
    river_data = RIVERS_PATH.read_bytes()
    river_header = river_data[:RIVER_BMP_HEADER_SIZE]
    if river_header != native_river_bmp(river_header):
        issues.append("map/rivers.bmp: the full palette must use implicit BMP colour counts")
    with Image.open(BytesIO(river_data)) as current:
        if current.getpalette() != outputs.rivers.getpalette():
            issues.append("map/rivers.bmp: palette bytes drifted")
        differences = sum(
            before != after
            for before, after in zip(
                current.get_flattened_data(), outputs.rivers.get_flattened_data()
            )
        )
    if differences:
        issues.append(f"map/rivers.bmp: {differences} IVN river pixels drifted")
    issues.extend(f"map/rivers.bmp: {issue}" for issue in outputs.river_issues)
    if UNITSTACKS_PATH.read_bytes() != outputs.unitstacks:
        issues.append("map/unitstacks.txt: IVN/IIA relief unit heights drifted")
    current_definition = DEFINITION_PATH.read_bytes().decode("utf-8-sig").splitlines()
    expected_definition = outputs.definition.decode("utf-8-sig").splitlines()
    definition_differences = sum(
        before != after
        for before, after in zip_longest(current_definition, expected_definition)
    )
    if definition_differences:
        issues.append(
            f"map/definition.csv: {definition_differences} IVN/IIA declared terrain rows drifted"
        )
    for province_id in sorted(outputs.footprints):
        if outputs.desired[province_id] != "urban":
            issues.append(f"settlement province {province_id} is not declared urban")
    issues.extend(coverage_issues(outputs))
    return issues


def native_river_bmp(data: bytes) -> bytes:
    """Use the river loader's implicit 256-colour table in a BMP or its header."""
    if (
        len(data) < RIVER_BMP_HEADER_SIZE
        or data[:2] != b"BM"
        or int.from_bytes(data[28:30], "little") != 8
        or int.from_bytes(data[10:14], "little") < RIVER_BMP_HEADER_SIZE + 256 * 4
    ):
        raise ValueError("rivers.bmp requires an 8-bit bitmap with a full palette")
    if data[46:54] == bytes(8):
        return data
    return data[:46] + bytes(8) + data[54:]


def atomic_save_bmp(image: Image.Image, path: Path) -> None:
    temporary = path.with_suffix(".bmp.tmp")
    try:
        image.save(temporary, format="BMP")
        with temporary.open("r+b") as generated:
            if path == RIVERS_PATH:
                header = native_river_bmp(generated.read(RIVER_BMP_HEADER_SIZE))
                generated.seek(0)
                generated.write(header)
            generated.flush()
            os.fsync(generated.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def apply() -> None:
    apply_province_geometry()
    outputs = expected()
    atomic_save_bmp(outputs.terrain, TERRAIN_PATH)
    atomic_save_bmp(outputs.trees, TREES_PATH)
    atomic_save_bmp(outputs.cities, CITIES_PATH)
    atomic_save_bmp(outputs.rivers, RIVERS_PATH)
    UNITSTACKS_PATH.write_bytes(outputs.unitstacks)
    atomic_save_bmp(outputs.heightmap, HEIGHTMAP_PATH)
    atomic_save_bmp(outputs.world_normal, WORLD_NORMAL_PATH)
    DEFINITION_PATH.write_bytes(outputs.definition)


# Inputs the IVN pass reads, relative to the root, by the module path they feed.
ROOT_PATHS = {
    "TERRAIN_PATH": "map/terrain.bmp",
    "TREES_PATH": "map/trees.bmp",
    "CITIES_PATH": "map/cities.bmp",
    "PROVINCES_PATH": "map/provinces.bmp",
    "DEFINITION_PATH": "map/definition.csv",
    "HEIGHTMAP_PATH": "map/heightmap.bmp",
    "WORLD_NORMAL_PATH": "map/world_normal.bmp",
    "RIVERS_PATH": "map/rivers.bmp",
    "UNITSTACKS_PATH": "map/unitstacks.txt",
    "RAILWAYS_PATH": "map/railways.txt",
    "TERRAIN_CONFIG_PATH": "common/terrain/00_terrain.txt",
    "PROVINCE_MANIFEST_PATH": "tools/data/adiscord_ivn_provinces.json",
    "PROVINCE_GEOMETRY_PATH": "tools/data/adiscord_ivn_province_geometry.png",
}


def use_root(root: Path) -> None:
    """Point every map, state and manifest path of this module at ``root``.

    The manifest tables follow the manifest found there. Only the Stage 2
    dry run moves the root, to copies outside the repository.
    """
    global MAP_ROOT, STATE_DIR, PROVINCE_MANIFEST, ISLAND_PROVINCE_TERRAIN, CITY_PROVINCES
    global ISLAND_URBAN_PROVINCES, SETTLEMENT_PROVINCES, RELIEF_EXCLUDED_PROVINCES
    global AUTHORED_RIVER_PROVINCES, _EXPECTED_SIGNATURE, _EXPECTED_OUTPUTS
    MAP_ROOT = root
    for name, relative in ROOT_PATHS.items():
        globals()[name] = root / relative
    STATE_DIR = root / "history/states"
    PROVINCE_MANIFEST = json.loads(
        (root / ROOT_PATHS["PROVINCE_MANIFEST_PATH"]).read_text(encoding="utf-8")
    )
    tables = manifest_tables(PROVINCE_MANIFEST)
    ISLAND_PROVINCE_TERRAIN = tables.island_terrain
    CITY_PROVINCES = tables.city_provinces
    ISLAND_URBAN_PROVINCES = tables.island_urban
    SETTLEMENT_PROVINCES = CITY_PROVINCES | ISLAND_URBAN_PROVINCES
    RELIEF_EXCLUDED_PROVINCES = tables.relief_excluded
    AUTHORED_RIVER_PROVINCES = tables.authored_rivers
    _EXPECTED_SIGNATURE = None
    _EXPECTED_OUTPUTS = None


def copy_dry_run_inputs(directory: Path) -> None:
    """Copy the inputs of the IVN pass into ``directory`` as plain files; the plan stays.

    A copy is never a link, so no write in the directory reaches the map.
    """
    sources = [
        relative
        for name, relative in ROOT_PATHS.items()
        if name not in ("PROVINCE_MANIFEST_PATH", "PROVINCE_GEOMETRY_PATH")
    ]
    sources += [
        state_path(state_id).relative_to(REPOSITORY_ROOT).as_posix()
        for state_id in sorted(SCOPED_STATE_IDS)
    ]
    sources += [
        path.relative_to(REPOSITORY_ROOT).as_posix()
        for path in sorted((REPOSITORY_ROOT / "history/units").glob("*.txt"))
    ]
    sources.append("map/supply_nodes.txt")
    for relative in sources:
        target = directory / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(REPOSITORY_ROOT / relative, target)


def off_border_river_pixels(rivers: np.ndarray, labels: np.ndarray, scope: np.ndarray) -> int:
    river = rivers < RIVER_SEA_PALETTE
    return int((river & scope & ~province_borders(labels)).sum())


def scope_statistics(root_labels: np.ndarray, rivers: np.ndarray, definition: bytes) -> dict:
    """Province, terrain and river counts of the IVN/IIA scope on one map state."""
    coastal = _coastal()
    scope_ids = province_ids_for_states(SCOPED_STATE_IDS)
    scope = np.isin(root_labels, sorted(scope_ids))
    terrain = Counter(
        fields[6]
        for fields in (line.split(";") for line in definition.decode("utf-8-sig").splitlines())
        if fields[0].isdigit() and int(fields[0]) in scope_ids
    )
    river = rivers < RIVER_SEA_PALETTE
    turns = river & state_line_turns(root_labels, scope)
    return {
        "provinces": len(set(np.unique(root_labels[scope]).tolist())),
        "state_line_turn_pixels": int(turns.sum()),
        "terrain": dict(sorted(terrain.items())),
        "borders": coastal.province_border_count(root_labels),
        "off_border_river_pixels": off_border_river_pixels(rivers, root_labels, scope),
        "river_pixels": int((river & scope).sum()),
        "river_palettes": {
            str(palette): count for palette, count in sorted(Counter(rivers[river & scope].tolist()).items())
        },
    }


def dry_run_stage2(directory: Path) -> dict:
    """Apply the Stage 2 plan in ``directory`` to copies of the map and report the result.

    The plan comes from ``--plan-stage2-provinces --output-root`` with the
    same directory. The pass runs twice: the first writes the copies, the
    second must find nothing left to change. Previews of relief, rivers,
    settlements, terrain and splits are written to ``directory/previews``.
    """
    directory = directory.resolve()
    if directory == REPOSITORY_ROOT or REPOSITORY_ROOT in directory.parents:
        raise RuntimeError("the Stage 2 dry run needs a directory outside the repository")
    planned = json.loads(
        (directory / ROOT_PATHS["PROVINCE_MANIFEST_PATH"]).read_text(encoding="utf-8")
    )
    if not has_stage2_plan(planned):
        raise RuntimeError(f"{directory}: no Stage 2 plan; run --plan-stage2-provinces --output-root first")
    copy_dry_run_inputs(directory)
    use_root(directory)
    try:
        written = [globals()[name] for name in ROOT_PATHS]
        if any(directory not in Path(path).resolve().parents for path in written):
            raise RuntimeError("a dry-run output would leave the dry-run directory")
        with Image.open(BytesIO(PROVINCES_PATH.read_bytes())) as source:
            before = all_province_grid(np.asarray(source.convert("RGB")))
        with Image.open(BytesIO(RIVERS_PATH.read_bytes())) as source:
            before_rivers = np.asarray(source).copy()
        before_stats = scope_statistics(before, before_rivers, DEFINITION_PATH.read_bytes())
        apply()
        issues = province_geometry_issues()
        issues += validate()
        with Image.open(BytesIO(PROVINCES_PATH.read_bytes())) as source:
            after = all_province_grid(np.asarray(source.convert("RGB")))
        outputs = expected()
        after_rivers = np.asarray(outputs.rivers)
        after_stats = scope_statistics(after, after_rivers, outputs.definition)
        previews = write_stage2_previews(directory / "previews", before, after, outputs)
        return {
            "before": before_stats,
            "after": after_stats,
            "issues_after_one_pass": issues,
            "previews": [path.as_posix() for path in previews],
        }
    finally:
        use_root(REPOSITORY_ROOT)


TERRAIN_PREVIEW_COLOURS = {
    "plains": (196, 214, 140),
    "forest": (62, 120, 60),
    "hills": (176, 150, 100),
    "mountain": (130, 110, 100),
    "marsh": (90, 140, 130),
    "urban": (210, 60, 60),
}
RIVER_PREVIEW_COLOUR = (40, 90, 220)
CITY_PREVIEW_COLOUR = (220, 40, 40)
TOWN_PREVIEW_COLOUR = (250, 150, 30)


def _preview_crop(scope: np.ndarray) -> tuple[slice, slice]:
    ys, xs = np.nonzero(scope)
    return (
        slice(max(0, int(ys.min()) - 6), int(ys.max()) + 7),
        slice(max(0, int(xs.min()) - 6), int(xs.max()) + 7),
    )


def _scaled(image: np.ndarray) -> Image.Image:
    picture = Image.fromarray(image.astype(np.uint8), "RGB")
    return picture.resize(
        (picture.width * STAGE2_PREVIEW_SCALE, picture.height * STAGE2_PREVIEW_SCALE), Image.NEAREST
    )


def _label_settlements(picture: Image.Image, labels: np.ndarray, crop: tuple[slice, slice]) -> None:
    """Write the English name of every planned settlement beside it."""
    draw = ImageDraw.Draw(picture)
    for settlement in stage2_plan(PROVINCE_MANIFEST).get("settlements", []):
        ys, xs = np.nonzero(labels[crop] == int(settlement["province"]))
        if not len(xs):
            continue
        x = int(xs.mean()) * STAGE2_PREVIEW_SCALE + 6
        y = int(ys.mean()) * STAGE2_PREVIEW_SCALE - 4
        text = f"{settlement['name_en']} ({settlement['value']})"
        draw.text((x + 1, y + 1), text, fill=(0, 0, 0))
        draw.text((x, y), text, fill=(255, 255, 255))


def write_stage2_previews(
    directory: Path, before: np.ndarray, after: np.ndarray, outputs: GeographyOutputs
) -> list[Path]:
    """Relief with rivers and settlements, terrain per province, and the splits before and after."""
    directory.mkdir(parents=True, exist_ok=True)
    scope_ids = province_ids_for_states(SCOPED_STATE_IDS)
    scope = np.isin(after, sorted(scope_ids))
    crop = _preview_crop(scope)
    labels = after[crop]
    inside = scope[crop]
    borders = province_borders(labels) & inside
    plan = stage2_plan(PROVINCE_MANIFEST)
    cities = np.isin(labels, [int(city) for city in CITY_PROVINCES]) & inside
    towns = np.isin(labels, [int(town) for town in plan.get("towns", {}).values()])
    heights = np.asarray(outputs.heightmap)[crop].astype(float)
    shade = np.clip((heights - HEIGHT_MIN) / (HEIGHT_MAX - HEIGHT_MIN), 0.0, 1.0)
    relief = np.stack([80 + 150 * shade, 120 + 110 * shade, 70 + 120 * shade], axis=-1)
    relief[~inside] *= 0.45
    relief[borders] *= 0.7
    relief[cities] = CITY_PREVIEW_COLOUR
    relief[towns] = TOWN_PREVIEW_COLOUR
    rivers = np.asarray(outputs.rivers)[crop]
    relief[rivers < RIVER_SEA_PALETTE] = RIVER_PREVIEW_COLOUR
    relief_picture = _scaled(relief)
    _label_settlements(relief_picture, after, crop)

    terrain = np.full((*labels.shape, 3), 40.0)
    for province, terrain_type in outputs.desired.items():
        terrain[(labels == province) & inside] = TERRAIN_PREVIEW_COLOURS.get(terrain_type, (255, 0, 255))
    terrain[borders] *= 0.55
    terrain_picture = _scaled(terrain)

    new_ids = set(stage2_parents(PROVINCE_MANIFEST))
    old = before[crop]
    old_sheet = np.full((*labels.shape, 3), 235.0)
    old_sheet[~inside] = 120
    old_sheet[province_borders(old) & inside] = 20
    new_sheet = np.full((*labels.shape, 3), 235.0)
    new_sheet[~inside] = 120
    new_sheet[np.isin(labels, sorted(new_ids)) & inside] = (190, 215, 250)
    new_sheet[cities] = CITY_PREVIEW_COLOUR
    new_sheet[towns] = TOWN_PREVIEW_COLOUR
    new_sheet[borders] = 20
    gap = np.full((labels.shape[0], 4, 3), 255.0)
    split_picture = _scaled(np.concatenate([old_sheet, gap, new_sheet], axis=1))

    paths = []
    for name, picture in (
        ("ivn_stage2_relief_rivers_settlements.png", relief_picture),
        ("ivn_stage2_terrain.png", terrain_picture),
        ("ivn_stage2_splits.png", split_picture),
    ):
        path = directory / name
        picture.save(path, optimize=True)
        paths.append(path)
    return paths


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_mutually_exclusive_group()
    actions.add_argument(
        "--check",
        action="store_true",
        help="validate synchronized terrain outputs (default)",
    )
    actions.add_argument(
        "--apply", action="store_true", help="write synchronized terrain outputs"
    )
    actions.add_argument(
        "--plan-island-provinces",
        action="store_true",
        help="add the island-administration cities and splits to the reviewed geometry data",
    )
    actions.add_argument(
        "--plan-stage2-provinces",
        action="store_true",
        help="plan the Stage 2 cities, towns and splits into the manifest and raster under --output-root",
    )
    actions.add_argument(
        "--dry-run-stage2",
        type=Path,
        metavar="DIR",
        help="apply the Stage 2 plan in DIR to copies of the map there and write previews and statistics",
    )
    actions.add_argument(
        "--smooth-stage2-state-borders",
        action="store_true",
        help="smooth the lines between IVN/IIA states in the stored Stage 2 plan; report only without --output-root",
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        help=(
            "root that receives the plan: --plan-stage2-provinces writes the repository without it, "
            "--smooth-stage2-state-borders writes nothing without it"
        ),
    )
    parser.add_argument(
        "--previews",
        action="store_true",
        help=f"with --smooth-stage2-state-borders, write state previews to {STATE_SMOOTHING_PREVIEW_DIR.relative_to(ROOT).as_posix()}",
    )
    args = parser.parse_args()
    if args.plan_island_provinces:
        plan_province_geometry(IIA_STATE_IDS, ISLAND_CITY_SETTLEMENTS)
        print(f"Wrote {PROVINCE_GEOMETRY_PATH.name} and {PROVINCE_MANIFEST_PATH.name}.")
        return 0
    if args.plan_stage2_provinces:
        report = write_stage2_plan(args.output_root or REPOSITORY_ROOT)
        print(
            f"Planned {report['new_ids']} Stage 2 provinces {report['first_id']}-{report['last_id']}; "
            f"{report['borders']} province borders, {report['border_margin']} free."
        )
        return 0
    if args.smooth_stage2_state_borders:
        report = write_smoothed_stage2_plan(args.output_root, args.previews)
        summary = {key: value for key, value in report.items() if key != "transfers"}
        print(json.dumps(summary, ensure_ascii=False, indent=1))
        if not report["stable"]:
            print(f"ERROR: the smoothing still moved pixels after {report['passes']} passes; nothing was written")
        if report["rail_segments_lost"]:
            print(f"ERROR: railway segments lost their contact: {report['rail_segments_lost']}")
        return 0 if report["stable"] and not report["rail_segments_lost"] else 1
    if args.dry_run_stage2:
        result = dry_run_stage2(args.dry_run_stage2)
        (args.dry_run_stage2 / "ivn_stage2_dry_run.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
        )
        for issue in result["issues_after_one_pass"]:
            print(f"ERROR: {issue}")
        return 1 if result["issues_after_one_pass"] else 0
    if args.apply:
        apply()
    issues = province_geometry_issues()
    if not issues:
        issues = validate()
    if issues:
        for issue in issues:
            print(f"ERROR: {issue}")
        return 1
    print(
        f"Ivanland geography validation passed for {len(scoped_provinces())} land provinces and {len(SETTLEMENT_PROVINCES)} settlements."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
