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
from tools.lib.adiscord_vorkerland_theatre_manifest import (
    UNITY_TOWER_NAME,
    UNITY_TOWER_PROVINCE,
    VORKERLAND_PROTECTED_LANDMARK_VPS,
    VORKERLAND_THEATRE_RETIRED_VP_IDS,
    VORKERLAND_THEATRE_VICTORY_POINTS,
    VORKERLAND_THEATRE_VP_NAME_OVERRIDES,
)
from tools.lib.paths import repository_root

ROOT = repository_root()
STATE_DIR = ROOT / "history" / "states"

NAM_SVETLOGORSK_STATE_ID = 688
NAM_SVETLOGORSK_PROVINCES = (689, 3127, 4025, 8635, 9211, 10967)
NAM_RESIDUAL_CITY_STATE_ID = 689
NAM_RESIDUAL_CITY_PROVINCES = (176, 2038, 2299, 7618, 7639, 8358)
NAM_DRYRIVER_STATE_ID = 690
EFL_MIDDLE_LOREN_STATE_ID = 691
AZH_BLACK_COAST_STATE_ID = 692
NAM_MAINLAND_STATE_RESOURCES = {
    67: {"oil": 80, "chromium": 6},
    NAM_SVETLOGORSK_STATE_ID: {"oil": 12, "chromium": 1},
    NAM_RESIDUAL_CITY_STATE_ID: {"oil": 36, "chromium": 5},
    NAM_DRYRIVER_STATE_ID: {"oil": 36, "chromium": 3},
}
NAM_ORIGINAL_MAINLAND_PROVINCES = (
    176, 334, 461, 689, 1015, 1710, 2038, 2231, 2299, 2935,
    3127, 4025, 4287, 4321, 4912, 6099, 6961, 7324, 7618, 7639,
    8058, 8351, 8358, 8445, 8635, 8888, 9016, 9116, 9211, 9641,
    10909, 10967, 11069, 11696, 11926, 11942, 12480, 12668, 12982,
)
NAM_PRE_CITY_MAINLAND_PROVINCES = tuple(
    sorted(set(NAM_ORIGINAL_MAINLAND_PROVINCES) - set(NAM_SVETLOGORSK_PROVINCES))
)
NAM_MAINLAND_AFTER_CITY_SPLIT_PROVINCES = tuple(
    sorted(
        set(NAM_ORIGINAL_MAINLAND_PROVINCES)
        - set(NAM_SVETLOGORSK_PROVINCES)
        - set(NAM_RESIDUAL_CITY_PROVINCES)
    )
)
NAM_RESOURCE_BASIN_PROVINCES = (
    334, 1710, 2935, 4287, 4321, 4912, 6099, 7324, 8351,
    8445, 8888, 9116, 10909, 11069, 11696, 11942, 12480, 12668,
)
NAM_DRYRIVER_PROVINCES = (461, 1015, 2231, 6961, 8058, 9016, 9641, 11926, 12982)
EFL_UPPER_LOREN_PROVINCES = (
    259, 324, 865, 1658, 1950, 2254, 2734, 2822, 3089, 3226,
    3977, 4014, 4096, 4175, 4237, 4339, 4717, 5651, 5766, 6150,
    6438, 7139, 7199, 7750, 7859, 8087, 8425, 9637, 9731, 10258,
    10759, 10806, 10866, 10932, 11744, 12109, 12135,
)
EFL_MIDDLE_LOREN_PROVINCES = (
    786, 797, 1411, 2473, 3046, 3176, 3730, 3833, 3916, 4060,
    4424, 5260, 5579, 6331, 7502, 8057, 8194, 8904, 9390, 9609,
    9694, 10113, 10454, 10722, 11083, 11652, 12131, 12218, 12306, 12830,
)
AZH_CORE_PROVINCES = (
    367, 643, 687, 729, 826, 1568, 2338, 2411, 2443, 4380, 5156,
    5288, 5305, 5483, 5555, 5594, 5683, 6184, 6505, 6577, 7079,
    7193, 7413, 7637, 7692, 7737, 8234, 8452, 8758, 8821, 8836,
    8958, 8990, 8997, 9013, 9119, 9633, 9798, 9909, 10077, 12458,
    12482, 12601, 12837, 12937, 13019,
)
AZH_BLACK_COAST_PROVINCES = (
    493, 601, 1360, 2264, 2362, 2802, 2804, 3464, 4089, 4678,
    5039, 5527, 5837, 6193, 6768, 7033, 7777, 8114, 8441, 8829,
    9264, 9375, 9758, 10489, 10626, 11445, 11630, 11734, 12498,
)
EFL_ORIGINAL_UPPER_LOREN_PROVINCES = tuple(sorted((*EFL_UPPER_LOREN_PROVINCES, *EFL_MIDDLE_LOREN_PROVINCES)))
AZH_ORIGINAL_PROVINCES = tuple(sorted((*AZH_CORE_PROVINCES, *AZH_BLACK_COAST_PROVINCES)))

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
    69: (367, 5),
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
    69: {"oil": 2, "chromium": 1},
    175: {"steel": 2, "aluminium": 2},
    236: {"steel": 3, "oil": 1},
    255: {"aluminium": 3, "oil": 1},
    263: {"tungsten": 2, "steel": 2},
    269: {"oil": 3, "chromium": 1},
    285: {"tungsten": 2, "aluminium": 2},
    291: {"steel": 3, "chromium": 1},
    299: {"aluminium": 3, "chromium": 1},
}
NAM_COALITION_FRONT_RESOURCES = {
    69: STATE_RESOURCES[69],
    AZH_BLACK_COAST_STATE_ID: {"oil": 1, "chromium": 1},
}

# The central Vorkerland theatre used to have only one steel-bearing state,
# which then passes to PWR during the opening map setup.  Keep deposits scarce
# and concentrated, but give each major industrial bloc one real supply source.
# The Unity Tower is a sealed administrative ruin rather than an extractive
# site, so its former steel deposit is deliberately absent.
VORKERLAND_STATE_RESOURCES = {
    33: {"steel": 16},
    38: {"steel": 10},
    72: {"steel": 8},
    73: {"steel": 6},
    74: {"steel": 8},
    80: {"steel": 8},
    102: {"steel": 10},
    105: {"steel": 16},
    121: {"steel": 12},
    145: {"steel": 6},
    197: {"steel": 8},
    306: {"steel": 6},
}

IVANLAND_STATE_RESOURCES = {
    25: {"steel": 24},
    99: {"steel": 16},
}

AFRELA_STATE_RESOURCES = {
    326: {"steel": 10},
}

DIRTY_STATE_RESOURCES = {
    state_id: {"steel": 4}
    for state_id in (49, 152, 169, 173, 177, 181)
}

REGIONAL_STATE_RESOURCES = {
    **VORKERLAND_STATE_RESOURCES,
    **IVANLAND_STATE_RESOURCES,
    **AFRELA_STATE_RESOURCES,
    **DIRTY_STATE_RESOURCES,
}

