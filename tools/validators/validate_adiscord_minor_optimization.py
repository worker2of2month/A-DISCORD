#!/usr/bin/env python3
"""Validate the explicit TFR-style dormant-minor optimization contract."""

from __future__ import annotations

import re
import sys
from pathlib import Path

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


ROOT = Path(__file__).resolve().parents[2]
TRIGGER_FILE = ROOT / "common/scripted_triggers/ADISCORD_minor_optimization_triggers.txt"
EFFECT_FILE = ROOT / "common/scripted_effects/ADISCORD_minor_optimization_effects.txt"
IDEA_FILE = ROOT / "common/ideas/ADISCORD_minor_optimization_ideas.txt"
ON_ACTION_FILE = ROOT / "common/on_actions/00_ADISCORD_minor_optimization_on_actions.txt"
ECONOMY_EFFECT_FILE = ROOT / "common/scripted_effects/ADISCORD_economy_effects.txt"

EXPECTED_SLOTS = {
    "AIN": 1,
    "AUR": 2,
    "BBV": 2,
    "BCM": 2,
    "BGT": 2,
    "BHG": 2,
    "BJK": 2,
    "BLD": 2,
    "BOR": 3,
    "BRN": 3,
    "COF": 1,
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
    "TFF": 1,
    "TMR": 2,
    "VES": 3,
    "WEF": 2,
    "YPR": 2,
}

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
    return "\n".join(line.split("#", 1)[0] for line in text.splitlines())


def history_slots(tag: str, root: Path = ROOT) -> int | None:
    matches = sorted((root / "history/countries").glob(f"{tag} -*.txt"))
    if len(matches) != 1:
        return None
    match = re.search(r"(?m)^\s*set_research_slots\s*=\s*(\d+)", read(matches[0]))
    return int(match.group(1)) if match else None


def participation_files(tag: str, root: Path = ROOT) -> list[Path]:
    token = re.compile(rf"\b{re.escape(tag)}\b")
    hits: list[Path] = []
    participation_roots = (
        root / "events",
        root / "common/decisions",
        root / "common/national_focus",
        root / "common/ai_strategy",
        root / "common/ai_strategy_plans",
        root / "common/on_actions",
        root / "common/scripted_effects",
        root / "common/scripted_triggers",
    )
    scan_exclusions = {
        (root / "common/scripted_triggers/ADISCORD_minor_optimization_triggers.txt").resolve(),
        (root / "common/scripted_effects/ADISCORD_minor_optimization_effects.txt").resolve(),
        (root / "common/on_actions/00_ADISCORD_minor_optimization_on_actions.txt").resolve(),
        (root / "common/scripted_effects/ADISCORD_technology_baseline_effects.txt").resolve(),
        (root / "common/scripted_triggers/ADISCORD_development_country_lists.txt").resolve(),
    }
    for participation_root in participation_roots:
        if not participation_root.exists():
            continue
        for path in participation_root.rglob("*.txt"):
            if path.resolve() in scan_exclusions:
                continue
            if token.search(uncommented(read(path))):
                hits.append(path.relative_to(root))
    return sorted(hits)


def validate(root: Path = ROOT) -> list[str]:
    root = Path(root)
    issues: list[str] = []
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
    economy_effect_text = read(
        root / "common/scripted_effects/ADISCORD_economy_effects.txt"
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
        "is_ai = yes",
        "has_war = no",
        "ADISCORD_is_non_participating_minor = yes",
        "has_country_flag = ADISCORD_non_participating_minor_released",
    ):
        if required not in eligibility:
            issues.append(f"eligibility trigger lacks {required}")

    for tag, expected_slots in sorted(EXPECTED_SLOTS.items()):
        actual_slots = history_slots(tag, root)
        if actual_slots != expected_slots:
            issues.append(f"{tag}: history has {actual_slots!r} research slots, expected {expected_slots}")
        hits = participation_files(tag, root)
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

    restore_block = named_block(effect_text, "ADISCORD_restore_non_participating_minor_research_slots")
    restore_tags = set(re.findall(r"\btag\s*=\s*([A-Z0-9]{3})\b", restore_block))
    if restore_tags != expected_tags:
        issues.append(
            "research restore list mismatch: "
            f"missing={sorted(expected_tags - restore_tags)} extra={sorted(restore_tags - expected_tags)}"
        )
    for slots in sorted(set(EXPECTED_SLOTS.values())):
        if f"set_research_slots = {slots}" not in restore_block:
            issues.append(f"research restore effect lacks {slots}-slot branch")

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
    if startup.count("every_country") != 1:
        issues.append("startup must perform exactly one country scan")
    if "ADISCORD_apply_non_participating_minor_optimization = yes" not in startup:
        issues.append("startup does not apply minor optimization")
    if "ADISCORD_release_non_participating_minor_optimization = yes" not in war:
        issues.append("on_war does not release an involved minor")
    for forbidden in ("on_daily", "on_weekly", "on_yearly"):
        if re.search(rf"(?m)^\s*{forbidden}\s*=", on_action_text):
            issues.append(f"optimization uses recurring poll {forbidden}")

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
    issues = validate()
    if issues:
        print("Dormant-minor optimization validation failed:")
        for issue in issues:
            print(f"- {issue}")
        return 1

    print(
        f"Dormant-minor optimization validation passed: {len(EXPECTED_SLOTS)} audited AI tags, "
        "TFR-style suppression, and event-driven wartime release."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
