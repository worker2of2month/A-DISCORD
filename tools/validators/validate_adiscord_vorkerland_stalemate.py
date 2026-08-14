#!/usr/bin/env python3
"""Validate the fresh-only Vorkerland anti-stalemate contract."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

_REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
if str(_REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPOSITORY_ROOT))

from tools.lib.paths import repository_root


ROOT = repository_root()

TRIGGERS = "common/scripted_triggers/ADISCORD_vorkerland_stalemate_triggers.txt"
EFFECTS = "common/scripted_effects/ADISCORD_vorkerland_stalemate_effects.txt"
ON_ACTIONS = "common/on_actions/05_ADISCORD_vorkerland_stalemate_on_actions.txt"
EVENTS = "events/ADISCORD_vorkerland_stalemate_events.txt"
AI = "common/ai_strategy/ADISCORD_vorkerland_stalemate_ai.txt"
IDEAS = "common/ideas/ADISCORD_vorkerland_stalemate_ideas.txt"
ENGLISH = "localisation/english/ADISCORD_vorkerland_stalemate_l_english.yml"
RUSSIAN = "localisation/russian/ADISCORD_vorkerland_stalemate_l_russian.yml"
REGISTRY = "tools/data/adiscord_event_ids.json"

SCOPED_FILES = (
    TRIGGERS,
    EFFECTS,
    ON_ACTIONS,
    EVENTS,
    AI,
    IDEAS,
    ENGLISH,
    RUSSIAN,
    REGISTRY,
)

CENTRAL_TARGETS = ("EYR", "EGC", "RIV", "REV", "YOR", "NDN", "SWB", "VHV", "OSV")
SOLAR_TARGETS = ("SRA", "CSL")

SCHEDULED_FLAGS = (
    "ADISCORD_vorkerland_central_stalemate_deadline_scheduled",
    "ADISCORD_vorkerland_solarino_stalemate_deadline_scheduled",
)
RESOLVED_FLAGS = (
    "ADISCORD_vorkerland_central_stalemate_deadline_resolved",
    "ADISCORD_vorkerland_solarino_stalemate_deadline_resolved",
)
ACTIVE_FLAGS = (
    "ADISCORD_vorkerland_central_breakthrough_window_active",
    "ADISCORD_vorkerland_solarino_breakthrough_window_active",
)


def _read(root: Path, relative: str) -> str:
    return (root / relative).read_text(encoding="utf-8-sig")


def _balanced(text: str) -> bool:
    depth = 0
    in_quote = False
    escaped = False
    for line in text.splitlines():
        for char in line:
            if char == "#" and not in_quote:
                break
            if char == "\\" and in_quote and not escaped:
                escaped = True
                continue
            if char == '"' and not escaped:
                in_quote = not in_quote
            elif not in_quote and char == "{":
                depth += 1
            elif not in_quote and char == "}":
                depth -= 1
                if depth < 0:
                    return False
            escaped = False
    return depth == 0 and not in_quote


def _strip_comments(text: str) -> str:
    lines: list[str] = []
    for line in text.splitlines():
        in_quote = False
        escaped = False
        cut = len(line)
        for index, char in enumerate(line):
            if char == "\\" and in_quote and not escaped:
                escaped = True
                continue
            if char == '"' and not escaped:
                in_quote = not in_quote
            elif char == "#" and not in_quote:
                cut = index
                break
            escaped = False
        lines.append(line[:cut])
    return "\n".join(lines)


def _named_block(text: str, name: str) -> str:
    match = re.search(rf"(?m)^\s*{re.escape(name)}\s*=\s*\{{", text)
    if not match:
        return ""
    opening = text.find("{", match.start(), match.end())
    depth = 0
    for index in range(opening, len(text)):
        if text[index] == "{":
            depth += 1
        elif text[index] == "}":
            depth -= 1
            if depth == 0:
                return text[match.start():index + 1]
    return ""


def _gameplay_texts(root: Path) -> list[tuple[str, str]]:
    result: list[tuple[str, str]] = []
    for directory in ("common", "events", "history"):
        base = root / directory
        if not base.exists():
            continue
        for path in base.rglob("*.txt"):
            result.append((path.relative_to(root).as_posix(), path.read_text(encoding="utf-8-sig")))
    return result


def collect_issues(root: Path = ROOT) -> list[str]:
    issues: list[str] = []
    texts: dict[str, str] = {}
    for relative in SCOPED_FILES:
        path = root / relative
        if not path.is_file():
            issues.append(f"missing stalemate contract file: {relative}")
            continue
        try:
            texts[relative] = _read(root, relative)
        except UnicodeDecodeError as exc:
            issues.append(f"{relative}: invalid UTF-8: {exc}")

    required_text_files = (TRIGGERS, EFFECTS, ON_ACTIONS, EVENTS, AI, IDEAS)
    for relative in required_text_files:
        text = texts.get(relative, "")
        if text and not _balanced(text):
            issues.append(f"{relative}: unbalanced Clausewitz braces")

    triggers = texts.get(TRIGGERS, "")
    effects = texts.get(EFFECTS, "")
    on_actions = texts.get(ON_ACTIONS, "")
    events = texts.get(EVENTS, "")
    ai = texts.get(AI, "")
    ideas = texts.get(IDEAS, "")
    combined = _strip_comments("\n".join(texts.get(path, "") for path in required_text_files))

    for token in (
        "has_global_flag = ADISCORD_vorkerland_collapse_started",
        "has_global_flag = ADISCORD_vorkerland_collapse_wars_started",
        "has_global_flag = ADISCORD_vorkerland_phase_central_preparation",
        "NOT = { has_global_flag = ADISCORD_vorkerland_central_showdown_started }",
        "NOT = { has_global_flag = ADISCORD_vorkerland_collapse_finished }",
        "is_ai = yes",
    ):
        if token not in triggers:
            issues.append(f"stalemate phase/AI trigger is missing: {token}")

    for trigger_name in (
        "ADISCORD_vorkerland_has_live_central_minor_war",
        "ADISCORD_vorkerland_has_live_solarino_war",
    ):
        block = _named_block(triggers, trigger_name)
        if "is_ai = yes" not in block:
            issues.append(f"{trigger_name} must be AI-only")
        if "NOT = { has_capitulated = yes }" not in block:
            issues.append(f"{trigger_name} must reject a capitulated attacker")

    for tag in CENTRAL_TARGETS + SOLAR_TARGETS:
        if f"has_war_with = {tag}" not in triggers:
            issues.append(f"live-war trigger is missing {tag}")

    if on_actions.count("on_war_relation_added = {") != 1:
        issues.append("stalemate scheduling must have exactly one on_war_relation_added hook")
    for token in (
        "ROOT = { ADISCORD_vorkerland_is_central_claimant = yes }",
        "FROM = { ADISCORD_vorkerland_is_central_minor = yes }",
        "ROOT = { tag = SOL }",
        "FROM = { OR = { tag = SRA tag = CSL } }",
    ):
        if token not in on_actions:
            issues.append(f"attacker/defender on-action gate is missing: {token}")
    for effect_name in (
        "ADISCORD_vorkerland_schedule_central_stalemate_deadline",
        "ADISCORD_vorkerland_schedule_solarino_stalemate_deadline",
    ):
        if on_actions.count(f"{effect_name} = yes") != 1:
            issues.append(f"{effect_name} must have exactly one on-action caller")
    if re.search(r"\bon_(daily|weekly|monthly|startup)\b", on_actions):
        issues.append("stalemate contract must not poll or run startup/save repair")
    if "every_country" in on_actions:
        issues.append("stalemate on-action must not scan every country")

    for event_id, days in (
        ("ADISCORD_vorkerland_stalemate.1", 240),
        ("ADISCORD_vorkerland_stalemate.2", 300),
    ):
        token = f"country_event = {{ id = {event_id} days = {days} }}"
        if effects.count(token) != 1:
            issues.append(f"one-shot deadline is missing or has wrong delay: {token}")
    if effects.count("add_timed_idea = { idea = ADISCORD_vorkerland_ai_breakthrough_window days = 75 }") != 2:
        issues.append("exactly two AI-gated 75-day idea callers are required")
    for active_flag in ACTIVE_FLAGS:
        token = f"set_country_flag = {{ flag = {active_flag} days = 75 }}"
        if effects.count(token) != 1:
            issues.append(f"bounded 75-day active flag is missing: {active_flag}")

    for effect_name, resolved_flag, active_flag in (
        (
            "ADISCORD_vorkerland_resolve_central_stalemate_deadline",
            RESOLVED_FLAGS[0],
            ACTIVE_FLAGS[0],
        ),
        (
            "ADISCORD_vorkerland_resolve_solarino_stalemate_deadline",
            RESOLVED_FLAGS[1],
            ACTIVE_FLAGS[1],
        ),
    ):
        block = _named_block(effects, effect_name)
        if not block:
            issues.append(f"missing resolver effect: {effect_name}")
            continue
        guard_write = block.find(f"set_country_flag = {resolved_flag}")
        payload = block.find(f"flag = {active_flag}")
        if guard_write < 0 or payload < 0 or guard_write > payload:
            issues.append(f"{effect_name} must write its permanent guard before its payload")

    for event_id, resolver in (
        ("ADISCORD_vorkerland_stalemate.1", "ADISCORD_vorkerland_resolve_central_stalemate_deadline"),
        ("ADISCORD_vorkerland_stalemate.2", "ADISCORD_vorkerland_resolve_solarino_stalemate_deadline"),
    ):
        if events.count(f"id = {event_id}") != 1:
            issues.append(f"event definition count is not one: {event_id}")
        if events.count(f"{resolver} = yes") != 1:
            issues.append(f"deadline event must call {resolver} exactly once")
    if events.count("hidden = yes") != 2 or events.count("is_triggered_only = yes") != 2:
        issues.append("both stalemate events must be hidden and triggered-only")
    if events.count("country_event = {") != 2:
        issues.append("deadline events must not schedule a retry or another event")

    expected_plan_count = len(CENTRAL_TARGETS) + len(SOLAR_TARGETS)
    if ai.count("abort_when_not_enabled = yes") != expected_plan_count:
        issues.append(f"stalemate AI must contain {expected_plan_count} bounded plans")
    for tag in CENTRAL_TARGETS:
        for token in (
            f"has_war_with = {tag}",
            f"type = front_control tag = {tag}",
            f"type = conquer id = {tag}",
        ):
            if token not in ai:
                issues.append(f"central breakthrough AI is missing: {token}")
    for tag in SOLAR_TARGETS:
        for token in (
            f"has_war_with = {tag}",
            f"type = front_control tag = {tag} ratio = 0.50",
            f"type = conquer id = {tag}",
        ):
            if token not in ai:
                issues.append(f"Solarino breakthrough AI is missing: {token}")
    for active_flag in ACTIVE_FLAGS:
        if f"has_country_flag = {active_flag}" not in ai:
            issues.append(f"AI plan is missing its timed activation flag: {active_flag}")
    for token in ("priority = 2000", "execution_type = rush", "manual_attack = yes"):
        if ai.count(token) != expected_plan_count:
            issues.append(f"all stalemate AI plans must use {token}")

    for token in (
        "allowed = { always = no }",
        "allowed_civil_war = { always = yes }",
        "removal_cost = -1",
        "army_attack_factor = 0.08",
        "breakthrough_factor = 0.10",
        "army_org_factor = 0.08",
        "planning_speed = 0.20",
        "land_reinforce_rate = 0.02",
        "supply_consumption_factor = -0.15",
        "army_speed_factor = 0.05",
    ):
        if token not in ideas:
            issues.append(f"bounded operational idea is missing: {token}")

    forbidden_tokens = (
        "declare_war_on",
        "white_peace",
        "annex_country",
        "transfer_state",
        "set_state_controller_to",
        "set_demilitarized_zone",
        "nuclear_strike",
        "on_startup",
        "migration",
        "catch_up",
        "retry",
    )
    for token in forbidden_tokens:
        if re.search(rf"\b{re.escape(token)}\b", combined, flags=re.IGNORECASE):
            issues.append(f"stalemate scope contains forbidden behavior: {token}")
    if re.search(r"\bstate\s*=\s*40\b|\b40\s*=\s*\{", combined, flags=re.MULTILINE):
        issues.append("Unity Tower state 40 is forbidden in the stalemate scope")
    if re.search(r"\bprovince\s*=\s*16428\b", combined):
        issues.append("Unity Tower province 16428 is forbidden in the stalemate scope")

    gameplay = _gameplay_texts(root)
    gameplay_joined = "\n".join(text for _, text in gameplay)
    for flag in SCHEDULED_FLAGS + RESOLVED_FLAGS:
        if len(re.findall(rf"set_country_flag\s*=\s*{re.escape(flag)}\b", gameplay_joined)) != 1:
            issues.append(f"permanent one-shot flag must have exactly one writer: {flag}")
        if re.search(rf"clr_country_flag\s*=\s*{re.escape(flag)}\b", gameplay_joined):
            issues.append(f"permanent one-shot flag must never be cleared: {flag}")
    for flag in ACTIVE_FLAGS:
        if len(re.findall(rf"set_country_flag\s*=\s*\{{[^}}]*\b{re.escape(flag)}\b", gameplay_joined)) != 1:
            issues.append(f"timed active flag must have exactly one writer: {flag}")
    if gameplay_joined.count("add_timed_idea = { idea = ADISCORD_vorkerland_ai_breakthrough_window days = 75 }") != 2:
        issues.append("operational idea must have exactly two bounded gameplay writers")

    registry_text = texts.get(REGISTRY, "")
    if registry_text:
        try:
            registry = json.loads(registry_text)
        except json.JSONDecodeError as exc:
            issues.append(f"event registry is not valid JSON: {exc}")
        else:
            entries = {entry.get("id"): entry for entry in registry.get("events", [])}
            for number in (1, 2):
                event_id = f"ADISCORD_vorkerland_stalemate.{number}"
                expected = {
                    "namespace": "ADISCORD_vorkerland_stalemate",
                    "number": number,
                    "owner": EVENTS,
                    "subsystem": "vorkerland_stalemate",
                    "status": "active",
                }
                entry = entries.get(event_id)
                if entry is None:
                    issues.append(f"event registry is missing {event_id}")
                else:
                    for key, value in expected.items():
                        if entry.get(key) != value:
                            issues.append(f"event registry drift for {event_id}: {key} != {value}")

    for relative in (ENGLISH, RUSSIAN):
        loc = texts.get(relative, "")
        for key in (
            "ADISCORD_vorkerland_ai_breakthrough_window:0",
            "ADISCORD_vorkerland_ai_breakthrough_window_desc:0",
        ):
            if loc.count(key) != 1:
                issues.append(f"{relative}: localisation key count is not one: {key}")
    russian_path = root / RUSSIAN
    if russian_path.is_file() and not russian_path.read_bytes().startswith(b"\xef\xbb\xbf"):
        issues.append("Russian stalemate localisation must retain the UTF-8 BOM")

    return issues


def main() -> int:
    issues = collect_issues()
    if issues:
        print("Vorkerland stalemate validation failed:")
        for issue in issues:
            print(f"- {issue}")
        return 1
    print("Vorkerland stalemate validation passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
