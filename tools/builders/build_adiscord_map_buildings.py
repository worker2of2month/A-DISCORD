#!/usr/bin/env python3
"""Synchronize map/buildings.txt state ids with the current province partition.

The Nudge building coordinates are authoritative.  State generators can move a
province out of a former catch-all state without moving its map objects; HOI4
then ignores those objects and may crash while rebuilding supply/front data
after a large ownership change.  Floating harbours are excluded because their
coordinates intentionally sit in sea provinces.
"""

from __future__ import annotations

import argparse
import csv
import json
from math import atan2
import re
from dataclasses import dataclass
from pathlib import Path

from PIL import Image
from tools.lib.paths import repository_root


ROOT = repository_root()
BUILDINGS_PATH = ROOT / "map" / "buildings.txt"
PROVINCES_PATH = ROOT / "map" / "provinces.bmp"
DEFINITION_PATH = ROOT / "map" / "definition.csv"
STATE_DIR = ROOT / "history" / "states"
SEA_POSITIONED_TYPES = {"floating_harbor"}
PORT_ANCHOR_TYPES = {
    "coastal_bunker",
    "dockyard",
    "naval_base_spawn",
    "naval_headquarters",
    "naval_supply_hub",
}
COASTAL_ADDITION_PROVINCES = frozenset(
    {6008, 7739, 2038, 7618, 16707, 16708, 16709, 16710, 16712, 16716, *range(16802, 16809)}
)
for city in json.loads(
    (ROOT / "tools/data/adiscord_southern_cities.json").read_text(encoding="utf-8")
)["cities"]:
    COASTAL_ADDITION_PROVINCES |= {
        city["parent"],
        city["province"],
        *(sector["province"] for sector in city.get("sectors", ())),
    }
REQUIRED_STATE_SPAWN_COUNTS = {
    "air_base": 1,
    "anti_air_building": 3,
    "fuel_silo": 1,
    "nuclear_reactor_spawn": 1,
    "radar_station": 1,
    "rocket_site_spawn": 1,
    "stronghold_network": 1,
    "synthetic_refinery": 1,
}
CITY_SPAWN_COUNTS = {
    "industrial_complex": 3,
    "arms_factory": 3,
    "special_project_facility_spawn": 1,
}


def required_spawns(state_id: int) -> dict[str, int]:
    if state_id in (241, 253, 260, 275, 283, 294, 300, 699, 700, 701, 709):
        return {**REQUIRED_STATE_SPAWN_COUNTS, **CITY_SPAWN_COUNTS}
    return REQUIRED_STATE_SPAWN_COUNTS


# The deliberate resource-war split assigns the original state positions to
# their physical provinces. Every resulting state still needs the complete set
# of 1.19 spawn anchors even when a building is not present at game start.
NAM_RESOURCE_WAR_SPAWN_STATES = {67, 68, 69, 70, 688, 689, 690, 691, 692}
NAM_SPLIT_SPAWN_POSITION_CANDIDATES = {
    (67, "air_base"): ("67;air_base;3701.00;10.25;548.00;0.66;0",),
    (67, "anti_air_building"): (
        "67;anti_air_building;3701.00;10.25;548.00;0.66;0",
        "67;anti_air_building;3690.00;10.80;575.00;4.36;0",
    ),
    (67, "stronghold_network"): ("67;stronghold_network;3724.00;10.60;605.00;5.21;0",),
    (67, "synthetic_refinery"): ("67;synthetic_refinery;3700.00;10.80;583.00;4.75;0",),
    (688, "anti_air_building"): ("688;anti_air_building;3599.00;10.35;600.00;2.76;0",),
    (688, "fuel_silo"): ("688;fuel_silo;3609.00;10.53;605.00;2.82;0",),
    (688, "nuclear_reactor_spawn"): (
        "688;nuclear_reactor_spawn;3611.00;10.65;605.00;6.27;0",
    ),
    (688, "radar_station"): ("688;radar_station;3641.00;10.60;593.00;1.25;0",),
    (688, "rocket_site_spawn"): ("688;rocket_site_spawn;3638.00;11.00;614.00;5.94;0",),
    (688, "stronghold_network"): (
        "688;stronghold_network;3616.00;10.50;594.00;4.14;0",
    ),
    (689, "air_base"): ("689;air_base;3666.00;10.65;540.00;2.65;0",),
    (689, "anti_air_building"): (
        "689;anti_air_building;3665.00;10.80;545.00;0.57;0",
        "689;anti_air_building;3699.00;10.50;527.00;5.76;0",
        "689;anti_air_building;3675.00;10.30;535.00;4.14;0",
    ),
    (689, "fuel_silo"): ("689;fuel_silo;3689.00;11.00;551.00;4.33;0",),
    (689, "nuclear_reactor_spawn"): (
        "689;nuclear_reactor_spawn;3669.00;10.65;543.00;3.55;0",
    ),
    (689, "radar_station"): ("689;radar_station;3653.00;10.45;555.00;2.77;0",),
    (689, "rocket_site_spawn"): ("689;rocket_site_spawn;3696.00;10.30;527.00;0.15;0",),
    (689, "synthetic_refinery"): (
        "689;synthetic_refinery;3683.00;10.60;540.00;2.69;0",
    ),
}

