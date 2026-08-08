#!/usr/bin/env python3
"""Populate the empty belt between Itora, Vorkerland and the Exclusion Zone.

The province lists in states 89, 126, 133-163, 179 and 223 remain
authoritative.  This follow-up owns only their starting countries, population,
industry, resources, claims, victory points, OOB placement and flags.

The western continent (states 474-550) is intentionally outside this builder.
"""

from __future__ import annotations

import argparse
import math
import re
from collections import Counter
from pathlib import Path

from PIL import Image

from tools.builders.build_adiscord_northern_countries import (
    distribute_levels,
    format_provinces,
    largest_remainder,
    load_definition,
    load_pixel_areas,
    load_positions,
    regiment_block,
    render_flag,
)
from tools.lib.paths import repository_root


ROOT = repository_root()
STATE_DIR = ROOT / "history" / "states"
UNIT_DIR = ROOT / "history" / "units"
FLAG_DIR = ROOT / "gfx" / "flags"
VP_LOCALISATION = ROOT / "localisation" / "russian" / "ADISCORD_inner_frontier_victory_points_l_russian.yml"
POPULATION_MARKER = "# Populated by tools/build_adiscord_inner_frontier_countries.py"
PROTECTORATE_TAG = "WCG"
PROTECTORATE_SUCCESSORS = {"KRM", "LMN"}


COUNTRIES: dict[str, dict[str, object]] = {
    "BOR": {
        "states": (89, 126, 135, 139, 140, 142, 143), "capital": 140,
        "capital_name": "Борея", "secondary_vps": ((89, "Иторские Ворота", 3),),
        "population": 3_600_000, "civilian": 8, "military": 4,
        "infrastructure": 3, "air_bases": 1,
        "resources": {"steel": 8, "coal": 5, "oil": 3},
        "divisions": 4, "unit_type": "infantry",
        "colors": ((64, 105, 124), (226, 226, 196), (172, 76, 58)),
    },
    "DOL": {
        "states": (133, 136, 137, 138, 141), "capital": 138,
        "capital_name": "Дольн", "population": 2_400_000,
        "civilian": 5, "military": 3, "infrastructure": 2, "air_bases": 0,
        "resources": {"coal": 5, "aluminium": 4},
        "divisions": 3, "unit_type": "ADISCORD_militia",
        "colors": ((91, 117, 75), (219, 205, 157), (78, 67, 98)),
    },
    "RIN": {
        "states": (134, 146, 147, 148, 149, 150), "capital": 149,
        "capital_name": "Рина", "secondary_vps": ((147, "Палатинский Двор", 3),),
        "population": 3_100_000, "civilian": 6, "military": 5,
        "infrastructure": 3, "air_bases": 1,
        "resources": {"steel": 8, "chromium": 4, "oil": 2},
        "divisions": 5, "unit_type": "infantry",
        "colors": ((102, 48, 61), (220, 190, 133), (55, 66, 79)),
    },
    "KRM": {
        "states": (151, 156, 161, 162, 163), "capital": 161,
        "capital_name": "Кремень", "population": 3_300_000,
        "civilian": 7, "military": 4, "infrastructure": 3, "air_bases": 1,
        "resources": {"tungsten": 8, "steel": 6, "coal": 6},
        "divisions": 4, "unit_type": "infantry",
        "colors": ((83, 78, 69), (205, 180, 116), (64, 108, 103)),
    },
    "LMN": {
        "states": (157, 158, 159, 160, 223), "capital": 159,
        "capital_name": "Леман", "population": 1_250_000,
        "civilian": 2, "military": 3, "infrastructure": 2, "air_bases": 0,
        "resources": {"chromium": 3, "coal": 2},
        "divisions": 3, "unit_type": "infantry",
        "colors": ((59, 70, 68), (192, 179, 132), (137, 55, 47)),
    },
    "RLY": {
        "states": (179,), "capital": 179,
        "capital_name": "Релейн", "population": 180_000,
        "civilian": 2, "military": 1, "infrastructure": 3, "air_bases": 0,
        "resources": {"aluminium": 3, "oil": 2, "coal": 2},
        "divisions": 1, "unit_type": "ADISCORD_militia",
        "colors": ((45, 78, 73), (210, 198, 150), (156, 68, 50)),
    },
}


