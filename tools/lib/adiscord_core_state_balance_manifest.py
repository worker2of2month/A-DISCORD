"""Approved balance contract for the starting states of NOD, STP, VAL, and the northern coalition."""

from __future__ import annotations


TARGET_STATES = {
    1: ("history/states/1-Ablia.txt", "STP", 1_200_000, "large_town"),
    2: ("history/states/2-New-Monaii.txt", "STP", 3_000_000, "city"),
    3: ("history/states/3-Neansas.txt", "STP", 1_100_000, "rural"),
    10: ("history/states/10-Ashya.txt", "NOD", 525_000, "town"),
    11: ("history/states/11-Ostrium.txt", "NOD", 2200000, "city"),
    12: ("history/states/12-Kaclana.txt", "NOD", 520_000, "town"),
    13: ("history/states/13-Treya.txt", "NOD", 580_000, "town"),
    17: ("history/states/17-Esnos.txt", "NOD", 300_000, "town"),
    18: ("history/states/18-Brioland.txt", "NOD", 285_000, "town"),
    24: ("history/states/24-Irem.txt", "VAL", 120_000, "rural"),
    28: ("history/states/28-Fada.txt", "STP", 6_300_000, "large_city"),
    29: ("history/states/29-Kreyden.txt", "STP", 1_800_000, "city"),
    30: ("history/states/30-Cussington.txt", "NOD", 7_600_000, "large_city"),
    42: ("history/states/42-Prigranichie.txt", "VAL", 80_000, "pastoral"),
    43: ("history/states/43-Balchansk.txt", "STP", 1_200_000, "town"),
    44: ("history/states/44-Iron-Shield.txt", "STP", 900_000, "town"),
    45: ("history/states/45-Livonn.txt", "STP", 1_200_000, "town"),
    46: ("history/states/46-Hosheit.txt", "STP", 300_000, "town"),
    48: ("history/states/48-Depoitodron.txt", "VAL", 8_000_000, "megalopolis"),
    53: ("history/states/53-Old-Fada.txt", "STP", 180_000, "pastoral"),
    54: ("history/states/54-Spastlant.txt", "VAL", 1_300_000, "city"),
    55: ("history/states/55-Erstantpeo.txt", "VAL", 90_000, "pastoral"),
    56: ("history/states/56-Zeigen.txt", "VAL", 320_000, "town"),
    57: ("history/states/57-Zoilong.txt", "VAL", 1_200_000, "town"),
    88: ("history/states/88-Shahterskiy-Poselok.txt", "STP", 650_000, "town"),
    168: ("history/states/168-168.txt", "VAL", 160_000, "town"),
    # Northern coalition: populations also cover the starting army and reserves.
    8: ("history/states/8-Osturg.txt", "YPR", 190_000, "town"),
    15: ("history/states/15-Duchebia.txt", "YPR", 180_000, "town"),
    16: ("history/states/16-Plaoya.txt", "YPR", 210_000, "town"),
    19: ("history/states/19-Cleikshen.txt", "YPR", 140_000, "town"),
    20: ("history/states/20-Eshait.txt", "YPR", 1230000, "city"),
    21: ("history/states/21-Teflar.txt", "YPR", 220_000, "town"),
    22: ("history/states/22-Otrea.txt", "YPR", 130_000, "town"),
    14: ("history/states/14-Flaem-Prana.txt", "COF", 720000, "town"),
    83: ("history/states/83-83.txt", "TFF", 210_000, "rural"),
    84: ("history/states/84-84.txt", "TFF", 850000, "town"),
    85: ("history/states/85-85.txt", "TFF", 190_000, "rural"),
    86: ("history/states/86-86.txt", "TFF", 160_000, "rural"),
    87: ("history/states/87-87.txt", "TFF", 81_000, "rural"),
    303: ("history/states/303-303.txt", "TFF", 9000, "rural"),
}

EXPECTED_POPULATION_TOTALS = {
    "NOD": 12010000,
    "STP": 17_830_000,
    "VAL": 11_270_000,
    "YPR": 2300000,
    "COF": 720000,
    "TFF": 1500000,
}

