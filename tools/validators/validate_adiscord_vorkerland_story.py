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
CAMPAIGN_STATE_EFFECTS = Path(
    "common/scripted_effects/ADISCORD_vorkerland_campaign_state_effects.txt"
)
PHASE_EVENTS = Path("events/ADISCORD_vorkerland_phase_events.txt")
COLLAPSE_EVENTS = Path("events/ADISCORD_vorkerland_collapse_events.txt")
CIVIL_WAR_FOCUS = Path("common/national_focus/ADISCORD_vorkerland_civil_war_focus.txt")

STORY_NUMBERS = (
    1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13,
    31, 32, 33, 34, 35, 36,
    41, 42, 43,
    50, 51, 52, 53, 54, 55, 56, 57, 58, 59, 60, 61,
)
STORY_IDS = tuple(f"ADISCORD_vorkerland_story.{number}" for number in STORY_NUMBERS)
COUNTRY_EVENT_NUMBERS = frozenset((5, 6))

SHOWDOWN_ID = "ADISCORD_vorkerland_story.1"
COMMAND_CHOICE_ID = "ADISCORD_vorkerland_story.5"
POSTWAR_ID = "ADISCORD_vorkerland_story.6"

OBJECTIVE_VARIABLE = "global.ADISCORD_vorkerland_objective_last"

WORKER_FATE_DISPATCH = (
    ("ADISCORD_vorkerland_worker_safe_with_loyalists", "ADISCORD_vorkerland_story.10"),
    ("ADISCORD_vorkerland_worker_rescued_by_vlad", "ADISCORD_vorkerland_story.11"),
    ("ADISCORD_vorkerland_worker_missing", "ADISCORD_vorkerland_story.12"),
    ("ADISCORD_vorkerland_worker_killed", "ADISCORD_vorkerland_story.13"),
)

VARIANT_DISPATCH = (
    ("ADISCORD_vorkerland_wkr_variant_neo_vorkerist", "ADISCORD_vorkerland_story.31"),
    ("ADISCORD_vorkerland_wkr_variant_utilitarian", "ADISCORD_vorkerland_story.32"),
    ("ADISCORD_vorkerland_vad_variant_imperial", "ADISCORD_vorkerland_story.33"),
    ("ADISCORD_vorkerland_vad_variant_joint", "ADISCORD_vorkerland_story.34"),
    ("ADISCORD_vorkerland_tva_variant_throughput", "ADISCORD_vorkerland_story.35"),
    ("ADISCORD_vorkerland_tva_variant_preservation", "ADISCORD_vorkerland_story.36"),
)

OBJECTIVE_DISPATCH = (
    (1, "ADISCORD_vorkerland_story.50"),
    (2, "ADISCORD_vorkerland_story.51"),
    (3, "ADISCORD_vorkerland_story.52"),
    (4, "ADISCORD_vorkerland_story.53"),
    (5, "ADISCORD_vorkerland_story.54"),
    (6, "ADISCORD_vorkerland_story.55"),
    (7, "ADISCORD_vorkerland_story.56"),
    (8, "ADISCORD_vorkerland_story.57"),
    (9, "ADISCORD_vorkerland_story.58"),
    (10, "ADISCORD_vorkerland_story.59"),
    (11, "ADISCORD_vorkerland_story.60"),
    (12, "ADISCORD_vorkerland_story.61"),
)

CAPITULATION_DISPATCH = (
    ("WKR", "ADISCORD_vorkerland_story.41"),
    ("VAD", "ADISCORD_vorkerland_story.42"),
    ("TVA", "ADISCORD_vorkerland_story.43"),
)

# The claimant capitals already have dedicated first-fall reports, so the iconic
# objective report must stand down for them instead of announcing the same city
# twice on the same day.
CAPITAL_OBJECTIVE_SUPPRESSION = (
    (1, "ADISCORD_vorkerland_story_wkr_capital_fell_first"),
    (2, "ADISCORD_vorkerland_story_vad_capital_fell_first"),
    (3, "ADISCORD_vorkerland_story_tva_capital_fell_first"),
)

WORKER_FATE_EFFECT = "ADISCORD_vorkerland_story_report_worker_fate"
OBJECTIVE_EFFECT = "ADISCORD_vorkerland_story_report_iconic_objective"
VARIANT_EFFECT = "ADISCORD_vorkerland_story_report_variant_declaration"
CAPITULATION_EFFECT = "ADISCORD_vorkerland_story_report_claimant_capitulation"

