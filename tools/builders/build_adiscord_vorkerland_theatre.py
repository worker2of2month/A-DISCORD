#!/usr/bin/env python3
"""Own bounded campaign rail connections and starting supply hubs."""

from __future__ import annotations

import argparse
import re
from collections import defaultdict
from collections.abc import Callable
from pathlib import Path

from tools.builders import build_adiscord_strategic_regions as map_regions
from tools.lib.paths import repository_root
from tools.lib.vorkerland_collapse_manifest import (
    DIRTY_GROUPS,
    DIRTY_INITIAL_OWNER_OVERRIDES,
    EXZ_REMAINDER_GROUPS,
)


ROOT = repository_root()
RAILWAYS_PATH = ROOT / "map" / "railways.txt"
SUPPLY_NODES_PATH = ROOT / "map" / "supply_nodes.txt"
OSV_CAPITAL_STATE = 318
OSV_CAPITAL_RAIL = (1, (16642, 1540, 1818))
# Each spur joins existing rail inside its starting country's borders.
# The paired hubs are the continuity contract, not extra construction.
STARTING_SUPPLY_RAILS = {
    "STP": (1, (119, 1, 16440), (16547, 16440)),
    "YPR": (1, (33, 73, 11), (16372, 11)),
}
# Capital, forward depot and embarkation port remain connected inside each country.
COALITION_SUPPLY_RAILS = {
    "EFL": (
        (2, (16717, 8904, 12830, 786, 5934, 10809, 1200, 6514, 6847, 1444, 9402, 10422)),
        (2, (10422, 6970, 11035, 9041, 6870, 5979, 6000, 6495)),
    ),
    "AZH": (
        (2, (16893, 16886, 7737, 729, 367, 5555, 6577)),
        (2, (7737, 9798, 10626, 9758, 8829, 1360, 5039, 3464, 493)),
    ),
}
COALITION_SUPPLY_HUB_STATES = {10422: 70, 6577: 727}
COALITION_SUPPLY_ENDPOINTS = {"EFL": (16717, 10422, 6495), "AZH": (16893, 6577, 493)}
# The imperial network joins the northern cities to Montera and the existing
# southern railway without relying on transit through neighbouring countries.
MON_CAPITAL_PROVINCE = 2845
MON_SUPPLY_RAILS = (
    (2, (2845, 10317, 11261, 11145, 4432, 3934, 9899)),
    (2, (2845, 7088, 418)),
    (2, (9899, 6800, 460, 16308, 2210, 12563, 6028)),
    (2, (6028, 5475, 12975, 8798, 5730, 1702, 2090)),
    (2, (2090, 11682, 11789, 9420, 1855, 10992, 212)),
    (2, (212, 768, 5489, 10541, 7210, 12168, 5283, 9322)),
    (2, (9322, 9807, 9741, 16330, 709, 635, 7404)),
    (2, (7404, 5509, 12916, 12408, 12689, 300, 8865)),
    (2, (9899, 4152, 1606, 6284, 7717, 6873, 1228, 8933, 7356, 3859)),
    (2, (3859, 9729, 4374, 11365, 11224, 5575, 8159, 5183, 10008, 6748)),
    (2, (8865, 1718, 12389, 9684, 10076, 12706, 1537, 2269, 9254, 10504, 1993, 7072)),
    # Upgrade the existing capital spur; the southern line retains its level.
    (2, (2845, 8790, 715, 12285)),
)
MON_SUPPLY_HUB_STATES = {
    2845: 469,  # Montera.
    9899: 459,  # Arken.
    6028: 460,  # Vald.
    6748: 471,  # Valtor.
    212: 425,
    2090: 444,
    9322: 439,
    7404: 445,
    8865: 448,
    3859: 456,
    8729: 470,
    10095: 472,
    418: 467,
}
# Capturing Kalten and the Pustograd corridor opens a western supply route
# without requiring control of Starolesye or the bunker.
MON_KALTEN_RAIL = (1, (8798, 6168, 1472, 10282, 3783))
MON_KALTEN_CORRIDOR_STATES = frozenset({710, 461, 51})
MON_KALTEN_CORRIDOR_HUBS = (3783, 12219)
# The western line must join the bunker without crossing a third country.
# Hubs become available to RUS only after it captures the border objectives.
KHAN_SUPPLY_RAIL = (2, (16546, 16544, 2298, 4486, 10563))
KHAN_SUPPLY_STATES = frozenset({66, 49, 176})
KHAN_SUPPLY_HUBS = (16531, 16639, 7445)
# Forward depots use existing rail; capturing the corridor is still required.
KHAN_CAMPAIGN_SUPPLY_HUB_STATES = {
    # SLA: western front, southern approach and the northern rail corridor.
    5032: 712,
    12219: 51,
    16630: 329,
    # RZA.
    7650: 220,
    2768: 217,
    11688: 214,
    # MLR.
    1707: 221,
    876: 189,
    # ERT.
    8500: 184,
    # IRT.
    10421: 182,
    16480: 207,
    # SCA.
    16334: 173,
    16489: 211,
}
# Level-2 operational spines through the six Dirty Zone belts. These routes
# already exist physically; the generator owns their throughput so future map
# regeneration cannot silently drop the Khan campaign logistics upgrade.
KHAN_CAMPAIGN_RAIL_UPGRADES = (
    (2, (16639, 16531)),
    (2, (16546, 11010, 2558)),
    (2, (16546, 16545, 7445, 4051, 5637, 10617, 11425, 8664, 5195, 9439, 16518)),
    (
        2,
        (
            16639,
            10563,
            12635,
            5961,
            4899,
            3728,
            5780,
            564,
            7706,
            876,
            12361,
            7164,
            6196,
            4580,
        ),
    ),
    (2, (16518, 11398, 2825, 2395, 2952, 9994, 1112, 16525, 16517)),
    (2, (16511, 6519, 11913, 10693, 12878, 16526)),
    (
        2,
        (
            6495,
            6000,
            5979,
            6870,
            9041,
            910,
            9308,
            7567,
            12366,
            7178,
            8981,
            691,
            7790,
            6015,
            11334,
            7786,
            16327,
            1907,
            16504,
            16469,
        ),
    ),
    (2, (2741, 7650, 2743, 12231, 8535, 6669, 10977, 8259, 9031, 11334)),
    (2, (2741, 5194, 6220, 6652, 10726, 8655, 11688, 10888, 5210)),
)
# Level-1 feeders join every dirty-zone state that had no railway, or lay far
# from one, to the nearest existing line. Each route stays inside zone states
# and runs between adjacent provinces from the junction to the state's VP.
DIRTY_ZONE_FEEDER_RAILS = (
    (1, (650, 3165, 12727, 9806)),  # state 152
    (1, (12727, 607, 3574, 5534)),  # state 153
    (1, (5534, 3217, 3781, 12867)),  # state 154
    (1, (1707, 11215, 12744)),  # state 222
    (1, (12867, 11199, 9785)),  # state 155
    (1, (12219, 6036, 1481, 9519, 813, 1132, 3783)),  # state 710
    (1, (9626, 7666, 7448, 3542, 7452)),  # state 711
    (1, (1112, 9740, 4513, 10415)),  # state 188
    (1, (2743, 5922, 10533)),  # state 215
    (1, (12231, 11099, 4945, 12428)),  # state 216
    (1, (6669, 2370, 16528)),  # state 204
    (1, (12581, 7409, 1193)),  # state 205
    (1, (10533, 9021, 12863)),  # state 209
    (1, (12863, 2838, 2137)),  # state 210
    (1, (2137, 7177, 2958, 2427)),  # state 212
    (1, (6151, 8687)),  # state 183
    (1, (12428, 599, 726)),  # state 206
    (1, (874, 2522, 2714)),  # state 330
    (1, (8687, 2617, 3130)),  # state 185
)
VORKERLAND_SUPPLY_HUB_STATES = {
    **KHAN_CAMPAIGN_SUPPLY_HUB_STATES,
    2427: 212,
    3783: 710,
    7452: 711,
    9806: 152,
    10533: 215,
    3728: 187,
    5637: 191,
    5780: 189,
    6387: 330,
    7164: 220,
    7399: 213,
    7445: 176,
    8655: 219,
    8664: 193,
    8981: 165,
    9031: 166,
    9846: 224,
    11334: 173,
    16516: 178,
    16522: 171,
    16534: 168,
    16536: 203,
    16639: 66,
    2539: 107,
    16643: 306,
    4148: 316,
    16642: 318,
}
# The western war runs along one trunk from the Vorkerland capital through
# the northern district and the Rimat corridor to the Itoran capital. Its
# records already exist; the generator owns their throughput. A hub receives
# no more than the weakest link behind it, so the two district links are
# raised together with the corridor.
VORKERLAND_CAPITAL_PROVINCE = 6713
WEST_TRUNK_RAIL_UPGRADES = (
    (2, (16399, 7885, 16388)),
    (2, (7885, 16395, 12227)),
    (
        2,
        (
            5135,
            12072,
            1029,
            7764,
            3743,
            10388,
            9453,
            7869,
            1128,
            2339,
            5469,
            2571,
            9908,
            2620,
            5568,
            161,
            4802,
            3147,
            9186,
            8071,
            12227,
        ),
    ),
    (2, (16379, 16367, 16355, 16361, 16370, 5135, 6801, 16578)),
    (2, (16568, 694, 5611, 2380, 16831, 10403, 8328, 11815, 4567, 6010, 16361)),
    (2, (16568, 694, 5611, 2380, 16831, 10403, 8328)),
)
# Itoran lines stay inside the starting borders and use the carved city
# provinces, never their rural parents: the IVN geography pass rewrites a
# parent to its city and would otherwise reroute the record.
ITORA_CAPITAL_PROVINCE = 16568
ITORA_SUPPLY_RAILS = (
    # Northern trunk: Old March - Dubravsk - Sredinsk - Verkhnemarsk - Northern March.
    (
        2,
        (
            16568,
            9066,
            16819,
            4909,
            1861,
            7508,
            8615,
            10158,
            10810,
            16830,
            3181,
            482,
            3541,
            16820,
            8068,
            2736,
            9053,
            16816,
        ),
    ),
    # Eastern trunk: Salemar line - Moressa - Vedrina - Serenga.
    (2, (8328, 9611, 11554, 5788, 2448, 8716, 3182, 8130, 3318, 4260, 4302, 16823)),
    # Northern frontier.
    (
        1,
        (
            16816,
            12614,
            8345,
            1697,
            3131,
            1971,
            2805,
            9790,
            9862,
            16822,
            3598,
            9685,
            10130,
            16824,
        ),
    ),
    (1, (1971, 3803, 8458, 16821, 8284, 16815)),
    (1, (12614, 1659, 16825)),
    # Western ring through the Rinval fens and the Longar hill line.
    (1, (16568, 9614, 401, 7263, 16827, 5273, 16863, 16828, 9132, 5055, 11487, 3304, 3541)),
    (1, (3181, 2211, 2025, 2157, 16826, 11132, 4037, 9133, 3245, 4553, 9100, 1971)),
    # Southern towns.
    (1, (2448, 957, 3951, 838)),
    (1, (16817, 11396, 882, 1091, 16818, 1421, 7453, 5187, 11985, 3318)),
    (1, (11815, 11396)),
    (1, (5611, 10313, 1890, 8839, 3453, 638, 9167, 9327)),
    (1, (5611, 16829)),
)
ITORA_SUPPLY_HUB_STATES = {
    16830: 716,  # Sredinsk.
    16816: 127,  # Northern March.
    16821: 131,
    16822: 130,
    16828: 697,  # Rinval.
    16826: 696,  # Longar.
    2448: 98,  # Moressa.
    3318: 95,  # Vedrina.
    882: 99,  # Lakora.
    9327: 101,  # Olsia.
}
# Corridor feeders give the front a second approach on each flank of the
# trunk: Serenga - Norven in the north, Talara - Norvein across the border and
# Rimat - Revel in the south, where the existing Revel spur closes the loop.
WEST_CORRIDOR_RAILS = (
    (1, (16823, 6507, 3729, 12738, 4659, 4166, 2896, 4528, 8032)),
    (1, (1421, 12072)),
    (
        1,
        (
            16591,
            4212,
            672,
            8468,
            4771,
            258,
            12241,
            12733,
            1129,
            9492,
            5170,
            8881,
            3757,
            2571,
            8059,
        ),
    ),
)
WEST_CORRIDOR_OWNERS = frozenset({"IVN", "PWR", "ZAO", "WRK"})
WEST_CORRIDOR_HUB_STATES = {3743: 91, 4166: 94, 12241: 71}
WEST_THEATRE_RAILS = (
    *WEST_TRUNK_RAIL_UPGRADES,
    *ITORA_SUPPLY_RAILS,
    *WEST_CORRIDOR_RAILS,
)
# Southern bloc and Furnace Union networks. Every state has a hub in itself or
# in a neighbouring state of the same country, and every hub is joined to its
# capital by rail inside the starting territory. Level-1 feeders follow
# physical borders from the hub to the nearest connected line.
SOUTH_CAPITAL_PROVINCES = {
    "NAM": 16716,
    "RHM": 16726,
    "SDR": 16727,
    "AZH": 16893,
    "WEF": 5869,
    "KDR": 16723,
    "GLP": 16740,
    "EFL": 16717,
    "SHL": 16713,
    "MZR": 16732,
    "KYZ": 16736,
}
SOUTH_SUPPLY_RAILS = {
    "NAM": (
        (1, (16716, 16881, 2038)),
        (1, (16890, 12668, 3127, 10967)),
    ),
    "SDR": (
        (1, (12578, 5590)),
        (1, (8946, 810)),
    ),
    "AZH": (
        (1, (6193, 9758)),
        (1, (16882, 13019, 12482, 6184, 729)),
    ),
    "KDR": (
        (1, (12825, 3134, 3139)),
        (1, (7497, 4198, 263, 11862, 7201, 1300, 2632, 4863, 5711)),
        (1, (4349, 3079, 5739, 939, 7201)),
    ),
    "GLP": (
        (1, (12583, 9672)),
        (1, (16731, 3643, 10952, 8580, 2073, 4350, 7708)),
        (1, (3415, 12369, 2342, 5473, 6512, 5595, 7073, 16796)),
    ),
    "SHL": (
        (1, (16899, 16794, 10927, 1149, 9742, 2412, 4995)),
        (1, (10949, 1900, 5451, 330, 7003, 5042, 7825)),
        (1, (3234, 7739, 834)),
        (1, (6126, 4537, 5042)),
    ),
    "MZR": (
        (1, (12452, 2249, 6904)),
        (1, (2806, 4357, 6747, 409, 9735, 3964, 5083, 1327)),
        (1, (16729, 261, 8120, 1299, 6153, 5293, 3504, 12452)),
    ),
    "KYZ": (
        (1, (5549, 7101, 3544, 2947, 3767, 10998, 5921, 16785, 16736)),
        (1, (12033, 10206, 5921)),
        (1, (16737, 16788, 3306, 1020, 7108, 2319, 2779, 12033)),
    ),
}
SOUTH_SUPPLY_HUB_STATES = {
    16890: 67,
    5869: 174,
    12825: 236,
    4349: 239,
    16723: 241,
    11597: 242,
    7497: 246,
    16725: 249,
    3614: 258,
    8946: 263,
    16729: 267,
    2806: 269,
    12452: 271,
    16731: 273,
    16732: 275,
    5549: 279,
    16737: 286,
    7825: 291,
    10949: 296,
    3415: 297,
    443: 703,
    12578: 704,
    12033: 706,
    16899: 707,
    12583: 708,
    8057: 720,
    16882: 728,
    6193: 729,
    3234: 730,
    6126: 733,
}
# Coastal NAM states are supplied through their ports; the two GLP states
# have no land route to the GLP network.
SOUTH_DETACHED_STATES = frozenset({225, 226, 227, 228, 229, 230, 231, 304, 305})
RETIRED_MARKERS = (
    "# BEGIN GENERATED: ADISCORD VORKERLAND THEATRE RAILS",
    "# END GENERATED: ADISCORD VORKERLAND THEATRE RAILS",
)


