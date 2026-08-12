#!/usr/bin/env python3
"""Validate the WKR-based Vorkerland recovery state-machine contract.

Keep the checks structural: they verify the public effects, triggers, event
IDs, phase ownership, atomic new-save materialization, and bounded edge queue
without snapshotting whole Clausewitz files.
"""

from __future__ import annotations

import re
import sys
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]

TAG_FILE = Path("common/country_tags/01_ADISCORD_vorkerland_collapse_tags.txt")
WKR_COUNTRY = Path("common/countries/WKR.txt")
WKR_HISTORY = Path("history/countries/WKR - Worker Emergency Government.txt")
COLLAPSE_CHARACTERS = Path("common/characters/ADISCORD_vorkerland_collapse_characters.txt")
PHASE_EFFECTS = Path("common/scripted_effects/ADISCORD_vorkerland_phase_effects.txt")
PHASE_TRIGGERS = Path("common/scripted_triggers/ADISCORD_vorkerland_phase_triggers.txt")
PHASE_EVENTS = Path("events/ADISCORD_vorkerland_phase_events.txt")
COLLAPSE_EVENTS = Path("events/ADISCORD_vorkerland_collapse_events.txt")
COLLAPSE_EFFECTS = Path("common/scripted_effects/ADISCORD_vorkerland_collapse_effects.txt")
COLLAPSE_ON_ACTIONS = Path("common/on_actions/01_ADISCORD_vorkerland_collapse_on_actions.txt")
FOCUS_DECISIONS = Path("common/decisions/ADISCORD_vorkerland_focus_decisions.txt")
FOCUS_DECISION_EFFECTS = Path("common/scripted_effects/ADISCORD_vorkerland_focus_decision_effects.txt")
ENGLISH_LOCALISATION = Path("localisation/english/ADISCORD_vorkerland_recovery_l_english.yml")
RUSSIAN_LOCALISATION = Path("localisation/russian/ADISCORD_vorkerland_recovery_l_russian.yml")

WKR_FLAGS = {
    Path("gfx/flags/WKR.tga"): (82, 52),
    Path("gfx/flags/medium/WKR.tga"): (41, 26),
    Path("gfx/flags/small/WKR.tga"): (10, 7),
}

CLAIMANT_HOME_STATES = {
    "WKR": (32, 33, 40, 200, 201),
    "VAD": (75, 106, 107, 121),
    "TVA": (36, 37, 38, 39, 324),
}

WKR_ROUTE_LEADERS = {
    "safe": "WRK_Nikita_Worcker",
    "fallback": "WRK_Anton_Bagley",
}

PHASE_FLAGS = (
    "ADISCORD_vorkerland_phase_prewar",
    "ADISCORD_vorkerland_phase_collapse",
    "ADISCORD_vorkerland_phase_regional_consolidation",
    "ADISCORD_vorkerland_phase_central_preparation",
    "ADISCORD_vorkerland_phase_central_showdown",
    "ADISCORD_vorkerland_phase_reunification",
    "ADISCORD_vorkerland_phase_postwar_integration",
)

PLAYER_PREFERENCE_FLAGS = (
    "ADISCORD_vorkerland_preference_worker",
    "ADISCORD_vorkerland_preference_joint",
    "ADISCORD_vorkerland_preference_utilitarian",
)

PHASE_SETTERS = {
    flag: flag.replace("ADISCORD_vorkerland_phase_", "ADISCORD_vorkerland_set_phase_")
    for flag in PHASE_FLAGS
}

PHASE_TRIGGER_NAMES = (
    "ADISCORD_vorkerland_is_temporary_claimant",
    "ADISCORD_vorkerland_collapse_materialized",
    "ADISCORD_vorkerland_regional_consolidation_complete",
    "ADISCORD_vorkerland_central_showdown_required",
    "ADISCORD_vorkerland_central_minor_campaign_phase_available",
    "ADISCORD_vorkerland_central_districts_owned_and_controlled",
    "ADISCORD_vorkerland_central_districts_inside_claimant_graph",
    "ADISCORD_vorkerland_central_showdown_edges_verified",
    "ADISCORD_vorkerland_has_single_surviving_claimant",
    "ADISCORD_vorkerland_reunification_verified",
)

PHASE_EFFECT_NAMES = (
    "ADISCORD_vorkerland_begin_collapse",
    "ADISCORD_vorkerland_verify_collapse_materialized",
    "ADISCORD_vorkerland_verify_regional_consolidation",
    "ADISCORD_vorkerland_begin_central_preparation",
    "ADISCORD_vorkerland_initialize_showdown_edge_queue",
    "ADISCORD_vorkerland_detach_showdown_claimants",
    "ADISCORD_vorkerland_attempt_showdown_edge_wkr_vad",
    "ADISCORD_vorkerland_attempt_showdown_edge_wkr_tva",
    "ADISCORD_vorkerland_attempt_showdown_edge_vad_tva",
    "ADISCORD_vorkerland_attempt_all_showdown_edges",
    "ADISCORD_vorkerland_advance_showdown_launch",
    "ADISCORD_vorkerland_verify_showdown_edge_wkr_vad",
    "ADISCORD_vorkerland_verify_showdown_edge_wkr_tva",
    "ADISCORD_vorkerland_verify_showdown_edge_vad_tva",
    "ADISCORD_vorkerland_verify_central_showdown",
    "ADISCORD_vorkerland_begin_reunification",
    "ADISCORD_vorkerland_verify_reunified_wrk",
)

# Reunification starts only after the war graph has a single surviving claimant;
# those two effects may legitimately refer to the newly formed WRK country.
ACTIVE_WAR_EFFECTS = PHASE_EFFECT_NAMES[:-1]
ACTIVE_WAR_TRIGGERS = tuple(
    name
    for name in PHASE_TRIGGER_NAMES[:-1]
    if name
    not in {
        "ADISCORD_vorkerland_central_minor_campaign_phase_available",
        "ADISCORD_vorkerland_central_districts_owned_and_controlled",
    }
)

SHOWDOWN_PAIRS = (
    ("wkr_vad", "WKR", "VAD", "WKR-VAD"),
    ("wkr_tva", "WKR", "TVA", "WKR-TVA"),
    ("vad_tva", "VAD", "TVA", "VAD-TVA"),
)

RETIRED_LEGACY_EVENT_IDS = (48, 49, 71, 72, 73, 79, 81)


def read(relative: Path) -> str:
    path = ROOT / relative
    if not path.is_file():
        return ""
    return path.read_text(encoding="utf-8-sig")


def strip_comments(text: str) -> str:
    return "\n".join(line.split("#", 1)[0] for line in text.splitlines())


def balanced(text: str) -> bool:
    depth = 0
    for character in strip_comments(text):
        if character == "{":
            depth += 1
        elif character == "}":
            depth -= 1
            if depth < 0:
                return False
    return depth == 0


def _braced_block(text: str, match_start: int, brace_start: int) -> str:
    depth = 0
    for index in range(brace_start, len(text)):
        if text[index] == "{":
            depth += 1
        elif text[index] == "}":
            depth -= 1
            if depth == 0:
                return text[match_start : index + 1]
    return ""


def named_blocks(text: str, name: str) -> list[str]:
    blocks: list[str] = []
    pattern = re.compile(rf"(?m)^\s*{re.escape(name)}\s*=\s*\{{")
    for match in pattern.finditer(text):
        brace_start = text.find("{", match.start())
        block = _braced_block(text, match.start(), brace_start)
        if block:
            blocks.append(block)
    return blocks


def named_block(text: str, name: str) -> str:
    blocks = named_blocks(text, name)
    return blocks[0] if blocks else ""


def event_blocks(text: str) -> list[tuple[str, str]]:
    blocks: list[tuple[str, str]] = []
    for match in re.finditer(r"(?m)^\s*country_event\s*=\s*\{", text):
        brace_start = text.find("{", match.start())
        block = _braced_block(text, match.start(), brace_start)
        event_id = re.search(r"(?m)^\s*id\s*=\s*([A-Za-z0-9_]+\.\d+)\s*$", block)
        if block and event_id:
            blocks.append((event_id.group(1), block))
    return blocks


def event_block(text: str, event_id: str) -> str:
    for candidate, block in event_blocks(text):
        if candidate == event_id:
            return block
    return ""


def _load(relative: Path, issues: list[str]) -> str:
    path = ROOT / relative
    if not path.is_file():
        issues.append(f"missing required file {relative.as_posix()}")
        return ""
    try:
        source = path.read_text(encoding="utf-8-sig")
    except UnicodeError as exc:
        issues.append(f"cannot decode {relative.as_posix()} as UTF-8: {exc}")
        return ""
    if not balanced(source):
        issues.append(f"unbalanced Clausewitz braces in {relative.as_posix()}")
    return strip_comments(source)


def _tga_dimensions(path: Path) -> tuple[int, int] | None:
    try:
        header = path.read_bytes()[:18]
    except OSError:
        return None
    if len(header) < 18:
        return None
    return (
        int.from_bytes(header[12:14], byteorder="little"),
        int.from_bytes(header[14:16], byteorder="little"),
    )


def _contains_wrk_scope(block: str) -> bool:
    return bool(
        re.search(r"\btag\s*=\s*WRK\b", block)
        or re.search(r"(?m)^\s*WRK\s*=\s*\{", block)
    )


def _set_flag(flag: str) -> str:
    return f"set_global_flag = {flag}"


def _clear_flag(flag: str) -> str:
    return f"clr_global_flag = {flag}"


