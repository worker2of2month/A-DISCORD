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
        OWNED_FEATURE_FILES,
        RESISTANCE_POSTURES,
        SECURITY_POSTURES,
        STP_CRISIS_FOCUS_REWARDS,
        STP_CRISIS_FOCUS_STAGES,
        STP_PARTY_FOCUSES,
        STP_SHABRAT_FOCUSES,
        STP_SPINE_FOCUS_STAGES,
    )
except ModuleNotFoundError:
    from stp_val_crisis_manifest import (
        DECISION_CATEGORIES,
        HEALTH_MISSIONS,
        OWNED_FEATURE_FILES,
        RESISTANCE_POSTURES,
        SECURITY_POSTURES,
        STP_CRISIS_FOCUS_REWARDS,
        STP_CRISIS_FOCUS_STAGES,
        STP_PARTY_FOCUSES,
        STP_SHABRAT_FOCUSES,
        STP_SPINE_FOCUS_STAGES,
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
        ("common/decisions/ADISCORD_VAL_contract_decisions.txt", "VAL contract decisions"),
        ("events/ADISCORD_VAL_contract_events.txt", "VAL contract events"),
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