def render_managed_line() -> str:
    level, provinces = OSV_CAPITAL_RAIL
    route = " ".join(map(str, provinces))
    return f"{level} {len(provinces)} {route}"


def render_supply_connection(tag: str) -> str:
    level, provinces, _ = STARTING_SUPPLY_RAILS[tag]
    return f"{level} {len(provinces)} {' '.join(map(str, provinces))}"


def render_rail_line(level: int, provinces: tuple[int, ...]) -> str:
    return f"{level} {len(provinces)} {' '.join(map(str, provinces))}"


def render_khan_connection() -> str:
    level, provinces = KHAN_SUPPLY_RAIL
    return render_rail_line(level, provinces)


def render_khan_campaign_rail(level: int, provinces: tuple[int, ...]) -> str:
    return render_rail_line(level, provinces)


def _rail_route(line: str) -> tuple[int, ...] | None:
    fields = line.strip().split()
    if (
        len(fields) < 3
        or not all(field.isdigit() for field in fields)
        or int(fields[1]) != len(fields) - 2
    ):
        return None
    return tuple(map(int, fields[2:]))


def update_source(source: str) -> str:
    """Update owned rail records without rewriting equivalent Nudge records."""
    managed = [
        render_managed_line(),
        *(render_supply_connection(tag) for tag in STARTING_SUPPLY_RAILS),
        render_khan_connection(),
        *(
            render_khan_campaign_rail(level, provinces)
            for level, provinces in KHAN_CAMPAIGN_RAIL_UPGRADES
        ),
        *(
            render_rail_line(level, provinces)
            for level, provinces in DIRTY_ZONE_FEEDER_RAILS
        ),
        *(render_rail_line(level, provinces) for level, provinces in MON_SUPPLY_RAILS),
        render_rail_line(*MON_KALTEN_RAIL),
        *(render_rail_line(level, route) for routes in COALITION_SUPPLY_RAILS.values() for level, route in routes),
        *(render_rail_line(level, route) for level, route in WEST_THEATRE_RAILS),
        *(render_rail_line(level, route) for routes in SOUTH_SUPPLY_RAILS.values() for level, route in routes),
    ]
    managed_routes = {_rail_route(line): line for line in managed}
    seen = set()
    lines = []
    for line in source.replace("\r\n", "\n").splitlines():
        if line.strip() in RETIRED_MARKERS:
            continue
        route = _rail_route(line)
        if route not in managed_routes:
            lines.append(line)
            continue
        if route in seen:
            continue
        expected = managed_routes[route]
        lines.append(line if line.split() == expected.split() else expected)
        seen.add(route)
    lines.extend(line for route, line in managed_routes.items() if route not in seen)
    return "\n".join(lines) + "\n"