def validate_wkr_semantics() -> list[str]:
    issues: list[str] = []
    tag_source = _load(TAG_FILE, issues)
    country_source = _load(WKR_COUNTRY, issues)
    history_source = _load(WKR_HISTORY, issues)
    character_source = _load(COLLAPSE_CHARACTERS, issues)

    expected_tag = re.compile(r'(?m)^\s*WKR\s*=\s*"countries/WKR\.txt"\s*$')
    if len(expected_tag.findall(tag_source)) != 1:
        issues.append("WKR must be declared exactly once in the existing Vorkerland tag file")

    tag_definitions: list[str] = []
    tag_root = ROOT / "common/country_tags"
    if tag_root.is_dir():
        for path in sorted(tag_root.glob("*.txt")):
            source = strip_comments(path.read_text(encoding="utf-8-sig"))
            if re.search(r"(?m)^\s*WKR\s*=", source):
                tag_definitions.append(path.relative_to(ROOT).as_posix())
    if tag_definitions != [TAG_FILE.as_posix()]:
        issues.append(f"WKR tag ownership must be unique, found {tag_definitions}")

    if country_source:
        for field in ("graphical_culture", "graphical_culture_2d", "color"):
            if not re.search(rf"(?m)^\s*{field}\s*=", country_source):
                issues.append(f"WKR country definition is missing {field}")

    if history_source:
        if not re.search(r"(?m)^\s*capital\s*=\s*32\s*$", history_source):
            issues.append("WKR runtime history must declare state 32 as its fallback capital")
        if not re.search(r"(?m)^\s*ruling_party\s*=\s*pragmatism\s*$", history_source):
            issues.append("WKR runtime history must use the worker emergency pragmatism fallback")
        if re.search(r"WKR_Worker_Emergency_Presidium|GFX_portrait_WRK_Temporary_Government", history_source):
            issues.append("WKR runtime history must not invent a temporary-government fallback leader")
        if re.search(r"Lucas[_ ]Brown", history_source, flags=re.IGNORECASE):
            issues.append("WKR runtime history must not use Lucas Brown as a fallback leader")

    fallback = WKR_ROUTE_LEADERS["fallback"]
    fallback_blocks = named_blocks(character_source, fallback)
    if len(fallback_blocks) != 1:
        issues.append(f"collapse characters must define exactly one fixed fallback {fallback}")
    # Anton is an authored character promoted by the collapse effect; keeping
    # his base definition role-free avoids duplicate country-leader roles.
    elif len(named_blocks(fallback_blocks[0], "country_leader")) > 1:
        issues.append(f"{fallback} must not define duplicate country_leader roles")

    for relative, expected_dimensions in WKR_FLAGS.items():
        path = ROOT / relative
        if not path.is_file():
            issues.append(f"missing WKR flag {relative.as_posix()}")
            continue
        actual_dimensions = _tga_dimensions(path)
        if actual_dimensions != expected_dimensions:
            issues.append(
                f"{relative.as_posix()} must be {expected_dimensions[0]}x{expected_dimensions[1]}, "
                f"found {actual_dimensions}"
            )

    for relative, header in (
        (ENGLISH_LOCALISATION, "l_english:"),
        (RUSSIAN_LOCALISATION, "l_russian:"),
    ):
        source = _load(relative, issues)
        if source:
            if not source.lstrip().startswith(header):
                issues.append(f"{relative.as_posix()} must use localisation header {header}")
            for key in ("WKR", "WKR_DEF", "WKR_ADJ"):
                if not re.search(rf"(?m)^\s*{key}:", source):
                    issues.append(f"{relative.as_posix()} is missing country-name key {key}")

    claimant_choice_localisation = (
        (
            ENGLISH_LOCALISATION,
            ("country controlled by the player", "Worker's fate", "Vlad and Armi"),
            "joint government",
        ),
        (
            RUSSIAN_LOCALISATION,
            ("только страну под управлением игрока", "судьба Уоркера", "Влада и Арми"),
            "совместн",
        ),
    )
    for relative, required_fragments, forbidden_option_fragment in claimant_choice_localisation:
        source = read(relative)
        for fragment in required_fragments:
            if fragment not in source:
                issues.append(
                    f"{relative.as_posix()} claimant-choice text must explain or name {fragment}"
                )
        option = re.search(
            r'(?m)^\s*ADISCORD_vorkerland_phase\.1\.b:\s*"([^"]*)"',
            source,
        )
        if not option:
            issues.append(f"{relative.as_posix()} is missing phase.1.b claimant-choice text")
        elif forbidden_option_fragment in option.group(1).lower():
            issues.append(
                f"{relative.as_posix()} phase.1.b must name Vlad and Armi, not promise a joint government"
            )
    russian_path = ROOT / RUSSIAN_LOCALISATION
    if russian_path.is_file() and not russian_path.read_bytes().startswith(b"\xef\xbb\xbf"):
        issues.append(f"{RUSSIAN_LOCALISATION.as_posix()} must retain a UTF-8 BOM")

    return issues


def _gameplay_phase_token_sources() -> list[tuple[Path, str]]:
    sources: list[tuple[Path, str]] = []
    for root_name in ("common", "events", "history"):
        directory = ROOT / root_name
        if not directory.is_dir():
            continue
        for path in directory.rglob("*.txt"):
            source = path.read_text(encoding="utf-8-sig")
            if "ADISCORD_vorkerland_phase_" in source:
                sources.append((path.relative_to(ROOT), strip_comments(source)))
    return sources


def _global_set_owners(flag: str) -> list[str]:
    owners: list[str] = []
    token = _set_flag(flag)
    for root_name in ("common", "events", "history"):
        directory = ROOT / root_name
        if not directory.is_dir():
            continue
        for path in directory.rglob("*.txt"):
            source = strip_comments(path.read_text(encoding="utf-8-sig"))
            if token in source:
                owners.append(path.relative_to(ROOT).as_posix())
    return sorted(owners)


