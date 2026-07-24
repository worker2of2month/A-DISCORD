#!/usr/bin/env python3
"""Read-only feature gate for the staged Vorkerland collapse implementation."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

try:
    from tools.vorkerland_collapse_manifest import (
        CAPITALS,
        CONTAMINATED_STATES,
        DIRTY_GROUPS,
        STATE_PARTITIONS,
        TAGS,
    )
except ModuleNotFoundError:
    from vorkerland_collapse_manifest import (
        CAPITALS,
        CONTAMINATED_STATES,
        DIRTY_GROUPS,
        STATE_PARTITIONS,
        TAGS,
    )


ROOT = Path(__file__).resolve().parents[1]
SECTIONS = ("manifest", "states", "countries", "dirty", "events", "ai", "outcomes", "superevents")
FEATURE = "ADISCORD_vorkerland_collapse"


def read(path: Path) -> str | None:
    """Return text without changing the file, or None when a later task has not created it."""
    try:
        return path.read_text(encoding="utf-8-sig")
    except FileNotFoundError:
        return None


def state_file(root: Path, state_id: int) -> Path | None:
    matches = sorted((root / "history" / "states").glob(f"{state_id}-*.txt"))
    return matches[0] if matches else None


def provinces(text: str) -> set[int]:
    match = re.search(r"\bprovinces\s*=\s*\{([^}]*)\}", text, re.DOTALL)
    return {int(value) for value in re.findall(r"\d+", match.group(1))} if match else set()


def require_file(issues: list[str], path: Path, label: str) -> str:
    text = read(path)
    if text is None:
        issues.append(f"missing {label}: {path.as_posix()}")
        return ""
    return text


def validate_manifest(issues: list[str]) -> None:
    dirty_states = set().union(*(set(group) for group in DIRTY_GROUPS.values()))
    if len(TAGS) != 16 or len(TAGS) != len(set(TAGS)):
        issues.append("manifest must define 16 unique fixed tags")
    if len(CONTAMINATED_STATES) != 37:
        issues.append("manifest must define 37 contaminated states")
    if dirty_states != CONTAMINATED_STATES - {23, 24, 57, 59, 60}:
        issues.append("dirty groups must cover every transferable contaminated state exactly once")
    if set(CAPITALS) != set(TAGS):
        issues.append("capital keys must equal fixed tags")
    if set(STATE_PARTITIONS) != {71, 72, 74, 76, 80}:
        issues.append("state partition keys must be 71, 72, 74, 76, and 80")


def validate_states(root: Path, issues: list[str]) -> None:
    for source_state, partition in STATE_PARTITIONS.items():
        actual: set[int] = set()
        for state_id, expected in partition.items():
            path = state_file(root, state_id)
            if path is None:
                issues.append(f"missing state {state_id} from partition of state {source_state}")
                continue
            found = provinces(read(path) or "")
            if found != set(expected):
                issues.append(f"state {state_id} provinces do not match its manifest partition")
            actual.update(found)
        expected_all = set().union(*(set(values) for values in partition.values()))
        if actual and actual != expected_all:
            issues.append(f"state partition for {source_state} does not cover the manifest provinces exactly")

    for tag, (state_id, capital) in CAPITALS.items():
        path = state_file(root, state_id)
        if path is not None and capital not in provinces(read(path) or ""):
            issues.append(f"capital province {capital} for {tag} is not in state {state_id}")


def validate_countries(root: Path, issues: list[str]) -> None:
    tag_file = root / "common" / "country_tags" / "01_ADISCORD_vorkerland_collapse_tags.txt"
    tag_text = require_file(issues, tag_file, "fixed-tag registry")
    characters = require_file(
        issues,
        root / "common" / "characters" / "ADISCORD_vorkerland_collapse_characters.txt",
        "collapse character database",
    )
    for tag in TAGS:
        if tag_text and re.search(rf"(?m)^\s*{tag}\s*=", tag_text) is None:
            issues.append(f"fixed tag {tag} is absent from the tag registry")
        require_file(issues, root / "common" / "countries" / f"{tag}.txt", f"country definition for {tag}")
        if not list((root / "history" / "countries").glob(f"{tag} - *.txt")):
            issues.append(f"missing dormant country history for {tag}")
        require_file(issues, root / "history" / "units" / f"{tag}_vorkerland_collapse.txt", f"collapse OOB for {tag}")
        if characters and tag not in characters:
            issues.append(f"character database has no entry for {tag}")
        for size in ("", "medium", "small"):
            flag = root / "gfx" / "flags" / size / f"{tag}.tga" if size else root / "gfx" / "flags" / f"{tag}.tga"
            if not flag.exists():
                issues.append(f"missing {size or 'large'} flag for {tag}")


def validate_dirty(root: Path, issues: list[str]) -> None:
    modifier = require_file(
        issues,
        root / "common" / "dynamic_modifiers" / "ADISCORD_vorkerland_collapse_dynamic_modifiers.txt",
        "dirty-state dynamic modifier",
    )
    effects = require_file(
        issues,
        root / "common" / "scripted_effects" / "ADISCORD_vorkerland_collapse_dirty_effects.txt",
        "dirty-state effect file",
    )
    if modifier:
        if "ADISCORD_vorkerland_dirty_state" not in modifier:
            issues.append("dirty-state modifier key is missing")
        if "remove_trigger" in modifier:
            issues.append("dirty-state modifier must not have a remove_trigger")
    if effects and "ADISCORD_vorkerland_apply_dirty_modifiers" not in effects:
        issues.append("dirty-state application effect is missing")
    for path in root.rglob("*.txt"):
        text = read(path) or ""
        if "remove_dynamic_modifier" in text and "ADISCORD_vorkerland_dirty_state" in text:
            issues.append(f"dirty-state modifier is removed in {path.relative_to(root).as_posix()}")


def validate_events(root: Path, issues: list[str]) -> None:
    events = require_file(issues, root / "events" / "ADISCORD_vorkerland_collapse_events.txt", "collapse event file")
    effects = require_file(issues, root / "common" / "scripted_effects" / "ADISCORD_vorkerland_collapse_effects.txt", "collapse effects")
    triggers = require_file(issues, root / "common" / "scripted_triggers" / "ADISCORD_vorkerland_collapse_triggers.txt", "collapse triggers")
    on_actions = require_file(issues, root / "common" / "on_actions" / "01_ADISCORD_vorkerland_collapse_on_actions.txt", "collapse on-actions")
    for text, label in ((events, "events"), (effects, "effects"), (triggers, "triggers"), (on_actions, "on-actions")):
        if text and FEATURE not in text:
            issues.append(f"collapse {label} do not contain the feature namespace")


def validate_ai(root: Path, issues: list[str]) -> None:
    ai = require_file(issues, root / "common" / "ai_strategy" / "ADISCORD_vorkerland_collapse_ai.txt", "collapse AI strategy file")
    if ai:
        if "abort_when_not_enabled = yes" not in ai:
            issues.append("collapse AI strategies must abort when disabled")
        for tag in TAGS:
            if tag not in ai:
                issues.append(f"collapse AI has no coverage for {tag}")


def validate_outcomes(root: Path, issues: list[str]) -> None:
    maps = require_file(
        issues,
        root / "common" / "scripted_effects" / "ADISCORD_vorkerland_collapse_map_effects.txt",
        "collapse outcome map effects",
    )
    if maps:
        for name in ("worker", "vlad", "dorian", "fragmented"):
            if f"ADISCORD_vorkerland_apply_{name}_map" not in maps:
                issues.append(f"missing {name} outcome map effect")


def validate_superevents(root: Path, issues: list[str]) -> None:
    files = (
        (root / "interface" / "superevents.gfx", "superevent GFX"),
        (root / "common" / "scripted_guis" / "superevents.txt", "superevent GUI"),
        (root / "common" / "scripted_localisation" / "ADISCORD_scripted_loc_superevents.txt", "superevent localisation script"),
        (root / "localisation" / "russian" / "ADISCORD_superevents_l_russian.yml", "Russian superevent localisation"),
    )
    for path, label in files:
        text = require_file(issues, path, label)
        if text and FEATURE not in text:
            issues.append(f"{label} has no Vorkerland collapse bindings")


CHECKS = {
    "manifest": lambda root, issues: validate_manifest(issues),
    "states": validate_states,
    "countries": validate_countries,
    "dirty": validate_dirty,
    "events": validate_events,
    "ai": validate_ai,
    "outcomes": validate_outcomes,
    "superevents": validate_superevents,
}


def validate(root: Path, section: str | None = None) -> list[str]:
    """Return all findings for the requested section, without modifying repository files."""
    if section is not None and section not in SECTIONS:
        raise ValueError(f"unknown section {section!r}; choose from {', '.join(SECTIONS)}")
    issues: list[str] = []
    for name in (section,) if section else SECTIONS:
        CHECKS[name](root, issues)
    return issues


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--section", choices=SECTIONS, help="run only one feature-gate section")
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
