#!/usr/bin/env python3
"""Validate terrain-aligned Exclusion Zone states and their fringe owners."""

from __future__ import annotations

import re
import sys
from pathlib import Path

_REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
if str(_REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPOSITORY_ROOT))

try:
    from tools.builders.build_adiscord_exclusion_zone_boundaries import (
        CITY_EXCEPTION_STATES,
        CONTAMINATED_FRINGE_STATES,
        FOREST_EXCEPTION_STATES,
        GEOGRAPHIC_EXCEPTION_STATES,
        NEW_OWNERS,
        ROOT,
        SUCCESSOR_CORES,
        plan_boundaries,
        state_path,
    )
    from tools.builders.build_adiscord_northern_countries import load_definition
    from tools.lib.vorkerland_collapse_manifest import (
        CONTAMINATED_STATES,
        DIRTY_GROUPS,
        EXZ_REMAINDER_GROUPS,
    )
except ModuleNotFoundError:
    from builders.build_adiscord_exclusion_zone_boundaries import (
        CITY_EXCEPTION_STATES,
        CONTAMINATED_FRINGE_STATES,
        FOREST_EXCEPTION_STATES,
        GEOGRAPHIC_EXCEPTION_STATES,
        NEW_OWNERS,
        ROOT,
        SUCCESSOR_CORES,
        plan_boundaries,
        state_path,
    )
    from builders.build_adiscord_northern_countries import load_definition
    from lib.vorkerland_collapse_manifest import (
        CONTAMINATED_STATES,
        DIRTY_GROUPS,
        EXZ_REMAINDER_GROUPS,
    )


def validate() -> list[str]:
    issues: list[str] = []
    planned, original_exz, final_owners = plan_boundaries()
    _colors, details = load_definition()
    for state_id, expected_provinces in sorted(planned.items()):
        source = state_path(state_id).read_text(encoding="utf-8-sig", errors="strict")
        province_match = re.search(r"\bprovinces\s*=\s*\{([^}]*)\}", source, re.DOTALL)
        owner_match = re.search(r"(?m)^\s*owner\s*=\s*([A-Z0-9]{3})", source)
        if not province_match or not owner_match:
            issues.append(f"state {state_id} lacks provinces or starting owner")
            continue
        actual_provinces = {int(value) for value in re.findall(r"\d+", province_match.group(1))}
        if actual_provinces != expected_provinces:
            issues.append(f"state {state_id} is not synchronized with the boundary planner")
        expected_owner = final_owners.get(state_id, owner_match.group(1))
        if owner_match.group(1) != expected_owner:
            issues.append(f"state {state_id} owner expected {expected_owner}, found {owner_match.group(1)}")
        successor = SUCCESSOR_CORES.get(state_id)
        if successor and not re.search(rf"(?m)^\s*add_core_of\s*=\s*{successor}\s*$", source):
            issues.append(f"state {state_id} lacks successor core {successor}")
        if expected_owner == "EXZ":
            terrains = {details[province_id]["terrain"] for province_id in actual_provinces}
            allowed = {"contaminated", "mountain"}
            if state_id in CITY_EXCEPTION_STATES:
                allowed.add("urban")
            if state_id in GEOGRAPHIC_EXCEPTION_STATES:
                allowed.update({"hills", "urban"})
            if state_id in FOREST_EXCEPTION_STATES:
                allowed.add("forest")
            if not terrains <= allowed:
                issues.append(f"EXZ state {state_id} retains non-contaminated terrain {sorted(terrains-allowed)}")
            if (
                "urban" in terrains
                and state_id not in CITY_EXCEPTION_STATES
                and state_id not in GEOGRAPHIC_EXCEPTION_STATES
            ):
                issues.append(f"EXZ state {state_id} has an unapproved city exception")

    reassigned = {
        state_id
        for state_id, owner in NEW_OWNERS.items()
        if state_id != 156 and owner != "EXZ"
    }
    dirty_successors = set().union(*(set(states) for states in DIRTY_GROUPS.values()))
    dirty_remainders = set().union(*(set(states) for states in EXZ_REMAINDER_GROUPS.values()))
    for state_id in sorted(reassigned):
        if state_id in dirty_successors or state_id in dirty_remainders or state_id in CONTAMINATED_STATES:
            issues.append(f"reassigned state {state_id} remains in the dirty-zone collapse manifest")
    expected_retained = original_exz - reassigned
    actual_retained = {state_id for state_id in original_exz if final_owners[state_id] == "EXZ"}
    if actual_retained != expected_retained or len(actual_retained) != 56:
        issues.append("EXZ must retain exactly 56 compact terrain-aligned state ids")
    planned_exz = {state_id for state_id, owner in final_owners.items() if owner == "EXZ"}
    if len(planned_exz) != 57 or 461 not in planned_exz:
        issues.append("EXZ must contain its 56 terrain-aligned core states plus state 461")
    if set(planned) & set(range(474, 551)):
        issues.append("western-continent states entered the Exclusion Zone boundary plan")

    # Country ownership is the player-visible zone mask.  A state containing
    # even one contaminated province must therefore start under EXZ; this also
    # catches future generated fringe states omitted from the source snapshot.
    contaminated_states: set[int] = set()
    for path in (ROOT / "history" / "states").glob("*.txt"):
        source = path.read_text(encoding="utf-8-sig", errors="strict")
        state_match = re.search(r"(?m)^\s*id\s*=\s*(\d+)", source)
        province_match = re.search(r"\bprovinces\s*=\s*\{([^}]*)\}", source, re.DOTALL)
        owner_match = re.search(r"(?m)^\s*owner\s*=\s*([A-Z0-9]{3})", source)
        if not state_match or not province_match:
            continue
        state_id = int(state_match.group(1))
        provinces = {int(value) for value in re.findall(r"\d+", province_match.group(1))}
        if any(details[province_id]["terrain"] == "contaminated" for province_id in provinces):
            contaminated_states.add(state_id)
            owner = owner_match.group(1) if owner_match else ""
            if owner != "EXZ":
                issues.append(f"contaminated state {state_id} starts outside EXZ under {owner or 'no owner'}")
    if not CONTAMINATED_FRINGE_STATES <= set(planned):
        issues.append("contaminated fringe states are missing from the boundary source snapshot")
    if not contaminated_states:
        issues.append("no contaminated states were found")

    localisation_path = ROOT / "localisation" / "russian" / "ZZ_ADISCORD_exclusion_zone_l_russian.yml"
    localisation = localisation_path.read_text(encoding="utf-8-sig", errors="strict")
    for key in ("EXZ", "EXZ_pragmatism"):
        match = re.search(rf'(?m)^\s*{key}:\s*"([^"]*)"\s*$', localisation)
        if not match or match.group(1) != "":
            issues.append(f"{key} must remain deliberately blank")
    if (ROOT / "gfx" / "leaders" / "WRK CONTROL ZONE.png").exists():
        issues.append("the unscoped source portrait name still exists")
    return issues


def main() -> int:
    issues = validate()
    if issues:
        print(f"Exclusion Zone boundary validation failed with {len(issues)} issue(s):")
        for issue in issues:
            print(f"- {issue}")
        return 1
    print("Exclusion Zone boundary validation passed: 57 EXZ states, no contaminated state outside EXZ, and a blank EXZ map label.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