EXPECTED_STATES = {
    89, 126,
    *range(133, 144),
    *range(146, 152),
    156, 157, 158, 159, 161, 162, 163,
    160, 179, 223,
}
STATE_OWNER = {
    state_id: tag
    for tag, profile in COUNTRIES.items()
    for state_id in profile["states"]
}
STARTING_OWNER = {
    state_id: PROTECTORATE_TAG if successor in PROTECTORATE_SUCCESSORS else successor
    for state_id, successor in STATE_OWNER.items()
}
CLAIMS_BY_STATE = {
    134: ("MON",),
    147: ("MON",),
    179: ("IRT",),
}
if set(STATE_OWNER) != EXPECTED_STATES:
    raise RuntimeError(
        f"inner-frontier coverage mismatch: missing={sorted(EXPECTED_STATES-set(STATE_OWNER))}, "
        f"unexpected={sorted(set(STATE_OWNER)-EXPECTED_STATES)}"
    )
if len(STATE_OWNER) != sum(len(profile["states"]) for profile in COUNTRIES.values()):
    raise RuntimeError("an inner-frontier state is assigned more than once")
if EXPECTED_STATES & set(range(474, 551)):
    raise RuntimeError("the inner-frontier builder must never touch the western continent")


def state_path(state_id: int) -> Path:
    matches = sorted(STATE_DIR.glob(f"{state_id}-*.txt"))
    if len(matches) != 1:
        raise RuntimeError(f"state {state_id}: expected one file, found {len(matches)}")
    return matches[0]


def parse_state(path: Path) -> tuple[int, tuple[int, ...]]:
    source = path.read_text(encoding="utf-8-sig", errors="strict")
    state_match = re.search(r"\bid\s*=\s*(\d+)", source)
    province_match = re.search(r"\bprovinces\s*=\s*\{([^}]*)\}", source, re.DOTALL)
    if not state_match or not province_match:
        raise RuntimeError(f"{path.relative_to(ROOT)} lacks id or provinces")
    return (
        int(state_match.group(1)),
        tuple(int(value) for value in re.findall(r"\d+", province_match.group(1))),
    )


