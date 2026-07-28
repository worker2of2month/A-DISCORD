#!/usr/bin/env python3
"""Validate strategic-region coverage, state membership, weather and localisation."""

from __future__ import annotations

import csv
import re
import sys
from collections import Counter
from pathlib import Path

from build_adiscord_strategic_regions import (
    MONTH_RANGES,
    OUTER_CLIMATE_BELTS,
    OUTER_REGION_SPECS,
    OUTER_STATE_MARKER,
    REGIONS,
    REMAINDER_STATE_MARKER,
    SEA_REGIONS,
    build_state_adjacency,
    connected_components,
    phenomenon,
    load_province_adjacency,
    load_province_definitions,
)


ROOT = Path(__file__).resolve().parents[1]
PHENOMENA = ("no_phenomenon", "rain_light", "rain_heavy", "snow", "blizzard", "sandstorm")
PROBABILITIES = PHENOMENA + ("arctic_water", "mud", "min_snow_level")


def extract_block(text: str, key: str, start: int = 0) -> tuple[str, int]:
    match = re.search(rf"\b{re.escape(key)}\s*=\s*\{{", text[start:])
    if not match:
        raise ValueError(f"missing {key} block")
    opening = start + match.end() - 1
    depth = 0
    for index in range(opening, len(text)):
        if text[index] == "{":
            depth += 1
        elif text[index] == "}":
            depth -= 1
            if depth == 0:
                return text[opening + 1:index], index + 1
    raise ValueError(f"unterminated {key} block")


def load_definitions() -> dict[int, str]:
    definitions: dict[int, str] = {}
    with (ROOT / "map" / "definition.csv").open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.reader(handle, delimiter=";"):
            if len(row) >= 5 and row[0].isdigit() and int(row[0]) > 0:
                definitions[int(row[0])] = row[4]
    return definitions


def load_state_provinces() -> dict[int, set[int]]:
    states: dict[int, set[int]] = {}
    for path in (ROOT / "history" / "states").glob("*.txt"):
        text = path.read_text(encoding="utf-8-sig", errors="strict")
        state_match = re.search(r"\bid\s*=\s*(\d+)", text)
        province_match = re.search(r"\bprovinces\s*=\s*\{([^}]*)\}", text, re.DOTALL)
        if state_match and province_match:
            states[int(state_match.group(1))] = {int(value) for value in re.findall(r"\d+", province_match.group(1))}
    return states


def load_generated_climate_keys(errors: list[str]) -> dict[int, str]:
    climate_keys: dict[int, str] = {}
    for path in (ROOT / "history" / "states").glob("*.txt"):
        text = path.read_text(encoding="utf-8-sig", errors="strict")
        if not text.startswith((OUTER_STATE_MARKER, REMAINDER_STATE_MARKER)):
            continue
        state_match = re.search(r"\bid\s*=\s*(\d+)", text)
        climate_match = re.search(r"(?m)^# adiscord_climate_region = ([a-z_]+)\s*$", text)
        if not state_match or not climate_match:
            errors.append(f"{path.relative_to(ROOT)}: missing generated climate marker")
            continue
        climate_key = climate_match.group(1)
        if climate_key not in OUTER_CLIMATE_BELTS:
            errors.append(f"{path.relative_to(ROOT)}: unknown climate key {climate_key}")
            continue
        climate_keys[int(state_match.group(1))] = climate_key
    return climate_keys


def parse_regions(errors: list[str]) -> dict[int, dict[str, object]]:
    parsed: dict[int, dict[str, object]] = {}
    for path in sorted((ROOT / "map" / "strategicregions").glob("*.txt")):
        try:
            text = path.read_text(encoding="utf-8-sig", errors="strict")
            outer, _ = extract_block(text, "strategic_region")
            id_match = re.search(r"\bid\s*=\s*(\d+)", outer)
            name_match = re.search(r'\bname\s*=\s*"([^"]+)"', outer)
            if not id_match or not name_match:
                raise ValueError("missing id or name")
            region_id = int(id_match.group(1))
            if region_id in parsed:
                raise ValueError(f"duplicate strategic region id {region_id}")
            province_block, _ = extract_block(outer, "provinces")
            provinces = {int(value) for value in re.findall(r"\d+", province_block)}
            parsed[region_id] = {"path": path, "name": name_match.group(1), "provinces": provinces, "text": outer}
        except (UnicodeError, ValueError) as exc:
            errors.append(f"{path.relative_to(ROOT)}: {exc}")
    return parsed


