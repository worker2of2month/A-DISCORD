#!/usr/bin/env python3
"""Validate the populated northern-country contract."""

from __future__ import annotations

import re
import sys
from collections import Counter
from pathlib import Path

from PIL import Image

_REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
if str(_REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPOSITORY_ROOT))

try:
    from tools.builders.build_adiscord_northern_countries import (
        COUNTRIES,
        EXPECTED_STATES,
        FLAG_DIR,
        ROOT,
        VP_LOCALISATION,
        build_profiles,
        render_oob,
        render_state,
        state_path,
    )
except ModuleNotFoundError:
    from builders.build_adiscord_northern_countries import (
        COUNTRIES,
        EXPECTED_STATES,
        FLAG_DIR,
        ROOT,
        VP_LOCALISATION,
        build_profiles,
        render_oob,
        render_state,
        state_path,
    )


EXPECTED_IDEAS = {
    "BRN": ("BRN_polar_signal_line",),
    "KHV": ("KHV_geothermal_colleges",),
    "ELN": ("ELN_census_engines",),
    "HON": ("HON_civic_compact",),
    "SKN": ("SKN_reserve_districts",),
    "LYS": ("LYS_bonded_warehouses",),
    "VES": ("VES_border_charters",),
    "MON": (
        "MON_throne_of_fifteen_crowns",
        "MON_imperial_general_staff",
        "MON_arsenal_belt",
        "MON_hierarchy_of_peoples",
    ),
}

EXPECTED_TRAITS = {
    "KRL": "KRL_winter_crown",
    "HON": "HON_first_citizen",
    "SKN": "SKN_iron_marshal",
    "VES": "VES_warden_of_western_gates",
    "MON": "MON_emperor_of_the_northern_marches",
}

LEADERS = {
    "BRN": "BRN_Emilia_Brandt",
    "KRL": "KRL_Edvard_Karel",
    "VRA": "VRA_Alrik_Varn",
    "FRS": "FRS_Mikael_Frost",
    "KHV": "KHV_Ilva_Havren",
    "SRV": "SRV_Eira_Sarven",
    "ELN": "ELN_Taal_Elander",
    "AUR": "AUR_Sofia_Aurell",
    "HON": "HON_Honter_Woke",
    "SVL": "SVL_Marta_Seval",
    "NVR": "NVR_Leif_Norven",
    "SKN": "SKN_Ren_Skad",
    "TMR": "TMR_Mira_Timer",
    "LYS": "LYS_Cassian_Lys",
    "KDL": "KDL_Oren_Kadel",
    "VES": "VES_Oskar_Vest",
    "DRV": "DRV_Council_of_Free_Valleys",
    "ORV": "ORV_Anton_Orval",
    "ARS": "ARS_Lina_Arsal",
    "VLD": "VLD_Irma_Vald",
    "MON": "MON_Marius_II_Arken",
}


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8-sig", errors="strict")


def named_history(tag: str) -> Path | None:
    matches = sorted((ROOT / "history" / "countries").glob(f"{tag} -*.txt"))
    return matches[0] if len(matches) == 1 else None


def owner_totals(tag: str) -> tuple[int, int, int]:
    population = civilian = military = 0
    for path in (ROOT / "history" / "states").glob("*.txt"):
        source = path.read_text(encoding="utf-8-sig", errors="strict")
        if not re.search(rf"(?m)^\s*owner\s*=\s*{tag}\s*$", source):
            continue
        manpower = re.search(r"\bmanpower\s*=\s*(\d+)", source)
        population += int(manpower.group(1)) if manpower else 0
        for key, counter in (("industrial_complex", "civilian"), ("arms_factory", "military")):
            match = re.search(rf"(?m)^\s*{key}\s*=\s*(\d+)", source)
            if match and counter == "civilian":
                civilian += int(match.group(1))
            elif match:
                military += int(match.group(1))
    return population, civilian, military


