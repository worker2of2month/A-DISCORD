#!/usr/bin/env python3
"""Validate bounded SOL/VLA diplomacy and explicit postwar WRK core packages.

This is intentionally a RED-to-GREEN contract validator.  It describes the
public scripted triggers/effects/decisions used by the Vorkerland phase
controller without owning their gameplay implementation.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[2]

DIPLOMACY_TRIGGERS = Path("common/scripted_triggers/ADISCORD_vorkerland_diplomacy_triggers.txt")
DIPLOMACY_EFFECTS = Path("common/scripted_effects/ADISCORD_vorkerland_diplomacy_effects.txt")
DIPLOMACY_DECISIONS = Path("common/decisions/ADISCORD_vorkerland_diplomacy_decisions.txt")
FOCUS_DECISIONS = Path("common/decisions/ADISCORD_vorkerland_focus_decisions.txt")
FOCUS_DECISION_EFFECTS = Path(
    "common/scripted_effects/ADISCORD_vorkerland_focus_decision_effects.txt"
)
DIPLOMACY_EVENTS = Path("events/ADISCORD_vorkerland_diplomacy_events.txt")
DIPLOMACY_ON_ACTIONS = Path("common/on_actions/03_ADISCORD_vorkerland_diplomacy_on_actions.txt")
PHASE_EFFECTS = Path("common/scripted_effects/ADISCORD_vorkerland_phase_effects.txt")
PHASE_EVENTS = Path("events/ADISCORD_vorkerland_phase_events.txt")
COLLAPSE_EFFECTS = Path("common/scripted_effects/ADISCORD_vorkerland_collapse_effects.txt")
FOCUS_FILE = Path("common/national_focus/ADISCORD_vorkerland_civil_war_focus.txt")
COLLAPSE_AI = Path("common/ai_strategy/ADISCORD_vorkerland_collapse_ai.txt")
WKR_AI_PLANS = Path(
    "common/ai_strategy_plans/ADISCORD_vorkerland_wkr_wartime_plan.txt"
)
COUNTRY_COSMETICS = Path("common/countries/cosmetic.txt")
DIPLOMACY_ENGLISH = Path("localisation/english/ADISCORD_vorkerland_diplomacy_l_english.yml")
DIPLOMACY_RUSSIAN = Path("localisation/russian/ADISCORD_vorkerland_diplomacy_l_russian.yml")
EVENT_ID_REGISTRY = Path("tools/data/adiscord_event_ids.json")

SOLAR_STATES = (76, 104, 198, 307, 310)
VOLNOGRAD_STATES = (74, 105, 197, 311, 312, 313, 314)

TERMINAL_CONTRACTS = {
    "ADISCORD_vorkerland_solar_terminal_sol": (
        "SOL",
        ("SRA", "CSL"),
        SOLAR_STATES,
        "ADISCORD_vorkerland_solar_winner_sol",
        "ADISCORD_vorkerland_solar_terminal_verified",
    ),
    "ADISCORD_vorkerland_solar_terminal_sra": (
        "SRA",
        ("SOL", "CSL"),
        SOLAR_STATES,
        "ADISCORD_vorkerland_solar_winner_sra",
        "ADISCORD_vorkerland_solar_terminal_verified",
    ),
    "ADISCORD_vorkerland_solar_terminal_csl": (
        "CSL",
        ("SOL", "SRA"),
        SOLAR_STATES,
        "ADISCORD_vorkerland_solar_winner_csl",
        "ADISCORD_vorkerland_solar_terminal_verified",
    ),
    "ADISCORD_vorkerland_volnograd_terminal_vla": (
        "VLA",
        ("EBA", "TGD"),
        VOLNOGRAD_STATES,
        "ADISCORD_vorkerland_volnograd_winner_vla",
        "ADISCORD_vorkerland_volnograd_terminal_verified",
    ),
    "ADISCORD_vorkerland_volnograd_terminal_eba": (
        "EBA",
        ("VLA", "TGD"),
        VOLNOGRAD_STATES,
        "ADISCORD_vorkerland_volnograd_winner_eba",
        "ADISCORD_vorkerland_volnograd_terminal_verified",
    ),
    "ADISCORD_vorkerland_volnograd_terminal_tgd": (
        "TGD",
        ("VLA", "EBA"),
        VOLNOGRAD_STATES,
        "ADISCORD_vorkerland_volnograd_winner_tgd",
        "ADISCORD_vorkerland_volnograd_terminal_verified",
    ),
}

OUTCOME_RECORDER = "ADISCORD_vorkerland_record_regional_diplomacy_outcomes"
VAD_SOL_OFFER = "ADISCORD_vorkerland_offer_vad_sol_alliance"
WKR_VLA_OFFER = "ADISCORD_vorkerland_offer_wkr_vla_alliance"
VAD_INTERVENTION_BORDER = "ADISCORD_vorkerland_vad_has_solar_intervention_border"
WKR_COUNTER_BORDER = "ADISCORD_vorkerland_wkr_has_solar_counter_border"
VAD_INTERVENTION = "ADISCORD_vorkerland_attempt_vad_solar_intervention"
RESERVE_VAD_INTERVENTION = "ADISCORD_vorkerland_reserve_vad_solar_intervention"
CANCEL_VAD_INTERVENTION_RESERVATION = (
    "ADISCORD_vorkerland_cancel_vad_solar_intervention_reservation"
)
VERIFY_VAD_INTERVENTION = "ADISCORD_vorkerland_verify_vad_solar_intervention"
CLEAR_FAILED_VAD_INTERVENTION = "ADISCORD_vorkerland_clear_failed_vad_solar_intervention"
RESTORE_SOL = "ADISCORD_vorkerland_restore_sol_as_vad_puppet"
VERIFY_SOL = "ADISCORD_vorkerland_verify_sol_restoration"
ARM_WKR_COUNTER = "ADISCORD_vorkerland_arm_wkr_solar_counter_intervention"
JOIN_ALLIES = "ADISCORD_vorkerland_join_regional_allies_to_showdown"

VAD_SOL_ACCEPTED = "ADISCORD_vorkerland_vad_sol_alliance_accepted"
WKR_VLA_ACCEPTED = "ADISCORD_vorkerland_wkr_vla_alliance_accepted"
SOL_RESTORATION_INITIALIZED = "ADISCORD_vorkerland_sol_restoration_initialized"
SOL_RESTORATION_VERIFIED = "ADISCORD_vorkerland_sol_restoration_verified"
WKR_COUNTER_READY = "ADISCORD_vorkerland_wkr_solar_counter_intervention_ready"
WKR_INTERVENTION_BORDER = "ADISCORD_vorkerland_wkr_has_solyarino_intervention_border"
WKR_INTERVENTION = "ADISCORD_vorkerland_attempt_wkr_solyarino_intervention"
VERIFY_WKR_INTERVENTION = "ADISCORD_vorkerland_verify_wkr_solyarino_intervention"
CLEAR_WKR_INTERVENTION = "ADISCORD_vorkerland_clear_wkr_solyarino_intervention"
WKR_OUTCOME_TRIGGER = "ADISCORD_vorkerland_wkr_solyarino_target_wars_finished"
QUEUE_WKR_OUTCOME = "ADISCORD_vorkerland_queue_wkr_solyarino_outcome_check"
CHECK_WKR_OUTCOME = "ADISCORD_vorkerland_check_wkr_solyarino_outcome"
MATERIALIZE_WKR_PROTECTORATE = "ADISCORD_vorkerland_materialize_sol_worker_protectorate"
VERIFY_WKR_PROTECTORATE = "ADISCORD_vorkerland_verify_sol_worker_protectorate"
WKR_AIR_BOOTSTRAP = "ADISCORD_vorkerland_bootstrap_wkr_air_sustainment"
WKR_DYNAMIC_FORTS = "ADISCORD_vorkerland_build_wkr_live_frontline_fortifications"

VAD_SOLAR_BORDER_PAIRS = ((81, 307), (110, 198), (110, 307))
WKR_SOLAR_BORDER_PAIRS = (
    (79, 310),
    (308, 307),
    (309, 307),
    (309, 310),
    (327, 310),
    (81, 307),
    (110, 198),
    (110, 307),
)

CORE_PACKAGES = {
    "ADISCORD_vorkerland_restore_core_claimant_homes": (
        32, 33, 36, 37, 38, 39, 75, 106, 107, 121, 200, 201, 324,
    ),
    "ADISCORD_vorkerland_restore_core_central_historical": (
        27, 35, 40, 79, 81, 82, 102, 108, 109, 110, 111,
        122, 123, 124, 306, 308, 309, 320, 323, 325, 327,
    ),
    "ADISCORD_vorkerland_restore_core_oitfort": (34,),
    "ADISCORD_vorkerland_restore_core_rimat": (202,),
    "ADISCORD_vorkerland_restore_core_techlar": (105,),
    "ADISCORD_vorkerland_restore_core_ebern": (311,),
    "ADISCORD_vorkerland_restore_core_solar": (104, 198, 307),
}

HISTORICAL_WRK_VAD_STATES = frozenset(
    {
        27, 32, 33, 34, 35, 36, 37, 38, 39, 40, 75, 79, 81, 82,
        102, 104, 105, 106, 107, 108, 109, 110, 111, 121, 122, 123,
        124, 198, 200, 201, 202, 306, 307, 308, 309, 311, 320, 323,
        324, 325, 327,
    }
)

LIVE_ALLY_OR_FOREIGN_STATES = frozenset(
    {74, 76, 197, 310, 312, 313, 314, *range(331, 341)}
)


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


def direct_named_blocks(text: str, name: str) -> list[str]:
    """Return assignments named *name* that are direct children of *text*."""
    outer_brace = text.find("{")
    if outer_brace < 0:
        return []
    results: list[str] = []
    pattern = re.compile(rf"(?<![A-Za-z0-9_]){re.escape(name)}\s*=\s*\{{")
    for match in pattern.finditer(text, outer_brace + 1):
        depth = 1
        for character in text[outer_brace + 1 : match.start()]:
            if character == "{":
                depth += 1
            elif character == "}":
                depth -= 1
        if depth != 1:
            continue
        brace_start = text.find("{", match.start())
        block = _braced_block(text, match.start(), brace_start)
        if block:
            results.append(block)
    return results


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


def _unique_block(source: str, name: str, kind: str, issues: list[str]) -> str:
    blocks = named_blocks(source, name)
    if len(blocks) != 1:
        issues.append(f"{kind} {name} must be defined exactly once, found {len(blocks)}")
        return blocks[0] if blocks else ""
    return blocks[0]


def _assignment(text: str, key: str, value: str) -> bool:
    return bool(re.search(rf"\b{re.escape(key)}\s*=\s*{re.escape(value)}\b", text))


def compact(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def direct_scalar_values(text: str, key: str) -> list[str]:
    """Return scalar values assigned directly inside a Clausewitz block."""
    outer_brace = text.find("{")
    if outer_brace < 0:
        return []
    results: list[str] = []
    pattern = re.compile(rf"(?<![A-Za-z0-9_]){re.escape(key)}\s*=\s*([^\s#{{}}]+)")
    for match in pattern.finditer(text, outer_brace + 1):
        depth = 1
        for character in text[outer_brace + 1 : match.start()]:
            if character == "{":
                depth += 1
            elif character == "}":
                depth -= 1
        if depth == 1:
            results.append(match.group(1))
    return results


def _state_block_has(block: str, state: int, assignments: tuple[tuple[str, str], ...]) -> bool:
    return any(
        all(_assignment(candidate, key, value) for key, value in assignments)
        for candidate in named_blocks(block, str(state))
    )


def _contains_pair_block(
    block: str,
    pair: tuple[int, int],
    left_tag: str,
    right_tags: tuple[str, ...],
) -> bool:
    left, right = pair
    for candidate in named_blocks(block, "AND"):
        if str(left) not in direct_scalar_values(candidate, "owns_state"):
            continue
        if str(left) not in direct_scalar_values(candidate, "controls_state"):
            continue
        right_blocks = [
            scope
            for tag in right_tags
            for scope in named_blocks(candidate, tag)
        ]
        for right_block in right_blocks:
            if _assignment(right_block, "owns_state", str(right)) and _assignment(
                right_block, "controls_state", str(right)
            ):
                return True
    return False


def validate_terminal_outcomes() -> list[str]:
    issues: list[str] = []
    triggers = _load(DIPLOMACY_TRIGGERS, issues)
    effects = _load(DIPLOMACY_EFFECTS, issues)

    for trigger_name, (winner, opponents, states, winner_flag, _) in TERMINAL_CONTRACTS.items():
        block = _unique_block(triggers, trigger_name, "terminal trigger", issues)
        if not block:
            continue
        if not _assignment(block, "country_exists", winner):
            issues.append(f"{trigger_name} must require country_exists = {winner}")
        winner_scope = named_block(block, winner)
        for token in ("is_subject = no", "has_capitulated = yes"):
            expected = token if token == "is_subject = no" else f"NOT = {{ {token} }}"
            if expected not in winner_scope:
                issues.append(f"{trigger_name} must keep {winner} independent and non-capitulated")
                break
        for state in states:
            if not _assignment(winner_scope, "owns_state", str(state)) or not _assignment(
                winner_scope, "controls_state", str(state)
            ):
                issues.append(f"{trigger_name} must require {winner} ownership/control of state {state}")
        for opponent in opponents:
            if f"NOT = {{ country_exists = {opponent} }}" not in block:
                issues.append(f"{trigger_name} lacks absent-rival condition for {opponent}")
            opponent_scopes = named_blocks(block, opponent)
            if not any(_assignment(scope, "has_capitulated", "yes") for scope in opponent_scopes):
                issues.append(f"{trigger_name} lacks capitulated-rival condition for {opponent}")
            if not any(_assignment(scope, "is_subject_of", winner) for scope in opponent_scopes):
                issues.append(f"{trigger_name} lacks {opponent} subject-of-{winner} terminal condition")
            if f"NOT = {{ has_war_with = {opponent} }}" not in winner_scope:
                issues.append(f"{trigger_name} must end {winner}'s war with {opponent}")
        if "every_owned_state" in block or "every_state" in block:
            issues.append(f"{trigger_name} must enumerate its exact state package")
        if winner_flag in block:
            issues.append(f"{trigger_name} must be a postcondition, not set {winner_flag}")

    recorder = _unique_block(effects, OUTCOME_RECORDER, "outcome effect", issues)
    if recorder:
        for trigger_name, (_, _, _, winner_flag, terminal_flag) in TERMINAL_CONTRACTS.items():
            if not _assignment(recorder, trigger_name, "yes"):
                issues.append(f"{OUTCOME_RECORDER} does not query {trigger_name}")
            if recorder.count(f"set_global_flag = {winner_flag}") != 1:
                issues.append(f"{OUTCOME_RECORDER} must set {winner_flag} exactly once")
            if f"NOT = {{ has_global_flag = {terminal_flag} }}" not in recorder:
                issues.append(f"{OUTCOME_RECORDER} must guard the idempotent {terminal_flag} outcome")
        for terminal_flag in {
            contract[4] for contract in TERMINAL_CONTRACTS.values()
        }:
            if f"set_global_flag = {terminal_flag}" not in recorder:
                issues.append(f"{OUTCOME_RECORDER} never verifies {terminal_flag}")
        for forbidden in ("every_country", "random_country", "declare_war_on", "add_to_war"):
            if forbidden in recorder:
                issues.append(f"{OUTCOME_RECORDER} must remain a bounded recorder; found {forbidden}")
        for offer in (VAD_SOL_OFFER, WKR_VLA_OFFER):
            if _assignment(recorder, offer, "yes"):
                issues.append(f"{OUTCOME_RECORDER} must not bypass the public decision for {offer}")
    return list(dict.fromkeys(issues))


def validate_bounded_outcome_hook() -> list[str]:
    issues: list[str] = []
    events = _load(DIPLOMACY_EVENTS, issues)
    on_actions = _load(DIPLOMACY_ON_ACTIONS, issues)

    outcome_event = event_block(events, "ADISCORD_vorkerland_diplomacy.1")
    if not outcome_event:
        issues.append("missing delayed regional outcome event ADISCORD_vorkerland_diplomacy.1")
    else:
        if "is_triggered_only = yes" not in outcome_event:
            issues.append("ADISCORD_vorkerland_diplomacy.1 must remain triggered-only")
        if outcome_event.count(f"{OUTCOME_RECORDER} = yes") != 1:
            issues.append(
                f"ADISCORD_vorkerland_diplomacy.1 must call {OUTCOME_RECORDER} exactly once"
            )

    on_capitulation = named_block(on_actions, "on_capitulation")
    regional_hook = named_blocks(on_capitulation, "if")
    regional_hook = regional_hook[0] if regional_hook else ""
    root_scope = named_block(named_block(regional_hook, "limit"), "ROOT")
    regional_tags = set(re.findall(r"\btag\s*=\s*([A-Z0-9]{3})\b", root_scope))
    if regional_tags != {"SOL", "SRA", "CSL", "VLA", "EBA", "TGD"}:
        issues.append(
            "on_capitulation outcome hook must be limited to SOL/SRA/CSL/VLA/EBA/TGD"
        )
    for token in (
        "ADISCORD_vorkerland_regional_diplomacy_check_scheduled",
        "days = 3",
        "id = ADISCORD_vorkerland_diplomacy.1 days = 1",
    ):
        if token not in regional_hook:
            issues.append(f"bounded on_capitulation outcome hook lacks {token}")

    if named_block(on_actions, "on_startup"):
        issues.append("diplomacy on_actions must be fresh-campaign-only and omit on_startup")

    for pulse in ("on_daily", "on_weekly", "on_monthly"):
        for block in named_blocks(on_actions, pulse):
            if OUTCOME_RECORDER in block or "ADISCORD_vorkerland_diplomacy.1" in block:
                issues.append(f"regional outcome recording must not run from {pulse}")
    if "every_country" in f"{events}\n{on_actions}":
        issues.append("regional diplomacy must not poll every_country")
    return list(dict.fromkeys(issues))


def validate_peaceful_invitations() -> list[str]:
    issues: list[str] = []
    effects = _load(DIPLOMACY_EFFECTS, issues)
    events = _load(DIPLOMACY_EVENTS, issues)
    decisions = _load(DIPLOMACY_DECISIONS, issues)
    on_actions = _load(DIPLOMACY_ON_ACTIONS, issues)
    focus_decisions = _load(FOCUS_DECISIONS, issues)
    focus_effects = _load(FOCUS_DECISION_EFFECTS, issues)
    collapse_effects = _load(COLLAPSE_EFFECTS, issues)
    contracts = (
        (
            VAD_SOL_OFFER,
            "ADISCORD_vorkerland_solar_winner_sol",
            "VAD",
            "SOL",
            VAD_SOL_ACCEPTED,
            "ADISCORD_vorkerland_vad_sol_invitation_pending",
            "ADISCORD_vorkerland_vad_sol_invitation_dispatch_guard",
            "ADISCORD_vorkerland_vad_sol_invitation_resolved",
            "ADISCORD_vorkerland_diplomacy.2",
            "ADISCORD_vorkerland_vad_invite_victorious_sol",
            "ADISCORD_vorkerland_focus_vad_sol_invitation_intent",
        ),
        (
            WKR_VLA_OFFER,
            "ADISCORD_vorkerland_volnograd_winner_vla",
            "WKR",
            "VLA",
            WKR_VLA_ACCEPTED,
            "ADISCORD_vorkerland_wkr_vla_invitation_pending",
            "ADISCORD_vorkerland_wkr_vla_invitation_dispatch_guard",
            "ADISCORD_vorkerland_wkr_vla_invitation_resolved",
            "ADISCORD_vorkerland_diplomacy.3",
            "ADISCORD_vorkerland_wkr_invite_victorious_vla",
            "ADISCORD_vorkerland_focus_wkr_vla_invitation_intent",
        ),
    )
    for (
        effect_name,
        winner_flag,
        inviter,
        invitee,
        accepted_flag,
        pending_flag,
        dispatch_flag,
        resolved_flag,
        event_id,
        decision_id,
        intent_flag,
    ) in contracts:
        block = _unique_block(effects, effect_name, "invitation effect", issues)
        if not block:
            continue
        for token in (
            f"has_global_flag = {winner_flag}",
            f"tag = {inviter}",
            f"NOT = {{ has_country_flag = {pending_flag} }}",
            f"NOT = {{ has_country_flag = {resolved_flag} }}",
            f"set_country_flag = {pending_flag}",
            f"flag = {dispatch_flag} days = 3",
            f"id = {event_id} days = 1",
        ):
            if token not in block:
                issues.append(f"{effect_name} lacks peaceful invitation gate {token}")
        invitee_scope = named_block(block, invitee)
        for token in ("exists = yes", "is_subject = no", "NOT = { has_capitulated = yes }"):
            if token not in invitee_scope:
                issues.append(f"{effect_name} must keep {invitee} independent and alive")
        for forbidden in (
            "create_faction",
            "add_to_faction",
            "declare_war_on",
            "add_to_war",
            "puppet =",
            "set_autonomy",
            f"set_global_flag = {accepted_flag}",
        ):
            if forbidden in block:
                issues.append(f"{effect_name} must only record a pending offer; found {forbidden}")

        acceptance = event_block(events, event_id)
        if not acceptance:
            issues.append(f"missing triggered acceptance event {event_id}")
            continue
        for token in (
            "is_triggered_only = yes",
            f"has_global_flag = {winner_flag}",
            "create_faction_from_template = {",
            "template = faction_template_ADISCORD_standard",
            f"add_to_faction = {invitee}",
            f"clr_country_flag = {pending_flag}",
            f"clr_country_flag = {dispatch_flag}",
            f"set_country_flag = {resolved_flag}",
            "set_country_flag = ADISCORD_vorkerland_preserve_wartime_faction",
            f"set_global_flag = {accepted_flag}",
            f"set_global_flag = {accepted_flag.replace('_accepted', '_declined')}",
            f"{JOIN_ALLIES} = yes",
        ):
            if token not in acceptance:
                issues.append(f"{event_id} lacks bounded acceptance/decline token {token}")
        for forbidden in ("declare_war_on", "add_to_war", "puppet =", "set_autonomy"):
            if forbidden in acceptance:
                issues.append(f"{event_id} must not start or merge a war during acceptance; found {forbidden}")
        event_trigger = named_block(acceptance, "trigger")
        if f"has_country_flag = {pending_flag}" not in event_trigger:
            issues.append(f"{event_id} event trigger must retain the inviter pending fallback")
        if acceptance.count(f"clr_country_flag = {dispatch_flag}") < 2:
            issues.append(f"{event_id} must clear its dispatch guard on accept and decline")
        accepted_at = compact(acceptance).find(f"set_global_flag = {accepted_flag}")
        reconciled_at = compact(acceptance).find(f"{JOIN_ALLIES} = yes")
        if accepted_at < 0 or reconciled_at < accepted_at:
            issues.append(f"{event_id} must record acceptance before reconciling live showdown wars")

        decision = _unique_block(decisions, decision_id, "public alliance decision", issues)
        for token in (
            f"allowed = {{ tag = {inviter} }}",
            f"has_country_flag = {intent_flag}",
            f"has_global_flag = {winner_flag}",
            f"complete_effect = {{ {effect_name} = yes }}",
            "fire_only_once = yes",
        ):
            if token not in compact(decision):
                issues.append(f"{decision_id} lacks public invitation contract {token}")

        showdown_guards = (
            "ADISCORD_vorkerland_focus_central_showdown_requested",
            "ADISCORD_vorkerland_showdown_queue_initialized",
            "ADISCORD_vorkerland_central_showdown_started",
        )
        for owner, source in (
            (effect_name, block),
            (event_id, acceptance),
            (decision_id, decision),
        ):
            for guard in showdown_guards:
                if guard in source:
                    issues.append(f"optional invitation {owner} still depends on showdown flag {guard}")
    commit = _unique_block(
        focus_decisions,
        "ADISCORD_vorkerland_commit_to_central_showdown",
        "central-showdown commit decision",
        issues,
    )
    scheduler = _unique_block(
        focus_effects,
        "ADISCORD_vorkerland_focus_schedule_final_showdown",
        "central-showdown scheduler effect",
        issues,
    )
    for pending_flag in (
        "ADISCORD_vorkerland_vad_sol_invitation_pending",
        "ADISCORD_vorkerland_wkr_vla_invitation_pending",
    ):
        if pending_flag in commit or pending_flag in scheduler:
            issues.append(f"optional pending invitation still blocks central showdown: {pending_flag}")

    detach = named_block(collapse_effects, "ADISCORD_vorkerland_leave_inherited_faction")
    if "ADISCORD_vorkerland_preserve_wartime_faction" not in detach:
        issues.append(
            "faction-detach helper must honor ADISCORD_vorkerland_preserve_wartime_faction"
        )
    return list(dict.fromkeys(issues))


def _validate_border_trigger(
    source: str,
    name: str,
    pairs: tuple[tuple[int, int], ...],
    left_tag: str,
    right_tags: tuple[str, ...],
    issues: list[str],
) -> str:
    block = _unique_block(source, name, "land-border trigger", issues)
    if not block:
        return ""
    for pair in pairs:
        if not _contains_pair_block(block, pair, left_tag, right_tags):
            issues.append(
                f"{name} lacks claimant-owned/controlled physical edge {pair[0]}-{pair[1]}"
            )
    expected_states = {state for pair in pairs for state in pair}
    owned_states = {
        int(state)
        for state in re.findall(r"\bowns_state\s*=\s*(\d+)\b", block)
    }
    controlled_states = {
        int(state)
        for state in re.findall(r"\bcontrols_state\s*=\s*(\d+)\b", block)
    }
    if owned_states != expected_states or controlled_states != expected_states:
        issues.append(
            f"{name} state edge manifest drifted: expected {sorted(expected_states)}, "
            f"owned={sorted(owned_states)}, controlled={sorted(controlled_states)}"
        )
    for forbidden in (
        "is_coastal",
        "is_on_continent",
        "any_owned_state",
        "every_owned_state",
        "is_neighbor_of",
    ):
        if forbidden in block:
            issues.append(f"{name} must prove its exact state-pair topology; found {forbidden}")
    return block


def validate_vad_intervention_and_restoration() -> list[str]:
    issues: list[str] = []
    triggers = _load(DIPLOMACY_TRIGGERS, issues)
    effects = _load(DIPLOMACY_EFFECTS, issues)
    events = _load(DIPLOMACY_EVENTS, issues)
    decisions = _load(DIPLOMACY_DECISIONS, issues)
    on_actions = _load(DIPLOMACY_ON_ACTIONS, issues)
    focus_decisions = _load(FOCUS_DECISIONS, issues)
    focus_effects = _load(FOCUS_DECISION_EFFECTS, issues)

    _validate_border_trigger(
        triggers,
        VAD_INTERVENTION_BORDER,
        VAD_SOLAR_BORDER_PAIRS,
        "VAD",
        ("SRA", "CSL"),
        issues,
    )

    intervention = _unique_block(effects, VAD_INTERVENTION, "intervention effect", issues)
    if intervention:
        intervention_compact = compact(intervention)
        for token in (
            "tag = VAD",
            "has_global_flag = ADISCORD_vorkerland_vad_solar_intervention_reserved",
            "has_global_flag = ADISCORD_vorkerland_phase_central_preparation",
            "NOT = { has_global_flag = ADISCORD_vorkerland_focus_central_showdown_requested }",
            "NOT = { has_global_flag = ADISCORD_vorkerland_central_showdown_started }",
            "NOT = { has_global_flag = ADISCORD_vorkerland_showdown_queue_initialized }",
            f"{VAD_INTERVENTION_BORDER} = yes",
            "has_global_flag = ADISCORD_vorkerland_solar_winner_sra",
            "has_global_flag = ADISCORD_vorkerland_solar_winner_csl",
            "set_global_flag = ADISCORD_vorkerland_vad_solar_intervention_active",
            "set_country_flag = ADISCORD_vorkerland_vad_solar_intervention_attempted",
            "set_country_flag = ADISCORD_vorkerland_vad_solar_intervention_verify_pending",
            "country_event = { id = ADISCORD_vorkerland_diplomacy.6 days = 1 }",
            f"{CANCEL_VAD_INTERVENTION_RESERVATION} = yes",
            "declare_war_on = { target = SRA type = take_state_focus generator = { 76 104 198 307 310 } }",
            "declare_war_on = { target = CSL type = take_state_focus generator = { 76 104 198 307 310 } }",
        ):
            if token not in intervention_compact:
                issues.append(f"{VAD_INTERVENTION} lacks gated intervention token {token}")
        if "target = SOL" in intervention:
            issues.append(f"{VAD_INTERVENTION} must never target SOL")
        for forbidden in ("create_faction", "add_to_faction", "every_country"):
            if forbidden in intervention:
                issues.append(f"{VAD_INTERVENTION} contains forbidden {forbidden}")

    reserve = _unique_block(
        effects, RESERVE_VAD_INTERVENTION, "intervention reservation effect", issues
    )
    for token in (
        "set_global_flag = ADISCORD_vorkerland_vad_solar_intervention_reserved",
        "clr_global_flag = ADISCORD_vorkerland_vad_solar_intervention_failed",
        "clr_global_flag = ADISCORD_vorkerland_vad_solar_intervention_target_sra",
        "clr_global_flag = ADISCORD_vorkerland_vad_solar_intervention_target_csl",
        "clr_global_flag = ADISCORD_vorkerland_sol_restoration_materialized",
        "clr_global_flag = ADISCORD_vorkerland_sol_restoration_materialization_retry",
        "clr_global_flag = ADISCORD_vorkerland_sol_restoration_retry",
        "clr_global_flag = ADISCORD_vorkerland_sol_restoration_failed",
        "clr_global_flag = ADISCORD_vorkerland_sol_restoration_fresh_release",
        "clr_country_flag = ADISCORD_vorkerland_vad_solar_intervention_verify_pending",
        "clr_country_flag = ADISCORD_vorkerland_vad_solar_intervention_verify_retry",
    ):
        if token not in compact(reserve):
            issues.append(f"{RESERVE_VAD_INTERVENTION} lacks attempt reset token {token}")
    cancel_reservation = _unique_block(
        effects,
        CANCEL_VAD_INTERVENTION_RESERVATION,
        "intervention reservation cleanup effect",
        issues,
    )
    if "clr_global_flag = ADISCORD_vorkerland_vad_solar_intervention_reserved" not in compact(
        cancel_reservation
    ):
        issues.append(f"{CANCEL_VAD_INTERVENTION_RESERVATION} must clear the reservation")

    verifier = _unique_block(
        effects, VERIFY_VAD_INTERVENTION, "intervention verification effect", issues
    )
    verifier_compact = compact(verifier)
    for token in (
        "has_global_flag = ADISCORD_vorkerland_vad_solar_intervention_active",
        "has_global_flag = ADISCORD_vorkerland_vad_solar_intervention_target_sra",
        "has_global_flag = ADISCORD_vorkerland_vad_solar_intervention_target_csl",
        "has_war_with = SRA",
        "has_war_with = CSL",
        "has_country_flag = ADISCORD_vorkerland_vad_solar_intervention_verify_retry",
        "country_event = { id = ADISCORD_vorkerland_diplomacy.9 days = 1 }",
        "ADISCORD_vorkerland_clear_failed_vad_solar_intervention = yes",
    ):
        if token not in verifier_compact:
            issues.append(f"{VERIFY_VAD_INTERVENTION} lacks bounded verifier token {token}")
    for event_id, retry_token in (
        ("ADISCORD_vorkerland_diplomacy.6", "NOT = { has_country_flag = ADISCORD_vorkerland_vad_solar_intervention_verify_retry }"),
        ("ADISCORD_vorkerland_diplomacy.9", "has_country_flag = ADISCORD_vorkerland_vad_solar_intervention_verify_retry"),
    ):
        verifier_event = event_block(events, event_id)
        for token in (
            "is_triggered_only = yes",
            f"{VERIFY_VAD_INTERVENTION} = yes",
            "has_country_flag = ADISCORD_vorkerland_vad_solar_intervention_verify_pending",
            retry_token,
        ):
            if token not in verifier_event:
                issues.append(f"{event_id} lacks bounded verifier token {token}")

    intervention_decision = _unique_block(
        decisions,
        "ADISCORD_vorkerland_vad_restore_sol_by_force",
        "public intervention decision",
        issues,
    )
    for token in (
        "allowed = { tag = VAD }",
        f"{VAD_INTERVENTION_BORDER} = yes",
        "NOT = { has_war = yes }",
        "NOT = { has_global_flag = ADISCORD_vorkerland_vad_solar_intervention_failed }",
        f"complete_effect = {{ {RESERVE_VAD_INTERVENTION} = yes }}",
        f"cancel_effect = {{ {CANCEL_VAD_INTERVENTION_RESERVATION} = yes }}",
        f"remove_effect = {{ {VAD_INTERVENTION} = yes }}",
        "fire_only_once = no",
    ):
        if token not in compact(intervention_decision):
            issues.append(f"public VAD intervention decision lacks {token}")
    if "cancel_trigger = {" not in intervention_decision:
        issues.append("public VAD intervention decision lacks reservation-safe cancellation")

    cleanup_effect = _unique_block(
        effects, CLEAR_FAILED_VAD_INTERVENTION, "intervention cleanup effect", issues
    )
    cleanup_compact = compact(cleanup_effect)
    for token in (
        "has_global_flag = ADISCORD_vorkerland_vad_solar_intervention_target_sra",
        "has_global_flag = ADISCORD_vorkerland_vad_solar_intervention_target_csl",
        "VAD = { NOT = { has_war_with = SRA } }",
        "VAD = { NOT = { has_war_with = CSL } }",
        "NOT = { has_country_flag = ADISCORD_vorkerland_vad_solar_intervention_verify_pending }",
        "clr_global_flag = ADISCORD_vorkerland_vad_solar_intervention_reserved",
        "clr_global_flag = ADISCORD_vorkerland_sol_restoration_materialization_retry",
        "clr_global_flag = ADISCORD_vorkerland_sol_restoration_retry",
        "set_global_flag = ADISCORD_vorkerland_vad_solar_intervention_failed",
    ):
        if token not in cleanup_compact:
            issues.append(f"{CLEAR_FAILED_VAD_INTERVENTION} lacks target-aware cleanup token {token}")
    if "has_war = yes" in cleanup_effect:
        issues.append(f"{CLEAR_FAILED_VAD_INTERVENTION} must not use unrelated VAD wars as its liveness test")

    on_capitulation = named_block(on_actions, "on_capitulation")
    on_peace = named_block(on_actions, "on_peace")
    cleanup = "ADISCORD_vorkerland_clear_failed_vad_solar_intervention = yes"
    if cleanup not in on_capitulation or cleanup not in on_peace:
        issues.append("VAD intervention failure state must unwind on capitulation and peace")

    commit = _unique_block(
        focus_decisions,
        "ADISCORD_vorkerland_commit_to_central_showdown",
        "central-showdown commit decision",
        issues,
    )
    scheduler = _unique_block(
        focus_effects,
        "ADISCORD_vorkerland_focus_schedule_final_showdown",
        "central-showdown scheduler effect",
        issues,
    )
    reservation = "ADISCORD_vorkerland_vad_solar_intervention_reserved"
    if reservation in commit or reservation in scheduler:
        issues.append("an inactive VAD intervention reservation still blocks central showdown")
    active_gate = "NOT = { has_global_flag = ADISCORD_vorkerland_vad_solar_intervention_active }"
    if active_gate not in compact(commit) or active_gate not in compact(scheduler):
        issues.append("central showdown must wait for the actually active VAD intervention only")
    settlement = next(
        (
            block
            for block in named_blocks(on_capitulation, "if")
            if "ADISCORD_vorkerland_vad_solar_intervention_active" in block
        ),
        "",
    )
    settlement_compact = compact(settlement)
    for token in (
        "ROOT = { OR = { AND = { tag = SRA",
        "AND = { tag = CSL",
        "FROM = { tag = VAD NOT = { has_capitulated = yes } }",
        "set_global_flag = skip_default_capitulation",
        "set_global_flag = ADISCORD_vorkerland_sol_restoration_pending",
        "clr_global_flag = ADISCORD_vorkerland_sol_restoration_materialization_retry",
        "annex_country = { target = ROOT transfer_troops = no }",
        "country_event = { id = ADISCORD_vorkerland_diplomacy.4 days = 1 }",
    ):
        if token not in settlement_compact:
            issues.append(f"bounded VAD intervention settlement lacks {token}")
    settlement_states = {
        int(value)
        for value in re.findall(r"\btransfer_state\s*=\s*(\d+)\b", settlement)
    }
    if settlement_states != set(SOLAR_STATES):
        issues.append(
            f"VAD intervention settlement must transfer exactly {list(SOLAR_STATES)}, "
            f"found {sorted(settlement_states)}"
        )
    for event_id, retry_token in (
        (
            "ADISCORD_vorkerland_diplomacy.4",
            "NOT = { has_global_flag = ADISCORD_vorkerland_sol_restoration_materialization_retry }",
        ),
        (
            "ADISCORD_vorkerland_diplomacy.7",
            "has_global_flag = ADISCORD_vorkerland_sol_restoration_materialization_retry",
        ),
    ):
        restoration_event = event_block(events, event_id)
        for token in (
            "is_triggered_only = yes",
            f"{RESTORE_SOL} = yes",
            "has_global_flag = ADISCORD_vorkerland_sol_restoration_pending",
            "NOT = { has_global_flag = ADISCORD_vorkerland_sol_restoration_materialized }",
            retry_token,
        ):
            if token not in restoration_event:
                issues.append(f"{event_id} lacks bounded materialization token {token}")

    restore = _unique_block(effects, RESTORE_SOL, "SOL restoration effect", issues)
    if restore:
        restore_compact = compact(restore)
        for state in SOLAR_STATES:
            if not _assignment(restore, "owns_state", str(state)) or not _assignment(
                restore, "controls_state", str(state)
            ):
                issues.append(f"{RESTORE_SOL} must require VAD ownership/control of state {state}")
            if not re.search(rf"\btransfer_state\s*=\s*{state}\b", restore):
                issues.append(f"{RESTORE_SOL} must explicitly transfer state {state} to SOL")
            if not _state_block_has(restore, state, (("add_core_of", "SOL"),)):
                issues.append(f"{RESTORE_SOL} must explicitly add the SOL core to state {state}")
        for token in (
            "tag = VAD",
            "has_global_flag = ADISCORD_vorkerland_vad_solar_intervention_active",
            "NOT = { country_exists = SOL }",
            "release_autonomy = { target = SOL autonomy_state = autonomy_puppet",
            "set_global_flag = ADISCORD_vorkerland_sol_restoration_fresh_release",
            "puppet = SOL",
            "set_autonomy = { target = SOL autonomy_state = autonomy_puppet",
            f"NOT = {{ has_global_flag = {SOL_RESTORATION_VERIFIED} }}",
            "set_global_flag = ADISCORD_vorkerland_sol_restoration_materialized",
            "set_global_flag = ADISCORD_vorkerland_sol_restoration_materialization_retry",
            "country_event = { id = ADISCORD_vorkerland_diplomacy.7 days = 1 }",
            "set_global_flag = ADISCORD_vorkerland_sol_restoration_failed",
            f"{CLEAR_FAILED_VAD_INTERVENTION} = yes",
            "country_event = { id = ADISCORD_vorkerland_diplomacy.5 days = 1 }",
        ):
            if token not in restore_compact:
                issues.append(f"{RESTORE_SOL} lacks idempotent reconstruction token {token}")
        if f"set_global_flag = {SOL_RESTORATION_VERIFIED}" in restore:
            issues.append(f"{RESTORE_SOL} must not set success before delayed postcondition verification")
        for forbidden in ("every_owned_state", "every_state", "annex_country"):
            if forbidden in restore:
                issues.append(f"{RESTORE_SOL} must remain exact-state and non-destructive; found {forbidden}")

    verify = _unique_block(effects, VERIFY_SOL, "SOL verification effect", issues)
    if verify:
        verify_compact = compact(verify)
        sol_scope = named_block(named_block(verify, "limit"), "SOL")
        for token in (
            "tag = VAD",
            "is_subject_of = VAD",
            "has_global_flag = ADISCORD_vorkerland_sol_restoration_fresh_release",
            f"NOT = {{ has_country_flag = {SOL_RESTORATION_INITIALIZED} }}",
            f"set_country_flag = {SOL_RESTORATION_INITIALIZED}",
            f"set_global_flag = {SOL_RESTORATION_VERIFIED}",
            "has_global_flag = ADISCORD_vorkerland_sol_restoration_materialized",
            "set_global_flag = ADISCORD_vorkerland_sol_restoration_retry",
            "country_event = { id = ADISCORD_vorkerland_diplomacy.8 days = 1 }",
            "clr_global_flag = ADISCORD_vorkerland_sol_restoration_materialized",
            "clr_global_flag = ADISCORD_vorkerland_sol_restoration_retry",
            "set_global_flag = ADISCORD_vorkerland_sol_restoration_failed",
            f"{CLEAR_FAILED_VAD_INTERVENTION} = yes",
        ):
            if token not in verify_compact:
                issues.append(f"{VERIFY_SOL} lacks postcondition token {token}")
        for state in SOLAR_STATES:
            if not _assignment(sol_scope, "owns_state", str(state)) or not _assignment(
                sol_scope, "controls_state", str(state)
            ):
                issues.append(f"{VERIFY_SOL} must verify SOL ownership/control of state {state}")
        if verify.count('load_oob = "SOL"') != 1:
            issues.append(f"{VERIFY_SOL} must load the SOL OOB exactly once behind its fresh-release guard")
        if "set_capital = { state = 76 }" not in compact(f"{restore}\n{verify}"):
            issues.append("SOL restoration must explicitly restore state 76 as the capital")
        for forbidden in ("release_autonomy", "puppet =", "transfer_state", "load_oob"):
            if forbidden in verify and forbidden != "load_oob":
                issues.append(f"{VERIFY_SOL} must be postcondition-only; found {forbidden}")

    for event_id, retry_token in (
        (
            "ADISCORD_vorkerland_diplomacy.5",
            "NOT = { has_global_flag = ADISCORD_vorkerland_sol_restoration_retry }",
        ),
        (
            "ADISCORD_vorkerland_diplomacy.8",
            "has_global_flag = ADISCORD_vorkerland_sol_restoration_retry",
        ),
    ):
        verify_event = event_block(events, event_id)
        for token in (
            "is_triggered_only = yes",
            f"{VERIFY_SOL} = yes",
            "has_global_flag = ADISCORD_vorkerland_sol_restoration_materialized",
            retry_token,
        ):
            if token not in verify_event:
                issues.append(f"{event_id} lacks bounded postcondition token {token}")
    return list(dict.fromkeys(issues))


def validate_counter_intervention() -> list[str]:
    issues: list[str] = []
    triggers = _load(DIPLOMACY_TRIGGERS, issues)
    effects = _load(DIPLOMACY_EFFECTS, issues)
    decisions = _load(DIPLOMACY_DECISIONS, issues)
    focus_decisions = _load(FOCUS_DECISIONS, issues)
    focus_effects = _load(FOCUS_DECISION_EFFECTS, issues)
    phase_events = _load(PHASE_EVENTS, issues)
    _validate_border_trigger(
        triggers,
        WKR_COUNTER_BORDER,
        WKR_SOLAR_BORDER_PAIRS,
        "WKR",
        ("SOL",),
        issues,
    )
    counter = _unique_block(effects, ARM_WKR_COUNTER, "counter-intervention effect", issues)
    counter_decision = _unique_block(
        decisions,
        "ADISCORD_vorkerland_wkr_counter_solar_restoration",
        "counter-intervention decision",
        issues,
    )
    for token in ("days_remove = 7", "fire_only_once = no", f"remove_effect = {{ {ARM_WKR_COUNTER} = yes }}"):
        if token not in compact(counter_decision):
            issues.append(f"public WKR counter-intervention decision lacks retry-safe token {token}")
    if counter:
        counter_compact = compact(counter)
        for token in (
            "tag = WKR",
            f"has_global_flag = {SOL_RESTORATION_VERIFIED}",
            f"{WKR_COUNTER_BORDER} = yes",
            "NOT = { has_global_flag = ADISCORD_vorkerland_showdown_queue_initialized }",
            "NOT = { has_global_flag = ADISCORD_vorkerland_central_showdown_started }",
            f"set_global_flag = {WKR_COUNTER_READY}",
            "set_global_flag = ADISCORD_vorkerland_focus_central_showdown_requested",
        ):
            if token not in counter_compact:
                issues.append(f"{ARM_WKR_COUNTER} lacks shared-showdown accelerator token {token}")
        schedule = re.search(
            r"country_event\s*=\s*\{\s*id\s*=\s*ADISCORD_vorkerland_phase\.4\s+days\s*=\s*(\d+)\s*\}",
            counter,
        )
        if not schedule or not 1 <= int(schedule.group(1)) <= 21:
            issues.append(f"{ARM_WKR_COUNTER} must accelerate guarded phase.4 within 1-21 days")
        for forbidden in (
            "declare_war_on",
            "target = SOL",
            "ADISCORD_vorkerland_initialize_showdown_edge_queue = yes",
            "ADISCORD_vorkerland_set_phase_central_showdown = yes",
            "add_to_war",
        ):
            if forbidden in counter:
                issues.append(f"{ARM_WKR_COUNTER} must only accelerate shared phase.4; found {forbidden}")
    phase_four = event_block(phase_events, "ADISCORD_vorkerland_phase.4")
    for token in (
        "has_global_flag = ADISCORD_vorkerland_phase_central_preparation",
        "NOT = { has_global_flag = ADISCORD_vorkerland_showdown_queue_initialized }",
        "NOT = { has_global_flag = ADISCORD_vorkerland_central_showdown_started }",
        "ADISCORD_vorkerland_initialize_showdown_edge_queue = yes",
    ):
        if token not in phase_four:
            issues.append(f"shared ADISCORD_vorkerland_phase.4 guard lacks {token}")
    commit = named_block(focus_decisions, "ADISCORD_vorkerland_commit_to_central_showdown")
    scheduler = named_block(focus_effects, "ADISCORD_vorkerland_focus_schedule_final_showdown")
    for optional_counter_gate in (
        WKR_COUNTER_READY,
        WKR_COUNTER_BORDER,
        SOL_RESTORATION_VERIFIED,
    ):
        if optional_counter_gate in commit or optional_counter_gate in scheduler:
            issues.append(
                f"optional WKR counter-intervention still blocks central showdown: {optional_counter_gate}"
            )
    return list(dict.fromkeys(issues))


def validate_showdown_allies() -> list[str]:
    issues: list[str] = []
    diplomacy_effects = _load(DIPLOMACY_EFFECTS, issues)
    phase_effects = _load(PHASE_EFFECTS, issues)
    join = _unique_block(diplomacy_effects, JOIN_ALLIES, "showdown ally effect", issues)
    if join:
        for token in (
            f"has_global_flag = {VAD_SOL_ACCEPTED}",
            f"has_global_flag = {WKR_VLA_ACCEPTED}",
            "targeted_alliance = VAD enemy = WKR",
            "targeted_alliance = VAD enemy = TVA",
            "targeted_alliance = WKR enemy = VAD",
            "targeted_alliance = WKR enemy = TVA",
        ):
            if token not in join:
                issues.append(f"{JOIN_ALLIES} lacks shared-war token {token}")
        if join.count("add_to_war = {") != 4:
            issues.append(f"{JOIN_ALLIES} must contain exactly four bounded add_to_war joins")
        for forbidden in ("declare_war_on", "create_faction", "add_to_faction"):
            if forbidden in join:
                issues.append(f"{JOIN_ALLIES} must join existing wars without {forbidden}")
    verify_showdown = named_block(phase_effects, "ADISCORD_vorkerland_verify_central_showdown")
    if not _assignment(verify_showdown, JOIN_ALLIES, "yes"):
        issues.append(f"verified central showdown must call {JOIN_ALLIES}")
    else:
        normalized = compact(verify_showdown)
        started = normalized.find(
            "set_global_flag = ADISCORD_vorkerland_central_showdown_started"
        )
        joined = normalized.find(f"{JOIN_ALLIES} = yes")
        if started < 0 or joined < started:
            issues.append(f"{JOIN_ALLIES} must run only after central_showdown_started is verified")
        if "ADISCORD_vorkerland_central_showdown_edges_verified = yes" not in normalized:
            issues.append(f"{JOIN_ALLIES} caller must remain inside the verified three-edge gate")
    return list(dict.fromkeys(issues))


def validate_vad_egc_route_priority() -> list[str]:
    issues: list[str] = []
    decisions = _load(FOCUS_DECISIONS, issues)
    wave = _unique_block(
        decisions,
        "ADISCORD_vorkerland_launch_central_minor_wave",
        "central-minor campaign wave decision",
        issues,
    )
    if "ai_will_do = { factor = 900 }" not in compact(wave):
        issues.append("central-minor campaign wave lacks base AI priority 900")
    marker = "ADISCORD_vorkerland_focus_vad_solland_liaison_prepared"
    if marker in wave:
        issues.append("central-minor campaign wave still serializes the EGC/Solar route")
    if "ADISCORD_vorkerland_consolidate_egc" in decisions:
        issues.append("legacy EGC-only consolidation decision survived the wave migration")
    return list(dict.fromkeys(issues))


def validate_core_packages() -> list[str]:
    issues: list[str] = []
    decisions = _load(FOCUS_DECISIONS, issues)
    package_states = [state for states in CORE_PACKAGES.values() for state in states]
    if len(package_states) != len(set(package_states)):
        issues.append("independent WRK core packages must not overlap")
    if frozenset(package_states) != HISTORICAL_WRK_VAD_STATES:
        issues.append(
            "independent WRK core packages must exactly cover the historical WRK/VAD state manifest"
        )
    if set(package_states) & LIVE_ALLY_OR_FOREIGN_STATES:
        issues.append("WRK core packages contain live ally or foreign-country states")

    for decision_id, states in CORE_PACKAGES.items():
        block = _unique_block(decisions, decision_id, "public core decision", issues)
        if not block:
            continue
        for token in (
            "allowed = { tag = WRK }",
            "has_global_flag = ADISCORD_vorkerland_phase_postwar_integration",
            "has_global_flag = ADISCORD_vorkerland_reunification_verified",
            "fire_only_once = yes",
        ):
            if token not in block:
                issues.append(f"{decision_id} lacks public package token {token}")
        for state in states:
            for token in (f"owns_state = {state}", f"controls_state = {state}"):
                if token not in block:
                    issues.append(f"{decision_id} lacks exact availability gate {token}")
            if not _state_block_has(block, state, (("add_core_of", "WRK"),)):
                issues.append(f"{decision_id} must explicitly add the WRK core to state {state}")
        referenced_states = {
            int(value)
            for value in re.findall(r"\b(?:owns_state|controls_state)\s*=\s*(\d+)\b", block)
        }
        if referenced_states != set(states):
            issues.append(
                f"{decision_id} state gate drifted: expected {list(states)}, found {sorted(referenced_states)}"
            )
        if re.search(
            r"\bhas_country_flag\s*=\s*ADISCORD_vorkerland_core_[A-Za-z0-9_]+_restored\b",
            block,
        ):
            issues.append(f"{decision_id} must not chain through another core-package flag")
        for forbidden in (
            "every_owned_state",
            "every_controlled_state",
            "every_state",
            "annex_country",
            "transfer_state",
            "puppet =",
            "set_autonomy",
        ):
            if forbidden in block:
                issues.append(f"{decision_id} must remain an independent explicit core package; found {forbidden}")
    return list(dict.fromkeys(issues))


def validate_wkr_solyarino_intervention() -> list[str]:
    issues: list[str] = []
    triggers = _load(DIPLOMACY_TRIGGERS, issues)
    effects = _load(DIPLOMACY_EFFECTS, issues)
    decisions = _load(DIPLOMACY_DECISIONS, issues)
    focus_decisions = _load(FOCUS_DECISIONS, issues)
    focus_effects = _load(FOCUS_DECISION_EFFECTS, issues)
    events = _load(DIPLOMACY_EVENTS, issues)
    on_actions = _load(DIPLOMACY_ON_ACTIONS, issues)
    focus_source = _load(FOCUS_FILE, issues)
    ai = _load(COLLAPSE_AI, issues)
    plans = _load(WKR_AI_PLANS, issues)
    phase_effects = _load(PHASE_EFFECTS, issues)
    phase_events = _load(PHASE_EVENTS, issues)
    cosmetics = _load(COUNTRY_COSMETICS, issues)
    english = _load(DIPLOMACY_ENGLISH, issues)
    russian = _load(DIPLOMACY_RUSSIAN, issues)
    event_registry = _load(EVENT_ID_REGISTRY, issues)
    if issues:
        return issues

    _validate_border_trigger(
        triggers,
        WKR_INTERVENTION_BORDER,
        WKR_SOLAR_BORDER_PAIRS,
        "WKR",
        ("SOL", "SRA", "CSL"),
        issues,
    )

    valid_triggers = {
        "SOL": "ADISCORD_vorkerland_wkr_valid_sol_target",
        "SRA": "ADISCORD_vorkerland_wkr_valid_sra_target",
        "CSL": "ADISCORD_vorkerland_wkr_valid_csl_target",
    }
    for tag, name in valid_triggers.items():
        block = _unique_block(triggers, name, "WKR Solarino target trigger", issues)
        target = named_block(block, tag)
        for token in (
            "exists = yes",
            "is_subject = no",
            "NOT = { has_capitulated = yes }",
            "NOT = { has_war_with = WKR }",
            "NOT = { is_in_faction_with = WKR }",
        ):
            if token not in target:
                issues.append(f"{name} lacks live independent target guard {token}")
    aggregate = _unique_block(
        triggers,
        "ADISCORD_vorkerland_wkr_has_valid_solyarino_target",
        "WKR Solarino aggregate target trigger",
        issues,
    )
    for name in valid_triggers.values():
        if f"{name} = yes" not in aggregate:
            issues.append(f"WKR Solarino aggregate trigger omits {name}")

    focus_blocks = [
        block
        for block in named_blocks(focus_source, "focus")
        if re.search(r"(?m)^\s*id\s*=\s*WKR_intervene_in_solyarino\s*$", block)
    ]
    if len(focus_blocks) != 1:
        issues.append(
            "WKR_intervene_in_solyarino focus must be defined exactly once, "
            f"found {len(focus_blocks)}"
        )
        terminal = focus_blocks[0] if focus_blocks else ""
    else:
        terminal = focus_blocks[0]
    for token in (
        "cost = 3",
        "focus = WKR_rehearse_operation_southbound",
        "has_global_flag = ADISCORD_vorkerland_phase_central_preparation",
        "has_global_flag = ADISCORD_vorkerland_phase_central_showdown",
        "ADISCORD_vorkerland_wkr_has_valid_solyarino_target = yes",
        f"{WKR_INTERVENTION_BORDER} = yes",
        f"{WKR_INTERVENTION} = yes",
        "NOT = { has_global_flag = ADISCORD_vorkerland_vad_solar_intervention_reserved }",
        "NOT = { has_global_flag = ADISCORD_vorkerland_vad_solar_intervention_active }",
    ):
        if token not in terminal:
            issues.append(f"WKR Solarino focus lacks bounded terminal token {token}")
    for forbidden in ("declare_war_on", "every_country", "random_country"):
        if forbidden in terminal:
            issues.append(f"WKR Solarino focus must delegate world effects; found {forbidden}")
    for stale_gate in (
        "NOT = { has_global_flag = ADISCORD_vorkerland_focus_central_showdown_requested }",
        "NOT = { has_global_flag = ADISCORD_vorkerland_showdown_queue_initialized }",
        "NOT = { has_global_flag = ADISCORD_vorkerland_central_showdown_started }",
        "NOT = { has_global_flag = ADISCORD_vorkerland_vad_sol_alliance_accepted }",
    ):
        if stale_gate in terminal:
            issues.append(f"WKR Solarino focus still blocks the live-showdown route: {stale_gate}")

    attempt = _unique_block(effects, WKR_INTERVENTION, "WKR intervention effect", issues)
    for token in (
        "tag = WKR",
        "is_subject = no",
        "NOT = { has_capitulated = yes }",
        "has_global_flag = ADISCORD_vorkerland_phase_central_preparation",
        "has_global_flag = ADISCORD_vorkerland_phase_central_showdown",
        f"{WKR_INTERVENTION_BORDER} = yes",
        "set_global_flag = ADISCORD_vorkerland_wkr_solyarino_intervention_active",
        "set_country_flag = ADISCORD_vorkerland_wkr_solyarino_verify_pending",
        "country_event = { id = ADISCORD_vorkerland_diplomacy.10 days = 1 }",
    ):
        if token not in attempt:
            issues.append(f"{WKR_INTERVENTION} lacks launch token {token}")
    if attempt.count("declare_war_on =") != 3:
        issues.append(f"{WKR_INTERVENTION} must own exactly three independent declaration blocks")
    for tag, name in valid_triggers.items():
        for token in (
            f"{name} = yes",
            f"set_country_flag = ADISCORD_vorkerland_wkr_solyarino_target_{tag.lower()}",
            f"{tag} = {{ ADISCORD_vorkerland_leave_inherited_faction = yes }}",
            f"declare_war_on = {{ target = {tag} type = annex_everything }}",
        ):
            if token not in attempt:
                issues.append(f"{WKR_INTERVENTION} lacks {tag} declaration token {token}")
    for forbidden in (
        "NOT = { has_global_flag = ADISCORD_vorkerland_focus_central_showdown_requested }",
        "NOT = { has_global_flag = ADISCORD_vorkerland_showdown_queue_initialized }",
        "NOT = { has_global_flag = ADISCORD_vorkerland_central_showdown_started }",
        "NOT = { has_global_flag = ADISCORD_vorkerland_vad_sol_alliance_accepted }",
        "NOT = { has_war = yes }",
        "NOT = { has_war_with = VAD }",
        "declare_war_on = { target = VAD",
    ):
        if forbidden in attempt:
            issues.append(f"{WKR_INTERVENTION} must remain usable during the VAD war: {forbidden}")

    verify = _unique_block(
        effects, VERIFY_WKR_INTERVENTION, "WKR intervention verifier", issues
    )
    for token in (
        "has_global_flag = ADISCORD_vorkerland_wkr_solyarino_intervention_active",
        "has_country_flag = ADISCORD_vorkerland_wkr_solyarino_verify_pending",
        "NOT = { has_country_flag = ADISCORD_vorkerland_wkr_solyarino_verify_retry }",
        "set_country_flag = ADISCORD_vorkerland_wkr_solyarino_verify_retry",
        "country_event = { id = ADISCORD_vorkerland_diplomacy.11 days = 1 }",
        f"{CLEAR_WKR_INTERVENTION} = yes",
    ):
        if token not in verify:
            issues.append(f"{VERIFY_WKR_INTERVENTION} lacks bounded retry token {token}")
    if verify.count("declare_war_on =") != 3:
        issues.append(f"{VERIFY_WKR_INTERVENTION} must retry at most one edge per target")
    for tag in ("SOL", "SRA", "CSL"):
        if f"has_war_with = {tag}" not in verify:
            issues.append(f"{VERIFY_WKR_INTERVENTION} does not verify the {tag} edge")

    cleanup = _unique_block(
        effects, CLEAR_WKR_INTERVENTION, "WKR intervention cleanup", issues
    )
    for token in (
        "clr_global_flag = ADISCORD_vorkerland_wkr_solyarino_intervention_active",
        "has_country_flag = ADISCORD_vorkerland_wkr_solyarino_intervention_failed",
        "has_global_flag = ADISCORD_vorkerland_sol_worker_protectorate_failed",
        "ADISCORD_vorkerland_begin_reunification = yes",
    ):
        if token not in cleanup:
            issues.append(f"{CLEAR_WKR_INTERVENTION} lacks terminal cleanup token {token}")
    if "ADISCORD_vorkerland_wkr_solyarino_target_wars_finished = yes" in cleanup:
        issues.append("WKR cleanup must not erase a successful peace before the outcome verifier")

    for event_id, retry_token, effect_name in (
        (
            "ADISCORD_vorkerland_diplomacy.10",
            "NOT = { has_country_flag = ADISCORD_vorkerland_wkr_solyarino_verify_retry }",
            VERIFY_WKR_INTERVENTION,
        ),
        (
            "ADISCORD_vorkerland_diplomacy.11",
            "has_country_flag = ADISCORD_vorkerland_wkr_solyarino_verify_retry",
            VERIFY_WKR_INTERVENTION,
        ),
    ):
        block = event_block(events, event_id)
        for token in (
            "hidden = yes",
            "is_triggered_only = yes",
            "tag = WKR",
            retry_token,
            f"{effect_name} = yes",
        ):
            if token not in block:
                issues.append(f"{event_id} lacks bounded event token {token}")

    outcome_trigger = _unique_block(
        triggers, WKR_OUTCOME_TRIGGER, "WKR intervention terminal trigger", issues
    )
    for tag in ("sol", "sra", "csl"):
        upper = tag.upper()
        for token in (
            f"has_country_flag = ADISCORD_vorkerland_wkr_solyarino_target_{tag}",
            f"NOT = {{ country_exists = {upper} }}",
            f"NOT = {{ has_war_with = {upper} }}",
        ):
            if token not in outcome_trigger:
                issues.append(f"{WKR_OUTCOME_TRIGGER} lacks {upper} terminal token {token}")
    for forbidden in ("has_capitulated = yes", "is_subject = yes"):
        if forbidden in outcome_trigger:
            issues.append(
                f"{WKR_OUTCOME_TRIGGER} must wait for each exact war edge, not accept {forbidden}"
            )

    queue = _unique_block(effects, QUEUE_WKR_OUTCOME, "WKR outcome queue", issues)
    for token in (
        "tag = WKR",
        "has_global_flag = ADISCORD_vorkerland_wkr_solyarino_intervention_active",
        "NOT = { has_country_flag = ADISCORD_vorkerland_wkr_solyarino_outcome_check_pending }",
        "set_country_flag = ADISCORD_vorkerland_wkr_solyarino_outcome_check_pending",
        "country_event = { id = ADISCORD_vorkerland_diplomacy.12 days = 1 }",
    ):
        if token not in queue:
            issues.append(f"{QUEUE_WKR_OUTCOME} lacks bounded queue token {token}")

    on_capitulation = named_block(on_actions, "on_capitulation")
    on_peace = named_block(on_actions, "on_peace")
    settlement = next(
        (
            block
            for block in named_blocks(on_capitulation, "if")
            if "ADISCORD_vorkerland_wkr_solyarino_intervention_active" in block
            and "set_global_flag = skip_default_capitulation" in block
            and "tag = WKR" in block
        ),
        "",
    )
    settlement_compact = compact(settlement)
    for token in (
        "FROM = { tag = WKR NOT = { has_capitulated = yes } }",
        "has_country_flag = ADISCORD_vorkerland_wkr_solyarino_target_sol",
        "has_country_flag = ADISCORD_vorkerland_wkr_solyarino_target_sra",
        "has_country_flag = ADISCORD_vorkerland_wkr_solyarino_target_csl",
        "limit = { ROOT = { tag = SOL } }",
        "target_country = WKR",
        "character = WRK_Richard_Gordon",
        "set_country_flag = ADISCORD_vorkerland_wkr_solyarino_gordon_carried",
        "set_global_flag = skip_default_capitulation",
        "annex_country = { target = ROOT transfer_troops = no }",
        f"{QUEUE_WKR_OUTCOME} = yes",
    ):
        if token not in settlement_compact:
            issues.append(f"WKR Solarino capitulation settlement lacks {token}")
    carry_to_wkr = settlement_compact.find("target_country = WKR")
    annex_sol_shell = settlement_compact.find(
        "annex_country = { target = ROOT transfer_troops = no }"
    )
    if carry_to_wkr < 0 or annex_sol_shell < 0 or carry_to_wkr >= annex_sol_shell:
        issues.append(
            "WKR Solarino capitulation must carry Richard Gordon from SOL to WKR "
            "before annexing the SOL shell"
        )
    if f"{QUEUE_WKR_OUTCOME} = yes" not in on_peace:
        issues.append("on_peace must queue the bounded WKR Solarino outcome check")
    puppet_hook = named_block(on_actions, "on_puppet")
    if f"{CLEAR_WKR_INTERVENTION} = yes" not in puppet_hook:
        issues.append("on_puppet must unwind an invalid WKR Solarino operation owner")

    outcome_event = event_block(events, "ADISCORD_vorkerland_diplomacy.12")
    for token in (
        "hidden = yes",
        "is_triggered_only = yes",
        "tag = WKR",
        "has_country_flag = ADISCORD_vorkerland_wkr_solyarino_outcome_check_pending",
        f"{CHECK_WKR_OUTCOME} = yes",
    ):
        if token not in outcome_event:
            issues.append(f"ADISCORD_vorkerland_diplomacy.12 lacks outcome token {token}")

    outcome = _unique_block(effects, CHECK_WKR_OUTCOME, "WKR outcome verifier", issues)
    for token in (
        f"{WKR_OUTCOME_TRIGGER} = yes",
        "set_global_flag = ADISCORD_vorkerland_sol_worker_protectorate_pending",
        "country_event = { id = ADISCORD_vorkerland_diplomacy.13 days = 1 }",
        "set_country_flag = ADISCORD_vorkerland_wkr_solyarino_intervention_failed",
        "set_global_flag = ADISCORD_vorkerland_sol_worker_protectorate_failed",
        f"{CLEAR_WKR_INTERVENTION} = yes",
    ):
        if token not in outcome:
            issues.append(f"{CHECK_WKR_OUTCOME} lacks terminal outcome token {token}")
    for state in SOLAR_STATES:
        if not _assignment(outcome, "owns_state", str(state)) or not _assignment(
            outcome, "controls_state", str(state)
        ):
            issues.append(f"{CHECK_WKR_OUTCOME} must prove WKR ownership/control of state {state}")

    materialize = _unique_block(
        effects, MATERIALIZE_WKR_PROTECTORATE, "SOL worker protectorate materializer", issues
    )
    materialize_compact = compact(materialize)
    for state in SOLAR_STATES:
        if not _assignment(materialize, "owns_state", str(state)) or not _assignment(
            materialize, "controls_state", str(state)
        ):
            issues.append(f"{MATERIALIZE_WKR_PROTECTORATE} must require state {state}")
        if not re.search(rf"\btransfer_state\s*=\s*{state}\b", materialize):
            issues.append(f"{MATERIALIZE_WKR_PROTECTORATE} must transfer state {state} to SOL")
        if not _state_block_has(materialize, state, (("add_core_of", "SOL"),)):
            issues.append(f"{MATERIALIZE_WKR_PROTECTORATE} must add the SOL core to state {state}")
    for token in (
        "tag = WKR",
        "NOT = { country_exists = SOL }",
        "release_autonomy = { target = SOL autonomy_state = autonomy_district_in_Vorkerland",
        "puppet = SOL",
        "set_autonomy = { target = SOL autonomy_state = autonomy_district_in_Vorkerland freedom_level = 0.10 }",
        "set_global_flag = ADISCORD_vorkerland_sol_worker_protectorate_fresh_release",
        "target_country = WKR",
        "target_country = SOL",
        "character = WRK_Richard_Gordon",
        "set_country_flag = ADISCORD_vorkerland_wkr_solyarino_gordon_carried",
        "set_country_flag = ADISCORD_vorkerland_wkr_solyarino_gordon_returned",
        "set_global_flag = ADISCORD_vorkerland_sol_worker_protectorate_materialized",
        "set_global_flag = ADISCORD_vorkerland_sol_worker_protectorate_materialization_retry",
        "country_event = { id = ADISCORD_vorkerland_diplomacy.14 days = 1 }",
        "country_event = { id = ADISCORD_vorkerland_diplomacy.15 days = 1 }",
        "set_global_flag = ADISCORD_vorkerland_sol_worker_protectorate_failed",
    ):
        if token not in materialize_compact:
            issues.append(f"{MATERIALIZE_WKR_PROTECTORATE} lacks bounded materialization token {token}")
    recover_gordon = materialize_compact.find("target_country = WKR")
    return_gordon = materialize_compact.find("target_country = SOL")
    queue_verification = materialize_compact.find(
        "country_event = { id = ADISCORD_vorkerland_diplomacy.15 days = 1 }"
    )
    if not (
        0 <= recover_gordon < return_gordon < queue_verification
    ):
        issues.append(
            "SOL worker protectorate materialization must recover Gordon to WKR, "
            "return him to the released SOL shell, then queue verification"
        )
    if "set_global_flag = ADISCORD_vorkerland_sol_worker_protectorate_verified" in materialize:
        issues.append("SOL worker protectorate materializer must not declare success before verification")

    protectorate_verify = _unique_block(
        effects, VERIFY_WKR_PROTECTORATE, "SOL worker protectorate verifier", issues
    )
    protectorate_verify_compact = compact(protectorate_verify)
    sol_scope = named_block(named_block(protectorate_verify, "limit"), "SOL")
    for state in SOLAR_STATES:
        if not _assignment(sol_scope, "owns_state", str(state)) or not _assignment(
            sol_scope, "controls_state", str(state)
        ):
            issues.append(f"{VERIFY_WKR_PROTECTORATE} must verify SOL state {state}")
    for token in (
        "is_subject_of = WKR",
        "has_country_flag = ADISCORD_vorkerland_wkr_solyarino_gordon_returned",
        "has_global_flag = ADISCORD_vorkerland_sol_worker_protectorate_fresh_release",
        "NOT = { has_country_flag = ADISCORD_vorkerland_sol_worker_protectorate_initialized }",
        "ADISCORD_grant_2150_technology_baseline = yes",
        "ADISCORD_grant_technology_profile_fragment_low_tech = yes",
        "ADISCORD_economy_initialize_country = yes",
        'load_oob = "SOL"',
        "set_capital = { state = 76 }",
        "ruling_party = pragmatism",
        "character = WRK_Richard_Gordon",
        "set_cosmetic_tag = SOL_vorkerland_worker_protectorate",
        "set_global_flag = ADISCORD_vorkerland_sol_worker_protectorate_verified",
        "set_global_flag = ADISCORD_vorkerland_sol_worker_protectorate_verify_retry",
        "country_event = { id = ADISCORD_vorkerland_diplomacy.16 days = 1 }",
        "ADISCORD_vorkerland_begin_reunification = yes",
    ):
        if token not in protectorate_verify_compact:
            issues.append(f"{VERIFY_WKR_PROTECTORATE} lacks postcondition token {token}")
    if protectorate_verify.count('load_oob = "SOL"') != 1:
        issues.append("SOL worker protectorate must load its OOB exactly once behind fresh-release guard")
    gordon_returned = protectorate_verify_compact.find(
        "has_country_flag = ADISCORD_vorkerland_wkr_solyarino_gordon_returned"
    )
    promote_gordon = protectorate_verify_compact.find(
        "promote_character = { character = WRK_Richard_Gordon"
    )
    if gordon_returned < 0 or promote_gordon < 0 or gordon_returned >= promote_gordon:
        issues.append(
            "SOL worker protectorate verification must prove Gordon returned before promotion"
        )

    for event_id, retry_token, effect_name in (
        ("ADISCORD_vorkerland_diplomacy.13", "NOT = { has_global_flag = ADISCORD_vorkerland_sol_worker_protectorate_materialization_retry }", MATERIALIZE_WKR_PROTECTORATE),
        ("ADISCORD_vorkerland_diplomacy.14", "has_global_flag = ADISCORD_vorkerland_sol_worker_protectorate_materialization_retry", MATERIALIZE_WKR_PROTECTORATE),
        ("ADISCORD_vorkerland_diplomacy.15", "NOT = { has_global_flag = ADISCORD_vorkerland_sol_worker_protectorate_verify_retry }", VERIFY_WKR_PROTECTORATE),
        ("ADISCORD_vorkerland_diplomacy.16", "has_global_flag = ADISCORD_vorkerland_sol_worker_protectorate_verify_retry", VERIFY_WKR_PROTECTORATE),
    ):
        block = event_block(events, event_id)
        for token in (
            "hidden = yes",
            "is_triggered_only = yes",
            "tag = WKR",
            retry_token,
            f"{effect_name} = yes",
        ):
            if token not in block:
                issues.append(f"{event_id} lacks bounded protectorate token {token}")

    begin_reunification = named_block(phase_effects, "ADISCORD_vorkerland_begin_reunification")
    phase_six = event_block(phase_events, "ADISCORD_vorkerland_phase.6")
    phase_active_gate = (
        "NOT = { has_global_flag = "
        "ADISCORD_vorkerland_wkr_solyarino_intervention_active }"
    )
    if phase_active_gate not in begin_reunification or phase_active_gate not in phase_six:
        issues.append("reunification queue and phase.6 must both wait for WKR Solarino resolution")
    formation = named_block(phase_effects, "ADISCORD_vorkerland_form_wrk_from_wkr")
    for token in (
        "has_global_flag = ADISCORD_vorkerland_sol_worker_protectorate_verified",
        "autonomy_state = autonomy_free",
        "puppet = SOL",
        "autonomy_state = autonomy_district_in_Vorkerland",
        "set_cosmetic_tag = SOL_vorkerland_worker_protectorate",
        "set_country_flag = ADISCORD_vorkerland_sol_worker_protectorate_rebound_to_wrk",
    ):
        if token not in formation:
            issues.append(f"WKR-to-WRK formation does not preserve the SOL protectorate: {token}")

    cosmetic = named_block(cosmetics, "SOL_vorkerland_worker_protectorate")
    if "color = rgb" not in cosmetic or "color_ui = rgb" not in cosmetic:
        issues.append("SOL worker protectorate cosmetic tag lacks map/UI colours")
    for directory, size in (("", (82, 52)), ("medium", (41, 26)), ("small", (10, 7))):
        flag_path = ROOT / "gfx" / "flags" / directory / "SOL_vorkerland_worker_protectorate.tga"
        if not flag_path.is_file():
            issues.append(f"SOL worker protectorate flag is missing: {flag_path.relative_to(ROOT)}")
            continue
        try:
            with Image.open(flag_path) as image:
                if image.size != size:
                    issues.append(
                        f"SOL worker protectorate flag {flag_path.relative_to(ROOT)} "
                        f"has {image.size}, expected {size}"
                    )
        except OSError as exc:
            issues.append(f"cannot read SOL worker protectorate flag: {exc}")
    for source, label in ((english, "English"), (russian, "Russian")):
        for suffix in ("", "_DEF", "_ADJ"):
            if f"SOL_vorkerland_worker_protectorate{suffix}:" not in source:
                issues.append(f"{label} SOL worker protectorate localisation lacks {suffix or 'name'}")
    if not (ROOT / DIPLOMACY_RUSSIAN).read_bytes().startswith(b"\xef\xbb\xbf"):
        issues.append("Russian diplomacy localisation lost its UTF-8 BOM")
    for number in range(13, 17):
        if f'"id": "ADISCORD_vorkerland_diplomacy.{number}"' not in event_registry:
            issues.append(f"event registry lacks ADISCORD_vorkerland_diplomacy.{number}")

    for forbidden in (
        "ADISCORD_vorkerland_diplomacy.10 days = 1",
        "ADISCORD_vorkerland_diplomacy.11 days = 1",
    ):
        if forbidden in on_actions:
            issues.append(f"WKR verifier must not be requeued from on_actions: {forbidden}")

    active_gate = (
        "NOT = { has_global_flag = "
        "ADISCORD_vorkerland_wkr_solyarino_intervention_active }"
    )
    commit = named_block(focus_decisions, "ADISCORD_vorkerland_commit_to_central_showdown")
    scheduler = named_block(focus_effects, "ADISCORD_vorkerland_focus_schedule_final_showdown")
    if active_gate not in commit or active_gate not in scheduler:
        issues.append("central showdown must wait for the live WKR Solarino intervention")
    vad_decision = named_block(decisions, "ADISCORD_vorkerland_vad_restore_sol_by_force")
    vad_offer = named_block(effects, VAD_SOL_OFFER)
    if active_gate not in vad_decision or active_gate not in vad_offer:
        issues.append("VAD Solarino diplomacy must yield to an already active WKR intervention")

    air = _unique_block(effects, WKR_AIR_BOOTSTRAP, "WKR air bootstrap", issues)
    for token in (
        "NOT = { has_country_flag = ADISCORD_vorkerland_wkr_air_sustainment_bootstrap_applied }",
        "type = ADISCORD_fighter_airframe_2163 creator = \"WKR\"",
        "requested_factories = 2",
        "type = ADISCORD_cas_airframe_2170 creator = \"WKR\"",
        "requested_factories = 1",
        "amount = 24 producer = WKR",
        "amount = 12 producer = WKR",
    ):
        if token not in air:
            issues.append(f"{WKR_AIR_BOOTSTRAP} lacks sustainment token {token}")
    if air.count("add_equipment_production =") != 2:
        issues.append("WKR air bootstrap must create exactly two bounded production lines")

    forts = _unique_block(effects, WKR_DYNAMIC_FORTS, "WKR live-front fort effect", issues)
    for token in (
        "any_controlled_state =",
        "random_controlled_state =",
        "any_neighbor_state =",
        "controller = { has_war_with = WKR }",
        "type = bunker",
        "level = 1",
        "all_provinces = yes",
        "limit_to_border = yes",
        "limit = { controls_state = 33 }",
        "province = 3248",
    ):
        if token not in forts:
            issues.append(f"{WKR_DYNAMIC_FORTS} lacks dynamic fort token {token}")
    if "every_controlled_state =" in forts:
        issues.append(f"{WKR_DYNAMIC_FORTS} must fortify one live-front state, not the whole belt")
    if forts.count("random_controlled_state =") != 1:
        issues.append(f"{WKR_DYNAMIC_FORTS} must choose exactly one live-front state")
    if forts.count("type = bunker") != 2:
        issues.append(f"{WKR_DYNAMIC_FORTS} must define one live-front and one home redoubt")
    if forts.count("province = 3248") != 1:
        issues.append(f"{WKR_DYNAMIC_FORTS} must use one bounded southern home fallback")
    if forts.count("all_provinces = yes") != 1 or forts.count("limit_to_border = yes") != 1:
        issues.append(f"{WKR_DYNAMIC_FORTS} must keep the full border selector inside one state")
    for forbidden in ("16428", "province = 6713", "state = 40"):
        if forbidden in forts:
            issues.append(f"{WKR_DYNAMIC_FORTS} must not name the Unity Tower contract: {forbidden}")

    air_ai = _unique_block(ai, "ADISCORD_vorkerland_wkr_focus_air_sustainment", "WKR air AI", issues)
    for token in (
        "has_country_flag = ADISCORD_vorkerland_focus_wkr_air_sustainment",
        "equipment_production_min_factories id = fighter value = 2",
        "equipment_production_min_factories id = cas value = 1",
    ):
        if token not in air_ai:
            issues.append(f"WKR focus air AI lacks {token}")
    for tag in ("sol", "sra", "csl"):
        profile = _unique_block(
            ai,
            f"ADISCORD_vorkerland_wkr_solyarino_front_{tag}",
            "WKR Solarino front AI",
            issues,
        )
        upper = tag.upper()
        for token in (
            "has_global_flag = ADISCORD_vorkerland_wkr_solyarino_intervention_active",
            f"has_country_flag = ADISCORD_vorkerland_wkr_solyarino_target_{tag}",
            f"has_war_with = {upper}",
            f"front_unit_request tag = {upper} value = 40",
            f"conquer id = {upper} value = 250",
        ):
            if token not in profile:
                issues.append(f"WKR {upper} front AI lacks {token}")

    core_plans = (
        _unique_block(
            plans,
            "ADISCORD_vorkerland_wkr_pragmatist_core_plan",
            "WKR pragmatist core focus plan",
            issues,
        ),
        _unique_block(
            plans,
            "ADISCORD_vorkerland_wkr_utilitarian_core_plan",
            "WKR utilitarian core focus plan",
            issues,
        ),
    )
    operation_plan = _unique_block(
        plans,
        "ADISCORD_vorkerland_wkr_solyarino_operation_plan",
        "WKR intervention focus plan",
        issues,
    )
    for token in (
        "WKR_establish_workers_air_command",
        "WKR_raise_mobile_fortification_crews",
        "WKR_keep_frontline_sorties_flying",
        "WKR_secure_the_southern_corridor",
        "WKR_rehearse_operation_southbound",
    ):
        for core_plan in core_plans:
            if token not in core_plan:
                issues.append(f"WKR core focus plan omits {token}")
    for token in (
        "has_global_flag = ADISCORD_vorkerland_phase_central_preparation",
        "has_global_flag = ADISCORD_vorkerland_phase_central_showdown",
        "has_country_flag = ADISCORD_vorkerland_focus_wkr_central_war_unlocked",
        f"{WKR_INTERVENTION_BORDER} = yes",
        "ADISCORD_vorkerland_wkr_has_valid_solyarino_target = yes",
        "WKR_intervene_in_solyarino",
    ):
        if token not in operation_plan:
            issues.append(f"WKR intervention focus plan omits {token}")
    for stale_gate in (
        "has_global_flag = ADISCORD_vorkerland_focus_central_showdown_requested",
        "has_global_flag = ADISCORD_vorkerland_showdown_queue_initialized",
        "has_global_flag = ADISCORD_vorkerland_central_showdown_started",
        "has_global_flag = ADISCORD_vorkerland_vad_sol_alliance_accepted",
    ):
        if stale_gate in operation_plan:
            issues.append(f"WKR intervention AI plan still aborts for live showdown state: {stale_gate}")

    new_contract = "\n".join(
        (
            attempt,
            verify,
            cleanup,
            queue,
            outcome,
            materialize,
            protectorate_verify,
            settlement,
            outcome_event,
            air,
            forts,
        )
    )
    for forbidden in (
        "every_country",
        "random_country",
        "on_startup",
        "on_monthly",
        "monthly_pulse",
        "save repair",
        "save-repair",
    ):
        if forbidden in new_contract:
            issues.append(f"WKR bounded intervention contract contains forbidden {forbidden}")
    return list(dict.fromkeys(issues))


def collect_issues() -> list[str]:
    issues: list[str] = []
    for validator in (
        validate_terminal_outcomes,
        validate_bounded_outcome_hook,
        validate_peaceful_invitations,
        validate_vad_intervention_and_restoration,
        validate_counter_intervention,
        validate_wkr_solyarino_intervention,
        validate_showdown_allies,
        validate_vad_egc_route_priority,
        validate_core_packages,
    ):
        issues.extend(validator())
    return list(dict.fromkeys(issues))


def main() -> int:
    issues = collect_issues()
    if issues:
        print("A-Discord Vorkerland diplomacy validation failed:")
        for issue in issues:
            print(f"- {issue}")
        return 1
    print(
        "A-Discord Vorkerland diplomacy validation passed: exact regional winners, "
        "bounded peaceful invitations, reachable SOL restoration, shared-showdown "
        "allies/counter-intervention, bounded WKR Solarino worker protectorate, and "
        "independent WRK core packages are coherent."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
