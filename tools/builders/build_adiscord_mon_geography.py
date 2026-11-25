"""Generate the Montar Empire geography: carved cities, relief, rivers, terrain and trees.

The default mode and ``--check`` list differences against the expected outputs.
``--plan-provinces`` writes the reviewed province geometry once per stage,
``--preview`` writes review images and ``--apply`` writes the map outputs.

Stage 2 extends the scope to the neighbours of Montar and keeps the Stage 1
keys of the data file and their meaning. It adds:

- ``terrain_bands``: the MON acceptance bands over its original provinces;
- ``regions``: one section per neighbour country with its states, capital
  state, landform overrides, relief, rivers, terrain bands and settlements;
- ``stage2``: the MON second cities (``settlements``), the MON relief levels
  and terrain bands that replace their Stage 1 values once the provinces are
  split (``levels`` by name, ``terrain_bands``), the river pixels of the
  neighbour scope as they stood before this builder (``existing_rivers``) and
  the Stage 2 plan (``planned``: origin, sheet_row, first_id, provinces,
  cities, towns, irregular_parts).

Later stages follow in ``stages``, one record per stage after the two
above, in map-apply order. A region names its stage with ``stage`` (2 when
absent); a stage record holds what the planner of that stage recorded:
``stage``, ``origin``, ``sheet_row``, ``first_id``, ``provinces``,
``cities``, ``towns``, ``irregular_parts``, ``existing_rivers``,
``ring_rivers`` and ``grouping_centres``. Regions of a stage without a record
stay out of the map pass until ``--plan-provinces`` plans them.

A region may also author ``split_threshold`` and ``split_part`` (pixels),
``part_min_pixels``, ``heights`` (``min``, ``max``), ``terrain_classes``
(the rural classes it may use), ``desert_zones``, ``pinned_terrain``
(``{province: terrain}``), ``no_split_states``, ``never_parent``,
``keep_provinces`` and ``keep_above`` (a height from which the existing
relief, terrain and trees stay). A settlement of kind ``adopt`` names an
existing city ``province`` that the state keeps instead of a carved one.

The scope is a set of state ids, never the current owners of those states.
The geometry raster stacks the reviewed changes of every stage: Stage 1
fills the rows above the ``sheet_row`` of the next stage, and each later
stage the rows from its own ``sheet_row`` to the next one.
"""

from __future__ import annotations

import argparse
import heapq
import json
import os
import re
import shutil
from bisect import bisect_right
from collections import Counter, defaultdict, deque
from dataclasses import dataclass, field
from io import BytesIO
from math import ceil, cos, radians, sin
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw
from scipy.ndimage import binary_dilation, distance_transform_edt, find_objects, gaussian_filter, label

from tools.builders.build_adiscord_coastal_geography import (
    PROVINCE_PIXEL_REPAIRS,
    PROVINCE_REPAIR_PROVINCES,
    RIVER_COURSES,
    STANDING_SLOTS,
    border_contacts,
    complete_native_anchors,
    moving_anchors_native,
    native_slots,
    province_border_count,
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
    STATE_SMOOTHING_PREVIEW_DIR,
    UNIFORM_TERRAIN_PALETTES,
    URBAN_PALETTE,
    _geodesic_partition,
    _grow_compact_region,
    _nearest_member,
    _prune_river_loops,
    _route_river,
    _snap_river_point,
    _tree_cell_sample_from_pixels,
    carve_junction_city,
    interior_river_pixels_by_state,
    lattice_noise,
    masked_slopes,
    native_river_bmp,
    neighbours_of,
    normal_from_height,
    palette_types,
    polyline_distance,
    province_adjacency,
    province_borders,
    province_colour,
    province_states,
    province_terrain_type,
    remove_four_province_corners,
    river_width_palette,
    scoped_provinces,
    slot_points,
    smooth_state_borders,
    stable_unit_hash,
    supply_node_points,
    tree_probability,
    write_state_smoothing_previews,
)
from tools.lib.adiscord_planned_geography import east_stages
from tools.lib.adiscord_starting_navies import STARTING_NAVIES
from tools.lib.city_terrains import CITY_TERRAINS
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
BUILDINGS = Path("map/buildings.txt")
SUPPLY_NODES = Path("map/supply_nodes.txt")
UNITS = Path("history/units")
# Inputs a dry run copies; the plan files come from --plan-provinces --output-root.
DRY_RUN_INPUTS = (
    PROVINCES, DEFINITION, HEIGHTMAP, WORLD_NORMAL, TERRAIN, TREES, RIVERS, CITIES, UNITSTACKS, RAILWAYS, STATE_NAMES, SUPPLY_NODES
)
DRY_RUN_REPORT = "mon_geography_dry_run.json"
PLAN_REPORT = "mon_geography_plan.json"

WINDOW_MARGIN = 40
REMAINDER_MIN_PIXELS = 60
# A town is smaller than a city; its remainder only has to stay a province of its own.
TOWN_REMAINDER_MIN_PIXELS = 40
TOWN_MIN_NEIGHBOURS = 2
DISTRICT_PIXELS = 45
# Placeholder label of a district while its site is evaluated.
DISTRICT_MARKER = -2
DISTRICT_ANCHOR_DISTANCE = 4.0
LEFTOVER_MARKER = -1
SITE_MARGIN = 30
VILLAGE_CITY_DISTANCE = 10.0
VILLAGE_SPACING = 15.0
VILLAGE_CORE_PIXELS = 8
# A settlement of this victory-point value spreads its houses over the neighbouring provinces.
METRO_VALUE = 8
# A metropolis of value 8 covers about 130 pixels; a capital of value 20 about 190.
METRO_BASE_PIXELS = 90
METRO_PIXELS_PER_VALUE = 5
# Cities of this value and the districts draw the western houses; smaller cities the low blocks.
LARGE_CITY_VALUE = 4
# The houses of a city may stand this many pixels past its province edge.
CITY_REACH = 3
# A town is a small built patch inside its province, like a harbour or a village.
TOWN_PATCH = (10, 16)
# Lobes and lattice noise make an outline ragged instead of a disc.
FOOTPRINT_LOBES = (0.42, 0.3, 0.18)
FOOTPRINT_NOISE = 0.35
FOOTPRINT_NOISE_CELL = 3.0
# A gorge river inside the scope may run on borders this far from its state line.
CANYON_LANE_WIDTH = 2.5
# Settlements stay out of a canyon: easing the town relief would fill the gorge.
CANYON_SETTLEMENT_CLEARANCE = 8.0
# Town ground keeps the broad slope of its site: relief detail finer than this sigma is smoothed away.
URBAN_SLOPE_SIGMA = 5.0
# A town eases from the land at its edge into that surface over this many pixels, so its
# edge has no step and the declared terrain of the provinces around it stays as it is.
URBAN_FEATHER = 3.0
# The state base field is smoothed this much, so no step appears on a state border.
LEVEL_SIGMA = 12.0
# Valleys deepen from 1.5 height units under the narrowest river to 4 under the widest.
VALLEY_RADIUS = 2.0
VALLEY_MIN_DEPTH = 1.5
VALLEY_MAX_DEPTH = 4.0
WIDEST_RIVER_PALETTE = 11
RIVER_FLOW_IN_PALETTE = 1
# A split marker starts a branch that leaves its river; the engine walks it like a tributary.
RIVER_FLOW_OUT_PALETTE = 2
REPAIR_WINDOW = 8
# A repaired course keeps this far from every marker it does not already touch.
MARKER_CLEARANCE = 2.9
# A repaired run may be at most this many times longer than the gap it closes.
REPAIR_DETOUR = 3
# Forks and markerless courses of the existing rivers are settled in at most this many passes.
RIVER_SETTLE_ROUNDS = 20
# Mending reroutes the rivers after each change of the geometry, at most this often.
MEND_ROUNDS = 6
# A pixel that restores a state area moves at least this far from the mended piece.
MEND_DISTANCE = 6
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
# A river bed never rises downstream. Where the ground does, the river cuts a valley
# whose depth fades with a Gaussian of radius RIVER_VALLEY_BASE plus the cut over
# RIVER_VALLEY_SPREAD, so a deep cut through a ridge opens a wide pass, not a trench.
RIVER_VALLEY_BASE = 2.0
RIVER_VALLEY_SPREAD = 5.0
RIVER_VALLEY_REACH = 24
REACHABLE_PIECE_PIXELS = 50
# A course that cuts a province is routed again without the cutting pixels.
ROUTE_ATTEMPTS = 12
SLIVER_PIXELS = 3
MOUNTAIN_HEIGHT = 160
MOUNTAIN_SLOPE = 12
HILLS_HEIGHT = 132
HILLS_SLOPE = 6
MARSH_HEIGHT = 106
# City groups of map/cities.txt: 15 draws the western houses of a large city; 1 is the
# map-wide default, and on urban terrain it draws the low blocks of a small town.
CITY_HOUSES_INDEX = 15
CITY_BACKGROUND_INDEX = 1
SMALL_CITY_INDEX = CITY_BACKGROUND_INDEX
TREE_PALETTES = (6, 5)
RURAL_TERRAINS = ("plains", "forest", "marsh", "hills", "mountain", "desert")
# Sand desert of common/terrain/00_terrain.txt; a region uses it only through authored desert zones.
DESERT_PALETTE = 3
RURAL_PALETTES = {**UNIFORM_TERRAIN_PALETTES, "desert": DESERT_PALETTE}
# A class a region does not allow falls back to the next class of its chain.
CLASS_FALLBACK = {"mountain": "hills", "hills": "plains", "marsh": "plains", "forest": "plains", "desert": "plains"}
# A province of this desert share is declared desert unless its relief or forest decides first.
DESERT_SHARE = 0.4
# Frozen state names: the relief must agree with the landform each name gives.
# A lake district ("поозёрье") is low land: plains, forest and marsh.
NAMED_LANDFORMS = {
    "нагорье": "upland",
    "перевал": "upland",
    "проход": "upland",
    "холмы": "hills",
    "водораздел": "hills",
    "каменка": "hills",
    "овраг": "hills",
    "леса": "forest",
    "просека": "forest",
    "перелесок": "forest",
    "лесная": "forest",
    "равнина": "plains",
    "степь": "plains",
    "проселок": "plains",
    "лощина": "plains",
    "поозерье": "lowland",
    "озерный": "lowland",
    "пустын": "desert",
    "пески": "desert",
}
UPLAND_HIGH_SHARE = 0.6
UPLAND_MIN_MOUNTAINS = 3
LOWLAND_SHARE = 0.6
LOWLAND_MIN_MARSH = 1
FORBIDDEN_TERRAINS = frozenset({"contaminated", "reactor_zone"})
# Stage 2: carved towns and the split of large rural provinces.
TOWN_PIXELS = 35
TOWN_SIZE = (30, 40)
CITY_SIZE = (40, 50)
SPLIT_THRESHOLD = 130
SPLIT_PART_PIXELS = 80
PART_MIN_PIXELS = 40
PART_MIN_ROUNDNESS = 0.35
# A parent below this roundness has arms or tails no split can round off; its
# parts may stay below the minimum by at most IRREGULAR_LOSS under the parent.
IRREGULAR_PARENT = 0.45
IRREGULAR_LOSS = 0.12
# Clearing four-province corners after a split moves single pixels; a part may
# end this far below the minimum roundness and is listed for review.
CORNER_LOSS = 0.01
PARTITION_ANGLES = 8
PARTITION_ITERATIONS = 20
PARTITION_SIGMAS = (1.0, 1.6)
SMOOTH_PASSES = 6
SECOND_CITY_PROVINCES = 30
SECOND_CITY_DISTANCE = 25.0
TOWN_CITY_DISTANCE = 18.0
SETTLEMENT_MIN_PARENT = 90
TOWN_MIN_PARENT = 75
SPREAD_RELAXATION = (1.0, 0.66, 0.4)
# The engine draws at most this many province borders; a plan keeps a margin.
BORDER_BUDGET = 65536
BORDER_MARGIN = 2000
# Pixels this close to the IVN geography keep their heights, terrain and trees:
# its builder blends into the nearest foreign heights and normals.
IVN_CLEARANCE = 8
# Provinces that script names by id beyond the files read in
# ``script_literal_provinces``: theatre bunkers, the ZAO bunker, the Unity
# Tower, and the naval bases and export ports of the east.
SCRIPT_LITERAL_PROVINCES = frozenset(
    {12227, 16400, 16397, 6192, 6713, 3248, 16622, 16428, 16568, 4443, 8243, 11944, 10730, 11841, 2553, 5986, 18994}
)
NAVAL_LITERAL_PROVINCES = frozenset({16568, 4443, 8243, 11944, 10730, 11841, 2553, 5986, 18994})
# Province building models whose positions stay with a literal province's id when it is split.
LITERAL_BUILDING_TYPES = ("bunker", "naval_base_spawn", "supply_node")
VICTORY_POINT_SLOT = 38
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
    """Province sets of the scope; planned ids are children of a parent.

    ``original`` holds the provinces that existed before either plan. A
    remainder is what a carved city or town leaves of its parent; a part is
    one piece of a split rural province.
    """

    states: list[int]
    state_of: dict[int, int]
    original: frozenset[int]
    planned: dict[int, dict]
    cities: dict[int, int]
    districts: frozenset[int]
    remainders: dict[int, int]
    towns: frozenset[int] = frozenset()
    parts: dict[int, int] = field(default_factory=dict)
    region_of: dict[int, str] = field(default_factory=dict)
    later: frozenset[int] = frozenset()
    # Existing city provinces that settlements of kind ``adopt`` keep as they are.
    adopted: frozenset[int] = frozenset()
    pinned: dict[int, str] = field(default_factory=dict)

    @property
    def provinces(self) -> frozenset[int]:
        return frozenset(self.state_of)

    @property
    def urban(self) -> frozenset[int]:
        return frozenset(self.cities) | self.districts | self.towns

    def region_provinces(self, tag: str) -> list[int]:
        return [province for province, state_id in self.state_of.items() if self.region_of[state_id] == tag]


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


def _expands(value, depth: int) -> bool:
    """Whether a value is written over several lines.

    A list of records puts one record on each line. A section of the file
    opens up; deeper, a dict opens up only when it holds records, sections
    of records or rows of pixels.
    """
    if isinstance(value, list):
        return bool(value) and isinstance(value[0], dict)
    if not isinstance(value, dict):
        return False
    if depth <= 1:
        return True
    return any(
        _expands(inner, depth + 1) or (isinstance(inner, list) and bool(inner) and isinstance(inner[0], list))
        for inner in value.values()
    )


def _dump_value(prefix: str, value, indent: int, depth: int, comma: str) -> list[str]:
    pad = " " * indent
    if isinstance(value, list) and _expands(value, depth):
        lines = [f"{pad}{prefix}["]
        lines += [f"{pad}  {_inline(item)}{',' if index + 1 < len(value) else ''}" for index, item in enumerate(value)]
        return [*lines, f"{pad}]{comma}"]
    if isinstance(value, dict) and _expands(value, depth):
        lines = [f"{pad}{prefix}{{"]
        items = list(value.items())
        for index, (key, inner) in enumerate(items):
            lines += _dump_value(f"{_inline(key)}: ", inner, indent + 2, depth + 1, "," if index + 1 < len(items) else "")
        return [*lines, f"{pad}}}{comma}"]
    return [f"{pad}{prefix}{_inline(value)}{comma}"]


def dump_data(data: dict) -> str:
    """Serialise the data file in its authored layout: one record per line."""
    return "\n".join(_dump_value("", data, 0, 0, "")) + "\n"


def state_provinces(root: Path, state_id: int) -> frozenset[int]:
    matches = sorted((root / "history/states").glob(f"{state_id}-*.txt"))
    if len(matches) != 1:
        raise RuntimeError(f"state {state_id}: expected one history file, found {len(matches)}")
    source = matches[0].read_text(encoding="utf-8-sig")
    block = re.search(r"\bprovinces\s*=\s*\{([^}]*)\}", source)
    if block is None:
        raise RuntimeError(f"state {state_id}: missing provinces block")
    return frozenset(int(value) for value in re.findall(r"\d+", block.group(1)))


def region_states(data: dict) -> dict[str, list[int]]:
    """States of every region in data order, MON first."""
    result = {"MON": [int(state_id) for state_id in data["states"]]}
    for tag, region in data.get("regions", {}).items():
        result[tag] = [int(state_id) for state_id in region["states"]]
    return result


def stage2_plan(data: dict) -> dict:
    return data.get("stage2", {}).get("planned", {})


def has_stage2_plan(data: dict) -> bool:
    return bool(stage2_plan(data).get("provinces"))


def region_stage(region: dict) -> int:
    """The stage that plans a region; a region without one belongs to Stage 2."""
    return int(region.get("stage", 2))


def stage_layers(data: dict) -> dict[int, dict]:
    """The plan record of every stage by number: ``planned``, ``stage2.planned``, then ``stages``.

    Stage 2 may hold only the ``sheet_row`` that ends Stage 1 in the raster.
    """
    layers = {1: data["planned"]}
    if stage2_plan(data):
        layers[2] = stage2_plan(data)
    for record in data.get("stages", []):
        number = int(record["stage"])
        if number <= max(max(layers), 2):
            raise RuntimeError(f"stage record {number}: stages must follow Stage 2 in increasing order")
        layers[number] = record
    return layers


def has_stage_plan(data: dict, number: int) -> bool:
    """Whether a stage has its recorded plan; from Stage 3 on, the record itself is the plan."""
    if number == 1:
        return bool(data["planned"]["provinces"])
    if number == 2:
        return has_stage2_plan(data)
    return number in stage_layers(data)


def later_layers(data: dict) -> list[dict]:
    """The plan records after Stage 1, in map-apply order."""
    return [record for number, record in sorted(stage_layers(data).items()) if number > 1]


def planned_entries(data: dict) -> list[dict]:
    return [entry for _number, record in sorted(stage_layers(data).items()) for entry in record.get("provinces", [])]


def later_entries(data: dict) -> list[dict]:
    return [entry for record in later_layers(data) for entry in record.get("provinces", [])]


def unplanned_stages(data: dict) -> list[int]:
    """Stages from 3 on whose regions are authored but not planned yet."""
    stages = {region_stage(region) for region in data.get("regions", {}).values()}
    return sorted(number for number in stages if number > 2 and not has_stage_plan(data, number))


def active_data(data: dict) -> dict:
    """The data without the regions of unplanned stages: the scope of the map pass."""
    waiting = set(unplanned_stages(data))
    if not waiting:
        return data
    result = dict(data)
    result["regions"] = {tag: region for tag, region in data["regions"].items() if region_stage(region) not in waiting}
    return result


# MON relief, river and terrain features; a later stage plans its own regions without them.
MON_FEATURES = (
    "levels", "uplands", "ridges", "basins", "canyons", "keep_zones", "forest_zones", "marsh_zones", "rivers", "river_edits",
    "owned_reaches",
)


def stage_data(data: dict, number: int) -> dict:
    """The data a stage planner reads: the regions of that stage and the plans before it.

    Stage 2 plans the MON towns and splits with its neighbour regions. From
    Stage 3 on only the regions of the stage are planned: the MON sections
    and the earlier plans leave the scope, whose states those plans never
    touch.
    """
    if number == 1:
        return stage1_data(data)
    regions = {tag: region for tag, region in data.get("regions", {}).items() if region_stage(region) == number}
    if number == 2:
        result = {key: value for key, value in data.items() if key != "stages"}
        result["regions"] = regions
        return result
    result = dict(data)
    for key in MON_FEATURES:
        result[key] = []
    result.update(
        {
            "states": [],
            "settlements": [],
            "existing_rivers": {},
            "planned": {"origin": [0, 0], "first_id": 0, "provinces": [], "cities": {}, "villages": {}},
            "stage2": {},
            "stages": [],
            "regions": regions,
        }
    )
    return result


def region_parameters(data: dict) -> dict[int, dict]:
    """The authored region of every scope state; MON states map to an empty dict."""
    result = {int(state_id): {} for state_id in data["states"]}
    for region in data.get("regions", {}).values():
        for state_id in region["states"]:
            result[int(state_id)] = region
    return result


def state_parameter(data: dict, key: str, default):
    """A per-region value for every scope state, ``default`` where its region has none."""
    return {state_id: region.get(key, default) for state_id, region in region_parameters(data).items()}


# Region features that the relief, rivers and terrain read as one list.
MERGED_FEATURES = (
    "levels", "uplands", "ridges", "basins", "keep_zones", "forest_zones", "marsh_zones", "desert_zones", "rivers", "river_edits"
)


def geography_view(data: dict) -> dict:
    """The data with the features of every region merged into the MON lists.

    MON features come first, so MON rivers are routed before those of the
    neighbours and keep their Stage 1 order.
    """
    view = dict(data)
    regions = list(data.get("regions", {}).values())
    for key in MERGED_FEATURES:
        view[key] = [*data.get(key, []), *(item for region in regions for item in region.get(key, []))]
    later = data.get("stage2", {})
    overrides = {level["name"]: level for level in later.get("levels", [])}
    view["levels"] = [overrides.get(level["name"], level) for level in view["levels"]]
    view["terrain_bands"] = later.get("terrain_bands", data["terrain_bands"])
    # A river into the sea is routed, marked and checked like a river into a lake.
    view["rivers"] = [
        {**river, "mouth": {"lake": river["mouth"]["sea"]}} if "sea" in river["mouth"] else river for river in view["rivers"]
    ]
    # Each later stage snapshots the rivers of its own scope and of the land beside it.
    snapshots = [data.get("stage2", {}), *data.get("stages", [])]
    view["existing_rivers"] = merged_rivers([data["existing_rivers"], *(record.get("existing_rivers", {}) for record in snapshots)])
    rings = [record["ring_rivers"] for record in snapshots if record.get("ring_rivers")]
    view["ring_rivers"] = merged_rivers(rings) if len(rings) > 1 else (rings[0] if rings else {})
    return view


# Features that shape the relief and the pixel classes of one relief group.
GROUP_FEATURES = ("levels", "uplands", "ridges", "basins", "forest_zones", "marsh_zones", "desert_zones")


def relief_groups(view: dict) -> list[tuple[list[int], dict]]:
    """The scope states of each relief group, with the view of the features it reads.

    MON and the Stage 2 regions form one group, as they were planned and
    applied together. Each later stage is a group of its own: its levels,
    relief features and zones never reach the land of another group, and
    its pixels near an earlier group keep their heights (``stage_belt``), so the
    earlier relief blends into the same heights as before that stage.
    """
    regions = view.get("regions", {})
    later: dict[int, list[dict]] = defaultdict(list)
    for region in regions.values():
        if region_stage(region) > 2:
            later[region_stage(region)].append(region)
    base_states = [int(state_id) for state_id in view["states"]]
    base_states += [int(state_id) for region in regions.values() if region_stage(region) <= 2 for state_id in region["states"]]
    if not later:
        return [(base_states, view)]
    taken = {
        id(item) for group in later.values() for region in group for key in GROUP_FEATURES for item in region.get(key, [])
    }
    base = dict(view)
    for key in GROUP_FEATURES:
        base[key] = [item for item in view.get(key, []) if id(item) not in taken]
    groups = [(base_states, base)]
    for _number, group in sorted(later.items()):
        stage_view = dict(view)
        for key in GROUP_FEATURES:
            stage_view[key] = [item for region in group for item in region.get(key, [])]
        groups.append(([int(state_id) for region in group for state_id in region["states"]], stage_view))
    return groups


def merged_rivers(snapshots: list[dict]) -> dict[str, list]:
    """River snapshots by row, in the order given."""
    merged: dict[str, list] = {}
    for snapshot in snapshots:
        for row, pixels in snapshot.items():
            merged.setdefault(row, []).extend(pixels)
    return merged


def stage1_data(data: dict) -> dict:
    """The data as Stage 1 left it: MON only, without regions or the later plans.

    Only the row where the Stage 2 geometry starts in the raster remains.
    """
    result = {key: value for key, value in data.items() if key not in ("regions", "stage2", "stages")}
    later = stage2_plan(data)
    if "sheet_row" in later:
        result["stage2"] = {"planned": {"sheet_row": later["sheet_row"]}}
    return result


def adopted_cities(data: dict) -> dict[int, int]:
    """The existing city province of every state whose settlement of kind ``adopt`` names one."""
    result = {}
    for _tag, entry in all_settlements(data):
        if entry["kind"] == "adopt" and entry.get("province") is not None:
            result[int(entry["state"])] = int(entry["province"])
    return result