ALL_STATE_RESOURCES = {
    **STATE_RESOURCES,
    **REGIONAL_STATE_RESOURCES,
}

# Generated naval OOBs require these real coastal bases. Keeping them in this
# builder prevents a state regeneration from silently deleting the fleets' ports.
GENERATED_STATE_BUILDINGS = {
    AZH_BLACK_COAST_STATE_ID: {"dockyard": 1},
}
GENERATED_PROVINCE_BUILDINGS = {
    AZH_BLACK_COAST_STATE_ID: ((493, "naval_base", 1),),
}

# Cities that were victory points before the Vorkerland state split. Keep the
# points on their actual urban provinces instead of losing them during rebuild.
VORKERLAND_CENTRES = {
    306: (16643, 5),
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
    306: {"population": 1_400_000, "category": "large_town", "infrastructure": 3, "industry": 2, "military": 1, "supplies": 3.0, "custom_buildings": {"ADISCORD_rare_components_plant": 1}},
    307: {"population": 800_000, "category": "town", "infrastructure": 2, "industry": 1, "supplies": 2.0},
    308: {"population": 1_100_000, "category": "large_town", "infrastructure": 3, "industry": 1, "supplies": 2.5},
    309: {"population": 800_000, "category": "town", "infrastructure": 3, "industry": 1, "supplies": 2.0},
    310: {"population": 400_000, "category": "rural", "infrastructure": 2, "industry": 1, "supplies": 2.0},
    311: {"population": 950_000, "category": "town", "infrastructure": 3, "industry": 1, "supplies": 2.5},
    312: {"population": 850_000, "category": "town", "infrastructure": 3, "industry": 1, "military": 1, "supplies": 3.0},
    313: {"population": 750_000, "category": "town", "infrastructure": 3, "industry": 1, "supplies": 3.0},
    314: {"population": 750_000, "category": "town", "infrastructure": 3, "industry": 1, "supplies": 3.0},
    315: {"population": 550_000, "category": "rural", "infrastructure": 2, "industry": 1, "supplies": 2.0},
    316: {"population": 500_000, "category": "rural", "infrastructure": 2, "industry": 1, "supplies": 2.0},
    317: {"population": 700_000, "category": "town", "infrastructure": 3, "industry": 1, "military": 1, "supplies": 3.0},
    318: {"population": 750_000, "category": "town", "infrastructure": 3, "industry": 1, "military": 1, "supplies": 3.0},
    319: {"population": 500_000, "category": "rural", "infrastructure": 2, "industry": 1, "supplies": 2.0},
    320: {"population": 500_000, "category": "rural", "infrastructure": 2, "industry": 0, "supplies": 1.5},
    321: {"population": 450_000, "category": "rural", "infrastructure": 2, "industry": 1, "supplies": 2.0},
    322: {"population": 600_000, "category": "town", "infrastructure": 3, "industry": 1, "supplies": 2.5},
    323: {"population": 750_000, "category": "town", "infrastructure": 2, "industry": 1, "supplies": 2.0},
    324: {"population": 700_000, "category": "town", "infrastructure": 3, "industry": 2, "supplies": 3.0},
    325: {"population": 450_000, "category": "rural", "infrastructure": 2, "industry": 1, "supplies": 2.0},
    327: {"population": 600_000, "category": "town", "infrastructure": 3, "industry": 1, "supplies": 2.0, "custom_buildings": {"ADISCORD_rare_alloy_foundry": 1}},
    328: {"population": 500_000, "category": "rural", "infrastructure": 2, "industry": 1, "supplies": 2.0},
}

# Vorkerland's legacy state files predate the Nudge split.  These values keep
# every civil-war front inhabited and supplied without flattening the old
# resources, victory points, bunkers and state ownership into generated data.
VORKERLAND_LEGACY_PROFILES = {
    40: {"population": 20_000, "category": "megalopolis", "infrastructure": 5, "civilian": 6, "military": 4, "air_base": 3, "supplies": 10.0, "custom_buildings": {"ADISCORD_science_center": 1}},
    71: {"population": 800_000, "category": "town", "infrastructure": 3, "civilian": 1, "military": 1, "supplies": 3.0},
    72: {"population": 850_000, "category": "town", "infrastructure": 3, "civilian": 1, "military": 2, "supplies": 3.0},
    73: {"population": 1_300_000, "category": "town", "infrastructure": 3, "civilian": 2, "military": 1, "supplies": 3.5},
    74: {"population": 1_300_000, "category": "large_town", "infrastructure": 4, "civilian": 3, "military": 2, "air_base": 1, "supplies": 4.5},
    76: {"population": 950_000, "category": "town", "infrastructure": 3, "civilian": 1, "military": 1, "supplies": 3.0},
    80: {"population": 1_350_000, "category": "large_town", "infrastructure": 3, "civilian": 2, "military": 1, "supplies": 3.5},
    90: {"population": 450_000, "category": "rural", "infrastructure": 2, "civilian": 1, "military": 1, "supplies": 2.5},
    91: {"population": 450_000, "category": "rural", "infrastructure": 2, "civilian": 1, "supplies": 2.5},
    93: {"population": 500_000, "category": "rural", "infrastructure": 2, "civilian": 1, "military": 1, "supplies": 2.5},
    94: {"population": 500_000, "category": "rural", "infrastructure": 2, "civilian": 1, "supplies": 2.5},
    144: {"population": 450_000, "category": "rural", "infrastructure": 2, "civilian": 1, "supplies": 2.0},
    145: {"population": 750_000, "category": "town", "infrastructure": 3, "civilian": 1, "military": 1, "supplies": 3.0},
    194: {"population": 850_000, "category": "town", "infrastructure": 3, "civilian": 1, "military": 1, "supplies": 3.0},
    195: {"population": 800_000, "category": "town", "infrastructure": 3, "civilian": 1, "military": 1, "supplies": 3.0},
    196: {"population": 750_000, "category": "town", "infrastructure": 3, "civilian": 1, "military": 1, "supplies": 3.0},
    197: {"population": 1_400_000, "category": "large_town", "infrastructure": 4, "civilian": 3, "military": 1, "air_base": 1, "supplies": 4.5},
    198: {"population": 800_000, "category": "town", "infrastructure": 3, "civilian": 2, "military": 1, "supplies": 3.5},
    199: {"population": 750_000, "category": "town", "infrastructure": 3, "civilian": 1, "military": 1, "supplies": 3.0},
}

# These border states must remain mobilizable when the collapse fronts open;
# a history-level DMZ survives the ownership transfer and freezes those wars.
PWR_PRE_COLLAPSE_DMZ_STATES = frozenset()

