#!/usr/bin/env python3
"""Static semantic checks for the A-DISCORD economy/AI integration."""

from __future__ import annotations

import re
import sys
from pathlib import Path

try:
    from tools.validators.validate_adiscord_division_templates import Entry, parse_clausewitz
except ModuleNotFoundError:  # Direct ``python tools/validators/...`` invocation.
    from validate_adiscord_division_templates import Entry, parse_clausewitz


ROOT = Path(__file__).resolve().parents[2]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8-sig")


def strip_comments(text: str) -> str:
    return re.sub(r"#.*", "", text)


def block(text: str, name: str) -> str:
    match = re.search(rf"(?m)^\s*{re.escape(name)}\s*=\s*\{{", text)
    if not match:
        return ""
    start = match.start()
    opening = text.find("{", match.start())
    depth = 0
    for index in range(opening, len(text)):
        char = text[index]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start : index + 1]
    return ""


def numeric_assignments(text: str, variable: str) -> list[float]:
    pattern = rf"set_variable\s*=\s*\{{\s*var\s*=\s*{re.escape(variable)}\s+value\s*=\s*(-?\d+(?:\.\d+)?)"
    return [float(value) for value in re.findall(pattern, text)]


def scalar_assignments(text: str, key: str) -> list[float]:
    return [
        float(value)
        for value in re.findall(
            rf"\b{re.escape(key)}\s*=\s*(-?\d+(?:\.\d+)?)\b",
            text,
        )
    ]


LEGACY_CONSTRUCTION = (
    "ADISCORD_economy_construction_spending_mode",
    "ADISCORD_economy_construction_budget_change_cooldown",
    *(f"ADISCORD_economy_construction_spending_{level}" for level in range(1, 6)),
)
ASSISTANCE_IDEAS = (
    "ADISCORD_economy_ai_assistance_base",
    "ADISCORD_economy_ai_assistance_civil_war",
    "ADISCORD_economy_ai_assistance_retreat",
)


def _walk_entries(
    entries: list[Entry], ancestors: tuple[Entry, ...] = ()
):
    for entry in entries:
        yield ancestors, entry
        if isinstance(entry.value, list):
            yield from _walk_entries(entry.value, ancestors + (entry,))


def _tokens_in(entries: list[Entry]) -> list[str]:
    result: list[str] = []
    for _, entry in _walk_entries(entries):
        if entry.key:
            result.append(entry.key)
        if isinstance(entry.value, str):
            result.append(entry.value)
    return result


def _direct_scalar(entries: list[Entry], key: str) -> str | None:
    return next(
        (entry.value for entry in entries if entry.key == key and isinstance(entry.value, str)),
        None,
    )


def _definitions(texts: tuple[str, ...]) -> dict[str, Entry]:
    definitions: dict[str, Entry] = {}
    duplicates: set[str] = set()
    for text in texts:
        for entry in parse_clausewitz(text):
            if not entry.key.startswith("ADISCORD_") or not isinstance(entry.value, list):
                continue
            if entry.key in definitions:
                duplicates.add(entry.key)
            definitions[entry.key] = entry
    if duplicates:
        raise AssertionError(f"duplicate scripted definitions: {sorted(duplicates)}")
    return definitions


def reachable_script_entries(texts: tuple[str, ...], roots: tuple[str, ...]) -> dict[str, Entry]:
    """Return structurally reachable scripted definitions.

    Both scalar calls (``helper = yes``) and parameter blocks
    (``helper = { ARG = value }``) are edges.  The Clausewitz tokenizer keeps
    comments and quoted decoys out of the graph.
    """

    definitions = _definitions(texts)
    missing = sorted(set(roots) - definitions.keys())
    if missing:
        raise AssertionError(f"missing scripted roots: {missing}")
    reachable: dict[str, Entry] = {}
    pending = list(roots)
    while pending:
        name = pending.pop()
        if name in reachable:
            continue
        definition = definitions[name]
        reachable[name] = definition
        for _, candidate in _walk_entries(definition.value):
            if candidate.key not in definitions:
                continue
            if candidate.value == "yes" or isinstance(candidate.value, list):
                pending.append(candidate.key)
    return dict(sorted(reachable.items()))


def migration_contract_issues(effects: str, other_runtime: dict[str, str] | None = None) -> list[str]:
    """Validate the sole schema-12 exception to construction-policy retirement."""

    issues: list[str] = []
    definitions = _definitions((effects,))
    migration = definitions.get("ADISCORD_economy_migrate_schema")
    if migration is None:
        return ["missing unique ADISCORD_economy_migrate_schema"]
    body = migration.value
    assert isinstance(body, list)
    copy_ok = any(
        entry.key == "set_variable"
        and isinstance(entry.value, list)
        and _direct_scalar(entry.value, "var") == "ADISCORD_economy_research_spending_mode"
        and _direct_scalar(entry.value, "value") == "ADISCORD_economy_construction_spending_mode"
        for _, entry in _walk_entries(body)
    )
    if not copy_ok:
        issues.append("schema 12 lacks the exact construction-to-research copy")
    required_counts = {
        "ADISCORD_economy_construction_spending_mode": 2,
        "ADISCORD_economy_construction_budget_change_cooldown": 1,
        **{f"ADISCORD_economy_construction_spending_{level}": 1 for level in range(1, 6)},
    }
    tokens = _tokens_in(body)
    for token, count in required_counts.items():
        if tokens.count(token) != count:
            issues.append(f"migration has non-exact legacy use {token}: {tokens.count(token)}")
    for variable in LEGACY_CONSTRUCTION[:2]:
        if not any(
            entry.key == "clear_variable" and entry.value == variable
            for _, entry in _walk_entries(body)
        ):
            issues.append(f"migration does not clear {variable}")
    removed: set[str] = set()
    for _, entry in _walk_entries(body):
        if entry.key != "remove_ideas":
            continue
        if isinstance(entry.value, str):
            removed.add(entry.value)
        else:
            removed.update(value for value in _tokens_in(entry.value) if value.startswith("ADISCORD_"))
    for idea in LEGACY_CONSTRUCTION[2:]:
        if idea not in removed:
            issues.append(f"migration does not remove {idea}")
    outside_tokens: list[str] = []
    for name, definition in definitions.items():
        if name != migration.key:
            outside_tokens.extend(_tokens_in([definition]))
    for path, text in (other_runtime or {}).items():
        try:
            outside_tokens.extend(_tokens_in(parse_clausewitz(text)))
        except ValueError as error:
            issues.append(f"{path}: Clausewitz parse error: {error}")
    for token in LEGACY_CONSTRUCTION:
        if token in outside_tokens:
            issues.append(f"live construction-policy token outside migration: {token}")
    return issues


def retired_capacity_boundary_issues(sources: dict[str, str]) -> list[str]:
    """Scan the complete public/runtime boundary with exact historical exceptions."""

    historical = {
        "docs/superpowers/plans/2026-08-02-adiscord-weekly-economy-dashboard.md",
        "docs/superpowers/plans/2026-08-08-adiscord-economy-recovery.md",
        "docs/superpowers/plans/2026-08-08-adiscord-integration-and-runtime-acceptance.md",
        "docs/superpowers/specs/2026-08-08-adiscord-recovery-design.md",
        "tools/tests/test_adiscord_economy_weekly_contracts.py",
        "tools/tests/test_validate_adiscord_gui_contracts.py",
    }
    issues: list[str] = []
    forbidden = re.compile(
        "debt" + r"_capacity|debt" + r"\s+capacity|долгов\w*\s+[её]мк", re.I
    )
    effects_path = "common/scripted_effects/ADISCORD_economy_effects.txt"
    for path, text in sources.items():
        if path in historical:
            continue
        if path != effects_path:
            if forbidden.search(text):
                issues.append(f"{path}: retired debt-capacity API")
            continue
        try:
            definitions = _definitions((text,))
        except (AssertionError, ValueError) as error:
            issues.append(f"{path}: Clausewitz parse error: {error}")
            continue
        migration = definitions.get("ADISCORD_economy_migrate_schema")
        for name, definition in definitions.items():
            if definition is migration:
                for _, entry in _walk_entries(definition.value):
                    refs = [entry.key] + ([entry.value] if isinstance(entry.value, str) else [])
                    if not any(forbidden.search(ref) for ref in refs):
                        continue
                    if not (entry.key == "clear_variable" and isinstance(entry.value, str)):
                        issues.append(f"{path}:{entry.line}: capacity migration operation is not a clear")
            elif forbidden.search(" ".join(_tokens_in([definition]))):
                issues.append(f"{path}:{definition.line}: retired debt-capacity API")
    return issues


def _operand_values(entry: Entry) -> set[str]:
    if isinstance(entry.value, str):
        return {entry.value}
    return {token for token in _tokens_in(entry.value) if token.startswith("ADISCORD_")}


def _branch_condition_tokens(ancestors: tuple[Entry, ...]) -> list[str]:
    tokens: list[str] = []
    for ancestor in ancestors:
        if ancestor.key not in {"if", "else_if"} or not isinstance(ancestor.value, list):
            continue
        for entry in ancestor.value:
            if entry.key == "limit" and isinstance(entry.value, list):
                tokens.extend(_tokens_in(entry.value))
    return tokens


def _check_variable_signatures(entries: list[Entry], variable: str) -> list[tuple[str | None, str | None]]:
    return [
        (_direct_scalar(entry.value, "value"), _direct_scalar(entry.value, "compare"))
        for _, entry in _walk_entries(entries)
        if entry.key == "check_variable"
        and isinstance(entry.value, list)
        and _direct_scalar(entry.value, "var") == variable
    ]


def _atom_signature(entry: Entry) -> tuple:
    value = (
        entry.value
        if isinstance(entry.value, str)
        else tuple(_atom_signature(child) for child in entry.value)
    )
    return entry.key, value


def _entries_signature(entries: list[Entry]) -> tuple:
    return tuple(_atom_signature(entry) for entry in entries)


def _fixture_body_signature(source: str) -> tuple:
    parsed = parse_clausewitz(f"ADISCORD_contract_fixture = {{ {source} }}")
    assert len(parsed) == 1 and isinstance(parsed[0].value, list)
    return _entries_signature(parsed[0].value)


def _matches_exact_body(entries: list[Entry], source: str) -> bool:
    return _entries_signature(entries) == _fixture_body_signature(source)


def _numeric_check_constraint(
    entry: Entry, positive: bool
) -> tuple[str, float, str] | None:
    if entry.key != "check_variable" or not isinstance(entry.value, list):
        return None
    variable = _direct_scalar(entry.value, "var")
    value = _direct_scalar(entry.value, "value")
    compare = _direct_scalar(entry.value, "compare")
    if variable is None or value is None or compare is None:
        return None
    try:
        numeric_value = float(value)
    except ValueError:
        return None
    if not positive:
        compare = {
            "equals": "not_equals",
            "not_equals": "equals",
            "greater_than": "less_than_or_equals",
            "greater_than_or_equals": "less_than",
            "less_than": "greater_than_or_equals",
            "less_than_or_equals": "greater_than",
        }.get(compare, "")
    return variable, numeric_value, compare


def _boolean_path_is_satisfiable(path: tuple[tuple[Entry, bool], ...]) -> bool:
    polarities: dict[tuple, set[bool]] = {}
    boolean_values: dict[str, set[bool]] = {}
    numeric: dict[str, list[tuple[float, str]]] = {}
    for entry, positive in path:
        polarities.setdefault(_atom_signature(entry), set()).add(positive)
        if isinstance(entry.value, str) and entry.value in {"yes", "no"}:
            truth = entry.value == "yes"
            boolean_values.setdefault(entry.key, set()).add(
                truth if positive else not truth
            )
        constraint = _numeric_check_constraint(entry, positive)
        if constraint is not None:
            variable, value, compare = constraint
            numeric.setdefault(variable, []).append((value, compare))
    if any(values == {True, False} for values in polarities.values()):
        return False
    if any(values == {True, False} for values in boolean_values.values()):
        return False
    for constraints in numeric.values():
        lower: tuple[float, bool] | None = None
        upper: tuple[float, bool] | None = None
        equals: set[float] = set()
        excluded: set[float] = set()
        for value, compare in constraints:
            if compare == "equals":
                equals.add(value)
            elif compare == "not_equals":
                excluded.add(value)
            elif compare in {"greater_than", "greater_than_or_equals"}:
                candidate = (value, compare == "greater_than_or_equals")
                if lower is None or candidate[0] > lower[0] or (
                    candidate[0] == lower[0] and not candidate[1]
                ):
                    lower = candidate
            elif compare in {"less_than", "less_than_or_equals"}:
                candidate = (value, compare == "less_than_or_equals")
                if upper is None or candidate[0] < upper[0] or (
                    candidate[0] == upper[0] and not candidate[1]
                ):
                    upper = candidate
        if len(equals) > 1:
            return False
        if equals:
            exact = next(iter(equals))
            if exact in excluded:
                return False
            if lower is not None and (
                exact < lower[0] or (exact == lower[0] and not lower[1])
            ):
                return False
            if upper is not None and (
                exact > upper[0] or (exact == upper[0] and not upper[1])
            ):
                return False
        if lower is not None and upper is not None and (
            lower[0] > upper[0]
            or (lower[0] == upper[0] and (not lower[1] or not upper[1]))
        ):
            return False
    return True


def _and_boolean_paths(
    alternatives: list[list[tuple[tuple[Entry, bool], ...]]],
) -> list[tuple[tuple[Entry, bool], ...]]:
    paths: list[tuple[tuple[Entry, bool], ...]] = [()]
    for child_paths in alternatives:
        merged: list[tuple[tuple[Entry, bool], ...]] = []
        for prefix in paths:
            for suffix in child_paths:
                candidate = prefix + suffix
                if _boolean_path_is_satisfiable(candidate):
                    merged.append(candidate)
        paths = merged
        if not paths:
            break
    return paths


def _boolean_entry_paths(
    entry: Entry, positive: bool
) -> list[tuple[tuple[Entry, bool], ...]]:
    if entry.key == "NOT" and isinstance(entry.value, list):
        return _boolean_entries_paths(entry.value, not positive)
    if entry.key in {"AND", "OR"} and isinstance(entry.value, list):
        alternatives = [
            _boolean_entry_paths(child, positive) for child in entry.value
        ]
        is_conjunction = (entry.key == "AND") == positive
        return _and_boolean_paths(alternatives) if is_conjunction else [
            path for child_paths in alternatives for path in child_paths
        ]
    if entry.key == "always" and isinstance(entry.value, str):
        truth = entry.value == "yes"
        return [()] if truth == positive else []
    return [((entry, positive),)]


def _boolean_entries_paths(
    entries: list[Entry], positive: bool = True
) -> list[tuple[tuple[Entry, bool], ...]]:
    alternatives = [_boolean_entry_paths(entry, positive) for entry in entries]
    if positive:
        return _and_boolean_paths(alternatives)
    return [path for child_paths in alternatives for path in child_paths]


def _condition_requires_entry(
    entries: list[Entry], matcher, positive: bool = True
) -> bool:
    matches = [entry for _, entry in _walk_entries(entries) if matcher(entry)]
    if len(matches) != 1:
        return False
    required = matches[0]
    paths = _boolean_entries_paths(entries)
    return bool(paths) and all(
        any(entry is required and polarity == positive for entry, polarity in path)
        for path in paths
    )


def _condition_is_exact_entry(entries: list[Entry], matcher) -> bool:
    matches = [entry for _, entry in _walk_entries(entries) if matcher(entry)]
    if len(matches) != 1:
        return False
    required = matches[0]
    paths = _boolean_entries_paths(entries)
    return bool(paths) and all(
        path
        and all(entry is required and positive for entry, positive in path)
        for path in paths
    )


def _check_matches(entry: Entry, variable: str, value: str, compare: str) -> bool:
    if entry.key != "check_variable" or not isinstance(entry.value, list):
        return False
    if _direct_scalar(entry.value, "var") != variable:
        return False
    actual_value = _direct_scalar(entry.value, "value")
    if _direct_scalar(entry.value, "compare") != compare or actual_value is None:
        return False
    if value.replace(".", "", 1).isdigit():
        try:
            return float(actual_value) == float(value)
        except ValueError:
            return False
    return actual_value == value


def _exact_check(entries: list[Entry], variable: str, value: str, compare: str) -> bool:
    return _condition_requires_entry(
        entries,
        lambda entry: _check_matches(entry, variable, value, compare),
    )


def _exact_scalar(
    entries: list[Entry], key: str, value: str, positive: bool = True
) -> bool:
    return _condition_requires_entry(
        entries,
        lambda entry: entry.key == key and entry.value == value,
        positive,
    )


def _direct_variable_operation(
    entries: list[Entry], operation: str, variable: str, value: str | None = None
) -> list[Entry]:
    matches = [
        entry
        for entry in entries
        if entry.key == operation
        and isinstance(entry.value, list)
        and _direct_scalar(entry.value, "var") == variable
    ]
    if value is not None:
        matches = [entry for entry in matches if _direct_scalar(entry.value, "value") == value]
    return matches


