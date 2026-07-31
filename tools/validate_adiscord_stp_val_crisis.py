#!/usr/bin/env python3
"""Read-only feature gate for the Stelander Kefreyt crisis implementation."""

from __future__ import annotations

import argparse
import re
import struct
import sys
from pathlib import Path

try:
    from tools.stp_val_crisis_manifest import (
        DECISION_CATEGORIES,
        HEALTH_MISSIONS,
        NOD_CONTROL_MISSIONS,
        NOD_ESCALATION_MISSIONS,
        NOD_LIMITED_TARGET_STATES,
        NOD_LIMITED_TIMEOUT_DAYS,
        NOD_POSTURES,
        NOD_SUPPORT_LEVELS,
        NORTHERN_MODES,
        NORTHERN_STATES,
        NORTHERN_TARGET_LOCKS,
        OWNED_FEATURE_FILES,
        POSTWAR_FOCUS_IDS,
        RESISTANCE_POSTURES,
        SECURITY_POSTURES,
        STP_ADAPTATION_FAMILIES,
        STP_CIVIL_WAR_ARMY_RATIOS,
        STP_CIVIL_WAR_FOCUS_IDS,
        STP_CIVIL_WAR_STATES,
        STP_CALENDAR_LORE_EVENTS,
        STP_CRISIS_FOCUS_LAYOUT,
        STP_CRISIS_FOCUS_REWARDS,
        STP_CRISIS_FOCUS_STAGES,
        STP_OPERATION_SPECS,
        STP_OPERATION_VARIANTS,
        STP_PARTY_FOCUSES,
        STP_RESISTANCE_PROJECTS,
        STP_SHABRAT_FOCUSES,
        STP_SPINE_FOCUS_STAGES,
        STP_STORY_ONLY_FOCUS_IDS,
        VAL_BASE_FOCUS_IDS,
        VAL_AI_FOCUS_COURSE_BIASES,
        VAL_CONTRACT_BANDS,
        VAL_CONTRACT_SPECIALISATIONS,
        VAL_CRISIS_FOCUS_IDS,
        VAL_FOCUS_REWARD_TOKENS,
        VAL_NORTHERN_OPERATION_SPECS,
        VAL_NORTHERN_OPERATION_TARGETS,
        VAL_STP_CONCESSION_FLAGS,
        VAL_STP_OPERATION_SPECS,
        WAR_COUNTDOWN_MISSION_DAYS,
        WAR_COUNTDOWN_MISSIONS,
        WAR_COUNTDOWN_TRUCE_POLICY,
        WAR_COUNTDOWN_WARNING_EVENTS,
    )
except ModuleNotFoundError:
    from stp_val_crisis_manifest import (
        DECISION_CATEGORIES,
        HEALTH_MISSIONS,
        NOD_CONTROL_MISSIONS,
        NOD_ESCALATION_MISSIONS,
        NOD_LIMITED_TARGET_STATES,
        NOD_LIMITED_TIMEOUT_DAYS,
        NOD_POSTURES,
        NOD_SUPPORT_LEVELS,
        NORTHERN_MODES,
        NORTHERN_STATES,
        NORTHERN_TARGET_LOCKS,
        OWNED_FEATURE_FILES,
        POSTWAR_FOCUS_IDS,
        RESISTANCE_POSTURES,
        SECURITY_POSTURES,
        STP_ADAPTATION_FAMILIES,
        STP_CIVIL_WAR_ARMY_RATIOS,
        STP_CIVIL_WAR_FOCUS_IDS,
        STP_CIVIL_WAR_STATES,
        STP_CALENDAR_LORE_EVENTS,
        STP_CRISIS_FOCUS_LAYOUT,
        STP_CRISIS_FOCUS_REWARDS,
        STP_CRISIS_FOCUS_STAGES,
        STP_OPERATION_SPECS,
        STP_OPERATION_VARIANTS,
        STP_PARTY_FOCUSES,
        STP_RESISTANCE_PROJECTS,
        STP_SHABRAT_FOCUSES,
        STP_SPINE_FOCUS_STAGES,
        STP_STORY_ONLY_FOCUS_IDS,
        VAL_BASE_FOCUS_IDS,
        VAL_AI_FOCUS_COURSE_BIASES,
        VAL_CONTRACT_BANDS,
        VAL_CONTRACT_SPECIALISATIONS,
        VAL_CRISIS_FOCUS_IDS,
        VAL_FOCUS_REWARD_TOKENS,
        VAL_NORTHERN_OPERATION_SPECS,
        VAL_NORTHERN_OPERATION_TARGETS,
        VAL_STP_CONCESSION_FLAGS,
        VAL_STP_OPERATION_SPECS,
        WAR_COUNTDOWN_MISSION_DAYS,
        WAR_COUNTDOWN_MISSIONS,
        WAR_COUNTDOWN_TRUCE_POLICY,
        WAR_COUNTDOWN_WARNING_EVENTS,
    )


ROOT = Path(__file__).resolve().parents[1]
SECTIONS = ("core", "stp", "civil_war", "val", "nod", "north", "peace", "ai", "gui", "localisation", "performance")
REQUIRED_FILES = {
    "core": (
        ("common/scripted_effects/ADISCORD_STP_VAL_crisis_core_effects.txt", "core scripted effects"),
        ("common/scripted_triggers/ADISCORD_STP_VAL_crisis_triggers.txt", "crisis scripted triggers"),
        (
            "common/dynamic_modifiers/ADISCORD_STP_VAL_crisis_dynamic_modifiers.txt",
            "crisis dynamic modifiers",
        ),
        ("common/on_actions/01_ADISCORD_STP_VAL_crisis_on_actions.txt", "crisis on-actions"),
        ("interface/ADISCORD_STP_VAL_crisis.gfx", "crisis sprite aliases"),
    ),
    "stp": (
        (
            "common/decisions/categories/ADISCORD_decision_categories_STP.txt",
            "canonical STP party decision category",
        ),
        (
            "common/decisions/categories/ADISCORD_STP_VAL_crisis_categories.txt",
            "crisis decision categories",
        ),
        ("common/decisions/ADISCORD_STP_crisis_decisions.txt", "STP crisis decisions"),
        ("events/ADISCORD_STP_crisis_events.txt", "STP crisis events"),
        ("common/national_focus/ADISCORD_national_focus_STP.txt", "STP crisis focus windows"),
        (
            "common/on_actions/01_ADISCORD_STP_VAL_crisis_on_actions.txt",
            "STP crisis calendar startup",
        ),
        (
            "common/scripted_effects/ADISCORD_STP_VAL_crisis_core_effects.txt",
            "STP crisis commitment effects",
        ),
        (
            "common/focus_inlay_windows/ADISCORD_STP_state_face_inlay_window.txt",
            "STP state-face inlay",
        ),
        (
            "common/scripted_localisation/ADISCORD_STP_leader_health_scripted_loc.txt",
            "STP health scripted localisation",
        ),
        (
            "common/scripted_localisation/ADISCORD_STP_state_face_scripted_loc.txt",
            "STP state-face scripted localisation",
        ),
        (
            "common/scripted_localisation/ADISCORD_STP_party_elections_scripted_loc.txt",
            "STP party scripted localisation",
        ),
        (
            "localisation/russian/ADISCORD_stp_state_face_l_russian.yml",
            "Russian STP state-face localisation",
        ),
        (
            "localisation/russian/ADISCORD_STP_party_elections_l_russian.yml",
            "Russian STP party localisation",
        ),
    ),
    "civil_war": (
        ("common/scripted_effects/ADISCORD_STP_VAL_crisis_war_effects.txt", "crisis war effects"),
        ("common/national_focus/ADISCORD_national_focus_STP_crisis_war.txt", "civil-war focus tree"),
        ("common/national_focus/ADISCORD_national_focus_STP_postwar.txt", "postwar focus tree"),
    ),
    "val": (
        ("common/national_focus/ADISCORD_national_focus_VAL.txt", "VAL contract focus tree"),
        ("interface/goals_shine.gfx", "VAL focus shine sprites"),
        ("common/dynamic_modifiers/ADISCORD_STP_VAL_crisis_dynamic_modifiers.txt", "VAL contract dynamic modifier"),
        ("common/scripted_effects/ADISCORD_STP_VAL_crisis_core_effects.txt", "VAL contract authority effects"),
        ("common/decisions/ADISCORD_VAL_contract_decisions.txt", "VAL contract decisions"),
        ("common/scripted_effects/ADISCORD_STP_VAL_contract_effects.txt", "VAL contract effects"),
        ("events/ADISCORD_VAL_contract_events.txt", "VAL contract events"),
        ("common/on_actions/01_ADISCORD_STP_VAL_crisis_on_actions.txt", "VAL crisis on-actions"),
        ("common/autonomous_states/ADISCORD_contract_clients.txt", "VAL contract-client autonomy"),
    ),
    "peace": (
        (
            "common/on_actions/01_ADISCORD_STP_VAL_crisis_on_actions.txt",
            "crisis scripted peace router",
        ),
        (
            "common/scripted_effects/ADISCORD_STP_VAL_crisis_war_effects.txt",
            "internal and Nodrul scripted peace effects",
        ),
        (
            "common/scripted_effects/ADISCORD_STP_VAL_contract_effects.txt",
            "Kefreyt scripted peace effects",
        ),
        (
            "common/autonomous_states/ADISCORD_contract_clients.txt",
            "contract subject autonomy levels",
        ),
    ),
    "nod": (
        ("common/decisions/ADISCORD_NOD_crisis_decisions.txt", "NOD crisis decisions"),
        ("events/ADISCORD_NOD_crisis_events.txt", "NOD crisis events"),
    ),
    "north": (
        ("common/scripted_effects/ADISCORD_STP_VAL_contract_effects.txt", "contract and northern effects"),
        ("common/scripted_triggers/ADISCORD_STP_VAL_crisis_triggers.txt", "northern eligibility triggers"),
        ("common/decisions/ADISCORD_VAL_contract_decisions.txt", "northern decisions"),
        ("events/ADISCORD_VAL_contract_events.txt", "northern events"),
        ("common/on_actions/01_ADISCORD_STP_VAL_crisis_on_actions.txt", "northern on-actions"),
    ),
    "ai": (
        ("common/ai_strategy/ADISCORD_STP_VAL_crisis_ai.txt", "crisis AI strategies"),
		("common/scripted_triggers/ADISCORD_STP_VAL_crisis_triggers.txt", "crisis AI reserve triggers"),
		("common/decisions/ADISCORD_STP_crisis_decisions.txt", "STP AI decision weights"),
		("common/decisions/ADISCORD_VAL_contract_decisions.txt", "VAL AI decision weights"),
		("common/decisions/ADISCORD_NOD_crisis_decisions.txt", "NOD AI decision weights"),
		("events/ADISCORD_STP_crisis_events.txt", "STP AI course events"),
		("events/ADISCORD_VAL_contract_events.txt", "VAL AI course and deal events"),
		("events/ADISCORD_NOD_crisis_events.txt", "NOD adaptive response events"),
    ),
    "gui": (
        # The obsolete VAL status panel was deliberately retired by the Kefreyt
        # rework. The replacement operations map has its own targeted gate.
    ),
    "localisation": (
        (
            "common/scripted_localisation/ADISCORD_STP_VAL_crisis_scripted_loc.txt",
            "crisis scripted localisation",
        ),
        ("localisation/russian/ADISCORD_STP_VAL_crisis_l_russian.yml", "Russian crisis localisation"),
    ),
    "performance": (),
}


def read(path: Path) -> str | None:
    """Read UTF-8 text, returning None when a later task has not created it yet."""
    try:
        return path.read_text(encoding="utf-8-sig")
    except FileNotFoundError:
        return None


def _mask_non_code(text: str) -> str:
    """Preserve positions while masking comments and quoted strings."""
    masked = list(text)
    in_comment = False
    in_string = False
    escaped = False
    for index, character in enumerate(text):
        if in_comment:
            if character == "\n":
                in_comment = False
            else:
                masked[index] = " "
            continue
        if in_string:
            masked[index] = " "
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == '"':
                in_string = False
            continue
        if character == "#":
            masked[index] = " "
            in_comment = True
        elif character == '"':
            masked[index] = " "
            in_string = True
    return "".join(masked)


def extract_named_block(text: str, identifier: str) -> str | None:
    """Return identifier's braced block, ignoring braces in comments and strings."""
    masked = _mask_non_code(text)
    match = re.search(rf"\b{re.escape(identifier)}\b\s*=\s*\{{", masked)
    if match is None:
        return None
    opening_brace = masked.index("{", match.start())
    depth = 0
    for index in range(opening_brace, len(masked)):
        if masked[index] == "{":
            depth += 1
        elif masked[index] == "}":
            depth -= 1
            if depth == 0:
                return text[opening_brace : index + 1]
    return None


def _has_balanced_braces(text: str) -> bool:
    depth = 0
    for character in _mask_non_code(text):
        if character == "{":
            depth += 1
        elif character == "}":
            depth -= 1
            if depth < 0:
                return False
    return depth == 0


def _iter_named_blocks(text: str, identifier: str):
    masked = _mask_non_code(text)
    pattern = re.compile(rf"\b{re.escape(identifier)}\b\s*=\s*\{{")
    for match in pattern.finditer(masked):
        opening_brace = masked.index("{", match.start())
        depth = 0
        for index in range(opening_brace, len(masked)):
            if masked[index] == "{":
                depth += 1
            elif masked[index] == "}":
                depth -= 1
                if depth == 0:
                    yield text[opening_brace : index + 1]
                    break


def _has_direct_child_block(block: str, identifier: str) -> bool:
    masked = _mask_non_code(block)
    opening_brace = masked.find("{")
    if opening_brace == -1:
        return False
    pattern = re.compile(rf"\b{re.escape(identifier)}\b\s*=\s*\{{")
    depth = 1
    for index in range(opening_brace + 1, len(masked)):
        if masked[index] == "{":
            depth += 1
        elif masked[index] == "}":
            depth -= 1
        elif depth == 1 and pattern.match(masked, index):
            return True
    return False


def _block_with_direct_assignment(
    text: str, block_name: str, assignment_name: str, assignment_value: str
) -> str | None:
    """Find the shallowest block with an exact direct scalar assignment."""
    masked = _mask_non_code(text)
    block_pattern = re.compile(rf"\b{re.escape(block_name)}\b\s*=\s*\{{")
    assignment_pattern = re.compile(
        rf"(?<![A-Za-z0-9_]){re.escape(assignment_name)}\s*=\s*"
        rf"{re.escape(assignment_value)}(?![A-Za-z0-9_.])"
    )
    matches: list[tuple[int, int, str]] = []
    for match in block_pattern.finditer(masked):
        opening_brace = masked.index("{", match.start())
        depth = 0
        closing_brace = None
        for index in range(opening_brace, len(masked)):
            if masked[index] == "{":
                depth += 1
            elif masked[index] == "}":
                depth -= 1
                if depth == 0:
                    closing_brace = index
                    break
        if closing_brace is None:
            continue
        block = text[opening_brace : closing_brace + 1]
        masked_block = masked[opening_brace : closing_brace + 1]
        for assignment in assignment_pattern.finditer(masked_block):
            prefix = masked_block[: assignment.start()]
            if prefix.count("{") - prefix.count("}") != 1:
                continue
            outer_depth = (
                masked[: match.start()].count("{") - masked[: match.start()].count("}")
            )
            matches.append((outer_depth, -len(block), block))
            break
    return min(matches, default=(0, 0, None))[2]


def _direct_scalar_values(block: str, identifier: str) -> list[str]:
    masked = _mask_non_code(block)
    pattern = re.compile(
        rf"(?<![A-Za-z0-9_]){re.escape(identifier)}\s*=\s*([A-Za-z0-9_.+-]+)"
    )
    values = []
    for match in pattern.finditer(masked):
        prefix = masked[: match.start()]
        if prefix.count("{") - prefix.count("}") == 1:
            values.append(match.group(1))
    return values


