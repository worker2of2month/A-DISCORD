#!/usr/bin/env python3
"""Read-only gate for the current border-driven Vorkerland collapse."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from PIL import Image

try:
    from tools import build_adiscord_strategic_regions as map_regions
    from tools.vorkerland_collapse_manifest import (
        CAPITALS,
        CONTAMINATED_STATES,
        DIRTY_GROUPS,
        EXZ_REMAINDER_GROUPS,
        STATE_PARTITIONS,
        TAGS,
    )
except (ModuleNotFoundError, ImportError):
    import build_adiscord_strategic_regions as map_regions
    from vorkerland_collapse_manifest import (
        CAPITALS,
        CONTAMINATED_STATES,
        DIRTY_GROUPS,
        EXZ_REMAINDER_GROUPS,
        STATE_PARTITIONS,
        TAGS,
    )


ROOT = Path(__file__).resolve().parents[1]
SECTIONS = (
    "manifest",
    "states",
    "countries",
    "events",
    "ai",
    "outcomes",
    "exhaustion",
    "superevents",
)
PERIPHERY_STATES = (
    40, 71, 72, 73, 74, 76, 80, 90, 91, 93, 94, 105, 144, 145,
    *range(194, 200), *range(306, 326), 327, 328,
)
STALE_SYSTEM_TOKENS = (
    "ADISCORD_vorkerland_stalemate",
    "ADISCORD_vorkerland_war_weariness",
    "ADISCORD_vorkerland_to_the_last",
    "ADISCORD_vorkerland_phase_",
    "ADISCORD_vorkerland_ai_consolidation_window",
    "ADISCORD_vorkerland_ai_regional_window",
)
INITIAL_CENTRAL_BORDER_PAIRS = {
    frozenset(pair) for pair in (
        ("WRK", "TVA"), ("WRK", "EYR"), ("VAD", "EYR"),
        ("VAD", "EGC"), ("TVA", "EYR"), ("TVA", "EGC"),
        ("EYR", "EGC"),
    )
}
INITIAL_LOCAL_BORDER_PAIRS = {
    frozenset(pair) for pair in (
        ("ZAO", "WPS"), ("WPA", "WPS"), ("PWR", "PSD"),
        ("VLA", "EBA"), ("VLA", "TGD"), ("EBA", "TGD"),
        ("ROM", "DVA"), ("SOL", "SRA"), ("SOL", "CSL"),
        ("SRA", "CSL"), ("TRU", "ZTA"),
    )
}


def read(root: Path, relative: str, issues: list[str]) -> str:
    path = root / relative
    if not path.exists():
        issues.append(f"missing {relative}")
        return ""
    return path.read_text(encoding="utf-8-sig", errors="strict")


def balanced(source: str) -> bool:
    depth = 0
    quoted = False
    escaped = False
    for raw in source.splitlines():
        line = raw.split("#", 1)[0]
        for char in line:
            if escaped:
                escaped = False
            elif quoted and char == "\\":
                escaped = True
            elif char == '"':
                quoted = not quoted
            elif not quoted and char == "{":
                depth += 1
            elif not quoted and char == "}":
                depth -= 1
                if depth < 0:
                    return False
    return depth == 0 and not quoted


def named_block(source: str, name: str) -> str:
    match = re.search(rf"(?m)^\s*{re.escape(name)}\s*=\s*\{{", source)
    if not match:
        return ""
    depth = 0
    quoted = False
    escaped = False
    for index in range(match.start(), len(source)):
        char = source[index]
        if escaped:
            escaped = False
        elif quoted and char == "\\":
            escaped = True
        elif char == '"':
            quoted = not quoted
        elif not quoted and char == "{":
            depth += 1
        elif not quoted and char == "}":
            depth -= 1
            if depth == 0:
                return source[match.start():index + 1]
    return ""


def state_source(root: Path, state_id: int, issues: list[str]) -> str:
    matches = sorted((root / "history" / "states").glob(f"{state_id}-*.txt"))
    if len(matches) != 1:
        issues.append(f"state {state_id}: expected one file, found {len(matches)}")
        return ""
    return matches[0].read_text(encoding="utf-8-sig")


def scalar(source: str, key: str) -> float | None:
    match = re.search(rf"(?m)^\s*{re.escape(key)}\s*=\s*(-?\d+(?:\.\d+)?)", source)
    return float(match.group(1)) if match else None


def initial_tag_states(effects: str, tag: str) -> set[int]:
    """Return states explicitly assigned to a tag by the collapse setup."""
    initial = named_block(effects, "ADISCORD_vorkerland_apply_initial_map")
    source = named_block(initial, tag) + "\n" + named_block(
        effects, f"ADISCORD_vorkerland_setup_{tag.lower()}"
    )
    return {int(value) for value in re.findall(r"\btransfer_state\s*=\s*(\d+)", source)}


def validate_manifest(root: Path, issues: list[str]) -> None:
    del root
    if len(TAGS) != 20 or len(set(TAGS)) != 20:
        issues.append("manifest must contain 20 unique collapse tags")
    if set(CAPITALS) != set(TAGS):
        issues.append("capital manifest must cover every collapse tag")
    dirty = tuple(state for states in DIRTY_GROUPS.values() for state in states)
    if len(dirty) != len(set(dirty)):
        issues.append("dirty-state groups overlap")
    if set(dirty) != CONTAMINATED_STATES - {23, 24, 57, 59, 60}:
        issues.append("dirty-state groups no longer cover the playable exclusion zone")
    remainder = tuple(state for states in EXZ_REMAINDER_GROUPS.values() for state in states)
    if len(remainder) != len(set(remainder)) or set(remainder) & set(dirty):
        issues.append("EXZ remainder groups overlap playable dirty states")
    if set(STATE_PARTITIONS) != {71, 72, 74, 76, 80}:
        issues.append("legacy state partition manifest changed unexpectedly")


def validate_states(root: Path, issues: list[str]) -> None:
    for source_state, partition in STATE_PARTITIONS.items():
        expected_union = set().union(*(set(values) for values in partition.values()))
        actual_union: set[int] = set()
        for state_id, expected in partition.items():
            source = state_source(root, state_id, issues)
            match = re.search(r"provinces\s*=\s*\{([^}]*)\}", source, re.DOTALL)
            actual = {int(value) for value in re.findall(r"\d+", match.group(1))} if match else set()
            if actual != set(expected):
                issues.append(f"state {state_id}: province partition drifted from source {source_state}")
            actual_union |= actual
        if actual_union != expected_union:
            issues.append(f"state {source_state}: partition no longer preserves all provinces")

    for state_id in PERIPHERY_STATES:
        if state_id == 326:  # PIV, not a Vorkerland successor state.
            continue
        source = state_source(root, state_id, issues)
        manpower = scalar(source, "manpower")
        supplies = scalar(source, "local_supplies")
        if manpower is None or manpower <= 0:
            issues.append(f"state {state_id}: Vorkerland population must be positive")
        if supplies is None or supplies < 1.5:
            issues.append(f"state {state_id}: local supply must be at least 1.5")
        if "set_demilitarized_zone = yes" in source:
            issues.append(f"state {state_id}: stale demilitarized zone freezes the front")

    technograd = state_source(root, 105, issues)
    for token in ("manpower = 9800000", "state_category = megalopolis", "infrastructure = 5", "local_supplies = 10.0"):
        if token not in technograd:
            issues.append(f"Technograd state 105 is missing {token}")
    if "impassable = yes" in technograd or "state_category = wasteland" in technograd:
        issues.append("Technograd must be a traversable megalopolis")


def validate_countries(root: Path, issues: list[str]) -> None:
    tags = read(root, "common/country_tags/01_ADISCORD_vorkerland_collapse_tags.txt", issues)
    characters = read(root, "common/characters/ADISCORD_vorkerland_collapse_characters.txt", issues)
    portraits = read(root, "interface/ADISCORD_leader_portraits.gfx", issues)
    for tag in TAGS:
        if f'{tag} = "countries/{tag}.txt"' not in tags:
            issues.append(f"tag {tag}: missing registration")
        if not (root / "common" / "countries" / f"{tag}.txt").exists():
            issues.append(f"tag {tag}: missing country definition")
        if not list((root / "history" / "countries").glob(f"{tag} - *.txt")):
            issues.append(f"tag {tag}: missing country history")
        if not (root / "history" / "units" / f"{tag}_vorkerland_collapse.txt").exists():
            issues.append(f"tag {tag}: missing collapse OOB")

    required_characters = {
        "EBA_Vlad_Mecra": "GFX_portrait_WRK_Vlad_Mecra",
        "TGD_Ted_Cuttle": "GFX_portrait_WRK_Ted_Cuttle",
        "IBA_Matvey_Mateusk": "GFX_portrait_IBA_Matvey_Mateusk",
        "IBL_Anton_Selevyostrov": "GFX_portrait_IBL_Anton_Selevyostrov",
        "WPA_Oliver_Larry_Gates": "GFX_portrait_WPA_Oliver_Larry_Gates",
        "DVA_Severin_Mark": "GFX_portrait_DVA_Severin_Mark",
        "EGC_Ruslan_Pike": "GFX_portrait_EGC_Ruslan_Pike",
        "WPS_Karim_Dol": "GFX_portrait_WPS_Karim_Dol",
        "SRA_Helio_Marr": "GFX_portrait_SRA_Helio_Marr",
        "ZTA_Viktor_Holt": "GFX_portrait_ZTA_Viktor_Holt",
    }
    for character, portrait in required_characters.items():
        block = named_block(characters, character)
        if not block or "country_leader" not in block or portrait not in block:
            issues.append(f"{character}: supplied portrait is not used by a country leader")
        gfx = named_block(portraits, "spriteTypes")
        if portrait not in gfx:
            issues.append(f"{character}: missing portrait sprite {portrait}")

    for cosmetic in (
        "WRK_vorkerland_emergency",
        "VAD_vorkerland_restoration",
        "WRK_vorkerland_joint_government",
        "PWR_rimat_republic",
        "ZAO_zaozersk_republic",
        "VLA_volnograd_republic",
        "ROM_frealor_republic",
        "TRU_zolotorevsk_republic",
    ):
        for directory, size in (("", (82, 52)), ("medium", (41, 26)), ("small", (10, 7))):
            path = root / "gfx" / "flags" / directory / f"{cosmetic}.tga"
            if not path.exists():
                issues.append(f"missing cosmetic flag {path.relative_to(root)}")
            else:
                with Image.open(path) as image:
                    if image.size != size:
                        issues.append(f"{path.relative_to(root)}: expected {size}, got {image.size}")

    cosmetic_definitions = read(root, "common/countries/cosmetic.txt", issues)
    for token in (
        "WRK_vorkerland_emergency = {",
        "color = rgb { 72 61 57 }",
        "color_ui = rgb { 196 93 52 }",
        "VAD_vorkerland_restoration = {",
        "color = rgb { 19 45 105 }",
        "color_ui = rgb { 65 112 210 }",
        "PWR_rimat_republic = {",
        "ROM_frealor_republic = {",
        "TRU_zolotorevsk_republic = {",
    ):
        if token not in cosmetic_definitions:
            issues.append(f"collapse cosmetic colours are missing {token}")
    pwr_flag = root / "gfx" / "flags" / "PWR_rimat_republic.tga"
    old_pwr_flag = root / "gfx" / "flags" / "PWR.tga"
    if pwr_flag.exists() and old_pwr_flag.exists():
        with Image.open(pwr_flag) as new_flag, Image.open(old_pwr_flag) as old_flag:
            if new_flag.convert("RGB").tobytes() == old_flag.convert("RGB").tobytes():
                issues.append("PWR collapse cosmetic still reuses its administrative flag")

    loc_path = root / "localisation" / "russian" / "ADISCORD_vorkerland_collapse_l_russian.yml"
    raw = loc_path.read_bytes() if loc_path.exists() else b""
    if not raw.startswith(b"\xef\xbb\xbf"):
        issues.append("Vorkerland Russian localisation must retain UTF-8 BOM")
    loc = raw.decode("utf-8-sig") if raw else ""
    for banned in ("Западный союз", "Норвенская береговая республика", "Восточное содружество"):
        if banned in loc:
            issues.append(f"obsolete/cringe country name survived localisation: {banned}")
    cosmetic_loc = read(root, "localisation/russian/countries_cosmetic_l_russian.yml", issues)
    for key, name in (
        ("PWR_rimat_republic", "Риматская республика"),
        ("ZAO_zaozersk_republic", "Заозерская республика"),
        ("VLA_volnograd_republic", "Вольноградская республика"),
        ("ROM_frealor_republic", "Республика Фреалор"),
        ("TRU_zolotorevsk_republic", "Золоторевская республика"),
    ):
        if f'{key}: "{name}"' not in cosmetic_loc:
            issues.append(f"{key} lacks its short republican name")

    if re.search(r"\bdesc\s*=\s*[A-Za-z0-9_]+_desc\b", characters):
        issues.append("new Vorkerland leaders still expose in-game biography desc keys")
    for leader in re.findall(r"(?m)^\s*([A-Z]{3}_[A-Za-z0-9_]+)\s*=", characters):
        if f"{leader}_desc:" in loc:
            issues.append(f"{leader}: obsolete in-game biography localisation survived")
    if "ZTA_Vera_Holt" in characters + portraits + loc or "GFX_portrait_ZTA_Vera_Holt" in portraits:
        issues.append("the obsolete Vera Holt character reference survived")
    viktor_portrait = root / "gfx" / "leaders" / "ZTA" / "portrait_ZTA_Viktor_Holt.png"
    if not viktor_portrait.exists():
        issues.append("Viktor Holt portrait filename was not migrated")


def validate_events(root: Path, issues: list[str]) -> None:
    events = read(root, "events/ADISCORD_vorkerland_collapse_events.txt", issues)
    effects = read(root, "common/scripted_effects/ADISCORD_vorkerland_collapse_effects.txt", issues)
    decisions = read(root, "common/decisions/ADISCORD_vorkerland_collapse_decisions.txt", issues)
    ideas = read(root, "common/ideas/ADISCORD_vorkerland_collapse_ideas.txt", issues)
    loc = read(root, "localisation/russian/ADISCORD_vorkerland_collapse_l_russian.yml", issues)
    triggers = read(root, "common/scripted_triggers/ADISCORD_vorkerland_collapse_triggers.txt", issues)
    on_actions = read(root, "common/on_actions/01_ADISCORD_vorkerland_collapse_on_actions.txt", issues)
    map_effects = read(root, "common/scripted_effects/ADISCORD_vorkerland_collapse_map_effects.txt", issues)
    news_loc = read(root, "localisation/russian/ADISORD_news_l_russian.yml", issues)
    superevent_loc = read(root, "localisation/russian/ADISCORD_superevents_l_russian.yml", issues)
    for label, source in (("events", events), ("effects", effects), ("decisions", decisions), ("ideas", ideas)):
        if not balanced(source):
            issues.append(f"collapse {label}: unbalanced braces or quote")
        for stale in STALE_SYSTEM_TOKENS:
            if stale in source:
                issues.append(f"collapse {label}: dead system token survived: {stale}")

    outbreak = named_block(events, "country_event")
    if not outbreak:
        issues.append("collapse outbreak event is missing")
    for token in (
        "ADISCORD_vorkerland_apply_initial_map = yes",
        "ADISCORD_vorkerland_teardown_confederation = yes",
        "ADISCORD_vorkerland_apply_claimant_cosmetics = yes",
        "GFX_portrait_ROM_Erwin_Von_Romanovskiy_civilwar",
        "GFX_portrait_TRU_Nikita_Truman_civilwar",
        "ADISCORD_vorkerland_form_joint_government = yes",
    ):
        if token not in outbreak:
            issues.append(f"collapse outbreak is missing {token}")
    if outbreak.find("ADISCORD_vorkerland_apply_initial_map = yes") > outbreak.find(
        "ADISCORD_vorkerland_teardown_confederation = yes"
    ):
        issues.append("collapse teardown must run after all regional tags are spawned")

    opening_news = named_block(outbreak, "news_event")
    if events.count("id = news.0") != 1:
        issues.append("collapse opening news must have exactly one trigger path")
    for token in (
        "NOT = { has_global_flag = ADISCORD_vorkerland_collapse_news_shown }",
        "set_global_flag = ADISCORD_vorkerland_collapse_news_shown",
        "news_event = { id = news.0 }",
    ):
        if token not in outbreak:
            issues.append(f"collapse opening news is missing {token}")
    if any(token in opening_news for token in ("hours =", "days =", "random_hours", "random_days")):
        issues.append("collapse opening news is still delayed or randomized")
    if outbreak.find("ADISCORD_vorkerland_apply_claimant_cosmetics = yes") > outbreak.find(
        "news_event = { id = news.0 }"
    ):
        issues.append("collapse opening news fires before successor setup is complete")
    if "news.0" in on_actions:
        issues.append("collapse opening news still has an on-action duplicate path")
    if 'news.0.t: "Конец единого Воркерланда"' not in news_loc:
        issues.append("collapse opening world-news title is not 'Конец единого Воркерланда'")
    teardown = named_block(effects, "ADISCORD_vorkerland_teardown_confederation")
    if "is_subject_of = WRK" in teardown:
        issues.append("collapse teardown still assumes WRK is every country's overlord")
    independent_tags = (
        "WRK", "VAD", "NAM", "DAN", "ZAO", "PWR", "VLA", "ROM", "SOL", "TRU",
        "TVA", "EYR", "EGC", "WPA", "WPS", "PSD", "EBA", "DVA", "SRA", "ZTA",
        "TGD", "IBL", "IBA",
    )
    for tag in independent_tags:
        country = named_block(teardown, tag)
        for token in (
            "is_subject = yes",
            "overlord =",
            f"target = {tag}",
            "autonomy_state = autonomy_free",
            "is_in_faction = yes",
            "leave_faction = yes",
        ):
            if token not in country:
                issues.append(f"{tag}: collapse teardown is missing {token}")

    initial_map = named_block(effects, "ADISCORD_vorkerland_apply_initial_map")
    wrk_partition = named_block(initial_map, "WRK")
    tgd_setup = named_block(effects, "ADISCORD_vorkerland_setup_tgd")
    if not re.search(r"transfer_state\s*=\s*32\b", wrk_partition):
        issues.append("WRK no longer receives the Unity Tower capital state 32")
    if re.search(r"transfer_state\s*=\s*105\b", wrk_partition):
        issues.append("WRK still receives TGD's peripheral state 105")
    for token in ("transfer_state = 105", "105 = { add_core_of = TGD", "set_capital = { state = 105 }"):
        if token not in tgd_setup:
            issues.append(f"TGD peripheral capital is missing {token}")
    for forbidden in ("transfer_state = 32", "transfer_state = 40"):
        if forbidden in tgd_setup:
            issues.append(f"TGD still claims the Unity Tower enclave: {forbidden}")

    war_start = re.search(
        r"(?ms)^country_event\s*=\s*\{\s*id\s*=\s*ADISCORD_vorkerland_collapse\.2\b(.*?)(?=^country_event\s*=\s*\{|\Z)",
        events,
    )
    second = war_start.group(1) if war_start else ""
    if "declare_war_on" in second:
        issues.append("collapse day-one event still declares wars immediately")
    for token in ("ADISCORD_vorkerland_collapse.31", "days = 21", "random_days = 14"):
        if token not in second:
            issues.append(f"collapse mobilisation pause is missing {token}")

    central_war = named_block(decisions, "ADISCORD_vorkerland_consolidate_central_border")
    for target in ("WRK", "VAD", "TVA"):
        if f"declare_war_on = {{ target = {target}" not in central_war:
            issues.append(f"central-war decision cannot directly attack {target}")
    if "ai_will_do" not in central_war:
        issues.append("ADISCORD_vorkerland_consolidate_central_border: AI cannot take the war decision")

    reunification_war = named_block(decisions, "ADISCORD_vorkerland_continue_reunification")
    if not reunification_war or "random_neighbor_country" not in reunification_war or "declare_war_on" not in reunification_war:
        issues.append("ADISCORD_vorkerland_continue_reunification: war is not gated by an actual common border")
    if "ai_will_do" not in reunification_war:
        issues.append("ADISCORD_vorkerland_continue_reunification: AI cannot take the war decision")
    if "ADISCORD_vorkerland_settle_regional_border" in decisions:
        issues.append("post-opening regional neighbour war decision survived")
    if "ADISCORD_vorkerland_is_local_rival_for_ROOT" in triggers:
        issues.append("post-opening regional neighbour war target trigger survived")
    reunification_allowed = named_block(
        named_block(decisions, "ADISCORD_vorkerland_continue_reunification"), "allowed"
    )
    if "NOT = { tag = WRK }" not in reunification_allowed:
        issues.append("WRK can still launch post-victory reunification wars")

    for name, block in (
        ("central", named_block(triggers, "ADISCORD_vorkerland_is_central_target_for_ROOT")),
        ("reunification", named_block(triggers, "ADISCORD_vorkerland_is_reunification_target_for_ROOT")),
    ):
        if "has_war = no" not in block:
            issues.append(f"{name} target can be dogpiled into a merged war")

    try:
        states = map_regions.load_states()
        province_types, colors = map_regions.load_province_definitions()
        physical_provinces = map_regions.load_province_adjacency(
            province_types, colors, include_special_adjacencies=False
        )
        physical_states = map_regions.build_state_adjacency(states, physical_provinces)
        collapse_tags = set().union(*(
            set(pair) for pair in INITIAL_CENTRAL_BORDER_PAIRS | INITIAL_LOCAL_BORDER_PAIRS
        ))
        assigned = {tag: initial_tag_states(effects, tag) for tag in collapse_tags}

        def physical_borders(pair: frozenset[str]) -> set[frozenset[int]]:
            first, second_tag = sorted(pair)
            return {
                frozenset((first_state, second_state))
                for first_state in assigned[first]
                for second_state in assigned[second_tag]
                if second_state in physical_states.get(first_state, set())
            }

        for pair in INITIAL_CENTRAL_BORDER_PAIRS | INITIAL_LOCAL_BORDER_PAIRS:
            if not physical_borders(pair):
                issues.append(f"initial war pair has no physical state border: {'-'.join(sorted(pair))}")
        if physical_borders(frozenset(("ZAO", "WPA"))):
            issues.append("ZAO-WPA is incorrectly treated as an initial physical-border pair")
        if physical_borders(frozenset(("VLA", "TGD"))) != {frozenset((74, 105))}:
            issues.append("TGD-VLA physical border drifted from states 105/74")
        if physical_borders(frozenset(("EBA", "TGD"))) != {
            frozenset((105, 311)), frozenset((105, 312))
        }:
            issues.append("TGD-EBA physical border drifted from states 105/311-312")
    except (OSError, ValueError, KeyError, RuntimeError) as error:
        issues.append(f"cannot audit physical collapse borders: {error}")

    if any(token in outbreak for token in ("create_faction", "add_to_faction")):
        issues.append("collapse setup creates a faction and can merge initial wars")
    macri_pact = named_block(decisions, "ADISCORD_vorkerland_macri_piv_pact")
    for token in (
        "controls_state = 74", "controls_state = 105", "controls_state = 197",
        "NOT = { country_exists = VLA }", "NOT = { country_exists = TGD }",
        "available = { has_war = no }",
    ):
        if token not in macri_pact:
            issues.append(f"Macri pact can merge an unfinished regional war: missing {token}")

    ivn = named_block(decisions, "ADISCORD_ivanland_limited_intervention")
    for token in (
        "selectable_mission = yes",
        "days_mission_timeout = 240",
        "target = IBL",
        "target = PWR",
        "type = take_state_focus",
        "generator = { 91 }",
        "generator = { 90 }",
        "intervention_success",
        "intervention_failure",
    ):
        if token not in ivn:
            issues.append(f"Ivanland timed decision is missing {token}")
    if "annex_everything" in ivn or ivn.count("type = take_state_focus") != 2:
        issues.append("Ivanland intervention must use exactly two fixed-state wargoals, never annex_everything")
    mandate = named_block(effects, "ADISCORD_vorkerland_setup_ivanland_mandate")
    if mandate.count("puppet =") != 1 or "puppet = IBA" not in mandate:
        issues.append("Ivanland success must create exactly one IBA puppet")
    ivn_history = read(root, "history/countries/IVN - IvanLand.txt", issues)
    iba_history = read(root, "history/countries/IBA - Ivanland Northern Mandate.txt", issues)
    if "recruit_character = IBA_Matvey_Mateusk" in ivn_history or "recruit_character = IBA_Matvey_Mateusk" not in iba_history:
        issues.append("Matvey Mateusk must be recruited directly by IBA history")
    for token in (
        "90 = { add_core_of = IBA add_claim_by = IBA",
        "71 = { add_claim_by = IBA }",
        "ADISCORD_vorkerland_appoint_mateusk = yes",
    ):
        if token not in mandate:
            issues.append(f"Norvane setup is missing {token}")
    mateusk = named_block(effects, "ADISCORD_vorkerland_appoint_mateusk")
    for token in (
        "promote_character = {",
        "character = IBA_Matvey_Mateusk",
        "portrait = GFX_portrait_IBA_Matvey_Mateusk",
        "ideology = pragmatism_ideology",
        "set_country_leader_portrait = {",
        "ADISCORD_vorkerland_mateusk_character_repair_v2",
    ):
        if token not in mateusk:
            issues.append(f"Mateusk appointment is missing {token}")
    if "create_country_leader" in mateusk:
        issues.append("Mateusk appointment still uses the legacy leader API")
    if "recruit_character" in mateusk:
        issues.append("Mateusk appointment uses recruit_character outside history")
    owned_by_iba = set(re.findall(r"transfer_state\s*=\s*(\d+)", mandate))
    if owned_by_iba != {"90", "91"} or "transfer_state = 71" in mandate:
        issues.append(f"Norvane ownership allowlist drifted from states 90/91: {sorted(owned_by_iba)}")
    war_cleanup = named_block(effects, "ADISCORD_vorkerland_end_ivanland_intervention_wars")
    for pair in (("IVN", "PWR"), ("IVN", "IBL"), ("IVN", "IBA"), ("IBA", "WRK"), ("IBA", "VAD"), ("IBA", "TVA"), ("IBA", "PWR"), ("IBA", "IBL"), ("IBL", "PWR")):
        if f"has_war_with = {pair[1]}" not in named_block(war_cleanup, pair[0]):
            issues.append(f"Ivanland cleanup does not white-peace {pair[0]}-{pair[1]}")
    success = named_block(effects, "ADISCORD_vorkerland_ivanland_intervention_success")
    if success.count("ADISCORD_vorkerland_end_ivanland_intervention_wars = yes") < 2 or "NOT = { has_global_flag = ADISCORD_vorkerland_ivanland_intervention_resolved }" not in success:
        issues.append("Ivanland success is not idempotent or does not clean wars before and after setup")
    if "Ivanland intervention resolved: SUCCESS" not in success:
        issues.append("Ivanland success has no deterministic outcome log")
    if "clr_global_flag = ADISCORD_vorkerland_ivanland_intervention_failed" not in success:
        issues.append("Ivanland success does not clear the mutually exclusive failure flag")
    failure = named_block(effects, "ADISCORD_vorkerland_ivanland_intervention_failure")
    for token in (
        "NOT = { has_global_flag = ADISCORD_vorkerland_ivanland_intervention_resolved }",
        "ruling_party = etatism",
        "GFX_portrait_IVN_Vadim_Ivanchik_after_retreat",
        "annex_country = { target = IBA",
        "transfer_state = 90",
        "transfer_state = 91",
        "ADISCORD_vorkerland_vadim_etatist_role_added",
        "Ivanland intervention resolved: FAILURE",
    ):
        if token not in failure:
            issues.append(f"Ivanland failure is missing {token}")
    if "clr_global_flag = ADISCORD_vorkerland_ivanland_intervention_succeeded" not in failure:
        issues.append("Ivanland failure does not clear the mutually exclusive success flag")

    monthly = named_block(on_actions, "on_monthly")
    for token in (
        "tag = IBA",
        "has_country_leader = {",
        "character = IBA_Matvey_Mateusk",
        "ruling_only = yes",
        "ADISCORD_vorkerland_appoint_mateusk = yes",
        "ADISCORD_vorkerland_end_ivanland_intervention_wars = yes",
        "tag = WRK",
        "ADISCORD_vorkerland_appoint_joint_council = yes",
    ):
        if token not in monthly:
            issues.append(f"Vorkerland save repair is missing {token}")
    joint = named_block(effects, "ADISCORD_vorkerland_appoint_joint_council")
    for token in (
        "promote_character = {",
        "character = WRK_VAD_Joint_Council",
        "portrait = GFX_portrait_WRK_Temporary_Government",
        "ADISCORD_vorkerland_joint_council_character_repair_v2",
    ):
        if token not in joint:
            issues.append(f"joint-government appointment is missing {token}")
    if "create_country_leader" in joint:
        issues.append("joint-government appointment still uses the legacy leader API")
    if "recruit_character" in joint:
        issues.append("joint-government appointment uses recruit_character outside history")

    for news_id, outcome, shown_flag, completion_token in (
        (
            "ADISCORD_vorkerland_news.1",
            success,
            "ADISCORD_vorkerland_ivanland_success_news_shown",
            "ADISCORD_vorkerland_setup_ivanland_mandate = yes",
        ),
        (
            "ADISCORD_vorkerland_news.2",
            failure,
            "ADISCORD_vorkerland_ivanland_failure_news_shown",
            "portrait = GFX_portrait_IVN_Vadim_Ivanchik_after_retreat",
        ),
    ):
        definition = re.search(
            rf"(?ms)^news_event\s*=\s*\{{\s*id\s*=\s*{re.escape(news_id)}\b"
            rf"(.*?)(?=^news_event\s*=\s*\{{|\Z)",
            events,
        )
        if events.count(f"id = {news_id}") != 1 or not definition:
            issues.append(f"{news_id}: expected exactly one world-news definition")
            continue
        body = definition.group(1)
        for token in (
            "hidden = yes", "is_triggered_only = yes", "fire_only_once = yes",
            f"title = {news_id}.t", f"desc = {news_id}.d",
            f"option = {{ name = {news_id}.a }}",
        ):
            if token not in body:
                issues.append(f"{news_id}: definition is missing {token}")
        if effects.count(f"news_event = {{ id = {news_id} }}") != 1:
            issues.append(f"{news_id}: expected exactly one production call site")
        for token in (
            f"NOT = {{ has_global_flag = {shown_flag} }}",
            f"set_global_flag = {shown_flag}",
            f"news_event = {{ id = {news_id} }}",
        ):
            if token not in outcome:
                issues.append(f"{news_id}: guarded outcome route is missing {token}")
        if outcome.find(completion_token) > outcome.find(f"news_event = {{ id = {news_id} }}"):
            issues.append(f"{news_id}: news fires before the outcome is fully applied")
        call = named_block(outcome, "news_event")
        if any(token in call for token in ("hours =", "days =", "random_hours", "random_days")):
            issues.append(f"{news_id}: outcome news call is delayed or randomized")
        for suffix in ("t", "d", "a"):
            if f"  {news_id}.{suffix}:" not in news_loc:
                issues.append(f"{news_id}: missing Russian localisation key {news_id}.{suffix}")
    proclamation = named_block(decisions, "ADISCORD_ivanland_proclaim_norvane")
    for token in (
        "controls_state = 90",
        "controls_state = 91",
        "ADISCORD_vorkerland_setup_ivanland_mandate = yes",
        "ADISCORD_vorkerland_ivanland_mandate_proclaimed",
        "factor = 400",
    ):
        if token not in proclamation:
            issues.append(f"Norvane proclamation decision is missing {token}")

    if "ADISCORD_vorkerland_erased_nations" not in effects or "ADISCORD_vorkerland_erased_nations" not in ideas:
        issues.append("cultural-erasure legacy is not represented as a national spirit")
    erased_nations = named_block(ideas, "ADISCORD_vorkerland_erased_nations")
    if "picture = generic_oppression" not in erased_nations:
        issues.append("cultural-erasure spirit must use the registered generic_oppression picture")
    macri_mission = named_block(
        ideas, "ADISCORD_vorkerland_piv_macri_volunteer_mission"
    )
    if "picture = generic_volunteer_expedition_bonus" not in macri_mission:
        issues.append(
            "Macri volunteer mission must use the registered generic_volunteer_expedition_bonus picture"
        )
    prepare = named_block(effects, "ADISCORD_vorkerland_prepare_conflict_country")
    initial = named_block(effects, "ADISCORD_vorkerland_prepare_initial_combatants")
    removed_by_prepare = set(re.findall(r"remove_ideas\s*=\s*([A-Za-z0-9_]+)", prepare))
    expected_prepare_removals = {
        "WRK_ashes_of_the_crown",
        "WRK_hourglass_of_discord",
        "WRK_constitution_of_the_republic",
        "VLA_national_spirit",
        "ADISCORD_vorkerland_erased_nations",
    }
    if removed_by_prepare != expected_prepare_removals:
        issues.append(
            "collapse spirit cleanup allowlist drifted: "
            f"{sorted(removed_by_prepare)}"
        )
    for forbidden in ("every_country", "every_other_country", "swap_ideas"):
        if forbidden in prepare:
            issues.append(f"collapse spirit cleanup must not use {forbidden}")
    for tag in ("WRK", "VAD", "VLA", "ZAO", "PWR", "ROM", "SOL", "TRU"):
        if f"tag = {tag}" not in prepare:
            issues.append(f"collapse spirit cleanup has no explicit {tag} guard")
    if not re.search(
        r"tag\s*=\s*VLA.*?remove_ideas\s*=\s*VLA_national_spirit.*?"
        r"add_ideas\s*=\s*ADISCORD_vorkerland_republics_from_the_ruins",
        prepare,
        re.DOTALL,
    ):
        issues.append("VLA does not replace its obsolete district spirit in the same guarded branch")
    republic_tags = {"ZAO", "PWR", "VLA", "ROM", "SOL", "TRU"}
    mobilized_tags = {"TVA", "EYR", "EGC", "PSD", "DVA", "SRA", "IBL", "IBA", "CSL"}
    for tag in republic_tags | mobilized_tags:
        if f"tag = {tag}" not in prepare:
            issues.append(f"{tag}: replacement spirit has no explicit preparation guard")
    for spirit in (
        "ADISCORD_vorkerland_republics_from_the_ruins",
        "ADISCORD_vorkerland_mobilized_periphery",
    ):
        if f"add_ideas = {spirit}" not in prepare:
            issues.append(f"collapse preparation does not add replacement spirit {spirit}")

    collapse_runtime = "\n".join((effects, map_effects, on_actions, events, decisions))
    collapse_removals = set(
        re.findall(r"remove_ideas\s*=\s*([A-Za-z0-9_]+)", collapse_runtime)
    )
    allowed_collapse_removals = expected_prepare_removals | {
        "ADISCORD_vorkerland_piv_macri_volunteer_mission",
        "ADISCORD_vorkerland_tgd_grid_collapse",
    }
    unexpected_removals = collapse_removals - allowed_collapse_removals
    if unexpected_removals:
        issues.append(f"collapse runtime removes unrelated ideas: {sorted(unexpected_removals)}")
    for unrelated in (
        "IVN_national_spirit", "RUS_national_spirit", "PIV_national_spirit",
        "NAM_national_spirit", "NOD_home_of_hedonist_revolution",
        "STP_hedonism_with_no_bondaries", "VAL_worldwide_famous_weponry",
    ):
        if unrelated in collapse_removals:
            issues.append(f"collapse runtime can remove unrelated national spirit {unrelated}")
    for audio_effect in (
        "ADISCORD_vorkerland_play_collapse_superevent_audio",
        "ADISCORD_vorkerland_play_local_superevent_audio",
    ):
        audio = named_block(map_effects, audio_effect)
        if "every_country" not in audio or "limit = { is_ai = no }" not in audio:
            issues.append(f"{audio_effect}: global audio routing guard drifted")
        if re.search(r"remove_ideas|swap_ideas|remove_dynamic_modifier", audio):
            issues.append(f"{audio_effect}: audio routing mutates country ideas")
    if "add_ideas = ADISCORD_vorkerland_erased_nations" in prepare:
        issues.append("cultural-erasure spirit still leaks to every successor")
    if effects.count("add_ideas = ADISCORD_vorkerland_erased_nations") != 1 or not re.search(
        r"WRK\s*=\s*\{[^{}]*add_ideas\s*=\s*ADISCORD_vorkerland_erased_nations",
        initial,
        re.DOTALL,
    ):
        issues.append("cultural-erasure spirit must be added only to WRK")

    unique_spirits = {
        "VAD": "ADISCORD_vorkerland_vad_imperial_chancery",
        "REPUBLICS": "ADISCORD_vorkerland_republics_from_the_ruins",
        "PERIPHERY": "ADISCORD_vorkerland_mobilized_periphery",
        "TGD_CRISIS": "ADISCORD_vorkerland_tgd_grid_collapse",
        "TGD": "ADISCORD_vorkerland_tgd_living_grid",
        "EBA": "ADISCORD_vorkerland_eba_free_quays",
        "ZTA": "ADISCORD_vorkerland_zta_golden_river_order",
        "WPA": "ADISCORD_vorkerland_wpa_municipal_compact",
        "WPS": "ADISCORD_vorkerland_wps_factory_councils",
    }
    for tag, spirit in unique_spirits.items():
        idea = named_block(ideas, spirit)
        if not idea or "picture =" not in idea or "modifier =" not in idea:
            issues.append(f"{tag}: unique collapse spirit {spirit} is incomplete")
        if f"add_ideas = {spirit}" not in effects + decisions:
            issues.append(f"{tag}: unique collapse spirit {spirit} is not applied")
        if f" {spirit}:" not in loc or f" {spirit}_desc:" not in loc:
            issues.append(f"{tag}: unique collapse spirit {spirit} lacks Russian localisation")

    for tag in ("TVA", "EYR", "EGC", "TGD", "EBA", "PSD", "DVA", "ZTA", "WPA", "WPS"):
        setup = named_block(effects, f"ADISCORD_vorkerland_setup_{tag.lower()}")
        manpower = re.search(r"add_manpower\s*=\s*(\d+)", setup)
        reserve = re.search(r"add_equipment_to_stockpile\s*=\s*\{[^{}]*amount\s*=\s*(\d+)", setup)
        if not manpower or int(manpower.group(1)) < 3000:
            issues.append(f"{tag}: collapse OOB lacks a useful manpower reserve")
        if not reserve or int(reserve.group(1)) < 160:
            issues.append(f"{tag}: collapse OOB lacks a useful rifle reserve")
    eba_setup = named_block(effects, "ADISCORD_vorkerland_setup_eba")
    if "add_manpower = 10000" not in eba_setup or "amount = 1100" not in eba_setup:
        issues.append("EBA: approved collapse reserve is missing")
    eba_oob = read(root, "history/units/EBA_vorkerland_collapse.txt", issues)
    eba_locations = [int(value) for value in re.findall(r"location\s*=\s*(\d+)", eba_oob)]
    if sorted(eba_locations) != sorted([16623, 16623, 16617, 16637]):
        issues.append("EBA: militia deployment is not distributed across the republic")
    for tag in ("WRK", "VAD"):
        country = re.search(rf"{tag}\s*=\s*\{{(.*?)\n\s*\}}", initial, re.DOTALL)
        if not country or "add_manpower = 8000" not in country.group(1) or "amount = 600" not in country.group(1):
            issues.append(f"{tag}: central claimant reserve is missing")
    legacy_reserves = {
        "ZAO": (4000, 850), "PWR": (8000, 1600), "VLA": (8000, 1800),
        "ROM": (6000, 1200), "SOL": (3000, 500), "TRU": (7000, 1400),
    }
    for tag, (manpower, rifles) in legacy_reserves.items():
        country = named_block(initial, tag)
        if f"add_manpower = {manpower}" not in country or f"amount = {rifles}" not in country:
            issues.append(f"{tag}: finite collapse reserve is missing")
    tva_oob = read(root, "history/units/TVA_vorkerland_collapse.txt", issues)
    if tva_oob.count("division = {") != 5:
        issues.append("TVA must start the collapse with exactly five militia divisions")

    local_oobs = {
        "PWR": "history/units/PWR.txt",
        "PSD": "history/units/PSD_vorkerland_collapse.txt",
        "ROM": "history/units/ROM.txt",
        "DVA": "history/units/DVA_vorkerland_collapse.txt",
        "TRU": "history/units/TRU.txt",
        "ZTA": "history/units/ZTA_vorkerland_collapse.txt",
    }
    for tag, path in local_oobs.items():
        oob = read(root, path, issues)
        equipment = [
            float(value)
            for value in re.findall(r"start_equipment_factor\s*=\s*([\d.]+)", oob)
        ]
        if oob.count("division = {") != 3 or len(equipment) != 3 or min(equipment, default=0) < 0.55:
            issues.append(f"{tag}: local war OOB must contain three supplied formations")

    local_capitals = {
        "PWR": (71, "16591"), "PSD": (194, "2339"),
        "ROM": (73, "16571"), "DVA": (145, "6729"),
        "TRU": (80, "3083"), "ZTA": (199, "12930"),
    }
    supply_nodes = {
        line.split()[1]
        for line in read(root, "map/supply_nodes.txt", issues).splitlines()
        if len(line.split()) == 2
    }
    railway_provinces = set(
        re.findall(r"\b\d+\b", read(root, "map/railways.txt", issues))
    )
    for tag, (state_id, hub) in local_capitals.items():
        paths = list((root / "history" / "states").glob(f"{state_id}-*.txt"))
        if len(paths) != 1:
            issues.append(f"{tag}: capital state {state_id} is missing or duplicated")
            continue
        state = paths[0].read_text(encoding="utf-8-sig")
        supply = re.search(r"local_supplies\s*=\s*([\d.]+)", state)
        if not supply or float(supply.group(1)) < 3.0:
            issues.append(f"{tag}: capital state lacks local wartime supply")
        if not re.search(r"arms_factory\s*=\s*2\b", state):
            issues.append(f"{tag}: capital state must have two military factories")
        if hub not in supply_nodes or hub not in railway_provinces:
            issues.append(f"{tag}: capital supply hub {hub} is missing from the rail network")

    cosmetics = named_block(effects, "ADISCORD_vorkerland_apply_claimant_cosmetics")
    for token in (
        "ROM = { ADISCORD_vorkerland_sync_independence_cosmetic = yes }",
        "TRU = { ADISCORD_vorkerland_sync_independence_cosmetic = yes }",
        "ZAO = { ADISCORD_vorkerland_sync_independence_cosmetic = yes }",
        "PWR = { set_cosmetic_tag = PWR_rimat_republic }",
        "VLA = { set_cosmetic_tag = VLA_volnograd_republic }",
    ):
        if token not in cosmetics:
            issues.append(f"collapse cosmetic is not applied: {token}")
    cosmetic_sync = named_block(effects, "ADISCORD_vorkerland_sync_independence_cosmetic")
    for token in (
        "is_subject = yes", "drop_cosmetic_tag = yes",
        "set_cosmetic_tag = ROM_frealor_republic",
        "set_cosmetic_tag = TRU_zolotorevsk_republic",
        "set_cosmetic_tag = ZAO_zaozersk_republic",
    ):
        if token not in cosmetic_sync:
            issues.append(f"independence cosmetic synchronizer is missing {token}")
    for hook in ("on_puppet", "on_release_as_puppet", "on_release_as_free", "on_monthly"):
        if "ADISCORD_vorkerland_sync_independence_cosmetic = yes" not in named_block(on_actions, hook):
            issues.append(f"{hook} does not synchronize republic/dependency cosmetics")
    loyalist = named_block(decisions, "ADISCORD_vorkerland_restore_loyalist_district")
    if set(re.findall(r"tag\s*=\s*([A-Z]{3})", named_block(loyalist, "allowed"))) != {"ZAO", "PWR", "VLA"}:
        issues.append("only ZAO/PWR/VLA may voluntarily restore loyalist district status")
    for token in (
        "is_subject = no", "has_war = no", "is_subject = no", "target = ROOT",
        "autonomy_state = autonomy_district_in_Vorkerland", "drop_cosmetic_tag = yes", "factor = 350",
    ):
        if token not in loyalist:
            issues.append(f"loyalist restoration decision is missing {token}")

    if "recruit_character = WRK_Anton_Bagley" in effects or "recruit_character = WRK_VAD_Joint_Council" in effects:
        issues.append("collapse runtime effects still recruit WRK characters outside history")
    wrk_history = read(root, "history/countries/WRK - WorkerLand.txt", issues)
    for character in ("WRK_Anton_Bagley", "WRK_VAD_Joint_Council"):
        if f"recruit_character = {character}" not in wrk_history:
            issues.append(f"WRK history does not recruit {character}")


def validate_ai(root: Path, issues: list[str]) -> None:
    ai = read(root, "common/ai_strategy/ADISCORD_vorkerland_collapse_ai.txt", issues)
    defines = read(root, "common/defines/ADISCORD_defines_changes.lua", issues)
    if not balanced(ai):
        issues.append("collapse AI: unbalanced braces or quote")
    for stale in STALE_SYSTEM_TOKENS:
        if stale in ai:
            issues.append(f"collapse AI still contains dead token {stale}")
    economy = named_block(ai, "ADISCORD_vorkerland_collapse_war_economy")
    if "type = ai_wanted_divisions_factor value = 8" not in economy:
        issues.append("collapse AI wanted-division factor must stay at the moderate value 8")
    if "ADISCORD_vorkerland_collapse_front_commitment" in ai:
        issues.append("obsolete all-tags front commitment survived")
    if "ADISCORD_vorkerland_dynamic_regional_front_commitment" in ai or "country_trigger = {" in ai:
        issues.append("removed dynamic regional front fallback survived")
    for token in (
        "NDefines.NMilitary.PLAN_EXECUTE_RUSH = -200",
        "NDefines.NAI.PLAN_ATTACK_MIN_ORG_FACTOR_HIGH = 0.15",
        "NDefines.NAI.PLAN_ATTACK_MIN_STRENGTH_FACTOR_HIGH = 0.25",
        "NDefines.NAI.FRONT_EVAL_UNIT_SUPPLY_AND_ORG_LACK_IMPACT = 0.2",
        "NDefines.NAITheatre.AI_THEATRE_SUPPLY_CRISIS_LIMIT = 0.0",
    ):
        if token not in defines:
            issues.append(f"collapse anti-freeze defines are missing {token}")

    for strategy in re.findall(r"ai_strategy\s*=\s*\{([^{}]*)\}", ai, re.DOTALL):
        if "type = front_control" in strategy or "type = front_unit_request" in strategy:
            if len(re.findall(r"\btag\s*=", strategy)) != 1:
                issues.append("front scalar strategy must contain exactly one target tag")
    regional_pairs = (
        ("ZAO", "WPA"), ("WPA", "ZAO"), ("WPA", "WPS"), ("WPS", "WPA"),
        ("WPS", "ZAO"), ("ZAO", "WPS"), ("PWR", "PSD"), ("PSD", "PWR"),
        ("VLA", "EBA"), ("EBA", "VLA"), ("ROM", "DVA"), ("DVA", "ROM"),
        ("VLA", "TGD"), ("TGD", "VLA"), ("EBA", "TGD"), ("TGD", "EBA"),
        ("SOL", "SRA"), ("SRA", "SOL"), ("TRU", "ZTA"), ("ZTA", "TRU"),
    )
    supply_aware_pairs = {
        ("PWR", "PSD"), ("PSD", "PWR"),
        ("ROM", "DVA"), ("DVA", "ROM"),
        ("TRU", "ZTA"), ("ZTA", "TRU"),
    }
    for attacker, defender in regional_pairs:
        front = named_block(ai, f"ADISCORD_vorkerland_front_{attacker.lower()}_{defender.lower()}")
        for token in (
            f"allowed = {{ tag = {attacker} }}",
            f"has_war_with = {defender}",
            f"front_unit_request tag = {defender}",
            f"front_control tag = {defender}",
        ):
            if token not in front:
                issues.append(f"{attacker}-{defender} anti-freeze front is missing {token}")
        if (attacker, defender) in supply_aware_pairs:
            for token in (
                f"front_unit_request tag = {defender} value = 75",
                "execution_type = careful",
                "manual_attack = no",
            ):
                if token not in front:
                    issues.append(f"{attacker}-{defender} supply-aware front is missing {token}")
            for forbidden in ("execution_type = rush", "manual_attack = yes"):
                if forbidden in front:
                    issues.append(f"{attacker}-{defender} supply-aware front still has {forbidden}")
        else:
            for token in ("execution_type = rush", "manual_attack = yes"):
                if token not in front:
                    issues.append(f"{attacker}-{defender} anti-freeze front is missing {token}")
    piv = named_block(ai, "ADISCORD_vorkerland_piv_support_macri")
    for token in ("tag = PIV", "is_subject = no", "send_volunteers_desire", "id = EBA", "value = 1000"):
        if token not in piv:
            issues.append(f"PIV volunteer strategy is missing {token}")


def validate_outcomes(root: Path, issues: list[str]) -> None:
    maps = read(root, "common/scripted_effects/ADISCORD_vorkerland_collapse_map_effects.txt", issues)
    triggers = read(root, "common/scripted_triggers/ADISCORD_vorkerland_collapse_triggers.txt", issues)
    on_actions = read(root, "common/on_actions/01_ADISCORD_vorkerland_collapse_on_actions.txt", issues)
    events = read(root, "events/ADISCORD_vorkerland_collapse_events.txt", issues)
    for name, tag in (("worker", "WRK"), ("vlad", "VAD"), ("dorian", "TVA")):
        block = named_block(maps, f"ADISCORD_vorkerland_apply_{name}_map")
        for forbidden in ("transfer_state", "annex_country", "puppet =", "set_autonomy"):
            if forbidden in block:
                issues.append(f"{name} central victory still performs automatic {forbidden}")
        for required in ("ADISCORD_vorkerland_central_war_finished", "ADISCORD_vorkerland_central_unifier", tag):
            if required not in block:
                issues.append(f"{name} central victory is missing {required}")

    reunification = named_block(triggers, "ADISCORD_vorkerland_is_reunification_target_for_ROOT")
    if "tag = ROM" not in reunification or "tag = TRU" not in reunification or "ROOT = { tag = VAD }" not in reunification:
        issues.append("ROM/TRU must be targets only for the imperial VAD claimant")
    if "ADISCORD_vorkerland_recognize_free_republics" not in read(root, "common/decisions/ADISCORD_vorkerland_collapse_decisions.txt", issues):
        issues.append("WRK cannot recognise the free ROM/TRU republics")
    central = named_block(triggers, "ADISCORD_vorkerland_is_central_claimant")
    if "tag = TGD" in central or set(re.findall(r"tag\s*=\s*([A-Z]{3})", central)) != {"WRK", "VAD", "TVA", "EYR", "EGC"}:
        issues.append("TGD must be outside the central claimant campaign")
    regional = named_block(triggers, "ADISCORD_vorkerland_is_regional_combatant")
    if not all(f"tag = {tag}" in regional for tag in ("VLA", "EBA", "TGD")):
        issues.append("TGD/VLA/EBA peripheral country classification is missing")
    for candidate in ("worker", "vlad", "dorian"):
        victory = named_block(triggers, f"ADISCORD_vorkerland_{candidate}_victory_candidate")
        if "ADISCORD_vorkerland_tgd_defeated" in victory:
            issues.append(f"{candidate} central victory still requires peripheral TGD")
    capitulation = named_block(on_actions, "on_capitulation")
    for token in (
        "set_global_flag = skip_default_capitulation",
        "ROOT = { OR = { tag = IBL tag = PWR } }",
        "ROOT = { tag = IVN }",
        "ADISCORD_vorkerland_ivanland_intervention_success = yes",
        "ADISCORD_vorkerland_ivanland_intervention_failure = yes",
        "IVN = { white_peace = ROOT }",
    ):
        if token not in capitulation:
            issues.append(f"Ivanland capitulation guard is missing {token}")
    for hook in ("on_capitulation", "on_monthly", "on_state_control_changed", "ADISCORD_vorkerland_check_central_outcome"):
        if hook not in on_actions:
            issues.append(f"central outcome fallback is missing {hook}")
    for stale in (
        "ADISCORD_vorkerland_collapse.23",
        "ADISCORD_vorkerland_apply_fragmented_map",
        "ADISCORD_vorkerland_fragmented",
    ):
        if stale in events + maps:
            issues.append(f"removed fragmentation timeout survived: {stale}")


def validate_exhaustion(root: Path, issues: list[str]) -> None:
    on_actions = read(root, "common/on_actions/01_ADISCORD_vorkerland_collapse_on_actions.txt", issues)
    effects = read(root, "common/scripted_effects/ADISCORD_vorkerland_collapse_effects.txt", issues)
    dynamic = read(
        root,
        "common/dynamic_modifiers/ADISCORD_vorkerland_collapse_dynamic_modifiers.txt",
        issues,
    )
    decisions = read(root, "common/decisions/ADISCORD_scenario_debug_decisions.txt", issues)
    categories = read(
        root,
        "common/decisions/categories/ADISCORD_scenario_debug_categories.txt",
        issues,
    )

    monthly = named_block(on_actions, "on_monthly")
    for token in (
        "tag = WRK",
        "tag = VAD",
        "ADISCORD_vorkerland_update_civil_war_exhaustion = yes",
    ):
        if token not in monthly:
            issues.append(f"WRK/VAD monthly exhaustion routing is missing {token}")
    for forbidden in ("every_country", "every_state"):
        if forbidden in monthly:
            issues.append(f"monthly exhaustion routing must not use {forbidden}")
    if "on_daily" in on_actions:
        issues.append("Vorkerland exhaustion must not add a daily pulse")

    update = named_block(effects, "ADISCORD_vorkerland_update_civil_war_exhaustion")
    compact_update = re.sub(r"\s+", " ", update)
    for token in (
        "ADISCORD_vorkerland_civil_war_casualties_snapshot_k",
        "ADISCORD_vorkerland_civil_war_casualties_delta_k",
        "value = casualties_k",
        "has_war_with = VAD",
        "has_war_with = WRK",
        "value = 2",
        "value = -8",
        "ADISCORD_vorkerland_refresh_civil_war_exhaustion = yes",
    ):
        if token not in update:
            issues.append(f"civil-war exhaustion update is missing {token}")
    for token in ("min = 0 max = 100", "min = 0 max = 10000"):
        if token not in compact_update:
            issues.append(f"civil-war exhaustion update is missing {token}")
    for threshold, gain in ((100, 6), (25, 3), (5, 1)):
        if not re.search(
            rf"ADISCORD_vorkerland_civil_war_casualties_delta_k\s+value\s*=\s*{threshold}\b.*?"
            rf"ADISCORD_vorkerland_civil_war_exhaustion\s+value\s*=\s*{gain}\b",
            update,
            re.DOTALL,
        ):
            issues.append(f"casualty threshold {threshold}k does not add {gain} exhaustion")
    if "global.ADISCORD_vorkerland_civil_war_exhaustion" in update:
        issues.append("WRK and VAD exhaustion must remain country-scoped, not global")

    refresh = named_block(effects, "ADISCORD_vorkerland_refresh_civil_war_exhaustion")
    for token in (
        "value = -0.002",
        "value = -0.001",
        "value = -0.0005",
        "force_update_dynamic_modifier = yes",
        "remove_dynamic_modifier",
    ):
        if token not in refresh:
            issues.append(f"civil-war exhaustion refresh is missing {token}")
    reset = named_block(effects, "ADISCORD_vorkerland_reset_civil_war_exhaustion")
    for token in (
        "value = casualties_k",
        "ADISCORD_vorkerland_refresh_civil_war_exhaustion = yes",
    ):
        if token not in reset:
            issues.append(f"civil-war exhaustion reset is missing {token}")

    modifier = named_block(dynamic, "ADISCORD_vorkerland_civil_war_exhaustion")
    for token in (
        "war_support_factor",
        "stability_factor",
        "industrial_capacity_factory",
        "army_morale_factor",
        "surrender_limit",
    ):
        if token not in modifier:
            issues.append(f"civil-war exhaustion modifier is missing {token}")
    for forbidden in ("factory_output =", "army_attack_factor", "army_org_factor"):
        if forbidden in modifier:
            issues.append(f"civil-war exhaustion must not refreeze fronts with {forbidden}")

    category = named_block(categories, "ADISCORD_scenario_debug_category")
    if "visible = { is_debug = yes }" not in category:
        issues.append("scenario debug category is no longer debug-only")
    for key in (
        "ADISCORD_debug_add_vorkerland_war_exhaustion",
        "ADISCORD_debug_reset_vorkerland_war_exhaustion",
    ):
        block = named_block(decisions, key)
        for token in ("tag = WRK", "tag = VAD", "ai_will_do = { factor = 0 }"):
            if token not in block:
                issues.append(f"{key} is missing {token}")

    collapse_loc_path = root / "localisation/russian/ADISCORD_vorkerland_collapse_l_russian.yml"
    debug_loc_path = root / "localisation/russian/ADISCORD_scenario_debug_l_russian.yml"
    for path, label in ((collapse_loc_path, "collapse"), (debug_loc_path, "scenario debug")):
        if not path.exists() or not path.read_bytes().startswith(b"\xef\xbb\xbf"):
            issues.append(f"{label} Russian localisation must retain UTF-8 BOM")
    collapse_loc = collapse_loc_path.read_text(encoding="utf-8-sig") if collapse_loc_path.exists() else ""
    debug_loc = debug_loc_path.read_text(encoding="utf-8-sig") if debug_loc_path.exists() else ""
    if "[?ADISCORD_vorkerland_civil_war_exhaustion|0]/100" not in collapse_loc:
        issues.append("civil-war exhaustion localisation does not expose the current score")
    for key in (
        "ADISCORD_debug_add_vorkerland_war_exhaustion:",
        "ADISCORD_debug_reset_vorkerland_war_exhaustion:",
    ):
        if key not in debug_loc:
            issues.append(f"scenario debug localisation is missing {key}")


def validate_superevents(root: Path, issues: list[str]) -> None:
    files = (
        "interface/superevents.gfx",
        "interface/superevents.gui",
        "common/scripted_guis/superevents.txt",
        "common/scripted_localisation/ADISCORD_scripted_loc_superevents.txt",
        "localisation/russian/ADISCORD_superevents_l_russian.yml",
    )
    for relative in files:
        source = read(root, relative, issues)
        for name in ("dirty_opening", "worker_victory", "vlad_victory", "dorian_victory"):
            if f"superevent_vorkerland_{name}" not in source:
                issues.append(f"{relative}: missing Vorkerland {name} binding")


CHECKS = {
    "manifest": validate_manifest,
    "states": validate_states,
    "countries": validate_countries,
    "events": validate_events,
    "ai": validate_ai,
    "outcomes": validate_outcomes,
    "exhaustion": validate_exhaustion,
    "superevents": validate_superevents,
}


def validate(root: Path, section: str | None = None) -> list[str]:
    if section is not None and section not in SECTIONS:
        raise ValueError(f"unknown section {section!r}; choose from {', '.join(SECTIONS)}")
    issues: list[str] = []
    for name in (section,) if section else SECTIONS:
        CHECKS[name](root, issues)
    return issues


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--section", choices=SECTIONS)
    args = parser.parse_args()
    issues = validate(ROOT, args.section)
    if issues:
        print("Vorkerland collapse validation failed:")
        print(*(f"- {issue}" for issue in issues), sep="\n")
        return 1
    print("Vorkerland collapse validation passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
