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


ROOT = Path(__file__).resolve().parents[2]

DIPLOMACY_TRIGGERS = Path("common/scripted_triggers/ADISCORD_vorkerland_diplomacy_triggers.txt")
DIPLOMACY_EFFECTS = Path("common/scripted_effects/ADISCORD_vorkerland_diplomacy_effects.txt")
DIPLOMACY_DECISIONS = Path("common/decisions/ADISCORD_vorkerland_diplomacy_decisions.txt")
FOCUS_DECISIONS = Path("common/decisions/ADISCORD_vorkerland_focus_decisions.txt")
DIPLOMACY_EVENTS = Path("events/ADISCORD_vorkerland_diplomacy_events.txt")
DIPLOMACY_ON_ACTIONS = Path("common/on_actions/03_ADISCORD_vorkerland_diplomacy_on_actions.txt")
PHASE_EFFECTS = Path("common/scripted_effects/ADISCORD_vorkerland_phase_effects.txt")
PHASE_EVENTS = Path("events/ADISCORD_vorkerland_phase_events.txt")
COLLAPSE_EFFECTS = Path("common/scripted_effects/ADISCORD_vorkerland_collapse_effects.txt")

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
RESTORE_SOL = "ADISCORD_vorkerland_restore_sol_as_vad_puppet"
VERIFY_SOL = "ADISCORD_vorkerland_verify_sol_restoration"
ARM_WKR_COUNTER = "ADISCORD_vorkerland_arm_wkr_solar_counter_intervention"
JOIN_ALLIES = "ADISCORD_vorkerland_join_regional_allies_to_showdown"

VAD_SOL_ACCEPTED = "ADISCORD_vorkerland_vad_sol_alliance_accepted"
WKR_VLA_ACCEPTED = "ADISCORD_vorkerland_wkr_vla_alliance_accepted"
SOL_RESTORATION_INITIALIZED = "ADISCORD_vorkerland_sol_restoration_initialized"
SOL_RESTORATION_VERIFIED = "ADISCORD_vorkerland_sol_restoration_verified"
WKR_COUNTER_READY = "ADISCORD_vorkerland_wkr_solar_counter_intervention_ready"

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
        27, 34, 35, 40, 79, 81, 82, 102, 108, 109, 110, 111,
        122, 123, 124, 306, 308, 309, 320, 323, 325, 327,
    ),
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

    startup = named_block(on_actions, "on_startup")
    for token in (
        "ADISCORD_vorkerland_regional_diplomacy_repair_scheduled",
        "days = 7",
        "id = ADISCORD_vorkerland_diplomacy.1 days = 1",
    ):
        if token not in startup:
            issues.append(f"one-shot startup diplomacy repair lacks {token}")
    if startup.count("ADISCORD_vorkerland_regional_diplomacy_repair_scheduled") != 2:
        issues.append("startup diplomacy repair must have one guard and one timed flag assignment")

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
    collapse_effects = _load(COLLAPSE_EFFECTS, issues)
    contracts = (
        (
            VAD_SOL_OFFER,
            "ADISCORD_vorkerland_solar_winner_sol",
            "VAD",
            "SOL",
            VAD_SOL_ACCEPTED,
            "ADISCORD_vorkerland_vad_sol_invitation_pending",
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
            f"set_country_flag = {resolved_flag}",
            "set_country_flag = ADISCORD_vorkerland_preserve_wartime_faction",
            f"set_global_flag = {accepted_flag}",
            f"set_global_flag = {accepted_flag.replace('_accepted', '_declined')}",
        ):
            if token not in acceptance:
                issues.append(f"{event_id} lacks bounded acceptance/decline token {token}")
        for forbidden in ("declare_war_on", "add_to_war", "puppet =", "set_autonomy"):
            if forbidden in acceptance:
                issues.append(f"{event_id} must not start or merge a war during acceptance; found {forbidden}")

        decision = _unique_block(decisions, decision_id, "public alliance decision", issues)
        for token in (
            f"allowed = {{ tag = {inviter} }}",
            f"has_country_flag = {intent_flag}",
            f"has_global_flag = {winner_flag}",
            "NOT = { has_global_flag = ADISCORD_vorkerland_central_showdown_started }",
            f"complete_effect = {{ {effect_name} = yes }}",
            "fire_only_once = yes",
        ):
            if token not in compact(decision):
                issues.append(f"{decision_id} lacks public invitation contract {token}")

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
            "has_global_flag = ADISCORD_vorkerland_phase_central_preparation",
            "NOT = { has_global_flag = ADISCORD_vorkerland_central_showdown_started }",
            "NOT = { has_global_flag = ADISCORD_vorkerland_showdown_queue_initialized }",
            f"{VAD_INTERVENTION_BORDER} = yes",
            "has_global_flag = ADISCORD_vorkerland_solar_winner_sra",
            "has_global_flag = ADISCORD_vorkerland_solar_winner_csl",
            "set_global_flag = ADISCORD_vorkerland_vad_solar_intervention_active",
            "set_country_flag = ADISCORD_vorkerland_vad_solar_intervention_attempted",
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
        f"remove_effect = {{ {VAD_INTERVENTION} = yes }}",
        "fire_only_once = yes",
    ):
        if token not in compact(intervention_decision):
            issues.append(f"public VAD intervention decision lacks {token}")

    on_capitulation = named_block(on_actions, "on_capitulation")
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
    restoration_event = event_block(events, "ADISCORD_vorkerland_diplomacy.4")
    for token in ("is_triggered_only = yes", f"{RESTORE_SOL} = yes"):
        if token not in restoration_event:
            issues.append(f"ADISCORD_vorkerland_diplomacy.4 lacks {token}")

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
            "set_global_flag = ADISCORD_vorkerland_sol_restoration_retry",
            "country_event = { id = ADISCORD_vorkerland_diplomacy.5 days = 1 }",
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

    verify_event = event_block(events, "ADISCORD_vorkerland_diplomacy.5")
    for token in ("is_triggered_only = yes", f"{VERIFY_SOL} = yes"):
        if token not in verify_event:
            issues.append(f"ADISCORD_vorkerland_diplomacy.5 lacks {token}")
    return list(dict.fromkeys(issues))


def validate_counter_intervention() -> list[str]:
    issues: list[str] = []
    triggers = _load(DIPLOMACY_TRIGGERS, issues)
    effects = _load(DIPLOMACY_EFFECTS, issues)
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


def collect_issues() -> list[str]:
    issues: list[str] = []
    for validator in (
        validate_terminal_outcomes,
        validate_bounded_outcome_hook,
        validate_peaceful_invitations,
        validate_vad_intervention_and_restoration,
        validate_counter_intervention,
        validate_showdown_allies,
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
        "allies/counter-intervention, and independent WRK core packages are coherent."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
