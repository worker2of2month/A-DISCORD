"""Targeted validation for the July state pass and southern microstates."""

from __future__ import annotations

import re
import sys
from pathlib import Path

from PIL import Image

_REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
if str(_REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPOSITORY_ROOT))

from tools.lib.adiscord_core_state_balance_manifest import NON_URBAN_SETTLEMENT_VPS
from tools.lib.adiscord_vorkerland_theatre_manifest import (
    UNITY_TOWER_NAME,
    UNITY_TOWER_PROVINCE,
    UNITY_TOWER_STATE,
    UNITY_TOWER_VALUE,
    VORKERLAND_PROTECTED_LANDMARK_VPS,
    VORKERLAND_THEATRE_PACKAGES,
    VORKERLAND_THEATRE_PACKAGE_TOTALS,
    VORKERLAND_THEATRE_RETIRED_VP_IDS,
    VORKERLAND_THEATRE_VICTORY_POINTS,
    VORKERLAND_THEATRE_VP_NAME_OVERRIDES,
    VORKERLAND_THEATRE_VP_PROVINCES,
)
from tools.builders.build_adiscord_new_states import (
    AFRELA_LEGACY_VICTORY_POINTS,
    CAPITALS,
    EXACT_LEGACY_FACTORY_STATE_IDS,
    LEGACY_STATE_PROFILES,
    LEGACY_OWNER_GAPS,
    LEGACY_OWNER_OVERRIDES,
    MINOR_VPS,
    NAM_COALITION_FRONT_RESOURCES,
    NAM_LEGACY_VICTORY_POINTS,
    SECONDARY_CENTRES,
    STATE_PROFILES,
    STATE_RESOURCES,
    STARTING_OWNERS,
    VORKERLAND_CENTRES,
    VORKERLAND_LEGACY_VICTORY_POINTS,
    VORKERLAND_LEGACY_PROFILES,
    VORKERLAND_MINOR_VPS,
    render_state,
    state_path,
)
from tools.builders.build_adiscord_ainholm_mandate import STATE_PROFILES as AINHOLM_STATE_PROFILES
from tools.builders.build_adiscord_northern_countries import COUNTRIES as NORTHERN_COUNTRIES, build_profiles as build_northern_profiles
from tools.builders.build_adiscord_inner_frontier_countries import (
    COUNTRIES as INNER_FRONTIER_COUNTRIES,
    build_profiles as build_inner_frontier_profiles,
)


_NORTHERN_PROFILES, _NORTHERN_PRINCIPAL_PROVINCES = build_northern_profiles()
_INNER_FRONTIER_PROFILES, _INNER_FRONTIER_PRINCIPAL_PROVINCES = build_inner_frontier_profiles()
NORTHERN_SETTLEMENT_STATES = {
    int(country["capital"])
    for country in NORTHERN_COUNTRIES.values()
} | {
    int(state_id)
    for country in NORTHERN_COUNTRIES.values()
    for state_id, _name, _value in country.get("secondary_vps", ())
}
INNER_FRONTIER_SETTLEMENT_STATES = {
    int(country["capital"])
    for country in INNER_FRONTIER_COUNTRIES.values()
} | {
    int(state_id)
    for country in INNER_FRONTIER_COUNTRIES.values()
    for state_id, _name, _value in country.get("secondary_vps", ())
}

APPROVED_NON_URBAN_SETTLEMENT_VPS = NON_URBAN_SETTLEMENT_VPS | frozenset(
    province_id
    for points in (
        *AFRELA_LEGACY_VICTORY_POINTS.values(),
        *NAM_LEGACY_VICTORY_POINTS.values(),
        *(profile["victory_points"] for profile in AINHOLM_STATE_PROFILES.values()),
    )
    for province_id, _value in points
) | frozenset(province_id for province_id, _value in VORKERLAND_CENTRES.values()) | frozenset(
    province_id for province_id, _value in VORKERLAND_MINOR_VPS.values()
) | frozenset(
    _NORTHERN_PRINCIPAL_PROVINCES[state_id] for state_id in NORTHERN_SETTLEMENT_STATES
) | frozenset(
    _INNER_FRONTIER_PRINCIPAL_PROVINCES[state_id] for state_id in INNER_FRONTIER_SETTLEMENT_STATES
) | VORKERLAND_THEATRE_VP_PROVINCES

EBA_EXPECTED_VPS = {
    197: {16623: 10},
    311: {5905: 1},
    312: {16637: 3},
    313: {16617: 3},
    314: {5405: 1},
}

EBA_EXPECTED_VP_NAMES = {
    16623: "Эберн",
    5905: "Фельден",
    16637: "Нойен",
    16617: "Эстервик",
    5405: "Линден",
}

EBA_EXPECTED_STATE_PROFILES = {
    197: {"population": 1_400_000, "category": "large_town", "infrastructure": 4, "civilian": 3, "military": 1, "air_base": 1, "supplies": 4.5},
    311: {"population": 950_000, "category": "town", "infrastructure": 3, "civilian": 1, "military": 0, "air_base": 0, "supplies": 2.5},
    312: {"population": 850_000, "category": "town", "infrastructure": 3, "civilian": 1, "military": 1, "air_base": 0, "supplies": 3.0},
    313: {"population": 750_000, "category": "town", "infrastructure": 3, "civilian": 1, "military": 0, "air_base": 0, "supplies": 3.0},
    314: {"population": 750_000, "category": "town", "infrastructure": 3, "civilian": 1, "military": 0, "air_base": 0, "supplies": 3.0},
}