def render_supply_node(province_id: int) -> str:
    return f"1 {province_id}"


def update_supply_source(source: str) -> str:
    """Append missing hubs and preserve the formatting of existing records."""
    hub_states = {
        **VORKERLAND_SUPPLY_HUB_STATES,
        **MON_SUPPLY_HUB_STATES,
        **COALITION_SUPPLY_HUB_STATES,
        **ITORA_SUPPLY_HUB_STATES,
        **WEST_CORRIDOR_HUB_STATES,
        **SOUTH_SUPPLY_HUB_STATES,
    }
    managed = {
        render_supply_node(province_id) for province_id in hub_states
    }
    seen = set()
    lines = []
    for line in source.replace("\r\n", "\n").splitlines():
        record = line.strip()
        if record in managed:
            if record in seen:
                continue
            seen.add(record)
        lines.append(line)
    lines.extend(
        render_supply_node(province_id)
        for province_id in sorted(hub_states)
        if render_supply_node(province_id) not in seen
    )
    return "\n".join(lines) + "\n"


def _reached_by_rail(
    start: int,
    rail_graph: dict[int, set[int]],
    allowed: Callable[[int], bool],
) -> set[int]:
    """Return the provinces joined to start by rail through allowed provinces."""
    pending = [start]
    reached = {start}
    while pending:
        province = pending.pop()
        for neighbour in rail_graph[province]:
            if neighbour not in reached and allowed(neighbour):
                reached.add(neighbour)
                pending.append(neighbour)
    return reached