# States created by reviewed province repartitions. Existing building
# coordinates follow the moved provinces; every resulting state still needs
# one complete set of HOI4 1.19 construction anchors of its own.
EXCLUSION_BOUNDARY_SPAWN_STATES = {
    241,
    253,
    260,
    275,
    283,
    294,
    300,
    699,
    700,
    701,
    702,
    703,
    704,
    705,
    706,
    707,
    708,
    709,
    49,
    51,
    153,
    154,
    155,
    165,
    166,
    169,
    173,
    180,
    184,
    185,
    187,
    189,
    193,
    210,
    211,
    213,
    214,
    215,
    222,
    223,
    224,
    329,
    330,
    160,
    454,
    455,
    460,
    461,
    472,
    25,
    128,
    693,
    694,
    695,
    696,
    697,
    698,
}


@dataclass(frozen=True)
class BuildingMismatch:
    line: int
    building_type: str
    recorded_state: int
    actual_state: int
    province: int


def load_state_by_province(root: Path = ROOT) -> dict[int, int]:
    state_by_province: dict[int, int] = {}
    for path in sorted((root / "history" / "states").glob("*.txt")):
        source = path.read_text(encoding="utf-8-sig", errors="strict")
        state_match = re.search(r"\bid\s*=\s*(\d+)", source)
        province_match = re.search(r"\bprovinces\s*=\s*\{([^}]*)\}", source, re.DOTALL)
        if not state_match or not province_match:
            continue
        state_id = int(state_match.group(1))
        for province in map(int, re.findall(r"\d+", province_match.group(1))):
            previous = state_by_province.setdefault(province, state_id)
            if previous != state_id:
                raise RuntimeError(
                    f"province {province} is assigned to states {previous} and {state_id}"
                )
    return state_by_province


def load_province_by_color(root: Path = ROOT) -> dict[tuple[int, int, int], int]:
    province_by_color: dict[tuple[int, int, int], int] = {}
    with (root / "map" / "definition.csv").open(
        encoding="utf-8-sig", newline=""
    ) as source:
        for row in csv.reader(source, delimiter=";"):
            if len(row) < 4 or not row[0].isdigit():
                continue
            color = tuple(map(int, row[1:4]))
            province = int(row[0])
            previous = province_by_color.setdefault(color, province)
            if previous != province:
                raise RuntimeError(f"definition.csv duplicates province colour {color}")
    return province_by_color


def _pixel_coordinate(value: str, maximum: int) -> int:
    coordinate = round(float(value))
    if not 0 <= coordinate < maximum:
        raise ValueError(f"map coordinate {value} is outside 0..{maximum - 1}")
    return coordinate