def _validate_file(relative_path: str, text: str, issues: list[str]) -> None:
    if not _has_balanced_braces(text):
        issues.append(f"{relative_path}: unbalanced braces")
    masked = _mask_non_code(text)
    if re.search(r"\bon_daily\s*=\s*\{", masked):
        issues.append(f"{relative_path}: on_daily is forbidden in crisis feature files")
    if any(not _has_direct_child_block(block, "limit") for block in _iter_named_blocks(text, "every_country")):
        issues.append(f"{relative_path}: unrestricted every_country is forbidden in crisis feature files")
    engine_unsafe = {
        r"\bcheck_temp_variable\b": "uses unsupported check_temp_variable",
        r"\$[A-Za-z_][A-Za-z0-9_]*\$": "uses unsupported scripted-effect parameters",
        r"\badd_army_experience\b": "uses obsolete add_army_experience",
        r"\bset_capital\s*=\s*\d+\b": "uses unbraced set_capital",
        r"(?<!has_)\bstability\s*[<>]": "uses invalid stability trigger",
        r"(?<!has_)\bpolitical_power\s*[<>]": "uses invalid political-power trigger",
        r"(?m)^\s*num_equipment(?:_in_armies)?@[A-Za-z0-9_]+\s*[<>]": "uses equipment variable as a direct trigger",
    }
    for pattern, message in engine_unsafe.items():
        if re.search(pattern, masked):
            issues.append(f"{relative_path}: {message}")
    if relative_path.startswith("common/decisions/") and re.search(
        r"\bcancelable\s*=\s*no\b", masked
    ):
        issues.append(f"{relative_path}: decisions use unsupported cancelable = no")


def _validate_section(root: Path, section: str, issues: list[str]) -> None:
    for relative_path, label in REQUIRED_FILES[section]:
        text = read(root / relative_path)
        if text is None:
            issues.append(f"missing {label}: {relative_path}")
            continue
        _validate_file(relative_path, text, issues)


def _validate_stp_contract(root: Path, issues: list[str]) -> None:
    categories = read(
        root / "common/decisions/categories/ADISCORD_STP_VAL_crisis_categories.txt"
    )
    decisions = read(root / "common/decisions/ADISCORD_STP_crisis_decisions.txt")
    events = read(root / "events/ADISCORD_STP_crisis_events.txt")
    focuses = read(root / "common/national_focus/ADISCORD_national_focus_STP.txt")
    focus_sprites = read(root / "interface/ADISCORD_national_focus.gfx")
    focus_shines = read(root / "interface/goals_shine.gfx")
    on_actions = read(
        root / "common/on_actions/01_ADISCORD_STP_VAL_crisis_on_actions.txt"
    )
    core = read(
        root / "common/scripted_effects/ADISCORD_STP_VAL_crisis_core_effects.txt"
    )
    triggers = read(
        root / "common/scripted_triggers/ADISCORD_STP_VAL_crisis_triggers.txt"
    )

    if categories is not None:
        masked_categories = _mask_non_code(categories)
        for category in DECISION_CATEGORIES:
            count = len(
                re.findall(
                    rf"\b{re.escape(category)}\b\s*=\s*\{{", masked_categories
                )
            )
            if count != 1:
                issues.append(
                    f"STP crisis category {category} must be defined exactly once"
                )

    party_categories = read(
        root / "common/decisions/categories/ADISCORD_decision_categories_STP.txt"
    )
    if party_categories is not None:
        party = extract_named_block(party_categories, "STP_elections_in_the_party") or ""
        for token in (
            "tag = STP",
            "has_country_flag = STP_main_campaign_side",
            "visible_when_empty = yes",
        ):
            if token not in party:
                issues.append(f"canonical STP party category is missing {token}")
    if decisions is not None and not extract_named_block(decisions, "STP_elections_in_the_party"):
        issues.append("STP crisis decisions must live in STP_elections_in_the_party")

    if decisions is not None:
        for mission, (days, event_id) in HEALTH_MISSIONS.items():
            block = extract_named_block(decisions, mission)
            if block is None:
                issues.append(f"missing canonical STP health mission {mission}")
                continue
            if _direct_scalar_values(block, "days_mission_timeout") != [str(days)]:
                issues.append(f"{mission} must last {days} days")
            if _direct_scalar_values(block, "selectable_mission") != ["no"]:
                issues.append(f"{mission} must be a nonselectable mission")
            if re.search(r"\bcancel_effect\s*=", _mask_non_code(block)):
                issues.append(f"{mission} must not define cancel_effect")
            if not re.search(
                rf"\bcountry_event\s*=\s*\{{\s*id\s*=\s*{re.escape(event_id)}\b",
                _mask_non_code(block),
            ):
                issues.append(f"{mission} must time out into {event_id}")

    if events is not None:
        chain = (
            (
                "stp_crisis.1",
                2,
                STP_CALENDAR_LORE_EVENTS[2],
                "STP_health_stage_2_to_3",
            ),
            (
                "stp_crisis.2",
                3,
                STP_CALENDAR_LORE_EVENTS[3],
                "STP_health_stage_3_to_4",
            ),
            (
                "stp_crisis.3",
                4,
                STP_CALENDAR_LORE_EVENTS[4],
                "STP_health_stage_4_to_death",
            ),
        )
        for event_id, stage, lore_events, next_mission in chain:
            block = _block_with_direct_assignment(
                events, "country_event", "id", event_id
            )
            if block is None:
                issues.append(f"missing STP calendar event {event_id}")
                continue
            for token in (
                "hidden = yes",
                f"ADISCORD_STP_VAL_effect_value value = {stage}",
                "STP_set_health_stage = yes",
                f"activate_mission = {next_mission}",
                *(f"country_event = {{ id = {lore_event} }}" for lore_event in lore_events),
            ):
                if token not in block:
                    issues.append(f"{event_id} is missing calendar action {token}")
        stage_two = _block_with_direct_assignment(
            events, "country_event", "id", "stp_crisis.1"
        )
        if stage_two is not None and not re.search(
            r"country_event\s*=\s*\{\s*id\s*=\s*stp_crisis\.5\s+days\s*=\s*69\s*\}",
            _mask_non_code(stage_two),
        ):
            issues.append("stp_crisis.1 must schedule the day-140 probe after 69 days")
        probe = _block_with_direct_assignment(
            events, "country_event", "id", "stp_crisis.5"
        )
        if probe is None or "country_event = { id = stp_crisis.6 }" not in probe:
            issues.append("stp_crisis.5 must invoke the forced side choice")
        death = _block_with_direct_assignment(
            events, "country_event", "id", "stp_crisis.4"
        )
        if death is None:
            issues.append("missing terminal STP death event stp_crisis.4")
        else:
            for token in (
                "set_country_flag = STP_ivanov_dead",
                "ADISCORD_STP_VAL_effect_value value = 5",
                "STP_set_health_stage = yes",
                "country_event = { id = stp_lore.12 }",
                "kill_country_leader = yes",
                "ADISCORD_STP_VAL_effect_value value = 2",
                "STP_set_crisis_phase = yes",
            ):
                if token not in death:
                    issues.append(f"stp_crisis.4 is missing terminal action {token}")
        forced = _block_with_direct_assignment(
            events, "country_event", "id", "stp_crisis.6"
        )
        if forced is None:
            issues.append("missing forced side-choice event stp_crisis.6")
        else:
            for token in (
                "STP_commit_to_shabrat = yes",
                "STP_commit_to_party = yes",
                "STP_forced_commit_no_reward",
                "complete_national_focus = STP_Divide_The_Command_Registers",
                "complete_national_focus = STP_Establish_Reserve_Communications",
                "STP_crisis_late_choice_lock",
                "days = 35",
            ):
                if token not in forced:
                    issues.append(f"stp_crisis.6 is missing forced-choice action {token}")
        for event_id, variable, values in (
            ("stp_crisis.10", "STP_security_posture", SECURITY_POSTURES),
            ("stp_crisis.11", "STP_resistance_posture", RESISTANCE_POSTURES),
        ):
            block = _block_with_direct_assignment(
                events, "country_event", "id", event_id
            )
            if block is None:
                issues.append(f"missing one-time posture event {event_id}")
                continue
            if not re.search(
                rf"check_variable\s*=\s*\{{\s*var\s*=\s*{variable}"
                r"\s+value\s*=\s*0\s+compare\s*=\s*equals\s*\}",
                _mask_non_code(block),
            ):
                issues.append(f"{event_id} must be zero-guarded for {variable}")
            assigned = {
                int(value)
                for value in re.findall(
                    rf"set_variable\s*=\s*\{{\s*var\s*=\s*{variable}"
                    r"\s+value\s*=\s*(\d+)\s*\}",
                    _mask_non_code(block),
                )
            }
            if assigned != set(values):
                issues.append(f"{event_id} must assign every canonical {variable} value")

    if focuses is not None:
        playable_focus_ids = {
            values[0]
            for block in _iter_named_blocks(focuses, "focus")
            if (values := _direct_scalar_values(block, "id"))
        }
        if playable_focus_ids != set(STP_CRISIS_FOCUS_STAGES):
            issues.append(
                "STP pre-death tree must contain exactly the "
                f"{len(STP_CRISIS_FOCUS_STAGES)} playable crisis focuses"
            )
        visible_focus_ids = (
            playable_focus_ids
            - set(STP_PARTY_FOCUSES)
            - {"STP_Govern_In_His_Name"}
        )
        if len(visible_focus_ids) != 17:
            issues.append("STP player route must contain exactly 17 visible mechanical focuses")
        if STP_SPINE_FOCUS_STAGES:
            issues.append("calendar spine focus manifest must remain empty")
        for removed_focus in STP_STORY_ONLY_FOCUS_IDS:
            if removed_focus in playable_focus_ids:
                issues.append(f"story-only focus {removed_focus} must not exist in the tree")
        if "is_completed_by_event = yes" in _mask_non_code(focuses):
            issues.append("STP pre-death tree must not contain event-completed focuses")
        used_icons: set[str] = set()
        for focus, stage in STP_CRISIS_FOCUS_STAGES.items():
            block = _block_with_direct_assignment(focuses, "focus", "id", focus)
            if block is None:
                issues.append(f"missing playable STP crisis focus {focus}")
                continue
            used_icons.update(_direct_scalar_values(block, "icon"))
            costs = _direct_scalar_values(block, "cost")
            if len(costs) != 1 or not 0 < float(costs[0]) <= 5:
                issues.append(f"playable focus {focus} must last at most 35 days")
            if _direct_scalar_values(block, "cancelable") != ["no"]:
                issues.append(f"playable focus {focus} must be noncancelable")
            if _direct_scalar_values(block, "cancel_if_invalid") != ["yes"]:
                issues.append(f"playable focus {focus} must cancel when its window closes")
            if _direct_scalar_values(block, "continue_if_invalid") != ["no"]:
                issues.append(f"playable focus {focus} must not continue outside its window")
            sticky = f"STP_focus_active_{focus}"
            select = extract_named_block(block, "select_effect") or ""
            available = extract_named_block(block, "available") or ""
            reward = extract_named_block(block, "completion_reward") or ""
            if f"set_country_flag = {sticky}" not in select:
                issues.append(f"playable focus {focus} must set its sticky selection flag")
            if f"has_country_flag = {sticky}" not in available:
                issues.append(f"playable focus {focus} must honor its sticky selection flag")
            if f"clr_country_flag = {sticky}" not in reward:
                issues.append(f"playable focus {focus} must clear its sticky selection flag")
            for token in (
                "NOT = { has_country_flag = STP_ivanov_dead }",
                "NOT = { has_country_flag = STP_crisis_late_choice_lock }",
            ):
                if token not in available:
                    issues.append(f"playable focus {focus} has an invalid stage window")
                    break
            if not re.search(
                r"check_variable\s*=\s*\{\s*var\s*=\s*STP_leader_health_stage"
                rf"\s+value\s*=\s*{stage}\s+compare\s*=\s*equals\s*\}}",
                _mask_non_code(available),
            ):
                issues.append(f"playable focus {focus} has an invalid stage window")
            interface = STP_CRISIS_FOCUS_REWARDS[focus]
            expected_reward = (
                f"{interface} = yes"
                if interface.startswith("STP_commit_to_")
                else f"set_country_flag = {interface}"
            )
            if expected_reward not in reward:
                issues.append(f"playable focus {focus} is missing reward {interface}")
            if "country_event" in _mask_non_code(reward):
                issues.append(f"playable focus {focus} must not use a story event as its reward")
            broad_markers = re.findall(
                r"\b(?:set_country_flag|add_political_power|add_stability|add_war_support|"
                r"army_experience|add_command_power|STP_improve_transition_[A-Za-z0-9_]+|"
                r"STP_change_node_[A-Za-z0-9_]+|STP_commit_to_[A-Za-z0-9_]+)\b",
                _mask_non_code(reward),
            )
            if len(broad_markers) < 2:
                issues.append(f"playable focus {focus} must provide a broad mechanical reward")
            relative, x, y = STP_CRISIS_FOCUS_LAYOUT[focus]
            if _direct_scalar_values(block, "x") != [str(x)] or _direct_scalar_values(
                block, "y"
            ) != [str(y)]:
                issues.append(f"playable focus {focus} breaks the compact crisis layout")
            actual_relative = _direct_scalar_values(block, "relative_position_id")
            expected_relative = [] if relative is None else [relative]
            if actual_relative != expected_relative:
                issues.append(f"playable focus {focus} has the wrong layout anchor")
            side_value = (
                1 if focus in STP_SHABRAT_FOCUSES else 2 if focus in STP_PARTY_FOCUSES else None
            )
            if side_value is not None and not re.search(
                r"var\s*=\s*STP_side_commitment\s+value\s*=\s*"
                rf"{side_value}\s+compare\s*=\s*equals",
                _mask_non_code(available),
            ):
                issues.append(f"playable focus {focus} has the wrong side gate")
        show = _block_with_direct_assignment(
            focuses, "focus", "id", "STP_Show_Him_The_Truth"
        ) or ""
        show_prerequisites = list(_iter_named_blocks(show, "prerequisite"))
        expected_opening = {
            "STP_The_Old_Man_On_The_Balcony",
            "STP_Count_The_Loyalists",
            "STP_The_City_Still_Dances",
            "STP_Foreign_Guests_At_The_Banquet",
        }
        actual_opening = set(
            re.findall(
                r"\bfocus\s*=\s*(STP_[A-Za-z0-9_]+)",
                _mask_non_code(show_prerequisites[0]) if show_prerequisites else "",
            )
        )
        if len(show_prerequisites) != 1 or actual_opening != expected_opening:
            issues.append("the four opening programmes must converge on the visible route focus")
        for party_focus in STP_PARTY_FOCUSES:
            block = _block_with_direct_assignment(focuses, "focus", "id", party_focus) or ""
            if any(_iter_named_blocks(block, "prerequisite")):
                issues.append(f"AI-only focus {party_focus} must not draw ghost prerequisite lines")
        if "GFX_focus_STP_Open_Wounds_Of_The_System" in used_icons:
            issues.append("the placeholder Open Wounds artwork must not be used by a focus")
        if focus_sprites is not None and focus_shines is not None:
            for icon in used_icons:
                base_sprite = next(
                    (
                        block
                        for block in _iter_named_blocks(focus_sprites, "spriteType")
                        if re.search(rf'\bname\s*=\s*"{re.escape(icon)}"', block)
                    ),
                    "",
                )
                shine_sprite = next(
                    (
                        block
                        for block in _iter_named_blocks(focus_shines, "SpriteType")
                        if re.search(
                            rf'\bname\s*=\s*"{re.escape(icon)}_shine"', block
                        )
                    ),
                    "",
                )
                if not base_sprite:
                    issues.append(f"STP focus icon {icon} is missing its base sprite")
                if not shine_sprite:
                    issues.append(f"STP focus icon {icon} is missing its shine sprite")
    if on_actions is not None:
        startup = extract_named_block(on_actions, "on_startup") or ""
        for token in (
            "STP_health_calendar_started",
            "country_event = { id = stp_lore.1 }",
            "activate_mission = STP_health_stage_1_to_2",
        ):
            if token not in startup:
                issues.append(f"STP startup is missing guarded calendar action {token}")
        if not re.search(
            r"NOT\s*=\s*\{\s*has_country_flag\s*=\s*STP_health_calendar_started\s*\}"
            r".*set_country_flag\s*=\s*STP_health_calendar_started"
            r".*country_event\s*=\s*\{\s*id\s*=\s*stp_lore\.1\s*\}"
            r".*activate_mission\s*=\s*STP_health_stage_1_to_2",
            _mask_non_code(startup),
            re.DOTALL,
        ):
            issues.append("STP startup calendar activation must be guarded and atomic")
        if startup.count("ADISCORD_STP_VAL_refresh_presentation_mirrors = yes") < 2:
            issues.append("STP and VAL startup scopes must refresh their presentation mirrors")

    if core is not None:
        mirrors = extract_named_block(
            core, "ADISCORD_STP_VAL_refresh_presentation_mirrors"
        ) or ""
        health_mutation = extract_named_block(core, "STP_set_health_stage") or ""
        for stage, health in ((1, 100), (2, 75), (3, 45), (4, 15)):
            token = f"var = STP_leader_health value = {health}"
            if token not in mirrors or token not in health_mutation:
                issues.append(
                    f"STP health stage {stage} must keep the {health}% presentation mirror"
                )
        for effect, value, event_id in (
            ("STP_commit_to_shabrat", 1, "stp_crisis.10"),
            ("STP_commit_to_party", 2, "stp_crisis.11"),
        ):
            block = extract_named_block(core, effect) or ""
            if not re.search(
                r"var\s*=\s*STP_side_commitment\s+value\s*=\s*0"
                r"\s+compare\s*=\s*equals",
                _mask_non_code(block),
            ):
                issues.append(f"{effect} must be one-way from an uncommitted state")
            if not re.search(
                r"set_variable\s*=\s*\{\s*var\s*=\s*STP_side_commitment"
                rf"\s+value\s*=\s*{value}\s*\}}",
                _mask_non_code(block),
            ):
                issues.append(f"{effect} must set commitment value {value}")
            if f"country_event = {{ id = {event_id} days = 1 }}" not in block:
                issues.append(f"{effect} must schedule one-time posture event {event_id}")

    scripted_paths = (
        "common/focus_inlay_windows/ADISCORD_STP_state_face_inlay_window.txt",
        "common/scripted_localisation/ADISCORD_STP_leader_health_scripted_loc.txt",
        "common/scripted_localisation/ADISCORD_STP_state_face_scripted_loc.txt",
        "common/scripted_localisation/ADISCORD_STP_party_elections_scripted_loc.txt",
    )
    for relative in scripted_paths:
        text = read(root / relative)
        if text is None:
            continue
        masked = _mask_non_code(text)
        if "original_tag = STP" in masked:
            issues.append(f"{relative}: must use current STP role gating")
        if re.search(
            r"\bvar\s*=\s*STP_state_face_stage\b"
            r"|\bSTP_state_face_stage\s*(?:=|>|<)",
            masked,
        ):
            issues.append(f"{relative}: legacy state-face variable access is forbidden")

    party_loc_path = (
        root / "localisation/russian/ADISCORD_STP_party_elections_l_russian.yml"
    )
    party_loc = read(party_loc_path)
    if party_loc is not None:
        health_loc = read(
            root / "localisation/russian/ADISCORD_STP_leader_health_l_russian.yml"
        ) or ""
        if "[?STP_leader_health|0]%" not in health_loc:
            issues.append("STP leader health must display as a whole-number percentage")
        if "[STPGetLeaderHealthEffects]" not in health_loc:
            issues.append("STP leader health display must expose its current modifiers")
        if "[?STP_party_suspicion|R0]%" not in party_loc:
            issues.append("STP party suspicion must display as a whole-number percentage")
        for legacy in (
            "[?STP_party_suspicion|R1%]",
            "STP_party_suspicion_political_power_gain_dynamic_var",
        ):
            if legacy in party_loc:
                issues.append(f"STP party suspicion localisation retains legacy token {legacy}")
    for relative in (
        "localisation/russian/ADISCORD_stp_state_face_l_russian.yml",
        "localisation/russian/ADISCORD_STP_party_elections_l_russian.yml",
    ):
        path = root / relative
        if path.exists() and not path.read_bytes().startswith(b"\xef\xbb\xbf"):
            issues.append(f"{relative}: Russian localisation must retain UTF-8 BOM")