def west_theatre_issues(
    rail_lines: list[str],
    supply_lines: list[str],
    province_types: dict[int, str],
    physical: dict[int, set[int]],
    state_by_province: dict[int, int],
    state_owners: dict[int, str],
) -> list[str]:
    """Validate the Vorkerland-Itora trunk, the Itoran network and corridor feeders."""
    issues: list[str] = []

    def owner(province: int) -> str | None:
        return state_owners.get(state_by_province.get(province))

    graphs: dict[int, dict[int, set[int]]] = {
        1: defaultdict(set),
        2: defaultdict(set),
    }
    for line in rail_lines:
        fields = line.split()
        route = _rail_route(line)
        if route is None or int(fields[0]) < 1:
            continue
        for minimum_level, graph in graphs.items():
            if int(fields[0]) < minimum_level:
                continue
            for first, second in zip(route, route[1:]):
                if second in physical.get(first, set()):
                    graph[first].add(second)
                    graph[second].add(first)

    for level, route in WEST_THEATRE_RAILS:
        label = "-".join(map(str, route))
        if rail_lines.count(render_rail_line(level, route)) != 1:
            issues.append(
                f"western rail {label} must occur exactly once at level {level}"
            )
        for province in route:
            if province_types.get(province) != "land":
                issues.append(f"western rail leaves land at {province}")
        for first, second in zip(route, route[1:]):
            if second not in physical.get(first, set()):
                issues.append(
                    f"western rail segment {first}-{second} is not physically adjacent"
                )
    for _, route in ITORA_SUPPLY_RAILS:
        for province in route:
            if owner(province) != "IVN":
                issues.append(
                    f"Itoran railway leaves its starting territory at {province}"
                )
    for _, route in WEST_CORRIDOR_RAILS:
        for province in route:
            if owner(province) not in WEST_CORRIDOR_OWNERS:
                issues.append(f"western corridor railway leaves the theatre at {province}")

    # The attacker is supplied only through an unbroken level-2 trunk.
    trunk = _reached_by_rail(
        VORKERLAND_CAPITAL_PROVINCE, graphs[2], lambda province: True
    )
    if ITORA_CAPITAL_PROVINCE not in trunk:
        issues.append(
            "western trunk is not level 2 between Vorkerland and the Itoran capital"
        )
    itoran = _reached_by_rail(
        ITORA_CAPITAL_PROVINCE,
        graphs[1],
        lambda province: owner(province) == "IVN",
    )
    for hub, expected_state in ITORA_SUPPLY_HUB_STATES.items():
        if supply_lines.count(render_supply_node(hub)) != 1:
            issues.append(f"Itoran supply hub {hub} must occur exactly once")
        if (
            state_by_province.get(hub) != expected_state
            or state_owners.get(expected_state) != "IVN"
        ):
            issues.append(f"Itoran supply hub {hub} moved outside its starting state")
        if province_types.get(hub) != "land":
            issues.append(f"Itoran supply hub {hub} is not on land")
        if hub not in itoran:
            issues.append(
                f"Itoran supply hub {hub} is disconnected from the capital inside its starting territory"
            )
    corridor = _reached_by_rail(
        VORKERLAND_CAPITAL_PROVINCE, graphs[1], lambda province: True
    )
    for hub, expected_state in WEST_CORRIDOR_HUB_STATES.items():
        if supply_lines.count(render_supply_node(hub)) != 1:
            issues.append(f"western corridor supply hub {hub} must occur exactly once")
        if state_by_province.get(hub) != expected_state:
            issues.append(f"western corridor supply hub {hub} moved outside its state")
        if province_types.get(hub) != "land":
            issues.append(f"western corridor supply hub {hub} is not on land")
        if hub not in corridor:
            issues.append(
                f"western corridor supply hub {hub} is disconnected from Vorkerland"
            )
    return issues


