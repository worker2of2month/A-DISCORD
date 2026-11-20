#!/usr/bin/env python3
"""Validate the connected latitude-band shells replacing catch-all state 23."""

from __future__ import annotations

import re
import sys
from collections import Counter
from pathlib import Path

_REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
if str(_REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPOSITORY_ROOT))

from tools.lib.adiscord_remainder_countries import STATE_OWNERS, synchronize

try:
    from tools.builders.build_adiscord_outer_states import (
        build_province_data,
        check_western_outputs,
        parse_state,
        western_source,
    )
    from tools.builders.build_adiscord_remainder_states import (
        BASE_STATE_LOCALISATION,
        EXPECTED_PROVINCE_COUNT,
        FIRST_NEW_STATE_ID,
        GENERATED_MARKER,
        LATITUDE_EDGES,
        LOCALISATION,
        band_for_y,
    )
    from tools.builders.build_adiscord_new_states import NAM_ARCHIPELAGO_ISLANDS
    from tools.builders.build_adiscord_strategic_regions import (
        OUTER_CLIMATE_BELTS,
        OUTER_REGION_SPECS,
        connected_components,
        load_province_adjacency,
        load_province_definitions,
    )
except ModuleNotFoundError:
    from builders.build_adiscord_outer_states import (
        build_province_data,
        check_western_outputs,
        parse_state,
        western_source,
    )
    from builders.build_adiscord_remainder_states import (
        BASE_STATE_LOCALISATION,
        EXPECTED_PROVINCE_COUNT,
        FIRST_NEW_STATE_ID,
        GENERATED_MARKER,
        LATITUDE_EDGES,
        LOCALISATION,
        band_for_y,
    )
    from builders.build_adiscord_new_states import NAM_ARCHIPELAGO_ISLANDS
    from builders.build_adiscord_strategic_regions import (
        OUTER_CLIMATE_BELTS,
        OUTER_REGION_SPECS,
        connected_components,
        load_province_adjacency,
        load_province_definitions,
    )


ROOT = Path(__file__).resolve().parents[2]
STATE_DIR = ROOT / "history" / "states"
ADJACENCIES = ROOT / "map" / "adjacencies.csv"
ISLAND_BRIDGE_COMMENT = "nam archipelago island bridge"


def raised_islands() -> dict[int, list[tuple[frozenset[int], bool]]]:
    """Group the archipelago table by state as (provinces, bridged) rows."""
    islands: dict[int, list[tuple[frozenset[int], bool]]] = {}
    for island in NAM_ARCHIPELAGO_ISLANDS:
        provinces = frozenset(part["province"] for part in island["provinces"])
        islands.setdefault(island["state"], []).append((provinces, bool(island["bridge"])))
    return islands


def island_bridge_ends() -> set[int]:
    """Provinces named by an archipelago bridge row of adjacencies.csv."""
    ends: set[int] = set()
    for line in ADJACENCIES.read_text(encoding="utf-8-sig").splitlines():
        row = line.split(";")
        if len(row) > 9 and row[9].strip() == ISLAND_BRIDGE_COMMENT:
            ends.update(int(value) for value in row[:2] if value.strip().isdigit())
    return ends


def raised_island_issues(
    state_id: int,
    provinces: set[int],
    islands: list[tuple[frozenset[int], bool]],
    adjacency: dict[int, set[int]],
    bridge_ends: set[int],
) -> list[str]:
    """Check that each raised island is a separate component of its state.

    A bridged island needs its strait row; an unbridged one is reached by sea.
    """
    errors = []
    components = {frozenset(c) for c in connected_components(provinces, adjacency)}
    for island, bridged in islands:
        label = f"state {state_id}: raised island {sorted(island)}"
        if not island <= provinces:
            errors.append(f"{label} is missing from the state")
        elif island not in components:
            errors.append(f"{label} is not a separate land component")
        if bridged != bool(island & bridge_ends):
            errors.append(
                f"{label} {'lacks its' if bridged else 'has an unlisted'} bridge adjacency"
            )
    return errors


def load_localisation(path: Path, errors: list[str]) -> dict[int, str]:
    if not path.exists():
        errors.append(f"missing localisation {path.relative_to(ROOT)}")
        return {}
    if not path.read_bytes().startswith(b"\xef\xbb\xbf"):
        errors.append(f"{path.relative_to(ROOT)} must use UTF-8 BOM")
    text = path.read_text(encoding="utf-8-sig", errors="strict")
    return {
        int(state_id): name
        for state_id, name in re.findall(
            r'^\s*STATE_(\d+)\s*:\s*"([^"]+)"', text, re.MULTILINE
        )
    }