def _is_exact_variable_write(
    entry: Entry, operation: str, variable: str, value: str
) -> bool:
    return (
        entry.key == operation
        and isinstance(entry.value, list)
        and len(entry.value) == 2
        and sorted(child.key for child in entry.value) == ["value", "var"]
        and _direct_scalar(entry.value, "var") == variable
        and _direct_scalar(entry.value, "value") == value
    )


def _is_exact_check_entry(
    entry: Entry, variable: str, value: str, compare: str
) -> bool:
    return (
        entry.key == "check_variable"
        and isinstance(entry.value, list)
        and len(entry.value) == 3
        and sorted(child.key for child in entry.value) == ["compare", "value", "var"]
        and _check_matches(entry, variable, value, compare)
    )


def _direct_limit(branch: Entry) -> list[Entry] | None:
    if not isinstance(branch.value, list):
        return None
    limits = [
        entry.value
        for entry in branch.value
        if entry.key == "limit" and isinstance(entry.value, list)
    ]
    return limits[0] if len(limits) == 1 else None


def _limit_is_satisfiable(entries: list[Entry]) -> bool:
    return bool(_boolean_entries_paths(entries))


def _direct_scalar_comparisons(entries: list[Entry]) -> list[tuple[str, str, str]]:
    """Return Clausewitz ``lhs <op> rhs`` triples owned by this exact block."""

    comparisons: list[tuple[str, str, str]] = []
    index = 0
    while index + 2 < len(entries):
        left, operator, right = entries[index : index + 3]
        if (
            left.key == operator.key == right.key == ""
            and isinstance(left.value, str)
            and isinstance(operator.value, str)
            and isinstance(right.value, str)
            and operator.value in {"<", "<=", "=", "==", ">=", ">"}
        ):
            comparisons.append((left.value, operator.value, right.value))
            index += 3
            continue
        index += 1
    return comparisons


def _requires_direct_scalar_comparison(
    entries: list[Entry], left: str, operator: str, right: str
) -> bool:
    return _direct_scalar_comparisons(entries).count((left, operator, right)) == 1


def _conditional_else_pairs(entries: list[Entry]):
    for index, branch in enumerate(entries):
        if branch.key in {"if", "else_if"} and isinstance(branch.value, list):
            following = entries[index + 1] if index + 1 < len(entries) else None
            paired_else = following if following and following.key == "else" and isinstance(following.value, list) else None
            yield branch, paired_else
        if isinstance(branch.value, list):
            yield from _conditional_else_pairs(branch.value)


def _unique_definition(text: str, name: str) -> Entry | None:
    matches = [entry for entry in parse_clausewitz(text) if entry.key == name]
    return matches[0] if len(matches) == 1 else None


def _direct_operation_value(
    entries: list[Entry], operation: str, variable: str
) -> list[str]:
    return [
        value
        for entry in entries
        if entry.key == operation
        and isinstance(entry.value, list)
        and _direct_scalar(entry.value, "var") == variable
        and (value := _direct_scalar(entry.value, "value")) is not None
    ]


def _branch_direct_call(branch: Entry) -> str | None:
    if not isinstance(branch.value, list):
        return None
    calls = [
        entry.key
        for entry in branch.value
        if entry.key.startswith("ADISCORD_") and entry.value == "yes"
    ]
    return calls[0] if len(calls) == 1 else None


def _direct_decision_branches(entries: list[Entry]) -> list[Entry]:
    return [entry for entry in entries if entry.key in {"if", "else_if"}]


def _policy_branch_limit(branch: Entry) -> list[Entry]:
    limit = _direct_limit(branch)
    return limit if limit is not None else []


def ai_policy_contract_issues(effects_text: str) -> list[str]:
    """Validate one ordered, reserve-aware economy action chain for the AI."""

    issues: list[str] = []
    policy = _unique_definition(effects_text, "ADISCORD_economy_ai_monthly_policy")
    if policy is None or not isinstance(policy.value, list):
        return ["missing unique AI monthly policy"]
    if any(token in block(effects_text, policy.key) for token in LEGACY_CONSTRUCTION):
        issues.append("AI policy references retired construction-policy state")

    if [entry.key for entry in policy.value] != ["if"]:
        return issues + ["AI policy contains an action outside its reserve owner"]
    owners = [entry for entry in policy.value if entry.key == "if"]
    if len(owners) != 1 or not isinstance(owners[0].value, list):
        return issues + ["AI policy lacks one direct reserve owner"]
    owner = owners[0]
    owner_limit = _direct_limit(owner)
    if owner_limit is None or not _limit_is_satisfiable(owner_limit):
        return issues + ["AI policy reserve owner is missing or dead"]
    if not _exact_scalar(owner_limit, "is_ai", "yes"):
        issues.append("AI policy reserve owner is not AI-only")
    if not _requires_direct_scalar_comparison(
        owner_limit, "has_political_power", ">", "50"
    ):
        issues.append("AI policy lacks the exact 50 PP story reserve")
    if not _matches_exact_body(owner_limit, "is_ai = yes has_political_power > 50"):
        issues.append("AI policy reserve predicate is not the exact AI-only >50 PP gate")

    state_chain = [
        entry for entry in owner.value if entry.key in {"if", "else_if", "else"}
    ]
    if [entry.key for entry in state_chain] != ["if", "else_if", "else_if", "else"]:
        return issues + ["AI fiscal states are not one exclusive four-way chain"]
    if [entry.key for entry in owner.value] != [
        "limit", "if", "else_if", "else_if", "else"
    ]:
        issues.append("AI reserve owner contains an action outside its fiscal-state chain")
    state_names = ("crisis", "stressed", "recovery", "healthy")
    expected_state_owner = {
        "crisis": "ADISCORD_economy_ai_is_crisis = yes",
        "stressed": "ADISCORD_economy_ai_is_stressed = yes",
        "recovery": "ADISCORD_economy_ai_is_recovery = yes",
    }
    state_actions: dict[str, list[tuple[str, list[Entry]]]] = {}
    for state_name, state in zip(state_names, state_chain):
        assert isinstance(state.value, list)
        if state_name in expected_state_owner:
            state_limit = _direct_limit(state)
            if state_limit is None or not _matches_exact_body(
                state_limit, expected_state_owner[state_name]
            ):
                issues.append(f"{state_name}: fiscal-state owner predicate is not exact")
        decisions = _direct_decision_branches(state.value)
        keys = [entry.key for entry in decisions]
        if keys and keys != ["if", *("else_if" for _ in keys[1:])]:
            issues.append(f"{state_name}: policy actions are not an exclusive chain")
        expected_state_keys = (["limit"] if state_name != "healthy" else []) + keys
        if [entry.key for entry in state.value] != expected_state_keys:
            issues.append(f"{state_name}: action escapes the exclusive policy chain")
        actions: list[tuple[str, list[Entry]]] = []
        for decision in decisions:
            call = _branch_direct_call(decision)
            if call is None:
                issues.append(f"{state_name}: decision does not own exactly one action")
                continue
            if [entry.key for entry in decision.value] != ["limit", call]:
                issues.append(f"{state_name}: decision contains a sibling action")
            condition = _policy_branch_limit(decision)
            if not condition or not _limit_is_satisfiable(condition):
                issues.append(f"{state_name}: action owner is missing or dead")
            actions.append((call, condition))
        state_actions[state_name] = actions

    expected_action_conditions: dict[
        tuple[str, str], tuple[str, ...]
    ] = {
        ("crisis", "ADISCORD_economy_increase_tax_burden"): (
            "check_variable = { var = ADISCORD_economy_monthly_balance value = 0 compare = less_than } ADISCORD_economy_can_increase_tax_burden = yes",
        ),
        ("crisis", "ADISCORD_economy_decrease_social_spending"): (
            "check_variable = { var = ADISCORD_economy_monthly_balance value = 0 compare = less_than } check_variable = { var = ADISCORD_economy_social_spending_mode value = 2 compare = greater_than } ADISCORD_economy_can_decrease_social_spending = yes",
        ),
        ("crisis", "ADISCORD_economy_decrease_army_spending"): (
            "has_war = no check_variable = { var = ADISCORD_economy_monthly_balance value = 0 compare = less_than } ADISCORD_economy_can_decrease_army_spending = yes",
        ),
        ("crisis", "ADISCORD_economy_decrease_research_spending"): (
            "check_variable = { var = ADISCORD_economy_monthly_balance value = 0 compare = less_than } ADISCORD_economy_can_decrease_research_spending = yes",
        ),
        ("stressed", "ADISCORD_economy_increase_tax_burden"): (
            "check_variable = { var = ADISCORD_economy_monthly_balance value = 0 compare = less_than } ADISCORD_economy_can_increase_tax_burden = yes",
        ),
        ("stressed", "ADISCORD_economy_decrease_social_spending"): (
            "check_variable = { var = ADISCORD_economy_monthly_balance value = 0 compare = less_than } check_variable = { var = ADISCORD_economy_social_spending_mode value = 3 compare = greater_than } ADISCORD_economy_can_decrease_social_spending = yes",
        ),
        ("stressed", "ADISCORD_economy_decrease_army_spending"): (
            "has_war = no check_variable = { var = ADISCORD_economy_fiscal_stress value = 55 compare = greater_than_or_equals } ADISCORD_economy_can_decrease_army_spending = yes",
        ),
        ("stressed", "ADISCORD_economy_decrease_research_spending"): (
            "check_variable = { var = ADISCORD_economy_monthly_balance value = 0 compare = less_than } ADISCORD_economy_can_decrease_research_spending = yes",
        ),
        ("recovery", "ADISCORD_economy_decrease_research_spending"): (
            "check_variable = { var = ADISCORD_economy_research_spending_mode value = 3 compare = greater_than } ADISCORD_economy_can_decrease_research_spending = yes",
        ),
        ("recovery", "ADISCORD_economy_increase_research_spending"): (
            "check_variable = { var = ADISCORD_economy_research_spending_mode value = 3 compare = less_than } ADISCORD_economy_can_increase_research_spending = yes",
        ),
        ("healthy", "ADISCORD_economy_decrease_research_spending"): (
            "check_variable = { var = ADISCORD_economy_research_spending_mode value = 4 compare = greater_than } ADISCORD_economy_can_decrease_research_spending = yes",
            "check_variable = { var = ADISCORD_economy_research_spending_mode value = 3 compare = greater_than } OR = { check_variable = { var = ADISCORD_economy_monthly_balance value = 0 compare = less_than_or_equals } check_variable = { var = ADISCORD_economy_debt_state value = 0 compare = greater_than } check_variable = { var = ADISCORD_economy_interest_share_income value = 10 compare = greater_than_or_equals } } ADISCORD_economy_can_decrease_research_spending = yes",
        ),
        ("healthy", "ADISCORD_economy_increase_research_spending"): (
            "check_variable = { var = ADISCORD_economy_research_spending_mode value = 3 compare = less_than } ADISCORD_economy_can_increase_research_spending = yes",
            "check_variable = { var = ADISCORD_economy_research_spending_mode value = 3 compare = equals } check_variable = { var = ADISCORD_economy_monthly_balance value = 0 compare = greater_than } check_variable = { var = ADISCORD_economy_debt_state value = 0 compare = equals } check_variable = { var = ADISCORD_economy_interest_share_income value = 10 compare = less_than } ADISCORD_economy_can_increase_research_spending = yes",
        ),
    }
    for (state_name, action), expected_sources in expected_action_conditions.items():
        found_conditions = [
            condition
            for found_action, condition in state_actions.get(state_name, [])
            if found_action == action
        ]
        expected_signatures = [
            _fixture_body_signature(source) for source in expected_sources
        ]
        if [
            _entries_signature(condition) for condition in found_conditions
        ] != expected_signatures:
            issues.append(f"{state_name}: {action} predicate is not exact")

    def action_positions(state: str) -> dict[str, list[int]]:
        result: dict[str, list[int]] = {}
        for index, (action, _) in enumerate(state_actions.get(state, [])):
            result.setdefault(action, []).append(index)
        return result

    for state in ("crisis", "stressed"):
        positions = action_positions(state)
        ordered = (
            "ADISCORD_economy_increase_tax_burden",
            "ADISCORD_economy_decrease_social_spending",
            "ADISCORD_economy_decrease_army_spending",
            "ADISCORD_economy_decrease_research_spending",
        )
        if any(len(positions.get(action, [])) != 1 for action in ordered):
            issues.append(f"{state}: missing one ordered fiscal recovery action")
        else:
            indices = [positions[action][0] for action in ordered]
            if indices != sorted(indices):
                issues.append(f"{state}: research is cut before tax/nonessential spending")

    def matching_conditions(state: str, action: str) -> list[list[Entry]]:
        return [condition for call, condition in state_actions.get(state, []) if call == action]

    recovery_up = matching_conditions(
        "recovery", "ADISCORD_economy_increase_research_spending"
    )
    recovery_down = matching_conditions(
        "recovery", "ADISCORD_economy_decrease_research_spending"
    )
    if len(recovery_up) != 1 or not _exact_check(
        recovery_up[0], "ADISCORD_economy_research_spending_mode", "3", "less_than"
    ):
        issues.append("recovery does not restore research toward level 3 from below")
    if len(recovery_down) != 1 or not _exact_check(
        recovery_down[0], "ADISCORD_economy_research_spending_mode", "3", "greater_than"
    ):
        issues.append("recovery does not restore research toward level 3 from above")

    healthy_up = matching_conditions(
        "healthy", "ADISCORD_economy_increase_research_spending"
    )
    healthy_down = matching_conditions(
        "healthy", "ADISCORD_economy_decrease_research_spending"
    )
    level_three = [
        condition
        for condition in healthy_up
        if _exact_check(
            condition, "ADISCORD_economy_research_spending_mode", "3", "equals"
        )
    ]
    toward_three = [
        condition
        for condition in healthy_up
        if _exact_check(
            condition, "ADISCORD_economy_research_spending_mode", "3", "less_than"
        )
    ]
    if len(toward_three) != 1:
        issues.append("healthy AI does not restore research toward level 3")
    if len(level_three) != 1 or not all(
        (
            _exact_check(level_three[0], "ADISCORD_economy_monthly_balance", "0", "greater_than"),
            _exact_check(level_three[0], "ADISCORD_economy_debt_state", "0", "equals"),
            _exact_check(level_three[0], "ADISCORD_economy_interest_share_income", "10", "less_than"),
        )
    ):
        issues.append("research level 4 lacks real surplus and safe debt/interest gates")
    if len(healthy_down) != 2:
        issues.append("healthy AI lacks bounded research fallback toward level 3/4")
    for condition in healthy_up:
        signatures = _check_variable_signatures(
            condition, "ADISCORD_economy_research_spending_mode"
        )
        if not signatures or any(
            compare not in {"equals", "less_than"}
            or (compare == "equals" and value != "3")
            or (compare == "less_than" and value != "3")
            for value, compare in signatures
        ):
            issues.append("AI can automatically raise research to level 5")
    return issues


