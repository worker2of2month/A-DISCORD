#!/usr/bin/env python3
"""Audit country dependencies and validate reversible minor suppression."""

from __future__ import annotations

import argparse
from collections import Counter
import json
import re
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

try:
    from tools.validators.validate_adiscord_economy_ai import (
        ai_assistance_contract_issues,
        ai_assistance_lifecycle_issues,
    )
except ModuleNotFoundError:  # Direct ``python tools/validators/...`` invocation.
    from validate_adiscord_economy_ai import (
        ai_assistance_contract_issues,
        ai_assistance_lifecycle_issues,
    )


from tools.lib.paths import source_section
from tools.validators.validate_adiscord_division_templates import parse_clausewitz


ROOT = Path(__file__).resolve().parents[2]
TRIGGER_FILE = ROOT / "common/scripted_triggers/ADISCORD_minor_optimization_triggers.txt"
EFFECT_FILE = ROOT / "common/scripted_effects/ADISCORD_minor_optimization_effects.txt"
IDEA_FILE = ROOT / "common/ideas/ADISCORD_minor_optimization_ideas.txt"
ON_ACTION_FILE = ROOT / "common/on_actions/00_ADISCORD_minor_optimization_on_actions.txt"
ECONOMY_EFFECT_FILE = ROOT / "common/scripted_effects/ADISCORD_economy_effects.txt"
PHASE_EFFECT_FILE = ROOT / "common/scripted_effects/ADISCORD_vorkerland_effects.txt"
GENERAL_HISTORY_FILE = ROOT / "history/general/ADISCORD_general_history.txt"

FRESH_CONTRACT = "ADISCORD_fresh_campaign_contract_v1"
FEATURE_FLAG = "ADISCORD_minor_optimization_fresh_campaign_v1"
TERMINAL_TAGS = {
    "WRK", "WKR", "VAD", "TVA", "WTD", "EYR", "EGC", "RIV", "REV",
    "YOR", "NDN", "SWB", "VHV", "OSV", "ZAO", "PWR", "VLA", "ROM",
    "SOL", "TRU", "WPA", "WPS", "PSD", "EBA", "DVA", "SRA", "ZTA",
    "TGD", "IBL", "IBA", "CSL",
}

EXPECTED_SLOTS = {
    "AUR": 2,
    "BBV": 2,
    "BCM": 2,
    "BGT": 2,
    "BHG": 2,
    "BJK": 2,
    "BLD": 2,
    "BOR": 3,
    "BRN": 3,
    "DOL": 3,
    "DRV": 2,
    "ELN": 3,
    "FRS": 2,
    "GLP": 2,
    "HON": 3,
    "KDR": 2,
    "KHV": 3,
    "KRL": 3,
    "KYZ": 2,
    "LYS": 3,
    "MON": 4,
    "NVR": 2,
    "ORV": 2,
    "RIN": 3,
    "RLY": 2,
    "SDR": 2,
    "SHL": 2,
    "SKN": 3,
    "TMR": 2,
    "VES": 3,
    "WEF": 2,
}

# Retired suppression entries still need restoration in existing campaigns.
RESTORE_SLOTS = {"AIN": 1, **EXPECTED_SLOTS}

PARTICIPATION_ROOTS = (
    ROOT / "events",
    ROOT / "common/decisions",
    ROOT / "common/national_focus",
    ROOT / "common/ai_strategy",
    ROOT / "common/ai_strategy_plans",
    ROOT / "common/on_actions",
    ROOT / "common/scripted_effects",
    ROOT / "common/scripted_triggers",
)

INVENTORY_ROOTS = (
    ROOT / "common/ideas", ROOT / "common/ai_templates", ROOT / "common/ai_navy",
    ROOT / "common/scripted_guis", ROOT / "common/scripted_localisation",
)

SCAN_EXCLUSIONS = {
    TRIGGER_FILE.resolve(),
    EFFECT_FILE.resolve(),
    ON_ACTION_FILE.resolve(),
    (ROOT / "common/scripted_effects/ADISCORD_technology_baseline_effects.txt").resolve(),
    (ROOT / "common/scripted_triggers/ADISCORD_development_country_lists.txt").resolve(),
}