def validate_new_save_materialization() -> list[str]:
    """Validate the one-shot WRK partition and its bounded postcondition check."""

    issues: list[str] = []
    effects = _load(PHASE_EFFECTS, issues)
    triggers = _load(PHASE_TRIGGERS, issues)
    phase_events = _load(PHASE_EVENTS, issues)
    collapse_events = _load(COLLAPSE_EVENTS, issues)
    collapse_effects = _load(COLLAPSE_EFFECTS, issues)
    on_actions = _load(COLLAPSE_ON_ACTIONS, issues)
    if any(
        not (ROOT / path).is_file()
        for path in (
            PHASE_EFFECTS,
            PHASE_TRIGGERS,
            PHASE_EVENTS,
            COLLAPSE_EVENTS,
            COLLAPSE_EFFECTS,
            COLLAPSE_ON_ACTIONS,
        )
    ):
        return issues

    choice = event_block(phase_events, "ADISCORD_vorkerland_phase.1")
    if not choice:
        issues.append("phase event .1 must expose the pre-collapse player claimant choice")
    else:
        choice_trigger = named_block(choice, "trigger")
        if len(re.findall(r"\btag\s*=\s*WRK\b", choice_trigger)) != 1:
            issues.append("phase event .1 must be scoped exactly to pre-collapse WRK")
        if choice_trigger.count("ADISCORD_vorkerland_collapse_not_started = yes") != 1:
            issues.append("phase event .1 must expire when the collapse has already started")
        if choice.count("fire_only_once = yes") != 1:
            issues.append("phase event .1 must be a one-shot claimant choice")
        if "hidden = yes" in choice:
            issues.append("phase event .1 must remain player-facing")
        if "change_tag_from" in choice:
            issues.append("phase event .1 must select a preference, not change country before the split")

        options = named_blocks(choice, "option")
        expected_options = (
            ("ADISCORD_vorkerland_phase.1.a", PLAYER_PREFERENCE_FLAGS[0]),
            ("ADISCORD_vorkerland_phase.1.b", PLAYER_PREFERENCE_FLAGS[1]),
            ("ADISCORD_vorkerland_phase.1.c", PLAYER_PREFERENCE_FLAGS[2]),
        )
        if len(options) != len(expected_options):
            issues.append("phase event .1 must expose exactly three claimant options")
        else:
            collapse_dispatch = "country_event = { id = ADISCORD_vorkerland_collapse.1 }"
            for option, (name, selected_flag) in zip(options, expected_options):
                if option.count(f"name = {name}") != 1:
                    issues.append(f"phase event .1 option must use localisation key {name}")
                for preference_flag in PLAYER_PREFERENCE_FLAGS:
                    if option.count(f"clr_global_flag = {preference_flag}") != 1:
                        issues.append(
                            f"{name} must clear {preference_flag} before selecting the player claimant"
                        )
                selected = re.findall(
                    r"\bset_global_flag\s*=\s*(ADISCORD_vorkerland_preference_[A-Za-z_]+)\b",
                    option,
                )
                if selected != [selected_flag]:
                    issues.append(f"{name} must set only {selected_flag}, found {selected}")
                if option.count(collapse_dispatch) != 1:
                    issues.append(f"{name} must invoke hidden collapse.1 immediately and exactly once")
        if choice.count("country_event = { id = ADISCORD_vorkerland_collapse.1 }") != 3:
            issues.append("all three phase event .1 options must invoke collapse.1 exactly once")
        if any(
            fate_token in choice
            for fate_token in (
                "ADISCORD_vorkerland_worker_safe_with_loyalists",
                "ADISCORD_vorkerland_worker_rescued_by_vlad",
                "ADISCORD_vorkerland_worker_missing",
                "ADISCORD_vorkerland_worker_killed",
                "ADISCORD_vorkerland_form_joint_government",
            )
        ):
            issues.append("the player claimant choice must not influence Worker's random fate")

    startup = named_block(on_actions, "on_startup")
    startup_choice_dispatches = [
        block
        for block in named_blocks(startup, "country_event")
        if re.search(r"\bid\s*=\s*ADISCORD_vorkerland_phase\.1\b", block)
    ]
    if len(startup_choice_dispatches) != 1:
        issues.append("startup must produce exactly one delayed phase.1 claimant choice")
    else:
        startup_choice = startup_choice_dispatches[0]
        for token in ("days = 120", "random_days = 60"):
            if startup_choice.count(token) != 1:
                issues.append(f"startup phase.1 claimant choice must retain {token}")
        wrk_producers = [
            block
            for block in named_blocks(startup, "WRK")
            if "id = ADISCORD_vorkerland_phase.1" in block
        ]
        if len(wrk_producers) != 1:
            issues.append("startup must schedule phase.1 from the live WRK country scope")
    if re.search(r"\bid\s*=\s*ADISCORD_vorkerland_collapse\.1\b", startup):
        issues.append("startup must wait for phase.1 instead of scheduling hidden collapse.1 directly")

    begin_collapse = named_block(effects, "ADISCORD_vorkerland_begin_collapse")
    if "change_tag_from" in begin_collapse:
        issues.append("begin_collapse must not change tags; event .1 owns the human-only handoff")
    if "annex_country" in begin_collapse:
        issues.append("begin_collapse must not consume WRK before event .1 finishes the claimant map")
    if begin_collapse.count("ADISCORD_vorkerland_set_phase_collapse = yes") != 1:
        issues.append("begin_collapse must enter collapse through the centralized phase setter")
    if begin_collapse.count("ADISCORD_vorkerland_reset_temporary_claimant_cores = yes") != 1:
        issues.append("begin_collapse must reset temporary claimant cores exactly once")

    collapse = event_block(collapse_events, "ADISCORD_vorkerland_collapse.1")
    if not collapse:
        issues.append("collapse event .1 must own the new-save WRK partition")
        return issues
    trigger = named_block(collapse, "trigger")
    immediate = named_block(collapse, "immediate")
    if len(re.findall(r"\btag\s*=\s*WRK\b", trigger)) != 1:
        issues.append("collapse event .1 must be entered exactly once from prewar WRK")

    tag_changes = list(re.finditer(r"\bchange_tag_from\s*=\s*WRK\b", immediate))
    handoffs = [
        block
        for block in named_blocks(immediate, "if")
        if "change_tag_from" in block
        and re.findall(r"\bis_ai\s*=\s*(yes|no)\b", named_block(block, "limit")) == ["no"]
    ]
    if len(tag_changes) != 3 or len(handoffs) != 1:
        issues.append("collapse event .1 must contain one human-only three-claimant handoff")
        handoff = ""
    else:
        handoff = handoffs[0]
        handoff_limit = named_block(handoff, "limit")
        ai_values = re.findall(r"\bis_ai\s*=\s*(yes|no)\b", handoff_limit)
        if ai_values != ["no"]:
            issues.append("collapse event .1 handoff must be guarded only for a human WRK player")
        for claimant in ("WKR", "VAD", "TVA"):
            handoff_scopes = [
                block
                for block in named_blocks(handoff, claimant)
                if re.search(r"\bchange_tag_from\s*=\s*WRK\b", block)
            ]
            if len(handoff_scopes) != 1:
                issues.append(f"collapse event .1 human branch must hand one route to {claimant}")

        worker_branches = [
            block
            for block in named_blocks(handoff, "if")
            if "ADISCORD_vorkerland_preference_worker" in named_block(block, "limit")
            and "WKR = { change_tag_from = WRK }" in block
        ]
        if len(worker_branches) != 1:
            issues.append("human handoff must route the Worker preference and no-preference fallback to WKR")
        else:
            worker_limit = named_block(worker_branches[0], "limit")
            for preference_flag in PLAYER_PREFERENCE_FLAGS:
                if f"NOT = {{ has_global_flag = {preference_flag} }}" not in worker_limit:
                    issues.append("WKR handoff must explicitly accept the all-preferences-absent old-save fallback")
                    break

        expected_preference_handoffs = (
            ("ADISCORD_vorkerland_preference_joint", "VAD"),
            ("ADISCORD_vorkerland_preference_utilitarian", "TVA"),
        )
        for preference_flag, claimant in expected_preference_handoffs:
            branches = [
                block
                for block in named_blocks(handoff, "else_if")
                if f"has_global_flag = {preference_flag}" in named_block(block, "limit")
                and f"{claimant} = {{ change_tag_from = WRK }}" in block
            ]
            if len(branches) != 1:
                issues.append(f"human handoff must route {preference_flag} exactly to {claimant}")
                continue
            branch_limit = named_block(branches[0], "limit")
            other_flags = tuple(
                flag for flag in PLAYER_PREFERENCE_FLAGS if flag != preference_flag
            )
            for other_flag in other_flags:
                if f"NOT = {{ has_global_flag = {other_flag} }}" not in branch_limit:
                    issues.append(
                        f"{claimant} handoff must exclude other preference {other_flag}"
                    )

        handoff_start = immediate.find(handoff)
        handoff_end = handoff_start + len(handoff)
        annex_after_handoff = immediate.find("annex_country = {", handoff_end)
        for preference_flag in PLAYER_PREFERENCE_FLAGS:
            clear_token = f"clr_global_flag = {preference_flag}"
            clear_positions = [match.start() for match in re.finditer(re.escape(clear_token), immediate)]
            if len(clear_positions) != 1:
                issues.append(f"collapse event .1 must clear consumed preference {preference_flag} exactly once")
            elif clear_positions[0] <= handoff_end:
                issues.append(f"collapse event .1 must clear {preference_flag} after the human handoff")
            elif annex_after_handoff < 0 or clear_positions[0] >= annex_after_handoff:
                issues.append(f"collapse event .1 must clear {preference_flag} before WRK is annexed")
        if any(f"set_global_flag = {flag}" in immediate for flag in PLAYER_PREFERENCE_FLAGS):
            issues.append("collapse event .1 must consume preferences without creating new ones")

    fate_lists = [
        block
        for block in named_blocks(immediate, "random_list")
        if "ADISCORD_vorkerland_worker_safe_with_loyalists" in block
    ]
    if len(fate_lists) != 1:
        issues.append("collapse event .1 must retain exactly one independent Worker-fate roll")
    elif any(preference_flag in fate_lists[0] for preference_flag in PLAYER_PREFERENCE_FLAGS):
        issues.append("Worker's random fate must not read the player's claimant preference")

    materialization_scopes = [
        block
        for block in named_blocks(immediate, "WKR")
        if re.search(r"\bannex_country\s*=\s*\{", block)
    ]
    if len(materialization_scopes) != 1:
        issues.append("collapse event .1 must have one WKR materialization scope that consumes WRK")
        materialization = ""
    else:
        materialization = materialization_scopes[0]
        annex_blocks = named_blocks(materialization, "annex_country")
        if len(annex_blocks) != 1:
            issues.append("WKR materialization must annex WRK exactly once")
        else:
            annex = annex_blocks[0]
            if not re.search(r"\btarget\s*=\s*WRK\b", annex):
                issues.append("WKR materialization annex must target the dormant WRK country")
            if not re.search(r"\btransfer_troops\s*=\s*yes\b", annex):
                issues.append("WKR materialization must inherit WRK troops during annexation")
        if materialization.count("ADISCORD_vorkerland_relocate_legacy_armies = yes") != 1:
            issues.append("WKR materialization must relocate inherited armies exactly once")
        elif materialization.find("ADISCORD_vorkerland_relocate_legacy_armies = yes") < materialization.find(
            "annex_country"
        ):
            issues.append("WKR army relocation must occur after WRK annexation")
        focus_tree = named_block(materialization, "load_focus_tree")
        for token, diagnostic in (
            (
                "tree = ADISCORD_vorkerland_civil_war_focus",
                "WKR materialization must select the lifecycle focus tree",
            ),
            (
                "keep_completed = yes",
                "WKR materialization must preserve completed prewar focuses",
            ),
            (
                "copy_completed_from = WRK",
                "WKR materialization must copy prewar WRK focus progress before annexation",
            ),
        ):
            if token not in focus_tree:
                issues.append(diagnostic)

    begin_position = immediate.find("ADISCORD_vorkerland_begin_collapse = yes")
    fate_position = immediate.find("random_list = {")
    split_position = immediate.find("ADISCORD_vorkerland_apply_initial_map = yes")
    characters_position = immediate.find("ADISCORD_vorkerland_prepare_claimant_characters = yes")
    handoff_positions = [match.start() for match in tag_changes]
    annex_position = immediate.find("annex_country = {")
    relocation_position = immediate.find("ADISCORD_vorkerland_relocate_legacy_armies = yes")
    verification_position = immediate.find(
        "country_event = { id = ADISCORD_vorkerland_phase.2 days = 1 }"
    )
    ordered_offsets = (
        begin_position,
        fate_position,
        split_position,
        characters_position,
        *(handoff_positions if len(handoff_positions) == 3 else (-1,)),
        annex_position,
        relocation_position,
        verification_position,
    )
    if any(offset < 0 for offset in ordered_offsets):
        issues.append("collapse event .1 is missing a required split/handoff/verification step")
    elif list(ordered_offsets) != sorted(ordered_offsets):
        issues.append(
            "collapse event .1 must order phase setup, fate, split, human handoff, annex, relocation, then verification"
        )
    if immediate.count("country_event = { id = ADISCORD_vorkerland_phase.2 days = 1 }") != 1:
        issues.append("collapse event .1 must schedule exactly one next-day materialization verification")

    initial_map = named_block(collapse_effects, "ADISCORD_vorkerland_apply_initial_map")
    initial_wkr = named_block(initial_map, "WKR")
    initial_wkr_states = Counter(
        int(state_id)
        for state_id in re.findall(r"\btransfer_state\s*=\s*(\d+)\b", initial_wkr)
    )
    if initial_wkr_states != Counter(CLAIMANT_HOME_STATES["WKR"]):
        issues.append("initial collapse map must transfer all five strict WKR home states exactly once")
    if initial_map.count("40 = { set_state_controller_to = WKR }") != 1:
        issues.append("initial collapse map must explicitly hand impassable state 40 control to WKR")

    materialized = named_block(triggers, "ADISCORD_vorkerland_collapse_materialized")
    exists_counts = Counter(re.findall(r"\bcountry_exists\s*=\s*([A-Z]{3})\b", materialized))
    expected_exists = Counter({"WKR": 1, "WRK": 1, "VAD": 1, "TVA": 1})
    if exists_counts != expected_exists:
        issues.append(
            "collapse_materialized must test exactly WKR/VAD/TVA existence and dormant WRK absence"
        )
    if not re.search(r"NOT\s*=\s*\{\s*country_exists\s*=\s*WRK\s*\}", materialized):
        issues.append("collapse_materialized must require the old WRK country to be absent")

    for tag, expected_states in CLAIMANT_HOME_STATES.items():
        claimant_scopes = [
            block
            for block in named_blocks(materialized, tag)
            if "is_subject = no" in block
            and "NOT = { has_capitulated = yes }" in block
            and "controls_state" in block
        ]
        if len(claimant_scopes) != 1:
            issues.append(f"collapse_materialized must define one active/home postcondition for {tag}")
            continue
        claimant = claimant_scopes[0]
        controlled_states = tuple(
            int(state_id)
            for state_id in re.findall(r"\bcontrols_state\s*=\s*(\d+)\b", claimant)
        )
        if Counter(controlled_states) != Counter(expected_states):
            issues.append(
                f"{tag} materialization homes must be exactly {list(expected_states)}, found {list(controlled_states)}"
            )
        if re.search(r"\bnum_divisions\b", claimant):
            issues.append(f"{tag} materialization must not depend on a mutable division count")
        if "is_subject = no" not in claimant or "NOT = { has_capitulated = yes }" not in claimant:
            issues.append(f"{tag} materialization must require an independent, active claimant")

    actual_ownership: dict[int, tuple[str, str]] = {}
    for match in re.finditer(r"(?m)^\s*(\d+)\s*=\s*\{", materialized):
        state_id = int(match.group(1))
        brace_start = materialized.find("{", match.start())
        state_block = _braced_block(materialized, match.start(), brace_start)
        owner = re.search(r"\bis_owned_by\s*=\s*([A-Z]{3})\b", state_block)
        controller = re.search(r"\bis_controlled_by\s*=\s*([A-Z]{3})\b", state_block)
        if owner or controller:
            actual_ownership[state_id] = (
                owner.group(1) if owner else "",
                controller.group(1) if controller else "",
            )
    expected_ownership = {
        state_id: (tag, tag)
        for tag, state_ids in CLAIMANT_HOME_STATES.items()
        for state_id in state_ids
    }
    if actual_ownership != expected_ownership:
        issues.append("collapse_materialized must require exact claimant ownership/control of every home state")

    leader_blocks = named_blocks(materialized, "has_country_leader")
    route_characters = Counter(
        match.group(1)
        for block in leader_blocks
        if (match := re.search(r"\bcharacter\s*=\s*([A-Za-z0-9_]+)\b", block))
    )
    if route_characters != Counter(WKR_ROUTE_LEADERS.values()):
        issues.append(
            "collapse_materialized route leaders must be exactly Nikita Worker or Anton Bagley"
        )
    for block in leader_blocks:
        if len(re.findall(r"\bruling_only\s*=\s*yes\b", block)) != 1:
            issues.append("each WKR materialization route leader check must be ruling-only")
    route_blocks = [
        block
        for block in named_blocks(materialized, "AND")
        if "has_country_leader" in block
    ]
    safe_blocks = [block for block in route_blocks if WKR_ROUTE_LEADERS["safe"] in block]
    fallback_blocks = [block for block in route_blocks if WKR_ROUTE_LEADERS["fallback"] in block]
    safe_flag = "ADISCORD_vorkerland_worker_safe_with_loyalists"
    if len(safe_blocks) != 1 or not re.search(
        rf"(?m)^\s*has_global_flag\s*=\s*{safe_flag}\s*$", safe_blocks[0] if safe_blocks else ""
    ):
        issues.append("Nikita Worker must rule WKR only on the safe-with-loyalists route")
    if len(fallback_blocks) != 1 or not re.search(
        rf"NOT\s*=\s*\{{\s*has_global_flag\s*=\s*{safe_flag}\s*\}}",
        fallback_blocks[0] if fallback_blocks else "",
    ):
        issues.append("Anton Bagley must rule every non-safe WKR route")
    if re.search(r"Lucas[_ ]Brown", materialized, flags=re.IGNORECASE):
        issues.append("collapse_materialized must not use Lucas Brown as a route fallback")

    verify = named_block(effects, "ADISCORD_vorkerland_verify_collapse_materialized")
    postcondition = "ADISCORD_vorkerland_collapse_materialized = yes"
    success_flag = "set_global_flag = ADISCORD_vorkerland_collapse_materialized_verified"
    success_blocks = [
        block
        for block in named_blocks(verify, "if")
        if postcondition in block and success_flag in block
    ]
    if len(success_blocks) != 1:
        issues.append("collapse verifier must have one success branch owned by the strict postcondition")
    else:
        success = success_blocks[0]
        if success.find(success_flag) < success.find(postcondition):
            issues.append("collapse verifier must set materialized_verified only after all postconditions")
        focus_tree_load = (
            "load_focus_tree = { tree = ADISCORD_vorkerland_civil_war_focus "
            "keep_completed = yes }"
        )
        if success.count(focus_tree_load) != 3:
            issues.append("verified materialization must load the lifecycle tree for WKR, VAD, and TVA")
        if success.count("ADISCORD_vorkerland_set_phase_regional_consolidation = yes") != 1:
            issues.append("verified materialization must advance to regional consolidation exactly once")
    if verify.count(success_flag) != 1:
        issues.append("materialized_verified must be set exactly once in the verified success branch")

    retry_flag = "ADISCORD_vorkerland_collapse_materialization_retry"
    retry_blocks = named_blocks(verify, "else_if")
    if len(retry_blocks) != 1:
        issues.append("collapse verifier must expose exactly one bounded repair branch")
    else:
        retry = retry_blocks[0]
        retry_limit = named_block(retry, "limit")
        if not re.search(
            rf"NOT\s*=\s*\{{\s*has_global_flag\s*=\s*{retry_flag}\s*\}}",
            retry_limit,
        ):
            issues.append("collapse repair must be guarded by an unset one-retry flag")
        if retry.count(f"set_global_flag = {retry_flag}") != 1:
            issues.append("collapse repair must consume its single retry before mutating countries")
        state_forty_repairs = [
            block
            for block in named_blocks(retry, "if")
            if "country_exists = WKR" in named_block(block, "limit")
            and "transfer_state = 40" in block
            and "40 = { set_state_controller_to = WKR }" in block
        ]
        if len(state_forty_repairs) != 1:
            issues.append("collapse retry must explicitly restore ownership and control of state 40 to WKR")
        repair_blocks = [
            block
            for block in named_blocks(retry, "if")
            if "country_exists = WRK" in block and "country_exists = WKR" in block
        ]
        if len(repair_blocks) != 1:
            issues.append("collapse retry must repair only a surviving WKR/WRK pair")
        else:
            repair = repair_blocks[0]
            repair_wkr = [
                block
                for block in named_blocks(repair, "WKR")
                if "annex_country" in block
            ]
            if len(repair_wkr) != 1:
                issues.append("collapse retry must let WKR consume a stale WRK remnant")
            else:
                repair_scope = repair_wkr[0]
                repair_annex = named_block(repair_scope, "annex_country")
                if not re.search(r"\btarget\s*=\s*WRK\b", repair_annex) or not re.search(
                    r"\btransfer_troops\s*=\s*yes\b", repair_annex
                ):
                    issues.append("collapse retry annex must target WRK with troop transfer")
                if repair_scope.count("ADISCORD_vorkerland_relocate_legacy_armies = yes") != 1:
                    issues.append("collapse retry must relocate inherited WRK armies exactly once")
                elif repair_scope.find("ADISCORD_vorkerland_relocate_legacy_armies = yes") < repair_scope.find(
                    "annex_country"
                ):
                    issues.append("collapse retry army relocation must follow repair annexation")
        retry_event = "country_event = { id = ADISCORD_vorkerland_phase.2 days = 1 }"
        if retry.count(retry_event) != 1:
            issues.append("collapse retry must schedule exactly one next-day postcondition check")
    if verify.count(f"set_global_flag = {retry_flag}") != 1:
        issues.append("collapse verifier must permit only one materialization retry")
    terminal_blocks = named_blocks(verify, "else")
    if len(terminal_blocks) != 1 or (
        "set_global_flag = ADISCORD_vorkerland_collapse_materialization_failed"
        not in (terminal_blocks[0] if terminal_blocks else "")
    ):
        issues.append("collapse verifier must terminate with a diagnostic failure after the one retry")

    verify_launch = named_block(effects, "ADISCORD_vorkerland_verify_regional_war_launch")
    graph_success = [
        block
        for block in named_blocks(verify_launch, "if")
        if "ADISCORD_vorkerland_regional_war_graph_active_or_terminal = yes" in block
        and "ADISCORD_vorkerland_rom_dva_edge_initialized_or_terminal = yes" in block
        and "set_global_flag = ADISCORD_vorkerland_northern_wars_began" in block
    ]
    if len(graph_success) != 1:
        issues.append("regional launch verifier must expose one verified war-graph success branch")
    else:
        graph_branch = graph_success[0]
        graph_limit = named_block(graph_branch, "limit")
        for token in (
            "ADISCORD_vorkerland_regional_war_graph_active_or_terminal = yes",
            "ADISCORD_vorkerland_rom_dva_edge_initialized_or_terminal = yes",
        ):
            if token not in graph_limit:
                issues.append("central preparation must remain inside both regional graph postconditions")
        if graph_branch.count("ADISCORD_vorkerland_begin_central_preparation = yes") != 1:
            issues.append("verified regional war-graph launch must begin central preparation exactly once")
        if "ADISCORD_vorkerland_regional_consolidation_complete = yes" in graph_branch:
            issues.append("central preparation must not wait for every peripheral war to finish")

    return issues


