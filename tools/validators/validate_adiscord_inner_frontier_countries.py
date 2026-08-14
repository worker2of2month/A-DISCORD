#!/usr/bin/env python3
"""Validate the populated Itora/Vorkerland inner-frontier contract."""

from __future__ import annotations

import re
import sys
from pathlib import Path

from PIL import Image

_REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
if str(_REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPOSITORY_ROOT))

try:
    from tools.builders.build_adiscord_inner_frontier_countries import (
        CLAIMS_BY_STATE,
        COUNTRIES,
        COUNTRY_DIR,
        COUNTRY_HISTORY_DIR,
        COUNTRY_HISTORY_PROFILES,
        EXZ_LOCALISATION,
        EXZ_LOCALISATION_ENTRIES,
        EXPECTED_STATES,
        FLAG_DIR,
        POPULATION_MARKER,
        PROTECTORATE_SUCCESSORS,
        PROTECTORATE_TAG,
        ROOT,
        VP_LOCALISATION,
        build_profiles,
        protectorate_profile,
        render_common_country,
        render_country_history,
        render_oob,
        render_state,
        state_path,
    )
    from tools.builders.build_adiscord_strategic_regions import (
        build_state_adjacency,
        connected_components,
        load_province_adjacency,
        load_province_definitions,
    )
except ModuleNotFoundError:
    from builders.build_adiscord_inner_frontier_countries import (
        CLAIMS_BY_STATE,
        COUNTRIES,
        COUNTRY_DIR,
        COUNTRY_HISTORY_DIR,
        COUNTRY_HISTORY_PROFILES,
        EXZ_LOCALISATION,
        EXZ_LOCALISATION_ENTRIES,
        EXPECTED_STATES,
        FLAG_DIR,
        POPULATION_MARKER,
        PROTECTORATE_SUCCESSORS,
        PROTECTORATE_TAG,
        ROOT,
        VP_LOCALISATION,
        build_profiles,
        protectorate_profile,
        render_common_country,
        render_country_history,
        render_oob,
        render_state,
        state_path,
    )
    from builders.build_adiscord_strategic_regions import (
        build_state_adjacency,
        connected_components,
        load_province_adjacency,
        load_province_definitions,
    )


LEADERS = {
    "BOR": "BOR_Elena_Borey",
    "DOL": "DOL_Marko_Doln",
    "RIN": "RIN_Alaric_IV_Ren",
    "KRM": "KRM_Ivo_Kremen",
    "LMN": "LMN_Vera_Lemann",
    "RLY": "RLY_Relay_Assembly_17",
    "WCG": "WCG_Edgar_Raut",
}
EXPECTED_TRAITS = {
    "BOR": "BOR_frontier_mediator",
    "RIN": "RIN_last_palatin",
    "LMN": "LMN_quarantine_commissioner",
    "WCG": "WCG_gate_commandant",
}
EXPECTED_IDEAS = {
    "BOR": ("BOR_itoran_relief_charter",),
    "RIN": ("RIN_two_oaths", "RIN_palace_guard"),
    "KRM": ("KRM_slag_road_compact",),
    "LMN": ("LMN_permanent_quarantine",),
    "RLY": ("RLY_closed_circuit",),
    "WCG": ("WCG_living_filter",),
}


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8-sig", errors="strict")


def named_history(tag: str) -> Path | None:
    matches = sorted((ROOT / "history" / "countries").glob(f"{tag} -*.txt"))
    return matches[0] if len(matches) == 1 else None


