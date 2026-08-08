"""Finish state shells and rebalance the generated war theatres.

The province lists remain authoritative: this builder only supplies the state
metadata that Nudge does not create (owner, core, population and buildings).
Legacy profiles are patched in place so their resources, VPs and special
province buildings remain authoritative too. Hand-authored country flags are
deliberately outside this map builder's ownership.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

from tools.builders.build_adiscord_map_buildings import (
    audit_buildings,
    ensure_nam_split_spawn_positions,
    synchronize_buildings,
)
from tools.lib.paths import repository_root

ROOT = repository_root()
STATE_DIR = ROOT / "history" / "states"

NAM_SVETLOGORSK_STATE_ID = 688
NAM_SVETLOGORSK_PROVINCES = (689, 3127, 4025, 8635, 9211, 10967)
NAM_RESIDUAL_CITY_STATE_ID = 689
NAM_RESIDUAL_CITY_PROVINCES = (176, 2038, 2299, 7618, 7639, 8358)
NAM_ORIGINAL_MAINLAND_PROVINCES = (
    176, 334, 461, 689, 1015, 1710, 2038, 2231, 2299, 2935,
    3127, 4025, 4287, 4321, 4912, 6099, 6961, 7324, 7618, 7639,
    8058, 8351, 8358, 8445, 8635, 8888, 9016, 9116, 9211, 9641,
    10909, 10967, 11069, 11696, 11926, 11942, 12480, 12668, 12982,
)
NAM_PRE_CITY_MAINLAND_PROVINCES = tuple(
    sorted(set(NAM_ORIGINAL_MAINLAND_PROVINCES) - set(NAM_SVETLOGORSK_PROVINCES))
)
NAM_RESIDUAL_MAINLAND_PROVINCES = tuple(
    sorted(
        set(NAM_ORIGINAL_MAINLAND_PROVINCES)
        - set(NAM_SVETLOGORSK_PROVINCES)
        - set(NAM_RESIDUAL_CITY_PROVINCES)
    )
)


KDR_STATES = tuple(range(234, 248))
RHM_STATES = (248, 249, 250, *range(252, 259))
SDR_STATES = (251, *range(259, 265))
MZR_STATES = tuple(range(265, 276))
KYZ_STATES = tuple(range(276, 287))
SHL_STATES = tuple(range(287, 295))
GLP_STATES = (*range(295, 303), 304, 305)

STARTING_OWNERS = {
    69: "AZH",
    174: "WEF",
    175: "WEF",
    **{state_id: "KDR" for state_id in KDR_STATES},
    **{state_id: "RHM" for state_id in RHM_STATES},
    **{state_id: "SDR" for state_id in SDR_STATES},
    **{state_id: "MZR" for state_id in MZR_STATES},
    **{state_id: "KYZ" for state_id in KYZ_STATES},
    **{state_id: "SHL" for state_id in SHL_STATES},
    **{state_id: "GLP" for state_id in GLP_STATES},
    303: "TFF",
    306: "WRK", 307: "VAD", 308: "WRK", 309: "WRK",
    310: "SOL", 311: "WRK", 312: "VLA", 313: "VLA",
    314: "VLA", 315: "TRU", 316: "TRU", 317: "TRU",
    318: "TRU", 319: "ROM", 320: "WRK", 321: "ROM",
    322: "ZAO", 323: "WRK", 324: "VAD", 325: "VAD",
    326: "PIV", 327: "WRK", 328: "PWR",
    329: "EXZ", 330: "EXZ",
}

LEGACY_OWNER_GAPS = {
    27: "WRK",
    79: "WRK",
    82: "WRK",
    194: "PWR",
    197: "VLA",
}

LEGACY_OWNER_OVERRIDES = {
    198: "VAD",
}

CAPITALS = {
    69: (367, 10),
    174: (158, 10),
    241: (971, 10),
    253: (443, 10),
    260: (197, 10),
    275: (193, 10),
    283: (1349, 10),
    294: (1198, 10),
    300: (492, 10),
}
SECONDARY_CENTRES = {
    240: (2309, 3), 248: (274, 3), 249: (488, 3),
    267: (261, 3), 278: (857, 3), 288: (834, 3),
    301: (251, 3),
}

# Smaller settlements spread VPs across the wide MZR and KYZ territories
# without also granting the population and industry of a secondary city.
MINOR_VPS = {
    265: (3465, 1), 270: (2504, 2), 273: (3643, 2),
    276: (10375, 1), 277: (6261, 2), 286: (7903, 2),
}

# Sparse deposits give every southern country something to extract and trade
# without turning the desert into a self-sufficient industrial heartland.
STATE_RESOURCES = {
    69: {"oil": 3, "chromium": 2},
    175: {"steel": 2, "aluminium": 2},
    236: {"steel": 3, "oil": 1},
    255: {"aluminium": 3, "oil": 1},
    263: {"tungsten": 2, "steel": 2},
    269: {"oil": 3, "chromium": 1},
    285: {"tungsten": 2, "aluminium": 2},
    291: {"steel": 3, "chromium": 1},
    299: {"aluminium": 3, "chromium": 1},
}

# Generated naval OOBs require these real coastal bases. Keeping them in this
# builder prevents a state regeneration from silently deleting the fleets' ports.
GENERATED_STATE_BUILDINGS = {
    69: {"dockyard": 1},
}
GENERATED_PROVINCE_BUILDINGS = {
    69: ((493, "naval_base", 1),),
}

# Cities that were victory points before the Vorkerland state split. Keep the
# points on their actual urban provinces instead of losing them during rebuild.
VORKERLAND_CENTRES = {
    306: (16643, 3),
    307: (16584, 3),
    308: (16615, 3),
    309: (11795, 5),
    312: (16637, 3),
    313: (16617, 3),
    317: (8803, 3),
    318: (16642, 3),
    323: (16590, 3),
    327: (16641, 5),
}

# Named railway settlements give Macri's wide republic small local objectives
# without pretending that every stop is a full urban centre.
VORKERLAND_MINOR_VPS = {
    311: (5905, 1),
    314: (5405, 1),
}

# Explicit profiles replace the old pseudo-random 24-72k population formula
# around the densely populated Vorkernsberg conurbation.
STATE_PROFILES = {
    306: {"population": 1_180_000, "category": "large_town", "infrastructure": 3, "industry": 2, "military": 1, "supplies": 3.0},
    307: {"population": 620_000, "category": "town", "infrastructure": 2, "industry": 1, "supplies": 2.0},
    308: {"population": 840_000, "category": "large_town", "infrastructure": 3, "industry": 1, "supplies": 2.5},
    309: {"population": 470_000, "category": "town", "infrastructure": 3, "industry": 1, "supplies": 2.0},
    310: {"population": 260_000, "category": "rural", "infrastructure": 2, "industry": 1, "supplies": 2.0},
    311: {"population": 750_000, "category": "town", "infrastructure": 3, "industry": 1, "supplies": 2.5},
    312: {"population": 650_000, "category": "town", "infrastructure": 3, "industry": 1, "military": 1, "supplies": 3.0},
    313: {"population": 550_000, "category": "town", "infrastructure": 3, "industry": 1, "supplies": 3.0},
    314: {"population": 550_000, "category": "town", "infrastructure": 3, "industry": 1, "supplies": 3.0},
    315: {"population": 310_000, "category": "rural", "infrastructure": 2, "industry": 1, "supplies": 2.0},
    316: {"population": 280_000, "category": "rural", "infrastructure": 2, "industry": 1, "supplies": 2.0},
    317: {"population": 360_000, "category": "town", "infrastructure": 3, "industry": 1, "military": 1, "supplies": 3.0},
    318: {"population": 420_000, "category": "town", "infrastructure": 3, "industry": 1, "military": 1, "supplies": 3.0},
    319: {"population": 300_000, "category": "rural", "infrastructure": 2, "industry": 1, "supplies": 2.0},
    320: {"population": 390_000, "category": "rural", "infrastructure": 2, "industry": 0, "supplies": 1.5},
    321: {"population": 280_000, "category": "rural", "infrastructure": 2, "industry": 1, "supplies": 2.0},
    322: {"population": 340_000, "category": "town", "infrastructure": 3, "industry": 1, "supplies": 2.5},
    323: {"population": 710_000, "category": "town", "infrastructure": 2, "industry": 1, "supplies": 2.0},
    324: {"population": 510_000, "category": "town", "infrastructure": 3, "industry": 2, "supplies": 3.0},
    325: {"population": 290_000, "category": "rural", "infrastructure": 2, "industry": 1, "supplies": 2.0},
    327: {"population": 310_000, "category": "town", "infrastructure": 3, "industry": 1, "supplies": 2.0},
    328: {"population": 260_000, "category": "rural", "infrastructure": 2, "industry": 1, "supplies": 2.0},
}

# Vorkerland's legacy state files predate the Nudge split.  These values keep
# every civil-war front inhabited and supplied without flattening the old
# resources, victory points, bunkers and state ownership into generated data.
VORKERLAND_LEGACY_PROFILES = {
    40: {"population": 12_500_000, "category": "megalopolis", "infrastructure": 5, "civilian": 6, "military": 4, "air_base": 3, "supplies": 10.0},
    71: {"population": 480_000, "category": "town", "infrastructure": 3, "civilian": 1, "military": 1, "supplies": 3.0},
    72: {"population": 520_000, "category": "town", "infrastructure": 3, "civilian": 1, "military": 2, "supplies": 3.0},
    73: {"population": 640_000, "category": "town", "infrastructure": 3, "civilian": 2, "military": 1, "supplies": 3.5},
    74: {"population": 1_100_000, "category": "large_town", "infrastructure": 4, "civilian": 3, "military": 2, "air_base": 1, "supplies": 4.5},
    76: {"population": 610_000, "category": "town", "infrastructure": 3, "civilian": 1, "military": 1, "supplies": 3.0},
    80: {"population": 720_000, "category": "large_town", "infrastructure": 3, "civilian": 2, "military": 1, "supplies": 3.5},
    90: {"population": 360_000, "category": "rural", "infrastructure": 2, "civilian": 1, "supplies": 2.5},
    91: {"population": 340_000, "category": "rural", "infrastructure": 2, "civilian": 1, "supplies": 2.5},
    93: {"population": 310_000, "category": "rural", "infrastructure": 2, "civilian": 1, "supplies": 2.5},
    94: {"population": 330_000, "category": "rural", "infrastructure": 2, "civilian": 1, "supplies": 2.5},
    144: {"population": 260_000, "category": "rural", "infrastructure": 2, "civilian": 1, "supplies": 2.0},
    145: {"population": 420_000, "category": "town", "infrastructure": 3, "civilian": 1, "military": 1, "supplies": 3.0},
    194: {"population": 410_000, "category": "town", "infrastructure": 3, "civilian": 1, "military": 1, "supplies": 3.0},
    195: {"population": 480_000, "category": "town", "infrastructure": 3, "civilian": 1, "military": 1, "supplies": 3.0},
    196: {"population": 520_000, "category": "town", "infrastructure": 3, "civilian": 1, "military": 1, "supplies": 3.0},
    197: {"population": 1_050_000, "category": "large_town", "infrastructure": 4, "civilian": 3, "military": 1, "air_base": 1, "supplies": 4.5},
    198: {"population": 510_000, "category": "town", "infrastructure": 3, "civilian": 2, "military": 1, "supplies": 3.5},
    199: {"population": 470_000, "category": "town", "infrastructure": 3, "civilian": 1, "military": 1, "supplies": 3.0},
}

# NAM begins with one mainland split into the Svetlogorsk uprising district,
# the broad resource basin, and a compact southern port which survives the SLF
# victory settlement. Totals stay unchanged across the three states.
NAM_STATE_PROFILES = {
    67: {"population": 430_000, "category": "large_city", "infrastructure": 4, "civilian": 2, "military": 0, "air_base": 1, "supplies": 5.0},
    225: {"population": 220_000, "category": "town", "infrastructure": 3, "civilian": 1, "military": 1, "supplies": 3.0},
    226: {"population": 140_000, "category": "rural", "infrastructure": 2, "civilian": 1, "supplies": 2.5},
    227: {"population": 180_000, "category": "rural", "infrastructure": 2, "civilian": 1, "supplies": 2.5},
    228: {"population": 300_000, "category": "town", "infrastructure": 3, "civilian": 2, "military": 1, "supplies": 3.5},
    229: {"population": 120_000, "category": "rural", "infrastructure": 2, "civilian": 1, "supplies": 2.5},
    230: {"population": 100_000, "category": "rural", "infrastructure": 2, "civilian": 1, "supplies": 2.5},
    231: {"population": 160_000, "category": "rural", "infrastructure": 2, "civilian": 1, "military": 1, "supplies": 2.5},
    NAM_SVETLOGORSK_STATE_ID: {"population": 90_000, "category": "town", "infrastructure": 3, "civilian": 1, "military": 1, "air_base": 1, "supplies": 3.0},
    NAM_RESIDUAL_CITY_STATE_ID: {"population": 120_000, "category": "town", "infrastructure": 3, "civilian": 1, "military": 2, "supplies": 3.5},
}

# The three states facing NAM's resource basin need enough population and
# local logistics for the restoration coalition to launch a real offensive.
NAM_COALITION_FRONT_PROFILES = {
    68: {"population": 300_000, "category": "town", "infrastructure": 3, "civilian": 2, "military": 1, "supplies": 4.0},
    69: {"population": 320_000, "category": "town", "infrastructure": 3, "civilian": 2, "military": 1, "air_base": 1, "supplies": 4.0},
    70: {"population": 350_000, "category": "town", "infrastructure": 3, "civilian": 2, "military": 1, "supplies": 4.0},
}

# Every state owned and cored by Ivanland at game start receives a coherent
# demographic/logistics baseline.  The existing hub in state 25 and its rail
# spur through states 100 and 99 remain authoritative, so the frontier relies
# on infrastructure plus local supply rather than a redundant second hub.
IVANLAND_STATE_PROFILES = {
    25: {"population": 3_600_000, "category": "metropolis", "infrastructure": 5, "civilian": 6, "military": 4, "air_base": 3, "supplies": 8.0},
    92: {"population": 420_000, "category": "rural", "infrastructure": 3, "civilian": 1, "military": 1, "supplies": 4.0},
    95: {"population": 680_000, "category": "town", "infrastructure": 4, "civilian": 2, "military": 2, "air_base": 1, "supplies": 5.0},
    96: {"population": 620_000, "category": "town", "infrastructure": 4, "civilian": 2, "military": 2, "supplies": 5.0},
    97: {"population": 780_000, "category": "town", "infrastructure": 3, "civilian": 2, "military": 1, "supplies": 3.5},
    98: {"population": 1_300_000, "category": "large_town", "infrastructure": 4, "civilian": 3, "military": 2, "supplies": 4.5},
    99: {"population": 1_450_000, "category": "large_city", "infrastructure": 4, "civilian": 4, "military": 3, "air_base": 2, "supplies": 5.0},
    100: {"population": 1_050_000, "category": "large_town", "infrastructure": 4, "civilian": 3, "military": 2, "supplies": 4.0},
    101: {"population": 520_000, "category": "town", "infrastructure": 3, "civilian": 2, "military": 1, "supplies": 3.0},
    127: {"population": 650_000, "category": "town", "infrastructure": 3, "civilian": 2, "military": 1, "supplies": 3.0},
    128: {"population": 320_000, "category": "rural", "infrastructure": 2, "civilian": 1, "supplies": 2.0},
    129: {"population": 480_000, "category": "rural", "infrastructure": 3, "civilian": 1, "military": 1, "supplies": 3.0},
    130: {"population": 560_000, "category": "town", "infrastructure": 3, "civilian": 2, "military": 1, "supplies": 3.5},
    131: {"population": 590_000, "category": "town", "infrastructure": 3, "civilian": 2, "military": 1, "supplies": 3.5},
    132: {"population": 430_000, "category": "rural", "infrastructure": 3, "civilian": 1, "military": 1, "supplies": 3.0},
    164: {"population": 350_000, "category": "rural", "infrastructure": 2, "civilian": 1, "supplies": 2.5},
}

# Afrela is populous enough to sustain its regional diplomacy and volunteer
# missions, but remains a medium power.  State 232 stays a small island port;
# the connected mainland follows the existing capital hub and railway spine.
AFRELA_STATE_PROFILES = {
    52: {"population": 3_200_000, "category": "metropolis", "infrastructure": 4, "civilian": 5, "military": 2, "air_base": 2, "supplies": 7.0},
    113: {"population": 1_500_000, "category": "large_city", "infrastructure": 3, "civilian": 2, "military": 1, "supplies": 3.5},
    114: {"population": 1_200_000, "category": "large_town", "infrastructure": 3, "civilian": 2, "military": 1, "supplies": 3.5},
    232: {"population": 120_000, "category": "rural", "infrastructure": 2, "civilian": 1, "supplies": 1.5},
    326: {"population": 1_100_000, "category": "large_town", "infrastructure": 3, "civilian": 2, "military": 1, "supplies": 3.5},
}

# Legacy states moved by ADISCORD_vorkerland_apply_initial_map and its setup
# effects must support the armies spawned there.  Existing sensible population
# figures are retained; empty shells and obviously under-classified cities get
# explicit demographic and industrial profiles.
VORKERLAND_INITIAL_MAP_LEGACY_PROFILES = {
    38: {"population": 1_650_000, "category": "metropolis", "infrastructure": 5, "civilian": 3, "military": 2, "air_base": 2, "supplies": 6.0},
    75: {"population": 7_430_000, "category": "large_city", "infrastructure": 5, "civilian": 5, "military": 3, "air_base": 3, "supplies": 8.0},
    81: {"population": 1_350_000, "category": "large_city", "infrastructure": 5, "civilian": 3, "military": 2, "air_base": 2, "supplies": 5.0},
    82: {"population": 420_000, "category": "rural", "infrastructure": 2, "civilian": 1, "military": 1, "supplies": 4.0},
    102: {"population": 13_520_000, "category": "megalopolis", "infrastructure": 5, "civilian": 7, "military": 5, "air_base": 3, "supplies": 10.0},
    104: {"population": 2_400_000, "category": "metropolis", "infrastructure": 4, "civilian": 4, "military": 2, "air_base": 2, "supplies": 6.0},
    105: {"population": 9_800_000, "category": "megalopolis", "infrastructure": 5, "civilian": 7, "military": 5, "air_base": 3, "supplies": 10.0},
    106: {"population": 2_530_000, "category": "large_city", "infrastructure": 4, "civilian": 3, "military": 2, "air_base": 2, "supplies": 5.0},
    107: {"population": 325_000, "category": "rural", "infrastructure": 2, "civilian": 1, "supplies": 2.5},
    108: {"population": 220_000, "category": "rural", "infrastructure": 3, "civilian": 1, "supplies": 2.5},
    109: {"population": 523_000, "category": "town", "infrastructure": 3, "civilian": 2, "military": 1, "supplies": 3.5},
    110: {"population": 986_000, "category": "large_town", "infrastructure": 4, "civilian": 3, "military": 1, "air_base": 1, "supplies": 4.5},
    111: {"population": 643_000, "category": "town", "infrastructure": 4, "civilian": 2, "military": 1, "supplies": 4.0},
    112: {"population": 1_530_000, "category": "large_city", "infrastructure": 3, "civilian": 2, "military": 1, "supplies": 4.0},
    113: {"population": 724_000, "category": "town", "infrastructure": 3, "civilian": 2, "military": 1, "supplies": 3.5},
    114: {"population": 432_000, "category": "town", "infrastructure": 3, "civilian": 1, "military": 1, "supplies": 3.0},
    115: {"population": 220_000, "category": "rural", "infrastructure": 2, "civilian": 1, "supplies": 2.0},
    116: {"population": 180_000, "category": "rural", "infrastructure": 2, "civilian": 1, "supplies": 2.0},
    117: {"population": 210_000, "category": "rural", "infrastructure": 2, "civilian": 1, "supplies": 2.0},
    # States 118-120 are now owned by the Ainholm mandate/Orval setup. Their
    # complete profiles belong to build_adiscord_ainholm_mandate.py; keeping
    # old theatre defaults here would silently overwrite that generator.
    121: {"population": 1_650_000, "category": "large_city", "infrastructure": 4, "civilian": 3, "military": 2, "supplies": 5.0},
    122: {"population": 986_000, "category": "large_town", "infrastructure": 4, "civilian": 2, "military": 1, "supplies": 4.0},
    123: {"population": 1_640_000, "category": "large_city", "infrastructure": 4, "civilian": 3, "military": 2, "supplies": 5.0},
    124: {"population": 240_000, "category": "rural", "infrastructure": 3, "civilian": 1, "military": 1, "supplies": 2.5},
    200: {"population": 180_000, "category": "rural", "infrastructure": 2, "civilian": 1, "supplies": 2.0},
    201: {"population": 220_000, "category": "rural", "infrastructure": 2, "civilian": 1, "supplies": 2.0},
    202: {"population": 160_000, "category": "rural", "infrastructure": 2, "civilian": 1, "supplies": 2.0},
}

VORKERLAND_LEGACY_VICTORY_POINTS = {
    82: ((8059, 3),),
    74: ((16585, 5),),
    197: ((16623, 10),),
    104: ((7778, 8), (16564, 3), (16583, 2)),
    105: ((16589, 12), (16565, 5), (16577, 3), (16581, 2)),
}

VORKERLAND_VICTORY_POINT_NAMES = {
    8803: "Верховье",
    16642: "Оствин",
    5405: "Линден",
    5905: "Фельден",
    16585: "Восточный плацдарм",
    10016: "Дальний пост",
    16623: "Эберн",
    16617: "Эстервик",
    16637: "Нойен",
    7778: "Велин",
    16564: "Слободск",
    16583: "Надречье",
    16589: "Техлар",
    16565: "Фирнов",
    16577: "Каменск",
    16581: "Северный Техлар",
}

AFRELA_LEGACY_VICTORY_POINTS = {
    52: ((4218, 12),),
    113: ((5162, 4),),
    114: ((7920, 4),),
    232: ((11546, 1),),
    326: ((16626, 5),),
}

NAM_LEGACY_VICTORY_POINTS = {
    NAM_SVETLOGORSK_STATE_ID: ((689, 3),),
    NAM_RESIDUAL_CITY_STATE_ID: ((2038, 5),),
}

AFRELA_VICTORY_POINT_NAMES = {
    4218: "Афрела",
    5162: "Мирель",
    7920: "Таверан",
    11546: "Апрельская Гавань",
    16626: "Дальрен",
}

NAM_VICTORY_POINT_NAMES = {
    689: "Светлогорск",
    2038: "Южная гавань",
}

GENERATED_LEGACY_VICTORY_POINTS = {
    **VORKERLAND_LEGACY_VICTORY_POINTS,
    **AFRELA_LEGACY_VICTORY_POINTS,
    **NAM_LEGACY_VICTORY_POINTS,
}

GENERATED_VICTORY_POINT_NAMES = {
    **VORKERLAND_VICTORY_POINT_NAMES,
    **AFRELA_VICTORY_POINT_NAMES,
    **NAM_VICTORY_POINT_NAMES,
}

VORKERLAND_STATE_NAMES = {
    315: "Златореченское нагорье",
    316: "Верхнеречье",
    317: "Верховье",
    318: "Оствинский округ",
    320: "Оствинская низина",
    104: "Центральная Слобода",
    105: "Фирновская агломерация",
}

GENERATED_STATE_NAMES = {
    **VORKERLAND_STATE_NAMES,
    NAM_SVETLOGORSK_STATE_ID: "Светлогорский округ",
    NAM_RESIDUAL_CITY_STATE_ID: "Южнобережный округ",
}

VORKERLAND_INITIAL_MAP_LEGACY_STATES = {
    27, 32, 33, 34, 35, 36, 37, 38, 39, 40,
    71, 72, 73, 74, 75, 76, 79, 80, 81, 82,
    90, 91, 93, 94, 102, 104, 105, 106, 107, 108, 109, 110, 111,
    121, 122, 123, 124, 144, 145, 194, 195, 196, 197, 198, 199,
    200, 201, 202,
}

LEGACY_STATE_PROFILES = {
    **VORKERLAND_LEGACY_PROFILES,
    **NAM_STATE_PROFILES,
    **NAM_COALITION_FRONT_PROFILES,
    **IVANLAND_STATE_PROFILES,
    **VORKERLAND_INITIAL_MAP_LEGACY_PROFILES,
    # Afrela owns 113-114, which were also covered by the broad 106-124
    # theatre audit. Country-specific profiles intentionally take precedence.
    **AFRELA_STATE_PROFILES,
}

EXTRA_CORES = {174: ("EFL",), 175: ("EFL",)}

# Tiny land provinces created in the same Nudge pass were left outside every
# state. Assign each to the neighbouring state with the longest shared border.
EXTRA_PROVINCES_BY_STATE = {
    258: (4759,),
    261: (3536,),
    265: (2244, 3528),
    270: (6833,),
    273: (3918, 10526),
    275: (196,),
    279: (8121,),
    288: (10490,),
    291: (946,),
}

TOWN_STATES = set(CAPITALS) | set(SECONDARY_CENTRES) | {
    306, 307, 308, 309, 318, 323, 327,
}
WASTELANDS = {238, 254, 258, 264, 267, 288, 292, 296, 329, 330}


def state_path(state_id: int) -> Path:
    matches = sorted(STATE_DIR.glob(f"{state_id}-*.txt"))
    if len(matches) != 1:
        raise RuntimeError(f"state {state_id}: expected one file, found {len(matches)}")
    return matches[0]


def population(state_id: int, owner: str) -> int:
    if state_id in STATE_PROFILES:
        return int(STATE_PROFILES[state_id]["population"])
    if owner == "EXZ":
        return 1
    if state_id == 303:
        return 9_000
    if state_id in CAPITALS:
        return {
            69: 145_000,
            174: 95_000,
            241: 135_000,
            253: 105_000,
            260: 72_000,
            275: 145_000,
            283: 112_000,
            294: 128_000,
            300: 118_000,
        }[state_id]
    if state_id in SECONDARY_CENTRES:
        return 65_000
    if 234 <= state_id <= 305:
        return 8_000 + ((state_id * 7_919) % 35_000)
    return 24_000 + ((state_id * 5_173) % 48_000)


def category(state_id: int) -> str:
    if state_id in STATE_PROFILES:
        return str(STATE_PROFILES[state_id]["category"])
    if state_id in TOWN_STATES:
        return "town"
    if state_id in WASTELANDS:
        return "wasteland"
    return "rural"


def buildings(state_id: int, owner: str) -> list[str]:
    if owner == "EXZ":
        return []
    profile = STATE_PROFILES.get(state_id)
    infrastructure = int(profile["infrastructure"]) if profile else 2
    lines = [f"infrastructure = {infrastructure}"]
    if profile:
        industry = int(profile["industry"])
        if industry:
            lines.append(f"industrial_complex = {industry}")
        military = int(profile.get("military", 0))
        if military:
            lines.append(f"arms_factory = {military}")
        air_base = int(profile.get("air_base", 0))
        if air_base:
            lines.append(f"air_base = {air_base}")
    elif state_id in CAPITALS:
        lines += ["industrial_complex = 2", "arms_factory = 1", "air_base = 1"]
    elif state_id in SECONDARY_CENTRES:
        lines += ["industrial_complex = 1"]
    elif state_id in TOWN_STATES:
        lines += ["industrial_complex = 1"]
    lines.extend(
        f"{building} = {level}"
        for building, level in GENERATED_STATE_BUILDINGS.get(state_id, {}).items()
    )
    lines.extend(
        f"{province} = {{ {building} = {level} }}"
        for province, building, level in GENERATED_PROVINCE_BUILDINGS.get(state_id, ())
    )
    return lines


def render_state(state_id: int, owner: str) -> str:
    path = state_path(state_id)
    old = path.read_text(encoding="utf-8-sig", errors="strict")
    province_match = re.search(r"provinces\s*=\s*\{([^}]*)\}", old, re.DOTALL)
    if not province_match:
        raise RuntimeError(f"state {state_id}: missing provinces block")
    provinces = [int(value) for value in re.findall(r"\d+", province_match.group(1))]
    provinces = sorted(set(provinces) | set(EXTRA_PROVINCES_BY_STATE.get(state_id, ())))
    if not provinces:
        raise RuntimeError(f"state {state_id}: empty provinces block")

    history = [f"\t\towner = {owner}", f"\t\tadd_core_of = {owner}"]
    history.extend(f"\t\tadd_core_of = {tag}" for tag in EXTRA_CORES.get(state_id, ()))
    urban_provinces = {
        int(fields[0])
        for line in (ROOT / "map" / "definition.csv").read_text(encoding="utf-8-sig").splitlines()
        if len(fields := line.split(";")) > 6 and fields[0].isdigit() and fields[6] == "urban"
    }
    centres = {
        **CAPITALS,
        **SECONDARY_CENTRES,
        **MINOR_VPS,
        **VORKERLAND_CENTRES,
        **VORKERLAND_MINOR_VPS,
    }
    if state_id in centres:
        province, value = centres[state_id]
        if province not in provinces:
            raise RuntimeError(f"state {state_id}: city VP {province} is outside the state")
        if province in urban_provinces or VORKERLAND_MINOR_VPS.get(state_id) == (province, value):
            history.append(f"\t\tvictory_points = {{ {province} {value} }}")

    state_buildings = buildings(state_id, owner)
    if state_buildings:
        history.append("\t\tbuildings = {")
        history.extend(f"\t\t\t{line}" for line in state_buildings)
        history.append("\t\t}")

    province_lines = []
    for start in range(0, len(provinces), 12):
        province_lines.append("\t\t" + " ".join(map(str, provinces[start:start + 12])))

    profile = STATE_PROFILES.get(state_id)
    local_supplies = 0.0 if owner == "EXZ" else (
        float(profile["supplies"]) if profile else (3.0 if state_id in CAPITALS else 1.5)
    )
    resource_block = []
    if state_id in STATE_RESOURCES:
        resource_block = ["\tresources = {"]
        resource_block.extend(
            f"\t\t{resource} = {amount}"
            for resource, amount in STATE_RESOURCES[state_id].items()
        )
        resource_block.append("\t}")
    return "\n".join([
        "state = {",
        f"\tid = {state_id}",
        f'\tname = "STATE_{state_id}"',
        f"\tmanpower = {population(state_id, owner)}",
        f"\tstate_category = {category(state_id)}",
        *resource_block,
        "\thistory = {",
        *history,
        "\t}",
        "\tprovinces = {",
        *province_lines,
        "\t}",
        "\tbuildings_max_level_factor = 1.000",
        f"\tlocal_supplies = {local_supplies:.1f}",
        "}",
        "",
    ])


def detach_northern_lighthouse() -> None:
    """State 303 was cut from the outer placeholder after Nudge's state pass."""
    outer = state_path(23)
    source = outer.read_text(encoding="utf-8-sig", errors="strict")
    matches = re.findall(r"(?<!\d)3261(?!\d)", source)
    if len(matches) > 1:
        raise RuntimeError("state 23: province 3261 is duplicated inside the placeholder")
    if matches:
        updated = re.sub(r"(?<!\d)3261(?!\d)\s*", "", source, count=1)
        outer.write_text(updated, encoding="utf-8", newline="\n")