# NAM begins with one mainland split into the Svetlogorsk uprising district,
# the broad resource basin, and a compact southern port which survives the SLF
# victory settlement. Totals stay unchanged across the three states.
NAM_STATE_PROFILES = {
    67: {"population": 480_000, "category": "large_city", "infrastructure": 4, "civilian": 2, "military": 1, "air_base": 1, "supplies": 5.0},
    225: {"population": 220_000, "category": "town", "infrastructure": 3, "civilian": 1, "military": 1, "supplies": 3.0},
    226: {"population": 140_000, "category": "rural", "infrastructure": 2, "civilian": 1, "supplies": 2.5},
    227: {"population": 180_000, "category": "rural", "infrastructure": 2, "civilian": 1, "supplies": 2.5},
    228: {"population": 300_000, "category": "town", "infrastructure": 3, "civilian": 2, "military": 1, "supplies": 3.5},
    229: {"population": 120_000, "category": "rural", "infrastructure": 2, "civilian": 1, "supplies": 2.5},
    230: {"population": 100_000, "category": "rural", "infrastructure": 2, "civilian": 1, "supplies": 2.5},
    231: {"population": 160_000, "category": "rural", "infrastructure": 2, "civilian": 1, "military": 1, "supplies": 2.5},
    NAM_SVETLOGORSK_STATE_ID: {"population": 90_000, "category": "town", "infrastructure": 3, "civilian": 1, "military": 0, "air_base": 1, "supplies": 3.0, "custom_buildings": {"dockyard": 1}},
    NAM_RESIDUAL_CITY_STATE_ID: {"population": 120_000, "category": "town", "infrastructure": 3, "civilian": 1, "military": 2, "supplies": 3.5},
    NAM_DRYRIVER_STATE_ID: {"population": 270_000, "category": "town", "infrastructure": 3, "civilian": 1, "supplies": 3.5},
}

# The three states facing NAM's resource basin need enough population and
# local logistics for the restoration coalition to launch a real offensive.
NAM_COALITION_FRONT_PROFILES = {
    68: {"population": 520_000, "category": "town", "infrastructure": 3, "civilian": 2, "military": 1, "supplies": 4.0},
    69: {"population": 380_000, "category": "town", "infrastructure": 3, "civilian": 2, "military": 1, "air_base": 1, "supplies": 4.0},
    70: {"population": 350_000, "category": "town", "infrastructure": 3, "civilian": 2, "military": 1, "supplies": 4.0},
    EFL_MIDDLE_LOREN_STATE_ID: {"population": 280_000, "category": "town", "infrastructure": 3, "civilian": 1, "supplies": 3.5},
    AZH_BLACK_COAST_STATE_ID: {"population": 240_000, "category": "town", "infrastructure": 3, "civilian": 1, "supplies": 3.5, "custom_buildings": {"dockyard": 1}},
}