def audit_buildings(root: Path = ROOT) -> tuple[list[str], list[BuildingMismatch]]:
    path = root / "map" / "buildings.txt"
    lines = path.read_text(encoding="utf-8-sig", errors="strict").splitlines()
    state_by_province = load_state_by_province(root)
    province_by_color = load_province_by_color(root)
    mismatches: list[BuildingMismatch] = []

    with Image.open(root / "map" / "provinces.bmp") as source:
        image = source.convert("RGB")
        for line_number, line in enumerate(lines, 1):
            fields = line.split(";")
            if len(fields) != 7 or not fields[0].isdigit():
                raise RuntimeError(
                    f"map/buildings.txt:{line_number}: malformed building row"
                )
            building_type = fields[1]
            if building_type in SEA_POSITIONED_TYPES:
                continue
            x = _pixel_coordinate(fields[2], image.width)
            z = _pixel_coordinate(fields[4], image.height)
            province = province_by_color.get(image.getpixel((x, image.height - 1 - z)))
            actual_state = (
                state_by_province.get(province) if province is not None else None
            )
            if actual_state is None:
                raise RuntimeError(
                    f"map/buildings.txt:{line_number}: {building_type} is not positioned in a state province"
                )
            recorded_state = int(fields[0])
            if recorded_state != actual_state:
                mismatches.append(
                    BuildingMismatch(
                        line=line_number,
                        building_type=building_type,
                        recorded_state=recorded_state,
                        actual_state=actual_state,
                        province=province,
                    )
                )
    return lines, mismatches


def mountain_building_heights(
    root: Path, lines: list[str]
) -> tuple[list[str], list[int]]:
    from tools.builders.build_adiscord_coastal_geography import RELIEF_PROVINCES

    province_by_color = load_province_by_color(root)
    result = list(lines)
    changed = []
    with (
        Image.open(root / "map/provinces.bmp") as provinces,
        Image.open(root / "map/heightmap.bmp") as heights,
    ):
        for index, line in enumerate(lines):
            fields = line.split(";")
            if fields[1] in SEA_POSITIONED_TYPES:
                continue
            x = _pixel_coordinate(fields[2], provinces.width)
            y = provinces.height - 1 - _pixel_coordinate(fields[4], provinces.height)
            if (
                province_by_color.get(provinces.getpixel((x, y)))
                not in RELIEF_PROVINCES
            ):
                continue
            expected = heights.getpixel((x, y)) / 10
            if abs(float(fields[3]) - expected) > 0.005:
                fields[3] = f"{expected:.2f}"
                result[index] = ";".join(fields)
                changed.append(index + 1)
    return result, changed


def synchronize_buildings(
    root: Path = ROOT, *, apply: bool = False
) -> list[BuildingMismatch]:
    lines, mismatches = audit_buildings(root)
    if apply:
        for mismatch in mismatches:
            fields = lines[mismatch.line - 1].split(";")
            fields[0] = str(mismatch.actual_state)
            lines[mismatch.line - 1] = ";".join(fields)
        lines, _height_changes = mountain_building_heights(root, lines)
        lines = interior_dam_anchor(lines)
        lines = bezhaysk_castle_clearance(lines)
        lines = khan_bunker_clearance(lines)
        lines = permanent_landmark_clearance(lines)
        # Nudge writes this file with CRLF and no final newline. The engine
        # treats a terminal empty row as a malformed building definition, so
        # preserve both details when regenerating the file.
        payload = "\r\n".join(lines).encode("utf-8")
        (root / "map" / "buildings.txt").write_bytes(payload)
    return mismatches


def interior_dam_anchor(lines: list[str]) -> list[str]:
    """Keep the dam inside its state under both native truncation and rounding."""
    result = []
    for line in lines:
        fields = line.split(";")
        if fields[:2] == ["53", "dam_spawn"]:
            fields[2], fields[4] = "3751.00", "947.00"
            line = ";".join(fields)
        result.append(line)
    return result


