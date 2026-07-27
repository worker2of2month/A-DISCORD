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
    REGIONS,
    SEA_REGIONS,
    connected_components,
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
    sea_provinces = {province_id for province_id, province_type in definitions.items() if province_type == "sea"}
    sea_components = connected_components(sea_provinces, adjacency)
    main_ocean = sea_components[0] if sea_components else set()
    states = load_state_provinces()
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

    for region_id, data in regions.items():
        validate_weather(region_id, str(data["text"]), errors)

    localisation_path = ROOT / "localisation" / "replace" / "strategic_region_names_l_russian.yml"
    if not localisation_path.exists():
        errors.append("missing Russian strategic-region localisation")
    else:
        if not localisation_path.read_bytes().startswith(b"\xef\xbb\xbf"):
            errors.append("strategic-region localisation must use UTF-8 BOM")
        localisation = localisation_path.read_text(encoding="utf-8-sig", errors="strict")
        keys = Counter(re.findall(r"^\s*(STRATEGICREGION_\d+)\s*:", localisation, re.MULTILINE))
        for region_id in sorted(expected_region_ids):
            key = f"STRATEGICREGION_{region_id}"
            if keys[key] != 1:
                errors.append(f"localisation key {key}: expected once, found {keys[key]}")

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
