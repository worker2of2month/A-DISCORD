#!/usr/bin/env python3
"""Validate focus-unlocked Vorkerland operations and bounded allied support."""

from __future__ import annotations

import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]

CATEGORY_FILE = Path(
    "common/decisions/categories/ADISCORD_vorkerland_focus_decision_categories.txt"
)
DECISION_FILE = Path("common/decisions/ADISCORD_vorkerland_focus_decisions.txt")
EFFECT_FILE = Path(
    "common/scripted_effects/ADISCORD_vorkerland_focus_decision_effects.txt"
)
PHASE_EFFECT_FILE = Path(
    "common/scripted_effects/ADISCORD_vorkerland_phase_effects.txt"
)
PHASE_TRIGGER_FILE = Path(
    "common/scripted_triggers/ADISCORD_vorkerland_phase_triggers.txt"
)
PHASE_EVENT_FILE = Path("events/ADISCORD_vorkerland_phase_events.txt")
EVENT_REGISTRY_FILE = Path("tools/data/adiscord_event_ids.json")
IDEA_FILE = Path("common/ideas/ADISCORD_vorkerland_focus_decision_ideas.txt")
ENGLISH_LOCALISATION = Path(
    "localisation/english/ADISCORD_vorkerland_focus_decisions_l_english.yml"
)
RUSSIAN_LOCALISATION = Path(
    "localisation/russian/ADISCORD_vorkerland_focus_decisions_l_russian.yml"
)

CENTRAL_DECISION = "ADISCORD_vorkerland_commit_to_central_showdown"
CENTRAL_EFFECT = "ADISCORD_vorkerland_focus_schedule_final_showdown"

CENTRAL_TARGETS = ("EYR", "EGC", "RIV", "REV", "YOR", "NDN", "SWB", "VHV", "OSV")
CENTRAL_WAVE_DECISION = "ADISCORD_vorkerland_launch_central_minor_wave"
LEGACY_CONTROLLER_MISSIONS = (
    "ADISCORD_vorkerland_focus_central_minor_launch_check",
    "ADISCORD_vorkerland_focus_central_minor_retry_check",
)
CENTRAL_WAVE_VERIFIER_EVENTS = {
    8: "ADISCORD_vorkerland_focus_confirm_central_minor_wave_launch = yes",
    9: "ADISCORD_vorkerland_focus_confirm_central_minor_wave_retry = yes",
}

CENTRAL_INTEGRATION_PACKAGES = {
    "EYR": ("ADISCORD_vorkerland_integrate_eyr_district", (102, 109, 111, 325), 21),
    "EGC": ("ADISCORD_vorkerland_integrate_egc_district", (81, 110, 124), 21),
    "RIV": ("ADISCORD_vorkerland_integrate_riv_district", (79, 306, 308, 309, 327), 21),
    "REV": ("ADISCORD_vorkerland_integrate_rev_district", (82, 323), 21),
    "YOR": ("ADISCORD_vorkerland_integrate_yor_district", (108, 122, 123), 21),
    "NDN": ("ADISCORD_vorkerland_integrate_ndn_district", (27,), 14),
    "SWB": ("ADISCORD_vorkerland_integrate_swb_district", (35,), 14),
    "VHV": ("ADISCORD_vorkerland_integrate_vhv_district", (315, 316, 317), 21),
    "OSV": ("ADISCORD_vorkerland_integrate_osv_district", (318, 320), 21),
}

CLAIMANT_HOME_STATES = (32, 33, 36, 37, 38, 39, 40, 75, 106, 107, 121, 200, 201, 324)

LEVY_DECISIONS = {
    "ADISCORD_vorkerland_wkr_retreat_levy_1": ("WKR", "0.20", "Workerland Militia", "0.55"),
    "ADISCORD_vorkerland_wkr_retreat_levy_2": ("WKR", "0.45", "Workerland Militia", "0.45"),
    "ADISCORD_vorkerland_vad_retreat_levy_1": (
        "VAD",
        "0.20",
        "Armi Security Detachment",
        "0.55",
    ),
    "ADISCORD_vorkerland_vad_retreat_levy_2": (
        "VAD",
        "0.45",
        "Armi Security Detachment",
        "0.45",
    ),
    "ADISCORD_vorkerland_tva_retreat_levy_1": ("TVA", "0.20", "TVA Collapse Militia", "0.55"),
    "ADISCORD_vorkerland_tva_retreat_levy_2": ("TVA", "0.45", "TVA Collapse Militia", "0.45"),
}

CORE_PACKAGES = {
    "ADISCORD_vorkerland_restore_core_claimant_homes": (
        32,
        33,
        36,
        37,
        38,
        39,
        75,
        106,
        107,
        121,
        200,
        201,
        324,
    ),
    "ADISCORD_vorkerland_restore_core_central_historical": (
        27,
        35,
        40,
        79,
        81,
        82,
        102,
        108,
        109,
        110,
        111,
        122,
        123,
        124,
        306,
        308,
        309,
        320,
        323,
        325,
        327,
    ),
    "ADISCORD_vorkerland_restore_core_oitfort": (34,),
    "ADISCORD_vorkerland_restore_core_rimat": (202,),
    "ADISCORD_vorkerland_restore_core_techlar": (105,),
    "ADISCORD_vorkerland_restore_core_ebern": (311,),
    "ADISCORD_vorkerland_restore_core_solar": (104, 198, 307),
}

CORE_FOCUS_UNLOCK = "ADISCORD_vorkerland_focus_postwar_core_decisions_unlocked"

