#!/usr/bin/env python3
"""Own bounded campaign rail connections and Vorkerland supply hubs."""

from __future__ import annotations

import argparse
import re
from collections import defaultdict
from pathlib import Path

from tools.builders import build_adiscord_strategic_regions as map_regions
from tools.lib.paths import repository_root


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
# The western line must join the bunker without crossing a third country.
# Hubs become available to RUS only after it captures the border objectives.
KHAN_SUPPLY_RAIL = (1, (16531, 4870, 2298, 16544, 16546))
KHAN_SUPPLY_STATES = frozenset({66, 49, 176})
KHAN_SUPPLY_HUBS = (16531, 16639, 7445)
VORKERLAND_SUPPLY_HUB_STATES = {
    16639: 49,
    7445: 176,
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


def render_supply_connection(tag: str) -> str:
    level, provinces, _ = STARTING_SUPPLY_RAILS[tag]
    return f"{level} {len(provinces)} {' '.join(map(str, provinces))}"


def render_khan_connection() -> str:
    level, provinces = KHAN_SUPPLY_RAIL
    return f"{level} {len(provinces)} {' '.join(map(str, provinces))}"


def update_source(source: str) -> str:
    """Append exact owned rail records while preserving all other lines."""
    lines = [
        line
        for line in source.replace("\r\n", "\n").splitlines()
        if line not in RETIRED_MARKERS
    ]
    managed = [render_managed_line(), *(render_supply_connection(tag) for tag in STARTING_SUPPLY_RAILS), render_khan_connection()]
    lines = [line for line in lines if line not in managed]
    lines.extend(managed)
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
        for tag, (_, route, hubs) in STARTING_SUPPLY_RAILS.items():
            if source.splitlines().count(render_supply_connection(tag)) != 1:
                issues.append(f"{tag} supply connection must occur exactly once")
            for province in route:
                if province_types.get(province) != "land":
                    issues.append(f"{tag} supply connection leaves land at {province}")
                if state_owners.get(state_by_province.get(province)) != tag:
                    issues.append(f"{tag} supply connection leaves its starting territory at {province}")
            for first, second in zip(route, route[1:]):
                if second not in physical.get(first, set()):
                    issues.append(f"{tag} rail segment {first}-{second} is not physically adjacent")
            pending = [hubs[0]]
            reached = {hubs[0]}
            while pending:
                province = pending.pop()
                for neighbour in rail_graph[province]:
                    if neighbour not in reached and state_owners.get(state_by_province.get(neighbour)) == tag:
                        reached.add(neighbour)
                        pending.append(neighbour)
            if hubs[1] not in reached:
                issues.append(f"{tag} supply hubs {hubs[0]} and {hubs[1]} are disconnected inside its starting territory")
        if source.splitlines().count(render_khan_connection()) != 1:
            issues.append("RUS border supply connection must occur exactly once")
        for province in KHAN_SUPPLY_RAIL[1]:
            if province_types.get(province) != "land" or state_by_province.get(province) not in KHAN_SUPPLY_STATES:
                issues.append(f"RUS border supply connection leaves its campaign territory at {province}")
        for first, second in zip(KHAN_SUPPLY_RAIL[1], KHAN_SUPPLY_RAIL[1][1:]):
            if second not in physical.get(first, set()):
                issues.append(f"RUS rail segment {first}-{second} is not physically adjacent")
        pending = [KHAN_SUPPLY_HUBS[0]]
        reached = set(pending)
        while pending:
            province = pending.pop()
            for neighbour in rail_graph[province]:
                if neighbour not in reached and state_by_province.get(neighbour) in KHAN_SUPPLY_STATES:
                    reached.add(neighbour)
                    pending.append(neighbour)
        for hub in KHAN_SUPPLY_HUBS:
            if hub not in reached:
                issues.append(f"RUS border supply hub {hub} is disconnected from the capital within states 66/49/176")
            if supply_lines.count(render_supply_node(hub)) != 1:
                issues.append(f"RUS border supply hub {hub} must occur exactly once")
    except (OSError, RuntimeError, ValueError, KeyError) as error:
        issues.append(f"cannot validate campaign rail geography: {error}")
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
    updated_supply = update_supply_source(supply_source)
    if updated_supply != supply_source.replace("\r\n", "\n"):
        SUPPLY_NODES_PATH.write_bytes(updated_supply.replace("\n", supply_newline).encode("utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate bounded campaign rail connections and supply hubs."
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
        "Campaign rail validation passed: OSV spur, STP/YPR connections, RUS border network and managed supply hubs."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