# RIN and MON remain suppressed before the Vorkerland war, then a one-shot
# feature router releases both countries before it schedules their crisis.
# Keep the exception path-scoped: a reference anywhere else is still a
# regression that silently turns a dormant country into an active participant.
EVENT_AWAKENED_PARTICIPATION = {
    tag: {
        Path("events/ADISCORD_rin_oath_crisis_events.txt"),
        Path("common/decisions/ADISCORD_rin_oath_crisis_decisions.txt"),
        Path("common/decisions/categories/ADISCORD_rin_oath_crisis_categories.txt"),
        Path("common/on_actions/02_ADISCORD_rin_oath_crisis_on_actions.txt"),
        Path("common/scripted_effects/ADISCORD_rin_oath_crisis_effects.txt"),
        Path("common/scripted_triggers/ADISCORD_rin_oath_crisis_triggers.txt"),
    }
    for tag in ("MON", "RIN")
}

# The feudal bloc wakes on war entry or when an authored settlement installs
# an administration without requiring that minor to have joined the war.
BEZHAYSK_TAGS = {"BJK", "BLD", "BHG", "BGT", "BBV", "BCM"}
for _tag in BEZHAYSK_TAGS:
    EVENT_AWAKENED_PARTICIPATION[_tag] = {
        Path("common/on_actions/09_ADISCORD_scripted_peace_on_actions.txt"),
        Path("common/scripted_effects/ADISCORD_bezhaysk_peace_effects.txt"),
    }
EVENT_AWAKENED_PARTICIPATION["BJK"].update({
    Path("common/decisions/ADISCORD_STP_decisions.txt"),
    Path("common/national_focus/ADISCORD_national_focus_STP.txt"),
    Path("common/national_focus/ADISCORD_national_focus_VAL.txt"),
    Path("common/scripted_triggers/ADISCORD_STP_scripted_triggers.txt"),
    Path("common/scripted_triggers/ADISCORD_VAL_rework_triggers.txt"),
    Path("events/ADISCORD_STP_events.txt"),
})


def bezhaysk_administration_release_issues(text: str) -> list[str]:
    """Every administration payload must wake its country before cache invalidation."""
    issues = []

    def inspect(entries, scope=None):
        markers = {"ADISCORD_bezhaysk_val_administration", "ADISCORD_bezhaysk_nod_administration"}
        if scope in BEZHAYSK_TAGS and any(node.key == "set_country_flag" and node.value in markers for node in entries):
            releases = [i for i, node in enumerate(entries)
                        if node.key == "ADISCORD_release_non_participating_minor_optimization" and node.value == "yes"]
            refreshes = [i for i, node in enumerate(entries) if node.key == "ADISCORD_economy_mark_dirty"]
            if len(releases) != 1 or not refreshes or releases[0] >= refreshes[0]:
                issues.append(f"{scope}: Bezhaysk administration must release suppression before refreshing economy")
        for node in entries:
            if isinstance(node.value, list):
                inspect(node.value, node.key if re.fullmatch(r"[A-Z]{3}", node.key) else scope)

    inspect(parse_clausewitz(text))
    return issues


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


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


def uncommented(text: str) -> str:
    return re.sub(
        r'"(?:\\.|[^"\\])*"|#[^\n]*',
        lambda match: "" if match[0].startswith("#") else match[0],
        text,
    )


def history_slots(tag: str, root: Path = ROOT) -> int | None:
    matches = sorted((root / "history/countries").glob(f"{tag} -*.txt"))
    if len(matches) != 1:
        return None
    match = re.search(r"(?m)^\s*set_research_slots\s*=\s*(\d+)", read(matches[0]))
    return int(match.group(1)) if match else None


def participation_index(root: Path = ROOT, *, include_passive: bool = False) -> dict[str, set[Path]]:
    """Conservative literal references, indexed in one pass; not a reachability proof."""
    hits: dict[str, set[Path]] = {}
    roots = PARTICIPATION_ROOTS + (INVENTORY_ROOTS if include_passive else ())
    participation_roots = (root / path.relative_to(ROOT) for path in roots)
    scan_exclusions = {root / path.relative_to(ROOT) for path in SCAN_EXCLUSIONS}
    for participation_root in participation_roots:
        if not participation_root.exists():
            continue
        for path in participation_root.rglob("*.txt"):
            if path in scan_exclusions:
                continue
            for tag in set(re.findall(r"\b[A-Z][A-Z0-9]{2}\b", uncommented(read(path)))):
                hits.setdefault(tag, set()).add(path.relative_to(root))
    return hits


def participation_files(tag: str, root: Path = ROOT) -> list[Path]:
    return sorted(participation_index(root).get(tag, set()))