def ai_assistance_contract_issues(
    ideas_text: str, effects_text: str, triggers_text: str = ""
) -> list[str]:
    """Validate exact incremental assistance, signature ownership, and reversibility."""

    issues: list[str] = []
    idea_ast = parse_clausewitz(ideas_text)
    effect_ast = parse_clausewitz(effects_text)
    expected = {
        ASSISTANCE_IDEAS[0]: (
            ("ADISCORD_economy_overall_income_factor", "0.05"),
            ("industrial_capacity_factory", "0.05"),
        ),
        ASSISTANCE_IDEAS[1]: (("supply_consumption_factor", "-0.10"),),
        ASSISTANCE_IDEAS[2]: (("army_defence_factor", "0.05"),),
    }
    all_prefixed_defs = [
        entry
        for _, entry in _walk_entries(idea_ast)
        if entry.key.startswith("ADISCORD_economy_ai_assistance_")
    ]
    all_assistance_defs = [
        entry
        for _, entry in _walk_entries(idea_ast)
        if entry.key in ASSISTANCE_IDEAS
    ]
    for name, expected_modifiers in expected.items():
        matches = [entry for entry in all_assistance_defs if entry.key == name]
        if len(matches) != 1 or not isinstance(matches[0].value, list):
            issues.append(f"expected one assistance idea {name}")
            continue
        idea = matches[0]
        if [entry.key for entry in idea.value] != [
            "allowed", "allowed_civil_war", "removal_cost", "modifier"
        ]:
            issues.append(f"{name}: idea body contains a non-allowlisted gameplay field")
        allowed = next(
            (
                entry for entry in idea.value
                if entry.key == "allowed" and isinstance(entry.value, list)
            ),
            None,
        )
        civil_war = next(
            (
                entry for entry in idea.value
                if entry.key == "allowed_civil_war" and isinstance(entry.value, list)
            ),
            None,
        )
        if allowed is None or not _matches_exact_body(allowed.value, "always = no"):
            issues.append(f"{name}: allowed gate is not exact")
        if civil_war is None or not _matches_exact_body(
            civil_war.value, "always = yes"
        ):
            issues.append(f"{name}: civil-war persistence gate is not exact")
        if [
            entry.value for entry in idea.value
            if entry.key == "removal_cost" and isinstance(entry.value, str)
        ] != ["-1"]:
            issues.append(f"{name}: removal cost is not exact")
        modifiers = [
            entry
            for entry in idea.value
            if entry.key == "modifier" and isinstance(entry.value, list)
        ]
        if len(modifiers) != 1:
            issues.append(f"{name}: missing unique modifier block")
            continue
        exact_found = tuple(
            (entry.key, entry.value)
            for entry in modifiers[0].value
            if isinstance(entry.value, str)
        )
        if len(modifiers[0].value) != len(exact_found) or exact_found != expected_modifiers:
            issues.append(f"{name}: modifier stack is not the exact bounded increment")
        idea_tokens = set(_tokens_in(idea.value))
        for forbidden_token in (
            "on_add",
            "on_remove",
            "equipment_bonus",
            "add_political_power",
            "add_equipment_to_stockpile",
            "army_attack_factor",
            "breakthrough_factor",
            "add_manpower",
            "add_stability",
            "set_technology",
            "add_tech",
        ):
            if forbidden_token in idea_tokens:
                issues.append(f"{name}: idea body uses prohibited {forbidden_token}")
    if len(all_prefixed_defs) != len(ASSISTANCE_IDEAS):
        issues.append("assistance has a duplicate or renamed stacking idea")

    refreshes = [
        entry
        for entry in effect_ast
        if entry.key == "ADISCORD_economy_refresh_ai_assistance"
    ]
    if len(refreshes) != 1 or not isinstance(refreshes[0].value, list):
        return issues + ["missing unique AI-assistance refresh"]
    refresh_definition = refreshes[0]
    direct = refresh_definition.value
    assistance_references: list[tuple[str, str, set[str]]] = []
    for definition in effect_ast:
        if not isinstance(definition.value, list):
            continue
        for _, entry in _walk_entries(definition.value):
            if entry.key not in {"add_ideas", "remove_ideas"}:
                continue
            values = _operand_values(entry)
            if values & set(ASSISTANCE_IDEAS):
                assistance_references.append((definition.key, entry.key, values))
    if any(
        definition_name != refresh_definition.key
        for definition_name, _, _ in assistance_references
    ):
        issues.append("an effect outside the assistance refresh owns an assistance idea")
    signature = "ADISCORD_economy_ai_assistance_signature_temp"
    stored_signature = "ADISCORD_economy_ai_assistance_signature"
    if _direct_operation_value(direct, "set_temp_variable", signature) != ["0"]:
        issues.append("assistance signature lacks a safe zero default")
    tier_owners = []
    for branch in direct:
        if branch.key != "if" or not isinstance(branch.value, list):
            continue
        limit = _direct_limit(branch)
        if limit is not None and _exact_scalar(
            limit, "has_variable", "ADISCORD_economy_simulation_tier"
        ):
            tier_owners.append(branch)
    if len(tier_owners) != 1 or _direct_operation_value(
        tier_owners[0].value, "set_temp_variable", signature
    ) != ["ADISCORD_economy_simulation_tier"]:
        issues.append("assistance signature does not safely own the exact simulation tier")

    signature_inputs = (
        ("is_ai", "yes", "10"),
        ("has_global_flag", "ADISCORD_vorkerland_collapse_wars_started", "100"),
        ("has_global_flag", "ADISCORD_vorkerland_collapse_finished", "150"),
        ("has_country_flag", "ADISCORD_vorkerland_conflict_spirits_finalized", "200"),
        ("has_war", "yes", "400"),
    )
    for key, value, weight in signature_inputs:
        owners = []
        for branch in direct:
            if branch.key != "if" or not isinstance(branch.value, list):
                continue
            limit = _direct_limit(branch)
            if limit is not None and _exact_scalar(limit, key, value):
                owners.append(branch)
        if len(owners) != 1 or _direct_operation_value(
            owners[0].value, "add_to_temp_variable", signature
        ) != [weight]:
            issues.append(f"assistance signature lacks exact input {key}={value}")
    surrender_owners = []
    for branch in direct:
        if branch.key != "if" or not isinstance(branch.value, list):
            continue
        limit = _direct_limit(branch)
        if limit is not None and _requires_direct_scalar_comparison(
            limit, "surrender_progress", ">", "0.35"
        ):
            surrender_owners.append(branch)
    if len(surrender_owners) != 1 or _direct_operation_value(
        surrender_owners[0].value, "add_to_temp_variable", signature
    ) != ["800"]:
        issues.append("assistance signature lacks the exact surrender threshold bit")

    change_owners = [
        branch
        for branch in direct
        if branch.key == "if"
        and isinstance(branch.value, list)
        and any(
            entry.key == "remove_ideas" for entry in branch.value
        )
    ]
    if len(change_owners) != 1:
        return issues + ["assistance lacks one signature-change owner"]
    owner = change_owners[0]
    owner_limit = _direct_limit(owner)
    if owner_limit is None or not _limit_is_satisfiable(owner_limit):
        issues.append("assistance signature-change owner is missing or dead")
    elif not _matches_exact_body(
        owner_limit,
        "OR = { NOT = { has_variable = ADISCORD_economy_ai_assistance_signature } "
        "check_variable = { var = ADISCORD_economy_ai_assistance_signature "
        "value = ADISCORD_economy_ai_assistance_signature_temp compare = not_equals } }",
    ):
        issues.append("assistance signature-change owner is not the exact two-arm positive OR")
    assert isinstance(owner.value, list)
    if [entry.key for entry in owner.value] != [
        "limit",
        "remove_ideas", "remove_ideas", "remove_ideas",
        "if", "if", "if",
        "ADISCORD_economy_refresh_ai_assistance_income_cache",
        "set_variable",
    ]:
        issues.append("assistance signature-change body contains an unowned operation")
    removals = [
        (index, _operand_values(entry))
        for index, entry in enumerate(owner.value)
        if entry.key == "remove_ideas"
    ]
    additions = [
        (index, _operand_values(entry), ancestors)
        for ancestors, entry in _walk_entries(owner.value)
        if entry.key == "add_ideas"
        for index in [owner.value.index(ancestors[0]) if ancestors else -1]
    ]
    removed = set().union(*(values for _, values in removals)) if removals else set()
    added = set().union(*(values for _, values, _ in additions)) if additions else set()
    exact_removal_values = [values for _, values in removals]
    if exact_removal_values != [{idea} for idea in ASSISTANCE_IDEAS]:
        issues.append("assistance removal allowlist is not the exact three ideas")
    exact_addition_values = [values for _, values, _ in additions]
    if exact_addition_values != [{idea} for idea in ASSISTANCE_IDEAS]:
        issues.append("assistance add allowlist is not the exact three ideas")
    for idea in ASSISTANCE_IDEAS:
        if idea not in removed:
            issues.append(f"{idea}: no remove-first path")
        if idea not in added:
            issues.append(f"{idea}: no bounded add path")
    if additions and removals and max(index for index, _ in removals) >= min(
        index for index, _, _ in additions
    ):
        issues.append("assistance additions precede complete removal")
    all_adds = [
        entry for _, entry in _walk_entries(direct) if entry.key == "add_ideas"
    ]
    owner_adds = [
        entry for _, entry in _walk_entries(owner.value) if entry.key == "add_ideas"
    ]
    if len(all_adds) != len(owner_adds):
        issues.append("assistance addition escapes the signature-change owner")
    trigger_for_idea = {
        ASSISTANCE_IDEAS[0]: "ADISCORD_economy_ai_assistance_is_eligible",
        ASSISTANCE_IDEAS[1]: "ADISCORD_economy_ai_assistance_civil_war_active",
        ASSISTANCE_IDEAS[2]: "ADISCORD_economy_ai_assistance_retreat_active",
    }
    for _, values, ancestors in additions:
        for idea in values & set(ASSISTANCE_IDEAS):
            branch = next(
                (
                    ancestor
                    for ancestor in reversed(ancestors)
                    if ancestor.key in {"if", "else_if"}
                ),
                None,
            )
            condition = _direct_limit(branch) if branch is not None else None
            if condition is None or not _exact_scalar(
                condition, trigger_for_idea[idea], "yes"
            ):
                issues.append(f"{idea}: addition uses the wrong eligibility trigger")
    owner_calls = [
        entry.key
        for entry in owner.value
        if entry.key.startswith("ADISCORD_") and entry.value == "yes"
    ]
    if owner_calls != ["ADISCORD_economy_refresh_ai_assistance_income_cache"]:
        issues.append("assistance does not refresh its economy-owned input exactly once")
    stored_writes = _direct_operation_value(
        owner.value, "set_variable", stored_signature
    )
    if stored_writes != [signature] or not owner.value or owner.value[-1].key != "set_variable":
        issues.append("assistance signature is not published last")

    if triggers_text:
        trigger_definitions = _definitions((triggers_text,))
        eligible = trigger_definitions.get("ADISCORD_economy_ai_assistance_is_eligible")
        civil = trigger_definitions.get("ADISCORD_economy_ai_assistance_civil_war_active")
        retreat = trigger_definitions.get("ADISCORD_economy_ai_assistance_retreat_active")
        monthly = trigger_definitions.get("ADISCORD_economy_ai_assistance_needs_monthly_evaluation")
        if eligible is None or not isinstance(eligible.value, list) or not all(
            (
                _exact_scalar(eligible.value, "is_ai", "yes"),
                _exact_check(eligible.value, "ADISCORD_economy_simulation_tier", "1", "greater_than_or_equals"),
                _exact_check(eligible.value, "ADISCORD_economy_simulation_tier", "2", "less_than_or_equals"),
            )
        ):
            issues.append("base assistance eligibility is not AI-only tier 1-2")
        if civil is None or not isinstance(civil.value, list) or not all(
            (
                _exact_scalar(civil.value, "ADISCORD_economy_ai_assistance_is_eligible", "yes"),
                _exact_scalar(civil.value, "has_global_flag", "ADISCORD_vorkerland_collapse_wars_started"),
                _exact_scalar(civil.value, "has_global_flag", "ADISCORD_vorkerland_collapse_finished", False),
                _exact_scalar(civil.value, "has_country_flag", "ADISCORD_vorkerland_conflict_spirits_finalized"),
                _exact_scalar(civil.value, "has_war", "yes"),
            )
        ):
            issues.append("civil-war assistance lacks the exact live collapse/war gate")
        if retreat is None or not isinstance(retreat.value, list) or not all(
            (
                _exact_scalar(retreat.value, "ADISCORD_economy_ai_assistance_civil_war_active", "yes"),
                _requires_direct_scalar_comparison(retreat.value, "surrender_progress", ">", "0.35"),
            )
        ):
            issues.append("retreat assistance lacks strict surrender_progress > 0.35")
        monthly_or = (
            [entry for entry in monthly.value if entry.key == "OR" and isinstance(entry.value, list)]
            if monthly is not None and isinstance(monthly.value, list)
            else []
        )
        expected_monthly_gate = [
            ("ADISCORD_economy_ai_assistance_is_eligible", "yes"),
            *(("has_idea", idea) for idea in ASSISTANCE_IDEAS),
        ]
        if (
            monthly is None
            or not isinstance(monthly.value, list)
            or len(monthly_or) != 1
            or len(monthly.value) != 1
            or [
                (entry.key, entry.value)
                for entry in monthly_or[0].value
                if isinstance(entry.value, str)
            ]
            != expected_monthly_gate
        ):
            issues.append("monthly assistance evaluation is not limited to eligible AI or stale ideas")
    forbidden = (
        "attack_bonus",
        "army_attack_factor",
        "breakthrough_factor",
        "add_tech",
        "set_technology",
        "add_equipment_to_stockpile",
        "add_manpower",
        "add_political_power",
        "add_stability",
        "production_speed_buildings_factor",
        "research_speed_factor",
        "ADISCORD_economy_treasury",
        "ADISCORD_economy_inflation",
        "debt_" + "capacity",
        "every_country",
        "any_country",
    )
    contract_text = block(effects_text, "ADISCORD_economy_refresh_ai_assistance")
    for token in forbidden:
        if token in contract_text:
            issues.append(f"assistance refresh uses prohibited token {token}")
    return issues


def ai_assistance_lifecycle_issues(
    economy_effects: str, minor_effects: str, minor_on_actions: str
) -> list[str]:
    issues: list[str] = []
    refresh = block(minor_effects, "ADISCORD_economy_refresh_ai_assistance")
    if any(token in refresh for token in ("every_country", "any_country")):
        issues.append("assistance refresh scans countries")
    tier = block(economy_effects, "ADISCORD_economy_set_simulation_tier")
    full_if_needed = block(
        economy_effects, "ADISCORD_economy_full_refresh_if_needed"
    )
    income = block(
        economy_effects, "ADISCORD_economy_refresh_ai_assistance_income_cache"
    )
    if tier.count("ADISCORD_economy_refresh_ai_assistance = yes") != 1:
        issues.append("simulation-tier changes do not refresh assistance exactly once")
    if full_if_needed.count("ADISCORD_economy_refresh_ai_assistance = yes") != 1:
        issues.append("bounded dirty/full refresh does not refresh assistance exactly once")
    if not income or any(
        token in income
        for token in ("every_country", "any_country", "every_owned_state", "ADISCORD_economy_full_refresh")
    ):
        issues.append("economy-owned assistance input refresh is missing or unbounded")

    for hook in ("on_startup", "on_war", "on_peace", "on_monthly"):
        body = block(minor_on_actions, hook)
        if not body:
            issues.append(f"minor optimization lacks {hook} assistance hook")
            continue
        if body.count("ADISCORD_economy_refresh_ai_assistance = yes") != 1:
            issues.append(f"{hook} does not route assistance exactly once")
        if hook != "on_startup" and any(
            token in body for token in ("every_country", "any_country")
        ):
            issues.append(f"{hook} assistance hook scans countries")
    startup = block(minor_on_actions, "on_startup")
    if startup.count("every_country") != 1:
        issues.append("protected startup must retain exactly one dormant-tag scan")
    parsed_on_actions = parse_clausewitz(minor_on_actions)
    on_action_roots = [
        entry
        for entry in parsed_on_actions
        if entry.key == "on_actions" and isinstance(entry.value, list)
    ]
    monthly_hooks: list[Entry] = []
    if len(on_action_roots) == 1:
        monthly_hooks = [
            entry
            for entry in on_action_roots[0].value
            if entry.key == "on_monthly" and isinstance(entry.value, list)
        ]
    if len(monthly_hooks) != 1:
        issues.append("monthly assistance lifecycle lacks one parsed owner")
    else:
        monthly_hook = monthly_hooks[0]
        monthly_effects = [
            entry
            for entry in monthly_hook.value
            if entry.key == "effect" and isinstance(entry.value, list)
        ]
        exact_monthly_owner = False
        if (
            [entry.key for entry in monthly_hook.value] == ["effect"]
            and len(monthly_effects) == 1
            and [entry.key for entry in monthly_effects[0].value] == ["if"]
        ):
            owner = monthly_effects[0].value[0]
            if isinstance(owner.value, list):
                limit = _direct_limit(owner)
                exact_monthly_owner = (
                    [entry.key for entry in owner.value]
                    == ["limit", "ADISCORD_economy_refresh_ai_assistance"]
                    and limit is not None
                    and _matches_exact_body(
                        limit,
                        "ADISCORD_economy_ai_assistance_needs_monthly_evaluation = yes",
                    )
                    and _direct_scalar(
                        owner.value, "ADISCORD_economy_refresh_ai_assistance"
                    )
                    == "yes"
                )
        if not exact_monthly_owner:
            issues.append(
                "monthly refresh is not nested in the exact eligible-AI-or-stale owner"
            )
    for forbidden_hook in ("on_daily", "on_weekly", "on_yearly"):
        if block(minor_on_actions, forbidden_hook):
            issues.append(f"assistance uses forbidden recurring hook {forbidden_hook}")
    return issues


