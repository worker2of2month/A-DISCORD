#!/usr/bin/env python3
"""Read-only gate for the current border-driven Vorkerland collapse."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from PIL import Image

_REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
if str(_REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPOSITORY_ROOT))

try:
    from tools.builders import build_adiscord_strategic_regions as map_regions
    from tools.lib.vorkerland_collapse_manifest import (
        CAPITALS,
        CONTAMINATED_STATES,
        DIRTY_GROUPS,
        EXZ_REMAINDER_GROUPS,
        STATE_PARTITIONS,
        TAGS,
    )
except (ModuleNotFoundError, ImportError):
    from builders import build_adiscord_strategic_regions as map_regions
    from lib.vorkerland_collapse_manifest import (
        CAPITALS,
        CONTAMINATED_STATES,
        DIRTY_GROUPS,
        EXZ_REMAINDER_GROUPS,
        STATE_PARTITIONS,
        TAGS,
    )


ROOT = Path(__file__).resolve().parents[2]
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
    "ADISCORD_vorkerland_ai_consolidation_window",
    "ADISCORD_vorkerland_ai_regional_window",
)
CENTRAL_MINOR_TARGETS = (
    "EYR", "EGC", "RIV", "REV", "YOR", "NDN", "SWB", "VHV", "OSV",
)
INITIAL_CENTRAL_BORDER_PAIRS = {
    frozenset(pair) for pair in (
        ("WKR", "TVA"), ("WKR", "RIV"), ("WKR", "NDN"), ("WKR", "SWB"),
        ("VAD", "EYR"), ("VAD", "EGC"), ("VAD", "YOR"),
        ("TVA", "EYR"), ("TVA", "EGC"), ("TVA", "RIV"),
        ("TVA", "REV"), ("TVA", "SWB"), ("TVA", "OSV"),
        ("EYR", "EGC"), ("EYR", "YOR"), ("EYR", "REV"),
        ("EGC", "RIV"), ("RIV", "NDN"), ("RIV", "VHV"),
        ("REV", "OSV"), ("NDN", "SWB"), ("NDN", "VHV"),
        ("NDN", "OSV"), ("SWB", "OSV"),
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


def event_block(
    source: str, event_id: str, event_type: str = "country_event"
) -> str:
    """Return the balanced top-level event whose own header declares event_id."""
    for match in re.finditer(
        rf"(?m)^{re.escape(event_type)}\s*=\s*\{{",
        source,
    ):
        depth = 0
        quoted = False
        escaped = False
        for index in range(match.end() - 1, len(source)):
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
                    block = source[match.start():index + 1]
                    header = re.match(
                        rf"(?ms)^{re.escape(event_type)}\s*=\s*\{{[^\r\n]*\r?\n\s*"
                        r"id\s*=\s*([^\s}]+)",
                        block,
                    )
                    if header and header.group(1) == event_id:
                        return block
                    break
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
    if len(TAGS) != 28 or len(set(TAGS)) != 28:
        issues.append("manifest must contain 28 unique collapse tags")
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

    tva_victory_points = {
        36: {12227: 60, 16417: 20, 5907: 10},
        37: {16400: 30, 16413: 15, 754: 10},
        38: {16398: 30, 6790: 20, 16425: 10},
        39: {16397: 40, 12985: 20, 16404: 10},
    }
    for state_id, expected in tva_victory_points.items():
        source = state_source(root, state_id, issues)
        actual = {
            int(province): int(value)
            for province, value in re.findall(
                r"victory_points\s*=\s*\{\s*(\d+)\s+(\d+)\s*\}", source
            )
        }
        if actual != expected:
            issues.append(f"TVA state {state_id}: victory-point layout drifted")

    victory_point_loc = read(root, "localisation/russian/victory_points_l_russian.yml", issues)
    for province in set().union(*(set(points) for points in tva_victory_points.values())):
        if not re.search(rf"(?m)^\s*VICTORY_POINTS_{province}:\s*\"[^\"]+\"", victory_point_loc):
            issues.append(f"TVA victory point {province}: missing Russian city name")
    for forbidden in ("\u0443\u0437\u0435\u043b", "\u043f\u0435\u0440\u0438\u043c\u0435\u0442\u0440"):
        if re.search(rf"(?mi)^\s*VICTORY_POINTS_\d+:[^\n]*{forbidden}", victory_point_loc):
            issues.append(f"Vorkerland victory-point name still contains {forbidden}")


def validate_countries(root: Path, issues: list[str]) -> None:
    tags = read(root, "common/country_tags/01_ADISCORD_vorkerland_collapse_tags.txt", issues)
    characters = read(root, "common/characters/ADISCORD_vorkerland_collapse_characters.txt", issues)
    portraits = read(root, "interface/ADISCORD_leader_portraits.gfx", issues)
    random_portraits = read(root, "interface/_random_portraits.gfx", issues)
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
        "PWR_Alexey_Lange": "GFX_Portrait_Forul_Generic_4",
        "SRA_Helio_Marr": "GFX_portrait_SRA_Helio_Marr",
        "ZTA_Viktor_Holt": "GFX_portrait_ZTA_Viktor_Holt",
        "RIV_Mikhail_Arsenyev": "GFX_portrait_RIV_Mikhail_Arsenyev",
        "REV_Elena_Rudenko": "GFX_portrait_REV_Elena_Rudenko",
        "YOR_Pavel_Korin": "GFX_portrait_YOR_Pavel_Korin",
        "NDN_Anna_Lind": "GFX_portrait_NDN_Anna_Lind",
        "SWB_Oskar_Renn": "GFX_portrait_SWB_Oskar_Renn",
        "VHV_Sergey_Melnik": "GFX_portrait_VHV_Sergey_Melnik",
        "OSV_Marina_Volkova": "GFX_portrait_OSV_Marina_Volkova",
    }
    for character, portrait in required_characters.items():
        block = named_block(characters, character)
        if not block or "country_leader" not in block or portrait not in block:
            issues.append(f"{character}: supplied portrait is not used by a country leader")
        if portrait not in portraits and portrait not in random_portraits:
            issues.append(f"{character}: missing portrait sprite {portrait}")

    dorian = named_block(characters, "TVA_Dorian_Worx")
    anton = named_block(characters, "WRK_Anton_Bagley")
    for token in (
        "GFX_portrait_WRK_Dorian_Worx",
        "ideology = technocracy_ideology",
    ):
        if token not in dorian:
            issues.append(f"Dorian Worx identity is missing {token}")
    if "GFX_portrait_WRK_Anton_Bagley" not in anton:
        issues.append("Anton Bagley no longer uses his stable semantic portrait sprite")
    # Preserve the established identities and semantic sprite bindings: Anton
    # is the cowboy-hat utilitarian successor; Dorian is the suited technocrat.
    for sprite, texture in (
        ("GFX_portrait_WRK_Dorian_Worx", "portrait_WRK_Dorian_Worx.png"),
        ("GFX_portrait_WRK_Anton_Bagley", "portrait_WRK_Anton_Bagley.png"),
    ):
        sprite_block = re.search(
            rf'(?ms)spriteType\s*=\s*\{{(?:(?!spriteType\s*=).)*?'
            rf'name\s*=\s*"{re.escape(sprite)}"(?:(?!spriteType\s*=).)*?\}}',
            portraits,
        )
        if not sprite_block or texture not in sprite_block.group(0):
            issues.append(f"{sprite}: expected identity-correct texture {texture}")

    for cosmetic in (
        "WRK_vorkerland_emergency",
        "WRK_vorkerland_utilitarian_republic",
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

    for tag in ("RIV", "REV", "YOR", "NDN", "SWB", "VHV", "OSV"):
        for directory, size in (("", (82, 52)), ("medium", (41, 26)), ("small", (10, 7))):
            path = root / "gfx" / "flags" / directory / f"{tag}.tga"
            if not path.exists():
                issues.append(f"missing central-country flag {path.relative_to(root)}")
            else:
                with Image.open(path) as image:
                    if image.size != size:
                        issues.append(f"{path.relative_to(root)}: expected {size}, got {image.size}")

    cosmetic_definitions = read(root, "common/countries/cosmetic.txt", issues)
    for token in (
        "WRK_vorkerland_emergency = {",
        "color = rgb { 72 61 57 }",
        "color_ui = rgb { 196 93 52 }",
        "WRK_vorkerland_utilitarian_republic = {",
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
    for token in ('NDN: "Норден"', 'SWB: "Старый Воркенсберг"', 'VHV: "Верховье"', 'OSV: "Оствин"'):
        if token not in loc:
            issues.append(f"short border-country name is missing: {token}")
    for banned in (
        "Западный союз",
        "Норвенская береговая республика",
        "Восточное содружество",
        "Восточная чрезвычайная администрация",
        "Северная гвардейская зона",
        "Йорский временный совет",
    ):
        if banned in loc:
            issues.append(f"obsolete/cringe country name survived localisation: {banned}")
    cosmetic_loc = read(root, "localisation/russian/countries_l_russian.yml", issues)
    for key, name in (
        ("WRK_vorkerland_utilitarian_republic", "Утилитарная Республика Воркерланда"),
        ("PWR_rimat_republic", "Риматская инженерная директория"),
        ("ZAO_zaozersk_republic", "Заозерская республика"),
        ("VLA_volnograd_republic", "Вольноградская республика"),
        ("ROM_frealor_republic", "Республика Фреалор"),
        ("TRU_zolotorevsk_republic", "Золоторевская республика"),
    ):
        if f'{key}: "{name}"' not in cosmetic_loc:
            issues.append(f"{key} lacks its required short country name")

    recovery_en = read(root, "localisation/english/ADISCORD_vorkerland_recovery_l_english.yml", issues)
    recovery_ru = read(root, "localisation/russian/ADISCORD_vorkerland_recovery_l_russian.yml", issues)
    for localisation, required, banned in (
        (recovery_en, "Control Dorian Worx's technical administration.", "Control the utilitarian directorate."),
        (recovery_ru, "Играть за техническую администрацию Дориана Воркса.", "Играть за утилитарный директорат."),
    ):
        if required not in localisation:
            issues.append(f"Worx claimant choice is missing {required}")
        if banned in localisation:
            issues.append(f"Worx claimant choice still presents him as utilitarian: {banned}")
    for localisation, country_name in (
        (recovery_en, 'WRK_technocracy: "Technocratic Republic of Vorkerland"'),
        (recovery_ru, 'WRK_technocracy: "Технократическая республика Воркерланда"'),
    ):
        if country_name not in localisation:
            issues.append(f"Dorian's restored technocratic country name is missing {country_name}")
    if 'WRK_vorkerland_utilitarian_republic: "Utilitarian Republic of Vorkerland"' not in recovery_en:
        issues.append("Anton Bagley's utilitarian cosmetic lacks its English country name")

    phase_effects = read(root, "common/scripted_effects/ADISCORD_vorkerland_phase_effects.txt", issues)
    tva_formation = named_block(phase_effects, "ADISCORD_vorkerland_form_wrk_from_tva")
    for token in (
        "set_country_flag = ADISCORD_vorkerland_route_utilitarian",
        "drop_cosmetic_tag = yes",
        "ruling_party = technocracy",
        "character = TVA_Dorian_Worx",
        "ideology = technocracy_ideology",
    ):
        if token not in tva_formation:
            issues.append(f"save-compatible Worx formation is missing {token}")
    for forbidden in (
        "ruling_party = utilitarism",
        "set_cosmetic_tag = WRK_vorkerland_utilitarian_republic",
        "GFX_portrait_WRK_Anton_Bagley",
    ):
        if forbidden in tva_formation:
            issues.append(f"Dorian's technocratic formation still borrows Anton's identity: {forbidden}")

    collapse_effects = read(root, "common/scripted_effects/ADISCORD_vorkerland_collapse_effects.txt", issues)
    tva_setup = named_block(collapse_effects, "ADISCORD_vorkerland_setup_tva")
    for token in (
        "ruling_party = technocracy",
        "character = TVA_Dorian_Worx",
        "ideology = technocracy_ideology",
        "portrait = GFX_portrait_WRK_Dorian_Worx",
    ):
        if token not in tva_setup:
            issues.append(f"TVA materialization is missing Dorian's technocratic identity: {token}")
    for forbidden in (
        "ruling_party = utilitarism",
        "GFX_portrait_WRK_Anton_Bagley",
    ):
        if forbidden in tva_setup:
            issues.append(f"TVA materialization incorrectly borrows Anton's identity: {forbidden}")
    claimant_setup = named_block(collapse_effects, "ADISCORD_vorkerland_apply_claimant_cosmetics")
    wkr_setup = named_block(claimant_setup, "WKR")
    anton_path = named_block(wkr_setup, "else")
    for token in (
        "ruling_party = utilitarism",
        "set_cosmetic_tag = WRK_vorkerland_utilitarian_republic",
        "ADISCORD_vorkerland_promote_anton_bagley = yes",
        "portrait = GFX_portrait_WRK_Anton_Bagley",
    ):
        if token not in anton_path:
            issues.append(f"Anton Bagley's WKR succession is missing {token}")
    worker_formation = named_block(phase_effects, "ADISCORD_vorkerland_form_wrk_from_wkr")
    for token in (
        "set_cosmetic_tag = WRK_vorkerland_utilitarian_republic",
        "ruling_party = utilitarism",
        "ADISCORD_vorkerland_promote_anton_bagley = yes",
    ):
        if token not in worker_formation:
            issues.append(f"Anton Bagley's restored-WRK succession is missing {token}")

    vad_setup = named_block(claimant_setup, "VAD")
    joint_vad = named_block(vad_setup, "if")
    imperial_vad = named_block(vad_setup, "else")
    for token in (
        "set_cosmetic_tag = WRK_vorkerland_joint_government",
        "ADISCORD_vorkerland_appoint_joint_council = yes",
    ):
        if token not in joint_vad:
            issues.append(f"survivor joint government is missing {token}")
    for token in (
        "set_cosmetic_tag = VAD_vorkerland_restoration",
        "portrait = GFX_portrait_WRK_Vlad_Petrichev_civilwar",
    ):
        if token not in imperial_vad:
            issues.append(f"Vlad Petrichev's imperial claimant identity is missing {token}")
        if token in joint_vad:
            issues.append(f"survivor joint government incorrectly borrows Vlad's imperial identity: {token}")

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
    phase_effects = read(root, "common/scripted_effects/ADISCORD_vorkerland_phase_effects.txt", issues)
    phase_events = read(root, "events/ADISCORD_vorkerland_phase_events.txt", issues)
    capitulation_effects = read(
        root,
        "common/scripted_effects/ZZ_ADISCORD_capitulation_distribution_effects.txt",
        issues,
    )
    decisions = read(root, "common/decisions/ADISCORD_vorkerland_collapse_decisions.txt", issues)
    focus_decisions = read(
        root,
        "common/decisions/ADISCORD_vorkerland_focus_decisions.txt",
        issues,
    )
    diplomacy_decisions = read(
        root,
        "common/decisions/ADISCORD_vorkerland_diplomacy_decisions.txt",
        issues,
    )
    ideas = read(root, "common/ideas/ADISCORD_vorkerland_collapse_ideas.txt", issues)
    loc = read(root, "localisation/russian/ADISCORD_vorkerland_collapse_l_russian.yml", issues)
    countries_loc = read(root, "localisation/russian/countries_l_russian.yml", issues)
    state_loc = read(root, "localisation/russian/state_names_l_russian.yml", issues)
    victory_point_loc = read(root, "localisation/russian/victory_points_l_russian.yml", issues)
    triggers = read(root, "common/scripted_triggers/ADISCORD_vorkerland_collapse_triggers.txt", issues)
    on_actions = read(root, "common/on_actions/01_ADISCORD_vorkerland_collapse_on_actions.txt", issues)
    map_effects = read(root, "common/scripted_effects/ADISCORD_vorkerland_collapse_map_effects.txt", issues)
    news_loc = read(root, "localisation/russian/events_l_russian.yml", issues)
    superevent_loc = read(root, "localisation/russian/ADISCORD_superevents_l_russian.yml", issues)
    for label, source in (
        ("events", events),
        ("effects", effects),
        ("phase effects", phase_effects),
        ("phase events", phase_events),
        ("decisions", decisions),
        ("focus decisions", focus_decisions),
        ("ideas", ideas),
        ("capitulation effects", capitulation_effects),
    ):
        if not balanced(source):
            issues.append(f"collapse {label}: unbalanced braces or quote")
        for stale in STALE_SYSTEM_TOKENS:
            if stale in source:
                issues.append(f"collapse {label}: dead system token survived: {stale}")

    event_definitions = re.findall(
        r"(?ms)^(?:country_event|news_event)\s*=\s*\{\s*id\s*=\s*([A-Za-z0-9_.-]+)",
        events,
    )
    duplicate_event_ids = sorted({event_id for event_id in event_definitions if event_definitions.count(event_id) > 1})
    if duplicate_event_ids:
        issues.append(f"collapse event IDs are duplicated: {duplicate_event_ids}")

    geography_loc = "\n".join((loc, state_loc, victory_point_loc))
    if "Техград" in geography_loc:
        issues.append("player-facing geography still renames Vorkensberg to Techgrad")
    for token in (
        'TGD: "Фирнов-Техлар"',
        'STATE_40: "Башня Единства"',
        'VICTORY_POINTS_16428: "Башня Единства"',
        'VICTORY_POINTS_6713: "Гранд-Воркенсберг"',
    ):
        if token not in geography_loc:
            issues.append(f"Vorkensberg/Firnov-Tehlar geography is missing {token}")

    outbreak = named_block(events, "country_event")
    if not outbreak:
        issues.append("collapse outbreak event is missing")
    for token in (
        "ADISCORD_vorkerland_apply_initial_map = yes",
        "ADISCORD_vorkerland_teardown_confederation = yes",
        "ADISCORD_vorkerland_apply_claimant_cosmetics = yes",
        "ADISCORD_vorkerland_form_joint_government = yes",
    ):
        if token not in outbreak:
            issues.append(f"collapse outbreak is missing {token}")
    if outbreak.find("ADISCORD_vorkerland_apply_initial_map = yes") > outbreak.find(
        "ADISCORD_vorkerland_teardown_confederation = yes"
    ):
        issues.append("collapse teardown must run after all regional tags are spawned")

    opening_news = named_block(outbreak, "news_event")
    if events.count("id = ADISCORD_superevent_news.1") != 1:
        issues.append("collapse opening news must have exactly one trigger path")
    for token in (
        "NOT = { has_global_flag = ADISCORD_vorkerland_collapse_news_shown }",
        "set_global_flag = ADISCORD_vorkerland_collapse_news_shown",
        "news_event = { id = ADISCORD_superevent_news.1 }",
    ):
        if token not in outbreak:
            issues.append(f"collapse opening news is missing {token}")
    if any(token in opening_news for token in ("hours =", "days =", "random_hours", "random_days")):
        issues.append("collapse opening news is still delayed or randomized")
    if outbreak.find("ADISCORD_vorkerland_apply_claimant_cosmetics = yes") > outbreak.find(
        "news_event = { id = ADISCORD_superevent_news.1 }"
    ):
        issues.append("collapse opening news fires before successor setup is complete")
    if "ADISCORD_superevent_news.1" in on_actions:
        issues.append("collapse opening news still has an on-action duplicate path")
    tower_guard = "ADISCORD_vorkerland_unity_tower_destruction_resolved"
    if f"NOT = {{ has_global_flag = {tower_guard} }}" not in outbreak:
        issues.append("collapse outbreak does not guard the physical Unity Tower destruction")
    if outbreak.count(f"set_global_flag = {tower_guard}") != 1:
        issues.append("collapse outbreak must record the Unity Tower destruction exactly once")
    if events.count("launch_nuke = {") != 1:
        issues.append("Unity Tower must have exactly one physical explosion producer")
    if outbreak.find(f"set_global_flag = {tower_guard}") > outbreak.find("launch_nuke = {"):
        issues.append("Unity Tower one-shot guard is recorded after the explosion")
    if not all(
        token in on_actions
        for token in (
            "has_global_flag = ADISCORD_vorkerland_collapse_started",
            f"NOT = {{ has_global_flag = {tower_guard} }}",
            f"set_global_flag = {tower_guard}",
        )
    ):
        issues.append("old collapse saves do not migrate the permanent Unity Tower guard")

    legacy_dirty_reveal = event_block(events, "ADISCORD_vorkerland_collapse.10")
    delayed_dirty_reveal = event_block(events, "ADISCORD_vorkerland_collapse.85")
    reveal_flag = "ADISCORD_vorkerland_dirty_reveal_v2_scheduled"
    for token in (
        f"NOT = {{ has_global_flag = {reveal_flag} }}",
        f"set_global_flag = {reveal_flag}",
        "id = ADISCORD_vorkerland_collapse.85",
        "days = 1095",
    ):
        if token not in outbreak:
            issues.append(f"fresh collapse lacks the three-year dirty-zone timer token {token}")
    if any(token in outbreak for token in ("days = 60", "random_days = 30")):
        issues.append("fresh collapse still schedules the obsolete early dirty-zone reveal")
    if "trigger = { always = no }" not in legacy_dirty_reveal:
        issues.append("legacy collapse.10 must be inert so serialized short timers cannot reveal the zone")
    for forbidden in ("ADISCORD_vorkerland_dirty_opened", "show_dirty_opening_superevent"):
        if forbidden in legacy_dirty_reveal:
            issues.append(f"legacy collapse.10 still performs reveal work: {forbidden}")
    for token in (
        f"has_global_flag = {reveal_flag}",
        "NOT = { has_global_flag = ADISCORD_vorkerland_dirty_opened }",
        "set_global_flag = ADISCORD_vorkerland_dirty_opened",
        "ADISCORD_vorkerland_show_dirty_opening_superevent = yes",
        "ADISCORD_vorkerland_collapse.11 days = 1",
        "ADISCORD_vorkerland_collapse.19 days = 11",
    ):
        if token not in delayed_dirty_reveal:
            issues.append(f"three-year dirty-zone reveal lacks {token}")
    for token in (
        "has_global_flag = ADISCORD_vorkerland_collapse_started",
        "NOT = { has_global_flag = ADISCORD_vorkerland_dirty_opened }",
        f"NOT = {{ has_global_flag = {reveal_flag} }}",
        f"set_global_flag = {reveal_flag}",
        "country_event = { id = ADISCORD_vorkerland_collapse.85 days = 1095 }",
    ):
        if token not in on_actions:
            issues.append(f"closed-zone old saves lack versioned three-year recovery token {token}")
    if 'news.0.t: "Конец единого Воркерланда"' not in news_loc:
        issues.append("collapse opening world-news title is not 'Конец единого Воркерланда'")
    teardown = named_block(effects, "ADISCORD_vorkerland_teardown_confederation")
    if "is_subject_of = WRK" in teardown:
        issues.append("collapse teardown still assumes WRK is every country's overlord")
    for effect_name, portrait in (
        (
            "ADISCORD_vorkerland_appoint_rom_etatist",
            "GFX_portrait_ROM_Erwin_Von_Romanovskiy_civilwar",
        ),
        (
            "ADISCORD_vorkerland_appoint_tru_chauvinist",
            "GFX_portrait_TRU_Nikita_Truman_civilwar",
        ),
    ):
        if portrait not in named_block(effects, effect_name):
            issues.append(f"{effect_name}: civil-war portrait is missing {portrait}")
    independent_tags = (
        "WKR", "VAD", "NAM", "DAN", "ZAO", "PWR", "VLA", "ROM", "SOL", "TRU",
        "TVA", "EYR", "EGC", "RIV", "REV", "YOR", "NDN", "SWB", "VHV", "OSV", "WPA", "WPS", "PSD", "EBA", "DVA", "SRA", "ZTA",
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
    wkr_partition = named_block(initial_map, "WKR")
    tgd_setup = named_block(effects, "ADISCORD_vorkerland_setup_tgd")
    if not re.search(r"transfer_state\s*=\s*32\b", wkr_partition):
        issues.append("WKR no longer receives the Unity Tower capital state 32")
    if re.search(r"transfer_state\s*=\s*105\b", wkr_partition):
        issues.append("WKR still receives TGD's peripheral state 105")

    expected_central_states = {
        "WKR": {32, 33, 40, 200, 201},
        "WTD": {34},
        "VAD": {75, 106, 107, 121},
        "PWR": {71, 90, 91, 202},
        "TVA": {36, 37, 38, 39, 324},
        "EYR": {102, 109, 111, 325},
        "EGC": {81, 110, 124},
        "RIV": {79, 306, 308, 309, 327},
        "REV": {82, 323},
        "YOR": {108, 122, 123},
        "NDN": {27},
        "SWB": {35},
        "VHV": {315, 316, 317},
        "OSV": {318, 320},
        "ZTA": {199},
    }
    for tag, expected in expected_central_states.items():
        actual = initial_tag_states(effects, tag)
        if actual != expected:
            issues.append(f"{tag}: central-state partition drifted: {sorted(actual)}")
    if "202 = { add_core_of = PWR set_state_controller_to = PWR }" not in initial_map:
        issues.append("state 202 is not assigned as a PWR core in the initial collapse map")
    if "40 = { set_state_controller_to = WKR }" not in initial_map:
        issues.append("impassable Unity Tower state 40 is not explicitly controlled by WKR")
    for tag in ("RIV", "REV", "YOR", "NDN", "SWB", "VHV", "OSV"):
        if f"ADISCORD_vorkerland_setup_{tag.lower()} = yes" not in initial_map:
            issues.append(f"{tag}: central setup is not called by the initial map")
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
    for token in (
        "ADISCORD_vorkerland_teardown_confederation = yes",
        "ADISCORD_vorkerland_collapse.31",
        "days = 21",
        "random_days = 14",
    ):
        if token not in second:
            issues.append(f"collapse mobilisation pause is missing {token}")

    legacy_central_decision = "ADISCORD_vorkerland_consolidate_central_border"
    if named_block(decisions, legacy_central_decision):
        issues.append(
            f"{legacy_central_decision}: legacy broad central-war producer survived"
        )
    if "ADISCORD_vorkerland_is_central_target_for_ROOT = yes" in decisions:
        issues.append(
            "collapse decisions still own a broad central-minor target producer"
        )

    expected_central_decisions = {
        f"ADISCORD_vorkerland_consolidate_{target.lower()}"
        for target in CENTRAL_MINOR_TARGETS
    }
    actual_central_decisions = set(
        re.findall(
            r"(?m)^\s*(ADISCORD_vorkerland_consolidate_[a-z0-9_]+)\s*=\s*\{",
            focus_decisions,
        )
    )
    if actual_central_decisions != expected_central_decisions:
        issues.append(
            "focus decisions do not exclusively own the nine named central-minor fronts"
        )
    for target in CENTRAL_MINOR_TARGETS:
        suffix = target.lower()
        decision_id = f"ADISCORD_vorkerland_consolidate_{suffix}"
        decision = named_block(focus_decisions, decision_id)
        visible = named_block(decision, "visible")
        complete = named_block(decision, "complete_effect")
        remove = named_block(decision, "remove_effect")
        for token in (
            "ADISCORD_vorkerland_central_minor_campaign_phase_available = yes",
            f"any_neighbor_country = {{ tag = {target} }}",
        ):
            if token not in visible:
                issues.append(f"{decision_id}: early-campaign visibility is missing {token}")
        for forbidden in (
            "ADISCORD_vorkerland_focus_wkr_central_war_unlocked",
            "ADISCORD_vorkerland_focus_vad_central_war_unlocked",
            "ADISCORD_vorkerland_focus_tva_central_war_unlocked",
            "ADISCORD_vorkerland_focus_central_front_prepared",
        ):
            if forbidden in visible:
                issues.append(f"{decision_id}: retains late final-showdown gate {forbidden}")
        target_flag = (
            f"set_country_flag = ADISCORD_vorkerland_focus_central_minor_target_{suffix}"
        )
        if target_flag not in complete:
            issues.append(f"{decision_id}: does not own its named target flag")
        launch = f"ADISCORD_vorkerland_focus_launch_minor_{suffix} = yes"
        if launch not in remove:
            issues.append(f"{decision_id}: does not own its named launch effect")
        if "declare_war_on" in decision:
            issues.append(f"{decision_id}: bypasses the delayed one-front launch effect")
        if decision.count("set_country_flag = ADISCORD_vorkerland_focus_central_minor_target_") != 1:
            issues.append(f"{decision_id}: must select exactly one central-minor target")
        if decision.count("ADISCORD_vorkerland_focus_launch_minor_") != 1:
            issues.append(f"{decision_id}: must call exactly one named launch effect")

    claimant_rival = named_block(triggers, "ADISCORD_vorkerland_is_main_claimant_rival_for_ROOT")
    for token in (
        "AND = { tag = TVA ROOT = { tag = WKR } }",
        "AND = { tag = WKR ROOT = { tag = TVA } }",
    ):
        if token not in claimant_rival:
            issues.append("Worker-Doctor pair is not excluded from immediate claimant wars")

    retired_worker_doctor_sources = {
        "events": events,
        "effects": effects,
        "decisions": decisions,
        "on_actions": on_actions,
        "phase effects": phase_effects,
        "phase events": phase_events,
    }
    for event_id in (48, 49):
        event_token = f"ADISCORD_vorkerland_collapse.{event_id}"
        for label, source in retired_worker_doctor_sources.items():
            active = "\n".join(line.split("#", 1)[0] for line in source.splitlines())
            if re.search(rf"\b{re.escape(event_token)}\b", active):
                issues.append(f"{label}: retired Worker-Doctor event survived: {event_token}")

    for retired in (
        "ADISCORD_vorkerland_prepare_worker_doctor_showdown",
        "ADISCORD_vorkerland_detach_worker_doctor_factions",
        "ADISCORD_vorkerland_launch_worker_doctor_war",
    ):
        if retired in "\n".join(
            line.split("#", 1)[0]
            for line in (decisions + "\n" + effects).splitlines()
        ):
            issues.append(f"retired Worker-Doctor launcher survived: {retired}")

    phase_four_match = re.search(
        r"(?ms)^country_event\s*=\s*\{\s*id\s*=\s*ADISCORD_vorkerland_phase\.4\b"
        r"(.*?)(?=^country_event\s*=\s*\{|\Z)",
        phase_events,
    )
    phase_five_match = re.search(
        r"(?ms)^country_event\s*=\s*\{\s*id\s*=\s*ADISCORD_vorkerland_phase\.5\b"
        r"(.*?)(?=^country_event\s*=\s*\{|\Z)",
        phase_events,
    )
    phase_four = phase_four_match.group(1) if phase_four_match else ""
    phase_five = phase_five_match.group(1) if phase_five_match else ""
    for token in (
        "has_global_flag = ADISCORD_vorkerland_phase_central_preparation",
        "ADISCORD_vorkerland_initialize_showdown_edge_queue = yes",
    ):
        if token not in phase_four:
            issues.append(f"phase.4 central-showdown handoff is missing {token}")
    if "ADISCORD_vorkerland_advance_showdown_launch = yes" not in phase_five:
        issues.append("phase.5 does not advance the guarded showdown queue")

    queue = named_block(phase_effects, "ADISCORD_vorkerland_initialize_showdown_edge_queue")
    for token in (
        "set_global_flag = ADISCORD_vorkerland_showdown_edge_wkr_tva_required",
        "ADISCORD_vorkerland_detach_showdown_claimants = yes",
        "country_event = { id = ADISCORD_vorkerland_phase.5 days = 1 }",
    ):
        if token not in queue:
            issues.append(f"three-claimant showdown queue is missing {token}")
    wkr_tva_attempt = named_block(
        phase_effects, "ADISCORD_vorkerland_attempt_showdown_edge_wkr_tva"
    )
    for token in (
        "WKR = { NOT = { has_war_with = TVA } }",
        "WKR = { declare_war_on = { target = TVA type = annex_everything } }",
        "set_global_flag = ADISCORD_vorkerland_showdown_edge_wkr_tva_attempted",
    ):
        if token not in wkr_tva_attempt:
            issues.append(f"WKR-TVA showdown attempt is missing {token}")
    wkr_tva_verify = named_block(
        phase_effects, "ADISCORD_vorkerland_verify_showdown_edge_wkr_tva"
    )
    for token in (
        "WKR = { has_war_with = TVA }",
        "set_global_flag = ADISCORD_vorkerland_showdown_edge_wkr_tva_verified",
        "ADISCORD_vorkerland_schedule_wtd_tva_temporary_alliance_check = yes",
        "set_global_flag = ADISCORD_vorkerland_showdown_edge_wkr_tva_retry",
        "set_global_flag = ADISCORD_vorkerland_showdown_edge_wkr_tva_failed",
    ):
        if token not in wkr_tva_verify:
            issues.append(f"WKR-TVA showdown verification is missing {token}")

    setup_wtd = named_block(effects, "ADISCORD_vorkerland_setup_wtd")
    align_wtd = named_block(effects, "ADISCORD_vorkerland_align_wtd_with_worx")
    for forbidden in ("puppet = WTD", "is_subject_of = TVA"):
        if forbidden in setup_wtd + "\n" + align_wtd + "\n" + wkr_tva_verify:
            issues.append(f"sovereign WTD contract still contains {forbidden}")
    for token in (
        "is_subject = yes",
        "autonomy_state = autonomy_free",
        "is_in_faction = yes",
        "leave_faction = yes",
        "ADISCORD_vorkerland_worx_aligned_technocrats",
    ):
        if token not in align_wtd:
            issues.append(f"sovereign WTD alignment is missing {token}")

    wtd_schedule = named_block(
        phase_effects, "ADISCORD_vorkerland_schedule_wtd_tva_temporary_alliance_check"
    )
    for token in (
        "is_subject = no",
        "NOT = { has_capitulated = yes }",
        "NOT = { has_war_with = WKR }",
        "TVA = { exists = yes has_war_with = WKR }",
        "WTD = { country_event = { id = ADISCORD_vorkerland_collapse.47 days = 1 } }",
    ):
        if token not in wtd_schedule:
            issues.append(f"sovereign WTD join scheduler is missing {token}")

    wtd_join = event_block(events, "ADISCORD_vorkerland_collapse.47")
    wtd_retry = event_block(events, "ADISCORD_vorkerland_collapse.67")
    for token in (
        "tag = WTD",
        "is_subject = no",
        "TVA = { exists = yes has_war_with = WKR }",
        "NOT = { has_war_with = WKR }",
        "targeted_alliance = TVA",
        "enemy = WKR",
        "country_event = { id = ADISCORD_vorkerland_collapse.67 days = 1 }",
    ):
        if token not in wtd_join:
            issues.append(f"sovereign WTD war join event .47 is missing {token}")
    for token in (
        "limit = { has_war_with = WKR }",
        "set_country_flag = ADISCORD_vorkerland_wtd_fighting_for_worx",
        "set_country_flag = ADISCORD_vorkerland_wtd_join_retry",
        "targeted_alliance = TVA",
        "enemy = WKR",
        "set_country_flag = ADISCORD_vorkerland_wtd_join_failed",
    ):
        if token not in wtd_retry:
            issues.append(f"sovereign WTD join postcondition event .67 is missing {token}")
    retry_call = "country_event = { id = ADISCORD_vorkerland_collapse.67 days = 1 }"
    if wtd_retry.count(retry_call) != 1:
        issues.append("sovereign WTD join event .67 must contain exactly one bounded retry")
    worker_doctor_monthly = named_block(on_actions, "on_monthly")
    for forbidden in (
        "ADISCORD_vorkerland_schedule_wtd_tva_temporary_alliance_check",
        "ADISCORD_vorkerland_collapse.47",
        "ADISCORD_vorkerland_collapse.67",
    ):
        if forbidden in worker_doctor_monthly:
            issues.append(f"sovereign WTD join must not poll on_monthly: {forbidden}")

    reunification_war = named_block(decisions, "ADISCORD_vorkerland_continue_reunification")
    if not reunification_war or "every_neighbor_country" not in reunification_war or "declare_war_on" not in reunification_war:
        issues.append("ADISCORD_vorkerland_continue_reunification: multi-front war is not gated by live borders")
    if "ai_will_do" not in reunification_war:
        issues.append("ADISCORD_vorkerland_continue_reunification: AI cannot take the war decision")
    regional_war = named_block(decisions, "ADISCORD_vorkerland_open_regional_fronts")
    regional_complete = named_block(regional_war, "complete_effect")
    if "ADISCORD_vorkerland_detach_regional_war_factions = yes" not in regional_complete:
        issues.append("regional-war decision does not clear inherited factions before declaring")
    regional_allowed = named_block(regional_war, "allowed")
    if set(re.findall(r"tag\s*=\s*([A-Z]{3})", regional_allowed)) != {"ZAO", "VLA", "ROM", "SOL", "TRU"}:
        issues.append("peripheral war decision has the wrong theatre-anchor allowlist")
    for token in (
        "has_global_flag = ADISCORD_vorkerland_claim_wars_authorized",
        "ADISCORD_vorkerland_regional_war_launch_scheduled",
        "ADISCORD_vorkerland_collapse.63 days = 1",
        "factor = 1000",
    ):
        if token not in regional_war:
            issues.append(f"peripheral multi-country war decision is missing {token}")
    if "declare_war_on =" in regional_complete or "add_to_war =" in regional_complete:
        issues.append("peripheral decision bypasses its one-day diplomatic-cache barrier")
    repair_wars = named_block(effects, "ADISCORD_vorkerland_repair_regional_wars")
    if repair_wars.count("declare_war_on =") != 17:
        issues.append("startup regional-war repair must restore seventeen independent rivalries")
    if repair_wars.count("is_subject = no") != 34 or repair_wars.count("has_capitulated = yes") != 34:
        issues.append("startup regional-war repair can revive a defeated or integrated participant")
    for attacker, defender, label in (
        ("WPA", "PSD", "Norven-Grain"),
        ("PWR", "PSD", "Norven-Wit"),
        ("TGD", "EBA", "Tehlar-Ebern"),
        ("SRA", "CSL", "Solvein-Central Solyarino League"),
    ):
        if not re.search(
            rf"{attacker}\s*=\s*\{{\s*declare_war_on\s*=\s*\{{\s*target\s*=\s*{defender}",
            repair_wars,
        ):
            issues.append(f"{label} direct rivalry is missing")
    regional_launch = named_block(effects, "ADISCORD_vorkerland_open_regional_fronts_after_detach")
    for token in (
        "ADISCORD_vorkerland_repair_regional_wars = yes",
        "ADISCORD_vorkerland_collapse.64 days = 1",
    ):
        if token not in regional_launch:
            issues.append(f"delayed regional-war launch is missing {token}")
    launch_success_tokens = (
        "set_global_flag = ADISCORD_vorkerland_northern_wars_began",
        "set_global_flag = ADISCORD_vorkerland_ivanland_planning_unlocked_v4",
        "clr_global_flag = ADISCORD_vorkerland_regional_war_launch_scheduled",
    )
    for token in launch_success_tokens:
        if token in regional_launch:
            issues.append(f"regional-war declaration launcher improperly owns verified success mutation {token}")
    regional_verifier = named_block(
        phase_effects, "ADISCORD_vorkerland_verify_regional_war_launch"
    )
    for token in (
        "ADISCORD_vorkerland_repair_regional_wars = yes",
        "ADISCORD_vorkerland_regional_war_graph_active_or_terminal = yes",
        "ADISCORD_vorkerland_schedule_northern_escalation = yes",
        *launch_success_tokens,
    ):
        if token not in regional_verifier:
            issues.append(f"regional-war phase verifier is missing {token}")
    startup = named_block(on_actions, "on_startup")
    if "ADISCORD_vorkerland_collapse.64 days = 1" not in startup:
        issues.append("startup does not schedule the bounded regional-war repair")
    if "ADISCORD_vorkerland_repair_regional_wars = yes" in startup:
        issues.append("startup still repairs regional wars in the faction-detachment tick")
    for event_id, token in (
        (63, "ADISCORD_vorkerland_open_regional_fronts_after_detach = yes"),
        (64, "ADISCORD_vorkerland_verify_regional_war_launch = yes"),
    ):
        match = re.search(
            rf"(?ms)^country_event\s*=\s*\{{\s*id\s*=\s*ADISCORD_vorkerland_collapse\.{event_id}\b"
            r"(.*?)(?=^country_event\s*=\s*\{|^add_namespace\s*=|\Z)",
            events,
        )
        if match is None or token not in match.group(1):
            issues.append(f"regional diplomatic-cache event .{event_id} is missing {token}")
    reunification_allowed = named_block(
        named_block(decisions, "ADISCORD_vorkerland_continue_reunification"), "allowed"
    )
    if "NOT = { tag = WRK }" not in reunification_allowed:
        issues.append("WRK can still launch post-victory reunification wars")

    for name, block in (
        ("main claimant", named_block(triggers, "ADISCORD_vorkerland_is_main_claimant_rival_for_ROOT")),
        ("central", named_block(triggers, "ADISCORD_vorkerland_is_central_target_for_ROOT")),
        ("reunification", named_block(triggers, "ADISCORD_vorkerland_is_reunification_target_for_ROOT")),
    ):
        if "has_war = no" in block:
            issues.append(f"{name} target still freezes while fighting an unrelated war")

    capitulation = named_block(on_actions, "on_capitulation")
    for token in (
        "ADISCORD_vorkerland_is_central_claimant = yes",
        "ADISCORD_vorkerland_is_main_claimant = yes",
        "ADISCORD_vorkerland_settle_central_capitulation = yes",
    ):
        if token not in capitulation:
            issues.append(f"central capitulation routing is missing {token}")
    central_settlement = named_block(
        capitulation_effects, "ADISCORD_vorkerland_settle_central_capitulation"
    )
    for token in (
        "flag = ADISCORD_vorkerland_central_recovery",
        "days = 35",
        "add_manpower = 1500",
        "ADISCORD_vorkerland_central_minor_winner_wrk",
        "has_global_flag = ADISCORD_vorkerland_phase_postwar_integration",
        "has_global_flag = ADISCORD_vorkerland_reunification_verified",
    ):
        if token not in central_settlement:
            issues.append(f"central recovery window is missing {token}")
    central_finalizer = named_block(
        capitulation_effects, "ADISCORD_vorkerland_finalize_central_minor_settlement"
    )
    for token in (
        "has_country_flag = ADISCORD_vorkerland_central_minor_winner_wrk",
        "WRK = { exists = yes is_subject = no NOT = { has_capitulated = yes } }",
        "annex_country = { target = ROOT transfer_troops = no }",
    ):
        if token not in central_finalizer:
            issues.append(f"old-save WRK minor finalizer is missing {token}")
    settlement_retry = event_block(events, "ADISCORD_vorkerland_collapse.66")
    force_flag = "ADISCORD_vorkerland_central_minor_settlement_force_transfer"
    if f"set_country_flag = {force_flag}" not in settlement_retry:
        issues.append("terminal central-minor retry does not arm force-transfer recovery")
    for tag in ("WKR", "VAD", "TVA", "WRK"):
        token = f"every_owned_state = {{ {tag} = {{ transfer_state = PREV }} }}"
        if token not in central_finalizer:
            issues.append(f"terminal central-minor finalizer cannot transfer a {tag} remnant")

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

        for tag in ("RIV", "REV", "YOR", "NDN", "SWB", "VHV", "OSV"):
            remaining = set(assigned[tag])
            reached: set[int] = set()
            frontier = [min(remaining)] if remaining else []
            while frontier:
                state_id = frontier.pop()
                if state_id in reached:
                    continue
                reached.add(state_id)
                frontier.extend((physical_states.get(state_id, set()) & remaining) - reached)
            if reached != remaining:
                issues.append(f"{tag}: central state belt is not physically connected")

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

    ivn_preparation = named_block(
        decisions, "ADISCORD_ivanland_prepare_northern_expedition"
    )
    for token in (
        "allowed = { tag = IVN }",
        "has_global_flag = ADISCORD_vorkerland_ivanland_planning_unlocked_v4",
        "available = { ADISCORD_ivanland_intervention_start_ready = yes }",
        "cost = 75",
        "days_remove = 120",
        "fire_only_once = yes",
        "civilian_factory_use = 2",
        "ADISCORD_vorkerland_activate_ivanland_intervention_mission = yes",
    ):
        if token not in ivn_preparation:
            issues.append(f"Ivanland visible 120-day preparation is missing {token}")

    ivn = named_block(decisions, "ADISCORD_ivanland_limited_intervention")
    for token in (
        "activation = { always = no }",
        "has_global_flag = ADISCORD_vorkerland_ivanland_intervention_active",
        "available = { always = no }",
        "selectable_mission = no",
        "days_mission_timeout = 240",
        "controls_state = 90",
        "controls_state = 91",
        "controls_state = 93",
        "controls_state = 94",
        "intervention_success",
        "intervention_failure",
    ):
        if token not in ivn:
            issues.append(f"Ivanland externally activated 240-day mission is missing {token}")
    if "ADISCORD_vorkerland_begin_ivanland_intervention = yes" in ivn:
        issues.append("Ivanland mission bypasses the authoritative preparation activation effect")
    ivn_cancel_trigger = named_block(ivn, "cancel_trigger")
    ivn_cancel_effect = named_block(ivn, "cancel_effect")
    if "has_capitulated = yes" not in ivn_cancel_trigger:
        issues.append("Ivanland mission cannot resolve an early capitulation")
    if "NOT = { has_war_with = PWR }" in ivn_cancel_trigger:
        issues.append("Ivanland mission can fail on a stale same-tick diplomatic cache")
    for token in (
        "ADISCORD_vorkerland_ivanland_intervention_success = yes",
        "ADISCORD_vorkerland_ivanland_intervention_failure = yes",
    ):
        if token not in ivn_cancel_effect:
            issues.append(f"Ivanland mission cancel routing is missing {token}")
    if "timeout_effect = { ADISCORD_vorkerland_ivanland_intervention_failure = yes }" not in ivn:
        issues.append("Ivanland mission timeout does not resolve as failure")
    intervention_activation = named_block(
        effects, "ADISCORD_vorkerland_activate_ivanland_intervention_mission"
    )
    for token in (
        "set_global_flag = ADISCORD_vorkerland_ivanland_intervention_active",
        "add_timed_idea = { idea = ADISCORD_vorkerland_ivanland_expeditionary_command days = 260 }",
        "activate_mission = ADISCORD_ivanland_limited_intervention",
        "ADISCORD_vorkerland_begin_ivanland_intervention = yes",
    ):
        if token not in intervention_activation:
            issues.append(f"Ivanland mission activation effect is missing {token}")
    intervention_start = named_block(effects, "ADISCORD_vorkerland_begin_ivanland_intervention")
    for token in (
        "ADISCORD_vorkerland_restore_pwr_psd",
        "ADISCORD_vorkerland_ivanland_expedition_supplied",
        "ADISCORD_vorkerland_collapse.77 days = 1",
    ):
        if token not in intervention_start:
            issues.append(f"Ivanland intervention staging effect is missing {token}")
    for forbidden in ("puppet = IBL", "puppet = IBA", "declare_war_on ="):
        if forbidden in intervention_start:
            issues.append(f"Ivanland intervention staging effect prematurely contains {forbidden}")
    intervention_front = named_block(
        effects, "ADISCORD_vorkerland_open_ivanland_intervention_front"
    )
    for token in (
        "create_faction_from_template =",
        "add_to_faction = ZAO",
        "add_to_faction = WPA",
        "add_to_faction = WPS",
        "add_to_faction = PSD",
        "target = PWR type = take_state_focus generator = { 90 91 }",
        "targeted_alliance = PWR enemy = IVN",
    ):
        if token not in intervention_front:
            issues.append(f"Ivanland delayed northern front is missing {token}")
    if "target = IBL" in intervention_front or "target = IBA" in intervention_front:
        issues.append("Ivanland delayed northern front targets a postwar client")
    intervention_cache = event_block(events, "ADISCORD_vorkerland_collapse.77")
    if "ADISCORD_vorkerland_open_ivanland_intervention_front = yes" not in intervention_cache:
        issues.append("Ivanland one-day diplomatic-cache event .77 does not open the intervention front")
    verifier_call = "country_event = { id = ADISCORD_vorkerland_collapse.82 days = 1 }"
    for token in (
        "clr_country_flag = ADISCORD_vorkerland_ivanland_front_launch_pending",
        "set_country_flag = { flag = ADISCORD_vorkerland_ivanland_front_verification_pending days = 3 }",
        verifier_call,
    ):
        if token not in intervention_front:
            issues.append(f"Ivanland .77 launch chain is missing {token}")
    if event_block(events, "ADISCORD_vorkerland_collapse.79"):
        issues.append("retired Ivanland verifier event .79 was reintroduced")

    intervention_postcondition = named_block(
        triggers, "ADISCORD_vorkerland_ivanland_intervention_front_verified"
    )
    for token in ("tag = IVN", "has_war_with = PWR"):
        if token not in intervention_postcondition:
            issues.append(f"Ivanland front postcondition is missing {token}")
    for defender in ("ZAO", "WPA", "WPS", "PSD"):
        terminal_or_active = (
            f"OR = {{ NOT = {{ country_exists = {defender} }} "
            f"{defender} = {{ is_subject = yes }} "
            f"{defender} = {{ has_capitulated = yes }} "
            f"{defender} = {{ has_war_with = IVN }} }}"
        )
        if terminal_or_active not in intervention_postcondition:
            issues.append(
                f"Ivanland front postcondition does not require live {defender} to share IVN's war"
            )
    for state in (90, 91, 93, 94):
        reachability = (
            f"{state} = {{ controller = {{ OR = {{ tag = IVN has_war_with = IVN }} }} }}"
        )
        if reachability not in intervention_postcondition:
            issues.append(
                f"Ivanland front postcondition does not verify controller reachability for state {state}"
            )

    intervention_verifier = event_block(events, "ADISCORD_vorkerland_collapse.82")
    for token in (
        "tag = IVN",
        "has_global_flag = ADISCORD_vorkerland_ivanland_intervention_active",
        "NOT = { has_global_flag = ADISCORD_vorkerland_ivanland_intervention_resolved }",
        "limit = { ADISCORD_vorkerland_ivanland_intervention_front_verified = yes }",
        "set_country_flag = ADISCORD_vorkerland_ivanland_front_verified_v1",
    ):
        if token not in intervention_verifier:
            issues.append(f"Ivanland front verifier .82 is missing {token}")
    war_retry_flag = "ADISCORD_vorkerland_ivanland_front_war_retry"
    join_retry_flag = "ADISCORD_vorkerland_ivanland_front_join_retry"
    if intervention_verifier.count(f"set_country_flag = {war_retry_flag}") != 1 or (
        f"NOT = {{ has_country_flag = {war_retry_flag} }}" not in intervention_verifier
    ):
        issues.append("Ivanland front verifier .82 must permit exactly one guarded PWR war retry")
    if intervention_verifier.count(
        "declare_war_on = { target = PWR type = take_state_focus generator = { 90 91 } }"
    ) != 1:
        issues.append("Ivanland front verifier .82 must contain exactly one PWR war retry mutation")
    if intervention_verifier.count(f"set_country_flag = {join_retry_flag}") != 1 or (
        f"NOT = {{ has_country_flag = {join_retry_flag} }}" not in intervention_verifier
    ):
        issues.append("Ivanland front verifier .82 must permit exactly one guarded coalition join retry")
    live_join_guard = (
        "exists = yes is_subject = no NOT = { has_capitulated = yes } "
        "NOT = { has_war_with = IVN }"
    )
    for defender in ("ZAO", "WPA", "WPS", "PSD"):
        defender_scope = named_block(intervention_verifier, defender)
        for token in (
            live_join_guard,
            "targeted_alliance = PWR enemy = IVN hostility_reason = asked_to_join",
        ):
            if token not in defender_scope:
                issues.append(f"Ivanland .82 join retry for {defender} is missing {token}")
    if intervention_verifier.count(verifier_call) != 2:
        issues.append("Ivanland front verifier .82 must reschedule only its one war and one join retry")
    if intervention_verifier.count("ADISCORD_vorkerland_ivanland_intervention_failure = yes") != 3:
        issues.append("Ivanland front verifier .82 must terminate all exhausted/invalid retry paths as failure")

    startup = named_block(on_actions, "on_startup")
    startup_verifier_index = startup.find(verifier_call)
    startup_ivn_start = startup.rfind("IVN = {", 0, startup_verifier_index)
    startup_ivn_bridge = (
        named_block(startup[startup_ivn_start:], "IVN")
        if startup_verifier_index >= 0 and startup_ivn_start >= 0
        else ""
    )
    for token in (
        "NOT = { has_country_flag = ADISCORD_vorkerland_ivanland_front_verified_v1 }",
        "NOT = { has_country_flag = ADISCORD_vorkerland_ivanland_front_launch_pending }",
        "NOT = { has_country_flag = ADISCORD_vorkerland_ivanland_front_verification_pending }",
        "set_country_flag = { flag = ADISCORD_vorkerland_ivanland_front_verification_pending days = 3 }",
        verifier_call,
    ):
        if token not in startup_ivn_bridge:
            issues.append(f"Ivanland startup front-verifier bridge is missing {token}")

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
        "ADISCORD_vorkerland_collapse.40 days = 1",
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

    selevyostrov = named_block(effects, "ADISCORD_vorkerland_appoint_selevyostrov")
    for token in (
        "ruling_party = chauvinism",
        "promote_character = {",
        "character = IBL_Anton_Selevyostrov",
        "ideology = chauvinism_ideology",
        "portrait = GFX_portrait_IBL_Anton_Selevyostrov",
        "ADISCORD_vorkerland_selevyostrov_character_repair_v1",
    ):
        if token not in selevyostrov:
            issues.append(f"Selevyostrov appointment is missing {token}")
    if "create_country_leader" in selevyostrov or "recruit_character" in selevyostrov:
        issues.append("Selevyostrov appointment must use the pre-recruited character API")
    if mandate.find("ADISCORD_vorkerland_appoint_mateusk = yes") < mandate.find("puppet = IBA"):
        issues.append("Mateusk must be appointed after IBA is puppeted so the political rebuild cannot replace him")
    owned_by_iba = set(re.findall(r"transfer_state\s*=\s*(\d+)", mandate))
    if owned_by_iba != {"90", "91"} or "transfer_state = 71" in mandate:
        issues.append(f"Norvane ownership allowlist drifted from states 90-91: {sorted(owned_by_iba)}")
    krait_setup = named_block(effects, "ADISCORD_vorkerland_setup_ibl")
    if set(re.findall(r"transfer_state\s*=\s*(\d+)", krait_setup)) != {"93", "94"}:
        issues.append("Krait ownership allowlist drifted from states 93-94")
    krait_expansion = named_block(effects, "ADISCORD_vorkerland_expand_krait_client")
    if "ADISCORD_vorkerland_setup_ibl = yes" not in krait_expansion:
        issues.append("legacy Krait expansion wrapper no longer delegates to the canonical IBL setup")
    if "ADISCORD_vorkerland_setup_ibl = yes" not in mandate:
        issues.append("Ivanland success settlement does not create the separate IBL client")
    war_cleanup = named_block(effects, "ADISCORD_vorkerland_end_ivanland_intervention_wars")
    cleanup_ivn = named_block(war_cleanup, "IVN")
    for flag in (
        "ADISCORD_vorkerland_ivanland_front_launch_pending",
        "ADISCORD_vorkerland_ivanland_front_verification_pending",
        war_retry_flag,
        join_retry_flag,
        "ADISCORD_vorkerland_ivanland_front_verified_v1",
    ):
        if f"clr_country_flag = {flag}" not in cleanup_ivn:
            issues.append(f"Ivanland intervention cleanup does not clear {flag}")
    for defender in ("PWR", "ZAO", "WPA", "WPS", "PSD"):
        if "remove_ideas = ADISCORD_vorkerland_northern_defense_front" not in named_block(
            war_cleanup, defender
        ):
            issues.append(f"Ivanland intervention cleanup leaves the defense idea on {defender}")
    for pair in (
        ("IVN", "ZAO"), ("IVN", "WPA"), ("IVN", "WPS"),
        ("IVN", "PWR"), ("IVN", "PSD"), ("IVN", "IBL"), ("IVN", "IBA"),
    ):
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
        "PWR = { transfer_state = 90 transfer_state = 91 }",
        "PSD = { transfer_state = 93 transfer_state = 94 }",
        "ADISCORD_vorkerland_vadim_etatist_role_added",
        "Ivanland intervention resolved: FAILURE",
    ):
        if token not in failure:
            issues.append(f"Ivanland failure is missing {token}")
    if "clr_global_flag = ADISCORD_vorkerland_ivanland_intervention_succeeded" not in failure:
        issues.append("Ivanland failure does not clear the mutually exclusive success flag")
    for token in (
        "91 = { add_core_of = PWR set_state_controller_to = PWR }",
        "93 = { set_state_controller_to = PSD }",
        "94 = { set_state_controller_to = PSD }",
        "clr_global_flag = ADISCORD_vorkerland_ivanland_krait_frontier_secured",
    ):
        if token not in failure:
            issues.append(f"Ivanland failure cannot restore the pre-intervention northern map: {token}")

    startup = named_block(on_actions, "on_startup")
    monthly = named_block(on_actions, "on_monthly")
    mateusk_repair_match = re.search(
        r"(?ms)^country_event\s*=\s*\{\s*id\s*=\s*ADISCORD_vorkerland_collapse\.40\b"
        r"(.*?)(?=^country_event\s*=\s*\{|^add_namespace\s*=|\Z)",
        events,
    )
    mateusk_repair = mateusk_repair_match.group(1) if mateusk_repair_match else ""
    for token in (
        "has_country_leader = {",
        "character = IBA_Matvey_Mateusk",
        "ruling_only = yes",
        "ADISCORD_vorkerland_appoint_mateusk = yes",
        "ADISCORD_vorkerland_end_ivanland_intervention_wars = yes",
    ):
        if token not in mateusk_repair:
            issues.append(f"Mateusk deferred repair is missing {token}")
    if "ADISCORD_vorkerland_collapse.40 days = 1" not in startup:
        issues.append("on_startup does not schedule the one-shot Mateusk save repair")
    if "ADISCORD_vorkerland_appoint_mateusk = yes" in monthly:
        issues.append("Mateusk repair still polls every country on_monthly")

    selevyostrov_repair_match = re.search(
        r"(?ms)^country_event\s*=\s*\{\s*id\s*=\s*ADISCORD_vorkerland_collapse\.42\b"
        r"(.*?)(?=^country_event\s*=\s*\{|^add_namespace\s*=|\Z)",
        events,
    )
    selevyostrov_repair = selevyostrov_repair_match.group(1) if selevyostrov_repair_match else ""
    for token in (
        "tag = IBL",
        "character = IBL_Anton_Selevyostrov",
        "ruling_only = yes",
        "ADISCORD_vorkerland_appoint_selevyostrov = yes",
    ):
        if token not in selevyostrov_repair:
            issues.append(f"Selevyostrov deferred repair is missing {token}")
    if "ADISCORD_vorkerland_collapse.42 days = 1" not in startup:
        issues.append("on_startup does not schedule the targeted Selevyostrov save repair")
    if "ADISCORD_vorkerland_appoint_selevyostrov = yes" in monthly:
        issues.append("Selevyostrov repair must not poll on_monthly")
    joint_repair_match = re.search(
        r"(?ms)^country_event\s*=\s*\{\s*id\s*=\s*ADISCORD_vorkerland_collapse\.62\b"
        r"(.*?)(?=^country_event\s*=\s*\{|^add_namespace\s*=|\Z)",
        events,
    )
    joint_repair = joint_repair_match.group(1) if joint_repair_match else ""
    for token in ("tag = VAD", "ADISCORD_vorkerland_appoint_joint_council = yes"):
        if token not in joint_repair:
            issues.append(f"Vorkerland joint-government delayed repair is missing {token}")
    if "ADISCORD_vorkerland_collapse.62 days = 1" not in startup:
        issues.append("on_startup does not schedule the one-shot joint-government repair")
    if "ADISCORD_vorkerland_appoint_joint_council = yes" in monthly:
        issues.append("joint-government repair still polls on_monthly")
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
    claimant_cosmetics = named_block(
        effects, "ADISCORD_vorkerland_apply_claimant_cosmetics"
    )
    vad_cosmetics = named_block(claimant_cosmetics, "VAD")
    joint_cosmetics = named_block(vad_cosmetics, "if")
    ordinary_vad_cosmetics = named_block(vad_cosmetics, "else")
    for token in (
        "has_global_flag = ADISCORD_vorkerland_joint_government_formed",
        "set_cosmetic_tag = WRK_vorkerland_joint_government",
        "ADISCORD_vorkerland_appoint_joint_council = yes",
    ):
        if token not in joint_cosmetics:
            issues.append(f"VAD claimant cosmetics do not preserve joint identity: {token}")
    for token in (
        "set_cosmetic_tag = VAD_vorkerland_restoration",
        "portrait = GFX_portrait_WRK_Vlad_Petrichev_civilwar",
    ):
        if token not in ordinary_vad_cosmetics:
            issues.append(f"ordinary VAD claimant cosmetics are missing {token}")
        if token in joint_cosmetics:
            issues.append(f"joint VAD claimant cosmetics still apply ordinary identity: {token}")

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
            "major = yes", "is_triggered_only = yes", "fire_only_once = yes",
            f"title = {news_id}.t", f"desc = {news_id}.d",
            f"option = {{ name = {news_id}.a }}",
        ):
            if token not in body:
                issues.append(f"{news_id}: definition is missing {token}")
        if "hidden = yes" in body:
            issues.append(f"{news_id}: world news is incorrectly hidden")
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
    if "ADISCORD_vorkerland_erased_nations" not in effects or "ADISCORD_vorkerland_erased_nations" not in ideas:
        issues.append("cultural-erasure legacy is not represented as a national spirit")
    erased_nations = named_block(ideas, "ADISCORD_vorkerland_erased_nations")
    if "picture = generic_oppression" not in erased_nations:
        issues.append("cultural-erasure spirit must use the registered generic_oppression picture")
    for token in (
        "stability_factor = -0.25", "war_support_factor = -0.15",
        "recruitable_population_factor = -0.20", "industrial_capacity_factory = -0.15",
        "consumer_goods_factor = 0.15", "political_power_gain = -0.20",
        "army_org_factor = -0.10",
    ):
        if token not in erased_nations:
            issues.append(f"severe cultural-erasure spirit is missing {token}")
    macri_mission = named_block(
        ideas, "ADISCORD_vorkerland_piv_macri_volunteer_mission"
    )
    if "picture = generic_volunteer_expedition_bonus" not in macri_mission:
        issues.append(
            "Macri volunteer mission must use the registered generic_volunteer_expedition_bonus picture"
        )
    prepare = named_block(effects, "ADISCORD_vorkerland_prepare_conflict_country")
    initial = named_block(effects, "ADISCORD_vorkerland_prepare_initial_combatants")
    if prepare.count("every_owned_state") != 1 or not re.search(
        r"every_owned_state\s*=\s*\{\s*add_core_of\s*=\s*ROOT\s*\}",
        prepare,
    ):
        issues.append("collapse preparation must grant every participant cores in its one-time setup")
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
    for tag in ("WKR", "VAD", "VLA", "ZAO", "PWR", "ROM", "SOL", "TRU"):
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
    mobilized_tags = {"TVA", "EYR", "EGC", "RIV", "REV", "YOR", "NDN", "SWB", "VHV", "OSV", "PSD", "DVA", "SRA", "IBL", "IBA", "CSL"}
    for tag in republic_tags | mobilized_tags:
        if f"tag = {tag}" not in prepare:
            issues.append(f"{tag}: replacement spirit has no explicit preparation guard")
    for spirit in (
        "ADISCORD_vorkerland_republics_from_the_ruins",
        "ADISCORD_vorkerland_mobilized_periphery",
    ):
        if f"add_ideas = {spirit}" not in prepare:
            issues.append(f"collapse preparation does not add replacement spirit {spirit}")

    repeatable_decisions = {
        "ADISCORD_vorkerland_wrk_activate_front_committees": ("WKR", "ADISCORD_vorkerland_wrk_front_committees"),
        "ADISCORD_vorkerland_wrk_requisition_rail_stock": ("WKR", "ADISCORD_vorkerland_wrk_rail_requisition"),
        "ADISCORD_vorkerland_vad_open_imperial_registers": ("VAD", "ADISCORD_vorkerland_vad_imperial_registers"),
        "ADISCORD_vorkerland_vad_form_field_commandantures": ("VAD", "ADISCORD_vorkerland_vad_field_commandantures"),
        "ADISCORD_vorkerland_tva_reroute_city_grid": ("TVA", "ADISCORD_vorkerland_tva_grid_rerouting"),
        "ADISCORD_vorkerland_tva_deploy_field_laboratories": ("TVA", "ADISCORD_vorkerland_tva_field_laboratories"),
    }
    for decision_id, (tag, spirit) in repeatable_decisions.items():
        decision = named_block(decisions, decision_id)
        for token in (
            f"allowed = {{ tag = {tag} }}",
            "has_war = yes",
            "fire_only_once = no",
            "days_re_enable =",
            f"add_timed_idea = {{ idea = {spirit}",
        ):
            if token not in decision:
                issues.append(f"{decision_id}: dynamic claimant decision is missing {token}")
        if not named_block(ideas, spirit):
            issues.append(f"{decision_id}: timed national spirit {spirit} is missing")
    vad_route_decisions = {
        "ADISCORD_vorkerland_vad_open_imperial_registers": (
            "ADISCORD_vorkerland_focus_vad_registers_opened",
            "ADISCORD_vorkerland_focus_vad_commandantures_formed",
        ),
        "ADISCORD_vorkerland_vad_form_field_commandantures": (
            "ADISCORD_vorkerland_focus_vad_commandantures_formed",
            "ADISCORD_vorkerland_focus_vad_registers_opened",
        ),
    }
    for decision_id, (selected_flag, rejected_flag) in vad_route_decisions.items():
        decision = named_block(decisions, decision_id)
        for section_name in ("visible", "available"):
            section = named_block(decision, section_name)
            for token in (
                f"has_country_flag = {selected_flag}",
                f"NOT = {{ has_country_flag = {rejected_flag} }}",
            ):
                if token not in section:
                    issues.append(
                        f"{decision_id}: {section_name} lacks exclusive route gate {token}"
                    )
    field_labs = named_block(
        decisions, "ADISCORD_vorkerland_tva_deploy_field_laboratories"
    )
    if "army_experience = 5" not in field_labs or "add_army_experience" in field_labs:
        issues.append("Doctor Worx field laboratories use an invalid army-experience effect")

    tva_setup = named_block(effects, "ADISCORD_vorkerland_setup_tva")
    for token in (
        "add_ideas = ADISCORD_vorkerland_tva_field_directorate",
        "add_ideas = ADISCORD_vorkerland_tva_ideological_fanaticism",
        "add_manpower = 11000",
        "type = infantry_equipment_0 amount = 1800 producer = TVA",
        "type = support_equipment amount = 120 producer = TVA",
        "type = artillery_equipment amount = 72 producer = TVA",
    ):
        if token not in tva_setup:
            issues.append(f"Doctor Worx starting package is missing {token}")
    tva_directorate = named_block(ideas, "ADISCORD_vorkerland_tva_field_directorate")
    for modifier in (
        "research_speed_factor = 0.05",
        "industrial_capacity_factory = 0.10",
        "army_org_factor = 0.06",
        "supply_consumption_factor = -0.08",
    ):
        if modifier not in tva_directorate:
            issues.append(f"Doctor Worx permanent directorate spirit is missing {modifier}")

    fanaticism = named_block(ideas, "ADISCORD_vorkerland_tva_ideological_fanaticism")
    for modifier in (
        "surrender_limit = 0.25",
        "war_support_factor = 0.10",
        "army_org_regain = 0.05",
    ):
        if modifier not in fanaticism:
            issues.append(f"Doctor Worx ideological fanaticism is missing {modifier}")
    state_36_paths = list((root / "history" / "states").glob("36-*.txt"))
    state_36 = state_36_paths[0].read_text(encoding="utf-8-sig") if len(state_36_paths) == 1 else ""
    if not re.search(r"victory_points\s*=\s*\{\s*12227\s+60\s*\}", state_36):
        issues.append("Vorkensberg city must be worth 60 victory points")

    technical_battalions = named_block(
        decisions, "ADISCORD_vorkerland_tva_raise_technical_battalions"
    )
    for token in (
        "allowed = { tag = TVA }", "cost = 40", "days_re_enable = 60",
        "36 = {", "owner = TVA", "owner = WPS", "owner = TGD",
        "add_manpower = 1800", "amount = 300 producer = TVA",
    ):
        if token not in technical_battalions:
            issues.append(f"Doctor Worx technical battalions decision is missing {token}")
    if technical_battalions.count("create_unit =") != 4:
        issues.append("Doctor Worx technical battalions decision must create two home and two conditional allied units")
    if technical_battalions.count("amount = 120 producer = TVA") != 2:
        issues.append("Doctor Worx technical allies do not receive two finite rifle grants")

    for token in (
        "ADISCORD_grant_technology_profile_industrial = yes",
        "ADISCORD_grant_technology_profile_energy = yes",
        "ADISCORD_grant_technology_profile_institutional = yes",
        "ADISCORD_grant_technology_profile_land = yes",
        "ADISCORD_grant_technology_profile_air = yes",
        "type = ADISCORD_combat_platform_2170 amount = 180 producer = TVA",
        "type = ADISCORD_fighter_airframe_2163 amount = 36 producer = TVA",
        "type = ADISCORD_cas_airframe_2170 amount = 18 producer = TVA",
    ):
        if token not in tva_setup:
            issues.append(f"Doctor Worx advanced starting package is missing {token}")

    disruption = named_block(decisions, "ADISCORD_vorkerland_tva_disrupt_enemy_logistics")
    for token in (
        "any_neighbor_country =", "every_neighbor_country =", "has_war_with = ROOT",
        "add_timed_idea = { idea = ADISCORD_vorkerland_tva_logistics_disruption days = 30 }",
        "days_re_enable = 45",
    ):
        if token not in disruption:
            issues.append(f"Doctor Worx logistics disruption is missing {token}")
    disruption_idea = named_block(ideas, "ADISCORD_vorkerland_tva_logistics_disruption")
    for token in (
        "supply_consumption_factor = 0.12", "army_org_regain = -0.08",
        "repair_speed_factor = -0.15", "planning_speed = -0.10",
    ):
        if token not in disruption_idea:
            issues.append(f"Doctor Worx logistics disruption spirit is missing {token}")

    for target, states in (("wrk", (33, 34)), ("vad", (75, 106))):
        partisan = named_block(decisions, f"ADISCORD_vorkerland_tva_infiltrate_{target}_rear")
        if partisan.count("create_unit =") != 2 or partisan.count("allow_spawning_on_enemy_provs = yes") != 2:
            issues.append(f"Doctor Worx {target.upper()} infiltration must create exactly two enemy-rear cells")
        for state in states:
            if f"{state} = {{" not in partisan:
                issues.append(f"Doctor Worx {target.upper()} infiltration is missing state {state}")
        for token in ("TVA Infiltration Cell", "fire_only_once = yes"):
            if token not in partisan:
                issues.append(f"Doctor Worx {target.upper()} infiltration is missing {token}")

    fortification = named_block(decisions, "ADISCORD_vorkerland_tva_seal_city_approaches")
    for token in (
        "province = 12227", "province = 16400", "province = 16397",
        "type = bunker", "level = 2", "fire_only_once = yes",
        "ADISCORD_vorkerland_tva_prepared_defense",
    ):
        if token not in fortification:
            issues.append(f"Doctor Worx one-time fortification is missing {token}")
    rotation = named_block(decisions, "ADISCORD_vorkerland_tva_rotate_fortress_garrisons")
    if "add_building_construction" in rotation or "fire_only_once = no" not in rotation:
        issues.append("Doctor Worx repeatable garrison rotation can permanently spam forts")

    relief_chain = (
        ("ADISCORD_vorkerland_wrk_open_erased_archives", "ADISCORD_vorkerland_erased_nations", "ADISCORD_vorkerland_erased_nations_relief_1", 90),
        ("ADISCORD_vorkerland_wrk_restore_displaced_councils", "ADISCORD_vorkerland_erased_nations_relief_1", "ADISCORD_vorkerland_erased_nations_relief_2", 120),
        ("ADISCORD_vorkerland_wrk_enact_constitutional_guarantees", "ADISCORD_vorkerland_erased_nations_relief_2", None, 150),
    )
    for decision_id, old_spirit, new_spirit, days in relief_chain:
        decision = named_block(decisions, decision_id)
        for token in (
            "allowed = { tag = WKR }", f"has_idea = {old_spirit}",
            f"days_remove = {days}", f"remove_ideas = {old_spirit}",
            "has_global_flag = ADISCORD_vorkerland_collapse_started",
        ):
            if token not in decision:
                issues.append(f"{decision_id}: cultural-erasure relief chain is missing {token}")
        if new_spirit and f"add_ideas = {new_spirit}" not in decision:
            issues.append(f"{decision_id}: cultural-erasure relief chain does not add {new_spirit}")
    for key in (
        "ADISCORD_vorkerland_tva_disrupt_enemy_logistics",
        "ADISCORD_vorkerland_tva_infiltrate_wrk_rear",
        "ADISCORD_vorkerland_tva_infiltrate_vad_rear",
        "ADISCORD_vorkerland_tva_seal_city_approaches",
        "ADISCORD_vorkerland_tva_rotate_fortress_garrisons",
        "ADISCORD_vorkerland_wrk_open_erased_archives",
        "ADISCORD_vorkerland_wrk_restore_displaced_councils",
        "ADISCORD_vorkerland_wrk_enact_constitutional_guarantees",
    ):
        if f" {key}:" not in loc or f" {key}_desc:" not in loc:
            issues.append(f"{key}: missing Russian localisation")

    integrations = {
        "ADISCORD_vorkerland_tva_integrate_wps": ("TVA", "WPS", 196, "autonomy_puppet"),
        "ADISCORD_vorkerland_tva_integrate_tgd": ("TVA", "TGD", 105, "autonomy_puppet"),
    }
    for decision_id, (claimant, target, state, autonomy) in integrations.items():
        decision = named_block(decisions, decision_id)
        for token in (
            f"allowed = {{ tag = {claimant} }}",
            f"controls_state = {state}",
            f"puppet = {target}",
            f"set_autonomy = {{ target = {target} autonomy_state = {autonomy}",
        ):
            if token not in decision:
                issues.append(f"{decision_id}: regional-winner integration is missing {token}")

    legacy_diplomacy = (
        "ADISCORD_vorkerland_wrk_integrate_vla",
        "ADISCORD_vorkerland_vad_recognize_sol",
    )
    for decision_id in legacy_diplomacy:
        if named_block(decisions, decision_id):
            issues.append(f"{decision_id}: legacy collapse diplomacy bypass survived")
        if f" {decision_id}:" in loc or f" {decision_id}_desc:" in loc:
            issues.append(f"{decision_id}: stale collapse localisation survived")

    canonical_diplomacy = {
        "ADISCORD_vorkerland_wkr_invite_victorious_vla": (
            "allowed = { tag = WKR }",
            "has_country_flag = ADISCORD_vorkerland_focus_wkr_vla_invitation_intent",
            "has_global_flag = ADISCORD_vorkerland_volnograd_terminal_verified",
            "has_global_flag = ADISCORD_vorkerland_volnograd_winner_vla",
            "complete_effect = { ADISCORD_vorkerland_offer_wkr_vla_alliance = yes }",
        ),
        "ADISCORD_vorkerland_vad_invite_victorious_sol": (
            "allowed = { tag = VAD }",
            "has_country_flag = ADISCORD_vorkerland_focus_vad_sol_invitation_intent",
            "has_country_flag = ADISCORD_vorkerland_focus_vad_solland_liaison_prepared",
            "has_global_flag = ADISCORD_vorkerland_solar_terminal_verified",
            "has_global_flag = ADISCORD_vorkerland_solar_winner_sol",
            "complete_effect = { ADISCORD_vorkerland_offer_vad_sol_alliance = yes }",
        ),
    }
    for decision_id, tokens in canonical_diplomacy.items():
        decision = named_block(diplomacy_decisions, decision_id)
        if not decision:
            issues.append(f"{decision_id}: canonical diplomacy decision owner is missing")
            continue
        for token in tokens:
            if token not in decision:
                issues.append(f"{decision_id}: canonical diplomacy flow is missing {token}")
        for bypass in ("controls_state =", "puppet =", "set_autonomy =", "declare_war_on ="):
            if bypass in decision:
                issues.append(f"{decision_id}: canonical invitation contains legacy bypass {bypass}")

    republic_sync = named_block(effects, "ADISCORD_vorkerland_sync_republics_from_ruins")
    for token in (
        "is_subject_of = WKR",
        "remove_ideas = ADISCORD_vorkerland_republics_from_the_ruins",
    ):
        if token not in republic_sync:
            issues.append(f"WRK subject-spirit synchronizer is missing {token}")

    for patron, flag, spirit, rifles in (
        ("btl", "ADISCORD_vorkerland_btl_contract_signed", "ADISCORD_vorkerland_btl_contract_support", 250),
        ("val", "ADISCORD_vorkerland_val_contract_signed", "ADISCORD_vorkerland_val_contract_support", 400),
    ):
        if not named_block(ideas, spirit):
            issues.append(f"{patron.upper()}: support spirit {spirit} is missing")
        for claimant in ("wrk", "vad", "tva"):
            decision_id = f"ADISCORD_vorkerland_{patron}_support_{claimant}"
            decision = named_block(decisions, decision_id)
            for token in (
                f"NOT = {{ has_global_flag = {flag} }}",
                f"set_global_flag = {flag}",
                f"add_ideas = {spirit}",
                f"amount = {rifles}",
            ):
                if token not in decision:
                    issues.append(f"{decision_id}: exclusive external support is missing {token}")
            if patron == "val" and "type = support_equipment amount = 60 producer = VAL" not in decision:
                issues.append(f"{decision_id}: Kefreyt support-equipment shipment is missing")

    btl_contract = named_block(ideas, "ADISCORD_vorkerland_btl_volunteer_contract")
    for token in (
        "can_send_volunteers = yes", "send_volunteers_tension = -1.0",
        "send_volunteer_divisions_required = -0.90", "send_volunteer_size = 1",
    ):
        if token not in btl_contract:
            issues.append(f"BTL volunteer contract is missing {token}")
    if 'BTL_Paul_Dorini: "Пауль Дорини"' not in countries_loc:
        issues.append("BTL leader Paul Dorini lacks Russian localisation")

    second_intervention = named_block(decisions, "ADISCORD_ivanland_second_intervention")
    for token in (
        "allowed = { tag = IVN }",
        "ADISCORD_vorkerland_ivanland_intervention_resolved",
        "has_war_with = VAD", "has_war_with = WKR",
        "NOT = { country_exists = TVA }",
        "var = ADISCORD_vorkerland_civil_war_exhaustion",
        "compare = greater_than_or_equals", "target = PSD", "target = PWR",
        "cost = 75", "ADISCORD_vorkerland_ivanland_second_intervention_started",
    ):
        if token not in second_intervention:
            issues.append(f"Ivanland second intervention is missing {token}")
    if second_intervention.count("declare_war_on =") != 2 or "add_to_war" in second_intervention:
        issues.append("Ivanland second intervention must open exactly two independent wars")
    if second_intervention.count("value = 100") != 3:
        issues.append("Ivanland second intervention does not test every surviving main claimant")

    island_occupation = named_block(decisions, "ADISCORD_ivanland_occupy_wrk_islands")
    for token in (
        "allowed = { tag = IVN }", "NOT = { has_war_with = WKR }",
        "200 = { is_owned_by = WKR is_controlled_by = WKR }",
        "201 = { is_owned_by = WKR is_controlled_by = WKR }",
        "transfer_state = 200", "transfer_state = 201", "cost = 50",
    ):
        if token not in island_occupation:
            issues.append(f"Ivanland peaceful island occupation is missing {token}")

    rom_intervention = named_block(decisions, "ADISCORD_vorkerland_rom_northern_intervention")
    for token in (
        "allowed = { tag = ROM }", "is_subject = no", "has_war = no",
        "generator = { 72 }", "generator = { 196 322 }",
        "days_mission_timeout = 240",
        "ADISCORD_vorkerland_rom_northern_intervention_success = yes",
        "ADISCORD_vorkerland_rom_northern_intervention_failure = yes",
    ):
        if token not in rom_intervention:
            issues.append(f"Frealor northern intervention is missing {token}")
    if rom_intervention.count("declare_war_on =") != 2:
        issues.append("Frealor northern intervention must open two limited wars")
    rom_success = named_block(effects, "ADISCORD_vorkerland_rom_northern_intervention_success")
    for state in (72, 196, 322):
        if f"transfer_state = {state}" not in rom_success or f"{state} = {{ add_claim_by = ROM" not in rom_success:
            issues.append(f"Frealor intervention success does not award claimed state {state}")

    zao_security = named_block(effects, "ADISCORD_vorkerland_ivanland_secure_zaozersk")
    for token in (
        "NOT = { country_exists = ZAO }", "transfer_state = 72",
        "release_autonomy =", "target = ZAO", "puppet = ZAO",
        "autonomy_state = autonomy_puppet",
        "ADISCORD_vorkerland_ivanland_zaozersk_secured",
    ):
        if token not in zao_security:
            issues.append(f"successful Ivanland intervention cannot secure Zaozersk: {token}")
    ivn_success = named_block(effects, "ADISCORD_vorkerland_ivanland_intervention_success")
    if "ADISCORD_vorkerland_ivanland_secure_zaozersk = yes" not in ivn_success:
        issues.append("Ivanland success does not invoke the Zaozersk protectorate effect")
    if "ADISCORD_vorkerland_ivanland_secure_zaozersk = yes" not in named_block(on_actions, "on_startup"):
        issues.append("successful old saves do not complete the Zaozersk protectorate")

    guarantee = named_block(decisions, "ADISCORD_ivanland_guarantee_free_republics")
    for token in (
        "allowed = { tag = IVN }", "cost = 100",
        "ADISCORD_vorkerland_ivanland_intervention_succeeded",
        "NOT = { has_global_flag = ADISCORD_vorkerland_central_war_finished }",
        "ROM = { is_neighbor_of = ROOT }", "country = ROM relation = guarantee",
        "country = TRU relation = guarantee",
        "ADISCORD_vorkerland_free_republics_guaranteed_by_ivn",
    ):
        if token not in guarantee:
            issues.append(f"Ivanland free-republic guarantee is missing {token}")
    republic_resolution = named_block(effects, "ADISCORD_vorkerland_resolve_unguaranteed_free_republics")
    for token in (
        "NOT = { has_global_flag = ADISCORD_vorkerland_free_republics_guaranteed_by_ivn }",
        "puppet = ROM", "puppet = TRU",
        "autonomy_state = autonomy_republic_in_Vorkerland",
        "target = ROM type = annex_everything", "target = TRU type = annex_everything",
        "ADISCORD_vorkerland_free_republics_resolution_done",
    ):
        if token not in republic_resolution:
            issues.append(f"Worker free-republic settlement is missing {token}")
    if republic_resolution.count("random_list =") != 2:
        issues.append("Worker free-republic settlement must roll independently for ROM and TRU")
    worker_map = named_block(map_effects, "ADISCORD_vorkerland_apply_worker_map")
    finalizer = named_block(phase_effects, "ADISCORD_vorkerland_finalize_reunified_wrk")
    if "ADISCORD_vorkerland_resolve_unguaranteed_free_republics = yes" not in finalizer:
        issues.append("verified Worker reunification does not resolve unguaranteed free republics")
    for route, map_effect in (
        ("worker", worker_map),
        ("vlad", named_block(map_effects, "ADISCORD_vorkerland_apply_vlad_map")),
        ("dorian", named_block(map_effects, "ADISCORD_vorkerland_apply_dorian_map")),
    ):
        if "ADISCORD_vorkerland_begin_reunification = yes" not in map_effect:
            issues.append(f"{route} claimant outcome does not enter guarded reunification")
        for forbidden in (
            "ADISCORD_vorkerland_central_war_finished",
            "ADISCORD_vorkerland_collapse_finished",
            "ADISCORD_vorkerland_show_worker_victory_superevent",
            "ADISCORD_vorkerland_show_vlad_victory_superevent",
            "ADISCORD_vorkerland_show_dorian_victory_superevent",
            "ADISCORD_vorkerland_split_external_gate = yes",
        ):
            if forbidden in map_effect:
                issues.append(f"{route} claimant outcome announces/finalizes before verified WRK: {forbidden}")

    for key in (
        "ADISCORD_ivanland_second_intervention",
        "ADISCORD_ivanland_occupy_wrk_islands",
        "ADISCORD_vorkerland_rom_northern_intervention",
        "ADISCORD_ivanland_guarantee_free_republics",
    ):
        if f" {key}:" not in loc or f" {key}_desc:" not in loc:
            issues.append(f"{key}: missing Russian localisation")

    collapse_runtime = "\n".join((effects, map_effects, on_actions, events, decisions))
    collapse_removals = set(
        re.findall(r"remove_ideas\s*=\s*([A-Za-z0-9_]+)", collapse_runtime)
    )
    allowed_collapse_removals = expected_prepare_removals | {
        "ADISCORD_vorkerland_piv_macri_volunteer_mission",
        "ADISCORD_vorkerland_tgd_grid_collapse",
        "ADISCORD_vorkerland_erased_nations_relief_1",
        "ADISCORD_vorkerland_erased_nations_relief_2",
        "ADISCORD_vorkerland_republics_from_the_ruins",
        "WRK_birthplace_of_the_first_revolution",
        "WRK_birthplace_of_the_first_revolution_front_republic",
        "ADISCORD_vorkerland_tva_field_directorate",
        "ADISCORD_vorkerland_tva_field_directorate_2",
        "ADISCORD_vorkerland_ivanland_expeditionary_command",
        "ADISCORD_vorkerland_northern_defense_front",
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
    finalizer = named_block(effects, "ADISCORD_vorkerland_finalize_conflict_spirits")
    if effects.count("add_ideas = ADISCORD_vorkerland_erased_nations") != 2 or not re.search(
        r"WKR\s*=\s*\{[^{}]*add_ideas\s*=\s*ADISCORD_vorkerland_erased_nations",
        initial,
        re.DOTALL,
    ) or "tag = WKR" not in finalizer:
        issues.append("cultural-erasure spirit must be added only to WKR")

    spirit_cleanup = re.search(
        r"(?ms)^country_event\s*=\s*\{\s*id\s*=\s*ADISCORD_vorkerland_collapse\.41\b"
        r"(.*?)(?=^country_event\s*=\s*\{|^add_namespace\s*=|\Z)",
        events,
    )
    spirit_cleanup_body = spirit_cleanup.group(1) if spirit_cleanup else ""
    for token in (
        "tag = WKR", "ADISCORD_vorkerland_finalize_conflict_spirits = yes",
        "set_global_flag = ADISCORD_vorkerland_conflict_spirits_finalized",
        "set_global_flag = ADISCORD_vorkerland_unique_spirits_finalized_v2",
    ):
        if token not in spirit_cleanup_body:
            issues.append(f"one-shot legacy-spirit cleanup is missing {token}")
    if "ADISCORD_vorkerland_collapse.41 days = 1" not in events:
        issues.append("collapse outbreak does not schedule the deferred legacy-spirit cleanup")
    if "ADISCORD_vorkerland_finalize_conflict_spirits = yes" in named_block(on_actions, "on_monthly"):
        issues.append("legacy-spirit cleanup must not poll on_monthly")

    for tag, spirit in (
        ("TVA", "ADISCORD_vorkerland_tva_ideological_fanaticism"),
        ("WPA", "ADISCORD_vorkerland_wpa_municipal_compact"),
        ("WPS", "ADISCORD_vorkerland_wps_factory_councils"),
        ("EBA", "ADISCORD_vorkerland_eba_free_quays"),
        ("ZTA", "ADISCORD_vorkerland_zta_golden_river_order"),
        ("TGD", "ADISCORD_vorkerland_tgd_grid_collapse"),
        ("CSL", "ADISCORD_vorkerland_csl_isolated_city"),
    ):
        if f"limit = {{ tag = {tag} }}" not in finalizer or f"add_ideas = {spirit}" not in finalizer:
            issues.append(f"{tag}: deferred spirit finalizer does not restore {spirit}")
    startup = named_block(on_actions, "on_startup")
    if "NOT = { has_global_flag = ADISCORD_vorkerland_unique_spirits_finalized_v2 }" not in startup:
        issues.append("startup lacks the one-shot v2 unique-spirit migration")
    for tag in ("TVA", "WPA", "WPS", "EBA", "ZTA", "TGD", "CSL"):
        if f"{tag} = {{ ADISCORD_vorkerland_finalize_conflict_spirits = yes }}" not in startup:
            issues.append(f"startup unique-spirit migration does not repair {tag}")

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

    for tag in ("TVA", "EYR", "EGC", "RIV", "REV", "YOR", "NDN", "SWB", "VHV", "OSV", "TGD", "EBA", "PSD", "DVA", "ZTA", "WPA", "WPS"):
        setup = named_block(effects, f"ADISCORD_vorkerland_setup_{tag.lower()}")
        manpower = re.search(r"add_manpower\s*=\s*(\d+)", setup)
        reserve = re.search(r"add_equipment_to_stockpile\s*=\s*\{[^{}]*amount\s*=\s*(\d+)", setup)
        minimum_manpower = 2000 if tag == "NDN" else 3000
        if not manpower or int(manpower.group(1)) < minimum_manpower:
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
    for tag in ("VAD",):
        country = re.search(rf"{tag}\s*=\s*\{{(.*?)\n\s*\}}", initial, re.DOTALL)
        if not country or "add_manpower = 8000" not in country.group(1) or "amount = 600" not in country.group(1):
            issues.append(f"{tag}: central claimant reserve is missing")
    wkr_initial = named_block(initial, "WKR")
    wkr_air_stockpile = "type = ADISCORD_fighter_airframe_2163 amount = 24 producer = WKR"
    wkr_air_oob = 'load_oob = "WRK_vorkerland_collapse_air"'
    if wkr_air_stockpile not in wkr_initial or wkr_air_oob not in wkr_initial:
        issues.append("WKR: claimant air stockpile or OOB load is missing")
    for technology in (
        "ADISCORD_tech_semi_autonomous_combat_modules = 1",
        "ADISCORD_tech_reclaimed_jet_platforms = 1",
        "ADISCORD_tech_battlefield_attack_aircraft = 1",
    ):
        if technology not in wkr_initial:
            issues.append(f"WKR: dormant claimant setup is missing pre-OOB technology {technology}")
        elif (
            wkr_air_stockpile in wkr_initial
            and wkr_air_oob in wkr_initial
            and wkr_initial.index(technology)
            > min(wkr_initial.index(wkr_air_stockpile), wkr_initial.index(wkr_air_oob))
        ):
            issues.append(f"WKR: {technology} must be granted before aircraft and air OOB materialize")
    legacy_reserves = {
        "ZAO": (4000, 850), "PWR": (8000, 1600), "VLA": (8000, 1800),
        "ROM": (6000, 1200), "SOL": (3000, 500), "TRU": (7000, 1400),
    }
    for tag, (manpower, rifles) in legacy_reserves.items():
        country = named_block(initial, tag)
        if f"add_manpower = {manpower}" not in country or f"amount = {rifles}" not in country:
            issues.append(f"{tag}: finite collapse reserve is missing")
    tva_oob = read(root, "history/units/TVA_vorkerland_collapse.txt", issues)
    if tva_oob.count("division = {") != 15 or "TVA Mobile Test Group" not in tva_oob or "TVA Infiltration Cell" not in tva_oob:
        issues.append("TVA must start with fourteen militia formations, one mobile group and an infiltration template")
    for tag in ("VAD",):
        oob = read(root, f"history/units/{tag}.txt", issues)
        initial_country = named_block(initial, tag)
        if oob.count("division = {") != 12 or "ADISCORD_combat_platform" not in oob:
            issues.append(f"{tag} must retain twelve pre-collapse formations and a mobile template")
        for token in (
            f"owner = {tag}", "create_unit =", "ADISCORD_combat_platform_2170",
            "ADISCORD_fighter_airframe_2163", "ADISCORD_cas_airframe_2170",
        ):
            if token not in initial_country:
                issues.append(f"{tag}: post-technology mobile/air package is missing {token}")
    central_minor_oobs = {
        "EYR": 6, "EGC": 5, "RIV": 6, "REV": 5, "YOR": 5,
        "NDN": 4, "SWB": 4, "VHV": 5, "OSV": 4,
    }
    for tag, divisions in central_minor_oobs.items():
        oob = read(root, f"history/units/{tag}_vorkerland_collapse.txt", issues)
        if oob.count("division = {") != divisions:
            issues.append(f"{tag} must start with exactly {divisions} militia divisions")

    central_minor_reserves = {
        "EYR": (6500, 800), "EGC": (5500, 650), "RIV": (7000, 850),
        "REV": (5500, 650), "YOR": (5500, 650), "NDN": (4500, 550),
        "SWB": (4500, 550), "VHV": (5500, 650), "OSV": (4500, 550),
    }
    for tag, (manpower, rifles) in central_minor_reserves.items():
        setup = named_block(effects, f"ADISCORD_vorkerland_setup_{tag.lower()}")
        if f"add_manpower = {manpower}" not in setup or f"amount = {rifles} producer = {tag}" not in setup:
            issues.append(f"{tag}: approved finite manpower/rifle reserve is missing")

    minor_trigger = named_block(triggers, "ADISCORD_vorkerland_is_minor_combatant")
    for tag in central_minor_oobs:
        if f"tag = {tag}" not in minor_trigger:
            issues.append(f"{tag}: missing from the bounded emergency-levy allowlist")
    if "ADISCORD_vorkerland_is_regional_combatant = yes" not in minor_trigger:
        issues.append("regional combatants are missing from the bounded emergency-levy allowlist")
    for tag in ("WRK", "VAD", "TVA", "IVN", "EXZ"):
        if f"tag = {tag}" in minor_trigger:
            issues.append(f"{tag}: must not receive the minor emergency levy")
    levies = named_block(effects, "ADISCORD_vorkerland_raise_emergency_levies")
    for token in (
        "add_manpower = 1800", "amount = 360 producer = ROOT",
        'division_template = \\"Emergency Militia\\"', "count = 2",
    ):
        if token not in levies:
            issues.append(f"bounded emergency levy is missing {token}")
    if "every_country" in levies or "every_state" in levies:
        issues.append("bounded emergency levy must not perform a global country/state scan")
    levy_decision = named_block(decisions, "ADISCORD_vorkerland_raise_emergency_levies")
    for token in (
        "allowed = { ADISCORD_vorkerland_is_minor_combatant = yes }",
        "has_war = yes", "cost = 25", "days_remove = 21",
        "fire_only_once = yes",
        "remove_effect = { ADISCORD_vorkerland_raise_emergency_levies = yes }",
    ):
        if token not in levy_decision:
            issues.append(f"bounded emergency-levy decision is missing {token}")
    if "ADISCORD_vorkerland_raise_emergency_levies" in on_actions:
        issues.append("emergency levies must be decision-driven, not polled by on_actions")

    ivn_oob = read(root, "history/units/IVN.txt", issues)
    ivn_units = named_block(ivn_oob, "units")
    if "set_major = yes" not in ivn_history or "set_research_slots = 5" not in ivn_history:
        issues.append("IVN must start as a major with five research slots")
    if ivn_units.count("division = {") != 16:
        issues.append("IVN must start with exactly sixteen field formations")
    for template, count in (("Capital Guard", 2), ("Line Infantry Brigade", 10), ("Local Security Detachment", 4)):
        if ivn_units.count(f'division_template = "{template}"') != count:
            issues.append(f"IVN must field exactly {count} {template} formations")
    equipment_factors = [float(value) for value in re.findall(r"start_equipment_factor\s*=\s*([0-9.]+)", ivn_units)]
    if len(equipment_factors) != 16 or min(equipment_factors, default=0.0) < 0.70:
        issues.append("IVN field formations must start at 70 percent equipment or better")
    ivn_locations = {int(value) for value in re.findall(r"location\s*=\s*(\d+)", ivn_units)}
    if ivn_locations != {16568, 9327, 3462, 3318, 888, 838, 2448, 882, 702, 595, 1971, 3447, 579, 2262, 423, 4217}:
        issues.append("IVN field formations are not distributed across all sixteen home states")
    intervention_start = named_block(effects, "ADISCORD_vorkerland_begin_ivanland_intervention")
    for token in (
        "ADISCORD_vorkerland_ivanland_expedition_supplied", "add_manpower = 8000",
        "amount = 1600 producer = IVN", "type = support_equipment amount = 120 producer = IVN",
        "type = artillery_equipment amount = 48 producer = IVN", "add_fuel = 5000",
    ):
        if token not in intervention_start:
            issues.append(f"IVN one-shot expedition reserve is missing {token}")
    zta_oob = read(root, "history/units/ZTA_vorkerland_collapse.txt", issues)
    if zta_oob.count("division = {") != 3:
        issues.append("ZTA must retain exactly three militia divisions after the northern split")

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
        expected = 5 if tag in {"PWR", "PSD"} else 3
        if oob.count("division = {") != expected or len(equipment) != expected or min(equipment, default=0) < 0.55:
            issues.append(f"{tag}: local war OOB must contain {expected} supplied formations")

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
    for tag in ("ROM", "TRU", "ZAO"):
        if "ADISCORD_vorkerland_sync_independence_cosmetic = yes" not in named_block(cosmetics, tag):
            issues.append(f"{tag}: collapse independence cosmetic is not synchronized")
    for token in (
        "set_cosmetic_tag = PWR_rimat_republic",
        "ADISCORD_vorkerland_appoint_pwr_technocrat = yes",
        "ADISCORD_vorkerland_collapse.44 days = 1",
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
    for hook in ("on_puppet", "on_release_as_puppet", "on_release_as_free"):
        if "ADISCORD_vorkerland_sync_independence_cosmetic = yes" not in named_block(on_actions, hook):
            issues.append(f"{hook} does not synchronize republic/dependency cosmetics")
    if "ADISCORD_vorkerland_sync_independence_cosmetic = yes" in named_block(on_actions, "on_monthly"):
        issues.append("republic cosmetic synchronization still polls on_monthly")
    loyalist = named_block(decisions, "ADISCORD_vorkerland_restore_loyalist_district")
    if set(re.findall(r"tag\s*=\s*([A-Z]{3})", named_block(loyalist, "allowed"))) != {"ZAO", "VLA"}:
        issues.append("only ZAO/VLA may voluntarily restore loyalist district status")
    if "ADISCORD_vorkerland_northern_loyalist_district_restored" in decisions + on_actions:
        issues.append("obsolete shared ZAO/PWR loyalist slot survived")
    for token in (
        "is_subject = no", "has_war = no", "is_subject = no", "target = ROOT",
        "autonomy_state = autonomy_district_in_Vorkerland", "drop_cosmetic_tag = yes", "factor = 350",
    ):
        if token not in loyalist:
            issues.append(f"loyalist restoration decision is missing {token}")

    pwr_history = read(root, "history/countries/PWR - PostWarZone.txt", issues)
    pwr_appointment = named_block(effects, "ADISCORD_vorkerland_appoint_pwr_technocrat")
    for token in (
        "ruling_party = technocracy",
        "character = PWR_Alexey_Lange",
        "ideology = technocracy_ideology",
        "portrait = GFX_Portrait_Forul_Generic_4",
    ):
        if token not in pwr_appointment:
            issues.append(f"Rimat technocratic appointment is missing {token}")
    if "recruit_character = PWR_Alexey_Lange" not in pwr_history:
        issues.append("PWR history does not recruit Alexey Lange")
    if "ruling_party = pragmatism" not in pwr_history or "ruling_party = technocracy" in pwr_history:
        issues.append("PWR must remain pragmatist before the Vorkerland collapse")
    if "recruit_character" in pwr_appointment or "create_country_leader" in pwr_appointment:
        issues.append("Rimat appointment must promote its history-recruited character")

    wartime_republics = (
        (
            "ROM",
            "history/countries/ROM - RomelLand.txt",
            "ADISCORD_vorkerland_appoint_rom_etatist",
            "ROM_Erwin_Von_Romanovskiy",
            "etatism",
            60,
        ),
        (
            "TRU",
            "history/countries/TRU - TrumanLand.txt",
            "ADISCORD_vorkerland_appoint_tru_chauvinist",
            "TRU_Nikita_Truman",
            "chauvinism",
            61,
        ),
    )
    startup = named_block(on_actions, "on_startup")
    monthly = named_block(on_actions, "on_monthly")
    for tag, history_path, effect_id, character, ideology, event_id in wartime_republics:
        history = read(root, history_path, issues)
        appointment = named_block(effects, effect_id)
        if "ruling_party = pragmatism" not in history:
            issues.append(f"{tag} must retain its pre-collapse pragmatist government")
        for token in (
            f"ruling_party = {ideology}",
            f"character = {character}",
            f"ideology = {ideology}_ideology",
            "promote_character = {",
        ):
            if token not in appointment:
                issues.append(f"{tag} wartime appointment is missing {token}")
        if "recruit_character" in appointment or "create_country_leader" in appointment:
            issues.append(f"{tag} wartime appointment must use its history-recruited character")
        if events.count(f"id = ADISCORD_vorkerland_collapse.{event_id}") != 1:
            issues.append(f"{tag} wartime repair event {event_id} is missing or duplicated")
        if f"ADISCORD_vorkerland_collapse.{event_id} days = 1" not in startup:
            issues.append(f"{tag} wartime government lacks a one-shot startup repair")
        if f"{effect_id} = yes" in monthly:
            issues.append(f"{tag} wartime government still polls on_monthly")

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

    if "ADISCORD_vorkerland_worker_doctor_front_preparation" in ai:
        issues.append("collapse AI still contains the retired Worker-Doctor preparation window")

    central_minors = {"EYR", "EGC", "RIV", "REV", "YOR", "NDN", "SWB", "VHV", "OSV"}
    central_fronts = {
        "wrk": ("WKR", {"VAD", "TVA", *central_minors}, {"WTD"}, 100, "careful", "no"),
        "vad": ("VAD", {"WKR", "TVA", *central_minors}, {"WTD"}, 65, "rush", "yes"),
        "tva": ("TVA", {"WKR", "VAD", *central_minors}, set(), 100, "careful", "no"),
        **{
            tag.lower(): (tag, {"WKR", "VAD", "TVA"}, set(), 100, "rush", "no")
            for tag in central_minors
        },
    }
    for slug, (defender, required_attackers, optional_attackers, request, execution, manual) in central_fronts.items():
        front = named_block(
            ai, f"ADISCORD_vorkerland_front_central_against_{slug}"
        )
        allowed = named_block(front, "allowed")
        actual_attackers = set(re.findall(r"tag\s*=\s*([A-Z]{3})", allowed))
        if not required_attackers <= actual_attackers or not actual_attackers <= required_attackers | optional_attackers:
            issues.append(f"central front against {defender} has the wrong attacker allowlist")
        for token in (
            f"has_war_with = {defender}",
            f"front_unit_request tag = {defender} value = {request}",
            f"front_control tag = {defender}",
            "priority = 1250",
            f"execution_type = {execution}",
            f"manual_attack = {manual}",
        ):
            if token not in front:
                issues.append(f"central front against {defender} is missing {token}")

    regional_pairs = (
        ("ZAO", "WPA"), ("WPA", "ZAO"), ("WPS", "ZAO"), ("ZAO", "WPS"),
        ("ZAO", "PSD"), ("PSD", "ZAO"), ("ZAO", "PWR"), ("PWR", "ZAO"),
        ("WPA", "PSD"), ("PSD", "WPA"), ("WPA", "PWR"), ("PWR", "WPA"),
        ("WPS", "PSD"), ("PSD", "WPS"), ("WPS", "PWR"), ("PWR", "WPS"),
        ("PWR", "PSD"), ("PSD", "PWR"),
        ("VLA", "EBA"), ("EBA", "VLA"), ("ROM", "DVA"), ("DVA", "ROM"),
        ("VLA", "TGD"), ("TGD", "VLA"), ("EBA", "TGD"), ("TGD", "EBA"),
        ("SOL", "SRA"), ("SRA", "SOL"), ("SOL", "CSL"), ("CSL", "SOL"),
        ("SRA", "CSL"), ("CSL", "SRA"),
        ("TRU", "ZTA"), ("ZTA", "TRU"),
    )
    supply_aware_pairs = {
        ("ZAO", "WPA"), ("WPA", "ZAO"), ("WPS", "ZAO"), ("ZAO", "WPS"),
        ("ZAO", "PSD"), ("PSD", "ZAO"), ("ZAO", "PWR"), ("PWR", "ZAO"),
        ("WPA", "PSD"), ("PSD", "WPA"), ("WPA", "PWR"), ("PWR", "WPA"),
        ("WPS", "PSD"), ("PSD", "WPS"), ("WPS", "PWR"), ("PWR", "WPS"),
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
            northern_pair = attacker in {"ZAO", "WPA", "WPS", "PWR", "PSD"} and defender in {
                "ZAO", "WPA", "WPS", "PWR", "PSD"
            }
            request = (33 if attacker in {"WPA", "WPS"} else 25) if northern_pair else 75
            for token in (
                f"front_unit_request tag = {defender} value = {request}",
                "execution_type = careful",
                "manual_attack = no",
            ):
                if token not in front:
                    issues.append(f"{attacker}-{defender} supply-aware front is missing {token}")
            for forbidden in ("execution_type = rush", "manual_attack = yes"):
                if forbidden in front:
                    issues.append(f"{attacker}-{defender} supply-aware front still has {forbidden}")
            if "front_unit_request tag = " in front and " value = 80" in front:
                issues.append(f"{attacker}-{defender} supply-aware front still rushes 80 percent of the army")
        else:
            for token in ("execution_type = rush", "manual_attack = yes"):
                if token not in front:
                    issues.append(f"{attacker}-{defender} anti-freeze front is missing {token}")
    piv = named_block(ai, "ADISCORD_vorkerland_piv_support_macri")
    for token in ("tag = PIV", "is_subject = no", "send_volunteers_desire", "id = EBA", "value = 1000"):
        if token not in piv:
            issues.append(f"PIV volunteer strategy is missing {token}")
    for slug, target in (("wrk", "WKR"), ("vad", "VAD"), ("tva", "TVA")):
        btl = named_block(ai, f"ADISCORD_vorkerland_btl_volunteers_{slug}")
        for token in ("tag = BTL", f"ADISCORD_vorkerland_btl_supports_{slug}", f"id = {target}", "value = 2000"):
            if token not in btl:
                issues.append(f"BTL volunteer strategy for {target} is missing {token}")
    for target in ("PSD", "PWR"):
        front = named_block(ai, f"ADISCORD_vorkerland_ivn_second_front_{target.lower()}")
        for token in (
            "allowed = { tag = IVN }",
            "ADISCORD_vorkerland_ivanland_second_intervention_started",
            f"has_war_with = {target}", f"front_unit_request tag = {target} value = 100",
            f"front_control tag = {target}", f"conquer id = {target}",
        ):
            if token not in front:
                issues.append(f"Ivanland second-intervention front against {target} is missing {token}")
    for name, attacker, defender in (
        ("ADISCORD_vorkerland_rom_intervention_front_zao", "ROM", "ZAO"),
        ("ADISCORD_vorkerland_zao_defend_rom_intervention", "ZAO", "ROM"),
        ("ADISCORD_vorkerland_rom_intervention_front_wps", "ROM", "WPS"),
        ("ADISCORD_vorkerland_wps_defend_rom_intervention", "WPS", "ROM"),
    ):
        front = named_block(ai, name)
        for token in (
            f"allowed = {{ tag = {attacker} }}",
            "ADISCORD_vorkerland_rom_northern_intervention_active",
            f"has_war_with = {defender}", f"front_unit_request tag = {defender}",
            f"front_control tag = {defender}", "manual_attack = no",
        ):
            if token not in front:
                issues.append(f"Frealor intervention AI profile {name} is missing {token}")


def validate_outcomes(root: Path, issues: list[str]) -> None:
    maps = read(root, "common/scripted_effects/ADISCORD_vorkerland_collapse_map_effects.txt", issues)
    triggers = read(root, "common/scripted_triggers/ADISCORD_vorkerland_collapse_triggers.txt", issues)
    on_actions = read(root, "common/on_actions/01_ADISCORD_vorkerland_collapse_on_actions.txt", issues)
    events = read(root, "events/ADISCORD_vorkerland_collapse_events.txt", issues)
    for name, tag in (("worker", "WKR"), ("vlad", "VAD"), ("dorian", "TVA")):
        block = named_block(maps, f"ADISCORD_vorkerland_apply_{name}_map")
        for forbidden in ("transfer_state", "annex_country", "puppet =", "set_autonomy"):
            if forbidden in block:
                issues.append(f"{name} central victory still performs automatic {forbidden}")
        for required in ("ADISCORD_vorkerland_begin_reunification = yes", "ADISCORD_vorkerland_central_unifier", tag):
            if required not in block:
                issues.append(f"{name} central victory is missing {required}")
        for premature in (
            "ADISCORD_vorkerland_central_war_finished",
            "ADISCORD_vorkerland_collapse_finished",
            "ADISCORD_vorkerland_finish_civil_war_exhaustion = yes",
            "victory_superevent = yes",
        ):
            if premature in block:
                issues.append(f"{name} claimant outcome finalizes before verified WRK: {premature}")

    reunification = named_block(triggers, "ADISCORD_vorkerland_is_reunification_target_for_ROOT")
    if "tag = ROM" not in reunification or "tag = TRU" not in reunification or "ROOT = { tag = VAD }" not in reunification:
        issues.append("ROM/TRU must be targets only for the imperial VAD claimant")
    postwar_decisions = read(root, "common/decisions/ADISCORD_vorkerland_focus_decisions.txt", issues)
    recognition = named_block(postwar_decisions, "ADISCORD_vorkerland_recognize_free_republics")
    if not recognition:
        issues.append("WRK cannot recognise the free ROM/TRU republics")
    else:
        for token in (
            "has_country_flag = ADISCORD_vorkerland_focus_worker_free_republics",
            "ROM = { exists = yes is_subject = no NOT = { has_war_with = ROOT } }",
            "TRU = { exists = yes is_subject = no NOT = { has_war_with = ROOT } }",
            "country = ROM",
            "country = TRU",
        ):
            if token not in recognition:
                issues.append(f"postwar recognition lacks independent-republic contract {token}")
    central = named_block(triggers, "ADISCORD_vorkerland_is_central_claimant")
    if "tag = TGD" in central or set(re.findall(r"tag\s*=\s*([A-Z]{3})", central)) != {"WKR", "VAD", "TVA", "EYR", "EGC", "RIV", "REV", "YOR", "NDN", "SWB", "VHV", "OSV"}:
        issues.append("TGD must be outside the central claimant campaign")
    regional = named_block(triggers, "ADISCORD_vorkerland_is_regional_combatant")
    if not all(f"tag = {tag}" in regional for tag in ("VLA", "EBA", "TGD")):
        issues.append("TGD/VLA/EBA peripheral country classification is missing")
    for candidate in ("worker", "vlad", "dorian"):
        victory = named_block(triggers, f"ADISCORD_vorkerland_{candidate}_victory_candidate")
        if "ADISCORD_vorkerland_tgd_defeated" in victory:
            issues.append(f"{candidate} central victory still requires peripheral TGD")
        for tag in ("riv", "rev", "yor", "ndn", "swb", "vhv", "osv"):
            if f"ADISCORD_vorkerland_{tag}_defeated = yes" not in victory:
                issues.append(f"{candidate} central victory does not require {tag.upper()} to be defeated")
    capitulation = named_block(on_actions, "on_capitulation")
    for token in (
        "set_global_flag = skip_default_capitulation",
        "has_global_flag = ADISCORD_vorkerland_ivanland_intervention_active",
        "ROOT = { OR = { tag = ZAO tag = WPA tag = WPS tag = PWR tag = PSD } }",
        "FROM = { OR = { tag = IVN has_war_together_with = IVN } }",
        "controls_state = 90",
        "controls_state = 91",
        "controls_state = 93",
        "controls_state = 94",
        "ROOT = { tag = IVN }",
        "ADISCORD_vorkerland_ivanland_intervention_success = yes",
        "ADISCORD_vorkerland_ivanland_intervention_failure = yes",
        "IVN = { white_peace = ROOT }",
    ):
        if token not in capitulation:
            issues.append(f"Ivanland capitulation guard is missing {token}")
    for hook in ("on_capitulation", "on_startup", "on_state_control_changed", "ADISCORD_vorkerland_check_central_outcome"):
        if hook not in on_actions:
            issues.append(f"central outcome fallback is missing {hook}")
    if "ADISCORD_vorkerland_check_central_outcome = yes" in named_block(on_actions, "on_monthly"):
        issues.append("central outcome still performs an unnecessary monthly fallback poll")
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
    map_effects = read(
        root,
        "common/scripted_effects/ADISCORD_vorkerland_collapse_map_effects.txt",
        issues,
    )
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

    exhaustion_update = "ADISCORD_vorkerland_update_civil_war_exhaustion = yes"
    monthly = named_block(on_actions, "on_monthly")
    if exhaustion_update in monthly:
        issues.append("civil-war exhaustion still uses an on_monthly polling pulse")
    for hook_name in ("on_war", "on_peace"):
        hook = named_block(on_actions, hook_name)
        for token in (
            "ADISCORD_vorkerland_is_main_claimant = yes",
            "NOT = { has_global_flag = ADISCORD_vorkerland_central_war_finished }",
            exhaustion_update,
        ):
            if token not in hook:
                issues.append(f"{hook_name} exhaustion edge routing is missing {token}")
    capitulation = named_block(on_actions, "on_capitulation")
    for token in (
        "ROOT = { ADISCORD_vorkerland_is_main_claimant = yes }",
        "NOT = { has_global_flag = ADISCORD_vorkerland_central_war_finished }",
        "ROOT = { ADISCORD_vorkerland_update_civil_war_exhaustion = yes }",
    ):
        if token not in capitulation:
            issues.append(f"on_capitulation exhaustion edge routing is missing {token}")
    if on_actions.count(exhaustion_update) != 3:
        issues.append("civil-war exhaustion updates must be owned only by war, peace, and capitulation edges")
    if "on_daily" in on_actions:
        issues.append("Vorkerland exhaustion must not add a daily pulse")

    finish = named_block(map_effects, "ADISCORD_vorkerland_finish_civil_war_exhaustion")
    for tag in ("WKR", "WRK", "VAD", "TVA"):
        if f"{tag} = {{ ADISCORD_vorkerland_reset_civil_war_exhaustion = yes }}" not in finish:
            issues.append(f"terminal exhaustion cleanup does not reset {tag}")
    finalizer = named_block(
        read(root, "common/scripted_effects/ADISCORD_vorkerland_phase_effects.txt", issues),
        "ADISCORD_vorkerland_finalize_reunified_wrk",
    )
    if "ADISCORD_vorkerland_finish_civil_war_exhaustion = yes" not in finalizer:
        issues.append("verified WRK finalizer does not finish civil-war exhaustion")
    for outcome in ("worker", "vlad", "dorian"):
        outcome_effect = named_block(map_effects, f"ADISCORD_vorkerland_apply_{outcome}_map")
        if "ADISCORD_vorkerland_finish_civil_war_exhaustion = yes" in outcome_effect:
            issues.append(f"{outcome} claimant outcome ends exhaustion before verified WRK")

    update = named_block(effects, "ADISCORD_vorkerland_update_civil_war_exhaustion")
    compact_update = re.sub(r"\s+", " ", update)
    for token in (
        "ADISCORD_vorkerland_civil_war_casualties_snapshot_k",
        "ADISCORD_vorkerland_civil_war_casualties_delta_k",
        "value = casualties_k",
        "has_war = yes",
        "NOT = { has_global_flag = ADISCORD_vorkerland_central_war_finished }",
        "value = 2",
        "ADISCORD_vorkerland_refresh_civil_war_exhaustion = yes",
    ):
        if token not in update:
            issues.append(f"civil-war exhaustion update is missing {token}")
    for token in ("min = 1 max = 100", "min = 0 max = 10000"):
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
        issues.append("WKR, VAD and TVA exhaustion must remain country-scoped, not global")

    if "value = -8" in update or re.search(r"ADISCORD_vorkerland_civil_war_exhaustion\s+value\s*=\s*-", update):
        issues.append("civil-war exhaustion still decreases before the central outcome")
    initialize = named_block(effects, "ADISCORD_vorkerland_initialize_civil_war_exhaustion")
    if "value = 1" not in initialize or "ADISCORD_vorkerland_refresh_civil_war_exhaustion = yes" not in initialize:
        issues.append("civil-war exhaustion is not initialized visibly at collapse start")

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
    if "icon = GFX_modifiers_sabotaged_resource" not in modifier:
        issues.append("civil-war exhaustion does not use a registered dynamic-modifier icon")
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
        for token in ("tag = WKR", "tag = VAD", "tag = TVA", "ai_will_do = { factor = 0 }"):
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

    map_effects = read(root, "common/scripted_effects/ADISCORD_vorkerland_collapse_map_effects.txt", issues)
    for name in ("dirty_opening", "worker_victory", "vlad_victory", "dorian_victory"):
        show_effect = named_block(map_effects, f"ADISCORD_vorkerland_show_{name}_superevent")
        if "ADISCORD_vorkerland_play_local_superevent_audio = yes" not in show_effect:
            issues.append(f"Vorkerland {name} superevent has no player audio route")

    news = read(root, "events/ADISCORD_news.txt", issues)
    for news_id, title_id, audio_id, sound_effect in (
        (
            "ADISCORD_superevent_news.1",
            "news.0",
            "ADISCORD_superevent_audio.1",
            "superevent_vorkerland_civilwar_sound_e",
        ),
        (
            "ADISCORD_superevent_news.2",
            "news.1",
            "ADISCORD_superevent_audio.2",
            "superevent_stelander_empire_sound_e",
        ),
    ):
        definition = event_block(news, news_id, "news_event")
        if not definition:
            issues.append(f"{news_id}: missing superevent news definition")
            continue
        for token in (
            f"title = {title_id}.t",
            f"desc = {title_id}.d",
            "major = yes",
            "is_triggered_only = yes",
            f"country_event = {{ id = {audio_id} }}",
        ):
            if token not in definition:
                issues.append(f"{news_id}: superevent news route is missing {token}")
        if "hidden = yes" in definition:
            issues.append(f"{news_id}: superevent news must remain visible")

        audio_proxy = event_block(news, audio_id)
        for token in (
            "hidden = yes",
            "is_triggered_only = yes",
            "limit = { is_ai = no }",
            f"scoped_sound_effect = {sound_effect}",
        ):
            if token not in audio_proxy:
                issues.append(f"{audio_id}: player-scoped audio proxy is missing {token}")

    sound_effects = read(root, "sound/superevents_effects.asset", issues)
    sound_defs = read(root, "sound/superevents_sound.asset", issues)
    for effect_name, sound_name, filename in (
        (
            "superevent_vorkerland_civilwar_sound_e",
            "superevent_vorkerland_civilwar_sound",
            "sound/superevents/superevent_vorkerland_civilwar_sound.wav",
        ),
        (
            "superevent_stelander_empire_sound_e",
            "superevent_stelander_empire_sound",
            "sound/superevents/superevent_stelander_empire_sound.wav",
        ),
    ):
        effect = re.search(
            rf"(?ms)^soundeffect\s*=\s*\{{(?:(?!^soundeffect\s*=).)*?"
            rf"\bname\s*=\s*\"?{re.escape(effect_name)}\"?\b"
            rf"(?:(?!^soundeffect\s*=).)*?^\}}",
            sound_effects,
        )
        if not effect or f"sound = {sound_name}" not in effect.group(0):
            issues.append(f"{effect_name}: broken sound-effect binding")
        if f'name = "{sound_name}"' not in sound_defs or not (root / filename).is_file():
            issues.append(f"{effect_name}: missing WAV sound definition or file")


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