def load_scope(root: Path, data: dict) -> Scope:
    planned = {int(entry["province"]): entry for entry in planned_entries(data)}
    region_of = {state_id: tag for tag, states in region_states(data).items() for state_id in states}
    state_of: dict[int, int] = {}
    for state_id in region_of:
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
    layers = [record for _number, record in sorted(stage_layers(data).items())]
    cities = {int(parent): int(city) for plan in layers for parent, city in plan.get("cities", {}).items()}
    towns = frozenset(int(town) for plan in layers[1:] for town in plan.get("towns", {}))
    districts = frozenset(province for province, entry in planned.items() if entry["kind"] == "district")
    remainders = {
        int(entry["parent"]): province for province, entry in planned.items() if entry["kind"] == "remainder"
    }
    parts = {province: int(entry["parent"]) for province, entry in planned.items() if entry["kind"] == "part"}
    later_ids = frozenset(int(entry["province"]) for entry in later_entries(data))
    adopted = adopted_cities(data)
    for state_id, province in adopted.items():
        if state_of.get(province) != state_id:
            raise RuntimeError(f"adopted city {province}: not a province of state {state_id}")
    pinned = {
        int(province): terrain
        for region in data.get("regions", {}).values()
        for province, terrain in region.get("pinned_terrain", {}).items()
    }
    return Scope(
        list(region_of),
        state_of,
        original,
        planned,
        cities,
        districts,
        remainders,
        towns,
        parts,
        region_of,
        later_ids,
        frozenset(adopted.values()),
        pinned,
    )


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
    """Append the provinces of every stage in map-apply order, or confirm they were appended before."""
    for _number, plan in sorted(stage_layers(data).items()):
        if plan.get("provinces"):
            register_plan_rows(definition, plan)


def register_plan_rows(definition: Definition, plan: dict) -> None:
    """Append the provinces of one plan, or confirm they were appended before.

    Planned ids continue the id sequence of the plan. Another builder that
    appended provinces since the plan took them, so the plan must be redone.
    A new province copies the terrain and continent of its parent; its
    coastal flag follows the plan.
    """
    entries = sorted(plan["provinces"], key=lambda entry: entry["province"])
    if not entries:
        return
    present = [int(entry["province"]) in definition.rows for entry in entries]
    if all(present):
        for entry in entries:
            if list(map(int, definition.rows[int(entry["province"])][1:4])) != list(entry["rgb"]):
                raise RuntimeError(f"province {entry['province']}: definition colour differs from the plan")
        return
    if any(present):
        raise RuntimeError("definition.csv holds only part of the planned provinces")
    first_id = int(plan["first_id"])
    if max(definition.rows) + 1 != first_id:
        raise RuntimeError(
            f"definition.csv ends at {max(definition.rows)}, the plan starts at {first_id}: replan the provinces"
        )
    for expected, entry in enumerate(entries, start=first_id):
        if int(entry["province"]) != expected:
            raise RuntimeError(f"planned province {entry['province']}: ids are not contiguous")
        parent = definition.rows[int(entry["parent"])]
        coastal = "true" if entry.get("coastal") else "false"
        row = [str(expected), *map(str, entry["rgb"]), "land", coastal, parent[6], parent[7]]
        definition.rows[expected] = row
        definition.lines.append(";".join(row))


def rail_pairs(root: Path) -> set[tuple[int, int]]:
    return rail_text_pairs((root / RAILWAYS).read_text(encoding="utf-8-sig"))


def rail_chain(line: str) -> list[int] | None:
    """The provinces of one railway line, or None for a line that is no railway."""
    fields = line.split()
    if len(fields) < 3 or not all(value.isdigit() for value in fields):
        return None
    return [int(value) for value in fields[2:]]


def rail_text_pairs(text: str) -> set[tuple[int, int]]:
    pairs = set()
    for line in text.splitlines():
        chain = rail_chain(line)
        if chain is None:
            continue
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


def geometry_layers(data: dict, sheet: np.ndarray) -> list[tuple[list[int], np.ndarray]]:
    """The reviewed geometry of each plan: its map origin and its RGBA crop.

    The raster stacks the plans: Stage 1 fills the rows above the
    ``sheet_row`` of the next stage, and every later stage the rows from its
    own ``sheet_row`` to the next one. A later stage records the pixels it
    changes on the map the stages before it left; transparent pixels stay
    as they are. Pixels its state-line smoothing moved carry the alpha
    SMOOTHED_ALPHA. A stage that only names its ``sheet_row`` ends the rows
    of the stage before it and stamps nothing itself.
    """
    starts = [(0, 1, data["planned"])]
    starts += [
        (int(record["sheet_row"]), number, record)
        for number, record in sorted(stage_layers(data).items())
        if number > 1 and "sheet_row" in record
    ]
    layers = []
    for index, (row, number, record) in enumerate(starts):
        end = starts[index + 1][0] if index + 1 < len(starts) else sheet.shape[0]
        if number == 1 or record.get("provinces"):
            layers.append((record["origin"], sheet[row:end]))
    return layers


def stamp_geometry(root: Path, rgb: np.ndarray, data: dict, colours: dict, scope: Scope) -> np.ndarray:
    """Return provinces.bmp pixels with the reviewed geometry of every plan stamped in."""
    if not data["planned"]["provinces"]:
        return rgb
    with Image.open(root / GEOMETRY_PATH) as source:
        sheet = np.asarray(source.convert("RGBA"))
    result = rgb.copy()
    allowed = {colours[province] for province in scope.provinces}
    for (x0, y0), geometry in geometry_layers(data, sheet):
        height, width = geometry.shape[:2]
        stamped = geometry[..., 3] > 0
        region = result[y0:y0 + height, x0:x0 + width]
        stamped = stamped[:region.shape[0], :region.shape[1]]
        geometry = geometry[:region.shape[0], :region.shape[1]]
        current = {tuple(int(value) for value in colour) for colour in np.unique(region[stamped], axis=0)}
        planned = {tuple(int(value) for value in colour) for colour in np.unique(geometry[..., :3][stamped], axis=0)}
        if not current <= allowed or not planned <= allowed:
            raise RuntimeError("the province geometry would change land outside the scope")
        region[stamped] = geometry[..., :3][stamped]
    break_crossings(result, allowed)
    return result


def _packed_rgb(rgb: np.ndarray) -> np.ndarray:
    values = rgb.astype(np.int64)
    return (values[..., 0] << 16) | (values[..., 1] << 8) | values[..., 2]


def crossing_squares(packed: np.ndarray) -> np.ndarray:
    """Top-left corners of the 2x2 squares where four different provinces meet."""
    a, b, c, d = packed[:-1, :-1], packed[:-1, 1:], packed[1:, :-1], packed[1:, 1:]
    return (a != b) & (a != c) & (a != d) & (b != c) & (b != d) & (c != d)


def break_crossings(rgb: np.ndarray, allowed: set[tuple[int, int, int]]) -> None:
    """Give one scope pixel of every four-province 2x2 square to a scope neighbour, in place.

    The engine rejects such a square as an invalid X crossing. A pixel takes
    the colour of a neighbour inside the square, so no province gains land
    away from its edge, and only a change that leaves no crossing around
    that pixel is kept. Provinces outside the scope keep every pixel.
    """
    packed = _packed_rgb(rgb)
    keys = {(red << 16) | (green << 8) | blue for red, green, blue in allowed}
    for y, x in zip(*np.nonzero(crossing_squares(packed))):
        square = packed[y:y + 2, x:x + 2]
        if not crossing_squares(square)[0, 0]:
            continue
        for py, px in ((y + 1, x + 1), (y + 1, x), (y, x + 1), (y, x)):
            original = int(packed[py, px])
            if original not in keys:
                continue
            # The horizontal neighbour inside the square first, then the vertical one.
            donors = (int(packed[py, x + (px == x)]), int(packed[y + (py == y), px]))
            for donor in (donor for donor in donors if donor in keys):
                packed[py, px] = donor
                around = packed[max(py - 1, 0):py + 2, max(px - 1, 0):px + 2]
                if not crossing_squares(around).any():
                    break
                packed[py, px] = original
            if int(packed[py, px]) != original:
                rgb[py, px] = ((packed[py, px] >> 16) & 255, (packed[py, px] >> 8) & 255, packed[py, px] & 255)
                break


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


def states_provinces(root: Path, states: list[int]) -> frozenset[int]:
    return frozenset().union(*(state_provinces(root, state_id) for state_id in states))


@dataclass
class Canyon:
    """A gorge along the border between MON and the states of a neighbour.

    ``distance`` is the distance of each pixel from the border line, on both
    sides. The far wall lies in ``band``, far-side land within the authored
    band width. An external far side lies outside the scope; there only
    heights change, read from the land beyond the band. Inside the scope the
    far side keeps its own relief and the gorge is cut into it.
    """

    feature: dict
    foreign: np.ndarray
    distance: np.ndarray
    band: np.ndarray
    course: np.ndarray
    near: np.ndarray | None = None
    external: bool = True


def canyon_layers(
    root: Path, data: dict, labels: np.ndarray, scope: np.ndarray, water: np.ndarray, planned: dict[int, dict] | None = None
) -> list[Canyon]:
    """The authored canyons; the near side is MON, the far side the authored states.

    Planned provinces belong to the side of their state.
    """
    canyons = []
    planned = planned or {}
    near_provinces = states_provinces(root, data["states"])
    near_provinces |= {province for province, entry in planned.items() if entry["state"] in data["states"]}
    near = np.isin(labels, list(near_provinces)) & scope
    for feature in data.get("canyons", []):
        far_states = [int(state_id) for state_id in feature["far_states"]]
        far_provinces = states_provinces(root, far_states)
        far_provinces |= {province for province, entry in planned.items() if entry["state"] in far_states}
        foreign = np.isin(labels, list(far_provinces)) & ~water
        if not (neighbours_of(foreign) & near).any():
            raise RuntimeError(f"canyon {feature['name']}: MON does not border states {far_states}")
        inside = distance_transform_edt(~foreign)
        outside = distance_transform_edt(~near)
        distance = np.where(near, inside, np.where(foreign, outside, np.inf)) - 0.5
        band = foreign & (distance <= feature["band"])
        external = not (foreign & scope).any()
        course = state_line_course(near, foreign)
        if not external:
            # Inside the scope the gorge may pass a bump of either side round its other side.
            course = province_borders(labels) & (near | foreign) & (distance <= CANYON_LANE_WIDTH)
        canyons.append(Canyon(feature, foreign, distance, band, course, near, external))
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
        if not canyon.external:
            continue
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
        near = mon if canyon.near is None else canyon.near
        scope = (near | canyon.band) & (canyon.distance <= feature["half_width"] + 4)
        floor = feature["floor"] + 3.0 * lattice_noise(gx, gy, 7.0, 151)
        reach = feature["half_width"] * (0.85 + 0.3 * lattice_noise(gx, gy, 11.0, 157))
        t = np.clip((canyon.distance - 0.5) / reach, 0.0, 1.0)
        wall = t * t * (3.0 - 2.0 * t)
        cut = np.maximum(minimum, floor + (heights - floor) * wall)
        rim = feature["rim_lift"] * np.exp(-(((canyon.distance - reach - 1.0) / 1.5) ** 2))
        lowered = np.minimum(heights, cut) + np.where(near, rim, 0.0)
        result = np.where(scope, lowered, result)
    return result


def border_blend(target: np.ndarray, source: np.ndarray, mon: np.ndarray, feather: float) -> tuple[np.ndarray, np.ndarray]:
    """Blend MON heights into the unchanged height of the nearest outside pixel."""
    distance, (ny, nx) = distance_transform_edt(mon, return_indices=True)
    weight = np.minimum(1.0, distance / feather)
    blended = weight * target + (1.0 - weight) * source[ny, nx].astype(float)
    return np.where(mon, blended, source.astype(float)), weight


def ease_towns_into_relief(field: np.ndarray, land: np.ndarray, towns: np.ndarray) -> None:
    """Lay towns on a smoothed copy of the relief, easing in from the land at their edge.

    City meshes follow a sloping heightmap, so a town keeps the slope of its site and
    loses only the rough detail. A single flat level would stand as a terrace with
    cliffs on the uphill side. Pixels outside the towns keep their heights.
    """
    if not towns.any():
        return
    weight = gaussian_filter(land.astype(float), URBAN_SLOPE_SIGMA)
    smooth = gaussian_filter(np.where(land, field, 0.0), URBAN_SLOPE_SIGMA) / np.maximum(weight, 1e-6)
    share = np.clip((distance_transform_edt(towns) - 1.0) / URBAN_FEATHER, 0.0, 1.0)
    share = share * share * (3.0 - 2.0 * share)
    eased = land & towns
    field[eased] = smooth[eased] * share[eased] + field[eased] * (1.0 - share[eased])


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


def reference_rivers(data: dict, window: Window, shape: tuple[int, int], key: str = "existing_rivers") -> np.ndarray:
    """The existing river pixels the builder starts from on every pass.

    ``existing_rivers`` records them as they stood before this builder drew
    its own courses, so each pass restores them and routes its rivers anew.
    ``ring_rivers`` does the same for the foreign land beside the scope
    where a course may turn.
    """
    result = np.full(shape, RIVER_LAND_PALETTE, np.uint8)
    # A later stage plans in its own window; pixels of other stages beyond it are skipped.
    for row, pixels in data.get(key, {}).items():
        y = int(row) - window.y0
        if not 0 <= y < shape[0]:
            continue
        for x, palette in pixels:
            if 0 <= x - window.x0 < shape[1]:
                result[y, x - window.x0] = palette
    return result


def apply_river_edits(data: dict, window: Window, rivers: np.ndarray, owned: np.ndarray) -> None:
    """Apply the authored pixel edits of existing courses in the scope, in place.

    Where an existing course meanders through a province the coastal
    builder repairs pixel by pixel, the province cannot change; an edit
    moves the course onto its border instead.
    """
    for edit in data.get("river_edits", []):
        for point in edit.get("drop", []):
            x, y = window.local(point)
            if owned[y, x]:
                rivers[y, x] = RIVER_LAND_PALETTE
        for x, y, palette in edit.get("add", []):
            lx, ly = window.local((x, y))
            if owned[ly, lx]:
                rivers[ly, lx] = palette


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
    slivers: np.ndarray,
) -> None:
    """Move off-border and cutting pixels of the existing rivers onto province borders, in place.

    A run of pixels inside a province, or of pixels that cut a piece off
    their province, is replaced by the cheapest border path between the
    course pixels on either side. When the course itself holds the border
    pixels the path needs, the run takes in its neighbouring course pixels
    of the scope, one ring at a time. A run whose ends stay joined without
    it is dropped; a moved source keeps palette 0. Pixels outside the scope
    keep their place. A run that cannot move stays; the later corner turns
    may still fix it, and the river checks report what remains.
    """
    course = existing & owned & (rivers < RIVER_SEA_PALETTE)
    markers = course & (rivers < WIDTH_STEPS[0])
    # A cut beside a marker stays: the junction or source would lose its course.
    cutting = cutting_course(packed, rivers < RIVER_SEA_PALETTE, owned) & ~markers & ~neighbours_of(markers)
    off = course & (~border | cutting)
    pieces, count = label(off)
    for piece in range(1, count + 1):
        cluster = pieces == piece
        if not (rivers[cluster] < RIVER_SEA_PALETTE).any():
            continue
        any(
            _repair_run(rivers, grown, owned, border, cities, heights, packed, slivers)
            for grown in _grown_runs(rivers, cluster, owned)
        )


def cutting_course(labels: np.ndarray, river: np.ndarray, owned: np.ndarray) -> np.ndarray:
    """Course pixels beside a piece that the course cuts off their own province."""
    result = np.zeros(river.shape, bool)
    nothing = np.zeros(river.shape, bool)
    for province in rivers_splitting_provinces(labels, river, owned, nothing):
        ys, xs = np.nonzero(labels == province)
        box = np.s_[max(0, ys.min() - 1):ys.max() + 2, max(0, xs.min() - 1):xs.max() + 2]
        inside = labels[box] == province
        stray = stray_land(inside, river[box], nothing[box])
        result[box] |= inside & river[box] & neighbours_of(stray)
    return result


def flip_corners(
    rivers: np.ndarray, owned: np.ndarray, border: np.ndarray, cities: np.ndarray, labels: np.ndarray, takers: np.ndarray
) -> None:
    """Move every course corner that lies inside a province to the opposite corner of its square, in place.

    A course that follows a diagonal province border turns on pixels that
    touch the far province only at a corner. The pixel diagonally opposite
    across the turn touches both course neighbours too; when it lies on a
    border, the course turns there instead. On the edge of the scope that
    pixel belongs to the foreign province; ``takers`` holds the foreign
    pixels a course may turn on, so the course stays on the state line. A
    move that would cut a piece off any province is skipped.
    """
    nothing = np.zeros((5, 5), bool)
    for _round in range(RIVER_SETTLE_ROUNDS):
        river = rivers < RIVER_SEA_PALETTE
        # A turn beside a source, flow-in or split pixel stays, so the marker keeps its course.
        markers = river & (rivers < WIDTH_STEPS[0])
        near_marker = markers | neighbours_of(markers)
        moved = False
        for y, x in zip(*np.nonzero(river & owned & ~border & ~near_marker)):
            sides = [(y + dy, x + dx) for dy, dx in ((-1, 0), (1, 0), (0, -1), (0, 1)) if river[y + dy, x + dx]]
            if len(sides) != 2 or sides[0][0] == sides[1][0] or sides[0][1] == sides[1][1]:
                continue
            qy = sides[0][0] + sides[1][0] - y
            qx = sides[0][1] + sides[1][1] - x
            if river[qy, qx] or not takers[qy, qx] or not border[qy, qx] or cities[qy, qx] or near_marker[qy, qx]:
                continue
            others = [
                (qy + dy, qx + dx)
                for dy, dx in ((-1, 0), (1, 0), (0, -1), (0, 1))
                if river[qy + dy, qx + dx] and (qy + dy, qx + dx) not in sides
            ]
            if others:
                continue
            trial = river.copy()
            trial[y, x] = False
            trial[qy, qx] = True
            box = np.s_[y - 2:y + 3, x - 2:x + 3]
            local = labels[box]
            if any(stray_land(local == value, trial[box], nothing).any() for value in np.unique(local)):
                continue
            rivers[qy, qx] = rivers[y, x]
            rivers[y, x] = RIVER_LAND_PALETTE
            river = trial
            moved = True
        if not moved:
            return


def ivn_edge_turns(labels: np.ndarray, owned: np.ndarray) -> np.ndarray:
    """Scope pixels where a course on the IVN state line must turn inside its province.

    On a diagonal step of that line the only other turn lies on an IVN
    pixel, whose rivers the IVN geography builder owns, and no other scope
    province touches the pixel.
    """
    ivn = np.isin(labels, sorted(scoped_provinces()))
    diagonal = np.zeros(labels.shape, bool)
    other = np.zeros(labels.shape, bool)
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            shifted = np.roll(np.roll(labels, dy, 0), dx, 1)
            if dy and dx:
                diagonal |= np.roll(np.roll(ivn, dy, 0), dx, 1)
            other |= (shifted != labels) & np.roll(np.roll(owned, dy, 0), dx, 1)
    return owned & diagonal & ~other


def coastal_courses(window: Window, shape: tuple[int, int]) -> np.ndarray:
    """The river pixels of the window that the coastal geography builder writes."""
    result = np.zeros(shape, bool)
    for x, y in RIVER_COURSES:
        if window.x0 <= x < window.x0 + shape[1] and window.y0 <= y < window.y0 + shape[0]:
            result[y - window.y0, x - window.x0] = True
    return result