SETTLEMENT_VPS = {
    10: (22, 1, "Ашия"),
    17: (34, 3, "Эснос"),
    18: (14, 3, "Бриоланд"),
    3: (45, 1, "Ниансанс"),
    53: (70, 1, "Старая Фада"),
    88: (110, 1, "Шахтёрский посёлок"),
    24: (9126, 1, "Ирим"),
    42: (125, 1, "Пограничный"),
    55: (9617, 1, "Ерстантпео"),
}

# Northern rail centres and local headquarters use their existing geographical names.
# The offshore state 303 stays outside the land campaign victory-point objective.
NORTHERN_CAMPAIGN_VPS = {
    14: ((75, 5), (2, 3), (5421, 1)),
    15: ((11, 3),),
    19: ((4, 2),),
    83: ((30, 3),),
    85: ((16, 3),),
    86: ((105, 3),),
    87: ((6471, 1),),
    303: (),
}

SETTLEMENT_VP_VALUES = {
    **{province: value for province, value, _name in SETTLEMENT_VPS.values()},
    **{province: value for points in NORTHERN_CAMPAIGN_VPS.values() for province, value in points},
}

NON_URBAN_SETTLEMENT_VPS = frozenset(SETTLEMENT_VP_VALUES)

URBAN_VP_MINIMUMS = {
    12: {16644: 5, 16647: 5},
    13: {16652: 5, 9395: 5},
    44: {16448: 5},
    54: {16653: 5},
    56: {16645: 5},
    168: {16534: 5},
}

EXPECTED_VP_NAMES = {
    14: "Бриоланд",
    22: "Ашия",
    34: "Эснос",
    45: "Ниансанс",
    70: "Старая Фада",
    110: "Шахтёрский посёлок",
    125: "Пограничный",
    9126: "Ирим",
    9617: "Ерстантпео",
    16356: "Остриум",
}

EXPECTED_DIRECT_BUILDINGS = {
    1: {"infrastructure": 3, "industrial_complex": 2, "arms_factory": 1, "air_base": 1},
    2: {"infrastructure": 3, "arms_factory": 2, "industrial_complex": 2},
    3: {"infrastructure": 3, "synthetic_refinery": 2},
    10: {"infrastructure": 2, "industrial_complex": 2, "arms_factory": 2},
    11: {"infrastructure": 3, "industrial_complex": 3, "arms_factory": 3, "air_base": 2},
    12: {"infrastructure": 2, "industrial_complex": 1, "arms_factory": 2},
    13: {"infrastructure": 2, "industrial_complex": 1, "arms_factory": 1, "synthetic_refinery": 1},
    17: {"infrastructure": 2, "arms_factory": 1},
    18: {"infrastructure": 2, "industrial_complex": 1, "synthetic_refinery": 1},
    24: {"infrastructure": 1, "synthetic_refinery": 2},
    28: {
        "infrastructure": 4,
        "arms_factory": 3,
        "hidden_dam": 1,
        "industrial_complex": 2,
        "ADISCORD_industrial_cluster": 1,
        "ADISCORD_business_center": 1,
        "air_base": 2,
    },
    29: {"infrastructure": 4, "industrial_complex": 4},
    30: {
        "infrastructure": 5,
        "industrial_complex": 2,
        "arms_factory": 3,
        "dockyard": 1,
        "ADISCORD_industrial_cluster": 1,
        "ADISCORD_business_center": 1,
        "air_base": 2,
    },
    42: {"infrastructure": 2, "hidden_dam": 1},
    43: {"infrastructure": 2, "industrial_complex": 2, "synthetic_refinery": 1},
    44: {"infrastructure": 2, "arms_factory": 1, "hidden_dam": 1, "industrial_complex": 1, "dockyard": 2},
    45: {"infrastructure": 3, "industrial_complex": 3},
    46: {"infrastructure": 2, "dockyard": 1, "industrial_complex": 1},
    48: {
        "infrastructure": 4,
        "arms_factory": 8,
        "industrial_complex": 2,
        "ADISCORD_industrial_cluster": 1,
        "ADISCORD_business_center": 1,
        "air_base": 2,
    },
    53: {"infrastructure": 1, "hidden_dam": 1},
    54: {"infrastructure": 3, "arms_factory": 2, "industrial_complex": 4, "air_base": 2},
    55: {"infrastructure": 2},
    56: {"infrastructure": 2, "industrial_complex": 1, "arms_factory": 1, "synthetic_refinery": 2},
    57: {"infrastructure": 3, "industrial_complex": 3, "arms_factory": 1},
    88: {"infrastructure": 4, "industrial_complex": 3},
    168: {"industrial_complex": 1, "infrastructure": 2},
    8: {"infrastructure": 2, "industrial_complex": 1},
    15: {"infrastructure": 2, "arms_factory": 1},
    16: {"infrastructure": 2},
    19: {"infrastructure": 2, "arms_factory": 1},
    20: {"infrastructure": 3, "industrial_complex": 2, "arms_factory": 4},
    21: {"infrastructure": 2},
    22: {"infrastructure": 1},
    14: {"infrastructure": 2, "industrial_complex": 1, "arms_factory": 2},
    83: {"infrastructure": 2, "arms_factory": 1},
    84: {"infrastructure": 3, "industrial_complex": 2, "arms_factory": 2},
    85: {"infrastructure": 2, "arms_factory": 1},
    86: {"infrastructure": 2},
    87: {"infrastructure": 1},
    303: {"infrastructure": 2},
}