def research_restore_slots(effect_text: str) -> dict[str, int]:
    """Read each disjoint tag branch; reject ambiguous or conditional restoration."""
    definition = parse_clausewitz(named_block(
        effect_text, "ADISCORD_restore_non_participating_minor_research_slots"
    ))[0]
    result: dict[str, int] = {}
    for index, branch in enumerate(definition.value):
        expected_kind = "if" if index == 0 else "else_if"
        if branch.key != expected_kind or not isinstance(branch.value, list):
            raise ValueError("research restoration must use one disjoint if/else_if chain")
        if [entry.key for entry in branch.value] != ["limit", "set_research_slots"]:
            raise ValueError("research restoration branch must own one limit and one slot write")
        limit, slots = branch.value
        conditions = limit.value
        if not isinstance(conditions, list):
            raise ValueError("research restoration limit must be a trigger block")
        if len(conditions) == 1 and conditions[0].key == "OR":
            conditions = conditions[0].value
        elif len(conditions) != 1:
            raise ValueError("research restoration tag alternatives require OR")
        if not conditions or any(
            entry.key != "tag" or not isinstance(entry.value, str) for entry in conditions
        ):
            raise ValueError("research restoration has a non-tag condition")
        for entry in conditions:
            if entry.value in result:
                raise ValueError(f"duplicate research restoration tag {entry.value}")
            result[entry.value] = int(slots.value)
    return result


def country_inventory(root: Path = ROOT) -> list[dict]:
    """Declared initial ownership and literal dependencies; dates/dynamic scopes need review."""
    tags = {}
    for path in sorted((root / "common/country_tags").glob("*.txt")):
        for entry in parse_clausewitz(read(path)):
            if re.fullmatch(r"[A-Z][A-Z0-9]{2}", entry.key):
                tags[entry.key] = entry.value
    owners, cores = Counter(), Counter()
    for path in sorted((root / "history/states").glob("*.txt")):
        for state in parse_clausewitz(read(path)):
            if state.key != "state" or not isinstance(state.value, list):
                continue
            for history in state.value:
                if history.key != "history" or not isinstance(history.value, list):
                    continue
                for entry in history.value:
                    if entry.key == "owner":
                        owners[entry.value] += 1
                    elif entry.key == "add_core_of":
                        cores[entry.value] += 1
    references = participation_index(root, include_passive=True)
    rows = []
    for tag in sorted(tags):
        histories = sorted((root / "history/countries").glob(f"{tag} -*.txt"))
        oobs = []
        for path in histories:
            for entry in parse_clausewitz(read(path)):
                if entry.key in {"oob", "set_oob", "set_air_oob", "set_naval_oob"}:
                    oobs.append(entry.value)
        rows.append({
            "tag": tag, "definition": tags[tag], "initial_states": owners[tag],
            "initial_cores": cores[tag], "country_history": [p.relative_to(root).as_posix() for p in histories],
            "initial_oob": oobs, "suppressed_ai": tag in EXPECTED_SLOTS,
            "story_awakened": tag in EVENT_AWAKENED_PARTICIPATION,
            "script_references": [p.as_posix() for p in sorted(references.get(tag, set()))],
        })
    return rows


def script_shape(entries):
    return tuple((entry.key, script_shape(entry.value) if isinstance(entry.value, list)
                  else entry.value) for entry in entries)


