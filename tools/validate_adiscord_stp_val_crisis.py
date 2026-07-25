#!/usr/bin/env python3
"""Read-only feature gate for the Stelander Kefreyt crisis implementation."""

from __future__ import annotations

import argparse
import re
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
        OWNED_FEATURE_FILES,
        POSTWAR_FOCUS_IDS,
        RESISTANCE_POSTURES,
        SECURITY_POSTURES,
        STP_ADAPTATION_FAMILIES,
        STP_CIVIL_WAR_ARMY_RATIOS,
        STP_CIVIL_WAR_FOCUS_IDS,
        STP_CIVIL_WAR_STATES,
        STP_CRISIS_FOCUS_REWARDS,
        STP_CRISIS_FOCUS_STAGES,
        STP_OPERATION_SPECS,
        STP_OPERATION_VARIANTS,
        STP_PARTY_FOCUSES,
        STP_RESISTANCE_PROJECTS,
        STP_SHABRAT_FOCUSES,
        STP_SPINE_FOCUS_STAGES,
        VAL_BASE_FOCUS_IDS,
        VAL_CONTRACT_BANDS,
        VAL_CRISIS_FOCUS_IDS,
        VAL_FOCUS_REWARD_TOKENS,
        VAL_NORTHERN_OPERATION_SPECS,
        VAL_NORTHERN_OPERATION_TARGETS,
        VAL_STP_CONCESSION_FLAGS,
        VAL_STP_OPERATION_SPECS,
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
        OWNED_FEATURE_FILES,
        POSTWAR_FOCUS_IDS,
        RESISTANCE_POSTURES,
        SECURITY_POSTURES,
        STP_ADAPTATION_FAMILIES,
        STP_CIVIL_WAR_ARMY_RATIOS,
        STP_CIVIL_WAR_FOCUS_IDS,
        STP_CIVIL_WAR_STATES,
        STP_CRISIS_FOCUS_REWARDS,
        STP_CRISIS_FOCUS_STAGES,
        STP_OPERATION_SPECS,
        STP_OPERATION_VARIANTS,
        STP_PARTY_FOCUSES,
        STP_RESISTANCE_PROJECTS,
        STP_SHABRAT_FOCUSES,
        STP_SPINE_FOCUS_STAGES,
        VAL_BASE_FOCUS_IDS,
        VAL_CONTRACT_BANDS,
        VAL_CRISIS_FOCUS_IDS,
        VAL_FOCUS_REWARD_TOKENS,
        VAL_NORTHERN_OPERATION_SPECS,
        VAL_NORTHERN_OPERATION_TARGETS,
        VAL_STP_CONCESSION_FLAGS,
        VAL_STP_OPERATION_SPECS,
    )


