#!/usr/bin/env python3
"""Read-only feature gate for the Stelander Kefreyt crisis implementation."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

try:
    from tools.stp_val_crisis_manifest import OWNED_FEATURE_FILES
except ModuleNotFoundError:
    from stp_val_crisis_manifest import OWNED_FEATURE_FILES


ROOT = Path(__file__).resolve().parents[1]
SECTIONS = ("core", "stp", "civil_war", "val", "nod", "north", "ai", "gui", "localisation", "performance")
REQUIRED_FILES = {
    "core": (
        ("common/scripted_effects/ADISCORD_STP_VAL_crisis_core_effects.txt", "core scripted effects"),
        ("common/scripted_triggers/ADISCORD_STP_VAL_crisis_triggers.txt", "crisis scripted triggers"),
        ("common/on_actions/01_ADISCORD_STP_VAL_crisis_on_actions.txt", "crisis on-actions"),
    ),
    "stp": (
        ("common/decisions/ADISCORD_STP_crisis_decisions.txt", "STP crisis decisions"),
        ("events/ADISCORD_STP_crisis_events.txt", "STP crisis events"),
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