def minor_lifecycle_issues(triggers: str, effects: str, hooks: str, shared_hooks: str) -> list[str]:
    """Validate guarded recovery and skipped assistance work independently of prose."""
    issues = []
    contracts = (
        (triggers, "ADISCORD_can_optimize_non_participating_minor", '''
            has_global_flag = ADISCORD_minor_optimization_fresh_campaign_v1
            is_ai = yes has_war = no ADISCORD_is_non_participating_minor = yes
            NOT = { has_country_flag = ADISCORD_non_participating_minor_released }
            NOT = { has_country_flag = ADISCORD_non_participating_minor_optimized }
        '''),
        (triggers, "ADISCORD_minor_optimization_needs_release", '''
            has_country_flag = ADISCORD_non_participating_minor_optimized
            OR = { is_ai = no has_war = yes NOT = { ADISCORD_is_non_participating_minor = yes } }
        '''),
        (effects, "ADISCORD_apply_non_participating_minor_optimization", '''
            if = { limit = { ADISCORD_can_optimize_non_participating_minor = yes }
                add_ideas = ADISCORD_non_participating_minor_optimization
                country_lock_all_division_template = yes set_research_slots = 0
                set_country_flag = ADISCORD_non_participating_minor_optimized
                if = { limit = { ADISCORD_economy_has_current_schema = yes }
                    ADISCORD_economy_set_simulation_tier = yes } }
        '''),
        (effects, "ADISCORD_release_non_participating_minor_optimization", '''
            if = { limit = { has_country_flag = ADISCORD_non_participating_minor_optimized }
                remove_ideas = ADISCORD_non_participating_minor_optimization
                country_lock_all_division_template = no
                ADISCORD_restore_non_participating_minor_research_slots = yes
                clr_country_flag = ADISCORD_non_participating_minor_optimized
                set_country_flag = ADISCORD_non_participating_minor_released
                if = { limit = { ADISCORD_economy_has_current_schema = yes }
                    ADISCORD_economy_initialize_country = yes
                    ADISCORD_economy_full_refresh = yes
                    ADISCORD_economy_light_update = yes
                    ADISCORD_economy_update_gui = yes }
                else_if = {
                    limit = { OR = { is_ai = no ADISCORD_economy_is_primary_tier_country = yes ADISCORD_economy_is_secondary_tier_country = yes } }
                    ADISCORD_economy_initialize_country = yes } }
        '''),
        (effects, "ADISCORD_reconcile_non_participating_minor_optimization", '''
            if = { limit = { ADISCORD_minor_optimization_needs_release = yes }
                ADISCORD_release_non_participating_minor_optimization = yes }
        '''),
    )
    for text, name, expected in contracts:
        try:
            actual = parse_clausewitz(named_block(text, name))[0].value
            if script_shape(actual) != script_shape(parse_clausewitz(expected)):
                issues.append(f"{name}: suppression/recovery contract differs")
        except (ValueError, IndexError) as exc:
            issues.append(f"{name}: {exc}")

    expected_monthly = parse_clausewitz('''
        if = { limit = { has_country_flag = ADISCORD_non_participating_minor_optimized }
            ADISCORD_reconcile_non_participating_minor_optimization = yes }
    ''')
    try:
        monthly = parse_clausewitz(named_block(shared_hooks, "on_monthly"))[0].value
        payload = next(entry.value for entry in monthly if entry.key == "effect")
        recovery_positions = [i for i, entry in enumerate(payload)
                              if script_shape([entry]) == script_shape(expected_monthly)]
        economy_positions = [i for i, entry in enumerate(payload)
                             if "ADISCORD_economy_should_monthly_update" in str(script_shape([entry]))]
        if (len(recovery_positions) != 1 or len(economy_positions) != 1
                or recovery_positions[0] >= economy_positions[0]):
            issues.append("monthly recovery must precede the economy gate with its optimized guard")
        if shared_hooks.count("ADISCORD_reconcile_non_participating_minor_optimization = yes") != 1:
            issues.append("monthly recovery must have exactly one shared caller")
    except (ValueError, StopIteration) as exc:
        issues.append(f"monthly recovery: {exc}")

    expected_assistance = script_shape(parse_clausewitz('''
        limit = { ADISCORD_economy_ai_assistance_needs_edge_evaluation = yes }
        ADISCORD_economy_refresh_ai_assistance = yes
    '''))

    def inspect(entries, parent=None):
        for entry in entries:
            if entry.key == "ADISCORD_economy_refresh_ai_assistance":
                if parent is None or parent.key != "if" or script_shape(parent.value) != expected_assistance:
                    issues.append("assistance edge lacks the eligibility-or-stale-idea guard")
            if isinstance(entry.value, list):
                inspect(entry.value, entry)

    for name in ("on_startup", "on_war", "on_peace"):
        inspect(parse_clausewitz(named_block(hooks, name)))
    return issues