SUPPORT_DECISIONS = {
    "ADISCORD_vorkerland_send_vla_support_tranche_1": ("WKR", "VLA"),
    "ADISCORD_vorkerland_send_vla_support_tranche_2": ("WKR", "VLA"),
    "ADISCORD_vorkerland_send_sol_support_tranche_1": ("VAD", "SOL"),
    "ADISCORD_vorkerland_send_sol_support_tranche_2": ("VAD", "SOL"),
}

LOCALISED_IDS = (
    "ADISCORD_vorkerland_focus_operations_category",
    "ADISCORD_vorkerland_allied_support_category",
    "ADISCORD_vorkerland_focus_central_minor_front_deadline",
    CENTRAL_WAVE_DECISION,
    *(package[0] for package in CENTRAL_INTEGRATION_PACKAGES.values()),
    CENTRAL_DECISION,
    *LEVY_DECISIONS,
    *CORE_PACKAGES,
    "ADISCORD_vorkerland_recognize_free_republics",
    *SUPPORT_DECISIONS,
    "ADISCORD_vorkerland_allied_supply_advisers",
)

TOOLTIP_IDS = (
    "ADISCORD_vorkerland_integrate_central_district_tt",
    "ADISCORD_vorkerland_central_showdown_command_ready_tt",
    "ADISCORD_vorkerland_central_showdown_campaigns_closed_tt",
    "ADISCORD_vorkerland_central_districts_integrated_tt",
    "ADISCORD_vorkerland_central_showdown_no_live_intervention_tt",
)


def read(relative: Path) -> str:
    return (ROOT / relative).read_text(encoding="utf-8-sig")


def named_block(text: str, name: str) -> str:
    match = re.search(rf"(?m)^\s*{re.escape(name)}\s*=\s*\{{", text)
    if not match:
        return ""
    start = text.find("{", match.start())
    depth = 0
    in_quote = False
    escaped = False
    for index in range(start, len(text)):
        char = text[index]
        if in_quote:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_quote = False
            continue
        if char == '"':
            in_quote = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[match.start() : index + 1]
    raise ValueError(f"unterminated block {name}")


def named_blocks(text: str, name: str) -> list[str]:
    blocks: list[str] = []
    cursor = 0
    pattern = re.compile(rf"(?m)^\s*{re.escape(name)}\s*=\s*\{{")
    while match := pattern.search(text, cursor):
        block = named_block(text[match.start() :], name)
        if not block:
            break
        blocks.append(block)
        cursor = match.start() + len(block)
    return blocks


def localisation_entries(text: str) -> dict[str, str]:
    return {
        match.group(1): match.group(2)
        for match in re.finditer(
            r'(?m)^\s+([A-Za-z0-9_]+):(?:\d+)?\s+"(.*)"\s*$', text
        )
    }


def expected_localisation_keys() -> set[str]:
    return {
        *LOCALISED_IDS,
        *(f"{entry}_desc" for entry in LOCALISED_IDS),
        *TOOLTIP_IDS,
    }