def fill_legacy_owner_gaps() -> None:
    """Close obvious pre-existing grey holes without rebuilding their metadata."""
    for state_id, owner in LEGACY_OWNER_GAPS.items():
        path = state_path(state_id)
        source = path.read_text(encoding="utf-8-sig", errors="strict")
        if re.search(r"(?m)^\s*owner\s*=", source):
            continue
        history = f"\n\thistory = {{\n\t\towner = {owner}\n\t\tadd_core_of = {owner}\n\t}}\n"
        marker = re.search(r"(?m)^\s*provinces\s*=", source)
        if not marker:
            raise RuntimeError(f"state {state_id}: missing provinces block")
        updated = source[:marker.start()] + history + source[marker.start():]
        path.write_text(updated, encoding="utf-8", newline="\n")


def apply_legacy_owner_overrides() -> None:
    """Keep explicit ownership corrections without rebuilding legacy states."""
    for state_id, owner in LEGACY_OWNER_OVERRIDES.items():
        path = state_path(state_id)
        source = path.read_text(encoding="utf-8-sig", errors="strict")
        updated, owner_count = re.subn(
            r"(?m)^(\s*)owner\s*=\s*[A-Z0-9]{3}\s*$",
            rf"\1owner={owner}",
            source,
            count=1,
        )
        updated, core_count = re.subn(
            r"(?m)^(\s*)add_core_of\s*=\s*[A-Z0-9]{3}\s*$",
            rf"\1add_core_of={owner}",
            updated,
            count=1,
        )
        if owner_count != 1 or core_count != 1:
            raise RuntimeError(f"state {state_id}: could not apply owner/core override")
        path.write_text(updated, encoding="utf-8", newline="\n")