def bezhaysk_castle_clearance(lines: list[str]) -> list[str]:
    """Keep native building visuals outside the permanent Grayson castle footprint."""
    placements = {
        ("supply_node", "3782.00", "968.00"): ("3783.00", "11.30", "971.10"),
        ("anti_air_building", "3782.00", "968.00"): ("3788.00", "11.00", "970.00"),
        ("industrial_complex", "3783.00", "970.00"): ("3788.00", "11.00", "974.00"),
        ("arms_factory", "3784.00", "967.00"): ("3787.00", "10.80", "964.00"),
        ("air_base", "3786.00", "967.00"): ("3788.00", "11.00", "966.00"),
        ("bunker", "3785.00", "968.00"): ("3783.00", "11.10", "965.00"),
        ("nuclear_reactor_spawn", "3784.00", "966.00"): ("3788.00", "11.00", "965.00"),
        ("special_project_facility_spawn", "3785.00", "967.00"): ("3786.80", "11.00", "965.50"),
    }
    result = []
    for line in lines:
        fields = line.split(";")
        if len(fields) == 7 and fields[0] == "41":
            position = placements.get((fields[1], fields[2], fields[4]))
            if position is not None:
                fields[2:5] = position
                line = ";".join(fields)
        result.append(line)
    return result


def khan_bunker_clearance(lines: list[str]) -> list[str]:
    """Keep the generic fort south of the permanent Khan bunker landmark."""
    result = []
    for line in lines:
        fields = line.split(";")
        if len(fields) == 7 and fields[:2] == ["66", "bunker"]:
            fields[2:5] = ["3482.00", "13.80", "942.00"]
            line = ";".join(fields)
        result.append(line)
    return result


def permanent_landmark_clearance(lines: list[str]) -> list[str]:
    """Move vanilla building visuals away from large always-visible landmarks.

    These are authored map anchors, so their replacement coordinates are kept
    explicit and stable rather than being selected from whichever buildings
    happen to be present in a generated file.  Every destination is in the
    original state and uses an existing terrain anchor where possible.
    """
    # (state, landmark_x, landmark_z, radius, destination_x, destination_y,
    # destination_z).  Destinations are in the same state and deliberately
    # use already-authored land anchors from that state where possible.
    zones = (
        (41, 3782.49, 969.30, 8.0, "3791.00", "11.00", "969.00"),
        (66, 3480.06, 946.54, 5.0, "3482.00", "13.80", "942.00"),
        (49, 3487.83, 934.76, 10.0, "3473.00", "17.55", "970.00"),
        (215, 3595.70, 767.51, 10.0, "3556.00", "10.95", "718.00"),
        (51, 3492.22, 976.80, 10.0, "3374.00", "14.38", "934.00"),
        (28, 3745.84, 940.78, 8.0, "3743.00", "10.30", "931.00"),
        (125, 3530.00, 904.52, 12.0, "3501.00", "12.00", "877.00"),
        (125, 3545.96, 903.63, 12.0, "3501.00", "12.00", "877.00"),
        (125, 3536.24, 906.55, 12.0, "3503.00", "12.03", "890.00"),
        (48, 3718.20, 913.50, 8.0, "3730.00", "10.25", "911.00"),
        (699, 3977.10, 934.50, 10.0, "3970.00", "12.57", "926.00"),
    )
    result = []
    for line in lines:
        fields = line.split(";")
        if len(fields) == 7 and fields[0].isdigit():
            state_id = int(fields[0])
            if fields[1] not in SEA_POSITIONED_TYPES | PORT_ANCHOR_TYPES:
                x, z = float(fields[2]), float(fields[4])
                for zone_state, landmark_x, landmark_z, radius, dx, dy, dz in zones:
                    if zone_state == state_id and (
                        (x - landmark_x) ** 2 + (z - landmark_z) ** 2
                    ) <= radius**2:
                        fields[2:5] = [dx, dy, dz]
                        line = ";".join(fields)
                        break
        result.append(line)
    return result