def research_policy_flow_issues(text: str) -> list[str]:
    definitions = _definitions((text,))
    effect = definitions.get("ADISCORD_economy_calculate_research_expenses")
    if effect is None or not isinstance(effect.value, list):
        return ["missing research expense calculation"]
    expected = {"1": 0.60, "2": 0.80, "3": 1.00, "4": 1.30, "5": 1.60}
    found: dict[str, list[float]] = {}
    all_multipliers = [
        entry
        for _, entry in _walk_entries(effect.value)
        if entry.key == "multiply_variable"
        and isinstance(entry.value, list)
        and _direct_scalar(entry.value, "var")
        == "ADISCORD_economy_research_expenses"
    ]
    for entry in effect.value:
        if entry.key not in {"if", "else_if"} or not isinstance(entry.value, list):
            continue
        limit = next((item for item in entry.value if item.key == "limit" and isinstance(item.value, list)), None)
        if limit is None:
            continue
        signatures = _check_variable_signatures(
            limit.value, "ADISCORD_economy_research_spending_mode"
        )
        multipliers = _direct_variable_operation(
            entry.value,
            "multiply_variable",
            "ADISCORD_economy_research_expenses",
        )
        if (
            len(signatures) == 1
            and signatures[0][0] is not None
            and signatures[0][1] == "equals"
            and len(multipliers) == 1
            and _exact_check(
                limit.value,
                "ADISCORD_economy_research_spending_mode",
                signatures[0][0],
                "equals",
            )
        ):
            level = signatures[0][0]
            try:
                found.setdefault(level, []).append(
                    float(_direct_scalar(multipliers[0].value, "value") or "nan")
                )
            except (TypeError, ValueError):
                pass
    exact_found = {
        level: values[0]
        for level, values in found.items()
        if len(values) == 1
    }
    return (
        []
        if len(all_multipliers) == 5
        and sum(len(values) for values in found.values()) == 5
        and exact_found == expected
        else [f"research multipliers are not bound one-to-one to levels: {found}"]
    )


def automatic_borrow_flow_issues(text: str) -> list[str]:
    issues: list[str] = []
    for name in ("ADISCORD_economy_apply_weekly_balance", "ADISCORD_economy_apply_monthly_balance"):
        definition = _definitions((text,)).get(name)
        if definition is None or not isinstance(definition.value, list):
            issues.append(f"missing {name}")
            continue
        owners: list[Entry] = []
        for branch, _ in _conditional_else_pairs(definition.value):
            assert isinstance(branch.value, list)
            limit = next(
                (
                    entry
                    for entry in branch.value
                    if entry.key == "limit" and isinstance(entry.value, list)
                ),
                None,
            )
            candidate_copies = [
                entry
                for _, entry in _walk_entries(branch.value)
                if entry.key == "set_variable"
                and isinstance(entry.value, list)
                and _direct_scalar(entry.value, "var")
                == "ADISCORD_economy_auto_borrow_temp"
                and _direct_scalar(entry.value, "value")
                == "ADISCORD_economy_uncovered_deficit_temp"
            ]
            if (
                limit is not None
                and len(candidate_copies) == 1
                and _condition_is_exact_entry(
                    limit.value,
                    lambda entry: _check_matches(
                        entry,
                        "ADISCORD_economy_treasury",
                        "0",
                        "less_than",
                    ),
                )
            ):
                owners.append(branch)
        if len(owners) != 1:
            issues.append(f"{name}: automatic borrow lacks one approved negative-treasury path")
            continue
        owner = owners[0]
        assert isinstance(owner.value, list)
        write_operations = {
            "clear_variable",
            "set_variable",
            "set_temp_variable",
            "add_to_variable",
            "add_to_temp_variable",
            "subtract_from_variable",
            "subtract_from_temp_variable",
            "multiply_variable",
            "multiply_temp_variable",
            "divide_variable",
            "divide_temp_variable",
            "clamp_variable",
            "clamp_temp_variable",
        }
        ordered = [
            (position, ancestors, entry)
            for position, (ancestors, entry) in enumerate(_walk_entries(owner.value))
            if entry.key in write_operations
            and (
                isinstance(entry.value, list)
                or (entry.key == "clear_variable" and isinstance(entry.value, str))
            )
        ]

        def writes_to(variable: str):
            return [
                operation
                for operation in ordered
                if isinstance(operation[2].value, list)
                and _direct_scalar(operation[2].value, "var") == variable
            ]

        source_writes = writes_to("ADISCORD_economy_uncovered_deficit_temp")
        automatic_writes = writes_to("ADISCORD_economy_auto_borrow_temp")
        source_sets = [
            operation
            for operation in source_writes
            if operation[2].key == "set_variable"
            and _direct_scalar(operation[2].value, "value") == "0"
        ]
        source_negations = [
            operation
            for operation in source_writes
            if operation[2].key == "subtract_from_variable"
            and _direct_scalar(operation[2].value, "value")
            == "ADISCORD_economy_treasury"
        ]
        copies = [
            operation
            for operation in automatic_writes
            if operation[2].key == "set_variable"
            and _direct_scalar(operation[2].value, "value")
            == "ADISCORD_economy_uncovered_deficit_temp"
        ]
        canonical: list[tuple[int, tuple[Entry, ...], Entry]] = []
        flow_is_exact = (
            len(source_writes) == 2
            and len(automatic_writes) == 1
            and len(source_sets) == 1
            and len(source_negations) == 1
            and len(copies) == 1
        )
        if flow_is_exact:
            canonical.extend((source_sets[0], source_negations[0], copies[0]))
        copy_position = copies[0][0] if len(copies) == 1 else -1
        for account in ("ADISCORD_economy_debt", "ADISCORD_economy_treasury"):
            owner_account_writes = [
                operation
                for operation in ordered
                if operation[0] > copy_position
                and (
                    (
                        isinstance(operation[2].value, list)
                        and _direct_scalar(operation[2].value, "var") == account
                    )
                    or (
                        operation[2].key == "clear_variable"
                        and operation[2].value == account
                    )
                )
            ]
            owner_additions = [
                operation
                for operation in owner_account_writes
                if operation[2].key == "add_to_variable"
                and _direct_scalar(operation[2].value, "value")
                == "ADISCORD_economy_auto_borrow_temp"
            ]
            all_additions = [
                entry
                for _, entry in _walk_entries(definition.value)
                if entry.key == "add_to_variable"
                and isinstance(entry.value, list)
                and _direct_scalar(entry.value, "var") == account
                and _direct_scalar(entry.value, "value")
                == "ADISCORD_economy_auto_borrow_temp"
            ]
            if (
                len(owner_account_writes) != 1
                or len(owner_additions) != 1
                or owner_additions[0][1]
                or len(all_additions) != 1
            ):
                flow_is_exact = False
            elif canonical:
                canonical.append(owner_additions[0])
            if len(all_additions) != 1:
                issues.append(f"{name}: automatic borrow does not fully fund {account}")
        if canonical and (
            any(ancestors for _, ancestors, _ in canonical)
            or [position for position, _, _ in canonical]
            != sorted(position for position, _, _ in canonical)
        ):
            flow_is_exact = False
        if not flow_is_exact:
            issues.append(
                f"{name}: uncovered deficit is capped, rewritten, or conditionally funded"
            )
    return issues


def debt_transition_flow_issues(text: str) -> list[str]:
    definition = _definitions((text,)).get("ADISCORD_economy_update_debt_state_after_settlement")
    if definition is None or not isinstance(definition.value, list):
        return ["missing debt transition"]
    issues: list[str] = []
    specs = (
        ("ADISCORD_economy_debt_emergency_streak", False, "4", "3"),
        ("ADISCORD_economy_debt_default_streak", True, "13", "4"),
    )
    for streak, needs_negative, threshold, target_state in specs:
        owners = []
        for branch, paired_else in _conditional_else_pairs(definition.value):
            assert isinstance(branch.value, list)
            increments = _direct_variable_operation(
                branch.value, "add_to_variable", streak, "1"
            )
            if increments:
                owners.append((branch, paired_else, increments))
        all_writes = [
            entry
            for _, entry in _walk_entries(definition.value)
            if entry.key in {"add_to_variable", "set_variable"}
            and isinstance(entry.value, list)
            and _direct_scalar(entry.value, "var") == streak
        ]
        if len(owners) != 1 or len(owners[0][2]) != 1 or len(all_writes) != 2:
            issues.append(f"{streak}: requires one owned increment and paired reset")
            continue
        branch, paired_else, _ = owners[0]
        assert isinstance(branch.value, list)
        limit = next(
            (entry for entry in branch.value if entry.key == "limit" and isinstance(entry.value, list)),
            None,
        )
        condition = limit.value if limit else []
        condition_ok = _limit_is_satisfiable(condition) and _exact_check(
            condition,
            "ADISCORD_economy_interest_share_income",
            "40",
            "greater_than_or_equals",
        )
        if needs_negative:
            condition_ok = condition_ok and _exact_check(
                condition,
                "ADISCORD_economy_weekly_balance",
                "0",
                "less_than",
            )
        reset_ok = bool(
            paired_else
            and isinstance(paired_else.value, list)
            and len(_direct_variable_operation(paired_else.value, "set_variable", streak, "0"))
            == 1
        )
        threshold_ok = False
        for threshold_branch, _ in _conditional_else_pairs(branch.value):
            assert isinstance(threshold_branch.value, list)
            threshold_limit = next(
                (
                    entry
                    for entry in threshold_branch.value
                    if entry.key == "limit" and isinstance(entry.value, list)
                ),
                None,
            )
            if threshold_limit is None:
                continue
            if _limit_is_satisfiable(threshold_limit.value) and _exact_check(
                threshold_limit.value,
                streak,
                threshold,
                "greater_than_or_equals",
            ) and len(
                _direct_variable_operation(
                    threshold_branch.value,
                    "set_variable",
                    "ADISCORD_economy_debt_state",
                    target_state,
                )
            ) == 1:
                threshold_ok = True
        if not condition_ok or not reset_ok or not threshold_ok:
            issues.append(f"{streak}: transition condition, reset, or threshold is invalid")
    variable_write_operations = {
        "set_variable", "add_to_variable", "subtract_from_variable",
        "multiply_variable", "divide_variable", "clamp_variable", "clear_variable",
    }

    def writes_variable(entry: Entry, variable: str) -> bool:
        if entry.key not in variable_write_operations:
            return False
        return entry.value == variable or (
            isinstance(entry.value, list)
            and _direct_scalar(entry.value, "var") == variable
        )

    state_owner_positions: list[int] = []
    for ancestors, entry in _walk_entries(definition.value):
        if not writes_variable(entry, "ADISCORD_economy_debt_state"):
            continue
        top_level_owner = ancestors[0] if ancestors else entry
        if top_level_owner in definition.value:
            state_owner_positions.append(definition.value.index(top_level_owner))
    mirrors = [
        (ancestors, entry)
        for ancestors, entry in _walk_entries(definition.value)
        if writes_variable(entry, "ADISCORD_economy_debt_crisis_level")
    ]
    sync_calls = [
        (ancestors, entry)
        for ancestors, entry in _walk_entries(definition.value)
        if entry.key == "ADISCORD_economy_sync_debt_state_idea"
    ]
    authority_ok = bool(
        state_owner_positions
        and len(mirrors) == 1
        and not mirrors[0][0]
        and _is_exact_variable_write(
            mirrors[0][1],
            "set_variable",
            "ADISCORD_economy_debt_crisis_level",
            "ADISCORD_economy_debt_state",
        )
        and len(sync_calls) == 1
        and not sync_calls[0][0]
        and sync_calls[0][1].value == "yes"
    )
    if authority_ok:
        mirror_position = definition.value.index(mirrors[0][1])
        sync_position = definition.value.index(sync_calls[0][1])
        authority_ok = max(state_owner_positions) < mirror_position < sync_position
    if not authority_ok:
        issues.append("debt transition does not mirror state and sync its idea after all state writes")
    return issues


def debt_notification_flow_issues(text: str) -> list[str]:
    definitions = _definitions((text,))
    issues: list[str] = []
    queue_name = "ADISCORD_economy_queue_debt_notification"
    queue = definitions.get(queue_name)
    if queue is None or not isinstance(queue.value, list):
        return ["missing debt notification queue"]

    settlement_names = {
        "ADISCORD_economy_apply_weekly_balance",
        "ADISCORD_economy_apply_monthly_balance",
    }
    for name, definition in definitions.items():
        calls = [
            (ancestors, entry)
            for ancestors, entry in _walk_entries(definition.value)
            if entry.key == queue_name and entry.value == "yes"
        ]
        if name not in settlement_names:
            if calls:
                issues.append(f"{name}: debt queue call outside a settlement")
            continue
        direct_calls = [entry for entry in definition.value if entry.key == queue_name]
        direct_updates = [
            entry
            for entry in definition.value
            if entry.key == "ADISCORD_economy_update_debt_state_after_settlement"
            and entry.value == "yes"
        ]
        if len(calls) != 1 or len(direct_calls) != 1:
            issues.append(f"{name}: notification queue is not called directly once")
            continue
        if len(direct_updates) != 1:
            issues.append(f"{name}: debt state is not updated directly once")
            continue
        previous_cache = _direct_variable_operation(
            definition.value,
            "set_variable",
            "ADISCORD_economy_pending_debt_notification_previous_state",
            "ADISCORD_economy_debt_state",
        )
        amount_reset = _direct_variable_operation(
            definition.value,
            "set_variable",
            "ADISCORD_economy_pending_debt_notification_amount",
            "0",
        )
        if len(previous_cache) != 1 or len(amount_reset) != 1:
            issues.append(f"{name}: settlement notification caches are not reset once")
            continue
        positions = [
            definition.value.index(previous_cache[0]),
            definition.value.index(amount_reset[0]),
            definition.value.index(direct_updates[0]),
            definition.value.index(direct_calls[0]),
        ]
        if max(positions[:2]) >= positions[2] or positions[2] >= positions[3]:
            issues.append(f"{name}: notification cache/update/queue order is invalid")

    kind_variable = "ADISCORD_economy_pending_debt_notification_kind"
    if len(queue.value) != 6:
        issues.append("notification queue is not the exact reset/first/upward/improvement/dispatch sequence")
    if len(queue.value) >= 2:
        if not _is_exact_variable_write(
            queue.value[0], "set_variable", kind_variable, "0"
        ):
            issues.append("notification queue does not directly reset kind first")
        if not _is_exact_variable_write(
            queue.value[1],
            "set_variable",
            "ADISCORD_economy_pending_debt_notification_new_state",
            "ADISCORD_economy_debt_state",
        ):
            issues.append("notification queue does not directly cache new state second")

    first_branch = queue.value[2] if len(queue.value) > 2 else None
    first_ok = bool(
        first_branch
        and first_branch.key == "if"
        and isinstance(first_branch.value, list)
        and len(first_branch.value) == 3
    )
    if first_ok:
        first_limit = _direct_limit(first_branch)
        first_ok = bool(
            first_limit is not None
            and len(first_limit) == 2
            and _limit_is_satisfiable(first_limit)
            and _exact_check(
                first_limit,
                "ADISCORD_economy_pending_debt_notification_amount",
                "0",
                "greater_than",
            )
            and _exact_scalar(
                first_limit,
                "has_variable",
                "ADISCORD_economy_first_loan_notified",
                positive=False,
            )
            and _is_exact_variable_write(
                first_branch.value[1], "set_variable", kind_variable, "1"
            )
            and _is_exact_variable_write(
                first_branch.value[2],
                "set_variable",
                "ADISCORD_economy_first_loan_notified",
                "1",
            )
        )
    if not first_ok:
        issues.append("first-loan notification kind 1 lacks its exact direct owner")

    upward_branch = queue.value[3] if len(queue.value) > 3 else None
    upward_ok = bool(
        upward_branch
        and upward_branch.key == "if"
        and isinstance(upward_branch.value, list)
        and len(upward_branch.value) == 6
    )
    if upward_ok:
        upward_limit = _direct_limit(upward_branch)
        upward_ok = bool(
            upward_limit is not None
            and len(upward_limit) == 2
            and _limit_is_satisfiable(upward_limit)
            and _exact_check(
                upward_limit,
                "ADISCORD_economy_debt_state",
                "ADISCORD_economy_pending_debt_notification_previous_state",
                "greater_than",
            )
            and _exact_check(
                upward_limit,
                "ADISCORD_economy_debt_state",
                "ADISCORD_economy_last_notified_debt_state",
                "greater_than",
            )
        )
        mapping_entries = upward_branch.value[1:5]
        expected_mapping = (("if", "4", "5"), ("else_if", "3", "4"), ("else_if", "2", "3"), ("else_if", "1", "2"))
        for mapping, (branch_key, state, kind) in zip(mapping_entries, expected_mapping):
            mapping_limit = _direct_limit(mapping)
            mapping_ok = bool(
                mapping.key == branch_key
                and isinstance(mapping.value, list)
                and len(mapping.value) == 2
                and mapping_limit is not None
                and len(mapping_limit) == 1
                and _limit_is_satisfiable(mapping_limit)
                and _exact_check(
                    mapping_limit,
                    "ADISCORD_economy_debt_state",
                    state,
                    "equals",
                )
                and _is_exact_variable_write(
                    mapping.value[1], "set_variable", kind_variable, kind
                )
            )
            upward_ok = upward_ok and mapping_ok
        upward_ok = upward_ok and _is_exact_variable_write(
            upward_branch.value[5],
            "set_variable",
            "ADISCORD_economy_last_notified_debt_state",
            "ADISCORD_economy_debt_state",
        )
    if not upward_ok:
        issues.append("upward owner lacks the exact ordered state 4..1 severity mapping")

    improvement_branch = queue.value[4] if len(queue.value) > 4 else None
    improvement_ok = bool(
        improvement_branch
        and improvement_branch.key == "if"
        and isinstance(improvement_branch.value, list)
        and len(improvement_branch.value) == 2
    )
    if improvement_ok:
        improvement_limit = _direct_limit(improvement_branch)
        improvement_ok = bool(
            improvement_limit is not None
            and len(improvement_limit) == 2
            and _limit_is_satisfiable(improvement_limit)
            and _is_exact_check_entry(
                improvement_limit[0],
                "ADISCORD_economy_debt_state",
                "ADISCORD_economy_pending_debt_notification_previous_state",
                "less_than",
            )
            and _is_exact_check_entry(
                improvement_limit[1],
                "ADISCORD_economy_last_notified_debt_state",
                "ADISCORD_economy_debt_state",
                "greater_than",
            )
            and _is_exact_variable_write(
                improvement_branch.value[1],
                "set_variable",
                "ADISCORD_economy_last_notified_debt_state",
                "ADISCORD_economy_debt_state",
            )
        )
    if not improvement_ok:
        issues.append("improvement does not lower notification state exactly")

    variable_write_operations = {
        "set_variable", "add_to_variable", "subtract_from_variable",
        "multiply_variable", "divide_variable", "clamp_variable", "clear_variable",
    }
    watermark_writes = [
        (ancestors, entry)
        for ancestors, entry in _walk_entries(queue.value)
        if entry.key in variable_write_operations
        and (
            entry.value == "ADISCORD_economy_last_notified_debt_state"
            or (
                isinstance(entry.value, list)
                and _direct_scalar(entry.value, "var")
                == "ADISCORD_economy_last_notified_debt_state"
            )
        )
    ]
    watermark_owners_ok = bool(
        upward_branch
        and isinstance(upward_branch.value, list)
        and len(upward_branch.value) == 6
        and improvement_branch
        and isinstance(improvement_branch.value, list)
        and len(improvement_branch.value) == 2
        and len(watermark_writes) == 2
        and len(watermark_writes[0][0]) == 1
        and watermark_writes[0][0][0] is upward_branch
        and watermark_writes[0][1] is upward_branch.value[5]
        and len(watermark_writes[1][0]) == 1
        and watermark_writes[1][0][0] is improvement_branch
        and watermark_writes[1][1] is improvement_branch.value[1]
        and all(
            _is_exact_variable_write(
                entry,
                "set_variable",
                "ADISCORD_economy_last_notified_debt_state",
                "ADISCORD_economy_debt_state",
            )
            for _, entry in watermark_writes
        )
    )
    if not watermark_owners_ok:
        issues.append("notification watermark has duplicate or unowned writes")

    dispatch_branch = queue.value[5] if len(queue.value) > 5 else None
    dispatch_ok = bool(
        dispatch_branch
        and dispatch_branch.key == "if"
        and isinstance(dispatch_branch.value, list)
        and len(dispatch_branch.value) == 2
    )
    if dispatch_ok:
        dispatch_limit = _direct_limit(dispatch_branch)
        event = dispatch_branch.value[1]
        dispatch_ok = bool(
            dispatch_limit is not None
            and len(dispatch_limit) == 2
            and _limit_is_satisfiable(dispatch_limit)
            and _exact_scalar(dispatch_limit, "is_ai", "no")
            and _exact_check(dispatch_limit, kind_variable, "0", "greater_than")
            and event.key == "country_event"
            and isinstance(event.value, list)
            and len(event.value) == 1
            and _direct_scalar(event.value, "id") == "ADISCORD_economy.3"
        )
    if not dispatch_ok:
        issues.append("debt modal is not the final direct human-only pending dispatch")

    kind_writes = [
        entry
        for _, entry in _walk_entries(queue.value)
        if entry.key == "set_variable"
        and isinstance(entry.value, list)
        and _direct_scalar(entry.value, "var") == kind_variable
    ]
    for kind in range(6):
        if sum(
            _is_exact_variable_write(entry, "set_variable", kind_variable, str(kind))
            for entry in kind_writes
        ) != 1:
            issues.append(f"notification kind {kind} does not have one exact owner")

    all_debt_events: list[tuple[str, tuple[Entry, ...], Entry]] = []
    for name, definition in definitions.items():
        for ancestors, entry in _walk_entries(definition.value):
            if (
                entry.key == "country_event"
                and isinstance(entry.value, list)
                and _direct_scalar(entry.value, "id") == "ADISCORD_economy.3"
            ):
                all_debt_events.append((name, ancestors, entry))
    if len(all_debt_events) != 1 or all_debt_events[0][0] != queue_name:
        issues.append("debt modal is not dispatched exactly once by the queue")
    else:
        _, ancestors, event = all_debt_events[0]
        if not (
            dispatch_ok
            and len(ancestors) == 1
            and ancestors[0] is dispatch_branch
            and isinstance(dispatch_branch.value, list)
            and dispatch_branch.value[1] is event
        ):
            issues.append("debt modal dispatch is not exactly human-only and pending")
    return issues