def validate_weather(region_id: int, text: str, errors: list[str]) -> None:
    try:
        weather, _ = extract_block(text, "weather")
    except ValueError as exc:
        errors.append(f"region {region_id}: {exc}")
        return

    periods: list[str] = []
    cursor = 0
    while True:
        try:
            period, cursor = extract_block(weather, "period", cursor)
        except ValueError:
            break
        periods.append(period)
    if len(periods) != 12:
        errors.append(f"region {region_id}: expected 12 weather periods, found {len(periods)}")
        return

    for month, period in enumerate(periods):
        between = re.search(r"\bbetween\s*=\s*\{\s*([^}]+?)\s*\}", period)
        temperature = re.search(r"\btemperature\s*=\s*\{\s*(-?[0-9.]+)\s+(-?[0-9.]+)\s*\}", period)
        if not between or " ".join(between.group(1).split()) != MONTH_RANGES[month]:
            errors.append(f"region {region_id}, month {month}: invalid date range")
        if not temperature:
            errors.append(f"region {region_id}, month {month}: missing temperature range")
        elif float(temperature.group(1)) > float(temperature.group(2)):
            errors.append(f"region {region_id}, month {month}: reversed temperature range")

        values: dict[str, float] = {}
        for key in PROBABILITIES:
            match = re.search(rf"\b{key}\s*=\s*([0-9.]+)", period)
            if not match:
                errors.append(f"region {region_id}, month {month}: missing {key}")
                continue
            value = float(match.group(1))
            values[key] = value
            if not 0.0 <= value <= 1.0:
                errors.append(f"region {region_id}, month {month}: {key}={value} is outside 0..1")
        if sum(values.get(key, 0.0) for key in PHENOMENA) > 1.0001:
            errors.append(f"region {region_id}, month {month}: phenomenon probabilities exceed 1")