# Call sites the story layer cannot add itself. Each entry is
# (effect, owning file, human-readable location).
EXTERNAL_DISPATCH = (
    (
        WORKER_FATE_EFFECT,
        COLLAPSE_EVENTS,
        "ADISCORD_vorkerland_collapse.1 immediate, after the Worker fate roll",
    ),
    (
        VARIANT_EFFECT,
        CIVIL_WAR_FOCUS,
        "each of the six completion_reward blocks that set an "
        "ADISCORD_vorkerland_{tag}_variant_{key} country flag",
    ),
)

# Tokens that look plausible next to set_global_flag but do not exist in the
# script API. Global arrays are addressed as add_to_array/is_in_array with a
# global. prefix, and a mistyped token fails silently at runtime.
UNDEFINED_ARRAY_TOKENS = (
    "add_to_global_array",
    "is_in_global_array",
    "remove_from_global_array",
    "clear_global_array",
)

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

CYRILLIC = re.compile(r"[\u0400-\u04FF]")


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


def localisation_entries(text: str) -> list[tuple[str, str]]:
    return re.findall(r'(?m)^\s*([A-Za-z0-9_.]+):(?:\d+)?\s*"(.*)"\s*$', text)


def localisation_keys(text: str) -> set[str]:
    return {key for key, _ in localisation_entries(text)}


def dispatch_target(block: str, anchor: str, pattern: re.Pattern[str]) -> str | None:
    """First value produced after ``anchor`` inside ``block``.

    This is what catches a branch that tests one outcome and then fires the
    neighbouring outcome's event, which is the failure mode a wall of copied
    blocks produces most often.
    """
    position = block.find(anchor)
    if position < 0:
        return None
    match = pattern.search(block, position)
    return match.group(1) if match else None


