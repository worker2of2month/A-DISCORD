#!/usr/bin/env python3
"""Own the bounded rail and supply layer for the Vorkerland civil-war theatre."""

from __future__ import annotations

import argparse
from pathlib import Path

from tools.builders import build_adiscord_strategic_regions as map_regions
from tools.lib.paths import repository_root


ROOT = repository_root()
RAILWAYS_PATH = ROOT / "map" / "railways.txt"
SUPPLY_NODES_PATH = ROOT / "map" / "supply_nodes.txt"
OSV_CAPITAL_STATE = 318
OSV_CAPITAL_RAIL = (1, (16642, 1540, 1818))
VORKERLAND_SUPPLY_HUB_STATES = {
    2539: 107,
    16643: 306,
    4148: 316,
    16642: 318,
}
RETIRED_MARKERS = (
    "# BEGIN GENERATED: ADISCORD VORKERLAND THEATRE RAILS",
    "# END GENERATED: ADISCORD VORKERLAND THEATRE RAILS",
)


def render_managed_line() -> str:
    level, provinces = OSV_CAPITAL_RAIL
    route = " ".join(map(str, provinces))
    return f"{level} {len(provinces)} {route}"


def update_source(source: str) -> str:
    """Append one exact owned rail record while preserving all other lines."""
    lines = [
        line
        for line in source.replace("\r\n", "\n").splitlines()
        if line not in RETIRED_MARKERS
    ]
    managed = render_managed_line()
    lines = [line for line in lines if line != managed]
    lines.append(managed)
    return "\n".join(lines) + "\n"


def render_supply_node(province_id: int) -> str:
    return f"1 {province_id}"


def update_supply_source(source: str) -> str:
    """Append exact generated hubs while preserving every unmanaged record."""
    lines = source.replace("\r\n", "\n").splitlines()
    managed = {
        render_supply_node(province_id)
        for province_id in VORKERLAND_SUPPLY_HUB_STATES
    }
    lines = [line for line in lines if line.strip() not in managed]
    lines.extend(
        render_supply_node(province_id)
        for province_id in sorted(VORKERLAND_SUPPLY_HUB_STATES)
    )
    return "\n".join(lines) + "\n"


def validate() -> list[str]:
    issues: list[str] = []
    raw = RAILWAYS_PATH.read_bytes()
    source = raw.decode("utf-8-sig").replace("\r\n", "\n")
    level, provinces = OSV_CAPITAL_RAIL
    expected_line = render_managed_line()
    if source.splitlines().count(expected_line) != 1:
        issues.append("OSV capital rail must occur exactly once")
    for marker in RETIRED_MARKERS:
        if marker in source:
            issues.append("map/railways.txt must remain numeric-only")

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
            if province_types.get(first) != "land" or province_types.get(second) != "land":
                issues.append(f"OSV rail segment {first}-{second} is not entirely on land")
            if second not in physical.get(first, set()):
                issues.append(f"OSV rail segment {first}-{second} is not physically adjacent")
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
                issues.append(f"Vorkerland supply hub {province_id} is not on a railway")
    except (OSError, RuntimeError, ValueError, KeyError) as error:
        issues.append(f"cannot validate OSV capital rail geography: {error}")
    return issues


def apply() -> None:
    raw = RAILWAYS_PATH.read_bytes()
    newline = "\r\n" if b"\r\n" in raw else "\n"
    source = raw.decode("utf-8-sig")
    updated = update_source(source).replace("\n", newline)
    RAILWAYS_PATH.write_bytes(updated.encode("utf-8"))

    supply_raw = SUPPLY_NODES_PATH.read_bytes()
    supply_newline = "\r\n" if b"\r\n" in supply_raw else "\n"
    supply_source = supply_raw.decode("utf-8-sig")
    updated_supply = update_supply_source(supply_source).replace("\n", supply_newline)
    SUPPLY_NODES_PATH.write_bytes(updated_supply.encode("utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate the bounded central Vorkerland theatre rail layer."
    )
    actions = parser.add_mutually_exclusive_group()
    actions.add_argument(
        "--check", action="store_true", help="validate current generated output (default)"
    )
    actions.add_argument("--apply", action="store_true", help="write the generated rail block")
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
        "Vorkerland theatre validation passed: OSV spur and four rail supply hubs are owned."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