def debt_reconciler_issues(text: str) -> list[str]:
    definition = _definitions((text,)).get("ADISCORD_economy_reconcile_debt_state_after_action")
    if definition is None or not isinstance(definition.value, list):
        return ["missing debt reconciler"]
    tokens = _tokens_in(definition.value)
    issues: list[str] = []
    state_variable = "ADISCORD_economy_debt_state"
    notified_variable = "ADISCORD_economy_last_notified_debt_state"
    variable_write_operations = {
        "set_variable",
        "add_to_variable",
        "subtract_from_variable",
        "multiply_variable",
        "divide_variable",
        "clamp_variable",
        "clear_variable",
    }
    debuffs = {
        "ADISCORD_economy_debt_strain",
        "ADISCORD_economy_debt_crisis",
        "ADISCORD_economy_debt_emergency",
        "ADISCORD_economy_debt_default",
    }
    target_ideas = {
        0: None,
        1: "ADISCORD_economy_debt_strain",
        2: "ADISCORD_economy_debt_crisis",
    }

    def writes_variable(entry: Entry, variable: str) -> bool:
        if entry.key not in variable_write_operations:
            return False
        if entry.key == "clear_variable":
            return entry.value == variable or (
                isinstance(entry.value, list)
                and _direct_scalar(entry.value, "var") == variable
            )
        return (
            isinstance(entry.value, list)
            and _direct_scalar(entry.value, "var") == variable
        )

    def exact_variable_set(entry: Entry, variable: str, value: int) -> bool:
        if entry.key != "set_variable" or not isinstance(entry.value, list):
            return False
        actual_value = _direct_scalar(entry.value, "value")
        try:
            value_matches = actual_value is not None and float(actual_value) == float(value)
        except ValueError:
            value_matches = False
        return (
            len(entry.value) == 2
            and sorted(child.key for child in entry.value) == ["value", "var"]
            and _direct_scalar(entry.value, "var") == variable
            and value_matches
        )

    def exact_check(entry: Entry, variable: str, value: int, compare: str) -> bool:
        return (
            isinstance(entry.value, list)
            and len(entry.value) == 3
            and sorted(child.key for child in entry.value) == ["compare", "value", "var"]
            and _check_matches(entry, variable, str(value), compare)
        )

    state_operations = [
        entry
        for _, entry in _walk_entries(definition.value)
        if writes_variable(entry, state_variable)
    ]
    notified_operations = [
        entry
        for _, entry in _walk_entries(definition.value)
        if writes_variable(entry, notified_variable)
    ]
    branches = [
        entry
        for entry in definition.value
        if entry.key in {"if", "else_if"} and isinstance(entry.value, list)
    ]
    if len(branches) != 3 or [branch.key for branch in branches] != ["if", "else_if", "else_if"]:
        issues.append("debt reconciler must have exactly three ordered state branches")

    found_targets: set[int] = set()
    claimed_state_writes: set[int] = set()
    claimed_notified_writes: set[int] = set()
    expected_bands = {0: 10, 1: 25, 2: 40}
    for branch in branches:
        assert isinstance(branch.value, list)
        direct_state_operations = [
            entry for entry in branch.value if writes_variable(entry, state_variable)
        ]
        if len(direct_state_operations) != 1:
            issues.append("debt reconciler branch must own exactly one state write")
            continue
        write = direct_state_operations[0]
        target_text = (
            _direct_scalar(write.value, "value")
            if isinstance(write.value, list)
            else None
        )
        try:
            target = int(target_text or "")
        except ValueError:
            issues.append("debt reconciler writes a non-numeric state")
            continue
        if target not in expected_bands or not exact_variable_set(write, state_variable, target):
            issues.append("debt reconciler writes an invalid state target")
            continue
        found_targets.add(target)
        claimed_state_writes.add(id(write))

        limits = [
            entry
            for entry in branch.value
            if entry.key == "limit" and isinstance(entry.value, list)
        ]
        condition_ok = False
        if len(limits) == 1:
            condition = limits[0].value
            assert isinstance(condition, list)
            condition_ok = (
                len(condition) == 2
                and sum(
                    exact_check(
                        entry,
                        "ADISCORD_economy_interest_share_income",
                        expected_bands[target],
                        "less_than",
                    )
                    for entry in condition
                )
                == 1
                and sum(
                    exact_check(entry, state_variable, target, "greater_than")
                    for entry in condition
                )
                == 1
                and _limit_is_satisfiable(condition)
            )
        if not condition_ok:
            issues.append("debt reconciler branch has the wrong state band or predicate")

        nested_conditions = [
            candidate
            for candidate in branch.value
            if candidate.key in {"if", "else_if"}
            and isinstance(candidate.value, list)
        ]
        metadata_ok = len(nested_conditions) == 1
        if metadata_ok:
            owner = nested_conditions[0]
            assert isinstance(owner.value, list)
            owner_writes = [
                entry
                for entry in owner.value
                if writes_variable(entry, notified_variable)
            ]
            owner_limits = [
                entry
                for entry in owner.value
                if entry.key == "limit" and isinstance(entry.value, list)
            ]
            metadata_ok = len(owner_writes) == 1 and exact_variable_set(
                owner_writes[0], notified_variable, target
            )
            if metadata_ok and len(owner_limits) == 1:
                owner_condition = owner_limits[0].value
                assert isinstance(owner_condition, list)
                metadata_ok = (
                    len(owner_condition) == 1
                    and exact_check(
                        owner_condition[0], notified_variable, target, "greater_than"
                    )
                    and _limit_is_satisfiable(owner_condition)
                    and owner.value.index(owner_limits[0]) < owner.value.index(owner_writes[0])
                )
            else:
                metadata_ok = False
            if metadata_ok:
                claimed_notified_writes.add(id(owner_writes[0]))
        if not metadata_ok:
            issues.append("debt reconciler branch has invalid notification-state ownership")

        removed: set[str] = set()
        for operation in branch.value:
            if operation.key == "remove_ideas":
                removed.update(_operand_values(operation))
        additions = [
            idea
            for operation in branch.value
            if operation.key == "add_ideas"
            for idea in _operand_values(operation)
            if idea in debuffs
        ]
        expected_idea = target_ideas[target]
        additions_ok = additions == ([] if expected_idea is None else [expected_idea])
        remove_positions = [
            index for index, operation in enumerate(branch.value) if operation.key == "remove_ideas"
        ]
        add_positions = [
            index for index, operation in enumerate(branch.value) if operation.key == "add_ideas"
        ]
        order_ok = bool(remove_positions) and (
            not add_positions or max(remove_positions) < min(add_positions)
        )
        if removed != debuffs or not additions_ok or not order_ok:
            issues.append("debt reconciler branch misapplies debt debuffs")

    if found_targets != set(expected_bands):
        issues.append("debt reconciler lacks the exact state targets 0, 1, and 2")
    if len(state_operations) != 3 or claimed_state_writes != {
        id(entry) for entry in state_operations
    }:
        issues.append("debt reconciler has extra or unowned state writes")
    if len(notified_operations) != 3 or claimed_notified_writes != {
        id(entry) for entry in notified_operations
    }:
        issues.append("debt reconciler has extra or unowned notification-state writes")
    if any("streak" in token for token in tokens if token.startswith("ADISCORD_")):
        issues.append("debt reconciler mutates settlement streaks")
    if "ADISCORD_economy_queue_debt_notification" in tokens:
        issues.append("debt reconciler queues notifications")
    if any(
        entry.key == "event" or entry.key.endswith("_event")
        for _, entry in _walk_entries(definition.value)
    ):
        issues.append("debt reconciler fires events")
    mirrors = [
        (ancestors, entry)
        for ancestors, entry in _walk_entries(definition.value)
        if writes_variable(entry, "ADISCORD_economy_debt_crisis_level")
    ]
    mirror_ok = bool(
        branches
        and len(mirrors) == 1
        and not mirrors[0][0]
        and _is_exact_variable_write(
            mirrors[0][1],
            "set_variable",
            "ADISCORD_economy_debt_crisis_level",
            "ADISCORD_economy_debt_state",
        )
        and max(definition.value.index(branch) for branch in branches)
        < definition.value.index(mirrors[0][1])
    )
    if not mirror_ok:
        issues.append("debt reconciler does not mirror state after its branch chain")
    return issues


def debt_notification_selector_issues(text: str) -> list[str]:
    """Bind every debt-notification selector to its exact ordered meaning."""

    try:
        ast = parse_clausewitz(text)
    except ValueError as error:
        return [f"debt notification selectors do not parse: {error}"]
    contracts = {
        "GetADISCORDEconomyDebtNotificationKindLoc": (
            (
                "ADISCORD_economy_pending_debt_notification_kind",
                (("5", "equals", "ADISCORD_economy_debt_notification_kind_default"),
                 ("4", "equals", "ADISCORD_economy_debt_notification_kind_emergency"),
                 ("3", "equals", "ADISCORD_economy_debt_notification_kind_crisis"),
                 ("2", "equals", "ADISCORD_economy_debt_notification_kind_strain"),
                 ("1", "equals", "ADISCORD_economy_debt_notification_kind_first_loan")),
            ),
            "ADISCORD_economy_debt_notification_kind_fallback",
        ),
        "GetADISCORDEconomyDebtNotificationCauseLoc": (
            (
                None,
                (("ADISCORD_economy_pending_debt_notification_amount", "0", "greater_than", "ADISCORD_economy_debt_notification_cause_auto_loan"),
                 ("ADISCORD_economy_pending_debt_notification_new_state", "1", "greater_than_or_equals", "ADISCORD_economy_debt_notification_cause_interest")),
            ),
            "ADISCORD_economy_debt_notification_cause_fallback",
        ),
        "GetADISCORDEconomyDebtNotificationStateLoc": (
            (
                "ADISCORD_economy_pending_debt_notification_new_state",
                (("4", "greater_than_or_equals", "ADISCORD_economy_debt_notification_state_default"),
                 ("3", "greater_than_or_equals", "ADISCORD_economy_debt_notification_state_emergency"),
                 ("2", "greater_than_or_equals", "ADISCORD_economy_debt_notification_state_crisis"),
                 ("1", "greater_than_or_equals", "ADISCORD_economy_debt_notification_state_strain")),
            ),
            "ADISCORD_economy_debt_notification_state_healthy",
        ),
        "GetADISCORDEconomyDebtNotificationNextRiskLoc": (
            (
                "ADISCORD_economy_pending_debt_notification_new_state",
                (("4", "greater_than_or_equals", "ADISCORD_economy_debt_notification_next_default"),
                 ("3", "greater_than_or_equals", "ADISCORD_economy_debt_notification_next_emergency"),
                 ("2", "greater_than_or_equals", "ADISCORD_economy_debt_notification_next_crisis"),
                 ("1", "greater_than_or_equals", "ADISCORD_economy_debt_notification_next_strain")),
            ),
            "ADISCORD_economy_debt_notification_next_healthy",
        ),
    }
    issues: list[str] = []
    for selector, ((shared_variable, raw_branches), fallback) in contracts.items():
        matches = [
            entry
            for entry in ast
            if entry.key == "defined_text"
            and isinstance(entry.value, list)
            and _direct_scalar(entry.value, "name") == selector
        ]
        if len(matches) != 1:
            issues.append(f"{selector}: expected one top-level defined_text, found {len(matches)}")
            continue
        selector_body = matches[0].value
        assert isinstance(selector_body, list)
        if shared_variable is None:
            expected = [tuple(branch) for branch in raw_branches]
        else:
            expected = [
                (shared_variable, value, compare, key)
                for value, compare, key in raw_branches
            ]
        exact_body_identity = bool(
            len(selector_body) == len(expected) + 2
            and selector_body[0].key == "name"
            and selector_body[0].value == selector
            and [entry.key for entry in selector_body[1:]]
            == ["text"] * (len(expected) + 1)
            and all(isinstance(entry.value, list) for entry in selector_body[1:])
        )
        if not exact_body_identity:
            issues.append(f"{selector}: body has duplicate identity or extra direct fields")
            continue
        branches = selector_body[1:]
        if len(branches) != len(expected) + 1:
            issues.append(f"{selector}: wrong number of ordered selector branches")
            continue
        for branch, (variable, value, compare, key) in zip(branches[:-1], expected):
            triggers = [
                entry
                for entry in branch.value
                if entry.key == "trigger" and isinstance(entry.value, list)
            ]
            branch_ok = bool(
                len(branch.value) == 2
                and [entry.key for entry in branch.value] == ["trigger", "localization_key"]
                and len(triggers) == 1
                and len(triggers[0].value) == 1
                and _limit_is_satisfiable(triggers[0].value)
                and _check_matches(triggers[0].value[0], variable, value, compare)
                and len(triggers[0].value[0].value) == 3
                and _direct_scalar(branch.value, "localization_key") == key
            )
            if not branch_ok:
                issues.append(f"{selector}: selector branch {key} has wrong semantics or owner")
        terminal = branches[-1]
        if not (
            len(terminal.value) == 1
            and terminal.value[0].key == "localization_key"
            and terminal.value[0].value == fallback
        ):
            issues.append(f"{selector}: terminal fallback is conditional, missing, or wrong")
    return issues