def validate_phase_controller() -> list[str]:
    issues: list[str] = []
    effects = _load(PHASE_EFFECTS, issues)
    triggers = _load(PHASE_TRIGGERS, issues)
    events = _load(PHASE_EVENTS, issues)
    if any(not (ROOT / path).is_file() for path in (PHASE_EFFECTS, PHASE_TRIGGERS, PHASE_EVENTS)):
        return issues

    clear = named_block(effects, "ADISCORD_vorkerland_clear_phase_flags")
    if len(named_blocks(effects, "ADISCORD_vorkerland_clear_phase_flags")) != 1:
        issues.append("phase controller must define exactly one clear_phase_flags effect")
    for flag in PHASE_FLAGS:
        if clear.count(_clear_flag(flag)) != 1:
            issues.append(f"clear_phase_flags must clear {flag} exactly once")
        if _set_flag(flag) in clear:
            issues.append(f"clear_phase_flags must not set {flag}")

    for flag, setter_name in PHASE_SETTERS.items():
        setter_blocks = named_blocks(effects, setter_name)
        if len(setter_blocks) != 1:
            issues.append(f"phase controller must define exactly one {setter_name}")
            continue
        setter = setter_blocks[0]
        if setter.count("ADISCORD_vorkerland_clear_phase_flags = yes") != 1:
            issues.append(f"{setter_name} must call clear_phase_flags exactly once")
        if setter.count(_set_flag(flag)) != 1:
            issues.append(f"{setter_name} must set only its owned phase flag {flag}")
        if setter.count("ADISCORD_vorkerland_refresh_focus_lifecycle = yes") != 1:
            issues.append(f"{setter_name} must refresh the lifecycle focus layout exactly once")
        foreign_mutations = [
            other
            for other in PHASE_FLAGS
            if other != flag and (_set_flag(other) in setter or _clear_flag(other) in setter)
        ]
        if foreign_mutations:
            issues.append(f"{setter_name} directly mutates foreign phases {foreign_mutations}")
        if effects.count(_set_flag(flag)) != 1:
            issues.append(f"{flag} must be set only once, inside its phase setter")
        if effects.count(_clear_flag(flag)) != 1:
            issues.append(f"{flag} must be cleared only once, inside clear_phase_flags")

    known_phase_flags = set(PHASE_FLAGS)
    for relative, source in _gameplay_phase_token_sources():
        found = set(re.findall(r"\bADISCORD_vorkerland_phase_[a-z0-9_]+\b", source))
        unknown = sorted(found - known_phase_flags)
        if unknown:
            issues.append(f"{relative.as_posix()} uses unknown phase flags {unknown}")
        if relative != PHASE_EFFECTS:
            for flag in PHASE_FLAGS:
                if _set_flag(flag) in source or _clear_flag(flag) in source:
                    issues.append(
                        f"{relative.as_posix()} directly mutates {flag}; use the phase setter effects"
                    )

    for trigger_name in PHASE_TRIGGER_NAMES:
        if len(named_blocks(triggers, trigger_name)) != 1:
            issues.append(f"phase trigger file must define exactly one {trigger_name}")
    claimant = named_block(triggers, "ADISCORD_vorkerland_is_temporary_claimant")
    claimant_tags = set(re.findall(r"\btag\s*=\s*([A-Z]{3})\b", claimant))
    if claimant_tags != {"WKR", "VAD", "TVA"}:
        issues.append(
            f"temporary wartime claimant set must be exactly WKR/VAD/TVA, found {sorted(claimant_tags)}"
        )

    refresh = named_block(effects, "ADISCORD_vorkerland_refresh_focus_lifecycle")
    for tag in ("WRK", "WKR", "VAD", "TVA"):
        scope = named_block(refresh, tag)
        if "focus_unlock = yes" not in scope:
            issues.append(f"lifecycle focus refresh must dirty the {tag} focus layout")

    for effect_name in PHASE_EFFECT_NAMES:
        if len(named_blocks(effects, effect_name)) != 1:
            issues.append(f"phase effect file must define exactly one {effect_name}")

    for name in ACTIVE_WAR_EFFECTS:
        block = named_block(effects, name)
        if block and _contains_wrk_scope(block):
            issues.append(f"active-war effect {name} still scopes the dormant WRK tag")
    for name in ACTIVE_WAR_TRIGGERS:
        block = named_block(triggers, name)
        if block and _contains_wrk_scope(block):
            issues.append(f"active-war trigger {name} still scopes the dormant WRK tag")

    central_preparation = named_block(effects, "ADISCORD_vorkerland_begin_central_preparation")
    if "ADISCORD_vorkerland_phase.4" in central_preparation:
        issues.append(
            "central preparation must wait for the visible consolidation/showdown decision"
        )

    if events.count("add_namespace = ADISCORD_vorkerland_phase") != 1:
        issues.append("phase events must declare add_namespace = ADISCORD_vorkerland_phase exactly once")
    phase_event_ids = [event_id for event_id, _ in event_blocks(events)]
    expected_event_ids = [f"ADISCORD_vorkerland_phase.{number}" for number in range(1, 8)]
    if Counter(phase_event_ids) != Counter(expected_event_ids):
        issues.append(f"phase event file must own unique IDs .1-.7, found {phase_event_ids}")

    definitions: dict[str, list[str]] = {event_id: [] for event_id in expected_event_ids}
    event_root = ROOT / "events"
    if event_root.is_dir():
        for path in sorted(event_root.glob("*.txt")):
            source = strip_comments(path.read_text(encoding="utf-8-sig"))
            for event_id, _ in event_blocks(source):
                if event_id in definitions:
                    definitions[event_id].append(path.relative_to(ROOT).as_posix())
    for event_id, owners in definitions.items():
        if owners != [PHASE_EVENTS.as_posix()]:
            issues.append(f"{event_id} must have one definition owned by {PHASE_EVENTS.as_posix()}, found {owners}")

    # Event .6 runs after the controller has selected one surviving claimant
    # and may therefore materialize/scope the dormant WRK destination.
    for event_number in range(2, 6):
        block = event_block(events, f"ADISCORD_vorkerland_phase.{event_number}")
        if block and _contains_wrk_scope(block):
            issues.append(f"active-war phase event .{event_number} still scopes dormant WRK")

    for label, source in (("effects", effects), ("triggers", triggers), ("events", events)):
        for forbidden in ("on_monthly", "every_country", "any_country", "random_country", "every_state"):
            if re.search(rf"\b{forbidden}\b", source):
                issues.append(f"phase {label} contains forbidden recurring/world scan {forbidden}")

    on_actions = _load(COLLAPSE_ON_ACTIONS, issues)
    for monthly in named_blocks(on_actions, "on_monthly"):
        if "ADISCORD_vorkerland_phase" in monthly:
            issues.append("phase controller is incorrectly driven from on_monthly")
    startup = named_block(on_actions, "on_startup")
    if "NOT = { has_global_flag = ADISCORD_vorkerland_collapse_started }" not in startup:
        issues.append("prewar focus lifecycle must stop after the collapse starts")
    wrk_startup_scopes = named_blocks(startup, "WRK")
    if not any(
        "ADISCORD_vorkerland_set_phase_prewar = yes" in scope
        for scope in wrk_startup_scopes
    ):
        issues.append("startup must initialise the prewar focus phase through its setter in WRK scope")

    bridge_flag = "ADISCORD_vorkerland_materialization_bridge_v1_scheduled"
    focus_tree_load = (
        "load_focus_tree = { tree = ADISCORD_vorkerland_civil_war_focus "
        "keep_completed = yes }"
    )
    materialization_bridges = [
        block
        for block in named_blocks(startup, "if")
        if f"set_global_flag = {bridge_flag}" in block
        and focus_tree_load in block
    ]
    if len(materialization_bridges) != 1:
        issues.append("startup must expose exactly one versioned old-save materialization bridge")
    else:
        bridge = materialization_bridges[0]
        bridge_limit = named_block(bridge, "limit")
        for token in (
            "has_global_flag = ADISCORD_vorkerland_collapse_wars_started",
            "NOT = { has_global_flag = ADISCORD_vorkerland_collapse_finished }",
            "NOT = { has_global_flag = ADISCORD_vorkerland_collapse_materialized_verified }",
            f"NOT = {{ has_global_flag = {bridge_flag} }}",
            "country_exists = WKR",
            "country_exists = VAD",
            "country_exists = TVA",
            "NOT = { country_exists = WRK }",
        ):
            if token not in bridge_limit:
                issues.append(f"startup materialization bridge guard is missing {token}")
        if bridge.count(f"set_global_flag = {bridge_flag}") != 1:
            issues.append("startup materialization bridge must consume its version guard exactly once")
        phase_two = "country_event = { id = ADISCORD_vorkerland_phase.2 days = 1 }"
        for claimant in ("WKR", "VAD", "TVA"):
            claimant_scopes = [
                scope
                for scope in named_blocks(bridge, claimant)
                if focus_tree_load in scope
            ]
            if len(claimant_scopes) != 1:
                issues.append(
                    f"startup materialization bridge must load one shared lifecycle tree into {claimant}"
                )
                continue
            claimant_scope = claimant_scopes[0]
            for token in (focus_tree_load, "focus_unlock = yes", "mark_focus_tree_layout_dirty = yes"):
                if token not in claimant_scope:
                    issues.append(f"startup materialization bridge {claimant} scope is missing {token}")
            if claimant == "WKR" and phase_two not in claimant_scope:
                issues.append("startup materialization bridge must schedule the phase.2 verifier from WKR")
            if claimant != "WKR" and phase_two in claimant_scope:
                issues.append(f"startup materialization bridge must not duplicate phase.2 from {claimant}")
        if bridge.count(focus_tree_load) != 3 or bridge.count(phase_two) != 1:
            issues.append("startup materialization bridge must load three trees and schedule one WKR phase.2")

    for failure_flag in (
        "ADISCORD_vorkerland_collapse_materialization_failed",
        "ADISCORD_vorkerland_regional_war_launch_failed",
        "ADISCORD_vorkerland_central_border_launch_failed",
        "ADISCORD_vorkerland_central_showdown_launch_failed",
        "ADISCORD_vorkerland_reunification_failed",
    ):
        if failure_flag not in effects + events:
            issues.append(f"phase controller is missing terminal diagnostic flag {failure_flag}")
    if "[ADISCORD][VORKERLAND][RECOVERY]" not in effects + events:
        issues.append("phase controller is missing the required recovery diagnostic log prefix")

    return issues


