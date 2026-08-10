#!/usr/bin/env python3
"""Validate focus-unlocked Vorkerland operations and bounded allied support."""

from __future__ import annotations

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
IDEA_FILE = Path("common/ideas/ADISCORD_vorkerland_focus_decision_ideas.txt")
ENGLISH_LOCALISATION = Path(
    "localisation/english/ADISCORD_vorkerland_focus_decisions_l_english.yml"
)
RUSSIAN_LOCALISATION = Path(
    "localisation/russian/ADISCORD_vorkerland_focus_decisions_l_russian.yml"
)

CENTRAL_DECISION = "ADISCORD_vorkerland_commit_to_central_showdown"
CENTRAL_EFFECT = "ADISCORD_vorkerland_focus_schedule_final_showdown"

CENTRAL_TARGETS = {
    "EYR": "ADISCORD_vorkerland_consolidate_eyr",
    "EGC": "ADISCORD_vorkerland_consolidate_egc",
    "RIV": "ADISCORD_vorkerland_consolidate_riv",
    "REV": "ADISCORD_vorkerland_consolidate_rev",
    "YOR": "ADISCORD_vorkerland_consolidate_yor",
    "NDN": "ADISCORD_vorkerland_consolidate_ndn",
    "SWB": "ADISCORD_vorkerland_consolidate_swb",
    "VHV": "ADISCORD_vorkerland_consolidate_vhv",
    "OSV": "ADISCORD_vorkerland_consolidate_osv",
}

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
        34,
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
    *CENTRAL_TARGETS.values(),
    CENTRAL_DECISION,
    *LEVY_DECISIONS,
    *CORE_PACKAGES,
    *SUPPORT_DECISIONS,
    "ADISCORD_vorkerland_allied_supply_advisers",
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
    }