def matching_brace(source: str, opening: int) -> int:
    """Return the closing brace for ``source[opening]``."""
    depth = 0
    for index in range(opening, len(source)):
        if source[index] == "{":
            depth += 1
        elif source[index] == "}":
            depth -= 1
            if depth == 0:
                return index
    raise RuntimeError("unclosed Clausewitz block")


def named_block(source: str, name: str) -> tuple[int, int]:
    match = re.search(rf"(?m)^\s*{re.escape(name)}\s*=\s*\{{", source)
    if not match:
        raise RuntimeError(f"missing {name} block")
    opening = source.find("{", match.start(), match.end())
    return opening, matching_brace(source, opening)


def set_scalar(source: str, key: str, value: str) -> str:
    """Set a top-level state scalar, inserting it before history if absent."""
    updated, count = re.subn(
        rf"(?m)^(\s*){re.escape(key)}\s*=\s*[^\s#]+\s*$",
        rf"\1{key} = {value}",
        source,
        count=1,
    )
    if count:
        return updated
    history = re.search(r"(?m)^\s*history\s*=", source)
    if not history:
        raise RuntimeError(f"cannot insert {key}: state has no history block")
    return source[:history.start()] + f"\t{key} = {value}\n" + source[history.start():]


def ensure_history_buildings(source: str, profile: dict[str, object]) -> str:
    """Raise state-level buildings to profile minima, preserving special ones."""
    if not re.search(r"(?m)^\s*history\s*=\s*\{", source):
        state_close = source.rfind("}")
        if state_close < 0:
            raise RuntimeError("cannot insert history: state block is unclosed")
        source = source[:state_close].rstrip() + "\n\thistory = {\n\t}\n" + source[state_close:]
    history_open, history_close = named_block(source, "history")
    history = source[history_open:history_close + 1]
    building_match = re.search(r"(?m)^\s*buildings\s*=\s*\{", history)
    if building_match:
        building_open = history.find("{", building_match.start(), building_match.end())
        building_close = matching_brace(history, building_open)
        block = history[building_open:building_close + 1]
    else:
        block = "{\n\t\t}"
        building_open = -1
        building_close = -1

    minima = {
        "infrastructure": int(profile["infrastructure"]),
        "industrial_complex": int(profile.get("civilian", 0)),
        "arms_factory": int(profile.get("military", 0)),
        "air_base": int(profile.get("air_base", 0)),
    }
    for building, minimum in minima.items():
        if not minimum:
            continue
        pattern = rf"(?m)^(\s*){re.escape(building)}\s*=\s*(\d+)\s*$"
        current = re.search(pattern, block)
        if current:
            value = max(int(current.group(2)), minimum)
            block = re.sub(pattern, rf"\1{building} = {value}", block, count=1)
        else:
            block = block[:1] + f"\n\t\t\t{building} = {minimum}" + block[1:]

    if building_match:
        history = history[:building_open] + block + history[building_close + 1:]
    else:
        history = history[:-1].rstrip() + f"\n\t\tbuildings = {block}\n\t}}"
    return source[:history_open] + history + source[history_close + 1:]