def _pair_flags(slug: str) -> dict[str, str]:
    return {
        state: f"ADISCORD_vorkerland_showdown_edge_{slug}_{state}"
        for state in ("required", "attempted", "retry", "verified", "failed")
    }


def validate_bounded_retry() -> list[str]:
    issues: list[str] = []
    effects = _load(PHASE_EFFECTS, issues)
    triggers = _load(PHASE_TRIGGERS, issues)
    events = _load(PHASE_EVENTS, issues)
    on_actions = _load(COLLAPSE_ON_ACTIONS, issues)
    decisions = _load(FOCUS_DECISIONS, issues)
    decision_effects = _load(FOCUS_DECISION_EFFECTS, issues)
    if any(
        not (ROOT / path).is_file()
        for path in (
            PHASE_EFFECTS,
            PHASE_TRIGGERS,
            PHASE_EVENTS,
            COLLAPSE_ON_ACTIONS,
            FOCUS_DECISIONS,
            FOCUS_DECISION_EFFECTS,
        )
    ):
        return issues

    initialize = named_block(effects, "ADISCORD_vorkerland_initialize_showdown_edge_queue")
    detach_all = named_block(effects, "ADISCORD_vorkerland_detach_showdown_claimants")
    attempt_all = named_block(effects, "ADISCORD_vorkerland_attempt_all_showdown_edges")
    advance = named_block(effects, "ADISCORD_vorkerland_advance_showdown_launch")

    for tag in ("WKR", "VAD", "TVA"):
        if not re.search(
            rf"(?s)country_exists\s*=\s*{tag}\b.*?{tag}\s*=\s*\{{.*?ADISCORD_vorkerland_leave_inherited_faction\s*=\s*yes",
            detach_all,
        ):
            issues.append(f"simultaneous showdown setup must detach {tag} before any declaration")
    detach_position = initialize.find("ADISCORD_vorkerland_detach_showdown_claimants = yes")
    delayed_dispatch_position = initialize.find("ADISCORD_vorkerland_phase.5 days = 1")
    if detach_position < 0 or delayed_dispatch_position < 0 or detach_position > delayed_dispatch_position:
        issues.append("showdown initialization must detach all claimants before its one-day cache delay")

    for slug, left, right, display_name in SHOWDOWN_PAIRS:
        flags = _pair_flags(slug)
        for state in ("attempted", "retry", "verified", "failed"):
            if initialize.count(_clear_flag(flags[state])) != 1:
                issues.append(f"showdown queue must reset {flags[state]} exactly once")

        pair_branch_found = False
        for branch in named_blocks(initialize, "if"):
            if (
                f"country_exists = {left}" in branch
                and f"country_exists = {right}" in branch
                and _set_flag(flags["required"]) in branch
            ):
                pair_branch_found = True
                break
        if not pair_branch_found:
            issues.append(f"showdown queue must require {display_name} only while both tags exist")
        else:
            pair_branch = next(
                branch
                for branch in named_blocks(initialize, "if")
                if f"country_exists = {left}" in branch
                and f"country_exists = {right}" in branch
                and _set_flag(flags["required"]) in branch
            )
            for endpoint in (left, right):
                endpoint_scope = re.search(
                    rf"(?s)\b{endpoint}\s*=\s*\{{(.*?)\}}",
                    pair_branch,
                )
                if not endpoint_scope or "is_subject = no" not in endpoint_scope.group(1):
                    issues.append(f"showdown queue must exclude subject endpoint {endpoint} from {display_name}")
                if not endpoint_scope or "has_capitulated = yes" not in endpoint_scope.group(1):
                    issues.append(f"showdown queue must exclude capitulated endpoint {endpoint} from {display_name}")

        attempt_name = f"ADISCORD_vorkerland_attempt_showdown_edge_{slug}"
        attempt = named_block(effects, attempt_name)
        if flags["required"] not in attempt:
            issues.append(f"{attempt_name} must gate its declaration through {flags['required']}")
        declaration = f"declare_war_on = {{ target = {right} type = annex_everything }}"
        if declaration not in attempt:
            issues.append(f"{attempt_name} must declare the {display_name} edge")
        if attempt.count(_set_flag(flags["attempted"])) != 1:
            issues.append(f"{attempt_name} must record exactly one attempted mutation")
        if "country_event =" in attempt:
            issues.append(f"{attempt_name} must not serialize the launch through its own delayed event")

        verify_name = f"ADISCORD_vorkerland_verify_showdown_edge_{slug}"
        verify = named_block(effects, verify_name)
        if not verify:
            issues.append(f"missing edge verifier {verify_name}")
            continue
        postcondition_positions = [
            position
            for position in (
                verify.find(f"has_war_with = {right}"),
                verify.find(f"has_war_with = {left}"),
            )
            if position >= 0
        ]
        verified_position = verify.find(_set_flag(flags["verified"]))
        if not postcondition_positions:
            issues.append(f"{verify_name} must verify a real {display_name} has_war_with postcondition")
        if verified_position < 0:
            issues.append(f"{verify_name} must own the {flags['verified']} success flag")
        elif postcondition_positions and verified_position < min(postcondition_positions):
            issues.append(f"{verify_name} sets verified before its has_war_with postcondition")
        if verify.count(_set_flag(flags["verified"])) != 1:
            issues.append(f"{verify_name} must set {flags['verified']} exactly once")
        if effects.count(_set_flag(flags["verified"])) != 1:
            issues.append(f"{flags['verified']} is mutated outside its dedicated verifier")
        verified_owners = _global_set_owners(flags["verified"])
        if verified_owners != [PHASE_EFFECTS.as_posix()]:
            issues.append(
                f"{flags['verified']} must be set only by its phase verifier, found owners {verified_owners}"
            )
        if verify.count(_set_flag(flags["retry"])) != 1:
            issues.append(f"{verify_name} must own exactly one explicit retry flag mutation")
        retry_guard = re.search(
            rf"NOT\s*=\s*\{{\s*has_global_flag\s*=\s*{re.escape(flags['retry'])}\s*\}}",
            verify,
        )
        if not retry_guard:
            issues.append(f"{verify_name} must guard its one retry with NOT has_global_flag")
        if verify.count(_set_flag(flags["failed"])) != 1:
            issues.append(f"{verify_name} must own exactly one terminal edge failure")
        if _set_flag("ADISCORD_vorkerland_central_showdown_launch_failed") not in verify:
            issues.append(f"{verify_name} must stop the showdown through the shared terminal failure flag")
        if "ADISCORD_vorkerland_phase.5" in verify:
            issues.append(f"{verify_name} must not serialize edge verification through a private event")
        if display_name not in verify or "[ADISCORD][VORKERLAND][RECOVERY]" not in verify:
            issues.append(f"{verify_name} must log its exact failed pair with the recovery prefix")

    attempt_calls = [
        f"ADISCORD_vorkerland_attempt_showdown_edge_{slug} = yes"
        for slug, _, _, _ in SHOWDOWN_PAIRS
    ]
    attempt_positions = [attempt_all.find(call) for call in attempt_calls]
    if any(position < 0 for position in attempt_positions):
        issues.append("simultaneous showdown launcher must invoke all three edge attempts")
    elif attempt_positions != sorted(attempt_positions):
        issues.append("simultaneous showdown launcher must keep deterministic WKR-VAD, WKR-TVA, VAD-TVA order")
    if "else_if = {" in attempt_all:
        issues.append("simultaneous showdown launcher must not use mutually exclusive one-edge branches")
    attempt_delay = attempt_all.find("ADISCORD_vorkerland_phase.5 days = 1")
    if attempt_delay < 0 or (attempt_positions and attempt_delay < max(attempt_positions)):
        issues.append("simultaneous showdown launcher must schedule one shared postcondition check after all attempts")

    verifier_calls = [
        f"ADISCORD_vorkerland_verify_showdown_edge_{slug} = yes"
        for slug, _, _, _ in SHOWDOWN_PAIRS
    ]
    verifier_positions = [advance.find(call) for call in verifier_calls]
    if any(position < 0 for position in verifier_positions):
        issues.append("showdown advance effect must verify all three edges in the same pass")
    if "ADISCORD_vorkerland_attempt_all_showdown_edges = yes" not in advance:
        issues.append("showdown advance effect must retry all still-missing edges together")
    if "ADISCORD_vorkerland_attempt_next_showdown_edge" in effects:
        issues.append("serial one-edge showdown dispatcher must be retired")

    unwind_name = "ADISCORD_vorkerland_unwind_failed_showdown_launch"
    unwind_blocks = named_blocks(effects, unwind_name)
    if len(unwind_blocks) != 1:
        issues.append("showdown recovery must define exactly one failed-launch unwind effect")
        unwind = ""
    else:
        unwind = unwind_blocks[0]
        unwind_limit = named_block(unwind, "limit")
        for guard in (
            "has_global_flag = ADISCORD_vorkerland_central_showdown_launch_failed",
            "NOT = { has_global_flag = ADISCORD_vorkerland_central_showdown_started }",
        ):
            if guard not in unwind_limit:
                issues.append(f"failed-launch unwind guard is missing {guard}")

        recovery_flags = (
            "ADISCORD_vorkerland_focus_central_showdown_requested",
            "ADISCORD_vorkerland_showdown_queue_initialized",
            "ADISCORD_vorkerland_showdown_launch_round_started",
            "ADISCORD_vorkerland_central_showdown_launch_failed",
            *(
                f"ADISCORD_vorkerland_showdown_edge_{slug}_{state}"
                for slug, _, _, _ in SHOWDOWN_PAIRS
                for state in ("required", "attempted", "retry", "verified", "failed")
            ),
        )
        for flag in recovery_flags:
            if unwind.count(_clear_flag(flag)) != 1:
                issues.append(f"failed-launch unwind must clear {flag} exactly once")

        cooldown_blocks = [
            block
            for block in named_blocks(unwind, "set_global_flag")
            if "flag = ADISCORD_vorkerland_showdown_retry_cooldown" in block
        ]
        if len(cooldown_blocks) != 1:
            issues.append("failed-launch unwind must arm exactly one timed showdown retry cooldown")
        elif cooldown_blocks[0].count("days = 7") != 1:
            issues.append("showdown retry cooldown must last exactly seven days")

    unwind_call = f"{unwind_name} = yes"
    if advance.count(unwind_call) != 1:
        issues.append("showdown advance must invoke failed-launch unwind exactly once")
    else:
        failure_position = advance.find(
            "has_global_flag = ADISCORD_vorkerland_central_showdown_launch_failed"
        )
        unwind_position = advance.find(unwind_call)
        if failure_position < 0 or unwind_position < failure_position:
            issues.append("showdown advance must unwind only after the terminal failure branch")

    commit = named_block(decisions, "ADISCORD_vorkerland_commit_to_central_showdown")
    if not commit:
        issues.append("missing visible central-showdown commit decision")
    else:
        if commit.count("fire_only_once = no") != 1:
            issues.append("central-showdown commit must be repeatable after a failed launch")
        if "fire_only_once = yes" in commit:
            issues.append("central-showdown commit must not retain its obsolete one-shot contract")
        if commit.count("days_re_enable = 7") != 1:
            issues.append("central-showdown commit must re-enable on the same seven-day retry cadence")
        available = named_block(commit, "available")
        cooldown_guard = (
            "NOT = { has_global_flag = ADISCORD_vorkerland_showdown_retry_cooldown }"
        )
        if cooldown_guard not in available:
            issues.append("central-showdown commit must remain unavailable during its retry cooldown")

        scheduler = named_block(
            decision_effects, "ADISCORD_vorkerland_focus_schedule_final_showdown"
        )
        scheduler_limits = [
            named_block(branch, "limit")
            for branch in named_blocks(scheduler, "if")
            if "set_global_flag = ADISCORD_vorkerland_focus_central_showdown_requested" in branch
        ]
        if len(scheduler_limits) != 1:
            issues.append("central-showdown scheduler must expose one guarded request mutation")
        elif cooldown_guard not in scheduler_limits[0]:
            issues.append("central-showdown scheduler must reject requests during retry cooldown")

    startup = named_block(on_actions, "on_startup")
    startup_repair_flag = "ADISCORD_vorkerland_showdown_startup_repair_scheduled"
    phase_repair_branches: dict[str, tuple[str, str]] = {}
    for branch_type in ("if", "else_if"):
        for branch in named_blocks(startup, branch_type):
            for phase_id in ("4", "5"):
                dispatch = f"ADISCORD_vorkerland_phase.{phase_id} days = 1"
                if dispatch in branch and f"flag = {startup_repair_flag}" in branch:
                    existing = phase_repair_branches.get(phase_id)
                    if existing is not None:
                        issues.append(f"startup must expose one coalesced phase.{phase_id} repair branch")
                    else:
                        phase_repair_branches[phase_id] = (branch_type, branch)

    for phase_id in ("4", "5"):
        if phase_id not in phase_repair_branches:
            issues.append(f"startup must recover a missing phase.{phase_id} showdown controller event")
            continue
        branch_type, branch = phase_repair_branches[phase_id]
        branch_limit = named_block(branch, "limit")
        for guard in (
            "has_global_flag = ADISCORD_vorkerland_phase_central_preparation",
            "NOT = { has_global_flag = ADISCORD_vorkerland_central_showdown_started }",
            f"NOT = {{ has_global_flag = {startup_repair_flag} }}",
            "OR = { country_exists = WKR country_exists = VAD country_exists = TVA }",
        ):
            if guard not in branch_limit:
                issues.append(f"startup phase.{phase_id} repair guard is missing {guard}")
        if phase_id == "4":
            if "has_global_flag = ADISCORD_vorkerland_focus_central_showdown_requested" not in branch_limit:
                issues.append("startup phase.4 repair must require an outstanding showdown request")
            if "NOT = { has_global_flag = ADISCORD_vorkerland_showdown_queue_initialized }" not in branch_limit:
                issues.append("startup phase.4 repair must require an uninitialized showdown queue")
            if branch_type != "if":
                issues.append("startup phase.4 repair must precede the initialized-queue branch")
        else:
            if "has_global_flag = ADISCORD_vorkerland_showdown_queue_initialized" not in branch_limit:
                issues.append("startup phase.5 repair must require an initialized showdown queue")
            if branch_type != "else_if":
                issues.append("startup phase.5 repair must be coalesced behind phase.4 with else_if")

        schedule_blocks = [
            block
            for block in named_blocks(branch, "set_global_flag")
            if f"flag = {startup_repair_flag}" in block
        ]
        if len(schedule_blocks) != 1:
            issues.append(f"startup phase.{phase_id} repair must set one timed coalescing guard")
        elif schedule_blocks[0].count("days = 3") != 1:
            issues.append(f"startup phase.{phase_id} coalescing guard must last three days")

        dispatch = f"country_event = {{ id = ADISCORD_vorkerland_phase.{phase_id} days = 1 }}"
        claimant_dispatches = (
            f"WKR = {{ {dispatch} }}",
            f"VAD = {{ {dispatch} }}",
            f"TVA = {{ {dispatch} }}",
        )
        positions = [branch.find(token) for token in claimant_dispatches]
        if any(position < 0 for position in positions):
            issues.append(f"startup phase.{phase_id} repair must cover WKR, VAD, and TVA claimants")
        elif positions != sorted(positions):
            issues.append(f"startup phase.{phase_id} repair must use WKR-VAD-TVA claimant priority")
        if branch.count(dispatch) != 3:
            issues.append(f"startup phase.{phase_id} repair must expose exactly three priority dispatches")

    recovery_tokens = (
        startup_repair_flag,
        "ADISCORD_vorkerland_showdown_retry_cooldown",
        unwind_name,
    )
    for monthly in named_blocks(on_actions, "on_monthly"):
        for token in recovery_tokens:
            if token in monthly:
                issues.append(f"showdown recovery must not poll {token} from on_monthly")

    edge_gate = named_block(triggers, "ADISCORD_vorkerland_central_showdown_edges_verified")
    for slug, _, _, _ in SHOWDOWN_PAIRS:
        flags = _pair_flags(slug)
        if flags["required"] not in edge_gate or flags["verified"] not in edge_gate:
            issues.append(f"central_showdown_edges_verified does not gate required edge {slug}")
            continue
        skip_branch_found = False
        for branch in named_blocks(edge_gate, "OR"):
            required_absent = re.search(
                rf"NOT\s*=\s*\{{\s*has_global_flag\s*=\s*{re.escape(flags['required'])}\s*\}}",
                branch,
            )
            if required_absent and f"has_global_flag = {flags['verified']}" in branch:
                skip_branch_found = True
                break
        if not skip_branch_found:
            issues.append(
                f"central_showdown_edges_verified must skip non-required {slug} without marking it verified"
            )

    verify_showdown = named_block(effects, "ADISCORD_vorkerland_verify_central_showdown")
    gate_token = "ADISCORD_vorkerland_central_showdown_edges_verified = yes"
    success_token = _set_flag("ADISCORD_vorkerland_central_showdown_started")
    if gate_token not in verify_showdown:
        issues.append("central showdown verifier must call the all-required-edges postcondition trigger")
    if success_token not in verify_showdown:
        issues.append("central showdown verifier must own the showdown_started success flag")
    elif verify_showdown.find(success_token) < verify_showdown.find(gate_token):
        issues.append("central showdown success is set before all required edges verify")
    phase_transition = "ADISCORD_vorkerland_set_phase_central_showdown = yes"
    if phase_transition not in verify_showdown:
        issues.append("central showdown verifier must enter the central_showdown phase")
    elif verify_showdown.find(phase_transition) < verify_showdown.find(gate_token):
        issues.append("central showdown phase transition occurs before edge postconditions")
    if verify_showdown.count(success_token) != 1 or effects.count(success_token) != 1:
        issues.append("central_showdown_started must have exactly one mutation in its verifier")
    showdown_owners = _global_set_owners("ADISCORD_vorkerland_central_showdown_started")
    if showdown_owners != [PHASE_EFFECTS.as_posix()]:
        issues.append(
            "central_showdown_started must be set only by the phase postcondition verifier, "
            f"found owners {showdown_owners}"
        )

    phase_five = event_block(events, "ADISCORD_vorkerland_phase.5")
    if "ADISCORD_vorkerland_advance_showdown_launch = yes" not in phase_five:
        issues.append("phase event .5 must advance the shared simultaneous attempt/postcondition round")
    for forbidden_success in (
        "ADISCORD_vorkerland_central_showdown_started",
        "ADISCORD_vorkerland_showdown_edge_wkr_vad_verified",
        "ADISCORD_vorkerland_showdown_edge_wkr_tva_verified",
        "ADISCORD_vorkerland_showdown_edge_vad_tva_verified",
    ):
        if _set_flag(forbidden_success) in phase_five:
            issues.append(f"phase event .5 directly sets success flag {forbidden_success}")

    phase_four = event_block(events, "ADISCORD_vorkerland_phase.4")
    if "ADISCORD_vorkerland_initialize_showdown_edge_queue = yes" not in phase_four:
        issues.append("phase event .4 must initialize the required showdown edge queue")

    phase_six = event_block(events, "ADISCORD_vorkerland_phase.6")
    for guard in (
        "ADISCORD_vorkerland_phase_reunification",
        "ADISCORD_vorkerland_central_showdown_started",
        "ADISCORD_vorkerland_central_showdown_edges_verified = yes",
        "ADISCORD_vorkerland_central_showdown_launch_failed",
        "ADISCORD_vorkerland_has_single_surviving_claimant = yes",
    ):
        if guard not in phase_six:
            issues.append(f"phase event .6 is missing guarded formation prerequisite {guard}")
    for target in ("EYR", "EGC", "RIV", "REV", "YOR", "NDN", "SWB", "VHV", "OSV"):
        guard = f"NOT = {{ country_exists = {target} }}"
        if guard not in phase_six:
            issues.append(f"phase event .6 can revive WRK before terminal district {target}")
    for flag in (
        "ADISCORD_vorkerland_focus_central_minor_launch_pending",
        "ADISCORD_vorkerland_focus_central_minor_deadline_active",
    ):
        if phase_six.count(flag) != 3:
            issues.append(f"phase event .6 must recheck {flag} for all three claimants")
    for state in (
        102, 109, 111, 325, 81, 110, 124, 79, 306, 308, 309, 327,
        82, 323, 108, 122, 123, 27, 35, 315, 316, 317, 318, 320,
    ):
        guard = f"{state} = {{ OR = {{ is_core_of = WKR is_core_of = VAD is_core_of = TVA }} }}"
        if guard not in phase_six:
            issues.append(f"phase event .6 can bypass civil integration of state {state}")

    verify_reunified = named_block(effects, "ADISCORD_vorkerland_verify_reunified_wrk")
    reunited_gate = "ADISCORD_vorkerland_reunification_verified = yes"
    postwar_transition = "ADISCORD_vorkerland_set_phase_postwar_integration = yes"
    if reunited_gate not in verify_reunified:
        issues.append("WRK formation verifier must call the reunification_verified postcondition")
    if postwar_transition not in verify_reunified:
        issues.append("WRK formation verifier must enter postwar integration after success")
    elif verify_reunified.find(postwar_transition) < verify_reunified.find(reunited_gate):
        issues.append("postwar integration success is set before WRK formation postconditions")
    phase_seven = event_block(events, "ADISCORD_vorkerland_phase.7")
    if "ADISCORD_vorkerland_verify_reunified_wrk = yes" not in phase_seven:
        issues.append("phase event .7 must own WRK formation postcondition verification")
    reunification_retry = "ADISCORD_vorkerland_reunification_retry"
    if phase_seven.count(_set_flag(reunification_retry)) != 1:
        issues.append("phase event .7 must own exactly one explicit reunification retry flag")
    retry_guard = re.search(
        rf"NOT\s*=\s*\{{\s*has_global_flag\s*=\s*{re.escape(reunification_retry)}\s*\}}",
        phase_seven,
    )
    if not retry_guard:
        issues.append("phase event .7 must guard its one formation retry")
    if phase_seven.count("ADISCORD_vorkerland_phase.7 days = 1") != 1:
        issues.append("phase event .7 must schedule exactly one explicit formation retry")

    return issues


