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

# The deliberate resource-war split assigns the original state positions to
# their physical provinces. Every resulting state still needs the complete set
# of 1.19 spawn anchors even when a building is not present at game start.
NAM_RESOURCE_WAR_SPAWN_STATES = {67, 68, 69, 70, 688, 689, 690, 691, 692}
NAM_SPLIT_SPAWN_POSITION_CANDIDATES = {
    (67, "air_base"): (
        "67;air_base;3701.00;10.25;548.00;0.66;0",
    ),
    (67, "anti_air_building"): (
        "67;anti_air_building;3701.00;10.25;548.00;0.66;0",
        "67;anti_air_building;3690.00;10.80;575.00;4.36;0",
    ),
    (67, "stronghold_network"): (
        "67;stronghold_network;3724.00;10.60;605.00;5.21;0",
    ),
    (67, "synthetic_refinery"): (
        "67;synthetic_refinery;3700.00;10.80;583.00;4.75;0",
    ),
    (688, "anti_air_building"): (
        "688;anti_air_building;3599.00;10.35;600.00;2.76;0",
    ),
    (688, "fuel_silo"): (
        "688;fuel_silo;3609.00;10.53;605.00;2.82;0",
    ),
    (688, "nuclear_reactor_spawn"): (
        "688;nuclear_reactor_spawn;3611.00;10.65;605.00;6.27;0",
    ),
    (688, "radar_station"): (
        "688;radar_station;3641.00;10.60;593.00;1.25;0",
    ),
    (688, "rocket_site_spawn"): (
        "688;rocket_site_spawn;3638.00;11.00;614.00;5.94;0",
    ),
    (688, "stronghold_network"): (
        "688;stronghold_network;3616.00;10.50;594.00;4.14;0",
    ),
    (689, "air_base"): (
        "689;air_base;3666.00;10.65;540.00;2.65;0",
    ),
    (689, "anti_air_building"): (
        "689;anti_air_building;3665.00;10.80;545.00;0.57;0",
        "689;anti_air_building;3699.00;10.50;527.00;5.76;0",
        "689;anti_air_building;3675.00;10.30;535.00;4.14;0",
    ),
    (689, "fuel_silo"): (
        "689;fuel_silo;3689.00;11.00;551.00;4.33;0",
    ),
    (689, "nuclear_reactor_spawn"): (
        "689;nuclear_reactor_spawn;3669.00;10.65;543.00;3.55;0",
    ),
    (689, "radar_station"): (
        "689;radar_station;3653.00;10.45;555.00;2.77;0",
    ),
    (689, "rocket_site_spawn"): (
        "689;rocket_site_spawn;3696.00;10.30;527.00;0.15;0",
    ),
    (689, "synthetic_refinery"): (
        "689;synthetic_refinery;3683.00;10.60;540.00;2.69;0",
    ),
}

# States created by reviewed province repartitions. Existing building
# coordinates follow the moved provinces; every resulting state still needs
# one complete set of HOI4 1.19 construction anchors of its own.
EXCLUSION_BOUNDARY_SPAWN_STATES = {
    49, 51, 153, 154, 155, 165, 166, 169, 173, 180, 184, 185, 187,
    189, 193, 210, 211, 213, 214, 215, 222, 223, 224, 329, 330,
    160, 454, 455, 460, 461, 472,
    25, 128, 693, 694, 695, 696, 697, 698,
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
    with (root / "map" / "definition.csv").open(encoding="utf-8-sig", newline="") as source:
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
                raise RuntimeError(f"map/buildings.txt:{line_number}: malformed building row")
            building_type = fields[1]
            if building_type in SEA_POSITIONED_TYPES:
                continue
            x = _pixel_coordinate(fields[2], image.width)
            z = _pixel_coordinate(fields[4], image.height)
            province = province_by_color.get(image.getpixel((x, image.height - 1 - z)))
            actual_state = state_by_province.get(province) if province is not None else None
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


def synchronize_buildings(root: Path = ROOT, *, apply: bool = False) -> list[BuildingMismatch]:
    lines, mismatches = audit_buildings(root)
    if apply:
        for mismatch in mismatches:
            fields = lines[mismatch.line - 1].split(";")
            fields[0] = str(mismatch.actual_state)
            lines[mismatch.line - 1] = ";".join(fields)
        # Nudge writes this file with CRLF and no final newline. The engine
        # treats a terminal empty row as a malformed building definition, so
        # preserve both details when regenerating the file.
        payload = "\r\n".join(lines).encode("utf-8")
        (root / "map" / "buildings.txt").write_bytes(payload)
    return mismatches


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
            raise RuntimeError(f"state {state_id} has no unitstack position for spawn repair")
        cursor = 0
        for building_type, minimum in REQUIRED_STATE_SPAWN_COUNTS.items():
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
    for line in (root / "map" / "unitstacks.txt").read_text(
        encoding="utf-8-sig", errors="strict"
    ).splitlines():
        fields = line.split(";")
        if len(fields) >= 5 and fields[0].isdigit() and fields[1] == "0":
            positions.setdefault(int(fields[0]), (fields[2], fields[3], fields[4]))
    return positions


def ensure_exclusion_boundary_spawn_positions(root: Path = ROOT) -> int:
    """Restore construction anchors left behind by the EXZ realignment."""
    path = root / "map" / "buildings.txt"
    lines = path.read_text(encoding="utf-8-sig", errors="strict").splitlines()
    state_by_province = load_state_by_province(root)
    positions = load_unitstack_positions(root)
    provinces_by_state: dict[int, list[int]] = {}
    for province_id, state_id in state_by_province.items():
        if state_id in EXCLUSION_BOUNDARY_SPAWN_STATES and province_id in positions:
            provinces_by_state.setdefault(state_id, []).append(province_id)
    counts: dict[tuple[int, str], int] = {}
    for line in lines:
        fields = line.split(";")
        if len(fields) == 7 and fields[0].isdigit():
            key = (int(fields[0]), fields[1])
            counts[key] = counts.get(key, 0) + 1

    added = 0
    for state_id in sorted(EXCLUSION_BOUNDARY_SPAWN_STATES):
        candidates = sorted(provinces_by_state.get(state_id, ()))
        if not candidates:
            raise RuntimeError(f"state {state_id} has no unitstack position for spawn repair")
        cursor = 0
        for building_type, minimum in REQUIRED_STATE_SPAWN_COUNTS.items():
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
        for building_type, minimum in REQUIRED_STATE_SPAWN_COUNTS.items():
            actual = counts.get((state_id, building_type), 0)
            if actual < minimum:
                issues.append(
                    f"map/buildings.txt: state {state_id} has {actual} {building_type} "
                    f"spawn positions; HOI4 1.19 requires at least {minimum}"
                )
    return issues


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
    return issues


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_mutually_exclusive_group()
    actions.add_argument("--check", action="store_true", help="validate current generated output (default)")
    actions.add_argument("--apply", action="store_true", help="rewrite mismatched state ids")
    args = parser.parse_args()

    if args.apply:
        mismatches = synchronize_buildings(ROOT, apply=True)
        added = ensure_exclusion_boundary_spawn_positions(ROOT)
        print(f"Corrected {len(mismatches)} map-building state mismatches.")
        print(f"Added {added} Exclusion Zone boundary spawn anchors.")
    issues = validate()
    if issues:
        for issue in issues:
            print(f"ERROR: {issue}")
        return 1
    print("Map-building validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