def validate_external_gate_cleanup(split_effect: str, collapse_on_actions: str) -> list[str]:
    issues: list[str] = []
    krm_states = {151, 156, 161, 162, 163}
    lmn_states = {157, 158, 159, 160, 223}
    annex_token = "annex_country = { target = WCG transfer_troops = no }"
    if annex_token not in split_effect:
        issues.append("dissolved WCG formations are transferred to a successor instead of being removed")
    cleanup_tokens = (
        "ADISCORD_vorkerland_delete_external_gate_formations = {",
        'division_template = "Filtration Battalion"',
        "disband = no",
    )
    if any(token not in split_effect for token in cleanup_tokens):
        issues.append("External Gate split lacks explicit generated-formation cleanup")
    cleanup_call = "WCG = { ADISCORD_vorkerland_delete_external_gate_formations = yes }"
    anchor_token = "161 = { add_core_of = KRM set_state_owner_to = KRM set_state_controller_to = KRM }"
    cleanup_pos = split_effect.find(cleanup_call)
    anchor_pos = split_effect.find(anchor_token)
    annex_pos = split_effect.find(annex_token)
    if not 0 <= cleanup_pos < anchor_pos < annex_pos:
        issues.append("WCG formations must be deleted and KRM materialised before WCG is annexed")
    for state_id in sorted((krm_states | lmn_states) - {161}):
        successor = "KRM" if state_id in krm_states else "LMN"
        transfer_token = f"{state_id} = {{ add_core_of = {successor} set_state_owner_to"
        if split_effect.find(transfer_token) < annex_pos:
            issues.append(f"state {state_id} is transferred before the still-landed WCG annex cleanup")
    migration_flag = "ADISCORD_vorkerland_external_gate_formations_removed_v4"
    for forbidden in (cleanup_call, migration_flag):
        if forbidden in collapse_on_actions:
            issues.append("collapse on_actions must not repair landless WCG formations from old saves")
            break
    return issues


