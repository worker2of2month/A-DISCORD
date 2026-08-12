#!/usr/bin/env python3
"""Validate the event-driven Rhine Palatinate oath-crisis contract."""

from __future__ import annotations

import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]

EVENTS = Path("events/ADISCORD_rin_oath_crisis_events.txt")
DECISIONS = Path("common/decisions/ADISCORD_rin_oath_crisis_decisions.txt")
CATEGORIES = Path("common/decisions/categories/ADISCORD_rin_oath_crisis_categories.txt")
EFFECTS = Path("common/scripted_effects/ADISCORD_rin_oath_crisis_effects.txt")
TRIGGERS = Path("common/scripted_triggers/ADISCORD_rin_oath_crisis_triggers.txt")
ON_ACTIONS = Path("common/on_actions/02_ADISCORD_rin_oath_crisis_on_actions.txt")
IDEAS = Path("common/ideas/ADISCORD_inner_frontier_ideas.txt")
LOCALISATION_PATHS = tuple(
    Path("localisation/russian") / filename
    for filename in (
        "countries_l_russian.yml",
        "politics_l_russian.yml",
        "events_l_russian.yml",
    )
)
MON_HISTORY = Path("history/countries/MON - Montar Empire.txt")
RIN_HISTORY = Path("history/countries/RIN - Rhine Palatinate.txt")
RIN_COUNTRY = Path("common/countries/RIN.txt")
RIN_OOB = Path("history/units/RIN.txt")


def read(relative: Path) -> str:
    return (ROOT / relative).read_text(encoding="utf-8-sig")


def named_block(text: str, name: str) -> str:
    match = re.search(rf"(?m)^\s*{re.escape(name)}\s*=\s*\{{", text)
    if not match:
        raise ValueError(f"missing block {name}")
    start = text.find("{", match.start())
    depth = 0
    for index in range(start, len(text)):
        if text[index] == "{":
            depth += 1
        elif text[index] == "}":
            depth -= 1
            if depth == 0:
                return text[match.start() : index + 1]
    raise ValueError(f"unterminated block {name}")


def event_block(text: str, event_id: str) -> str:
    for match in re.finditer(r"(?m)^country_event\s*=\s*\{", text):
        start = text.find("{", match.start())
        depth = 0
        for index in range(start, len(text)):
            if text[index] == "{":
                depth += 1
            elif text[index] == "}":
                depth -= 1
                if depth == 0:
                    block = text[match.start() : index + 1]
                    if re.search(rf"(?m)^\s*id\s*=\s*{re.escape(event_id)}\s*$", block):
                        return block
                    break
    raise ValueError(f"missing country event {event_id}")


def state_history(state_id: int) -> str:
    matches = sorted((ROOT / "history/states").glob(f"{state_id}-*.txt"))
    if len(matches) != 1:
        return ""
    return matches[0].read_text(encoding="utf-8-sig")


