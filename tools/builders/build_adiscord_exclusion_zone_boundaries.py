#!/usr/bin/env python3
"""Align the Exclusion Zone's state borders with contaminated terrain.

The source snapshot preserves the pre-realignment province allocation.  The
planner removes exposed ordinary terrain from EXZ, while keeping contaminated
land, mountain massifs, established cities, and compact enclosed foothills.
No artificial access corridor, province colour, state id, or western-continent
state is changed.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter, deque
from pathlib import Path

from tools.builders.build_adiscord_northern_countries import format_provinces, load_definition
from tools.builders.build_adiscord_strategic_regions import (
    connected_components,
    load_province_adjacency,
    load_province_definitions,
)
from tools.lib.paths import repository_root


ROOT = repository_root()
STATE_DIR = ROOT / "history" / "states"
SOURCE_PATH = ROOT / "tools" / "data" / "adiscord_exclusion_zone_boundary_source.json"

# These are the only urban exceptions allowed to remain under EXZ.  Every one
# is an established victory-point state; unmarked urban terrain follows the
# ordinary fringe realignment.
CITY_EXCEPTION_STATES = {
    49, 170, 171, 178, 181, 184, 186, 189, 193, 203, 204, 211,
}

# Small non-mountain provinces enclosed by the northern and central mountain
# massifs stay with their original EXZ states.  Cutting access corridors through
# neighbouring countries for these pockets produces worse borders than leaving
# the compact geographic exception inside the wasteland.
GEOGRAPHIC_EXCEPTION_STATES = {51, 206, 329}

# Three former EXZ state ids survive as ordinary neighbouring territory.  The
# empty-state ids are intentionally reused so strategic-region references and
# saved state indexes remain stable.
NEW_OWNERS = {
    160: "WCG",
    218: "BTL",
    223: "WCG",
    156: "WCG",
}
SUCCESSOR_CORES = {
    156: "KRM",
    160: "LMN",
    223: "LMN",
}

def state_path(state_id: int) -> Path:
    matches = sorted(STATE_DIR.glob(f"{state_id}-*.txt"))
    if len(matches) != 1:
        raise RuntimeError(f"state {state_id}: expected one history file, found {len(matches)}")
    return matches[0]


def load_source() -> dict[int, set[int]]:
    payload = json.loads(SOURCE_PATH.read_text(encoding="utf-8"))
    if payload.get("schema") != 1:
        raise RuntimeError("unsupported Exclusion Zone boundary source schema")
    return {int(state_id): set(provinces) for state_id, provinces in payload["states"].items()}


def load_current_owners() -> dict[int, str]:
    owners: dict[int, str] = {}
    for path in STATE_DIR.glob("*.txt"):
        source = path.read_text(encoding="utf-8-sig", errors="strict")
        state_match = re.search(r"(?m)^\s*id\s*=\s*(\d+)", source)
        owner_match = re.search(r"(?m)^\s*owner\s*=\s*([A-Z0-9]{3})", source)
        if state_match and owner_match:
            owners[int(state_match.group(1))] = owner_match.group(1)
    return owners


def load_current_province_states() -> dict[int, int]:
    province_to_state: dict[int, int] = {}
    for path in STATE_DIR.glob("*.txt"):
        source = path.read_text(encoding="utf-8-sig", errors="strict")
        state_match = re.search(r"(?m)^\s*id\s*=\s*(\d+)", source)
        province_match = re.search(r"\bprovinces\s*=\s*\{([^}]*)\}", source, re.DOTALL)
        if not state_match or not province_match:
            continue
        state_id = int(state_match.group(1))
        for province_id in map(int, re.findall(r"\d+", province_match.group(1))):
            province_to_state[province_id] = state_id
    return province_to_state


def seeded_partition(
    component: set[int],
    target_predicates: tuple[tuple[int, object], ...],
    province_to_state: dict[int, int],
    owners: dict[int, str],
    adjacency: dict[int, set[int]],
) -> dict[int, set[int]]:
    """Split a connected fringe between external-border seeds."""
    seeds: dict[int, set[int]] = {target: set() for target, _predicate in target_predicates}
    for province_id in component:
        for neighbour in adjacency[province_id]:
            if neighbour in component:
                continue
            neighbour_state = province_to_state.get(neighbour)
            if neighbour_state is None:
                continue
            for target, predicate in target_predicates:
                if predicate(neighbour_state, owners.get(neighbour_state, "")):
                    seeds[target].add(province_id)

    assignment: dict[int, int] = {}
    queue: deque[int] = deque()
    for target in sorted(seeds):
        if not seeds[target]:
            raise RuntimeError(f"target state {target} has no border seed")
        for province_id in sorted(seeds[target]):
            if province_id not in assignment or target < assignment[province_id]:
                assignment[province_id] = target
    queue.extend(sorted(assignment))
    while queue:
        province_id = queue.popleft()
        target = assignment[province_id]
        for neighbour in sorted(adjacency[province_id]):
            if neighbour in component and neighbour not in assignment:
                assignment[neighbour] = target
                queue.append(neighbour)
    if set(assignment) != component:
        raise RuntimeError("seeded boundary partition left provinces unassigned")
    return {
        target: {province_id for province_id, assigned in assignment.items() if assigned == target}
        for target in seeds
    }


def plan_boundaries() -> tuple[dict[int, set[int]], set[int], dict[int, str]]:
    source = load_source()
    owners = load_current_owners()
    original_exz = {state_id for state_id in source if state_id not in {156, 179}}
    province_to_state = load_current_province_states()
    # Internal provenance must always come from the immutable source snapshot;
    # current state borders are the output and must not influence a rerun.
    for state_id, provinces in source.items():
        for province_id in provinces:
            province_to_state[province_id] = state_id
    _colors, details = load_definition()
    province_types, color_to_province = load_province_definitions()
    adjacency = load_province_adjacency(
        province_types, color_to_province, include_special_adjacencies=False
    )

    planned = {state_id: set() for state_id in source}
    protected: set[int] = set()
    for state_id in original_exz:
        for province_id in source[state_id]:
            terrain = details[province_id]["terrain"]
            if terrain in {"contaminated", "mountain"} or (
                terrain == "urban" and state_id in CITY_EXCEPTION_STATES
            ):
                planned[state_id].add(province_id)
                protected.add(province_id)

    # Removing ordinary terrain cuts off tiny contaminated pieces in three
    # states.  Attach them to an adjacent EXZ state rather than leaving a
    # physically disconnected state.
    for source_state, target_state in ((51, 49), (330, 191)):
        components = sorted(
            connected_components(planned[source_state], adjacency),
            key=lambda component: (-len(component), min(component)),
        )
        for component in components[1:]:
            planned[source_state].difference_update(component)
            planned[target_state].update(component)

    ordinary = set().union(*(source[state_id] for state_id in original_exz)) - protected
    for component in connected_components(ordinary, adjacency):
        source_states = {province_to_state[province_id] for province_id in component}
        if 223 in source_states:
            partitions = seeded_partition(
                component,
                (
                    (218, lambda _state, owner: owner == "BTL"),
                    (223, lambda state, _owner: state in {157, 158, 159}),
                ),
                province_to_state,
                owners,
                adjacency,
            )
            planned[218].update(partitions[218])
            planned[223].update(partitions[223])
        elif 330 in source_states:
            planned[179].update(component)
        elif 160 in source_states:
            planned[160].update(component)
        elif 206 in source_states:
            planned[206].update(component)
        elif source_states <= {51, 329}:
            for province_id in component:
                planned[province_to_state[province_id]].add(province_id)
        elif 155 in source_states:
            planned[156].update(component)
        else:
            raise RuntimeError(f"unclassified ordinary-terrain component: {sorted(source_states)}")

    # State 156 and the Relay Enclave predate the realignment and keep their
    # original provinces in addition to their assigned fringe land.
    planned[156].update(source[156])
    planned[179].update(source[179])
    final_owners = {state_id: "EXZ" for state_id in original_exz}
    final_owners.update(NEW_OWNERS)

    expected_union = set().union(*source.values())
    actual_union = set().union(*planned.values())
    if expected_union != actual_union:
        raise RuntimeError(
            f"boundary plan changed province coverage: missing={sorted(expected_union-actual_union)}, "
            f"unexpected={sorted(actual_union-expected_union)}"
        )
    counts = Counter(province_id for provinces in planned.values() for province_id in provinces)
    duplicates = sorted(province_id for province_id, count in counts.items() if count != 1)
    if duplicates:
        raise RuntimeError(f"boundary plan duplicates provinces: {duplicates}")
    for state_id, provinces in planned.items():
        components = connected_components(provinces, adjacency)
        if len(components) != 1:
            raise RuntimeError(
                f"state {state_id} is disconnected after realignment: "
                f"{[len(component) for component in components]}"
            )
        if final_owners.get(state_id) == "EXZ":
            terrains = {details[province_id]["terrain"] for province_id in provinces}
            allowed = {"contaminated", "mountain"}
            if state_id in CITY_EXCEPTION_STATES:
                allowed.add("urban")
            if state_id in GEOGRAPHIC_EXCEPTION_STATES:
                allowed.update({"hills", "urban"})
            if not terrains <= allowed:
                raise RuntimeError(f"EXZ state {state_id} retains forbidden terrain: {sorted(terrains-allowed)}")
    return planned, original_exz, final_owners


def replace_owner_and_cores(source: str, state_id: int, owner: str) -> str:
    source = re.sub(
        r"(?m)^([ \t]*)owner\s*=\s*[A-Z0-9]{3}[ \t]*$",
        lambda match: f"{match.group(1)}owner = {owner}",
        source,
        count=1,
    )
    core_lines = [f"add_core_of = {owner}"]
    successor = SUCCESSOR_CORES.get(state_id)
    if successor:
        core_lines.append(f"add_core_of = {successor}")
    def render_cores(match: re.Match[str]) -> str:
        indentation = match.group("indent")
        return "\n".join(f"{indentation}{line}" for line in core_lines)

    source, count = re.subn(
        r"(?m)^(?P<indent>[ \t]*)add_core_of\s*=\s*[A-Z0-9]{3}[ \t]*$"
        r"(?:\n(?P=indent)add_core_of\s*=\s*[A-Z0-9]{3}[ \t]*$)*",
        render_cores,
        source,
        count=1,
    )
    if count != 1:
        raise RuntimeError(f"state {state_id}: expected one starting core line")
    return source


def render_state(state_id: int, provinces: set[int], owner: str) -> str:
    path = state_path(state_id)
    source = path.read_text(encoding="utf-8-sig", errors="strict")
    source, count = re.subn(
        r"(?s)(\bprovinces\s*=\s*\{)[^}]*(\})",
        lambda match: f"{match.group(1)}\n{format_provinces(provinces)}\n\t{match.group(2)}",
        source,
        count=1,
    )
    if count != 1:
        raise RuntimeError(f"state {state_id}: expected one province block")
    current_owner = re.search(r"(?m)^\s*owner\s*=\s*([A-Z0-9]{3})", source)
    if not current_owner:
        raise RuntimeError(f"state {state_id}: missing starting owner")
    if current_owner.group(1) != owner or state_id in SUCCESSOR_CORES:
        source = replace_owner_and_cores(source, state_id, owner)
    return source if source.endswith("\n") else source + "\n"


def apply() -> None:
    planned, _original_exz, final_owners = plan_boundaries()
    current_owners = load_current_owners()
    for state_id, provinces in sorted(planned.items()):
        path = state_path(state_id)
        path.write_text(
            render_state(state_id, provinces, final_owners.get(state_id, current_owners[state_id])),
            encoding="utf-8",
            newline="\n",
        )
    print(f"Realigned {len(planned)} states around the Exclusion Zone.")


def print_summary() -> None:
    planned, original_exz, final_owners = plan_boundaries()
    retained = sorted(state_id for state_id in original_exz if final_owners[state_id] == "EXZ")
    reassigned = sorted(state_id for state_id in original_exz if final_owners[state_id] != "EXZ")
    print(f"EXZ retained states: {len(retained)}")
    print(f"Reassigned former EXZ states: {', '.join(f'{state}:{final_owners[state]}' for state in reassigned)}")
    print(f"Affected province allocation: {sum(len(provinces) for provinces in planned.values())} provinces")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="write the planned state boundaries and owners")
    args = parser.parse_args()
    print_summary()
    if args.apply:
        apply()
    else:
        print("Dry run only; pass --apply to write state history files.")


if __name__ == "__main__":
    main()