EXPECTED_INDUSTRY_TOTALS = {
    "NOD": {"industrial_complex": 10, "arms_factory": 12, "dockyard": 1},
    "STP": {"industrial_complex": 20, "arms_factory": 7, "dockyard": 3},
    "VAL": {"industrial_complex": 11, "arms_factory": 12, "dockyard": 0},
    "YPR": {"industrial_complex": 3, "arms_factory": 6, "dockyard": 0},
    "COF": {"industrial_complex": 1, "arms_factory": 2, "dockyard": 0},
    "TFF": {"industrial_complex": 2, "arms_factory": 4, "dockyard": 0},
}

EXPECTED_RESOURCES = {
    1: {"oil": 6, "chromium": 4},
    2: {},
    3: {"steel": 22, "oil": 2},
    10: {},
    11: {"steel": 44, "aluminium": 10, "tungsten": 4},
    12: {},
    13: {},
    17: {},
    18: {},
    24: {"oil": 7},
    28: {},
    29: {"chromium": 28, "aluminium": 12},
    30: {},
    42: {},
    43: {"steel": 18, "aluminium": 3, "tungsten": 3, "chromium": 2},
    44: {"steel": 18, "aluminium": 3, "tungsten": 3, "chromium": 2},
    45: {"steel": 18, "aluminium": 3, "tungsten": 3, "chromium": 2},
    46: {"steel": 11, "aluminium": 12},
    48: {},
    53: {},
    54: {},
    55: {"oil": 12},
    56: {},
    57: {},
    88: {"steel": 18, "aluminium": 3, "tungsten": 3, "chromium": 2},
    168: {},
    8: {},
    15: {"steel": 24},
    16: {},
    19: {"aluminium": 2},
    20: {},
    21: {"tungsten": 2},
    22: {},
    14: {"steel": 8, "aluminium": 2},
    83: {},
    84: {},
    85: {"aluminium": 2},
    86: {"steel": 16},
    87: {},
    303: {},
}

EXPECTED_RESOURCE_TOTALS = {
    "NOD": {"steel": 44, "aluminium": 10, "tungsten": 4},
    "STP": {"steel": 105, "chromium": 40, "aluminium": 36, "tungsten": 12, "oil": 8},
    "VAL": {"oil": 19},
    "YPR": {"steel": 24, "aluminium": 2, "tungsten": 2},
    "COF": {"steel": 8, "aluminium": 2},
    "TFF": {"steel": 16, "aluminium": 2},
}

CAPITAL_CUSTOM_BUILDING_STATES = frozenset({28, 30, 48})
STP_CLAIMS_ON_VAL = frozenset({42, 55})