def validate_reunification_formation() -> list[str]:
    issues: list[str] = []
    effects = _load(PHASE_EFFECTS, issues)
    triggers = _load(PHASE_TRIGGERS, issues)
    events = _load(PHASE_EVENTS, issues)
    if any(not (ROOT / path).is_file() for path in (PHASE_EFFECTS, PHASE_TRIGGERS, PHASE_EVENTS)):
        return issues

    release = named_block(effects, "ADISCORD_vorkerland_release_losing_claimant_subjects")
    for token in (
        "every_subject_country = {",
        "overlord = {",
        "target = PREV",
        "autonomy_state = autonomy_free",
        "leave_faction = yes",
    ):
        if token not in release:
            issues.append(f"losing-claimant subject release is missing {token}")

    formations = (
        (
            "WKR",
            ("VAD", "TVA"),
            "ADISCORD_vorkerland_route_worker",
            "set_cosmetic_tag = WRK_vorkerland_emergency",
            None,
        ),
        (
            "VAD",
            ("WKR", "TVA"),
            "ADISCORD_vorkerland_route_joint",
            "set_cosmetic_tag = WRK_vorkerland_joint_government",
            "ADISCORD_vorkerland_appoint_joint_council = yes",
        ),
        (
            "TVA",
            ("WKR", "VAD"),
            "ADISCORD_vorkerland_route_utilitarian",
            "drop_cosmetic_tag = yes",
            "promote_character = {",
        ),
    )
    for winner, losers, route, cosmetic_effect, leader_effect in formations:
        name = f"ADISCORD_vorkerland_form_wrk_from_{winner.lower()}"
        block = named_block(effects, name)
        # The formation event scopes this effect to the verified winner. Keep
        # using that live country object across change_tag_from; a same-tick
        # lookup through the new WRK tag has the same cache race that formerly
        # broke collapse materialisation.
        change = f"change_tag_from = {winner}"
        change_position = block.find(change)
        if change_position < 0:
            issues.append(f"{name} must change the verified winner {winner} into WRK")
            continue
        if f"WRK = {{ change_tag_from = {winner} }}" in block:
            issues.append(f"{name} must change tag through the live winner scope, not a same-tick WRK lookup")
        for loser in losers:
            release_token = (
                f"{loser} = {{ ADISCORD_vorkerland_release_losing_claimant_subjects = yes }}"
            )
            release_position = block.find(release_token)
            if release_position < 0 or release_position > change_position:
                issues.append(f"{name} must release {loser} subjects before the winner changes tag")
            annex = f"annex_country = {{ target = {loser} transfer_troops = yes }}"
            annex_position = block.find(annex)
            if annex_position < 0 or annex_position < change_position:
                issues.append(f"{name} must annex {loser} with troop transfer only after change_tag_from")
        for token in (
            "ADISCORD_vorkerland_prepare_claimants_for_formation = yes",
            "ADISCORD_vorkerland_finalize_wrk_formation = yes",
            f"set_country_flag = {route}",
            cosmetic_effect,
        ):
            if token not in block:
                issues.append(f"{name} is missing formation contract {token}")
        if leader_effect and leader_effect not in block:
            issues.append(f"{name} is missing route leader effect {leader_effect}")

    finalize = named_block(effects, "ADISCORD_vorkerland_finalize_wrk_formation")
    if "set_capital = { state = 32 }" not in finalize:
        issues.append("reunified WRK must restore state 32 as its capital")
    for route in (
        "ADISCORD_vorkerland_route_worker",
        "ADISCORD_vorkerland_route_joint",
        "ADISCORD_vorkerland_route_utilitarian",
    ):
        if finalize.count(f"clr_country_flag = {route}") != 1:
            issues.append(f"formation finalizer must clear prior country route {route} exactly once")

    reunited = named_block(triggers, "ADISCORD_vorkerland_reunification_verified")
    for token in (
        "country_exists = WRK",
        "controls_state = 32",
        "32 = { is_owned_by = WRK is_controlled_by = WRK }",
        "NOT = { country_exists = WKR }",
        "NOT = { country_exists = VAD }",
        "NOT = { country_exists = TVA }",
    ):
        if token not in reunited:
            issues.append(f"reunification postcondition is missing {token}")

    phase_six = event_block(events, "ADISCORD_vorkerland_phase.6")
    if "ADISCORD_vorkerland_has_single_surviving_claimant = yes" not in phase_six:
        issues.append("formation event must require one surviving claimant")
    formation_branches = named_blocks(phase_six, "if") + named_blocks(phase_six, "else_if")
    for winner in ("WKR", "VAD", "TVA"):
        winner_branches = [
            block
            for block in formation_branches
            if re.search(rf"\b{winner}\s*=\s*\{{\s*exists\s*=\s*yes\b", named_block(block, "limit"))
        ]
        effect_name = f"ADISCORD_vorkerland_form_wrk_from_{winner.lower()} = yes"
        if len(winner_branches) != 1:
            issues.append(f"formation event must expose one verified {winner} winner branch")
            continue
        destination_scopes = [
            block
            for block in named_blocks(winner_branches[0], "WRK")
            if effect_name in block
        ]
        if len(destination_scopes) != 1:
            issues.append(f"formation event must run {effect_name} in the materialized WRK scope")
            continue
        destination = destination_scopes[0]
        if "country_event = { id = ADISCORD_vorkerland_phase.7 days = 1 }" not in destination:
            issues.append(f"formation event must schedule the next-day assertion from WRK after {winner} formation")
    return issues