def set_history_building_level(source: str, building: str, level: int) -> str:
    """Set one state building exactly while preserving province buildings."""
    history_open, history_close = named_block(source, "history")
    history = source[history_open:history_close + 1]
    building_match = re.search(r"(?m)^\s*buildings\s*=\s*\{", history)
    if not building_match:
        raise RuntimeError("cannot set exact building level: history has no buildings block")
    building_open = history.find("{", building_match.start(), building_match.end())
    building_close = matching_brace(history, building_open)
    block = history[building_open:building_close + 1]
    pattern = rf"(?m)^([ \t]*){re.escape(building)}\s*=\s*\d+\s*$"
    if re.search(pattern, block):
        if level:
            block = re.sub(pattern, rf"\1{building} = {level}", block, count=1)
        else:
            block = re.sub(pattern + r"\n?", "", block, count=1)
    elif level:
        block = block[:-1].rstrip() + f"\n\t\t\t{building} = {level}\n\t\t}}"
    history = history[:building_open] + block + history[building_close + 1:]
    return source[:history_open] + history + source[history_close + 1:]


def split_svetlogorsk_from_nam() -> None:
    """Carve the uprising and residual city states without changing NAM totals."""
    mainland_path = state_path(67)
    source = mainland_path.read_text(encoding="utf-8-sig", errors="strict")
    province_match = re.search(r"provinces\s*=\s*\{([^}]*)\}", source, re.DOTALL)
    if not province_match:
        raise RuntimeError("state 67: missing provinces block")
    current = set(map(int, re.findall(r"\d+", province_match.group(1))))
    allowed = (
        set(NAM_ORIGINAL_MAINLAND_PROVINCES),
        set(NAM_PRE_CITY_MAINLAND_PROVINCES),
        set(NAM_RESIDUAL_MAINLAND_PROVINCES),
    )
    if current not in allowed:
        raise RuntimeError("state 67: province manifest drifted from the Svetlogorsk split")

    province_lines = [
        "\t\t" + " ".join(map(str, NAM_RESIDUAL_MAINLAND_PROVINCES[start:start + 12]))
        for start in range(0, len(NAM_RESIDUAL_MAINLAND_PROVINCES), 12)
    ]
    replacement = "provinces={\n" + "\n".join(province_lines) + "\n\t}"
    source = source[:province_match.start()] + replacement + source[province_match.end():]

    # Both physical ports leave state 67: 689 belongs to Svetlogorsk and 2038
    # becomes the harbour of the small residual NAM city-state.
    for port in (689, 2038):
        source = re.sub(
            rf"(?m)^\s*{port}\s*=\s*\{{\s*naval_base\s*=\s*\d+\s*\}}\s*$\n?",
            "",
            source,
            count=1,
        )

    for building, level in {
        "industrial_complex": 2,
        "arms_factory": 0,
        "air_base": 1,
        "dockyard": 0,
    }.items():
        source = set_history_building_level(source, building, level)
    source, oil_count = re.subn(
        r"(?m)^(\s*)oil\s*=\s*\d+\s*$", r"\1oil = 144", source, count=1
    )
    source, chromium_count = re.subn(
        r"(?m)^(\s*)chromium\s*=\s*\d+\s*$", r"\1chromium = 13", source, count=1
    )
    if oil_count != 1 or chromium_count != 1:
        raise RuntimeError("state 67: expected one oil and one chromium resource entry")
    mainland_path.write_text(source, encoding="utf-8", newline="\n")

    target = STATE_DIR / f"{NAM_SVETLOGORSK_STATE_ID}-Svetlogorsk.txt"
    matches = sorted(STATE_DIR.glob(f"{NAM_SVETLOGORSK_STATE_ID}-*.txt"))
    if matches and matches != [target]:
        raise RuntimeError(f"state {NAM_SVETLOGORSK_STATE_ID}: id is already occupied")
    provinces = " ".join(map(str, NAM_SVETLOGORSK_PROVINCES))
    target.write_text(
        "\n".join([
            "# Generated by tools/build_adiscord_new_states.py",
            "state={",
            f"\tid={NAM_SVETLOGORSK_STATE_ID}",
            f'\tname=\"STATE_{NAM_SVETLOGORSK_STATE_ID}\"',
            f"\tprovinces={{ {provinces} }}",
            "\tmanpower = 90000",
            "\tbuildings_max_level_factor = 1.000",
            "\tstate_category = town",
            "\tlocal_supplies = 3.0",
            "\thistory = {",
            "\t\towner = NAM",
            "\t\tadd_core_of = NAM",
            "\t\tvictory_points = { 689 3 }",
            "\t\tbuildings = {",
            "\t\t\tinfrastructure = 3",
            "\t\t\tindustrial_complex = 1",
            "\t\t\tarms_factory = 1",
            "\t\t\tair_base = 1",
            "\t\t\tdockyard = 1",
            "\t\t\t689 = { naval_base = 2 }",
            "\t\t}",
            "\t}",
            "}",
            "",
        ]),
        encoding="utf-8",
        newline="\n",
    )

    residual_target = STATE_DIR / f"{NAM_RESIDUAL_CITY_STATE_ID}-South-Coast.txt"
    residual_matches = sorted(STATE_DIR.glob(f"{NAM_RESIDUAL_CITY_STATE_ID}-*.txt"))
    if residual_matches and residual_matches != [residual_target]:
        raise RuntimeError(f"state {NAM_RESIDUAL_CITY_STATE_ID}: id is already occupied")
    residual_provinces = " ".join(map(str, NAM_RESIDUAL_CITY_PROVINCES))
    residual_target.write_text(
        "\n".join([
            "# Generated by tools/build_adiscord_new_states.py",
            "state={",
            f"\tid={NAM_RESIDUAL_CITY_STATE_ID}",
            f'\tname="STATE_{NAM_RESIDUAL_CITY_STATE_ID}"',
            "\tresources = {",
            "\t\toil = 20",
            "\t\tchromium = 2",
            "\t}",
            f"\tprovinces={{ {residual_provinces} }}",
            "\tmanpower = 120000",
            "\tbuildings_max_level_factor = 1.000",
            "\tstate_category = town",
            "\tlocal_supplies = 3.5",
            "\thistory = {",
            "\t\towner = NAM",
            "\t\tadd_core_of = NAM",
            "\t\tvictory_points = { 2038 5 }",
            "\t\tbuildings = {",
            "\t\t\tinfrastructure = 3",
            "\t\t\tindustrial_complex = 1",
            "\t\t\tarms_factory = 2",
            "\t\t\t2038 = { naval_base = 1 }",
            "\t\t}",
            "\t}",
            "}",
            "",
        ]),
        encoding="utf-8",
        newline="\n",
    )

    _, mismatches = audit_buildings(ROOT)
    unexpected = [
        mismatch for mismatch in mismatches
        if not (
            (
                mismatch.recorded_state == 67
                and (
                    (
                        mismatch.actual_state == NAM_SVETLOGORSK_STATE_ID
                        and mismatch.province in NAM_SVETLOGORSK_PROVINCES
                    )
                    or (
                        mismatch.actual_state == NAM_RESIDUAL_CITY_STATE_ID
                        and mismatch.province in NAM_RESIDUAL_CITY_PROVINCES
                    )
                )
            )
            or (
                mismatch.recorded_state == 71
                and mismatch.actual_state == 91
                and mismatch.province == 3743
            )
        )
    ]
    if unexpected:
        raise RuntimeError(f"unrelated map/buildings state mismatches: {unexpected[:5]}")
    if mismatches:
        synchronize_buildings(ROOT, apply=True)
    ensure_nam_split_spawn_positions(ROOT)
    _, remaining = audit_buildings(ROOT)
    if remaining:
        raise RuntimeError(f"NAM split spawn-position repair drifted: {remaining[:5]}")