def ensure_nam_split_spawn_positions(root: Path = ROOT) -> int:
    """Restore construction anchors across the split resource-war theatre."""
    path = root / "map" / "buildings.txt"
    lines = path.read_text(encoding="utf-8-sig", errors="strict").splitlines()
    counts: dict[tuple[int, str], int] = {}
    for line in lines:
        fields = line.split(";")
        if len(fields) == 7 and fields[0].isdigit():
            key = (int(fields[0]), fields[1])
            counts[key] = counts.get(key, 0) + 1

    added = 0
    state_by_province = load_state_by_province(root)
    positions = load_unitstack_positions(root)
    provinces_by_state: dict[int, list[int]] = {}
    for province_id, state_id in state_by_province.items():
        if state_id in NAM_RESOURCE_WAR_SPAWN_STATES and province_id in positions:
            provinces_by_state.setdefault(state_id, []).append(province_id)

    for state_id in sorted(NAM_RESOURCE_WAR_SPAWN_STATES):
        candidates = sorted(provinces_by_state.get(state_id, ()))
        if not candidates:
            raise RuntimeError(
                f"state {state_id} has no unitstack position for spawn repair"
            )
        cursor = 0
        for building_type, minimum in required_spawns(state_id).items():
            key = (state_id, building_type)
            while counts.get(key, 0) < minimum:
                province_id = candidates[cursor % len(candidates)]
                cursor += 1
                x, height, z = positions[province_id]
                rotation = ((state_id * 37 + cursor * 53) % 628) / 100.0
                line = f"{state_id};{building_type};{x};{height};{z};{rotation:.2f};0"
                if line not in lines:
                    lines.append(line)
                    added += 1
                counts[key] = counts.get(key, 0) + 1

    if added:
        path.write_bytes("\r\n".join(lines).encode("utf-8"))
    return added


def load_unitstack_positions(root: Path = ROOT) -> dict[int, tuple[str, str, str]]:
    positions: dict[int, tuple[str, str, str]] = {}
    for line in (
        (root / "map" / "unitstacks.txt")
        .read_text(encoding="utf-8-sig", errors="strict")
        .splitlines()
    ):
        fields = line.split(";")
        if len(fields) >= 5 and fields[0].isdigit() and fields[1] == "0":
            positions.setdefault(int(fields[0]), (fields[2], fields[3], fields[4]))
    return positions


def ensure_exclusion_boundary_spawn_positions(root: Path = ROOT) -> int:
    """Restore construction anchors left behind by the EXZ realignment."""
    return ensure_state_spawn_positions(root, EXCLUSION_BOUNDARY_SPAWN_STATES)


def ensure_state_spawn_positions(root: Path, state_ids: set[int]) -> int:
    """Complete native construction anchors after a province repartition."""
    path = root / "map" / "buildings.txt"
    lines = path.read_text(encoding="utf-8-sig", errors="strict").splitlines()
    state_by_province = load_state_by_province(root)
    positions = load_unitstack_positions(root)
    provinces_by_state: dict[int, list[int]] = {}
    province_by_color = load_province_by_color(root)
    with Image.open(root / "map/provinces.bmp") as source:
        image = source.convert("RGB")
        for province_id, (x, height, z) in list(positions.items()):
            px = _pixel_coordinate(x, image.width)
            pz = _pixel_coordinate(z, image.height)
            actual = province_by_color.get(image.getpixel((px, image.height - 1 - pz)))
            state_id = state_by_province.get(actual)
            if state_id in state_ids:
                # Integer anchors agree under native truncation and rounding.
                positions[province_id] = (f"{px:.2f}", height, f"{pz:.2f}")
                provinces_by_state.setdefault(state_id, []).append(province_id)
    counts: dict[tuple[int, str], int] = {}
    for line in lines:
        fields = line.split(";")
        if len(fields) == 7 and fields[0].isdigit():
            key = (int(fields[0]), fields[1])
            counts[key] = counts.get(key, 0) + 1

    added = 0
    for state_id in sorted(state_ids):
        candidates = sorted(provinces_by_state.get(state_id, ()))
        if not candidates:
            raise RuntimeError(
                f"state {state_id} has no unitstack position for spawn repair"
            )
        cursor = 0
        for building_type, minimum in required_spawns(state_id).items():
            key = (state_id, building_type)
            while counts.get(key, 0) < minimum:
                province_id = candidates[cursor % len(candidates)]
                cursor += 1
                x, height, z = positions[province_id]
                rotation = ((state_id * 37 + cursor * 53) % 628) / 100.0
                line = f"{state_id};{building_type};{x};{height};{z};{rotation:.2f};0"
                if line not in lines:
                    lines.append(line)
                    added += 1
                    counts[key] = counts.get(key, 0) + 1

    if added:
        path.write_bytes("\r\n".join(lines).encode("utf-8"))
    return added