def main() -> int:
    errors: list[str] = []
    definitions, color_to_province = load_province_definitions()
    adjacency = load_province_adjacency(definitions, color_to_province)
    physical_adjacency = load_province_adjacency(
        definitions, color_to_province, include_special_adjacencies=False
    )
    sea_provinces = {province_id for province_id, province_type in definitions.items() if province_type == "sea"}
    sea_components = connected_components(sea_provinces, adjacency)
    main_ocean = sea_components[0] if sea_components else set()
    states = load_state_provinces()
    generated_climate_keys = load_generated_climate_keys(errors)
    regions = parse_regions(errors)
    expected_region_ids = {region.region_id for region in (*SEA_REGIONS, *REGIONS)}
    sea_region_ids = {region.region_id for region in SEA_REGIONS}
    if set(regions) != expected_region_ids:
        errors.append(f"strategic region ids differ: expected {sorted(expected_region_ids)}, found {sorted(regions)}")

    province_regions: dict[int, list[int]] = {}
    for region_id, data in regions.items():
        expected_name = f"STRATEGICREGION_{region_id}"
        if data["name"] != expected_name:
            errors.append(f"region {region_id}: expected name {expected_name}, found {data['name']}")
        has_naval_terrain = bool(re.search(r"\bnaval_terrain\s*=\s*water_deep_ocean\b", str(data["text"])))
        if region_id in sea_region_ids and not has_naval_terrain:
            errors.append(f"sea region {region_id}: missing naval terrain")
        elif region_id not in sea_region_ids and has_naval_terrain:
            errors.append(f"land region {region_id}: unexpected naval terrain")
        for province_id in data["provinces"]:
            province_regions.setdefault(province_id, []).append(region_id)
            if province_id not in definitions:
                errors.append(f"region {region_id}: unknown province {province_id}")
            elif region_id in sea_region_ids and definitions[province_id] != "sea":
                errors.append(f"sea region {region_id}: non-sea province {province_id}")
            elif region_id not in sea_region_ids and definitions[province_id] == "sea" and province_id in main_ocean:
                errors.append(f"land region {region_id}: ocean province {province_id}")

    naval_provinces = set().union(
        *(set(regions[region_id]["provinces"]) for region_id in sea_region_ids if region_id in regions)
    )
    missing_ocean = sorted(main_ocean - naval_provinces)
    non_ocean_naval = sorted(naval_provinces - main_ocean)
    if missing_ocean:
        errors.append(f"ocean provinces outside naval regions: {missing_ocean[:30]}")
    if non_ocean_naval:
        errors.append(f"isolated lake provinces inside naval regions: {non_ocean_naval[:30]}")
    for region_id in sorted(sea_region_ids & set(regions)):
        provinces = set(regions[region_id]["provinces"])
        components = connected_components(provinces, adjacency)
        if len(components) != 1:
            errors.append(
                f"sea region {region_id}: fractioned into {len(components)} components "
                f"with sizes {[len(component) for component in components]}"
            )
    for component in sea_components[1:]:
        actual_regions = {
            province_regions[province_id][0]
            for province_id in component
            if province_id in province_regions and len(province_regions[province_id]) == 1
        }
        if len(actual_regions) != 1 or actual_regions & sea_region_ids:
            errors.append(
                f"isolated lake component {sorted(component)} must belong to one land region, found {sorted(actual_regions)}"
            )

    missing = sorted(set(definitions) - set(province_regions))
    duplicates = sorted(province_id for province_id, ids in province_regions.items() if len(ids) != 1)
    if missing:
        errors.append(f"provinces without strategic region: {missing[:30]}")
    if duplicates:
        errors.append(f"provinces in multiple strategic regions: {duplicates[:30]}")

    expected_by_state = {state_id: region.region_id for region in REGIONS for state_id in region.states}
    for state_id, provinces in sorted(states.items()):
        actual = {province_regions[province_id][0] for province_id in provinces if province_id in province_regions}
        if len(actual) != 1:
            errors.append(f"state {state_id}: split between strategic regions {sorted(actual)}")
        elif state_id not in expected_by_state:
            errors.append(f"state {state_id}: absent from strategic-region manifest")
        elif next(iter(actual)) != expected_by_state[state_id]:
            errors.append(f"state {state_id}: expected region {expected_by_state[state_id]}, found {next(iter(actual))}")

    state_adjacency = build_state_adjacency(states, physical_adjacency)
    profile_belts: dict[str, set[int]] = {}
    for climate_key, (_slug, _name, profile) in OUTER_REGION_SPECS.items():
        profile_belts.setdefault(profile, set()).add(OUTER_CLIMATE_BELTS[climate_key])
    for region in REGIONS:
        if region.region_id < 43:
            continue
        components = connected_components(set(region.states), state_adjacency)
        if len(components) != 1:
            errors.append(
                f"generated land region {region.region_id}: fractioned into {len(components)} "
                f"non-neighbouring state groups {list(map(sorted, components))}"
            )
        belts = {
            OUTER_CLIMATE_BELTS[generated_climate_keys[state_id]]
            for state_id in region.states
            if state_id in generated_climate_keys
        }
        if len(belts) != 1:
            errors.append(f"generated land region {region.region_id}: crosses climate belts {sorted(belts)}")
        elif next(iter(belts)) not in profile_belts.get(region.climate, set()):
            errors.append(
                f"generated land region {region.region_id}: profile {region.climate} does not match belt {next(iter(belts))}"
            )

    for climate_key, (_slug, _name, profile) in OUTER_REGION_SPECS.items():
        if not climate_key.startswith("world_"):
            continue
        belt = OUTER_CLIMATE_BELTS[climate_key]
        max_snow = max(phenomenon(profile, month)[3] for month in range(12))
        max_blizzard = max(phenomenon(profile, month)[4] for month in range(12))
        if belt == 5 and (max_snow > 0.0 or max_blizzard > 0.0):
            errors.append(f"{climate_key}: tropical belt must not generate snow or blizzards")
        elif belt == 4 and (max_snow > 0.03 or max_blizzard > 0.0):
            errors.append(f"{climate_key}: warm belt has excessive winter weather")
        elif belt <= 1 and max_snow < 0.25:
            errors.append(f"{climate_key}: polar/subarctic belt has too little winter snow")

    checked_state_edges: set[tuple[int, int]] = set()
    for state_id, neighbours in state_adjacency.items():
        if state_id not in generated_climate_keys:
            continue
        for neighbour in neighbours:
            if neighbour not in generated_climate_keys:
                continue
            edge = tuple(sorted((state_id, neighbour)))
            if edge in checked_state_edges:
                continue
            checked_state_edges.add(edge)
            first_belt = OUTER_CLIMATE_BELTS[generated_climate_keys[state_id]]
            second_belt = OUTER_CLIMATE_BELTS[generated_climate_keys[neighbour]]
            if abs(first_belt - second_belt) > 1:
                errors.append(
                    f"neighbouring generated states {state_id}/{neighbour}: climate jumps from belt "
                    f"{first_belt} to {second_belt}"
                )

    for region_id, data in regions.items():
        validate_weather(region_id, str(data["text"]), errors)

    localisation_path = ROOT / "localisation" / "replace" / "strategic_region_names_l_russian.yml"
    if not localisation_path.exists():
        errors.append("missing Russian strategic-region localisation")
    else:
        if not localisation_path.read_bytes().startswith(b"\xef\xbb\xbf"):
            errors.append("strategic-region localisation must use UTF-8 BOM")
        localisation = localisation_path.read_text(encoding="utf-8-sig", errors="strict")
        localisation_rows = re.findall(
            r'^\s*(STRATEGICREGION_\d+)\s*:\s*"([^"]+)"', localisation, re.MULTILINE
        )
        keys = Counter(key for key, _name in localisation_rows)
        for region_id in sorted(expected_region_ids):
            key = f"STRATEGICREGION_{region_id}"
            if keys[key] != 1:
                errors.append(f"localisation key {key}: expected once, found {keys[key]}")
        generated_names = [
            name
            for key, name in localisation_rows
            if int(key.rsplit("_", 1)[1]) >= 43
        ]
        duplicate_generated_names = sorted(
            name for name, count in Counter(generated_names).items() if count > 1
        )
        if duplicate_generated_names:
            errors.append(f"generated strategic regions have duplicate names {duplicate_generated_names[:20]}")
        technical_names = [
            name for name in generated_names if re.search(r"\b(?:лев(?:ый|ая|ое|ые)|прав(?:ый|ая|ое|ые))\b", name, re.IGNORECASE)
        ]
        if technical_names:
            errors.append(f"generated strategic regions expose technical side names {technical_names[:20]}")
        numbered_names = [
            name for name in generated_names if re.search(r"\s[IVXLCDM]+$", name)
        ]
        if numbered_names:
            errors.append(f"generated strategic regions expose technical Roman suffixes {numbered_names[:20]}")
        misplaced_state_toponyms = [
            name
            for _key, name in localisation_rows
            if re.search(r"(?:Римат|Итор|Англи)", name, re.IGNORECASE)
        ]
        if misplaced_state_toponyms:
            errors.append(
                "strategic regions reuse state/country-only toponyms "
                f"{misplaced_state_toponyms[:20]}"
            )

    weather_positions_path = ROOT / "map" / "weatherpositions.txt"
    position_counts: Counter[int] = Counter()
    for line_number, line in enumerate(weather_positions_path.read_text(encoding="utf-8-sig", errors="strict").splitlines(), 1):
        if not line.strip():
            continue
        fields = line.split(";")
        if len(fields) != 5 or not fields[0].isdigit() or fields[4] not in ("small", "big"):
            errors.append(f"weatherpositions.txt:{line_number}: invalid row")
            continue
        try:
            float(fields[1])
            float(fields[2])
            float(fields[3])
        except ValueError:
            errors.append(f"weatherpositions.txt:{line_number}: invalid coordinates")
            continue
        position_counts[int(fields[0])] += 1
    for region_id in sorted(expected_region_ids):
        if position_counts[region_id] == 0:
            errors.append(f"region {region_id}: no weather position")
    unexpected_positions = sorted(set(position_counts) - expected_region_ids)
    if unexpected_positions:
        errors.append(f"weather positions reference unknown regions: {unexpected_positions}")

    if errors:
        print(f"Strategic-region validation failed: {len(errors)} error(s)")
        for error in errors:
            print(f"- {error}")
        return 1

    land_counts = {region_id: len(data["provinces"]) for region_id, data in regions.items() if region_id not in sea_region_ids}
    sea_counts = {region_id: len(data["provinces"]) for region_id, data in regions.items() if region_id in sea_region_ids}
    print(f"Strategic-region validation passed: {len(regions)} regions, {len(states)} states, {len(definitions)} provinces.")
    print(f"Land-region province counts: {land_counts}")
    print(f"Sea-region province counts: {sea_counts}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