ROOT = Path(__file__).resolve().parents[1]
SECTIONS = ("core", "stp", "civil_war", "val", "nod", "north", "ai", "gui", "localisation", "performance")
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
        ("common/dynamic_modifiers/ADISCORD_STP_VAL_crisis_dynamic_modifiers.txt", "VAL contract dynamic modifier"),
        ("common/scripted_effects/ADISCORD_STP_VAL_crisis_core_effects.txt", "VAL contract authority effects"),
    ),
    "nod": (
        ("common/decisions/ADISCORD_NOD_crisis_decisions.txt", "NOD crisis decisions"),
        ("events/ADISCORD_NOD_crisis_events.txt", "NOD crisis events"),
    ),
    "north": (
        ("common/scripted_effects/ADISCORD_STP_VAL_contract_effects.txt", "contract and northern effects"),
    ),
    "ai": (
        ("common/ai_strategy/ADISCORD_STP_VAL_crisis_ai.txt", "crisis AI strategies"),
    ),
    "gui": (
        ("interface/ADISCORD_STP_VAL_crisis.gui", "crisis GUI"),
        ("common/scripted_guis/ADISCORD_STP_VAL_crisis_scripted_gui.txt", "crisis scripted GUI"),
    ),
    "localisation": (
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
                STP_SPINE_FOCUS_STAGES[2],
                "STP_health_stage_2_to_3",
            ),
            (
                "stp_crisis.2",
                3,
                STP_SPINE_FOCUS_STAGES[3],
                "STP_health_stage_3_to_4",
            ),
            (
                "stp_crisis.3",
                4,
                STP_SPINE_FOCUS_STAGES[4],
                "STP_health_stage_4_to_death",
            ),
        )
        for event_id, stage, spine, next_mission in chain:
            block = _block_with_direct_assignment(
                events, "country_event", "id", event_id
            )
            if block is None:
                issues.append(f"missing STP calendar event {event_id}")
                continue
            for token in (
                "hidden = yes",
                f"STP_set_health_stage = {{ value = {stage} }}",
                f"activate_mission = {next_mission}",
                *(f"complete_national_focus = {focus}" for focus in spine),
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
                "STP_set_health_stage = { value = 5 }",
                "complete_national_focus = STP_The_Father_Of_Peace_Is_Gone",
                "retire_character = STP_Petr_Ivanov",
                "STP_set_crisis_phase = { value = 2 }",
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
        for focus, stage in STP_CRISIS_FOCUS_STAGES.items():
            block = _block_with_direct_assignment(focuses, "focus", "id", focus)
            if block is None:
                issues.append(f"missing playable STP crisis focus {focus}")
                continue
            if _direct_scalar_values(block, "cost") != ["5"]:
                issues.append(f"playable focus {focus} must preserve cost 5")
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
            side_value = (
                1 if focus in STP_SHABRAT_FOCUSES else 2 if focus in STP_PARTY_FOCUSES else None
            )
            if side_value is not None and not re.search(
                r"var\s*=\s*STP_side_commitment\s+value\s*=\s*"
                rf"{side_value}\s+compare\s*=\s*equals",
                _mask_non_code(available),
            ):
                issues.append(f"playable focus {focus} has the wrong side gate")
        for spine in (focus for focuses_by_stage in STP_SPINE_FOCUS_STAGES.values() for focus in focuses_by_stage):
            block = _block_with_direct_assignment(focuses, "focus", "id", spine)
            available = extract_named_block(block or "", "available") or ""
            if "is_completed_by_event = yes" not in available:
                issues.append(f"calendar spine focus {spine} must be event-only")

    if on_actions is not None:
        startup = extract_named_block(on_actions, "on_startup") or ""
        for token in (
            "STP_health_calendar_started",
            "complete_national_focus = STP_Nectar_of_the_Gods",
            "activate_mission = STP_health_stage_1_to_2",
        ):
            if token not in startup:
                issues.append(f"STP startup is missing guarded calendar action {token}")
        if not re.search(
            r"NOT\s*=\s*\{\s*has_country_flag\s*=\s*STP_health_calendar_started\s*\}"
            r".*set_country_flag\s*=\s*STP_health_calendar_started"
            r".*complete_national_focus\s*=\s*STP_Nectar_of_the_Gods"
            r".*activate_mission\s*=\s*STP_health_stage_1_to_2",
            _mask_non_code(startup),
            re.DOTALL,
        ):
            issues.append("STP startup calendar activation must be guarded and atomic")

    if core is not None:
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
                "STP_start_resistance_revolt",
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
        leader = extract_named_block(war, "STP_assign_postwar_leader") or ""
        for token in (
            "STP_internal_outcome_finalizing",
            "STP_internal_outcome_finalized",
            "save_global_event_target_as = STP_postwar_country",
            "set_country_flag = STP_postwar_campaign_side",
            "STP_set_crisis_phase = { value = 3 }",
            "STP_assign_postwar_leader = yes",
            "tree = ADISCORD_STP_postwar_focus",
            "STP_clear_external_crisis_participants = yes",
            "VAL_STP_start_war_countdown = { type = 120 }",
        ):
            if token not in finalizer:
                issues.append(f"single internal finalizer is missing {token}")
        if (
            "STP_assign_postwar_leader = yes" in finalizer
            and "tree = ADISCORD_STP_postwar_focus" in finalizer
            and finalizer.index("STP_assign_postwar_leader = yes")
            > finalizer.index("tree = ADISCORD_STP_postwar_focus")
        ):
            issues.append("bridge focus must complete before the postwar tree is loaded")
        for bridge in (
            "STP_The_Mountain_Window",
            "STP_No_One_Controls_The_Transition",
            "STP_The_Party_Closes_Ranks",
        ):
            if leader.count(bridge) != 1:
                issues.append(f"postwar leader assignment must complete {bridge} exactly once")
        countdown = extract_named_block(war, "VAL_STP_start_war_countdown") or ""
        for flag in (120, 180, 300, 450):
            if f"VAL_STP_countdown_{flag}" not in countdown:
                issues.append(f"countdown forward interface is missing literal type {flag}")
        if "activate_mission" in countdown:
            issues.append("Task 5 countdown forward interface must not activate undefined missions")

    if events is not None:
        death = _block_with_direct_assignment(events, "country_event", "id", "stp_crisis.4") or ""
        router = _block_with_direct_assignment(events, "country_event", "id", "stp_crisis.50") or ""
        if "country_event = { id = stp_crisis.50 }" not in death:
            issues.append("Ivanov death event must invoke the Task 5 outcome router")
        expected_outcomes = {
            "STP_outcome_shabrat_bloodless",
            "STP_outcome_shabrat_main_war",
            "STP_outcome_sotnikov_main_war",
            "STP_outcome_hedersett_fail_state",
            "STP_outcome_hedersett_consolidation",
            "STP_outcome_hedersett_vs_shabrat",
            "STP_outcome_hedersett_vs_sotnikov",
        }
        actual_outcomes = set(
            re.findall(
                r"\bset_country_flag\s*=\s*(STP_outcome_[A-Za-z0-9_]+)",
                _mask_non_code(router),
            )
        )
        if actual_outcomes != expected_outcomes:
            issues.append("Ivanov death router must expose exactly seven canonical outcomes")
        if router.count("STP_finalize_internal_outcome = yes") != 3:
            issues.append("all three no-war outcomes must use the single finalizer")
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
            if re.search(r"\bFROM\b", _mask_non_code(block)):
                issues.append(f"{hook} must not infer the internal winner from FROM")

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
    core = read(root / "common/scripted_effects/ADISCORD_STP_VAL_crisis_core_effects.txt")
    triggers = read(root / "common/scripted_triggers/ADISCORD_STP_VAL_crisis_triggers.txt")
    dynamic = read(root / "common/dynamic_modifiers/ADISCORD_STP_VAL_crisis_dynamic_modifiers.txt")
    ideas = read(root / "common/ideas/ADISCORD_STP_VAL_crisis_ideas.txt")
    decisions = read(root / "common/decisions/ADISCORD_VAL_contract_decisions.txt")
    contract_effects = read(
        root / "common/scripted_effects/ADISCORD_STP_VAL_contract_effects.txt"
    )
    contract_events = read(root / "events/ADISCORD_VAL_contract_events.txt")

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

        for focus_id, tokens in VAL_FOCUS_REWARD_TOKENS.items():
            reward = extract_named_block(blocks.get(focus_id, ""), "completion_reward") or ""
            for token in tokens:
                if token not in reward:
                    issues.append(f"{focus_id} reward is missing {token}")

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
        for pair in (
            ("VAL_One_Ledger_One_Banner", "VAL_Export_Rifles_Not_Promises"),
            ("VAL_One_Ledger_One_Banner", "VAL_Morns_Supply_Trains"),
            ("VAL_One_Ledger_One_Banner", "VAL_Dead_Villages_Still_Count"),
            ("VAL_One_Ledger_One_Banner", "VAL_Different_Views_On_Freedom"),
        ):
            if not re.search(
                rf"prerequisite\s*=\s*\{{[^}}]*focus\s*=\s*{pair[0]}[^}}]*focus\s*=\s*{pair[1]}[^}}]*\}}",
                _mask_non_code(final_join),
                re.DOTALL,
            ):
                issues.append(f"VAL final join is missing alternative {' + '.join(pair)}")

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
        if re.search(r"volunteer", _mask_non_code(focus_text + (dynamic or "")), re.IGNORECASE):
            issues.append("VAL contract campaign must not use volunteer modifiers")

    if core is not None:
        refresh = extract_named_block(core, "VAL_refresh_contract_modifier") or ""
        for band in VAL_CONTRACT_BANDS:
            if f"# VAL contract band {band['minimum']}-{band['maximum']}" not in refresh:
                issues.append(f"VAL contract modifier is missing band {band['minimum']}-{band['maximum']}")
        if refresh.count("force_update_dynamic_modifier = yes") != 1:
            issues.append("VAL contract modifier must force-update exactly once behind a band change")
        for token in (
            "VAL_contract_new_band",
            "VAL_contract_band",
            "compare = equals",
        ):
            if token not in refresh:
                issues.append(f"VAL band-change guard is missing {token}")

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
        for decision_id, (cost, days, family) in VAL_STP_OPERATION_SPECS.items():
            block = extract_named_block(decisions, decision_id) or ""
            if not block:
                issues.append(f"missing VAL STP operation {decision_id}")
                continue
            if _direct_scalar_values(block, "cost") != [str(cost)]:
                issues.append(f"{decision_id} must cost {cost} PP")
            if _direct_scalar_values(block, "days_remove") != [str(days)]:
                issues.append(f"{decision_id} must last {days} days")
            available = extract_named_block(block, "available") or ""
            for token in (
                "VAL_foreign_operation_active",
                "VAL_STP_target_cooldown",
                f"VAL_STP_block_{family}",
            ):
                if token not in available:
                    issues.append(f"{decision_id} availability is missing {token}")

        for target in VAL_NORTHERN_OPERATION_TARGETS:
            for suffix, (cost, days, _) in VAL_NORTHERN_OPERATION_SPECS.items():
                decision_id = f"VAL_{target}_{suffix}"
                block = extract_named_block(decisions, decision_id) or ""
                if not block:
                    issues.append(f"missing northern operation {decision_id}")
                    continue
                if _direct_scalar_values(block, "cost") != [str(cost)]:
                    issues.append(f"{decision_id} must cost {cost} PP")
                if _direct_scalar_values(block, "days_remove") != [str(days)]:
                    issues.append(f"{decision_id} must last {days} days")
                available = extract_named_block(block, "available") or ""
                for token in ("VAL_foreign_operation_active", f"VAL_{target}_target_cooldown"):
                    if token not in available:
                        issues.append(f"{decision_id} availability is missing {token}")
                if suffix == "arms_brokerage" and "amount = -400" not in block:
                    issues.append(f"{decision_id} must pay 400 infantry equipment")
                if suffix == "infrastructure_concession" and "civilian_factory_use = 2" not in block:
                    issues.append(f"{decision_id} must reserve two civilian factories")
                if suffix == "hire_local_captain":
                    for token in ("add_command_power = -15", "amount = -80"):
                        if token not in block:
                            issues.append(f"{decision_id} is missing paid captain cost {token}")
                if suffix == "prepare_separate_terms":
                    for token in ("civilian_factory_use = 1", "amount = 2"):
                        if token not in block:
                            issues.append(f"{decision_id} is missing separate-terms gate {token}")

    if contract_effects is None:
        issues.append("missing contract and northern effects: common/scripted_effects/ADISCORD_STP_VAL_contract_effects.txt")
    else:
        finish = extract_named_block(contract_effects, "VAL_finish_stp_operation") or ""
        for token in ("VAL_STP_target_cooldown", "days = 42", "VAL_clear_foreign_operation = yes"):
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
        memory = extract_named_block(contract_effects, "VAL_update_northern_family_memory") or ""
        for token in ("$last_var$", "$streak_var$", "value = 3", "days = 90"):
            if token not in memory:
                issues.append(f"VAL northern family memory is missing {token}")
        northern_resolver = extract_named_block(contract_effects, "VAL_resolve_northern_operation") or ""
        for token in ("days = 70", "$influence_var$", "max = 3"):
            if token not in northern_resolver:
                issues.append(f"VAL northern resolver is missing {token}")
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
            if f"countdown = {countdown}" not in contract_effects:
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
        "num_equipment@infantry_equipment",
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


def _validate_performance(root: Path, issues: list[str]) -> None:
    for relative_path in OWNED_FEATURE_FILES:
        text = read(root / relative_path)
        if text is not None:
            _validate_file(relative_path, text, issues)


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