def corner_takers(labels: np.ndarray, owned: np.ndarray, water: np.ndarray, window: Window) -> np.ndarray:
    """Foreign land beside the scope where a state-line course may turn.

    The IVN geography builder owns the rivers of its provinces, and the
    coastal builder the pixels it repairs and the courses it writes; those
    pixels and their neighbours are never taken.
    """
    coastal = coastal_courses(window, labels.shape)
    for x, y in PROVINCE_PIXEL_REPAIRS:
        if window.x0 <= x < window.x0 + labels.shape[1] and window.y0 <= y < window.y0 + labels.shape[0]:
            coastal[y - window.y0, x - window.x0] = True
    others = np.isin(labels, sorted(scoped_provinces())) | coastal | neighbours_of(coastal)
    return neighbours_of(owned) & ~owned & ~water & ~others


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
    # A new pixel near a source, flow-in or split pixel would crowd the junction.
    beside_marker = (distance_transform_edt(~(river & (rivers < WIDTH_STEPS[0]))) <= MARKER_CLEARANCE) & ~river
    # A course beside another river may have to touch it on its way round.
    for allowed in ((free | end_mask) & ~beside_marker, (loose | end_mask) & ~beside_marker):
        forbidden = np.zeros(river.shape, bool)
        for _attempt in range(ROUTE_ATTEMPTS):
            try:
                path = _route_river(ends[0], [ends[1]], allowed & ~forbidden, heights, packed)
            except RuntimeError:
                break
            if len(path) > REPAIR_DETOUR * (abs(ends[0][0] - ends[1][0]) + abs(ends[0][1] - ends[1][1]) + 2):
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
    open_goals = [goal for goal in goals if final[goal[1], goal[0]]]
    if not open_goals:
        raise RuntimeError("every mouth pixel is closed")
    path.extend(_route_river(path[-1], open_goals, final, heights, packed)[1:])
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

    A flow-in pixel touches the river at one side only, beside a receiver
    pixel whose course runs straight through it, and the pixel behind it
    lies straight away from the receiver. Every other pixel
    beside a river is closed to the course, so the tributary arrives at a
    right angle. ``taken`` pixels lie too close to another junction.
    """
    mx, my = window.local(river["points"][-1])
    touching = np.zeros(current.shape, np.int8)
    for axis, shift in ((0, 1), (0, -1), (1, 1), (1, -1)):
        touching += np.roll(current, shift, axis)
    clear = lane & ~current & ~neighbours_of(current)
    approaches = {}
    across = current & np.roll(current, 1, 1) & np.roll(current, -1, 1) & (touching == 2)
    along = current & np.roll(current, 1, 0) & np.roll(current, -1, 0) & (touching == 2)
    for py, px in zip(*np.nonzero(receiver & (across | along))):
        if max(abs(px - mx), abs(py - my)) > CONFLUENCE_RADIUS:
            continue
        sides = ((0, 1), (0, -1)) if across[py, px] else ((1, 0), (-1, 0))
        for dx, dy in sides:
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
    tolerated: np.ndarray | None = None,
) -> RiverNetwork:
    """Rebuild the river layer of the scope from the existing rivers and the data.

    ``tolerated`` pixels may be cut off a province; only the mending pass
    of the planner routes with them.
    """
    rivers = source.copy()
    rivers[owned] = reference_rivers(data, window, rivers.shape)[owned]
    ring = corner_takers(labels, owned, water, window) if data.get("ring_rivers") else np.zeros(owned.shape, bool)
    rivers[ring] = reference_rivers(data, window, rivers.shape, "ring_rivers")[ring]
    apply_river_edits(data, window, rivers, owned | ring)
    restored = rivers.copy()
    existing = river_masks(rivers, water)
    packed = labels.astype(np.uint32)
    border = province_borders(packed)
    origin = (window.x0, window.y0)
    # No piece of a province may be cut off, however small.
    slivers = np.zeros(labels.shape, bool) if tolerated is None else tolerated
    # The coastal builder writes a few course pixels itself; they and the pixels beside them stay.
    foreign_course = coastal_courses(window, labels.shape)
    editable = owned & ~foreign_course & ~neighbours_of(foreign_course)
    flip_corners(rivers, editable, border, cities, packed, editable | ring)
    repair_existing_rivers(rivers, existing, editable, border, cities, heights, packed, slivers)
    issues = []
    edit_owned_reaches(data, window, rivers, water)
    issues.extend(widen_owned_reaches(data, window, rivers, labels, water))
    reach, _reach_issues = owned_reach_mask(data, window, rivers, labels, water)
    thin_courses(rivers, editable | reach, water, line_pixels(packed))
    # Thinning leaves new turns where a course was two pixels wide.
    flip_corners(rivers, editable, border, cities, packed, editable | ring)
    settle_existing_markers(rivers, water, editable & ~neighbours_of(reach))
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
    network.issues.extend(river_network_issues(network, labels, owned, water, lakes, cities, restored, origin, slivers))
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


def edit_owned_reaches(data: dict, window: Window, rivers: np.ndarray, water: np.ndarray) -> None:
    """Apply the authored pixel edits of every owned reach, in place.

    Where the reach meets its tributaries the existing course may need one
    pixel moved so that every junction is a plain T; ``drop`` pixels leave the
    course and ``add`` pixels join it at the reach width.
    """
    for reach in data.get("owned_reaches", []):
        for point in reach.get("drop", []):
            x, y = window.local(point)
            rivers[y, x] = RIVER_LAND_PALETTE
        for point in reach.get("add", []):
            x, y = window.local(point)
            if not water[y, x]:
                rivers[y, x] = int(reach["width"])


def widen_owned_reaches(
    data: dict, window: Window, rivers: np.ndarray, labels: np.ndarray, water: np.ndarray
) -> list[str]:
    """Raise the width palette of every owned reach to its authored width, in place.

    Widths only grow, so a widened reach stays as it is on the next pass.
    """
    issues = []
    for reach in data.get("owned_reaches", []):
        try:
            path = trace_reach(reach, window, river_masks(rivers, water), labels)
        except RuntimeError as error:
            issues.append(str(error))
            continue
        # The engine walks a course through side neighbours; a diagonal step
        # of the existing course gets the corner pixel that closes it.
        for (ax, ay), (bx, by) in zip(path, path[1:]):
            if ax != bx and ay != by:
                corners = [(bx, ay), (ax, by)]
                free = [(x, y) for x, y in corners if not water[y, x]]
                if free and not any(rivers[y, x] < RIVER_SEA_PALETTE for x, y in corners):
                    x, y = free[0]
                    rivers[y, x] = int(reach["width"])
        mask, reach_issues = owned_reach_mask({"owned_reaches": [reach]}, window, rivers, labels, water)
        issues.extend(reach_issues)
        rivers[mask] = np.maximum(rivers[mask], int(reach["width"]))
    return issues


def river_degree(river: np.ndarray) -> np.ndarray:
    """Number of river pixels beside each pixel."""
    count = np.zeros(river.shape, np.int8)
    for axis, shift in ((0, 1), (0, -1), (1, 1), (1, -1)):
        count += np.roll(river, shift, axis)
    return count


def river_blocks(river: np.ndarray) -> np.ndarray:
    """Pixels of every 2x2 square that is river throughout."""
    square = river[:-1, :-1] & river[:-1, 1:] & river[1:, :-1] & river[1:, 1:]
    result = np.zeros(river.shape, bool)
    result[:-1, :-1] |= square
    result[:-1, 1:] |= square
    result[1:, :-1] |= square
    result[1:, 1:] |= square
    return result


def _removable(river: np.ndarray, y: int, x: int) -> bool:
    """A course pixel whose neighbours stay joined without it and that ends no course."""
    sides = [(y + dy, x + dx) for dy, dx in ((-1, 0), (1, 0), (0, -1), (0, 1)) if river[y + dy, x + dx]]
    if len(sides) < 2:
        return False
    local = river[y - 1:y + 2, x - 1:x + 2].copy()
    local[1, 1] = False
    pieces, _count = label(local)
    return len({int(pieces[sy - y + 1, sx - x + 1]) for sy, sx in sides}) == 1


def thin_courses(rivers: np.ndarray, editable: np.ndarray, water: np.ndarray, lines: np.ndarray) -> None:
    """Reduce every editable course to a simple line, in place.

    The engine draws a river by walking from pixel to pixel; a 2x2 square or a
    pixel with three course neighbours gives the walk a second way and it
    stops or turns there. Such a pixel is removed when its neighbours stay
    joined without it; pixels off a province border line go first. A
    one-pixel spur left beside such a pixel goes too. Markers and the pixel a
    flow-in marker touches stay.
    """
    while True:
        river = river_masks(rivers, water)
        markers = river & (rivers < WIDTH_STEPS[0])
        degree = river_degree(river & ~markers)
        crowded = editable & river & ~markers & ~neighbours_of(markers) & (river_blocks(river) | (degree >= 3))
        # A one-pixel spur beside a crowded pixel is no course of its own.
        spurs = editable & river & ~markers & ~neighbours_of(markers) & (degree == 1) & neighbours_of(river & (degree >= 3))
        if spurs.any():
            rivers[spurs] = RIVER_LAND_PALETTE
            continue
        removed = False
        for preference in (crowded & ~lines, crowded & lines):
            for y, x in zip(*np.nonzero(preference)):
                if _removable(river, int(y), int(x)):
                    rivers[y, x] = RIVER_LAND_PALETTE
                    river[y, x] = False
                    removed = True
            if removed:
                break
        if not removed:
            return


def _course_ahead(river: np.ndarray, start: tuple[int, int], closed: set[tuple[int, int]]) -> int:
    """Number of course pixels reached from ``start`` without entering ``closed`` pixels."""
    seen = {start}
    queue = deque([start])
    while queue:
        x, y = queue.popleft()
        for step in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if river[step[1], step[0]] and step not in seen and step not in closed:
                seen.add(step)
                queue.append(step)
    return len(seen)


def settle_existing_markers(rivers: np.ndarray, water: np.ndarray, editable: np.ndarray) -> None:
    """Give the existing courses of ``editable`` the markers the engine walks from, in place.

    The engine stops a walk where it has two ways on. At such a fork the
    walk keeps the way with the longer course ahead; the first pixel of the
    other way becomes a flow-in pixel, so that branch is drawn as a
    tributary. A course without any source or flow-in pixel gets a source at
    its end farthest from water. The walks run on a copy padded with land,
    so a course may reach the edge of the window.
    """
    padded = np.pad(rivers, 1, constant_values=RIVER_LAND_PALETTE)
    _settle_markers(padded, np.pad(water, 1), np.pad(editable, 1))
    rivers[...] = padded[1:-1, 1:-1]


def _settle_markers(rivers: np.ndarray, water: np.ndarray, editable: np.ndarray) -> None:
    for _round in range(RIVER_SETTLE_ROUNDS):
        river = river_masks(rivers, water)
        red = branch_markers(rivers, river)
        _visits, forks, walks = walk_courses(rivers, water)
        ends = {walk[-1]: walk for walk in walks.values()}
        settled = False
        for fx, fy in forks:
            walk = ends.get((fx, fy))
            if walk is None or not editable[fy, fx]:
                continue
            closed = set(walk)
            ways = [
                (nx, ny)
                for nx, ny in ((fx + 1, fy), (fx - 1, fy), (fx, fy + 1), (fx, fy - 1))
                if river[ny, nx] and not red[ny, nx] and (nx, ny) not in closed and editable[ny, nx]
            ]
            if len(ways) < 2:
                continue
            ways.sort(key=lambda way: (-_course_ahead(river & ~red, way, closed), way[1], way[0]))
            for x, y in ways[1:]:
                rivers[y, x] = RIVER_FLOW_IN_PALETTE
            settled = True
        if settled:
            continue
        settled = add_missing_sources(rivers, water, editable)
        if not settled:
            return


def add_missing_sources(rivers: np.ndarray, water: np.ndarray, editable: np.ndarray) -> bool:
    """Put a source on every editable course that has no marker at all; report whether one was added."""
    river = river_masks(rivers, water)
    pieces, count = label(river)
    added = False
    shore = distance_transform_edt(~water)
    degree = river_degree(river)
    for piece in range(1, count + 1):
        course = pieces == piece
        if (rivers[course] <= RIVER_FLOW_OUT_PALETTE).any() or not editable[course].all():
            continue
        ends = course & (degree <= 1)
        ys, xs = np.nonzero(ends if ends.any() else course)
        index = int(np.lexsort((xs, ys, -shore[ys, xs]))[0])
        rivers[ys[index], xs[index]] = RIVER_SOURCE_PALETTE
        added = True
    return added


def branch_markers(rivers: np.ndarray, river: np.ndarray) -> np.ndarray:
    """Flow-in and split pixels: each starts a branch the engine walks away from its river."""
    return river & ((rivers == RIVER_FLOW_IN_PALETTE) | (rivers == RIVER_FLOW_OUT_PALETTE))


def course_shape_issues(rivers: np.ndarray, scope: np.ndarray, water: np.ndarray, origin: tuple[int, int]) -> list[str]:
    """Every course is a simple line; only a receiver pixel touches one branch marker besides its course."""
    river = river_masks(rivers, water)
    red = branch_markers(rivers, river)
    issues = []
    blocks = river_blocks(river) & scope
    if blocks.any():
        issues.append(f"{int(blocks.sum())} river pixels form 2x2 blocks, first at {_map_point(blocks, origin)}")
    plain = river_degree(river & ~red)
    reds = river_degree(red)
    crowded = scope & river & ~red & ((plain > 2) | (reds > 1))
    if crowded.any():
        issues.append(f"{int(crowded.sum())} river pixels have a third course neighbour, first at {_map_point(crowded, origin)}")
    red_crowded = scope & red & (river_degree(river) > 2)
    if red_crowded.any():
        issues.append(f"flow-in pixels touch more than two course pixels, first at {_map_point(red_crowded, origin)}")
    return issues


def walk_courses(rivers: np.ndarray, water: np.ndarray) -> tuple[np.ndarray, list[tuple[int, int]], dict[tuple[int, int], list]]:
    """Walk every river as the engine draws it: from each source pixel and each flow-in pixel.

    A walk never enters another flow-in pixel. From a flow-in pixel it starts
    into the tributary: the course pixel beside it with no other course
    neighbour than the one it leads on to. Returns how often each pixel was
    walked, the pixels where a walk had two ways on, and every walk by its start.
    A split pixel starts its branch the same way.
    """
    river = river_masks(rivers, water)
    red = branch_markers(rivers, river)
    visits = np.zeros(rivers.shape, np.int16)
    forks = []
    walks = {}
    starts = [(int(x), int(y)) for y, x in zip(*np.nonzero(river & ((rivers == RIVER_SOURCE_PALETTE) | red)))]
    for start in starts:
        walk = [start]
        seen = {start}
        if red[start[1], start[0]]:
            first = tributary_starts(river, start)
            if len(first) != 1:
                forks.append(start)
                continue
            walk.append(first[0])
            seen.add(first[0])
        while True:
            x, y = walk[-1]
            ways = [
                (nx, ny)
                for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1))
                if river[ny, nx] and not red[ny, nx] and (nx, ny) not in seen
            ]
            if not ways:
                break
            if len(ways) > 1:
                forks.append((x, y))
                break
            walk.append(ways[0])
            seen.add(ways[0])
        for x, y in walk:
            visits[y, x] += 1
        walks[start] = walk
    return visits, forks, walks


def drawing_issues(
    data: dict, rivers: np.ndarray, labels: np.ndarray, water: np.ndarray, scope: np.ndarray
) -> list[str]:
    """Every river pixel in scope is drawn by exactly one walk; each owned reach reaches its lake."""
    visits, forks, walks = walk_courses(rivers, water)
    river = river_masks(rivers, water)
    issues = []
    in_scope = [point for point in forks if scope[point[1], point[0]]]
    if in_scope:
        issues.append(f"river walks fork at {in_scope[:3]}")
    missed = scope & river & (visits == 0)
    if missed.any():
        issues.append(f"{int(missed.sum())} river pixels are drawn by no walk, first at {_map_point(missed, (0, 0))}")
    twice = scope & river & (visits > 1)
    if twice.any():
        issues.append(f"{int(twice.sum())} river pixels are drawn twice, first at {_map_point(twice, (0, 0))}")
    full = Window(0, rivers.shape[0], 0, rivers.shape[1])
    for reach in data.get("owned_reaches", []):
        path = trace_reach(reach, full, river, labels)
        mouth = neighbours_of(labels == int(reach["mouth"]["lake"]))
        stems = [
            walk for start, walk in walks.items()
            if rivers[start[1], start[0]] == RIVER_SOURCE_PALETTE and path[0] in walk
        ]
        if len(stems) != 1 or not mouth[stems[0][-1][1], stems[0][-1][0]] or not set(path) <= set(stems[0]):
            issues.append(f"owned reach {reach['name']}: no single drawn course carries it into lake {reach['mouth']['lake']}")
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
    origin: tuple[int, int],
    slivers: np.ndarray,
) -> list[str]:
    """Validate the rivers of the scope: sources, borders, connectivity, branching and mouths.

    Every river pixel touches another province across a pixel edge, and no
    river pixel cuts any piece of a province off.
    """
    rivers = network.pixels
    river = river_masks(rivers, water)
    issues = []
    # Pixels the coastal builder writes are checked by that builder.
    window = Window(origin[1], origin[1] + labels.shape[0], origin[0], origin[0] + labels.shape[1])
    off_border = river & owned & ~province_borders(labels) & ~coastal_courses(window, labels.shape)
    off_border &= ~ivn_edge_turns(labels, owned)
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
    heights: np.ndarray,
    mon: np.ndarray,
    forest_zone: np.ndarray,
    marsh_zone: np.ndarray,
    desert_zone: np.ndarray | None = None,
) -> np.ndarray:
    """Return a terrain-type index per pixel (TYPE_ORDER), -1 outside MON.

    Relief decides mountains and hills first; low land in a marsh zone is
    marsh, then a forest zone gives forest and a desert zone desert.
    """
    slope = masked_slopes(heights, mon)
    mountain = mon & ((heights >= MOUNTAIN_HEIGHT) | (slope >= MOUNTAIN_SLOPE))
    shoulder = mon & ~mountain & neighbours_of(mountain)
    hills = mon & ~mountain & (shoulder | (heights >= HILLS_HEIGHT) | (slope >= HILLS_SLOPE))
    marsh = mon & ~mountain & ~hills & marsh_zone & (heights < MARSH_HEIGHT)
    forest = mon & ~mountain & ~hills & ~marsh & forest_zone
    result = np.full(heights.shape, -1, np.int8)
    result[mon] = TYPE_ORDER.index("plains")
    if desert_zone is not None:
        result[mon & ~mountain & ~hills & ~marsh & ~forest & desert_zone] = TYPE_ORDER.index("desert")
    result[forest] = TYPE_ORDER.index("forest")
    result[marsh] = TYPE_ORDER.index("marsh")
    result[hills] = TYPE_ORDER.index("hills")
    result[mountain] = TYPE_ORDER.index("mountain")
    return result


def restrict_classes(classes: np.ndarray, states: np.ndarray, data: dict) -> np.ndarray:
    """Demote every pixel class its region does not allow along CLASS_FALLBACK, in place."""
    for region in data.get("regions", {}).values():
        allowed = region.get("terrain_classes")
        if allowed is None:
            continue
        if "plains" not in allowed or set(allowed) - set(RURAL_TERRAINS):
            raise RuntimeError(f"region {region.get('name')}: terrain classes {allowed} must hold plains and rural classes only")
        inside = np.isin(states, [int(state_id) for state_id in region["states"]])
        for terrain in TYPE_ORDER:
            target = terrain
            while target not in allowed:
                target = CLASS_FALLBACK[target]
            if target != terrain:
                classes[inside & (classes == TYPE_ORDER.index(terrain))] = TYPE_ORDER.index(target)
    return classes


# New classes are appended, so the index of every older class stays.
TYPE_ORDER = ("plains", "forest", "marsh", "hills", "mountain", "desert")


def rural_terrain(counts: Counter) -> str:
    """The declared terrain of a rural province from its pixel classes.

    Without desert pixels this is the rule of the IVN geography. Desert
    yields to marsh, mountains, hills and forest as they do to one another,
    and wins at DESERT_SHARE or as the largest class.
    """
    if not counts.get("desert"):
        return province_terrain_type(counts)
    total = sum(counts.values())
    share = {terrain: counts.get(terrain, 0) / total for terrain in RURAL_TERRAINS}
    if share["marsh"] >= 0.35:
        return "marsh"
    if share["mountain"] >= 0.4:
        return "mountain"
    if share["mountain"] + share["hills"] >= 0.4:
        return "hills"
    if share["forest"] >= 0.4:
        return "forest"
    if share["desert"] >= DESERT_SHARE:
        return "desert"
    return max(RURAL_TERRAINS, key=lambda terrain: (counts.get(terrain, 0), -RURAL_TERRAINS.index(terrain)))


def kept_terrains(scope: Scope, definition: Definition) -> dict[int, str]:
    """Provinces whose declared terrain this builder keeps.

    A city terrain on the map stays unless the province is a settlement this
    builder carves; an adopted city keeps whatever it declares; a pinned
    province takes its authored terrain.
    """
    result = {}
    for province in scope.provinces:
        if province in scope.urban or province not in definition.rows:
            continue
        current = definition.rows[province][6]
        if current in CITY_TERRAINS or province in scope.adopted:
            result[province] = current
    result.update(scope.pinned)
    return result


def province_types(
    classes: np.ndarray,
    labels: np.ndarray,
    scope: Scope,
    urban_pixels: np.ndarray,
    kept: dict[int, str] | None = None,
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
    kept = kept or {}
    for province in scope.provinces:
        if province in scope.urban:
            desired[province] = "urban"
        elif province in kept:
            desired[province] = kept[province]
        elif province in counts:
            desired[province] = rural_terrain(counts[province])
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


@dataclass
class Footprints:
    """Built pixels of every carved settlement and the city group each one draws."""

    built: np.ndarray
    models: np.ndarray


def settlement_values(data: dict) -> dict[int, int]:
    """Victory-point value of every city and town province."""
    values = {}
    for _tag, entry in all_settlements(data):
        province = settlement_province(entry)
        if province is not None and entry["kind"] in ("city", "town"):
            values[int(province)] = int(entry.get("value") or 1)
    return values


def metro_pixels(value: int) -> int:
    return METRO_BASE_PIXELS + METRO_PIXELS_PER_VALUE * value


def footprint_score(shape: tuple[int, int], anchor: tuple[int, int], size: int, salt: int, origin: tuple[int, int]) -> np.ndarray:
    """Growth order of a footprint: distance from the anchor stretched into lobes, plus noise.

    ``origin`` is the map (x, y) of the first cell, so the noise follows map coordinates.
    """
    ay, ax = anchor
    ys, xs = np.mgrid[0:shape[0], 0:shape[1]].astype(float)
    angle = np.arctan2(ys - ay, xs - ax)
    stretch = np.ones(shape)
    for harmonic, amplitude in enumerate(FOOTPRINT_LOBES, 1):
        phase = 2.0 * np.pi * stable_unit_hash(salt, harmonic, 41)
        stretch += amplitude * np.cos(harmonic * angle - phase)
    radius = np.sqrt(size / np.pi)
    noise = lattice_noise(xs + origin[0], ys + origin[1], FOOTPRINT_NOISE_CELL, salt)
    return np.hypot(ys - ay, xs - ax) / (radius * stretch) + FOOTPRINT_NOISE * noise


def grow_footprint(allowed: np.ndarray, anchor: tuple[int, int], size: int, score: np.ndarray) -> np.ndarray:
    """Take ``size`` 4-connected allowed pixels from ``anchor`` (y, x) in the order of ``score``."""
    selected = np.zeros(allowed.shape, bool)
    ay, ax = anchor
    frontier = [(float(score[ay, ax]), ay, ax)]
    seen = {(ay, ax)}
    count = 0
    while frontier and count < size:
        _score, y, x = heapq.heappop(frontier)
        selected[y, x] = True
        count += 1
        for ny, nx in ((y + 1, x), (y - 1, x), (y, x + 1), (y, x - 1)):
            if (ny, nx) in seen or not (0 <= ny < allowed.shape[0] and 0 <= nx < allowed.shape[1]) or not allowed[ny, nx]:
                continue
            seen.add((ny, nx))
            heapq.heappush(frontier, (float(score[ny, nx]), ny, nx))
    return selected


def settlement_footprints(
    data: dict,
    scope: Scope,
    labels: np.ndarray,
    grid: np.ndarray,
    window: Window,
    states: np.ndarray,
    painted: np.ndarray,
    forbidden: np.ndarray,
) -> Footprints:
    """Lay out the houses of every carved city, district and town.

    A metropolis spreads over the neighbouring provinces of its state, a city
    fills about its own province with a ragged edge, and a town is a small
    patch inside its province. Footprints never overlap, cross a river bank
    or reach the shore band.
    """
    values = settlement_values(data)
    boxes = find_objects(grid)
    urban = np.isin(labels, sorted(scope.urban)) & painted
    built = np.zeros(labels.shape, bool)
    models = np.full(labels.shape, CITY_BACKGROUND_INDEX, np.uint8)
    margin = int(np.sqrt(metro_pixels(max(values.values(), default=METRO_VALUE)) / np.pi) * 2) + CITY_REACH + 4
    for province in sorted(scope.urban):
        if boxes[province - 1] is None:
            continue
        _oy, _ox, _inside, _depth, (cx, cy) = province_interior(grid, province, boxes[province - 1])
        ly, lx = cy - window.y0, cx - window.x0
        if not (0 <= ly < labels.shape[0] and 0 <= lx < labels.shape[1]):
            continue
        y0, y1 = max(ly - margin, 0), min(ly + margin + 1, labels.shape[0])
        x0, x1 = max(lx - margin, 0), min(lx + margin + 1, labels.shape[1])
        crop = (slice(y0, y1), slice(x0, x1))
        own = (labels[crop] == province) & painted[crop]
        if not own.any():
            continue
        value = values.get(province, LARGE_CITY_VALUE if province in scope.districts else 1)
        state = scope.state_of[province]
        rural = painted[crop] & (states[crop] == state) & ~urban[crop]
        if province in scope.towns:
            low, high = TOWN_PATCH
            size = low + int(stable_unit_hash(province, 0, 43) * (high - low + 1))
            reach = own
            model = SMALL_CITY_INDEX
        elif value >= METRO_VALUE:
            size = metro_pixels(value)
            reach = own | rural
            model = CITY_HOUSES_INDEX
        else:
            size = int(own.sum())
            grown = distance_transform_edt(~own) <= CITY_REACH
            reach = own | (grown & rural)
            model = CITY_HOUSES_INDEX if value >= LARGE_CITY_VALUE or province in scope.districts else SMALL_CITY_INDEX
        allowed = reach & ~forbidden[crop] & ~built[crop]
        if not allowed.any():
            allowed = own & ~built[crop]
        anchor = (ly - y0, lx - x0)
        if not allowed[anchor]:
            ys, xs = np.nonzero(allowed & own) if (allowed & own).any() else np.nonzero(allowed)
            nearest = int(np.argmin((ys - anchor[0]) ** 2 + (xs - anchor[1]) ** 2))
            anchor = (int(ys[nearest]), int(xs[nearest]))
        score = footprint_score(allowed.shape, anchor, size, province, (window.x0 + x0, window.y0 + y0))
        piece = grow_footprint(allowed, anchor, size, score)
        built[crop] |= piece
        models[crop][piece] = model
    return Footprints(built, models)


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
    """Give every scope province and every changed neighbour native unit anchors.

    A province without rows, or whose standing army stands off its interior
    centre or on another province, receives a fresh native set. A province
    whose slot set or moving rows no longer match its borders, or with a row
    on another province, keeps its standing slots that still stand inside
    and has the rest rebuilt in the engine's neighbour order. A neighbour
    outside the scope is checked when its borders changed in this pass or
    when it touches a province of the Stage 2 plan, so its moving slots
    follow its new neighbours. Every scope row then rests on the new
    heightmap. Rows stay grouped by slot in province order.
    """
    rows, newline = read_unitstacks(original)
    slots: dict[int, dict[int, list[str]]] = defaultdict(dict)
    for row in rows:
        slots[int(row[0])][int(row[1])] = row
    neighbours = province_neighbours(grid)
    local = province_neighbours(grid[window.s])
    old_local = province_neighbours(before[window.s])
    # Outside the scope only a province whose borders changed is touched; the
    # IVN builder places the anchors of its own provinces.
    later = set(scope.later) | {int(scope.planned[province]["parent"]) for province in scope.later}
    candidates = set(scope.provinces) | {
        province
        for province in set(local) | set(old_local)
        if local.get(province) != old_local.get(province) or local.get(province, set()) & later
    }
    candidates -= scoped_provinces()
    boxes = find_objects(grid)
    map_height = grid.shape[0]
    rebuilt: dict[int, dict[int, list[str]]] = {}
    # The coastal builder places the anchors of the provinces it repairs.
    foreign = frozenset(PROVINCE_REPAIR_PROVINCES)
    for province in sorted(candidates - foreign):
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
        # A row on another province's land was left behind when the province shrank.
        strays = {slot for slot, row in existing.items() if anchor_elsewhere(row, grid, kinds, province)}
        if 0 not in existing or 0 in strays or not standing_anchor_central(existing[0], grid, interior):
            keep = {}
            offset = existing[0][6] if 0 in existing else offset
        elif strays or set(existing) != native_slots(kind, len(neighbours[province])) or not moving_anchors_native(
            existing, contacts, map_height
        ):
            keep = {slot: row for slot, row in existing.items() if slot in STANDING_SLOTS and slot not in strays}
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


def anchor_elsewhere(row: list[str], grid: np.ndarray, kinds: dict[int, str], province: int) -> bool:
    """Whether a unit anchor stands on the land of another province."""
    x = round(float(row[2]))
    y = grid.shape[0] - 1 - round(float(row[4]))
    other = int(grid[y, x])
    return other != province and kinds.get(other) == "land"


def state_landforms(root: Path, states: list[int], data: dict | None = None) -> dict[int, str]:
    """The landform each state name gives; a region may author it for a name without one."""
    text = (root / STATE_NAMES).read_text(encoding="utf-8-sig")
    overrides = {
        int(state_id): landform
        for region in (data or {}).get("regions", {}).values()
        for state_id, landform in region.get("landforms", {}).items()
    }
    result = {}
    for state_id in states:
        match = re.search(rf"^\s*STATE_{state_id}:\d*\s*\"([^\"]*)\"", text, re.MULTILINE)
        if match is None:
            raise RuntimeError(f"STATE_{state_id}: no Russian name")
        name = match.group(1).lower().replace("ё", "е")
        kinds = sorted({kind for word, kind in NAMED_LANDFORMS.items() if word in name})
        if state_id in overrides:
            if kinds:
                raise RuntimeError(f"STATE_{state_id}: name {match.group(1)!r} already names a landform")
            kinds = [overrides[state_id]]
        if len(kinds) != 1:
            raise RuntimeError(f"STATE_{state_id}: name {match.group(1)!r} names no single landform")
        result[state_id] = kinds[0]
    return result


def stand_in_province(scope: Scope, province: int) -> int:
    """The rural province that represents an original province in the bands.

    A carved city or town is urban, so its remainder counts in its place; a
    split province counts once, as the part that keeps its id.
    """
    return scope.remainders.get(province, province) if province in scope.urban else province


def split_parents() -> dict[int, int]:
    """The parent of every state that the new-states builder split off another."""
    from tools.builders.build_adiscord_new_states import STATE_SPLITS

    return {int(child): int(split["parent"]) for child, split in STATE_SPLITS.items()}


def landform_issue(state_id: int | str, landform: str, counts: Counter, rural: int) -> str | None:
    if landform == "upland":
        high = (counts["hills"] + counts["mountain"]) / rural
        if high < UPLAND_HIGH_SHARE or counts["mountain"] < UPLAND_MIN_MOUNTAINS:
            return f"state {state_id} upland: {counts['hills']} hills and {counts['mountain']} mountain of {rural}"
        return None
    if landform == "lowland":
        low = (counts["plains"] + counts["forest"] + counts["marsh"]) / rural
        if low < LOWLAND_SHARE or counts["marsh"] < LOWLAND_MIN_MARSH:
            return f"state {state_id} lowland: {counts['marsh']} marsh and {low:.0%} low land of {rural}"
        return None
    if counts[landform] * 2 <= rural:
        return f"state {state_id} {landform}: only {counts[landform]} of {rural} rural provinces"
    return None


def terrain_issues(
    desired: dict[int, str],
    scope: Scope,
    landforms: dict[int, str],
    bands: dict[str, list[int]],
    region: str = "MON",
    unbanded: frozenset[int] = frozenset(),
) -> tuple[list[str], dict]:
    """Check the declared terrain of one region against its bands and its state names.

    The bands count the original provinces of the region, each through its
    stand-in, so carving and splitting never change their total. An
    ``unbanded`` province keeps a city terrain and counts nowhere.
    """
    issues = []
    original = [
        province
        for province in scope.original
        if scope.region_of[scope.state_of[province]] == region and province not in unbanded
    ]
    totals = Counter(desired[stand_in_province(scope, province)] for province in original)
    for terrain, (low, high) in bands.items():
        if not low <= totals.get(terrain, 0) <= high:
            issues.append(f"{region}: {totals.get(terrain, 0)} {terrain} provinces lie outside the band {low}-{high}")
    other = set(totals) - set(bands)
    if other:
        issues.append(f"{region}: unexpected declared terrain {sorted(other)}")
    per_state = {}
    # A half split off a state with the landform of its parent shows it
    # together with the parent: the landform was authored for the whole land.
    parents = split_parents()
    families: dict[int, list[int]] = defaultdict(list)
    for state_id in scope.states:
        if scope.region_of[state_id] != region:
            continue
        parent = parents.get(state_id)
        joined = parent in scope.region_of and landforms.get(parent) == landforms[state_id]
        families[parent if joined else state_id].append(state_id)
    for root_state, members in families.items():
        family_counts: Counter = Counter()
        for state_id in members:
            rural = [
                desired[province]
                for province, owner in scope.state_of.items()
                if owner == state_id and province not in scope.urban and province not in unbanded
            ]
            per_state[state_id] = dict(Counter(rural))
            family_counts.update(rural)
        # A state of kept city provinces only has no landform to show.
        if not family_counts:
            continue
        label = "+".join(str(state_id) for state_id in sorted(members))
        issue = landform_issue(label, landforms[root_state], family_counts, sum(family_counts.values()))
        if issue:
            issues.append(issue)
    provinces = scope.region_provinces(region)
    forbidden = sorted(province for province in provinces if desired[province] in FORBIDDEN_TERRAINS)
    if forbidden:
        issues.append(f"forbidden terrain in {forbidden}")
    held = sum(
        1
        for province in scope.original
        if scope.region_of[scope.state_of[province]] == region and province in unbanded
    )
    return issues, {"totals": dict(totals), "states": per_state, "unbanded": held}


@dataclass
class Geography:
    """Every derived layer of the window, shared by the plan and the previews."""

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
    frozen: np.ndarray | None = None
    # Adopted cities and kept city terrains: their terrain, city mask and trees stay.
    held: np.ndarray | None = None
    # Urban-province pixels without houses, and the city group of every built pixel.
    unbuilt: np.ndarray | None = None
    models: np.ndarray | None = None

    @property
    def kept(self) -> np.ndarray:
        """Scope pixels whose terrain, city mask and trees stay as they are."""
        result = np.zeros(self.mon.shape, bool)
        for mask in (self.frozen, self.held):
            if mask is not None:
                result |= mask
        return result

    @property
    def painted(self) -> np.ndarray:
        """Scope pixels whose terrain, city mask and trees this builder paints."""
        return self.mon & ~self.kept


@dataclass
class Ground:
    """Province masks and the authored relief of the window, before rivers.

    ``mon`` is the whole scope: MON and, in Stage 2, its neighbours.
    ``frozen`` scope pixels beside the IVN geography keep their heights,
    terrain and trees.
    """

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
    frozen: np.ndarray | None = None


def lookup_raster(labels: np.ndarray, values: dict[int, int], dtype=np.int32) -> np.ndarray:
    """Map every province label of ``labels`` to its value, 0 where it has none."""
    table = np.zeros(int(max(int(labels.max()), max(values, default=0))) + 1, dtype)
    for province, value in values.items():
        table[province] = value
    return table[labels]


def frozen_pixels(
    data: dict,
    labels: np.ndarray,
    scope: np.ndarray,
    window: Window,
    heights: np.ndarray | None = None,
    states: np.ndarray | None = None,
) -> np.ndarray:
    """Scope pixels that keep their heights, terrain and trees.

    The band beside the IVN geography stays, because that builder blends
    into the nearest foreign heights; an authored keep zone holds a massif
    whose existing relief stays as it is. A region's ``keep_provinces`` keep
    the ground a landmark stands on, and its ``keep_above`` the existing
    heights from that level up, so permanent snow stays where it lies.
    """
    result = np.zeros(scope.shape, bool)
    protected = np.isin(labels, list(scoped_provinces()))
    if protected.any():
        result |= scope & (distance_transform_edt(~protected) <= IVN_CLEARANCE)
    if data.get("keep_zones"):
        gy, gx = np.mgrid[window.y0:window.y1, window.x0:window.x1].astype(float)
        result |= scope & zone_mask(gx, gy, data["keep_zones"])
    for region in data.get("regions", {}).values():
        if region.get("keep_provinces"):
            result |= scope & np.isin(labels, [int(province) for province in region["keep_provinces"]])
        if region.get("keep_above") is not None:
            if heights is None or states is None:
                raise RuntimeError("a keep_above region needs the source heights and the state raster")
            # New relief must stay below the kept level, or a second pass would keep more.
            if int(region.get("heights", data["heights"])["max"]) >= int(region["keep_above"]):
                raise RuntimeError(f"region {region.get('name')}: its height maximum must stay below keep_above")
            inside = np.isin(states, [int(state_id) for state_id in region["states"]])
            result |= scope & inside & (heights >= int(region["keep_above"]))
    return result


def stage_belt(data: dict, scope: np.ndarray, states: np.ndarray) -> np.ndarray:
    """Pixels of a later relief group within one feather of an earlier group.

    They keep their heights: the earlier relief blends into them and so
    stays as it was when its stage was applied. Their terrain, city masks
    and trees follow their own group.
    """
    result = np.zeros(scope.shape, bool)
    groups = relief_groups(data)
    earlier = scope & np.isin(states, groups[0][0])
    for group_states, _view in groups[1:]:
        member = scope & np.isin(states, group_states)
        if earlier.any():
            result |= member & (distance_transform_edt(~earlier) <= float(data["heights"]["feather"]))
        earlier |= member
    return result


def prepare_ground(
    root: Path, data: dict, scope: Scope, grid: np.ndarray, kinds: dict[int, str], heights: np.ndarray, window: Window
) -> Ground:
    """Build the relief of the scope and of its canyon walls from unchanging inputs only.

    The border blend reads the heights outside the scope or in its frozen
    band, and inside an external far-wall band the heights of the land
    beyond it, so the relief never feeds back on itself.
    """
    labels = window_labels(grid, window)
    mon = np.isin(labels, list(scope.provinces))
    water = np.isin(labels, [province for province, kind in kinds.items() if kind in ("sea", "lake")])
    states = lookup_raster(labels, scope.state_of)
    cities = np.isin(labels, list(scope.urban))
    frozen = frozen_pixels(data, labels, mon, window, heights, states)
    editable = mon & ~frozen & ~stage_belt(data, mon, states)
    canyons = canyon_layers(root, data, labels, mon, water, scope.planned)
    reference = canyon_reference(heights, canyons, mon)
    target = np.zeros(mon.shape)
    for group_states, view in relief_groups(data):
        member = mon & np.isin(states, group_states)
        if member.any():
            target = np.where(member, relief_target(view, window, member, states), target)
    blended, weight = border_blend(target, reference, editable, float(data["heights"]["feather"]))
    relief_scope = editable.copy()
    clearance = np.zeros(mon.shape, bool)
    for canyon in canyons:
        if canyon.external:
            blended = np.where(canyon.band, reference, blended)
            relief_scope |= canyon.band
        clearance |= mon & (canyon.distance < CANYON_SETTLEMENT_CLEARANCE)
    field = cut_canyons(blended, canyons, mon, window, float(data["heights"]["min"]))
    mouths = {int(river["mouth"]["lake"]) for river in data["rivers"] if "lake" in river["mouth"]}
    lake_ids = sorted(
        province for province in np.unique(labels[water]).tolist() if kinds[province] == "lake" or province in mouths
    )
    return Ground(labels, mon, water, states, cities, canyons, relief_scope, clearance, field, weight, lake_ids, frozen)


def ground_rivers(
    data: dict, window: Window, ground: Ground, rivers: np.ndarray, tolerated: np.ndarray | None = None
) -> RiverNetwork:
    routing = np.clip(np.rint(ground.field), 0, 255).astype(np.int16)
    return mon_rivers(
        data,
        window,
        rivers,
        ground.labels,
        ground.mon,
        ground.water,
        ground.lake_ids,
        ground.cities,
        routing,
        ground.canyons,
        tolerated,
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
    # Stage 2 carves every village into a town province of its own.
    cores = {} if scope.towns else village_cores(data, labels, grid, window, forbidden | ground.cities)
    floor, ceiling = height_limits(data, ground.states)
    kept = kept_terrains(scope, definition)
    held_provinces = sorted(scope.adopted | {province for province, terrain in kept.items() if terrain not in RURAL_PALETTES})
    held = mon & np.isin(labels, held_provinces) if held_provinces else None
    painted = mon.copy()
    for mask in (ground.frozen, held):
        if mask is not None:
            painted &= ~mask
    footprints = settlement_footprints(data, scope, labels, grid, window, ground.states, painted, forbidden)
    # Houses outside the urban provinces; urban ground left unbuilt shows the land around it.
    fringe = footprints.built & ~ground.cities
    unbuilt = ground.cities & painted & ~footprints.built
    # Houses spread over rural provinces stand on their relief as it is.
    towns = ground.cities.copy()
    for core in cores.values():
        towns |= core
    # Kept cities lie on the eased relief like carved ones.
    if held is not None:
        towns |= held
    groups = [(mon & np.isin(ground.states, group_states), view) for group_states, view in relief_groups(data)]
    # Valleys, town relief and pixel classes read the land of their own relief group only.
    carved = ground.field
    for member, _view in groups:
        carved = carve_valleys(carved, np.where(member, network.pixels, RIVER_LAND_PALETTE), member, ground.weight, floor)
        ease_towns_into_relief(carved, member, towns & member)
    carve_ravines(carved, data, network, ground.relief_scope)
    # Provinces declare the terrain of the land before the rivers cut through it:
    # a gorge does not turn a mountain province into plains.
    landform = np.clip(np.rint(carved), floor, ceiling).astype(np.uint8)
    landform = np.where(ground.relief_scope, landform, sources["heightmap"][window.s])
    carve_river_beds(carved, network.pixels, ground.water, ground.relief_scope, sources["heightmap"][window.s], ground.weight)
    heights = np.clip(np.rint(carved), floor, ceiling).astype(np.uint8)
    heights = np.where(ground.relief_scope, heights, sources["heightmap"][window.s])
    gy, gx = np.mgrid[window.y0:window.y1, window.x0:window.x1].astype(float)
    classes = np.full(heights.shape, -1, np.int8)
    for member, view in groups:
        desert = zone_mask(gx, gy, view["desert_zones"]) if view.get("desert_zones") else None
        group_classes = classify_pixels(
            landform, member, zone_mask(gx, gy, view["forest_zones"]), zone_mask(gx, gy, view["marsh_zones"]), desert
        )
        classes = np.where(member, group_classes, classes)
    restrict_classes(classes, ground.states, data)
    # Houses spread over a rural province do not change the terrain it declares.
    urban_pixels = ground.cities.copy()
    for core in cores.values():
        urban_pixels |= core
    desired, counts = province_types(classes, labels, scope, urban_pixels, kept)
    return Geography(
        window, labels, mon, ground.states, ground.water, ground.cities, heights, network, classes, desired, counts,
        cores, fringe, shore, ground.relief_scope, ground.canyons, ground.frozen, held, unbuilt, footprints.models,
    )


def height_limits(data: dict, states: np.ndarray) -> tuple[float | np.ndarray, float | np.ndarray]:
    """The lowest and highest relief of every pixel: the MON range, or the range its region authors."""
    low = float(data["heights"]["min"])
    high = float(data["heights"]["max"])
    regions = [region for region in data.get("regions", {}).values() if "heights" in region]
    if not regions:
        return low, high
    low_raster = np.full(states.shape, low)
    high_raster = np.full(states.shape, high)
    for region in regions:
        inside = np.isin(states, [int(state_id) for state_id in region["states"]])
        low_raster[inside] = float(region["heights"]["min"])
        high_raster[inside] = float(region["heights"]["max"])
    return low_raster, high_raster


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


def downstream_walks(rivers: np.ndarray, water: np.ndarray) -> list[tuple[list[tuple[int, int]], bool]]:
    """Every river walk in the direction its water flows, with whether it ends in a receiver.

    The engine walks a river from its source pixel downstream and a
    tributary from its flow-in pixel upstream; a split branch leaves its
    river downstream. A tributary therefore ends on its flow-in pixel.
    """
    course = rivers.copy()
    course[[0, -1], :] = RIVER_LAND_PALETTE
    course[:, [0, -1]] = RIVER_LAND_PALETTE
    _visits, _forks, walks = walk_courses(course, water)
    result = []
    for (x, y), walk in walks.items():
        if course[y, x] == RIVER_FLOW_IN_PALETTE:
            result.append((walk[::-1], True))
        else:
            result.append((walk, False))
    return result


def carve_river_beds(
    field: np.ndarray,
    rivers: np.ndarray,
    water: np.ndarray,
    scope: np.ndarray,
    outside: np.ndarray,
    weight: np.ndarray,
) -> None:
    """Lower the ground so that no river climbs on its way downstream, in place.

    The bed of a walk is the lowest ground met so far. Tributaries go before
    their receiver, which is no higher than any of them at the junction, so
    a tributary never climbs into its river. Only pixels of ``scope``
    change, and ground is only ever lowered; elsewhere the walk meets the
    heights of ``outside``. The valley fades with the border ``weight`` of
    the relief, so it leaves no wall against unchanged land.
    """
    ground = np.where(scope, field, outside.astype(float))
    walks = downstream_walks(rivers, water)
    owner: dict[tuple[int, int], int] = {}
    for index, (walk, _joins) in enumerate(walks):
        for point in walk:
            owner.setdefault(point, index)
    # The receiver pixel beside the flow-in pixel of every tributary.
    junctions: dict[int, tuple[int, tuple[int, int]]] = {}
    for index, (walk, joins) in enumerate(walks):
        if not joins:
            continue
        x, y = walk[-1]
        for point in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if owner.get(point, index) != index:
                junctions[index] = (owner[point], point)
                break
    incoming = Counter(receiver for receiver, _point in junctions.values())
    caps: dict[tuple[int, int], float] = {}
    beds = np.full(field.shape, np.nan)
    pending = list(range(len(walks)))
    while pending:
        ready = [index for index in pending if incoming[index] == 0] or pending[:1]
        for index in ready:
            bed = np.inf
            for x, y in walks[index][0]:
                bed = min(bed, float(ground[y, x]), caps.get((x, y), np.inf))
                beds[y, x] = bed if np.isnan(beds[y, x]) else min(beds[y, x], bed)
            if index in junctions:
                receiver, point = junctions[index]
                caps[point] = min(caps.get(point, np.inf), bed)
                incoming[receiver] -= 1
        pending = [index for index in pending if index not in ready]
    height, width = field.shape
    for y, x in zip(*np.nonzero(~np.isnan(beds) & scope)):
        bed = float(beds[y, x])
        cut = float(ground[y, x]) - bed
        if cut <= 0.5:
            continue
        radius = RIVER_VALLEY_BASE + cut / RIVER_VALLEY_SPREAD
        reach = int(min(np.ceil(2.2 * radius), RIVER_VALLEY_REACH))
        y0, y1 = max(y - reach, 0), min(y + reach + 1, height)
        x0, x1 = max(x - reach, 0), min(x + reach + 1, width)
        gy, gx = np.mgrid[y0:y1, x0:x1]
        depth = cut * np.exp(-((np.hypot(gy - y, gx - x) / radius) ** 2)) * weight[y0:y1, x0:x1]
        # The valley follows the shape of the land it cuts and never sinks below the bed.
        lowered = np.maximum(np.minimum(bed, ground[y0:y1, x0:x1]), ground[y0:y1, x0:x1] - depth)
        local = scope[y0:y1, x0:x1]
        field[y0:y1, x0:x1] = np.where(local, np.minimum(field[y0:y1, x0:x1], lowered), field[y0:y1, x0:x1])


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


def build_plan(root: Path = ROOT, data: dict | None = None) -> MonPlan:
    """Compute every output in memory, with validation issues and a report.

    ``data`` replaces the data file, for instance by its Stage 1 sections.
    Regions of a stage without its plan stay out of the pass.
    """
    data = read_json(root) if data is None else data
    waiting = unplanned_stages(data)
    data = active_data(data)
    if any(region_stage(region) == 2 for region in data.get("regions", {}).values()) and not data.get("stage2", {}).get(
        "existing_rivers"
    ):
        raise RuntimeError("the neighbour regions have no river snapshot: run --plan-provinces")
    scope = load_scope(root, data)
    view = geography_view(data)
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
    settle_parent_coastal_flags(definition, data, grid, window)
    issues = coastal_flag_issues(definition, data, grid, window, scope)
    crossings = crossing_squares(_packed_rgb(rgb))[window.s]
    if crossings.any():
        cy, cx = (int(value[0]) for value in np.nonzero(crossings))
        issues.append(f"{int(crossings.sum())} four-province crossings, first at {cx + window.x0}, {cy + window.y0}")
    geography = build_geography(root, view, scope, grid, definition, sources, window)
    issues.extend(geography.network.issues)
    railways = (root / RAILWAYS).read_bytes()
    repair = repair_railways(railways, province_adjacency(geography.labels), scope, managed_rail_routes())
    issues.extend(repair.issues)
    pairs = rail_text_pairs(repair.text.decode("utf-8-sig"))
    issues.extend(carve_issues(root, data, scope, grid, definition.kinds(), window, pairs))
    issues.extend(literal_issues(root, scope, geography.labels, definition.kinds()))
    # The remaining steps read the river and zone lists of every region.
    data = view

    heights = sources["heightmap"].copy()
    heights[window.s] = geography.heights
    rivers = sources["rivers"].copy()
    rivers[window.s] = geography.network.pixels
    full_water = np.isin(grid, [province for province, kind in definition.kinds().items() if kind in ("sea", "lake")])
    settle_owned_reach_markers(data, rivers, grid, full_water)
    full_mon = np.zeros(grid.shape, bool)
    full_mon[window.s] = geography.mon
    issues.extend(marker_issues(data, rivers, grid, full_water, full_mon, geography.network.routes, window))
    reach, _reach_issues = owned_reach_mask(data, window, rivers[window.s], geography.labels, geography.water)
    shape_scope = geography.relief_scope | reach
    issues.extend(course_shape_issues(rivers[window.s], shape_scope, geography.water, (window.x0, window.y0)))
    drawn_scope = np.zeros(grid.shape, bool)
    drawn_scope[window.s] = shape_scope
    issues.extend(drawing_issues(data, rivers, grid, full_water, drawn_scope))
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
    if geography.kept.any():
        kept = tree_cells_touching(geography.kept, window, grid.shape, trees_shape)
        trees = np.where(kept, sources["trees"], trees)
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
        RAILWAYS: repair.text,
    }
    landforms = state_landforms(root, scope.states, data)
    # Kept city terrains and adopted cities count in no band, as carved settlements do not.
    unbanded = scope.adopted | frozenset(
        province
        for province, terrain in geography.desired.items()
        if terrain in CITY_TERRAINS and province not in scope.urban
    )
    term_issues, terrain_report = terrain_issues(geography.desired, scope, landforms, data["terrain_bands"], "MON", unbanded)
    issues.extend(term_issues)
    region_terrain = {}
    for tag, region in data.get("regions", {}).items():
        region_issues, region_terrain[tag] = terrain_issues(
            geography.desired, scope, landforms, region["terrain_bands"], tag, unbanded
        )
        issues.extend(region_issues)
    relief = geography.mon & geography.relief_scope
    mon_heights = geography.heights[relief]
    floor, ceiling = height_limits(data, geography.states)
    below = mon_heights < (floor[relief] if isinstance(floor, np.ndarray) else floor)
    above = mon_heights > (ceiling[relief] if isinstance(ceiling, np.ndarray) else ceiling)
    if below.any() or above.any():
        issues.append(f"heights {mon_heights.min()}-{mon_heights.max()} leave the authored range")
    issues.extend(settlement_issues(data, scope, geography))
    issues.extend(ravine_issues(data, geography))
    issues.extend(state_area_issues(scope, before[window.s], geography.labels, smoothed_mask(root, data, window)))
    borders = province_border_count(grid)
    margin = border_margin_issue(borders)
    if margin:
        issues.append(margin)
    report = {
        "unplanned_stages": waiting,
        "rail_repairs": repair.repairs,
        "managed_rail_breaks": repair.managed,
        "terrain": terrain_report,
        "region_terrain": region_terrain,
        "borders": borders,
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


def state_area_issues(
    scope: Scope, before: np.ndarray, after: np.ndarray, smoothed: np.ndarray | None = None
) -> list[str]:
    """Every state keeps its pixel area, apart from the pixels its state-line smoothing moved.

    Carving and splitting move land between the provinces of one state;
    mending may move a pixel across a state line, and then as many pixels
    move back. ``smoothed`` pixels count as they stand after the pass.
    """
    if smoothed is not None and smoothed.any():
        before = np.where(smoothed, after, before)
    issues = []
    for state_id in scope.states:
        members = [province for province, owner in scope.state_of.items() if owner == state_id]
        if np.isin(before, members).sum() != np.isin(after, members).sum():
            issues.append(f"state {state_id}: its pixel area changed")
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

    Every rural province takes the one palette of its declared terrain. Built
    settlement pixels carry palette 13 and the city group of their tier,
    except on the shoreline band, where city meshes would float over the
    water. Unbuilt pixels of an urban province take the palette of the
    nearest rural pixel.
    """
    labels = geography.labels
    mon = geography.painted
    palette_of = np.zeros(int(labels.max()) + 1, np.uint8)
    for province, terrain_type in geography.desired.items():
        if terrain_type == "urban" or terrain_type in RURAL_PALETTES:
            palette_of[province] = URBAN_PALETTE if terrain_type == "urban" else RURAL_PALETTES[terrain_type]
    terrain[mon] = palette_of[labels[mon]]
    unbuilt = geography.unbuilt if geography.unbuilt is not None else np.zeros(mon.shape, bool)
    unbuilt = unbuilt & mon
    rural = mon & ~geography.cities
    if unbuilt.any() and rural.any():
        _distance, (ny, nx) = distance_transform_edt(~rural, return_indices=True)
        terrain[unbuilt] = terrain[ny[unbuilt], nx[unbuilt]]
    built = (geography.cities & ~unbuilt) | geography.fringe
    for core in geography.cores.values():
        built |= core
    built &= mon
    houses = built & ~geography.shore
    terrain[houses] = URBAN_PALETTE
    terrain[built & geography.shore] = URBAN_FALLBACK_PALETTE
    cities[mon] = CITY_BACKGROUND_INDEX
    models = geography.models if geography.models is not None else np.full(mon.shape, CITY_HOUSES_INDEX, np.uint8)
    cities[houses] = models[houses]