def _validate_civil_war_contract(root: Path, issues: list[str]) -> None:
    war = read(
        root / "common/scripted_effects/ADISCORD_STP_VAL_crisis_war_effects.txt"
    )
    events = read(root / "events/ADISCORD_STP_crisis_events.txt")
    on_actions = read(
        root / "common/on_actions/01_ADISCORD_STP_VAL_crisis_on_actions.txt"
    )
    war_tree = read(
        root / "common/national_focus/ADISCORD_national_focus_STP_crisis_war.txt"
    )
    postwar_tree = read(
        root / "common/national_focus/ADISCORD_national_focus_STP_postwar.txt"
    )
    ideas = read(root / "common/ideas/ADISCORD_STP_VAL_crisis_ideas.txt")
    decisions = read(root / "common/decisions/ADISCORD_STP_crisis_decisions.txt")
    units = read(root / "history/units/STP.txt")

    if war is not None:
        for effect, expected in (
            (
                "STP_start_resistance_revolt_chauvinism",
                tuple(str(value) for value in STP_CIVIL_WAR_ARMY_RATIOS["resistance_revolter"]),
            ),
            (
                "STP_start_resistance_revolt_etatism",
                tuple(str(value) for value in STP_CIVIL_WAR_ARMY_RATIOS["resistance_revolter"]),
            ),
            (
                "STP_start_party_revolt",
                tuple(str(value) for value in STP_CIVIL_WAR_ARMY_RATIOS["party_revolter"]),
            ),
        ):
            block = extract_named_block(war, effect) or ""
            starts = list(_iter_named_blocks(block, "start_civil_war"))
            if len(starts) != 4:
                issues.append(f"{effect} must contain exactly four literal start_civil_war branches")
                continue
            ratios = tuple(
                values[0] if len(values) == 1 else ""
                for values in (
                    _direct_scalar_values(start, "army_ratio") for start in starts
                )
            )
            if ratios != expected:
                issues.append(f"{effect} has a noncanonical or computed army_ratio table")
            for start in starts:
                if _direct_scalar_values(start, "size") != ["0"]:
                    issues.append(f"{effect} must use size = 0 in every split branch")
                    break
                if _direct_scalar_values(start, "keep_all_characters") != ["yes"]:
                    issues.append(f"{effect} must retain characters for deterministic reassignment")
                    break

        masked_war = _mask_non_code(war)
        if "delete_unit_template_and_units" in masked_war:
            issues.append("civil-war split must not delete division templates or arbitrary units")
        delete_blocks = list(_iter_named_blocks(war, "delete_units"))
        if len(delete_blocks) != 1 or any(
            'division_template = "Capital Guard"' not in block
            or _direct_scalar_values(block, "disband") != ["yes"]
            for block in delete_blocks
        ):
            issues.append("civil-war split may disband only the deployed Capital Guard")
        for token in (
            "save_global_event_target_as = STP_crisis_main_side",
            "save_global_event_target_as = STP_crisis_party_side",
            "save_global_event_target_as = STP_crisis_resistance_side",
            "original_tag = STP",
            "has_war_with = ROOT",
            "NOT = { has_country_flag = STP_main_campaign_side }",
            "tree = ADISCORD_STP_crisis_war_focus",
            "keep_completed = no",
        ):
            if token not in war:
                issues.append(f"guarded civil-war split is missing {token}")

        state_map = extract_named_block(war, "STP_apply_civil_war_state_map") or ""
        transferred = {
            int(value)
            for value in re.findall(
                r"\btransfer_state\s*=\s*(\d+)\b", _mask_non_code(state_map)
            )
        }
        if transferred != set(STP_CIVIL_WAR_STATES):
            issues.append("civil-war state mapping must transfer only all eleven manifest states")
        for state in STP_CIVIL_WAR_STATES:
            if f"STP_prewar_owned_state_{state}" not in war:
                issues.append(f"civil-war split does not snapshot state {state}")

        escrow = extract_named_block(war, "STP_transfer_resistance_escrow") or ""
        for equipment in ("infantry", "support"):
            source = f"STP_resistance_escrow_{equipment}"
            snapshot = f"STP_prewar_resistance_escrow_{equipment}"
            transfer_index = escrow.find(f"amount = ROOT.{snapshot}")
            zero_index = escrow.find(f"set_variable = {{ var = {source} value = 0 }}")
            if transfer_index == -1 or zero_index == -1 or zero_index < transfer_index:
                issues.append(f"{source} must transfer once before every copied source is zeroed")

        finalizer = extract_named_block(war, "STP_finalize_internal_outcome") or ""
        for token in (
            "STP_internal_outcome_finalizing",
            "STP_internal_outcome_finalized",
            "save_global_event_target_as = STP_postwar_country",
            "set_country_flag = STP_postwar_campaign_side",
            "ADISCORD_STP_VAL_effect_value value = 3",
            "STP_set_crisis_phase = yes",
            "STP_assign_postwar_leader = yes",
            "tree = ADISCORD_STP_postwar_focus",
            "STP_clear_external_crisis_participants = yes",
            "VAL_STP_start_war_countdown_120 = yes",
        ):
            if token not in finalizer:
                issues.append(f"single internal finalizer is missing {token}")
        if (
            "STP_assign_postwar_leader = yes" in finalizer
            and "tree = ADISCORD_STP_postwar_focus" in finalizer
            and finalizer.index("STP_assign_postwar_leader = yes")
            > finalizer.index("tree = ADISCORD_STP_postwar_focus")
        ):
            issues.append("postwar leader assignment must run before the postwar tree is loaded")
        if extract_named_block(war, "STP_complete_transition_outcome_focus") is not None:
            issues.append("outcomes must route directly without a transition-focus bridge")
        if "STP_complete_transition_outcome_focus = yes" in war:
            issues.append("postwar logic must not call a transition-focus bridge")
        for days in (120, 180, 300, 450):
            countdown = extract_named_block(war, f"VAL_STP_start_war_countdown_{days}") or ""
            for token in (
                "VAL_STP_countdown_pending",
                f"STP_VAL_start_canonical_countdown_{days} = yes",
            ):
                if token not in countdown:
                    issues.append(f"countdown forward interface {days} is missing {token}")
            if "activate_mission" in countdown:
                issues.append("countdown forward interface must leave mission ownership to the canonical starter")

    if events is not None:
        death = _block_with_direct_assignment(events, "country_event", "id", "stp_crisis.4") or ""
        router = _block_with_direct_assignment(events, "country_event", "id", "stp_crisis.50") or ""
        if "country_event = { id = stp_crisis.50 days = 3 }" not in death:
            issues.append(
                "Ivanov death event must leave a three-day interregnum before the outcome router"
            )
        expected_outcomes = {
            "STP_outcome_shabrat_bloodless",
            "STP_outcome_shabrat_main_war",
            "STP_outcome_sotnikov_main_war",
            "STP_outcome_hedersett_consolidation",
        }
        actual_outcomes = set(
            re.findall(
                r"\bset_country_flag\s*=\s*(STP_outcome_[A-Za-z0-9_]+)",
                _mask_non_code(router),
            )
        )
        if actual_outcomes != expected_outcomes:
            issues.append("Ivanov death router must expose exactly four canonical outcomes")
        if router.count("STP_finalize_internal_outcome = yes") != 1:
            issues.append("the rare bloodless outcome must use the single finalizer")
        fallback = _block_with_direct_assignment(
            events, "country_event", "id", "stp_crisis.51"
        ) or ""
        for token in (
            "STP_try_finalize_internal_war = yes",
            "country_event = { id = stp_crisis.51 days = 3 }",
            "STP_internal_outcome_finalizing",
            "STP_internal_outcome_finalized",
        ):
            if token not in fallback:
                issues.append(f"three-day civil-war fallback is missing {token}")

    if on_actions is not None:
        for hook in ("on_peace", "on_capitulation"):
            block = extract_named_block(on_actions, hook) or ""
            for token in (
                "STP_try_finalize_internal_war = yes",
                "STP_internal_outcome_finalizing",
                "STP_internal_outcome_finalized",
            ):
                if token not in block:
                    issues.append(f"{hook} is missing guarded internal-war completion")
                    break
            # on_peace has no reliable winner scope. on_capitulation may use
            # FROM only to verify the exact war side; the winner itself must
            # still be selected from the saved canonical role targets.
            if hook == "on_peace" and re.search(r"\bFROM\b", _mask_non_code(block)):
                issues.append(f"{hook} must not infer the internal winner from FROM")

        capitulation = extract_named_block(on_actions, "on_capitulation") or ""
        for token in (
            "STP_internal_capitulated_side",
            "event_target:STP_crisis_party_side",
            "event_target:STP_crisis_resistance_side",
            "STP_resolve_scripted_internal_victory = yes",
        ):
            if token not in capitulation:
                issues.append(
                    "on_capitulation scripted internal peace must select the winner from saved role targets"
                )
                break

    for tree, expected, label in (
        (war_tree, set(STP_CIVIL_WAR_FOCUS_IDS), "civil-war"),
        (postwar_tree, set(POSTWAR_FOCUS_IDS), "postwar"),
    ):
        if tree is None:
            continue
        ids = set(
            re.findall(r"\bid\s*=\s*(STP_[A-Za-z0-9_]+)", _mask_non_code(tree))
        )
        if ids != expected:
            issues.append(f"{label} focus tree must define exactly its manifest focus IDs")
        for focus_id in expected:
            block = _block_with_direct_assignment(tree, "focus", "id", focus_id) or ""
            if _direct_scalar_values(block, "cost") != ["5"]:
                issues.append(f"{label} focus {focus_id} must cost 5")

    if ideas is None:
        issues.append("missing Task 5 officer preparation ideas")
    else:
        for idea, planning in (
            ("STP_officer_preparation_1", "0.05"),
            ("STP_officer_preparation_2", "0.075"),
            ("STP_officer_preparation_3", "0.10"),
        ):
            block = extract_named_block(ideas, idea) or ""
            if _direct_scalar_values(
                extract_named_block(block, "modifier") or "", "max_planning_factor"
            ) != [planning]:
                issues.append(f"{idea} must have its exact planning bonus")

    if decisions is not None:
        sabotage = extract_named_block(decisions, "STP_party_market_sabotage") or ""
        if _direct_scalar_values(sabotage, "days_mission_timeout") != ["90"]:
            issues.append("party market sabotage must last exactly 90 days")
        modifier = extract_named_block(sabotage, "modifier") or ""
        if _direct_scalar_values(modifier, "civilian_factory_use") != ["1"]:
            issues.append("party market sabotage must reserve exactly one civilian factory")

    if units is not None:
        for template in (
            "STP Mountain Resistance Militia",
            "STP Urban Resistance Militia",
        ):
            block = next(
                (
                    candidate
                    for candidate in _iter_named_blocks(units, "division_template")
                    if re.search(
                        rf'\bname\s*=\s*"{re.escape(template)}"', candidate
                    )
                ),
                None,
            )
            if block is None or "ADISCORD_militia" not in block:
                issues.append(f"missing locked militia template {template}")
            elif (
                _direct_scalar_values(block, "is_locked") != ["yes"]
                or _direct_scalar_values(block, "force_allow_recruiting") != ["no"]
            ):
                issues.append(f"militia template {template} must remain locked")