def pending_external_dispatch(root: Path = ROOT) -> list[str]:
    """Story dispatchers whose only possible call site is another effort's file."""
    pending: list[str] = []
    for effect, owner, location in EXTERNAL_DISPATCH:
        path = root / owner
        source = path.read_text(encoding="utf-8-sig") if path.is_file() else ""
        if f"{effect} = yes" not in strip_comments(source):
            pending.append(f"{effect} = yes -> {owner.as_posix()} ({location})")
    return pending


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
    campaign_state_effects = read(root, CAMPAIGN_STATE_EFFECTS, issues)
    phase_events = read(root, PHASE_EVENTS, issues)

    for relative, source in (
        (STORY_EVENTS, story_events),
        (STORY_EFFECTS, story_effects),
        (NEWS_EVENTS, news),
        (ON_ACTIONS, on_actions),
        (PHASE_EFFECTS, phase_effects),
        (CAMPAIGN_STATE_EFFECTS, campaign_state_effects),
        (PHASE_EVENTS, phase_events),
    ):
        if source and not balanced(source):
            issues.append(f"unbalanced Clausewitz braces in {relative.as_posix()}")

    if "add_namespace = ADISCORD_vorkerland_story" not in story_events:
        issues.append("story event namespace is missing or drifted")

    definitions = event_blocks(story_events)
    for number, event_id in zip(STORY_NUMBERS, STORY_IDS):
        found = definitions.get(event_id)
        if not found:
            issues.append(f"missing story event {event_id}")
            continue
        expected_kind = (
            "country_event" if number in COUNTRY_EVENT_NUMBERS else "news_event"
        )
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
    story_source = strip_comments(story_events + "\n" + story_effects)
    for token in UNDEFINED_ARRAY_TOKENS:
        if token in story_source:
            issues.append(
                f"story layer uses {token}, which the script API does not define; "
                "use the array argument with a global. prefix instead"
            )
    showdown = definitions.get(SHOWDOWN_ID, ("", ""))[1]
    if "picture = GFX_event_china_civil_war_1" not in showdown:
        issues.append("verified showdown news must use the registered neutral civil-war picture")
    if 'name = "GFX_event_china_civil_war_1"' not in event_pictures:
        issues.append("neutral civil-war event picture is not registered in A-Discord")

    event_five = definitions.get(COMMAND_CHOICE_ID, ("", ""))[1]
    if event_five.count("option = {") != 2:
        issues.append("story.5 must offer exactly two command-apparatus choices")
    for token in (
        "ADISCORD_vorkerland_story_rival_headquarters_integrated",
        "ADISCORD_vorkerland_story_rival_apparatus_dissolved",
    ):
        if token not in event_five:
            issues.append(f"story.5 is missing outcome {token}")

    event_six = definitions.get(POSTWAR_ID, ("", ""))[1]
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

    issues.extend(dispatch_issues(story_effects))

    english_entries = dict(localisation_entries(english))
    russian_entries = dict(localisation_entries(russian))
    english_keys = set(english_entries)
    russian_keys = set(russian_entries)
    required_story_loc = {
        *(
            f"ADISCORD_vorkerland_story.{number}.{suffix}"
            for number in STORY_NUMBERS
            if number != 6
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

    issues.extend(
        localisation_quality_issues(
            english, russian, english_entries, russian_entries, required_story_loc
        )
    )

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

        issues.extend(upstream_contract_issues(root, campaign_state_effects))

    return issues


def dispatch_issues(story_effects: str) -> list[str]:
    """Every reported outcome must reach the presentation that belongs to it."""
    issues: list[str] = []
    news_pattern = re.compile(r"news_event\s*=\s*\{\s*id\s*=\s*([A-Za-z0-9_.]+)")

    fate = named_block(story_effects, WORKER_FATE_EFFECT)
    if not fate:
        issues.append(f"story effects are missing {WORKER_FATE_EFFECT}")
    else:
        for flag, event_id in WORKER_FATE_DISPATCH:
            target = dispatch_target(fate, f"has_global_flag = {flag}", news_pattern)
            if target is None:
                issues.append(f"{WORKER_FATE_EFFECT} never reads {flag}")
            elif target != event_id:
                issues.append(
                    f"{WORKER_FATE_EFFECT} dispatches {target} for {flag}, expected {event_id}"
                )
        if "clr_global_flag = ADISCORD_vorkerland_story_worker_fate_reported" not in fate:
            issues.append(
                f"{WORKER_FATE_EFFECT} must release its guard when no fate flag is set, "
                "or an early call silences the report for the whole campaign"
            )

    objective = named_block(story_effects, OBJECTIVE_EFFECT)
    if not objective:
        issues.append(f"story effects are missing {OBJECTIVE_EFFECT}")
    else:
        if f"var = {OBJECTIVE_VARIABLE}" not in objective:
            issues.append(f"{OBJECTIVE_EFFECT} must read {OBJECTIVE_VARIABLE}")
        if "ADISCORD_vorkerland_story_objectives_reported" not in objective:
            issues.append(
                f"{OBJECTIVE_EFFECT} must record reported objectives so one centre "
                "cannot be announced twice"
            )
        for value, event_id in OBJECTIVE_DISPATCH:
            target = dispatch_target(
                objective,
                (
                    f"limit = {{ check_variable = {{ var = {OBJECTIVE_VARIABLE} "
                    f"value = {value} compare = equals }} }}"
                ),
                news_pattern,
            )
            if target is None:
                issues.append(f"{OBJECTIVE_EFFECT} never reads objective {value}")
            elif target != event_id:
                issues.append(
                    f"{OBJECTIVE_EFFECT} dispatches {target} for objective {value}, "
                    f"expected {event_id}"
                )
        for value, flag in CAPITAL_OBJECTIVE_SUPPRESSION:
            suppression = re.search(
                rf"value = {value} compare = equals \}}\s*\n\s*has_global_flag = {re.escape(flag)}",
                objective,
            )
            if not suppression:
                issues.append(
                    f"{OBJECTIVE_EFFECT} must suppress objective {value} once {flag} "
                    "has already announced that capital"
                )

    variant = named_block(story_effects, VARIANT_EFFECT)
    if not variant:
        issues.append(f"story effects are missing {VARIANT_EFFECT}")
    else:
        for flag, event_id in VARIANT_DISPATCH:
            target = dispatch_target(variant, f"has_country_flag = {flag}", news_pattern)
            if target is None:
                issues.append(f"{VARIANT_EFFECT} never reads {flag}")
            elif target != event_id:
                issues.append(
                    f"{VARIANT_EFFECT} dispatches {target} for {flag}, expected {event_id}"
                )

    capitulation = named_block(story_effects, CAPITULATION_EFFECT)
    if not capitulation:
        issues.append(f"story effects are missing {CAPITULATION_EFFECT}")
    else:
        for tag, event_id in CAPITULATION_DISPATCH:
            target = dispatch_target(capitulation, f"tag = {tag}", news_pattern)
            if target is None:
                issues.append(f"{CAPITULATION_EFFECT} never reads {tag}")
            elif target != event_id:
                issues.append(
                    f"{CAPITULATION_EFFECT} dispatches {target} for {tag}, expected {event_id}"
                )

    # Both of these dispatchers are reached from story-owned effects that
    # on_state_control_changed and on_capitulation already call, so they need no
    # hook outside the story files and must not silently lose the call.
    capital_fall = named_block(
        story_effects, "ADISCORD_vorkerland_story_check_first_claimant_capital_fall"
    )
    if f"{OBJECTIVE_EFFECT} = yes" not in capital_fall:
        issues.append(
            "iconic-objective news is unreachable: the state-control story entry point "
            f"no longer calls {OBJECTIVE_EFFECT}"
        )
    command_choice = named_block(
        story_effects, "ADISCORD_vorkerland_story_offer_first_claimant_command_choice"
    )
    if f"{CAPITULATION_EFFECT} = yes" not in command_choice:
        issues.append(
            "claimant-capitulation news is unreachable: the capitulation story entry "
            f"point no longer calls {CAPITULATION_EFFECT}"
        )
    elif f"ROOT = {{ {CAPITULATION_EFFECT} = yes }}" not in command_choice:
        issues.append(
            f"{CAPITULATION_EFFECT} must be scoped to ROOT: on_capitulation calls the "
            "entry point inside FROM, the winner, so an unscoped call would name the "
            "victor as the claimant that fell"
        )
    return issues


def localisation_quality_issues(
    english: str,
    russian: str,
    english_entries: dict[str, str],
    russian_entries: dict[str, str],
    required: set[str],
) -> list[str]:
    """Catch empty, duplicated, untranslated and copy-pasted story strings."""
    issues: list[str] = []
    for language, source in (("English", english), ("Russian", russian)):
        seen: set[str] = set()
        repeated: set[str] = set()
        for key, _ in localisation_entries(source):
            if key in seen:
                repeated.add(key)
            seen.add(key)
        duplicates = sorted(repeated)
        if duplicates:
            issues.append(
                f"{language} story localisation defines duplicate keys: {', '.join(duplicates)}"
            )

    for key in sorted(required):
        english_value = english_entries.get(key, "")
        russian_value = russian_entries.get(key, "")
        if key in english_entries and not english_value.strip():
            issues.append(f"English story localisation {key} is empty")
        if key in russian_entries and not russian_value.strip():
            issues.append(f"Russian story localisation {key} is empty")
        if russian_value and not CYRILLIC.search(russian_value):
            issues.append(f"Russian story localisation {key} contains no Cyrillic text")
        if english_value and CYRILLIC.search(english_value):
            issues.append(f"English story localisation {key} contains Cyrillic text")

    # Each variant of a shared event must be written, not copied. Comparing the
    # bodies is what would have caught the reference mod reusing one city's text
    # for another.
    families: list[tuple[str, list[str]]] = [
        ("Worker fate", [f"ADISCORD_vorkerland_story.{number}.d" for number in (10, 11, 12, 13)]),
        (
            "Iconic objective",
            [f"ADISCORD_vorkerland_story.{number}.d" for number in range(50, 62)],
        ),
        (
            "Claimant capitulation",
            [f"ADISCORD_vorkerland_story.{number}.d" for number in (41, 42, 43)],
        ),
    ]
    for label, keys in families:
        for language, entries in (("English", english_entries), ("Russian", russian_entries)):
            values = [entries[key] for key in keys if entries.get(key, "").strip()]
            if len(values) != len(set(values)):
                issues.append(
                    f"{language} {label} descriptions repeat the same text across variants"
                )
    return issues


def upstream_contract_issues(root: Path, campaign_state_effects: str) -> list[str]:
    """Guard the identifiers the news layer reads out of other efforts' files."""
    issues: list[str] = []
    resolve = named_block(
        campaign_state_effects, "ADISCORD_vorkerland_resolve_iconic_objective"
    )
    if not resolve:
        issues.append(
            "iconic-objective news has no upstream: "
            "ADISCORD_vorkerland_resolve_iconic_objective is gone"
        )
    elif f"var = {OBJECTIVE_VARIABLE}" not in resolve:
        issues.append(
            f"iconic-objective news reads {OBJECTIVE_VARIABLE}, which "
            "ADISCORD_vorkerland_resolve_iconic_objective no longer writes"
        )

    collapse_path = root / COLLAPSE_EVENTS
    collapse = collapse_path.read_text(encoding="utf-8-sig") if collapse_path.is_file() else ""
    for flag, _ in WORKER_FATE_DISPATCH:
        if f"set_global_flag = {flag}" not in collapse:
            issues.append(f"Worker fate news reads {flag}, which the collapse layer no longer sets")

    focus_path = root / CIVIL_WAR_FOCUS
    focus = focus_path.read_text(encoding="utf-8-sig") if focus_path.is_file() else ""
    for flag, _ in VARIANT_DISPATCH:
        if f"set_country_flag = {flag}" not in focus:
            issues.append(f"variant news reads {flag}, which the focus tree no longer sets")
    return issues


def main() -> int:
    issues = collect_issues()
    pending = pending_external_dispatch()
    if issues:
        print("Vorkerland story/news validation failed:")
        for issue in issues:
            print(f"- {issue}")
        return 1
    print("Vorkerland story/news validation passed.")
    if pending:
        print("Pending external wiring (call sites owned by other efforts):")
        for entry in pending:
            print(f"- {entry}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