def all_settlements(data: dict) -> list[tuple[str, dict]]:
    """Every settlement entry with its region: MON, the MON second cities, then each region."""
    result = [("MON", entry) for entry in data["settlements"]]
    result += [("MON", entry) for entry in data.get("stage2", {}).get("settlements", [])]
    for tag, region in data.get("regions", {}).items():
        result += [(tag, entry) for entry in region.get("settlements", [])]
    return result


def settlement_province(entry: dict) -> int | None:
    """The province that carries the victory point of a settlement."""
    return entry.get("parent") if entry["kind"] == "city" else entry.get("province")


def settlement_issues(data: dict, scope: Scope, geography: Geography) -> list[str]:
    """Every settlement stands on a province of its state with the declared terrain of its kind.

    Before Stage 2 a village keeps its rural province; Stage 2 carves every
    village and town into an urban province of its own.
    """
    issues = []
    for _tag, entry in all_settlements(data):
        if entry["kind"] == "adopt":
            province = entry.get("province")
            if province is None or scope.state_of.get(int(province)) != entry["state"]:
                issues.append(f"adopted city of state {entry['state']}: province {province} lies outside the state")
            elif int(province) in scope.planned or int(province) in scope.parts.values() or int(province) in scope.remainders:
                issues.append(f"adopted city {province}: carved or split, an adopted city keeps its geometry")
            continue
        if entry["kind"] not in ("village", "town", "city"):
            continue
        province = settlement_province(entry)
        name = entry["name"]
        if province is None:
            issues.append(f"{entry['kind']} {name}: no planned province")
        elif scope.state_of.get(province) != entry["state"]:
            issues.append(f"{entry['kind']} {name}: province {province} lies outside state {entry['state']}")
        elif entry["kind"] == "village" and not scope.towns and geography.desired[province] == "urban":
            issues.append(f"village {name}: province {province} is urban")
        elif (entry["kind"] != "village" or scope.towns) and geography.desired[province] != "urban":
            issues.append(f"{entry['kind']} {name}: province {province} is not urban")
    return issues