def validate_retired_legacy_events() -> list[str]:
    issues: list[str] = []
    collapse_events = _load(COLLAPSE_EVENTS, issues)

    for event_id in RETIRED_LEGACY_EVENT_IDS:
        full_id = f"ADISCORD_vorkerland_collapse.{event_id}"
        matches = [block for candidate, block in event_blocks(collapse_events) if candidate == full_id]
        if matches:
            issues.append(f"retired legacy event {full_id} must not remain defined")

    return issues


def collect_issues() -> list[str]:
    issues: list[str] = []
    for validator in (
        validate_wkr_semantics,
        validate_new_save_materialization,
        validate_phase_controller,
        validate_bounded_retry,
        validate_reunification_formation,
        validate_retired_legacy_events,
    ):
        issues.extend(validator())
    # Section validators intentionally overlap on the three controller files.
    # Report shared missing-file diagnostics once while preserving stable order.
    return list(dict.fromkeys(issues))


def main() -> int:
    issues = collect_issues()
    if issues:
        print("Vorkerland recovery validation failed:")
        for issue in issues:
            print(f"- {issue}")
        return 1
    print(
        "Vorkerland recovery validation passed: WKR claimant semantics, atomic new-save "
        "materialization, seven-phase controller, simultaneous bounded three-edge launch, "
        "guarded WRK formation, and retired legacy paths are coherent."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