def validate(root: Path = ROOT) -> list[str]:
    root = Path(root)
    issues: list[str] = []
    issues.extend(bezhaysk_administration_release_issues(read(
        root / "common/scripted_effects/ADISCORD_bezhaysk_peace_effects.txt")))
    trigger_text = read(
        root / "common/scripted_triggers/ADISCORD_minor_optimization_triggers.txt"
    )
    effect_text = read(
        root / "common/scripted_effects/ADISCORD_minor_optimization_effects.txt"
    )
    idea_text = read(root / "common/ideas/ADISCORD_minor_optimization_ideas.txt")
    all_idea_text = "\n".join(
        read(path) for path in sorted((root / "common/ideas").rglob("*.txt"))
    )
    all_effect_text = "\n".join(
        read(path)
        for path in sorted((root / "common/scripted_effects").rglob("*.txt"))
    )
    on_action_text = read(
        root / "common/on_actions/00_ADISCORD_minor_optimization_on_actions.txt"
    )
    issues.extend(minor_lifecycle_issues(
        trigger_text, effect_text, on_action_text,
        read(root / "common/on_actions/00_ADISCORD_on_actions.txt"),
    ))
    economy_effect_text = read(
        root / "common/scripted_effects/ADISCORD_economy_effects.txt"
    )
    phase_effect_text = source_section(read(
        root / "common/scripted_effects/ADISCORD_vorkerland_effects.txt"
    ), 'phase_effects')
    general_history_text = read(
        root / "history/general/ADISCORD_general_history.txt"
    )

    try:
        dormant_block = named_block(trigger_text, "ADISCORD_is_non_participating_minor")
        dormant_tags = set(re.findall(r"\btag\s*=\s*([A-Z0-9]{3})\b", dormant_block))
    except ValueError as exc:
        issues.append(str(exc))
        dormant_tags = set()

    expected_tags = set(EXPECTED_SLOTS)
    if dormant_tags != expected_tags:
        issues.append(
            "dormant tag list mismatch: "
            f"missing={sorted(expected_tags - dormant_tags)} extra={sorted(dormant_tags - expected_tags)}"
        )

    eligibility = named_block(trigger_text, "ADISCORD_can_optimize_non_participating_minor")
    for required in (
        f"has_global_flag = {FEATURE_FLAG}",
        "is_ai = yes",
        "has_war = no",
        "ADISCORD_is_non_participating_minor = yes",
        "has_country_flag = ADISCORD_non_participating_minor_released",
    ):
        if required not in eligibility:
            issues.append(f"eligibility trigger lacks {required}")

    references = participation_index(root)
    for tag, expected_slots in sorted(EXPECTED_SLOTS.items()):
        actual_slots = history_slots(tag, root)
        if actual_slots != expected_slots:
            issues.append(f"{tag}: history has {actual_slots!r} research slots, expected {expected_slots}")
        hits = references.get(tag, set())
        allowed_hits = EVENT_AWAKENED_PARTICIPATION.get(tag, set())
        unexpected_hits = set(hits) - allowed_hits
        if unexpected_hits:
            issues.append(
                f"{tag}: dormant tag now participates outside its event-awakened contract in "
                f"{', '.join(map(str, sorted(unexpected_hits)))}"
            )

    apply_block = named_block(effect_text, "ADISCORD_apply_non_participating_minor_optimization")
    for required in (
        "add_ideas = ADISCORD_non_participating_minor_optimization",
        "country_lock_all_division_template = yes",
        "set_research_slots = 0",
        "set_country_flag = ADISCORD_non_participating_minor_optimized",
    ):
        if required not in apply_block:
            issues.append(f"apply effect lacks {required}")

    release_block = named_block(effect_text, "ADISCORD_release_non_participating_minor_optimization")
    for required in (
        "remove_ideas = ADISCORD_non_participating_minor_optimization",
        "country_lock_all_division_template = no",
        "ADISCORD_restore_non_participating_minor_research_slots = yes",
        "clr_country_flag = ADISCORD_non_participating_minor_optimized",
        "set_country_flag = ADISCORD_non_participating_minor_released",
    ):
        if required not in release_block:
            issues.append(f"release effect lacks {required}")

    try:
        restored = research_restore_slots(effect_text)
        if restored != RESTORE_SLOTS:
            issues.append("research restore tag-to-slot mapping differs from authored capacities")
    except (ValueError, TypeError) as exc:
        issues.append(f"invalid research restoration: {exc}")

    for required in (
        "production_speed_buildings_factor = -9999",
        "industrial_capacity_factory = -9999",
        "industrial_capacity_dockyard = -9999",
        "consumer_goods_factor = 10",
        "conscription = -1",
    ):
        if required not in idea_text:
            issues.append(f"optimization idea lacks {required}")

    startup = named_block(on_action_text, "on_startup")
    war = named_block(on_action_text, "on_war")
    state_control = named_block(on_action_text, "on_state_control_changed")
    if startup.count("every_country") != 1:
        issues.append("fresh startup must perform exactly one country scan")
    if "ADISCORD_apply_non_participating_minor_optimization = yes" not in startup:
        issues.append("startup does not apply minor optimization")
    if startup.count("ADISCORD_economy_refresh_ai_assistance = yes") != 1:
        issues.append("fresh startup does not initialize assistance exactly once per scanned country")
    startup_order = [
        startup.find(f"has_global_flag = {FRESH_CONTRACT}"),
        startup.find(f"NOT = {{ has_global_flag = {FEATURE_FLAG} }}"),
        startup.find(f"set_global_flag = {FEATURE_FLAG}"),
        startup.find("every_country"),
    ]
    if any(position < 0 for position in startup_order) or startup_order != sorted(startup_order):
        issues.append("startup lacks ordered fresh-contract guard, feature guard, activation, and scan")
    if general_history_text.count(f"set_global_flag = {FRESH_CONTRACT}") != 1:
        issues.append("general history does not seed the fresh-campaign contract exactly once")
    if "ADISCORD_release_non_participating_minor_optimization = yes" not in war:
        issues.append("on_war does not release an involved minor")
    if state_control.count("ADISCORD_economy_ai_assistance_needs_edge_evaluation = yes") != 2:
        issues.append("state-control assistance edge does not guard ROOT and FROM exactly once")
    if state_control.count("ADISCORD_economy_refresh_ai_assistance = yes") != 2:
        issues.append("state-control assistance edge does not refresh ROOT and FROM exactly once")
    if state_control.count("FROM =") != 1:
        issues.append("state-control assistance edge lacks one former-controller scope")
    if any(token in state_control for token in ("every_country", "any_country")):
        issues.append("state-control assistance edge scans countries")
    for forbidden in ("on_daily", "on_weekly", "on_monthly", "on_yearly"):
        if re.search(rf"(?m)^\s*{forbidden}\s*=", on_action_text):
            issues.append(f"optimization uses recurring poll {forbidden}")

    refresh_block = named_block(effect_text, "ADISCORD_economy_refresh_ai_assistance")
    if refresh_block.count(f"has_global_flag = {FEATURE_FLAG}") != 1:
        issues.append("assistance refresh lacks one fresh-campaign feature gate")

    terminal_country = named_block(
        effect_text, "ADISCORD_economy_refresh_terminal_assistance_country"
    )
    if "exists = yes" not in terminal_country or terminal_country.count(
        "ADISCORD_economy_refresh_ai_assistance = yes"
    ) != 1:
        issues.append("terminal assistance country helper is not existence-guarded and singular")
    terminal = named_block(
        effect_text, "ADISCORD_economy_refresh_vorkerland_terminal_assistance"
    )
    terminal_tags = set(
        re.findall(r"(?m)^\s*([A-Z0-9]{3})\s*=\s*\{", terminal)
    )
    if terminal_tags != TERMINAL_TAGS:
        issues.append(
            "terminal assistance tag set mismatch: "
            f"missing={sorted(TERMINAL_TAGS - terminal_tags)} "
            f"extra={sorted(terminal_tags - TERMINAL_TAGS)}"
        )
    if terminal.count("ADISCORD_economy_refresh_terminal_assistance_country = yes") != len(
        TERMINAL_TAGS
    ):
        issues.append("terminal assistance fanout is not exactly one call per authored tag")
    if any(token in terminal for token in ("every_country", "any_country")):
        issues.append("terminal assistance fanout scans countries")
    finalizer = named_block(phase_effect_text, "ADISCORD_vorkerland_finalize_reunified_wrk")
    finish_position = finalizer.find(
        "set_global_flag = ADISCORD_vorkerland_collapse_finished"
    )
    refresh_position = finalizer.find(
        "ADISCORD_economy_refresh_vorkerland_terminal_assistance = yes"
    )
    if (
        finish_position < 0
        or refresh_position < 0
        or finish_position >= refresh_position
        or finalizer.count(
            "ADISCORD_economy_refresh_vorkerland_terminal_assistance = yes"
        ) != 1
    ):
        issues.append("terminal assistance refresh is not called once after collapse_finished")

    issues.extend(
        ai_assistance_contract_issues(all_idea_text, all_effect_text, trigger_text)
    )
    issues.extend(
        ai_assistance_lifecycle_issues(
            economy_effect_text, effect_text, on_action_text
        )
    )

    return issues


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory", action="store_true", help="Print declared country ownership and dependency inventory as JSON")
    args = parser.parse_args()
    if args.inventory:
        print(json.dumps(country_inventory(), ensure_ascii=False, indent=2))
        return 0
    issues = validate()
    if issues:
        print("Dormant-minor optimization validation failed:")
        for issue in issues:
            print(f"- {issue}")
        return 1

    print(
        f"Dormant-minor optimization validation passed: {len(EXPECTED_SLOTS)} audited AI tags, "
        "reversible suppression, and event-driven wartime release."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