def roundness(mask: np.ndarray) -> float:
    """Area over the area of the circle round the centroid that holds every pixel."""
    ys, xs = np.nonzero(mask)
    radius = float(np.sqrt(((ys - ys.mean()) ** 2 + (xs - xs.mean()) ** 2).max())) + 0.5
    return len(ys) / (np.pi * radius * radius)


def shore_provinces(definition: Definition, grid: np.ndarray, window: Window) -> set[int]:
    """Land provinces of the window that touch the sea."""
    labels = window_labels(grid, window)
    sea = np.isin(labels, [province for province, row in definition.rows.items() if row[4] == "sea"])
    return set(np.unique(labels[neighbours_of(sea) & ~sea]).tolist())


def settle_parent_coastal_flags(definition: Definition, data: dict, grid: np.ndarray, window: Window) -> None:
    """Set the coastal flag of every parent of a later stage from its shore, in place.

    A settlement keeps the id of its parent; where no site on the sea shore
    satisfied the carving rules, the parent lost its shore to the remainder.
    """
    entries = later_entries(data)
    if not entries:
        return
    coastal = shore_provinces(definition, grid, window)
    for entry in entries:
        parent = int(entry["parent"])
        definition.rows[parent][5] = "true" if parent in coastal else "false"


def coastal_flag_issues(definition: Definition, data: dict, grid: np.ndarray, window: Window, scope: Scope) -> list[str]:
    """The coastal flag of every province of a later stage and of its parent matches the geometry."""
    entries = later_entries(data)
    if not entries:
        return []
    coastal = shore_provinces(definition, grid, window)
    issues = []
    for entry in entries:
        for province in (int(entry["province"]), int(entry["parent"])):
            if (definition.rows[province][5] == "true") != (province in coastal):
                issues.append(f"province {province}: coastal flag {definition.rows[province][5]} differs from its shore")
    return issues


def carve_issues(
    root: Path,
    data: dict,
    scope: Scope,
    grid: np.ndarray,
    kinds: dict[int, str],
    window: Window,
    pairs: set[tuple[int, int]] | None = None,
) -> list[str]:
    """Check the carved and split geometry: sizes, shapes, neighbours, rail contacts.

    ``pairs`` are the railway segments after the rail repair of this pass;
    by default those of the map.
    """
    if not scope.planned:
        return ["no planned province geometry: run --plan-provinces"]
    issues = []
    for number in sorted({region_stage(region) for region in data.get("regions", {}).values()}):
        if not has_stage_plan(data, number):
            issues.append(f"no planned Stage {number} province geometry: run --plan-provinces")
    labels = window_labels(grid, window)
    adjacency = province_adjacency(labels)
    pairs = rail_pairs(root) if pairs is None else pairs
    part_minimum = state_parameter(data, "part_min_pixels", PART_MIN_PIXELS)
    sizes = np.bincount(labels.ravel())
    boxes = find_objects(labels)
    for parent in sorted(scope.cities):
        size = int(sizes[parent])
        if not CITY_SIZE[0] <= size <= CITY_SIZE[1]:
            issues.append(f"city {parent}: {size} pixels")
        land = {province for province in adjacency.get(parent, ()) if kinds.get(province) == "land"}
        if len(land) < CITY_MIN_NEIGHBOURS:
            issues.append(f"city {parent}: only {len(land)} land neighbours")
    for town in sorted(scope.towns):
        if not TOWN_SIZE[0] <= int(sizes[town]) <= TOWN_SIZE[1]:
            issues.append(f"town {town}: {int(sizes[town])} pixels")
    exempt = {province for record in later_layers(data) for province in record.get("irregular_parts", [])}
    repaired = frozenset(PROVINCE_REPAIR_PROVINCES) & scope.provinces
    for entry in later_entries(data):
        if int(entry["parent"]) in repaired:
            issues.append(f"province {entry['parent']}: the coastal builder repairs its pixels, it may not be carved or split")
    for province, entry in scope.planned.items():
        size = int(sizes[province])
        split = province in scope.parts.values()
        if entry["kind"] == "remainder" and not split and size < remainder_minimum(scope, entry):
            issues.append(f"remainder {province}: {size} pixels")
        if entry["kind"] == "district" and int(entry["parent"]) not in adjacency.get(province, ()):
            issues.append(f"district {province}: does not touch its city")
        if label(labels == province)[1] != 1:
            issues.append(f"planned province {province}: not one connected piece")
    for part, parent in sorted(scope.parts.items()):
        for province in (part, parent):
            mask = labels[boxes[province - 1]] == province
            if mask.sum() < part_minimum[scope.state_of[province]]:
                issues.append(f"split part {province}: {int(mask.sum())} pixels")
            if province not in exempt and roundness(mask) < PART_MIN_ROUNDNESS:
                issues.append(f"split part {province}: roundness {roundness(mask):.2f}")
    for a, b in sorted(pairs):
        if (a in scope.provinces or b in scope.provinces) and b not in adjacency.get(a, set()):
            detour = rail_detour(adjacency, scope, a, b)
            via = f": pass it through {detour[1:-1]}" if detour else ""
            issues.append(f"railway segment {a}-{b} joins provinces that do not touch{via}")
    return issues


def remainder_minimum(scope: Scope, entry: dict) -> int:
    return TOWN_REMAINDER_MIN_PIXELS if int(entry["parent"]) in scope.towns else REMAINDER_MIN_PIXELS


def planned_children(scope: Scope, province: int) -> list[int]:
    """New provinces made from ``province``, and the parts of its remainder."""
    children = [child for child, entry in scope.planned.items() if int(entry["parent"]) == province]
    for child in list(children):
        children += [part for part, parent in scope.parts.items() if parent == child]
    return sorted(set(children))


def rail_detour(adjacency: dict[int, set[int]], scope: Scope, a: int, b: int) -> list[int] | None:
    """The shortest chain from ``a`` to ``b`` through the new provinces made from either."""
    return province_path(adjacency, a, b, {a, b, *planned_children(scope, a), *planned_children(scope, b)})


def border_margin_issue(borders: int) -> str | None:
    """The engine draws at most BORDER_BUDGET province borders; a plan keeps BORDER_MARGIN of them free."""
    if BORDER_BUDGET - borders < BORDER_MARGIN:
        return f"the map draws {borders} province borders: less than {BORDER_MARGIN} of {BORDER_BUDGET} stay free"
    return None


@dataclass
class RailRepair:
    text: bytes
    repairs: list[dict]
    managed: list[dict]
    issues: list[str]


def managed_rail_routes() -> frozenset[tuple[int, ...]]:
    """The railway lines the Vorkerland theatre builder writes; this builder never rewrites them."""
    from tools.builders.build_adiscord_vorkerland_theatre import update_source

    return frozenset(tuple(chain) for line in update_source("").splitlines() if (chain := rail_chain(line)))


def repair_railways(
    original: bytes, adjacency: dict[int, set[int]], scope: Scope, managed: frozenset[tuple[int, ...]]
) -> RailRepair:
    """Pass every railway line whose segment a split or carve broke through the new provinces between its ends.

    A segment with an end in the scope whose provinces no longer touch takes
    the shortest chain through the provinces made from either end. The
    chain avoids the other provinces of the line, since a line never visits
    a province twice. A theatre-managed line keeps its route and is
    reported; its builder reroutes it. A line without a repair keeps its
    bytes, its trailing space and its line ending.
    """
    bom = b"\xef\xbb\xbf" if original.startswith(b"\xef\xbb\xbf") else b""
    text = original.decode("utf-8-sig")
    newline = "\r\n" if "\r\n" in text else "\n"
    lines = text.splitlines()
    repairs: list[dict] = []
    managed_breaks: list[dict] = []
    issues: list[str] = []
    changed = False
    for index, line in enumerate(lines):
        chain = rail_chain(line)
        if chain is None or len(chain) != int(line.split()[1]):
            continue
        repaired = chain[:1]
        detours = []
        failed = False
        for province in chain[1:]:
            previous = repaired[-1]
            if province in adjacency.get(previous, ()) or not (previous in scope.provinces or province in scope.provinces):
                repaired.append(province)
                continue
            others = set(chain) | set(repaired)
            allowed = {previous, province, *planned_children(scope, previous), *planned_children(scope, province)}
            path = province_path(adjacency, previous, province, allowed - (others - {previous, province}))
            if path is None:
                failed = True
                repaired.append(province)
                continue
            detours.append({"segment": [previous, province], "via": path[1:-1]})
            repaired.extend(path[1:])
        if not detours and not failed:
            continue
        if tuple(chain) in managed:
            managed_breaks.append({"line": chain, "detours": detours})
            continue
        if failed:
            issues.append(f"railway line {chain[0]}-{chain[-1]}: a broken segment has no detour through new provinces; split a spur")
            continue
        fields = line.split()
        lines[index] = f"{fields[0]} {len(repaired)} {' '.join(map(str, repaired))}" + (" " if line.endswith(" ") else "")
        repairs.append({"line": chain, "repaired": repaired, "detours": detours})
        changed = True
    if not changed:
        return RailRepair(original, repairs, managed_breaks, issues)
    return RailRepair(bom + (newline.join(lines) + newline).encode("utf-8"), repairs, managed_breaks, issues)


# --- province planning ---


def _evaluate_site(
    labels: np.ndarray,
    region: np.ndarray,
    site: np.ndarray,
    owner: int,
    pairs: set[tuple[int, int]],
    kinds: dict[int, str],
    site_label: int,
    remainder_min: int = REMAINDER_MIN_PIXELS,
    river: np.ndarray | None = None,
) -> tuple[list[str], list[int], int]:
    """Return hard failures, lost rail contacts and land neighbours of a carved site.

    ``owner`` is the province whose ``region`` the site is carved from; its
    leftover must stay one piece of at least ``remainder_min`` pixels. The site
    takes ``site_label``; when that is the owner itself, the site inherits
    the owner's rail contacts. Only a window around the region is examined.
    With ``river`` no river pixel may cut the site, the leftover or a donor
    apart, so the river keeps running on their borders.
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
    if leftover.sum() < remainder_min:
        failures.append(f"remainder below {remainder_min} pixels")
    if leftover.any() and label(leftover)[1] != 1:
        failures.append("remainder split")
    donors = set(np.unique(before[site[crop]]).tolist()) - {owner}
    for donor in sorted(donors):
        rest = after == donor
        if not rest.any() or label(rest)[1] != 1:
            failures.append(f"donor {donor} split")
    if river is not None:
        nothing = np.zeros(leftover.shape, bool)
        for value in (site_label, LEFTOVER_MARKER, *sorted(donors)):
            if stray_land(after == value, river[crop], nothing).any():
                failures.append(f"a river cuts {value} apart")
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
    size: int = CITY_PIXELS,
    remainder_min: int = REMAINDER_MIN_PIXELS,
    min_neighbours: int = CITY_MIN_NEIGHBOURS,
    river: np.ndarray | None = None,
    coast: np.ndarray | None = None,
) -> tuple[np.ndarray, list[int], int]:
    """Carve a compact city or town inside its parent; keep rail contacts when a site allows it.

    For a city the junction site of ``carve_junction_city`` comes first. When
    it breaks a rule or a rail contact, the sites near the hint are tried,
    then the rest of the parent while a rail contact is still lost; the
    fewest losses win. With ``coast`` the site must touch it: the settlement
    keeps the id, and so the coastal flag, of its parent.
    """
    if size == CITY_PIXELS:
        city = carve_junction_city(labels, donors, region, hint, shore=shore)
        failures, lost, land = _evaluate_site(labels, region, city, parent, pairs, kinds, parent, remainder_min, river)
        off_coast = coast is not None and not (city & coast).any()
        if city.sum() == size and not failures and not lost and land >= min_neighbours and not off_coast:
            return city, lost, land
    ys, xs = np.nonzero(region & donors)
    distance = np.hypot(ys - hint[0], xs - hint[1])
    order = np.lexsort((xs, ys, distance))
    best = None
    for index in order:
        if distance[index] > CITY_SITE_DISTANCE and best is not None and not best[4] and not best[2]:
            break
        city = grow_city(labels, donors, region, (int(ys[index]), int(xs[index])), size)
        if city.sum() != size:
            continue
        failures, lost, land = _evaluate_site(labels, region, city, parent, pairs, kinds, parent, remainder_min, river)
        if land < min_neighbours:
            failures = [*failures, f"only {land} land neighbours"]
        if coast is not None and not (city & coast).any():
            failures = [*failures, "off the coast"]
        score = (len(failures), len(lost), -min(land, CITY_MIN_NEIGHBOURS + 1), float(distance[index]))
        if best is None or score < best[0]:
            best = (score, city, lost, land, failures)
        if not failures and not lost and land > CITY_MIN_NEIGHBOURS:
            break
    if best is None or best[4]:
        raise RuntimeError(f"city {parent}: no site satisfies the carving rules {best[4] if best else ''}")
    return best[1], best[2], best[3]


def plan_provinces(root: Path = ROOT, output_root: Path | None = None) -> dict:
    """Carve the MON cities, the capital district and the remainders; pick the villages.

    The result is stored as data under ``output_root`` (the repository by
    default), so the map pass only stamps it. A stored plan is never
    replanned from a map that already carries it.
    """
    data = read_json(root)
    planned = data["planned"]
    if planned["provinces"] or planned["first_id"] or planned["cities"] or planned["villages"]:
        raise RuntimeError("the MON province plan exists: restore the pre-apply map and empty planned first")
    scope = load_scope(root, stage1_data(data))
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
    scope = load_scope(root, stage1_data(data))
    stamped = grid.copy()
    stamped[window.s] = labels
    pick_villages(root, data, scope, stamped, definition, window, pairs, original)
    report["villages"] = data["planned"]["villages"]
    write_plan_files(root if output_root is None else output_root, data, image)
    return report


def write_plan_files(output_root: Path, data: dict, sheet: np.ndarray) -> None:
    """Write the data file and the geometry raster under ``output_root``."""
    (output_root / GEOMETRY_PATH).parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(sheet, "RGBA").save(output_root / GEOMETRY_PATH, optimize=True)
    (output_root / DATA_PATH).write_text(dump_data(data), encoding="utf-8", newline="\n")


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


# --- Stage 2 province planning ---


def _farthest_seeds(region: np.ndarray, parts: int, angle: float) -> list[tuple[int, int]]:
    """Farthest-point seeds, starting from the extreme pixel of the region towards ``angle``."""
    ys, xs = np.nonzero(region)
    cy, cx = ys.mean(), xs.mean()
    first = int(np.argmax((ys - cy) * sin(angle) + (xs - cx) * cos(angle)))
    seeds = [(int(ys[first]), int(xs[first]))]
    while len(seeds) < parts:
        spread = np.min([(ys - sy) ** 2 + (xs - sx) ** 2 for sy, sx in seeds], axis=0)
        index = int(np.argmax(spread))
        seeds.append((int(ys[index]), int(xs[index])))
    return seeds


def _lloyd_partition(region: np.ndarray, seeds: list[tuple[int, int]]) -> np.ndarray:
    """Geodesic k-means: assign pixels to the nearest seed, move each seed to its part's centre."""
    owner = _geodesic_partition(region, seeds)
    for _iteration in range(PARTITION_ITERATIONS):
        moved = []
        for index in range(len(seeds)):
            part = owner == index
            if not part.any():
                return owner
            ys, xs = np.nonzero(part)
            moved.append(_nearest_member(part, ys.mean(), xs.mean()))
        if moved == seeds:
            break
        seeds = moved
        owner = _geodesic_partition(region, seeds)
    return owner


def _line_partitions(region: np.ndarray) -> list[np.ndarray]:
    """Two-part splits by straight cuts at several angles and area shares."""
    ys, xs = np.nonzero(region)
    cy, cx = ys.mean(), xs.mean()
    result = []
    for angle in np.linspace(0.0, np.pi, 2 * PARTITION_ANGLES, endpoint=False):
        projection = (ys - cy) * np.sin(angle) + (xs - cx) * np.cos(angle)
        ordered = np.sort(projection)
        for share in np.linspace(0.38, 0.62, 7):
            owner = np.full(region.shape, -1, np.int32)
            owner[ys, xs] = (projection > ordered[int(share * len(ordered))]).astype(np.int32)
            result.append(owner)
    return result


def _smooth_partition(owner: np.ndarray, region: np.ndarray, parts: int, sigma: float) -> np.ndarray:
    """Round the borders between parts by a Gaussian majority vote; a pixel that would detach stays."""
    result = owner.copy()
    for _pass in range(SMOOTH_PASSES):
        scores = np.stack(
            [gaussian_filter((result == index).astype(float), sigma) + 1e-6 * (result == index) for index in range(parts)]
        )
        vote = np.where(region, np.argmax(scores, axis=0), -1).astype(np.int32)
        for index in range(parts):
            pieces, count = label(vote == index)
            if count > 1:
                sizes = np.bincount(pieces.ravel())
                sizes[0] = 0
                stray = (pieces > 0) & (pieces != int(np.argmax(sizes)))
                vote[stray] = result[stray]
        if np.array_equal(vote, result):
            break
        result = vote
    return result


def partition_rank(
    owner: np.ndarray,
    parts: int,
    river: np.ndarray | None = None,
    slivers: np.ndarray | None = None,
    min_pixels: int = PART_MIN_PIXELS,
) -> tuple[bool, float]:
    """Whether every part is whole, at least ``min_pixels`` and uncut by ``river``, and the lowest part roundness.

    A sliver the river already cut off the parent may stay cut off.
    """
    masks = [owner == index for index in range(parts)]
    if any(not mask.any() for mask in masks):
        return False, -1.0
    whole = all(label(mask)[1] == 1 for mask in masks) and min(int(mask.sum()) for mask in masks) >= min_pixels
    if whole and river is not None:
        tolerated = np.zeros(owner.shape, bool) if slivers is None else slivers
        whole = not any(stray_land(mask, river, tolerated).any() for mask in masks)
    return whole, min(roundness(mask) for mask in masks)


def _fill_partition(owner: np.ndarray, region: np.ndarray) -> np.ndarray:
    """Give every unassigned region pixel the part of its nearest assigned pixel along the region."""
    result = owner.copy()
    queue = deque(zip(*np.nonzero(result >= 0)))
    while queue:
        y, x = queue.popleft()
        for ny, nx in ((y + 1, x), (y - 1, x), (y, x + 1), (y, x - 1)):
            if region[ny, nx] and result[ny, nx] < 0:
                result[ny, nx] = result[y, x]
                queue.append((ny, nx))
    return result


def _kmeans_candidates(region: np.ndarray, parts: int) -> list[np.ndarray]:
    candidates = []
    for angle in np.linspace(0.0, 2.0 * np.pi, PARTITION_ANGLES, endpoint=False):
        owner = _lloyd_partition(region, _farthest_seeds(region, parts, float(angle)))
        candidates += [_smooth_partition(owner, region, parts, sigma) for sigma in PARTITION_SIGMAS]
    return candidates


def partition_province(
    region: np.ndarray, parts: int, contacts=None, river: np.ndarray | None = None, min_pixels: int = PART_MIN_PIXELS
) -> tuple[np.ndarray, bool, float]:
    """Split one province into compact connected parts; the roundest valid split wins.

    Geodesic k-means runs from several seedings and is smoothed; a split in
    two also tries straight cuts. Where a river runs through the province,
    splits of the land beside it are tried too, the river pixels joining the
    part beside them, so the river becomes a border between parts. Among
    splits whose parts are all round enough, ``contacts`` (a split to a
    count) prefers the one whose best part keeps most railway contacts. No
    part may be cut apart by a ``river`` pixel. Returns the part of every
    pixel (-1 outside), whether the parts are whole and hold ``min_pixels``,
    and the lowest part roundness.
    """
    candidates = _kmeans_candidates(region, parts)
    if parts == 2:
        candidates += [_smooth_partition(owner, region, parts, PARTITION_SIGMAS[0]) for owner in _line_partitions(region)]
    slivers = None
    if river is not None and (river & region).any():
        slivers = stray_land(region, river, np.zeros(region.shape, bool))
        land = region & ~river & ~slivers
        if label(land)[1] == 1 and land.sum() >= parts * min_pixels:
            candidates += [_fill_partition(owner, region) for owner in _kmeans_candidates(land, parts)]
    ranked = []
    for index, owner in enumerate(candidates):
        whole, lowest = partition_rank(owner, parts, river, slivers, min_pixels)
        kept = contacts(owner) if contacts is not None and whole and lowest >= PART_MIN_ROUNDNESS else 0
        ranked.append(((whole, lowest >= PART_MIN_ROUNDNESS, kept, lowest, -index), index, whole, lowest))
    _key, index, whole, lowest = max(ranked)
    return candidates[index], whole, lowest


def mend_river_cuts(labels: np.ndarray, river: np.ndarray, ids: list[int]) -> None:
    """Give a piece that a river cuts off one part to the sibling part it touches across land, in place."""
    nothing = np.zeros(labels.shape, bool)
    siblings = np.isin(labels, ids)
    for child in ids:
        stray = stray_land(labels == child, river, nothing)
        pieces, count = label(stray)
        for piece in range(1, count + 1):
            fragment = pieces == piece
            ring = neighbours_of(fragment) & ~fragment & ~river & siblings & (labels != child)
            if ring.any():
                labels[fragment] = int(np.bincount(labels[ring]).argmax())


def interior_point(mask: np.ndarray) -> tuple[int, int]:
    """The deepest pixel of a mask (y, x); ties go to the first in scan order."""
    depth = distance_transform_edt(np.pad(mask, 1))[1:-1, 1:-1]
    index = int(np.argmax(depth))
    return divmod(index, mask.shape[1])


def province_points(root: Path, grid: np.ndarray, provinces: frozenset[int]) -> dict[int, dict[str, tuple[int, int]]]:
    """Map pixels (x, row) of the unit anchors and building models of each province.

    ``anchor`` is the standing army (slot 0) and ``victory_point`` the VP
    marker; a building model of LITERAL_BUILDING_TYPES belongs to the
    province under it, as the engine reads it.
    """
    height, width = grid.shape
    result: dict[int, dict[str, tuple[int, int]]] = defaultdict(dict)
    rows, _newline = read_unitstacks((root / UNITSTACKS).read_bytes())
    for row in rows:
        if len(row) > 4 and row[0].isdigit() and int(row[0]) in provinces and row[1] in ("0", str(VICTORY_POINT_SLOT)):
            key = "anchor" if row[1] == "0" else "victory_point"
            result[int(row[0])][key] = (round(float(row[2])), height - 1 - round(float(row[4])))
    for line in (root / BUILDINGS).read_text(encoding="utf-8-sig").splitlines():
        fields = line.split(";")
        if len(fields) < 5 or fields[1] not in LITERAL_BUILDING_TYPES:
            continue
        x = round(float(fields[2]))
        y = height - 1 - round(float(fields[4]))
        if 0 <= y < height and 0 <= x < width and int(grid[y, x]) in provinces:
            result[int(grid[y, x])].setdefault(fields[1], (x, y))
    return dict(result)


def unit_locations(root: Path) -> frozenset[int]:
    """Provinces where an order of battle places a division, a fleet or its base."""
    pattern = re.compile(r"\b(?:location|naval_base)\s*=\s*(\d+)")
    result: set[int] = set()
    for path in sorted((root / UNITS).glob("*.txt")):
        result.update(int(value) for value in pattern.findall(path.read_text(encoding="utf-8-sig", errors="replace")))
    return frozenset(result)


def supply_hubs(root: Path) -> frozenset[int]:
    """Provinces of the supply hubs on the map."""
    result = set()
    for line in (root / SUPPLY_NODES).read_text(encoding="utf-8-sig").splitlines():
        fields = line.split()
        if len(fields) == 2 and all(value.isdigit() for value in fields):
            result.add(int(fields[1]))
    return frozenset(result)


def state_history(root: Path, state_id: int) -> str:
    return next((root / "history/states").glob(f"{state_id}-*.txt")).read_text(encoding="utf-8-sig")


def state_naval_bases(root: Path, states: list[int]) -> frozenset[int]:
    """Provinces holding a naval base in the history files of ``states``."""
    pattern = re.compile(r"\b(\d+)\s*=\s*\{[^{}]*\bnaval_base\b")
    return frozenset(int(value) for state_id in states for value in pattern.findall(state_history(root, state_id)))