def south_theatre_issues(
    rail_lines: list[str],
    supply_lines: list[str],
    province_types: dict[int, str],
    physical: dict[int, set[int]],
    state_by_province: dict[int, int],
    state_owners: dict[int, str],
) -> list[str]:
    """Validate southern feeders, hub placement, capital links and state coverage."""
    issues: list[str] = []

    def owner(province: int) -> str | None:
        return state_owners.get(state_by_province.get(province))

    rail_graph: dict[int, set[int]] = defaultdict(set)
    for line in rail_lines:
        route = _rail_route(line)
        if route is None or int(line.split()[0]) < 1:
            continue
        for first, second in zip(route, route[1:]):
            if second in physical.get(first, set()):
                rail_graph[first].add(second)
                rail_graph[second].add(first)
    for tag, routes in SOUTH_SUPPLY_RAILS.items():
        for level, route in routes:
            if rail_lines.count(render_rail_line(level, route)) != 1:
                issues.append(f"{tag} southern feeder must occur exactly once: {route}")
            for province in route:
                if province_types.get(province) != "land" or owner(province) != tag:
                    issues.append(f"{tag} southern feeder leaves its own land at {province}")
            for first, second in zip(route, route[1:]):
                if second not in physical.get(first, set()):
                    issues.append(f"{tag} southern feeder is not adjacent: {first}-{second}")
    hub_states: dict[str, set[int]] = defaultdict(set)
    for line in supply_lines:
        fields = line.split()
        if len(fields) == 2 and fields[1].isdigit():
            state = state_by_province.get(int(fields[1]))
            if state in state_owners:
                hub_states[state_owners[state]].add(state)
    for hub, expected_state in SOUTH_SUPPLY_HUB_STATES.items():
        if supply_lines.count(render_supply_node(hub)) != 1:
            issues.append(f"southern supply hub {hub} must occur exactly once")
        if state_by_province.get(hub) != expected_state or province_types.get(hub) != "land":
            issues.append(f"southern supply hub {hub} moved outside state {expected_state}")
    state_neighbours: dict[int, set[int]] = defaultdict(set)
    for province, neighbours in physical.items():
        for neighbour in neighbours:
            first, second = state_by_province.get(province), state_by_province.get(neighbour)
            if first and second and first != second:
                state_neighbours[first].add(second)
    for tag, capital in SOUTH_CAPITAL_PROVINCES.items():
        reached = _reached_by_rail(capital, rail_graph, lambda province: owner(province) == tag)
        for hub, state in SOUTH_SUPPLY_HUB_STATES.items():
            if state_owners.get(state) == tag and hub not in reached:
                issues.append(f"{tag} supply hub {hub} is disconnected from the capital inside its territory")
        for state, state_owner in state_owners.items():
            if state_owner != tag or state in SOUTH_DETACHED_STATES:
                continue
            nearby = {state} | {other for other in state_neighbours[state] if state_owners.get(other) == tag}
            if not nearby & hub_states[tag]:
                issues.append(f"{tag} state {state} has no supply hub in itself or a neighbouring own state")
    return issues