def validate() -> list[str]:
    issues: list[str] = []
    profiles, principal_provinces = build_profiles()
    if set(profiles) != EXPECTED_STATES:
        issues.append("generated profile coverage does not match states 331-473")

    expected_split_territories = {
        "KRL": {335, 336, 339, 345, 349, 353, 362},
        "VRA": {341, 347},
        "HON": {376, 382, 388, 392, 396, 397, 400},
        "SVL": {360},
        "KHV": {346, 348, 354, 355},
        "SRV": {364, 368, 375, 386, 405},
        "LYS": {394, 402, 408, 412, 415, 420, 422, 424, 432, 435, 437, 442, 447, 452},
        "KDL": {427, 446, 457},
        "ORV": {426, 436, 454, 455},
        "ARS": {441, 449},
        "VLD": {460, 467, 472},
    }
    for tag, expected_states in expected_split_territories.items():
        actual_states = set(COUNTRIES[tag]["states"])
        if actual_states != expected_states:
            issues.append(f"{tag} expected states {sorted(expected_states)}, found {sorted(actual_states)}")

    preserved_split_totals = {
        ("KRL", "VRA"): (3_800_000, 7, 4, 4),
        ("HON", "SVL"): (4_200_000, 8, 4, 5),
        ("KHV", "SRV"): (2_400_000, 4, 3, 3),
        ("LYS", "KDL"): (3_500_000, 7, 3, 4),
        ("ORV", "ARS", "VLD"): (2_455_204, 5, 3, 3),
    }
    for tags, expected in preserved_split_totals.items():
        actual = (
            sum(int(COUNTRIES[tag]["population"]) for tag in tags),
            sum(int(COUNTRIES[tag]["civilian"]) for tag in tags),
            sum(int(COUNTRIES[tag]["military"]) for tag in tags),
            sum(int(COUNTRIES[tag]["divisions"]) for tag in tags),
        )
        if actual != expected:
            issues.append(f"split balance for {'/'.join(tags)} expected {expected}, found {actual}")
    if 457 in set(COUNTRIES["MON"]["states"]) or 457 not in set(COUNTRIES["KDL"]["states"]):
        issues.append("state 457 must belong to KDL rather than MON")

    tags_source = read("common/country_tags/04_ADISCORD_northern_countries_tags.txt")
    characters = read("common/characters/ADISCORD_northern_characters.txt")
    traits = read("common/country_leader/ADISCORD_northern_traits.txt")
    ideas = read("common/ideas/ADISCORD_northern_ideas.txt")
    portraits = read("interface/ADISCORD_northern_portraits.gfx")
    country_loc_path = ROOT / "localisation" / "russian" / "ADISCORD_northern_countries_l_russian.yml"
    country_loc = country_loc_path.read_text(encoding="utf-8-sig", errors="strict")
    vp_loc = VP_LOCALISATION.read_text(encoding="utf-8-sig", errors="strict") if VP_LOCALISATION.exists() else ""
    tech_builder = read("tools/builders/build_adiscord_technology_system.py")
    tech_data = read("tools/data/adiscord_starting_technology_profiles.json")

    for localisation_path in (country_loc_path, VP_LOCALISATION):
        if not localisation_path.exists() or not localisation_path.read_bytes().startswith(b"\xef\xbb\xbf"):
            issues.append(f"{localisation_path.relative_to(ROOT)} must retain a UTF-8 BOM")

    for state_id in sorted(EXPECTED_STATES):
        path = state_path(state_id)
        actual = path.read_text(encoding="utf-8-sig", errors="strict")
        expected = render_state(state_id, profiles[state_id])
        if actual != expected:
            issues.append(f"{path.relative_to(ROOT)} is not synchronized with the northern builder")

    for tag, country in COUNTRIES.items():
        if f'{tag} = "countries/{tag}.txt"' not in tags_source:
            issues.append(f"country tag {tag} is not registered")
        country_definition = ROOT / "common" / "countries" / f"{tag}.txt"
        if not country_definition.exists():
            issues.append(f"missing common country definition for {tag}")
        history_path = named_history(tag)
        if history_path is None:
            issues.append(f"expected one country history for {tag}")
            continue
        history = history_path.read_text(encoding="utf-8-sig", errors="strict")
        for token in (
            f"capital = {country['capital']}",
            f'oob = "{tag}"',
            f"recruit_character = {LEADERS[tag]}",
        ):
            if token not in history:
                issues.append(f"{history_path.relative_to(ROOT)} lacks {token}")
        expected_ideas = set(EXPECTED_IDEAS.get(tag, ()))
        actual_ideas = {
            idea
            for idea in re.findall(r"\b[A-Z]{3}_[a-z0-9_]+\b", history)
            if idea in set().union(*map(set, EXPECTED_IDEAS.values()))
        }
        if actual_ideas != expected_ideas:
            issues.append(f"{tag} starting ideas expected {sorted(expected_ideas)}, found {sorted(actual_ideas)}")
        if LEADERS[tag] not in characters:
            issues.append(f"missing character {LEADERS[tag]}")
        trait = EXPECTED_TRAITS.get(tag)
        if trait and trait not in characters:
            issues.append(f"{LEADERS[tag]} lacks special trait {trait}")
        if trait and trait not in traits:
            issues.append(f"leader trait {trait} is not defined")
        for idea in expected_ideas:
            if idea not in ideas or idea not in country_loc:
                issues.append(f"national spirit {idea} lacks definition or localisation")

        oob_path = ROOT / "history" / "units" / f"{tag}.txt"
        expected_oob = render_oob(tag, country, principal_provinces)
        if not oob_path.exists() or oob_path.read_text(encoding="utf-8-sig", errors="strict") != expected_oob:
            issues.append(f"history/units/{tag}.txt is not synchronized with the northern builder")
        else:
            owned_provinces = {
                province
                for state_id in country["states"]
                for province in profiles[int(state_id)]["provinces"]
            }
            locations = {int(value) for value in re.findall(r"\blocation\s*=\s*(\d+)", expected_oob)}
            if not locations <= owned_provinces:
                issues.append(f"{tag} OOB contains locations outside starting ownership")

        for localisation_key in (tag, f"{tag}_DEF", f"{tag}_ADJ", LEADERS[tag]):
            if not re.search(rf"(?m)^\s*{re.escape(localisation_key)}:\s*\"", country_loc):
                issues.append(f"missing Russian localisation key {localisation_key}")
        if f'"{tag}"' not in tech_data or f'"{tag}":' not in tech_builder:
            issues.append(f"starting technology profile is missing for {tag}")

        for directory, size in ((FLAG_DIR, (82, 52)), (FLAG_DIR / "medium", (41, 26)), (FLAG_DIR / "small", (10, 7))):
            flag = directory / f"{tag}.tga"
            if not flag.exists():
                issues.append(f"missing flag {flag.relative_to(ROOT)}")
                continue
            with Image.open(flag) as image:
                if image.size != size or image.mode != "RGBA":
                    issues.append(f"{flag.relative_to(ROOT)} expected RGBA {size}, found {image.mode} {image.size}")

    for portrait_id, relative_path in (
        ("GFX_portrait_MON_Marius_II_Arken", "gfx/leaders/MON/portrait_MON_mongol_monarchy.png"),
        ("GFX_portrait_HON_Honter_Woke", "gfx/leaders/HON/portrait_HON_honter_woke.png"),
    ):
        if portrait_id not in portraits or relative_path not in portraits:
            issues.append(f"portrait binding {portrait_id} -> {relative_path} is missing")
        portrait_path = ROOT / relative_path
        if not portrait_path.exists():
            issues.append(f"portrait asset {relative_path} is missing")
        else:
            with Image.open(portrait_path) as image:
                if image.size != (156, 210):
                    issues.append(f"portrait asset {relative_path} expected 156x210, found {image.size}")

    for country in COUNTRIES.values():
        capital_state = int(country["capital"])
        key = f"VICTORY_POINTS_{principal_provinces[capital_state]}"
        if key not in vp_loc:
            issues.append(f"missing generated victory-point localisation {key}")

    mon_population, mon_civilian, mon_military = owner_totals("MON")
    if mon_population != int(COUNTRIES["MON"]["population"]) or (mon_civilian, mon_military) != (28, 18):
        issues.append("MON must retain its 12.2M population and 28+18 factory great-power baseline")
    for tag in set(COUNTRIES) - {"MON"}:
        population, civilian, military = owner_totals(tag)
        if mon_population <= population or mon_civilian + mon_military <= civilian + military:
            issues.append(f"MON is not stronger than northern peer {tag}")
    for stronger in ("WRK", "IVN"):
        population, civilian, military = owner_totals(stronger)
        if population <= mon_population or civilian + military <= mon_civilian + mon_military:
            issues.append(f"MON must remain below {stronger} in raw population and factory totals")
    mon_history = named_history("MON")
    if mon_history and len(EXPECTED_IDEAS["MON"]) != 4:
        issues.append("MON must start with exactly four bespoke national spirits")
    if "????" in country_loc or "????" in vp_loc:
        issues.append("northern Russian localisation contains encoding damage")

    return issues


def main() -> int:
    issues = validate()
    if issues:
        print(f"Northern-country validation failed with {len(issues)} issue(s):")
        for issue in issues:
            print(f"- {issue}")
        return 1
    print(
        f"Northern-country validation passed: {len(COUNTRIES)} countries, "
        f"{len(EXPECTED_STATES)} states, {sum(int(country['divisions']) for country in COUNTRIES.values())} divisions."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