def collect_issues() -> list[str]:
    issues: list[str] = []
    texts = {
        path: read(path)
        for path in (
            EVENTS, DECISIONS, CATEGORIES, EFFECTS, TRIGGERS, ON_ACTIONS,
            IDEAS, MON_HISTORY, RIN_HISTORY, RIN_COUNTRY, RIN_OOB,
        )
    }

    events = texts[EVENTS]
    event_ids = re.findall(r"(?m)^\s*id\s*=\s*(ADISCORD_rin_crisis\.\d+)\b", events)
    if event_ids != [
        "ADISCORD_rin_crisis.1", "ADISCORD_rin_crisis.2",
        "ADISCORD_rin_crisis.3", "ADISCORD_rin_crisis.4",
    ]:
        issues.append(f"RIN event namespace must contain exactly .1-.4, found {event_ids}")
    if events.count("add_namespace = ADISCORD_rin_crisis") != 1:
        issues.append("RIN event namespace declaration is missing or duplicated")

    try:
        prompt = event_block(events, "ADISCORD_rin_crisis.1")
        split_event = event_block(events, "ADISCORD_rin_crisis.2")
        partition_verify = event_block(events, "ADISCORD_rin_crisis.3")
        partition_terminal = event_block(events, "ADISCORD_rin_crisis.4")
    except ValueError as exc:
        issues.append(str(exc))
        prompt = split_event = partition_verify = partition_terminal = ""
    for token in (
        "fire_only_once = yes",
        "picture = GFX_report_event_generic_diplomacy",
        "has_global_flag = ADISCORD_vorkerland_collapse_started",
        "has_global_flag = ADISCORD_vorkerland_collapse_wars_started",
        "ADISCORD_rin_begin_oath_crisis = yes",
        "set_global_flag = ADISCORD_rin_oath_crisis_opened",
        "ai_chance = { base = 100 }",
        "ai_chance = { base = 0 }",
    ):
        if token not in prompt:
            issues.append(f"visible oath event lacks {token}")
    for token in (
        "has_global_flag = ADISCORD_rin_oath_crisis_split_pending",
        "ADISCORD_rin_start_oath_civil_war = yes",
    ):
        if token not in split_event:
            issues.append(f"deferred split event lacks {token}")
    for token in (
        "ADISCORD_rin_partition_verification_pending",
        "ADISCORD_rin_partition_armistice_is_valid = yes",
        "ADISCORD_rin_apply_partition_armistice = yes",
        "ADISCORD_rin_crisis.4 days = 1",
    ):
        if token not in partition_verify:
            issues.append(f"first partition verifier lacks {token}")
    if partition_verify.count("ADISCORD_rin_apply_partition_armistice = yes") != 1:
        issues.append("first partition verifier must perform exactly one repair")
    for token in (
        "ADISCORD_rin_partition_verification_pending",
        "ADISCORD_rin_partition_verification_retry",
        "ADISCORD_rin_oath_crisis_terminal_failure",
    ):
        if token not in partition_terminal:
            issues.append(f"terminal partition verifier lacks {token}")
    if (
        "ADISCORD_rin_apply_partition_armistice = yes" in partition_terminal
        or partition_terminal.count("country_event =") != 1
    ):
        issues.append("terminal partition verifier schedules or performs an unbounded second repair")

    on_actions = texts[ON_ACTIONS]
    try:
        startup = named_block(on_actions, "on_startup")
        war = named_block(on_actions, "on_war")
        capitulation = named_block(on_actions, "on_capitulation")
        peace = named_block(on_actions, "on_peace")
    except ValueError as exc:
        issues.append(str(exc))
        startup = war = capitulation = peace = ""
    for block_name, block, delay in (("startup", startup, 1), ("on_war", war, 7)):
        for token in (
            "set_global_flag = ADISCORD_rin_oath_crisis_scheduled",
            "RIN = {",
            "MON = {",
            "ADISCORD_release_non_participating_minor_optimization = yes",
            f"ADISCORD_rin_crisis.1 days = {delay}",
        ):
            if token not in block:
                issues.append(f"{block_name} producer lacks {token}")
        if block.find("set_global_flag = ADISCORD_rin_oath_crisis_scheduled") > block.find(
            f"ADISCORD_rin_crisis.1 days = {delay}"
        ):
            issues.append(f"{block_name} schedules the event before raising its global guard")
        event_position = block.find(f"ADISCORD_rin_crisis.1 days = {delay}")
        release_positions = [match.start() for match in re.finditer(
            "ADISCORD_release_non_participating_minor_optimization = yes", block
        )]
        if len(release_positions) != 2 or any(position > event_position for position in release_positions):
            issues.append(f"{block_name} must release dormant MON and RIN before scheduling the event")
    if "ADISCORD_rin_is_vorkerland_war_actor = yes" not in war:
        issues.append("on_war producer is not restricted to a Vorkerland claimant")
    for forbidden in ("on_daily", "on_weekly", "on_monthly", "on_yearly", "every_country"):
        if re.search(rf"(?m)^\s*{forbidden}\s*=", on_actions) or forbidden == "every_country" and forbidden in on_actions:
            issues.append(f"RIN crisis uses forbidden recurring/global poll {forbidden}")
    for token in (
        "set_global_flag = skip_default_capitulation",
        "white_peace = ROOT",
        "annex_country = { target = ROOT transfer_troops = yes }",
        "ADISCORD_rin_complete_southern_victory = yes",
        "ADISCORD_rin_complete_northern_victory = yes",
    ):
        if token not in capitulation:
            issues.append(f"capitulation router lacks {token}")
    if "ADISCORD_rin_complete_partition_armistice = yes" not in peace:
        issues.append("on_peace fallback does not settle an externally ended RIN war")
    if "event_target:ADISCORD_rin_southern_charter" not in peace:
        issues.append("on_peace fallback resolves the ambiguous original RIN tag instead of cached southern ROOT")

    triggers = texts[TRIGGERS]
    try:
        actor = named_block(triggers, "ADISCORD_rin_is_vorkerland_war_actor")
        schedule = named_block(triggers, "ADISCORD_rin_oath_crisis_can_schedule")
        legacy = named_block(triggers, "ADISCORD_rin_oath_crisis_legacy_needs_schedule")
        partition_valid = named_block(triggers, "ADISCORD_rin_partition_armistice_is_valid")
    except ValueError as exc:
        issues.append(str(exc))
        actor = schedule = legacy = partition_valid = ""
    actor_tags = set(re.findall(r"\btag\s*=\s*([A-Z0-9]{3})\b", actor))
    if actor_tags != {"WKR", "VAD", "TVA"}:
        issues.append(f"war producer actor set is {sorted(actor_tags)}, expected WKR/VAD/TVA")
    for block_name, block in (("fresh", schedule), ("legacy", legacy)):
        for token in (
            "ADISCORD_rin_oath_crisis_scheduled",
            "ADISCORD_rin_oath_crisis_opened",
            "ADISCORD_rin_oath_crisis_active",
            "ADISCORD_rin_oath_crisis_resolved",
            "MON = { exists = yes }",
        ):
            if token not in block:
                issues.append(f"{block_name} schedule guard lacks {token}")
    if "RIN = { exists = yes }" not in schedule:
        issues.append("fresh schedule guard does not confirm that RIN exists")
    if "tag = RIN" not in legacy or "RIN = {" in legacy:
        issues.append("startup legacy trigger is not a country-scoped RIN trigger")
    try:
        startup_rin = named_block(startup, "RIN")
    except ValueError as exc:
        issues.append(str(exc))
        startup_rin = ""
    if "ADISCORD_rin_oath_crisis_legacy_needs_schedule = yes" not in startup_rin:
        issues.append("startup invokes the legacy country trigger outside explicit RIN scope")
    if "ADISCORD_vorkerland_collapse_wars_started" not in legacy:
        issues.append("startup migration can manufacture the crisis before the collapse wars")
    for state_id in (134, 146, 147, 148, 149, 150):
        if f"owns_state = {state_id}" not in partition_valid:
            issues.append(f"partition runtime assertion does not check ownership of state {state_id}")
        if f"controls_state = {state_id}" not in partition_valid:
            issues.append(f"partition runtime assertion does not check control of state {state_id}")
    for token in (
        "has_country_flag = ADISCORD_rin_charter_compact_survived",
        "has_country_flag = ADISCORD_rin_crown_palatin_survived",
        "has_idea = RIN_charter_compact",
        "has_idea = RIN_crown_palatin",
        "is_subject_of = MON",
    ):
        if token not in partition_valid:
            issues.append(f"partition runtime assertion lacks {token}")

    effects = texts[EFFECTS]
    try:
        begin = named_block(effects, "ADISCORD_rin_begin_oath_crisis")
        split = named_block(effects, "ADISCORD_rin_start_oath_civil_war")
        apply_partition = named_block(effects, "ADISCORD_rin_apply_partition_armistice")
        complete_partition = named_block(effects, "ADISCORD_rin_complete_partition_armistice")
        armistice = named_block(effects, "ADISCORD_rin_force_partition_armistice")
    except ValueError as exc:
        issues.append(str(exc))
        begin = split = apply_partition = complete_partition = armistice = ""
    if begin.find("autonomy_state = autonomy_free") > begin.find("ADISCORD_rin_crisis.2 days = 1"):
        issues.append("RIN is not freed before the one-day diplomatic cache barrier")
    for token in (
        "ideology = chauvinism",
        "size = 0",
        "army_ratio = 0.40",
        "navy_ratio = 0",
        "air_ratio = 0",
        "capital = 147",
        "states = { 134 147 }",
        "save_global_event_target_as = ADISCORD_rin_northern_court",
        "save_global_event_target_as = ADISCORD_rin_southern_charter",
        "set_cosmetic_tag = RIN_northern_court",
        "activate_mission = ADISCORD_rin_palatin_breakup_mission",
    ):
        if token not in split:
            issues.append(f"deterministic RIN split lacks {token}")
    if "\n\tRIN = {" in split:
        issues.append("post-civil-war split resolves the ambiguous original RIN tag instead of southern ROOT")
    for forbidden in ("declare_war_on", "add_to_war", "create_faction", "add_to_faction"):
        if forbidden in effects or forbidden in events or forbidden in on_actions:
            issues.append(f"RIN crisis can merge with another war through {forbidden}")
    if "white_peace = ROOT" not in armistice or "has_war_with = ROOT" not in armistice:
        issues.append("180-day armistice does not close the local civil war")
    if "save_global_event_target_as = ADISCORD_rin_southern_charter" not in armistice:
        issues.append("mission timeout does not preserve its southern ROOT")

    try:
        north_partition = named_block(apply_partition, "event_target:ADISCORD_rin_northern_court")
    except ValueError as exc:
        issues.append(str(exc))
        north_partition = ""
    all_transfers = [int(value) for value in re.findall(r"\btransfer_state\s*=\s*(\d+)", apply_partition)]
    north_transfers = [int(value) for value in re.findall(r"\btransfer_state\s*=\s*(\d+)", north_partition)]
    if all_transfers != [146, 148, 149, 150, 134, 147]:
        issues.append(f"partition transfer order/set is {all_transfers}, expected south 146/148/149/150 then north 134/147")
    if north_transfers != [134, 147]:
        issues.append(f"northern partition transfer set is {north_transfers}, expected 134/147")
    if "\n\tRIN = {" in apply_partition:
        issues.append("partition repair resolves the ambiguous original RIN tag instead of southern ROOT")
    for state_id in (146, 148, 149, 150):
        token = f"{state_id} = {{ set_state_controller_to = event_target:ADISCORD_rin_southern_charter }}"
        if token not in apply_partition:
            issues.append(f"southern partition does not restore controller of state {state_id}")
    for state_id in (134, 147):
        token = f"{state_id} = {{ set_state_controller_to = event_target:ADISCORD_rin_northern_court }}"
        if token not in apply_partition:
            issues.append(f"northern partition does not restore controller of state {state_id}")
    for token in (
        "remove_mission = ADISCORD_rin_palatin_breakup_mission",
        "remove_ideas = RIN_two_oaths",
        "remove_ideas = RIN_southern_charter_mobilization",
        "remove_ideas = RIN_northern_crown_columns",
        "add_ideas = RIN_charter_compact",
        "set_country_flag = ADISCORD_rin_charter_compact_survived",
        "clr_country_flag = ADISCORD_rin_crown_palatin_survived",
        "puppet = event_target:ADISCORD_rin_northern_court",
        "autonomy_state = autonomy_puppet",
    ):
        if token not in apply_partition:
            issues.append(f"partition repair lacks {token}")
    for token in (
        "add_ideas = RIN_crown_palatin",
        "set_country_flag = ADISCORD_rin_crown_palatin_survived",
        "clr_country_flag = ADISCORD_rin_charter_compact_survived",
    ):
        if token not in north_partition:
            issues.append(f"northern partition outcome lacks {token}")
    for token in (
        "ADISCORD_rin_apply_partition_armistice = yes",
        "ADISCORD_rin_crisis.3 days = 1",
        "set_country_flag = ADISCORD_rin_partition_verification_pending",
    ):
        if token not in complete_partition:
            issues.append(f"partition completion lacks {token}")

    decisions = texts[DECISIONS]
    categories = texts[CATEGORIES]
    try:
        mission = named_block(decisions, "ADISCORD_rin_palatin_breakup_mission")
        category = named_block(categories, "ADISCORD_rin_oath_crisis_category")
    except ValueError as exc:
        issues.append(str(exc))
        mission = category = ""
    for token in (
        "activation = { always = no }",
        "available = { always = no }",
        "selectable_mission = no",
        "days_mission_timeout = 180",
        "ADISCORD_rin_force_partition_armistice = yes",
    ):
        if token not in mission:
            issues.append(f"RIN breakup mission lacks {token}")
    if "ADISCORD_rin_southern_charter_side" not in category:
        issues.append("RIN mission category is not limited to the playable southern side")

    mon_history = texts[MON_HISTORY]
    if not re.search(
        r"(?s)set_autonomy\s*=\s*\{[^{}]*target\s*=\s*RIN[^{}]*autonomous_state\s*=\s*autonomy_puppet",
        mon_history,
    ):
        issues.append("MON history does not establish RIN as its starting puppet")
    rin_history = texts[RIN_HISTORY]
    rin_country = texts[RIN_COUNTRY]
    for field, expected in (
        ("graphical_culture", "western_european_gfx"),
        ("graphical_culture_2d", "western_european_2d"),
        ("color", "rgb { 102 48 61 }"),
    ):
        if re.search(rf"(?m)^\s*{re.escape(field)}\s*=", rin_history):
            issues.append(f"RIN history contains common-country field {field}")
        if not re.search(
            rf"(?m)^\s*{re.escape(field)}\s*=\s*{re.escape(expected)}\s*$",
            rin_country,
        ):
            issues.append(f"RIN common country definition lacks authoritative {field} = {expected}")
    rin_oob = texts[RIN_OOB]
    if rin_oob.count("division = {") != 5:
        issues.append("RIN must retain its five-division generated starting OOB")
    try:
        rin_template = named_block(rin_oob, "division_template")
        rin_regiments = named_block(rin_template, "regiments")
    except ValueError as exc:
        issues.append(str(exc))
        rin_regiments = ""
    if "ADISCORD_line_artillery = {" not in rin_regiments:
        issues.append("RIN line template lacks its runtime-safe ADISCORD_line_artillery battalion")
    if re.search(r"(?m)^\s*artillery\s*=\s*\{", rin_regiments):
        issues.append("RIN places the support-only artillery subunit in a regiment column")
    for state_id in (134, 146, 147, 148, 149, 150):
        state = state_history(state_id)
        if "owner = RIN" not in state or "add_core_of = RIN" not in state:
            issues.append(f"state {state_id} no longer starts as a RIN core and possession")
    for state_id in (134, 147):
        if "add_claim_by = MON" not in state_history(state_id):
            issues.append(f"northern split state {state_id} lacks its established MON claim")

    ideas = texts[IDEAS]
    for idea in (
        "RIN_southern_charter_mobilization",
        "RIN_northern_crown_columns",
        "RIN_charter_compact",
        "RIN_crown_palatin",
    ):
        if f"{idea} = {{" not in ideas:
            issues.append(f"missing RIN crisis idea {idea}")
    localisation = "\n".join(read(path) for path in LOCALISATION_PATHS)
    for key in (
        "RIN_northern_court",
        "ADISCORD_rin_oath_crisis_category",
        "ADISCORD_rin_palatin_breakup_mission",
        "ADISCORD_rin_crisis.1.t",
        "ADISCORD_rin_crisis.1.d",
        "ADISCORD_rin_crisis.1.a",
        "ADISCORD_rin_crisis.1.b",
    ):
        if not re.search(rf"(?m)^\s*{re.escape(key)}:", localisation):
            issues.append(f"missing Russian localisation key {key}")

    if list((ROOT / "gfx/flags").glob("RIN_northern_court.*")):
        issues.append("RIN crisis added a bitmap cosmetic flag instead of reusing RIN graphics")

    return issues


def main() -> int:
    issues = collect_issues()
    if issues:
        print("RIN oath-crisis validation failed:")
        for issue in issues:
            print(f"- {issue}")
        return 1
    print(
        "RIN oath-crisis validation passed: event-driven producer, deterministic "
        "134/147 split, 180-day mission, bounded outcomes, and no war merging."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