def collect_issues() -> list[str]:
    issues: list[str] = []
    paths = (
        CATEGORY_FILE,
        DECISION_FILE,
        EFFECT_FILE,
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
    ideas = read(IDEA_FILE)

    for category in (
        "ADISCORD_vorkerland_focus_operations_category",
        "ADISCORD_vorkerland_allied_support_category",
    ):
        if not named_block(categories, category):
            issues.append(f"missing category {category}")
        if not named_block(decisions, category):
            issues.append(f"missing decision group {category}")

    target_tags = tuple(CENTRAL_TARGETS)
    central_front_tokens = tuple(f"has_war_with = {target}" for target in target_tags)
    for target, decision_id in CENTRAL_TARGETS.items():
        block = named_block(decisions, decision_id)
        effect_id = f"ADISCORD_vorkerland_focus_launch_minor_{target.lower()}"
        effect = named_block(effects, effect_id)
        for tag in ("WKR", "VAD", "TVA"):
            hook = f"ADISCORD_vorkerland_focus_{tag.lower()}_central_war_unlocked"
            if hook not in block:
                issues.append(f"{decision_id} lacks exact claimant unlock {hook}")
        for token in (
            "ADISCORD_vorkerland_phase_central_preparation",
            f"{target} = {{ exists = yes is_subject = no",
            f"any_neighbor_country = {{ tag = {target} }}",
            "ADISCORD_vorkerland_focus_central_minor_launch_pending",
            "ADISCORD_vorkerland_focus_central_minor_recovery_cooldown",
            "days_remove = 1",
            "fire_only_once = no",
            "ADISCORD_vorkerland_focus_cleanup_central_minor_front = yes",
            f"set_country_flag = ADISCORD_vorkerland_focus_central_minor_target_{target.lower()}",
            "ADISCORD_vorkerland_leave_inherited_faction = yes",
            f"{target} = {{ ADISCORD_vorkerland_leave_inherited_faction = yes }}",
            f"remove_effect = {{ {effect_id} = yes }}",
            "ai_will_do = { factor = 900 }",
        ):
            if token not in block:
                issues.append(f"{decision_id} lacks bounded named-front token {token}")
        if not effect:
            issues.append(f"{decision_id} lacks delayed launch effect {effect_id}")
            continue
        for token in (
            "ADISCORD_vorkerland_phase_central_preparation",
            "ADISCORD_vorkerland_focus_central_minor_launch_pending",
            "OR = { tag = WKR tag = VAD tag = TVA }",
            f"{target} = {{ exists = yes is_subject = no",
            f"any_neighbor_country = {{ tag = {target} }}",
            f"declare_war_on = {{ target = {target} type = annex_everything }}",
            "activate_mission = ADISCORD_vorkerland_focus_central_minor_launch_check",
        ):
            if token not in effect:
                issues.append(f"{effect_id} lacks safe delayed-front token {token}")
        if effect.count("declare_war_on = {") != 1:
            issues.append(f"{effect_id} must declare exactly its one named front")
        for front_token in central_front_tokens:
            if front_token not in block or front_token not in effect:
                issues.append(f"{decision_id}/{effect_id} lacks one-front exclusion {front_token}")

    launch_check = named_block(
        decisions, "ADISCORD_vorkerland_focus_central_minor_launch_check"
    )
    retry_check = named_block(
        decisions, "ADISCORD_vorkerland_focus_central_minor_retry_check"
    )
    deadline = named_block(
        decisions, "ADISCORD_vorkerland_focus_central_minor_front_deadline"
    )
    for mission_id, block, callback in (
        (
            "launch check",
            launch_check,
            "ADISCORD_vorkerland_focus_confirm_central_minor_launch = yes",
        ),
        (
            "retry check",
            retry_check,
            "ADISCORD_vorkerland_focus_confirm_central_minor_retry = yes",
        ),
    ):
        for token in (
            "activation = { always = no }",
            "visible = { always = no }",
            "selectable_mission = no",
            "days_mission_timeout = 1",
            callback,
        ):
            if token not in block:
                issues.append(f"central minor {mission_id} lacks cache-check token {token}")
    for token in (
        "ADISCORD_vorkerland_focus_central_minor_deadline_active",
        "selectable_mission = no",
        "fire_only_once = no",
        "days_mission_timeout = 240",
        "ADISCORD_vorkerland_focus_cleanup_central_minor_front = yes",
        "ADISCORD_vorkerland_focus_resolve_central_minor_deadline = yes",
    ):
        if token not in deadline:
            issues.append(f"central minor deadline lacks hard-bound token {token}")

    first_confirmation = named_block(
        effects, "ADISCORD_vorkerland_focus_confirm_central_minor_launch"
    )
    retry_confirmation = named_block(
        effects, "ADISCORD_vorkerland_focus_confirm_central_minor_retry"
    )
    resolver = named_block(
        effects, "ADISCORD_vorkerland_focus_resolve_central_minor_deadline"
    )
    for token in (
        "ADISCORD_vorkerland_focus_central_minor_launch_retry",
        "activate_mission = ADISCORD_vorkerland_focus_central_minor_retry_check",
        "ADISCORD_vorkerland_focus_arm_central_minor_deadline = yes",
    ):
        if token not in first_confirmation:
            issues.append(f"central minor first confirmation lacks one-retry token {token}")
    if "ADISCORD_vorkerland_focus_arm_central_minor_deadline = yes" not in retry_confirmation:
        issues.append("central minor retry confirmation cannot arm the verified deadline")
    for token in (
        "ADISCORD_vorkerland_focus_central_minor_recovery_cooldown",
        "days = 14",
        "ADISCORD_vorkerland_focus_cleanup_central_minor_front = yes",
    ):
        if token not in retry_confirmation:
            issues.append(f"central minor failed retry lacks visible recovery token {token}")
    for target in target_tags:
        declaration = f"declare_war_on = {{ target = {target} type = annex_everything }}"
        if effects.count(declaration) != 2:
            issues.append(f"{target} must have exactly one initial declaration and one retry")
        for token in (
            f"ADISCORD_vorkerland_focus_central_minor_target_{target.lower()}",
            f"annex_country = {{ target = {target} transfer_troops = no }}",
        ):
            if token not in resolver:
                issues.append(f"central minor deadline resolver lacks {target} token {token}")

    central = named_block(decisions, CENTRAL_DECISION)
    central_effect = named_block(effects, CENTRAL_EFFECT)
    for tag in ("WKR", "VAD", "TVA"):
        hook = f"ADISCORD_vorkerland_focus_{tag.lower()}_central_war_unlocked"
        if hook not in central or hook not in central_effect:
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
        terminal = (
            f"OR = {{ NOT = {{ country_exists = {target} }} "
            f"{target} = {{ is_subject = yes }} {target} = {{ has_capitulated = yes }} }}"
        )
        if terminal not in central or terminal not in central_effect:
            issues.append(f"final showdown lacks terminal gate for {target}")
        if f"has_war_with = {target}" not in central or f"has_war_with = {target}" not in central_effect:
            issues.append(f"final showdown ignores live consolidation front {target}")
    for token in (
        "ADISCORD_vorkerland_phase_central_preparation",
        "ADISCORD_vorkerland_focus_central_minor_launch_pending",
        "ADISCORD_vorkerland_focus_central_minor_deadline_active",
    ):
        if token not in central or token not in central_effect:
            issues.append(f"final showdown lacks consolidation-stage guard {token}")
    if "fire_only_once = yes" not in central or "ai_will_do = { factor = 1000 }" not in central:
        issues.append("central decision must be one-shot with high AI priority")
    for forbidden in ("declare_war_on", "start_civil_war", "create_wargoal"):
        if forbidden in central or forbidden in central_effect:
            issues.append(f"central focus decision contains forbidden private-war effect {forbidden}")

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
            "fire_only_once = yes",
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
            "fire_only_once = yes",
            "ai_will_do = { factor = 500",
        ):
            if token not in block:
                issues.append(f"{decision_id} lacks smart allied-support gate {token}")
        if ally == "VLA":
            handshake = "ADISCORD_vorkerland_wkr_vla_alliance_accepted"
            if block.count(handshake) < 2 or handshake not in effect:
                issues.append(f"{decision_id} must recheck the accepted WKR-VLA alliance")
            for stale in (
                "ADISCORD_vorkerland_joined_worker_republic",
                "is_subject_of = ROOT",
            ):
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
        if not effect:
            issues.append(f"missing support effect {decision_id}")
            continue
        for token in (
            "amount = -300",
            "amount = -30",
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
        "A-Discord Vorkerland focus-decision validation passed: named one-front central "
        "consolidation, shared showdown handoff, finite retreat levies, explicit core "
        "packages, and bounded allied support are coherent."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