def validate() -> list[str]:
    issues: list[str] = []
    raw = RAILWAYS_PATH.read_bytes()
    source = "\n".join(line.strip() for line in raw.decode("utf-8-sig").splitlines())
    level, provinces = OSV_CAPITAL_RAIL
    expected_line = render_managed_line()
    if source.splitlines().count(expected_line) != 1:
        issues.append("OSV capital rail must occur exactly once")
    for marker in RETIRED_MARKERS:
        if marker in source:
            issues.append("map/railways.txt must remain numeric-only")
    for rail_level, rail_route in (*KHAN_CAMPAIGN_RAIL_UPGRADES, *DIRTY_ZONE_FEEDER_RAILS):
        expected_rail = render_khan_campaign_rail(rail_level, rail_route)
        if source.splitlines().count(expected_rail) != 1:
            issues.append(
                f"RUS campaign rail {'-'.join(map(str, rail_route))} must occur exactly once at level {rail_level}"
            )

    supply_source = SUPPLY_NODES_PATH.read_text(
        encoding="utf-8-sig", errors="strict"
    ).replace("\r\n", "\n")
    supply_lines = [line.strip() for line in supply_source.splitlines() if line.strip()]
    for province_id in VORKERLAND_SUPPLY_HUB_STATES:
        expected_supply = render_supply_node(province_id)
        if supply_lines.count(expected_supply) != 1:
            issues.append(
                f"Vorkerland supply hub {province_id} must occur exactly once"
            )

    try:
        states = map_regions.load_states()
        state_by_province = {
            province_id: state_id
            for state_id, state_provinces in states.items()
            for province_id in state_provinces
        }
        wrong_states = {
            province_id: state_by_province.get(province_id)
            for province_id in provinces
            if state_by_province.get(province_id) != OSV_CAPITAL_STATE
        }
        if wrong_states:
            issues.append(f"OSV capital rail leaves state 318: {wrong_states}")

        wrong_hub_states = {
            province_id: state_by_province.get(province_id)
            for province_id, expected_state in VORKERLAND_SUPPLY_HUB_STATES.items()
            if state_by_province.get(province_id) != expected_state
        }
        if wrong_hub_states:
            issues.append(
                f"Vorkerland supply hubs moved outside their states: {wrong_hub_states}"
            )

        province_types, colors = map_regions.load_province_definitions()
        physical = map_regions.load_province_adjacency(
            province_types,
            colors,
            include_special_adjacencies=False,
        )
        for first, second in zip(provinces, provinces[1:]):
            if (
                province_types.get(first) != "land"
                or province_types.get(second) != "land"
            ):
                issues.append(
                    f"OSV rail segment {first}-{second} is not entirely on land"
                )
            if second not in physical.get(first, set()):
                issues.append(
                    f"OSV rail segment {first}-{second} is not physically adjacent"
                )
        for _, campaign_route in KHAN_CAMPAIGN_RAIL_UPGRADES:
            for first, second in zip(campaign_route, campaign_route[1:]):
                if (
                    province_types.get(first) != "land"
                    or province_types.get(second) != "land"
                ):
                    issues.append(
                        f"RUS campaign rail segment {first}-{second} is not entirely on land"
                    )
                if second not in physical.get(first, set()):
                    issues.append(
                        f"RUS campaign rail segment {first}-{second} is not physically adjacent"
                    )
        railway_provinces = {
            int(province_id)
            for line in source.splitlines()
            if (parts := line.split()) and all(part.isdigit() for part in parts)
            for province_id in parts[2:]
        }
        for province_id in VORKERLAND_SUPPLY_HUB_STATES:
            if province_types.get(province_id) != "land":
                issues.append(f"Vorkerland supply hub {province_id} is not on land")
            if province_id not in railway_provinces:
                issues.append(
                    f"Vorkerland supply hub {province_id} is not on a railway"
                )
        state_owners = {}
        for path in (ROOT / "history/states").glob("*.txt"):
            history = path.read_text(encoding="utf-8-sig")
            state = re.search(r"\bid\s*=\s*(\d+)", history)
            owner = re.search(r"\bowner\s*=\s*([A-Z0-9]+)", history)
            if state and owner:
                state_owners[int(state.group(1))] = owner.group(1)
        rail_graph: dict[int, set[int]] = defaultdict(set)
        for line in source.splitlines():
            parts = line.split()
            if (
                len(parts) > 2
                and all(part.isdigit() for part in parts)
                and int(parts[0]) > 0
                and int(parts[1]) == len(parts) - 2
            ):
                route = tuple(map(int, parts[2:]))
                for first, second in zip(route, route[1:]):
                    if (
                        province_types.get(first) == "land"
                        and province_types.get(second) == "land"
                        and second in physical.get(first, set())
                    ):
                        rail_graph[first].add(second)
                        rail_graph[second].add(first)
        for rail_level, route in MON_SUPPLY_RAILS:
            expected = render_rail_line(rail_level, route)
            if source.splitlines().count(expected) != 1:
                issues.append(
                    f"MON rail {'-'.join(map(str, route))} must occur exactly once at level {rail_level}"
                )
            for province in route:
                if province_types.get(province) != "land":
                    issues.append(f"MON railway leaves land at {province}")
                if state_owners.get(state_by_province.get(province)) != "MON":
                    issues.append(
                        f"MON railway leaves its starting territory at {province}"
                    )
            for first, second in zip(route, route[1:]):
                if second not in physical.get(first, set()):
                    issues.append(
                        f"MON rail segment {first}-{second} is not physically adjacent"
                    )
        pending = [MON_CAPITAL_PROVINCE]
        reached = set(pending)
        while pending:
            province = pending.pop()
            for neighbour in rail_graph[province]:
                if (
                    neighbour not in reached
                    and state_owners.get(state_by_province.get(neighbour)) == "MON"
                ):
                    reached.add(neighbour)
                    pending.append(neighbour)
        for hub, expected_state in MON_SUPPLY_HUB_STATES.items():
            if supply_lines.count(render_supply_node(hub)) != 1:
                issues.append(f"MON supply hub {hub} must occur exactly once")
            if (
                state_by_province.get(hub) != expected_state
                or state_owners.get(expected_state) != "MON"
            ):
                issues.append(f"MON supply hub {hub} moved outside its starting state")
            if province_types.get(hub) != "land":
                issues.append(f"MON supply hub {hub} is not on land")
            if hub not in reached:
                issues.append(
                    f"MON supply hub {hub} is disconnected from the capital inside its starting territory"
                )
        kalten_level, kalten_route = MON_KALTEN_RAIL
        if source.splitlines().count(render_rail_line(kalten_level, kalten_route)) != 1:
            issues.append("MON Kalten connection must occur exactly once at level 1")
        for province, expected_state in zip(kalten_route, (460, 460, 460, 460, 710)):
            if (
                province_types.get(province) != "land"
                or state_by_province.get(province) != expected_state
            ):
                issues.append(f"MON Kalten connection leaves its border corridor at {province}")
        for first, second in zip(kalten_route, kalten_route[1:]):
            if second not in physical.get(first, set()):
                issues.append(f"MON Kalten rail segment {first}-{second} is not physically adjacent")
        corridor_states = MON_KALTEN_CORRIDOR_STATES | {
            state for state, owner in state_owners.items() if owner == "MON"
        }
        pending = [MON_CAPITAL_PROVINCE]
        reached = set(pending)
        while pending:
            province = pending.pop()
            for neighbour in rail_graph[province]:
                if (
                    neighbour not in reached
                    and state_by_province.get(neighbour) in corridor_states
                ):
                    reached.add(neighbour)
                    pending.append(neighbour)
        for hub in MON_KALTEN_CORRIDOR_HUBS:
            if hub not in reached:
                issues.append(
                    f"MON corridor supply hub {hub} is disconnected from the capital without Starolesye"
                )
        for tag, routes in COALITION_SUPPLY_RAILS.items():
            owned_graph = defaultdict(set)
            for level, route in routes:
                if source.splitlines().count(render_rail_line(level, route)) != 1:
                    issues.append(f"{tag} coalition rail must occur exactly once: {route}")
                for province in route:
                    if province_types.get(province) != "land" or state_owners.get(state_by_province.get(province)) != tag:
                        issues.append(f"{tag} coalition rail leaves its own land at {province}")
                for first, second in zip(route, route[1:]):
                    if second not in physical.get(first, set()):
                        issues.append(f"{tag} coalition rail is not adjacent: {first}-{second}")
                    owned_graph[first].add(second)
                    owned_graph[second].add(first)
            capital, hub, port = COALITION_SUPPLY_ENDPOINTS[tag]
            pending = [capital]
            reached = {capital}
            while pending:
                for neighbour in owned_graph[pending.pop()] - reached:
                    reached.add(neighbour)
                    pending.append(neighbour)
            if not {hub, port} <= reached:
                issues.append(f"{tag} level-2 capital, hub and port network is disconnected")
            if supply_lines.count(render_supply_node(hub)) != 1:
                issues.append(f"{tag} forward supply hub {hub} must occur exactly once")
            if state_by_province.get(hub) != COALITION_SUPPLY_HUB_STATES[hub]:
                issues.append(f"{tag} forward supply hub {hub} moved outside its state")
        for tag, (_, route, hubs) in STARTING_SUPPLY_RAILS.items():
            if source.splitlines().count(render_supply_connection(tag)) != 1:
                issues.append(f"{tag} supply connection must occur exactly once")
            for province in route:
                if province_types.get(province) != "land":
                    issues.append(f"{tag} supply connection leaves land at {province}")
                if state_owners.get(state_by_province.get(province)) != tag:
                    issues.append(
                        f"{tag} supply connection leaves its starting territory at {province}"
                    )
            for first, second in zip(route, route[1:]):
                if second not in physical.get(first, set()):
                    issues.append(
                        f"{tag} rail segment {first}-{second} is not physically adjacent"
                    )
            pending = [hubs[0]]
            reached = {hubs[0]}
            while pending:
                province = pending.pop()
                for neighbour in rail_graph[province]:
                    if (
                        neighbour not in reached
                        and state_owners.get(state_by_province.get(neighbour)) == tag
                    ):
                        reached.add(neighbour)
                        pending.append(neighbour)
            if hubs[1] not in reached:
                issues.append(
                    f"{tag} supply hubs {hubs[0]} and {hubs[1]} are disconnected inside its starting territory"
                )
        if source.splitlines().count(render_khan_connection()) != 1:
            issues.append("RUS border supply connection must occur exactly once")
        for province in KHAN_SUPPLY_RAIL[1]:
            if (
                province_types.get(province) != "land"
                or state_by_province.get(province) not in KHAN_SUPPLY_STATES
            ):
                issues.append(
                    f"RUS border supply connection leaves its campaign territory at {province}"
                )
        for first, second in zip(KHAN_SUPPLY_RAIL[1], KHAN_SUPPLY_RAIL[1][1:]):
            if second not in physical.get(first, set()):
                issues.append(
                    f"RUS rail segment {first}-{second} is not physically adjacent"
                )
        pending = [KHAN_SUPPLY_HUBS[0]]
        reached = set(pending)
        while pending:
            province = pending.pop()
            for neighbour in rail_graph[province]:
                if (
                    neighbour not in reached
                    and state_by_province.get(neighbour) in KHAN_SUPPLY_STATES
                ):
                    reached.add(neighbour)
                    pending.append(neighbour)
        for hub in KHAN_SUPPLY_HUBS:
            if hub not in reached:
                issues.append(
                    f"RUS border supply hub {hub} is disconnected from the capital within states 66/49/176"
                )
            if supply_lines.count(render_supply_node(hub)) != 1:
                issues.append(f"RUS border supply hub {hub} must occur exactly once")
        issues.extend(
            west_theatre_issues(
                source.splitlines(),
                supply_lines,
                province_types,
                physical,
                state_by_province,
                state_owners,
            )
        )
        issues.extend(
            south_theatre_issues(
                source.splitlines(),
                supply_lines,
                province_types,
                physical,
                state_by_province,
                state_owners,
            )
        )
        campaign_states = {66}
        for tag, core_states in DIRTY_GROUPS.items():
            campaign_states.update(core_states)
            campaign_states.update(EXZ_REMAINDER_GROUPS.get(tag, ()))
        campaign_states.difference_update(DIRTY_INITIAL_OWNER_OVERRIDES)
        supply_corridors = (
            (
                "Starolesye",
                {66, *DIRTY_GROUPS["SLA"], *EXZ_REMAINDER_GROUPS["SLA"]},
                (5032, 12219, 16630),
            ),
            ("campaign", campaign_states, tuple(KHAN_CAMPAIGN_SUPPLY_HUB_STATES)),
        )
        for corridor, allowed_states, hubs in supply_corridors:
            pending = [KHAN_SUPPLY_HUBS[0]]
            reached = set(pending)
            while pending:
                province = pending.pop()
                for neighbour in rail_graph[province]:
                    if (
                        neighbour not in reached
                        and state_by_province.get(neighbour) in allowed_states
                    ):
                        reached.add(neighbour)
                        pending.append(neighbour)
            for hub in hubs:
                if hub not in reached:
                    issues.append(
                        f"RUS {corridor} supply hub {hub} is disconnected from the capital inside its campaign territory"
                    )
    except (OSError, RuntimeError, ValueError, KeyError) as error:
        issues.append(f"cannot validate campaign rail geography: {error}")
    return issues