def validate() -> list[str]:
    issues: list[str] = []
    profiles, principal_provinces = build_profiles()
    if set(profiles) != EXPECTED_STATES or len(EXPECTED_STATES) != 29:
        issues.append("inner-frontier profile coverage must contain exactly 29 approved states")
    if EXPECTED_STATES & set(range(474, 551)):
        issues.append("western-continent states 474-550 entered the inner-frontier contract")
    for state_id in range(474, 551):
        western_paths = sorted((ROOT / "history" / "states").glob(f"{state_id}-outer-left.txt"))
        if len(western_paths) == 1 and POPULATION_MARKER in western_paths[0].read_text(encoding="utf-8-sig", errors="strict"):
            issues.append(f"western-continent state {state_id} was touched by the inner-frontier builder")

    tags_source = read("common/country_tags/05_ADISCORD_inner_frontier_tags.txt")
    characters = read("common/characters/ADISCORD_inner_frontier_characters.txt")
    traits = read("common/country_leader/ADISCORD_inner_frontier_traits.txt")
    ideas = read("common/ideas/ADISCORD_inner_frontier_ideas.txt")
    country_loc_paths = tuple(
        ROOT / "localisation" / "russian" / filename
        for filename in (
            "countries_l_russian.yml",
            "parties_l_russian.yml",
            "nsb_characters_l_russian.yml",
            "ADISCORD_traits_l_russian.yml",
            "ADISCORD_ideas_l_russian.yml",
            "politics_l_russian.yml",
            "events_l_russian.yml",
        )
    )
    country_loc = "\n".join(
        path.read_text(encoding="utf-8-sig", errors="strict") for path in country_loc_paths
    )
    vp_loc = VP_LOCALISATION.read_text(encoding="utf-8-sig", errors="strict") if VP_LOCALISATION.exists() else ""
    adjacency_source = read("map/adjacencies.csv")
    tech_builder = read("tools/builders/build_adiscord_technology_system.py")
    tech_data = read("tools/data/adiscord_starting_technology_profiles.json")
    split_effect = read("common/scripted_effects/ADISCORD_inner_frontier_effects.txt")
    collapse_maps = read("common/scripted_effects/ADISCORD_vorkerland_collapse_map_effects.txt")
    collapse_effects = read("common/scripted_effects/ADISCORD_vorkerland_collapse_effects.txt")
    phase_effects = read("common/scripted_effects/ADISCORD_vorkerland_phase_effects.txt")
    collapse_on_actions = read("common/on_actions/01_ADISCORD_vorkerland_collapse_on_actions.txt")

    for localisation_path in (*country_loc_paths, VP_LOCALISATION, EXZ_LOCALISATION):
        if not localisation_path.exists() or not localisation_path.read_bytes().startswith(b"\xef\xbb\xbf"):
            issues.append(f"{localisation_path.relative_to(ROOT)} must retain a UTF-8 BOM")

    for tag, history_profile in COUNTRY_HISTORY_PROFILES.items():
        common_path = COUNTRY_DIR / f"{tag}.txt"
        expected_common = render_common_country(tag)
        if (
            not common_path.exists()
            or common_path.read_text(encoding="utf-8-sig", errors="strict") != expected_common
        ):
            issues.append(
                f"{common_path.relative_to(ROOT)} is not synchronized with the inner-frontier builder"
            )

        history_path = COUNTRY_HISTORY_DIR / str(history_profile["filename"])
        expected_history = render_country_history(tag)
        if (
            not history_path.exists()
            or history_path.read_text(encoding="utf-8-sig", errors="strict") != expected_history
        ):
            issues.append(
                f"{history_path.relative_to(ROOT)} is not synchronized with the inner-frontier builder"
            )
        elif re.search(
            r"(?m)^\s*(?:graphical_culture|graphical_culture_2d|color)\s*=",
            expected_history,
        ):
            issues.append(
                f"{history_path.relative_to(ROOT)} contains common-country fields in history scope"
            )

    state_sets: dict[int, set[int]] = {}
    for state_id in sorted(EXPECTED_STATES):
        path = state_path(state_id)
        actual = path.read_text(encoding="utf-8-sig", errors="strict")
        expected = render_state(state_id, profiles[state_id])
        if actual != expected:
            issues.append(f"{path.relative_to(ROOT)} is not synchronized with the inner-frontier builder")
        state_sets[state_id] = set(profiles[state_id]["provinces"])
        for claimant in CLAIMS_BY_STATE.get(state_id, ()):
            if not re.search(rf"(?m)^\s*add_claim_by\s*=\s*{claimant}\s*$", actual):
                issues.append(f"state {state_id} lacks approved claim by {claimant}")

    province_types, color_to_province = load_province_definitions()
    special_province_adjacency = load_province_adjacency(
        province_types, color_to_province, include_special_adjacencies=True
    )
    province_adjacency = load_province_adjacency(
        province_types, color_to_province, include_special_adjacencies=False
    )
    bridge_rows = [
        fields
        for line in adjacency_source.splitlines()[1:]
        if len(fields := line.split(";")) >= 10
        and fields[0].isdigit()
        and fields[1].isdigit()
        and {int(fields[0]), int(fields[1])} == {16488, 16328}
    ]
    if len(bridge_rows) != 1:
        issues.append(f"Relyen bridge adjacency expected once, found {len(bridge_rows)}")
    else:
        bridge = bridge_rows[0]
        if bridge[2] != "sea" or bridge[3] != "16264":
            issues.append("Relyen bridge must cross sea province 16264")
    if 16328 not in special_province_adjacency.get(16488, set()):
        issues.append("Relyen bridge is absent from the playable province adjacency graph")
    if 16328 in province_adjacency.get(16488, set()):
        issues.append("Relyen bridge endpoints unexpectedly share a physical land border")
    state_adjacency = build_state_adjacency(state_sets, province_adjacency)
    for tag, country in COUNTRIES.items():
        components = connected_components(set(country["states"]), state_adjacency)
        if len(components) != 1:
            issues.append(f"{tag} successor territory is disconnected: {[sorted(component) for component in components]}")

        if f'{tag} = "countries/{tag}.txt"' not in tags_source:
            issues.append(f"country tag {tag} is not registered")
        if not (ROOT / "common" / "countries" / f"{tag}.txt").exists():
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
        all_ideas = set().union(*map(set, EXPECTED_IDEAS.values()))
        actual_ideas = {
            idea for idea in re.findall(r"\b[A-Z]{3}_[a-z0-9_]+\b", history) if idea in all_ideas
        }
        expected_ideas = set(EXPECTED_IDEAS.get(tag, ()))
        if actual_ideas != expected_ideas:
            issues.append(f"{tag} starting ideas expected {sorted(expected_ideas)}, found {sorted(actual_ideas)}")
        if LEADERS[tag] not in characters:
            issues.append(f"missing character {LEADERS[tag]}")
        trait = EXPECTED_TRAITS.get(tag)
        if trait and (trait not in characters or trait not in traits):
            issues.append(f"missing special leader trait {trait}")
        for idea in expected_ideas:
            if idea not in ideas or idea not in country_loc:
                issues.append(f"national spirit {idea} lacks definition or localisation")

        oob_path = ROOT / "history" / "units" / f"{tag}.txt"
        expected_oob = render_oob(tag, country, principal_provinces)
        if not oob_path.exists() or oob_path.read_text(encoding="utf-8-sig", errors="strict") != expected_oob:
            issues.append(f"history/units/{tag}.txt is not synchronized with the inner-frontier builder")
        else:
            owned_provinces = {
                province
                for state_id in country["states"]
                for province in profiles[int(state_id)]["provinces"]
            }
            locations = {int(value) for value in re.findall(r"\blocation\s*=\s*(\d+)", expected_oob)}
            if not locations <= owned_provinces:
                issues.append(f"{tag} OOB contains locations outside its successor territory")

        for localisation_key in (tag, f"{tag}_DEF", f"{tag}_ADJ", LEADERS[tag]):
            if not re.search(rf'(?m)^\s*{re.escape(localisation_key)}:\s*"', country_loc):
                issues.append(f"missing Russian localisation key {localisation_key}")
        if tag not in PROTECTORATE_SUCCESSORS and (f'"{tag}"' not in tech_data or f'"{tag}":' not in tech_builder):
            issues.append(f"starting technology profile is missing for {tag}")

        for directory, size in ((FLAG_DIR, (82, 52)), (FLAG_DIR / "medium", (41, 26)), (FLAG_DIR / "small", (10, 7))):
            flag = directory / f"{tag}.tga"
            if not flag.exists():
                issues.append(f"missing flag {flag.relative_to(ROOT)}")
                continue
            with Image.open(flag) as image:
                if image.size != size or image.mode != "RGBA":
                    issues.append(f"{flag.relative_to(ROOT)} expected RGBA {size}, found {image.mode} {image.size}")

    gate = protectorate_profile()
    if f'{PROTECTORATE_TAG} = "countries/{PROTECTORATE_TAG}.txt"' not in tags_source:
        issues.append("WCG country tag is not registered")
    if not (ROOT / "common" / "countries" / "WCG.txt").exists():
        issues.append("missing common country definition for WCG")
    gate_history_path = named_history(PROTECTORATE_TAG)
    if gate_history_path is None:
        issues.append("expected one country history for WCG")
    else:
        gate_history = gate_history_path.read_text(encoding="utf-8-sig", errors="strict")
        for token in ('capital = 159', 'oob = "WCG"', 'recruit_character = WCG_Edgar_Raut', 'WCG_living_filter'):
            if token not in gate_history:
                issues.append(f"{gate_history_path.relative_to(ROOT)} lacks {token}")
    wrk_history = read("history/countries/WRK - WorkerLand.txt")
    for token in (
        "add_to_faction = WCG",
        "target = WCG",
        "autonomous_state = autonomy_vorkerland_sanitary_gate",
    ):
        if token not in wrk_history:
            issues.append(f"WRK history lacks External Gate dependency token {token}")
    autonomy = read("common/autonomous_states/ADISCORD_vorkerland_sanitary_gate.txt")
    for token in (
        "id = autonomy_vorkerland_sanitary_gate",
        "is_puppet = yes",
        "cic_to_overlord_factor = 0.50",
        "mic_to_overlord_factor = 0.65",
        "can_take_level = { always = no }",
    ):
        if token not in autonomy:
            issues.append(f"special External Gate autonomy lacks {token}")
    autonomy_icon_gfx = read("interface/ADISCORD_autonomy_icons.gfx")
    autonomy_icon_path = (
        ROOT
        / "gfx"
        / "interface"
        / "autonomy"
        / "autonomy_vorkerland_sanitary_gate_icon.png"
    )
    old_autonomy_icon_path = (
        ROOT / "gfx" / "interface" / "autonomy" / "воркерланд санитарная зона.png"
    )
    for token in (
        'name = "GFX_autonomy_vorkerland_sanitary_gate_icon"',
        'textureFile = "gfx/interface/autonomy/autonomy_vorkerland_sanitary_gate_icon.png"',
    ):
        if token not in autonomy_icon_gfx:
            issues.append(f"External Gate autonomy icon GFX lacks {token}")
    if not autonomy_icon_path.exists():
        issues.append("renamed External Gate autonomy icon is missing")
    else:
        with Image.open(autonomy_icon_path) as image:
            if image.size != (35, 36) or image.mode != "RGBA":
                issues.append(
                    "External Gate autonomy icon must preserve the supplied RGBA 35x36 asset, "
                    f"found {image.mode} {image.size}"
                )
    if old_autonomy_icon_path.exists():
        issues.append("the unscoped Cyrillic External Gate autonomy icon filename still exists")
    gate_oob = render_oob(PROTECTORATE_TAG, gate, principal_provinces)
    gate_oob_path = ROOT / "history" / "units" / "WCG.txt"
    if not gate_oob_path.exists() or gate_oob_path.read_text(encoding="utf-8-sig", errors="strict") != gate_oob:
        issues.append("history/units/WCG.txt is not synchronized with the inner-frontier builder")
    if "WCG_Edgar_Raut" not in characters or "WCG_gate_commandant" not in traits:
        issues.append("External Gate leader or special trait is missing")
    if "WCG_living_filter" not in ideas or "WCG_living_filter" not in country_loc:
        issues.append("External Gate's harsh national spirit is missing")
    portrait_gfx = read("interface/ADISCORD_inner_frontier_portraits.gfx")
    portrait_path = ROOT / "gfx" / "leaders" / "WCG" / "portrait_WCG_Edgar_Raut.png"
    if "GFX_portrait_WCG_Edgar_Raut" not in portrait_gfx or not portrait_path.exists():
        issues.append("renamed External Gate portrait is not wired")
    for localisation_key in ("WCG", "WCG_DEF", "WCG_ADJ", "WCG_Edgar_Raut", "autonomy_vorkerland_sanitary_gate"):
        localisation_source = country_loc if localisation_key != "autonomy_vorkerland_sanitary_gate" else read("localisation/russian/autonomy_l_russian.yml")
        if not re.search(rf'(?m)^\s*{re.escape(localisation_key)}:\s*"', localisation_source):
            issues.append(f"missing Russian localisation key {localisation_key}")
    if '"WCG"' not in tech_data or '"WCG":' not in tech_builder:
        issues.append("starting technology profile is missing for WCG")
    for directory, size in ((FLAG_DIR, (82, 52)), (FLAG_DIR / "medium", (41, 26)), (FLAG_DIR / "small", (10, 7))):
        flag = directory / "WCG.tga"
        if not flag.exists():
            issues.append(f"missing flag {flag.relative_to(ROOT)}")
            continue
        with Image.open(flag) as image:
            if image.size != size or image.mode != "RGBA":
                issues.append(f"{flag.relative_to(ROOT)} expected RGBA {size}, found {image.mode} {image.size}")
    krm_states = {151, 156, 161, 162, 163}
    lmn_states = {157, 158, 159, 160, 223}
    for state_id in sorted(krm_states | lmn_states):
        successor = "KRM" if state_id in krm_states else "LMN"
        state_source = state_path(state_id).read_text(encoding="utf-8-sig", errors="strict")
        if not re.search(r"(?m)^\s*owner\s*=\s*WCG\s*$", state_source):
            issues.append(f"state {state_id} must start under WCG")
        if not re.search(rf"(?m)^\s*add_core_of\s*=\s*{successor}\s*$", state_source):
            issues.append(f"state {state_id} lacks successor core {successor}")
        for token in (f"{state_id} = {{ add_core_of = {successor}", f"set_state_owner_to = {successor}"):
            if token not in split_effect:
                issues.append(f"External Gate split effect lacks {successor} transfer for state {state_id}")
    if "ADISCORD_vorkerland_split_external_gate = yes" in collapse_maps:
        issues.append("legacy outcome maps must not own External Gate lifecycle cleanup")
    if collapse_effects.count("ADISCORD_vorkerland_split_external_gate = yes") != 1:
        issues.append("the initial Vorkerland collapse must split the External Gate immediately")
    if phase_effects.count("ADISCORD_vorkerland_split_external_gate = yes") != 1:
        issues.append("the terminal phase finalizer must idempotently verify the External Gate split")
    if "ADISCORD_vorkerland_split_external_gate = yes" in collapse_on_actions:
        issues.append("collapse on_actions must not repair the External Gate split from old saves")
    issues.extend(validate_external_gate_cleanup(split_effect, collapse_on_actions))

    for country in COUNTRIES.values():
        settlement_states = {int(country["capital"])} | {
            int(state_id) for state_id, _name, _value in country.get("secondary_vps", ())
        }
        for state_id in settlement_states:
            key = f"VICTORY_POINTS_{principal_provinces[state_id]}"
            if key not in vp_loc:
                issues.append(f"missing generated victory-point localisation {key}")

    expected_rly_localisation = {
        "RLY": "Релейн",
        "RLY_DEF": "Релейнская республика",
        "RLY_ADJ": "релейнск.",
        "RLY_technocracy": "Релейнская республика",
        "RLY_technocracy_party": "Станционный совет",
        "RLY_Relay_Assembly_17": "Станционный совет Релейна",
    }
    for key, value in expected_rly_localisation.items():
        if not re.search(rf'(?m)^\s*{re.escape(key)}:\s*"{re.escape(value)}"\s*$', country_loc):
            issues.append(f"RLY visible localisation {key} must be {value}")
    if COUNTRIES["RLY"]["capital_name"] != "Релейн":
        issues.append("RLY generated capital must be named Релейн")
    if "Реле-17" in country_loc or "Реле-17" in vp_loc or "Релейный анклав №17" in country_loc:
        issues.append("obsolete RLY player-facing name remains in Russian localisation")

    exz_localisation = EXZ_LOCALISATION.read_text(encoding="utf-8-sig", errors="strict")
    for key, value in EXZ_LOCALISATION_ENTRIES.items():
        if not re.search(rf'(?m)^\s*{re.escape(key)}:\s*"{re.escape(value)}"\s*$', exz_localisation):
            issues.append(f"generated EXZ localisation {key} is not synchronized with the inner-frontier builder")
    damage_marker = "?" * 4
    if damage_marker in country_loc or damage_marker in vp_loc:
        issues.append("inner-frontier Russian localisation contains encoding damage")
    return issues


def main() -> int:
    issues = validate()
    if issues:
        print(f"Inner-frontier validation failed with {len(issues)} issue(s):")
        for issue in issues:
            print(f"- {issue}")
        return 1
    print(
        f"Inner-frontier validation passed: {len(COUNTRIES)} successors plus WCG, "
        f"{len(EXPECTED_STATES)} states, {sum(int(country['divisions']) for country in COUNTRIES.values()) + 5} OOB divisions."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