def required_spawn_issues(lines: list[str], state_ids: set[int]) -> list[str]:
    counts: dict[tuple[int, str], int] = {}
    for line in lines:
        fields = line.split(";")
        if len(fields) != 7 or not fields[0].isdigit():
            continue
        key = (int(fields[0]), fields[1])
        counts[key] = counts.get(key, 0) + 1

    issues: list[str] = []
    for state_id in sorted(state_ids):
        for building_type, minimum in required_spawns(state_id).items():
            actual = counts.get((state_id, building_type), 0)
            if actual < minimum:
                issues.append(
                    f"map/buildings.txt: state {state_id} has {actual} {building_type} "
                    f"spawn positions; expected at least {minimum}"
                )
    return issues


def coastal_port_plan(root: Path = ROOT) -> tuple[list[str], list[int]]:
    """Give coastal split provinces the native port anchors required by the map.

    These anchors permit navigation and construction; they do not grant a
    built naval base or alter the state's starting economy.
    """
    lines = (root / "map/buildings.txt").read_text(encoding="utf-8-sig").splitlines()
    state_by_province = load_state_by_province(root)
    colors = load_province_by_color(root)
    sea_ids = set()
    coastal_ids = set()
    for line in (
        (root / "map/definition.csv").read_text(encoding="utf-8-sig").splitlines()
    ):
        fields = line.split(";")
        if len(fields) >= 5 and fields[4] == "sea":
            sea_ids.add(int(fields[0]))
        if len(fields) >= 6 and fields[4] == "land" and fields[5] == "true":
            coastal_ids.add(int(fields[0]))
    present = set()
    with (
        Image.open(root / "map/provinces.bmp") as provinces,
        Image.open(root / "map/heightmap.bmp") as heights,
    ):
        pixels = provinces.load()
        for line in lines:
            fields = line.split(";")
            if len(fields) == 7 and fields[1] == "naval_base_spawn":
                x = _pixel_coordinate(fields[2], provinces.width)
                y = (
                    provinces.height
                    - 1
                    - _pixel_coordinate(fields[4], provinces.height)
                )
                present.add(colors.get(pixels[x, y]))
        missing = sorted((COASTAL_ADDITION_PROVINCES & coastal_ids) - present)
        if not missing:
            return lines, []
        positions = load_unitstack_positions(root)
        candidates = {province: [] for province in missing}
        shorelines = {province: [] for province in missing}
        interior = {province: [] for province in missing}
        for y in range(1, provinces.height - 1):
            for x in range(1, provinces.width - 1):
                province = colors.get(pixels[x, y])
                if province not in candidates:
                    continue
                # Keep the anchor inside land on both sides of the native
                # integer-coordinate boundary used when resolving map objects.
                stable = pixels[x, y + 1] == pixels[x, y]
                if stable:
                    interior[province].append((x, y))
                for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                    sea = colors.get(pixels[x + dx, y + dy])
                    if sea in sea_ids:
                        center_x, _height, center_z = map(float, positions[province])
                        distance = (x - center_x) ** 2 + (
                            provinces.height - 1 - y - center_z
                        ) ** 2
                        shorelines[province].append((distance, x, y, sea, dx, dy))
                        if stable:
                            candidates[province].append((distance, x, y, sea, dx, dy))
        for province in missing:
            if not candidates[province]:
                if not shorelines[province] or not interior[province]:
                    raise RuntimeError(
                        f"coastal province {province}: no safe land anchor beside its sea boundary"
                    )
                _distance, shore_x, shore_y, sea, dx, dy = min(shorelines[province])
                x, y = min(
                    interior[province],
                    key=lambda point: (point[0] - shore_x) ** 2
                    + (point[1] - shore_y) ** 2,
                )
                candidates[province].append((0, x, y, sea, dx, dy))
            _distance, x, y, sea, dx, dy = min(candidates[province])
            state = state_by_province[province]
            elevation = heights.getpixel((x, y)) / 10
            rotation = atan2(dx, -dy)
            lines.append(
                f"{state};naval_base_spawn;{x:.2f};{elevation:.2f};"
                f"{provinces.height - 1 - y:.2f};{rotation:.2f};{sea}"
            )
    return lines, missing