def _validate_val_contract_campaign(root: Path, issues: list[str]) -> None:
    focus_text = read(root / "common/national_focus/ADISCORD_national_focus_VAL.txt")
    goal_shines = read(root / "interface/goals_shine.gfx")
    core = read(root / "common/scripted_effects/ADISCORD_STP_VAL_crisis_core_effects.txt")
    triggers = read(root / "common/scripted_triggers/ADISCORD_STP_VAL_crisis_triggers.txt")
    dynamic = read(root / "common/dynamic_modifiers/ADISCORD_STP_VAL_crisis_dynamic_modifiers.txt")
    ideas = "\n".join(
        filter(
            None,
            (
                read(root / "common/ideas/ADISCORD_STP_VAL_crisis_ideas.txt"),
                read(root / "common/ideas/ADISCORD_VAL_rework_ideas.txt"),
            ),
        )
    )
    decisions = read(root / "common/decisions/ADISCORD_VAL_contract_decisions.txt")
    contract_effects = read(
        root / "common/scripted_effects/ADISCORD_STP_VAL_contract_effects.txt"
    )
    contract_events = read(root / "events/ADISCORD_VAL_contract_events.txt")
    on_actions = read(root / "common/on_actions/01_ADISCORD_STP_VAL_crisis_on_actions.txt")
    autonomy = read(root / "common/autonomous_states/ADISCORD_contract_clients.txt")

    if focus_text is not None:
        blocks: dict[str, str] = {}
        for focus_id in (*VAL_BASE_FOCUS_IDS, *VAL_CRISIS_FOCUS_IDS):
            block = _block_with_direct_assignment(
                focus_text, "focus", "id", focus_id
            ) or ""
            blocks[focus_id] = block
            if not block:
                issues.append(f"missing VAL campaign focus {focus_id}")
                continue
            if _direct_scalar_values(block, "cost") != ["5"]:
                issues.append(f"{focus_id} must cost exactly 5")
            reward = extract_named_block(block, "completion_reward") or ""
            if not _mask_non_code(reward).strip("{} \t\r\n"):
                issues.append(f"{focus_id} must have a gameplay reward")
            hidden = extract_named_block(reward, "hidden_effect") or ""
            internal_effects = (
                "VAL_change_contract_authority = yes",
                "VAL_refresh_contract_modifier = yes",
                "VAL_change_final_war_preparation = yes",
                "VAL_change_stp_leverage = yes",
            )
            for token in internal_effects:
                if token in reward and token not in hidden:
                    issues.append(f"{focus_id} exposes internal recalculation {token}")
            if any(token in reward for token in internal_effects) and "custom_effect_tooltip" not in reward:
                issues.append(f"{focus_id} must explain hidden gameplay changes with a custom tooltip")

        for focus_id, tokens in VAL_FOCUS_REWARD_TOKENS.items():
            reward = extract_named_block(blocks.get(focus_id, ""), "completion_reward") or ""
            for token in tokens:
                if token not in reward:
                    issues.append(f"{focus_id} reward is missing {token}")

        for focus_id, course_flags in VAL_AI_FOCUS_COURSE_BIASES.items():
            ai = extract_named_block(blocks.get(focus_id, ""), "ai_will_do") or ""
            if ai.strip() == "{ base = 1 }":
                issues.append(f"{focus_id} must not use a context-free AI choice")
            for flag in course_flags:
                if f"has_country_flag = {flag}" not in ai:
                    issues.append(f"{focus_id} AI choice is missing course bias {flag}")
        for focus_id in ("VAL_Gromovs_Assault_Tables", "VAL_October_Of_2160"):
            ai = extract_named_block(blocks.get(focus_id, ""), "ai_will_do") or ""
            if "NOD =" not in ai or "NOD_crisis_posture_guardian" not in ai:
                issues.append(f"{focus_id} AI choice must react to the live Nodrul posture")

        for group in (
            ("VAL_Ballistics_Schools", "VAL_Brokered_Steel"),
            ("VAL_Vorons_Companies", "VAL_Stahls_Schedules", "VAL_Gromovs_Assault_Tables"),
            ("VAL_Field_Surgeons", "VAL_Bread_From_Barracks"),
            ("VAL_Trading_Partners", "VAL_October_Of_2160"),
            VAL_CRISIS_FOCUS_IDS[:4],
        ):
            for focus_id in group:
                block = blocks.get(focus_id, "")
                for rival in group:
                    if rival != focus_id and f"focus = {rival}" not in (
                        extract_named_block(block, "mutually_exclusive") or ""
                    ):
                        issues.append(f"{focus_id} must exclude {rival}")

        final_join = blocks.get("VAL_Contracts_Outlive_Kings", "")
        for terminal in (
            "VAL_State_Contract",
            "VAL_Industrial_Mobilization_Plan",
            "VAL_Army_Of_The_Ledger",
        ):
            if not re.search(
                rf"prerequisite\s*=\s*\{{\s*focus\s*=\s*{terminal}\s*\}}",
                _mask_non_code(final_join),
            ):
                issues.append(f"VAL final join must require completed branch {terminal}")

        for focus_id in VAL_CRISIS_FOCUS_IDS[:4]:
            block = blocks.get(focus_id, "")
            allow = extract_named_block(block, "allow_branch") or ""
            for token in (
                "has_completed_focus = VAL_Contracts_Outlive_Kings",
                "VAL_stp_crisis_at_least_rupture = yes",
            ):
                if token not in allow:
                    issues.append(f"{focus_id} branch gate is missing {token}")

        for focus_id in ("VAL_Offer_The_Mountain_Contract", "VAL_Secure_The_Resource_Corridor"):
            if "VAL_has_active_stp_civil_war = yes" not in blocks.get(focus_id, ""):
                issues.append(f"{focus_id} must require the active saved STP civil war")
        if "VAL_can_negotiate_deferred_invoice = yes" not in blocks.get(
            "VAL_Negotiate_The_Deferred_Invoice", ""
        ):
            issues.append("VAL deferred-invoice focus must require the live no-war window")
        present = blocks.get("VAL_Present_The_Final_Invoice", "")
        if "VAL_has_postwar_stp_target = yes" not in present:
            issues.append("VAL final-invoice focus must require the saved postwar country")
        if "VAL_STP_start_war_countdown" in present:
            issues.append("VAL final-invoice focus must not alter the canonical war timer")
        if "declare_war_on" in _mask_non_code(present):
            issues.append("VAL final-invoice focus must not be the final-war declaration path")
        if re.search(r"volunteer", _mask_non_code(focus_text + (dynamic or "")), re.IGNORECASE):
            issues.append("VAL contract campaign must not use volunteer modifiers")

        if goal_shines is not None:
            used_icons = set(re.findall(r"\bicon\s*=\s*(GFX_goal_generic_[A-Za-z0-9_]+)", focus_text))
            for icon in used_icons:
                shine = f"{icon}_shine"
                expected_texture = f'gfx/interface/goals/{icon.removeprefix("GFX_")}.dds'
                sprite = next(
                    (
                        block
                        for block in _iter_named_blocks(goal_shines, "SpriteType")
                        if re.search(rf'\bname\s*=\s*"{re.escape(shine)}"', block)
                    ),
                    "",
                )
                if not sprite:
                    issues.append(f"VAL focus icon {icon} is missing its shine sprite")
                elif expected_texture not in sprite or "goal_unknown.dds" in sprite:
                    issues.append(f"VAL focus icon {icon} has an invalid shine texture")

    if core is not None:
        refresh = extract_named_block(core, "VAL_refresh_contract_modifier") or ""
        for band in VAL_CONTRACT_BANDS:
            if f"# VAL contract band {band['minimum']}-{band['maximum']}" not in refresh:
                issues.append(f"VAL contract modifier is missing band {band['minimum']}-{band['maximum']}")
        if refresh.count("force_update_dynamic_modifier = yes") != 1:
            issues.append("VAL contract modifier must force-update exactly once per requested refresh")
        for token in (
            "VAL_contract_new_band",
            "VAL_contract_band",
            "compare = equals",
        ):
            if token not in refresh:
                issues.append(f"VAL band-change guard is missing {token}")
        for flag, assignments in VAL_CONTRACT_SPECIALISATIONS.items():
            branch = next(
                (
                    block
                    for block in _iter_named_blocks(refresh, "if")
                    if f"has_country_flag = {flag}" in block
                ),
                "",
            )
            if not branch:
                issues.append(f"VAL contract specialisation is missing flag {flag}")
                continue
            for variable, value in assignments:
                token = f"add_to_variable = {{ var = {variable} value = {value} }}"
                if token not in branch:
                    issues.append(f"VAL contract specialisation {flag} is missing {token}")
        readiness = extract_named_block(core, "VAL_recalculate_stp_campaign_readiness") or ""
        for token in (
            "VAL_STP_final_war_preparation",
            "VAL_STP_leverage_component",
            "value = 0.35",
            "VAL_contract_authority value = 75",
            "VAL_STP_intel_43",
            "VAL_STP_client_garrison",
            "VAL_STP_resource_rights_45",
            "VAL_CIN_influence value = 2",
            "VAL_OSF_influence value = 2",
            "NOD_crisis_posture_guardian",
            "value = 15",
            "clamp_variable = { var = VAL_STP_campaign_readiness min = 0 max = 100 }",
            "VAL_refresh_stp_campaign_plan_modifier = yes",
        ):
            if token not in readiness:
                issues.append(f"VAL campaign-readiness calculation is missing {token}")
        plan = extract_named_block(core, "VAL_refresh_stp_campaign_plan_modifier") or ""
        for threshold in (25, 50, 75):
            if f"VAL_STP_campaign_readiness value = {threshold}" not in plan:
                issues.append(f"VAL campaign plan is missing readiness band {threshold}")
        for token in (
            "VAL_STP_campaign_attack_factor",
            "VAL_STP_campaign_defence_factor",
            "VAL_STP_campaign_planning_factor",
            "VAL_STP_campaign_supply_factor",
            "VAL_STP_final_war_active",
            "modifier = VAL_stelander_campaign_plan",
        ):
            if token not in plan:
                issues.append(f"VAL campaign-plan refresh is missing {token}")

    if dynamic is not None:
        campaign_plan = extract_named_block(dynamic, "VAL_stelander_campaign_plan") or ""
        for token in (
            "has_country_flag = VAL_STP_final_war_active",
            "army_attack_factor = VAL_STP_campaign_attack_factor",
            "army_defence_factor = VAL_STP_campaign_defence_factor",
            "planning_speed = VAL_STP_campaign_planning_factor",
            "supply_consumption_factor = VAL_STP_campaign_supply_factor",
        ):
            if token not in campaign_plan:
                issues.append(f"VAL campaign dynamic modifier is missing {token}")

    if triggers is not None:
        for trigger in (
            "VAL_stp_crisis_at_least_rupture",
            "VAL_has_active_stp_civil_war",
            "VAL_can_negotiate_deferred_invoice",
            "VAL_has_postwar_stp_target",
        ):
            if not extract_named_block(triggers, trigger):
                issues.append(f"missing VAL crisis focus trigger {trigger}")

    if ideas is not None:
        for idea, token in (
            ("VAL_factory_cathedrals_drive", "production_speed_arms_factory_factor = 0.10"),
            ("VAL_hot_production_lines", "production_factory_max_efficiency_factor = 0.03"),
            ("VAL_northern_roads_drive", "production_speed_infrastructure_factor = 0.10"),
        ):
            if token not in (extract_named_block(ideas, idea) or ""):
                issues.append(f"missing or incomplete VAL focus idea {idea}")

    if decisions is None:
        issues.append("missing VAL contract decisions: common/decisions/ADISCORD_VAL_contract_decisions.txt")
    else:
        # Player-facing operations moved to ADISCORD_VAL_rework_decisions.txt.
        # This legacy file may contain service missions only.
        for obsolete_id in (*VAL_STP_OPERATION_SPECS, "VAL_launch_northern_campaign"):
            if extract_named_block(decisions, obsolete_id):
                issues.append(f"obsolete player-facing VAL decision remains: {obsolete_id}")
        for target in VAL_NORTHERN_OPERATION_TARGETS:
            for suffix in VAL_NORTHERN_OPERATION_SPECS:
                obsolete_id = f"VAL_{target}_{suffix}"
                if extract_named_block(decisions, obsolete_id):
                    issues.append(f"obsolete player-facing VAL decision remains: {obsolete_id}")

        for mission_id in WAR_COUNTDOWN_MISSIONS:
            mission = extract_named_block(decisions, mission_id) or ""
            if not mission:
                issues.append(f"missing canonical final-war mission {mission_id}")
                continue
            expected_days = WAR_COUNTDOWN_MISSION_DAYS[mission_id]
            if _direct_scalar_values(mission, "days_mission_timeout") != [str(expected_days)]:
                issues.append(f"{mission_id} must time out after {expected_days} days")
            timeout_type = 14 if mission_id.endswith("breached") else expected_days
            for token in (
                "selectable_mission = no",
                "STP_VAL_resolve_countdown_timeout = yes",
                f"ADISCORD_STP_VAL_timeout_type value = {timeout_type}",
            ):
                if token not in mission:
                    issues.append(f"{mission_id} is missing canonical timeout token {token}")

    if contract_effects is None:
        issues.append("missing contract and northern effects: common/scripted_effects/ADISCORD_STP_VAL_contract_effects.txt")
    else:
        finish = extract_named_block(contract_effects, "VAL_finish_stp_operation") or ""
        for token in (
            "VAL_STP_target_cooldown",
            "days = 42",
            "VAL_recalculate_stp_campaign_readiness = yes",
            "VAL_clear_foreign_operation = yes",
        ):
            if token not in finish:
                issues.append(f"VAL STP resolver cleanup is missing {token}")
        clear = extract_named_block(contract_effects, "VAL_clear_foreign_operation") or ""
        if "VAL_foreign_operation_active" not in clear:
            issues.append("VAL shared foreign slot is never cleared")
        selector = extract_named_block(contract_effects, "VAL_select_negotiation_posture") or ""
        if "value = 0 compare = equals" not in selector:
            issues.append("VAL negotiation posture must be selected only while unset")
        for value in range(1, 5):
            if f"var = VAL_negotiation_posture value = {value}" not in selector:
                issues.append(f"VAL negotiation posture selector cannot reach {value}")
        for family in ("intel", "supply", "concession", "garrison", "nodrul"):
            for token in (
                f"VAL_STP_exposure_{family}",
                f"VAL_STP_block_{family}",
            ):
                if token not in contract_effects:
                    issues.append(f"VAL STP exposure system is missing {token}")
        for target in VAL_NORTHERN_OPERATION_TARGETS:
            resolver = extract_named_block(
                contract_effects, f"VAL_resolve_{target.lower()}_operation"
            ) or ""
            for token in (
                f"VAL_{target}_last_family",
                f"VAL_{target}_repeat_streak",
                "value = 3",
                "days = 90",
                "days = 70",
                f"VAL_{target}_influence",
                "max = 3",
            ):
                if token not in resolver:
                    issues.append(f"VAL {target} northern resolver is missing {token}")
        floor = extract_named_block(core or "", "VAL_recalculate_stp_leverage_floor") or ""
        for token in (
            "VAL_STP_resource_rights_45",
            "VAL_STP_resource_rights_88",
            "VAL_STP_client_garrison",
            "owns_state = 45",
            "owns_state = 88",
            "VAL_STP_leverage_floor",
        ):
            if token not in floor:
                issues.append(f"VAL STP leverage floor is missing {token}")
        for state in ("channel", "viability", "concessions", "offer", "response"):
            if f"VAL_STP_negotiation_state_{state}" not in contract_effects:
                issues.append(f"VAL mountain deal is missing state {state}")
        for flag in VAL_STP_CONCESSION_FLAGS:
            if flag not in contract_effects:
                issues.append(f"VAL mountain deal is missing concession {flag}")
        for countdown in (180, 300, 450):
            wrapper = extract_named_block(
                contract_effects, f"VAL_apply_mountain_contract_{countdown}"
            ) or ""
            for token in (
                f"ADISCORD_STP_VAL_effect_value value = {countdown}",
                "VAL_apply_mountain_contract = yes",
            ):
                if token not in wrapper:
                    issues.append(f"VAL mountain deal cannot select {countdown} days")
        cleanup = extract_named_block(contract_effects, "VAL_STP_cleanup_contract_relations") or ""
        for token in (
            "remove_resource_rights = 45",
            "remove_resource_rights = 88",
            "relation = military_access",
            "civilian_factory_use",
            "VAL_STP_concession_arms_debt",
            "clear_global_event_target = STP_val_contract_partner",
        ):
            search_block = cleanup if token != "civilian_factory_use" else (decisions or "")
            if token not in search_block:
                issues.append(f"VAL contract lifecycle is missing {token}")
        corridor = extract_named_block(contract_effects, "VAL_prepare_resource_corridor") or ""
        for token in (
            "VAL_resource_corridor_attempted",
            "VAL_corridor_owner_45",
            "VAL_corridor_owner_88",
            "generator = { 45 88 }",
        ):
            if token not in corridor:
                issues.append(f"VAL resource corridor is missing {token}")
        corridor_accept = extract_named_block(contract_effects, "VAL_accept_resource_corridor") or ""
        for token in ("controls_state = 45", "controls_state = 88", "transfer_state"):
            if token not in corridor_accept:
                issues.append(f"VAL corridor concession is missing physical-control guard {token}")
        if "on_daily" in _mask_non_code(contract_effects):
            issues.append("VAL contract mechanics must remain event-driven")

        clear_countdown = extract_named_block(contract_effects, "STP_VAL_clear_countdown") or ""
        selector = extract_named_block(contract_effects, "STP_VAL_select_countdown_owner") or ""
        starter = extract_named_block(contract_effects, "STP_VAL_start_canonical_countdown") or ""
        breach = extract_named_block(contract_effects, "STP_VAL_start_breach_countdown") or ""
        final_warning = extract_named_block(contract_effects, "STP_VAL_apply_final_warning") or ""
        protection = extract_named_block(contract_effects, "STP_VAL_remove_diplomatic_protection") or ""
        final_war = extract_named_block(contract_effects, "STP_VAL_begin_final_war") or ""
        final_val = extract_named_block(contract_effects, "STP_VAL_resolve_final_val_victory") or ""
        final_stp = extract_named_block(contract_effects, "STP_VAL_resolve_final_stp_victory") or ""
        for mission_id in WAR_COUNTDOWN_MISSIONS:
            if f"remove_decision = {mission_id}" not in clear_countdown:
                issues.append(f"countdown cleanup does not remove {mission_id}")
        for flag in ("120", "180", "300", "450", "breached"):
            token = f"VAL_STP_countdown_generation_{flag}"
            if token not in clear_countdown or token not in starter + breach:
                issues.append(f"countdown generation token is not finite: {token}")
        for token in (
            "event_target:STP_postwar_country = { is_ai = no }",
            "is_ai = no",
            "save_global_event_target_as = STP_VAL_countdown_owner",
            "VAL_STP_countdown_owner_postwar",
            "VAL_STP_countdown_owner_val",
        ):
            if token not in selector:
                issues.append(f"canonical countdown-owner selector is missing {token}")
        for mission_id, (warning_event, warning_day, d1_event, d1_day) in WAR_COUNTDOWN_WARNING_EVENTS.items():
            if f"activate_mission = {mission_id}" not in starter + breach:
                issues.append(f"canonical starter never activates {mission_id}")
            for event_id, day in ((warning_event, warning_day), (d1_event, d1_day)):
                schedule = f"country_event = {{ id = {event_id}" + (" }" if day == 0 else f" days = {day} }}")
                if schedule not in starter + breach:
                    issues.append(f"{mission_id} is missing scheduled {event_id} at day {day}")
        for token in (
            "VAL_STP_final_warning_active",
            "STP_VAL_expire_countdown_concessions = yes",
        ):
            if token not in final_warning:
                issues.append(f"D-14 warning is missing {token}")
        for token in ("relation = non_aggression_pact", "active = no"):
            if token not in protection:
                issues.append(f"D-1 protection removal is missing {token}")
        if WAR_COUNTDOWN_TRUCE_POLICY != "no_engine_truce":
            issues.append("validator fixture must record the supported no-engine-truce policy")
        if re.search(r"\bset_truce\b|relation\s*=\s*truce", _mask_non_code(contract_effects)):
            issues.append("countdown must not invent an unverified engine-truce removal path")
        if "days = 13" not in breach or "STP_VAL_apply_final_warning = yes" not in breach:
            issues.append("material breach must warn immediately and remove protection on day 13")
        if "has_country_flag = VAL_STP_final_warning_active" not in breach or "STP_VAL_begin_final_war = yes" not in breach:
            issues.append("a post-warning breach must begin the final war immediately")
        declaration_index = final_war.find("declare_war_on")
        for token in (
            "VAL_recalculate_stp_campaign_readiness = yes",
            "VAL_STP_cleanup_contract_relations = yes",
            "VAL_clear_foreign_operation = yes",
            "STP_VAL_clear_countdown = yes",
            "remove_wargoal =",
            "ADISCORD_STP_VAL_effect_value value = 4",
            "STP_set_crisis_phase = yes",
            "VAL_STP_final_war_active",
        ):
            token_index = final_war.find(token)
            if token_index == -1 or declaration_index == -1 or token_index > declaration_index:
                issues.append(f"final-war cleanup must precede declaration: {token}")
        for outcome, autonomy_id in (
            (final_val, "autonomy_contract_client"),
            (final_val, "autonomy_contract_protectorate"),
            (final_stp, "autonomy_free"),
        ):
            if autonomy_id not in outcome:
                issues.append(f"scripted final peace is missing autonomy outcome {autonomy_id}")
        for outcome in (final_val, final_stp):
            if "white_peace" not in outcome:
                issues.append("final VAL-STP outcomes must be scripted peace, not a conference")
        if "VAL_STP_campaign_readiness value = 75" not in final_val:
            issues.append("the contract-client peace requires at least 75 campaign readiness")

    if contract_events is None:
        issues.append("missing VAL contract events: events/ADISCORD_VAL_contract_events.txt")
    else:
        for event_id in ("val_contract.1", "val_contract.2", "val_contract.3", "val_contract.4", "val_contract.5"):
            if not _block_with_direct_assignment(contract_events, "country_event", "id", event_id):
                issues.append(f"missing mountain negotiation event {event_id}")
        for event_id in ("val_contract.300", "val_contract.301", "val_contract.302"):
            block = _block_with_direct_assignment(contract_events, "country_event", "id", event_id) or ""
            if "is_triggered_only = yes" not in block or block.count("option =") < 2:
                issues.append(f"human northern target response is incomplete: {event_id}")
        for mission_id, (warning_event, _, d1_event, _) in WAR_COUNTDOWN_WARNING_EVENTS.items():
            generation = mission_id.removeprefix("STP_VAL_war_countdown_")
            for event_id, required_effect in (
                (warning_event, "STP_VAL_apply_final_warning = yes"),
                (d1_event, "STP_VAL_remove_diplomatic_protection = yes"),
            ):
                block = _block_with_direct_assignment(contract_events, "country_event", "id", event_id) or ""
                if mission_id not in block or f"VAL_STP_countdown_generation_{generation}" not in block:
                    issues.append(f"{event_id} does not recheck {mission_id}'s finite generation")
                if required_effect not in block and event_id != "val_contract.64":
                    issues.append(f"{event_id} is missing {required_effect}")

    if on_actions is not None:
        war_hook = extract_named_block(on_actions, "on_war_relation_added") or ""
        for token in (
            "ROOT = { tag = VAL }",
            "check_variable = { var = STP_crisis_phase value = 2 compare = less_than }",
            "NOD_refresh_army_equipment_ratio = yes",
            "NOD_handle_early_val_aggression = yes",
        ):
            if token not in war_hook:
                issues.append(f"early VAL aggression reaction is missing {token}")
        capitulation = extract_named_block(on_actions, "on_capitulation") or ""
        for token in (
            "VAL_STP_final_war_active",
            "set_global_flag = skip_default_capitulation",
            "STP_VAL_resolve_final_val_victory = yes",
            "STP_VAL_resolve_final_stp_victory = yes",
        ):
            if token not in capitulation:
                issues.append(f"scripted final peace on-action is missing {token}")

    if autonomy is not None:
        for autonomy_id in ("autonomy_contract_client", "autonomy_contract_protectorate"):
            block = _block_with_direct_assignment(autonomy, "autonomy_state", "id", autonomy_id) or ""
            for token in ("is_puppet = yes", "can_not_declare_war = yes", "can_take_level"):
                if token not in block:
                    issues.append(f"special contract subject is incomplete: {autonomy_id} / {token}")