def collect_issues() -> list[str]:
    issues: list[str] = []
    paths = (
        CATEGORY_FILE,
        DECISION_FILE,
        EFFECT_FILE,
        PHASE_EFFECT_FILE,
        PHASE_TRIGGER_FILE,
        PHASE_EVENT_FILE,
        EVENT_REGISTRY_FILE,
        IDEA_FILE,
        ENGLISH_LOCALISATION,
        RUSSIAN_LOCALISATION,
    )
    for relative in paths:
        if not (ROOT / relative).is_file():
            issues.append(f"missing {relative.as_posix()}")
    if issues:
        return issues

    categories = read(CATEGORY_FILE)
    decisions = read(DECISION_FILE)
    effects = read(EFFECT_FILE)
    phase_effects = read(PHASE_EFFECT_FILE)
    phase_triggers = read(PHASE_TRIGGER_FILE)
    phase_events = read(PHASE_EVENT_FILE)
    event_registry = read(EVENT_REGISTRY_FILE)
    ideas = read(IDEA_FILE)

    minor_phase_trigger = named_block(
        phase_triggers, "ADISCORD_vorkerland_central_minor_campaign_phase_available"
    )
    if "has_global_flag = ADISCORD_vorkerland_phase_central_preparation" not in minor_phase_trigger:
        issues.append("central minor campaign phase trigger lacks central preparation")
    for forbidden in (
        "has_global_flag = ADISCORD_vorkerland_phase_central_showdown",
        "has_global_flag = ADISCORD_vorkerland_phase_reunification",
        "ADISCORD_vorkerland_has_single_surviving_claimant = yes",
        "tag = WRK",
        "has_global_flag = ADISCORD_vorkerland_phase_postwar_integration",
        "has_global_flag = ADISCORD_vorkerland_reunification_verified",
        "has_country_flag = ADISCORD_vorkerland_route_worker",
        "has_country_flag = ADISCORD_vorkerland_route_joint",
        "has_country_flag = ADISCORD_vorkerland_route_utilitarian",
    ):
        if forbidden in minor_phase_trigger:
            issues.append(
                f"central minor campaign phase trigger reopens after preparation: {forbidden}"
            )
    district_control_trigger = named_block(
        phase_triggers, "ADISCORD_vorkerland_central_districts_owned_and_controlled"
    )
    claimant_graph_trigger = named_block(
        phase_triggers, "ADISCORD_vorkerland_central_districts_inside_claimant_graph"
    )
    for state in sorted(
        state
        for _, states, _ in CENTRAL_INTEGRATION_PACKAGES.values()
        for state in states
    ):
        if district_control_trigger.count(f"controls_state = {state}") != 1:
            issues.append(f"terminal district controller does not require control of state {state}")
        owner_gate = (
            f"{state} = {{ OR = {{ is_owned_by = WKR is_owned_by = VAD "
            "is_owned_by = TVA } }"
        )
        if owner_gate not in district_control_trigger:
            issues.append(f"terminal district controller accepts an external owner in state {state}")
        graph_state = named_block(claimant_graph_trigger, str(state))
        for token in (
            "OR = { is_owned_by = WKR is_owned_by = VAD is_owned_by = TVA }",
            "OR = { is_controlled_by = WKR is_controlled_by = VAD is_controlled_by = TVA }",
        ):
            if token not in graph_state:
                issues.append(f"pre-showdown claimant graph state {state} lacks {token}")

    for category in (
        "ADISCORD_vorkerland_focus_operations_category",
        "ADISCORD_vorkerland_allied_support_category",
    ):
        if not named_block(categories, category):
            issues.append(f"missing category {category}")
        if not named_block(decisions, category):
            issues.append(f"missing decision group {category}")

    target_tags = tuple(CENTRAL_TARGETS)
    wave = named_block(decisions, CENTRAL_WAVE_DECISION)
    launcher = named_block(effects, "ADISCORD_vorkerland_focus_launch_central_minor_wave")
    wave_visible = named_block(wave, "visible")
    wave_available = named_block(wave, "available")
    viability_trigger_name = "ADISCORD_vorkerland_has_adjacent_viable_central_minor"
    viability_trigger = named_block(phase_triggers, viability_trigger_name)
    for scope_name, scope in (("visible", wave_visible), ("available", wave_available)):
        if scope.count(f"{viability_trigger_name} = yes") != 1:
            issues.append(
                f"central minor wave {scope_name} must require exactly one viable-target trigger"
            )
    for token in (
        "ADISCORD_vorkerland_central_minor_campaign_phase_available = yes",
        "ADISCORD_vorkerland_focus_central_minor_launch_pending",
        "ADISCORD_vorkerland_focus_central_minor_recovery_cooldown",
        "days_remove = 1",
        "fire_only_once = no",
        "ADISCORD_vorkerland_focus_cleanup_central_minor_front = yes",
        "remove_effect = { ADISCORD_vorkerland_focus_launch_central_minor_wave = yes }",
        "ai_will_do = { factor = 900 }",
    ):
        if token not in wave:
            issues.append(f"central minor wave decision lacks {token}")
    for target in target_tags:
        viable_branch = (
            f"AND = {{ any_neighbor_country = {{ tag = {target} }} "
            f"{target} = {{ exists = yes is_subject = no "
            "NOT = { has_capitulated = yes } "
            "NOT = { OR = { has_war_with = WKR has_war_with = VAD "
            "has_war_with = TVA } } } }"
        )
        if viability_trigger.count(viable_branch) != 1:
            issues.append(
                f"central minor viable-target trigger must define {target} exactly once"
            )
        for token in (
            f"any_neighbor_country = {{ tag = {target} }}",
            f"{target} = {{ exists = yes is_subject = no",
            f"set_country_flag = ADISCORD_vorkerland_focus_central_minor_target_{target.lower()}",
            f"{target} = {{ ADISCORD_vorkerland_leave_inherited_faction = yes }}",
        ):
            if token not in wave:
                issues.append(f"central minor wave decision lacks {target} token {token}")
        declaration = f"declare_war_on = {{ target = {target} type = annex_everything }}"
        if launcher.count(declaration) != 1:
            issues.append(f"central minor wave launcher must declare {target} exactly once")
    if launcher.count("declare_war_on = {") != len(target_tags):
        issues.append("central minor wave launcher must contain all nine independent declarations")
    if "else_if =" in launcher:
        issues.append("central minor wave launcher must not serialize targets with else_if")

    complete_effect = named_block(wave, "complete_effect")
    pending_setter = (
        "set_country_flag = ADISCORD_vorkerland_focus_central_minor_launch_pending"
    )
    pending_guards = [
        block for block in named_blocks(complete_effect, "if") if pending_setter in block
    ]
    if len(pending_guards) != 1:
        issues.append("central minor wave must set launch pending in exactly one guarded branch")
    else:
        pending_guard = pending_guards[0]
        if "OR = {" not in pending_guard:
            issues.append("central minor launch-pending branch lacks recorded-target OR guard")
        for target in target_tags:
            flag = (
                "has_country_flag = "
                f"ADISCORD_vorkerland_focus_central_minor_target_{target.lower()}"
            )
            if flag not in pending_guard:
                issues.append(f"central minor launch-pending guard lacks recorded target {target}")
    if decisions.count(pending_setter) + effects.count(pending_setter) != 1:
        issues.append("central minor launch pending may only be set by its recorded-target guard")
    if not any(
        "ADISCORD_vorkerland_focus_cleanup_central_minor_front = yes" in block
        for block in named_blocks(complete_effect, "else")
    ):
        issues.append("central minor wave lacks empty-target cleanup fallback")

    launch_event_call = "country_event = { id = ADISCORD_vorkerland_phase.8 days = 1 }"
    launcher_event_guards = [
        block for block in named_blocks(launcher, "if") if launch_event_call in block
    ]
    if launcher.count(launch_event_call) != 1 or len(launcher_event_guards) != 1:
        issues.append("central minor launcher must schedule phase.8 once from its guarded branch")
    elif not all(
        f"ADISCORD_vorkerland_focus_central_minor_target_{target.lower()}" in launcher_event_guards[0]
        for target in target_tags
    ):
        issues.append("central minor phase.8 scheduling branch lacks the recorded target set")
    for legacy in (
        "ADISCORD_vorkerland_consolidate_eyr",
        "ADISCORD_vorkerland_consolidate_egc",
        "ADISCORD_vorkerland_consolidate_riv",
        "ADISCORD_vorkerland_consolidate_rev",
        "ADISCORD_vorkerland_consolidate_yor",
        "ADISCORD_vorkerland_consolidate_ndn",
        "ADISCORD_vorkerland_consolidate_swb",
        "ADISCORD_vorkerland_consolidate_vhv",
        "ADISCORD_vorkerland_consolidate_osv",
        "ADISCORD_vorkerland_focus_launch_minor_",
    ):
        if legacy in decisions or legacy in effects:
            issues.append(f"legacy serialized central-front producer remains: {legacy}")

    deadline = named_block(
        decisions, "ADISCORD_vorkerland_focus_central_minor_front_deadline"
    )
    controller_sources = {
        DECISION_FILE.as_posix(): decisions,
        EFFECT_FILE.as_posix(): effects,
        PHASE_TRIGGER_FILE.as_posix(): phase_triggers,
        PHASE_EVENT_FILE.as_posix(): phase_events,
    }
    for mission_id in LEGACY_CONTROLLER_MISSIONS:
        for source_name, source in controller_sources.items():
            if mission_id in source:
                issues.append(f"legacy controller mission remains in {source_name}: {mission_id}")
            for operation in ("activate_mission", "remove_mission"):
                if f"{operation} = {mission_id}" in source:
                    issues.append(
                        f"legacy controller {operation} remains in {source_name}: {mission_id}"
                    )

    event_blocks = named_blocks(phase_events, "country_event")
    for number, callback in CENTRAL_WAVE_VERIFIER_EVENTS.items():
        event_id = f"ADISCORD_vorkerland_phase.{number}"
        matching = [block for block in event_blocks if f"id = {event_id}" in block]
        if len(matching) != 1:
            issues.append(f"central minor verifier event {event_id} must be defined exactly once")
            continue
        event = matching[0]
        for token in ("hidden = yes", "is_triggered_only = yes"):
            if token not in event:
                issues.append(f"central minor verifier event {event_id} lacks {token}")
        immediate = named_block(event, "immediate")
        if immediate.count(callback) != 1:
            issues.append(f"central minor verifier event {event_id} must call {callback} once")

    try:
        registry_events = json.loads(event_registry).get("events", [])
    except (json.JSONDecodeError, AttributeError):
        issues.append("event registry is not valid JSON with an events list")
        registry_events = []
    for number in CENTRAL_WAVE_VERIFIER_EVENTS:
        event_id = f"ADISCORD_vorkerland_phase.{number}"
        matches = [entry for entry in registry_events if entry.get("id") == event_id]
        expected = {
            "id": event_id,
            "namespace": "ADISCORD_vorkerland_phase",
            "number": number,
            "owner": PHASE_EVENT_FILE.as_posix(),
            "subsystem": "vorkerland_phase",
            "status": "active",
        }
        if matches != [expected]:
            issues.append(f"event registry entry for {event_id} is missing or not canonical")
    for token in (
        "ADISCORD_vorkerland_focus_central_minor_deadline_active",
        "selectable_mission = no",
        "fire_only_once = no",
        "days_mission_timeout = 240",
        "ADISCORD_vorkerland_focus_finish_central_minor_wave = yes",
        "ADISCORD_vorkerland_focus_resolve_central_minor_wave_deadline = yes",
    ):
        if token not in deadline:
            issues.append(f"central minor deadline lacks protracted-front token {token}")

    first_confirmation = named_block(
        effects, "ADISCORD_vorkerland_focus_confirm_central_minor_wave_launch"
    )
    retry_confirmation = named_block(
        effects, "ADISCORD_vorkerland_focus_confirm_central_minor_wave_retry"
    )
    resolver = named_block(
        effects, "ADISCORD_vorkerland_focus_resolve_central_minor_wave_deadline"
    )
    for token in (
        "ADISCORD_vorkerland_central_minor_campaign_phase_available = yes",
        "has_country_flag = ADISCORD_vorkerland_focus_central_minor_launch_pending",
        "NOT = { has_country_flag = ADISCORD_vorkerland_focus_central_minor_launch_retry }",
        "ADISCORD_vorkerland_has_retryable_recorded_central_minor_front = yes",
        "ADISCORD_vorkerland_focus_central_minor_launch_retry",
        "ADISCORD_vorkerland_focus_retry_central_minor_wave_declarations = yes",
        "country_event = { id = ADISCORD_vorkerland_phase.9 days = 1 }",
        "ADISCORD_vorkerland_focus_arm_central_minor_deadline = yes",
    ):
        if token not in first_confirmation:
            issues.append(f"central minor first confirmation lacks one-retry token {token}")
    retry_event_call = "country_event = { id = ADISCORD_vorkerland_phase.9 days = 1 }"
    retry_branches = [
        block
        for block in named_blocks(first_confirmation, "else_if")
        if retry_event_call in block
    ]
    if len(retry_branches) != 1:
        issues.append("central minor first confirmation must contain one guarded retry branch")
    else:
        for token in (
            "ADISCORD_vorkerland_central_minor_campaign_phase_available = yes",
            "has_country_flag = ADISCORD_vorkerland_focus_central_minor_launch_pending",
            "NOT = { has_country_flag = ADISCORD_vorkerland_focus_central_minor_launch_retry }",
            "ADISCORD_vorkerland_has_retryable_recorded_central_minor_front = yes",
            "is_subject = no",
            "NOT = { has_capitulated = yes }",
            "set_country_flag = ADISCORD_vorkerland_focus_central_minor_launch_retry",
            "ADISCORD_vorkerland_focus_retry_central_minor_wave_declarations = yes",
            retry_event_call,
        ):
            if token not in retry_branches[0]:
                issues.append(f"central minor guarded retry branch lacks {token}")
    for token in (
        "set_country_flag = ADISCORD_vorkerland_focus_central_minor_launch_retry",
        "ADISCORD_vorkerland_focus_retry_central_minor_wave_declarations = yes",
        retry_event_call,
    ):
        if first_confirmation.count(token) != 1:
            issues.append(f"central minor first confirmation must contain {token} exactly once")
    for token in (
        "ADISCORD_vorkerland_central_minor_campaign_phase_available = yes",
        "ADISCORD_vorkerland_focus_arm_central_minor_deadline = yes",
    ):
        if token not in retry_confirmation:
            issues.append(f"central minor retry confirmation lacks prepared-front token {token}")
    if effects.count(retry_event_call) != 1:
        issues.append("central minor retry verifier must be scheduled exactly once")
    for forbidden in (
        "country_event = { id = ADISCORD_vorkerland_phase.8",
        "country_event = { id = ADISCORD_vorkerland_phase.9",
        "set_country_flag = ADISCORD_vorkerland_focus_central_minor_launch_retry",
        "ADISCORD_vorkerland_focus_retry_central_minor_wave_declarations = yes",
    ):
        if forbidden in retry_confirmation:
            issues.append(f"central minor retry confirmation may not recurse through {forbidden}")

    retryable_trigger = named_block(
        phase_triggers, "ADISCORD_vorkerland_has_retryable_recorded_central_minor_front"
    )
    for target in target_tags:
        retryable_branch = (
            "AND = { has_country_flag = "
            f"ADISCORD_vorkerland_focus_central_minor_target_{target.lower()} "
            f"NOT = {{ has_war_with = {target} }} "
            f"any_neighbor_country = {{ tag = {target} }} "
            f"{target} = {{ exists = yes is_subject = no "
            "NOT = { has_capitulated = yes } "
            "NOT = { OR = { has_war_with = WKR has_war_with = VAD "
            "has_war_with = TVA } } } }"
        )
        if retryable_trigger.count(retryable_branch) != 1:
            issues.append(
                f"central minor retryable trigger must define recorded target {target} exactly once"
            )
    finish_wave = named_block(
        effects, "ADISCORD_vorkerland_focus_finish_central_minor_wave"
    )
    for token in (
        "ADISCORD_vorkerland_focus_central_minor_recovery_cooldown",
        "days = 14",
        "ADISCORD_vorkerland_focus_cleanup_central_minor_front = yes",
    ):
        if token not in finish_wave:
            issues.append(f"central minor wave finish lacks regroup token {token}")
    if "ADISCORD_vorkerland_focus_finish_central_minor_wave = yes" not in retry_confirmation:
        issues.append("central minor failed retry does not enter wave regrouping")
    for forbidden in ("transfer_state", "white_peace", "annex_country"):
        if forbidden in resolver:
            issues.append(
                f"central minor deadline may not force a genuine belligerent outcome: {forbidden}"
            )
    for token in (
        "ADISCORD_vorkerland_focus_central_minor_front_protracted",
        "days = 180",
        "ADISCORD_vorkerland_focus_finish_central_minor_wave = yes",
        "live war remains unresolved",
    ):
        if token not in resolver:
            issues.append(f"central minor deadline diagnostic lacks {token}")
    for target in target_tags:
        declaration = f"declare_war_on = {{ target = {target} type = annex_everything }}"
        if effects.count(declaration) != 2:
            issues.append(f"{target} must have exactly one wave declaration and one retry")

    integrated_states: list[int] = []
    for target, (decision_id, states, duration) in CENTRAL_INTEGRATION_PACKAGES.items():
        block = named_block(decisions, decision_id)
        integrated_states.extend(states)
        for token in (
            "allowed = { OR = { tag = WKR tag = VAD tag = TVA tag = WRK } }",
            "ADISCORD_vorkerland_central_minor_campaign_phase_available = yes",
            f"NOT = {{ country_exists = {target} }}",
            f"days_remove = {duration}",
            "days_re_enable = 7",
            "fire_only_once = no",
            "custom_effect_tooltip = ADISCORD_vorkerland_integrate_central_district_tt",
            "ADISCORD_vorkerland_begin_reunification = yes",
            "ai_will_do = { factor = 600 }",
        ):
            if token not in block:
                issues.append(f"{decision_id} lacks bounded civil-integration token {token}")
        if "complete_effect =" in block or "remove_effect =" not in block:
            issues.append(f"{decision_id} must award cores only after its timed work finishes")
        expected_cost = 10 if len(states) == 1 else 15
        if f"cost = {expected_cost}" not in block:
            issues.append(f"{decision_id} has wrong proportional cost")
        for state in states:
            if block.count(f"owns_state = {state}") < 3:
                issues.append(f"{decision_id} must recheck ownership of state {state} at completion")
            if block.count(f"controls_state = {state}") < 2:
                issues.append(f"{decision_id} must recheck control of state {state} at completion")
            if not re.search(
                rf"\b{state}\s*=\s*\{{\s*add_core_of\s*=\s*ROOT\s*\}}", block
            ):
                issues.append(f"{decision_id} does not core exactly secured state {state}")
            if not re.search(
                rf"\b{state}\s*=\s*\{{\s*NOT\s*=\s*\{{\s*is_core_of\s*=\s*ROOT", block
            ):
                issues.append(f"{decision_id} lacks already-integrated visibility guard for {state}")
        if "every_owned_state" in block or "every_state" in block:
            issues.append(f"{decision_id} must not use bulk coring")
    if len(integrated_states) != len(set(integrated_states)) or len(integrated_states) != 24:
        issues.append("central civil-integration packages must be disjoint and cover exactly 24 states")

    central = named_block(decisions, CENTRAL_DECISION)
    central_effect = named_block(effects, CENTRAL_EFFECT)
    central_visible = named_block(central, "visible")
    central_available = named_block(central, "available")
    command_ready_tooltip = (
        "tooltip = ADISCORD_vorkerland_central_showdown_command_ready_tt"
    )
    if "ADISCORD_vorkerland_phase_central_preparation" not in central_visible:
        issues.append("final showdown must become visible during central preparation")
    if (
        "ADISCORD_vorkerland_focus_central_front_prepared" in central_visible
        or "central_war_unlocked" in central_visible
    ):
        issues.append("final showdown hides its command-readiness blocker")
    if (
        command_ready_tooltip not in central_available
        or "ADISCORD_vorkerland_focus_central_front_prepared" not in central_available
    ):
        issues.append("final showdown must explain command readiness in available")
    for tag in ("WKR", "VAD", "TVA"):
        hook = f"ADISCORD_vorkerland_focus_{tag.lower()}_central_war_unlocked"
        if hook not in central_available or hook not in central_effect:
            issues.append(f"central controller request lacks exact {tag} hook {hook}")
    for token in (
        "ADISCORD_vorkerland_focus_central_showdown_requested",
        "ADISCORD_vorkerland_showdown_queue_initialized",
        "ADISCORD_vorkerland_central_showdown_started",
    ):
        if token not in central or token not in central_effect:
            issues.append(f"central controller request lacks global guard {token}")
    if "country_event = { id = ADISCORD_vorkerland_phase.4 days = 1 }" not in central_effect:
        issues.append("final showdown must explicitly schedule the shared phase.4 controller hook")
    for target in target_tags:
        terminal = f"NOT = {{ country_exists = {target} }}"
        if terminal not in central or terminal not in central_effect:
            issues.append(f"final showdown lacks terminal gate for {target}")
        if f"{target} = {{ is_subject = yes }}" in central or f"{target} = {{ is_subject = yes }}" in central_effect:
            issues.append(f"final showdown incorrectly accepts a live {target} puppet as terminal")
        if f"has_war_with = {target}" not in central or f"has_war_with = {target}" not in central_effect:
            issues.append(f"final showdown ignores live consolidation front {target}")
    for state in integrated_states:
        core_gate = f"{state} = {{ OR = {{ is_core_of = WKR is_core_of = VAD is_core_of = TVA }} }}"
        if core_gate not in central or core_gate not in central_effect:
            issues.append(f"final showdown can bypass civil integration of state {state}")
    for tooltip in (
        "ADISCORD_vorkerland_central_showdown_command_ready_tt",
        "ADISCORD_vorkerland_central_showdown_campaigns_closed_tt",
        "ADISCORD_vorkerland_central_districts_integrated_tt",
        "ADISCORD_vorkerland_central_showdown_no_live_intervention_tt",
    ):
        if f"tooltip = {tooltip}" not in central:
            issues.append(f"final showdown lacks the readable blocker tooltip {tooltip}")
    for token in (
        "ADISCORD_vorkerland_phase_central_preparation",
        "ADISCORD_vorkerland_focus_central_minor_launch_pending",
        "ADISCORD_vorkerland_focus_central_minor_deadline_active",
    ):
        if token not in central or token not in central_effect:
            issues.append(f"final showdown lacks consolidation-stage guard {token}")
    for token in (
        "fire_only_once = no",
        "days_re_enable = 7",
        "NOT = { has_global_flag = ADISCORD_vorkerland_showdown_retry_cooldown }",
        "ai_will_do = { factor = 1000 }",
    ):
        if token not in central:
            issues.append(f"repeatable central decision lacks retry contract {token}")
    if "NOT = { has_global_flag = ADISCORD_vorkerland_showdown_retry_cooldown }" not in central_effect:
        issues.append("central showdown scheduler lacks retry cooldown guard")
    live_intervention = (
        "NOT = { has_global_flag = ADISCORD_vorkerland_vad_solar_intervention_active }"
    )
    if live_intervention not in central or live_intervention not in central_effect:
        issues.append("final showdown must wait only for an actually active Solar restoration war")
    for optional_blocker in (
        "ADISCORD_vorkerland_vad_solar_intervention_reserved",
        "ADISCORD_vorkerland_vad_sol_invitation_pending",
        "ADISCORD_vorkerland_wkr_vla_invitation_pending",
        "ADISCORD_vorkerland_wkr_solar_counter_intervention_ready",
        "ADISCORD_vorkerland_wkr_has_solar_counter_border",
        "ADISCORD_vorkerland_sol_restoration_verified",
    ):
        if optional_blocker in central or optional_blocker in central_effect:
            issues.append(f"optional diplomacy still blocks the final showdown: {optional_blocker}")
    for forbidden in ("declare_war_on", "start_civil_war", "create_wargoal"):
        if forbidden in central or forbidden in central_effect:
            issues.append(f"central focus decision contains forbidden private-war effect {forbidden}")

    reunification = named_block(phase_effects, "ADISCORD_vorkerland_begin_reunification")
    inherit_cores = named_block(
        phase_effects, "ADISCORD_vorkerland_inherit_integrated_claimant_cores"
    )
    formation = named_block(phase_effects, "ADISCORD_vorkerland_finalize_wrk_formation")
    for target in target_tags:
        if f"NOT = {{ country_exists = {target} }}" not in reunification:
            issues.append(f"reunification lacks terminal government gate for {target}")
    for phase in (
        "ADISCORD_vorkerland_phase_central_showdown",
        "ADISCORD_vorkerland_phase_reunification",
    ):
        if phase not in reunification:
            issues.append(f"reunification entry gate lacks phase {phase}")
    if reunification.count(
        "ADISCORD_vorkerland_central_districts_owned_and_controlled = yes"
    ) != 3:
        issues.append("reunification must evaluate district ownership/control in each live claimant")
    for flag in (
        "ADISCORD_vorkerland_focus_central_minor_launch_pending",
        "ADISCORD_vorkerland_focus_central_minor_deadline_active",
    ):
        if reunification.count(flag) != 3:
            issues.append(f"reunification must check {flag} for all three claimants")
    inherited_states = sorted(set(integrated_states).union(CLAIMANT_HOME_STATES))
    for state in integrated_states:
        gate = f"{state} = {{ OR = {{ is_core_of = WKR is_core_of = VAD is_core_of = TVA }} }}"
        if gate not in reunification:
            issues.append(f"reunification can skip integration of state {state}")
    for state in inherited_states:
        state_block = named_block(inherit_cores, str(state))
        for token in (
            "is_owned_by = WRK",
            "OR = { is_core_of = WKR is_core_of = VAD is_core_of = TVA }",
            "add_core_of = WRK",
            "remove_core_of = WKR",
            "remove_core_of = VAD",
            "remove_core_of = TVA",
        ):
            if token not in state_block:
                issues.append(f"inherited core state {state} lacks safe token {token}")
        if "is_controlled_by = WRK" in state_block:
            issues.append(
                f"inherited core state {state} can lose earned integration to transient control"
            )
    inherited_block_states = sorted(
        int(value)
        for value in re.findall(r"(?m)^\s*(\d+)\s*=\s*\{", inherit_cores)
    )
    if inherited_block_states != inherited_states:
        issues.append("claimant-core inheritance must contain exactly its 38 explicit states")
    if "ADISCORD_vorkerland_inherit_integrated_claimant_cores = yes" not in formation:
        issues.append("WRK formation does not inherit verified claimant cores")

    for decision_id, (tag, threshold, template, equipment_factor) in LEVY_DECISIONS.items():
        block = named_block(decisions, decision_id)
        effect_id = decision_id.replace(
            "ADISCORD_vorkerland_", "ADISCORD_vorkerland_raise_", 1
        )
        effect = named_block(effects, effect_id)
        hook = f"ADISCORD_vorkerland_focus_{tag.lower()}_retreat_levies_unlocked"
        for token in (
            f"tag = {tag}",
            hook,
            f"surrender_progress > {threshold}",
            "has_manpower >",
            "capital_scope = { is_owned_by = ROOT is_controlled_by = ROOT }",
            "days_remove =",
            "fire_only_once = no",
            "ai_will_do = { factor =",
        ):
            if token not in block:
                issues.append(f"{decision_id} lacks bounded levy contract {token}")
        if not effect:
            issues.append(f"{decision_id} lacks delayed effect {effect_id}")
            continue
        if effect.count("create_unit = {") != 1:
            issues.append(f"{effect_id} must create exactly one unit")
        for token in (
            "has_war = yes",
            "NOT = { has_capitulated = yes }",
            f"surrender_progress > {threshold}",
            f'division_template = \\"{template}\\"',
            "start_experience_factor = 0.0",
            f"start_equipment_factor = {equipment_factor}",
            "owner = PREV",
        ):
            if token not in effect:
                issues.append(f"{effect_id} lacks weak existing-template token {token}")
        for forbidden in ("load_oob", "add_manpower", "add_equipment_to_stockpile", "count ="):
            if forbidden in effect:
                issues.append(f"{effect_id} contains unbounded levy token {forbidden}")

    all_package_states: list[int] = []
    for decision_id, states in CORE_PACKAGES.items():
        block = named_block(decisions, decision_id)
        all_package_states.extend(states)
        for token in (
            "tag = WRK",
            "ADISCORD_vorkerland_phase_postwar_integration",
            "ADISCORD_vorkerland_reunification_verified",
            CORE_FOCUS_UNLOCK,
            "fire_only_once = yes",
        ):
            if token not in block:
                issues.append(f"{decision_id} lacks postwar core guard {token}")
        for state in states:
            if f"owns_state = {state}" not in block or f"controls_state = {state}" not in block:
                issues.append(f"{decision_id} must own and control state {state}")
            if not re.search(rf"\b{state}\s*=\s*\{{\s*add_core_of\s*=\s*WRK\s*\}}", block):
                issues.append(f"{decision_id} does not explicitly core state {state}")
        if "every_owned_state" in block or "every_state" in block:
            issues.append(f"{decision_id} must not use bulk state iteration")
        owned_states = tuple(int(value) for value in re.findall(r"owns_state\s*=\s*(\d+)", block))
        controlled_states = tuple(
            int(value) for value in re.findall(r"controls_state\s*=\s*(\d+)", block)
        )
        cored_states = tuple(
            int(value)
            for value in re.findall(
                r"\b(\d+)\s*=\s*\{\s*add_core_of\s*=\s*WRK\s*\}", block
            )
        )
        if owned_states != states or controlled_states != states or cored_states != states:
            issues.append(f"{decision_id} must contain exactly its declared state package")
        country_flags = set(re.findall(r"has_country_flag\s*=\s*([A-Za-z0-9_]+)", block))
        if country_flags != {CORE_FOCUS_UNLOCK} or "set_country_flag =" in block:
            issues.append(
                f"{decision_id} must depend only on the shared focus unlock, not other core-package flags"
            )
        if re.search(r"\b(?:SOL|VLA)\s*=", block):
            issues.append(f"{decision_id} must not depend on a live SOL or VLA country")
    if len(all_package_states) != len(set(all_package_states)):
        issues.append("postwar core packages overlap")
    forbidden_buffer_states = set(range(331, 341))
    leaked_buffer_states = forbidden_buffer_states.intersection(all_package_states)
    if leaked_buffer_states:
        issues.append(f"postwar core packages include forbidden buffer states {sorted(leaked_buffer_states)}")

    support_category = named_block(categories, "ADISCORD_vorkerland_allied_support_category")
    for token in (
        "ADISCORD_vorkerland_wkr_vla_alliance_accepted",
        "ADISCORD_vorkerland_vad_sol_alliance_accepted",
        "ADISCORD_vorkerland_sol_restoration_verified",
        "OR = { is_in_faction_with = ROOT is_subject_of = ROOT }",
    ):
        if token not in support_category:
            issues.append(f"allied-support category lacks diplomatic outcome token {token}")

    for decision_id, (donor, ally) in SUPPORT_DECISIONS.items():
        block = named_block(decisions, decision_id)
        effect = named_block(effects, decision_id)
        for token in (
            f"tag = {donor}",
            f"{ally} = {{",
            "NOT = { has_capitulated = yes }",
            "has_war = yes",
            "has_manpower > 2999",
            "has_political_power > 49",
            "has_equipment = { infantry_equipment > 1499 support_equipment > 149 }",
            "days_remove = 5",
            "fire_only_once = no",
            "ai_will_do = { factor = 500",
        ):
            if token not in block:
                issues.append(f"{decision_id} lacks smart allied-support gate {token}")
        if ally == "VLA":
            handshake = "ADISCORD_vorkerland_wkr_vla_alliance_accepted"
            if block.count(handshake) < 2 or handshake not in effect:
                issues.append(f"{decision_id} must recheck the accepted WKR-VLA alliance")
            for stale in ("ADISCORD_vorkerland_joined_worker_republic",):
                if stale in block or stale in effect:
                    issues.append(f"{decision_id} retains stale VLA gate {stale}")
        else:
            for handshake in (
                "ADISCORD_vorkerland_vad_sol_alliance_accepted",
                "ADISCORD_vorkerland_sol_restoration_verified",
            ):
                if block.count(handshake) < 2 or handshake not in effect:
                    issues.append(f"{decision_id} must recheck SOL outcome {handshake}")
            relation = "OR = { is_in_faction_with = ROOT is_subject_of = ROOT }"
            if block.count(relation) < 2 or relation not in effect:
                issues.append(f"{decision_id} must accept SOL as faction ally or subject")
            if "ADISCORD_vorkerland_independence_recognized_by_vad" in block or (
                "ADISCORD_vorkerland_independence_recognized_by_vad" in effect
            ):
                issues.append(f"{decision_id} retains the stale SOL recognition gate")
        if ally == "VLA":
            relation = "OR = { is_in_faction_with = ROOT is_subject_of = ROOT }"
            if block.count(relation) < 2 or relation not in effect:
                issues.append(f"{decision_id} must require a live VLA alliance or subject relation")
        if not effect:
            issues.append(f"missing support effect {decision_id}")
            continue
        for cost_line in (
            "add_equipment_to_stockpile = { type = infantry_equipment amount = -300 }",
            "add_equipment_to_stockpile = { type = support_equipment amount = -30 }",
        ):
            if cost_line not in effect:
                issues.append(f"{decision_id} must deduct equipment without a producer filter: {cost_line}")
        for token in (
            "amount = 300",
            "amount = 30",
            "ADISCORD_vorkerland_allied_supply_advisers days = 60",
        ):
            if token not in effect:
                issues.append(f"{decision_id} effect lacks bounded delivery token {token}")
        for forbidden in ("add_to_faction", "create_faction", "puppet =", "set_autonomy", "declare_war_on"):
            if forbidden in effect:
                issues.append(f"{decision_id} must not create a diplomatic outcome via {forbidden}")

    for donor, ally in (("vla", "VLA"), ("sol", "SOL")):
        first = named_block(effects, f"ADISCORD_vorkerland_send_{donor}_support_tranche_1")
        second = named_block(decisions, f"ADISCORD_vorkerland_send_{donor}_support_tranche_2")
        cooldown = f"ADISCORD_vorkerland_{donor}_support_cooldown"
        if f"flag = {cooldown} days = 90" not in first:
            issues.append(f"{ally} first support tranche lacks a 90-day cooldown")
        if f"NOT = {{ has_country_flag = {cooldown} }}" not in second:
            issues.append(f"{ally} second support tranche ignores its cooldown")

    idea = named_block(ideas, "ADISCORD_vorkerland_allied_supply_advisers")
    for token in (
        "supply_consumption_factor = -0.06",
        "planning_speed = 0.08",
        "land_reinforce_rate = 0.01",
    ):
        if token not in idea:
            issues.append(f"allied adviser idea lacks {token}")

    english = read(ENGLISH_LOCALISATION)
    russian = read(RUSSIAN_LOCALISATION)
    if not english.startswith("l_english:\n"):
        issues.append("English focus-decision localisation has the wrong header")
    if not russian.startswith("l_russian:\n"):
        issues.append("Russian focus-decision localisation has the wrong header")
    if not (ROOT / RUSSIAN_LOCALISATION).read_bytes().startswith(b"\xef\xbb\xbf"):
        issues.append("Russian focus-decision localisation must use UTF-8 BOM")
    expected = expected_localisation_keys()
    for language, entries in (
        ("English", localisation_entries(english)),
        ("Russian", localisation_entries(russian)),
    ):
        if set(entries) != expected:
            issues.append(
                f"{language} localisation key mismatch: "
                f"missing={sorted(expected - set(entries))}, extra={sorted(set(entries) - expected)}"
            )
        if any(not value.strip() for value in entries.values()):
            issues.append(f"{language} localisation contains an empty value")

    return issues


def main() -> int:
    issues = collect_issues()
    if issues:
        print("A-Discord Vorkerland focus-decision validation failed:")
        for issue in issues:
            print(f"- {issue}")
        return 1
    print(
        "A-Discord Vorkerland focus-decision validation passed: adjacent-wave central "
        "campaigns, shared showdown handoff, finite retreat levies, explicit core "
        "packages, and bounded allied support are coherent."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
