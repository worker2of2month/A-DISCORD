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


ROOT = Path(__file__).resolve().parents[1]
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


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="rewrite mismatched state ids")
    args = parser.parse_args()

    mismatches = synchronize_buildings(ROOT, apply=args.apply)
    action = "Corrected" if args.apply else "Found"
    print(f"{action} {len(mismatches)} map-building state mismatches.")
    for item in mismatches[:20]:
        print(
            f"- line {item.line}: {item.building_type} {item.recorded_state} -> "
            f"{item.actual_state} (province {item.province})"
        )
    if mismatches and not args.apply:
        print("Dry run only; pass --apply to update map/buildings.txt.")


if __name__ == "__main__":
    main()