def _validate_nod_contract(root: Path, issues: list[str]) -> None:
    decisions = read(root / "common/decisions/ADISCORD_NOD_crisis_decisions.txt")
    events = read(root / "events/ADISCORD_NOD_crisis_events.txt")
    effects = read(
        root / "common/scripted_effects/ADISCORD_STP_VAL_crisis_war_effects.txt"
    )
    triggers = read(
        root / "common/scripted_triggers/ADISCORD_STP_VAL_crisis_triggers.txt"
    )
    on_actions = read(
        root / "common/on_actions/01_ADISCORD_STP_VAL_crisis_on_actions.txt"
    )
    ideas = read(root / "common/ideas/ADISCORD_STP_VAL_crisis_ideas.txt")
    stp_events = read(root / "events/ADISCORD_STP_crisis_events.txt")

    selector = extract_named_block(effects or "", "NOD_select_crisis_posture") or ""
    for posture in NOD_POSTURES:
        if (
            selector.count(f"clr_country_flag = {posture}") != 1
            or f"set_country_flag = {posture}" not in selector
        ):
            issues.append(f"NOD posture selector must clear and reach {posture}")
    for driver in (
        "has_war",
        "strength_ratio",
        "has_equipment = { infantry_equipment > 1499 }",
        "is_subject_of = NOD",
        "STP_nodrul_shabrat_activity_discovered",
        "STP_nodrul_disinformation_bias",
    ):
        if driver not in selector:
            issues.append(f"NOD posture selector is missing contextual driver {driver}")
    if "NOT = { has_country_flag = NOD_crisis_posture_lock }" not in selector:
        issues.append("NOD posture selector must respect its stage lock")

    if ideas is not None:
        for idea, required_tokens in {
            "STP_nodrul_limited_support": (
                "supply_consumption_factor",
                "planning_speed",
                "land_reinforce_rate",
            ),
            "NOD_ypr_trade_rights": ("production_lack_of_resource_penalty_factor",),
            "NOD_cof_reparations": ("industrial_capacity_factory",),
            "NOD_beshay_trade_concession": ("supply_consumption_factor",),
        }.items():
            block = extract_named_block(ideas, idea) or ""
            if not block:
                issues.append(f"missing temporary NOD crisis idea {idea}")
                continue
            for token in required_tokens:
                if token not in block:
                    issues.append(f"{idea} is missing gameplay modifier {token}")

    if decisions is not None:
        for mission, (_, target, days) in NOD_ESCALATION_MISSIONS.items():
            block = extract_named_block(decisions, mission) or ""
            if _direct_scalar_values(block, "days_mission_timeout") != [str(days)]:
                issues.append(f"{mission} must last exactly {days} days")
            if f"NOD_attempt_limited_war_{target.lower()} = yes" not in block:
                issues.append(f"{mission} must recheck and attempt only {target}")
        for target, days in NOD_LIMITED_TIMEOUT_DAYS.items():
            block = (
                extract_named_block(
                    decisions, f"NOD_limited_war_timeout_{target.lower()}"
                )
                or ""
            )
            if _direct_scalar_values(block, "days_mission_timeout") != [str(days)]:
                issues.append(f"NOD limited war against {target} must time out in {days} days")
        for mission, (target, days, generation) in NOD_CONTROL_MISSIONS.items():
            block = extract_named_block(decisions, mission) or ""
            if _direct_scalar_values(block, "days_mission_timeout") != [str(days)]:
                issues.append(f"{mission} must hold control for {days} days")
            if (
                f"NOD_{target.lower()}_control_generation_{generation}" not in block
            ):
                issues.append(f"{mission} is missing its generation token")
        for decision, (_, _, level) in NOD_SUPPORT_LEVELS.items():
            block = extract_named_block(decisions, decision) or ""
            if f"NOD_send_stp_{level}_support = yes" not in block:
                issues.append(f"{decision} must call its paid support effect")

    if triggers is not None:
        direct = extract_named_block(triggers, "NOD_can_directly_defend_stp") or ""
        nod_scope = extract_named_block(direct, "NOD") or ""
        for token in (
            "country_exists = NOD",
            "NOD_crisis_posture_guardian",
            "has_war = no",
            "has_capitulated = no",
            "NOD_has_85_percent_army_equipment = yes",
            "controls_state = 10",
            "controls_state = 11",
            "tag = ROOT",
            "ratio < 0.8",
        ):
            if token not in direct and token not in nod_scope:
                issues.append(f"target-scoped NOD direct-defence trigger is missing {token}")
        if re.search(r"\btag\s*=\s*NOD\b", _mask_non_code(direct)):
            issues.append("NOD direct-defence trigger must remain callable from STP scope")
        eligibility = {
            "ypr": ((15, 19), "0.9"),
            "cof": ((14,), "1.1"),
            "bhg": ((5,), "1.25"),
            "bbv": ((7,), "1.25"),
        }
        for target, (states, ratio) in eligibility.items():
            block = extract_named_block(triggers, f"NOD_can_escalate_{target}") or ""
            if any(f"controls_state = {state}" not in block for state in states):
                issues.append(f"NOD {target.upper()} eligibility is missing target control")
            if f"ratio < {ratio}" not in block:
                issues.append(f"NOD {target.upper()} eligibility has wrong strength ratio")

    task_six_effect_names = [
        "NOD_clear_limited_conflict_state",
        "NOD_emergency_limited_white_peace",
        "NOD_evaluate_limited_war_losses",
        *(f"NOD_attempt_limited_war_{target}" for target in ("ypr", "cof", "bhg", "bbv")),
        *(f"NOD_apply_{target}_limited_victory" for target in ("ypr", "cof", "bhg", "bbv")),
        *(f"NOD_send_stp_{level}_support" for level in ("material", "limited", "full")),
    ]
    task_six_effects = "\n".join(
        extract_named_block(effects or "", name) or "" for name in task_six_effect_names
    )
    for token in ("transfer_state", "set_state_owner", "add_to_faction", "skip_default_capitulation"):
        if token in _mask_non_code(task_six_effects + (events or "") + (decisions or "")):
            issues.append(f"NOD limited-conflict feature must not use {token}")
    for required in (
        "NOD_limited_war_participant",
        "NOD_limited_war_target",
        "NOD_limited_war_nod",
        "NOD_limited_war_target_country",
        "white_peace",
        "deployed_army_manpower_k",
        "casualties",
        "value = 0.08",
        "value = 1.5",
        "NOD_limited_war_pyrrhic",
        "NOD_change_crisis_attention",
    ):
        if required not in task_six_effects:
            issues.append(f"NOD limited-conflict effects are missing {required}")

    if on_actions is not None:
        for hook in (
            "on_war_relation_added",
            "on_peace",
            "on_capitulation",
            "on_leave_faction",
            "on_annex",
            "on_state_control_changed",
        ):
            block = extract_named_block(on_actions, hook) or ""
            if not re.search(r"NOD_(?:select_crisis_posture|check_limited_war)", block):
                issues.append(f"{hook} is missing event-driven NOD reevaluation/cleanup")

    if stp_events is not None:
        for event_id in ("stp_crisis.1", "stp_crisis.2", "stp_crisis.3", "stp_crisis.4"):
            block = (
                _block_with_direct_assignment(stp_events, "country_event", "id", event_id)
                or ""
            )
            if "NOD_select_crisis_posture = yes" not in block:
                issues.append(f"{event_id} must re-evaluate the NOD posture")
        disinformation = (
            _block_with_direct_assignment(stp_events, "country_event", "id", "stp_crisis.25")
            or ""
        )
        if (
            "STP_nodrul_disinformation_bias" not in disinformation
            or "declare_war_on" in disinformation
        ):
            issues.append("STP disinformation must only bias NOD posture selection")


