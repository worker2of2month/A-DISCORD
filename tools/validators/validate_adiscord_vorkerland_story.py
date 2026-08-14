#!/usr/bin/env python3
"""Validate the bounded Vorkerland civil-war story and news layer."""

from __future__ import annotations

import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]

STORY_EVENTS = Path("events/ADISCORD_vorkerland_story_events.txt")
STORY_EFFECTS = Path("common/scripted_effects/ADISCORD_vorkerland_story_effects.txt")
ENGLISH_LOC = Path("localisation/english/ADISCORD_vorkerland_story_l_english.yml")
RUSSIAN_LOC = Path("localisation/russian/ADISCORD_vorkerland_story_l_russian.yml")
NEWS_EVENTS = Path("events/ADISCORD_news.txt")
EVENT_PICTURES = Path("interface/ADISCORD_eventpictures.gfx")
ON_ACTIONS = Path("common/on_actions/01_ADISCORD_vorkerland_collapse_on_actions.txt")
PHASE_EFFECTS = Path("common/scripted_effects/ADISCORD_vorkerland_phase_effects.txt")
PHASE_EVENTS = Path("events/ADISCORD_vorkerland_phase_events.txt")

STORY_IDS = tuple(f"ADISCORD_vorkerland_story.{number}" for number in range(1, 10))
NEWS_IDS = frozenset((*STORY_IDS[:4], *STORY_IDS[6:]))
COUNTRY_IDS = frozenset((STORY_IDS[4], STORY_IDS[5]))

FORBIDDEN_MUTATIONS = (
    "annex_country",
    "declare_war_on",
    "puppet",
    "set_autonomy",
    "set_state_controller_to",
    "set_state_owner",
    "start_civil_war",
    "transfer_state",
    "white_peace",
)


def read(root: Path, relative: Path, issues: list[str]) -> str:
    path = root / relative
    if not path.is_file():
        issues.append(f"missing required file {relative.as_posix()}")
        return ""
    try:
        return path.read_text(encoding="utf-8-sig")
    except UnicodeError as exc:
        issues.append(f"cannot decode {relative.as_posix()} as UTF-8: {exc}")
        return ""


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


def _braced_block(text: str, start: int, brace_start: int) -> str:
    depth = 0
    for index in range(brace_start, len(text)):
        if text[index] == "{":
            depth += 1
        elif text[index] == "}":
            depth -= 1
            if depth == 0:
                return text[start : index + 1]
    return ""


def named_blocks(text: str, name: str) -> list[str]:
    blocks: list[str] = []
    pattern = re.compile(rf"(?<![A-Za-z0-9_]){re.escape(name)}\s*=\s*\{{")
    for match in pattern.finditer(text):
        brace_start = text.find("{", match.start())
        block = _braced_block(text, match.start(), brace_start)
        if block:
            blocks.append(block)
    return blocks


def named_block(text: str, name: str) -> str:
    blocks = named_blocks(text, name)
    return blocks[0] if blocks else ""


def event_blocks(text: str) -> dict[str, tuple[str, str]]:
    results: dict[str, tuple[str, str]] = {}
    pattern = re.compile(r"(?m)^\s*(country_event|news_event)\s*=\s*\{")
    for match in pattern.finditer(text):
        brace_start = text.find("{", match.start())
        block = _braced_block(text, match.start(), brace_start)
        event_id = re.search(r"(?m)^\s*id\s*=\s*([A-Za-z0-9_]+\.\d+)\s*$", block)
        if event_id:
            results[event_id.group(1)] = (match.group(1), block)
    return results


def forbidden_story_mutations(text: str) -> list[str]:
    clean = strip_comments(text)
    return [
        token
        for token in FORBIDDEN_MUTATIONS
        if re.search(rf"(?<![A-Za-z0-9_]){re.escape(token)}(?:\s*=|\s+)", clean)
    ]


def localisation_keys(text: str) -> set[str]:
    return set(re.findall(r'(?m)^\s*([A-Za-z0-9_.]+):(?:\d+)?\s*"', text))


