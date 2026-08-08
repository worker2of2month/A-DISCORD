#!/usr/bin/env python3
"""Validate the connected latitude-band shells replacing catch-all state 23."""

from __future__ import annotations

import re
import sys
from collections import Counter
from pathlib import Path

_REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(_REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPOSITORY_ROOT))

try:
    from tools.builders.build_adiscord_outer_states import build_province_data, parse_state
    from tools.builders.build_adiscord_remainder_states import (
        BASE_STATE_LOCALISATION,
        EXPECTED_PROVINCE_COUNT,
        FIRST_NEW_STATE_ID,
        GENERATED_MARKER,
        LATITUDE_EDGES,
        LOCALISATION,
        band_for_y,
    )
    from tools.builders.build_adiscord_strategic_regions import (
        OUTER_CLIMATE_BELTS,
        OUTER_REGION_SPECS,
        connected_components,
        load_province_adjacency,
        load_province_definitions,
    )
except ModuleNotFoundError:
    from builders.build_adiscord_outer_states import build_province_data, parse_state
    from builders.build_adiscord_remainder_states import (
        BASE_STATE_LOCALISATION,
        EXPECTED_PROVINCE_COUNT,
        FIRST_NEW_STATE_ID,
        GENERATED_MARKER,
        LATITUDE_EDGES,
        LOCALISATION,
        band_for_y,
    )
    from builders.build_adiscord_strategic_regions import (
        OUTER_CLIMATE_BELTS,
        OUTER_REGION_SPECS,
        connected_components,
        load_province_adjacency,
        load_province_definitions,
    )


ROOT = Path(__file__).resolve().parents[1]
STATE_DIR = ROOT / "history" / "states"


def load_localisation(path: Path, errors: list[str]) -> dict[int, str]:
    if not path.exists():
        errors.append(f"missing localisation {path.relative_to(ROOT)}")
        return {}
    if not path.read_bytes().startswith(b"\xef\xbb\xbf"):
        errors.append(f"{path.relative_to(ROOT)} must use UTF-8 BOM")
    text = path.read_text(encoding="utf-8-sig", errors="strict")
    return {
        int(state_id): name
        for state_id, name in re.findall(r'^\s*STATE_(\d+)\s*:\s*"([^"]+)"', text, re.MULTILINE)
    }


def main() -> int:
    errors: list[str] = []
    rows: dict[int, tuple[Path, set[int], str, str]] = {}
    all_provinces: set[int] = set()
    for path in sorted(STATE_DIR.glob("*.txt")):
        text = path.read_text(encoding="utf-8-sig", errors="strict")
        if not text.startswith(GENERATED_MARKER):
            continue
        state_id, provinces, _source = parse_state(path)
        climate_match = re.search(r"(?m)^# adiscord_climate_region = ([a-z_]+)\s*$", text)
        name_match = re.search(r"(?m)^# adiscord_strategic_name = (.+?)\s*$", text)
        if not climate_match or not name_match:
            errors.append(f"{path.relative_to(ROOT)}: missing climate or strategic-name marker")
            continue
        if state_id in rows:
            errors.append(f"duplicate remainder state id {state_id}")
            continue
        overlap = all_provinces & provinces
        if overlap:
            errors.append(f"{path.relative_to(ROOT)} overlaps provinces {sorted(overlap)[:20]}")
        all_provinces.update(provinces)
        rows[state_id] = (path, provinces, climate_match.group(1), name_match.group(1).strip())

        if re.search(r"\b(owner|add_core_of|victory_points|buildings)\s*=", text):
            errors.append(f"{path.relative_to(ROOT)}: neutral shell has ownership/core/content history")
        if not re.search(r"\bmanpower\s*=\s*1\b", text):
            errors.append(f"{path.relative_to(ROOT)}: neutral shell manpower must be 1")

    if 23 not in rows:
        errors.append("state 23 is not a generated connected remainder shell")
    new_ids = sorted(state_id for state_id in rows if state_id != 23)
    if new_ids and new_ids != list(range(FIRST_NEW_STATE_ID, new_ids[-1] + 1)):
        errors.append(f"remainder state IDs are not contiguous from {FIRST_NEW_STATE_ID}")
    if len(all_provinces) != EXPECTED_PROVINCE_COUNT:
        errors.append(
            f"remainder coverage changed: expected {EXPECTED_PROVINCE_COUNT} provinces, found {len(all_provinces)}"
        )

    province_types, color_to_province = load_province_definitions()
    data = build_province_data(province_types, color_to_province)
    adjacency = load_province_adjacency(
        province_types, color_to_province, include_special_adjacencies=False
    )
    for state_id, (path, provinces, climate_key, strategic_name) in sorted(rows.items()):
        if not provinces:
            errors.append(f"state {state_id}: empty")
            continue
        components = connected_components(provinces, adjacency)
        if len(components) != 1:
            errors.append(
                f"state {state_id}: {len(components)} disconnected components "
                f"with sizes {[len(component) for component in components]}"
            )
        bands = {band_for_y(data[province_id].y) for province_id in provinces if province_id in data}
        if len(bands) != 1:
            errors.append(f"state {state_id}: crosses latitude bands {sorted(bands)}")
        if climate_key not in OUTER_REGION_SPECS or climate_key not in OUTER_CLIMATE_BELTS:
            errors.append(f"state {state_id}: unknown climate key {climate_key}")
        elif len(bands) == 1 and OUTER_CLIMATE_BELTS[climate_key] != next(iter(bands)):
            errors.append(
                f"state {state_id}: climate {climate_key} belongs to belt "
                f"{OUTER_CLIMATE_BELTS[climate_key]}, geometry is belt {next(iter(bands))}"
            )
        if re.search(r"\s[IVXLCDM]+$", strategic_name):
            errors.append(f"state {state_id}: technical Roman suffix in {strategic_name}")

    generated_localisation = load_localisation(LOCALISATION, errors)
    base_localisation = load_localisation(BASE_STATE_LOCALISATION, errors)
    names: list[str] = []
    for state_id in sorted(rows):
        source = base_localisation if state_id == 23 else generated_localisation
        if state_id not in source:
            errors.append(f"state {state_id}: missing Russian localisation")
            continue
        name = source[state_id]
        names.append(name)
        if re.search(r"\s[IVXLCDM]+$", name):
            errors.append(f"state {state_id}: technical Roman suffix in localisation {name}")
        if name != rows[state_id][3]:
            errors.append(
                f"state {state_id}: localisation {name!r} differs from strategic toponym {rows[state_id][3]!r}"
            )
    duplicates = sorted(name for name, count in Counter(names).items() if count > 1)
    if duplicates:
        errors.append(f"duplicate remainder state names {duplicates[:20]}")

    if errors:
        print(f"Remainder-state validation failed: {len(errors)} error(s)")
        for error in errors:
            print(f"- {error}")
        return 1
    print(
        f"Remainder-state validation passed: {len(rows)} connected states, "
        f"{len(all_provinces)} provinces, {len(LATITUDE_EDGES) + 1} latitude bands."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