def state_victory_points(root: Path, states: list[int]) -> dict[int, int]:
    """The victory points of the history files of ``states`` by province."""
    pattern = re.compile(r"victory_points\s*=\s*\{\s*(\d+)\s+(\d+)")
    return {
        int(province): int(value)
        for state_id in states
        for province, value in pattern.findall(state_history(root, state_id))
    }


def script_literal_provinces(root: Path, states: list[int]) -> tuple[frozenset[int], frozenset[int]]:
    """Provinces that script names by id, and those of them with a naval base.

    SCRIPT_LITERAL_PROVINCES joins the order-of-battle locations, the
    starting-navy ports, the supply hubs and the naval bases of the history
    files of ``states``.
    """
    ports = frozenset(navy.port for navy in STARTING_NAVIES.values())
    naval = NAVAL_LITERAL_PROVINCES | ports | state_naval_bases(root, states)
    return SCRIPT_LITERAL_PROVINCES | unit_locations(root) | supply_hubs(root) | naval, naval


def literal_issues(root: Path, scope: Scope, labels: np.ndarray, kinds: dict[int, str]) -> list[str]:
    """Every literal province of the scope keeps its id on land; a naval base keeps its sea contact."""
    literals, naval = script_literal_provinces(root, scope.states)
    present = set(np.unique(labels).tolist())
    sea = np.isin(labels, [province for province, kind in kinds.items() if kind == "sea"])
    issues = []
    for province in sorted(literals & scope.provinces):
        if province not in present:
            issues.append(f"literal province {province}: its id left the map")
        elif kinds.get(province) != "land":
            issues.append(f"literal province {province}: not land")
        elif province in naval and not (neighbours_of(sea) & (labels == province)).any():
            issues.append(f"literal province {province}: its naval base lost the sea")
    return issues


# Pixel moves that resolve a four-province corner: (dy, dx) takes the label of (ny, nx).
CORNER_MOVES = ((0, 0, 0, 1), (0, 1, 0, 0), (1, 0, 1, 1), (1, 1, 1, 0), (0, 0, 1, 0), (1, 0, 0, 0), (0, 1, 1, 1), (1, 1, 0, 1))


def clear_corners(labels: np.ndarray, editable: np.ndarray, state_of: dict[int, int]) -> None:
    """Remove every four-province corner that touches an editable pixel, in place.

    HOI4 rejects a point where four provinces meet. As in
    ``remove_four_province_corners`` one pixel takes the label of its
    neighbour, here only between provinces of one state, so state areas
    stay. A corner elsewhere in the window belongs to another builder.
    """
    while True:
        a = labels[:-1, :-1]
        b = labels[:-1, 1:]
        c = labels[1:, :-1]
        d = labels[1:, 1:]
        corners = (a != b) & (a != c) & (a != d) & (b != c) & (b != d) & (c != d)
        touching = editable[:-1, :-1] | editable[:-1, 1:] | editable[1:, :-1] | editable[1:, 1:]
        found = np.argwhere(corners & touching)
        if not len(found):
            return
        for y, x in found:
            for dy, dx, ny, nx in CORNER_MOVES:
                source = int(labels[y + dy, x + dx])
                target = int(labels[y + ny, x + nx])
                if (
                    editable[y + dy, x + dx]
                    and editable[y + ny, x + nx]
                    and state_of.get(source) is not None
                    and state_of.get(source) == state_of.get(target)
                ):
                    labels[y + dy, x + dx] = target
                    break
            else:
                raise RuntimeError(f"four-province corner at window {(int(x), int(y))} has no movable pixel")


class StagePlanner:
    """Carve the settlements of one stage and split the large rural provinces of its regions.

    It works on the window of the map the earlier stages left; every earlier
    stage must be on the map. Settlements come first, so no split cuts a
    town; then every large rural province is split. New ids follow in that
    order from ``first_id``. A carved settlement keeps the id of its parent;
    the rest of the parent becomes a remainder. An adopted city keeps its
    province as it is.
    """

    def __init__(self, root: Path, data: dict, stage: int = 2) -> None:
        self.root = root
        self.full = data
        self.stage = stage
        self.data = stage_data(data, stage)
        if not any(region_stage(region) == stage for region in data.get("regions", {}).values()):
            raise RuntimeError(f"Stage {stage} has no region to plan")
        self.scope = load_scope(root, self.data)
        definition = read_definition(root)
        for number, record in sorted(stage_layers(data).items()):
            if number < stage and record.get("provinces") and int(record["first_id"]) not in definition.rows:
                raise RuntimeError(f"apply the Stage {number} plan before planning Stage {stage}")
        self.kinds = definition.kinds()
        self.used = set(definition.colours().values())
        self.first_id = max(definition.rows) + 1
        with Image.open(root / PROVINCES) as source:
            self.grid = province_grid(np.asarray(source.convert("RGB")), definition.colours())
        self.window = mon_window(self.grid, self.scope.provinces)
        self.labels = window_labels(self.grid, self.window).copy()
        self.original = self.labels.copy()
        scope_mask = np.isin(self.labels, list(self.scope.provinces))
        self.water = np.isin(self.labels, [province for province, kind in self.kinds.items() if kind in ("sea", "lake")])
        self.sea = np.isin(self.labels, [province for province, kind in self.kinds.items() if kind == "sea"])
        self.shore = neighbours_of(self.water) & ~self.water
        with Image.open(root / RIVERS) as source:
            self.river_pixels = np.asarray(source)[self.window.s].copy()
        if stage > 2:
            self.river_pixels = self.restore_earlier_rings(self.river_pixels)
        with Image.open(root / HEIGHTMAP) as source:
            heights = np.asarray(source)[self.window.s]
        river = river_masks(self.river_pixels, self.water)
        clearance = np.zeros(self.labels.shape, bool)
        for canyon in canyon_layers(root, self.data, self.labels, scope_mask, self.water, self.scope.planned):
            clearance |= scope_mask & (canyon.distance < CANYON_SETTLEMENT_CLEARANCE)
        states = lookup_raster(self.labels, self.scope.state_of)
        self.no_sites = clearance | frozen_pixels(geography_view(self.data), self.labels, scope_mask, self.window, heights, states)
        self.river = river
        self.locked = river | neighbours_of(river) | self.water | clearance
        self.banks = neighbours_of(river)
        self.pairs = rail_pairs(root)
        self.on_rail = {province for pair in self.pairs for province in pair}
        self.state_of = dict(self.scope.state_of)
        # A city terrain on the map stays: such a province is neither carved, split nor a donor.
        self.city_terrain = {
            province: definition.rows[province][6]
            for province in self.scope.provinces
            if province in definition.rows and definition.rows[province][6] in CITY_TERRAINS
        }
        self.settled = set(self.scope.urban) | set(self.city_terrain) | set(self.scope.adopted)
        self.split_threshold = state_parameter(self.data, "split_threshold", SPLIT_THRESHOLD)
        self.split_part = state_parameter(self.data, "split_part", SPLIT_PART_PIXELS)
        self.part_minimum = state_parameter(self.data, "part_min_pixels", PART_MIN_PIXELS)
        regions = list(self.data.get("regions", {}).values())
        self.no_split_states = frozenset(int(state_id) for region in regions for state_id in region.get("no_split_states", []))
        # Landmark provinces keep their geometry: no settlement, split or donor touches them.
        locked_ids = {int(province) for region in regions for key in ("never_parent", "keep_provinces") for province in region.get(key, [])}
        # The coastal builder repairs single pixels of these provinces by id; they keep their geometry.
        self.foreign = (frozenset(PROVINCE_REPAIR_PROVINCES) | frozenset(locked_ids)) & self.scope.provinces
        self.adopted: list[int] = []
        self.entries: list[dict] = []
        self.cities: list[int] = []
        self.towns: list[int] = []
        self.irregular: list[int] = []
        self.failed_splits: list[dict] = []
        self.splits: dict[int, tuple[list[int], float]] = {}
        self.coastal_kept: list[int] = []
        self.points = province_points(root, self.grid, self.scope.provinces)
        self.literals, self.naval = script_literal_provinces(root, self.scope.states)
        self.hubs = supply_hubs(root)
        self.victory_points = state_victory_points(root, self.scope.states)
        self.report_lost: list[dict] = []

    def restore_earlier_rings(self, rivers: np.ndarray) -> np.ndarray:
        """River pixels as they stood before this builder drew any course.

        A course of an earlier stage may turn on the foreign land beside its
        scope; the ring snapshot of that stage holds the pixels as they were.
        The snapshots of this stage are taken from the restored pixels, so a
        turn the earlier pass drew is never recorded as an existing river.
        """
        earlier = active_data(self.full)
        view = geography_view(earlier)
        if not view.get("ring_rivers"):
            return rivers
        provinces = load_scope(self.root, earlier).provinces
        owned = np.isin(self.labels, sorted(provinces))
        ring = corner_takers(self.labels, owned, self.water, self.window)
        restored = rivers.copy()
        restored[ring] = reference_rivers(view, self.window, rivers.shape, "ring_rivers")[ring]
        return restored

    # Province bookkeeping

    def new_id(self) -> int:
        return self.first_id + len(self.entries)

    def add_entry(self, province: int, parent: int, state_id: int, kind: str) -> None:
        self.entries.append({"province": province, "parent": parent, "state": state_id, "kind": kind})
        self.state_of[province] = state_id

    def members(self, state_id: int) -> list[int]:
        return sorted(province for province, owner in self.state_of.items() if owner == state_id)

    def mask(self, province: int) -> np.ndarray:
        return self.labels == province

    def donors(self, state_id: int, parent: int | None = None) -> np.ndarray:
        """Pixels a settlement of the state may take: no settlement, no Stage 1 province, no lock.

        A literal province gives pixels only to a settlement carved in itself,
        so its anchors, building models and sea contact stay with its id.
        """
        literals = (self.literals & frozenset(self.members(state_id))) - {parent}
        fixed = sorted(self.settled | set(self.scope.planned) | self.foreign | literals)
        members = np.isin(self.labels, self.members(state_id))
        return members & ~np.isin(self.labels, fixed) & ~self.locked & ~self.no_sites

    def centre(self, province: int) -> tuple[int, int]:
        """The deepest pixel of a province, in window coordinates (y, x)."""
        ys, xs = np.nonzero(self.mask(province))
        y0, x0 = int(ys.min()), int(xs.min())
        y, x = interior_point(self.labels[y0:ys.max() + 1, x0:xs.max() + 1] == province)
        return y + y0, x + x0

    def touches_sea(self, province: int) -> bool:
        return bool((neighbours_of(self.sea) & self.mask(province)).any())

    def province_size(self, province: int) -> int:
        return int(self.mask(province).sum())

    # Settlements

    def carve(self, state_id: int, parent: int, size: int) -> None:
        """Carve a city or town of ``size`` pixels round the centre of ``parent``."""
        if self.state_of.get(parent) != state_id:
            raise RuntimeError(f"settlement parent {parent} lies outside state {state_id}")
        region = self.mask(parent)
        donors = self.donors(state_id, parent)
        shore = self.shore if (region & self.shore).any() else None
        city = size == CITY_PIXELS
        rules = (
            REMAINDER_MIN_PIXELS if city else TOWN_REMAINDER_MIN_PIXELS,
            CITY_MIN_NEIGHBOURS if city else TOWN_MIN_NEIGHBOURS,
            self.river,
        )
        hint = self.centre(parent)
        # A coastal parent keeps its coastal flag where a site on the sea shore
        # satisfies the rules; otherwise the map pass sets the flag from the geometry.
        coast = neighbours_of(self.sea) & ~self.sea
        attempts = [(donors, hint, None)]
        if (region & coast).any():
            ys, xs = np.nonzero(region & coast)
            nearest = int(np.argmin((ys - hint[0]) ** 2 + (xs - hint[1]) ** 2))
            attempts.insert(0, (donors, (int(ys[nearest]), int(xs[nearest])), coast))
        # Where every site that takes from a neighbour splits it, the parent gives all the pixels.
        attempts.append((donors & region, hint, None))
        failures = []
        for allowed, start, required in attempts:
            try:
                site, lost, land = carve_site(
                    self.labels, allowed, region, start, parent, self.pairs, self.kinds, shore, size, *rules, required
                )
                break
            except RuntimeError as error:
                failures.append(str(error))
        else:
            raise RuntimeError(failures[-1])
        remainder = self.new_id()
        self.labels[region & ~site] = remainder
        self.labels[site] = parent
        self.add_entry(remainder, parent, state_id, "remainder")
        self.settled.add(parent)
        if lost:
            self.report_lost.append({"settlement": parent, "lost_rail": lost})

    def carve_district(self, state_id: int, parent: int) -> None:
        remainder = next(
            int(entry["province"]) for entry in self.entries if entry["parent"] == parent and entry["kind"] == "remainder"
        )
        donors = self.donors(state_id) & (self.labels != parent)
        hint = self.centre(parent)
        district = grow_district(self.labels, donors, self.mask(remainder), hint, parent, self.pairs, self.kinds)
        district_id = self.new_id()
        self.labels[district] = district_id
        self.add_entry(district_id, parent, state_id, "district")
        self.settled.add(district_id)

    def site_options(self, state_id: int, minimum: int) -> list[tuple[int, tuple[int, int]]]:
        """Rural provinces of a state that may hold a new settlement, with their centres.

        A chosen site keeps the id of its parent on the settlement, so a
        literal province or one with a victory point is never chosen; the
        data names such a parent explicitly where it becomes a city.
        """
        options = []
        for province in self.members(state_id):
            if province in self.settled or province in self.foreign or self.kinds.get(province, "land") != "land":
                continue
            if province in self.literals or province in self.victory_points:
                continue
            if province in self.scope.planned or province in {int(entry["province"]) for entry in self.entries}:
                continue
            if self.province_size(province) < minimum or self.touches_sea(province):
                continue
            centre = self.centre(province)
            if self.no_sites[centre]:
                continue
            options.append((province, centre))
        return options

    def settlement_centres(self, state_id: int) -> list[tuple[int, int]]:
        return [self.centre(province) for province in sorted(self.settled) if self.state_of.get(province) == state_id]

    def city_choices(self, state_id: int) -> list[int]:
        """Railway provinces near the middle of the state first, then the most central ones."""
        ys, xs = np.nonzero(np.isin(self.labels, self.members(state_id)))
        cy, cx = ys.mean(), xs.mean()
        options = self.site_options(state_id, SETTLEMENT_MIN_PARENT)

        def rank(option: tuple[int, tuple[int, int]]) -> tuple:
            province, (y, x) = option
            return (province not in self.on_rail, np.hypot(y - cy, x - cx), province)

        return [province for province, _centre in sorted(options, key=rank)]

    def spread_choices(self, state_id: int, minimum: int, distance: float, target: float) -> list[int]:
        """Provinces away from the settlements of their state; river banks and railways first.

        A small state may hold no province that far away; the distance then
        shrinks in steps.
        """
        others = self.settlement_centres(state_id)
        options = self.site_options(state_id, minimum)
        result: list[int] = []
        for share in SPREAD_RELAXATION:
            ranked = []
            for province, (y, x) in options:
                gap = min((np.hypot(y - oy, x - ox) for oy, ox in others), default=target)
                if gap < distance * share or province in result:
                    continue
                bank = bool((self.banks & self.mask(province)).any())
                ranked.append(((not (bank or province in self.on_rail), abs(gap - target), province), province))
            result += [province for _score, province in sorted(ranked)]
        return result

    def plan_settlements(self) -> None:
        """Carve MON towns, MON second cities and the cities, districts and towns of each region."""
        for entry in self.data["settlements"]:
            if entry["kind"] == "village":
                self.carve(int(entry["state"]), int(entry["province"]), TOWN_PIXELS)
                self.towns.append(int(entry["province"]))
        for entry in self.data["stage2"].get("settlements", []):
            self.plan_entry(entry)
        for region in self.data["regions"].values():
            for entry in region["settlements"]:
                self.plan_entry(entry)

    def carve_first(self, state_id: int, choices: list[int], size: int) -> int:
        """Carve in the first chosen province whose sites satisfy the rules and keep every railway contact.

        A carve that cuts a railway contact is undone while a later choice
        may keep them all; when none does, the first carve that satisfies
        the rules stays.
        """
        failures = []
        fallback = None
        for province in choices:
            labels = self.labels.copy()
            entries = len(self.entries)
            losses = len(self.report_lost)
            try:
                self.carve(state_id, province, size)
            except RuntimeError as error:
                failures.append(str(error))
                continue
            if len(self.report_lost) == losses:
                return province
            fallback = province if fallback is None else fallback
            self.labels[:] = labels
            for entry in self.entries[entries:]:
                del self.state_of[entry["province"]]
            del self.entries[entries:]
            del self.report_lost[losses:]
            self.settled.discard(province)
        if fallback is not None:
            self.carve(state_id, fallback, size)
            return fallback
        raise RuntimeError(f"state {state_id}: no province holds a settlement: {failures[:3]}")

    def plan_entry(self, entry: dict) -> None:
        """Carve one authored settlement; a missing province is chosen and recorded in the entry."""
        state_id = int(entry["state"])
        if entry["kind"] in ("city", "district") and state_id in self.no_split_states:
            raise RuntimeError(f"state {state_id}: only towns are carved in a state that is never split; adopt its city")
        if entry["kind"] == "city":
            if entry.get("parent") is None:
                main = any(
                    self.state_of.get(city) == state_id for city in [*self.cities, *self.scope.cities, *self.adopted]
                )
                if main:
                    choices = self.spread_choices(state_id, SETTLEMENT_MIN_PARENT, SECOND_CITY_DISTANCE, 35.0)
                else:
                    choices = self.city_choices(state_id)
                entry["parent"] = self.carve_first(state_id, choices, CITY_PIXELS)
            else:
                self.carve(state_id, int(entry["parent"]), CITY_PIXELS)
            self.cities.append(int(entry["parent"]))
        elif entry["kind"] == "district":
            if entry.get("parent") is None:
                entry["parent"] = next(city for city in self.cities if self.state_of[city] == state_id)
            self.carve_district(state_id, int(entry["parent"]))
        elif entry["kind"] == "town":
            if entry.get("province") is None:
                choices = self.spread_choices(state_id, TOWN_MIN_PARENT, TOWN_CITY_DISTANCE, 25.0)
                entry["province"] = self.carve_first(state_id, choices, TOWN_PIXELS)
            else:
                self.carve(state_id, int(entry["province"]), TOWN_PIXELS)
            self.towns.append(int(entry["province"]))
        elif entry["kind"] == "adopt":
            if entry.get("province") is None:
                entry["province"] = self.adoption_choice(state_id)
            province = int(entry["province"])
            if self.state_of.get(province) != state_id:
                raise RuntimeError(f"adopted city {province} lies outside state {state_id}")
            self.settled.add(province)
            self.adopted.append(province)
        else:
            raise RuntimeError(f"settlement {entry}: unknown kind")

    def adoption_choice(self, state_id: int) -> int:
        """The city-terrain province of a state nearest its middle, for an adoption without a province."""
        options = [province for province in self.city_terrain if self.state_of.get(province) == state_id]
        if not options:
            raise RuntimeError(f"state {state_id}: no city province to adopt")
        ys, xs = np.nonzero(np.isin(self.labels, self.members(state_id)))
        cy, cx = ys.mean(), xs.mean()

        def distance(province: int) -> tuple[float, int]:
            y, x = self.centre(province)
            return float(np.hypot(y - cy, x - cx)), province

        return min(options, key=distance)

    # Splitting

    def split_candidates(self) -> list[int]:
        result = []
        for states in region_states(self.data).values():
            for state_id in states:
                if state_id in self.no_split_states:
                    continue
                for province in self.members(state_id):
                    if province in self.settled or province in self.foreign:
                        continue
                    if self.kinds.get(province, "land") != "land":
                        continue
                    if self.province_size(province) <= self.split_threshold[state_id]:
                        continue
                    if self.touches_sea(province):
                        self.coastal_kept.append(province)
                        continue
                    result.append(province)
        return result

    def holds(self, part: np.ndarray, box: tuple[slice, slice], point: tuple[int, int] | None) -> bool:
        """Whether a map pixel (x, row) lies in ``part``, a crop of the window at ``box``."""
        if point is None:
            return False
        y = point[1] - self.window.y0 - box[0].start
        x = point[0] - self.window.x0 - box[1].start
        return 0 <= y < part.shape[0] and 0 <= x < part.shape[1] and bool(part[y, x])

    def keep_rank(self, province: int, part: np.ndarray, box: tuple[slice, slice], contacts: int) -> tuple:
        """The claim of one part of a split province on the id of its parent; the highest claim keeps it.

        A literal province keeps its id where it touches the sea, for a naval
        base, and where its unit anchors and building models stand. Then
        follow the part with the VP marker, the part with the supply hub,
        the part with most railway contacts (``contacts``), the part with the
        standing anchor and the largest part.
        """
        points = self.points.get(province, {})
        literal: tuple[bool, int] = (False, 0)
        if province in self.literals:
            sea = province in self.naval and bool((neighbours_of(self.sea[box]) & part).any())
            literal = (sea, sum(self.holds(part, box, point) for point in points.values()))
        victory = province in self.victory_points and self.holds(part, box, points.get("victory_point"))
        hub = province in self.hubs and self.holds(part, box, points.get("supply_node"))
        anchor = self.holds(part, box, points.get("anchor"))
        return (literal, victory, hub, contacts, anchor, int(part.sum()))

    def split(self, province: int) -> None:
        """Split one province; the part that ranks first in ``keep_rank`` keeps the id.

        Among the round splits the planner prefers the one whose kept part
        keeps most railway contacts, so the claims of ``keep_rank`` above the
        railway cut as few chains as they can.
        """
        ys, xs = np.nonzero(self.mask(province))
        box = np.s_[max(0, ys.min() - 1):ys.max() + 2, max(0, xs.min() - 1):xs.max() + 2]
        crop = self.labels[box]
        region = crop == province
        state_id = self.state_of[province]
        parts = ceil(int(region.sum()) / self.split_part[state_id])
        minimum = self.part_minimum[state_id]
        rail = rail_neighbours(self.pairs, province)
        rail_pixels = np.isin(crop, sorted(rail))

        def kept_part(split: np.ndarray) -> tuple[int, int]:
            """The index of the part that keeps the id and its railway contacts."""
            ranked = []
            for index in range(int(split.max()) + 1):
                part = split == index
                if not part.any():
                    continue
                contacts = len(set(np.unique(crop[neighbours_of(part) & rail_pixels]).tolist()))
                ranked.append(((*self.keep_rank(province, part, box, contacts), -index), index, contacts))
            _rank, index, contacts = max(ranked)
            return index, contacts

        prefer = (lambda split: kept_part(split)[1]) if rail else None
        owner, whole, lowest = partition_province(region, parts, prefer, self.river[box], minimum)
        if (not whole or lowest < PART_MIN_ROUNDNESS) and parts > 2:
            # One part fewer leaves larger parts that can round off an arm of the parent.
            fewer, fewer_whole, fewer_lowest = partition_province(region, parts - 1, prefer, self.river[box], minimum)
            if fewer_whole and fewer_lowest >= PART_MIN_ROUNDNESS:
                owner = fewer
                parts -= 1
        kept, _contacts = kept_part(owner)
        others = [index for index in range(parts) if index != kept]
        others.sort(key=lambda index: tuple(np.mean(np.nonzero(owner == index), axis=1)))
        new = {}
        for index in others:
            new[index] = self.new_id()
            self.add_entry(new[index], province, self.state_of[province], "part")
        for index, child in new.items():
            crop[owner == index] = child
        self.splits[province] = ([province, *new.values()], roundness(region))

    def judge_splits(self) -> None:
        """Sort out the splits whose parts stay below the minimum roundness, on the final geometry.

        Such parts are accepted only from an irregular parent and within
        IRREGULAR_LOSS of its roundness, or within CORNER_LOSS of the
        minimum; they are listed for review.
        """
        for province, (ids, own_roundness) in sorted(self.splits.items()):
            ys, xs = np.nonzero(np.isin(self.labels, ids))
            box = np.s_[max(0, ys.min() - 1):ys.max() + 2, max(0, xs.min() - 1):xs.max() + 2]
            mend_river_cuts(self.labels[box], self.river[box], ids)
            masks = [self.labels[box] == child for child in ids]
            minimum = self.part_minimum[self.state_of[province]]
            whole = all(label(mask)[1] == 1 and mask.sum() >= minimum for mask in masks)
            river = self.river[box]
            parent = (self.original[box] == province) | np.isin(self.labels[box], ids)
            slivers = stray_land(parent, river, np.zeros(river.shape, bool))
            if any(stray_land(mask, river, slivers).any() for mask in masks):
                self.failed_splits.append({"province": province, "parts": ids, "cut_by_river": True})
                continue
            lowest = min(roundness(mask) for mask in masks)
            if whole and lowest >= PART_MIN_ROUNDNESS:
                continue
            irregular_parent = own_roundness < IRREGULAR_PARENT and lowest >= own_roundness - IRREGULAR_LOSS
            if whole and (irregular_parent or lowest >= PART_MIN_ROUNDNESS - CORNER_LOSS):
                self.irregular.extend(child for child, mask in zip(ids, masks) if roundness(mask) < PART_MIN_ROUNDNESS)
            else:
                self.failed_splits.append({"province": province, "parts": ids, "roundness": round(lowest, 2)})

    # Plan

    def plan(self) -> dict:
        self.plan_settlements()
        for province in self.split_candidates():
            self.split(province)
        new_ids = [int(entry["province"]) for entry in self.entries]
        changed = self.labels != self.original
        touched = set(new_ids) | set(np.unique(self.original[changed]).tolist())
        clear_corners(self.labels, np.isin(self.labels, sorted(touched)) & ~self.water, self.state_of)
        self.check_states()
        self.judge_splits()
        return self.finish(new_ids)

    def check_states(self) -> None:
        for states in region_states(self.data).values():
            for state_id in states:
                before = [province for province, owner in self.scope.state_of.items() if owner == state_id]
                if (np.isin(self.original, before) != np.isin(self.labels, self.members(state_id))).any():
                    raise RuntimeError(f"state {state_id}: its pixel area changed")

    def finish(self, new_ids: list[int]) -> dict:
        """Record the plan and the river snapshot in the data; return the geometry sheet and the report."""
        coastal = set(np.unique(self.labels[neighbours_of(self.sea) & ~self.sea]).tolist())
        entries = []
        for entry in self.entries:
            record = {
                "province": entry["province"],
                "rgb": list(province_colour(int(entry["province"]), self.used)),
                "state": entry["state"],
                "parent": entry["parent"],
                "kind": entry["kind"],
            }
            if entry["province"] in coastal:
                record["coastal"] = True
            entries.append(record)
        full = self.grid.copy()
        full[self.window.s] = self.labels
        borders = province_border_count(full)
        refusal = border_margin_issue(borders)
        if refusal:
            raise RuntimeError(f"the plan is refused: {refusal}")
        sheet, origin, sheet_row = self.geometry_sheet(entries)
        plan = {
            "origin": origin,
            "sheet_row": sheet_row,
            "first_id": self.first_id,
            "provinces": entries,
            "cities": {str(city): city for city in sorted(self.cities)},
            "towns": {str(town): town for town in sorted(self.towns)},
            "irregular_parts": sorted(set(self.irregular)),
        }
        if self.stage == 2:
            self.full["stage2"]["existing_rivers"] = self.river_snapshot()
            self.full["stage2"]["ring_rivers"] = self.ring_snapshot()
            self.full["stage2"]["planned"] = plan
        else:
            record = {
                "stage": self.stage,
                **plan,
                "existing_rivers": self.river_snapshot(),
                "ring_rivers": self.ring_snapshot(),
                "grouping_centres": self.grouping_centres(),
            }
            self.full["stages"] = [*self.full.get("stages", []), record]
        return {"sheet": sheet, "report": self.summary(entries, borders, full)}

    def grouping_centres(self) -> dict[str, list[float]]:
        """Mean standing-anchor position (x, z) of every state of the stage on the uncarved map.

        Strategic-region grouping reads these centres instead of the carved
        map, where a split moves the anchors while the states keep their pixels.
        """
        positions: dict[int, tuple[float, float]] = {}
        rows, _newline = read_unitstacks((self.root / UNITSTACKS).read_bytes())
        for row in rows:
            if len(row) > 4 and row[0].isdigit() and row[1] == "0":
                positions.setdefault(int(row[0]), (float(row[2]), float(row[4])))
        centres = {}
        for states in region_states(self.data).values():
            for state_id in states:
                members = [province for province, owner in sorted(self.scope.state_of.items()) if owner == state_id]
                points = [positions[province] for province in members if province in positions]
                if not points:
                    raise RuntimeError(f"state {state_id}: no standing anchor for its grouping centre")
                centres[str(state_id)] = [
                    sum(point[0] for point in points) / len(points),
                    sum(point[1] for point in points) / len(points),
                ]
        return centres

    def geometry_sheet(self, entries: list[dict]) -> tuple[np.ndarray, list[int], int]:
        """The raster of the earlier stages with the changes of this stage stacked below it."""
        with Image.open(self.root / GEOMETRY_PATH) as source:
            first = np.asarray(source.convert("RGBA"))
        palette = {province: tuple(map(int, row[1:4])) for province, row in read_definition(self.root).rows.items()}
        palette.update({int(entry["province"]): tuple(entry["rgb"]) for entry in entries})
        if not (self.labels != self.original).any():
            return first, [self.window.x0, self.window.y0], int(first.shape[0])
        origin, second = geometry_image(self.labels, self.original, palette, [], self.window)
        width = max(first.shape[1], second.shape[1])
        sheet = np.zeros((first.shape[0] + second.shape[0], width, 4), np.uint8)
        sheet[:first.shape[0], :first.shape[1]] = first
        sheet[first.shape[0]:, :second.shape[1]] = second
        return sheet, origin, int(first.shape[0])

    def river_snapshot(self) -> dict[str, list[list[int]]]:
        """River pixels of the neighbour provinces as they stand before this builder draws its own."""
        neighbours = [
            province for province, state_id in self.scope.state_of.items() if self.scope.region_of[state_id] != "MON"
        ]
        river = river_masks(self.river_pixels, self.water) & np.isin(self.original, neighbours)
        snapshot: dict[str, list[list[int]]] = {}
        for y, x in zip(*np.nonzero(river)):
            pixel = [int(x) + self.window.x0, int(self.river_pixels[y, x])]
            snapshot.setdefault(str(int(y) + self.window.y0), []).append(pixel)
        return snapshot

    def ring_snapshot(self) -> dict[str, list[list[int]]]:
        """River pixels of the foreign land beside the scope where a state-line course may turn."""
        ring = corner_takers(self.labels, np.isin(self.labels, sorted(self.state_of)), self.water, self.window)
        snapshot: dict[str, list[list[int]]] = {}
        for y, x in zip(*np.nonzero(ring & river_masks(self.river_pixels, self.water))):
            pixel = [int(x) + self.window.x0, int(self.river_pixels[y, x])]
            snapshot.setdefault(str(int(y) + self.window.y0), []).append(pixel)
        return snapshot or {"0": []}

    def summary(self, entries: list[dict], borders: int, full: np.ndarray) -> dict:
        """Plan statistics per region, railway chains to reroute and the settlement table."""
        adjacency = province_adjacency(self.labels)
        children: dict[int, set[int]] = defaultdict(set)
        for entry in entries:
            children[int(entry["parent"])].add(int(entry["province"]))
        for parent in list(children):
            for child in list(children[parent]):
                children[parent] |= children.get(child, set())
        # The theatre builder reroutes its own lines; the map pass repairs the others.
        managed = {
            (min(a, b), max(a, b)) for route in managed_rail_routes() for a, b in zip(route, route[1:])
        }
        reroutes = []
        for a, b in sorted(self.pairs):
            if (a in self.state_of or b in self.state_of) and b not in adjacency.get(a, set()):
                allowed = {a, b} | children.get(a, set()) | children.get(b, set())
                reroutes.append(
                    {"segment": [a, b], "via": province_path(adjacency, a, b, allowed), "theatre_managed": (a, b) in managed}
                )
        regions = {}
        for tag, states in region_states(self.data).items():
            before = [
                province
                for province, state_id in self.scope.state_of.items()
                if state_id in states and self.kinds.get(province) == "land"
            ]
            mine = [entry for entry in entries if entry["state"] in states]
            regions[tag] = {
                "provinces_before": len(before),
                "provinces_after": len(before) + len(mine),
                "splits": len({entry["parent"] for entry in mine if entry["kind"] == "part"}),
                "new_ids": [mine[0]["province"], mine[-1]["province"]] if mine else [],
            }
        return {
            "stage": self.stage,
            "first_id": self.first_id,
            "last_id": self.first_id + len(entries) - 1,
            "new_ids": len(entries),
            "adopted": sorted(self.adopted),
            "borders": borders,
            "border_margin": BORDER_BUDGET - borders,
            "regions": regions,
            "failed_splits": self.failed_splits,
            "irregular_parts": sorted(set(self.irregular)),
            "coastal_unsplit": sorted(self.coastal_kept),
            "settlement_rail_losses": self.report_lost,
            "rail_reroutes": reroutes,
        }