def validate(root: Path = ROOT) -> list[str]:
    buildings_path = root / "map" / "buildings.txt"
    try:
        if buildings_path.read_bytes().endswith((b"\r", b"\n")):
            return [
                "map/buildings.txt has a terminal empty row; HOI4 reports it as "
                "an invalid argument count"
            ]
        lines, mismatches = audit_buildings(root)
        state_ids = set(load_state_by_province(root).values())
    except (OSError, RuntimeError, ValueError) as exc:
        return [str(exc)]
    issues = [
        (
            f"map/buildings.txt:{item.line}: {item.building_type} belongs to state "
            f"{item.actual_state} via province {item.province}, not state {item.recorded_state}"
        )
        for item in mismatches
    ]
    issues.extend(required_spawn_issues(lines, state_ids))
    if interior_dam_anchor(lines) != lines:
        issues.append("state 53 dam_spawn must use its interior integer anchor")
    if bezhaysk_castle_clearance(lines) != lines:
        issues.append("state 41 building visuals overlap the Grayson castle footprint")
    if khan_bunker_clearance(lines) != lines:
        issues.append("state 66 generic fort overlaps the Khan bunker footprint")
    if permanent_landmark_clearance(lines) != lines:
        issues.append("vanilla building visuals overlap a permanent landmark footprint")
    _planned_heights, height_changes = mountain_building_heights(root, lines)
    issues.extend(
        f"map/buildings.txt:{line}: building height differs from the mountain surface"
        for line in height_changes
    )
    try:
        _planned, missing_ports = coastal_port_plan(root)
        issues.extend(
            f"coastal province {province} has no naval_base_spawn"
            for province in missing_ports
        )
    except (OSError, RuntimeError, ValueError) as exc:
        issues.append(str(exc))
    return issues


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_mutually_exclusive_group()
    actions.add_argument(
        "--check",
        action="store_true",
        help="validate current generated output (default)",
    )
    actions.add_argument(
        "--apply", action="store_true", help="rewrite mismatched state ids"
    )
    args = parser.parse_args()

    if args.apply:
        mismatches = synchronize_buildings(ROOT, apply=True)
        added = ensure_exclusion_boundary_spawn_positions(ROOT)
        western_manifest = json.loads(
            (ROOT / "tools/data/adiscord_western_states.json").read_text(encoding="utf-8")
        )
        western_ids = set(map(int, western_manifest["states"])) | set(
            map(int, western_manifest.get("donors", {}))
        )
        western_added = ensure_state_spawn_positions(ROOT, western_ids)
        port_lines, missing_ports = coastal_port_plan(ROOT)
        if missing_ports:
            BUILDINGS_PATH.write_bytes("\r\n".join(port_lines).encode("utf-8"))
        print(f"Corrected {len(mismatches)} map-building state mismatches.")
        print(f"Added {added} Exclusion Zone boundary spawn anchors.")
        print(f"Added {western_added} western boundary spawn anchors.")
        print(f"Added {len(missing_ports)} coastal port anchors.")
    issues = validate()
    if issues:
        for issue in issues:
            print(f"ERROR: {issue}")
        return 1
    print("Map-building validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
