"""Approved balance contract for the starting states of NOD, STP, and VAL."""

from __future__ import annotations


TARGET_STATES = {
    1: ("history/states/1-Ablia.txt", "STP", 1_200_000, "large_town"),
    2: ("history/states/2-New-Monaii.txt", "STP", 3_000_000, "city"),
    3: ("history/states/3-Neansas.txt", "STP", 1_100_000, "rural"),
    10: ("history/states/10-Ashya.txt", "NOD", 525_000, "town"),
    11: ("history/states/11-Ostrium.txt", "NOD", 1_200_000, "city"),
    12: ("history/states/12-Kaclana.txt", "NOD", 520_000, "town"),
    13: ("history/states/13-Treya.txt", "NOD", 580_000, "town"),
    17: ("history/states/17-Esnos.txt", "NOD", 300_000, "town"),
    18: ("history/states/18-Brioland.txt", "NOD", 285_000, "town"),
    24: ("history/states/24-Irem.txt", "VAL", 120_000, "rural"),
    28: ("history/states/28-Fada.txt", "STP", 6_300_000, "large_city"),
    29: ("history/states/29-Kreyden.txt", "STP", 1_800_000, "city"),
    30: ("history/states/30-Cussington.txt", "NOD", 7_600_000, "large_city"),
    42: ("history/states/42-Prigranichie.txt", "VAL", 80_000, "pastoral"),
    43: ("history/states/43-Balchansk.txt", "STP", 950_000, "town"),
    44: ("history/states/44-Iron-Shield.txt", "STP", 500_000, "town"),
    45: ("history/states/45-Livonn.txt", "STP", 900_000, "town"),
    46: ("history/states/46-Hosheit.txt", "STP", 300_000, "town"),
    48: ("history/states/48-Depoitodron.txt", "VAL", 8_000_000, "megalopolis"),
    53: ("history/states/53-Old-Fada.txt", "STP", 180_000, "pastoral"),
    54: ("history/states/54-Spastlant.txt", "VAL", 1_300_000, "city"),
    55: ("history/states/55-Erstantpeo.txt", "VAL", 90_000, "pastoral"),
    56: ("history/states/56-Zeigen.txt", "VAL", 320_000, "town"),
    57: ("history/states/57-Zoilong.txt", "VAL", 1_200_000, "town"),
    88: ("history/states/88-Shahterskiy-Poselok.txt", "STP", 150_000, "town"),
    168: ("history/states/168-168.txt", "VAL", 160_000, "town"),
}

EXPECTED_POPULATION_TOTALS = {
    "NOD": 11_010_000,
    "STP": 16_380_000,
    "VAL": 11_270_000,
}

SETTLEMENT_VPS = {
    10: (22, 1, "Ашия"),
    17: (34, 1, "Эснос"),
    18: (14, 1, "Бриоланд"),
    3: (45, 1, "Ниансанс"),
    53: (70, 1, "Старая Фада"),
    88: (110, 1, "Шахтёрский посёлок"),
    24: (9126, 1, "Ирим"),
    42: (125, 1, "Пограничный"),
    55: (9617, 1, "Ерстантпео"),
}

NON_URBAN_SETTLEMENT_VPS = frozenset(province for province, _value, _name in SETTLEMENT_VPS.values())

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
    1: {"infrastructure": 3, "industrial_complex": 2, "arms_factory": 1},
    2: {"infrastructure": 3, "arms_factory": 2, "industrial_complex": 2},
    3: {"infrastructure": 3, "synthetic_refinery": 2},
    10: {"infrastructure": 2, "industrial_complex": 2, "arms_factory": 1},
    11: {"infrastructure": 3, "industrial_complex": 2, "arms_factory": 1},
    12: {"infrastructure": 2, "industrial_complex": 1, "arms_factory": 1},
    13: {"infrastructure": 2, "industrial_complex": 1, "arms_factory": 1},
    17: {"infrastructure": 2},
    18: {"infrastructure": 2},
    24: {"infrastructure": 1},
    28: {
        "infrastructure": 4,
        "arms_factory": 3,
        "hidden_dam": 1,
        "industrial_complex": 2,
        "ADISCORD_industrial_cluster": 1,
        "ADISCORD_business_center": 1,
    },
    29: {"infrastructure": 4, "industrial_complex": 4},
    30: {
        "infrastructure": 5,
        "industrial_complex": 2,
        "arms_factory": 2,
        "dockyard": 1,
        "ADISCORD_industrial_cluster": 1,
        "ADISCORD_business_center": 1,
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
    },
    53: {"infrastructure": 1, "hidden_dam": 1},
    54: {"infrastructure": 3, "arms_factory": 2, "industrial_complex": 4},
    55: {"infrastructure": 2},
    56: {"infrastructure": 2, "industrial_complex": 1, "arms_factory": 1},
    57: {"infrastructure": 3, "industrial_complex": 3, "arms_factory": 1},
    88: {"infrastructure": 4, "industrial_complex": 3},
    168: {"industrial_complex": 1, "infrastructure": 2},
}

EXPECTED_INDUSTRY_TOTALS = {
    "NOD": {"industrial_complex": 8, "arms_factory": 6, "dockyard": 1},
    "STP": {"industrial_complex": 20, "arms_factory": 7, "dockyard": 3},
    "VAL": {"industrial_complex": 11, "arms_factory": 12, "dockyard": 0},
}

EXPECTED_RESOURCES = {
    1: {"oil": 6, "chromium": 4},
    2: {},
    3: {"steel": 22, "oil": 2},
    10: {},
    11: {"steel": 17, "aluminium": 5},
    12: {},
    13: {},
    17: {},
    18: {},
    24: {"oil": 7},
    28: {},
    29: {"chromium": 28, "aluminium": 12},
    30: {},
    42: {"tungsten": 12, "steel": 20},
    43: {},
    44: {},
    45: {"steel": 39, "aluminium": 9},
    46: {"steel": 11, "aluminium": 12},
    48: {},
    53: {},
    54: {"steel": 5},
    55: {"oil": 12, "chromium": 12},
    56: {},
    57: {},
    88: {"tungsten": 12, "chromium": 8, "steel": 31},
    168: {},
}

EXPECTED_RESOURCE_TOTALS = {
    "NOD": {"steel": 17, "aluminium": 5},
    "STP": {"steel": 103, "chromium": 40, "aluminium": 33, "tungsten": 12, "oil": 8},
    "VAL": {"steel": 25, "tungsten": 12, "oil": 19, "chromium": 12},
}

CAPITAL_CUSTOM_BUILDING_STATES = frozenset({28, 30, 48})
STP_CLAIMS_ON_VAL = frozenset({42, 55})
