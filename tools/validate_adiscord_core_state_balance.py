"""Validate the approved NOD/STP/VAL starting-state balance contract."""

from __future__ import annotations

import re
import sys
from collections import defaultdict
from pathlib import Path

from adiscord_core_state_balance_manifest import (
    CAPITAL_CUSTOM_BUILDING_STATES,
    EXPECTED_DIRECT_BUILDINGS,
    EXPECTED_INDUSTRY_TOTALS,
    EXPECTED_POPULATION_TOTALS,
    EXPECTED_RESOURCES,
    EXPECTED_RESOURCE_TOTALS,
    EXPECTED_VP_NAMES,
    NON_URBAN_SETTLEMENT_VPS,
    SETTLEMENT_VPS,
    STP_CLAIMS_ON_VAL,
    TARGET_STATES,
    URBAN_VP_MINIMUMS,
)


ROOT = Path(__file__).resolve().parents[1]
ERRORS: list[str] = []
FACTORY_KEYS = ("industrial_complex", "arms_factory", "dockyard")
CUSTOM_BUILDING_KEYS = ("ADISCORD_industrial_cluster", "ADISCORD_business_center")


def check(condition: bool, message: str) -> None:
    if not condition:
        ERRORS.append(message)


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig", errors="strict")


def named_blocks(source: str, name: str) -> list[str]:
    result: list[str] = []
    pattern = re.compile(rf"(?m)^\s*{re.escape(name)}\s*=\s*\{{")
    for match in pattern.finditer(source):
        start = source.find("{", match.start())
        depth = 0
        for index in range(start, len(source)):
            if source[index] == "{":
                depth += 1
            elif source[index] == "}":
                depth -= 1
                if depth == 0:
                    result.append(source[start + 1:index])
                    break
        else:
            ERRORS.append(f"unterminated {name} block")
    return result


def first_block(source: str, name: str) -> str:
    blocks = named_blocks(source, name)
    return blocks[0] if blocks else ""


def direct_integer_assignments(source: str) -> dict[str, int]:
    result: dict[str, int] = {}
    depth = 0
    for raw_line in source.splitlines():
        line = raw_line.split("#", 1)[0]
        if depth == 0:
            match = re.match(r"\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(\d+)\s*$", line)
            if match:
                result[match.group(1)] = int(match.group(2))
        depth += line.count("{") - line.count("}")
    return result


def scalar(source: str, key: str) -> str | None:
    match = re.search(rf"(?m)^\s*{re.escape(key)}\s*=\s*([A-Za-z0-9_]+)\s*$", source)
    return match.group(1) if match else None


def victory_points(history: str) -> list[tuple[int, int]]:
    return [
        (int(province), int(value))
        for province, value in re.findall(r"victory_points\s*=\s*\{\s*(\d+)\s+(\d+)\s*\}", history)
    ]