def _validate_northern_campaign(root: Path, issues: list[str]) -> None:
    triggers = read(root / "common/scripted_triggers/ADISCORD_STP_VAL_crisis_triggers.txt") or ""
    effects = read(root / "common/scripted_effects/ADISCORD_STP_VAL_contract_effects.txt") or ""
    decisions = read(root / "common/decisions/ADISCORD_VAL_contract_decisions.txt") or ""
    events = read(root / "events/ADISCORD_VAL_contract_events.txt") or ""
    on_actions = read(root / "common/on_actions/01_ADISCORD_STP_VAL_crisis_on_actions.txt") or ""
    old_on_actions = read(root / "common/on_actions/00_on_actions.txt") or ""
    test_decisions = read(root / "common/decisions/ADISCORD_test_wars_decisions.txt") or ""
    test_categories = read(root / "common/decisions/categories/ADISCORD_test_wars_categories.txt") or ""
    ideas = read(root / "common/ideas/ADISCORD_STP_VAL_crisis_ideas.txt") or ""

    for trigger_id, target, state in (
        ("VAL_northern_cin_is_eligible", "CIN", NORTHERN_STATES["CIN"]),
        ("VAL_northern_osf_is_eligible", "OSF", NORTHERN_STATES["OSF"]),
    ):
        block = extract_named_block(triggers, trigger_id) or ""
        for token in (
            f"country_exists = {target}",
            "is_subject = no",
            "has_capitulated = no",
            "has_war = no",
            "is_in_faction = no",
            f"owns_state = {state}",
            f"controls_state = {state}",
            f"has_guaranteed = {target}",
            f"VAL_{target}_influence value = 2",
        ):
            if token not in block:
                issues.append(f"{trigger_id} is missing start guard {token}")

    for trigger_id in (
        "VAL_northern_full_mode_is_eligible",
        "VAL_northern_partial_cin_is_eligible",
        "VAL_northern_partial_osf_is_eligible",
    ):
        if not extract_named_block(triggers, trigger_id):
            issues.append(f"missing northern mode trigger {trigger_id}")
    partial_cin = extract_named_block(triggers, "VAL_northern_partial_cin_is_eligible") or ""
    partial_osf = extract_named_block(triggers, "VAL_northern_partial_osf_is_eligible") or ""
    if "VAL_northern_osf_is_eligible = no" not in partial_cin:
        issues.append("partial CIN mode must require OSF to be ineligible")
    if "VAL_northern_cin_is_eligible = no" not in partial_osf:
        issues.append("partial OSF mode must require CIN to be ineligible")

    window = extract_named_block(triggers, "VAL_can_start_northern_campaign") or ""
    for token in (
        "VAL_northern_campaign_attempted",
        "VAL_STP_final_warning_active",
        "VAL_northern_balanced_civil_war_human = yes",
        "VAL_northern_balanced_civil_war_ai = yes",
        "VAL_northern_fresh_long_deal = yes",
        "VAL_STP_countdown_120",
        "VAL_STP_countdown_180",
    ):
        if token not in window:
            issues.append(f"northern start window is missing {token}")
    for trigger_id, surrender in (
        ("VAL_northern_balanced_civil_war_human", "surrender_progress < 0.50"),
        ("VAL_northern_balanced_civil_war_ai", "surrender_progress < 0.35"),
    ):
        block = extract_named_block(triggers, trigger_id) or ""
        if surrender not in block:
            issues.append(f"{trigger_id} is missing exact surrender threshold")
    ai_window = extract_named_block(triggers, "VAL_northern_balanced_civil_war_ai") or ""
    for token in (
        "num_divisions > 5",
        "has_equipment = { infantry_equipment > 1499 }",
        "has_equipment = { support_equipment > 149 }",
    ):
        if token not in ai_window:
            issues.append(f"northern AI reserve gate is missing {token}")

    mission = extract_named_block(decisions, "VAL_northern_campaign_timeout_210") or ""
    if _direct_scalar_values(mission, "days_mission_timeout") != ["210"]:
        issues.append("northern campaign must use one 210-day mission")
    if extract_named_block(decisions, "VAL_launch_northern_campaign"):
        issues.append("obsolete northern start decision remains player-facing")

    start = extract_named_block(effects, "VAL_start_guarded_northern_campaign") or ""
    attempted_index = start.find("set_country_flag = VAL_northern_campaign_attempted")
    declaration_index = start.find("declare_war_on")
    if attempted_index == -1 or declaration_index == -1 or attempted_index > declaration_index:
        issues.append("northern attempted flag must be permanent and set before declaration")
    for mode in NORTHERN_MODES:
        if mode not in start:
            issues.append(f"northern start effect cannot reach mode {mode}")
    for token in (
        "VAL_northern_owner_59",
        "VAL_northern_owner_61",
        "VAL_northern_cin_participant",
        "VAL_northern_osf_participant",
        "generator = { 59 }",
        "generator = { 61 }",
        "activate_mission = VAL_northern_campaign_timeout_210",
    ):
        if token not in start:
            issues.append(f"northern start effect is missing {token}")
    if re.search(r"declare_war_on\s*=\s*\{[^}]*target\s*=\s*APH", _mask_non_code(start), re.DOTALL):
        issues.append("APH must never enter the northern war automatically")
    if "create_faction" in _mask_non_code(start):
        issues.append("northern campaign must not create a permanent faction")

    scheduler = extract_named_block(effects, "VAL_check_northern_campaign_control") or ""
    for event_id, state in (("val_contract.400", 59), ("val_contract.401", 61)):
        if f"controls_state = {state}" not in scheduler or f"id = {event_id} days = 30" not in scheduler:
            issues.append(f"state {state} lacks its finite 30-day control token")
    for event_id, resolver in (
        ("val_contract.400", "VAL_resolve_northern_control_59 = yes"),
        ("val_contract.401", "VAL_resolve_northern_control_61 = yes"),
    ):
        block = _block_with_direct_assignment(events, "country_event", "id", event_id) or ""
        if resolver not in block:
            issues.append(f"northern control event {event_id} is missing {resolver}")

    for state, lock in zip((59, 61), NORTHERN_TARGET_LOCKS):
        accept = extract_named_block(effects, f"VAL_accept_northern_{state}_concession") or ""
        for token in (
            f"VAL_northern_owner_{state}",
            "VAL_northern_campaign_participant",
            "VAL_northern_campaign_contaminated",
            f"controls_state = {state}",
            f"NOT = {{ has_country_flag = {lock} }}",
            f"transfer_state = {state}",
            f"set_country_flag = {lock}",
            "white_peace",
        ):
            if token not in accept:
                issues.append(f"guarded northern transfer {state} is missing {token}")

    timeout = extract_named_block(effects, "VAL_resolve_northern_campaign_timeout") or ""
    cleanup = extract_named_block(effects, "VAL_clear_active_northern_campaign") or ""
    for token in ("VAL_address_northern_white_peace = yes", "VAL_clear_active_northern_campaign = yes"):
        if token not in timeout:
            issues.append(f"northern timeout is missing {token}")
    if "clr_country_flag = VAL_northern_campaign_attempted" in cleanup:
        issues.append("northern cleanup must preserve the permanent attempted flag")

    war_hook = extract_named_block(on_actions, "on_war_relation_added") or ""
    for token in ("VAL_northern_campaign_participant", "VAL_mark_northern_campaign_contaminated = yes"):
        if token not in war_hook:
            issues.append(f"northern contamination hook is missing {token}")
    capitulation = extract_named_block(on_actions, "on_capitulation") or ""
    for token in (
        "VAL_northern_capitulated_country",
        "set_global_flag = skip_default_capitulation",
        "VAL_handle_northern_campaign_capitulation = yes",
    ):
        if token not in capitulation:
            issues.append(f"northern scripted capitulation is missing {token}")

    collision = extract_named_block(effects, "STP_VAL_handle_northern_timer_collision") or ""
    for token in ("is_ai = no", "val_contract.430", "ratio < 1.5", "VAL_continue_northern_two_front_war"):
        if token not in collision:
            issues.append(f"northern timer collision is missing {token}")
    idea = extract_named_block(ideas, "VAL_northern_two_front_overstretch") or ""
    for token in ("supply_consumption_factor = 0.15", "planning_speed = -0.10"):
        if token not in idea:
            issues.append(f"northern overstretch idea is missing {token}")

    for forbidden in (
        "VAL scripted test war",
        "transfer_state = 59",
        "transfer_state = 61",
        "ADISCORD_test_capitulation_resistance",
    ):
        if forbidden in old_on_actions:
            issues.append(f"old unsafe northern capitulation handler remains: {forbidden}")
    for forbidden in ("VAL_start_test_war_with_STP", "VAL_start_test_war_with_CIN"):
        if forbidden in test_decisions + test_categories:
            issues.append(f"superseded VAL test-war decision remains: {forbidden}")

    localisation_path = root / "localisation/russian/ADISCORD_test_wars_l_russian.yml"
    if localisation_path.exists():
        raw = localisation_path.read_bytes()
        if not raw.startswith(b"\xef\xbb\xbf"):
            issues.append("ADISCORD_test_wars_l_russian.yml must retain its UTF-8 BOM")
        text = raw.decode("utf-8-sig")
        if text.count("l_russian:") != 1:
            issues.append("ADISCORD_test_wars_l_russian.yml must have exactly one header")


def _validate_ai_contract(root: Path, issues: list[str]) -> None:
    strategy = read(root / "common/ai_strategy/ADISCORD_STP_VAL_crisis_ai.txt") or ""
    triggers = read(
        root / "common/scripted_triggers/ADISCORD_STP_VAL_crisis_triggers.txt"
    ) or ""
    stp_decisions = read(
        root / "common/decisions/ADISCORD_STP_crisis_decisions.txt"
    ) or ""
    val_decisions = read(
        root / "common/decisions/ADISCORD_VAL_rework_decisions.txt"
    ) or ""
    nod_decisions = read(
        root / "common/decisions/ADISCORD_NOD_crisis_decisions.txt"
    ) or ""
    stp_events = read(root / "events/ADISCORD_STP_crisis_events.txt") or ""
    val_events = read(root / "events/ADISCORD_VAL_contract_events.txt") or ""
    nod_events = read(root / "events/ADISCORD_NOD_crisis_events.txt") or ""

    course_blocks = {
        "STP_AI_CAUTIOUS_SHABRAT": "STP_ai_course_cautious_shabrat",
        "STP_AI_MILITARY_INFILTRATION": "STP_ai_course_military_infiltration",
        "STP_AI_MASS_MOVEMENT": "STP_ai_course_mass_movement",
        "STP_AI_CONTROLLED_PARTY": "STP_ai_course_controlled_party",
        "STP_AI_PURGE_PARTY": "STP_ai_course_purge_party",
        "VAL_AI_CONTRACT_BROKER": "VAL_ai_course_contract_broker",
        "VAL_AI_RESOURCE_RAIDER": "VAL_ai_course_resource_raider",
        "VAL_AI_PATIENT_INVADER": "VAL_ai_course_patient_invader",
        "VAL_AI_NORTHERN_BROKER": "VAL_ai_course_northern_broker",
        "NOD_AI_GUARDIAN": "NOD_crisis_posture_guardian",
        "NOD_AI_YPR": "NOD_crisis_posture_ypr",
        "NOD_AI_COF": "NOD_crisis_posture_cof",
        "NOD_AI_WAIT": "NOD_crisis_posture_wait",
    }
    for block_id, course_flag in course_blocks.items():
        block = extract_named_block(strategy, block_id) or ""
        enable = extract_named_block(block, "enable") or ""
        if f"has_country_flag = {course_flag}" not in enable:
            issues.append(f"AI course {block_id} is not enabled by {course_flag}")
        if "abort_when_not_enabled = yes" not in block:
            issues.append(f"AI course {block_id} must abort when its posture changes")

    for block_id in ("NOD_AI_BESHAY_BHG", "NOD_AI_BESHAY_BBV"):
        block = extract_named_block(strategy, block_id) or ""
        if "has_country_flag = NOD_crisis_posture_beshay" not in block:
            issues.append(f"AI course {block_id} must belong to the Beshay posture")
        if "abort_when_not_enabled = yes" not in block:
            issues.append(f"AI course {block_id} must abort when its target changes")

    masked_strategy = _mask_non_code(strategy)
    if re.search(r"\badd_ai_strategy\b", masked_strategy):
        issues.append("crisis AI must use self-removing static strategies, not add_ai_strategy")
    if re.search(r"\bcall_allies\s*=\s*-9999\b", masked_strategy):
        issues.append("limited-war ally suppression uses an invalid literal field")
    if masked_strategy.count("target = call_allies") != 4:
        issues.append("each Nodrul limited-war opponent needs addressed call-allies suppression")
    for target in ("YPR", "COF", "BHG", "BBV"):
        block = extract_named_block(strategy, f"NOD_AI_LIMITED_WAR_{target}") or ""
        if f"id = {target} target = call_allies value = -9999" not in " ".join(block.split()):
            issues.append(f"call-allies suppression is missing literal target {target}")

    for block_id in (
        "VAL_AI_CONTRACT_BROKER",
        "VAL_AI_RESOURCE_RAIDER",
        "VAL_AI_PATIENT_INVADER",
        "VAL_AI_NORTHERN_BROKER",
    ):
        block = extract_named_block(strategy, block_id) or ""
        if re.search(r"\btype\s*=\s*(?:conquer|prepare_for_war)\b", _mask_non_code(block)):
            issues.append(f"{block_id} creates an illicit early VAL war strategy")

    reserve_tokens = {
        "STP_ai_has_current_course_reserve": (
            "has_political_power > 59.99", "command_power > 14.9",
            "has_equipment = { infantry_equipment > 399 }",
            "has_political_power > 39.99", "command_power > 29.9",
            "has_equipment = { infantry_equipment > 1199 }", "STP_ai_army_equipment_above_70",
        ),
        "VAL_ai_has_current_course_reserve": (
            "has_political_power > 59.99", "command_power > 19.9",
            "has_equipment = { infantry_equipment > 1499 }",
            "has_political_power > 74.99", "command_power > 39.9",
            "has_equipment = { infantry_equipment > 1999 }",
            "event_target:STP_crisis_party_side = { num_divisions > 2 }",
            "event_target:STP_crisis_resistance_side = { num_divisions > 2 }",
        ),
        "NOD_ai_has_current_course_reserve": (
            "has_political_power > 74.99", "command_power > 29.9",
            "has_equipment = { infantry_equipment > 1499 }",
            "has_political_power > 34.99", "command_power > 9.9",
            "has_equipment = { infantry_equipment > 1199 }",
        ),
    }
    for trigger_id, tokens in reserve_tokens.items():
        block = extract_named_block(triggers, trigger_id) or ""
        for token in tokens:
            if token not in block:
                issues.append(f"AI reserve {trigger_id} is missing {token}")

    for decision_id in (
        "STP_operation_palace_channel",
        "STP_operation_recruit_young_officers",
        "STP_operation_mountain_caches",
        "STP_operation_steal_black_ledger",
        "STP_operation_silent_march",
        "STP_operation_nodrul_disinformation",
        "STP_operation_nodrul_disinformation_convoys",
        "STP_operation_val_secret_channel",
        "STP_operation_seal_palace",
        "STP_operation_rotate_garrisons",
        "STP_operation_targeted_raid",
        "STP_operation_burn_client_archives",
        "STP_operation_arm_festival_police",
        "STP_operation_request_nodrul_advisers",
        "STP_operation_false_val_channel",
    ):
        block = extract_named_block(stp_decisions, decision_id) or ""
        ai = extract_named_block(block, "ai_will_do") or ""
        if "factor = 0" not in ai or "STP_ai_has_current_course_reserve = yes" not in ai:
            issues.append(f"{decision_id} can spend below its AI course reserve")

    for decision_id in (
        "VAL_ops_bribe_stelander_brokers",
        "VAL_ops_arm_stelander_clients",
        "VAL_ops_finance_cin_contacts",
        "VAL_ops_sell_rifles_to_cin",
        "VAL_ops_finance_osf_contacts",
        "VAL_ops_sell_rifles_to_osf",
        "VAL_ops_secure_stelander_steel",
        "VAL_pay_quarterly_contract_norm",
    ):
        block = extract_named_block(val_decisions, decision_id) or ""
        ai = extract_named_block(block, "ai_will_do") or ""
        if "factor = 0" not in ai:
            issues.append(f"{decision_id} can spend below its AI course reserve")

    for decision_id in (
        "NOD_support_stp_material",
        "NOD_support_stp_limited",
        "NOD_support_stp_full",
    ):
        block = extract_named_block(nod_decisions, decision_id) or ""
        ai = extract_named_block(block, "ai_will_do") or ""
        if "factor = 0" not in ai or "NOD_ai_has_current_course_reserve = yes" not in ai:
            issues.append(f"{decision_id} can spend below its AI course reserve")

    stp_selector = _block_with_direct_assignment(
        stp_events, "country_event", "id", "stp_crisis.900"
    ) or ""
    val_selector = _block_with_direct_assignment(
        val_events, "country_event", "id", "val_contract.900"
    ) or ""
    for label, block, lock in (
        ("STP", stp_selector, "STP_ai_course_lock"),
        ("VAL", val_selector, "VAL_ai_course_lock"),
    ):
        if f"flag = {lock} days = 70" not in " ".join(block.split()):
            issues.append(f"{label} AI course selector must lock its choice for 70 days")

    for token in (
        "VAL_STP_concession_count",
        "NOD_crisis_posture_guardian",
        "VAL_ai_has_current_course_reserve = yes",
        "surrender_progress",
        "has_equipment = { infantry_equipment > 1999 }",
    ):
        if token not in val_events:
            issues.append(f"VAL deal score is missing adaptive factor {token}")
    for token in ("surrender_progress", "NOD_ai_has_current_course_reserve = yes"):
        if token not in nod_events:
            issues.append(f"Nodrul concession AI is missing adaptive factor {token}")