def policy_effect_selector_issues(
    text: str, selector: str, target_var: str, effect_prefix: str
) -> list[str]:
    """Validate one exact five-level directional effect selector."""

    ast = parse_clausewitz(text)
    matches = [
        entry
        for entry in ast
        if entry.key == "defined_text"
        and isinstance(entry.value, list)
        and any(
            child.key == "name" and child.value == selector
            for child in entry.value
        )
    ]
    if len(matches) != 1:
        return [f"{selector}: missing unique defined_text"]

    selector_body = matches[0].value
    assert isinstance(selector_body, list)
    if not (
        len(selector_body) == 6
        and selector_body[0].key == "name"
        and selector_body[0].value == selector
        and [entry.key for entry in selector_body[1:]] == ["text"] * 5
        and all(isinstance(entry.value, list) for entry in selector_body[1:])
    ):
        return [f"{selector}: body has extra fields or the wrong branch count"]

    issues: list[str] = []
    branches = selector_body[1:]
    for level, branch in enumerate(branches[:4], start=1):
        assert isinstance(branch.value, list)
        triggers = [
            entry
            for entry in branch.value
            if entry.key == "trigger" and isinstance(entry.value, list)
        ]
        expected_key = f"{effect_prefix}_{level}"
        branch_ok = bool(
            len(branch.value) == 2
            and [entry.key for entry in branch.value]
            == ["trigger", "localization_key"]
            and len(triggers) == 1
            and len(triggers[0].value) == 1
            and _limit_is_satisfiable(triggers[0].value)
            and _is_exact_check_entry(
                triggers[0].value[0],
                target_var,
                str(level),
                "less_than_or_equals",
            )
            and _direct_scalar(branch.value, "localization_key") == expected_key
        )
        if not branch_ok:
            issues.append(
                f"{selector}: level {level} threshold/effect mapping is not exact"
            )

    terminal = branches[4]
    assert isinstance(terminal.value, list)
    if not (
        len(terminal.value) == 1
        and terminal.value[0].key == "localization_key"
        and terminal.value[0].value == f"{effect_prefix}_5"
    ):
        issues.append(f"{selector}: level 5 fallback is conditional, missing, or wrong")
    return issues


def policy_selector_issues(
    text: str,
    selector: str,
    mode_var: str,
    cooldown_var: str,
    direction: str,
) -> list[str]:
    """Validate exact ordered, positive and satisfiable disabled reasons."""

    ast = parse_clausewitz(text)
    matches = [
        entry
        for entry in ast
        if entry.key == "defined_text"
        and isinstance(entry.value, list)
        and any(
            child.key == "name" and child.value == selector
            for child in entry.value
        )
    ]
    if len(matches) != 1:
        return [f"{selector}: missing unique defined_text"]

    selector_body = matches[0].value
    assert isinstance(selector_body, list)
    if not (
        len(selector_body) == 5
        and selector_body[0].key == "name"
        and selector_body[0].value == selector
        and [entry.key for entry in selector_body[1:]] == ["text"] * 4
        and all(isinstance(entry.value, list) for entry in selector_body[1:])
    ):
        return [f"{selector}: body has extra fields or the wrong branch count"]

    branches = selector_body[1:]
    boundary = "ADISCORD_economy_policy_blocked_minimum" if direction == "decrease" else "ADISCORD_economy_policy_blocked_maximum"
    issues: list[str] = []
    boundary_value = "1" if direction == "decrease" else "5"
    boundary_compare = "less_than_or_equals" if direction == "decrease" else "greater_than_or_equals"

    exact_checks = (
        (mode_var, boundary_value, boundary_compare, boundary),
        (
            cooldown_var,
            "0",
            "greater_than",
            "ADISCORD_economy_policy_blocked_cooldown",
        ),
    )
    for branch, (variable, value, compare, key) in zip(
        branches[:2], exact_checks
    ):
        assert isinstance(branch.value, list)
        triggers = [
            entry
            for entry in branch.value
            if entry.key == "trigger" and isinstance(entry.value, list)
        ]
        if not (
            len(branch.value) == 2
            and [entry.key for entry in branch.value]
            == ["trigger", "localization_key"]
            and len(triggers) == 1
            and len(triggers[0].value) == 1
            and _limit_is_satisfiable(triggers[0].value)
            and _is_exact_check_entry(
                triggers[0].value[0], variable, value, compare
            )
            and _direct_scalar(branch.value, "localization_key") == key
        ):
            issues.append(f"{selector}: reason {key} has the wrong exact owner")

    scope_branch = branches[2]
    assert isinstance(scope_branch.value, list)
    scope_triggers = [
        entry
        for entry in scope_branch.value
        if entry.key == "trigger" and isinstance(entry.value, list)
    ]
    scope_ok = False
    if (
        len(scope_branch.value) == 2
        and [entry.key for entry in scope_branch.value]
        == ["trigger", "localization_key"]
        and len(scope_triggers) == 1
        and len(scope_triggers[0].value) == 1
        and _limit_is_satisfiable(scope_triggers[0].value)
    ):
        negation = scope_triggers[0].value[0]
        scope_ok = bool(
            negation.key == "NOT"
            and isinstance(negation.value, list)
            and len(negation.value) == 1
            and negation.value[0].key == "ADISCORD_economy_should_show_player_ui"
            and negation.value[0].value == "yes"
            and _direct_scalar(scope_branch.value, "localization_key")
            == "ADISCORD_economy_policy_blocked_scope"
        )
    if not scope_ok:
        issues.append(f"{selector}: unavailable-scope reason has the wrong exact owner")

    terminal = branches[3]
    assert isinstance(terminal.value, list)
    if not (
        len(terminal.value) == 1
        and terminal.value[0].key == "localization_key"
        and terminal.value[0].value == "ADISCORD_economy_policy_preview_available"
    ):
        issues.append(f"{selector}: available preview is not the sole final fallback")
    return issues