def apply() -> None:
    raw = RAILWAYS_PATH.read_bytes()
    newline = "\r\n" if b"\r\n" in raw else "\n"
    source = raw.decode("utf-8-sig")
    updated = update_source(source).replace("\n", newline)
    if updated.encode("utf-8") != raw:
        RAILWAYS_PATH.write_bytes(updated.encode("utf-8"))

    supply_raw = SUPPLY_NODES_PATH.read_bytes()
    supply_newline = "\r\n" if b"\r\n" in supply_raw else "\n"
    supply_source = supply_raw.decode("utf-8-sig")
    updated_supply = update_supply_source(supply_source)
    if updated_supply != supply_source.replace("\r\n", "\n"):
        SUPPLY_NODES_PATH.write_bytes(
            updated_supply.replace("\n", supply_newline).encode("utf-8")
        )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate bounded campaign rail connections and supply hubs."
    )
    actions = parser.add_mutually_exclusive_group()
    actions.add_argument(
        "--check",
        action="store_true",
        help="validate current generated output (default)",
    )
    actions.add_argument(
        "--apply", action="store_true", help="write the generated rail block"
    )
    args = parser.parse_args()

    if args.apply:
        apply()
    issues = validate()
    if issues:
        print("Vorkerland theatre rail validation failed:")
        for issue in issues:
            print(f"- {issue}")
        return 1
    print(
        "Campaign rail validation passed: OSV spur, STP/YPR connections, MON network, RUS campaign spines, western and southern theatres and managed supply hubs."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
