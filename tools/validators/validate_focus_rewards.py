"""Conservative editorial lint for standalone, consumable-only focus rewards.

The units below are an authoring floor, not a claim about campaign balance.
Conditional, scoped and opaque effects require semantic review. Research,
permanent capabilities and story routes deliberately have no numeric floor.
Consumer indexing verifies native reads and their local action, not reachability
of scripted definitions; an uncalled scripted consumer needs semantic review.
"""

from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
import re

from tools.validators.validate_adiscord_division_templates import Entry, parse_clausewitz


ROOT = Path(__file__).resolve().parents[2]
PREVIEW_FILES = frozenset({"ADISCORD_national_focus_bookmark.txt"})
CONSUMER_DIRECTORIES = (
    "common/decisions",
    "common/scripted_effects",
    "common/scripted_triggers",
    "common/on_actions",
    "events",
)
IGNORED_CONTEXTS = frozenset({
    "effect_tooltip", "custom_effect_tooltip", "ai_will_do", "ai_chance",
    "ai_weight", "ai_strategy", "ai_strategy_plan", "prerequisite",
})
CONDITION_CONTEXTS = frozenset({
    "limit", "trigger", "visible", "available", "allowed", "potential",
    "activation", "target_trigger", "cancel_trigger", "custom_cost_trigger",
    "abort", "fire_only_once", "mean_time_to_happen",
})
RESOURCE_UNITS = {
    "add_political_power": 75,
    "army_experience": 40,
    "navy_experience": 40,
    "air_experience": 40,
    "add_command_power": 40,
    "add_stability": 0.05,
    "add_war_support": 0.05,
    "add_manpower": 4000,
    "add_fuel": 10000,
}
EQUIPMENT_UNITS = {
    "support_equipment": 300,
    "motorized_equipment": 300,
    "infantry_equipment": 9000,
    "artillery_equipment": 100,
    "convoy": 20,
    "train_equipment": 12,
}
SCORING_UNITS = {
    **RESOURCE_UNITS,
    **{f"equipment:{equipment}": unit for equipment, unit in EQUIPMENT_UNITS.items()},
    "treasury": 600,
}
SUBSTANTIVE_EFFECTS = frozenset({
    "add_ideas", "remove_ideas", "swap_ideas", "add_timed_idea",
    "add_dynamic_modifier", "remove_dynamic_modifier",
    "add_tech_bonus", "add_doctrine_cost_reduction", "set_technology",
    "add_research_slot", "add_to_tech_sharing_group",
    "country_event", "news_event", "state_event",
    "add_building_construction", "add_extra_state_shared_building_slots",
    "set_building_level", "add_resource", "remove_resource",
    "add_offsite_building", "add_province_modifier", "add_state_modifier",
    "add_core_of", "remove_core_of", "add_state_claim", "remove_state_claim",
    "transfer_state", "set_state_owner", "set_state_controller", "annex_country",
    "create_wargoal", "declare_war_on", "create_faction", "add_to_faction",
    "set_autonomy", "release", "release_puppet", "puppet", "white_peace",
    "load_oob", "create_unit", "division_template", "create_ship",
    "add_equipment_production", "set_rule", "set_politics",
    "add_popularity", "add_opinion_modifier", "add_to_faction",
    "activate_advisor", "recruit_character", "promote_character",
    "add_country_leader_role", "add_corps_commander_role", "add_field_marshal_role",
    "add_power_balance_value", "set_power_balance", "add_intel",
    "add_to_war", "diplomatic_relation", "set_country_leader_ideology", "set_cosmetic_tag",
    "send_equipment", "transfer_units_fraction",
})
BOOKKEEPING_EFFECTS = frozenset({
    "clr_country_flag", "set_temp_variable", "clear_variable",
    "log", "log_command", "ADISCORD_economy_mark_dirty",
})
LEDGER_VARIABLE = "ADISCORD_economy_current_month_action_income"
TREASURY_VARIABLE = "ADISCORD_economy_treasury"
STATE_VARIABLE_EFFECTS = frozenset({
    "set_variable", "add_to_variable", "subtract_from_variable",
    "multiply_variable", "divide_variable", "clamp_variable",
})