def province_path(adjacency: dict[int, set[int]], start: int, goal: int, allowed: set[int]) -> list[int] | None:
    """Shortest chain of touching provinces from ``start`` to ``goal`` inside ``allowed``."""
    previous: dict[int, int | None] = {start: None}
    queue = deque([start])
    while queue:
        current = queue.popleft()
        if current == goal:
            chain = [goal]
            while previous[chain[-1]] is not None:
                chain.append(previous[chain[-1]])
            return chain[::-1]
        for step in sorted(adjacency.get(current, ())):
            if step in allowed and step not in previous:
                previous[step] = current
                queue.append(step)
    return None


def mend_provinces(root: Path = ROOT) -> dict:
    """Mend the geometry of the latest stage where a river course cuts a province or runs inside one.

    The rivers are routed with the slivers beside a canyon line tolerated,
    as Stage 1 routed them. A piece a course cuts off joins a province of
    its state that it touches across land; when it touches none, it joins
    its neighbour across the state line, which gives back one pixel of the
    same border, so both states keep their areas. A course pixel inside a
    province gets a border by moving one land pixel beside it to the
    province of the same state that this pixel touches. The pixels are
    recorded in the layer of the latest stage in the geometry raster, and
    rounds repeat until no change is needed, so the strict pass of the
    builder routes the same courses on borders only. From Stage 3 on only
    the provinces of that stage's regions change.
    """
    report: dict = {"mended": [], "unresolved": []}
    for _round in range(MEND_ROUNDS):
        data = active_data(read_json(root))
        latest = max(stage_layers(data))
        editable = None
        if latest > 2:
            editable = frozenset(
                int(state_id)
                for region in data["regions"].values()
                if region_stage(region) == latest
                for state_id in region["states"]
            )
        scope = load_scope(root, data)
        view = geography_view(data)
        definition = read_definition(root)
        register_planned_rows(definition, data)
        colours = definition.colours()
        with Image.open(root / PROVINCES) as source:
            original_rgb = np.asarray(source.convert("RGB"))
        grid = province_grid(stamp_geometry(root, original_rgb, data, colours, scope), colours)
        window = mon_window(grid, scope.provinces)
        sources = load_sources(root)
        ground = prepare_ground(root, view, scope, grid, definition.kinds(), sources["heightmap"][window.s], window)
        tolerated = np.zeros(ground.mon.shape, bool)
        for canyon in ground.canyons:
            tolerated |= canyon.near & neighbours_of(canyon.foreign)
        network = ground_rivers(view, window, ground, sources["rivers"][window.s], tolerated)
        river = river_masks(network.pixels, ground.water)
        labels = ground.labels.copy()
        mender = GeometryMender(labels, river, scope, editable)
        for province in rivers_splitting_provinces(labels, river, ground.mon, np.zeros(labels.shape, bool)):
            mender.mend_cut(province)
        for y, x in zip(*np.nonzero(river & ground.mon & ~province_borders(labels))):
            mender.give_border(int(y), int(x))
        report["unresolved"] = [
            {"province": province, "at": [x + window.x0, y + window.y0], "case": case} for province, (y, x), case in mender.unresolved
        ]
        if not mender.changes:
            break
        for province, (y, x), receiver in mender.changes:
            report["mended"].append({"province": province, "at": [x + window.x0, y + window.y0], "to": receiver})
        # A part that gave or took a pixel may fall below the minimum roundness; it is listed for review.
        record = stage_layers(data)[latest]
        irregular = set(record["irregular_parts"])
        for province in {value for giver, _pixel, receiver in mender.changes for value in (giver, receiver)}:
            if (province in scope.parts or province in scope.parts.values()) and roundness(labels == province) < PART_MIN_ROUNDNESS:
                irregular.add(province)
        record["irregular_parts"] = sorted(irregular)
        changed = labels != ground.labels
        updates = {
            (int(x) + window.x0, int(y) + window.y0): colours[int(labels[y, x])] for y, x in zip(*np.nonzero(changed))
        }
        record_stage_pixels(root, read_json(root), latest, sorted(irregular), updates)
    return report


class GeometryMender:
    """Single-pixel changes of the scope geometry that put every course on a border.

    A change never touches a city, town, district, a province the coastal
    builder repairs or a river pixel, and keeps every province in one piece.
    """

    def __init__(
        self, labels: np.ndarray, river: np.ndarray, scope: Scope, states: frozenset[int] | None = None
    ) -> None:
        self.labels = labels
        self.river = river
        self.scope = scope
        self.fixed = scope.urban | scope.adopted | (frozenset(PROVINCE_REPAIR_PROVINCES) & scope.provinces)
        # Only provinces of these states change; None leaves every scope state editable.
        self.states = states
        self.changes: list[tuple[int, tuple[int, int], int]] = []
        self.unresolved: list[tuple[int, tuple[int, int], str]] = []

    def movable(self, province: int) -> bool:
        if self.states is not None and self.scope.state_of.get(province) not in self.states:
            return False
        return province in self.scope.provinces and province not in self.fixed

    def assign(self, y: int, x: int, receiver: int) -> bool:
        """Give one land pixel to ``receiver`` when both provinces stay whole and no four provinces meet."""
        giver = int(self.labels[y, x])
        if not self.movable(giver) or not self.movable(receiver):
            return False
        box = np.s_[y - 3:y + 4, x - 3:x + 4]
        before = self.labels[box].copy()
        self.labels[y, x] = receiver
        after = self.labels[box]
        nothing = np.zeros(after.shape, bool)
        whole = all(label(after == value)[1] <= label(before == value)[1] for value in (giver, receiver))
        # The box may show a province in pieces that join outside it; no piece may be added.
        river = self.river[box]
        uncut = all(
            stray_land(after == value, river, nothing).sum() <= stray_land(before == value, river, nothing).sum()
            for value in (giver, receiver)
        )
        a, b, c, d = after[:-1, :-1], after[:-1, 1:], after[1:, :-1], after[1:, 1:]
        corners = ((a != b) & (a != c) & (a != d) & (b != c) & (b != d) & (c != d)).any()
        if whole and uncut and not corners:
            self.changes.append((giver, (y, x), receiver))
            return True
        self.labels[box] = before
        return False

    def mend_cut(self, province: int) -> None:
        if not self.movable(province):
            self.unresolved.append((province, interior_point(self.labels == province), "cut, fixed province"))
            return
        for piece, receiver in cut_off_pieces(self.labels, self.river, province, self.scope):
            pixels = list(zip(*np.nonzero(piece)))
            if receiver is not None and self.movable(receiver):
                if all(self.assign(int(y), int(x), receiver) for y, x in pixels):
                    continue
            if not self.swap_across(province, piece, pixels):
                self.unresolved.append((province, (int(pixels[0][0]), int(pixels[0][1])), "cut"))

    def swap_across(self, province: int, piece: np.ndarray, pixels: list) -> bool:
        """Give the piece to its neighbour across the state line and restore both state areas.

        As many pixels then move back towards the state of ``province``,
        across a land contact of the two states or through one other state
        of the scope, far from the piece.
        """
        ring = neighbours_of(piece) & ~piece & ~self.river
        options = Counter(int(value) for value in self.labels[ring].tolist() if self.movable(int(value)) and value != province)
        home = self.scope.state_of[province]
        for receiver, _count in options.most_common():
            snapshot = (self.labels.copy(), len(self.changes))
            away = self.scope.state_of[receiver]
            if all(self.assign(int(y), int(x), receiver) for y, x in pixels):
                if all(self.balance(away, home, piece) for _pixel in pixels):
                    return True
            self.labels[...] = snapshot[0]
            del self.changes[snapshot[1]:]
        return False

    def balance(self, source: int, target: int, avoid: np.ndarray) -> bool:
        """Move one land pixel from state ``source`` to state ``target``, directly or through a third state."""
        if self.transfer(source, target, avoid):
            return True
        for middle in sorted(set(self.scope.states) - {source, target}):
            snapshot = (self.labels.copy(), len(self.changes))
            if self.transfer(source, middle, avoid) and self.transfer(middle, target, avoid):
                return True
            self.labels[...] = snapshot[0]
            del self.changes[snapshot[1]:]
        return False

    def transfer(self, source: int, target: int, avoid: np.ndarray) -> bool:
        """Move one land pixel of a province of ``source`` to a province of ``target`` it touches across land."""
        states = lookup_raster(self.labels, self.scope.state_of)
        movable = ~np.isin(self.labels, sorted(self.fixed)) & ~self.river
        targets = (states == target) & movable
        candidates = (states == source) & movable & neighbours_of(targets) & ~neighbours_of(self.river)
        candidates &= distance_transform_edt(~avoid) > MEND_DISTANCE
        for y, x in zip(*np.nonzero(candidates)):
            receivers = {
                int(self.labels[ny, nx])
                for ny, nx in ((y - 1, x), (y + 1, x), (y, x - 1), (y, x + 1))
                if targets[ny, nx]
            }
            for receiver in sorted(receivers):
                if self.assign(int(y), int(x), receiver):
                    return True
        return False

    def give_border(self, y: int, x: int) -> None:
        """Move a pixel beside an interior course pixel to another province of its state.

        Land pixels are tried first. A course pixel may move too when it
        stays on a border, since only its province changes.
        """
        province = int(self.labels[y, x])
        if self.on_border(y, x):
            return
        state_id = self.scope.state_of.get(province)
        sides = ((y - 1, x), (y + 1, x), (y, x - 1), (y, x + 1))
        for wy, wx in sorted(sides, key=lambda side: bool(self.river[side])):
            for ny, nx in ((wy - 1, wx), (wy + 1, wx), (wy, wx - 1), (wy, wx + 1)):
                receiver = int(self.labels[ny, nx])
                if receiver == province or self.scope.state_of.get(receiver) != state_id:
                    continue
                if not self.assign(wy, wx, receiver):
                    continue
                if not self.river[wy, wx] or self.on_border(wy, wx):
                    return
                self.labels[wy, wx] = province
                self.changes.pop()
        self.unresolved.append((province, (y, x), "inside"))

    def on_border(self, y: int, x: int) -> bool:
        return any(int(self.labels[ny, nx]) != int(self.labels[y, x]) for ny, nx in ((y - 1, x), (y + 1, x), (y, x - 1), (y, x + 1)))


def cut_off_pieces(labels: np.ndarray, river: np.ndarray, province: int, scope: Scope) -> list[tuple[np.ndarray, int | None]]:
    """Each piece a river cuts off ``province``, with the rural province of its state it touches across land."""
    ys, xs = np.nonzero(labels == province)
    box = np.s_[max(0, ys.min() - 1):ys.max() + 2, max(0, xs.min() - 1):xs.max() + 2]
    local = labels[box]
    stray = stray_land(local == province, river[box], np.zeros(local.shape, bool))
    pieces, count = label(stray)
    state_id = scope.state_of[province]
    result = []
    for index in range(1, count + 1):
        piece = np.zeros(labels.shape, bool)
        piece[box] = pieces == index
        ring = neighbours_of(piece) & ~piece & ~river
        options = [
            int(value)
            for value in labels[ring].tolist()
            if value != province and scope.state_of.get(int(value)) == state_id and int(value) not in scope.urban
        ]
        result.append((piece, Counter(options).most_common(1)[0][0] if options else None))
    return result


def record_stage_pixels(
    root: Path,
    data: dict,
    number: int,
    irregular: list[int],
    updates: dict[tuple[int, int], tuple[int, int, int]],
) -> None:
    """Add pixels to the layer of the latest stage, widening it when needed, and record its irregular parts.

    The latest stage owns the last rows of the raster.
    """
    with Image.open(root / GEOMETRY_PATH) as source:
        sheet = np.asarray(source.convert("RGBA"))
    if number != max(stage_layers(data)) or number < 2:
        raise RuntimeError(f"Stage {number} is not the latest planned stage")
    later = stage_layers(data)[number]
    later["irregular_parts"] = irregular
    later["origin"], result = widen_stage_layer(sheet, later, updates)
    Image.fromarray(result, "RGBA").save(root / GEOMETRY_PATH, optimize=True)
    (root / DATA_PATH).write_text(dump_data(data), encoding="utf-8", newline="\n")


def widen_stage_layer(
    sheet: np.ndarray, record: dict, updates: dict[tuple[int, int], tuple[int, int, int]], alpha: int = 255
) -> tuple[list[int], np.ndarray]:
    """The origin and the raster of the latest stage ``record`` with ``updates`` ({(x, y): rgb}) painted in.

    The layer grows to hold them; the rows of the earlier stages stay as they are.
    """
    split = int(record["sheet_row"])
    first, second = sheet[:split], sheet[split:]
    x0, y0 = record["origin"]
    xs = [x for x, _y in updates] + [x0, x0 + second.shape[1] - 1]
    ys = [y for _x, y in updates] + [y0, y0 + second.shape[0] - 1]
    left, top = min(xs), min(ys)
    layer = np.zeros((max(ys) - top + 1, max(xs) - left + 1, 4), np.uint8)
    layer[y0 - top:y0 - top + second.shape[0], x0 - left:x0 - left + second.shape[1]] = second
    for (x, y), colour in updates.items():
        layer[y - top, x - left] = (*colour, alpha)
    width = max(first.shape[1], layer.shape[1])
    result = np.zeros((first.shape[0] + layer.shape[0], width, 4), np.uint8)
    result[:first.shape[0], :first.shape[1]] = first
    result[first.shape[0]:, :layer.shape[1]] = layer
    return [left, top], result


STATE_SMOOTHING_REPORT = "mon_stage_state_smoothing.json"
# Layer alpha of the pixels the state-line smoothing moved; the stamp reads
# any alpha above 0, and the state-area check lets exactly these change state.
SMOOTHED_ALPHA = 254


def smoothed_mask(root: Path, data: dict, window: Window) -> np.ndarray:
    """Window pixels that the state-line smoothing of any stage moved."""
    result = np.zeros((window.y1 - window.y0, window.x1 - window.x0), bool)
    if not data["planned"]["provinces"]:
        return result
    with Image.open(root / GEOMETRY_PATH) as source:
        sheet = np.asarray(source.convert("RGBA"))
    for (x0, y0), geometry in geometry_layers(data, sheet):
        ys, xs = np.nonzero(geometry[..., 3] == SMOOTHED_ALPHA)
        ys = ys + y0 - window.y0
        xs = xs + x0 - window.x0
        inside = (ys >= 0) & (ys < result.shape[0]) & (xs >= 0) & (xs < result.shape[1])
        result[ys[inside], xs[inside]] = True
    return result
# The longer lines of the east, with the split states among them, still move
# a few pixels up to the thirteenth pass; the plan stores the settled state,
# so a second run moves none.
STAGE_SMOOTHING_PASSES = 16


def history_states(root: Path) -> dict[int, int]:
    """The state of every province that a state history file lists."""
    result = {}
    for path in sorted((root / "history/states").glob("*.txt")):
        source = path.read_text(encoding="utf-8-sig")
        state = re.search(r"\bid\s*=\s*(\d+)", source)
        block = re.search(r"\bprovinces\s*=\s*\{([^}]*)\}", source)
        if state is None or block is None:
            continue
        for value in re.findall(r"\d+", block.group(1)):
            result[int(value)] = int(state.group(1))
    return result


def smoothing_limits(scope: Scope, data: dict) -> tuple[dict[int, int], dict[int, float]]:
    """Least size and roundness of the planned provinces, as ``carve_issues`` checks them."""
    part_minimum = state_parameter(data, "part_min_pixels", PART_MIN_PIXELS)
    exempt = {province for record in later_layers(data) for province in record.get("irregular_parts", [])}
    sizes: dict[int, int] = {}
    shapes: dict[int, float] = {}
    for province, entry in scope.planned.items():
        if entry["kind"] == "remainder" and province not in scope.parts.values():
            sizes[province] = remainder_minimum(scope, entry)
    for part, parent in scope.parts.items():
        for province in (part, parent):
            sizes[province] = max(sizes.get(province, 0), int(part_minimum[scope.state_of[province]]))
            if province not in exempt:
                shapes[province] = PART_MIN_ROUNDNESS
    return sizes, shapes


def stage_smoothing_frozen(
    root: Path,
    view: dict,
    scope: Scope,
    grid: np.ndarray,
    window: Window,
    rivers: np.ndarray,
    reference: np.ndarray,
    land: np.ndarray,
) -> np.ndarray:
    """Window pixels that keep their province while the state lines of the latest stage are smoothed.

    The pixels ``frozen_pixels`` keeps (the band beside the IVN geography,
    keep zones, ``keep_provinces``, ``keep_above``), the belt beside earlier
    stages, the provinces the coastal builder repairs, the standing and
    victory-point anchors and the supply-hub models, and every province
    along a course this builder redraws on each pass, with the pixels round
    it. Those courses are where the river layer differs from the restored
    snapshot; a line moved beside them would move the course on the next pass.
    """
    labels = window_labels(grid, window)
    eight = np.ones((3, 3), bool)
    mon = np.isin(labels, sorted(scope.provinces))
    states = lookup_raster(labels, scope.state_of)
    with Image.open(root / HEIGHTMAP) as source:
        heights = np.asarray(source)[window.s]
    frozen = frozen_pixels(view, labels, mon, window, heights, states) | stage_belt(view, mon, states)
    repaired = sorted(PROVINCE_REPAIR_PROVINCES & scope.provinces)
    if repaired:
        frozen |= binary_dilation(np.isin(labels, repaired), eight)
    unitstacks = (root / UNITSTACKS).read_bytes()
    points = [point for slot in (0, VICTORY_POINT_SLOT) for point in slot_points(unitstacks, grid.shape[0], slot).values()]
    # The pass does not write the building models; a dry run keeps them in the repository.
    points += [point for hub in supply_node_points(grid, ROOT).values() for point in hub]
    for x, y in points:
        lx, ly = x - window.x0, y - window.y0
        if 0 <= ly < labels.shape[0] and 0 <= lx < labels.shape[1]:
            frozen[ly, lx] = True
    redrawn = mon & land & ((rivers < RIVER_SEA_PALETTE) != (reference < RIVER_SEA_PALETTE))
    if redrawn.any():
        carriers = np.unique(labels[binary_dilation(redrawn, eight) & mon])
        frozen |= binary_dilation(np.isin(labels, carriers), eight)
    return frozen