def validate() -> None:
    definition_provinces: set[int] = set()
    province_terrain: dict[int, str] = {}
    with (ROOT / "map/definition.csv").open(encoding="utf-8-sig") as handle:
        for line in handle:
            fields = line.rstrip("\r\n").split(";")
            if len(fields) >= 7 and fields[0].isdigit():
                province = int(fields[0])
                definition_provinces.add(province)
                province_terrain[province] = fields[6]

    localisation_path = ROOT / "localisation/russian/victory_points_l_russian.yml"
    localisation_bytes = localisation_path.read_bytes()
    check(localisation_bytes.startswith(b"\xef\xbb\xbf"), "victory point localisation must use UTF-8 BOM")
    localisation = localisation_bytes.decode("utf-8-sig", errors="strict")

    sources: dict[int, str] = {}
    histories: dict[int, str] = {}
    provinces_by_state: dict[int, set[int]] = {}
    vps_by_state: dict[int, list[tuple[int, int]]] = {}
    population_totals: dict[str, int] = defaultdict(int)
    industry_totals: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    resource_totals: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))

    for state_id, (relative_path, owner, population, category) in sorted(TARGET_STATES.items()):
        path = ROOT / relative_path
        check(path.is_file(), f"state {state_id}: missing {relative_path}")
        if not path.is_file():
            continue
        source = read_text(path)
        sources[state_id] = source
        history_blocks = named_blocks(source, "history")
        check(len(history_blocks) == 1, f"state {state_id}: expected one history block, found {len(history_blocks)}")
        history = history_blocks[0] if history_blocks else ""
        histories[state_id] = history

        check(scalar(source, "id") == str(state_id), f"state {state_id}: wrong id")
        actual_population = scalar(source, "manpower")
        check(actual_population == str(population), f"state {state_id}: expected manpower {population}, found {actual_population}")
        actual_category = scalar(source, "state_category")
        check(actual_category == category, f"state {state_id}: expected category {category}, found {actual_category}")
        check(scalar(history, "owner") == owner, f"state {state_id}: expected owner {owner}")
        check(bool(re.search(rf"(?m)^\s*add_core_of\s*=\s*{owner}\s*$", history)), f"state {state_id}: missing {owner} core")
        population_totals[owner] += int(actual_population or 0)

        province_block = first_block(source, "provinces")
        provinces = {int(value) for value in re.findall(r"\d+", province_block)}
        provinces_by_state[state_id] = provinces
        check(bool(provinces), f"state {state_id}: empty province list")

        building_blocks = named_blocks(history, "buildings")
        expected_buildings = EXPECTED_DIRECT_BUILDINGS[state_id]
        expected_block_count = 0 if not expected_buildings else 1
        check(
            len(building_blocks) == expected_block_count,
            f"state {state_id}: expected {expected_block_count} state buildings block(s), found {len(building_blocks)}",
        )
        actual_buildings = direct_integer_assignments(building_blocks[0]) if building_blocks else {}
        check(actual_buildings == expected_buildings, f"state {state_id}: wrong direct buildings {actual_buildings}")
        for key in FACTORY_KEYS:
            industry_totals[owner][key] += actual_buildings.get(key, 0)
        for key in CUSTOM_BUILDING_KEYS:
            expected_custom = 1 if state_id in CAPITAL_CUSTOM_BUILDING_STATES else 0
            check(actual_buildings.get(key, 0) == expected_custom, f"state {state_id}: expected {key} = {expected_custom}")

        resource_blocks = named_blocks(source, "resources")
        actual_resources = direct_integer_assignments(resource_blocks[0]) if resource_blocks else {}
        check(actual_resources == EXPECTED_RESOURCES[state_id], f"state {state_id}: wrong resources {actual_resources}")
        for resource, value in actual_resources.items():
            resource_totals[owner][resource] += value

        state_vps = victory_points(history)
        check(len(state_vps) == len({province for province, _value in state_vps}), f"state {state_id}: duplicate VP province")
        vps_by_state[state_id] = state_vps
        for province, value in state_vps:
            check(province in definition_provinces, f"state {state_id}: VP {province} missing from definition.csv")
            check(province in provinces, f"state {state_id}: VP {province} is outside the state")
            terrain = province_terrain.get(province)
            if terrain == "urban":
                check(value >= 5, f"state {state_id}: urban VP {province} is below 5")
            else:
                check(province in NON_URBAN_SETTLEMENT_VPS, f"state {state_id}: unapproved non-urban VP {province}")
                check(value == 1, f"state {state_id}: settlement VP {province} must equal 1")

    check(dict(population_totals) == EXPECTED_POPULATION_TOTALS, f"wrong population totals {dict(population_totals)}")
    for owner, expected in EXPECTED_INDUSTRY_TOTALS.items():
        actual = {key: industry_totals[owner].get(key, 0) for key in FACTORY_KEYS}
        check(actual == expected, f"{owner}: wrong industry totals {actual}")
    for owner, expected in EXPECTED_RESOURCE_TOTALS.items():
        actual = dict(resource_totals[owner])
        check(actual == expected, f"{owner}: wrong resource totals {actual}")

    for state_id, (province, value, _name) in SETTLEMENT_VPS.items():
        check((province, value) in vps_by_state.get(state_id, []), f"state {state_id}: missing settlement VP {province}:{value}")
        check(province_terrain.get(province) != "urban", f"state {state_id}: settlement VP {province} unexpectedly became urban")
    for state_id, expected_vps in URBAN_VP_MINIMUMS.items():
        actual_vps = dict(vps_by_state.get(state_id, []))
        for province, value in expected_vps.items():
            check(actual_vps.get(province) == value, f"state {state_id}: expected urban VP {province}:{value}")
            check(province_terrain.get(province) == "urban", f"state {state_id}: VP {province} is not urban")

    for province, expected_name in EXPECTED_VP_NAMES.items():
        pattern = re.compile(rf'(?m)^\s*VICTORY_POINTS_{province}(?::\d+)?:\s*"([^"]*)"')
        matches = pattern.findall(localisation)
        check(len(matches) == 1, f"VP {province}: expected one Russian localisation key, found {len(matches)}")
        if matches:
            check(matches[0] == expected_name, f"VP {province}: expected name {expected_name!r}, found {matches[0]!r}")

    for state_id in STP_CLAIMS_ON_VAL:
        check(bool(re.search(r"(?m)^\s*add_claim_by\s*=\s*STP\s*$", histories.get(state_id, ""))), f"state {state_id}: missing STP claim")
    stolen_val_resources = sum(sum(EXPECTED_RESOURCES[state_id].values()) for state_id in STP_CLAIMS_ON_VAL)
    total_val_resources = sum(EXPECTED_RESOURCE_TOTALS["VAL"].values())
    check(stolen_val_resources == 56 and total_val_resources == 68, "VAL resource corridor must contain 56 of 68 resource units")


def main() -> int:
    validate()
    if ERRORS:
        print(f"Core state balance validation failed: {len(ERRORS)} error(s)")
        for error in ERRORS:
            print(f"- {error}")
        return 1
    print("Core state balance validation passed: NOD/STP/VAL population, VP, industry, buildings, and resources match the approved contract.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