# Every state owned and cored by Ivanland at game start receives a coherent
# demographic/logistics baseline.  The existing hub in state 25 and its rail
# spur through states 100 and 99 remain authoritative, so the frontier relies
# on infrastructure plus local supply rather than a redundant second hub.
IVANLAND_STATE_PROFILES = {
    25: {"population": 4_000_000, "category": "metropolis", "infrastructure": 5, "civilian": 6, "military": 4, "air_base": 3, "supplies": 8.0},
    92: {"population": 480_000, "category": "rural", "infrastructure": 3, "civilian": 1, "military": 1, "supplies": 4.0},
    95: {"population": 780_000, "category": "town", "infrastructure": 4, "civilian": 2, "military": 2, "air_base": 1, "supplies": 5.0},
    96: {"population": 720_000, "category": "town", "infrastructure": 4, "civilian": 2, "military": 2, "supplies": 5.0},
    97: {"population": 880_000, "category": "town", "infrastructure": 3, "civilian": 2, "military": 1, "supplies": 3.5},
    98: {"population": 1_450_000, "category": "large_town", "infrastructure": 4, "civilian": 3, "military": 2, "supplies": 4.5},
    99: {"population": 1_650_000, "category": "large_city", "infrastructure": 4, "civilian": 4, "military": 3, "air_base": 2, "supplies": 5.0},
    100: {"population": 1_200_000, "category": "large_town", "infrastructure": 4, "civilian": 3, "military": 2, "supplies": 4.0},
    101: {"population": 600_000, "category": "town", "infrastructure": 3, "civilian": 2, "military": 1, "supplies": 3.0},
    127: {"population": 750_000, "category": "town", "infrastructure": 3, "civilian": 2, "military": 1, "supplies": 3.0},
    128: {"population": 360_000, "category": "rural", "infrastructure": 2, "civilian": 1, "supplies": 2.0},
    129: {"population": 550_000, "category": "rural", "infrastructure": 3, "civilian": 1, "military": 1, "supplies": 3.0},
    130: {"population": 650_000, "category": "town", "infrastructure": 3, "civilian": 2, "military": 1, "supplies": 3.5},
    131: {"population": 680_000, "category": "town", "infrastructure": 3, "civilian": 2, "military": 1, "supplies": 3.5},
    132: {"population": 500_000, "category": "rural", "infrastructure": 3, "civilian": 1, "military": 1, "supplies": 3.0},
    164: {"population": 400_000, "category": "rural", "infrastructure": 2, "civilian": 1, "supplies": 2.5},
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

# The contaminated zone is sparse, not empty.  Capitals and a few surviving
# workshop/rail nodes support each successor republic; exposed wasteland
# corridors in EXZ_REMAINDER_GROUPS deliberately remain at manpower 1.
DIRTY_REPUBLIC_STATE_PROFILES = {
    49: {"population": 220_000, "category": "town", "infrastructure": 3, "civilian": 2, "military": 1, "supplies": 2.5},
    51: {"population": 150_000, "category": "rural", "infrastructure": 2, "supplies": 1.5},
    155: {"population": 120_000, "category": "rural", "infrastructure": 2, "civilian": 1, "supplies": 1.5},
    176: {"population": 90_000, "category": "rural", "infrastructure": 1, "supplies": 1.0},
    187: {"population": 80_000, "category": "rural", "infrastructure": 0, "supplies": 0.5},
    191: {"population": 90_000, "category": "rural", "infrastructure": 0, "supplies": 0.5},
    125: {"population": 120_000, "category": "rural", "infrastructure": 2, "supplies": 1.5},
    177: {"population": 220_000, "category": "town", "infrastructure": 3, "civilian": 2, "military": 1, "supplies": 2.5},
    188: {"population": 70_000, "category": "rural", "infrastructure": 1, "supplies": 1.0},
    192: {"population": 70_000, "category": "rural", "infrastructure": 0, "supplies": 0.5},
    208: {"population": 60_000, "category": "rural", "infrastructure": 0, "supplies": 0.5},
    213: {"population": 100_000, "category": "rural", "infrastructure": 2, "civilian": 1, "supplies": 1.5},
    214: {"population": 50_000, "category": "rural", "infrastructure": 0, "supplies": 0.5},
    215: {"population": 70_000, "category": "rural", "infrastructure": 1, "supplies": 1.0},
    216: {"population": 60_000, "category": "rural", "infrastructure": 0, "supplies": 0.5},
    217: {"population": 70_000, "category": "rural", "infrastructure": 0, "supplies": 0.5},
    220: {"population": 80_000, "category": "rural", "infrastructure": 0, "military": 1, "supplies": 0.5},
    152: {"population": 220_000, "category": "town", "infrastructure": 3, "civilian": 2, "military": 1, "supplies": 2.5},
    153: {"population": 120_000, "category": "rural", "infrastructure": 2, "civilian": 1, "supplies": 1.5},
    154: {"population": 100_000, "category": "rural", "infrastructure": 1, "supplies": 1.0},
    189: {"population": 80_000, "category": "rural", "infrastructure": 1, "supplies": 1.0},
    190: {"population": 70_000, "category": "rural", "infrastructure": 0, "supplies": 0.5},
    219: {"population": 70_000, "category": "rural", "infrastructure": 0, "supplies": 0.5},
    221: {"population": 60_000, "category": "rural", "infrastructure": 0, "supplies": 0.5},
    222: {"population": 80_000, "category": "rural", "infrastructure": 0, "supplies": 0.5},
    224: {"population": 90_000, "category": "rural", "infrastructure": 0, "supplies": 0.5},
    167: {"population": 80_000, "category": "rural", "infrastructure": 1, "civilian": 1, "supplies": 1.0},
    168: {"population": 160_000, "category": "town", "infrastructure": 2, "civilian": 1, "supplies": 1.5},
    169: {"population": 220_000, "category": "town", "infrastructure": 3, "civilian": 1, "military": 1, "supplies": 2.5},
    171: {"population": 80_000, "category": "rural", "infrastructure": 1, "supplies": 1.0},
    184: {"population": 70_000, "category": "rural", "infrastructure": 0, "supplies": 0.5},
    185: {"population": 50_000, "category": "rural", "infrastructure": 0, "supplies": 0.5},
    203: {"population": 60_000, "category": "rural", "infrastructure": 0, "supplies": 0.5},
    178: {"population": 60_000, "category": "rural", "infrastructure": 1, "supplies": 1.0},
    180: {"population": 60_000, "category": "rural", "infrastructure": 1, "supplies": 1.0},
    181: {"population": 220_000, "category": "town", "infrastructure": 3, "civilian": 2, "military": 1, "supplies": 2.5},
    182: {"population": 70_000, "category": "rural", "infrastructure": 0, "supplies": 0.5},
    183: {"population": 60_000, "category": "rural", "infrastructure": 0, "supplies": 0.5},
    193: {"population": 100_000, "category": "rural", "infrastructure": 2, "civilian": 1, "supplies": 1.5},
    206: {"population": 50_000, "category": "rural", "infrastructure": 0, "supplies": 0.5},
    207: {"population": 60_000, "category": "rural", "infrastructure": 0, "supplies": 0.5},
    165: {"population": 60_000, "category": "rural", "infrastructure": 1, "supplies": 1.0},
    166: {"population": 60_000, "category": "rural", "infrastructure": 1, "supplies": 1.0},
    172: {"population": 60_000, "category": "rural", "infrastructure": 0, "supplies": 0.5},
    173: {"population": 220_000, "category": "town", "infrastructure": 3, "civilian": 1, "military": 1, "supplies": 2.5},
    204: {"population": 50_000, "category": "rural", "infrastructure": 0, "supplies": 0.5},
    205: {"population": 60_000, "category": "rural", "infrastructure": 0, "supplies": 0.5},
    209: {"population": 60_000, "category": "rural", "infrastructure": 0, "supplies": 0.5},
    210: {"population": 70_000, "category": "rural", "infrastructure": 2, "civilian": 1, "supplies": 1.5},
    211: {"population": 80_000, "category": "rural", "infrastructure": 2, "civilian": 1, "supplies": 1.5},
    212: {"population": 70_000, "category": "rural", "infrastructure": 0, "supplies": 0.5},
}

# Legacy states moved by ADISCORD_vorkerland_apply_initial_map and its setup
# effects must support the armies spawned there. The Unity Tower is a sealed
# complex with a 20k custodial population; its former 11.48m residents are
# evenly dispersed across the six adjacent metropolitan districts, with the
# two surplus people assigned to states 33 and 34. Empty shells and obviously
# under-classified cities otherwise get explicit demographic and industrial
# profiles.  Advanced-material plants share state slots and reduce
# local_building_slots_factor themselves.  buildings_max_level_factor does not
# add shared slots, so their host category and starting factory count must fit
# the post-modifier category capacity directly.
VORKERLAND_INITIAL_MAP_LEGACY_PROFILES = {
    27: {"population": 2_000_000, "category": "large_town", "infrastructure": 3, "civilian": 2, "military": 1, "supplies": 3.0, "custom_buildings": {"ADISCORD_rare_components_plant": 1}},
    32: {"population": 7_000_000, "category": "megalopolis", "infrastructure": 5, "civilian": 2, "military": 3, "air_base": 3, "supplies": 10.0, "custom_buildings": {"ADISCORD_unity_tower_complex": 1, "ADISCORD_business_center": 1}},
    33: {"population": 10_913_334, "category": "megalopolis", "infrastructure": 5, "civilian": 7, "military": 3, "supplies": 10.0, "custom_buildings": {"ADISCORD_rare_alloy_foundry": 1}},
    34: {"population": 4_913_334, "category": "megalopolis", "infrastructure": 4, "civilian": 2, "military": 1, "supplies": 5.0},
    35: {"population": 6_113_333, "category": "large_city", "infrastructure": 5, "civilian": 5, "military": 2, "supplies": 6.0},
    36: {"population": 8_413_333, "category": "metropolis", "infrastructure": 5, "civilian": 4, "supplies": 7.0},
    37: {"population": 3_200_000, "category": "large_city", "infrastructure": 5, "civilian": 6, "supplies": 5.0},
    38: {"population": 3_713_333, "category": "metropolis", "infrastructure": 5, "civilian": 6, "military": 2, "air_base": 2, "supplies": 6.0, "custom_buildings": {"ADISCORD_rare_components_plant": 1}},
    39: {"population": 7_413_333, "category": "metropolis", "infrastructure": 5, "civilian": 2, "military": 7, "supplies": 7.0},
    75: {"population": 9_500_000, "category": "megalopolis", "infrastructure": 5, "civilian": 5, "military": 3, "air_base": 3, "supplies": 8.0},
    79: {"population": 1_200_000, "category": "large_town", "infrastructure": 3, "civilian": 2, "military": 1, "supplies": 3.0, "custom_buildings": {"ADISCORD_rare_alloy_foundry": 1}},
    81: {"population": 2_200_000, "category": "large_city", "infrastructure": 5, "civilian": 3, "military": 2, "air_base": 2, "supplies": 5.0},
    82: {"population": 800_000, "category": "town", "infrastructure": 2, "civilian": 1, "military": 1, "supplies": 4.0},
    102: {"population": 11_500_000, "category": "megalopolis", "infrastructure": 5, "civilian": 7, "military": 5, "air_base": 3, "supplies": 10.0},
    104: {"population": 3_500_000, "category": "metropolis", "infrastructure": 4, "civilian": 4, "military": 2, "air_base": 2, "supplies": 6.0},
    105: {"population": 9_800_000, "category": "megalopolis", "infrastructure": 5, "civilian": 6, "military": 4, "air_base": 3, "supplies": 10.0, "custom_buildings": {"ADISCORD_techlar_metallurgical_combine": 1, "ADISCORD_industrial_cluster": 1}},
    106: {"population": 3_800_000, "category": "large_city", "infrastructure": 4, "civilian": 3, "military": 2, "air_base": 2, "supplies": 5.0},
    107: {"population": 1_200_000, "category": "town", "infrastructure": 2, "civilian": 1, "supplies": 2.5},
    108: {"population": 650_000, "category": "rural", "infrastructure": 3, "civilian": 1, "supplies": 2.5},
    109: {"population": 900_000, "category": "town", "infrastructure": 3, "civilian": 2, "military": 1, "supplies": 3.5},
    110: {"population": 1_500_000, "category": "large_town", "infrastructure": 4, "civilian": 3, "military": 1, "air_base": 1, "supplies": 4.5},
    111: {"population": 1_000_000, "category": "town", "infrastructure": 4, "civilian": 2, "military": 1, "supplies": 4.0},
    112: {"population": 1_530_000, "category": "large_city", "infrastructure": 3, "civilian": 2, "military": 1, "supplies": 4.0},
    113: {"population": 724_000, "category": "town", "infrastructure": 3, "civilian": 2, "military": 1, "supplies": 3.5},
    114: {"population": 432_000, "category": "town", "infrastructure": 3, "civilian": 1, "military": 1, "supplies": 3.0},
    115: {"population": 220_000, "category": "rural", "infrastructure": 2, "civilian": 1, "supplies": 2.0},
    116: {"population": 180_000, "category": "rural", "infrastructure": 2, "civilian": 1, "supplies": 2.0},
    117: {"population": 210_000, "category": "rural", "infrastructure": 2, "civilian": 1, "supplies": 2.0},
    # States 118-120 are now owned by the Ainholm mandate/Orval setup. Their
    # complete profiles belong to build_adiscord_ainholm_mandate.py; keeping
    # old theatre defaults here would silently overwrite that generator.
    121: {"population": 3_000_000, "category": "large_city", "infrastructure": 4, "civilian": 3, "military": 2, "supplies": 5.0},
    122: {"population": 1_500_000, "category": "large_town", "infrastructure": 4, "civilian": 2, "military": 1, "supplies": 4.0},
    123: {"population": 2_400_000, "category": "large_city", "infrastructure": 4, "civilian": 3, "military": 2, "supplies": 5.0},
    124: {"population": 650_000, "category": "rural", "infrastructure": 3, "civilian": 1, "military": 1, "supplies": 2.5},
    200: {"population": 700_000, "category": "town", "infrastructure": 2, "civilian": 1, "supplies": 2.0},
    201: {"population": 800_000, "category": "town", "infrastructure": 2, "civilian": 1, "supplies": 2.0},
    202: {"population": 650_000, "category": "rural", "infrastructure": 2, "civilian": 1, "supplies": 2.0},
}

VORKERLAND_LEGACY_VICTORY_POINTS = {
    27: ((16614, 3),),
    82: ((8059, 5),),
    74: ((16585, 5),),
    197: ((16623, 10),),
    104: ((7778, 8), (16564, 3), (16583, 2)),
    105: ((16589, 12), (16565, 5), (16577, 3), (16581, 2)),
}

VORKERLAND_VICTORY_POINT_NAMES = {
    6713: "Гранд-Воркенсберг",
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
    67: ((1710, 2), (6099, 3)),
    68: ((259, 5), (6150, 2)),
    69: ((367, 5), (8234, 2)),
    70: ((2986, 2), (6495, 4)),
    NAM_SVETLOGORSK_STATE_ID: ((689, 3),),
    NAM_RESIDUAL_CITY_STATE_ID: ((2038, 5),),
    NAM_DRYRIVER_STATE_ID: ((8058, 2), (9016, 2)),
    EFL_MIDDLE_LOREN_STATE_ID: ((8057, 3),),
    AZH_BLACK_COAST_STATE_ID: ((493, 3), (5039, 2)),
}

AFRELA_VICTORY_POINT_NAMES = {
    4218: "Афрела",
    5162: "Мирель",
    7920: "Таверан",
    11546: "Апрельская Гавань",
    16626: "Дальрен",
}

NAM_VICTORY_POINT_NAMES = {
    1710: "Высокое",
    6099: "Ключевск",
    8058: "Рудный",
    9016: "Сухоречье",
    259: "Эфлор",
    6150: "Высокий Лорен",
    367: "Ажар",
    493: "Чёрная гавань",
    8234: "Карас",
    2986: "Фенн",
    6495: "Лорен",
    8057: "Морен",
    5039: "Сайр",
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
    **VORKERLAND_THEATRE_VP_NAME_OVERRIDES,
}

VORKERLAND_STATE_NAMES = {
    40: "Башня Единства",
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
    NAM_DRYRIVER_STATE_ID: "Сухоречье",
    EFL_MIDDLE_LOREN_STATE_ID: "Средний Лорен",
    AZH_BLACK_COAST_STATE_ID: "Чёрное побережье",
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
    **DIRTY_REPUBLIC_STATE_PROFILES,
    # Afrela owns 113-114, which were also covered by the broad 106-124
    # theatre audit. Country-specific profiles intentionally take precedence.
    **AFRELA_STATE_PROFILES,
}

# Sealed landmarks remain physically impassable even when their surrounding
# legacy-state metadata is refreshed. State 125 is the reactor exclusion zone;
# RZA uses state 177, not the sealed reactor site, as its capital.
IMPASSABLE_LEGACY_STATE_IDS = frozenset({40, 125})

# These dense legacy states already contain other slot-sharing buildings.  Their
# factory values are exact budgets, not minima: retaining higher historical
# values would overflow the category capacity after landmarks are applied.
EXACT_LEGACY_FACTORY_STATE_IDS = frozenset({32, 33, 34, 35, 105})

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
        lines.extend(
            f"{building} = {int(level)}"
            for building, level in profile.get("custom_buildings", {}).items()
        )
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
    if state_id in VORKERLAND_THEATRE_VICTORY_POINTS:
        for province, value in VORKERLAND_THEATRE_VICTORY_POINTS[state_id]:
            if province not in provinces:
                raise RuntimeError(
                    f"state {state_id}: theatre VP {province} is outside the state"
                )
            history.append(f"\t\tvictory_points = {{ {province} {value} }}")
    elif state_id in centres:
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
    if state_id in ALL_STATE_RESOURCES:
        resource_block = ["\tresources = {"]
        resource_block.extend(
            f"\t\t{resource} = {amount}"
            for resource, amount in ALL_STATE_RESOURCES[state_id].items()
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
    """Set one top-level state scalar and remove stale duplicate declarations."""
    pattern = rf"(?m)^([ \t]*){re.escape(key)}[ \t]*=[ \t]*[^\s#]+[ \t]*$"
    seen = False

    def replace(match: re.Match[str]) -> str:
        nonlocal seen
        if seen:
            return ""
        seen = True
        return f"{match.group(1)}{key} = {value}"

    updated = re.sub(pattern, replace, source)
    if seen:
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
    minima.update({
        str(building): int(level)
        for building, level in profile.get("custom_buildings", {}).items()
    })
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


def ensure_state_resources(source: str, resources: dict[str, int]) -> str:
    """Set selected deposits exactly while preserving every unrelated resource."""
    resource_match = re.search(r"(?m)^\s*resources\s*=\s*\{", source)
    if resource_match:
        opening = source.find("{", resource_match.start(), resource_match.end())
        closing = matching_brace(source, opening)
        block = source[opening:closing + 1]
    else:
        history = re.search(r"(?m)^\s*history\s*=", source)
        if not history:
            raise RuntimeError("cannot insert resources: state has no history block")
        rendered = "\tresources = {\n\t}\n"
        source = source[:history.start()] + rendered + source[history.start():]
        resource_match = re.search(r"(?m)^\s*resources\s*=\s*\{", source)
        assert resource_match is not None
        opening = source.find("{", resource_match.start(), resource_match.end())
        closing = matching_brace(source, opening)
        block = source[opening:closing + 1]

    for resource, value in resources.items():
        pattern = rf"(?m)^([ \t]*){re.escape(resource)}\s*=\s*-?\d+\s*$"
        if re.search(pattern, block):
            block = re.sub(pattern, rf"\1{resource} = {int(value)}", block, count=1)
        else:
            block = block[:-1].rstrip() + f"\n\t\t{resource} = {int(value)}\n\t}}"
    return source[:opening] + block + source[closing + 1:]


def remove_state_resource(source: str, resource: str) -> str:
    """Remove one exhausted state deposit, retaining all other resources."""
    resource_match = re.search(r"(?m)^\s*resources\s*=\s*\{", source)
    if not resource_match:
        return source
    opening = source.find("{", resource_match.start(), resource_match.end())
    closing = matching_brace(source, opening)
    block = source[opening:closing + 1]
    block = re.sub(
        rf"(?m)^[ \t]*{re.escape(resource)}\s*=\s*-?\d+\s*\r?\n?",
        "",
        block,
    )
    if not re.search(r"(?m)^\s*[A-Za-z_]+\s*=", block):
        return source[:resource_match.start()] + source[closing + 1:]
    return source[:opening] + block + source[closing + 1:]


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


def write_resource_war_state(
    state_id: int,
    filename: str,
    provinces: tuple[int, ...],
    owner: str,
    profile: dict[str, object],
    resources: dict[str, int] | None,
    victory_points: tuple[tuple[int, int], ...],
    province_buildings: tuple[tuple[int, str, int], ...] = (),
) -> None:
    """Write one generated NAM-war state from its explicit, reviewed manifest."""
    target = STATE_DIR / filename
    matches = sorted(STATE_DIR.glob(f"{state_id}-*.txt"))
    if matches and matches != [target]:
        raise RuntimeError(f"state {state_id}: id is already occupied by {matches}")

    province_lines = [
        "\t\t" + " ".join(map(str, provinces[start:start + 12]))
        for start in range(0, len(provinces), 12)
    ]
    lines = [
        "# Generated by tools/build_adiscord_new_states.py",
        "state={",
        f"\tid={state_id}",
        f'\tname="STATE_{state_id}"',
    ]
    if resources:
        lines.append("\tresources = {")
        lines.extend(f"\t\t{resource} = {amount}" for resource, amount in resources.items())
        lines.append("\t}")
    lines.extend([
        "\tprovinces={",
        *province_lines,
        "\t}",
        f"\tmanpower = {int(profile['population'])}",
        "\tbuildings_max_level_factor = 1.000",
        f"\tstate_category = {profile['category']}",
        f"\tlocal_supplies = {float(profile['supplies']):.1f}",
        "\thistory = {",
        f"\t\towner = {owner}",
        f"\t\tadd_core_of = {owner}",
    ])
    lines.extend(
        f"\t\tvictory_points = {{ {province_id} {value} }}"
        for province_id, value in victory_points
    )
    state_buildings = {
        "infrastructure": int(profile["infrastructure"]),
        "industrial_complex": int(profile.get("civilian", 0)),
        "arms_factory": int(profile.get("military", 0)),
        "air_base": int(profile.get("air_base", 0)),
        **{
            str(building): int(level)
            for building, level in profile.get("custom_buildings", {}).items()
        },
    }
    lines.append("\t\tbuildings = {")
    lines.extend(
        f"\t\t\t{building} = {level}"
        for building, level in state_buildings.items()
        if level
    )
    lines.extend(
        f"\t\t\t{province_id} = {{ {building} = {level} }}"
        for province_id, building, level in province_buildings
    )
    lines.extend(["\t\t}", "\t}", "}", ""])
    target.write_text("\n".join(lines), encoding="utf-8", newline="\n")


def split_svetlogorsk_from_nam() -> None:
    """Create the connected nine-state NAM resource-war theatre."""
    current_manifests = {
        67: {
            frozenset(NAM_ORIGINAL_MAINLAND_PROVINCES),
            frozenset(NAM_PRE_CITY_MAINLAND_PROVINCES),
            frozenset(NAM_MAINLAND_AFTER_CITY_SPLIT_PROVINCES),
            frozenset(NAM_RESOURCE_BASIN_PROVINCES),
        },
        68: {frozenset(EFL_ORIGINAL_UPPER_LOREN_PROVINCES), frozenset(EFL_UPPER_LOREN_PROVINCES)},
        69: {frozenset(AZH_ORIGINAL_PROVINCES), frozenset(AZH_CORE_PROVINCES)},
    }
    for state_id, allowed in current_manifests.items():
        source = state_path(state_id).read_text(encoding="utf-8-sig", errors="strict")
        match = re.search(r"provinces\s*=\s*\{([^}]*)\}", source, re.DOTALL)
        if not match:
            raise RuntimeError(f"state {state_id}: missing provinces block")
        current = frozenset(map(int, re.findall(r"\d+", match.group(1))))
        if current not in allowed:
            raise RuntimeError(f"state {state_id}: resource-war split manifest drifted")

    definitions = (
        (67, "67-67.txt", NAM_RESOURCE_BASIN_PROVINCES, "NAM", NAM_STATE_PROFILES[67], NAM_MAINLAND_STATE_RESOURCES[67]),
        (68, "68-68.txt", EFL_UPPER_LOREN_PROVINCES, "EFL", NAM_COALITION_FRONT_PROFILES[68], None),
        (69, "69-69.txt", AZH_CORE_PROVINCES, "AZH", NAM_COALITION_FRONT_PROFILES[69], STATE_RESOURCES[69]),
        (NAM_SVETLOGORSK_STATE_ID, "688-Svetlogorsk.txt", NAM_SVETLOGORSK_PROVINCES, "NAM", NAM_STATE_PROFILES[NAM_SVETLOGORSK_STATE_ID], NAM_MAINLAND_STATE_RESOURCES[NAM_SVETLOGORSK_STATE_ID]),
        (NAM_RESIDUAL_CITY_STATE_ID, "689-South-Coast.txt", NAM_RESIDUAL_CITY_PROVINCES, "NAM", NAM_STATE_PROFILES[NAM_RESIDUAL_CITY_STATE_ID], NAM_MAINLAND_STATE_RESOURCES[NAM_RESIDUAL_CITY_STATE_ID]),
        (NAM_DRYRIVER_STATE_ID, "690-Dryriver.txt", NAM_DRYRIVER_PROVINCES, "NAM", NAM_STATE_PROFILES[NAM_DRYRIVER_STATE_ID], NAM_MAINLAND_STATE_RESOURCES[NAM_DRYRIVER_STATE_ID]),
        (EFL_MIDDLE_LOREN_STATE_ID, "691-Middle-Loren.txt", EFL_MIDDLE_LOREN_PROVINCES, "EFL", NAM_COALITION_FRONT_PROFILES[EFL_MIDDLE_LOREN_STATE_ID], None),
        (AZH_BLACK_COAST_STATE_ID, "692-Black-Coast.txt", AZH_BLACK_COAST_PROVINCES, "AZH", NAM_COALITION_FRONT_PROFILES[AZH_BLACK_COAST_STATE_ID], NAM_COALITION_FRONT_RESOURCES[AZH_BLACK_COAST_STATE_ID]),
    )
    province_buildings = {
        NAM_SVETLOGORSK_STATE_ID: ((689, "naval_base", 2),),
        NAM_RESIDUAL_CITY_STATE_ID: ((2038, "naval_base", 1),),
        AZH_BLACK_COAST_STATE_ID: GENERATED_PROVINCE_BUILDINGS[AZH_BLACK_COAST_STATE_ID],
    }
    for state_id, filename, provinces, owner, profile, resources in definitions:
        write_resource_war_state(
            state_id,
            filename,
            tuple(provinces),
            owner,
            profile,
            resources,
            NAM_LEGACY_VICTORY_POINTS[state_id],
            province_buildings.get(state_id, ()),
        )

    _, mismatches = audit_buildings(ROOT)
    expected_moves = {
        (67, NAM_SVETLOGORSK_STATE_ID): set(NAM_SVETLOGORSK_PROVINCES),
        (67, NAM_RESIDUAL_CITY_STATE_ID): set(NAM_RESIDUAL_CITY_PROVINCES),
        (67, NAM_DRYRIVER_STATE_ID): set(NAM_DRYRIVER_PROVINCES),
        (68, EFL_MIDDLE_LOREN_STATE_ID): set(EFL_MIDDLE_LOREN_PROVINCES),
        (69, AZH_BLACK_COAST_STATE_ID): set(AZH_BLACK_COAST_PROVINCES),
        (71, 91): {3743},
    }
    unexpected = [
        mismatch for mismatch in mismatches
        if mismatch.province not in expected_moves.get(
            (mismatch.recorded_state, mismatch.actual_state), set()
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


def replace_history_victory_points(
    source: str, points: tuple[tuple[int, int], ...]
) -> str:
    """Replace every history VP with one exact ordered manifest block."""
    history_open, history_close = named_block(source, "history")
    history = source[history_open:history_close + 1]
    pattern = re.compile(
        r"(?m)^([ \t]*)victory_points[ \t]*=[ \t]*\{[ \t]*"
        r"\d+[ \t]+\d+[ \t]*\}[ \t]*(?:\n|$)"
    )
    matches = list(pattern.finditer(history))
    if matches:
        insertion = matches[0].start()
        indent = matches[0].group(1)
        history = pattern.sub("", history)
    else:
        closing_line = history.rfind("\n", 0, len(history) - 1)
        insertion = closing_line + 1 if closing_line >= 0 else len(history) - 1
        closing_indent = history[insertion:-1]
        indent = f"{closing_indent}\t"

    if points:
        block = "".join(
            f"{indent}victory_points = {{ {province_id} {value} }}\n"
            for province_id, value in points
        )
        history = history[:insertion] + block + history[insertion:]

    return source[:history_open] + history + source[history_close + 1:]


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


def set_history_demilitarized_zone(source: str, enabled: bool) -> str:
    """Set one canonical history-level DMZ entry without touching other data."""
    history_open, history_close = named_block(source, "history")
    history = source[history_open:history_close + 1]
    history = re.sub(
        r"(?m)^\s*set_demilitarized_zone\s*=\s*yes\s*$\n?",
        "",
        history,
    )
    if enabled:
        history = history[:-1].rstrip() + "\n\t\tset_demilitarized_zone = yes\n\t}"
    return source[:history_open] + history + source[history_close + 1:]


def apply_legacy_state_profiles(state_ids: set[int] | None = None) -> None:
    """Patch legacy Vorkerland and NAM states without discarding map data."""
    for state_id, profile in LEGACY_STATE_PROFILES.items():
        if state_ids is not None and state_id not in state_ids:
            continue
        path = state_path(state_id)
        source = path.read_text(encoding="utf-8-sig", errors="strict")
        source = set_scalar(source, "manpower", str(profile["population"]))
        source = set_scalar(source, "state_category", str(profile["category"]))
        source = set_scalar(
            source,
            "buildings_max_level_factor",
            f"{float(profile.get('buildings_max_level_factor', 1.0)):.3f}",
        )
        if state_id == 27:
            source = source.replace(
                "# Three shared factories require at least three local building slots.",
                "# Five base slots retain four shared buildings after the plant slot penalty.",
            )
        source = set_scalar(source, "local_supplies", f"{float(profile['supplies']):.1f}")
        if state_id in IMPASSABLE_LEGACY_STATE_IDS:
            source = set_scalar(source, "impassable", "yes")
        else:
            source = re.sub(r"(?m)^\s*impassable\s*=\s*yes\s*$\n?", "", source)
        if state_id in VORKERLAND_LEGACY_PROFILES:
            source = set_history_demilitarized_zone(
                source,
                state_id in PWR_PRE_COLLAPSE_DMZ_STATES,
            )
        source = ensure_history_buildings(source, profile)
        if state_id in EXACT_LEGACY_FACTORY_STATE_IDS:
            source = set_history_building_level(
                source, "industrial_complex", int(profile.get("civilian", 0))
            )
            source = set_history_building_level(
                source, "arms_factory", int(profile.get("military", 0))
            )
        if state_id in REGIONAL_STATE_RESOURCES:
            source = ensure_state_resources(source, REGIONAL_STATE_RESOURCES[state_id])
        if state_id == 40:
            source = remove_state_resource(source, "steel")
        if state_id in VORKERLAND_THEATRE_VICTORY_POINTS:
            source = replace_history_victory_points(
                source, VORKERLAND_THEATRE_VICTORY_POINTS[state_id]
            )
        elif state_id in GENERATED_LEGACY_VICTORY_POINTS:
            source = ensure_history_victory_points(
                source, GENERATED_LEGACY_VICTORY_POINTS[state_id]
            )
        path.write_text(source, encoding="utf-8", newline="\n")


def replace_localisation_value(source: str, key: str, value: str) -> str:
    """Set one localisation value while removing stale duplicate keys."""
    pattern = re.compile(
        rf'(?m)^([ \t]*){re.escape(key)}:[ \t]*"[^"]*"[ \t]*(?:\n|$)'
    )
    seen = False

    def replace(match: re.Match[str]) -> str:
        nonlocal seen
        if seen:
            return ""
        seen = True
        return f'{match.group(1)}{key}: "{value}"\n'

    source = pattern.sub(replace, source)
    if not seen:
        source = source.rstrip() + f'\n {key}: "{value}"\n'
    return source


def remove_localisation_key(source: str, key: str) -> str:
    pattern = re.compile(
        rf'(?m)^[ \t]*{re.escape(key)}:[ \t]*"[^"]*"[ \t]*(?:\n|$)'
    )
    return pattern.sub("", source)


def update_vorkerland_vp_localisation(source: str) -> str:
    for province_id in VORKERLAND_THEATRE_RETIRED_VP_IDS:
        source = remove_localisation_key(source, f"VICTORY_POINTS_{province_id}")
    for province_id, name in VORKERLAND_THEATRE_VP_NAME_OVERRIDES.items():
        source = replace_localisation_value(
            source, f"VICTORY_POINTS_{province_id}", name
        )
    return source


def apply_generated_victory_point_localisation() -> None:
    """Keep generated Russian VP names BOM-safe and duplicate-free."""
    path = ROOT / "localisation" / "russian" / "victory_points_l_russian.yml"
    source = update_vorkerland_vp_localisation(
        path.read_text(encoding="utf-8-sig", errors="strict")
    )
    for province_id, name in GENERATED_VICTORY_POINT_NAMES.items():
        source = replace_localisation_value(
            source, f"VICTORY_POINTS_{province_id}", name
        )
    path.write_text(source.rstrip() + "\n", encoding="utf-8-sig", newline="\n")


def apply_vorkerland_victory_points() -> None:
    """Apply only the exact central-theatre VP and Russian-name manifest."""
    for state_id, protected_points in VORKERLAND_PROTECTED_LANDMARK_VPS.items():
        if VORKERLAND_THEATRE_VICTORY_POINTS.get(state_id) != protected_points:
            raise RuntimeError(
                f"protected Vorkerland landmark state {state_id} changed or disappeared"
            )
    if UNITY_TOWER_PROVINCE in VORKERLAND_THEATRE_RETIRED_VP_IDS:
        raise RuntimeError("Unity Tower cannot be retired from the Vorkerland theatre")
    if VORKERLAND_THEATRE_VP_NAME_OVERRIDES.get(UNITY_TOWER_PROVINCE) != UNITY_TOWER_NAME:
        raise RuntimeError("Unity Tower must retain its protected Russian name")

    for state_id, points in VORKERLAND_THEATRE_VICTORY_POINTS.items():
        path = state_path(state_id)
        source = path.read_text(encoding="utf-8-sig", errors="strict")
        province_match = re.search(r"\bprovinces\s*=\s*\{([^}]*)\}", source, re.DOTALL)
        if not province_match:
            raise RuntimeError(f"state {state_id}: missing provinces block")
        provinces = {int(value) for value in re.findall(r"\d+", province_match.group(1))}
        wrong = sorted(province_id for province_id, _value in points if province_id not in provinces)
        if wrong:
            raise RuntimeError(f"state {state_id}: theatre VPs outside state: {wrong}")
        updated = replace_history_victory_points(source, points)
        if updated != source:
            path.write_text(updated, encoding="utf-8", newline="\n")

    localisation_path = ROOT / "localisation" / "russian" / "victory_points_l_russian.yml"
    localisation = localisation_path.read_text(encoding="utf-8-sig", errors="strict")
    updated_localisation = update_vorkerland_vp_localisation(localisation).rstrip() + "\n"
    if updated_localisation != localisation:
        localisation_path.write_text(
            updated_localisation, encoding="utf-8-sig", newline="\n"
        )


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


def apply() -> None:
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


def apply_nam_resource_war_states() -> None:
    """Regenerate only NAM-war mainland data and its generated VP names."""
    split_svetlogorsk_from_nam()
    apply_legacy_state_profiles({67, 68, 69, 70, 690, 691, 692})
    apply_generated_victory_point_localisation()
    apply_generated_state_name_localisation()


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate A-Discord state metadata.")
    actions = parser.add_mutually_exclusive_group()
    actions.add_argument("--check", action="store_true", help="validate current generated outputs (default)")
    actions.add_argument("--apply", action="store_true", help="write generated state metadata and localisation")
    actions.add_argument(
        "--apply-nam-split",
        action="store_true",
        help="regenerate only the NAM mainland split and its state-owned data",
    )
    actions.add_argument(
        "--apply-nam-resource-war",
        action="store_true",
        help="regenerate NAM-war mainland states and their generated VP names",
    )
    actions.add_argument(
        "--apply-vorkerland-vps",
        action="store_true",
        help="apply only the exact central Vorkerland VP and Russian-name manifest",
    )
    actions.add_argument(
        "--apply-legacy-state",
        action="append",
        type=int,
        metavar="STATE_ID",
        help="patch only the selected legacy state profile; may be repeated",
    )
    args = parser.parse_args()
    if args.apply:
        apply()
        return 0
    if args.apply_nam_split:
        split_svetlogorsk_from_nam()
        print("Regenerated the NAM mainland split without touching unrelated states.")
        return 0
    if args.apply_nam_resource_war:
        apply_nam_resource_war_states()
        print("Regenerated NAM-war mainland states and victory-point names.")
        return 0
    if args.apply_vorkerland_vps:
        apply_vorkerland_victory_points()
        print("Applied the exact central Vorkerland victory-point manifest.")
        return 0
    if args.apply_legacy_state:
        state_ids = set(args.apply_legacy_state)
        unknown = sorted(state_ids - set(LEGACY_STATE_PROFILES))
        if unknown:
            parser.error(f"states without a legacy profile: {unknown}")
        apply_legacy_state_profiles(state_ids)
        print(f"Applied {len(state_ids)} selected legacy state profile(s): {sorted(state_ids)}.")
        return 0
    from tools.validators.validate_adiscord_new_states import main as validate_main

    return validate_main()


if __name__ == "__main__":
    raise SystemExit(main())