def ensure_history_victory_points(
    source: str, points: tuple[tuple[int, int], ...]
) -> str:
    """Set generated urban VPs while preserving every unrelated history item."""
    history_open, history_close = named_block(source, "history")
    history = source[history_open:history_close + 1]
    for province_id, value in points:
        pattern = rf"(?m)^(\s*)victory_points\s*=\s*\{{\s*{province_id}\s+\d+\s*\}}\s*$"
        if re.search(pattern, history):
            history = re.sub(
                pattern,
                rf"\1victory_points = {{ {province_id} {value} }}",
                history,
                count=1,
            )
        else:
            history = history[:-1].rstrip() + (
                f"\n\t\tvictory_points = {{ {province_id} {value} }}\n\t}}"
            )
    return source[:history_open] + history + source[history_close + 1:]


def apply_legacy_state_profiles() -> None:
    """Patch legacy Vorkerland and NAM states without discarding map data."""
    for state_id, profile in LEGACY_STATE_PROFILES.items():
        path = state_path(state_id)
        source = path.read_text(encoding="utf-8-sig", errors="strict")
        source = set_scalar(source, "manpower", str(profile["population"]))
        source = set_scalar(source, "state_category", str(profile["category"]))
        source = set_scalar(source, "buildings_max_level_factor", "1.000")
        source = set_scalar(source, "local_supplies", f"{float(profile['supplies']):.1f}")
        source = re.sub(r"(?m)^\s*impassable\s*=\s*yes\s*$\n?", "", source)
        if state_id in VORKERLAND_LEGACY_PROFILES:
            source = re.sub(
                r"(?m)^\s*set_demilitarized_zone\s*=\s*yes\s*$\n?",
                "",
                source,
            )
        source = ensure_history_buildings(source, profile)
        if state_id in GENERATED_LEGACY_VICTORY_POINTS:
            source = ensure_history_victory_points(
                source, GENERATED_LEGACY_VICTORY_POINTS[state_id]
            )
        path.write_text(source, encoding="utf-8", newline="\n")