def _validate_scripted_peace_contract(root: Path, issues: list[str]) -> None:
    on_actions = read(
        root / "common/on_actions/01_ADISCORD_STP_VAL_crisis_on_actions.txt"
    ) or ""
    internal = read(
        root / "common/scripted_effects/ADISCORD_STP_VAL_crisis_war_effects.txt"
    ) or ""
    contracts = read(
        root / "common/scripted_effects/ADISCORD_STP_VAL_contract_effects.txt"
    ) or ""
    autonomy = read(
        root / "common/autonomous_states/ADISCORD_contract_clients.txt"
    ) or ""

    capitulation = extract_named_block(on_actions, "on_capitulation") or ""
    for token in (
        "NOD_resolve_limited_target_capitulation = yes",
        "NOD_emergency_limited_white_peace = yes",
        "VAL_resolve_resource_corridor_concession = yes",
        "VAL_resolve_resource_corridor_defeat = yes",
        "STP_VAL_resolve_early_val_victory = yes",
        "STP_VAL_resolve_early_stp_victory = yes",
        "STP_resolve_scripted_internal_victory = yes",
        "STP_VAL_resolve_final_val_victory = yes",
        "STP_VAL_resolve_final_stp_victory = yes",
        "VAL_handle_northern_campaign_capitulation = yes",
    ):
        if token not in capitulation:
            issues.append(f"scripted capitulation router is missing {token}")
    if capitulation.count("set_global_flag = skip_default_capitulation") < 9:
        issues.append("every crisis capitulation branch must claim scripted peace")

    for token in (
        "STP_resolve_scripted_internal_victory = {",
        "white_peace = { tag = event_target:STP_internal_capitulated_side }",
        "annex_country = {",
        "NOD_addressed_limited_white_peace = {",
        "NOD_resolve_limited_target_capitulation = {",
    ):
        if token not in internal:
            issues.append(f"internal or Nodrul scripted peace is missing {token}")

    for token in (
        "VAL_address_resource_corridor_white_peace = {",
        "VAL_clear_resource_corridor_state = {",
        "VAL_check_resource_corridor_integrity = {",
        "STP_VAL_address_early_aggression_peace = {",
        "STP_VAL_resolve_early_val_victory = {",
        "STP_VAL_resolve_early_stp_victory = {",
        "VAL_address_northern_white_peace = {",
    ):
        if token not in contracts:
            issues.append(f"Kefreyt scripted peace is missing {token}")

    for resolver in (
        "STP_VAL_resolve_final_val_victory",
        "STP_VAL_resolve_final_stp_victory",
    ):
        block = extract_named_block(contracts, resolver) or ""
        if "white_peace = { tag = event_target:STP_postwar_country }" not in block:
            issues.append(f"final-war resolver {resolver} must close the exact war by script")

    for autonomy_id in (
        "autonomy_contract_protectorate",
        "autonomy_contract_client",
    ):
        if not re.search(rf"\bid\s*=\s*{re.escape(autonomy_id)}\b", autonomy):
            issues.append(f"missing special contract subject level {autonomy_id}")


CRISIS_GUI_GETTERS = (
    "STPGetReadinessBand",
    "STPGetSuspicionBand",
    "STPGetNODAssessment",
    "STPGetVALAssessment",
    "STPGetActiveMajorOperation",
    "STPGetActiveAuxOperation",
    "STPGetObservedCountermeasure",
    "STPGetBloodlessOutcomeIntel",
    "STPGetShabratWarOutcomeIntel",
    "STPGetSotnikovOutcomeIntel",
    "STPGetPartyOutcomeIntel",
    "VALGetContractAuthorityBand",
    "VALGetSTPCrisisPhase",
    "VALGetNODAssessment",
    "VALGetCINInfluence",
    "VALGetOSFInfluence",
    "VALGetAPHInfluence",
    "VALGetState45Status",
    "VALGetState88Status",
    "VALGetDealStatus",
    "VALGetCountdownStatus",
    "VALGetForeignOperationStatus",
    "VALGetWarConcept",
)


def _png_dimensions(path: Path) -> tuple[int, int] | None:
    try:
        with path.open("rb") as stream:
            if stream.read(8) != b"\x89PNG\r\n\x1a\n":
                return None
            if stream.read(4) != b"\x00\x00\x00\r" or stream.read(4) != b"IHDR":
                return None
            return struct.unpack(">II", stream.read(8))
    except FileNotFoundError:
        return None


def _dds_dimensions(path: Path) -> tuple[int, int] | None:
    try:
        with path.open("rb") as stream:
            if stream.read(4) != b"DDS ":
                return None
            header = stream.read(124)
            if len(header) != 124 or struct.unpack_from("<I", header, 0)[0] != 124:
                return None
            height = struct.unpack_from("<I", header, 8)[0]
            width = struct.unpack_from("<I", header, 12)[0]
            return width, height
    except FileNotFoundError:
        return None


def _localisation_index(root: Path) -> dict[str, list[str]]:
    index: dict[str, list[str]] = {}
    for path in sorted((root / "localisation/russian").glob("*.yml")):
        text = read(path) or ""
        for match in re.finditer(r"^\s*([A-Za-z0-9_.-]+):(?:\d+)?\s", text, re.MULTILINE):
            index.setdefault(match.group(1), []).append(path.name)
    return index


def _validate_gui_contract(root: Path, issues: list[str]) -> None:
    categories = read(root / "common/decisions/categories/ADISCORD_STP_VAL_crisis_categories.txt") or ""
    scripted = read(root / "common/scripted_guis/ADISCORD_STP_VAL_crisis_scripted_gui.txt") or ""
    gui = read(root / "interface/ADISCORD_STP_VAL_crisis.gui") or ""
    scripted_loc = read(root / "common/scripted_localisation/ADISCORD_STP_VAL_crisis_scripted_loc.txt") or ""

    def block_with_quoted_name(text: str, block_type: str, name: str) -> str:
        for block in _iter_named_blocks(text, block_type):
            if re.search(rf'\bname\s*=\s*"{re.escape(name)}"', block):
                return block
        return ""

    def defined_text_block(name: str) -> str:
        for block in _iter_named_blocks(scripted_loc, "defined_text"):
            if re.search(rf"\bname\s*=\s*{re.escape(name)}\b", block):
                return block
        return ""

    legacy_category = extract_named_block(categories, "VAL_contract_campaign") or ""
    for token in ("tag = VAL", "visible = { always = no }"):
        if token not in " ".join(legacy_category.split()):
            issues.append(f"retired VAL category is missing compatibility guard {token}")
    for forbidden in ("visible_when_empty", "scripted_gui"):
        if forbidden in legacy_category:
            issues.append(f"retired VAL category still exposes obsolete GUI token {forbidden}")
    if scripted or gui:
        issues.append("retired VAL crisis panel files still exist")

    combined = "\n".join((scripted, gui))
    for forbidden in (
        "effects =",
        "buttonType",
        "_click",
        "set_variable",
        "add_to_variable",
        "set_country_flag",
        "clr_country_flag",
        "original_tag = STP",
        "scrollbarType",
        "gridBoxType",
    ):
        if forbidden in combined:
            issues.append(f"read-only crisis GUI contains forbidden mutation or nested list token {forbidden}")
    if "STP_security_posture" in combined or "success_chance" in combined:
        issues.append("STP crisis panel exposes hidden security posture or exact success chance")

    gui_names = re.findall(r'\bname\s*=\s*"([A-Za-z0-9_]+)"', gui)
    duplicates = sorted({name for name in gui_names if gui_names.count(name) > 1})
    for name in duplicates:
        issues.append(f"crisis GUI object name is duplicated: {name}")

    all_defined_names: dict[str, list[str]] = {}
    for path in sorted((root / "common/scripted_localisation").glob("*.txt")):
        text = read(path) or ""
        for name in re.findall(r"\bname\s*=\s*([A-Za-z0-9_]+)", text):
            all_defined_names.setdefault(name, []).append(path.name)
    for getter in CRISIS_GUI_GETTERS:
        if len(all_defined_names.get(getter, ())) != 1:
            issues.append(f"scripted localisation getter {getter} must be defined exactly once")
        block = defined_text_block(getter)
        if "always = yes" not in block:
            issues.append(f"scripted localisation getter {getter} lacks an always fallback")

    for getter in (
        "STPGetReadinessBand",
        "STPGetSuspicionBand",
        "VALGetContractAuthorityBand",
        "VALGetCINInfluence",
        "VALGetOSFInfluence",
        "VALGetAPHInfluence",
    ):
        block = defined_text_block(getter)
        thresholds = [int(value) for value in re.findall(
            r"value\s*=\s*(\d+)\s+compare\s*=\s*greater_than_or_equals", block
        )]
        if thresholds != sorted(thresholds, reverse=True):
            issues.append(f"scripted localisation getter {getter} thresholds are not descending")

    crisis_russian = read(root / "localisation/russian/ADISCORD_STP_VAL_crisis_l_russian.yml") or ""
    for getter in CRISIS_GUI_GETTERS:
        if f"[{getter}]" not in crisis_russian:
            issues.append(f"crisis GUI does not render getter {getter}")
    for token in (
        "[?STP_resistance_readiness|0]%",
        "[?STP_party_suspicion|0]%",
        "[?VAL_contract_authority|0]%",
        "[?VAL_STP_campaign_readiness|0]%",
    ):
        if token not in crisis_russian:
            issues.append(f"crisis GUI percentage must use whole-number literal formatting: {token}")

    texture_files = (
        "interface/ADISCORD_STP_VAL_crisis.gfx",
        "interface/ADISCORD_bop.gfx",
        "interface/ADISCORD_stp_state_face.gfx",
        "interface/ADISCORD_leader_portraits.gfx",
    )
    for relative in texture_files:
        text = read(root / relative) or ""
        for texture in re.findall(r'\btexturefile\s*=\s*"([^\"]+)"', text, re.IGNORECASE):
            texture_path = root / texture.replace("/", "\\")
            if not texture_path.is_file():
                issues.append(f"missing GUI texture referenced by {relative}: {texture}")

    dead_strip = "gfx/leaders/STP/ivanov_glitch_animation.dds"
    if _dds_dimensions(root / dead_strip) != (8112, 210):
        issues.append("Ivanov death animation must be a 48-frame 169 by 210 DDS strip")
    state_face_gfx = read(root / "interface/ADISCORD_stp_state_face.gfx") or ""
    leader_gfx = read(root / "interface/ADISCORD_leader_portraits.gfx") or ""
    inlay = read(
        root / "common/focus_inlay_windows/ADISCORD_STP_state_face_inlay_window.txt"
    ) or ""
    for relative, text, sprite in (
        ("interface/ADISCORD_stp_state_face.gfx", state_face_gfx, "GFX_STP_state_face_dead"),
        (
            "interface/ADISCORD_leader_portraits.gfx",
            leader_gfx,
            "GFX_portrait_STP_Petr_Ivanov_animated",
        ),
    ):
        for token in (
            "frameAnimatedSpriteType",
            f'name = "{sprite}"',
            f'texturefile = "{dead_strip}"',
            "noOfFrames = 48",
            "animation_rate_fps = 12",
            "looping = yes",
            "play_on_show = yes",
        ):
            if token not in text:
                issues.append(f"Ivanov death animation is missing {token} in {relative}")
    if not re.search(
        r"GFX_STP_state_face_dead\s*=\s*\{\s*has_country_flag\s*=\s*STP_ivanov_dead\s*\}",
        _mask_non_code(inlay),
    ):
        issues.append("state-face inlay must select the animated portrait only after Ivanov dies")
    elif inlay.index("GFX_STP_state_face_dead") > inlay.index("GFX_STP_state_face_stage_5"):
        issues.append("animated death portrait must take priority over the static terminal face")

    for path in (
        "gfx/interface/ideas/STP/idea_STP_deadman_rulling_the_country.png",
        "gfx/interface/ideas/STP/idea_STP_National_Strikes.png",
        "gfx/interface/ideas/STP/idea_STP_hidden_slaves_trade.png",
        "gfx/interface/ideas/VAL/idea_VAL_mercenary_state.png",
    ):
        if _png_dimensions(root / path) != (68, 68):
            issues.append(f"crisis spirit icon must be 68 by 68: {path}")
    for path in (
        "gfx/interface/bop/STP_bop_less_hedonism_Shabrat.png",
        "gfx/interface/bop/STP_bop_less_hedonism_Sotnikov.png",
        "gfx/interface/bop/STP_bop_more_hedonism_Hedersett.png",
        "gfx/interface/bop/STP_bop_more_hedonism_Rober.png",
    ):
        if _png_dimensions(root / path) != (78, 88):
            issues.append(f"crisis outcome card must be 78 by 88: {path}")
    for path in (
        "gfx/leaders/STP/portrait_STP_Maksim_Shabrat.png",
        "gfx/leaders/STP/portrait_STP_Grigory_Sotnikov.png",
        "gfx/leaders/STP/portrait_STP_Rufus_Hedersett.png",
    ):
        if _png_dimensions(root / path) != (156, 210):
            issues.append(f"STP successor portrait must be 156 by 210: {path}")


def _validate_localisation_contract(root: Path, issues: list[str]) -> None:
    crisis_path = root / "localisation/russian/ADISCORD_STP_VAL_crisis_l_russian.yml"
    if not crisis_path.exists():
        return
    raw = crisis_path.read_bytes()
    if not raw.startswith(b"\xef\xbb\xbf"):
        issues.append("Russian crisis localisation must use a UTF-8 BOM")
    crisis_loc = read(crisis_path) or ""
    if len(re.findall(r"^l_russian:\s*$", crisis_loc, re.MULTILINE)) != 1:
        issues.append("Russian crisis localisation must contain exactly one l_russian header")

    changed_russian = (
        "localisation/russian/ADISCORD_STP_VAL_crisis_l_russian.yml",
        "localisation/russian/ADISCORD_stp_state_face_l_russian.yml",
        "localisation/russian/ADISCORD_STP_party_elections_l_russian.yml",
        "localisation/russian/ADISCORD_national_focuses_l_russian.yml",
        "localisation/russian/nsb_characters_l_russian.yml",
    )
    for relative in changed_russian:
        path = root / relative
        if path.exists() and not path.read_bytes().startswith(b"\xef\xbb\xbf"):
            issues.append(f"{relative}: changed Russian localisation must retain UTF-8 BOM")

    if "Голос площади" in (read(root / "localisation/russian/ADISCORD_stp_state_face_l_russian.yml") or ""):
        issues.append("STP health presentation retains obsolete Voice of the Square language")

    localisation = _localisation_index(root)
    crisis_keys = [
        key
        for key in re.findall(r"^\s*([A-Za-z0-9_.-]+):(?:\d+)?\s", crisis_loc, re.MULTILINE)
        if key != "l_russian"
    ]
    for key in sorted(set(crisis_keys)):
        paths = localisation.get(key, [])
        if len(paths) != 1:
            issues.append(f"crisis localisation key is duplicated: {key} in {', '.join(paths)}")

    required: set[str] = set()
    gui = read(root / "interface/ADISCORD_STP_VAL_crisis.gui") or ""
    required.update(re.findall(r'\b(?:text|pdx_tooltip)\s*=\s*"([A-Za-z0-9_.-]+)"', gui))
    scripted_loc = read(root / "common/scripted_localisation/ADISCORD_STP_VAL_crisis_scripted_loc.txt") or ""
    required.update(re.findall(r"\blocalization_key\s*=\s*([A-Za-z0-9_.-]+)", scripted_loc))

    for relative in (
        "common/national_focus/ADISCORD_national_focus_STP.txt",
        "common/national_focus/ADISCORD_national_focus_STP_crisis_war.txt",
        "common/national_focus/ADISCORD_national_focus_STP_postwar.txt",
        "common/national_focus/ADISCORD_national_focus_VAL.txt",
    ):
        text = read(root / relative) or ""
        for block in _iter_named_blocks(text, "focus"):
            values = _direct_scalar_values(block, "id")
            if values and values[0].startswith(("STP_", "VAL_")):
                required.add(values[0])
                required.add(f"{values[0]}_desc")

    for relative in (
        "common/decisions/ADISCORD_STP_crisis_decisions.txt",
        "common/decisions/ADISCORD_VAL_contract_decisions.txt",
        "common/decisions/ADISCORD_NOD_crisis_decisions.txt",
    ):
        text = read(root / relative) or ""
        for decision_id in re.findall(r"^\t([A-Z][A-Za-z0-9_]+)\s*=\s*\{", text, re.MULTILINE):
            required.add(decision_id)
            required.add(f"{decision_id}_desc")

    for relative in (
        "events/ADISCORD_STP_crisis_events.txt",
        "events/ADISCORD_VAL_contract_events.txt",
        "events/ADISCORD_NOD_crisis_events.txt",
    ):
        text = read(root / relative) or ""
        required.update(re.findall(r"\b(?:title|desc|text|name)\s*=\s*((?:stp_crisis|val_contract|nod_crisis)\.[A-Za-z0-9_.]+)", text))

    for relative in (
        "common/dynamic_modifiers/ADISCORD_STP_VAL_crisis_dynamic_modifiers.txt",
        "common/ideas/ADISCORD_STP_VAL_crisis_ideas.txt",
    ):
        text = read(root / relative) or ""
        for identifier in re.findall(r"^(?:\t+)?((?:STP|VAL|NOD)_[A-Za-z0-9_]+)\s*=\s*\{", text, re.MULTILINE):
            required.add(identifier)
            required.add(f"{identifier}_desc")
    autonomy = read(root / "common/autonomous_states/ADISCORD_contract_clients.txt") or ""
    for identifier in re.findall(r"\bid\s*=\s*(autonomy_contract_[A-Za-z0-9_]+)", autonomy):
        required.add(identifier)
        required.add(f"{identifier}_desc")

    for key in sorted(required):
        if key not in localisation:
            issues.append(f"missing Russian crisis localisation key {key}")


