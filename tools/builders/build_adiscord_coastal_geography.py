"""Build bounded coastal, settlement, province-border and mountain geography.

Province geometry and state membership remain authored inputs. Only the explicit
island masks acquire new land; mainland edits use explicit province masks.
"""

from __future__ import annotations

import argparse
import json
import re
from bisect import bisect_right
from collections import defaultdict, deque
from io import BytesIO
from math import atan2, cos, pi, radians, sin
from pathlib import Path

import numpy as np
from PIL import Image
from scipy.ndimage import (
    binary_dilation, binary_fill_holes, distance_transform_edt, find_objects, gaussian_filter, label,
)

from tools.builders.build_adiscord_ivn_geography import (
    RIVER_SEA_PALETTE, RIVER_SOURCE_PALETTE, compact_partition, lattice_noise, native_river_bmp,
    normal_from_height, province_borders, river_width_palette, stable_unit_hash,
)
from tools.builders.build_adiscord_new_states import (
    COUNTRY_DISTRICTS, DISTRICT_CHILDREN, ISLAND_DISTRICTS, ISLAND_TOWNS, NAM_ARCHIPELAGO_ISLANDS,
    NEW_CITY_APPROACHES, REGIONAL_SETTLEMENTS, SOUTHERN_CITIES, SOUTHERN_CITY_APPROACHES, SOUTHERN_CITY_POINTS,
    SOUTHERN_INTERIOR_DISTRICTS, SOUTHERN_RURAL_SPLITS, island_district_provinces, southern_city_rail_route,
    state_file_provinces, state_path,
)
from tools.lib.city_terrains import CITY_TERRAINS, NATIONAL_CITY_CLUSTERS, NATIONAL_CITY_TERRAIN
from tools.lib.coastal_clearance import (
    URBAN_FALLBACK_PALETTE,
    province_colours,
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
ARAB_CITIES = frozenset({16713, 16714, 16715, 16718, 16719, 16720}) | frozenset(
    entry["province"] for entry in SOUTHERN_CITIES if entry["state"] not in {175, 228, 726}
)
# Urban growth authored in Nudge: expanded southern cities and their new
# districts receive city rasters without becoming manifest cities. The
# hand-painted parents and rural sectors of the southern cities Damir, Arsan,
# Rahma, Haret, Sekhvan, Ormis and Veyr are urban as well.
ARAB_URBAN_GROWTH = frozenset({
    488, 971, 1349, 4089, 16745, 16746, 16751, 16753, 16784, 16785, 16786,
    16882, 16883, 16886, 16888, 16889, 16891, 16893, 16894,
    274, 443, 492, 2309, 2504, 3643, 7903,
    16742, 16743, 16744, 16748, 16749, 16750, 16754, 16755, 16756,
    16766, 16767, 16768, 16769, 16770, 16771, 16787, 16788, 16789,
    16796, 16797, 16798,
})
# Arab cities take the combat terrain of their rural surroundings: hill cities
# stand among hills and mountains, desert cities among sand. Cities in forest
# or farmland keep ordinary urban terrain. A multi-province city follows the
# prevailing surroundings of the whole cluster. Every Arab city province is in
# the geometry masks, so the definition pass below writes its terrain field.
ARAB_HILL_CITIES = frozenset({
    16713, 16714, 16715, 16718, 16719, 16727, 16728,
    16729, 16733, 16739, 16897, 16899,
}) | frozenset(
    entry["province"] for entry in SOUTHERN_CITIES
    if entry.get("regional_town") and entry["province"] in ARAB_CITIES
    and entry["parent_terrain"] in {"hills", "mountain"}
)
ARAB_FARMLAND_CITIES = frozenset({7903, 16734, 16735, 16737, 16738, 16787, 16788, 16789}) | frozenset(
    entry["province"] for entry in SOUTHERN_CITIES
    if entry.get("regional_town") and entry["province"] in ARAB_CITIES
    and entry["parent_terrain"] in {"plains", "forest"}
)
ARAB_CITY_TERRAIN = {
    province: "hill_city" if province in ARAB_HILL_CITIES
    else "urban" if province in ARAB_FARMLAND_CITIES
    else "desert_city"
    for province in ARAB_CITIES | ARAB_URBAN_GROWTH
}
# Hand-painted urban provinces of the north use the northern city raster:
# Lower Loren, the Fada centre 145, the outskirts of the state 121 city and the
# separately carved settlement provinces 16689-16705.
URBAN_GROWTH = ARAB_URBAN_GROWTH | frozenset({
    1198, 16881, 16884, 16885, 16887, 16890, 16892, 16900, 16901,
    145, 5245, 16611, 16612,
    16689, 16690, 16691, 16693, 16694, 16696, 16697, 16698, 16699,
    16701, 16702, 16703, 16704, 16705,
})
RURAL_SECTORS = tuple(
    {**sector, "parent": city["parent"], "parent_terrain": city["parent_terrain"], "terrain": city["parent_terrain"]}
    for city in SOUTHERN_CITIES for sector in city.get("sectors", ())
)
SOUTHERN_GEOMETRY = (*SOUTHERN_CITIES, *RURAL_SECTORS, *SOUTHERN_RURAL_SPLITS, *NEW_CITY_APPROACHES, *SOUTHERN_INTERIOR_DISTRICTS)
COUNTRY_DISTRICT_IDS = set(DISTRICT_CHILDREN) | {entry["province"] for entry in COUNTRY_DISTRICTS}
RURAL_SPLIT_PARENTS = {entry["province"]: entry["parent"] for entry in (*SOUTHERN_RURAL_SPLITS, *SOUTHERN_INTERIOR_DISTRICTS)}
# Resolve province corners, short contacts and frontage loops without changing state membership.
# Coordinates use the top-left raster origin.
PROVINCE_PIXEL_REPAIRS = {
    (3971, 1447): (971, 16746),
    (3805, 1171): (10375, 16777),
    (3959, 1034): (834, 16738),
    # Lower Loren: the hand-painted corner of 1198, 627, 16901 and 5926.
    (3704, 1345): (16901, 1198),
    # Keep a three-pixel-wide approach from 6099 to the southern edge of 4287.
    (3674, 1433): (4287, 6099),
    (3675, 1433): (4287, 6099),
    (3676, 1433): (4287, 6099),
    (3674, 1434): (4287, 6099),
    (3675, 1434): (4287, 6099),
    (3676, 1434): (4287, 6099),
    (3674, 1435): (4287, 6099),
    (3675, 1435): (4287, 6099),
    # Yubor: rounded border transitions preserve the authored neighbour graph.
    (3843, 957): (92, 83),
    (3844, 957): (92, 83),
    (3845, 957): (92, 83),
    (3843, 958): (92, 83),
    (3844, 958): (92, 83),
    (3845, 958): (83, 92),
    (3843, 959): (92, 83),
    (3851, 969): (51, 103),
    (3852, 969): (51, 103),
    (3851, 970): (51, 108),
    (3852, 970): (51, 103),
    (3851, 971): (51, 108),
    (3852, 971): (51, 103),
    (3851, 972): (51, 108),
    (3852, 972): (51, 103),
    (3851, 973): (51, 108),
    (3852, 973): (51, 108),
    (3852, 974): (51, 108),
    (3853, 974): (103, 108),
    (3850, 975): (48, 108),
    (3851, 975): (48, 108),
    (3852, 975): (51, 108),
    (3853, 975): (51, 108),
    (3854, 975): (51, 108),
    (3851, 976): (48, 108),
    (3852, 976): (51, 108),
    (3853, 976): (51, 108),
    (3852, 977): (51, 108),
    # Ishait needs separate northern and southern approaches: province 6 must
    # not touch both enemy shoulders around the city and repeat in the front.
    (3848, 984): (6, 51),
    (3844, 985): (6, 51),
    (3845, 985): (6, 51),
    (3846, 985): (6, 51),
    (3847, 985): (6, 51),
    (3848, 985): (6, 51),
    (3842, 986): (6, 16372),
    (3843, 986): (6, 16372),
    (3844, 986): (6, 16372),
    (3845, 986): (6, 16372),
    (3840, 988): (6, 85),
    (3841, 988): (6, 85),
    (3842, 988): (6, 85),
    (3839, 989): (6, 85),
    (3840, 989): (6, 85),
    (3841, 989): (6, 85),
    (3842, 989): (85, 6),
    (3855, 989): (81, 16646),
    (3856, 989): (16646, 81),
    (3857, 989): (16646, 81),
    (3839, 990): (6, 85),
    (3840, 990): (6, 85),
    (3841, 990): (6, 85),
    (3842, 990): (85, 6),
    (3854, 990): (6, 16646),
    (3855, 990): (81, 16646),
    (3856, 990): (81, 16646),
    (3857, 990): (16646, 81),
    (3853, 991): (6, 16646),
    (3857, 991): (88, 16646),
    (3852, 997): (11496, 6),
    (3853, 997): (11496, 88),
    (3850, 998): (127, 88),
    (3852, 998): (11496, 88),
    (3853, 998): (11496, 88),
    (3849, 999): (127, 88),
    (3850, 999): (127, 88),
    (3848, 1000): (11496, 88),
    (3849, 1000): (127, 88),
    (3850, 1000): (127, 88),
    (3851, 1000): (127, 88),
    (3852, 1000): (127, 88),
    (3849, 1001): (127, 88),
    (3850, 1001): (127, 88),
    (3851, 1001): (127, 88),
    (3850, 1002): (127, 88),
    (3835, 1008): (33, 16649),
    (3836, 1008): (7283, 16649),
    (3837, 1008): (7283, 16649),
    (3838, 1008): (7283, 16649),
    (3839, 1008): (7283, 16649),
    (3835, 1009): (16649, 33),
    (3836, 1009): (7283, 16649),
    (3837, 1009): (7283, 16649),
    (3838, 1009): (7283, 16649),
    (3837, 1010): (7283, 16649),
    (3847, 1014): (7283, 127),
    (3847, 1015): (7283, 127),
    (3848, 1015): (7283, 127),
    (3846, 1016): (28, 127),
    (3847, 1016): (28, 127),
    (3848, 1016): (28, 127),
    (3850, 1016): (124, 127),
    (3847, 1017): (28, 127),
    (3848, 1017): (28, 127),
    (3849, 1017): (124, 127),
    (3850, 1017): (124, 127),
    (3851, 1017): (124, 127),
    (3847, 1018): (28, 127),
    (3848, 1018): (124, 127),
    (3849, 1018): (124, 127),
    (3850, 1018): (124, 127),
    (3851, 1018): (124, 127),
    (3849, 1019): (124, 127),
    (3814, 1027): (118, 131),
    (3815, 1027): (118, 131),
    (3816, 1027): (118, 131),
    (3817, 1027): (118, 131),
    (3814, 1028): (131, 118),
    (3815, 1028): (131, 118),
    (3816, 1028): (118, 131),
    (3817, 1028): (118, 131),
    (3814, 1029): (129, 118),
    (3815, 1029): (129, 118),
    (3814, 1030): (129, 118),
    (3815, 1030): (129, 118),
    (3816, 1030): (129, 118),
    (3814, 1031): (129, 118),
    (3815, 1031): (129, 118),
    (3815, 1032): (129, 118),
    # Assign isolated southern pixels to their adjoining provinces.
    (3791, 1502): (729, 16877),
    (3809, 1496): (9633, 16872),
    (3970, 1446): (971, 16746),
    # Connect Zshat across the western edge of Old Zshat with a two-pixel corridor.
    (3122, 1360): (16597, 10926),
    (3122, 1361): (16616, 10926),
    (3123, 1361): (16616, 10926),
    (3122, 1362): (16616, 10926),
    (3123, 1362): (16616, 10926),
    (3123, 1363): (16616, 10926),
}
# A river runs on province borders and never cuts a province apart. Every land
# part a river cut off goes to the province on its own bank. Pixels keep their
# authored surface unless they carry the urban raster into a province without
# city terrain; those sample the recipient surface like the repairs above.
# Where moving land would take a state's coast, buildings or a pinned frontage,
# the river course itself moves onto the border: "river_courses" lists the
# rewritten rivers.bmp pixels (254 sea, 255 land, 0 a moved source).
RIVER_BANK_REPAIRS_PATH = ROOT / "tools/data/adiscord_river_bank_repairs.json"


def load_river_bank_repairs(path: Path) -> tuple[dict[tuple[int, int], tuple[int, int]], frozenset[tuple[int, int]]]:
    repairs = {}
    kept_surface = set()
    for entry in json.loads(path.read_text(encoding="utf-8"))["repairs"]:
        if entry["surface"] not in ("keep", "recipient"):
            raise ValueError(f"river bank {entry['from']}-{entry['to']}: unknown surface {entry['surface']}")
        for x, y in entry["pixels"]:
            if (x, y) in repairs or (x, y) in PROVINCE_PIXEL_REPAIRS:
                raise ValueError(f"river bank pixel {x}, {y} is repaired twice")
            repairs[x, y] = (entry["from"], entry["to"])
            if entry["surface"] == "keep":
                kept_surface.add((x, y))
    return repairs, frozenset(kept_surface)


def load_river_courses(path: Path) -> dict[tuple[int, int], int]:
    courses = {}
    for entry in json.loads(path.read_text(encoding="utf-8"))["river_courses"]:
        for x, y in entry["pixels"]:
            if (x, y) in courses:
                raise ValueError(f"river course pixel {x}, {y} is listed twice")
            courses[x, y] = entry["value"]
    return courses


def load_island_rivers(path: Path) -> tuple[tuple[tuple[int, int], ...], ...]:
    """Read the rivers authored on island districts, each from its source to its mouth."""
    rivers = []
    for entry in json.loads(path.read_text(encoding="utf-8"))["island_rivers"]:
        course = tuple((x, y) for x, y in entry["path"])
        for (x, y), (next_x, next_y) in zip(course, course[1:]):
            if abs(x - next_x) + abs(y - next_y) != 1:
                raise ValueError(f"island river from {course[0]}: the course breaks at {x}, {y}")
        rivers.append(course)
    return tuple(rivers)


RIVER_BANK_REPAIRS, RIVER_BANK_KEPT_SURFACE = load_river_bank_repairs(RIVER_BANK_REPAIRS_PATH)
RIVER_COURSES = load_river_courses(RIVER_BANK_REPAIRS_PATH)
# An island river is a source pixel followed by a course that widens towards
# the mouth. It runs on province-border pixels of the island districts.
ISLAND_RIVERS = load_island_rivers(RIVER_BANK_REPAIRS_PATH)
for river_course in ISLAND_RIVERS:
    for index, pixel in enumerate(river_course):
        if pixel in RIVER_COURSES:
            raise ValueError(f"island river pixel {pixel} is listed twice")
        RIVER_COURSES[pixel] = (
            RIVER_SOURCE_PALETTE if index == 0 else river_width_palette(index / len(river_course), len(river_course))
        )
PROVINCE_PIXEL_REPAIRS.update(RIVER_BANK_REPAIRS)
PROVINCE_REPAIR_PROVINCES = frozenset(
    province for pair in PROVINCE_PIXEL_REPAIRS.values() for province in pair
)
DISPLACED_PROVINCES |= PROVINCE_REPAIR_PROVINCES
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
APPROACH_PROVINCES = {entry[key] for entry in SOUTHERN_CITY_APPROACHES for key in ("province", "parent", "city")}
ANCHOR_REFERENCES.update(RURAL_SPLIT_PARENTS)
DISPLACED_PROVINCES |= APPROACH_PROVINCES
DISPLACED_PROVINCES |= frozenset(RURAL_SPLIT_PARENTS.values())
# Every province whose pixels the southern Nudge pass moved, splits excluded.
NUDGE_SPLIT_DONORS = frozenset({
    461, 729, 971, 1015, 2231, 2374, 2411, 3127, 3584, 3706, 4025, 4089,
    4287, 4321, 4380, 5156, 5305, 5348, 5594, 6099, 6184, 7079, 7413, 7737,
    8452, 8888, 9016, 9119, 9211, 9633, 10967, 11069, 12458, 12668, 13019,
    13248, 13382, 13882, 16745, 16746, 16747, 16752, 16753,
})
DISPLACED_PROVINCES |= NUDGE_SPLIT_DONORS
# Provinces whose borders the hand-painted urban pass moved: the Lower Loren
# cities with their neighbours and the enlarged cores and sectors of Haret,
# Sekhvan, Ormis and Zarkhan. They follow the same anchor rules as the donors.
HAND_PAINTED_PROVINCES = frozenset({
    627, 1198, 1444, 2412, 2504, 3643, 3872, 4478, 5926, 6514, 6847, 7903,
    9402, 10845, 12974, 16730, 16731, 16737, 16766, 16767, 16768, 16769,
    16770, 16771, 16787, 16788, 16789, 16899,
})
DISPLACED_PROVINCES |= HAND_PAINTED_PROVINCES
# Provinces whose pixels or borders the passes above changed. unit_anchors
# reconciles their anchors and those of their neighbours.
ANCHOR_TOUCHED_PROVINCES = (
    frozenset(NUDGE_SPLIT_PARENTS) | NUDGE_SPLIT_DONORS | PROVINCE_REPAIR_PROVINCES | HAND_PAINTED_PROVINCES
    | COUNTRY_DISTRICT_IDS | APPROACH_PROVINCES
    | frozenset(RURAL_SPLIT_PARENTS) | frozenset(RURAL_SPLIT_PARENTS.values())
)
# Districts of the neighbouring island states and the provinces they were cut
# from. They stay in the archipelago scope below: relief, terrain and forests
# follow the generated island surface, and their anchors are reconciled.
ISLAND_DISTRICT_PARENTS = {district["province"]: district["parent"] for district in ISLAND_DISTRICTS}
ISLAND_DISTRICT_PROVINCES = frozenset(ISLAND_DISTRICT_PARENTS)
ISLAND_DISTRICT_SCOPE = ISLAND_DISTRICT_PROVINCES | frozenset(ISLAND_DISTRICT_PARENTS.values())
ISLAND_TOWN_PROVINCES = frozenset(district["province"] for district in ISLAND_TOWNS)
ANCHOR_TOUCHED_PROVINCES |= ISLAND_DISTRICT_SCOPE
# The Svetlogorye archipelago and its neighbouring island states: relief is a
# pure function of position, coastline and the authored river courses, and
# each province takes one terrain from the relief under it. Islands raised
# from the sea join it; an island of several provinces is cut into compact
# parts. A near island is bridged to the island its sea province touches; a
# distant one is reached by sea and, when settled, has a harbour.
ARCHIPELAGO_STATES = (225, 226, 227, 228, 229, 230, 231)
# The neighbours share the relief, terrain, forests and anchor heights. Towns
# and harbours stay with the states whose settlements are authored.
ARCHIPELAGO_NEIGHBOUR_STATES = {
    "FLR": (623, 624, 653, 681, 682, 683, 684, 685),
    "CHD": (672, 673, 674, 675, 676, 677, 678, 679, 680),
    "LUR": (649, 650, 651, 652),
    "ULV": (643, 644, 645, 646, 647, 648),
    "PIV": (232,),
}
# Provinces another pass of this builder shapes keep that treatment.
ARCHIPELAGO_FOREIGN_SCOPES = (
    CITIES | URBAN_GROWTH | RELIEF_SURFACE_PROVINCES | ISLANDS
    | frozenset(COUNTRY_DISTRICT_IDS) | DISPLACED_PROVINCES | PROVINCE_REPAIR_PROVINCES
)
ARCHIPELAGO_NEIGHBOUR_PROVINCES = frozenset().union(
    *(
        state_file_provinces(state_path(state))
        for states in ARCHIPELAGO_NEIGHBOUR_STATES.values()
        for state in states
    )
) - ARCHIPELAGO_FOREIGN_SCOPES
ARCHIPELAGO_NEW_PROVINCES = frozenset(
    part["province"] for island in NAM_ARCHIPELAGO_ISLANDS for part in island["provinces"]
)
ARCHIPELAGO_PROVINCES = ARCHIPELAGO_NEW_PROVINCES.union(
    *(state_file_provinces(state_path(state)) for state in ARCHIPELAGO_STATES)
) | ARCHIPELAGO_NEIGHBOUR_PROVINCES | ISLAND_DISTRICT_PROVINCES
ISLAND_BRIDGE_COMMENT = "nam archipelago island bridge"
# Narrow straits of the Ulven League, bridged between the listed states.
STRAIT_BRIDGES = ((643, 644), (643, 645), (647, 648))
# Surveyed islets a narrow strait away from the rest of their state: (state,
# islet province). Each is bridged to the nearest shore of that state.
ISLET_BRIDGES = ((643, 5943), (643, 5632))
STRAIT_BRIDGE_COMMENT = "ulven league strait bridge"
# Every settlement of the Svetlogorye states, the harbour towns of raised
# islands and the governorate's big-city clusters are city provinces: the
# whole dry area away from the shore band carries the urban texture, city
# models and lights, and the province declares a city terrain. A neighbour
# province already declared as a city keeps its terrain and is painted alike.
ARCHIPELAGO_TOWNS = frozenset(
    province
    for state in ARCHIPELAGO_STATES
    for province, _value, _name in REGIONAL_SETTLEMENTS.get(state, ())
) | frozenset(island["town"]["province"] for island in NAM_ARCHIPELAGO_ISLANDS if "town" in island)
ARCHIPELAGO_CITY_CLUSTERS = frozenset(NATIONAL_CITY_CLUSTERS.get("svetlogorye_town", ())) & ARCHIPELAGO_PROVINCES
ARCHIPELAGO_CITY_TERRAIN = {
    province: NATIONAL_CITY_TERRAIN.get(province, "svetlogorye_town")
    for province in (ARCHIPELAGO_TOWNS | ARCHIPELAGO_CITY_CLUSTERS) & ARCHIPELAGO_PROVINCES
}
# Towns of the neighbouring island states have no national city terrain.
ARCHIPELAGO_CITY_TERRAIN.update({province: "urban" for province in ISLAND_TOWN_PROVINCES})
CITY_BACKGROUND_INDEX = 1
ARCHIPELAGO_PALETTES = {"plains": 0, "forest": 4, "marsh": 9, "hills": 17, "mountain": 20}
ARCHIPELAGO_MOUNTAIN_HEIGHT = 148.0
ARCHIPELAGO_HILL_HEIGHT = 127.0
ARCHIPELAGO_FOREST_SHARE = 0.62
ARCHIPELAGO_TREE_PALETTES = (6, 5)
# A river cuts a valley of this radius; it sinks by a share of its height
# above the shore plus a fixed channel, so lowland rivers stay below their banks.
ARCHIPELAGO_RIVER_RADIUS = 2.5
ARCHIPELAGO_RIVER_DEPTH = 0.45
ARCHIPELAGO_RIVER_CHANNEL = 2.0
ARCHIPELAGO_MIN_HEIGHT = 97
ARCHIPELAGO_MAX_HEIGHT = 180
COLOURMAP =Path("map/terrain/colormap_rgb_cityemissivemask_a.dds")
COLOURMAP_SOURCE = Path("tools/assets/source/map/colormap_rgb_cityemissivemask_a.dds")
SEA_FLOOR_HEIGHT = 89
# Depth is the distance from a pixel to the nearest pixel outside its province.
# The interior centre is the pixel nearest the centroid among those at least
# ANCHOR_CENTRE_DEPTH of the greatest depth deep, so a concave province or one
# around an enclave keeps its army inside. A standing land army (slot 0)
# shallower than CENTRAL_ANCHOR_DEPTH of the greatest depth, or farther from
# the interior centre than the greatest depth itself, is drawn off centre.
ANCHOR_CENTRE_DEPTH = 0.7
CENTRAL_ANCHOR_DEPTH = 0.5
# Slots 0 standstill, 9 attacking, 10 defending, 21 railway-gun standstill and
# 38 victory point stand around the province centre; every other slot leads
# towards one neighbour.
STANDING_SLOTS = frozenset({0, 9, 10, 21, 38})
# Native moving slots face within 0.1 rad of their offset from slot 0.
MOVING_FACING_TOLERANCE = 0.5


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


def archipelago_heights(land: np.ndarray) -> np.ndarray:
    """Raise island interiors into massifs and basins that fall to the shore.

    Broad noise decides where an interior becomes a massif; ridged noise cuts
    it into spurs and valleys. An islet is too narrow to rise far, so it stays
    a low rock. Sea pixels return zero.
    """
    ys, xs = np.nonzero(land)
    crop = np.s_[ys.min() - 2:ys.max() + 3, xs.min() - 2:xs.max() + 3]
    inside = land[crop]
    shore_distance = distance_transform_edt(inside)
    gy, gx = np.mgrid[crop].astype(float)
    massif = np.clip((lattice_noise(gx, gy, 34.0, 71) - 0.3) / 0.45, 0.0, 1.0) ** 1.5
    rise = shore_distance / (shore_distance + 7.0) * (6.0 + 64.0 * massif)
    ridges = 1.0 - np.abs(2.0 * lattice_noise(gx, gy, 9.0, 73) - 1.0)
    grain = (lattice_noise(gx, gy, 4.0, 79) - 0.5) * np.minimum(1.0, shore_distance / 3.0)
    surface = 97.0 + 3.0 * np.minimum(1.0, shore_distance / 2.5) + rise * (0.85 + 0.45 * ridges) + 3.0 * grain
    result = np.zeros(land.shape, dtype=np.uint8)
    result[crop] = np.where(inside, np.clip(np.rint(surface), ARCHIPELAGO_MIN_HEIGHT, ARCHIPELAGO_MAX_HEIGHT), 0)
    return result


def carve_river_valleys(heights: np.ndarray, land: np.ndarray, rivers: np.ndarray) -> np.ndarray:
    """Cut a valley along every river pixel on the given land.

    The rivers stay where rivers.bmp draws them; only the ground around them
    sinks. No land pixel drops below the shore level, so a river never runs
    under the sea surface. Pixels outside the land keep their heights.
    """
    river = land & (rivers < RIVER_SEA_PALETTE)
    if not river.any():
        return heights
    ys, xs = np.nonzero(river)
    margin = int(ARCHIPELAGO_RIVER_RADIUS * 4) + 1
    crop = np.s_[
        max(0, ys.min() - margin):ys.max() + margin + 1,
        max(0, xs.min() - margin):xs.max() + margin + 1,
    ]
    valley = np.exp(-((distance_transform_edt(~river[crop]) / ARCHIPELAGO_RIVER_RADIUS) ** 2))
    level = heights[crop].astype(float)
    above_shore = np.maximum(0.0, level - (ARCHIPELAGO_MIN_HEIGHT + 3))
    cut = valley * (ARCHIPELAGO_RIVER_DEPTH * above_shore + ARCHIPELAGO_RIVER_CHANNEL)
    carved = np.clip(np.rint(level - cut), ARCHIPELAGO_MIN_HEIGHT, ARCHIPELAGO_MAX_HEIGHT).astype(heights.dtype)
    result = heights.copy()
    result[crop] = np.where(land[crop], carved, heights[crop])
    return result


def sea_anchor_pixels(
    unitstacks: bytes, buildings: bytes, shape: tuple[int, int], sea_provinces: set[int], margin: int = 0
) -> np.ndarray:
    """Mark the pixels of every sea unit anchor and floating harbour, with a margin."""
    result = np.zeros(shape, bool)
    rows = [
        fields
        for line in unitstacks.decode("utf-8").splitlines()
        if int((fields := line.split(";"))[0]) in sea_provinces
    ]
    rows += [
        [fields[6], "", fields[2], fields[3], fields[4]]
        for line in buildings.decode("utf-8-sig").splitlines()
        if len(fields := line.split(";")) == 7 and fields[1] == "floating_harbor"
    ]
    for row in rows:
        x = round(float(row[2]))
        y = shape[0] - 1 - round(float(row[4]))
        result[max(0, y - margin):y + margin + 1, max(0, x - margin):x + margin + 1] = True
    return result


def island_mask(shape: tuple[int, int], island: dict) -> np.ndarray:
    """Return an island's rotated, ragged outline as a full-map mask.

    The body is a rotated ellipse; optional lobes, given in the body's own
    axes, add capes and peninsulas. Fine noise frays the shore and coarse
    noise, scaled to the island, cuts bays. Only the largest landmass is kept,
    without lagoons.
    """
    x, y = island["centre"]
    x_radius, y_radius = island["radii"]
    angle = radians(island["angle"])
    salt = island["provinces"][0]["province"]
    lobes = island.get("lobes", ())
    extent = max(
        (max(x_radius, y_radius), *(abs(ox) + max(lx, ly) for ox, _oy, lx, ly in lobes),
         *(abs(oy) + max(lx, ly) for _ox, oy, lx, ly in lobes))
    )
    reach = int(extent * 1.4) + 3
    window = np.s_[y - reach:y + reach + 1, x - reach:x + reach + 1]
    gy, gx = np.mgrid[window].astype(float)
    dx = gx - x
    dy = gy - y
    along = dx * cos(angle) + dy * sin(angle)
    across = dy * cos(angle) - dx * sin(angle)
    outline = (along / x_radius) ** 2 + (across / y_radius) ** 2
    for offset_along, offset_across, lobe_along, lobe_across in lobes:
        lobe = ((along - offset_along) / lobe_along) ** 2 + ((across - offset_across) / lobe_across) ** 2
        outline = np.minimum(outline, lobe)
    coast = 0.55 * (lattice_noise(gx, gy, 3.0, salt) - 0.5)
    coast += 0.9 * (lattice_noise(gx, gy, max(3.0, max(x_radius, y_radius) / 1.6), salt + 1) - 0.5)
    inside = outline + coast <= 1.0
    pieces, count = label(inside)
    if count > 1:
        sizes = np.bincount(pieces.ravel())
        sizes[0] = 0
        inside = pieces == int(sizes.argmax())
    result = np.zeros(shape, bool)
    result[window] = binary_fill_holes(inside)
    return result


def island_provinces(mask: np.ndarray, island: dict) -> np.ndarray:
    """Cut an island into its listed provinces; return their IDs, zero elsewhere."""
    ys, xs = np.nonzero(mask)
    window = np.s_[ys.min() - 1:ys.max() + 2, xs.min() - 1:xs.max() + 2]
    ids = np.array([part["province"] for part in island["provinces"]])
    result = np.zeros(mask.shape, np.int32)
    if len(ids) == 1:
        result[mask] = ids[0]
        return result
    owner = compact_partition(mask[window], len(ids))
    if (owner[mask[window]] < 0).any():
        raise ValueError(f"island {ids[0]}: its outline is not one landmass")
    result[window] = np.where(owner >= 0, ids[np.maximum(owner, 0)], 0)
    return result


def bridge_endpoints(
    grid: np.ndarray, parts: list[int], home: int, sea: int
) -> tuple[tuple[int, int], tuple[int, int]] | None:
    """Return the shortest straight crossing from an island to its home.

    The crossing runs only over its own sea province, so it neither cuts
    across other land nor passes through waters whose fleets cannot block it.
    """
    island = np.isin(grid, parts)
    ys, xs = np.nonzero(island)
    reach = 40
    window = np.s_[max(0, ys.min() - reach):ys.max() + reach + 1, max(0, xs.min() - reach):xs.max() + reach + 1]
    local = grid[window]
    water = local == sea
    start = np.argwhere(island[window] & binary_dilation(water))
    stop = np.argwhere((local == home) & binary_dilation(water))
    if not len(start) or not len(stop):
        return None
    gaps = ((start[:, None, :] - stop[None, :, :]) ** 2).sum(axis=2)
    allowed = {sea, home, *parts}
    for flat in np.argsort(gaps, axis=None, kind="stable")[:400]:
        first, second = np.unravel_index(int(flat), gaps.shape)
        (y0, x0), (y1, x1) = start[first], stop[second]
        steps = int(np.ceil(np.hypot(y1 - y0, x1 - x0) * 3)) + 2
        path_y = np.rint(np.linspace(y0, y1, steps)).astype(int)
        path_x = np.rint(np.linspace(x0, x1, steps)).astype(int)
        if set(np.unique(local[path_y, path_x]).tolist()) <= allowed:
            return (
                (int(y0) + window[0].start, int(x0) + window[1].start),
                (int(y1) + window[0].start, int(x1) + window[1].start),
            )
    return None


def strait_crossing(
    grid: np.ndarray, first: frozenset[int], second: frozenset[int], seas: set[int]
) -> tuple[int, int, int, tuple[int, int], tuple[int, int]]:
    """Return the shortest crossing between two states over one sea province.

    The result names both shore provinces, the sea province between them and
    the two shore pixels.
    """
    water = binary_dilation(np.isin(grid, list(seas)))
    start = np.argwhere(np.isin(grid, list(first)) & water)
    stop = np.argwhere(np.isin(grid, list(second)) & water)
    gaps = ((start[:, None, :] - stop[None, :, :]) ** 2).sum(axis=2)
    for flat in np.argsort(gaps, axis=None, kind="stable")[:400]:
        index, other = np.unravel_index(int(flat), gaps.shape)
        (y0, x0), (y1, x1) = start[index], stop[other]
        steps = int(np.ceil(np.hypot(y1 - y0, x1 - x0) * 3)) + 2
        path = grid[
            np.rint(np.linspace(y0, y1, steps)).astype(int), np.rint(np.linspace(x0, x1, steps)).astype(int)
        ]
        crossed = set(np.unique(path).tolist()) - {int(grid[y0, x0]), int(grid[y1, x1])}
        if len(crossed) == 1 and crossed <= seas:
            return int(grid[y0, x0]), int(grid[y1, x1]), crossed.pop(), (int(y0), int(x0)), (int(y1), int(x1))
    raise ValueError("strait bridge: no crossing over a single sea province")


def island_bridges(original: bytes, grid: np.ndarray, seas: set[int]) -> bytes:
    """Bridge every near raised island to its home island across the sea around it."""
    text = original.decode("utf-8-sig")
    newline = "\r\n" if "\r\n" in text else "\n"
    lines = [
        line for line in text.splitlines()
        if not line.endswith((ISLAND_BRIDGE_COMMENT, STRAIT_BRIDGE_COMMENT))
    ]
    tail = [lines.pop()] if lines and lines[-1].startswith("-1;") else []
    map_height = grid.shape[0]
    for island in NAM_ARCHIPELAGO_ISLANDS:
        # A distant island has no bridge; it is reached by sea.
        if not island["bridge"]:
            continue
        parts = [part["province"] for part in island["provinces"]]
        endpoints = bridge_endpoints(grid, parts, island["home"], island["sea"])
        if endpoints is None:
            raise ValueError(f"island {parts[0]}: no crossing to {island['home']} stays over sea province {island['sea']}")
        (y0, x0), (y1, x1) = endpoints
        province = int(grid[y0, x0])
        lines.append(
            f"{province};{island['home']};sea;{island['sea']};{x0};{map_height - 1 - y0};"
            f"{x1};{map_height - 1 - y1};;{ISLAND_BRIDGE_COMMENT}"
        )
    def surveyed(state: int) -> frozenset[int]:
        # Districts belong to their state before its province list names them.
        members = state_file_provinces(state_path(state)) | island_district_provinces(state)
        return members - ARCHIPELAGO_NEW_PROVINCES

    crossings = [(surveyed(first), surveyed(second)) for first, second in STRAIT_BRIDGES]
    crossings += [(frozenset({islet}), surveyed(state) - {islet}) for state, islet in ISLET_BRIDGES]
    for first, second in crossings:
        start, stop, sea, (y0, x0), (y1, x1) = strait_crossing(grid, first, second, seas)
        lines.append(
            f"{start};{stop};sea;{sea};{x0};{map_height - 1 - y0};{x1};{map_height - 1 - y1};;{STRAIT_BRIDGE_COMMENT}"
        )
    return (newline.join([*lines, *tail]) + newline).encode("utf-8")


def check_island_rivers(rivers: np.ndarray, grid: np.ndarray, sea: np.ndarray) -> None:
    """Reject an island river off the district borders and a town on a river.

    An island river runs over province-border pixels of island district land
    and its last pixel touches the sea. No island town carries a river pixel:
    a river beside a town lies on the opposite bank.
    """
    border = province_borders(grid)
    land = np.isin(grid, list(ISLAND_DISTRICT_SCOPE - ISLAND_TOWN_PROVINCES))
    for course in ISLAND_RIVERS:
        xs, ys = np.array(course).T
        if not (land[ys, xs] & border[ys, xs]).all():
            raise ValueError(f"island river from {course[0]}: it leaves the district borders")
        x, y = course[-1]
        if not (sea[y - 1, x] or sea[y + 1, x] or sea[y, x - 1] or sea[y, x + 1]):
            raise ValueError(f"island river from {course[0]}: its mouth at {x}, {y} is not on the coast")
    towns = np.isin(grid, list(ISLAND_TOWN_PROVINCES))
    if (towns & (rivers < RIVER_SEA_PALETTE)).any():
        raise ValueError("an island town covers a river pixel")


def archipelago_terrain(
    grid: np.ndarray, heights: np.ndarray, boxes: list, city_terrain: dict[int, str]
) -> dict[int, str]:
    """Give each island province the terrain of the relief under it.

    City provinces take their entry in `city_terrain` instead.
    """
    result = {}
    for province in sorted(ARCHIPELAGO_PROVINCES):
        if province in city_terrain:
            result[province] = city_terrain[province]
            continue
        box = boxes[province - 1] if province <= len(boxes) else None
        if box is None:
            raise ValueError(f"archipelago province {province}: no pixels on the province map")
        inside = grid[box] == province
        ys, xs = np.nonzero(inside)
        level = float(heights[box][inside].mean())
        x = float(xs.mean()) + box[1].start
        y = float(ys.mean()) + box[0].start
        moisture = float(lattice_noise(np.array([x]), np.array([y]), 38.0, 83)[0])
        if level >= ARCHIPELAGO_MOUNTAIN_HEIGHT:
            result[province] = "mountain"
        elif level >= ARCHIPELAGO_HILL_HEIGHT:
            result[province] = "hills"
        elif moisture >= 0.72 and level < 104.5:
            result[province] = "marsh"
        elif moisture >= 0.5:
            result[province] = "forest"
        else:
            result[province] = "plains"
    return result


def archipelago_trees(pixels: np.ndarray, forest: np.ndarray, land: np.ndarray) -> None:
    """Plant the island forests and clear the tree cells of other island land."""
    height, width = pixels.shape
    ys, xs = np.nonzero(land)
    tx0, tx1 = xs.min() * width // land.shape[1], xs.max() * width // land.shape[1]
    ty0, ty1 = ys.min() * height // land.shape[0], ys.max() * height // land.shape[0]
    for ty in range(ty0, ty1 + 1):
        y = (2 * ty + 1) * land.shape[0] // (2 * height)
        for tx in range(tx0, tx1 + 1):
            x = (2 * tx + 1) * land.shape[1] // (2 * width)
            if not land[y, x]:
                continue
            planted = forest[y, x] and stable_unit_hash(tx, ty, 23) < ARCHIPELAGO_FOREST_SHARE
            pixels[ty, tx] = ARCHIPELAGO_TREE_PALETTES[stable_unit_hash(tx, ty, 29) >= 0.65] if planted else 0


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


def exclusion_zone_provinces(root: Path) -> set[int]:
    provinces = set()
    for path in (root / "history/states").glob("*.txt"):
        source = path.read_text(encoding="utf-8-sig")
        owner = re.search(r"(?m)^\s*owner\s*=\s*([A-Z0-9]{3})\b", source)
        if owner and owner.group(1) == "EXZ":
            provinces.update(state_file_provinces(path))
    return provinces


def build_colourmap(
    base: bytes, islands: np.ndarray, unlit: np.ndarray, terrain: bytes, cities: bytes,
) -> bytes:
    """Count lit settlement pixels in each 2x2 map cell."""
    colourmap = patch_colourmap(base, islands)
    with Image.open(BytesIO(terrain)) as ground, Image.open(BytesIO(cities)) as buildings:
        for raster in (ground, buildings):
            if raster.mode != "P" or raster.size != islands.shape[::-1]:
                raise ValueError("city lights require indexed terrain and city rasters matching provinces.bmp")
        # Indices 2 and 15 mark settlements. Index 1 covers the city map background.
        footprint = ((np.asarray(ground) == 13) | np.isin(np.asarray(buildings), (2, 15))) & ~unlit
    height, width = islands.shape[0] // 2, islands.shape[1] // 2
    coverage = footprint.reshape(height, 2, width, 2).sum(axis=(1, 3), dtype=np.uint8)
    # BC3 endpoints 64 and 224 give the palette 64, 224, 96, 128, 160,
    # 192, 0, 255. All five possible coverage levels have an exact entry.
    selectors = np.array([6, 0, 3, 5, 7], dtype=np.uint8)[coverage]
    tiles = selectors.reshape(height // 4, 4, width // 4, 4)
    tiles = tiles.transpose(0, 2, 1, 3).reshape(-1, 16)
    packed = np.zeros(len(tiles), dtype=np.uint64)
    for pixel in range(16):
        packed |= tiles[:, pixel].astype(np.uint64) << (3 * pixel)

    # Only the first eight bytes of each block carry alpha. Keep the
    # compressed daylight colours, including island tints, byte for byte.
    result = bytearray(colourmap)
    blocks = np.frombuffer(result, dtype=np.uint8, offset=128).reshape(-1, 16)
    blocks[:, :2] = (64, 224)
    blocks[:, 2:8] = packed.astype("<u8", copy=False).view(np.uint8).reshape(-1, 8)[:, :6]
    return bytes(result)


def current_colourmap_plan(root: Path = ROOT) -> dict[Path, bytes]:
    definition = (root / "map/definition.csv").read_bytes()
    with Image.open(root / "map/provinces.bmp") as source:
        provinces = np.asarray(source.convert("RGB"))
    islands = water_mask(provinces, province_colours(definition, ISLANDS | ARCHIPELAGO_NEW_PROVINCES))
    unlit_colours = water_colours(definition) | province_colours(definition, exclusion_zone_provinces(root))
    colourmap = build_colourmap(
        (root / COLOURMAP_SOURCE).read_bytes(), islands, water_mask(provinces, unlit_colours),
        (root / "map/terrain.bmp").read_bytes(), (root / "map/cities.bmp").read_bytes(),
    )
    return {COLOURMAP: colourmap}


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


def province_interior(
    grid: np.ndarray, province: int, box: tuple[slice, slice],
) -> tuple[int, int, np.ndarray, np.ndarray, tuple[int, int]]:
    """Return the window origin, province mask, depth and interior centre (x, y).

    The window keeps a one-pixel margin around the province bounding box.
    """
    origin_y = max(box[0].start - 1, 0)
    origin_x = max(box[1].start - 1, 0)
    inside = grid[origin_y:box[0].stop + 1, origin_x:box[1].stop + 1] == province
    # Zero padding makes the map edge a border as well.
    depth = distance_transform_edt(np.pad(inside, 1))[1:-1, 1:-1]
    ys, xs = np.nonzero(inside)
    deep_y, deep_x = np.nonzero(depth >= ANCHOR_CENTRE_DEPTH * depth.max())
    nearest = int(np.argmin((deep_x - xs.mean()) ** 2 + (deep_y - ys.mean()) ** 2))
    centre = (int(deep_x[nearest]) + origin_x, int(deep_y[nearest]) + origin_y)
    return origin_y, origin_x, inside, depth, centre


def standing_anchor_central(row: list[str], grid: np.ndarray, interior: tuple) -> bool:
    origin_y, origin_x, inside, depth, (centre_x, centre_y) = interior
    x = round(float(row[2]))
    y = grid.shape[0] - 1 - round(float(row[4]))
    local_y, local_x = y - origin_y, x - origin_x
    if not (0 <= local_y < inside.shape[0] and 0 <= local_x < inside.shape[1] and inside[local_y, local_x]):
        return False
    greatest = depth.max()
    deep_enough = depth[local_y, local_x] >= CENTRAL_ANCHOR_DEPTH * greatest
    return bool(deep_enough and np.hypot(x - centre_x, y - centre_y) <= greatest)


def border_contacts(
    grid: np.ndarray, province: int, box: tuple[slice, slice], interior: tuple,
) -> list[tuple[int, float, float]]:
    """Return each pixel neighbour with its mean contact pixel (x, y) in moving-slot order.

    The engine indexes moving slots by the order in which a scan of
    provinces.bmp, stored bottom row first, meets each neighbour: the earlier
    pixel of the first contact pair, read bottom-up and left to right. A tie
    goes to the lower province ID.
    """
    origin_y, origin_x, inside, _depth, _centre = interior
    window = grid[origin_y:box[0].stop + 1, origin_x:box[1].stop + 1]
    map_height, map_width = grid.shape
    rows = np.arange(window.shape[0]) + origin_y
    columns = np.arange(window.shape[1]) + origin_x
    pairs = (
        (window[:, :-1], window[:, 1:], rows[:, None], columns[None, :-1]),
        # The lower pixel of a vertical pair comes first in the scan.
        (window[:-1], window[1:], rows[1:, None], columns[None, :]),
    )
    first_contact = {}
    for first, second, row, column in pairs:
        contact = (first == province) != (second == province)
        other = np.where(first == province, second, first)
        scan = np.broadcast_to((map_height - 1 - row) * map_width + column, contact.shape)
        for neighbour, position in zip(other[contact].tolist(), scan[contact].tolist()):
            if neighbour not in first_contact or position < first_contact[neighbour]:
                first_contact[neighbour] = position
    padded = np.pad(window, 1)
    contacts = []
    for neighbour in sorted(first_contact, key=lambda neighbour: (first_contact[neighbour], neighbour)):
        touching = inside & (
            (padded[:-2, 1:-1] == neighbour) | (padded[2:, 1:-1] == neighbour)
            | (padded[1:-1, :-2] == neighbour) | (padded[1:-1, 2:] == neighbour)
        )
        ys, xs = np.nonzero(touching)
        contacts.append((neighbour, float(xs.mean()) + origin_x, float(ys.mean()) + origin_y))
    return contacts


def moving_anchors_native(
    anchors: dict[int, list[str]], contacts: list[tuple[int, float, float]], map_height: int,
) -> bool:
    """Check that each moving slot lies towards its neighbour and faces away from the standing army."""
    if 0 not in anchors:
        return False
    centre_x = round(float(anchors[0][2]))
    centre_y = map_height - 1 - round(float(anchors[0][4]))
    for slot, (_neighbour, contact_x, contact_y) in enumerate(contacts[:8], 1):
        if slot not in anchors:
            return False
        dx = float(anchors[slot][2]) - centre_x
        dy = map_height - 1 - float(anchors[slot][4]) - centre_y
        if np.hypot(dx, dy) < 1:
            continue
        towards = dx * (contact_x - centre_x) + dy * (contact_y - centre_y) >= 0
        error = (float(anchors[slot][5]) - atan2(dx, dy) + pi) % (2 * pi) - pi
        if not towards or abs(error) > MOVING_FACING_TOLERANCE:
            return False
    return True


def complete_native_anchors(
    province: int,
    kind: str,
    existing: dict[int, list[str]],
    grid: np.ndarray,
    heights: np.ndarray,
    interior: tuple,
    contacts: list[tuple[int, float, float]],
    offset: str | None = None,
) -> dict[int, list[str]]:
    """Keep valid rows of a native slot set and add the slots its borders now need."""
    origin_y, origin_x, inside, _depth, centre = interior
    points = np.argwhere(inside) + (origin_y, origin_x)
    map_height = heights.shape[0]
    if 0 in existing:
        x = round(float(existing[0][2]))
        y = map_height - 1 - round(float(existing[0][4]))
        if grid[y, x] == province:
            centre = (x, y)
    cx, cy = centre
    if offset is None:
        offset = existing[0][6] if 0 in existing else ("0.12" if kind == "sea" else "0.24")

    def row(slot: int, x: float, y: float, rotation: float) -> list[str]:
        x, y = closest_pixel(points, x, y)
        return [str(province), str(slot), f"{x:.2f}", f"{heights[y, x] / 10:.2f}",
                f"{map_height - 1 - y:.2f}", f"{rotation:.2f}", offset]

    generated = {0: row(0, cx, cy, 0.0), 9: row(9, cx - 3, cy, 1.57), 10: row(10, cx + 3, cy, -1.57),
                 21: row(21, cx - 3, cy, 0.0)}
    generated[38] = list(generated[10])
    generated[38][1] = "38"
    for index, (_neighbour, contact_x, contact_y) in enumerate(contacts[:8], 1):
        dx = contact_x - cx
        dy = contact_y - cy
        length = max(float(np.hypot(dx, dy)), 1.0)
        x, y = closest_pixel(points, cx + 3 * dx / length, cy + 3 * dy / length)
        # A moving army faces from the centre to its own slot. With pixel rows
        # growing southwards, rotation 0 faces south and pi / 2 faces east.
        if (x, y) != (cx, cy):
            dx, dy = x - cx, y - cy
        generated[index] = row(index, x, y, atan2(dx, dy))
        for base in (22, 11, 30):
            copy = list(generated[index])
            copy[1] = str(base + index - 1)
            generated[base + index - 1] = copy
    return {
        slot: existing[slot] if slot in existing else generated[slot]
        for slot in sorted(native_slots(kind, len(contacts)))
    }


def unit_anchors(
    original: bytes,
    points: dict[int, np.ndarray],
    heights: np.ndarray,
    grid: np.ndarray,
    kinds: dict[int, str],
) -> bytes:
    """Keep native unit anchors inside their provinces.

    A province has slots 0, 9, 10, 21 and 38 plus up to eight slots per border
    row (two rows on land, four at sea), sized by its neighbour count. A slot
    set copied from another province or left over from an older border is
    unsafe at game start, so every province around the southern Nudge and
    hand-painted passes keeps its valid rows, loses slots for borders it no
    longer has and gains the slots its new borders need. A province moved
    wholesale keeps no anchor inside its pixels and receives a fresh native
    set. A land province of this pass or one of its neighbours whose standing
    anchor lies outside its pixels, on a border or away from its interior
    centre receives a fresh set around that centre and keeps its model offset;
    so does a sea province whose standing anchor lies outside its pixels.
    Any other province of that scope whose moving slots do not lead towards
    their neighbours in the engine's order keeps its standing slots and has
    the rest rebuilt. Rows stay grouped by slot type in the native order.
    """
    rows = [line.split(";") for line in original.decode("utf-8").splitlines()]
    neighbours = province_neighbours(grid)
    slots = defaultdict(dict)
    for row in rows:
        slots[int(row[0])][int(row[1])] = row
    # A city carved without rural sectors has no anchors yet: it receives a
    # native set, and its parent (a neighbour here) gains the new border slots.
    touched = set(ANCHOR_TOUCHED_PROVINCES) | {province for province in points if province not in slots}
    scope = touched | {neighbour for province in touched for neighbour in neighbours[province]}
    map_height = heights.shape[0]

    def anchor_inside(province: int, row: list[str]) -> bool:
        return grid[map_height - 1 - round(float(row[4])), round(float(row[2]))] == province

    relocated = {
        province for province in touched & points.keys()
        if slots[province] and not any(anchor_inside(province, row) for row in slots[province].values())
    }
    boxes = find_objects(grid)
    interiors = {}
    contacts = {}

    def shape(province: int) -> tuple[tuple, list[tuple[int, float, float]]]:
        if province not in interiors:
            interiors[province] = province_interior(grid, province, boxes[province - 1])
            contacts[province] = border_contacts(grid, province, boxes[province - 1], interiors[province])
        return interiors[province], contacts[province]

    # Snapping a stray anchor to the nearest pixel leaves the army on the border
    # it crossed, so the whole set moves to the interior instead. A fleet whose
    # water became island land stands outside its province in the same way.
    owned = scope | DISPLACED_PROVINCES | set(ANCHOR_REFERENCES)

    def standing_off_centre(province: int) -> bool:
        if kinds.get(province) == "sea":
            return not anchor_inside(province, slots[province][0])
        if kinds.get(province) != "land":
            return False
        return not standing_anchor_central(slots[province][0], grid, shape(province)[0])

    centred = {province for province in owned if 0 in slots.get(province, {}) and standing_off_centre(province)}
    # Moving rows copied from a parent, kept from an older border or ordered
    # by province ID draw a moving army at the wrong border; they are rebuilt
    # around the province's own standing slots.
    misdirected = {
        province for province in owned - centred
        if kinds.get(province) in ("land", "sea") and slots.get(province)
        and not moving_anchors_native(slots[province], shape(province)[1], map_height)
    }
    rebuilt = {}
    for province in sorted(scope | centred | misdirected):
        kind = kinds.get(province)
        if kind not in ("land", "sea"):
            continue
        fresh = province in relocated or province in centred
        if (set(slots[province]) == native_slots(kind, len(neighbours[province]))
                and not fresh and province not in misdirected):
            continue
        if fresh:
            existing = {}
        elif province in misdirected:
            existing = {slot: row for slot, row in slots[province].items() if slot in STANDING_SLOTS}
        else:
            existing = slots[province]
        rebuilt[province] = complete_native_anchors(
            province, kind, existing, grid, heights, *shape(province),
            offset=slots[province][0][6] if province in centred else None,
        )

    def normalise(row: list[str]) -> list[str]:
        province = int(row[0])
        if (province in DISPLACED_PROVINCES or province in ANCHOR_REFERENCES or province in COUNTRY_DISTRICT_IDS
                or province in ISLAND_DISTRICT_SCOPE):
            x = float(row[2])
            y = map_height - 1 - float(row[4])
            # Half-pixel anchors must resolve to the province under both
            # truncation and rounding.
            if grid[round(y), round(x)] != province or grid[int(y), int(x)] != province:
                x, y = closest_pixel(points[province], x, y)
                row[2:5] = [f"{x:.2f}", f"{heights[y, x] / 10:.2f}", f"{map_height - 1 - y:.2f}"]
        if province in RELIEF_PROVINCES or province in ARCHIPELAGO_PROVINCES:
            x = round(float(row[2]))
            y = map_height - 1 - round(float(row[4]))
            # An anchor over water keeps the sea surface, not the seabed.
            if grid[y, x] == province:
                row[3] = f"{heights[y, x] / 10:.2f}"
        return row

    blocks = defaultdict(list)
    for row in rows:
        if int(row[0]) not in rebuilt:
            blocks[int(row[1])].append(normalise(row))
    additions = defaultdict(list)
    for province, anchors in rebuilt.items():
        for slot, row in anchors.items():
            additions[slot].append((province, normalise(list(row))))
    for slot, rows_to_add in additions.items():
        block = blocks[slot]
        # Nudge preserves a few out-of-order rows. Insert before the first
        # larger ID without disturbing their original order.
        prefix = np.maximum.accumulate([int(row[0]) for row in block]).tolist() if block else []
        merged = []
        start = 0
        for province, row in rows_to_add:
            index = bisect_right(prefix, province)
            merged.extend(block[start:index])
            merged.append(row)
            start = index
        merged.extend(block[start:])
        blocks[slot] = merged
    newline = "\r\n" if b"\r\n" in original else "\n"
    ordered = [";".join(row) for slot in sorted(blocks) for row in blocks[slot]]
    return (newline.join(ordered) + newline).encode("utf-8")


def railway_plan(original: bytes, provinces: np.ndarray, definitions: dict[int, tuple[int, int, int]]) -> bytes:
    """Insert local sector crossings while preserving existing railway levels."""
    groups = {}
    for city in SOUTHERN_CITIES:
        members = {city["parent"], city["province"], *(sector["province"] for sector in city.get("sectors", ()))}
        # A parent carved twice keeps the crossings of both families.
        for province in members:
            groups[province] = groups.get(province, set()) | members
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
        route = southern_city_rail_route(tuple(fields[2:]))
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
        if repaired == fields[2:]:
            result.append(line)
        else:
            ending = "\r\n" if line.endswith("\r\n") else "\n" if line.endswith("\n") else ""
            result.append(" ".join(map(str, (fields[0], len(repaired), *repaired))) + ending)
    return "".join(result).encode("utf-8")


def repair_surface_references(grid: np.ndarray) -> dict[tuple[int, int], tuple[int, int]]:
    """Sample unchanged recipient pixels so border repairs preserve local surface styles."""
    references = {}
    recipients = {replacement for _original, replacement in PROVINCE_PIXEL_REPAIRS.values()}
    for province in sorted(recipients - RELIEF_SURFACE_PROVINCES):
        mask = grid == province
        for x, y in PROVINCE_PIXEL_REPAIRS:
            mask[y, x] = False
        points = np.argwhere(mask)
        if not len(points):
            raise ValueError(f"province {province}: no unchanged surface reference")
        for (x, y), (_original, replacement) in PROVINCE_PIXEL_REPAIRS.items():
            if replacement == province and (x, y) not in RIVER_BANK_KEPT_SURFACE:
                references[x, y] = closest_pixel(points, x, y)
    return references


def province_border_count(grid: np.ndarray) -> int:
    """Count distinct contact curves, including coastlines and the horizontal seam."""
    from scipy.sparse import coo_matrix
    from scipy.sparse.csgraph import connected_components

    width = grid.shape[1]
    starts = []
    ends = []
    for vertical in (False, True):
        if vertical:
            first, second = grid, np.roll(grid, 1, axis=1)
        else:
            first, second = grid[:-1], grid[1:]
        y, x = np.nonzero(first != second)
        low = np.minimum(first[y, x], second[y, x]).astype(np.int64)
        high = np.maximum(first[y, x], second[y, x]).astype(np.int64)
        # Give vertices of each unordered pair a separate namespace. Two
        # disjoint contacts between the same provinces then count separately.
        pair = ((low << 16) | high) << 32
        vertex = (y if vertical else y + 1) * width
        starts.append(pair | (vertex + x))
        ends.append(pair | (vertex + width + x if vertical else vertex + (x + 1) % width))
    nodes, inverse = np.unique(np.concatenate([*starts, *ends]), return_inverse=True)
    first, second = np.split(inverse, 2)
    graph = coo_matrix((np.ones(len(first), dtype=np.uint8), (first, second)), shape=(len(nodes), len(nodes)))
    count = connected_components(graph, directed=False, return_labels=False)
    # At a diagonal pixel contact distinct curves can touch at one vertex.
    # Counting every extra pair of arms is conservative at these junctions.
    degrees = np.bincount(inverse, minlength=len(nodes))
    return int(count + np.maximum(degrees - 2, 0).sum())


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
    for entry in (*SOUTHERN_GEOMETRY, *COUNTRY_DISTRICTS):
        parent_index = entries_by_id[entry["parent"]]
        fields = definition_lines[parent_index].split(";")
        if "parent_terrain" in entry:
            fields[6] = entry["parent_terrain"]
        # Island terrain follows the generated relief, province by province.
        elif entry["state"] not in ARCHIPELAGO_STATES and fields[6] != entry["terrain"]:
            raise ValueError(f"rural province {entry['province']}: parent terrain differs from the split")
        definition_lines[parent_index] = ";".join(fields)
        province = entry["province"]
        if province not in entries_by_id:
            if province != max(entries_by_id) + 1:
                raise ValueError(f"province {province}: non-contiguous southern city ID")
            entries_by_id[province] = len(definition_lines)
            definition_lines.append(";".join(map(str, (province, *entry["rgb"], "land", "false", entry.get("terrain", "urban"), fields[7]))))
        elif tuple(map(int, definition_lines[entries_by_id[province]].split(";")[1:4])) != tuple(entry["rgb"]):
            raise ValueError(f"province {province}: city ID is occupied by another color")
    for island in NAM_ARCHIPELAGO_ISLANDS:
        continent = definition_lines[entries_by_id[island["home"]]].split(";")[7]
        for part in island["provinces"]:
            province = part["province"]
            if province not in entries_by_id:
                if province != max(entries_by_id) + 1:
                    raise ValueError(f"province {province}: non-contiguous island ID")
                entries_by_id[province] = len(definition_lines)
                definition_lines.append(";".join(map(str, (province, *part["rgb"], "land", "true", "plains", continent))))
            elif tuple(map(int, definition_lines[entries_by_id[province]].split(";")[1:4])) != tuple(part["rgb"]):
                raise ValueError(f"province {province}: island ID is occupied by another color")
    for district in ISLAND_DISTRICTS:
        province = district["province"]
        if province not in entries_by_id:
            if province != max(entries_by_id) + 1:
                raise ValueError(f"province {province}: non-contiguous island district ID")
            parent = definition_lines[entries_by_id[district["parent"]]].split(";")
            entries_by_id[province] = len(definition_lines)
            # The coastal flag and the terrain are set from the final geometry below.
            definition_lines.append(";".join(map(str, (province, *district["rgb"], "land", "false", parent[6], parent[7]))))
        elif tuple(map(int, definition_lines[entries_by_id[province]].split(";")[1:4])) != tuple(district["rgb"]):
            raise ValueError(f"province {province}: island district ID is occupied by another color")
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
    # Surface and city masks belong to the original geography. Restore district
    # pixels locally before painting that layer, then apply rural boundaries last.
    previous = province_grid(provinces, {e["province"]: definitions[e["province"]] for e in COUNTRY_DISTRICTS})
    restore = previous != 0
    colours = np.zeros((max(definitions) + 1, 3), dtype=np.uint8)
    for entry in COUNTRY_DISTRICTS:
        colours[entry["province"]] = definitions[entry["parent"]]
    provinces[restore] = colours[previous[restore]]
    country_masks = []
    for entry in COUNTRY_DISTRICTS:
        x, y = entry["origin"]
        mask = np.array([list(row) for row in entry["mask"]]) == "1"
        window = np.s_[y:y + mask.shape[0], x:x + mask.shape[1]]
        country_masks.append((entry, mask, window))
    stamped = (*SOUTHERN_GEOMETRY, *(area for area in SOUTHERN_CITY_APPROACHES if "rgb" not in area), *ISLAND_DISTRICTS)
    for entry in stamped:
        left, top = entry["origin"]
        for y, row in enumerate(entry["mask"], top):
            for x, selected_pixel in enumerate(row, left):
                if selected_pixel != "1":
                    continue
                permitted = {definitions[entry["parent"]], definitions[entry["province"]]}
                if (x, y) in PROVINCE_PIXEL_REPAIRS:
                    permitted.add(definitions[PROVINCE_PIXEL_REPAIRS[x, y][1]])
                if tuple(provinces[y, x]) not in permitted:
                    raise ValueError(f"carved province {entry['province']}: geometry changed at {x}, {y}")
                provinces[y, x] = definitions[entry["province"]]
    for (x, y), (original, replacement) in PROVINCE_PIXEL_REPAIRS.items():
        if tuple(provinces[y, x]) not in (definitions[original], definitions[replacement]):
            raise ValueError(f"province repair source changed at {x}, {y}")
        provinces[y, x] = definitions[replacement]
    raised = np.zeros(provinces.shape[:2], bool)
    colour_table = np.zeros((max(definitions) + 1, 3), dtype=np.uint8)
    for province, colour in definitions.items():
        colour_table[province] = colour
    sea_provinces = {int(line.split(";")[0]) for line in definition_lines if line.split(";")[4] == "sea"}
    anchors = sea_anchor_pixels(
        read(Path("map/unitstacks.txt")), read(Path("map/buildings.txt")), raised.shape, sea_provinces
    )
    for island in NAM_ARCHIPELAGO_ISLANDS:
        mask = island_mask(raised.shape, island)
        parts = island_provinces(mask, island)
        allowed = [definitions[island["sea"]], *(definitions[part["province"]] for part in island["provinces"])]
        # An island may only rise from open water of its own sea province,
        # clear of the fleet and floating-harbour anchors drawn there.
        if not np.isin(provinces[mask], allowed).all() or (raised & mask).any():
            raise ValueError(f"island {parts[mask][0]}: its site is no longer open water of sea province {island['sea']}")
        if (mask & anchors).any():
            raise ValueError(f"island {parts[mask][0]}: it would cover a sea anchor")
        provinces[mask] = colour_table[parts[mask]]
        raised |= mask
        sea_left = np.all(provinces == definitions[island["sea"]], axis=2)
        if label(sea_left)[1] != 1:
            raise ValueError(f"sea province {island['sea']}: an island would split it")
    selected = (
        set(ANCHOR_REFERENCES) | DISPLACED_PROVINCES | CITIES | URBAN_GROWTH | RELIEF_SURFACE_PROVINCES
        | ARCHIPELAGO_NEW_PROVINCES | ISLAND_DISTRICT_SCOPE
    )
    grid = province_grid(provinces, definitions)
    # Keep local pixel coordinates for anchor placement. A full world mask for each
    # rural subdivision would scale memory with both map area and province count.
    boxes = find_objects(grid)
    points = {}
    for province in selected:
        box = boxes[province - 1] if province <= len(boxes) else None
        if box is None:
            raise ValueError(f"province {province}: empty coastal geometry")
        points[province] = np.argwhere(grid[box] == province) + (box[0].start, box[1].start)
    surface_references = repair_surface_references(grid)
    islands = np.isin(grid, list(ISLANDS))
    cities = np.isin(grid, list(CITIES | URBAN_GROWTH))
    arab_cities = np.isin(grid, list(ARAB_CITIES | ARAB_URBAN_GROWTH))
    mountains = np.isin(grid, list(RELIEF_SURFACE_PROVINCES))
    with Image.open(root / "map/heightmap.bmp") as source:
        mountain_heightmap = mountain_heights(mountains, np.array(source))
    outputs = {}
    surface_grid = grid
    grid = surface_grid.copy()
    for entry, mask, window in country_masks:
        if not np.all(grid[window][mask] == entry["parent"]):
            raise ValueError(f"rural district {entry['province']}: parent footprint changed")
        grid[window][mask] = entry["province"]
        provinces[window][mask] = definitions[entry["province"]]
    border_count = province_border_count(grid)
    if border_count > 65_536:
        raise ValueError(f"province borders exceed the display limit: {border_count:,} / 65,536")
    boxes = find_objects(grid)
    for province in COUNTRY_DISTRICT_IDS:
        box = boxes[province - 1]
        if box is None:
            raise ValueError(f"province {province}: empty rural district")
        points[province] = np.argwhere(grid[box] == province) + (box[0].start, box[1].start)
    # Archipelago: Svetlogorye towns and cities take their city terrain; a
    # neighbour province declared as a city keeps it. Every other province
    # follows the relief.
    archipelago = np.isin(grid, list(ARCHIPELAGO_PROVINCES))
    declared_terrain = {int(fields[0]): fields[6] for line in definition_lines if len(fields := line.split(";")) >= 8}
    city_terrain = {
        **ARCHIPELAGO_CITY_TERRAIN,
        **{
            province: declared_terrain[province]
            for province in ARCHIPELAGO_NEIGHBOUR_PROVINCES
            if declared_terrain.get(province) in CITY_TERRAINS
        },
    }
    archipelago_heightmap = archipelago_heights(archipelago)
    island_terrain = archipelago_terrain(grid, archipelago_heightmap, boxes, city_terrain)
    island_palette = np.zeros(max(definitions) + 1, dtype=np.uint8)
    for province, kind in island_terrain.items():
        island_palette[province] = URBAN_FALLBACK_PALETTE if province in city_terrain else ARCHIPELAGO_PALETTES[kind]
    # Cities of the CITIES scope are painted by the city pass below.
    archipelago_cities = np.isin(grid, list(set(city_terrain) - CITIES))
    # A city stands on levelled ground at the height of its surroundings.
    city_ground = np.isin(grid, list(city_terrain))
    levelled = gaussian_filter(np.where(archipelago, archipelago_heightmap, ARCHIPELAGO_MIN_HEIGHT).astype(float), 3.0)
    archipelago_heightmap[city_ground] = np.clip(
        np.rint(levelled[city_ground]), ARCHIPELAGO_MIN_HEIGHT, ARCHIPELAGO_MAX_HEIGHT
    ).astype(np.uint8)
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
    # Coast the Nudge pass gave to the sea keeps no land relief above the
    # local sea floor.
    flooded = sea & np.isin(grid, list(NUDGE_SPLIT_DONORS))
    # Shared shoreline clearance: no city meshes or trees at the waterline.
    definition_text = "\n".join(definition_lines).encode("utf-8")
    water = water_mask(provinces, water_colours(definition_text))
    shore = urban_blocked(water, provinces, definition_text) & ~water
    built_up = archipelago_cities & ~shore
    relief_terrain = {}
    for index, line in enumerate(definition_lines):
        fields = line.split(";")
        if int(fields[0]) not in points:
            continue
        ys, xs = points[int(fields[0])].T
        coastal = any(sea[ys + dy, xs + dx].any() for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)))
        fields[5] = "true" if coastal else "false"
        if int(fields[0]) in ARAB_CITY_TERRAIN:
            fields[6] = ARAB_CITY_TERRAIN[int(fields[0])]
        elif int(fields[0]) in NATIONAL_CITY_TERRAIN:
            fields[6] = NATIONAL_CITY_TERRAIN[int(fields[0])]
        elif int(fields[0]) in CITIES:
            fields[6] = "urban"
        elif int(fields[0]) in RELIEF_PROVINCES:
            fields[6] = RELIEF_TERRAIN[int(fields[0])]
            relief_terrain[int(fields[0])] = fields[6]
        definition_lines[index] = ";".join(fields)
    for index, line in enumerate(definition_lines):
        fields = line.split(";")
        if int(fields[0]) in island_terrain and int(fields[0]) not in CITIES:
            fields[6] = island_terrain[int(fields[0])]
            definition_lines[index] = ";".join(fields)
    newline = "\r\n" if b"\r\n" in definition_bytes else "\n"
    outputs[Path("map/definition.csv")] = (newline.join(definition_lines) + newline).encode("utf-8")
    heights = None
    river_bed = None
    # Rivers precede the heightmap: the archipelago relief carves their final course.
    for name, mode, value in (("terrain", "P", 0), ("rivers", "P", 255), ("heightmap", "L", None), ("cities", "P", None)):
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
            if name in ("terrain", "cities"):
                source_pixels = np.asarray(source)
                for (x, y), (reference_x, reference_y) in surface_references.items():
                    pixels[y, x] = source_pixels[reference_y, reference_x]
            if name == "heightmap":
                pixels[mountains] = mountain_heightmap[mountains]
                pixels[islands] = lowland_heights(islands)[islands]
                carved = carve_river_valleys(archipelago_heightmap, archipelago, river_bed)
                pixels[archipelago] = carved[archipelago]
                flooded &= pixels > SEA_FLOOR_HEIGHT
                pixels[flooded] = SEA_FLOOR_HEIGHT
                heights = pixels
            elif name == "cities":
                # Only the city provinces carry city models on the archipelago.
                pixels[archipelago & ~cities] = CITY_BACKGROUND_INDEX
                pixels[built_up] = 15
                pixels[cities] = 15
                pixels[arab_cities] = 2
            else:
                pixels[islands | raised] = value
                if name == "rivers":
                    for (x, y), course in RIVER_COURSES.items():
                        pixels[y, x] = course
                    check_island_rivers(pixels, grid, sea)
                    river_bed = pixels
                if name == "terrain":
                    pixels[archipelago] = island_palette[grid[archipelago]]
                    pixels[built_up] = 13
                    pixels[cities & ~shore] = 13
                    pixels[cities & shore] = URBAN_FALLBACK_PALETTE
                    for province, kind in relief_terrain.items():
                        province_mask = surface_grid == province
                        pixels[province_mask] = {"desert": 3, "hills": 2, "mountain": 18}[kind]
                        if kind == "mountain":
                            pixels[province_mask & (mountain_heightmap >= 180)] = 11
                            pixels[province_mask & (mountain_heightmap >= 205)] = 16
            encoded = bmp_bytes(source, pixels, b"" if converted else original)
            outputs[path] = native_river_bmp(encoded) if name == "rivers" else encoded
    normal_path = Path("map/world_normal.bmp")
    original = (root / normal_path).read_bytes()
    with Image.open(BytesIO(original)) as source:
        normal = normal_from_height(
            Image.fromarray(heights), source, bytearray((islands | mountains | flooded | archipelago).tobytes())
        )
        if normal.tobytes() == source.tobytes():
            outputs[normal_path] = original
        else:
            encoded = BytesIO()
            normal.save(encoded, format="BMP")
            outputs[normal_path] = encoded.getvalue()
    outputs[COLOURMAP] = build_colourmap(
        read(COLOURMAP_SOURCE), islands | raised, water | np.isin(grid, list(exclusion_zone_provinces(root))),
        outputs[Path("map/terrain.bmp")], outputs[Path("map/cities.bmp")],
    )
    tree_path = Path("map/trees.bmp")
    original = read(tree_path)
    with Image.open(BytesIO(original)) as source:
        pixels = np.array(source)
        archipelago_trees(pixels, archipelago & (island_palette[grid] == ARCHIPELAGO_PALETTES["forest"]), archipelago)
        # Remove trees from every cell intersecting the new urban footprint.
        # The tree map uses a different grid, so point sampling misses narrow cities.
        tree_clearance = cities | archipelago_cities | (mountains & (mountain_heightmap >= 165))
        urban = {
            int(fields[0]) for line in definition_lines
            if (fields := line.split(";"))[6] in CITY_TERRAINS
        }
        for (x, y), (_original, replacement) in PROVINCE_PIXEL_REPAIRS.items():
            if replacement in urban:
                tree_clearance[y, x] = True
        ys, xs = np.where(tree_clearance)
        tx = xs * source.width // provinces.shape[1]
        ty = ys * source.height // provinces.shape[0]
        pixels[ty, tx] = 0
        pixels[tree_cells_blocked(water, source.width, source.height)] = 0
        outputs[tree_path] = bmp_bytes(source, pixels, original)
    stack_path = Path("map/unitstacks.txt")
    kinds = {int(line.split(";")[0]): line.split(";")[4] for line in definition_lines}
    outputs[stack_path] = unit_anchors(
        (root / stack_path).read_bytes(), points, heights, grid, kinds
    )
    railways = Path("map/railways.txt")
    outputs[railways] = railway_plan(read(railways), provinces, definitions)
    adjacencies = Path("map/adjacencies.csv")
    outputs[adjacencies] = island_bridges(read(adjacencies), grid, sea_provinces)
    return outputs


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--apply", action="store_true")
    mode.add_argument("--check", action="store_true")
    parser.add_argument("--colourmap-only", action="store_true", help="rebuild the DDS from the current map rasters")
    args = parser.parse_args()
    plan = current_colourmap_plan if args.colourmap_only else build_plan
    outputs = plan()
    changed = [path for path, data in outputs.items() if (ROOT / path).read_bytes() != data]
    for path in changed:
        print(f"{'WRITE' if args.apply else 'STALE'} {path.as_posix()}")
        if args.apply:
            (ROOT / path).write_bytes(outputs[path])
    if args.apply:
        repeated = plan()
        if any((ROOT / path).read_bytes() != data for path, data in repeated.items()):
            raise RuntimeError("coastal geography is not idempotent")
    elif changed:
        return 1
    subject = "Colourmap" if args.colourmap_only else "Coastal geography"
    print(f"{subject} is current.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
