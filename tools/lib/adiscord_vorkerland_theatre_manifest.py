"""Exact victory-point contract for the central Vorkerland war theatre."""

from __future__ import annotations


UNITY_TOWER_STATE = 40
UNITY_TOWER_PROVINCE = 16428
UNITY_TOWER_VALUE = 5
UNITY_TOWER_NAME = "Башня Единства"
VORKERLAND_PROTECTED_LANDMARK_VPS = {
    UNITY_TOWER_STATE: ((UNITY_TOWER_PROVINCE, UNITY_TOWER_VALUE),),
}


VORKERLAND_THEATRE_VICTORY_POINTS: dict[int, tuple[tuple[int, int], ...]] = {
    27: ((16614, 3), (5090, 3)),
    32: ((6713, 30), (16405, 10)),
    33: ((3248, 10), (3913, 3)),
    34: ((16426, 10),),
    35: ((16388, 10),),
    36: ((12227, 10), (16417, 5), (5907, 3)),
    37: ((16400, 10), (16413, 5), (754, 3)),
    38: ((16398, 10), (6790, 5), (16425, 3)),
    39: ((16397, 10), (12985, 5), (16404, 3)),
    UNITY_TOWER_STATE: VORKERLAND_PROTECTED_LANDMARK_VPS[UNITY_TOWER_STATE],
    75: ((16593, 10), (6192, 15), (8243, 10)),
    79: ((16592, 5),),
    81: ((16587, 10), (16616, 2), (16620, 2)),
    82: ((8059, 5),),
    102: ((16594, 10), (16580, 5), (16575, 5), (16570, 5), (4841, 5)),
    105: ((16589, 12), (16565, 5), (16577, 3), (16581, 2)),
    106: ((11944, 10), (2949, 3)),
    107: ((16635, 1), (16640, 1), (2539, 5)),
    108: ((10147, 3),),
    109: ((16574, 3),),
    110: ((16566, 5),),
    111: ((11274, 3),),
    121: ((16560, 10),),
    122: ((16569, 5),),
    123: ((16576, 5),),
    124: ((16579, 3),),
    200: (),
    201: (),
    306: ((16643, 5),),
    308: ((16615, 3),),
    309: ((11795, 5),),
    315: ((3762, 3),),
    316: ((4148, 5),),
    317: ((8803, 3),),
    318: ((16642, 3),),
    320: ((12099, 3),),
    323: ((16590, 3),),
    324: ((12192, 5),),
    325: ((4569, 3),),
    327: ((16641, 5),),
}


VORKERLAND_THEATRE_VP_NAME_OVERRIDES: dict[int, str] = {
    2539: "Верхний Орвин",
    2949: "Руден",
    3248: "Зюдхайм",
    3762: "Лесогорск",
    3913: "Гартен",
    4148: "Бережск",
    4569: "Ольхов",
    4841: "Торген",
    5090: "Горенск",
    10147: "Луговск",
    11274: "Ярмарск",
    11944: "Сутрица",
    12099: "Сосновец",
    12192: "Вестмар",
    UNITY_TOWER_PROVINCE: UNITY_TOWER_NAME,
    16426: "Ойтфорт",
    16560: "Северин",
    16569: "Лаурен",
    16570: "Слобода",
    16575: "Йорсен",
    16579: "Выцк",
    16580: "Меркен",
    16592: "Грейн",
    16593: "Затерн",
}


VORKERLAND_THEATRE_RETIRED_VP_IDS: frozenset[int] = frozenset()


VORKERLAND_THEATRE_PACKAGES: dict[str, tuple[int, ...]] = {
    "WKR": (32, 33, 40, 200, 201),
    "VAD": (75, 106, 107, 121),
    "TVA": (36, 37, 38, 39, 324),
    "EYR": (102, 109, 111, 325),
    "EGC": (81, 110, 124),
    "RIV": (79, 306, 308, 309, 327),
    "REV": (82, 323),
    "YOR": (108, 122, 123),
    "NDN": (27,),
    "SWB": (35,),
    "VHV": (315, 316, 317),
    "OSV": (318, 320),
    "WTD": (34,),
    "TGD": (105,),
}


VORKERLAND_THEATRE_PACKAGE_TOTALS: dict[str, int] = {
    "WKR": 58,
    "VAD": 65,
    "TVA": 77,
    "EYR": 39,
    "EGC": 22,
    "RIV": 23,
    "REV": 8,
    "YOR": 13,
    "NDN": 6,
    "SWB": 10,
    "VHV": 11,
    "OSV": 6,
    "WTD": 10,
    "TGD": 22,
}


VORKERLAND_THEATRE_VP_PROVINCES = frozenset(
    province_id
    for points in VORKERLAND_THEATRE_VICTORY_POINTS.values()
    for province_id, _value in points
)
