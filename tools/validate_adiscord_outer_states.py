#!/usr/bin/env python3
"""Validate the coarse-left and northern-right generated state pass."""

from __future__ import annotations

import re
import sys
from collections import Counter

from build_adiscord_outer_states import (
    CLIMATE_MARKER,
    FIRST_STATE_ID,
    GENERATED_MARKER,
    LOCALISATION,
    STATE_DIR,
    build_province_data,
    cluster_statistics,
    load_province_adjacency,
    load_province_definitions,
    load_source_pool,
    parse_state,
    select_landmasses,
)
from build_adiscord_strategic_regions import OUTER_REGION_SPECS, connected_components
from build_adiscord_northern_countries import POPULATION_MARKER
from validate_adiscord_northern_countries import validate as validate_northern_countries


def main() -> int:
    errors: list[str] = []
    source_pool, _outer, _source, generated_paths = load_source_pool()
    province_types, color_to_province = load_province_definitions()
    data = build_province_data(province_types, color_to_province)
    adjacency = load_province_adjacency(province_types, color_to_province)
    left, right, _right_components = select_landmasses(source_pool, adjacency, data)
    expected = left | right

    generated: dict[int, tuple[set[int], str, str]] = {}
    assigned: set[int] = set()
    landmass_counts: Counter[str] = Counter()
    climate_counts: Counter[str] = Counter()
    for path in generated_paths:
        state_id, provinces, source = parse_state(path)
        climate_match = re.search(rf"(?m)^{re.escape(CLIMATE_MARKER)}([a-z_]+)\s*$", source)
        landmass_match = re.fullmatch(r"\d+-outer-(left|right)\.txt", path.name)
        if state_id in generated:
            errors.append(f"duplicate generated state id {state_id}")
            continue
        if not climate_match:
            errors.append(f"state {state_id}: missing climate marker")
            climate = ""
        else:
            climate = climate_match.group(1)
            if climate not in OUTER_REGION_SPECS:
                errors.append(f"state {state_id}: unknown climate key {climate}")
        if not landmass_match:
            errors.append(f"state {state_id}: unexpected filename {path.name}")
            landmass = ""
        else:
            landmass = landmass_match.group(1)
        if not source.startswith(GENERATED_MARKER):
            errors.append(f"state {state_id}: missing generated marker")
        if landmass == "right":
            if POPULATION_MARKER not in source:
                errors.append(f"state {state_id}: northern-right shell is not populated")
        else:
            for forbidden in (r"\bowner\s*=", r"\badd_core_of\s*=", r"\bvictory_points\s*=", r"\bbuildings\s*=\s*\{"):
                if re.search(forbidden, source):
                    errors.append(f"state {state_id}: neutral shell contains {forbidden}")
            if not re.search(r"(?m)^\s*manpower\s*=\s*1\s*$", source):
                errors.append(f"state {state_id}: neutral shell manpower must be 1")
            if not re.search(r"(?m)^\s*state_category\s*=\s*(rural|wasteland)\s*$", source):
                errors.append(f"state {state_id}: invalid provisional state category")
        overlap = assigned & provinces
        if overlap:
            errors.append(f"state {state_id}: duplicate provinces {sorted(overlap)[:20]}")
        assigned.update(provinces)
        generated[state_id] = (provinces, climate, landmass)
        landmass_counts[landmass] += 1
        climate_counts[climate] += 1

        components = connected_components(provinces, adjacency)
        if landmass == "left" and len(components) != 1:
            errors.append(f"state {state_id}: coarse left-continent state has {len(components)} components")
        elif landmass == "right" and len(components) > 1:
            centres = [cluster_statistics(component, data) for component in components]
            widest = max(
                ((float(a["x"]) - float(b["x"])) ** 2 + (float(a["y"]) - float(b["y"])) ** 2) ** 0.5
                for index, a in enumerate(centres)
                for b in centres[index + 1:]
            )
            # Long, narrow island arcs are kept together to avoid one-province
            # states; 600 pixels still prevents grouping unrelated archipelagos.
            if widest > 600:
                errors.append(f"state {state_id}: island group spans {widest:.0f} pixels")

    ids = sorted(generated)
    if ids and ids != list(range(FIRST_STATE_ID, ids[-1] + 1)):
        errors.append("generated state IDs are not contiguous")
    if assigned != expected:
        errors.append(f"generated coverage mismatch: missing {len(expected-assigned)}, unexpected {len(assigned-expected)}")
    if not 130 <= landmass_counts["right"] <= 160:
        errors.append(f"right continent: expected 130-160 states, found {landmass_counts['right']}")
    if not 70 <= landmass_counts["left"] <= 85:
        errors.append(f"left continent: expected 70-85 coarse states, found {landmass_counts['left']}")

    errors.extend(f"northern countries: {issue}" for issue in validate_northern_countries())

    if not LOCALISATION.exists():
        errors.append("missing generated outer-state localisation")
    else:
        if not LOCALISATION.read_bytes().startswith(b"\xef\xbb\xbf"):
            errors.append("outer-state localisation must use UTF-8 BOM")
        localisation = LOCALISATION.read_text(encoding="utf-8-sig", errors="strict")
        name_rows = re.findall(r'(?m)^\s*STATE_(\d+)\s*:\s*"([^"]+)"\s*$', localisation)
        keys = Counter(int(value) for value, _name in name_rows)
        for state_id in ids:
            if keys[state_id] != 1:
                errors.append(f"STATE_{state_id}: expected one generated Russian name")
        unexpected = sorted(set(keys) - set(ids))
        if unexpected:
            errors.append(f"outer localisation has unexpected state keys {unexpected[:20]}")
        names = Counter(name for _state_id, name in name_rows)
        duplicate_names = sorted(name for name, count in names.items() if count > 1)
        if duplicate_names:
            errors.append(f"outer localisation has duplicate names {duplicate_names[:20]}")
        numbered_names = [name for name in names if re.search(r"\s[IVXLCDM]+$", name)]
        if numbered_names:
            errors.append(f"outer localisation has technical Roman suffixes {numbered_names[:20]}")

    if errors:
        print(f"Outer-state validation failed: {len(errors)} error(s)")
        for error in errors:
            print(f"- {error}")
        return 1
    print(
        f"Outer-state validation passed: {len(generated)} generated states "
        f"({landmass_counts['right']} populated northern-right, {landmass_counts['left']} neutral coarse-left) "
        f"across {len(climate_counts)} climate groups."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