@dataclass(frozen=True)
class FocusReward:
    path: str
    line: int
    focus_id: str
    cost: float | None
    classification: str
    score: float
    threshold: float | None
    review_effects: tuple[str, ...] = ()


@dataclass
class AuditReport:
    focuses: list[FocusReward] = field(default_factory=list)
    counts: Counter = field(default_factory=Counter)
    parse_issues: list[str] = field(default_factory=list)


@dataclass
class _Reward:
    amounts: dict[str, float] = field(default_factory=dict)
    substantive: bool = False
    flags: set[str] = field(default_factory=set)
    review: set[str] = field(default_factory=set)

    @property
    def score(self) -> float:
        return sum(max(0, amount) / SCORING_UNITS[resource] for resource, amount in self.amounts.items())

    def add_resource(self, resource: str, amount: float) -> None:
        self.amounts[resource] = self.amounts.get(resource, 0) + amount

    def merge(self, other: _Reward) -> None:
        for resource, amount in other.amounts.items():
            self.add_resource(resource, amount)
        self.substantive |= other.substantive
        self.flags.update(other.flags)
        self.review.update(other.review)


def _scalar(entries: list[Entry], key: str) -> str | None:
    return next(
        (entry.value for entry in entries if entry.key == key and isinstance(entry.value, str)),
        None,
    )


def _number(value: str | None) -> float | None:
    try:
        number = float(value) if value is not None else None
    except ValueError:
        return None
    return number if number is None or float("-inf") < number < float("inf") else None


def _walk(entries: list[Entry]):
    for entry in entries:
        if entry.key in IGNORED_CONTEXTS:
            continue
        yield entry
        if isinstance(entry.value, list):
            yield from _walk(entry.value)


def _definitions(entries: list[Entry]):
    for entry in entries:
        if entry.key in {"focus", "shared_focus"} and isinstance(entry.value, list):
            yield entry
        elif isinstance(entry.value, list):
            yield from _definitions(entry.value)


def _equipment_resource(name: str | None) -> str | None:
    if name is None:
        return None
    for equipment in EQUIPMENT_UNITS:
        if re.fullmatch(rf"(?:ADISCORD_)?{equipment}(?:_\d+)?", name):
            return f"equipment:{equipment}"
    return None


def _variable_value(entries: list[Entry]) -> tuple[str | None, float | None]:
    variable = _scalar(entries, "var")
    if variable is not None:
        return variable, _number(_scalar(entries, "value"))
    # Native variable effects also accept ``{ variable_name = amount }``.
    if len(entries) == 1 and isinstance(entries[0].value, str):
        return entries[0].key, _number(entries[0].value)
    return None, None


def _analyse(entries: list[Entry], scripts: dict[str, list[Entry]], stack=()) -> _Reward:
    result = _Reward()
    for entry in entries:
        key = entry.key
        if key in IGNORED_CONTEXTS or key in BOOKKEEPING_EFFECTS:
            continue
        if key == "hidden_effect" and isinstance(entry.value, list):
            result.merge(_analyse(entry.value, scripts, stack))
        elif key in RESOURCE_UNITS:
            amount = _number(entry.value if isinstance(entry.value, str) else None)
            if amount is None:
                result.review.add(key)
            else:
                result.add_resource(key, amount)
        elif key == "add_equipment_to_stockpile" and isinstance(entry.value, list):
            resource = _equipment_resource(_scalar(entry.value, "type"))
            amount = _number(_scalar(entry.value, "amount"))
            if resource is None or amount is None:
                result.review.add(key)
            else:
                result.add_resource(resource, amount)
        elif key == "set_country_flag":
            flag = entry.value if isinstance(entry.value, str) else _scalar(entry.value, "flag")
            if flag:
                result.flags.add(flag)
            else:
                result.review.add(key)
        elif key in {"add_to_variable", "subtract_from_variable"} and isinstance(entry.value, list):
            variable, amount = _variable_value(entry.value)
            if variable == LEDGER_VARIABLE:
                continue
            if variable == TREASURY_VARIABLE and amount is not None:
                signed_amount = -amount if key == "subtract_from_variable" else amount
                result.add_resource("treasury", signed_amount)
            else:
                result.review.add(f"{key}:{variable or '?'}")
        elif key == "unlock_decision_tooltip":
            # A tooltip is only evidence of access when a native gameplay gate
            # consumes this focus or one of its flags; the index checks that.
            continue
        elif key in SUBSTANTIVE_EFFECTS:
            result.substantive = True
        elif key in scripts and entry.value == "yes" and key not in stack:
            result.merge(_analyse(scripts[key], scripts, stack + (key,)))
        else:
            # Do not flatten conditionals, random/recipient scopes or macros:
            # the sum of their branches is not a guaranteed standalone reward.
            result.review.add(key or "unparsed_effect")
    return result