ROOT = Path(__file__).resolve().parents[2]
ERRORS: list[str] = []
SETTLEMENT_TERRAINS = frozenset({"urban", "vorkernsberg"})


def check(condition: bool, message: str) -> None:
    if not condition:
        ERRORS.append(message)


def text(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig", errors="strict")


SOUTHERN_LOCALISATION_PATHS = tuple(
    ROOT / "localisation" / "russian" / filename
    for filename in (
        "countries_l_russian.yml",
        "parties_l_russian.yml",
        "nsb_characters_l_russian.yml",
        "ADISCORD_traits_l_russian.yml",
        "ADISCORD_ideas_l_russian.yml",
    )
)


def southern_localisation() -> str:
    return "\n".join(text(path) for path in SOUTHERN_LOCALISATION_PATHS)


def block(source: str, name: str) -> str:
    match = re.search(rf"(?m)^\s*{re.escape(name)}\s*=\s*\{{", source)
    if not match:
        ERRORS.append(f"missing scripted block {name}")
        return ""
    start = source.find("{", match.start())
    depth = 0
    for index in range(start, len(source)):
        if source[index] == "{":
            depth += 1
        elif source[index] == "}":
            depth -= 1
            if depth == 0:
                return source[start + 1:index]
    ERRORS.append(f"unterminated scripted block {name}")
    return ""


def event_block(source: str, event_id: str) -> str:
    match = re.search(
        rf"(?m)^\s*country_event\s*=\s*\{{\s*$"
        rf"(?:(?!^\s*country_event\s*=).)*?^\s*id\s*=\s*{re.escape(event_id)}\s*$",
        source,
        re.DOTALL,
    )
    if not match:
        ERRORS.append(f"missing country event {event_id}")
        return ""
    start = source.find("{", match.start())
    depth = 0
    for index in range(start, len(source)):
        if source[index] == "{":
            depth += 1
        elif source[index] == "}":
            depth -= 1
            if depth == 0:
                return source[start + 1:index]
    ERRORS.append(f"unterminated country event {event_id}")
    return ""


def building_level(source: str, name: str) -> int:
    match = re.search(rf"(?m)^\s*{re.escape(name)}\s*=\s*(\d+)", source)
    return int(match.group(1)) if match else 0


def state_profile(source: str) -> dict[str, int | float | str]:
    history = block(source, "history")
    buildings = block(history, "buildings")
    return {
        "population": int(re.search(r"(?m)^\s*manpower\s*=\s*(\d+)", source).group(1)),
        "category": re.search(r"(?m)^\s*state_category\s*=\s*(\w+)", source).group(1),
        "infrastructure": building_level(buildings, "infrastructure"),
        "civilian": building_level(buildings, "industrial_complex"),
        "military": building_level(buildings, "arms_factory"),
        "air_base": building_level(buildings, "air_base"),
        "supplies": float(re.search(r"(?m)^\s*local_supplies\s*=\s*([\d.]+)", source).group(1)),
    }


def normalized_builder_profile(state_id: int) -> dict[str, int | float | str]:
    profile = (
        LEGACY_STATE_PROFILES[state_id]
        if state_id in LEGACY_STATE_PROFILES
        else STATE_PROFILES[state_id]
    )
    return {
        "population": int(profile["population"]),
        "category": str(profile["category"]),
        "infrastructure": int(profile["infrastructure"]),
        "civilian": int(profile.get("civilian", profile.get("industry", 0))),
        "military": int(profile.get("military", 0)),
        "air_base": int(profile.get("air_base", 0)),
        "supplies": float(profile["supplies"]),
    }


def validate_states() -> None:
    localisation = "\n".join(text(path) for path in (ROOT / "localisation/russian").glob("*.yml"))
    province_terrain: dict[int, str] = {}
    province_kind: dict[int, str] = {}
    with (ROOT / "map/definition.csv").open(encoding="utf-8-sig") as handle:
        for line in handle:
            fields = line.rstrip("\r\n").split(";")
            if len(fields) >= 7 and fields[0].isdigit():
                province_terrain[int(fields[0])] = fields[6]
                province_kind[int(fields[0])] = fields[4]
    for state_id, owner in sorted(STARTING_OWNERS.items()):
        source = text(state_path(state_id))
        owner_match = re.search(r"(?m)^\s*owner\s*=\s*([A-Z0-9]{3})", source)
        check(bool(owner_match) and owner_match.group(1) == owner, f"state {state_id}: expected owner {owner}")
        check(bool(re.search(rf"(?m)^\s*add_core_of\s*=\s*{owner}\s*$", source)), f"state {state_id}: missing {owner} core")
        check(bool(re.search(r"(?m)^\s*state_category\s*=\s*\w+", source)), f"state {state_id}: missing state category")
        check(bool(re.search(r"(?m)^\s*manpower\s*=\s*\d+", source)), f"state {state_id}: missing manpower")
        check(bool(re.search(rf"(?m)^\s*STATE_{state_id}:\s*\".+\"", localisation)), f"state {state_id}: missing Russian name")
        if state_id in STATE_RESOURCES:
            resource_block = block(source, "resources")
            actual_resources = {
                resource: int(value)
                for resource, value in re.findall(r"(?m)^\s*([a-z_]+)\s*=\s*(\d+)\s*$", resource_block)
            }
            check(actual_resources == STATE_RESOURCES[state_id], f"state {state_id}: wrong resource deposit")

    southern_tags = {"KDR", "RHM", "SDR", "MZR", "KYZ", "SHL", "GLP", "AZH", "WEF"}
    resource_totals = {tag: 0 for tag in southern_tags}
    for state_id, resources in STATE_RESOURCES.items():
        owner = STARTING_OWNERS[state_id]
        check("coal" not in resources, f"{owner}: southern starting deposit must not use coal")
        if owner in resource_totals:
            resource_totals[owner] += sum(resources.values())
    for state_id, resources in NAM_COALITION_FRONT_RESOURCES.items():
        if state_id in STATE_RESOURCES:
            continue
        source = text(state_path(state_id))
        resource_block = block(source, "resources")
        actual_resources = {
            resource: int(value)
            for resource, value in re.findall(r"(?m)^\s*([a-z_]+)\s*=\s*(\d+)\s*$", resource_block)
        }
        check(actual_resources == resources, f"state {state_id}: wrong resource deposit")
        resource_totals["AZH"] += sum(resources.values())
    for tag, amount in resource_totals.items():
        check(4 <= amount <= 6, f"{tag}: expected a modest 4-6 starting resources, found {amount}")

    for state_id, owner in sorted(LEGACY_OWNER_GAPS.items()):
        source = text(state_path(state_id))
        check(bool(re.search(rf"(?m)^\s*owner\s*=\s*{owner}\s*$", source)), f"legacy state {state_id}: expected owner {owner}")
        check(bool(re.search(rf"(?m)^\s*add_core_of\s*=\s*{owner}\s*$", source)), f"legacy state {state_id}: missing {owner} core")

    for state_id, owner in sorted(LEGACY_OWNER_OVERRIDES.items()):
        source = text(state_path(state_id))
        check(bool(re.search(rf"(?m)^\s*owner\s*=\s*{owner}\s*$", source)), f"legacy state {state_id}: expected owner {owner}")
        check(bool(re.search(rf"(?m)^\s*add_core_of\s*=\s*{owner}\s*$", source)), f"legacy state {state_id}: missing {owner} core")

    for state_id in sorted(LEGACY_STATE_PROFILES):
        source = text(state_path(state_id))
        for scalar_name in (
            "manpower",
            "state_category",
            "buildings_max_level_factor",
            "local_supplies",
        ):
            declarations = re.findall(
                rf"(?m)^[ \t]*{re.escape(scalar_name)}[ \t]*=[ \t]*[^\s#]+[ \t]*$",
                source,
            )
            check(
                len(declarations) == 1,
                f"legacy state {state_id}: expected one {scalar_name} declaration, found {len(declarations)}",
            )

    vad_population_contract = {
        75: (9_500_000, "megalopolis", 5, 5, 3, 8.0),
        106: (3_800_000, "large_city", 3, 2, 2, 5.0),
        107: (1_200_000, "town", 1, 0, 0, 2.5),
        121: (3_000_000, "large_city", 3, 2, 0, 5.0),
    }
    check(
        sum(profile[0] for profile in vad_population_contract.values())
        == 17_500_000,
        "VAD: expected exact 17500000 population package",
    )
    for state_id, (
        population,
        category,
        civilian,
        military,
        air_base,
        supplies,
    ) in vad_population_contract.items():
        actual = state_profile(text(state_path(state_id)))
        check(
            (actual["population"], actual["category"]) == (population, category),
            f"VAD state {state_id}: expected population/category {population}/{category}",
        )
        check(
            (
                actual["civilian"],
                actual["military"],
                actual["air_base"],
                actual["supplies"],
            )
            == (civilian, military, air_base, supplies),
            f"VAD state {state_id}: factory, air-base, or supply package changed",
        )
        expected = normalized_builder_profile(state_id)
        check(
            (expected["population"], expected["category"], expected["supplies"])
            == (population, category, supplies),
            f"VAD state {state_id}: builder population/category/supply contract changed",
        )

    for state_id, province_id in ((200, 4443), (201, 12443)):
        actual = state_profile(text(state_path(state_id)))
        expected = normalized_builder_profile(state_id)
        check(
            actual == expected,
            f"WKR regional city state {state_id}: generated profile differs from its builder profile",
        )
        check(
            actual["category"] == "town",
            f"WKR regional city state {state_id}: expected town category",
        )
        check(
            province_terrain.get(province_id) == "urban",
            f"WKR regional city province {province_id}: expected urban terrain",
        )

    for state_id, expected_vps in sorted(VORKERLAND_LEGACY_VICTORY_POINTS.items()):
        source = text(state_path(state_id))
        actual_vps = {
            int(province_id): int(value)
            for province_id, value in re.findall(
                r"victory_points\s*=\s*\{\s*(\d+)\s+(\d+)\s*\}", source
            )
        }
        for province_id, value in expected_vps:
            check(
                actual_vps.get(province_id) == value,
                f"Vorkerland legacy state {state_id}: expected VP {province_id}:{value}",
            )

    vp_localisation_path = ROOT / "localisation/russian/victory_points_l_russian.yml"
    vp_localisation = text(vp_localisation_path)
    check(
        vp_localisation_path.read_bytes().startswith(b"\xef\xbb\xbf"),
        "Vorkerland VP localisation must use UTF-8 BOM",
    )
    package_states = {
        state_id
        for states in VORKERLAND_THEATRE_PACKAGES.values()
        for state_id in states
    }
    check(
        package_states == set(VORKERLAND_THEATRE_VICTORY_POINTS),
        "Vorkerland VP package states do not exactly cover the manifest",
    )
    for state_id, expected_vps in sorted(VORKERLAND_THEATRE_VICTORY_POINTS.items()):
        source = text(state_path(state_id))
        actual_vps = tuple(
            (int(province_id), int(value))
            for province_id, value in re.findall(
                r"victory_points\s*=\s*\{\s*(\d+)\s+(\d+)\s*\}", source
            )
        )
        check(
            actual_vps == expected_vps,
            f"Vorkerland theatre state {state_id}: expected exact VPs {expected_vps}, found {actual_vps}",
        )
        province_match = re.search(r"\bprovinces\s*=\s*\{([^}]*)\}", source, re.DOTALL)
        state_provinces = (
            {int(value) for value in re.findall(r"\d+", province_match.group(1))}
            if province_match
            else set()
        )
        check(bool(province_match), f"Vorkerland theatre state {state_id}: missing provinces")
        for province_id, _value in expected_vps:
            check(
                province_id in state_provinces,
                f"Vorkerland theatre state {state_id}: VP {province_id} is outside the state",
            )
            check(
                province_kind.get(province_id) == "land",
                f"Vorkerland theatre state {state_id}: VP {province_id} is not land",
            )
            matches = re.findall(
                rf'(?m)^\s*VICTORY_POINTS_{province_id}:(?:\d+)?\s*"([^"]*)"\s*$',
                vp_localisation,
            )
            check(
                len(matches) == 1,
                f"Vorkerland theatre VP {province_id}: expected one Russian name",
            )
        if state_id in STARTING_OWNERS:
            rendered_vps = tuple(
                (int(province_id), int(value))
                for province_id, value in re.findall(
                    r"victory_points\s*=\s*\{\s*(\d+)\s+(\d+)\s*\}",
                    render_state(state_id, STARTING_OWNERS[state_id]),
                )
            )
            check(
                rendered_vps == expected_vps,
                f"Vorkerland theatre generator state {state_id}: expected exact VPs {expected_vps}, found {rendered_vps}",
            )

    for package, states in VORKERLAND_THEATRE_PACKAGES.items():
        actual_total = sum(
            value
            for state_id in states
            for _province_id, value in VORKERLAND_THEATRE_VICTORY_POINTS[state_id]
        )
        check(
            actual_total == VORKERLAND_THEATRE_PACKAGE_TOTALS[package],
            f"Vorkerland package {package}: expected VP total {VORKERLAND_THEATRE_PACKAGE_TOTALS[package]}, found {actual_total}",
        )

    for province_id, expected_name in VORKERLAND_THEATRE_VP_NAME_OVERRIDES.items():
        matches = re.findall(
            rf'(?m)^\s*VICTORY_POINTS_{province_id}:(?:\d+)?\s*"([^"]*)"\s*$',
            vp_localisation,
        )
        check(
            matches == [expected_name],
            f"Vorkerland theatre VP {province_id}: expected Russian name {expected_name!r}, found {matches}",
        )
    for province_id in VORKERLAND_THEATRE_RETIRED_VP_IDS:
        check(
            not re.search(rf"(?m)^\s*VICTORY_POINTS_{province_id}:", vp_localisation),
            f"retired Vorkerland VP localisation remains: {province_id}",
        )
    state_40 = text(state_path(40))
    check("impassable = yes" in state_40, "Vorkerland state 40 must remain impassable")
    check(
        VORKERLAND_PROTECTED_LANDMARK_VPS
        == {UNITY_TOWER_STATE: ((UNITY_TOWER_PROVINCE, UNITY_TOWER_VALUE),)},
        "Unity Tower protected-landmark contract changed",
    )
    check(
        VORKERLAND_THEATRE_VICTORY_POINTS.get(UNITY_TOWER_STATE)
        == VORKERLAND_PROTECTED_LANDMARK_VPS[UNITY_TOWER_STATE],
        "Unity Tower must remain in the exact Vorkerland theatre VP manifest",
    )
    check(
        UNITY_TOWER_PROVINCE not in VORKERLAND_THEATRE_RETIRED_VP_IDS,
        "Unity Tower cannot be retired from the Vorkerland theatre",
    )
    check(
        VORKERLAND_THEATRE_VP_NAME_OVERRIDES.get(UNITY_TOWER_PROVINCE)
        == UNITY_TOWER_NAME,
        "Unity Tower must retain its protected Russian name",
    )
    check(
        re.findall(
            rf"victory_points\s*=\s*\{{\s*{UNITY_TOWER_PROVINCE}\s+(\d+)\s*\}}",
            state_40,
        )
        == [str(UNITY_TOWER_VALUE)],
        f"Vorkerland state {UNITY_TOWER_STATE} must retain Unity Tower VP "
        f"{UNITY_TOWER_PROVINCE}:{UNITY_TOWER_VALUE}",
    )

    for state_id in sorted(EXACT_LEGACY_FACTORY_STATE_IDS):
        source = text(state_path(state_id))
        actual = state_profile(source)
        expected = normalized_builder_profile(state_id)
        check(
            actual["category"] == expected["category"],
            f"legacy state {state_id}: expected exact category {expected['category']}, found {actual['category']}",
        )
        for key in ("civilian", "military"):
            check(
                actual[key] == expected[key],
                f"legacy state {state_id}: expected exact {key} level {expected[key]}, found {actual[key]}",
            )

    for state_id, expected_vps in EBA_EXPECTED_VPS.items():
        source = text(state_path(state_id))
        actual_vps = {
            int(province_id): int(value)
            for province_id, value in re.findall(
                r"victory_points\s*=\s*\{\s*(\d+)\s+(\d+)\s*\}", source
            )
        }
        for province_id, value in expected_vps.items():
            check(
                actual_vps.get(province_id) == value,
                f"EBA state {state_id}: expected VP {province_id}:{value}",
            )
        if state_id in STARTING_OWNERS:
            rendered_vps = {
                int(province_id): int(value)
                for province_id, value in re.findall(
                    r"victory_points\s*=\s*\{\s*(\d+)\s+(\d+)\s*\}",
                    render_state(state_id, STARTING_OWNERS[state_id]),
                )
            }
            for province_id, value in expected_vps.items():
                check(
                    rendered_vps.get(province_id) == value,
                    f"EBA generator state {state_id}: expected VP {province_id}:{value}",
                )

    actual_profiles: dict[int, dict[str, int | float | str]] = {}
    for state_id, expected_profile in EBA_EXPECTED_STATE_PROFILES.items():
        actual_profile = state_profile(text(state_path(state_id)))
        actual_profiles[state_id] = actual_profile
        check(
            actual_profile == expected_profile,
            f"EBA state {state_id}: expected profile {expected_profile}, found {actual_profile}",
        )
        check(
            normalized_builder_profile(state_id) == expected_profile,
            f"EBA builder state {state_id}: expected profile {expected_profile}",
        )
        if state_id in STARTING_OWNERS:
            rendered_profile = state_profile(
                render_state(state_id, STARTING_OWNERS[state_id])
            )
            check(
                rendered_profile == expected_profile,
                f"EBA generator state {state_id}: expected profile {expected_profile}, found {rendered_profile}",
            )

    check(
        sum(int(profile["population"]) for profile in actual_profiles.values()) == 4_700_000,
        "EBA: expected total population 4700000",
    )
    check(
        sum(int(profile["civilian"]) for profile in actual_profiles.values()) == 7,
        "EBA: expected seven civilian factories",
    )
    check(
        sum(int(profile["military"]) for profile in actual_profiles.values()) == 2,
        "EBA: expected two military factories",
    )
    check(
        sum(int(profile["air_base"]) for profile in actual_profiles.values()) == 1,
        "EBA: expected one air base",
    )
    check(
        sum(float(profile["supplies"]) for profile in actual_profiles.values()) == 16.0,
        "EBA: expected 16.0 total local supplies",
    )

    for province_id, expected_name in EBA_EXPECTED_VP_NAMES.items():
        pattern = rf'(?m)^\s*VICTORY_POINTS_{province_id}:\s*"([^"]*)"\s*$'
        matches = re.findall(pattern, localisation)
        check(
            len(matches) == 1,
            f"EBA VP {province_id}: expected one Russian localisation key",
        )
        if matches:
            check(
                matches[0] == expected_name,
                f"EBA VP {province_id}: expected name {expected_name!r}",
            )

    centres = {
        **CAPITALS,
        **SECONDARY_CENTRES,
        **MINOR_VPS,
        **VORKERLAND_CENTRES,
        **VORKERLAND_MINOR_VPS,
    }
    for state_id, (province_id, value) in centres.items():
        source = text(state_path(state_id))
        vp_pattern = rf"victory_points\s*=\s*\{{\s*{province_id}\s+{value}\s*\}}"
        if (
            province_terrain.get(province_id) in SETTLEMENT_TERRAINS
            or province_id in APPROVED_NON_URBAN_SETTLEMENT_VPS
        ):
            check(bool(re.search(vp_pattern, source)), f"state {state_id}: missing urban VP {province_id}")
            city_key = rf"(?m)^\s*VICTORY_POINTS_{province_id}:\s*\".+\""
            check(len(re.findall(city_key, localisation)) == 1, f"VP {province_id}: expected one Russian city name")
        else:
            check(not re.search(vp_pattern, source), f"state {state_id}: non-urban province {province_id} must not be a VP")

    for path in (ROOT / "history/states").glob("*.txt*"):
        source = text(path)
        for province_id in map(int, re.findall(r"victory_points\s*=\s*\{\s*(\d+)", source)):
            check(
                province_terrain.get(province_id) in SETTLEMENT_TERRAINS
                or province_id in APPROVED_NON_URBAN_SETTLEMENT_VPS,
                f"{path.name}: VP {province_id} is not urban or an approved settlement",
            )


def validate_countries() -> None:
    tags = text(ROOT / "common/country_tags/02_ADISCORD_southern_desert_tags.txt")
    characters = text(ROOT / "common/characters/ADISCORD_southern_desert_characters.txt")
    ideas = text(ROOT / "common/ideas/ADISCORD_southern_desert_ideas.txt")
    traits = text(ROOT / "common/country_leader/ADISCORD_southern_desert_traits.txt")
    portraits_gfx = text(ROOT / "interface/ADISCORD_southern_desert_portraits.gfx")
    localisation = southern_localisation()
    for localisation_path in SOUTHERN_LOCALISATION_PATHS:
        check(
            localisation_path.read_bytes().startswith(b"\xef\xbb\xbf"),
            f"shared southern localisation must use UTF-8 BOM: {localisation_path.name}",
        )
    for retired_name in (
        "Кадирский Караванный Союз",
        "Рахмийская Лига Колодцев",
        "Союз Сухого Русла",
        "Мазарский Водный Синдикат",
        "Кяризская Конфедерация",
        "Шахрабадская Лига",
        "Содружество Стеклянных Портов",
        "Ажарский Чёрный Бассейн",
        "Вольный Эфлорский Рубеж",
    ):
        check(retired_name not in localisation, f"retired country name remains visible: {retired_name}")

    expected = {
        "KDR": (241, 971, "KDR_Rashid_al_Kadir", "KDR_law_of_a_thousand_miles", "KDR_keeper_of_caravan_law"),
        "RHM": (253, 443, "RHM_Faris_Rahma", "RHM_cistern_parliament", "RHM_first_voice_of_cisterns"),
        "SDR": (260, 197, "SDR_Hamid_Sahr", "SDR_dry_river_patrols", "SDR_marshal_of_the_dry_bed"),
        "MZR": (275, 193, "MZR_Ration_Assembly", "MZR_common_water_charter", "MZR_stewards_of_common_wells"),
        "KYZ": (283, 1349, "KYZ_Qanat_Assembly", "KYZ_free_qanat_compact", "KYZ_voice_of_the_communes"),
        "SHL": (294, 1198, "SHL_Jalil_Nur", "SHL_nine_furnaces_compact", "SHL_mediator_of_nine_furnaces"),
        "GLP": (300, 492, "GLP_Miran_Veyr", "GLP_prismatic_trade_code", "GLP_broker_of_glass_ports"),
        "AZH": (69, 367, "AZH_Samir_Azhar", "AZH_black_basin_levy", "AZH_warden_of_the_black_basin"),
        "WEF": (174, 158, "WEF_Elina_Fenn", "WEF_frontier_municipalism", "WEF_mayor_of_the_last_bridge"),
    }
    political_profiles = {
        "KDR": ("chauvinism", "chauvinism_ideology"),
        "RHM": ("humanism", "humanism_ideology"),
        "SDR": ("pragmatism", "pragmatism_ideology"),
        "MZR": ("utilitarism", "utilitarism_ideology"),
        "KYZ": ("anarchism", "anarchism_ideology"),
        "SHL": ("hedonism", "aristocratic_hedonism"),
        "GLP": ("hedonism", "hedonism_ideology"),
        "AZH": ("etatism", "etatism_ideology"),
        "WEF": ("utilitarism", "utilitarism_ideology"),
    }
    portrait_profiles = {
        "KDR": ("GFX_portrait_KDR_Rashid_al_Kadir", "KDR/portrait_KDR_Rashid_al_Kadir.png"),
        "RHM": ("GFX_portrait_RHM_Faris_Rahma", "RHM/portrait_RHM_Faris_Rahma.png"),
        "SDR": ("GFX_portrait_SDR_Hamid_Sahr", "SDR/portrait_SDR_Hamid_Sahr.png"),
        "MZR": ("GFX_Portrait_Forul_Generic_7", None),
        "KYZ": ("GFX_Portrait_Forul_Generic_3", None),
        "SHL": ("GFX_portrait_SHL_Jalil_Nur", "SHL/portrait_SHL_Jalil_Nur.png"),
        "GLP": ("GFX_portrait_GLP_Miran_Veyr", "GLP/portrait_GLP_Miran_Veyr.png"),
        "AZH": ("GFX_portrait_AZH_Samir_Azhar", "AZH/portrait_AZH_Samir_Azhar.png"),
        "WEF": ("GFX_portrait_WEF_Elina_Fenn", "WEF/portrait_WEF_Elina_Fenn.png"),
    }
    idea_pictures = {
        "KDR": "PER_persepolis_idea",
        "RHM": "AFG_helmand_adopted_treaty",
        "SDR": "generic_fortify_the_borders",
        "MZR": "PER_food_for_all_idea",
        "KYZ": "PER_feat_of_engineering_idea",
        "SHL": "IRQ_state_company_for_iron_and_steel",
        "GLP": "CHI_china_merchant_group",
        "AZH": "generic_central_management",
        "WEF": "ger_rebuild_the_nation",
    }
    for tag, (capital, province, leader, idea, trait) in expected.items():
        check(bool(re.search(rf"(?m)^\s*{tag}\s*=\s*\"countries/{tag}\.txt\"", tags)), f"{tag}: missing country tag")
        check((ROOT / f"common/countries/{tag}.txt").is_file(), f"{tag}: missing country definition")
        histories = list((ROOT / "history/countries").glob(f"{tag} - *.txt"))
        check(len(histories) == 1, f"{tag}: expected one country history")
        if histories:
            history = text(histories[0])
            check(bool(re.search(rf"(?m)^\s*capital\s*=\s*{capital}\s*$", history)), f"{tag}: wrong capital")
            check(f'oob = "{tag}"' in history, f"{tag}: missing OOB")
            check(f"recruit_character = {leader}" in history, f"{tag}: missing leader recruitment")
            check(idea in history, f"{tag}: missing national spirit")
        leader_block = block(characters, leader)
        check(f"traits = {{ {trait} }}" in leader_block, f"{tag}: leader is missing unique trait {trait}")
        portrait, portrait_file = portrait_profiles[tag]
        check(f"large = {portrait}" in leader_block, f"{tag}: leader uses the wrong portrait")
        if portrait_file:
            portrait_pattern = (
                rf'name\s*=\s*"{re.escape(portrait)}"[\s\S]{{0,160}}?'
                rf'texturefile\s*=\s*"gfx/leaders/{re.escape(portrait_file)}"'
            )
            check(bool(re.search(portrait_pattern, portraits_gfx)), f"{tag}: missing portrait sprite {portrait}")
            portrait_path = ROOT / "gfx/leaders" / portrait_file
            check(portrait_path.is_file(), f"{tag}: missing portrait texture {portrait_file}")
            if portrait_path.is_file():
                with Image.open(portrait_path) as portrait_image:
                    check(portrait_image.size == (156, 210), f"{tag}: portrait {portrait_file} must be 156x210")
        idea_block = block(ideas, idea)
        check(bool(idea_block), f"{tag}: missing national spirit definition {idea}")
        check(
            bool(re.search(rf"(?m)^\s*picture\s*=\s*{re.escape(idea_pictures[tag])}\s*$", idea_block)),
            f"{tag}: national spirit uses the wrong vanilla picture",
        )
        check(bool(block(traits, trait)), f"{tag}: missing leader trait definition {trait}")
        oob_path = ROOT / f"history/units/{tag}.txt"
        check(oob_path.is_file(), f"{tag}: missing OOB file")
        if oob_path.is_file():
            check(bool(re.search(rf"\blocation\s*=\s*{province}\b", text(oob_path))), f"{tag}: OOB is outside its capital")
        for folder, size in (("", (82, 52)), ("medium", (41, 26)), ("small", (10, 7))):
            flag = ROOT / "gfx/flags" / folder / f"{tag}.tga"
            check(flag.is_file(), f"{tag}: missing {folder or 'large'} flag")
            if flag.is_file():
                with Image.open(flag) as image:
                    check(image.size == size, f"{tag}: {folder or 'large'} flag has size {image.size}, expected {size}")
                    check(image.mode == "RGBA", f"{tag}: {folder or 'large'} flag must be 32bpp RGBA, got {image.mode}")
        for key in (
            tag,
            f"{tag}_DEF",
            f"{tag}_ADJ",
            f"{tag}_{political_profiles[tag][0]}",
            f"{tag}_{political_profiles[tag][0]}_party",
            leader,
            f"{leader}_desc",
            idea,
            f"{idea}_desc",
            trait,
            f"{trait}_desc",
        ):
            check(bool(re.search(rf"(?m)^\s*{re.escape(key)}:\s*\"", localisation)), f"{tag}: missing localisation {key}")

    for tag, (government, leader_ideology) in political_profiles.items():
        leader = expected[tag][2]
        history_path = next((ROOT / "history/countries").glob(f"{tag} - *.txt"))
        history = text(history_path)
        check(
            bool(re.search(rf"(?m)^\s*ruling_party\s*=\s*{government}\s*$", history)),
            f"{tag}: expected non-technocratic starting government {government}",
        )
        check(
            "technocracy" not in history,
            f"{tag}: technocracy remains in starting political setup",
        )
        popularities = {
            ideology: int(value)
            for ideology, value in re.findall(r"(?m)^\s*([a-z_]+)\s*=\s*(\d+)\s*$", block(history, "set_popularities"))
        }
        check(sum(popularities.values()) == 100, f"{tag}: starting popularities do not sum to 100")
        check(
            popularities.get(government, 0) == max(popularities.values(), default=0),
            f"{tag}: ruling ideology is not the most popular starting ideology",
        )
        check(
            bool(re.search(rf"(?m)^\s*ideology\s*=\s*{leader_ideology}\s*$", block(characters, leader))),
            f"{tag}: leader ideology does not match the replacement government",
        )


def validate_news_settings() -> None:
    superevents = text(ROOT / "common/scripted_guis/superevents.txt")
    effects = text(ROOT / "common/scripted_effects/ADISCORD_vorkerland_collapse_map_effects.txt")
    news = text(ROOT / "events/ADISCORD_news.txt")
    localisation = southern_localisation()

    for obsolete in (
        "common/decisions/categories/ADISCORD_news_settings_categories.txt",
        "common/decisions/ADISCORD_news_settings_anchor.txt",
        "common/decisions/ADISCORD_news_settings_decisions.txt",
        "common/scripted_guis/ADISCORD_news_settings_scripted_gui.txt",
        "common/scripted_triggers/ADISCORD_news_settings_triggers.txt",
        "interface/ADISCORD_news_settings.gui",
    ):
        check(not (ROOT / obsolete).exists(), f"news settings: obsolete file must be removed: {obsolete}")

    combined = "\n".join((superevents, effects, news, localisation))
    for kind in ("major", "local"):
        disabled_flag = f"ADISCORD_{kind}_news_disabled"
        enabled_trigger = f"ADISCORD_{kind}_news_enabled"
        check(disabled_flag not in combined, f"news settings: obsolete country flag remains: {disabled_flag}")
        check(enabled_trigger not in combined, f"news settings: obsolete scripted trigger remains: {enabled_trigger}")
        for key in (f"ADISCORD_{kind}_news_checkbox", f"ADISCORD_{kind}_news_checkbox_tt"):
            check(not re.search(rf"(?m)^\s*{key}:\s*\"", localisation), f"news settings: obsolete localisation remains: {key}")


def validate_vorkerland_expansion() -> None:
    effects = text(ROOT / "common/scripted_effects/ADISCORD_vorkerland_collapse_effects.txt")
    maps = text(ROOT / "common/scripted_effects/ADISCORD_vorkerland_collapse_map_effects.txt")
    phase_effects = text(ROOT / "common/scripted_effects/ADISCORD_vorkerland_phase_effects.txt")
    phase_events = text(ROOT / "events/ADISCORD_vorkerland_phase_events.txt")
    expansion_assignments = {
        "tva": ("TVA", {324}),
        "riv": ("RIV", {308}),
        "rev": ("REV", {323}),
        "osv": ("OSV", {318, 320}),
    }
    for setup_name, (tag, state_ids) in expansion_assignments.items():
        setup = block(effects, f"ADISCORD_vorkerland_setup_{setup_name}")
        for state_id in sorted(state_ids):
            check(
                f"transfer_state = {state_id}" in setup,
                f"{tag} setup: missing assigned expansion state {state_id}",
            )
            check(
                bool(re.search(rf"\b{state_id}\s*=\s*\{{\s*add_core_of\s*=\s*{tag}", setup)),
                f"{tag} setup: missing core for state {state_id}",
            )

    # A central victory records the surviving wartime claimant, then the guarded
    # phase controller forms final WRK. Keep direct map-paint forbidden here so
    # generated expansion-state assignments cannot be bypassed by an outcome.
    winner_paths = (
        (
            "ADISCORD_vorkerland_apply_worker_map",
            "WKR",
            "ADISCORD_vorkerland_worker_won",
            "ADISCORD_vorkerland_form_wrk_from_wkr",
        ),
        (
            "ADISCORD_vorkerland_apply_vlad_map",
            "VAD",
            "ADISCORD_vorkerland_vlad_won",
            "ADISCORD_vorkerland_form_wrk_from_vad",
        ),
        (
            "ADISCORD_vorkerland_apply_dorian_map",
            "TVA",
            "ADISCORD_vorkerland_dorian_won",
            "ADISCORD_vorkerland_form_wrk_from_tva",
        ),
    )
    finalizer = block(phase_effects, "ADISCORD_vorkerland_finalize_reunified_wrk")
    for map_name, winner_tag, victory_flag, formation_effect in winner_paths:
        winner = block(maps, map_name)
        for required in ("ADISCORD_vorkerland_begin_reunification = yes",):
            check(required in winner, f"{map_name}: missing phase handoff token {required}")
        for forbidden in (
            "set_global_flag = ADISCORD_vorkerland_central_war_finished",
            f"set_global_flag = {victory_flag}",
            "victory_superevent = yes",
        ):
            check(forbidden not in winner, f"{map_name}: premature victory token {forbidden}")
        check(
            f"set_global_flag = {victory_flag}" in finalizer,
            f"verified finalizer does not record {victory_flag}",
        )
        check(
            bool(
                re.search(
                    rf"\b{winner_tag}\s*=\s*\{{.*?"
                    r"set_country_flag\s*=\s*ADISCORD_vorkerland_central_unifier",
                    winner,
                    re.DOTALL,
                )
            ),
            f"{map_name}: missing central-unifier marker for wartime {winner_tag}",
        )
        formation = block(phase_effects, formation_effect)
        for required in (
            f"change_tag_from = {winner_tag}",
            "ADISCORD_vorkerland_finalize_wrk_formation = yes",
        ):
            check(required in formation, f"{formation_effect}: missing final-WRK token {required}")
        for forbidden in ("transfer_state", "annex_country", "puppet =", "set_autonomy"):
            check(forbidden not in winner, f"{map_name}: central victory must not use {forbidden}")

    begin_reunification = block(phase_effects, "ADISCORD_vorkerland_begin_reunification")
    for required in (
        "has_global_flag = ADISCORD_vorkerland_phase_central_showdown",
        "has_global_flag = ADISCORD_vorkerland_central_showdown_started",
        "ADISCORD_vorkerland_central_showdown_edges_verified = yes",
        "NOT = { has_global_flag = ADISCORD_vorkerland_central_showdown_launch_failed }",
        "ADISCORD_vorkerland_has_single_surviving_claimant = yes",
        "ADISCORD_vorkerland_set_phase_reunification = yes",
        "country_event = { id = ADISCORD_vorkerland_phase.6 days = 1 }",
    ):
        check(required in begin_reunification, f"reunification phase handoff is missing {required}")

    phase_six = event_block(phase_events, "ADISCORD_vorkerland_phase.6")
    for _map_name, winner_tag, _victory_flag, formation_effect in winner_paths:
        check(
            bool(
                re.search(
                    rf"\b{winner_tag}\s*=\s*\{{.*?{re.escape(formation_effect)}\s*=\s*yes"
                    r".*?country_event\s*=\s*\{\s*id\s*=\s*ADISCORD_vorkerland_phase\.7\s+days\s*=\s*1\s*\}",
                    phase_six,
                    re.DOTALL,
                )
            ),
            f"phase.6 does not form and verify final WRK from surviving {winner_tag}",
        )


def main() -> int:
    validate_states()
    validate_countries()
    validate_news_settings()
    validate_vorkerland_expansion()
    if ERRORS:
        print(f"New-state validation failed: {len(ERRORS)} error(s)")
        for error in ERRORS:
            print(f"- {error}")
        return 1
    print("New-state validation passed: 100 rebuilt states, 9 microstates with unique spirits/leader traits, obsolete news settings removed, 5 legacy owner gaps and 5-state Doctor Worx expansion.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