def _validate_legacy_integration(root: Path, issues: list[str]) -> None:
    """Guard save compatibility, cleanup, and cross-file references."""
    legacy_events_path = root / "events/ADISCORD_events_STP.txt"
    if not legacy_events_path.exists():
        return

    legacy_events = read(legacy_events_path) or ""
    for event_id in ("stp.1", "stp.2"):
        block = _block_with_direct_assignment(
            legacy_events, "country_event", "id", event_id
        ) or ""
        for token in (
            "hidden = yes",
            "is_triggered_only = yes",
            "tag = STP",
            "has_country_flag = STP_main_campaign_side",
            "country_event = { id = stp_crisis.6 }",
        ):
            if token not in block:
                issues.append(f"legacy event {event_id} is not a safe crisis forwarder")
        for forbidden in (
            "complete_national_focus",
            "set_variable",
            "add_to_variable",
            "add_power_balance_value",
        ):
            if forbidden in _mask_non_code(block):
                issues.append(f"legacy event {event_id} retains obsolete mutation {forbidden}")

    old_decisions = read(root / "common/decisions/ADISCORD_decisions_STP.txt") or ""
    for decision_id in (
        "STP_add_left_bop_debug_decision",
        "STP_add_right_bop_debug_decision",
    ):
        block = extract_named_block(old_decisions, decision_id) or ""
        visible = extract_named_block(block, "visible") or ""
        available = extract_named_block(block, "available") or ""
        complete = extract_named_block(block, "complete_effect") or ""
        if "always = no" not in visible or "always = no" not in available:
            issues.append(f"legacy debug decision {decision_id} must remain invisible and inert")
        if re.sub(r"\s+", "", _mask_non_code(complete)) != "{}":
            issues.append(f"legacy debug decision {decision_id} has a non-empty effect")
        if "original_tag" in block or "add_power_balance_value" in block:
            issues.append(f"legacy debug decision {decision_id} can still mutate the old BOP")
    old_category = read(
        root / "common/decisions/categories/ADISCORD_decision_categories_STP.txt"
    ) or ""
    category = extract_named_block(old_category, "STP_balance_of_power_category") or ""
    if "always = no" not in (extract_named_block(category, "visible") or ""):
        issues.append("legacy STP balance-of-power category must remain hidden")

    scripted_loc_files = sorted((root / "common/scripted_localisation").glob("*.txt"))
    support_definitions: list[tuple[Path, str]] = []
    for path in scripted_loc_files:
        text = read(path) or ""
        for block in _iter_named_blocks(text, "defined_text"):
            if _direct_scalar_values(block, "name") == ["WhoTFDoWeSupportLeader"]:
                support_definitions.append((path, block))
    if len(support_definitions) != 1:
        issues.append("WhoTFDoWeSupportLeader must be defined exactly once")
    else:
        path, block = support_definitions[0]
        if "tag = STP" not in block or "STP_main_campaign_side" not in block:
            issues.append(f"{path.name}: leader support getter lacks current-role gating")
        if "original_tag = STP" in block:
            issues.append(f"{path.name}: leader support getter uses stale original-tag gating")

    old_ideas = read(root / "common/ideas/valeraland.txt") or ""
    mercenary_stub = extract_named_block(old_ideas, "VAL_mercenary_state") or ""
    modifier = extract_named_block(mercenary_stub, "modifier") or ""
    if not mercenary_stub or re.sub(r"\s+", "", _mask_non_code(modifier)) != "{}":
        issues.append("VAL_mercenary_state must parse as an empty compatibility stub")
    for forbidden in (
        "send_volunteer_size",
        "send_volunteer_divisions_required",
        "army_attack_factor",
        "army_defence_factor",
    ):
        if forbidden in mercenary_stub:
            issues.append(f"VAL_mercenary_state retains gameplay modifier {forbidden}")
    for relative in (
        "history/countries/VAL - ValeraLand.txt",
        "common/bookmarks/the_gathering_storm.txt",
    ):
        if "VAL_mercenary_state" in (read(root / relative) or ""):
            issues.append(f"{relative}: grants obsolete VAL_mercenary_state")

    core_path = root / "common/scripted_effects/ADISCORD_STP_VAL_crisis_core_effects.txt"
    core = read(core_path) or ""
    state_face_access = re.compile(
        r"\bvar\s*=\s*STP_state_face_stage\b"
        r"|\bvalue\s*=\s*STP_state_face_stage\b"
        r"|\bSTP_state_face_stage\s*(?:=|>|<)"
    )
    for base in (root / "common", root / "events", root / "history"):
        if not base.exists():
            continue
        for path in base.rglob("*.txt"):
            text = read(path) or ""
            if state_face_access.search(_mask_non_code(text)) and path != core_path:
                issues.append(
                    f"{path.relative_to(root)}: legacy state-face variable is read outside its compatibility API"
                )
    if len(state_face_access.findall(_mask_non_code(core))) != 4:
        issues.append("legacy state-face mirror must be confined to four migration/wrapper accesses")

    initialize = extract_named_block(core, "ADISCORD_STP_VAL_initialize_schema") or ""
    suspicion_migration = initialize.find(
        "multiply_variable = { var = STP_party_suspicion value = 100 }"
    )
    suspicion_default = initialize.find(
        "set_variable = { var = STP_party_suspicion value = 5 }"
    )
    val_reconstruction = initialize.find(
        "set_variable = { var = VAL_contract_authority value = 35 }"
    )
    schema_commit = initialize.find(
        "set_variable = { var = ADISCORD_STP_VAL_crisis_schema_version value = 2 }"
    )
    if min(suspicion_migration, suspicion_default, val_reconstruction, schema_commit) < 0:
        issues.append("schema initialization is missing a required migration phase")
    else:
        if not suspicion_migration < suspicion_default < schema_commit:
            issues.append("legacy suspicion must migrate before defaults and schema commit")
        if not val_reconstruction < schema_commit:
            issues.append("VAL authority must be reconstructed before schema commit")
    if "NOT = { has_variable = ADISCORD_STP_VAL_crisis_schema_version }" not in initialize:
        issues.append("schema migration lacks its idempotent outer guard")
    for token in (
        "check_variable = { var = ADISCORD_STP_VAL_crisis_schema_version value = 2 compare = less_than }",
        "has_variable = ADISCORD_STP_VAL_crisis_schema_version",
        "clamp_variable = { var = VAL_contract_authority min = 0 max = 100 }",
    ):
        if token not in initialize:
            issues.append(f"schema v1-to-v2 migration is missing {token}")
    for focus_id, rewards in VAL_FOCUS_REWARD_TOKENS.items():
        if (
            any("VAL_change_contract_authority" in reward for reward in rewards)
            and f"has_completed_focus = {focus_id}" not in initialize
        ):
            issues.append(f"VAL authority migration omits completed reward {focus_id}")

    crisis_texts: dict[str, str] = {}
    for relative in OWNED_FEATURE_FILES:
        text = read(root / relative)
        if text is not None:
            crisis_texts[relative] = text
    combined = "\n".join(crisis_texts.values())
    saved_targets = set(
        re.findall(r"\bsave_global_event_target_as\s*=\s*([A-Za-z0-9_]+)", combined)
    )
    cleared_targets = set(
        re.findall(r"\bclear_global_event_target\s*=\s*([A-Za-z0-9_]+)", combined)
    )
    persistent_targets = {"STP_postwar_country"}
    for target in sorted(saved_targets - cleared_targets - persistent_targets):
        issues.append(f"temporary global event target {target} has no cleanup path")

    for relative, text in crisis_texts.items():
        if "skip_default_capitulation" in text and relative != (
            "common/on_actions/01_ADISCORD_STP_VAL_crisis_on_actions.txt"
        ):
            issues.append(f"{relative}: globally suppresses capitulation outside the exact router")
    on_actions = crisis_texts.get(
        "common/on_actions/01_ADISCORD_STP_VAL_crisis_on_actions.txt", ""
    )
    capitulation = extract_named_block(on_actions, "on_capitulation") or ""
    for token in (
        "set_global_flag = STP_VAL_skip_capitulation_claimed",
        "has_global_flag = STP_VAL_skip_capitulation_claimed",
        "clr_global_flag = STP_VAL_skip_capitulation_claimed",
    ):
        if token not in capitulation:
            issues.append(f"scripted capitulation router lacks scoped flag cleanup {token}")
    if "clr_global_flag = skip_default_capitulation" in capitulation:
        issues.append("scripted capitulation router must leave shared fallback cleanup to the final global router")
    fallback = read(
        root / "common/on_actions/ZZ_ADISCORD_default_capitulation_on_actions.txt"
    ) or ""
    if "clr_global_flag = skip_default_capitulation" not in fallback:
        issues.append("final global capitulation router does not clean its shared reservation flag")

    contracts = crisis_texts.get(
        "common/scripted_effects/ADISCORD_STP_VAL_contract_effects.txt", ""
    )
    contract_cleanup = extract_named_block(contracts, "VAL_STP_cleanup_contract_relations") or ""
    for token in (
        "remove_resource_rights = 45",
        "remove_resource_rights = 88",
        "relation = military_access",
        "relation = non_aggression_pact",
        "remove_ideas = STP_val_contract_advisers",
        "remove_ideas = VAL_STP_postwar_contract_income",
        "remove_decision = VAL_STP_adviser_factory_obligation",
        "clr_country_flag = VAL_STP_contract_active",
        "clear_global_event_target = STP_val_contract_partner",
    ):
        if token not in contract_cleanup:
            issues.append(f"contract cleanup manifest is missing {token}")
    for effect_id, tokens in {
        "VAL_clear_foreign_operation": (
            "VAL_foreign_operation_active",
            "VAL_operation_STP_map_mountain_passes",
            "VAL_operation_APH_prepare_separate_terms",
        ),
        "VAL_clear_active_northern_campaign": (
            "VAL_northern_campaign_participant",
            "VAL_northern_campaign_timeout_210",
            "VAL_northern_cin_participant",
            "VAL_northern_owner_61",
        ),
    }.items():
        block = extract_named_block(contracts, effect_id) or ""
        for token in tokens:
            if token not in block:
                issues.append(f"{effect_id} cleanup manifest is missing {token}")
    war_effects = crisis_texts.get(
        "common/scripted_effects/ADISCORD_STP_VAL_crisis_war_effects.txt", ""
    )
    for effect_id, tokens in {
        "STP_clear_external_crisis_participants": (
            "STP_external_crisis_participant",
            "STP_direct_external_intervention",
            "STP_nodrul_limited_support",
            "NOD_STP_temporary_access",
        ),
        "NOD_clear_limited_conflict_state": (
            "NOD_limited_war_active",
            "NOD_limited_war_target",
            "NOD_limited_war_target_country",
            "NOD_limited_war_timeout_ypr",
        ),
    }.items():
        block = extract_named_block(war_effects, effect_id) or ""
        for token in tokens:
            if token not in block:
                issues.append(f"{effect_id} cleanup manifest is missing {token}")

    canonical_variables = (
        "STP_party_suspicion",
        "STP_resistance_readiness",
        "STP_leader_health_stage",
        "VAL_contract_authority",
    )
    direct_mutation = re.compile(
        r"\b(?:set_variable|add_to_variable|subtract_from_variable|multiply_variable|"
        r"divide_variable|clamp_variable)\s*=\s*\{[^{}]*\bvar\s*=\s*("
        + "|".join(map(re.escape, canonical_variables))
        + r")\b",
        re.DOTALL,
    )
    for relative, text in crisis_texts.items():
        if relative == "common/scripted_effects/ADISCORD_STP_VAL_crisis_core_effects.txt":
            continue
        for variable in direct_mutation.findall(_mask_non_code(text)):
            issues.append(f"{relative}: directly mutates canonical variable {variable}")

    event_definitions: set[str] = set()
    for path in (root / "events").glob("*.txt"):
        text = read(path) or ""
        for block_type in ("country_event", "news_event"):
            for block in _iter_named_blocks(text, block_type):
                event_definitions.update(
                    value
                    for value in _direct_scalar_values(block, "id")
                    if value.startswith(("stp_crisis.", "val_contract.", "nod_crisis."))
                )
    event_references = set(
        re.findall(r"\b(?:id|event_id)\s*=\s*((?:stp_crisis|val_contract|nod_crisis)\.\d+)", combined)
    )
    for event_id in sorted(event_references - event_definitions):
        issues.append(f"crisis content references undefined event {event_id}")


def _validate_performance(root: Path, issues: list[str]) -> None:
    for relative_path in OWNED_FEATURE_FILES:
        text = read(root / relative_path)
        if text is not None:
            _validate_file(relative_path, text, issues)
    _validate_legacy_integration(root, issues)


def validate(root: Path, section: str | None = None) -> list[str]:
    """Return all findings for the requested section without modifying repository files."""
    if section is not None and section not in SECTIONS:
        raise ValueError(f"unknown section {section!r}; choose from {', '.join(SECTIONS)}")
    issues: list[str] = []
    for name in (section,) if section else SECTIONS:
        if name == "performance":
            _validate_performance(root, issues)
        else:
            _validate_section(root, name, issues)
            if name == "stp":
                _validate_stp_contract(root, issues)
            elif name == "civil_war":
                _validate_civil_war_contract(root, issues)
            elif name == "val":
                _validate_val_contract_campaign(root, issues)
            elif name == "nod":
                _validate_nod_contract(root, issues)
            elif name == "north":
                _validate_northern_campaign(root, issues)
            elif name == "peace":
                _validate_scripted_peace_contract(root, issues)
            elif name == "ai":
                _validate_ai_contract(root, issues)
            elif name == "gui":
                _validate_gui_contract(root, issues)
            elif name == "localisation":
                _validate_localisation_contract(root, issues)
    return list(dict.fromkeys(issues))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--section", choices=SECTIONS, help="run only one feature-gate section")
    parser.add_argument("--print-owned-files", action="store_true", help="print exact feature-owned paths")
    args = parser.parse_args()
    if args.print_owned_files:
        print(*OWNED_FEATURE_FILES, sep="\n")
        return 0
    issues = validate(ROOT, args.section)
    if issues:
        print("Stelander Kefreyt crisis validation failed:")
        print(*(f"- {issue}" for issue in issues), sep="\n")
        return 1
    print("Stelander Kefreyt crisis validation passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