def build_profiles() -> tuple[dict[int, dict[str, object]], dict[int, int]]:
    color_to_province, details = load_definition()
    areas = load_pixel_areas(color_to_province)
    positions = load_positions()
    shells = {state_id: parse_state(state_path(state_id))[1] for state_id in EXPECTED_STATES}
    principal_provinces: dict[int, int] = {}
    state_pixels: dict[int, int] = {}
    for state_id, provinces in shells.items():
        state_pixels[state_id] = sum(areas[province_id] for province_id in provinces)
        urban = [
            province_id
            for province_id in provinces
            if details[province_id]["terrain"] == "urban" and province_id in positions
        ]
        available = urban or [province_id for province_id in provinces if province_id in positions]
        if not available:
            principal_provinces[state_id] = min(provinces)
            continue
        center_x = sum(positions[p][0] * areas[p] for p in available if p in positions) / sum(
            areas[p] for p in available if p in positions
        )
        center_y = sum(positions[p][1] * areas[p] for p in available if p in positions) / sum(
            areas[p] for p in available if p in positions
        )
        principal_provinces[state_id] = min(
            available,
            key=lambda p: ((positions[p][0] - center_x) ** 2 + (positions[p][1] - center_y) ** 2, -areas[p], p),
        )

    profiles: dict[int, dict[str, object]] = {}
    for tag, country in COUNTRIES.items():
        states = list(country["states"])
        capital = int(country["capital"])
        weights = {
            state_id: math.sqrt(state_pixels[state_id]) * (2.3 if state_id == capital else 1.0)
            for state_id in states
        }
        populations = largest_remainder(int(country["population"]), weights)
        ranking = [capital] + sorted((state_id for state_id in states if state_id != capital), key=lambda state_id: (-populations[state_id], state_id))
        civilians = distribute_levels(int(country["civilian"]), ranking, 3)
        military = distribute_levels(int(country["military"]), ranking, 3)
        air_bases = distribute_levels(int(country["air_bases"]), ranking, 2)
        resources_by_state: dict[int, Counter[str]] = {state_id: Counter() for state_id in states}
        resource_ranking = sorted(states, key=lambda state_id: (-state_pixels[state_id], state_id))
        for resource_index, (resource, total) in enumerate(country["resources"].items()):
            deposits = min(len(resource_ranking), max(1, min(3, int(total) // 3)))
            targets = [resource_ranking[(resource_index + offset) % len(resource_ranking)] for offset in range(deposits)]
            for state_id, amount in largest_remainder(int(total), {state_id: 1.0 for state_id in targets}).items():
                resources_by_state[state_id][resource] += amount

        vp_values: dict[int, tuple[str, int]] = {
            capital: (str(country["capital_name"]), 5)
        }
        for state_id, name, value in country.get("secondary_vps", ()):
            vp_values[int(state_id)] = (str(name), int(value))

        for state_id in states:
            population = populations[state_id]
            if state_id == capital:
                category = "large_town" if population >= 750_000 else "town"
            elif population >= 650_000:
                category = "town"
            else:
                category = "rural"
            infrastructure = min(5, int(country["infrastructure"]) + (1 if state_id == capital else 0))
            factories = civilians[state_id] + military[state_id]
            profiles[state_id] = {
                "owner": STARTING_OWNER[state_id],
                "successor": tag,
                "population": population,
                "category": category,
                "infrastructure": infrastructure,
                "civilian": civilians[state_id],
                "military": military[state_id],
                "air_base": air_bases[state_id],
                "resources": dict(resources_by_state[state_id]),
                "vp": vp_values.get(state_id),
                "vp_province": principal_provinces[state_id],
                "claims": CLAIMS_BY_STATE.get(state_id, ()),
                "local_supplies": round(min(7.0, 0.8 + infrastructure * 0.55 + factories * 0.20), 1),
                "provinces": shells[state_id],
            }
    return profiles, principal_provinces


def render_state(state_id: int, profile: dict[str, object]) -> str:
    history = [
        "\thistory = {",
        f"\t\towner = {profile['owner']}",
        f"\t\tadd_core_of = {profile['owner']}",
    ]
    if profile["successor"] != profile["owner"]:
        history.append(f"\t\tadd_core_of = {profile['successor']}")
    history.extend(f"\t\tadd_claim_by = {tag}" for tag in profile["claims"])
    if profile["vp"]:
        _name, value = profile["vp"]
        history.append(f"\t\tvictory_points = {{ {profile['vp_province']} {value} }}")
    history.extend(("\t\tbuildings = {", f"\t\t\tinfrastructure = {profile['infrastructure']}"))
    for key, field in (("industrial_complex", "civilian"), ("arms_factory", "military"), ("air_base", "air_base")):
        if profile[field]:
            history.append(f"\t\t\t{key} = {profile[field]}")
    history.extend(("\t\t}", "\t}"))

    resources: list[str] = []
    if profile["resources"]:
        resources.append("\tresources = {")
        for resource, amount in sorted(profile["resources"].items()):
            resources.append(f"\t\t{resource} = {amount}")
        resources.append("\t}")

    return "\n".join([
        POPULATION_MARKER,
        "state = {",
        f"\tid = {state_id}",
        f'\tname = "STATE_{state_id}"',
        f"\tmanpower = {profile['population']}",
        f"\tstate_category = {profile['category']}",
        *history,
        "\tprovinces = {",
        format_provinces(profile["provinces"]),
        "\t}",
        *resources,
        "\tbuildings_max_level_factor = 1.000",
        f"\tlocal_supplies = {profile['local_supplies']:.1f}",
        "}",
        "",
    ])


def render_oob(tag: str, country: dict[str, object], principal_provinces: dict[int, int]) -> str:
    states = [int(country["capital"])] + [int(state_id) for state_id in country["states"] if state_id != country["capital"]]
    unit_type = str(country["unit_type"])
    template = "Палатинская линейная дивизия" if tag == "RIN" else "Фильтрационный батальон" if tag == PROTECTORATE_TAG else "Пограничная бригада" if unit_type == "infantry" else "Поселенческая дружина"
    regiment_count = 5 if tag == "RIN" else 4 if unit_type == "infantry" else 3
    lines = [
        "division_template = {",
        f'\tname = "{template}"',
        "\tregiments = {",
        *regiment_block(unit_type, regiment_count),
    ]
    if tag == "RIN":
        lines.append("\t\tartillery = { x = 2 y = 1 }")
    lines.extend(("\t}", "}", "units = {"))
    for index in range(int(country["divisions"])):
        lines.append(
            f'\tdivision = {{ division_name = {{ is_name_ordered = yes name_order = {index + 1} }} '
            f'location = {principal_provinces[states[index % len(states)]]} division_template = "{template}" '
            f"start_experience_factor = {0.25 if tag == 'RIN' else 0.15:.2f} "
            f"start_equipment_factor = {0.86 if tag == 'RIN' else 0.72:.2f} }}"
        )
    lines.extend(("}", ""))
    return "\n".join(lines)


def protectorate_profile() -> dict[str, object]:
    return {
        "states": tuple(COUNTRIES["KRM"]["states"]) + tuple(COUNTRIES["LMN"]["states"]),
        "capital": COUNTRIES["LMN"]["capital"],
        "divisions": 5,
        "unit_type": "infantry",
    }


def write_flags() -> None:
    sizes = ((FLAG_DIR, (82, 52)), (FLAG_DIR / "medium", (41, 26)), (FLAG_DIR / "small", (10, 7)))
    for style, (tag, country) in enumerate(COUNTRIES.items()):
        base = render_flag(tag, country["colors"], style)
        for directory, size in sizes:
            directory.mkdir(parents=True, exist_ok=True)
            image = base if size == base.size else base.resize(size, Image.Resampling.LANCZOS)
            image.save(directory / f"{tag}.tga")
    gate_colors = ((40, 43, 39), (190, 145, 48), (112, 44, 38))
    gate = render_flag(PROTECTORATE_TAG, gate_colors, 5)
    for directory, size in sizes:
        image = gate if size == gate.size else gate.resize(size, Image.Resampling.LANCZOS)
        image.save(directory / f"{PROTECTORATE_TAG}.tga")


def apply() -> None:
    profiles, principal_provinces = build_profiles()
    for state_id, profile in sorted(profiles.items()):
        state_path(state_id).write_text(render_state(state_id, profile), encoding="utf-8", newline="\n")
    for tag, country in COUNTRIES.items():
        (UNIT_DIR / f"{tag}.txt").write_text(render_oob(tag, country, principal_provinces), encoding="utf-8", newline="\n")
    gate_country = protectorate_profile()
    (UNIT_DIR / f"{PROTECTORATE_TAG}.txt").write_text(
        render_oob(PROTECTORATE_TAG, gate_country, principal_provinces),
        encoding="utf-8",
        newline="\n",
    )
    localisation = ["\ufeffl_russian:"]
    for country in COUNTRIES.values():
        capital_state = int(country["capital"])
        localisation.append(f' VICTORY_POINTS_{principal_provinces[capital_state]}: "{country["capital_name"]}"')
        for state_id, name, _value in country.get("secondary_vps", ()):
            localisation.append(f' VICTORY_POINTS_{principal_provinces[int(state_id)]}: "{name}"')
    VP_LOCALISATION.write_text("\n".join(localisation) + "\n", encoding="utf-8", newline="\n")
    write_flags()
    print(f"Applied {len(profiles)} populated inner-frontier states, {len(COUNTRIES) + 1} OOBs and {(len(COUNTRIES) + 1) * 3} flags.")


def print_summary() -> None:
    profiles, _principal = build_profiles()
    for tag, country in COUNTRIES.items():
        states = [profiles[int(state_id)] for state_id in country["states"]]
        resources = Counter()
        for state in states:
            resources.update(state["resources"])
        print(
            f"{tag}: states={len(states)} population={sum(int(state['population']) for state in states):,} "
            f"factories={sum(int(state['civilian']) for state in states)}+"
            f"{sum(int(state['military']) for state in states)} divisions={country['divisions']} "
            f"resources={dict(sorted(resources.items()))}"
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_mutually_exclusive_group()
    actions.add_argument("--check", action="store_true", help="validate current generated outputs (default)")
    actions.add_argument("--apply", action="store_true", help="write states, OOBs, victory-point localisation and flags")
    args = parser.parse_args()
    if args.apply:
        print_summary()
        apply()
        return 0
    from tools.validators.validate_adiscord_inner_frontier_countries import main as validate_main

    return validate_main()


if __name__ == "__main__":
    raise SystemExit(main())
