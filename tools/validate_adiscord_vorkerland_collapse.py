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
        DIRTY_INITIAL_OWNER_OVERRIDES,
        EXZ_REMAINDER_GROUPS,
        STATE_PARTITIONS,
        TAGS,
    )
except ModuleNotFoundError:
    from vorkerland_collapse_manifest import (
        CAPITALS,
        CONTAMINATED_STATES,
        DIRTY_GROUPS,
        DIRTY_INITIAL_OWNER_OVERRIDES,
        EXZ_REMAINDER_GROUPS,
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
    text = re.sub(r'(?m)#.*$', '', text)
    match = re.search(r"\bprovinces\s*=\s*\{([^}]*)\}", text, re.DOTALL)
    return {int(value) for value in re.findall(r"\d+", match.group(1))} if match else set()


def require_file(issues: list[str], path: Path, label: str) -> str:
    text = read(path)
    if text is None:
        issues.append(f"missing {label}: {path.as_posix()}")
        return ""
    return text


def validate_manifest(issues: list[str]) -> None:
    dirty_sequence = tuple(state for group in DIRTY_GROUPS.values() for state in group)
    dirty_states = set().union(*(set(group) for group in DIRTY_GROUPS.values()))
    remainder_sequence = tuple(state for group in EXZ_REMAINDER_GROUPS.values() for state in group)
    remainder_states = set(remainder_sequence)
    if len(TAGS) != 16 or len(TAGS) != len(set(TAGS)):
        issues.append("manifest must define 16 unique fixed tags")
    if len(CONTAMINATED_STATES) != 59:
        issues.append("manifest must define 59 contaminated states")
    if (
        dirty_states != CONTAMINATED_STATES - {23, 24, 57, 59, 60}
        or len(dirty_sequence) != len(dirty_states)
    ):
        issues.append("dirty groups must cover every transferable contaminated state exactly once")
    if len(remainder_sequence) != len(remainder_states) or dirty_states & remainder_states:
        issues.append("EXZ remainder states must be unique and separate from playable dirty states")
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

    if tag_text and re.search(r'(?m)^\s*EXZ\s*=\s*"countries/EXZ\.txt"', tag_text) is None:
        issues.append("the exclusion-zone placeholder tag EXZ is absent from the tag registry")
    exz_country = require_file(issues, root / "common" / "countries" / "EXZ.txt", "country definition for EXZ")
    if exz_country:
        for token in ("color = rgb { 82 96 91 }", "color_ui = rgb { 82 96 91 }"):
            if token not in exz_country:
                issues.append(f"EXZ country definition is missing {token}")
    exz_histories = list((root / "history" / "countries").glob("EXZ - *.txt"))
    if not exz_histories:
        issues.append("missing country history for the exclusion-zone placeholder EXZ")
    placeholder_characters = require_file(
        issues,
        root / "common" / "characters" / "ADISCORD_dirty_zone_characters.txt",
        "exclusion-zone character database",
    )
    if placeholder_characters and "EXZ_No_Authority" not in placeholder_characters:
        issues.append("exclusion-zone character database has no No Authority leader")
    if placeholder_characters and "GFX_portrait_EXZ_No_Command" not in placeholder_characters:
        issues.append("exclusion-zone character does not use the No Command portrait")
    if not (root / "gfx" / "leaders" / "EXZ" / "Portrait_EXZ_No_Command.png").exists():
        issues.append("missing EXZ No Command portrait asset")
    if exz_histories:
        history = read(exz_histories[0]) or ""
        if "add_ideas = closed_economy" not in history:
            issues.append("EXZ must use closed_economy to remain outside the market")
    for size in ("", "medium", "small"):
        flag = root / "gfx" / "flags" / size / "EXZ.tga" if size else root / "gfx" / "flags" / "EXZ.tga"
        if not flag.exists():
            issues.append(f"missing {size or 'large'} black flag for EXZ")


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
    if effects:
        if re.search(r"\btransfer_state\s*=", effects):
            issues.append("dirty-zone successor setup must not use transfer_state")
        for tag, states in DIRTY_GROUPS.items():
            for state_id in states:
                path = state_file(root, state_id)
                history = read(path) if path else None
                initial_owner = DIRTY_INITIAL_OWNER_OVERRIDES.get(state_id, "EXZ")
                if history is None or re.search(
                    rf"(?m)^\s*owner\s*=\s*{initial_owner}\s*$", history
                ) is None:
                    issues.append(
                        f"dirty state {state_id} is not owned by {initial_owner} at game start"
                    )
                if history is None or re.search(
                    rf"(?m)^\s*add_core_of\s*=\s*{initial_owner}\s*$", history
                ) is None:
                    issues.append(
                        f"dirty state {state_id} is not cored by {initial_owner} at game start"
                    )
                if re.search(
                    rf"{state_id}\s*=\s*\{{[^}}]*set_state_owner_to\s*=\s*{tag}\b[^}}]*set_state_controller_to\s*=\s*{tag}\b",
                    effects,
                ) is None:
                    issues.append(
                        f"dirty state {state_id} must receive {tag} as owner and then controller"
                    )
        for tag, states in EXZ_REMAINDER_GROUPS.items():
            for state_id in states:
                path = state_file(root, state_id)
                history = read(path) if path else None
                if history is None or re.search(r"(?m)^\s*owner\s*=\s*EXZ\s*$", history) is None:
                    issues.append(f"EXZ remainder state {state_id} is not owned by EXZ at game start")
                if re.search(
                    rf"{state_id}\s*=\s*\{{[^}}]*set_state_owner_to\s*=\s*{tag}\b[^}}]*set_state_controller_to\s*=\s*{tag}\b",
                    effects,
                ) is None:
                    issues.append(
                        f"EXZ remainder state {state_id} must receive {tag} as owner and then controller"
                    )

        routed_exz_states = {
            state_id
            for state_id in set().union(*(set(states) for states in DIRTY_GROUPS.values()))
            if DIRTY_INITIAL_OWNER_OVERRIDES.get(state_id, "EXZ") == "EXZ"
        } | set().union(*(set(states) for states in EXZ_REMAINDER_GROUPS.values()))
        actual_exz_states = set()
        for path in (root / "history" / "states").glob("*.txt"):
            history = read(path) or ""
            if re.search(r"(?m)^\s*owner\s*=\s*EXZ\s*$", history):
                match = re.search(r"\bid\s*=\s*(\d+)", history)
                if match:
                    actual_exz_states.add(int(match.group(1)))
        if actual_exz_states != routed_exz_states:
            missing = sorted(actual_exz_states - routed_exz_states)
            stale = sorted(routed_exz_states - actual_exz_states)
            issues.append(
                f"every EXZ-owned state must leave EXZ during the cascade; unrouted={missing}, not_owned_by_exz={stale}"
            )
        excluded = CONTAMINATED_STATES - set().union(*(set(states) for states in DIRTY_GROUPS.values()))
        for state_id in excluded:
            path = state_file(root, state_id)
            history = read(path) if path else None
            if history and re.search(r"(?m)^\s*owner\s*=\s*EXZ\s*$", history):
                issues.append(f"excluded contaminated state {state_id} must not be assigned to EXZ")

    gui_files = (
        (root / "interface" / "ADISCORD_dirty_zone.gui", "dirty-zone GUI"),
        (root / "interface" / "ADISCORD_dirty_zone.gfx", "dirty-zone GFX"),
        (root / "common" / "scripted_guis" / "ADISCORD_dirty_zone_scripted_gui.txt", "dirty-zone scripted GUI"),
        (root / "common" / "scripted_triggers" / "ADISCORD_dirty_zone_triggers.txt", "dirty-zone GUI trigger"),
    )
    gui_text = "\n".join(require_file(issues, path, label) for path, label in gui_files)
    for token in (
        "ADISCORD_Dirty_Zone_Diplomacy_Container",
        "selected_country_context",
        "parent_window_token = selected_country_view",
        "original_tag = EXZ",
        "GFX_ADISCORD_Dirty_Zone_Wallpaper",
    ):
        if token not in gui_text:
            issues.append(f"dirty-zone diplomacy overlay is missing {token}")
    gui = read(root / "interface" / "ADISCORD_dirty_zone.gui") or ""
    if 'name = "ADISCORD_Dirty_Zone_Relations_Block"' in gui:
        issues.append("dirty-zone GUI still displays the baked TNO Anarchy relations block")
    if "position = { x = 265 y = 365 }" not in gui:
        issues.append("dirty-zone terminal panel does not use the adjusted position")

    diplo = require_file(
        issues,
        root / "common" / "scripted_triggers" / "00_diplo_action_valid_triggers.txt",
        "diplomatic-action validity hooks",
    )
    for action in (
        "generate_wargoal", "guarantee", "improverelation", "join_faction",
        "lend_lease", "milacc", "nonaggressionpact", "send_attache",
        "international_market_access_rights",
    ):
        if re.search(
            rf"is_diplomatic_action_valid_{action}\s*=\s*\{{[^}}]*ADISCORD_diplomacy_not_dirty_zone_pair\s*=\s*yes",
            diplo,
            re.DOTALL,
        ) is None:
            issues.append(f"EXZ diplomatic quarantine does not cover {action}")
    for asset in (
        "dirty_zone_wallpaper.dds",
        "dirty_zone_animation.dds",
        "relations_block.dds",
        "scrollbar_block.dds",
    ):
        if not (root / "gfx" / "interface" / "ADISCORD_dirty_zone" / asset).exists():
            issues.append(f"dirty-zone diplomacy overlay is missing {asset}")
    for path in root.rglob("*.txt"):
        text = read(path) or ""
        if "remove_dynamic_modifier" in text and "ADISCORD_vorkerland_dirty_state" in text:
            issues.append(f"dirty-state modifier is removed in {path.relative_to(root).as_posix()}")


def validate_events(root: Path, issues: list[str]) -> None:
    events = require_file(issues, root / "events" / "ADISCORD_vorkerland_collapse_events.txt", "collapse event file")
    effects = require_file(issues, root / "common" / "scripted_effects" / "ADISCORD_vorkerland_collapse_effects.txt", "collapse effects")
    dirty_effects = require_file(issues, root / "common" / "scripted_effects" / "ADISCORD_vorkerland_collapse_dirty_effects.txt", "dirty-zone collapse effects")
    ideas = require_file(issues, root / "common" / "ideas" / "ADISCORD_vorkerland_collapse_ideas.txt", "collapse national spirits")
    triggers = require_file(issues, root / "common" / "scripted_triggers" / "ADISCORD_vorkerland_collapse_triggers.txt", "collapse triggers")
    on_actions = require_file(issues, root / "common" / "on_actions" / "01_ADISCORD_vorkerland_collapse_on_actions.txt", "collapse on-actions")
    for text, label in ((events, "events"), (triggers, "triggers"), (on_actions, "on-actions")):
        if text and FEATURE not in text:
            issues.append(f"collapse {label} do not contain the feature namespace")
    if effects:
        for helper in (
            "ADISCORD_vorkerland_teardown_confederation",
            "ADISCORD_vorkerland_apply_initial_map",
        ):
            if helper not in effects:
                issues.append(f"collapse effects are missing {helper}")
        for tag in ("NAM", "DAN", "VAD", "ZAO", "PWR", "VLA", "ROM", "SOL", "TRU"):
            if re.search(
                rf"WRK\s*=\s*\{{\s*set_autonomy\s*=\s*\{{\s*target\s*=\s*{tag}\s+"
                rf"autonomy_state\s*=\s*autonomy_free\s*\}}\s*\}}",
                effects,
            ) is None:
                issues.append(f"collapse teardown must release {tag} with autonomy_free")
        if re.search(r"\bend_puppet\s*=", effects):
            issues.append("collapse teardown must not rely on delayed end_puppet updates")
        if "ADISCORD_vorkerland_prepare_conflict_country" not in effects:
            issues.append("collapse effects do not prepare combatant national spirits")
    if dirty_effects and ("give_guarantee" in dirty_effects or "has_guaranteed" in dirty_effects):
        issues.append("dirty-zone activation must not mutate diplomatic relations in the spawn tick")
    if dirty_effects and "ADISCORD_vorkerland_prepare_conflict_country" in dirty_effects:
        issues.append("dirty-zone successors must not receive the Vorkerland civil-war spirit")
    if events:
        opening = re.search(
            r"(?m)^country_event\s*=\s*\{\s*\n\tid\s*=\s*ADISCORD_vorkerland_collapse\.10\s*$"
            r"(?P<body>.*?)^\}",
            events,
            re.DOTALL,
        )
        opening_text = opening.group("body") if opening else ""
        for event_id, days in ((11, 1), (17, 3), (12, 5), (18, 7), (13, 9), (19, 11)):
            if re.search(
                rf"country_event\s*=\s*\{{\s*id\s*=\s*ADISCORD_vorkerland_collapse\.{event_id}\s+days\s*=\s*{days}\s*\}}",
                opening_text,
            ) is None:
                issues.append(f"dirty-zone opening must schedule event {event_id} for day {days}")
        for event_id in (11, 12, 13, 17, 18, 19):
            definition = re.search(
                rf"country_event\s*=\s*\{{\s*id\s*=\s*ADISCORD_vorkerland_collapse\.{event_id}\b(?P<body>.*?)\n\}}",
                events,
                re.DOTALL,
            )
            if definition and "fire_only_once = yes" in definition.group("body"):
                issues.append(f"recoverable dirty spawn event {event_id} must not be fire_only_once")
    if dirty_effects:
        for token in (
            "ADISCORD_vorkerland_start_khan_border_war",
            "declare_war_on = { target = SLA type = annex_everything }",
            "ADISCORD_vorkerland_check_khan_border_war",
            "controls_state = 49",
            "controls_state = 176",
            "white_peace = SLA",
        ):
            if token not in dirty_effects:
                issues.append(f"Khan border war is missing {token}")
    if ideas:
        for token in (
            "ADISCORD_vorkerland_to_the_last",
            "surrender_limit = 1.0",
            "army_attack_factor = 0.10",
            "breakthrough_factor = 0.25",
            "army_morale_factor = 0.10",
            "supply_consumption_factor = -0.10",
        ):
            if token not in ideas:
                issues.append(f"the To the Last spirit is missing {token}")

    dirty_tags = set(DIRTY_GROUPS)
    for tag in TAGS:
        oob = require_file(
            issues,
            root / "history" / "units" / f"{tag}_vorkerland_collapse.txt",
            f"{tag} collapse OOB",
        )
        if oob:
            template = oob.split("units =", 1)[0]
            if template.count("ADISCORD_militia =") != 3:
                issues.append(f"{tag} collapse template must contain three militia battalions")
            factors = re.findall(r"start_equipment_factor\s*=\s*([0-9.]+)", oob)
            if not factors or any(factor != "0.70" for factor in factors):
                issues.append(f"{tag} collapse divisions must start at 70% equipment")
        setup_text = dirty_effects if tag in dirty_tags else effects
        reserve = 80 if tag in dirty_tags else 160
        if setup_text and re.search(
            rf'load_oob\s*=\s*"{tag}_vorkerland_collapse"\s*'
            rf'add_equipment_to_stockpile\s*=\s*\{{\s*type\s*=\s*infantry_equipment_0\s+'
            rf'amount\s*=\s*{reserve}\s+producer\s*=\s*{tag}\s*\}}',
            setup_text,
        ) is None:
            issues.append(f"{tag} collapse setup must grant a {reserve}-rifle reserve after its OOB")


def validate_ai(root: Path, issues: list[str]) -> None:
    ai = require_file(issues, root / "common" / "ai_strategy" / "ADISCORD_vorkerland_collapse_ai.txt", "collapse AI strategy file")
    defines = require_file(issues, root / "common" / "defines" / "ADISCORD_defines_changes.lua", "global AI defines")
    effects = require_file(issues, root / "common" / "scripted_effects" / "ADISCORD_vorkerland_collapse_effects.txt", "collapse phase effects")
    on_actions = require_file(issues, root / "common" / "on_actions" / "01_ADISCORD_vorkerland_collapse_on_actions.txt", "collapse phase on-actions")
    if ai:
        if "abort_when_not_enabled = yes" not in ai:
            issues.append("collapse AI strategies must abort when disabled")
        for tag in ("WRK", "VAD", "ZAO", "PWR", "VLA", "ROM", "SOL", "TRU", *TAGS):
            if tag not in ai:
                issues.append(f"collapse AI has no coverage for {tag}")
        for target in ("TVA", "VAD", "WRK", "EYR", "EGC", "WPA", "WPS", "ZAO", "PSD", "PWR", "EBA", "VLA", "DVA", "ROM", "SRA", "SOL", "ZTA", "TRU"):
            if f"has_war_with = {target}" not in ai:
                issues.append(f"collapse AI lacks a guarded front against {target}")
        for token in ("ADISCORD_vorkerland_khan_border_offensive", "has_war_with = SLA", "type = conquer id = SLA"):
            if token not in ai:
                issues.append(f"Khan border-war AI is missing {token}")
        for token in (
            "ADISCORD_vorkerland_force_front_commitment",
            "type = front_unit_request",
            "value = 75",
        ):
            if token not in ai:
                issues.append(f"collapse front coverage is missing {token}")
        for forbidden in ("ratio = 0.01", "manual_attack = yes"):
            if forbidden in ai:
                issues.append(f"collapse AI must not force depleted attacks with {forbidden}")
        safe_offensives = re.findall(
            r"type\s*=\s*front_control\s+tag\s*=\s*\w+\s+ratio\s*=\s*[0-9.]+\s+"
            r"priority\s*=\s*\d+\s+ordertype\s*=\s*front\s+execution_type\s*=\s*rush\s+"
            r"execute_order\s*=\s*yes\s+manual_attack\s*=\s*no",
            ai,
        )
        if len(safe_offensives) != 28:
            issues.append(
                f"collapse target fronts must expose 28 safe rush offensives, found {len(safe_offensives)}"
            )
    if defines:
        for token in (
            "NDefines.NAI.PLAN_ATTACK_MIN_ORG_FACTOR_HIGH = 0.50",
            "NDefines.NAI.PLAN_ATTACK_MIN_STRENGTH_FACTOR_HIGH = 0.50",
            "NDefines.NAI.FRONT_EVAL_UNIT_SUPPLY_AND_ORG_LACK_IMPACT = 1.0",
            "NDefines.NAITheatre.AI_THEATRE_SUPPLY_CRISIS_LIMIT = 0.1",
            "NDefines.NAI.PLAN_ACTIVATION_SUPERIORITY_AGGRO = 1.0",
            "NDefines.NMilitary.PLAN_EXECUTE_BALANCED_LIMIT = 0.0",
            "NDefines.NMilitary.PLAN_EXECUTE_RUSH = -10",
        ):
            if token not in defines:
                issues.append(f"global sustainable-offensive AI handling is missing {token}")
    if effects and "ADISCORD_vorkerland_update_ai_phase" not in effects:
        issues.append("collapse AI phase updater is missing")
    if on_actions:
        if "ADISCORD_vorkerland_update_ai_phase = yes" not in on_actions:
            issues.append("collapse monthly phase update is missing")
        if "every_country" in on_actions:
            issues.append("collapse monthly phase update must remain country-scoped")
        if "on_state_control_changed" not in on_actions or "ADISCORD_vorkerland_check_khan_border_war = yes" not in on_actions:
            issues.append("Khan border war must resolve from on_state_control_changed")


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
        if "remove_dynamic_modifier" in maps or "transfer_state = 23" in maps:
            issues.append("outcome maps must not clean or transfer contaminated state 23")
    triggers = require_file(issues, root / "common" / "scripted_triggers" / "ADISCORD_vorkerland_collapse_triggers.txt", "collapse outcome triggers")
    legacy_weekly = root / "common" / "on_actions" / "02_ADISCORD_vorkerland_collapse_outcomes_on_actions.txt"
    events = require_file(issues, root / "events" / "ADISCORD_vorkerland_collapse_events.txt", "collapse outcome events")
    if triggers:
        defeated_requirements = {
            "worker": ("vad", "tva"),
            "vlad": ("wrk", "tva"),
            "dorian": ("wrk", "vad"),
        }
        for name, defeated_tags in defeated_requirements.items():
            if f"ADISCORD_vorkerland_{name}_victory_candidate" not in triggers:
                issues.append(f"missing {name} victory candidate trigger")
            for defeated in defeated_tags:
                if f"ADISCORD_vorkerland_{defeated}_defeated = yes" not in triggers:
                    issues.append(f"{name} victory does not require {defeated.upper()} defeat")
    if legacy_weekly.exists():
        issues.append("legacy collapse outcome weekly pulse must be removed")
    if events:
        if "id = ADISCORD_vorkerland_collapse.24" in events or "id = ADISCORD_vorkerland_collapse.25" in events:
            issues.append("collapse outcomes must not use polling or probe events")
        if "update_worker_victory_timer" in events or "update_vlad_victory_timer" in events or "update_dorian_victory_timer" in events:
            issues.append("collapse outcomes must not use victory timers")
        if "days = 1080" not in events:
            issues.append("collapse fragmentation fallback is missing")
        if "ADISCORD_vorkerland_activate_stalemate_missions = yes" not in events:
            issues.append("collapse war start does not activate the stalemate missions")
    on_actions = require_file(
        issues,
        root / "common" / "on_actions" / "01_ADISCORD_vorkerland_collapse_on_actions.txt",
        "collapse on-actions",
    )
    if on_actions:
        if "on_capitulation" not in on_actions:
            issues.append("collapse outcomes must run directly from on_capitulation")
        for name, tag, event_id in (("worker", "WRK", 20), ("vlad", "VAD", 21), ("dorian", "TVA", 22)):
            if f"ADISCORD_vorkerland_{name}_victory_candidate = yes" not in on_actions:
                issues.append(f"on_capitulation does not test the {name} candidate")
            if f"{tag} = {{ country_event = {{ id = ADISCORD_vorkerland_collapse.{event_id} hours = 1 }} }}" not in on_actions:
                issues.append(f"on_capitulation does not route the {tag} victory event")
        if on_actions.count("set_global_flag = skip_default_capitulation") != 3:
            issues.append("each bespoke Vorkerland outcome must reserve the global capitulation fallback")

    fallback = require_file(
        issues,
        root / "common" / "on_actions" / "ZZ_ADISCORD_default_capitulation_on_actions.txt",
        "global default capitulation fallback",
    )
    if fallback:
        for token in (
            "NOT = { has_global_flag = skip_default_capitulation }",
            "every_enemy_country",
            "original_tag = ROOT",
            "is_in_faction_with = ROOT",
            "is_puppet_of = ROOT",
            "white_peace = PREV",
            "target = PREV",
            "transfer_troops = no",
            "clr_global_flag = skip_default_capitulation",
        ):
            if token not in fallback:
                issues.append(f"global capitulation fallback is missing {token}")

    decisions = require_file(
        issues,
        root / "common" / "decisions" / "ADISCORD_vorkerland_collapse_decisions.txt",
        "collapse stalemate mission",
    )
    effects = require_file(
        issues,
        root / "common" / "scripted_effects" / "ADISCORD_vorkerland_collapse_effects.txt",
        "collapse stalemate effects",
    )
    dynamic = require_file(
        issues,
        root / "common" / "dynamic_modifiers" / "ADISCORD_vorkerland_collapse_dynamic_modifiers.txt",
        "collapse dynamic war weariness",
    )
    ai = require_file(issues, root / "common" / "ai_strategy" / "ADISCORD_vorkerland_collapse_ai.txt", "collapse stalemate AI")
    if decisions:
        for token in (
            "ADISCORD_vorkerland_stalemate_deadline",
            "selectable_mission = no",
            "fire_only_once = no",
            "days_mission_timeout = 180",
            "custom_effect_tooltip = ADISCORD_vorkerland_war_weariness_increase_tt",
            "hidden_effect = {",
            "ADISCORD_vorkerland_increase_war_weariness = yes",
            "activate_mission = ADISCORD_vorkerland_stalemate_deadline",
            "set_country_flag = ADISCORD_vorkerland_stalemate_escalation",
        ):
            if token not in decisions:
                issues.append(f"collapse stalemate mission is missing {token}")
    if effects:
        if "ADISCORD_vorkerland_activate_stalemate_missions" not in effects:
            issues.append("collapse stalemate mission activation effect is missing")
        if "has_country_flag = ADISCORD_vorkerland_stalemate_escalation" not in effects:
            issues.append("collapse AI phase updater ignores stalemate escalation")
        for token in (
            "ADISCORD_vorkerland_clear_conflict_country",
            "remove_decision = ADISCORD_vorkerland_stalemate_deadline",
            "ADISCORD_vorkerland_clear_war_weariness = yes",
            "clr_country_flag = ADISCORD_vorkerland_stalemate_escalation",
            "ADISCORD_vorkerland_increase_war_weariness",
            "add_to_variable = { var = ADISCORD_vorkerland_war_weariness_level value = 1 }",
            "clamp_variable = { var = ADISCORD_vorkerland_war_weariness_level min = 1 max = 5 }",
            "add_to_variable = { var = ADISCORD_vorkerland_surrender_limit_offset value = -0.05 }",
            "clamp_variable = { var = ADISCORD_vorkerland_surrender_limit_offset min = -1 max = 0 }",
            "remove_dynamic_modifier = { modifier = ADISCORD_vorkerland_war_weariness }",
            "clear_variable = ADISCORD_vorkerland_surrender_limit_offset",
        ):
            if token not in effects:
                issues.append(f"collapse outcome cleanup is missing {token}")
    if dynamic:
        for token in (
            "ADISCORD_vorkerland_war_weariness = {",
            "custom_modifier_tooltip = ADISCORD_vorkerland_war_weariness_level_tt",
            "war_support_factor = ADISCORD_vorkerland_war_weariness_war_support_factor",
            "stability_factor = ADISCORD_vorkerland_war_weariness_stability_factor",
            "consumer_goods_factor = ADISCORD_vorkerland_war_weariness_consumer_goods_factor",
            "surrender_limit = ADISCORD_vorkerland_surrender_limit_offset",
        ):
            if token not in dynamic:
                issues.append(f"collapse dynamic war weariness is missing {token}")
    if decisions and "add_ideas = ADISCORD_vorkerland_war_weariness" in decisions:
        issues.append("collapse timed mission must not stack the legacy war-weariness idea")
    if events and "id = ADISCORD_vorkerland_collapse.30" in events:
        issues.append("collapse escalating weariness must restart directly without a handoff event")
    if ai:
        if "ADISCORD_vorkerland_stalemate_offensive" not in ai or "priority = 600" not in ai:
            issues.append("collapse stalemate offensive AI strategy is missing")


def validate_superevents(root: Path, issues: list[str]) -> None:
    files = (
        (root / "interface" / "superevents.gfx", "superevent GFX"),
        (root / "interface" / "superevents.gui", "superevent windows"),
        (root / "common" / "scripted_guis" / "superevents.txt", "superevent GUI"),
        (root / "common" / "scripted_localisation" / "ADISCORD_scripted_loc_superevents.txt", "superevent localisation script"),
        (root / "localisation" / "russian" / "ADISCORD_superevents_l_russian.yml", "Russian superevent localisation"),
    )
    for path, label in files:
        text = require_file(issues, path, label)
        if text:
            for name in ("dirty_opening", "worker_victory", "vlad_victory", "dorian_victory", "fragmented"):
                if f"superevent_vorkerland_{name}" not in text:
                    issues.append(f"{label} has no Vorkerland {name} binding")
    maps = require_file(
        issues,
        root / "common" / "scripted_effects" / "ADISCORD_vorkerland_collapse_map_effects.txt",
        "collapse superevent effects",
    )
    news = require_file(issues, root / "events" / "ADISCORD_news.txt", "collapse news events")
    if maps:
        for required in (
            "ADISCORD_vorkerland_play_collapse_superevent_audio",
            "every_country",
            "is_ai = no",
            "scoped_sound_effect = superevent_vorkerland_civilwar_sound_e",
        ):
            if required not in maps:
                issues.append(f"collapse superevent audio is missing {required}")
    if news and "ADISCORD_vorkerland_play_collapse_superevent_audio = yes" not in news:
        issues.append("civil-war superevent does not route audio to the human country")
    timed_flags = (
        (news, "superevent_vorkerland_civilwar"),
        (news, "superevent_stelander_empire"),
        (maps, "superevent_vorkerland_dirty_opening"),
        (maps, "superevent_vorkerland_worker_victory"),
        (maps, "superevent_vorkerland_vlad_victory"),
        (maps, "superevent_vorkerland_dorian_victory"),
        (maps, "superevent_vorkerland_fragmented"),
    )
    for text, flag in timed_flags:
        if text and not re.search(
            rf"set_global_flag\s*=\s*\{{\s*flag\s*=\s*{flag}\s+value\s*=\s*1\s+days\s*=\s*20\s*\}}",
            text,
        ):
            issues.append(f"superevent flag {flag} has no twenty-day observer-safe timeout")


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