def main() -> int:
    errors: list[str] = []
    rows: dict[int, tuple[Path, set[int], str, str]] = {}
    all_provinces: set[int] = set()
    islands = raised_islands()
    raised_by_state = {
        state_id: set().union(*(island for island, _bridged in state_islands))
        for state_id, state_islands in islands.items()
    }
    all_raised = set().union(*raised_by_state.values())
    for path in sorted(STATE_DIR.glob("*.txt")):
        text = path.read_text(encoding="utf-8-sig", errors="strict")
        if not text.startswith(GENERATED_MARKER):
            continue
        state_id, provinces, _source = parse_state(path)
        climate_match = re.search(
            r"(?m)^# adiscord_climate_region = ([a-z_]+)\s*$", text
        )
        name_match = re.search(r"(?m)^# adiscord_strategic_name = (.+?)\s*$", text)
        if not climate_match or not name_match:
            errors.append(
                f"{path.relative_to(ROOT)}: missing climate or strategic-name marker"
            )
            continue
        if state_id in rows:
            errors.append(f"duplicate remainder state id {state_id}")
            continue
        overlap = all_provinces & provinces
        if overlap:
            errors.append(
                f"{path.relative_to(ROOT)} overlaps provinces {sorted(overlap)[:20]}"
            )
        all_provinces.update(provinces)
        if provinces & all_raised != raised_by_state.get(state_id, set()):
            errors.append(
                f"{path.relative_to(ROOT)}: raised island provinces "
                f"{sorted(provinces & all_raised)} differ from the archipelago table "
                f"{sorted(raised_by_state.get(state_id, set()))}"
            )
        rows[state_id] = (
            path,
            provinces,
            climate_match.group(1),
            name_match.group(1).strip(),
        )

        if state_id not in STATE_OWNERS and str(state_id) not in western_source()["states"] and re.search(
            r"\b(owner|add_core_of|victory_points|buildings)\s*=", text
        ):
            errors.append(
                f"{path.relative_to(ROOT)}: neutral shell has ownership/core/content history"
            )
        settled = "settlement" in western_source()["states"].get(str(state_id), {})
        if state_id not in STATE_OWNERS and not settled and not re.search(r"\bmanpower\s*=\s*1\b", text):
            errors.append(f"{path.relative_to(ROOT)}: neutral shell manpower must be 1")

    if 23 not in rows:
        errors.append("state 23 is not a generated connected remainder shell")
    new_ids = sorted(state_id for state_id in rows if state_id != 23)
    if new_ids and new_ids != list(range(FIRST_NEW_STATE_ID, new_ids[-1] + 1)):
        errors.append(
            f"remainder state IDs are not contiguous from {FIRST_NEW_STATE_ID}"
        )
    source_provinces = set().union(*(
        set(western_source()["source_partitions"][str(state_id)]["provinces"])
        if str(state_id) in western_source()["states"] else row[1] - all_raised
        for state_id, row in rows.items()
    ))
    if len(source_provinces) != EXPECTED_PROVINCE_COUNT:
        errors.append(
            f"remainder source coverage changed: expected {EXPECTED_PROVINCE_COUNT} provinces, found {len(source_provinces)}"
        )

    province_types, color_to_province = load_province_definitions()
    data = build_province_data(province_types, color_to_province)
    adjacency = load_province_adjacency(
        province_types, color_to_province, include_special_adjacencies=False
    )
    bridge_ends = island_bridge_ends()
    for state_id, (path, provinces, climate_key, strategic_name) in sorted(
        rows.items()
    ):
        errors.extend(
            raised_island_issues(
                state_id, provinces, islands.get(state_id, []), adjacency, bridge_ends
            )
        )
        if str(state_id) in western_source()["states"]:
            continue
        if not provinces - all_raised:
            errors.append(f"state {state_id}: empty")
            continue
        components = connected_components(provinces - all_raised, adjacency)
        if len(components) != 1:
            errors.append(
                f"state {state_id}: {len(components)} disconnected components "
                f"with sizes {[len(component) for component in components]}"
            )
        bands = {
            band_for_y(data[province_id].y)
            for province_id in provinces - all_raised
            if province_id in data
        }
        if len(bands) != 1:
            errors.append(f"state {state_id}: crosses latitude bands {sorted(bands)}")
        if (
            climate_key not in OUTER_REGION_SPECS
            or climate_key not in OUTER_CLIMATE_BELTS
        ):
            errors.append(f"state {state_id}: unknown climate key {climate_key}")
        elif len(bands) == 1 and OUTER_CLIMATE_BELTS[climate_key] != next(iter(bands)):
            errors.append(
                f"state {state_id}: climate {climate_key} belongs to belt "
                f"{OUTER_CLIMATE_BELTS[climate_key]}, geometry is belt {next(iter(bands))}"
            )
        if re.search(r"\s[IVXLCDM]+$", strategic_name):
            errors.append(
                f"state {state_id}: technical Roman suffix in {strategic_name}"
            )

    generated_localisation = load_localisation(LOCALISATION, errors)
    names: list[str] = []
    for state_id in sorted(rows):
        if state_id not in generated_localisation:
            errors.append(f"state {state_id}: missing Russian localisation")
            continue
        name = generated_localisation[state_id]
        names.append(name)
        if re.search(r"\s[IVXLCDM]+$", name):
            errors.append(
                f"state {state_id}: technical Roman suffix in localisation {name}"
            )
        if name != rows[state_id][3]:
            errors.append(
                f"state {state_id}: localisation {name!r} differs from strategic toponym {rows[state_id][3]!r}"
            )
    duplicates = sorted(name for name, count in Counter(names).items() if count > 1)
    if duplicates:
        errors.append(f"duplicate remainder state names {duplicates[:20]}")

    errors.extend(check_western_outputs())
    errors.extend(f"remainder country output differs: {path}" for path in synchronize())
    from tools.validators.validate_adiscord_outer_states import western_geography_issues

    errors.extend(western_geography_issues(adjacency, data))
    if errors:
        print(f"Remainder-state validation failed: {len(errors)} error(s)")
        for error in errors:
            print(f"- {error}")
        return 1
    print(
        f"Remainder-state validation passed: {len(rows)} generated states, "
        f"{len(all_provinces)} provinces, {len(LATITUDE_EDGES) + 1} latitude bands."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