def validate(root: Path = ROOT) -> list[str]:
    root = Path(root)
    issues: list[str] = []

    def read_at_root(path: str) -> str:
        return (root / path).read_text(encoding="utf-8-sig")

    def read_required(path: str) -> str:
        source = root / path
        if not source.is_file():
            issues.append(f"missing required future-owned source: {path}")
            return ""
        return source.read_text(encoding="utf-8-sig")

    effects = strip_comments(
        read_at_root("common/scripted_effects/ADISCORD_economy_effects.txt")
    )
    modifier_effects = strip_comments(
        read_at_root("common/scripted_effects/ADISCORD_economy_modifier_effects.txt")
    )
    triggers = strip_comments(
        read_at_root("common/scripted_triggers/ADISCORD_economy_triggers.txt")
    )
    on_actions = strip_comments(
        read_at_root("common/on_actions/00_ADISCORD_on_actions.txt")
    )
    default_ai = strip_comments(read_at_root("common/ai_strategy/default.txt"))
    economy_ai = strip_comments(
        read_at_root("common/ai_strategy/ADISCORD_economy_ai.txt")
    )
    gui = strip_comments(read_at_root("interface/ADISCORD_economy.gui"))
    interface_gfx = strip_comments(read_at_root("interface/ADISCORD_economy.gfx"))
    scripted_gui = strip_comments(
        read_at_root("common/scripted_guis/ADISCORD_economy_scripted_gui.txt")
    )
    scripted_loc = strip_comments(
        read_at_root("common/scripted_localisation/ADISCORD_economy_scripted_loc.txt")
    )
    ideas = strip_comments(read_at_root("common/ideas/ADISCORD_economy_ideas.txt"))
    minor_ideas = strip_comments(
        read_required("common/ideas/ADISCORD_minor_optimization_ideas.txt")
    )
    all_idea_text = "\n".join(
        strip_comments(path.read_text(encoding="utf-8-sig"))
        for path in sorted((root / "common/ideas").rglob("*.txt"))
    )
    all_effect_text = "\n".join(
        path.read_text(encoding="utf-8-sig")
        for path in sorted((root / "common/scripted_effects").rglob("*.txt"))
    )
    minor_effects = strip_comments(
        read_required("common/scripted_effects/ADISCORD_minor_optimization_effects.txt")
    )
    minor_on_actions = strip_comments(
        read_required("common/on_actions/00_ADISCORD_minor_optimization_on_actions.txt")
    )
    minor_triggers = strip_comments(
        read_required("common/scripted_triggers/ADISCORD_minor_optimization_triggers.txt")
    )
    buildings = strip_comments(read_at_root("common/buildings/00_buildings.txt"))
    dynamic_modifiers = strip_comments(
        read_at_root("common/dynamic_modifiers/ADISCORD_economy_dynamic_modifiers.txt")
    )
    localisation = read_at_root("localisation/russian/ADISCORD_economy_l_russian.yml")

    def require(condition: bool, message: str) -> None:
        if not condition:
            issues.append(message)

    issues.extend(
        migration_contract_issues(
            effects,
            {
                "triggers": triggers,
                "ideas": ideas,
                "scripted_gui": scripted_gui,
                "scripted_loc": scripted_loc,
                "economy_ai": economy_ai,
            },
        )
    )
    if minor_ideas and minor_effects:
        issues.extend(
            ai_assistance_contract_issues(
                all_idea_text, all_effect_text, minor_triggers
            )
        )
        issues.extend(
            ai_assistance_lifecycle_issues(
                effects, minor_effects, minor_on_actions
            )
        )
    issues.extend(ai_policy_contract_issues(effects))
    issues.extend(research_policy_flow_issues(effects))
    issues.extend(automatic_borrow_flow_issues(effects))
    issues.extend(debt_transition_flow_issues(effects))
    issues.extend(debt_notification_flow_issues(effects))
    issues.extend(debt_reconciler_issues(effects))
    issues.extend(debt_notification_selector_issues(scripted_loc))
    boundary_sources: dict[str, str] = {}
    text_suffixes = {".txt", ".gui", ".gfx", ".yml", ".yaml", ".md", ".py"}
    for directory in ("common", "interface", "events", "localisation", "docs", "tools"):
        for path in (root / directory).rglob("*"):
            if path.is_file() and path.suffix.casefold() in text_suffixes:
                boundary_sources[path.relative_to(root).as_posix()] = path.read_text(
                    encoding="utf-8-sig", errors="replace"
                )
    issues.extend(retired_capacity_boundary_issues(boundary_sources))
    selector_policies = {
        "Tax": ("tax", "ADISCORD_economy_tax_burden_mode", "ADISCORD_economy_tax_change_cooldown"),
        "Army": ("army", "ADISCORD_economy_army_spending_mode", "ADISCORD_economy_army_budget_change_cooldown"),
        "Research": ("research", "ADISCORD_economy_research_spending_mode", "ADISCORD_economy_research_budget_change_cooldown"),
        "Social": ("social", "ADISCORD_economy_social_spending_mode", "ADISCORD_economy_social_budget_change_cooldown"),
    }
    for title, (policy, mode_var, cooldown_var) in selector_policies.items():
        for direction in ("decrease", "increase"):
            selector = f"GetADISCORDEconomy{title}{direction.title()}PreviewLoc"
            issues.extend(
                policy_selector_issues(
                    scripted_loc, selector, mode_var, cooldown_var, direction
                )
            )
            effect_selector = (
                f"GetADISCORDEconomy{title}{direction.title()}EffectLoc"
            )
            issues.extend(
                policy_effect_selector_issues(
                    scripted_loc,
                    effect_selector,
                    f"ADISCORD_economy_{policy}_{direction}_target_level",
                    f"ADISCORD_economy_{policy}_effects",
                )
            )

    require("ADISCORD_economy_schema_version" in effects, "economy lacks a schema-versioned migration")
    require("ADISCORD_economy_migrate_schema" in effects, "economy lacks ADISCORD_economy_migrate_schema")

    for name in ("GetADISCORDInternalBondsAvailabilityLoc", "GetADISCORDExternalLoanAvailabilityLoc"):
        require(f"name = {name}" in scripted_loc, f"loan UI lacks dynamic availability text {name}")
    require("[GetADISCORDInternalBondsAvailabilityLoc]" in localisation
            and "[GetADISCORDExternalLoanAvailabilityLoc]" in localisation,
            "loan tooltips do not expose the current failed requirement")
    for trigger_name in ("ADISCORD_economy_can_issue_internal_bonds", "ADISCORD_economy_can_take_external_loan"):
        require("has_tech =" not in block(triggers, trigger_name),
                f"ordinary debt action still has an unrelated technology gate: {trigger_name}")
    require("ADISCORD_economy_loan_blocked_technology" not in scripted_loc
            and "ADISCORD_economy_loan_blocked_technology" not in localisation,
            "loan UI still documents the removed technology gate")

    base_gains = numeric_assignments(effects, "ADISCORD_economy_base_monthly_development_gain")
    require(any(value > 0 for value in base_gains), "base monthly economic-development gain is never positive")
    development = block(effects, "ADISCORD_economy_calculate_development_multiplier")
    require(
        re.search(
            r"set_variable\s*=\s*\{\s*var\s*=\s*ADISCORD_economy_base_monthly_development_gain\s+value\s*=\s*[1-9]",
            development,
        )
        is not None,
        "development calculation does not establish a positive organic base",
    )
    require(
        "add_to_variable = { var = ADISCORD_economy_base_monthly_development_gain value = ADISCORD_economic_development_monthly_growth }"
        in development,
        "content-driven economic growth is not added to the organic base",
    )
    require(
        "value = ADISCORD_economic_development_monthly_growth" not in re.sub(
            r"add_to_variable\s*=\s*\{[^{}]*ADISCORD_economic_development_monthly_growth[^{}]*\}", "", development
        ),
        "development calculation overwrites its organic base with the legacy growth variable",
    )

    require("ADISCORD_economy_casualties_snapshot_k" in effects, "economy lacks a cumulative casualty snapshot")
    require("ADISCORD_economy_monthly_casualties_delta_k" in effects, "economy lacks a monthly casualty delta")
    for effect_name in ("ADISCORD_economy_update_war_fatigue", "ADISCORD_economy_update_demographic_fatigue"):
        effect_block = block(effects, effect_name)
        require(bool(effect_block), f"missing {effect_name}")
        require("ADISCORD_economy_monthly_casualties_delta_k" in effect_block, f"{effect_name} does not use casualty delta")
        require("casualties_k" not in effect_block, f"{effect_name} still charges lifetime casualties every tick")

    require("ADISCORD_economy_ai_state" in effects, "economy lacks the AI state variable")
    require("ADISCORD_economy_update_ai_state" in effects, "economy lacks the AI state transition effect")
    require("ADISCORD_economy_ai_participates" in triggers, "economy lacks an explicit secondary-AI participation contract")
    for state in ("healthy", "stressed", "crisis", "recovery"):
        require(f"ADISCORD_economy_ai_is_{state}" in triggers, f"missing AI economy trigger for {state}")
        require("ADISCORD_economy_ai_participates" in block(triggers, f"ADISCORD_economy_ai_is_{state}"),
                f"AI economy state {state} can activate for a dormant country")

    monthly = block(effects, "ADISCORD_economy_monthly_update")
    weekly = block(effects, "ADISCORD_economy_weekly_update")
    yearly = block(effects, "ADISCORD_economy_yearly_update")
    weekly_gate = block(triggers, "ADISCORD_economy_should_weekly_update")
    weekly_prepare = block(effects, "ADISCORD_economy_prepare_weekly_country")
    require("ADISCORD_economy_update_ai_state" in monthly, "monthly update does not refresh AI state")
    require("ADISCORD_economy_apply_yearly_balance" in yearly, "secondary yearly economy lacks aggregate fiscal semantics")
    require("ADISCORD_economy_tick_scale value = 6" in yearly,
            "secondary AI does not use the explicit half-pressure annual stabilizer")
    require("ADISCORD_economy_update_workforce_drain" in yearly,
            "secondary yearly economy omits workforce pressure")
    require(yearly.rfind("ADISCORD_economy_update_ai_state") > yearly.find("ADISCORD_economy_apply_yearly_balance"),
            "secondary AI state is not refreshed after its annual transaction")
    require("ADISCORD_economy_full_refresh = yes" not in monthly.split("ADISCORD_economy_building_recount_months", 1)[0],
            "monthly update performs an unconditional building scan")
    require("ADISCORD_economy_full_refresh_if_needed" in monthly,
            "monthly update lacks a dirty-state building refresh")
    require("ADISCORD_economy_tick_budget_cooldowns" in monthly,
            "monthly update does not release budget-control cooldowns")
    require("ADISCORD_economy_apply_monthly_balance" not in monthly
            and "ADISCORD_economy_apply_weekly_balance" not in monthly,
            "monthly strategy update still changes treasury")
    require(monthly.find("ADISCORD_economy_update_monthly_budget_trend") < monthly.find("ADISCORD_economy_tick_budget_cooldowns"),
            "budget cooldowns expire before monthly fiscal pressure is recorded")
    require(weekly.count("ADISCORD_economy_apply_weekly_balance") == 1,
            "weekly economy does not contain exactly one cash settlement")
    require("ADISCORD_economy_full_refresh" not in weekly
            and "ADISCORD_economy_recount_economic_buildings" not in weekly,
            "weekly economy directly invokes a heavy building refresh")
    light_update = block(effects, "ADISCORD_economy_light_update")
    require("ADISCORD_economy_calculate_weekly_budget = yes" in light_update,
            "light economy refresh leaves the player-facing weekly forecast stale")
    require("ADISCORD_economy_calculate_weekly_budget = yes" not in weekly,
            "weekly settlement duplicates the forecast already refreshed by the light update")
    require("ADISCORD_economy_prepare_weekly_country" in weekly
            and "ADISCORD_economy_initialize_country" not in weekly,
            "weekly economy does not use the lightweight preparation path")
    require("ADISCORD_economy_simulation_tier" in weekly_gate
            and "ADISCORD_economy_is_primary_tier_country" not in weekly_gate,
            "weekly eligibility recalculates primary status instead of using the cached tier")
    require(not any(token in weekly_gate for token in ("any_enemy_country", "any_country", "every_country")),
            "weekly eligibility contains a country iteration")
    require("ADISCORD_economy_set_simulation_tier" not in weekly_prepare
            and not any(token in weekly_prepare for token in ("any_enemy_country", "any_country", "every_country", "every_owned_state")),
            "weekly preparation recalculates the tier or scans countries/states")
    control_change = block(on_actions, "on_state_control_changed")
    require(control_change.count("ADISCORD_economy_mark_dirty = yes") == 2
            and control_change.count("has_variable = ADISCORD_economy_initialized") == 2,
            "state control changes do not invalidate both existing economy caches")
    require("every_country" not in control_change and "every_owned_state" not in control_change,
            "state control cache invalidation performs a global or state scan")

    stretched = block(effects, "ADISCORD_economy_update_stretched")
    require("ADISCORD_economy_planned_shortage_pressure" in stretched,
            "planned shortages do not feed the derived overstretch score")
    require("ADISCORD_economy_action_overload_residue" in stretched,
            "one-off action overload does not persist into the derived overstretch score")
    effects_without_stretched = effects.replace(stretched, "")
    require(
        re.search(r"add_to_variable\s*=\s*\{\s*var\s*=\s*ADISCORD_economy_stretched_score", effects_without_stretched) is None,
        "an action writes directly into the derived overstretch score and will be erased",
    )

    macro = block(effects, "ADISCORD_economy_calculate_macro_indicators")
    ordered_steps = [
        "ADISCORD_economy_calculate_debt_metrics",
        "ADISCORD_economy_update_macro_confidence",
    ]
    positions = [macro.find(step) for step in ordered_steps]
    require(all(position >= 0 for position in positions), "macro pass is missing a required derived calculation")
    require(positions == sorted(positions), "macro pass is not ordered deterministically")
    for step in ordered_steps:
        require(macro.count(step) == 1, f"macro pass must call {step} exactly once")

    policy = block(effects, "ADISCORD_economy_ai_monthly_policy")
    require("else_if" in policy, "AI monthly policy is not an exclusive ordered decision chain")
    require("ADISCORD_economy_increase_army_spending" in policy, "AI never restores army spending")
    require("ADISCORD_economy_increase_research_spending" in policy, "AI never restores research spending")
    require("ADISCORD_economy_decrease_research_spending" in policy, "AI never reduces research during fiscal stress")
    require("ADISCORD_economy_increase_social_spending" in policy, "AI never restores social spending")
    require("ADISCORD_economy_construction_spending" not in policy,
            "AI still treats automatic construction expense as a policy")

    assistance_specs = {
        "ADISCORD_economy_ai_assistance_base": {
            "ADISCORD_economy_overall_income_factor": 0.05,
            "industrial_capacity_factory": 0.05,
        },
        "ADISCORD_economy_ai_assistance_civil_war": {
            "supply_consumption_factor": -0.10,
        },
        "ADISCORD_economy_ai_assistance_retreat": {
            "army_defence_factor": 0.05,
        },
    }
    assistance_refresh = block(
        minor_effects + "\n" + effects, "ADISCORD_economy_refresh_ai_assistance"
    )
    require(bool(assistance_refresh), "economy lacks a cached AI-assistance refresh")
    if assistance_refresh:
        require("is_ai = yes" in assistance_refresh,
                "economy assistance can be applied to a player")
        require("ADISCORD_economy_simulation_tier" in assistance_refresh,
                "economy assistance ignores the simulation tier")
        require("surrender_progress" in assistance_refresh and "> 0.35" in assistance_refresh,
                "retreat assistance lacks the bounded surrender threshold")
    for idea_name, expected_modifiers in assistance_specs.items():
        idea = block(minor_ideas, idea_name)
        require(bool(idea), f"minor optimization lacks {idea_name}")
        if idea:
            require("allowed = { always = no }" in idea,
                    f"{idea_name} is visible instead of hidden")
            require(idea_name not in ideas,
                    f"{idea_name} is duplicated in the economy idea file")
            for modifier, expected in expected_modifiers.items():
                values = scalar_assignments(idea, modifier)
                if modifier == "supply_consumption_factor":
                    require(len(values) == 1 and expected <= values[0] <= 0,
                            f"{idea_name} violates the {modifier} assistance bound")
                else:
                    require(values == [expected],
                            f"{idea_name} violates the {modifier} assistance bound")
        if assistance_refresh:
            require(f"remove_ideas = {idea_name}" in assistance_refresh,
                    f"{idea_name} has no immediate removal path")
            require(f"add_ideas = {idea_name}" in assistance_refresh,
                    f"{idea_name} is never applied under its bounded condition")

    emission = block(effects, "ADISCORD_economy_expand_money_emission")
    require("ADISCORD_economy_treasury" in emission, "money emission creates no liquidity")
    require("ADISCORD_economy_current_month_action_income" in effects, "ledger lacks action-income accounting")
    reduce_emission = block(effects, "ADISCORD_economy_reduce_money_emission")
    require("ADISCORD_economy_recent_money_printing" in reduce_emission,
            "emission can be expanded and reversed in the same accounting month")
    require("ADISCORD_economy_has_treasury_room_35" in block(triggers, "ADISCORD_economy_can_expand_money_emission"),
            "money emission can charge penalties when the treasury has no room")
    require("ADISCORD_economy_has_debt_room_" not in triggers,
            "loan availability still uses a retired room gate")

    apply_balance = block(effects, "ADISCORD_economy_apply_weekly_balance")
    require("ADISCORD_economy_last_period_cap_writeoff" in apply_balance,
            "treasury-cap overflow is not recorded in the ledger")
    require(apply_balance.find("ADISCORD_economy_last_period_cap_writeoff") < apply_balance.find("ADISCORD_economy_treasury_after_tick"),
            "treasury is snapshotted before cap overflow is recorded")
    require("value = ADISCORD_economy_last_period_cap_writeoff" in apply_balance,
            "cap writeoff is missing from the accounting identity")
    # Full-deficit funding is owned by automatic_borrow_flow_issues above. Its
    # parsed data-flow contract requires one exact uncovered amount, one direct
    # addition to debt and treasury, and rejects caps, rewrites, nested funding,
    # or a hidden remainder. A separate unfunded ledger adjustment would now
    # invent cash that cannot exist after the exact transfer.

    timed_actions = {
        "ADISCORD_economy_expand_money_emission": "ADISCORD_economy_money_printing",
        "ADISCORD_economy_civilian_investment_action": "ADISCORD_economy_civilian_investment",
        "ADISCORD_economy_military_investment_action": "ADISCORD_economy_military_investment",
        "ADISCORD_economy_war_taxes_action": "ADISCORD_economy_war_taxes",
    }
    for effect_name, idea_name in timed_actions.items():
        action = block(effects, effect_name)
        require(
            re.search(
                rf"add_timed_idea\s*=\s*\{{\s*idea\s*=\s*{re.escape(idea_name)}\s+days\s*=\s*30\s*\}}",
                action,
            )
            is not None,
            f"{effect_name} does not keep {idea_name} active for exactly 30 days",
        )
    legacy_cleanup = block(effects, "ADISCORD_economy_clear_one_month_action_ideas")
    require("remove_ideas" not in legacy_cleanup,
            "monthly cleanup still shortens 30-day action ideas at the calendar boundary")
    for trigger_name, idea_name in (
        ("ADISCORD_economy_can_print_money", "ADISCORD_economy_money_printing"),
        ("ADISCORD_economy_can_reduce_money_emission", "ADISCORD_economy_money_printing"),
        ("ADISCORD_economy_can_use_civilian_stimulus", "ADISCORD_economy_civilian_investment"),
        ("ADISCORD_economy_can_use_military_investment", "ADISCORD_economy_military_investment"),
        ("ADISCORD_economy_can_use_war_taxes", "ADISCORD_economy_war_taxes"),
    ):
        require(idea_name in block(triggers, trigger_name),
                f"{trigger_name} allows its 30-day action spirit to be bypassed")

    repay = block(effects, "ADISCORD_economy_repay_debt")
    early_repay = block(effects, "ADISCORD_economy_early_repay_debt")
    require("1.20" not in repay, "ordinary debt repayment still destroys more debt than treasury")
    require("1.25" not in early_repay, "early debt repayment still destroys more debt than treasury")
    restructure = block(effects, "ADISCORD_economy_restructure_debt")
    require("ADISCORD_economy_recent_debt" in restructure,
            "debt restructuring has no accounting-period lock")
    for effect_name in (
        "ADISCORD_economy_calculate_debt_metrics",
        "ADISCORD_economy_update_debt_state_after_settlement",
        "ADISCORD_economy_reconcile_debt_state_after_action",
        "ADISCORD_economy_queue_debt_notification",
    ):
        require(bool(block(effects, effect_name)), f"schema 12 lacks {effect_name}")
    for repayment_name in (
        "ADISCORD_economy_repay_debt",
        "ADISCORD_economy_early_repay_debt",
        "ADISCORD_economy_restructure_debt",
    ):
        repayment = block(effects, repayment_name)
        require("ADISCORD_economy_calculate_debt_metrics = yes" in repayment,
                f"{repayment_name} leaves interest metrics stale")
        require("ADISCORD_economy_reconcile_debt_state_after_action = yes" in repayment,
                f"{repayment_name} cannot lower the debt debuff immediately")

    for cooldown in (
        "ADISCORD_economy_tax_change_cooldown",
        "ADISCORD_economy_army_budget_change_cooldown",
        "ADISCORD_economy_research_budget_change_cooldown",
        "ADISCORD_economy_social_budget_change_cooldown",
    ):
        require(cooldown in effects and cooldown in triggers, f"budget control lacks cooldown {cooldown}")
        require(f"var = {cooldown} min = 0 max = 3" in effects,
                f"strategic budget cooldown {cooldown} is not three months")

    require("ADISCORD_economy_set_budget_course_" not in effects
            and "ADISCORD_economy_can_select_budget_course_" not in triggers,
            "obsolete all-in-one budget courses remain wired into the economy")

    social_expenses = block(effects, "ADISCORD_economy_calculate_social_expenses")
    for multiplier in ("0.45", "0.75", "1.00", "1.35", "1.80"):
        require(f"value = {multiplier}" in social_expenses,
                f"social budget lacks the distinct {multiplier} cost multiplier")
    for level in range(1, 6):
        idea_name = f"ADISCORD_economy_social_spending_{level}"
        require(idea_name in ideas, f"social budget level {level} has no gameplay idea")
        require(effects.count(idea_name) >= 2,
                f"social budget level {level} is not refreshed with policy ideas")

    army_expenses = block(effects, "ADISCORD_economy_calculate_army_expenses")
    require("has_army_manpower" in army_expenses, "army upkeep is disconnected from fielded manpower")
    require(re.search(r"has_army_manpower\s*=\s*\{\s*size\s*>", army_expenses) is not None,
            "army-upkeep manpower thresholds do not use the engine-supported comparison syntax")
    resource_income = block(effects, "ADISCORD_economy_calculate_resource_income")
    policy_refresh = block(
        modifier_effects, "ADISCORD_economy_recalculate_policy_modifiers"
    )
    recount = block(effects, "ADISCORD_economy_recount_economic_buildings")
    require("ADISCORD_economy_resource_endowment" in resource_income,
            "strategic rent ignores the country's resource endowment")
    require("set_variable = { var = ADISCORD_economy_resource_income value = ADISCORD_economy_resource_endowment }" in resource_income,
            "strategic rent is not rooted in the cached resource endowment")
    require(
        "multiply_variable = { var = ADISCORD_economy_resource_income value = ADISCORD_economy_cached_resource_trade_law_factor }"
        in resource_income,
        "trade law is not applied as a cached multiplier of real resource rent",
    )
    require(
        "ADISCORD_economy_has_idea_free_trade = yes" in policy_refresh
        and "var = ADISCORD_economy_cached_resource_trade_law_factor value = 1.25"
        in policy_refresh,
        "free trade does not refresh the cached resource-rent multiplier",
    )
    require(
        "add_to_variable = { var = ADISCORD_economy_resource_income value = ADISCORD_economy_cached_resource_trade_law_factor }"
        not in resource_income,
        "trade law creates resource income for countries without resources",
    )
    require("resource@steel" in recount and "resource@oil" in recount and "resource@coal" in recount,
            "owned-state refresh does not build a real resource-endowment index")
    require("check_variable = { resource@steel >" in recount,
            "resource-endowment checks do not use the engine-supported state resource syntax")
    require("damaged_building_level@industrial_complex" in recount,
            "bombing disruption is not connected to actual damaged industry")
    require("ADISCORD_economy_public_investment_stock" in effects,
            "reserve investment has no persistent productive-capital stock")
    require(recount.count("every_owned_state") == 1 and "every_country" not in recount,
            "economic buildings are not recounted in one country-local owned-state pass")

    expected_building_costs = {
        "ADISCORD_business_center": "750",
        "ADISCORD_science_center": "1250",
        "ADISCORD_industrial_cluster": "1500",
    }
    for building_name, extra_cost in expected_building_costs.items():
        building = block(buildings, building_name)
        require(bool(building), f"missing economic building {building_name}")
        require(f"per_controlled_building_extra_cost = {extra_cost}" in building,
                f"{building_name} does not become progressively more expensive")
    require("state_production_speed_buildings_factor = 0.05" in block(buildings, "ADISCORD_business_center"),
            "business center lacks its distinct commercial-slot role")
    require("local_building_slots_factor = 0.10" in block(buildings, "ADISCORD_business_center"),
            "business center lacks its stronger regional slot bonus")
    require("local_building_slots_factor = 0.06" in block(buildings, "ADISCORD_science_center"),
            "science center still duplicates the stronger commercial/industrial state role")
    require("local_factory_energy_consumption = 0.10" in block(buildings, "ADISCORD_industrial_cluster"),
            "industrial cluster lacks its visible heavy-industry energy burden")
    require("state_production_speed_buildings_factor = 0.10" in block(buildings, "ADISCORD_industrial_cluster"),
            "industrial cluster lacks its stronger regional construction bonus")
    cluster_output = block(dynamic_modifiers, "ADISCORD_economy_cluster_local_factory_output")
    require("industrial_capacity_factory = ADISCORD_economy_cluster_factory_output_factor" in cluster_output,
            "industrial cluster lacks its location-weighted military-factory output modifier")
    require("building_level@arms_factory" in recount
            and "damaged_building_level@arms_factory" in recount
            and "is_controlled_by = ROOT" in recount
            and "ADISCORD_economy_state_cluster_level_temp" in recount,
            "industrial cluster output is not tied to operational military factories in its state")
    require("ADISCORD_economy_cluster_supported_factory_points_temp" in recount
            and "ADISCORD_economy_operational_military_factories_temp" in recount
            and "force_update_dynamic_modifier = yes" in recount,
            "industrial cluster weighted output is not refreshed by the cached state recount")
    require(recount.count("is_controlled_by = ROOT") >= 2,
            "occupied economic buildings still contribute income or national network bonuses")
    require("ADISCORD_economy_cluster_factory_output_percent value = 5" in recount
            and "ADISCORD_economy_cluster_factory_output_factor value = 100" in recount
            and "max = 15" in recount,
            "industrial cluster output formula is not bounded to +5% per state level")
    custom_targets = [int(value) for value in re.findall(
        r"building_target\s+id\s*=\s*ADISCORD_(?:business_center|science_center|industrial_cluster)\s+value\s*=\s*(\d+)",
        economy_ai,
    )]
    require(bool(custom_targets) and max(custom_targets) <= 3,
            "AI economic-building targets are missing or encourage uncontrolled construction")

    factory_source_cache = block(effects, "ADISCORD_economy_cache_weekly_factory_sources")
    construction_expenses = block(effects, "ADISCORD_economy_calculate_construction_expenses")
    require("num_of_available_civilian_factories" in factory_source_cache
            and "ADISCORD_economy_cached_available_civilian_factories" in construction_expenses
            and "num_of_available_civilian_factories" not in construction_expenses,
            "construction expenses do not consume cached assigned civilian capacity")
    military_factory_expenses = block(effects, "ADISCORD_economy_calculate_military_factory_expenses")
    require("num_of_available_military_factories" in factory_source_cache
            and "ADISCORD_economy_cached_available_military_factories" in military_factory_expenses
            and "num_of_available_military_factories" not in military_factory_expenses,
            "military-industry expenses do not consume cached assigned factories")
    bombing = block(effects, "ADISCORD_economy_update_bombing_disruption")
    require("ADISCORD_economy_damage_index_temp" in bombing and "num_of_civilian_factories" in bombing,
            "bombing damage is not normalized by country industry")
    workforce = block(effects, "ADISCORD_economy_update_workforce_drain")
    require("has_army_manpower" in workforce and "ADISCORD_economy_army_expenses" not in workforce,
            "workforce drain can be erased merely by cutting army pay")
    require("ADISCORD_economy_apply_institutional_income_factors" in block(effects, "ADISCORD_economy_calculate_income"),
            "financial-control and confidence KPIs remain cosmetic")
    idea_refresh = block(effects, "ADISCORD_economy_refresh_spending_ideas")
    require("ADISCORD_economy_last_idea_signature" in idea_refresh,
            "economy still churns all national spirits every regular refresh")
    require("ADISCORD_economy_social_spending_mode" in idea_refresh,
            "social budget changes do not invalidate the optimized idea signature")
    require("ADISCORD_economy_research_spending_mode" in idea_refresh,
            "research budget changes do not invalidate the optimized idea signature")
    require("ADISCORD_economy_construction_spending_mode" not in idea_refresh,
            "retired construction policy remains in the idea signature")

    migration = block(effects, "ADISCORD_economy_migrate_schema")
    require("value = 12 compare = less_than" in migration,
            "economy save migration was not advanced to schema 12")
    require("ADISCORD_economy_research_spending_mode" in migration
            and "value = ADISCORD_economy_construction_spending_mode" in migration,
            "schema 12 does not map the former construction setting to research")
    require("ADISCORD_economy_research_budget_change_cooldown value = 0" in migration,
            "schema 12 does not release the new research-policy cooldown")
    require("ADISCORD_economy_recalculate_policy_modifiers = yes" in migration,
            "schema 12 does not initialize weekly policy caches for existing saves")
    require("ADISCORD_economy_was_at_war" in migration
            and "ADISCORD_economy_postwar_demobilization_months" in migration,
            "schema 12 does not preserve postwar demobilization state")
    weekly_budget = block(effects, "ADISCORD_economy_calculate_weekly_budget")
    require("ADISCORD_economy_safe_reserve value = ADISCORD_economy_weekly_expenses" in weekly_budget
            and "ADISCORD_economy_safe_reserve min = 50 max = 250" in weekly_budget,
            "schema 12 reserve target does not reuse the O(1) weekly forecast")
    for settlement_name in ("ADISCORD_economy_apply_weekly_balance", "ADISCORD_economy_apply_monthly_balance"):
        settlement = block(effects, settlement_name)
        require("ADISCORD_economy_auto_borrow_temp" in settlement
                and "ADISCORD_economy_auto_loan_enabled" not in settlement,
                f"{settlement_name} still allows hidden save state to disable deficit borrowing")
    for retired_name in (
        "ADISCORD_economy_auto_loan_enabled",
        "ADISCORD_economy_toggle_auto_loan",
        "ADISCORD_economy_gui_page",
        # The two retired construction variables have one exact schema-12
        # migration exception, validated structurally by
        # migration_contract_issues() above.  Do not reject that migration via
        # this coarse whole-file substring guard.
        "ADISCORD_economy_admin_spending_mode",
        "ADISCORD_economy_weekly_player_refresh",
        "ADISCORD_economy_gui_try_early_repay_debt",
        "ADISCORD_economy_gui_try_expand_emission",
        "ADISCORD_economy_gui_try_reduce_emission",
        "ADISCORD_economy_gui_try_invest_reserves",
        "ADISCORD_economy_gui_try_civilian_investment",
        "ADISCORD_economy_gui_try_military_investment",
    ):
        require(retired_name not in effects, f"retired economy state is still live: {retired_name}")
    cycle = block(effects, "ADISCORD_economy_update_model_and_cycle")
    require("ADISCORD_economy_cycle_phase value = 4" not in cycle
            and "ADISCORD_economy_cycle_phase value = 5" not in cycle
            and "ADISCORD_economy_cycle_phase value = 6" not in cycle
            and "ADISCORD_economy_cycle_phase value = 7" not in cycle,
            "dashboard still computes model-specific pseudo-cycles above the four readable states")
    require("clamp_variable = { var = ADISCORD_economy_cycle_phase min = 0 max = 3 }" in effects,
            "economy cycle is not clamped to the four-state contract")
    require(scripted_loc.count("localization_key = ADISCORD_economy_cycle_") == 4,
            "scripted localisation exposes more than four economy-cycle states")

    require('name = "ADISCORD_economy_dashboard_window"' in gui, "economy dashboard window is missing")
    require('position = { x = 6 y = 78 }' in gui and re.search(r"Orientation\s*=\s*UPPER_LEFT", gui, re.I),
            "economy dashboard is not docked beside the native top-bar windows")
    require("size = { width = 840 height = 560 }" in gui,
            "economy dashboard no longer fits the supported 1366x768 layout envelope")
    require("ADISCORD_economy_header_art" not in gui,
            "economy dashboard still uses the broken decorative header sprite")
    require(len(re.findall(r'name\s*=\s*"ADISCORD_economy_(?:tax|army|research|social)_step_[1-5]"', gui)) == 20,
            "economy dashboard does not expose four complete five-step scales")
    require(len(re.findall(r'name\s*=\s*"ADISCORD_economy_(?:tax|army|research|social)_active_marker"', gui)) == 4,
            "economy dashboard does not expose one active marker per budget scale")
    require(re.search(r'buttonText\s*=\s*"[+-]"', gui) is None,
            "economy dashboard still uses blank text +/- controls")
    require("GFX_button_123x34" not in gui,
            "economy dashboard still uses the button sprite that clips compact policy controls")
    require(not (root / "common/decisions/ADISCORD_economy_decisions.txt").exists(),
            "economy actions have returned to the decisions menu")
    require(not (root / "common/decisions/categories/ADISCORD_economy_categories.txt").exists(),
            "economy decision category still exists")
    require(not (root / "common/decisions/ADISCORD_society_development_debug_decisions.txt").exists(),
            "society-development debug decisions are exposed at game start")
    require(not (root / "common/decisions/categories/ADISCORD_society_development_debug_categories.txt").exists(),
            "society-development debug category is exposed at game start")
    require("ADISCORD_economy_tab_" not in gui and "ADISCORD_economy_budget_page" not in gui
            and "ADISCORD_economy_operations_page" not in gui,
            "economy dashboard still exposes the old multi-tab office UI")
    require("ADISCORD_economy_overview_page" not in gui
            and "ADISCORD_economy_overview_script" not in scripted_gui,
            "economy content remains a separate window that can disappear behind the shell")
    dashboard_start = gui.find('name = "ADISCORD_economy_dashboard_window"')
    dashboard_gui = gui[dashboard_start:] if dashboard_start >= 0 else ""
    require("ADISCORD_economy_status_panel" in dashboard_gui
            and "ADISCORD_economy_command_panel" in dashboard_gui,
            "dashboard content is not nested inside the single registered window")
    dashboard_script = block(scripted_gui, "ADISCORD_economy_dashboard_script")
    require('window_name = "ADISCORD_economy_dashboard_window"' in dashboard_script
            and "ADISCORD_economy_window_is_open = yes" in dashboard_script,
            "single economy window is not bound to the open-state trigger")
    open_window = block(effects, "ADISCORD_economy_open_window")
    require(
        re.search(
            r"if\s*=\s*\{\s*limit\s*=\s*\{\s*"
            r"ADISCORD_economy_should_show_player_ui\s*=\s*yes\s*\}"
            r"[\s\S]*?ADISCORD_economy_initialize_country\s*=\s*yes",
            open_window,
        )
        is not None,
        "observer opening the economy dashboard can mutate the selected AI country",
    )

    for removed_control in (
        "ADISCORD_economy_tax_burden_1", "ADISCORD_economy_army_budget_1",
        "ADISCORD_economy_construction_budget_1",
        "ADISCORD_economy_action_early_repay_debt", "ADISCORD_economy_action_expand_emission",
        "ADISCORD_economy_action_civilian_investment", "ADISCORD_economy_action_military_investment",
    ):
        require(removed_control not in gui, f"simplified economy UI still exposes {removed_control}")
    require("ADISCORD_economy_course_" not in gui,
            "economy UI still exposes preset courses instead of direct compact controls")
    visible_regulators = set(re.findall(
        r'name\s*=\s*"(ADISCORD_economy_(?:tax|army|research|social)_(?:decrease|increase))"', gui
    ))
    expected_regulators = {
        f"ADISCORD_economy_{category}_{direction}"
        for category in ("tax", "army", "research", "social")
        for direction in ("decrease", "increase")
    }
    require(visible_regulators == expected_regulators,
            "economy UI must expose exactly eight compact arrow budget controls")
    for category in ("tax", "army", "research", "social"):
        require(re.search(
            rf'name\s*=\s*"ADISCORD_economy_{category}_decrease"[\s\S]{{0,200}}spriteType\s*=\s*"button_left"',
            gui,
        ) is not None, f"economy {category} decrease control is not a left arrow")
        require(re.search(
            rf'name\s*=\s*"ADISCORD_economy_{category}_increase"[\s\S]{{0,200}}spriteType\s*=\s*"button_right"',
            gui,
        ) is not None, f"economy {category} increase control is not a right arrow")
    visible_actions = set(re.findall(r'name\s*=\s*"(ADISCORD_economy_action_[^"]+)"', gui))
    expected_actions = {
        "ADISCORD_economy_action_internal_bonds",
        "ADISCORD_economy_action_external_loan",
        "ADISCORD_economy_action_repay_debt",
        "ADISCORD_economy_action_restructure_debt",
        "ADISCORD_economy_action_stabilization",
        "ADISCORD_economy_action_war_taxes",
    }
    require(visible_actions == expected_actions,
            "economy UI must expose exactly six focused treasury operations")
    require(
        'pdx_tooltip = "ADISCORD_economy_balance_tt"' in gui
        and 'pdx_tooltip_delayed = "ADISCORD_economy_balance_delayed_tt"' in gui,
        "balance KPI lacks the requested short/delayed income and expense breakdown",
    )
    require('name = "ADISCORD_economy_topbar_button"' in gui
            and 'quadTextureSprite = "GFX_ADISCORD_economy_topbar_button"' in gui,
            "topbar lacks the dedicated economy button")
    require('name = "ADISCORD_economy_topbar_icon"' not in gui
            and 'name = "ADISCORD_economy_topbar_value"' not in gui,
            "topbar still overlays the retired treasury icon/value composition")
    require('name = "GFX_ADISCORD_economy_topbar_button"' in interface_gfx,
            "economy topbar button sprite is not registered")

    gui_buttons = set(re.findall(r'buttonType\s*=\s*\{.*?name\s*=\s*"(ADISCORD_economy_[^"]+)"', gui, re.S))
    require(bool(gui_buttons), "economy dashboard contains no discoverable interactive buttons")
    for button_name in sorted(gui_buttons):
        require(f"{button_name}_click" in scripted_gui, f"GUI button {button_name} has no scripted click effect")
        guarded = button_name in expected_regulators or "_action_" in button_name
        if guarded:
            require(f"{button_name}_click_enabled" in scripted_gui,
                    f"GUI button {button_name} gives no disabled-state feedback")

    guarded_actions = {
        "internal_bonds": "issue_internal_bonds",
        "external_loan": "take_external_loan",
        "repay_debt": "repay_debt",
        "restructure_debt": "restructure_debt",
        "stabilization": "stabilization",
        "war_taxes": "war_taxes",
    }
    for action, effect in guarded_actions.items():
        require(f'ADISCORD_economy_action_{action}' in gui,
                f"the dashboard does not expose the {action} economy operation")
        require(f"ADISCORD_economy_gui_try_{effect}" in effects,
                f"the dashboard operation {action} has no guarded GUI effect")

    localisation_keys = set(re.findall(r"(?m)^\s*([A-Za-z0-9_.-]+):", localisation))
    for match in re.finditer(r'(?:text|buttonText|pdx_tooltip)\s*=\s*"([^"]+)"', gui):
        key = match.group(1)
        if key in {"CLOSE", "X", "+", "-", "1", "2", "3", "4", "5"}:
            continue
        require(key in localisation_keys, f"economy GUI references missing localisation key {key}")
    custom_sprites = set(re.findall(r'"(GFX_ADISCORD_economy_[^"]+)"', gui))
    for sprite in custom_sprites:
        require(f'name = "{sprite}"' in interface_gfx, f"economy GUI references undefined sprite {sprite}")
    require("GetADISCORDEconomyAdviceLoc" in scripted_loc,
            "economy dashboard has no contextual policy recommendation")

    monthly_on_action = block(block(on_actions, "on_actions"), "on_monthly")
    require("every_country" not in monthly_on_action, "on_monthly contains a global country scan")
    weekly_on_action = block(block(on_actions, "on_actions"), "on_weekly")
    require("ADISCORD_economy_should_weekly_update" in weekly_on_action,
            "on_weekly lacks the primary-economy eligibility gate")
    require(weekly_on_action.count("ADISCORD_economy_weekly_update") == 1,
            "on_weekly does not invoke exactly one economy settlement")
    require(not any(token in weekly_on_action for token in ("every_country", "every_owned_state", "all_owned_state")),
            "on_weekly contains a country or state scan")

    unsupported_generic_roles = (
        "strategic_bomber",
        "naval_bomber",
        "heavy_fighter",
        "capital_ship",
        "screen_ship",
        "submarine",
        "marines",
        "paratroopers",
    )
    for role in unsupported_generic_roles:
        require(not re.search(rf"\bid\s*=\s*{role}\b", default_ai), f"generic AI still desires unsupported role {role}")

    require(re.search(r"type\s*=\s*avoid_starting_wars\s+value\s*=\s*-", economy_ai) is not None,
            "overstretched AI does not suppress war-starting desire")
    for profile in re.finditer(r"(?m)^\s*(ADISCORD_ai_[\w]+)\s*=\s*\{", economy_ai):
        profile_block = block(economy_ai, profile.group(1))
        require("abort_when_not_enabled = yes" in profile_block,
                f"{profile.group(1)} can leave stale AI strategy values active")

    forbidden_regular_loop_tokens = ("for_each_loop", "for_each_scope_loop", "while_loop_effect", "global.technology")
    for token in forbidden_regular_loop_tokens:
        require(token not in monthly and token not in yearly, f"regular economy pulse contains forbidden expensive token {token}")

    return issues


def main() -> int:
    issues = validate()
    if issues:
        print("A-DISCORD economy/AI validation: FAIL")
        for issue in issues:
            print(f"- {issue}")
        return 1
    print("A-DISCORD economy/AI validation: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