def _has_action(entries: list[Entry], scripts: dict[str, list[Entry]], stack=()) -> bool:
    for entry in entries:
        key = entry.key
        if key in IGNORED_CONTEXTS or key in CONDITION_CONTEXTS:
            continue
        if key in RESOURCE_UNITS or key in SUBSTANTIVE_EFFECTS or key == "add_equipment_to_stockpile":
            return True
        if key in {"add_to_variable", "subtract_from_variable"} and isinstance(entry.value, list):
            variable, _ = _variable_value(entry.value)
            if variable == TREASURY_VARIABLE:
                return True
        if key in scripts and key not in stack and _has_action(scripts[key], scripts, stack + (key,)):
            return True
        if isinstance(entry.value, list) and _has_action(entry.value, scripts, stack):
            return True
    return False


def _has_opaque_state_change(entries, scripts, stack=()) -> bool:
    for entry in entries:
        key = entry.key
        if key in IGNORED_CONTEXTS or key in CONDITION_CONTEXTS:
            continue
        if key in STATE_VARIABLE_EFFECTS and isinstance(entry.value, list):
            variable, _ = _variable_value(entry.value)
            if variable != LEDGER_VARIABLE:
                return True
        if key in scripts and key not in stack:
            if _has_opaque_state_change(scripts[key], scripts, stack + (key,)):
                return True
        if isinstance(entry.value, list) and _has_opaque_state_change(entry.value, scripts, stack):
            return True
    return False


def _consumer_index(sources, scripts):
    focuses: set[str] = set()
    flags: set[str] = set()
    state_consumers: set[str] = set()
    triggers: dict[str, list[Entry]] = {}
    units: list[tuple[list[Entry], bool]] = []
    for path, entries in sources:
        if "scripted_triggers" in path.parts:
            triggers.update({entry.key: entry.value for entry in entries if isinstance(entry.value, list)})
        else:
            native_access = "decisions" in path.parts or "events" in path.parts
            units.append((entries, native_access))

    def inspect(entries, meaningful, opaque_state=False, visited=()):
        for entry in _walk(entries):
            if entry.key == "has_completed_focus" and isinstance(entry.value, str):
                if meaningful:
                    focuses.add(entry.value)
                elif opaque_state:
                    state_consumers.add(entry.value)
            if entry.key == "has_country_flag" and meaningful:
                flag = entry.value if isinstance(entry.value, str) else _scalar(entry.value, "flag")
                if flag:
                    flags.add(flag)
            if entry.key in triggers and entry.key not in visited and entry.value in ("yes", "no"):
                inspect(triggers[entry.key], meaningful, opaque_state, visited + (entry.key,))

    def inspect_sites(entries, native_access):
        for entry in entries:
            if entry.key in IGNORED_CONTEXTS or not isinstance(entry.value, list):
                continue
            if entry.key in CONDITION_CONTEXTS:
                # A marker must control a real action in its own block. An
                # unrelated reward beside a self-guard does not consume it.
                grants_access = native_access and entry.key not in {"limit", "mean_time_to_happen"}
                inspect(
                    entry.value,
                    grants_access or _has_action(entries, scripts),
                    _has_opaque_state_change(entries, scripts),
                )
            else:
                inspect_sites(entry.value, native_access)

    for entries, native_access in units:
        inspect_sites(entries, native_access)
    return focuses, flags, state_consumers