def apply_generated_victory_point_localisation() -> None:
    """Keep generated Russian VP names BOM-safe and duplicate-free."""
    path = ROOT / "localisation" / "russian" / "victory_points_l_russian.yml"
    source = path.read_text(encoding="utf-8-sig", errors="strict")
    for province_id, name in GENERATED_VICTORY_POINT_NAMES.items():
        key = f"VICTORY_POINTS_{province_id}"
        pattern = rf'(?m)^([ \t]*){re.escape(key)}:[ \t]*"[^"]*"[ \t]*$'
        replacement = rf'\1{key}: "{name}"'
        if re.search(pattern, source):
            source = re.sub(pattern, replacement, source, count=1)
        else:
            source = source.rstrip() + f'\n {key}: "{name}"\n'
    path.write_text(source.rstrip() + "\n", encoding="utf-8-sig", newline="\n")


def apply_generated_state_name_localisation() -> None:
    """Rename generated states without touching unrelated localisation."""
    path = ROOT / "localisation" / "russian" / "state_names_l_russian.yml"
    source = path.read_text(encoding="utf-8-sig", errors="strict")
    for state_id, name in GENERATED_STATE_NAMES.items():
        key = f"STATE_{state_id}"
        pattern = rf'(?m)^([ \t]*){re.escape(key)}:[ \t]*"[^"]*"[ \t]*$'
        replacement = rf'\1{key}: "{name}"'
        if re.search(pattern, source):
            source = re.sub(pattern, replacement, source, count=1)
        else:
            source = source.rstrip() + f'\n {key}: "{name}"\n'
    path.write_text(source.rstrip() + "\n", encoding="utf-8-sig", newline="\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate A-Discord state metadata.")
    parser.parse_args()
    missing = sorted(set(range(234, 331)) - set(STARTING_OWNERS))
    if missing:
        raise RuntimeError(f"new states without a starting owner: {missing}")
    detach_northern_lighthouse()
    fill_legacy_owner_gaps()
    apply_legacy_owner_overrides()
    split_svetlogorsk_from_nam()
    for state_id, owner in sorted(STARTING_OWNERS.items()):
        state_path(state_id).write_text(render_state(state_id, owner), encoding="utf-8", newline="\n")
    apply_legacy_state_profiles()
    apply_generated_victory_point_localisation()
    apply_generated_state_name_localisation()
    print(f"Built metadata for {len(STARTING_OWNERS)} states; hand-authored flags were left untouched.")


if __name__ == "__main__":
    main()