def collect_issues(root: Path = ROOT, *, require_hooks: bool = True) -> list[str]:
    issues: list[str] = []
    story_events = read(root, STORY_EVENTS, issues)
    story_effects = read(root, STORY_EFFECTS, issues)
    english = read(root, ENGLISH_LOC, issues)
    russian = read(root, RUSSIAN_LOC, issues)
    news = read(root, NEWS_EVENTS, issues)
    event_pictures = read(root, EVENT_PICTURES, issues)
    on_actions = read(root, ON_ACTIONS, issues)
    phase_effects = read(root, PHASE_EFFECTS, issues)
    phase_events = read(root, PHASE_EVENTS, issues)

    for relative, source in (
        (STORY_EVENTS, story_events),
        (STORY_EFFECTS, story_effects),
        (NEWS_EVENTS, news),
        (ON_ACTIONS, on_actions),
        (PHASE_EFFECTS, phase_effects),
        (PHASE_EVENTS, phase_events),
    ):
        if source and not balanced(source):
            issues.append(f"unbalanced Clausewitz braces in {relative.as_posix()}")

    if "add_namespace = ADISCORD_vorkerland_story" not in story_events:
        issues.append("story event namespace is missing or drifted")

    definitions = event_blocks(story_events)
    for event_id in STORY_IDS:
        found = definitions.get(event_id)
        if not found:
            issues.append(f"missing story event {event_id}")
            continue
        expected_kind = "news_event" if event_id in NEWS_IDS else "country_event"
        if found[0] != expected_kind:
            issues.append(f"{event_id} must be a {expected_kind}, found {found[0]}")
        if "is_triggered_only = yes" not in found[1]:
            issues.append(f"{event_id} must be triggered-only")
        if "fire_only_once = yes" not in found[1]:
            issues.append(f"{event_id} must be fire-only-once")

    extras = sorted(set(definitions) - set(STORY_IDS))
    if extras:
        issues.append("unexpected story event IDs: " + ", ".join(extras))

    forbidden = forbidden_story_mutations(story_events + "\n" + story_effects)
    if forbidden:
        issues.append("story layer owns forbidden map/war/peace mutations: " + ", ".join(forbidden))
    if "ADISCORD_superevent_news.2" in story_events + story_effects:
        issues.append("story layer references hazardous legacy ADISCORD_superevent_news.2")
    if "GFX_event_vorkerland_explosion" in story_events:
        issues.append("non-explosion story events must not reuse the collapse explosion picture")
    if "add_army_experience" in story_events:
        issues.append("story events use invalid add_army_experience instead of army_experience")
    showdown = definitions.get(STORY_IDS[0], ("", ""))[1]
    if "picture = GFX_event_china_civil_war_1" not in showdown:
        issues.append("verified showdown news must use the registered neutral civil-war picture")
    if 'name = "GFX_event_china_civil_war_1"' not in event_pictures:
        issues.append("neutral civil-war event picture is not registered in A-Discord")

    event_five = definitions.get(STORY_IDS[4], ("", ""))[1]
    if event_five.count("option = {") != 2:
        issues.append("story.5 must offer exactly two command-apparatus choices")
    for token in (
        "ADISCORD_vorkerland_story_rival_headquarters_integrated",
        "ADISCORD_vorkerland_story_rival_apparatus_dissolved",
    ):
        if token not in event_five:
            issues.append(f"story.5 is missing outcome {token}")

    event_six = definitions.get(STORY_IDS[5], ("", ""))[1]
    if event_six.count("option = {") != 6:
        issues.append("story.6 must offer exactly two choices for each of three routes")
    for route in ("route_worker", "route_joint", "route_utilitarian"):
        if event_six.count(f"has_country_flag = ADISCORD_vorkerland_{route}") < 3:
            issues.append(f"story.6 does not provide a description and two choices for {route}")
    if "ADISCORD_vorkerland_story.6.worx.d" not in event_six:
        issues.append("story.6 route_utilitarian is missing its Doctor Worx description")

    required_effect_tokens = (
        "ADISCORD_vorkerland_story_showdown_announced",
        "ADISCORD_vorkerland_story_first_claimant_capital_fell",
        "32 = { is_controlled_by = ROOT }",
        "75 = { is_controlled_by = ROOT }",
        "36 = { is_controlled_by = ROOT }",
        "tag = WTD",
        "tag = VLA",
        "tag = SOL",
        "OVERLORD =",
        "ADISCORD_vorkerland_story_first_claimant_capitulated",
        "ADISCORD_vorkerland_story_postwar_event_offered",
        "ADISCORD_vorkerland_story_postwar_choice_resolved",
    )
    for token in required_effect_tokens:
        if token not in story_effects:
            issues.append(f"story effects are missing contract token {token}")

    english_keys = localisation_keys(english)
    russian_keys = localisation_keys(russian)
    required_story_loc = {
        *(
            f"ADISCORD_vorkerland_story.{number}.{suffix}"
            for number in (1, 2, 3, 4, 5, 7, 8, 9)
            for suffix in ("t", "d", "a")
        ),
        "ADISCORD_vorkerland_story.5.b",
        "ADISCORD_vorkerland_story.6.t",
        "ADISCORD_vorkerland_story.6.worker.d",
        "ADISCORD_vorkerland_story.6.joint.d",
        "ADISCORD_vorkerland_story.6.worx.d",
        "ADISCORD_vorkerland_story.6.worker.a",
        "ADISCORD_vorkerland_story.6.worker.b",
        "ADISCORD_vorkerland_story.6.joint.a",
        "ADISCORD_vorkerland_story.6.joint.b",
        "ADISCORD_vorkerland_story.6.worx.a",
        "ADISCORD_vorkerland_story.6.worx.b",
    }
    for language, keys in (("English", english_keys), ("Russian", russian_keys)):
        missing = sorted(required_story_loc - keys)
        if missing:
            issues.append(f"{language} story localisation is missing: {', '.join(missing)}")
    for number in (1, 2):
        for suffix in ("t", "d", "a"):
            key = f"ADISCORD_vorkerland_news.{number}.{suffix}"
            if key not in english_keys:
                issues.append(f"English Ivanland news localisation is missing {key}")

    russian_path = root / RUSSIAN_LOC
    if russian_path.is_file() and not russian_path.read_bytes().startswith(b"\xef\xbb\xbf"):
        issues.append("Russian story localisation must use UTF-8 BOM")
    for token in ("Doctor Dorian Worx", "technocratic", "technocracy"):
        if token not in english:
            issues.append(f"English route_utilitarian presentation is missing {token!r}")
    for token in ("доктора Дориана Воркса", "технократи"):
        if token not in russian:
            issues.append(f"Russian route_utilitarian presentation is missing {token!r}")

    news_definitions = event_blocks(news)
    opening = news_definitions.get("ADISCORD_superevent_news.1", ("", ""))[1]
    opening_immediate = named_block(opening, "immediate")
    opening_options = named_blocks(opening, "option")
    for token in (
        "superevent_vorkerland_civilwar",
        "ADISCORD_superevent_audio.1",
        "every_country =",
    ):
        if token not in opening_immediate:
            issues.append(f"opening collapse superevent immediate is missing {token}")
    if any(
        token in option
        for option in opening_options
        for token in ("superevent_vorkerland_civilwar", "ADISCORD_superevent_audio.1")
    ):
        issues.append("opening collapse presentation still depends on clicking its option")

    if require_hooks:
        showdown_effect = named_block(phase_effects, "ADISCORD_vorkerland_verify_central_showdown")
        if "ADISCORD_vorkerland_story_announce_verified_showdown = yes" not in showdown_effect:
            issues.append("verified central-showdown caller is missing the story announcement hook")

        state_control = named_block(on_actions, "on_state_control_changed")
        if "ADISCORD_vorkerland_story_check_first_claimant_capital_fall = yes" not in state_control:
            issues.append("on_state_control_changed is missing the first-capital story hook")
        capitulation = named_block(on_actions, "on_capitulation")
        if "ADISCORD_vorkerland_story_offer_first_claimant_command_choice = yes" not in capitulation:
            issues.append("central capitulation path is missing the winner story hook")
        monthly = named_block(on_actions, "on_monthly")
        if "ADISCORD_vorkerland_story" in monthly:
            issues.append("story layer must not use monthly polling")

        phase_seven = event_blocks(phase_events).get("ADISCORD_vorkerland_phase.7", ("", ""))[1]
        if "ADISCORD_vorkerland_story_offer_post_reunification = yes" not in phase_seven:
            issues.append("phase.7 is missing the verified post-reunification story hook")

    return issues


def main() -> int:
    issues = collect_issues()
    if issues:
        print("Vorkerland story/news validation failed:")
        for issue in issues:
            print(f"- {issue}")
        return 1
    print("Vorkerland story/news validation passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