def audit(root: Path = ROOT) -> AuditReport:
    """Classify every loaded focus/shared definition and expose coverage gaps."""
    root = Path(root)
    report = AuditReport()
    parsed: dict[Path, list[Entry]] = {}
    paths = set((root / "common/national_focus").glob("*.txt"))
    for directory in CONSUMER_DIRECTORIES:
        paths.update((root / directory).rglob("*.txt"))
    for path in sorted(paths):
        try:
            parsed[path] = parse_clausewitz(path.read_text(encoding="utf-8-sig"))
        except (ValueError, UnicodeError) as error:
            report.parse_issues.append(f"{path.relative_to(root).as_posix()}: {error}")
    scripts = {
        entry.key: entry.value
        for path, entries in parsed.items()
        if "scripted_effects" in path.parts
        for entry in entries
        if isinstance(entry.value, list)
    }
    consumers = [(path, entries) for path, entries in parsed.items() if "national_focus" not in path.parts]
    external_focuses, external_flags, state_consumers = _consumer_index(consumers, scripts)
    for path, entries in parsed.items():
        if "national_focus" not in path.parts:
            continue
        for definition in _definitions(entries):
            if path.name in PREVIEW_FILES:
                report.counts["excluded_preview"] += 1
                continue
            focus_id = _scalar(definition.value, "id") or "<missing id>"
            cost = _number(_scalar(definition.value, "cost"))
            threshold = cost / 3 if cost is not None and cost >= 0 else None
            reward = _Reward()
            for entry in definition.value:
                if entry.key in {"completion_reward", "select_effect"} and isinstance(entry.value, list):
                    reward.merge(_analyse(entry.value, scripts))
            if focus_id in state_consumers:
                reward.review.add("external_state_consumer")
            if focus_id in external_focuses or reward.flags & external_flags:
                classification = "external_milestone"
            elif reward.review or threshold is None:
                classification = "semantic_review"
            elif reward.substantive:
                classification = "substantive"
            elif reward.score + 1e-9 < threshold:
                classification = "weak"
            else:
                classification = "consumable"
            if threshold is None:
                reward.review.add("focus_cost")
            report.focuses.append(FocusReward(
                path.relative_to(root).as_posix(), definition.line, focus_id, cost,
                classification, reward.score, threshold, tuple(sorted(reward.review)),
            ))
            report.counts[classification] += 1
    return report


def collect_issues(root: Path = ROOT) -> list[str]:
    """Return definite lint failures only; semantic-review cases stay visible in CLI."""
    report = audit(root)
    issues = list(report.parse_issues)
    for focus in report.focuses:
        if focus.classification == "weak":
            issues.append(
                f"{focus.path}:{focus.line}: {focus.focus_id}: weak standalone focus reward "
                f"({focus.score:.3f} editorial units < {focus.threshold:.3f}, "
                f"{focus.cost * 7:g} days); no indexed external gameplay consumer"
            )
    return issues


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--limit", type=int, default=300)
    parser.add_argument("--review", action="store_true", help="list opaque/conditional effects for manual review")
    args = parser.parse_args(argv)
    report = audit(args.root)
    print("Focus reward classifications: " + ", ".join(f"{key}={value}" for key, value in sorted(report.counts.items())))
    displayed = [item for item in report.focuses if item.classification == "weak" or (args.review and item.review_effects)]
    for item in displayed[:max(0, args.limit)]:
        details = ", ".join(item.review_effects) if item.review_effects else f"{item.score:.3f} < {item.threshold:.3f} editorial units"
        print(f"{item.path}:{item.line}: {item.focus_id}: {item.classification}: {details}")
    if len(displayed) > args.limit:
        print(f"... {len(displayed) - max(0, args.limit)} more records")
    for issue in report.parse_issues:
        print(issue)
    print("Scope: unconditional consumables only; unknown effects require semantic review. Static lint is not campaign balance or runtime proof.")
    print("Consumer index checks local native gameplay reads; reachability of scripted definitions requires semantic review.")
    return 1 if report.counts["weak"] or report.parse_issues else 0


if __name__ == "__main__":
    raise SystemExit(main())