def smooth_stage_plan(root: Path = ROOT) -> tuple[dict, np.ndarray, dict, dict]:
    """Smooth the lines between the states of the latest planned stage (spec 13.3 of the Itora-Vorkerland design).

    States come from the history files, so a state split off after the plan
    is a state of its own. The ``no_split_states`` of the stage keep every
    pixel. Returns the data, the raster, the report and the window arrays
    for previews; the moved pixels join the layer of the stage, so the map
    pass stamps them with the rest of its plan.
    """
    data = read_json(root)
    number = max(stage_layers(data))
    if number < 3:
        raise RuntimeError("no stage after Stage 2 is planned")
    active = active_data(data)
    view = geography_view(active)
    scope = load_scope(root, active)
    definition = read_definition(root)
    register_planned_rows(definition, active)
    colours = definition.colours()
    kinds = definition.kinds()
    with Image.open(root / PROVINCES) as source:
        original = np.asarray(source.convert("RGB"))
    grid = province_grid(stamp_geometry(root, original, active, colours, scope), colours).astype(np.int32)
    regions = [region for region in active["regions"].values() if region_stage(region) == number]
    listed = {int(state_id) for region in regions for state_id in region["states"]}
    fixed = {int(state_id) for region in regions for state_id in region.get("no_split_states", [])}
    history = history_states(root)
    state_of = {province: history.get(province, state_id) for province, state_id in scope.state_of.items()}
    stage_provinces = frozenset(province for province, state_id in scope.state_of.items() if state_id in listed)
    stage_states = frozenset(state_of[province] for province in stage_provinces)
    window = mon_window(grid, stage_provinces)
    labels = window_labels(grid, window)
    land = np.isin(labels, [province for province, kind in kinds.items() if kind == "land"])
    with Image.open(root / RIVERS) as source:
        rivers = np.asarray(source)[window.s]
    reference = reference_rivers(view, window, labels.shape)
    ring = reference_rivers(view, window, labels.shape, "ring_rivers")
    # The restored snapshot is repaired on every pass, so its pixels and their banks stay too.
    river = land & ((rivers < RIVER_SEA_PALETTE) | (reference < RIVER_SEA_PALETTE) | (ring < RIVER_SEA_PALETTE))
    frozen = stage_smoothing_frozen(root, view, scope, grid, window, rivers, reference, land)
    kept = kept_terrains(scope, definition)
    settlements = scope.urban | scope.adopted | {province for province, terrain in kept.items() if terrain == "urban"}
    sizes, shapes = smoothing_limits(scope, active)
    smoothing = smooth_state_borders(
        labels,
        state_of,
        stage_states - fixed,
        land,
        river,
        settlements=frozenset(settlements),
        frozen=frozen,
        rail_pairs=rail_pairs(root),
        min_pixels=sizes,
        min_roundness=shapes,
        passes=STAGE_SMOOTHING_PASSES,
    )
    full = grid.copy()
    full[window.s] = smoothing.labels
    borders = province_border_count(full)
    states_before = province_states(labels, state_of)
    states_after = province_states(smoothing.labels, state_of)
    course = land & (rivers < RIVER_SEA_PALETTE)
    moved = smoothing.labels != labels
    sheet_data = data
    with Image.open(root / GEOMETRY_PATH) as source:
        sheet = np.asarray(source.convert("RGBA")).copy()
    if moved.any():
        record = stage_layers(data)[number]
        updates = {
            (int(x) + window.x0, int(y) + window.y0): colours[int(smoothing.labels[y, x])] for y, x in zip(*np.nonzero(moved))
        }
        origin, sheet = widen_stage_layer(sheet, record, updates, SMOOTHED_ALPHA)
        sheet_data = dict(data)
        sheet_data["stages"] = [
            {**entry, "origin": origin} if entry is record else entry for entry in data["stages"]
        ]
    report = {
        "stage": number,
        **smoothing.report(),
        "window": [window.x0, window.y0, window.x1, window.y1],
        "smoothed_states": sorted(stage_states - fixed),
        "frozen_states": sorted(fixed),
        "frozen_pixels": int((frozen & land & np.isin(labels, sorted(stage_provinces))).sum()),
        "borders_before": province_border_count(grid),
        "borders": borders,
        "border_margin": BORDER_BUDGET - borders,
        "interior_river_pixels_before": interior_river_pixels_by_state(course, states_before, land, stage_states),
        "interior_river_pixels_after": interior_river_pixels_by_state(course, states_after, land, stage_states),
    }
    arrays = {"before": states_before, "after": states_after, "land": land, "river": course, "states": stage_states}
    return sheet_data, sheet, report, arrays


def write_smoothed_stage_plan(root: Path = ROOT, output_root: Path | None = None, previews: bool = False) -> dict:
    """Smooth the latest stage; write the plan under ``output_root`` only when one is given.

    ``output_root`` is the repository itself or a directory outside it.
    Nothing is written when no pixel moves, the smoothing did not settle
    within its passes or a railway segment lost its contact. Outside the
    repository the report is written beside the plan.
    """
    if dump_data(read_json(root)).encode("utf-8") != (root / DATA_PATH).read_bytes():
        raise RuntimeError(f"{DATA_PATH.name} is not in the planner's format; it would be rewritten")
    if output_root is not None and output_root.resolve() != ROOT.resolve():
        output_root = outside_repository(output_root)
    data, sheet, report, arrays = smooth_stage_plan(root)
    if report["border_margin"] < BORDER_MARGIN:
        raise RuntimeError(
            f"smoothing draws {report['borders']} province borders: less than {BORDER_MARGIN} of {BORDER_BUDGET} stay free"
        )
    report["written"] = False
    if output_root is not None and report["stable"] and report["moved_pixels"] and not report["rail_segments_lost"]:
        write_plan_files(output_root, data, sheet)
        report["written"] = True
    if previews:
        name = f"mon_stage{report['stage']}_state_smoothing.png"
        paths = write_state_smoothing_previews(STATE_SMOOTHING_PREVIEW_DIR, arrays, arrays["states"], name)
        report["previews"] = [path.as_posix() for path in paths]
    if output_root is not None and output_root.resolve() != ROOT.resolve():
        output_root.mkdir(parents=True, exist_ok=True)
        (output_root / STATE_SMOOTHING_REPORT).write_text(
            json.dumps(report, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
        )
    return report


def snapshot_ring_rivers(root: Path = ROOT) -> int:
    """Record the river pixels of the foreign land beside the scope, as they stand now.

    A course on the state line may turn on that land; each pass restores
    the recorded pixels first, so a turn never outlives its course. The
    snapshot is taken once, before any pass has turned a course there.
    """
    data = read_json(root)
    if data["stage2"].get("ring_rivers"):
        raise RuntimeError("the ring river snapshot exists")
    scope = load_scope(root, data)
    definition = read_definition(root)
    register_planned_rows(definition, data)
    colours = definition.colours()
    with Image.open(root / PROVINCES) as source:
        grid = province_grid(stamp_geometry(root, np.asarray(source.convert("RGB")), data, colours, scope), colours)
    window = mon_window(grid, scope.provinces)
    labels = window_labels(grid, window)
    kinds = definition.kinds()
    water = np.isin(labels, [province for province, kind in kinds.items() if kind in ("sea", "lake")])
    ring = corner_takers(labels, np.isin(labels, list(scope.provinces)), water, window)
    with Image.open(root / RIVERS) as source:
        rivers = np.asarray(source)[window.s]
    snapshot: dict[str, list[list[int]]] = {}
    for y, x in zip(*np.nonzero(ring & (rivers < RIVER_SEA_PALETTE))):
        snapshot.setdefault(str(int(y) + window.y0), []).append([int(x) + window.x0, int(rivers[y, x])])
    # An empty ring still marks the snapshot as taken.
    data["stage2"]["ring_rivers"] = snapshot or {"0": []}
    (root / DATA_PATH).write_text(dump_data(data), encoding="utf-8", newline="\n")
    return sum(len(pixels) for pixels in snapshot.values())


def next_stage(data: dict) -> int | None:
    """The first stage without its plan: Stage 1, then the stages of the authored regions."""
    if not has_stage_plan(data, 1):
        return 1
    stages = sorted({region_stage(region) for region in data.get("regions", {}).values()})
    return next((number for number in stages if not has_stage_plan(data, number)), None)


def plan_stage(root: Path, number: int) -> tuple[dict, np.ndarray, dict]:
    """Plan one stage on the map the earlier stages left; return the data, the geometry sheet and the report.

    A stored plan is never replanned from a map that carries it.
    """
    data = read_json(root)
    if has_stage_plan(data, number):
        raise RuntimeError(f"the Stage {number} plan exists: restore the pre-apply map and remove its record first")
    result = StagePlanner(root, data, number).plan()
    return data, result["sheet"], result["report"]


def outside_repository(directory: Path) -> Path:
    """Resolve a working directory and refuse one inside the repository, where it could shadow its files."""
    directory = directory.resolve()
    if directory == ROOT.resolve() or ROOT.resolve() in directory.parents:
        raise RuntimeError(f"{directory}: choose a directory outside the repository")
    return directory


def write_stage_plan(root: Path = ROOT, output_root: Path | None = None) -> dict:
    """Plan the next stage and write its data and raster under ``output_root`` (the repository by default).

    Outside the repository the report is written beside them.
    """
    if output_root is not None:
        output_root = outside_repository(output_root)
    data = read_json(root)
    number = next_stage(data)
    if number is None:
        raise RuntimeError("every authored stage is planned")
    if number == 1:
        return plan_provinces(root, output_root)
    data, sheet, report = plan_stage(root, number)
    write_plan_files(root if output_root is None else output_root, data, sheet)
    if output_root is not None:
        (output_root / PLAN_REPORT).write_text(json.dumps(report, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return report


def copy_inputs(directory: Path, root: Path = ROOT) -> None:
    """Copy the map, state, unit and name inputs of the pass into ``directory`` as plain files; the plan stays.

    A copy is never a link, so no write in the directory reaches the map.
    """
    histories = [*sorted((root / "history/states").glob("*.txt")), *sorted((root / UNITS).glob("*.txt"))]
    sources = [*DRY_RUN_INPUTS, *(path.relative_to(root) for path in histories)]
    for relative in sources:
        target = directory / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(root / relative, target)


def dry_run(directory: Path) -> dict:
    """Apply the plan in ``directory`` to fresh copies of the map there, twice, and write previews.

    The plan comes from ``--plan-provinces --output-root`` with the same
    directory. The second pass must find nothing left to change. Previews
    go to ``directory/previews``.
    """
    directory = outside_repository(directory)
    if not (directory / DATA_PATH).exists() or not (directory / GEOMETRY_PATH).exists():
        raise RuntimeError(f"{directory}: no plan; run --plan-provinces --output-root first")
    copy_inputs(directory)
    first = apply(directory)
    repeated = build_plan(directory)
    previews = write_previews(directory, Path("previews"))
    return {
        "issues": first.issues,
        "stale_after_second_pass": [path.as_posix() for path in stale_outputs(repeated, directory)],
        "borders": first.report["borders"],
        "border_margin": BORDER_BUDGET - first.report["borders"],
        "unplanned_stages": first.report["unplanned_stages"],
        "rail_repairs": first.report["rail_repairs"],
        "managed_rail_breaks": first.report["managed_rail_breaks"],
        "region_terrain": first.report["region_terrain"],
        "heights": first.report["heights"],
        "previews": [path.as_posix() for path in previews],
    }


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
    "desert": (230, 205, 140),
    "urban": (200, 40, 40),
}
# Kept city terrains of the map (vorkernsberg and the national city terrains).
KEPT_CITY_COLOUR = (150, 30, 90)


def _borders(labels: np.ndarray) -> np.ndarray:
    return province_borders(labels.astype(np.uint32))


def _upscale(image: np.ndarray, scale: int) -> Image.Image:
    return Image.fromarray(image).resize((image.shape[1] * scale, image.shape[0] * scale), Image.NEAREST)


def preview_images(root: Path = ROOT, directory: Path = PREVIEW_DIR) -> dict[Path, Image.Image]:
    """Review images of the whole scope, of every region and of the canyons."""
    data = active_data(read_json(root))
    scope = load_scope(root, data)
    view = geography_view(data)
    definition = read_definition(root)
    register_planned_rows(definition, data)
    colours = definition.colours()
    with Image.open(root / PROVINCES) as source:
        original_rgb = np.asarray(source.convert("RGB"))
    rgb = stamp_geometry(root, original_rgb, data, colours, scope)
    grid = province_grid(rgb, colours)
    window = mon_window(grid, scope.provinces)
    before = window_labels(province_grid(original_rgb, colours), window)
    sources = load_sources(root)
    geography = build_geography(root, view, scope, grid, definition, sources, window)
    relief = relief_image(geography)
    terrain = terrain_image(geography)
    images = {}
    for name, array in (("plan_relief_rivers.png", relief), ("plan_terrain.png", terrain)):
        image = _upscale(array, 2)
        _label_settlements(ImageDraw.Draw(image), view, grid, window, 2, (0, 0))
        images[directory / name] = image
    images[directory / "plan_cities.png"] = city_sheet(data, scope, geography.labels, before, geography)
    for canyon in geography.canyons:
        name = re.sub(r"[^a-z]+", "_", canyon.feature["name"].lower()).strip("_")
        images[directory / f"plan_{name}.png"] = canyon_sheet(canyon, geography, sources["heightmap"][window.s])
    hydrology = hydrology_image(geography, sources["rivers"], window)
    provinces = province_change_image(geography, before, scope)
    for tag, states in region_states(data).items():
        ys, xs = np.nonzero(np.isin(geography.states, states))
        crop = np.s_[max(0, ys.min() - 6):ys.max() + 7, max(0, xs.min() - 6):xs.max() + 7]
        offset = (crop[1].start, crop[0].start)
        for kind, array in (("relief", relief), ("terrain", terrain), ("hydrology", hydrology), ("provinces", provinces)):
            image = _upscale(array[crop], REGION_PREVIEW_SCALE)
            if kind != "provinces":
                _label_settlements(ImageDraw.Draw(image), view, grid, window, REGION_PREVIEW_SCALE, offset)
            images[directory / f"{tag}_{kind}.png"] = image
    return images


REGION_PREVIEW_SCALE = 4


def relief_image(geography: Geography) -> np.ndarray:
    """Hillshade with borders, water, rivers, cities and towns; frozen pixels are outlined in magenta."""
    labels = geography.labels
    borders = _borders(labels) & (geography.mon | neighbours_of(geography.mon))
    river = geography.network.pixels < RIVER_SEA_PALETTE
    relief = hillshade(geography.heights)
    relief[borders] = (relief[borders] * 0.8).astype(np.uint8)
    relief[_borders(geography.states) & geography.mon] = (30, 30, 30)
    relief[geography.water] = (80, 120, 200)
    relief[river] = (20, 60, 230)
    relief[geography.cities] = (220, 40, 40)
    for core in geography.cores.values():
        relief[core] = (250, 150, 20)
    relief[geography.fringe] = (240, 110, 110)
    if geography.frozen is not None:
        relief[geography.frozen & _borders(geography.frozen.astype(np.int64))] = (255, 0, 255)
    return relief


def terrain_image(geography: Geography) -> np.ndarray:
    labels = geography.labels
    colours = np.full((int(labels.max()) + 1, 3), 235, np.uint8)
    for province, terrain_type in geography.desired.items():
        colours[province] = TERRAIN_COLOURS.get(terrain_type, KEPT_CITY_COLOUR)
    terrain = np.where(geography.mon[..., None], colours[labels], 235).astype(np.uint8)
    borders = _borders(labels) & (geography.mon | neighbours_of(geography.mon))
    terrain[borders] = (terrain[borders] * 0.75).astype(np.uint8)
    terrain[_borders(geography.states) & geography.mon] = (20, 20, 20)
    terrain[geography.water] = (80, 120, 200)
    terrain[geography.network.pixels < RIVER_SEA_PALETTE] = (20, 60, 230)
    for core in geography.cores.values():
        terrain[core] = (250, 150, 20)
    return terrain


RIVER_WIDTH_COLOURS = {
    3: (150, 190, 255),
    4: (120, 165, 250),
    6: (90, 140, 240),
    7: (60, 115, 230),
    9: (40, 90, 215),
    10: (25, 65, 190),
    11: (10, 40, 160),
}


def hydrology_image(geography: Geography, rivers: np.ndarray, window: Window) -> np.ndarray:
    """River widths from light to dark, sources green, flow-in pixels red, flow marks orange.

    The engine walks a river from its source downstream and a tributary from
    its flow-in pixel upstream. Every eighth pixel of a walk marks the next
    pixel downstream.
    """
    image = (hillshade(geography.heights).astype(float) * 0.45 + 140).astype(np.uint8)
    image[geography.water] = (170, 200, 240)
    image[_borders(geography.states) & geography.mon] = (90, 90, 90)
    pixels = geography.network.pixels
    for width, colour in RIVER_WIDTH_COLOURS.items():
        image[pixels == width] = colour
    full = rivers.copy()
    full[window.s] = pixels
    water = np.zeros(full.shape, bool)
    water[window.s] = geography.water
    _visits, _forks, walks = walk_courses(full, water)
    for start, walk in walks.items():
        downstream = walk if full[start[1], start[0]] == RIVER_SOURCE_PALETTE else walk[::-1]
        for index in range(4, len(downstream) - 1, 8):
            x, y = downstream[index + 1]
            ly, lx = y - window.y0, x - window.x0
            if 0 <= ly < image.shape[0] and 0 <= lx < image.shape[1]:
                image[ly, lx] = (255, 150, 0)
    image[pixels == RIVER_SOURCE_PALETTE] = (0, 200, 0)
    image[pixels == RIVER_FLOW_IN_PALETTE] = (230, 0, 0)
    return image


def province_change_image(geography: Geography, before: np.ndarray, scope: Scope) -> np.ndarray:
    """Province geometry before and after: removed borders magenta, new borders dark, kept borders black.

    Split parts are tinted green, remainders sand, cities red, towns orange
    and districts violet.
    """
    labels = geography.labels
    image = np.full(labels.shape + (3,), 235, np.uint8)
    image[np.isin(labels, sorted(set(scope.parts) | set(scope.parts.values())))] = (205, 225, 190)
    remainders = [province for province, entry in scope.planned.items() if entry["kind"] == "remainder"]
    image[np.isin(labels, remainders)] = (240, 215, 160)
    image[geography.cities] = (220, 60, 60)
    image[np.isin(labels, sorted(scope.towns))] = (250, 150, 20)
    image[np.isin(labels, sorted(scope.districts))] = (200, 120, 200)
    image[geography.water] = (80, 120, 200)
    old = _borders(before)
    new = _borders(labels)
    image[old & ~new] = (200, 0, 200)
    image[new & ~old] = (70, 70, 70)
    image[old & new] = (0, 0, 0)
    image[~geography.mon & ~geography.water] = (180, 180, 180)
    return image


def names_table(data: dict) -> str:
    """Markdown table of every settlement for the author's review."""
    lines = [
        "# Settlements of the eastern geography",
        "",
        "Stage 1 villages become carved towns once the Stage 2 plan exists.",
        "",
        "| Region | State | Kind | Province | VP | Russian | English | Stage |",
        "|---|---|---|---|---|---|---|---|",
    ]
    later = {id(entry) for entry in data.get("stage2", {}).get("settlements", [])}
    regions = data.get("regions", {})
    for tag, entry in all_settlements(data):
        if entry["kind"] == "district":
            continue
        if tag != "MON":
            stage = str(region_stage(regions[tag]))
        else:
            stage = "2" if id(entry) in later else "1"
        kind = "town" if entry["kind"] == "village" and has_stage2_plan(data) else entry["kind"]
        lines.append(
            f"| {tag} | {entry['state']} | {kind} | {settlement_province(entry)} | {entry.get('value', '')} | "
            f"{entry.get('name', '')} | {entry.get('name_en', '')} | {stage} |"
        )
    return "\n".join(lines) + "\n"


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


def _label_settlements(
    draw: ImageDraw.ImageDraw, data: dict, grid: np.ndarray, window: Window, scale: int, offset: tuple[int, int]
) -> None:
    """Write the province, VP and English name beside every city and town in the image."""
    boxes = find_objects(grid)
    width, height = draw.im.size
    for _tag, entry in all_settlements(data):
        province = settlement_province(entry)
        if province is None or entry["kind"] == "district":
            continue
        _oy, _ox, _inside, _depth, (cx, cy) = province_interior(grid, province, boxes[province - 1])
        x = (cx - window.x0 - offset[0]) * scale
        y = (cy - window.y0 - offset[1]) * scale
        if not (0 <= x < width and 0 <= y < height):
            continue
        text = f"{province} VP{entry.get('value', '-')} {entry.get('name_en', '')}".strip()
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


def write_previews(root: Path = ROOT, directory: Path | None = None) -> list[Path]:
    """Write the review images and the settlement table, by default to the development previews."""
    directory = PREVIEW_DIR if directory is None else directory
    paths = []
    for path, image in preview_images(root, directory).items():
        (root / path).parent.mkdir(parents=True, exist_ok=True)
        image.save(root / path, optimize=True)
        paths.append(path)
    table = directory / "settlements.md"
    (root / table).write_text(names_table(read_json(root)), encoding="utf-8", newline="\n")
    return [*paths, table]


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
    mode.add_argument(
        "--plan-provinces", action="store_true", help="plan the province geometry of the next stage into the data file"
    )
    mode.add_argument("--preview", action="store_true", help="write review images")
    mode.add_argument(
        "--mend-provinces",
        action="store_true",
        help="give pieces that rivers cut off to a neighbour in the geometry of the latest stage",
    )
    mode.add_argument(
        "--dry-run",
        type=Path,
        metavar="DIR",
        help="apply the plan in DIR to copies of the map there, twice, and write previews and a report",
    )
    mode.add_argument(
        "--smooth-stage-state-borders",
        action="store_true",
        help="smooth the lines between the states of the latest stage; report only without --output-root",
    )
    parser.add_argument("--preview-dir", type=Path, default=None, help="directory of the review images")
    parser.add_argument(
        "--output-root",
        type=Path,
        default=None,
        help=(
            "directory outside the repository that receives the plan of --plan-provinces or --mend-provinces; "
            "--smooth-stage-state-borders also accepts the repository itself"
        ),
    )
    parser.add_argument(
        "--previews",
        action="store_true",
        help="with --smooth-stage-state-borders, write the state previews beside the IVN ones",
    )
    args = parser.parse_args()
    if args.plan_provinces:
        report = write_stage_plan(ROOT, args.output_root)
        print(json.dumps(report, ensure_ascii=False, indent=1))
        return 0
    if args.mend_provinces:
        root = ROOT
        if args.output_root is not None:
            # Mending reads the plan there and a fresh copy of the map beside it.
            root = outside_repository(args.output_root)
            copy_inputs(root)
        print(json.dumps(mend_provinces(root), ensure_ascii=False, indent=1))
        return 0
    if args.smooth_stage_state_borders:
        report = write_smoothed_stage_plan(ROOT, args.output_root, args.previews)
        print(json.dumps({key: value for key, value in report.items() if key != "transfers"}, ensure_ascii=False, indent=1))
        if not report["stable"]:
            print(f"ERROR: the smoothing still moved pixels after {report['passes']} passes; nothing was written")
        if report["rail_segments_lost"]:
            print(f"ERROR: railway segments lost their contact: {report['rail_segments_lost']}")
        return 0 if report["stable"] and not report["rail_segments_lost"] else 1
    if args.dry_run:
        result = dry_run(args.dry_run)
        report = json.dumps(result, ensure_ascii=False, indent=1) + "\n"
        (args.dry_run / DRY_RUN_REPORT).write_text(report, encoding="utf-8")
        for issue in result["issues"]:
            print(f"ERROR: {issue}")
        for path in result["stale_after_second_pass"]:
            print(f"STALE after the second pass: {path}")
        print(f"Dry run in {args.dry_run}: {result['border_margin']} province borders free, report {DRY_RUN_REPORT}.")
        return 1 if result["issues"] or result["stale_after_second_pass"] else 0
    if args.preview:
        for path in write_previews(ROOT, args.preview_dir):
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
    for number in plan.report["unplanned_stages"]:
        print(f"NOTE: the regions of Stage {number} are not planned yet and stay out of the pass")
    if stale or plan.issues:
        return 1
    print(f"MON geography is current: {len(plan.report['rivers'])} rivers, terrain {plan.report['terrain']['totals']}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
